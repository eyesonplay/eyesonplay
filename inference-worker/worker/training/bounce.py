"""Train our own tennis bounce model from labelled matches.

    python -m worker.training.bounce \\
        --pair match1.mp4 match1-labels.json --pair match2.mp4 match2-labels.json

Each video is analysed once by the real pipeline (cached), the first part of
each labelled span trains the model and the last part (--held-out) is kept
for evaluation. On that held-out part the event engine is replayed with the
built-in rule, the installed TennisProject model (when present) and the new
model, and their events are scored against the labels. The new model is
saved (tennis_bounce_own.cbm + .json) only if its bounce F1 is at least the
best of the others, unless --force; the worker then uses it automatically.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eop_benchmark import load_labels
from football_events.types import FrameObservation

from worker.config import WorkerSettings
from worker.detect.bounce_model import (
    DEFAULT_PROBABILITY,
    DEFAULT_WEIGHTS,
    OWN_WEIGHTS,
    BounceModel,
    BounceScorer,
    load_bounce_scorer,
)
from worker.device import select_device
from worker.training.dataset import Window, ball_windows, bounce_times, in_span, label_windows, split_point
from worker.training.evaluate import replay, score_span
from worker.training.extract import Recording, cached_record
from worker.training.model import TrainedBounceModel, predict, train_bounce_model

DEFAULT_CACHE = Path.home() / ".pitchside" / "training"
DEFAULT_MODELS = Path.home() / ".pitchside" / "models"
RULES = "rules"
SCORED_FIELDS = ("true_positives", "false_positives", "false_negatives")

Results = dict[str, dict[str, dict[str, float]]]  # detector -> event type -> counts and scores


@dataclass(frozen=True)
class LabelledVideo:
    video: Path
    labels: dict[str, Any]
    recording: Recording
    split_s: float


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if not 0.0 < args.held_out < 1.0:
            raise ValueError("--held-out must be between 0 and 1")
        videos = [_load(Path(v), Path(lbl), args) for v, lbl in args.pair]
        trained = _train(videos, args.iterations)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    results = _evaluate(videos, trained, args.models_dir)
    _print_results(trained, results)
    return _save(trained, results, videos, args)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m worker.training.bounce", description="Train the tennis bounce model.")
    p.add_argument("--pair", nargs=2, action="append", required=True, metavar=("VIDEO", "LABELS"))
    p.add_argument("--models-dir", type=Path, default=DEFAULT_MODELS, help="TrackNet/YOLO/bounce weights")
    p.add_argument("--output-dir", type=Path, help="where to save the new model (default: --models-dir)")
    p.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE, help="recorded detections")
    p.add_argument("--fps", type=int, default=25, help="processing FPS (tennis needs 25)")
    p.add_argument("--player-model", default="yolov8n", help="YOLO weights for players")
    p.add_argument("--held-out", type=float, default=0.25, help="last fraction of each labelled span for evaluation")
    p.add_argument("--iterations", type=int, default=800)
    p.add_argument("--force", action="store_true", help="save even if not better than the installed models")
    return p


def _load(video: Path, labels_path: Path, args: argparse.Namespace) -> LabelledVideo:
    if not video.is_file():
        raise ValueError(f"video not found: {video}")
    labels = load_labels(labels_path)
    if labels.get("sport", "tennis") != "tennis":
        raise ValueError(f"{labels_path} labels a {labels['sport']} match, not tennis")
    if not bounce_times(labels, 0.0, float("inf")):
        raise ValueError(f"{labels_path} has no bounce labels")
    settings = WorkerSettings(inference_mode="real", models_dir=args.models_dir, media_dir=video.parent)
    recording = cached_record(video, args.cache_dir, settings, select_device("real"), args.fps, args.player_model)
    return LabelledVideo(video, labels, recording, split_point(labels, args.held_out))


def _train(videos: Sequence[LabelledVideo], iterations: int) -> TrainedBounceModel:
    windows: list[Window] = []
    targets: list[int] = []
    for v in videos:
        train = in_span(ball_windows(v.recording.observations, v.recording.frame_height), 0.0, v.split_s)
        kept, labels = label_windows(train, bounce_times(v.labels, 0.0, v.split_s))
        windows += kept
        targets += labels
        print(f"{v.video.name}: {len(kept)} training windows, {sum(labels)} bounces (until {v.split_s:.0f} s)")
    return train_bounce_model(windows, targets, iterations=iterations)


def _evaluate(videos: Sequence[LabelledVideo], trained: TrainedBounceModel, models_dir: Path) -> Results:
    candidates: dict[str, BounceModel | None] = {RULES: None}
    existing = load_bounce_scorer(models_dir, DEFAULT_WEIGHTS, quiet=True)
    if existing is not None:
        candidates[DEFAULT_WEIGHTS] = BounceModel(existing, DEFAULT_PROBABILITY, DEFAULT_WEIGHTS)
    candidates[OWN_WEIGHTS] = BounceModel(_scorer(trained), trained.threshold, OWN_WEIGHTS)
    return {name: _combine([_held_out_report(v, model) for v in videos]) for name, model in candidates.items()}


def _held_out_report(v: LabelledVideo, model: BounceModel | None) -> dict[str, Any]:
    held_out: list[FrameObservation] = [obs for obs in v.recording.observations if obs.video_ts >= v.split_s]
    return score_span(v.labels, replay(held_out, v.recording.frame_height, model), v.split_s)


def _scorer(trained: TrainedBounceModel) -> BounceScorer:
    def score(points: Sequence[tuple[float, float]]) -> float:
        return predict(trained.model, [Window(0.0, tuple(points))])[0] if len(points) == 5 else 0.0

    return score


def _combine(reports: Sequence[dict[str, Any]]) -> dict[str, dict[str, float]]:
    counts: dict[str, dict[str, int]] = defaultdict(lambda: dict.fromkeys(SCORED_FIELDS, 0))
    for report in reports:
        for kind, s in report["by_type"].items():
            for f in SCORED_FIELDS:
                counts[kind][f] += s[f]
    return {kind: {**c, **_prf(c)} for kind, c in sorted(counts.items())}


def _prf(c: dict[str, int]) -> dict[str, float]:
    tp, fp, fn = c["true_positives"], c["false_positives"], c["false_negatives"]
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}


def _print_results(trained: TrainedBounceModel, results: Results) -> None:
    v = trained.validation
    print(
        f"\nwindows {trained.windows} ({trained.positives} bounces); threshold {trained.threshold} "
        f"(validation windows: precision {v.precision:.0%}, recall {v.recall:.0%})"
    )
    print("\nheld-out events (engine replay)")
    print(f"{'detector':24} {'event':12} {'labels':>6} {'found':>6} {'prec':>6} {'recall':>7} {'F1':>6}")
    for name, by_type in results.items():
        for kind, s in by_type.items():
            labels = int(s["true_positives"] + s["false_negatives"])
            found = int(s["true_positives"] + s["false_positives"])
            print(
                f"{name:24} {kind:12} {labels:>6} {found:>6} {s['precision']:>6.0%} {s['recall']:>7.0%} {s['f1']:>6.2f}"
            )


def _bounce_f1(by_type: dict[str, dict[str, float]]) -> float:
    return by_type.get("bounce", {}).get("f1", 0.0)


def _save(
    trained: TrainedBounceModel, results: Results, videos: Sequence[LabelledVideo], args: argparse.Namespace
) -> int:
    own = _bounce_f1(results[OWN_WEIGHTS])
    best_other = max(_bounce_f1(r) for name, r in results.items() if name != OWN_WEIGHTS)
    if own < best_other and not args.force:
        print(f"\nnot saved: bounce F1 {own:.2f} is below {best_other:.2f}; label more, or use --force")
        return 1
    meta = {
        "source": [{"video": v.video.name, "labels": v.labels.get("source", "")} for v in videos],
        "held_out": args.held_out,
        "fps": args.fps,
        "evaluation": results,
    }
    path = trained.save(args.output_dir or args.models_dir, meta)
    print(f"\nsaved {path} (the worker uses it from the next match)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
