"""Ball velocity estimated over a short time window in the active space."""

from __future__ import annotations

from collections import deque

from football_events.geometry import Space
from football_events.types import Point


class BallKinematics:
    def __init__(self, window_s: float = 0.25) -> None:
        self._window_s = window_s
        self._space: Space | None = None
        self._samples: deque[tuple[float, Point]] = deque()

    def update(self, t: float, space: Space | None, pos: Point | None) -> tuple[Point | None, float]:
        if space is None or pos is None:
            return None, 0.0
        if space is not self._space:
            self._space = space
            self._samples.clear()
        self._samples.append((t, pos))
        while len(self._samples) > 2 and t - self._samples[0][0] > self._window_s:
            self._samples.popleft()
        if len(self._samples) < 2:
            return None, 0.0
        t0, p0 = self._samples[0]
        dt = t - t0
        if dt <= 0:
            return None, 0.0
        velocity = Point((pos.x - p0.x) / dt, (pos.y - p0.y) / dt)
        return velocity, (velocity.x**2 + velocity.y**2) ** 0.5
