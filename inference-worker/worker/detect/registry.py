"""Builds the source, detector and pitch mapper for a match.

Real-mode modules (OpenCV/FFmpeg/ultralytics) are imported lazily so the mock
worker image stays small and starts without a GPU stack.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from worker.config import WorkerSettings
from worker.control.commands import MatchConfig
from worker.detect.base import Detector, ModelLoadError
from worker.ingest.source import FrameSource, ReconnectCallback, SourceError
from worker.pitch.mapper import HomographyMapper, NullMapper, PitchMapper

# A tennis ball high in the air near a baseline projects far beyond the court;
# the event engine still needs that projection to see the ball change direction.
TENNIS_PLAUSIBLE = (-150.0, 250.0)

DETECTOR_FAMILIES = {
    "mock": "Synthetic detections from the simulated match (development)",
    "yolo": "Ultralytics YOLO (COCO person/sports-ball or a football fine-tune)",
    # "rfdetr": add worker/detect/rfdetr_detector.py and a branch below.
}


@dataclass(slots=True)
class Components:
    source: FrameSource
    detector: Detector
    mapper: PitchMapper


def build_components(
    config: MatchConfig, settings: WorkerSettings, device: str, on_reconnect: ReconnectCallback
) -> Components:
    if settings.inference_mode == "mock":
        return _mock_components(config, settings)
    return _real_components(config, settings, device, on_reconnect)


def _mock_components(config: MatchConfig, settings: WorkerSettings) -> Components:
    if config.sport == "tennis":
        return _mock_tennis_components(config, settings)
    from worker.detect.mock_detector import MockDetector
    from worker.ingest.mock_source import MockSource
    from worker.simulation.camera import SimCamera

    camera = SimCamera(settings.mock_width, settings.mock_height)
    source = MockSource(config.processing_fps, camera.width, camera.height, settings.mock_seed)
    detector = MockDetector(camera, detect_players=config.detect_players, seed=settings.mock_seed)
    mapper: PitchMapper = NullMapper()
    if pitch_mapping_enabled(config):
        # The synthetic camera is known exactly, so these coordinates are real.
        mapper = HomographyMapper(camera.pixel_to_normalised)
    return Components(source, detector, mapper)


def _mock_tennis_components(config: MatchConfig, settings: WorkerSettings) -> Components:
    from worker.detect.mock_tennis_detector import MockTennisDetector
    from worker.ingest.mock_source import MockSource
    from worker.simulation.tennis_camera import TennisCamera
    from worker.simulation.tennis_sim import TennisSimulation

    camera = TennisCamera(settings.mock_width, settings.mock_height)
    source = MockSource(
        config.processing_fps, camera.width, camera.height, simulation=TennisSimulation(settings.mock_seed)
    )
    detector = MockTennisDetector(camera, detect_players=config.detect_players, seed=settings.mock_seed)
    # The synthetic camera is known exactly: court coordinates are real.
    mapper: PitchMapper = (
        HomographyMapper(camera.pixel_to_normalised, plausible=TENNIS_PLAUSIBLE)
        if pitch_mapping_enabled(config)
        else NullMapper()
    )
    return Components(source, detector, mapper)


def _real_components(
    config: MatchConfig, settings: WorkerSettings, device: str, on_reconnect: ReconnectCallback
) -> Components:
    from worker.detect.yolo_detector import load_yolo_detector
    from worker.ingest.ffmpeg_source import FFmpegSource

    detector: Detector = load_yolo_detector(config.model_name, settings.models_dir, device, config.detect_players)
    if config.sport == "tennis":
        from worker.detect.tracknet import TennisDetector, TrackNetBallDetector, load_tracknet

        # Generic detectors miss the tiny, blurred tennis ball: TrackNet tracks it.
        detector = TennisDetector(detector, TrackNetBallDetector(load_tracknet(settings.models_dir, device), device))
    mapper = _real_mapper(config, settings, device)
    source = FFmpegSource(
        url=resolve_source(config, settings.media_dir),
        fps=config.processing_fps,
        is_live=config.is_live,
        settings=settings,
        on_reconnect=on_reconnect,
    )
    return Components(source, detector, mapper)


def _real_mapper(config: MatchConfig, settings: WorkerSettings, device: str) -> PitchMapper:
    """Automatic calibration when enabled and the pitch model is installed;
    otherwise pixel coordinates only (pitch positions are never invented)."""
    if not pitch_mapping_enabled(config):
        return NullMapper("disabled")
    if config.sport == "tennis":
        from worker.court.mapper import TennisCourtMapper

        return TennisCourtMapper()  # classical line detection: no model needed
    from worker.pitch.auto_mapper import AutoHomographyMapper
    from worker.pitch.keypoint_detector import load_pitch_keypoints

    keypoints = load_pitch_keypoints(settings.models_dir, device, settings.pitch_model_weights)
    if keypoints is None:
        return NullMapper("no_model")
    return AutoHomographyMapper(keypoints)


def pitch_mapping_enabled(config: MatchConfig) -> bool:
    return config.enable_pitch_mapping and config.detection_model == "ball_players_pitch"


def resolve_source(config: MatchConfig, media_dir: Path) -> str:
    if config.source_type != "upload":
        return config.source
    path = (media_dir / config.source).resolve()
    if media_dir.resolve() not in path.parents:
        raise SourceError("uploaded file path escapes the media directory")
    if not path.is_file():
        raise SourceError(f"uploaded file not found: {config.source}")
    return str(path)


__all__ = ["DETECTOR_FAMILIES", "Components", "ModelLoadError", "build_components", "pitch_mapping_enabled"]
