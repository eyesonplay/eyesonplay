"""Dashboard login: users, sessions, protected routes, rate limits, CSRF guard."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import select
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.passwords import hash_password, verify_password
from app.core.users import create_user
from app.db.models import User, UserSession
from app.main import create_app
from conftest import ADMIN_EMAIL, ADMIN_PASSWORD, login_sync, match_body


async def test_dashboard_api_requires_login(anon_client):
    response = await anon_client.get("/api/matches")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_liveness_probe_stays_public(anon_client):
    assert (await anon_client.get("/api/system/live")).status_code == 200


async def test_login_sets_a_secure_session_cookie(anon_client):
    response = await anon_client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})

    assert response.status_code == 200
    assert response.json()["data"] == {"email": ADMIN_EMAIL}
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    me = await anon_client.get("/api/auth/me")
    assert me.json()["data"]["email"] == ADMIN_EMAIL


async def test_email_is_case_insensitive(anon_client):
    response = await anon_client.post("/api/auth/login", json={"email": ADMIN_EMAIL.upper(), "password": ADMIN_PASSWORD})

    assert response.status_code == 200


async def test_wrong_password_and_unknown_email_look_the_same(anon_client):
    wrong = await anon_client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": "nope-nope-nope"})
    unknown = await anon_client.post("/api/auth/login", json={"email": "who@example.com", "password": "nope-nope-nope"})

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["error"]["message"] == unknown.json()["error"]["message"]


async def test_logout_ends_the_session(client):
    assert (await client.post("/api/auth/logout")).status_code == 200

    assert (await client.get("/api/auth/me")).status_code == 401
    assert (await client.get("/api/matches")).status_code == 401


async def test_expired_session_is_refused(client, app):
    async with app.state.session_factory() as db:
        for row in await db.scalars(select(UserSession)):
            row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        await db.commit()

    assert (await client.get("/api/matches")).status_code == 401


async def test_sessions_are_stored_hashed(client, app):
    token = client.cookies.get("eop_session")
    async with app.state.session_factory() as db:
        stored = [s.token_hash for s in await db.scalars(select(UserSession))]

    assert token and token not in stored and len(stored) == 1


async def test_repeated_failed_logins_are_rate_limited(anon_client):
    for _ in range(5):
        await anon_client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong-password"})

    blocked = await anon_client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})

    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) > 0


async def test_cross_site_writes_are_refused(client):
    evil = await client.post("/api/matches", json=match_body(), headers={"Origin": "https://evil.example"})
    allowed = await client.post("/api/matches", json=match_body(), headers={"Origin": "http://localhost:3000"})

    assert evil.status_code == 403
    assert allowed.status_code == 201


async def test_media_requires_login(anon_client):
    assert (await anon_client.get("/media/uploads/anything.mp4")).status_code == 401


async def test_api_key_management_requires_login(anon_client):
    assert (await anon_client.post("/api/api-keys", json={"name": "x"})).status_code == 401


def test_dashboard_websocket_requires_login(settings):
    app = create_app(settings, background_tasks=False, create_schema=True)
    app.state.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    with TestClient(app) as client:
        login_sync(client)
        match = client.post("/api/matches", json=match_body()).json()["data"]
        with client.websocket_connect(f"/ws/matches/{match['id']}") as ws:
            assert json.loads(ws.receive_text())["type"] == "status"
            ws.close()
        client.cookies.clear()
        with client.websocket_connect(f"/ws/matches/{match['id']}") as ws:
            with pytest.raises(WebSocketDisconnect) as exc:
                ws.receive_text()
            assert exc.value.code == 4401


async def test_admin_is_bootstrapped_once_and_never_overwritten(settings, redis):
    app = create_app(settings, background_tasks=False, create_schema=True)
    app.state.redis = redis
    async with app.router.lifespan_context(app):
        async with app.state.session_factory() as db:
            user = (await db.scalars(select(User))).one()
            user.password_hash = hash_password("changed-by-the-admin")
            await db.commit()
    async with app.router.lifespan_context(app):  # restart
        async with app.state.session_factory() as db:
            user = (await db.scalars(select(User))).one()

    assert verify_password(user.password_hash, "changed-by-the-admin")


async def test_create_user_hashes_the_password(app):
    async with app.state.session_factory() as db:
        user = await create_user(db, "Coach@Example.com", "a-long-password")

    assert user.email == "coach@example.com"
    assert user.password_hash != "a-long-password" and verify_password(user.password_hash, "a-long-password")


async def test_short_passwords_are_refused(app):
    async with app.state.session_factory() as db:
        with pytest.raises(ValueError):
            await create_user(db, "short@example.com", "short")


async def test_disabled_user_cannot_log_in(app):
    async with app.state.session_factory() as db:
        user = await create_user(db, "gone@example.com", "a-long-password")
        user.disabled = True
        await db.commit()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.post("/api/auth/login", json={"email": "gone@example.com", "password": "a-long-password"})

    assert response.status_code == 401


# --- Hardening from the security review -------------------------------------


async def test_uploads_are_refused_before_the_body_is_read(anon_client):
    # A malformed multipart body: if it were parsed first this would be a 4xx parse error.
    response = await anon_client.post(
        "/api/uploads", content=b"x" * 4096, headers={"Content-Type": "multipart/form-data; boundary=nope"}
    )

    assert response.status_code == 401


async def test_concurrent_guesses_cannot_beat_the_email_limit(anon_client):
    import asyncio

    guesses = [
        anon_client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": f"wrong-{i}-password"})
        for i in range(12)
    ]
    responses = await asyncio.gather(*guesses)

    assert sum(r.status_code == 401 for r in responses) <= 5
    assert all(r.status_code in (401, 429) for r in responses)


async def test_changing_a_password_signs_out_every_session(client, app):
    from app.core.users import find_user, set_password

    async with app.state.session_factory() as db:
        await set_password(db, await find_user(db, ADMIN_EMAIL), "a-brand-new-password")

    assert (await client.get("/api/matches")).status_code == 401


@pytest.mark.parametrize("admin_password", ["eyesonplay-admin"])
async def test_production_refuses_the_dev_admin_password(settings, redis, admin_password):
    prod = settings.model_copy(update={"cookie_secure": True, "admin_email": "admin@example.com"})
    prod.admin_password = SecretStr(admin_password)
    app = create_app(prod, background_tasks=False, create_schema=True)
    app.state.redis = redis

    with pytest.raises(RuntimeError, match="development admin"):
        async with app.router.lifespan_context(app):
            pass


async def test_production_refuses_a_leftover_dev_admin(settings, redis):
    dev = settings.model_copy(update={"admin_email": "admin@example.com"})
    dev.admin_password = SecretStr("eyesonplay-admin")
    dev_app = create_app(dev, background_tasks=False, create_schema=True)
    dev_app.state.redis = redis
    async with dev_app.router.lifespan_context(dev_app):
        pass  # the dev stack created admin@example.com / eyesonplay-admin

    prod = settings.model_copy(update={"cookie_secure": True})  # its own admin from conftest
    prod_app = create_app(prod, background_tasks=False, create_schema=True)
    prod_app.state.redis = redis
    with pytest.raises(RuntimeError, match="development admin"):
        async with prod_app.router.lifespan_context(prod_app):
            pass


async def test_api_docs_can_be_turned_off(settings, redis):
    app = create_app(settings.model_copy(update={"api_docs": False}), background_tasks=False, create_schema=True)
    app.state.redis = redis
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            assert (await c.get("/docs")).status_code == 404
            assert (await c.get("/openapi.json")).status_code == 404


async def test_untrusted_request_ids_are_not_echoed(anon_client):
    response = await anon_client.get("/api/system/live", headers={"x-request-id": "evil;id<script>"})

    assert response.headers["x-request-id"] != "evil;id<script>"
    assert len(response.headers["x-request-id"]) <= 64
