# Phase 5 — 素材理解与筛选（catalog）

## 输入

- `harvest_page/manifest.json`（Phase 4 产出且已做过尺寸 / 清晰度筛选；论文 entry 由 Phase 2 / Phase 3 写入）；
- `inputs.json`（用户来源输入、目标时长、语言、朝向，以及全局 / 阶段级 agent 与 model 要求）；
- `research-brief.md`（调研结果与证据）；
- `vision_analyze/topic-context.txt`（从用户输入和调研结果提炼的 summary，含叙事角度）；
- `catalog-instructions.md`（用户对素材理解 / 筛选的原话与额外要求，如有）；
- `fetch_materials = false` 时 Phase 4 跳过：标准模式下本 phase 也一起跳过；论文模式（`input_mode = "paper"`）下本 phase 照常进行，走委派包基础指令里的「仅论文素材」路径。

## 输出

- `material-catalog.json`（每条 harvest entry 对应一条 catalog entry，含图片 / 视频的 `id`、`semantic_description`、`selected_clips`，每个 clip 带 `clip_path`）；
- `clips/`（无音轨片段文件）；
- `extract_frames/<slug>/<video-name>/`；
- `vision_analyze/<slug>/`；
- `vision_analyze/topic-context.txt`。

## 完成判据

- `material-catalog.json` 存在、非空、JSON 可解析，`entries` 为非空列表；
- 每张图片 / 每个视频均有非空字符串 `id` 与 `semantic_description`；
- 每个 `selected_clip` 均有 `clip_path`，且对应文件（相对工作区根）存在且非空；
- `required_material_refs` 不重复且均可在本 catalog 内按 entry 解析（标准模式可选，论文模式必须显式声明，无适用关键图时写 `[]`）；
- `catalog-instructions.md` 可选：新增、修改或删除该文件不会自动触发重做，需重建时由主 agent 用 `--redo 5-material-catalog --reason "..."` 登记。

## 执行后自检

状态脚本校验结构、描述与切片文件后，由执行 agent 自检内容质量：

- `semantic_description` 基于实际画面说明讲解用途，而非照搬标语。
- 非必用素材适配度 `<7/10` 或偏题项已过滤，达标切题的通用素材尽量保留供下游场景优先选用；论文关键图 / 表（方法、模型结构、核心实验结果）一张不漏列入 `required_material_refs`（即使关掉网络抓取或评分偏低也不得静默省略；无图写 `[]`）。
- 视频已完成“粗看（每请求 ≤8 帧）→ 局部细看（每请求一张 ≤16 帧的 4×4 拼图，附源时间范围）”两步分析，`selected_clips` 边界有局部帧依据；长图、图表与滚动录像在有可见依据时标出了 `focal_region`（无依据置 `null`，禁编造坐标）。
- 论文条目区分非空 caption 复用与缺失 caption 的视觉分析。
- 只基于 Phase 4 筛选后的 manifest 构建，禁回原目录捡回已剔除素材；仍不可用的素材从 catalog 移除或退回 Phase 4 重做。

## 下一步

Phase 6（脚本与场景规划）：只通过 catalog 引用素材，不直接接触 `local_path`。

## 护栏

- **上屏素材必须可追溯到 `material-catalog.json`，且视频一律剥除音轨。** Phase 5 用 `scripts/cut-clips.py` 切出无音轨 `clip_path`（`-an`），下游只嵌入 `clip_path` 并在 `<video>` 加 `muted playsinline` 兜底，禁直接嵌入原视频 `local_path`。
- **无显式 VLM 配置不得跳过视觉分析。** `vision-analyze.py` 返回 `delegate_to_agent` 时，执行 agent 用自身多模态看图能力按返回的 `prompt` / `context` 完成分析（Mode 2）；指定模型不支持看图时先报告，禁静默换模型。

**素材引用格式（slug-qualified ref）：** 素材 `id` 保持文件 stem、仅在所属 entry 内唯一。Phase 6 起引用图片 / 视频必须写 `<slug>/<id>`，视频片段写 `<slug>/<video_id>:<start>-<end>`（裸 id 无效）；Phase 8 按 `slug` 定位 entry 后分别解析到图片的 `local_path` 与片段的 `selected_clips[].clip_path`。

---

本阶段按 `references/delegation/conventions.md` 统一委派（阶段级要求记 `inputs.json.delegation.catalog`，优先于默认值与环境 VLM 配置）。被委派的 catalog agent 从 handoff 读取输入，并按 manifest 访问实际媒体、字幕与论文 metadata。主 agent 执行四步：

1. **写话题 context 摘要**（200 字以内自然语言，含核心主题与叙事角度、目标受众与基调、3–5 个核心论点），保存至 `vision_analyze/topic-context.txt` 作为本阶段常量传入每次视觉分析。
2. **生成 handoff**：写妥 `inputs.json` 与可选 `catalog-instructions.md` 后，运行 `source .venv/bin/activate && python3 scripts/prepare-handoff.py {work_dir}/{topic_name} catalog` 生成 `catalog-handoff.md`。
3. **派发**：按返回 JSON 的 `coding_agent` / `coding_model` 原样派发单句 `dispatch_prompt`。
4. **验收**：运行 `python3 scripts/pipeline-status.py {work_dir}/{topic_name}`；若 `next_phase` 仍为 Phase 5 且 `reason` 为 `missing` / `corrupt`，将 `next_phase.problems` 原样交回 catalog agent 修复。

未指定 agent / model 且环境既无原生委派工具也无法运行目标 CLI 时，主 agent 自行阅读 `references/delegation/catalog/base-instructions.md`，逐条处理 manifest entry 并增量写入 `material-catalog.json`。
