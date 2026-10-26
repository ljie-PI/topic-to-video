"""Direct-import tests for scripts/script_text.py.

A paragraph is a run of consecutive non-blank lines; blank (or whitespace-only)
lines separate paragraphs. The expected spans and texts below are worked out by
hand from that rule.
"""
from __future__ import annotations

import script_text


def test_paragraph_spans_of_two_paragraphs():
    # 'a\nb' = 0..3, '\n' separator line at 4, 'c' = 5.. ; each span ends just
    # past the newline of its last line.
    assert script_text.paragraph_spans('a\nb\n\nc\n') == [(0, 4), (5, 7)]


def test_paragraph_spans_ignore_leading_and_trailing_blank_lines():
    assert script_text.paragraph_spans('\n\nab\n\n\n') == [(2, 5)]


def test_paragraph_spans_treat_space_only_lines_as_blank():
    assert script_text.paragraph_spans('a\n \t\n　\nb') == [(0, 2), (7, 9)]


def test_paragraph_spans_collapse_multiple_blank_lines():
    assert script_text.paragraph_spans('a\n\n\n\nb\n') == [(0, 2), (5, 7)]


def test_paragraph_spans_single_paragraph():
    # The last line has no newline; its span still counts one separator
    # character, so the end is one past len(text) (8).
    assert script_text.paragraph_spans('只有一段\n第二行') == [(0, 9)]


def test_paragraph_spans_of_empty_and_blank_text():
    assert script_text.paragraph_spans('') == []
    assert script_text.paragraph_spans('\n \n') == []


def test_paragraphs_join_lines_and_drop_trailing_whitespace():
    assert script_text.paragraphs('第一行\n第二行\n\n\n第三段  \n') == ['第一行\n第二行', '第三段']


def test_paragraphs_keep_leading_indentation():
    assert script_text.paragraphs('　　开头缩进\n\nb') == ['　　开头缩进', 'b']


def test_paragraphs_of_empty_text():
    assert script_text.paragraphs('') == []


def test_count_chars_ignores_every_kind_of_whitespace():
    # ASCII space, tab, newline, carriage return and the full-width space U+3000.
    assert script_text.count_chars('一 二\t三\n四\r五　六') == 6


def test_count_chars_counts_punctuation_and_latin():
    assert script_text.count_chars('Hi, 你好。') == 6


def test_count_chars_of_empty_text():
    assert script_text.count_chars('') == 0
    assert script_text.count_chars(' \n　') == 0
