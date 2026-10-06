"""Allowed processing actions per match status, and worker -> match status mapping."""

from __future__ import annotations

from enum import StrEnum

from app.core.errors import ConflictError
from app.db.models import Match, MatchStatus

S = MatchStatus


class Action(StrEnum):
    START = "start"
    PAUSE = "pause"
    STOP = "stop"
    RESTART = "restart"


ALLOWED: dict[Action, frozenset[MatchStatus]] = {
    Action.START: frozenset({S.READY, S.COMPLETED, S.FAILED, S.PAUSED}),  # PAUSED -> resume
    Action.PAUSE: frozenset({S.STARTING, S.PROCESSING}),
    Action.STOP: frozenset({S.STARTING, S.PROCESSING, S.PAUSED}),
    Action.RESTART: frozenset({S.STARTING, S.PROCESSING, S.PAUSED, S.COMPLETED, S.FAILED}),
}

ACTIVE_STATUSES = frozenset({S.STARTING, S.PROCESSING, S.PAUSED})

# Worker session status -> match status.
WORKER_STATUS_MAP: dict[str, MatchStatus] = {
    "starting": S.STARTING,
    "processing": S.PROCESSING,
    "reconnecting": S.PROCESSING,
    "paused": S.PAUSED,
    "completed": S.COMPLETED,
    "stopped": S.COMPLETED,
    "failed": S.FAILED,
}
TERMINAL_WORKER_STATUSES = frozenset({"completed", "stopped", "failed"})
# Which desired control state a non-terminal worker status must agree with.
EXPECTED_CONTROL = {"starting": "running", "processing": "running", "reconnecting": "running", "paused": "paused"}


def ensure_allowed(match: Match, action: Action) -> None:
    if action in (Action.START, Action.RESTART) and not match.video_source:
        raise ConflictError("Add a video source before starting processing")
    if match.status not in ALLOWED[action]:
        raise ConflictError(f"Cannot {action.value} a match that is {match.status.value}")


def idle_status(match: Match) -> MatchStatus:
    return S.READY if match.video_source else S.DRAFT
