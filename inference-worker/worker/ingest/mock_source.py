"""Mock source: advances the simulated match in real time at the processing fps.

No pixels are produced; each Frame carries the ground-truth world snapshot
for the MockDetector to "see".
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any, Protocol

from worker.ingest.source import Frame
from worker.simulation.match_sim import MatchSimulation

MOCK_SOURCE_FPS = 25.0


class Simulation(Protocol):
    def step(self, dt: float) -> Any: ...  # returns a snapshot with a `t` attribute


class MockSource:
    is_live = False

    def __init__(
        self,
        fps: float,
        width: int,
        height: int,
        seed: int | None = None,
        realtime: bool = True,
        simulation: Simulation | None = None,
    ) -> None:
        if fps <= 0:
            raise ValueError("fps must be positive")
        self.width, self.height = width, height
        self.source_fps: float | None = MOCK_SOURCE_FPS
        self._period = 1.0 / fps
        self._sim: Simulation = simulation or MatchSimulation(seed)
        self._realtime = realtime
        self._closed = False

    def __iter__(self) -> Iterator[Frame]:
        frame_number = 0
        next_due = time.monotonic()
        while not self._closed:
            if self._realtime:
                next_due = self._wait(next_due)
            snapshot = self._sim.step(self._period)
            yield Frame(
                frame_number=frame_number,
                video_ts=snapshot.t,
                wall_ts=time.time(),
                width=self.width,
                height=self.height,
                truth=snapshot,
            )
            frame_number += 1

    def _wait(self, next_due: float) -> float:
        delay = next_due - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        elif -delay > self._period:
            # We fell behind (e.g. after a pause): resync instead of bursting.
            next_due = time.monotonic()
        return next_due + self._period

    def close(self) -> None:
        self._closed = True
