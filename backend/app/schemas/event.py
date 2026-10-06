from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

# UI filter groups -> concrete event types.
EVENT_GROUPS: dict[str, tuple[str, ...]] = {
    "ball": ("ball_detected", "ball_lost", "ball_move"),
    "pass": ("pass", "pass_candidate"),
    "shot": ("shot", "shot_candidate"),
    "possession": ("possession", "possession_change"),
    "out": ("ball_out",),
    "corner": ("corner",),
    "goal": ("goal", "goal_candidate"),
    # tennis
    "serve": ("serve", "fault", "double_fault"),
    "hit": ("hit",),
    "bounce": ("bounce",),
    "point": ("point_won",),
}


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_uid: str
    match_id: str
    session_id: str | None
    event_type: str
    video_timestamp: float
    match_clock: str
    confidence: float
    payload: dict[str, Any]
    created_at: datetime


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    match_id: str
    started_at: datetime
    stopped_at: datetime | None
    status: str
    frames_processed: int
    average_fps: float | None
    average_latency: float | None
    worker_id: str | None
    device: str | None
    error: str | None
