import time

import cv2
import numpy as np
import pytest

from worker.court.detector import detect_court
from worker.court.geometry import COURT_LINES
from worker.court.mapper import TennisCourtMapper
from worker.ingest.source import Frame
from worker.pitch.homography import apply_homography
from worker.simulation.tennis_camera import TennisCamera

CAMERA = TennisCamera(1280, 720)
TRUE_H = CAMERA._court_to_px  # normalised court -> pixels


def court_image(h: np.ndarray = TRUE_H) -> np.ndarray:
    """Blue hard court with white lines, as the synthetic broadcast camera sees it."""
    image = np.full((720, 1280, 3), (200, 140, 60), np.uint8)  # BGR light blue surround
    quad = np.array([apply_homography(h, u, v) for u, v in ((0, 0), (0, 100), (100, 100), (100, 0))], np.int32)
    cv2.fillPoly(image, [quad], (150, 95, 40))  # darker court
    for (ax, ay), (bx, by) in COURT_LINES:
        pa, pb = apply_homography(h, ax, ay), apply_homography(h, bx, by)
        cv2.line(image, (round(pa[0]), round(pa[1])), (round(pb[0]), round(pb[1])), (245, 245, 245), 3, cv2.LINE_AA)
    return image


def test_detects_the_court_lines():
    fit = detect_court(court_image())

    assert fit is not None and fit.score >= 0.75
    for u, v in ((0, 0), (100, 100), (50, 50), (23, 12.5)):
        expected = apply_homography(TRUE_H, u, v)
        found = apply_homography(fit.court_to_pixel, u, v)
        assert np.hypot(found[0] - expected[0], found[1] - expected[1]) < 6


def test_no_court_in_a_close_up():
    close_up = cv2.GaussianBlur(np.random.default_rng(1).integers(0, 255, (720, 1280, 3), dtype=np.uint8), (31, 31), 0)
    assert detect_court(close_up) is None


def test_mapper_calibrates_in_background_and_maps_points():
    mapper = TennisCourtMapper()
    image = court_image()
    deadline = time.time() + 30
    t = 0.0
    while not mapper.calibrated and time.time() < deadline:
        mapper.observe(Frame(int(t * 25), t, 0.0, 1280, 720, image))
        t += 0.5
        time.sleep(0.05)

    assert mapper.calibrated
    px = apply_homography(TRUE_H, 40.0, 60.0)
    p = mapper.to_pitch(*px)
    assert p is not None and p.x == pytest.approx(40, abs=1.5) and p.y == pytest.approx(60, abs=1.5)
    assert mapper.calibration()["state"] == "ok"


def test_mapper_drops_calibration_when_the_court_leaves_the_frame():
    mapper = TennisCourtMapper()
    image = court_image()
    deadline, t = time.time() + 30, 0.0
    while not mapper.calibrated and time.time() < deadline:
        mapper.observe(Frame(0, t, 0.0, 1280, 720, image))
        t += 0.5
        time.sleep(0.05)
    blank = np.full((720, 1280, 3), (90, 60, 30), np.uint8)

    mapper.observe(Frame(1, t + 1.0, 0.0, 1280, 720, blank))

    assert not mapper.calibrated and mapper.to_pitch(640, 400) is None


def calibrated_mapper(image: np.ndarray) -> tuple[TennisCourtMapper, float]:
    mapper = TennisCourtMapper()
    deadline, t = time.time() + 30, 0.0
    while not mapper.calibrated and time.time() < deadline:
        mapper.observe(Frame(0, t, 0.0, 1280, 720, image))
        t += 0.5
        time.sleep(0.05)
    assert mapper.calibrated
    return mapper, t


def test_court_is_back_on_the_first_frame_after_a_close_up():
    """Broadcast cameras return to the same wide framing: the last fit is
    re-checked on every frame while lost, without waiting for a full search."""
    image = court_image()
    mapper, t = calibrated_mapper(image)
    close_up = np.full((720, 1280, 3), (90, 60, 30), np.uint8)
    mapper.observe(Frame(1, t + 0.5, 0.0, 1280, 720, close_up))
    assert not mapper.calibrated

    mapper.observe(Frame(2, t + 0.56, 0.0, 1280, 720, image))

    assert mapper.calibrated and mapper.calibration()["state"] == "ok"


def test_a_different_framing_is_not_mistaken_for_the_old_one():
    image = court_image()
    mapper, t = calibrated_mapper(image)
    mapper.observe(Frame(1, t + 0.5, 0.0, 1280, 720, np.full((720, 1280, 3), (90, 60, 30), np.uint8)))
    shifted = np.roll(image, 90, axis=1)  # camera panned: the old fit no longer lands on the lines

    mapper.observe(Frame(2, t + 0.56, 0.0, 1280, 720, shifted))

    assert not mapper.calibrated
