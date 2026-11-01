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

    # 持久化的媒体路径相对 harvest_page/，不能出现绝对路径。
    paths = [page_entry['images'][0]['local_path'],
             page_entry['scroll_recording']['local_path'],
             video_entry['videos'][0]['suggested_output_dir']]
    assert all(not path.startswith('/') for path in paths)

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
    assert not updated['local_path'].startswith('/')


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
            assert not video['suggested_output_dir'].startswith('/')
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
    _, steps = catalog.split('**每一条 harvest entry（每个 URL 一条）：**', 1)

    rule = steps.split('1. **抽帧**')[0]
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
    assert '{title}' in research and '{abstract}' in research
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

1. Hook —— 这篇论文为什么重要 / 它要解决什么问题
2. Background —— 先前的工作和 SOTA（来自 Deep Research）
3. Key insight / approach（来自论文摘要 + 引言，引用论文中的 figure）
4. Method walkthrough（用 `material_ref` 引用论文 figure）
5. Results（用 `material_ref` 引用论文 table / chart）
6. Impact 与后续工作（来自 Deep Research）
7. Takeaway / CTA

论文 figure（`source_type: "paper_pdf"` 条目）是**首选**素材。从 web 抓取的资源作为补充 B-roll。叙述中合适时自然引用图号 / 表号：`"如表一所示..."`。''' in script_base
    assert 'related-foo_img_001' not in research
    assert 'related-foo_img_001' not in script_base
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
    assert '没说用 3 分钟' in phase_1
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
    # 委派默认 Pi。
    assert '默认 `pi-coding-agent`' in phase_1
    assert 'claude-code' not in phase_1


def test_phase_1_owns_the_qa_field_without_asking_or_explaining_it_all():
    phase_1 = doc_text('references/phases/01-gather-inputs.md')

    assert '`quick` / `standard`（缺省）/ `strict`' in phase_1
    assert '只按用户明确要求写，不主动问' in phase_1
    assert '完整流程见 Phase 9' in phase_1
    # 档位的实现细节留在 Phase 9，不在这里展开。
    assert '在 Phase 1' not in phase_1.split('qa_level')[1].split('\n')[0]
    assert 'contact sheet' not in phase_1


def test_template_is_a_phase_8_decision():
    phase_1 = doc_text('references/phases/01-gather-inputs.md')
    phase_6 = doc_text('references/phases/06-script-scene-plan.md')
    phase_8 = doc_text('references/phases/08-composition.md')

    # Phase 1 不选模板，也不提后续字幕流程。
    assert '| `template`' not in phase_1
    assert '模板是 Phase 8 的画面选择' in phase_1
    assert 'Phase 7' not in phase_1
    # Phase 6 不读模板、不依赖它。
    assert '模板不在本阶段输入里' in phase_6
    assert 'narration.md' not in phase_6
    # Phase 8 先定 layout 与模板，再准备 handoff。
    assert text_index(phase_8, '#### 8.0 — 选 layout 与 template') < text_index(
        phase_8, '#### 8.1 — 物化与字体'
    )
    assert '不命中就不选' in phase_8
    assert '约束优先于模板' in phase_8
    assert '`template` 为 null 时 handoff 里写“无”' in phase_8


def test_paper_key_figures_are_declared_and_checked_end_to_end():
    phase_1 = doc_text('references/phases/01-gather-inputs.md')
    phase_2 = doc_text('references/phases/02-paper-parse.md')
    phase_5 = doc_text('references/phases/05-material-catalog.md')
    phase_6 = doc_text('references/phases/06-script-scene-plan.md')
    phase_8 = doc_text('references/phases/08-composition.md')
    catalog_base = doc_text('references/delegation/catalog/base-instructions.md')
    composition_base = doc_text('references/delegation/composition/base-instructions.md')

    rule = '方法、模型结构、关键实验结果等关键图'
    assert f'论文模式即使不联网搜索，论文自己的关键图也照样进视频' in phase_1
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
    """layout 是 Phase 8 的画面决定：Phase 1 不选、不指引、也不解释归属。"""
    phase_1 = doc_text('references/phases/01-gather-inputs.md')

    assert '| `layout`' not in phase_1
    assert 'layout' not in phase_1
    # presenter / stage 只在 layout 语境里出现。
    assert 'presenter' not in phase_1
    assert 'stage' not in phase_1

    # 朝向仍然由本阶段确定，三档写清楚。
    assert '`orientation`' in phase_1
    assert '1080×1440' in phase_1 and '1080×1920' in phase_1 and '1920×1080' in phase_1

    # 画面决定归 Phase 8。
    phase_8 = doc_text('references/phases/08-composition.md')
    assert '先定 layout' in phase_8
    assert 'presenter' in phase_8 and 'stage' in phase_8

    presenter = doc_text('modules/layouts/presenter.md')
    assert '带主持人的通用横屏布局' in presenter
    assert '用不用模板都可以选它' in presenter


def test_jay_generic_performance_and_github_specific_overlay():
    jay = doc_text('modules/components/jay/jay.md')
    generic = jay.split('### 通用演法')[1].split('### 动作库')[0]
    generic_rows = [line for line in generic.splitlines() if line.startswith('| ')][1:]
    assert len(generic_rows) == 6
    for cue in (
        '["wave", 3000]',
        'typing [切点 - 0.85, 切点 + 0.05]',
        '[该时刻, 1.0, "L"]',
        '[该时刻, 1.0, "U"]',
        'beat → 画面',
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
    assert action_library.count('| 动作 | 推荐时长 | 表现 | 适合的时刻 | 对应 beat |') == 2
    for action, beat in (
        ('`question`', 'question'),
        ('`idea`', 'idea'),
        ('`think`', 'caveat'),
        ('`sigh`', 'caveat'),
        ('`eureka`', 'highlight（数字）'),
        ('`smile`', 'highlight（非数字）'),
        ('`shake`', 'negation'),
        ('`nod-small`', 'confirm'),
    ):
        row = next(line for line in action_library.splitlines() if line.startswith(f'| {action} |'))
        assert row.endswith(f'| {beat} |')

    github = doc_text('modules/templates/github/github.md')
    overlay = github.split('## 5. 人物怎么演')[1]
    assert '先按 `components/jay/jay.md` 的通用演法' in overlay
    overlay_rows = [line for line in overlay.splitlines() if line.startswith('| ')][1:]
    assert len(overlay_rows) == 3
    assert '[cue, 1.0, "U"]' in overlay
    assert '[cue + 1.7, 1.0, "L"]' in overlay
    assert '["eureka", 2700]' in overlay
    assert '封面的介绍出现时' in overlay and '瞥视 `"L"`' in overlay
    for generic_cue in ('["smile", 2200]', '["idea", 2400]', '["question", 2400]', '["lean", 2400]'):
        assert generic_cue not in overlay


def test_composition_requires_jay_for_presenter():
    composition = doc_text('references/delegation/composition/base-instructions.md')
    layout_rules = composition.split('## 三、必须遵守 layout 区域')[1].split('## 工作顺序')[0]

    assert 'layout 有人物区（presenter）时必须挂 `jay`' in layout_rules
    assert '`VIDEO.jay` 按 `jay.md` 的通用演法编排' in layout_rules
    assert '有模板时再叠加模板的演法' in layout_rules
    assert 'node modules/components/jay/make-envelope.mjs voice_clone/narration.mp3' in layout_rules


def test_scene_plan_beats_authoring_and_composition_contract():
    script_base = doc_text('references/delegation/script/base-instructions.md')
    assert '"beats": [{"type": "idea", "text": "原样取自显示稿的一小段"}]' in script_base
    for beat_type in ('question', 'idea', 'caveat', 'highlight', 'negation', 'confirm'):
        assert f'`{beat_type}`' in script_base
    assert '8–30 个字符' in script_base
    assert '平均每分钟不超过 4 个' in script_base
    assert '两个 beat 的文本不能重叠' in script_base
    assert '这个字段可以省略' in script_base

    composition = doc_text('references/delegation/composition/base-instructions.md')
    beat_mapping = composition.split('## 四、把语义节拍落到画面')[1].split('## 工作顺序')[0]
    assert composition.count('| type | 有 Jay（presenter） | 没有 Jay |') == 1
    for row in (
        '| question | `["question", 2400]` | 按所选 design 第 6、7 节的强调写法，强调对应的提问文字 |',
        '| idea | `["idea", 2400]` | 按所选 design 的强调写法，强调关键句或图示 |',
        '| caveat | `["think", 2000]` 加一条不超过 4 个字的 `thoughts`，或 `["sigh", 2600]` | 对应信息用 `--c-warning` 左线的 callout 出现 |',
        '| highlight | 数字类用 `["eureka", 2700]`，其他用 `["smile", 2200]` | 按所选 design 的强调写法，强调数字或关键词 |',
        '| negation | `["shake", 1600]` | 对应项打 ✗，文字降为 `--c-ink2` |',
        '| confirm | `["nod-small", 1000]` | 不加额外动效 |',
    ):
        assert row in beat_mapping
    assert '动作从 `begin_s` 开始' in beat_mapping
    assert '后一个顺延' in beat_mapping

    # 模板不再给旁白下指令：它是 Phase 8 的画面选择。
    assert not (REPO_ROOT / 'modules' / 'templates' / 'github' / 'narration.md').exists()
    assert '是 Phase 8 的画面选择' in script_base
