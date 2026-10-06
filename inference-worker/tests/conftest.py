from __future__ import annotations

import pytest

from worker.config import WorkerSettings
from worker.control.commands import MatchConfig


@pytest.fixture
def settings(tmp_path) -> WorkerSettings:
    return WorkerSettings(
        inference_mode="mock",
        worker_id="test-worker",
        media_dir=tmp_path,
        models_dir=tmp_path,
        mock_seed=7,
        control_poll_interval_s=0.05,
        metrics_interval_s=0.2,
        source_reconnect_attempts=1,
        source_reconnect_base_delay_s=0.05,
        source_read_timeout_s=5,
    )


@pytest.fixture
def match_config() -> MatchConfig:
    return MatchConfig(
        source_type="hls",
        source="https://example.com/live.m3u8",
        processing_fps=10,
        detection_model="ball_players_pitch",
        confidence_threshold=0.5,
    )
