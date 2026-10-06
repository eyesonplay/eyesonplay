"""Single-ball tracker: Kalman smoothing, gating, duplicate suppression,
coasting through short dropouts and re-acquisition after camera cuts."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np

from worker.detect.base import Detection
from worker.track.kalman import ConstantVelocityKalman

HISTORY_LENGTH = 30


@dataclass(frozen=True, slots=True)
class BallState:
    timestamp: float
    frame_number: int
    pixel_x: float
    pixel_y: float
    confidence: float
    velocity_x: float
    velocity_y: float
    speed: float
    track_id: int
    predicted: bool
    size: float  # last observed bbox side, for drawing


@dataclass(frozen=True, slots=True)
class TrailPoint:
    t: float
    x: float
    y: float


class BallTracker:
    def __init__(
        self,
        max_coast_frames: int = 6,
        base_gate_px: float = 60.0,
        reacquire_confidence: float = 0.75,
        reacquire_frames: int = 2,
        process_noise: float = 400.0,
    ) -> None:
        self._process_noise = process_noise
        self._kf: ConstantVelocityKalman | None = None
        self._track_id = 0
        self._misses = 0
        self._last_t = 0.0
        self._last_conf = 0.0
        self._size = 10.0
        self._far_hits = 0
        self._max_coast = max_coast_frames
        self._base_gate = base_gate_px
        self._reacquire_conf = reacquire_confidence
        self._reacquire_frames = reacquire_frames
        self._history: deque[TrailPoint] = deque(maxlen=HISTORY_LENGTH)

    @property
    def history(self) -> list[TrailPoint]:
        return list(self._history)

    def update(self, detections: list[Detection], frame_number: int, t: float) -> BallState | None:
        balls = sorted((d for d in detections if d.cls == "ball"), key=lambda d: d.confidence, reverse=True)
        if self._kf is None:
            if not balls:
                return None
            return self._start(balls[0], frame_number, t)

        dt = max(t - self._last_t, 1e-3)
        pred = self._kf.predict(dt)
        self._last_t = t
        match = self._gate(balls, pred, dt)
        if match is not None:
            self._far_hits = 0
            return self._correct(match, frame_number, t)

        strong = [d for d in balls if d.confidence >= self._reacquire_conf]
        self._far_hits = self._far_hits + 1 if strong else 0
        if strong and self._far_hits >= self._reacquire_frames:
            return self._start(strong[0], frame_number, t)

        self._misses += 1
        if self._misses > self._max_coast:
            self._kf = None
            self._history.clear()
            return None
        return self._state(frame_number, t, predicted=True)

    def _gate(self, balls: list[Detection], pred: np.ndarray, dt: float) -> Detection | None:
        vx, vy = self._kf.velocity if self._kf else (0.0, 0.0)
        gate = self._base_gate + np.hypot(vx, vy) * dt * 0.5 + self._misses * 40.0
        best, best_d = None, gate
        for det in balls:  # the closest to the prediction wins; duplicates are dropped
            d = float(np.hypot(det.center[0] - pred[0], det.center[1] - pred[1]))
            if d <= best_d:
                best, best_d = det, d
        return best

    def _start(self, det: Detection, frame_number: int, t: float) -> BallState:
        cx, cy = det.center
        self._kf = ConstantVelocityKalman(cx, cy, process_noise=self._process_noise)
        self._track_id += 1
        self._misses, self._far_hits = 0, 0
        self._last_t = t
        self._history.clear()
        return self._correct(det, frame_number, t, already_initialised=True)

    def _correct(self, det: Detection, frame_number: int, t: float, already_initialised: bool = False) -> BallState:
        assert self._kf is not None
        if not already_initialised:
            self._kf.update(*det.center)
        self._misses = 0
        self._last_conf = det.confidence
        x1, y1, x2, y2 = det.bbox
        self._size = max(x2 - x1, y2 - y1)
        return self._state(frame_number, t, predicted=False)

    def _state(self, frame_number: int, t: float, predicted: bool) -> BallState:
        assert self._kf is not None
        x, y = self._kf.position
        vx, vy = self._kf.velocity
        self._history.append(TrailPoint(t, x, y))
        confidence = self._last_conf * (0.85**self._misses)
        return BallState(t, frame_number, x, y, confidence, vx, vy, float(np.hypot(vx, vy)), self._track_id, predicted, self._size)
