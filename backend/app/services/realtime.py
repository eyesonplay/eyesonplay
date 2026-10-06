"""Helpers for the live channels: API-originated status messages and the
latest worker metrics for matches."""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.logging import get_logger
from app.core.redis_keys import channel
from app.db.models import Match
from app.schemas.match import LiveMetrics

log = get_logger(component="realtime")


def envelope(kind: str, match_id: str, data: Any, session_id: str | None = None) -> str:
    return json.dumps(
        {"type": kind, "match_id": match_id, "session_id": session_id, "ts": round(time.time(), 3), "seq": 0, "data": data},
        separators=(",", ":"),
        default=str,
    )


async def publish_match_status(redis: Redis, match: Match) -> None:
    """Tell live dashboards about a status change made by the API itself."""
    data = {
        "status": match.status.value,
        "message": match.status_message,
        "error": match.last_error,
        "origin": "api",
    }
    try:
        await redis.publish(channel(match.id, "status"), envelope("status", match.id, data, match.current_session_id))
    except RedisError as exc:
        log.warning("status publish failed", match_id=match.id, error=str(exc))


async def latest_metrics(redis: Redis, match_ids: Sequence[str]) -> dict[str, dict[str, Any]]:
    if not match_ids:
        return {}
    try:
        raw = await redis.mget([channel(mid, "metrics:last") for mid in match_ids])
    except RedisError as exc:
        log.warning("metrics lookup failed", error=str(exc))
        return {}
    result = {}
    for mid, value in zip(match_ids, raw, strict=True):
        if value:
            result[mid] = json.loads(value).get("data", {})
    return result


def to_live(metrics: dict[str, Any] | None) -> LiveMetrics | None:
    if not metrics:
        return None
    return LiveMetrics(
        inference_fps=metrics.get("inference_fps"),
        latency_ms=metrics.get("latency_ms"),
        frames_processed=metrics.get("frames_processed"),
        device=metrics.get("device"),
    )
