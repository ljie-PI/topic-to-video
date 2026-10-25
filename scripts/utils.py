"""Shared helpers for voice-utils: resource monitoring, path resolution, metrics.

Path resolution order for every configurable path:
    1. explicit CLI argument (handled in each tool)
    2. environment variable
    3. default relative to the repository root
       (the parent directory of this file's directory)
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Optional

SCRIPT_DIR = Path(__file__).resolve().parent          # <repo>/scripts
REPO_ROOT = SCRIPT_DIR.parent                          # repo root (contains models/)


def resolve_path(cli_value: Optional[str], env_var: str, default: Path) -> Path:
    """Resolve a path: CLI arg > env var > default."""
    value = cli_value or os.environ.get(env_var)
    path = Path(value) if value else Path(default)
    return path.resolve()


def default_models_dir() -> Path:
    return REPO_ROOT / "models"


class ResourceMonitor:
    """Background sampler of process CPU / RSS and MLX GPU memory.

    Process CPU% on macOS can exceed 100 when multiple cores are used.
    """

    def __init__(self, sample_interval: float = 0.5):
        self.sample_interval = sample_interval
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.samples: list[dict[str, Any]] = []
        self._psutil = None
        self._proc = None
        self._mx = None
        try:
            import psutil  # type: ignore

            self._psutil = psutil
            self._proc = psutil.Process(os.getpid())
            self._proc.cpu_percent(None)  # prime
        except ImportError:
            pass
        try:
            import mlx.core as mx  # type: ignore

            self._mx = mx
        except ImportError:
            pass

    def _take_sample(self) -> dict[str, Any]:
        sample: dict[str, Any] = {"timestamp": time.time()}
        if self._proc is not None:
            with self._proc.oneshot():
                sample["cpu_percent"] = self._proc.cpu_percent(None)
                sample["rss_bytes"] = self._proc.memory_info().rss
        if self._mx is not None:
            try:
                get_active = getattr(self._mx, "get_active_memory", None) or self._mx.metal.get_active_memory
                get_peak = getattr(self._mx, "get_peak_memory", None) or self._mx.metal.get_peak_memory
                sample["gpu_mem_active_bytes"] = int(get_active())
                sample["gpu_mem_peak_bytes"] = int(get_peak())
            except Exception:
                pass
        return sample

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.samples.append(self._take_sample())
            except Exception:
                pass
            self._stop_event.wait(self.sample_interval)

    def start(self) -> None:
        if self._thread is None:
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        if self._thread is not None:
            self._stop_event.set()
            self._thread.join(timeout=5)
            self._thread = None

    def __enter__(self) -> "ResourceMonitor":
        self.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.stop()

    def summary(self) -> dict[str, Any]:
        summary: dict[str, Any] = {"sample_interval_s": self.sample_interval}
        if not self.samples:
            return summary

        def _max(key: str) -> Optional[float]:
            vals = [s[key] for s in self.samples if key in s]
            return max(vals) if vals else None

        def _mean(key: str) -> Optional[float]:
            vals = [s[key] for s in self.samples if key in s]
            return sum(vals) / len(vals) if vals else None

        summary["peak_cpu_percent"] = _max("cpu_percent")
        summary["mean_cpu_percent"] = _mean("cpu_percent")
        summary["peak_rss_bytes"] = _max("rss_bytes")
        summary["peak_rss_gb"] = (
            round(summary["peak_rss_bytes"] / 1024**3, 3)
            if summary["peak_rss_bytes"] is not None
            else None
        )
        summary["peak_gpu_mem_bytes"] = _max("gpu_mem_peak_bytes")
        summary["peak_gpu_mem_gb"] = (
            round(summary["peak_gpu_mem_bytes"] / 1024**3, 3)
            if summary["peak_gpu_mem_bytes"] is not None
            else None
        )
        summary["num_samples"] = len(self.samples)
        return summary


def save_metrics(path: Path, metrics: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    print(f"[metrics] saved -> {path}")


def log_latency(stage: str, started: float) -> float:
    elapsed = time.perf_counter() - started
    print(f"[latency] {stage}: {elapsed:.2f}s")
    return elapsed
