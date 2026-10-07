"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import re
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis
from sqlalchemy.exc import SQLAlchemyError

from app.background.event_persister import event_handler
from app.background.status_listener import status_handler
from app.background.stream_consumer import consume_stream
from app.background.watchdog import Watchdog
from app.core.config import Settings, get_settings
from app.core.errors import error_body, install_error_handlers
from app.core.logging import configure_logging, get_logger
from app.core.redis_keys import EVENTS_GROUP, EVENTS_STREAM, STATUS_GROUP, STATUS_STREAM
from app.core.sessions import COOKIE_NAME, user_for_token
from app.core.users import bootstrap_admin, refuse_dev_admin
from app.db.base import Base, create_engine, session_factory
from app.db import models  # noqa: F401 - register tables
from app.deps import origin_allowed, require_user
from app.routers import api_keys, auth, events, feed, labels, matches, media, processing, settings, system, uploads, ws

log = get_logger(component="main")
REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
# Concurrent Argon2 verifications (memory-hard): more wait instead of exhausting RAM.
PASSWORD_CHECKS = 4


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
        app.state.password_checks = asyncio.Semaphore(PASSWORD_CHECKS)
        if not hasattr(app.state, "redis"):
            app.state.redis = Redis.from_url(app_settings.redis_url, decode_responses=True, health_check_interval=15)
        app_settings.media_dir.mkdir(parents=True, exist_ok=True)
        if create_schema:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        await _bootstrap_admin(app, app_settings)
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
        title="EyesOnPlay API",
        version="0.1.0",
        description="Real-time sports video analysis (football, tennis): matches, processing control, events and live feed.",
        lifespan=lifespan,
        docs_url="/docs" if app_settings.api_docs else None,
        redoc_url="/redoc" if app_settings.api_docs else None,
        openapi_url="/openapi.json" if app_settings.api_docs else None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=True,  # the dashboard's session cookie
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )
    install_error_handlers(app)

    @app.middleware("http")
    async def request_context(request: Request, call_next) -> Response:  # noqa: ANN001
        supplied = request.headers.get("x-request-id", "")
        request_id = supplied if REQUEST_ID.match(supplied) else uuid.uuid4().hex[:12]
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

    @app.middleware("http")
    async def upload_guard(request: Request, call_next) -> Response:  # noqa: ANN001
        """Uploads are large: check the session before FastAPI reads the body
        (a route dependency would only run after the whole file is spooled)."""
        if request.method == "POST" and request.url.path.rstrip("/") == "/api/uploads":
            if not origin_allowed(request.headers.get("origin"), request.headers.get("host"), app_settings):
                return JSONResponse(error_body("forbidden", "Cross-site request refused"), status_code=403)
            async with request.app.state.session_factory() as db:
                if await user_for_token(db, request.cookies.get(COOKIE_NAME)) is None:
                    return JSONResponse(error_body("unauthorized", "Sign in to continue"), status_code=401)
        return await call_next(request)

    # Dashboard routes need a signed-in user; the integration feed uses API keys,
    # the WebSocket checks the session itself, and liveness stays public.
    signed_in = [Depends(require_user)]
    for module in (matches, processing, events, labels, uploads, media, settings, system, api_keys):
        app.include_router(module.router, dependencies=signed_in)
    for public in (auth.router, system.public_router, ws.router, feed.router):
        app.include_router(public)
    return app


async def _bootstrap_admin(app: FastAPI, settings: Settings) -> None:
    password = settings.admin_password.get_secret_value() if settings.admin_password else None
    if settings.admin_email and not password:
        log.warning("ADMIN_EMAIL is set without ADMIN_PASSWORD; no admin created")
    try:
        async with app.state.session_factory() as db:
            if settings.cookie_secure:  # production
                await refuse_dev_admin(db, password)
            await bootstrap_admin(db, settings.admin_email, password)
    except (SQLAlchemyError, ValueError):
        log.exception("could not create the admin user (are migrations applied?)")


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
