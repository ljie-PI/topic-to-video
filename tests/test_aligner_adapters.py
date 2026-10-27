"""Exercise the real aligner adapters through the public CLIs, without models.

The hyphenated voice-clone script and the transcribe CLI run in subprocesses.
Stand-in third-party packages on PYTHONPATH provide deterministic aligner tokens
and silent synthesis, while all repository production code remains real.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from cli_helpers import parse_stdout, run_cli as run_script

REPO_ROOT = Path(__file__).resolve().parent.parent
TRANSCRIBE = REPO_ROOT / 'scripts' / 'transcribe.py'
VOICE_CLONE = REPO_ROOT / 'scripts' / 'voice-clone.py'

TEXT = '你好。再见。'
# mlx's sentence grouper matches tokens by length including punctuation, so its
# CLI tests use newline-separated sentences, which it strips.
MLX_TEXT = '你好\n再见'

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

_ENV_BLACKLIST_PREFIXES = (
    'TTS_', 'ASR_', 'ALIGNER_', 'QWEN3', 'DASHSCOPE_', 'COSYVOICE_',
)
NO_ASR_ENV = {
    'ASR_DETECT_PLATFORM': 'linux',
    'ASR_DETECT_MACHINE': 'x86_64',
    'ASR_DETECT_CUDA': '0',
}


def run_cli(script: Path, *args: str, env: dict[str, str]) -> subprocess.CompletedProcess:
    return run_script(
        script, *args, env=env, blocked_prefixes=_ENV_BLACKLIST_PREFIXES
    )


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_package(root: Path, name: str, source: str = '') -> Path:
    package = root / name
    package.mkdir(parents=True, exist_ok=True)
    (package / '__init__.py').write_text(source, encoding='utf-8')
    return package


_ALIGNER_ITEMS = """
def items():
    if os.environ.get('FAKE_ALIGNER_ITEMS') == 'empty':
        return []
    return [
        SimpleNamespace(text='你', start_time=0.0, end_time=0.25),
        SimpleNamespace(text='好', start_time=0.25, end_time=0.5),
        SimpleNamespace(text='再', start_time=0.75, end_time=1.0),
        SimpleNamespace(text='见', start_time=1.0, end_time=1.5),
    ]
"""


@pytest.fixture
def fake_packages(tmp_path: Path) -> Path:
    root = tmp_path / 'fake_packages'
    write_package(root, 'torch', """
float16 = 'float16'
float32 = 'float32'
class cuda:
    @staticmethod
    def is_available():
        return False
    @staticmethod
    def empty_cache():
        pass
""")
    write_package(root, 'qwen_asr', """
import os
from types import SimpleNamespace
""" + _ALIGNER_ITEMS + """
class Qwen3ASRModel:
    @staticmethod
    def from_pretrained(*args, **kwargs):
        return Qwen3ASRModel()
    def transcribe(self, audio, language, return_time_stamps):
        return [SimpleNamespace(
            text='你好。再见。',
            time_stamps=SimpleNamespace(items=items()),
        )]

class Qwen3ForcedAligner:
    @staticmethod
    def from_pretrained(*args, **kwargs):
        return Qwen3ForcedAligner()
    def align(self, audio, text, language):
        return [items()]
""")
    write_package(root, 'qwen_tts', """
class Qwen3TTSModel:
    @staticmethod
    def from_pretrained(*args, **kwargs):
        return Qwen3TTSModel()
    def generate_voice_clone(self, **kwargs):
        return [[0.0]], 24000
""")
    write_package(root, 'soundfile', """
import wave

def read(path):
    return [0.0], 24000

def write(path, wav, sample_rate):
    with wave.open(str(path), 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(b'\\0\\0' * sample_rate)
""")
    write_package(root, 'mlx_audio')
    write_package(root / 'mlx_audio', 'tts')
    write_package(root / 'mlx_audio', 'stt')
    tts_utils = root / 'mlx_audio' / 'tts' / 'utils.py'
    tts_utils.write_text('def load_model(path):\n    return object()\n', encoding='utf-8')
    (root / 'mlx_audio' / 'tts' / 'generate.py').write_text("""
import wave
from pathlib import Path

def generate_audio(output_path, file_prefix, **kwargs):
    path = Path(output_path) / (file_prefix + '.wav')
    with wave.open(str(path), 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(24000)
        output.writeframes(b'\\0\\0' * 24000)
""", encoding='utf-8')
    (root / 'mlx_audio' / 'stt' / 'utils.py').write_text("""
import os
from types import SimpleNamespace
""" + _ALIGNER_ITEMS + """
class Model:
    def generate(self, audio, text, language):
        return SimpleNamespace(items=items())

def load_model(path):
    return Model()
""", encoding='utf-8')
    return root


def package_env(fake_packages: Path, **extra: str) -> dict[str, str]:
    return {'PYTHONPATH': str(fake_packages), **NO_ASR_ENV, **extra}


def run_voice_clone(
    tmp_path: Path,
    fake_packages: Path,
    *,
    backend: str,
    text: str = TEXT,
    extra: tuple[str, ...] = (),
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    narration = tmp_path / 'narration.txt'
    narration.write_text(text, encoding='utf-8')
    reference = tmp_path / 'reference.wav'
    reference.write_bytes(b'fake reference; fake soundfile does not read it')
    return run_cli(
        VOICE_CLONE,
        '--backend', backend,
        '--input-file', str(narration),
        '--output-dir', str(tmp_path / 'out'),
        '--transcript-output', str(tmp_path / 'transcript.json'),
        '--emit-transcript',
        '--reference-wav', str(reference),
        '--reference-text', 'reference text',
        *extra,
        env=package_env(fake_packages, **(env or {})),
    )


def assert_direct_align_failure(proc: subprocess.CompletedProcess, message: str) -> None:
    assert proc.returncode == 1, proc.stderr
    result = parse_stdout(proc)
    direct, asr = result['transcript_attempts']
    assert direct['method'] == 'direct_align'
    assert message in direct['error']
    assert asr['method'] == 'asr'


# --- transcribe.py: qwen3 ASR ---------------------------------------------------


def test_qwen3_asr_cli_groups_aligner_tokens_into_the_transcript_schema(
    tmp_path: Path, fake_packages: Path
):
    audio = tmp_path / 'narration.mp3'
    audio.write_bytes(b'')
    output = tmp_path / 'transcript.json'

    proc = run_cli(
        TRANSCRIBE,
        str(audio), str(output), '--backend', 'qwen3',
        env=package_env(fake_packages, ASR_ITN='0'),
    )

    assert proc.returncode == 0, proc.stderr
    assert parse_stdout(proc)['success'] is True
    assert read_json(output) == EXPECTED


# --- voice-clone.py: torch Qwen3-ForcedAligner (qwen3tts) -----------------------


@pytest.mark.usefixtures('require_ffmpeg')
def test_torch_aligner_cli_writes_the_transcript_schema(tmp_path: Path, fake_packages: Path):
    proc = run_voice_clone(tmp_path, fake_packages, backend='qwen3tts')

    assert proc.returncode == 0, proc.stderr
    assert parse_stdout(proc)['transcript_method'] == 'direct_align'
    assert read_json(tmp_path / 'transcript.json') == EXPECTED


@pytest.mark.usefixtures('require_ffmpeg')
def test_torch_aligner_cli_reports_unavailable_aligner_and_writes_nothing(
    tmp_path: Path, fake_packages: Path
):
    (fake_packages / 'qwen_asr' / '__init__.py').write_text(
        "raise ImportError('qwen_asr deliberately unavailable')\n", encoding='utf-8'
    )

    proc = run_voice_clone(tmp_path, fake_packages, backend='qwen3tts')

    assert_direct_align_failure(proc, 'unavailable')
    assert not (tmp_path / 'transcript.json').exists()


@pytest.mark.usefixtures('require_ffmpeg')
def test_torch_aligner_cli_without_timestamps_falls_back_and_writes_nothing(
    tmp_path: Path, fake_packages: Path
):
    proc = run_voice_clone(
        tmp_path, fake_packages, backend='qwen3tts', env={'FAKE_ALIGNER_ITEMS': 'empty'}
    )

    assert_direct_align_failure(proc, 'no timestamps')
    assert not (tmp_path / 'transcript.json').exists()


# --- voice-clone.py: mlx-audio aligner ------------------------------------------


@pytest.mark.usefixtures('require_ffmpeg')
def test_mlx_aligner_cli_writes_the_transcript_schema(tmp_path: Path, fake_packages: Path):
    proc = run_voice_clone(tmp_path, fake_packages, backend='mlx', text=MLX_TEXT)

    assert proc.returncode == 0, proc.stderr
    assert parse_stdout(proc)['transcript_method'] == 'direct_align'
    expected = [
        {**sentence, 'text': text}
        for sentence, text in zip(EXPECTED, ['你好', '再见'])
    ]
    assert read_json(tmp_path / 'transcript.json') == expected


@pytest.mark.usefixtures('require_ffmpeg')
def test_mlx_aligner_cli_rescales_timestamps_when_the_mp3_was_retimed(
    tmp_path: Path, fake_packages: Path
):
    proc = run_voice_clone(
        tmp_path, fake_packages, backend='mlx', text=MLX_TEXT,
        extra=('--speech-rate', '2.0'),
    )

    assert proc.returncode == 0, proc.stderr
    transcript = read_json(tmp_path / 'transcript.json')
    assert [(s['begin'], s['end']) for s in transcript] == [(0, 250), (375, 750)]


@pytest.mark.usefixtures('require_ffmpeg')
def test_mlx_aligner_cli_failure_falls_back_and_writes_nothing(
    tmp_path: Path, fake_packages: Path
):
    proc = run_voice_clone(
        tmp_path, fake_packages, backend='mlx', text=MLX_TEXT,
        env={'FAKE_ALIGNER_ITEMS': 'empty'},
    )

    assert_direct_align_failure(proc, 'no sentences or no words')
    assert not (tmp_path / 'transcript.json').exists()


@pytest.mark.usefixtures('require_ffmpeg')
def test_mlx_aligner_cli_with_words_but_no_sentences_falls_back(
    tmp_path: Path, fake_packages: Path
):
    # Pure punctuation produces words from the fake model but no grouped
    # sentences. This must be an alignment failure, not a one-sentence fallback.
    proc = run_voice_clone(tmp_path, fake_packages, backend='mlx', text='...')

    assert_direct_align_failure(proc, 'no sentences or no words')
    assert not (tmp_path / 'transcript.json').exists()
