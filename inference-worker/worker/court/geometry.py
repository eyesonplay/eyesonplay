"""Tennis court template in normalised coordinates (see tennis_events.court):
x 0-100 near baseline to far baseline, y 0-100 across the doubles court."""

from __future__ import annotations

LENGTH_M, WIDTH_M = 23.77, 10.97
SERVICE = 6.40 / LENGTH_M * 100  # net to service line
SINGLES = 1.37 / WIDTH_M * 100  # doubles to singles sideline

Segment = tuple[tuple[float, float], tuple[float, float]]

# Ground lines (the net is not on the ground and is excluded).
COURT_LINES: tuple[Segment, ...] = (
    ((0, 0), (0, 100)),  # near baseline
    ((100, 0), (100, 100)),  # far baseline
    ((0, 0), (100, 0)),  # doubles sidelines
    ((0, 100), (100, 100)),
    ((0, SINGLES), (100, SINGLES)),  # singles sidelines
    ((0, 100 - SINGLES), (100, 100 - SINGLES)),
    ((50 - SERVICE, SINGLES), (50 - SERVICE, 100 - SINGLES)),  # service lines
    ((50 + SERVICE, SINGLES), (50 + SERVICE, 100 - SINGLES)),
    ((50 - SERVICE, 50), (50 + SERVICE, 50)),  # centre service line
)

# Points inside the boxes, where no line should be (rejects collapsed fits).
INTERIOR: tuple[tuple[float, float], ...] = (
    (25, 30), (25, 70), (75, 30), (75, 70), (12, 50), (88, 50), (40, 25), (60, 75),
)  # fmt: skip

# Which pairs of court lines two detected lines may be (near/far, left/right).
ALONG_PAIRS: tuple[tuple[float, float], ...] = ((0, 100), (0, 50 + SERVICE), (50 - SERVICE, 100), (50 - SERVICE, 50 + SERVICE))
ACROSS_PAIRS: tuple[tuple[float, float], ...] = ((0, 100), (SINGLES, 100 - SINGLES))
