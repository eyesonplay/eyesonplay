"""Worker entrypoint: `python -m worker.main`."""

from __future__ import annotations

import asyncio
import contextlib
import signal

from redis.asyncio import Redis
from redis.exceptions import RedisError

from worker.config import WorkerSettings, get_settings
from worker.control.command_consumer import consume_commands
from worker.control.commands import StartCommand
from worker.control.match_runner import MatchRunner
from worker.control.runner_registry import RunnerRegistry
from worker.device import select_device
from worker.heartbeat import heartbeat_key, heartbeat_loop
from worker.logging import configure_logging, get_logger
from worker.publish.gpu import GpuMonitor


async def wait_for_redis(redis: Redis, stop: asyncio.Event) -> None:
    log = get_logger(component="startup")
    delay = 1.0
    while not stop.is_set():
        try:
            await redis.ping()
            return
        except RedisError as exc:
            log.warning("waiting for redis", error=str(exc), retry_in_s=delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 15.0)


async def run(settings: WorkerSettings) -> None:
    log = get_logger(component="main", worker_id=settings.worker_id)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    redis = Redis.from_url(settings.redis_url, decode_responses=True, health_check_interval=15)
    await wait_for_redis(redis, stop)
    device = select_device(settings.inference_mode)
    gpu = GpuMonitor()
    log.info("worker started", mode=settings.inference_mode, device=device, gpu=gpu.available,
             capacity=settings.max_concurrent_matches)  # fmt: skip

    def factory(cmd: StartCommand) -> MatchRunner:
        return MatchRunner(cmd, redis, settings, device, gpu)

    registry = RunnerRegistry(settings.max_concurrent_matches, factory)
    tasks = [
        asyncio.create_task(consume_commands(redis, settings, registry, stop), name="consumer"),
        asyncio.create_task(heartbeat_loop(redis, settings, registry, device, gpu, stop), name="heartbeat"),
    ]
    stop_task = asyncio.create_task(stop.wait())
    done, _ = await asyncio.wait([*tasks, stop_task], return_when=asyncio.FIRST_COMPLETED)
    for task in done:
        if task is not stop_task and task.exception():
            log.error("worker task crashed", task=task.get_name(), error=repr(task.exception()))
    log.info("worker stopping", active=registry.active_matches)
    stop.set()
    await registry.shutdown()
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    with contextlib.suppress(RedisError):
        await redis.delete(heartbeat_key(settings.worker_id))
    await redis.aclose()


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    asyncio.run(run(settings))


if __name__ == "__main__":
    main()
