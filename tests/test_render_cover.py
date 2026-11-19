"""Behavioral and browser integration tests for scripts/render-cover.py."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

from cli_helpers import load_script_module, parse_stdout

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / 'scripts' / 'render-cover.py'
PRESENTER_WAVE = REPO_ROOT / 'modules' / 'components' / 'presenter' / 'images' / 'presenter-wave.png'

render_mod = load_script_module('render-cover.py', 'render_cover_test_mod')
video_contract = load_script_module('video_contract.py', 'video_contract_cover_test_mod')


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )


def prepare_cover_assets(cover_dir: Path) -> None:
    assets = cover_dir / 'assets'
    assets.mkdir(parents=True, exist_ok=True)
    Image.new('RGB', (1200, 1200), (36, 48, 72)).save(assets / 'subject.png', format='PNG')
    shutil.copyfile(PRESENTER_WAVE, assets / 'presenter-wave.png')


def clean_portrait_html() -> str:
    slot = video_contract.cover_presenter_slot(1080, 1440)
    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; }}
  html, body {{
    width: 1080px; height: 1440px; margin: 0; padding: 0;
    overflow: hidden; position: relative; background: #111319; color: #F8FAFC;
    font-family: sans-serif;
  }}
  h1 {{
    position: absolute; left: 56px; top: 56px; margin: 0;
    font-size: 80px; line-height: 1.18; font-weight: 800; color: #F8FAFC;
  }}
  h1 span {{ display: block; white-space: nowrap; }}
  h1 em {{ font-style: normal; color: #F97316; }}
  .hero {{
    position: absolute; left: 48px; top: 272px; width: 984px; height: 880px;
    overflow: hidden; border-radius: 20px;
  }}
  .hero img.bg {{
    width: 100%; height: 100%; object-fit: cover; display: block;
  }}
  .stats {{
    position: absolute; left: 56px; top: 1188px; width: 640px; height: 160px;
    display: flex; gap: 36px; align-items: center;
  }}
  .stats strong {{ font-size: 56px; color: #F97316; font-variant-numeric: tabular-nums; }}
  .presenter {{
    position: absolute; left: {slot['x']}px; top: {slot['y']}px;
    width: {slot['size']}px; height: {slot['size']}px; z-index: 20; pointer-events: none;
  }}
  .presenter img.presenter-art {{ width: 100%; height: 100%; object-fit: contain; display: block; }}
</style>
</head>
<body>
  <h1 data-block>
    <span data-line>零接口跑通游戏</span>
    <span data-line>成本直降 <em>90%</em></span>
  </h1>
  <div class="hero" data-block data-subject>
    <img class="bg" src="assets/subject.png" alt="subject">
  </div>
  <div class="stats" data-block>
    <strong data-num>95.8%</strong>
    <strong data-num>12s</strong>
  </div>
  <div class="presenter" data-block>
    <img class="presenter-art" src="assets/presenter-wave.png" alt="">
  </div>
</body>
</html>
"""


def clean_landscape_html(width: int, height: int) -> str:
    slot = video_contract.cover_presenter_slot(width, height)
    sub_w = int(width * 0.54)
    sub_h = int(height * 0.88)
    sub_x = width - sub_w - 32
    sub_y = int((height - sub_h) / 2)
    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; }}
  html, body {{
    width: {width}px; height: {height}px; margin: 0; padding: 0;
    overflow: hidden; position: relative; background: #12151E; color: #FFFFFF;
    font-family: sans-serif;
  }}
  h1 {{
    position: absolute; left: 64px; top: 180px; margin: 0;
    font-size: 66px; line-height: 1.22; font-weight: 800; color: #FFFFFF;
  }}
  h1 span {{ display: block; white-space: nowrap; }}
  h1 em {{
    font-style: normal; background: #EA580C; color: #FFFFFF;
    padding: 0 10px; border-radius: 8px;
  }}
  .hero {{
    position: absolute; left: {sub_x}px; top: {sub_y}px;
    width: {sub_w}px; height: {sub_h}px; overflow: hidden; border-radius: 18px;
  }}
  .hero img.bg {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
  .stats {{
    position: absolute; left: 64px; bottom: 120px; width: 520px; height: 110px;
    display: flex; gap: 28px; align-items: center;
  }}
  .stats strong {{ font-size: 52px; color: #FACC15; font-variant-numeric: tabular-nums; }}
  .presenter {{
    position: absolute; left: {slot['x']}px; top: {slot['y']}px;
    width: {slot['size']}px; height: {slot['size']}px; z-index: 20; pointer-events: none;
  }}
  .presenter img.presenter-art {{ width: 100%; height: 100%; object-fit: contain; display: block; }}
</style>
</head>
<body>
  <h1 data-block>
    <span data-line>删掉一步反而快</span>
    <span data-line>吞吐暴涨 <em>3.2倍</em></span>
  </h1>
  <div class="hero" data-block data-subject>
    <img class="bg" src="assets/subject.png" alt="subject">
  </div>
  <div class="stats" data-block>
    <strong data-num>50.0% → 95.8%</strong>
    <strong data-num>3.2×</strong>
    <strong data-num>-90%</strong>
  </div>
  <div class="presenter" data-block>
    <img class="presenter-art" src="assets/presenter-wave.png" alt="">
  </div>
</body>
</html>
"""


def test_static_css_guardrails_reject_viewport_units_and_bare_img_selectors():
    assert render_mod.check_html_css_source(clean_portrait_html()) == []

    vw_html = '<style>.hero { width: 100vw; height: 60vh; } .hero img.bg { width: 100%; }</style>'
    assert 'vw_vh_forbidden' in dict(render_mod.check_html_css_source(vw_html))

    url_only = '<style>.hero { background: url("assets/scene_100vh.png"); }</style>'
    assert render_mod.check_html_css_source(url_only) == []

    for bad_sel in ('<style>img { width: 100%; }</style>', '<style>.hero img { width: 100%; }</style>'):
        assert 'bare_img_selector' in dict(render_mod.check_html_css_source(bad_sel))

    qualified = (
        '<style>@keyframes fade { from { opacity: 0; } to { opacity: 1; } } '
        '.hero img.bg, .presenter img.presenter-art, img[data-role="icon"] { width: 100%; }</style>'
    )
    assert render_mod.check_html_css_source(qualified) == []


def test_evaluate_cover_snapshot_catches_each_machine_rule():
    slot_16x9 = video_contract.cover_presenter_slot(1920, 1080)
    base_snapshot = {
        'doc': [1920, 1080],
        'fontsStatus': 'loaded',
        'brokenImages': [],
        'hasTopBar': False,
        'h1': {'left': 64, 'top': 200, 'right': 620, 'bottom': 380, 'x': 64, 'y': 200, 'width': 556, 'height': 180},
        'lines': [
            {'text': '删掉一步反而快', 'left': 64, 'right': 580, 'top': 200, 'bottom': 280, 'nowrap': True, 'wrappedRows': 1},
            {'text': '吞吐暴涨3.2倍', 'left': 64, 'right': 610, 'top': 290, 'bottom': 370, 'nowrap': True, 'wrappedRows': 1},
        ],
        'subject': {'left': 840, 'top': 60, 'right': 1888, 'bottom': 1020, 'x': 840, 'y': 60, 'width': 1048, 'height': 960},
        'presenter': {
            'left': slot_16x9['x'],
            'top': slot_16x9['y'],
            'right': slot_16x9['x'] + slot_16x9['size'],
            'bottom': slot_16x9['y'] + slot_16x9['size'],
            'width': slot_16x9['size'],
            'height': slot_16x9['size'],
        },
        'presenterSrc': 'assets/presenter-wave.png',
        'presenterImgRect': {'width': slot_16x9['size'], 'height': slot_16x9['size']},
        'stats': {'left': 64, 'top': 840, 'right': 560, 'bottom': 950},
        'cta': None,
        'nums': 3,
        'numRects': [
            {'left': 64, 'top': 850, 'right': 220, 'bottom': 940},
            {'left': 240, 'top': 850, 'right': 380, 'bottom': 940},
            {'left': 400, 'top': 850, 'right': 540, 'bottom': 940},
        ],
        'numTexts': ['95.8%', '3.2×', '-90%'],
        'blocks': 4,
    }
    findings, warnings, metrics = render_mod.evaluate_cover_snapshot(
        cover_id='1920x1080',
        width=1920,
        height=1080,
        snapshot=base_snapshot,
        static_issues=[],
        contrast_diff=0.82,
        allow_zero_num=False,
    )
    assert findings == []
    assert warnings == []
    assert metrics['nums'] == 3
    assert metrics['presenter_slot'] == slot_16x9

    # Dirty snapshot triggering overflow, top bar, >5 blocks, >3 nums, wrong presenter slot & asset,
    # bad title lines, tiny subject, lateral gap <40px, collisions, 16:9 badge intrusion, low contrast.
    dirty = {
        **base_snapshot,
        'doc': [1980, 1080],
        'hasTopBar': True,
        'blocks': 6,
        'nums': 4,
        'lines': [
            {
                'text': '这是一句超过十个字符的超长标题定语堆栈',
                'left': 64,
                'right': 820,
                'top': 240,
                'bottom': 320,
                'nowrap': False,
                'wrappedRows': 2,
            },
        ],
        'subject': {'left': 840, 'top': 200, 'right': 1240, 'bottom': 600},
        'presenter': {'left': 200, 'top': 850, 'right': 420, 'bottom': 1070, 'width': 220, 'height': 220},
        'presenterSrc': 'assets/presenter-base.png',
        'stats': {'left': 180, 'top': 860, 'right': 520, 'bottom': 960},
        'cta': {'left': 1760, 'top': 1010, 'right': 1900, 'bottom': 1070},
    }
    bad_findings, _, _ = render_mod.evaluate_cover_snapshot(
        cover_id='1920x1080',
        width=1920,
        height=1080,
        snapshot=dirty,
        static_issues=[],
        contrast_diff=0.35,
        allow_zero_num=False,
    )
    checks = {item['check'] for item in bad_findings}
    assert {
        'doc_overflow',
        'top_bar_forbidden',
        'visual_blocks_count',
        'num_count',
        'title_line_count',
        'title_nowrap',
        'title_char_limit',
        'subject_ratio',
        'presenter_asset_invalid',
        'presenter_slot_mismatch',
        'presenter_stats_overlap',
        'landscape_text_gap',
        'badge_safe_zone_intrusion',
        'title_contrast_low',
    } <= checks

    # Missing presenter emits presenter_missing.
    missing_p, _, _ = render_mod.evaluate_cover_snapshot(
        cover_id='1920x1080',
        width=1920,
        height=1080,
        snapshot={**base_snapshot, 'presenter': None},
        static_issues=[],
        contrast_diff=0.82,
        allow_zero_num=False,
    )
    assert any(f['check'] == 'presenter_missing' for f in missing_p)


def test_cli_usage_and_missing_dir_errors(tmp_path: Path):
    bad_size = run_cli(str(tmp_path), '--sizes', 'wide')
    assert bad_size.returncode == 2
    assert parse_stdout(bad_size)['success'] is False

    too_small = run_cli(str(tmp_path), '--sizes', '100x100')
    assert too_small.returncode == 2
    assert parse_stdout(too_small)['success'] is False

    missing_dir = run_cli(str(tmp_path / 'does_not_exist'))
    assert missing_dir.returncode == 1
    assert parse_stdout(missing_dir)['success'] is False


@pytest.mark.usefixtures('require_chrome')
def test_renders_all_three_default_sizes_with_fixed_waving_presenter_and_400px_thumbnails(tmp_path: Path):
    ws = tmp_path / 'ws'
    cover_dir = ws / 'cover'
    prepare_cover_assets(cover_dir)

    (cover_dir / 'cover_1080x1440.html').write_text(clean_portrait_html(), encoding='utf-8')
    (cover_dir / 'cover_1440x1080.html').write_text(clean_landscape_html(1440, 1080), encoding='utf-8')
    (cover_dir / 'cover_1920x1080.html').write_text(clean_landscape_html(1920, 1080), encoding='utf-8')

    report_path = cover_dir / 'cover-report.json'
    proc = run_cli(str(ws), '--output', str(report_path))
    assert proc.returncode == 0, proc.stderr
    result = parse_stdout(proc)

    assert result['success'] is True
    assert result['verdict'] == 'pass', result['findings']
    assert result['sizes'] == ['1080x1440', '1440x1080', '1920x1080']
    assert len(result['covers']) == 3
    assert json.loads(report_path.read_text(encoding='utf-8'))['verdict'] == 'pass'

    for size_str, expected_1x in (
        ('1080x1440', (1080, 1440)),
        ('1440x1080', (1440, 1080)),
        ('1920x1080', (1920, 1080)),
    ):
        with Image.open(cover_dir / f'cover_{size_str}.png') as im_1x:
            assert im_1x.size == expected_1x
        with Image.open(cover_dir / f'cover_{size_str}@2x.png') as im_2x:
            assert im_2x.size == (expected_1x[0] * 2, expected_1x[1] * 2)
        with Image.open(cover_dir / 'qa' / f'thumb_{size_str}_400w.png') as thumb:
            assert thumb.width == 400


@pytest.mark.usefixtures('require_chrome')
def test_browser_detects_missing_html_presenter_drift_and_low_contrast(tmp_path: Path):
    cover_dir = tmp_path / 'cover'
    prepare_cover_assets(cover_dir)

    # Low-contrast title (#888888 on #777777) + bare img selector + drifted presenter top; 1440x1080 missing.
    bad_html = (
        clean_portrait_html()
        .replace('#111319', '#777777')
        .replace('#F8FAFC', '#888888')
        .replace('.hero img.bg', '.hero img')
        .replace('top: 1084px;', 'top: 900px;')
    )
    (cover_dir / 'cover_1080x1440.html').write_text(bad_html, encoding='utf-8')

    proc = run_cli(str(cover_dir), '--sizes', '1080x1440', '1440x1080')
    assert proc.returncode == 0, proc.stderr
    result = parse_stdout(proc)
    assert result['verdict'] == 'fail'
    checks = {item['check'] for item in result['findings']}
    assert 'bare_img_selector' in checks
    assert 'presenter_slot_mismatch' in checks
    assert 'title_contrast_low' in checks
    assert 'html_missing' in checks
