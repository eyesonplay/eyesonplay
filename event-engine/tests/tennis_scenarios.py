"""Scripted tennis rallies seen by a simple broadcast camera behind the near baseline.

Court coordinates are normalised (see tennis_events.court). The ball's
"pitch" is the ground projection of its pixel position, exactly as a real
calibration would give, so it is only correct when the ball is on the ground.
"""

from __future__ import annotations

import math

from football_events import BallObservation, FrameObservation, PlayerObservation, Point

FPS = 25.0


def _w(x: float) -> float:  # pixels per normalised y unit (perspective: wider near)
    return 9.0 - 0.05 * x


def _ppm(x: float) -> float:  # pixels per metre of height
    return 40.0 - 0.25 * x


def ground(x: float, y: float) -> tuple[float, float]:
    return 640 + (y - 50) * _w(x), 650 - 4.5 * x


def ground_inverse(px: float, py: float) -> tuple[float, float]:
    x = (650 - py) / 4.5
    return x, 50 + (px - 640) / _w(x)


def ball_pixel(x: float, y: float, z: float) -> tuple[float, float]:
    px, py = ground(x, y)
    return px, py - z * _ppm(x)


def player_obs(track_id: int, x: float, y: float) -> PlayerObservation:
    fx, fy = ground(x, y)
    h = _ppm(x) * 1.85
    return PlayerObservation(track_id, "player", (fx - 0.2 * h, fy - h, fx + 0.2 * h, fy), 0.9, Point(x, y))


def flight(start, end, z0: float, z1: float, peak: float, seconds: float):
    """Ball positions (x, y, z) from start to end with a parabolic height."""
    n = max(2, int(seconds * FPS))
    pts = []
    for k in range(1, n + 1):
        f = k / n
        x = start[0] + (end[0] - start[0]) * f
        y = start[1] + (end[1] - start[1]) * f
        z = z0 + (z1 - z0) * f + 4 * (peak - max(z0, z1) / 2) * f * (1 - f)
        pts.append((x, y, max(0.0, z)))
    return pts


def frames(points, players, start_frame=0, t0=0.0):
    out = []
    for i, (x, y, z) in enumerate(points):
        px, py = ball_pixel(x, y, z)
        gx, gy = ground_inverse(px, py)
        ball = BallObservation(Point(px, py), Point(gx, gy), 0.9)
        out.append(FrameObservation(start_frame + i, t0 + i / FPS, 0.0, ball, tuple(players)))
    return out


def idle(players, seconds, start_frame, t0):
    n = int(seconds * FPS)
    return [FrameObservation(start_frame + i, t0 + i / FPS, 0.0, None, tuple(players)) for i in range(n)]


def chain(*segments):
    """Concatenate flight segments; returns a flat list of (x, y, z)."""
    pts = []
    for seg in segments:
        pts.extend(seg)
    return pts


def run(engine, observations, settle_s: float = 1.5):
    """Feed observations, then `settle_s` of frames without the ball so pending
    point endings (held for confirmation) are finalised."""
    observations = list(observations)
    if observations and settle_s > 0:
        last = observations[-1]
        observations += idle(last.players, settle_s, last.frame_number + 1, last.video_ts + 1 / FPS)
    events = []
    for obs in observations:
        events.extend(engine.update(obs))
    return events


def names(events):
    return [e.event_type.value for e in events]


__all__ = ["chain", "flight", "frames", "idle", "math", "names", "player_obs", "run"]
