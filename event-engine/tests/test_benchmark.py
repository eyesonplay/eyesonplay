"""Scoring detected events against hand-labelled ground truth."""

from __future__ import annotations

import json

import pytest

from eop_benchmark import load_labels, load_predictions, score
from eop_benchmark.__main__ import main


def labels(*events, **extra):
    return {"sport": "tennis", "events": list(events), **extra}


def ev(t, event, **fields):
    return {"video_timestamp": t, "event": event, **fields}


def test_perfect_detection_scores_one():
    truth = labels({"t": 1.0, "event": "serve"}, {"t": 1.6, "event": "bounce", "in": True})

    report = score(truth, [ev(1.02, "serve"), ev(1.55, "bounce", **{"in": True})])

    assert report.by_type["serve"].precision == report.by_type["serve"].recall == 1.0
    assert report.by_type["bounce"].f1 == 1.0


def test_events_must_be_close_in_time():
    truth = labels({"t": 5.0, "event": "hit"}, {"t": 9.0, "event": "hit"}, labelled_until_s=20.0)

    report = score(truth, [ev(5.3, "hit"), ev(9.8, "hit")], tolerance_s=0.5)

    hit = report.by_type["hit"]
    assert (hit.true_positives, hit.false_positives, hit.false_negatives) == (1, 1, 1)
    assert hit.mean_abs_offset_s == pytest.approx(0.3)


def test_each_label_matches_one_detection_only():
    truth = labels({"t": 2.0, "event": "bounce"})

    report = score(truth, [ev(1.9, "bounce"), ev(2.05, "bounce")])

    bounce = report.by_type["bounce"]
    assert (bounce.true_positives, bounce.false_positives) == (1, 1)
    assert bounce.mean_abs_offset_s == pytest.approx(0.05)  # the closer one was matched


def test_labelled_details_are_checked_on_matched_events():
    truth = labels({"t": 3.0, "event": "bounce", "in": False}, {"t": 4.0, "event": "bounce", "in": True})

    report = score(truth, [ev(3.0, "bounce", **{"in": True}), ev(4.0, "bounce", **{"in": True})])

    bounce = report.by_type["bounce"]
    assert bounce.recall == 1.0  # both bounces found...
    assert bounce.attribute_accuracy == {"in": 0.5}  # ...but one called wrong


def test_only_labelled_event_types_and_span_are_scored():
    truth = labels({"t": 1.0, "event": "serve"}, labelled_until_s=10.0)

    report = score(truth, [ev(1.0, "serve"), ev(2.0, "ball_move"), ev(30.0, "serve")])

    assert set(report.by_type) == {"serve"}
    assert report.by_type["serve"].false_positives == 0  # 30 s is outside the labelled span


def test_predictions_load_from_export_api_envelope_or_records(tmp_path):
    payloads = [ev(1.0, "serve")]
    for content in (payloads, {"data": payloads}, {"data": [{"payload": payloads[0]}]}):
        path = tmp_path / "p.json"
        path.write_text(json.dumps(content))
        assert load_predictions(path) == payloads


def test_labels_are_validated(tmp_path):
    path = tmp_path / "labels.json"
    path.write_text(json.dumps({"events": [{"event": "serve"}]}))

    with pytest.raises(ValueError, match="t"):
        load_labels(path)


def test_cli_prints_a_table_and_json(tmp_path, capsys):
    (tmp_path / "labels.json").write_text(json.dumps(labels({"t": 1.0, "event": "serve"})))
    (tmp_path / "events.json").write_text(json.dumps([ev(1.1, "serve")]))

    assert main([str(tmp_path / "labels.json"), str(tmp_path / "events.json")]) == 0
    assert "serve" in capsys.readouterr().out

    assert main([str(tmp_path / "labels.json"), str(tmp_path / "events.json"), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["by_type"]["serve"]["f1"] == 1.0
