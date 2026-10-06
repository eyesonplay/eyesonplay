from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AppSettings

SETTINGS_ROW_ID = 1


class SettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self) -> AppSettings:
        row = await self._s.get(AppSettings, SETTINGS_ROW_ID)
        if row is None:
            row = AppSettings(id=SETTINGS_ROW_ID)
            self._s.add(row)
            await self._s.flush()
        return row
