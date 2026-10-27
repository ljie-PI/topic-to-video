"""Every design JSON supplies the floors check-composition enforces."""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DESIGNS = sorted(
    d for d in (REPO_ROOT / 'modules' / 'designs').iterdir() if (d / f'{d.name}.md').is_file()
)


def load_check_composition():
    spec = importlib.util.spec_from_file_location(
        'check_composition', REPO_ROOT / 'scripts' / 'check-composition.py'
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_design_json_yields_reading_and_ui_floors():
    module = load_check_composition()
    assert [d.name for d in DESIGNS] == ['default', 'github', 'producthunt']
    for design in DESIGNS:
        args = argparse.Namespace(
            min_font_size=None,
            min_ui_font_size=None,
            design=str(design / f'{design.name}.json'),
        )
        assert module.load_font_floors(args) == (26, 22), design.name
