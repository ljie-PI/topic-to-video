#!/usr/bin/env python3
"""
Voice-cloned narration TTS with a local-first backend.

Backends (select via --backend or TTS_BACKEND env, default: qwen3tts):
  qwen3tts   Local Qwen3-TTS (Apache-2.0) voice clone — reference WAV + its
             transcript via Qwen3-TTS-12Hz-1.7B-Base. Runs on the local GPU.
  voxcpm     Local VoxCPM2 (Apache-2.0) ultimate cloning — reference WAV +
             its transcript. Runs on the local GPU. 48kHz output.
  dashscope  Aliyun DashScope CosyVoice (cloud fallback). Needs
             DASHSCOPE_API_KEY + COSYVOICE_VOICE_ID.

Usage:
  source .venv/bin/activate
  # local (default)
  export VOXCPM_REF_WAV="/path/to/my_voice.wav"        # reference timbre
  python3 voice-clone.py --input-file narration.txt --output-dir voice_clone
  # cloud fallback
  export TTS_BACKEND=dashscope
  export DASHSCOPE_API_KEY="sk-..."
  export COSYVOICE_VOICE_ID="cosyvoice-v3.5-plus-..."
  python3 voice-clone.py --input-file narration.txt --output-dir voice_clone

Optional env:
  TTS_BACKEND        qwen3tts (default) | voxcpm | dashscope
  VOXCPM_MODEL       VoxCPM model id or local dir (default: openbmb/VoxCPM2)
  VOXCPM_REF_WAV     reference audio for cloning (required for voxcpm/qwen3tts)
  VOXCPM_REF_TEXT    transcript of the reference audio. If unset, a sibling
                     "<ref>.txt" is used, else it is auto-generated once with
                     Qwen3-ASR and cached next to the reference WAV.
  QWEN3TTS_MODEL     Qwen3-TTS model id or local dir
                     (default: Qwen/Qwen3-TTS-12Hz-1.7B-Base)
  QWEN3TTS_LANGUAGE  Qwen3-TTS language hint (default: Chinese)
  QWEN3_ASR_MODEL    Qwen3-ASR model used for the one-time reference transcript
                     (default: Qwen/Qwen3-ASR-1.7B)

Output: {output_dir}/narration.mp3
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Reduce CUDA allocator fragmentation so long narrations don't OOM on smaller
# cards (e.g. 11GB). Must be set before torch initializes the CUDA allocator;
# setdefault leaves any user-provided value untouched.
os.environ.setdefault('PYTORCH_CUDA_ALLOC_CONF', 'expandable_segments:True')

DASHSCOPE_MODEL = "cosyvoice-v3.5-plus"
DEFAULT_VOXCPM_MODEL = "openbmb/VoxCPM2"
DEFAULT_QWEN3TTS_MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
DEFAULT_REF_ASR_MODEL = "Qwen/Qwen3-ASR-1.7B"

# Default playback speed per backend. VoxCPM / Qwen3-TTS speak at a natural ~1.0
# pace; 1.2 (applied via ffmpeg atempo) lands close to the brisker DashScope/
# CosyVoice narration pace while preserving pitch. CosyVoice keeps its own 1.4.
DEFAULT_VOXCPM_SPEECH_RATE = 1.2
DEFAULT_QWEN3TTS_SPEECH_RATE = 1.2
DEFAULT_DASHSCOPE_SPEECH_RATE = 1.4


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
    parser = JsonArgumentParser(description='Synthesize cloned-voice narration.')
    parser.add_argument(
        '--backend',
        choices=['voxcpm', 'qwen3tts', 'dashscope'],
        default=None,
        help='TTS backend. Defaults to TTS_BACKEND env or "qwen3tts".',
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
        help='VoxCPM reference audio for cloning. Defaults to VOXCPM_REF_WAV.',
    )
    parser.add_argument(
        '--reference-text',
        default=None,
        help='Transcript of the reference audio (inline string or path to a .txt). '
             'Defaults to VOXCPM_REF_TEXT, a sibling "<ref>.txt", or auto-ASR.',
    )
    parser.add_argument(
        '--speech-rate',
        type=float,
        default=None,
        help='Playback speed. dashscope: CosyVoice speech_rate (default 1.4). '
             'voxcpm: ffmpeg atempo factor applied post-synthesis (default 1.2).',
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


def resolve_reference_text(ref_wav: Path, cli_value: str | None) -> str:
    """Return the transcript of the reference audio for VoxCPM ultimate cloning.

    Resolution order:
      1. --reference-text / VOXCPM_REF_TEXT, treated as a file path if it looks
         path-like, otherwise as an inline string.
      2. A sibling "<ref>.txt" cached next to the reference WAV.
      3. Auto-transcribe the reference once with Qwen3-ASR and cache it.
    """
    raw = cli_value or os.environ.get('VOXCPM_REF_TEXT')
    if raw and raw.strip():
        candidate = Path(raw)
        looks_like_path = (
            os.sep in raw
            or (os.altsep and os.altsep in raw)
            or raw.strip().lower().endswith('.txt')
        )
        if candidate.is_file():
            text = candidate.read_text(encoding='utf-8').strip()
            if text:
                return text
            raise ValueError(f'reference transcript file is empty: {candidate}')
        if looks_like_path:
            # A path-looking value that does not resolve is almost certainly a
            # typo; failing loudly beats silently cloning from the literal path.
            raise FileNotFoundError(f'reference transcript file not found: {candidate}')
        return raw.strip()

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
        # Free the ASR model before VoxCPM loads — both are multi-GB and the
        # local GPU (e.g. 11GB) cannot hold them simultaneously.
        del model
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    if not text:
        raise RuntimeError('reference transcription returned empty text')
    return text


def write_mp3(wav, sample_rate: int, output_path: Path, atempo: float | None) -> None:
    """Write a float waveform to mp3 via ffmpeg, optionally re-timing speed."""
    import soundfile as sf

    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        tmp_wav = tmp.name
    try:
        sf.write(tmp_wav, wav, sample_rate)
        cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-i', tmp_wav]
        if atempo is not None and abs(atempo - 1.0) > 1e-3:
            cmd += ['-filter:a', f'atempo={atempo:.4f}']
        cmd += ['-c:a', 'libmp3lame', '-q:a', '2', str(output_path)]
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=300)
    finally:
        try:
            os.unlink(tmp_wav)
        except OSError:
            pass


def synth_voxcpm(text: str, output_path: Path, args: argparse.Namespace) -> None:
    import torch
    from voxcpm import VoxCPM

    ref_wav_value = args.reference_wav or os.environ.get('VOXCPM_REF_WAV')
    if not ref_wav_value:
        raise EnvironmentError(
            'VoxCPM reference audio not set. Pass --reference-wav or set VOXCPM_REF_WAV.'
        )
    ref_wav = Path(ref_wav_value).expanduser()
    if not ref_wav.is_file():
        raise FileNotFoundError(f'reference audio not found: {ref_wav}')

    ref_text = resolve_reference_text(ref_wav, args.reference_text)

    model_id = os.environ.get('VOXCPM_MODEL', DEFAULT_VOXCPM_MODEL)
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    log(f'loading VoxCPM model={model_id} device={device}')
    model = VoxCPM.from_pretrained(model_id, load_denoiser=False, optimize=False, device=device)

    log('synthesizing narration with VoxCPM ultimate cloning')
    wav = model.generate(
        text=text,
        prompt_wav_path=str(ref_wav),
        prompt_text=ref_text,
        reference_wav_path=str(ref_wav),
    )
    sample_rate = int(model.tts_model.sample_rate)
    atempo = args.speech_rate if args.speech_rate is not None else DEFAULT_VOXCPM_SPEECH_RATE
    write_mp3(wav, sample_rate, output_path, atempo)


def synth_qwen3tts(text: str, output_path: Path, args: argparse.Namespace) -> None:
    import gc

    import torch
    from qwen_tts import Qwen3TTSModel

    ref_wav_value = args.reference_wav or os.environ.get('VOXCPM_REF_WAV')
    if not ref_wav_value:
        raise EnvironmentError(
            'Qwen3-TTS reference audio not set. Pass --reference-wav or set VOXCPM_REF_WAV.'
        )
    ref_wav = Path(ref_wav_value).expanduser()
    if not ref_wav.is_file():
        raise FileNotFoundError(f'reference audio not found: {ref_wav}')

    ref_text = resolve_reference_text(ref_wav, args.reference_text)

    model_id = os.environ.get('QWEN3TTS_MODEL', DEFAULT_QWEN3TTS_MODEL)
    language = os.environ.get('QWEN3TTS_LANGUAGE', 'Chinese')
    use_cuda = torch.cuda.is_available()
    dtype = torch.float16 if use_cuda else torch.float32  # Turing: fp16, no flash-attn
    device = 'cuda:0' if use_cuda else 'cpu'

    log(f'loading Qwen3-TTS model={model_id} device={device} dtype={dtype}')
    model = Qwen3TTSModel.from_pretrained(model_id, device_map=device, dtype=dtype)

    # Pass the reference clip as a (waveform, sr) tuple loaded via soundfile so
    # audio I/O does not depend on an external SoX binary.
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

    atempo = args.speech_rate if args.speech_rate is not None else DEFAULT_QWEN3TTS_SPEECH_RATE
    write_mp3(wav, int(sr), output_path, atempo)


def synth_dashscope(text: str, output_path: Path, args: argparse.Namespace) -> None:
    from dashscope.audio.tts_v2 import SpeechSynthesizer
    import dashscope

    api_key = os.environ.get('DASHSCOPE_API_KEY')
    if not api_key:
        raise EnvironmentError('DASHSCOPE_API_KEY env var not set')
    voice = args.voice or os.environ.get('COSYVOICE_VOICE_ID')
    if not voice:
        raise EnvironmentError('CosyVoice voice id not set. Pass --voice or set COSYVOICE_VOICE_ID.')

    dashscope.api_key = api_key
    dashscope.base_websocket_api_url = 'wss://dashscope.aliyuncs.com/api-ws/v1/inference'

    speech_rate = args.speech_rate if args.speech_rate is not None else DEFAULT_DASHSCOPE_SPEECH_RATE
    log(f'synthesizing narration to {output_path} (CosyVoice, speech_rate={speech_rate})')
    synthesizer = SpeechSynthesizer(model=DASHSCOPE_MODEL, voice=voice, speech_rate=speech_rate)
    audio = synthesizer.call(text)
    log(
        'requestId='
        f'{synthesizer.get_last_request_id()}, '
        f'first_packet_delay={synthesizer.get_first_package_delay()}ms'
    )
    output_path.write_bytes(audio)


def main() -> int:
    try:
        args = parse_args()
        backend = args.backend or os.environ.get('TTS_BACKEND', 'qwen3tts')
        input_text = read_input_text(args.input_file)

        output_dir = Path(args.output_dir).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = (output_dir / 'narration.mp3').resolve()

        if backend == 'voxcpm':
            synth_voxcpm(input_text, output_path, args)
        elif backend == 'qwen3tts':
            synth_qwen3tts(input_text, output_path, args)
        elif backend == 'dashscope':
            synth_dashscope(input_text, output_path, args)
        else:
            raise ValueError(f'unknown TTS backend: {backend}')

        duration_s = detect_duration_seconds(output_path)
        log(f'wrote {output_path}')
        print_json(
            {
                'success': True,
                'backend': backend,
                'output_path': str(output_path),
                'duration_s': duration_s,
            }
        )
        return 0
    except SystemExit:
        raise
    except Exception as exc:
        log(f'error: {exc}')
        print_json({'success': False, 'error': str(exc)})
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
