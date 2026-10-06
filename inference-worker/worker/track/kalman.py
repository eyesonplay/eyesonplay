"""2D constant-velocity Kalman filter (state: x, y, vx, vy)."""

from __future__ import annotations

import numpy as np


class ConstantVelocityKalman:
    def __init__(self, x: float, y: float, process_noise: float = 400.0, measurement_noise: float = 9.0) -> None:
        self.state = np.array([x, y, 0.0, 0.0])
        self.cov = np.diag([measurement_noise, measurement_noise, 2500.0, 2500.0])
        self._q = process_noise
        self._r = np.eye(2) * measurement_noise
        self._h = np.array([[1.0, 0, 0, 0], [0, 1.0, 0, 0]])

    def predict(self, dt: float) -> np.ndarray:
        f = np.eye(4)
        f[0, 2] = f[1, 3] = dt
        # Piecewise white-acceleration process noise.
        g = np.array([[0.5 * dt**2, 0], [0, 0.5 * dt**2], [dt, 0], [0, dt]])
        self.state = f @ self.state
        self.cov = f @ self.cov @ f.T + g @ g.T * self._q
        return self.state[:2].copy()

    def update(self, x: float, y: float) -> None:
        z = np.array([x, y])
        innovation = z - self._h @ self.state
        s = self._h @ self.cov @ self._h.T + self._r
        k = self.cov @ self._h.T @ np.linalg.inv(s)
        self.state = self.state + k @ innovation
        self.cov = (np.eye(4) - k @ self._h) @ self.cov

    @property
    def position(self) -> tuple[float, float]:
        return float(self.state[0]), float(self.state[1])

    @property
    def velocity(self) -> tuple[float, float]:
        return float(self.state[2]), float(self.state[3])
