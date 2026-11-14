"""Each theme Markdown holds the single-file CSS + metadata contract consistent with designs.md."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

import video_contract

REPO_ROOT = Path(__file__).resolve().parent.parent
DESIGNS_ROOT = REPO_ROOT / 'modules' / 'designs'
DESIGN_NAMES = ['default', 'github', 'producthunt']


def design_dir(name: str) -> Path:
    return DESIGNS_ROOT / name


def load_contract(name: str) -> dict:
    return video_contract.load_design_preset(REPO_ROOT, name)


def contract_tokens() -> set[str]:
    return set(video_contract.DESIGN_TOKEN_NAMES)


@pytest.mark.parametrize('name', DESIGN_NAMES)
def test_tokens_cover_the_shared_design_contract(name: str):
    contract = load_contract(name)

    assert contract['design'] == name
    assert set(contract['tokens']) == contract_tokens()


@pytest.mark.parametrize('name', DESIGN_NAMES)
def test_font_floors_match_the_markdown_and_omit_caption_font_px(name: str):
    text = (design_dir(name) / f'{name}.md').read_text(encoding='utf-8')
    floor_line = next(line for line in text.splitlines() if '字号下限' in line and '阅读文字不小于' in line)
    reading = int(re.search(r'阅读文字不小于\s*(\d+)px', floor_line).group(1))
    ui = int(re.search(r'界面小字不小于\s*(\d+)px', floor_line).group(1))
    contract = load_contract(name)

    assert contract['min_font_px'] == {'reading': reading, 'ui': ui}
    assert 'caption_font_px' not in contract
    assert '字幕 36px' not in floor_line
    assert '字幕（36px' not in text
    assert 'layout.caption.font_size_px' in floor_line


@pytest.mark.parametrize('name, fonts', [
    ('default', {
        'css_filename': 'default-fonts.css',
        'rename': {'Noto Sans SC': 'NotoSansSC', 'IBM Plex Mono': 'IBMPlexMono'},
        'css2_families': ['Noto+Sans+SC:wght@100..900', 'IBM+Plex+Mono:wght@400;500;600;700'],
    }),
    ('github', {
        'css_filename': 'github-fonts.css',
        'rename': {},
        'css2_families': [
            'Noto+Sans:wdth,wght@62.5..100,100..900',
            'Noto+Sans+SC:wght@100..900',
            'Noto+Sans+Mono:wdth,wght@62.5..100,100..900',
        ],
    }),
    ('producthunt', {
        'css_filename': 'producthunt-fonts.css',
        'rename': {'Noto Sans SC': 'NotoSansSC', 'IBM Plex Mono': 'IBMPlexMono'},
        'css2_families': ['Noto+Sans+SC:wght@100..900', 'IBM+Plex+Mono:wght@400;500;600;700'],
    }),
])
def test_font_metadata_migrates_without_changing_values(name: str, fonts: dict):
    assert load_contract(name)['fonts'] == fonts


def test_no_standalone_design_json_files_remain():
    assert list(DESIGNS_ROOT.glob('*/*.json')) == []


def test_parse_design_markdown_rejects_duplicated_tokens_or_broken_blocks(tmp_path: Path):
    source = (design_dir('default') / 'default.md').read_text(encoding='utf-8')
    doc = tmp_path / 'broken.md'

    doc.write_text(source.replace('"min_font_px"', '"tokens": {}, "min_font_px"'), encoding='utf-8')
    with pytest.raises(ValueError, match='exactly min_font_px and fonts'):
        video_contract.parse_design_markdown(doc)

    doc.write_text(source.replace('--c-canvas: #f3f1ec;', ''), encoding='utf-8')
    with pytest.raises(ValueError, match='--c-canvas'):
        video_contract.parse_design_markdown(doc)


def test_extension_docs_require_single_file_markdown_contracts():
    designs_text = (DESIGNS_ROOT / 'designs.md').read_text(encoding='utf-8')
    modules_text = (REPO_ROOT / 'modules' / 'modules.md').read_text(encoding='utf-8')

    assert '<主题>.md' in designs_text
    assert '<名>.md' in modules_text
    assert '不再单独拆' not in designs_text
    for text in (designs_text, modules_text):
        assert 'fonts.json' not in text
        assert 'caption_font_px' not in text
        assert '<名>.json' not in text
        assert '<主题>.json' not in text


def test_design_index_owns_shared_rules_and_states_positive_responsibilities():
    text = (DESIGNS_ROOT / 'designs.md').read_text(encoding='utf-8')
    first_para = text.split('\n\n')[1]

    for item in ('配色', '字体', '字号', '背景', '形状', '图标风格', '动效节奏'):
        assert item in first_para
    assert '不管内容，也不管版面' not in text
    for shared in ('字号阶梯（1920×1080）', 'tabular-nums', 'data-text-role="ui"', '2px', '16×16', 'repeat: -1'):
        assert shared in text


@pytest.mark.parametrize('name', DESIGN_NAMES)
def test_theme_docs_deduplicate_shared_sections_and_stale_font_prestage_copy(name: str):
    doc_path = design_dir(name) / f'{name}.md'
    text = doc_path.read_text(encoding='utf-8')
    contract = load_contract(name)

    assert '这份文档只规定外观' not in text
    assert '主题变量值' not in text
    assert '## 1. 配色' in text
    assert '## 2. 字体' in text
    assert '配色与机器配置' not in text
    assert '字号阶梯（1920×1080）' not in text
    assert '通用元素的外观' not in text
    assert '要做 / 不要做' not in text
    assert f'{name}.json' not in text
    assert contract['fonts']['css_filename'] in text
    assert 'fonts-download.sh' not in text
    assert 'resources/fonts/' not in text
    assert '预置在 `composition/assets/fonts/`' not in text

    headings = {
        match.group(1)
        for match in re.finditer(r'^#{2,3}\s+(\d+(?:\.\d+)?)', text, flags=re.MULTILINE)
    }
    for ref in re.findall(r'见\s*(?:第\s*)?(\d+(?:\.\d+)?)\s*(?:节)?', text):
        assert ref in headings, f'{name}: broken section reference {ref}'

    links = re.findall(r'\[[^\]]+\]\(([^)]+)\)', text)
    assert any(link.split('#', 1)[0] == '../designs.md' for link in links), name
    for link in links:
        rel_target = link.split('#', 1)[0]
        if not rel_target:
            continue
        target = (doc_path.parent / rel_target).resolve()
        assert target.is_file(), f'{name}: broken link {link}'
