# Image Animations Reference — HyperFrames + GSAP

> **Suggestive catalog, not prescriptive.** The Phase 8 coding sub-agent MAY
> consult this when a scene is driven by still images and needs motion. It is
> free to remix, simplify, or invent its own effects — the hyperframes skill
> sets the lint/timing rules; aesthetics are the sub-agent's call.

Use these patterns when a scene is driven by still images (search results, screenshots, extracted video frames) and you want motion directly in the HTML composition instead of pre-rendering video clips with FFmpeg. All examples target the shared HyperFrames GSAP timeline on `window.__timelines["main"]` and use absolute time positions.

## General pattern

- Put the image inside a scene container with `class="scene clip"`.
- Keep the container clipped with `overflow: hidden` whenever the image scales or pans.
- Use `object-fit: cover` for most full-frame images.
- Animate on `window.__timelines["main"]`, not a standalone GSAP timeline.
- Match `data-start` / `data-duration` in HTML with `sceneStart` / `sceneDuration` in JS.

Basic setup pattern:

```html
<div class="scene clip" data-start="0" data-duration="6">
  <img id="example-img" src="images/example.jpg" alt="Example" />
</div>

<script>
  const tl = window.__timelines["main"];
  const sceneStart = 0;
  const sceneDuration = 6;

  tl.fromTo('#example-img', { scale: 1 }, {
    scale: 1.1,
    duration: sceneDuration,
    ease: 'none'
  }, sceneStart);
</script>
```

---

## 1. Ken Burns (Slow Zoom)

**Effect:** A slow centered zoom from 100% to 120%, like a documentary still-image move.

### HTML

```html
<div class="scene clip s1" data-start="0" data-duration="6">
  <img id="s1-img" src="images/ken-burns.jpg" alt="Documentary still" />
</div>
```

### CSS

```css
.s1 {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.s1 img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  transform-origin: 50% 50%;
  will-change: transform;
}
```

### GSAP

```html
<script>
  const tl = window.__timelines["main"];
  const sceneStart = 0;
  const sceneDuration = 6;

  tl.fromTo('#s1-img', {
    scale: 1
  }, {
    scale: 1.2,
    duration: sceneDuration,
    ease: 'none',
    transformOrigin: '50% 50%'
  }, sceneStart);
</script>
```

### Usage notes / gotchas

- `overflow: hidden` on the container is required, otherwise the zoomed image spills outside the scene.
- `object-fit: cover` keeps the frame filled while preserving aspect ratio.
- `ease: 'none'` gives the most FFmpeg-like constant motion.
- For a more subtle move, use `scale: 1.1` instead of `1.2`.

---

## 2. Pan (Horizontal Drift)

**Effect:** A slow left-to-right or right-to-left drift across an oversized image.

### HTML

```html
<div class="scene clip s2" data-start="6" data-duration="6">
  <img id="s2-img" src="images/pan-wide.jpg" alt="Wide image for pan" />
</div>
```

### CSS

```css
.s2 {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.s2 img {
  position: absolute;
  top: 0;
  left: 0;
  width: 130%;
  height: 100%;
  object-fit: cover;
  display: block;
  will-change: transform;
}
```

### GSAP

```html
<script>
  const tl = window.__timelines["main"];
  const sceneStart = 6;
  const sceneDuration = 6;

  tl.fromTo('#s2-img', {
    x: '0%'
  }, {
    x: '-15%',
    duration: sceneDuration,
    ease: 'none'
  }, sceneStart);
</script>
```

### Variant: pan + zoom

```html
<script>
  const tl = window.__timelines["main"];
  const sceneStart = 6;
  const sceneDuration = 6;

  tl.fromTo('#s2-img', {
    x: '0%',
    scale: 1
  }, {
    x: '-15%',
    scale: 1.06,
    duration: sceneDuration,
    ease: 'none',
    transformOrigin: '50% 50%'
  }, sceneStart);
</script>
```

### Usage notes / gotchas

- The image must be wider than the viewport (`width: 120%` to `140%`) or the pan will have no visible travel.
- Use negative `x` to drift left; swap to positive values if you want the image to move right.
- This works especially well for landscape photos in a 16:9 scene.
- Keep the container clipped with `overflow: hidden`.

---

## 3. Slideshow Fade (Multiple Images)

**Effect:** Multiple images are stacked in the same scene and crossfade from one to the next.

### HTML

```html
<div class="scene clip s3" data-start="12" data-duration="9">
  <img id="s3-img1" src="images/slide-1.jpg" alt="Slide 1" />
  <img id="s3-img2" src="images/slide-2.jpg" alt="Slide 2" />
  <img id="s3-img3" src="images/slide-3.jpg" alt="Slide 3" />
</div>
```

### CSS

```css
.s3 {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.s3 img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  opacity: 0;
  will-change: opacity, transform;
}
```

### GSAP

```html
<script>
  const tl = window.__timelines["main"];
  const sceneStart = 12;
  const sceneDuration = 9;

  gsap.set('#s3-img1', { opacity: 1, scale: 1.02 });
  gsap.set(['#s3-img2', '#s3-img3'], { opacity: 0, scale: 1.02 });

  tl.to('#s3-img1', {
    opacity: 0,
    duration: 1,
    ease: 'power1.inOut'
  }, sceneStart + 2);

  tl.fromTo('#s3-img2', {
    opacity: 0
  }, {
    opacity: 1,
    duration: 1,
    ease: 'power1.inOut'
  }, sceneStart + 2);

  tl.to('#s3-img2', {
    opacity: 0,
    duration: 1,
    ease: 'power1.inOut'
  }, sceneStart + 5);

  tl.fromTo('#s3-img3', {
    opacity: 0
  }, {
    opacity: 1,
    duration: 1,
    ease: 'power1.inOut'
  }, sceneStart + 5);

  tl.to(['#s3-img1', '#s3-img2', '#s3-img3'], {
    scale: 1.08,
    duration: sceneDuration,
    ease: 'none',
    overwrite: 'auto'
  }, sceneStart);
</script>
```

### Usage notes / gotchas

- Stack images with `position: absolute` and identical sizing.
- Set the first image visible at the start; all later images should start at `opacity: 0`.
- Crossfades usually feel best with 0.6-1.2 second fade durations.
- Add a subtle shared scale tween to avoid the scene feeling static during the fades.
- For 4 images, keep the same pattern and shift the fade times forward.

---

## 4. Grid Layout

**Effect:** Show 2-4 images at once in a grid, then apply a subtle collective zoom to the whole layout.

### HTML

```html
<div class="scene clip s4" data-start="21" data-duration="6">
  <div id="s4-grid" class="image-grid">
    <div class="cell"><img src="images/grid-1.jpg" alt="Grid image 1" /></div>
    <div class="cell"><img src="images/grid-2.jpg" alt="Grid image 2" /></div>
    <div class="cell"><img src="images/grid-3.jpg" alt="Grid image 3" /></div>
    <div class="cell"><img src="images/grid-4.jpg" alt="Grid image 4" /></div>
  </div>
</div>
```

### CSS

```css
.s4 {
  position: absolute;
  inset: 0;
  overflow: hidden;
  padding: 40px;
  box-sizing: border-box;
}

.s4 .image-grid {
  width: 100%;
  height: 100%;
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 1fr 1fr;
  gap: 20px;
  will-change: transform;
}

.s4 .cell {
  position: relative;
  overflow: hidden;
  border-radius: 20px;
}

.s4 .cell img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
```

### GSAP

```html
<script>
  const tl = window.__timelines["main"];
  const sceneStart = 21;
  const sceneDuration = 6;

  tl.fromTo('#s4-grid', {
    scale: 1
  }, {
    scale: 1.05,
    duration: sceneDuration,
    ease: 'none',
    transformOrigin: '50% 50%'
  }, sceneStart);
</script>
```

### Usage notes / gotchas

- Each grid cell should have `overflow: hidden` so the image crops cleanly inside its tile.
- A small zoom (`1` → `1.03` or `1.05`) usually feels better than a dramatic move.
- Grid layouts work well when you need to summarize multiple sources or show several frames from one video.
- Use consistent border radius / gaps so the layout feels intentional, not accidental.

---

## 5. Montage (Mixed Motion)

**Effect:** A stacked-image sequence where each image gets a different move (zoom in, zoom out, pan left, pan right) with crossfade transitions between shots.

### HTML

```html
<div class="scene clip s5" data-start="27" data-duration="12">
  <img id="s5-img1" src="images/montage-1.jpg" alt="Montage image 1" />
  <img id="s5-img2" src="images/montage-2.jpg" alt="Montage image 2" />
  <img id="s5-img3" src="images/montage-3.jpg" alt="Montage image 3" />
  <img id="s5-img4" src="images/montage-4.jpg" alt="Montage image 4" />
</div>
```

### CSS

```css
.s5 {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.s5 img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  opacity: 0;
  will-change: opacity, transform;
}
```

### GSAP

```html
<script>
  const tl = window.__timelines["main"];
  const sceneStart = 27;
  const shotDuration = 3;
  const fadeDuration = 0.6;

  gsap.set(['#s5-img1', '#s5-img2', '#s5-img3', '#s5-img4'], { opacity: 0 });

  tl.fromTo('#s5-img1', {
    opacity: 0,
    scale: 1
  }, {
    opacity: 1,
    scale: 1.12,
    duration: shotDuration,
    ease: 'none',
    transformOrigin: '50% 50%'
  }, sceneStart);
  tl.to('#s5-img1', {
    opacity: 0,
    duration: fadeDuration,
    ease: 'power1.inOut'
  }, sceneStart + shotDuration - fadeDuration);

  tl.fromTo('#s5-img2', {
    opacity: 0,
    scale: 1.1
  }, {
    opacity: 1,
    scale: 1,
    duration: shotDuration,
    ease: 'none',
    transformOrigin: '50% 50%'
  }, sceneStart + 2.4);
  tl.to('#s5-img2', {
    opacity: 0,
    duration: fadeDuration,
    ease: 'power1.inOut'
  }, sceneStart + 2.4 + shotDuration - fadeDuration);

  tl.fromTo('#s5-img3', {
    opacity: 0,
    x: '0%'
  }, {
    opacity: 1,
    x: '-12%',
    duration: shotDuration,
    ease: 'none'
  }, sceneStart + 4.8);
  tl.to('#s5-img3', {
    opacity: 0,
    duration: fadeDuration,
    ease: 'power1.inOut'
  }, sceneStart + 4.8 + shotDuration - fadeDuration);

  tl.fromTo('#s5-img4', {
    opacity: 0,
    x: '-12%'
  }, {
    opacity: 1,
    x: '0%',
    duration: shotDuration,
    ease: 'none'
  }, sceneStart + 7.2);
  tl.to('#s5-img4', {
    opacity: 0,
    duration: fadeDuration,
    ease: 'power1.inOut'
  }, sceneStart + 7.2 + shotDuration - fadeDuration);
</script>
```

### Usage notes / gotchas

- Montage works best when each image is visually distinct; otherwise the motion differences are hard to notice.
- Keep the motion vocabulary simple: one axis or one zoom direction per shot.
- Overlap fades slightly so the sequence feels continuous.
- If you see overlapping tween warnings on the same element/property, add `overwrite: 'auto'` to the later tween.

---

## Image Sizing Best Practices

### `object-fit: cover` vs `contain`

- **Use `object-fit: cover`** for most full-screen scenes. It fills the frame and hides aspect-ratio mismatch by cropping.
- **Use `object-fit: contain`** only when the entire image must remain visible (product shot, chart, screenshot, portrait photo with important edges).
- If you use `contain`, give the scene a deliberate background color or blurred backdrop so empty margins look intentional.

### Portrait vs landscape in horizontal / vertical video

- In **16:9 horizontal video**, landscape photos are easiest for pans and Ken Burns moves.
- Portrait photos in a horizontal frame often need `cover` cropping, side padding, or a designed background treatment.
- In **9:16 vertical video**, portrait photos usually work best as the main image; landscape images often need stronger `cover` cropping.
- For mixed source sets, normalize the composition style instead of forcing every image to behave the same way.

### Practical sizing rules

- Use images large enough to survive moderate zoom (`1.1` to `1.2`) without looking soft.
- If the image will pan, make it larger than the viewport on the travel axis.
- For screenshots or UI captures, avoid aggressive zoom unless the source resolution is high.

---

## Performance Tips

- Use reasonable source sizes: for most scenes, **cap photos at about 1920px wide** for 1080p output.
- Prefer **JPEG/WebP for photos**; use PNG only when you need transparency or sharp UI edges.
- Avoid stacking many oversized images in one scene if only one is visible at a time.
- Add `will-change: transform` or `will-change: opacity, transform` only to animated layers, not everything on the page.
- Keep moves subtle and continuous; very large transforms increase the chance of softness and visual jitter.

---

## Combining with Text

Layering text over animated images is common and works well if readability is designed in.

### Basic pattern

```html
<div class="scene clip hero" data-start="39" data-duration="6">
  <img id="hero-img" src="images/hero.jpg" alt="Background image" />
  <div class="hero-overlay"></div>
  <div class="hero-copy">
    <div class="eyebrow">Key takeaway</div>
    <h1>Animate the image, not a pre-rendered clip</h1>
    <p>GSAP motion in HTML is easier to tweak scene by scene.</p>
  </div>
</div>
```

```css
.hero {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.hero img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  z-index: 1;
}

.hero-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.28);
  z-index: 2;
}

.hero-copy {
  position: absolute;
  left: 80px;
  right: 80px;
  bottom: 80px;
  color: white;
  z-index: 3;
}
```

### Text-on-image tips

- Put the image at a lower `z-index`, then a semi-transparent overlay, then the text.
- Use a dark overlay (`rgba(0,0,0,0.2)` to `0.45`) or light overlay depending on the palette.
- Keep the text itself static or only lightly animated; the image is already providing motion.
- If the image is busy, reserve a quieter area for the copy or add a gradient overlay behind the text block.

---

## 6. Parallax (Depth Layers)

**Effect:** Foreground and background layers move at different speeds, creating a sense of depth. Works beautifully for product shots, concept illustrations, or any scene where you can separate a subject from its background.

### HTML

```html
<div class="scene clip s6" data-start="39" data-duration="8">
  <img id="s6-bg" src="images/parallax-bg.jpg" alt="Background layer" />
  <img id="s6-fg" src="images/parallax-fg.png" alt="Foreground layer" />
</div>
```

### CSS

```css
.s6 {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.s6 img {
  position: absolute;
  inset: 0;
  width: 110%;
  height: 110%;
  object-fit: cover;
  display: block;
  will-change: transform;
}

.s6 #s6-fg {
  z-index: 2;
}

.s6 #s6-bg {
  z-index: 1;
}
```

### GSAP

```html
<script>
  const tl = window.__timelines["main"];
  const sceneStart = 39;
  const sceneDuration = 8;

  // Background moves slowly
  tl.fromTo('#s6-bg', {
    x: '0%', y: '0%'
  }, {
    x: '-3%', y: '-2%',
    duration: sceneDuration,
    ease: 'none'
  }, sceneStart);

  // Foreground moves faster — creates depth illusion
  tl.fromTo('#s6-fg', {
    x: '0%', y: '0%'
  }, {
    x: '-7%', y: '-4%',
    duration: sceneDuration,
    ease: 'none'
  }, sceneStart);
</script>
```

### Usage notes / gotchas

- Foreground should ideally be a PNG with transparency (cutout subject) for the best depth effect.
- If you only have one image, you can fake parallax by duplicating it: blur one copy as the "background" and crop the subject for the "foreground".
- Both layers need to be slightly oversized (`110%`) so the movement doesn't reveal empty edges.
- Speed ratio of ~2:1 (foreground:background) feels natural.

---

## 7. Reveal / Wipe

**Effect:** An image is progressively revealed from one direction using CSS `clip-path` animation. Great for before/after comparisons or dramatic unveils.

### HTML

```html
<div class="scene clip s7" data-start="47" data-duration="6">
  <img id="s7-img" src="images/reveal.jpg" alt="Revealed image" />
</div>
```

### CSS

```css
.s7 {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.s7 img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  will-change: clip-path;
}
```

### GSAP — Left-to-right wipe

```html
<script>
  const tl = window.__timelines["main"];
  const sceneStart = 47;

  tl.fromTo('#s7-img', {
    clipPath: 'inset(0 100% 0 0)'
  }, {
    clipPath: 'inset(0 0% 0 0)',
    duration: 1.5,
    ease: 'power2.out'
  }, sceneStart);
</script>
```

### Variant — Circle reveal from center

```html
<script>
  tl.fromTo('#s7-img', {
    clipPath: 'circle(0% at 50% 50%)'
  }, {
    clipPath: 'circle(75% at 50% 50%)',
    duration: 1.2,
    ease: 'power2.out'
  }, sceneStart);
</script>
```

### Variant — Before/after comparison (two images)

```html
<div class="scene clip s7b" data-start="47" data-duration="6">
  <img id="s7b-before" src="images/before.jpg" alt="Before" />
  <img id="s7b-after" src="images/after.jpg" alt="After" />
</div>

<script>
  // After image sits on top, revealed via wipe
  gsap.set('#s7b-before', { zIndex: 1 });
  gsap.set('#s7b-after', { zIndex: 2, clipPath: 'inset(0 100% 0 0)' });

  tl.to('#s7b-after', {
    clipPath: 'inset(0 0% 0 0)',
    duration: 2,
    ease: 'power1.inOut'
  }, sceneStart + 1.5);
</script>
```

### Usage notes / gotchas

- `clip-path` animations are GPU-accelerated in modern Chromium — perfect for HyperFrames render.
- Use `inset()` for rectangular wipes, `circle()` for spotlight reveals, `polygon()` for diagonal wipes.
- Diagonal wipe: `clipPath: 'polygon(0 0, 0% 0, 0% 100%, 0 100%)'` → `'polygon(0 0, 100% 0, 100% 100%, 0 100%)'`.
- Don't animate `clip-path` on the container — animate it on the `<img>` directly.

---

## 8. Zoom to Detail

**Effect:** Start with a full view of an image, then zoom into a specific region to highlight a detail. Ideal for UI screenshots, code snippets, charts, or any image where a specific area needs emphasis.

### HTML

```html
<div class="scene clip s8" data-start="53" data-duration="6">
  <img id="s8-img" src="images/screenshot.jpg" alt="Full screenshot" />
</div>
```

### CSS

```css
.s8 {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.s8 img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  will-change: transform;
}
```

### GSAP — Zoom to top-right area (e.g., a button)

```html
<script>
  const tl = window.__timelines["main"];
  const sceneStart = 53;
  const sceneDuration = 6;

  // Show full image for 2 seconds, then zoom to detail
  tl.to('#s8-img', {
    scale: 2.5,
    transformOrigin: '75% 30%',  // point of interest coordinates
    duration: 2,
    ease: 'power2.inOut'
  }, sceneStart + 2);

  // Hold zoomed view, then optionally zoom back
  tl.to('#s8-img', {
    scale: 1,
    duration: 1.5,
    ease: 'power2.inOut'
  }, sceneStart + 4.5);
</script>
```

### Usage notes / gotchas

- `transformOrigin` is the key — it sets the zoom target. `'75% 30%'` means 75% from left, 30% from top.
- Use high-resolution source images (≥ 2x the output resolution) so the zoomed detail stays sharp.
- Hold the zoomed view long enough for the viewer to read/process the detail (at least 1.5s).
- Add a highlight overlay (circle or box) at the zoom target for extra clarity if the detail is small.
- For code screenshots: `transformOrigin: '50% 40%'` with `scale: 3` works well to focus on a specific function.

---

## 9. Vertical Pan

**Effect:** Slowly scroll down a tall image (long screenshot, webpage capture, chat log, code listing). The image is taller than the viewport and pans vertically.

### HTML

```html
<div class="scene clip s9" data-start="59" data-duration="8">
  <img id="s9-img" src="images/long-screenshot.jpg" alt="Long screenshot" />
</div>
```

### CSS

```css
.s9 {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.s9 img {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: auto;  /* natural height, taller than viewport */
  display: block;
  will-change: transform;
}
```

### GSAP

```html
<script>
  const tl = window.__timelines["main"];
  const sceneStart = 59;
  const sceneDuration = 8;

  // Calculate scroll distance based on image vs viewport ratio
  // For an image 3x the viewport height, we need to scroll ~67%
  const scrollPercent = 65;  // adjust based on actual image aspect ratio

  tl.fromTo('#s9-img', {
    y: '0%'
  }, {
    y: `-${scrollPercent}%`,
    duration: sceneDuration,
    ease: 'power1.inOut'  // slight ease for natural scroll feel
  }, sceneStart);
</script>
```

### Usage notes / gotchas

- The image must be taller than the scene viewport. Set `height: auto` (not `100%`) to preserve the natural aspect ratio.
- Calculate `scrollPercent` from the image's aspect ratio: if image height = 3× viewport height, scroll ~67%.
- Use `ease: 'power1.inOut'` for a gentle start/stop, mimicking human scrolling.
- For very long images, `ease: 'none'` (constant speed) may feel more natural.
- Consider pausing at key sections: split the scroll into 2-3 `tl.to()` calls with small gaps.

---

## 10. Split Screen

**Effect:** Two images shown side-by-side with an animated divider. Perfect for A vs B comparisons, before/after, or contrasting two concepts.

### HTML

```html
<div class="scene clip s10" data-start="67" data-duration="6">
  <div id="s10-left" class="split-half">
    <img src="images/split-left.jpg" alt="Option A" />
    <div class="split-label">Before</div>
  </div>
  <div id="s10-right" class="split-half">
    <img src="images/split-right.jpg" alt="Option B" />
    <div class="split-label">After</div>
  </div>
  <div id="s10-divider" class="split-divider"></div>
</div>
```

### CSS

```css
.s10 {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.s10 .split-half {
  position: absolute;
  top: 0;
  height: 100%;
  width: 50%;
  overflow: hidden;
}

.s10 #s10-left { left: 0; }
.s10 #s10-right { right: 0; }

.s10 .split-half img {
  width: 200%;  /* each image is full-width, clipped to half */
  height: 100%;
  object-fit: cover;
  display: block;
}

.s10 #s10-right img {
  margin-left: -100%;  /* show right half of the image */
}

.s10 .split-divider {
  position: absolute;
  top: 0;
  left: 50%;
  width: 4px;
  height: 100%;
  background: white;
  z-index: 10;
  transform: translateX(-50%);
}

.s10 .split-label {
  position: absolute;
  bottom: 60px;
  left: 50%;
  transform: translateX(-50%);
  color: white;
  font-size: 48px;
  font-weight: bold;
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.5);
  z-index: 5;
}
```

### GSAP — Animate entry

```html
<script>
  const tl = window.__timelines["main"];
  const sceneStart = 67;

  // Left half slides in from left
  tl.fromTo('#s10-left', {
    x: '-100%'
  }, {
    x: '0%',
    duration: 0.8,
    ease: 'power2.out'
  }, sceneStart);

  // Right half slides in from right
  tl.fromTo('#s10-right', {
    x: '100%'
  }, {
    x: '0%',
    duration: 0.8,
    ease: 'power2.out'
  }, sceneStart);

  // Divider fades in
  tl.fromTo('#s10-divider', {
    opacity: 0, scaleY: 0
  }, {
    opacity: 1, scaleY: 1,
    duration: 0.5,
    ease: 'power2.out'
  }, sceneStart + 0.6);
</script>
```

### Usage notes / gotchas

- If using two separate images, set each half's img to `width: 100%; object-fit: cover`.
- If using one wide image split in half, use the `width: 200%` + `margin-left: -100%` trick shown above.
- Labels help the viewer understand which side is which — add them below or above each half.
- Keep the divider line thin (2-4px) and white or a contrast color from the palette.
- For vertical split (top/bottom), swap width↔height and left↔top in the CSS.

---

## 11. Picture-in-Picture

**Effect:** A small inset window floats over the main image. Common for showing a person's avatar alongside a product shot, or quoting a source while showing its context.

### HTML

```html
<div class="scene clip s11" data-start="73" data-duration="6">
  <img id="s11-main" src="images/pip-main.jpg" alt="Main image" />
  <div id="s11-pip" class="pip-window">
    <img src="images/pip-inset.jpg" alt="Inset image" />
  </div>
</div>
```

### CSS

```css
.s11 {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.s11 #s11-main {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  z-index: 1;
}

.s11 .pip-window {
  position: absolute;
  bottom: 60px;
  right: 60px;
  width: 320px;
  height: 240px;
  border-radius: 16px;
  overflow: hidden;
  border: 3px solid rgba(255, 255, 255, 0.8);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  z-index: 5;
  will-change: transform, opacity;
}

.s11 .pip-window img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
```

### GSAP

```html
<script>
  const tl = window.__timelines["main"];
  const sceneStart = 73;
  const sceneDuration = 6;

  // Main image: subtle Ken Burns
  tl.fromTo('#s11-main', {
    scale: 1
  }, {
    scale: 1.08,
    duration: sceneDuration,
    ease: 'none',
    transformOrigin: '50% 50%'
  }, sceneStart);

  // PiP window slides in from bottom-right
  tl.fromTo('#s11-pip', {
    y: 80, opacity: 0, scale: 0.8
  }, {
    y: 0, opacity: 1, scale: 1,
    duration: 0.6,
    ease: 'back.out(1.4)'
  }, sceneStart + 0.5);
</script>
```

### Usage notes / gotchas

- PiP window should be small enough not to block key content — typically 15-25% of frame width.
- Position in a corner where the main image has less detail (bottom-right is the default).
- Add `border` and `box-shadow` to separate the inset from the background visually.
- `ease: 'back.out'` gives a satisfying "pop-in" entrance.
- For vertical video, position at top-right to avoid thumb zone.

---

## 12. Blur-to-Sharp

**Effect:** Image starts blurred (out of focus) and gradually sharpens into clarity. Creates suspense or a "loading into focus" feeling.

### HTML

```html
<div class="scene clip s12" data-start="79" data-duration="6">
  <img id="s12-img" src="images/blur-sharp.jpg" alt="Focusing image" />
</div>
```

### CSS

```css
.s12 {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.s12 img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  will-change: filter, transform;
}
```

### GSAP

```html
<script>
  const tl = window.__timelines["main"];
  const sceneStart = 79;
  const sceneDuration = 6;

  // Blur-to-sharp over first 2 seconds
  tl.fromTo('#s12-img', {
    filter: 'blur(20px)',
    scale: 1.1
  }, {
    filter: 'blur(0px)',
    scale: 1,
    duration: 2,
    ease: 'power2.out'
  }, sceneStart);
</script>
```

### Variant — Sharp then blur out (exit)

```html
<script>
  // Image starts sharp, blurs out at end of scene
  tl.to('#s12-img', {
    filter: 'blur(15px)',
    scale: 1.05,
    duration: 1.5,
    ease: 'power2.in'
  }, sceneStart + sceneDuration - 1.5);
</script>
```

### Usage notes / gotchas

- GSAP can animate CSS `filter` properties directly — `blur()`, `brightness()`, `saturate()` all work.
- Combine blur-to-sharp with a slight scale (`1.1` → `1.0`) for a cinematic "rack focus" feel.
- Heavy blur values (> 30px) on very large images may cause jank in the render — keep ≤ 20px.
- Works well as a scene entrance or exit transition, paired with other effects.

---

## 13. Scale Bounce

**Effect:** Image enters the frame with an elastic spring animation — overshoots then settles. Ideal for playful, energetic, or product-announcement style scenes.

### HTML

```html
<div class="scene clip s13" data-start="85" data-duration="6">
  <img id="s13-img" src="images/bounce-product.jpg" alt="Product shot" />
</div>
```

### CSS

```css
.s13 {
  position: absolute;
  inset: 0;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.s13 img {
  width: 80%;
  height: auto;
  object-fit: contain;
  display: block;
  will-change: transform, opacity;
  /* Drop shadow to lift product off background */
  filter: drop-shadow(0 20px 40px rgba(0, 0, 0, 0.3));
}
```

### GSAP

```html
<script>
  const tl = window.__timelines["main"];
  const sceneStart = 85;

  // Bounce in from small scale
  tl.fromTo('#s13-img', {
    scale: 0,
    opacity: 0,
    rotation: -5
  }, {
    scale: 1,
    opacity: 1,
    rotation: 0,
    duration: 0.8,
    ease: 'elastic.out(1, 0.5)'
  }, sceneStart + 0.3);
</script>
```

### Variant — Multiple items bouncing in with stagger

```html
<script>
  // For multiple product images / icons
  tl.fromTo('.s13 .bounce-item', {
    scale: 0,
    opacity: 0
  }, {
    scale: 1,
    opacity: 1,
    duration: 0.6,
    ease: 'back.out(2)',
    stagger: 0.15
  }, sceneStart + 0.3);
</script>
```

### Usage notes / gotchas

- `elastic.out(1, 0.5)` creates a spring-like bounce; adjust the second parameter (0.3-0.8) for more or less bounce.
- `back.out(2)` is a simpler overshoot without oscillation — use when elastic feels too playful.
- This effect works best with `object-fit: contain` (not `cover`) so the full image is visible.
- Add `drop-shadow` to the image for a "floating" product-shot feel.
- Good for: product announcements, logo reveals, icon/badge animations, app screenshots.
- Bad for: documentary tone, serious technical content (use Ken Burns instead).

---

## Choosing the right pattern

| Effect | Best for | Mood / Style | Image type |
|--------|----------|-------------|------------|
| **Ken Burns** | One strong image carrying a scene | Documentary, emotional, calm | Portrait photos, product shots, landscapes |
| **Pan** | Wide-frame panoramic shots | Open, unhurried | Panoramas, architecture, dashboards, timelines |
| **Slideshow Fade** | 2-4 related stills shown in progression | Smooth, narrative | Series screenshots, product iterations, team photos |
| **Grid** | Comparing multiple sources at once | Information-dense, analytical | Multiple products, multi-frame screenshots, data cards |
| **Montage** | Rapid walk-through of many examples | Fast-paced, rich | Mixed media, news roundups |
| **Parallax** | Depth and premium feel | Polished, product-grade | Subject + background layers (or PNG cutouts) |
| **Reveal/Wipe** | Suspense reveals, before/after comparisons | Dramatic, pivotal | Comparison images, product launches, data changes |
| **Zoom to Detail** | Highlighting a specific region in an image | Focused, instructional | UI screenshots, code, charts, data dashboards |
| **Vertical Pan** | Long-form content | Informational, fluid | Webpage captures, chat logs, code listings |
| **Split Screen** | A vs B comparisons | Comparative, decision-oriented | Two products, old vs new versions, competitor analysis |
| **Picture-in-Picture** | Main image + auxiliary context | Layered, rich | Product + person, quote + source |
| **Blur-to-Sharp** | Suspenseful openings, focus shifts | Cinematic, mysterious | Any image, especially scene openers |
| **Scale Bounce** | Energetic entrances, emphasis | Playful, youthful | Products, logos, icons, app screenshots |

### Combination Ideas

Effects can be combined for richer compositions:

- **Ken Burns + Blur-to-Sharp**: Scene opens blurred, focuses, then slowly zooms — cinematic intro
- **Zoom to Detail + Reveal**: Reveal full image first, then zoom to a detail — instructional content
- **Parallax + PiP**: Depth-layered background with a floating inset window — premium product showcase
- **Slideshow + Scale Bounce**: Images bounce in one-by-one instead of fading — lively product showcase
- **Split Screen + Vertical Pan**: Each half scrolls a different long screenshot — code/doc comparison

All thirteen patterns are implemented natively in the browser with GSAP, keeping them editable inside the HyperFrames composition without any FFmpeg pre-processing.
