"""Reliable Redis stream consumption with consumer groups.

Pending (delivered but unacknowledged) entries are re-processed first, and a
batch is only acknowledged after its handler succeeded, so a crash or a
database outage never loses events or status updates.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError, ResponseError

from app.core.logging import get_logger

Message = tuple[str, dict[str, str]]
Handler = Callable[[list[Message]], Awaitable[None]]


async def ensure_group(redis: Redis, stream: str, group: str) -> None:
    try:
        await redis.xgroup_create(stream, group, id="0", mkstream=True)
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


def parse_envelope(fields: dict[str, str] | None) -> dict[str, Any] | None:
    if not fields:  # entries trimmed by MAXLEN while pending come back empty
        return None
    try:
        env = json.loads(fields.get("payload", ""))
    except json.JSONDecodeError:
        return None
    if not isinstance(env, dict) or not isinstance(env.get("data"), dict) or not env.get("match_id"):
        return None
    return env


async def consume_stream(
    redis: Redis,
    stream: str,
    group: str,
    consumer: str,
    handler: Handler,
    stop: asyncio.Event,
    batch_size: int = 200,
    block_ms: int = 1000,
) -> None:
    log = get_logger(component="stream_consumer", stream=stream, group=group)
    backoff, group_ready, pending_done = 1.0, False, False
    while not stop.is_set():
        try:
            if not group_ready:
                await ensure_group(redis, stream, group)
                group_ready = True
            read_id = ">" if pending_done else "0"
            response = await redis.xreadgroup(
                group, consumer, {stream: read_id}, count=batch_size, block=block_ms if pending_done else None
            )
            messages: list[Message] = response[0][1] if response else []
            if not messages:
                pending_done = True
                continue
            await handler(messages)
            await redis.xack(stream, group, *[message_id for message_id, _ in messages])
            backoff = 1.0
        except ResponseError as exc:
            if "NOGROUP" in str(exc):
                group_ready = False
                continue
            log.error("redis response error", error=str(exc))
            await _sleep(stop, backoff)
        except RedisError as exc:
            log.warning("redis unavailable; retrying", error=str(exc), retry_in_s=backoff)
            await _sleep(stop, backoff)
            backoff = min(backoff * 2, 15.0)
        except Exception:  # noqa: BLE001 - handler failure: keep entries pending and retry
            log.exception("batch handler failed; will retry pending entries")
            pending_done = False
            await _sleep(stop, backoff)
            backoff = min(backoff * 2, 15.0)


async def _sleep(stop: asyncio.Event, seconds: float) -> None:
    try:
        await asyncio.wait_for(stop.wait(), seconds)
    except TimeoutError:
        pass
