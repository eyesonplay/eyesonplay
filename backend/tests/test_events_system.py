import json

from app.background.event_persister import event_handler

from conftest import add_heartbeat
from test_background import event_fields


async def seed_events(app, match_id):
    handle = event_handler(app.state.session_factory)
    await handle([
        (f"{i}-0", event_fields(match_id, f"evt_{i}", event))
        for i, event in enumerate(["ball_move", "pass", "shot_candidate", "possession", "pass"], start=1)
    ])  # fmt: skip


async def test_event_filters_by_group_and_type(app, client, match):
    await seed_events(app, match["id"])
    base = f"/api/matches/{match['id']}/events"

    passes = (await client.get(base, params={"group": "pass"})).json()
    shots = (await client.get(base, params={"type": "shot_candidate"})).json()
    bad = await client.get(base, params={"group": "nonsense"})

    assert [e["event_type"] for e in passes["data"]] == ["pass", "pass"]
    assert len(shots["data"]) == 1
    assert bad.status_code == 422


async def test_event_pagination_cursor(app, client, match):
    await seed_events(app, match["id"])

    first = (await client.get("/api/events", params={"limit": 2})).json()
    second = (await client.get("/api/events", params={"limit": 2, "before_id": first["meta"]["next_before_id"]})).json()

    assert len(first["data"]) == 2 and len(second["data"]) == 2
    assert first["data"][-1]["id"] > second["data"][0]["id"]


async def test_export_is_valid_json_attachment(app, client, match):
    await seed_events(app, match["id"])

    response = await client.get(f"/api/matches/{match['id']}/events/export")

    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    payloads = json.loads(response.text)
    assert [p["event_id"] for p in payloads] == [f"evt_{i}" for i in range(1, 6)]


async def test_export_empty_match(client, match):
    response = await client.get(f"/api/matches/{match['id']}/events/export")
    assert json.loads(response.text) == []


async def test_health_reports_components_and_workers(client, redis):
    await add_heartbeat(redis)

    data = (await client.get("/api/system/health")).json()["data"]

    assert data["status"] == "ok"
    assert data["database"]["ok"] and data["redis"]["ok"]
    assert data["workers"] == 1


async def test_gpu_hidden_without_nvidia_and_listed_with(client, redis):
    await add_heartbeat(redis, "cpu-worker")
    assert (await client.get("/api/system/gpu")).json()["data"] == []

    gpu = [{"index": 0, "name": "NVIDIA L4", "utilization": 63, "memory_used_mb": 7200, "memory_total_mb": 23034, "temperature_c": 61}]
    await add_heartbeat(redis, "gpu-worker", gpu=gpu)
    gpus = (await client.get("/api/system/gpu")).json()["data"]
    summary = (await client.get("/api/dashboard/summary")).json()["data"]

    assert gpus[0]["name"] == "NVIDIA L4" and gpus[0]["worker_id"] == "gpu-worker"
    assert summary["gpu_utilization"] == 63
    assert summary["workers"] == 2


async def test_workers_and_models(client, redis):
    await add_heartbeat(redis)

    workers = (await client.get("/api/system/workers")).json()["data"]
    models = (await client.get("/api/models")).json()["data"]

    assert workers[0]["worker_id"] == "w1"
    assert models[0]["name"] == "mock-detector" and models[0]["loaded"] is True


async def test_settings_round_trip_and_used_as_defaults(client):
    current = (await client.get("/api/settings")).json()["data"]
    current.update(default_processing_fps=25, default_detection_model="ball")
    del current["updated_at"]

    saved = (await client.put("/api/settings", json=current)).json()["data"]
    from conftest import match_body

    created = (await client.post("/api/matches", json=match_body())).json()["data"]

    assert saved["default_processing_fps"] == 25
    assert created["processing_fps"] == 25 and created["detection_model"] == "ball"
