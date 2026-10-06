"""Shirt colour of a detected player, from the torso area of the box.

NumPy only (works in the mock/CPU image too). Grass-green pixels are ignored
so the pitch showing between arms and body does not dilute the kit colour.
"""

from __future__ import annotations

import numpy as np

Box = tuple[float, float, float, float]

# Torso as fractions of the player box (excludes head, shorts and legs).
TORSO_TOP, TORSO_BOTTOM = 0.15, 0.5
TORSO_SIDE_MARGIN = 0.25
MIN_PIXELS = 12
GREEN_DOMINANCE = 1.1


def shirt_color(image_bgr: np.ndarray, bbox: Box) -> np.ndarray | None:
    """Mean RGB (0-255) of the torso's non-grass pixels, or None if too few."""
    height, width = image_bgr.shape[:2]
    x1, y1, x2, y2 = bbox
    w, h = x2 - x1, y2 - y1
    if w <= 2 or h <= 4:
        return None
    left = int(max(0, x1 + w * TORSO_SIDE_MARGIN))
    right = int(min(width, x2 - w * TORSO_SIDE_MARGIN))
    top = int(max(0, y1 + h * TORSO_TOP))
    bottom = int(min(height, y1 + h * TORSO_BOTTOM))
    if right <= left or bottom <= top:
        return None
    rgb = image_bgr[top:bottom, left:right, ::-1].reshape(-1, 3).astype(np.float64)
    r, g, b = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    grass = (g > r * GREEN_DOMINANCE) & (g > b * GREEN_DOMINANCE)
    kit = rgb[~grass]
    if len(kit) < MIN_PIXELS:
        return None
    return kit.mean(axis=0)
