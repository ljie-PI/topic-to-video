# Phase 4 — 素材抓取（可选；`inputs.json` 的 `fetch_materials = false` 时跳过）

## 输入

`research-brief.md` 的 **Source URLs** 一节（研究阶段已按可抓取页面类型预筛）+ 用户提供的 URL + `gemini_deep_research_sources.json`。

## 输出

`harvest_page/manifest.json`（v2，`entries` 与 `harvest_batches` 非空）+ `harvest_page/<url-slug>/` 目录；YouTube/Bilibili 条目带 `pending_downloads[]`，`video-download.py --harvest-dir` 会在下载成功后直接更新 manifest。论文 entry 已由 Phase 2 写入同一份 manifest，后续 harvest 不会覆盖它。

## 完成判据

`harvest_page/manifest.json` 存在、非空、JSON 可解析且 `entries` 与 `harvest_batches` 为非空列表（只有论文 entry 不算完成 web harvest）；`pending_downloads[]` 已逐项顺序处理（失败项保留 `download_required: true`）。

## 下一步

Phase 5（素材 catalog）；若 `fetch_materials = false`，本 phase 与 Phase 5 都跳过，直接进入 Phase 6（脚本与场景规划，按"无素材"路径处理）。

---

agent（LLM）先生成一批大概率能提供丰富视觉素材的 URL，再用整个列表 ONE 次 调用 `harvest-pages.py`。对每个普通渲染页，工具会抽出图片 / 视频，并默认录制一段自上而下的滚动视频；YouTube/Bilibili 直链页面会被列入 Phase 4.b，而不是直接在 Chrome 里打开。

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
- PDF —— 改用 `parse-pdf.py`（Phase 2）；`harvest-pages.py` 渲染不了 PDF

URL 来源（按优先级）：

1. 用户提供的 URL（如果有则必含）。
2. 研究 brief **Source URLs** 一节列出的 URL —— Phase 3 阶段已按可抓取的页面类型预筛过。
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
  --profile-dir {work_dir}/chrome_profile \
  --viewport 1680x1680
```

默认单 URL 失败继续；传 `--no-continue-on-error` 中断。首次调用启动 1680x1680 Chrome 于 `{work_dir}/chrome_profile`；结束后保留进程供 CDP 复用。

输出：`harvest_page/manifest.json` + `harvest_page/<url-slug>/` 目录（每个 URL 一个）。`manifest.entries[]` 的结构如下——每个渲染页 entry 含有 `text_excerpt`、`metrics`、`images[]`、`videos[]`，以及可选的 `scroll_recording`；YouTube/Bilibili 直链 entry 的 `videos[]` 带有 `download_required: true` 且没有 scroll recording。manifest 顶层还会带一个 **`pending_downloads[]`** —— 列出 harvester 检测到的所有 YouTube/Bilibili URL（不管是直接通过 `--urls` 传入的，还是从页面里发现内嵌的）。

#### Paper mode：保留解析出来的论文

当 `input_mode = "paper"` 时，`parse-pdf.py` 已把论文 entry upsert 到 `harvest_page/manifest.json`。`harvest-pages.py` 每批也只 upsert 本批 entry 并追加 `harvest_batches`，因此重跑或换镜像 URL 不会抹掉论文、其他批次或已完成的下载。后续所有阶段都读同一份统一 manifest。

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
