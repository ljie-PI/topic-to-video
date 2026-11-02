"""Guardrails live at their point of use, including the recovery rules.

Troubleshooting used to sit in a separate references/gotchas.md that each phase
linked by number. Recovery is part of the rule that prevents the failure, so it
lives in the owning phase's guardrails: the agent only reads one phase doc and
still needs to know what to do when a tool breaks.
"""
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


def failure_handling(relpath: str) -> str:
    """Where a phase doc keeps its recovery rules: 护栏, plus 异常恢复 if present."""
    doc = doc_text(relpath)
    parts = [section(doc, '护栏')]
    if '## 异常恢复' in doc:
        parts.append(section(doc, '异常恢复'))
    return '\n'.join(parts)


def test_skill_keeps_only_cross_phase_guardrails_and_the_output_convention():
    skill = doc_text('SKILL.md')
    core = section(skill, '核心护栏')

    assert len(re.findall(r'^\d+\. \*\*', core, flags=re.MULTILINE)) == 6
    for required in (
        '写之前先调研',
        '进度只看 pipeline-status',
        '每步自检',
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
    # The convention says what the status JSON is for; it no longer promises a
    # log format nobody depends on.
    output = section(skill, '输出约定')
    assert '输出到 stdout' in output and '不能当作阶段完成的依据' in output
    assert '人类可读' not in skill


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
    assert 'Phase 5 的护栏' in script
    assert 'references/phases/05-material-catalog.md' in script


@pytest.mark.parametrize('doc_path', PHASE_DOCS, ids=lambda path: path.name)
def test_every_phase_has_guardrails_immediately_after_next_step(doc_path: Path):
    text = doc_path.read_text(encoding='utf-8')
    headings = re.findall(r'^## (.+)$', text, flags=re.MULTILINE)

    next_step = headings.index('下一步')
    assert headings[next_step + 1] == '护栏'
    if doc_path.name == '09-check-mix.md':
        # Phase 1 收集输入有自己的规则（不要逐项追问、要求要落地、不提前定模板），
        # 不再是一个空的“无”。
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


@pytest.mark.parametrize('relpath, required', [
    ('references/phases/02-paper-parse.md', ('MinerU 云端失败', '`-60007`', '`--pdf` 重试')),
    ('references/phases/03-research.md', ('Gemini UI 自动化很脆', '`web_search` 并把问题告诉用户')),
    ('references/phases/03-research.md', ('profile 被别的进程占着', '`--cdp-url`')),
    ('references/phases/04-material-harvest.md', ('返回 0 张图', '`--page-load-timeout`')),
    ('references/phases/04-material-harvest.md', ('profile 被别的进程占着', '`--cdp-url`')),
    ('references/phases/05-material-catalog.md', ('`delegate_to_agent`', 'Mode 2')),
    ('references/phases/07-voice-subtitles.md', ('外部 transcript', '`npx hyperframes transcribe`')),
    ('references/phases/07-voice-subtitles.md', ('OOM', '报告阻塞')),
])
def test_every_phase_keeps_the_recovery_it_needs_when_a_tool_fails(relpath: str, required: tuple):
    # Each case is a failure a phase has actually hit, plus the remedy that keeps
    # the agent from stalling or silently skipping the step.
    text = failure_handling(relpath)
    for phrase in required:
        assert phrase in text, f'{relpath} lost: {phrase}'


def test_phase7_recovery_says_how_to_resume_without_faking_audio():
    recovery = section(doc_text('references/phases/07-voice-subtitles.md'), '异常恢复')

    # An external transcript only helps if the run reuses this run's audio: the
    # default command deletes whatever sits at the transcript path.
    assert '`--align-only`' in recovery
    assert '会先删掉这个路径上已有的 transcript' in recovery
    assert '没有时间戳的纯文本不能用' in recovery
    # Chunked audio cannot be stitched back into one timeline, so the only
    # recovery offered is another configured backend.
    assert '分段合成' not in recovery
    assert '报告阻塞' in recovery


def test_troubleshooting_is_not_outsourced_to_a_shared_gotcha_file():
    # The agent reads exactly one phase doc; a symptom there with its remedy in
    # another file is a dead end.
    assert not (REPO_ROOT / 'references' / 'gotchas.md').exists()
    for doc_path in PHASE_DOCS:
        assert 'gotchas' not in doc_path.read_text(encoding='utf-8'), doc_path.name


def test_every_executable_script_is_documented_at_its_point_of_use():
    # The entry no longer keeps a table of every tool; the guarantee that matters
    # is that no CLI is left undocumented, and that it is documented where it is
    # used.
    scripts = REPO_ROOT / 'scripts'
    expected = {
        path.name
        for path in scripts.glob('*.py')
        if re.search(r"^if __name__ == ['\"]__main__['\"]:", path.read_text(encoding='utf-8'), flags=re.MULTILINE)
    }
    expected.add('fonts-download.sh')
    docs = [doc_text('SKILL.md'), doc_text('references/pipeline-control.md')]
    docs += [path.read_text(encoding='utf-8') for path in PHASE_DOCS]
    docs += sorted(
        path.read_text(encoding='utf-8')
        for path in (REPO_ROOT / 'references' / 'delegation').glob('**/*.md')
    )
    documented = {name for name in expected if any(name in text for text in docs)}

    assert documented == expected
    # And the entry itself does not grow the duplicate table back.
    assert '| `prepare-handoff.py` |' not in doc_text('SKILL.md')
    assert '| `voice-subtitles.py` |' not in doc_text('SKILL.md')


def test_delegation_resolves_the_target_before_choosing_how_to_dispatch():
    """原生 sub-agent 工具不等于能派发 Pi：先看目标，再选手段。"""
    text = doc_text('references/delegation/conventions.md')

    # 默认目标仍写在文档里。
    assert '默认 coding agent 是 **pi-coding-agent**' in text
    assert '`pi`' in text
    # 先解析 coding_agent，再判断工具能不能派发它。
    resolve_at = text.index('先确定目标')
    mechanism_at = text.index('再判断可用工具能不能派发这个目标')
    assert resolve_at < mechanism_at
    # 有原生工具 ≠ 能派发 Pi。
    assert '不等于' in text and 'Pi' in text
    # 用户点名的其他 agent 用自己的入口，不落回 Pi。
    assert '不要仍落到 `pi`' in text
    # 未知或不可用目标要明确报告，不静默替换。
    assert '不要静默换成别的 agent' in text
    # Pi 的已核实形态保留。
    assert 'pi -p -- "<dispatch_prompt>"' in text
    assert '--add-dir' not in text
