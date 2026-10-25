#!/usr/bin/env python
"""Align a narration script to its TTS audio: word- and sentence-level
timestamps without any ASR step.

The script text is the exact source text you fed to the TTS, so alignment
quality is optimal (forced alignment only fails when text != audio content).

Usage pipeline:
    1. tts_qwen.py --text "$(cat script.txt)" --prefix narration
    2. text_align.py --audio narration.wav --text-file script.txt --language Chinese

Outputs (next to the audio unless --output is given):
    <audio-stem>.align.json   word-level timestamps
    <audio-stem>.srt          sentence-level subtitles (split on 。!?!;\\n)

Path configuration (CLI > env var > default):
    --audio / ALIGN_AUDIO       TTS-generated audio (required)
    --text / ALIGN_TEXT         the source script text (or --text-file)
    --language / ALIGN_LANGUAGE (default: Chinese)
    --model / ALIGNER_MODEL     (default: <models>/Qwen3-ForcedAligner-0.6B-8bit)
    --output / ALIGN_OUTPUT_BASE  output path without extension
                                  (default: same dir/name as the audio)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import (
    ResourceMonitor,
    default_models_dir,
    log_latency,
    resolve_path,
    save_metrics,
)

# sentence-ending punctuation for Chinese/English scripts
_SENT_SPLIT = re.compile(r"(?<=[。！？!?；;])|\n+")


def align_text(
    audio_path: str | Path,
    text: str,
    *,
    model_path: str | Path | None = None,
    language: str = "Chinese",
    load_model_fn=None,
) -> dict:
    """Align `text` to `audio_path` and return word/sentence timestamps.

    Returns {"words": [...], "sentences": [...], "align_s": float}.
    `load_model_fn` lets callers reuse an already-loaded aligner model.
    """
    from mlx_audio.stt.utils import load_model as _load_model

    t0 = time.perf_counter()
    model = load_model_fn if load_model_fn is not None else _load_model(str(model_path))
    aligned = model.generate(audio=str(audio_path), text=text, language=language)
    if isinstance(aligned, list):
        aligned = aligned[0]
    items = getattr(aligned, "items", aligned) or []
    words = [{"word": it.text, "start": round(it.start_time, 3),
              "end": round(it.end_time, 3)} for it in items]
    sentences = group_sentences(words, text)
    return {"words": words, "sentences": sentences,
            "align_s": round(time.perf_counter() - t0, 3)}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--audio", required=True)
    p.add_argument("--text", default=None)
    p.add_argument("--text-file", default=None)
    p.add_argument("--language", default=None)
    p.add_argument("--model", default=None)
    p.add_argument("--output", default=None)
    p.add_argument("--metrics", default=None)
    return p.parse_args()


def group_sentences(words: list[dict], script_text: str) -> list[dict]:
    """Group aligned word spans into sentence spans using the script's
    punctuation. Falls back to pauses > 0.5s when punctuation count differs.
    """
    boundaries = [m.end() for m in _SENT_SPLIT.finditer(script_text)]
    # cumulative character count in the aligned units (aligner units are
    # CJK chars or words, punctuation typically not emitted)
    units = [w["word"] for w in words]
    flat = "".join(units)
    # strip punctuation/spaces from script for index mapping
    stripped = _SENT_SPLIT.split(script_text)
    stripped = [s for s in (s.strip() for s in stripped) if s]

    sentences = []
    pos = 0  # pointer into words
    for chunk in stripped:
        target = re.sub(r"[\s，,、.．:：\"'\"'()（）-]", "", chunk)
        if not target:
            continue
        # find the word span covering this chunk
        acc = ""
        start_word = pos
        while pos < len(words) and len(acc) < len(target):
            acc += words[pos]["word"]
            pos += 1
        if start_word >= len(words):
            break
        sentences.append({
            "text": chunk,
            "start": words[start_word]["start"],
            "end": words[pos - 1]["end"],
        })
    return sentences


def to_srt(sentences: list[dict]) -> str:
    def fmt(t: float) -> str:
        ms = int(round(t * 1000))
        h, ms = divmod(ms, 3600000)
        m, ms = divmod(ms, 60000)
        s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    lines = []
    for i, sent in enumerate(sentences, 1):
        lines.append(f"{i}\n{fmt(sent['start'])} --> {fmt(sent['end'])}\n{sent['text']}\n")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()

    audio_path = resolve_path(args.audio, "ALIGN_AUDIO", Path.cwd())
    model_path = resolve_path(args.model, "ALIGNER_MODEL",
                              default_models_dir() / "Qwen3-ForcedAligner-0.6B-8bit")
    language = args.language or "Chinese"

    text = args.text
    if text is None and args.text_file:
        text = Path(resolve_path(args.text_file, "ALIGN_TEXT_FILE", Path.cwd())).read_text(
            encoding="utf-8").strip()
    if not text:
        raise ValueError("no text: pass --text or --text-file")

    if not audio_path.exists():
        raise FileNotFoundError(f"audio not found: {audio_path}")
    if not model_path.exists():
        raise FileNotFoundError(f"model not found: {model_path}")

    out_base = resolve_path(args.output, "ALIGN_OUTPUT_BASE", audio_path.with_suffix(""))
    metrics_path = resolve_path(args.metrics, "ALIGN_METRICS_FILE",
                                Path(str(out_base) + ".align_metrics.json"))

    print(f"audio    : {audio_path}")
    print(f"text     : {text[:60]}{'...' if len(text) > 60 else ''}")
    print(f"language : {language}")

    monitor = ResourceMonitor(sample_interval=0.5)
    monitor.start()

    result = align_text(audio_path, text, model_path=model_path, language=language)
    words, sentences, elapsed = result["words"], result["sentences"], result["align_s"]

    monitor.stop()
    log_latency("align", time.perf_counter() - elapsed)

    json_path = Path(str(out_base) + ".align.json")
    srt_path = Path(str(out_base) + ".srt")
    json_path.write_text(json.dumps({
        "audio": str(audio_path),
        "language": language,
        "words": words,
        "sentences": sentences,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    srt_path.write_text(to_srt(sentences), encoding="utf-8")

    metrics = {
        "task": "text_align",
        "audio": str(audio_path),
        "model": str(model_path),
        "language": language,
        "align_s": elapsed,
        "num_words": len(words),
        "num_sentences": len(sentences),
        "resources": monitor.summary(),
    }
    save_metrics(metrics_path, metrics)

    print(f"\n{len(words)} words, {len(sentences)} sentences")
    print(f"JSON={json_path}")
    print(f"SRT=  {srt_path}")


if __name__ == "__main__":
    main()
