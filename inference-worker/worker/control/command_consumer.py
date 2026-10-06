"""Consumes start commands from the shared Redis stream (consumer group).

Each command is delivered to exactly one worker; a worker only reads when it
has spare capacity, which spreads matches across worker replicas.
"""

from __future__ import annotations

import asyncio

from pydantic import ValidationError
from redis.asyncio import Redis
from redis.exceptions import RedisError, ResponseError

from worker.config import WorkerSettings
from worker.control.commands import COMMANDS_GROUP, COMMANDS_STREAM, ControlSignal, StartCommand, control_key
from worker.control.runner_registry import RunnerRegistry
from worker.logging import get_logger

log = get_logger(component="command_consumer")


async def ensure_group(redis: Redis) -> None:
    try:
        await redis.xgroup_create(COMMANDS_STREAM, COMMANDS_GROUP, id="$", mkstream=True)
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


async def consume_commands(redis: Redis, settings: WorkerSettings, registry: RunnerRegistry, stop: asyncio.Event) -> None:
    backoff = 1.0
    group_ready = False
    while not stop.is_set():
        if not registry.has_capacity:
            await asyncio.sleep(0.5)
            continue
        try:
            if not group_ready:
                await ensure_group(redis)
                group_ready = True
            response = await redis.xreadgroup(
                COMMANDS_GROUP, settings.worker_id, {COMMANDS_STREAM: ">"}, count=1, block=2000
            )
            backoff = 1.0
        except ResponseError as exc:
            if "NOGROUP" in str(exc):
                group_ready = False
                continue
            raise
        except RedisError as exc:
            log.warning("redis unavailable; retrying", error=str(exc), retry_in_s=backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 15.0)
            continue
        for _stream, messages in response or []:
            for message_id, fields in messages:
                try:
                    await _handle(redis, registry, fields or {})
                    await redis.xack(COMMANDS_STREAM, COMMANDS_GROUP, message_id)
                except RedisError as exc:
                    # Left pending; a transient outage must never stop the worker.
                    log.warning("command handling failed; will retry", error=str(exc))
                    await asyncio.sleep(backoff)
                except Exception:  # noqa: BLE001 - one bad command must not kill the consumer
                    log.exception("command handling crashed; command dropped")
                    await redis.xack(COMMANDS_STREAM, COMMANDS_GROUP, message_id)


async def _handle(redis: Redis, registry: RunnerRegistry, fields: dict[str, str]) -> None:
    try:
        cmd = StartCommand.model_validate_json(fields.get("payload", ""))
    except ValidationError as exc:
        log.error("invalid command rejected", error=str(exc)[:500])
        return
    raw = await redis.get(control_key(cmd.match_id))
    try:
        control = ControlSignal.model_validate_json(raw) if raw else None
    except ValidationError:
        control = None
    if control is None or control.session_id != cmd.session_id or control.state == "stopped":
        log.info("stale start command ignored", match_id=cmd.match_id, session_id=cmd.session_id)
        return
    log.info("start command accepted", match_id=cmd.match_id, session_id=cmd.session_id)
    await registry.start(cmd)
