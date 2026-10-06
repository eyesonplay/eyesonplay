"""Frame source contract.

A source is a blocking iterator of `Frame`s, consumed from a worker thread.
Sources do their own frame sampling (to the configured processing fps) so
that unnecessary frames are never decoded or sent to the detector.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np


class SourceError(RuntimeError):
    """The source cannot deliver frames (after any reconnect attempts)."""


ReconnectCallback = Callable[[int, str], None]


@dataclass(frozen=True, slots=True)
class Frame:
    frame_number: int  # index of the processed (sampled) frame
    video_ts: float  # seconds since source start
    wall_ts: float  # unix time the frame was captured/read
    width: int
    height: int
    image: np.ndarray | None = None  # BGR, None for mock frames
    truth: Any = None  # ground-truth world state (mock mode only)


class FrameSource(Protocol):
    width: int
    height: int
    source_fps: float | None
    is_live: bool

    def __iter__(self) -> Iterator[Frame]: ...

    def close(self) -> None: ...
