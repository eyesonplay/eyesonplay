"""ORM models: Match, Event, ProcessingSession, AppSettings, ApiKey."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BigIntPk, JsonType


def utcnow() -> datetime:
    return datetime.now(UTC)


class MatchStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    STARTING = "starting"
    PROCESSING = "processing"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class Sport(StrEnum):
    FOOTBALL = "football"
    TENNIS = "tennis"


class SourceType(StrEnum):
    HLS = "hls"
    RTMP = "rtmp"
    URL = "url"
    UPLOAD = "upload"


class DetectionModel(StrEnum):
    BALL = "ball"
    BALL_PLAYERS = "ball_players"
    BALL_PLAYERS_PITCH = "ball_players_pitch"


def _enum(cls: type[StrEnum], name: str) -> Enum:
    return Enum(cls, name=name, native_enum=False, values_callable=lambda e: [m.value for m in e], length=32)


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    sport: Mapped[Sport] = mapped_column(_enum(Sport, "sport"), default=Sport.FOOTBALL, server_default="football")
    home_team: Mapped[str] = mapped_column(String(120))
    away_team: Mapped[str] = mapped_column(String(120))
    competition: Mapped[str | None] = mapped_column(String(120))
    match_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    video_source_type: Mapped[SourceType | None] = mapped_column(_enum(SourceType, "source_type"))
    video_source: Mapped[str | None] = mapped_column(Text)
    status: Mapped[MatchStatus] = mapped_column(_enum(MatchStatus, "match_status"), index=True)
    status_message: Mapped[str | None] = mapped_column(Text)
    last_error: Mapped[str | None] = mapped_column(Text)
    processing_fps: Mapped[int] = mapped_column(Integer)
    detection_model: Mapped[DetectionModel] = mapped_column(_enum(DetectionModel, "detection_model"))
    model_name: Mapped[str] = mapped_column(String(120))
    confidence_threshold: Mapped[float] = mapped_column(Float)
    enable_event_detection: Mapped[bool] = mapped_column(Boolean, default=True)
    enable_player_tracking: Mapped[bool] = mapped_column(Boolean, default=True)
    enable_pitch_mapping: Mapped[bool] = mapped_column(Boolean, default=True)
    kickoff_offset_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    # The same match in another app (e.g. "riosport:1557417"), for integrations.
    external_ref: Mapped[str | None] = mapped_column(String(80), index=True)
    current_session_id: Mapped[str | None] = mapped_column(String(40))
    event_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, index=True)


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("match_id", "event_uid", name="uq_events_match_event_uid"),
        Index("ix_events_match_video_ts", "match_id", "video_timestamp"),
        Index("ix_events_match_type", "match_id", "event_type"),
    )

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    event_uid: Mapped[str] = mapped_column(String(40))
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"))
    session_id: Mapped[str | None] = mapped_column(String(40))
    event_type: Mapped[str] = mapped_column(String(40))
    video_timestamp: Mapped[float] = mapped_column(Float)
    match_clock: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[float] = mapped_column(Float)
    payload: Mapped[dict[str, Any]] = mapped_column(JsonType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class ProcessingSession(Base):
    __tablename__ = "processing_sessions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32))
    frames_processed: Mapped[int] = mapped_column(Integer, default=0)
    average_fps: Mapped[float | None] = mapped_column(Float)
    average_latency: Mapped[float | None] = mapped_column(Float)  # milliseconds
    worker_id: Mapped[str | None] = mapped_column(String(120))
    device: Mapped[str | None] = mapped_column(String(32))
    error: Mapped[str | None] = mapped_column(Text)


class AppSettings(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    default_processing_fps: Mapped[int] = mapped_column(Integer, default=10)
    default_detection_model: Mapped[DetectionModel] = mapped_column(
        _enum(DetectionModel, "detection_model"), default=DetectionModel.BALL_PLAYERS_PITCH
    )
    default_model_name: Mapped[str] = mapped_column(String(120), default="yolov8n")
    default_confidence_threshold: Mapped[float] = mapped_column(Float, default=0.5)
    default_enable_event_detection: Mapped[bool] = mapped_column(Boolean, default=True)
    default_enable_player_tracking: Mapped[bool] = mapped_column(Boolean, default=True)
    default_enable_pitch_mapping: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ApiKey(Base):
    """A key another app uses for the integration feed. Only its SHA-256 is stored."""

    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    prefix: Mapped[str] = mapped_column(String(16))
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class User(Base):
    """A dashboard user. Passwords are stored as Argon2 hashes only."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)  # stored lower-case
    password_hash: Mapped[str] = mapped_column(String(255))
    disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserSession(Base):
    """A login session. The browser holds the token; only its SHA-256 is stored."""

    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
