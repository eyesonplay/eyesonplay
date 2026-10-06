"""shot_candidate / shot heuristic.

Conditions: a speed spike shortly after a player's last touch. With pitch
coordinates the trajectory must also head into the goal mouth within
`shot_max_distance_m`; only then can confidence reach the `shot` threshold.
Without pitch coordinates the goal direction is unknown, so the result is a
low-confidence `shot_candidate` and never a `shot`.
"""

from __future__ import annotations

from dataclasses import dataclass

from football_events.context import FrameContext
from football_events.geometry import (
    GOAL_HALF_WIDTH_M,
    PITCH_LENGTH_M,
    PITCH_WIDTH_M,
    Space,
    location_dict,
)
from football_events.types import EventDraft, EventType, Point

GOAL_TOLERANCE_M = 2.0


@dataclass(frozen=True, slots=True)
class GoalAlignment:
    side: str
    alignment: float  # 1.0 = dead centre of the goal mouth
    distance_m: float


class ShotRule:
    def __init__(self) -> None:
        self._last_touch_reported: int | None = None

    def update(self, ctx: FrameContext) -> list[EventDraft]:
        state, cfg = ctx.possession, ctx.config
        if ctx.ball is None or ctx.ball.predicted or ctx.velocity is None or ctx.space is None:
            return []
        if state.last_holder is None or state.last_touch_time is None or state.last_touch_ball is None:
            return []
        if ctx.t - state.last_touch_time > cfg.shot_origin_window_s:
            return []
        if state.last_touch_frame == self._last_touch_reported:
            return []
        min_speed = cfg.shot_min_speed.for_space(ctx.space)
        if ctx.speed < min_speed:
            return []

        details: dict[str, object] = {
            "track_id": state.last_holder,
            "location": location_dict(state.last_touch_ball),
            "speed": round(ctx.speed, 2),
            "speed_unit": "m/s" if ctx.space is Space.PITCH else "px/s",
        }
        speed_factor = min(1.0, (ctx.speed - min_speed) / min_speed)

        if ctx.space is Space.PIXEL:
            confidence = round(min(cfg.shot_no_pitch_max_confidence, 0.25 + 0.15 * speed_factor), 3)
            self._last_touch_reported = state.last_touch_frame
            details["reason"] = "speed_spike_without_pitch_calibration"
            return [EventDraft(EventType.SHOT_CANDIDATE, confidence, details)]

        assert ctx.ball_pos is not None
        aim = goal_alignment(ctx.ball_pos, ctx.velocity, cfg.shot_max_distance_m)
        if aim is None:
            return []
        self._last_touch_reported = state.last_touch_frame
        confidence = round(min(0.97, 0.45 + 0.3 * speed_factor + 0.25 * aim.alignment), 3)
        details.update(target_goal=aim.side, distance_to_goal_m=round(aim.distance_m, 1))
        drafts = [EventDraft(EventType.SHOT_CANDIDATE, confidence, details)]
        if confidence >= cfg.shot_confirm_confidence:
            drafts.append(EventDraft(EventType.SHOT, confidence, dict(details)))
        return drafts


def goal_alignment(pos_m: Point, velocity: Point, max_distance_m: float) -> GoalAlignment | None:
    """Where the current trajectory crosses the goal line, if it hits the goal mouth."""
    if abs(velocity.x) < 1e-6:
        return None
    goal_x = PITCH_LENGTH_M if velocity.x > 0 else 0.0
    dx = goal_x - pos_m.x
    if abs(dx) > max_distance_m:
        return None
    y_at_line = pos_m.y + velocity.y * (dx / velocity.x)
    tolerance = GOAL_HALF_WIDTH_M + GOAL_TOLERANCE_M
    offset = abs(y_at_line - PITCH_WIDTH_M / 2)
    if offset > tolerance:
        return None
    return GoalAlignment("right" if velocity.x > 0 else "left", 1.0 - offset / tolerance, abs(dx))
