#!/usr/bin/env python3
"""共享的“选中片段静音文件”路径推导。

cut-clips.py 负责写出该文件并记录 ``clip_path``；pipeline-status.py 用同一套
规则重新推导路径，以校验 ``clip_path`` 是否指向该片段当前时间窗对应的文件。
规则只在这里写一份，两边就不会各自漂移。
"""
from __future__ import annotations

import math
from typing import Any

CLIPS_DIR = 'clips'


def clip_relpath(video_id: Any, start: Any, end: Any) -> str:
    """返回 clips/<video_id>_<start:.2f>-<end:.2f>.mp4。"""
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
