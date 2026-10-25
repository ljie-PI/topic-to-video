#!/usr/bin/env python3
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
    in MILLISECONDS (align.json uses seconds).

stdout is exactly one JSON document in every mode: success or error, exit 0
on success, 1 on a runtime/input error (unreadable or invalid align.json, an
alignment with no sentences/words, missing audio/model) and 2 on a usage
error (--align-json and --emit-transcript must be passed together). Progress
and latency diagnostics go to stderr.

Path configuration (CLI > env var > default):
    --audio / ALIGN_AUDIO       TTS-generated audio (required outside conversion)
    --text / ALIGN_TEXT         the source script text (or --text-file /
                                ALIGN_TEXT_FILE)
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

from transcript_schema import transcript_from_mlx_alignment
from utils import (
    ResourceMonitor,
    default_models_dir,
    log_latency,
    resolve_path,
    save_metrics,
)

# sentence-ending punctuation for Chinese/English scripts
_SENT_SPLIT = re.compile(r"(?<=[。！？!?；;])|\n+")


def transcript_from_alignment(align: dict) -> list[dict]:
    """Convert an alignment result to the pipeline transcript schema.

    ``align`` is the dict returned by :func:`align_text` (or a parsed
    align.json): ``words`` is the flat aligned token list (``word`` /
    ``start`` / ``end``, seconds) and ``sentences`` the punctuation-grouped
    sentence spans (``text`` / ``start`` / ``end``, seconds). Returns the
    transcript schema shared with transcribe.py — a list of
    ``{begin, end, text, words:[{text, begin, end}]}`` with ALL times in
    milliseconds.

    Thin adapter over transcript_schema.transcript_from_mlx_alignment, which
    owns the shared grouping walk. Raises ValueError when the alignment holds
    no sentences or no words — an empty transcript is never a valid pipeline
    product.
    """
    if not align.get("sentences") or not align.get("words"):
        raise ValueError("alignment has no sentences or no words")
    return transcript_from_mlx_alignment(align)


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


def group_sentences(words: list[dict], script_text: str) -> list[dict]:
    """Group aligned word spans into sentence spans using the script's punctuation.

    Each punctuated chunk of the script consumes aligned words until their
    combined length covers the chunk's alignable text, so every sentence span
    starts at its first word and ends at its last. Chunks with no alignable
    characters (pure punctuation) are skipped.
    """
    stripped = [s.strip() for s in _SENT_SPLIT.split(script_text)]
    stripped = [s for s in stripped if s]

    sentences = []
    pos = 0  # pointer into words
    for chunk in stripped:
        target = re.sub(r"[\s，,、.．:：\"'\"'()（）-]", "", chunk)
        if not target:
            continue
        if pos >= len(words):
            break
        # find the word span covering this chunk
        acc = ""
        start_word = pos
        while pos < len(words) and len(acc) < len(target):
            acc += words[pos]["word"]
            pos += 1
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


class JsonArgumentParser(argparse.ArgumentParser):
    """Usage errors still print one JSON document on stdout (exit 2)."""

    def error(self, message: str) -> None:
        print(json.dumps({"success": False, "error": message}, ensure_ascii=False))
        raise SystemExit(2)


def parse_args() -> argparse.Namespace:
    p = JsonArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--audio", default=None,
                   help="TTS audio to align (required unless the --align-json "
                        "conversion mode is used; or set ALIGN_AUDIO)")
    p.add_argument("--text", default=None,
                   help="source script text (or --text-file / ALIGN_TEXT_FILE, "
                        "or set ALIGN_TEXT)")
    p.add_argument("--text-file", default=None,
                   help="file containing the source script text (or set "
                        "ALIGN_TEXT_FILE)")
    p.add_argument("--language", default=None,
                   help="aligner language name (default: ALIGN_LANGUAGE or Chinese)")
    p.add_argument("--model", default=None,
                   help="aligner model dir or HF id (default: ALIGNER_MODEL or "
                        "<repo>/models/Qwen3-ForcedAligner-0.6B-8bit)")
    p.add_argument("--output", default=None,
                   help="output path without extension (default: ALIGN_OUTPUT_BASE "
                        "or the audio's own path)")
    p.add_argument("--metrics", default=None,
                   help="metrics JSON path (default: ALIGN_METRICS_FILE or "
                        "<output>.align_metrics.json)")
    p.add_argument("--align-json", default=None,
                   help="conversion mode: read this align.json instead of "
                        "running the aligner (no model load)")
    p.add_argument("--emit-transcript", default=None,
                   help="conversion mode: write the pipeline transcript schema "
                        "(milliseconds) to this path")
    return p.parse_args()


def _print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def convert_align_json(align_json_path: str, transcript_path: str) -> int:
    """Pure align.json -> transcript.json conversion (no model, no audio).

    Prints one JSON result to stdout; returns the process exit code.
    """
    src = Path(align_json_path)
    try:
        payload = json.loads(src.read_text(encoding="utf-8"))
    except FileNotFoundError:
        _print_json({"success": False, "error": f"align.json not found: {src}"})
        return 1
    except OSError as exc:
        _print_json({"success": False,
                     "error": f"cannot read align.json: {exc}"})
        return 1
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        _print_json({"success": False, "error": f"invalid align.json: {exc}"})
        return 1
    if not isinstance(payload, dict):
        _print_json({"success": False,
                     "error": "align.json root is not an object"})
        return 1
    try:
        transcript = transcript_from_alignment(payload)
    except (ValueError, KeyError, TypeError) as exc:
        _print_json({"success": False, "error": str(exc)})
        return 1
    out = Path(transcript_path)
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        _print_json({"success": False,
                     "error": f"cannot write transcript: {exc}"})
        return 1
    _print_json({
        "success": True,
        "output_path": str(out.resolve()),
        "sentence_count": len(transcript),
        "word_count": sum(len(s["words"]) for s in transcript),
    })
    return 0


def _run_conversion(args: argparse.Namespace) -> int:
    """--align-json / --emit-transcript: usage error -> exit 2, else convert."""
    if not (args.align_json and args.emit_transcript):
        _print_json({
            "success": False,
            "error": "--align-json and --emit-transcript must be passed together",
        })
        return 2
    return convert_align_json(args.align_json, args.emit_transcript)


def _align_language(args: argparse.Namespace) -> str:
    return args.language or os.environ.get("ALIGN_LANGUAGE") or "Chinese"


def _resolve_text(args: argparse.Namespace) -> str:
    """CLI --text > ALIGN_TEXT > --text-file / ALIGN_TEXT_FILE."""
    text = args.text or os.environ.get("ALIGN_TEXT")
    if text is None:
        text_file = args.text_file or os.environ.get("ALIGN_TEXT_FILE")
        if text_file:
            text = Path(
                resolve_path(text_file, "ALIGN_TEXT_FILE", Path.cwd())
            ).read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(
            "no text: pass --text / --text-file, or set ALIGN_TEXT / ALIGN_TEXT_FILE"
        )
    return text


def run_alignment(args: argparse.Namespace) -> int:
    """Align audio + script, write align.json/srt/metrics, print one JSON."""
    if not args.audio and not os.environ.get("ALIGN_AUDIO"):
        raise ValueError("no audio: pass --audio (or set ALIGN_AUDIO)")
    audio_path = resolve_path(args.audio, "ALIGN_AUDIO", Path.cwd())
    model_path = resolve_path(args.model, "ALIGNER_MODEL",
                              default_models_dir() / "Qwen3-ForcedAligner-0.6B-8bit")
    language = _align_language(args)
    text = _resolve_text(args)

    if not audio_path.exists():
        raise FileNotFoundError(f"audio not found: {audio_path}")
    if not model_path.exists():
        raise FileNotFoundError(f"model not found: {model_path}")

    out_base = resolve_path(args.output, "ALIGN_OUTPUT_BASE", audio_path.with_suffix(""))
    metrics_path = resolve_path(args.metrics, "ALIGN_METRICS_FILE",
                                Path(str(out_base) + ".align_metrics.json"))

    print(f"audio    : {audio_path}", file=sys.stderr)
    print(f"text     : {text[:60]}{'...' if len(text) > 60 else ''}", file=sys.stderr)
    print(f"language : {language}", file=sys.stderr)

    monitor = ResourceMonitor(sample_interval=0.5)
    monitor.start()
    t_align = time.perf_counter()
    result = align_text(audio_path, text, model_path=model_path, language=language)
    log_latency("align", t_align)
    monitor.stop()

    words, sentences, elapsed = result["words"], result["sentences"], result["align_s"]

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

    _print_json({
        "success": True,
        "audio": str(audio_path),
        "align_json": str(json_path.resolve()),
        "srt": str(srt_path.resolve()),
        "metrics": str(metrics_path.resolve()),
        "word_count": len(words),
        "sentence_count": len(sentences),
        "align_s": elapsed,
    })
    return 0


def main() -> int:
    """Entry point: stdout carries exactly one JSON document, in every mode."""
    try:
        args = parse_args()
        if args.align_json or args.emit_transcript:
            return _run_conversion(args)
        return run_alignment(args)
    except Exception as exc:  # noqa: BLE001 - failures end with one JSON error
        _print_json({"success": False, "error": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
