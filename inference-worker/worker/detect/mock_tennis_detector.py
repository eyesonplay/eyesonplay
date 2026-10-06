"""MockTennisDetector: noisy detections of the simulated tennis rally."""

from __future__ import annotations

import numpy as np

from worker.detect.base import Detection
from worker.ingest.source import Frame
from worker.simulation.tennis_camera import PLAYER_HEIGHT_M, TennisCamera
from worker.simulation.tennis_sim import TennisSnapshot

BALL_DIAMETER_M = 0.067 * 3  # drawn larger than life: motion blur makes it bigger on video
BALL_MISS_P = 0.06
JITTER_PX = 1.0
KITS = {"near": (230, 230, 235), "far": (30, 60, 140)}  # white vs navy shirts (RGB)


class MockTennisDetector:
    name = "mock-tennis-detector"
    family = "mock"
    device = "cpu"

    def __init__(self, camera: TennisCamera, detect_players: bool = True, seed: int | None = None) -> None:
        self._camera = camera
        self._detect_players = detect_players
        self._rng = np.random.default_rng(seed)

    def detect(self, frame: Frame) -> list[Detection]:
        snap = frame.truth
        if not isinstance(snap, TennisSnapshot):
            return []
        detections: list[Detection] = []
        if snap.ball is not None and self._rng.random() >= BALL_MISS_P:
            px, py = self._camera.project(*snap.ball)
            px, py = px + self._rng.normal(0, JITTER_PX), py + self._rng.normal(0, JITTER_PX)
            r = max(2.0, BALL_DIAMETER_M * self._camera.pixels_per_metre(py) / 2)
            detections.append(Detection("ball", (px - r, py - r, px + r, py + r), float(self._rng.uniform(0.75, 0.97))))
        if self._detect_players:
            for p in snap.players:
                fx, fy = self._camera.project(p.x, p.y)
                h = PLAYER_HEIGHT_M * self._camera.pixels_per_metre(fy)
                w = h * 0.38
                kit = np.clip(np.array(KITS[p.side]) + self._rng.normal(0, 10, 3), 0, 255)
                detections.append(
                    Detection("player", (fx - w / 2, fy - h, fx + w / 2, fy), 0.93, tuple(float(v) for v in kit))
                )
        return detections
