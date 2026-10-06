"""API keys for the integration feed: `psk_` + 40 random characters, stored as SHA-256."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ApiKey

KEY_PREFIX = "psk_"
PREFIX_SHOWN = 12  # "psk_" + 8 characters, enough to recognise a key in the list
HEADER = "X-API-Key"


def generate_key() -> str:
    return KEY_PREFIX + secrets.token_urlsafe(30)


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


async def find_active(db: AsyncSession, key: str | None) -> ApiKey | None:
    """The active key matching [key] (stamping its last use), or None."""
    if not key or not key.startswith(KEY_PREFIX):
        return None
    row = (await db.scalars(select(ApiKey).where(ApiKey.key_hash == hash_key(key)))).first()
    if row is None or row.revoked_at is not None:
        return None
    row.last_used_at = datetime.now(UTC)
    await db.commit()
    return row
