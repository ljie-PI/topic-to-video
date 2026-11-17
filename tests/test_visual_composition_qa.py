"""Scene-level composition QA through the recorded-snapshot CLI seam."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import composition_warnings
from cli_helpers import load_script_module, parse_stdout, write_silent_mp3

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / 'scripts/check-composition.py'


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')


def element(scene_id: str, *, caption: bool = False, font_size: int = 30) -> dict:
    return {
        'selector': 'span.caption-text' if caption else 'div.shared',
        'id': 'caption-text' if caption else 'shared',
        'tag': 'span' if caption else 'div',
        'label': 'caption text' if caption else 'div shared',
        'rect': {'x': 96, 'y': 1008, 'width': 200, 'height': 40} if caption else
                {'x': 1200, 'y': 700, 'width': 400, 'height': 100},
        'ownText': True,
        'text': '字幕' if caption else 'shared element',
        'fontSize': font_size,
        'isCaption': caption,
        'isUiText': False,
        'isSceneRoot': False,
        'sceneId': None if caption else scene_id,
        'lineCount': 1,
        'layoutIgnore': False,
        'surface': False,
        'media': None,
        'ancestors': ['caption-bar'] if caption else [],
        'overflowStyle': 'visible visible',
        'clientWidth': 200 if caption else 400,
        'clientHeight': 40 if caption else 100,
        'scrollWidth': 200 if caption else 400,
        'scrollHeight': 40 if caption else 100,
    }


def snapshot(scene_id: str, time: float, *, caption_font: int | None = None) -> dict:
    captions = caption_font is not None
    return {
        'scene_id': scene_id, 'time': time, 'fontsStatus': 'loaded', 'presenterVisible': scene_id == 'b',
        'elements': [element(scene_id), *([element(scene_id, caption=True, font_size=caption_font)] if captions else [])],
        'captionTexts': ['字幕'] if captions else [],
        'captionDetails': [{
            'text': '字幕', 'fontSize': caption_font, 'lineCount': 1,
            'rect': {'x': 96, 'y': 1008, 'width': 200, 'height': 40},
        }] if captions else [],
    }


def borrowed_layout(name: str) -> dict:
    data = json.loads((ROOT / 'modules' / 'layouts' / f'{name}.json').read_text(encoding='utf-8'))
    return {'preset': name, 'regions': data['regions'], 'caption': data['caption']}


def visual_scene(scene_id: str, begin: float, end: float, layout: dict) -> dict:
    return {
        'scene_id': scene_id,
        'source_scene_ids': ['scene_1'],
        'begin_s': begin,
        'end_s': end,
        'template': None,
        'layout': layout,
    }


def workspace(tmp_path: Path, snapshots: list[dict]) -> tuple[Path, Path]:
    ws = tmp_path / 'ws'
    write_json(ws / 'inputs.json', {'orientation': 'landscape'})
    write_json(ws / 'composition/scene-config.json', {
        'version': 1,
        'canvas': {'width': 1920, 'height': 1080},
        'total_s': 10,
        'scenes': [
            visual_scene('a', 0, 5, borrowed_layout('landscape')),
            visual_scene('b', 5, 10, borrowed_layout('landscape-presenter')),
        ],
    })
    write_silent_mp3(ws / 'voice_clone/narration.mp3', 10.0)
    path = tmp_path / 'snapshots.json'
    write_json(path, snapshots)
    return ws, path


def run(ws: Path, snapshots: Path, *extra: str) -> tuple[subprocess.CompletedProcess, dict]:
    proc = subprocess.run([
        sys.executable, str(SCRIPT), str(ws / 'composition'),
        '--scene-config', str(ws / 'composition/scene-config.json'),
        '--min-font-size', '22', '--snapshots-from', str(snapshots), *extra,
    ], capture_output=True, text=True)
    return proc, parse_stdout(proc)


@pytest.mark.usefixtures('require_ffmpeg')
def test_scene_layouts_and_active_caption_specs_are_checked_per_scene(tmp_path: Path):
    ws, snapshots = workspace(tmp_path, [snapshot('a', 2, caption_font=36), snapshot('b', 7, caption_font=30)])
    units = tmp_path / 'units.json'
    write_json(units, {'units': [{'text': '字幕', 'begin_s': 0, 'end_s': 10}]})

    proc, result = run(ws, snapshots, '--subtitle-units', str(units))

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert result['verdict'] == 'fail'
    assert {(f['scene_id'], f['check']) for f in result['findings']} == {
        ('b', 'outside_content_regions'),
        ('b', 'reserved_region_intrusion'),
        ('b', 'caption_mismatch'),
    }
    assert [s['layout'] for s in result['scenes_checked']] == ['landscape', 'landscape-presenter']
    mismatch = [f for f in result['findings'] if f['check'] == 'caption_mismatch']
    assert len(mismatch) == 1
    assert mismatch[0]['scene_id'] == 'b'
    assert '30px' in mismatch[0]['issue'] and '36px' in mismatch[0]['issue']


@pytest.mark.usefixtures('require_ffmpeg')
def test_missing_visual_scene_snapshot_cannot_pass(tmp_path: Path):
    ws, snapshots = workspace(tmp_path, [snapshot('a', 2)])
    proc, result = run(ws, snapshots)
    assert proc.returncode == 0
    assert result['verdict'] == 'fail'
    assert any(f['check'] == 'scene_coverage' and f['scene_id'] == 'b' for f in result['findings'])


@pytest.mark.usefixtures('require_ffmpeg')
def test_scene_mount_must_exist_at_each_start_middle_and_end_snapshot(tmp_path: Path):
    start = snapshot('a', 0.2)
    middle = snapshot('a', 2.5)
    end = snapshot('a', 4.8)
    for boundary in (start, end):
        boundary['elements'][0]['sceneId'] = None
    ws, snapshots = workspace(tmp_path, [start, middle, end, snapshot('b', 7)])

    proc, result = run(ws, snapshots)

    assert proc.returncode == 0
    missing = [f for f in result['findings'] if f['check'] == 'scene_mount_missing']
    assert [f['time_s'] for f in missing] == [0.2, 4.8]


@pytest.mark.usefixtures('require_ffmpeg')
def test_adjacent_subtitle_units_and_scene_mode_exact_bounds_do_not_false_positive(tmp_path: Path):
    before_switch = snapshot('a', 4.98, caption_font=36)
    after_unit_end = snapshot('b', 5.1)
    ws, snapshots = workspace(tmp_path, [before_switch, after_unit_end])
    units = tmp_path / 'units.json'
    write_json(units, {'units': [
        {'text': '字幕', 'begin_s': 0.0, 'end_s': 5.0},
        {'text': '下一句', 'begin_s': 5.0, 'end_s': 5.06},
    ]})

    proc, result = run(ws, snapshots, '--subtitle-units', str(units))

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert [f for f in result['findings'] if f['check'] == 'caption_mismatch'] == []


def test_short_scene_sampling_stays_inside_its_range():
    module = load_script_module('check-composition.py', 'check_composition')
    times = module.scene_check_times({'begin_s': 2.0, 'end_s': 2.1})
    assert len(times) == 3
    assert all(2.0 < time < 2.1 for time in times)


def free_layout() -> dict:
    return {
        'preset': None,
        'regions': [
            {'id': 'main', 'kind': 'content', 'rect': {'x': 96, 'y': 80, 'width': 1728, 'height': 820}},
            {'id': 'caption', 'kind': 'reserved', 'component': 'caption-bar',
             'rect': {'x': 96, 'y': 930, 'width': 1728, 'height': 120}},
        ],
        'caption': {'width_px': 1728, 'font_size_px': 36, 'max_lines': 2},
    }


def mixed_workspace(tmp_path: Path, snapshots: list[dict]) -> tuple[Path, Path]:
    """模板场景 + 自由回退场景同片共存的工作区（验收要求的两种正常路径）。"""
    ws = tmp_path / 'ws'
    write_json(ws / 'inputs.json', {'orientation': 'landscape'})
    write_json(ws / 'composition/scene-config.json', {
        'version': 1,
        'canvas': {'width': 1920, 'height': 1080},
        'total_s': 10,
        'scenes': [
            {**visual_scene('tpl', 0, 5, borrowed_layout('landscape-presenter')),
             'template': {'name': 'github-trending', 'scene': 'project-cover'}},
            visual_scene('free', 5, 10, free_layout()),
        ],
    })
    write_silent_mp3(ws / 'voice_clone/narration.mp3', 10.0)
    path = tmp_path / 'snapshots.json'
    write_json(path, snapshots)
    return ws, path


def mixed_snapshot(scene_id: str, time: float, *, presenter: bool) -> dict:
    item = snapshot(scene_id, time, caption_font=36)
    if scene_id == 'tpl':
        # presenter 的 content 区：side (1184,100,640x522)
        item['elements'][0]['rect'] = {'x': 1200, 'y': 120, 'width': 400, 'height': 100}
    else:
        # 自由布局的 main content 区 (96,80,1728x820)，caption 在 reserved caption-bar 区
        item['elements'][0]['rect'] = {'x': 200, 'y': 120, 'width': 400, 'height': 100}
        item['elements'][1]['rect'] = {'x': 96, 'y': 930, 'width': 200, 'height': 40}
        item['captionDetails'][0]['rect'] = {'x': 96, 'y': 930, 'width': 200, 'height': 40}
    item['presenterVisible'] = presenter
    return item


@pytest.mark.usefixtures('require_ffmpeg')
def test_template_and_free_scenes_pass_and_check_current_subtitle_units(tmp_path: Path):
    """模板场景与自由回退场景同片通过区域检查，且以当前（含手改）字幕文件为准。"""
    ws, snapshots_path = mixed_workspace(tmp_path, [
        mixed_snapshot('tpl', 2, presenter=True),
        mixed_snapshot('free', 7, presenter=False),
    ])
    snapshots = json.loads(snapshots_path.read_text(encoding='utf-8'))
    for snap in snapshots:
        snap['captionTexts'] = ['改过的字幕']
        snap['captionDetails'][0]['text'] = '改过的字幕'
    units = tmp_path / 'units.json'
    write_json(units, {'units': [{'text': '改过的字幕', 'begin_s': 0, 'end_s': 10}]})
    edited_path = tmp_path / 'edited-snapshots.json'
    write_json(edited_path, snapshots)

    proc, result = run(ws, edited_path, '--subtitle-units', str(units))

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert result['verdict'] == 'pass', result['findings']
    assert [(s['scene_id'], s['layout']) for s in result['scenes_checked']] == [
        ('tpl', 'landscape-presenter'), ('free', None),
    ]

    # 反向对照：屏幕若仍是初稿文本，与当前（已编辑）单元不符，必须报 mismatch
    proc, result = run(ws, snapshots_path, '--subtitle-units', str(units))

    assert proc.returncode == 0
    mismatch = [f for f in result['findings'] if f['check'] == 'caption_mismatch']
    assert len(mismatch) == 2
    assert all('改过的字幕' in f['issue'] for f in mismatch)


@pytest.mark.usefixtures('require_ffmpeg')
def test_presenter_visibility_mismatch_against_person_region_is_reported(tmp_path: Path):
    ws, snapshots = mixed_workspace(tmp_path, [
        mixed_snapshot('tpl', 2, presenter=False),
        mixed_snapshot('free', 7, presenter=True),
    ])
    units = tmp_path / 'units.json'
    write_json(units, {'units': [{'text': '字幕', 'begin_s': 0, 'end_s': 10}]})

    proc, result = run(ws, snapshots, '--subtitle-units', str(units))

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert result['verdict'] == 'fail'
    assert [(f['scene_id'], f['check'], f['issue']) for f in result['findings']] == [
        ('tpl', 'presenter_component', 'visual scene layout has a presenter region but presenter is not visible'),
        ('free', 'presenter_component', 'presenter is visible in a visual scene whose layout has no presenter region'),
    ]


def make_el(
    scene_id: str, el_id: str, rect: dict, *, tag: str = 'div', own_text: bool = False,
    text: str = '', surface: bool = False, media: dict | None = None,
    svg_group_rect: dict | None = None, dom_id: int | None = None,
    ancestor_dom_ids: list[int] | None = None, ancestors: list[str] | None = None,
) -> dict:
    return {
        **({'domId': dom_id} if dom_id is not None else {}),
        **({'ancestorDomIds': ancestor_dom_ids} if ancestor_dom_ids is not None else {}),
        'selector': f'#{el_id}' if el_id else tag, 'id': el_id, 'tag': tag, 'label': f'{tag} {el_id}',
        'rect': rect, 'svgGroupRect': svg_group_rect, 'ownText': own_text, 'text': text, 'fontSize': 30,
        'isCaption': False, 'isUiText': False, 'isSceneRoot': False, 'sceneId': scene_id, 'lineCount': 1,
        'layoutIgnore': False, 'surface': surface, 'media': media, 'ancestors': ancestors or [],
        'overflowStyle': 'visible visible',
        'clientWidth': int(rect['width']), 'clientHeight': int(rect['height']),
        'scrollWidth': int(rect['width']), 'scrollHeight': int(rect['height']),
    }


def make_media(
    src: str, vis_rect: dict, *, tag: str = 'img', iw: int = 1600, ih: int = 900,
    scale: float | None = None, crop_box: dict | None = None, role: str = '',
    material_ref: str = '', complete: bool = True,
) -> dict:
    base = (
        {'tag': 'img', 'complete': complete, 'naturalWidth': iw, 'src': src}
        if tag == 'img' else {'tag': 'video', 'readyState': 4, 'error': False, 'src': src}
    )
    return {
        **base, 'intrinsicWidth': iw, 'intrinsicHeight': ih, 'objectFit': 'contain',
        'objectPosition': '50% 50%', 'mediaRole': role, 'materialRef': material_ref,
        'resolvedSrc': src, 'paintedRect': vis_rect,
        'scale': scale if scale is not None else (max(vis_rect['width'] / iw, vis_rect['height'] / ih) if iw and ih else None),
        'visibleRect': vis_rect, 'cropBox': crop_box if crop_box is not None else {'x': 0.0, 'y': 0.0, 'w': 1.0, 'h': 1.0},
    }


def scenes_ws(tmp_path: Path, scene_specs: list[tuple[str, str, list[dict], bool]]) -> tuple[Path, Path]:
    ws = tmp_path / 'ws'
    total = 5.0 * len(scene_specs)
    write_json(ws / 'inputs.json', {'orientation': 'landscape'})
    write_json(ws / 'composition/scene-config.json', {
        'version': 1, 'canvas': {'width': 1920, 'height': 1080}, 'total_s': total,
        'scenes': [
            visual_scene(sid, i * 5.0, (i + 1) * 5.0, borrowed_layout(layout_name))
            for i, (sid, layout_name, _, _) in enumerate(scene_specs)
        ],
    })
    write_silent_mp3(ws / 'voice_clone/narration.mp3', total)
    snaps_path = tmp_path / 'snapshots.json'
    write_json(snaps_path, [
        {
            'scene_id': sid, 'time': i * 5.0 + dt, 'sought': True, 'fontsStatus': 'loaded',
            'presenterVisible': presenter, 'elements': elements, 'captionTexts': [], 'captionDetails': [],
        }
        for i, (sid, _, elements, presenter) in enumerate(scene_specs)
        for dt in (0.1, 2.5, 4.9)
    ])
    return ws, snaps_path


def test_content_region_assignment_media_predicates_and_crop_fallback():
    module = load_script_module('check-composition.py', 'check_composition_regions')
    regions = module.RegionIndex(json.loads((ROOT / 'modules/layouts/landscape-presenter.json').read_text(encoding='utf-8')))
    assert composition_warnings.assign_content_region({'x': 120, 'y': 220, 'width': 500, 'height': 300}, regions)['id'] == 'main'
    assert module.assign_content_region({'x': 1200, 'y': 120, 'width': 500, 'height': 300}, regions)['id'] == 'side'
    assert composition_warnings.assign_content_region({'x': 10, 'y': 1010, 'width': 100, 'height': 50}, regions) is None

    box = {'x': 120, 'y': 220, 'width': 120, 'height': 80}
    zero_img = composition_warnings.content_media_metrics(
        make_el('s1', 'zi', box, tag='img', media=make_media('lazy.png', box, iw=0, ih=0, complete=False))
    )
    zero_vid = composition_warnings.content_media_metrics(
        make_el('s1', 'zv', box, tag='video', media=make_media('clip.mp4', box, tag='video', iw=0, ih=0))
    )
    icon_img = composition_warnings.content_media_metrics(
        make_el('s1', 'ic', box, tag='img', media=make_media('icon.png', box, iw=128, ih=128))
    )
    content_img = composition_warnings.content_media_metrics(
        make_el('s1', 'ci', box, tag='img', media=make_media('shot.png', box, iw=400, ih=300))
    )
    assert zero_img is not None and not composition_warnings.is_non_icon_content_media(zero_img)
    assert not composition_warnings.is_non_icon_content_media(zero_img, allow_zero_video=True)
    assert zero_vid is not None and not composition_warnings.is_non_icon_content_media(zero_vid)
    assert composition_warnings.is_non_icon_content_media(zero_vid, allow_zero_video=True)
    assert icon_img is not None and not composition_warnings.is_non_icon_content_media(icon_img)
    assert content_img is not None and composition_warnings.is_non_icon_content_media(content_img)

    pan_metrics = composition_warnings.content_media_metrics(make_el(
        's2', 'pan-zoom', {'x': 540, 'y': 20, 'width': 1600, 'height': 1000}, tag='img',
        media={
            **make_media('../materials/pan.png', {'x': 940, 'y': 220, 'width': 800, 'height': 500}, iw=1600, ih=1000, scale=1.0),
            'paintedRect': {'x': 540, 'y': 20, 'width': 1600, 'height': 1000}, 'cropBox': None,
        },
    ))
    assert pan_metrics['cropBox'] == pytest.approx({'x': 0.25, 'y': 0.20, 'w': 0.50, 'h': 0.50})


@pytest.mark.usefixtures('require_ffmpeg')
def test_media_size_scale_and_icon_or_zero_intrinsic_width_exclusions(tmp_path: Path):
    stamp = {'x': 200, 'y': 260, 'width': 500, 'height': 300}
    tiny_zero_img = {'x': 760, 'y': 260, 'width': 120, 'height': 80}
    tiny_zero_vid = {'x': 920, 'y': 260, 'width': 120, 'height': 80}
    tiny_icon = {'x': 1080, 'y': 260, 'width': 96, 'height': 96}
    left, right = {'x': 180, 'y': 260, 'width': 500, 'height': 300}, {'x': 820, 'y': 260, 'width': 500, 'height': 300}
    box_a, box_b, box_c = (
        {'x': 120, 'y': 220, 'width': 640, 'height': 360},
        {'x': 820, 'y': 220, 'width': 960, 'height': 540},
        {'x': 120, 'y': 620, 'width': 650, 'height': 320},
    )
    ws, snaps = scenes_ws(tmp_path, [
        ('s1', 'landscape', [
            make_el('s1', 'single-shot', stamp, media=make_media('shot1.png', stamp, iw=800, ih=480)),
            make_el('s1', 'unloaded-zero-img', tiny_zero_img, tag='img', media=make_media('lazy.png', tiny_zero_img, iw=0, ih=0, complete=False)),
            make_el('s1', 'unprobed-zero-vid', tiny_zero_vid, tag='video', media=make_media('raw.mp4', tiny_zero_vid, tag='video', iw=0, ih=0)),
            make_el('s1', 'ui-icon', tiny_icon, media=make_media('icon.png', tiny_icon, iw=64, ih=64, scale=1.5)),
        ], False),
        ('s2', 'landscape', [
            make_el('s2', 'left-shot', left, media=make_media('cmp1.png', left, iw=800, ih=480)),
            make_el('s2', 'right-shot', right, media=make_media('cmp2.png', right, iw=800, ih=480)),
        ], False),
        ('s3', 'landscape', [
            make_el('s3', 'std-downscale', box_a, media=make_media('a.png', box_a, iw=1600, ih=900, scale=0.40)),
            make_el('s3', 'uhd-ok', box_b, media=make_media('b.png', box_b, iw=2560, ih=1440, scale=0.40)),
            make_el('s3', 'lowres-upscale', box_c, media=make_media('c.png', box_c, iw=480, ih=240, scale=1.35)),
        ], False),
    ])

    _, report = run(ws, snaps)
    assert report['verdict'] == 'pass', report['findings']
    warnings = report['warnings']

    # s1: <img> with intrinsicWidth=0, <video> with intrinsicWidth=0, and 64px UI icon do NOT trigger media_too_small
    assert not any('#unloaded-zero-img' in w for w in warnings), warnings
    assert not any('#unprobed-zero-vid' in w for w in warnings), warnings
    assert not any('#ui-icon' in w for w in warnings), warnings
    s1_small = [w for w in warnings if w.startswith('[s1] media_too_small:')]
    assert len(s1_small) == 1 and '#single-shot' in s1_small[0] and 'N=1' in s1_small[0]

    # s2: two-up comparison (N=2) passes with no warnings
    assert not any(w.startswith('[s2]') for w in warnings), warnings

    # s3: standard downscale (<0.45) and upscale (>1.25) warn; UHD (>1920 at 0.40 >= 0.35) is clean
    blurry = [w for w in warnings if w.startswith('[s3] media_blurry_scale:')]
    assert len(blurry) == 2
    assert any('#std-downscale' in w and 'downscaled' in w for w in blurry)
    assert any('#lowres-upscale' in w and 'upscaled' in w for w in blurry)
    assert not any('#uhd-ok' in w for w in warnings)


@pytest.mark.usefixtures('require_ffmpeg')
def test_svg_overflow_overlap_occlusion_and_text_duplication_heuristics(tmp_path: Path):
    media_box = {'x': 100, 'y': 420, 'width': 640, 'height': 360}
    vid_box = {'x': 780, 'y': 420, 'width': 320, 'height': 240}
    icon_box = {'x': 780, 'y': 700, 'width': 150, 'height': 150}
    ws, snaps = scenes_ws(tmp_path, [('s1', 'landscape-presenter', [
        make_el('s1', 'main-p', {'x': 100, 'y': 210, 'width': 960, 'height': 60}, own_text=True,
                text='分布式调度器支持毫秒级故障恢复，集群资源利用率提升百分之四十', dom_id=10, ancestor_dom_ids=[1]),
        make_el('s1', 'main-inline-b', {'x': 240, 'y': 214, 'width': 220, 'height': 40}, tag='b', own_text=True,
                text='毫秒级故障恢复', dom_id=12, ancestor_dom_ids=[11, 10, 1]),
        make_el('s1', 'side-short-tag', {'x': 1200, 'y': 110, 'width': 180, 'height': 36}, own_text=True,
                text='核心要点', dom_id=20, ancestor_dom_ids=[1]),
        make_el('s1', 'side-dup-card', {'x': 1200, 'y': 170, 'width': 580, 'height': 120}, own_text=True,
                text='支持毫秒级故障恢复，集群资源利用率提升百分之四十', dom_id=21, ancestor_dom_ids=[1]),
        make_el('s1', 'bad-svg-text', {'x': 115, 'y': 310, 'width': 210, 'height': 30}, tag='text', own_text=True,
                text='超宽架构模块名称', svg_group_rect={'x': 130, 'y': 295, 'width': 150, 'height': 56}, dom_id=30, ancestor_dom_ids=[1]),
        make_el('s1', 'ok-bar-label', {'x': 420, 'y': 300, 'width': 90, 'height': 24}, tag='text', own_text=True,
                text='99.9%', svg_group_rect={'x': 445, 'y': 330, 'width': 40, 'height': 20}, dom_id=31, ancestor_dom_ids=[1]),
        make_el('s1', 'hero-img', media_box, media=make_media('hero.png', media_box, iw=1600, ih=900), dom_id=40, ancestor_dom_ids=[1]),
        make_el('s1', 'leader-tip', {'x': 735, 'y': 500, 'width': 40, 'height': 4}, surface=True, dom_id=41, ancestor_dom_ids=[1]),
        make_el('s1', 'occluding-pill', {'x': 200, 'y': 500, 'width': 160, 'height': 48}, own_text=True, surface=True,
                text='压在图上的浮标', dom_id=42, ancestor_dom_ids=[1]),
        make_el('s1', 'zero-vid', vid_box, tag='video', media=make_media('clip.mp4', vid_box, tag='video', iw=0, ih=0), dom_id=43, ancestor_dom_ids=[1]),
        make_el('s1', 'vid-pill', {'x': 820, 'y': 480, 'width': 140, 'height': 40}, own_text=True, surface=True,
                text='压在视频上', dom_id=44, ancestor_dom_ids=[1]),
        make_el('s1', 'card-icon', icon_box, media=make_media('badge.png', icon_box, iw=128, ih=128), dom_id=45, ancestor_dom_ids=[1]),
        make_el('s1', 'icon-pill', {'x': 800, 'y': 730, 'width': 100, 'height': 36}, own_text=True, surface=True,
                text='图标角标', dom_id=46, ancestor_dom_ids=[1]),
        make_el('s1', 'side-card-1', {'x': 1200, 'y': 340, 'width': 320, 'height': 140}, own_text=True, surface=True,
                text='独立卡片一', dom_id=50, ancestor_dom_ids=[1]),
        make_el('s1', 'side-card-2', {'x': 1320, 'y': 380, 'width': 320, 'height': 140}, own_text=True, surface=True,
                text='独立卡片二', dom_id=51, ancestor_dom_ids=[1]),
    ], True)])

    _, report = run(ws, snaps)
    assert report['verdict'] == 'pass', report['findings']
    warnings = report['warnings']
    assert any(w.startswith('[s1] svg_text_overflow:') and '#bad-svg-text' in w for w in warnings)
    assert not any('#ok-bar-label' in w for w in warnings)
    assert any(w.startswith('[s1] material_occlusion:') and '#occluding-pill' in w and '#hero-img' in w for w in warnings)
    assert any(w.startswith('[s1] material_occlusion:') and '#vid-pill' in w and '#zero-vid' in w for w in warnings)
    assert not any('#leader-tip' in w or '#card-icon' in w for w in warnings)
    assert any(w.startswith('[s1] element_overlap:') and '#side-card-1' in w and '#side-card-2' in w for w in warnings)
    assert not any('#main-inline-b' in w for w in warnings)
    assert any(w.startswith('[s1] region_text_duplication:') for w in warnings)


@pytest.mark.usefixtures('require_ffmpeg')
def test_media_reuse_and_crop_box_fallback_across_scenes(tmp_path: Path):
    cover_vis = {'x': 120, 'y': 220, 'width': 760, 'height': 475}
    pan_vis = {'x': 940, 'y': 220, 'width': 800, 'height': 500}
    vid_vis = {'x': 120, 'y': 720, 'width': 480, 'height': 220}
    ws, snaps = scenes_ws(tmp_path, [
        ('s1', 'landscape', [
            make_el('s1', 'c1', cover_vis, media={
                **make_media('../materials/cover.png', cover_vis, iw=800, ih=1000, scale=0.95),
                'objectFit': 'cover', 'objectPosition': '50% 0%',
                'paintedRect': {'x': 120, 'y': 220, 'width': 760, 'height': 950}, 'cropBox': None,
            }),
            make_el('s1', 'v1', vid_vis, tag='video', media=make_media('../materials/demo.mp4', vid_vis, tag='video', iw=0, ih=0)),
            make_el('s1', 'r1', pan_vis, media=make_media('crops/f2a.png', pan_vis, material_ref='paper/fig2')),
        ], False),
        ('s2', 'landscape', [
            make_el('s2', 'c2', cover_vis, media={
                **make_media('../materials/cover.png', cover_vis, iw=800, ih=1000, scale=0.95),
                'objectFit': 'cover', 'objectPosition': '50% 100%',
                'paintedRect': {'x': 120, 'y': -255, 'width': 760, 'height': 950}, 'cropBox': None,
            }),
            make_el('s2', 'v2', vid_vis, tag='video', media=make_media('../materials/demo.mp4', vid_vis, tag='video', iw=0, ih=0)),
            make_el('s2', 'p2', pan_vis, media={
                **make_media('../materials/pan.png', pan_vis, iw=1600, ih=1000, scale=0.50),
                'objectFit': 'fill', 'paintedRect': pan_vis, 'cropBox': None,
            }),
        ], False),
        ('s3', 'landscape', [
            make_el('s3', 'r3', cover_vis, media=make_media('crops/f2b.png', cover_vis, material_ref='paper/fig2')),
            make_el('s3', 'p3', pan_vis, tag='img', media={
                **make_media('../materials/pan.png', pan_vis, iw=1600, ih=1000, scale=1.0),
                'objectFit': 'none', 'paintedRect': {'x': 540, 'y': 20, 'width': 1600, 'height': 1000}, 'cropBox': None,
            }),
        ], False),
        ('s4', 'landscape', [
            make_el('s4', 'p4', pan_vis, tag='img', media={
                **make_media('../materials/pan.png?ver=2', pan_vis, iw=1600, ih=1000, scale=1.0),
                'objectFit': 'none', 'paintedRect': {'x': 524, 'y': 10, 'width': 1600, 'height': 1000}, 'cropBox': None,
            }),
        ], False),
    ])

    _, report = run(ws, snaps)
    assert report['verdict'] == 'pass', report['findings']
    reuse = [w for w in report['warnings'] if 'media_reuse' in w]
    assert reuse == [
        '[s2] media_reuse: adjacent reuse of video materials/demo.mp4 (previously used in s1)',
        '[s3] media_reuse: non-adjacent reuse of ref:paper/fig2 (previously used in s1)',
        '[s4] media_reuse: adjacent reuse of image materials/pan.png without focal zoom/pan shift (previously used in s3)',
    ]
