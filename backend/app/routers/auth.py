"""Dashboard login: POST /api/auth/login, POST /api/auth/logout, GET /api/auth/me."""

from __future__ import annotations

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core import rate_limit
from app.core.config import Settings
from app.core.errors import TooManyRequestsError, UnauthorizedError
from app.core.logging import get_logger
from app.core.passwords import burn_verification, verify_password
from app.core.sessions import COOKIE_NAME, end_session, start_session
from app.core.users import find_user, normalise_email
from app.db.models import User
from app.deps import check_origin, get_app_settings, get_db, get_redis, require_user
from app.schemas.auth import LoginIn, UserOut
from app.schemas.common import Envelope, ok

router = APIRouter(prefix="/api/auth", tags=["auth"])
log = get_logger(component="auth")

Db = Annotated[AsyncSession, Depends(get_db)]
RedisDep = Annotated[Redis, Depends(get_redis)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]
WRONG_CREDENTIALS = "Wrong email or password"


@router.post("/login", response_model=Envelope[UserOut])
async def login(body: LoginIn, request: Request, response: Response, db: Db, redis: RedisDep, settings: SettingsDep) -> Envelope[UserOut]:
    check_origin(request)
    email = normalise_email(body.email)
    ip_key = f"login:ip:{request.client.host if request.client else 'unknown'}"
    email_key = f"login:email:{email}"
    # Count the attempt before checking the password (atomic INCR), so parallel
    # guesses cannot all slip past the limit; a successful sign-in resets it.
    for key, limit in ((ip_key, settings.login_max_attempts_per_ip), (email_key, settings.login_max_failures)):
        if await rate_limit.hit(redis, key, settings.login_window_s) > limit:
            wait = await rate_limit.retry_after(redis, key)
            raise TooManyRequestsError("Too many sign-in attempts. Try again later.", headers={"Retry-After": str(wait)})

    user = await find_user(db, email)
    async with request.app.state.password_checks:
        if user is None or user.disabled:
            await run_in_threadpool(burn_verification, body.password)
            valid = False
        else:
            valid = await run_in_threadpool(verify_password, user.password_hash, body.password)
    if not valid or user is None:
        # Only name real accounts in logs: people type passwords into the email field.
        log.info("login failed", email=email if user is not None else "<unknown account>")
        raise UnauthorizedError(WRONG_CREDENTIALS)

    await rate_limit.reset(redis, email_key)
    ttl = timedelta(hours=settings.session_ttl_hours)
    token = await start_session(db, user, ttl)
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=int(ttl.total_seconds()),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    log.info("login", email=email)
    return ok(UserOut(email=user.email))


@router.post("/logout", response_model=Envelope[None])
async def logout(request: Request, response: Response, db: Db) -> Envelope[None]:
    check_origin(request)
    await end_session(db, request.cookies.get(COOKIE_NAME))
    response.delete_cookie(COOKIE_NAME, path="/")
    return ok(None)


@router.get("/me", response_model=Envelope[UserOut])
async def me(user: Annotated[User, Depends(require_user)]) -> Envelope[UserOut]:
    return ok(UserOut(email=user.email))
