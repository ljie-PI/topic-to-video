#!/usr/bin/env python3
"""Shared derivation of a selected clip's silent-file path.

cut-clips.py writes the file and records ``clip_path``; pipeline-status.py
re-derives the same path to validate that ``clip_path`` names the file of the
clip's current window. One rule lives here so the two cannot drift.

The path is namespaced by the catalog entry's slug because a video id is only
unique per entry (harvest-pages names every page's native video native_001,
so two entries can both hold a ``native_001``), and the window keeps
millisecond precision so a sub-centisecond edit cannot collide with the
previous file and silently reuse it.
"""
from __future__ import annotations

import math
import re
from typing import Any

CLIPS_DIR = 'clips'

_SAFE = re.compile(r'[^\w-]+')


def _safe_part(value: Any, what: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f'{what} must be a non-empty string')
    if what == 'video id' and (any(char in value for char in '/\\\0') or value.startswith('.')):
        raise ValueError(f'video id {value!r} cannot be used in a file name')
    return _SAFE.sub('_', value)


def clip_relpath(slug: Any, video_id: Any, start: Any, end: Any) -> str:
    """The workspace-relative silent file for one selected clip."""
    safe_slug = _safe_part(slug, 'entry slug') if isinstance(slug, str) and slug else 'entry'
    safe_id = _safe_part(video_id, 'video id')
    try:
        start_f, end_f = float(start), float(end)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'clip window {start}-{end} must be numbers') from exc
    if not (math.isfinite(start_f) and math.isfinite(end_f)):
        raise ValueError(f'clip window {start}-{end} must be finite numbers')
    start_s, end_s = f'{start_f:.3f}', f'{end_f:.3f}'
    return f'{CLIPS_DIR}/{safe_slug}/{safe_id}_{start_s}-{end_s}.mp4'
