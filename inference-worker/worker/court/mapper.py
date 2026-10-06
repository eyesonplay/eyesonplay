"""Pixel -> normalised court coordinates for real tennis video.

The full court search runs on a background thread (it takes ~1-2 s); in
between, the cached calibration is re-checked cheaply on each due frame and
kept while it still fits (broadcast tennis cameras are mostly static). A cut
to a close-up or crowd shot fails the check: coordinates become unavailable
rather than wrong. The wide camera comes back to the same framing, so while
the court is lost the last good fit is re-checked on every frame and restored
as soon as it fits again, without waiting for a full search.
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

import numpy as np

from football_events import Point
from worker.court.detector import CourtFit, LineMask, detect_court, score
from worker.ingest.source import Frame
from worker.logging import get_logger
from worker.pitch.homography import apply_homography

log = get_logger(component="court_mapper")

CHECK_INTERVAL_S = 0.5
RESTORE_INTERVAL_S = 0.04  # while lost: re-check the last good fit (about every frame)
SEARCH_INTERVAL_S = 1.0
KEEP_SCORE = 0.65  # a cached fit is kept while it still scores this well
PLAUSIBLE = (-150.0, 250.0)  # airborne balls project far off court; still useful for direction


class TennisCourtMapper:
    def __init__(self) -> None:
        self._fit: CourtFit | None = None
        self._last_good: CourtFit | None = None
        self._pixel_to_court: np.ndarray | None = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="court-search")
        self._search: Future[CourtFit | None] | None = None
        self._last_check = -1e9
        self._last_search = -1e9
        self._state = "searching"
        self._last_score: float | None = None

    @property
    def calibrated(self) -> bool:
        return self._pixel_to_court is not None

    def calibration(self) -> dict[str, Any]:
        return {
            "state": "ok" if self.calibrated else self._state,
            "score": None if self._last_score is None else round(self._last_score, 2),
            "pitch_in_view": self.calibrated or self._state != "no_court",
        }

    def observe(self, frame: Frame) -> None:
        if frame.image is None:
            return
        self._collect_search()
        t = frame.video_ts
        if self._fit is not None and t - self._last_check >= CHECK_INTERVAL_S:
            self._last_check = t
            lines = LineMask(frame.image)
            current = score(lines.to_analysis(self._fit.court_to_pixel), lines)
            self._last_score = current
            if current < KEEP_SCORE:
                self._set(None)  # camera moved or cut: find the court again
                self._state = "searching"
        if self._fit is None and self._last_good is not None and t - self._last_check >= RESTORE_INTERVAL_S:
            self._try_restore(frame.image, t)
        if self._fit is None and self._search is None and t - self._last_search >= SEARCH_INTERVAL_S:
            self._last_search = t
            self._search = self._executor.submit(detect_court, frame.image.copy())

    def _try_restore(self, image: np.ndarray, t: float) -> None:
        assert self._last_good is not None
        self._last_check = t
        lines = LineMask(image)
        current = score(lines.to_analysis(self._last_good.court_to_pixel), lines)
        if current >= KEEP_SCORE:
            self._set(self._last_good)
            self._last_score = current

    def _collect_search(self) -> None:
        if self._search is None or not self._search.done():
            return
        future, self._search = self._search, None
        try:
            fit = future.result()
        except Exception:  # noqa: BLE001 - a failed search must not stop processing
            log.exception("court search failed")
            fit = None
        if fit is None:
            self._state = "no_court"
            return
        self._set(fit)
        self._last_score = fit.score
        log.info("court calibrated", score=round(fit.score, 2))

    def _set(self, fit: CourtFit | None) -> None:
        self._fit = fit
        if fit is not None:
            self._last_good = fit
        self._pixel_to_court = np.linalg.inv(fit.court_to_pixel) if fit is not None else None

    def to_pitch(self, x: float, y: float) -> Point | None:
        if self._pixel_to_court is None:
            return None
        result = apply_homography(self._pixel_to_court, x, y)
        if result is None:
            return None
        low, high = PLAUSIBLE
        if not (low <= result[0] <= high and low <= result[1] <= high):
            return None
        return Point(result[0], result[1])

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
