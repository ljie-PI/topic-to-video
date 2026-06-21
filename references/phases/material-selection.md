### Phase 4 — 素材理解与筛选

**优先委派给 sub-agent。** 本阶段 context 消耗大（要对很多图片 / 帧做视觉分析，30-50+ 次工具调用）。可用时使用当前 runtime 原生的 sub-agent / 委派工具，把 manifest 路径、研究 brief、**话题 context 摘要**和这份阶段文档交给它；它产出 `material-catalog.json`。主 agent 只读最终的 catalog。

如果当前环境没有 sub-agent 工具，可以 inline 跑这一阶段，但要把 context 控制住：一次处理一条 manifest 条目，把结果增量写进 `material-catalog.json`。

#### 话题 context 摘要

在开始视觉分析之前，主 agent 先从当前 context（研究 brief、用户输入、叙事角度）提炼一份**话题 context 摘要**，供所有视觉分析调用使用。摘要为自然语言，200 字以内，包含：

- 视频的核心主题与叙事角度（"这是一段关于 X 的中文解说视频，重点讲解 Y 和 Z"）
- 目标受众与风格基调
- 3-5 个核心论点或关键概念（供 VLM 判断图片能"说明"哪个论点）

这份摘要在整个 Phase 4 中作为常量传入每次视觉分析，写到 `vision_analyze/topic-context.txt` 备查。如果委派给 sub-agent，把摘要内容直接写进委派 prompt。

遍历 Phase 3 产出的 `harvest_page/manifest.json["entries"]`。对每一条 entry，在 `{work_dir}/{topic_name}/material-catalog.json` 里建一个 "material entry"。

**每一条 harvest entry（每个 URL 一条）：**

1. **抽帧**：对 `entry.videos` 里的每个视频，以及 `entry.scroll_recording`（如果有）：
   ```bash
   scripts/extract-frames.py <video> \
     {work_dir}/{topic_name}/extract_frames/<slug>/<video-name>/ \
     --max-frames 16
   ```
   帧文件名带时间戳（如 `frame_t00.5s.jpg`），可以反向映射到 clip 区间。

2. **解析字幕**：对每个带 sidecar 字幕文件的已下载视频：
   ```bash
   scripts/subtitle-parse.py <subtitle> --keywords '<terms from research brief>'
   ```

3. **视觉分析**：用 `scripts/vision-analyze.py`，传入 `--context-file vision_analyze/topic-context.txt`：
   - 对图片（光栅图和 SVG）：按 URL 聚合图片，每次调用最多放 10 张；同一 URL 超过 10 张时拆成多个 batch，且共享同一话题 context 摘要。prompt 询问"这张图在讲解该话题时可以用来说明什么论点或概念"、视觉风格、1-10 的适配度评分，并根据 `width` / `height` 和画面内容给出布局能力提示：是否适合 `media_first`、`viewport_reveal`、`band`、`detail_callout`、`comparison_pair` 等。对极端比例素材，尽量指出明显的关键区域 / avoid-region；若可行，用 0-1 归一化坐标写入 `focal_region`。
   - 对每个视频：一个 batch 跑在抽出的帧上。prompt 额外询问最相关片段的起止时间戳，以及该片段适合说明话题的哪个方面；同时判断该 clip 是否适合 `video_first`、`viewport_reveal`、`comparison_pair` 或 `comparison_sequence`，并指出关键动作 / UI 区域或应避免遮挡的区域。
   - **Mode 1（显式 VLM）：** 若已设置 `VLM_API_KEY` + `VLM_BASE_URL` + `VLM_MODEL` → 直接走 OpenAI 兼容的调用，话题 context 摘要作为 system prompt 或 user prompt 前缀注入。
   - **Mode 2（主 agent 直接分析）：** 否则 → 脚本返回 `delegate_to_agent` 和图片路径列表。此时由**主 agent 自身的多模态视觉能力**（Read 图片文件，让模型直接看图）完成分析——使用与主 agent 其他推理相同的模型，不调用任何外部工具。分析时把话题 context 摘要带入 prompt，与 Mode 1 保持一致，产出同样格式的 `semantic_description` 和 `score`，并手动写入 `material-catalog.json`。

   **Paper-origin entries（`source_type: "paper_pdf"`）：** 直接把 PDF caption（`paper_metadata.figure_captions` / `table_captions`）作为 `semantic_description`，默认 `score: 8`。只对没有 caption 的论文素材跑 VLM。

4. **组合**：把 `entry.text_excerpt` + 图片描述 + 各帧描述合成 catalog entry。**关键：** 对每个视频，写一份 `selected_clips` 列表，元素形如 `{start, end, reason, frame_paths[]}` —— 这些就是 Phase 5（脚本与场景-素材匹配）和 Phase 8（composition）会引用的片段。

5. **过滤：** 丢掉 VLM 评分 <5/10 或者偏题的素材。不要把垃圾带进解说阶段。

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
          "local_path": ".../images/img_001.webp",
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
          "local_path": ".../videos/2MJDdzSXL74.webm",
          "width": 1920, "height": 1080,
          "aspect_ratio": 1.7778,
          "ratio_bucket": "wide",
          "layout_affordance": ["video_first", "comparison_sequence"],
          "focal_region": {"x": 0.12, "y": 0.18, "w": 0.74, "h": 0.62, "reason": "关键 UI 操作区域"},
          "duration_seconds": 312.4,
          "semantic_description": "...",
          "selected_clips": [
            {"start": 12.0, "end": 18.5, "reason": "...", "frame_paths": [...]}
          ]
        }
      ]
    }
  ]
}
```

- `entries[*].slug` 在每个 URL 上唯一，与 harvest 输出目录名一致。
- 每张图 / 每个视频都带一个 `id`（harvester 写出的文件 stem，例如 `img_001` 或 YouTube video id）。Phase 5.2 起通过 **`material_ref`** 引用素材，并在 `scene-material-suggestions.json` 中定义具体引用格式。Phase 8 的 coding sub-agent 负责把 `material_ref` 解析成 catalog entry → `local_path`；主 agent 永远不直接碰 `local_path`。
- `semantic_description` 是结合话题 context 生成的叙事锚点描述（"适合用于说明 X 概念 / Y 论点"），而非纯粹的图像内容描述；Phase 5.2 的场景-素材匹配、Phase 5.3 的屏幕文本块规划和 Phase 8 的 HyperFrames sub-agent 都依赖它做匹配决策。Phase 5.3 会参考已匹配素材的 `semantic_description`，为截图 / figure / table 生成外置信息区、解释 callout 或 data block，但不得要求 Phase 8 用前景文本覆盖素材主体。
- **`width` / `height` 必须透传**：图片由 harvester 抓取时记录；视频由 `video-download.py` + `apply-video-download-result.py` 通过 ffprobe 写入 manifest，构建 catalog 时直接搬过来。Phase 8 的 HyperFrames sub-agent 用这两个字段为每个素材容器设置正确的宽高比，**禁止猜或假设 16:9**。若个别素材缺失（旧 manifest、抓取失败），catalog 里写 `null` 而不是省略字段；下游应当回退到 ffprobe 实测或居中适配，并在 `composition/DESIGN.md` 中标注。
- `aspect_ratio`、`ratio_bucket`、`layout_affordance`、`focal_region` 是布局提示字段，优先由 Phase 4 根据 `width` / `height`、视觉分析和 topic context 写入；旧 catalog 缺失时，下游可按 `width / height` 推断并在 `composition/DESIGN.md` 标注。建议 bucket：`wide`、`tall`、`square-ish`、`ultra-wide`、`ultra-tall`、`strip`。
- `layout_affordance` 只表示素材适合的展示方式，不等于最终 layout；Phase 5.2 根据旁白和全局 scene 需求选择 `layout_role`。可选值包括 `video_first`、`media_first`、`media_continuation`、`viewport_reveal`、`band`、`detail_callout`、`comparison_pair`、`comparison_sequence`。
- `focal_region` 使用归一化坐标 `{x, y, w, h, reason}` 描述关键区域或应避免遮挡的区域；它不是自动裁切命令，只用于 Phase 8 设计 reveal viewport、半透明文本浮层避让和 QA 检查。

**输出：** `extract_frames/<slug>/<video-name>/`、`vision_analyze/<slug>/`、`material-catalog.json`。
