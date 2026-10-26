"""CLI coverage for SRT/VTT subtitle parsing."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / 'scripts' / 'subtitle-parse.py'


def run_parser(tmp_path: Path, name: str, content: str, *args: str) -> dict:
    subtitle = tmp_path / name
    subtitle.write_text(content, encoding='utf-8')
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), str(subtitle), *args],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert 'Traceback' not in proc.stderr
    assert len(proc.stdout.splitlines()) == 1
    return json.loads(proc.stdout)


def test_srt_outputs_begin_and_end_seconds(tmp_path: Path):
    result = run_parser(
        tmp_path,
        'captions.srt',
        '1\n00:00:01,250 --> 00:00:02,500\nHello <b>world</b>\n',
    )

    assert result['success'] is True
    assert result['entries'] == [
        {
            'index': 1,
            'start_time': '00:00:01.250',
            'end_time': '00:00:02.500',
            'begin_s': 1.25,
            'end_s': 2.5,
            'text': 'Hello world',
        }
    ]


def test_vtt_with_hours(tmp_path: Path):
    result = run_parser(
        tmp_path,
        'captions.vtt',
        'WEBVTT\n\n00:00:01.000 --> 01:02:03.500\nHourly cue\n',
    )

    assert result['entries'][0]['begin_s'] == 1.0
    assert result['entries'][0]['end_s'] == 3723.5
    assert result['entries'][0]['text'] == 'Hourly cue'


def test_vtt_without_hours(tmp_path: Path):
    result = run_parser(
        tmp_path,
        'captions.vtt',
        'WEBVTT\n\n00:01.000 --> 01:02.500\nShort cue\n',
    )

    assert result['entries'][0]['begin_s'] == 1.0
    assert result['entries'][0]['end_s'] == 62.5
    assert result['entries'][0]['text'] == 'Short cue'


def test_vtt_cue_settings_are_not_part_of_timestamp(tmp_path: Path):
    result = run_parser(
        tmp_path,
        'captions.vtt',
        'WEBVTT\n\n00:01.000 --> 00:02.000 align:start position:0%\nAligned cue\n',
    )

    assert result['entries'][0]['begin_s'] == 1.0
    assert result['entries'][0]['end_s'] == 2.0
    assert result['entries'][0]['text'] == 'Aligned cue'


def test_keywords_filter_entries_case_insensitively(tmp_path: Path):
    result = run_parser(
        tmp_path,
        'captions.srt',
        '1\n00:00:01,000 --> 00:00:02,000\nAI changes video\n\n'
        '2\n00:00:03,000 --> 00:00:04,000\nUnrelated cue\n',
        '--keywords',
        'ai',
    )

    assert result['total_entries'] == 2
    assert result['matched_entries'] == 1
    assert [entry['text'] for entry in result['entries']] == ['AI changes video']


def test_malformed_timestamp_warns_and_retains_good_cues(tmp_path: Path):
    result = run_parser(
        tmp_path,
        'captions.vtt',
        'WEBVTT\n\n00:00.000 --> 00:01.000\nKeep me\n\n'
        'not-a-time --> 00:03.000\nDrop me\n\n'
        '00:04.000 --> 00:05.000\nKeep me too\n',
    )

    assert [entry['text'] for entry in result['entries']] == ['Keep me', 'Keep me too']
    assert result['total_entries'] == 2
    assert len(result['warnings']) == 1
    assert 'not-a-time' in result['warnings'][0]
