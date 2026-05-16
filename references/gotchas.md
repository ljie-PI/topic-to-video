# Gotchas Catalog — Detailed Pitfalls

Each gotcha here was hit by an actual baseline agent. Reproductions, root causes, and fixes.

## 1. Whisper / `npx hyperframes transcribe` for Chinese

**Symptom:**
```
$ npx hyperframes transcribe narration.mp3 --language zh
◇ Downloading model small.en
◇ Transcription failed:           ← empty error
```

**Root cause:** Two problems compound:
1. Default model `small.en` is English-only, refuses non-English audio (or auto-translates).
2. The download often fails silently from this network. Retrying with `--model small` (no `.en`) downloads `ggml-small.bin` (466MB) — but then whisper.cpp's JSON output fragments multi-byte UTF-8 across token boundaries (`\xe8\xae` pieces), producing `\ufffd\ufffd` garbage in the result.

**Fix:** Use **DashScope Paraformer-realtime-v2** instead. See `scripts/transcribe-paraformer.py`. Returns clean UTF-8, sentence + word timestamps, ~1 second for a 75s audio.

**If Paraformer is also unavailable:** request the user to obtain a transcription externally (their own Whisper install, OpenAI API, or paste subtitles); HyperFrames `transcribe` accepts `.srt` / `.vtt` / `.json`.

---

## 2. Paraformer `sample_rate` mismatch

**Symptom:**
```
status_code: 44
error: Failed to decode audio: sample rate 16000 not equals with real 22050
sentence count: 0
```

**Root cause:** Paraformer rejects audio whose sample_rate doesn't match the rate declared in `Recognition()`. CosyVoice MP3 output is 22050. The default in most examples is 16000.

**Fix:** Always probe first:
```python
import subprocess
sr = int(subprocess.check_output(['ffprobe', '-v', 'error',
    '-select_streams', 'a:0', '-show_entries', 'stream=sample_rate',
    '-of', 'default=noprint_wrappers=1:nokey=1', audio_path]).strip())
```
Then pass `sample_rate=sr` to `Recognition()`. The shipped script does this.

---

## 3. Multi-worker render produces non-encodable frames

**Symptom:**
```
Conversion failed!  Try --docker for containerized rendering
[libx264] height not divisible by 2 (1920x993)
[out#0/mp4] Nothing was written into output file
```

**Root cause:** This Linux box's bundled Chromium lacks `HeadlessExperimental.beginFrame`, so HyperFrames falls back to screenshot mode. With multiple workers there's a race producing odd-height frames (1920×993 instead of 1920×1080) — x264 refuses odd heights.

**Fix:** Always render with `--workers 1`:
```bash
hyperframes render --quality high --workers 1 --output renders/final.mp4
```
Slower but reliable.

---

## 4. `[Compiler] No deterministic font mapping for: AR PL UKai CN`

**Symptom:** Render compiles but fonts revert to Chromium fallback (often Noto Sans), losing the handdrawn look.

**Root cause:** HyperFrames embeds fonts deterministically by name, only for fonts it has metadata for. System Linux fonts (`AR PL UKai CN`, `WenQuanYi Micro Hei`) are not in its registry.

**Fix:** Always download Google Fonts woff2 files into `fonts/` and reference via `@font-face`. See `scripts/fonts-download.sh`. Five fonts cover the full Chinese-handdrawn aesthetic:
- `Ma Shan Zheng` (中文标题/正文)
- `Long Cang` (中文行书 / 字幕)
- `Zhi Mang Xing` (中文写意装饰，optional)
- `Caveat` 700 (英文/数字 emphasis)
- `Patrick Hand` (英文/数字 body)

---

## 5. Caveat / PatrickHand on Chinese characters

**Symptom:** Inside `<span style="font-family: 'Caveat'">削弱</span>`, the Chinese chars render as boxes, garbled glyphs, or fall back to a different family mid-word.

**Root cause:** Caveat and PatrickHand are Latin-only. They have no CJK glyph table.

**Fix:** Switch the font for that span:
```css
.s7 .moat-card .badge {
  font-family: 'MaShanZheng', serif; /* was Caveat */
  font-weight: 400;
  font-size: 30px;
}
```

For mixed labels, split by script instead of styling the whole badge with Caveat:

```html
<div class="badge mixed-text">
  <span class="zh">削弱</span>
  <span class="latin">Moat</span>
</div>
```

```css
.badge .zh { font-family: 'MaShanZheng', serif; font-weight: 400; }
.badge .latin { font-family: 'Caveat', cursive; font-weight: 700; }
```

Before rendering a project, run:

```bash
python3 /home_ext/ljie/.copilot/skills/topic-to-video/scripts/check-cjk-fonts.py index.html
```

---

## 6. `tl.from(textContent: 0)` on element with nested `<span>`

**Symptom:** Number renders as `NaN%` for the entire scene.

**Root cause:** GSAP's textContent tween reads `el.textContent` as a string, snaps it to numeric, then writes back the rounded string. When the element contains `<span class="unit">%</span>`, `textContent` returns "100%" (with unit), and the snap parse yields NaN.

**Reproducer:**
```html
<div id="n">100<span class="unit">%</span></div>
```
```js
tl.from('#n', { textContent: 0, snap: { textContent: 1 } });  // → "NaN%"
```

**Fix:** Don't tween textContent on these. Use `scale` for emphasis:
```js
tl.from('#n', { scale: 0.5, duration: 0.55, ease: 'back.out(2)',
                transformOrigin: '50% 50%' }, 5.95);
```

If you really need a count-up with a unit, split into two siblings:
```html
<span id="n-num">100</span><span class="unit">%</span>
```
Then `tl.from('#n-num', { textContent: 0, ... })` is safe.

---

## 7. Audio clip float-precision overlap

**Symptom:**
```
✗ overlapping_clips_same_track: Track 20: clip ending at 30.773s overlaps with clip starting at 30.772s.
```

**Root cause:** Two consecutive audio clips on the same track. Their start/duration values are 3-decimal rounded (e.g. duration `7.391` rendered from `7.391625`), but the underlying float comparison sees ending=30.77294 vs starting=30.772. Lint flags any overlap.

**Fix (preferred):** Use 6-decimal precision for chained audio clips:
```html
<audio data-start="0" data-duration="7.026938" ...></audio>
<audio data-start="7.026938" data-duration="7.784438" ...></audio>
```

**Alternative:** Subtract 0.001s from each segment's duration (the shipped `scene-anchor.py` does this automatically for video scenes).

**Alternative:** Use a single concatenated `narration.mp3` and one `<audio>` element instead of per-segment files.

---

## 8. CSS selector `[data-composition-id="main"]` triggers lint

**Symptom:**
```
⚠ composition_self_attribute_selector: Selector matches the block's own id
```

**Root cause:** The root composition div has `data-composition-id="main"`, but using that as a CSS selector creates ambiguity at the framework level.

**Fix:** Always use `#root` (or the id you assigned):
```css
/* WRONG */
[data-composition-id="main"] .title { font-size: 120px; }
/* RIGHT */
#root .title { font-size: 120px; }
/* OR (most common): scope by scene class */
.s1 .title { font-size: 120px; }
```

---

## 9. `Math.ceil` for `repeat:` count

**Symptom:**
```
⚠ gsap_repeat_ceil_overshoot: Math.ceil(10.5/2)-1 = 5 → 6 cycles × 2s = 12s, exceeds 10.5s
```

**Root cause:** `ceil` rounds up, causing the last cycle to extend past the composition end.

**Fix:** Use `Math.floor`:
```js
// Animate doodle drift over the full 76.6s composition with 14s cycles:
tl.to('#doodle', { rotation: 8, duration: 14, ease: 'sine.inOut',
  yoyo: true, repeat: Math.floor(76.6 / 28) - 1 }, 0);
//             not Math.ceil ^^^^^^^^
```

---

## 10. `overlapping_gsap_tweens` on consecutive same-property tweens

**Symptom:**
```
⚠ overlapping_gsap_tweens: GSAP tweens overlap on "#page-wipe" for scaleX between 0.00s and 0.28s.
```

**Root cause:** Two tweens animating the same property on the same element with overlapping time windows.

**Fix:** Add `overwrite: 'auto'` to the later tween:
```js
tl.to('#s4-ring', { rotation: 360, duration: 12, ease: 'none',
  transformOrigin: '50% 50%', overwrite: 'auto' }, 25.0);
```

---

## 11. `GSAP target #X not found` for shared selectors

**Symptom:** Console warnings like `GSAP target #scene-02 .subcopy not found` for some scenes that don't have a `.subcopy` element.

**Root cause:** A generic loop animates `.headline`, `.subcopy`, `.card` for every scene, but not every scene has all three.

**Fix:** Filter empty selectors:
```js
function enter(sel, fromVars, at) {
  const targets = gsap.utils.toArray(sel);
  if (targets.length === 0) return;
  tl.from(targets, fromVars, at);
}
enter('#s2 .subcopy', { opacity: 0, y: 20, duration: 0.5 }, 5.0);
```

---

## 12. Inline `<span class="highlight">` overflows for Chinese

**Symptom:**
```
✗ text_box_overflow span.highlight inside span.highlight overflowed top 3.79px "AI训练"
```

**Root cause:** Highlight pills with tight padding/line-height assume Latin x-height. Chinese characters at 100px+ overshoot the inline-block.

**Fix:**
```css
.highlight {
  padding: 4px 16px 12px;     /* extra bottom for descenders */
  line-height: 1.15;          /* not 1.0 or 1.05 */
  border-radius: 10px;
}
```

---

## 13. `#9893a5` body text fails WCAG AA

**Symptom:**
```
⚠ WCAG AA contrast warnings:
  · div.caption-note "..." — 2.73:1
```

**Root cause:** `--subtle #9893a5` is the lightest text color in the palette — too faint on cream background for body copy.

**Fix:** Reserve `--subtle` for genuinely decorative text only (corner marks, scene numbers). Body copy must use `--muted #797593` (3.6:1) or `--text #575279` (5.8:1).

---

## 14. `npx hyperframes` first run hangs on Linux box

**Symptom:** `npx hyperframes --version` runs for 3+ minutes with no output.

**Root cause:** First-time npx fetches `hyperframes` + `onnxruntime-node`. The latter's postinstall script tries to download a build manifest which 302-redirects in a way the install script doesn't handle, hanging.

**Fix:** Install once with `--ignore-scripts`:
```bash
npm install --no-save --ignore-scripts hyperframes
# Then use the local binary:
./node_modules/.bin/hyperframes <command>
```

---

## 15. `python` vs `python3`

**Symptom:** `bash: python: command not found`

**Fix:** Always use `python3` in commands and shell scripts. The venv's `bin/activate` does symlink `python → python3`, but only inside the activated venv.

---

## 16. `networkidle0` hangs in Puppeteer screenshots

**Symptom:** `TimeoutError: Waiting failed: 30000ms exceeded` when trying to grab a frame via puppeteer.

**Root cause:** `file://`-loaded `<audio>` and `<video>` elements raise `net::ERR_ABORTED` events that `networkidle0` keeps waiting on forever.

**Fix:** Use `domcontentloaded` + explicit wait for `window.__timelines.main`:
```js
await page.goto(fileUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.waitForFunction(() => Boolean(window.__timelines && window.__timelines.main));
await page.evaluate((t) => {
  const tl = window.__timelines.main;
  tl.pause(0);
  tl.time(t, false);
}, atSeconds);
await page.screenshot({ path: out, clip: { x: 0, y: 0, width: 1920, height: 1080 } });
```

(Usually unnecessary — just use `hyperframes render --quality draft --workers 1` instead.)

## 17. Paraformer normalizes English to lowercase

**Symptom:** Your scene anchor "Hugging" or "PyTorch" doesn't match in transcript even though you can hear those words in the audio.

**Root cause:** Paraformer's Chinese ASR pipeline lowercases all English words and may drop spaces. So `Hugging Face` becomes `hugging face`, `PyTorch` becomes `pytorch`.

**Fix:** Shipped `scripts/scene-anchor.py` does case-insensitive matching (since GREEN-phase update). If you wrote your own anchor logic, lowercase both sides before `.find()`. Prefer Chinese anchors when possible — they're transcribed verbatim.

```python
# Audio says "Hugging Face 的 candle"
# Paraformer returns: "hugging face的candle"
joined.find('Hugging')                  # → -1 (fails)
joined.lower().find('Hugging'.lower())  # → matches
```

---

## 18. Punchline / summary elements containing Chinese must explicitly use a CJK font

**Symptom:** The summary line at the end of a scene, such as a one-sentence punchline or closing summary, uses a visibly different font from nearby content and often overlaps the grid or cards above it.

**Root cause:** When designing the punchline, it is easy to reuse the `.eyebrow` / `.brand` Caveat or PatrickHand styling, which is Latin-only. If an element containing Chinese declares Caveat, CJK characters fall back to Chromium's system font, changing line height, weight, and visual style:
- The font appearance changes abruptly and breaks the unified handwritten look.
- System Chinese fonts have a taller line box than Caveat, often overflowing the bottom boundary and overlapping content above.

**Reproducer:**
```css
/* WRONG */
.scene .conclude {
  font-family: 'Caveat', cursive;
  font-size: 78px;
  bottom: 130px;
}
```
```html
<div class="conclude">某句中文总结。</div>   <!-- CJK fallback -->
```

**Fix:** For any element that contains CJK summary or punchline text, explicitly set a Chinese font and leave enough room for CJK glyph width:
```css
/* RIGHT */
.scene .conclude {
  font-family: 'MaShanZheng', serif;   /* explicit CJK family */
  font-size: 56px;                      /* CJK is ~1.4x wider than Latin; reduce by about one third */
  bottom: 70px;                         /* leave more room to avoid overlapping the grid */
}
```

**Tooling caveat:** `check-cjk-fonts.py` can produce many false positives from ancestor selectors such as `.scene`, `.eyebrow`, `.brand`, and `.corner-mark`, so the real punchline-frame problem can be hidden by noise. **Manually inspect final rendered scene frames that contain punchlines.**

---

## 19. Embedded video clips bleed their source audio into the final mp4

**Symptom:** The final `final_with_bgm.mp4` plays the narration but you can also hear the original speaker / music / sound effects from one of the embedded `<video class="clip">` elements — usually only during the scene where that clip is on screen.

**Root cause:** A scene's `selected_clips[clip_index]` was cut with `ffmpeg -ss <start> -to <end> -c copy` (or `-c copy -c:a copy`) and the resulting mp4 still carries the source audio track. The HTML embeds it as `<video class="clip" muted>`. The `muted` attribute only suppresses *playback through the WebAudio output*; it does not strip the audio track from the file. During `hyperframes render` Chromium hands the page off to ffmpeg, which under some pipelines (especially when narration is mixed in via a separate `<audio>` element) picks up the clip's audio track anyway. Result: clip voice or music underneath the narration, lower and offset by the GSAP scene start.

**Fix:** Strip the audio track at cut time — `muted` on the tag is belt-and-suspenders, not the primary defense:
```bash
# WRONG — keeps source audio
ffmpeg -y -ss 12.0 -to 18.5 -i source.mp4 -c copy clip.mp4

# RIGHT — audio track removed entirely
ffmpeg -y -ss 12.0 -to 18.5 -i source.mp4 -c:v copy -an clip.mp4
```

Then embed with `<video class="clip" muted playsinline>` so that even if a clip slipped through without `-an`, the browser still silences it for the renderer.

**Verification:** `ffprobe -v error -show_streams <clip.mp4>` should list only `codec_type=video` — no `codec_type=audio` line. If you see an audio stream on any embedded clip, re-cut it.
