"""Record what the worker sees on a video: run the real tennis pipeline
(TrackNet ball, YOLO players, court calibration) over a file as fast as the
hardware allows and keep each frame's observation for the event engine.

Recordings are cached (one video takes minutes; training runs take seconds),
keyed by the file's path, size, modification time and the processing FPS.
The cache is a pickle written by this module and only read back by it.
"""

from __future__ import annotations

import hashlib
import pickle
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from football_events.types import FrameObservation

from worker.config import WorkerSettings
from worker.control.commands import MatchConfig
from worker.logging import get_logger
from worker.pipeline import FramePipeline

log = get_logger(component="training")

CACHE_VERSION = 1
PROGRESS_EVERY_S = 30.0  # video seconds between progress lines


@dataclass(frozen=True)
class Recording:
    frame_height: int
    fps: int
    observations: tuple[FrameObservation, ...]


class _Recorder:
    """Stands in for the event engine and keeps what it would have been given."""

    def __init__(self, on_frame: Callable[[FrameObservation], None]) -> None:
        self._on_frame = on_frame

    def update(self, obs: FrameObservation) -> list:
        self._on_frame(obs)
        return []


def record(video: Path, settings: WorkerSettings, device: str, fps: int, player_model: str) -> Recording:
    from worker.detect.registry import components_for_file

    config = MatchConfig(
        sport="tennis",
        source_type="upload",
        source=video.name,
        processing_fps=fps,
        detection_model="ball_players_pitch",
        model_name=player_model,
        confidence_threshold=0.25,
    )
    components = components_for_file(video, config, settings, device)
    observations: list[FrameObservation] = []
    pipeline = FramePipeline(config, components.detector, components.mapper, _Recorder(observations.append))
    started, next_report = time.monotonic(), PROGRESS_EVERY_S
    try:
        for frame in components.source:
            pipeline.process(frame)
            if frame.video_ts >= next_report:
                next_report += PROGRESS_EVERY_S
                wall_s = round(time.monotonic() - started)
                log.info("recording", video=video.name, video_s=round(frame.video_ts), wall_s=wall_s)
        return Recording(components.source.height, fps, tuple(observations))
    finally:
        components.close()


def cached_record(
    video: Path, cache_dir: Path, settings: WorkerSettings, device: str, fps: int, player_model: str
) -> Recording:
    path = cache_dir / f"{video.stem}-{_cache_key(video, fps, player_model)}.pkl"
    if path.is_file():
        log.info("using recorded detections", video=video.name, cache=str(path))
        with path.open("rb") as fh:
            return pickle.load(fh)  # our own cache file
    recording = record(video, settings, device, fps, player_model)
    cache_dir.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("wb") as fh:
        pickle.dump(recording, fh, protocol=pickle.HIGHEST_PROTOCOL)
    tmp.replace(path)
    return recording


def _cache_key(video: Path, fps: int, player_model: str) -> str:
    stat = video.stat()
    raw = f"{CACHE_VERSION}|{video.resolve()}|{stat.st_size}|{stat.st_mtime_ns}|{fps}|{player_model}"
    return hashlib.sha1(raw.encode()).hexdigest()[:12]
