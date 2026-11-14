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
    'coding_agent': 'pi-coding-agent',
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
    if inputs['fetch_materials'] and step != 'catalog':
        write(ws / 'material-catalog.json', '{"entries": []}')
    if step == 'catalog':
        write(ws / 'harvest_page' / 'manifest.json', '{"version": 2, "entries": []}')
        write(ws / 'vision_analyze' / 'topic-context.txt', '话题摘要\n')
    if step == 'composition':
        write(ws / 'script.txt', '甲\n\n乙\n')
        write(ws / 'scene-plan.json', '[]')
        write(ws / 'voice_clone' / 'narration.mp3')
        write(ws / 'transcribe' / 'transcript.json', '[]')
        write(ws / 'transcribe' / 'timeline.json', '{"paragraphs": []}')
        write(ws / 'narration.txt', '甲\n\n乙\n')
        write(ws / 'narration-offsets.json', '{"version": 1, "segments": []}')
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


class TestDelegationSelection:
    @pytest.mark.parametrize('step', ['catalog', 'script', 'composition'])
    def test_exact_stage_agent_and_model_reach_handoff_and_dispatch_result(self, tmp_path: Path, step: str):
        ws = make_workspace(
            tmp_path, step, coding_agent='claude-code',
            delegation={step: {'agent': 'pi-coding-agent', 'model': 'provider/exact-model'}},
        )
        result = prepare(ws, step, '--resolved-model', 'provider/exact-model')
        section = handoff_sections((ws / f'{step}-handoff.md').read_text(encoding='utf-8'))['Coding Agent']

        assert result['coding_agent'] == 'pi-coding-agent'
        assert result['coding_model'] == 'provider/exact-model'
        assert result['requested_model'] == 'provider/exact-model'
        assert section.startswith('pi-coding-agent\n')
        assert '请求模型：provider/exact-model；实际模型：provider/exact-model' in section
        assert 'claude-code' not in section

    def test_catalog_selection_does_not_override_script(self, tmp_path: Path):
        ws = make_workspace(tmp_path, delegation={'catalog': {'agent': 'codex', 'model': 'provider/model'}})
        result = prepare(ws, 'script')

        assert result['coding_agent'] == 'pi-coding-agent'
        assert result['coding_model'] is None
        assert result['requested_model'] is None
        assert handoff_sections((ws / 'script-handoff.md').read_text(encoding='utf-8'))['Coding Agent'] == 'pi-coding-agent'

    def test_invalid_model_is_rejected_before_writing_any_handoff(self, tmp_path: Path):
        ws = make_workspace(tmp_path, delegation={'catalog': {'model': ''}})
        proc, result = run_cli(str(ws), 'script')

        assert proc.returncode == 1
        assert 'delegation.catalog.model' in result['error']
        assert not (ws / 'script-handoff.md').exists()
        assert not (ws / 'references').exists()


class TestResolvedModel:
    """--resolved-model 传递目标 CLI 查询出的真实标识：请求留原样，实际值用于派发。

    受控候选：本类测试用注入的 resolved 值模拟目标 CLI 的查询结果（精确、近似、
    空结果），不调用真实 CLI 或付费模型；CLI 查询与近似判断本身是主 agent 按
    references/delegation/conventions.md 执行的步骤。
    """

    def test_an_approximate_candidate_is_adopted_with_request_and_actual_shown(
        self, tmp_path: Path,
    ):
        ws = make_workspace(tmp_path, 'script', delegation={'script': {'model': '模糊的请求名'}})

        result = prepare(ws, 'script', '--resolved-model', 'provider/closest-real-id')

        section = handoff_sections((ws / 'script-handoff.md').read_text(encoding='utf-8'))['Coding Agent']
        assert result['coding_model'] == 'provider/closest-real-id'
        assert result['requested_model'] == '模糊的请求名'
        # handoff、JSON、实际派发的 coding_model 是同一个真实标识；请求与实际同时可见。
        assert '请求模型：模糊的请求名；实际模型：provider/closest-real-id' in section
        assert '模糊的请求名' not in result['dispatch_prompt']

    @pytest.mark.parametrize('step', ['catalog', 'composition'])
    def test_each_step_resolves_its_own_model_without_leaking(self, tmp_path: Path, step: str):
        # 阶段覆盖：catalog 与 composition 分别指定不同模型，互不影响。
        ws = make_workspace(
            tmp_path, step,
            delegation={'catalog': {'model': 'provider/catalog-model'},
                        'composition': {'model': 'provider/composition-model'}},
        )
        resolved = {'catalog': 'provider/catalog-model', 'composition': 'provider/composition-model'}[step]

        result = prepare(ws, step, '--resolved-model', resolved)

        section = handoff_sections((ws / f'{step}-handoff.md').read_text(encoding='utf-8'))['Coding Agent']
        assert result['coding_model'] == resolved
        assert result['requested_model'] == resolved
        assert f'实际模型：{resolved}' in section
        other = 'provider/composition-model' if step == 'catalog' else 'provider/catalog-model'
        assert other not in section

    def test_a_requested_model_without_resolution_is_blocked_before_any_write(self, tmp_path: Path):
        # 有请求但未解析（CLI 无候选 / 不可用 / 候选无法区分）：不生成 handoff。
        ws = make_workspace(tmp_path, 'script', delegation={'script': {'model': '模糊的请求名'}})

        proc, result = run_cli(str(ws), 'script')

        assert proc.returncode == 1
        assert 'requested but not resolved' in result['error']
        assert not (ws / 'script-handoff.md').exists()
        assert not (ws / 'references').exists()

    def test_a_resolved_model_without_a_request_is_rejected(self, tmp_path: Path):
        ws = make_workspace(tmp_path)

        proc, result = run_cli(str(ws), 'script', '--resolved-model', 'provider/exact-model')

        assert proc.returncode == 1
        assert 'no model was requested' in result['error']
        assert not (ws / 'script-handoff.md').exists()
        assert not (ws / 'references').exists()

    def test_a_model_request_stays_in_inputs_after_resolution(self, tmp_path: Path):
        # 原始请求继续留在输入中，prepare-handoff 只读取、不改写它。
        ws = make_workspace(tmp_path, delegation={'script': {'model': '模糊的请求名'}})

        prepare(ws, 'script', '--resolved-model', 'provider/closest-real-id')

        inputs = json.loads((ws / 'inputs.json').read_text(encoding='utf-8'))
        assert inputs['delegation']['script']['model'] == '模糊的请求名'


class TestRequestLists:
    """用户原话进 handoff：不能被当成模板、不能破坏小节结构。"""

    def additional(self, ws: Path, step: str = 'script') -> str:
        return handoff_sections((ws / f'{step}-handoff.md').read_text(encoding='utf-8'))[
            'Additional Instructions'
        ]

    @pytest.mark.parametrize('step, field', [
        ('script', 'narration_requests'),
        ('composition', 'composition_requests'),
    ], ids=['script', 'composition'])
    def test_absent_and_empty_request_lists_write_the_same_section(self, tmp_path: Path, step: str, field: str):
        absent = make_workspace(tmp_path / 'a', step)
        prepare(absent, step)
        empty = make_workspace(tmp_path / 'b', step, **{field: []})
        prepare(empty, step)

        assert self.additional(absent, step) == 'None'
        assert self.additional(empty, step) == 'None'

    def test_literal_braces_in_a_request_survive(self, tmp_path: Path):
        ws = make_workspace(tmp_path, narration_requests=['保留 {{name}} 这种字面量'])

        prepare(ws, 'script')

        # 写入的值不再被当成占位符：literal braces 原样到手。
        assert self.additional(ws) == '- 保留 {{name}} 这种字面量'

    def test_a_multiline_request_stays_one_list_item(self, tmp_path: Path):
        ws = make_workspace(tmp_path, 'composition', composition_requests=['第一句\n第二句\n\n第三句'])

        prepare(ws, 'composition')

        section = self.additional(ws, 'composition')
        assert section == '- 第一句\n  第二句\n  第三句'
        assert list(
            handoff_sections((ws / 'composition-handoff.md').read_text(encoding='utf-8'))
        ) == SECTIONS

    @pytest.mark.parametrize('step, field, initial_requests, updated_requests', [
        ('script', 'narration_requests', ['语气更口语'], ['语气更口语', '结尾不要 CTA']),
        ('composition', 'composition_requests', None, ['深色', '强调实验对比图']),
    ], ids=['script', 'composition'])
    def test_a_request_list_change_reaches_the_handoff(
        self, tmp_path: Path, step: str, field: str,
        initial_requests: list[str] | None, updated_requests: list[str],
    ):
        overrides = {field: initial_requests} if initial_requests is not None else {}
        ws = make_workspace(tmp_path, step, **overrides)
        prepare(ws, step)
        assert self.additional(ws, step) == (
            '\n'.join(f'- {request}' for request in initial_requests) if initial_requests else 'None'
        )

        write(ws / 'inputs.json', json.dumps(
            {**INPUTS, field: updated_requests}, ensure_ascii=False
        ))
        prepare(ws, step)

        assert self.additional(ws, step) == '\n'.join(f'- {request}' for request in updated_requests)

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
        if (
            not path.exists()
            and path.parts[-3:] != ('.venv', 'bin', 'activate')
            and '<design>' not in path.parts
        )
    }


class TestHandoffContent:
    def test_script_handoff_commands_material_refs_and_base_references(self, tmp_path: Path):
        ws = make_workspace(tmp_path, template='github-trending')
        prepare(ws, 'script')

        text = (ws / 'script-handoff.md').read_text(encoding='utf-8')
        sections = handoff_sections(text)

        assert f'source {REPO_ROOT}/.venv/bin/activate && python3 {REPO_ROOT}/scripts/make-narration.py' in text
        assert 'python3 scripts/' not in text
        assert '`<slug>/<id>`' in sections['Outputs']
        assert '`<slug>/<video_id>:<start>-<end>`' in sections['Outputs']

        refs = sections['Required References']
        items = re.findall(r'^\d+\. (.+)$', refs, flags=re.MULTILINE)
        assert [absolute_paths(item) for item in items] == [
            {ws / 'references' / 'delegation' / 'script' / 'base-instructions.md'},
        ]
        assert 'modules/templates' not in refs

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


class TestAdditionalInstructions:
    @pytest.mark.parametrize('step, field, requests, other_field', [
        ('script', 'narration_requests', ['语气更口语', '结尾不要 CTA'], 'composition_requests'),
        ('composition', 'composition_requests', ['深色', '强调实验对比图'], 'narration_requests'),
    ], ids=['script', 'composition'])
    def test_inlines_only_the_steps_requests_and_ignores_old_instruction_files(
        self, tmp_path: Path, step: str, field: str, requests: list[str], other_field: str,
    ):
        ws = make_workspace(
            tmp_path, step, **{field: requests, other_field: ['not for this step']},
        )
        # 旧项目可能还留着这些文件；它们不再被读取。
        for name in ('narration-instructions.md', 'composition-instructions.md', 'style-prompt.md'):
            write(ws / name, '旧文件里的要求')
        prepare(ws, step)

        sections = handoff_sections((ws / f'{step}-handoff.md').read_text(encoding='utf-8'))

        assert sections['Additional Instructions'] == '\n'.join(f'- {request}' for request in requests)


class TestMaterialization:
    @pytest.mark.parametrize('step', ['script', 'catalog'])
    def test_package_and_conventions_are_copied_without_modules_or_fonts(self, tmp_path: Path, step: str):
        ws = make_workspace(tmp_path, step)

        result = prepare(ws, step, env={'FONTS_RESOURCES_DIR': str(tmp_path / 'no-fonts')})

        delegation = ws / 'references' / 'delegation'
        source = REPO_ROOT / 'references' / 'delegation'
        assert (delegation / 'conventions.md').read_bytes() == (source / 'conventions.md').read_bytes()
        for name in ('base-instructions.md', 'handoff-template.md'):
            assert (delegation / step / name).read_bytes() == (source / step / name).read_bytes()
        for other_step in {'catalog', 'script', 'composition'} - {step}:
            assert not (delegation / other_step).exists()
        assert not (ws / 'modules').exists()
        assert not (ws / 'composition').exists()
        assert result['materialized'] == [str(delegation / 'conventions.md'), str(delegation / step)]

    @pytest.mark.parametrize('step, path_parts, unit_parts', [
        ('script', ('references', 'delegation', 'script', 'base-instructions.md'), ('references', 'delegation', 'script')),
        ('catalog', ('references', 'delegation', 'catalog', 'base-instructions.md'), ('references', 'delegation', 'catalog')),
        ('composition', ('modules', 'layouts', 'landscape-presenter.md'), ('modules',)),
    ], ids=['script', 'catalog', 'composition'])
    def test_rerun_keeps_an_edited_copy_and_refresh_restores_it(
        self, tmp_path: Path, step: str, path_parts: tuple[str, ...], unit_parts: tuple[str, ...],
    ):
        ws = make_workspace(tmp_path, step)
        prepare(ws, step)
        copy = ws.joinpath(*path_parts)
        copy.write_text('edited by the user', encoding='utf-8')

        rerun = prepare(ws, step)

        assert copy.read_text(encoding='utf-8') == 'edited by the user'
        assert rerun['materialized'] == []

        refreshed = prepare(ws, step, '--refresh')

        source = REPO_ROOT.joinpath(*path_parts)
        assert copy.read_bytes() == source.read_bytes()
        assert str(ws.joinpath(*unit_parts)) in refreshed['materialized']

    def test_rerun_fills_in_a_missing_file_without_touching_the_others(self, tmp_path: Path):
        ws = make_workspace(tmp_path)
        prepare(ws, 'script')
        package = ws / 'references' / 'delegation' / 'script'
        (package / 'handoff-template.md').unlink()
        (package / 'base-instructions.md').write_text('edited', encoding='utf-8')

        rerun = prepare(ws, 'script')

        assert (package / 'handoff-template.md').read_bytes() == (
            REPO_ROOT / 'references' / 'delegation' / 'script' / 'handoff-template.md'
        ).read_bytes()
        assert (package / 'base-instructions.md').read_text(encoding='utf-8') == 'edited'
        assert rerun['materialized'] == [str(package)]


class TestCatalogHandoff:
    def test_inputs_outputs_references_and_cut_clips_command(self, tmp_path: Path):
        ws = make_workspace(
            tmp_path, 'catalog', narration_requests=['x'], composition_requests=['y']
        )
        write(ws / 'narration-instructions.md', 'not for catalog')
        write(ws / 'composition-instructions.md', 'not for catalog')
        prepare(ws, 'catalog')

        sections = handoff_sections((ws / 'catalog-handoff.md').read_text(encoding='utf-8'))
        inputs = sections['Inputs']
        for relative in (
            'harvest_page/manifest.json',
            'research-brief.md',
            'vision_analyze/topic-context.txt',
            'inputs.json',
        ):
            assert f'{ws}/{relative}' in inputs
        outputs = sections['Outputs']
        for relative in ('material-catalog.json', 'extract_frames/', 'vision_analyze/', 'clips/'):
            assert f'{ws}/{relative}' in outputs
        assert (
            f'source {REPO_ROOT}/.venv/bin/activate && '
            f'python3 {REPO_ROOT}/scripts/cut-clips.py {ws}'
        ) in outputs
        assert 'python3 scripts/' not in outputs
        assert absolute_paths(sections['Required References']) == {
            ws / 'references' / 'delegation' / 'catalog' / 'base-instructions.md',
            ws / 'references' / 'delegation' / 'conventions.md',
        }
        assert sections['Additional Instructions'] == 'None'

    def test_catalog_receives_user_material_instructions(self, tmp_path: Path):
        ws = make_workspace(tmp_path, 'catalog')
        instructions = ws / 'catalog-instructions.md'
        write(instructions, '优先选择能看清操作步骤的界面。')
        prepare(ws, 'catalog')

        sections = handoff_sections((ws / 'catalog-handoff.md').read_text(encoding='utf-8'))

        assert sections['Additional Instructions'] == f'- {instructions}'
        assert instructions.read_text(encoding='utf-8') == '优先选择能看清操作步骤的界面。'


COMPOSITION_PRODUCTS = {
    'composition/design.json',
    'composition/storyboard.md',
    'composition/index.html',
    'composition/compositions',
    'composition/check-composition.json',
    'composition/renders/final.mp4',
}

# 本阶段自己生成的产物：handoff 命令会写它们，所以生成前它们不该存在。
COMPOSITION_GENERATED = {
    'composition',
    'composition/assets/fonts',
    'composition/scene-config.json',
    'composition/assets/subtitle-units.json',
    'composition/assets/template-cues.json',
    'composition/assets/template-timeline.json',
}


class TestHandoffContract:
    @pytest.mark.parametrize('step, products', [
        ('script', {'script.txt', 'tts-lexicon.json', 'scene-plan.json', 'narration.txt', 'narration-offsets.json'}),
        ('catalog', {'material-catalog.json', 'extract_frames', 'clips'}),
        ('composition', COMPOSITION_PRODUCTS | COMPOSITION_GENERATED),
    ], ids=['script', 'catalog', 'composition'])
    def test_writes_handoff_and_dispatch_prompt_with_only_products_missing(
        self, tmp_path: Path, step: str, products: set[str],
    ):
        ws = make_workspace(tmp_path, step, template='github-trending' if step != 'catalog' else None)

        result = prepare(ws, step)

        handoff = ws / f'{step}-handoff.md'
        assert result['handoff_path'] == str(handoff)
        assert result['dispatch_prompt'] == f'读取 {handoff} 并按它执行；完成后报告产物路径。'
        if step != 'composition':
            assert result['fonts'] is None
        text = handoff.read_text(encoding='utf-8')
        assert text.startswith(f'# {step}-handoff — demo-topic')
        assert list(handoff_sections(text)) == SECTIONS
        assert '{{' not in text and '}}' not in text
        assert pointed_at_paths_that_do_not_exist(text) == {ws / product for product in products}


class TestCompositionHandoff:
    def test_tool_only_inputs_are_not_agent_reading_inputs(self, tmp_path: Path):
        ws = make_workspace(tmp_path, 'composition')
        result = prepare(ws, 'composition')
        text = (ws / 'composition-handoff.md').read_text(encoding='utf-8')
        sections = handoff_sections(text)
        agent_inputs, tool_inputs = sections['Inputs'].split('### 仅供工具读取', 1)

        assert '### Agent 阅读与画面资源' in agent_inputs
        for relative in ('script.txt', 'scene-plan.json', 'transcribe/timeline.json'):
            assert str(ws / relative) in agent_inputs
        for relative in ('transcribe/transcript.json', 'narration.txt', 'narration-offsets.json'):
            path = str(ws / relative)
            assert path not in agent_inputs
            assert path in tool_inputs
            assert path in sections['Outputs']  # existing tool commands still receive the files
        assert '正常流程不阅读或复述其全文' in tool_inputs
        assert str(ws / 'composition/scene-config.json') not in sections['Inputs']
        assert str(ws / 'composition/scene-config.json') in sections['Outputs']
        assert result['dispatch_prompt'] == f'读取 {ws}/composition-handoff.md 并按它执行；完成后报告产物路径。'

    def test_commands_and_selection_order_use_visual_scenes_and_design_artifact(self, tmp_path: Path):
        ws = make_workspace(tmp_path, 'composition', design='default', layout='stage')
        prepare(ws, 'composition')

        text = (ws / 'composition-handoff.md').read_text(encoding='utf-8')
        sections = handoff_sections(text)

        assert f'cd {ws}/composition && npx hyperframes check' in text
        assert f'source {REPO_ROOT}/.venv/bin/activate && python3 {REPO_ROOT}/scripts/check-composition.py' in text
        assert f'--scene-config {ws}/composition/scene-config.json' in text
        assert f'--narration-audio {ws}/voice_clone/narration.mp3' in text
        assert f'--design {ws}/composition/design.json' in text
        assert f'--output {ws}/composition/check-composition.json' in text
        assert '--layout ' not in text
        assert '--timeline ' not in text
        assert 'python3 scripts/' not in text

        assert '用户要求 → 特别匹配模块 → 即时生成' in sections['Outputs']
        refs = sections['Required References']
        assert '发现入口，不是采用清单' in refs
        assert '必须采用' not in refs
        assert '每个 scene 都必须' not in refs

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

    @pytest.mark.parametrize('input_mode', ['standard', 'paper'])
    def test_inputs_section_lists_the_catalog_only_when_materials_are_fetched(
        self, tmp_path: Path, input_mode: str
    ):
        ws = make_workspace(
            tmp_path, 'composition', input_mode=input_mode, fetch_materials=False
        )
        if input_mode == 'paper':
            write(ws / 'material-catalog.json', '{"entries": []}')
        prepare(ws, 'composition')

        inputs = handoff_sections((ws / 'composition-handoff.md').read_text(encoding='utf-8'))['Inputs']

        if input_mode == 'paper':
            assert str(ws / 'material-catalog.json') in inputs
        else:
            assert '- material-catalog.json：无（' in inputs
        assert 'orientation landscape' in inputs
        assert 'design github' not in inputs and 'design 未预选' not in inputs
        assert 'template 无' not in inputs and 'template 未选择' not in inputs  # 无全局模板决策
        assert 'layout presenter' not in inputs

    @pytest.mark.parametrize('template', ['github-trending', None], ids=['selected-template', 'no-template'])
    def test_required_references_follow_the_overlay_order(self, tmp_path: Path, template: str | None):
        ws = make_workspace(tmp_path, 'composition', template=template, design='producthunt', layout='presenter', orientation='landscape')
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

        expected = [
            ['references/delegation/composition/base-instructions.md'],
            ['references/delegation/composition/scene-config.md'],
            ['modules/modules.md'],
            ['modules/designs/designs.md'],
            ['modules/layouts/layouts.md'],
            ['modules/templates/templates.md'],
            ['modules/components/components.md'],
        ]

        assert [rel(absolute_paths(item)) for item in items] == expected
        assert '组件索引：按需读要挂载的组件文档' in items[-1]
        assert '**可选参考（可跳过）**' in body
        optional = body.split('**可选参考（可跳过）**', 1)[1]
        assert absolute_paths(optional) == {
            ws / 'modules/patterns', ws / 'modules/motion.md', ws / 'modules/transitions',
        }
        assert '查阅条件见基础指令第四部分' in optional
        assert all(
            'modules/patterns' not in item
            and 'modules/motion.md' not in item
            and 'modules/transitions' not in item
            for item in items
        )
        # 模板按场景借用：不预选任何具体模板文档。
        assert 'modules/templates/github-trending' not in body


class TestCompositionMaterialization:
    def test_modules_are_copied_for_composition_and_edited_template_contract_repairs_on_refresh(self, tmp_path: Path):
        ws = make_workspace(tmp_path, 'composition', template='github-trending')

        result = prepare(ws, 'composition')

        modules = ws / 'modules'
        assert (modules / 'modules.md').read_bytes() == (REPO_ROOT / 'modules' / 'modules.md').read_bytes()
        assert (modules / 'layouts' / 'landscape-presenter.json').is_file()
        assert (modules / 'layouts' / 'portrait-presenter.json').is_file()
        assert (modules / 'layouts' / 'portrait-3x4-presenter.json').is_file()
        assert (modules / 'components' / 'presenter' / 'presenter.html').is_file()
        delegation = ws / 'references' / 'delegation'
        assert (delegation / 'conventions.md').is_file()
        assert (delegation / 'composition' / 'base-instructions.md').is_file()
        assert not (delegation / 'script').exists()
        assert result['materialized'] == [
            str(delegation / 'conventions.md'),
            str(delegation / 'composition'),
            str(modules),
        ]

        # Edited template contract copy is advisory (not a gate), and --refresh restores it.
        tpl_contract = modules / 'templates' / 'github-trending' / 'github-trending.json'
        contract = json.loads(tpl_contract.read_text(encoding='utf-8'))
        contract['preferred_layouts'] = ['landscape']
        tpl_contract.write_text(json.dumps(contract), encoding='utf-8')
        prepare(ws, 'composition')
        prepare(ws, 'composition', '--refresh')
        assert json.loads(tpl_contract.read_text(encoding='utf-8'))['preferred_layouts'] == ['landscape-presenter']


class TestCompositionDesignDelegation:
    def test_handoff_never_preselects_design_preinstalls_fonts_or_gates_on_legacy_design(self, tmp_path: Path):
        ws = make_workspace(tmp_path, 'composition')
        inputs = json.loads((ws / 'inputs.json').read_text(encoding='utf-8'))
        inputs.pop('design', None)
        write(ws / 'inputs.json', json.dumps(inputs, ensure_ascii=False))

        result = prepare(ws, 'composition', env={'FONTS_RESOURCES_DIR': str(tmp_path / 'missing-fonts')})

        assert result['fonts'] is None
        assert not (ws / 'composition' / 'assets' / 'fonts').exists()
        sections = handoff_sections((ws / 'composition-handoff.md').read_text(encoding='utf-8'))
        assert 'orientation landscape' in sections['Inputs']
        assert 'design default' not in sections['Inputs'] and 'design 未预选' not in sections['Inputs']
        assert f'--design {ws}/composition/design.json' in sections['Outputs']
        assert 'fonts-download.sh' in sections['Outputs']
        assert str(ws / 'modules/designs/designs.md') in sections['Required References']
        assert str(ws / 'modules/designs/default/default.md') not in sections['Required References']

        # Legacy inputs.design is neither validated as a gate nor injected into Inputs.
        inputs['design'] = 'no-such-design'
        write(ws / 'inputs.json', json.dumps(inputs, ensure_ascii=False))
        legacy_res = prepare(ws, 'composition')
        assert legacy_res['fonts'] is None
        assert not (ws / 'composition' / 'assets' / 'fonts').exists()
        legacy_sections = handoff_sections((ws / 'composition-handoff.md').read_text(encoding='utf-8'))
        assert 'no-such-design' not in legacy_sections['Inputs']
        assert str(ws / 'modules/designs/designs.md') in legacy_sections['Required References']

    def test_style_and_scene_scoped_design_requests_flow_through_composition_requests(self, tmp_path: Path):
        ws = make_workspace(tmp_path, 'composition')
        inputs = json.loads((ws / 'inputs.json').read_text(encoding='utf-8'))
        scoped_request = '仅叙事 scene 2 使用 github 风格，其他 scene 不传播'
        inputs.pop('design', None)
        inputs['composition_requests'] = [scoped_request]
        write(ws / 'inputs.json', json.dumps(inputs, ensure_ascii=False))

        result = prepare(ws, 'composition')

        assert result['fonts'] is None
        assert not (ws / 'composition' / 'assets' / 'fonts').exists()
        sections = handoff_sections((ws / 'composition-handoff.md').read_text(encoding='utf-8'))
        assert scoped_request in sections['Additional Instructions']
        assert 'design github' not in sections['Inputs']


class TestFailures:
    def test_bad_cli_arguments_and_missing_workspace_fail_cleanly(self, tmp_path: Path):
        ws = make_workspace(tmp_path)
        proc, result = run_cli(str(ws), 'not-a-step')
        assert proc.returncode == 2 and result['success'] is False
        assert not (ws / 'not-a-step-handoff.md').exists()

        missing_args, missing_res = run_cli()
        assert missing_args.returncode == 2 and missing_res['success'] is False

        no_ws, no_ws_res = run_cli(str(tmp_path / 'nowhere'), 'script')
        assert no_ws.returncode == 1 and 'workspace is not a directory' in no_ws_res['error']

    def test_unusable_inputs_json_and_field_types_exit_1(self, tmp_path: Path):
        ws = make_workspace(tmp_path)
        for inputs_text, message in (
            (None, 'inputs.json not found'),
            ('{not json', 'not valid JSON'),
            ('[]', 'not an object'),
            ('{"coding_agent": "pi-coding-agent"}', 'missing fields'),
        ):
            (ws / 'inputs.json').unlink(missing_ok=True)
            if inputs_text is not None:
                write(ws / 'inputs.json', inputs_text)
            proc, result = run_cli(str(ws), 'script')
            assert proc.returncode == 1 and message in result['error']

        for overrides, message in (
            ({'fetch_materials': 'false'}, 'fetch_materials'),
            ({'duration': '90秒'}, 'duration'),
            ({'duration': {'min': 5}}, 'duration'),
            ({'coding_agent': ''}, 'coding_agent'),
            ({'language': None}, 'language'),
            ({'narration_requests': '语气更口语'}, 'narration_requests'),
            ({'narration_requests': ['']}, 'narration_requests'),
        ):
            write(ws / 'inputs.json', json.dumps({**INPUTS, **overrides}, ensure_ascii=False))
            proc, result = run_cli(str(ws), 'script')
            assert proc.returncode == 1 and message in result['error']

        comp_ws = make_workspace(tmp_path / 'comp', 'composition')
        for overrides, message in (
            ({'orientation': 'vertical'}, 'orientation'),
            ({'composition_requests': ['ok', 3]}, 'composition_requests'),
        ):
            write(comp_ws / 'inputs.json', json.dumps({**INPUTS, **overrides}, ensure_ascii=False))
            proc, result = run_cli(str(comp_ws), 'composition')
            assert proc.returncode == 1 and message in result['error']

    def test_missing_step_prerequisites_exit_1_before_touching_workspace(self, tmp_path: Path):
        comp_ws = make_workspace(tmp_path / 'comp', 'composition')
        (comp_ws / 'transcribe' / 'timeline.json').unlink()
        proc, result = run_cli(str(comp_ws), 'composition')
        assert proc.returncode == 1 and str(comp_ws / 'transcribe' / 'timeline.json') in result['error']
        assert not (comp_ws / 'composition-handoff.md').exists()
        assert not (comp_ws / 'modules').exists()
        assert not (comp_ws / 'composition').exists()

        script_ws = make_workspace(tmp_path / 'script')
        catalog_file = script_ws / 'material-catalog.json'
        catalog_bytes = catalog_file.read_bytes()
        catalog_file.unlink()
        proc, result = run_cli(str(script_ws), 'script')
        assert proc.returncode == 1 and str(catalog_file) in result['error']

        catalog_file.write_bytes(catalog_bytes)
        (script_ws / 'research-brief.md').unlink()
        proc, result = run_cli(str(script_ws), 'script')
        assert proc.returncode == 1 and str(script_ws / 'research-brief.md') in result['error']

    def test_steps_accept_only_declared_inputs_and_ignore_legacy_visual_fields(self, tmp_path: Path):
        for step in ('catalog', 'script'):
            ws = make_workspace(tmp_path / step, step)
            inputs = json.loads((ws / 'inputs.json').read_text(encoding='utf-8'))
            for field in ('source', 'design', 'orientation', 'layout', 'template'):
                inputs.pop(field, None)
            inputs.update(layout={}, template='../unused', composition_requests=3)
            write(ws / 'inputs.json', json.dumps(inputs, ensure_ascii=False))
            prepare(ws, step)

        comp_ws = make_workspace(tmp_path / 'comp', 'composition')
        base_inputs = json.loads((comp_ws / 'inputs.json').read_text(encoding='utf-8'))
        base_inputs.pop('layout', None)
        base_inputs.pop('template', None)
        write(comp_ws / 'inputs.json', json.dumps(base_inputs, ensure_ascii=False))
        assert not (comp_ws / 'composition' / 'scene-config.json').exists()
        prepare(comp_ws, 'composition')
        text = (comp_ws / 'composition-handoff.md').read_text(encoding='utf-8')
        assert f'{comp_ws}/modules/layouts/layouts.md' in text
        assert f'--scene-config {comp_ws}/composition/scene-config.json' in text
        assert not (comp_ws / 'composition' / 'scene-config.json').exists()

        for legacy_overrides in (
            {'template': 'github-trending', 'layout': 'portrait', 'orientation': 'portrait'},
            {'layout': 'presenter', 'orientation': 'portrait'},
            {'template': 'no-such-template', 'layout': 'no-such-layout'},
            {'layout': 'portrait-3x4', 'orientation': 'portrait-3:4'},
        ):
            write(comp_ws / 'inputs.json', json.dumps({**base_inputs, **legacy_overrides}, ensure_ascii=False))
            prepare(comp_ws, 'composition')
            body = handoff_sections((comp_ws / 'composition-handoff.md').read_text(encoding='utf-8'))['Required References']
            assert f'{comp_ws}/modules/layouts/layouts.md' in body
            assert 'portrait-3x4.json' not in body


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
    @pytest.mark.parametrize('placeholder', ['no_such_value', 'Ws2'])
    def test_an_unreplaced_placeholder_exits_1_and_writes_nothing(
        self, tmp_path: Path, skill_copy: Path, placeholder: str,
    ):
        ws = make_workspace(tmp_path)
        template = skill_copy / 'references' / 'delegation' / 'script' / 'handoff-template.md'
        template.write_text(
            template.read_text(encoding='utf-8').replace(
                '## Coding Agent', f'## Coding Agent {{{{{placeholder}}}}}',
            ),
            encoding='utf-8',
        )

        proc, result = run_cli(str(ws), 'script', script=skill_copy / 'scripts' / 'prepare-handoff.py')

        assert proc.returncode == 1
        assert result['success'] is False
        assert placeholder in result['error']
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
    def test_fonts_script_is_not_called_before_design_selection(self, tmp_path: Path, skill_copy: Path):
        ws = make_workspace(tmp_path, 'composition')
        (skill_copy / 'scripts' / 'fonts-download.sh').write_text('echo "boom" >&2\nexit 3\n', encoding='utf-8')

        proc, result = run_cli(str(ws), 'composition', script=skill_copy / 'scripts' / 'prepare-handoff.py')

        assert proc.returncode == 0, proc.stderr + proc.stdout
        assert result['success'] is True
        assert result['fonts'] is None
        assert (ws / 'composition-handoff.md').exists()
        assert not (ws / 'composition' / 'assets' / 'fonts').exists()


class TestInputsRendering:
    def test_a_numeric_duration_is_written_in_minutes(self, tmp_path: Path):
        ws = make_workspace(tmp_path, duration=5, language='en', input_mode='paper', template=None)
        prepare(ws, 'script')

        inputs = handoff_sections((ws / 'script-handoff.md').read_text(encoding='utf-8'))['Inputs']

        assert '（目标时长 5 分钟、语言 en、input_mode paper）' in inputs


class TestReviewRoundFixes:
    """Regressions pinned from the first /code-review round."""

    def test_paths_with_spaces_are_quoted_in_commands(self, tmp_path: Path):
        spaced = (tmp_path / 'AI Agents 2026').resolve()
        ws = (spaced / 'ws' / 'demo-topic').resolve()
        write(ws / 'inputs.json', json.dumps(INPUTS, ensure_ascii=False))
        write(ws / 'research-brief.md', '# brief\n')
        write(ws / 'material-catalog.json', '{"entries": []}')
        write(ws / 'script.txt', '甲\n\n乙\n')
        write(ws / 'scene-plan.json', '[]')
        write(ws / 'voice_clone' / 'narration.mp3')
        write(ws / 'transcribe' / 'transcript.json', '[]')
        write(ws / 'transcribe' / 'timeline.json', '{"paragraphs": []}')
        write(ws / 'narration.txt', '甲\n\n乙\n')
        write(ws / 'narration-offsets.json', '{"version": 1, "segments": []}')

        prepare(ws, 'composition')
        prepare(ws, 'script')

        composition = (ws / 'composition-handoff.md').read_text(encoding='utf-8')
        assert f"cd '{ws}/composition' && npx hyperframes check" in composition
        assert f"--scene-config '{ws}/composition/scene-config.json'" in composition
        assert f"--narration-audio '{ws}/voice_clone/narration.mp3'" in composition
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

    def test_paper_mode_script_handoff_uses_self_contained_base_instructions(self, tmp_path: Path):
        ws = make_workspace(tmp_path, input_mode='paper', fetch_materials=False)
        write(ws / 'material-catalog.json', '{"entries": []}')

        prepare(ws, 'script')

        handoff = (ws / 'script-handoff.md').read_text(encoding='utf-8')
        sections = handoff_sections(handoff)
        assert '02-paper-parse' not in handoff
        assert '05-material-catalog' not in handoff
        assert str(ws / 'material-catalog.json') in sections['Inputs']
        assert str(ws / 'references/delegation/script/base-instructions.md') in sections['Required References']


class TestDelegationDocs:
    """Delegated phase docs invoke prepare-handoff.py rather than filling handoff-template.md directly."""

    def test_delegated_phase_docs_run_prepare_handoff_and_dispatch_its_prompt(self):
        for doc, step in (
            ('references/phases/05-material-catalog.md', 'catalog'),
            ('references/phases/06-script-scene-plan.md', 'script'),
            ('references/phases/08-composition.md', 'composition'),
        ):
            text = (REPO_ROOT / doc).read_text(encoding='utf-8')
            assert (
                f'source .venv/bin/activate && python3 scripts/prepare-handoff.py '
                f'{{work_dir}}/{{topic_name}} {step}'
            ) in text, doc
            assert 'dispatch_prompt' in text, doc
            assert 'handoff-template.md' not in text, doc
