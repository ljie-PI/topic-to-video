"""Integration tests for scripts/prepare-handoff.py.

The test seam is the script's command line (repo convention: stdout = one
JSON document, exit codes 0 / 1 / 2) plus the files it leaves in the
workspace. Fixture workspaces are built in tmp dirs; the skill root is the
repository itself (the script locates it from its own path).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / 'scripts' / 'prepare-handoff.py'

SECTIONS = ['Coding Agent', 'Inputs', 'Outputs', 'Required References', 'Additional Instructions']

INPUTS = {
    'source': 'https://example.com/article',
    'input_mode': 'standard',
    'duration': '5min',
    'language': 'zh',
    'orientation': 'landscape',
    'template': None,
    'design': 'github',
    'layout': 'presenter',
    'coding_agent': 'claude-code',
    'fetch_materials': True,
}


def write(path: Path, text: str = 'x') -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def make_workspace(tmp_path: Path, step: str = 'script', **overrides) -> Path:
    """A workspace holding exactly the inputs the step's handoff points at."""
    ws = (tmp_path / 'ws' / 'demo-topic').resolve()
    inputs = {**INPUTS, **overrides}
    write(ws / 'inputs.json', json.dumps(inputs, ensure_ascii=False))
    write(ws / 'research-brief.md', '# brief\n')
    if inputs['fetch_materials']:
        write(ws / 'material-catalog.json', '{"entries": []}')
    if step == 'composition':
        write(ws / 'script.txt', '甲\n\n乙\n')
        write(ws / 'scene-plan.json', '[]')
        write(ws / 'voice_clone' / 'narration.mp3')
        write(ws / 'transcribe' / 'subtitle-units.json', '{"units": []}')
        write(ws / 'transcribe' / 'timeline.json', '{"paragraphs": []}')
    return ws


def run_cli(*args: str, env: dict[str, str] | None = None, script: Path = SCRIPT) -> tuple[subprocess.CompletedProcess, dict]:
    proc = subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )
    lines = proc.stdout.splitlines()
    assert len(lines) == 1, f'expected one stdout line, got {proc.stdout!r}\nstderr: {proc.stderr}'
    return proc, json.loads(lines[0])


def prepare(ws: Path, step: str, *args: str, **kwargs) -> dict:
    proc, result = run_cli(str(ws), step, *args, **kwargs)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert result['success'] is True
    return result


def handoff_sections(text: str) -> dict[str, str]:
    """Section title -> body, for the '## ' headings of a handoff."""
    parts = re.split(r'^## (.+)$', text, flags=re.MULTILINE)
    return {title.strip(): body.strip() for title, body in zip(parts[1::2], parts[2::2])}


class TestScriptHandoff:
    def test_writes_handoff_and_returns_the_dispatch_prompt(self, tmp_path: Path):
        ws = make_workspace(tmp_path)

        result = prepare(ws, 'script')

        handoff = ws / 'script-handoff.md'
        assert result['handoff_path'] == str(handoff)
        assert result['dispatch_prompt'] == f'读取 {handoff} 并按它执行；完成后报告产物路径。'
        assert result['fonts'] is None
        text = handoff.read_text(encoding='utf-8')
        assert text.startswith('# script-handoff — demo-topic')
        assert list(handoff_sections(text)) == SECTIONS
        assert '{{' not in text and '}}' not in text


ABSOLUTE_PATH = re.compile(r'(?:(?<=[\s`（(、，；：])|^)(/[^\s`，。；：、（）()]+)', re.MULTILINE)


def absolute_paths(text: str) -> set[Path]:
    return {Path(match.rstrip('/')) for match in ABSOLUTE_PATH.findall(text)}


def pointed_at_paths_that_do_not_exist(text: str) -> set[Path]:
    """Absolute paths in a handoff that are missing on disk.

    The skill's venv is part of the environment, not of the repository, so the
    activate script is not required to exist.
    """
    return {
        path for path in absolute_paths(text)
        if not path.exists() and path.parts[-3:] != ('.venv', 'bin', 'activate')
    }


class TestHandoffContent:
    def test_every_absolute_path_exists_except_the_products_the_agent_writes(self, tmp_path: Path):
        ws = make_workspace(tmp_path, template='github')
        prepare(ws, 'script')

        text = (ws / 'script-handoff.md').read_text(encoding='utf-8')

        assert pointed_at_paths_that_do_not_exist(text) == {
            ws / 'script.txt',
            ws / 'tts-lexicon.json',
            ws / 'scene-plan.json',
            ws / 'narration.txt',
            ws / 'narration-offsets.json',
        }

    def test_commands_run_the_skills_scripts_by_absolute_path(self, tmp_path: Path):
        ws = make_workspace(tmp_path)
        prepare(ws, 'script')

        text = (ws / 'script-handoff.md').read_text(encoding='utf-8')

        assert f'source {REPO_ROOT}/.venv/bin/activate && python3 {REPO_ROOT}/scripts/make-narration.py' in text
        assert 'python3 scripts/' not in text

    def test_coding_agent_comes_from_inputs(self, tmp_path: Path):
        ws = make_workspace(tmp_path, coding_agent='codex')
        prepare(ws, 'script')

        sections = handoff_sections((ws / 'script-handoff.md').read_text(encoding='utf-8'))

        assert sections['Coding Agent'] == 'codex'

    def test_research_brief_is_a_required_path_and_the_catalog_follows_fetch_materials(self, tmp_path: Path):
        ws = make_workspace(tmp_path, fetch_materials=False)
        prepare(ws, 'script')

        inputs = handoff_sections((ws / 'script-handoff.md').read_text(encoding='utf-8'))['Inputs']

        assert f'- research-brief.md：{ws}/research-brief.md' in inputs
        assert '无（fetch_materials = false' in inputs
        assert 'material-catalog.json）' not in inputs


class TestRequiredReferences:
    def test_references_are_numbered_in_overlay_order_with_the_template_item(self, tmp_path: Path):
        ws = make_workspace(tmp_path, template='github')
        prepare(ws, 'script')

        body = handoff_sections((ws / 'script-handoff.md').read_text(encoding='utf-8'))['Required References']

        items = re.findall(r'^\d+\. (.+)$', body, flags=re.MULTILINE)
        assert [absolute_paths(item) for item in items] == [
            {ws / 'references' / 'delegation' / 'script' / 'base-instructions.md'},
            {REPO_ROOT / 'modules' / 'templates' / 'github' / 'narration.md'},
        ]

    def test_null_template_drops_the_template_item(self, tmp_path: Path):
        ws = make_workspace(tmp_path, template=None)
        prepare(ws, 'script')

        body = handoff_sections((ws / 'script-handoff.md').read_text(encoding='utf-8'))['Required References']

        assert re.findall(r'^(\d+)\. ', body, flags=re.MULTILINE) == ['1']
        assert 'modules/templates' not in body


class TestAdditionalInstructions:
    def test_none_when_no_instruction_file_exists(self, tmp_path: Path):
        ws = make_workspace(tmp_path)
        prepare(ws, 'script')

        sections = handoff_sections((ws / 'script-handoff.md').read_text(encoding='utf-8'))

        assert sections['Additional Instructions'] == 'None'

    def test_lists_the_instruction_file_that_exists(self, tmp_path: Path):
        ws = make_workspace(tmp_path)
        write(ws / 'narration-instructions.md', '结尾不要 CTA')
        write(ws / 'composition-instructions.md', 'not for the script step')
        prepare(ws, 'script')

        sections = handoff_sections((ws / 'script-handoff.md').read_text(encoding='utf-8'))

        assert sections['Additional Instructions'] == f'- {ws}/narration-instructions.md'


class TestMaterialization:
    def test_script_package_and_conventions_are_copied_without_modules(self, tmp_path: Path):
        ws = make_workspace(tmp_path)

        result = prepare(ws, 'script')

        delegation = ws / 'references' / 'delegation'
        source = REPO_ROOT / 'references' / 'delegation'
        assert (delegation / 'conventions.md').read_bytes() == (source / 'conventions.md').read_bytes()
        for name in ('base-instructions.md', 'handoff-template.md'):
            assert (delegation / 'script' / name).read_bytes() == (source / 'script' / name).read_bytes()
        assert not (delegation / 'composition').exists()
        assert not (ws / 'modules').exists()
        assert not (ws / 'composition').exists()
        assert result['materialized'] == [str(delegation / 'conventions.md'), str(delegation / 'script')]

    def test_rerun_keeps_an_edited_copy_and_refresh_restores_it(self, tmp_path: Path):
        ws = make_workspace(tmp_path)
        prepare(ws, 'script')
        copy = ws / 'references' / 'delegation' / 'script' / 'base-instructions.md'
        copy.write_text('edited by the user', encoding='utf-8')

        rerun = prepare(ws, 'script')

        assert copy.read_text(encoding='utf-8') == 'edited by the user'
        assert rerun['materialized'] == []

        refreshed = prepare(ws, 'script', '--refresh')

        source = REPO_ROOT / 'references' / 'delegation' / 'script' / 'base-instructions.md'
        assert copy.read_bytes() == source.read_bytes()
        assert str(ws / 'references' / 'delegation' / 'script') in refreshed['materialized']

    def test_rerun_fills_in_a_missing_file_without_touching_the_others(self, tmp_path: Path):
        ws = make_workspace(tmp_path)
        prepare(ws, 'script')
        package = ws / 'references' / 'delegation' / 'script'
        (package / 'handoff-template.md').unlink()
        (package / 'base-instructions.md').write_text('edited', encoding='utf-8')

        rerun = prepare(ws, 'script')

        assert (package / 'handoff-template.md').is_file()
        assert (package / 'base-instructions.md').read_text(encoding='utf-8') == 'edited'
        assert rerun['materialized'] == [str(package)]


COMPOSITION_PRODUCTS = {
    'composition/storyboard.md',
    'composition/index.html',
    'composition/compositions',
    'composition/check-composition.json',
    'composition/renders/final.mp4',
}


class TestCompositionHandoff:
    def test_writes_a_five_section_handoff_of_absolute_paths(self, tmp_path: Path):
        ws = make_workspace(tmp_path, 'composition', template='github')

        result = prepare(ws, 'composition')

        handoff = ws / 'composition-handoff.md'
        assert result['handoff_path'] == str(handoff)
        assert result['dispatch_prompt'] == f'读取 {handoff} 并按它执行；完成后报告产物路径。'
        text = handoff.read_text(encoding='utf-8')
        assert text.startswith('# composition-handoff — demo-topic')
        assert list(handoff_sections(text)) == SECTIONS
        assert '{{' not in text and '}}' not in text
        assert pointed_at_paths_that_do_not_exist(text) == {ws / product for product in COMPOSITION_PRODUCTS}

    def test_commands_use_the_workspace_copies_of_layout_and_design(self, tmp_path: Path):
        ws = make_workspace(tmp_path, 'composition', design='default', layout='stage')
        prepare(ws, 'composition')

        text = (ws / 'composition-handoff.md').read_text(encoding='utf-8')

        assert f'cd {ws}/composition && npx hyperframes check' in text
        assert f'source {REPO_ROOT}/.venv/bin/activate && python3 {REPO_ROOT}/scripts/check-composition.py' in text
        assert f'--layout {ws}/modules/layouts/stage.json' in text
        assert f'--design-doc {ws}/modules/designs/default/default.md' in text
        assert f'--output {ws}/composition/check-composition.json' in text
        assert 'python3 scripts/' not in text

    def test_documented_options_of_the_commands_exist_in_the_scripts(self, tmp_path: Path):
        ws = make_workspace(tmp_path, 'composition')
        prepare(ws, 'composition')
        prepare(ws, 'script')

        checked: set[str] = set()
        for handoff in ('composition-handoff.md', 'script-handoff.md'):
            text = (ws / handoff).read_text(encoding='utf-8').replace('\\\n', ' ')
            for script, tail in re.findall(r'scripts/([\w-]+\.py)((?: +\S+)+)', text):
                source = (REPO_ROOT / 'scripts' / script).read_text(encoding='utf-8')
                # The tail may start with a positional argument (check-composition's
                # composition dir), so match option/value pairs anywhere in it.
                options = re.findall(r'(--[\w-]+) +\S+', tail)
                assert options, f'{handoff}: scripts/{script} documents no options at all'
                checked.add(script)
                for option in options:
                    assert f"'{option}'" in source, f'{handoff}: scripts/{script} has no {option}'
        assert 'check-composition.py' in checked  # the positional-first command is covered
        assert 'make-narration.py' in checked

    def test_inputs_section_lists_the_catalog_only_when_materials_are_fetched(self, tmp_path: Path):
        ws = make_workspace(tmp_path, 'composition', fetch_materials=False)
        prepare(ws, 'composition')

        inputs = handoff_sections((ws / 'composition-handoff.md').read_text(encoding='utf-8'))['Inputs']

        assert '- material-catalog.json：无（' in inputs
        assert f'design github、layout presenter、template 无、orientation landscape' in inputs

    def test_required_references_follow_the_overlay_order(self, tmp_path: Path):
        ws = make_workspace(tmp_path, 'composition', template='github', design='producthunt', layout='portrait', orientation='portrait')
        prepare(ws, 'composition')

        body = handoff_sections((ws / 'composition-handoff.md').read_text(encoding='utf-8'))['Required References']

        items = re.findall(r'^\d+\. (.+)$', body, flags=re.MULTILINE)

        def rel(paths: set[Path]) -> list[str]:
            out = []
            for path in paths:
                if path.is_relative_to(ws):
                    out.append(str(path.relative_to(ws)))
                else:
                    out.append(f'skill:{path.relative_to(REPO_ROOT)}')
            return sorted(out)

        assert [rel(absolute_paths(item)) for item in items] == [
            ['references/delegation/composition/base-instructions.md'],
            ['modules/modules.md'],
            ['modules/designs/designs.md', 'modules/designs/producthunt/producthunt.md'],
            ['modules/layouts/portrait.json', 'modules/layouts/portrait.md'],
            ['modules/templates/github/github.md'],
            ['modules/components', 'modules/patterns'],
            ['skill:modules/examples'],
        ]
        assert items[-2].startswith('按 storyboard 需要，自行阅读 ')
        assert 'github-trending' in items[-1] and 'jay-actions' in items[-1]

    def test_null_template_drops_the_template_item(self, tmp_path: Path):
        ws = make_workspace(tmp_path, 'composition', template=None)
        prepare(ws, 'composition')

        body = handoff_sections((ws / 'composition-handoff.md').read_text(encoding='utf-8'))['Required References']

        # base, modules.md, design, layout, patterns/components, examples
        assert len(re.findall(r'^\d+\. ', body, flags=re.MULTILINE)) == 6
        assert 'modules/templates' not in body

    def test_additional_instructions_list_the_existing_files(self, tmp_path: Path):
        ws = make_workspace(tmp_path, 'composition')
        write(ws / 'narration-instructions.md', 'script step only')

        prepare(ws, 'composition')
        none = handoff_sections((ws / 'composition-handoff.md').read_text(encoding='utf-8'))['Additional Instructions']
        write(ws / 'composition-instructions.md', '深色')
        write(ws / 'style-prompt.md', '旧项目')
        prepare(ws, 'composition')
        listed = handoff_sections((ws / 'composition-handoff.md').read_text(encoding='utf-8'))['Additional Instructions']

        assert none == 'None'
        assert listed == f'- {ws}/composition-instructions.md\n- {ws}/style-prompt.md'


class TestCompositionMaterialization:
    def test_modules_are_copied_without_examples(self, tmp_path: Path):
        ws = make_workspace(tmp_path, 'composition')

        result = prepare(ws, 'composition')

        modules = ws / 'modules'
        assert (modules / 'modules.md').read_bytes() == (REPO_ROOT / 'modules' / 'modules.md').read_bytes()
        assert (modules / 'layouts' / 'presenter.json').is_file()
        assert (modules / 'components' / 'jay' / 'jay.html').is_file()
        assert not (modules / 'examples').exists()
        delegation = ws / 'references' / 'delegation'
        assert (delegation / 'conventions.md').is_file()
        assert (delegation / 'composition' / 'base-instructions.md').is_file()
        assert not (delegation / 'script').exists()
        assert result['materialized'] == [
            str(delegation / 'conventions.md'),
            str(delegation / 'composition'),
            str(modules),
        ]

    def test_rerun_keeps_an_edited_modules_copy_and_refresh_restores_it(self, tmp_path: Path):
        ws = make_workspace(tmp_path, 'composition')
        prepare(ws, 'composition')
        layout = ws / 'modules' / 'layouts' / 'presenter.json'
        layout.write_text('{"edited": true}', encoding='utf-8')

        rerun = prepare(ws, 'composition')

        assert layout.read_text(encoding='utf-8') == '{"edited": true}'
        assert rerun['materialized'] == []

        refreshed = prepare(ws, 'composition', '--refresh')

        assert layout.read_bytes() == (REPO_ROOT / 'modules' / 'layouts' / 'presenter.json').read_bytes()
        assert str(ws / 'modules') in refreshed['materialized']


class TestFonts:
    def test_installs_the_selected_designs_fonts_without_network(self, tmp_path: Path):
        ws = make_workspace(tmp_path, 'composition', design='producthunt')

        result = prepare(ws, 'composition', env={'FONTS_CSS2_URL': 'http://127.0.0.1:9/css2'})

        fonts = ws / 'composition' / 'assets' / 'fonts'
        css = (fonts / 'producthunt-fonts.css').read_text(encoding='utf-8')
        assert result['fonts']['success'] is True
        assert result['fonts']['output_dir'] == str(fonts)
        # A summary, not the ~100-file list: the main agent only dispatches the prompt.
        assert result['fonts']['installed'] and result['fonts']['installed'] > 0
        assert 'files' not in result['fonts']
        for reference in re.findall(r'url\(([^)]+)\)', css):
            assert (fonts / reference).is_file()

    def test_every_run_installs_fonts_again_even_without_refresh(self, tmp_path: Path):
        ws = make_workspace(tmp_path, 'composition')
        prepare(ws, 'composition')
        fonts = ws / 'composition' / 'assets' / 'fonts'
        stale = next(fonts.glob('*.woff2'))
        stale.unlink()

        prepare(ws, 'composition')

        assert stale.is_file()

    def test_fonts_failure_exits_1_with_the_fonts_error(self, tmp_path: Path):
        ws = make_workspace(tmp_path, 'composition')
        empty_resources = tmp_path / 'no-fonts'
        empty_resources.mkdir()

        proc, result = run_cli(str(ws), 'composition', env={'FONTS_RESOURCES_DIR': str(empty_resources)})

        assert proc.returncode == 1, proc.stderr
        assert result['success'] is False
        assert result['fonts']['success'] is False
        assert 'no vendored fonts for theme github' in result['fonts']['error']
        assert result['error'] == result['fonts']['error']
        assert not (ws / 'composition-handoff.md').exists()


class TestFailures:
    def test_unknown_step_is_a_bad_argument(self, tmp_path: Path):
        ws = make_workspace(tmp_path)

        proc, result = run_cli(str(ws), 'catalog')

        assert proc.returncode == 2
        assert result['success'] is False
        assert not (ws / 'catalog-handoff.md').exists()

    def test_missing_arguments_are_bad_arguments(self):
        proc, result = run_cli()

        assert proc.returncode == 2
        assert result['success'] is False

    def test_workspace_must_exist(self, tmp_path: Path):
        proc, result = run_cli(str(tmp_path / 'nowhere'), 'script')

        assert proc.returncode == 1
        assert result['success'] is False
        assert 'workspace is not a directory' in result['error']

    @pytest.mark.parametrize('inputs_text, message', [
        (None, 'inputs.json not found'),
        ('{not json', 'not valid JSON'),
        ('[]', 'not an object'),
        ('{"coding_agent": "claude-code"}', 'missing fields'),
    ])
    def test_unusable_inputs_json_exits_1(self, tmp_path: Path, inputs_text: str | None, message: str):
        ws = make_workspace(tmp_path)
        (ws / 'inputs.json').unlink()
        if inputs_text is not None:
            write(ws / 'inputs.json', inputs_text)

        proc, result = run_cli(str(ws), 'script')

        assert proc.returncode == 1
        assert result['success'] is False
        assert message in result['error']

    def test_missing_input_exits_1_before_touching_the_workspace(self, tmp_path: Path):
        ws = make_workspace(tmp_path, 'composition')
        (ws / 'transcribe' / 'timeline.json').unlink()

        proc, result = run_cli(str(ws), 'composition')

        assert proc.returncode == 1
        assert result['success'] is False
        assert str(ws / 'transcribe' / 'timeline.json') in result['error']
        assert not (ws / 'composition-handoff.md').exists()
        assert not (ws / 'modules').exists()
        assert not (ws / 'composition').exists()

    def test_the_script_step_requires_the_research_brief(self, tmp_path: Path):
        ws = make_workspace(tmp_path)
        (ws / 'research-brief.md').unlink()

        proc, result = run_cli(str(ws), 'script')

        assert proc.returncode == 1
        assert str(ws / 'research-brief.md') in result['error']

    def test_a_catalog_is_required_only_when_materials_are_fetched(self, tmp_path: Path):
        ws = make_workspace(tmp_path)
        (ws / 'material-catalog.json').unlink()

        proc, result = run_cli(str(ws), 'script')

        assert proc.returncode == 1
        assert str(ws / 'material-catalog.json') in result['error']

    def test_unknown_template_exits_1(self, tmp_path: Path):
        ws = make_workspace(tmp_path, template='no-such-template')

        proc, result = run_cli(str(ws), 'script')

        assert proc.returncode == 1
        assert 'no-such-template' in result['error']

    def test_unknown_layout_exits_1_for_composition(self, tmp_path: Path):
        ws = make_workspace(tmp_path, 'composition', layout='no-such-layout')

        proc, result = run_cli(str(ws), 'composition')

        assert proc.returncode == 1
        assert 'no-such-layout.json' in result['error']
        assert not (ws / 'composition-handoff.md').exists()
        # Sources are validated before anything is written.
        assert not (ws / 'references').exists()
        assert not (ws / 'modules').exists()
        assert not (ws / 'composition').exists()

    @pytest.mark.parametrize(
        'overrides, message',
        [
            ({'fetch_materials': 'false'}, 'fetch_materials'),
            ({'duration': '90秒'}, 'duration'),
            ({'duration': {'min': 5}}, 'duration'),
            ({'coding_agent': ''}, 'coding_agent'),
            ({'language': None}, 'language'),
        ],
    )
    def test_field_types_are_validated(self, tmp_path: Path, overrides: dict, message: str):
        ws = make_workspace(tmp_path, **overrides)

        proc, result = run_cli(str(ws), 'script')

        assert proc.returncode == 1
        assert message in result['error']

    def test_a_trailing_newline_in_a_name_is_rejected(self, tmp_path: Path):
        # `re.match` with $ would let 'github\n' through; fullmatch must not.
        ws = make_workspace(tmp_path, design='github\n')

        proc, result = run_cli(str(ws), 'script')

        assert proc.returncode == 1
        assert 'design' in result['error']

    @pytest.mark.parametrize('field', ['design', 'layout', 'template'])
    def test_names_in_inputs_cannot_be_paths(self, tmp_path: Path, field: str):
        ws = make_workspace(tmp_path, **{field: '../escape'})

        proc, result = run_cli(str(ws), 'script')

        assert proc.returncode == 1
        assert field in result['error']


@pytest.fixture
def skill_copy(tmp_path: Path) -> Path:
    """A skill root whose scripts and delegation docs can be edited; modules and fonts are shared."""
    root = tmp_path / 'skill'
    shutil.copytree(REPO_ROOT / 'scripts', root / 'scripts', ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(REPO_ROOT / 'references', root / 'references')
    (root / 'modules').symlink_to(REPO_ROOT / 'modules')
    (root / 'resources').symlink_to(REPO_ROOT / 'resources')
    return root


class TestTemplateErrors:
    def test_an_unreplaced_placeholder_exits_1_and_writes_nothing(self, tmp_path: Path, skill_copy: Path):
        ws = make_workspace(tmp_path)
        template = skill_copy / 'references' / 'delegation' / 'script' / 'handoff-template.md'
        template.write_text(
            template.read_text(encoding='utf-8').replace('## Coding Agent', '## Coding Agent {{no_such_value}}'),
            encoding='utf-8',
        )

        proc, result = run_cli(str(ws), 'script', script=skill_copy / 'scripts' / 'prepare-handoff.py')

        assert proc.returncode == 1
        assert result['success'] is False
        assert 'no_such_value' in result['error']
        assert not (ws / 'script-handoff.md').exists()
        assert not (ws / 'references').exists()

    def test_a_template_without_a_markdown_block_exits_1(self, tmp_path: Path, skill_copy: Path):
        ws = make_workspace(tmp_path)
        (skill_copy / 'references' / 'delegation' / 'script' / 'handoff-template.md').write_text('no block here', encoding='utf-8')

        proc, result = run_cli(str(ws), 'script', script=skill_copy / 'scripts' / 'prepare-handoff.py')

        assert proc.returncode == 1
        assert 'markdown code block' in result['error']

    def test_the_skill_root_is_the_one_the_script_lives_in(self, tmp_path: Path, skill_copy: Path):
        ws = make_workspace(tmp_path)

        prepare(ws, 'script', script=skill_copy / 'scripts' / 'prepare-handoff.py')

        text = (ws / 'script-handoff.md').read_text(encoding='utf-8')
        assert f'source {skill_copy}/.venv/bin/activate && python3 {skill_copy}/scripts/make-narration.py' in text


class TestFontsFailureModes:
    def test_a_fonts_script_that_prints_no_json_still_gives_a_json_error(self, tmp_path: Path, skill_copy: Path):
        ws = make_workspace(tmp_path, 'composition')
        (skill_copy / 'scripts' / 'fonts-download.sh').write_text('echo "boom" >&2\nexit 3\n', encoding='utf-8')

        proc, result = run_cli(str(ws), 'composition', script=skill_copy / 'scripts' / 'prepare-handoff.py')

        assert proc.returncode == 1
        assert result['success'] is False
        assert result['fonts'] == {'success': False, 'error': 'boom'}
        assert result['error'] == 'boom'
        assert not (ws / 'composition-handoff.md').exists()


class TestInputsRendering:
    def test_a_numeric_duration_is_written_in_minutes(self, tmp_path: Path):
        ws = make_workspace(tmp_path, duration=5, language='en', input_mode='paper', template=None)
        prepare(ws, 'script')

        inputs = handoff_sections((ws / 'script-handoff.md').read_text(encoding='utf-8'))['Inputs']

        assert '（目标时长 5 分钟、语言 en、input_mode paper、所选模板 无）' in inputs


class TestReviewRoundFixes:
    """Regressions pinned from the first /code-review round."""

    def test_portrait_3x4_uses_the_shared_portrait_doc(self, tmp_path: Path):
        # portrait-3x4 has only a .json; portrait.md covers both portrait canvases.
        ws = make_workspace(tmp_path, 'composition', layout='portrait-3x4', orientation='portrait')

        prepare(ws, 'composition')

        text = (ws / 'composition-handoff.md').read_text(encoding='utf-8')
        assert f'--layout {ws}/modules/layouts/portrait-3x4.json' in text
        body = handoff_sections(text)['Required References']
        assert f'{ws}/modules/layouts/portrait-3x4.json + {ws}/modules/layouts/portrait.md' in body

    def test_paths_with_spaces_are_quoted_in_commands(self, tmp_path: Path):
        spaced = (tmp_path / 'AI Agents 2026').resolve()
        ws = (spaced / 'ws' / 'demo-topic').resolve()
        write(ws / 'inputs.json', json.dumps(INPUTS, ensure_ascii=False))
        write(ws / 'research-brief.md', '# brief\n')
        write(ws / 'material-catalog.json', '{"entries": []}')
        write(ws / 'script.txt', '甲\n\n乙\n')
        write(ws / 'scene-plan.json', '[]')
        write(ws / 'voice_clone' / 'narration.mp3')
        write(ws / 'transcribe' / 'subtitle-units.json', '{"units": []}')
        write(ws / 'transcribe' / 'timeline.json', '{"paragraphs": []}')

        prepare(ws, 'composition')
        prepare(ws, 'script')

        composition = (ws / 'composition-handoff.md').read_text(encoding='utf-8')
        assert f"cd '{ws}/composition' && npx hyperframes check" in composition
        assert f"--layout '{ws}/modules/layouts/presenter.json'" in composition
        script = (ws / 'script-handoff.md').read_text(encoding='utf-8')
        assert f"--script '{ws}/script.txt'" in script

    def test_copies_do_not_inherit_read_only_source_permissions(self, tmp_path: Path, skill_copy: Path):
        source = skill_copy / 'references' / 'delegation' / 'script' / 'base-instructions.md'
        source.chmod(0o444)
        ws = make_workspace(tmp_path)

        prepare(ws, 'script', script=skill_copy / 'scripts' / 'prepare-handoff.py')

        copy = ws / 'references' / 'delegation' / 'script' / 'base-instructions.md'
        assert copy.stat().st_mode & 0o200  # writable, though the source is read-only
        copy.write_text('edited', encoding='utf-8')
        prepare(ws, 'script', '--refresh', script=skill_copy / 'scripts' / 'prepare-handoff.py')
        assert copy.read_bytes() == source.read_bytes()

    def test_paper_mode_script_handoff_lists_the_paper_parse_doc(self, tmp_path: Path):
        ws = make_workspace(tmp_path, input_mode='paper')

        prepare(ws, 'script')

        body = handoff_sections((ws / 'script-handoff.md').read_text(encoding='utf-8'))['Required References']
        assert f'{REPO_ROOT}/references/phases/02-paper-parse.md' in body

    def test_placeholder_names_allow_uppercase_digits_and_hyphens(self, tmp_path: Path, skill_copy: Path):
        template = skill_copy / 'references' / 'delegation' / 'script' / 'handoff-template.md'
        template.write_text(
            template.read_text(encoding='utf-8').replace('## Coding Agent', '## Coding Agent {{Ws2}}'),
            encoding='utf-8',
        )
        ws = make_workspace(tmp_path)

        proc, result = run_cli(str(ws), 'script', script=skill_copy / 'scripts' / 'prepare-handoff.py')

        assert proc.returncode == 1
        assert 'Ws2' in result['error']  # recognized as a placeholder, reported unreplaced

    def test_a_design_kept_only_in_the_workspace_still_gets_fonts(self, tmp_path: Path, skill_copy: Path):
        # pipeline-status accepts a design removed from the skill when the
        # workspace holds its copy; the handoff must not fail at fonts either.
        (skill_copy / 'modules').unlink()
        gutted = tmp_path / 'gutted-modules'
        shutil.copytree(REPO_ROOT / 'modules', gutted, ignore=shutil.ignore_patterns('github', 'examples'))
        (skill_copy / 'modules').symlink_to(gutted)
        ws = make_workspace(tmp_path, 'composition', design='github')
        copied = ws / 'modules' / 'designs' / 'github'
        shutil.copytree(REPO_ROOT / 'modules' / 'designs' / 'github', copied)

        result = prepare(ws, 'composition', script=skill_copy / 'scripts' / 'prepare-handoff.py')

        assert result['fonts']['success'] is True
        assert (ws / 'composition' / 'assets' / 'fonts' / 'github-fonts.css').is_file()


class TestDelegationDocs:
    """The docs the main agent follows hand it prepare-handoff.py, not a template to fill."""

    @pytest.mark.parametrize('doc, step', [
        ('references/phases/06-script-scene-plan.md', 'script'),
        ('references/phases/08-composition.md', 'composition'),
    ])
    def test_phase_docs_run_prepare_handoff_and_dispatch_its_prompt(self, doc: str, step: str):
        text = (REPO_ROOT / doc).read_text(encoding='utf-8')

        assert f'python3 scripts/prepare-handoff.py {{work_dir}}/{{topic_name}} {step}' in text
        assert 'dispatch_prompt' in text
        assert 'handoff-template.md' not in text

    def test_conventions_grant_the_skill_root_to_headless_agents(self):
        text = (REPO_ROOT / 'references' / 'delegation' / 'conventions.md').read_text(encoding='utf-8')

        assert 'claude -p "<dispatch_prompt>" --add-dir <ws> --add-dir <skill_root>' in text

    def test_composition_instructions_choose_components_before_writing_the_storyboard(self):
        text = (REPO_ROOT / 'references' / 'delegation' / 'composition' / 'base-instructions.md').read_text(encoding='utf-8')

        assert 0 < text.index('modules/components/components.md') < text.index('组件使用表')
        assert 'reserved 区要求的组件必须出现在表里' in text
        assert '由你自己从工作区的 `modules/` 拷进 `composition/`' in text

    def test_script_instructions_report_all_five_products(self):
        text = (REPO_ROOT / 'references' / 'delegation' / 'script' / 'base-instructions.md').read_text(encoding='utf-8')

        assert '五个产物路径' in text
        assert '四个产物路径' not in text

    def test_modules_doc_no_longer_copies_examples_or_previews_for_the_delegated_agent(self):
        text = (REPO_ROOT / 'modules' / 'modules.md').read_text(encoding='utf-8')

        assert '复制 `examples/' not in text
        assert 'npx hyperframes init composition/' in text
        assert 'composition/assets/fonts/' in text
        assert '用 `npx hyperframes preview` 交给用户看' not in text

    def test_modules_doc_initializes_a_fresh_dir_before_fonts_get_in_the_way(self):
        text = (REPO_ROOT / 'modules' / 'modules.md').read_text(encoding='utf-8')

        # The init-into-a-fresh-dir workaround comes before the pre-placed-fonts note.
        assert 'composition-init/' in text
        assert text.index('composition-init/') < text.index('不用再装')

    def test_base_instructions_no_longer_point_at_a_workspace_relative_paper_doc(self):
        text = (REPO_ROOT / 'references' / 'delegation' / 'script' / 'base-instructions.md').read_text(
            encoding='utf-8'
        )

        assert '02-paper-parse' not in text  # the relative path dies in the workspace copy
        assert 'Required References' in text

    def test_conventions_scope_the_script_to_script_and_composition(self):
        text = (REPO_ROOT / 'references' / 'delegation' / 'conventions.md').read_text(encoding='utf-8')

        assert '只支持 `script` 和 `composition`' in text
        assert '重新运行一次 `prepare-handoff.py`' in text
