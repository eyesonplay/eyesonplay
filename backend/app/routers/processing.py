from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_redis
from app.routers.matches import to_out
from app.schemas.common import Envelope, ok
from app.schemas.match import MatchOut
from app.services.processing_service import ProcessingService

router = APIRouter(prefix="/api/matches", tags=["processing"])

Db = Annotated[AsyncSession, Depends(get_db)]
RedisDep = Annotated[Redis, Depends(get_redis)]


@router.post("/{match_id}/start", response_model=Envelope[MatchOut])
async def start(match_id: str, db: Db, redis: RedisDep) -> Envelope[MatchOut]:
    """Start processing, or resume it when the match is paused."""
    match = await ProcessingService(db, redis).start(match_id)
    return ok((await to_out(redis, [match]))[0])


@router.post("/{match_id}/pause", response_model=Envelope[MatchOut])
async def pause(match_id: str, db: Db, redis: RedisDep) -> Envelope[MatchOut]:
    match = await ProcessingService(db, redis).pause(match_id)
    return ok((await to_out(redis, [match]))[0])


@router.post("/{match_id}/stop", response_model=Envelope[MatchOut])
async def stop(match_id: str, db: Db, redis: RedisDep) -> Envelope[MatchOut]:
    match = await ProcessingService(db, redis).stop(match_id)
    return ok((await to_out(redis, [match]))[0])


@router.post("/{match_id}/restart", response_model=Envelope[MatchOut])
async def restart(match_id: str, db: Db, redis: RedisDep) -> Envelope[MatchOut]:
    """Start a fresh session from the beginning of the source; clears previous events."""
    match = await ProcessingService(db, redis).restart(match_id)
    return ok((await to_out(redis, [match]))[0])
