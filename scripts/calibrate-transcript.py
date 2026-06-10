#!/usr/bin/env python3
"""Build transcript-timed subtitle units with narration-based Latin corrections.

Usage:
  python3 scripts/calibrate-transcript.py \
    --narration narration.txt \
    --transcript transcribe/transcript.json \
    --output transcribe/subtitle-units.json
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from typing import Any


TOOL_NAME = 'calibrate-transcript'
LATIN_SPAN_RE = re.compile(r'[A-Za-z][A-Za-z0-9+._/-]*(?:\s+[A-Za-z][A-Za-z0-9+._/-]*)*')
SOFT_BREAK_CHARS = set('，,；;、')
HARD_BREAK_CHARS = set('。.!！？?')
CHINESE_DIGITS = {
    '零': 0,
    '〇': 0,
    '一': 1,
    '二': 2,
    '两': 2,
    '三': 3,
    '四': 4,
    '五': 5,
    '六': 6,
    '七': 7,
    '八': 8,
    '九': 9,
}
CHINESE_SMALL_UNITS = {'十': 10, '百': 100, '千': 1000}
CHINESE_BIG_UNITS = {'万': 10000, '亿': 100000000}
CHINESE_NUMBER_CHARS = set(CHINESE_DIGITS) | set(CHINESE_SMALL_UNITS) | set(CHINESE_BIG_UNITS)


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        log(f'bad arguments: {message}')
        print_json({'success': False, 'error': message})
        raise SystemExit(2)


@dataclass
class Word:
    text: str
    begin: int
    end: int


@dataclass
class Unit:
    text: str
    begin_ms: int
    end_ms: int
    words: list[Word]


@dataclass
class Match:
    start: int
    end: int
    confidence: float
    text: str


def log(message: str) -> None:
    print(f'[{TOOL_NAME}] {message}', file=sys.stderr)


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def parse_args() -> argparse.Namespace:
    parser = JsonArgumentParser(
        description='Create transcript-timed subtitle units with narration-based Latin corrections.'
    )
    parser.add_argument('--narration', required=True, help='Path to narration.txt')
    parser.add_argument('--transcript', required=True, help='Path to transcribe/transcript.json')
    parser.add_argument('--output', required=True, help='Output path for subtitle-units.json')
    parser.add_argument(
        '--max-chars',
        type=int,
        default=28,
        help='Conservative max display characters before splitting a subtitle unit.',
    )
    parser.add_argument(
        '--min-confidence',
        type=float,
        default=0.65,
        help='Minimum fuzzy match confidence for using narration as correction source.',
    )
    return parser.parse_args()


def read_text(path: str) -> str:
    with open(path, encoding='utf-8') as file:
        return file.read().replace('\r\n', '\n').replace('\r', '\n').strip()


def as_int_ms(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{label} is not a numeric timestamp: {value!r}')
    return int(round(value))


def load_transcript(path: str) -> list[dict[str, Any]]:
    with open(path, encoding='utf-8') as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError('transcript root must be a list of sentence objects')

    sentences: list[dict[str, Any]] = []
    for sentence_index, sentence in enumerate(data, start=1):
        if not isinstance(sentence, dict):
            raise ValueError(f'transcript sentence {sentence_index} is not an object')
        raw_words = sentence.get('words')
        if not isinstance(raw_words, list) or not raw_words:
            raise ValueError(f'transcript sentence {sentence_index} has no word timestamps')

        words: list[Word] = []
        for word_index, raw_word in enumerate(raw_words, start=1):
            if not isinstance(raw_word, dict):
                raise ValueError(f'sentence {sentence_index} word {word_index} is not an object')
            text = str(raw_word.get('text') or '').strip()
            if not text:
                continue
            begin = as_int_ms(raw_word.get('begin'), f'sentence {sentence_index} word {word_index}.begin')
            end = as_int_ms(raw_word.get('end'), f'sentence {sentence_index} word {word_index}.end')
            if end < begin:
                raise ValueError(f'sentence {sentence_index} word {word_index} has end before begin')
            words.append(Word(text=text, begin=begin, end=end))

        if not words:
            raise ValueError(f'transcript sentence {sentence_index} has no non-empty words')

        text = str(sentence.get('text') or ''.join(word.text for word in words)).strip()
        sentences.append({'text': text, 'words': words})

    return sentences


def display_len(text: str) -> int:
    return len(''.join(ch for ch in text if not ch.isspace()))


def words_to_text(words: list[Word]) -> str:
    return ''.join(word.text for word in words).strip()


def chunk_long_word(word: Word, max_chars: int) -> list[Word]:
    if display_len(word.text) <= max_chars:
        return [word]

    chars = list(word.text)
    chunks = [''.join(chars[index:index + max_chars]) for index in range(0, len(chars), max_chars)]
    duration = max(1, word.end - word.begin)
    out: list[Word] = []
    for index, chunk in enumerate(chunks):
        begin = word.begin + round(duration * index / len(chunks))
        end = word.begin + round(duration * (index + 1) / len(chunks))
        out.append(Word(text=chunk, begin=begin, end=end))
    return out


def expand_long_words(words: list[Word], max_chars: int) -> list[Word]:
    expanded: list[Word] = []
    for word in words:
        expanded.extend(chunk_long_word(word, max_chars))
    return expanded


def build_unit(words: list[Word], text: str | None = None) -> Unit:
    if not words:
        raise ValueError('cannot build unit from empty word list')
    return Unit(
        text=(text if text is not None else words_to_text(words)).strip(),
        begin_ms=words[0].begin,
        end_ms=words[-1].end,
        words=words,
    )


def split_large_segment(words: list[Word], max_chars: int) -> list[list[Word]]:
    chunks: list[list[Word]] = []
    current: list[Word] = []
    for word in words:
        if current and display_len(words_to_text(current + [word])) > max_chars:
            chunks.append(current)
            current = []
        current.append(word)
        if display_len(words_to_text(current)) >= max_chars:
            chunks.append(current)
            current = []
    if current:
        chunks.append(current)
    return chunks


def split_sentence(sentence: dict[str, Any], max_chars: int) -> list[Unit]:
    text = str(sentence['text']).strip()
    words = expand_long_words(sentence['words'], max_chars)
    if display_len(text) <= max_chars:
        return [build_unit(words, text)]

    segments: list[list[Word]] = []
    current: list[Word] = []
    for word in words:
        current.append(word)
        current_text = words_to_text(current)
        if (
            current_text
            and any(ch in SOFT_BREAK_CHARS or ch in HARD_BREAK_CHARS for ch in word.text)
            and display_len(current_text) >= max(8, max_chars // 2)
        ):
            segments.append(current)
            current = []
    if current:
        segments.append(current)

    units: list[Unit] = []
    for segment in segments:
        if display_len(words_to_text(segment)) <= max_chars:
            units.append(build_unit(segment))
        else:
            units.extend(build_unit(chunk) for chunk in split_large_segment(segment, max_chars))
    return units


def is_cjk(char: str) -> bool:
    return (
        '\u3400' <= char <= '\u4dbf'
        or '\u4e00' <= char <= '\u9fff'
        or '\uf900' <= char <= '\ufaff'
    )


def char_weight(char: str) -> float:
    if is_cjk(char):
        return 3.0
    if char.isdigit():
        return 2.0
    return 1.0


def text_weight(text: str) -> float:
    return sum(char_weight(char) for char in text)


def weighted_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    matcher = difflib.SequenceMatcher(None, left, right, autojunk=False)
    matched_weight = 0.0
    for block in matcher.get_matching_blocks():
        if block.size:
            matched_weight += text_weight(left[block.a:block.a + block.size])
    total_weight = text_weight(left) + text_weight(right)
    if total_weight == 0:
        return 0.0
    return (2 * matched_weight) / total_weight


def parse_chinese_number(text: str) -> int | None:
    if not text:
        return None
    if all(char in CHINESE_DIGITS for char in text):
        if len(text) == 1:
            return None
        return int(''.join(str(CHINESE_DIGITS[char]) for char in text))

    total = 0
    section = 0
    number = 0
    seen = False
    for char in text:
        if char in CHINESE_DIGITS:
            number = CHINESE_DIGITS[char]
            seen = True
        elif char in CHINESE_SMALL_UNITS:
            unit = CHINESE_SMALL_UNITS[char]
            section += (number or 1) * unit
            number = 0
            seen = True
        elif char in CHINESE_BIG_UNITS:
            unit = CHINESE_BIG_UNITS[char]
            section += number
            total += (section or 1) * unit
            section = 0
            number = 0
            seen = True
        else:
            return None

    if not seen:
        return None
    return total + section + number


def append_normalized_number(
    chars: list[str],
    mapping: list[int],
    number_text: str,
    source_start: int,
    source_len: int,
) -> None:
    if not number_text:
        return
    if len(number_text) == 1:
        chars.append(number_text)
        mapping.append(source_start)
        return
    for index, char in enumerate(number_text):
        source_offset = round(index * (source_len - 1) / max(1, len(number_text) - 1))
        chars.append(char)
        mapping.append(source_start + source_offset)


def normalize_with_map(text: str) -> tuple[str, list[int]]:
    chars: list[str] = []
    mapping: list[int] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char in CHINESE_NUMBER_CHARS:
            end = index + 1
            while end < len(text) and text[end] in CHINESE_NUMBER_CHARS:
                end += 1
            number_value = parse_chinese_number(text[index:end])
            if number_value is not None:
                append_normalized_number(chars, mapping, str(number_value), index, end - index)
                index = end
                continue

        normalized = unicodedata.normalize('NFKC', char).lower()
        for normalized_char in normalized:
            if normalized_char.isalnum():
                chars.append(normalized_char)
                mapping.append(index)
        index += 1
    return ''.join(chars), mapping


def original_slice(text: str, mapping: list[int], start: int, end: int) -> str:
    if start >= end or not mapping:
        return ''
    start_index = mapping[max(0, start)]
    end_index = mapping[min(len(mapping), end) - 1] + 1
    while start_index > 0 and is_latin_token_char(text[start_index - 1]):
        start_index -= 1
    while end_index < len(text) and is_latin_token_char(text[end_index]):
        end_index += 1
    return text[start_index:end_index].strip()


def is_latin_token_char(char: str) -> bool:
    return char.isascii() and (char.isalnum() or char in '+._/-')


def find_narration_match(
    unit_text: str,
    narration_text: str,
    narration_norm: str,
    narration_map: list[int],
    cursor: int,
    min_confidence: float,
) -> Match | None:
    unit_norm, _ = normalize_with_map(unit_text)
    if not unit_norm:
        return None

    exact_index = narration_norm.find(unit_norm, cursor)
    if exact_index != -1:
        end = exact_index + len(unit_norm)
        return Match(
            start=exact_index,
            end=end,
            confidence=1.0,
            text=original_slice(narration_text, narration_map, exact_index, end),
        )

    window_end = min(len(narration_norm), cursor + max(240, len(unit_norm) * 6))
    if cursor >= window_end:
        return None

    remaining = window_end - cursor
    min_len = max(1, int(len(unit_norm) * 0.55))
    max_len = min(remaining, int(len(unit_norm) * 1.55) + 8)
    best_start = cursor
    best_end = cursor
    best_confidence = 0.0

    for start in range(cursor, window_end):
        local_remaining = window_end - start
        if local_remaining < min_len:
            break
        for length in range(min_len, min(max_len, local_remaining) + 1):
            candidate = narration_norm[start:start + length]
            confidence = weighted_similarity(unit_norm, candidate)
            if confidence > best_confidence:
                best_confidence = confidence
                best_start = start
                best_end = start + length

    if best_confidence < min_confidence:
        return None

    return Match(
        start=best_start,
        end=best_end,
        confidence=round(best_confidence, 4),
        text=original_slice(narration_text, narration_map, best_start, best_end),
    )


def latin_spans(text: str) -> list[re.Match[str]]:
    return list(LATIN_SPAN_RE.finditer(text))


def apply_latin_corrections(transcript_text: str, narration_text: str) -> tuple[str, list[dict[str, str]], list[str]]:
    transcript_spans = latin_spans(transcript_text)
    narration_spans = latin_spans(narration_text)
    if not transcript_spans or not narration_spans:
        return transcript_text, [], [match.group(0) for match in narration_spans]

    pairs = list(zip(transcript_spans, narration_spans))
    corrected = transcript_text
    corrections: list[dict[str, str]] = []
    for transcript_match, narration_match in reversed(pairs):
        source = transcript_match.group(0)
        target = narration_match.group(0)
        if source == target:
            continue
        corrected = corrected[:transcript_match.start()] + target + corrected[transcript_match.end():]
        corrections.append({'from': source, 'to': target})
    corrections.reverse()

    unapplied = [match.group(0) for match in narration_spans[len(pairs):]]
    return corrected, corrections, unapplied


def calibrate(args: argparse.Namespace) -> dict[str, Any]:
    narration_text = read_text(args.narration)
    if not narration_text:
        raise ValueError('narration text is empty')

    sentences = load_transcript(args.transcript)
    units: list[Unit] = []
    for sentence in sentences:
        units.extend(split_sentence(sentence, args.max_chars))
    if not units:
        raise ValueError('transcript produced no subtitle units')

    narration_norm, narration_map = normalize_with_map(narration_text)
    cursor = 0
    out_units: list[dict[str, Any]] = []
    matched_units = 0
    fallback_units = 0
    warnings: list[str] = []

    previous_end = -1
    for index, unit in enumerate(units, start=1):
        if unit.begin_ms < previous_end:
            raise ValueError(f'unit {index} timing overlaps previous unit')
        previous_end = unit.end_ms

        match = find_narration_match(
            unit.text,
            narration_text,
            narration_norm,
            narration_map,
            cursor,
            args.min_confidence,
        )

        display_text = unit.text
        corrections: list[dict[str, str]] = []
        unapplied_latin_tokens: list[str] = []
        source = 'transcript_fallback'
        match_confidence = 0.0
        matched_text = None

        if match is not None:
            matched_units += 1
            match_confidence = match.confidence
            matched_text = match.text
            cursor = max(cursor, match.end)
            display_text, corrections, unapplied_latin_tokens = apply_latin_corrections(unit.text, match.text)
            source = 'transcript_with_narration_latin_corrections' if corrections else 'transcript_with_narration_match'
        else:
            fallback_units += 1
            warnings.append(f'unit {index} used transcript fallback: {unit.text[:40]}')

        out_unit: dict[str, Any] = {
            'index': index,
            'text': display_text,
            'begin_ms': unit.begin_ms,
            'end_ms': unit.end_ms,
            'begin_s': round(unit.begin_ms / 1000, 3),
            'end_s': round(unit.end_ms / 1000, 3),
            'source': source,
            'transcript_text': unit.text,
            'matched_narration_text': matched_text,
            'match_confidence': match_confidence,
            'corrections': corrections,
        }
        if unapplied_latin_tokens:
            out_unit['unapplied_latin_tokens'] = unapplied_latin_tokens
        out_units.append(out_unit)

    return {
        'source_text': os.path.normpath(args.transcript),
        'correction_source': os.path.normpath(args.narration),
        'units': out_units,
        'summary': {
            'unit_count': len(out_units),
            'matched_units': matched_units,
            'fallback_units': fallback_units,
            'warnings': warnings,
        },
    }


def main() -> int:
    args = parse_args()
    try:
        result = calibrate(args)
        output_dir = os.path.dirname(os.path.abspath(args.output))
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as file:
            json.dump(result, file, ensure_ascii=False, indent=2)
            file.write('\n')
        log(f'wrote {args.output} with {result["summary"]["unit_count"]} units')
        print_json(
            {
                'success': True,
                'output_path': os.path.abspath(args.output),
                'summary': result['summary'],
            }
        )
        return 0
    except Exception as exc:
        log(f'error: {exc}')
        print_json({'success': False, 'error': str(exc)})
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
