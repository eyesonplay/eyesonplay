from football_events import EventEngine

from conftest import frames, hold, of_type, run


def test_possession_requires_consecutive_frames():
    engine = EventEngine("m1")
    players = {7: (50, 50)}

    events = run(engine, frames(hold((50.5, 50), players, 2)))
    assert of_type(events, "possession") == []

    events = run(engine, frames(hold((50.5, 50), players, 1), start=2))
    poss = of_type(events, "possession")
    assert len(poss) == 1
    assert poss[0].details["track_id"] == 7
    assert engine.possession.holder == 7


def test_single_frame_blip_never_changes_possession():
    engine = EventEngine("m1")
    players = {7: (50, 50), 9: (60, 50)}
    specs = hold((50.5, 50), players, 5) + hold((59.5, 50), players, 1) + hold((50.5, 50), players, 5)

    events = run(engine, frames(specs))

    assert of_type(events, "possession_change") == []
    assert engine.possession.holder == 7


def test_possession_change_between_two_players():
    engine = EventEngine("m1")
    players = {7: (50, 50), 9: (51.5, 50)}
    # Ball sits at player 7, then moves onto player 9 (a tackle at close range).
    specs = hold((50.2, 50), players, 4) + hold((51.6, 50), players, 6)

    events = run(engine, frames(specs))

    changes = of_type(events, "possession_change")
    assert len(changes) == 1
    assert changes[0].details == {"from_track_id": 7, "to_track_id": 9}
    assert engine.possession.holder == 9


def test_referee_never_gets_possession():
    from football_events import FrameObservation

    from conftest import ball, player

    engine = EventEngine("m1")
    obs = [
        FrameObservation(i, i / 10, 0.0, ball(50, 50), (player(99, 50, 50, role="referee"),))
        for i in range(6)
    ]

    events = run(engine, obs)

    assert of_type(events, "possession") == []


def test_possession_in_pixel_space_without_calibration():
    engine = EventEngine("m1")
    players = {4: (50, 50)}

    events = run(engine, frames(hold((51, 50), players, 4), with_pitch=False))

    assert len(of_type(events, "possession")) == 1
