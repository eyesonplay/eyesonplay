"""Coordinate helpers.

Normalised pitch coordinates (0-100 on both axes) are converted to metres
before measuring distances so that x and y distances are comparable.
"""

from __future__ import annotations

import math
from enum import StrEnum

from football_events.types import BallObservation, PlayerObservation, Point

PITCH_LENGTH_M = 105.0
PITCH_WIDTH_M = 68.0
GOAL_HALF_WIDTH_M = 3.66


class Space(StrEnum):
    PITCH = "pitch"
    PIXEL = "pixel"


def normalised_to_metres(p: Point) -> Point:
    return Point(p.x * PITCH_LENGTH_M / 100.0, p.y * PITCH_WIDTH_M / 100.0)


def distance(a: Point, b: Point) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def ball_space(ball: BallObservation) -> Space:
    return Space.PITCH if ball.pitch is not None else Space.PIXEL


def ball_position(ball: BallObservation, space: Space) -> Point | None:
    if space is Space.PITCH:
        return normalised_to_metres(ball.pitch) if ball.pitch is not None else None
    return ball.pixel


def player_position(player: PlayerObservation, space: Space) -> Point | None:
    if space is Space.PITCH:
        return normalised_to_metres(player.pitch) if player.pitch is not None else None
    return player.foot


def location_dict(ball: BallObservation) -> dict[str, object]:
    """Public location of a ball observation, preferring pitch coordinates."""
    if ball.pitch is not None:
        return {"coordinate_space": Space.PITCH.value, **ball.pitch.to_dict()}
    return {"coordinate_space": Space.PIXEL.value, **ball.pixel.to_dict()}
