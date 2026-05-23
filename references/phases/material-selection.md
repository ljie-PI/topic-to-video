### Phase 4 — 素材理解与筛选

**优先委派给 sub-agent。** 本阶段 context 消耗大（要对很多图片 / 帧做视觉分析，30-50+ 次工具调用）。可用时使用当前 runtime 原生的 sub-agent / 委派工具，把 manifest 路径、研究 brief 和这份阶段文档交给它；它产出 `material-catalog.json`。主 agent 只读最终的 catalog。

如果当前环境没有 sub-agent 工具，可以 inline 跑这一阶段，但要把 context 控制住：一次处理一条 manifest 条目，把结果增量写进 `material-catalog.json`。

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

3. **视觉分析**：用 `scripts/vision-analyze.py`：
   - 对图片（光栅图和 SVG）：每个 URL 一个 batch（每次调用最多 10 张）。prompt 询问 subject、视觉风格、1-10 的适配度评分。
   - 对每个视频：一个 batch 跑在抽出的帧上。prompt 额外询问最相关片段的起止时间戳。
   - **Mode 1（显式 VLM）：** 若已设置 `VLM_API_KEY` + `VLM_BASE_URL` + `VLM_MODEL` → 直接走 OpenAI 兼容的调用。
   - **Mode 2（委派）：** 否则 → 脚本返回 `delegate_to_agent` 和图片路径列表；agent 用自己的 `view` 工具看图。

   **Paper-origin entries（`source_type: "paper_pdf"`）：** 论文里的 figure 和 table 在 PDF 中本就带有权威的 caption（位于 `paper_metadata.figure_captions` / `table_captions`）。直接把这些 caption 作为 `semantic_description`，默认 `score: 8`。只对没有 caption 的论文素材跑 VLM。

4. **组合**：把 `entry.text_excerpt` + 图片描述 + 各帧描述合成 catalog entry。**关键：** 对每个视频，写一份 `selected_clips` 列表，元素形如 `{start, end, reason, frame_paths[]}` —— 这些就是 Phase 5（解说）和 Phase 8（composition）会引用的片段。

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
        {"id": "img_001", "local_path": ".../images/img_001.webp", "semantic_description": "...", "score": 8}
      ],
      "videos": [
        {
          "id": "2MJDdzSXL74",
          "local_path": ".../videos/2MJDdzSXL74.webm",
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
- 每张图 / 每个视频都带一个 `id`（harvester 写出的文件 stem，例如 `img_001` 或 YouTube video id）。Phase 5/7/8 通过 **`material_ref`** 引用素材——schema 在 Phase 7 中首次定义时给出。Phase 8 的 coding sub-agent 负责把 `material_ref` 解析成 catalog entry → `local_path`；主 agent 永远不直接碰 `local_path`。
- `semantic_description` 是 VLM 生成的 caption；Phase 8 的 HyperFrames sub-agent 用它做 composition 决策。

**输出：** `extract_frames/<slug>/<video-name>/`、`vision_analyze/<slug>/`、`material-catalog.json`。
