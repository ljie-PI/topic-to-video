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
        if not path.exists() and path.parts[-3:] != ('.venv', 'bin', 'activate')
    }


class TestHandoffContent:
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

    def test_script_handoff_renders_slug_qualified_material_ref_formats(self, tmp_path: Path):
        ws = make_workspace(tmp_path)
        prepare(ws, 'script')

        outputs = handoff_sections((ws / 'script-handoff.md').read_text(encoding='utf-8'))['Outputs']

        assert '`<slug>/<id>`' in outputs
        assert '`<slug>/<video_id>:<start>-<end>`' in outputs

    def test_research_brief_is_a_required_path_and_the_catalog_follows_fetch_materials(self, tmp_path: Path):
        ws = make_workspace(tmp_path, fetch_materials=False)
        prepare(ws, 'script')

        inputs = handoff_sections((ws / 'script-handoff.md').read_text(encoding='utf-8'))['Inputs']

        assert f'- research-brief.md：{ws}/research-brief.md' in inputs
        assert '无（fetch_materials = false' in inputs
        assert 'material-catalog.json）' not in inputs


class TestRequiredReferences:
    def test_script_references_are_just_the_base_instructions(self, tmp_path: Path):
        # 模板是 Phase 8 的画面选择：即使 inputs.json 里已经有 template，script 也不读它。
        ws = make_workspace(tmp_path, template='github')
        prepare(ws, 'script')

        body = handoff_sections((ws / 'script-handoff.md').read_text(encoding='utf-8'))['Required References']

        items = re.findall(r'^\d+\. (.+)$', body, flags=re.MULTILINE)
        assert [absolute_paths(item) for item in items] == [
            {ws / 'references' / 'delegation' / 'script' / 'base-instructions.md'},
        ]
        assert 'modules/templates' not in body


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
        ('composition', ('modules', 'layouts', 'presenter.md'), ('modules',)),
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
    def test_inputs_outputs_and_cut_clips_command(self, tmp_path: Path):
        ws = make_workspace(tmp_path, 'catalog')
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

    def test_required_references_and_none_without_catalog_instructions(self, tmp_path: Path):
        ws = make_workspace(
            tmp_path, 'catalog', narration_requests=['x'], composition_requests=['y']
        )
        write(ws / 'narration-instructions.md', 'not for catalog')
        write(ws / 'composition-instructions.md', 'not for catalog')
        prepare(ws, 'catalog')

        sections = handoff_sections((ws / 'catalog-handoff.md').read_text(encoding='utf-8'))

        base = ws / 'references' / 'delegation' / 'catalog' / 'base-instructions.md'
        assert absolute_paths(sections['Required References']) == {
            base,
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
    'composition/storyboard.md',
    'composition/index.html',
    'composition/compositions',
    'composition/check-composition.json',
    'composition/renders/final.mp4',
}

# 本阶段自己生成的产物：handoff 命令会写它们，所以生成前它们不该存在。
COMPOSITION_GENERATED = {
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
        ws = make_workspace(tmp_path, step, template='github' if step != 'catalog' else None)

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
        assert '已有用户编辑是有效输入' in sections['Outputs']
        assert result['dispatch_prompt'] == f'读取 {ws}/composition-handoff.md 并按它执行；完成后报告产物路径。'
        base = (ws / 'references/delegation/composition/base-instructions.md').read_text(encoding='utf-8')
        assert '标为「仅供工具读取」' in base
        assert '先读工作区里的输入（handoff 的 Inputs 一节列出的文件）' not in base

    def test_commands_use_visual_scenes_and_the_workspace_design_copy(self, tmp_path: Path):
        ws = make_workspace(tmp_path, 'composition', design='default', layout='stage')
        prepare(ws, 'composition')

        text = (ws / 'composition-handoff.md').read_text(encoding='utf-8')

        assert f'cd {ws}/composition && npx hyperframes check' in text
        assert f'source {REPO_ROOT}/.venv/bin/activate && python3 {REPO_ROOT}/scripts/check-composition.py' in text
        assert f'--scene-config {ws}/composition/scene-config.json' in text
        assert f'--narration-audio {ws}/voice_clone/narration.mp3' in text
        assert f'--design {ws}/modules/designs/default/default.json' in text
        assert f'--output {ws}/composition/check-composition.json' in text
        assert '--layout ' not in text
        assert '--timeline ' not in text
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
        assert 'design github、orientation landscape' in inputs
        assert 'template 无' not in inputs and 'template 未选择' not in inputs  # 无全局模板决策
        assert 'layout presenter' not in inputs

    @pytest.mark.parametrize('template', ['github', None], ids=['selected-template', 'no-template'])
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
            [
                'modules/designs/designs.md',
                'modules/designs/producthunt/producthunt.json',
                'modules/designs/producthunt/producthunt.md',
            ],
            ['modules/layouts/layouts.md'],
            ['modules/templates/templates.md'],
            ['modules/components'],
        ]

        assert [rel(absolute_paths(item)) for item in items] == expected
        assert '组件目录：按需读要挂载的组件文档' in items[-1]
        assert '**可选参考（可跳过）**' in body
        optional = body.split('**可选参考（可跳过）**', 1)[1]
        assert absolute_paths(optional) == {ws / 'modules/patterns', ws / 'modules/motion.md'}
        assert '查阅条件见基础指令第四部分' in optional
        assert all('modules/patterns' not in item and 'modules/motion.md' not in item for item in items)
        # 模板按场景借用：不预选任何具体模板文档。
        assert 'modules/templates/github' not in body

    def test_no_global_template_is_dispatched_at_all(self, tmp_path: Path):
        ws = make_workspace(tmp_path, 'composition')
        inputs = json.loads((ws / 'inputs.json').read_text(encoding='utf-8'))
        inputs.pop('template')
        (ws / 'inputs.json').write_text(json.dumps(inputs, ensure_ascii=False), encoding='utf-8')

        prepare(ws, 'composition')

        inputs_section = handoff_sections(
            (ws / 'composition-handoff.md').read_text(encoding='utf-8')
        )['Inputs']
        assert 'template 未选择' not in inputs_section  # 模板逐场景决定，不是全局 handoff 内容
        assert 'template 无（不使用模板）' not in inputs_section


class TestCompositionMaterialization:
    def test_modules_are_copied_for_composition(self, tmp_path: Path):
        ws = make_workspace(tmp_path, 'composition')

        result = prepare(ws, 'composition')

        modules = ws / 'modules'
        assert (modules / 'modules.md').read_bytes() == (REPO_ROOT / 'modules' / 'modules.md').read_bytes()
        assert (modules / 'layouts' / 'presenter.json').is_file()
        assert (modules / 'components' / 'jay' / 'jay.html').is_file()
        delegation = ws / 'references' / 'delegation'
        assert (delegation / 'conventions.md').is_file()
        assert (delegation / 'composition' / 'base-instructions.md').is_file()
        assert not (delegation / 'script').exists()
        assert result['materialized'] == [
            str(delegation / 'conventions.md'),
            str(delegation / 'composition'),
            str(modules),
        ]

    def test_an_edited_workspace_layout_copy_is_not_a_gate(self, tmp_path: Path):
        """preset 是逐 scene 的可选借用：工作区 layout 副本被改过不再阻止准备
        handoff；--refresh 仍把副本换回库文件。"""
        ws = make_workspace(tmp_path, 'composition', layout='presenter')
        prepare(ws, 'composition')
        copy = ws / 'modules' / 'layouts' / 'presenter.json'
        data = json.loads(copy.read_text(encoding='utf-8'))
        data['canvas'] = {'width': 1080, 'height': 1920}
        copy.write_text(json.dumps(data), encoding='utf-8')

        prepare(ws, 'composition')

        prepare(ws, 'composition', '--refresh')
        assert json.loads(copy.read_text(encoding='utf-8'))['canvas'] == {'width': 1920, 'height': 1080}

    def test_commands_use_the_scene_config_pipeline_entry(self, tmp_path: Path):
        ws = make_workspace(tmp_path, 'composition', template='github', layout='stage')
        write(ws / 'composition/scene-config.json', json.dumps({
            'version': 1,
            'canvas': {'width': 1920, 'height': 1080},
            'total_s': 5,
            'scenes': [],
        }))

        prepare(ws, 'composition')

        assert '--scene-config' in (ws / 'composition-handoff.md').read_text(encoding='utf-8')

    def test_legacy_template_layout_combos_are_not_validated(self, tmp_path: Path):
        """旧全局 template/layout 组合不再是门槛：竖屏项目带着 github 模板名也能
        生成 handoff——模板与布局由 agent 逐场景决定。"""
        ws = make_workspace(tmp_path, 'composition', template='github', layout='portrait', orientation='portrait')

        prepare(ws, 'composition')

        assert (ws / 'composition-handoff.md').exists()


class TestFonts:
    def test_installs_the_selected_designs_fonts_without_network(self, tmp_path: Path):
        ws = make_workspace(tmp_path, 'composition', design='producthunt')

        result = prepare(ws, 'composition', env={'FONTS_CSS2_URL': 'http://127.0.0.1:9/css2'})

        fonts = ws / 'composition' / 'assets' / 'fonts'
        css = (fonts / 'producthunt-fonts.css').read_text(encoding='utf-8')
        assert result['fonts']['success'] is True
        assert result['fonts']['output_dir'] == str(fonts)
        # A summary, not the ~100-file list: the main agent only dispatches the prompt.
        assert result['fonts']['installed'] > 0
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

        proc, result = run_cli(str(ws), 'not-a-step')

        assert proc.returncode == 2
        assert result['success'] is False
        assert not (ws / 'not-a-step-handoff.md').exists()

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
        ('{"coding_agent": "pi-coding-agent"}', 'missing fields'),
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

    def test_the_script_step_needs_no_template_or_layout(self, tmp_path: Path):
        # 旁白在 Phase 8 之前就写完了：那时的 inputs.json 里还没有模板与 layout。
        ws = make_workspace(tmp_path)
        inputs = json.loads((ws / 'inputs.json').read_text(encoding='utf-8'))
        for name in ('template', 'layout'):
            inputs.pop(name, None)
        write(ws / 'inputs.json', json.dumps(inputs, ensure_ascii=False))

        prepare(ws, 'script')

    def test_composition_handoff_needs_no_visual_decisions_nor_scene_config(self, tmp_path: Path):
        """Scene template / layouts are decided after dispatch, not a handoff precondition."""
        ws = make_workspace(tmp_path, 'composition')
        inputs = json.loads((ws / 'inputs.json').read_text(encoding='utf-8'))
        inputs.pop('layout', None)
        inputs.pop('template', None)
        write(ws / 'inputs.json', json.dumps(inputs, ensure_ascii=False))
        assert not (ws / 'composition' / 'scene-config.json').exists()

        prepare(ws, 'composition')

        text = (ws / 'composition-handoff.md').read_text(encoding='utf-8')
        assert f'{ws}/modules/layouts/layouts.md' in text
        assert f'--scene-config {ws}/composition/scene-config.json' in text
        assert f'--narration-audio {ws}/voice_clone/narration.mp3' in text
        assert not (ws / 'composition' / 'scene-config.json').exists()

    @pytest.mark.parametrize('field', ['narration_requests', 'composition_requests'])
    @pytest.mark.parametrize('value', ['语气更口语', None, [''], ['ok', 3]])
    def test_requests_must_be_lists_of_non_empty_strings(self, tmp_path: Path, field: str, value):
        step = 'script' if field == 'narration_requests' else 'composition'
        ws = make_workspace(tmp_path, step, **{field: value})

        proc, result = run_cli(str(ws), step)

        assert proc.returncode == 1
        assert field in result['error']

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

    def test_legacy_layout_canvas_mismatch_is_not_a_gate(self, tmp_path: Path):
        ws = make_workspace(tmp_path, 'composition', layout='presenter', orientation='portrait')

        prepare(ws, 'composition')

    def test_an_unknown_orientation_exits_1(self, tmp_path: Path):
        ws = make_workspace(tmp_path, 'composition', orientation='vertical')

        proc, result = run_cli(str(ws), 'composition')

        assert proc.returncode == 1
        assert 'orientation' in result['error']

    def test_unknown_legacy_template_or_layout_names_are_not_gates(self, tmp_path: Path):
        # 模板与 layout 在 Phase 8 逐场景决定；inputs.json 的旧全局名字不再校验。
        ws = make_workspace(tmp_path, 'composition', template='no-such-template', layout='no-such-layout')

        prepare(ws, 'composition')

        assert (ws / 'composition-handoff.md').exists()

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

    @pytest.mark.parametrize('field, value', [
        pytest.param('design', 'github\n', id='design-trailing-newline'),
        pytest.param('design', '../escape', id='design-path'),
    ])
    def test_names_in_inputs_reject_paths_and_trailing_newlines(self, tmp_path: Path, field: str, value: str):
        ws = make_workspace(tmp_path, 'composition', **{field: value})

        proc, result = run_cli(str(ws), 'composition')

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

        assert '（目标时长 5 分钟、语言 en、input_mode paper）' in inputs


class TestReviewRoundFixes:
    """Regressions pinned from the first /code-review round."""

    def test_legacy_layout_still_references_the_layout_catalog(self, tmp_path: Path):
        # 旧字段继续参与校验，但 handoff 不把某一个 layout 当成全片选择。
        ws = make_workspace(tmp_path, 'composition', layout='portrait-3x4', orientation='portrait-3:4')

        prepare(ws, 'composition')

        text = (ws / 'composition-handoff.md').read_text(encoding='utf-8')
        assert f'--scene-config {ws}/composition/scene-config.json' in text
        assert '--layout ' not in text
        body = handoff_sections(text)['Required References']
        assert f'{ws}/modules/layouts/layouts.md' in body
        assert f'{ws}/modules/layouts/portrait-3x4.json' not in body

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

    def test_a_design_kept_only_in_the_workspace_is_rejected(self, tmp_path: Path, skill_copy: Path):
        # 已从库中移除的 design 不再靠工作区的历史副本继续驱动生成。
        (skill_copy / 'modules').unlink()
        gutted = tmp_path / 'gutted-modules'
        shutil.copytree(REPO_ROOT / 'modules', gutted, ignore=shutil.ignore_patterns('github'))
        (skill_copy / 'modules').symlink_to(gutted)
        ws = make_workspace(tmp_path, 'composition', design='github')
        copied = ws / 'modules' / 'designs' / 'github'
        shutil.copytree(REPO_ROOT / 'modules' / 'designs' / 'github', copied)

        proc, result = run_cli(str(ws), 'composition', script=skill_copy / 'scripts' / 'prepare-handoff.py')

        assert proc.returncode == 1
        assert "design 'github' is not an available design" in result['error']
        assert not (ws / 'composition' / 'assets' / 'fonts').exists()


class TestDelegationDocs:
    """The docs the main agent follows hand it prepare-handoff.py, not a template to fill."""

    @pytest.mark.parametrize('doc, step', [
        ('references/phases/05-material-catalog.md', 'catalog'),
        ('references/phases/06-script-scene-plan.md', 'script'),
        ('references/phases/08-composition.md', 'composition'),
    ])
    def test_phase_docs_run_prepare_handoff_and_dispatch_its_prompt(self, doc: str, step: str):
        text = (REPO_ROOT / doc).read_text(encoding='utf-8')

        assert (
            f'source .venv/bin/activate && python3 scripts/prepare-handoff.py '
            f'{{work_dir}}/{{topic_name}} {step}'
        ) in text
        assert 'dispatch_prompt' in text
        assert 'handoff-template.md' not in text

    def test_conventions_dispatch_through_pi_from_the_workspace(self):
        text = (REPO_ROOT / 'references' / 'delegation' / 'conventions.md').read_text(encoding='utf-8')

        assert '默认 coding agent 是 **pi-coding-agent**' in text
        assert 'pi -p -- "<dispatch_prompt>"' in text
        # Pi 没有 --add-dir 那类目录授权开关：靠 cwd 与绝对路径，而不是照搬其他 CLI。
        assert '--add-dir' not in text
        assert '--permission-mode' not in text
        assert (
            '运行 `source .venv/bin/activate && python3 scripts/prepare-handoff.py <ws> <step>`'
        ) in text

    @pytest.mark.parametrize('doc', [
        'modules/modules.md',
        'modules/templates/github/github.md',
        'modules/components/jay/jay.md',
    ])
    def test_example_docs_do_not_point_to_the_removed_handoff_reference(self, doc: str):
        text = (REPO_ROOT / doc).read_text(encoding='utf-8')

        assert 'handoff 的 Required References' not in text

    def test_composition_instructions_choose_components_before_writing_the_storyboard(self):
        text = (REPO_ROOT / 'references' / 'delegation' / 'composition' / 'base-instructions.md').read_text(encoding='utf-8')

        assert text.index('modules/components/components.md') < text.index('组件使用表')
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

    def test_conventions_list_all_three_delegation_packages(self):
        text = (REPO_ROOT / 'references' / 'delegation' / 'conventions.md').read_text(encoding='utf-8')

        for step in ('catalog', 'script', 'composition'):
            assert f'`references/delegation/{step}/`' in text
        assert '只支持 `script` 和 `composition`' not in text
        assert '重新运行一次 `prepare-handoff.py`' in text

    def test_phase_5_keeps_main_agent_workflow_and_inline_fallback(self):
        text = (REPO_ROOT / 'references' / 'phases' / '05-material-catalog.md').read_text(encoding='utf-8')

        assert '写进委派 prompt' not in text
        assert '主 agent 做四件事' in text
        assert '200 字以内' in text
        assert '3-5 个核心论点或关键概念' in text
        assert 'pipeline-status.py {work_dir}/{topic_name}' in text
        assert '环境既不能原生委派也不能运行目标 CLI' in text
        assert '未指定 agent' in text
        assert 'references/delegation/catalog/base-instructions.md' in text
        assert '一次处理一条 manifest entry' in text
        assert '增量写入 `material-catalog.json`' in text
        assert '`material-catalog.json` 的结构' not in text
        assert '**Mode 1（显式 VLM）' not in text

    def test_catalog_base_instructions_contain_all_delegated_rules(self):
        text = (REPO_ROOT / 'references' / 'delegation' / 'catalog' / 'base-instructions.md').read_text(encoding='utf-8')

        for required in (
            '**路径 base（必须保持一致）',
            '### 抽帧与字幕',
            '**Mode 1（显式 VLM）',
            '**Mode 2（执行 agent 直接分析）',
            '**Paper-origin entries',
            '**过滤阈值为 7 分',
            '**所有 entry 写完后运行一次',
            'scripts/cut-clips.py {work_dir}/{topic_name}',
            '`material-catalog.json` 的结构',
            '## 仅论文素材（`input_mode = "paper"` 且 `fetch_materials = false`）',
        ):
            assert required in text

    def test_skill_entry_points_at_the_delegation_prep_script(self):
        text = (REPO_ROOT / 'SKILL.md').read_text(encoding='utf-8')

        assert '`scripts/prepare-handoff.py`：委派步骤的准备' in text
        assert 'dispatch_prompt' in text
