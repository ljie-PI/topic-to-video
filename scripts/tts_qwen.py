#!/usr/bin/env python
"""Qwen TTS: clone a reference voice with Qwen3-TTS Base (mlx-audio).

Designed for the Qwen codec architecture whose output is already clean —
no post-processing denoise stage. Emits the audio and a metrics JSON with
latency and resource usage (CPU / memory / GPU memory).

Path configuration (nothing is hardcoded; CLI > env var > default):
    --text / TTS_TEXT             text to synthesize (or --text-file / TTS_TEXT_FILE)
    --voice / VOICE_REF           reference audio (default: <repo>/resources/my_voice.wav)
    --ref-text / TTS_REF_TEXT     transcript of the reference audio (optional —
                                  Qwen Base clones well without it)
    --language / TTS_LANGUAGE     language code (default: auto)
    --model / TTS_MODEL           model dir (default: <models>/Qwen3-TTS-12Hz-1.7B-Base-bf16)
    --output-dir / TTS_OUTPUT_DIR (default: current working directory)
    --prefix / TTS_PREFIX         output file prefix (default: tts)
    --metrics / TTS_METRICS_FILE  (default: <output-dir>/<prefix>_metrics.json)

Outputs:
    <output-dir>/<prefix>.wav     synthesized audio
    metrics JSON

Scriptable: stdout ends with OUTPUT=<path> so callers can do
    out=$(python tts_qwen.py --text "..." | grep '^OUTPUT=' | cut -d= -f2)
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# make utils importable regardless of CWD
sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import (
    ResourceMonitor,
    default_models_dir,
    log_latency,
    resolve_path,
    save_metrics,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("text_pos", nargs="?", default=None, help="text to synthesize (positional)")
    p.add_argument("--text", default=None, help="text to synthesize")
    p.add_argument("--text-file", default=None, help="file containing the text")
    p.add_argument("--voice", default=None, help="reference audio for the voice")
    p.add_argument("--ref-text", default=None, help="transcript of the reference audio (optional)")
    p.add_argument("--language", default=None, help="language code (default: auto)")
    p.add_argument("--model", default=None)
    p.add_argument("--output-dir", default=None)
    p.add_argument("--prefix", default=None)
    p.add_argument("--metrics", default=None)
    return p.parse_args()


def synthesize(
    text: str,
    output_path: str | Path,
    *,
    voice_path: str | Path | None = None,
    model_path: str | Path | None = None,
    language: str = "auto",
    ref_text: str | None = None,
    load_model_fn=None,
) -> dict:
    """Clone the reference voice and synthesize `text` into `output_path`.

    Returns a metrics dict (latencies + resources). `load_model_fn` lets
    callers (e.g. narrate.py) reuse an already-loaded model across calls.
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

    # mlx-audio may suffix segmented output with _000 — pick what was produced
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


def main() -> None:
    args = parse_args()

    # ---- resolve inputs ---------------------------------------------------
    model_path = resolve_path(args.model, "TTS_MODEL",
                              default_models_dir() / "Qwen3-TTS-12Hz-1.7B-Base-bf16")
    voice_path = resolve_path(args.voice, "VOICE_REF", Path.cwd() / "my_voice.wav")
    if not voice_path.exists():
        # fall back to the repo workspace default voice
        fallback = resolve_path(None, "VOICE_REF",
                                Path(__file__).resolve().parent.parent / "resources" / "my_voice.wav")
        if fallback.exists():
            voice_path = fallback
    output_dir = resolve_path(args.output_dir, "TTS_OUTPUT_DIR", Path.cwd())
    prefix = args.prefix or os.environ.get("TTS_PREFIX") or "tts"
    metrics_path = resolve_path(args.metrics, "TTS_METRICS_FILE",
                                output_dir / f"{prefix}_metrics.json")

    text = args.text_pos or args.text
    if text is None and args.text_file:
        text = Path(resolve_path(args.text_file, "TTS_TEXT_FILE", Path.cwd())).read_text(
            encoding="utf-8").strip()
    if text is None:
        text = os.environ.get("TTS_TEXT")
    if not text:
        raise ValueError("no text: pass it positionally, via --text / --text-file / TTS_TEXT")

    ref_text = args.ref_text or os.environ.get("TTS_REF_TEXT") or None
    language = args.language or os.environ.get("TTS_LANGUAGE") or "auto"

    if not model_path.exists():
        raise FileNotFoundError(f"model not found: {model_path}")
    if not voice_path.exists():
        raise FileNotFoundError(f"voice reference not found: {voice_path}")

    output_path = output_dir / f"{prefix}.wav"

    print(f"model     : {model_path}")
    print(f"voice     : {voice_path}")
    print(f"language  : {language}")
    print(f"text      : {text}")
    print(f"output    : {output_path}")

    metrics = synthesize(
        text, output_path,
        voice_path=voice_path, model_path=model_path,
        language=language, ref_text=ref_text,
    )
    metrics["task"] = "qwen_tts_clone"
    save_metrics(metrics_path, metrics)

    print(f"OUTPUT={output_path}")


if __name__ == "__main__":
    main()
