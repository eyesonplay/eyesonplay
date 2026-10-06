"""Tennis court geometry in normalised coordinates.

x: 0-100 along the court, baseline to baseline (net at 50). The "near" player
is on x < 50 (camera side), "far" on x > 50.
y: 0-100 across the doubles court; singles sidelines at 12.5 and 87.5.
The near player faces +x with y increasing to their right.
"""

from __future__ import annotations

from dataclasses import dataclass

LENGTH_M = 23.77
DOUBLES_WIDTH_M = 10.97
SINGLES_MARGIN_M = 1.37
NET_TO_SERVICE_LINE_M = 6.40

NET_X = 50.0
SERVICE_OFFSET_X = NET_TO_SERVICE_LINE_M / LENGTH_M * 100  # 26.92
SINGLES_Y = (SINGLES_MARGIN_M / DOUBLES_WIDTH_M * 100, 100 - SINGLES_MARGIN_M / DOUBLES_WIDTH_M * 100)
CENTRE_Y = 50.0

NEAR, FAR = "near", "far"


@dataclass(frozen=True, slots=True)
class CourtPoint:
    x: float
    y: float

    def to_dict(self) -> dict[str, float]:
        return {"x": round(self.x, 2), "y": round(self.y, 2)}


def side_of(x: float) -> str:
    return NEAR if x < NET_X else FAR


def opponent(side: str) -> str:
    return FAR if side == NEAR else NEAR


def to_metres(dx: float, dy: float) -> tuple[float, float]:
    return dx * LENGTH_M / 100, dy * DOUBLES_WIDTH_M / 100


def in_court(p: CourtPoint, singles: bool, tolerance: float) -> bool:
    """Lines are in: `tolerance` (normalised units) absorbs line width and noise."""
    low, high = SINGLES_Y if singles else (0.0, 100.0)
    return -tolerance <= p.x <= 100 + tolerance and low - tolerance <= p.y <= high + tolerance


def server_court(server_side: str, server_y: float) -> str:
    """"deuce" when the server stands on their right half, else "ad"."""
    right = server_y > CENTRE_Y if server_side == NEAR else server_y < CENTRE_Y
    return "deuce" if right else "ad"


def in_service_box(p: CourtPoint, server_side: str, server_y: float, tolerance: float) -> bool:
    """The serve must land in the diagonally opposite service box."""
    if server_side == NEAR:
        x_ok = NET_X - tolerance <= p.x <= NET_X + SERVICE_OFFSET_X + tolerance
    else:
        x_ok = NET_X - SERVICE_OFFSET_X - tolerance <= p.x <= NET_X + tolerance
    # Cross court: a server on y > 50 aims at y < 50 and vice versa.
    if server_y > CENTRE_Y:
        y_ok = SINGLES_Y[0] - tolerance <= p.y <= CENTRE_Y + tolerance
    else:
        y_ok = CENTRE_Y - tolerance <= p.y <= SINGLES_Y[1] + tolerance
    return x_ok and y_ok
