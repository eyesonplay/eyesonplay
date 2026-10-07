"""Runs one match processing session from start to a terminal state."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Iterator
from enum import StrEnum

from redis.asyncio import Redis
from redis.exceptions import RedisError

from football_events import EngineConfig, EventEngine
from tennis_events import TennisConfig, TennisEventEngine
from worker.config import WorkerSettings
from worker.control.commands import MatchConfig, ControlSignal, StartCommand, control_key, lease_key
from worker.detect.base import ModelLoadError
from worker.detect.registry import Components, build_components
from worker.ingest.source import Frame, SourceError
from worker.logging import get_logger
from worker.pipeline import FramePipeline
from worker.publish.gpu import GpuMonitor
from worker.publish.metrics import SessionMetrics
from worker.publish.publisher import Publisher

MAX_CONSECUTIVE_REDIS_FAILURES = 30


class Outcome(StrEnum):
    COMPLETED = "completed"
    STOPPED = "stopped"
    SUPERSEDED = "superseded"


class MatchRunner:
    def __init__(self, cmd: StartCommand, redis: Redis, settings: WorkerSettings, device: str, gpu: GpuMonitor) -> None:
        self.cmd = cmd
        self._redis = redis
        self._settings = settings
        self._device = device
        self._gpu = gpu
        self._pub = Publisher(redis, cmd.match_id, cmd.session_id, settings.worker_id, device)
        self._log = get_logger(match_id=cmd.match_id, session_id=cmd.session_id)
        self._redis_failures = 0

    async def run(self) -> None:
        cfg = self.cmd.config
        self._log.info("session starting", source_type=cfg.source_type, fps=cfg.processing_fps, mode=self._settings.inference_mode)
        await self._pub.status("starting", "Loading model and opening video source")
        # The lease is refreshed by its own task so slow model loads, stalled
        # sources and reconnect backoff never look like a dead worker.
        lease_task = asyncio.create_task(self._keep_lease(), name=f"lease:{self.cmd.match_id}")
        try:
            await self._run_session()
        finally:
            lease_task.cancel()
            await asyncio.gather(lease_task, return_exceptions=True)
            await self._release_lease()

    async def _run_session(self) -> None:
        cfg = self.cmd.config
        loop = asyncio.get_running_loop()

        def on_reconnect(attempt: int, reason: str) -> None:
            message = f"Source disconnected; reconnect attempt {attempt}: {reason}"
            asyncio.run_coroutine_threadsafe(self._pub.status("reconnecting", message), loop)

        try:
            components = await asyncio.to_thread(build_components, cfg, self._settings, self._device, on_reconnect)
        except (ModelLoadError, SourceError, ValueError) as exc:
            await self._fail(str(exc))
            return

        metrics = SessionMetrics(source_fps=components.source.source_fps)
        try:
            outcome = await self._process(components, metrics)
        except SourceError as exc:
            await self._fail(str(exc), metrics)
            return
        except asyncio.CancelledError:
            await asyncio.shield(self._fail("Processing interrupted: worker shutting down", metrics))
            raise
        except Exception as exc:  # noqa: BLE001 - every failure must reach the UI
            self._log.exception("session crashed")
            await self._fail(f"Internal processing error: {type(exc).__name__}: {exc}", metrics)
            return
        finally:
            components.close()

        self._log.info("session finished", outcome=outcome.value, **metrics.session_stats())
        if outcome is Outcome.COMPLETED:
            await self._pub.status("completed", "Video source finished", metrics.session_stats())
        else:
            await self._pub.status("stopped", "Processing stopped", metrics.session_stats())

    async def _process(self, components: Components, metrics: SessionMetrics) -> Outcome:
        cfg = self.cmd.config
        engine = (
            _event_engine(self.cmd.match_id, cfg, self._settings, components.source.height)
            if cfg.enable_event_detection
            else None
        )
        pipeline = FramePipeline(cfg, components.detector, components.mapper, engine, components.scoreboard)
        frames: Iterator[Frame] = iter(components.source)
        control: ControlSignal | None = None
        last_control = last_metrics = 0.0
        paused, announced = False, False

        while True:
            now = time.monotonic()
            if now - last_control >= self._settings.control_poll_interval_s:
                control, last_control = await self._read_control(control), now
            if control is None or control.state == "stopped":
                return Outcome.STOPPED
            if control.session_id != self.cmd.session_id:
                return Outcome.SUPERSEDED

            if now - last_metrics >= self._settings.metrics_interval_s:
                last_metrics = now
                await self._guard(self._publish_metrics(metrics))

            if control.state == "paused":
                if not paused:
                    paused = True
                    await self._guard(self._pub.status("paused", "Processing paused"))
                if components.source.is_live:
                    await asyncio.to_thread(next, frames, None)  # keep draining the live stream
                else:
                    await asyncio.sleep(self._settings.control_poll_interval_s)
                continue

            frame = await asyncio.to_thread(next, frames, None)
            if frame is None:
                return Outcome.COMPLETED
            if paused or not announced:
                paused, announced = False, True
                await self._guard(self._pub.status("processing", f"Processing on {self._device}"))
            result = await asyncio.to_thread(pipeline.process, frame)
            if await self._guard(self._pub.frame(result)):
                metrics.record(result, time.time())

    async def _publish_metrics(self, metrics: SessionMetrics) -> None:
        await self._pub.metrics(metrics.snapshot(self._device, self._gpu.read()))

    async def _keep_lease(self) -> None:
        interval = max(0.5, self._settings.lease_ttl_s / 4)
        while True:
            try:
                await self._refresh_lease()
            except RedisError as exc:
                self._log.warning("lease refresh failed", error=str(exc))
            await asyncio.sleep(interval)

    async def _guard(self, operation: object) -> bool:
        """Await a Redis operation; tolerate short outages, abort on long ones."""
        try:
            await operation  # type: ignore[misc]
        except RedisError as exc:
            self._redis_failures += 1
            self._log.warning("redis publish failed", error=str(exc), consecutive=self._redis_failures)
            if self._redis_failures >= MAX_CONSECUTIVE_REDIS_FAILURES:
                raise
            await asyncio.sleep(min(2.0, 0.1 * self._redis_failures))
            return False
        self._redis_failures = 0
        return True

    async def _read_control(self, previous: ControlSignal | None) -> ControlSignal | None:
        try:
            raw = await self._redis.get(control_key(self.cmd.match_id))
        except RedisError as exc:
            self._log.warning("control read failed; keeping last state", error=str(exc))
            return previous
        return ControlSignal.model_validate_json(raw) if raw else None

    async def _refresh_lease(self) -> None:
        lease = json.dumps({"worker_id": self._settings.worker_id, "session_id": self.cmd.session_id})
        await self._redis.set(lease_key(self.cmd.match_id), lease, ex=self._settings.lease_ttl_s)

    async def _release_lease(self) -> None:
        try:
            raw = await self._redis.get(lease_key(self.cmd.match_id))
            if raw and json.loads(raw).get("session_id") == self.cmd.session_id:
                await self._redis.delete(lease_key(self.cmd.match_id))
        except RedisError as exc:
            self._log.warning("lease release failed", error=str(exc))

    async def _fail(self, message: str, metrics: SessionMetrics | None = None) -> None:
        self._log.error("session failed", reason=message)
        stats = metrics.session_stats() if metrics else None
        try:
            await self._pub.status("failed", message, stats)
            await self._pub.error(message)
        except RedisError as exc:
            self._log.error("could not publish failure", error=str(exc))


def _event_engine(
    match_id: str, cfg: MatchConfig, settings: WorkerSettings, frame_height: int
) -> EventEngine | TennisEventEngine:
    if cfg.sport == "tennis":
        bounce_model = None
        if settings.inference_mode == "real":
            from worker.detect.bounce_model import load_bounce_model

            bounce_model = load_bounce_model(settings.models_dir)  # learned bounces on real video
        learned = {"bounce_scorer": bounce_model.scorer, "bounce_probability": bounce_model.probability} if bounce_model else {}
        config = TennisConfig(
            kickoff_offset_seconds=cfg.kickoff_offset_seconds, frame_height_px=frame_height, **learned
        )
        return TennisEventEngine(match_id, config)
    return EventEngine(match_id, EngineConfig(kickoff_offset_seconds=cfg.kickoff_offset_seconds))
