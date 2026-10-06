"""Thresholds for every rule. Distances exist in two units because the engine
works in metres when pitch calibration is available and in pixels otherwise."""

from __future__ import annotations

from dataclasses import dataclass, field

from football_events.geometry import Space
from football_events.types import EventType


@dataclass(frozen=True, slots=True)
class SpaceThreshold:
    metres: float
    pixels: float

    def for_space(self, space: Space) -> float:
        return self.metres if space is Space.PITCH else self.pixels


@dataclass(frozen=True, slots=True)
class EngineConfig:
    kickoff_offset_seconds: float = 0.0

    ball_lost_after_frames: int = 5

    ball_move_min_interval_s: float = 1.0
    ball_move_min_distance: SpaceThreshold = SpaceThreshold(1.0, 15.0)

    possession_radius: SpaceThreshold = SpaceThreshold(1.8, 35.0)
    possession_release_radius: SpaceThreshold = SpaceThreshold(3.0, 60.0)
    possession_confirm_frames: int = 3
    possession_release_frames: int = 3

    pass_min_distance: SpaceThreshold = SpaceThreshold(5.0, 80.0)
    pass_max_duration_s: float = 4.0
    pass_candidate_min_speed: SpaceThreshold = SpaceThreshold(6.0, 150.0)

    shot_min_speed: SpaceThreshold = SpaceThreshold(15.0, 500.0)
    shot_max_distance_m: float = 35.0
    shot_origin_window_s: float = 1.0
    shot_confirm_confidence: float = 0.8
    shot_no_pitch_max_confidence: float = 0.4

    ball_out_margin: float = 0.5  # normalised pitch units
    ball_out_frames: int = 3

    corner_radius_m: float = 2.5  # the 1 m corner arc plus detection error
    corner_still_speed: float = 1.5  # m/s: the ball counts as placed below this
    corner_settle_s: float = 1.0
    corner_taker_radius_m: float = 4.0

    enabled_events: frozenset[EventType] = field(default_factory=lambda: frozenset(EventType))

    def __post_init__(self) -> None:
        positive_ints = {
            "ball_lost_after_frames": self.ball_lost_after_frames,
            "possession_confirm_frames": self.possession_confirm_frames,
            "possession_release_frames": self.possession_release_frames,
            "ball_out_frames": self.ball_out_frames,
        }
        for name, value in positive_ints.items():
            if value < 1:
                raise ValueError(f"{name} must be >= 1, got {value}")
        if not 0.0 <= self.shot_confirm_confidence <= 1.0:
            raise ValueError("shot_confirm_confidence must be within [0, 1]")
