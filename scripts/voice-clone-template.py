#!/usr/bin/env python3
"""
CosyVoice TTS via Aliyun DashScope — TEMPLATE.
Copy this file to your project, replace input_text, run.

Prerequisites:
  source .venv/bin/activate
  export DASHSCOPE_API_KEY="sk-..."

Output: {output_dir}/narration.mp3 (sample rate 22050)
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Use the model + voice from voice_clone.py. Both must be the SAME pair that
# was registered when the voice was cloned.
MODEL = "cosyvoice-v3.5-plus"
VOICE = "cosyvoice-v3.5-plus-myvoice-1b98aef0e50242ad9d23ae69bb3511f7"

# === REPLACE THIS ===
input_text = """
在这里粘贴中文旁白脚本。

每段之间空一行作为自然停顿。
数字写中文（二零二六、一百五十）。
英文专有名词保留原样（Anthropic、Claude Code）。

最后一段可以是 CTA：点赞、关注、收藏，下期见。
"""
# ====================


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
    parser = JsonArgumentParser(description='Synthesize narration audio with CosyVoice.')
    parser.add_argument(
        '--output-dir',
        default='.',
        help='Directory for narration.mp3 output (default: current directory)',
    )
    return parser.parse_args()


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


def main() -> int:
    try:
        args = parse_args()
        from dashscope.audio.tts_v2 import SpeechSynthesizer
        import dashscope

        api_key = os.environ.get('DASHSCOPE_API_KEY')
        if not api_key:
            raise EnvironmentError('DASHSCOPE_API_KEY env var not set')

        dashscope.api_key = api_key
        dashscope.base_websocket_api_url = 'wss://dashscope.aliyuncs.com/api-ws/v1/inference'

        output_dir = Path(args.output_dir).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = (output_dir / 'narration.mp3').resolve()

        log(f'synthesizing narration to {output_path}')
        synthesizer = SpeechSynthesizer(model=MODEL, voice=VOICE, speech_rate=1.5)
        audio = synthesizer.call(input_text)

        log(
            'requestId='
            f'{synthesizer.get_last_request_id()}, '
            f'first_packet_delay={synthesizer.get_first_package_delay()}ms'
        )

        output_path.write_bytes(audio)
        duration_s = detect_duration_seconds(output_path)
        log(f'wrote {output_path}')
        print_json({'success': True, 'output_path': str(output_path), 'duration_s': duration_s})
        return 0
    except SystemExit:
        raise
    except Exception as exc:
        log(f'error: {exc}')
        print_json({'success': False, 'error': str(exc)})
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
