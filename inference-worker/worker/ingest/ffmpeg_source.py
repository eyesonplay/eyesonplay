"""FFmpegSource: continuous frame extraction from HLS / RTMP / URL / files.

FFmpeg decodes the stream and samples it to the processing fps (`-vf fps=N`),
writing raw BGR frames to a pipe. Nothing is downloaded up front. When the
source drops, FFmpeg is restarted with exponential backoff; file sources
resume from the last processed timestamp.
"""

from __future__ import annotations

import json
import os
import select
import subprocess
import time
from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np

from worker.config import WorkerSettings
import tempfile

from worker.ingest.source import Frame, ReconnectCallback, SourceError
from worker.ingest.source_guard import ensure_public_host, protocol_whitelist
from worker.logging import get_logger

log = get_logger(component="ffmpeg_source")

_STDERR_TAIL = 2000


@dataclass(frozen=True, slots=True)
class ProbeResult:
    width: int
    height: int
    fps: float | None


def probe(url: str, timeout_s: float, is_file: bool = False) -> ProbeResult:
    cmd = [
        "ffprobe", "-v", "error", "-protocol_whitelist", protocol_whitelist(is_file), "-select_streams", "v:0",
        "-show_entries", "stream=width,height,avg_frame_rate,r_frame_rate",
        "-of", "json", url,
    ]  # fmt: skip
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=timeout_s, check=False, text=True)
    except subprocess.TimeoutExpired as exc:
        raise SourceError(f"timed out probing source after {timeout_s:.0f}s") from exc
    except FileNotFoundError as exc:
        raise SourceError("ffprobe is not installed in the worker image") from exc
    if out.returncode != 0:
        raise SourceError(f"cannot open video source: {out.stderr.strip()[-400:] or 'unknown error'}")
    streams = json.loads(out.stdout or "{}").get("streams") or []
    if not streams or not streams[0].get("width"):
        raise SourceError("source has no decodable video stream")
    s = streams[0]
    return ProbeResult(int(s["width"]), int(s["height"]), _parse_rate(s.get("avg_frame_rate") or s.get("r_frame_rate")))


def _parse_rate(rate: str | None) -> float | None:
    if not rate or rate in ("0/0", "0"):
        return None
    num, _, den = rate.partition("/")
    try:
        value = float(num) / float(den or 1)
    except (ValueError, ZeroDivisionError):
        return None
    return round(value, 3) if value > 0 else None


class FFmpegSource:
    def __init__(
        self,
        url: str,
        fps: float,
        is_live: bool,
        settings: WorkerSettings,
        on_reconnect: ReconnectCallback | None = None,
    ) -> None:
        self._url = url
        self._fps = fps
        self.is_live = is_live
        self._settings = settings
        self._on_reconnect = on_reconnect
        self._proc: subprocess.Popen[bytes] | None = None
        self._stderr: tempfile.TemporaryFile | None = None  # type: ignore[valid-type]
        self._closed = False
        self._is_file = not url.startswith(("http://", "https://", "rtmp://", "rtmps://"))
        if not self._is_file and not settings.allow_private_sources:
            ensure_public_host(url)
        info = self._probe_with_retry()
        self.width, self.height, self.source_fps = info.width, info.height, info.fps

    def _probe_with_retry(self) -> ProbeResult:
        attempt = 0
        while True:
            try:
                return probe(self._url, self._settings.source_read_timeout_s, self._is_file)
            except SourceError as exc:
                attempt += 1
                if not self.is_live or attempt > self._settings.source_reconnect_attempts:
                    raise
                self._backoff(attempt, str(exc))

    def _command(self, start_ts: float) -> list[str]:
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-protocol_whitelist", protocol_whitelist(self._is_file)]
        if self._url.startswith(("http://", "https://")):
            cmd += ["-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "5"]
        if not self.is_live:
            cmd += ["-re"]  # play files at native speed so the dashboard stays in sync
            if start_ts > 0:
                cmd += ["-ss", f"{start_ts:.3f}"]
        cmd += ["-i", self._url, "-an", "-vf", f"fps={self._fps}", "-f", "rawvideo", "-pix_fmt", "bgr24", "pipe:1"]
        return cmd

    def __iter__(self) -> Iterator[Frame]:
        frame_size = self.width * self.height * 3
        frame_number, attempt, resume_ts = 0, 0, 0.0
        while not self._closed:
            # stderr goes to a temp file: an undrained pipe could fill up and block ffmpeg.
            self._stderr = tempfile.TemporaryFile()
            self._proc = subprocess.Popen(self._command(resume_ts), stdout=subprocess.PIPE, stderr=self._stderr)
            segment_start, local_index = resume_ts, 0
            try:
                while not self._closed:
                    raw = self._read_frame(frame_size)
                    if raw is None:
                        break
                    attempt = 0
                    video_ts = segment_start + local_index / self._fps
                    image = np.frombuffer(raw, dtype=np.uint8).reshape(self.height, self.width, 3)
                    yield Frame(frame_number, video_ts, time.time(), self.width, self.height, image)
                    frame_number += 1
                    local_index += 1
                    resume_ts = video_ts + 1 / self._fps
            except TimeoutError:
                log.warning("source stalled", url=self._safe_url, timeout_s=self._settings.source_read_timeout_s)
            finally:
                error = self._stop_process()
            if self._closed:
                return
            if not self.is_live and error is None:
                return  # end of file
            attempt += 1
            if attempt > self._settings.source_reconnect_attempts:
                raise SourceError(f"video source disconnected: {error or 'stream stalled'}")
            self._backoff(attempt, error or "stream stalled")

    def _read_frame(self, size: int) -> bytes | None:
        assert self._proc is not None and self._proc.stdout is not None
        fd = self._proc.stdout.fileno()
        chunks, remaining = [], size
        while remaining > 0:
            ready, _, _ = select.select([fd], [], [], self._settings.source_read_timeout_s)
            if not ready:
                raise TimeoutError
            chunk = os.read(fd, min(remaining, 1 << 20))
            if not chunk:
                return None
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _stop_process(self) -> str | None:
        """Terminate ffmpeg; return an error description if it failed."""
        proc, self._proc = self._proc, None
        if proc is None:
            return None
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        if proc.stdout is not None:
            proc.stdout.close()
        stderr = ""
        if self._stderr is not None:
            self._stderr.seek(0)
            stderr = self._stderr.read().decode(errors="replace")[-_STDERR_TAIL:]
            self._stderr.close()
            self._stderr = None
        if self._closed or proc.returncode == 0:
            return None
        return stderr.strip() or f"ffmpeg exited with code {proc.returncode}"

    def _backoff(self, attempt: int, reason: str) -> None:
        delay = min(30.0, self._settings.source_reconnect_base_delay_s * 2 ** (attempt - 1))
        log.warning("reconnecting to source", attempt=attempt, delay_s=delay, reason=reason[-300:])
        if self._on_reconnect is not None:
            self._on_reconnect(attempt, reason[-300:])
        time.sleep(delay)

    @property
    def _safe_url(self) -> str:
        return self._url.split("?", 1)[0]

    def close(self) -> None:
        self._closed = True
        self._stop_process()
