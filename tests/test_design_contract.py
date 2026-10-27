"""The design JSON contracts stay complete and consistent with their docs."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DESIGNS_ROOT = REPO_ROOT / 'modules' / 'designs'
DESIGN_NAMES = ['default', 'github', 'producthunt']
TOKEN_PATTERN = re.compile(r'--c-[a-z0-9-]+|--font-[a-z]+|--motion-[a-z-]+|--ground')


def design_dir(name: str) -> Path:
    return DESIGNS_ROOT / name


def load_contract(name: str) -> dict:
    return json.loads((design_dir(name) / f'{name}.json').read_text(encoding='utf-8'))


def contract_tokens() -> set[str]:
    text = (DESIGNS_ROOT / 'designs.md').read_text(encoding='utf-8')
    tokens = set(TOKEN_PATTERN.findall(text))
    if {'--c-tile0', '--c-tile4'} <= tokens:
        tokens.update(f'--c-tile{index}' for index in range(5))
    return tokens


def markdown_tokens(name: str) -> dict[str, str]:
    text = (design_dir(name) / f'{name}.md').read_text(encoding='utf-8')
    blocks = re.findall(r'```css\s*:root\s*\{(.*?)\}\s*```', text, flags=re.DOTALL)
    assert len(blocks) == 1, name
    return {
        token: value.strip()
        for token, value in re.findall(r'(--[\w-]+)\s*:\s*([^;]+);', blocks[0])
    }


@pytest.mark.parametrize('name', DESIGN_NAMES)
def test_tokens_cover_the_shared_design_contract(name: str):
    contract = load_contract(name)

    assert contract['design'] == name
    assert set(contract['tokens']) == contract_tokens()


@pytest.mark.parametrize('name', DESIGN_NAMES)
def test_token_values_match_the_markdown_css(name: str):
    assert load_contract(name)['tokens'] == markdown_tokens(name)


@pytest.mark.parametrize('name', DESIGN_NAMES)
def test_font_floors_and_caption_size_match_the_markdown(name: str):
    text = (design_dir(name) / f'{name}.md').read_text(encoding='utf-8')
    floor_line = next(line for line in text.splitlines() if '字号下限' in line and '阅读文字不小于' in line)
    reading = int(re.search(r'阅读文字不小于\s*(\d+)px', floor_line).group(1))
    ui = int(re.search(r'界面小字不小于\s*(\d+)px', floor_line).group(1))
    caption = int(re.search(r'字幕\s*(\d+)px', floor_line).group(1))
    contract = load_contract(name)

    assert contract['min_font_px'] == {'reading': reading, 'ui': ui}
    assert contract['caption_font_px'] == caption


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


def test_only_theme_named_json_contracts_remain():
    assert sorted(path.name for path in DESIGNS_ROOT.glob('*/*.json')) == [
        'default.json', 'github.json', 'producthunt.json',
    ]
    assert list(DESIGNS_ROOT.glob('*/fonts.json')) == []


def test_extension_docs_require_markdown_and_json_contracts():
    for path in (DESIGNS_ROOT / 'designs.md', REPO_ROOT / 'modules' / 'modules.md'):
        text = path.read_text(encoding='utf-8')
        assert '<名>.json' in text
        assert 'fonts.json' not in text
