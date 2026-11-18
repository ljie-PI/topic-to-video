# Phase 1 — 收集输入

## 输入

用户在对话中给出的需求：主题、文章 URL、粘贴的文本或论文 PDF / URL，以及他明确说过的其他要求（时长、语言、朝向、风格、素材、要不要审稿）。

先把这些需求读全，再动手写 `inputs.json`：已经说过的就不要重复问，没说的用下表的默认值。

## 输出

`inputs.json`（工作区根目录）。字段：

| 字段 | 说明 |
| --- | --- |
| `source` | 来源：要抓取的 URL、粘贴的文本，或仅一个主题 |
| `input_mode` | `standard`（默认）/ `topic` / `article` / `text` / `paper`（论文模式） |
| `duration` | 目标时长，单位分钟，写成数字（默认 `3`）；也接受数字加分钟单位的字符串（`"5min"`、`"5 分钟"`）。用户说了就照他说的，不自行设上下限。`"90秒"`、`"1h"`、`"3-5分钟"` 这类写法不接受，会被判为损坏 |
| `language` | 解说语言，默认中文 |
| `orientation` | `landscape`（横屏 1920×1080）/ `portrait`（竖屏 1080×1920，仅显式 9:16）/ `portrait-3:4`（1080×1440，默认竖屏） |
| `coding_agent` | 全局委派目标；默认值与命令以 `references/delegation/conventions.md` 的统一约定为准 |
| `delegation` | 可选，阶段级 agent / model 要求。对象的键为 `catalog` / `script` / `composition`，各值只含 `agent` 和 / 或 `model`（非空字符串）；如 `{"catalog": {"agent": "pi-coding-agent", "model": "<provider>/<model-id>"}}`。未指定 agent 时继承 `coding_agent`，未指定 model 时使用目标 agent 自身的模型配置；用户点名时严格遵循，未提就不填 |
| `fetch_materials` | 是否联网抓取视觉素材（布尔） |
| `approval_gates` | 可选，默认 `[]`（全自动、不停下来审稿）；不主动询问是否审稿。用户要求审稿时按入口的表填：只看调研用 `["research-brief"]`，只看旁白用 `["script"]`，只说“中途让我审稿”就两处都填。续跑保留已有要求，用户明确改才动 |
| `narration_requests` | 可选，字符串列表，默认不填。用户对旁白提出的长期要求（“语气更口语”“结尾不要 CTA”），逐条用他的原话记下；Phase 6 委派前读它 |
| `composition_requests` | 可选，字符串列表，默认不填。用户对画面与视觉风格提出的长期要求（“强调方法图”“不要人物区”“用 github 主题”“仅第 2 场用深色科技风”），逐条用原话记下；Phase 8 委派前读它 |
| `material_search_requests` | 可选，字符串列表，默认不填。用户点名要用某个平台找素材（“去 Google 图片搜某产品的界面”“在 B 站找演示视频”）时，把原话逐条记下；Phase 4 读它。它只是记录，不会自动让素材阶段重做：用户新提或修改这类要求时，另按 `references/pipeline-control.md` 登记 Phase 4 重做。不主动要求平台搜索 |
| `qa_level` | 可选，渲染后 QA 档位：`quick` / `standard`（缺省）/ `strict`。只按用户明确要求写，不主动问；三档的完整流程见 Phase 9 |
| `bgm` | 可选，是否混入背景音乐（布尔，缺省 `true`）；仅在用户明确要求不要背景音乐 / BGM 时写 `false`（跳过 Phase 10，直接交付 `final.mp4`）。只按用户明确要求写，不主动问 |

## 完成判据

`inputs.json` 存在、非空、JSON 可解析，且上表非可选字段齐全（`fetch_materials` 必须是布尔；`duration` 必须是分钟数；`orientation` 必须是三个规范朝向之一；`qa_level`、`bgm`、`approval_gates`、`narration_requests`、`composition_requests`、`material_search_requests` 和 `delegation` 都可缺省，填写时按上表类型校验）。

## 执行后自检

写入前核对（格式与类型由 `pipeline-status` 校验）：

- 用户提过的来源、时长、语言、朝向、风格、素材与审稿要求均已落入对应字段；未提项使用上表默认值，不臆测编造。
- 用户原话完整分流：旁白要求记 `narration_requests`，画面要求记 `composition_requests`，指定平台找素材记 `material_search_requests`，素材理解 / 筛选要求记 `catalog-instructions.md`，阶段级 agent / model 要求记 `delegation`（同一要求不重复记两处）。
- 缺少默认值且无法开工的关键歧义（如只说“做个短视频”但看不出主题重点）或互相冲突的要求，先向用户提问（一次只问一个）。

修改 `inputs.json` 后重跑状态脚本，并按已知修改范围用 `--redo` 显式登记受影响的下游阶段。

## 下一步

跑 `python3 scripts/pipeline-status.py {work_dir}/{topic_name}` 确认下一个 phase：论文模式（`input_mode = "paper"`）进 Phase 2（解析论文），其余直接进 Phase 3（调研）。

## 护栏

- **先读已有需求，能默认的不问。** 仅在缺乏可默认的关键信息或用户要求冲突时提问（一次一问），不重问用户已说明的参数，也不把字段表当问卷逐项确认。
- **用户原话必须落盘，不只留在对话或 Scratchpad。** 下游 agent 只读工作区文件，不回看当前对话。
- **外观主题（design）、模板和字幕排版归 Phase 8 决定。** 本阶段只把视觉风格要求记入 `composition_requests`，不预选主题，也不为迁就某个模板提前改叙事、时长或朝向。

---

**特殊输入与跨项目风格处理：**

1. **朝向细分**：默认横屏 `landscape`（`1920×1080`）；用户只说“竖屏”未指定比例时写 `portrait-3:4`（`1080×1440`），明确要求 9:16 时才写 `portrait`（`1080×1920`）。
2. **输入模式识别（`input_mode`）**：
   - 来源是本地 `.pdf` 路径，或以 `.pdf` 结尾的 URL（如 arXiv PDF）→ 置 `input_mode = "paper"`（保留 PDF URL 供 `parse-pdf.py --url` 使用）；论文模式即使 `fetch_materials = false`，论文自身的关键图表仍进入视频；
   - 其他来源 → 默认 `input_mode = "standard"`（后续跳过所有论文专属步骤）。
3. **沿用其他项目风格**（如“用和 `xxx-video/` 一样的风格”）：读取目标项目的 `composition/design.json`，将对应主题或风格要求整理写入本项目的 `composition_requests`；本项目最终外观仍由 Phase 8 落盘为 `composition/design.json`。

落盘 `inputs.json` 后运行 `python3 scripts/pipeline-status.py {work_dir}/{topic_name}` 进入下一阶段。
