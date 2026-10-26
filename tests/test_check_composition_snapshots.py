"""Recorded-snapshot CLI tests that never require or launch Chrome."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / 'scripts' / 'check-composition.py'
FIXTURE = REPO_ROOT / 'tests' / 'fixtures' / 'check_composition_snapshots.json'

LAYOUT = {
    'canvas': {'width': 1000, 'height': 1000},
    'regions': [
        {
            'id': 'main',
            'kind': 'content',
            'rect': {'x': 0, 'y': 0, 'width': 1000, 'height': 1000},
        },
        {
            'id': 'caption-bar',
            'kind': 'reserved',
            'rect': {'x': 900, 'y': 900, 'width': 100, 'height': 100},
            'component': 'caption-bar',
        },
    ],
}


def test_recorded_snapshots_cover_three_findings_without_chrome(tmp_path: Path):
    layout_path = tmp_path / 'layout.json'
    layout_path.write_text(json.dumps(LAYOUT), encoding='utf-8')

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(tmp_path / 'composition-does-not-exist'),
            '--layout', str(layout_path),
            '--min-font-size', '22',
            '--snapshots-from', str(FIXTURE),
            '--chrome-path', '/definitely/no-chrome',
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result['verdict'] == 'fail'
    assert result['viewport'] == {'width': 1000, 'height': 1000}
    assert [scene['scene_id'] for scene in result['scenes_checked']] == [
        'outside', 'reserved', 'overflow'
    ]
    assert [(finding['scene_id'], finding['check']) for finding in result['findings']] == [
        ('outside', 'outside_content_regions'),
        ('reserved', 'reserved_region_intrusion'),
        ('overflow', 'text_overflow'),
    ]
    for finding in result['findings']:
        assert set(finding) == {'scene_id', 'check', 'issue', 'time_s', 'frame'}
        assert finding['issue']
        assert finding['time_s'] == {'outside': 1.0, 'reserved': 2.0, 'overflow': 3.0}[finding['scene_id']]
        assert finding['frame'] is None


def test_snapshots_from_help_marks_test_debug_seam():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), '--help'],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0
    assert '--snapshots-from' in proc.stdout
    assert 'test/debug seam' in proc.stdout
    assert 'skips Chrome' in proc.stdout
