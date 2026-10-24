#!/usr/bin/env python3
"""Align the ASR transcript to the narration draft and build subtitle units.

Replaces the old calibrate-transcript / scene-anchor pair. Subtitle text
comes from the DISPLAY draft (script.txt); the ASR transcript only provides
timing. The alignment is backend-independent: ASR tokens and the narration
draft are normalized before a character-level alignment, so tokens with or
without punctuation, with or without spaces, and Chinese or Arabic numerals
all align (Chinese numeral runs are converted to Arabic digits, reusing the
normalization logic from the retired calibrate-transcript.py).

Inputs:
  --transcript   transcribe/transcript.json — the stable ASR schema: a list
                 of sentences, each {begin, end, text, words:[{text, begin,
                 end}]} with millisecond timestamps. Word tokens may carry
                 punctuation and may split words arbitrarily.
  --narration    narration.txt — the TTS narration draft (what was actually
                 read aloud).
  --offsets      narration-offsets.json — per-character map from narration
                 positions back to display-draft positions, produced by
                 make-narration.py.
  --script       script.txt — the display draft (subtitle text source).
  --width / --font-size / --max-lines
                 subtitle area parameters: the per-line width cap in CJK
                 units is int(width / font_size); a unit may span up to
                 --max-lines lines (portrait allows 2).
  --scene-plan   optional scene plan JSON; when scenes carry `cues`, each
                 cue's seconds are written to timeline.json.

Alignment:
  Both sides are normalized (NFKC, lowercase, alnum only, Chinese numerals
  -> Arabic digits) and aligned with a character-level SequenceMatcher.
  Equal blocks map narration characters back through the offset table to
  the display draft, so brand names and numerals reappear in display form.
  Transcript regions with no narration match (TTS read extra text, or the
  region is too distorted to align) keep the ASR text. Narration regions
  with no audio (TTS skipped text) are dropped with a warning.

Fallback flag:
  The transcript schema carries no confidence field, so "low confidence" is
  defined by the alignment itself: units that contain ASR text from an
  unaligned region carry `"fallback": true`; aligned units have
  `fallback: false`. Counts are aggregated in `summary.fallback_units`.

Segmentation:
  - split at sentence-final punctuation first (。！？!?…, and Latin .!?
    when not inside a word/number);
  - strip trailing ，and 。from each unit, keep ？！;
  - units wider than the cap break at ，,；;、：:——; breaks never fall
    inside an English word or number (breaks between two Latin-token
    characters are forbidden);
  - a too-short trailing segment (narrower than max(2, 0.2 * cap)) is
    rebalanced once by re-splitting the last two segments at the break
    position closest to their midpoint;
  - units shorter than 0.6 s are merged into a neighbour (the previous
    unit when one exists); a merged unit may exceed the width cap, which
    is the lesser evil compared with a flashing subtitle.

Outputs (paths from --units-output / --timeline-output):
  subtitle-units.json : {"version": 1, "units": [...], "summary": {...}}
    each unit: {index, text, begin_ms, end_ms, begin_s, end_s, fallback,
    paragraph} — the text / begin_s / end_s fields keep the existing
    downstream contract of the old calibrate-transcript units.
  timeline.json : {"version": 1, "total_s", "paragraphs": [{index, begin_s,
    end_s}]}; with --scene-plan a "cues" list [{scene_id, cue, begin_s,
    end_s}] is added (cues that cannot be located are reported as warnings
    and omitted).

Output convention:
  stdout : one JSON object
    success: {"success": true, "units_path": ..., "timeline_path": ...,
              "summary": {...}}
    error:   {"success": false, "error": "..."}
  stderr : human-readable log prefixed with [align-narration]
  exit   : 0 success, 1 runtime error, 2 invalid arguments
"""
from __future__ import annotations

import argparse
import bisect
import difflib
import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from typing import Any, Callable

TOOL_NAME = 'align-narration'

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

SENTENCE_FINAL_CHARS = set('。！？!?…')
TRAILING_STRIP_CHARS = {'，', ',', '。'}
SOFT_BREAK_CHARS = {'，', ',', '；', ';', '、', '：', ':', '—', '–', '-'}
MIN_UNIT_MS = 600


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
class Atom:
    """One display character with timing (atoms are the segmentation atoms).

    borrowed=True marks punctuation/space atoms that inherited the timing of
    a neighbouring aligned character; unit boundaries ignore them so a unit
    that starts with a space never overlaps the previous unit.
    """

    text: str
    begin_ms: int
    end_ms: int
    fallback: bool
    paragraph: int
    borrowed: bool = False


def log(message: str) -> None:
    print(f'[{TOOL_NAME}] {message}', file=sys.stderr)


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def parse_args() -> argparse.Namespace:
    parser = JsonArgumentParser(
        description='Align transcript timing onto the display draft and build subtitle units + timeline.'
    )
    parser.add_argument('--transcript', required=True, help='Path to transcribe/transcript.json')
    parser.add_argument('--narration', required=True, help='Path to narration.txt (the TTS narration draft)')
    parser.add_argument('--offsets', required=True, help='Path to narration-offsets.json (from make-narration)')
    parser.add_argument('--script', required=True, help='Path to script.txt (the display draft)')
    parser.add_argument(
        '--units-output',
        default=None,
        help='Output path for subtitle units (default: <transcript dir>/subtitle-units.json).',
    )
    parser.add_argument(
        '--timeline-output',
        default=None,
        help='Output path for timeline.json (default: <transcript dir>/timeline.json).',
    )
    parser.add_argument('--width', type=int, default=1200, help='Subtitle area width in px (default 1200).')
    parser.add_argument('--font-size', type=int, default=42, help='Subtitle font size in px (default 42).')
    parser.add_argument('--max-lines', type=int, default=1, help='Maximum subtitle lines per unit (default 1).')
    parser.add_argument(
        '--scene-plan',
        default=None,
        help='Optional scene plan JSON with per-scene cues; enables cue seconds in timeline.json.',
    )
    args = parser.parse_args()
    if args.width <= 0 or args.font_size <= 0 or args.max_lines < 1:
        parser.error('--width and --font-size must be positive, --max-lines must be >= 1')
    return args


def read_text(path: str) -> str:
    """Raw read: narration/script positions must match the offset table exactly."""
    with open(path, encoding='utf-8') as file:
        return file.read()


def as_int_ms(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{label} is not a numeric timestamp: {value!r}')
    return int(round(value))


def load_transcript(path: str) -> list[Word]:
    with open(path, encoding='utf-8') as file:
        data = json.load(file)
    if not isinstance(data, list) or not data:
        raise ValueError('transcript root must be a non-empty list of sentence objects')
    words: list[Word] = []
    for sentence_index, sentence in enumerate(data, start=1):
        if not isinstance(sentence, dict):
            raise ValueError(f'transcript sentence {sentence_index} is not an object')
        raw_words = sentence.get('words')
        if not isinstance(raw_words, list) or not raw_words:
            raise ValueError(f'transcript sentence {sentence_index} has no word timestamps')
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
        raise ValueError('transcript has no non-empty words')
    return words


# --- normalization (number handling reused from retired calibrate-transcript) ----


def parse_chinese_number(text: str) -> int | None:
    if not text:
        return None
    if all(char in CHINESE_DIGITS for char in text):
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
    """Lowercased alnum-only stream; Chinese numeral runs become Arabic digits.

    Returns (normalized_text, mapping) where mapping[i] is the index of the
    source character that produced normalized character i.
    """
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


def is_latin_token_char(char: str) -> bool:
    return char.isascii() and (char.isalnum() or char in '+._/-')


def is_cjk(char: str) -> bool:
    return (
        '㐀' <= char <= '䶿'
        or '一' <= char <= '鿿'
        or '豈' <= char <= '﫿'
    )


# --- inputs ----------------------------------------------------------------------


def load_offsets(path: str) -> tuple[dict[str, Any], Callable[[int], int]]:
    with open(path, encoding='utf-8') as file:
        data = json.load(file)
    if not isinstance(data, dict) or not isinstance(data.get('segments'), list):
        raise ValueError('offsets file must be an object with a segments list')
    segments = sorted(data['segments'], key=lambda seg: seg['narration_start'])
    starts = [seg['narration_start'] for seg in segments]

    def to_script(position: int) -> int:
        index = bisect.bisect_right(starts, position) - 1
        if index < 0:
            raise ValueError(f'narration position {position} not covered by offset table')
        segment = segments[index]
        span = max(0, segment['script_end'] - segment['script_start'] - 1)
        return segment['script_start'] + min(position - segment['narration_start'], span)

    return data, to_script


def paragraph_spans(text: str) -> list[tuple[int, int]]:
    """Non-blank line groups: [(start, end)] character spans, 1-based lookup."""
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


# --- alignment -------------------------------------------------------------------


def build_display_atoms(
    script_text: str,
    narration_map: list[int],
    to_script: Callable[[int], int],
    n_start: int,
    n_end: int,
    a_start: int,
    a_end: int,
    asr_times: list[tuple[int, int]],
    paragraph: int,
) -> list[Atom]:
    """Turn one aligned (per-paragraph) equal block into display-draft atoms.

    The display slice spans the draft characters covered by the block; the
    punctuation and spaces inside it reappear in subtitle text (that is what
    keeps English words spaced and numerals in display form). Unaligned
    display characters borrow the timing of the nearest aligned character.
    """
    display_start = to_script(narration_map[n_start])
    display_end = to_script(narration_map[n_end - 1]) + 1
    # swallow sentence-final punctuation right after the last aligned char
    while display_end < len(script_text) and script_text[display_end] in SENTENCE_FINAL_CHARS:
        display_end += 1
    display = script_text[display_start:display_end]
    aligned_count = n_end - n_start
    aligned_of: list[int | None] = [None] * len(display)
    for offset in range(aligned_count):
        position = to_script(narration_map[n_start + offset]) - display_start
        if 0 <= position < len(display):
            aligned_of[position] = offset
    aligned_of_direct = list(aligned_of)
    last: int | None = None
    for position in range(len(display)):
        if aligned_of[position] is not None:
            last = aligned_of[position]
        elif last is not None:
            aligned_of[position] = last
    for position in range(len(display) - 1, -1, -1):
        if aligned_of[position] is None and position + 1 < len(display):
            aligned_of[position] = aligned_of[position + 1]
    atoms: list[Atom] = []
    for position, char in enumerate(display):
        offset = aligned_of[position]
        if offset is None:  # display text the offsets table does not cover
            continue
        begin_ms, end_ms = asr_times[a_start + offset]
        atoms.append(Atom(text=char, begin_ms=begin_ms, end_ms=end_ms,
                          fallback=False, paragraph=paragraph,
                          borrowed=aligned_of_direct[position] is None))
    return atoms


def build_atoms(
    script_text: str,
    narration_text: str,
    to_script: Callable[[int], int],
    words: list[Word],
    spans: list[tuple[int, int]],
    warnings: list[str],
) -> list[Atom]:
    """Character-level alignment -> timed display atoms.

    Equal blocks yield display-draft atoms (fallback=False); transcript-only
    blocks keep the ASR text (fallback=True); narration-only blocks are
    dropped with a warning (no audio exists for them).
    """
    narration_norm, narration_map = normalize_with_map(narration_text)

    asr_chars: list[str] = []
    asr_times: list[tuple[int, int]] = []
    asr_word_spans: list[tuple[int, int]] = []
    for word in words:
        word_norm, _ = normalize_with_map(word.text)
        span_start = len(asr_chars)
        count = max(1, len(word_norm))
        for offset in range(count):
            begin = word.begin + round((word.end - word.begin) * offset / count)
            end = word.begin + round((word.end - word.begin) * (offset + 1) / count)
            asr_chars.append(word_norm[offset])
            asr_times.append((begin, end))
        asr_word_spans.append((span_start, len(asr_chars)))
    asr_norm = ''.join(asr_chars)

    span_starts = [span[0] for span in spans]

    def paragraph_of(narration_char_index: int) -> int:
        index = bisect.bisect_right(span_starts, narration_char_index) - 1
        return index + 1  # 1-based

    atoms: list[Atom] = []
    matcher = difflib.SequenceMatcher(None, narration_norm, asr_norm, autojunk=False)
    for tag, n1, n2, a1, a2 in matcher.get_opcodes():
        if tag == 'equal':
            # an equal run may span paragraph breaks (newlines normalize away);
            # process it in per-paragraph sub-runs
            offset = 0
            while offset < n2 - n1:
                paragraph = paragraph_of(narration_map[n1 + offset])
                sub_end = offset + 1
                while sub_end < n2 - n1 and paragraph_of(narration_map[n1 + sub_end]) == paragraph:
                    sub_end += 1
                atoms.extend(
                    build_display_atoms(
                        script_text, narration_map, to_script,
                        n1 + offset, n1 + sub_end, a1 + offset, a1 + sub_end,
                        asr_times, paragraph,
                    )
                )
                offset = sub_end
        elif tag in ('replace', 'insert'):
            # ASR text with no narration counterpart: keep it, flag fallback.
            paragraph = atoms[-1].paragraph if atoms else 1
            for word_index, (span_start, span_end) in enumerate(asr_word_spans):
                if span_end <= a1 or span_start >= a2:
                    continue
                word = words[word_index]
                count = max(1, len(word.text))
                for offset, char in enumerate(word.text):
                    begin = word.begin + round((word.end - word.begin) * offset / count)
                    end = word.begin + round((word.end - word.begin) * (offset + 1) / count)
                    atoms.append(Atom(text=char, begin_ms=begin, end_ms=end,
                                      fallback=True, paragraph=paragraph))
        elif tag == 'delete':
            dropped_start = narration_map[n1]
            dropped_end = narration_map[n2 - 1] + 1
            dropped = narration_text[dropped_start:dropped_end].strip()
            if dropped:
                warning = f'narration text has no audio and was dropped: {dropped[:40]}'
                warnings.append(warning)
                log(f'warning: {warning}')

    return atoms


# --- segmentation ----------------------------------------------------------------


def char_width(char: str) -> float:
    if is_cjk(char):
        return 1.0
    if char.isascii():
        if char.isalnum():
            return 0.55
        if char.isspace():
            return 0.3
        return 0.4
    return 1.0


def atoms_width(atoms: list[Atom]) -> float:
    return sum(char_width(atom.text) for atom in atoms)


def break_allowed(left: Atom, right: Atom) -> bool:
    # never break inside an English word or number
    return not (is_latin_token_char(left.text) and is_latin_token_char(right.text))


def unit_text(atoms: list[Atom]) -> str:
    text = ''.join(atom.text for atom in atoms).rstrip()
    while text and text[-1] in TRAILING_STRIP_CHARS:
        text = text[:-1].rstrip()
    return text


def unit_bounds(atoms: list[Atom]) -> tuple[int, int] | None:
    """Effective (begin_ms, end_ms): borrowed punctuation/space atoms at the
    edges are ignored so adjacent units never overlap on borrowed timing."""
    anchors = [atom for atom in atoms if not atom.borrowed]
    if not anchors:
        anchors = atoms
    return anchors[0].begin_ms, anchors[-1].end_ms


def find_cut(current: list[Atom], overflow: Atom) -> int | None:
    """Index of the atom AFTER which to cut, or None if no valid cut exists.

    The cut may sit at the very end of ``current`` (the atom after the cut
    is then ``overflow``); a cut between two Latin-token characters is
    never allowed, so English words and numbers are never split.
    """
    def right_of(index: int) -> Atom:
        return current[index + 1] if index + 1 < len(current) else overflow

    for index in range(len(current) - 1, -1, -1):
        if current[index].text in SOFT_BREAK_CHARS and break_allowed(current[index], right_of(index)):
            return index
    for index in range(len(current) - 1, -1, -1):
        if break_allowed(current[index], right_of(index)):
            return index
    return None


def rebalance(segments: list[list[Atom]], cap: float) -> list[list[Atom]]:
    """Fix a too-short trailing segment by re-splitting the last two segments."""
    if len(segments) < 2:
        return segments
    last_width = atoms_width(segments[-1])
    if last_width >= max(2.0, 0.2 * cap):
        return segments
    combined = segments[-2] + segments[-1]
    cuts = [
        index
        for index in range(len(combined) - 1)
        if break_allowed(combined[index], combined[index + 1])
    ]
    if not cuts:
        return segments
    half = atoms_width(combined) / 2
    best = min(cuts, key=lambda index: abs(atoms_width(combined[:index + 1]) - half))
    head, tail = combined[:best + 1], combined[best + 1:]
    if not tail or atoms_width(tail) <= last_width + 0.01:
        return segments  # no improvement
    return segments[:-2] + [head, tail]


def split_sentence(sentence: list[Atom], cap: float, warnings: list[str]) -> list[list[Atom]]:
    if atoms_width(sentence) <= cap or len(sentence) < 2:
        return [sentence]
    segments: list[list[Atom]] = []
    current: list[Atom] = []
    current_width = 0.0
    for atom in sentence:
        width = char_width(atom.text)
        if current and current_width + width > cap:
            cut = find_cut(current, atom)
            if cut is None:
                cut = len(current) - 1  # single token wider than the cap
                warnings.append(f'segment exceeds width cap; broke inside a token: {current[0].text[:20]}')
            segments.append(current[:cut + 1])
            current = current[cut + 1:]
            current_width = atoms_width(current)
        current.append(atom)
        current_width += width
    if current:
        segments.append(current)
    return rebalance(segments, cap)


def split_into_sentences(atoms: list[Atom]) -> list[list[Atom]]:
    sentences: list[list[Atom]] = []
    current: list[Atom] = []
    for index, atom in enumerate(atoms):
        current.append(atom)
        next_char = atoms[index + 1].text if index + 1 < len(atoms) else ''
        is_final = atom.text in SENTENCE_FINAL_CHARS or (
            atom.text in '.!?' and not is_latin_token_char(next_char)
        )
        if is_final:
            sentences.append(current)
            current = []
    if current:
        sentences.append(current)
    return sentences


def merge_short_units(
    units: list[list[Atom]], cap: float, warnings: list[str]
) -> tuple[list[list[Atom]], int]:
    """Merge units shorter than MIN_UNIT_MS into a neighbour (previous first).

    A merged unit may exceed the width cap; that is preferred over a
    subtitle that flashes for less than MIN_UNIT_MS.
    """
    merged_count = 0
    changed = True
    while changed:
        changed = False
        index = 0
        while index < len(units):
            atoms = units[index]
            if atoms and atoms[-1].end_ms - atoms[0].begin_ms < MIN_UNIT_MS and len(units) > 1:
                if index > 0:
                    units[index - 1:index + 1] = [units[index - 1] + atoms]
                    index -= 1
                else:
                    units[index:index + 2] = [atoms + units[index + 1]]
                merged_count += 1
                changed = True
            index += 1
    return units, merged_count


# --- timeline cues -----------------------------------------------------------------


def locate_cues(
    scene_plan: list[dict[str, Any]],
    atoms_by_paragraph: dict[int, list[Atom]],
    warnings: list[str],
) -> list[dict[str, Any]]:
    cues: list[dict[str, Any]] = []
    for scene in scene_plan:
        if not isinstance(scene, dict):
            continue
        scene_id = scene.get('scene_id') or scene.get('id')
        paragraphs = scene.get('paragraphs') or []
        for cue in scene.get('cues') or []:
            cue_norm, _ = normalize_with_map(str(cue))
            found: tuple[int, int] | None = None
            for paragraph in paragraphs:
                atoms = atoms_by_paragraph.get(int(paragraph), [])
                norm_chars: list[str] = []
                norm_atom: list[Atom] = []
                for atom in atoms:
                    for char in normalize_with_map(atom.text)[0]:
                        norm_chars.append(char)
                        norm_atom.append(atom)
                haystack = ''.join(norm_chars)
                position = haystack.find(cue_norm) if cue_norm else -1
                if position != -1:
                    first = norm_atom[position]
                    last = norm_atom[position + len(cue_norm) - 1]
                    found = (first.begin_ms, last.end_ms)
                    break
            if found is None:
                warning = f'cue not found for scene {scene_id!r}: {str(cue)[:40]!r}'
                warnings.append(warning)
                log(f'warning: {warning}')
                continue
            cues.append(
                {
                    'scene_id': scene_id,
                    'cue': cue,
                    'begin_s': round(found[0] / 1000, 3),
                    'end_s': round(found[1] / 1000, 3),
                }
            )
    return cues


# --- main --------------------------------------------------------------------------


def align(args: argparse.Namespace) -> dict[str, Any]:
    narration_text = read_text(args.narration)
    if not narration_text.strip():
        raise ValueError('narration text is empty')
    script_text = read_text(args.script)
    if not script_text.strip():
        raise ValueError('display draft (script) is empty')
    words = load_transcript(args.transcript)
    offsets, to_script = load_offsets(args.offsets)
    if offsets.get('narration_length') not in (None, len(narration_text)):
        raise ValueError('offsets narration_length does not match narration.txt')
    if offsets.get('script_length') not in (None, len(script_text)):
        raise ValueError('offsets script_length does not match script.txt')

    spans = paragraph_spans(narration_text)
    if not spans:
        raise ValueError('narration has no paragraphs')

    warnings: list[str] = []
    atoms = build_atoms(script_text, narration_text, to_script, words, spans, warnings)

    cap = int(args.width / args.font_size) * args.max_lines
    log(f'paragraphs={len(spans)} asr_words={len(words)} atoms={len(atoms)} cap={cap}')

    atoms_by_paragraph: dict[int, list[Atom]] = {}
    for atom in atoms:
        atoms_by_paragraph.setdefault(atom.paragraph, []).append(atom)

    units: list[dict[str, Any]] = []
    fallback_units = 0
    merged_total = 0
    previous_end = -1
    for paragraph in sorted(atoms_by_paragraph):
        paragraph_atoms = atoms_by_paragraph[paragraph]
        segments: list[list[Atom]] = []
        for sentence in split_into_sentences(paragraph_atoms):
            segments.extend(split_sentence(sentence, cap, warnings))
        segments, merged = merge_short_units(segments, cap, warnings)
        merged_total += merged
        for segment in segments:
            text = unit_text(segment)
            if not text:
                continue
            bounds = unit_bounds(segment)
            if bounds is None:
                continue
            begin_ms, end_ms = bounds
            if begin_ms < previous_end:
                raise ValueError('unit timing overlaps previous unit')
            previous_end = end_ms
            fallback = any(atom.fallback for atom in segment)
            if fallback:
                fallback_units += 1
            units.append(
                {
                    'index': len(units) + 1,
                    'text': text,
                    'begin_ms': begin_ms,
                    'end_ms': end_ms,
                    'begin_s': round(begin_ms / 1000, 3),
                    'end_s': round(end_ms / 1000, 3),
                    'fallback': fallback,
                    'paragraph': paragraph,
                }
            )

    if not units:
        raise ValueError('alignment produced no subtitle units')

    paragraphs = []
    for paragraph in sorted(atoms_by_paragraph):
        paragraph_atoms = atoms_by_paragraph[paragraph]
        paragraphs.append(
            {
                'index': paragraph,
                'begin_s': round(min(atom.begin_ms for atom in paragraph_atoms) / 1000, 3),
                'end_s': round(max(atom.end_ms for atom in paragraph_atoms) / 1000, 3),
            }
        )
    for paragraph_index in range(1, len(spans) + 1):
        if paragraph_index not in atoms_by_paragraph:
            warning = f'paragraph {paragraph_index} has no aligned audio; missing from timeline'
            warnings.append(warning)
            log(f'warning: {warning}')

    total_s = round(max(atom.end_ms for atom in atoms) / 1000, 3)

    cues: list[dict[str, Any]] = []
    if args.scene_plan:
        with open(args.scene_plan, encoding='utf-8') as file:
            scene_plan = json.load(file)
        if not isinstance(scene_plan, list):
            raise ValueError('scene plan root must be a list')
        cues = locate_cues(scene_plan, atoms_by_paragraph, warnings)

    return {
        'units': {'version': 1, 'units': units, 'summary': {}},
        'timeline': {
            'version': 1,
            'total_s': total_s,
            'paragraphs': paragraphs,
            **({'cues': cues} if args.scene_plan else {}),
        },
        'summary': {
            'unit_count': len(units),
            'fallback_units': fallback_units,
            'merged_units': merged_total,
            'cue_count': len(cues),
            'warnings': warnings,
        },
    }


def main() -> int:
    args = parse_args()
    transcript_dir = os.path.dirname(os.path.abspath(args.transcript))
    units_output = args.units_output or os.path.join(transcript_dir, 'subtitle-units.json')
    timeline_output = args.timeline_output or os.path.join(transcript_dir, 'timeline.json')
    try:
        result = align(args)
        result['units']['summary'] = result['summary']
        for output_path, payload in (
            (units_output, result['units']),
            (timeline_output, result['timeline']),
        ):
            output_dir = os.path.dirname(os.path.abspath(output_path))
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as file:
                json.dump(payload, file, ensure_ascii=False, indent=2)
                file.write('\n')
            log(f'wrote {output_path}')
        print_json(
            {
                'success': True,
                'units_path': os.path.abspath(units_output),
                'timeline_path': os.path.abspath(timeline_output),
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
