# Phase 4 — 素材抓取（可选；`inputs.json` 的 `fetch_materials = false` 时跳过）

## 输入

- `research.md` 的 **Source URLs** 一节（研究阶段已按可抓取页面类型预筛）；
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

`pipeline-status` 只检查 manifest 的结构。下面几项自己看：

- 抓到的页面真的和主题相关吗？明显无关的来源删掉并记下原因。
- 图片是否清晰可用（缩略图、水印、占位图不算），视频是否有内容而不是错误页。
- 返回 200 不等于内容可用：登录墙、验证码页、付费墙占位页不能当素材交给下游。
- `material_search_requests` 里每一条都执行过吗？找到、没找到、平台不可用，都要说清楚，不能把普通网页搜索说成已完成指定平台搜索。
- 受限来源（需登录 / 地区限制 / 反机器人验证）是否记入了 `search-notes.md`？Phase 9 交付时按它汇总给用户。
- 失败项保留 `download_required: true` 即可，不要为了过关伪造下载。
- Phase 4.c 的尺寸与清晰度筛选做了吗？不合格的素材是否已从 manifest 引用中移除，而不是只写在对话里？

素材明显不够或偏题，就补搜一次（仍在上限内）；还是不行就接受 B-roll 少一些，或者请用户自带素材，不以数量凑数。

## 下一步

Phase 5（素材 catalog）；若 `fetch_materials = false`，本 phase 跳过：标准模式下 Phase 5 也跳过，直接进入 Phase 6（脚本与场景规划，按"无素材"路径处理）；论文模式直接进入 Phase 5（仅论文素材）。

## 护栏

- **素材搜索是可选但推荐的。** `inputs.json` 里 `fetch_materials = false` 或用户自带全部视觉时跳过（Phase 4 / 5 一起跳过；论文模式只跳过 Phase 4，论文自己的 figure 仍由 Phase 5 进 catalog）。
- **Chrome over CDP。** `harvest-pages.py` 和 `gemini-deep-research.py` 必须显式传 `--profile-dir {work_dir}/chrome_profile`。复用已运行的 CDP 时，启动参数不会生效；检查 stderr warning 和输出 JSON 的 `chrome.ignored_flags`，需要新配置就先关闭复用的 Chrome。Chrome 启动即退出通常是 profile 被别的进程占着：关掉冲突进程或换 `--profile-dir`；9222 被占用时传另一个 `--cdp-url`，比如 `http://localhost:9223`。
- **登录态靠继承，不靠用户在流程中间去登录。** 采集 context 会继承共享 profile 的 cookies，并在该站点已打开标签页时带上它的 localStorage。登录态不够时记下受限来源继续做，到最终交付再提示补抓。不要停下来要求用户登录，不要向用户索取或自存密码 / cookie，也不要把“用的是同一个 Chrome”当成已登录的证据。
- **视频下载顺序执行。** yt-dlp 并行时会被限速。
- **`harvest-pages.py` 返回 0 张图时先怀疑加载。** 调大 `--page-load-timeout`；仍是 0 就复用 `{work_dir}/chrome_profile` 先手动处理 cookie banner、等懒加载出来，再重跑抓取。

---

### Phase 4.a — 选择 URL 并批量抓取页面

agent（LLM）先汇总、筛选出一批大概率能提供丰富视觉素材的 URL 写进 `harvest-urls.txt`，再用该文件 ONE 次调用 `harvest-pages.py`。对每个普通渲染页，工具会抽出图片 / 视频，并默认录制一段自上而下的滚动视频；YouTube/Bilibili 直链页面会被列入 Phase 4.b，而不是直接在 Chrome 里打开。

#### URL 选择规则（用来生成 URL 清单）

页面质量比数量重要：按相关性和素材质量挑，不为凑数添加聚合页，也不要求每个讲解点都配到画面——某个点只靠旁白讲也正常。**INCLUDE** 以下类型的页面：

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

社交页面**不因“可能需要登录”提前排除**：优先具体的帖子 / 贴文（信息密度高、容易定位画面），而不是整个 feed。采集时只用与主题相关的那部分，不把无关的个人动态带进成片，也不拿别人的头像 / 私人内容源当素材。如果只能匿名访问，登录墙后的内容抓不到，按下面的受限来源规则记录并继续。

**EXCLUDE**（产出低，常被 bot 拦截）：

- 搜索结果页（Google、Bing）—— 不是目的地
- 聚合榜单（"Top 10 AI tools..."）—— stock 图
- 付费墙新闻正文页 —— 内容被拦
- 应用商店 listing —— 只有小缩略图
- PDF —— 改用 `parse-pdf.py`（Phase 2）；`harvest-pages.py` 渲染不了 PDF

URL 来源（按优先级）：

1. 用户提供的 URL（如果有则必含）。
2. 研究 brief **Source URLs** 一节列出的 URL —— Phase 3 阶段已按可抓取的页面类型预筛过。
3. `gemini_deep_research_sources.json` 中所有未被上面覆盖、且匹配 INCLUDE 类型的 URL。文件存在就读完整；不存在（Gemini 未跑或失败）就跳过这一档，不因此阻塞抓取。
4. 如果某个要讲的重点仍缺可用画面，用 `web_search` 针对该缺口找具体页面（官方图、文档插图、演讲视频）；仍不够就接受 B-roll 少一些，不要用搜索结果页顶替。

#### 用户指定了搜索平台时

`inputs.json` 的 `material_search_requests` 非空时，按它写的原话去做，并且在 agent 这一侧完成——`harvest-pages.py` 不会自己去搜。这个字段只是记录“用户要在哪找素材”，不会自动触发重做；用户新提出或修改这类要求时，主 agent 先按 `references/pipeline-control.md` 用 `--redo 4-material-harvest` 登记，再在本阶段执行。

- **图片搜索（Google / Bing 等）：** 用浏览器或 Playwright 打开指定平台的图片搜索，按画面需求生成关键词；选中相关结果后进入原始页面，核对出处、清晰度和使用许可，再把**原始来源页面的 URL** 加入待抓列表。
- **视频网站（YouTube / Bilibili）：** 按“项目名 + 演示 / 讲座 / 实验”之类的关键词找候选，优先官方或作者发布；确认观看页与内容后，把观看 URL 写进清单（会被列入 `pending_downloads`）或直接交给 `video-download.py`。
- **平台打不开、需要登录或地区受限：** 先用现有登录态试，抓不到就把这个来源及其限制写进 `search-notes.md`，换其他可用来源继续；不要默认停下来请用户登录，也不要夸大成果。如果缺的正好是用户点名的核心素材且无替代，按材料不足处理，说清缺什么。
- **搜不到合格素材：** 如实说明结果，不为了交差保留偏题、模糊或来源不明的资源。

#### 受限来源的记录

抓不到或抓不全的来源记在工作区的 `search-notes.md`（和调研阶段的搜索记录同一个文件，不是阶段产物）：来源 URL、目标平台、尝试方式（匿名 / 继承登录态）、结果、限制原因（登录墙 / 验证码 / 地区 / 已下线）、替代来源，以及是否值得登录后补抓。不要写入密码、cookie 或任何凭据。

这条记录不会卡住流程：非关键来源失败就继续做，到 Phase 9 交付时汇总给用户。

#### 生成待抓的 URL 清单

把上面筛选出的 URL 写到 `{work_dir}/{topic_name}/harvest-urls.txt`：UTF-8，一行一个，空行忽略。

直接用研究文件是不行的：brief 的 **Source URLs** 是带页面类型注释的 Markdown，还没包含本阶段补搜 / 平台搜索得到的 URL；`gemini_deep_research_sources.json` 是未经素材筛选的引用列表，且可能不存在。所以清单由 agent 生成——它才是“这次实际要抓什么”的可复查记录。

清单不是阶段产物，不参与 `pipeline-status` 判定；续跑仍然只看状态脚本。补抓时把清单改成这次要抓的 URL，再跑一次（已有批次会追加进 `harvest_batches`，完成过的下载不会被重置）。

#### 运行 harvest-pages.py

```bash
python3 scripts/harvest-pages.py \
  --urls-file "{work_dir}/{topic_name}/harvest-urls.txt" \
  --output-dir "{work_dir}/{topic_name}/harvest_page/" \
  --profile-dir "{work_dir}/chrome_profile" \
  --viewport 1680x1680
```

从文件读整个列表，不要在命令行上展开 URL（`--urls $(cat file)` 同样受命令行长度限制）。只有两三个 URL 的手动调试才用 `--urls`（与 `--urls-file` 互斥）。默认单 URL 失败继续；传 `--no-continue-on-error` 中断。首次调用启动 1680x1680 Chrome 于 `{work_dir}/chrome_profile`；结束后保留进程供 CDP 复用。

文件读不到、不是 UTF-8 或没有有效行时，脚本在启动 Chrome 前就以参数错误（退出码 2）报错；不会建出半成品输出目录。

#### harvest-pages.py 的实际输出

它写两样东西：磁盘上的 `harvest_page/manifest.json`（累积的历史），和 stdout 上的一次批次结果。两者**不是同一个结构**：stdout 只有本批条目，`chrome` 这类运行信息也只在 stdout。

目录（每个 URL 一个 slug 目录；普通渲染页才有 `page-source.html` / `images/` / `videos/` / `recording/`，视频直链条目只有空的 `videos/`）：

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

几点容易误读的地方：

- 普通页 entry 与视频直链 entry 字段集合相同；直链条目 `images` 为空、`scroll_recording` 为 `null`。
- `pending_downloads[]` 是推导出来的，磁盘上始终保留该列表（没有待下载项时是 `[]`）；stdout 在没有待下载项时**省略**该字段。
- 同一视频被多个页面引用时只会出现一条 pending（`source_slug` 是首次发现的页面，其余写在 `also_referenced_by`），只需下载一次。
- `scroll_recording.method` 记录实际用的后端（`playwright` 或 `cdp_screencast`），失败时整个 `scroll_recording` 为 `null`。
- `chrome`（`cdp_url` / `reused` / `ignored_flags`）只在 stdout，不入 manifest。

同一次调用的 stdout（节选，未列出的字段与磁盘条目相同）：

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

非 http(s) 的 URL 不会让整批失败，而是进 `rejected[]`（同时在 stdout 顶层出现）；全部 URL 都失败时 `success` 为 `false` 且退出码为 1。

### Phase 4.b — 处理 pending video downloads

`harvest-pages.py` 对 YouTube 和 Bilibili 只**列出** URL（原生 HTML5 `<video>` 片段会在发现阶段直接内联下载，因为它们需要页面的 cookie / referer；图片也会实际落盘）。agent 必须对 `pending_downloads[]` 的每一项调用 `video-download.py` 真正去下：

```bash
# 对 manifest.pending_downloads 里的每一项（每项只运行这一条命令）：
python3 scripts/video-download.py --url "<item.url>" --harvest-dir "{work_dir}/{topic_name}/harvest_page/"
```

规则：

- **顺序执行**，不并行 —— yt-dlp 并行时容易被限速 / 限 IP。
- 不传 `--output-dir` 时自动使用该项的 `suggested_output_dir`，下载到 `harvest_page/<source_slug>/videos/`。
- 文件名用 yt-dlp 的视频 id 加实际扩展名（如 `dQw4w9WgXcQ.webm`），字幕是同名 sidecar（如 `dQw4w9WgXcQ.en.srt`）；同一 URL 只下一个视频，被多个 entry 引用时共用这一个文件。
- 下载成功会自动将 `download_required` 置为 `false`、加上相对 `local_path` 和可选的 `subtitle_path`、把 `id` 设为下载文件的 stem，写入媒体宽高和时长，并同步 manifest、所有引用 entry 及其 `metadata.json`。
- 如果 `video-download.py` 返回 `{"success": false}`（地区封锁、年龄限制、410 等），保留 `download_required: true` 并跳过它；Phase 5 不会把没有本地文件的视频拿去抽帧。如果该话题正好依赖这段 clip，用 `web_search` 找一个被转发的镜像，并在清单里换成新 URL 重跑 `harvest-pages.py`。

#### video-download.py 的实际输出

下载后的目录（文件名来自 yt-dlp 的视频 id；没下到字幕时就没有 `.srt`）：

```text
harvest_page/www-youtube-com-watch-df2c6f/videos/
├── dQw4w9WgXcQ.webm
└── dQw4w9WgXcQ.en.srt
```

成功时的 stdout（`files` / `videos[].path` 是绝对路径；宽高 / 时长来自 ffprobe，探测失败时为 `null`）：

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

同一条视频在磁盘 manifest 里的变化（其余字段不变，路径变成相对 `harvest_page/`）：

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

- 同一条 URL 从 `pending_downloads[]` 消失；引用它的每个 entry 和各自的 `metadata.json` 同步更新，**不另生成一份 download manifest**。
- 没有字幕时 `subtitle_path` 为 `null`；视频探测不到尺寸 / 时长时对应字段为 `null`。
- 失败时 stdout 为 `{"success": false, "error": "..."}`，退出码 1，manifest 保持不变；但输出目录里可能已经留下部分下载文件，不要假定失败就一定没产物。

### Phase 4.c — 结果筛选（进入 Phase 5 之前）

4.a 抽出的东西和 4.b 下回来的视频不能直接交给下游：网页里的缩略图、低清粘贴图、展示横幅和登录页截图都会混在里面。本步骤把明显不能用的挑出去，只留可用素材。

分工：**Phase 4 只剔除“明显不能用”的**（太小、看不清、根本不是内容）；话题相关性、VLM 评分、选哪几秒归 Phase 5。不要在这里把整套视觉分析重做一遍。

适用范围：本阶段抓的 web 素材（原生视频、已下载的外部平台视频、滚动录像、网页图片）。**不**套到 Phase 2 / 3 的论文 figure 和 table 上。

#### 尺寸条件

下面的门槛是制作默认值，不是行业标准。**以文件的实际像素尺寸为准**，不用文件字节数、不用页面上的显示尺寸、不把放大后的尺寸当成像素尺寸。

| 素材 | 默认最低条件 | 说明 |
| --- | --- | --- |
| 位图图片 | 宽 ≥500 px 且 高 ≥300 px | 与 harvester 初抓门槛一致；排除常见缩略图 |
| 视频 / 滚动录像 | 短边 ≥360 px 且 长边 ≥640 px | 约 360p 下限；`640×360` 与 `360×640` 都过，`480×270` 不过 |
| 要占满画面的大图 / 大视频 | 优先短边 ≥720 px 且 长边 ≥1280 px | 720p 以上更适合大画面；这是优选，不是所有小配图的硬门槛 |
| SVG / 行内 SVG | 不套位图像素门槛 | 矢量图不能按声明尺寸淘汰；但仍要确认放大后内容清楚，内嵌低清位图不自动豁免 |

- 不改 `--min-image-width` / `--min-image-height` 默认值，也不新增视频尺寸参数：视频门槛写在下载完成后的执行判断里。
- 图片门槛是宽高**分别**比较（`500×300`），不是旋转无关的长短边规则；较窄的竖图若被初抓漏掉，下一次单独讨论，不在本轮顺手改采集参数。
- 宽高缺失或为 `null` 时先实证确认，不能把 `null` 当合格，也不能编一个尺寸填上去；媒体本身损坏走恢复流程，不当作“素材不合格”静默丢掉。
- 不拿文件体积、码率或时长单独判模糊，也不加统一的最短视频时长要求。
- 用户点名要的关键素材不够清：先找高清版本；真找不到就说明不足，不默默降低门槛，也不假装已合格。

#### 清晰度判断

**图片：** 直接看下载下来的文件，重点看要上屏的主体、文字、公式、图表标签和 UI。尺寸够但关键内容糊成一片、压缩块明显、只有占位图、关键部分被遮挡，同样剔除。背景自然虚化、留白、线条稀疏本身不算不清楚。

**视频 / 滚动录像：** 先用 `extract-frames.py` 抽少量代表帧看一眼，例如 `--max-frames 3`；怀疑某处有问题时再专门抽那一段，不要仅凭三帧下结论说整段都没用。

抽帧默认会把宽度缩到 512 px，**别用这个缩略预览判原片模糊**：质量检查时传 `--max-width` 不小于原视频宽度，否则会把高清源误判成模糊。

- 关键内容持续认不出、全片找不到清楚可用的画面 → 整段剔除。
- 只是一段运动模糊、片头很糊，其余部分清楚 → 保留，由 Phase 5 选片时避开那些位置。
- 黑屏、登录页、验证码页、错误页不当画面用。静态演示、图表不因“不运动”被一刀切排除。
- 不加 OpenCV、Laplacian 模糊阈值、OCR 判分或第二轮 VLM 分析：直接看图 / 代表帧，避免误伤矢量图、文字图和低纹理素材。

#### 筛选结果怎么落地

只在对话里说“这张不要”，或者只在笔记里标注却仍把原 manifest 交给 Phase 5，都不算筛完。做法是把**筛选后的媒体清单写回同一份 manifest**，不另建排除清单，也不加新字段。

1. 先列不合格的：entry slug、媒体 `id` 与相对 `local_path`、尺寸、原因（`too_small` / `blurred` / `unreadable` 等），写进现有 `search-notes.md`。那只是审计说明，不是新字段，也不参与状态判定。
2. 把已下载且确认不合格的图片 / 视频从对应 entry 的 `images[]` / `videos[]` 中移除；不合格的滚动录像设为 `scroll_recording: null`。同一个物理视频被多个 entry 引用时，所有引用一起处理。
3. 用现有入口写回（在 skill 根目录运行；`upsert_entries` 内部已经传 `dirty_slugs`，会同步 `manifest.json` 和对应 `metadata.json`，不要手写两份文件）：

   ```bash
   python3 - <<'PY'
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

   一个 entry 只需改一行（`slug` 与两个集合）；多条目不合格就按条重跑。别把不合格项留在数组里等下游自己筛：Phase 5 不会替你做这个判断。
4. 原始媒体文件保留供复查，不重命名 `id`；保留 URL / slug、论文 entry、来源 `metrics` 和 `harvest_batches`。`metrics` 描述的是页面发现情况，不改成筛选后的数量；发现 / 保留 / 剔除的数量与原因汇总在 `search-notes.md`。
5. 下载失败（`download_required: true`）的不是质量不合格，保留原状态和 pending；已下载却文件不见的是损坏，走恢复，不静默当成“质量不合格”跳过。
6. 筛完不够，按现有搜索额度补找高清来源，补抓后重新筛；还是不够就接受少一些 B-roll 并如实说明。

下游只读筛选后的 manifest：Phase 5 不会去翻原目录把剔除的素材捡回来。
