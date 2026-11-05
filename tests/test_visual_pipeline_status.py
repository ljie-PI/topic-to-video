"""Scene-mode Phase 8/9 state and freshness without changing legacy fixtures."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import media
import video_contract
from composition_hash import composition_sources_fingerprint, visual_contract_fingerprint
from test_pipeline_status import complete_all, parse_result, read_stamps, run_cli

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
        'sources_sha256': composition_sources_fingerprint(ws / 'composition'),
        'visual_contract_sha256': visual_contract_fingerprint(
            ws / video_contract.VISUAL_SCENES_PATH, [scene['layout_path'] for scene in scenes],
        ),
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


def test_visual_workspace_completes_without_legacy_layout_and_tracks_only_used_layouts(tmp_path: Path):
    make_visual_workspace(tmp_path)

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase'] is None, result
    stamp = read_stamps(tmp_path)['phases']['8-composition']
    assert video_contract.VISUAL_SCENES_PATH in stamp['products']
    assert 'inputs.json#layout' not in stamp['upstream']
    assert 'modules/layouts/presenter.json' in stamp['upstream']
    assert 'modules/layouts/stage.json' in stamp['upstream']
    assert 'modules/layouts/portrait.json' not in stamp['upstream']
    assert 'modules/layouts/None.json' not in stamp['upstream']
    assert read_stamps(tmp_path)['phases']['9-check-mix']['upstream'][video_contract.VISUAL_SCENES_PATH]


def test_scene_declaration_change_rejects_old_report_without_touching_phase_7(tmp_path: Path):
    make_visual_workspace(tmp_path)
    parse_result(run_cli(str(tmp_path)))
    before = (tmp_path / 'transcribe/timeline.json').read_bytes()
    path = tmp_path / video_contract.VISUAL_SCENES_PATH
    data = json.loads(path.read_text(encoding='utf-8'))
    data['scenes'][0]['end_s'] -= 0.1
    data['scenes'][1]['begin_s'] -= 0.1
    write_json(path, data)

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] == '8-composition'
    assert 'composition/check-composition.json' in result['corrupt_products']
    assert '7-voice-subtitles' in result['completed_phases']
    assert (tmp_path / 'transcribe/timeline.json').read_bytes() == before
    restamp = run_cli(str(tmp_path), '--restamp', '8-composition')
    assert restamp.returncode == 1


def test_used_layout_edit_invalidates_but_unused_layout_edit_does_not(tmp_path: Path):
    make_visual_workspace(tmp_path)
    parse_result(run_cli(str(tmp_path)))
    used = tmp_path / 'modules/layouts/stage.json'
    used.parent.mkdir(parents=True, exist_ok=True)
    used.write_bytes((ROOT / 'modules/layouts/stage.json').read_bytes())
    # Materialize the effective copy before the initial accepted stamp.
    refresh_report(tmp_path)
    parse_result(run_cli(str(tmp_path)))

    unused = tmp_path / 'modules/layouts/portrait.json'
    unused.parent.mkdir(parents=True, exist_ok=True)
    unused.write_text('{"changed": true}', encoding='utf-8')
    assert parse_result(run_cli(str(tmp_path)))['next_phase'] is None

    data = json.loads(used.read_text(encoding='utf-8'))
    data['caption']['font_size_px'] = 34
    write_json(used, data)
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '8-composition'
    assert 'visual_contract_sha256' in result['next_phase']['problems']['composition/check-composition.json']
    assert '7-voice-subtitles' in result['completed_phases']


def test_identical_effective_layout_copy_does_not_invalidate_report(tmp_path: Path):
    make_visual_workspace(tmp_path)
    parse_result(run_cli(str(tmp_path)))
    copy = tmp_path / 'modules/layouts/stage.json'
    copy.parent.mkdir(parents=True, exist_ok=True)
    copy.write_bytes((ROOT / 'modules/layouts/stage.json').read_bytes())

    assert parse_result(run_cli(str(tmp_path)))['next_phase'] is None


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
    write_json(tmp_path / 'inputs.json', inputs)

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] == '8-composition'
    assert video_contract.VISUAL_SCENES_PATH in result['missing_products']


def test_phase_9_rechecks_visual_scene_identity_after_phase_8_is_restamped(tmp_path: Path):
    make_visual_workspace(tmp_path)
    parse_result(run_cli(str(tmp_path)))
    path = tmp_path / video_contract.VISUAL_SCENES_PATH
    data = json.loads(path.read_text(encoding='utf-8'))
    data['scenes'][1]['scene_id'] = 'renamed_visual'
    write_json(path, data)
    refresh_report(tmp_path)
    assert run_cli(str(tmp_path), '--restamp', '8-composition').returncode == 0

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] == '9-check-mix'
    assert result['next_phase']['reason'] == 'stale'
    assert result['next_phase']['changed_upstream'] == [video_contract.VISUAL_SCENES_PATH]
