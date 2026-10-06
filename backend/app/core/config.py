"""API settings from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
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

    # Dashboard login. The admin is created on startup if no user has this
    # email yet; an existing user's password is never overwritten.
    admin_email: str | None = None
    admin_password: SecretStr | None = None
    session_ttl_hours: int = Field(default=24 * 14, ge=1)
    # Send the session cookie over HTTPS only. Must be true in production.
    cookie_secure: bool = False
    login_max_failures: int = Field(default=5, ge=1)  # per email, per window
    login_max_attempts_per_ip: int = Field(default=20, ge=1)  # per window
    login_window_s: int = Field(default=15 * 60, ge=1)
    feed_requests_per_minute: int = Field(default=120, ge=1)  # per API key

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> object:
        if isinstance(value, str) and not value.startswith("["):
            return [v.strip() for v in value.split(",") if v.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
