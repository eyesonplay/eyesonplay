from football_events import EventEngine

from conftest import frames, hold, of_type, run, travel

TAKER = {11: (1.6, 3.5)}  # standing next to the top-left corner flag
CORNER_SPOT = (0.6, 1.0)  # ball placed in the corner arc (about 0.6 m from the flag)


def test_ball_placed_in_the_corner_arc_with_a_player_is_a_corner():
    events = run(EventEngine("m1"), frames(hold(CORNER_SPOT, TAKER, 15)))

    corners = of_type(events, "corner")
    assert len(corners) == 1
    details = corners[0].details
    assert details["corner"] == "top_left"
    assert details["taker_track_id"] == 11
    assert details["location"]["coordinate_space"] == "pitch"


def test_ball_rolling_through_the_corner_is_not_a_corner():
    players = {11: (8, 10)}
    specs = travel((10, 12), (0.5, 0.8), players, 4) + travel((0.5, 0.8), (10, 2), players, 4)

    events = run(EventEngine("m1"), frames(specs))

    assert of_type(events, "corner") == []


def test_a_still_ball_in_the_corner_with_nobody_near_is_not_a_corner():
    nobody_near = {11: (30, 40)}

    events = run(EventEngine("m1"), frames(hold(CORNER_SPOT, nobody_near, 20)))

    assert of_type(events, "corner") == []


def test_one_corner_per_placement_and_a_new_one_after_the_kick():
    players = {11: (98.4, 96.5)}
    spot = (99.4, 99.0)  # bottom-right corner
    specs = hold(spot, players, 20) + travel(spot, (88, 55), players, 4) + hold((88, 55), players, 5)
    specs += travel((88, 55), spot, players, 6) + hold(spot, players, 15)

    corners = of_type(run(EventEngine("m1"), frames(specs)), "corner")

    assert [c.details["corner"] for c in corners] == ["bottom_right", "bottom_right"]


def test_no_corner_without_pitch_calibration():
    events = run(EventEngine("m1"), frames(hold(CORNER_SPOT, TAKER, 15), with_pitch=False))

    assert of_type(events, "corner") == []


def test_a_brief_stop_is_not_enough():
    specs = hold(CORNER_SPOT, TAKER, 5) + travel(CORNER_SPOT, (12, 20), TAKER, 4)

    events = run(EventEngine("m1"), frames(specs))

    assert of_type(events, "corner") == []
