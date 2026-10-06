"""Tracks the match sessions running in this worker process."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable

from worker.control.commands import StartCommand
from worker.control.match_runner import MatchRunner
from worker.logging import get_logger

log = get_logger(component="runner_registry")

SUPERSEDE_GRACE_S = 5.0


class RunnerRegistry:
    def __init__(self, max_concurrent: int, factory: Callable[[StartCommand], MatchRunner]) -> None:
        self._max = max_concurrent
        self._factory = factory
        self._tasks: dict[str, asyncio.Task[None]] = {}

    @property
    def has_capacity(self) -> bool:
        return len(self._tasks) < self._max

    @property
    def active_matches(self) -> list[str]:
        return list(self._tasks)

    @property
    def capacity(self) -> int:
        return self._max

    async def start(self, cmd: StartCommand) -> None:
        previous = self._tasks.get(cmd.match_id)
        if previous is not None:
            # A restart: the old runner notices the new session id and exits.
            with contextlib.suppress(TimeoutError, asyncio.CancelledError):
                await asyncio.wait_for(asyncio.shield(previous), SUPERSEDE_GRACE_S)
            if not previous.done():
                previous.cancel()
        runner = self._factory(cmd)
        task = asyncio.create_task(runner.run(), name=f"match:{cmd.match_id}")
        self._tasks[cmd.match_id] = task
        task.add_done_callback(lambda t, mid=cmd.match_id: self._on_done(mid, t))

    def _on_done(self, match_id: str, task: asyncio.Task[None]) -> None:
        if self._tasks.get(match_id) is task:
            del self._tasks[match_id]
        if not task.cancelled() and task.exception() is not None:
            log.error("runner task crashed", match_id=match_id, error=repr(task.exception()))

    async def shutdown(self) -> None:
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
