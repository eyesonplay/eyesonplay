"""Automatic pitch calibration for moving broadcast cameras.

Every `interval_s` of video the landmark detector runs; a homography from
pixels to normalised pitch coordinates is fitted (RANSAC) and accepted only if
it is well supported and reprojects accurately. Between fits the last valid
homography is reused, but only for `max_age_s`: with a panning camera an old
homography is wrong, and pitch coordinates must never be invented.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from football_events import Point
from worker.ingest.source import Frame
from worker.pitch.camera_motion import CameraMotion
from worker.pitch.homography import apply_homography, compute_homography
from worker.pitch.keypoint_detector import Landmark, LandmarkDetector
from worker.pitch.mapper import HomographyMapper
from worker.pitch.template import PITCH_LANDMARKS

RANSAC_THRESHOLD = 2.0  # normalised pitch units
_TIME_EPSILON = 1e-6
GRASS_DOMINANCE = 1.1
GRASS_MIN_GREEN = 50
MIN_VIEW_AREA, MAX_VIEW_AREA = 100.0, 16000.0  # normalised units^2 (whole pitch = 10000)  # video timestamps like 0.1 * k are not exact


@dataclass(frozen=True, slots=True)
class CalibrationConfig:
    interval_s: float = 0.4
    max_age_s: float = 1.0
    # While camera motion is tracked continuously since the last fit, the
    # calibration stays valid this long without landmarks (drift accumulates).
    max_tracked_age_s: float = 8.0
    # Below this share of grass-green pixels there is no pitch in view
    # (graphics, close-ups, crowd): calibration is dropped at once. Measured
    # on broadcast footage: play 0.37-0.90, graphics/close-ups <= 0.24.
    min_grass_fraction: float = 0.35
    # Four points always fit a homography exactly, so a wrongly labelled
    # landmark would go unnoticed; five or more make the fit verifiable.
    min_keypoints: int = 5
    min_confidence: float = 0.5
    # Median landmark reprojection error, relative to frame width (1.2% = 15 px at 1280).
    max_reprojection_fraction: float = 0.012
    min_spread_fraction: float = 0.02  # landmark hull area / frame area
    smoothing: float = 0.5  # weight of the new homography when blending
    min_inlier_ratio: float = 0.6
    # A new fit must agree with the current calibration, or with the previous
    # fit (two consecutive agreeing fits), within this mean distance in
    # normalised pitch units. Wrong fits jump around; correct ones are stable.
    # (a panning broadcast camera moves several units between fits).
    max_disagreement: float = 12.0


@dataclass(frozen=True, slots=True)
class CalibrationStatus:
    state: str  # "ok" (fresh fit) | "tracking" (carried by camera motion) | "searching"
    keypoints: int
    error_px: float | None
    age_s: float | None
    pending: bool = False
    pitch_in_view: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "keypoints": self.keypoints,
            "error_px": None if self.error_px is None else round(self.error_px, 2),
            "age_s": None if self.age_s is None else round(self.age_s, 2),
            "pending": self.pending,
            "pitch_in_view": self.pitch_in_view,
        }


class AutoHomographyMapper:
    def __init__(self, detector: LandmarkDetector, config: CalibrationConfig | None = None) -> None:
        self._detector = detector
        self._cfg = config or CalibrationConfig()
        self._motion = CameraMotion()
        self._tracking = False  # camera motion followed without a break since the fit
        self._pitch_in_view = True
        self._h: np.ndarray | None = None
        self._fitted_at: float | None = None
        self._last_attempt: float | None = None
        self._now = 0.0
        self._last_keypoints = 0
        self._last_error: float | None = None
        self._pending: np.ndarray | None = None

    @property
    def calibrated(self) -> bool:
        if self._h is None or self._fitted_at is None:
            return False
        limit = self._cfg.max_tracked_age_s if self._tracking else self._cfg.max_age_s
        return self._now - self._fitted_at <= limit

    def calibration(self) -> dict[str, Any]:
        return self.status().to_dict()

    def status(self) -> CalibrationStatus:
        age = None if self._fitted_at is None else self._now - self._fitted_at
        fresh = age is not None and age <= self._cfg.max_age_s
        state = ("ok" if fresh else "tracking") if self.calibrated else "searching"
        return CalibrationStatus(
            state, self._last_keypoints, self._last_error, age, self._pending is not None, self._pitch_in_view
        )

    def observe(self, frame: Frame) -> None:
        self._now = frame.video_ts
        if frame.image is not None:
            self._pitch_in_view = grass_fraction(frame.image) >= self._cfg.min_grass_fraction
            if not self._pitch_in_view:
                self._forget()
                return
            self._follow_camera(frame.image)
        due = self._last_attempt is None or frame.video_ts - self._last_attempt >= self._cfg.interval_s - _TIME_EPSILON
        if frame.image is None or not due:
            return
        self._last_attempt = frame.video_ts
        landmarks = [lm for lm in self._detector.detect(frame.image) if lm.confidence >= self._cfg.min_confidence]
        self._last_keypoints = len(landmarks)
        fitted = self._fit(landmarks, frame.image)
        if fitted is None:
            return
        h, error = fitted
        size = (frame.width, frame.height)
        limit = self._cfg.max_disagreement
        agrees_current = self.calibrated and self._h is not None and _disagreement(self._h, h, size) <= limit
        agrees_pending = self._pending is not None and _disagreement(self._pending, h, size) <= limit
        if not (agrees_current or agrees_pending):
            self._pending = h  # unconfirmed (wrong fit or camera cut): wait for the next fit
            return
        self._pending = None
        if agrees_current and self._h is not None:
            h = self._cfg.smoothing * h + (1 - self._cfg.smoothing) * self._h
            h = h / h[2, 2]
        self._h, self._fitted_at, self._last_error = h, frame.video_ts, error
        self._tracking = True

    def _forget(self) -> None:
        """No pitch on screen: nothing can be mapped, and the next view may differ."""
        self._h = self._pending = self._fitted_at = None
        self._tracking = False
        self._last_keypoints = 0
        self._motion.reset()

    def _follow_camera(self, image: np.ndarray) -> None:
        """Carry the calibration (and an unconfirmed fit) along with the camera."""
        motion = self._motion.update(image)
        if motion.status == "first":
            return
        if motion.matrix is None:
            self._tracking = False  # cannot follow the camera: only fresh fits extend calibration
            if motion.status == "lost":
                self._pending = None  # a cut: the unconfirmed fit belongs to the old view
            return
        if self._h is not None:
            self._h = _normalise(self._h @ motion.matrix)
        if self._pending is not None:
            self._pending = _normalise(self._pending @ motion.matrix)

    def to_pitch(self, x: float, y: float) -> Point | None:
        if not self.calibrated or self._h is None:
            return None
        return HomographyMapper(self._h).to_pitch(x, y)

    def _fit(self, landmarks: list[Landmark], image: np.ndarray) -> tuple[np.ndarray, float] | None:
        height, width = image.shape[:2]
        if len(landmarks) < self._cfg.min_keypoints:
            return None
        pixels = np.array([(lm.x, lm.y) for lm in landmarks], dtype=np.float64)
        pitch = np.array([PITCH_LANDMARKS[lm.index] for lm in landmarks], dtype=np.float64)
        if _hull_area(pixels) < self._cfg.min_spread_fraction * width * height:
            return None  # landmarks nearly collinear / clustered: unstable fit
        fit = _robust_homography(pixels, pitch)
        if fit is None:
            return None
        h, inliers = fit
        if inliers < self._cfg.min_keypoints or inliers < self._cfg.min_inlier_ratio * len(landmarks):
            return None  # too many landmarks disagree with the fit (likely mislabelled)
        inverse = np.linalg.inv(h)
        errors = []
        for (px, py), (qx, qy) in zip(pixels, pitch, strict=True):
            back = apply_homography(inverse, qx, qy)
            if back is None:
                return None
            errors.append(float(np.hypot(back[0] - px, back[1] - py)))
        error = float(np.median(errors))
        if error > self._cfg.max_reprojection_fraction * width:
            return None
        centre = apply_homography(h, width / 2, height / 2)
        if centre is None or not (-20 <= centre[0] <= 120 and -20 <= centre[1] <= 120):
            return None  # the middle of the frame must land on or near the pitch
        if not _plausible_view(h, width, height):
            return None  # the visible pitch area would be degenerate or impossibly large
        return h, error


def grass_fraction(image_bgr: np.ndarray) -> float:
    """Share of grass-green pixels, on a coarse grid (cheap: ~1/64 of pixels)."""
    sample = image_bgr[::8, ::8].astype(np.float32)
    b, g, r = sample[..., 0], sample[..., 1], sample[..., 2]
    grass = (g > r * GRASS_DOMINANCE) & (g > b * GRASS_DOMINANCE) & (g > GRASS_MIN_GREEN)
    return float(grass.mean())


def _normalise(h: np.ndarray) -> np.ndarray:
    return h / h[2, 2]


def _plausible_view(h: np.ndarray, width: int, height: int) -> bool:
    """The lower two thirds of the frame (where the pitch is) must map to a
    convex quad on or near the pitch, from 1% of it up to a whole-pitch wide view."""
    corners = [(0, height * 0.35), (width, height * 0.35), (width, height), (0, height)]
    mapped = [apply_homography(h, x, y) for x, y in corners]
    if any(p is None or not (-60 <= p[0] <= 160 and -60 <= p[1] <= 160) for p in mapped):
        return False
    points = np.array(mapped)
    area = _hull_area(points)
    return MIN_VIEW_AREA <= area <= MAX_VIEW_AREA and len(_convex_hull(points)) == 4


def _disagreement(a: np.ndarray, b: np.ndarray, size: tuple[int, int]) -> float:
    """Mean distance (normalised pitch units) between two calibrations over a
    grid covering the lower two thirds of the frame, where the pitch is."""
    width, height = size
    distances = []
    for fx in (0.15, 0.5, 0.85):
        for fy in (0.4, 0.65, 0.9):
            pa = apply_homography(a, fx * width, fy * height)
            pb = apply_homography(b, fx * width, fy * height)
            if pa is not None and pb is not None:
                distances.append(float(np.hypot(pa[0] - pb[0], pa[1] - pb[1])))
    return float(np.mean(distances)) if distances else float("inf")


def _robust_homography(pixels: np.ndarray, pitch: np.ndarray) -> tuple[np.ndarray, int] | None:
    """RANSAC homography and its inlier count (all points when OpenCV is absent)."""
    inliers = len(pixels)
    try:
        import cv2

        h, mask = cv2.findHomography(pixels, pitch, cv2.RANSAC, RANSAC_THRESHOLD)
        if mask is not None:
            inliers = int(mask.sum())
    except ImportError:
        h = None
    if h is None:
        try:
            h = compute_homography([tuple(p) for p in pixels], [tuple(q) for q in pitch])
        except (ValueError, np.linalg.LinAlgError):
            return None
    if abs(h[2, 2]) < 1e-12 or abs(np.linalg.det(h)) < 1e-12:
        return None
    return h / h[2, 2], inliers


def _hull_area(points: np.ndarray) -> float:
    """Area of the convex hull, no OpenCV needed."""
    hull = _convex_hull(points)
    if len(hull) < 3:
        return 0.0
    return 0.5 * abs(sum(hull[i][0] * hull[i - 1][1] - hull[i - 1][0] * hull[i][1] for i in range(len(hull))))


def _convex_hull(points: np.ndarray) -> list[tuple]:
    """Convex hull vertices (monotone chain)."""
    pts = sorted(map(tuple, points))
    if len(pts) < 3:
        return pts

    def cross(o: tuple, a: tuple, b: tuple) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[tuple] = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper: list[tuple] = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]
