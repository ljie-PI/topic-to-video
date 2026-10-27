"""Tests for the mlx alignment -> pipeline transcript schema adapter.

The adapter is a pure library function: the mlx aligner's seconds-based spans
become sentence and word timestamps in integer milliseconds, with no audio,
model, JSON file handling, or CLI involved.
"""
from __future__ import annotations

from types import SimpleNamespace

from transcript_schema import (
    build_transcript,
    sentence_texts,
    transcript_from_mlx_alignment,
    transcript_from_torch_alignment,
)

ALIGN_JSON = {
    'audio': 'narration.wav',
    'language': 'Chinese',
    'words': [
        {'word': '大', 'start': 0.0, 'end': 0.326},
        {'word': '家', 'start': 0.326, 'end': 0.6},
        {'word': '好', 'start': 0.6, 'end': 0.9},
        {'word': '今', 'start': 1.2, 'end': 1.5},
        {'word': '天', 'start': 1.5, 'end': 1.834},
    ],
    'sentences': [
        {'text': '大家好。', 'start': 0.0, 'end': 0.9},
        {'text': '今天。', 'start': 1.2, 'end': 1.834},
    ],
}

EXPECTED_TRANSCRIPT = [
    {
        'begin': 0,
        'end': 900,
        'text': '大家好。',
        'words': [
            {'text': '大', 'begin': 0, 'end': 326},
            {'text': '家', 'begin': 326, 'end': 600},
            {'text': '好', 'begin': 600, 'end': 900},
        ],
    },
    {
        'begin': 1200,
        'end': 1834,
        'text': '今天。',
        'words': [
            {'text': '今', 'begin': 1200, 'end': 1500},
            {'text': '天', 'begin': 1500, 'end': 1834},
        ],
    },
]


def test_convert_mlx_alignment_to_transcript():
    assert transcript_from_mlx_alignment(ALIGN_JSON) == EXPECTED_TRANSCRIPT


def test_word_timestamps_are_integer_milliseconds():
    transcript = transcript_from_mlx_alignment(ALIGN_JSON)

    for sentence in transcript:
        assert set(sentence) == {'begin', 'end', 'text', 'words'}
        for field in ('begin', 'end'):
            assert isinstance(sentence[field], int)
        for word in sentence['words']:
            assert set(word) == {'text', 'begin', 'end'}
            assert isinstance(word['begin'], int)
            assert isinstance(word['end'], int)


def test_empty_alignment_returns_empty_transcript():
    alignment = {'audio': 'x.wav', 'language': 'Chinese', 'words': [], 'sentences': []}

    assert transcript_from_mlx_alignment(alignment) == []


def test_missing_alignment_fields_return_empty_transcript():
    assert transcript_from_mlx_alignment({'audio': 'x.wav', 'language': 'Chinese'}) == []


def test_punctuation_only_targets_fall_back_to_one_sentence_without_losing_words():
    words = [
        {'text': 'Hello', 'begin': 0, 'end': 400},
        {'text': 'world', 'begin': 400, 'end': 800},
    ]

    assert build_transcript(words, [{'text': '!!!'}]) == [{
        'begin': 0,
        'end': 800,
        'text': 'Helloworld',
        'words': words,
    }]


def test_sentence_texts_preserves_decimal_points_and_drops_unalignable_text():
    assert sentence_texts('GPT 5.4 works!  ...\n下一章。') == [
        'GPT 5.4 works!', '下一章。'
    ]


def test_torch_adapter_uses_original_text_and_converts_seconds_to_milliseconds():
    items = [
        SimpleNamespace(text='你', start_time=0.0, end_time=0.25),
        SimpleNamespace(text='好', start_time=0.25, end_time=0.5),
    ]

    assert transcript_from_torch_alignment('你好。', items) == [{
        'begin': 0,
        'end': 500,
        'text': '你好。',
        'words': [
            {'text': '你', 'begin': 0, 'end': 250},
            {'text': '好', 'begin': 250, 'end': 500},
        ],
    }]
