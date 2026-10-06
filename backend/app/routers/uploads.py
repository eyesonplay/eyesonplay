from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, UploadFile, status

from app.core.config import Settings
from app.deps import get_app_settings
from app.schemas.common import Envelope, ok
from app.schemas.upload import UploadOut
from app.services.upload_service import PayloadTooLargeError, save_upload

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=Envelope[UploadOut])
async def upload_video(
    request: Request,
    file: Annotated[UploadFile, File(description="MP4/MOV/MKV/WebM video")],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> Envelope[UploadOut]:
    max_bytes = settings.max_upload_mb * (1 << 20)
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > max_bytes + (1 << 20):
        raise PayloadTooLargeError(f"File exceeds the {settings.max_upload_mb} MB upload limit")
    result = await save_upload(file, settings.media_dir, max_bytes)
    return ok(result)
