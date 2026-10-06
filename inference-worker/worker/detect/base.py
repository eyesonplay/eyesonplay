"""Detector contract. Implementations: MockDetector, YOLODetector.

Adding another model (e.g. RF-DETR) means one new module implementing
`Detector` plus one entry in `worker.detect.registry`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from worker.ingest.source import Frame

DetectionClass = Literal["ball", "player", "goalkeeper", "referee"]


class ModelLoadError(RuntimeError):
    """The detection model could not be loaded."""


@dataclass(frozen=True, slots=True)
class Detection:
    cls: DetectionClass
    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2 pixels
    confidence: float
    # Known shirt colour (RGB) when the detector provides it (mock mode);
    # real detectors leave it None and the colour is read from the image.
    appearance: tuple[float, float, float] | None = None

    @property
    def center(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        return (x1 + x2) / 2, (y1 + y2) / 2


class Detector(Protocol):
    name: str
    family: str
    device: str

    def detect(self, frame: Frame) -> list[Detection]: ...
