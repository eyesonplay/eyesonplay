"""Planar homography utilities (direct linear transform, numpy only)."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

Pair = tuple[float, float]


def compute_homography(src: Sequence[Pair], dst: Sequence[Pair]) -> np.ndarray:
    """3x3 matrix H with dst ~ H @ src, from >= 4 point correspondences."""
    if len(src) != len(dst) or len(src) < 4:
        raise ValueError("need at least 4 matching point pairs")
    rows = []
    for (x, y), (u, v) in zip(src, dst, strict=True):
        rows.append([-x, -y, -1, 0, 0, 0, u * x, u * y, u])
        rows.append([0, 0, 0, -x, -y, -1, v * x, v * y, v])
    _, _, vt = np.linalg.svd(np.asarray(rows, dtype=np.float64))
    h = vt[-1].reshape(3, 3)
    if abs(h[2, 2]) < 1e-12:
        raise ValueError("degenerate point configuration")
    return h / h[2, 2]


def apply_homography(h: np.ndarray, x: float, y: float) -> Pair | None:
    vec = h @ np.array([x, y, 1.0])
    if abs(vec[2]) < 1e-12:
        return None
    return float(vec[0] / vec[2]), float(vec[1] / vec[2])
