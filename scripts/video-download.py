#!/usr/bin/env python3
"""用 yt-dlp 下载视频和 / 或字幕的封装。

用法：
  python3 video-download.py --url "https://youtube.com/watch?v=xxx" --output-dir downloads
  python3 video-download.py --url "https://bilibili.com/video/BVxxx" --subtitles-only
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cli
import harvest_manifest
import media

TOOL_NAME = 'video-download'

log = cli.make_logger(TOOL_NAME)


def parse_args() -> argparse.Namespace:
    parser = cli.JsonArgumentParser(TOOL_NAME, description='Download a video and subtitles with yt-dlp.')
    parser.add_argument('--url', required=True, help='Video URL to download')
    parser.add_argument('--output-dir', default=None, help='Output directory (default: pending manifest directory, or downloads)')
    parser.add_argument('--harvest-dir', default=None, help='harvest_page directory to update after download')
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
    args = parser.parse_args()
    if args.subtitles_only and args.harvest_dir:
        parser.error('--subtitles-only cannot be used with --harvest-dir')
    return args


def tail_text(text: str, limit: int = 4000) -> str:
    text = (text or '').strip()
    if len(text) <= limit:
        return text
    return text[-limit:]


def resolve_ytdlp_binary() -> str:
    override = (os.environ.get('YTDLP_BIN') or '').strip()
    if override:
        return override
    if sys.executable:
        exe_path = Path(sys.executable)
        candidates = (
            (exe_path.with_name('yt-dlp.exe'), exe_path.with_name('yt-dlp'))
            if os.name == 'nt'
            else (exe_path.with_name('yt-dlp'),)
        )
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
    return shutil.which('yt-dlp') or 'yt-dlp'


def detect_common_issue(output: str) -> Tuple[str, str]:
    lowered = (output or '').lower()
    if any(
        needle in lowered
        for needle in (
            'confirm you\u2019re not a bot',
            "confirm you're not a bot",
            'not a bot',
            'login_required',
        )
    ):
        return (
            'bot_check',
            'Video site blocked automated download with a bot check (PO Token or cookies required).',
        )
    if 'only images are available' in lowered or (
        'requested format is not available' in lowered and 'storyboard' in lowered
    ):
        return (
            'storyboard_only',
            'Only storyboard images are available; no playable video stream could be downloaded.',
        )
    checks: Tuple[Tuple[str, str, str], ...] = (
        ('unsupported url', 'invalid_url', 'Unsupported or invalid video URL.'),
        ('unsupported webpage', 'invalid_url', 'Unsupported or invalid video URL.'),
        ('video unavailable', 'unavailable', 'Video is unavailable or has been removed.'),
        ('this video is private', 'unavailable', 'Video is private and cannot be downloaded.'),
        ('sign in to confirm your age', 'login_required', 'Video is age-restricted and requires login.'),
        ('this video requires login', 'login_required', 'This video requires login.'),
        ('login required', 'login_required', 'This video requires login.'),
        ('too many requests', 'rate_limited', 'Rate limited by the video site. Please retry later.'),
        ('http error 429', 'rate_limited', 'Rate limited by the video site. Please retry later.'),
        ('requested format is not available', 'format_unavailable', 'Requested video format is not available.'),
        ('file is larger than max-filesize', 'max_filesize', 'Video exceeds the configured max file size limit.'),
        ('certificate verify failed', 'network_error', 'TLS certificate verification failed while contacting the video site.'),
        ('failed to download webpage', 'network_error', 'Failed to fetch video metadata. Check the URL or network access.'),
        ('unable to extract', 'extract_error', 'yt-dlp could not extract video information from this page.'),
    )
    for needle, kind, message in checks:
        if needle in lowered:
            return kind, message
    return 'unknown', tail_text(output) or 'yt-dlp failed with an unknown error.'


def build_command(args: argparse.Namespace, target_dir: Path) -> List[str]:
    command = [
        resolve_ytdlp_binary(),
        '--write-subs',
        '--write-auto-subs',
        '--convert-subs',
        'srt',
        '--sub-langs',
        'en,zh',
        '--output',
        str(target_dir / '%(id)s.%(ext)s'),
    ]
    if args.subtitles_only:
        command.append('--skip-download')
    else:
        command.extend(['--format', 'bv*+ba/b', '--max-filesize', args.max_file_size])
    command.append(args.url)
    return command


def _probe_staged_video(video_path: Path) -> Tuple[bool, Dict[str, Any]]:
    info: Dict[str, Any] = {
        'width': None,
        'height': None,
        'duration_seconds': None,
    }
    try:
        probed = media.probe(video_path)
    except media.MediaToolMissing:
        log('media probe binary not on PATH; falling back to non-empty file check')
        try:
            return video_path.stat().st_size > 0, info
        except OSError:
            return False, info
    except media.MediaProbeError as exc:
        log(str(exc))
        return False, info

    width = probed['width']
    height = probed['height']
    duration = probed['duration_seconds']
    valid_duration = duration if isinstance(duration, (int, float)) and duration > 0 else None
    info.update({
        'width': width,
        'height': height,
        'duration_seconds': valid_duration,
    })
    is_valid = bool(width and width > 0 and height and height > 0 and valid_duration is not None)
    if is_valid:
        log(f'  probed {video_path.name}: {width}x{height}')
    return is_valid, info


def main() -> int:
    args = parse_args()
    harvest_dir = Path(args.harvest_dir).expanduser().resolve() if args.harvest_dir else None

    try:
        if args.output_dir:
            output_dir = Path(args.output_dir).expanduser().resolve()
        elif harvest_dir is not None:
            pending = next(
                (item for item in harvest_manifest.load(harvest_dir)['pending_downloads'] if item.get('url') == args.url),
                None,
            )
            if pending is None or not pending.get('suggested_output_dir'):
                raise ValueError('--output-dir is required when the URL has no pending suggested_output_dir')
            output_dir = harvest_manifest.resolve(harvest_dir, pending['suggested_output_dir']).resolve()
        else:
            output_dir = Path('downloads').resolve()
        if output_dir.exists() and not output_dir.is_dir():
            raise ValueError(f'Output path is not a directory: {output_dir}')
        output_dir.mkdir(parents=True, exist_ok=True)

        timeout = 120 if args.subtitles_only else 600
        combined_output = ''
        returncode = 0
        final_files: List[str] = []
        videos_info: List[Dict[str, Any]] = []
        storyboard_error: Optional[str] = None

        log(f'Downloading {"subtitles only" if args.subtitles_only else "video+subtitles"} from {args.url} -> {output_dir}')
        with tempfile.TemporaryDirectory(prefix='.ytdlp-', dir=output_dir) as raw_temp_dir:
            temp_dir = Path(raw_temp_dir)
            command = build_command(args, temp_dir)
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            combined_output = '\n'.join(part for part in [completed.stdout, completed.stderr] if part)
            returncode = completed.returncode

            if returncode == 0:
                staged_files = sorted((p for p in temp_dir.iterdir() if p.is_file()), key=lambda p: p.name)
                probed_by_name: Dict[str, Dict[str, Any]] = {}
                valid_video_names: set[str] = set()

                if not args.subtitles_only:
                    staged_videos = [p for p in staged_files if p.suffix.lower() in harvest_manifest.VIDEO_EXTS]
                    for video_file in staged_videos:
                        is_valid, info = _probe_staged_video(video_file)
                        probed_by_name[video_file.name] = info
                        if is_valid:
                            valid_video_names.add(video_file.name)
                    if not valid_video_names:
                        if any(p.suffix.lower() == '.mhtml' for p in staged_files):
                            storyboard_error = (
                                'yt-dlp downloaded only storyboard files (.mhtml) without a playable video stream.'
                            )
                        elif staged_videos:
                            storyboard_error = (
                                'yt-dlp produced an unplayable or empty video file without a valid video stream.'
                            )
                        else:
                            storyboard_error = (
                                'yt-dlp finished without producing a playable video file.'
                            )

                if storyboard_error is None:
                    for src in staged_files:
                        if (
                            not args.subtitles_only
                            and src.suffix.lower() in harvest_manifest.VIDEO_EXTS
                            and src.name not in valid_video_names
                        ):
                            continue
                        dest = (output_dir / src.name).resolve()
                        os.replace(src, dest)
                        final_path = str(dest)
                        final_files.append(final_path)
                        if not args.subtitles_only and src.name in valid_video_names:
                            videos_info.append({
                                'path': final_path,
                                **probed_by_name[src.name],
                            })

        if returncode != 0:
            failure_kind, error_message = detect_common_issue(combined_output)
            log(f'yt-dlp failed ({failure_kind}): {error_message}')
            cli.print_json({'success': False, 'failure_kind': failure_kind, 'error': error_message})
            return 1

        if storyboard_error is not None:
            log(f'yt-dlp failed (storyboard_only): {storyboard_error}')
            cli.print_json({
                'success': False,
                'failure_kind': 'storyboard_only',
                'error': storyboard_error,
            })
            return 1

        log(f'Download complete ({len(final_files)} file(s))')
        result = {
            'success': True,
            'output_dir': str(output_dir),
            'files': final_files,
            'videos': videos_info,
            'stdout_tail': tail_text(combined_output),
        }
        if harvest_dir is not None:
            harvest_manifest.apply_download(harvest_dir, args.url, result)
            result['manifest_updated'] = True
        cli.print_json(result)
        return 0
    except FileNotFoundError:
        log('yt-dlp is not installed or not available on PATH.')
        cli.print_json({
            'success': False,
            'failure_kind': 'missing_binary',
            'error': 'yt-dlp is not installed or not available on PATH.',
        })
        return 1
    except subprocess.TimeoutExpired as exc:
        output = '\n'.join(
            part.decode('utf-8', errors='replace') if isinstance(part, bytes) else part
            for part in [exc.stdout, exc.stderr]
            if part
        )
        message = f'yt-dlp timed out after {exc.timeout} seconds. {tail_text(output)}'.strip()
        log(message)
        cli.print_json({'success': False, 'failure_kind': 'timeout', 'error': message})
        return 1
    except Exception as exc:
        log(f'error: {exc}')
        cli.print_json({'success': False, 'failure_kind': 'unknown', 'error': str(exc)})
        return 1


if __name__ == '__main__':
    raise SystemExit(cli.run(main, TOOL_NAME))
