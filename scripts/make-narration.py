#!/usr/bin/env python3
"""Generate the TTS narration draft from the display draft and a TTS lexicon.

The script stage of the pipeline produces a display draft (`script.txt`,
paragraph-separated, used for subtitles and visuals) and a lexicon
(`tts-lexicon.json`, a display form -> reading form map for brand names,
numbers, years, etc.).  This script derives the narration draft
(`narration.txt`) deterministically, so only the display draft and the
lexicon are ever hand-written.

Replacement rule (deterministic):
  Scan the display draft left to right.  At each position, among the lexicon
  entries whose display form matches the text starting at that position, the
  LONGEST display form wins.  Ties (same display-form length) break on the
  display form string itself.  If no entry matches, the character is copied
  unchanged.  Newlines and paragraph structure are preserved as-is.

Offset table (`narration-offsets.json`): every narration character position
can be mapped back to a display-draft position.  The table is a sorted,
contiguous list of segments covering [0, len(narration)):

  {"version": 1,
   "script_length": S, "narration_length": N,
   "segments": [{"narration_start": a, "narration_end": b,
                 "script_start": c, "script_end": d}]}

  narration position i maps back to
  script_start + min(i - narration_start, script_end - script_start - 1).

Usage:
  python3 scripts/make-narration.py \
    --script {work_dir}/{topic_name}/script.txt \
    --lexicon {work_dir}/{topic_name}/tts-lexicon.json \
    --output-dir {work_dir}/{topic_name}/

  # custom output paths (defaults below):
  --narration-out PATH   (default <output-dir>/narration.txt)
  --offsets-out PATH     (default <output-dir>/narration-offsets.json)

Output convention:
  stdout : single JSON object
    success: {"success": true, "narration_path": "...",
              "offsets_path": "...", "script_length": N,
              "narration_length": N, "replacement_count": N}
    error:   {"success": false, "error": "..."}
  stderr : human-readable progress prefixed with `[make-narration]`
  exit   : 0 success, 1 runtime error, 2 invalid arguments
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

TOOL_NAME = 'make-narration'
OFFSETS_VERSION = 1


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        log(f'Argument error: {message}')
        print(json.dumps({'success': False, 'error': message}, ensure_ascii=False))
        self.exit(2)


def log(message: str) -> None:
    print(f'[{TOOL_NAME}] {message}', file=sys.stderr)


def fail(message: str, exit_code: int = 1) -> None:
    log(message)
    print(json.dumps({'success': False, 'error': message}, ensure_ascii=False))
    raise SystemExit(exit_code)


def parse_args() -> argparse.Namespace:
    p = ArgumentParser(description='Derive the TTS narration draft from the display draft + lexicon.')
    p.add_argument('--script', required=True, help='Path to the display draft (script.txt).')
    p.add_argument('--lexicon', required=True, help='Path to the TTS lexicon (tts-lexicon.json).')
    p.add_argument('--output-dir', required=True, help='Directory for narration.txt and narration-offsets.json.')
    p.add_argument('--narration-out', default=None,
                   help='Narration output path (default <output-dir>/narration.txt).')
    p.add_argument('--offsets-out', default=None,
                   help='Offset table output path (default <output-dir>/narration-offsets.json).')
    return p.parse_args()


def load_lexicon(path: Path) -> dict[str, str]:
    """Load and validate the lexicon: a JSON object of non-empty str -> non-empty str."""
    if not path.is_file():
        fail(f'lexicon file not found: {path}')
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(f'lexicon is not valid JSON: {exc}')
    if not isinstance(data, dict):
        fail('lexicon root is not a JSON object (display form -> reading form map)')
    lexicon: dict[str, str] = {}
    for key, value in data.items():
        if not isinstance(key, str) or not isinstance(value, str):
            fail(f'lexicon entries must be strings, got {key!r}: {value!r}')
        if not key:
            fail('lexicon contains an empty display form')
        lexicon[key] = value
    return lexicon


def build_matches(lexicon: dict[str, str]) -> list[tuple[str, str]]:
    """Lexicon entries sorted for deterministic scanning:
    display-form length descending, then display form string ascending."""
    return sorted(lexicon.items(), key=lambda kv: (-len(kv[0]), kv[0]))


def render(script_text: str, lexicon: dict[str, str]) -> tuple[str, list[dict[str, int]], int]:
    """Deterministically replace lexicon entries in the display draft.

    Returns (narration_text, segments, replacement_count).  Segments map
    contiguous narration spans back to contiguous display-draft spans; both
    sides include newlines so paragraph structure lines up.
    """
    matches = build_matches(lexicon)
    narration_chars: list[str] = []
    segments: list[dict[str, int]] = []
    replacement_count = 0

    n = len(script_text)
    i = 0
    seg_n_start = 0
    seg_s_start = 0

    def flush_segment(until_n: int, until_s: int) -> None:
        if until_n > seg_n_start:
            segments.append({
                'narration_start': seg_n_start,
                'narration_end': until_n,
                'script_start': seg_s_start,
                'script_end': until_s,
            })

    while i < n:
        hit: tuple[str, str] | None = None
        for display, reading in matches:
            if display and script_text.startswith(display, i):
                hit = (display, reading)
                break
        if hit is not None:
            display, reading = hit
            # flush pending 1:1 span before the replacement
            flush_segment(len(narration_chars), i)
            narration_chars.extend(reading)
            segments.append({
                'narration_start': len(narration_chars) - len(reading),
                'narration_end': len(narration_chars),
                'script_start': i,
                'script_end': i + len(display),
            })
            seg_n_start = len(narration_chars)
            seg_s_start = i + len(display)
            replacement_count += 1
            i += len(display)
        else:
            narration_chars.append(script_text[i])
            i += 1

    flush_segment(len(narration_chars), n)
    return ''.join(narration_chars), segments, replacement_count


def main() -> None:
    args = parse_args()

    script_path = Path(args.script).expanduser()
    lexicon_path = Path(args.lexicon).expanduser()
    output_dir = Path(args.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    narration_path = Path(args.narration_out).expanduser() if args.narration_out \
        else output_dir / 'narration.txt'
    offsets_path = Path(args.offsets_out).expanduser() if args.offsets_out \
        else output_dir / 'narration-offsets.json'

    if not script_path.is_file():
        fail(f'script file not found: {script_path}')
    script_text = script_path.read_text(encoding='utf-8')
    if not script_text.strip():
        fail(f'script file is empty: {script_path}')

    lexicon = load_lexicon(lexicon_path)
    log(f'Loaded {len(lexicon)} lexicon entries from {lexicon_path}')

    narration_text, segments, replacement_count = render(script_text, lexicon)

    narration_path.write_text(narration_text, encoding='utf-8')
    offsets_payload = {
        'version': OFFSETS_VERSION,
        'script_length': len(script_text),
        'narration_length': len(narration_text),
        'segments': segments,
    }
    offsets_path.write_text(
        json.dumps(offsets_payload, indent=2, ensure_ascii=False), encoding='utf-8'
    )

    log(f'Narration written to {narration_path} ({len(narration_text)} chars, '
        f'{replacement_count} replacements)')
    log(f'Offset table written to {offsets_path} ({len(segments)} segments)')

    print(json.dumps({
        'success': True,
        'narration_path': str(narration_path),
        'offsets_path': str(offsets_path),
        'script_length': len(script_text),
        'narration_length': len(narration_text),
        'replacement_count': replacement_count,
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
