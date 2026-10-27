# Phase 5 — 素材理解与筛选（catalog）

## 输入

`harvest_page/manifest.json`（Phase 4 产出；论文 entry 由 Phase 2 / Phase 3 写入）+ `research-brief.md`（提炼话题 context 摘要）。`fetch_materials = false` 时 Phase 4 跳过：标准模式下本 phase 也一起跳过；论文模式（`input_mode = "paper"`）下本 phase 照常进行，走委派包基础指令里的「仅论文素材」路径。

## 输出

`material-catalog.json`（每条 harvest entry 对应一条 catalog entry，含图片 / 视频的 `id`、`semantic_description`、`selected_clips`，每个 clip 带 `clip_path`）+ `clips/`（无音轨片段文件）+ `extract_frames/<slug>/<video-name>/` + `vision_analyze/<slug>/` + `vision_analyze/topic-context.txt`。

## 完成判据

`material-catalog.json` 存在、非空、JSON 可解析，`entries` 为非空列表；每张图片 / 每个视频都有非空字符串的 `id` 和 `semantic_description`（VLM 评分 <5 或偏题的素材已过滤）；每个 `selected_clip` 都有 `clip_path`，且它指向的文件（相对工作区）存在且非空；状态脚本会逐项检查。

## 下一步

Phase 6（脚本与场景规划）：旁白与场景规划只引用本 phase 产出的 catalog，不直接接触素材 `local_path`。

## 护栏

- **每个资源都能追溯到 `material-catalog.json`。** 没有 catalog 引用 → 屏幕上不出现该资源。**视频材料一律剥音轨**：Phase 5 用 `scripts/cut-clips.py` 把每个 `selected_clip` 切成无音轨文件（`clip_path`，`-an`），composition 只用这些文件；Phase 8 HTML 嵌入时 `<video>` 标签必须带 `muted playsinline` 兜底。
  ↳ DO NOT：嵌入整段原视频或视频的 `local_path`；切片段时不带 `-an`；`<video>` 漏 `muted`。
- 历史坑见 `references/gotchas.md` #8（`vision-analyze.py` 返回 `delegate_to_agent`）。

**素材引用采用方案 A（slug-qualified ref）。** 素材 `id` 保持 harvester 写出的文件 stem，只在所属 entry 内唯一，不改 harvester / manifest 的 id。Phase 6 的图片 / 视频 ref 必须写成 `<slug>/<id>`，视频 clip 必须写成 `<slug>/<video_id>:<start>-<end>`；`slug` 是 `entries[*].slug`，解析时只查该 entry。两个 entry 可以各有 `img_001`，同一个 video id 也可以出现在多个 entry，它们由不同 slug 明确区分；裸 id 不是有效 ref。Phase 8 按同一契约把图片解析到该 entry 的 `local_path`，把 clip 解析到该 entry 的 `selected_clips[].clip_path`。

---

**优先委派给 coding agent。** 本阶段 context 消耗大（要对很多图片 / 帧做视觉分析，30-50+ 次工具调用）。按 `references/delegation/conventions.md` 的统一委派约定派发（默认 claude-code，派发 prompt 一句话，让被委派的 agent 自己读输入）。主 agent 只做四件事：

1. **写话题 context 摘要。** 在开始视觉分析之前，主 agent 先从当前 context（研究 brief、用户输入、叙事角度）提炼一份**话题 context 摘要**，供所有视觉分析调用使用。摘要为自然语言，200 字以内，包含：
   - 视频的核心主题与叙事角度（"这是一段关于 X 的中文解说视频，重点讲解 Y 和 Z"）
   - 目标受众与风格基调
   - 3-5 个核心论点或关键概念（供 VLM 判断图片能"说明"哪个论点）

   这份摘要在整个 Phase 5 中作为常量传入每次视觉分析，写到 `vision_analyze/topic-context.txt` 备查。
2. **生成 handoff。** 运行 `source .venv/bin/activate && python3 scripts/prepare-handoff.py {work_dir}/{topic_name} catalog`。它把委派约定和 catalog 委派包物化到工作区（不复制 modules、不安装字体），生成路径全为绝对路径的 `catalog-handoff.md`。
3. **派发。** 把输出 JSON 里的 `dispatch_prompt` 原样派发，派发方式见 `references/delegation/conventions.md`。
4. **验收。** catalog agent 返回后运行 `python3 scripts/pipeline-status.py {work_dir}/{topic_name}`。`next_phase` 仍是 Phase 5 且 `reason` 为 `missing` / `corrupt` 时，把 `next_phase.problems` 原样交给 catalog agent 修复，修完再验收；主 agent 只读最终的 catalog。

如果当前环境没有 sub-agent 工具，主 agent 自己阅读 `references/delegation/catalog/base-instructions.md`，一次处理一条 manifest entry，逐条执行并增量写入 `material-catalog.json`，以控制 context。
