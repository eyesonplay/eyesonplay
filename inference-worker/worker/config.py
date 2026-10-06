"""Worker settings, read from environment variables."""

from __future__ import annotations

import socket
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    inference_mode: Literal["mock", "real"] = "mock"
    redis_url: str = "redis://localhost:6379/0"
    worker_id: str = Field(default_factory=socket.gethostname)
    max_concurrent_matches: int = Field(default=4, ge=1, le=64)
    log_level: str = "INFO"

    media_dir: Path = Path("/data/media")
    models_dir: Path = Path("/data/models")
    default_yolo_weights: str = "yolov8n.pt"
    # 32-keypoint pitch model (Roboflow `sports` layout) for automatic calibration.
    pitch_model_weights: str = "football-pitch-detection.pt"

    heartbeat_interval_s: float = 2.0
    heartbeat_ttl_s: int = 10
    lease_ttl_s: int = 8
    metrics_interval_s: float = 1.0
    control_poll_interval_s: float = 0.25

    source_reconnect_attempts: int = Field(default=8, ge=0)
    source_reconnect_base_delay_s: float = 1.0
    source_read_timeout_s: float = 15.0
    # Stream URLs resolving to private/loopback/link-local addresses are refused
    # (SSRF protection). Enable only for trusted local development.
    allow_private_sources: bool = False

    mock_width: int = 1280
    mock_height: int = 720
    mock_seed: int | None = None


@lru_cache
def get_settings() -> WorkerSettings:
    return WorkerSettings()
