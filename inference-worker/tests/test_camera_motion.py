import cv2
import numpy as np
import pytest

from worker.ingest.source import Frame
from worker.pitch.auto_mapper import AutoHomographyMapper, CalibrationConfig
from worker.pitch.camera_motion import CameraMotion
from worker.pitch.homography import apply_homography

from test_auto_calibration import LEFT_HALF, NORMALISED_TO_PIXEL, StubDetector, landmarks

def _grass_world() -> np.ndarray:
    """Textured, grass-coloured world (BGR) so optical flow has features."""
    noise = np.random.default_rng(0).integers(0, 90, (900, 1600, 3)).astype(np.uint8)
    noise[..., 1] += 120
    return cv2.GaussianBlur(noise, (5, 5), 0)


WORLD = _grass_world()


def view(dx: int) -> np.ndarray:
    """A 1280x720 camera window over a larger textured world, panned by dx pixels."""
    return np.ascontiguousarray(WORLD[60:780, 100 + dx : 1380 + dx])


def test_pan_is_recovered_as_translation():
    motion = CameraMotion()
    assert motion.update(view(0)).status == "first"

    result = motion.update(view(12))

    assert result.status == "ok"
    # current pixel x maps to previous pixel x + 12 (the camera moved right)
    x, y = apply_homography(result.matrix, 640, 360)
    assert x == pytest.approx(652, abs=1.0) and y == pytest.approx(360, abs=1.0)


def test_hard_cut_is_reported_as_lost():
    motion = CameraMotion()
    motion.update(view(0))
    other = np.ascontiguousarray(np.random.default_rng(9).integers(0, 255, (720, 1280, 3), dtype=np.uint8))
    assert motion.update(other).status == "lost"


def test_blank_frames_are_unknown_not_a_cut():
    motion = CameraMotion()
    blank = np.zeros((720, 1280, 3), np.uint8)
    motion.update(blank)
    assert motion.update(blank).status == "unknown"


def test_calibration_follows_the_camera_without_landmarks():
    detector = StubDetector(landmarks(LEFT_HALF))
    mapper = AutoHomographyMapper(detector, CalibrationConfig(max_age_s=1.0, max_tracked_age_s=8.0))
    for k, t in enumerate((0.0, 0.4)):
        mapper.observe(Frame(k, t, 0.0, 1280, 720, view(0)))
    reference = mapper.to_pitch(640, 500)
    detector.result = []  # landmarks leave the frame; the camera pans right

    dx = 0
    for k in range(1, 31):  # 3 s at 10 fps, 4 px per frame
        dx = 4 * k
        mapper.observe(Frame(k + 2, 0.4 + k * 0.1, 0.0, 1280, 720, view(dx)))

    assert mapper.calibrated and mapper.calibration()["state"] == "tracking"
    # The world point that was at pixel x=640 is now at x=640-dx.
    moved = mapper.to_pitch(640 - dx, 500)
    assert moved is not None and moved.x == pytest.approx(reference.x, abs=0.5)


def test_tracking_ends_at_a_cut():
    detector = StubDetector(landmarks(LEFT_HALF))
    mapper = AutoHomographyMapper(detector)
    for k, t in enumerate((0.0, 0.4)):
        mapper.observe(Frame(k, t, 0.0, 1280, 720, view(0)))
    detector.result = []
    cut = np.ascontiguousarray(np.random.default_rng(9).integers(0, 255, (720, 1280, 3), dtype=np.uint8))

    mapper.observe(Frame(3, 0.5, 0.0, 1280, 720, cut))
    mapper.observe(Frame(4, 1.6, 0.0, 1280, 720, cut))

    assert not mapper.calibrated
