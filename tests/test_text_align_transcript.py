"""Tests for scripts/text_align.py's align.json -> transcript.json conversion seam.

The seam is the CLI: ``--align-json <in> --emit-transcript <out>`` performs a
pure schema conversion (no model load): the mlx aligner's seconds-based
align.json becomes the pipeline transcript schema (sentence list, all times in
milliseconds). Repo convention: stdout = one JSON, exit codes 0 / 1 / 2.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / 'scripts' / 'text_align.py'

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


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


def parse_stdout(proc: subprocess.CompletedProcess) -> dict:
    """stdout must be exactly one parseable JSON document."""
    return json.loads(proc.stdout)


def write_align_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')


def test_convert_align_json_to_transcript(tmp_path: Path):
    src = tmp_path / 'narration.align.json'
    out = tmp_path / 'transcript.json'
    write_align_json(src, ALIGN_JSON)
    proc = run_cli('--align-json', str(src), '--emit-transcript', str(out))
    assert proc.returncode == 0, proc.stderr
    result = parse_stdout(proc)
    assert result['success'] is True
    transcript = json.loads(out.read_text(encoding='utf-8'))
    assert transcript == EXPECTED_TRANSCRIPT


def test_word_timestamps_are_integer_milliseconds(tmp_path: Path):
    src = tmp_path / 'narration.align.json'
    out = tmp_path / 'transcript.json'
    write_align_json(src, ALIGN_JSON)
    proc = run_cli('--align-json', str(src), '--emit-transcript', str(out))
    assert proc.returncode == 0, proc.stderr
    transcript = json.loads(out.read_text(encoding='utf-8'))
    for sentence in transcript:
        assert set(sentence) == {'begin', 'end', 'text', 'words'}
        for field in ('begin', 'end'):
            assert isinstance(sentence[field], int)
        for word in sentence['words']:
            assert set(word) == {'text', 'begin', 'end'}
            assert isinstance(word['begin'], int)
            assert isinstance(word['end'], int)


def test_empty_alignment_exits_1(tmp_path: Path):
    src = tmp_path / 'narration.align.json'
    out = tmp_path / 'transcript.json'
    write_align_json(src, {'audio': 'x.wav', 'language': 'Chinese', 'words': [], 'sentences': []})
    proc = run_cli('--align-json', str(src), '--emit-transcript', str(out))
    assert proc.returncode == 1
    result = parse_stdout(proc)
    assert result['success'] is False
    assert not out.exists()


def test_missing_align_json_exits_1(tmp_path: Path):
    out = tmp_path / 'transcript.json'
    proc = run_cli(
        '--align-json', str(tmp_path / 'nope.json'), '--emit-transcript', str(out)
    )
    assert proc.returncode == 1
    result = parse_stdout(proc)
    assert result['success'] is False
    assert not out.exists()


def test_invalid_align_json_exits_1(tmp_path: Path):
    src = tmp_path / 'narration.align.json'
    out = tmp_path / 'transcript.json'
    src.write_text('{"words": [', encoding='utf-8')  # truncated JSON
    proc = run_cli('--align-json', str(src), '--emit-transcript', str(out))
    assert proc.returncode == 1
    result = parse_stdout(proc)
    assert result['success'] is False
    assert not out.exists()


def test_conversion_needs_no_audio_or_model(tmp_path: Path):
    """--align-json/--emit-transcript must not require --audio or a model dir."""
    src = tmp_path / 'narration.align.json'
    out = tmp_path / 'transcript.json'
    write_align_json(src, ALIGN_JSON)
    proc = run_cli('--align-json', str(src), '--emit-transcript', str(out))
    assert proc.returncode == 0, proc.stderr
    assert 'audio not found' not in proc.stderr
    assert 'model not found' not in proc.stderr
