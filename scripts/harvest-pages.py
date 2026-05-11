#!/usr/bin/env python3
"""Batch URL material harvester for the topic-to-video skill.

Given an array of URLs, this tool decides per URL whether to:
  - Mode `media`        : extract >=512px images and embedded videos
                          (native <video>, YouTube/Bilibili via video-download.py).
  - Mode `scroll-record`: scroll the page top->bottom and record the scroll as
                          a video file for downstream extract-frames + vision-analyze.

Browser model: attaches over CDP (default http://localhost:9222) to a Chrome
process. If no CDP responder is reachable, auto-launches system Chrome with
--user-data-dir=<profile-dir>. Profile defaults to
~/.hermes/workspace/chrome_profile and is SHARED with TuberUp's
gemini-deep-research. Chrome is left running on exit so subsequent invocations
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
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

TOOL_NAME = 'harvest-pages'
DEFAULT_CDP_URL = 'http://localhost:9222'
DEFAULT_PROFILE_DIR = '~/.hermes/workspace/chrome_profile'
CHROME_CANDIDATES = [
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
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
    p.add_argument('--mode', default='auto', choices=('auto', 'media', 'scroll-record'),
                   help='Per-URL mode. Default auto (decided per page).')
    p.add_argument('--min-image-size', type=int, default=512,
                   help='Minimum naturalWidth AND naturalHeight (px) to keep an image. Default 512.')
    p.add_argument('--max-images-per-url', type=int, default=20, help='Cap on images per URL.')
    p.add_argument('--max-videos-per-url', type=int, default=5, help='Cap on videos per URL.')
    p.add_argument('--scroll-duration', type=int, default=30,
                   help='Scroll-record duration in seconds (capped at 60). Default 30.')
    p.add_argument('--viewport', default='1280x720', help='Viewport WxH for new contexts. Default 1280x720.')
    p.add_argument('--text-threshold', type=int, default=800,
                   help='Word count above which a page can be considered text-heavy. Default 800.')
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

def find_chrome(explicit: Optional[str]) -> Optional[str]:
    if explicit:
        return explicit if Path(explicit).is_file() else None
    env_path = os.environ.get('CHROME_PATH')
    if env_path and Path(env_path).is_file():
        return env_path
    for cand in CHROME_CANDIDATES:
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
            f'{", ".join(CHROME_CANDIDATES)}. '
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

  const imgs = Array.from(document.images || []);
  const largeImageCount = imgs.filter(im => (im.naturalWidth||0) >= 512 && (im.naturalHeight||0) >= 512).length;

  const videos = document.querySelectorAll('video').length;
  const iframes = Array.from(document.querySelectorAll('iframe')).filter(f =>
    /youtube\.com|youtu\.be|youtube-nocookie\.com|player\.bilibili\.com/.test(f.src || '')
  ).length;
  const anchors = Array.from(document.querySelectorAll('a[href]')).filter(a =>
    /youtube\.com|youtu\.be|bilibili\.com\/video/.test(a.href || '')
  ).length;

  let articleTextLen = 0;
  for (const sel of ['article', 'main', '[role="main"]']) {
    for (const el of document.querySelectorAll(sel)) {
      const t = (el.innerText || '').trim();
      if (t.length > articleTextLen) articleTextLen = t.length;
    }
  }

  return {
    word_count: wordCount,
    large_image_count: largeImageCount,
    video_count: videos + iframes + anchors,
    article_text_len: articleTextLen,
    title: document.title || '',
    text_excerpt: text.slice(0, 2000),
  };
}
"""

EXTRACT_IMAGES_JS = r"""
() => {
  const out = [];
  const seen = new Set();
  for (const img of document.images || []) {
    const url = img.currentSrc || img.src;
    if (!url) continue;
    if (seen.has(url)) continue;
    seen.add(url);
    out.push({
      url,
      width: img.naturalWidth || 0,
      height: img.naturalHeight || 0,
      alt: (img.alt || '').slice(0, 200),
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

def normalize_youtube(url: str) -> str:
    """Normalize youtube iframe/short URLs to canonical watch URLs (best-effort)."""
    m = re.match(r'^https?://(?:www\.)?youtube(?:-nocookie)?\.com/embed/([A-Za-z0-9_-]{6,})', url)
    if m:
        return f'https://www.youtube.com/watch?v={m.group(1)}'
    m = re.match(r'^https?://youtu\.be/([A-Za-z0-9_-]{6,})', url)
    if m:
        return f'https://www.youtube.com/watch?v={m.group(1)}'
    return url


def decide_mode(metrics: Dict[str, Any], text_threshold: int, forced: str) -> str:
    if forced in ('media', 'scroll-record'):
        return forced
    word_count = metrics.get('word_count', 0)
    large_imgs = metrics.get('large_image_count', 0)
    videos = metrics.get('video_count', 0)
    article_len = metrics.get('article_text_len', 0)
    is_text_heavy = (
        (word_count >= text_threshold and large_imgs + videos < 3)
        or article_len >= 1500
    )
    return 'scroll-record' if is_text_heavy else 'media'


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


def run_video_download(url: str, output_dir: Path) -> Dict[str, Any]:
    script = Path(__file__).resolve().parent / 'video-download.py'
    cmd = [sys.executable, str(script), '--url', url, '--output-dir', str(output_dir)]
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=900, check=False)
    except subprocess.TimeoutExpired:
        return {'success': False, 'error': 'video-download.py timed out (900s)'}
    try:
        return json.loads(completed.stdout.strip().splitlines()[-1])
    except Exception:
        return {
            'success': False,
            'error': f'video-download.py returned non-JSON (rc={completed.returncode}): '
                     f'{(completed.stdout + completed.stderr)[-400:]}',
        }


def find_subtitle_for(video_path: Path, files: List[str]) -> Optional[str]:
    """Pick a sidecar subtitle for a downloaded video, if yt-dlp produced one."""
    stem = video_path.stem
    for f in files:
        p = Path(f)
        if p.parent != video_path.parent:
            continue
        if p.stem.startswith(stem) and p.suffix.lower() in ('.vtt', '.srt'):
            return str(p.resolve())
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
    page_type = None
    mode_used = None
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

        mode_used = decide_mode(metrics, args.text_threshold, args.mode)
        page_type = 'text-heavy' if mode_used == 'scroll-record' else 'media-rich'
        log(f'  mode={mode_used}; metrics={metrics}')

        if mode_used == 'media':
            # extract image candidates
            raw_imgs = page.evaluate(EXTRACT_IMAGES_JS) or []
            kept = [
                im for im in raw_imgs
                if im.get('width', 0) >= args.min_image_size
                and im.get('height', 0) >= args.min_image_size
            ][: args.max_images_per_url]
            log(f'  images: {len(raw_imgs)} found, {len(kept)} pass size filter')

            for i, im in enumerate(kept, start=1):
                local = download_image(ctx.request, im['url'], images_dir, i)
                meta = {
                    'url': im['url'],
                    'width': im.get('width', 0),
                    'height': im.get('height', 0),
                    'alt': im.get('alt', ''),
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
                    log(f'  ytdlp: {v["url"]}')
                    res = run_video_download(v['url'], videos_dir)
                    if res.get('success'):
                        files = res.get('files', [])
                        video_files = [f for f in files if Path(f).suffix.lower() in ('.mp4', '.webm', '.mkv', '.m4a')]
                        meta['downloaded'] = bool(video_files)
                        if video_files:
                            video_path = Path(video_files[0])
                            meta['local_path'] = str(video_path.resolve())
                            meta['id'] = video_path.stem
                            sub = find_subtitle_for(video_path, files)
                            if sub:
                                meta['subtitle_path'] = sub
                        else:
                            meta['error'] = 'no video file produced'
                    else:
                        meta['downloaded'] = False
                        meta['error'] = res.get('error', 'unknown video-download error')
                else:  # native
                    native_idx += 1
                    local = download_native_video(ctx.request, v['url'], videos_dir, native_idx)
                    if local:
                        meta['downloaded'] = True
                        meta['local_path'] = str(local.resolve())
                        meta['id'] = local.stem
                    else:
                        meta['downloaded'] = False
                        meta['error'] = 'native download failed'
                videos_meta.append(meta)

        # close context BEFORE scroll-record (record needs its own context)
    finally:
        try:
            ctx.close()
        except Exception:
            pass

    if mode_used == 'scroll-record':
        capped = min(60, max(5, args.scroll_duration))
        record_path, method = primary_scroll_record(
            browser, url, viewport, capped, args.page_load_timeout, slug_dir
        )
        if record_path is None:
            log(f'  primary scroll-record failed ({method}); trying CDP screencast fallback')
            record_path, method = cdp_screencast_record(
                browser, url, viewport, capped, args.page_load_timeout, slug_dir
            )
        if record_path is None:
            return {
                'url': url,
                'slug': slug,
                'success': False,
                'error': f'scroll recording failed ({method})',
            }
        dur = probe_duration(record_path) or float(capped)
        scroll_recording = {
            'local_path': str(record_path.resolve()),
            'duration_sec': round(dur, 3),
            'method': method,
        }
        log(f'  scroll-record OK via {method}: {record_path}')

    entry = {
        'url': url,
        'slug': slug,
        'success': True,
        'page_type': page_type,
        'mode': mode_used,
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

def main() -> None:
    args = parse_args()
    try:
        viewport = parse_viewport(args.viewport)
    except ValueError as exc:
        fail(str(exc), exit_code=2)

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # dedupe URL list preserving order, and reject any URL whose scheme isn't http(s).
    # Without this guard `harvest-pages.py file:///etc/passwd` or `chrome://settings`
    # would be passed straight to Playwright and could read local files or trigger
    # privileged Chrome UIs.
    seen = set()
    urls = []
    bad_urls: List[Dict[str, str]] = []
    for u in args.urls:
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
        urls.append(u)
    if not urls:
        fail(
            'no http(s) URLs to harvest after scheme filtering. '
            f'Rejected: {[b["url"] for b in bad_urls]}',
            exit_code=2,
        )
    log(f'Batch size: {len(urls)} URL(s); output={output_dir}'
        + (f' (rejected {len(bad_urls)} non-http(s) URL(s))' if bad_urls else ''))

    # ensure Playwright is available
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except Exception:
        fail(
            'playwright not installed; run: pip install playwright '
            '(no `playwright install chromium` needed — uses system Chrome over CDP)'
        )

    # ensure Chrome is up on CDP
    ensure_cdp(args)

    from playwright.sync_api import sync_playwright

    entries: List[Dict[str, Any]] = []
    succeeded = 0
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.connect_over_cdp(args.cdp_url)
        except Exception as exc:
            fail(f'connect_over_cdp({args.cdp_url}) failed: {exc}')

        log(f'Connected to Chrome over CDP ({args.cdp_url})')

        used_slugs = set()
        for url in urls:
            slug = slugify_url(url)
            # collision-proof against accidental duplicate slugs
            base, n = slug, 2
            while slug in used_slugs:
                slug = f'{base}-{n}'
                n += 1
            used_slugs.add(slug)

            slug_dir = output_dir / slug
            slug_dir.mkdir(parents=True, exist_ok=True)
            try:
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

        try:
            browser.close()  # detach the Playwright client (does NOT kill Chrome — we connected over CDP)
        except Exception:
            pass

    batch_success = succeeded > 0
    manifest = {
        'success': batch_success,
        'output_dir': str(output_dir),
        'batch_size': len(urls),
        'succeeded': succeeded,
        'entries': entries,
    }
    if bad_urls:
        manifest['rejected'] = bad_urls
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
    log(f'Done. {succeeded}/{len(urls)} entries succeeded.')
    if not batch_success:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
