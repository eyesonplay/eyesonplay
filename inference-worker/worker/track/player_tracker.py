"""Multi-object tracker for players/goalkeepers/referees.

Greedy association on a similarity that combines IoU with a motion-predicted
box and a centre-distance gate (relative to box height), so small, fast
players far from the camera keep their identity. Deliberately simple for the
MVP; Phase 3 swaps in ByteTrack behind the same `update()` signature.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from worker.detect.base import Detection

Box = tuple[float, float, float, float]

VELOCITY_SMOOTHING = 0.6


@dataclass(frozen=True, slots=True)
class TrackedObject:
    track_id: int | None
    cls: str
    bbox: Box
    confidence: float
    appearance: tuple[float, float, float] | None = None


@dataclass(slots=True)
class _Track:
    track_id: int
    cls: str
    bbox: Box
    vx: float = 0.0
    vy: float = 0.0
    misses: int = 0

    def predicted(self) -> Box:
        steps = self.misses + 1
        dx, dy = self.vx * steps, self.vy * steps
        x1, y1, x2, y2 = self.bbox
        return (x1 + dx, y1 + dy, x2 + dx, y2 + dy)

    def update(self, det: Detection) -> None:
        (ox, oy), (nx, ny) = _center(self.bbox), _center(det.bbox)
        steps = self.misses + 1
        a = VELOCITY_SMOOTHING
        self.vx = a * (nx - ox) / steps + (1 - a) * self.vx
        self.vy = a * (ny - oy) / steps + (1 - a) * self.vy
        self.bbox, self.cls, self.misses = det.bbox, det.cls, 0


def _center(b: Box) -> tuple[float, float]:
    return (b[0] + b[2]) / 2, (b[1] + b[3]) / 2


def iou(a: Box, b: Box) -> float:
    ix1, iy1, ix2, iy2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter <= 0:
        return 0.0
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return inter / (area_a + area_b - inter)


def similarity(predicted: Box, det: Box, gate_factor: float) -> float:
    """IoU, or a distance-based score when boxes are close but barely overlap."""
    overlap = iou(predicted, det)
    (px, py), (dx, dy) = _center(predicted), _center(det)
    gate = gate_factor * max(det[3] - det[1], 1.0)
    distance_score = 0.5 * (1.0 - math.hypot(px - dx, py - dy) / gate)
    return max(overlap, distance_score)


class PlayerTracker:
    def __init__(self, min_similarity: float = 0.2, max_age: int = 10, gate_factor: float = 1.5) -> None:
        self._tracks: list[_Track] = []
        self._next_id = 1
        self._min_similarity = min_similarity
        self._max_age = max_age
        self._gate_factor = gate_factor

    def update(self, detections: list[Detection]) -> list[TrackedObject]:
        people = [d for d in detections if d.cls != "ball"]
        pairs = sorted(
            (
                (similarity(t.predicted(), d.bbox, self._gate_factor), ti, di)
                for ti, t in enumerate(self._tracks)
                for di, d in enumerate(people)
            ),
            reverse=True,
        )
        used_tracks: set[int] = set()
        used_dets: set[int] = set()
        result: list[TrackedObject] = []
        for score, ti, di in pairs:
            if score < self._min_similarity:
                break
            if ti in used_tracks or di in used_dets:
                continue
            used_tracks.add(ti)
            used_dets.add(di)
            track, det = self._tracks[ti], people[di]
            track.update(det)
            result.append(TrackedObject(track.track_id, det.cls, det.bbox, det.confidence, det.appearance))

        for ti, track in enumerate(self._tracks):
            if ti not in used_tracks:
                track.misses += 1
        self._tracks = [t for t in self._tracks if t.misses <= self._max_age]

        for di, det in enumerate(people):
            if di in used_dets:
                continue
            track = _Track(self._next_id, det.cls, det.bbox)
            self._next_id += 1
            self._tracks.append(track)
            result.append(TrackedObject(track.track_id, det.cls, det.bbox, det.confidence, det.appearance))
        return result


def untracked(detections: list[Detection]) -> list[TrackedObject]:
    """Players without identities, used when tracking is disabled."""
    return [TrackedObject(None, d.cls, d.bbox, d.confidence, d.appearance) for d in detections if d.cls != "ball"]
