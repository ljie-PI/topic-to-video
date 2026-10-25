#!/usr/bin/env python3
"""Narrate a script: TTS + forced alignment in one run.

Turns a plain narration script (no timestamps) into:
    - spoken audio cloned from a reference voice (Qwen3-TTS Base)
    - word-level and sentence-level timestamps (Qwen3-ForcedAligner, aligned
      against the ORIGINAL script — no ASR, zero transcription errors)
    - an SRT subtitle file

This is the composition of tts_qwen.py and text_align.py; use those when you
only need one stage. Both heavy models are loaded exactly once.

Path configuration (nothing is hardcoded; CLI > env var > default):
    --text / TTS_TEXT             script text (or positional, or --text-file /
                                  TTS_TEXT_FILE; TTS_TEXT_FILE is read when
                                  neither --text nor --text-file is passed)
    --voice / VOICE_REF           reference voice audio (default: <repo>/resources/my_voice.wav)
    --ref-text / TTS_REF_TEXT     transcript of the reference audio (optional)
    --language / TTS_LANGUAGE     language code (default: auto)
    --model / TTS_MODEL           TTS model (default: <models>/Qwen3-TTS-12Hz-1.7B-Base-bf16)
    --aligner-model / ALIGNER_MODEL (default: <models>/Qwen3-ForcedAligner-0.6B-8bit)
    --output-dir / TTS_OUTPUT_DIR (default: current working directory)
    --prefix / TTS_PREFIX         output file prefix (default: narration)
    --metrics / NARRATE_METRICS_FILE (default: <output-dir>/<prefix>_metrics.json)

Outputs in <output-dir>:
    <prefix>.wav        synthesized audio
    <prefix>.srt        sentence-level subtitles
    <prefix>.align.json word- and sentence-level timestamps
    <prefix>_metrics.json latency + resource usage of every stage

Scriptable: stdout ends with WAV= / SRT= / JSON= lines.

Failures print one JSON line ({"success": false, "error": ...}) on stdout and
exit 1; progress and latency diagnostics go to stderr where noted.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from text_align import align_text, to_srt
from tts_qwen import synthesize
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
    p.add_argument("text_pos", nargs="?", default=None,
                   help="script text (positional; or set TTS_TEXT)")
    p.add_argument("--text", default=None,
                   help="script text (or set TTS_TEXT)")
    p.add_argument("--text-file", default=None,
                   help="file containing the script (or set TTS_TEXT_FILE; used "
                        "when --text is absent)")
    p.add_argument("--voice", default=None,
                   help="reference voice audio (or set VOICE_REF; default: "
                        "<repo>/resources/my_voice.wav)")
    p.add_argument("--ref-text", default=None,
                   help="transcript of the reference audio, optional (or set "
                        "TTS_REF_TEXT)")
    p.add_argument("--language", default=None,
                   help="language code (or set TTS_LANGUAGE; default: auto)")
    p.add_argument("--model", default=None,
                   help="TTS model dir or HF id (or set TTS_MODEL)")
    p.add_argument("--aligner-model", default=None,
                   help="forced aligner model dir or HF id (or set ALIGNER_MODEL)")
    p.add_argument("--output-dir", default=None,
                   help="output directory (or set TTS_OUTPUT_DIR; default: cwd)")
    p.add_argument("--prefix", default=None,
                   help="output file prefix (or set TTS_PREFIX; default: narration)")
    p.add_argument("--metrics", default=None,
                   help="metrics JSON path (or set NARRATE_METRICS_FILE)")
    return p.parse_args()


def main() -> int:
    """Run TTS + alignment; human-readable progress on success, JSON on failure."""
    try:
        return _run(parse_args())
    except Exception as exc:  # noqa: BLE001 - failures end with one JSON line
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False))
        return 1


def _run(args: argparse.Namespace) -> int:
    # ---- resolve inputs ---------------------------------------------------
    model_path = resolve_path(args.model, "TTS_MODEL",
                              default_models_dir() / "Qwen3-TTS-12Hz-1.7B-Base-bf16")
    aligner_path = resolve_path(args.aligner_model, "ALIGNER_MODEL",
                                default_models_dir() / "Qwen3-ForcedAligner-0.6B-8bit")
    voice_path = resolve_path(args.voice, "VOICE_REF", Path.cwd() / "my_voice.wav")
    if not voice_path.exists():
        fallback = resolve_path(None, "VOICE_REF",
                                Path(__file__).resolve().parent.parent / "resources" / "my_voice.wav")
        if fallback.exists():
            voice_path = fallback
    output_dir = resolve_path(args.output_dir, "TTS_OUTPUT_DIR", Path.cwd())
    prefix = args.prefix or os.environ.get("TTS_PREFIX") or "narration"
    metrics_path = resolve_path(args.metrics, "NARRATE_METRICS_FILE",
                                output_dir / f"{prefix}_metrics.json")

    text = args.text_pos or args.text
    if text is None:
        text_file = args.text_file or os.environ.get("TTS_TEXT_FILE")
        if text_file:
            text = Path(
                resolve_path(text_file, "TTS_TEXT_FILE", Path.cwd())
            ).read_text(encoding="utf-8").strip()
    if not text:
        text = os.environ.get("TTS_TEXT")
    if not text:
        raise ValueError(
            "no script text: pass it positionally, via --text / --text-file, "
            "or set TTS_TEXT / TTS_TEXT_FILE"
        )

    ref_text = args.ref_text or os.environ.get("TTS_REF_TEXT") or None
    language = args.language or os.environ.get("TTS_LANGUAGE") or "auto"

    for p, label in [(model_path, "TTS model"), (aligner_path, "aligner model"),
                     (voice_path, "voice reference")]:
        if not p.exists():
            raise FileNotFoundError(f"{label} not found: {p}")

    output_dir.mkdir(parents=True, exist_ok=True)
    wav_path = output_dir / f"{prefix}.wav"
    srt_path = output_dir / f"{prefix}.srt"
    json_path = output_dir / f"{prefix}.align.json"

    print(f"tts model : {model_path}")
    print(f"aligner   : {aligner_path}")
    print(f"voice     : {voice_path}")
    print(f"language  : {language}")
    print(f"text      : {text[:80]}{'...' if len(text) > 80 else ''}")
    print(f"output    : {wav_path} (+ .srt, .align.json)")

    monitor = ResourceMonitor(sample_interval=0.5)
    monitor.start()
    t_all = time.perf_counter()

    # ---- load both models once --------------------------------------------
    from mlx_audio.stt.utils import load_model as load_stt_model
    from mlx_audio.tts.utils import load_model as load_tts_model

    t0 = time.perf_counter()
    tts_model = load_tts_model(str(model_path))
    tts_load_s = log_latency("tts model load", t0)

    t0 = time.perf_counter()
    aligner_model = load_stt_model(str(aligner_path))
    aligner_load_s = log_latency("aligner model load", t0)

    # ---- stage 1: synthesize ----------------------------------------------
    tts_metrics = synthesize(
        text, wav_path,
        voice_path=voice_path, model_path=model_path,
        language=language, ref_text=ref_text,
        load_model_fn=tts_model,
    )

    # ---- stage 2: align the ORIGINAL script against the fresh audio -------
    # the aligner wants a language name, not a code
    align_language = "Chinese" if language == "auto" else language.capitalize()
    t_align = time.perf_counter()
    align_metrics = align_text(
        wav_path, text,
        model_path=aligner_path, language=align_language,
        load_model_fn=aligner_model,
    )
    log_latency("align", t_align)

    words = align_metrics["words"]
    sentences = align_metrics["sentences"]

    json_path.write_text(json.dumps({
        "audio": str(wav_path),
        "language": language,
        "script": text,
        "words": words,
        "sentences": sentences,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    srt_path.write_text(to_srt(sentences), encoding="utf-8")

    monitor.stop()
    metrics = {
        "task": "narrate",
        "text": text,
        "language": language,
        "tts": {"model": str(model_path), "voice_ref": str(voice_path), **tts_metrics},
        "align": {"model": str(aligner_path),
                  "align_s": align_metrics["align_s"],
                  "num_words": len(words), "num_sentences": len(sentences)},
        "stage_loads": {"tts_model_load_s": tts_load_s, "aligner_model_load_s": aligner_load_s},
        "total_s": round(time.perf_counter() - t_all, 3),
        "resources": monitor.summary(),
        "outputs": {"wav": str(wav_path), "srt": str(srt_path), "json": str(json_path)},
    }
    save_metrics(metrics_path, metrics)

    print(f"\n{len(words)} words, {len(sentences)} sentences")
    print(f"WAV=  {wav_path}")
    print(f"SRT=  {srt_path}")
    print(f"JSON= {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
