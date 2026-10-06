"""TennisEventEngine: point state machine over trajectory turning points.

idle  --hit-->  serve  --bounce in box-->  rally  --out / net / double bounce-->  idle
                  \\--bounce outside--> fault (second fault: double fault, point)
Bounces while idle (the server bouncing the ball) are ignored.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from football_events.clock import format_match_clock
from football_events.ids import new_event_id
from football_events.types import Event, FrameObservation, PlayerObservation
from tennis_events.config import TennisConfig
from tennis_events.court import (
    CourtPoint,
    in_court,
    in_service_box,
    opponent,
    server_court,
    side_of,
)
from tennis_events.trajectory import Sample, TrajectoryAnalyser, Turning
from tennis_events.types import TennisEventType as T

IDLE, SERVE, RALLY = "idle", "serve", "rally"
# A point is not over if the other player plays the ball: endings (out, net,
# double bounce, fault) are held this long and cancelled by such a hit.
END_CONFIRM_S = 0.8
SERVE_CONFIRM_S = 1.2  # a served ball crosses the net well within this


@dataclass(frozen=True, slots=True)
class Draft:
    event_type: T
    confidence: float
    details: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _PendingEnd:
    finalise: Callable[[], list[Draft]]  # applies the state change, returns its events
    obs: FrameObservation  # when the ending was decided (event timestamps)
    resume_side: str  # a hit by this player proves the ending wrong
    t: float


@dataclass(frozen=True, slots=True)
class _Player:
    track_id: int | None
    side: str
    bbox: tuple[float, float, float, float]
    court: CourtPoint | None = None  # feet on the court, when calibrated


class TennisEventEngine:
    def __init__(self, match_id: str, config: TennisConfig | None = None, id_factory: Callable[[], str] = new_event_id) -> None:
        self._match_id = match_id
        self._cfg = config or TennisConfig()
        self._new_id = id_factory
        self._trajectory = TrajectoryAnalyser(
            self._cfg.bounce_impulse,
            self._cfg.bounce_scorer,
            self._cfg.bounce_probability,
            to_720p=720.0 / self._cfg.frame_height_px,
        )
        self._phase = IDLE
        self._faults = 0
        self._server_side: str | None = None
        self._server_y = 50.0
        self._last_hitter: str | None = None
        self._hits = 0
        self._bounces = 0
        self._last_turning_t = -1e9
        self._last_activity_t: float | None = None
        self._players: list[_Player] = []
        self._tentative: tuple[str, Draft, FrameObservation] | None = None  # serve awaiting the net crossing
        self._pending_end: _PendingEnd | None = None
        self._obs: FrameObservation | None = None
        self._player_height = 0.0

    @property
    def phase(self) -> str:
        return self._phase

    def update(self, obs: FrameObservation) -> list[Event]:
        self._obs = obs
        self._players = self._sides(obs.players) or self._players
        heights = [p.bbox[3] - p.bbox[1] for p in self._players]
        if heights:
            self._player_height = sum(heights) / len(heights)
        drafts: list[Draft] = []
        confirmed: list[tuple[FrameObservation, Draft]] = []
        ball = obs.ball
        if ball is None or ball.predicted:
            drafts += self._check_timeout(obs.video_ts)
        else:
            court = CourtPoint(ball.pitch.x, ball.pitch.y) if ball.pitch is not None else None
            turning = self._trajectory.push(
                Sample(obs.video_ts, obs.frame_number, ball.pixel.x, ball.pixel.y, court, ball),
                self._height_at(ball.pixel.y),
            )
            if self._phase == IDLE:
                confirmed = self._confirm_serve(Sample(obs.video_ts, obs.frame_number, ball.pixel.x, ball.pixel.y, court, ball))
            if turning is not None and turning.sample.t - self._last_turning_t >= self._cfg.min_event_gap_s:
                drafts += self._on_turning(turning)
            drafts += self._check_timeout(obs.video_ts)
        events = [*confirmed, *((obs, d) for d in drafts)]
        pending = self._pending_end
        if pending is not None and obs.video_ts - pending.t >= END_CONFIRM_S:
            self._pending_end = None
            events += [(pending.obs, d) for d in pending.finalise()]
        enabled = self._cfg.enabled_events
        return [self._finalise(o, d) for o, d in events if d.event_type in enabled]

    def _end(self, resume_side: str, finalise: Callable[[], list[Draft]]) -> list[Draft]:
        """Hold a point-ending decision until it is confirmed (see END_CONFIRM_S)."""
        if self._pending_end is None and self._obs is not None:
            self._pending_end = _PendingEnd(finalise, self._obs, resume_side, self._obs.video_ts)
        return []

    # ----------------------------------------------------------------- players
    def _sides(self, players: tuple[PlayerObservation, ...]) -> list[_Player]:
        people = [p for p in players if p.role in ("player", "goalkeeper")]
        if not people:
            return []
        if all(p.pitch is not None for p in people):
            return [
                _Player(p.track_id, side_of(p.pitch.x), p.bbox, CourtPoint(p.pitch.x, p.pitch.y))  # type: ignore[union-attr]
                for p in people
            ]
        # Uncalibrated: the player lowest on screen is on the near side.
        ordered = sorted(people, key=lambda p: p.bbox[3], reverse=True)
        return [_Player(p.track_id, "near" if i == 0 else "far", p.bbox) for i, p in enumerate(ordered)]

    def _height_at(self, y_px: float) -> float:
        """On-screen height of a player standing at this image row (perspective):
        interpolated between the nearest and farthest player."""
        if len(self._players) < 2:
            return self._player_height
        near = max(self._players, key=lambda p: p.bbox[3])
        far = min(self._players, key=lambda p: p.bbox[3])
        y_near, y_far = near.bbox[3], far.bbox[3]
        h_near, h_far = near.bbox[3] - near.bbox[1], far.bbox[3] - far.bbox[1]
        if y_near - y_far < 1:
            return self._player_height
        f = min(1.2, max(-0.2, (y_px - y_far) / (y_near - y_far)))
        return max(1.0, h_far + (h_near - h_far) * f)

    def _hitter(self, sample: Sample) -> _Player | None:
        reach = self._cfg.hit_reach * self._height_at(sample.y)
        best, best_d = None, float("inf")
        for p in self._players:
            x1, y1, x2, y2 = p.bbox
            dx = max(x1 - sample.x, 0.0, sample.x - x2)
            dy = max(y1 - sample.y, 0.0, sample.y - y2)
            d = (dx * dx + dy * dy) ** 0.5
            if d <= reach and d < best_d:
                best, best_d = p, d
        return best

    # ----------------------------------------------------------------- events
    def _on_turning(self, turning: Turning) -> list[Draft]:
        hitter = self._hitter(turning.sample)
        # A hit sends the ball away from the hitter; a bounce keeps it travelling
        # the same way (often towards the receiver, who may be standing close).
        struck_away = hitter is not None and (turning.outgoing > 0) == (hitter.side == "near")
        if turning.reversal and hitter is not None and struck_away:
            self._last_turning_t = self._last_activity_t = turning.sample.t
            return self._on_hit(hitter, turning.sample)
        if turning.bounce:
            self._last_turning_t = turning.sample.t
            if self._phase != IDLE:
                self._last_activity_t = turning.sample.t
            return self._on_bounce(turning.sample, turning.impulse)
        return []

    def _on_hit(self, hitter: _Player, sample: Sample) -> list[Draft]:
        if self._pending_end is not None and hitter.side == self._pending_end.resume_side:
            self._pending_end = None  # the ball was played: the point goes on
        details = {"player": hitter.side, "track_id": hitter.track_id, "side": self._racket_side(hitter, sample)}
        if sample.court is not None:
            details["location"] = sample.court.to_dict()
        if self._phase == IDLE:
            # The server's feet, not the ball: at contact the ball is ~2.6 m up,
            # so its ground projection is far from where the server stands.
            self._server_y = hitter.court.y if hitter.court is not None else 50.0
            details.update(
                serve_number=self._faults + 1,
                court=server_court(hitter.side, self._server_y) if sample.court is not None else None,
            )
            serve = Draft(T.SERVE, 0.8, details)
            if sample.court is None:
                return self._start_serve(hitter.side, serve)  # uncalibrated: cannot check the net
            # Tentative: a toss or a bounce at the server's feet also reverses
            # the projected ball; it is a serve once the ball crosses the net.
            assert self._obs is not None
            self._tentative = (hitter.side, serve, self._obs)
            return []
        if self._phase == SERVE and hitter.side != self._server_side:
            # The receiver returned the serve, so it was in (its bounce was
            # missed, e.g. a fast serve on the far side): continue as a rally.
            self._phase = RALLY
        if self._phase == RALLY and hitter.side != self._last_hitter:
            self._last_hitter, self._hits, self._bounces = hitter.side, self._hits + 1, 0
            details["rally_hits"] = self._hits
            return [Draft(T.HIT, 0.75, details)]
        return []

    def _start_serve(self, side: str, serve: Draft) -> list[Draft]:
        self._phase, self._server_side, self._last_hitter, self._hits, self._bounces = SERVE, side, side, 1, 0
        self._tentative = None
        return [serve]

    def _confirm_serve(self, sample: Sample) -> list[tuple[FrameObservation, Draft]]:
        """A tentative serve becomes one when the ball crosses the net; it is
        stamped with the hit, when it was played, not when it was confirmed."""
        if self._tentative is None or sample.court is None:
            return []
        side, serve, hit = self._tentative
        if sample.t - hit.video_ts > SERVE_CONFIRM_S:
            self._tentative = None
            return []
        if side_of(sample.court.x) == side:
            return []
        return [(hit, d) for d in self._start_serve(side, serve)]

    def _on_bounce(self, sample: Sample, impulse: float) -> list[Draft]:
        if self._phase == IDLE:
            return []  # e.g. the server bouncing the ball before serving
        court = sample.court
        confidence = round(min(0.95, 0.5 + 0.1 * abs(impulse)), 3)
        if court is None:
            return [Draft(T.BOUNCE, confidence, {"in": None, "location": None})]
        is_in = in_court(court, self._cfg.singles, self._cfg.line_tolerance)
        details: dict[str, Any] = {"location": court.to_dict(), "side": side_of(court.x), "in": is_in}
        if self._pending_end is not None:
            return [Draft(T.BOUNCE, confidence, details)]
        if self._phase == RALLY and self._misread_own_side(court):
            return []
        if self._phase == SERVE:
            assert self._server_side is not None
            is_in = in_service_box(court, self._server_side, self._server_y, self._cfg.line_tolerance)
            details["in"] = is_in
            return [Draft(T.BOUNCE, confidence, details), *self._serve_landed(is_in)]
        return [Draft(T.BOUNCE, confidence, details), *self._rally_bounce(court, is_in, confidence)]

    def _serve_landed(self, is_in: bool) -> list[Draft]:
        if is_in:
            self._phase, self._bounces = RALLY, 1
            return []
        server = self._server_side or "near"

        def finalise() -> list[Draft]:
            self._faults += 1
            if self._faults >= 2:
                self._faults = 0
                return [Draft(T.DOUBLE_FAULT, 0.8, {"player": server}), *self._point_now(opponent(server), "double_fault")]
            self._reset_point()
            return [Draft(T.FAULT, 0.8, {"player": server, "serve_number": 1})]

        return self._end(opponent(server), finalise)

    def _misread_own_side(self, court: CourtPoint) -> bool:
        """A bounce on the last hitter's side, too far from the net to be a net error."""
        own_side = side_of(court.x) == self._last_hitter
        return own_side and abs(court.x - 50.0) > self._cfg.net_error_zone

    def _rally_bounce(self, court: CourtPoint, is_in: bool, confidence: float) -> list[Draft]:
        assert self._last_hitter is not None
        hitter = self._last_hitter
        if self._bounces >= 1:
            # The ball already landed in: wherever it bounces next (even past
            # the baseline), the receiver did not reach it.
            return self._point(hitter, "double_bounce")
        if side_of(court.x) == hitter:
            return self._point(opponent(hitter), "net")
        if not is_in:
            out = Draft(T.BALL_OUT, confidence, {"location": court.to_dict(), "player": hitter})
            return self._end(opponent(hitter), lambda: [out, *self._point_now(opponent(hitter), "out")])
        self._bounces += 1
        return []

    def _check_timeout(self, t: float) -> list[Draft]:
        if self._phase == IDLE or self._last_activity_t is None or self._pending_end is not None:
            return []
        if t - self._last_activity_t < self._cfg.rally_timeout_s:
            return []
        if self._phase == RALLY and self._bounces >= 1 and self._last_hitter is not None:
            return self._point_now(self._last_hitter, "not_returned")
        self._reset_point()
        return []

    def _point(self, winner: str, reason: str) -> list[Draft]:
        """A rally ending; the loser can still prove it wrong by playing the ball."""
        return self._end(opponent(winner), lambda: self._point_now(winner, reason))

    def _point_now(self, winner: str, reason: str) -> list[Draft]:
        rally = self._hits
        self._faults = 0 if reason != "double_fault" else self._faults
        self._reset_point()
        return [Draft(T.POINT_WON, 0.7, {"winner": winner, "reason": reason, "rally_length": rally})]

    def _reset_point(self) -> None:
        self._pending_end = None
        self._phase, self._last_hitter, self._hits, self._bounces = IDLE, None, 0, 0
        self._last_activity_t = None
        self._trajectory.reset()

    @staticmethod
    def _racket_side(player: _Player, sample: Sample) -> str:
        """Ball to the player's right or left (from the player's view). Forehand
        vs backhand needs handedness, which is unknown, so only the side is given."""
        centre = (player.bbox[0] + player.bbox[2]) / 2
        right_on_screen = sample.x > centre
        # The near player faces away from the camera: screen right is their right.
        return ("right" if right_on_screen else "left") if player.side == "near" else ("left" if right_on_screen else "right")

    def _finalise(self, obs: FrameObservation, draft: Draft) -> Event:
        return Event(
            event_id=self._new_id(),
            event_type=draft.event_type,
            match_id=self._match_id,
            timestamp=obs.wall_ts,
            video_timestamp=obs.video_ts,
            frame_number=obs.frame_number,
            match_clock=format_match_clock(obs.video_ts, self._cfg.kickoff_offset_seconds),
            confidence=draft.confidence,
            ball=obs.ball,
            details={"sport": "tennis", **draft.details},
        )
