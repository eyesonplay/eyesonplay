"""MockDetector: turns ground-truth world snapshots into noisy detections.

It mimics a real detector: pixel jitter, missed balls (more often when the
ball is close to a player), missed players and occasional low-confidence false
positives, so the tracker and event engine are genuinely exercised.
"""

from __future__ import annotations

import numpy as np

from worker.detect.base import Detection
from worker.ingest.source import Frame
from worker.simulation.camera import SimCamera
from worker.simulation.match_sim import WorldSnapshot

BALL_SIZE_PX = 14.0
PLAYER_HEIGHT_PX = 82.0
PLAYER_WIDTH_PX = 30.0
BALL_MISS_P = 0.05
BALL_OCCLUDED_MISS_P = 0.18
PLAYER_MISS_P = 0.03
FALSE_POSITIVE_P = 0.02
JITTER_PX = 1.5
# Simulated kits (RGB): home red, away blue, distinct goalkeepers, black referee.
KIT_COLORS: dict[tuple[int, str], tuple[int, int, int]] = {
    (0, "player"): (200, 40, 45),
    (1, "player"): (45, 80, 205),
    (0, "goalkeeper"): (235, 200, 40),
    (1, "goalkeeper"): (60, 200, 120),
    (-1, "referee"): (20, 20, 25),
}
KIT_NOISE = 14.0


class MockDetector:
    name = "mock-detector"
    family = "mock"
    device = "cpu"

    def __init__(self, camera: SimCamera, detect_players: bool = True, seed: int | None = None) -> None:
        self._camera = camera
        self._detect_players = detect_players
        self._rng = np.random.default_rng(seed)

    def detect(self, frame: Frame) -> list[Detection]:
        snapshot = frame.truth
        if not isinstance(snapshot, WorldSnapshot):
            return []
        detections: list[Detection] = []
        ball = self._ball(snapshot)
        if ball is not None:
            detections.append(ball)
        if self._detect_players:
            detections.extend(self._players(snapshot))
        if self._rng.random() < FALSE_POSITIVE_P:
            detections.append(self._false_positive())
        return detections

    def _ball(self, snap: WorldSnapshot) -> Detection | None:
        near_player = any(np.hypot(p.x - snap.ball_x, p.y - snap.ball_y) < 0.8 for p in snap.players)
        if self._rng.random() < (BALL_OCCLUDED_MISS_P if near_player else BALL_MISS_P):
            return None
        px, py = self._camera.project(snap.ball_x, snap.ball_y)
        px, py = px + self._rng.normal(0, JITTER_PX), py + self._rng.normal(0, JITTER_PX)
        if not (0 <= px < self._camera.width and 0 <= py < self._camera.height):
            return None
        half = BALL_SIZE_PX * self._camera.scale_at(py) / 2
        conf = float(np.clip(self._rng.normal(0.9, 0.05), 0.5, 0.99))
        return Detection("ball", (px - half, py - half, px + half, py + half), conf)

    def _players(self, snap: WorldSnapshot) -> list[Detection]:
        result = []
        for p in snap.players:
            if self._rng.random() < PLAYER_MISS_P:
                continue
            fx, fy = self._camera.project(p.x, p.y)
            fx, fy = fx + self._rng.normal(0, JITTER_PX), fy + self._rng.normal(0, JITTER_PX)
            s = self._camera.scale_at(fy)
            w, h = PLAYER_WIDTH_PX * s, PLAYER_HEIGHT_PX * s
            conf = float(np.clip(self._rng.normal(0.91, 0.03), 0.6, 0.99))
            kit = KIT_COLORS.get((p.team, p.role), KIT_COLORS[(-1, "referee")])
            appearance = tuple(float(v) for v in np.clip(np.array(kit) + self._rng.normal(0, KIT_NOISE, 3), 0, 255))
            result.append(Detection(p.role, (fx - w / 2, fy - h, fx + w / 2, fy), conf, appearance))  # type: ignore[arg-type]
        return result

    def _false_positive(self) -> Detection:
        x = float(self._rng.uniform(0, self._camera.width))
        y = float(self._rng.uniform(self._camera.height * 0.25, self._camera.height))
        return Detection("ball", (x - 6, y - 6, x + 6, y + 6), float(self._rng.uniform(0.2, 0.5)))
