import asyncio
import json

import fakeredis.aioredis
import pytest

from worker.control.command_consumer import _handle
from worker.control.commands import EVENTS_STREAM, STATUS_STREAM, ControlSignal, StartCommand, control_key
from worker.control.match_runner import MatchRunner
from worker.control.runner_registry import RunnerRegistry
from worker.publish.gpu import GpuMonitor


@pytest.fixture
async def redis():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


async def set_control(redis, match_id, session_id, state):
    await redis.set(control_key(match_id), ControlSignal(session_id=session_id, state=state).model_dump_json())


async def statuses(redis):
    entries = await redis.xrange(STATUS_STREAM)
    return [json.loads(f["payload"])["data"]["status"] for _, f in entries]


async def test_runner_processes_pauses_and_stops(redis, settings, match_config):
    cmd = StartCommand(command="start", match_id="m1", session_id="s1", config=match_config)
    await set_control(redis, "m1", "s1", "running")
    runner = MatchRunner(cmd, redis, settings, "cpu", GpuMonitor())

    task = asyncio.create_task(runner.run())
    await asyncio.sleep(1.2)
    await set_control(redis, "m1", "s1", "paused")
    await asyncio.sleep(0.3)
    await set_control(redis, "m1", "s1", "running")
    await asyncio.sleep(0.3)
    await set_control(redis, "m1", "s1", "stopped")
    await asyncio.wait_for(task, 5)

    assert await statuses(redis) == ["starting", "processing", "paused", "processing", "stopped"]
    assert await redis.xlen(EVENTS_STREAM) > 0
    assert await redis.get("match:m1:frame:last") is not None
    assert await redis.get("match:m1:metrics:last") is not None
    assert await redis.get("match:m1:lease") is None


async def test_runner_exits_when_superseded_by_restart(redis, settings, match_config):
    cmd = StartCommand(command="start", match_id="m1", session_id="s1", config=match_config)
    await set_control(redis, "m1", "s1", "running")
    task = asyncio.create_task(MatchRunner(cmd, redis, settings, "cpu", GpuMonitor()).run())
    await asyncio.sleep(0.4)
    await set_control(redis, "m1", "s2", "running")
    await asyncio.wait_for(task, 5)

    assert (await statuses(redis))[-1] == "stopped"


async def test_runner_fails_with_clear_message_on_bad_upload(redis, settings, match_config):
    cfg = match_config.model_copy(update={"source_type": "upload", "source": "../../etc/passwd"})
    settings = settings.model_copy(update={"inference_mode": "real"})
    cmd = StartCommand(command="start", match_id="m1", session_id="s1", config=cfg)
    await set_control(redis, "m1", "s1", "running")

    await MatchRunner(cmd, redis, settings, "cpu", GpuMonitor()).run()

    entries = await redis.xrange(STATUS_STREAM)
    last = json.loads(entries[-1][1]["payload"])["data"]
    assert last["status"] == "failed"
    assert last["message"]


async def test_consumer_ignores_stale_and_invalid_commands(redis, match_config):
    started = []

    class FakeRegistry:
        async def start(self, cmd):
            started.append(cmd.session_id)

    cmd = StartCommand(command="start", match_id="m1", session_id="old", config=match_config)
    await set_control(redis, "m1", "new", "running")
    await _handle(redis, FakeRegistry(), {"payload": cmd.model_dump_json()})
    await _handle(redis, FakeRegistry(), {"payload": "{not json"})
    current = cmd.model_copy(update={"session_id": "new"})
    await _handle(redis, FakeRegistry(), {"payload": current.model_dump_json()})

    assert started == ["new"]


async def test_registry_capacity_and_shutdown(redis, settings, match_config):
    registry = RunnerRegistry(1, lambda c: MatchRunner(c, redis, settings, "cpu", GpuMonitor()))
    await set_control(redis, "m1", "s1", "running")
    await registry.start(StartCommand(command="start", match_id="m1", session_id="s1", config=match_config))

    assert not registry.has_capacity
    assert registry.active_matches == ["m1"]
    await asyncio.sleep(0.5)  # let the runner start before the worker shuts down
    await registry.shutdown()
    assert (await statuses(redis))[-1] == "failed"
