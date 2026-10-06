"""Classical tennis court detection (no learned model, no licence constraints).

1. Line pixels: thin bright pixels (top-hat) or plain bright white, unsaturated.
2. Hough segments, grouped into near-horizontal lines (baselines / service
   lines) and the two converging sideline families.
3. Every combination of two horizontals and one left + one right sideline is
   mapped to candidate court lines, giving a homography.
4. Each candidate is scored by drawing the whole court template and checking,
   line by line, that it lands on line pixels; collapsed or wrong-half fits
   fail the per-line, interior and shape checks.
Broadcast tennis cameras are mostly static, so the result is cached and only
re-checked cheaply (`score`) until it stops fitting.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

import numpy as np

from worker.court.geometry import ACROSS_PAIRS, ALONG_PAIRS, COURT_LINES, INTERIOR

ANALYSIS_WIDTH = 960
MIN_SCORE = 0.75  # wrong-half fits measured at 0.55-0.66, correct ones 0.83-0.94
SAMPLES_PER_LINE = 30
MIN_VISIBLE_SAMPLES = 10
MIN_LINES_VISIBLE = 7
MIN_LINES_COVERED = 6
MAX_CANDIDATE_LINES = (8, 4)  # horizontals, sidelines per side
Line = tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class CourtFit:
    court_to_pixel: np.ndarray  # 3x3, full-resolution pixels
    score: float


class LineMask:
    """Line pixels of one frame, at analysis resolution."""

    def __init__(self, image_bgr: np.ndarray) -> None:
        import cv2

        height, width = image_bgr.shape[:2]
        self.scale = min(1.0, ANALYSIS_WIDTH / width)
        small = cv2.resize(image_bgr, None, fx=self.scale, fy=self.scale) if self.scale < 1 else image_bgr
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
        s, v = hsv[..., 1], hsv[..., 2]
        tophat = cv2.morphologyEx(v, cv2.MORPH_TOPHAT, cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9)))
        thin = (tophat >= 30) & (s <= 90) & (v >= 120)  # thin, dimmer distant lines
        bright = (v >= 170) & (s <= 70)  # thick, bright near lines
        self.mask = (thin | bright).astype(np.uint8) * 255
        self.dilated = cv2.dilate(self.mask, np.ones((3, 3), np.uint8))
        self.height, self.width = self.mask.shape

    def to_analysis(self, court_to_pixel: np.ndarray) -> np.ndarray:
        return np.diag([self.scale, self.scale, 1.0]) @ court_to_pixel


def score(court_to_px: np.ndarray, lines: LineMask) -> float:
    """Template agreement in [0, 1]; 0 for implausible fits. `court_to_px` is at
    analysis resolution."""
    import cv2

    covered, coverages = 0, []
    for (ax, ay), (bx, by) in COURT_LINES:
        hits = visible = 0
        for t in np.linspace(0.0, 1.0, SAMPLES_PER_LINE):
            q = court_to_px @ np.array([ax + (bx - ax) * t, ay + (by - ay) * t, 1.0])
            if q[2] <= 1e-9:
                continue
            x, y = q[0] / q[2], q[1] / q[2]
            if 0 <= x < lines.width and 0 <= y < lines.height:
                visible += 1
                hits += int(lines.dilated[int(y), int(x)] > 0)
        if visible >= MIN_VISIBLE_SAMPLES:
            coverages.append(hits / visible)
            covered += int(hits / visible >= 0.5)
    if len(coverages) < MIN_LINES_VISIBLE or covered < MIN_LINES_COVERED:
        return 0.0
    corners = []
    for u, v in ((0, 0), (0, 100), (100, 100), (100, 0)):
        q = court_to_px @ np.array([u, v, 1.0])
        if q[2] <= 1e-9:
            return 0.0
        corners.append([q[0] / q[2], q[1] / q[2]])
    quad = np.array(corners, np.float32)
    if not cv2.isContourConvex(quad) or cv2.contourArea(quad) < 0.04 * lines.width * lines.height:
        return 0.0
    lit_inside = 0
    for u, v in INTERIOR:
        q = court_to_px @ np.array([u, v, 1.0])
        x, y = q[0] / q[2], q[1] / q[2]
        if 0 <= x < lines.width and 0 <= y < lines.height and lines.dilated[int(y), int(x)] > 0:
            lit_inside += 1
    return float(np.mean(coverages)) - 0.1 * lit_inside


def detect_court(image_bgr: np.ndarray) -> CourtFit | None:
    """Full search; ~1-2 s on a 1080p frame. None when no court is found."""
    import cv2

    lines = LineMask(image_bgr)
    segments = cv2.HoughLinesP(
        lines.mask, 1, np.pi / 360, threshold=80, minLineLength=int(0.08 * lines.width), maxLineGap=15
    )
    if segments is None:
        return None
    horizontals, lefts, rights = _group(segments.reshape(-1, 4))
    best_score, best = 0.0, None
    for near, far in itertools.combinations(horizontals, 2):
        if near[1] + near[3] < far[1] + far[3]:
            near, far = far, near  # the near line is lower on screen
        for left, right in itertools.product(lefts, rights):
            corners = [_intersect(near, left), _intersect(near, right), _intersect(far, right), _intersect(far, left)]
            if any(c is None for c in corners):
                continue
            dst = np.float32(corners)
            for (x_near, x_far), (y_left, y_right) in itertools.product(ALONG_PAIRS, ACROSS_PAIRS):
                src = np.float32([(x_near, y_left), (x_near, y_right), (x_far, y_right), (x_far, y_left)])
                h = cv2.getPerspectiveTransform(src, dst)
                s = score(h, lines)
                if s > best_score:
                    best_score, best = s, h
    if best is None or best_score < MIN_SCORE:
        return None
    full = np.diag([1 / lines.scale, 1 / lines.scale, 1.0]) @ best
    return CourtFit(full / full[2, 2], best_score)


def _group(segments: np.ndarray) -> tuple[list[Line], list[Line], list[Line]]:
    horizontals, lefts, rights = [], [], []
    for x1, y1, x2, y2 in segments:
        angle = (np.degrees(np.arctan2(y2 - y1, x2 - x1)) + 180) % 180
        entry = (float(np.hypot(x2 - x1, y2 - y1)), (float(x1), float(y1), float(x2), float(y2)))
        if angle < 6 or angle > 174:
            horizontals.append(entry)
        elif 20 < angle < 85:
            rights.append(entry)  # top-left to bottom-right: the right sideline
        elif 95 < angle < 160:
            lefts.append(entry)
    n_h, n_s = MAX_CANDIDATE_LINES
    merged: list[Line] = []
    for _, line in sorted(sorted(horizontals, reverse=True)[:25], key=lambda e: (e[1][1] + e[1][3]) / 2):
        if merged and abs((line[1] + line[3]) / 2 - (merged[-1][1] + merged[-1][3]) / 2) < 8:
            continue  # the same court line found twice
        merged.append(line)
    longest = lambda group: [line for _, line in sorted(group, reverse=True)[:n_s]]  # noqa: E731
    return merged[:n_h], longest(lefts), longest(rights)


def _intersect(a: Line, b: Line) -> tuple[float, float] | None:
    x1, y1, x2, y2 = a
    x3, y3, x4, y4 = b
    d = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(d) < 1e-9:
        return None
    px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / d
    py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / d
    return px, py
