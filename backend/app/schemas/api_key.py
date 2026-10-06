"""API key and integration feed schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.db.models import MatchStatus, Sport


class ApiKeyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class ApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    prefix: str
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class ApiKeyCreated(ApiKeyOut):
    """Returned once, on creation: the only time the full key is shown."""

    key: str


class FeedMatchOut(BaseModel):
    """What another app needs to link a match: no video source or processing settings."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    sport: Sport
    name: str
    home_team: str
    away_team: str
    competition: str | None
    match_date: datetime
    status: MatchStatus
    external_ref: str | None
    kickoff_offset_seconds: float
