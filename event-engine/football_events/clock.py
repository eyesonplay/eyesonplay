"""Match clock formatting."""

from __future__ import annotations


def format_match_clock(video_ts: float, kickoff_offset_seconds: float = 0.0) -> str:
    """`video_ts + offset` as MM:SS. Minutes are not capped at 90 (added time)."""
    total = max(0, int(video_ts + kickoff_offset_seconds))
    minutes, seconds = divmod(total, 60)
    return f"{minutes:02d}:{seconds:02d}"
