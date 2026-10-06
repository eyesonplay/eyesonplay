from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class ComponentHealth(BaseModel):
    ok: bool
    detail: str | None = None


class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    database: ComponentHealth
    redis: ComponentHealth
    workers: int


class GpuOut(BaseModel):
    worker_id: str
    index: int
    name: str
    utilization: float
    memory_used_mb: float
    memory_total_mb: float
    temperature_c: float | None


class WorkerOut(BaseModel):
    worker_id: str
    mode: str
    device: str
    active_matches: list[str]
    capacity: int
    started_at: float
    last_seen: float
    gpu: list[dict[str, Any]] | None
    models: list[dict[str, Any]]


class ModelOut(BaseModel):
    name: str
    family: str
    description: str | None
    device: str
    loaded: bool
    worker_id: str
    classes: list[str] | None = None


class DashboardSummary(BaseModel):
    active_matches: int
    processing_matches: int
    events_today: int
    gpu_utilization: float | None
    average_inference_fps: float | None
    average_latency_ms: float | None
    devices: list[str]
    workers: int
