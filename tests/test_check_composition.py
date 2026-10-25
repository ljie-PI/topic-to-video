"""Integration tests for scripts/check-composition.py.

The test seam is the script's command line (repo convention: stdout = one
JSON, exit 0 = run completed with verdict pass/fail, 1 = runtime error,
2 = usage). Fixture compositions are tiny static HTML files built in tmp
dirs and measured through system Chrome + Playwright (required dependencies:
without them these tests fail via the require_chrome fixture, never skip).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.usefixtures('require_chrome')

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / 'scripts' / 'check-composition.py'
PRESENTER_LAYOUT = REPO_ROOT / 'modules' / 'layouts' / 'presenter.json'

SUBTITLE_UNITS = {
    'units': [
        {'text': '大家好', 'begin_s': 0.0, 'end_s': 20.0},
    ]
}

TIMELINE = {
    'version': 1,
    'total_s': 20.0,
    'scenes': [
        {'scene_id': 's1', 'begin_s': 0.0, 'end_s': 10.0},
        {'scene_id': 's2', 'begin_s': 10.0, 'end_s': 20.0},
    ],
}

BASE_CSS = """
  html, body { margin: 0; width: 1920px; height: 1080px; overflow: hidden; }
  * { box-sizing: border-box; }
"""

# Static fixtures toggle scene visibility from the check-time event the script
# dispatches at every seek (see scripts/check-composition.py), so each scene's
# check times only see that scene's elements.
SCENE_TOGGLE_JS = """
  document.addEventListener('check-time', (event) => {
    const time = event.detail.time;
    document.querySelectorAll('[data-scene-id]').forEach((el) => {
      const start = parseFloat(el.getAttribute('data-scene-start') || '0');
      const end = parseFloat(el.getAttribute('data-scene-end') || '1e9');
      el.style.visibility = (time >= start && time <= end) ? 'visible' : 'hidden';
    });
  });
"""

SCENE_ATTRS = 'data-scene-id="{sid}" data-scene-start="{start}" data-scene-end="{end}"'


def scene(sid: str, start: float, end: float, inner: str) -> str:
    return (
        f'<div {SCENE_ATTRS.format(sid=sid, start=start, end=end)} '
        f'style="position:absolute; inset:0;">{inner}</div>'
    )


CAPTION_BAR = """
  <div id="caption-bar" style="position:absolute; left:0; top:1008px; width:1920px; height:72px;">
    <span id="caption-text" style="font-size:36px;">大家好</span>
  </div>
"""

JAY = """
  <div id="jay" style="position:absolute; left:1294px; top:642px; width:420px; height:420px;
       background:#cccccc;"></div>
"""

CLEAN_SCENE = """
  <div class="panel" style="position:absolute; left:96px; top:196px; width:800px; height:400px;
       font-size:30px; line-height:1.4;">正常内容文本</div>
"""

DIRTY_SCENE = """
  <div class="panel" style="position:absolute; left:96px; top:196px; width:800px; height:400px;
       font-size:30px; line-height:1.4;">正常内容文本</div>
  <div class="stray" style="position:absolute; left:1700px; top:400px; width:400px; height:100px;
       background:#eeeeee;">越出画面的元素</div>
  <div class="intruder" style="position:absolute; left:200px; top:1020px; width:300px; height:40px;
       background:#ffdddd;">压住字幕区的元素</div>
  <div class="overflow" style="position:absolute; left:96px; top:640px; width:300px; height:44px;
       overflow:hidden; font-size:30px; line-height:1.2;">这是一段很长很长一定会溢出固定高度的文本内容</div>
  <img class="shot" src="missing-image.png"
       style="position:absolute; left:1184px; top:100px; width:400px; height:300px;" />
  <div class="tiny" style="position:absolute; left:96px; top:720px; width:200px; height:30px;
       font-size:12px;">小字</div>
"""


def write_composition(tmp_path: Path, scenes: list[str]) -> Path:
    comp = tmp_path / 'composition'
    comp.mkdir(parents=True)
    html = (
        '<!doctype html><html><head><meta charset="utf-8">'
        f'<style>{BASE_CSS}</style></head><body>'
        + ''.join(scenes)
        + f'<script>{SCENE_TOGGLE_JS}</script>'
        + '</body></html>'
    )
    (comp / 'index.html').write_text(html, encoding='utf-8')
    return comp


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


def run_check(tmp_path: Path, comp: Path, *, units=None, timeline=None) -> tuple:
    args = [
        str(comp),
        '--layout', str(PRESENTER_LAYOUT),
        '--min-font-size', '22',
    ]
    if units is not None:
        units_path = tmp_path / 'subtitle-units.json'
        write_json(units_path, units)
        args += ['--subtitle-units', str(units_path)]
    if timeline is not None:
        timeline_path = tmp_path / 'timeline.json'
        write_json(timeline_path, timeline)
        args += ['--timeline', str(timeline_path)]
    proc = run_cli(*args)
    result = json.loads(proc.stdout)
    return proc, result


def checks_of(result: dict) -> set[tuple[str, str]]:
    return {(finding['scene_id'], finding['check']) for finding in result['findings']}


# --- fixture with deliberately broken elements -----------------------------------


def test_dirty_fixture_reports_each_check(tmp_path: Path):
    comp = write_composition(
        tmp_path,
        [
            scene('s1', 0.0, 10.0, DIRTY_SCENE + CAPTION_BAR),
            scene('s2', 10.0, 20.0, CLEAN_SCENE + CAPTION_BAR),
        ],
    )
    proc, result = run_check(tmp_path, comp, units=SUBTITLE_UNITS, timeline=TIMELINE)
    assert proc.returncode == 0
    assert result['success'] is True
    assert result['verdict'] == 'fail'
    checks = checks_of(result)
    assert ('s1', 'outside_content_regions') in checks
    assert ('s1', 'reserved_region_intrusion') in checks
    assert ('s1', 'text_overflow') in checks
    assert ('s1', 'media_load_failure') in checks
    assert ('s1', 'font_size_below_min') in checks
    # s2 is clean: every finding belongs to s1
    assert all(finding['scene_id'] == 's1' for finding in result['findings'])
    for finding in result['findings']:
        assert finding['detail']


def test_out_of_bounds_finding_carries_scene_id(tmp_path: Path):
    comp = write_composition(
        tmp_path,
        [
            scene('s1', 0.0, 10.0, CLEAN_SCENE),
            scene(
                's2',
                10.0,
                20.0,
                '<div class="stray" style="position:absolute; left:1750px; top:400px; '
                'width:400px; height:100px; font-size:30px; background:#eeeeee;">越界</div>',
            ),
        ],
    )
    proc, result = run_check(tmp_path, comp, timeline=TIMELINE)
    assert proc.returncode == 0
    assert checks_of(result) == {('s2', 'outside_content_regions')}


# --- clean fixture ----------------------------------------------------------------


def test_clean_fixture_passes(tmp_path: Path):
    comp = write_composition(
        tmp_path,
        [
            scene('s1', 0.0, 10.0, CLEAN_SCENE + CAPTION_BAR + JAY),
            scene('s2', 10.0, 20.0, CLEAN_SCENE + CAPTION_BAR + JAY),
        ],
    )
    proc, result = run_check(tmp_path, comp, units=SUBTITLE_UNITS, timeline=TIMELINE)
    assert proc.returncode == 0
    assert result['success'] is True
    assert result['verdict'] == 'pass'
    assert result['findings'] == []


def test_caption_mismatch_is_found(tmp_path: Path):
    comp = write_composition(
        tmp_path,
        [scene('s1', 0.0, 10.0, CLEAN_SCENE + CAPTION_BAR)],
    )
    units = {'units': [{'text': '大家好啊', 'begin_s': 0.0, 'end_s': 10.0}]}
    proc, result = run_check(tmp_path, comp, units=units, timeline=TIMELINE)
    assert proc.returncode == 0
    assert ('s1', 'caption_mismatch') in checks_of(result)


# --- CLI seam ---------------------------------------------------------------------


def test_usage_error_exits_2():
    proc = run_cli('--bogus-flag')
    assert proc.returncode == 2
    result = json.loads(proc.stdout)
    assert result['success'] is False


def test_invalid_argument_value_exits_2(tmp_path: Path):
    comp = write_composition(tmp_path, [scene('s1', 0.0, 10.0, CLEAN_SCENE)])
    proc = run_cli(
        str(comp),
        '--layout', str(PRESENTER_LAYOUT),
        '--min-font-size', '22',
        '--viewport', 'not-a-viewport',
    )
    assert proc.returncode == 2
    result = json.loads(proc.stdout)
    assert result['success'] is False


def test_missing_composition_exits_1(tmp_path: Path):
    proc = run_cli(
        str(tmp_path / 'nope'),
        '--layout', str(PRESENTER_LAYOUT),
        '--min-font-size', '22',
    )
    assert proc.returncode == 1
    result = json.loads(proc.stdout)
    assert result['success'] is False


def test_scenes_fall_back_to_dom_roots_without_timeline(tmp_path: Path):
    comp = write_composition(
        tmp_path,
        [
            scene('s1', 0.0, 10.0, CLEAN_SCENE + CAPTION_BAR),
            scene('s2', 10.0, 20.0, CLEAN_SCENE + CAPTION_BAR),
        ],
    )
    proc, result = run_check(tmp_path, comp, units=SUBTITLE_UNITS)
    assert proc.returncode == 0
    assert result['verdict'] == 'pass'
    checked = {s['scene_id'] for s in result['scenes_checked']}
    assert checked == {'s1', 's2'}


def test_design_doc_supplies_min_font_size(tmp_path: Path):
    comp = write_composition(
        tmp_path,
        [scene('s1', 0.0, 10.0, CLEAN_SCENE + CAPTION_BAR)],
    )
    design_doc = tmp_path / 'theme.md'
    design_doc.write_text('# theme\n\n**字号下限**：阅读文字不小于 26px。\n', encoding='utf-8')
    units_path = tmp_path / 'subtitle-units.json'
    write_json(units_path, SUBTITLE_UNITS)
    proc = run_cli(
        str(comp),
        '--layout', str(PRESENTER_LAYOUT),
        '--design-doc', str(design_doc),
        '--subtitle-units', str(units_path),
    )
    assert proc.returncode == 0
    result = json.loads(proc.stdout)
    assert result['min_font_size'] == 26
    # Without a 界面小字 label the UI-text minimum falls back to the reading one.
    assert result['min_ui_font_size'] == 26
    # panel text is 30px, above the parsed 26px floor
    assert result['verdict'] == 'pass'


UI_TEXT_SCENE = """
  <div class="panel" style="position:absolute; left:96px; top:196px; width:800px; height:400px;
       font-size:30px; line-height:1.4;">
    <div class="title-bar" data-text-role="ui" style="font-size:23px;">面板标题</div>
    <div class="body-small" style="font-size:23px;">正文小字</div>
  </div>
"""


def test_ui_text_role_uses_the_ui_minimum(tmp_path: Path):
    comp = write_composition(tmp_path, [scene('s1', 0.0, 10.0, UI_TEXT_SCENE + CAPTION_BAR)])
    design_doc = tmp_path / 'theme.md'
    design_doc.write_text(
        '# theme\n\n**字号下限**：阅读文字不小于 26px，界面小字不小于 22px，字幕 36px。\n',
        encoding='utf-8',
    )
    units_path = tmp_path / 'subtitle-units.json'
    write_json(units_path, SUBTITLE_UNITS)
    proc = run_cli(
        str(comp),
        '--layout', str(PRESENTER_LAYOUT),
        '--design-doc', str(design_doc),
        '--subtitle-units', str(units_path),
    )
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert (result['min_font_size'], result['min_ui_font_size']) == (26, 22)
    small = [f['detail'] for f in result['findings'] if f['check'] == 'font_size_below_min']
    # 23px body text fails the 26px reading minimum; the 23px UI title bar passes.
    assert len(small) == 1
    assert 'body-small' in small[0] and 'reading-text minimum 26px' in small[0]
