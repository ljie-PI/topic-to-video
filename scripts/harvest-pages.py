#!/usr/bin/env python3
r"""topic-to-video skill 的批量 URL 素材抓取器。

对浏览器打开的每个 URL，无条件抽取：
  - naturalWidth >= --min-image-width（默认 500）且
    naturalHeight >= --min-image-height（默认 300）的位图
  - SVG 图片（<img src="*.svg"> 和行内 <svg> 元素都算）——它们绕过宽高阈值，
    因为矢量图常常只声明极小的固有尺寸
  - 所有内嵌 <video> 元素，以及 YouTube / Bilibili 的 iframe / 链接

默认会为每个渲染过的页面录制一段滚动视频（用 --no-scroll-record 关闭）。

直接的 YouTube / Bilibili 观看页 URL 会被短路：它们以 `download_required: true`
记入 manifest，由 agent 调用 video-download.py；这些 URL 不打开浏览器，因此图片
抽取与滚动录制对它们不适用。

浏览器模型：通过 CDP（默认 http://localhost:9222）连到一个 Chrome 进程。若没有
可达的 CDP 响应者，则自动以 --user-data-dir=<profile-dir> 启动系统 Chrome。所需的
profile 与 gemini-deep-research.py 共享。退出时 Chrome 保持运行，以便后续调用立即
重连。复用 CDP 时，被忽略的显式启动参数会在 stderr 以及 manifest 的
chrome.ignored_flags 字段中报告。

用法：
  python3 harvest-pages.py \
    --urls-file "{work_dir}/{topic}/harvest-urls.txt" \
    --output-dir {work_dir}/{topic}/harvest_page/ \
    --profile-dir {work_dir}/chrome_profile

  短列表也可以直接放在命令行上（与 --urls-file 互斥）：
  python3 harvest-pages.py --urls https://example.com/ ...

输出约定：
  stdout : 本次批次的结果 JSON（`success` / `entries` / `chrome` 等），
           不是磁盘 manifest 的原样输出；
  manifest: <output-dir>/manifest.json（v2，保留历史批次与论文 entry）
  stderr : 带 `[harvest-pages]` 前缀的人类可读进度
  exit   : 0 成功（>=1 条成功），1 运行时错误
           （CDP 启动失败或全部条目失败），2 参数非法
           （含 --urls-file 读不到、为空）

登录态：每个 URL 的采集 context 都会继承共享 profile 默认 context 的 cookies；
profile 里已打开在该站点（同 origin）的标签页还会提供它的 localStorage。
新建的 context 不共享 cookies，不显式继承就抓不到登录后的页面。不会关闭或
改动用户的默认 context 与标签页，也不写任何 auth-state 文件。
"""

import argparse
import base64
import mimetypes
import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

import chrome_cdp
import cli
import harvest_manifest
import media

TOOL_NAME = 'harvest-pages'
DEFAULT_CDP_URL = 'http://localhost:9222'
CHROME_WINDOW_SIZE = '1680,1680'
USER_AGENT = (
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
)


# -----------------------------------------------------------------------------
# I/O 辅助函数
# -----------------------------------------------------------------------------

log = cli.make_logger(TOOL_NAME)


def parse_args() -> argparse.Namespace:
    p = cli.JsonArgumentParser(TOOL_NAME, description='Batch URL material harvester (Playwright over CDP).')
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument('--urls', nargs='+', help='One or more URLs to harvest.')
    source.add_argument('--urls-file', dest='urls_file',
                        help='UTF-8 file with one URL per line (blank lines ignored). '
                             'Mutually exclusive with --urls.')
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
    p.add_argument('--profile-dir', required=True,
                   help='Chrome profile dir (required; use the shared work_dir profile).')
    p.add_argument('--chrome-path', default=None,
                   help='Path to Chrome executable. Auto-detected if unset.')
    p.add_argument('--headless', default=None, choices=('auto', 'on', 'off'),
                   help="Chrome headless mode: auto, on, or off (default off).")
    p.add_argument('--no-sandbox', action='store_true', default=None,
                   help='Pass --no-sandbox to Chrome (auto-enabled when running as root or inside a container).')
    p.add_argument('--no-continue-on-error', action='store_true',
                   help='Stop the batch on the first per-URL failure. Default off (best-effort).')
    args = p.parse_args()
    args.explicit_headless = args.headless
    args.headless = args.headless or 'off'
    return args


def read_urls_file(path_value: str) -> Tuple[List[str], Optional[str]]:
    """读取待抓 URL 清单：UTF-8（允许 BOM），一行一个，忽略空行。

    返回 (urls, error)。错误在启动 Chrome 之前就交给调用方，使参数问题
    不会先拉起一个浏览器再失败。
    """
    path = Path(path_value).expanduser()
    try:
        text = path.read_text(encoding='utf-8-sig')
    except FileNotFoundError:
        return [], f'--urls-file not found: {path}'
    except UnicodeDecodeError as exc:
        return [], f'--urls-file is not valid UTF-8: {path} ({exc.reason})'
    except OSError as exc:
        return [], f'--urls-file could not be read: {path} ({exc})'
    urls = [line.strip() for line in text.splitlines()]
    urls = [url for url in urls if url]
    if not urls:
        return [], f'--urls-file contains no URLs: {path}'
    return urls, None


def collect_urls(args: argparse.Namespace) -> Tuple[List[str], Optional[str]]:
    """把两种输入形式归一成同一个 URL 列表，后续处理完全一致。"""
    if args.urls_file:
        return read_urls_file(args.urls_file)
    return list(args.urls), None


def parse_viewport(s: str) -> Tuple[int, int]:
    m = re.match(r'^(\d+)x(\d+)$', s)
    if not m:
        raise ValueError(f'Invalid --viewport {s!r}, expected WxH (e.g. 1280x720)')
    return int(m.group(1)), int(m.group(2))


# -----------------------------------------------------------------------------
# 页面级辅助函数（在 Playwright 上下文内运行）
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
  // 标准的 <img> 元素（包括 <img src="*.svg">）
  for (const img of document.images || []) {
    const url = img.currentSrc || img.src;
    if (!url) continue;
    if (seen.has(url)) continue;
    seen.add(url);
    const isSvg = /\.svg(\?|#|$)/i.test(url);
    let w = img.naturalWidth || 0;
    let h = img.naturalHeight || 0;
    // SVG 的 <img> 常常 naturalWidth=0；退回用渲染尺寸
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
  // 行内 <svg> 元素 —— 序列化成标记
  for (const svg of document.querySelectorAll('svg')) {
    const rect = svg.getBoundingClientRect();
    if (rect.width < 40 || rect.height < 40) continue;  // 跳过极小的图标
    const markup = new XMLSerializer().serializeToString(svg);
    if (markup.length < 100) continue;  // 跳过琐碎 / 空的 SVG
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
  // 带 src 或 <source> 的 <video>
  for (const v of document.querySelectorAll('video')) {
    const src = v.currentSrc || v.src || '';
    if (src) push(src, 'native');
    for (const s of v.querySelectorAll('source')) {
      if (s.src) push(s.src, 'native');
    }
  }
  // 已知平台对应的 iframe
  for (const f of document.querySelectorAll('iframe')) {
    const u = f.src || '';
    if (!u) continue;
    if (/youtube\.com|youtu\.be|youtube-nocookie\.com/.test(u)) push(u, 'youtube');
    else if (/player\.bilibili\.com/.test(u)) push(u, 'bilibili');
  }
  // 指向 YouTube / Bilibili 观看页的链接
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
  // 顶部短暂停顿
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
        // 底部短暂停顿
        setTimeout(resolve, 600);
      }
    };
    tick();
  });
}
"""


# -----------------------------------------------------------------------------
# 单个 URL 的处理
# -----------------------------------------------------------------------------

# YouTube / Bilibili URL 模式目录。由 `normalize_youtube`（把 embed / 短链 /
# youtu.be 形式转成规范的观看 URL）与 `detect_watchable_platform`（判断某 URL
# 是否能不经浏览器直接由 yt-dlp 抓取）共用。只编译一次；host 部分不区分大小写。
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
    """把 youtube 的 iframe / 短链 URL 规范化为观看 URL（尽力而为）。

    host 匹配不区分大小写（RFC 3986 允许大写主机名）；
    视频 ID 捕获组保留大小写。
    """
    for pat in _YT_NORMALIZE_PATTERNS:
        m = pat.match(url)
        if m:
            return f'https://www.youtube.com/watch?v={m.group(1)}'
    return url


def detect_watchable_platform(url: str) -> Optional[str]:
    """当该 URL 是 video-download.py（yt-dlp）能直接抓取的可观看视频页时，
    返回 'youtube' 或 'bilibili'，否则返回 None。

    匹配（host 比较不区分大小写）：
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
        if suffix in harvest_manifest.VIDEO_EXTS:
            ext = suffix
        path = dest_dir / f'native_{index:03d}{ext}'
        path.write_bytes(body)
        return path
    except Exception as exc:
        log(f'  video {index}: failed: {exc}')
        return None


# -----------------------------------------------------------------------------
# 滚动录制
# -----------------------------------------------------------------------------

DEFAULT_PORTS = {'http': 80, 'https': 443}

# 在同一次同步执行里先核对 location.origin 再读 localStorage：标签页可能在选中之后
# 跳去别的站点，分开两步读就会把那个站点的数据当成这个 origin 的。
LOCAL_STORAGE_JS = """(expectedOrigin) => {
  if (location.origin !== expectedOrigin) {
    return {origin: location.origin, entries: null};
  }
  const entries = {};
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    entries[key] = localStorage.getItem(key);
  }
  return {origin: location.origin, entries};
}"""


def page_origin(url: str) -> Optional[str]:
    """把 URL 归成 storage 用的 origin（scheme://host[:port]）。

    按 origin 语义规范化，不比较原始 netloc：host 小写、去掉 userinfo、
    省略该 scheme 的默认端口、IPv6 加方括号。否则 `https://EXAMPLE.com` 或
    `https://example.com:443` 会被当成与 `https://example.com` 不同的站点，
    它们的 localStorage 登录态会被静默丢掉。
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    scheme = (parsed.scheme or '').lower()
    if not scheme:
        return None
    try:
        host = parsed.hostname
        port = parsed.port
    except ValueError:  # 非法端口（如 http://example.com:abc/）
        return None
    if not host:
        return None
    host = host.lower()
    if ':' in host:  # IPv6 字面量，urlparse 已去掉方括号
        host = f'[{host}]'
    if port is not None and port != DEFAULT_PORTS.get(scheme):
        return f'{scheme}://{host}:{port}'
    return f'{scheme}://{host}'


def read_local_storage(profile_context, origin: str) -> Tuple[Dict[str, str], Optional[str]]:
    """读这个 origin 在共享 profile 里已加载的 localStorage。

    不能直接用 `context.storage_state()`：跨连接（另一个进程读同一个 CDP
    Chrome）时它只收集本连接跟踪过的导航，登录页早已打开，origins 会是空的。

    只复用 profile 里已经打开在该 origin 的标签页，不新建、不导航：
    没有打开的标签页时返回空快照（cookie 仍然生效），以免为读会话而
    额外请求站点首页。

    标签页选中后可能在读取前跳去另一个站点，所以核对 origin 与读取数据放在
    同一次 evaluate 里；对不上就丢弃结果并告警，不把那个站点的会话数据贴上
    这个 origin 的标签。
    """
    page = next((p for p in profile_context.pages if page_origin(p.url) == origin), None)
    if page is None:
        return {}, None
    try:
        result = page.evaluate(LOCAL_STORAGE_JS, origin) or {}
    except Exception as exc:
        return {}, f'{type(exc).__name__}: {exc}'
    actual_origin = result.get('origin')
    if actual_origin != origin:
        return {}, f'page navigated to {actual_origin!r} before the read'
    entries = result.get('entries')
    if not isinstance(entries, dict):
        return {}, f'unexpected localStorage payload from {actual_origin!r}'
    return {str(name): str(value) for name, value in entries.items()}, None


def profile_storage_state(profile_context, origins: Sequence[str] = ()
                         ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """把共享 profile 的登录态打包成新建 context 可用的 storage state。

    新建的 Playwright context 不共享其它 context 的 cookies / localStorage，
    所以复用同一个 Chrome 进程不等于复用登录态：cookies 与待采集 origin 的
    localStorage 必须显式传进新的采集 context。全程只读，不改动用户已有的
    context 与标签页。

    返回 (state, warning)。没有任何可用登录态时 state 为 None；某一部分读取
    失败时 warning 说明原因，其余部分仍可使用。
    """
    if profile_context is None:
        return None, None
    try:
        cookies = profile_context.cookies()
    except Exception as exc:
        return None, f'could not read profile cookies ({type(exc).__name__}: {exc})'
    state_origins: List[Dict[str, Any]] = []
    problems: List[str] = []
    for origin in origins:
        entries, error = read_local_storage(profile_context, origin)
        if error:
            problems.append(f'{origin}: {error}')
        elif entries:
            state_origins.append({
                'origin': origin,
                'localStorage': [{'name': name, 'value': value} for name, value in entries.items()],
            })
    warning = '; '.join(problems) or None
    if not cookies and not state_origins:
        return None, warning
    return {'cookies': cookies, 'origins': state_origins}, warning


def new_harvest_context(browser, viewport: Tuple[int, int], record_dir: Optional[Path] = None,
                        storage_state: Optional[Dict[str, Any]] = None):
    """创建 harvest 与兜底路径共用的那一份 context 配置。

    `storage_state` 是调用方从同一个 profile context 读到的快照；主路径、录屏
    重试路径和 CDP 兜底路径传同一份，以免兜底重新变成匿名页。导入被拒绝时
    退回匿名抓取并告警，不因单条 cookie 使整批失败，也不假装已登录。
    """
    vp_w, vp_h = viewport
    options: Dict[str, Any] = {
        'viewport': {'width': vp_w, 'height': vp_h},
        'user_agent': USER_AGENT,
        'locale': 'zh-CN',
        'extra_http_headers': {'Accept-Language': 'zh-CN,en;q=0.9'},
    }
    if record_dir is not None:
        record_dir.mkdir(parents=True, exist_ok=True)
        options.update({
            'record_video_dir': str(record_dir),
            'record_video_size': {'width': vp_w, 'height': vp_h},
        })
    if storage_state:
        try:
            return browser.new_context(**options, storage_state=storage_state)
        except Exception as exc:
            log(f'  profile login state rejected ({type(exc).__name__}: {exc}); '
                f'continuing anonymously')
    return browser.new_context(**options)


def primary_scroll_record(ctx, page, scroll_duration: int,
                          output_dir: Path) -> Tuple[Optional[Path], Optional[str]]:
    """录制已加载的 harvest 页面，然后冲刷出它的视频。"""
    rec_dir = output_dir / 'recording'
    try:
        page.evaluate(SCROLL_RECORD_JS, scroll_duration * 1000)
    finally:
        ctx.close()  # 冲刷出 .webm

    # 找出 rec_dir 中最新的 .webm
    webms = sorted(rec_dir.glob('*.webm'), key=lambda p: p.stat().st_mtime, reverse=True)
    if not webms:
        return None, 'playwright_no_video'
    target = rec_dir / f'scroll-{int(time.time())}.webm'
    webms[0].rename(target)
    return target, 'playwright'


def cdp_screencast_record(browser, url: str, viewport: Tuple[int, int], scroll_duration: int,
                          page_load_timeout: int, output_dir: Path,
                          storage_state: Optional[Dict[str, Any]] = None) -> Tuple[Optional[Path], Optional[str]]:
    try:
        media.ensure_binary(os.environ.get('FFMPEG_BIN', 'ffmpeg'))
    except media.MediaToolMissing:
        return None, 'cdp_no_ffmpeg'
    rec_dir = output_dir / 'recording'
    frames_dir = rec_dir / 'frames'
    frames_dir.mkdir(parents=True, exist_ok=True)
    vp_w, vp_h = viewport

    ctx = new_harvest_context(browser, viewport, storage_state=storage_state)
    frame_idx = [0]
    try:
        page = ctx.new_page()
        page.set_default_timeout(page_load_timeout * 1000)
        page.goto(url, wait_until='domcontentloaded', timeout=page_load_timeout * 1000)
        log(f'loaded {url}')
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
        media.run_ffmpeg(cmd[1:], timeout=180)
    except media.FfmpegError as exc:
        log(f'  ffmpeg failed: {exc.stderr_tail[:300]}')
        return None, 'ffmpeg_failed'

    # 清理帧文件
    try:
        shutil.rmtree(frames_dir)
    except Exception:
        pass

    return out_mp4, 'cdp_screencast'


# -----------------------------------------------------------------------------
# 单个 URL 的流水线
# -----------------------------------------------------------------------------

def harvest_one(browser, url: str, slug: str, slug_dir: Path, args: argparse.Namespace,
                viewport: Tuple[int, int],
                storage_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    log(f'-- {slug} -- {url}')
    images_dir = slug_dir / 'images'
    videos_dir = slug_dir / 'videos'
    images_dir.mkdir(parents=True, exist_ok=True)
    videos_dir.mkdir(parents=True, exist_ok=True)

    record_dir = slug_dir / 'recording' if args.scroll_record else None
    ctx = new_harvest_context(browser, viewport, record_dir=record_dir, storage_state=storage_state)
    metrics = {}
    title = ''
    text_excerpt = ''
    images_meta: List[Dict[str, Any]] = []
    videos_meta: List[Dict[str, Any]] = []
    scroll_recording: Optional[Dict[str, Any]] = None
    primary_error: Optional[Exception] = None
    try:
        try:
            page = ctx.new_page()
        except Exception as exc:
            if not args.scroll_record:
                raise
            # Playwright 录像需要它自带的 ffmpeg。当这个可选二进制不可用时，
            # 保留历史上一直存在的 CDP 兜底路径。
            primary_error = exc
            log(f'  primary scroll-record raised ({type(exc).__name__}: {exc})')
            ctx.close()
            ctx = new_harvest_context(browser, viewport, storage_state=storage_state)
            page = ctx.new_page()
        page.set_default_timeout(args.page_load_timeout * 1000)
        page.goto(url, wait_until='domcontentloaded', timeout=args.page_load_timeout * 1000)
        log(f'loaded {url}')
        try:
            page.wait_for_load_state('networkidle', timeout=5000)
        except Exception:
            pass

        # 保存页面源码以便调试
        try:
            (slug_dir / 'page-source.html').write_text(page.content(), encoding='utf-8', errors='replace')
        except Exception as exc:
            log(f'  page-source.html save failed: {exc}')

        # 自动滚动，把懒加载的图片实体化出来
        try:
            page.evaluate(AUTO_SCROLL_JS)
        except Exception as exc:
            log(f'  autoscroll failed: {exc}')

        metrics = page.evaluate(METRICS_JS) or {}
        title = metrics.pop('title', '')
        text_excerpt = metrics.pop('text_excerpt', '')
        log(f'  metrics={metrics}')

        # 抽取图片候选
        raw_imgs = page.evaluate(EXTRACT_IMAGES_JS) or []
        kept = [
            im for im in raw_imgs
            if im.get('type') in ('svg', 'inline-svg')  # SVG 绕过尺寸过滤
            or (im.get('width', 0) >= args.min_image_width
                and im.get('height', 0) >= args.min_image_height)
        ][: args.max_images_per_url]
        log(f'  images: {len(raw_imgs)} found, {len(kept)} pass size filter')

        for i, im in enumerate(kept, start=1):
            img_type = im.get('type', 'raster')
            if img_type == 'inline-svg':
                # 直接把行内 SVG 的标记存成文件
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

        # 抽取视频候选
        raw_vids = page.evaluate(EXTRACT_VIDEOS_JS) or []
        # 按规范化后的 url 去重
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
                # 外部平台：只登记 URL；由 agent 在后续步骤调用
                # video-download.py（见 references/phases/04-material-harvest.md 的 Phase 4.b）。
                meta['download_required'] = True
                meta['suggested_output_dir'] = str(videos_dir.resolve())
                log(f'  external video listed (download_required): {v["url"]}')
            else:  # 原生 HTML5 <video>
                native_idx += 1
                local = download_native_video(ctx.request, v['url'], videos_dir, native_idx)
                if local:
                    meta['download_required'] = False
                    meta['downloaded'] = True
                    meta['local_path'] = str(local.resolve())
                    meta['id'] = local.stem
                    try:
                        probed = media.probe(local)
                    except (media.MediaProbeError, media.MediaToolMissing) as exc:
                        log(f'  native video probe failed: {exc}')
                        probed = {'width': None, 'height': None, 'duration_seconds': None}
                    meta.update({
                        'width': probed['width'],
                        'height': probed['height'],
                        'duration_seconds': probed['duration_seconds'],
                    })
                else:
                    meta['download_required'] = False
                    meta['downloaded'] = False
                    meta['error'] = 'native download failed'
            videos_meta.append(meta)

        if args.scroll_record:
            capped = min(60, max(5, args.scroll_duration))
            # 抽取与 Playwright 录制共用这个页面和 context。
            # 只有录制失败才允许打开兜底 context 并重新加载。
            record_path: Optional[Path] = None
            method = 'not-attempted'
            if primary_error is None:
                try:
                    record_path, method = primary_scroll_record(ctx, page, capped, slug_dir)
                except Exception as exc:
                    log(f'  primary scroll-record raised ({type(exc).__name__}: {exc})')
                    record_path, method = None, f'{type(exc).__name__}'
            else:
                method = f'{type(primary_error).__name__}'
            if record_path is None:
                log(f'  primary scroll-record failed ({method}); trying CDP screencast fallback')
                try:
                    record_path, method = cdp_screencast_record(
                        browser, url, viewport, capped, args.page_load_timeout, slug_dir, storage_state
                    )
                except Exception as exc:
                    log(f'  CDP fallback raised ({type(exc).__name__}: {exc})')
                    record_path, method = None, f'{type(exc).__name__}'
            if record_path is None:
                log(f'  scroll-record failed ({method}); continuing without recording')
            else:
                try:
                    dur = media.probe_duration(record_path)
                except (media.MediaProbeError, media.MediaToolMissing):
                    dur = float(capped)
                scroll_recording = {
                    'local_path': str(record_path.resolve()),
                    'duration_seconds': round(dur, 3),
                    'width': viewport[0],
                    'height': viewport[1],
                    'method': method,
                }
                log(f'  scroll-record OK via {method}: {record_path}')
    finally:
        try:
            ctx.close()
        except Exception:
            pass

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
# 驱动
# -----------------------------------------------------------------------------

def partition_urls(
    raw_urls: List[str],
) -> Tuple[List[Tuple[str, str, Optional[str]]], List[Dict[str, str]]]:
    """对 `raw_urls` 去重、丢弃非 http(s) 的、给每个分配唯一 slug，并
    判断每个 URL 是否是 yt-dlp 能抓取的观看页。

    返回 (items, bad_urls)，其中：
      - items[i] = (url, slug, platform_or_None)。`platform_or_None` 是
        `detect_watchable_platform` 的返回值，非 None 表示走短路路径
        （不做 Playwright 渲染）。
      - bad_urls 是被拒绝的 `{url, error}` 条目列表，manifest 会在
        `rejected` 下报告它们。

    scheme 守卫会拒绝 `file://`、`chrome://`、`javascript:` 等，使调用方无法诱使
    Playwright 读取本地文件或触发需要特权的 Chrome 界面。
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
        s = harvest_manifest.slug_for_url(u)
        base, n = s, 2
        while s in used_slugs:
            s = f'{base}-{n}'
            n += 1
        used_slugs.add(s)
        items.append((u, s, detect_watchable_platform(u)))
    return items, bad_urls


def main() -> None:
    args = parse_args()
    try:
        viewport = parse_viewport(args.viewport)
    except ValueError as exc:
        cli.fail(TOOL_NAME, str(exc), exit_code=2)

    output_dir = Path(args.output_dir).expanduser().resolve()

    raw_urls, urls_error = collect_urls(args)
    if urls_error:
        cli.fail(TOOL_NAME, urls_error, exit_code=2)
    if args.urls_file:
        log(f'Loaded {len(raw_urls)} URL(s) from {Path(args.urls_file).expanduser()}')

    items, bad_urls = partition_urls(raw_urls)
    if not items:
        cli.fail(TOOL_NAME,
            'no http(s) URLs to harvest after scheme filtering. '
            f'Rejected: {[b["url"] for b in bad_urls]}',
            exit_code=2,
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    log(f'Batch size: {len(items)} URL(s); output={output_dir}'
        + (f' (rejected {len(bad_urls)} non-http(s) URL(s))' if bad_urls else ''))

    # 确保 Playwright 可用（只在至少一个 URL 需要渲染时才必需）
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except Exception:
        # 把硬失败推迟到我们确知真的需要浏览器时。
        sync_playwright = None  # type: ignore

    needs_chrome = any(plat is None for _, _, plat in items)
    direct_count = sum(1 for _, _, plat in items if plat is not None)
    if direct_count:
        log(f'{direct_count}/{len(items)} URL(s) recognized as direct video pages — '
            f'these will be listed without browser rendering.')

    entries: List[Dict[str, Any]] = []
    succeeded = 0

    chrome_session = None
    browser = None
    chrome_metadata = {
        'cdp_url': args.cdp_url,
        'reused': False,
        'ignored_flags': [],
    }
    if needs_chrome:
        if sync_playwright is None:
            cli.fail(TOOL_NAME,
                'playwright not installed; run: pip install playwright '
                '(no `playwright install chromium` needed — uses system Chrome over CDP)'
            )
        try:
            chrome_session = chrome_cdp.attach_or_launch(
                args.cdp_url,
                args.profile_dir,
                headless=args.explicit_headless,
                window_size=CHROME_WINDOW_SIZE,
                no_sandbox=args.no_sandbox,
                chrome_path=args.chrome_path,
            )
        except Exception as exc:
            cli.fail(TOOL_NAME, str(exc))
        browser = chrome_session.browser
        chrome_metadata = chrome_session.metadata()
        log(f'Connected to Chrome over CDP ({args.cdp_url})')
    else:
        log('No URL requires browser rendering — skipping Chrome/CDP setup.')

    # 登录态必须在创建任何采集 context 之前从 profile 的默认 context 读快照，
    # 且整批只读一次：主路径、录屏重试路径与 CDP 兜底共用同一份快照。
    profile_context = browser.contexts[0] if browser is not None and browser.contexts else None
    rendered_origins = sorted({
        origin
        for url, _, platform in items
        if platform is None and (origin := page_origin(url))
    })
    storage_state, state_warning = profile_storage_state(profile_context, rendered_origins)
    if state_warning:
        log(f'warning: incomplete profile login state ({state_warning})')
    if storage_state is None and profile_context is not None:
        log('No login state in the shared Chrome profile — harvesting anonymously.')
    elif storage_state is not None:
        log(f'Reusing the shared Chrome profile login state '
            f'({len(storage_state.get("cookies") or [])} cookie(s), '
            f'{len(storage_state.get("origins") or [])} origin(s)).')

    try:
        for url, slug, platform in items:
            slug_dir = output_dir / slug
            slug_dir.mkdir(parents=True, exist_ok=True)
            try:
                if platform is not None:
                    # 短路：不做 Playwright 导航。agent 会针对 `videos[]` 中登记的
                    # URL 调用 video-download.py（见 references/phases/04-material-harvest.md 的 Phase 4.b）。
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
                    entry = harvest_one(browser, url, slug, slug_dir, args, viewport, storage_state)
            except Exception as exc:
                log(f'  fatal per-URL error: {exc}')
                entry = {'url': url, 'slug': slug, 'success': False, 'error': str(exc)}

            if entry.get('success'):
                succeeded += 1
            entries.append(entry)

            if not entry.get('success') and args.no_continue_on_error:
                log('--no-continue-on-error set; stopping batch')
                break
    finally:
        if chrome_session is not None:
            try:
                chrome_session.close()
            except Exception:
                pass

    saved = harvest_manifest.upsert_entries(output_dir, entries)
    saved = harvest_manifest.record_harvest_batch(output_dir, {
        'urls': [entry['url'] for entry in entries],
        'succeeded': succeeded,
        'failed': len(entries) - succeeded,
        'rejected': bad_urls,
    })
    by_slug = {entry.get('slug'): entry for entry in saved['entries']}
    batch_entries = [by_slug[entry['slug']] for entry in entries]
    pending_downloads = harvest_manifest.pending_downloads(batch_entries)

    batch_success = succeeded > 0
    result = {
        'success': batch_success,
        'output_dir': str(output_dir),
        'batch_size': len(items),
        'succeeded': succeeded,
        'chrome': chrome_metadata,
        'entries': batch_entries,
    }
    if bad_urls:
        result['rejected'] = bad_urls
    if pending_downloads:
        result['pending_downloads'] = pending_downloads
    if not batch_success:
        result['error'] = 'All URLs failed; see entries[].error for details.'

    cli.print_json(result)
    log(f'Done. {succeeded}/{len(items)} entries succeeded.')
    if not batch_success:
        raise SystemExit(1)


if __name__ == '__main__':
    raise SystemExit(cli.run(main, TOOL_NAME))
