"""Check script commands and local references written in user-facing docs."""
from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_FILES = [
    REPO_ROOT / 'SKILL.md',
    *sorted((REPO_ROOT / 'references').glob('**/*.md')),
    *sorted((REPO_ROOT / 'modules').glob('**/*.md')),
]
SCRIPT_REFERENCE = re.compile(r'(?<![\w./-])(scripts/[\w-]+\.(?:py|sh))\b')
SCRIPT_ARGUMENT = re.compile(r'(?<![\w-])(--[a-z][a-z0-9-]*)')
LOCAL_REFERENCE = re.compile(r'`((?:references|modules)/[^`]+)`')
MODULE_RELATIVE_REFERENCE = re.compile(
    r'`((?:designs|layouts|components|transitions|templates|patterns)/[^`\s]+)`'
)
PLACEHOLDER_CHARACTERS = frozenset('<{*')


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


def test_documented_scripts_arguments_and_paths_exist():
    assert DOC_FILES, 'no doc files matched'
    script_sources: dict[Path, str] = {}
    failures: list[str] = []

    for doc_path in DOC_FILES:
        rel_doc = doc_path.relative_to(REPO_ROOT)
        for line_number, line in logical_lines(doc_path):
            for script_match in SCRIPT_REFERENCE.finditer(line):
                relative_script = script_match.group(1)
                script_path = REPO_ROOT / relative_script
                if not script_path.is_file():
                    failures.append(f'{rel_doc}:{line_number}: missing script {relative_script}')
                    continue
                source = script_sources.setdefault(
                    script_path, script_path.read_text(encoding='utf-8')
                )
                for argument in SCRIPT_ARGUMENT.findall(line[script_match.end():]):
                    if argument not in source:
                        failures.append(
                            f'{rel_doc}:{line_number}: {relative_script} does not define {argument}'
                        )

            for match in LOCAL_REFERENCE.finditer(line):
                relative_path = match.group(1)
                if PLACEHOLDER_CHARACTERS.intersection(relative_path):
                    continue
                if not (REPO_ROOT / relative_path).exists():
                    failures.append(f'{rel_doc}:{line_number}: missing path {relative_path}')

            if doc_path.is_relative_to(REPO_ROOT / 'modules'):
                for match in MODULE_RELATIVE_REFERENCE.finditer(line):
                    relative_path = match.group(1)
                    if PLACEHOLDER_CHARACTERS.intersection(relative_path):
                        continue
                    if not (REPO_ROOT / 'modules' / relative_path).exists():
                        failures.append(f'{rel_doc}:{line_number}: missing module path {relative_path}')

    assert not failures, '\n'.join(failures)


# A delegated agent reads its delegation package, not the main agent's phase
# docs, so what it needs must live in the package itself.
DELEGATION_DOCS = sorted((REPO_ROOT / 'references' / 'delegation').glob('**/*.md'))
PHASE_DOCS = sorted((REPO_ROOT / 'references' / 'phases').glob('*.md'))
PAPER_PARSE_DOC = 'references/phases/02-paper-parse.md'
CATALOG_DOC = 'references/phases/05-material-catalog.md'


def test_phase_and_delegation_docs_keep_package_boundaries():
    assert DELEGATION_DOCS, 'no delegation docs found'
    assert PHASE_DOCS, 'no phase docs found'

    violations: list[str] = []
    for doc_path in [*DELEGATION_DOCS, *PHASE_DOCS]:
        if doc_path.name == '02-paper-parse.md':
            continue
        if '02-paper-parse' in doc_path.read_text(encoding='utf-8'):
            violations.append(f'{doc_path.relative_to(REPO_ROOT)} points at {PAPER_PARSE_DOC}')

    for doc_path in DELEGATION_DOCS:
        if '05-material-catalog' in doc_path.read_text(encoding='utf-8'):
            violations.append(f'{doc_path.relative_to(REPO_ROOT)} points at {CATALOG_DOC}')

    assert not violations, '\n'.join(violations)
