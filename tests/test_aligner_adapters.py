"""Tests for the real aligners' transcript adapters, with the model libraries faked.

voice-clone.py's mlx and torch direct aligners and transcribe.py's qwen3 ASR
all turn an aligner's token list into the pipeline transcript schema through
``transcript_schema`` (no wrapper functions in between). The heavy third-party
libraries (torch, qwen_asr, mlx_audio) are replaced by stand-ins in
``sys.modules`` so the real script code runs without any model; everything
else is the script's own code.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / 'scripts'

TEXT = '你好。再见。'
# mlx's sentence grouper (text_align.group_sentences) matches a sentence to
# aligner tokens by length including '。', so its tests use newline-separated
# sentences, which it strips.
MLX_TEXT = '你好\n再见'


def token(text: str, start: float, end: float) -> SimpleNamespace:
    return SimpleNamespace(text=text, start_time=start, end_time=end)


ITEMS = [token('你', 0.0, 0.25), token('好', 0.25, 0.5), token('再', 0.75, 1.0), token('见', 1.0, 1.5)]

EXPECTED = [
    {
        'begin': 0,
        'end': 500,
        'text': '你好。',
        'words': [
            {'text': '你', 'begin': 0, 'end': 250},
            {'text': '好', 'begin': 250, 'end': 500},
        ],
    },
    {
        'begin': 750,
        'end': 1500,
        'text': '再见。',
        'words': [
            {'text': '再', 'begin': 750, 'end': 1000},
            {'text': '见', 'begin': 1000, 'end': 1500},
        ],
    },
]


def load_script(monkeypatch: pytest.MonkeyPatch, filename: str, module_name: str):
    """Import a hyphenated script as a module (its sibling imports resolve)."""
    monkeypatch.setenv('PYTORCH_CUDA_ALLOC_CONF', 'expandable_segments:True')  # keep os.environ clean
    monkeypatch.syspath_prepend(str(SCRIPTS_DIR))
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fake_torch() -> types.ModuleType:
    module = types.ModuleType('torch')
    module.float16 = 'float16'
    module.float32 = 'float32'
    module.cuda = SimpleNamespace(is_available=lambda: False, empty_cache=lambda: None)
    return module


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


# --- transcribe.py: qwen3 ASR ---------------------------------------------------


def test_qwen3_asr_groups_aligner_tokens_into_the_transcript_schema(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    class Qwen3ASRModel:
        @staticmethod
        def from_pretrained(*args, **kwargs):
            return Qwen3ASRModel()

        def transcribe(self, audio, language, return_time_stamps):
            return [SimpleNamespace(text=TEXT, time_stamps=SimpleNamespace(items=ITEMS))]

    qwen_asr = types.ModuleType('qwen_asr')
    qwen_asr.Qwen3ASRModel = Qwen3ASRModel
    monkeypatch.setitem(sys.modules, 'torch', fake_torch())
    monkeypatch.setitem(sys.modules, 'qwen_asr', qwen_asr)
    monkeypatch.setenv('ASR_ITN', '0')
    transcribe = load_script(monkeypatch, 'transcribe.py', 'transcribe_under_test')
    audio = tmp_path / 'narration.mp3'
    audio.write_bytes(b'')

    assert transcribe.Qwen3ASRBackend().transcribe(str(audio)) == EXPECTED


# --- voice-clone.py: torch Qwen3-ForcedAligner (qwen3tts) -----------------------


def install_fake_torch_aligner(monkeypatch: pytest.MonkeyPatch, items: list) -> None:
    class Qwen3ForcedAligner:
        @staticmethod
        def from_pretrained(*args, **kwargs):
            return Qwen3ForcedAligner()

        def align(self, audio, text, language):
            return [items]

    qwen_asr = types.ModuleType('qwen_asr')
    qwen_asr.Qwen3ForcedAligner = Qwen3ForcedAligner
    monkeypatch.setitem(sys.modules, 'torch', fake_torch())
    monkeypatch.setitem(sys.modules, 'qwen_asr', qwen_asr)


def qwen3tts_backend(voice_clone):
    return voice_clone.Qwen3TTSBackend(
        argparse.Namespace(transcript_output=None, speech_rate=None)
    )


def test_torch_aligner_writes_the_transcript_schema(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    install_fake_torch_aligner(monkeypatch, ITEMS)
    voice_clone = load_script(monkeypatch, 'voice-clone.py', 'voice_clone_under_test')
    out = tmp_path / 'transcript.json'

    qwen3tts_backend(voice_clone).emit_transcript(TEXT, tmp_path / 'narration.mp3', out)

    assert read_json(out) == EXPECTED


def test_torch_aligner_that_cannot_be_imported_raises_instead_of_returning_quietly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    monkeypatch.setitem(sys.modules, 'torch', fake_torch())
    monkeypatch.setitem(sys.modules, 'qwen_asr', None)  # makes `import qwen_asr` raise
    voice_clone = load_script(monkeypatch, 'voice-clone.py', 'voice_clone_under_test')
    out = tmp_path / 'transcript.json'

    with pytest.raises(RuntimeError, match='unavailable'):
        qwen3tts_backend(voice_clone).emit_transcript(TEXT, tmp_path / 'narration.mp3', out)
    assert not out.exists()


def test_torch_aligner_without_timestamps_raises_and_writes_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    install_fake_torch_aligner(monkeypatch, [])
    voice_clone = load_script(monkeypatch, 'voice-clone.py', 'voice_clone_under_test')
    out = tmp_path / 'transcript.json'

    with pytest.raises(ValueError, match='no timestamps'):
        qwen3tts_backend(voice_clone).emit_transcript(TEXT, tmp_path / 'narration.mp3', out)
    assert not out.exists()


# --- voice-clone.py: mlx-audio aligner ------------------------------------------


def install_fake_mlx_aligner(monkeypatch: pytest.MonkeyPatch, items: list) -> None:
    class Model:
        def generate(self, audio, text, language):
            return SimpleNamespace(items=items)

    utils = types.ModuleType('mlx_audio.stt.utils')
    utils.load_model = lambda model_path: Model()
    for name in ('mlx_audio', 'mlx_audio.stt'):
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
    monkeypatch.setitem(sys.modules, 'mlx_audio.stt.utils', utils)


def mlx_backend(voice_clone):
    return voice_clone.MLXBackend(argparse.Namespace(transcript_output=None, speech_rate=None))


def test_mlx_aligner_writes_the_transcript_schema(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    install_fake_mlx_aligner(monkeypatch, ITEMS)
    voice_clone = load_script(monkeypatch, 'voice-clone.py', 'voice_clone_under_test')
    out = tmp_path / 'transcript.json'

    mlx_backend(voice_clone).emit_transcript(MLX_TEXT, tmp_path / 'narration.mp3', out)

    expected = [{**sentence, 'text': text} for sentence, text in zip(EXPECTED, ['你好', '再见'])]
    assert read_json(out) == expected


def test_mlx_aligner_rescales_timestamps_when_the_mp3_was_retimed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    install_fake_mlx_aligner(monkeypatch, ITEMS)
    voice_clone = load_script(monkeypatch, 'voice-clone.py', 'voice_clone_under_test')
    backend = mlx_backend(voice_clone)
    backend._atempo = 2.0  # ffmpeg atempo doubled the speed after alignment
    out = tmp_path / 'transcript.json'

    backend.emit_transcript(MLX_TEXT, tmp_path / 'narration.mp3', out)

    transcript = read_json(out)
    assert [(s['begin'], s['end']) for s in transcript] == [(0, 250), (375, 750)]


def test_mlx_aligner_failure_raises_instead_of_returning_quietly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    install_fake_mlx_aligner(monkeypatch, [])
    voice_clone = load_script(monkeypatch, 'voice-clone.py', 'voice_clone_under_test')
    out = tmp_path / 'transcript.json'

    with pytest.raises(ValueError, match='no timestamps'):
        mlx_backend(voice_clone).emit_transcript(MLX_TEXT, tmp_path / 'narration.mp3', out)
    assert not out.exists()
