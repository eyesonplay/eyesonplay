import re

from football_events import EngineConfig, EventEngine
from football_events.clock import format_match_clock
from football_events.ids import new_event_id

from conftest import frames, run


def test_payload_shape_with_pitch():
    engine = EventEngine("match_001", EngineConfig(kickoff_offset_seconds=2490))
    event = run(engine, frames([((72.4, 38.1), {})]))[0]

    payload = event.to_payload()

    assert payload["event"] == "ball_detected"
    assert payload["match_id"] == "match_001"
    assert payload["match_clock"] == "41:30"
    assert payload["ball"]["pitch"] == {"x": 72.4, "y": 38.1}
    assert payload["team"] is None and payload["player"] is None


def test_payload_pitch_is_null_without_calibration():
    engine = EventEngine("m1")
    event = run(engine, frames([((72.4, 38.1), {})], with_pitch=False))[0]

    assert event.to_payload()["ball"]["pitch"] is None


def test_match_clock_format():
    assert format_match_clock(0) == "00:00"
    assert format_match_clock(61.9) == "01:01"
    assert format_match_clock(95 * 60 + 5) == "95:05"
    assert format_match_clock(-3) == "00:00"


def test_event_ids_are_unique_and_sortable_format():
    ids = {new_event_id() for _ in range(1000)}
    assert len(ids) == 1000
    assert all(re.fullmatch(r"evt_[0-9A-HJKMNP-TV-Z]{26}", i) for i in ids)


def test_config_validation():
    import pytest

    with pytest.raises(ValueError):
        EngineConfig(possession_confirm_frames=0)
