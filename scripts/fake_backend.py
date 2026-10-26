"""Deterministic stand-ins for the TTS / ASR models (test-only backends).

``voice-clone.py --backend fake`` and ``transcribe.py --backend fake`` use
these helpers so the full synthesis + transcript path runs without loading any
model. They are reachable ONLY by naming ``fake`` explicitly (``--backend``,
``TTS_BACKEND`` or ``ASR_BACKEND``); auto resolution never picks them.

The fake "aligner" treats every alignable character as one word — letters and
numbers only, punctuation dropped, mirroring ``transcript_schema.kept_chars``
and the real aligners' token cleaning — spreads the words evenly over the
audio duration, then groups them into sentences with the same
``transcript_schema`` rules as the real aligners.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import media
from transcript_schema import kept_chars, transcript_from_torch_alignment

# Synthetic speaking pace and the floor that keeps very short texts non-empty.
CHARS_PER_SECOND = 7.5
MIN_DURATION_S = 1.0


def alignable_chars(text: str) -> list[str]:
    """Every alignable character (letters/numbers, punctuation dropped) is one fake word."""
    return list(kept_chars(text))


def synthetic_duration_s(text: str) -> float:
    return max(MIN_DURATION_S, len(alignable_chars(text)) / CHARS_PER_SECOND)


def write_silent_mp3(path: Path, duration_s: float) -> None:
    media.run_ffmpeg(
        [
            '-y', '-loglevel', 'error',
            '-f', 'lavfi', '-i', 'anullsrc=r=24000:cl=mono',
            '-t', f'{duration_s:.3f}',
            '-c:a', 'libmp3lame', '-q:a', '2',
            path,
        ],
        timeout=60,
    )


def uniform_transcript(text: str, duration_s: float) -> list[dict]:
    """Transcript schema for ``text`` spoken at an even pace over ``duration_s``."""
    chars = alignable_chars(text)
    if not chars:
        raise ValueError('no alignable text (only whitespace)')
    step = duration_s / len(chars)
    items = [
        SimpleNamespace(text=ch, start_time=index * step, end_time=(index + 1) * step)
        for index, ch in enumerate(chars)
    ]
    return transcript_from_torch_alignment(text, items)
