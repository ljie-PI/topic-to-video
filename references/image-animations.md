# Image Animations Reference — HyperFrames + GSAP

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

## Choosing the right pattern

- **Ken Burns:** one strong image, emotional or documentary tone.
- **Pan:** wide scene, landscape photo, architecture, screenshots of dashboards or timelines.
- **Slideshow Fade:** 2-4 related stills, visual progression without hard cuts.
- **Grid Layout:** compare multiple sources at once.
- **Montage:** fastest-paced option; best when the narration is moving through several examples in quick succession.

These five patterns cover most of the FFmpeg-style still-image motions from TuberUp's `imageToVideo.ts`, but implemented natively in the browser with GSAP so they stay editable inside the HyperFrames composition.
