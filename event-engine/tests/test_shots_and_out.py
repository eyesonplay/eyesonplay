from football_events import EngineConfig, EventEngine
from football_events.rules.shots import goal_alignment
from football_events.types import Point

from conftest import frames, hold, of_type, run, travel

SHOOTER = {18: (82, 50)}


def test_fast_ball_towards_goal_is_shot_candidate_and_shot():
    engine = EventEngine("m1")
    specs = hold((82.3, 50), SHOOTER, 5) + travel((82.3, 50), (99, 51), SHOOTER, 3)

    events = run(engine, frames(specs))

    candidates = of_type(events, "shot_candidate")
    assert len(candidates) == 1
    assert candidates[0].details["track_id"] == 18
    assert candidates[0].details["target_goal"] == "right"
    assert len(of_type(events, "shot")) == 1


def test_shot_below_confirm_threshold_stays_candidate():
    engine = EventEngine("m1", EngineConfig(shot_confirm_confidence=0.99))
    specs = hold((82.3, 50), SHOOTER, 5) + travel((82.3, 50), (99, 51), SHOOTER, 3)

    events = run(engine, frames(specs))

    assert len(of_type(events, "shot_candidate")) == 1
    assert of_type(events, "shot") == []


def test_fast_ball_sideways_is_not_a_shot():
    engine = EventEngine("m1")
    specs = hold((82.3, 50), SHOOTER, 5) + travel((82.3, 50), (83, 10), SHOOTER, 3)

    events = run(engine, frames(specs))

    assert of_type(events, "shot_candidate") == []


def test_without_pitch_only_low_confidence_candidate():
    engine = EventEngine("m1")
    # ~800 px/s in a 1000 px wide frame: clearly above the pixel speed threshold.
    specs = hold((82.3, 50), SHOOTER, 5) + travel((82.3, 50), (99, 51), SHOOTER, 2)

    events = run(engine, frames(specs, with_pitch=False))

    candidates = of_type(events, "shot_candidate")
    assert len(candidates) == 1
    assert candidates[0].confidence <= 0.4
    assert of_type(events, "shot") == []


def test_goal_alignment_misses_wide_trajectory():
    assert goal_alignment(Point(90, 34), Point(20, 0), 35) is not None
    assert goal_alignment(Point(90, 34), Point(20, 20), 35) is None
    assert goal_alignment(Point(30, 34), Point(20, 0), 35) is None


def test_ball_out_once_per_exit_and_rearms():
    engine = EventEngine("m1")
    specs = hold((50, 101), {}, 4) + hold((50, 99), {}, 2) + hold((101, 50), {}, 4)

    events = run(engine, frames(specs))

    outs = of_type(events, "ball_out")
    assert [e.details["side"] for e in outs] == ["bottom", "right"]
    assert outs[1].details["within_goal_mouth"] is True


def test_ball_out_requires_pitch_calibration():
    engine = EventEngine("m1")

    events = run(engine, frames(hold((101, 50), {}, 5), with_pitch=False))

    assert of_type(events, "ball_out") == []
