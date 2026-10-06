import numpy as np
import pytest

from worker.ingest.source import Frame
from worker.pitch.auto_mapper import AutoHomographyMapper, CalibrationConfig
from worker.pitch.homography import apply_homography
from worker.pitch.keypoint_detector import Landmark
from worker.pitch.mapper import NullMapper
from worker.pitch.template import PITCH_LANDMARKS
from worker.simulation.camera import SimCamera

CAMERA = SimCamera(1280, 720)
NORMALISED_TO_PIXEL = np.linalg.inv(CAMERA.pixel_to_normalised)


def landmarks(indices, noise=0.0, seed=0):
    rng = np.random.default_rng(seed)
    out = []
    for i in indices:
        x, y = apply_homography(NORMALISED_TO_PIXEL, *PITCH_LANDMARKS[i])
        out.append(Landmark(i, x + rng.normal(0, noise), y + rng.normal(0, noise), 0.9))
    return out


class StubDetector:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def detect(self, image):
        self.calls += 1
        return self.result


GRASS = np.full((720, 1280, 3), (40, 140, 40), np.uint8)  # BGR pitch green


def frame(t):
    return Frame(int(t * 10), t, 0.0, 1280, 720, GRASS)


def calibrate(mapper, t0=0.0):
    """A calibration is confirmed by two consecutive agreeing fits."""
    mapper.observe(frame(t0))
    mapper.observe(frame(t0 + 0.4))


LEFT_HALF = [0, 1, 4, 5, 9, 10, 11, 12, 13, 14, 15, 16, 30]


def test_recovers_pitch_coordinates_from_visible_landmarks():
    mapper = AutoHomographyMapper(StubDetector(landmarks(LEFT_HALF, noise=0.5)))

    calibrate(mapper)

    assert mapper.calibrated
    target = (40.0, 30.0)
    px, py = apply_homography(NORMALISED_TO_PIXEL, *target)
    p = mapper.to_pitch(px, py)
    assert p is not None and p.x == pytest.approx(40, abs=0.6) and p.y == pytest.approx(30, abs=0.6)
    status = mapper.calibration()
    assert status["state"] == "ok" and status["keypoints"] == len(LEFT_HALF) and status["error_px"] < 2


def test_too_few_landmarks_means_no_pitch_coordinates():
    mapper = AutoHomographyMapper(StubDetector(landmarks([0, 1, 13])))

    mapper.observe(frame(0.0))

    assert not mapper.calibrated
    assert mapper.to_pitch(640, 400) is None
    assert mapper.calibration()["state"] == "searching"


def test_clustered_landmarks_are_rejected():
    mapper = AutoHomographyMapper(StubDetector(landmarks([6, 7, 8, 2, 3])))  # goal box corners only

    mapper.observe(frame(0.0))

    assert not mapper.calibrated


def test_a_wrong_landmark_is_rejected_by_ransac():
    points = landmarks(LEFT_HALF)
    wrong = Landmark(points[3].index, points[3].x + 150, points[3].y - 90, 0.9)
    mapper = AutoHomographyMapper(StubDetector([*points[:3], wrong, *points[4:]]))

    calibrate(mapper)

    assert mapper.calibrated
    p = mapper.to_pitch(*apply_homography(NORMALISED_TO_PIXEL, 25.0, 50.0))
    assert p is not None and p.x == pytest.approx(25, abs=1) and p.y == pytest.approx(50, abs=1)


def test_calibration_expires_when_landmarks_disappear():
    detector = StubDetector(landmarks(LEFT_HALF))
    mapper = AutoHomographyMapper(detector, CalibrationConfig(interval_s=0.4, max_age_s=1.0))
    calibrate(mapper)  # fitted at t=0.4
    detector.result = []

    mapper.observe(frame(0.9))
    assert mapper.calibrated  # still within max age
    mapper.observe(frame(1.6))
    assert not mapper.calibrated
    assert mapper.to_pitch(640, 400) is None


def test_detector_runs_at_calibration_interval_only():
    detector = StubDetector(landmarks(LEFT_HALF))
    mapper = AutoHomographyMapper(detector, CalibrationConfig(interval_s=0.4))
    for k in range(10):
        mapper.observe(frame(k * 0.1))
    assert detector.calls == 3  # t = 0.0, 0.4, 0.8


def test_null_mapper_reports_reason():
    assert NullMapper("no_model").calibration() == {"state": "no_model"}



def test_single_fit_is_not_trusted_until_confirmed():
    mapper = AutoHomographyMapper(StubDetector(landmarks(LEFT_HALF)))

    mapper.observe(frame(0.0))

    assert not mapper.calibrated
    assert mapper.calibration()["pending"] is True


def test_inconsistent_fit_does_not_replace_calibration():
    detector = StubDetector(landmarks(LEFT_HALF))
    mapper = AutoHomographyMapper(detector)
    calibrate(mapper)
    good = mapper.to_pitch(640, 500)

    # A fit from shifted landmarks (e.g. mislabelled) disagrees with the current one.
    detector.result = [Landmark(lm.index, lm.x + 220, lm.y + 60, lm.confidence) for lm in landmarks(LEFT_HALF)]
    mapper.observe(frame(0.8))

    after = mapper.to_pitch(640, 500)
    assert after is not None and after.x == pytest.approx(good.x, abs=0.5)


def test_camera_cut_is_accepted_after_two_agreeing_fits():
    detector = StubDetector(landmarks(LEFT_HALF))
    mapper = AutoHomographyMapper(detector, CalibrationConfig(smoothing=1.0))
    calibrate(mapper)
    shifted = [Landmark(lm.index, lm.x + 220, lm.y + 60, lm.confidence) for lm in landmarks(LEFT_HALF)]
    detector.result = shifted

    mapper.observe(frame(0.8))
    mapper.observe(frame(1.2))

    moved = mapper.to_pitch(*apply_homography(NORMALISED_TO_PIXEL, 30.0, 40.0))
    assert moved is not None and abs(moved.x - 30.0) > 3  # now follows the new view


def test_no_pitch_in_view_drops_calibration_immediately():
    detector = StubDetector(landmarks(LEFT_HALF))
    mapper = AutoHomographyMapper(detector)
    calibrate(mapper)
    graphics = np.full((720, 1280, 3), (120, 60, 20), np.uint8)  # a studio/graphics frame

    mapper.observe(Frame(9, 0.5, 0.0, 1280, 720, graphics))

    assert not mapper.calibrated
    status = mapper.calibration()
    assert status["state"] == "searching" and status["pitch_in_view"] is False
