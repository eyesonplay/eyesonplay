"""EventEngine: runs all rules over one FrameObservation at a time."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from football_events.clock import format_match_clock
from football_events.config import EngineConfig
from football_events.context import FrameContext, PossessionState
from football_events.geometry import ball_position, ball_space
from football_events.ids import new_event_id
from football_events.kinematics import BallKinematics
from football_events.rules.ball_move import BallMoveRule
from football_events.rules.ball_out import BallOutRule
from football_events.rules.ball_presence import BallPresenceRule
from football_events.rules.corners import CornerRule
from football_events.rules.goals import GoalRule
from football_events.rules.passes import PassRule
from football_events.rules.possession import PossessionRule
from football_events.rules.shots import ShotRule
from football_events.types import Event, EventDraft, FrameObservation


class EventEngine:
    """Stateful per-match engine. Not thread-safe: one instance per match."""

    def __init__(
        self,
        match_id: str,
        config: EngineConfig | None = None,
        id_factory: Callable[[], str] = new_event_id,
    ) -> None:
        self._match_id = match_id
        self._config = config or EngineConfig()
        self._new_id = id_factory
        self._kinematics = BallKinematics()
        self._presence = BallPresenceRule()
        self._possession = PossessionRule()
        self._passes = PassRule()
        self._shots = ShotRule()
        self._out = BallOutRule()
        self._corners = CornerRule()
        self._goals = GoalRule()
        self._move = BallMoveRule()

    @property
    def config(self) -> EngineConfig:
        return self._config

    @property
    def possession(self) -> PossessionState:
        return self._possession.state

    def update(self, obs: FrameObservation) -> list[Event]:
        ctx = self._context(obs)
        drafts: list[EventDraft] = list(self._presence.update(ctx))
        possession_drafts, possession = self._possession.update(ctx)
        ctx = replace(ctx, possession=possession)
        drafts.extend(possession_drafts)
        drafts.extend(self._passes.update(ctx))
        drafts.extend(self._shots.update(ctx))
        drafts.extend(self._out.update(ctx))
        drafts.extend(self._corners.update(ctx))
        drafts.extend(self._goals.update(ctx))
        drafts.extend(self._move.update(ctx))
        enabled = self._config.enabled_events
        return [self._finalise(obs, d) for d in drafts if d.event_type in enabled]

    def _context(self, obs: FrameObservation) -> FrameContext:
        ball = obs.ball
        space = ball_space(ball) if ball is not None else None
        pos = ball_position(ball, space) if ball is not None and space is not None else None
        velocity, speed = self._kinematics.update(obs.video_ts, space, pos)
        return FrameContext(
            obs=obs,
            config=self._config,
            space=space,
            ball_pos=pos,
            velocity=velocity,
            speed=speed,
            possession=self._possession.state,
        )

    def _finalise(self, current: FrameObservation, draft: EventDraft) -> Event:
        obs = draft.at or current
        return Event(
            event_id=self._new_id(),
            event_type=draft.event_type,
            match_id=self._match_id,
            timestamp=obs.wall_ts,
            video_timestamp=obs.video_ts,
            frame_number=obs.frame_number,
            match_clock=format_match_clock(obs.video_ts, self._config.kickoff_offset_seconds),
            confidence=draft.confidence,
            ball=obs.ball,
            details=draft.details,
        )
