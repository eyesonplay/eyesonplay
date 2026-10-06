"""Immutable value types shared by the engine and its rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class EventType(StrEnum):
    BALL_DETECTED = "ball_detected"
    BALL_LOST = "ball_lost"
    BALL_MOVE = "ball_move"
    POSSESSION = "possession"
    POSSESSION_CHANGE = "possession_change"
    PASS_CANDIDATE = "pass_candidate"
    PASS = "pass"
    SHOT_CANDIDATE = "shot_candidate"
    SHOT = "shot"
    BALL_OUT = "ball_out"
    CORNER = "corner"


# Event types the architecture is designed to support later. They are not
# produced yet; listing them keeps API/UI filters forward compatible.
PLANNED_EVENT_TYPES: tuple[str, ...] = (
    "goal",
    "throw_in",
    "goal_kick",
    "free_kick",
    "cross",
    "tackle",
    "interception",
    "save",
)


@dataclass(frozen=True, slots=True)
class Point:
    x: float
    y: float

    def to_dict(self) -> dict[str, float]:
        return {"x": round(self.x, 2), "y": round(self.y, 2)}


@dataclass(frozen=True, slots=True)
class BallObservation:
    """Tracked ball state for one frame.

    `pitch` is normalised 0-100 on both axes and is `None` whenever pitch
    calibration is unavailable. It must never be guessed.
    """

    pixel: Point
    pitch: Point | None
    confidence: float
    track_id: int = 1
    predicted: bool = False  # True when the tracker coasts without a detection


@dataclass(frozen=True, slots=True)
class PlayerObservation:
    track_id: int
    role: str  # "player" | "goalkeeper" | "referee"
    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2 in pixels
    confidence: float
    pitch: Point | None = None  # normalised foot position, if calibrated

    @property
    def foot(self) -> Point:
        x1, _, x2, y2 = self.bbox
        return Point((x1 + x2) / 2, y2)

    @property
    def can_possess(self) -> bool:
        return self.role in ("player", "goalkeeper")


@dataclass(frozen=True, slots=True)
class FrameObservation:
    frame_number: int
    video_ts: float  # seconds since start of the video source
    wall_ts: float  # unix seconds when the frame was captured
    ball: BallObservation | None
    players: tuple[PlayerObservation, ...] = ()


@dataclass(frozen=True, slots=True)
class EventDraft:
    """What a rule produces; the engine stamps ids, clock and ball info."""

    event_type: EventType
    confidence: float
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Event:
    event_id: str
    event_type: StrEnum  # football EventType or tennis TennisEventType
    match_id: str
    timestamp: float
    video_timestamp: float
    frame_number: int
    match_clock: str
    confidence: float
    ball: BallObservation | None
    details: dict[str, Any]

    def to_payload(self) -> dict[str, Any]:
        ball = None
        if self.ball is not None:
            ball = {
                "pixel": self.ball.pixel.to_dict(),
                "pitch": self.ball.pitch.to_dict() if self.ball.pitch else None,
                "confidence": round(self.ball.confidence, 3),
            }
        return {
            "event_id": self.event_id,
            "match_id": self.match_id,
            "timestamp": round(self.timestamp, 3),
            "video_timestamp": round(self.video_timestamp, 3),
            "frame": self.frame_number,
            "match_clock": self.match_clock,
            "event": self.event_type.value,
            "confidence": round(self.confidence, 3),
            # Team and player identity are unknown until an identity model
            # exists. They are explicitly null rather than guessed.
            "team": None,
            "player": None,
            "ball": ball,
            **self.details,
        }
