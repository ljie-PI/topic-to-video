#!/usr/bin/env python3
"""
Word/character level ASR with a local-first backend.

Backends (select via --backend or ASR_BACKEND env, default: auto):
  auto       Pick by environment: CUDA GPU -> qwen3; DASHSCOPE_API_KEY ->
             dashscope; otherwise exit 1 with a JSON error listing what is
             missing (Apple Silicon included: ASR is the fallback when
             voice-clone.py's direct alignment fails, so it is never "not
             needed").
  qwen3      Local Qwen3-ASR + Qwen3-ForcedAligner (Apache-2.0). Runs on the
             local GPU, returns char-level (CJK) / word-level (Latin)
             timestamps with optional ITN. No cloud key needed.
  dashscope  Aliyun DashScope non-realtime ASR (paraformer-v2, cloud
             fallback). Needs DASHSCOPE_API_KEY.
  fake       TEST ONLY (测试用): "recognizes" the text in ASR_FAKE_TEXT, spread
             evenly over the audio's ffprobe duration; no model. Only
             selectable explicitly (--backend fake / ASR_BACKEND=fake); auto
             never picks it.

Usage:
  python3 transcribe.py <input.mp3|http(s)://...|oss://...> <output.json>
                        [--backend auto|qwen3|dashscope]
  python3 transcribe.py --resolve-backend   # print the auto decision (no model)

Optional env:
  ASR_BACKEND           auto (default) | qwen3 | dashscope
  # qwen3 backend:
  QWEN3_ASR_MODEL       default Qwen/Qwen3-ASR-1.7B
  QWEN3_ALIGNER_MODEL   default Qwen/Qwen3-ForcedAligner-0.6B
  QWEN3_LANGUAGE        force a language name (e.g. "Chinese"); default auto
  ASR_ITN               1 (default) applies inverse text normalization
                        (spoken Chinese numerals -> Arabic digits, e.g.
                        三点一 -> 3.1) via wetext; set 0 to keep verbatim
  # dashscope backend:
  DASHSCOPE_API_KEY     required for dashscope
  ASR_MODEL             default paraformer-v2; e.g. qwen3-asr-flash-filetrans
  ASR_LANGUAGE_HINTS    JSON array, default ["zh", "en"]

Output JSON shape (stable downstream contract):
  [
    {
      "begin": 0,           # ms
      "end": 60020,         # ms
      "text": "...",
      "words": [{"text": "为", "begin": 0, "end": 326}, ...]
    },
    ...
  ]

Testing seam (documented; also used by the test-suite): the hardware/OS
probes behind auto/--resolve-backend read these overrides when set:
  ASR_DETECT_PLATFORM   e.g. darwin | linux   (default: sys.platform)
  ASR_DETECT_MACHINE    e.g. arm64 | x86_64   (default: platform.machine())
  ASR_DETECT_CUDA       1 | 0                 (default: torch.cuda.is_available())
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

sys.path.insert(0, str(Path(__file__).resolve().parent))  # sibling scripts

import backend_select as bs
import cli
import fake_backend
import media
from backend_select import BackendUnavailableError, UnknownBackendError
from transcript_schema import transcript_from_torch_alignment


# --- backend selection (auto) ---------------------------------------------------
#
# The probes, the CLI > env > auto resolution and the --resolve-backend output
# live in backend_select.py (shared with voice-clone.py). This script only
# supplies the ASR backend registry and the ASR auto order; the documented
# probe overrides are ASR_DETECT_PLATFORM / ASR_DETECT_MACHINE / ASR_DETECT_CUDA.

PROBE_PREFIX = 'ASR_DETECT'


def _auto_backend(probes: dict[str, object]) -> tuple[str, dict[str, object]]:
    """ASR auto order: CUDA -> qwen3; DASHSCOPE_API_KEY -> dashscope;
    otherwise BackendUnavailableError listing what is missing."""
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
    """Resolve the effective ASR backend. Returns (name, source, probes).

    source is 'cli' (--backend), 'env' (ASR_BACKEND) or 'auto'. See
    backend_select.resolve_backend_name for the shared contract and
    _auto_backend for the ASR auto order.
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


# --------------------------------------------------------------------------- #
# Shared ITN + sentence-segmentation helpers (used by the local backend)
# --------------------------------------------------------------------------- #

# Calendar units; ITN is applied per chunk split *after* these so wetext does
# not collapse a full date (年 + 月) into a slash form like "2026/06" — keeping
# the cloud-style "2026年6月" and avoiding merge artifacts at the boundary.
_CAL_UNITS = '年月日号時时分秒'
_CAL_SPLIT = re.compile(f'(?<=[{_CAL_UNITS}])')
_ITN_NORMALIZER = None
_ITN_DISABLED = False


def itn_enabled() -> bool:
    return os.environ.get('ASR_ITN', '1') not in ('0', 'false', 'False', '')


def _get_itn_normalizer():
    """Lazily build a single wetext zh ITN normalizer; None if unavailable."""
    global _ITN_NORMALIZER, _ITN_DISABLED
    if _ITN_DISABLED:
        return None
    if _ITN_NORMALIZER is None:
        try:
            from wetext import Normalizer
            _ITN_NORMALIZER = Normalizer(lang='zh', operator='itn')
        except Exception as exc:  # noqa: BLE001 - degrade gracefully
            log(f'ITN disabled (wetext unavailable: {exc})')
            _ITN_DISABLED = True
            return None
    return _ITN_NORMALIZER


def itn_text(text: str) -> str:
    """Inverse-text-normalize one string (spoken Chinese numbers -> digits).

    Splits at calendar-unit boundaries first so dates keep their unit form.
    Returns the input unchanged if ITN is unavailable.
    """
    norm = _get_itn_normalizer()
    if norm is None:
        return text
    out = []
    for chunk in _CAL_SPLIT.split(text):
        out.append(norm.normalize(chunk) if chunk else '')
    return ''.join(out)


def apply_itn_to_sentences(sentences: list[dict]) -> list[dict]:
    """Rewrite each sentence's text + word tokens to ITN (Arabic digit) form.

    Word-level timestamps are preserved: characters that collapse into one
    Arabic-digit token inherit the merged span (first.begin .. last.end). Each
    original word token is emitted exactly once (no drop, no duplicate); a span
    that ITN deletes is folded into the neighbouring token's time. Falls back
    to the verbatim sentence on any error.
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
                # words overlapping this original char range, de-duplicated and
                # excluding any already emitted by an earlier opcode.
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
                    # ITN deleted these chars; keep their time by extending the
                    # neighbouring token so no span is silently lost.
                    new_words[-1]['end'] = max(new_words[-1]['end'], end)
            out.append({
                'begin': s['begin'],
                'end': s['end'],
                'text': new_text,
                'words': new_words or words,
            })
        except Exception as exc:  # noqa: BLE001 - keep verbatim on failure
            log(f'ITN skipped for one sentence ({exc})')
            out.append(s)
    return out


# --------------------------------------------------------------------------- #
# Backend interface + implementations
# --------------------------------------------------------------------------- #


class ASRBackend(abc.ABC):
    """Common interface: turn an audio reference into our sentence schema."""

    name: str

    @abc.abstractmethod
    def transcribe(self, audio_arg: str) -> list[dict]:
        """Return [{begin, end, text, words:[{text, begin, end}]}] in ms."""
        raise NotImplementedError


class Qwen3ASRBackend(ASRBackend):
    """Local Qwen3-ASR + Qwen3-ForcedAligner (with optional ITN)."""

    name = 'qwen3'

    def transcribe(self, audio_arg: str) -> list[dict]:
        if not is_remote_audio(audio_arg) and not os.path.isfile(audio_arg):
            raise FileNotFoundError(f'not found: {audio_arg}')

        import torch
        from qwen_asr import Qwen3ASRModel

        asr_model = os.environ.get('QWEN3_ASR_MODEL', DEFAULT_QWEN3_ASR_MODEL)
        aligner_model = os.environ.get('QWEN3_ALIGNER_MODEL', DEFAULT_QWEN3_ALIGNER_MODEL)
        use_cuda = torch.cuda.is_available()
        # Turing (sm_75) has no native bf16; fp16 is the fast, stable choice.
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
    """Test-only: the transcript is ASR_FAKE_TEXT spread evenly over the audio."""

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
    """Cloud DashScope non-realtime ASR (paraformer-v2)."""

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
        """Flatten paraformer-v2 word objects to {text, begin, end}."""
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
        """Parse paraformer-v2 transcription JSON into our schema."""
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
    """--resolve-backend: print the backend decision (probes only), no models."""
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
