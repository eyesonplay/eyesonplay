"""corner: the ball is placed and settles in a corner arc with a player next
to it (the taker). Only from pitch coordinates: without calibration the corner
flags cannot be located, so nothing is emitted. Reported once per placement;
the next corner needs the ball to leave the corner area first."""

from __future__ import annotations

from football_events.context import FrameContext
from football_events.geometry import PITCH_LENGTH_M, PITCH_WIDTH_M, Space, distance, location_dict, player_position
from football_events.types import EventDraft, EventType, PlayerObservation, Point

_CORNERS: dict[str, Point] = {
    "top_left": Point(0.0, 0.0),
    "top_right": Point(PITCH_LENGTH_M, 0.0),
    "bottom_left": Point(0.0, PITCH_WIDTH_M),
    "bottom_right": Point(PITCH_LENGTH_M, PITCH_WIDTH_M),
}
_TAKER_ROLES = ("player", "goalkeeper")


class CornerRule:
    def __init__(self) -> None:
        self._corner: str | None = None
        self._still_since: float | None = None
        self._reported = False

    def update(self, ctx: FrameContext) -> list[EventDraft]:
        ball = ctx.ball
        if ball is None or ctx.space is not Space.PITCH or ctx.ball_pos is None:
            return []  # e.g. the taker hides the ball for a moment: keep the state
        cfg = ctx.config
        corner = corner_at(ctx.ball_pos, cfg.corner_radius_m)
        if corner is None:
            self._corner, self._still_since, self._reported = None, None, False
            return []
        if self._reported:
            return []
        moving = ctx.speed > cfg.corner_still_speed
        if moving or corner != self._corner or self._still_since is None:
            self._corner = corner
            self._still_since = None if moving else ctx.t
            return []
        settled = ctx.t - self._still_since
        taker = _taker(ctx.obs.players, ctx.ball_pos, cfg.corner_taker_radius_m)
        if settled < cfg.corner_settle_s or taker is None:
            return []
        self._reported = True
        return [
            EventDraft(
                EventType.CORNER,
                round(ball.confidence * 0.85, 3),
                {
                    "corner": corner,
                    "goal_line": corner.split("_")[1],
                    "location": location_dict(ball),
                    "taker_track_id": taker.track_id,
                    "settled_s": round(settled, 2),
                },
            )
        ]


def corner_at(ball_m: Point, radius_m: float) -> str | None:
    """Name of the corner the ball (in metres) is within `radius_m` of, if any."""
    for name, flag in _CORNERS.items():
        if distance(ball_m, flag) <= radius_m:
            return name
    return None


def _taker(players: tuple[PlayerObservation, ...], ball_m: Point, radius_m: float) -> PlayerObservation | None:
    """The nearest outfield player or keeper within `radius_m` of the ball."""
    best: PlayerObservation | None = None
    best_d = radius_m
    for p in players:
        pos = player_position(p, Space.PITCH) if p.role in _TAKER_ROLES else None
        if pos is None:
            continue
        d = distance(pos, ball_m)
        if d <= best_d:
            best, best_d = p, d
    return best
