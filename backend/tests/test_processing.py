import json

from redis.exceptions import ConnectionError as RedisConnectionError

from app.core.redis_keys import COMMANDS_STREAM, control_key


async def control(redis, match_id):
    return json.loads(await redis.get(control_key(match_id)))


async def test_start_queues_command_and_sets_control(client, redis, match):
    response = await client.post(f"/api/matches/{match['id']}/start")

    data = response.json()["data"]
    assert data["status"] == "starting"
    session_id = data["current_session_id"]
    assert await control(redis, match["id"]) == {"session_id": session_id, "state": "running"}
    entries = await redis.xrange(COMMANDS_STREAM)
    command = json.loads(entries[-1][1]["payload"])
    assert command["session_id"] == session_id
    assert command["config"]["source"] == match["video_source"]
    assert command["config"]["processing_fps"] == 10


async def test_pause_resume_stop_cycle(client, redis, match):
    mid = match["id"]
    await client.post(f"/api/matches/{mid}/start")

    paused = (await client.post(f"/api/matches/{mid}/pause")).json()["data"]
    assert paused["status"] == "paused"
    assert (await control(redis, mid))["state"] == "paused"

    resumed = (await client.post(f"/api/matches/{mid}/start")).json()["data"]
    assert resumed["status"] == "processing"
    assert resumed["current_session_id"] == paused["current_session_id"]
    assert (await redis.xlen(COMMANDS_STREAM)) == 1  # resume does not queue a new job

    stopped = (await client.post(f"/api/matches/{mid}/stop")).json()["data"]
    assert stopped["status"] == "completed"
    assert (await control(redis, mid))["state"] == "stopped"

    sessions = (await client.get(f"/api/matches/{mid}/sessions")).json()["data"]
    assert sessions[0]["status"] == "stopped" and sessions[0]["stopped_at"]


async def test_restart_creates_new_session(client, redis, match):
    mid = match["id"]
    first = (await client.post(f"/api/matches/{mid}/start")).json()["data"]["current_session_id"]

    second = (await client.post(f"/api/matches/{mid}/restart")).json()["data"]["current_session_id"]

    assert first != second
    assert (await control(redis, mid))["session_id"] == second
    assert await redis.xlen(COMMANDS_STREAM) == 2


async def test_illegal_transitions_return_409(client, match):
    mid = match["id"]
    assert (await client.post(f"/api/matches/{mid}/pause")).status_code == 409
    assert (await client.post(f"/api/matches/{mid}/stop")).status_code == 409


async def test_cannot_start_draft(client):
    from conftest import match_body

    body = match_body()
    del body["video_source_type"], body["video_source"]
    draft = (await client.post("/api/matches", json=body)).json()["data"]

    response = await client.post(f"/api/matches/{draft['id']}/start")

    assert response.status_code == 409
    assert "video source" in response.json()["error"]["message"]


async def test_start_when_redis_down_fails_cleanly(client, redis, match, monkeypatch):
    def broken_pipeline(*args, **kwargs):
        raise RedisConnectionError("connection refused")

    monkeypatch.setattr(redis, "pipeline", broken_pipeline)

    response = await client.post(f"/api/matches/{match['id']}/start")

    assert response.status_code == 503
    detail = (await client.get(f"/api/matches/{match['id']}")).json()["data"]
    assert detail["status"] == "failed"
    assert "Redis" in detail["last_error"]
