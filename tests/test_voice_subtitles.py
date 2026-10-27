"""CLI integration tests for the single-command Phase 7 workflow (issue #106).

All synthesis uses the fake TTS backend from #105. Workspaces start with a
real script/lexicon and make-narration.py, never with real model dependencies.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from cli_helpers import parse_stdout, run_cli

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / 'scripts' / 'voice-subtitles.py'
MAKE_NARRATION = REPO_ROOT / 'scripts' / 'make-narration.py'
PIPELINE_STATUS = REPO_ROOT / 'scripts' / 'pipeline-status.py'

_ENV_BLACKLIST_PREFIXES = ('TTS_', 'ASR_', 'ALIGN', 'QWEN3', 'DASHSCOPE_', 'COSYVOICE_')
SCRIPT_TEXT = '甲' * 22 + '\n\n' + '乙' * 23 + '\n'
SCENE_PLAN = [
    {
        'scene_id': 'scene_1',
        'paragraphs': [1, 2],
        'intent': '测试完整配音字幕流程',
        'facts': [],
        'material_candidates': [],
        'cues': ['这个 cue 不在旁白里'],
    }
]


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')


def run_voice_subtitles(
    ws: Path, *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess:
    return run_cli(
        SCRIPT,
        str(ws),
        '--backend',
        'fake',
        *args,
        env=env or {},
        blocked_prefixes=_ENV_BLACKLIST_PREFIXES,
        timeout=120,
    )


def run_pipeline_status(ws: Path, *args: str) -> dict:
    proc = run_cli(PIPELINE_STATUS, str(ws), *args, env={})
    assert proc.returncode == 0, proc.stderr
    return parse_stdout(proc)


def make_workspace(tmp_path: Path, *, scene_plan: bool = True) -> Path:
    ws = tmp_path / 'workspace'
    write_json(
        ws / 'inputs.json',
        {
            'source': 'https://example.com/article',
            'input_mode': 'standard',
            'duration': 0.1,
            'language': 'zh',
            'orientation': 'landscape',
            'template': None,
            'design': 'default',
            'layout': 'stage',
            'coding_agent': 'claude-code',
            'fetch_materials': False,
            'qa_level': 'standard',
        },
    )
    (ws / 'script.txt').write_text(SCRIPT_TEXT, encoding='utf-8')
    write_json(ws / 'tts-lexicon.json', {'OpenHuman': 'Open Human'})
    if scene_plan:
        write_json(ws / 'scene-plan.json', SCENE_PLAN)
    proc = run_cli(
        MAKE_NARRATION,
        '--script', str(ws / 'script.txt'),
        '--lexicon', str(ws / 'tts-lexicon.json'),
        '--output-dir', str(ws),
        env={},
    )
    assert proc.returncode == 0, proc.stderr
    return ws


def approve_current_phase(ws: Path, gate: str) -> None:
    run_pipeline_status(ws, '--approve', gate)


@pytest.mark.usefixtures('require_ffmpeg')
def test_full_command_writes_all_products_and_pipeline_completes_phase_7(tmp_path: Path):
    ws = make_workspace(tmp_path)
    (ws / 'research-brief.md').write_text(
        '# research brief\n\n## Key facts (verified)\n- fact [source]\n',
        encoding='utf-8',
    )
    approve_current_phase(ws, 'research-brief')
    approve_current_phase(ws, 'script')

    proc = run_voice_subtitles(ws)

    assert proc.returncode == 0, proc.stderr
    result = parse_stdout(proc)
    assert result['success'] is True
    assert result['backend'] == 'fake'
    assert result['transcript_method'] == 'direct_align'
    products = {
        'audio': ws / 'voice_clone' / 'narration.mp3',
        'transcript': ws / 'transcribe' / 'transcript.json',
        'subtitle_units': ws / 'transcribe' / 'subtitle-units.json',
        'timeline': ws / 'transcribe' / 'timeline.json',
    }
    assert result['products'] == {
        name: str(path.resolve()) for name, path in products.items()
    }
    assert all(path.stat().st_size > 0 for path in products.values())
    timeline = json.loads(products['timeline'].read_text(encoding='utf-8'))
    assert timeline['scenes'][0]['scene_id'] == 'scene_1'
    assert any('cue not found' in warning for warning in result['warnings'])

    status = run_pipeline_status(ws)
    phases = {phase['id']: phase['status'] for phase in status['phases']}
    assert phases['7-voice-subtitles'] == 'completed'
    assert status['next_phase']['id'] == '8-composition'


@pytest.mark.usefixtures('require_ffmpeg')
def test_missing_scene_plan_produces_timeline_without_scenes(tmp_path: Path):
    ws = make_workspace(tmp_path, scene_plan=False)

    proc = run_voice_subtitles(ws)

    assert proc.returncode == 0, proc.stderr
    assert parse_stdout(proc)['success'] is True
    timeline = json.loads((ws / 'transcribe' / 'timeline.json').read_text(encoding='utf-8'))
    assert 'scenes' not in timeline
    assert 'cues' not in timeline


@pytest.mark.usefixtures('require_ffmpeg')
def test_nonexistent_layout_is_an_align_failure_with_child_json(tmp_path: Path):
    ws = make_workspace(tmp_path)
    inputs = json.loads((ws / 'inputs.json').read_text(encoding='utf-8'))
    inputs['layout'] = 'does-not-exist'
    write_json(ws / 'inputs.json', inputs)

    proc = run_voice_subtitles(ws)

    assert proc.returncode == 1
    result = parse_stdout(proc)
    assert result['success'] is False
    assert result['failed_step'] == 'align'
    assert result['child']['success'] is False
    assert 'does-not-exist.json' in result['child']['error']


def test_empty_required_input_fails_before_tts(tmp_path: Path):
    ws = make_workspace(tmp_path)
    (ws / 'narration.txt').write_text('', encoding='utf-8')

    proc = run_voice_subtitles(ws)

    assert proc.returncode == 1
    result = parse_stdout(proc)
    assert result['success'] is False
    assert result['failed_step'] == 'inputs'
    assert 'narration.txt' in result['error']
    assert not (ws / 'voice_clone' / 'narration.mp3').exists()


@pytest.mark.usefixtures('require_ffmpeg')
def test_tts_failure_propagates_child_error_json(tmp_path: Path):
    ws = make_workspace(tmp_path)

    proc = run_voice_subtitles(
        ws,
        env={
            'TTS_FAKE_ALIGN_FAIL': '1',
            'ASR_DETECT_PLATFORM': 'linux',
            'ASR_DETECT_MACHINE': 'x86_64',
            'ASR_DETECT_CUDA': '0',
        },
    )

    assert proc.returncode == 1
    result = parse_stdout(proc)
    assert result['success'] is False
    assert result['failed_step'] == 'tts'
    assert result['child']['success'] is False
    assert result['child']['transcript_attempts'][0]['method'] == 'direct_align'


@pytest.mark.usefixtures('require_ffmpeg')
def test_align_only_reuses_existing_audio_and_transcript(tmp_path: Path):
    ws = make_workspace(tmp_path)
    first = run_voice_subtitles(ws)
    assert first.returncode == 0, first.stderr
    audio = ws / 'voice_clone' / 'narration.mp3'
    transcript = ws / 'transcribe' / 'transcript.json'
    original_audio = audio.read_bytes()
    original_transcript = transcript.read_bytes()

    proc = run_voice_subtitles(ws, '--align-only')

    assert proc.returncode == 0, proc.stderr
    result = parse_stdout(proc)
    assert result['success'] is True
    assert result['warnings']
    assert audio.read_bytes() == original_audio
    assert transcript.read_bytes() == original_transcript
