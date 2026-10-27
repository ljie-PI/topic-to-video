#!/usr/bin/env python3
"""Shared derivation of a selected clip's silent-file path.

cut-clips.py writes the file and records ``clip_path``; pipeline-status.py
re-derives the same path to validate that ``clip_path`` names the file of the
clip's current window. One rule lives here so the two cannot drift.
"""
from __future__ import annotations

import math
from typing import Any

CLIPS_DIR = 'clips'


def clip_relpath(video_id: Any, start: Any, end: Any) -> str:
    """Return clips/<video_id>_<start:.2f>-<end:.2f>.mp4."""
    if not isinstance(video_id, str) or not video_id:
        raise ValueError('video has no id')
    if any(char in video_id for char in '/\\\0') or video_id.startswith('.'):
        raise ValueError(f'video id {video_id!r} cannot be used in a file name')
    try:
        start_f, end_f = float(start), float(end)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'clip window {start}-{end} must be numbers') from exc
    if not (math.isfinite(start_f) and math.isfinite(end_f)):
        raise ValueError(f'clip window {start}-{end} must be finite numbers')
    return f'{CLIPS_DIR}/{video_id}_{start_f:.2f}-{end_f:.2f}.mp4'
