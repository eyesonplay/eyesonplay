"""Pixel -> normalised pitch (0-100) mapping.

Mappers return `None` whenever calibration is unavailable or the projection
is implausible. Pitch coordinates are never fabricated.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

import numpy as np

from football_events import Point
from worker.pitch.homography import Pair, apply_homography, compute_homography

# Points projecting further than this outside the pitch are treated as errors.
_PLAUSIBLE_MIN, _PLAUSIBLE_MAX = -25.0, 125.0


class PitchMapper(Protocol):
    @property
    def calibrated(self) -> bool: ...

    def to_pitch(self, x: float, y: float) -> Point | None: ...


class NullMapper:
    """No calibration. `reason` tells the dashboard why (disabled, no model…)."""

    calibrated = False

    def __init__(self, reason: str = "disabled") -> None:
        self.reason = reason

    def calibration(self) -> dict[str, object]:
        return {"state": self.reason}

    def to_pitch(self, x: float, y: float) -> Point | None:
        return None


class HomographyMapper:
    """Maps pixels to normalised pitch coordinates via a homography."""

    calibrated = True

    def __init__(self, pixel_to_pitch: np.ndarray, plausible: tuple[float, float] = (_PLAUSIBLE_MIN, _PLAUSIBLE_MAX)) -> None:
        self._h = pixel_to_pitch
        self._plausible = plausible

    def calibration(self) -> dict[str, object]:
        return {"state": "fixed"}

    @classmethod
    def from_keypoints(cls, pixels: Sequence[Pair], pitch_normalised: Sequence[Pair]) -> HomographyMapper:
        return cls(compute_homography(pixels, pitch_normalised))

    def to_pitch(self, x: float, y: float) -> Point | None:
        result = apply_homography(self._h, x, y)
        if result is None:
            return None
        px, py = result
        low, high = self._plausible
        if not (low <= px <= high and low <= py <= high):
            return None
        return Point(px, py)
