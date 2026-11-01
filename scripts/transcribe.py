#!/usr/bin/env python3
"""
词 / 字符级的 ASR，优先使用本地后端。

后端（用 --backend 或 ASR_BACKEND 环境变量选择，默认 auto）：
  auto       按环境挑选：有 CUDA GPU -> qwen3；有 DASHSCOPE_API_KEY ->
             dashscope；否则以一条 JSON 错误退出 1，并列出缺少什么
             （Apple Silicon 也在其中：当 voice-clone.py 的直接对齐失败时，
             ASR 就是兜底，因此它永远不会“不需要”）。
  qwen3      本地 Qwen3-ASR + Qwen3-ForcedAligner（Apache-2.0）。跑在本地
             GPU 上，返回字符级（CJK）/ 词级（拉丁）时间戳，可选 ITN。不需要
             云端 key。
  dashscope  阿里云 DashScope 非实时 ASR（paraformer-v2，云端兜底）。需要
             DASHSCOPE_API_KEY。
  fake       TEST ONLY（测试用）：把 ASR_FAKE_TEXT 中的文本“识别”出来，按音频
             ffprobe 时长均匀铺开；不加载模型。只能显式选择
             （--backend fake / ASR_BACKEND=fake）；auto 永远不会选它。

用法：
  python3 transcribe.py <input.mp3|http(s)://...|oss://...> <output.json>
                        [--backend auto|qwen3|dashscope]
  python3 transcribe.py --resolve-backend   # 只打印 auto 的决定（不加载模型）

可选环境变量：
  ASR_BACKEND           auto（默认）| qwen3 | dashscope | fake（仅测试）
  ASR_FAKE_TEXT         （仅 fake 后端，必需）fake ASR 要“识别”的 UTF-8 文本；
                        没有它时 fake 后端会报错
  # qwen3 后端：
  QWEN3_ASR_MODEL       默认 Qwen/Qwen3-ASR-1.7B
  QWEN3_ALIGNER_MODEL   默认 Qwen/Qwen3-ForcedAligner-0.6B
  QWEN3_LANGUAGE        强制指定语言名（例如 "Chinese"）；默认 auto
  ASR_ITN               1（默认）时做逆文本归一化（口语中文数字 -> 阿拉伯数字，
                        例如 三点一 -> 3.1），由 wetext 完成；设 0 则保持原文
  # dashscope 后端：
  DASHSCOPE_API_KEY     dashscope 必需
  ASR_MODEL             默认 paraformer-v2；例如 qwen3-asr-flash-filetrans
  ASR_LANGUAGE_HINTS    JSON 数组，默认 ["zh", "en"]

输出 JSON 形状（稳定的下游契约）：
  [
    {
      "begin": 0,           # 毫秒
      "end": 60020,         # 毫秒
      "text": "...",
      "words": [{"text": "为", "begin": 0, "end": 326}, ...]
    },
    ...
  ]

测试接缝（有文档记录；测试套件也用它）：auto / --resolve-backend 背后的硬件 /
系统探测在被设置时读取这些覆盖值：
  ASR_DETECT_PLATFORM   例如 darwin | linux   （默认：sys.platform）
  ASR_DETECT_MACHINE    例如 arm64 | x86_64   （默认：platform.machine()）
  ASR_DETECT_CUDA       1 | 0                 （默认：torch.cuda.is_available()）
"""
from __future__ import annotations

import abc
import argparse
import json
import os
import re
import sys
from http import HTTPStatus
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # 同级脚本

import backend_select as bs
import cli
import fake_backend
import media
from backend_select import BackendUnavailableError, UnknownBackendError
from transcript_schema import transcript_from_torch_alignment


# --- 后端选择（auto） --------------------------------------------------------
#
# 各项探测、CLI > 环境变量 > auto 的解析，以及 --resolve-backend 的输出，都在
# backend_select.py 中（与 voice-clone.py 共用）。本脚本只提供 ASR 后端注册表与
# ASR 的 auto 顺序；有文档记录的探测覆盖值是 ASR_DETECT_PLATFORM /
# ASR_DETECT_MACHINE / ASR_DETECT_CUDA。

PROBE_PREFIX = 'ASR_DETECT'


def _auto_backend(probes: dict[str, object]) -> tuple[str, dict[str, object]]:
    """ASR 的 auto 顺序：CUDA -> qwen3；DASHSCOPE_API_KEY -> dashscope；
    否则抛 BackendUnavailableError 并列出缺少什么。"""
    missing: list[str] = []
    if probes['cuda']:
        return 'qwen3', probes
    missing.append('CUDA-capable GPU with torch (backend qwen3)')
    if probes['dashscope_key']:
        return 'dashscope', probes
    missing.append('DASHSCOPE_API_KEY (backend dashscope)')
    raise BackendUnavailableError(
        'no usable ASR backend: ' + '; '.join(missing), missing, probes
    )


def resolve_backend_name(cli_backend: str | None) -> tuple[str, str, dict[str, object]]:
    """解析出实际生效的 ASR 后端。返回 (name, source, probes)。

    source 是 'cli'（--backend）、'env'（ASR_BACKEND）或 'auto'。共用的契约见
    backend_select.resolve_backend_name，ASR 的 auto 顺序见 _auto_backend。
    """
    return bs.resolve_backend_name(
        cli_backend,
        env_var='ASR_BACKEND',
        probe_prefix=PROBE_PREFIX,
        backends=BACKENDS,
        auto_resolve=_auto_backend,
        label='ASR',
    )


TOOL_NAME = 'transcribe'

print_json = cli.print_json
log = cli.make_logger(TOOL_NAME)


def is_remote_audio(audio_arg: str) -> bool:
    return audio_arg.startswith(('http://', 'https://', 'oss://'))


# ----------------------------------------------------------------------------- #
# 共用的 ITN + 分句辅助函数（本地后端使用）
# ----------------------------------------------------------------------------- #

# 日历单位；ITN 在这些单位处切块之后再逐块施加，这样 wetext 不会把完整日期
# （年 + 月）压成 "2026/06" 这种斜杠形式 —— 保持云端风格的 "2026年6月"，
# 并避免在边界处产生合并痕迹。
_CAL_UNITS = '年月日号時时分秒'
_CAL_SPLIT = re.compile(f'(?<=[{_CAL_UNITS}])')
_ITN_NORMALIZER = None
_ITN_DISABLED = False


def itn_enabled() -> bool:
    return os.environ.get('ASR_ITN', '1') not in ('0', 'false', 'False', '')


def _get_itn_normalizer():
    """惰性构建一个 wetext 中文 ITN 归一化器；不可用时为 None。"""
    global _ITN_NORMALIZER, _ITN_DISABLED
    if _ITN_DISABLED:
        return None
    if _ITN_NORMALIZER is None:
        try:
            from wetext import Normalizer
            _ITN_NORMALIZER = Normalizer(lang='zh', operator='itn')
        except Exception as exc:  # noqa: BLE001 - 优雅降级
            log(f'ITN disabled (wetext unavailable: {exc})')
            _ITN_DISABLED = True
            return None
    return _ITN_NORMALIZER


def itn_text(text: str) -> str:
    """对单个字符串做逆文本归一化（口语中文数字 -> 数字）。

    先按日历单位边界切分，使日期保持其带单位的形式。
    ITN 不可用时原样返回输入。
    """
    norm = _get_itn_normalizer()
    if norm is None:
        return text
    out = []
    for chunk in _CAL_SPLIT.split(text):
        out.append(norm.normalize(chunk) if chunk else '')
    return ''.join(out)


def apply_itn_to_sentences(sentences: list[dict]) -> list[dict]:
    """把每个句子的 text 与词 token 重写成 ITN（阿拉伯数字）形式。

    词级时间戳被保留：合并成一个阿拉伯数字 token 的那些字符继承合并后的区间
    （first.begin .. last.end）。每个原始词 token 恰好输出一次（不丢、不重复）；
    ITN 删掉的区间会并入相邻 token 的时间。任何错误时退回逐字的原句。
    """
    import difflib

    if not itn_enabled() or _get_itn_normalizer() is None:
        return sentences

    out = []
    for s in sentences:
        words = s.get('words') or []
        try:
            new_text = itn_text(s.get('text') or '')
            orig = ''.join(w['text'] for w in words)
            itn = itn_text(orig)
            char_word = [wi for wi, w in enumerate(words) for _ in w['text']]
            new_words: list[dict] = []
            emitted: set[int] = set()
            sm = difflib.SequenceMatcher(None, orig, itn, autojunk=False)
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                # 与该原始字符区间有重叠的词，去重后
                # 排除已被更早的 opcode 输出过的。
                wis = [wi for wi in dict.fromkeys(char_word[i1:i2]) if wi not in emitted]
                if tag == 'equal':
                    for wi in wis:
                        new_words.append(dict(words[wi]))
                        emitted.add(wi)
                    continue
                seg = itn[j1:j2]
                if wis:
                    begin = words[wis[0]]['begin']
                    end = words[wis[-1]]['end']
                    emitted.update(wis)
                else:
                    begin = new_words[-1]['end'] if new_words else (
                        words[0]['begin'] if words else 0)
                    end = begin
                if seg:
                    new_words.append({'text': seg, 'begin': begin, 'end': end})
                elif wis and new_words:
                    # ITN 删掉了这些字符；把它们的时间并入相邻 token，
                    # 使任何区间都不会被悄悄丢掉。
                    new_words[-1]['end'] = max(new_words[-1]['end'], end)
            out.append({
                'begin': s['begin'],
                'end': s['end'],
                'text': new_text,
                'words': new_words or words,
            })
        except Exception as exc:  # noqa: BLE001 - 失败时保留逐字原文
            log(f'ITN skipped for one sentence ({exc})')
            out.append(s)
    return out


# ----------------------------------------------------------------------------- #
# 后端接口与实现
# ----------------------------------------------------------------------------- #


class ASRBackend(abc.ABC):
    """共同接口：把一个音频引用变成我们的句子 schema。"""

    name: str

    @abc.abstractmethod
    def transcribe(self, audio_arg: str) -> list[dict]:
        """返回毫秒级的 [{begin, end, text, words:[{text, begin, end}]}]。"""
        raise NotImplementedError


class Qwen3ASRBackend(ASRBackend):
    """本地 Qwen3-ASR + Qwen3-ForcedAligner（可选 ITN）。"""

    name = 'qwen3'

    def transcribe(self, audio_arg: str) -> list[dict]:
        if not is_remote_audio(audio_arg) and not os.path.isfile(audio_arg):
            raise FileNotFoundError(f'not found: {audio_arg}')

        import torch
        from qwen_asr import Qwen3ASRModel

        asr_model = os.environ.get('QWEN3_ASR_MODEL', DEFAULT_QWEN3_ASR_MODEL)
        aligner_model = os.environ.get('QWEN3_ALIGNER_MODEL', DEFAULT_QWEN3_ALIGNER_MODEL)
        use_cuda = torch.cuda.is_available()
        # Turing（sm_75）没有原生 bf16；fp16 是更快也更稳的选择。
        dtype = torch.float16 if use_cuda else torch.float32
        device = 'cuda:0' if use_cuda else 'cpu'

        log(f'loading Qwen3-ASR model={asr_model} aligner={aligner_model} '
            f'device={device} dtype={dtype}')
        model = Qwen3ASRModel.from_pretrained(
            asr_model,
            dtype=dtype,
            device_map=device,
            max_new_tokens=2048,
            forced_aligner=aligner_model,
            forced_aligner_kwargs=dict(dtype=dtype, device_map=device),
        )

        language = os.environ.get('QWEN3_LANGUAGE') or None
        log(f'transcribing {audio_arg} (language={language or "auto"})')
        results = model.transcribe(
            audio=audio_arg,
            language=language,
            return_time_stamps=True,
        )
        result = results[0]
        items = list(result.time_stamps.items) if result.time_stamps is not None else []
        if not items:
            log('warning: no aligned tokens returned')
            return []
        sentences = transcript_from_torch_alignment(result.text or '', items)
        if itn_enabled():
            log('applying ITN (Chinese numerals -> Arabic digits); set ASR_ITN=0 to disable')
            sentences = apply_itn_to_sentences(sentences)
        return sentences


class FakeASRBackend(ASRBackend):
    """仅测试用：转写内容是 ASR_FAKE_TEXT 按音频时长均匀铺开。"""

    name = 'fake'

    def transcribe(self, audio_arg: str) -> list[dict]:
        text = os.environ.get('ASR_FAKE_TEXT')
        if not text:
            raise RuntimeError(
                'ASR_FAKE_TEXT is not set: the fake ASR backend needs the text to "recognize"'
            )
        if is_remote_audio(audio_arg) or not os.path.isfile(audio_arg):
            raise FileNotFoundError(f'not found: {audio_arg}')
        duration_s = media.probe_duration(audio_arg)
        log(f'fake ASR (test only): spreading the text over {duration_s:.2f}s')
        return fake_backend.uniform_transcript(text, duration_s)


class ParaformerBackend(ASRBackend):
    """云端 DashScope 非实时 ASR（paraformer-v2）。"""

    name = 'dashscope'

    @staticmethod
    def _parse_language_hints() -> list[str]:
        raw = os.environ.get('ASR_LANGUAGE_HINTS')
        if not raw:
            return ['zh', 'en']
        try:
            hints = json.loads(raw)
            if isinstance(hints, list) and all(isinstance(h, str) for h in hints):
                return hints
            raise ValueError('ASR_LANGUAGE_HINTS must decode to list[str]')
        except json.JSONDecodeError as exc:
            raise ValueError(f'ASR_LANGUAGE_HINTS is not valid JSON: {exc}') from exc

    @staticmethod
    def _convert_words(raw_words: list[dict]) -> list[dict]:
        """把 paraformer-v2 的词对象摊平成 {text, begin, end}。"""
        out = []
        for word in raw_words or []:
            text = (word.get('text') or '') + (word.get('punctuation') or '')
            out.append(
                {
                    'text': text,
                    'begin': word.get('begin_time'),
                    'end': word.get('end_time'),
                }
            )
        return out

    def _parse_payload(self, payload: dict) -> list[dict]:
        """把 paraformer-v2 的转写 JSON 解析成我们的 schema。"""
        sentences = []
        for transcript in payload.get('transcripts') or []:
            for sentence in transcript.get('sentences') or []:
                sentences.append(
                    {
                        'begin': sentence.get('begin_time'),
                        'end': sentence.get('end_time'),
                        'text': sentence.get('text'),
                        'words': self._convert_words(sentence.get('words') or []),
                    }
                )
        return sentences

    def transcribe(self, audio_arg: str) -> list[dict]:
        from dashscope.audio.asr import Transcription
        from dashscope.utils.oss_utils import OssUtils
        import dashscope
        import requests

        is_remote = is_remote_audio(audio_arg)
        if not is_remote and not os.path.isfile(audio_arg):
            raise FileNotFoundError(f'not found: {audio_arg}')

        api_key = os.environ.get('DASHSCOPE_API_KEY')
        if not api_key:
            raise EnvironmentError('DASHSCOPE_API_KEY env var not set')
        dashscope.api_key = api_key

        model = os.environ.get('ASR_MODEL', 'paraformer-v2')
        language_hints = self._parse_language_hints()

        if is_remote:
            file_url = audio_arg
            log(f'using remote audio URL: {file_url}')
        else:
            log(f'uploading local audio to DashScope OSS: {audio_arg}')
            file_url, _ = OssUtils.upload(
                model=model,
                file_path=os.path.abspath(audio_arg),
                api_key=api_key,
            )
            log(f'uploaded to {file_url}')

        log(f'submit async transcription: model={model} language_hints={language_hints}')
        submit_response = Transcription.async_call(
            model=model,
            file_urls=[file_url],
            language_hints=language_hints,
            # paraformer-v2 后端只对带这个 header 的请求解析 oss:// URL；
            # 缺这个 header 时返回 FILE_DOWNLOAD_FAILED。SDK 的 Transcription
            # 类没自动加（不像 image_synthesis / multimodal_conversation 等），
            # 必须手动传。
            headers={'X-DashScope-OssResourceResolve': 'enable'},
        )
        if submit_response.status_code != HTTPStatus.OK:
            raise RuntimeError(
                f'submit failed: status_code={submit_response.status_code} '
                f'code={getattr(submit_response, "code", None)} '
                f'message={getattr(submit_response, "message", None)}'
            )
        task_id = submit_response.output.task_id
        log(f'task submitted: task_id={task_id}; waiting for completion')

        result_response = Transcription.wait(task=task_id)
        if result_response.status_code != HTTPStatus.OK:
            raise RuntimeError(
                f'task fetch failed: status_code={result_response.status_code} '
                f'message={getattr(result_response, "message", None)}'
            )
        task_status = getattr(result_response.output, 'task_status', None)
        if task_status != 'SUCCEEDED':
            raise RuntimeError(
                f'task did not succeed: task_status={task_status} '
                f'output={result_response.output}'
            )

        results = getattr(result_response.output, 'results', None) or []
        if not results:
            raise RuntimeError(f'task succeeded but no results: {result_response.output}')
        first = results[0]
        if first.get('subtask_status') != 'SUCCEEDED':
            raise RuntimeError(
                f'subtask failed: {first.get("subtask_status")} message={first.get("message")}'
            )
        transcription_url = first.get('transcription_url')
        if not transcription_url:
            raise RuntimeError(f'no transcription_url in result: {first}')

        log(f'downloading transcription JSON: {transcription_url}')
        transcript_response = requests.get(transcription_url, timeout=120)
        transcript_response.raise_for_status()
        return self._parse_payload(transcript_response.json())


DEFAULT_QWEN3_ASR_MODEL = 'Qwen/Qwen3-ASR-1.7B'
DEFAULT_QWEN3_ALIGNER_MODEL = 'Qwen/Qwen3-ForcedAligner-0.6B'

BACKENDS: dict[str, type[ASRBackend]] = {
    cls.name: cls for cls in (Qwen3ASRBackend, ParaformerBackend, FakeASRBackend)
}


# --------------------------------------------------------------------------- #


def parse_args() -> argparse.Namespace:
    parser = cli.JsonArgumentParser(
        TOOL_NAME,
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            'key env vars: ASR_BACKEND (default auto), QWEN3_ASR_MODEL, '
            'QWEN3_ALIGNER_MODEL, DASHSCOPE_API_KEY, ASR_MODEL. Probe overrides '
            'for --resolve-backend: ASR_DETECT_PLATFORM / ASR_DETECT_MACHINE / '
            'ASR_DETECT_CUDA.'
        ),
    )
    parser.add_argument('input', nargs='?', default=None,
                        help='input.mp3 | http(s)://... | oss://...')
    parser.add_argument('output', nargs='?', default=None, help='output JSON path')
    parser.add_argument(
        '--backend',
        choices=['auto'] + sorted(BACKENDS),
        default=None,
        help='ASR backend. Defaults to ASR_BACKEND env or "auto" (CUDA -> '
             'qwen3; DASHSCOPE_API_KEY -> dashscope). "fake" is test-only '
             '(测试用): no model, never chosen by auto.',
    )
    parser.add_argument(
        '--resolve-backend',
        action='store_true',
        help='Print the backend decision as one JSON document and exit '
             '(probes only — no model is loaded).',
    )
    return parser.parse_args()


def resolve_backend_cli(args: argparse.Namespace) -> int:
    """--resolve-backend：打印后端决定（只做探测），不加载模型。"""
    return bs.resolve_backend_cli(
        lambda: resolve_backend_name(args.backend), log=log, print_json=print_json
    )


def main() -> int:
    args = parse_args()
    if args.resolve_backend:
        return resolve_backend_cli(args)
    if not args.input or not args.output:
        log('bad arguments: input and output are required (unless --resolve-backend)')
        print_json({'success': False, 'error': 'input and output are required'})
        return 2

    try:
        backend_name, _source, _probes = resolve_backend_name(args.backend)
    except (UnknownBackendError, BackendUnavailableError) as exc:
        return bs.backend_error_response(exc, log=log, print_json=print_json)

    backend_cls = BACKENDS[backend_name]
    sentences = backend_cls().transcribe(args.input)

    out_dir = os.path.dirname(os.path.abspath(args.output))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(sentences, f, ensure_ascii=False, indent=2)

    total_words = sum(len(sentence['words']) for sentence in sentences)
    log(f'wrote {args.output}: {len(sentences)} sentences, {total_words} words')
    print_json(
        {
            'success': True,
            'backend': backend_name,
            'output_path': os.path.abspath(args.output),
            'sentence_count': len(sentences),
            'word_count': total_words,
        }
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(cli.run(main, TOOL_NAME))
