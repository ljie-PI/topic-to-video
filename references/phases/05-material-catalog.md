# Phase 5 — 素材理解与筛选（catalog）

## 输入

- `harvest_page/manifest.json`（Phase 4 产出；论文 entry 由 Phase 2 / Phase 3 写入）；
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
- 每张图片 / 每个视频都有非空字符串的 `id` 和 `semantic_description`（适配度评分 <7 或偏题的素材已过滤）；
- 每个 `selected_clip` 都有 `clip_path`，且它指向的文件（相对工作区）存在且非空；
- 状态脚本检查结构、描述与文件；评分、相关性和片段内容由执行 agent 自检，不由状态脚本判定。
- `catalog-instructions.md` 是可选上游输入：生成 catalog 后新增、修改或删除该文件，状态脚本会将本阶段标为 `stale`，并暂停下游；缺省时不要求创建该文件。旧戳首次补齐新增依赖时沿用兼容规则，不强制重做，之后的文件变化照常判为过期。

## 执行后自检

`pipeline-status` 会逐项检查引用、描述、`clip_path`。此外由委派的 catalog agent 自己（或主 agent 兜底时）判断：

- 每条 `semantic_description` 是否真的描述了这张图 / 这段画面，而不是照标语。
- 打分是否过低（<7 / 10；量表见委派包基础指令）却仍留在 catalog 里，或者高质量的却漏掉了。
- 视频是否按“粗看每请求最多 8 帧 → 局部细看每请求一张最多 16 帧的 4×4 拼图”完成分析；拼图 prompt 是否附源时间范围，`selected_clips` 的起止是否有局部帧依据，真的落在关键动作 / 界面的那几秒，而不是只用粗帧估计。
- 论文条目是否按 caption 规则处理，缺失 caption 的是否跑了视觉分析。

## 下一步

Phase 6（脚本与场景规划）：旁白与场景规划只引用本 phase 产出的 catalog，不直接接触素材 `local_path`。

## 护栏

- **每个资源都能追溯到 `material-catalog.json`。** 没有 catalog 引用 → 屏幕上不出现该资源。**视频材料一律剥音轨**：Phase 5 用 `scripts/cut-clips.py` 把每个 `selected_clip` 切成无音轨文件（`clip_path`，`-an`），composition 只用这些文件；Phase 8 HTML 嵌入时 `<video>` 标签必须带 `muted playsinline` 兜底。
  ↳ DO NOT：嵌入整段原视频或视频的 `local_path`；切片段时不带 `-an`；`<video>` 漏 `muted`。
- **没有 VLM 配置不是跳过视觉分析的理由。** `vision-analyze.py` 返回 `delegate_to_agent` 时，由执行 agent 用自身的看图能力按返回的 `prompt` / `context` 完成分析（委派包基础指令的 Mode 2），照样写 `semantic_description` 和 `score`；用户选择显式 VLM 路径时再按要求配置。指定模型无法完成看图时先说明，不用另一个模型代替。

**素材引用采用方案 A（slug-qualified ref）。** 素材 `id` 保持 harvester 写出的文件 stem，只在所属 entry 内唯一，不改 harvester / manifest 的 id。Phase 6 的图片 / 视频 ref 必须写成 `<slug>/<id>`，视频 clip 必须写成 `<slug>/<video_id>:<start>-<end>`；`slug` 是 `entries[*].slug`，解析时只查该 entry。两个 entry 可以各有 `img_001`，同一个 video id 也可以出现在多个 entry，它们由不同 slug 明确区分；裸 id 不是有效 ref。Phase 8 按同一契约把图片解析到该 entry 的 `local_path`，把 clip 解析到该 entry 的 `selected_clips[].clip_path`。

---

**用户指定本阶段的 agent / model 时必须严格遵循；未指定时优先委派给 pi-coding-agent（命令 `pi`）。** 本阶段需要对多张图片 / 视频帧做视觉分析。按 `references/delegation/conventions.md` 的统一约定派发；素材理解 / 素材匹配的阶段级要求记入 `inputs.json.delegation.catalog`，不能被全局默认值或已有 VLM 配置覆盖。派发 prompt 保持一句话，被委派的 catalog agent 从 handoff 读取上述输入，并按 manifest 路径读取实际图片、视频、字幕与论文 metadata，不只看素材清单。主 agent 做四件事：

1. **写话题 context 摘要。** 在开始视觉分析之前，主 agent 先从当前 context（研究 brief、用户输入、叙事角度）提炼一份**话题 context 摘要**，供所有视觉分析调用使用。摘要为自然语言，200 字以内，包含：
   - 视频的核心主题与叙事角度（"这是一段关于 X 的中文解说视频，重点讲解 Y 和 Z"）
   - 目标受众与风格基调
   - 3-5 个核心论点或关键概念（供 VLM 判断图片能"说明"哪个论点）

   这份摘要在整个 Phase 5 中作为常量传入每次视觉分析，写到 `vision_analyze/topic-context.txt` 备查。
2. **生成 handoff。** 先把阶段级 agent / model 要求写入 `inputs.json`，用户对素材的额外要求写入 `catalog-instructions.md`（如有），再运行 `source .venv/bin/activate && python3 scripts/prepare-handoff.py {work_dir}/{topic_name} catalog`。它把委派约定和 catalog 委派包物化到工作区（不复制 modules、不安装字体），生成路径全为绝对路径的 `catalog-handoff.md`。
3. **派发。** 用输出 JSON 里的 `coding_agent` / `coding_model` 选择实际 agent / model，把 `dispatch_prompt` 原样派发，方式见 `references/delegation/conventions.md`。
4. **验收。** catalog agent 返回后运行 `python3 scripts/pipeline-status.py {work_dir}/{topic_name}`。`next_phase` 仍是 Phase 5 且 `reason` 为 `missing` / `corrupt` 时，把 `next_phase.problems` 原样交给 catalog agent 修复，修完再验收；主 agent 只读最终的 catalog。

未指定 agent / model 且环境既不能原生委派也不能运行目标 CLI 时，主 agent 自己阅读 `references/delegation/catalog/base-instructions.md`，一次处理一条 manifest entry，逐条执行并增量写入 `material-catalog.json`，以控制 context。
