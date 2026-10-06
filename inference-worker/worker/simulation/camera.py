"""Synthetic broadcast camera for mock mode: projects pitch metres to pixels.

The whole pitch is visible as a trapezoid (far touchline narrower), like a
wide broadcast shot. Because the projection is known exactly, mock mode can
produce genuine (not fabricated) pitch coordinates via its inverse.
"""

from __future__ import annotations

import numpy as np

from football_events.geometry import PITCH_LENGTH_M, PITCH_WIDTH_M
from worker.pitch.homography import Pair, apply_homography, compute_homography

# Pitch corners in metres -> fractions of the frame (x, y).
_CORNERS_M: tuple[Pair, ...] = ((0, 0), (PITCH_LENGTH_M, 0), (PITCH_LENGTH_M, PITCH_WIDTH_M), (0, PITCH_WIDTH_M))
_CORNERS_FRAC: tuple[Pair, ...] = ((0.11, 0.24), (0.89, 0.24), (0.99, 0.96), (0.01, 0.96))


class SimCamera:
    def __init__(self, width: int, height: int) -> None:
        self.width, self.height = width, height
        pixels = [(fx * width, fy * height) for fx, fy in _CORNERS_FRAC]
        self._metres_to_px = compute_homography(_CORNERS_M, pixels)
        normalised = [(x / PITCH_LENGTH_M * 100, y / PITCH_WIDTH_M * 100) for x, y in _CORNERS_M]
        self.pixel_to_normalised: np.ndarray = compute_homography(pixels, normalised)

    def project(self, x_m: float, y_m: float) -> Pair:
        result = apply_homography(self._metres_to_px, x_m, y_m)
        assert result is not None  # the camera homography is well conditioned
        return result

    def scale_at(self, y_px: float) -> float:
        """Apparent object size factor: smaller towards the far touchline."""
        top, bottom = _CORNERS_FRAC[0][1] * self.height, _CORNERS_FRAC[2][1] * self.height
        f = min(1.0, max(0.0, (y_px - top) / (bottom - top)))
        return 0.55 + 0.45 * f
