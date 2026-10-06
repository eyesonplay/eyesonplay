import json
import time

from app.background.event_persister import event_handler
from app.background.status_listener import apply_status
from app.background.stream_consumer import parse_envelope
from app.background.watchdog import Watchdog
from app.core.redis_keys import lease_key

from conftest import add_heartbeat


def status_env(match_id, session_id, status, message=None, stats=None):
    return {"type": "status", "match_id": match_id, "session_id": session_id, "data": {
        "status": status, "message": message, "worker_id": "w1", "device": "cpu", "stats": stats}}  # fmt: skip


def event_fields(match_id, event_id, event="pass", session_id=None):
    env = {"type": "event", "match_id": match_id, "session_id": session_id, "data": {
        "event_id": event_id, "event": event, "video_timestamp": 12.5, "match_clock": "00:12",
        "confidence": 0.9, "ball": None}}  # fmt: skip
    return {"payload": json.dumps(env)}


async def get(client, mid):
    return (await client.get(f"/api/matches/{mid}")).json()["data"]


async def test_worker_status_updates_match_and_session(app, client, redis, match):
    started = (await client.post(f"/api/matches/{match['id']}/start")).json()["data"]
    sid = started["current_session_id"]

    async with app.state.session_factory() as db:
        await apply_status(db, redis, status_env(match["id"], sid, "processing", "Processing on cpu"))
        await db.commit()
    assert (await get(client, match["id"]))["status"] == "processing"

    async with app.state.session_factory() as db:
        await apply_status(db, redis, status_env(match["id"], sid, "failed", "Source disconnected",
                                                 {"frames_processed": 50, "average_fps": 9.8, "average_latency_ms": 120}))  # fmt: skip
        await db.commit()
    detail = await get(client, match["id"])
    assert detail["status"] == "failed"
    assert detail["last_error"] == "Source disconnected"
    session = (await client.get(f"/api/matches/{match['id']}/sessions")).json()["data"][0]
    assert session["frames_processed"] == 50 and session["error"] == "Source disconnected"


async def test_stale_session_and_race_updates_are_ignored(app, client, redis, match):
    mid = match["id"]
    old = (await client.post(f"/api/matches/{mid}/start")).json()["data"]["current_session_id"]
    await client.post(f"/api/matches/{mid}/restart")
    await client.post(f"/api/matches/{mid}/pause")

    async with app.state.session_factory() as db:
        await apply_status(db, redis, status_env(mid, old, "failed", "old session"))
        new = (await get(client, mid))["current_session_id"]
        await apply_status(db, redis, status_env(mid, new, "processing"))  # desired state is paused
        await db.commit()

    assert (await get(client, mid))["status"] == "paused"


async def test_event_persister_is_idempotent_and_counts(app, client, match):
    handle = event_handler(app.state.session_factory)
    messages = [("1-0", event_fields(match["id"], "evt_a")), ("2-0", event_fields(match["id"], "evt_b"))]

    await handle(messages)
    await handle(messages)  # redelivery after a crash
    await handle([("3-0", event_fields("match_deleted", "evt_c")), ("4-0", {"payload": "garbage"})])

    assert (await get(client, match["id"]))["event_count"] == 2
    events = (await client.get(f"/api/matches/{match['id']}/events")).json()["data"]
    assert {e["event_uid"] for e in events} == {"evt_a", "evt_b"}


async def test_watchdog_fails_unclaimed_job_when_no_worker(app, client, redis, settings, match):
    mid = match["id"]
    await client.post(f"/api/matches/{mid}/start")
    watchdog = Watchdog(app.state.session_factory, redis, settings.model_copy(update={"worker_start_timeout_s": 0}))

    await watchdog.check_once()

    detail = await get(client, mid)
    assert detail["status"] == "failed"
    assert "No inference worker" in detail["last_error"]


async def test_watchdog_detects_lost_worker_after_grace(app, client, redis, settings, match):
    mid = match["id"]
    sid = (await client.post(f"/api/matches/{mid}/start")).json()["data"]["current_session_id"]
    async with app.state.session_factory() as db:
        await apply_status(db, redis, status_env(mid, sid, "processing"))
        await db.commit()
    await add_heartbeat(redis)
    watchdog = Watchdog(app.state.session_factory, redis, settings)

    await redis.set(lease_key(mid), json.dumps({"worker_id": "w1", "session_id": sid}))
    await watchdog.check_once()
    assert (await get(client, mid))["status"] == "processing"

    await redis.delete(lease_key(mid))
    await watchdog.check_once()
    assert (await get(client, mid))["status"] == "processing"  # one miss is tolerated
    await watchdog.check_once()
    detail = await get(client, mid)
    assert detail["status"] == "failed"
    assert "worker lost" in detail["last_error"]


def test_parse_envelope_rejects_malformed():
    assert parse_envelope({"payload": "nope"}) is None
    assert parse_envelope({"payload": json.dumps({"data": {}, "match_id": ""})}) is None
    assert parse_envelope({"payload": json.dumps({"data": {"a": 1}, "match_id": "m", "ts": time.time()})})


async def test_events_of_superseded_sessions_are_dropped(app, client, match):
    mid = match["id"]
    old = (await client.post(f"/api/matches/{mid}/start")).json()["data"]["current_session_id"]
    new = (await client.post(f"/api/matches/{mid}/restart")).json()["data"]["current_session_id"]
    handle = event_handler(app.state.session_factory)

    await handle([("1-0", event_fields(mid, "evt_old", session_id=old)), ("2-0", event_fields(mid, "evt_new", session_id=new))])

    events = (await client.get(f"/api/matches/{mid}/events")).json()["data"]
    assert [e["event_uid"] for e in events] == ["evt_new"]


async def test_status_listener_skips_poison_message(app, redis, client, match):
    from app.background.status_listener import status_handler

    sid = (await client.post(f"/api/matches/{match['id']}/start")).json()["data"]["current_session_id"]
    bad = status_env(match["id"], sid, "processing", stats={"frames_processed": "lots"})
    good = status_env(match["id"], sid, "processing", "ok")
    handle = status_handler(app.state.session_factory, redis)

    await handle([("1-0", {"payload": json.dumps(bad)}), ("2-0", {"payload": json.dumps(good)}), ("3-0", None)])

    assert (await get(client, match["id"]))["status"] == "processing"
