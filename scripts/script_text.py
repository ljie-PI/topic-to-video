"""展示稿（script.txt）的段落与字符计数规则。

align-narration（段落时间轴）、pipeline-status（字数与 scene-plan 覆盖检查）
以及写脚本的 agent 自己的规则共用这一份定义，因此不会各自漂移。段落是一组连续
的非空行；空行或只含空白的行用于分隔段落。
"""
from __future__ import annotations


def paragraph_spans(text: str) -> list[tuple[int, int]]:
    """把非空行分组表示为 [(start, end)] 形式的字符区间。

    ``end`` 指向结束段落最后一行换行符之后一位；最后一行没有换行符时，它就是
    ``len(text)`` 之后一位。
    """
    spans: list[tuple[int, int]] = []
    position = 0
    start: int | None = None
    for line in text.split('\n') + ['']:
        if line.strip():
            if start is None:
                start = position
        elif start is not None:
            spans.append((start, position))
            start = None
        position += len(line) + 1
    return spans


def paragraphs(text: str) -> list[str]:
    """按顺序返回各段落：其各行用换行符连接，并去掉行尾空白。"""
    return [text[start:end].rstrip() for start, end in paragraph_spans(text)]


def count_chars(text: str) -> int:
    """``text`` 中的字符数，统计前先去掉所有空白字符（包括 U+3000）。"""
    return sum(1 for char in text if not char.isspace())
