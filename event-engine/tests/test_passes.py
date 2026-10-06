from football_events import EventEngine

from conftest import frames, hold, of_type, run, travel

PLAYERS = {12: (40, 50), 27: (60, 50)}


def _pass_specs(end=(60, 50), players=PLAYERS, travel_frames=10):
    return (
        hold((40.3, 50), players, 5)
        + travel((40.3, 50), end, players, travel_frames)
        + hold(end, players, 6)
    )


def test_pass_is_emitted_exactly_once_with_details():
    engine = EventEngine("m1")

    events = run(engine, frames(_pass_specs()))

    passes = of_type(events, "pass")
    assert len(passes) == 1
    p = passes[0]
    assert p.details["from_track_id"] == 12
    assert p.details["to_track_id"] == 27
    assert p.details["start"]["coordinate_space"] == "pitch"
    assert p.details["distance_unit"] == "m"
    assert 15 < p.details["distance"] < 25
    assert 0 < p.details["duration"] <= 4
    assert 0 < p.confidence <= 0.95
    assert len(of_type(events, "pass_candidate")) == 1
    assert len(of_type(events, "possession_change")) == 1


def test_short_touch_between_adjacent_players_is_not_a_pass():
    players = {12: (40, 50), 27: (42, 50)}
    engine = EventEngine("m1")

    events = run(engine, frames(_pass_specs(end=(42, 50), players=players, travel_frames=4)))

    assert of_type(events, "pass") == []


def test_ball_returning_to_same_player_is_not_a_pass():
    engine = EventEngine("m1")
    specs = (
        hold((40.3, 50), PLAYERS, 5)
        + travel((40.3, 50), (50, 50), PLAYERS, 5)
        + travel((50, 50), (40.3, 50), PLAYERS, 5)
        + hold((40.3, 50), PLAYERS, 5)
    )

    events = run(engine, frames(specs))

    assert of_type(events, "pass") == []


def test_slow_transfer_beyond_max_duration_is_not_a_pass():
    engine = EventEngine("m1")

    events = run(engine, frames(_pass_specs(travel_frames=60)))

    assert of_type(events, "pass") == []


def test_pass_in_pixel_space():
    engine = EventEngine("m1")

    events = run(engine, frames(_pass_specs(), with_pitch=False))

    passes = of_type(events, "pass")
    assert len(passes) == 1
    assert passes[0].details["distance_unit"] == "px"
