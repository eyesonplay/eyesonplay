import asyncio
import json

import fakeredis.aioredis

from worker.control.runner_registry import RunnerRegistry
from worker.device import select_device
from worker.heartbeat import heartbeat_key, heartbeat_loop, models_info
from worker.publish.gpu import GpuMonitor


def test_mock_mode_always_uses_cpu():
    assert select_device("mock") == "cpu"


def test_gpu_monitor_reports_nothing_without_nvidia():
    monitor = GpuMonitor()
    assert monitor.available is False
    assert monitor.read() is None


def test_models_info_mock(settings):
    models = models_info(settings, "cpu")
    assert models[0]["name"] == "mock-detector" and models[0]["loaded"] is True


async def test_heartbeat_publishes_worker_state(settings):
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    stop = asyncio.Event()
    registry = RunnerRegistry(3, lambda cmd: None)  # type: ignore[arg-type, return-value]
    task = asyncio.create_task(heartbeat_loop(redis, settings, registry, "cpu", GpuMonitor(), stop))
    await asyncio.sleep(0.1)
    stop.set()
    await asyncio.wait_for(task, 3)

    beat = json.loads(await redis.get(heartbeat_key(settings.worker_id)))
    assert beat["mode"] == "mock" and beat["capacity"] == 3 and beat["gpu"] is None
    assert await redis.ttl(heartbeat_key(settings.worker_id)) > 0
    await redis.aclose()
