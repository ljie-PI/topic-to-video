"""Each theme Markdown holds the single-file CSS + metadata contract consistent with designs.md."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

import video_contract
from cli_helpers import parse_stdout

REPO_ROOT = Path(__file__).resolve().parent.parent
CHECK_COMPOSITION = REPO_ROOT / 'scripts' / 'check-composition.py'
DESIGNS_ROOT = REPO_ROOT / 'modules' / 'designs'
DESIGN_NAMES = ['default', 'github', 'producthunt']


def design_dir(name: str) -> Path:
    return DESIGNS_ROOT / name


def load_contract(name: str) -> dict:
    return video_contract.load_design_preset(REPO_ROOT, name)


def contract_tokens() -> set[str]:
    return set(video_contract.DESIGN_TOKEN_NAMES)


EXPECTED_FONTS = {
    'default': {
        'css_filename': 'default-fonts.css',
        'rename': {'Noto Sans SC': 'NotoSansSC', 'IBM Plex Mono': 'IBMPlexMono'},
        'css2_families': ['Noto+Sans+SC:wght@100..900', 'IBM+Plex+Mono:wght@400;500;600;700'],
    },
    'github': {
        'css_filename': 'github-fonts.css',
        'rename': {},
        'css2_families': [
            'Noto+Sans:wdth,wght@62.5..100,100..900',
            'Noto+Sans+SC:wght@100..900',
            'Noto+Sans+Mono:wdth,wght@62.5..100,100..900',
        ],
    },
    'producthunt': {
        'css_filename': 'producthunt-fonts.css',
        'rename': {'Noto Sans SC': 'NotoSansSC', 'IBM Plex Mono': 'IBMPlexMono'},
        'css2_families': ['Noto+Sans+SC:wght@100..900', 'IBM+Plex+Mono:wght@400;500;600;700'],
    },
}


@pytest.mark.parametrize('name', DESIGN_NAMES)
def test_theme_markdown_contract_tokens_floors_fonts_and_links(name: str):
    doc_path = design_dir(name) / f'{name}.md'
    text = doc_path.read_text(encoding='utf-8')
    contract = load_contract(name)

    assert contract['design'] == name
    assert set(contract['tokens']) == contract_tokens()
    assert contract['fonts'] == EXPECTED_FONTS[name]

    floor_line = next(line for line in text.splitlines() if '字号下限' in line and '阅读文字不小于' in line)
    reading = int(re.search(r'阅读文字不小于\s*(\d+)px', floor_line).group(1))
    ui = int(re.search(r'界面小字不小于\s*(\d+)px', floor_line).group(1))
    assert contract['min_font_px'] == {'reading': reading, 'ui': ui}
    assert 'caption_font_px' not in contract
    assert contract['fonts']['css_filename'] in text

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


def test_parse_design_markdown_rejects_duplicated_tokens_or_broken_blocks(tmp_path: Path):
    assert list(DESIGNS_ROOT.glob('*/*.json')) == []
    source = (design_dir('default') / 'default.md').read_text(encoding='utf-8')
    doc = tmp_path / 'broken.md'

    doc.write_text(source.replace('"min_font_px"', '"tokens": {}, "min_font_px"'), encoding='utf-8')
    with pytest.raises(ValueError, match='exactly min_font_px and fonts'):
        video_contract.parse_design_markdown(doc)

    doc.write_text(source.replace('--c-canvas: #f3f1ec;', ''), encoding='utf-8')
    with pytest.raises(ValueError, match='--c-canvas'):
        video_contract.parse_design_markdown(doc)


def test_every_design_doc_yields_reading_and_ui_floors(tmp_path: Path):
    snapshots = tmp_path / 'snapshots.json'
    snapshots.write_text('[]', encoding='utf-8')
    for name in DESIGN_NAMES:
        proc = subprocess.run(
            [
                sys.executable,
                str(CHECK_COMPOSITION),
                str(tmp_path),
                '--layout', str(REPO_ROOT / 'modules' / 'layouts' / 'landscape.json'),
                '--design', str(design_dir(name) / f'{name}.md'),
                '--snapshots-from', str(snapshots),
            ],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, f'{name}: {proc.stderr}'
        report = parse_stdout(proc)
        assert (report['min_font_size'], report['min_ui_font_size']) == (26, 22), name
