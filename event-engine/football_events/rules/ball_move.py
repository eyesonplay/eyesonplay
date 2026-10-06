"""ball_move: throttled position updates, only when the ball actually moved."""

from __future__ import annotations

from football_events.context import FrameContext
from football_events.geometry import Space, distance
from football_events.types import EventDraft, EventType, Point


class BallMoveRule:
    def __init__(self) -> None:
        self._last_t: float | None = None
        self._last_pos: Point | None = None
        self._last_space: Space | None = None

    def update(self, ctx: FrameContext) -> list[EventDraft]:
        ball, pos, space = ctx.ball, ctx.ball_pos, ctx.space
        if ball is None or pos is None or space is None or ball.predicted:
            return []
        cfg = ctx.config
        if self._last_t is not None and ctx.t - self._last_t < cfg.ball_move_min_interval_s:
            return []
        if (
            self._last_pos is not None
            and self._last_space is space
            and distance(pos, self._last_pos) < cfg.ball_move_min_distance.for_space(space)
        ):
            return []
        self._last_t, self._last_pos, self._last_space = ctx.t, pos, space
        details: dict[str, object] = {"coordinate_space": space.value}
        if ctx.velocity is not None:
            details["velocity"] = ctx.velocity.to_dict()
            details["speed"] = round(ctx.speed, 2)
        return [EventDraft(EventType.BALL_MOVE, ball.confidence, details)]
