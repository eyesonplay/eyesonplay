"""Admin: create, list and revoke integration API keys (dashboard side, like the rest of /api)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api_keys import PREFIX_SHOWN, generate_key, hash_key
from app.core.errors import NotFoundError
from app.core.ids import new_id
from app.core.logging import get_logger
from app.db.models import ApiKey
from app.deps import get_db
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyOut
from app.schemas.common import Envelope, ok

router = APIRouter(prefix="/api/api-keys", tags=["api keys"])
log = get_logger(component="api_keys")

Db = Annotated[AsyncSession, Depends(get_db)]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=Envelope[ApiKeyCreated])
async def create_key(body: ApiKeyCreate, db: Db) -> Envelope[ApiKeyCreated]:
    key = generate_key()
    row = ApiKey(id=new_id("key"), name=body.name, prefix=key[:PREFIX_SHOWN], key_hash=hash_key(key))
    db.add(row)
    await db.commit()
    await db.refresh(row)
    log.info("api key created", key_id=row.id, name=row.name)
    return ok(ApiKeyCreated(**ApiKeyOut.model_validate(row).model_dump(), key=key))


@router.get("", response_model=Envelope[list[ApiKeyOut]])
async def list_keys(db: Db) -> Envelope[list[ApiKeyOut]]:
    rows = await db.scalars(select(ApiKey).order_by(ApiKey.created_at.desc()))
    return ok([ApiKeyOut.model_validate(r) for r in rows])


@router.delete("/{key_id}", response_model=Envelope[ApiKeyOut])
async def revoke_key(key_id: str, db: Db) -> Envelope[ApiKeyOut]:
    row = await db.get(ApiKey, key_id)
    if row is None:
        raise NotFoundError(f"API key {key_id} not found")
    row.revoked_at = row.revoked_at or datetime.now(UTC)
    await db.commit()
    await db.refresh(row)
    log.info("api key revoked", key_id=row.id)
    return ok(ApiKeyOut.model_validate(row))
