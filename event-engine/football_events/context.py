"""Per-frame context passed to every rule."""

from __future__ import annotations

from dataclasses import dataclass

from football_events.config import EngineConfig
from football_events.geometry import Space
from football_events.types import BallObservation, FrameObservation, Point


@dataclass(frozen=True, slots=True)
class PossessionState:
    holder: int | None = None
    holder_confidence: float = 0.0
    last_holder: int | None = None
    last_touch_ball: BallObservation | None = None
    last_touch_time: float | None = None
    last_touch_frame: int | None = None
    confirmed: int | None = None  # holder confirmed on this frame
    released: int | None = None  # holder that lost the ball on this frame


@dataclass(frozen=True, slots=True)
class FrameContext:
    obs: FrameObservation
    config: EngineConfig
    space: Space | None  # None when there is no usable ball this frame
    ball_pos: Point | None  # in `space` units (metres or pixels)
    velocity: Point | None  # `space` units per second
    speed: float
    possession: PossessionState

    @property
    def ball(self) -> BallObservation | None:
        return self.obs.ball

    @property
    def t(self) -> float:
        return self.obs.video_ts
