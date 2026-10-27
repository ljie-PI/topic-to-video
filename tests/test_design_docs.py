"""Every design JSON supplies the floors check-composition enforces."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / 'scripts' / 'check-composition.py'
DESIGNS = sorted(
    d for d in (REPO_ROOT / 'modules' / 'designs').iterdir() if (d / f'{d.name}.md').is_file()
)


def test_every_design_json_yields_reading_and_ui_floors(tmp_path: Path):
    snapshots = tmp_path / 'snapshots.json'
    snapshots.write_text('[]', encoding='utf-8')
    assert [d.name for d in DESIGNS] == ['default', 'github', 'producthunt']
    for design in DESIGNS:
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                str(tmp_path),
                '--layout', str(REPO_ROOT / 'modules' / 'layouts' / 'stage.json'),
                '--design', str(design / f'{design.name}.json'),
                '--snapshots-from', str(snapshots),
            ],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stderr
        report = json.loads(proc.stdout)
        assert (report['min_font_size'], report['min_ui_font_size']) == (26, 22), design.name
