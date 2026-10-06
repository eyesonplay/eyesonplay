"""Command and control contract shared with the API (see docs/redis-contract.md)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

COMMANDS_STREAM = "worker:commands"
COMMANDS_GROUP = "workers"
STATUS_STREAM = "status:updates"
EVENTS_STREAM = "events:stream"

Sport = Literal["football", "tennis"]
SourceType = Literal["hls", "rtmp", "url", "upload"]
DetectionModel = Literal["ball", "ball_players", "ball_players_pitch"]
ControlState = Literal["running", "paused", "stopped"]


class MatchConfig(BaseModel):
    sport: Sport = "football"
    source_type: SourceType
    source: str = Field(min_length=1)
    processing_fps: int = Field(ge=1, le=60)
    detection_model: DetectionModel
    model_name: str = "yolov8n"
    confidence_threshold: float = Field(ge=0.0, le=1.0)
    enable_event_detection: bool = True
    enable_player_tracking: bool = True
    enable_pitch_mapping: bool = True
    kickoff_offset_seconds: float = 0.0

    @property
    def detect_players(self) -> bool:
        return self.detection_model != "ball"

    @property
    def is_live(self) -> bool:
        return self.source_type in ("hls", "rtmp")


class StartCommand(BaseModel):
    command: Literal["start"]
    match_id: str
    session_id: str
    config: MatchConfig


class ControlSignal(BaseModel):
    session_id: str
    state: ControlState


def control_key(match_id: str) -> str:
    return f"match:{match_id}:control"


def lease_key(match_id: str) -> str:
    return f"match:{match_id}:lease"


def channel(match_id: str, kind: str) -> str:
    return f"match:{match_id}:{kind}"
