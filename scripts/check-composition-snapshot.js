// Snapshot collection for scripts/check-composition.py.
// Loaded by the Python script and passed to Playwright's page.evaluate;
// it must stay a single async function expression: async (args) => {...}
async ({ checks }) => {
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  async function seekTo(seconds) {
    const time = Math.max(0, Number(seconds) || 0);
    const timeMs = time * 1000;
    let didSeek = false;

    if (window.__layoutQA && typeof window.__layoutQA.seek === 'function') {
      try { await window.__layoutQA.seek(time); didSeek = true; } catch (_) {}
    }
    const timelines = window.__timelines ? Object.values(window.__timelines).filter(Boolean) : [];
    for (const timeline of timelines) {
      try {
        if (typeof timeline.pause === 'function') timeline.pause();
        if (typeof timeline.seek === 'function') { timeline.seek(time, false); didSeek = true; }
        else if (typeof timeline.totalTime === 'function') { timeline.totalTime(time, false); didSeek = true; }
      } catch (_) {}
    }
    const animeInstances = Array.isArray(window.__hfAnime) ? window.__hfAnime : [];
    for (const entry of animeInstances) {
      const animation = entry && (entry.animation || entry.instance || entry);
      try {
        if (typeof animation.pause === 'function') animation.pause();
        if (typeof animation.seek === 'function') { animation.seek(timeMs); didSeek = true; }
      } catch (_) {}
    }
    for (const media of Array.from(document.querySelectorAll('video,audio'))) {
      try {
        media.pause();
        if (Number.isFinite(media.duration)) {
          media.currentTime = Math.max(0, Math.min(time, media.duration || time));
        }
        didSeek = true;
      } catch (_) {}
    }
    // Test seam: compositions may toggle scene visibility on this event; the
    // built-in seek hooks above drive real animation timelines.
    window.__checkTime = time;
    try { document.dispatchEvent(new CustomEvent('check-time', { detail: { time } })); } catch (_) {}
    await sleep(didSeek ? 80 : 120);
  }

  function hasBox(rect) {
    return rect && rect.width > 3 && rect.height > 3;
  }

  function visible(el) {
    let current = el;
    while (current && current.nodeType === Node.ELEMENT_NODE) {
      const style = getComputedStyle(current);
      if (style.display === 'none' || ['hidden', 'collapse'].includes(style.visibility)
          || Number(style.opacity || 1) < 0.03) return false;
      current = current.parentElement;
    }
    return hasBox(el.getBoundingClientRect());
  }

  function labelOf(el) {
    return `${el.tagName || ''} ${el.id || ''} ${typeof el.className === 'string' ? el.className : ''}`.toLowerCase();
  }

  function hasOwnText(el) {
    return Array.from(el.childNodes).some(
      (node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim().length > 0);
  }

  function textContent(el) {
    return (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
  }

  function hasVisibleSurface(el) {
    const style = getComputedStyle(el);
    return (
      style.backgroundImage !== 'none' ||
      (style.backgroundColor && !['rgba(0, 0, 0, 0)', 'transparent'].includes(style.backgroundColor)) ||
      parseFloat(style.borderTopWidth || '0') > 0
    );
  }

  function selectorFor(el) {
    if (el.id) return `#${el.id}`;
    const classes = typeof el.className === 'string'
      ? el.className.trim().split(/\s+/).filter(Boolean).slice(0, 3) : [];
    if (classes.length) return `${el.tagName.toLowerCase()}.${classes.join('.')}`;
    return el.tagName.toLowerCase();
  }

  function collectSnapshot(time) {
    const elements = [];
    for (const el of Array.from(document.querySelectorAll('*'))) {
      if (el.nodeType !== Node.ELEMENT_NODE) continue;
      const rect = el.getBoundingClientRect();
      if (!hasBox(rect) || !visible(el)) continue;
      const style = getComputedStyle(el);
      const isSceneRoot = el.hasAttribute('data-scene-id');
      const layoutIgnore = el.hasAttribute('data-layout-ignore');
      const ancestors = [];
      let current = el.parentElement;
      while (current) {
        if (current.id) ancestors.push(current.id);
        if (current.getAttribute && current.getAttribute('data-composition-id')) {
          ancestors.push(current.getAttribute('data-composition-id'));
        }
        current = current.parentElement;
      }
      let media = null;
      if (el.tagName === 'IMG') {
        media = { tag: 'img', complete: el.complete, naturalWidth: el.naturalWidth,
                  src: el.getAttribute('src') || '' };
      } else if (el.tagName === 'VIDEO') {
        media = { tag: 'video', readyState: el.readyState, error: Boolean(el.error),
                  src: el.getAttribute('src') || '' };
      }
      elements.push({
        selector: selectorFor(el),
        id: el.id || '',
        tag: el.tagName.toLowerCase(),
        label: labelOf(el),
        rect: { x: rect.left, y: rect.top, width: rect.width, height: rect.height },
        ownText: hasOwnText(el),
        text: textContent(el),
        fontSize: parseFloat(style.fontSize || '0') || 0,
        isCaption: /subtitle|caption|closed-caption/.test(labelOf(el)),
        isUiText: Boolean(el.closest('[data-text-role="ui"]')),
        isSceneRoot,
        layoutIgnore,
        surface: hasVisibleSurface(el),
        media,
        ancestors,
        overflowStyle: [style.overflowX, style.overflowY].join(' '),
        clientWidth: el.clientWidth,
        clientHeight: el.clientHeight,
        scrollWidth: el.scrollWidth,
        scrollHeight: el.scrollHeight,
      });
    }
    const captionTexts = elements
      .filter((el) => el.isCaption && el.ownText && el.text)
      .map((el) => el.text);
    return {
      time,
      fontsStatus: document.fonts ? document.fonts.status : 'loaded',
      elements,
      captionTexts,
    };
  }

  const results = [];
  for (const check of checks) {
    await seekTo(check.time);
    await sleep(150);
    results.push({ scene_id: check.scene_id, ...collectSnapshot(check.time) });
  }
  return results;
}
