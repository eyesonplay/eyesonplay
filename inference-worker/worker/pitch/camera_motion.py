"""Frame-to-frame camera motion (pan/tilt/zoom) from sparse optical flow.

Broadcast cameras follow the ball, so pitch landmarks often leave the frame.
Chaining each frame's motion onto the last landmark-based calibration keeps
the pitch mapping valid in between. Moving players are rejected as RANSAC
outliers; a hard camera cut breaks the flow and is reported as `None`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

ANALYSIS_WIDTH = 640
MAX_CORNERS = 400
MIN_TRACKED = 40
MIN_INLIERS = 25
MIN_INLIER_RATIO = 0.5
RANSAC_PX = 3.0


@dataclass(frozen=True, slots=True)
class MotionResult:
    # ok: motion estimated; first: nothing to compare yet; unknown: too little
    # texture to judge; lost: features tracked but no consistent camera motion
    # (a cut or heavy occlusion).
    status: Literal["ok", "first", "unknown", "lost"]
    matrix: np.ndarray | None = None  # current-frame pixels -> previous-frame pixels


class CameraMotion:
    def __init__(self) -> None:
        self._prev_gray: np.ndarray | None = None
        self._scale = 1.0

    def reset(self) -> None:
        self._prev_gray = None

    def update(self, image_bgr: np.ndarray) -> MotionResult:
        import cv2  # real-mode dependency only

        height, width = image_bgr.shape[:2]
        scale = min(1.0, ANALYSIS_WIDTH / width)
        small = cv2.resize(image_bgr, (int(width * scale), int(height * scale))) if scale < 1.0 else image_bgr
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        prev, self._prev_gray, previous_scale, self._scale = self._prev_gray, gray, self._scale, scale
        if prev is None or prev.shape != gray.shape or previous_scale != scale:
            return MotionResult("first")

        corners = cv2.goodFeaturesToTrack(prev, maxCorners=MAX_CORNERS, qualityLevel=0.01, minDistance=8)
        if corners is None or len(corners) < MIN_TRACKED:
            return MotionResult("unknown")
        moved, status, _ = cv2.calcOpticalFlowPyrLK(prev, gray, corners, None)
        ok = status.reshape(-1) == 1
        if int(ok.sum()) < MIN_TRACKED:
            return MotionResult("lost")
        before, after = corners.reshape(-1, 2)[ok], moved.reshape(-1, 2)[ok]
        m, mask = cv2.findHomography(after, before, cv2.RANSAC, RANSAC_PX)
        if m is None or mask is None:
            return MotionResult("lost")
        inliers = int(mask.sum())
        if inliers < MIN_INLIERS or inliers < MIN_INLIER_RATIO * len(before):
            return MotionResult("lost")  # no consistent motion: camera cut or heavy occlusion
        s = np.diag([scale, scale, 1.0])
        full = np.linalg.inv(s) @ m @ s
        return MotionResult("ok", full / full[2, 2])
