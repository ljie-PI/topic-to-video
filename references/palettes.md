# 备选配色

默认是 **Rosé Pine Dawn**（温暖、明亮、手绘）。用户想换风格时有以下备选。

## Rosé Pine Dawn（默认 —— 见 `references/design-dawn.md`）

Mood：温暖、平静、亲密。搭配手绘字体。

## Rosé Pine Moon Serious（可选 —— 见 `references/design-moon.md`）

Mood：严肃、克制、深色、编辑感。**仅在用户明确要求 "moon"、"严肃"、"深色" 或深色编辑风格时使用**；AI / SaaS / 编程 / 技术讲解 等技术主题请改用 Tech 或 GitHub 预设，不由 Moon 自动匹配。

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

字体：`NotoSansSC` 用于中文标题、正文与字幕 + `IBMPlexMono` 用于英文、数据与代码。

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

## News（新闻洞察 —— 见 `references/design-news.md`）

Mood：可信、克制、编辑感。白底 + 品牌紫强调。适合新闻解读、时事分析、热点复盘、深度报道、媒体洞察、行业动态。配色提取自 Kraken DESIGN.md。

```
--bg:        #ffffff
--surface:   #f5f5f8
--band:      #f1ecfe   /* 紫色 subtle band / eyebrow */
--text:      #101114
--muted:     #686b82
--subtle:    #9497a9
--line:      #dedee5

--accent-1:  #7132f5   /* 品牌紫 — brand / link / marker（小字文字用 #5741d8） */
--accent-2:  #149e61   /* 绿 — 利好 / 正向（文字 #026b3f） */
--accent-3:  #e5484d   /* 红（派生）— 利空 / 风险（文字 #c81e1e） */
--accent-4:  #e3a008   /* 琥珀（派生）— 存疑 / 注意（文字 #8a5a00） */
```

字体：`NotoSansSC`（中文标题 / 正文 / 字幕） + `IBMPlexMono`（数字 / 数据 / 来源），复用 Moon 字体；可选拉丁品牌 `IBM Plex Sans`。

## Tech（技术讲解 —— 见 `references/design-tech.md`）

Mood：终端原生、纯等宽、manpage 感、极简。暖奶油底 + 唯一深色 TUI mockup。适合技术讲解、CLI / 终端工具、开发者内容、源码 · 命令行原理、工程拆解。配色提取自 opencode.ai DESIGN.md。区别于 Moon（深色 rose-pine）与 GitHub（浅色品牌克制）。

```
--bg:        #fdfcfc
--surface:   #f8f7f7
--card:      #f1eeee
--dark:      #201d1d   /* 深色 TUI surface / 代码块 */
--text:      #201d1d
--body:      #424245
--muted:     #646262
--line:      rgba(15,0,0,0.12)

--accent-1:  #007aff   /* 蓝 — info / link / 命令（文字 #0056b3） */
--accent-2:  #30d158   /* 绿 — 通过 / verified（文字派生 #147a3c） */
--accent-3:  #ff3b30   /* 红 — error / 失败（文字 #d70015） */
--accent-4:  #ff9f0a   /* 琥珀 — 注意 / caution（文字 #995f06） */
```

字体：`NotoSansSC`（中文；等宽字体无中文字形，故中文回退到非等宽的 `NotoSansSC`） + `IBMPlexMono`（拉丁 / 代码 / 数据 / ASCII marker），复用 Moon 字体。

## 如何选择

| 用户说 | 选 |
|--------|----|
| "rose pine dawn"、"dawn"、"笔记本"、"小红书"、"温暖"、"手绘"、"ins 风" | Rosé Pine Dawn |
| "rose pine moon"、"moon"、"严肃"、"深色"、"深色编辑" | Rosé Pine Moon Serious |
| "新闻"、"时事"、"热点"、"深度报道"、"洞察"、"媒体"、"行业动态" | News |
| "技术讲解"、"CLI"、"终端"、"命令行"、"开发者"、"源码"、"manpage"、"极简技术" | Tech |
| "杂志"、"编辑"、"复古"、"质感" | Warm Editorial |
| "科技"、"未来"、"premium"、"币圈"、"暗黑" 但不是 "moon" | 反问：Rosé Pine Moon Serious 还是 Dark Premium |
| 没说风格，主题是哲学 / 人文 / 生活 | Rosé Pine Dawn |
| 没说风格，主题是 AI/SaaS/编程 / 技术讲解 | 反问：Tech 终端·manpage 还是 GitHub 品牌克制 |
| 完全没风格指向 | Rosé Pine Dawn |

## 按画幅决定 padding

| Orientation | Scene padding | Hero 字号 |
|-------------|---------------|----------|
| 1920×1080 | 90px 140px | 100-160px |
| 1080×1440 | 90px 80px | 80-130px |
| 1080×1920 | 90px 70px | 90-140px |
| 1080×1080（方形） | 90px 100px | 80-120px |
