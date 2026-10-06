from football_events import EngineConfig, EventEngine, EventType

from conftest import frames, of_type, run


def test_ball_detected_once_then_lost_after_debounce():
    # Arrange
    engine = EventEngine("m1")
    specs = [((50, 50), {})] * 3 + [(None, {})] * 5 + [((50, 50), {})]

    # Act
    events = run(engine, frames(specs))

    # Assert
    assert [e.event_type for e in events if e.event_type != EventType.BALL_MOVE] == [
        EventType.BALL_DETECTED,
        EventType.BALL_LOST,
        EventType.BALL_DETECTED,
    ]


def test_short_dropout_does_not_emit_ball_lost():
    engine = EventEngine("m1")
    specs = [((50, 50), {})] * 2 + [(None, {})] * 4 + [((50, 50), {})]

    events = run(engine, frames(specs))

    assert of_type(events, "ball_lost") == []
    assert len(of_type(events, "ball_detected")) == 1


def test_ball_move_is_throttled_by_interval_and_distance():
    engine = EventEngine("m1", EngineConfig(ball_move_min_interval_s=1.0))
    moving = [((10 + i, 50), {}) for i in range(30)]  # 3 seconds of movement
    stationary = [((40, 50), {})] * 30

    events = run(engine, frames(moving + stationary))

    moves = of_type(events, "ball_move")
    assert 3 <= len(moves) <= 4
    assert all(e.video_timestamp < 3.2 for e in moves)


def test_disabled_event_types_are_filtered():
    engine = EventEngine("m1", EngineConfig(enabled_events=frozenset({EventType.BALL_LOST})))
    specs = [((50, 50), {})] * 3 + [(None, {})] * 6

    events = run(engine, frames(specs))

    assert [e.event_type for e in events] == [EventType.BALL_LOST]
