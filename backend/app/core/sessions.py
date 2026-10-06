"""Login sessions: an opaque random token in an HttpOnly cookie, SHA-256 in the database."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import new_id
from app.db.models import User, UserSession

COOKIE_NAME = "eop_session"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def start_session(db: AsyncSession, user: User, ttl: timedelta) -> str:
    """A new session for the user; returns the token for the cookie."""
    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    db.add(UserSession(id=new_id("ses"), user_id=user.id, token_hash=_hash(token), expires_at=now + ttl))
    user.last_login_at = now
    # Housekeeping: expired sessions are useless; drop them here instead of a job.
    await db.execute(delete(UserSession).where(UserSession.expires_at < now))
    await db.commit()
    return token


async def user_for_token(db: AsyncSession, token: str | None) -> User | None:
    """The active user owning this session token, or None."""
    if not token:
        return None
    row = (
        await db.execute(
            select(UserSession, User).join(User, User.id == UserSession.user_id).where(UserSession.token_hash == _hash(token))
        )
    ).first()
    if row is None:
        return None
    session, user = row
    expires = session.expires_at if session.expires_at.tzinfo else session.expires_at.replace(tzinfo=UTC)
    if expires <= datetime.now(UTC) or user.disabled:
        return None
    return user


async def end_session(db: AsyncSession, token: str | None) -> None:
    if token:
        await db.execute(delete(UserSession).where(UserSession.token_hash == _hash(token)))
        await db.commit()
