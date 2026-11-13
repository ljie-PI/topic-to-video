"""Public composition/design.json contract and its real consumers."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

import composition_design
import video_contract
from test_check_composition import (
    CAPTION_BAR,
    CLEAN_SCENE,
    PRESENTER_LAYOUT,
    scene,
    write_composition,
)
from test_pipeline_status import complete_all, parse_result, run_cli as run_status

REPO_ROOT = Path(__file__).resolve().parent.parent
CHECK_COMPOSITION = REPO_ROOT / 'scripts' / 'check-composition.py'


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')


def preset_design(name: str = 'github') -> dict:
    preset = json.loads(
        (REPO_ROOT / 'modules' / 'designs' / name / f'{name}.json').read_text(encoding='utf-8')
    )
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


def load(path: Path, payload: dict) -> dict:
    write_json(path, payload)
    return composition_design.load_composition_design(path, skill_root=REPO_ROOT)


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


def test_custom_preset_must_be_null(tmp_path: Path):
    payload = custom_design()
    payload['preset'] = 'github'

    with pytest.raises(ValueError, match='preset must be null'):
        load(tmp_path / 'composition' / 'design.json', payload)


def test_custom_ui_floor_must_be_at_least_22px(tmp_path: Path):
    payload = custom_design()
    payload['min_font_px']['ui'] = 21

    with pytest.raises(ValueError, match='ui must be at least 22px'):
        load(tmp_path / 'composition' / 'design.json', payload)

    payload['min_font_px']['ui'] = 22
    assert load(tmp_path / 'composition' / 'design.json', payload) == payload


@pytest.mark.parametrize('source', ['preset', 'custom'])
@pytest.mark.usefixtures('require_ffmpeg')
def test_phase_8_accepts_both_design_sources(tmp_path: Path, source: str):
    complete_all(tmp_path)
    payload = preset_design() if source == 'preset' else custom_design()
    write_json(tmp_path / composition_design.COMPOSITION_DESIGN_PATH, payload)

    result = parse_result(run_status(str(tmp_path)))

    assert result['next_phase'] is None, result
    assert '8-composition' in result['completed_phases']


@pytest.mark.usefixtures('require_chrome')
def test_real_check_composition_reads_custom_design_font_floors(tmp_path: Path):
    comp = write_composition(tmp_path, [scene('s1', 0.0, 10.0, CLEAN_SCENE + CAPTION_BAR)])
    design_path = tmp_path / 'composition' / 'design.json'
    write_json(design_path, custom_design())

    proc = subprocess.run(
        [
            sys.executable,
            str(CHECK_COMPOSITION),
            str(comp),
            '--layout',
            str(PRESENTER_LAYOUT),
            '--design',
            str(design_path),
        ],
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0, proc.stderr + proc.stdout
    result = json.loads(proc.stdout)
    assert (result['min_font_size'], result['min_ui_font_size']) == (31, 23)
    small_text = [
        finding for finding in result['findings']
        if finding['check'] == 'font_size_below_min' and 'panel' in finding['issue']
    ]
    assert small_text and '31px' in small_text[0]['issue']
