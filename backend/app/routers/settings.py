from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.repositories.settings_repo import SettingsRepository
from app.schemas.common import Envelope, ok
from app.schemas.settings import AppSettingsIn, AppSettingsOut

router = APIRouter(prefix="/api/settings", tags=["settings"])
Db = Annotated[AsyncSession, Depends(get_db)]


@router.get("", response_model=Envelope[AppSettingsOut])
async def get_settings(db: Db) -> Envelope[AppSettingsOut]:
    row = await SettingsRepository(db).get()
    await db.commit()
    return ok(AppSettingsOut.model_validate(row))


@router.put("", response_model=Envelope[AppSettingsOut])
async def put_settings(body: AppSettingsIn, db: Db) -> Envelope[AppSettingsOut]:
    row = await SettingsRepository(db).get()
    for field, value in body.model_dump().items():
        setattr(row, field, value)
    await db.commit()
    await db.refresh(row)
    return ok(AppSettingsOut.model_validate(row))
