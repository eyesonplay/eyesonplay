import numpy as np
import pytest

from worker.detect.base import Detection
from worker.pitch.homography import compute_homography
from worker.pitch.mapper import HomographyMapper, NullMapper
from worker.simulation.camera import SimCamera
from worker.track.ball_tracker import BallTracker
from worker.track.player_tracker import PlayerTracker, iou


def ball_at(x, y, conf=0.9):
    return Detection("ball", (x - 5, y - 5, x + 5, y + 5), conf)


def test_camera_projection_round_trips_through_mapper():
    camera = SimCamera(1280, 720)
    mapper = HomographyMapper(camera.pixel_to_normalised)
    for x_m, y_m in [(0, 0), (52.5, 34), (105, 68), (88.0, 20.0)]:
        px, py = camera.project(x_m, y_m)
        p = mapper.to_pitch(px, py)
        assert p is not None
        assert p.x == pytest.approx(x_m / 105 * 100, abs=1e-6)
        assert p.y == pytest.approx(y_m / 68 * 100, abs=1e-6)


def test_mapper_rejects_implausible_projection_and_null_mapper_never_guesses():
    camera = SimCamera(1280, 720)
    mapper = HomographyMapper(camera.pixel_to_normalised)
    assert mapper.to_pitch(640, -5000) is None
    assert NullMapper().to_pitch(640, 360) is None


def test_homography_requires_four_points():
    with pytest.raises(ValueError):
        compute_homography([(0, 0)] * 3, [(0, 0)] * 3)


def test_ball_tracker_smooths_noise_and_estimates_velocity():
    rng = np.random.default_rng(1)
    tracker = BallTracker()
    state = None
    for i in range(30):
        t = i / 10
        state = tracker.update([ball_at(100 + 200 * t + rng.normal(0, 2), 300 + rng.normal(0, 2))], i, t)
    assert state is not None
    assert state.velocity_x == pytest.approx(200, rel=0.15)
    assert abs(state.velocity_y) < 30
    assert len(tracker.history) == 30


def test_ball_tracker_coasts_then_declares_lost():
    tracker = BallTracker(max_coast_frames=3)
    for i in range(5):
        tracker.update([ball_at(100 + i * 10, 100)], i, i / 10)
    coasting = [tracker.update([], 5 + k, (5 + k) / 10) for k in range(3)]
    assert all(s is not None and s.predicted for s in coasting)
    assert tracker.update([], 8, 0.8) is None


def test_ball_tracker_prefers_detection_nearest_prediction():
    tracker = BallTracker()
    for i in range(5):
        tracker.update([ball_at(100 + i * 10, 100)], i, i / 10)
    state = tracker.update([ball_at(600, 600, conf=0.6), ball_at(151, 100, conf=0.5)], 5, 0.5)
    assert state is not None and abs(state.pixel_x - 150) < 10


def test_ball_tracker_reacquires_after_camera_cut():
    tracker = BallTracker()
    for i in range(5):
        tracker.update([ball_at(100, 100)], i, i / 10)
    first_id = tracker.update([ball_at(900, 500)], 5, 0.5).track_id
    state = tracker.update([ball_at(900, 500)], 6, 0.6)
    assert state is not None and state.track_id == first_id + 1
    assert state.pixel_x == pytest.approx(900)


def test_player_tracker_keeps_ids_and_expires_tracks():
    tracker = PlayerTracker(max_age=2)
    a = Detection("player", (0, 0, 20, 60), 0.9)
    b = Detection("player", (100, 0, 120, 60), 0.9)
    first = tracker.update([a, b])
    moved = tracker.update([Detection("player", (2, 0, 22, 60), 0.9), b])
    assert sorted(o.track_id for o in first) == sorted(o.track_id for o in moved)
    for _ in range(3):
        tracker.update([b])
    reborn = tracker.update([a, b])
    assert max(o.track_id for o in reborn) == 3


def test_iou():
    assert iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1
    assert iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0
