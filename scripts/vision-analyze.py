#!/usr/bin/env python3
"""DashScope multimodal vision analysis CLI.

Usage:
  python3 vision-analyze.py --prompt "Describe what's in these images" --images frame_001.jpg frame_002.jpg
  python3 vision-analyze.py --prompt "Rate image quality 1-10" --images https://example.com/img.jpg --model qwen-vl-plus

Requires:
  export DASHSCOPE_API_KEY="sk-..."
"""

import argparse
import base64
import json
import mimetypes
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

MAX_IMAGES = 10
DEFAULT_MODEL = 'qwen-vl-max'
DETAIL_LEVELS = ('low', 'high', 'auto')
TOOL_NAME = 'vision-analyze'


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        log(f'Argument error: {message}')
        print(json.dumps({'success': False, 'error': message}, ensure_ascii=False))
        self.exit(2)


def log(message: str) -> None:
    print(f'[{TOOL_NAME}] {message}', file=sys.stderr)


def parse_args() -> argparse.Namespace:
    parser = ArgumentParser(description='Analyze one or more images with DashScope Qwen-VL models.')
    parser.add_argument('--prompt', required=True, help='Analysis prompt or question.')
    parser.add_argument('--images', required=True, nargs='+', help='One or more local image paths or http/https URLs.')
    parser.add_argument('--model', default=DEFAULT_MODEL, help=f'Model name (default: {DEFAULT_MODEL}).')
    parser.add_argument(
        '--detail',
        default='low',
        choices=DETAIL_LEVELS,
        help='Image detail level: low, high, or auto (default: low).',
    )
    return parser.parse_args()


def is_remote_image(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {'http', 'https'} and bool(parsed.netloc)


def guess_mime_type(path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(path.name)
    if mime_type and mime_type.startswith('image/'):
        return mime_type

    suffix = path.suffix.lower()
    if suffix in {'.jpg', '.jpeg'}:
        return 'image/jpeg'
    if suffix == '.png':
        return 'image/png'
    if suffix == '.webp':
        return 'image/webp'
    if suffix == '.gif':
        return 'image/gif'
    if suffix == '.bmp':
        return 'image/bmp'
    return 'image/jpeg'


def local_image_to_data_url(image_path: str) -> str:
    path = Path(image_path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f'Image file not found: {image_path}')

    encoded = base64.b64encode(path.read_bytes()).decode('ascii')
    mime_type = guess_mime_type(path)
    return f'data:{mime_type};base64,{encoded}'


def normalize_image_source(image: str) -> str:
    if is_remote_image(image):
        return image
    return local_image_to_data_url(image)


def get_response_value(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def extract_analysis_text(response) -> str:
    output = get_response_value(response, 'output')
    choices = get_response_value(output, 'choices') or []
    if not choices:
        raise ValueError('DashScope response did not contain any choices')

    message = get_response_value(choices[0], 'message')
    content = get_response_value(message, 'content') or []
    if not content:
        raise ValueError('DashScope response did not contain any content')

    first_item = content[0]
    text = get_response_value(first_item, 'text')
    if not text:
        raise ValueError('DashScope response did not contain text output')
    return text


def fail(message: str, exit_code: int = 1) -> None:
    log(message)
    print(json.dumps({'success': False, 'error': message}, ensure_ascii=False))
    raise SystemExit(exit_code)


def main() -> None:
    args = parse_args()

    if len(args.images) > MAX_IMAGES:
        fail(f'Max {MAX_IMAGES} images are allowed per request')

    api_key = os.environ.get('DASHSCOPE_API_KEY')
    if not api_key:
        fail('DASHSCOPE_API_KEY env var not set')

    try:
        import dashscope
        from dashscope import MultiModalConversation

        dashscope.api_key = api_key

        log(f'Analyzing {len(args.images)} images with {args.model}...')
        content = [{'image': normalize_image_source(image)} for image in args.images]
        content.append({'text': args.prompt})

        response = MultiModalConversation.call(
            model=args.model,
            messages=[{'role': 'user', 'content': content}],
            image_detail=args.detail,
        )

        status_code = get_response_value(response, 'status_code', 200)
        if status_code != 200:
            message = get_response_value(response, 'message', 'DashScope request failed')
            fail(f'status_code={status_code} message={message}')

        analysis = extract_analysis_text(response)
        log('Vision analysis completed')
        print(
            json.dumps(
                {
                    'success': True,
                    'analysis': analysis,
                    'model': args.model,
                    'image_count': len(args.images),
                },
                ensure_ascii=False,
            )
        )
    except SystemExit:
        raise
    except Exception as exc:
        fail(str(exc))


if __name__ == '__main__':
    main()
