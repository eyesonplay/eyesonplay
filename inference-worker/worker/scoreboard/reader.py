"""Background OCR of the broadcast scoreboard.

About once per `interval_s` of video, a band of the frame where scoreboards
usually sit is read on a worker thread, so detection never waits for OCR.
The reader tries the usual positions (top-left first) until one shows a score
and then stays there. Each finished reading gets a new `read_id`; the event
engine confirms a goal only from repeated readings (see football_events.rules.goals).
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor

import numpy as np

from football_events.types import ScoreboardObservation
from worker.ingest.source import Frame
from worker.logging import get_logger
from worker.scoreboard.parser import Token, parse_reading

log = get_logger(component="scoreboard")

# (top, bottom, left, right) as fractions of the frame, most common first.
BANDS: tuple[tuple[float, float, float, float], ...] = (
    (0.0, 0.16, 0.0, 0.42),  # top-left
    (0.0, 0.16, 0.58, 1.0),  # top-right
    (0.84, 1.0, 0.0, 0.42),  # bottom-left
    (0.84, 1.0, 0.58, 1.0),  # bottom-right
)

Ocr = Callable[[np.ndarray, int], list[Token]]


class ScoreboardReader:
    def __init__(self, ocr: Ocr, interval_s: float = 1.0, search_reads: int = 8) -> None:
        self._ocr = ocr
        self._interval_s = interval_s
        self._search_reads = search_reads  # empty readings before trying the next band
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="scoreboard")
        self._pending: Future[list[Token]] | None = None
        self._band = 0
        self._found = False
        self._misses = 0
        self._last_submit = float("-inf")
        self._read_id = 0
        self._latest: ScoreboardObservation | None = None

    def observe(self, frame: Frame) -> None:
        self._collect()
        if frame.image is None or self._pending is not None:
            return
        if frame.video_ts - self._last_submit < self._interval_s:
            return
        self._last_submit = frame.video_ts
        self._pending = self._executor.submit(self._ocr, _crop(frame.image, BANDS[self._band]).copy(), self._band)

    def latest(self) -> ScoreboardObservation | None:
        self._collect()
        return self._latest

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _collect(self) -> None:
        if self._pending is None or not self._pending.done():
            return
        future, self._pending = self._pending, None
        try:
            tokens = future.result()
        except Exception:  # noqa: BLE001 - OCR trouble must not stop processing
            log.exception("scoreboard OCR failed")
            tokens = []
        reading = parse_reading(tokens)
        self._read_id += 1
        self._latest = ScoreboardObservation(self._read_id, reading.home, reading.away, reading.goal_banner)
        if reading.home is not None or reading.goal_banner:
            if not self._found:
                log.info("scoreboard found", band=self._band, home=reading.home, away=reading.away)
            self._found, self._misses = True, 0
        elif not self._found:
            self._misses += 1
            if self._misses >= self._search_reads:
                self._band, self._misses = (self._band + 1) % len(BANDS), 0


def _crop(image: np.ndarray, band: tuple[float, float, float, float]) -> np.ndarray:
    h, w = image.shape[:2]
    top, bottom, left, right = band
    return image[int(top * h) : int(bottom * h), int(left * w) : int(right * w)]


def load_scoreboard_reader() -> ScoreboardReader | None:
    """A reader backed by RapidOCR (Apache-2.0, ONNX, CPU), or None if it is not installed."""
    try:
        from rapidocr import RapidOCR
    except ImportError:
        log.warning("rapidocr not installed: goals cannot be confirmed from the scoreboard")
        return None
    engine = RapidOCR()

    def ocr(image: np.ndarray, band: int) -> list[Token]:
        result = engine(image)
        if not result.txts:
            return []
        return [
            Token(str(text), float(np.mean(np.asarray(box)[:, 0])), float(score))
            for box, text, score in zip(result.boxes, result.txts, result.scores, strict=False)
        ]

    log.info("scoreboard reader loaded", engine="rapidocr")
    return ScoreboardReader(ocr)
