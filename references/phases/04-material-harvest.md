# Phase 4 — 素材抓取（可选；`inputs.json` 的 `fetch_materials = false` 时跳过）

## 输入

- `research-brief.md` 的 **Source URLs** 一节（研究阶段已按可抓取页面类型预筛）；
- 用户提供的 URL；
- `gemini_deep_research_sources.json`（存在时）；
- `inputs.json` 的 `material_search_requests`（可选）。

## 输出

- `harvest_page/manifest.json`（v2，`entries` 与 `harvest_batches` 非空；`images[]` / `videos[]` 是筛选后的清单，见 Phase 4.c）；
- `harvest_page/<url-slug>/` 目录（每个 URL 一个，含 `metadata.json`）；
- YouTube/Bilibili 条目带 `pending_downloads[]`，`video-download.py --harvest-dir` 会在下载成功后直接更新 manifest；
- 论文 entry 已由 Phase 2 / Phase 3 写入同一份 manifest，后续 harvest 不会覆盖它。

## 完成判据

- `pipeline-status` 校验 `harvest_page/manifest.json` 存在、非空、JSON 可解析，且 `entries` 与 `harvest_batches` 为非空列表（只有论文 entry 不算完成 web harvest）。它**不**检查下载是否尝试过。
- 执行者核对：`pending_downloads[]` 已逐项顺序尝试（失败项保留 `download_required: true`），并按 Phase 4.c 剔除尺寸不够 / 看不清的素材。

## 执行后自检

`pipeline-status` 仅检查 manifest 结构，执行者须核对：

- 页面与主题相关（明显偏题来源剔除并记录原因）；图片清晰可用（缩略图、水印、占位图不算），视频有实质内容而非错误页；HTTP 200 的登录墙、验证码页、付费墙不得当作可用素材。
- `material_search_requests` 已逐条在目标平台执行并如实记录结果（禁拿普通网页搜索冒充指定平台搜索）。
- 受限来源（需登录 / 地区限制 / 反机器人验证）已记入 `search-notes.md`，供最终交付时说明；下载失败项保留 `download_required: true`，禁伪造下载。
- 已完成 Phase 4.c 的像素尺寸与清晰度筛选，并将剔除结果写回 `harvest_page/manifest.json`（不只停留在对话或笔记中）。

素材不足或偏题时在搜索上限内补搜一次；仍不够则接受较少 B-roll 或请用户提供素材，不拿低质素材凑数。

## 下一步

进入 Phase 5（素材 catalog）。若 `fetch_materials = false` 则本阶段跳过：标准模式连同 Phase 5 跳过直进 Phase 6（无素材路径），论文模式进 Phase 5（仅论文素材）。

## 护栏

- **Chrome over CDP。** 显式传 `--profile-dir {work_dir}/chrome_profile`（CDP 复用参数与端口冲突处理同 Phase 3）。
- **登录态仅靠继承，不中断流程求登录。** 采集自动继承共享 profile 的 cookies 及已开同站标签页的 localStorage；受限时记入 `search-notes.md` 继续执行，禁向用户索取或保存密码 / cookie。
- **视频下载必须顺序执行**，防 `yt-dlp` 并行限速。
- **抓取返回 0 张图时先排查加载**：调大 `--page-load-timeout`；仍为 0 则在共享 profile 中处理 cookie banner / 等待懒加载后重跑。

---

### Phase 4.a — 选择 URL 并批量抓取页面

汇总高价值视觉页面写入 `harvest-urls.txt`，单次调用 `harvest-pages.py`：普通页提取图片 / 原生视频并默认录制滚动视频；YouTube / Bilibili 直链列入 `pending_downloads[]` 交由 Phase 4.b 下载。

#### URL 选择规则（用来生成 URL 清单）

质量优先，不为凑数添加聚合页，也不强求每个讲解点都配网页素材。**INCLUDE**：

| 页面类型 | 为什么是好来源 | 期望产出 |
|---------|---------------|---------|
| 官方产品 / 项目首页 | 主视觉、截图、产品视频 | 图片 / 视频 + 滚动录像 |
| GitHub 仓库主页 | README 截图、demo gif、社交预览图 | 图片 / 视频 + 滚动录像 |
| 官方文档落地页 | 架构图、解释性长文 | 图片 / SVG + 滚动录像 |
| 官方博客 / 发布公告 | 内联图片、嵌入的 YouTube | 图片 / 视频 + 滚动录像 |
| Wikipedia 词条（成熟话题） | infobox 图片、整洁的散文 | 图片 + 滚动录像 |
| 会议演讲 / keynote 的 YouTube 页 | 通过 yt-dlp 下载 | pending video download |
| 作者个人站 / about 页 | 头像、横幅 | 图片 + 滚动录像 |
| 相关的社交帖子 / 作者时间线 | 官方账号发布的截图、演示、公告 | 图片 / 视频 + 滚动录像 |

社交来源优先选具体帖子而非整条 feed，只采集与主题相关的部分，禁将无关私人动态或他人头像当素材；匿名受限时按受限来源记录并继续。

**EXCLUDE**（低质或易拦截）：搜索结果页（Google / Bing）、聚合榜单页、付费墙正文页、应用商店缩略图页、PDF（PDF 由 Phase 2 `parse-pdf.py` 处理）。

URL 来源优先级：

1. 用户提供的 URL（若有则必含）；
2. `research-brief.md` **Source URLs** 一节；
3. `gemini_deep_research_sources.json`（存在时）中未覆盖且符合 INCLUDE 类型的 URL；
4. 关键讲解点仍缺画面时，在搜索额度内定向 `web_search` 官方图 / 文档 / 演讲视频（仍无则接受少 B-roll，禁拿搜索结果页顶替）。

#### 用户指定了搜索平台时

`inputs.json` 的 `material_search_requests` 非空时由 agent 侧按原话执行（新增或修改该字段须先按 `references/pipeline-control.md` 登记 `--redo 4-material-harvest`）：

- **图片搜索（Google / Bing 等）**：用浏览器或 Playwright 在目标平台搜图，进入匹配结果的**原始来源页面**核对出处、清晰度和使用许可后，将原始页面 URL 加入清单。
- **视频网站（YouTube / Bilibili）**：按“项目名 + 演示 / 讲座 / 实验”检索，优先官方或作者频道，确认后将观看页 URL 加入清单或传给 `video-download.py`。
- **平台受限或无合格结果**：先用继承登录态尝试，失败则将来源 URL、平台、尝试方式、受限原因与替代方案记入 `search-notes.md`（禁存凭据）；仅当缺失的是用户点名的核心不可替代素材时按材料不足报告。

#### 生成待抓的 URL 清单

将筛选后的纯 URL 写入 `{work_dir}/{topic_name}/harvest-urls.txt`（UTF-8，一行一个，空行忽略）。清单由 agent 汇总筛选后生成，勿直接传入带注释的 `research-brief.md` 或未筛选的 `gemini_deep_research_sources.json`。清单非阶段产物；补抓时更新为新批次 URL 重跑即可（自动追加 `harvest_batches`，已完成下载不重置）。

#### 运行 harvest-pages.py

```bash
source .venv/bin/activate && python3 scripts/harvest-pages.py \
  --urls-file "{work_dir}/{topic_name}/harvest-urls.txt" \
  --output-dir "{work_dir}/{topic_name}/harvest_page/" \
  --profile-dir "{work_dir}/chrome_profile" \
  --viewport 1680x1680
```

一律用 `--urls-file` 读文件（禁命令行展开长列表；`--urls` 仅限两三个 URL 调试且与之互斥）。默认单 URL 失败继续（`--no-continue-on-error` 才中断）；文件不可读或无有效行时以退出码 `2` 报错；首次启动 `1680x1680` Chrome 后保留进程供 CDP 复用。

#### harvest-pages.py 的实际输出

脚本更新磁盘累积的 `harvest_page/manifest.json`，并在 stdout 输出本批结果（stdout 仅含本批条目与 `chrome` 运行信息）。目录结构（普通页含 `page-source.html` / `images/` / `videos/` / `recording/`，视频直链仅含空 `videos/`）：

```text
harvest_page/
├── manifest.json
├── anthropic-com-news-claude-code-d30296/
│   ├── metadata.json          # 该 entry 的镜像，内容与 manifest.entries[i] 相同
│   ├── page-source.html
│   ├── images/img_001.png
│   ├── recording/scroll-1762012345.webm   # playwright 录制是 .webm，CDP 兜底是 .mp4
│   └── videos/
└── www-youtube-com-watch-df2c6f/
    ├── metadata.json
    └── videos/                # 尚未下载；下载后落在这里
```

磁盘上的 manifest（同一批的两种 entry；媒体路径相对 `harvest_page/`）：

```json
{
  "version": 2,
  "entries": [
    {
      "url": "https://anthropic.com/news/claude-code",
      "slug": "anthropic-com-news-claude-code-d30296",
      "success": true,
      "title": "Claude Code",
      "text_excerpt": "Claude Code is an agentic coding tool...",
      "metrics": {"word_count": 812, "video_count": 1},
      "images": [
        {
          "url": "https://anthropic.com/images/hero.png",
          "width": 1680,
          "height": 945,
          "alt": "Claude Code in a terminal",
          "type": "raster",
          "local_path": "anthropic-com-news-claude-code-d30296/images/img_001.png",
          "id": "img_001"
        }
      ],
      "videos": [],
      "scroll_recording": {
        "local_path": "anthropic-com-news-claude-code-d30296/recording/scroll-1762012345.webm",
        "duration_seconds": 30.0,
        "width": 1680,
        "height": 1680,
        "method": "playwright"
      }
    },
    {
      "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
      "slug": "www-youtube-com-watch-df2c6f",
      "success": true,
      "title": "",
      "text_excerpt": "",
      "metrics": {},
      "images": [],
      "videos": [
        {
          "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
          "platform": "youtube",
          "download_required": true,
          "suggested_output_dir": "www-youtube-com-watch-df2c6f/videos"
        }
      ],
      "scroll_recording": null
    }
  ],
  "pending_downloads": [
    {
      "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
      "platform": "youtube",
      "suggested_output_dir": "www-youtube-com-watch-df2c6f/videos",
      "source_slug": "www-youtube-com-watch-df2c6f"
    }
  ],
  "harvest_batches": [
    {
      "at": "2025-11-01T15:41:32.447141Z",
      "urls": [
        "https://anthropic.com/news/claude-code",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
      ],
      "succeeded": 2,
      "failed": 0,
      "rejected": []
    }
  ],
  "updated_at": "2025-11-01T15:41:32.447266Z"
}
```

字段要点：
- `pending_downloads[]` 在磁盘 manifest 中常驻（无待下项时为 `[]`，stdout 无待下项时省略）；同一视频跨多页引用只列一条 pending（附 `also_referenced_by`），只下一次。
- `scroll_recording.method` 为 `playwright`（`.webm`）或 `cdp_screencast`（`.mp4`），录制失败时整项为 `null`。
- 非 http(s) URL 归入 `rejected[]`；整批全部失败时 `success: false` 且退出码为 `1`。

同一次调用的 stdout（节选）：

```json
{
  "success": true,
  "output_dir": "/work/demo/harvest_page",
  "batch_size": 2,
  "succeeded": 2,
  "chrome": {"cdp_url": "http://localhost:9222", "reused": false, "ignored_flags": []},
  "entries": [
    {"url": "https://anthropic.com/news/claude-code", "slug": "anthropic-com-news-claude-code-d30296", "success": true},
    {"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "slug": "www-youtube-com-watch-df2c6f", "success": true}
  ],
  "pending_downloads": [
    {"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "platform": "youtube", "suggested_output_dir": "www-youtube-com-watch-df2c6f/videos", "source_slug": "www-youtube-com-watch-df2c6f"}
  ]
}
```

### Phase 4.b — 处理 pending video downloads

原生 HTML5 `<video>` 与图片已在 4.a 内联落盘；YouTube / Bilibili 直链需逐项顺序运行 `video-download.py`：

```bash
# 对 manifest.pending_downloads 里的每一项（每项只运行这一条命令）：
source .venv/bin/activate && python3 scripts/video-download.py --url "<item.url>" --harvest-dir "{work_dir}/{topic_name}/harvest_page/"
```

规则：

- **必须顺序执行**，避免 `yt-dlp` 并行限速 / 封 IP。
- 默认使用该项 `suggested_output_dir`，先在独立临时子目录下载并校验有效视频流，通过后移入 `harvest_page/<source_slug>/videos/`；文件名为 `<video_id>.<ext>`（字幕为同名 `.srt` sidecar），跨 entry 引用同一 URL 共用同一文件。
- 下载成功后自动将 `download_required` 置 `false`，写入相对 `local_path`、可选 `subtitle_path`、`id`（文件 stem）、宽高与时长，从 `pending_downloads[]` 移除并同步所有引用 entry 及 `metadata.json`。
- 返回 `{"success": false, "failure_kind": "...", "error": "..."}` 时：保留 `download_required: true` 并跳过（自动清理 `.ytdlp-*` 临时目录，不改动已有文件与 manifest）。遇 `"bot_check"`（如 `Sign in to confirm you’re not a bot` / `LOGIN_REQUIRED`）或 `"storyboard_only"`（无有效视频流）时**单次尝试即早停**，记入 `search-notes.md` 后直接继续下游；仅当话题强依赖该片段时，才用 `web_search` 找替代源更新清单重跑。

#### video-download.py 的实际输出

下载目录示例：

```text
harvest_page/www-youtube-com-watch-df2c6f/videos/
├── dQw4w9WgXcQ.webm
└── dQw4w9WgXcQ.en.srt
```

成功 stdout（路径为绝对路径；`ffprobe` 探测失败时宽高 / 时长为 `null`）：

```json
{
  "success": true,
  "output_dir": "/work/demo/harvest_page/www-youtube-com-watch-df2c6f/videos",
  "files": [
    "/work/demo/harvest_page/www-youtube-com-watch-df2c6f/videos/dQw4w9WgXcQ.webm",
    "/work/demo/harvest_page/www-youtube-com-watch-df2c6f/videos/dQw4w9WgXcQ.en.srt"
  ],
  "videos": [
    {
      "path": "/work/demo/harvest_page/www-youtube-com-watch-df2c6f/videos/dQw4w9WgXcQ.webm",
      "width": 1920,
      "height": 1080,
      "duration_seconds": 531.0
    }
  ],
  "stdout_tail": "[download] 100% of ...",
  "manifest_updated": true
}
```

磁盘 manifest 更新后的视频条目（路径相对 `harvest_page/`；无字幕时 `subtitle_path: null`）：

```json
{
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "platform": "youtube",
  "download_required": false,
  "downloaded": true,
  "local_path": "www-youtube-com-watch-df2c6f/videos/dQw4w9WgXcQ.webm",
  "subtitle_path": "www-youtube-com-watch-df2c6f/videos/dQw4w9WgXcQ.en.srt",
  "suggested_output_dir": "www-youtube-com-watch-df2c6f/videos",
  "id": "dQw4w9WgXcQ",
  "width": 1920,
  "height": 1080,
  "duration_seconds": 531.0
}
```

失败时退出码为 `1`，stdout 携带结构化 `failure_kind`（如 `bot_check`、`storyboard_only`、`login_required`、`rate_limited`、`unavailable`、`invalid_url`、`format_unavailable`、`max_filesize`、`network_error`、`extract_error`、`missing_binary`、`timeout`、`unknown`）：

```json
{
  "success": false,
  "failure_kind": "bot_check",
  "error": "Video site blocked automated download with a bot check (PO Token or cookies required)."
}
```

### Phase 4.c — 结果筛选（进入 Phase 5 之前）

对本阶段抓取的 web 素材（网页图片、原生视频、外部下载视频、滚动录像）剔除缩略图、模糊图与登录墙等明显不可用项；**不适用于 Phase 2 / 3 的论文图表**，话题相关性与精确选片归 Phase 5。

#### 尺寸条件

**一律以文件实际像素尺寸为准**（不用字节数、页面显示尺寸或放大后尺寸，也不按文件体积/码率/时长一刀切淘汰）：

| 素材 | 默认最低条件 | 说明 |
| --- | --- | --- |
| 位图图片 | 宽 ≥500 px 且 高 ≥300 px | 宽高分别比较（非长短边互换）；排除常见缩略图 |
| 视频 / 滚动录像 | 短边 ≥360 px 且 长边 ≥640 px | 约 360p 下限（`640×360` 与 `360×640` 均合格，`480×270` 剔除） |
| 要占满画面的大图 / 大视频 | 优先短边 ≥720 px 且 长边 ≥1280 px | 大画面优选，非小配图硬门槛 |
| SVG / 行内 SVG | 不套位图像素门槛 | 确认放大后内容清晰；内嵌低清位图不豁免 |

- 不修改采集脚本默认参数；宽高为 `null` 时须实测确认（禁把 `null` 当合格或编造尺寸；文件损坏走恢复流程）。
- 用户点名的关键素材清晰度不足时先搜高清版；找不到则如实说明，禁静默降标。

#### 清晰度判断

- **图片**：直接查看原文件主体、文字、公式、图表标签与 UI；主体糊成一片、重度压缩块、占位图或关键内容被遮挡的一律剔除（自然背景虚化或留白除外）。
- **视频 / 滚动录像**：用 `source .venv/bin/activate && python3 scripts/extract-frames.py` 先抽少量代表帧（如 `--max-frames 3`），**必须传不小于原视频宽度的 `--max-width`**（禁拿默认 512px 缩略帧误判高清源模糊），存疑处再抽局部确认：
  - 全片关键内容持续无法辨认，或为黑屏 / 登录页 / 验证码页 / 错误页 → 整段剔除（静态图表或演示不因缺乏运动剔除）；
  - 仅片头或局部运动模糊、其余清晰 → 保留，交由 Phase 5 选片避开。
- 直接人工看图 / 代表帧判断，不加 OpenCV / Laplacian 模糊阈值、OCR 或额外 VLM 过滤。

#### 筛选结果怎么落地

筛选结果必须写回 `harvest_page/manifest.json`（不另建排除文件或新字段）：

1. 在 `search-notes.md` 记录剔除项（slug、媒体 `id`、`local_path`、尺寸与原因如 `too_small` / `blurred` / `unreadable`）及发现/保留/剔除汇总。
2. 从对应 entry 的 `images[]` / `videos[]` 移除不合格项（同一物理视频跨多 entry 引用时一并移除），不合格滚动录像置 `scroll_recording: null`。
3. 在 skill 根目录调用 `harvest_manifest.upsert_entries` 同步写回 `manifest.json` 与对应 `metadata.json`（禁手改两份文件）：

   ```bash
   source .venv/bin/activate && python3 - <<'PY'
   import sys
   from pathlib import Path

   sys.path.insert(0, 'scripts')
   import harvest_manifest

   harvest_dir = Path('{work_dir}/{topic_name}/harvest_page')
   slug = '<slug>'
   drop_images = {'img_003'}      # 不合格的图片 id
   drop_videos = {'<video-id>'}   # 不合格的视频 id 或 url
   drop_recording = False         # 滚动录像也不合格时改成 True

   def dropped(item, keys):
       return any(key in keys for key in (item.get('id'), item.get('url')) if key)

   entry = next(e for e in harvest_manifest.load(harvest_dir)['entries'] if e['slug'] == slug)
   entry['images'] = [im for im in entry['images'] if not dropped(im, drop_images)]
   entry['videos'] = [v for v in entry['videos'] if not dropped(v, drop_videos)]
   if drop_recording:
       entry['scroll_recording'] = None
   harvest_manifest.upsert_entries(harvest_dir, [entry])
   PY
   ```

4. 保留原始媒体文件、原 `id`、论文 entry、来源 `metrics`（反映页面原始发现量，不改写）与 `harvest_batches`；下载失败（`download_required: true`）保留原状态，已下载文件丢失按损坏恢复。
5. 筛后不足可在剩余搜索额度内补抓重筛；仍不足则接受较少 B-roll 并如实说明。Phase 5 只读筛选后的 manifest。
