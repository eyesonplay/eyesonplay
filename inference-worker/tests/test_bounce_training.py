import json
import math
import random

import pytest

from football_events.types import BallObservation, FrameObservation, Point

from worker.detect.bounce_model import DEFAULT_WEIGHTS, OWN_WEIGHTS, load_bounce_model
from worker.training.dataset import ball_windows, bounce_times, label_windows, split_point
from worker.training.evaluate import score_span

FPS = 25
PERIOD_S = 0.8  # a bounce (lowest point on screen) every 0.8 s


def _obs(i: int, x: float, y: float, predicted: bool = False) -> FrameObservation:
    ball = BallObservation(pixel=Point(x, y), pitch=None, confidence=0.9, track_id=1, predicted=predicted)
    return FrameObservation(i, i / FPS, 0.0, ball, ())


def bouncing(seconds: float, noise: float = 0.0, seed: int = 1) -> list[FrameObservation]:
    """A ball crossing the screen, bouncing (a cusp at the bottom) every PERIOD_S."""
    rng = random.Random(seed)
    out = []
    for i in range(int(seconds * FPS)):
        t = i / FPS
        y = 600 - 200 * abs(math.sin(math.pi * t / PERIOD_S)) + rng.gauss(0, noise)
        out.append(_obs(i, 100 + 300 * t + rng.gauss(0, noise), y))
    return out


def test_windows_use_consecutive_detections_at_720p_scale():
    obs = bouncing(1.0)
    obs[10] = _obs(10, 0, 0, predicted=True)  # a predicted ball is not a measurement

    windows = ball_windows(obs, frame_height_px=1080)

    centres = [round(w.t * FPS) for w in windows]
    assert 12 in centres and 10 not in centres
    w = windows[0]
    assert len(w.points) == 5
    assert w.points[2] == pytest.approx((obs[2].ball.pixel.x * 720 / 1080, obs[2].ball.pixel.y * 720 / 1080))


def test_a_gap_breaks_the_trajectory():
    obs = bouncing(1.0)
    gapped = obs[:10] + obs[20:]  # 0.4 s without the ball

    windows = ball_windows(gapped, frame_height_px=720)

    assert windows
    assert all(not (w.points[0][0] < obs[15].ball.pixel.x < w.points[-1][0]) for w in windows)


def test_the_window_nearest_a_label_is_the_bounce_and_its_neighbours_are_left_out():
    windows = ball_windows(bouncing(2.0), frame_height_px=720)

    kept, targets = label_windows(windows, [0.81], tolerance_s=0.12)

    positives = [w.t for w, y in zip(kept, targets, strict=True) if y == 1]
    assert positives == [pytest.approx(0.8)]
    assert all(abs(w.t - 0.81) > 0.12 for w, y in zip(kept, targets, strict=True) if y == 0)


def test_bounce_labels_within_the_span():
    labels = {"events": [{"t": 1, "event": "bounce"}, {"t": 2, "event": "hit"}, {"t": 9, "event": "bounce"}]}

    assert bounce_times(labels, 0, 5) == [1]
    assert split_point({"labelled_until_s": 100, "events": []}, held_out=0.25) == pytest.approx(75)


def test_scores_only_the_held_out_span():
    labels = {"labelled_until_s": 20, "events": [{"t": 4, "event": "bounce"}, {"t": 16, "event": "bounce"}]}
    found = [{"event": "bounce", "video_timestamp": 4.1}, {"event": "bounce", "video_timestamp": 16.05}]

    report = score_span(labels, found, start=15)

    assert report["by_type"]["bounce"]["true_positives"] == 1
    assert report["by_type"]["bounce"]["false_negatives"] == 0


def test_trained_model_finds_bounces_and_is_preferred_with_its_threshold(tmp_path):
    pytest.importorskip("catboost")
    from worker.training.model import train_bounce_model

    windows = ball_windows(bouncing(40.0, noise=1.5), frame_height_px=720)
    kept, targets = label_windows(windows, [k * PERIOD_S for k in range(1, 50)], tolerance_s=0.12)
    trained = train_bounce_model(kept, targets, iterations=200)
    trained.save(tmp_path, {"source": "synthetic"})
    (tmp_path / DEFAULT_WEIGHTS).write_bytes((tmp_path / OWN_WEIGHTS).read_bytes())

    model = load_bounce_model(tmp_path)

    assert model is not None and model.name == OWN_WEIGHTS
    assert model.probability == pytest.approx(trained.threshold)
    assert json.loads((tmp_path / "tennis_bounce_own.json").read_text())["source"] == "synthetic"
    test = ball_windows(bouncing(8.0, noise=1.5, seed=7), frame_height_px=720)
    found = [w.t for w in test if model.scorer(w.points) > model.probability]
    hits = [t for t in found if abs(t / PERIOD_S - round(t / PERIOD_S)) * PERIOD_S <= 0.08]
    assert len(hits) >= 8 and len(found) - len(hits) <= 3  # 9 bounces in 8 s


def test_no_model_installed_means_rule_based_bounces(tmp_path):
    assert load_bounce_model(tmp_path) is None


def test_cli_trains_evaluates_and_saves(tmp_path, monkeypatch, capsys):
    pytest.importorskip("catboost")
    from worker.training import bounce
    from worker.training.extract import Recording

    video = tmp_path / "match.mp4"
    video.write_bytes(b"not decoded: the recording is stubbed")
    labels = tmp_path / "labels.json"
    times = [k * PERIOD_S for k in range(1, 50)]
    labels.write_text(json.dumps({"sport": "tennis", "events": [{"t": t, "event": "bounce"} for t in times]}))
    recording = Recording(720, FPS, tuple(bouncing(40.0, noise=1.5)))
    monkeypatch.setattr(bounce, "cached_record", lambda *args, **kwargs: recording)
    monkeypatch.setattr(bounce, "select_device", lambda mode: "cpu")
    out = tmp_path / "out"

    code = bounce.main(["--pair", str(video), str(labels), "--models-dir", str(tmp_path), "--output-dir", str(out)])

    assert code == 0
    meta = json.loads((out / "tennis_bounce_own.json").read_text())
    assert meta["source"] == [{"video": "match.mp4", "labels": ""}]
    assert set(meta["evaluation"]) == {"rules", OWN_WEIGHTS}
    assert "held-out events" in capsys.readouterr().out


def test_cli_rejects_labels_for_another_sport(tmp_path, capsys):
    from worker.training import bounce

    video = tmp_path / "match.mp4"
    video.write_bytes(b"x")
    labels = tmp_path / "labels.json"
    labels.write_text(json.dumps({"sport": "football", "events": [{"t": 1, "event": "goal"}]}))

    assert bounce.main(["--pair", str(video), str(labels)]) == 2
    assert "not tennis" in capsys.readouterr().err


def test_a_video_is_recorded_once_then_read_from_the_cache(tmp_path, monkeypatch):
    from worker.training import extract

    video = tmp_path / "match.mp4"
    video.write_bytes(b"x")
    calls = []

    def fake_record(*args, until_s):
        calls.append(args)
        return extract.Recording(720, FPS, tuple(bouncing(1.0)))

    monkeypatch.setattr(extract, "record", fake_record)

    first = extract.cached_record(video, tmp_path / "cache", None, "cpu", FPS, "yolov8n")
    second = extract.cached_record(video, tmp_path / "cache", None, "cpu", FPS, "yolov8n")

    assert len(calls) == 1
    assert second == first


def test_a_bounce_labelled_twice_counts_once():
    labels = {"events": [{"t": t, "event": "bounce"} for t in (19.39, 19.39, 20.62, 20.71, 23.09, 23.41, 30.0)]}

    times = bounce_times(labels, 0, 100)

    assert times == pytest.approx([19.39, 20.665, 23.25, 30.0])


def test_recording_stops_after_the_labelled_span(tmp_path, monkeypatch):
    from worker.training import extract

    video = tmp_path / "match.mp4"
    video.write_bytes(b"x")
    seen = []
    monkeypatch.setattr(
        extract, "record", lambda *args, until_s: seen.append(until_s) or extract.Recording(720, FPS, ())
    )

    extract.cached_record(video, tmp_path / "cache", None, "cpu", FPS, "yolov8n", until_s=60.0)
    extract.cached_record(video, tmp_path / "cache", None, "cpu", FPS, "yolov8n", until_s=90.0)

    assert seen == [60.0, 90.0]  # a longer span is recorded again
