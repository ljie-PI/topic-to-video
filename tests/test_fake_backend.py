"""Tests for the helpers behind the test-only fake TTS / ASR backends."""
from __future__ import annotations

import pytest

import fake_backend


def test_duration_follows_a_7_5_characters_per_second_pace_with_a_one_second_floor():
    assert fake_backend.synthetic_duration_s('你好') == 1.0  # floor
    assert fake_backend.synthetic_duration_s('大' * 15) == pytest.approx(2.0)
    assert fake_backend.synthetic_duration_s('大' * 75) == pytest.approx(10.0)


def test_whitespace_does_not_count_towards_the_duration():
    assert fake_backend.synthetic_duration_s(' 大 \n' * 15) == pytest.approx(2.0)


def test_uniform_transcript_spreads_one_word_per_character_over_the_duration():
    # Punctuation is dropped from the word tokens, exactly like the real
    # aligners' token cleaning (transcript_schema.kept_chars): a sentence ends
    # at its last letter token, never earlier.
    transcript = fake_backend.uniform_transcript('你好。再见。', 3.0)

    assert transcript == [
        {
            'begin': 0,
            'end': 1500,
            'text': '你好。',
            'words': [
                {'text': '你', 'begin': 0, 'end': 750},
                {'text': '好', 'begin': 750, 'end': 1500},
            ],
        },
        {
            'begin': 1500,
            'end': 3000,
            'text': '再见。',
            'words': [
                {'text': '再', 'begin': 1500, 'end': 2250},
                {'text': '见', 'begin': 2250, 'end': 3000},
            ],
        },
    ]


def test_uniform_transcript_of_whitespace_only_text_is_an_error():
    with pytest.raises(ValueError, match='no alignable text'):
        fake_backend.uniform_transcript(' \n ', 2.0)
