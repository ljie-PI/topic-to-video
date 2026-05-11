#!/usr/bin/env python3
"""yt-dlp wrapper for downloading a video and/or subtitles.

Usage:
  python3 video-download.py --url "https://youtube.com/watch?v=xxx" --output-dir downloads
  python3 video-download.py --url "https://bilibili.com/video/BVxxx" --subtitles-only
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

TOOL_NAME = 'video-download'


def log(message: str) -> None:
    print(f'[{TOOL_NAME}] {message}', file=sys.stderr)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Download a video and subtitles with yt-dlp.')
    parser.add_argument('--url', required=True, help='Video URL to download')
    parser.add_argument('--output-dir', default='downloads', help='Output directory (default: downloads)')
    parser.add_argument(
        '--subtitles-only',
        action='store_true',
        help='Only download subtitles and skip the video file',
    )
    parser.add_argument(
        '--max-file-size',
        default='200M',
        help='Max video size for yt-dlp (default: 200M)',
    )
    return parser.parse_args()


def tail_text(text: str, limit: int = 4000) -> str:
    text = (text or '').strip()
    if len(text) <= limit:
        return text
    return text[-limit:]


def detect_common_issue(output: str) -> str:
    lowered = output.lower()
    checks = [
        ('unsupported url', 'Unsupported or invalid video URL.'),
        ('unsupported webpage', 'Unsupported or invalid video URL.'),
        ('video unavailable', 'Video is unavailable or has been removed.'),
        ('this video is private', 'Video is private and cannot be downloaded.'),
        ('sign in to confirm your age', 'Video is age-restricted and requires login.'),
        ('login required', 'This video requires login.'),
        ('too many requests', 'Rate limited by the video site. Please retry later.'),
        ('http error 429', 'Rate limited by the video site. Please retry later.'),
        ('failed to download webpage', 'Failed to fetch video metadata. Check the URL or network access.'),
        ('unable to extract', 'yt-dlp could not extract video information from this page.'),
        ('requested format is not available', 'Requested video format is not available.'),
        ('file is larger than max-filesize', 'Video exceeds the configured max file size limit.'),
        ('certificate verify failed', 'TLS certificate verification failed while contacting the video site.'),
    ]
    for needle, message in checks:
        if needle in lowered:
            return message
    return tail_text(output) or 'yt-dlp failed with an unknown error.'


def collect_changed_files(output_dir: Path, before_stats: Dict[Path, int]) -> List[str]:
    files: List[str] = []
    for path in sorted(p.resolve() for p in output_dir.iterdir() if p.is_file()):
        mtime_ns = path.stat().st_mtime_ns
        if path not in before_stats or before_stats[path] != mtime_ns:
            files.append(str(path))
    return files


def build_command(args: argparse.Namespace, output_dir: Path) -> List[str]:
    command = [
        'yt-dlp',
        '--write-subs',
        '--write-auto-subs',
        '--sub-langs',
        'en,zh',
        '--output',
        str(output_dir / '%(id)s.%(ext)s'),
    ]
    if args.subtitles_only:
        command.append('--skip-download')
    else:
        command.extend(['--max-filesize', args.max_file_size])
    command.append(args.url)
    return command


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).expanduser().resolve()

    try:
        if output_dir.exists() and not output_dir.is_dir():
            raise ValueError(f'Output path is not a directory: {output_dir}')
        output_dir.mkdir(parents=True, exist_ok=True)

        before_stats = {
            path.resolve(): path.stat().st_mtime_ns
            for path in output_dir.iterdir()
            if path.is_file()
        }
        command = build_command(args, output_dir)
        timeout = 120 if args.subtitles_only else 600

        log(f'Downloading {"subtitles only" if args.subtitles_only else "video+subtitles"} from {args.url} -> {output_dir}')
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        combined_output = '\n'.join(part for part in [completed.stdout, completed.stderr] if part)

        if completed.returncode != 0:
            error_message = detect_common_issue(combined_output)
            log(f'yt-dlp failed: {error_message}')
            print(json.dumps({'success': False, 'error': error_message}, ensure_ascii=False))
            return 1

        files = collect_changed_files(output_dir, before_stats)
        if not files:
            files = [str(path.resolve()) for path in sorted(output_dir.iterdir()) if path.is_file()]
        log(f'Download complete ({len(files)} file(s))')
        result = {
            'success': True,
            'output_dir': str(output_dir),
            'files': files,
            'stdout_tail': tail_text(combined_output),
        }
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except FileNotFoundError:
        log('yt-dlp is not installed or not available on PATH.')
        print(json.dumps({'success': False, 'error': 'yt-dlp is not installed or not available on PATH.'}, ensure_ascii=False))
        return 1
    except subprocess.TimeoutExpired as exc:
        output = '\n'.join(
            part.decode('utf-8', errors='replace') if isinstance(part, bytes) else part
            for part in [exc.stdout, exc.stderr]
            if part
        )
        message = f'yt-dlp timed out after {exc.timeout} seconds. {tail_text(output)}'.strip()
        log(message)
        print(
            json.dumps(
                {'success': False, 'error': message},
                ensure_ascii=False,
            )
        )
        return 1
    except Exception as exc:
        log(f'error: {exc}')
        print(json.dumps({'success': False, 'error': str(exc)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    sys.exit(main())
