"""TrackNet tennis-ball detector.

Network re-implemented from yastrebksv/TennisProject (TrackNet, Huang et al.)
with identical layer names so the published weights load unchanged. Those
weights carry no licence: personal testing only, see docs/third-party.md.

TrackNet looks at three consecutive frames (current + two previous, 640x360),
so motion blur that defeats single-frame detectors becomes a signal. It
outputs a 256-level heatmap per pixel; the ball is the circle found in the
thresholded heatmap, preferring the one closest to the previous position.
"""

from __future__ import annotations

import threading
from collections import deque
from pathlib import Path
from typing import Any

import numpy as np

from worker.detect.base import Detection, ModelLoadError
from worker.ingest.source import Frame
from worker.logging import get_logger

log = get_logger(component="tracknet")

INPUT_W, INPUT_H = 640, 360
HEATMAP_THRESHOLD = 127
MAX_JUMP_AT_720P = 80.0  # px between consecutive detections (original postprocess)
BALL_BOX_AT_720P = 12.0
DEFAULT_WEIGHTS = "tracknet_ball.pt"

_models: dict[tuple[str, str], Any] = {}
_models_lock = threading.Lock()


def _build_network() -> Any:
    import torch.nn as nn

    class ConvBlock(nn.Module):
        def __init__(self, in_channels: int, out_channels: int) -> None:
            super().__init__()
            self.block = nn.Sequential(
                nn.Conv2d(in_channels, out_channels, 3, stride=1, padding=1, bias=True),
                nn.ReLU(),
                nn.BatchNorm2d(out_channels),
            )

        def forward(self, x: Any) -> Any:
            return self.block(x)

    class BallTrackerNet(nn.Module):
        def __init__(self, input_channels: int = 9, out_channels: int = 256) -> None:
            super().__init__()
            self.conv1, self.conv2 = ConvBlock(input_channels, 64), ConvBlock(64, 64)
            self.pool1 = nn.MaxPool2d(2, 2)
            self.conv3, self.conv4 = ConvBlock(64, 128), ConvBlock(128, 128)
            self.pool2 = nn.MaxPool2d(2, 2)
            self.conv5, self.conv6, self.conv7 = ConvBlock(128, 256), ConvBlock(256, 256), ConvBlock(256, 256)
            self.pool3 = nn.MaxPool2d(2, 2)
            self.conv8, self.conv9, self.conv10 = ConvBlock(256, 512), ConvBlock(512, 512), ConvBlock(512, 512)
            self.ups1 = nn.Upsample(scale_factor=2)
            self.conv11, self.conv12, self.conv13 = ConvBlock(512, 256), ConvBlock(256, 256), ConvBlock(256, 256)
            self.ups2 = nn.Upsample(scale_factor=2)
            self.conv14, self.conv15 = ConvBlock(256, 128), ConvBlock(128, 128)
            self.ups3 = nn.Upsample(scale_factor=2)
            self.conv16, self.conv17, self.conv18 = ConvBlock(128, 64), ConvBlock(64, 64), ConvBlock(64, out_channels)

        def forward(self, x: Any) -> Any:
            x = self.pool1(self.conv2(self.conv1(x)))
            x = self.pool2(self.conv4(self.conv3(x)))
            x = self.pool3(self.conv7(self.conv6(self.conv5(x))))
            x = self.ups1(self.conv10(self.conv9(self.conv8(x))))
            x = self.ups2(self.conv13(self.conv12(self.conv11(x))))
            x = self.ups3(self.conv15(self.conv14(x)))
            return self.conv18(self.conv17(self.conv16(x)))

    return BallTrackerNet()


def load_tracknet(models_dir: Path, device: str, name: str = DEFAULT_WEIGHTS) -> Any:
    path = models_dir / name
    if not path.is_file():
        raise ModelLoadError(f"TrackNet weights not installed ({path}); see README > Tennis ball tracking")
    key = (str(path), device)
    with _models_lock:
        if key not in _models:
            try:
                import torch

                net = _build_network()
                net.load_state_dict(torch.load(path, map_location="cpu"))
                net = net.to(device).eval()
                if device in ("cuda", "mps"):
                    net = net.half()  # identical heatmaps, ~25% faster on Apple GPUs, more on NVIDIA
                _models[key] = net
            except Exception as exc:  # noqa: BLE001 - surface load failures clearly
                raise ModelLoadError(f"failed to load TrackNet weights {path.name}: {exc}") from exc
            log.info("tracknet loaded", weights=str(path), device=device)
        return _models[key]


class TrackNetBallDetector:
    """Per-match detector (keeps the previous frames); the network is shared."""

    name = "tracknet"
    family = "tracknet"

    def __init__(self, network: Any, device: str) -> None:
        self._net = network
        self.device = device
        self._lock = threading.Lock()
        self._previous: deque[np.ndarray] = deque(maxlen=2)
        self._last: tuple[float, float] | None = None

    def detect(self, frame: Frame) -> list[Detection]:
        if frame.image is None:
            return []
        import cv2

        small = cv2.resize(frame.image, (INPUT_W, INPUT_H)).astype(np.float32) / 255.0
        if len(self._previous) < 2:
            self._previous.append(small)
            return []
        stacked = np.concatenate((small, self._previous[-1], self._previous[-2]), axis=2)
        self._previous.append(small)
        heatmap = self._infer(stacked)
        found = self._locate(heatmap, frame.width / INPUT_W, frame.height / INPUT_H, frame.height / 720.0)
        self._last = found
        if found is None:
            return []
        x, y = found
        half = BALL_BOX_AT_720P * frame.height / 720.0 / 2
        return [Detection("ball", (x - half, y - half, x + half, y + half), 0.8)]

    def _infer(self, stacked: np.ndarray) -> np.ndarray:
        import torch

        tensor = torch.from_numpy(np.ascontiguousarray(np.rollaxis(stacked, 2, 0))[None]).to(self.device)
        if self.device in ("cuda", "mps"):
            tensor = tensor.half()
        with self._lock, torch.no_grad():
            out = self._net(tensor)
        return (out.argmax(dim=1)[0].detach().cpu().numpy()).astype(np.uint8)

    def _locate(self, heatmap: np.ndarray, sx: float, sy: float, scale_720: float) -> tuple[float, float] | None:
        import cv2

        _, binary = cv2.threshold(heatmap, HEATMAP_THRESHOLD, 255, cv2.THRESH_BINARY)
        circles = cv2.HoughCircles(binary, cv2.HOUGH_GRADIENT, dp=1, minDist=1, param1=50, param2=2, minRadius=2, maxRadius=7)
        if circles is None:
            return None
        candidates = [(float(c[0]) * sx, float(c[1]) * sy) for c in circles[0]]
        if self._last is None:
            return candidates[0]
        max_jump = MAX_JUMP_AT_720P * scale_720
        for x, y in candidates:
            if np.hypot(x - self._last[0], y - self._last[1]) < max_jump:
                return x, y
        return None


class TennisDetector:
    """Players from the generic detector, the ball from TrackNet."""

    family = "tennis"

    def __init__(self, players: Any, ball: TrackNetBallDetector) -> None:
        self._players = players
        self._ball = ball
        self.name = f"{players.name}+tracknet"
        self.device = ball.device

    def detect(self, frame: Frame) -> list[Detection]:
        people = [d for d in self._players.detect(frame) if d.cls != "ball"]
        return people + self._ball.detect(frame)
