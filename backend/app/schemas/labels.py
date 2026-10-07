"""Label schemas: one hand-marked event per entry, in the benchmark's format."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_LABELS = 20000
_SCALARS = (str, int, float, bool, type(None))


class LabelEvent(BaseModel):
    """`t` (video seconds) and `event`, plus details such as `in`, `player`, `team`."""

    model_config = ConfigDict(extra="allow")

    t: float = Field(ge=0, le=24 * 3600)
    event: str = Field(min_length=1, max_length=40, pattern=r"^[a-z][a-z_]*$")

    @model_validator(mode="after")
    def details_are_plain_values(self) -> LabelEvent:
        for key, value in (self.model_extra or {}).items():
            if len(key) > 40 or not isinstance(value, _SCALARS):
                raise ValueError(f"label detail '{key}' must be a short name with a plain value")
        return self


class LabelsIn(BaseModel):
    events: list[LabelEvent] = Field(max_length=MAX_LABELS)
    labelled_until_s: float | None = Field(default=None, ge=0, le=24 * 3600)


class LabelsOut(BaseModel):
    events: list[dict[str, Any]]
    labelled_until_s: float | None
    updated_at: datetime | None
