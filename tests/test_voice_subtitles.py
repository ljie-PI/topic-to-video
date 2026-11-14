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
RESEARCH_BRIEF = (
    '# research brief\n\n'
    '## Key facts (verified)\n- fact [source]\n\n'
    '## Quotes (verbatim if possible)\n- "quote" — Person, [source]\n\n'
    '## Numbers / dates\n- 1, unit, [source]\n\n'
    '## Source URLs (for Phase 4 harvest)\n- https://example.com/article — official site\n'
)
SCENE_PLAN = [
    {
        'scene_id': 'scene_1',
        'paragraphs': [1, 2],
        'intent': '测试完整配音字幕流程',
        'content_plan': '按段落顺序讲完两个例子。',
        'material_candidates': [],
        'cues': ['这个 cue 不在旁白里'],
    }
]

# Fake backend with a failing aligner and no reachable ASR backend: the run
# produces audio but cannot produce a transcript.
_NO_TRANSCRIPT_ENV = {
    'TTS_FAKE_ALIGN_FAIL': '1',
    'ASR_DETECT_PLATFORM': 'linux',
    'ASR_DETECT_MACHINE': 'x86_64',
    'ASR_DETECT_CUDA': '0',
}


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
            'design': 'default',
            'coding_agent': 'pi-coding-agent',
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


@pytest.mark.usefixtures('require_ffmpeg')
def test_full_command_writes_all_products_ignores_legacy_layout_and_completes_phase_7(tmp_path: Path):
    ws = make_workspace(tmp_path)
    # layout 是 Phase 8 的决定：即使 inputs.json 带有无效 legacy layout，Phase 7 也不读它。
    inputs = json.loads((ws / 'inputs.json').read_text(encoding='utf-8'))
    inputs['layout'] = 'does-not-exist'
    write_json(ws / 'inputs.json', inputs)
    (ws / 'research-brief.md').write_text(RESEARCH_BRIEF, encoding='utf-8')
    proc = run_voice_subtitles(ws)

    assert proc.returncode == 0, proc.stderr
    result = parse_stdout(proc)
    assert result['success'] is True
    assert result['backend'] == 'fake'
    assert result['transcript_method'] == 'direct_align'
    products = {
        'audio': ws / 'voice_clone' / 'narration.mp3',
        'transcript': ws / 'transcribe' / 'transcript.json',
        'timeline': ws / 'transcribe' / 'timeline.json',
    }
    assert result['products'] == {
        name: str(path.resolve()) for name, path in products.items()
    }
    assert all(path.stat().st_size > 0 for path in products.values())
    # 最终字幕属于 Phase 8：layout 定下来之后再生成，Phase 7 不预先按容量切。
    assert not (ws / 'transcribe' / 'subtitle-units.json').exists()
    timeline = json.loads(products['timeline'].read_text(encoding='utf-8'))
    assert timeline['scenes'][0]['scene_id'] == 'scene_1'
    # 语义节拍已删除：时间轴只有段落、场景与 cue。
    assert 'beats' not in timeline
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

    proc = run_voice_subtitles(ws, env=_NO_TRANSCRIPT_ENV)

    assert proc.returncode == 1
    result = parse_stdout(proc)
    assert result['success'] is False
    assert result['failed_step'] == 'tts'
    assert result['child']['success'] is False
    assert result['child']['transcript_attempts'][0]['method'] == 'direct_align'
    # The narration itself succeeded; only the transcript is missing.
    audio = ws / 'voice_clone' / 'narration.mp3'
    assert audio.is_file() and audio.stat().st_size > 0


@pytest.mark.usefixtures('require_ffmpeg')
def test_external_transcript_align_only_resumes_validates_words_and_rerun_drops_it(tmp_path: Path):
    ws = make_workspace(tmp_path)
    first = run_voice_subtitles(ws)
    assert first.returncode == 0, first.stderr
    transcript = ws / 'transcribe' / 'transcript.json'
    external = transcript.read_bytes()

    # A full regeneration deletes whatever sits at the transcript path.
    transcript.write_bytes(external)
    dropped = run_voice_subtitles(ws, env=_NO_TRANSCRIPT_ENV)
    assert dropped.returncode == 1
    assert not transcript.exists()

    # --align-only rejects a transcript without word timestamps, and succeeds with valid external words.
    write_json(transcript, [{'begin': 0, 'end': 1000, 'text': '甲', 'words': []}])
    bad_align = run_voice_subtitles(ws, '--align-only')
    assert bad_align.returncode == 1
    assert parse_stdout(bad_align)['failed_step'] == 'align'

    transcript.write_bytes(external)
    audio = ws / 'voice_clone' / 'narration.mp3'
    audio_before = audio.read_bytes()
    recovered = run_voice_subtitles(ws, '--align-only', env=_NO_TRANSCRIPT_ENV)

    assert recovered.returncode == 0, recovered.stderr
    assert parse_stdout(recovered)['success'] is True
    assert audio.read_bytes() == audio_before
    assert transcript.read_bytes() == external
    assert (ws / 'transcribe' / 'timeline.json').is_file()


@pytest.mark.usefixtures('require_ffmpeg')
def test_crlf_producer_voice_and_composition_subtitles_chain(tmp_path: Path):
    ws = make_workspace(tmp_path)
    (ws / 'script.txt').write_bytes(SCRIPT_TEXT.replace('\n', '\r\n').encode('utf-8'))
    (ws / 'research-brief.md').write_text(RESEARCH_BRIEF, encoding='utf-8')
    made = run_cli(
        MAKE_NARRATION, '--script', str(ws / 'script.txt'),
        '--lexicon', str(ws / 'tts-lexicon.json'), '--output-dir', str(ws), env={},
    )
    assert made.returncode == 0, made.stderr
    assert parse_stdout(made)['success'] is True

    voiced = run_voice_subtitles(ws)
    assert voiced.returncode == 0, voiced.stderr + voiced.stdout
    assert parse_stdout(voiced)['success'] is True
    assert '7-voice-subtitles' in run_pipeline_status(ws)['completed_phases']

    prepared = run_cli(REPO_ROOT / 'scripts' / 'prepare-handoff.py', str(ws), 'composition', env={})
    assert prepared.returncode == 0, prepared.stderr
    assert parse_stdout(prepared)['success'] is True

    timeline_before = (ws / 'transcribe/timeline.json').read_bytes()
    subtitles = run_cli(
        REPO_ROOT / 'scripts' / 'align-narration.py',
        '--mode', 'subtitles',
        '--script', str(ws / 'script.txt'),
        '--narration', str(ws / 'narration.txt'),
        '--offsets', str(ws / 'narration-offsets.json'),
        '--transcript', str(ws / 'transcribe/transcript.json'),
        '--layout', str(ws / 'modules/layouts/landscape.json'),
        '--units-output', str(ws / 'composition/assets/subtitle-units.json'),
        env={},
    )
    assert subtitles.returncode == 0, subtitles.stderr + subtitles.stdout
    assert parse_stdout(subtitles)['success'] is True
    assert (ws / 'transcribe/timeline.json').read_bytes() == timeline_before
    assert json.loads((ws / 'composition/assets/subtitle-units.json').read_text(encoding='utf-8'))['units']
