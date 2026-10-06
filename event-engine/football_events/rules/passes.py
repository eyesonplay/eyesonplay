"""pass_candidate / pass.

Player A holds the ball, the ball leaves A, travels at least
`pass_min_distance` and player B (B != A) gains confirmed possession within
`pass_max_duration_s`. Each (from, to, release frame) is emitted once.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from football_events.context import FrameContext, PossessionState
from football_events.geometry import Space, ball_position, distance, location_dict
from football_events.types import BallObservation, EventDraft, EventType


@dataclass(frozen=True, slots=True)
class _PendingPass:
    from_track_id: int
    start_ball: BallObservation
    start_t: float
    start_frame: int
    candidate_emitted: bool = False


class PassRule:
    def __init__(self) -> None:
        self._prev = PossessionState()
        self._pending: _PendingPass | None = None
        self._emitted: set[tuple[int, int, int]] = set()

    def update(self, ctx: FrameContext) -> list[EventDraft]:
        state = ctx.possession
        drafts: list[EventDraft] = []
        if state.released is not None:
            self._pending = self._start_pending(state.released)

        pending = self._pending
        if pending is not None and state.confirmed is not None:
            drafts.extend(self._complete(ctx, pending, state.confirmed))
            self._pending = None
        elif pending is not None:
            drafts.extend(self._maybe_candidate(ctx, pending))
            if ctx.t - pending.start_t > ctx.config.pass_max_duration_s:
                self._pending = None

        self._prev = state
        return drafts

    def _start_pending(self, released: int) -> _PendingPass | None:
        prev = self._prev
        if prev.last_touch_ball is None or prev.last_touch_time is None or prev.last_touch_frame is None:
            return None
        return _PendingPass(released, prev.last_touch_ball, prev.last_touch_time, prev.last_touch_frame)

    def _maybe_candidate(self, ctx: FrameContext, pending: _PendingPass) -> list[EventDraft]:
        if pending.candidate_emitted or ctx.space is None or ctx.possession.holder is not None:
            return []
        if ctx.speed < ctx.config.pass_candidate_min_speed.for_space(ctx.space):
            return []
        self._pending = replace(pending, candidate_emitted=True)
        confidence = round(min(0.9, 0.5 + 0.4 * (ctx.ball.confidence if ctx.ball else 0.0)), 3)
        return [
            EventDraft(
                EventType.PASS_CANDIDATE,
                confidence,
                {"from_track_id": pending.from_track_id, "start": location_dict(pending.start_ball)},
            )
        ]

    def _complete(self, ctx: FrameContext, pending: _PendingPass, to_track_id: int) -> list[EventDraft]:
        if to_track_id == pending.from_track_id or ctx.ball is None:
            return []
        key = (pending.from_track_id, to_track_id, pending.start_frame)
        if key in self._emitted:
            return []
        duration = ctx.t - pending.start_t
        if duration <= 0 or duration > ctx.config.pass_max_duration_s:
            return []
        space, dist = _travel(pending.start_ball, ctx.ball)
        min_dist = ctx.config.pass_min_distance.for_space(space)
        if dist < min_dist:
            return []
        self._emitted.add(key)
        distance_factor = min(1.0, dist / (2 * min_dist))
        confidence = round(min(0.95, 0.55 + 0.2 * distance_factor + 0.2 * ctx.possession.holder_confidence), 3)
        return [
            EventDraft(
                EventType.PASS,
                confidence,
                {
                    "from_track_id": pending.from_track_id,
                    "to_track_id": to_track_id,
                    "start": location_dict(pending.start_ball),
                    "end": location_dict(ctx.ball),
                    "distance": round(dist, 2),
                    "distance_unit": "m" if space is Space.PITCH else "px",
                    "duration": round(duration, 2),
                },
            )
        ]


def _travel(a: BallObservation, b: BallObservation) -> tuple[Space, float]:
    """Distance between two ball observations in the best common space."""
    space = Space.PITCH if a.pitch is not None and b.pitch is not None else Space.PIXEL
    pa, pb = ball_position(a, space), ball_position(b, space)
    assert pa is not None and pb is not None
    return space, distance(pa, pb)
