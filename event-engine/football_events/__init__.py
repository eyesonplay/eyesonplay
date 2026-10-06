"""Football event engine.

Turns per-frame tracked observations (ball + players, pixel and optional pitch
coordinates) into football events such as possession, passes and shots.
The package has no I/O and no third-party dependencies so it can be unit
tested in isolation and embedded in any worker process.
"""

from football_events.config import EngineConfig
from football_events.engine import EventEngine
from football_events.types import (
    PLANNED_EVENT_TYPES,
    BallObservation,
    Event,
    EventType,
    FrameObservation,
    PlayerObservation,
    Point,
    ScoreboardObservation,
)

__all__ = [
    "PLANNED_EVENT_TYPES",
    "BallObservation",
    "EngineConfig",
    "Event",
    "EventEngine",
    "EventType",
    "FrameObservation",
    "PlayerObservation",
    "Point",
    "ScoreboardObservation",
]
