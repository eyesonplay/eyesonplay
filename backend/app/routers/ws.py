"""Live match feed: `/ws/matches/{match_id}`.

On connect the client receives a snapshot (status, last frame/ball/players,
last metrics, recent events), then every message published on the match's
Redis channels. Message envelope: `{type, match_id, session_id, ts, seq, data}`
with type in status | frame | ball | players | event | metrics | error.
"""

from __future__ import annotations

import asyncio
import contextlib
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from redis.asyncio import Redis
from redis.asyncio.client import PubSub
from redis.exceptions import RedisError

from app.core.logging import get_logger
from app.core.redis_keys import LIVE_CHANNELS, channel
from app.core.sessions import COOKIE_NAME, user_for_token
from app.db.models import Match
from app.deps import origin_allowed
from app.repositories.event_repo import EventRepository
from app.repositories.match_repo import MatchRepository
from app.services.realtime import envelope
from app.services.status_machine import ACTIVE_STATUSES

router = APIRouter()
log = get_logger(component="ws")

SNAPSHOT_EVENTS = 50
CLOSE_UNAUTHORIZED = 4401
CLOSE_FORBIDDEN = 4403
CLOSE_NOT_FOUND = 4404
CLOSE_UNAVAILABLE = 1011
PUBSUB_POLL_S = 1.0


@router.websocket("/ws/matches/{match_id}")
async def match_feed(websocket: WebSocket, match_id: str) -> None:
    """Dashboard feed: the browser's session cookie, from an allowed origin."""
    await websocket.accept()
    settings = websocket.app.state.settings
    if not origin_allowed(websocket.headers.get("origin"), websocket.headers.get("host"), settings):
        await websocket.close(code=CLOSE_FORBIDDEN, reason="cross-site connection refused")
        return
    async with websocket.app.state.session_factory() as db:
        user = await user_for_token(db, websocket.cookies.get(COOKIE_NAME))
    if user is None:
        await websocket.close(code=CLOSE_UNAUTHORIZED, reason="sign in required")
        return
    await serve_feed(websocket, match_id)


async def serve_feed(websocket: WebSocket, match_id: str) -> None:
    """Snapshot, then live messages, on an accepted socket (dashboard and integration feed)."""
    redis: Redis = websocket.app.state.redis
    async with websocket.app.state.session_factory() as db:
        match = await MatchRepository(db).get(match_id)
        recent = await EventRepository(db).list(match_id, None, SNAPSHOT_EVENTS) if match else []
    if match is None:
        await websocket.close(code=CLOSE_NOT_FOUND, reason="match not found")
        return

    pubsub = redis.pubsub(ignore_subscribe_messages=True)
    try:
        await pubsub.subscribe(*[channel(match_id, kind) for kind in LIVE_CHANNELS])
        await _send_snapshot(websocket, redis, match, [e.payload for e in reversed(recent)])
        await _relay(websocket, pubsub)
    except WebSocketDisconnect:
        pass
    except RedisError as exc:
        log.warning("live feed unavailable", match_id=match_id, error=str(exc))
        with contextlib.suppress(Exception):
            await websocket.send_text(envelope("error", match_id, {"message": "Realtime feed unavailable (Redis). Reconnecting…"}))
            await websocket.close(code=CLOSE_UNAVAILABLE)
    finally:
        with contextlib.suppress(Exception):
            await pubsub.aclose()


async def _send_snapshot(ws: WebSocket, redis: Redis, match: Match, events: list[dict]) -> None:
    status = {"status": match.status.value, "message": match.status_message, "error": match.last_error, "origin": "snapshot"}
    await ws.send_text(envelope("status", match.id, status, match.current_session_id))
    if match.status not in ACTIVE_STATUSES:
        frame_raw = metrics_raw = None  # no stale detections for idle matches
    else:
        frame_raw, metrics_raw = await redis.mget([channel(match.id, "frame:last"), channel(match.id, "metrics:last")])
    if frame_raw:
        frame = json.loads(frame_raw)
        await ws.send_text(frame_raw)
        data = frame.get("data", {})
        await ws.send_text(envelope("ball", match.id, data.get("ball"), frame.get("session_id")))
        await ws.send_text(envelope("players", match.id, data.get("players", []), frame.get("session_id")))
    if metrics_raw:
        await ws.send_text(metrics_raw)
    for payload in events:
        await ws.send_text(envelope("event", match.id, payload, match.current_session_id))


async def _relay(ws: WebSocket, pubsub: PubSub) -> None:
    async def forward() -> None:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=PUBSUB_POLL_S)
            if message is not None and message.get("type") == "message":
                await ws.send_text(message["data"])

    async def drain_client() -> None:
        while True:  # client pings keep the connection alive; content is ignored
            await ws.receive_text()

    tasks = [asyncio.create_task(forward()), asyncio.create_task(drain_client())]
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()  # re-raise WebSocketDisconnect / RedisError
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
