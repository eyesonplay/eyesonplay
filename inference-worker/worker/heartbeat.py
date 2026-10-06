"""Worker heartbeat: liveness, device, GPU metrics, models and active matches."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

from worker.config import WorkerSettings
from worker.control.runner_registry import RunnerRegistry
from worker.detect.registry import DETECTOR_FAMILIES
from worker.logging import get_logger
from worker.publish.gpu import GpuMonitor

log = get_logger(component="heartbeat")


def heartbeat_key(worker_id: str) -> str:
    return f"worker:{worker_id}:heartbeat"


def models_info(settings: WorkerSettings, device: str) -> list[dict[str, Any]]:
    if settings.inference_mode == "mock":
        return [
            {
                "name": "mock-detector",
                "family": "mock",
                "description": DETECTOR_FAMILIES["mock"],
                "device": "cpu",
                "loaded": True,
                "classes": ["ball", "player", "goalkeeper", "referee"],
            }
        ]
    from worker.detect.yolo_detector import loaded_models

    loaded = loaded_models()
    models = [
        {"name": m["weights"], "family": "yolo", "description": DETECTOR_FAMILIES["yolo"], "device": m["device"], "loaded": True}
        for m in loaded
    ]
    if not any(m["weights"].startswith(settings.default_yolo_weights.removesuffix(".pt")) for m in loaded):
        models.append(
            {"name": settings.default_yolo_weights, "family": "yolo", "description": DETECTOR_FAMILIES["yolo"], "device": device, "loaded": False}
        )
    return models


async def heartbeat_loop(
    redis: Redis,
    settings: WorkerSettings,
    registry: RunnerRegistry,
    device: str,
    gpu: GpuMonitor,
    stop: asyncio.Event,
) -> None:
    started_at = time.time()
    while not stop.is_set():
        payload = {
            "worker_id": settings.worker_id,
            "mode": settings.inference_mode,
            "device": device,
            "gpu": gpu.read(),
            "models": models_info(settings, device),
            "active_matches": registry.active_matches,
            "capacity": registry.capacity,
            "started_at": started_at,
            "ts": time.time(),
        }
        try:
            await redis.set(heartbeat_key(settings.worker_id), json.dumps(payload), ex=settings.heartbeat_ttl_s)
        except RedisError as exc:
            log.warning("heartbeat failed", error=str(exc))
        try:
            await asyncio.wait_for(stop.wait(), settings.heartbeat_interval_s)
        except TimeoutError:
            pass
