"""Integration tests for scripts/check-composition.py.

The test seam is the script's command line (repo convention: stdout = one
JSON, exit 0 = run completed with verdict pass/fail, 1 = runtime error,
2 = usage). Fixture compositions are tiny static HTML files built in tmp
dirs and measured through system Chrome + Playwright (required dependencies:
without them these tests fail via the require_chrome fixture, never skip).
"""
from __future__ import annotations

import json
import struct
import subprocess
import sys
import zlib
from pathlib import Path

import pytest

from cli_helpers import parse_stdout, write_silent_mp3

pytestmark = pytest.mark.usefixtures('require_chrome')

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / 'scripts' / 'check-composition.py'
PRESENTER_LAYOUT = REPO_ROOT / 'modules' / 'layouts' / 'landscape-presenter.json'

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

# Static fixtures expose the project-generic seek entry: the snapshot script
# drives window.__layoutQA.seek(videoSeconds) before measuring DOM, and also
# dispatches a check-time event (see scripts/check-composition.py), so each
# scene's check times only see that scene's elements.
SCENE_TOGGLE_JS = """
  const applyCheckTime = (time) => {
    document.querySelectorAll('[data-scene-id]').forEach((el) => {
      const start = parseFloat(el.getAttribute('data-scene-start') || '0');
      const end = parseFloat(el.getAttribute('data-scene-end') || '1e9');
      el.style.visibility = (time >= start && time <= end) ? 'visible' : 'hidden';
    });
  };
  document.addEventListener('check-time', (event) => applyCheckTime(event.detail.time));
  window.__layoutQA = { seek: async (time) => applyCheckTime(time) };
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

PRESENTER = """
  <div id="presenter" style="position:absolute; left:1294px; top:642px; width:420px; height:420px;
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


def run_check(
    tmp_path: Path,
    comp: Path,
    *,
    units=None,
    timeline=None,
    layout: Path = PRESENTER_LAYOUT,
    extra_args: tuple[str, ...] = (),
) -> tuple:
    args = [
        str(comp),
        '--layout', str(layout),
        '--min-font-size', '22',
        *extra_args,
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
    result = parse_stdout(proc)
    return proc, result


def checks_of(result: dict) -> set[tuple[str, str]]:
    return {(finding['scene_id'], finding['check']) for finding in result['findings']}


# --- fixture with deliberately broken elements -----------------------------------


def test_dirty_fixture_reports_each_check_and_attributes_scenes(tmp_path: Path):
    comp = write_composition(
        tmp_path,
        [
            scene('s1', 0.0, 10.0, DIRTY_SCENE + CAPTION_BAR),
            scene('s2', 10.0, 20.0, CLEAN_SCENE + CAPTION_BAR),
            scene(
                's3',
                20.0,
                30.0,
                '<div class="stray" style="position:absolute; left:1750px; top:400px; '
                'width:400px; height:100px; font-size:30px; background:#eeeeee;">越界</div>'
                + CAPTION_BAR,
            ),
        ],
    )
    timeline = {
        'version': 1,
        'total_s': 30.0,
        'scenes': [
            *TIMELINE['scenes'],
            {'scene_id': 's3', 'begin_s': 20.0, 'end_s': 30.0},
        ],
    }
    units = {
        'units': [
            {'text': '大家好', 'begin_s': 0.0, 'end_s': 20.0},
            {'text': '大家好啊', 'begin_s': 20.0, 'end_s': 30.0},
        ]
    }
    proc, result = run_check(tmp_path, comp, units=units, timeline=timeline)
    assert proc.returncode == 0
    assert result['success'] is True
    assert result['verdict'] == 'fail'
    checks = checks_of(result)
    assert {
        ('s1', 'outside_content_regions'),
        ('s1', 'reserved_region_intrusion'),
        ('s1', 'text_overflow'),
        ('s1', 'media_load_failure'),
        ('s1', 'font_size_below_min'),
        ('s3', 'outside_content_regions'),
        ('s3', 'caption_mismatch'),
    } <= checks
    # s2 is clean: findings are attributed strictly to the offending scenes
    assert {finding['scene_id'] for finding in result['findings']} == {'s1', 's3'}


# --- clean fixture ----------------------------------------------------------------


def test_clean_fixture_passes_and_dumps_snapshots(tmp_path: Path):
    comp = write_composition(
        tmp_path,
        [
            scene('s1', 0.0, 10.0, CLEAN_SCENE + CAPTION_BAR + PRESENTER),
            scene('s2', 10.0, 20.0, CLEAN_SCENE + CAPTION_BAR + PRESENTER),
        ],
    )
    dump_path = tmp_path / 'recorded' / 'snapshots.json'
    proc, result = run_check(
        tmp_path,
        comp,
        units=SUBTITLE_UNITS,
        timeline=TIMELINE,
        extra_args=('--dump-snapshots', str(dump_path)),
    )
    assert proc.returncode == 0, proc.stderr
    assert result['success'] is True
    assert result['verdict'] == 'pass'
    assert result['findings'] == []
    snapshots = json.loads(dump_path.read_text(encoding='utf-8'))
    assert isinstance(snapshots, list) and len(snapshots) == 6
    assert {snapshot['scene_id'] for snapshot in snapshots} == {'s1', 's2'}
    assert all(isinstance(snapshot['time'], (int, float)) for snapshot in snapshots)
    assert all(isinstance(snapshot['elements'], list) for snapshot in snapshots)


# --- CLI seam ---------------------------------------------------------------------


def test_invalid_argument_value_exits_2(tmp_path: Path):
    comp = write_composition(tmp_path, [scene('s1', 0.0, 10.0, CLEAN_SCENE)])
    proc = run_cli(
        str(comp),
        '--layout', str(PRESENTER_LAYOUT),
        '--min-font-size', '22',
        '--viewport', 'not-a-viewport',
    )
    assert proc.returncode == 2
    assert parse_stdout(proc)['success'] is False


def test_missing_composition_exits_1(tmp_path: Path):
    proc = run_cli(
        str(tmp_path / 'nope'),
        '--layout', str(PRESENTER_LAYOUT),
        '--min-font-size', '22',
    )
    assert proc.returncode == 1
    assert parse_stdout(proc)['success'] is False


def test_invalid_timeline_scene_is_skipped_with_warning(tmp_path: Path):
    comp = write_composition(
        tmp_path,
        [scene('s1', 0.0, 10.0, CLEAN_SCENE)],
    )
    timeline = {
        'scenes': [
            {'scene_id': 'broken', 'end_s': 5.0},
            {'scene_id': 's1', 'begin_s': 0.0, 'end_s': 10.0},
        ]
    }

    proc, result = run_check(tmp_path, comp, timeline=timeline)

    assert proc.returncode == 0, proc.stderr
    assert result['success'] is True
    assert 'Traceback' not in proc.stderr
    assert any('broken' in warning and 'skipped' in warning for warning in result['warnings'])
    assert [scene['scene_id'] for scene in result['scenes_checked']] == ['s1']


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


UI_TEXT_SCENE = """
  <div class="panel" style="position:absolute; left:96px; top:196px; width:800px; height:400px;
       font-size:32px; line-height:1.4;">
    <div class="body-ok" style="font-size:32px;">正文正常字号</div>
    <div class="title-bar" data-text-role="ui" style="font-size:24px;">面板标题</div>
    <div class="body-small" style="font-size:24px;">正文小字</div>
  </div>
"""


def test_design_json_supplies_reading_and_ui_font_minimums(tmp_path: Path):
    import video_contract

    comp = write_composition(tmp_path, [scene('s1', 0.0, 10.0, UI_TEXT_SCENE + CAPTION_BAR)])
    preset = video_contract.load_design_preset(REPO_ROOT, 'github')
    design = tmp_path / 'design.json'
    write_json(design, {
        'version': 1,
        'source': 'custom',
        'preset': None,
        'tokens': dict(preset['tokens']),
        'min_font_px': {'reading': 31, 'ui': 23},
    })
    units_path = tmp_path / 'subtitle-units.json'
    write_json(units_path, SUBTITLE_UNITS)
    proc = run_cli(
        str(comp),
        '--layout', str(PRESENTER_LAYOUT),
        '--design', str(design),
        '--subtitle-units', str(units_path),
    )
    assert proc.returncode == 0, proc.stderr
    result = parse_stdout(proc)
    assert (result['min_font_size'], result['min_ui_font_size']) == (31, 23)
    small = [f['issue'] for f in result['findings'] if f['check'] == 'font_size_below_min']
    # 32px reading text and 24px UI title bar pass; 24px body-small fails the 31px reading floor.
    assert len(small) == 1
    assert 'body-small' in small[0] and 'reading-text minimum 31px' in small[0]


def test_viewport_defaults_to_layout_canvas(tmp_path: Path):
    comp = write_composition(tmp_path, [scene('s1', 0.0, 10.0, CLEAN_SCENE)])
    portrait_layout = REPO_ROOT / 'modules' / 'layouts' / 'portrait.json'

    proc, result = run_check(tmp_path, comp, layout=portrait_layout)

    assert proc.returncode == 0, proc.stderr
    assert result['viewport'] == {'width': 1080, 'height': 1920}
    assert result['viewport_mismatch'] is False


def test_explicit_viewport_mismatch_is_used_and_reported(tmp_path: Path):
    comp = write_composition(tmp_path, [scene('s1', 0.0, 10.0, CLEAN_SCENE)])

    proc, result = run_check(tmp_path, comp, extra_args=('--viewport', '1280x720'))

    assert proc.returncode == 0, proc.stderr
    assert result['viewport'] == {'width': 1280, 'height': 720}
    assert result['viewport_mismatch'] is True
    assert 'warning' in proc.stderr.lower()
    assert 'viewport' in proc.stderr.lower()
    assert any('viewport' in warning for warning in result['warnings'])


def write_png(path: Path, width: int, height: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    chunk = lambda t, b: struct.pack('>I', len(b)) + t + b + struct.pack('>I', zlib.crc32(t + b) & 0xFFFFFFFF)  # noqa: E731
    ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
    idat = chunk(b'IDAT', zlib.compress((b'\x00' + b'\x30\x60\x90' * width) * height, level=1))
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + ihdr + idat + chunk(b'IEND', b''))


@pytest.mark.usefixtures('require_ffmpeg')
def test_dump_snapshots_roundtrip_and_chrome_warning_telemetry(tmp_path: Path):
    ws = tmp_path / 'ws'
    comp = ws / 'composition'
    write_png(ws / 'materials/pan.png', 1600, 1000)
    write_png(ws / 'materials/cover.png', 800, 1000)
    write_png(ws / 'materials/stamp.png', 800, 500)
    write_json(ws / 'inputs.json', {'orientation': 'landscape'})
    write_silent_mp3(ws / 'voice_clone/narration.mp3', 20.0)

    presenter_data = json.loads(PRESENTER_LAYOUT.read_text(encoding='utf-8'))
    stage_data = json.loads((REPO_ROOT / 'modules/layouts/landscape.json').read_text(encoding='utf-8'))
    borrow = lambda name, data: {'preset': name, 'regions': data['regions'], 'caption': data['caption']}  # noqa: E731
    scene_cfg = comp / 'scene-config.json'
    write_json(scene_cfg, {
        'version': 1, 'canvas': {'width': 1920, 'height': 1080}, 'total_s': 20.0,
        'scenes': [
            {'scene_id': 's1', 'source_scene_ids': ['n1'], 'begin_s': 0.0, 'end_s': 5.0, 'template': None, 'layout': borrow('landscape-presenter', presenter_data)},
            {'scene_id': 's2', 'source_scene_ids': ['n2'], 'begin_s': 5.0, 'end_s': 10.0, 'template': None, 'layout': borrow('landscape', stage_data)},
            {'scene_id': 's3', 'source_scene_ids': ['n3'], 'begin_s': 10.0, 'end_s': 15.0, 'template': None, 'layout': borrow('landscape', stage_data)},
            {'scene_id': 's4', 'source_scene_ids': ['n4'], 'begin_s': 15.0, 'end_s': 20.0, 'template': None, 'layout': borrow('landscape', stage_data)},
        ],
    })

    scenes_html = [
        scene('s1', 0.0, 5.0, """
          <div id="s1-main-copy" style="position:absolute; left:96px; top:200px; width:960px; height:80px; font-size:32px;">
            新一代推理引擎支持零拷贝显存池架构，单机吞吐量提升三倍以上
          </div>
          <svg id="s1-svg" width="560" height="220" viewBox="0 0 560 220" style="position:absolute; left:96px; top:290px; width:560px; height:220px;">
            <g id="narrow-node">
              <rect x="80" y="20" width="220" height="80" fill="#eef4ff" stroke="#3366cc" />
              <text id="overflow-label" x="190" y="68" text-anchor="middle" font-size="28">超长节点标题明显溢出承载框</text>
            </g>
            <g id="bar-item">
              <rect x="420" y="150" width="44" height="28" fill="#66aa88" />
              <text id="bar-label" x="442" y="136" text-anchor="middle" font-size="24">128 GB/s</text>
            </g>
          </svg>
          <img id="s1-cover" src="../materials/cover.png"
               style="position:absolute; left:120px; top:540px; width:640px; height:400px; object-fit:cover; object-position:50% 0%;" />
          <img id="s1-pan" src="../materials/pan.png"
               style="position:absolute; left:1184px; top:100px; width:640px; height:400px; object-fit:fill;" />
          <div id="s1-side-dup" style="position:absolute; left:1184px; top:510px; width:620px; height:108px; font-size:28px;">
            支持零拷贝显存池架构，单机吞吐量提升三倍以上
          </div>
        """ + PRESENTER),
        scene('s2', 5.0, 10.0, """
          <img id="s2-cover" src="../materials/cover.png"
               style="position:absolute; left:120px; top:220px; width:640px; height:400px; object-fit:cover; object-position:50% 100%;" />
          <div id="s2-edge-leader" style="position:absolute; left:756px; top:280px; width:44px; height:2px; border-top:2px solid #2266dd;"></div>
          <div id="s2-occluder" style="position:absolute; left:180px; top:260px; width:240px; height:70px; background:#ffffff; font-size:28px;">遮挡图片浮层</div>
          <div id="s2-wrap" style="position:absolute; left:940px; top:220px; width:800px; height:500px; overflow:hidden;">
            <img id="s2-pan" src="../materials/pan.png" style="width:800px; height:500px; object-fit:none; object-position:-400px -200px;" />
          </div>
          <div id="s2-card-a" style="position:absolute; left:120px; top:700px; width:360px; height:140px; background:#f5f7fa; border:2px solid #8899aa;">
            <div id="s2-card-a-child" style="font-size:28px;">父子文本不误判重叠</div>
          </div>
          <div id="s2-card-b" style="position:absolute; left:340px; top:730px; width:360px; height:140px; background:#fff4ee; border:2px solid #cc8866; font-size:28px;">与左侧卡片同层重叠</div>
        """),
        scene('s3', 10.0, 15.0, """
          <img id="s3-cover-static" src="../materials/cover.png"
               style="position:absolute; left:120px; top:220px; width:640px; height:400px; object-fit:cover; object-position:50% 96%;" />
          <img id="s3-stamp" src="../materials/stamp.png"
               style="position:absolute; left:900px; top:220px; width:200px; height:125px;" />
        """),
        scene('s4', 15.0, 20.0, """
          <img id="s4-pan-again" src="../materials/pan.png?cache=2"
               style="position:absolute; left:120px; top:210px; width:1120px; height:700px; object-fit:contain;" />
        """),
    ]
    comp.mkdir(parents=True, exist_ok=True)
    (comp / 'index.html').write_text(
        f'<!doctype html><html><head><meta charset="utf-8"><style>{BASE_CSS}</style></head><body>'
        + ''.join(scenes_html)
        + """<script>
          const applyCheckTime = (time) => {
            document.querySelectorAll('[data-scene-id]').forEach((el) => {
              const s = parseFloat(el.getAttribute('data-scene-start') || '0');
              const e = parseFloat(el.getAttribute('data-scene-end') || '1e9');
              el.style.display = (time >= s && time < e) ? 'block' : 'none';
            });
          };
          document.addEventListener('check-time', (ev) => applyCheckTime(ev.detail.time));
          window.__layoutQA = { seek: async (time) => applyCheckTime(time) };
        </script></body></html>""",
        encoding='utf-8',
    )

    dump_path = tmp_path / 'dumped-snapshots.json'
    live_proc = run_cli(str(ws), '--scene-config', str(scene_cfg), '--min-font-size', '22', '--dump-snapshots', str(dump_path))
    assert live_proc.returncode == 0, live_proc.stdout + live_proc.stderr
    live_report = parse_stdout(live_proc)

    replay_proc = run_cli(
        str(ws), '--scene-config', str(scene_cfg), '--min-font-size', '22',
        '--snapshots-from', str(dump_path), '--chrome-path', '/definitely/no-chrome',
    )
    assert replay_proc.returncode == 0, replay_proc.stdout + replay_proc.stderr
    assert live_report == parse_stdout(replay_proc)
    assert live_report['verdict'] == 'pass', live_report['findings']
    assert live_report['findings'] == []

    snapshots = json.loads(dump_path.read_text(encoding='utf-8'))
    by_id = {el['id']: el['media'] for snap in snapshots for el in snap['elements'] if el.get('id') in {'s1-cover', 's2-cover', 's1-pan', 's2-pan'}}
    assert by_id['s1-cover']['paintedRect'] == pytest.approx({'x': 120, 'y': 540, 'width': 640, 'height': 800})
    assert by_id['s1-cover']['cropBox'] == pytest.approx({'x': 0.0, 'y': 0.0, 'w': 1.0, 'h': 0.5})
    assert by_id['s2-cover']['paintedRect'] == pytest.approx({'x': 120, 'y': -180, 'width': 640, 'height': 800})
    assert by_id['s2-cover']['cropBox'] == pytest.approx({'x': 0.0, 'y': 0.5, 'w': 1.0, 'h': 0.5})
    assert by_id['s1-pan']['cropBox'] == pytest.approx({'x': 0.0, 'y': 0.0, 'w': 1.0, 'h': 1.0})
    assert by_id['s2-pan']['paintedRect'] == pytest.approx({'x': 540, 'y': 20, 'width': 1600, 'height': 1000})
    assert by_id['s2-pan']['visibleRect'] == pytest.approx({'x': 940, 'y': 220, 'width': 800, 'height': 500})
    assert by_id['s2-pan']['cropBox'] == pytest.approx({'x': 0.25, 'y': 0.20, 'w': 0.50, 'h': 0.50})

    warnings = live_report['warnings']
    assert len(warnings) == len(set(warnings)), warnings
    assert any(w.startswith('[s1] svg_text_overflow:') and '#overflow-label' in w for w in warnings)
    assert not any('#bar-label' in w for w in warnings)
    assert any(w.startswith('[s1] media_blurry_scale:') and '#s1-pan' in w for w in warnings)
    assert any(w.startswith('[s1] region_text_duplication:') for w in warnings)
    assert any(w.startswith('[s2] material_occlusion:') and '#s2-occluder' in w for w in warnings)
    assert not any('#s2-edge-leader' in w or '#s2-card-a-child' in w for w in warnings)
    assert any(w.startswith('[s2] element_overlap:') and '#s2-card-a' in w and '#s2-card-b' in w for w in warnings)
    assert not any(w.startswith('[s2] media_reuse:') for w in warnings)
    assert any(w.startswith('[s3] media_too_small:') and '#s3-stamp' in w for w in warnings)
    assert any(w.startswith('[s3] media_reuse: adjacent reuse of image materials/cover.png') for w in warnings)
    assert any(w.startswith('[s4] media_reuse: non-adjacent reuse of materials/pan.png') and 's2' in w for w in warnings)


@pytest.mark.usefixtures('require_ffmpeg')
def test_project_cover_template_logo_and_subtree_exemption_in_chrome(tmp_path: Path):
    ws = tmp_path / 'ws'
    comp = ws / 'composition'
    write_png(comp / 'assets/logo.png', 600, 600)
    write_png(comp / 'assets/screenshot.png', 1280, 720)
    write_json(ws / 'inputs.json', {'orientation': 'landscape'})
    write_silent_mp3(ws / 'voice_clone/narration.mp3', 5.0)

    presenter_data = json.loads(PRESENTER_LAYOUT.read_text(encoding='utf-8'))
    scene_cfg = comp / 'scene-config.json'
    write_json(scene_cfg, {
        'version': 1, 'canvas': {'width': 1920, 'height': 1080}, 'total_s': 5.0,
        'scenes': [{
            'scene_id': 'cover', 'source_scene_ids': ['n1'], 'begin_s': 0.0, 'end_s': 5.0,
            'template': {'name': 'github-trending', 'scene': 'project-cover'},
            'layout': {'preset': 'landscape-presenter', 'regions': presenter_data['regions'], 'caption': presenter_data['caption']},
        }],
    })

    cover_html = (REPO_ROOT / 'modules/templates/github-trending/project-cover.html').read_text(encoding='utf-8')
    inline_mjs = (REPO_ROOT / 'modules/templates/github-trending/project-cover.mjs').read_text(encoding='utf-8').replace('export function init', 'function initProjectCover')

    def build_index(extra_free_html: str) -> str:
        return f"""<!doctype html><html><head><meta charset="utf-8">
        <style>{BASE_CSS} :root {{ --font-sans: Arial, sans-serif; --font-mono: monospace; --c-ink: #222; --c-ink2: #666; --c-card: #fff; --c-border: #888; --c-focus: #06f; --c-highlight: #fc0; --c-muted: #aaa; --c-surface: #eee; --c-focus-tint: #def; --c-positive: #2a4; --c-positive-tint: #dfd; --c-positive-solid: #2a4; --c-positive-text: #142; }}</style></head><body>
        {cover_html}
        <div data-scene-id="cover" data-scene-start="0" data-scene-end="5" style="position:absolute; inset:0;">
          <div id="project-cover" data-composition-id="project-cover" style="position:absolute; inset:0;"></div>
          {extra_free_html}
        </div>
        {PRESENTER}
        <script>
          const noopTl = new Proxy({{}}, {{ get: () => () => noopTl }});
          {inline_mjs}
          const host = document.getElementById('project-cover');
          host.appendChild(document.querySelector('template').content.cloneNode(true));
          initProjectCover(host.querySelector('#root'), {{
            params: {{ rank: 1, owner: 'demo', repo: 'engine', tagline: '高性能本地推理框架', topics: 'rust,llm', stars: 4200, lang: 'Rust', logo: 'assets/logo.png', nameAt: 0.1, taglineAt: 0.3, starsAt: 0.6 }},
            duration: 5, gsap: {{ timeline: () => noopTl }},
          }});
          window.__layoutQA = {{ seek: async () => {{}} }};
        </script></body></html>"""

    (comp / 'index.html').write_text(build_index(''), encoding='utf-8')
    dump_clean = tmp_path / 'cover-clean.json'
    proc_clean = run_cli(str(comp), '--scene-config', str(scene_cfg), '--min-font-size', '22', '--dump-snapshots', str(dump_clean))
    assert proc_clean.returncode == 0, proc_clean.stdout + proc_clean.stderr
    report_clean = parse_stdout(proc_clean)
    assert report_clean['verdict'] == 'pass', report_clean['findings']
    assert report_clean['warnings'] == []
    logo_els = [el for el in json.loads(dump_clean.read_text(encoding='utf-8'))[0]['elements'] if el.get('media') and 'logo.png' in el['media'].get('src', '')]
    assert len(logo_els) == 1 and logo_els[0]['media']['mediaRole'] == 'logo'

    (comp / 'index.html').write_text(
        build_index('<img id="free-postage-stamp" src="assets/screenshot.png" style="position:absolute; left:110px; top:860px; width:160px; height:90px;" />'),
        encoding='utf-8',
    )
    proc_extra = run_cli(str(comp), '--scene-config', str(scene_cfg), '--min-font-size', '22')
    assert proc_extra.returncode == 0, proc_extra.stdout + proc_extra.stderr
    report_extra = parse_stdout(proc_extra)
    assert report_extra['verdict'] == 'pass', report_extra['findings']
    assert any(w.startswith('[cover] media_too_small:') and '#free-postage-stamp' in w for w in report_extra['warnings'])
    assert not any('logo.png' in w or '#pc-side' in w for w in report_extra['warnings'])
