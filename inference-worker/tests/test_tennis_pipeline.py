from collections import Counter

from tennis_events import TennisEventEngine
from worker.detect.mock_tennis_detector import MockTennisDetector
from worker.detect.registry import TENNIS_PLAUSIBLE
from worker.ingest.mock_source import MockSource
from worker.pipeline import FramePipeline
from worker.pitch.mapper import HomographyMapper
from worker.simulation.tennis_camera import TennisCamera
from worker.simulation.tennis_sim import TennisSimulation


def run_tennis(match_config, seconds=180, seed=5):
    cfg = match_config.model_copy(update={"sport": "tennis", "processing_fps": 25})
    camera = TennisCamera(1280, 720)
    source = MockSource(25, 1280, 720, realtime=False, simulation=TennisSimulation(seed))
    pipeline = FramePipeline(
        cfg, MockTennisDetector(camera, seed=seed), HomographyMapper(camera.pixel_to_normalised, plausible=TENNIS_PLAUSIBLE), TennisEventEngine("m1")
    )
    results = []
    for frame in source:
        results.append(pipeline.process(frame))
        if frame.video_ts >= seconds:
            break
    return results


def test_simulated_tennis_produces_points(match_config):
    results = run_tennis(match_config)
    events = [e for r in results for e in r.events]
    counts = Counter(e.event_type.value for e in events)

    assert counts["serve"] >= 15
    assert counts["bounce"] >= counts["serve"]
    assert counts["hit"] >= 5
    assert counts["point_won"] >= 10
    winners = {e.details["winner"] for e in events if e.event_type.value == "point_won"}
    assert winners == {"near", "far"}


def test_tennis_frames_have_court_coordinates_and_no_teams(match_config):
    results = run_tennis(match_config, seconds=5)
    msg = next(r for r in results if r.ball is not None).frame_message()

    assert msg["coordinate_mode"] == "pitch"
    assert len(msg["players"]) == 2 and all(p["team"] is None for p in msg["players"])
    assert msg["teams"] == []
