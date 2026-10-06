"""Pitch landmark detection with a YOLO pose model (32 pitch keypoints)."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from worker.detect.base import ModelLoadError
from worker.logging import get_logger
from worker.pitch.template import PITCH_LANDMARKS

log = get_logger(component="pitch_keypoints")

DEFAULT_PITCH_WEIGHTS = "football-pitch-detection.pt"
_cache: dict[tuple[str, str], Any] = {}
_cache_lock = threading.Lock()


@dataclass(frozen=True, slots=True)
class Landmark:
    index: int  # index into PITCH_LANDMARKS
    x: float  # pixels
    y: float
    confidence: float


class LandmarkDetector(Protocol):
    def detect(self, image: np.ndarray) -> list[Landmark]: ...


class YOLOPitchKeypoints:
    def __init__(self, model: Any, device: str) -> None:
        self._model = model
        self._device = device
        self._lock = threading.Lock()

    def detect(self, image: np.ndarray) -> list[Landmark]:
        with self._lock:
            results = self._model.predict(image, conf=0.3, device=self._device, verbose=False)
        if not results or results[0].keypoints is None or len(results[0].keypoints) == 0:
            return []
        kp = results[0].keypoints
        xy = kp.xy[0].tolist()
        conf = kp.conf[0].tolist() if kp.conf is not None else [1.0] * len(xy)
        return [
            Landmark(i, float(x), float(y), float(c))
            for i, ((x, y), c) in enumerate(zip(xy, conf, strict=False))
            if i < len(PITCH_LANDMARKS) and (x > 0 or y > 0)
        ]


def pitch_weights_path(models_dir: Path, name: str = DEFAULT_PITCH_WEIGHTS) -> Path:
    return models_dir / name


def load_pitch_keypoints(models_dir: Path, device: str, name: str = DEFAULT_PITCH_WEIGHTS) -> YOLOPitchKeypoints | None:
    """Returns None (pixel coordinates only) when the pitch model is not installed."""
    path = pitch_weights_path(models_dir, name)
    if not path.is_file():
        log.info("pitch keypoint model not installed; pitch mapping unavailable", expected=str(path))
        return None
    key = (str(path), device)
    with _cache_lock:
        model = _cache.get(key)
        if model is None:
            try:
                from ultralytics import YOLO

                model = YOLO(str(path))
                model.to(device)
            except Exception as exc:  # noqa: BLE001 - surface load failures clearly
                raise ModelLoadError(f"failed to load pitch model {path.name}: {exc}") from exc
            n_kpts = getattr(model.model, "kpt_shape", [len(PITCH_LANDMARKS)])[0] if hasattr(model, "model") else None
            if n_kpts is not None and n_kpts != len(PITCH_LANDMARKS):
                raise ModelLoadError(f"pitch model has {n_kpts} keypoints; expected {len(PITCH_LANDMARKS)}")
            _cache[key] = model
            log.info("pitch keypoint model loaded", weights=str(path), device=device)
    return YOLOPitchKeypoints(model, device)
