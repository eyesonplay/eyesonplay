"""goal and goal_candidate.

A goal is confirmed by the broadcast's on-screen score: a new score read the
same way `goal_confirm_reads` times in a row, one higher for one team. It is
stamped at the moment it happened when that was seen (the ball crossing the
goal line between the posts, or a "GOAL" graphic), otherwise when the
scoreboard changed. The first score read is the starting point, not a goal; a
lower score (a disallowed goal, a misread) becomes the new starting point.

Without a readable scoreboard, the ball crossing the goal line between the
posts is only a `goal_candidate`: with one camera the ball's height (over the
bar or not) is unknown.
"""

from __future__ import annotations

from dataclasses import dataclass

from football_events.context import FrameContext
from football_events.geometry import GOAL_HALF_WIDTH_M, PITCH_LENGTH_M, PITCH_WIDTH_M, location_dict
from football_events.types import EventDraft, EventType, FrameObservation, ScoreboardObservation

_MOUTH_HALF_NORM = GOAL_HALF_WIDTH_M / PITCH_WIDTH_M * 100
SCOREBOARD_CONFIDENCE = 0.9
SEEN_CONFIDENCE = 0.97  # scoreboard plus the goal moment itself
UNSEEN_JUMP_CONFIDENCE = 0.75  # several goals between two readings


@dataclass(frozen=True, slots=True)
class _Moment:
    obs: FrameObservation
    kind: str  # "ball_in_goal" | "goal_graphic"


class GoalRule:
    def __init__(self) -> None:
        self._score: tuple[int, int] | None = None  # confirmed
        self._pending: tuple[int, int] | None = None
        self._pending_reads = 0
        self._last_read_id: int | None = None
        self._moments: list[_Moment] = []
        self._prev_x: float | None = None
        self._in_goal = False
        self._last_candidate_t = float("-inf")

    def update(self, ctx: FrameContext) -> list[EventDraft]:
        drafts = self._ball_in_goal(ctx)
        board = ctx.obs.scoreboard
        if board is not None and board.read_id != self._last_read_id:
            self._last_read_id = board.read_id
            drafts += self._read(ctx, board)
        return drafts

    # ------------------------------------------------------------ ball in goal
    def _ball_in_goal(self, ctx: FrameContext) -> list[EventDraft]:
        ball = ctx.ball
        if ball is None or ball.pitch is None:
            return []
        x, y = ball.pitch.x, ball.pitch.y
        depth = ctx.config.goal_depth_m / PITCH_LENGTH_M * 100
        crossed_in = (100 < x <= 100 + depth or -depth <= x < 0) and abs(y - 50) <= _MOUTH_HALF_NORM
        prev, self._prev_x = self._prev_x, x
        if not crossed_in:
            self._in_goal = False
            return []
        if self._in_goal or prev is None or not 0 <= prev <= 100:
            return []  # already reported, or no in-play position before it
        self._in_goal = True
        if ctx.t - self._last_candidate_t < ctx.config.goal_candidate_cooldown_s:
            return []  # the same ball bouncing around the line
        self._last_candidate_t = ctx.t
        self._moments.append(_Moment(ctx.obs, "ball_in_goal"))
        return [
            EventDraft(
                EventType.GOAL_CANDIDATE,
                round(ball.confidence * 0.5, 3),
                {
                    "goal": "right" if x > 100 else "left",
                    "location": location_dict(ball),
                    "last_touch_track_id": ctx.possession.last_holder,
                },
            )
        ]

    # -------------------------------------------------------------- scoreboard
    def _read(self, ctx: FrameContext, board: ScoreboardObservation) -> list[EventDraft]:
        if board.goal_banner:
            self._moments.append(_Moment(ctx.obs, "goal_graphic"))
        self._forget_old_moments(ctx.t, ctx.config.goal_evidence_window_s)
        if board.home is None or board.away is None:
            return []
        reading = (board.home, board.away)
        if reading == self._score:
            self._pending, self._pending_reads = None, 0
            return []
        if reading != self._pending:
            self._pending, self._pending_reads = reading, 0
        self._pending_reads += 1
        if self._pending_reads < ctx.config.goal_confirm_reads:
            return []
        previous, self._score = self._score, reading
        self._pending, self._pending_reads = None, 0
        if previous is None:
            return []  # the starting score
        return self._goals(ctx, previous, reading)

    def _goals(self, ctx: FrameContext, before: tuple[int, int], after: tuple[int, int]) -> list[EventDraft]:
        home_gain, away_gain = after[0] - before[0], after[1] - before[1]
        if home_gain < 0 or away_gain < 0 or home_gain + away_gain == 0:
            return []  # lower (disallowed goal or misread): new starting point
        if home_gain + away_gain == 1:
            team = "home" if home_gain else "away"
            moment, evidence = self._goal_moment(ctx.config.goal_ball_before_graphic_s)
            self._moments.clear()
            return [
                EventDraft(
                    EventType.GOAL,
                    SEEN_CONFIDENCE if moment else SCOREBOARD_CONFIDENCE,
                    _details(team, after, ["scoreboard", *evidence], ctx.t),
                    at=moment.obs if moment else None,
                )
            ]
        # Several goals between two readings (e.g. a highlights cut): report
        # each, in score order, at the moment the scoreboard changed.
        self._moments.clear()
        drafts: list[EventDraft] = []
        home, away = before
        for team, gain in (("home", home_gain), ("away", away_gain)):
            for _ in range(gain):
                home, away = (home + 1, away) if team == "home" else (home, away + 1)
                drafts.append(EventDraft(EventType.GOAL, UNSEEN_JUMP_CONFIDENCE, _details(team, (home, away), ["scoreboard"], ctx.t)))
        return drafts

    def _goal_moment(self, ball_before_graphic_s: float) -> tuple[_Moment | None, list[str]]:
        """When the goal happened, and the evidence used for it. The ball crossing
        the line is exact, but only trusted shortly before the broadcaster's
        "GOAL" graphic when there is one; otherwise the graphic times the goal."""
        balls = [m for m in self._moments if m.kind == "ball_in_goal"]
        graphics = [m for m in self._moments if m.kind == "goal_graphic"]
        if not graphics:
            return (max(balls, key=_time), ["ball_in_goal"]) if balls else (None, [])
        graphic = min(graphics, key=_time)
        g = graphic.obs.video_ts
        near = [b for b in balls if g - ball_before_graphic_s <= b.obs.video_ts <= g]
        if near:
            return max(near, key=_time), ["ball_in_goal", "goal_graphic"]
        return graphic, ["goal_graphic"]

    def _forget_old_moments(self, now: float, window_s: float) -> None:
        self._moments = [m for m in self._moments if now - m.obs.video_ts <= window_s]


def _time(moment: _Moment) -> float:
    return moment.obs.video_ts


def _details(team: str, score: tuple[int, int], evidence: list[str], confirmed_at: float) -> dict[str, object]:
    return {
        "team": team,  # home = the team shown first (left) on the broadcast scoreboard
        "score": {"home": score[0], "away": score[1]},
        "evidence": evidence,
        "confirmed_at_s": round(confirmed_at, 2),
    }
