from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from app.core.config import Settings
from app.core.errors import NotFoundError
from app.deps import get_app_settings

router = APIRouter(tags=["media"])


@router.get("/media/{path:path}")
async def media(path: str, settings: Annotated[Settings, Depends(get_app_settings)]) -> FileResponse:
    """Serves uploaded videos (with HTTP range support) to the dashboard player."""
    root = settings.media_dir.resolve()
    target = (root / path).resolve()
    if root not in target.parents or not target.is_file() or target.name.startswith("."):
        raise NotFoundError("Media file not found")
    return FileResponse(target)
