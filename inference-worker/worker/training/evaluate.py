"""Evaluate a bounce detector the way it is used: replay recorded detections
through the tennis event engine and score its events against the labels
(with the accuracy benchmark, eop_benchmark)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from eop_benchmark import score
from football_events.types import FrameObservation
from tennis_events import TennisEventEngine
from tennis_events.config import TennisConfig

from worker.detect.bounce_model import BounceModel
from worker.training.dataset import labelled_until


def replay(
    observations: Sequence[FrameObservation], frame_height_px: float, model: BounceModel | None
) -> list[dict[str, Any]]:
    """Events the engine finds on these detections; `model` None is the built-in rule."""
    learned = {"bounce_scorer": model.scorer, "bounce_probability": model.probability} if model else {}
    engine = TennisEventEngine("training", TennisConfig(frame_height_px=frame_height_px, **learned))
    return [event.to_payload() for obs in observations for event in engine.update(obs)]


def score_span(labels: dict[str, Any], predictions: Sequence[dict[str, Any]], start: float) -> dict[str, Any]:
    """Benchmark report over the labelled span from `start` on."""
    end = labelled_until(labels)
    span = {**labels, "labelled_until_s": end, "events": [e for e in labels["events"] if start <= e["t"] <= end]}
    found = [
        p for p in predictions if isinstance(p.get("video_timestamp"), (int, float)) and p["video_timestamp"] >= start
    ]
    return score(span, found).to_dict()
