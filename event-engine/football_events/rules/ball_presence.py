"""ball_detected / ball_lost with a debounce so a single missed frame is ignored."""

from __future__ import annotations

from football_events.context import FrameContext
from football_events.types import EventDraft, EventType


class BallPresenceRule:
    def __init__(self) -> None:
        self._missing = 0
        self._visible = False

    def update(self, ctx: FrameContext) -> list[EventDraft]:
        ball = ctx.ball
        if ball is not None:
            self._missing = 0
            if self._visible:
                return []
            self._visible = True
            return [EventDraft(EventType.BALL_DETECTED, ball.confidence)]

        self._missing += 1
        if self._visible and self._missing >= ctx.config.ball_lost_after_frames:
            self._visible = False
            return [EventDraft(EventType.BALL_LOST, 1.0, {"missing_frames": self._missing})]
        return []
