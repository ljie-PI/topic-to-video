# Phase 4 — 素材抓取（可选；`inputs.json` 的 `fetch_materials = false` 时跳过）

## 输入

`research-brief.md` 的 **Source URLs** 一节（研究阶段已按可抓取页面类型预筛）+ 用户提供的 URL + `gemini_deep_research_sources.json`。

## 输出

`harvest_page/manifest.json`（v2，`entries` 与 `harvest_batches` 非空）+ `harvest_page/<url-slug>/` 目录；YouTube/Bilibili 条目带 `pending_downloads[]`，`video-download.py --harvest-dir` 会在下载成功后直接更新 manifest。论文 entry 已由 Phase 2 / Phase 3 写入同一份 manifest，后续 harvest 不会覆盖它。

## 完成判据

`harvest_page/manifest.json` 存在、非空、JSON 可解析且 `entries` 与 `harvest_batches` 为非空列表（只有论文 entry 不算完成 web harvest）；`pending_downloads[]` 已逐项顺序处理（失败项保留 `download_required: true`）。

## 执行后自检

`pipeline-status` 只检查 manifest 的结构和 `pending_downloads` 是否已逐项处理。下面几项自己看：

- 抓到的页面真的和主题相关吗？明显无关的来源删掉并记下原因。
- 图片是否清晰可用（缩略图、水印、占位图不算），视频是否有内容而不是错误页。
- `material_search_requests` 里每一条都执行过吗？找到、没找到、平台不可用，都要说清楚。
- 失败项保留 `download_required: true` 即可，不要为了过关伪造下载。

素材明显不够或偏题，就补搜一次（仍在上限内）；还是不行就接受 B-roll 少一些，或者请用户自带素材，不以数量凑数。

## 下一步

Phase 5（素材 catalog）；若 `fetch_materials = false`，本 phase 跳过：标准模式下 Phase 5 也跳过，直接进入 Phase 6（脚本与场景规划，按"无素材"路径处理）；论文模式直接进入 Phase 5（仅论文素材）。

## 护栏

- **素材搜索是可选但推荐的。** `inputs.json` 里 `fetch_materials = false` 或用户自带全部视觉时跳过（Phase 4 / 5 一起跳过；论文模式只跳过 Phase 4，论文自己的 figure 仍由 Phase 5 进 catalog）。
- **Chrome over CDP。** `harvest-pages.py` 和 `gemini-deep-research.py` 必须显式传 `--profile-dir {work_dir}/chrome_profile`。复用已运行的 CDP 时，启动参数不会生效；检查 stderr warning 和输出 JSON 的 `chrome.ignored_flags`，需要新配置就先关闭复用的 Chrome。Chrome 启动即退出通常是 profile 被别的进程占着：关掉冲突进程或换 `--profile-dir`；9222 被占用时传另一个 `--cdp-url`，比如 `http://localhost:9223`。
- **视频下载顺序执行。** yt-dlp 并行时会被限速。
- **`harvest-pages.py` 返回 0 张图时先怀疑加载。** 调大 `--page-load-timeout`；仍是 0 就复用 `{work_dir}/chrome_profile` 先手动处理 cookie banner、等懒加载出来，再重跑抓取。

---

agent（LLM）先生成一批大概率能提供丰富视觉素材的 URL，再用整个列表 ONE 次 调用 `harvest-pages.py`。对每个普通渲染页，工具会抽出图片 / 视频，并默认录制一段自上而下的滚动视频；YouTube/Bilibili 直链页面会被列入 Phase 4.b，而不是直接在 Chrome 里打开。

#### URL 选择规则（用来构建数组）

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

**EXCLUDE**（产出低，常被 bot 拦截）：

- 搜索结果页（Google、Bing）—— 不是目的地
- 社交媒体 feed（Twitter/X 时间线、LinkedIn feed）—— 需要登录
- 聚合榜单（"Top 10 AI tools..."）—— stock 图
- 付费墙新闻正文页 —— 内容被拦
- 应用商店 listing —— 只有小缩略图
- PDF —— 改用 `parse-pdf.py`（Phase 2）；`harvest-pages.py` 渲染不了 PDF

URL 来源（按优先级）：

1. 用户提供的 URL（如果有则必含）。
2. 研究 brief **Source URLs** 一节列出的 URL —— Phase 3 阶段已按可抓取的页面类型预筛过。
3. `gemini_deep_research_sources.json` 中所有未被上面覆盖、且匹配 INCLUDE 类型的 URL。读整个文件，把每条符合条件的都加上。
4. 如果某个要讲的重点仍缺可用画面，用 `web_search` 针对该缺口找具体页面（官方图、文档插图、演讲视频）；仍不够就接受 B-roll 少一些，不要用搜索结果页顶替。

#### 用户指定了搜索平台时

`inputs.json` 的 `material_search_requests` 非空时，按它写的原话去做，并且在 agent 这一侧完成——`harvest-pages.py` 不会自己去搜。这个字段只是记录“用户要在哪找素材”，不会自动触发重做；用户新提出或修改这类要求时，主 agent 先按 `references/pipeline-control.md` 用 `--redo 4-material-harvest` 登记，再在本阶段执行。

- **图片搜索（Google / Bing 等）：** 用浏览器或 Playwright 打开指定平台的图片搜索，按画面需求生成关键词；选中相关结果后进入原始页面，核对出处、清晰度和使用许可，再把**原始来源页面的 URL** 加入待抓列表。
- **视频网站（YouTube / Bilibili）：** 按“项目名 + 演示 / 讲座 / 实验”之类的关键词找候选，优先官方或作者发布；确认观看页与内容后，把观看 URL 交给 `harvest-pages.py`（会被列入 `pending_downloads`）或直接交给 `video-download.py`。
- **平台打不开、需要登录或地区受限：** 说明限制，请用户给直链或同意换来源；不要把普通网页搜索说成已经做了指定平台的图片搜索。
- **搜不到合格素材：** 如实说明结果，不为了交差保留偏题、模糊或来源不明的资源。

#### 运行 harvest-pages.py

```bash
scripts/harvest-pages.py \
  --urls https://anthropic.com/news/claude-code \
         https://github.com/anthropics/claude-code \
         https://docs.anthropic.com/claude-code \
         https://www.youtube.com/watch?v=... \
  --output-dir {work_dir}/{topic_name}/harvest_page/ \
  --profile-dir {work_dir}/chrome_profile \
  --viewport 1680x1680
```

默认单 URL 失败继续；传 `--no-continue-on-error` 中断。首次调用启动 1680x1680 Chrome 于 `{work_dir}/chrome_profile`；结束后保留进程供 CDP 复用。

输出：`harvest_page/manifest.json` + `harvest_page/<url-slug>/` 目录（每个 URL 一个）。`manifest.entries[]` 的结构如下——每个渲染页 entry 含有 `text_excerpt`、`metrics`、`images[]`、`videos[]`，以及可选的 `scroll_recording`；YouTube/Bilibili 直链 entry 的 `videos[]` 带有 `download_required: true` 且没有 scroll recording。manifest 顶层还会带一个 **`pending_downloads[]`** —— 列出 harvester 检测到的所有 YouTube/Bilibili URL（不管是直接通过 `--urls` 传入的，还是从页面里发现内嵌的）。

### Phase 4.b — 处理 pending video downloads

`harvest-pages.py` 是纯发现工具：它会内联下载原生 HTML5 `<video>` 片段（因为这些需要页面的 cookie / referer），但对 YouTube 和 Bilibili 只**列出** URL。agent 必须对 `pending_downloads[]` 的每一项调用 `video-download.py` 真正去下：

```bash
# 对 manifest.pending_downloads 里的每一项（每项只运行这一条命令）：
scripts/video-download.py --url "<item.url>" --harvest-dir {work_dir}/{topic_name}/harvest_page/
```

规则：
- **顺序执行**，不并行 —— yt-dlp 并行时容易被限速 / 限 IP。
- 不传 `--output-dir` 时自动使用该项的 `suggested_output_dir`，下载到 `harvest_page/<source_slug>/videos/`。
- 下载成功会自动将 `download_required` 置为 `false`、加上相对 `local_path` 和可选的 `subtitle_path`、把 `id` 设为下载文件的 stem，写入媒体宽高和时长，并同步 manifest、所有引用 entry 及其 `metadata.json`。
- 如果 `video-download.py` 返回 `{"success": false}`（地区封锁、年龄限制、410 等），保留 `download_required: true` 并跳过它——Phase 5 会忽略它。如果该话题正好依赖这段 clip，用 `web_search` 找一个被转发的镜像，并用新 URL 重跑 `harvest-pages.py`。
