"""Guardrails live at their point of use; gotchas remain maintainer notes."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PHASE_DOCS = sorted((REPO_ROOT / 'references' / 'phases').glob('*.md'))


def doc_text(relpath: str) -> str:
    return (REPO_ROOT / relpath).read_text(encoding='utf-8')


def section(text: str, heading: str) -> str:
    match = re.search(
        rf'^## {re.escape(heading)}\n(.*?)(?=^## |^---\s*$|\Z)',
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match, f'missing ## {heading}'
    return match.group(1)


def guardrails(relpath: str) -> str:
    return section(doc_text(relpath), '护栏')


def test_skill_keeps_only_cross_phase_guardrails_and_the_output_convention():
    skill = doc_text('SKILL.md')
    core = section(skill, '核心护栏')

    assert len(re.findall(r'^\d+\. \*\*', core, flags=re.MULTILINE)) == 5
    for required in (
        '写之前先调研',
        '进度只看 pipeline-status',
        '委派步骤（Phase 5 / 6 / 8）',
        '每个素材都能追溯到 `material-catalog.json`',
        'source .venv/bin/activate',
    ):
        assert required in core
    for moved in (
        'TTS 后端由环境变量选择',
        'ASR 后端由环境变量选择',
        '预先 stage 确定性的 WOFF2 字体',
        'Composition 委派给 coding agent',
        '素材搜索是可选但推荐的',
        'Chrome over CDP',
        '视频下载顺序执行',
    ):
        assert moved not in core
    assert '所有脚本都把 JSON 输出到 stdout' in section(skill, '输出约定')


def test_skill_delegation_guardrail_preserves_the_phase5_fallback():
    core = section(doc_text('SKILL.md'), '核心护栏')

    assert '唯一例外' in core
    assert 'Phase 5' in core
    assert '没有 sub-agent 工具' in core
    assert 'references/phases/05-material-catalog.md' in core


def test_voice_subtitles_command_activates_the_project_venv():
    phase7 = doc_text('references/phases/07-voice-subtitles.md')

    assert (
        'source .venv/bin/activate && python3 scripts/voice-subtitles.py '
        '{work_dir}/{topic_name}'
    ) in phase7


def test_cut_clips_points_to_the_current_phase5_guardrails():
    script = doc_text('scripts/cut-clips.py')

    assert 'SKILL.md guardrail 6' not in script
    assert 'Phase 5 guardrails' in script
    assert 'references/phases/05-material-catalog.md' in script


@pytest.mark.parametrize('doc_path', PHASE_DOCS, ids=lambda path: path.name)
def test_every_phase_has_guardrails_immediately_after_next_step(doc_path: Path):
    text = doc_path.read_text(encoding='utf-8')
    headings = re.findall(r'^## (.+)$', text, flags=re.MULTILINE)

    next_step = headings.index('下一步')
    assert headings[next_step + 1] == '护栏'
    if doc_path.name in {'01-gather-inputs.md', '09-check-mix.md'}:
        assert section(text, '护栏').strip() == '无'
    else:
        assert section(text, '护栏').strip() != '无'


@pytest.mark.parametrize('relpath, required', [
    ('references/phases/03-research.md', 'Chrome over CDP'),
    ('references/phases/04-material-harvest.md', '素材搜索是可选但推荐的'),
    ('references/phases/04-material-harvest.md', '视频下载顺序执行'),
    ('references/phases/05-material-catalog.md', 'scripts/cut-clips.py'),
    ('references/phases/06-script-scene-plan.md', '素材 catalog / vision 分析在 Phase 5，不是 Phase 6'),
    ('references/phases/07-voice-subtitles.md', 'TTS 后端由环境变量选择'),
    ('references/phases/07-voice-subtitles.md', 'ASR 后端由环境变量选择'),
    ('references/phases/08-composition.md', '预先 stage 确定性的 WOFF2 字体'),
    ('references/phases/08-composition.md', '字体实现归 HyperFrames'),
    ('references/phases/08-composition.md', 'Composition 委派给 coding agent'),
    ('references/phases/08-composition.md', 'Scene 设计归 HyperFrames'),
])
def test_phase_specific_rules_move_to_their_owning_phase(relpath: str, required: str):
    assert required in guardrails(relpath)


def test_gotchas_are_continuous_maintainer_notes_without_duplicate_rules():
    gotchas = doc_text('references/gotchas.md')

    assert gotchas.startswith('# 维护者笔记：历史症状 → 原因 → 修复\n')
    numbers = [int(value) for value in re.findall(r'^## (\d+)\.', gotchas, flags=re.MULTILINE)]
    assert numbers == list(range(1, len(numbers) + 1))
    assert len(numbers) == 10
    assert 'HyperFrames Transcribe 的中文下载与 UTF-8 故障' in gotchas
    assert '未校准 ASR 会造成字幕文本错误' in gotchas
    for removed in (
        '中文场景下避免使用 HyperFrames Transcribe',
        '不要编辑 TTS 脚本源码',
        '硬件精度注意事项',
        '全角中文冒号可能引入 TTS 停顿',
        '视频下载必须顺序执行',
        '剥掉视频片段的原始音轨',
        '在项目环境里使用 Python 3',
        'Paper mode 不要跳过主论文解析',
        'catalog 未建立前不要写脚本或匹配素材',
        '主 agent 不手写 composition HTML',
        '字幕文本不要直接照搬未校准 ASR',
    ):
        assert removed not in gotchas


def test_every_retained_gotcha_is_linked_from_its_phase_guardrails():
    gotchas = doc_text('references/gotchas.md')
    retained = {int(value) for value in re.findall(r'^## (\d+)\.', gotchas, flags=re.MULTILINE)}
    expected_links = {
        '01-gather-inputs.md': set(),
        '02-paper-parse.md': {5},
        '03-research.md': {4, 6},
        '04-material-harvest.md': {6, 7},
        '05-material-catalog.md': {8},
        '06-script-scene-plan.md': set(),
        '07-voice-subtitles.md': {1, 2, 3, 9, 10},
        '08-composition.md': set(),
        '09-check-mix.md': set(),
    }
    linked = set()
    for doc_path in PHASE_DOCS:
        refs = {
            int(value)
            for value in re.findall(
                r'历史坑见 `references/gotchas\.md` #(\d+)',
                guardrails(str(doc_path.relative_to(REPO_ROOT))),
            )
        }
        assert refs == expected_links[doc_path.name]
        linked.update(refs)
    assert linked == retained


def test_skill_tool_table_matches_every_executable_cli_script():
    scripts = REPO_ROOT / 'scripts'
    expected = {
        path.name
        for path in scripts.glob('*.py')
        if re.search(r"^if __name__ == ['\"]__main__['\"]:", path.read_text(encoding='utf-8'), flags=re.MULTILINE)
    }
    expected.add('fonts-download.sh')
    tools = section(doc_text('SKILL.md'), '工具与依赖')
    documented = set(re.findall(r'^\| `([^`]+\.(?:py|sh))` \|', tools, flags=re.MULTILINE))

    assert documented == expected
    assert 'make-narration.py' in documented
