"""Real-Chrome integration tests for scene-aware reusable components.

The fixture loads the component HTML verbatim through data-composition-src.
A small test-only HyperFrames host supplies variables and deterministic seeks;
no npm install or preview server is needed. Jay still performs its real image
build, simulation, and WebGL rendering in Chrome.
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


# The production components use GSAP's paused-timeline API. This deliberately
# small deterministic implementation supports only the set/fromTo/to/seek calls
# they make. Reapplying operations from each element's original inline style is
# important: it exercises both forward and backward seeks rather than merely
# checking the final state after monotonically playing the timeline.
TIMELINE_SEEKER = r"""
(() => {
  const isElement = (target) => target instanceof Element;
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
    constructor() { this.operations = []; this.targets = new Map(); }
    remember(target) {
      if (isElement(target) && !this.targets.has(target)) {
        this.targets.set(target, target.getAttribute('style') || '');
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
    pause() { return this; }
    seek(time) {
      for (const [target, style] of this.targets) target.setAttribute('style', style);
      const operations = this.operations.map((operation, index) => ({ operation, index }))
        .sort((a, b) => a.operation.at - b.operation.at || a.index - b.index);
      for (const { operation } of operations) {
        const { kind, target, at } = operation;
        if (time < at) continue;
        if (kind === 'set') {
          for (const [name, value] of Object.entries(operation.values)) put(target, name, value);
          continue;
        }
        const duration = numeric(operation.to.duration);
        const progress = duration > 0 ? Math.max(0, Math.min(1, (time - at) / duration)) : 1;
        if (kind === 'fromTo') {
          for (const [name, value] of Object.entries(operation.to)) {
            if (name === 'duration' || name === 'ease') continue;
            put(target, name, mix(operation.from[name], value, progress));
          }
        } else {
          for (const [name, value] of Object.entries(operation.to)) {
            if (name === 'duration' || name === 'ease') continue;
            put(target, name, mix(current(target, name), value, progress));
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
window.__timelines = {};
window.__hyperframes = {
  getVariables: () => window.__mountVariables || {},
};
window.__mountErrors = [];
async function mountComposition(host) {
  const response = await fetch(host.getAttribute('data-composition-src'));
  if (!response.ok) throw new Error(`mount failed: ${response.status} ${response.statusText}`);
  const documentNode = new DOMParser().parseFromString(await response.text(), 'text/html');
  const template = documentNode.querySelector('template');
  if (!template) throw new Error('component has no template');
  const fragment = template.content.cloneNode(true);
  const scripts = Array.from(fragment.querySelectorAll('script')).map((script) => {
    const source = script.textContent;
    script.remove();
    return source;
  });
  host.appendChild(fragment);
  window.__mountVariables = JSON.parse(host.getAttribute('data-variable-values') || '{}');
  try {
    for (const source of scripts) {
      const script = document.createElement('script');
      script.textContent = source;
      host.appendChild(script);
    }
  } finally {
    window.__mountVariables = {};
  }
}
window.__mountPromise = (async () => {
  for (const host of document.querySelectorAll('[data-composition-src]')) {
    await mountComposition(host);
  }
})();
window.seek = async (time) => {
  await window.__mountPromise;
  for (const timeline of Object.values(window.__timelines)) timeline.pause().seek(time, false);
  const pending = [];
  window.dispatchEvent(new CustomEvent('hf-seek', {
    detail: { time, waitUntil: (promise) => pending.push(Promise.resolve(promise)) },
  }));
  await Promise.all(pending);
};
"""


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        pass


@contextmanager
def composition_url(tmp_path: Path, video: dict, *components: str):
    """Serve a temporary host while loading component sources from this repo."""
    composition = tmp_path / 'composition'
    (composition / 'compositions').mkdir(parents=True)
    mounts = []
    for component in components:
        source = ROOT / 'modules/components' / component / f'{component}.html'
        shutil.copyfile(source, composition / 'compositions' / f'{component}.html')
        mounts.append(
            f'<div id="{component}" data-composition-id="{component}" '
            f'data-composition-src="compositions/{component}.html" data-start="0" '
            f'data-duration="6" data-width="1920" data-height="1080" '
            f'style="position:absolute;inset:0"></div>'
        )
    if 'jay' in components:
        images = composition / 'assets/jay'
        images.mkdir(parents=True)
        for name in ('jay-base.png', 'jay-wave.png'):
            shutil.copyfile(ROOT / 'modules/components/jay/images' / name, images / name)

    html = """<!doctype html><html><head><meta charset="utf-8">
      <link rel="icon" href="data:,">
      <style>
        * { box-sizing: border-box; }
        html, body { margin: 0; width: 1920px; height: 1080px; }
        :root { --font-sans: Arial, sans-serif; --c-chrome: #222;
          --c-chrome-ink: #fff; --c-ink: #222; --c-card: #fff;
          --c-border: #888; --c-focus: #06f; --c-highlight: #fc0; }
      </style>
      <script>window.VIDEO = __VIDEO__;</script>
      <script>__TIMELINE_SEEKER__</script>
      </head><body><main data-composition-id="main">__MOUNTS__</main>
      <script>__MOUNTER__</script></body></html>"""
    html = (html.replace('__VIDEO__', json.dumps(video, ensure_ascii=False))
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


def open_component_page(browser, url: str):
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
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
            {'scene_id': 'stage', 'begin_s': 2, 'end_s': 4,
             'caption_rect': {'x': 96, 'y': 1008, 'width': 1728, 'height': 72},
             'caption': {'width_px': 1728, 'font_size_px': 36, 'max_lines': 1}},
            {'scene_id': 'presenter', 'begin_s': 4, 'end_s': 6,
             'caption_rect': {'x': 96, 'y': 1008, 'width': 1166, 'height': 72},
             'caption': {'width_px': 1166, 'font_size_px': 36, 'max_lines': 1}},
        ],
    }
    with composition_url(tmp_path, video, 'caption-bar') as url:
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
            assert errors == []
            page.close()


def jay_state(page, time: float) -> dict:
    return page.evaluate("""async (time) => {
      await window.seek(time);
      const stage = document.querySelector('#jay-stage');
      return { display: getComputedStyle(stage).display,
        left: stage.style.left, top: stage.style.top, size: stage.style.width };
    }""", time)


def test_jay_single_full_video_mount_follows_presenter_scene_visibility(tmp_path: Path):
    video = {'jay': {'duration': 6, 'placements': [
        {'begin_s': 0, 'end_s': 2, 'visible': True, 'x': 1294, 'y': 642, 'size': 420},
        {'begin_s': 2, 'end_s': 4, 'visible': False},
        {'begin_s': 4, 'end_s': 6, 'visible': True, 'x': 1294, 'y': 642, 'size': 420},
    ]}}
    with composition_url(tmp_path, video, 'jay') as url:
        with chrome_cdp.launch_isolated() as session:
            page, errors = open_component_page(session.browser, url)
            page.wait_for_function('Boolean(window.__hf && window.__hf.buildReady && window.__hf.buildReady.jay)')
            # This is the component's real asynchronous image/WebGL build.
            page.evaluate('window.__hf.buildReady.jay')
            assert page.locator('[data-composition-src="compositions/jay.html"]').count() == 1
            host = page.locator('#jay')
            assert host.get_attribute('data-start') == '0'
            assert host.get_attribute('data-duration') == '6'
            assert page.locator('#jay-stage').count() == 1

            assert jay_state(page, 1)['display'] != 'none'
            assert jay_state(page, 3)['display'] == 'none'
            assert jay_state(page, 5) == {
                'display': 'block', 'left': '1294px', 'top': '642px', 'size': '420px',
            }
            assert jay_state(page, 3)['display'] == 'none'
            assert jay_state(page, 1)['display'] != 'none'
            # A nonempty placement contract is closed at the final end_s too.
            assert jay_state(page, 6)['display'] == 'none'

            # The production collector must inspect #jay-stage. The host stays
            # visible and has a full-canvas box, so it cannot make a hidden Jay
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
            assert [snapshot['jayVisible'] for snapshot in snapshots] == [
                True, False, True, False, False,
            ]
            assert errors == []
            page.close()
