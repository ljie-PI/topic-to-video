# 备选配色

默认是 **Rosé Pine Dawn**（温暖、明亮、手绘）。用户想换风格时有以下备选。

## Rosé Pine Dawn（默认 —— 见 `references/design-dawn.md`）

Mood：温暖、平静、亲密。搭配手绘字体。

## Rosé Pine Moon Serious（可选 —— 见 `references/design-moon.md`）

Mood：严肃、技术、克制、编辑感。适合 AI、SaaS、编程、商业分析、技术评论，以及用户要求 "moon"、"严肃"、"深色" 或 "技术感" 的场景。

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

字体：`NotoSerifSC` 用于中文标题 + `NotoSansSC` 用于中文正文 / 字幕 + `IBMPlexMono` 用于英文、数据与代码。

⚠️ Moon 不是手绘风。除非用户明确要求把手绘元素融进 Moon 风格，否则不要使用 `MaShanZheng`、`LongCang`、`Caveat` 或 `PatrickHand`。

⚠️ 深色背景会让字体看起来更粗。正文保持 400/500，700 主要用于标题，并对渲染出的帧跑 HyperFrames 的对比度校验。

## Warm Editorial

Mood：杂志跨页、精致、新闻感。搭配 serif + 干净 sans。

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

字体：`EB Garamond` 或 `Crimson Pro`（serif 标题） + `Inter` 或 `IBM Plex Sans`（正文） + `JetBrains Mono`（数据）。

⚠️ 即便是这个配色，**也不要搭配两种 sans-serif**。serif + sans + mono 是安全的三件套。

## Dark Premium

Mood：科技、深邃、高级。搭配几何感 sans。

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

字体：`Space Grotesk` 或 `Manrope`（标题） + `Inter`（正文） + `JetBrains Mono`（代码）。

⚠️ 深色背景会让字体看起来更粗 —— 正文字重降 50（例如用 350 而不是 400）。在 accent 之下加一层细微的 radial glow（透明度 ~15-25%，永远不要 5%）。

⚠️ 深色背景上不要用满屏 linear gradient —— H.264 会出现 banding。改用 radial 或 纯色 + 局部 glow。

## 如何选择

| 用户说 | 选 |
|--------|----|
| "rose pine dawn"、"dawn"、"笔记本"、"小红书"、"温暖"、"手绘"、"ins 风" | Rosé Pine Dawn |
| "rose pine moon"、"moon"、"严肃"、"深色"、"技术感"、"技术评论"、"AI"、"SaaS"、"编程" | Rosé Pine Moon Serious |
| "杂志"、"编辑"、"复古"、"质感" | Warm Editorial |
| "科技"、"未来"、"premium"、"币圈"、"暗黑" 但不是 "moon" | 反问：Rosé Pine Moon Serious 还是 Dark Premium |
| 没说风格，主题是哲学 / 人文 / 生活 | Rosé Pine Dawn |
| 没说风格，主题是 AI/SaaS/编程 | 反问：Dawn 温暖讲解 还是 Moon 严肃技术编辑 |
| 完全没风格指向 | Rosé Pine Dawn |

## 按画幅决定 padding

| Orientation | Scene padding | Hero 字号 |
|-------------|---------------|----------|
| 1920×1080 | 90px 140px | 100-160px |
| 1080×1440 | 90px 80px | 80-130px |
| 1080×1920 | 90px 70px | 90-140px |
| 1080×1080（方形） | 90px 100px | 80-120px |
