"""Integration tests for scripts/make-narration.py.

The test seam is the script's command line (repo convention: stdout = one
JSON, exit codes 0 / 1 / 2). Fixture files are built in tmp dirs.

Offset-table contract under test (narration-offsets.json):
  {
    "version": 1,
    "script_length": S,        # character length of the display draft
    "narration_length": N,     # character length of the narration output
    "segments": [
      {"narration_start": a, "narration_end": b,
       "script_start": c, "script_end": d}
    ]
  }
  - segments are sorted and contiguous: they cover every narration position
    [0, N) exactly once;
  - narration position i maps back to the display draft at
    script_start + min(i - narration_start, script_end - script_start - 1);
  - for 1:1 (unreplaced) spans the two lengths are equal and characters
    match the display draft exactly.

Replacement rule under test: at each display-draft position, lexicon entries
are matched longest-display-form-first; ties break on the display form string
(see the script docstring and references/phases/06-script-scene-plan.md).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / 'scripts' / 'make-narration.py'

SCRIPT_TEXT = 'OpenHuman 在 2026 年发布了新模型。\n\nNVIDIA 股价涨 5%。\n'

LEXICON = {
    'OpenHuman': 'Open Human',
    '2026 年': '二零二六年',
    'NVIDIA': '英伟达',
    '5%': '百分之五',
}

EXPECTED_NARRATION = 'Open Human 在 二零二六年发布了新模型。\n\n英伟达 股价涨 百分之五。\n'


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')


def make_fixtures(tmp_path: Path, script_text: str = SCRIPT_TEXT, lexicon=LEXICON):
    script_path = tmp_path / 'script.txt'
    lexicon_path = tmp_path / 'tts-lexicon.json'
    out_dir = tmp_path / 'out'
    write_text(script_path, script_text)
    write_json(lexicon_path, lexicon)
    return script_path, lexicon_path, out_dir


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


def parse_result(proc: subprocess.CompletedProcess) -> dict:
    """stdout must be exactly one parseable JSON document."""
    assert proc.returncode in (0, 1, 2)
    return json.loads(proc.stdout)


def run_success(tmp_path: Path, script_text: str = SCRIPT_TEXT, lexicon=LEXICON) -> dict:
    script_path, lexicon_path, out_dir = make_fixtures(tmp_path, script_text, lexicon)
    proc = run_cli('--script', str(script_path), '--lexicon', str(lexicon_path),
                   '--output-dir', str(out_dir))
    assert proc.returncode == 0
    return parse_result(proc)


# --- replacement behavior ---------------------------------------------------


def test_lexicon_replacement_produces_expected_narration(tmp_path: Path):
    result = run_success(tmp_path)
    assert result['success'] is True
    narration = Path(result['narration_path']).read_text(encoding='utf-8')
    assert narration == EXPECTED_NARRATION
    assert result['narration_length'] == len(EXPECTED_NARRATION)


def test_replacement_is_deterministic(tmp_path: Path):
    script_path, lexicon_path, out_dir = make_fixtures(tmp_path)
    args = ('--script', str(script_path), '--lexicon', str(lexicon_path),
            '--output-dir', str(out_dir))
    first = run_cli(*args)
    narration_1 = Path(json.loads(first.stdout)['narration_path']).read_bytes()
    offsets_1 = Path(json.loads(first.stdout)['offsets_path']).read_bytes()
    second = run_cli(*args)
    narration_2 = Path(json.loads(second.stdout)['narration_path']).read_bytes()
    offsets_2 = Path(json.loads(second.stdout)['offsets_path']).read_bytes()
    assert first.returncode == 0 and second.returncode == 0
    assert narration_1 == narration_2
    assert offsets_1 == offsets_2


def test_empty_lexicon_is_identity(tmp_path: Path):
    result = run_success(tmp_path, lexicon={})
    narration = Path(result['narration_path']).read_text(encoding='utf-8')
    assert narration == SCRIPT_TEXT
    offsets = json.loads(Path(result['offsets_path']).read_text(encoding='utf-8'))
    for seg in offsets['segments']:
        # every span maps 1:1 back to the display draft
        assert seg['narration_end'] - seg['narration_start'] == \
            seg['script_end'] - seg['script_start']


def test_overlapping_entries_use_longest_match_first(tmp_path: Path):
    # "OpenHuman" and "Open" both match at position 0; the longer display
    # form must win. "Human" vs "Humanity": only "Human" matches here.
    lexicon = {'OpenHuman': 'Open Human', 'Open': 'Opened', 'Human': 'Humanity'}
    result = run_success(tmp_path, script_text='OpenHuman 和 Human。\n', lexicon=lexicon)
    narration = Path(result['narration_path']).read_text(encoding='utf-8')
    assert narration == 'Open Human 和 Humanity。\n'


def test_overlapping_numeric_entries_use_longest_match_first(tmp_path: Path):
    lexicon = {'2026': '二零二六', '2026 年': '二零二六年'}
    result = run_success(tmp_path, script_text='到 2026 年为止。\n', lexicon=lexicon)
    narration = Path(result['narration_path']).read_text(encoding='utf-8')
    assert narration == '到 二零二六年为止。\n'


# --- offset table -----------------------------------------------------------


def map_position(offsets: dict, pos: int) -> int:
    """Map a narration position back to a display-draft position."""
    for seg in offsets['segments']:
        if seg['narration_start'] <= pos < seg['narration_end']:
            span = seg['script_end'] - seg['script_start']
            return seg['script_start'] + min(pos - seg['narration_start'], span - 1)
    raise AssertionError(f'narration position {pos} is not covered by any segment')


def test_offset_table_maps_every_narration_position(tmp_path: Path):
    script_path, lexicon_path, out_dir = make_fixtures(tmp_path)
    proc = run_cli('--script', str(script_path), '--lexicon', str(lexicon_path),
                   '--output-dir', str(out_dir))
    result = parse_result(proc)
    assert proc.returncode == 0
    script_text = SCRIPT_TEXT
    narration = Path(result['narration_path']).read_text(encoding='utf-8')
    offsets = json.loads(Path(result['offsets_path']).read_text(encoding='utf-8'))

    assert offsets['narration_length'] == len(narration)
    assert offsets['script_length'] == len(script_text)
    # segments are sorted and contiguous, covering [0, len(narration))
    cursor = 0
    for seg in offsets['segments']:
        assert seg['narration_start'] == cursor
        assert seg['narration_end'] > seg['narration_start']
        assert seg['script_end'] > seg['script_start']
        assert 0 <= seg['script_start'] < seg['script_end'] <= len(script_text)
        cursor = seg['narration_end']
    assert cursor == len(narration)

    # every narration position maps back inside the display draft
    for pos in range(len(narration)):
        script_pos = map_position(offsets, pos)
        assert 0 <= script_pos < len(script_text)


def test_offset_table_unreplaced_spans_preserve_exact_characters(tmp_path: Path):
    result = run_success(tmp_path)
    script_text = SCRIPT_TEXT
    narration = Path(result['narration_path']).read_text(encoding='utf-8')
    offsets = json.loads(Path(result['offsets_path']).read_text(encoding='utf-8'))
    for seg in offsets['segments']:
        n_len = seg['narration_end'] - seg['narration_start']
        s_len = seg['script_end'] - seg['script_start']
        if n_len == s_len:
            # 1:1 span: characters must match the display draft exactly
            assert narration[seg['narration_start']:seg['narration_end']] == \
                script_text[seg['script_start']:seg['script_end']]


def test_offset_table_marks_replaced_spans(tmp_path: Path):
    # the "OpenHuman" → "Open Human" replacement must appear as a segment
    # whose lengths differ (10 narration chars over 9 script chars)
    result = run_success(tmp_path)
    offsets = json.loads(Path(result['offsets_path']).read_text(encoding='utf-8'))
    replaced = [seg for seg in offsets['segments']
                if seg['narration_end'] - seg['narration_start']
                != seg['script_end'] - seg['script_start']]
    assert replaced, 'expected at least one replaced segment'
    assert replaced[0]['script_start'] == 0  # OpenHuman sits at the very start


# --- errors -----------------------------------------------------------------


def test_usage_error_exits_2(tmp_path: Path):
    proc = run_cli('--bogus-flag')
    assert proc.returncode == 2
    result = parse_result(proc)
    assert result['success'] is False


def test_missing_script_file_exits_1(tmp_path: Path):
    lexicon_path = tmp_path / 'tts-lexicon.json'
    write_json(lexicon_path, LEXICON)
    proc = run_cli('--script', str(tmp_path / 'nope.txt'), '--lexicon', str(lexicon_path),
                   '--output-dir', str(tmp_path / 'out'))
    assert proc.returncode == 1
    result = parse_result(proc)
    assert result['success'] is False


def test_invalid_lexicon_exits_1(tmp_path: Path):
    script_path = tmp_path / 'script.txt'
    write_text(script_path, SCRIPT_TEXT)
    lexicon_path = tmp_path / 'tts-lexicon.json'
    write_json(lexicon_path, ['not', 'a', 'map'])
    proc = run_cli('--script', str(script_path), '--lexicon', str(lexicon_path),
                   '--output-dir', str(tmp_path / 'out'))
    assert proc.returncode == 1
    result = parse_result(proc)
    assert result['success'] is False


def test_empty_script_exits_1(tmp_path: Path):
    result = None
    script_path = tmp_path / 'script.txt'
    write_text(script_path, '')
    lexicon_path = tmp_path / 'tts-lexicon.json'
    write_json(lexicon_path, LEXICON)
    proc = run_cli('--script', str(script_path), '--lexicon', str(lexicon_path),
                   '--output-dir', str(tmp_path / 'out'))
    assert proc.returncode == 1
    assert parse_result(proc)['success'] is False
