from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from tennis_events.types import TennisEventType


@dataclass(frozen=True, slots=True)
class TennisConfig:
    kickoff_offset_seconds: float = 0.0
    singles: bool = True
    line_tolerance: float = 0.6  # normalised units (~10 cm across, ~14 cm along)
    # A ball stopped by the net lands within this of it (normalised units along,
    # 20 = ~4.8 m); an own-side bounce farther back is a misread, not a net error.
    net_error_zone: float = 20.0
    # A bounce is an abrupt upward change in the ball's on-screen vertical
    # velocity, measured in player heights per second (scale-free).
    bounce_impulse: float = 2.2
    # A hit is a reversal of the ball's direction along the court close to a player.
    hit_reach: float = 0.9  # x the on-screen player height at the ball's depth
    min_event_gap_s: float = 0.2
    rally_timeout_s: float = 2.5  # ball not seen / no event: the point is over
    player_height_m: float = 1.85
    # Optional learned bounce detector: given 5 consecutive ball positions in
    # 1280x720 pixels (2 before, the candidate, 2 after) returns a probability.
    # When set it replaces the vertical-impulse rule for bounces.
    bounce_scorer: Callable[[Sequence[tuple[float, float]]], float] | None = None
    bounce_probability: float = 0.45
    frame_height_px: float = 720.0  # to convert positions to the scorer's 720p scale
    enabled_events: frozenset[TennisEventType] = field(default_factory=lambda: frozenset(TennisEventType))
