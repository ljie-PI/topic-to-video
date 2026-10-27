"""Tests for the mlx alignment -> pipeline transcript schema adapter.

The adapter is a pure library function: the mlx aligner's seconds-based spans
become sentence and word timestamps in integer milliseconds, with no audio,
model, JSON file handling, or CLI involved.
"""
from __future__ import annotations

from transcript_schema import transcript_from_mlx_alignment

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
