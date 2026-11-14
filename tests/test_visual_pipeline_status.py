"""Scene-mode Phase 8/9 state without changing legacy fixtures.

指纹删除后，状态脚本只验收产物与报告数据本身：scene-config 改了、preset 声明改
了都不会让 Phase 8/9 自动过期；需要重做时由主 agent 显式登记。
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import media
import scene_config
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


def borrowed_layout(name: str) -> dict:
    data = json.loads((ROOT / 'modules' / 'layouts' / f'{name}.json').read_text(encoding='utf-8'))
    return {'preset': name, 'regions': data['regions'], 'caption': data['caption']}


def visual_scene(scene_id: str, begin: float, end: float, layout: dict, *, template=None) -> dict:
    return {
        'scene_id': scene_id,
        'source_scene_ids': ['scene_1'],
        'begin_s': begin,
        'end_s': end,
        'template': template,
        'layout': layout,
    }


def scene_config_doc(duration: float, layouts: tuple[str, str]) -> dict:
    return {
        'version': 1,
        'canvas': {'width': 1920, 'height': 1080},
        'total_s': duration,
        'scenes': [
            visual_scene('visual_a', 0, duration / 2, borrowed_layout(layouts[0])),
            visual_scene('visual_b', duration / 2, duration, borrowed_layout(layouts[1])),
        ],
    }


def refresh_report(ws: Path) -> None:
    config = json.loads((ws / scene_config.SCENE_CONFIG_PATH).read_text(encoding='utf-8'))
    write_json(ws / 'composition/check-composition.json', {
        'success': True, 'verdict': 'pass', 'findings': [],
        'scenes_checked': [
            {'scene_id': scene['scene_id'], 'layout': scene['layout']['preset'], 'check_times': [scene['begin_s']]}
            for scene in config['scenes']
        ],
    })


def make_visual_workspace(ws: Path, layouts: tuple[str, str] = ('landscape-presenter', 'landscape')) -> None:
    complete_all(ws)
    duration = write_audio(ws)
    inputs = json.loads((ws / 'inputs.json').read_text(encoding='utf-8'))
    inputs.pop('layout', None)
    write_json(ws / 'inputs.json', inputs)
    write_json(ws / scene_config.SCENE_CONFIG_PATH, scene_config_doc(duration, layouts))
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


def test_scene_config_change_after_the_report_is_not_auto_invalidating(tmp_path: Path):
    make_visual_workspace(tmp_path)
    parse_result(run_cli(str(tmp_path)))
    before = (tmp_path / 'transcribe/timeline.json').read_bytes()
    path = tmp_path / scene_config.SCENE_CONFIG_PATH
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


def test_scene_config_error_is_still_reported_as_a_corrupt_product(tmp_path: Path):
    # 删除的是指纹比对，不是配置本身的校验：不合法的场景配置仍判损坏。
    make_visual_workspace(tmp_path)
    parse_result(run_cli(str(tmp_path)))
    path = tmp_path / scene_config.SCENE_CONFIG_PATH
    data = json.loads(path.read_text(encoding='utf-8'))
    data['scenes'][1]['end_s'] = 0.5  # 覆盖错误：最后一个场景够不到 total_s
    write_json(path, data)

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] == '8-composition'
    assert scene_config.SCENE_CONFIG_PATH in result['corrupt_products']
    assert '7-voice-subtitles' in result['completed_phases']


def test_identical_scene_bytes_recopied_do_not_invalidate(tmp_path: Path):
    make_visual_workspace(tmp_path)
    parse_result(run_cli(str(tmp_path)))
    path = tmp_path / scene_config.SCENE_CONFIG_PATH
    original = path.read_bytes()
    path.write_bytes(original)

    assert parse_result(run_cli(str(tmp_path)))['next_phase'] is None


def test_no_visual_config_is_a_missing_phase_8_product(tmp_path: Path):
    complete_all(tmp_path)
    (tmp_path / scene_config.SCENE_CONFIG_PATH).unlink()
    inputs = json.loads((tmp_path / 'inputs.json').read_text(encoding='utf-8'))
    inputs.pop('layout', None)
    inputs['template'] = 'github-trending'  # 旧全局字段不再是门槛，只保留原样
    write_json(tmp_path / 'inputs.json', inputs)

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] == '8-composition'
    assert scene_config.SCENE_CONFIG_PATH in result['missing_products']
    assert 'inputs.json#template' not in result['next_phase']['problems']


def test_declared_template_resources_must_exist(tmp_path: Path):
    # 模板的采用是逐 scene 的决定，但声明的模板与场景部分必须真实存在：
    # 不存在的模板资源在 scene-config 校验里报 corrupt，且不牵连其他 scene。
    make_visual_workspace(tmp_path, layouts=('landscape', 'landscape'))
    path = tmp_path / scene_config.SCENE_CONFIG_PATH
    data = json.loads(path.read_text(encoding='utf-8'))
    data['scenes'][1]['template'] = {'name': 'github-trending', 'scene': 'project-cover'}
    write_json(path, data)
    refresh_report(tmp_path)
    assert parse_result(run_cli(str(tmp_path)))['next_phase'] is None

    data['scenes'][1]['template'] = {'name': 'github-trending', 'scene': 'no-such-scene'}
    write_json(path, data)

    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '8-composition'
    assert scene_config.SCENE_CONFIG_PATH in result['corrupt_products']
    assert 'no-such-scene' in result['next_phase']['problems'][scene_config.SCENE_CONFIG_PATH]


def test_free_layout_scene_without_template_is_a_normal_path(tmp_path: Path):
    make_visual_workspace(tmp_path)
    path = tmp_path / scene_config.SCENE_CONFIG_PATH
    data = json.loads(path.read_text(encoding='utf-8'))
    data['scenes'][0]['template'] = None
    data['scenes'][0]['layout'] = {
        'preset': None,
        'regions': [
            {'id': 'main', 'kind': 'content', 'rect': {'x': 96, 'y': 80, 'width': 1728, 'height': 820}},
            {'id': 'caption', 'kind': 'reserved', 'component': 'caption-bar',
             'rect': {'x': 96, 'y': 930, 'width': 1728, 'height': 120}},
        ],
        'caption': {'width_px': 1728, 'font_size_px': 36, 'max_lines': 2},
    }
    write_json(path, data)
    refresh_report(tmp_path)

    assert parse_result(run_cli(str(tmp_path)))['next_phase'] is None


def test_phase_9_is_not_auto_invalidated_after_a_phase_8_redo(tmp_path: Path):
    make_visual_workspace(tmp_path)
    parse_result(run_cli(str(tmp_path)))
    path = tmp_path / scene_config.SCENE_CONFIG_PATH
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
