"""The phase docs and pipeline-status's PHASES table describe the same products.

Each phase doc lists its products in the "## 输出" section; pipeline-status
validates them from PHASES. A product that PHASES checks but the doc never
names would be demanded of an agent that was never told to write it.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

import harvest_manifest  # scripts/ 由 conftest.py 加入 sys.path

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_pipeline_status():
    spec = importlib.util.spec_from_file_location('pipeline_status', REPO_ROOT / 'scripts' / 'pipeline-status.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # @dataclass looks its module up here
    spec.loader.exec_module(module)
    return module


PHASES = load_pipeline_status().PHASES


def output_section(doc: Path) -> str:
    """The text under the doc's '## 输出' heading, up to the next '## ' heading."""
    match = re.search(r'^## 输出\n(.*?)(?=^## |\Z)', doc.read_text(encoding='utf-8'), re.MULTILINE | re.DOTALL)
    assert match, f'{doc.relative_to(REPO_ROOT)} has no "## 输出" section'
    return match.group(1)


@pytest.mark.parametrize('phase', PHASES, ids=[phase['id'] for phase in PHASES])
def test_every_product_checked_by_pipeline_status_is_named_in_the_phase_doc_output(phase):
    section = output_section(REPO_ROOT / phase['doc'])
    missing = [relpath for relpath in phase['products'] if relpath not in section]
    assert not missing, f'{phase["doc"]} "## 输出" does not name: {missing}'


def test_review_policy_is_opt_in_and_consistent_across_skill_and_phase_docs():
    skill = doc_text('SKILL.md')
    phase1 = doc_text('references/phases/01-gather-inputs.md')
    research = doc_text('references/phases/03-research.md')
    script = doc_text('references/phases/06-script-scene-plan.md')

    for text in (skill, phase1, research, script):
        assert 'approval_gates' in text
        assert '全自动' in text
        assert '`[]`' in text
    assert '不主动询问是否审稿' in skill
    assert '不主动询问是否审稿' in phase1
    assert '普通“继续”' in skill
    assert '不要用批量 `--approve`' in skill
    assert '校验合格后默认自动继续' in research
    assert '校验通过后默认自动进入 TTS' in script
    for text, gate in ((research, 'research-brief'), (script, 'script')):
        assert f'`approval_gates` 包含 `{gate}` 时' in text
        assert '未启用此 gate 时，不额外找用户审稿' in text
        assert '不用 `--approve` 代替' in text
    assert '只有启用了 `script` gate 才需重新确认' in script
    script_base = doc_text('references/delegation/script/base-instructions.md')
    assert '`approval_gates` 包含 `script` 时才由主 agent 找用户确认' in script_base
    assert '你不自行批准或决定取消审稿' in script_base


def test_phase_4_filters_media_before_phase_5():
    harvest = doc_text('references/phases/04-material-harvest.md')
    catalog = doc_text('references/phases/05-material-catalog.md')

    # 筛选是 Phase 4 的最后一步，标题层级与 4.a / 4.b 一致。
    assert harvest.count('\n### Phase 4.c') == 1
    assert harvest.index('### Phase 4.b') < harvest.index('### Phase 4.c')

    section = harvest.split('### Phase 4.c', 1)[1]
    # 尺寸门槛：位图沿用初抓门槛，视频用旋转无关的短边 / 长边。
    assert '宽 ≥500 px 且 高 ≥300 px' in section
    assert '短边 ≥360 px 且 长边 ≥640 px' in section
    assert '短边 ≥720 px 且 长边 ≥1280 px' in section
    assert 'SVG' in section
    # 清晰度靠看图 / 代表帧，不引入模糊度算法。
    assert '--max-frames 3' in section
    assert '--max-width' in section
    assert '不加 OpenCV' in section
    # 筛选结果写回 manifest，而不是只写进 notes。
    assert 'upsert_entries' in section
    assert 'scroll_recording' in section
    assert '原始媒体文件保留' in section

    # 下游只看筛选后的 manifest。
    assert '已做过尺寸 / 清晰度筛选' in catalog
    assert '回原目录' in catalog
    base = doc_text('references/delegation/catalog/base-instructions.md')
    assert '不要扫描 `images/` / `videos/` 目录' in base


def test_phase_4_documents_the_url_list_file_and_both_halves():
    harvest = doc_text('references/phases/04-material-harvest.md')
    script = doc_text('scripts/harvest-pages.py')

    # Phase 4.a / 4.b 是同一阶段内的两个步骤，标题层级必须一致。
    assert harvest.count('\n### Phase 4.a') == 1
    assert harvest.count('\n### Phase 4.b') == 1
    assert harvest.index('### Phase 4.a') < harvest.index('### Phase 4.b')

    # URL 走文件，不在命令行上展开列表。
    assert 'harvest-urls.txt' in harvest
    assert '--urls-file' in harvest
    assert '不要在命令行上展开' in harvest
    assert '--urls-file' in script

    # 清单是 Phase 4 自己生成的，不能直接把手研究文件当最终清单。
    assert '不是阶段产物' in harvest


def test_phase_4_output_examples_are_parseable_json():
    harvest = doc_text('references/phases/04-material-harvest.md')
    blocks = [json.loads(raw) for raw in re.findall(r'```json\n(.*?)```', harvest, re.DOTALL)]

    manifest = next(block for block in blocks if 'version' in block)
    assert manifest['version'] == 2
    assert set(manifest) == {
        'version', 'entries', 'pending_downloads', 'harvest_batches', 'updated_at',
    }
    page_entry, video_entry = manifest['entries']
    assert page_entry['images'] and page_entry['scroll_recording']
    assert video_entry['images'] == [] and video_entry['scroll_recording'] is None
    assert video_entry['videos'][0]['download_required'] is True
    assert manifest['pending_downloads'][0]['source_slug'] == video_entry['slug']

    # 批次 stdout 与磁盘 manifest 不是同一个结构。
    batch = next(block for block in blocks if 'batch_size' in block)
    assert 'chrome' in batch and 'version' not in batch
    assert len(batch['entries']) == batch['batch_size']

    # 下载结果：stdout 用绝对路径，manifest 更新用相对路径。
    download = next(block for block in blocks if 'files' in block)
    assert download['manifest_updated'] is True
    assert all(path.startswith('/') for path in download['files'])
    updated = next(block for block in blocks if 'download_required' in block and 'id' in block)
    assert updated['download_required'] is False and updated['downloaded'] is True


RECORDING_EXTENSIONS = {'playwright': '.webm', 'cdp_screencast': '.mp4'}


def test_phase_4_examples_match_the_slugs_and_recording_backend_they_claim():
    """示例得是真实输出：slug 来自实际规则，录制扩展名来自实际后端。"""
    harvest = doc_text('references/phases/04-material-harvest.md')
    blocks = [json.loads(raw) for raw in re.findall(r'```json\n(.*?)```', harvest, re.DOTALL)]
    manifest = next(block for block in blocks if 'version' in block)

    for entry in manifest['entries']:
        assert entry['slug'] == harvest_manifest.slug_for_url(entry['url'])
        for image in entry['images']:
            assert image['local_path'].startswith(f'{entry["slug"]}/')
        for video in entry['videos']:
            assert video['suggested_output_dir'] == f'{entry["slug"]}/videos'
        recording = entry['scroll_recording']
        if recording is not None:
            assert recording['local_path'].startswith(f'{entry["slug"]}/recording/')
            expected = RECORDING_EXTENSIONS[recording['method']]
            assert recording['local_path'].endswith(expected), (
                f'{recording["method"]} 录制应是 {expected}'
            )

    # 下载示例的目录、stdout 与 manifest 更新指向同一个 slug。
    video_slug = manifest['pending_downloads'][0]['source_slug']
    download = next(block for block in blocks if 'files' in block)
    assert download['output_dir'].endswith(f'{video_slug}/videos')
    assert all(f'{video_slug}/videos/' in path for path in download['files'])
    updated = next(block for block in blocks if 'download_required' in block and 'id' in block)
    assert updated['local_path'].startswith(f'{video_slug}/videos/')
    assert updated['id'] in updated['local_path']


def test_phase_4_separates_script_checks_from_the_executor_check():
    harvest = doc_text('references/phases/04-material-harvest.md')
    criteria = harvest.split('## 完成判据', 1)[1].split('## 执行后自检')[0]

    # pipeline-status 只校验 manifest 结构，下载是否逐项尝试是执行者的工作。
    assert 'pipeline-status' in criteria
    assert '它**不**检查下载是否尝试过' in criteria
    assert '执行者核对' in criteria


def test_login_gated_sources_are_harvestable_in_every_phase_that_filters_them():
    research = doc_text('references/phases/03-research.md')
    harvest = doc_text('references/phases/04-material-harvest.md')

    # 上游不能把它们提前滤掉，否则 Phase 4 根本看不到这些 URL。
    assert '不是聚合页或社交 feed' not in research
    research_sources = research.split('## Source URLs (for Phase 4 harvest)')[1]
    assert '需要登录才能看全的页面不必提前排除' in research_sources

    # Phase 4 不再用“需要登录”当排除理由，而是尽量用共享 profile 的登录态。
    exclude = harvest.partition('**EXCLUDE**')[2].split('URL 来源（按优先级）')[0]
    assert '社交媒体 feed' not in exclude
    assert '需要登录' not in exclude
    assert '不因“可能需要登录”提前排除' in harvest
    assert 'cookies' in harvest and 'localStorage' in harvest


def test_restricted_sources_are_recorded_and_reported_at_delivery():
    harvest = doc_text('references/phases/04-material-harvest.md')
    check_mix = doc_text('references/phases/09-check-mix.md')

    assert 'search-notes.md' in harvest
    assert '登录墙' in harvest

    assert 'search-notes.md' in check_mix
    delivery = check_mix.split('#### 9.6')[1]
    assert '--redo 4-material-harvest' in delivery
    assert 'qa-report.json' in delivery
    assert '不是阶段产物' in delivery


def test_catalog_package_skips_videos_without_a_local_file():
    catalog = doc_text('references/delegation/catalog/base-instructions.md')
    rule = catalog.split('## 公共视觉分析方式')[0]
    assert 'download_required: true' in rule
    assert '跳过这个视频' in rule
    # 素材没下到与工作区文件损坏是两件事，不能混着跳过。
    assert '工作区损坏' in rule


def test_phase7_owns_the_voice_subtitles_command_instead_of_the_skill_entry():
    doc = (REPO_ROOT / 'references/phases/07-voice-subtitles.md').read_text(encoding='utf-8')

    assert doc.count('python3 scripts/voice-subtitles.py {work_dir}/{topic_name}') == 1
    assert 'python3 scripts/voice-clone.py \\\n' not in doc
    assert 'python3 scripts/align-narration.py \\\n' not in doc
    assert 'python3 scripts/transcribe.py' not in doc
    assert 'failed_step' in doc
    assert '单独补跑转录' not in doc

    # The entry stopped keeping a full script table; the phase doc is where the
    # command, its flags and its failure handling live.
    skill = (REPO_ROOT / 'SKILL.md').read_text(encoding='utf-8')
    assert '--align-only' in doc
    assert '| `voice-subtitles.py` |' not in skill


def doc_text(relpath: str) -> str:
    return (REPO_ROOT / relpath).read_text(encoding='utf-8')


def test_paper_mode_instructions_live_in_the_phase_or_package_that_uses_them():
    paper_parse = doc_text('references/phases/02-paper-parse.md')
    research = doc_text('references/phases/03-research.md')
    script_base = doc_text('references/delegation/script/base-instructions.md')

    # Phase 3 researches: the paper prompt and the related-paper parse live there.
    assert '围绕论文《{title}》的背景调研' in research
    # The prompt placeholders come from disk (metadata.json), not from a past stdout.
    assert '{abstract}' in research
    assert 'harvest_page/main-paper/metadata.json' in research
    # Related papers come from Deep Research and are parsed before gap-finding.
    deep_research_at = research.index('3. **跑 Gemini Deep Research。**')
    related_at = research.index('4. **解析相关论文（可选，仅论文模式）。**')
    gaps_at = research.index('5. **找空缺。**')
    search_at = research.index('6. **按缺口搜索。**')
    brief_at = research.index('7. **合成研究 brief')
    assert deep_research_at < related_at < gaps_at < search_at < brief_at
    related_section = research[related_at:gaps_at]
    assert '--slug "related-' in related_section
    assert 'parse-pdf.py' in related_section
    assert '最多解析 5 篇' in related_section
    assert 'full_markdown_path' in related_section
    assert 'web_search' not in related_section
    # The original narration structure and figure rule move verbatim, without
    # adding related-paper slug or material-ID namespacing rules.
    assert '''Phase 6 撰写旁白时，论文模式沿用论文自身的逻辑流，而非通用的主题结构：

1. Hook —— 三句以内（见上面「开场钩子」）说明这篇论文要解决什么问题、为什么重要
2. Background —— 先前的工作和 SOTA（来自 Deep Research）
3. Key insight / approach（来自论文摘要 + 引言，引用论文中的 figure）
4. Method walkthrough（用 `material_ref` 引用论文 figure）
5. Results（用 `material_ref` 引用论文 table / chart）
6. Impact 与后续工作（来自 Deep Research）
7. Takeaway / CTA

论文 figure（`source_type: "paper_pdf"` 条目）是**首选**素材。从 web 抓取的资源作为补充 B-roll。叙述中合适时自然引用图号 / 表号：`"如表一所示..."`。''' in script_base
    assert 'related-foo_img_001' not in research
    assert 'related-foo_img_001' not in script_base
    assert '02-paper-parse' not in script_base
    assert '05-material-catalog' not in script_base
    # Phase 2 keeps only the main-paper parse.
    for moved in ('围绕论文《{title}》的背景调研', 'Takeaway / CTA', 'related-'):
        assert moved not in paper_parse, f'02-paper-parse.md still holds: {moved}'
    assert '--slug "main-paper"' in paper_parse


def test_phase_1_assures_paper_figures_at_the_visual_material_question():
    phase_1 = doc_text('references/phases/01-gather-inputs.md')
    assurance = '论文模式即使不联网搜索，论文自己的关键图也照样进视频'
    visual_question_at = phase_1.index('6. 视觉素材')
    input_detection_at = phase_1.index('9. **输入类型识别：**')
    assurance_at = phase_1.index(assurance)

    assert visual_question_at < assurance_at < input_detection_at
    assert phase_1.count(assurance) == 1


def test_every_phase_doc_names_what_to_check_after_running_it():
    # A phase whose products pass can still be wrong; each doc says what the
    # agent judges itself, right after the criteria the script enforces.
    merged_phase_doc = '07-voice-subtitles.md'
    for phase in PHASES:
        text = doc_text(phase['doc'])
        criteria = text.index('## 完成判据')
        next_step = text.index('## 下一步')
        assert criteria < next_step, f'{phase["doc"]} puts the self-check elsewhere'
        if phase['doc'].endswith(merged_phase_doc):
            # Phase 7 folds the executor check into 完成判据 so the reader sees the
            # script's guarantees and the human judgement in one place.
            assert '## 执行后自检' not in text, f'{phase["doc"]} splits the check again'
            criteria_section = text[criteria:next_step]
            assert '状态脚本校验' in criteria_section
            assert '执行者核对' in criteria_section
            continue
        assert '## 执行后自检' in text, f'{phase["doc"]} has no "## 执行后自检"'
        self_check = text.index('## 执行后自检')
        assert criteria < self_check < next_step, f'{phase["doc"]} puts the self-check elsewhere'


def test_the_entry_leaves_duration_and_orientation_to_the_phase_docs():
    skill = doc_text('SKILL.md')
    phase_1 = doc_text('references/phases/01-gather-inputs.md')

    # The description decides when the skill applies; length and orientation are
    # asked for in Phase 1, not promised as entry conditions.
    for worded in ('3-10 分钟', '3–10 分钟', '横屏或竖屏'):
        assert worded not in skill, f'SKILL.md still promises {worded}'
    # 没说的项走默认值（时长 3 分钟），不再要求拿默认值当问题去问用户。
    assert '用户没说就先问一句' not in phase_1


def test_search_and_redo_rules_are_stated_once_and_linked():
    skill = doc_text('SKILL.md')
    research = doc_text('references/phases/03-research.md')
    harvest = doc_text('references/phases/04-material-harvest.md')
    control = doc_text('references/pipeline-control.md')

    # Adaptive search with a cap instead of fixed counts and URL quotas.
    assert '10-15' not in research and '10-15' not in harvest
    assert '2-3 轮' not in research
    assert '最多 8 次' in research
    assert '连续两轮' in research
    assert 'search-notes.md' in research

    # Redo is an explicit request, not an inference from changed files.
    assert '--redo' in skill and '--finish' in skill
    assert 'references/pipeline-control.md' in skill
    assert '--redo' in control and '--finish' in control
    assert '不要把一次修复意见当成风格规则' in control
    # A user who names a platform search must still be served without making it
    # the default.
    assert 'material_search_requests' in phase_1_doc()
    assert 'material_search_requests' in harvest


def phase_1_doc() -> str:
    return doc_text('references/phases/01-gather-inputs.md')


def test_phase_4_no_longer_documents_merging_the_parsed_paper():
    assert 'Paper mode' not in doc_text('references/phases/04-material-harvest.md')


def test_catalog_docs_separate_media_tasks_and_use_a_defined_seven_point_threshold():
    catalog = doc_text('references/delegation/catalog/base-instructions.md')
    phase = doc_text('references/phases/05-material-catalog.md')

    for heading in ('## 公共视觉分析方式', '## 图片', '## 视频与滚动录像', '## 论文', '## 组合与切片段'):
        assert heading in catalog
    assert '1. **视觉理解：**' in catalog
    assert '2. **话题语义匹配：**' in catalog
    assert '3. **展示建议：**' in catalog
    assert '<7' in catalog and '<7' in phase
    assert '<5' not in catalog and '<5' not in phase
    assert '评分量表' in catalog
    assert '话题相关性 | 0–4' in catalog
    assert 'max(1, floor(D / max_frames))' in catalog
    assert '视频粗看每请求最多 8 帧' in catalog
    assert '不是把看图任务交回调用者' in catalog
    assert '不合格就重做本阶段' not in phase
    assert '不要靠手改 catalog' not in phase
    assert '不合格就自己重做' not in catalog


def test_catalog_defaults_to_ordered_coarse_frames_then_local_detail():
    catalog = doc_text('references/delegation/catalog/base-instructions.md')
    phase = doc_text('references/phases/05-material-catalog.md')
    flow = catalog.split('### 默认流程：多帧粗看 → 候选片段局部细看')[1].split('## 论文')[0]

    steps = ('1. **多帧粗看。**', '2. **提名候选窗口。**', '3. **候选片段局部细看。**', '4. **合成视频级结果。**')
    positions = [flow.index(step) for step in steps]
    assert positions == sorted(positions)
    for required in (
        '8 + 8 两批',
        '前一批的简短时序摘要',
        '--detail low',
        '不直接写成最终 `selected_clips`',
        '--detail high',
        '原帧最大宽度 1280 px',
        '--max-frames 20',
        '不能因上限截断而漏看后半段',
        '`frame_paths` 引用局部核对帧',
        '每张 4×4 拼图最多 16 帧',
        '每请求只输入一张拼图',
        '`sheets[*].prompt`',
        '作为整体理解',
        '源视频时间范围',
    ):
        assert required in flow
    assert '--max-frames 16 --max-width 512' in catalog
    assert '局部帧依据' in phase
    assert '每请求最多 8 帧' in phase
    assert 'scripts/stitch-frames.py' in catalog
    assert '调研依据：' not in catalog
    assert '不生成 4×4 拼图' not in flow
    assert '仅作为后续可评测' not in flow


def test_default_agent_and_command_live_only_in_the_conventions():
    for path in (REPO_ROOT / 'references').rglob('*.md'):
        text = path.read_text(encoding='utf-8')
        assert not re.search(r'默认\s+`?claude-code', text), str(path)
    # 默认目标与命令只在统一约定维护；各 phase / 模板只引用它，不复述默认 Pi 提示。
    conventions = doc_text('references/delegation/conventions.md')
    assert '默认 coding agent 是 **pi-coding-agent**' in conventions
    assert '`pi`' in conventions
    for doc in (
        'references/phases/01-gather-inputs.md',
        'references/phases/05-material-catalog.md',
        'references/phases/06-script-scene-plan.md',
        'references/phases/08-composition.md',
    ):
        text = doc_text(doc)
        assert 'references/delegation/conventions.md' in text, doc
        assert not re.search(r'默认[^\n。；]*pi-coding-agent', text), doc


def test_catalog_delegation_package_documents_the_paper_only_path():
    catalog = doc_text('references/delegation/catalog/base-instructions.md')
    section = catalog.split('## 仅论文素材')[1]
    assert 'score: 8' in section and 'caption' in section
    # An empty caption means no caption: those figures go through the VLM step.
    assert '空字符串' in catalog
    # Paper tables are often tall: layout hints are derived, not invented.
    assert 'viewport_reveal' in section
    assert 'focal_region' in section


def test_material_ref_contract_is_slug_qualified_across_phase_and_delegation_docs():
    phase_5 = doc_text('references/phases/05-material-catalog.md')
    assert '方案 A' in phase_5
    assert '只在所属 entry 内唯一' in phase_5
    assert '不改 harvester / manifest 的 id' in phase_5

    qualified_ref = '`<slug>/<id>`'
    qualified_clip = '`<slug>/<video_id>:<start>-<end>`'
    for doc in (
        'references/phases/05-material-catalog.md',
        'references/phases/06-script-scene-plan.md',
        'references/delegation/catalog/base-instructions.md',
        'references/delegation/script/base-instructions.md',
        'references/delegation/script/handoff-template.md',
        'references/delegation/composition/base-instructions.md',
        'references/delegation/composition/handoff-template.md',
    ):
        text = doc_text(doc)
        assert qualified_ref in text, doc
        assert qualified_clip in text, doc

    script_base = doc_text('references/delegation/script/base-instructions.md')
    assert '"ref": "example/img_001"' in script_base
    assert '裸 id' in script_base
    composition_base = doc_text('references/delegation/composition/base-instructions.md')
    assert '同一个 video id 出现在多个 entry' in composition_base


def test_phase_1_collects_inputs_without_interviewing_the_user():
    phase_1 = doc_text('references/phases/01-gather-inputs.md')

    # 标题只写阶段名，提问规则在正文。
    assert phase_1.startswith('# Phase 1 — 收集输入\n')
    assert '先把这些需求读全' in phase_1
    assert '一次问一个' in phase_1
    # 默认值：3 分钟；普通竖屏用 3:4，只有显式 9:16 才用 1080×1920。
    assert '没说用 3 分钟' in phase_1
    assert '默认横屏 `1920×1080`' in phase_1
    assert '用户说“竖屏”但没给比例时用 `1080×1440`' in phase_1
    assert '明确要 9:16 时才用 `1080×1920`' in phase_1
    # 委派默认目标：Phase 1 只引用统一约定，不复述默认 Pi 提示。
    assert '默认 `pi-coding-agent`' not in phase_1
    assert 'references/delegation/conventions.md' in phase_1
    assert 'claude-code' not in phase_1


def test_phase_1_owns_the_qa_field_without_asking_or_explaining_it_all():
    phase_1 = doc_text('references/phases/01-gather-inputs.md')

    assert '`quick` / `standard`（缺省）/ `strict`' in phase_1
    assert '只按用户明确要求写，不主动问' in phase_1
    assert '完整流程见 Phase 9' in phase_1
    # 档位的实现细节留在 Phase 9，不在这里展开。
    assert '在 Phase 1' not in phase_1.split('qa_level')[1].split('\n')[0]
    assert 'contact sheet' not in phase_1


def test_template_is_chosen_by_the_composition_agent():
    phase_1 = doc_text('references/phases/01-gather-inputs.md')
    phase_6 = doc_text('references/phases/06-script-scene-plan.md')
    phase_8 = doc_text('references/phases/08-composition.md')
    composition = doc_text('references/delegation/composition/base-instructions.md')

    # Phase 1 不选模板，也不提后续字幕流程。
    assert '| `template`' not in phase_1
    assert '模板由 Phase 8 的 composition agent 决定' in phase_1
    assert 'Phase 7' not in phase_1
    # Phase 6 不读模板、不依赖它。
    assert '模板不在本阶段输入里' in phase_6
    assert 'narration.md' not in phase_6
    # Phase 8 主 agent 只确认全片约束；视觉 scenes、模板与 layout 由被委派 agent 决定。
    assert text_index(phase_8, '#### 8.0 — 确认全片约束与派发前置条件') < text_index(
        phase_8, '#### 8.1 — 物化与字体'
    )
    assert '视觉 scenes、模板与 layout 不在这一步决定' in phase_8
    assert '不要求预先决定全局 template / layout' in phase_8
    assert 'composition/scene-config.json` 已存在' in phase_8
    assert '不命中就不用' in composition
    assert '不写回 `inputs.json`' in composition
    assert 'preferred_layouts' in composition


def test_phase_8_visual_scenes_are_outputs_not_handoff_preconditions():
    phase_8 = doc_text('references/phases/08-composition.md')
    outputs = phase_8.split('## 输出', 1)[1].split('## 完成判据', 1)[0]
    criteria = phase_8.split('## 完成判据', 1)[1].split('## 执行后自检', 1)[0]

    assert 'composition/scene-config.json' in outputs
    assert '{version: 1, canvas, total_s, scenes}' in outputs
    assert 'composition/scene-config.json' in criteria
    assert 'template' in criteria
    assert '不要求预先决定全局 template / layout' in phase_8
    assert 'align-narration.py --mode subtitles --scene-config ... --narration-audio ...' in phase_8


def test_paper_key_figures_are_declared_and_checked_end_to_end():
    phase_2 = doc_text('references/phases/02-paper-parse.md')
    phase_5 = doc_text('references/phases/05-material-catalog.md')
    phase_6 = doc_text('references/phases/06-script-scene-plan.md')
    phase_8 = doc_text('references/phases/08-composition.md')
    catalog_base = doc_text('references/delegation/catalog/base-instructions.md')
    composition_base = doc_text('references/delegation/composition/base-instructions.md')

    rule = '方法、模型结构、关键实验结果等关键图'
    assert rule in phase_2 and rule in phase_5
    assert 'required_material_refs' in phase_5 and 'required_material_refs' in phase_6
    assert 'required_material_refs' in phase_8
    assert 'required_material_refs' in catalog_base
    assert 'required_material_refs' in composition_base
    assert '覆盖表' in composition_base
    # 不改写既定取舍：关键图必须用，其余仍按素材质量筛选。
    assert 'VLM 评分 <5 或偏题' not in phase_5.split('required_material_refs')[1]


def text_index(text: str, needle: str) -> int:
    return text.index(needle)


def test_phase_1_says_nothing_about_layout():
    """Scene layouts belong to Phase 8; Phase 1 fixes only the global canvas."""
    phase_1 = doc_text('references/phases/01-gather-inputs.md')

    assert 'layout' not in phase_1
    assert 'presenter' not in phase_1
    assert 'stage' not in phase_1
    assert '`orientation`' in phase_1

    phase_8 = doc_text('references/phases/08-composition.md')
    assert '主 agent 不选择视觉 scene、模板或 layout' in phase_8
    assert 'modules/layouts/layouts.md' in phase_8
    assert 'composition/scene-config.json' in phase_8


def test_jay_generic_performance_and_github_specific_overlay():
    jay = doc_text('modules/components/jay/jay.md')
    generic = jay.split('### 通用演法')[1].split('### 动作库')[0]
    for cue in (
        '["wave", 3000]',
        'typing [切点 - 0.85, 切点 + 0.05]',
        '[该时刻, 1.0, "L"]',
        '[该时刻, 1.0, "U"]',
        '从下面的动作库挑一个合适的动作',
        '["laugh", 2200]',
        '["wave", 3200]',
    ):
        assert cue in generic
    for semantic_action in (
        '["smile", 2200]',
        '["idea", 2400]',
        '["question", 2400]',
        '["think", 2000]',
        '["sigh", 2600]',
        '["shake", 1600]',
        '["nod-small", 1000]',
    ):
        assert semantic_action not in generic

    action_library = jay.split('### 动作库（`acts`）')[1].split('### 常驻动作')[0]
    # 动作库不再按已删除的语义节拍分类：四列，按“适合的时刻”选。
    assert {
        line for line in action_library.splitlines() if line.startswith('| 动作 |')
    } == {'| 动作 | 推荐时长 | 表现 | 适合的时刻 |'}
    assert '对应 beat' not in jay
    for action in ('`question`', '`idea`', '`think`', '`eureka`', '`shake`', '`nod-small`'):
        assert action in action_library
    assert '同一时间只做一个动作' in action_library

    envelope = jay.split('### 嘴型数据（`envelope`）', 1)[1].split('## 限制', 1)[0]
    assert 'node components/jay/make-envelope.mjs 配音.wav > envelope.json' in envelope
    assert (
        'node modules/components/jay/make-envelope.mjs voice_clone/narration.mp3 '
        '> composition/assets/jay-envelope.json'
    ) in envelope
    assert 'VIDEO.jay.envelope' in envelope
    assert 'envelopeFps' in envelope
    assert '不是新增的阶段产物门槛' in envelope
    assert '换了配音，就要重新生成 envelope，并且按新配音的时间重排剧本' in envelope

    github = doc_text('modules/templates/github/github.md')
    overlay = github.split('## 5. 人物怎么演')[1]
    assert '先按 `components/jay/jay.md` 的通用演法' in overlay
    assert '[cue, 1.0, "U"]' in overlay
    assert '[cue + 1.7, 1.0, "L"]' in overlay
    assert '["eureka", 2700]' in overlay
    assert '封面的介绍出现时' in overlay and '瞥视 `"L"`' in overlay
    for generic_cue in ('["smile", 2200]', '["idea", 2400]', '["question", 2400]', '["lean", 2400]'):
        assert generic_cue not in overlay


def test_composition_requires_jay_for_presenter():
    composition = doc_text('references/delegation/composition/base-instructions.md')
    layout_rules = composition.split('## 三、必须遵守各 scene 的 layout 区域')[1].split('## 四、', 1)[0]
    section4 = composition.split('## 四、内容演绎与模板选择', 1)[1].split('## 五、', 1)[0]
    modules = doc_text('modules/modules.md')
    handoff_template = doc_text('references/delegation/composition/handoff-template.md')
    phase_8 = doc_text('references/phases/08-composition.md')

    assert 'reserved 区域只放各自 `component` 声明的组件' in layout_rules
    assert 'scene 的 regions 有人物区' in layout_rules
    assert '唯一常驻实例' in layout_rules
    assert '没有人物区的 scene 不强制显示 Jay' in layout_rules
    assert 'placements' in layout_rules
    assert '`modules/components/jay/jay.md`' in layout_rules or '`jay.md`' in layout_rules
    assert '有模板时再叠加模板的演法' in layout_rules
    assert 'make-envelope.mjs' not in composition
    assert '动作自己排' not in section4
    assert 'make-envelope.mjs' not in modules
    assert 'components/jay/jay.md' in modules
    assert 'components.md' in handoff_template and '组件索引' in handoff_template and '按需读要挂载的组件文档' in handoff_template
    assert 'components.md' in phase_8 and '组件索引' in phase_8 and '按需读要挂载的组件文档' in phase_8


def test_scene_plan_content_plan_and_opening_hook_contract():
    script_base = doc_text('references/delegation/script/base-instructions.md')
    phase_8 = doc_text('references/phases/08-composition.md')
    # 场景规划只到叙事层：内容与演绎方式，不预设模板 / pattern / 动作，也不保留未消费的 facts 字段。
    assert '"content_plan": "用哪些内容、按什么顺序和方式讲，来达成 intent"' in script_base
    assert '**不包含** `template_scene` / `pattern_hints` / `beats`' in script_base
    assert '`content_plan`：这场景讲什么、怎样展开' in script_base
    assert '"facts"' not in script_base and '`facts`' not in script_base
    assert '`facts`' not in phase_8
    # 解说角色定位与默认讲解风格（问题先行、直白易懂、日常例子与难点分步拆解），支持单次 narration_requests 覆盖。
    assert '善于把复杂主题讲给非专业观众听懂的解说者' in script_base
    assert '### 讲解方式与语言风格（所有模式共用）' in script_base
    assert '先引出问题，再展开机制' in script_base
    assert '拒绝空泛的 high-level 套话' in script_base
    assert '多举日常例子，难点分步拆解' in script_base
    assert '`narration_requests`' in script_base
    # 开场钩子：三句以内、方法可选、事实有据。
    assert '整个钩子不超过三句短句' in script_base
    assert '一种主钩子' in script_base
    assert '不要为了钩子编造事实' in script_base
    # 稿长按 7 字符/秒：不是 TTS 语速参数。
    assert '7 字符/秒' in script_base and '5min ≈ 2100 chars' in script_base
    assert '不指定 speech rate' in script_base
    assert '7.5 字符/秒' not in script_base

    composition = doc_text('references/delegation/composition/base-instructions.md')
    # 模板与 pattern 归 composition，不再按上游节拍映射动作。
    assert '## 四、内容演绎与模板选择' in composition
    assert '逐场景选择' in composition and '参考库按需' in composition
    assert 'beat → 画面' not in composition
    assert '语义节拍' not in composition
    assert '模板选择及理由写进 storyboard，不写回 `inputs.json`' in composition

    # 模板不再给旁白下指令：它由 composition 阶段选。
    assert not (REPO_ROOT / 'modules' / 'templates' / 'github' / 'narration.md').exists()
    assert '由 composition 阶段决定' in script_base


def test_composition_defaults_to_original_design_and_only_records_borrowed_references():
    composition = doc_text('references/delegation/composition/base-instructions.md')
    design = composition.split('## 四、内容演绎与模板选择', 1)[1].split('## 五、', 1)[0]

    assert '自主设计优先' in design
    assert '自主构思构图、视觉隐喻、信息展开与动效' in design
    assert '`modules/patterns/`、`modules/motion.md` 与 `modules/transitions/` 都是可跳过的参考入口' in design
    assert '才定向查阅' in design
    assert '内容关系、素材形态和区域约束高度吻合' in design
    assert '全片不用参考库也完全合格' in design
    assert '只在借用时' in design and '借用内容与匹配理由' in design
    assert '无需填写 pattern 字段或未使用理由' in design
    assert '简洁的静态呈现也是有效选择' in design

    # 表达与事实边界：自主表现机制、创意边界、新增屏幕事实来源、示意与证据边界。
    assert '### 表达与事实边界' in design
    boundary = design.split('### 表达与事实边界', 1)[1]
    assert 'DOM/SVG/CSS/Canvas/WebGL' in boundary
    assert 'modules/motion.md' in boundary
    assert '视觉创意服务于理解' in boundary
    assert '不得破坏所选 design token、各 scene 实际落盘的 regions、可读性、真实语音同步或事实含义' in boundary
    assert '`script.txt`' in boundary
    assert '`scene-plan.json`' in boundary
    assert '`material-catalog.json`' in boundary
    assert '`composition_requests`' in boundary
    assert '需要新增上游事实时向主 agent 报告并建议回退，不得自行编造' in boundary
    assert '图示、类比和示意可用于解释概念或关系，但不得伪装成真实数据或证据' in boundary
    assert '会改变事实含义的构图、标注与动画不使用' in boundary

    workflow = composition.split('## 工作顺序', 1)[1]
    assert '**自主构思并写 storyboard**' in workflow
    assert '字幕以显示稿为准，新增屏幕文字与标注守第四部分事实边界' in workflow
    assert '字幕与屏幕文字都以显示稿为准' not in workflow
    assert '素材、构图、信息展开与动效安排' in workflow
    assert '先定模板与 pattern' not in workflow
    assert '动效选择参考 `modules/motion.md`' not in workflow
    # 自主发挥不放松 design、区域与真实语音的边界。
    assert '默认时长、缓动与列表间隔跟随主题 token' in composition
    assert 'reserved 区域只放各自 `component` 声明的组件' in composition
    assert '时间只取真实语音' in composition


def test_pattern_and_motion_indexes_are_optional_and_not_a_fixed_design_sequence():
    patterns = doc_text('modules/patterns/patterns.md')
    motion = doc_text('modules/motion.md')
    for text in (patterns, motion):
        assert '**按需参考库**' in text
        assert 'composition 基础指令第四部分' in text

    assert '## 决定借用后怎么查' in patterns
    assert '不要求继续查阅 `motion.md`' in patterns
    assert '按 `motion.md` 的选择顺序定' not in patterns
    assert '## 动效构思的参考维度' in motion
    assert '没有固定顺序' in motion
    assert '构思从表达目标与素材出发' in motion
    assert '不要求每个 scene 有招牌机制或持续运动' in motion
    assert '只 animate opacity / transform' not in motion

    phase = doc_text('references/phases/08-composition.md')
    handoff = doc_text('references/delegation/composition/handoff-template.md')
    for text in (phase, handoff):
        assert '可选参考' in text
        assert 'transitions' in text
        assert '素材与 pattern 选择' not in text
        assert '模板 / pattern 的选择与理由' not in text


def test_transitions_are_a_top_level_module_category_without_stale_paths():
    modules = doc_text('modules/modules.md')
    components = doc_text('modules/components/components.md')
    transitions = doc_text('modules/transitions/transitions.md')
    tile_wipe = doc_text('modules/transitions/tile-wipe/tile-wipe.md')

    assert 'transitions/transitions.md' in modules
    assert 'transitions/tile-wipe/tile-wipe.md' in modules
    assert 'transitions/tile-wipe/tile-wipe.md' in tile_wipe
    assert 'VIDEO.cuts' in transitions
    assert '自由布局不强制使用转场' in transitions
    old_transition_path = 'components' + '/transitions'
    assert old_transition_path not in modules
    assert old_transition_path not in components
    assert old_transition_path not in tile_wipe

    for doc in (
        'references/delegation/composition/base-instructions.md',
        'references/delegation/composition/handoff-template.md',
        'references/phases/08-composition.md',
    ):
        text = doc_text(doc)
        assert '组件与转场使用表' in text
        assert '组件使用表' not in text
        assert '`cuts`' in text


def test_module_path_conventions_distinguish_prose_links_and_commands():
    modules = doc_text('modules/modules.md')
    assert '下文所有路径都相对 `modules/`' not in modules
    assert '正文（散文、表格、行内代码）里的路径引用相对 `modules/`' in modules
    assert 'Markdown 链接目标相对当前 Markdown 文件所在目录' in modules
    assert '阅读原始文档时也按此基准解析链接' in modules
    assert 'shell 命令从 skill 根目录（仓库根）写相对路径' in modules


@pytest.mark.parametrize('doc', [
    'modules/modules.md',
    'modules/templates/templates.md',
    'modules/layouts/layouts.md',
    'modules/components/components.md',
    'modules/motion.md',
    'modules/patterns/patterns.md',
])
def test_composition_reference_links_resolve_from_the_markdown_file(doc):
    match = re.search(r'\[composition 基础指令第四部分\]\(([^)]+)\)', doc_text(doc))
    assert match, doc
    relative_path, _, fragment = match.group(1).partition('#')
    target = (REPO_ROOT / doc).parent / relative_path
    assert target.resolve() == (REPO_ROOT / 'references/delegation/composition/base-instructions.md').resolve()
    assert target.is_file()
    assert fragment == '四内容演绎与模板选择'


def test_scene_module_adoption_rule_is_unified_across_base_handoff_phase_and_indexes():
    composition = doc_text('references/delegation/composition/base-instructions.md')
    section4 = composition.split('## 四、内容演绎与模板选择', 1)[1].split('## 五、', 1)[0]

    assert '默认即时生成，预定义模块是例外' in section4
    for required in (
        '先应用用户要求及其作用范围',
        '未指定时评估“特别匹配”，不是“勉强可用”',
        '模块表达的内容关系与 scene 的叙事目标一致',
        '素材形态、数据、画布、可读性和交互需求适合该模块',
        '不需要改旁白、视觉 scene、orientation 或用户要求来迁就模块',
        '采用它比即时生成更清楚或更可靠，而不只是少写代码',
        '没有特别匹配就即时生成',
        '按实际采用落盘',
        'template: null',
        'preset: null',
        '保持模块内部依赖完整',
        '只记录实际采用',
    ):
        assert required in section4

    for text in (
        composition.split('## 一、输入契约', 1)[1].split('## 二、', 1)[0],
        doc_text('references/delegation/composition/handoff-template.md'),
        doc_text('references/phases/08-composition.md'),
    ):
        assert '用户要求 → 特别匹配模块 → 即时生成' in text

    modules = doc_text('modules/modules.md')
    assert '发现入口，不是采用清单' in modules
    assert '阅读模块目录不等于采用模块' in modules

    templates = doc_text('modules/templates/templates.md')
    assert '特别匹配' in templates
    assert '`template: null`' in templates
    assert 'preferred_layouts' in templates

    layouts = doc_text('modules/layouts/layouts.md')
    assert '特别匹配' in layouts
    assert '`preset: null`' in layouts

    components = doc_text('modules/components/components.md')
    assert '特别匹配' in components
    assert '自绘所需部件' in components
    assert '不为了目录完整而挂 Jay/nav/转场' in components

    patterns = doc_text('modules/patterns/patterns.md')
    assert '特别匹配' in patterns
    assert '不借用' in patterns

    motion = doc_text('modules/motion.md')
    assert '特别匹配' in motion
    assert '保持静态' in motion



def test_composition_base_instructions_opening_lists_five_constraint_categories():
    composition = doc_text('references/delegation/composition/base-instructions.md')
    opening = composition.split('## 一、输入契约', 1)[0]

    for item in (
        '1. 输入、真实语音与素材契约；',
        '2. 所选 design 的 token 与字号约束；',
        '3. 各视觉 scene 实际落盘的 layout regions/caption；',
        '4. 逐场景内容演绎、template/layout 与自主设计；',
        '5. 模板时间锚点只能来自真实朗读。',
    ):
        assert item in opening

    assert '各视觉 scene' in opening
    assert '逐场景' in opening
    assert '工作顺序' in opening
    assert '其余视觉设计由 composition agent 决定' in opening
    assert '除此之外你没有别的规则' not in composition
    assert '主 agent 已选定 layout' not in composition
    assert '写回 inputs.json' not in opening

