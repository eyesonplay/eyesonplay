"""Start / pause / resume / stop / restart a match's processing session.

The API is the only writer of desired state (`match:{id}:control`). Start
commands are queued on a Redis stream consumed by a worker consumer group.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ServiceUnavailableError
from app.core.ids import new_id
from app.core.logging import get_logger
from app.core.redis_keys import COMMANDS_STREAM, control_key
from app.db.models import Match, MatchStatus, ProcessingSession
from app.repositories.event_repo import EventRepository
from app.repositories.match_repo import MatchRepository
from app.repositories.session_repo import SessionRepository
from app.services.realtime import publish_match_status
from app.services.status_machine import Action, ensure_allowed

log = get_logger(component="processing")

COMMAND_STREAM_MAXLEN = 10_000


def control_value(session_id: str, state: str) -> str:
    return json.dumps({"session_id": session_id, "state": state})


def start_command(match: Match, session_id: str) -> dict[str, object]:
    assert match.video_source_type is not None and match.video_source is not None
    return {
        "command": "start",
        "match_id": match.id,
        "session_id": session_id,
        "config": {
            "sport": match.sport.value,
            "source_type": match.video_source_type.value,
            "source": match.video_source,
            "processing_fps": match.processing_fps,
            "detection_model": match.detection_model.value,
            "model_name": match.model_name,
            "confidence_threshold": match.confidence_threshold,
            "enable_event_detection": match.enable_event_detection,
            "enable_player_tracking": match.enable_player_tracking,
            "enable_pitch_mapping": match.enable_pitch_mapping,
            "kickoff_offset_seconds": match.kickoff_offset_seconds,
        },
    }


class ProcessingService:
    def __init__(self, db: AsyncSession, redis: Redis) -> None:
        self._db = db
        self._redis = redis
        self._matches = MatchRepository(db)
        self._sessions = SessionRepository(db)
        self._events = EventRepository(db)

    async def start(self, match_id: str) -> Match:
        match = await self._matches.get_or_404(match_id, for_update=True)
        ensure_allowed(match, Action.START)
        if match.status is MatchStatus.PAUSED and match.current_session_id:
            return await self._set_desired(match, "running", MatchStatus.PROCESSING, "Resuming processing")
        return await self._launch(match)

    async def restart(self, match_id: str) -> Match:
        match = await self._matches.get_or_404(match_id, for_update=True)
        ensure_allowed(match, Action.RESTART)
        await self._close_current_session(match, "superseded")
        # A restart reprocesses the source from the beginning, so earlier
        # detections would be duplicated; they are cleared (the UI warns).
        await self._events.delete_for_match(match.id)
        match.event_count = 0
        return await self._launch(match)

    async def pause(self, match_id: str) -> Match:
        match = await self._matches.get_or_404(match_id, for_update=True)
        ensure_allowed(match, Action.PAUSE)
        return await self._set_desired(match, "paused", MatchStatus.PAUSED, "Paused by user")

    async def stop(self, match_id: str) -> Match:
        match = await self._matches.get_or_404(match_id, for_update=True)
        ensure_allowed(match, Action.STOP)
        await self._close_current_session(match, "stopped")
        return await self._set_desired(match, "stopped", MatchStatus.COMPLETED, "Stopped by user")

    async def _launch(self, match: Match) -> Match:
        session = ProcessingSession(id=new_id("ses"), match_id=match.id, status="queued")
        self._sessions.add(session)
        match.current_session_id = session.id
        match.status = MatchStatus.STARTING
        match.status_message = "Queued for an inference worker"
        match.last_error = None
        await self._db.commit()
        try:
            pipe = self._redis.pipeline(transaction=True)
            pipe.set(control_key(match.id), control_value(session.id, "running"))
            pipe.xadd(
                COMMANDS_STREAM,
                {"payload": json.dumps(start_command(match, session.id))},
                maxlen=COMMAND_STREAM_MAXLEN,
                approximate=True,
            )
            await pipe.execute()
        except RedisError as exc:
            await self._mark_failed(match, session, f"Realtime service (Redis) unavailable: {exc}")
            raise ServiceUnavailableError("Cannot reach Redis to start processing; try again shortly") from exc
        log.info("processing queued", match_id=match.id, session_id=session.id)
        await publish_match_status(self._redis, match)
        return match

    async def _set_desired(self, match: Match, state: str, status: MatchStatus, message: str) -> Match:
        if match.current_session_id is None:
            raise ServiceUnavailableError("Match has no processing session")
        try:
            await self._redis.set(control_key(match.id), control_value(match.current_session_id, state))
        except RedisError as exc:
            raise ServiceUnavailableError(f"Cannot reach Redis to {state} processing; try again shortly") from exc
        match.status = status
        match.status_message = message
        await self._db.commit()
        await publish_match_status(self._redis, match)
        return match

    async def _close_current_session(self, match: Match, status: str) -> None:
        if not match.current_session_id:
            return
        session = await self._sessions.get(match.current_session_id)
        if session is not None and session.stopped_at is None:
            session.status = status
            session.stopped_at = datetime.now(UTC)

    async def _mark_failed(self, match: Match, session: ProcessingSession, error: str) -> None:
        match.status = MatchStatus.FAILED
        match.last_error = error
        match.status_message = None
        session.status = "failed"
        session.error = error
        session.stopped_at = datetime.now(UTC)
        await self._db.commit()
