#!/usr/bin/env python3
"""
DashScope 非实时语音识别 (paraformer-v2) for Chinese / mixed audio.

参考文档:
  https://help.aliyun.com/zh/model-studio/non-realtime-speech-recognition-user-guide

接口模式 — HTTP REST 异步任务 (OpenAI 兼容风格的 REST 调用 + task_id 轮询):
  POST  /api/v1/services/audio/asr/transcription   (X-DashScope-Async: enable)
        → task_id
  GET   /api/v1/tasks/{task_id}                     轮询直到 SUCCEEDED / FAILED
  GET   transcription_url                           下载词级时间戳 JSON

为什么仍然 import dashscope SDK 而不是裸 `requests`:
  - 文档要求 file_url 是公网 URL；narration.mp3 是本地文件，必须先上传。
  - dashscope SDK 暴露了 `OssUtils.upload(model, file_path, api_key)`，
    会向 DashScope 申请上传凭证并把本地文件 POST 到对应 OSS bucket，
    返回 `oss://...` URL — paraformer-v2 的 file_urls 直接接受。
  - `Transcription.async_call() / wait() / fetch()` 是上述 REST 流程的
    薄封装；裸 requests 实现会需要复刻签名 / 轮询 / OSS 凭证刷新等
    协议细节，得不偿失。
  - 转写结果的下载用裸 `requests`（transcription_url 是公网 JSON）。

Usage:
  python3 transcribe-paraformer.py <input.mp3|http(s)://...|oss://...> <output.json>

可选环境变量:
  DASHSCOPE_API_KEY     (必填)
  ASR_MODEL             默认 paraformer-v2；其它可选 qwen3-asr-flash-filetrans
  ASR_LANGUAGE_HINTS    JSON 数组，默认 ["zh", "en"]

Output JSON shape (保持与既有下游兼容):
  [
    {
      "begin": 0,           # ms
      "end": 60020,         # ms
      "text": "...",
      "words": [{"text": "为", "begin": 0, "end": 326}, ...]
    },
    ...
  ]

WHY 切到非实时 paraformer-v2 (而不是 paraformer-realtime-v2):
  - 实时模型上限 ~5min，且 SDK 必须显式传 format / sample_rate，否则报
    `status_code=44 sample rate ... not equals with real ...`。
  - 非实时 paraformer-v2 / qwen3-asr-flash-filetrans 走 file-based REST 异步
    任务，自动识别 format 与 sample rate，单文件支持 ≤12h、≤2GB。
  - 默认开启 ITN（inverse text normalization），narration 里的"一万六千二百
    八十八"会被自动归一化成 "16288"。
"""
from __future__ import annotations

import json
import os
import sys
from http import HTTPStatus

import requests


def print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def log(message: str) -> None:
    print(f'[transcribe] {message}', file=sys.stderr)


def parse_language_hints() -> list[str]:
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


def convert_words(raw_words: list[dict]) -> list[dict]:
    """Flatten paraformer-v2 word objects to {text, begin, end}.

    paraformer-v2 returns per-word `punctuation` separately; concatenate it
    onto the word text so the downstream caption builder sees a single token
    that already includes its trailing punctuation.
    """
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


def parse_transcription_payload(payload: dict) -> list[dict]:
    """Parse paraformer-v2 transcription JSON into our schema.

    paraformer-v2 result shape:
      {
        "transcripts": [
          {
            "channel_id": 0,
            "content_duration_in_milliseconds": ...,
            "text": "全文 ...",
            "sentences": [
              {
                "begin_time": 0, "end_time": 1000, "text": "...",
                "words": [
                  {"begin_time": 0, "end_time": 200, "text": "为",
                   "punctuation": ""},
                  ...
                ]
              },
              ...
            ]
          },
          ...
        ]
      }
    """
    sentences = []
    for transcript in payload.get('transcripts') or []:
        for sentence in transcript.get('sentences') or []:
            sentences.append(
                {
                    'begin': sentence.get('begin_time'),
                    'end': sentence.get('end_time'),
                    'text': sentence.get('text'),
                    'words': convert_words(sentence.get('words') or []),
                }
            )
    return sentences


def main() -> int:
    if len(sys.argv) != 3:
        message = 'Usage: transcribe-paraformer.py <input.mp3|http(s)://...|oss://...> <output.json>'
        log(message)
        print_json({'success': False, 'error': message})
        return 2

    try:
        from dashscope.audio.asr import Transcription
        from dashscope.utils.oss_utils import OssUtils
        import dashscope

        audio_arg, out_path = sys.argv[1], sys.argv[2]

        is_remote = (
            audio_arg.startswith('http://')
            or audio_arg.startswith('https://')
            or audio_arg.startswith('oss://')
        )
        if not is_remote and not os.path.isfile(audio_arg):
            raise FileNotFoundError(f'not found: {audio_arg}')

        api_key = os.environ.get('DASHSCOPE_API_KEY')
        if not api_key:
            raise EnvironmentError('DASHSCOPE_API_KEY env var not set')
        dashscope.api_key = api_key

        model = os.environ.get('ASR_MODEL', 'paraformer-v2')
        language_hints = parse_language_hints()

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

        log(f'submit async transcription: model={model} '
            f'language_hints={language_hints}')
        submit_response = Transcription.async_call(
            model=model,
            file_urls=[file_url],
            language_hints=language_hints,
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
        transcript_payload = transcript_response.json()

        sentences = parse_transcription_payload(transcript_payload)

        out_dir = os.path.dirname(os.path.abspath(out_path))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(sentences, f, ensure_ascii=False, indent=2)

        total_words = sum(len(sentence['words']) for sentence in sentences)
        log(f'wrote {out_path}: {len(sentences)} sentences, {total_words} words')
        print_json(
            {
                'success': True,
                'output_path': os.path.abspath(out_path),
                'sentence_count': len(sentences),
                'word_count': total_words,
                'model': model,
                'task_id': task_id,
            }
        )
        return 0
    except Exception as exc:
        log(f'error: {exc}')
        print_json({'success': False, 'error': str(exc)})
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
