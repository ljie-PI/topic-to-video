"""The phase docs and pipeline-status's PHASES table describe the same products.

Each phase doc lists its products in the "## 输出" section; pipeline-status
validates them from PHASES. A product that PHASES checks but the doc never
names would be demanded of an agent that was never told to write it.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

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


def test_phase7_offers_one_voice_clone_command_without_a_manual_asr_fallback():
    doc = (REPO_ROOT / 'references/phases/07-voice-subtitles.md').read_text(encoding='utf-8')
    section = doc.split('#### 7.1 —', 1)[1].split('#### 7.2 —', 1)[0]

    assert 'python3 scripts/voice-clone.py' in section
    assert 'python3 scripts/transcribe.py' not in section
    assert '单独补跑转录' not in section


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
    search_at = research.index('6. **做有针对性的搜索。**')
    brief_at = research.index('7. **合成研究 brief')
    assert deep_research_at < related_at < gaps_at < search_at < brief_at
    related_section = research[related_at:gaps_at]
    assert '--slug "related-' in related_section
    assert 'parse-pdf.py' in related_section
    assert '最多解析 2 篇' in related_section
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
    assurance = '论文模式下，论文自己的 figure 无论如何都会用上'
    visual_question_at = phase_1.index('7. 询问是否需要搜索视觉素材')
    input_detection_at = phase_1.index('8. **输入类型识别：**')
    assurance_at = phase_1.index(assurance)

    assert visual_question_at < assurance_at < input_detection_at
    assert phase_1.count(assurance) == 1
    assert '评分过滤仍然适用' not in phase_1


def test_phase_4_no_longer_documents_merging_the_parsed_paper():
    assert 'Paper mode' not in doc_text('references/phases/04-material-harvest.md')


def test_phase_5_documents_the_paper_only_path():
    catalog = doc_text('references/phases/05-material-catalog.md')
    section = catalog.split('## 仅论文素材')[1]
    assert 'score: 8' in section and 'caption' in section
    # An empty caption means no caption: those figures go through the VLM step.
    assert '空字符串' in catalog
    # Paper tables are often tall: layout hints are derived, not invented.
    assert 'viewport_reveal' in section
    assert 'focal_region' in section
