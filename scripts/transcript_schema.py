"""流水线 transcript schema 的唯一构建器。

本仓库中每个 transcript 产出方都输出同一形状：一个句子列表，每个句子为
``{begin, end, text, words}``，每个词为 ``{text, begin, end}``，所有时间都是
整数毫秒。下游（``align-narration.py``）只依赖这一形状。

仓库里有两种对齐器：

* mlx-audio 的 Qwen3-ForcedAligner —— ``text_align.align_text`` 已把它的 item
  转成 ``{'word', 'start', 'end'}``（秒），以及按标点分组的句子区间
  ``{'text', 'start', 'end'}``；
* torch 的 Qwen3-ForcedAligner —— 一个扁平的 item 列表，带 ``text`` /
  ``start_time`` / ``end_time``（秒），并以原始的脚本原文（标点保留）作为句子
  边界的来源。

本模块持有那唯一的分组算法（以 token 为锚的“保留字符”配额，因此任何词的时间
都不会丢失或重复），以及两个薄适配器
:func:`transcript_from_mlx_alignment` / :func:`transcript_from_torch_alignment`，
供脚本直接调用。
"""

from __future__ import annotations

import re
import unicodedata

# 仍带标点的脚本所用的句末边界。
# CJK 结束符无条件切分；拉丁 .!? 仅在后跟空白或字符串结尾时切分，
# 因此 "GPT 5.4" / "v2.0" 不会在数字中间被切开。
SENTENCE_BOUNDARY = re.compile(r'(?<=[。！？…\n])|(?<=[.!?])(?=\s|$)')


def to_ms(seconds: float) -> int:
    """秒 -> 整数毫秒（schema 唯一的时间单位）。"""
    return int(round(float(seconds) * 1000.0))


def kept_chars(text: str) -> str:
    """只保留字母 / 数字，并转成小写。

    与强制对齐器的 token 清洗保持一致（它保留 Unicode 的 L/N 类别、丢弃标点与
    空白），因此一个句子的保留字符字符串等于其各对齐 token 的保留字符字符串的
    拼接。
    """
    return ''.join(
        ch.lower() for ch in text if unicodedata.category(ch)[0] in ('L', 'N')
    )


def sentence_texts(full_text: str) -> list[str]:
    """把带标点的脚本切成非空、可对齐的句子文本。"""
    texts = []
    for part in SENTENCE_BOUNDARY.split(full_text):
        sentence_text = part.strip()
        if sentence_text and kept_chars(sentence_text):
            texts.append(sentence_text)
    return texts


def _sentence(target: dict, group: list[dict]) -> dict:
    """生成一行 transcript 句子：时间优先取目标值，否则取词的时间。"""
    begin = target.get('begin')
    end = target.get('end')
    return {
        'begin': begin if begin is not None else group[0]['begin'],
        'end': end if end is not None else group[-1]['end'],
        'text': target['text'],
        'words': group,
    }


def _single_sentence(words: list[dict]) -> list[dict]:
    """脚本没有可用的句子边界时的兜底。"""
    return [
        {
            'begin': words[0]['begin'],
            'end': words[-1]['end'],
            'text': ''.join(word['text'] for word in words),
            'words': list(words),
        }
    ]


def build_transcript(words: list[dict], sentences: list[dict]) -> list[dict]:
    """把对齐后的词分组成流水线的 transcript schema。

    ``words`` 是 ``{'text', 'begin', 'end'}``（毫秒），已由对齐器清洗（CJK 单字
    或拉丁词 token，标点已去掉）。``sentences`` 是 ``{'text', ['begin', 'end']}``
    （毫秒）目标：句子文本加可选的时间。mlx 两者都提供；torch 适配器只提供文本，
    时间取自分组后的词。

    遍历是 *以 token 为锚* 的：每个词都恰好归入一个句子，因此任何词级时间都不会
    丢。某个词的保留字符超出当前句子配额时，它仍留在它补完的那个句子里，溢出量
    结转给后续句子以保持对齐。没有词时返回 ``[]``。
    """
    if not words:
        return []

    targets: list[dict] = []
    for sentence in sentences or []:
        keep_len = len(kept_chars(sentence.get('text') or ''))
        if keep_len == 0:
            continue
        targets.append(
            {
                'text': sentence['text'],
                'keep_len': keep_len,
                'begin': sentence.get('begin'),
                'end': sentence.get('end'),
            }
        )
    if not targets:
        return _single_sentence(words)

    transcript: list[dict] = []
    ti = 0
    group: list[dict] = []
    acc = 0  # 朝当前目标累计的保留字符（含结转）
    for word in words:
        if not kept_chars(word['text']) and not group and transcript:
            # 紧跟在上一句恰好收于前一个 token 之后的纯标点 token 属于该句：
            # 让它留在那里，而不要用它开启下一句。
            transcript[-1]['words'].append(word)
            continue
        group.append(word)
        acc += len(kept_chars(word['text']))
        # 配额满足后关闭当前句，并结转跨边界的 token 带来的溢出。``group`` 的
        # 判断避免在某个超大 token 一次满足两个配额时输出空句子。
        while ti < len(targets) - 1 and group and acc >= targets[ti]['keep_len']:
            acc -= targets[ti]['keep_len']
            transcript.append(_sentence(targets[ti], group))
            group = []
            ti += 1

    if group:
        target = targets[ti] if ti < len(targets) else {
            'text': ''.join(word['text'] for word in group)
        }
        transcript.append(_sentence(target, group))
    return transcript


# --- 面向两种对齐器输出的薄适配器 ---------------------------------------------


def transcript_from_mlx_alignment(alignment: dict) -> list[dict]:
    """适配器：mlx align_text 结果 / align.json -> transcript schema。

    ``alignment`` 含有 ``words``（``{'word', 'start', 'end'}``，秒）以及按标点
    分组的 ``sentences``（``{'text', 'start', 'end'}``，秒）。
    """
    words = [
        {'text': word['word'], 'begin': to_ms(word['start']), 'end': to_ms(word['end'])}
        for word in alignment.get('words') or []
    ]
    sentences = [
        {
            'text': sentence['text'],
            'begin': to_ms(sentence['start']),
            'end': to_ms(sentence['end']),
        }
        for sentence in alignment.get('sentences') or []
    ]
    return build_transcript(words, sentences)


def transcript_from_torch_alignment(full_text: str, items: list) -> list[dict]:
    """适配器：torch 强制对齐器的 items + 原文 -> transcript schema。

    ``items`` 是带 ``text`` / ``start_time`` / ``end_time``（秒）的对齐器对象，
    每个 CJK 字符或拉丁词一项，标点已去掉。
    """
    words = [
        {
            'text': item.text,
            'begin': to_ms(item.start_time),
            'end': to_ms(item.end_time),
        }
        for item in items
    ]
    sentences = [{'text': text} for text in sentence_texts(full_text)]
    return build_transcript(words, sentences)
