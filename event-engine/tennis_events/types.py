from __future__ import annotations

from enum import StrEnum


class TennisEventType(StrEnum):
    SERVE = "serve"
    HIT = "hit"
    BOUNCE = "bounce"
    BALL_OUT = "ball_out"
    FAULT = "fault"
    DOUBLE_FAULT = "double_fault"
    POINT_WON = "point_won"
