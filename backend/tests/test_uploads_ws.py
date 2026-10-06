import json
import shutil
import subprocess

import pytest
from starlette.testclient import TestClient

from app.main import create_app

from conftest import login_sync, match_body

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


@pytest.fixture
def clip(tmp_path):
    path = tmp_path / "clip.mp4"
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=25", "-t", "1",
         "-pix_fmt", "yuv420p", str(path)],
        check=True,
    )  # fmt: skip
    return path


@needs_ffmpeg
async def test_upload_valid_video_and_serve_with_range(client, clip):
    with clip.open("rb") as f:
        response = await client.post("/api/uploads", files={"file": ("match.mp4", f, "video/mp4")})

    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["video_source"].startswith("uploads/") and data["width"] == 320
    created = await client.post("/api/matches", json=match_body(video_source_type="upload", video_source=data["video_source"]))
    assert created.status_code == 201

    ranged = await client.get(f"/media/{data['video_source']}", headers={"Range": "bytes=0-99"})
    assert ranged.status_code == 206 and len(ranged.content) == 100


@needs_ffmpeg
async def test_corrupt_upload_is_rejected(client, settings):
    response = await client.post("/api/uploads", files={"file": ("bad.mp4", b"\x00garbage" * 500, "video/mp4")})

    assert response.status_code == 422
    assert response.json()["error"]["message"] == "Uploaded file is not a readable video"
    assert list((settings.media_dir / "uploads").iterdir()) == []


async def test_unsupported_extension_rejected(client):
    response = await client.post("/api/uploads", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert response.status_code == 422


async def test_media_path_traversal_blocked(client):
    assert (await client.get("/media/../../etc/passwd")).status_code == 404


def test_websocket_snapshot_and_relay(settings):
    import fakeredis.aioredis

    app = create_app(settings, background_tasks=False, create_schema=True)
    app.state.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    with TestClient(app) as client:
        login_sync(client)
        match = client.post("/api/matches", json=match_body()).json()["data"]
        with client.websocket_connect(f"/ws/matches/{match['id']}") as ws:
            snapshot = json.loads(ws.receive_text())
            assert snapshot["type"] == "status" and snapshot["data"]["status"] == "ready"

            client.post(f"/api/matches/{match['id']}/start")
            relayed = json.loads(ws.receive_text())
            assert relayed["type"] == "status" and relayed["data"]["status"] == "starting"
            ws.close()  # a client disconnect must end the handler cleanly


def test_websocket_unknown_match_closes_4404(settings):
    import fakeredis.aioredis
    from starlette.websockets import WebSocketDisconnect

    app = create_app(settings, background_tasks=False, create_schema=True)
    app.state.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    with TestClient(app) as client:
        login_sync(client)
        with client.websocket_connect("/ws/matches/match_nope") as ws:
            with pytest.raises(WebSocketDisconnect) as exc:
                ws.receive_text()
            assert exc.value.code == 4404
