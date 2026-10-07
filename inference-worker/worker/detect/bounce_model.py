"""Learned tennis bounce detector (CatBoost). Our own model, trained on
labelled matches with `python -m worker.training.bounce`, is preferred; the
TennisProject model (yastrebksv/TennisProject, no licence on the weights:
personal testing only, see docs/third-party.md) is the fallback.

The features reproduce the original `prepare_features` for one frame: for
lags 1 and 2 before and after, absolute x differences, signed y differences
and their ratios, in 1280x720 pixel coordinates.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from worker.logging import get_logger

log = get_logger(component="bounce_model")

DEFAULT_WEIGHTS = "tennis_bounce.cbm"
OWN_WEIGHTS = "tennis_bounce_own.cbm"  # its threshold and metrics are in the .json beside it
DEFAULT_PROBABILITY = 0.45
EPS = 1e-15

BounceScorer = Callable[[Sequence[tuple[float, float]]], float]


@dataclass(frozen=True, slots=True)
class BounceModel:
    scorer: BounceScorer
    probability: float  # a window scoring above this is a bounce
    name: str


def bounce_features(window: Sequence[tuple[float, float]]) -> list[float]:
    """window: 5 positions (t-2, t-1, t, t+1, t+2)."""
    (x_m2, y_m2), (x_m1, y_m1), (x, y), (x_p1, y_p1), (x_p2, y_p2) = window
    lag_x, lag_y = {1: x_m1, 2: x_m2}, {1: y_m1, 2: y_m2}
    inv_x, inv_y = {1: x_p1, 2: x_p2}, {1: y_p1, 2: y_p2}
    x_diff = {i: abs(lag_x[i] - x) for i in (1, 2)}
    x_diff_inv = {i: abs(inv_x[i] - x) for i in (1, 2)}
    y_diff = {i: lag_y[i] - y for i in (1, 2)}
    y_diff_inv = {i: inv_y[i] - y for i in (1, 2)}
    x_div = {i: abs(x_diff[i] / (x_diff_inv[i] + EPS)) for i in (1, 2)}
    y_div = {i: y_diff[i] / (y_diff_inv[i] + EPS) for i in (1, 2)}
    return [
        x_diff[1], x_diff[2], x_diff_inv[1], x_diff_inv[2], x_div[1], x_div[2],
        y_diff[1], y_diff[2], y_diff_inv[1], y_diff_inv[2], y_div[1], y_div[2],
    ]  # fmt: skip


def load_bounce_model(models_dir: Path) -> BounceModel | None:
    """Our own trained model when installed, else the TennisProject one; None
    (rule-based bounces) when neither can be loaded."""
    own = load_bounce_scorer(models_dir, OWN_WEIGHTS, quiet=True)
    if own is not None:
        return BounceModel(own, _own_threshold(models_dir / OWN_WEIGHTS), OWN_WEIGHTS)
    default = load_bounce_scorer(models_dir)
    return BounceModel(default, DEFAULT_PROBABILITY, DEFAULT_WEIGHTS) if default is not None else None


def _own_threshold(weights: Path) -> float:
    meta = weights.with_suffix(".json")
    try:
        threshold = float(json.loads(meta.read_text())["threshold"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        log.warning("bounce model threshold unreadable; using the default", meta=str(meta), error=str(exc))
        return DEFAULT_PROBABILITY
    return threshold if 0.0 < threshold < 1.0 else DEFAULT_PROBABILITY


def load_bounce_scorer(models_dir: Path, name: str = DEFAULT_WEIGHTS, quiet: bool = False) -> BounceScorer | None:
    """None (rule-based bounces) when the model or catboost is not installed."""
    path = models_dir / name
    if not path.is_file():
        if quiet:
            return None
        log.info("bounce model not installed; using the rule-based bounce detector", expected=str(path))
        return None
    try:
        import catboost
    except ImportError:
        log.warning("catboost not installed; using the rule-based bounce detector")
        return None
    model = catboost.CatBoostRegressor()
    model.load_model(str(path))
    log.info("bounce model loaded", weights=str(path))

    def score(window: Sequence[tuple[float, float]]) -> float:
        if len(window) != 5:
            return 0.0
        return float(model.predict([bounce_features(window)])[0])

    return score
