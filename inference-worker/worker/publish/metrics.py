"""Rolling processing metrics for one match session."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from worker.pipeline import FrameResult

_WINDOW_S = 5.0


@dataclass(slots=True)
class SessionMetrics:
    source_fps: float | None
    started_at: float = field(default_factory=time.monotonic)
    frames_processed: int = 0
    events_emitted: int = 0
    _latency_total_ms: float = 0.0
    _recent: deque[tuple[float, float, float, float]] = field(default_factory=deque)

    def record(self, result: FrameResult, published_at: float) -> None:
        now = time.monotonic()
        latency_ms = (published_at - result.frame.wall_ts) * 1000
        self.frames_processed += 1
        self.events_emitted += len(result.events)
        self._latency_total_ms += latency_ms
        self._recent.append((now, result.timings.detect_ms, result.timings.event_ms, latency_ms))
        while self._recent and now - self._recent[0][0] > _WINDOW_S:
            self._recent.popleft()

    @property
    def inference_fps(self) -> float:
        if len(self._recent) < 2:
            return 0.0
        span = self._recent[-1][0] - self._recent[0][0]
        return (len(self._recent) - 1) / span if span > 0 else 0.0

    @property
    def average_fps(self) -> float:
        elapsed = time.monotonic() - self.started_at
        return self.frames_processed / elapsed if elapsed > 0 else 0.0

    @property
    def average_latency_ms(self) -> float:
        return self._latency_total_ms / self.frames_processed if self.frames_processed else 0.0

    def snapshot(self, device: str, gpu: list[dict[str, Any]] | None) -> dict[str, Any]:
        recent = list(self._recent)
        n = len(recent) or 1
        return {
            "source_fps": self.source_fps,
            "inference_fps": round(self.inference_fps, 2),
            "detect_ms": round(sum(r[1] for r in recent) / n, 2),
            "event_ms": round(sum(r[2] for r in recent) / n, 2),
            "latency_ms": round(sum(r[3] for r in recent) / n, 1),
            "frames_processed": self.frames_processed,
            "events_emitted": self.events_emitted,
            "device": device,
            "gpu": gpu[0] if gpu else None,
        }

    def session_stats(self) -> dict[str, Any]:
        return {
            "frames_processed": self.frames_processed,
            "average_fps": round(self.average_fps, 2),
            "average_latency_ms": round(self.average_latency_ms, 1),
        }
