"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from app.background.event_persister import event_handler
from app.background.status_listener import status_handler
from app.background.stream_consumer import consume_stream
from app.background.watchdog import Watchdog
from app.core.config import Settings, get_settings
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging, get_logger
from app.core.redis_keys import EVENTS_GROUP, EVENTS_STREAM, STATUS_GROUP, STATUS_STREAM
from app.db.base import Base, create_engine, session_factory
from app.db import models  # noqa: F401 - register tables
from app.routers import api_keys, events, feed, matches, media, processing, settings, system, uploads, ws

log = get_logger(component="main")


def create_app(
    settings_override: Settings | None = None, *, background_tasks: bool = True, create_schema: bool = False
) -> FastAPI:
    """`create_schema` builds tables directly (tests); production uses Alembic."""
    app_settings = settings_override or get_settings()
    configure_logging(app_settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(app_settings.database_url)
        app.state.settings = app_settings
        app.state.engine = engine
        app.state.session_factory = session_factory(engine)
        if not hasattr(app.state, "redis"):
            app.state.redis = Redis.from_url(app_settings.redis_url, decode_responses=True, health_check_interval=15)
        app_settings.media_dir.mkdir(parents=True, exist_ok=True)
        if create_schema:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        stop = asyncio.Event()
        tasks = _start_background(app, stop) if background_tasks else []
        log.info("api started", background_tasks=background_tasks)
        try:
            yield
        finally:
            stop.set()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await app.state.redis.aclose()
            await engine.dispose()

    app = FastAPI(
        title="Football Vision API",
        version="0.1.0",
        description="Real-time football video analysis: matches, processing control, events and live feed.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )
    install_error_handlers(app)

    @app.middleware("http")
    async def request_context(request: Request, call_next) -> Response:  # noqa: ANN001
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        structlog.contextvars.bind_contextvars(request_id=request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.unbind_contextvars("request_id")
        response.headers["x-request-id"] = request_id
        if not request.url.path.startswith(("/api/system/live", "/media")):
            log.info("request", method=request.method, path=request.url.path, status=response.status_code,
                     duration_ms=round((time.perf_counter() - started) * 1000, 1))  # fmt: skip
        return response

    for module in (matches, processing, events, uploads, media, settings, system, ws, api_keys, feed):
        app.include_router(module.router)
    return app


def _start_background(app: FastAPI, stop: asyncio.Event) -> list[asyncio.Task[None]]:
    s: Settings = app.state.settings
    redis, factory = app.state.redis, app.state.session_factory
    return [
        asyncio.create_task(
            consume_stream(redis, STATUS_STREAM, STATUS_GROUP, s.instance_id, status_handler(factory, redis), stop),
            name="status-listener",
        ),
        asyncio.create_task(
            consume_stream(redis, EVENTS_STREAM, EVENTS_GROUP, s.instance_id, event_handler(factory), stop),
            name="event-persister",
        ),
        asyncio.create_task(Watchdog(factory, redis, s).run(stop), name="watchdog"),
    ]


app = create_app(create_schema=get_settings().auto_create_schema)
