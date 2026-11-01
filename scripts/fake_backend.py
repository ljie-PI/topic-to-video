"""TTS / ASR 模型的确定性替身（仅用于测试的后端）。

``voice-clone.py --backend fake`` 和 ``transcribe.py --backend fake`` 使用这些
辅助函数，使完整的合成 + 转写链路无需加载任何模型即可跑通。它们只能通过显式
指定 ``fake`` 触达（``--backend``、``TTS_BACKEND`` 或 ``ASR_BACKEND``）；自动
解析永远不会选中它们。

假的“对齐器”把每个非空白字符当作一个词，在音频时长上均匀铺开，然后按与真实
对齐器相同的 ``transcript_schema`` 规则把它们分组成句。
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import media
from transcript_schema import transcript_from_torch_alignment

# 合成的语速，以及保证极短文本不会被压成空的下限。
CHARS_PER_SECOND = 7.5
MIN_DURATION_S = 1.0


def alignable_chars(text: str) -> list[str]:
    """每个非空白字符（含标点）都算一个假词。"""
    return [ch for ch in text if not ch.isspace()]


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
    """``text`` 以均匀语速在 ``duration_s`` 内念完时对应的 transcript schema。"""
    chars = alignable_chars(text)
    if not chars:
        raise ValueError('no alignable text (only whitespace)')
    step = duration_s / len(chars)
    items = [
        SimpleNamespace(text=ch, start_time=index * step, end_time=(index + 1) * step)
        for index, ch in enumerate(chars)
    ]
    return transcript_from_torch_alignment(text, items)
