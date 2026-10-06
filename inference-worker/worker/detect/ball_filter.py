"""Cheap context filter for ball candidates on real video.

Stock detectors produce low-confidence "ball" hits in the crowd, on the
advertising boards and on line markings. A real ball in play is surrounded
by grass, so candidates whose surrounding ring is mostly not pitch-green are
rejected.
"""

from __future__ import annotations

import numpy as np

from worker.detect.base import Detection

RING_PADDING_PX = 6
MIN_GREEN_FRACTION = 0.45
# OpenCV-style HSV ranges for pitch grass (hue in 0..179).
GREEN_HUE = (30, 90)
MIN_SATURATION = 40
MIN_VALUE = 35


def green_fraction(image: np.ndarray, bbox: tuple[float, float, float, float]) -> float:
    import cv2  # real-mode dependency only

    h, w = image.shape[:2]
    x1, y1, x2, y2 = bbox
    pad = RING_PADDING_PX + max(x2 - x1, y2 - y1)
    ox1, oy1 = max(0, int(x1 - pad)), max(0, int(y1 - pad))
    ox2, oy2 = min(w, int(x2 + pad)), min(h, int(y2 + pad))
    if ox2 <= ox1 or oy2 <= oy1:
        return 0.0
    patch = cv2.cvtColor(image[oy1:oy2, ox1:ox2], cv2.COLOR_BGR2HSV)
    ring = np.ones(patch.shape[:2], dtype=bool)
    ring[max(0, int(y1) - oy1) : int(y2) - oy1 + 1, max(0, int(x1) - ox1) : int(x2) - ox1 + 1] = False
    hue, sat, val = patch[..., 0], patch[..., 1], patch[..., 2]
    green = (hue >= GREEN_HUE[0]) & (hue <= GREEN_HUE[1]) & (sat >= MIN_SATURATION) & (val >= MIN_VALUE)
    total = int(ring.sum())
    return float((green & ring).sum()) / total if total else 0.0


def on_pitch(image: np.ndarray | None, detection: Detection) -> bool:
    if image is None or detection.cls != "ball":
        return True
    return green_fraction(image, detection.bbox) >= MIN_GREEN_FRACTION
