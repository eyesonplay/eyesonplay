"""Match request/response schemas with source validation."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.db.models import DetectionModel, MatchStatus, SourceType, Sport

ProcessingFps = Literal[5, 10, 15, 25, 30]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Team = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
ModelName = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9._-]{1,120}$")]
Confidence = Annotated[float, Field(ge=0.05, le=0.99)]
KickoffOffset = Annotated[float, Field(ge=0, le=3 * 3600)]
ExternalRef = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9._:-]{1,80}$")]

_UPLOAD_RE = re.compile(r"^uploads/[a-z0-9]{26}\.(mp4|mov|mkv|webm)$")
_SCHEMES: dict[SourceType, tuple[str, ...]] = {
    SourceType.HLS: ("http://", "https://"),
    SourceType.URL: ("http://", "https://"),
    SourceType.RTMP: ("rtmp://", "rtmps://"),
}


def validate_source(source_type: SourceType | None, source: str | None) -> None:
    if (source_type is None) != (source is None):
        raise ValueError("video_source_type and video_source must be provided together")
    if source_type is None or source is None:
        return
    if len(source) > 2048:
        raise ValueError("video_source is too long")
    if source_type is SourceType.UPLOAD:
        if not _UPLOAD_RE.match(source):
            raise ValueError("uploaded video reference is invalid; upload the file first")
        return
    if not source.lower().startswith(_SCHEMES[source_type]):
        allowed = " or ".join(_SCHEMES[source_type])
        raise ValueError(f"{source_type.value.upper()} source must start with {allowed}")


class _SourceFields(BaseModel):
    video_source_type: SourceType | None = None
    video_source: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] | None = None


class MatchCreate(_SourceFields):
    model_config = ConfigDict(extra="forbid")

    sport: Sport = Sport.FOOTBALL
    name: Name
    home_team: Team
    away_team: Team
    competition: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    match_date: datetime
    # Unset processing options fall back to the defaults on the Settings page.
    processing_fps: ProcessingFps | None = None
    detection_model: DetectionModel | None = None
    model_name: ModelName | None = None
    confidence_threshold: Confidence | None = None
    enable_event_detection: bool | None = None
    enable_player_tracking: bool | None = None
    enable_pitch_mapping: bool | None = None
    kickoff_offset_seconds: KickoffOffset = 0.0
    external_ref: ExternalRef | None = None

    @model_validator(mode="after")
    def _check_source(self) -> MatchCreate:
        validate_source(self.video_source_type, self.video_source)
        return self


class MatchUpdate(_SourceFields):
    model_config = ConfigDict(extra="forbid")

    sport: Sport | None = None
    name: Name | None = None
    home_team: Team | None = None
    away_team: Team | None = None
    competition: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    match_date: datetime | None = None
    processing_fps: ProcessingFps | None = None
    detection_model: DetectionModel | None = None
    model_name: ModelName | None = None
    confidence_threshold: Confidence | None = None
    enable_event_detection: bool | None = None
    enable_player_tracking: bool | None = None
    enable_pitch_mapping: bool | None = None
    kickoff_offset_seconds: KickoffOffset | None = None
    external_ref: ExternalRef | None = None

    @model_validator(mode="after")
    def _check_source(self) -> MatchUpdate:
        fields = self.model_fields_set
        if "video_source_type" in fields or "video_source" in fields:
            validate_source(self.video_source_type, self.video_source)
        return self


class LiveMetrics(BaseModel):
    inference_fps: float | None = None
    latency_ms: float | None = None
    frames_processed: int | None = None
    device: str | None = None


class MatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sport: Sport
    name: str
    home_team: str
    away_team: str
    competition: str | None
    match_date: datetime
    video_source_type: SourceType | None
    video_source: str | None
    status: MatchStatus
    status_message: str | None
    last_error: str | None
    processing_fps: int
    detection_model: DetectionModel
    model_name: str
    confidence_threshold: float
    enable_event_detection: bool
    enable_player_tracking: bool
    enable_pitch_mapping: bool
    kickoff_offset_seconds: float
    external_ref: str | None = None
    current_session_id: str | None
    event_count: int
    created_at: datetime
    updated_at: datetime
    live: LiveMetrics | None = None
