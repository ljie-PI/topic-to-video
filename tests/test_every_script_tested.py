"""Require every executable script to have a direct test reference.

The reference gate is deliberately lightweight: it prevents new scripts from
being added without any test suite noticing them.  Line coverage and the
behavioral tests provide the stronger quality checks.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / 'scripts'
TESTS_DIR = REPO_ROOT / 'tests'
EXEMPT = {}


def _test_sources() -> list[tuple[Path, str]]:
    return [
        (path, path.read_text(encoding='utf-8'))
        for path in sorted(TESTS_DIR.glob('test_*.py'))
        if path != Path(__file__)
    ]


def _is_referenced(script: Path, sources: list[tuple[Path, str]]) -> bool:
    for _, source in sources:
        if script.name in source:
            return True
        if script.suffix == '.py':
            module = script.stem
            if re.search(rf'^\s*(?:import\s+{re.escape(module)}(?:\s|$)|from\s+{re.escape(module)}\s+import\s)', source, re.MULTILINE):
                return True
    return False


def test_exemptions_are_empty():
    assert EXEMPT == {}


@pytest.mark.parametrize(
    'script',
    sorted([*SCRIPTS_DIR.glob('*.py'), *SCRIPTS_DIR.glob('*.sh')]),
    ids=lambda path: path.name,
)
def test_every_script_is_referenced_by_a_test(script: Path):
    if script.name in EXEMPT:
        pytest.fail(f'exemptions are not permitted: {script.name}: {EXEMPT[script.name]}')
    assert _is_referenced(script, _test_sources()), (
        f'{script.relative_to(REPO_ROOT)} is not referenced by any tests/test_*.py; '
        'add a behavioral test using its public CLI or import seam'
    )


def test_tests_never_skip():
    forbidden = (
        'pytest.mark.' + 'skip',
        'skip' + 'if',
        'importor' + 'skip',
        'pytest.' + 'skip(',
    )
    violations = []
    for path in sorted(TESTS_DIR.glob('*.py')):
        source = path.read_text(encoding='utf-8')
        for token in forbidden:
            if token in source:
                violations.append(f'{path.relative_to(REPO_ROOT)}: {token}')
    assert not violations, 'tests must fail on missing dependencies, never skip:\n' + '\n'.join(violations)
