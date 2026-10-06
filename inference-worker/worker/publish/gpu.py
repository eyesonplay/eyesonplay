"""NVIDIA GPU metrics via NVML. Returns None when no NVIDIA GPU is available,
so the dashboard can hide unsupported metrics instead of showing zeros."""

from __future__ import annotations

from typing import Any

from worker.logging import get_logger

log = get_logger(component="gpu")


class GpuMonitor:
    def __init__(self) -> None:
        self._nvml: Any = None
        self._handles: list[Any] = []
        try:
            import pynvml

            pynvml.nvmlInit()
            self._nvml = pynvml
            self._handles = [pynvml.nvmlDeviceGetHandleByIndex(i) for i in range(pynvml.nvmlDeviceGetCount())]
            log.info("nvml initialised", gpus=len(self._handles))
        except Exception as exc:  # noqa: BLE001 - ImportError or NVMLError: no GPU metrics
            log.info("gpu metrics unavailable", reason=str(exc) or type(exc).__name__)

    @property
    def available(self) -> bool:
        return bool(self._handles)

    def read(self) -> list[dict[str, Any]] | None:
        if not self._handles:
            return None
        nv = self._nvml
        result = []
        for index, handle in enumerate(self._handles):
            try:
                util = nv.nvmlDeviceGetUtilizationRates(handle)
                mem = nv.nvmlDeviceGetMemoryInfo(handle)
                name = nv.nvmlDeviceGetName(handle)
                temp = nv.nvmlDeviceGetTemperature(handle, nv.NVML_TEMPERATURE_GPU)
            except Exception as exc:  # noqa: BLE001
                log.warning("gpu read failed", index=index, error=str(exc))
                continue
            result.append(
                {
                    "index": index,
                    "name": name.decode() if isinstance(name, bytes) else name,
                    "utilization": util.gpu,
                    "memory_used_mb": round(mem.used / 1024**2),
                    "memory_total_mb": round(mem.total / 1024**2),
                    "temperature_c": temp,
                }
            )
        return result or None
