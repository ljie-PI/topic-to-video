#!/usr/bin/env python3
"""用 mlx-audio 克隆参考音色的 Qwen TTS 库。

mlx-audio 的导入仍留在 :func:`synthesize` 内部惰性执行，因此调用方无需安装 MLX
即可导入本模块。延迟诊断信息写到 stderr。
"""

from __future__ import annotations

import sys
from pathlib import Path

# 让 utils 无论当前工作目录是什么都能被导入
sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import ResourceMonitor, log_latency


def synthesize(
    text: str,
    output_path: str | Path,
    *,
    voice_path: str | Path | None = None,
    model_path: str | Path | None = None,
    language: str = "auto",
    ref_text: str | None = None,
    load_model_fn=None,
) -> dict:  # pragma: no cover - 需要受支持硬件上有真实的 mlx-audio TTS 模型。
    """克隆参考音色，并把 `text` 合成到 `output_path`。

    返回一个指标 dict（各阶段延迟 + 资源占用）。`load_model_fn` 让调用方在多
    次调用之间复用已加载的模型。
    """
    import time as _time

    from mlx_audio.tts.generate import generate_audio
    from mlx_audio.tts.utils import load_model as _load_model

    output_path = Path(output_path)
    output_dir = output_path.parent
    prefix = output_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)

    monitor = ResourceMonitor(sample_interval=0.5)
    monitor.start()
    t_all = _time.perf_counter()

    metrics: dict = {"model": str(model_path), "voice_ref": str(voice_path),
                     "language": language, "text": text, "ref_text": ref_text}

    t0 = _time.perf_counter()
    model = load_model_fn if load_model_fn is not None else _load_model(str(model_path))
    metrics["model_load_s"] = log_latency("model load", t0) if load_model_fn is None else 0.0

    t0 = _time.perf_counter()
    generate_audio(
        text=text,
        model=model,
        ref_audio=str(voice_path) if voice_path else None,
        ref_text=ref_text,
        lang_code=language,
        output_path=str(output_dir),
        file_prefix=prefix,
        save=True,
        verbose=False,
    )
    metrics["synthesize_s"] = log_latency("synthesize", t0)

    # mlx-audio 可能给分段输出加 _000 后缀 —— 取实际产出的那个
    candidates = sorted(output_dir.glob(f"{prefix}*.wav"))
    if not candidates:
        raise RuntimeError(f"synthesis produced no file matching {prefix}*.wav in {output_dir}")
    produced = candidates[0]
    if produced != output_path:
        produced.rename(output_path)

    monitor.stop()
    metrics["resources"] = monitor.summary()
    metrics["total_s"] = round(_time.perf_counter() - t_all, 3)
    metrics["output"] = str(output_path)
    return metrics
