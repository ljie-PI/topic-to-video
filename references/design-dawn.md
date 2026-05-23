# Style Hint — Rosé Pine Dawn × Notion Handdrawn

> Optional mood and palette hint for `topic-to-video`. This is not a
> HyperFrames implementation spec. The Phase 8 sub-agent uses the `hyperframes`
> skill and project `DESIGN.md` process for actual CSS, layout, animation, and
> rendering decisions.

## Palette (use ONLY these colors)

**Backgrounds**
- Main canvas: `#faf4ed` (warm cream)
- Card surface: `#fffaf3` (near-white warmth)
- Elevated overlay: `#f2e9e1` (soft peach-beige)

**Text**
- Primary / headlines: `#575279` (soft violet-gray)
- Secondary / body: `#797593` (muted lavender)
- Subtle / decorative only: `#9893a5` (NOT for body — fails WCAG 4.5:1)

**Accents — pick ONE per scene**
- Foam `#56949f` (saltwater teal) — info blocks, neutral tags
- Love `#b4637a` (muted rose) — warm accents, warnings, "fade" badges
- Iris `#907aa9` (grounded purple) — secondary links, hints, Loop motifs
- Gold `#ea9d34` (amber) — emphasis highlights (use sparingly, max 1 element)
- Rose `#d7827e` (soft coral) — gentle callouts, "now" markers
- Pine `#286983` (deep teal) — keywords, cool contrast, "solid" badges

**Borders / Dividers**: `#cecacd` (warm gray)

## Typography

| Use | Font | Weight | Notes |
|---|---|---|---|
| Chinese headlines | `MaShanZheng` | 400 | Bold-feeling brush style |
| Chinese body | `MaShanZheng` | 400 | Same family, just smaller |
| Chinese captions / 字幕 | `LongCang` | 400 | Cursive script |
| Chinese accent decoration | `ZhiMangXing` | 400 | Optional |
| English/numbers — emphasis | `Caveat` | 700 | Handwriting marker |
| English/numbers — body | `PatrickHand` | 400 | Casual handwriting |

**NEVER use Caveat or PatrickHand for Chinese characters** — they have no CJK glyphs, browser falls back to garbled rendering.

For mixed Chinese + Latin text, the HyperFrames sub-agent should use the
project fonts deliberately. This file names the desired families only; it does
not prescribe CSS implementation.

## Video Sizes (these override web sizes)

| Element | 1920×1080 | 1080×1440 | 1080×1920 |
|---|---|---|---|
| Hero headline | 100-160px | 80-130px | 90-140px |
| Section headline | 60-90px | 50-76px | 56-80px |
| Body text | 32-56px | 28-46px | 30-48px |
| Data labels | 22-32px | 22-30px | 22-32px |
| Padding (.scene) | 90px 140px | 90px 80px | 90px 70px |

## Shape Mood

- Flat, tactile cards and tags.
- Rounded labels are acceptable when they serve the information design.
- Avoid heavy shadows; keep the handdrawn mood light and quiet.

## Motion Mood

- Every decorative element: ambient breathe / drift / rotate (sine.inOut yoyo, finite repeat)
- Every entrance: 3+ different eases per scene (mix `expo.out`, `back.out(1.7)`, `power3.out`, `sine.out`)
- NO exit animations except final scene
- Scene transition handled implicitly by hyperframes track switch
- Headlines enter first, supporting elements stagger after

## Don'ts

- ❌ Never use shadows, gradients, glow, neon
- ❌ Never use saturated colors outside this palette
- ❌ Never use `#9893a5` for body text (contrast)
- ❌ Never use Latin handwriting fonts for Chinese
- ❌ Never combine multiple accent colors on one element
- ❌ Never use accent colors as large background fills
