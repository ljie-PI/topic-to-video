"""Check script commands and local references written in user-facing docs."""
from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_FILES = [
    REPO_ROOT / 'SKILL.md',
    *sorted((REPO_ROOT / 'references').glob('**/*.md')),
    *sorted((REPO_ROOT / 'modules').glob('**/*.md')),
]
SCRIPT_REFERENCE = re.compile(r'(?<![\w./-])(scripts/[\w-]+\.(?:py|sh))\b')
SCRIPT_ARGUMENT = re.compile(r'(?<![\w-])(--[a-z][a-z0-9-]*)')
LOCAL_REFERENCE = re.compile(r'`((?:references|modules)/[^`]+)`')
PLACEHOLDER_CHARACTERS = frozenset('<{*')


def test_doc_globs_match_at_least_one_file():
    # Parametrized over these lists, an empty glob silently runs zero tests.
    assert DOC_FILES, 'no doc files matched'
    assert DELEGATION_DOCS, 'no delegation docs found'
    assert PHASE_DOCS, 'no phase docs found'


def logical_lines(path: Path) -> Iterator[tuple[int, str]]:
    """Join backslash-continued shell commands into single logical lines."""
    pending = ''
    start_line = 1
    for line_number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        stripped = line.rstrip()
        if not pending:
            start_line = line_number
        if stripped.endswith('\\'):
            pending += stripped[:-1] + ' '
        else:
            yield start_line, pending + line
            pending = ''
    if pending:
        yield start_line, pending


@pytest.mark.parametrize('doc_path', DOC_FILES, ids=lambda path: str(path.relative_to(REPO_ROOT)))
def test_documented_scripts_arguments_and_paths_exist(doc_path: Path):
    failures: list[str] = []
    for line_number, line in logical_lines(doc_path):
        for script_match in SCRIPT_REFERENCE.finditer(line):
            relative_script = script_match.group(1)
            script_path = REPO_ROOT / relative_script
            if not script_path.is_file():
                failures.append(f'line {line_number}: missing script {relative_script}')
                continue
            source = script_path.read_text(encoding='utf-8')
            for argument in SCRIPT_ARGUMENT.findall(line[script_match.end():]):
                if argument not in source:
                    failures.append(
                        f'line {line_number}: {relative_script} does not define {argument}'
                    )

        for match in LOCAL_REFERENCE.finditer(line):
            relative_path = match.group(1)
            if PLACEHOLDER_CHARACTERS.intersection(relative_path):
                continue
            if not (REPO_ROOT / relative_path).exists():
                failures.append(f'line {line_number}: missing path {relative_path}')

    assert not failures, f'{doc_path.relative_to(REPO_ROOT)}:\n' + '\n'.join(failures)


# A delegated agent reads its delegation package, not the main agent's phase
# docs, so what it needs must live in the package itself.
DELEGATION_DOCS = sorted((REPO_ROOT / 'references' / 'delegation').glob('**/*.md'))
PHASE_DOCS = sorted((REPO_ROOT / 'references' / 'phases').glob('*.md'))
PAPER_PARSE_DOC = 'references/phases/02-paper-parse.md'
CATALOG_DOC = 'references/phases/05-material-catalog.md'


@pytest.mark.parametrize(
    'doc_path',
    [path for path in [*DELEGATION_DOCS, *PHASE_DOCS] if path.name != '02-paper-parse.md'],
    ids=lambda path: str(path.relative_to(REPO_ROOT)),
)
def test_paper_parse_doc_is_referenced_by_no_other_phase_or_delegation_doc(doc_path: Path):
    text = doc_path.read_text(encoding='utf-8')
    assert '02-paper-parse' not in text, f'{doc_path.relative_to(REPO_ROOT)} points at {PAPER_PARSE_DOC}'


@pytest.mark.parametrize('doc_path', DELEGATION_DOCS, ids=lambda path: str(path.relative_to(REPO_ROOT)))
def test_delegation_docs_do_not_point_at_the_catalog_phase_doc(doc_path: Path):
    text = doc_path.read_text(encoding='utf-8')
    assert '05-material-catalog' not in text, f'{doc_path.relative_to(REPO_ROOT)} points at {CATALOG_DOC}'
