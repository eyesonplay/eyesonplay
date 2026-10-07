"""Train the bounce model: a CatBoost regressor on the 12 bounce features (the
same model type and features the worker loads, see worker.detect.bounce_model).

The decision threshold is chosen on the last part of the training windows
(in time order), then the model is refitted on all of them.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from worker.detect.bounce_model import OWN_WEIGHTS, bounce_features
from worker.training.dataset import Window

VALIDATION_FRACTION = 0.2
MAX_POSITIVE_WEIGHT = 10.0  # bounces are rare: weigh them up, within reason
THRESHOLDS = tuple(round(0.05 * i, 2) for i in range(2, 19))  # 0.10 … 0.90
MIN_POSITIVES = 5


@dataclass(frozen=True, slots=True)
class WindowScore:
    threshold: float
    precision: float
    recall: float
    f1: float

    def to_dict(self) -> dict[str, float]:
        return {"threshold": self.threshold, "precision": self.precision, "recall": self.recall, "f1": self.f1}


@dataclass(frozen=True)
class TrainedBounceModel:
    model: Any  # catboost.CatBoostRegressor
    threshold: float
    validation: WindowScore
    windows: int
    positives: int

    def save(self, models_dir: Path, metadata: dict[str, Any]) -> Path:
        models_dir.mkdir(parents=True, exist_ok=True)
        weights = models_dir / OWN_WEIGHTS
        self.model.save_model(str(weights))
        meta = {
            "threshold": self.threshold,
            "trained_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "windows": self.windows,
            "positives": self.positives,
            "validation": self.validation.to_dict(),
            **metadata,
        }
        weights.with_suffix(".json").write_text(json.dumps(meta, indent=2))
        return weights


def train_bounce_model(
    windows: Sequence[Window], targets: Sequence[int], iterations: int = 800, seed: int = 0
) -> TrainedBounceModel:
    positives = sum(targets)
    if positives < MIN_POSITIVES or positives == len(targets):
        raise ValueError(f"need at least {MIN_POSITIVES} labelled bounces and some non-bounces, got {positives}")
    cut = int(len(windows) * (1 - VALIDATION_FRACTION))
    probe = _fit(windows[:cut], targets[:cut], iterations, seed)
    validation = best_threshold(predict(probe, windows[cut:]), targets[cut:])
    model = _fit(windows, targets, iterations, seed)
    return TrainedBounceModel(model, validation.threshold, validation, len(windows), positives)


def best_threshold(scores: Sequence[float], targets: Sequence[int]) -> WindowScore:
    results = [window_score(scores, targets, t) for t in THRESHOLDS]
    return max(results, key=lambda r: (r.f1, r.threshold))


def window_score(scores: Sequence[float], targets: Sequence[int], threshold: float) -> WindowScore:
    pairs = list(zip(scores, targets, strict=True))
    tp = sum(1 for s, y in pairs if s > threshold and y)
    fp = sum(1 for s, y in pairs if s > threshold and not y)
    fn = sum(1 for s, y in pairs if s <= threshold and y)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return WindowScore(threshold, round(precision, 4), round(recall, 4), round(f1, 4))


def predict(model: Any, windows: Sequence[Window]) -> list[float]:
    if not windows:
        return []
    return [float(p) for p in model.predict([bounce_features(w.points) for w in windows])]


def _fit(windows: Sequence[Window], targets: Sequence[int], iterations: int, seed: int) -> Any:
    from catboost import CatBoostRegressor

    positives = sum(targets)
    weight = min(MAX_POSITIVE_WEIGHT, (len(targets) - positives) / max(positives, 1))
    model = CatBoostRegressor(
        iterations=iterations, depth=6, random_seed=seed, verbose=False, allow_writing_files=False
    )
    model.fit(
        [bounce_features(w.points) for w in windows],
        list(targets),
        sample_weight=[weight if y else 1.0 for y in targets],
    )
    return model
