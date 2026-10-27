#!/usr/bin/env python3
"""Forced alignment of a narration script to its TTS audio (mlx-audio).

Library home of ``align_text`` / ``group_sentences``: the mlx direct-alignment
path in voice-clone.py imports these helpers from here so that no pipeline
script imports from the text_align.py CLI (issue #105). The mlx model import
stays lazy inside align_text, so importing this module is cheap.

The text_align.py CLI wraps this for interactive use and its align.json ->
transcript.json conversion mode.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

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
