"""A plausible football world for mock mode.

Two 4-4-2 teams hold formation shapes that shift with the ball, the nearest
players press, the ball carrier dribbles towards goal and then passes, shoots
or is tackled. Balls can go out of play and are restarted. Everything is in
pitch metres; the mock detector projects it through a synthetic camera so
the real tracking and event pipeline is exercised end to end.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

import numpy as np

from football_events.geometry import GOAL_HALF_WIDTH_M, PITCH_LENGTH_M, PITCH_WIDTH_M

_FORMATION = (
    (5, 34), (20, 10), (20, 26), (20, 42), (20, 58),
    (40, 10), (40, 26), (40, 42), (40, 58), (57, 27), (57, 41),
)  # fmt: skip
REFEREE_ID = 99
CONTROL_RADIUS_M = 1.2
PLAYER_SPEED = 7.0
SHAPE_SPEED = 3.5
DRIBBLE_SPEED = 4.5
ROLLING_DECEL = 4.0
TACKLE_RATE_PER_S = 0.3
PRESS_SPEED = 5.0
MAX_PASS_M = 35.0
ATTACK_PUSH_M = 10.0
DEFEND_DROP_M = 4.0
PASS_ERROR_M = 2.0
DEAD_BALL_S = 2.5


class BallMode(Enum):
    CONTROLLED = auto()
    FLIGHT = auto()
    DEAD = auto()


@dataclass(frozen=True, slots=True)
class WorldPlayer:
    pid: int
    team: int  # 0 home (attacks right), 1 away, -1 referee
    role: str  # "player" | "goalkeeper" | "referee"
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class WorldSnapshot:
    t: float
    ball_x: float
    ball_y: float
    ball_in_play: bool
    carrier: int | None
    players: tuple[WorldPlayer, ...]


@dataclass(slots=True)
class _Agent:
    pid: int
    team: int
    role: str
    anchor: np.ndarray
    pos: np.ndarray


class MatchSimulation:
    def __init__(self, seed: int | None = None) -> None:
        self._rng = np.random.default_rng(seed)
        self.t = 0.0
        self._agents = self._build_agents()
        self._by_id = {a.pid: a for a in self._agents}
        self._ball = np.array([PITCH_LENGTH_M / 2, PITCH_WIDTH_M / 2])
        self._vel = np.zeros(2)
        self._mode = BallMode.CONTROLLED
        self._carrier: int | None = None
        self._receiver: int | None = None
        self._kicker_team = 0
        self._kick_time = 0.0
        self._dead_until = 0.0
        self._decision_at = 0.0
        self._dribble_dir = np.array([1.0, 0.0])
        self._kick_off(team=0)

    # ----------------------------------------------------------------- public
    def step(self, dt: float) -> WorldSnapshot:
        self.t += dt
        self._move_players(dt)
        if self._mode is BallMode.CONTROLLED:
            self._carry(dt)
        elif self._mode is BallMode.FLIGHT:
            self._fly(dt)
        elif self.t >= self._dead_until:
            self._restart()
        return self.snapshot()

    def snapshot(self) -> WorldSnapshot:
        return WorldSnapshot(
            t=self.t,
            ball_x=float(self._ball[0]),
            ball_y=float(self._ball[1]),
            ball_in_play=self._mode is not BallMode.DEAD,
            carrier=self._carrier,
            players=tuple(
                WorldPlayer(a.pid, a.team, a.role, float(a.pos[0]), float(a.pos[1])) for a in self._agents
            ),
        )

    # ------------------------------------------------------------------ setup
    def _build_agents(self) -> list[_Agent]:
        agents = []
        for team in (0, 1):
            for i, (x, y) in enumerate(_FORMATION):
                ax = x if team == 0 else PITCH_LENGTH_M - x
                ay = y * PITCH_WIDTH_M / 68
                anchor = np.array([ax, ay], dtype=float)
                role = "goalkeeper" if i == 0 else "player"
                agents.append(_Agent(team * 11 + i + 1, team, role, anchor, anchor.copy()))
        ref = np.array([PITCH_LENGTH_M / 2 - 6, PITCH_WIDTH_M / 2 + 8])
        agents.append(_Agent(REFEREE_ID, -1, "referee", ref, ref.copy()))
        return agents

    def _kick_off(self, team: int) -> None:
        for agent in self._agents:
            agent.pos = agent.anchor.copy()
        striker = self._by_id[team * 11 + 10]
        striker.pos = np.array([PITCH_LENGTH_M / 2, PITCH_WIDTH_M / 2])
        self._ball = striker.pos.copy()
        self._give_ball(striker)

    # ---------------------------------------------------------------- players
    def _move_players(self, dt: float) -> None:
        shift = np.array([(self._ball[0] - PITCH_LENGTH_M / 2) * 0.35, (self._ball[1] - PITCH_WIDTH_M / 2) * 0.15])
        chasers = self._chasers()
        for agent in self._agents:
            if agent.pid == self._carrier:
                continue
            target, speed = self._target_for(agent, shift, chasers)
            self._move_towards(agent, target, speed * dt)

    def _chasers(self) -> set[int]:
        controlling_team = self._by_id[self._carrier].team if self._carrier is not None else None
        chasers: set[int] = set()
        for team in (0, 1):
            if team == controlling_team or self._mode is BallMode.DEAD:
                continue
            outfield = [a for a in self._agents if a.team == team and a.role == "player"]
            outfield.sort(key=lambda a: float(np.linalg.norm(a.pos - self._ball)))
            chasers.update(a.pid for a in outfield[:1])
        return chasers

    def _target_for(self, agent: _Agent, shift: np.ndarray, chasers: set[int]) -> tuple[np.ndarray, float]:
        if agent.role == "referee":
            return self._ball + np.array([-6.0, 8.0]), 5.0
        if agent.pid == self._receiver and self._mode is BallMode.FLIGHT:
            return self._ball + self._vel * 0.4, PLAYER_SPEED
        if agent.pid in chasers:
            # A loose ball is chased at full speed; a carrier is pressed more slowly.
            speed = PLAYER_SPEED if self._carrier is None else PRESS_SPEED
            return self._ball.copy(), speed
        if agent.role == "goalkeeper":
            y = float(np.clip(self._ball[1], PITCH_WIDTH_M / 2 - 4, PITCH_WIDTH_M / 2 + 4))
            return np.array([agent.anchor[0], y]), SHAPE_SPEED
        forward = 1.0 if agent.team == 0 else -1.0
        push = ATTACK_PUSH_M if agent.team == self._kicker_team else -DEFEND_DROP_M
        jitter = self._rng.normal(0, 0.6, 2)
        return agent.anchor + shift + np.array([push * forward, 0.0]) + jitter, SHAPE_SPEED

    @staticmethod
    def _move_towards(agent: _Agent, target: np.ndarray, max_step: float) -> None:
        delta = target - agent.pos
        dist = float(np.linalg.norm(delta))
        if dist > 1e-6:
            agent.pos = agent.pos + delta / dist * min(dist, max_step)
        agent.pos = np.clip(agent.pos, [-2, -2], [PITCH_LENGTH_M + 2, PITCH_WIDTH_M + 2])

    # ------------------------------------------------------------------- ball
    def _give_ball(self, agent: _Agent) -> None:
        self._mode = BallMode.CONTROLLED
        self._carrier, self._receiver = agent.pid, None
        self._kicker_team = agent.team
        self._vel = np.zeros(2)
        self._decision_at = self.t + float(self._rng.uniform(0.7, 2.2))
        self._dribble_dir = self._new_dribble_dir(agent)

    def _new_dribble_dir(self, agent: _Agent) -> np.ndarray:
        goal_x = PITCH_LENGTH_M if agent.team == 0 else 0.0
        direction = np.array([goal_x - agent.pos[0], (PITCH_WIDTH_M / 2 - agent.pos[1]) * 0.3])
        direction += self._rng.normal(0, 4.0, 2)
        return direction / max(float(np.linalg.norm(direction)), 1e-6)

    def _carry(self, dt: float) -> None:
        carrier = self._by_id[self._carrier] if self._carrier is not None else None
        if carrier is None:
            return
        carrier.pos = np.clip(carrier.pos + self._dribble_dir * DRIBBLE_SPEED * dt, [1, 1], [104, 67])
        self._ball = carrier.pos + self._dribble_dir * 0.6
        tackler = self._nearest(self._ball, exclude_team=carrier.team, radius=1.0)
        if tackler is not None and self._rng.random() < 1 - np.exp(-TACKLE_RATE_PER_S * dt):
            self._give_ball(tackler)
            return
        if self.t >= self._decision_at:
            self._decide(carrier)

    def _decide(self, carrier: _Agent) -> None:
        goal_x = PITCH_LENGTH_M if carrier.team == 0 else 0.0
        if abs(goal_x - carrier.pos[0]) < 30 and self._rng.random() < 0.6:
            target = np.array([goal_x + np.sign(goal_x - carrier.pos[0]) * 2, 34 + self._rng.uniform(-6, 6)])
            self._kick(carrier, target, float(self._rng.uniform(22, 28)), receiver=None)
            return
        if self._rng.random() < 0.1:
            self._decision_at = self.t + float(self._rng.uniform(0.8, 1.6))
            self._dribble_dir = self._new_dribble_dir(carrier)
            return
        mate = self._pick_teammate(carrier)
        dist = float(np.linalg.norm(mate.pos - carrier.pos))
        target = mate.pos + self._rng.normal(0, PASS_ERROR_M, 2)
        self._kick(carrier, target, float(np.clip(dist * 1.1 + 8, 10, 22)), receiver=mate.pid)

    def _pick_teammate(self, carrier: _Agent) -> _Agent:
        forward = 1 if carrier.team == 0 else -1
        mates = [a for a in self._agents if a.team == carrier.team and a.pid != carrier.pid and a.role == "player"]
        in_range = [a for a in mates if np.linalg.norm(a.pos - carrier.pos) <= MAX_PASS_M] or mates
        in_range.sort(
            key=lambda a: float(np.linalg.norm(a.pos - carrier.pos)) * 0.3 - (a.pos[0] - carrier.pos[0]) * forward * 0.7
        )
        mates = in_range
        return mates[int(self._rng.integers(0, min(3, len(mates))))]

    def _kick(self, kicker: _Agent, target: np.ndarray, speed: float, receiver: int | None) -> None:
        direction = target - self._ball
        self._vel = direction / max(float(np.linalg.norm(direction)), 1e-6) * speed
        self._mode = BallMode.FLIGHT
        self._carrier, self._receiver = None, receiver
        self._kicker_team = kicker.team
        self._kick_time = self.t

    def _fly(self, dt: float) -> None:
        speed = float(np.linalg.norm(self._vel))
        if speed > 0:
            self._vel *= max(0.0, speed - ROLLING_DECEL * dt) / speed
        self._ball = self._ball + self._vel * dt
        if not (0 <= self._ball[0] <= PITCH_LENGTH_M and 0 <= self._ball[1] <= PITCH_WIDTH_M):
            self._mode, self._dead_until = BallMode.DEAD, self.t + DEAD_BALL_S
            self._vel = np.zeros(2)
            return
        if self.t - self._kick_time < 0.3:
            return
        receiver = self._nearest(self._ball, exclude_team=None, radius=CONTROL_RADIUS_M)
        if receiver is not None:
            self._give_ball(receiver)

    def _restart(self) -> None:
        x, y = float(self._ball[0]), float(self._ball[1])
        restart_team = 1 - self._kicker_team
        over_goal_line = x < 0 or x > PITCH_LENGTH_M
        if over_goal_line and abs(y - PITCH_WIDTH_M / 2) <= GOAL_HALF_WIDTH_M:
            conceding = 1 if x > PITCH_LENGTH_M else 0
            self._kick_off(team=conceding)
            return
        if over_goal_line:
            keeper_x = 5.5 if x < 0 else PITCH_LENGTH_M - 5.5
            taker = self._nearest(np.array([keeper_x, 34.0]), exclude_team=1 - restart_team, radius=None, role="goalkeeper")
            self._ball = np.array([keeper_x, 34.0])
        else:
            self._ball = np.array([float(np.clip(x, 1, PITCH_LENGTH_M - 1)), 0.3 if y < 0 else PITCH_WIDTH_M - 0.3])
            taker = self._nearest(self._ball, exclude_team=1 - restart_team, radius=None)
        if taker is None:
            self._kick_off(team=restart_team)
            return
        taker.pos = self._ball.copy()
        self._give_ball(taker)

    def _nearest(
        self, point: np.ndarray, exclude_team: int | None, radius: float | None, role: str | None = None
    ) -> _Agent | None:
        best, best_d = None, float("inf")
        for agent in self._agents:
            if agent.role == "referee" or agent.team == exclude_team or (role and agent.role != role):
                continue
            d = float(np.linalg.norm(agent.pos - point))
            if d < best_d and (radius is None or d <= radius):
                best, best_d = agent, d
        return best
