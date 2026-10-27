# catalog 基础指令（Phase 5 — 素材理解与筛选）

遍历 Phase 4 产出的 `harvest_page/manifest.json["entries"]`。对每一条 entry，在 `{work_dir}/{topic_name}/material-catalog.json` 里建一个 "material entry"。

**路径 base（必须保持一致）：** v2 manifest 里的 `local_path` / `subtitle_path`（包括 `scroll_recording.local_path`）都相对于 `{work_dir}/{topic_name}/harvest_page/`，不是相对于当前目录或 workspace root。调用抽帧、字幕解析和视觉分析工具时，相对路径必须加上这个 `harvest_page/` 前缀；旧 manifest 的绝对路径原样使用。写入 `material-catalog.json` 时仍原样保留 manifest 的相对路径，不改写成绝对路径或其他 base。

**每一条 harvest entry（每个 URL 一条）：**

1. **抽帧**：对 `entry.videos` 里的每个视频，以及 `entry.scroll_recording`（如果有）：
   ```bash
   scripts/extract-frames.py <video> \
     {work_dir}/{topic_name}/extract_frames/<slug>/<video-name>/ \
     --max-frames 16
   ```
   帧文件名带时间戳（如 `frame_t0012.50s.jpg`）。输出 JSON 的 `interval_s` 是采样间隔，`frames` 中每项含绝对路径 `path` 和源视频时间 `t_s`（秒），可以反向映射到 clip 区间。

2. **解析字幕**：对每个带 sidecar 字幕文件的已下载视频：
   ```bash
   scripts/subtitle-parse.py <subtitle> --keywords '<terms from research brief>'
   ```
   输出 JSON 的 `entries` 中，每条字幕包含 `text`、`begin_s` / `end_s`（秒）及原始时间戳；无法解析时间戳的 cue 会被跳过并记入 `warnings`，其余字幕正常输出。

3. **视觉分析**：用 `scripts/vision-analyze.py`，传入 `--context-file vision_analyze/topic-context.txt`：
   - 对图片（光栅图和 SVG）：按 URL 聚合图片，每次调用最多放 10 张；同一 URL 超过 10 张时拆成多个 batch，且共享同一话题 context 摘要。prompt 询问"这张图在讲解该话题时可以用来说明什么论点或概念"、视觉风格、1-10 的适配度评分，并根据 `width` / `height` 和画面内容给出布局能力提示：是否适合 `media_first`、`viewport_reveal`、`band`、`detail_callout`、`comparison_pair` 等。对 tall / ultra-tall 素材，写入 `viewport_reveal` affordance，并标注 `focal_region`、start / mid / end 关键区域或 avoid-region；可用 0-1 归一化坐标。
   - 对每个视频：一个 batch 跑在抽出的帧上。prompt 额外询问最相关片段的起止时间戳，以及该片段适合说明话题的哪个方面；同时判断该 clip 是否适合 `video_first`、`viewport_reveal`、`comparison_pair` 或 `comparison_sequence`，并指出关键动作 / UI 区域或应避免遮挡的区域。
   - **Mode 1（显式 VLM）：** 若已设置 `VLM_API_KEY` + `VLM_BASE_URL` + `VLM_MODEL` → 直接走 OpenAI 兼容的调用，话题 context 摘要作为 system prompt 或 user prompt 前缀注入。
   - **Mode 2（主 agent 直接分析）：** 否则 → 脚本返回 `delegate_to_agent`、图片路径列表和 `context`（话题摘要原文）。此时由**主 agent 自身的多模态视觉能力**（Read 图片文件，让模型直接看图）完成分析——使用与主 agent 其他推理相同的模型，不调用任何外部工具。分析时使用返回的 `context`，与 Mode 1 保持一致，产出同样格式的 `semantic_description` 和 `score`，并手动写入 `material-catalog.json`。

   **Paper-origin entries（manifest 里 `source_type: "paper_pdf"` 的 entry；写进 catalog 后按 slug 辨认——`main-paper` 是主论文，`related-*` 是相关论文，catalog schema 没有 `source_type` 字段）：** 直接把 PDF caption（`paper_metadata.figure_captions` / `table_captions`）作为 `semantic_description`，默认 `score: 8`。**caption 为空字符串等同没有 caption**——parse-pdf 对每个图表 id 都写条目，没抽到标题的是 `''`：这种走下面的 VLM 步骤，不要写空的 `semantic_description`（状态脚本会判 corrupt）。带 caption 的条目不做视觉分析。

4. **组合**：把 `entry.text_excerpt` + 图片描述 + 各帧描述合成 catalog entry。**关键：** 对每个视频，写一份 `selected_clips` 列表，元素形如 `{start, end, reason, frame_paths[]}` —— 这些就是 Phase 6（场景规划的 `material_candidates`）和 Phase 8（composition）会引用的片段。`clip_path` 不用手写，由下面「切片段」一节的 `cut-clips.py` 写入。

5. **过滤：** 丢掉 VLM 评分 <5/10 或者偏题的素材。不要把垃圾带进解说阶段。

**切片段（所有 entry 的 catalog 写完之后，运行一次）：**

```bash
scripts/cut-clips.py {work_dir}/{topic_name}
```

对 catalog 里每个视频的每个 `selected_clip`，切出 `{work_dir}/{topic_name}/clips/<video_id>_<start:.2f>-<end:.2f>.mp4`（`-an` 去掉音轨，libx264 重编码），在该 clip 上写入 `clip_path`（相对工作区），并原地更新 `material-catalog.json`（原子写、保留原文件权限）。视频的相对 `local_path` 以 `harvest_page/` 为 base，绝对路径原样使用。目标文件已存在且非空时跳过，所以改过 catalog 后可以直接重跑。输出 JSON：`{"success": true, "clips": [{"ref": "<video_id>:<start>-<end>", "clip_path": ..., "skipped": false}], "errors": []}`；只要有一个 clip 失败就退出 1（已切好的保留且 catalog 增量写回），按 `errors` 里的 `ref` 与原因修 catalog（窗口、`local_path`）后重跑。

**`material-catalog.json` 的结构：**

```json
{
  "topic_name": "...",
  "entries": [
    {
      "url": "...", "slug": "...", "title": "...", "page_type": "...",
      "text_excerpt": "...",
      "images": [
        {
          "id": "img_001",
          "local_path": "example/images/img_001.webp",
          "width": 1280, "height": 720,
          "aspect_ratio": 1.7778,
          "ratio_bucket": "wide",
          "layout_affordance": ["media_first", "comparison_pair"],
          "focal_region": null,
          "semantic_description": "...", "score": 8
        }
      ],
      "videos": [
        {
          "id": "2MJDdzSXL74",
          "local_path": "example/videos/2MJDdzSXL74.webm",
          "width": 1920, "height": 1080,
          "aspect_ratio": 1.7778,
          "ratio_bucket": "wide",
          "layout_affordance": ["video_first", "comparison_sequence"],
          "focal_region": {"x": 0.12, "y": 0.18, "w": 0.74, "h": 0.62, "reason": "关键 UI 操作区域"},
          "duration_seconds": 312.4,
          "semantic_description": "...",
          "selected_clips": [
            {"start": 12.0, "end": 18.5, "reason": "...", "frame_paths": [...],
             "clip_path": "clips/2MJDdzSXL74_12.00-18.50.mp4"}
          ]
        }
      ]
    }
  ]
}
```

- `entries[*].slug` 在每个 URL 上唯一，与 harvest 输出目录名一致。
- 每张图 / 每个视频都带一个 `id`（harvester 写出的文件 stem，例如 `img_001` 或 YouTube video id）。Phase 6 起通过 **`material_ref`** 引用素材：图片 / 视频用素材 id，视频 clip 用 `<video_id>:<start>-<end>`（秒，与 `selected_clips` 对应）。Phase 8 的 composition agent 负责解析 `material_ref`：图片解析到 catalog entry 的 `local_path`，视频 clip 一律解析到 `selected_clips[].clip_path`（见下），不再使用视频的 `local_path`；主 agent 永远不直接碰 `local_path`。
- `selected_clips[].clip_path` 指向无音轨的片段文件，相对**工作区根**（不同于图片 / 视频 `local_path` 的 `harvest_page/` base）；Phase 6 的 `<video_id>:<start>-<end>` 引用对应的就是它。composition 嵌入视频时只用 `clip_path`。
- `semantic_description` 是结合话题 context 生成的叙事锚点描述（"适合用于说明 X 概念 / Y 论点"），而非纯粹的图像内容描述；Phase 6 的场景规划（`material_candidates`）和 Phase 8 的 composition agent 都依赖它做匹配决策。
- **`width` / `height` 必须透传**：图片由 harvester 抓取时记录；视频由 `video-download.py --harvest-dir` 通过 ffprobe 写入 manifest，构建 catalog 时直接搬过来。Phase 8 的 HyperFrames sub-agent 用这两个字段为每个素材容器设置正确的宽高比，**禁止猜或假设 16:9**。若个别素材缺失（旧 manifest、抓取失败），catalog 里写 `null` 而不是省略字段。
- `aspect_ratio`、`ratio_bucket`、`layout_affordance`、`focal_region` 是布局提示字段，优先由 Phase 5 根据 `width` / `height`、视觉分析和 topic context 写入；旧 catalog 缺失时，可按 `width / height` 推断。`ratio_bucket` 建议按 `r = width / height` 判定：`ultra-wide` / `strip` `r >= 2.4`；`wide` `1.20 <= r < 2.4`；`square-ish` `0.90 <= r < 1.20`；`tall` `0.50 <= r < 0.90`；`ultra-tall` `r < 0.50`。`tall` / `ultra-tall` 素材写入 `layout_affordance: ["viewport_reveal"]`，并提供 `focal_region`、start / mid / end 关键区域说明或 avoid-region。
- `layout_affordance` 只表示素材适合的展示方式，不等于最终 layout；composition 阶段根据旁白和 scene 需求自由决定呈现方式。可选值包括 `video_first`、`media_first`、`viewport_reveal`、`band`、`detail_callout`、`comparison_pair`、`comparison_sequence`。
- `focal_region` 使用归一化坐标 `{x, y, w, h, reason}` 描述关键区域或应避免遮挡的区域；它不是自动裁切命令，只用于 Phase 8 设计 reveal viewport、半透明文本浮层避让和 QA 检查。

**输出：** `extract_frames/<slug>/<video-name>/`、`vision_analyze/<slug>/`、`material-catalog.json`、`clips/`。

## 仅论文素材（`input_mode = "paper"` 且 `fetch_materials = false`）

Phase 4 被跳过，`harvest_page/manifest.json` 里只有 Phase 2 / Phase 3 写入的论文条目（`main-paper`，加上 Phase 3 解析的相关论文），没有 web 页面、视频和滚动录像。论文自己的 figure / table 是论文模式的**首选**素材，不因为不抓 web 素材而丢掉。流程与上文相同（抽帧 / 字幕步骤对论文 entry 是空操作：论文 entry 没有视频、没有 `selected_clips`），只有视觉分析一步按第 3 步的 Paper-origin 规则：带非空 caption 的 figure / table 直接用 caption 作为 `semantic_description`、`score: 8`，**不做视觉分析**；caption 缺失或为空的才跑 VLM。

布局提示字段按论文素材的特点处理：

- 论文图片都带 `width` / `height`（parse-pdf 用 PIL 实测写入 manifest），`aspect_ratio` / `ratio_bucket` 直接按上文的公式推导；个别缺失写 `null` 而不是省略字段。
- 论文里的表格常常很高（`tall` / `ultra-tall`）：`layout_affordance` 写 `["viewport_reveal"]`，与上文 tall 素材的规则一致。
- 跳过了视觉分析的条目没有 VLM 给出的焦点信息：`focal_region` 写 `null`（或按表格内容人工标注），不要编造。
