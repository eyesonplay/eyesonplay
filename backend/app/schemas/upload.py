from __future__ import annotations

from pydantic import BaseModel


class UploadOut(BaseModel):
    video_source: str
    original_filename: str
    size_bytes: int
    duration_s: float | None
    width: int | None
    height: int | None
