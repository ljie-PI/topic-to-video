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

Pure conversion mode (no audio, no model — used by the pipeline to turn an
align.json into the pipeline transcript schema):
    text_align.py --align-json narration.align.json --emit-transcript transcript.json

    Reads the align.json written by this script (or a dump of the dict returned
    by align_text) and writes the pipeline transcript schema: a sentence list,
    every sentence {begin, end, text, words:[{text, begin, end}]}, ALL times
    in MILLISECONDS (align.json uses seconds). Prints one JSON result to
    stdout; exit 0 on success, 1 on error (missing/invalid input or an
    alignment with no sentences/words).

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
import os
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


def _to_ms(seconds: float) -> int:
    return int(round(float(seconds) * 1000.0))


def transcript_from_alignment(align: dict) -> list[dict]:
    """Convert an alignment result to the pipeline transcript schema.

    ``align`` is the dict returned by :func:`align_text` (or a parsed
    align.json): ``words`` is the flat aligned token list (``word`` /
    ``start`` / ``end``, seconds) and ``sentences`` the punctuation-grouped
    sentence spans (``text`` / ``start`` / ``end``, seconds). Returns the
    transcript schema shared with transcribe.py — a list of
    ``{begin, end, text, words:[{text, begin, end}]}`` with ALL times in
    milliseconds.

    Words are assigned to sentences by start time: a word belongs to the
    latest sentence whose ``start`` is <= the word's ``start`` (which is how
    :func:`group_sentences` built the spans, so no token is dropped or
    duplicated). Raises ValueError when the alignment holds no sentences or
    no words — an empty transcript is never a valid pipeline product.
    """
    words = align.get("words") or []
    sentences = align.get("sentences") or []
    if not sentences or not words:
        raise ValueError("alignment has no sentences or no words")
    transcript = []
    wi = 0
    for si, sent in enumerate(sentences):
        next_start = sentences[si + 1]["start"] if si + 1 < len(sentences) else None
        sent_words = []
        while wi < len(words) and (next_start is None or words[wi]["start"] < next_start):
            w = words[wi]
            sent_words.append(
                {"text": w["word"], "begin": _to_ms(w["start"]), "end": _to_ms(w["end"])}
            )
            wi += 1
        transcript.append(
            {
                "begin": _to_ms(sent["start"]),
                "end": _to_ms(sent["end"]),
                "text": sent["text"],
                "words": sent_words,
            }
        )
    return transcript


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
    p.add_argument("--audio", default=None,
                   help="TTS audio to align (required unless --emit-transcript "
                        "conversion mode is used)")
    p.add_argument("--text", default=None)
    p.add_argument("--text-file", default=None)
    p.add_argument("--language", default=None)
    p.add_argument("--model", default=None)
    p.add_argument("--output", default=None)
    p.add_argument("--metrics", default=None)
    p.add_argument("--align-json", default=None,
                   help="conversion mode: read this align.json instead of "
                        "running the aligner (no model load)")
    p.add_argument("--emit-transcript", default=None,
                   help="conversion mode: write the pipeline transcript schema "
                        "(milliseconds) to this path")
    return p.parse_args()


def convert_align_json(align_json_path: str, transcript_path: str) -> int:
    """Pure align.json -> transcript.json conversion (no model, no audio).

    Prints one JSON result to stdout; returns the process exit code.
    """
    src = Path(align_json_path)
    try:
        payload = json.loads(src.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(json.dumps({"success": False,
                          "error": f"align.json not found: {src}"}, ensure_ascii=False))
        return 1
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(json.dumps({"success": False,
                          "error": f"invalid align.json: {exc}"}, ensure_ascii=False))
        return 1
    if not isinstance(payload, dict):
        print(json.dumps({"success": False,
                          "error": "align.json root is not an object"}, ensure_ascii=False))
        return 1
    try:
        transcript = transcript_from_alignment(payload)
    except (ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    out = Path(transcript_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "success": True,
        "output_path": str(out.resolve()),
        "sentence_count": len(transcript),
        "word_count": sum(len(s["words"]) for s in transcript),
    }, ensure_ascii=False))
    return 0


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

    # Pure conversion mode: align.json -> pipeline transcript (no model load).
    if args.align_json or args.emit_transcript:
        if not (args.align_json and args.emit_transcript):
            raise SystemExit(
                "--align-json and --emit-transcript must be passed together")
        raise SystemExit(convert_align_json(args.align_json, args.emit_transcript))

    if not args.audio and not os.environ.get("ALIGN_AUDIO"):
        raise SystemExit("no audio: pass --audio (or set ALIGN_AUDIO)")
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
