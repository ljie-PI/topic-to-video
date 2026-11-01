"""语音相关工具共享的资源监控与延迟日志辅助函数。"""

from __future__ import annotations

import os
import sys
import threading
import time
from typing import Any, Optional


class ResourceMonitor:
    """后台采样进程 CPU / RSS 与 MLX GPU 显存。

    macOS 上多核并行时，进程 CPU% 可能超过 100。
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
            self._proc.cpu_percent(None)  # 预热
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


def log_latency(stage: str, started: float) -> float:
    """把某阶段的实际耗时写到 STDERR，并返回耗秒数。

    诊断信息绝不能写到 stdout：``voice-clone.py``（mlx 后端）通过
    ``tts_qwen.synthesize`` 调用这里，而它的 stdout 必须恰好是一个 JSON 文档，
    所以往 stdout 打一行 ``[latency]`` 会破坏这一约定。
    """
    elapsed = time.perf_counter() - started
    print(f"[latency] {stage}: {elapsed:.2f}s", file=sys.stderr)
    return elapsed
