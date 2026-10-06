"""Integration feed for other apps: API keys, external match links, keyed WebSocket."""

from __future__ import annotations

import json

import fakeredis.aioredis
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import create_app
from conftest import match_body


async def create_key(client, name="riosport") -> dict:
    response = await client.post("/api/api-keys", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def test_key_is_shown_once_and_stored_hashed(client):
    created = await create_key(client)
    assert created["key"].startswith("psk_") and len(created["key"]) > 30
    listed = (await client.get("/api/api-keys")).json()["data"]
    assert [k["name"] for k in listed] == ["riosport"]
    assert "key" not in listed[0] and listed[0]["prefix"] == created["key"][:12]


async def test_feed_needs_a_valid_active_key(client):
    assert (await client.get("/api/v1/feed/matches")).status_code == 401
    bad = await client.get("/api/v1/feed/matches", headers={"X-API-Key": "psk_wrong"})
    assert bad.status_code == 401
    created = await create_key(client)
    good = await client.get("/api/v1/feed/matches", headers={"X-API-Key": created["key"]})
    assert good.status_code == 200
    await client.delete(f"/api/api-keys/{created['id']}")
    revoked = await client.get("/api/v1/feed/matches", headers={"X-API-Key": created["key"]})
    assert revoked.status_code == 401


async def test_feed_lists_matches_with_their_external_ref(client):
    key = (await create_key(client))["key"]
    linked = await client.post("/api/matches", json=match_body(external_ref="riosport:1557417"))
    assert linked.status_code == 201, linked.text
    await client.post("/api/matches", json=match_body(name="Other", home_team="Leeds"))
    rows = (await client.get("/api/v1/feed/matches", headers={"X-API-Key": key})).json()["data"]
    assert {r["external_ref"] for r in rows} == {"riosport:1557417", None}
    only = await client.get("/api/v1/feed/matches", params={"external_ref": "riosport:1557417"}, headers={"X-API-Key": key})
    assert [r["home_team"] for r in only.json()["data"]] == ["Arsenal"]
    # The feed shares what another app needs, never the video source.
    assert "video_source" not in rows[0]


async def test_external_ref_can_be_set_later(client, match):
    patched = await client.patch(f"/api/matches/{match['id']}", json={"external_ref": "riosport:42"})
    assert patched.json()["data"]["external_ref"] == "riosport:42"


@pytest.fixture
def ws_app(settings):
    app = create_app(settings, background_tasks=False, create_schema=True)
    app.state.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    return app


def test_keyed_websocket_relays_the_match_feed(ws_app):
    with TestClient(ws_app) as client:
        key = client.post("/api/api-keys", json={"name": "riosport"}).json()["data"]["key"]
        match = client.post("/api/matches", json=match_body()).json()["data"]
        with client.websocket_connect(f"/ws/v1/feed/matches/{match['id']}", headers={"X-API-Key": key}) as ws:
            snapshot = json.loads(ws.receive_text())
            assert snapshot["type"] == "status"
            ws.close()


def test_keyed_websocket_refuses_a_missing_key(ws_app):
    with TestClient(ws_app) as client:
        match = client.post("/api/matches", json=match_body()).json()["data"]
        with client.websocket_connect(f"/ws/v1/feed/matches/{match['id']}") as ws:
            with pytest.raises(WebSocketDisconnect) as exc:
                ws.receive_text()
            assert exc.value.code == 4401
