"""Integration feed for other apps (e.g. RioSport), API key required.

`GET /api/v1/feed/matches` lists matches to link (by `external_ref`, or teams + date);
`/ws/v1/feed/matches/{id}` is the same live feed as the dashboard's WebSocket. The key
goes in the `X-API-Key` header (or `?api_key=` where a client can't set headers).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, WebSocket
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from redis.asyncio import Redis

from app.core import rate_limit
from app.core.api_keys import find_active
from app.core.config import Settings
from app.core.errors import TooManyRequestsError, UnauthorizedError
from app.db.models import ApiKey, Match, MatchStatus
from app.deps import get_app_settings, get_db, get_redis
from app.routers.ws import serve_feed
from app.schemas.api_key import FeedMatchOut
from app.schemas.common import Envelope, ok

router = APIRouter(tags=["integration feed"])

CLOSE_UNAUTHORIZED = 4401
Db = Annotated[AsyncSession, Depends(get_db)]


FEED_WINDOW_S = 60


async def require_key(
    db: Db,
    redis: Annotated[Redis, Depends(get_redis)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    x_api_key: Annotated[str | None, Header()] = None,
    api_key: Annotated[str | None, Query()] = None,
) -> ApiKey:
    row = await find_active(db, x_api_key or api_key)
    if row is None:
        raise UnauthorizedError("A valid API key is required (X-API-Key header)")
    window_key = f"feed:{row.id}"
    if await rate_limit.hit(redis, window_key, FEED_WINDOW_S) > settings.feed_requests_per_minute:
        wait = await rate_limit.retry_after(redis, window_key)
        raise TooManyRequestsError("Rate limit exceeded for this API key", headers={"Retry-After": str(wait)})
    return row


@router.get("/api/v1/feed/matches", response_model=Envelope[list[FeedMatchOut]])
async def feed_matches(
    db: Db,
    _: Annotated[ApiKey, Depends(require_key)],
    status_filter: Annotated[list[MatchStatus] | None, Query(alias="status")] = None,
    external_ref: Annotated[str | None, Query(max_length=80)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> Envelope[list[FeedMatchOut]]:
    query = select(Match)
    if status_filter:
        query = query.where(Match.status.in_(status_filter))
    if external_ref:
        query = query.where(Match.external_ref == external_ref)
    rows = await db.scalars(query.order_by(Match.match_date.desc()).limit(limit))
    return ok([FeedMatchOut.model_validate(m) for m in rows])


@router.websocket("/ws/v1/feed/matches/{match_id}")
async def feed_socket(websocket: WebSocket, match_id: str) -> None:
    await websocket.accept()
    key = websocket.headers.get("x-api-key") or websocket.query_params.get("api_key")
    async with websocket.app.state.session_factory() as db:
        allowed = await find_active(db, key)
    if allowed is None:
        await websocket.close(code=CLOSE_UNAUTHORIZED, reason="valid API key required")
        return
    await serve_feed(websocket, match_id)
