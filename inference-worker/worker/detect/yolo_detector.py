"""YOLODetector (ultralytics).

Works with stock COCO weights (person -> player, sports ball -> ball) and with
football fine-tunes whose class names include ball/player/goalkeeper/referee.
Models are loaded once per worker and shared between matches.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from worker.detect.base import Detection, DetectionClass, ModelLoadError
from worker.ingest.source import Frame
from worker.logging import get_logger

log = get_logger(component="yolo")

_COCO_MAP: dict[str, DetectionClass] = {"person": "player", "sports ball": "ball"}
_FOOTBALL_NAMES: dict[str, DetectionClass] = {
    "ball": "ball",
    "football": "ball",
    "player": "player",
    "goalkeeper": "goalkeeper",
    "referee": "referee",
}
_cache: dict[tuple[str, str], Any] = {}
_cache_lock = threading.Lock()

INFERENCE_IMAGE_SIZE = 1280  # the ball is tiny; a larger input helps recall
MIN_RAW_CONFIDENCE = 0.1  # final threshold is applied per match by the pipeline


class YOLODetector:
    family = "yolo"

    def __init__(self, model: Any, name: str, device: str, detect_players: bool) -> None:
        self._model = model
        self._lock = threading.Lock()  # ultralytics predictors are not re-entrant
        self.name = name
        self.device = device
        self._class_map = _class_map(model.names)
        wanted = {"ball"} | ({"player", "goalkeeper", "referee"} if detect_players else set())
        self._class_ids = [cid for cid, cls in self._class_map.items() if cls in wanted]
        if not any(self._class_map[c] == "ball" for c in self._class_ids):
            raise ModelLoadError(f"model {name} has no ball class (classes: {list(model.names.values())})")

    def detect(self, frame: Frame) -> list[Detection]:
        if frame.image is None:
            return []
        with self._lock:
            results = self._model.predict(
                frame.image,
                conf=MIN_RAW_CONFIDENCE,
                classes=self._class_ids,
                imgsz=INFERENCE_IMAGE_SIZE,
                device=self.device,
                verbose=False,
            )
        detections: list[Detection] = []
        for result in results:
            boxes = result.boxes
            for xyxy, conf, cls_id in zip(boxes.xyxy.tolist(), boxes.conf.tolist(), boxes.cls.tolist(), strict=True):
                cls = self._class_map.get(int(cls_id))
                if cls is not None:
                    detections.append(Detection(cls, tuple(xyxy), float(conf)))  # type: ignore[arg-type]
        return detections


def _class_map(names: dict[int, str]) -> dict[int, DetectionClass]:
    lowered = {cid: n.lower() for cid, n in names.items()}
    if any(n in _FOOTBALL_NAMES for n in lowered.values()):
        return {cid: _FOOTBALL_NAMES[n] for cid, n in lowered.items() if n in _FOOTBALL_NAMES}
    return {cid: _COCO_MAP[n] for cid, n in lowered.items() if n in _COCO_MAP}


def resolve_weights(model_name: str, models_dir: Path) -> str:
    filename = model_name if model_name.endswith((".pt", ".onnx", ".engine")) else f"{model_name}.pt"
    local = models_dir / filename
    # Stock ultralytics names are downloaded on first use into the models dir.
    return str(local) if local.exists() else filename


def load_yolo_detector(model_name: str, models_dir: Path, device: str, detect_players: bool) -> YOLODetector:
    weights = resolve_weights(model_name, models_dir)
    key = (weights, device)
    with _cache_lock:
        model = _cache.get(key)
        if model is None:
            model = _load(weights, device)
            _cache[key] = model
    return YOLODetector(model, model_name, device, detect_players)


def _load(weights: str, device: str) -> Any:
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise ModelLoadError("ultralytics is not installed; build the worker with the real/gpu target") from exc
    try:
        model = YOLO(weights)
        model.to(device)
    except Exception as exc:  # noqa: BLE001 - surface any load failure to the UI
        raise ModelLoadError(f"failed to load {weights} on {device}: {exc}") from exc
    log.info("model loaded", weights=weights, device=device)
    return model


def loaded_models() -> list[dict[str, str]]:
    with _cache_lock:
        return [{"weights": w, "device": d} for w, d in _cache]
