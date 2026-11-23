"""Real-Chrome integration tests for the explicit module init interface.

The fixture mounts module HTML through data-composition-src and wires each
migrated module's sibling .mjs with a minimal adapter — the same plain-browser
contract documented in modules/modules.md: params come from
data-variable-values, data from window.VIDEO, and every module owns a paused
timeline in local seconds. No HyperFrames global is required to initialise or
seek: the adapter converts video seconds to local seconds per mount
(time - data-start), awaits `ready`, seeks the timeline, then calls `seek(t)`
for self-drawing modules like presenter.

Presenter performs its real image build, simulation, and WebGL rendering in Chrome
through the same init interface, including the asynchronous `ready`
resolution and per-time-point `seek` bridging.
"""
from __future__ import annotations

import json
import shutil
import threading
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

import chrome_cdp

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_JS = (ROOT / 'scripts/check-composition-snapshot.js').read_text(encoding='utf-8')
pytestmark = pytest.mark.usefixtures('require_chrome')


# The production modules use GSAP's paused-timeline API. This deliberately
# small deterministic implementation supports only the set/fromTo/to/seek calls
# they make. Reapplying operations from each element's original inline style is
# important: it exercises both forward and backward seeks rather than merely
# checking the final state after monotonically playing the timeline. Plain
# object targets (star count-up, README scroll) interpolate their numeric
# fields and fire onUpdate like GSAP does.
TIMELINE_SEEKER = r"""
(() => {
  const isElement = (target) => target instanceof Element;
  const asTargets = (target) => Array.isArray(target) ? target : [target];
  const cssName = (name) => name.replace(/[A-Z]/g, (c) => '-' + c.toLowerCase());
  const numeric = (value, fallback = 0) => {
    const parsed = parseFloat(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  };
  const put = (target, name, value) => {
    if (!isElement(target)) return;
    if (name === 'y') {
      target.style.transform = `translateY(${numeric(value)}px)`;
    } else {
      target.style.setProperty(cssName(name), String(value));
    }
  };
  const current = (target, name) => {
    if (!isElement(target)) return 0;
    if (name === 'y') return numeric(target.style.transform);
    return numeric(target.style.getPropertyValue(cssName(name)),
      numeric(getComputedStyle(target).getPropertyValue(cssName(name))));
  };
  const mix = (from, to, progress) => {
    if (typeof from === 'number' && typeof to === 'number') {
      return from + (to - from) * progress;
    }
    if (typeof from === 'string' && typeof to === 'string') {
      const unit = from.endsWith('px') && to.endsWith('px') ? 'px' : '';
      if (unit) return String(numeric(from) + (numeric(to) - numeric(from)) * progress) + unit;
    }
    return progress < 1 ? from : to;
  };

  class Timeline {
    constructor() { this.operations = []; this.targets = new Map(); this._time = 0; }
    remember(target) {
      for (const item of asTargets(target)) {
        if (isElement(item) && !this.targets.has(item)) {
          this.targets.set(item, item.getAttribute('style') || '');
        }
      }
    }
    set(target, values, at) {
      this.remember(target);
      this.operations.push({ kind: 'set', target, values, at });
      return this;
    }
    fromTo(target, from, to, at) {
      this.remember(target);
      this.operations.push({ kind: 'fromTo', target, from, to, at });
      return this;
    }
    to(target, to, at) {
      this.remember(target);
      this.operations.push({ kind: 'to', target, to, at });
      return this;
    }
    time() { return this._time; }
    clear() {
      this.operations = [];
      this.targets.clear();
      return this;
    }
    pause() { return this; }
    kill() { return this; }
    seek(time) {
      this._time = numeric(time, 0);
      for (const [target, style] of this.targets) target.setAttribute('style', style);
      const operations = this.operations.map((operation, index) => ({ operation, index }))
        .sort((a, b) => a.operation.at - b.operation.at || a.index - b.index);
      for (const { operation } of operations) {
        const { kind, target, at } = operation;
        if (time < at) continue;
        for (const item of asTargets(target)) {
          if (kind === 'set') {
            if (isElement(item)) {
              for (const [name, value] of Object.entries(operation.values)) put(item, name, value);
            } else {
              Object.assign(item, operation.values);
            }
            continue;
          }
          const duration = numeric(operation.to.duration);
          const progress = duration > 0 ? Math.max(0, Math.min(1, (time - at) / duration)) : 1;
          if (kind === 'fromTo') {
            for (const [name, value] of Object.entries(operation.to)) {
              if (name === 'duration' || name === 'ease' || name === 'onUpdate') continue;
              if (isElement(item)) put(item, name, mix(operation.from[name], value, progress));
              else item[name] = mix(operation.from[name], value, progress);
            }
          } else {
            for (const [name, value] of Object.entries(operation.to)) {
              if (name === 'duration' || name === 'ease' || name === 'onUpdate') continue;
              if (isElement(item)) put(item, name, mix(current(item, name), value, progress));
              else item[name] = mix(item[name], value, progress);
            }
          }
          if (!isElement(item) && typeof operation.to.onUpdate === 'function') {
            operation.to.onUpdate();
          }
        }
      }
      return this;
    }
  }
  window.gsap = { timeline: () => new Timeline() };
})();
"""

MOUNTER = r"""
// Minimal adapter, mirroring the generated-project wiring documented in
// modules/modules.md: the migrated modules never see HyperFrames globals.
// Video seconds from the caller are converted to local seconds per mount
// (time - data-start); the module data times (acts, envelope, placements)
// are local seconds of that mount.
window.__instances = [];   // { name, host, start, instance } — owned by this adapter
window.__mountErrors = [];
function modulePayload(name, params) {
  const V = window.VIDEO || {};
  switch (name) {
    case 'caption-bar':
      return { captions: V[params.data || 'captions'] || [],
               captionSegments: V[params.layoutData || 'captionSegments'] || [] };
    case 'nav-bar':
      return V[params.data || 'tabs'] || [];
    case 'tile-wipe':
      return V[params.data || 'cuts'] || [];
    case 'trending-overview':
      return V[params.data || 'trending'] || {};
    case 'presenter':
      return V[params.data || 'presenter'] || {};
    default:
      const keys = { 'flow-path': 'flowPath', 'topology-graph': 'topologyGraph', 'chart-build': 'chartBuild', 'focus-callout': 'focusCallout' };
      return keys[name] ? (V[params.data || keys[name]] || {}) : null;
  }
}
async function mountComposition(host) {
  const src = host.getAttribute('data-composition-src');
  const response = await fetch(src);
  if (!response.ok) throw new Error(`mount failed: ${response.status} ${response.statusText}`);
  const documentNode = new DOMParser().parseFromString(await response.text(), 'text/html');
  const template = documentNode.querySelector('template');
  if (!template) throw new Error('component has no template');
  host.appendChild(template.content.cloneNode(true));
  const name = host.getAttribute('data-composition-id');
  const params = JSON.parse(host.getAttribute('data-variable-values') || '{}');
  // The init entry of the sibling <name>.mjs next to the copied <name>.html.
  const moduleUrl = new URL(src.replace(/\.html$/, '.mjs'), location.href);
  const module = await import(moduleUrl.href);
  const instance = module.init(host.querySelector('#root'), {
    params,
    data: modulePayload(name, params),
    duration: Number(host.getAttribute('data-duration')) || 0,
    gsap,
  });
  window.__instances.push({
    name,
    host,
    start: Number(host.getAttribute('data-start')) || 0,
    instance,
  });
}
window.__mountPromise = (async () => {
  for (const host of document.querySelectorAll('[data-composition-src]')) {
    try {
      await mountComposition(host);
    } catch (error) {
      window.__mountErrors.push(
        `${host.getAttribute('data-composition-id')}: ${error.message}`);
    }
  }
})();
window.seek = async (time) => {
  await window.__mountPromise;
  for (const entry of window.__instances) {
    // Video seconds -> local seconds of this mount, then timeline + self-draw.
    const local = Math.max(0, time - (entry.start || 0));
    if (entry.instance.ready) await entry.instance.ready;
    entry.instance.timeline.pause().seek(local, false);
    if (typeof entry.instance.seek === 'function') await entry.instance.seek(local);
  }
};
"""


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        pass


@contextmanager
def composition_url(tmp_path: Path, video: dict, *components: str):
    """Serve a temporary host; each component is a modules/-relative path."""
    with composition_url_with_mounts(
        tmp_path,
        video,
        [(component, None) for component in components],
    ) as url:
        yield url


@contextmanager
def composition_url_with_mounts(
    tmp_path: Path, video: dict, mounts_spec: list, *, canvas: tuple[int, int] = (1920, 1080),
):
    """Serve a temporary host while loading module sources from this repo.

    mounts_spec entries are (modules-relative path without extension, params
    dict or None) plus an optional third dict of extra host attributes
    (e.g. data-start / data-duration overrides for scene mounts). Params
    become the host's data-variable-values.
    """
    canvas_w, canvas_h = canvas
    composition = tmp_path / 'composition'
    (composition / 'compositions').mkdir(parents=True)
    mounts = []
    seen: dict[str, int] = {}
    for item in mounts_spec:
        component, params, *rest = item
        extra = rest[0] if rest else {}
        base = ROOT / 'modules' / component
        directory_module = base.parent / base.name / f'{base.name}.html'
        source = directory_module if directory_module.is_file() else base
        shutil.copyfile(source.with_suffix('.html'), composition / 'compositions' / f'{source.stem}.html')
        if source.with_suffix('.mjs').is_file():
            shutil.copyfile(source.with_suffix('.mjs'), composition / 'compositions' / f'{source.stem}.mjs')
        name = source.stem
        seen[name] = seen.get(name, 0) + 1
        host_id = name if seen[name] == 1 else f'{name}-{seen[name]}'
        variables = f" data-variable-values='{json.dumps(params, ensure_ascii=False)}'" if params else ''
        start = extra.get('data-start', '0')
        duration = extra.get('data-duration', '6')
        other = ''.join(
            f' {key}="{value}"' for key, value in extra.items()
            if key not in ('data-start', 'data-duration'))
        mounts.append(
            f'<div id="{host_id}" data-composition-id="{name}" '
            f'data-composition-src="compositions/{name}.html" data-start="{start}" '
            f'data-duration="{duration}" data-width="{canvas_w}" data-height="{canvas_h}"{variables}{other} '
            f'style="position:absolute;inset:0"></div>'
        )
    if any(str(item[0]).startswith('motions/') for item in mounts_spec):
        shutil.copyfile(
            ROOT / 'modules/motions/motion-utils.mjs',
            composition / 'compositions/motion-utils.mjs',
        )
    if any(str(item[0]).startswith('components/presenter') for item in mounts_spec):
        images = composition / 'assets/presenter'
        images.mkdir(parents=True)
        for name in ('presenter-base.png', 'presenter-wave.png'):
            shutil.copyfile(ROOT / 'modules/components/presenter/images' / name, images / name)

    html = """<!doctype html><html><head><meta charset="utf-8">
      <link rel="icon" href="data:,">
      <style>
        * { box-sizing: border-box; }
        html, body { margin: 0; width: __CANVAS_W__px; height: __CANVAS_H__px; }
        :root { --font-sans: Arial, sans-serif; --font-mono: monospace;
          --c-chrome: #222; --c-chrome-ink: #fff; --c-chrome-muted: #999;
          --c-chrome-active: #f66; --c-ink: #222; --c-ink2: #666; --c-card: #fff;
          --c-border: #888; --c-focus: #06f; --c-highlight: #fc0; --c-muted: #aaa;
          --c-surface: #eee; --c-focus-tint: #def; --c-positive: #2a4;
          --c-positive-tint: #dfd; --c-positive-solid: #2a4; --c-positive-text: #142;
          --c-done: #4c4583; --c-info: #3e6994; --c-warning: #94661b; --c-danger: #a4434a;
          --c-tile0: #e4e8ec; --c-tile1: #c3dfca; --c-tile2: #92c4a0;
          --c-tile3: #5f9f75; --c-tile4: #33744c;
        }
      </style>
      <script>window.VIDEO = __VIDEO__;</script>
      <script>__TIMELINE_SEEKER__</script>
      </head><body><main data-composition-id="main">__MOUNTS__</main>
      <script>__MOUNTER__</script></body></html>"""
    html = (html.replace('__CANVAS_W__', str(canvas_w))
            .replace('__CANVAS_H__', str(canvas_h))
            .replace('__VIDEO__', json.dumps(video, ensure_ascii=False))
            .replace('__TIMELINE_SEEKER__', TIMELINE_SEEKER)
            .replace('__MOUNTS__', ''.join(mounts))
            .replace('__MOUNTER__', MOUNTER))
    (composition / 'index.html').write_text(html, encoding='utf-8')

    handler = partial(QuietHandler, directory=str(composition))
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}/index.html'
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def open_component_page(browser, url: str, *, viewport: tuple[int, int] = (1920, 1080)):
    page = browser.new_page(viewport={'width': viewport[0], 'height': viewport[1]})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(url, wait_until='networkidle', timeout=30000)
    page.evaluate('window.__mountPromise')
    assert errors == []
    return page, errors


def collect_snapshots(page, checks: list[dict]) -> list[dict]:
    """Run the production QA collector, including its own seek and DOM paths."""
    # HyperFrames normally supplies this integration. The fixture routes it to
    # the same mounted timelines and hf-seek event used by the direct checks.
    page.evaluate('window.__layoutQA = { seek: window.seek }')
    return page.evaluate(SNAPSHOT_JS, {'checks': checks})


def caption_state(page, time: float) -> dict:
    return page.evaluate("""async (time) => {
      await window.seek(time);
      const line = document.querySelector('#cb-1');
      const span = line.querySelector('span');
      const lineStyle = getComputedStyle(line);
      const style = getComputedStyle(span);
      const range = document.createRange();
      range.selectNodeContents(span);
      const lineTops = new Set(Array.from(range.getClientRects())
        .filter((rect) => rect.width > 0 && rect.height > 0)
        .map((rect) => Math.round(rect.top)));
      const rect = line.getBoundingClientRect();
      return {
        rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
        lineOpacity: Number(lineStyle.opacity), fontSize: parseFloat(style.fontSize),
        whiteSpace: style.whiteSpace, maxHeight: parseFloat(style.maxHeight),
        lineHeight: parseFloat(style.lineHeight), lineCount: lineTops.size,
      };
    }""", time)


def test_caption_bar_uses_scene_contract_at_exact_times_and_reverse_seeks(tmp_path: Path):
    # One cue crosses all three visual scenes. Its 36 CJK characters wrap to two
    # lines in the first region and exceed the last region when kept on one line.
    text = '场景字幕必须严格采用当前布局规定的字号宽度与最大行数而不是临时缩小'
    video = {
        'captions': [{'start': 0, 'end': 5.5, 'text': text}],
        'captionSegments': [
            {'scene_id': 'portrait', 'begin_s': 0, 'end_s': 2,
             'caption_rect': {'x': 70, 'y': 1620, 'width': 940, 'height': 200},
             'caption': {'width_px': 940, 'font_size_px': 42, 'max_lines': 2}},
            {'scene_id': 'landscape', 'begin_s': 2, 'end_s': 4,
             'caption_rect': {'x': 96, 'y': 1008, 'width': 1728, 'height': 72},
             'caption': {'width_px': 1728, 'font_size_px': 36, 'max_lines': 1}},
            {'scene_id': 'landscape-presenter', 'begin_s': 4, 'end_s': 6,
             'caption_rect': {'x': 96, 'y': 1008, 'width': 1166, 'height': 72},
             'caption': {'width_px': 1166, 'font_size_px': 36, 'max_lines': 1}},
        ],
    }
    with composition_url(tmp_path, video, 'components/caption-bar') as url:
        with chrome_cdp.launch_isolated() as session:
            page, errors = open_component_page(session.browser, url)

            initial = caption_state(page, 0.05)
            # Dynamic data starts at cue.start=0, without the legacy 0.15s delay.
            assert initial['lineOpacity'] == pytest.approx(1)
            assert initial['rect'] == {'x': 70, 'y': 1620, 'width': 940, 'height': 200}
            assert initial['fontSize'] == 42
            assert initial['whiteSpace'] == 'normal'
            assert initial['lineHeight'] == pytest.approx(42 * 1.15)
            assert initial['maxHeight'] == pytest.approx(2 * 42 * 1.15)
            assert initial['lineCount'] == 2

            stage = caption_state(page, 2.5)
            assert stage['rect'] == {'x': 96, 'y': 1008, 'width': 1728, 'height': 72}
            assert stage['fontSize'] == 36
            assert stage['whiteSpace'] == 'nowrap'
            assert stage['maxHeight'] == pytest.approx(36 * 1.15)
            assert stage['lineCount'] == 1

            presenter = caption_state(page, 4.5)
            assert presenter['rect']['width'] == 1166
            # The text is wider than this region: scene mode must not shrink it.
            assert presenter['fontSize'] == 36
            assert presenter['whiteSpace'] == 'nowrap'

            # Backward seeks must restore every per-segment property, not just
            # whichever values happened to be applied by the most recent scene.
            assert caption_state(page, 2.5) == stage
            restored = caption_state(page, 0.5)
            assert restored == initial
            # Dynamic data also ends at cue.end, with no legacy +0.1s extension.
            assert caption_state(page, 5.55)['lineOpacity'] == pytest.approx(0)

            # Exercise the production QA collector against the mounted
            # subcomposition, not a fixture-specific DOM projection.
            snapshots = collect_snapshots(page, [
                {'scene_id': 'portrait', 'time': 0.5},
                {'scene_id': 'stage', 'time': 2.5},
                {'scene_id': 'portrait-backward', 'time': 0.5},
                {'scene_id': 'ended', 'time': 5.55},
            ])
            assert [snapshot['captionTexts'] for snapshot in snapshots] == [
                [text], [text], [text], [],
            ]
            details = [snapshot['captionDetails'] for snapshot in snapshots]
            assert len(details[0]) == len(details[1]) == len(details[2]) == 1
            assert details[0][0]['text'] == details[1][0]['text'] == text
            assert (details[0][0]['fontSize'], details[0][0]['lineCount']) == (42, 2)
            assert (details[1][0]['fontSize'], details[1][0]['lineCount']) == (36, 1)
            assert details[2] == details[0]
            assert details[0][0]['rect']['x'] == 70
            assert details[0][0]['rect']['width'] == 940
            assert details[1][0]['rect']['width'] == 1728
            assert details[3] == []
            assert page.evaluate('window.__mountErrors') == []
            assert errors == []
            page.close()


def test_migrated_modules_init_and_seek_without_vendor_globals(tmp_path: Path):
    video = {
        'tabs': [{'label': '概览', 'at': 0}, {'label': '#1', 'at': 2.0}],
        'captions': [{'start': 0.2, 'end': 4.0, 'text': '本周热榜开场'}],
        'cuts': [{'at': 2.0, 'label': '#1', 'title': 'demo / ', 'emphasis': 'tool',
                  'meta': [{'dot': '#dea584', 'text': 'Rust'}]}],
        'trending': {'repos': [
            {'rank': 1, 'owner': 'demo', 'repo': 'tool', 'desc': '一句话描述',
             'stars': '1,234', 'readme': 'x.png', 'cue': 1.0},
        ]},
    }
    mounts = [
        ('components/caption-bar', None),
        ('components/nav-bar', {'logo': '', 'path': 'github / trending'}),
        ('transitions/tile-wipe', None),
        ('templates/github-trending/trending-overview', None),
        ('templates/github-trending/project-cover',
         {'owner': 'demo', 'repo': 'tool', 'logo': 'assets/brand/github-mark-white.svg',
          'nameAt': 0.5, 'taglineAt': 1.0,
          'tagline': '一句话介绍', 'stars': 2000, 'starsAt': 2.0}),
    ]
    with composition_url_with_mounts(tmp_path, video, mounts) as url:
        with chrome_cdp.launch_isolated() as session:
            page, errors = open_component_page(session.browser, url)
            state = page.evaluate("""async () => {
              await window.seek(4.2);
              const nav = document.querySelector('#nav-bar');
              const tiles = document.querySelector('#tile-wipe');
              const trending = document.querySelector('#trending-overview');
              const cover = document.querySelector('#project-cover');
              const caption = document.querySelector('#caption-bar');
              return {
                mountErrors: window.__mountErrors,
                // Migrated modules must not touch the vendor registries.
                legacyTimelines: typeof window.__timelines,
                legacyHf: typeof window.__hf,
                instanceNames: window.__instances.map((entry) => entry.name),
                paused: window.__instances.every((entry) => entry.instance.timeline.paused !== false),
                tabs: nav.querySelectorAll('.tab').length,
                lineWidth: nav.querySelector('#nb-line').style.width,
                tileCount: tiles.querySelectorAll('#tw-tiles i').length,
                plateClip: tiles.querySelector('#tw-plate').style.clipPath,
                cardLabel: (tiles.querySelector('.tw-card .lb') || {}).textContent || null,
                rows: trending.querySelectorAll('#to-list .row').length,
                rank: (trending.querySelector('#to-list .rk') || {}).textContent,
                count: cover.querySelector('#pc-count').textContent,
                logoRole: cover.querySelector('#pc-side img')?.getAttribute('data-media-role'),
                starState: cover.querySelector('#pc-meta .s1').style.opacity,
                captionText: (caption.querySelector('#cb-1 span') || {}).textContent || null,
              };
            }""")
            assert state['mountErrors'] == []
            # Migrated modules must not register into the vendor registries.
            assert state['legacyTimelines'] == 'undefined'
            assert state['legacyHf'] == 'undefined'
            assert sorted(state['instanceNames']) == [
                'caption-bar', 'nav-bar', 'project-cover', 'tile-wipe',
                'trending-overview',
            ]
            assert state['paused'] is True
            assert state['tabs'] == 2
            assert state['lineWidth'] != ''
            assert state['tileCount'] > 0
            assert state['plateClip'] != ''
            assert state['cardLabel'] == '#1'
            assert state['rows'] == 1
            assert state['rank'] == '1'
            # past starsAt + 1.4s count-up: the number reached its target
            assert state['count'] == '+2,000'
            assert state['logoRole'] == 'logo'
            assert float(state['starState']) == 1
            assert state['captionText'] == '本周热榜开场'
            assert errors == []
            page.close()


def test_two_instances_with_different_params_and_data_do_not_interfere(tmp_path: Path):
    video = {
        'capsA': [{'start': 0, 'end': 3, 'text': '第一句字幕内容'}],
        'segsA': [
            {'scene_id': 'wide', 'begin_s': 0, 'end_s': 3,
             'caption_rect': {'x': 70, 'y': 1000, 'width': 940, 'height': 200},
             'caption': {'width_px': 940, 'font_size_px': 42, 'max_lines': 2}},
        ],
        'capsB': [{'start': 0, 'end': 3, 'text': 'second line'}],
    }
    mounts = [
        ('components/caption-bar', {'data': 'capsA', 'layoutData': 'segsA'}),
        ('components/caption-bar', {'data': 'capsB', 'fontSize': 28}),
    ]
    with composition_url_with_mounts(tmp_path, video, mounts) as url:
        with chrome_cdp.launch_isolated() as session:
            page, errors = open_component_page(session.browser, url)

            first = page.evaluate("""async (time) => {
              await window.seek(time);
              return Array.from(document.querySelectorAll('[data-composition-src]')).map((host) => {
                const line = host.querySelector('.cb-line');
                const span = line.querySelector('span');
                const rect = line.getBoundingClientRect();
                return { text: span.textContent,
                  rect: { x: rect.x, y: rect.y, width: rect.width },
                  opacity: Number(getComputedStyle(line).opacity),
                  fontSize: parseFloat(getComputedStyle(span).fontSize) };
              });
            }""", 0.5)
            assert first[0] == {
                'text': '第一句字幕内容', 'rect': {'x': 70, 'y': 1000, 'width': 940},
                'opacity': pytest.approx(1), 'fontSize': 42,
            }
            assert first[1] == {
                'text': 'second line', 'rect': {'x': 96, 'y': 1008, 'width': 1166},
                'opacity': pytest.approx(1), 'fontSize': 28,
            }
            distinct = page.evaluate("""() => {
              const timelines = window.__instances.map((entry) => entry.instance.timeline);
              return new Set(timelines).size === timelines.length;
            }""")
            assert distinct is True

            # Tear the first instance down the way an adapter would: destroy the
            # module, drop the host, and stop driving it.
            page.evaluate("""() => {
              const [entry] = window.__instances.splice(0, 1);
              entry.instance.destroy();
              entry.host.remove();
            }""")
            remaining = page.evaluate("""async (time) => {
              await window.seek(time);
              const host = document.querySelector('[data-composition-src="compositions/caption-bar.html"]');
              const line = host.querySelector('.cb-line');
              const span = line.querySelector('span');
              const rect = line.getBoundingClientRect();
              return { hosts: document.querySelectorAll('[data-composition-src]').length,
                text: span.textContent, rect: { x: rect.x, y: rect.y },
                opacity: Number(getComputedStyle(line).opacity),
                fontSize: parseFloat(getComputedStyle(span).fontSize),
                instances: window.__instances.length };
            }""", 2.5)
            assert remaining['hosts'] == 1
            assert remaining['instances'] == 1
            assert remaining['text'] == 'second line'
            assert remaining['rect'] == {'x': 96, 'y': 1008}
            assert remaining['opacity'] == pytest.approx(1)
            assert remaining['fontSize'] == 28

            # Remounting a fresh instance must not resurrect the old driver.
            page.evaluate("""async () => {
              const main = document.querySelector('main');
              const host = document.createElement('div');
              host.id = 'host-caption-bar-again';
              host.setAttribute('data-composition-id', 'caption-bar');
              host.setAttribute('data-composition-src', 'compositions/caption-bar.html');
              host.setAttribute('data-start', '0');
              host.setAttribute('data-duration', '6');
              host.setAttribute('data-width', '1920');
              host.setAttribute('data-height', '1080');
              host.setAttribute('data-variable-values', '{"data":"capsA","layoutData":"segsA"}');
              host.style.position = 'absolute';
              host.style.inset = '0';
              main.appendChild(host);
              await mountComposition(host);
            }""")
            remounted = page.evaluate("""async (time) => {
              await window.seek(time);
              const host = document.querySelector('#host-caption-bar-again');
              const line = host.querySelector('.cb-line');
              const span = line.querySelector('span');
              const rect = line.getBoundingClientRect();
              return { text: span.textContent, rect: { x: rect.x, y: rect.y },
                fontSize: parseFloat(getComputedStyle(span).fontSize),
                instances: window.__instances.length,
                mountErrors: window.__mountErrors };
            }""", 0.5)
            assert remounted == {
                'text': '第一句字幕内容', 'rect': {'x': 70, 'y': 1000}, 'fontSize': 42,
                'instances': 2, 'mountErrors': [],
            }
            assert errors == []
            page.close()


def presenter_state(page, time: float) -> dict:
    """Seek (video seconds) and sample the stage geometry plus a canvas
    fingerprint, proving the WebGL character itself is re-drawn per seek."""
    return page.evaluate("""async (time) => {
      await window.seek(time);
      const stage = document.querySelector('#presenter-stage');
      const canvas = document.querySelector('#presenter-gl');
      return { display: getComputedStyle(stage).display,
        left: stage.style.left, top: stage.style.top, size: stage.style.width,
        canvas: canvas.toDataURL('image/png') };
    }""", time)


def presenter_mouth_dark(page, host_id: str, time: float) -> int:
    """Dark-pixel count in a window around the mouth: envelope-driven mouth
    opening shows a region of dark mouth interior there, not just ink lines."""
    return page.evaluate("""async ({ hostId, time }) => {
      await window.seek(time);
      const host = document.getElementById(hostId);
      const gl = host.querySelector('#presenter-gl');
      const c = document.createElement('canvas');
      c.width = gl.width; c.height = gl.height;
      const x = c.getContext('2d');
      x.drawImage(gl, 0, 0);
      // mouth region in 2048 space is ~(958..1142, 800..900); canvas is 1200px
      const data = x.getImageData(545, 455, 130, 85).data;
      let dark = 0;
      for (let i = 0; i < data.length; i += 4) {
        if (data[i + 3] < 200) continue;
        const lum = 0.3 * data[i] + 0.59 * data[i + 1] + 0.11 * data[i + 2];
        if (lum < 60) dark += 1;
      }
      return dark;
    }""", {'hostId': host_id, 'time': time})


def test_presenter_single_full_video_mount_follows_presenter_scene_visibility(tmp_path: Path):
    video = {'presenter': {'duration': 6, 'placements': [
        {'begin_s': 0, 'end_s': 2, 'visible': True, 'x': 1294, 'y': 642, 'size': 420},
        {'begin_s': 2, 'end_s': 4, 'visible': False},
        {'begin_s': 4, 'end_s': 6, 'visible': True, 'x': 1294, 'y': 642, 'size': 420},
    ]}}
    with composition_url(tmp_path, video, 'components/presenter') as url:
        with chrome_cdp.launch_isolated() as session:
            page, errors = open_component_page(session.browser, url)
            init = page.evaluate("""async () => {
              await window.__mountPromise;
              const entry = window.__instances.find((item) => item.name === 'presenter');
              // The component's real asynchronous image/WebGL build.
              await entry.instance.ready;
              return { mountErrors: window.__mountErrors,
                legacyTimelines: typeof window.__timelines,
                legacyHf: typeof window.__hf };
            }""")
            assert init == {'mountErrors': [], 'legacyTimelines': 'undefined',
                            'legacyHf': 'undefined'}
            assert page.locator('[data-composition-src="compositions/presenter.html"]').count() == 1
            host = page.locator('#presenter')
            assert host.get_attribute('data-start') == '0'
            assert host.get_attribute('data-duration') == '6'
            assert page.locator('#presenter-stage').count() == 1

            visible = presenter_state(page, 1)
            assert visible['display'] != 'none'
            hidden = presenter_state(page, 3)
            assert hidden['display'] == 'none'
            frame5 = presenter_state(page, 5)
            assert {key: frame5[key] for key in ('display', 'left', 'top', 'size')} == {
                'display': 'block', 'left': '1294px', 'top': '642px', 'size': '420px',
            }
            assert presenter_state(page, 3)['display'] == 'none'
            again = presenter_state(page, 1)
            assert again['display'] != 'none'
            # A nonempty placement contract is closed at the final end_s too.
            ended = presenter_state(page, 6)
            assert ended['display'] == 'none'
            # The character is really drawn: the canvas holds pixels and every
            # seek re-renders it (same time -> identical frame, different
            # time -> different frame), not just an empty timeline.
            assert len(visible['canvas']) > 20000
            assert again['canvas'] == visible['canvas']
            assert ended['canvas'] != visible['canvas']

            # The production collector must inspect #presenter-stage. The host stays
            # visible and has a full-canvas box, so it cannot make a hidden presenter
            # count as visible by itself.
            host_state = host.evaluate("""(element) => ({
              display: getComputedStyle(element).display,
              width: element.getBoundingClientRect().width,
              height: element.getBoundingClientRect().height,
            })""")
            assert host_state['display'] != 'none'
            assert host_state['width'] == 1920 and host_state['height'] == 1080
            snapshots = collect_snapshots(page, [
                {'scene_id': 'presenter', 'time': 1},
                {'scene_id': 'stage', 'time': 3},
                {'scene_id': 'presenter-again', 'time': 5},
                {'scene_id': 'stage-backward', 'time': 3},
                {'scene_id': 'ended', 'time': 6},
            ])
            assert [snapshot['presenterVisible'] for snapshot in snapshots] == [
                True, False, True, False, False,
            ]
            assert errors == []
            page.close()


def test_presenter_scene_mount_keeps_local_seconds_for_acts_and_envelope(tmp_path: Path):
    # Scene clipped from a longer video: the host starts at video 2.5s and the
    # adapter converts video seconds to local seconds. Acting-script times
    # (placements, acts, envelope) stay local: nothing may shift by the
    # mount offset, and a scene covering only part of the narration must not
    # replay or anticipate lip sync. The envelope is loud everywhere except a
    # quiet window at local 2.0-3.0s.
    envelope = [100] * (30 * 8)
    for i in range(30 * 2, 30 * 3):
        envelope[i] = 0
    video = {'presenter': {
        'duration': 6,
        'seed': 7,
        'envelopeFps': 30,
        'envelope': envelope,
        'acts': [[0.5, 'think', 2000]],
        'thoughts': [[0.5, '想法']],
        'placements': [
            {'begin_s': 0, 'end_s': 2, 'visible': True, 'x': 100, 'y': 200, 'size': 300},
            {'begin_s': 2, 'end_s': 6, 'visible': False},
        ],
    }}
    mounts = [('components/presenter', None, {'data-start': '2.5', 'data-duration': '6'})]
    with composition_url_with_mounts(tmp_path, video, mounts) as url:
        with chrome_cdp.launch_isolated() as session:
            page, errors = open_component_page(session.browser, url)
            page.evaluate("window.__mountPromise.then(() => window.__instances[0].instance.ready)")

            def bubble(time):
                return page.evaluate("""async (time) => {
                  await window.seek(time);
                  const stage = document.querySelector('#presenter-stage');
                  const thought = document.querySelector('#presenter-thought');
                  return { display: getComputedStyle(stage).display,
                    left: stage.style.left, top: stage.style.top, size: stage.style.width,
                    thoughtOpacity: Number(thought.getAttribute('opacity')),
                    thoughtText: document.querySelector('#presenter-thought-text').textContent };
                }""", time)

            # Local 1.5s = video 4.0s: visible placement, think act in full swing.
            mid = bubble(4.0)
            assert mid == {'display': 'block', 'left': '100px', 'top': '200px',
                           'size': '300px', 'thoughtOpacity': pytest.approx(1),
                           'thoughtText': '想法'}
            # Local 0.25s = video 2.75s: placement visible, act not started yet.
            early = bubble(2.75)
            assert early['display'] == 'block'
            assert early['thoughtOpacity'] == pytest.approx(0)
            # Local 3.5s = video 6.0s: second placement hides the stage, the
            # act has fully decayed; nothing lingers from the first fragment.
            late = bubble(6.0)
            assert late['display'] == 'none'
            # The pose chase has decayed to effectively nothing.
            assert late['thoughtOpacity'] < 0.01
            # Past the slot: the final end_s closes the contract as before.
            assert bubble(8.5)['display'] == 'none'

            # Envelope sampling follows local seconds: the mouth is open at
            # local 1.0 (video 3.5) and closed inside the quiet window at
            # local 2.5 (video 5.0). A shift by the 2.5s mount offset would
            # sample a loud frame inside the quiet window and fail here.
            loud = presenter_mouth_dark(page, 'presenter', 3.5)
            quiet = presenter_mouth_dark(page, 'presenter', 5.0)
            assert loud > 30
            assert loud > quiet + 20
            assert errors == []
            page.close()


def test_two_presenter_instances_with_different_roots_positions_and_data_do_not_interfere(tmp_path: Path):
    video = {
        'presenterA': {'duration': 6, 'seed': 1, 'envelopeFps': 30, 'envelope': [80] * 180},
        'presenterB': {'duration': 6, 'seed': 999, 'envelopeFps': 30, 'envelope': [0] * 180,
                       'placements': [
                           {'begin_s': 0, 'end_s': 3, 'visible': True, 'x': 900, 'y': 500, 'size': 500},
                           {'begin_s': 3, 'end_s': 6, 'visible': False},
                       ]},
    }
    mounts = [
        ('components/presenter', {'data': 'presenterA', 'x': 100, 'y': 100, 'size': 300}),
        ('components/presenter', {'data': 'presenterB', 'x': 900, 'y': 500, 'size': 500, 'fxScale': 1.3}),
    ]
    with composition_url_with_mounts(tmp_path, video, mounts) as url:
        with chrome_cdp.launch_isolated() as session:
            page, errors = open_component_page(session.browser, url)
            page.evaluate("""async () => {
              await window.__mountPromise;
              await Promise.all(window.__instances.map((entry) => entry.instance.ready));
            }""")
            state = page.evaluate("""async (time) => {
              await window.seek(time);
              const stageOf = (hostId) => {
                const stage = document.getElementById(hostId).querySelector('#presenter-stage');
                return { display: getComputedStyle(stage).display,
                  left: stage.style.left, top: stage.style.top, size: stage.style.width,
                  canvas: stage.parentElement.querySelector('#presenter-gl').toDataURL('image/png') };
              };
              return { a: stageOf('presenter'), b: stageOf('presenter-2'),
                timelinesDistinct: new Set(window.__instances.map(
                  (entry) => entry.instance.timeline)).size === 2 };
            }""", 1.0)
            # Different roots, positions and acting data stay separate.
            assert state['a']['display'] == 'block'
            assert (state['a']['left'], state['a']['top'], state['a']['size']) == ('100px', '100px', '300px')
            assert (state['b']['left'], state['b']['top'], state['b']['size']) == ('900px', '500px', '500px')
            assert state['a']['canvas'] != state['b']['canvas']
            assert state['timelinesDistinct'] is True

            # B's own placements hide it after local 3s; A (no placements,
            # param geometry) stays visible the whole slot.
            later = page.evaluate("""async (time) => {
              await window.seek(time);
              const display = (hostId) => getComputedStyle(
                document.getElementById(hostId).querySelector('#presenter-stage')).display;
              return { a: display('presenter'), b: display('presenter-2') };
            }""", 4.0)
            assert later == {'a': 'block', 'b': 'none'}

            # Tear A down the way an adapter would: no driver may survive,
            # and B must keep rendering without interference.
            page.evaluate("""async () => {
              const index = window.__instances.findIndex((entry) => entry.host.id === 'presenter');
              const [entry] = window.__instances.splice(index, 1);
              entry.instance.destroy();
              entry.host.remove();
            }""")
            surviving = page.evaluate("""async (time) => {
              await window.seek(time);
              const stage = document.getElementById('presenter-2').querySelector('#presenter-stage');
              const canvas = stage.parentElement.querySelector('#presenter-gl');
              const frame = canvas.toDataURL('image/png');
              await window.seek(time);
              const again = canvas.toDataURL('image/png');
              return { names: window.__instances.map((entry) => entry.name),
                hosts: document.querySelectorAll('[data-composition-src]').length,
                bDisplay: getComputedStyle(stage).display,
                bFrame: frame, bFrameAgain: again };
            }""", 2.0)
            assert surviving['names'] == ['presenter']
            assert surviving['hosts'] == 1
            assert surviving['bDisplay'] == 'block'
            assert surviving['bFrame'] == surviving['bFrameAgain']
            assert errors == []
            page.close()


def test_presenter_ready_rejects_when_build_assets_are_missing(tmp_path: Path):
    video = {'presenter': {'duration': 6}}
    with composition_url(tmp_path, video, 'components/presenter') as url:
        # Break the layer source before the page loads: the asynchronous
        # build must surface the failure through the returned `ready` promise
        # instead of leaving a silently empty character.
        (tmp_path / 'composition/assets/presenter/presenter-base.png').unlink()
        with chrome_cdp.launch_isolated() as session:
            browser = session.browser
            page = browser.new_page(viewport={'width': 1920, 'height': 1080})
            page.goto(url, wait_until='networkidle', timeout=30000)
            page.evaluate('window.__mountPromise')
            outcome = page.evaluate("""async () => {
              const entry = window.__instances.find((item) => item.name === 'presenter');
              let message = null;
              try {
                await entry.instance.ready;
              } catch (error) {
                message = String((error && error.message) || error);
              }
              return { message, mountErrors: window.__mountErrors };
            }""")
            assert outcome['mountErrors'] == []
            assert outcome['message']
            page.close()


def test_portrait_presenter_switches_bar_character_and_tile_wipe_within_portrait_canvas(tmp_path: Path):
    portrait_presenter = json.loads((ROOT / 'modules/layouts/portrait-presenter.json').read_text(encoding='utf-8'))
    portrait = json.loads((ROOT / 'modules/layouts/portrait.json').read_text(encoding='utf-8'))
    pp_regions = {r['id']: r['rect'] for r in portrait_presenter['regions']}
    p_regions = {r['id']: r['rect'] for r in portrait['regions']}

    video = {
        'captions': [
            {'start': 0.2, 'end': 2.8, 'text': '竖屏讲解场景底部有双行字幕条且右侧有主持人'},
            {'start': 3.2, 'end': 5.8, 'text': '切到无主持人竖屏舞台后底条自动收起并切换居中深色字'},
        ],
        'captionSegments': [
            {
                'scene_id': 'host_scene', 'begin_s': 0, 'end_s': 3,
                'caption_rect': pp_regions['caption-text'],
                'caption_bar_rect': pp_regions['caption-bar'],
                'caption': portrait_presenter['caption'],
            },
            {
                'scene_id': 'stage_scene', 'begin_s': 3, 'end_s': 6,
                'caption_rect': p_regions['caption-text'],
                'caption_bar_rect': None,
                'caption': portrait['caption'],
            },
        ],
        'presenter': {
            'duration': 6,
            'glances': [[0.5, 1.0, 'U']],
            'placements': [
                {'begin_s': 0, 'end_s': 3, 'visible': True,
                 'x': pp_regions['person']['x'], 'y': pp_regions['person']['y'],
                 'size': pp_regions['person']['width']},
                {'begin_s': 3, 'end_s': 6, 'visible': False},
            ],
        },
        'cuts': [{'at': 3.0}],
    }
    mounts = [
        ('components/caption-bar', None, {'data-track-kind': 'captions'}),
        ('components/presenter', {'x': 720, 'y': 1476, 'size': 300, 'fxScale': 1.4}),
        ('transitions/tile-wipe', {'originX': 870, 'originY': 1709, 'top': 88, 'bottom': 1776}),
    ]
    with composition_url_with_mounts(tmp_path, video, mounts, canvas=(1080, 1920)) as url:
        with chrome_cdp.launch_isolated() as session:
            page, errors = open_component_page(session.browser, url, viewport=(1080, 1920))

            state_at = """async (time) => {
              await window.seek(time);
              const bar = document.querySelector('#cb-bar');
              const barStyle = getComputedStyle(bar);
              const barRect = bar.getBoundingClientRect();
              const stage = document.querySelector('#presenter-stage');
              const stageStyle = getComputedStyle(stage);
              const stageRect = stage.getBoundingClientRect();
              const plateRect = document.querySelector('#tw-plate').getBoundingClientRect();
              const activeLine = Array.from(document.querySelectorAll('.cb-line'))
                .find((el) => Number(getComputedStyle(el).opacity) > 0.5);
              const spanStyle = activeLine ? getComputedStyle(activeLine.querySelector('span')) : null;
              return {
                barDisplay: barStyle.display,
                barRect: { x: barRect.x, y: barRect.y, width: barRect.width, height: barRect.height },
                presenterDisplay: stageStyle.display,
                presenterRect: { x: stageRect.x, y: stageRect.y, width: stageRect.width, height: stageRect.height },
                plateWidth: plateRect.width,
                plateHeight: plateRect.height,
                textAlign: spanStyle ? spanStyle.textAlign : null,
                textColor: spanStyle ? spanStyle.color : null,
              };
            }"""

            host_state = page.evaluate(state_at, 1.0)
            assert host_state['barDisplay'] == 'block'
            assert host_state['barRect'] == {'x': 0, 'y': 1776, 'width': 1080, 'height': 144}
            assert host_state['presenterDisplay'] == 'block'
            assert host_state['presenterRect'] == {'x': 720, 'y': 1476, 'width': 300, 'height': 300}
            assert host_state['plateWidth'] == 1080
            assert host_state['plateHeight'] == 1688  # 88 (nav bar) .. 1776 (caption bar)
            assert host_state['textAlign'] == 'center'
            assert host_state['textColor'] == 'rgb(255, 255, 255)'

            stage_state = page.evaluate(state_at, 4.5)
            assert stage_state['barDisplay'] == 'none'
            assert stage_state['presenterDisplay'] == 'none'
            assert stage_state['textAlign'] == 'center'
            assert stage_state['textColor'] == 'rgb(34, 34, 34)'

            # Reverse seek back to portrait-presenter restores bottom bar, character, and chrome-ink text.
            assert page.evaluate(state_at, 1.0) == host_state

            # Add visible visual-scene mounts inside each scene's `main` region so
            # check-composition validates the full portrait-presenter -> portrait composition.
            page.evaluate("""() => {
              const main = document.querySelector('main');
              for (const [id, start, end, height] of [
                ['host_scene', 0, 3, 900],
                ['stage_scene', 3, 6, 1240],
              ]) {
                const sceneEl = document.createElement('div');
                sceneEl.setAttribute('data-scene-id', id);
                sceneEl.setAttribute('data-scene-start', String(start));
                sceneEl.setAttribute('data-scene-end', String(end));
                sceneEl.style.cssText = 'position:absolute;inset:0;display:none';
                const card = document.createElement('div');
                card.id = `card-${id}`;
                card.style.cssText = `position:absolute;left:70px;top:300px;width:940px;height:${height}px;font-size:32px;background:var(--c-card)`;
                card.textContent = `竖屏内容区 ${id}`;
                sceneEl.appendChild(card);
                main.appendChild(sceneEl);
              }
              const origSeek = window.seek;
              window.seek = async (time) => {
                for (const el of document.querySelectorAll('[data-scene-id]')) {
                  const s = Number(el.getAttribute('data-scene-start'));
                  const e = Number(el.getAttribute('data-scene-end'));
                  el.style.display = time >= s && time < e ? 'block' : 'none';
                }
                return origSeek(time);
              };
            }""")

            snapshots = collect_snapshots(page, [
                {'scene_id': 'host_scene', 'time': 1.0},
                {'scene_id': 'stage_scene', 'time': 4.5},
            ])
            assert [s['presenterVisible'] for s in snapshots] == [True, False]
            assert snapshots[0]['captionDetails'][0]['fontSize'] == 38
            assert snapshots[0]['captionDetails'][0]['lineCount'] <= 2
            assert snapshots[1]['captionDetails'][0]['fontSize'] == 42
            assert snapshots[1]['captionDetails'][0]['lineCount'] <= 2

            # Verify stylesheet CSS on .cb-line span can still override barless --cb-ink
            # (e.g. light text over dark footage in a custom/freeform scene).
            overridden_color = page.evaluate("""async () => {
              const style = document.createElement('style');
              style.textContent = '#caption-bar .cb-line span { color: rgb(240, 248, 255); }';
              document.head.appendChild(style);
              await window.seek(4.5);
              const active = Array.from(document.querySelectorAll('.cb-line'))
                .find((el) => Number(getComputedStyle(el).opacity) > 0.5);
              return getComputedStyle(active.querySelector('span')).color;
            }""")
            assert overridden_color == 'rgb(240, 248, 255)'
            assert errors == []
            page.close()

    # Run real check-composition.py against the collected portrait-presenter +
    # portrait + tile-wipe snapshots: #tw-plate must not trigger outside_content_regions
    # or reserved_region_intrusion into person, and both scenes must pass QA!
    import subprocess
    import sys
    ws = tmp_path / 'qa_ws'
    (ws / 'composition').mkdir(parents=True)
    (ws / 'composition/index.html').write_text('<html></html>', encoding='utf-8')
    (ws / 'inputs.json').write_text(json.dumps({'orientation': 'portrait'}), encoding='utf-8')
    (ws / 'voice_clone').mkdir(parents=True)
    subprocess.run([
        'ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=mono',
        '-t', '6', '-c:a', 'libmp3lame', str(ws / 'voice_clone/narration.mp3'),
    ], capture_output=True, check=True)
    scene_cfg = ws / 'composition/scene-config.json'
    scene_cfg.write_text(json.dumps({
        'version': 1,
        'canvas': {'width': 1080, 'height': 1920},
        'total_s': 6.0,
        'scenes': [
            {
                'scene_id': 'host_scene', 'source_scene_ids': ['s1'],
                'begin_s': 0.0, 'end_s': 3.0, 'template': None,
                'layout': {
                    'preset': 'portrait-presenter',
                    'regions': portrait_presenter['regions'],
                    'caption': portrait_presenter['caption'],
                },
            },
            {
                'scene_id': 'stage_scene', 'source_scene_ids': ['s2'],
                'begin_s': 3.0, 'end_s': 6.0, 'template': None,
                'layout': {
                    'preset': 'portrait',
                    'regions': portrait['regions'],
                    'caption': portrait['caption'],
                },
            },
        ],
    }, ensure_ascii=False), encoding='utf-8')
    units_path = ws / 'units.json'
    units_path.write_text(json.dumps({
        'units': [
            {'text': video['captions'][0]['text'], 'begin_s': 0.2, 'end_s': 2.8},
            {'text': video['captions'][1]['text'], 'begin_s': 3.2, 'end_s': 5.8},
        ],
    }, ensure_ascii=False), encoding='utf-8')
    snaps_path = ws / 'snapshots.json'
    snaps_path.write_text(json.dumps(snapshots, ensure_ascii=False), encoding='utf-8')
    qa_proc = subprocess.run([
        sys.executable, str(ROOT / 'scripts/check-composition.py'),
        str(ws / 'composition'),
        '--scene-config', str(scene_cfg),
        '--design', str(ROOT / 'modules/designs/default/default.md'),
        '--subtitle-units', str(units_path),
        '--snapshots-from', str(snaps_path),
    ], capture_output=True, text=True)
    assert qa_proc.returncode == 0, qa_proc.stdout + qa_proc.stderr
    qa_report = json.loads(qa_proc.stdout)
    assert qa_report['verdict'] == 'pass', qa_report['findings']


@pytest.mark.parametrize('orientation, canvas, region', [
    ('landscape', (1920, 1080), {'x': 96, 'y': 196, 'width': 1048, 'height': 788}),
    ('portrait', (1080, 1920), {'x': 70, 'y': 300, 'width': 940, 'height': 1170}),
], ids=['landscape', 'portrait'])
def test_motion_modules_wrap_copy_seek_reversibly_and_pass_qa(
    tmp_path: Path, orientation: str, canvas: tuple[int, int], region: dict[str, int], require_ffmpeg,
):
    import subprocess
    import sys

    video = {
        'flowPath': {'nodes': [{'id': 'n1', 'label': '多源异构工程文档解析与语法树抽取 FLOW_TAIL_1', 'detail': '保留长路径 https://github.com/org/repo/flow_token_alpha_ok', 'at': 0.15}, {'id': 'n2', 'label': '确定性多行折行与承载矩形动态适配 FLOW_TAIL_2', 'detail': '最小阅读字号二十六像素与界面二十二像素零截断 FLOW_DET_2', 'at': 0.65}, {'id': 'n3', 'label': '逐帧采样与编码门禁验收 FLOW_TAIL_3', 'detail': 'unbrokenidentifierwithoutdelimiterstailFLOW3 保持间距清晰', 'at': 1.2, 'status': 'positive'}], 'edges': [{'from': 'n1', 'to': 'n2', 'label': 'AST EDGE_1', 'at': 0.45}, {'from': 'n2', 'to': 'n3', 'label': '1:1 EDGE_2', 'at': 1.0}]},
        'topologyGraph': {'layers': [{'id': 'edge', 'label': '接入网关 LAYER_1'}, {'id': 'core', 'label': '编排合成核 LAYER_2'}, {'id': 'store', 'label': '构件存储 LAYER_3'}], 'nodes': [{'id': 'gw', 'label': '多协议鉴权流控路由网关 TOPO_TAIL_1', 'detail': '/api/v2/deterministic_gateway_tail_ok', 'layer': 'edge', 'at': 0.1}, {'id': 'sched', 'label': 'DAG 拓扑任务调度核心 TOPO_TAIL_2', 'detail': '按语音时间戳切换子图焦点', 'layer': 'core', 'at': 0.45, 'emphasis': True}, {'id': 'worker', 'label': '隔离渲染沙箱节点 TOPO_TAIL_3', 'detail': '1:1 像素视口矢量度量', 'layer': 'core', 'at': 0.65}, {'id': 'cas', 'label': '内容寻址构件存储库 TOPO_TAIL_4', 'detail': '哈希去重复用静态纹理', 'layer': 'store', 'at': 1.0}], 'links': [{'from': 'gw', 'to': 'sched', 'label': 'gRPC LINK_1', 'at': 0.35, 'emphasis': True}, {'from': 'sched', 'to': 'worker', 'at': 0.75, 'emphasis': True}, {'from': 'worker', 'to': 'cas', 'at': 1.1}], 'focusSequence': [{'nodeIds': ['gw', 'sched'], 'at': 0.55}, {'nodeIds': ['sched', 'worker', 'cas'], 'at': 1.25}]},
        'chartBar': {'items': [{'label': '串行基线 BAR_TAIL_1', 'value': 38, 'at': 0.15}, {'label': '增量缓存 BAR_TAIL_2', 'value': 84, 'at': 0.6}, {'label': '零拷贝引擎 zero_copy_bar_tail_ok', 'value': 156, 'displayValue': '156 fps', 'at': 1.05, 'emphasis': True}], 'summary': '吞吐提升 4.1 倍 BAR_SUM_OK', 'summaryAt': 1.4},
        'chartLine': {'points': [{'label': 'v1.0_base', 'value': 24, 'at': 0.15}, {'label': 'v1.5_cache', 'value': 76, 'at': 0.65}, {'label': 'v2.0_readout_tail_ok', 'value': 148, 'at': 1.25, 'emphasis': True}], 'summary': '趋势曲线稳定收敛 LINE_SUM_OK', 'summaryAt': 1.5},
        'chartMetric': {'label': '高压缩比细线完整率 METRIC_TAIL_OK', 'value': 99.8, 'displayValue': '99.8 %', 'detail': '覆盖超长标识符 metric_unbroken_token_tail_ok 实测', 'summary': '兼顾纸面呼吸感与抗断线稳定性', 'at': 0.2},
        'focusCallout': {'stops': [{'crop': {'x': 0.0, 'y': 0.0, 'w': 1.0, 'h': 1.0}, 'anchor': {'x': 0.78, 'y': 0.28}, 'label': '全局架构视口概览 CALLOUT_TAIL_1', 'detail': '外沿引线零像素侵入主画面内部', 'at': 0.15}, {'crop': {'x': 0.32, 'y': 0.38, 'w': 0.52, 'h': 0.5}, 'anchor': {'x': 0.88, 'y': 0.68}, 'label': '局部推进稀疏路由核 callout_router_tail_ok', 'detail': '视口平滑推拉并同步切换外置标注焦点', 'at': 1.05}]},
    }
    geom = {'x': region['x'], 'y': region['y'], 'width': region['width'], 'height': region['height']}
    scenes = [('s_flow', 0.0, 2.0, 'motions/flow-path', {**geom, 'title': '流水线 TITLE_FLOW', 'data': 'flowPath'}), ('s_topo', 2.0, 4.0, 'motions/topology-graph', {**geom, 'title': '系统拓扑 TITLE_TOPO', 'data': 'topologyGraph'}), ('s_bar', 4.0, 6.0, 'motions/chart-build', {**geom, 'variant': 'bar', 'title': '吞吐对比', 'unit': ' fps', 'data': 'chartBar'}), ('s_line', 6.0, 8.0, 'motions/chart-build', {**geom, 'variant': 'line', 'title': '版本趋势', 'unit': ' req/s', 'data': 'chartLine'}), ('s_metric', 8.0, 10.0, 'motions/chart-build', {**geom, 'variant': 'metric', 'unit': '%', 'data': 'chartMetric'}), ('s_callout', 10.0, 12.0, 'motions/focus-callout', {**geom, 'title': '视口推拉标注', 'src': 'assets/diagram.png', 'intrinsicWidth': 1200, 'intrinsicHeight': 800, 'data': 'focusCallout'})]
    mounts = [(c, p, {'data-start': str(s), 'data-duration': str(e - s), 'data-scene-id': sid, 'data-scene-start': str(s), 'data-scene-end': str(e)}) for sid, s, e, c, p in scenes]
    tails = ('FLOW_TAIL_1', 'flow_token_alpha_ok', 'unbrokenidentifierwithoutdelimiterstailFLOW3', 'EDGE_2', 'TOPO_TAIL_1', 'TOPO_TAIL_4', 'zero_copy_bar_tail_ok', 'v2.0_readout_tail_ok', 'METRIC_TAIL_OK', 'metric_unbroken_token_tail_ok', 'callout_router_tail_ok', '156 fps', '99.8 %')

    with composition_url_with_mounts(tmp_path, video, mounts, canvas=canvas) as url:
        diag = tmp_path / 'composition/assets/diagram.png'
        diag.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=1200x800:d=0.1', '-frames:v', '1', str(diag)], capture_output=True, check=True)
        with chrome_cdp.launch_isolated() as session:
            page, errors = open_component_page(session.browser, url, viewport=canvas)
            page.evaluate("""() => { const o = window.seek; window.seek = async (t) => { for (const el of document.querySelectorAll('[data-scene-id]')) el.style.display = t >= Number(el.dataset.sceneStart) && t < Number(el.dataset.sceneEnd) ? 'block' : 'none'; return o(t); }; }""")
            flow_q = """async (t) => { await window.seek(t); const h = document.querySelector('[data-scene-id="s_flow"]'); return { vb: h.querySelector('#fp-svg').getAttribute('viewBox'), nodes: Array.from(h.querySelectorAll('.fp-node')).map((g) => { const r = g.querySelector('rect').getBoundingClientRect(); return { op: Number(getComputedStyle(g).opacity), st: g.style.getPropertyValue('--node-stroke'), x: Math.round(r.x), y: Math.round(r.y), ts: g.querySelectorAll('tspan').length }; }), dashes: Array.from(h.querySelectorAll('.fp-edges path[pathLength="1"]')).map((p) => Number(p.style.strokeDashoffset || 0)) }; }"""
            f_early, f_late = page.evaluate(flow_q, 0.45), page.evaluate(flow_q, 1.75)
            axis_key = 'y' if orientation == 'portrait' else 'x'
            assert f_early['vb'] == f"0 0 {region['width']} {region['height']}" and f_early['nodes'][0]['op'] > 0.5 and f_early['nodes'][2]['op'] == pytest.approx(0)
            assert (f_late['nodes'][0]['st'], f_late['nodes'][2]['st']) == ('var(--c-done)', 'var(--c-positive-solid)')
            assert all(d == pytest.approx(0) for d in f_late['dashes']) and any(n['ts'] >= 2 for n in f_late['nodes'])
            assert f_late['nodes'][0][axis_key] < f_late['nodes'][1][axis_key] < f_late['nodes'][2][axis_key] and page.evaluate(flow_q, 0.45) == f_early

            topo_end = page.evaluate("""async () => { await window.seek(3.7); return Array.from(document.querySelectorAll('[data-scene-id="s_topo"] .tg-node')).map((g) => [Number(getComputedStyle(g).opacity), g.style.getPropertyValue('--node-stroke')]); }""")
            assert topo_end[0][0] == pytest.approx(0.56) and topo_end[1][1] == 'var(--c-focus)' and topo_end[3][1] == 'var(--c-focus)'

            fc_q = """async (t) => { await window.seek(t); const h = document.querySelector('[data-scene-id="s_callout"]'), vp = h.querySelector('#fc-viewport').getBoundingClientRect(); const hits = Array.from(h.querySelectorAll('.fc-card rect, .fc-leaders path, .fc-leaders circle')).filter((el) => { if (Number(getComputedStyle(el).opacity) < 0.03) return false; const b = el.getBoundingClientRect(); return Math.max(0, Math.min(b.right, vp.right - 1) - Math.max(b.left, vp.x + 1)) * Math.max(0, Math.min(b.bottom, vp.bottom - 1) - Math.max(b.top, vp.y + 1)) > 1; }); return { vb: getComputedStyle(h.querySelector('#fc-img')).objectViewBox, hits: hits.length }; }"""
            fc1, fc2 = page.evaluate(fc_q, 10.6), page.evaluate(fc_q, 11.85)
            assert fc1 == {'vb': 'inset(0%)', 'hits': 0} and fc2['hits'] == 0 and '38%' in fc2['vb'] and page.evaluate(fc_q, 10.6) == fc1

            rendered_all = []
            for sid, s, e, _, _ in scenes:
                chk = page.evaluate("""async ({ sid, t }) => {
                  await window.seek(t); const h = document.querySelector(`[data-scene-id="${sid}"]`);
                  const txt = Array.from(h.querySelectorAll('text')).map((el) => Array.from(el.querySelectorAll('tspan')).map((x) => x.textContent).join('') || el.textContent).join(' || ');
                  const overflow = [];
                  for (const g of h.querySelectorAll('g')) {
                    const rects = Array.from(g.children).filter((c) => c.tagName.toLowerCase() === 'rect');
                    if (rects.length !== 1) continue;
                    const b = rects[0].getBoundingClientRect(); if (b.width < 30 || b.height < 24) continue;
                    for (const te of g.querySelectorAll(':scope > text, :scope > g[data-text-role="ui"]:not(.fp-badge):not(.fc-badge) > text')) {
                      const tb = te.getBoundingClientRect();
                      if (tb.width > 0 && (tb.left < b.left - 3 || tb.right > b.right + 3 || tb.top < b.top - 3 || tb.bottom > b.bottom + 3)) overflow.push(te.textContent);
                    }
                  }
                  const cards = Array.from(h.querySelectorAll('.fp-node, .tg-node, .fc-card')).filter((g) => Number(getComputedStyle(g).opacity) > 0.05).map((g) => g.querySelector('rect').getBoundingClientRect());
                  let overlaps = 0;
                  for (let i = 0; i < cards.length; i++) for (let j = i + 1; j < cards.length; j++) if (Math.max(0, Math.min(cards[i].right, cards[j].right) - Math.max(cards[i].left, cards[j].left)) * Math.max(0, Math.min(cards[i].bottom, cards[j].bottom) - Math.max(cards[i].top, cards[j].top)) > 1) overlaps++;
                  return { txt, overflow, overlaps };
                }""", {'sid': sid, 't': e - 0.15})
                assert '…' not in chk['txt'] and chk['overflow'] == [] and chk['overlaps'] == 0, f'{orientation} {sid}: {chk}'
                rendered_all.append(chk['txt'])
            assert all(tok in ' || '.join(rendered_all) for tok in tails)
            snapshots = collect_snapshots(page, [{'scene_id': sid, 'time': round(t, 3)} for sid, s, e, _, _ in scenes for t in (s + 0.1, (s + e) / 2, e - 0.1)])
            assert page.evaluate('window.__mountErrors') == [] and errors == []
            page.close()

    ws = tmp_path / f'qa_{orientation}'
    (ws / 'composition').mkdir(parents=True); (ws / 'voice_clone').mkdir(parents=True)
    (ws / 'composition/index.html').write_text('<html></html>', encoding='utf-8')
    (ws / 'inputs.json').write_text(json.dumps({'orientation': orientation}), encoding='utf-8')
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=mono', '-t', '12', '-c:a', 'libmp3lame', str(ws / 'voice_clone/narration.mp3')], capture_output=True, check=True)
    cap_spec = {'width_px': 1166, 'font_size_px': 36, 'max_lines': 1} if orientation == 'landscape' else {'width_px': 600, 'font_size_px': 38, 'max_lines': 2}
    cap_rect = {'x': 96, 'y': 1008, 'width': 1166, 'height': 72} if orientation == 'landscape' else {'x': 70, 'y': 1776, 'width': 600, 'height': 144}
    scene_cfg, snaps_path = ws / 'composition/scene-config.json', ws / 'snapshots.json'
    scene_cfg.write_text(json.dumps({'version': 1, 'canvas': {'width': canvas[0], 'height': canvas[1]}, 'total_s': 12.0, 'scenes': [{'scene_id': sid, 'source_scene_ids': [sid], 'begin_s': s, 'end_s': e, 'template': None, 'layout': {'preset': None, 'regions': [{'id': 'main', 'kind': 'content', 'rect': region}, {'id': 'caption-text', 'kind': 'reserved', 'rect': cap_rect, 'component': 'caption-bar'}], 'caption': cap_spec}} for sid, s, e, _, _ in scenes]}, ensure_ascii=False), encoding='utf-8')
    snaps_path.write_text(json.dumps(snapshots, ensure_ascii=False), encoding='utf-8')
    qa = subprocess.run([sys.executable, str(ROOT / 'scripts/check-composition.py'), str(ws / 'composition'), '--scene-config', str(scene_cfg), '--design', str(ROOT / 'modules/designs/default/default.md'), '--snapshots-from', str(snaps_path)], capture_output=True, text=True)
    assert qa.returncode == 0 and json.loads(qa.stdout)['verdict'] == 'pass'


def test_default_design_h264_mp4_preserves_thin_lines_and_translucent_paper_texture(tmp_path: Path, require_ffmpeg):
    import subprocess
    from PIL import Image, ImageStat
    import video_contract

    video = {'chartBuild': {'items': [{'label': 'Base', 'value': 38, 'at': 0.1}, {'label': 'Cache', 'value': 84, 'at': 0.4}, {'label': 'ZeroCopy', 'value': 148, 'at': 0.7, 'emphasis': True}]}}
    params = {'x': 96, 'y': 96, 'width': 1240, 'height': 888, 'variant': 'bar', 'orientation': 'vertical', 'title': 'H.264 Thin-Line & Paper Grain'}
    with composition_url_with_mounts(tmp_path, video, [('motions/chart-build', params)]) as url:
        comp, frames, mp4, png = tmp_path / 'composition', tmp_path / 'frames', tmp_path / 'out.mp4', tmp_path / 'decoded.png'
        (comp / 'assets/textures').mkdir(parents=True); frames.mkdir()
        shutil.copyfile(ROOT / 'modules/designs/default/textures/paper.jpg', comp / 'assets/textures/paper.jpg')
        tokens = '; '.join(f'{k}: {v}' for k, v in video_contract.load_design_preset(ROOT, 'default')['tokens'].items())
        idx = comp / 'index.html'
        idx.write_text(idx.read_text(encoding='utf-8').replace('</style>', f':root{{{tokens};}} #ground{{position:fixed;inset:0;background:var(--ground)}} #card-mix{{position:absolute;left:1368px;top:96px;width:456px;height:560px;border-radius:12px;border:1.5px solid var(--c-border);background:color-mix(in srgb, var(--c-card) 82%, transparent)}} #card-flat{{position:absolute;left:1368px;top:688px;width:456px;height:296px;border-radius:12px;border:1.5px solid var(--c-border);background:var(--c-card)}}</style>').replace('<body>', '<body><div id="ground"></div>').replace('</main>', '<div id="card-mix"></div><div id="card-flat"></div></main>'), encoding='utf-8')
        with chrome_cdp.launch_isolated() as session:
            page, errors = open_component_page(session.browser, url, viewport=(1920, 1080))
            geom = page.evaluate("""async () => { await window.seek(1.5); const d = document.querySelector('.cb-header line').getBoundingClientRect(); return { div: { l: d.left, r: d.right, y: (d.top + d.bottom) / 2 }, lines: Array.from(document.querySelectorAll('.cb-grid line')).map((l) => { const r = l.getBoundingClientRect(); return { sw: l.getAttribute('stroke-width'), dash: l.getAttribute('stroke-dasharray'), x1: r.left, x2: r.right, y: (r.top + r.bottom) / 2 }; }), bars: Array.from(document.querySelectorAll('.cb-bar-col')).map((g) => { const r = g.getBoundingClientRect(); return { l: r.left, r: r.right }; }) }; }""")
            for i in range(6):
                page.evaluate('window.seek', 1.2 + i * 0.05); page.screenshot(path=str(frames / f'f_{i:02d}.png'))
            assert page.evaluate('window.__mountErrors') == [] and errors == []
            page.close()

    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-framerate', '15', '-i', str(frames / 'f_%02d.png'), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(mp4)], capture_output=True, check=True)
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', '0.2', '-i', str(mp4), '-frames:v', '1', str(png)], capture_output=True, check=True)
    im = Image.open(png).convert('L'); px = im.load()
    dy, axis, dash = round(geom['div']['y']), next(g for g in geom['lines'] if not g['dash']), min((g for g in geom['lines'] if g['dash']), key=lambda g: g['y'])
    ay, gy = round(axis['y']), round(dash['y'])
    div_c = [(px[x, dy - 4] + px[x, dy + 4]) / 2 - min(px[x, dy - 1], px[x, dy], px[x, dy + 1]) for x in range(int(geom['div']['l']) + 12, int(geom['div']['r']) - 12)]
    axis_c = [(px[x, ay - 5] + px[x, ay + 5]) / 2 - min(px[x, ay - 1], px[x, ay], px[x, ay + 1]) for x in range(int(axis['x1']) + 12, int(axis['x2']) - 12) if not any(b['l'] - 8 <= x <= b['r'] + 8 for b in geom['bars'])]
    peaks = [max((px[x, gy - 4] + px[x, gy + 4]) / 2 - min(px[x, gy - 1], px[x, gy], px[x, gy + 1]) for x in range(wx, wx + 16)) for wx in range(int(dash['x1']) + 16, int(geom['bars'][-1]['l']) - 32, 16) if not any(b['l'] - 10 <= wx <= b['r'] + 10 for b in geom['bars'])]
    assert axis['sw'] == '1.25' and min(div_c) >= 6.0 and min(axis_c) >= 8.0 and min(peaks) >= 3.5
    assert ImageStat.Stat(im.crop((1384, 112, 1808, 640))).stddev[0] > 0.5 and ImageStat.Stat(im.crop((1384, 704, 1808, 968))).stddev[0] < 0.15


def _wide_ttf_bytes(family: str = 'WideGlyphTest', advance: int = 1800, upem: int = 1000) -> bytes:
    import struct
    g = struct.pack('>hhhhhHH4B4h4h', 1, 50, 0, advance - 50, 700, 3, 0, 1, 1, 1, 1, 50, advance - 100, 0, 100 - advance, 0, 0, 700, -700)
    g += b'\x00' * ((4 - len(g) % 4) % 4)
    gids, fam, sub = [2] * 94, family.encode('utf-16-be'), 'Regular'.encode('utf-16-be')
    cmap_s = struct.pack('>7H3HH3H3h3H94H', 4, 228, 0, 6, 4, 1, 2, 0x20, 0x7E, 0xFFFF, 0, 0x20, 0x21, 0xFFFF, 1 - 0x20, 0, 1, 0, 4, 0, *gids)
    offs, lens = (0, len(fam), len(fam) + len(sub), len(fam) * 2 + len(sub)), (len(fam), len(sub), len(fam), len(fam))
    name = struct.pack('>3H', 0, 4, 54) + b''.join(struct.pack('>6H', 3, 1, 0x0409, nid, ln, of) for nid, ln, of in zip((1, 2, 4, 6), lens, offs)) + fam + sub + fam + fam
    tables = {
        'OS/2': struct.pack('>Hh3H11h10s4I4s3H3h2H', 0, advance, 400, 5, 0, 650, 600, 0, 75, 650, 600, 0, 475, 50, 250, 0, b'\0' * 10, 1, 0, 0, 0, b'TEST', 0x40, 0x20, 0x7E, 800, -200, 0, 800, 200),
        'cmap': struct.pack('>2H2HI', 0, 1, 3, 1, 12) + cmap_s, 'glyf': g + g,
        'head': struct.pack('>2H3I2H2Q4h2H3h', 1, 0, 0x10000, 0, 0x5F0F3CF5, 0x0B, upem, 0, 0, 0, -200, advance, 800, 0, 8, 2, 0, 0),
        'hhea': struct.pack('>I3hH11hH', 0x10000, 800, -200, 0, advance, 0, 0, advance, 1, 0, 0, 0, 0, 0, 0, 0, 3),
        'hmtx': struct.pack('>3HhHh', upem, 0, 600, 0, advance, 0), 'loca': struct.pack('>4H', 0, len(g) // 2, len(g) // 2, len(g)),
        'maxp': struct.pack('>I14H', 0x10000, 3, 4, 1, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0), 'name': name, 'post': struct.pack('>Iihh5I', 0x30000, 0, -100, 50, 0, 0, 0, 0, 0),
    }
    off, entries, body = 12 + 16 * len(tables), [], []
    for tag in sorted(tables):
        raw = tables[tag]; pad = raw + b'\x00' * ((4 - len(raw) % 4) % 4)
        entries.append(struct.pack('>4s3I', tag.encode(), sum(struct.unpack(f'>{len(pad) // 4}I', pad)) & 0xFFFFFFFF, off, len(raw)))
        body.append(pad); off += len(pad)
    return struct.pack('>I4H', 0x10000, 10, 128, 3, 32) + b''.join(entries) + b''.join(body)


def test_motion_modules_relayout_on_delayed_wide_font_and_isolate_destroy(tmp_path: Path):
    font_req, release, wide_ttf = threading.Event(), threading.Event(), _wide_ttf_bytes()
    video = {
        'flow': {'nodes': [{'id': 'a', 'label': 'alpha beta gamma', 'at': 0.1}, {'id': 'b', 'label': 'delta zeta theta', 'at': 0.8}]},
        'topo': {'layers': [{'id': 'l1', 'label': 'edge'}, {'id': 'l2', 'label': 'core'}], 'nodes': [{'id': 'n1', 'label': 'alpha beta gamma', 'layer': 'l1', 'at': 0.1}, {'id': 'n2', 'label': 'delta zeta theta', 'layer': 'l2', 'at': 0.7, 'emphasis': True}], 'links': [{'from': 'n1', 'to': 'n2', 'at': 0.5}]},
        'lineA': {'points': [{'label': 'alpha beta gamma', 'value': 10, 'at': 0.1}, {'label': 'delta zeta', 'value': 40, 'at': 0.8}], 'summary': 'alpha beta gamma', 'summaryAt': 0.5},
        'lineB': {'points': [{'label': 'Q1', 'value': 90, 'at': 0.1}, {'label': 'Q2', 'value': 180, 'at': 0.8}]},
        'callout': {'targetRect': {'x': 24, 'y': 24, 'width': 420, 'height': 340}, 'stops': [{'anchor': {'x': 0.8, 'y': 0.4}, 'label': 'alpha beta', 'at': 0.5}]},
    }
    mounts = [
        ('motions/flow-path', {'x': 20, 'y': 20, 'width': 540, 'height': 460, 'direction': 'vertical', 'data': 'flow'}),
        ('motions/topology-graph', {'x': 580, 'y': 20, 'width': 540, 'height': 460, 'data': 'topo'}),
        ('motions/chart-build', {'x': 20, 'y': 500, 'width': 540, 'height': 460, 'variant': 'line', 'data': 'lineA'}),
        ('motions/chart-build', {'x': 1140, 'y': 500, 'width': 740, 'height': 460, 'variant': 'line', 'data': 'lineB'}),
        ('motions/focus-callout', {'x': 580, 'y': 500, 'width': 820, 'height': 460, 'data': 'callout'}),
        ('motions/flow-path', {'x': 1280, 'y': 20, 'width': 540, 'height': 460, 'direction': 'vertical', 'data': 'flow'}),
    ]
    with composition_url_with_mounts(tmp_path, video, mounts):
        pass
    idx = tmp_path / 'composition/index.html'
    idx.write_text(idx.read_text(encoding='utf-8').replace('--font-sans: Arial, sans-serif; --font-mono: monospace;', '--font-sans: "WideGlyphTest", Arial, sans-serif; --font-mono: "WideGlyphTest", monospace;').replace('</style>', '</style><script>const ff=new FontFace("WideGlyphTest","url(delayed-wide.ttf)",{weight:"100 900"});document.fonts.add(ff);window.__fontLoaded=ff.load();</script>'), encoding='utf-8')

    class GatedHandler(QuietHandler):
        def do_GET(self):
            if self.path.split('?', 1)[0].endswith('/delayed-wide.ttf'):
                font_req.set(); release.wait(timeout=15)
                try: self.send_response(200); self.send_header('Content-Type', 'font/ttf'); self.send_header('Content-Length', str(len(wide_ttf))); self.end_headers(); self.wfile.write(wide_ttf)
                except BrokenPipeError: pass
                return
            super().do_GET()

    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(GatedHandler, directory=str(tmp_path / 'composition')))
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        with chrome_cdp.launch_isolated() as session:
            page, errors = session.browser.new_page(viewport={'width': 1920, 'height': 1080}), []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(f'http://127.0.0.1:{server.server_port}/index.html', wait_until='domcontentloaded', timeout=30000)
            assert font_req.wait(timeout=10)
            page.evaluate('window.__mountPromise')
            before = page.evaluate("""() => {
              window.__tls = new Map(window.__instances.map((e) => [e.host.id, e.instance.timeline]));
              for (const e of window.__instances) if (e.host.id !== 'flow-path-2') e.instance.timeline.pause().seek(1.2, false);
              const [dead] = window.__instances.splice(window.__instances.findIndex((e) => e.host.id === 'flow-path-2'), 1);
              dead.instance.destroy(); window.__deadReady = dead.instance.ready;
              const idsA = Array.from(document.querySelectorAll('#chart-build defs [id]')).map((x) => x.id), idsB = new Set(Array.from(document.querySelectorAll('#chart-build-2 defs [id]')).map((x) => x.id));
              const card = (s) => { const g = document.querySelector(s), r = g.querySelector('rect').getBoundingClientRect(); return { w: r.width, h: r.height, ts: g.querySelector(':scope > text').querySelectorAll('tspan').length }; };
              return { status: document.fonts.status, deadHtml: document.querySelector('#flow-path-2 svg').innerHTML, overlap: idsA.filter((x) => idsB.has(x)), fcImgs: Array.from(document.querySelectorAll('#focus-callout img')).filter((i) => i.offsetParent !== null).length, flow: card('#flow-path .fp-node'), topo: card('#topology-graph .tg-node'), summary: card('#chart-build .cb-summary'), callout: card('#focus-callout .fc-card') };
            }""")
            assert before['status'] == 'loading' and before['overlap'] == [] and before['fcImgs'] == 0 and all(before[k]['ts'] == 1 for k in ('flow', 'topo', 'summary', 'callout'))
            release.set()
            after = page.evaluate("""async () => {
              await window.__fontLoaded; await window.__deadReady; await Promise.all(window.__instances.map((e) => e.instance.ready));
              const card = (s) => { const g = document.querySelector(s), r = g.querySelector('rect').getBoundingClientRect(); return { w: r.width, h: r.height, ts: g.querySelector(':scope > text').querySelectorAll('tspan').length }; };
              const bad = [];
              for (const e of window.__instances) for (const ts of e.host.querySelectorAll('tspan[data-max-width]')) if (ts.hasAttribute('lengthAdjust') || ts.getComputedTextLength() > Number(ts.getAttribute('data-max-width')) + 1) bad.push(ts.textContent);
              const sameTl = window.__instances.every((e) => e.instance.timeline === window.__tls.get(e.host.id)), times = window.__instances.map((e) => e.instance.timeline.time());
              const valB = document.querySelector('#chart-build-2 .cb-readout text[text-anchor="end"]').textContent.trim();
              const recededOp = Number(getComputedStyle(document.querySelectorAll('#flow-path .fp-node')[0]).opacity);
              window.__tls.get('flow-path').seek(0.2);
              const backOp = Number(getComputedStyle(document.querySelectorAll('#flow-path .fp-node')[1]).opacity);
              const u = await import('./compositions/motion-utils.mjs'), svg = document.querySelector('#flow-path svg');
              const toks = u.readThemeTokens(document.documentElement);
              const cv = document.createElement('canvas'), ctx = cv.getContext('2d');
              const cvPat = u.createCanvasHatchPattern(ctx, { color: toks.border, alpha: 0.22 });
              const craft = {
                hasMask: Boolean(svg.querySelector('mask[id$="-grid-mask"]')),
                hasTrim: Boolean(document.querySelector('#flow-path .fp-node .m-card-trim')),
                hasPort: Boolean(document.querySelector('#topology-graph .tg-node .m-port')),
                hasHatch: Boolean(document.querySelector('#topology-graph defs pattern[id$="-band-hatch"]')),
                tokFocus: Boolean(toks.focus && toks.enterDuration > 0 && toks.easing),
                canvasPattern: Boolean(cvPat && typeof cvPat === 'object'),
              };
              return { status: document.fonts.status, deadHtml: document.querySelector('#flow-path-2 svg').innerHTML, bad, sameTl, times, valB, recededOp, backOp, craft, wrapped: u.wrapLines('alpha beta gamma', 320, 26, svg).length, probes: svg.querySelectorAll('text[aria-hidden="true"]').length, flow: card('#flow-path .fp-node'), topo: card('#topology-graph .tg-node'), summary: card('#chart-build .cb-summary'), callout: card('#focus-callout .fc-card') };
            }""")
            assert after['status'] == 'loaded' and after['deadHtml'] == before['deadHtml'] and after['bad'] == []
            assert after['sameTl'] is True and after['times'] == [pytest.approx(1.2)] * 5 and after['valB'] == '180' and after['backOp'] == pytest.approx(0)
            assert after['recededOp'] == pytest.approx(0.64) and all(after['craft'].values()), after['craft']
            assert after['wrapped'] >= 2 and after['probes'] == 0 and all(after[k]['ts'] >= 2 and (after[k]['h'] > before[k]['h'] or after[k]['w'] > before[k]['w']) for k in ('flow', 'topo', 'summary', 'callout'))
            assert page.evaluate('window.__mountErrors') == [] and errors == []
            page.close()
    finally:
        release.set(); server.shutdown(); server.server_close(); thread.join(timeout=5)
