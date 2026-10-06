"""ball_out: only from pitch coordinates. Without calibration we cannot know
where the touchlines are, so nothing is emitted."""

from __future__ import annotations

from football_events.context import FrameContext
from football_events.geometry import GOAL_HALF_WIDTH_M, PITCH_WIDTH_M, location_dict
from football_events.types import EventDraft, EventType, Point

_GOAL_MOUTH_HALF_NORM = GOAL_HALF_WIDTH_M / PITCH_WIDTH_M * 100


class BallOutRule:
    def __init__(self) -> None:
        self._out_frames = 0
        self._reported = False

    def update(self, ctx: FrameContext) -> list[EventDraft]:
        ball = ctx.ball
        if ball is None or ball.pitch is None:
            return []
        side = out_side(ball.pitch, ctx.config.ball_out_margin)
        if side is None:
            self._out_frames, self._reported = 0, False
            return []
        self._out_frames += 1
        if self._reported or self._out_frames < ctx.config.ball_out_frames:
            return []
        self._reported = True
        over_goal_line = side in ("left", "right")
        return [
            EventDraft(
                EventType.BALL_OUT,
                round(ball.confidence * 0.9, 3),
                {
                    "side": side,
                    "location": location_dict(ball),
                    "last_touch_track_id": ctx.possession.last_holder,
                    "within_goal_mouth": over_goal_line and abs(ball.pitch.y - 50) <= _GOAL_MOUTH_HALF_NORM,
                },
            )
        ]


def out_side(p: Point, margin: float) -> str | None:
    if p.x < -margin:
        return "left"
    if p.x > 100 + margin:
        return "right"
    if p.y < -margin:
        return "top"
    if p.y > 100 + margin:
        return "bottom"
    return None
