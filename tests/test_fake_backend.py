"""Tests for the helpers behind the test-only fake TTS / ASR backends."""
from __future__ import annotations

import pytest

import fake_backend


@pytest.mark.parametrize('text, duration', [
    pytest.param('你好', 1.0, id='one-second-floor'),
    pytest.param('大' * 15, 2.0, id='two-seconds'),
    pytest.param('大' * 75, 10.0, id='ten-seconds'),
    pytest.param(' 大 \n' * 15, 2.0, id='whitespace'),
    pytest.param('大，' * 15, 4.0, id='punctuation'),
])
def test_duration_uses_non_whitespace_characters_with_a_one_second_floor(text, duration):
    assert fake_backend.synthetic_duration_s(text) == pytest.approx(duration)


def test_uniform_transcript_spreads_one_word_per_non_whitespace_character():
    transcript = fake_backend.uniform_transcript('你好。再见。', 3.0)

    assert transcript == [
        {
            'begin': 0,
            'end': 1000,  # a sentence closes on its last letter token
            'text': '你好。',
            'words': [
                {'text': '你', 'begin': 0, 'end': 500},
                {'text': '好', 'begin': 500, 'end': 1000},
                {'text': '。', 'begin': 1000, 'end': 1500},
            ],
        },
        {
            'begin': 1500,
            'end': 3000,
            'text': '再见。',
            'words': [
                {'text': '再', 'begin': 1500, 'end': 2000},
                {'text': '见', 'begin': 2000, 'end': 2500},
                {'text': '。', 'begin': 2500, 'end': 3000},
            ],
        },
    ]


def test_uniform_transcript_of_whitespace_only_text_is_an_error():
    with pytest.raises(ValueError, match='no alignable text'):
        fake_backend.uniform_transcript(' \n ', 2.0)
