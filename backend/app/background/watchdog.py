"""Detects lost workers and stuck sessions; fails them with a clear reason."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.logging import get_logger
from app.core.redis_keys import control_key, lease_key
from app.db.models import Match, MatchStatus, ProcessingSession
from app.repositories.match_repo import MatchRepository
from app.repositories.session_repo import SessionRepository
from app.services.realtime import publish_match_status
from app.services.status_machine import ACTIVE_STATUSES
from app.services.system_service import list_workers

log = get_logger(component="watchdog")


class Watchdog:
    def __init__(self, factory: async_sessionmaker[AsyncSession], redis: Redis, settings: Settings) -> None:
        self._factory = factory
        self._redis = redis
        self._settings = settings
        self._misses: dict[str, int] = {}

    async def run(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            try:
                await self.check_once()
            except RedisError as exc:
                log.warning("watchdog cannot reach redis", error=str(exc))
            except Exception:  # noqa: BLE001 - never let the watchdog die
                log.exception("watchdog check failed")
            try:
                await asyncio.wait_for(stop.wait(), self._settings.watchdog_interval_s)
            except TimeoutError:
                pass

    async def check_once(self) -> None:
        async with self._factory() as db:
            matches = await MatchRepository(db).with_statuses(list(ACTIVE_STATUSES))
            if not matches:
                self._misses.clear()
                return
            worker_count = len(await list_workers(self._redis))
            failed: list[Match] = []
            for match in matches:
                reason = await self._failure_reason(db, match, worker_count)
                if reason is None:
                    continue
                # Re-read under a row lock: a user action or worker update may
                # have changed the match while we were checking Redis.
                session_id = match.current_session_id
                locked = await MatchRepository(db).get_for_update(match.id)
                if locked is None or locked.status not in ACTIVE_STATUSES or locked.current_session_id != session_id:
                    continue
                await self._fail(db, locked, reason)
                failed.append(locked)
            await db.commit()
        for match in failed:
            await publish_match_status(self._redis, match)

    async def _failure_reason(self, db: AsyncSession, match: Match, worker_count: int) -> str | None:
        raw = await self._redis.get(lease_key(match.id))
        if raw and json.loads(raw).get("session_id") == match.current_session_id:
            self._misses.pop(match.id, None)
            return None
        session = await SessionRepository(db).get(match.current_session_id) if match.current_session_id else None
        if match.status is MatchStatus.STARTING:
            if session is not None and _age_s(session) < self._settings.worker_start_timeout_s:
                return None
            if worker_count == 0:
                return "No inference worker is running. Start the worker service and try again."
            return "No inference worker picked up the job in time (all workers busy?)."
        self._misses[match.id] = self._misses.get(match.id, 0) + 1
        if self._misses[match.id] < self._settings.lost_lease_checks:
            return None
        self._misses.pop(match.id, None)
        return "Inference worker stopped responding (worker lost). Restart processing to continue."

    async def _fail(self, db: AsyncSession, match: Match, reason: str) -> None:
        log.error("processing session failed by watchdog", match_id=match.id, reason=reason)
        match.status = MatchStatus.FAILED
        match.last_error = reason
        match.status_message = None
        if match.current_session_id:
            session = await SessionRepository(db).get(match.current_session_id)
            if session is not None:
                session.status, session.error = "failed", reason
                session.stopped_at = session.stopped_at or datetime.now(UTC)
            stop = json.dumps({"session_id": match.current_session_id, "state": "stopped"})
            await self._redis.set(control_key(match.id), stop)


def _age_s(session: ProcessingSession) -> float:
    started = session.started_at
    if started.tzinfo is None:  # SQLite returns naive datetimes
        started = started.replace(tzinfo=UTC)
    return (datetime.now(UTC) - started).total_seconds()
