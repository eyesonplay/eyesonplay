"""Dashboard users: creation, lookup and the startup admin."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import new_id
from app.core.logging import get_logger
from app.core.passwords import MIN_PASSWORD_LENGTH, hash_password, verify_password
from app.db.models import User, UserSession

log = get_logger(component="users")

# The local development account in docker-compose.yml. Never valid in production.
DEV_ADMIN_EMAIL = "admin@example.com"
DEV_ADMIN_PASSWORD = "eyesonplay-admin"


def normalise_email(email: str) -> str:
    return email.strip().lower()


async def find_user(db: AsyncSession, email: str) -> User | None:
    return (await db.scalars(select(User).where(User.email == normalise_email(email)))).first()


async def create_user(db: AsyncSession, email: str, password: str) -> User:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Passwords need at least {MIN_PASSWORD_LENGTH} characters")
    address = normalise_email(email)
    if "@" not in address:
        raise ValueError("Not an email address")
    if await find_user(db, address) is not None:
        raise ValueError(f"A user with email {address} already exists")
    user = User(id=new_id("usr"), email=address, password_hash=hash_password(password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def set_password(db: AsyncSession, user: User, password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Passwords need at least {MIN_PASSWORD_LENGTH} characters")
    user.password_hash = hash_password(password)
    # A new password (e.g. after a compromise) signs the user out everywhere.
    await db.execute(delete(UserSession).where(UserSession.user_id == user.id))
    await db.commit()


async def bootstrap_admin(db: AsyncSession, email: str | None, password: str | None) -> None:
    """Create the configured admin if missing; never touch an existing user."""
    if not email or not password:
        return
    if await find_user(db, email) is not None:
        return
    await create_user(db, email, password)
    log.info("admin user created", email=normalise_email(email))


async def refuse_dev_admin(db: AsyncSession, configured_password: str | None) -> None:
    """Production must not run with the development account's known password,
    whether configured now or left over in a database that started in dev."""
    if configured_password == DEV_ADMIN_PASSWORD:
        raise RuntimeError("ADMIN_PASSWORD is the development admin password; set your own")
    leftover = await find_user(db, DEV_ADMIN_EMAIL)
    if leftover is not None and not leftover.disabled and verify_password(leftover.password_hash, DEV_ADMIN_PASSWORD):
        raise RuntimeError(
            f"The development admin {DEV_ADMIN_EMAIL} still has its default password; "
            "change it (python -m app.cli set-password) or disable it before running in production"
        )
