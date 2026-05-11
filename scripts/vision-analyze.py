#!/usr/bin/env python3
"""Model-agnostic vision analysis CLI.

Two modes, selected by environment:

  Mode 1 — Explicit VLM (when VLM_API_KEY is set):
    Calls any OpenAI-compatible /chat/completions endpoint.
    Required env: VLM_API_KEY, VLM_BASE_URL, VLM_MODEL.
    Example (Qwen-VL via DashScope OpenAI-compatible endpoint):
      export VLM_API_KEY="$DASHSCOPE_API_KEY"
      export VLM_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
      export VLM_MODEL="qwen-vl-max"

  Mode 2 — Delegate to agent (when VLM_API_KEY is unset):
    Emits a `delegate_to_agent` directive (no API call, no base64 in stdout).
    The calling agent is expected to use its own `view` tool on each local
    image path returned by the script, then answer the prompt using its own
    vision-capable model.

Usage:
  python3 vision-analyze.py --prompt "Describe content and rate quality 1-10" \
      --images frame_001.jpg frame_002.jpg https://example.com/img.jpg \
      [--model qwen-vl-max] [--detail low|high|auto]

Output convention:
  stdout: single JSON object
    Mode 1 success: {"success": true, "mode": "vlm", "analysis": "...", "model": "...", "image_count": N}
    Mode 2:         {"success": true, "mode": "delegate_to_agent", "instruction": "...", "prompt": "...", "images": {"local": [...], "remote": [...]}, "image_count": N}
    Error:          {"success": false, "error": "..."}
  stderr: human-readable progress lines prefixed with `[vision-analyze]`
  Exit codes: 0 success, 1 runtime error, 2 invalid arguments
"""

import argparse
import base64
import json
import mimetypes
import os
import sys
from pathlib import Path
from urllib import error as urlerror
from urllib import request as urlrequest
from urllib.parse import urlparse

MAX_IMAGES = 10
DETAIL_LEVELS = ('low', 'high', 'auto')
TOOL_NAME = 'vision-analyze'
HTTP_TIMEOUT_SECONDS = 60

DELEGATE_INSTRUCTION = (
    'No explicit vision model is configured (VLM_API_KEY is unset). '
    'To analyze these images, use your own `view` tool on each local path in '
    '`images.local`, then answer `prompt` using your own vision-capable model. '
    'For URLs in `images.remote`, use `web_fetch` with raw=true to retrieve '
    'the image bytes, or skip if not reachable.'
)


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        log(f'Argument error: {message}')
        print(json.dumps({'success': False, 'error': message}, ensure_ascii=False))
        self.exit(2)


def log(message: str) -> None:
    print(f'[{TOOL_NAME}] {message}', file=sys.stderr)


def parse_args() -> argparse.Namespace:
    parser = ArgumentParser(description='Analyze images with an OpenAI-compatible vision model or delegate to the main agent.')
    parser.add_argument('--prompt', required=True, help='Analysis prompt or question.')
    parser.add_argument('--images', required=True, nargs='+', help='One or more local image paths or http/https URLs.')
    parser.add_argument(
        '--model',
        default=None,
        help='Model name override for Mode 1. If omitted, falls back to VLM_MODEL env var. Ignored in Mode 2.',
    )
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


def resolve_local_path(image_path: str) -> str:
    path = Path(image_path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f'Image file not found: {image_path}')
    return str(path.resolve())


def fail(message: str, exit_code: int = 1) -> None:
    log(message)
    print(json.dumps({'success': False, 'error': message}, ensure_ascii=False))
    raise SystemExit(exit_code)


def split_images(images):
    local, remote = [], []
    for img in images:
        if is_remote_image(img):
            remote.append(img)
        else:
            local.append(resolve_local_path(img))
    return local, remote


def build_vlm_content(images, prompt, detail):
    content = []
    for img in images:
        url = img if is_remote_image(img) else local_image_to_data_url(img)
        content.append({'type': 'image_url', 'image_url': {'url': url, 'detail': detail}})
    content.append({'type': 'text', 'text': prompt})
    return content


def call_openai_compatible_vlm(api_key, base_url, model, content, timeout):
    endpoint = base_url.rstrip('/') + '/chat/completions'
    payload = json.dumps({
        'model': model,
        'messages': [{'role': 'user', 'content': content}],
    }).encode('utf-8')

    req = urlrequest.Request(
        endpoint,
        data=payload,
        method='POST',
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
    )

    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode('utf-8', errors='replace')
    except urlerror.HTTPError as exc:
        body = exc.read().decode('utf-8', errors='replace') if exc.fp else ''
        raise RuntimeError(f'HTTP {exc.code} from {endpoint}: {body[:500]}')
    except urlerror.URLError as exc:
        raise RuntimeError(f'Network error calling {endpoint}: {exc.reason}')

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f'Non-JSON response from {endpoint}: {exc}; body={raw[:500]}')

    choices = data.get('choices') or []
    if not choices:
        raise RuntimeError(f'Response contained no choices: {raw[:500]}')

    message = choices[0].get('message') or {}
    text = message.get('content')

    if isinstance(text, list):
        parts = []
        for part in text:
            if isinstance(part, dict) and part.get('type') == 'text':
                parts.append(part.get('text', ''))
            elif isinstance(part, str):
                parts.append(part)
        text = ''.join(parts)

    if not isinstance(text, str) or not text.strip():
        raise RuntimeError(f'Response contained empty content: {raw[:500]}')

    return text


def run_mode_vlm(args, api_key):
    base_url = os.environ.get('VLM_BASE_URL')
    model = args.model or os.environ.get('VLM_MODEL')
    missing = []
    if not base_url:
        missing.append('VLM_BASE_URL')
    if not model:
        missing.append('VLM_MODEL (or pass --model)')
    if missing:
        fail(f'VLM_API_KEY is set but missing required config: {", ".join(missing)}')

    log(f'Mode: vlm; model={model}; base_url={base_url}; images={len(args.images)}')

    content = build_vlm_content(args.images, args.prompt, args.detail)
    analysis = call_openai_compatible_vlm(api_key, base_url, model, content, HTTP_TIMEOUT_SECONDS)

    log('Vision analysis completed')
    print(json.dumps(
        {
            'success': True,
            'mode': 'vlm',
            'analysis': analysis,
            'model': model,
            'image_count': len(args.images),
        },
        ensure_ascii=False,
    ))


def run_mode_delegate(args):
    local, remote = split_images(args.images)
    log(f'Mode: delegate_to_agent; local={len(local)} remote={len(remote)}')
    print(json.dumps(
        {
            'success': True,
            'mode': 'delegate_to_agent',
            'instruction': DELEGATE_INSTRUCTION,
            'prompt': args.prompt,
            'images': {'local': local, 'remote': remote},
            'image_count': len(args.images),
        },
        ensure_ascii=False,
    ))


def main() -> None:
    args = parse_args()

    if len(args.images) > MAX_IMAGES:
        fail(f'Max {MAX_IMAGES} images are allowed per request (got {len(args.images)})')

    api_key = os.environ.get('VLM_API_KEY')

    try:
        if api_key:
            run_mode_vlm(args, api_key)
        else:
            run_mode_delegate(args)
    except SystemExit:
        raise
    except FileNotFoundError as exc:
        fail(str(exc))
    except Exception as exc:
        fail(str(exc))


if __name__ == '__main__':
    main()
