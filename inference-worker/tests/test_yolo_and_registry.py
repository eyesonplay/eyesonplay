from types import SimpleNamespace

import numpy as np
import pytest

from worker.control.commands import MatchConfig
from worker.detect.base import ModelLoadError
from worker.detect.registry import pitch_mapping_enabled, resolve_source
from worker.detect.yolo_detector import YOLODetector, _class_map, resolve_weights
from worker.ingest.source import Frame, SourceError


class _Tensor(list):
    def tolist(self):
        return list(self)


class StubModel:
    """Mimics the ultralytics predict() result structure."""

    def __init__(self, names, boxes):
        self.names = names
        self._boxes = boxes
        self.calls = []

    def predict(self, image, **kwargs):
        self.calls.append(kwargs)
        xyxy, conf, cls = zip(*self._boxes) if self._boxes else ((), (), ())
        boxes = SimpleNamespace(xyxy=_Tensor(xyxy), conf=_Tensor(conf), cls=_Tensor(cls))
        return [SimpleNamespace(boxes=boxes)]


def frame(image=True):
    return Frame(0, 0.0, 0.0, 640, 360, np.zeros((360, 640, 3), np.uint8) if image else None)


def test_coco_weights_map_person_and_sports_ball():
    model = StubModel({0: "person", 32: "sports ball", 2: "car"},
                      [([10, 10, 30, 80], 0.9, 0), ([100, 100, 110, 110], 0.6, 32), ([0, 0, 5, 5], 0.9, 2)])  # fmt: skip
    detector = YOLODetector(model, "yolov8n", "cpu", detect_players=True)

    detections = detector.detect(frame())

    assert [(d.cls, d.confidence) for d in detections] == [("player", 0.9), ("ball", 0.6)]
    assert sorted(model.calls[0]["classes"]) == [0, 32]


def test_football_finetune_classes_are_used_directly():
    mapping = _class_map({0: "Ball", 1: "goalkeeper", 2: "player", 3: "referee"})
    assert mapping == {0: "ball", 1: "goalkeeper", 2: "player", 3: "referee"}


def test_ball_only_mode_requests_only_ball_class():
    model = StubModel({0: "person", 32: "sports ball"}, [])
    YOLODetector(model, "yolov8n", "cpu", detect_players=False).detect(frame())
    assert model.calls[0]["classes"] == [32]


def test_model_without_ball_class_fails_loudly():
    with pytest.raises(ModelLoadError, match="no ball class"):
        YOLODetector(StubModel({0: "person"}, []), "people-only", "cpu", detect_players=True)


def test_frames_without_pixels_are_skipped():
    model = StubModel({32: "sports ball"}, [])
    assert YOLODetector(model, "m", "cpu", True).detect(frame(image=False)) == []
    assert model.calls == []


def test_resolve_weights_prefers_local_file(tmp_path):
    (tmp_path / "football.pt").write_bytes(b"x")
    assert resolve_weights("football", tmp_path) == str(tmp_path / "football.pt")
    assert resolve_weights("yolov8n", tmp_path) == "yolov8n.pt"


def test_upload_paths_cannot_escape_media_dir(tmp_path, match_config):
    (tmp_path / "uploads").mkdir()
    (tmp_path / "uploads" / "ok.mp4").write_bytes(b"x")
    ok = match_config.model_copy(update={"source_type": "upload", "source": "uploads/ok.mp4"})
    escape = match_config.model_copy(update={"source_type": "upload", "source": "../secret.mp4"})
    missing = match_config.model_copy(update={"source_type": "upload", "source": "uploads/nope.mp4"})

    assert resolve_source(ok, tmp_path).endswith("uploads/ok.mp4")
    with pytest.raises(SourceError, match="escapes"):
        resolve_source(escape, tmp_path)
    with pytest.raises(SourceError, match="not found"):
        resolve_source(missing, tmp_path)


def test_pitch_mapping_requires_pitch_model():
    base = dict(source_type="hls", source="https://x/y.m3u8", processing_fps=10, confidence_threshold=0.5)
    assert pitch_mapping_enabled(MatchConfig(detection_model="ball_players_pitch", **base))
    assert not pitch_mapping_enabled(MatchConfig(detection_model="ball_players", **base))
