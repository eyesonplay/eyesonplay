from __future__ import annotations

from collections.abc import AsyncIterator, Iterable, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Event, Match

EXPORT_CHUNK = 1000


class EventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def insert_many(self, rows: Sequence[dict[str, Any]]) -> None:
        """Idempotent bulk insert: duplicates (same match_id + event_uid) are skipped."""
        if not rows:
            return
        insert = sqlite_insert if self._s.bind.dialect.name == "sqlite" else pg_insert
        stmt = insert(Event).values(list(rows)).on_conflict_do_nothing(index_elements=["match_id", "event_uid"])
        await self._s.execute(stmt)

    async def refresh_counts(self, match_ids: Iterable[str]) -> None:
        for match_id in set(match_ids):
            count = select(func.count()).where(Event.match_id == match_id).scalar_subquery()
            await self._s.execute(update(Match).where(Match.id == match_id).values(event_count=count))

    async def list(
        self,
        match_id: str | None,
        types: Sequence[str] | None,
        limit: int,
        before_id: int | None = None,
    ) -> list[Event]:
        query = select(Event)
        if match_id:
            query = query.where(Event.match_id == match_id)
        if types:
            query = query.where(Event.event_type.in_(types))
        if before_id:
            query = query.where(Event.id < before_id)
        return list(await self._s.scalars(query.order_by(Event.id.desc()).limit(limit)))

    async def stream_payloads(self, match_id: str) -> AsyncIterator[dict[str, Any]]:
        last_id = 0
        while True:
            rows = list(
                await self._s.scalars(
                    select(Event)
                    .where(Event.match_id == match_id, Event.id > last_id)
                    .order_by(Event.id)
                    .limit(EXPORT_CHUNK)
                )
            )
            if not rows:
                return
            for row in rows:
                yield row.payload
            last_id = rows[-1].id

    async def count_since(self, since: datetime) -> int:
        return await self._s.scalar(select(func.count()).where(Event.created_at >= since)) or 0

    async def delete_for_match(self, match_id: str) -> None:
        await self._s.execute(delete(Event).where(Event.match_id == match_id))

    async def current_sessions(self, match_ids: Iterable[str]) -> dict[str, str | None]:
        """match id -> current session id, for matches that still exist."""
        ids = set(match_ids)
        if not ids:
            return {}
        rows = await self._s.execute(select(Match.id, Match.current_session_id).where(Match.id.in_(ids)))
        return {match_id: session_id for match_id, session_id in rows}
