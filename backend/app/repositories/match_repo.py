from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.db.models import Match, MatchStatus


class MatchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, match_id: str) -> Match | None:
        return await self._s.get(Match, match_id)

    async def get_or_404(self, match_id: str, *, for_update: bool = False) -> Match:
        match = await self.get_for_update(match_id) if for_update else await self.get(match_id)
        if match is None:
            raise NotFoundError(f"Match {match_id} not found")
        return match

    async def get_for_update(self, match_id: str) -> Match | None:
        """Row-locks the match (Postgres) so concurrent actions are serialized."""
        query = select(Match).where(Match.id == match_id).with_for_update().execution_options(populate_existing=True)
        return (await self._s.scalars(query)).first()

    async def list(
        self,
        statuses: Sequence[MatchStatus] | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Match], int]:
        query = select(Match)
        if statuses:
            query = query.where(Match.status.in_(statuses))
        if search:
            like = f"%{search.lower()}%"
            query = query.where(
                or_(
                    func.lower(Match.name).like(like),
                    func.lower(Match.home_team).like(like),
                    func.lower(Match.away_team).like(like),
                    func.lower(Match.competition).like(like),
                )
            )
        total = await self._s.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = await self._s.scalars(query.order_by(Match.updated_at.desc()).limit(limit).offset(offset))
        return list(rows), total

    async def with_statuses(self, statuses: Sequence[MatchStatus]) -> list[Match]:
        return list(await self._s.scalars(select(Match).where(Match.status.in_(statuses))))

    async def count_with_statuses(self, statuses: Sequence[MatchStatus]) -> int:
        return await self._s.scalar(select(func.count()).where(Match.status.in_(statuses))) or 0

    async def count_using_source(self, source: str) -> int:
        return await self._s.scalar(select(func.count()).where(Match.video_source == source)) or 0

    def add(self, match: Match) -> None:
        self._s.add(match)

    async def delete(self, match: Match) -> None:
        await self._s.delete(match)
