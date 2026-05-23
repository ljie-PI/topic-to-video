### Phase 3 — 素材抓取

agent（LLM）先生成一批大概率能提供丰富视觉素材的 URL，再用整个列表 ONE 次 调用 `harvest-pages.py`。对每个普通渲染页，工具会抽出图片 / 视频，并默认录制一段自上而下的滚动视频；YouTube/Bilibili 直链页面会被列入 Phase 3.b，而不是直接在 Chrome 里打开。

#### URL 选择规则（用来构建数组）

目标 **10-15 个 URL**。**INCLUDE** 以下类型的页面：

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
- PDF —— 改用 `parse-pdf.py`（Phase 2a）；`harvest-pages.py` 渲染不了 PDF

URL 来源（按优先级）：

1. 用户提供的 URL（如果有则必含）。
2. 研究 brief **Source URLs** 一节列出的 URL —— Phase 2 阶段已按可抓取的页面类型预筛过。
3. `gemini_deep_research_sources.json` 中所有未被上面覆盖、且匹配 INCLUDE 类型的 URL。读整个文件，把每条符合条件的都加上。
4. 如果仍然 <10 个 URL，用 `web_search` 搜 `"{topic} official site"`、`"{topic} github"`、`"{topic} documentation"`、`"{topic} demo"` 直到列表达到 10-15 条。

#### 运行 harvest-pages.py

```bash
scripts/harvest-pages.py \
  --urls https://anthropic.com/news/claude-code \
         https://github.com/anthropics/claude-code \
         https://docs.anthropic.com/claude-code \
         https://www.youtube.com/watch?v=... \
  --output-dir {work_dir}/{topic_name}/harvest_page/ \
  --profile-dir {work_dir}/chrome_profile
```

第一次调用会在 `{work_dir}/chrome_profile` 启动 Chrome；后续调用通过 CDP（`http://localhost:9222`）复用同一进程。Chrome 在多次调用之间保持运行。单条 URL 失败不会拖垮整个 batch。

输出：`harvest_page/manifest.json` + `harvest_page/<url-slug>/` 目录（每个 URL 一个）。`manifest.entries[]` 的结构如下——每个渲染页 entry 含有 `text_excerpt`、`metrics`、`images[]`、`videos[]`，以及可选的 `scroll_recording`；YouTube/Bilibili 直链 entry 的 `videos[]` 带有 `download_required: true` 且没有 scroll recording。manifest 顶层还会带一个 **`pending_downloads[]`** —— 列出 harvester 检测到的所有 YouTube/Bilibili URL（不管是直接通过 `--urls` 传入的，还是从页面里发现内嵌的）。

#### Paper mode：把解析出来的论文并入 manifest

当 `input_mode = "paper"` 时，`parse-pdf.py` 会把论文 entry 写到 `harvest_page/manifest_papers.json`（独立于 web harvest manifest）。`harvest-pages.py` 跑完（或被跳过）后，将其合并：

```bash
scripts/merge-paper-manifest.py \
  --harvest-dir {work_dir}/{topic_name}/harvest_page/
```

合并之后，`manifest.json` 同时包含论文来源 entry（`source_type: "paper_pdf"`）和 web 来源 entry。后续所有阶段都读同一份统一 manifest。

### Phase 3.b — 处理 pending video downloads

`harvest-pages.py` 是纯发现工具：它会内联下载原生 HTML5 `<video>` 片段（因为这些需要页面的 cookie / referer），但对 YouTube 和 Bilibili 只**列出** URL。agent 必须对 `pending_downloads[]` 的每一项调用 `video-download.py` 真正去下：

```bash
# 对 manifest.pending_downloads 里的每一项：
scripts/video-download.py \
  --url "<item.url>" \
  --output-dir "<item.suggested_output_dir>"
```

规则：
- **顺序执行**，不并行 —— yt-dlp 并行时容易被限速 / 限 IP。
- 直接用 `item.suggested_output_dir`；它就是 `harvest_page/<source_slug>/videos/`，下载下来的文件会落到与原生视频同一目录。
- 每次下载成功后，把 JSON 结果应用到 `manifest.json` 和对应的 `metadata.json`：
  ```bash
  scripts/apply-video-download-result.py \
    --harvest-dir {work_dir}/{topic_name}/harvest_page/ \
    --source-slug "<item.source_slug>" \
    --url "<item.url>" \
    --result-json /path/to/video-download-result.json
  ```
  这一步会将 `download_required` 置为 `false`、加上 `local_path` 和可选的 `subtitle_path`、把 `id` 设为下载文件的 stem，并把更新同步扩散到所有 `also_referenced_by` slug。
- 如果 `video-download.py` 返回 `{"success": false}`（地区封锁、年龄限制、410 等），保留 `download_required: true` 并跳过它——Phase 4 会忽略它。如果该话题正好依赖这段 clip，用 `web_search` 找一个被转发的镜像，并用新 URL 重跑 `harvest-pages.py`。

这种解耦让 `harvest-pages.py` 的运行时间由 Playwright（快、确定）主导，而 yt-dlp 的失败被局限在单条 URL 上，不会拖垮整个 batch。
