#!/usr/bin/env python3
"""
带音色克隆的旁白 TTS，后端由环境选择。

后端（用 --backend 或 TTS_BACKEND 环境变量选择，默认 auto）：
  auto       按环境挑选：Apple Silicon（darwin/arm64）且有 mlx-audio -> mlx；
             有 CUDA GPU -> qwen3tts；有 DASHSCOPE_API_KEY -> dashscope；
             否则以一条 JSON 错误退出 1，并列出缺少什么。
  mlx        mlx-audio Qwen3-TTS 音色克隆 + Qwen3-ForcedAligner 对旁白文本的
             直接对齐。每次运行都产出 narration.mp3 和 transcript.json
             （流水线 schema，毫秒）。
  qwen3tts   本地 Qwen3-TTS（Apache-2.0）音色克隆 —— 参考 WAV 及其转写文本，
             经 Qwen3-TTS-12Hz-1.7B-Base 完成。跑在本地 GPU 上。带
             --emit-transcript 时，会先用 torch 的 Qwen3-ForcedAligner 尝试把
             旁白文本对齐到音频。
  dashscope  阿里云 DashScope CosyVoice（云端兜底）。需要 DASHSCOPE_API_KEY +
             COSYVOICE_VOICE_ID。没有直接对齐器。
  fake       TEST ONLY（测试用）：静音 mp3 加一个均匀时间的对齐器，不加载模型。
             只能显式选择（--backend fake / TTS_BACKEND=fake）；auto 永远不会
             选它。见下面的 TTS_FAKE_ALIGN_FAIL。

转写契约：当传入 --emit-transcript，或后端总是产出转写（mlx、fake）时，一次运行
就需要转写。转写路径上已有的任何文件都会在合成之前被删掉（它属于更早的那份音频）。
后端自己的直接对齐器先跑（transcript_method "direct_align"）；当它什么都没写时
（对齐器不可用、对齐失败，或该后端没有对齐器），本脚本以子进程方式运行
`transcribe.py <mp3> <transcript>`（transcript_method "asr"；ASR_BACKEND 及环境
中其他设置都会生效）。两者都失败时退出码为 1，mp3 被保留，JSON 错误会在
"transcript_attempts" 下列出每一次尝试。因此一次运行要么留下一份新的转写，要么
失败。

用法：
  source .venv/bin/activate
  # auto（默认）—— 只探测决定，不加载任何模型：
  python3 voice-clone.py --resolve-backend
  # 本地（由 auto 选中）
  export TTS_REF_WAV="/path/to/my_voice.wav"           # 参考音色
  python3 voice-clone.py --input-file narration.txt --output-dir voice_clone
  # 云端兜底
  export TTS_BACKEND=dashscope
  export DASHSCOPE_API_KEY="sk-..."
  export COSYVOICE_VOICE_ID="cosyvoice-v3.5-plus-..."
  python3 voice-clone.py --input-file narration.txt --output-dir voice_clone

可选环境变量：
  TTS_BACKEND        auto（默认）| mlx | qwen3tts | dashscope | fake（仅测试）
  TTS_REF_WAV        用于克隆的参考音频（mlx/qwen3tts 必需；旧别名：
                     VOXCPM_REF_WAV）
  TTS_REF_TEXT       参考音频的转写文本。对 mlx 可选；对 qwen3tts 会先用同目录的
                     "<ref>.txt"，否则用 Qwen3-ASR 自动生成一次并缓存在参考 WAV
                     旁边。（旧别名：VOXCPM_REF_TEXT）
  QWEN3TTS_MODEL     Qwen3-TTS 模型 id 或本地目录
                     （默认：Qwen/Qwen3-TTS-12Hz-1.7B-Base）
  QWEN3TTS_LANGUAGE  Qwen3-TTS 语言提示（默认：Chinese）
  QWEN3_ASR_MODEL    用于生成一次性参考转写的 Qwen3-ASR 模型
                     （默认：Qwen/Qwen3-ASR-1.7B）
  QWEN3_ALIGNER_MODEL  为 --emit-transcript 服务的 torch 对齐器
                     （默认：Qwen/Qwen3-ForcedAligner-0.6B）
  TTS_MODEL_MLX      mlx-audio TTS 模型：HF id 或本地目录
                     （默认：mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16）
  ALIGNER_MODEL_MLX  mlx-audio 对齐器模型：HF id 或本地目录
                     （默认：mlx-community/Qwen3-ForcedAligner-0.6B-8bit）
  TTS_LANGUAGE_MLX   mlx TTS 语言代码（默认：auto）
  ALIGNER_LANGUAGE_MLX  mlx 对齐器语言（默认：Chinese）
  TTS_FAKE_ALIGN_FAIL  置 1 让 fake 后端的对齐器失败（在测试中触发 ASR 兜底）

测试接缝（有文档记录；测试套件也用它）：auto / --resolve-backend 背后的硬件 /
系统探测在被设置时读取这些覆盖值：
  TTS_DETECT_PLATFORM   例如 darwin | linux   （默认：sys.platform）
  TTS_DETECT_MACHINE    例如 arm64 | x86_64   （默认：platform.machine()）
  TTS_DETECT_CUDA       1 | 0                 （默认：torch.cuda.is_available()）
  TTS_DETECT_MLX_AUDIO  1 | 0                 （默认：importlib find_spec）

产出：{output_dir}/narration.mp3，以及在该次运行需要转写时（见上面的转写契约）
{output_dir}/transcript.json（可用 --transcript-output 改路径）；成功 JSON 随后
带有 transcript_path 与 transcript_method。
"""
from __future__ import annotations

import abc
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # 同级脚本

import backend_select as bs
import cli
import fake_backend
import media
from backend_select import BackendUnavailableError, UnknownBackendError
from transcript_schema import (
    transcript_from_mlx_alignment,
    transcript_from_torch_alignment,
)

# 减小 CUDA 分配器的碎片，让长旁白不会在显存更小的卡（例如 11GB）上 OOM。
# 必须在 torch 初始化 CUDA 分配器之前设置；
# setdefault 不会覆盖用户已提供的值。
os.environ.setdefault('PYTORCH_CUDA_ALLOC_CONF', 'expandable_segments:True')

TOOL_NAME = 'voice-clone'
DASHSCOPE_MODEL = "cosyvoice-v3.5-plus"
DEFAULT_QWEN3TTS_MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
DEFAULT_REF_ASR_MODEL = "Qwen/Qwen3-ASR-1.7B"
DEFAULT_QWEN3_ALIGNER_MODEL = "Qwen/Qwen3-ForcedAligner-0.6B"
# mlx-audio 模型：纯 HF id（由 mlx-audio 下载）或本地目录。
DEFAULT_TTS_MODEL_MLX = "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16"
DEFAULT_ALIGNER_MODEL_MLX = "mlx-community/Qwen3-ForcedAligner-0.6B-8bit"

# 各后端的默认播放速度（通过 ffmpeg atempo 施加，保持音高）。
# 配快速参考音色时 Qwen3-TTS 以 1.0 朗读最自然；CosyVoice 保持它自己的 1.4。
DEFAULT_QWEN3TTS_SPEECH_RATE = 1.0
DEFAULT_DASHSCOPE_SPEECH_RATE = 1.4


# --- 后端选择（auto） --------------------------------------------------------
#
# 各项探测、CLI > 环境变量 > auto 的解析，以及 --resolve-backend 的输出，都在
# backend_select.py 中（与 transcribe.py 共用）。本脚本只提供 TTS 后端注册表与
# TTS 的 auto 顺序；有文档记录的探测覆盖值是 TTS_DETECT_PLATFORM /
# TTS_DETECT_MACHINE / TTS_DETECT_CUDA / TTS_DETECT_MLX_AUDIO。

PROBE_PREFIX = 'TTS_DETECT'


def _auto_backend(probes: dict[str, object]) -> tuple[str, dict[str, object]]:
    """TTS 的 auto 顺序：Apple Silicon + mlx-audio -> mlx；CUDA -> qwen3tts；
    DASHSCOPE_API_KEY -> dashscope；否则抛 BackendUnavailableError。"""
    missing: list[str] = []
    if probes['platform'] == 'darwin' and probes['machine'] == 'arm64':
        if probes['mlx_audio']:
            return 'mlx', probes
        missing.append('mlx-audio package on Apple Silicon (pip install mlx-audio; backend mlx)')
    if probes['cuda']:
        return 'qwen3tts', probes
    missing.append('CUDA-capable GPU with torch (backend qwen3tts)')
    if probes['dashscope_key']:
        return 'dashscope', probes
    missing.append('DASHSCOPE_API_KEY (backend dashscope)')
    raise BackendUnavailableError(
        'no usable TTS backend: ' + '; '.join(missing), missing, probes
    )


def resolve_backend_name(cli_backend: str | None) -> tuple[str, str, dict[str, object]]:
    """解析出实际生效的 TTS 后端。返回 (name, source, probes)。

    source 是 'cli'（--backend）、'env'（TTS_BACKEND）或 'auto'。共用的契约见
    backend_select.resolve_backend_name，TTS 的 auto 顺序见 _auto_backend。
    对 BACKENDS/'auto' 之外的取值抛 UnknownBackendError。
    """
    return bs.resolve_backend_name(
        cli_backend,
        env_var='TTS_BACKEND',
        probe_prefix=PROBE_PREFIX,
        backends=BACKENDS,
        auto_resolve=_auto_backend,
        label='TTS',
        include_mlx=True,
    )


def reference_wav_env() -> str | None:
    """TTS_REF_WAV 给出的参考 WAV 路径（旧别名 VOXCPM_REF_WAV）。"""
    return os.environ.get('TTS_REF_WAV') or os.environ.get('VOXCPM_REF_WAV')


def default_reference_wav() -> Path | None:
    """随 skill 分发的参考音色：<repo>/resources/my_voice.wav（存在时）。"""
    candidate = Path(__file__).resolve().parent.parent / 'resources' / 'my_voice.wav'
    return candidate if candidate.is_file() else None


def resolve_reference_audio(cli_value: str | None) -> Path:
    """优先级：CLI --reference-wav > TTS_REF_WAV > 分发的 resources/my_voice.wav。"""
    value = cli_value or reference_wav_env()
    if value:
        return Path(value).expanduser()
    bundled = default_reference_wav()
    if bundled is not None:
        return bundled
    raise EnvironmentError(
        'reference audio needed. Pass --reference-wav, set TTS_REF_WAV, '
        'or provide resources/my_voice.wav.'
    )


def reference_text_env() -> str | None:
    """TTS_REF_TEXT 给出的参考转写文本（旧别名 VOXCPM_REF_TEXT）。"""
    return os.environ.get('TTS_REF_TEXT') or os.environ.get('VOXCPM_REF_TEXT')


print_json = cli.print_json
log = cli.make_logger(TOOL_NAME)


def parse_args() -> argparse.Namespace:
    parser = cli.JsonArgumentParser(
        TOOL_NAME,
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            'key env vars: TTS_BACKEND (default auto), TTS_REF_WAV / TTS_REF_TEXT, '
            'QWEN3TTS_MODEL, QWEN3_ALIGNER_MODEL, TTS_MODEL_MLX '
            f'(default {DEFAULT_TTS_MODEL_MLX}), ALIGNER_MODEL_MLX '
            f'(default {DEFAULT_ALIGNER_MODEL_MLX}), DASHSCOPE_API_KEY, '
            'COSYVOICE_VOICE_ID. Probe overrides for --resolve-backend: '
            'TTS_DETECT_PLATFORM / TTS_DETECT_MACHINE / TTS_DETECT_CUDA / '
            'TTS_DETECT_MLX_AUDIO.'
        ),
    )
    parser.add_argument(
        '--backend',
        choices=['auto', *BACKENDS],
        default=None,
        help='TTS backend. Defaults to TTS_BACKEND env or "auto" (Apple '
             'Silicon + mlx-audio -> mlx; CUDA -> qwen3tts; DASHSCOPE_API_KEY '
             '-> dashscope). "fake" is test-only (测试用): no model, never '
             'chosen by auto.',
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
        help='Require a fresh transcript.json from this run: the backend\'s '
             'direct aligner first, transcribe.py (ASR) when that writes '
             'nothing; exit 1 (with transcript_attempts) if neither does. '
             'Always on for backends that always emit one (mlx, fake).',
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
    return round(media.probe_duration(audio_path, timeout=30), 3)


def _reference_text_from_raw(raw: str) -> str:
    """把 --reference-text / TTS_REF_TEXT 的值解释成路径或内联文本。"""
    stripped = raw.strip()
    candidate = Path(stripped).expanduser()
    if candidate.is_file():
        text = candidate.read_text(encoding='utf-8').strip()
        if text:
            return text
        raise ValueError(f'reference transcript file is empty: {candidate}')
    # 只在它真的像路径时才当路径处理：.txt 后缀，或
    # 含路径分隔符且内部没有空白。真正的内联转写
    # 通常含空格（也可能含 "/"，例如 "AI/人工智能"），
    # 因此不能被误读成一个缺失的文件。
    looks_like_path = stripped.lower().endswith('.txt') or (
        not any(ch.isspace() for ch in stripped)
        and (os.sep in stripped or bool(os.altsep and os.altsep in stripped))
    )
    if looks_like_path:
        # 看起来像路径却解析不出来的值，几乎一定是笔误；
        # 大声失败胜过不声不响地拿这段字面路径去克隆。
        raise FileNotFoundError(f'reference transcript file not found: {candidate}')
    return stripped


def resolve_reference_text(ref_wav: Path, cli_value: str | None) -> str:
    """返回用于音色克隆的参考音频转写文本。

    解析顺序：
      1. --reference-text / TTS_REF_TEXT，若看起来像路径则当作文件路径，
         否则当作内联字符串。
      2. 缓存在参考 WAV 旁边的同目录 "<ref>.txt"。
      3. 用 Qwen3-ASR 自动转写该参考音频一次并缓存。
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
    """mlx 变体：同样的解析顺序，减去 torch 自动 ASR 兜底（mlx 的
    Qwen3-TTS Base 没有参考转写也能克隆得很好）。"""
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
    """参考片段的纯文本转写（不带时间戳）。"""
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
        # 在 TTS 模型加载之前释放 ASR 模型 —— 两者都是多 GB 级，
        # 本地 GPU（例如 11GB）无法同时容纳它们。
        del model
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    if not text:
        raise RuntimeError('reference transcription returned empty text')
    return text


def _atempo_chain(rate: float | None) -> str | None:
    """为任意正速度构建 ffmpeg atempo 滤镜（或其串联）。

    单个 ``atempo`` 只支持 0.5–2.0，因此超出范围的倍率会被分解成一串在范围内的
    因子（例如 2.5 -> atempo=2.0,atempo=1.25）。
    不需要重新定速时返回 None。
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
    """通过 ffmpeg 把已有的音频文件转成 mp3，可选重新定速。"""
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
    """通过 ffmpeg 把浮点波形写成 mp3，可选重新定速。"""
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
    """共同接口：把旁白文本合成为 mp3 文件。

    两个布尔开关声明后端与转写的关系；``main()`` 据此持有契约（删除过期文件、
    直接对齐 -> ASR 的兜底、失败报告）：

    * ``always_emits_transcript`` —— mlx、fake：旁白文本直接对齐到音频上，
      因此每次运行都必须留下转写，无论是否带 flag；
    * ``has_direct_aligner`` —— mlx、qwen3tts、fake：能通过
      :meth:`emit_transcript` 用本地强制对齐器写出 transcript.json。没有对齐器
      的后端（dashscope）在需要转写时直接走 ASR —— 对它们不会记录一次假的直接
      对齐尝试。
    """

    name: str
    always_emits_transcript: bool = False
    has_direct_aligner: bool = False

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args

    def transcript_path(self, output_path: Path) -> Path:
        """本次运行写 transcript.json 的位置（当它确实写一份时）。"""
        raw = self.args.transcript_output
        return Path(raw).expanduser() if raw else output_path.parent / 'transcript.json'

    def wants_transcript(self, emit_transcript: bool) -> bool:
        """本次运行是否必须产出一份转写（flag 或后端能力）。"""
        return emit_transcript or self.always_emits_transcript

    @abc.abstractmethod
    def synthesize(self, text: str, output_path: Path) -> Path | None:
        """写出 ``output_path``；返回为对齐保留的音频（或 None）。

        返回的路径会交给 :meth:`emit_transcript`，并在 :meth:`cleanup` 中释放，
        这样后端可以在 mp3 之前的波形上做对齐，而不会把它泄漏到输出目录中。
        """
        raise NotImplementedError

    def emit_transcript(
        self,
        text: str,
        output_path: Path,
        transcript_path: Path,
        alignment_audio: Path | None = None,
    ) -> None:
        """用本后端的对齐器写出 ``transcript_path``；做不到时抛异常。"""
        raise RuntimeError(f'{self.name} backend has no direct aligner')

    def cleanup(self) -> None:
        """释放为产出转写而保留的任何临时音频。"""


def write_transcript(path: Path, sentences: list[dict]) -> None:
    if not sentences:
        # 空转写永远不是有效产物；让调用方去兜底。
        raise ValueError('aligner returned no timestamps')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sentences, ensure_ascii=False, indent=2), encoding='utf-8')
    log(f'wrote transcript: {path} ({len(sentences)} sentences)')


def scale_alignment_times(alignment: dict, factor: float) -> dict:
    """把 align_text 结果中的每个 start/end（秒）乘以 ``factor`` —— 用在
    ffmpeg atempo 在对齐之后重新定速了交付 mp3 的场景。"""
    for word in alignment.get('words') or []:
        word['start'] = round(word['start'] * factor, 3)
        word['end'] = round(word['end'] * factor, 3)
    for sentence in alignment.get('sentences') or []:
        sentence['start'] = round(sentence['start'] * factor, 3)
        sentence['end'] = round(sentence['end'] * factor, 3)
    return alignment


def emit_transcript_via_torch_aligner(text: str, audio_path: Path, out_path: Path) -> None:
    """用 torch 的 Qwen3-ForcedAligner 把旁白文本对齐到音频，
    并把 transcript schema（句子列表，毫秒）写到 ``out_path``。

    对齐器无法导入或返回不了时间戳时抛异常 —— 调用方随后退回用 ASR
    （transcribe.py）产出转写。
    """
    try:
        import torch
        from qwen_asr import Qwen3ForcedAligner
    except Exception as exc:  # noqa: BLE001 - 任何导入失败 => 没有对齐器
        raise RuntimeError(f'torch Qwen3-ForcedAligner unavailable ({exc})') from exc
    import gc

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
    write_transcript(out_path, transcript_from_torch_alignment(text, items))


class MLXBackend(TTSBackend):
    """mlx-audio Qwen3-TTS 音色克隆 + Qwen3-ForcedAligner 直接对齐。

    Apple Silicon 路径：不用 ASR —— 旁白文本被直接对齐到合成出的音频上，因此
    transcript.json 与 narration.txt 逐字一致。合成与转写产出是两个独立步骤
    （``main`` 会分别调用）。
    """

    name = 'mlx'
    always_emits_transcript = True
    has_direct_aligner = True

    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__(args)
        self._wav_path: Path | None = None
        self._atempo: float = DEFAULT_QWEN3TTS_SPEECH_RATE

    def _synthesize_wav(self, text: str, wav_path: Path) -> None:
        """用 mlx-audio TTS 输出到 ``wav_path``（mp3 之前的对齐源）。"""
        from tts_qwen import synthesize as mlx_synthesize  # 惰性：会拉起 mlx-audio

        ref_wav = resolve_reference_audio(self.args.reference_wav)
        if not ref_wav.is_file():
            raise FileNotFoundError(f'reference audio not found: {ref_wav}')
        ref_text = resolve_reference_text_optional(ref_wav, self.args.reference_text)

        tts_model = os.environ.get('TTS_MODEL_MLX', DEFAULT_TTS_MODEL_MLX)
        tts_language = os.environ.get('TTS_LANGUAGE_MLX', 'auto')
        log(f'synthesizing narration with mlx-audio Qwen3-TTS (model={tts_model})')
        mlx_synthesize(
            text,
            wav_path,
            voice_path=ref_wav,
            model_path=tts_model,
            language=tts_language,
            ref_text=ref_text,
        )

    def synthesize(self, text: str, output_path: Path) -> Path:
        """合成 mp3；保留 wav 供直接对齐并返回它。"""
        self._atempo = (
            self.args.speech_rate
            if self.args.speech_rate is not None
            else DEFAULT_QWEN3TTS_SPEECH_RATE
        )
        self._wav_path = output_path.with_suffix('.wav')
        self._synthesize_wav(text, self._wav_path)
        convert_to_mp3(self._wav_path, output_path, self._atempo)
        return self._wav_path

    def emit_transcript(
        self,
        text: str,
        output_path: Path,
        transcript_path: Path,
        alignment_audio: Path | None = None,
    ) -> None:
        """用 mlx-audio 对齐旁白文本并写出 transcript.json。

        失败时抛异常；调用方退回 ASR，mp3 不受影响。
        """
        from mlx_align import align_text  # 惰性：会拉起 mlx-audio

        aligner_model = os.environ.get('ALIGNER_MODEL_MLX', DEFAULT_ALIGNER_MODEL_MLX)
        align_language = os.environ.get('ALIGNER_LANGUAGE_MLX', 'Chinese')
        audio = alignment_audio or self._wav_path or output_path
        log(f'aligning narration text directly (model={aligner_model}, no ASR)')
        alignment = align_text(
            audio, text, model_path=aligner_model, language=align_language
        )
        if not alignment.get('words') or not alignment.get('sentences'):
            # 没有句子的话，schema 会把整段文本悄悄包成一个区间；
            # 那是一次失败的对齐，于是轮到 ASR。
            raise ValueError('alignment has no sentences or no words')
        if self._atempo and abs(self._atempo - 1.0) > 1e-3:
            # mp3 在合成之后被重新定速过；把时间戳按比例缩放以对应。
            alignment = scale_alignment_times(alignment, 1.0 / self._atempo)
        write_transcript(transcript_path, transcript_from_mlx_alignment(alignment))

    def cleanup(self) -> None:
        if self._wav_path is None:
            return
        try:
            self._wav_path.unlink()
        except OSError:
            pass
        self._wav_path = None


class Qwen3TTSBackend(TTSBackend):
    """本地 Qwen3-TTS 音色克隆（参考 WAV + 它的转写文本）。"""

    name = 'qwen3tts'
    has_direct_aligner = True

    def synthesize(self, text: str, output_path: Path) -> None:
        import gc

        import torch
        from qwen_tts import Qwen3TTSModel

        ref_wav = resolve_reference_audio(self.args.reference_wav)
        if not ref_wav.is_file():
            raise FileNotFoundError(f'reference audio not found: {ref_wav}')

        ref_text = resolve_reference_text(ref_wav, self.args.reference_text)

        model_id = os.environ.get('QWEN3TTS_MODEL', DEFAULT_QWEN3TTS_MODEL)
        language = os.environ.get('QWEN3TTS_LANGUAGE', 'Chinese')
        use_cuda = torch.cuda.is_available()
        dtype = torch.float16 if use_cuda else torch.float32  # Turing：fp16，无 flash-attn
        device = 'cuda:0' if use_cuda else 'cpu'

        log(f'loading Qwen3-TTS model={model_id} device={device} dtype={dtype}')
        model = Qwen3TTSModel.from_pretrained(model_id, device_map=device, dtype=dtype)

        # 通过 soundfile 把参考片段以 (waveform, sr) 元组传入，
        # 这样音频 I/O 不依赖外部的 SoX 二进制。
        import soundfile as sf
        ref_audio, ref_sr = sf.read(str(ref_wav))
        if getattr(ref_audio, 'ndim', 1) > 1:
            ref_audio = ref_audio.mean(axis=1)  # 下混为单声道

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

    def emit_transcript(
        self,
        text: str,
        output_path: Path,
        transcript_path: Path,
        alignment_audio: Path | None = None,
    ) -> None:
        """用 torch 的 Qwen3-ForcedAligner 产出转写（不走 ASR）。"""
        emit_transcript_via_torch_aligner(text, output_path, transcript_path)


class CosyVoiceBackend(TTSBackend):
    """云端 DashScope CosyVoice 合成（兜底）。"""

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


class FakeBackend(TTSBackend):
    """仅测试用：静音 mp3 + 一个均匀时间的对齐器，不加载模型。

    只能通过显式 ``--backend fake`` / ``TTS_BACKEND=fake`` 触达（auto 永不选
    它）。``TTS_FAKE_ALIGN_FAIL=1`` 会让对齐器失败，从而可以演练 ASR 兜底。
    """

    name = 'fake'
    always_emits_transcript = True
    has_direct_aligner = True

    def synthesize(self, text: str, output_path: Path) -> None:
        duration_s = fake_backend.synthetic_duration_s(text)
        log(f'writing {duration_s:.2f}s of silence (fake backend, test only)')
        fake_backend.write_silent_mp3(output_path, duration_s)

    def emit_transcript(
        self,
        text: str,
        output_path: Path,
        transcript_path: Path,
        alignment_audio: Path | None = None,
    ) -> None:
        if os.environ.get('TTS_FAKE_ALIGN_FAIL') == '1':
            raise RuntimeError('fake aligner failed (TTS_FAKE_ALIGN_FAIL=1)')
        duration_s = media.probe_duration(output_path)
        write_transcript(transcript_path, fake_backend.uniform_transcript(text, duration_s))


BACKENDS: dict[str, type[TTSBackend]] = {
    cls.name: cls
    for cls in (MLXBackend, Qwen3TTSBackend, CosyVoiceBackend, FakeBackend)
}


class TranscriptError(RuntimeError):
    """直接对齐与 ASR 都没能留下转写；携带每一次尝试。"""

    def __init__(self, attempts: list[dict[str, str]]) -> None:
        self.attempts = attempts
        tries = '; '.join(f"{a['method']}: {a['error']}" for a in attempts)
        super().__init__(f'no fresh transcript could be produced ({tries})')


def transcribe_with_asr(audio_path: Path, transcript_path: Path) -> None:
    """对 mp3 运行 scripts/transcribe.py；失败时带上它的错误抛出。

    子进程继承环境，因此 ASR_BACKEND 和后端凭据会像手动运行时那样生效。stdout
    可能夹带零散的行（某个爱聊天的 SDK 在输出 JSON 之前打的），因此以最后一行
    可解析的 JSON 作为结果；stderr 会被捕获，失败时报告其尾部。
    """
    script = Path(__file__).resolve().parent / 'transcribe.py'
    log(f'running {script.name} (ASR) on {audio_path}')
    proc = subprocess.run(
        [sys.executable, str(script), str(audio_path), str(transcript_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    result: dict | None = None
    for line in reversed([line for line in proc.stdout.splitlines() if line.strip()]):
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            result = parsed
            break
    stderr_tail = '\n'.join(proc.stderr.splitlines()[-5:])
    if proc.returncode != 0 or result is None or result.get('success') is not True:
        message = (
            (result or {}).get('error')
            or f'{script.name} exited {proc.returncode} without a JSON result'
        )
        if stderr_tail:
            message = f'{message}; stderr: {stderr_tail}'
        raise RuntimeError(message)
    if not result.get('sentence_count') or not transcript_path.is_file():
        raise RuntimeError(
            f"{script.name} reported success but wrote no sentences"
            + (f'; stderr: {stderr_tail}' if stderr_tail else '')
        )


def produce_transcript(
    backend: TTSBackend,
    text: str,
    output_path: Path,
    transcript_path: Path,
    alignment_audio: Path | None,
) -> str:
    """在 ``transcript_path`` 留下一份新的转写；返回它是怎么产生的。

    直接对齐（后端自己的对齐器，若有）优先；当它什么都没写时，通过
    transcribe.py 走 ASR。两者都不行时抛 :class:`TranscriptError`，其中携带
    实际做过的每一次尝试。
    """
    attempts: list[dict[str, str]] = []
    if backend.has_direct_aligner:
        try:
            backend.emit_transcript(text, output_path, transcript_path, alignment_audio)
            if not transcript_path.is_file():
                raise RuntimeError('direct alignment wrote no transcript')
            return 'direct_align'
        except Exception as exc:  # noqa: BLE001 - 任何对齐器失败 => 试 ASR
            log(f'direct alignment failed ({exc}); falling back to ASR')
            attempts.append({'method': 'direct_align', 'error': str(exc)})
        transcript_path.unlink(missing_ok=True)
    try:
        transcribe_with_asr(output_path, transcript_path)
    except Exception as exc:  # noqa: BLE001 - 作为第二次尝试报告
        log(f'ASR failed ({exc})')
        attempts.append({'method': 'asr', 'error': str(exc)})
        transcript_path.unlink(missing_ok=True)
        raise TranscriptError(attempts) from exc
    return 'asr'


def resolve_backend_cli(args: argparse.Namespace) -> int:
    """--resolve-backend：打印后端决定（只做探测），不加载模型。"""
    return bs.resolve_backend_cli(
        lambda: resolve_backend_name(args.backend), log=log, print_json=print_json
    )


def main() -> int:
    args = parse_args()
    if args.resolve_backend:
        return resolve_backend_cli(args)

    try:
        backend_name, _source, _probes = resolve_backend_name(args.backend)
    except (UnknownBackendError, BackendUnavailableError) as exc:
        return bs.backend_error_response(exc, log=log, print_json=print_json)
    backend_cls = BACKENDS[backend_name]

    input_text = read_input_text(args.input_file)

    output_dir = Path(args.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = (output_dir / 'narration.mp3').resolve()

    # 所有后端共用一处转写落点：synthesize() 返回为对齐保留的音频
    # （mlx 是 mp3 之前的 wav），wants_transcript() 决定本次运行是否
    # 必须留下一份转写，cleanup() 在任何情况下都会释放那段音频。
    backend = backend_cls(args)
    transcript_path = backend.transcript_path(output_path)
    # 更早一次运行留下的转写描述的是那次的音频，绝不是这一次的：
    # 若本次运行没能产出自己的转写，那份文件不能存活下来。
    if transcript_path.is_file():
        log(f'removing stale transcript from an earlier run: {transcript_path}')
        transcript_path.unlink()
    transcript_method = None
    try:
        alignment_audio = backend.synthesize(input_text, output_path)
        if backend.wants_transcript(args.emit_transcript):
            transcript_method = produce_transcript(
                backend, input_text, output_path, transcript_path, alignment_audio
            )
    except TranscriptError as exc:
        # mp3 是好的、会保留；只是转写缺失。
        log(f'error: {exc}')
        print_json(
            {
                'success': False,
                'error': str(exc),
                'output_path': str(output_path),
                'transcript_attempts': exc.attempts,
            }
        )
        return 1
    finally:
        backend.cleanup()

    duration_s = detect_duration_seconds(output_path)
    log(f'wrote {output_path}')
    payload: dict[str, object] = {
        'success': True,
        'backend': backend_name,
        'output_path': str(output_path),
        'duration_s': duration_s,
    }
    if transcript_method is not None:
        payload['transcript_method'] = transcript_method
        payload['transcript_path'] = str(transcript_path.resolve())
    print_json(payload)
    return 0


if __name__ == '__main__':
    raise SystemExit(cli.run(main, TOOL_NAME))
