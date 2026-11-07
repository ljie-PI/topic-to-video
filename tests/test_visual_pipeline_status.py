"""Scene-mode Phase 8/9 state without changing legacy fixtures.

指纹删除后，状态脚本只验收产物与报告数据本身：视觉声明改了、layout 副本改了
都不会让 Phase 8/9 自动过期；需要重做时由主 agent 显式登记。
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import media
import video_contract
from test_pipeline_status import complete_all, parse_result, run_cli

pytestmark = pytest.mark.usefixtures('require_ffmpeg')
ROOT = Path(__file__).resolve().parent.parent


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')


def write_audio(ws: Path) -> float:
    path = ws / 'voice_clone/narration.mp3'
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        'ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=mono',
        '-t', '2.6', '-c:a', 'libmp3lame', str(path),
    ], capture_output=True, check=True)
    return media.probe_duration(path)


def refresh_report(ws: Path) -> None:
    scenes, problem = _load_direct(ws)
    assert problem is None, problem
    write_json(ws / 'composition/check-composition.json', {
        'success': True, 'verdict': 'pass', 'findings': [],
        'scenes_checked': [
            {'scene_id': scene['scene_id'], 'layout': scene['layout'], 'check_times': [scene['begin_s']]}
            for scene in scenes
        ],
    })


def _load_direct(ws: Path):
    declaration = ws / video_contract.VISUAL_SCENES_PATH
    try:
        duration = media.probe_duration(ws / 'voice_clone/narration.mp3')
        return video_contract.load_visual_scenes(
            declaration, ROOT, 'landscape', duration, ws=ws,
        ), None
    except ValueError as exc:
        return None, str(exc)


def make_visual_workspace(ws: Path, layouts: tuple[str, str] = ('presenter', 'stage')) -> None:
    complete_all(ws)
    duration = write_audio(ws)
    inputs = json.loads((ws / 'inputs.json').read_text(encoding='utf-8'))
    inputs.pop('layout')
    write_json(ws / 'inputs.json', inputs)
    write_json(ws / video_contract.VISUAL_SCENES_PATH, {'version': 1, 'scenes': [
        {'scene_id': 'visual_a', 'begin_s': 0, 'end_s': duration / 2, 'layout': layouts[0]},
        {'scene_id': 'visual_b', 'begin_s': duration / 2, 'end_s': duration, 'layout': layouts[1]},
    ]})
    refresh_report(ws)


def test_visual_workspace_completes_without_legacy_layout_and_without_state_files(tmp_path: Path):
    make_visual_workspace(tmp_path)

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase'] is None, result
    # 指纹状态文件已删除：扫描只依赖产物、报告数据、审稿与重做记录。
    assert not (tmp_path / '.pipeline' / 'stamps.json').exists()
    assert not (tmp_path / '.pipeline' / 'fpcache.json').exists()


def test_old_or_corrupt_fingerprint_state_files_do_not_block_a_fresh_scan(tmp_path: Path):
    # 旧指纹文件存在或损坏都不影响新扫描，也不被误删其他用户状态。
    make_visual_workspace(tmp_path)
    pipeline = tmp_path / '.pipeline'
    pipeline.mkdir(exist_ok=True)
    (pipeline / 'stamps.json').write_text('garbage', encoding='utf-8')
    (pipeline / 'fpcache.json').write_text('{broken', encoding='utf-8')

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase'] is None
    # 不再读写的旧文件原样保留（不属于本脚本的状态，不替用户清理）。
    assert (pipeline / 'stamps.json').read_text(encoding='utf-8') == 'garbage'
    assert (pipeline / 'fpcache.json').read_text(encoding='utf-8') == '{broken'


def test_scene_declaration_change_after_the_report_is_not_auto_invalidating(tmp_path: Path):
    make_visual_workspace(tmp_path)
    parse_result(run_cli(str(tmp_path)))
    before = (tmp_path / 'transcribe/timeline.json').read_bytes()
    path = tmp_path / video_contract.VISUAL_SCENES_PATH
    data = json.loads(path.read_text(encoding='utf-8'))
    data['scenes'][0]['end_s'] -= 0.1
    data['scenes'][1]['begin_s'] -= 0.1
    write_json(path, data)

    result = parse_result(run_cli(str(tmp_path)))

    # 声明仍然合法（覆盖与边界都成立），scenes_checked 比对的是报告里记录的
    # 声明快照：没有内容指纹，状态脚本不会自动判报告失效。
    assert result['next_phase'] is None
    assert '7-voice-subtitles' in result['completed_phases']
    assert (tmp_path / 'transcribe/timeline.json').read_bytes() == before


def test_used_layout_edit_after_the_report_is_not_auto_invalidating(tmp_path: Path):
    make_visual_workspace(tmp_path)
    parse_result(run_cli(str(tmp_path)))
    used = tmp_path / 'modules/layouts/stage.json'
    used.parent.mkdir(parents=True, exist_ok=True)
    used.write_bytes((ROOT / 'modules/layouts/stage.json').read_bytes())
    refresh_report(tmp_path)
    parse_result(run_cli(str(tmp_path)))

    unused = tmp_path / 'modules/layouts/portrait.json'
    unused.parent.mkdir(parents=True, exist_ok=True)
    unused.write_text('{"changed": true}', encoding='utf-8')
    assert parse_result(run_cli(str(tmp_path)))['next_phase'] is None

    # 有效 layout 副本被改：声明与 report 仍旧合法时，状态脚本不自动判失效；
    # 需要按修改范围显式登记 Phase 8 重做并重跑 check-composition。
    data = json.loads(used.read_text(encoding='utf-8'))
    data['caption']['font_size_px'] = 34
    write_json(used, data)
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase'] is None
    assert '7-voice-subtitles' in result['completed_phases']


def test_scene_declaration_error_is_still_reported_as_a_corrupt_product(tmp_path: Path):
    # 删除的是指纹比对，不是声明本身的校验：不合法的场景声明仍判损坏。
    make_visual_workspace(tmp_path)
    parse_result(run_cli(str(tmp_path)))
    path = tmp_path / video_contract.VISUAL_SCENES_PATH
    data = json.loads(path.read_text(encoding='utf-8'))
    data['scenes'][1]['end_s'] = 0.5  # 覆盖错误：最后一个场景够不到配音时长
    write_json(path, data)

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] == '8-composition'
    assert video_contract.VISUAL_SCENES_PATH in result['corrupt_products']
    assert '7-voice-subtitles' in result['completed_phases']


def test_identical_scene_bytes_recopied_do_not_invalidate(tmp_path: Path):
    make_visual_workspace(tmp_path)
    parse_result(run_cli(str(tmp_path)))
    path = tmp_path / video_contract.VISUAL_SCENES_PATH
    original = path.read_bytes()
    path.write_bytes(original)

    assert parse_result(run_cli(str(tmp_path)))['next_phase'] is None


def test_template_must_support_every_visual_scene_layout(tmp_path: Path):
    make_visual_workspace(tmp_path, layouts=('stage', 'stage'))
    inputs = json.loads((tmp_path / 'inputs.json').read_text(encoding='utf-8'))
    inputs['template'] = 'github'
    write_json(tmp_path / 'inputs.json', inputs)

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] == '8-composition'
    assert 'not stage' in result['next_phase']['problems']['inputs.json#template']


def test_no_visual_declaration_or_legacy_layout_is_missing_phase_8_product(tmp_path: Path):
    complete_all(tmp_path)
    inputs = json.loads((tmp_path / 'inputs.json').read_text(encoding='utf-8'))
    inputs.pop('layout')
    inputs['template'] = 'github'
    write_json(tmp_path / 'inputs.json', inputs)

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] == '8-composition'
    assert video_contract.VISUAL_SCENES_PATH in result['missing_products']
    assert 'inputs.json#template' not in result['next_phase']['problems']


def test_corrupt_visual_declaration_with_compatible_layouts_does_not_blame_template(tmp_path: Path):
    make_visual_workspace(tmp_path, layouts=('presenter', 'presenter'))
    inputs = json.loads((tmp_path / 'inputs.json').read_text(encoding='utf-8'))
    inputs['template'] = 'github'
    write_json(tmp_path / 'inputs.json', inputs)
    path = tmp_path / video_contract.VISUAL_SCENES_PATH
    data = json.loads(path.read_text(encoding='utf-8'))
    data['scenes'][1]['end_s'] = 0.5  # Coverage error, but declared layouts are all presenter.
    write_json(path, data)

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] == '8-composition'
    assert video_contract.VISUAL_SCENES_PATH in result['corrupt_products']
    assert 'inputs.json#template' not in result['next_phase']['problems']


def test_phase_9_is_not_auto_invalidated_after_a_phase_8_redo(tmp_path: Path):
    make_visual_workspace(tmp_path)
    parse_result(run_cli(str(tmp_path)))
    path = tmp_path / video_contract.VISUAL_SCENES_PATH
    data = json.loads(path.read_text(encoding='utf-8'))
    data['scenes'][1]['scene_id'] = 'renamed_visual'
    write_json(path, data)
    refresh_report(tmp_path)

    # 显式登记 Phase 8 重做并结束后，Phase 9 保持完成——QA/混音是否重跑由主
    # agent 按交付范围显式登记，不由文件变化推断。
    redo_proc = run_cli(
        str(tmp_path), '--redo', '8-composition', '--reason', '视觉场景重命名',
    )
    assert redo_proc.returncode == 0, redo_proc.stderr
    finish = run_cli(str(tmp_path), '--finish', '8-composition')
    assert finish.returncode == 0, finish.stderr

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase'] is None
