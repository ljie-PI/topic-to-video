"""Public composition/design.json contract and its real consumers."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import composition_design
import video_contract
from test_pipeline_status import complete_all, parse_result, run_cli as run_status

REPO_ROOT = Path(__file__).resolve().parent.parent


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')


def preset_design(name: str = 'github') -> dict:
    preset = video_contract.load_design_preset(REPO_ROOT, name)
    return {
        'version': 1,
        'source': 'preset',
        'preset': name,
        'tokens': copy.deepcopy(preset['tokens']),
        'min_font_px': dict(preset['min_font_px']),
    }


def custom_design() -> dict:
    design = preset_design()
    design.update(source='custom', preset=None)
    design['tokens']['--c-canvas'] = '#101418'
    design['min_font_px'] = {'reading': 31, 'ui': 23}
    return design


def load(path: Path, payload: dict, *, inputs: dict | None = None) -> dict:
    write_json(path, payload)
    return composition_design.load_composition_design(path, skill_root=REPO_ROOT, inputs=inputs)


@pytest.mark.parametrize('payload', [preset_design(), custom_design()], ids=['preset', 'custom'])
def test_public_reader_accepts_preset_and_custom_contracts(tmp_path: Path, payload: dict):
    result = load(tmp_path / 'composition' / 'design.json', payload)

    assert result == payload
    assert set(result['tokens']) == set(video_contract.DESIGN_TOKEN_NAMES)
    assert 'fonts' not in result


@pytest.mark.parametrize(
    'mutate, message',
    [
        (lambda data: data.update(version=True), 'version'),
        (lambda data: data.update(source='borrowed'), 'source'),
        (lambda data: data.update(source='custom'), 'preset'),
        (lambda data: data.update(preset='default'), 'tokens'),
        (lambda data: data.update(fonts={}), 'exactly'),
        (lambda data: data['tokens'].pop('--c-canvas'), '--c-canvas'),
        (lambda data: data['min_font_px'].update(reading=0), 'positive integers'),
        (lambda data: data['min_font_px'].update(ui=True), 'positive integers'),
    ],
    ids=['boolean-version', 'source', 'custom-preset', 'preset-drift', 'fonts-root-field', 'missing-token', 'reading-floor', 'ui-floor'],
)
def test_public_reader_rejects_invalid_contracts(tmp_path: Path, mutate, message: str):
    payload = preset_design()
    mutate(payload)
    path = tmp_path / 'composition' / 'design.json'
    write_json(path, payload)

    with pytest.raises(ValueError, match=message):
        composition_design.load_composition_design(path, skill_root=REPO_ROOT)


def test_custom_contract_enforces_null_preset_and_22px_ui_floor(tmp_path: Path):
    bad_preset = custom_design()
    bad_preset['preset'] = 'github'
    with pytest.raises(ValueError, match='preset must be null'):
        load(tmp_path / 'composition' / 'design.json', bad_preset)

    payload = custom_design()
    payload['min_font_px']['ui'] = 21
    with pytest.raises(ValueError, match='ui must be at least 22px'):
        load(tmp_path / 'composition' / 'design.json', payload)

    payload['min_font_px']['ui'] = 22
    assert load(tmp_path / 'composition' / 'design.json', payload) == payload


def test_inputs_constraints_default_to_preset_and_allow_custom_only_with_user_requests(tmp_path: Path):
    path = tmp_path / 'composition' / 'design.json'

    # 无 composition_requests：必须从库内 preset 选择，拒绝自造 custom。
    assert load(path, preset_design('default'), inputs={}) == preset_design('default')
    assert load(path, preset_design('github'), inputs={}) == preset_design('github')
    with pytest.raises(ValueError, match='composition_requests'):
        load(path, custom_design(), inputs={})
    with pytest.raises(ValueError, match='composition_requests'):
        load(path, custom_design(), inputs={'composition_requests': []})

    # 用户在 composition_requests 提出要求：允许 custom；旧工作区残留的 inputs.design 不作门槛。
    custom_inputs = {'design': 'legacy-ignored', 'composition_requests': ['全片用深色科技风配色']}
    assert load(path, custom_design(), inputs=custom_inputs) == custom_design()
    assert load(path, preset_design('default'), inputs={'design': 'legacy-ignored'}) == preset_design('default')


@pytest.mark.parametrize('source', ['preset', 'custom'])
@pytest.mark.usefixtures('require_ffmpeg')
def test_phase_8_accepts_preset_by_default_and_gates_custom_on_user_requests(tmp_path: Path, source: str):
    complete_all(tmp_path)
    inputs = json.loads((tmp_path / 'inputs.json').read_text(encoding='utf-8'))
    inputs.pop('design', None)
    write_json(tmp_path / 'inputs.json', inputs)
    payload = preset_design() if source == 'preset' else custom_design()
    write_json(tmp_path / composition_design.COMPOSITION_DESIGN_PATH, payload)

    if source == 'custom':
        unrequested = parse_result(run_status(str(tmp_path)))
        assert unrequested['next_phase']['id'] == '8-composition'
        assert 'composition_requests' in unrequested['next_phase']['problems']['composition/design.json']
        inputs['composition_requests'] = ['全片使用深色科技风配色']
        write_json(tmp_path / 'inputs.json', inputs)

    result = parse_result(run_status(str(tmp_path)))

    assert result['next_phase'] is None, result
    assert '8-composition' in result['completed_phases']
