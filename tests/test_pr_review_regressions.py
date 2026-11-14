"""Behavior regressions from the follow-up PR review, including real CLI chains."""
from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import harvest_manifest
import test_pipeline_status as status_fixtures
import test_prepare_handoff as handoff_fixtures
import test_voice_subtitles as voice_fixtures

ROOT = Path(__file__).resolve().parent.parent


def load_script(filename: str):
    name = 'review_' + filename.replace('-', '_').replace('.py', '')
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


status = load_script('pipeline-status.py')
render = load_script('check-render.py')


def run(script: str, *args):
    proc = subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / script), *map(str, args)],
        capture_output=True, text=True, timeout=120,
    )
    assert len(proc.stdout.splitlines()) == 1, proc.stderr + proc.stdout
    return proc, json.loads(proc.stdout)


@pytest.mark.usefixtures('require_ffmpeg')
def test_crlf_producer_voice_and_composition_subtitles_chain(tmp_path: Path):
    ws = voice_fixtures.make_workspace(tmp_path)
    (ws / 'script.txt').write_bytes(voice_fixtures.SCRIPT_TEXT.replace('\n', '\r\n').encode('utf-8'))
    (ws / 'research-brief.md').write_text(status_fixtures.RESEARCH_BRIEF, encoding='utf-8')
    made, _ = run('make-narration.py', '--script', ws / 'script.txt',
                  '--lexicon', ws / 'tts-lexicon.json', '--output-dir', ws)
    assert made.returncode == 0
    assert status.check_narration_offsets(ws, 'narration-offsets.json').ok
    voiced = voice_fixtures.run_voice_subtitles(ws)
    assert voiced.returncode == 0, voiced.stderr + voiced.stdout
    scanned = voice_fixtures.run_pipeline_status(ws)
    assert '7-voice-subtitles' in scanned['completed_phases']
    inputs = json.loads((ws / 'inputs.json').read_text())
    inputs.update(layout='stage', template=None)
    status_fixtures.write_json(ws / 'inputs.json', inputs)
    prepared, _ = run('prepare-handoff.py', ws, 'composition')
    assert prepared.returncode == 0, prepared.stderr
    timeline_before = (ws / 'transcribe/timeline.json').read_bytes()
    subtitles, _ = run('align-narration.py', '--mode', 'subtitles',
        '--script', ws / 'script.txt', '--narration', ws / 'narration.txt',
        '--offsets', ws / 'narration-offsets.json', '--transcript', ws / 'transcribe/transcript.json',
        '--layout', ws / 'modules/layouts/stage.json',
        '--units-output', ws / 'composition/assets/subtitle-units.json')
    assert subtitles.returncode == 0, subtitles.stderr + subtitles.stdout
    assert (ws / 'transcribe/timeline.json').read_bytes() == timeline_before
    assert json.loads((ws / 'composition/assets/subtitle-units.json').read_text())['units']
    # 等长编辑不再由内容哈希识别：偏移表仍按字数校验通过。
    (ws / 'script.txt').write_bytes((ws / 'script.txt').read_bytes().replace('甲'.encode(), '丙'.encode(), 1))
    assert status.check_narration_offsets(ws, 'narration-offsets.json').ok


@pytest.mark.parametrize('version', [None, 1, 3])
def test_status_rejects_old_manifest_versions(tmp_path: Path, version):
    status_fixtures.complete_through_catalog(tmp_path)
    manifest = json.loads((tmp_path / 'harvest_page/manifest.json').read_text())
    if version is None:
        manifest.pop('version', None)
    else:
        manifest['version'] = version
    status_fixtures.write_json(tmp_path / 'harvest_page/manifest.json', manifest)
    _, result = run('pipeline-status.py', tmp_path)
    assert result['next_phase']['id'] == '4-material-harvest'
    assert 'version' in result['next_phase']['problems']['harvest_page/manifest.json']
    assert '4-material-harvest' not in result['completed_phases']


@pytest.mark.parametrize('value', ['/old-project/a.png', '~/a.png', '../a.png', 'C:/old/a.png'])
def test_persisted_paths_are_rejected_before_upsert_or_migration(tmp_path: Path, value: str):
    harvest_manifest.upsert_entries(tmp_path, [{
        'slug': 'one', 'success': True, 'images': [], 'videos': [],
    }])
    manifest_path = tmp_path / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['entries'][0]['images'] = [{'id': 'img', 'local_path': value}]
    status_fixtures.write_json(manifest_path, manifest)
    before = manifest_path.read_bytes()
    with pytest.raises(ValueError, match='local_path'):
        harvest_manifest.load(tmp_path)
    with pytest.raises(ValueError, match='local_path'):
        harvest_manifest.upsert_entries(tmp_path, [{'slug': 'two', 'images': [], 'videos': []}])
    assert manifest_path.read_bytes() == before
    assert not (tmp_path / 'two').exists()


@pytest.mark.parametrize('kind, field', [('images', 'local_path'), ('videos', 'subtitle_path')])
def test_catalog_rejects_persisted_absolute_paths(tmp_path: Path, kind: str, field: str):
    status_fixtures.complete_through_catalog(tmp_path)
    catalog = copy.deepcopy(status_fixtures.CATALOG)
    catalog['entries'][0][kind][0][field] = '/old-project/file'
    status_fixtures.write_json(tmp_path / 'material-catalog.json', catalog)
    _, result = run('pipeline-status.py', tmp_path)
    assert result['next_phase']['id'] == '5-material-catalog'
    assert field in result['next_phase']['problems']['material-catalog.json']


def write_edited_template_contract(ws: Path) -> Path:
    rel = Path('modules/templates/github-trending/github-trending.json')
    path = ws / rel
    contract = json.loads((ROOT / rel).read_text(encoding='utf-8'))
    contract['preferred_layouts'] = ['stage']
    status_fixtures.write_json(path, contract)
    return path


def test_edited_template_copy_is_advisory_and_refresh_repairs_it(tmp_path: Path):
    # preferred_layouts 是推荐不是门槛：工作区副本被改过不再阻止准备 handoff；
    # --refresh 仍会把副本恢复成库里的声明。
    ws = handoff_fixtures.make_workspace(tmp_path, 'composition', template='github-trending')
    path = write_edited_template_contract(ws)
    proc, result = run('prepare-handoff.py', ws, 'composition')
    assert proc.returncode == 0, result
    assert (ws / 'composition-handoff.md').exists()
    repaired, _ = run('prepare-handoff.py', ws, 'composition', '--refresh')
    assert repaired.returncode == 0, repaired.stderr
    assert json.loads(path.read_text(encoding='utf-8'))['preferred_layouts'] == ['presenter']


@pytest.mark.parametrize('template', [{}, [], '', '../escape'])
def test_legacy_global_template_values_are_not_gates(tmp_path: Path, template):
    # 模板是逐 scene 的决定：inputs.json 的旧全局 template 字段无论是什么值，
    # 都不再制造 inputs.json#template 问题。
    status_fixtures.complete_through_voice_subtitles(tmp_path, fetch_materials=False, template=template)
    _, result = run('pipeline-status.py', tmp_path)
    assert '1-gather-inputs' in result['completed_phases']
    assert '7-voice-subtitles' in result['completed_phases']
    assert result['next_phase']['id'] == '8-composition'
    assert 'inputs.json#template' not in result['next_phase']['problems']


@pytest.mark.parametrize('step', ['catalog', 'script'])
def test_handoff_accepts_only_its_declared_step_inputs(tmp_path: Path, step: str):
    ws = handoff_fixtures.make_workspace(tmp_path, step)
    inputs = json.loads((ws / 'inputs.json').read_text())
    for field in ('source', 'design', 'orientation', 'layout', 'template'):
        inputs.pop(field, None)
    # Unrelated visual values must not be inspected, even when present.
    inputs.update(layout={}, template='../unused', composition_requests=3)
    status_fixtures.write_json(ws / 'inputs.json', inputs)
    proc, result = run('prepare-handoff.py', ws, step)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert result['success']


def test_layout_copy_change_invalidates_nothing_until_an_explicit_redo(tmp_path: Path):
    path = tmp_path / 'modules/layouts/stage.json'
    path.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / 'modules/layouts/stage.json', path)
    status_fixtures.settle(tmp_path, fetch_materials=False)
    phase_7 = {name: (tmp_path / name).read_bytes() for name in (
        'voice_clone/narration.mp3', 'transcribe/transcript.json', 'transcribe/timeline.json')}
    data = json.loads(path.read_text())
    data['caption']['width_px'] = 500
    status_fixtures.write_json(path, data)
    _, result = run('pipeline-status.py', tmp_path)
    # 没有内容新鲜度追踪：layout 副本改动不自动判 Phase 8 过期。
    assert result['next_phase'] is None
    assert '8-composition' in result['completed_phases']
    assert '7-voice-subtitles' in result['completed_phases']
    assert all((tmp_path / name).read_bytes() == contents for name, contents in phase_7.items())


@pytest.mark.parametrize('paper', [False, True])
def test_catalog_content_changes_do_not_invalidate_any_phase(tmp_path: Path, paper: bool):
    status_fixtures.settle(tmp_path, fetch_materials=False, input_mode='paper' if paper else 'standard')
    path = tmp_path / 'material-catalog.json'
    catalog = json.loads(path.read_text())
    catalog['notes'] = 'only catalog changed'
    status_fixtures.write_json(path, catalog)
    _, result = run('pipeline-status.py', tmp_path)
    assert result['next_phase'] is None


@pytest.mark.parametrize('orientation, width, height, matches', [
    ('landscape', 1920, 1080, True), ('landscape', 1280, 720, False),
    ('portrait', 1080, 1920, True), ('portrait', 1080, 1440, False),
    ('portrait-3:4', 1080, 1440, True), ('portrait-3:4', 1080, 1920, False),
])
def test_render_metadata_obeys_the_exact_canvas_contract(orientation, width, height, matches):
    probe = dict(width=width, height=height, has_audio=True,
                 audio_duration_s=1.0, container_duration_s=1.0)
    findings = render.check_container(probe, orientation)
    assert (not findings) == matches


def test_ambiguous_clips_never_select_the_first_window():
    index = status.CatalogIndex({'a/video'}, {'a/video': [(12, 18.5), (12.015, 18.515)]})
    for order in (index.clips['a/video'], list(reversed(index.clips['a/video']))):
        index.clips['a/video'] = order
        with pytest.raises(ValueError, match='ambiguous'):
            status.parse_ref('a/video:12.009-18.509', index)


def test_required_refs_are_deduplicated_by_resolved_identity():
    catalog = copy.deepcopy(status_fixtures.CATALOG)
    catalog['required_material_refs'] = ['example/vid_001:12-18.5', 'example/vid_001:12.00-18.50']
    result = status.check_required_refs(catalog)
    assert not result.ok
    assert 'repeats' in result.detail


def test_status_does_not_gate_on_the_template_declaration(tmp_path: Path):
    # preferred_layouts 是建议性的：状态脚本不读模板声明做兼容性门槛。
    status_fixtures.settle(tmp_path, fetch_materials=False, layout='presenter', template='github-trending')
    write_edited_template_contract(tmp_path)
    _, result = run('pipeline-status.py', tmp_path)
    assert result['next_phase'] is None


def test_materializing_identical_resource_bytes_invalidates_nothing(tmp_path: Path):
    status_fixtures.settle(tmp_path, fetch_materials=False)
    for name in ('modules/layouts/stage.json', 'modules/designs/default/default.md'):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, path)
    _, result = run('pipeline-status.py', tmp_path)
    assert result['next_phase'] is None


@pytest.mark.parametrize('contents', ['{broken', ''])
def test_no_material_mode_never_reads_a_residual_catalog(tmp_path: Path, contents: str):
    status_fixtures.settle(tmp_path, fetch_materials=False)
    (tmp_path / 'material-catalog.json').write_text(contents, encoding='utf-8')
    _, result = run('pipeline-status.py', tmp_path)
    assert result['next_phase'] is None


def test_duplicate_qualified_material_ids_are_reported_as_ambiguous():
    catalog = copy.deepcopy(status_fixtures.CATALOG)
    catalog['entries'][0]['images'].append(dict(catalog['entries'][0]['images'][0]))
    index = status.catalog_index_from_data(catalog)
    with pytest.raises(ValueError, match='ambiguous'):
        status.parse_ref('example/img_001', index)


def test_unreadable_offset_source_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    status_fixtures.write_script(tmp_path, status_fixtures.SCRIPT_TXT)
    read_text = Path.read_text

    def denied(path, *args, **kwargs):
        if path == tmp_path / 'script.txt':
            raise PermissionError('injected unreadable script.txt')
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'read_text', denied)
    result = status.check_narration_offsets(tmp_path, 'narration-offsets.json')
    assert not result.ok
    assert 'unreadable script.txt' in result.detail
