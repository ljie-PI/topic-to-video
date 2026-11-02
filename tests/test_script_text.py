"""Direct-import tests for scripts/script_text.py.

A paragraph is a run of consecutive non-blank lines; blank (or whitespace-only)
lines separate paragraphs. The expected spans and texts below are worked out by
hand from that rule.
"""
from __future__ import annotations

import pytest

import script_text


@pytest.mark.parametrize('text, expected', [
    pytest.param('a\nb\n\nc\n', [(0, 4), (5, 7)], id='two-paragraphs'),
    pytest.param('\n\nab\n\n\n', [(2, 5)], id='edge-blank-lines'),
    pytest.param('a\n \t\n　\nb', [(0, 2), (7, 9)], id='whitespace-separators'),
    pytest.param('a\n\n\n\nb\n', [(0, 2), (5, 7)], id='multiple-separators'),
    pytest.param('只有一段\n第二行', [(0, 9)], id='no-final-newline'),
    pytest.param('', [], id='empty'),
    pytest.param('\n \n', [], id='blank'),
])
def test_paragraph_spans(text, expected):
    assert script_text.paragraph_spans(text) == expected


@pytest.mark.parametrize('text, expected', [
    pytest.param('第一行\n第二行\n\n\n第三段  \n', ['第一行\n第二行', '第三段'], id='joined-lines'),
    pytest.param('　　开头缩进\n\nb', ['　　开头缩进', 'b'], id='leading-indentation'),
    pytest.param('', [], id='empty'),
])
def test_paragraphs(text, expected):
    assert script_text.paragraphs(text) == expected


@pytest.mark.parametrize('text, expected', [
    pytest.param('一 二\t三\n四\r五　六', 6, id='whitespace'),
    pytest.param('Hi, 你好。', 6, id='punctuation-and-latin'),
    pytest.param('', 0, id='empty'),
    pytest.param(' \n　', 0, id='blank'),
])
def test_count_chars(text, expected):
    assert script_text.count_chars(text) == expected
