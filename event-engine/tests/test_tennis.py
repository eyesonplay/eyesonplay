from tennis_events import TennisEventEngine
from tennis_events.court import CourtPoint, in_court, in_service_box, server_court

from tennis_scenarios import chain, flight, frames, idle, names, player_obs, run

NEAR = player_obs(1, 2.0, 70.0)  # near server, right half (deuce court)
FAR = player_obs(2, 96.0, 35.0)


def serve_and_rally_points():
    """Near serves cross-court into the far deuce box, far returns, ball bounces twice near."""
    serve = chain(
        flight((2.5, 70), (2.5, 70), 1.0, 2.6, 2.7, 0.3),  # toss up to the contact point
        flight((2.5, 70), (66, 30), 2.6, 0.0, 2.8, 0.6),  # serve to the bounce
        flight((66, 30), (95, 35), 0.0, 1.0, 1.6, 0.5),  # up to the far player
    )
    ret = chain(
        flight((95, 35), (25, 45), 1.0, 0.0, 2.4, 0.9),  # return lands near side, inside
        flight((25, 45), (15, 48), 0.0, 0.0, 0.8, 0.5),  # second bounce, unreturned
        flight((15, 48), (10, 49), 0.0, 0.0, 0.3, 0.3),
    )
    return chain(serve, ret)


def test_court_geometry():
    assert in_court(CourtPoint(50, 50), singles=True, tolerance=0)
    assert not in_court(CourtPoint(50, 95), singles=True, tolerance=0)
    assert in_court(CourtPoint(50, 95), singles=False, tolerance=0)
    assert server_court("near", 70) == "deuce" and server_court("far", 70) == "ad"
    assert in_service_box(CourtPoint(65, 30), "near", 70, 0)
    assert not in_service_box(CourtPoint(65, 70), "near", 70, 0)  # wrong box (not cross-court)
    assert not in_service_box(CourtPoint(85, 30), "near", 70, 0)  # beyond the service line


def test_serve_return_and_double_bounce_wins_point():
    engine = TennisEventEngine("m1")

    events = run(engine, frames(serve_and_rally_points(), [NEAR, FAR]))

    assert names(events) == ["serve", "bounce", "hit", "bounce", "bounce", "point_won"]
    serve, first_bounce, ret = events[0], events[1], events[2]
    assert serve.details["player"] == "near" and serve.details["court"] == "deuce"
    assert first_bounce.details["in"] is True and first_bounce.details["side"] == "far"
    assert ret.details["player"] == "far"
    point = events[-1].details
    assert point == {"sport": "tennis", "winner": "far", "reason": "double_bounce", "rally_length": 2}


def test_bounce_location_is_accurate_on_the_ground():
    events = run(TennisEventEngine("m1"), frames(serve_and_rally_points(), [NEAR, FAR]))
    loc = events[1].details["location"]
    assert abs(loc["x"] - 66) < 2.5 and abs(loc["y"] - 30) < 2.5


def test_long_serves_are_faults_then_double_fault():
    long_serve = chain(
        flight((2.5, 70), (2.5, 70), 1.0, 2.6, 2.7, 0.3),
        flight((2.5, 70), (85, 30), 2.6, 0.0, 2.9, 0.7),  # beyond the service line
        flight((85, 30), (112, 33), 0.0, 1.0, 1.4, 0.35),  # keeps most of its pace past the baseline
    )
    engine = TennisEventEngine("m1")
    first = run(engine, frames(long_serve, [NEAR, FAR]))
    gap = idle([NEAR, FAR], 1.0, 100, 2.0)
    second = run(engine, gap + frames(long_serve, [NEAR, FAR], start_frame=200, t0=4.0))

    assert names(first) == ["serve", "bounce", "fault"]
    assert names(second) == ["serve", "bounce", "double_fault", "point_won"]
    assert second[-1].details["winner"] == "far" and second[-1].details["reason"] == "double_fault"


def test_ball_out_in_rally():
    points = chain(
        flight((2.5, 70), (2.5, 70), 1.0, 2.6, 2.7, 0.3),
        flight((2.5, 70), (66, 30), 2.6, 0.0, 2.8, 0.6),
        flight((66, 30), (95, 35), 0.0, 1.0, 1.6, 0.5),
        flight((95, 35), (20, 97), 1.0, 0.0, 2.4, 0.9),  # return lands wide (outside singles)
        flight((20, 97), (10, 100), 0.0, 0.3, 0.8, 0.4),
    )
    events = run(TennisEventEngine("m1"), frames(points, [NEAR, FAR]))

    assert names(events)[-3:] == ["bounce", "ball_out", "point_won"]
    assert events[-1].details["winner"] == "near" and events[-1].details["reason"] == "out"


def test_bounces_before_the_serve_are_ignored():
    pre_serve = chain(flight((3, 72), (3, 72), 1.0, 0.0, 1.0, 0.4), flight((3, 72), (3, 72), 0.0, 1.0, 1.0, 0.4))
    events = run(TennisEventEngine("m1"), frames(pre_serve, [NEAR, FAR]))
    assert events == []


def test_point_ends_when_ball_is_not_returned():
    points = chain(
        flight((2.5, 70), (2.5, 70), 1.0, 2.6, 2.7, 0.3),
        flight((2.5, 70), (66, 30), 2.6, 0.0, 2.8, 0.6),  # ace: bounces in...
        flight((66, 30), (90, 22), 0.0, 1.2, 1.4, 0.4),  # ...flies past the receiver, then leaves the frame
    )
    engine = TennisEventEngine("m1")
    events = run(engine, frames(points, [NEAR, FAR]) + idle([NEAR, FAR], 3.0, 100, 1.0))

    assert names(events) == ["serve", "bounce", "point_won"]
    assert events[-1].details["reason"] == "not_returned" and events[-1].details["winner"] == "near"


def test_return_without_detected_serve_bounce_continues_the_rally():
    # The serve bounce is not visible (ball missing around it), but the
    # receiver returns: the serve was in and the rally goes on.
    from football_events import FrameObservation

    obs = frames(serve_and_rally_points(), [NEAR, FAR])
    hidden = [
        FrameObservation(o.frame_number, o.video_ts, o.wall_ts, None, o.players) if 0.78 <= o.video_ts <= 0.95 else o
        for o in obs
    ]
    events = run(TennisEventEngine("m1"), hidden)

    assert "fault" not in names(events)
    assert "hit" in names(events)
    assert events[-1].details["reason"] == "double_bounce"



def far_return_landing_at(landing):
    """Near serves, far returns and the ball comes down on the far (own) side at `landing`."""
    return chain(
        flight((2.5, 70), (2.5, 70), 1.0, 2.6, 2.7, 0.3),
        flight((2.5, 70), (66, 30), 2.6, 0.0, 2.8, 0.6),
        flight((66, 30), (95, 35), 0.0, 1.0, 1.6, 0.5),
        flight((95, 35), landing, 1.0, 0.0, 1.3, 0.3),
        flight(landing, (25, 45), 0.0, 0.0, 2.4, 0.9),
        flight((25, 45), (15, 48), 0.0, 0.0, 0.8, 0.5),
        flight((15, 48), (10, 49), 0.0, 0.0, 0.3, 0.3),
    )


def test_bounce_deep_on_the_hitters_own_side_is_not_a_net_error():
    """A ball that hits the net drops near it; a 'bounce' near the hitter's
    baseline is a misread (e.g. the swing), and the rally goes on."""
    events = run(TennisEventEngine("m1"), frames(far_return_landing_at((88, 36)), [NEAR, FAR]))

    points = [e.details for e in events if e.event_type == "point_won"]
    assert [p["reason"] for p in points] == ["double_bounce"] and points[0]["winner"] == "far"
    assert not [e for e in events if e.event_type == "bounce" and e.details["location"]["x"] == 88.0]


def test_ball_dropping_near_the_net_on_own_side_is_a_net_error():
    events = run(TennisEventEngine("m1"), frames(far_return_landing_at((56, 38)), [NEAR, FAR]))

    points = [e.details for e in events if e.event_type == "point_won"]
    assert points[0]["reason"] == "net" and points[0]["winner"] == "near"


def test_ball_landing_in_then_past_the_baseline_is_a_winner_not_out():
    """In first, then its second bounce behind the receiver: the hitter wins it."""
    points = chain(
        flight((2.5, 70), (2.5, 70), 1.0, 2.6, 2.7, 0.3),
        flight((2.5, 70), (66, 30), 2.6, 0.0, 2.8, 0.6),
        flight((66, 30), (95, 35), 0.0, 1.0, 1.6, 0.5),
        flight((95, 35), (20, 45), 1.0, 0.0, 2.4, 0.9),  # return lands in, deep
        flight((20, 45), (-8, 48), 0.0, 0.0, 1.0, 0.5),  # past the near player, behind the baseline
        flight((-8, 48), (-12, 49), 0.0, 0.0, 0.3, 0.3),
    )
    events = run(TennisEventEngine("m1"), frames(points, [NEAR, FAR]))

    assert "ball_out" not in names(events)
    point = [e.details for e in events if e.event_type == "point_won"]
    assert point == [{"sport": "tennis", "winner": "far", "reason": "double_bounce", "rally_length": 2}]


def test_ace_bouncing_behind_the_receiver_is_not_a_fault():
    points = chain(
        flight((2.5, 70), (2.5, 70), 1.0, 2.6, 2.7, 0.3),
        flight((2.5, 70), (66, 30), 2.6, 0.0, 2.8, 0.6),  # serve lands in the box
        flight((66, 30), (112, 22), 0.0, 0.0, 1.4, 0.6),  # untouched, bounces again behind the baseline
        flight((112, 22), (116, 20), 0.0, 0.0, 0.3, 0.3),
    )
    events = run(TennisEventEngine("m1"), frames(points, [NEAR, FAR]), settle_s=4.0)

    assert "fault" not in names(events) and "ball_out" not in names(events)
    assert [e.details["winner"] for e in events if e.event_type == "point_won"] == ["near"]


def test_serve_is_timestamped_at_the_hit_not_when_it_crosses_the_net():
    events = run(TennisEventEngine("m1"), frames(serve_and_rally_points(), [NEAR, FAR]))

    serve = next(e for e in events if e.event_type == "serve")
    assert abs(serve.video_timestamp - 0.3) <= 0.1  # contact after the 0.3 s toss
