#!/usr/bin/env python3
"""把旁白脚本强制对齐到其 TTS 音频（mlx-audio）。

voice-clone.py 中 mlx 直接对齐路径的 ``align_text`` / ``group_sentences`` 库
所在地。mlx 模型仍在 align_text 内部才惰性导入，因此导入本模块开销很小。
text_align.py 为兼容库调用方转出 align_text。
"""
from __future__ import annotations

import re
import time
from pathlib import Path

# 用于中英文脚本的句子结束标点
_SENT_SPLIT = re.compile(r"(?<=[。！？!?；;])|\n+")


def align_text(
    audio_path: str | Path,
    text: str,
    *,
    model_path: str | Path | None = None,
    language: str = "Chinese",
    load_model_fn=None,
) -> dict:  # pragma: no cover - 需要受支持硬件上有真实的 mlx-audio 对齐器。
    """把 `text` 对齐到 `audio_path`，返回词级 / 句级时间戳。

    返回 {"words": [...], "sentences": [...], "align_s": float}。
    `load_model_fn` 让调用方复用已经加载好的对齐模型。
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
    """用脚本自带的标点，把对齐后的词区间分组成句区间。

    脚本中每个带标点的片段会依次吃掉对齐词，直到这些词的总长度覆盖该片段里可
    对齐的文本，因此每个句区间都从它的第一个词开始、到最后一个词结束。没有可
    对齐字符的片段（纯标点）会被跳过。
    """
    stripped = [s.strip() for s in _SENT_SPLIT.split(script_text)]
    stripped = [s for s in stripped if s]

    sentences = []
    pos = 0  # words 中的指针
    for chunk in stripped:
        target = re.sub(r"[\s，,、.．:：\"'\"'()（）-]", "", chunk)
        if not target:
            continue
        if pos >= len(words):
            break
        # 找出覆盖该片段的词区间
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
