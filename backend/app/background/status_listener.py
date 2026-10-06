"""Applies worker status updates to processing sessions and matches."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.background.stream_consumer import Message, parse_envelope
from app.core.logging import get_logger
from app.core.redis_keys import control_key
from app.db.models import MatchStatus
from app.repositories.match_repo import MatchRepository
from app.repositories.session_repo import SessionRepository
from app.services.status_machine import EXPECTED_CONTROL, TERMINAL_WORKER_STATUSES, WORKER_STATUS_MAP

log = get_logger(component="status_listener")

API_CLOSED_SESSION_STATUSES = {"stopped", "superseded"}


def status_handler(factory: async_sessionmaker[AsyncSession], redis: Redis):  # noqa: ANN201
    async def handle(messages: list[Message]) -> None:
        async with factory() as db:
            for _, fields in messages:
                env = parse_envelope(fields)
                if env is None:
                    log.warning("malformed status message skipped")
                    continue
                try:
                    async with db.begin_nested():
                        await apply_status(db, redis, env)
                except (KeyError, TypeError, ValueError):
                    log.exception("status message rejected", match_id=env.get("match_id"))
            await db.commit()

    return handle


async def apply_status(db: AsyncSession, redis: Redis, env: dict[str, Any]) -> None:
    data: dict[str, Any] = env["data"]
    worker_status = str(data.get("status", ""))
    session_id = env.get("session_id")
    if worker_status not in WORKER_STATUS_MAP or not session_id:
        return
    terminal = worker_status in TERMINAL_WORKER_STATUSES
    message = data.get("message")

    session = await SessionRepository(db).get(session_id)
    if session is not None:
        if session.status not in API_CLOSED_SESSION_STATUSES:
            session.status = worker_status
        session.worker_id = data.get("worker_id") or session.worker_id
        session.device = data.get("device") or session.device
        stats = data.get("stats") or {}
        if stats:
            session.frames_processed = int(stats.get("frames_processed", session.frames_processed))
            session.average_fps = stats.get("average_fps", session.average_fps)
            session.average_latency = stats.get("average_latency_ms", session.average_latency)
        if worker_status == "failed":
            session.error = message
        if terminal and session.stopped_at is None:
            session.stopped_at = datetime.now(UTC)

    match = await MatchRepository(db).get(env["match_id"])
    if match is None or match.current_session_id != session_id:
        return  # stale update from an earlier session
    if not terminal:
        if match.status in (MatchStatus.COMPLETED, MatchStatus.FAILED):
            return
        if await _desired_state(redis, match.id) != EXPECTED_CONTROL[worker_status]:
            return  # the user already changed the desired state; ignore the race
    elif worker_status == "stopped" and match.status is MatchStatus.COMPLETED:
        return

    match.status = WORKER_STATUS_MAP[worker_status]
    match.status_message = message
    if worker_status == "failed":
        match.last_error = message
    log.info("match status updated", match_id=match.id, status=match.status.value, worker_status=worker_status)


async def _desired_state(redis: Redis, match_id: str) -> str | None:
    raw = await redis.get(control_key(match_id))
    return json.loads(raw).get("state") if raw else None
