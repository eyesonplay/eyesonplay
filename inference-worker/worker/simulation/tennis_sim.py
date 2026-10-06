"""A simple but physical tennis rally simulation for mock mode.

Ball flight uses gravity and a bouncing coefficient; players move at a
realistic speed and return balls they can reach after the bounce. Serves
alternate deuce/ad courts; some serves are faults, some shots land out, some
balls are not reached (winners). Coordinates are metres: x along the court
(0 = near baseline, 23.77 = far baseline), y across the doubles court (0-10.97),
z height. The mock detector projects this through a broadcast-style camera.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

import numpy as np

LENGTH, WIDTH = 23.77, 10.97
NET_X = LENGTH / 2
SINGLES = (1.37, WIDTH - 1.37)
SERVICE_LINE = 6.40
G = 9.81
RESTITUTION_Z = 0.72
FRICTION_XY = 0.82
PLAYER_SPEED = 6.0
REACH_M = 1.3
POINT_PAUSE_S = 2.0
PRE_SERVE_S = 1.2


class Phase(Enum):
    PAUSE = auto()
    PRE_SERVE = auto()
    FLIGHT = auto()


@dataclass(frozen=True, slots=True)
class TennisPlayer:
    pid: int
    side: str  # "near" | "far"
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class TennisSnapshot:
    t: float
    ball: tuple[float, float, float] | None  # metres, None when not in play
    players: tuple[TennisPlayer, TennisPlayer]


class TennisSimulation:
    def __init__(self, seed: int | None = None) -> None:
        self._rng = np.random.default_rng(seed)
        self.t = 0.0
        self._pos = {"near": np.array([-0.8, 7.0]), "far": np.array([LENGTH + 0.8, 4.0])}
        self._target = dict(self._pos)
        self._ball: np.ndarray | None = None
        self._vel = np.zeros(3)
        self._phase = Phase.PAUSE
        self._phase_until = 0.5
        self._server = "near"
        self._point = 0
        self._serve_number = 1
        self._last_hitter = "near"
        self._bounces = 0
        self._receiver_will_hit = False
        self._return_delay = 0.4
        self._first_bounce_t = 0.0
        self._first_bounce_in = False

    # ----------------------------------------------------------------- public
    def step(self, dt: float) -> TennisSnapshot:
        self.t += dt
        self._move_players(dt)
        if self._phase is Phase.PAUSE and self.t >= self._phase_until:
            self._start_pre_serve()
        elif self._phase is Phase.PRE_SERVE:
            self._pre_serve(dt)
        elif self._phase is Phase.FLIGHT:
            self._fly(dt)
        return self.snapshot()

    def snapshot(self) -> TennisSnapshot:
        ball = tuple(float(v) for v in self._ball) if self._ball is not None else None
        players = tuple(TennisPlayer(i + 1, side, float(self._pos[side][0]), float(self._pos[side][1]))
                        for i, side in enumerate(("near", "far")))  # fmt: skip
        return TennisSnapshot(self.t, ball, players)  # type: ignore[arg-type]

    # ----------------------------------------------------------------- serve
    def _server_spot(self) -> np.ndarray:
        deuce = self._point % 2 == 0
        near = self._server == "near"
        # Deuce court is the server's right half: near player's right is +y.
        y = (7.0 if deuce else 4.0) if near else (4.0 if deuce else 7.0)
        return np.array([-0.4 if near else LENGTH + 0.4, y])

    def _start_pre_serve(self) -> None:
        spot = self._server_spot()
        self._pos[self._server] = spot.copy()
        receiver = "far" if self._server == "near" else "near"
        self._pos[receiver] = np.array([LENGTH + 0.5 if receiver == "far" else -0.5, WIDTH - spot[1]])
        self._target = dict(self._pos)
        self._ball = np.array([spot[0] + (0.4 if self._server == "near" else -0.4), spot[1] + 0.3, 1.0])
        self._vel = np.array([0.0, 0.0, -2.0])  # the server bounces the ball before serving
        self._phase, self._phase_until = Phase.PRE_SERVE, self.t + PRE_SERVE_S

    def _pre_serve(self, dt: float) -> None:
        assert self._ball is not None
        self._integrate(dt, count_bounces=False)
        if self.t >= self._phase_until:
            self._serve()

    def _serve(self) -> None:
        near = self._server == "near"
        spot = self._server_spot()
        fault = self._rng.random() < (0.3 if self._serve_number == 1 else 0.12)
        box_y = (SINGLES[0] + 0.5, WIDTH / 2 - 0.4) if spot[1] > WIDTH / 2 else (WIDTH / 2 + 0.4, SINGLES[1] - 0.5)
        depth = NET_X + (1 if near else -1) * self._rng.uniform(3.5, SERVICE_LINE - 0.4)
        if fault:  # long or wide
            depth = NET_X + (1 if near else -1) * self._rng.uniform(SERVICE_LINE + 0.6, SERVICE_LINE + 2.5)
        target = np.array([depth, self._rng.uniform(*box_y)])
        contact = np.array([spot[0] + (0.3 if near else -0.3), spot[1], 2.6])
        self._launch("serve", contact, target, flight_s=self._rng.uniform(0.55, 0.7))

    # ----------------------------------------------------------------- rally
    def _launch(self, hitter: str, origin: np.ndarray, target: np.ndarray, flight_s: float) -> None:
        self._ball = origin.astype(float)
        horizontal = (target - origin[:2]) / flight_s
        vz = (0.5 * G * flight_s**2 - origin[2]) / flight_s
        self._vel = np.array([horizontal[0], horizontal[1], vz])
        self._last_hitter = self._server if hitter == "serve" else hitter
        self._bounces = 0
        self._phase = Phase.FLIGHT
        receiver = "far" if self._last_hitter == "near" else "near"
        self._target[receiver] = np.array([target[0] + (2.5 if receiver == "far" else -2.5), target[1]])
        # Returns are struck as the ball rises to hitting height after the bounce.
        self._return_delay = float(self._rng.uniform(0.3, 0.5))
        reach_time = np.linalg.norm(self._target[receiver] - self._pos[receiver]) / PLAYER_SPEED
        self._receiver_will_hit = reach_time < flight_s + 0.6 and self._rng.random() < 0.8

    def _fly(self, dt: float) -> None:
        assert self._ball is not None
        self._integrate(dt, count_bounces=True)
        x, y, z = self._ball
        receiver = "far" if self._last_hitter == "near" else "near"
        due = self.t - self._first_bounce_t >= self._return_delay
        if self._bounces == 1 and self._receiver_will_hit and due and self._in_bounds():
            self._return_shot(receiver)
            return
        if self._bounces >= 2 or abs(y - WIDTH / 2) > WIDTH or x < -8 or x > LENGTH + 8:
            self._end_point()

    def _return_shot(self, hitter: str) -> None:
        assert self._ball is not None
        far = hitter == "far"
        out = self._rng.random() < 0.15
        depth = self._rng.uniform(2.0, NET_X - 1.0)
        tx = (depth if far else LENGTH - depth)
        ty = self._rng.uniform(SINGLES[0] + 0.4, SINGLES[1] - 0.4)
        if out:
            ty = self._rng.choice([SINGLES[0] - 0.8, SINGLES[1] + 0.8])
        origin = np.array([self._ball[0], self._ball[1], max(0.9, self._ball[2])])
        self._pos[hitter] = np.array([origin[0] + (0.4 if far else -0.4), origin[1] - 0.5])
        self._launch(hitter, origin, np.array([tx, ty]), flight_s=self._rng.uniform(0.85, 1.15))

    def _in_bounds(self) -> bool:
        assert self._ball is not None
        return self._first_bounce_in

    def _integrate(self, dt: float, count_bounces: bool) -> None:
        assert self._ball is not None
        self._vel[2] -= G * dt
        self._ball = self._ball + self._vel * dt
        if self._ball[2] <= 0:
            self._ball[2] = 0.0
            self._vel[2] = -self._vel[2] * RESTITUTION_Z
            self._vel[:2] *= FRICTION_XY
            if count_bounces:
                self._bounces += 1
                if self._bounces == 1:
                    self._first_bounce_in = self._bounce_in()
                    self._first_bounce_t = self.t

    def _bounce_in(self) -> bool:
        assert self._ball is not None
        x, y = self._ball[0], self._ball[1]
        receiver_side_far = self._last_hitter == "near"
        on_receiver_side = x > NET_X if receiver_side_far else x < NET_X
        return bool(on_receiver_side and 0 <= x <= LENGTH and SINGLES[0] <= y <= SINGLES[1])

    def _end_point(self) -> None:
        self._ball = None
        self._phase, self._phase_until = Phase.PAUSE, self.t + POINT_PAUSE_S
        fault = self._serve_number == 1 and self._bounces >= 1 and not self._first_bounce_in and self._last_hitter == self._server
        if fault:
            self._serve_number = 2
            self._phase_until = self.t + 0.8
            return
        self._serve_number = 1
        self._point += 1
        if self._point % 4 == 0:
            self._server = "far" if self._server == "near" else "near"

    def _move_players(self, dt: float) -> None:
        for side in ("near", "far"):
            delta = self._target[side] - self._pos[side]
            dist = float(np.linalg.norm(delta))
            if dist > 1e-6:
                self._pos[side] = self._pos[side] + delta / dist * min(dist, PLAYER_SPEED * dt)
