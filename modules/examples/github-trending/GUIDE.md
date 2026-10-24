# 示例：GitHub 本周热榜（0–27.2 秒）

一个完整的 HyperFrames 工程，按 `templates/github/GUIDE.md` 的组装方法拼成（路径相对 `modules/` 目录）。可以整个复制出去，作为新视频的起点。

| 来源 | 在这个工程里的样子 |
|---|---|
| 设计主题 `designs/github/github.md` | `index.html` 的第一段 `:root` 变量、字体 CSS 引用、纸纹背景；`assets/fonts/`、`assets/textures/` |
| 布局 `layouts/presenter.md` | 所有挂载点的位置和层级 |
| 组件 `components/` | `compositions/nav-bar.html`、`caption-bar.html`、`tile-wipe.html`、`jay.html`；`assets/jay/` |
| 模板 `github` | 第二段 `:root`（贡献图配色）、`assets/brand/`、`compositions/trending-overview.html` 和 `project-cover.html` |

| 时间（秒） | 画面 |
|---|---|
| 0–20.7 | 榜单总览：5 个项目逐个高亮，星标变成实心；README 截图切换并滚动；Jay 开场挥手，讲到项目时抬头看榜单，再看 README |
| 20.25–21.7 | 方格转场（贡献图绿色），盖住时亮出“#1 storytold / artcraft”卡片；导航下划线移到 #1；Jay 在转场前打字 |
| 20.7–27.2 | 第 1 名封面：名字、介绍、+20,267 数字滚动、Rust、Star → Starred；Jay 在 25 秒做惊喜动作 |
| 全程 | 顶部导航条；底部字幕条；Jay 跟着配音动嘴 |

## 文件

- `index.html`：主题变量、模板覆盖、背景，以及 6 个挂载点。
- `data/narration.json`：旁白逐句时间轴（字幕和动作时间的来源）。
- `assets/audio/narration.m4a`：前 27.2 秒的配音。只用来生成嘴型，不在画面里播放。
- `data/video-data.js`：`window.VIDEO`（标签、字幕、转场卡片、榜单、Jay 剧本和嘴型），由下面的脚本生成，不要手改。
- `tools/build-data.mjs`：从 `data/narration.json` 和配音生成 `data/video-data.js`。写完会读回比对，保证数据没有被格式化弄坏。
- `compositions/`：从 skill 的 `components/` 和 `templates/github/` 原样复制。
- `assets/`：
  - 主题资源：`textures/`；`fonts/` 由下载脚本生成，不进仓库；
  - 模板资源：`brand/`；
  - 组件资源：`jay/`；
  - 素材：`readme/`、`logos/`、`audio/`。

README 截图是占位的单帧，比面板高不了多少，所以滚动幅度很小。换成完整的长截图后会正常滚动。

## 运行

```
bash ../../../scripts/fonts-download.sh assets/fonts github   # 下载主题字体（skill 根目录的脚本），只需一次
node tools/build-data.mjs                       # 重新生成数据；复制到别处后用 MAKE_ENVELOPE=<skill>/modules/scripts/make-envelope.mjs 指定嘴型工具
export HYPERFRAMES_BROWSER_PATH="<本机 Chrome 路径>"   # 只在 HyperFrames 自带的浏览器无法启动时需要
npx hyperframes check
npx hyperframes preview
```
