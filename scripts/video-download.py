#!/usr/bin/env python3
"""用 yt-dlp 下载视频和 / 或字幕的封装。

用法：
  python3 video-download.py --url "https://youtube.com/watch?v=xxx" --output-dir downloads
  python3 video-download.py --url "https://bilibili.com/video/BVxxx" --subtitles-only
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib import request as urlrequest
from urllib.parse import urlparse

import chrome_cdp
import cli
import harvest_manifest
import media

TOOL_NAME = 'video-download'
DEFAULT_CDP_URL = 'http://localhost:9222'
COOKIE_DOMAIN_SUFFIXES = (
    'youtube.com',
    'google.com',
    'bilibili.com',
)

log = cli.make_logger(TOOL_NAME)


def parse_args() -> argparse.Namespace:
    parser = cli.JsonArgumentParser(TOOL_NAME, description='Download a video and subtitles with yt-dlp.')
    parser.add_argument('--url', required=True, help='Video URL to download')
    parser.add_argument('--output-dir', default=None, help='Output directory (default: pending manifest directory, or downloads)')
    parser.add_argument('--harvest-dir', default=None, help='harvest_page directory to update after download')
    parser.add_argument(
        '--profile-dir',
        default=None,
        help='Shared Chrome profile dir to inherit login cookies over CDP (auto-inferred from --harvest-dir when omitted).',
    )
    parser.add_argument('--cdp-url', default=None, help=f'CDP endpoint (default {DEFAULT_CDP_URL}).')
    parser.add_argument('--chrome-path', default=None, help='Path to Chrome executable when launching for profile cookies.')
    parser.add_argument('--headless', default=None, choices=('auto', 'on', 'off'), help='Chrome headless mode when launching for cookies.')
    parser.add_argument('--no-sandbox', action='store_true', default=None, help='Pass --no-sandbox when launching Chrome.')
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
    args.explicit_cdp_url = args.cdp_url
    args.cdp_url = args.cdp_url or DEFAULT_CDP_URL
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


def build_format_selector(max_file_size: str) -> str:
    size = (max_file_size or '').strip()
    if size:
        return (
            f'bv*[height<=1080][filesize<={size}]+ba/'
            f'bv*[height<=1080][filesize_approx<={size}]+ba/'
            f'b[height<=1080][filesize<={size}]/'
            f'bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b'
        )
    return 'bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b'


def build_command(args: argparse.Namespace, target_dir: Path, cookie_file: Optional[Path] = None) -> List[str]:
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
    if cookie_file is not None:
        command.extend(['--cookies', str(cookie_file)])
    if args.subtitles_only:
        command.append('--skip-download')
    else:
        command.extend(['--format', build_format_selector(args.max_file_size), '--max-filesize', args.max_file_size])
    command.append(args.url)
    return command


def build_ytdlp_env() -> Dict[str, str]:
    """确保本地回环地址（如 127.0.0.1:4416 的 bgutil PO Token HTTP 服务）不走代理。"""
    env = dict(os.environ)
    raw = env.get('NO_PROXY') or env.get('no_proxy') or ''
    items = [item.strip() for item in raw.split(',') if item.strip()]
    existing = {item.lower() for item in items}
    for host in ('127.0.0.1', 'localhost', '::1'):
        if host not in existing:
            items.append(host)
    merged = ','.join(items)
    env['NO_PROXY'] = merged
    env['no_proxy'] = merged
    return env


def resolve_profile_dir(explicit: Optional[str], harvest_dir: Optional[Path]) -> Optional[Path]:
    """显式 `--profile-dir` 优先；否则从 `{work_dir}/{topic}/harvest_page` 推断 `{work_dir}/chrome_profile`。"""
    if explicit:
        return Path(explicit).expanduser().resolve()
    if harvest_dir is not None:
        for base in (harvest_dir, harvest_dir.resolve()):
            candidate = base.parent.parent / 'chrome_profile'
            if candidate.exists():
                return candidate.resolve()
    return None


def _relevant_cookie(domain: str, url_host: str) -> bool:
    clean = domain.lstrip('.').lower()
    if not clean:
        return False
    if url_host and (url_host == clean or url_host.endswith('.' + clean) or clean.endswith('.' + url_host)):
        return True
    return any(clean == suffix or clean.endswith('.' + suffix) for suffix in COOKIE_DOMAIN_SUFFIXES)


def write_netscape_cookies(cookies: Sequence[Dict[str, Any]], dest: Path, url: str) -> int:
    url_host = (urlparse(url).hostname or '').lower()
    kept = [
        c for c in cookies
        if isinstance(c, dict) and c.get('name') and c.get('domain') and _relevant_cookie(str(c['domain']), url_host)
    ]
    if not kept:
        return 0
    lines = ['# Netscape HTTP Cookie File']
    for cookie in kept:
        domain = str(cookie['domain']).replace('\t', ' ').replace('\n', '').replace('\r', '')
        include_sub = 'TRUE' if domain.startswith('.') else 'FALSE'
        path = str(cookie.get('path') or '/').replace('\t', ' ').replace('\n', '').replace('\r', '')
        secure = 'TRUE' if cookie.get('secure') else 'FALSE'
        raw_exp = cookie.get('expires')
        expires = int(raw_exp) if isinstance(raw_exp, (int, float)) and raw_exp > 0 else 0
        name = str(cookie['name']).replace('\t', ' ').replace('\n', '').replace('\r', '')
        value = str(cookie.get('value') or '').replace('\t', ' ').replace('\n', '').replace('\r', '')
        lines.append(f'{domain}\t{include_sub}\t{path}\t{secure}\t{expires}\t{name}\t{value}')
    fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as handle:
        handle.write('\n'.join(lines) + '\n')
    return len(kept)


def _read_cdp_ws_cookies(cdp_url: str) -> List[Dict[str, Any]]:
    """直接经浏览器级 CDP WebSocket 调 Storage.getCookies（避开 Chrome 158 弹出框导致 Playwright connect_over_cdp 失败）。"""
    import websockets

    host = (urlparse(cdp_url).hostname or '').lower()
    opener = (
        urlrequest.build_opener(urlrequest.ProxyHandler({}))
        if host in {'127.0.0.1', 'localhost', '::1'}
        else urlrequest.build_opener()
    )
    with opener.open(f'{cdp_url.rstrip("/")}/json/version', timeout=3.0) as resp:
        ws_url = json.loads(resp.read().decode('utf-8'))['webSocketDebuggerUrl']

    async def _fetch() -> List[Dict[str, Any]]:
        async with websockets.connect(ws_url, proxy=None, open_timeout=5.0, close_timeout=2.0) as ws:
            await ws.send(json.dumps({'id': 1, 'method': 'Storage.getCookies'}))
            while True:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))
                if msg.get('id') == 1:
                    return msg.get('result', {}).get('cookies', []) or []

    return asyncio.run(_fetch())


def export_cdp_cookies(args: argparse.Namespace, harvest_dir: Optional[Path], dest: Path) -> Optional[Path]:
    """从共享 `chrome_profile`（或已就绪 CDP）导出临时 Netscape cookies。"""
    profile_dir = resolve_profile_dir(args.profile_dir, harvest_dir)
    if profile_dir is None and args.explicit_cdp_url is None:
        return None
    cdp_up = chrome_cdp.cdp_ready(args.cdp_url)
    if not cdp_up and profile_dir is None:
        return None
    if not cdp_up and profile_dir is not None and args.profile_dir is None:
        cookie_db = profile_dir / 'Default' / 'Cookies'
        if not cookie_db.is_file():
            return None

    launched_proc: Optional[subprocess.Popen] = None
    try:
        chrome_cdp.ensure_loopback_no_proxy()
        if not cdp_up:
            executable = chrome_cdp.find_chrome(args.chrome_path)
            if not executable:
                raise RuntimeError('System Chrome not found')
            launched_proc = chrome_cdp._launch_chrome(
                executable,
                args.cdp_url,
                profile_dir.resolve(),
                headless=args.headless if args.headless is not None else 'on',
                window_size='1280,720',
                no_sandbox=args.no_sandbox,
            )
            chrome_cdp._wait_for_cdp(args.cdp_url, profile_dir.resolve(), launched_proc)
        raw_cookies = _read_cdp_ws_cookies(args.cdp_url)
        count = write_netscape_cookies(raw_cookies, dest, args.url)
        if count > 0:
            log(f'Inherited {count} login cookie(s) from shared Chrome profile via CDP')
            return dest
    except Exception as exc:
        log(f'warning: could not read Chrome profile cookies ({type(exc).__name__}: {exc}); continuing without cookies')
    finally:
        if launched_proc is not None:
            try:
                launched_proc.terminate()
                launched_proc.wait(timeout=5)
            except Exception:
                launched_proc.kill()
    return None


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
    harvest_dir = Path(os.path.abspath(os.path.expanduser(args.harvest_dir))) if args.harvest_dir else None

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
            cookie_file = export_cdp_cookies(args, harvest_dir, temp_dir / 'cookies.txt')
            command = build_command(args, temp_dir, cookie_file=cookie_file)
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                env=build_ytdlp_env(),
                timeout=timeout,
                check=False,
            )
            if cookie_file is not None:
                cookie_file.unlink(missing_ok=True)
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
                        lowered = combined_output.lower()
                        if 'file is larger than max-filesize' in lowered:
                            cli.print_json({
                                'success': False,
                                'failure_kind': 'max_filesize',
                                'error': 'Video exceeds the configured max file size limit.',
                            })
                            return 1
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
