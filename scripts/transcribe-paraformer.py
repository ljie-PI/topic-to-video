#!/usr/bin/env python3
"""
DashScope Paraformer-realtime-v2 ASR for Chinese audio.

Usage:
  python3 transcribe-paraformer.py <input.mp3> <output.json>

Requires:
  source .venv/bin/activate
  export DASHSCOPE_API_KEY="sk-..."

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

CRITICAL: sample_rate MUST match the actual audio sample rate.
  CosyVoice MP3  → 22050
  Generic 44.1k  → 44100 (or downsample first)
  16k recordings → 16000

This script auto-detects sample_rate via ffprobe.
"""
import json
import os
import subprocess
import sys

def print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def log(message: str) -> None:
    print(f'[transcribe] {message}', file=sys.stderr)


def detect_sample_rate(path: str) -> int:
    out = subprocess.run(
        [
            'ffprobe',
            '-v',
            'error',
            '-select_streams',
            'a:0',
            '-show_entries',
            'stream=sample_rate',
            '-of',
            'default=noprint_wrappers=1:nokey=1',
            path,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return int(out.stdout.strip())


def main() -> int:
    if len(sys.argv) != 3:
        message = 'Usage: transcribe-paraformer.py <input.mp3> <output.json>'
        log(message)
        print_json({'success': False, 'error': message})
        return 2

    try:
        from dashscope.audio.asr import Recognition
        import dashscope

        audio_path, out_path = sys.argv[1], sys.argv[2]
        if not os.path.isfile(audio_path):
            raise FileNotFoundError(f'not found: {audio_path}')

        api_key = os.environ.get('DASHSCOPE_API_KEY')
        if not api_key:
            raise EnvironmentError('DASHSCOPE_API_KEY env var not set')
        dashscope.api_key = api_key

        fmt = os.path.splitext(audio_path)[1][1:].lower() or 'mp3'
        sr = detect_sample_rate(audio_path)
        log(f'file={audio_path} format={fmt} sample_rate={sr}')

        rec = Recognition(
            model='paraformer-realtime-v2',
            format=fmt,
            sample_rate=sr,
            language_hints=['zh'],
            callback=None,
        )
        result = rec.call(audio_path)
        if result.status_code != 200:
            msg = getattr(result, 'message', '<no message>')
            raise RuntimeError(f'status_code={result.status_code} message={msg}')

        sentences = result.get_sentence() or []
        out = []
        for sentence in sentences:
            out.append(
                {
                    'begin': sentence.get('begin_time'),
                    'end': sentence.get('end_time'),
                    'text': sentence.get('text'),
                    'words': [
                        {'text': word.get('text'), 'begin': word.get('begin_time'), 'end': word.get('end_time')}
                        for word in (sentence.get('words') or [])
                    ],
                }
            )

        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

        total_words = sum(len(sentence['words']) for sentence in out)
        log(f'wrote {out_path}: {len(out)} sentences, {total_words} words')
        print_json(
            {
                'success': True,
                'output_path': os.path.abspath(out_path),
                'sentence_count': len(out),
                'word_count': total_words,
            }
        )
        return 0
    except Exception as exc:
        log(f'error: {exc}')
        print_json({'success': False, 'error': str(exc)})
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
