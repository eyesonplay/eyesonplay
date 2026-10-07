"""Bounce training data: windows of ball positions exactly as the event engine
sees them, labelled from a hand-labelled match.

The tennis engine scores each run of WINDOW consecutive detected (not
predicted) ball positions, at 720p scale, for a bounce at the middle one; a
gap longer than MAX_GAP_S starts a new run. The same windows are built here,
so the trained model is used on the inputs it was trained on.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from football_events.types import FrameObservation
from tennis_events.trajectory import MAX_GAP_S, WINDOW

SCORER_HEIGHT_PX = 720.0
POSITIVE_TOLERANCE_S = 0.12  # a label this close to a window centre marks that window
DUPLICATE_GAP_S = 0.4  # a ball cannot bounce twice this quickly: closer labels are one bounce


@dataclass(frozen=True, slots=True)
class Window:
    t: float  # video time of the middle position
    points: tuple[tuple[float, float], ...]  # WINDOW positions, 720p pixels


def ball_windows(observations: Iterable[FrameObservation], frame_height_px: float) -> list[Window]:
    scale = SCORER_HEIGHT_PX / frame_height_px
    run: deque[tuple[float, float, float]] = deque(maxlen=WINDOW)
    windows: list[Window] = []
    for obs in observations:
        ball = obs.ball
        if ball is None or ball.predicted:
            continue
        if run and obs.video_ts - run[-1][0] > MAX_GAP_S:
            run.clear()
        run.append((obs.video_ts, ball.pixel.x * scale, ball.pixel.y * scale))
        if len(run) == WINDOW:
            windows.append(Window(run[WINDOW // 2][0], tuple((x, y) for _, x, y in run)))
    return windows


def label_windows(
    windows: Sequence[Window], bounces: Sequence[float], tolerance_s: float = POSITIVE_TOLERANCE_S
) -> tuple[list[Window], list[int]]:
    """The window nearest each labelled bounce is a positive; other windows
    within the tolerance are left out (a frame either side of a bounce is
    neither clearly one nor clearly not); the rest are negatives."""
    nearest: set[int] = set()
    near: set[int] = set()
    for t in bounces:
        close = [i for i, w in enumerate(windows) if abs(w.t - t) <= tolerance_s]
        if close:
            nearest.add(min(close, key=lambda i: abs(windows[i].t - t)))
            near.update(close)
    kept = [(w, int(i in nearest)) for i, w in enumerate(windows) if i in nearest or i not in near]
    return [w for w, _ in kept], [y for _, y in kept]


def bounce_times(labels: dict[str, Any], start: float, end: float) -> list[float]:
    """Labelled bounces in [start, end); a bounce labelled twice (a double key
    press, a second pass) counts once, at the mean of its labels."""
    times = sorted(float(e["t"]) for e in labels["events"] if e["event"] == "bounce")
    groups: list[list[float]] = []
    for t in times:
        if groups and t - groups[-1][-1] < DUPLICATE_GAP_S:
            groups[-1].append(t)
        else:
            groups.append([t])
    merged = [sum(g) / len(g) for g in groups]
    return [t for t in merged if start <= t < end]


def labelled_until(labels: dict[str, Any]) -> float:
    explicit = labels.get("labelled_until_s")
    if isinstance(explicit, (int, float)) and explicit > 0:
        return float(explicit)
    return max((float(e["t"]) for e in labels["events"]), default=0.0)


def split_point(labels: dict[str, Any], held_out: float) -> float:
    """Video time from which the labelled span is held out for evaluation
    (the end of a match, never seen in training)."""
    return labelled_until(labels) * (1.0 - held_out)


def in_span(windows: Iterable[Window], start: float, end: float) -> list[Window]:
    return [w for w in windows if start <= w.t < end]
