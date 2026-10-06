"""Splits outfield players into two teams by shirt colour.

Colours of `player` detections are collected and clustered into two groups
(k-means, k=2). The clusters are re-fitted as the match goes on, and new
centres are matched to the previous ones so a team keeps its label. Each
track's team is a majority vote over its recent frames, so one bad crop
(shadow, overlap) never flips a player's colour. Players whose colour is far
from both kits (referees with generic detectors, odd crops) stay unassigned.
Which team is home or away is unknown: teams are only "A" and "B".
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from typing import Any

import numpy as np

KMEANS_ITERATIONS = 12


@dataclass(frozen=True, slots=True)
class TeamConfig:
    min_samples: int = 30
    refit_every: int = 60
    max_samples: int = 600
    vote_window: int = 15
    min_votes: int = 3
    outlier_factor: float = 3.0  # x the typical in-cluster distance
    min_center_separation: float = 40.0  # RGB distance between the two kits


@dataclass(frozen=True, slots=True)
class Team:
    id: int  # 0 = A, 1 = B
    color: str  # "#rrggbb", the kit colour as seen on video

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "label": "AB"[self.id], "color": self.color}


class TeamClassifier:
    def __init__(self, config: TeamConfig | None = None) -> None:
        self._cfg = config or TeamConfig()
        self._samples: deque[np.ndarray] = deque(maxlen=self._cfg.max_samples)
        self._since_fit = 0
        self._centers: np.ndarray | None = None  # shape (2, 3)
        self._spread = 0.0
        self._votes: dict[int, deque[int | None]] = {}

    @property
    def teams(self) -> list[Team]:
        if self._centers is None:
            return []
        return [Team(i, _hex(c)) for i, c in enumerate(self._centers)]

    def assign(self, players: list[tuple[int | None, str, np.ndarray | None]]) -> list[int | None]:
        """players: (track_id, class, shirt colour). Returns a team id or None each."""
        for _, cls, color in players:
            if cls == "player" and color is not None:
                self._samples.append(color)
                self._since_fit += 1
        if len(self._samples) >= self._cfg.min_samples and (
            self._centers is None or self._since_fit >= self._cfg.refit_every
        ):
            self._fit()
        return [self._team_for(track_id, cls, color) for track_id, cls, color in players]

    def _team_for(self, track_id: int | None, cls: str, color: np.ndarray | None) -> int | None:
        raw = self._classify(color) if cls == "player" else None
        if track_id is None:
            return raw
        votes = self._votes.setdefault(track_id, deque(maxlen=self._cfg.vote_window))
        votes.append(raw)
        counted = Counter(v for v in votes if v is not None)
        if not counted:
            return None
        team, count = counted.most_common(1)[0]
        return team if count >= self._cfg.min_votes else None

    def _classify(self, color: np.ndarray | None) -> int | None:
        if color is None or self._centers is None:
            return None
        distances = np.linalg.norm(self._centers - color, axis=1)
        best = int(np.argmin(distances))
        if distances[best] > self._cfg.outlier_factor * max(self._spread, 1.0):
            return None
        return best

    def _fit(self) -> None:
        self._since_fit = 0
        data = np.array(self._samples)
        centers, labels = _kmeans2(data)
        if np.linalg.norm(centers[0] - centers[1]) < self._cfg.min_center_separation:
            return  # kits not distinguishable yet (e.g. only one team in view)
        if self._centers is not None:
            # Keep labels stable: swap if the new centres match the old ones crossed.
            straight = np.linalg.norm(centers - self._centers, axis=1).sum()
            crossed = np.linalg.norm(centers[::-1] - self._centers, axis=1).sum()
            if crossed < straight:
                centers, labels = centers[::-1], 1 - labels
        self._centers = centers
        self._spread = float(np.median(np.linalg.norm(data - centers[labels], axis=1)))


def _kmeans2(data: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Deterministic 2-means: farthest-point initialisation, Lloyd iterations."""
    first = data[np.argmin(np.linalg.norm(data - data.mean(axis=0), axis=1))]
    second = data[np.argmax(np.linalg.norm(data - first, axis=1))]
    centers = np.array([first, second], dtype=np.float64)
    labels = np.zeros(len(data), dtype=int)
    for _ in range(KMEANS_ITERATIONS):
        labels = np.argmin(np.linalg.norm(data[:, None, :] - centers[None, :, :], axis=2), axis=1)
        updated = np.array([data[labels == k].mean(axis=0) if np.any(labels == k) else centers[k] for k in (0, 1)])
        if np.allclose(updated, centers):
            break
        centers = updated
    return centers, labels


def _hex(rgb: np.ndarray) -> str:
    r, g, b = (int(np.clip(round(v), 0, 255)) for v in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"
