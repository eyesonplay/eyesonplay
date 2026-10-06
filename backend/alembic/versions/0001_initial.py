"""initial schema: matches, events, processing_sessions, app_settings

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

MATCH_STATUS = ("draft", "ready", "starting", "processing", "paused", "completed", "failed")
SOURCE_TYPE = ("hls", "rtmp", "url", "upload")
DETECTION_MODEL = ("ball", "ball_players", "ball_players_pitch")


def _enum(values: tuple[str, ...], name: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, length=32)


def upgrade() -> None:
    op.create_table(
        "matches",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("home_team", sa.String(120), nullable=False),
        sa.Column("away_team", sa.String(120), nullable=False),
        sa.Column("competition", sa.String(120)),
        sa.Column("match_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("video_source_type", _enum(SOURCE_TYPE, "source_type")),
        sa.Column("video_source", sa.Text),
        sa.Column("status", _enum(MATCH_STATUS, "match_status"), nullable=False),
        sa.Column("status_message", sa.Text),
        sa.Column("last_error", sa.Text),
        sa.Column("processing_fps", sa.Integer, nullable=False),
        sa.Column("detection_model", _enum(DETECTION_MODEL, "detection_model"), nullable=False),
        sa.Column("model_name", sa.String(120), nullable=False),
        sa.Column("confidence_threshold", sa.Float, nullable=False),
        sa.Column("enable_event_detection", sa.Boolean, nullable=False),
        sa.Column("enable_player_tracking", sa.Boolean, nullable=False),
        sa.Column("enable_pitch_mapping", sa.Boolean, nullable=False),
        sa.Column("kickoff_offset_seconds", sa.Float, nullable=False, server_default="0"),
        sa.Column("current_session_id", sa.String(40)),
        sa.Column("event_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_matches_status", "matches", ["status"])
    op.create_index("ix_matches_updated_at", "matches", ["updated_at"])

    op.create_table(
        "events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("event_uid", sa.String(40), nullable=False),
        sa.Column("match_id", sa.String(40), sa.ForeignKey("matches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.String(40)),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("video_timestamp", sa.Float, nullable=False),
        sa.Column("match_clock", sa.String(16), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("match_id", "event_uid", name="uq_events_match_event_uid"),
    )
    op.create_index("ix_events_match_video_ts", "events", ["match_id", "video_timestamp"])
    op.create_index("ix_events_match_type", "events", ["match_id", "event_type"])
    op.create_index("ix_events_created_at", "events", ["created_at"])

    op.create_table(
        "processing_sessions",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("match_id", sa.String(40), sa.ForeignKey("matches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stopped_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("frames_processed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("average_fps", sa.Float),
        sa.Column("average_latency", sa.Float),
        sa.Column("worker_id", sa.String(120)),
        sa.Column("device", sa.String(32)),
        sa.Column("error", sa.Text),
    )
    op.create_index("ix_processing_sessions_match_id", "processing_sessions", ["match_id"])

    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("default_processing_fps", sa.Integer, nullable=False),
        sa.Column("default_detection_model", _enum(DETECTION_MODEL, "detection_model"), nullable=False),
        sa.Column("default_model_name", sa.String(120), nullable=False),
        sa.Column("default_confidence_threshold", sa.Float, nullable=False),
        sa.Column("default_enable_event_detection", sa.Boolean, nullable=False),
        sa.Column("default_enable_player_tracking", sa.Boolean, nullable=False),
        sa.Column("default_enable_pitch_mapping", sa.Boolean, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("app_settings")
    op.drop_table("processing_sessions")
    op.drop_table("events")
    op.drop_table("matches")
