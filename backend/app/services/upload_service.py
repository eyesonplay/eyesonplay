"""Uploaded video storage with size limits and ffprobe validation."""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

from fastapi import UploadFile

from app.core.errors import AppError, UnprocessableError
from app.core.ids import ulid
from app.core.logging import get_logger
from app.schemas.upload import UploadOut

log = get_logger(component="uploads")

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}
CHUNK_BYTES = 1 << 20
PROBE_TIMEOUT_S = 30


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "payload_too_large"


async def save_upload(file: UploadFile, media_dir: Path, max_bytes: int) -> UploadOut:
    original = Path(file.filename or "video").name
    ext = Path(original).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise UnprocessableError(f"Unsupported file type '{ext or 'none'}'. Use {', '.join(sorted(ALLOWED_EXTENSIONS))}")

    uploads = media_dir / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    name = f"{ulid()}{ext}"
    final = uploads / name
    partial = uploads / f".{name}.part"
    size = 0
    try:
        with partial.open("wb") as out:
            while chunk := await file.read(CHUNK_BYTES):
                size += len(chunk)
                if size > max_bytes:
                    raise PayloadTooLargeError(f"File exceeds the {max_bytes // (1 << 20)} MB upload limit")
                await asyncio.to_thread(out.write, chunk)
        if size == 0:
            raise UnprocessableError("Uploaded file is empty")
        info = await probe_video(partial)
        partial.rename(final)
    finally:
        partial.unlink(missing_ok=True)

    log.info("upload stored", file=name, size_bytes=size)
    return UploadOut(
        video_source=f"uploads/{name}",
        original_filename=original,
        size_bytes=size,
        duration_s=info.get("duration"),
        width=info.get("width"),
        height=info.get("height"),
    )


async def probe_video(path: Path) -> dict[str, float | int | None]:
    if shutil.which("ffprobe") is None:
        log.warning("ffprobe not installed; skipping upload validation")
        return {}
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-protocol_whitelist", "file", "-select_streams", "v:0",
        "-show_entries", "stream=width,height:format=duration", "-of", "json", str(path),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )  # fmt: skip
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), PROBE_TIMEOUT_S)
    except TimeoutError as exc:
        proc.kill()
        await proc.wait()
        raise UnprocessableError("Timed out validating the uploaded video") from exc
    data = json.loads(stdout or b"{}")
    streams = data.get("streams") or []
    if proc.returncode != 0 or not streams:
        reason = stderr.decode(errors="replace").strip()[-300:] or "no video stream found"
        raise UnprocessableError("Uploaded file is not a readable video", details=reason)
    duration = data.get("format", {}).get("duration")
    return {
        "width": streams[0].get("width"),
        "height": streams[0].get("height"),
        "duration": round(float(duration), 2) if duration else None,
    }
