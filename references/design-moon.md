# Style Hint — Rosé Pine Moon × Serious Technical Editorial

> Optional dark mood and palette hint for `topic-to-video`. This is not a
> HyperFrames implementation spec. The Phase 8 sub-agent uses the `hyperframes`
> skill and project `DESIGN.md` process for actual CSS, layout, animation, and
> rendering decisions.
> The companion handdrawn reference is `references/design-dawn.md`.

## Palette (use ONLY these colors)

**Backgrounds**
- Main canvas: `#232136` (Moon base)
- Card surface: `#2a273f` (Moon surface)
- Elevated overlay: `#393552` (Moon overlay)

**Text**
- Primary / headlines: `#e0def4` (Moon text)
- Secondary / body: `#908caa` (Moon subtle; safe on base for medium/large text)
- Decorative muted only: `#6e6a86` (Moon muted; not for body copy)

**Accents — pick ONE per scene**
- Iris `#c4a7e7` — primary technical highlight, labels, emphasis
- Foam `#9ccfd8` — neutral data callouts, comparison markers
- Gold `#f6c177` — one important number or warning per scene
- Love `#eb6f92` — risk, failure, tension, urgent callouts
- Rose `#ea9a97` — human/soft contrast, rare CTA
- Pine `#3e8fb0` — deep blue support accent; use on large text or shapes only

**Borders / Dividers**
- Standard line: `#56526e`
- Subtle divider: `#44415a`
- Low highlight / inset: `#2a283e`

## Typography

| Use | Font | Weight | Notes |
|---|---|---|---|
| Chinese headlines | `NotoSerifSC` | 700 | Serious editorial tone; use for main claims |
| Chinese section titles | `NotoSerifSC` | 600 | Use when 700 feels too heavy |
| Chinese body | `NotoSansSC` | 400 | Clear, modern, less playful than Dawn |
| Chinese captions / subtitles | `NotoSansSC` | 500 | Slightly stronger for video readability |
| English / data / code | `IBMPlexMono` | 400 | Technical labels, filenames, model names |
| English / numeric emphasis | `IBMPlexMono` | 600 | Numbers, versions, command snippets |

**Do not use Dawn handwriting fonts in Moon** unless the user explicitly asks for a handdrawn contrast. Moon should feel restrained, technical, and editorial.

The main agent pre-stages Moon fonts with `scripts/fonts-download.sh`. The
HyperFrames sub-agent decides how to load and apply those local font assets.

## Video Sizes

| Element | 1920×1080 | 1080×1440 | 1080×1920 |
|---|---|---|---|
| Hero headline | 88-136px | 72-116px | 76-124px |
| Section headline | 54-82px | 46-70px | 50-76px |
| Body text | 30-48px | 28-42px | 28-44px |
| Data labels | 22-32px | 22-30px | 22-32px |
| Code / monospace | 22-34px | 22-30px | 22-32px |
| Padding (.scene) | 90px 140px | 90px 80px | 90px 70px |

## Shape Mood

- Compact flat panels and serious editorial data blocks.
- Highlights should read as lines, tags, or small marks rather than large bright fills.
- Avoid heavy shadow and playful ornament.

## Motion

- Entrances should be restrained: `power3.out`, `expo.out`, `sine.out`.
- Use smaller movement than Dawn: `y: 20-44`, `x: 20-40`, `scale: 0.96-1`.
- Avoid bouncy `back.out(1.7)` unless the content needs a rare moment of emphasis.
- No full-screen linear gradients on dark backgrounds. Use solid backgrounds plus localized radial accents at 15-25% opacity.
- Keep ambient decoration subtle: grids, hairlines, small orbital marks, terminal-like cursors, or diagram nodes.

## Don'ts

- Do not replace Dawn's handdrawn default; Moon is optional.
- Do not use `MaShanZheng`, `LongCang`, `Caveat`, or `PatrickHand` for Moon unless the user explicitly asks for mixed handdrawn contrast.
- Do not use `#6e6a86` for normal body text.
- Do not use full-screen linear gradients on dark backgrounds.
- Do not combine more than one accent color in a single scene's main content.
- Do not make large accent-color backgrounds; use accent as line, tag, number, or small symbol.
