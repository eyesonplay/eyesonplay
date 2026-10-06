"""Redis contract shared with the inference worker (docs/redis-contract.md)."""

from __future__ import annotations

COMMANDS_STREAM = "worker:commands"
STATUS_STREAM = "status:updates"
EVENTS_STREAM = "events:stream"
STATUS_GROUP = "api-status"
EVENTS_GROUP = "api-persist"
HEARTBEAT_PATTERN = "worker:*:heartbeat"

LIVE_CHANNELS = ("events", "detections", "metrics", "status")


def control_key(match_id: str) -> str:
    return f"match:{match_id}:control"


def lease_key(match_id: str) -> str:
    return f"match:{match_id}:lease"


def channel(match_id: str, kind: str) -> str:
    return f"match:{match_id}:{kind}"
