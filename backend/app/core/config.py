"""API settings from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from typing import Annotated

from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://football:football@localhost:5432/football"
    redis_url: str = "redis://localhost:6379/0"
    media_dir: Path = Path("/data/media")
    # Comma separated in the environment (NoDecode: not parsed as JSON).
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    log_level: str = "INFO"
    # Redis consumer name; keep it stable per replica (e.g. api-1, api-2) so
    # pending stream entries are re-read after a restart.
    instance_id: str = "api-1"

    max_upload_mb: int = Field(default=4096, ge=1)
    worker_start_timeout_s: float = 45.0
    watchdog_interval_s: float = 5.0
    lost_lease_checks: int = 2
    # Development only: create tables directly instead of running Alembic
    # (lets the API run on SQLite without Postgres).
    auto_create_schema: bool = False

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> object:
        if isinstance(value, str) and not value.startswith("["):
            return [v.strip() for v in value.split(",") if v.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
