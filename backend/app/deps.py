"""FastAPI dependencies."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.sessions import COOKIE_NAME, user_for_token
from app.db.models import User

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.session_factory() as session:
        yield session


def get_redis(request: Request) -> Redis:
    return request.app.state.redis


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def origin_allowed(origin: str | None, host: str | None, settings: Settings) -> bool:
    """Browsers send Origin on cross-site and on state-changing requests. Allow the
    configured dashboard origins and the API's own host (same-origin deployments
    behind a reverse proxy). No Origin header means a non-browser client."""
    if not origin:
        return True
    if origin in settings.cors_origins:
        return True
    return host is not None and urlsplit(origin).netloc == host


def check_origin(request: Request) -> None:
    settings: Settings = request.app.state.settings
    if request.method not in SAFE_METHODS and not origin_allowed(
        request.headers.get("origin"), request.headers.get("host"), settings
    ):
        raise ForbiddenError("Cross-site request refused")


async def require_user(request: Request, db: Annotated[AsyncSession, Depends(get_db)]) -> User:
    """The signed-in dashboard user; guards every dashboard route."""
    check_origin(request)
    user = await user_for_token(db, request.cookies.get(COOKIE_NAME))
    if user is None:
        raise UnauthorizedError("Sign in to continue")
    return user
