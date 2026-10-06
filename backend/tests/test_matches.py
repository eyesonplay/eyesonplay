from conftest import match_body


async def test_create_applies_defaults_and_ready_status(client):
    response = await client.post("/api/matches", json=match_body())

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["id"].startswith("match_")
    assert data["status"] == "ready"
    assert data["processing_fps"] == 10
    assert data["detection_model"] == "ball_players_pitch"
    assert response.json()["error"] is None


async def test_match_without_source_is_draft(client):
    body = match_body()
    del body["video_source_type"], body["video_source"]

    response = await client.post("/api/matches", json=body)

    assert response.json()["data"]["status"] == "draft"


async def test_source_scheme_is_validated(client):
    response = await client.post("/api/matches", json=match_body(video_source_type="rtmp"))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_upload_reference_must_come_from_upload_endpoint(client):
    response = await client.post(
        "/api/matches", json=match_body(video_source_type="upload", video_source="../../etc/passwd")
    )
    assert response.status_code == 422


async def test_processing_fps_must_be_supported_value(client):
    response = await client.post("/api/matches", json=match_body(processing_fps=12))
    assert response.status_code == 422


async def test_list_filter_and_search(client, match):
    await client.post("/api/matches", json=match_body(name="Leeds vs Spurs", home_team="Leeds", away_team="Spurs"))

    all_ = (await client.get("/api/matches")).json()
    searched = (await client.get("/api/matches", params={"q": "leeds"})).json()
    by_status = (await client.get("/api/matches", params={"status": "processing"})).json()

    assert all_["meta"]["total"] == 2
    assert [m["home_team"] for m in searched["data"]] == ["Leeds"]
    assert by_status["data"] == []


async def test_get_missing_match_returns_error_envelope(client):
    response = await client.get("/api/matches/match_missing")

    assert response.status_code == 404
    assert response.json() == {
        "data": None,
        "error": {"code": "not_found", "message": "Match match_missing not found", "details": None},
        "meta": None,
    }


async def test_patch_updates_and_recomputes_idle_status(client, match):
    response = await client.patch(
        f"/api/matches/{match['id']}", json={"video_source_type": None, "video_source": None, "name": "Renamed"}
    )

    data = response.json()["data"]
    assert data["name"] == "Renamed"
    assert data["status"] == "draft"


async def test_patch_source_locked_while_processing(client, match):
    await client.post(f"/api/matches/{match['id']}/start")

    locked = await client.patch(f"/api/matches/{match['id']}", json={"processing_fps": 25})
    allowed = await client.patch(f"/api/matches/{match['id']}", json={"name": "Still fine"})

    assert locked.status_code == 409
    assert allowed.status_code == 200


async def test_delete_refused_while_active_then_allowed(client, match):
    await client.post(f"/api/matches/{match['id']}/start")
    assert (await client.delete(f"/api/matches/{match['id']}")).status_code == 409

    await client.post(f"/api/matches/{match['id']}/stop")
    assert (await client.delete(f"/api/matches/{match['id']}")).status_code == 200
    assert (await client.get(f"/api/matches/{match['id']}")).status_code == 404


def test_cors_origins_parse_from_comma_separated_env(monkeypatch):
    from app.core.config import Settings

    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000, http://127.0.0.1:3000")
    assert Settings().cors_origins == ["http://localhost:3000", "http://127.0.0.1:3000"]


async def test_tennis_match_round_trip_and_start_command(client, redis):
    import json

    from app.core.redis_keys import COMMANDS_STREAM
    from conftest import match_body

    created = (await client.post("/api/matches", json=match_body(sport="tennis", name="Alcaraz vs Sinner"))).json()["data"]
    assert created["sport"] == "tennis"
    assert (await client.post("/api/matches", json=match_body(sport="cricket"))).status_code == 422

    await client.post(f"/api/matches/{created['id']}/start")
    command = json.loads((await redis.xrange(COMMANDS_STREAM))[-1][1]["payload"])
    assert command["config"]["sport"] == "tennis"
