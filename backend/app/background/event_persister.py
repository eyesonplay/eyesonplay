"""Persists worker events from the Redis stream into Postgres (idempotent)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.background.stream_consumer import Message, parse_envelope
from app.core.logging import get_logger
from app.repositories.event_repo import EventRepository

log = get_logger(component="event_persister")


def to_row(env: dict[str, Any]) -> dict[str, Any] | None:
    data = env["data"]
    try:
        return {
            "event_uid": str(data["event_id"]),
            "match_id": str(env["match_id"]),
            "session_id": env.get("session_id"),
            "event_type": str(data["event"]),
            "video_timestamp": float(data["video_timestamp"]),
            "match_clock": str(data["match_clock"]),
            "confidence": float(data["confidence"]),
            "payload": data,
            "created_at": datetime.now(UTC),
        }
    except (KeyError, TypeError, ValueError):
        return None


def event_handler(factory: async_sessionmaker[AsyncSession]):  # noqa: ANN201
    async def handle(messages: list[Message]) -> None:
        rows = []
        for _, fields in messages:
            env = parse_envelope(fields)
            row = to_row(env) if env else None
            if row is None:
                log.warning("malformed event skipped")
                continue
            rows.append(row)
        if not rows:
            return
        async with factory() as db:
            repo = EventRepository(db)
            current = await repo.current_sessions(r["match_id"] for r in rows)
            # Events of deleted matches, or of sessions superseded by a restart
            # (whose events were cleared), are not persisted.
            kept = [r for r in rows if r["match_id"] in current and r["session_id"] == current[r["match_id"]]]
            if len(kept) != len(rows):
                log.info("stale events dropped", dropped=len(rows) - len(kept))
            await repo.insert_many(kept)
            await repo.refresh_counts(r["match_id"] for r in kept)
            await db.commit()

    return handle
