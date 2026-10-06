"""Scenario builders: describe ball/player positions per frame in normalised
pitch coordinates; pixels are derived as pitch * 10 for pixel-only tests."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from football_events import BallObservation, EventEngine, FrameObservation, PlayerObservation, Point
from football_events.types import Event

FPS = 10.0

PlayerMap = dict[int, tuple[float, float]]
FrameSpec = tuple[tuple[float, float] | None, PlayerMap]


def player(track_id: int, x: float, y: float, *, with_pitch: bool = True, role: str = "player") -> PlayerObservation:
    fx, fy = x * 10, y * 10
    return PlayerObservation(
        track_id=track_id,
        role=role,
        bbox=(fx - 10, fy - 50, fx + 10, fy),
        confidence=0.9,
        pitch=Point(x, y) if with_pitch else None,
    )


def ball(x: float, y: float, *, with_pitch: bool = True, confidence: float = 0.95) -> BallObservation:
    return BallObservation(
        pixel=Point(x * 10, y * 10),
        pitch=Point(x, y) if with_pitch else None,
        confidence=confidence,
    )


def frames(specs: Sequence[FrameSpec], *, with_pitch: bool = True, start: int = 0) -> list[FrameObservation]:
    result = []
    for i, (ball_xy, players) in enumerate(specs, start=start):
        result.append(
            FrameObservation(
                frame_number=i,
                video_ts=i / FPS,
                wall_ts=1_760_000_000 + i / FPS,
                ball=ball(*ball_xy, with_pitch=with_pitch) if ball_xy is not None else None,
                players=tuple(player(pid, x, y, with_pitch=with_pitch) for pid, (x, y) in players.items()),
            )
        )
    return result


def run(engine: EventEngine, observations: Iterable[FrameObservation]) -> list[Event]:
    events: list[Event] = []
    for obs in observations:
        events.extend(engine.update(obs))
    return events


def of_type(events: list[Event], name: str) -> list[Event]:
    return [e for e in events if e.event_type.value == name]


def hold(ball_xy: tuple[float, float], players: PlayerMap, n: int) -> list[FrameSpec]:
    return [(ball_xy, players)] * n


def travel(start: tuple[float, float], end: tuple[float, float], players: PlayerMap, n: int) -> list[FrameSpec]:
    """Ball moves linearly from start to end over n frames (exclusive of start)."""
    out: list[FrameSpec] = []
    for k in range(1, n + 1):
        f = k / n
        out.append(((start[0] + (end[0] - start[0]) * f, start[1] + (end[1] - start[1]) * f), players))
    return out
