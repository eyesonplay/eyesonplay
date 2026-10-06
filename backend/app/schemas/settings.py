from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.db.models import DetectionModel
from app.schemas.match import Confidence, ModelName, ProcessingFps


class AppSettingsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_processing_fps: ProcessingFps
    default_detection_model: DetectionModel
    default_model_name: ModelName
    default_confidence_threshold: Confidence
    default_enable_event_detection: bool
    default_enable_player_tracking: bool
    default_enable_pitch_mapping: bool


class AppSettingsOut(AppSettingsIn):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    updated_at: datetime
