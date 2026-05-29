#!/usr/bin/env python3
"""
DashScope Paraformer-v2 (non-realtime) ASR for Chinese / mixed audio.

Usage:
  python3 transcribe-paraformer.py <input.mp3|http(s)://...|oss://...> <output.json>

Requires:
  source .venv/bin/activate
  export DASHSCOPE_API_KEY="sk-..."

Optional env:
  ASR_MODEL             default paraformer-v2; e.g. qwen3-asr-flash-filetrans
  ASR_LANGUAGE_HINTS    JSON array, default ["zh", "en"]

Output JSON shape:
  [
    {
      "begin": 0,           # ms
      "end": 60020,         # ms
      "text": "...",
      "words": [{"text": "为", "begin": 0, "end": 326}, ...]
    },
    ...
  ]

WHY NOT Whisper / npx hyperframes transcribe:
  - Hyperframes whisper download often fails with empty error
  - Whisper.cpp JSON output fragments multi-byte UTF-8 (中文乱码)
  - Paraformer-v2 returns clean UTF-8 + word-level timestamps
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
