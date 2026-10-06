"""Per-frame processing: detect -> track -> pitch map -> events.

Synchronous and CPU/GPU bound; the match runner calls it from a thread.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from football_events import BallObservation, Event, EventEngine, FrameObservation, PlayerObservation, Point
from worker.control.commands import MatchConfig
from worker.detect.ball_filter import on_pitch
from worker.detect.base import Detection, Detector
from worker.ingest.source import Frame
from worker.pitch.mapper import PitchMapper
from worker.track.ball_tracker import BallState, BallTracker, TrailPoint
from worker.court.players import select_tennis_players
from worker.teams.shirt_color import shirt_color
from worker.teams.team_classifier import Team, TeamClassifier
from worker.track.player_tracker import PlayerTracker, TrackedObject, untracked


BALL_MAX_THRESHOLD = 0.2
TENNIS_PROCESS_NOISE = 1e7


@dataclass(frozen=True, slots=True)
class Timings:
    detect_ms: float
    track_ms: float
    event_ms: float


@dataclass(frozen=True, slots=True)
class MappedPlayer:
    obj: TrackedObject
    pitch: Point | None
    team: int | None = None


@dataclass(frozen=True, slots=True)
class FrameResult:
    frame: Frame
    ball: BallState | None
    ball_pitch: Point | None
    trail: list[tuple[TrailPoint, Point | None]]
    players: list[MappedPlayer]
    events: list[Event]
    timings: Timings
    pitch_calibrated: bool
    calibration: dict[str, Any] = field(default_factory=dict)
    teams: list[Team] = field(default_factory=list)
    processed_at: float = field(default_factory=time.time)

    def frame_message(self) -> dict[str, Any]:
        f = self.frame
        return {
            "frame_number": f.frame_number,
            "video_timestamp": round(f.video_ts, 3),
            "timestamp": round(f.wall_ts, 3),
            "width": f.width,
            "height": f.height,
            "coordinate_mode": "pitch" if self.pitch_calibrated else "pixel",
            "calibration": self.calibration,
            "ball": self._ball_dict(),
            "trail": [
                {"t": round(p.t, 3), "x": round(p.x, 1), "y": round(p.y, 1), "pitch": pitch.to_dict() if pitch else None}
                for p, pitch in self.trail
            ],
            "players": [
                {
                    "track_id": mp.obj.track_id,
                    "class": mp.obj.cls,
                    "bbox": [round(v, 1) for v in mp.obj.bbox],
                    "confidence": round(mp.obj.confidence, 3),
                    "pitch": mp.pitch.to_dict() if mp.pitch else None,
                    "team": mp.team,
                }
                for mp in self.players
            ],
            "teams": [t.to_dict() for t in self.teams],
            "latency_ms": round((self.processed_at - f.wall_ts) * 1000, 1),
        }

    def _ball_dict(self) -> dict[str, Any] | None:
        b = self.ball
        if b is None:
            return None
        half = b.size / 2
        return {
            "track_id": b.track_id,
            "bbox": [round(b.pixel_x - half, 1), round(b.pixel_y - half, 1), round(b.pixel_x + half, 1), round(b.pixel_y + half, 1)],
            "pixel": {"x": round(b.pixel_x, 1), "y": round(b.pixel_y, 1)},
            "pitch": self.ball_pitch.to_dict() if self.ball_pitch else None,
            "confidence": round(b.confidence, 3),
            "velocity": {"x": round(b.velocity_x, 1), "y": round(b.velocity_y, 1)},
            "speed": round(b.speed, 1),
            "predicted": b.predicted,
        }


def _calibration(mapper: PitchMapper) -> dict[str, Any]:
    info = getattr(mapper, "calibration", None)
    return info() if callable(info) else {}


class FramePipeline:
    def __init__(
        self,
        config: MatchConfig,
        detector: Detector,
        mapper: PitchMapper,
        engine: EventEngine | None,
    ) -> None:
        self._config = config
        self._detector = detector
        self._mapper = mapper
        self._engine = engine
        # Tennis bounces and hits are abrupt: follow measurements closely there
        # (football benefits from stronger smoothing of a slower ball).
        self._ball_tracker = BallTracker(process_noise=TENNIS_PROCESS_NOISE if config.sport == "tennis" else 400.0)
        self._player_tracker = PlayerTracker() if config.enable_player_tracking else None
        self._teams = TeamClassifier()

    def process(self, frame: Frame) -> FrameResult:
        t0 = time.perf_counter()
        detections = [d for d in self._detector.detect(frame) if self._accept(d, frame)]
        if not self._config.detect_players:
            detections = [d for d in detections if d.cls == "ball"]
        t1 = time.perf_counter()

        observe = getattr(self._mapper, "observe", None)
        if observe is not None:
            observe(frame)  # automatic calibration refreshes its homography
        ball = self._ball_tracker.update(detections, frame.frame_number, frame.video_ts)
        people = self._player_tracker.update(detections) if self._player_tracker else untracked(detections)
        ball_pitch = self._mapper.to_pitch(ball.pixel_x, ball.pixel_y) if ball else None
        if self._config.sport == "football":
            team_ids = self._teams.assign([(p.track_id, p.cls, self._shirt(frame, p)) for p in people])
        else:
            people = select_tennis_players(people, self._foot_pitch, frame.height)
            team_ids = [None] * len(people)  # tennis players are told apart by court side
        players = [MappedPlayer(p, self._foot_pitch(p), team) for p, team in zip(people, team_ids, strict=True)]
        trail = [(p, self._mapper.to_pitch(p.x, p.y)) for p in self._ball_tracker.history]
        t2 = time.perf_counter()

        events = self._engine.update(self._observation(frame, ball, ball_pitch, players)) if self._engine else []
        t3 = time.perf_counter()

        return FrameResult(
            frame=frame,
            ball=ball,
            ball_pitch=ball_pitch,
            trail=trail,
            players=players,
            events=events,
            timings=Timings((t1 - t0) * 1000, (t2 - t1) * 1000, (t3 - t2) * 1000),
            pitch_calibrated=self._mapper.calibrated,
            calibration=_calibration(self._mapper),
            teams=self._teams.teams,
        )

    def _accept(self, det: Detection, frame: Frame) -> bool:
        if det.cls != "ball":
            return det.confidence >= self._config.confidence_threshold
        # Balls are tiny and score low on general-purpose detectors: use a lower
        # threshold and reject candidates that are not on grass.
        threshold = min(self._config.confidence_threshold, BALL_MAX_THRESHOLD)
        if self._config.sport != "football":
            return det.confidence >= threshold  # the grass check only makes sense on a football pitch
        return det.confidence >= threshold and on_pitch(frame.image, det)

    @staticmethod
    def _shirt(frame: Frame, obj: TrackedObject) -> np.ndarray | None:
        if obj.appearance is not None:
            return np.array(obj.appearance)
        return shirt_color(frame.image, obj.bbox) if frame.image is not None else None

    def _foot_pitch(self, obj: TrackedObject) -> Point | None:
        x1, _, x2, y2 = obj.bbox
        return self._mapper.to_pitch((x1 + x2) / 2, y2)

    @staticmethod
    def _observation(
        frame: Frame, ball: BallState | None, ball_pitch: Point | None, players: list[MappedPlayer]
    ) -> FrameObservation:
        ball_obs = None
        if ball is not None:
            ball_obs = BallObservation(
                pixel=Point(ball.pixel_x, ball.pixel_y),
                pitch=ball_pitch,
                confidence=ball.confidence,
                track_id=ball.track_id,
                predicted=ball.predicted,
            )
        player_obs = tuple(
            PlayerObservation(mp.obj.track_id, mp.obj.cls, mp.obj.bbox, mp.obj.confidence, mp.pitch)
            for mp in players
            if mp.obj.track_id is not None
        )
        return FrameObservation(frame.frame_number, frame.video_ts, frame.wall_ts, ball_obs, player_obs)
