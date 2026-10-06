from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        redis_url="redis://unused",
        media_dir=tmp_path / "media",
        worker_start_timeout_s=30,
        lost_lease_checks=2,
    )


@pytest.fixture
async def redis():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


@pytest.fixture
async def app(settings, redis):
    application = create_app(settings, background_tasks=False, create_schema=True)
    application.state.redis = redis
    async with application.router.lifespan_context(application):
        yield application


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def match_body(**overrides) -> dict:
    body = {
        "name": "Arsenal vs Chelsea",
        "home_team": "Arsenal",
        "away_team": "Chelsea",
        "competition": "Premier League",
        "match_date": datetime(2026, 10, 4, 15, 0, tzinfo=UTC).isoformat(),
        "video_source_type": "hls",
        "video_source": "https://example.com/live-match.m3u8",
    }
    body.update(overrides)
    return body


@pytest.fixture
async def match(client) -> dict:
    response = await client.post("/api/matches", json=match_body())
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def add_heartbeat(redis, worker_id="w1", gpu=None):
    hb = {
        "worker_id": worker_id, "mode": "mock", "device": "cpu", "gpu": gpu,
        "models": [{"name": "mock-detector", "family": "mock", "device": "cpu", "loaded": True}],
        "active_matches": [], "capacity": 4, "started_at": time.time(), "ts": time.time(),
    }  # fmt: skip
    await redis.set(f"worker:{worker_id}:heartbeat", json.dumps(hb), ex=10)
