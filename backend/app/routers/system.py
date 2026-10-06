from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MatchStatus
from app.deps import get_db, get_redis
from app.repositories.event_repo import EventRepository
from app.repositories.match_repo import MatchRepository
from app.schemas.common import Envelope, ok
from app.schemas.system import ComponentHealth, DashboardSummary, GpuOut, HealthOut, ModelOut, WorkerOut
from app.services.realtime import latest_metrics
from app.services.status_machine import ACTIVE_STATUSES
from app.services.system_service import gpus, list_workers, models

router = APIRouter(tags=["system"])
Db = Annotated[AsyncSession, Depends(get_db)]
RedisDep = Annotated[Redis, Depends(get_redis)]
CHECK_TIMEOUT_S = 2.0


@router.get("/api/system/live", include_in_schema=False)
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/system/health", response_model=Envelope[HealthOut])
async def health(db: Db, redis: RedisDep) -> Envelope[HealthOut]:
    database = await _check(db.execute(text("SELECT 1")))
    cache = await _check(redis.ping())
    workers = len(await list_workers(redis)) if cache.ok else 0
    status = "ok" if database.ok and cache.ok else "degraded"
    return ok(HealthOut(status=status, database=database, redis=cache, workers=workers))


async def _check(awaitable: object) -> ComponentHealth:
    try:
        await asyncio.wait_for(awaitable, CHECK_TIMEOUT_S)  # type: ignore[arg-type]
    except Exception as exc:  # noqa: BLE001 - health checks report failures, never raise
        return ComponentHealth(ok=False, detail=f"{type(exc).__name__}: {exc}"[:300])
    return ComponentHealth(ok=True)


@router.get("/api/system/workers", response_model=Envelope[list[WorkerOut]])
async def workers(redis: RedisDep) -> Envelope[list[WorkerOut]]:
    return ok(await list_workers(redis))


@router.get("/api/system/gpu", response_model=Envelope[list[GpuOut]])
async def gpu(redis: RedisDep) -> Envelope[list[GpuOut]]:
    """Empty list when no NVIDIA GPU is reported by any worker."""
    return ok(gpus(await list_workers(redis)))


@router.get("/api/models", response_model=Envelope[list[ModelOut]])
async def list_models(redis: RedisDep) -> Envelope[list[ModelOut]]:
    return ok(models(await list_workers(redis)))


@router.get("/api/dashboard/summary", response_model=Envelope[DashboardSummary])
async def summary(db: Db, redis: RedisDep) -> Envelope[DashboardSummary]:
    matches = MatchRepository(db)
    active = await matches.with_statuses(list(ACTIVE_STATUSES))
    processing = [m for m in active if m.status is MatchStatus.PROCESSING]
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    events_today = await EventRepository(db).count_since(today)
    worker_list = await list_workers(redis)
    gpu_list = gpus(worker_list)
    metrics = list((await latest_metrics(redis, [m.id for m in processing])).values())
    fps = [m["inference_fps"] for m in metrics if m.get("inference_fps")]
    latency = [m["latency_ms"] for m in metrics if m.get("latency_ms")]
    return ok(
        DashboardSummary(
            active_matches=len(active),
            processing_matches=len(processing),
            events_today=events_today,
            gpu_utilization=round(sum(g.utilization for g in gpu_list) / len(gpu_list), 1) if gpu_list else None,
            average_inference_fps=round(sum(fps) / len(fps), 2) if fps else None,
            average_latency_ms=round(sum(latency) / len(latency), 1) if latency else None,
            devices=sorted({w.device for w in worker_list}),
            workers=len(worker_list),
        )
    )
