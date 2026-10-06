from collections import Counter

from football_events import EngineConfig, EventEngine
from worker.detect.mock_detector import MockDetector
from worker.ingest.mock_source import MockSource
from worker.pipeline import FramePipeline
from worker.pitch.mapper import HomographyMapper, NullMapper
from worker.simulation.camera import SimCamera


def run_pipeline(match_config, seconds=180, mapper_on=True, seed=3):
    camera = SimCamera(1280, 720)
    source = MockSource(match_config.processing_fps, 1280, 720, seed=seed, realtime=False)
    mapper = HomographyMapper(camera.pixel_to_normalised) if mapper_on else NullMapper()
    pipeline = FramePipeline(match_config, MockDetector(camera, seed=seed), mapper, EventEngine("m1", EngineConfig()))
    results = []
    for frame in source:
        results.append(pipeline.process(frame))
        if frame.video_ts >= seconds:
            break
    return results


def test_simulated_match_produces_realistic_event_mix(match_config):
    results = run_pipeline(match_config)

    counts = Counter(e.event_type.value for r in results for e in r.events)

    assert counts["possession"] > 20
    assert counts["pass"] > 5
    assert counts["possession_change"] > 5
    assert counts["ball_move"] > 50
    assert counts["shot_candidate"] + counts["ball_out"] > 0
    # Every event carries real pitch coordinates in calibrated mock mode.
    sample = next(e for r in results for e in r.events if e.event_type.value == "pass")
    payload = sample.to_payload()
    assert payload["start"]["coordinate_space"] == "pitch"


def test_frame_message_shape(match_config):
    results = run_pipeline(match_config, seconds=3)
    msg = next(r for r in results if r.ball is not None).frame_message()

    assert msg["coordinate_mode"] == "pitch"
    assert set(msg["ball"]) >= {"bbox", "pixel", "pitch", "confidence", "velocity", "speed", "track_id"}
    assert len(msg["players"]) >= 18
    assert all(p["track_id"] is not None for p in msg["players"])
    assert msg["trail"]


def test_without_calibration_pitch_is_null(match_config):
    results = run_pipeline(match_config, seconds=3, mapper_on=False)
    msg = next(r for r in results if r.ball is not None).frame_message()

    assert msg["coordinate_mode"] == "pixel"
    assert msg["ball"]["pitch"] is None
    assert all(p["pitch"] is None for p in msg["players"])


def test_ball_only_model_drops_players(match_config):
    cfg = match_config.model_copy(update={"detection_model": "ball"})
    results = run_pipeline(cfg, seconds=2)

    assert all(r.players == [] for r in results)


def test_mock_players_are_split_into_two_teams(match_config):
    results = run_pipeline(match_config, seconds=8)
    msg = results[-1].frame_message()

    assert [t["label"] for t in msg["teams"]] == ["A", "B"]
    outfield = [p for p in msg["players"] if p["class"] == "player"]
    assigned = [p["team"] for p in outfield if p["team"] is not None]
    assert len(assigned) >= 16 and set(assigned) == {0, 1}
    assert all(p["team"] is None for p in msg["players"] if p["class"] in ("referee", "goalkeeper"))
