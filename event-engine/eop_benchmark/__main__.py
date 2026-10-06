"""python -m eop_benchmark LABELS.json EVENTS.json [--tolerance 0.5] [--json]"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from eop_benchmark import DEFAULT_TOLERANCE_S, Report, load_labels, load_predictions, score


def _table(report: Report) -> str:
    rows = [f"{'event':<16}{'labels':>7}{'found':>7}{'prec':>7}{'recall':>8}{'F1':>7}{'Δt (s)':>8}  details"]
    for kind, s in report.by_type.items():
        offset = f"{s.mean_abs_offset_s:.2f}" if s.mean_abs_offset_s is not None else "—"
        details = ", ".join(f"{k} {v:.0%}" for k, v in s.attribute_accuracy.items())
        rows.append(
            f"{kind:<16}{s.true_positives + s.false_negatives:>7}{s.true_positives + s.false_positives:>7}"
            f"{s.precision:>7.0%}{s.recall:>8.0%}{s.f1:>7.2f}{offset:>8}  {details}"
        )
    rows.append(f"\ntolerance ±{report.tolerance_s} s, scored up to {report.labelled_until_s:.1f} s of video")
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m eop_benchmark", description="Score detected events against labels.")
    parser.add_argument("labels", type=Path, help="hand-labelled ground truth (JSON)")
    parser.add_argument("events", type=Path, help="detected events: the dashboard's JSON export")
    parser.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE_S, help="seconds (default 0.5)")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args(argv)
    try:
        report = score(load_labels(args.labels), load_predictions(args.events), args.tolerance)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report.to_dict(), indent=2) if args.json else _table(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
