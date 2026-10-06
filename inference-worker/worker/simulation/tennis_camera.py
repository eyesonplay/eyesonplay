"""Broadcast-style camera behind and above the near baseline, for tennis mock mode.

Ground points map through a homography fitted to the doubles-court corners;
height lifts a point up the screen by the local pixels-per-metre, so balls in
the air project like on real video (their ground projection is wrong until
they bounce, exactly what the event engine must cope with).
"""

from __future__ import annotations

import numpy as np

from worker.pitch.homography import Pair, apply_homography, compute_homography
from worker.simulation.tennis_sim import LENGTH, WIDTH

PLAYER_HEIGHT_M = 1.85
# Normalised court corners (x along, y across) -> fractions of the frame.
_CORNERS_N: tuple[Pair, ...] = ((0, 0), (0, 100), (100, 100), (100, 0))
_CORNERS_FRAC: tuple[Pair, ...] = ((0.12, 0.86), (0.88, 0.86), (0.635, 0.30), (0.365, 0.30))
_NEAR_PLAYER_FRAC, _FAR_PLAYER_FRAC = 0.20, 0.085  # on-screen player height / frame height


class TennisCamera:
    def __init__(self, width: int, height: int) -> None:
        self.width, self.height = width, height
        pixels = [(fx * width, fy * height) for fx, fy in _CORNERS_FRAC]
        self._court_to_px = compute_homography(_CORNERS_N, pixels)
        self.pixel_to_normalised: np.ndarray = compute_homography(pixels, _CORNERS_N)

    @staticmethod
    def normalise(x_m: float, y_m: float) -> Pair:
        return x_m / LENGTH * 100, y_m / WIDTH * 100

    def ground(self, x_m: float, y_m: float) -> Pair:
        result = apply_homography(self._court_to_px, *self.normalise(x_m, y_m))
        assert result is not None
        return result

    def pixels_per_metre(self, y_px: float) -> float:
        near_y, far_y = _CORNERS_FRAC[0][1] * self.height, _CORNERS_FRAC[2][1] * self.height
        f = (y_px - far_y) / (near_y - far_y)
        frac = _FAR_PLAYER_FRAC + (_NEAR_PLAYER_FRAC - _FAR_PLAYER_FRAC) * f
        return max(2.0, frac * self.height / PLAYER_HEIGHT_M)

    def project(self, x_m: float, y_m: float, z_m: float = 0.0) -> Pair:
        gx, gy = self.ground(x_m, y_m)
        return gx, gy - z_m * self.pixels_per_metre(gy)
