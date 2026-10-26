"""Paragraph and character counting rules for the display draft (script.txt).

One definition shared by align-narration (paragraph timeline), pipeline-status
(word-count and scene-plan coverage checks), and the script agent's own rules,
so they cannot drift apart. A paragraph is a run of consecutive non-blank
lines; blank or whitespace-only lines separate paragraphs.
"""
from __future__ import annotations


def paragraph_spans(text: str) -> list[tuple[int, int]]:
    """Non-blank line groups as [(start, end)] character spans.

    ``end`` is one past the newline that closes the paragraph's last line, so
    for a last line without a newline it is one past ``len(text)``.
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
    """The paragraphs in order: their lines joined by newlines, trailing whitespace removed."""
    return [text[start:end].rstrip() for start, end in paragraph_spans(text)]


def count_chars(text: str) -> int:
    """Characters in ``text`` once every whitespace character (including U+3000) is dropped."""
    return sum(1 for char in text if not char.isspace())
