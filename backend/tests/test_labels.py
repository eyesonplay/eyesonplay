"""Hand-labelled ground truth per match: the labelling page saves here; the
benchmark and training pipelines read the export."""

from __future__ import annotations

import json


async def test_a_match_starts_without_labels(client, match):
    response = await client.get(f"/api/matches/{match['id']}/labels")

    assert response.status_code == 200
    assert response.json()["data"] == {"events": [], "labelled_until_s": None, "updated_at": None}


async def test_labels_are_saved_sorted_by_time(client, match):
    body = {
        "labelled_until_s": 30.0,
        "events": [
            {"t": 12.5, "event": "bounce", "in": True},
            {"t": 3.04, "event": "serve", "player": "near"},
        ],
    }

    saved = (await client.put(f"/api/matches/{match['id']}/labels", json=body)).json()["data"]
    again = (await client.get(f"/api/matches/{match['id']}/labels")).json()["data"]

    assert [e["t"] for e in saved["events"]] == [3.04, 12.5]
    assert again["events"][1] == {"t": 12.5, "event": "bounce", "in": True}
    assert again["labelled_until_s"] == 30.0 and again["updated_at"] is not None


async def test_saving_replaces_the_previous_labels(client, match):
    url = f"/api/matches/{match['id']}/labels"
    await client.put(url, json={"events": [{"t": 1, "event": "hit"}]})
    await client.put(url, json={"events": [{"t": 2, "event": "bounce"}]})

    events = (await client.get(url)).json()["data"]["events"]

    assert events == [{"t": 2.0, "event": "bounce"}]


async def test_invalid_labels_are_refused(client, match):
    url = f"/api/matches/{match['id']}/labels"
    for bad in (
        {"events": [{"t": -1, "event": "hit"}]},
        {"events": [{"t": 1, "event": ""}]},
        {"events": [{"t": 1, "event": "hit", "extra": {"nested": True}}]},
        {"events": [{"t": 1, "event": "hit"}] * 20001},
    ):
        assert (await client.put(url, json=bad)).status_code == 422


async def test_export_is_the_benchmark_label_format(client, match):
    url = f"/api/matches/{match['id']}/labels"
    await client.put(url, json={"labelled_until_s": 20, "events": [{"t": 5, "event": "goal", "team": "home"}]})

    response = await client.get(url + "/export")

    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    exported = json.loads(response.text)
    assert exported["sport"] == "football"
    assert exported["labelled_until_s"] == 20
    assert exported["events"] == [{"t": 5.0, "event": "goal", "team": "home"}]
    assert match["name"] in exported["source"]


async def test_unknown_match(client):
    assert (await client.get("/api/matches/match_nope/labels")).status_code == 404


async def test_labels_need_a_signed_in_user(anon_client, match):
    assert (await anon_client.get(f"/api/matches/{match['id']}/labels")).status_code == 401


async def test_deleting_the_match_deletes_its_labels(client, match, app):
    from sqlalchemy import select

    from app.db.models import MatchLabels

    await client.put(f"/api/matches/{match['id']}/labels", json={"events": [{"t": 1, "event": "hit"}]})
    assert (await client.delete(f"/api/matches/{match['id']}")).status_code == 200

    async with app.state.session_factory() as db:
        assert (await db.scalars(select(MatchLabels))).all() == []
