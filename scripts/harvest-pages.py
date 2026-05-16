#!/usr/bin/env python3
"""Batch URL material harvester for the topic-to-video skill.

For every URL the browser opens, unconditionally extracts:
  - Raster images with naturalWidth >= --min-image-width (default 500) and
    naturalHeight >= --min-image-height (default 300)
  - SVG images (both <img src="*.svg"> and inline <svg> elements) — these
    bypass the width/height thresholds because vector graphics often
    advertise tiny intrinsic dimensions
  - All embedded <video> elements and YouTube/Bilibili iframe/anchor links

Records a scroll video of each rendered page by default (disable with
--no-scroll-record).

Direct YouTube/Bilibili watch-page URLs are short-circuited: they are listed
in the manifest with `download_required: true` and the agent calls
video-download.py for them; no browser is opened for those URLs, so image
extraction and scroll recording do not apply.

Browser model: attaches over CDP (default http://localhost:9222) to a Chrome
process. If no CDP responder is reachable, auto-launches system Chrome with
--user-data-dir=<profile-dir>. Profile defaults to
./chrome_profile and is SHARED with
gemini-deep-research.py. Chrome is left running on exit so subsequent invocations
reconnect instantly.

Usage:
  python3 harvest-pages.py \\
    --urls https://github.com/anthropic/claude-code \\
           https://docs.anthropic.com/claude-code \\
           https://en.wikipedia.org/wiki/Claude_(language_model) \\
    --output-dir ~/.hermes/workspace/{topic}/harvest_page/

Output convention:
  stdout : top-level JSON manifest with one entry per URL (also written to
           <output-dir>/manifest.json)
  stderr : human-readable progress prefixed with `[harvest-pages]`
  exit   : 0 success (>=1 entry succeeded), 1 runtime error
           (CDP startup failure or all entries failed), 2 invalid arguments
"""

import argparse
import base64
import hashlib
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

TOOL_NAME = 'harvest-pages'
DEFAULT_CDP_URL = 'http://localhost:9222'
DEFAULT_PROFILE_DIR = './chrome_profile'
CHROME_CANDIDATES_LINUX = [
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
]
CHROME_CANDIDATES_MAC = [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    '/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary',
]
CHROME_CANDIDATES_WIN = [
    os.path.expandvars(r'%ProgramFiles%\Google\Chrome\Application\chrome.exe'),
    os.path.expandvars(r'%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe'),
    os.path.expandvars(r'%LocalAppData%\Google\Chrome\Application\chrome.exe'),
]
CDP_READY_TIMEOUT_S = 15.0
CDP_POLL_INTERVAL_S = 0.5
USER_AGENT = (
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
)


# -----------------------------------------------------------------------------
# I/O helpers
# -----------------------------------------------------------------------------

class ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        log(f'Argument error: {message}')
        print(json.dumps({'success': False, 'error': message}, ensure_ascii=False))
        self.exit(2)


def log(message: str) -> None:
    print(f'[{TOOL_NAME}] {message}', file=sys.stderr)


def fail(message: str, exit_code: int = 1) -> None:
    log(message)
    print(json.dumps({'success': False, 'error': message}, ensure_ascii=False))
    raise SystemExit(exit_code)


def parse_args() -> argparse.Namespace:
    p = ArgumentParser(description='Batch URL material harvester (Playwright over CDP).')
    p.add_argument('--urls', required=True, nargs='+', help='One or more URLs to harvest.')
    p.add_argument('--output-dir', required=True, help='Batch output root (per-URL subdirs are created underneath).')
    p.add_argument('--no-scroll-record', dest='scroll_record', action='store_false', default=True,
                   help='Disable scroll-record (on by default). '
                        'Note: scroll-record only applies to URLs opened in the browser; '
                        'direct YouTube/Bilibili watch URLs are short-circuited and never recorded.')
    p.add_argument('--min-image-width', type=int, default=500,
                   help='Minimum naturalWidth (px) to keep a raster image. Default 500. '
                        'SVG / inline-SVG candidates bypass this filter.')
    p.add_argument('--min-image-height', type=int, default=300,
                   help='Minimum naturalHeight (px) to keep a raster image. Default 300. '
                        'SVG / inline-SVG candidates bypass this filter.')
    p.add_argument('--max-images-per-url', type=int, default=20, help='Cap on images per URL.')
    p.add_argument('--max-videos-per-url', type=int, default=5, help='Cap on videos per URL.')
    p.add_argument('--scroll-duration', type=int, default=30,
                   help='Scroll-record duration in seconds (capped at 60). Default 30.')
    p.add_argument('--viewport', default='1280x720', help='Viewport WxH for new contexts. Default 1280x720.')
    p.add_argument('--page-load-timeout', type=int, default=30,
                   help='Per-URL page load timeout in seconds. Default 30.')
    p.add_argument('--cdp-url', default=DEFAULT_CDP_URL, help=f'CDP endpoint (default {DEFAULT_CDP_URL}).')
    p.add_argument('--profile-dir', default=DEFAULT_PROFILE_DIR,
                   help=f'Chrome profile dir (default {DEFAULT_PROFILE_DIR}).')
    p.add_argument('--chrome-path', default=None,
                   help='Path to Chrome executable. Auto-detected if unset.')
    p.add_argument('--headless', default='auto', choices=('auto', 'on', 'off'),
                   help="Chrome headless mode. 'auto' (default) = headless when DISPLAY is unset.")
    p.add_argument('--no-sandbox', action='store_true', default=None,
                   help='Pass --no-sandbox to Chrome (auto-enabled when running as root or inside a container).')
    p.add_argument('--no-continue-on-error', action='store_true',
                   help='Stop the batch on the first per-URL failure. Default off (best-effort).')
    return p.parse_args()


def parse_viewport(s: str) -> Tuple[int, int]:
    m = re.match(r'^(\d+)x(\d+)$', s)
    if not m:
        raise ValueError(f'Invalid --viewport {s!r}, expected WxH (e.g. 1280x720)')
    return int(m.group(1)), int(m.group(2))


def slugify_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.netloc or 'unknown').lower().replace('.', '-').replace(':', '-')
    path = (parsed.path or '/').strip('/').lower()
    path = re.sub(r'[^a-z0-9]+', '-', path).strip('-')[:60]
    digest = hashlib.sha1(url.encode('utf-8')).hexdigest()[:6]
    if path:
        slug = f'{host}-{path}-{digest}'
    else:
        slug = f'{host}-{digest}'
    return slug.strip('-')[:120]


# -----------------------------------------------------------------------------
# CDP / browser setup
# -----------------------------------------------------------------------------

def _chrome_candidates() -> list:
    """Return Chrome candidate paths for the current platform."""
    import platform
    s = platform.system()
    if s == 'Darwin':
        return CHROME_CANDIDATES_MAC
    elif s == 'Windows':
        return CHROME_CANDIDATES_WIN
    return CHROME_CANDIDATES_LINUX


def find_chrome(explicit: Optional[str]) -> Optional[str]:
    if explicit:
        return explicit if Path(explicit).is_file() else None
    env_path = os.environ.get('CHROME_PATH')
    if env_path and Path(env_path).is_file():
        return env_path
    for cand in _chrome_candidates():
        if Path(cand).is_file():
            return cand
    return None


def cdp_ready(cdp_url: str) -> bool:
    from urllib import request as urlrequest
    from urllib import error as urlerror
    try:
        with urlrequest.urlopen(f'{cdp_url.rstrip("/")}/json/version', timeout=2.0) as resp:
            return resp.status == 200
    except (urlerror.URLError, urlerror.HTTPError, TimeoutError, ConnectionError, OSError):
        return False


def _should_be_headless(headless_mode: str) -> bool:
    if headless_mode == 'on':
        return True
    if headless_mode == 'off':
        return False
    return not os.environ.get('DISPLAY')


def _should_disable_sandbox(no_sandbox_flag: Optional[bool]) -> bool:
    if no_sandbox_flag:
        return True
    try:
        if os.geteuid() == 0:
            return True
    except AttributeError:
        pass
    return Path('/.dockerenv').exists()


def launch_chrome(chrome_path: str, cdp_url: str, profile_dir: Path,
                  headless_mode: str = 'auto',
                  no_sandbox_flag: Optional[bool] = None) -> subprocess.Popen:
    parsed = urlparse(cdp_url)
    port = parsed.port or 9222
    profile_dir.mkdir(parents=True, exist_ok=True)
    args = [
        chrome_path,
        f'--remote-debugging-port={port}',
        f'--user-data-dir={profile_dir}',
        '--no-first-run',
        '--no-default-browser-check',
        '--disable-features=Translate',
    ]
    if _should_be_headless(headless_mode):
        args.append('--headless=new')
        args.append('--disable-gpu')
    if _should_disable_sandbox(no_sandbox_flag):
        args.append('--no-sandbox')
    log(f'Launching Chrome: {chrome_path} (port={port}, profile={profile_dir}, '
        f'flags={[a for a in args[3:] if a.startswith("--")]})')
    return subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )


def wait_for_cdp(cdp_url: str, proc: Optional[subprocess.Popen]) -> None:
    deadline = time.time() + CDP_READY_TIMEOUT_S
    while time.time() < deadline:
        if proc is not None and proc.poll() is not None:
            fail(
                f'Chrome exited immediately (code {proc.returncode}). '
                'Profile may be locked by another Chrome window. '
                f'Profile path: {DEFAULT_PROFILE_DIR}. '
                'Close other Chrome instances using this profile, or pass a different --profile-dir.'
            )
        if cdp_ready(cdp_url):
            return
        time.sleep(CDP_POLL_INTERVAL_S)
    fail(
        f'CDP at {cdp_url} did not become ready within {CDP_READY_TIMEOUT_S}s. '
        'Check that the port is free and Chrome can launch with the given profile.'
    )


def ensure_cdp(args: argparse.Namespace) -> None:
    """Ensure something is listening on CDP. Auto-launch system Chrome if not."""
    if cdp_ready(args.cdp_url):
        log(f'CDP already ready at {args.cdp_url}; reusing existing Chrome')
        return
    chrome_path = find_chrome(args.chrome_path)
    if not chrome_path:
        fail(
            'System Chrome not found. Tried: '
            f'{", ".join(_chrome_candidates())}. '
            'Install Chrome or pass --chrome-path.'
        )
    profile_dir = Path(args.profile_dir).expanduser()
    proc = launch_chrome(chrome_path, args.cdp_url, profile_dir,
                         headless_mode=args.headless,
                         no_sandbox_flag=args.no_sandbox)
    wait_for_cdp(args.cdp_url, proc)
    log(f'CDP ready at {args.cdp_url} (chrome pid={proc.pid}; left running on exit)')


# -----------------------------------------------------------------------------
# Page-level helpers (run inside Playwright contexts)
# -----------------------------------------------------------------------------

AUTO_SCROLL_JS = """
async () => {
  const step = 400;
  const delay = 80;
  let lastH = -1;
  for (let i = 0; i < 200; i++) {
    if (window.scrollY + window.innerHeight >= document.body.scrollHeight) break;
    window.scrollBy(0, step);
    await new Promise(r => setTimeout(r, delay));
    if (document.body.scrollHeight === lastH && i > 4) break;
    lastH = document.body.scrollHeight;
  }
  window.scrollTo(0, 0);
}
"""

METRICS_JS = r"""
() => {
  const drop = new Set(['NAV','FOOTER','HEADER','ASIDE','SCRIPT','STYLE','NOSCRIPT']);
  const isVisible = (el) => {
    const cs = window.getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const walk = (root, acc) => {
    if (!root) return;
    for (const el of root.children) {
      if (drop.has(el.tagName)) continue;
      if (!isVisible(el)) continue;
      if (el.children.length === 0) {
        const t = (el.innerText || '').trim();
        if (t) acc.push(t);
      } else {
        walk(el, acc);
      }
    }
  };
  const acc = [];
  walk(document.body, acc);
  const text = acc.join(' ');
  const wordCount = text ? text.split(/\s+/).filter(Boolean).length : 0;

  const videos = document.querySelectorAll('video').length;
  const iframes = Array.from(document.querySelectorAll('iframe')).filter(f =>
    /youtube\.com|youtu\.be|youtube-nocookie\.com|player\.bilibili\.com/.test(f.src || '')
  ).length;
  const anchors = Array.from(document.querySelectorAll('a[href]')).filter(a =>
    /youtube\.com|youtu\.be|bilibili\.com\/video/.test(a.href || '')
  ).length;

  return {
    word_count: wordCount,
    video_count: videos + iframes + anchors,
    title: document.title || '',
    text_excerpt: text.slice(0, 2000),
  };
}
"""

EXTRACT_IMAGES_JS = r"""
() => {
  const out = [];
  const seen = new Set();
  // Standard <img> elements (including <img src="*.svg">)
  for (const img of document.images || []) {
    const url = img.currentSrc || img.src;
    if (!url) continue;
    if (seen.has(url)) continue;
    seen.add(url);
    const isSvg = /\.svg(\?|#|$)/i.test(url);
    let w = img.naturalWidth || 0;
    let h = img.naturalHeight || 0;
    // SVG <img> often has naturalWidth=0; fall back to rendered size
    if (isSvg && (w === 0 || h === 0)) {
      const rect = img.getBoundingClientRect();
      w = Math.round(rect.width) || 0;
      h = Math.round(rect.height) || 0;
    }
    out.push({
      url,
      width: w,
      height: h,
      alt: (img.alt || '').slice(0, 200),
      type: isSvg ? 'svg' : 'raster',
    });
  }
  // Inline <svg> elements — serialize to markup
  for (const svg of document.querySelectorAll('svg')) {
    const rect = svg.getBoundingClientRect();
    if (rect.width < 40 || rect.height < 40) continue;  // skip tiny icons
    const markup = new XMLSerializer().serializeToString(svg);
    if (markup.length < 100) continue;  // skip trivial/empty SVGs
    const key = 'inline-svg-' + markup.length + '-' + Math.round(rect.width) + 'x' + Math.round(rect.height);
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({
      url: null,
      width: Math.round(rect.width),
      height: Math.round(rect.height),
      alt: (svg.getAttribute('aria-label') || svg.querySelector('title')?.textContent || '').slice(0, 200),
      type: 'inline-svg',
      markup,
    });
  }
  return out;
}
"""

EXTRACT_VIDEOS_JS = r"""
() => {
  const out = [];
  const seen = new Set();
  const push = (url, platform) => {
    if (!url || seen.has(url)) return;
    seen.add(url);
    out.push({ url, platform });
  };
  // <video> with src or <source>
  for (const v of document.querySelectorAll('video')) {
    const src = v.currentSrc || v.src || '';
    if (src) push(src, 'native');
    for (const s of v.querySelectorAll('source')) {
      if (s.src) push(s.src, 'native');
    }
  }
  // iframes for known platforms
  for (const f of document.querySelectorAll('iframe')) {
    const u = f.src || '';
    if (!u) continue;
    if (/youtube\.com|youtu\.be|youtube-nocookie\.com/.test(u)) push(u, 'youtube');
    else if (/player\.bilibili\.com/.test(u)) push(u, 'bilibili');
  }
  // anchors linking to YouTube/Bilibili watch pages
  for (const a of document.querySelectorAll('a[href]')) {
    const u = a.href || '';
    if (/youtube\.com\/watch|youtu\.be\//.test(u)) push(u, 'youtube');
    else if (/bilibili\.com\/video/.test(u)) push(u, 'bilibili');
  }
  return out;
}
"""

SCROLL_RECORD_JS = """
async (durationMs) => {
  // brief pause at top
  await new Promise(r => setTimeout(r, 600));
  const start = performance.now();
  const totalH = Math.max(0, document.body.scrollHeight - window.innerHeight);
  const step = 1000 / 60;
  return await new Promise(resolve => {
    const tick = () => {
      const elapsed = performance.now() - start;
      const t = Math.min(1, elapsed / durationMs);
      window.scrollTo(0, totalH * t);
      if (t < 1) {
        setTimeout(tick, step);
      } else {
        // brief pause at bottom
        setTimeout(resolve, 600);
      }
    };
    tick();
  });
}
"""


# -----------------------------------------------------------------------------
# Per-URL processing
# -----------------------------------------------------------------------------

# YouTube/Bilibili URL pattern catalogue. Shared between `normalize_youtube`
# (turns embed/short/youtu.be forms into the canonical watch URL) and
# `detect_watchable_platform` (decides whether a URL is yt-dlp-fetchable
# without going through the browser). Compiled once; case-insensitive on host.
_VIDEO_ID = r'[A-Za-z0-9_-]{6,}'
_YT_NORMALIZE_PATTERNS = [
    re.compile(rf'^https?://(?:www\.)?youtube(?:-nocookie)?\.com/embed/({_VIDEO_ID})', re.IGNORECASE),
    re.compile(rf'^https?://youtu\.be/({_VIDEO_ID})', re.IGNORECASE),
    re.compile(rf'^https?://(?:www\.|m\.)?youtube\.com/shorts/({_VIDEO_ID})', re.IGNORECASE),
]
_YT_DETECT_PATTERNS = [
    re.compile(r'^https?://(?:(?:www|m)\.)?youtube\.com/watch\?', re.IGNORECASE),
    re.compile(rf'^https?://youtu\.be/{_VIDEO_ID}', re.IGNORECASE),
    re.compile(rf'^https?://(?:(?:www|m)\.)?youtube\.com/shorts/{_VIDEO_ID}', re.IGNORECASE),
    re.compile(rf'^https?://(?:www\.)?youtube(?:-nocookie)?\.com/embed/{_VIDEO_ID}', re.IGNORECASE),
]
_BILI_DETECT_PATTERNS = [
    re.compile(r'^https?://(?:www\.|m\.)?bilibili\.com/video/(?:BV[A-Za-z0-9]+|av\d+)', re.IGNORECASE),
    re.compile(r'^https?://b23\.tv/[A-Za-z0-9]+', re.IGNORECASE),
]


def normalize_youtube(url: str) -> str:
    """Normalize youtube iframe/short URLs to canonical watch URLs (best-effort).

    Host matching is case-insensitive (RFC 3986 allows uppercase hostnames);
    the video-ID capture group preserves case.
    """
    for pat in _YT_NORMALIZE_PATTERNS:
        m = pat.match(url)
        if m:
            return f'https://www.youtube.com/watch?v={m.group(1)}'
    return url


def detect_watchable_platform(url: str) -> Optional[str]:
    """Return 'youtube' or 'bilibili' when the URL is a watchable video page that
    video-download.py (yt-dlp) can fetch directly, else None.

    Matches (host comparison is case-insensitive):
      - YouTube:  youtube.com/watch?v=..., youtu.be/<id>, /shorts/<id>,
                  /embed/<id>, youtube-nocookie.com/embed/<id>, m.youtube.com/...
      - Bilibili: bilibili.com/video/BV..., bilibili.com/video/av..., b23.tv/...
    """
    if not url:
        return None
    u = url.strip()
    if any(pat.match(u) for pat in _YT_DETECT_PATTERNS):
        return 'youtube'
    if any(pat.match(u) for pat in _BILI_DETECT_PATTERNS):
        return 'bilibili'
    return None




def guess_image_ext(url: str, content_type: Optional[str]) -> str:
    if content_type:
        ct = content_type.split(';')[0].strip().lower()
        ext = mimetypes.guess_extension(ct)
        if ext:
            return ext
    parsed = urlparse(url)
    suffix = Path(parsed.path).suffix
    if suffix and len(suffix) <= 6:
        return suffix
    return '.jpg'


def download_image(request_ctx, url: str, dest_dir: Path, index: int) -> Optional[Path]:
    try:
        resp = request_ctx.get(url, timeout=20000)
        if not resp.ok:
            log(f'  image {index}: HTTP {resp.status} for {url[:80]}')
            return None
        content_type = resp.headers.get('content-type', '')
        ext = guess_image_ext(url, content_type)
        path = dest_dir / f'img_{index:03d}{ext}'
        path.write_bytes(resp.body())
        return path
    except Exception as exc:
        log(f'  image {index}: failed: {exc}')
        return None


def download_native_video(request_ctx, url: str, dest_dir: Path, index: int, max_bytes: int = 200 * 1024 * 1024) -> Optional[Path]:
    try:
        resp = request_ctx.get(url, timeout=60000)
        if not resp.ok:
            log(f'  video {index}: HTTP {resp.status} for {url[:80]}')
            return None
        body = resp.body()
        if len(body) > max_bytes:
            log(f'  video {index}: skipped (size {len(body)} > {max_bytes})')
            return None
        ext = '.mp4'
        parsed = urlparse(url)
        suffix = Path(parsed.path).suffix
        if suffix in ('.mp4', '.webm', '.mov'):
            ext = suffix
        path = dest_dir / f'native_{index:03d}{ext}'
        path.write_bytes(body)
        return path
    except Exception as exc:
        log(f'  video {index}: failed: {exc}')
        return None


# -----------------------------------------------------------------------------
# Scroll recording
# -----------------------------------------------------------------------------

def primary_scroll_record(browser, url: str, viewport: Tuple[int, int], scroll_duration: int,
                          page_load_timeout: int, output_dir: Path) -> Tuple[Optional[Path], Optional[str]]:
    rec_dir = output_dir / 'recording'
    rec_dir.mkdir(parents=True, exist_ok=True)
    vp_w, vp_h = viewport
    ctx = browser.new_context(
        viewport={'width': vp_w, 'height': vp_h},
        user_agent=USER_AGENT,
        locale='zh-CN',
        extra_http_headers={'Accept-Language': 'zh-CN,en;q=0.9'},
        record_video_dir=str(rec_dir),
        record_video_size={'width': vp_w, 'height': vp_h},
    )
    try:
        page = ctx.new_page()
        page.set_default_timeout(page_load_timeout * 1000)
        page.goto(url, wait_until='domcontentloaded', timeout=page_load_timeout * 1000)
        try:
            page.wait_for_load_state('networkidle', timeout=5000)
        except Exception:
            pass
        page.evaluate(SCROLL_RECORD_JS, scroll_duration * 1000)
    finally:
        ctx.close()  # flushes the .webm

    # Find newest .webm in rec_dir
    webms = sorted(rec_dir.glob('*.webm'), key=lambda p: p.stat().st_mtime, reverse=True)
    if not webms:
        return None, 'playwright_no_video'
    target = rec_dir / f'scroll-{int(time.time())}.webm'
    webms[0].rename(target)
    return target, 'playwright'


def cdp_screencast_record(browser, url: str, viewport: Tuple[int, int], scroll_duration: int,
                          page_load_timeout: int, output_dir: Path) -> Tuple[Optional[Path], Optional[str]]:
    if not shutil.which('ffmpeg'):
        return None, 'cdp_no_ffmpeg'
    rec_dir = output_dir / 'recording'
    frames_dir = rec_dir / 'frames'
    frames_dir.mkdir(parents=True, exist_ok=True)
    vp_w, vp_h = viewport

    ctx = browser.new_context(
        viewport={'width': vp_w, 'height': vp_h},
        user_agent=USER_AGENT,
        locale='zh-CN',
        extra_http_headers={'Accept-Language': 'zh-CN,en;q=0.9'},
    )
    frame_idx = [0]
    try:
        page = ctx.new_page()
        page.set_default_timeout(page_load_timeout * 1000)
        page.goto(url, wait_until='domcontentloaded', timeout=page_load_timeout * 1000)
        try:
            page.wait_for_load_state('networkidle', timeout=5000)
        except Exception:
            pass

        cdp = ctx.new_cdp_session(page)

        def on_frame(params):
            try:
                data = base64.b64decode(params['data'])
                frame_idx[0] += 1
                (frames_dir / f'f_{frame_idx[0]:06d}.jpg').write_bytes(data)
                cdp.send('Page.screencastFrameAck', {'sessionId': params['sessionId']})
            except Exception as exc:
                log(f'  screencast frame error: {exc}')

        cdp.on('Page.screencastFrame', on_frame)
        cdp.send('Page.startScreencast', {
            'format': 'jpeg',
            'quality': 70,
            'maxWidth': vp_w,
            'maxHeight': vp_h,
            'everyNthFrame': 1,
        })
        page.evaluate(SCROLL_RECORD_JS, scroll_duration * 1000)
        cdp.send('Page.stopScreencast')
    finally:
        ctx.close()

    if frame_idx[0] == 0:
        return None, 'cdp_no_frames'

    out_mp4 = rec_dir / f'scroll-{int(time.time())}.mp4'
    cmd = [
        'ffmpeg', '-y', '-loglevel', 'error',
        '-framerate', '30',
        '-pattern_type', 'glob',
        '-i', str(frames_dir / 'f_*.jpg'),
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        str(out_mp4),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=180)
    except subprocess.CalledProcessError as exc:
        log(f'  ffmpeg failed: {exc.stderr.decode("utf-8", "replace")[:300]}')
        return None, 'ffmpeg_failed'

    # cleanup frames
    try:
        shutil.rmtree(frames_dir)
    except Exception:
        pass

    return out_mp4, 'cdp_screencast'


def probe_duration(path: Path) -> Optional[float]:
    if not shutil.which('ffprobe'):
        return None
    try:
        out = subprocess.check_output(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', str(path)],
            timeout=15,
        )
        return float(out.decode().strip())
    except Exception:
        return None


# -----------------------------------------------------------------------------
# Per-URL pipeline
# -----------------------------------------------------------------------------

def harvest_one(browser, url: str, slug: str, slug_dir: Path, args: argparse.Namespace,
                viewport: Tuple[int, int]) -> Dict[str, Any]:
    log(f'-- {slug} -- {url}')
    images_dir = slug_dir / 'images'
    videos_dir = slug_dir / 'videos'
    images_dir.mkdir(parents=True, exist_ok=True)
    videos_dir.mkdir(parents=True, exist_ok=True)

    vp_w, vp_h = viewport
    ctx = browser.new_context(
        viewport={'width': vp_w, 'height': vp_h},
        user_agent=USER_AGENT,
        locale='zh-CN',
        extra_http_headers={'Accept-Language': 'zh-CN,en;q=0.9'},
    )
    metrics = {}
    title = ''
    text_excerpt = ''
    images_meta: List[Dict[str, Any]] = []
    videos_meta: List[Dict[str, Any]] = []
    scroll_recording: Optional[Dict[str, Any]] = None
    try:
        page = ctx.new_page()
        page.set_default_timeout(args.page_load_timeout * 1000)
        page.goto(url, wait_until='domcontentloaded', timeout=args.page_load_timeout * 1000)
        try:
            page.wait_for_load_state('networkidle', timeout=5000)
        except Exception:
            pass

        # save page source for debugging
        try:
            (slug_dir / 'page-source.html').write_text(page.content(), encoding='utf-8', errors='replace')
        except Exception as exc:
            log(f'  page-source.html save failed: {exc}')

        # autoscroll to materialize lazy images
        try:
            page.evaluate(AUTO_SCROLL_JS)
        except Exception as exc:
            log(f'  autoscroll failed: {exc}')

        metrics = page.evaluate(METRICS_JS) or {}
        title = metrics.pop('title', '')
        text_excerpt = metrics.pop('text_excerpt', '')
        log(f'  metrics={metrics}')

        # extract image candidates
        raw_imgs = page.evaluate(EXTRACT_IMAGES_JS) or []
        kept = [
            im for im in raw_imgs
            if im.get('type') in ('svg', 'inline-svg')  # SVGs bypass size filter
            or (im.get('width', 0) >= args.min_image_width
                and im.get('height', 0) >= args.min_image_height)
        ][: args.max_images_per_url]
        log(f'  images: {len(raw_imgs)} found, {len(kept)} pass size filter')

        for i, im in enumerate(kept, start=1):
            img_type = im.get('type', 'raster')
            if img_type == 'inline-svg':
                # Save inline SVG markup directly
                path = images_dir / f'svg_{i:03d}.svg'
                try:
                    path.write_text(im['markup'], encoding='utf-8')
                except Exception as exc:
                    log(f'  inline-svg {i}: write failed: {exc}')
                    images_meta.append({
                        'url': None,
                        'width': im.get('width', 0),
                        'height': im.get('height', 0),
                        'alt': im.get('alt', ''),
                        'type': 'inline-svg',
                        'downloaded': False,
                        'error': f'write failed: {exc}',
                    })
                    continue
                meta = {
                    'url': None,
                    'width': im.get('width', 0),
                    'height': im.get('height', 0),
                    'alt': im.get('alt', ''),
                    'local_path': str(path.resolve()),
                    'id': path.stem,
                    'type': 'inline-svg',
                }
            else:
                local = download_image(ctx.request, im['url'], images_dir, i)
                meta = {
                    'url': im['url'],
                    'width': im.get('width', 0),
                    'height': im.get('height', 0),
                    'alt': im.get('alt', ''),
                    'type': img_type,
                }
                if local:
                    meta['local_path'] = str(local.resolve())
                    meta['id'] = local.stem
                else:
                    meta['downloaded'] = False
                    meta['error'] = 'download failed'
            images_meta.append(meta)

        # extract video candidates
        raw_vids = page.evaluate(EXTRACT_VIDEOS_JS) or []
        # dedupe by normalized url
        seen = set()
        normalized = []
        for v in raw_vids:
            u = v['url']
            if v['platform'] in ('youtube',):
                u = normalize_youtube(u)
            if u in seen:
                continue
            seen.add(u)
            normalized.append({'url': u, 'platform': v['platform']})
        normalized = normalized[: args.max_videos_per_url]
        log(f'  videos: {len(raw_vids)} found, {len(normalized)} kept')

        native_idx = 0
        for v in normalized:
            meta: Dict[str, Any] = {'url': v['url'], 'platform': v['platform']}
            if v['platform'] in ('youtube', 'bilibili'):
                # External platform: list the URL; agent calls video-download.py
                # in a follow-up step (see SKILL.md Phase 3.b).
                meta['download_required'] = True
                meta['suggested_output_dir'] = str(videos_dir.resolve())
                log(f'  external video listed (download_required): {v["url"]}')
            else:  # native HTML5 <video>
                native_idx += 1
                local = download_native_video(ctx.request, v['url'], videos_dir, native_idx)
                if local:
                    meta['download_required'] = False
                    meta['downloaded'] = True
                    meta['local_path'] = str(local.resolve())
                    meta['id'] = local.stem
                else:
                    meta['download_required'] = False
                    meta['downloaded'] = False
                    meta['error'] = 'native download failed'
            videos_meta.append(meta)

        # close context BEFORE scroll-record (record needs its own context)
    finally:
        try:
            ctx.close()
        except Exception:
            pass

    if args.scroll_record:
        capped = min(60, max(5, args.scroll_duration))
        try:
            record_path, method = primary_scroll_record(
                browser, url, viewport, capped, args.page_load_timeout, slug_dir
            )
            if record_path is None:
                log(f'  primary scroll-record failed ({method}); trying CDP screencast fallback')
                record_path, method = cdp_screencast_record(
                    browser, url, viewport, capped, args.page_load_timeout, slug_dir
                )
            if record_path is None:
                log(f'  scroll-record failed ({method}); continuing without recording')
            else:
                dur = probe_duration(record_path) or float(capped)
                scroll_recording = {
                    'local_path': str(record_path.resolve()),
                    'duration_sec': round(dur, 3),
                    'method': method,
                }
                log(f'  scroll-record OK via {method}: {record_path}')
        except Exception as exc:
            # Scroll-record failure must not discard already-collected images/videos.
            log(f'  scroll-record raised ({type(exc).__name__}: {exc}); continuing without recording')

    entry = {
        'url': url,
        'slug': slug,
        'success': True,
        'title': title,
        'text_excerpt': text_excerpt,
        'metrics': metrics,
        'images': images_meta,
        'videos': videos_meta,
        'scroll_recording': scroll_recording,
    }
    return entry


# -----------------------------------------------------------------------------
# Driver
# -----------------------------------------------------------------------------

def partition_urls(
    raw_urls: List[str],
) -> Tuple[List[Tuple[str, str, Optional[str]]], List[Dict[str, str]]]:
    """Dedupe `raw_urls`, drop non-http(s), assign a unique slug to each, and
    classify whether each URL is a yt-dlp-fetchable watch page.

    Returns (items, bad_urls) where:
      - items[i] = (url, slug, platform_or_None). `platform_or_None` is the
        return value of `detect_watchable_platform` and signals the short-circuit
        path (no Playwright render).
      - bad_urls is the list of `{url, error}` rejected entries the manifest
        surfaces under `rejected`.

    The scheme guard rejects `file://`, `chrome://`, `javascript:`, etc. so a
    caller can't trick Playwright into reading local files or triggering
    privileged Chrome UIs.
    """
    seen: set = set()
    used_slugs: set = set()
    items: List[Tuple[str, str, Optional[str]]] = []
    bad_urls: List[Dict[str, str]] = []
    for u in raw_urls:
        if u in seen:
            continue
        seen.add(u)
        try:
            scheme = urlparse(u).scheme.lower()
        except Exception:
            scheme = ''
        if scheme not in ('http', 'https'):
            bad_urls.append({'url': u, 'error': f'unsupported URL scheme {scheme!r}; only http(s) is allowed'})
            log(f'  reject: {u} (scheme={scheme!r} — only http/https allowed)')
            continue
        s = slugify_url(u)
        base, n = s, 2
        while s in used_slugs:
            s = f'{base}-{n}'
            n += 1
        used_slugs.add(s)
        items.append((u, s, detect_watchable_platform(u)))
    return items, bad_urls


def aggregate_pending_downloads(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Collect every external video URL that still needs yt-dlp into a flat list
    so the agent can iterate one array instead of nested-looping
    `entries[].videos[]`.

    Deduplicate by canonical URL. The same clip is frequently embedded on
    multiple pages of the same batch (homepage + GitHub README is a common
    pattern); downloading it twice into two per-slug directories wastes
    bandwidth and risks yt-dlp rate-limiting. The first occurrence's
    `suggested_output_dir` wins; additional referrers go into
    `also_referenced_by` so Phase 3.b can fan out the `local_path` update to
    every metadata.json that points at the same clip.
    """
    pending: List[Dict[str, Any]] = []
    index: Dict[str, int] = {}
    for e in entries:
        if not e.get('success'):
            continue
        for v in e.get('videos', []) or []:
            if not v.get('download_required'):
                continue
            url_key = v.get('url', '')
            if not url_key:
                continue
            if url_key in index:
                pending[index[url_key]].setdefault('also_referenced_by', []).append(
                    e.get('slug', '')
                )
                continue
            index[url_key] = len(pending)
            pending.append({
                'url': url_key,
                'platform': v.get('platform', ''),
                'suggested_output_dir': v.get('suggested_output_dir', ''),
                'source_slug': e.get('slug', ''),
            })
    return pending


def main() -> None:
    args = parse_args()
    try:
        viewport = parse_viewport(args.viewport)
    except ValueError as exc:
        fail(str(exc), exit_code=2)

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    items, bad_urls = partition_urls(args.urls)
    if not items:
        fail(
            'no http(s) URLs to harvest after scheme filtering. '
            f'Rejected: {[b["url"] for b in bad_urls]}',
            exit_code=2,
        )
    log(f'Batch size: {len(items)} URL(s); output={output_dir}'
        + (f' (rejected {len(bad_urls)} non-http(s) URL(s))' if bad_urls else ''))

    # ensure Playwright is available (only required when at least one URL needs rendering)
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except Exception:
        # Defer the hard failure until we know we actually need a browser.
        sync_playwright = None  # type: ignore

    needs_chrome = any(plat is None for _, _, plat in items)
    direct_count = sum(1 for _, _, plat in items if plat is not None)
    if direct_count:
        log(f'{direct_count}/{len(items)} URL(s) recognized as direct video pages — '
            f'these will be listed without browser rendering.')

    entries: List[Dict[str, Any]] = []
    succeeded = 0

    pw = None
    browser = None
    if needs_chrome:
        if sync_playwright is None:
            fail(
                'playwright not installed; run: pip install playwright '
                '(no `playwright install chromium` needed — uses system Chrome over CDP)'
            )
        # ensure Chrome is up on CDP
        ensure_cdp(args)
        from playwright.sync_api import sync_playwright as _sp
        pw = _sp().start()
        try:
            browser = pw.chromium.connect_over_cdp(args.cdp_url)
        except Exception as exc:
            try:
                pw.stop()
            except Exception:
                pass
            fail(f'connect_over_cdp({args.cdp_url}) failed: {exc}')
        log(f'Connected to Chrome over CDP ({args.cdp_url})')
    else:
        log('No URL requires browser rendering — skipping Chrome/CDP setup.')

    try:
        for url, slug, platform in items:
            slug_dir = output_dir / slug
            slug_dir.mkdir(parents=True, exist_ok=True)
            try:
                if platform is not None:
                    # Short-circuit: no Playwright navigation. The agent will call
                    # video-download.py for the URL listed in `videos[]` (see SKILL.md Phase 3.b).
                    videos_dir = slug_dir / 'videos'
                    videos_dir.mkdir(parents=True, exist_ok=True)
                    canonical = normalize_youtube(url) if platform == 'youtube' else url
                    log(f'-- {slug} -- {url}  (video URL only; platform={platform})')
                    entry: Dict[str, Any] = {
                        'url': url,
                        'slug': slug,
                        'success': True,
                        'title': '',
                        'text_excerpt': '',
                        'metrics': {},
                        'images': [],
                        'videos': [{
                            'url': canonical,
                            'platform': platform,
                            'download_required': True,
                            'suggested_output_dir': str(videos_dir.resolve()),
                        }],
                        'scroll_recording': None,
                    }
                else:
                    entry = harvest_one(browser, url, slug, slug_dir, args, viewport)
            except Exception as exc:
                log(f'  fatal per-URL error: {exc}')
                entry = {'url': url, 'slug': slug, 'success': False, 'error': str(exc)}

            # write per-URL metadata
            try:
                (slug_dir / 'metadata.json').write_text(
                    json.dumps(entry, ensure_ascii=False, indent=2),
                    encoding='utf-8',
                )
            except Exception as exc:
                log(f'  metadata.json save failed: {exc}')

            if entry.get('success'):
                succeeded += 1
            entries.append(entry)

            if not entry.get('success') and args.no_continue_on_error:
                log('--no-continue-on-error set; stopping batch')
                break
    finally:
        if browser is not None:
            try:
                browser.close()  # detach the Playwright client (does NOT kill Chrome — we connected over CDP)
            except Exception:
                pass
        if pw is not None:
            try:
                pw.stop()
            except Exception:
                pass

    # Aggregate pending external downloads across the batch (deduplicated by
    # canonical URL). See aggregate_pending_downloads docstring.
    pending_downloads = aggregate_pending_downloads(entries)

    batch_success = succeeded > 0
    manifest = {
        'success': batch_success,
        'output_dir': str(output_dir),
        'batch_size': len(items),
        'succeeded': succeeded,
        'entries': entries,
    }
    if bad_urls:
        manifest['rejected'] = bad_urls
    if pending_downloads:
        manifest['pending_downloads'] = pending_downloads
    if not batch_success:
        manifest['error'] = 'All URLs failed; see entries[].error for details.'

    try:
        (output_dir / 'manifest.json').write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
    except Exception as exc:
        log(f'manifest.json save failed: {exc}')

    print(json.dumps(manifest, ensure_ascii=False))
    log(f'Done. {succeeded}/{len(items)} entries succeeded.')
    if not batch_success:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
