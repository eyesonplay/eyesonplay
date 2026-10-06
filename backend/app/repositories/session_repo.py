from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ProcessingSession


class SessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, session_id: str) -> ProcessingSession | None:
        return await self._s.get(ProcessingSession, session_id)

    def add(self, processing_session: ProcessingSession) -> None:
        self._s.add(processing_session)

    async def for_match(self, match_id: str, limit: int = 20) -> list[ProcessingSession]:
        query = (
            select(ProcessingSession)
            .where(ProcessingSession.match_id == match_id)
            .order_by(ProcessingSession.started_at.desc())
            .limit(limit)
        )
        return list(await self._s.scalars(query))
