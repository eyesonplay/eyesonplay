"""Pitch landmark template (32 points) in normalised 0-100 coordinates.

The order matches the keypoint order of the Roboflow `sports` pitch model
(SoccerPitchConfiguration, MIT licence): index i of the model's keypoints is
landmark i here. Dimensions follow that configuration (120 x 70 m template);
normalising keeps the 0-100 contract independent of the real pitch size.
"""

from __future__ import annotations

LENGTH, WIDTH = 12000.0, 7000.0  # centimetres
_PB_W, _PB_L = 4100.0, 2015.0  # penalty box
_GB_W, _GB_L = 1832.0, 550.0  # goal box
_CIRCLE_R, _SPOT = 915.0, 1100.0

_CM: tuple[tuple[float, float], ...] = (
    (0, 0), (0, (WIDTH - _PB_W) / 2), (0, (WIDTH - _GB_W) / 2), (0, (WIDTH + _GB_W) / 2),
    (0, (WIDTH + _PB_W) / 2), (0, WIDTH), (_GB_L, (WIDTH - _GB_W) / 2), (_GB_L, (WIDTH + _GB_W) / 2),
    (_SPOT, WIDTH / 2), (_PB_L, (WIDTH - _PB_W) / 2), (_PB_L, (WIDTH - _GB_W) / 2),
    (_PB_L, (WIDTH + _GB_W) / 2), (_PB_L, (WIDTH + _PB_W) / 2), (LENGTH / 2, 0),
    (LENGTH / 2, WIDTH / 2 - _CIRCLE_R), (LENGTH / 2, WIDTH / 2 + _CIRCLE_R), (LENGTH / 2, WIDTH),
    (LENGTH - _PB_L, (WIDTH - _PB_W) / 2), (LENGTH - _PB_L, (WIDTH - _GB_W) / 2),
    (LENGTH - _PB_L, (WIDTH + _GB_W) / 2), (LENGTH - _PB_L, (WIDTH + _PB_W) / 2),
    (LENGTH - _SPOT, WIDTH / 2), (LENGTH - _GB_L, (WIDTH - _GB_W) / 2),
    (LENGTH - _GB_L, (WIDTH + _GB_W) / 2), (LENGTH, 0), (LENGTH, (WIDTH - _PB_W) / 2),
    (LENGTH, (WIDTH - _GB_W) / 2), (LENGTH, (WIDTH + _GB_W) / 2), (LENGTH, (WIDTH + _PB_W) / 2),
    (LENGTH, WIDTH), (LENGTH / 2 - _CIRCLE_R, WIDTH / 2), (LENGTH / 2 + _CIRCLE_R, WIDTH / 2),
)  # fmt: skip

PITCH_LANDMARKS: tuple[tuple[float, float], ...] = tuple((x / LENGTH * 100, y / WIDTH * 100) for x, y in _CM)
