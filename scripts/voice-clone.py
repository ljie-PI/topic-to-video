#!/usr/bin/env python3
"""
Voice-cloned narration TTS with environment-selected backends.

Backends (select via --backend or TTS_BACKEND env, default: auto):
  auto       Pick by environment: Apple Silicon (darwin/arm64) with mlx-audio
             -> mlx; CUDA GPU -> qwen3tts; DASHSCOPE_API_KEY -> dashscope;
             otherwise exit 1 with a JSON error listing what is missing.
  mlx        mlx-audio Qwen3-TTS voice clone + Qwen3-ForcedAligner direct
             alignment of the narration text (NO ASR step). Emits
             narration.mp3 AND transcript.json (pipeline schema, ms).
  qwen3tts   Local Qwen3-TTS (Apache-2.0) voice clone — reference WAV + its
             transcript via Qwen3-TTS-12Hz-1.7B-Base. Runs on the local GPU.
             With --emit-transcript it additionally aligns narration text to
             the audio with the torch Qwen3-ForcedAligner (when importable)
             and writes transcript.json; if the aligner is unavailable the
             transcript is simply absent (fall back to transcribe.py).
  dashscope  Aliyun DashScope CosyVoice (cloud fallback). Needs
             DASHSCOPE_API_KEY + COSYVOICE_VOICE_ID.

Usage:
  source .venv/bin/activate
  # auto (default) — probe the decision without loading any model:
  python3 voice-clone.py --resolve-backend
  # local (auto-selected)
  export TTS_REF_WAV="/path/to/my_voice.wav"           # reference timbre
  python3 voice-clone.py --input-file narration.txt --output-dir voice_clone
  # cloud fallback
  export TTS_BACKEND=dashscope
  export DASHSCOPE_API_KEY="sk-..."
  export COSYVOICE_VOICE_ID="cosyvoice-v3.5-plus-..."
  python3 voice-clone.py --input-file narration.txt --output-dir voice_clone

Optional env:
  TTS_BACKEND        auto (default) | mlx | qwen3tts | dashscope
  TTS_REF_WAV        reference audio for cloning (required for mlx/qwen3tts;
                     legacy alias: VOXCPM_REF_WAV)
  TTS_REF_TEXT       transcript of the reference audio. Optional for mlx;
                     for qwen3tts a sibling "<ref>.txt" is used, else it is
                     auto-generated once with Qwen3-ASR and cached next to
                     the reference WAV. (legacy alias: VOXCPM_REF_TEXT)
  QWEN3TTS_MODEL     Qwen3-TTS model id or local dir
                     (default: Qwen/Qwen3-TTS-12Hz-1.7B-Base)
  QWEN3TTS_LANGUAGE  Qwen3-TTS language hint (default: Chinese)
  QWEN3_ASR_MODEL    Qwen3-ASR model used for the one-time reference transcript
                     (default: Qwen/Qwen3-ASR-1.7B)
  QWEN3_ALIGNER_MODEL  torch aligner for --emit-transcript
                     (default: Qwen/Qwen3-ForcedAligner-0.6B)
  TTS_MODEL_MLX      mlx-audio TTS model: HF id or local dir
                     (default: mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16)
  ALIGNER_MODEL_MLX  mlx-audio aligner model: HF id or local dir
                     (default: mlx-community/Qwen3-ForcedAligner-0.6B-8bit)
  TTS_LANGUAGE_MLX   mlx TTS language code (default: auto)
  ALIGNER_LANGUAGE_MLX  mlx aligner language (default: Chinese)

Testing seam (documented; also used by the test-suite): the hardware/OS
probes behind auto/--resolve-backend read these overrides when set:
  TTS_DETECT_PLATFORM   e.g. darwin | linux   (default: sys.platform)
  TTS_DETECT_MACHINE    e.g. arm64 | x86_64   (default: platform.machine())
  TTS_DETECT_CUDA       1 | 0                 (default: torch.cuda.is_available())
  TTS_DETECT_MLX_AUDIO  1 | 0                 (default: importlib find_spec)

Outputs: {output_dir}/narration.mp3, plus {output_dir}/transcript.json
(--transcript-output to redirect) for the mlx backend and for qwen3tts with
--emit-transcript when the aligner is available.
"""
from __future__ import annotations

import abc
import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # sibling scripts

# Reduce CUDA allocator fragmentation so long narrations don't OOM on smaller
# cards (e.g. 11GB). Must be set before torch initializes the CUDA allocator;
# setdefault leaves any user-provided value untouched.
os.environ.setdefault('PYTORCH_CUDA_ALLOC_CONF', 'expandable_segments:True')

DASHSCOPE_MODEL = "cosyvoice-v3.5-plus"
DEFAULT_QWEN3TTS_MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
DEFAULT_REF_ASR_MODEL = "Qwen/Qwen3-ASR-1.7B"
DEFAULT_QWEN3_ALIGNER_MODEL = "Qwen/Qwen3-ForcedAligner-0.6B"
# mlx-audio models: plain HF ids (mlx-audio downloads them) or local dirs.
DEFAULT_TTS_MODEL_MLX = "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16"
DEFAULT_ALIGNER_MODEL_MLX = "mlx-community/Qwen3-ForcedAligner-0.6B-8bit"

# Default playback speed per backend (applied via ffmpeg atempo, pitch-kept).
# Qwen3-TTS with a fast reference voice reads naturally at 1.0; CosyVoice keeps
# its own 1.4.
DEFAULT_QWEN3TTS_SPEECH_RATE = 1.0
DEFAULT_DASHSCOPE_SPEECH_RATE = 1.4


# --- environment probes (auto backend) -----------------------------------------
#
# Every probe reads a TTS_DETECT_* override first so the auto decision is
# testable without the hardware (documented in the module docstring).


def detect_platform() -> str:
    return os.environ.get('TTS_DETECT_PLATFORM') or sys.platform


def detect_machine() -> str:
    return os.environ.get('TTS_DETECT_MACHINE') or platform.machine()


def detect_cuda() -> bool:
    override = os.environ.get('TTS_DETECT_CUDA')
    if override is not None:
        return override == '1'
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:  # noqa: BLE001 - no torch / broken torch => no CUDA
        return False


def detect_mlx_audio() -> bool:
    override = os.environ.get('TTS_DETECT_MLX_AUDIO')
    if override is not None:
        return override == '1'
    import importlib.util

    return importlib.util.find_spec('mlx_audio') is not None


def environment_probes() -> dict[str, object]:
    return {
        'platform': detect_platform(),
        'machine': detect_machine(),
        'mlx_audio': detect_mlx_audio(),
        'cuda': detect_cuda(),
        'dashscope_key': bool(os.environ.get('DASHSCOPE_API_KEY')),
    }


class BackendUnavailableError(Exception):
    """Auto resolution found no usable backend; carries the missing list."""

    def __init__(self, missing: list[str], probes: dict[str, object] | None = None) -> None:
        self.missing = missing
        self.probes = probes or {}
        super().__init__('no usable TTS backend: ' + '; '.join(missing))


class UnknownBackendError(Exception):
    pass


def resolve_backend_name(cli_backend: str | None) -> tuple[str, str, dict[str, object]]:
    """Resolve the effective backend. Returns (name, source, probes).

    source is 'cli' (--backend), 'env' (TTS_BACKEND) or 'auto'. Auto order:
    Apple Silicon with mlx-audio -> mlx; CUDA -> qwen3tts; DASHSCOPE_API_KEY
    -> dashscope; otherwise raise BackendUnavailableError. Raises
    UnknownBackendError for values outside BACKENDS/'auto'.
    """
    explicit = cli_backend or os.environ.get('TTS_BACKEND')
    source = 'cli' if cli_backend else ('env' if os.environ.get('TTS_BACKEND') else 'auto')
    if explicit and explicit != 'auto':
        if explicit not in BACKENDS:
            raise UnknownBackendError(f'unknown TTS backend: {explicit}')
        return explicit, source, environment_probes()

    probes = environment_probes()
    missing: list[str] = []
    if probes['platform'] == 'darwin' and probes['machine'] == 'arm64':
        if probes['mlx_audio']:
            return 'mlx', 'auto', probes
        missing.append('mlx-audio package on Apple Silicon (pip install mlx-audio; backend mlx)')
    if probes['cuda']:
        return 'qwen3tts', 'auto', probes
    missing.append('CUDA-capable GPU with torch (backend qwen3tts)')
    if probes['dashscope_key']:
        return 'dashscope', 'auto', probes
    missing.append('DASHSCOPE_API_KEY (backend dashscope)')
    raise BackendUnavailableError(missing, probes)


def reference_wav_env() -> str | None:
    """Reference WAV path from TTS_REF_WAV (legacy alias VOXCPM_REF_WAV)."""
    return os.environ.get('TTS_REF_WAV') or os.environ.get('VOXCPM_REF_WAV')


def reference_text_env() -> str | None:
    """Reference transcript from TTS_REF_TEXT (legacy alias VOXCPM_REF_TEXT)."""
    return os.environ.get('TTS_REF_TEXT') or os.environ.get('VOXCPM_REF_TEXT')


def print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def log(message: str) -> None:
    print(f'[voice-clone] {message}', file=sys.stderr)


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        log(f'bad arguments: {message}')
        print_json({'success': False, 'error': message})
        raise SystemExit(2)


def parse_args() -> argparse.Namespace:
    parser = JsonArgumentParser(
        description='Synthesize cloned-voice narration.',
        epilog=(
            'key env vars: TTS_BACKEND (default auto), TTS_REF_WAV / TTS_REF_TEXT, '
            'QWEN3TTS_MODEL, QWEN3_ALIGNER_MODEL, TTS_MODEL_MLX '
            f'(default {DEFAULT_TTS_MODEL_MLX}), ALIGNER_MODEL_MLX '
            f'(default {DEFAULT_ALIGNER_MODEL_MLX}), DASHSCOPE_API_KEY, '
            'COSYVOICE_VOICE_ID. Probe overrides for --resolve-backend: '
            'TTS_DETECT_PLATFORM / TTS_DETECT_MACHINE / TTS_DETECT_CUDA / '
            'TTS_DETECT_MLX_AUDIO. Full docs: module docstring.'
        ),
    )
    parser.add_argument(
        '--backend',
        choices=['auto', 'mlx', 'qwen3tts', 'dashscope'],
        default=None,
        help='TTS backend. Defaults to TTS_BACKEND env or "auto" (Apple '
             'Silicon + mlx-audio -> mlx; CUDA -> qwen3tts; DASHSCOPE_API_KEY '
             '-> dashscope).',
    )
    parser.add_argument(
        '--resolve-backend',
        action='store_true',
        help='Print the backend decision as one JSON document and exit '
             '(probes only — no model is loaded).',
    )
    parser.add_argument(
        '--emit-transcript',
        action='store_true',
        help='qwen3tts only: after synthesis, align the narration text to the '
             'audio with the torch Qwen3-ForcedAligner and write '
             'transcript.json (skips the ASR step). If the aligner is not '
             'importable, the transcript is skipped with a warning. Always '
             'on for the mlx backend.',
    )
    parser.add_argument(
        '--transcript-output',
        default=None,
        help='Where to write transcript.json (default: <output-dir>/transcript.json).',
    )
    parser.add_argument(
        '--input-file',
        '--text-file',
        dest='input_file',
        default=None,
        help='Narration text file. Defaults to ./narration.txt when present; otherwise reads stdin.',
    )
    parser.add_argument(
        '--voice',
        default=None,
        help='DashScope CosyVoice voice id. Defaults to COSYVOICE_VOICE_ID.',
    )
    parser.add_argument(
        '--reference-wav',
        default=None,
        help='Reference audio for cloning (mlx / qwen3tts). Defaults to '
             'TTS_REF_WAV (legacy alias VOXCPM_REF_WAV).',
    )
    parser.add_argument(
        '--reference-text',
        default=None,
        help='Transcript of the reference audio (inline string or path to a .txt). '
             'Defaults to TTS_REF_TEXT (legacy alias VOXCPM_REF_TEXT), a sibling '
             '"<ref>.txt", or (qwen3tts only) auto-ASR. Optional for mlx.',
    )
    parser.add_argument(
        '--speech-rate',
        type=float,
        default=None,
        help='Playback speed. dashscope: CosyVoice speech_rate (default 1.4). '
             'mlx / qwen3tts: ffmpeg atempo factor post-synthesis (default 1.0).',
    )
    parser.add_argument(
        '--output-dir',
        default='.',
        help='Directory for narration.mp3 output (default: current directory)',
    )
    return parser.parse_args()


def read_input_text(input_file: str | None) -> str:
    path = Path(input_file) if input_file else Path('narration.txt')
    if path.is_file():
        text = path.read_text(encoding='utf-8')
    elif input_file:
        raise FileNotFoundError(f'input file not found: {path}')
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        raise ValueError('No narration text provided. Pass --input-file or create narration.txt.')
    text = text.strip()
    if not text:
        raise ValueError('Narration text is empty')
    return text


def detect_duration_seconds(audio_path: Path) -> float:
    result = subprocess.run(
        [
            'ffprobe',
            '-v',
            'error',
            '-show_entries',
            'format=duration',
            '-of',
            'default=noprint_wrappers=1:nokey=1',
            str(audio_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    duration_text = result.stdout.strip()
    if not duration_text:
        raise ValueError('ffprobe returned an empty duration for narration audio')
    duration_s = float(duration_text)
    if duration_s <= 0:
        raise ValueError(f'Invalid narration duration: {duration_text}')
    return round(duration_s, 3)


def _reference_text_from_raw(raw: str) -> str:
    """Interpret a --reference-text / TTS_REF_TEXT value as path or inline text."""
    stripped = raw.strip()
    candidate = Path(stripped).expanduser()
    if candidate.is_file():
        text = candidate.read_text(encoding='utf-8').strip()
        if text:
            return text
        raise ValueError(f'reference transcript file is empty: {candidate}')
    # Treat as a path only when it really looks like one: a .txt suffix, or
    # a path separator with no internal whitespace. A real inline transcript
    # usually contains spaces (and may contain a "/" as in "AI/人工智能"),
    # so it must not be misread as a missing file.
    looks_like_path = stripped.lower().endswith('.txt') or (
        not any(ch.isspace() for ch in stripped)
        and (os.sep in stripped or bool(os.altsep and os.altsep in stripped))
    )
    if looks_like_path:
        # A path-looking value that does not resolve is almost certainly a
        # typo; failing loudly beats silently cloning from the literal path.
        raise FileNotFoundError(f'reference transcript file not found: {candidate}')
    return stripped


def resolve_reference_text(ref_wav: Path, cli_value: str | None) -> str:
    """Return the transcript of the reference audio for voice cloning.

    Resolution order:
      1. --reference-text / TTS_REF_TEXT, treated as a file path if it looks
         path-like, otherwise as an inline string.
      2. A sibling "<ref>.txt" cached next to the reference WAV.
      3. Auto-transcribe the reference once with Qwen3-ASR and cache it.
    """
    raw = cli_value or reference_text_env()
    if raw and raw.strip():
        return _reference_text_from_raw(raw)

    sidecar = ref_wav.with_suffix('.txt')
    if sidecar.is_file():
        text = sidecar.read_text(encoding='utf-8').strip()
        if text:
            log(f'using cached reference transcript: {sidecar}')
            return text

    log('reference transcript not found; transcribing reference once with Qwen3-ASR')
    text = transcribe_reference_plain(ref_wav)
    sidecar.write_text(text + '\n', encoding='utf-8')
    log(f'cached reference transcript to {sidecar}')
    return text


def resolve_reference_text_optional(ref_wav: Path, cli_value: str | None) -> str | None:
    """mlx variant: same resolution minus the torch auto-ASR fallback (the mlx
    Qwen3-TTS Base clones well without a reference transcript)."""
    raw = cli_value or reference_text_env()
    if raw and raw.strip():
        return _reference_text_from_raw(raw)
    sidecar = ref_wav.with_suffix('.txt')
    if sidecar.is_file():
        text = sidecar.read_text(encoding='utf-8').strip()
        if text:
            log(f'using cached reference transcript: {sidecar}')
            return text
    return None


def transcribe_reference_plain(ref_wav: Path) -> str:
    """Plain-text (no timestamps) transcription of the reference clip."""
    import gc

    import torch
    from qwen_asr import Qwen3ASRModel

    model_id = os.environ.get('QWEN3_ASR_MODEL', DEFAULT_REF_ASR_MODEL)
    dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
    model = Qwen3ASRModel.from_pretrained(
        model_id,
        dtype=dtype,
        device_map=device,
        max_new_tokens=512,
    )
    try:
        results = model.transcribe(audio=str(ref_wav), language=None)
        text = (results[0].text or '').strip()
    finally:
        # Free the ASR model before the TTS model loads — both are multi-GB and
        # the local GPU (e.g. 11GB) cannot hold them simultaneously.
        del model
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    if not text:
        raise RuntimeError('reference transcription returned empty text')
    return text


def _atempo_chain(rate: float | None) -> str | None:
    """Build an ffmpeg atempo filter (or chain) for any positive speed.

    A single ``atempo`` only supports 0.5–2.0, so out-of-range rates are
    decomposed into a chain of in-range factors (e.g. 2.5 -> atempo=2.0,atempo=1.25).
    Returns None when no re-timing is needed.
    """
    if rate is None or abs(rate - 1.0) <= 1e-3:
        return None
    if rate <= 0:
        raise ValueError(f'--speech-rate must be positive, got {rate}')
    factors: list[float] = []
    remaining = rate
    while remaining > 2.0:
        factors.append(2.0)
        remaining /= 2.0
    while remaining < 0.5:
        factors.append(0.5)
        remaining /= 0.5
    factors.append(remaining)
    return ','.join(f'atempo={f:.4f}' for f in factors)


def convert_to_mp3(src_path: Path, output_path: Path, atempo: float | None) -> None:
    """Convert an existing audio file to mp3 via ffmpeg, optionally re-timing."""
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-i', str(src_path)]
    atempo_filter = _atempo_chain(atempo)
    if atempo_filter:
        cmd += ['-filter:a', atempo_filter]
    cmd += ['-c:a', 'libmp3lame', '-q:a', '2', str(output_path)]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=300)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or '').strip() or str(exc)
        raise RuntimeError(f'ffmpeg failed: {detail}') from exc


def write_mp3(wav, sample_rate: int, output_path: Path, atempo: float | None) -> None:
    """Write a float waveform to mp3 via ffmpeg, optionally re-timing speed."""
    import soundfile as sf

    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        tmp_wav = tmp.name
    try:
        sf.write(tmp_wav, wav, sample_rate)
        convert_to_mp3(Path(tmp_wav), output_path, atempo)
    finally:
        try:
            os.unlink(tmp_wav)
        except OSError:
            pass


class TTSBackend(abc.ABC):
    """Common interface: synthesize narration text into an mp3 file."""

    name: str

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args

    def transcript_path(self, output_path: Path) -> Path:
        """Where this run writes transcript.json (when it writes one)."""
        raw = self.args.transcript_output
        return Path(raw).expanduser() if raw else output_path.parent / 'transcript.json'

    @abc.abstractmethod
    def synthesize(self, text: str, output_path: Path) -> None:
        raise NotImplementedError


def write_transcript(path: Path, sentences: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sentences, ensure_ascii=False, indent=2), encoding='utf-8')
    log(f'wrote transcript: {path} ({len(sentences)} sentences)')


def scale_alignment_times(alignment: dict, factor: float) -> dict:
    """Scale every start/end (seconds) in an align_text result by ``factor`` —
    used when ffmpeg atempo re-times the delivered mp3 after alignment."""
    for word in alignment.get('words') or []:
        word['start'] = round(word['start'] * factor, 3)
        word['end'] = round(word['end'] * factor, 3)
    for sentence in alignment.get('sentences') or []:
        sentence['start'] = round(sentence['start'] * factor, 3)
        sentence['end'] = round(sentence['end'] * factor, 3)
    return alignment


def emit_transcript_via_torch_aligner(text: str, audio_path: Path, out_path: Path) -> bool:
    """Align narration text to the audio with the torch Qwen3-ForcedAligner
    and write the transcript schema (sentence list, ms) to ``out_path``.

    Returns True when the transcript was written. When the aligner cannot be
    imported, logs a warning and returns False — the phase then falls back to
    transcribe.py (ASR) for transcript.json.
    """
    try:
        import torch
        from qwen_asr import Qwen3ForcedAligner
    except Exception as exc:  # noqa: BLE001 - any import failure => no aligner
        log(
            f'torch Qwen3-ForcedAligner unavailable ({exc}); transcript.json '
            'not written — fall back to transcribe.py'
        )
        return False
    import gc

    from transcribe import segment_into_sentences

    model_id = os.environ.get('QWEN3_ALIGNER_MODEL', DEFAULT_QWEN3_ALIGNER_MODEL)
    language = os.environ.get('QWEN3TTS_LANGUAGE', 'Chinese')
    use_cuda = torch.cuda.is_available()
    dtype = torch.float16 if use_cuda else torch.float32
    device = 'cuda:0' if use_cuda else 'cpu'
    log(f'loading Qwen3-ForcedAligner model={model_id} device={device} dtype={dtype}')
    aligner = Qwen3ForcedAligner.from_pretrained(model_id, dtype=dtype, device_map=device)
    try:
        results = aligner.align(audio=str(audio_path), text=text, language=language)
    finally:
        del aligner
        gc.collect()
        if use_cuda:
            torch.cuda.empty_cache()
    items = list(results[0]) if results else []
    sentences = segment_into_sentences(text, items)
    if not sentences:
        log('warning: aligner returned no timestamps; transcript.json not written')
        return False
    write_transcript(out_path, sentences)
    return True


class MLXBackend(TTSBackend):
    """mlx-audio Qwen3-TTS voice clone + Qwen3-ForcedAligner direct alignment.

    Apple Silicon path: no ASR — the narration text is aligned straight onto
    the synthesized audio, so transcript.json matches narration.txt verbatim.
    """

    name = 'mlx'

    def synthesize(self, text: str, output_path: Path) -> None:
        from tts_qwen import synthesize as mlx_synthesize  # lazy: pulls mlx-audio
        from text_align import align_text, transcript_from_alignment

        ref_wav_value = self.args.reference_wav or reference_wav_env()
        if not ref_wav_value:
            raise EnvironmentError(
                'mlx backend needs reference audio. Pass --reference-wav or set TTS_REF_WAV.'
            )
        ref_wav = Path(ref_wav_value).expanduser()
        if not ref_wav.is_file():
            raise FileNotFoundError(f'reference audio not found: {ref_wav}')
        ref_text = resolve_reference_text_optional(ref_wav, self.args.reference_text)

        tts_model = os.environ.get('TTS_MODEL_MLX', DEFAULT_TTS_MODEL_MLX)
        aligner_model = os.environ.get('ALIGNER_MODEL_MLX', DEFAULT_ALIGNER_MODEL_MLX)
        tts_language = os.environ.get('TTS_LANGUAGE_MLX', 'auto')
        align_language = os.environ.get('ALIGNER_LANGUAGE_MLX', 'Chinese')
        atempo = self.args.speech_rate if self.args.speech_rate is not None else DEFAULT_QWEN3TTS_SPEECH_RATE

        wav_path = output_path.with_suffix('.wav')
        log(f'synthesizing narration with mlx-audio Qwen3-TTS (model={tts_model})')
        mlx_synthesize(
            text,
            wav_path,
            voice_path=ref_wav,
            model_path=tts_model,
            language=tts_language,
            ref_text=ref_text,
        )
        try:
            try:
                log(f'aligning narration text directly (model={aligner_model}, no ASR)')
                alignment = align_text(wav_path, text, model_path=aligner_model, language=align_language)
                if atempo and abs(atempo - 1.0) > 1e-3:
                    # The mp3 is re-timed after alignment; scale timestamps to match.
                    alignment = scale_alignment_times(alignment, 1.0 / atempo)
                write_transcript(
                    self.transcript_path(output_path), transcript_from_alignment(alignment)
                )
            except Exception as exc:  # noqa: BLE001 - audio still usable via ASR
                log(
                    f'warning: mlx forced alignment failed ({exc}); transcript.json '
                    'not written — run transcribe.py for the transcript'
                )
            convert_to_mp3(wav_path, output_path, atempo)
        finally:
            try:
                wav_path.unlink()
            except OSError:
                pass


class Qwen3TTSBackend(TTSBackend):
    """Local Qwen3-TTS voice clone (reference WAV + its transcript)."""

    name = 'qwen3tts'

    def synthesize(self, text: str, output_path: Path) -> None:
        import gc

        import torch
        from qwen_tts import Qwen3TTSModel

        ref_wav_value = self.args.reference_wav or reference_wav_env()
        if not ref_wav_value:
            raise EnvironmentError(
                'Qwen3-TTS reference audio not set. Pass --reference-wav or set TTS_REF_WAV.'
            )
        ref_wav = Path(ref_wav_value).expanduser()
        if not ref_wav.is_file():
            raise FileNotFoundError(f'reference audio not found: {ref_wav}')

        ref_text = resolve_reference_text(ref_wav, self.args.reference_text)

        model_id = os.environ.get('QWEN3TTS_MODEL', DEFAULT_QWEN3TTS_MODEL)
        language = os.environ.get('QWEN3TTS_LANGUAGE', 'Chinese')
        use_cuda = torch.cuda.is_available()
        dtype = torch.float16 if use_cuda else torch.float32  # Turing: fp16, no flash-attn
        device = 'cuda:0' if use_cuda else 'cpu'

        log(f'loading Qwen3-TTS model={model_id} device={device} dtype={dtype}')
        model = Qwen3TTSModel.from_pretrained(model_id, device_map=device, dtype=dtype)

        # Pass the reference clip as a (waveform, sr) tuple loaded via soundfile
        # so audio I/O does not depend on an external SoX binary.
        import soundfile as sf
        ref_audio, ref_sr = sf.read(str(ref_wav))
        if getattr(ref_audio, 'ndim', 1) > 1:
            ref_audio = ref_audio.mean(axis=1)  # downmix to mono

        log('synthesizing narration with Qwen3-TTS voice clone')
        wavs, sr = model.generate_voice_clone(
            text=text,
            language=language,
            ref_audio=(ref_audio, ref_sr),
            ref_text=ref_text,
        )
        wav = wavs[0]
        del model
        gc.collect()
        if use_cuda:
            torch.cuda.empty_cache()

        atempo = self.args.speech_rate if self.args.speech_rate is not None else DEFAULT_QWEN3TTS_SPEECH_RATE
        write_mp3(wav, int(sr), output_path, atempo)


class CosyVoiceBackend(TTSBackend):
    """Cloud DashScope CosyVoice synthesis (fallback)."""

    name = 'dashscope'

    def synthesize(self, text: str, output_path: Path) -> None:
        from dashscope.audio.tts_v2 import SpeechSynthesizer
        import dashscope

        api_key = os.environ.get('DASHSCOPE_API_KEY')
        if not api_key:
            raise EnvironmentError('DASHSCOPE_API_KEY env var not set')
        voice = self.args.voice or os.environ.get('COSYVOICE_VOICE_ID')
        if not voice:
            raise EnvironmentError('CosyVoice voice id not set. Pass --voice or set COSYVOICE_VOICE_ID.')

        dashscope.api_key = api_key
        dashscope.base_websocket_api_url = 'wss://dashscope.aliyuncs.com/api-ws/v1/inference'

        speech_rate = self.args.speech_rate if self.args.speech_rate is not None else DEFAULT_DASHSCOPE_SPEECH_RATE
        log(f'synthesizing narration to {output_path} (CosyVoice, speech_rate={speech_rate})')
        synthesizer = SpeechSynthesizer(model=DASHSCOPE_MODEL, voice=voice, speech_rate=speech_rate)
        audio = synthesizer.call(text)
        log(
            'requestId='
            f'{synthesizer.get_last_request_id()}, '
            f'first_packet_delay={synthesizer.get_first_package_delay()}ms'
        )
        if not isinstance(audio, (bytes, bytearray)):
            raise RuntimeError(
                f'CosyVoice returned no audio (got {type(audio).__name__}); '
                'check DASHSCOPE_API_KEY / COSYVOICE_VOICE_ID and account quota.'
            )
        output_path.write_bytes(audio)


BACKENDS: dict[str, type[TTSBackend]] = {
    cls.name: cls for cls in (MLXBackend, Qwen3TTSBackend, CosyVoiceBackend)
}


def resolve_backend_cli(args: argparse.Namespace) -> int:
    """--resolve-backend: print the backend decision (probes only), no models."""
    try:
        backend_name, source, probes = resolve_backend_name(args.backend)
    except UnknownBackendError as exc:
        log(f'error: {exc}')
        print_json({'success': False, 'error': str(exc)})
        return 2
    except BackendUnavailableError as exc:
        log(f'error: {exc}')
        print_json(
            {'success': False, 'error': str(exc), 'missing': exc.missing, 'probes': exc.probes}
        )
        return 1
    print_json(
        {
            'success': True,
            'backend': backend_name,
            'backend_source': source,
            'probes': probes,
        }
    )
    return 0


def main() -> int:
    try:
        args = parse_args()
        if args.resolve_backend:
            return resolve_backend_cli(args)

        try:
            backend_name, _source, _probes = resolve_backend_name(args.backend)
        except UnknownBackendError as exc:
            log(f'error: {exc}')
            print_json({'success': False, 'error': str(exc)})
            return 2
        except BackendUnavailableError as exc:
            log(f'error: {exc}')
            print_json(
                {'success': False, 'error': str(exc), 'missing': exc.missing, 'probes': exc.probes}
            )
            return 1
        backend_cls = BACKENDS[backend_name]

        input_text = read_input_text(args.input_file)

        output_dir = Path(args.output_dir).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = (output_dir / 'narration.mp3').resolve()

        backend = backend_cls(args)
        backend.synthesize(input_text, output_path)

        # qwen3tts (CUDA): --emit-transcript adds the direct-alignment
        # transcript when the torch aligner is importable; mlx writes its
        # transcript inside synthesize().
        transcript_path = backend.transcript_path(output_path)
        if backend_name == 'qwen3tts' and args.emit_transcript:
            emit_transcript_via_torch_aligner(input_text, output_path, transcript_path)

        duration_s = detect_duration_seconds(output_path)
        log(f'wrote {output_path}')
        payload: dict[str, object] = {
            'success': True,
            'backend': backend_name,
            'output_path': str(output_path),
            'duration_s': duration_s,
        }
        if transcript_path.is_file():
            payload['transcript_path'] = str(transcript_path.resolve())
        print_json(payload)
        return 0
    except SystemExit:
        raise
    except Exception as exc:
        log(f'error: {exc}')
        print_json({'success': False, 'error': str(exc)})
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
