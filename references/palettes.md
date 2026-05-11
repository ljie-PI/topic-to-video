# Alternative Palettes

Default is **Rosé Pine Dawn** (warm, light, handdrawn). Alternates are available when the user wants something different.

## Rosé Pine Dawn (Default — see `references/design-dawn.md`)

Mood: warm, calm, intimate. Pairs with handdrawn fonts.

## Rosé Pine Moon Serious (Optional — see `references/design-moon.md`)

Mood: serious, technical, restrained, editorial. Use for AI, SaaS, programming, business analysis, technical commentary, and any user request for "moon", "严肃", "深色", or "技术感".

```
--bg:        #232136
--surface:   #2a273f
--overlay:   #393552
--text:      #e0def4
--muted:     #908caa
--subtle:    #6e6a86
--line:      #56526e

--foam:      #9ccfd8
--love:      #eb6f92
--iris:      #c4a7e7
--gold:      #f6c177
--rose:      #ea9a97
--pine:      #3e8fb0
```

Fonts: `NotoSerifSC` for Chinese headlines + `NotoSansSC` for Chinese body/captions + `IBMPlexMono` for English, data, and code.

⚠️ Moon is not handdrawn. Do not use `MaShanZheng`, `LongCang`, `Caveat`, or `PatrickHand` unless the user explicitly asks to blend handdrawn elements into the Moon style.

⚠️ Dark backgrounds increase apparent font weight. Keep body at 400/500, use 700 mainly for headlines, and run HyperFrames contrast validation on rendered frames.

## Warm Editorial

Mood: magazine spread, refined, journalistic. Pairs with serif + clean sans.

```
--bg:        #f6f1e7
--surface:   #fffefb
--overlay:   #ece4d2
--text:      #2c2826
--muted:     #6b5f57
--subtle:    #aaa092
--line:      #c9bfae

--accent-1:  #c8521c   /* terracotta — hero accent */
--accent-2:  #4a6741   /* moss — secondary */
--accent-3:  #8a5a44   /* cocoa — tertiary */
--accent-4:  #d6a634   /* mustard — emphasis */
```

Fonts: `EB Garamond` or `Crimson Pro` (serif headlines) + `Inter` or `IBM Plex Sans` (body) + `JetBrains Mono` (data).

⚠️ Even in this palette, **don't pair two sans-serifs**. Serif + sans + mono is the safe trio.

## Dark Premium

Mood: tech, deep, premium. Pairs with geometric sans.

```
--bg:        #0a0e1a
--surface:   #131826
--overlay:   #1c2237
--text:      #e8ecf4
--muted:     #9aa3b8
--subtle:    #5e6884
--line:      #2a3147

--accent-1:  #6366f1   /* indigo — hero */
--accent-2:  #06b6d4   /* cyan — secondary */
--accent-3:  #f59e0b   /* amber — emphasis */
--accent-4:  #ec4899   /* pink — rare CTA */
```

Fonts: `Space Grotesk` or `Manrope` (headlines) + `Inter` (body) + `JetBrains Mono` (code).

⚠️ Dark backgrounds increase apparent font weight — drop body weight by 50 (e.g. 350 instead of 400). Add subtle radial glow under accents (~15-25% opacity, never 5%).

⚠️ No full-screen linear gradients on dark — H.264 banding. Use radial or solid + localized glow.

## How to Pick

| User says | Pick |
|---|---|
| "rose pine dawn", "dawn", "笔记本", "小红书", "温暖", "手绘", "ins 风" | Rosé Pine Dawn |
| "rose pine moon", "moon", "严肃", "深色", "技术感", "技术评论", "AI", "SaaS", "编程" | Rosé Pine Moon Serious |
| "杂志"、"编辑"、"复古"、"质感" | Warm Editorial |
| "科技", "未来", "premium", "币圈", "暗黑" but not "moon" | Ask: Rosé Pine Moon Serious or Dark Premium |
| No style, and topic is philosophy/humanities/life | Rosé Pine Dawn |
| No style, and topic is AI/SaaS/programming | Ask: Rosé Pine Dawn for warm explainer, or Rosé Pine Moon Serious for technical editorial |
| No style at all | Rosé Pine Dawn |

## Dimension-Aware Padding

| Orientation | Scene padding | Hero size |
|---|---|---|
| 1920×1080 | 90px 140px | 100-160px |
| 1080×1440 | 90px 80px | 80-130px |
| 1080×1920 | 90px 70px | 90-140px |
| 1080×1080 (square) | 90px 100px | 80-120px |
