"""Pick the two tennis players among all detected people (umpire, line judges,
ball kids and spectators are people too)."""

from __future__ import annotations

from collections.abc import Callable

from football_events import Point
from worker.track.player_tracker import TrackedObject

# Players stand on the court or up to ~6 m behind the baselines / ~3 m outside
# the doubles sidelines (normalised units).
COURT_AREA_X = (-30.0, 130.0)
COURT_AREA_Y = (-28.0, 128.0)


def select_tennis_players(
    people: list[TrackedObject], foot_on_court: Callable[[TrackedObject], Point | None], frame_height: int
) -> list[TrackedObject]:
    """At most one player per half: the person nearest the centre of that half.
    Without court calibration, the largest person in the lower and upper part
    of the frame."""
    located = [(p, foot_on_court(p)) for p in people if p.cls == "player"]
    if located and all(court is not None for _, court in located):
        chosen = []
        for near_half in (True, False):
            candidates = [
                (p, c)
                for p, c in located
                if c is not None
                and COURT_AREA_X[0] <= c.x <= COURT_AREA_X[1]
                and COURT_AREA_Y[0] <= c.y <= COURT_AREA_Y[1]
                and (c.x < 50) == near_half
            ]
            if candidates:
                centre_x = 10.0 if near_half else 90.0
                chosen.append(min(candidates, key=lambda pc: abs(pc[1].y - 50) + abs(pc[1].x - centre_x) * 0.5)[0])
        return chosen
    # Uncalibrated fallback: biggest person in each half of the frame.
    halves: list[TrackedObject] = []
    for lower in (True, False):
        group = [p for p, _ in located if ((p.bbox[3] > frame_height * 0.55) == lower)]
        if group:
            halves.append(max(group, key=lambda p: (p.bbox[3] - p.bbox[1]) * p.confidence))
    return halves
