"""Compute device selection: CUDA when available, then Apple MPS (local
development on a Mac), otherwise CPU."""

from __future__ import annotations

from worker.logging import get_logger

log = get_logger(component="device")


def select_device(mode: str) -> str:
    if mode == "mock":
        return "cpu"
    try:
        import torch
    except ImportError:
        log.warning("torch not installed; using cpu")
        return "cpu"
    if torch.cuda.is_available():
        name = torch.cuda.get_device_name(0)
        log.info("cuda available", gpu=name)
        return "cuda"
    if torch.backends.mps.is_available():
        log.info("cuda unavailable; using apple mps")
        return "mps"
    log.warning("cuda unavailable; falling back to cpu")
    return "cpu"
