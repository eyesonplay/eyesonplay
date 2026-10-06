"""Accuracy benchmark: score detected events against hand-labelled ground truth.

Labels (JSON):

    {
      "sport": "tennis",
      "source": "free text: which video, who labelled it",
      "labelled_until_s": 120.0,
      "events": [
        {"t": 0.48, "event": "serve", "player": "near"},
        {"t": 0.80, "event": "bounce", "in": true}
      ]
    }

Only event types that appear in the labels are scored, and only detections up
to `labelled_until_s` (default: the last label plus the tolerance). A detection
matches the closest unmatched label of the same type within the time tolerance.
Any other label field (`in`, `player`, `winner`, `corner`, …) is compared on
matched pairs and reported as attribute accuracy.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_TOLERANCE_S = 0.5
_TIME_KEYS = ("t", "event")


@dataclass(frozen=True)
class TypeScore:
    true_positives: int
    false_positives: int
    false_negatives: int
    mean_abs_offset_s: float | None
    attribute_accuracy: dict[str, float] = field(default_factory=dict)

    @property
    def precision(self) -> float:
        found = self.true_positives + self.false_positives
        return self.true_positives / found if found else 0.0

    @property
    def recall(self) -> float:
        labelled = self.true_positives + self.false_negatives
        return self.true_positives / labelled if labelled else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "precision": self.precision, "recall": self.recall, "f1": self.f1}


@dataclass(frozen=True)
class Report:
    tolerance_s: float
    labelled_until_s: float
    by_type: dict[str, TypeScore]

    def to_dict(self) -> dict[str, Any]:
        return {
            "tolerance_s": self.tolerance_s,
            "labelled_until_s": self.labelled_until_s,
            "by_type": {name: s.to_dict() for name, s in self.by_type.items()},
        }


def load_labels(path: Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text())
    events = data.get("events") if isinstance(data, dict) else None
    if not isinstance(events, list):
        raise ValueError("labels need an 'events' list")
    for i, label in enumerate(events):
        if not isinstance(label, dict) or not isinstance(label.get("t"), (int, float)) or not label.get("event"):
            raise ValueError(f"label {i} needs a numeric 't' (seconds) and an 'event' type")
    return data


def load_predictions(path: Path) -> list[dict[str, Any]]:
    """Events as exported by the dashboard (a JSON array), an API response
    (`{"data": [...]}`) or event records (`{"payload": {...}}`)."""
    data = json.loads(Path(path).read_text())
    items = data.get("data", []) if isinstance(data, dict) else data
    return [item.get("payload", item) for item in items if isinstance(item, dict)]


def score(
    labels: dict[str, Any], predictions: list[dict[str, Any]], tolerance_s: float = DEFAULT_TOLERANCE_S
) -> Report:
    truth = labels["events"]
    until = float(labels.get("labelled_until_s") or (max((lbl["t"] for lbl in truth), default=0.0) + tolerance_s))
    labelled_types = {lbl["event"] for lbl in truth}
    by_type: dict[str, TypeScore] = {}
    grouped_truth: dict[str, list[dict[str, Any]]] = defaultdict(list)
    grouped_pred: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for lbl in truth:
        grouped_truth[lbl["event"]].append(lbl)
    for pred in predictions:
        t = pred.get("video_timestamp")
        if pred.get("event") in labelled_types and isinstance(t, (int, float)) and t <= until:
            grouped_pred[pred["event"]].append(pred)
    for kind in sorted(labelled_types):
        by_type[kind] = _score_type(grouped_truth[kind], grouped_pred[kind], tolerance_s)
    return Report(tolerance_s=tolerance_s, labelled_until_s=until, by_type=by_type)


def _score_type(truth: list[dict[str, Any]], preds: list[dict[str, Any]], tolerance_s: float) -> TypeScore:
    # Closest pairs first, each label and detection used once.
    pairs = sorted(
        (abs(p["video_timestamp"] - lbl["t"]), li, pi)
        for li, lbl in enumerate(truth)
        for pi, p in enumerate(preds)
        if abs(p["video_timestamp"] - lbl["t"]) <= tolerance_s
    )
    used_labels: set[int] = set()
    used_preds: set[int] = set()
    matched: list[tuple[float, dict[str, Any], dict[str, Any]]] = []
    for offset, li, pi in pairs:
        if li in used_labels or pi in used_preds:
            continue
        used_labels.add(li)
        used_preds.add(pi)
        matched.append((offset, truth[li], preds[pi]))
    return TypeScore(
        true_positives=len(matched),
        false_positives=len(preds) - len(matched),
        false_negatives=len(truth) - len(matched),
        mean_abs_offset_s=sum(o for o, _, _ in matched) / len(matched) if matched else None,
        attribute_accuracy=_attribute_accuracy(matched),
    )


def _attribute_accuracy(matched: list[tuple[float, dict[str, Any], dict[str, Any]]]) -> dict[str, float]:
    hits: dict[str, list[bool]] = defaultdict(list)
    for _, lbl, pred in matched:
        for key, expected in lbl.items():
            if key not in _TIME_KEYS:
                hits[key].append(pred.get(key) == expected)
    return {key: sum(v) / len(v) for key, v in sorted(hits.items())}
