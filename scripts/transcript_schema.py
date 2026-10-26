"""Single builder for the pipeline transcript schema.

Every transcript producer in this repo emits the same shape: a sentence list,
each sentence ``{begin, end, text, words}`` and each word
``{text, begin, end}``, ALL times in integer MILLISECONDS. Downstream
(``align-narration.py``) depends on that shape only.

The repo has two aligner flavours:

* mlx-audio's Qwen3-ForcedAligner — ``text_align.align_text`` already turns its
  items into ``{'word', 'start', 'end'}`` (seconds) plus punctuation-grouped
  sentence spans ``{'text', 'start', 'end'}``;
* the torch Qwen3-ForcedAligner — a flat item list with ``text`` /
  ``start_time`` / ``end_time`` (seconds) and the ORIGINAL script text
  (punctuation intact) as the source of sentence boundaries.

This module owns the one grouping algorithm (token-anchored kept-character
quotas, so no word timing is ever dropped or duplicated) and the two thin
adapters :func:`transcript_from_mlx_alignment` /
:func:`transcript_from_torch_alignment`, which the scripts call directly.
"""

from __future__ import annotations

import re
import unicodedata

# Sentence-final boundaries for scripts that still carry punctuation.
# CJK enders split unconditionally; Latin .!? split only when followed by
# whitespace or end-of-string so "GPT 5.4" / "v2.0" are not split mid-number.
SENTENCE_BOUNDARY = re.compile(r'(?<=[。！？…\n])|(?<=[.!?])(?=\s|$)')


def to_ms(seconds: float) -> int:
    """Seconds -> integer milliseconds (the schema's only time unit)."""
    return int(round(float(seconds) * 1000.0))


def kept_chars(text: str) -> str:
    """Letters/numbers only, lowercased.

    Mirrors the forced aligner's token cleaning (it keeps Unicode L/N
    categories and drops punctuation/space), so a sentence's kept-char string
    equals the concatenation of its aligned tokens' kept-char strings.
    """
    return ''.join(
        ch.lower() for ch in text if unicodedata.category(ch)[0] in ('L', 'N')
    )


def sentence_texts(full_text: str) -> list[str]:
    """Split a punctuated script into non-empty, alignable sentence texts."""
    texts = []
    for part in SENTENCE_BOUNDARY.split(full_text):
        sentence_text = part.strip()
        if sentence_text and kept_chars(sentence_text):
            texts.append(sentence_text)
    return texts


def _sentence(target: dict, group: list[dict]) -> dict:
    """One transcript sentence: timing pref from the target, else from words."""
    begin = target.get('begin')
    end = target.get('end')
    return {
        'begin': begin if begin is not None else group[0]['begin'],
        'end': end if end is not None else group[-1]['end'],
        'text': target['text'],
        'words': group,
    }


def _single_sentence(words: list[dict]) -> list[dict]:
    """Fallback when the script has no usable sentence boundary."""
    return [
        {
            'begin': words[0]['begin'],
            'end': words[-1]['end'],
            'text': ''.join(word['text'] for word in words),
            'words': list(words),
        }
    ]


def build_transcript(words: list[dict], sentences: list[dict]) -> list[dict]:
    """Group aligned words into the pipeline transcript schema.

    ``words`` are ``{'text', 'begin', 'end'}`` (ms), already cleaned by the
    aligner (CJK character or Latin word tokens, punctuation stripped).
    ``sentences`` are ``{'text', ['begin', 'end']}`` (ms) targets: the sentence
    text plus optional timing. mlx supplies both; the torch adapter supplies
    text only and timing is taken from the grouped words.

    The walk is *token-anchored*: every word is assigned to exactly one
    sentence, so no word-level timing is ever dropped. A word whose kept chars
    overshoot the current sentence quota stays in the sentence it completes,
    and the overflow is carried so subsequent sentences stay aligned.
    Returns ``[]`` when there are no words.
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
    acc = 0  # kept chars accumulated toward the current target (incl. carry)
    for word in words:
        if not kept_chars(word['text']) and not group and transcript:
            # A punctuation-only token right after a sentence closed on the
            # exact previous token punctuates that sentence; keep it there
            # instead of opening the next one with it.
            transcript[-1]['words'].append(word)
            continue
        group.append(word)
        acc += len(kept_chars(word['text']))
        # Close the current sentence once its quota is met, carrying overflow
        # from a boundary-spanning token. The ``group`` guard prevents emitting
        # an empty sentence when one oversized token satisfies two quotas.
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


# --- thin adapters for the two aligner outputs ---------------------------------


def transcript_from_mlx_alignment(alignment: dict) -> list[dict]:
    """Adapter: mlx align_text result / align.json -> transcript schema.

    ``alignment`` holds ``words`` (``{'word', 'start', 'end'}``, seconds) and
    punctuation-grouped ``sentences`` (``{'text', 'start', 'end'}``, seconds).
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
    """Adapter: torch forced-aligner items + original text -> transcript schema.

    ``items`` are aligner objects with ``text`` / ``start_time`` / ``end_time``
    in seconds, one per CJK character or Latin word, punctuation stripped.
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
