"""Worker heartbeats, GPU metrics and model inventory from Redis."""

from __future__ import annotations

import json
from typing import Any

from redis.asyncio import Redis

from app.core.redis_keys import HEARTBEAT_PATTERN
from app.schemas.system import GpuOut, ModelOut, WorkerOut


async def list_workers(redis: Redis) -> list[WorkerOut]:
    keys = [key async for key in redis.scan_iter(match=HEARTBEAT_PATTERN, count=100)]
    if not keys:
        return []
    workers = []
    for raw in await redis.mget(keys):
        if not raw:
            continue
        hb: dict[str, Any] = json.loads(raw)
        workers.append(
            WorkerOut(
                worker_id=hb["worker_id"],
                mode=hb.get("mode", "unknown"),
                device=hb.get("device", "unknown"),
                active_matches=hb.get("active_matches", []),
                capacity=hb.get("capacity", 0),
                started_at=hb.get("started_at", 0.0),
                last_seen=hb.get("ts", 0.0),
                gpu=hb.get("gpu"),
                models=hb.get("models", []),
            )
        )
    return sorted(workers, key=lambda w: w.worker_id)


def gpus(workers: list[WorkerOut]) -> list[GpuOut]:
    result = []
    for worker in workers:
        for g in worker.gpu or []:
            result.append(GpuOut(worker_id=worker.worker_id, **{k: g.get(k) for k in GpuOut.model_fields if k != "worker_id"}))
    return result


def models(workers: list[WorkerOut]) -> list[ModelOut]:
    return [
        ModelOut(
            name=m.get("name", "unknown"),
            family=m.get("family", "unknown"),
            description=m.get("description"),
            device=m.get("device", worker.device),
            loaded=bool(m.get("loaded")),
            worker_id=worker.worker_id,
            classes=m.get("classes"),
        )
        for worker in workers
        for m in worker.models
    ]
