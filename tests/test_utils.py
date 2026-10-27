"""Direct tests for resource monitoring and latency diagnostics."""
from __future__ import annotations

import builtins
import time
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from utils import ResourceMonitor, log_latency


def test_monitor_handles_absent_optional_process_and_gpu_libraries(monkeypatch: pytest.MonkeyPatch):
    real_import = builtins.__import__

    def without_optional_dependencies(name, *args, **kwargs):
        if name == 'psutil' or name == 'mlx' or name.startswith('mlx.'):
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', without_optional_dependencies)
    monitor = ResourceMonitor(sample_interval=0.25)

    sample = monitor._take_sample()

    assert set(sample) == {'timestamp'}
    assert monitor.summary() == {'sample_interval_s': 0.25}


def test_take_sample_and_summary_aggregate_process_and_gpu_metrics():
    monitor = ResourceMonitor()
    process = SimpleNamespace(
        oneshot=lambda: nullcontext(),
        cpu_percent=lambda interval: 125.0,
        memory_info=lambda: SimpleNamespace(rss=2 * 1024**3),
    )
    gpu = SimpleNamespace(
        get_active_memory=lambda: 512,
        get_peak_memory=lambda: 2 * 1024**3,
    )
    monitor._proc = process
    monitor._mx = gpu

    sample = monitor._take_sample()
    monitor.samples = [sample, {**sample, 'cpu_percent': 75.0, 'rss_bytes': 1024**3}]
    summary = monitor.summary()

    assert sample['cpu_percent'] == 125.0
    assert sample['rss_bytes'] == 2 * 1024**3
    assert sample['gpu_mem_active_bytes'] == 512
    assert sample['gpu_mem_peak_bytes'] == 2 * 1024**3
    assert summary['peak_cpu_percent'] == 125.0
    assert summary['mean_cpu_percent'] == 100.0
    assert summary['peak_rss_gb'] == 2.0
    assert summary['peak_gpu_mem_gb'] == 2.0
    assert summary['num_samples'] == 2


def test_monitor_context_starts_sampling_and_always_stops_the_thread():
    with ResourceMonitor(sample_interval=0.001) as monitor:
        deadline = time.monotonic() + 1.0
        while not monitor.samples and time.monotonic() < deadline:
            time.sleep(0.001)
        assert monitor.samples, 'background monitor did not collect a sample'
        assert monitor._thread is not None

    assert monitor._thread is None
    monitor.stop()  # Stopping an already stopped monitor is safe.


def test_log_latency_returns_elapsed_time_and_writes_only_to_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.setattr(time, 'perf_counter', lambda: 1.25)

    elapsed = log_latency('alignment', 0.5)
    captured = capsys.readouterr()

    assert elapsed == 0.75
    assert captured.out == ''
    assert captured.err == '[latency] alignment: 0.75s\n'
