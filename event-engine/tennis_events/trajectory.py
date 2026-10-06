"""Turning points of the ball trajectory: reversals (hits) and bounces.

Each frame adds a sample; the sample two frames back is examined with two
samples on either side. Consecutive detections around one real event are
merged and reported at their strongest frame (the actual contact), so events
are reported a few frames late. Velocities are
scaled by the players' on-screen height, which makes thresholds independent
of resolution and zoom.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from football_events.types import BallObservation
from tennis_events.court import CourtPoint

WINDOW = 5
MAX_GAP_S = 0.35  # a longer gap breaks the trajectory
CLUSTER_GAP_S = 0.1  # detections closer than this belong to one event
# A hit sends the ball away at shot speed; the apex of an arc only *looks* like a
# reversal (perspective) and barely moves. Speeds in court units (0-100) per second.
MIN_SHOT_SPEED = 15.0  # ~3.6 m/s along the court after the turning point
MIN_INCOMING_SPEED = 2.0
# Uncalibrated fallback: on-screen vertical speed in player heights per second.
MIN_SHOT_SPEED_PX = 1.0


@dataclass(frozen=True, slots=True)
class Sample:
    t: float
    frame: int
    x: float  # pixels
    y: float
    court: CourtPoint | None  # ground projection (exact only at a bounce)
    ball: BallObservation


@dataclass(frozen=True, slots=True)
class Turning:
    sample: Sample
    reversal: bool  # direction along the court flipped
    bounce: bool  # strong upward kick in on-screen vertical velocity
    impulse: float  # vertical velocity change, player heights / s (negative = upward kick)
    outgoing: float = 0.0  # along-court velocity after the turning point (+ = towards the far side)


class TrajectoryAnalyser:
    def __init__(
        self,
        bounce_impulse: float,
        bounce_scorer: Callable[[Sequence[tuple[float, float]]], float] | None = None,
        bounce_probability: float = 0.45,
        to_720p: float = 1.0,
    ) -> None:
        self._samples: deque[Sample] = deque(maxlen=WINDOW)
        self._bounce_impulse = bounce_impulse
        self._scorer = bounce_scorer
        self._bounce_probability = bounce_probability
        self._to_720p = to_720p
        self._cluster: list[Turning] = []

    def reset(self) -> None:
        self._samples.clear()
        self._cluster = []

    def push(self, sample: Sample, player_height_px: float) -> Turning | None:
        raw = self._detect(sample, player_height_px)
        # A bounce followed at once by a hit (the return) are two events: a
        # cluster only continues while the kind of detection stays the same.
        same_event = (
            raw is not None
            and (not self._cluster or raw.sample.t - self._cluster[-1].sample.t <= CLUSTER_GAP_S)
            and (not self._cluster or raw.reversal == self._cluster[-1].reversal)
        )
        if raw is not None and same_event:
            self._cluster.append(raw)
            return None
        merged = _merge(self._cluster)
        self._cluster = [raw] if raw is not None else []
        return merged

    def _detect(self, sample: Sample, player_height_px: float) -> Turning | None:
        if self._samples and sample.t - self._samples[-1].t > MAX_GAP_S:
            self._samples.clear()
        self._samples.append(sample)
        if len(self._samples) < WINDOW:
            return None
        before, mid, after = self._samples[0], self._samples[2], self._samples[4]
        dt1, dt2 = mid.t - before.t, after.t - mid.t
        if dt1 <= 0 or dt2 <= 0:
            return None
        scale = max(player_height_px, 1.0)
        vy_before = (mid.y - before.y) / dt1 / scale
        vy_after = (after.y - mid.y) / dt2 / scale
        impulse = vy_after - vy_before

        calibrated = before.court is not None and mid.court is not None and after.court is not None
        along_before = _along(before, mid, scale) / dt1
        along_after = _along(mid, after, scale) / dt2
        min_out = MIN_SHOT_SPEED if calibrated else MIN_SHOT_SPEED_PX
        min_in = MIN_INCOMING_SPEED if calibrated else MIN_SHOT_SPEED_PX / 4
        reversal = along_before * along_after < 0 and abs(along_after) >= min_out and abs(along_before) >= min_in
        if self._scorer is not None:
            window = [(s.x * self._to_720p, s.y * self._to_720p) for s in self._samples]
            bounce = self._scorer(window) > self._bounce_probability
            if bounce:
                impulse = min(impulse, -self._bounce_impulse)  # strongest frame of the cluster still wins
        else:
            bounce = impulse < -self._bounce_impulse
        if not (reversal or bounce):
            return None
        return Turning(mid, reversal, bounce, impulse, along_after)


def _merge(cluster: list[Turning]) -> Turning | None:
    """One event per cluster, at the frame with the strongest upward kick."""
    if not cluster:
        return None
    strongest = min(cluster, key=lambda turning: turning.impulse)
    return Turning(
        strongest.sample,
        reversal=any(turning.reversal for turning in cluster),
        bounce=any(turning.bounce for turning in cluster),
        impulse=strongest.impulse,
        outgoing=cluster[-1].outgoing,
    )


def _along(a: Sample, b: Sample, scale: float) -> float:
    """Movement along the court (towards the far baseline is positive): court
    units when calibrated, otherwise on-screen player heights (up = far)."""
    if a.court is not None and b.court is not None:
        return b.court.x - a.court.x
    return (a.y - b.y) / scale
