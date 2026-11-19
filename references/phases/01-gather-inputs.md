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
| `delegation` | 可选，阶段级 agent / model 要求。对象的键为 `catalog` / `script` / `composition` / `cover`，各值只含 `agent` 和 / 或 `model`（非空字符串）；如 `{"catalog": {"agent": "pi-coding-agent", "model": "<provider>/<model-id>"}}`。未指定 agent 时继承 `coding_agent`，未指定 model 时使用目标 agent 自身的模型配置；用户点名时严格遵循，未提就不填 |
| `fetch_materials` | 是否联网抓取视觉素材（布尔，默认 `true`；用户明确不要素材时写 `false`） |
| `approval_gates` | 可选，默认 `[]`（全自动、不停下来审稿）；不主动询问是否审稿。用户要求审稿时按入口的表填：只看调研用 `["research-brief"]`，只看旁白用 `["script"]`，只说“中途让我审稿”就两处都填。续跑保留已有要求，用户明确改才动 |
| `narration_requests` | 可选，字符串列表，默认不填。用户对旁白提出的长期要求（“语气更口语”“结尾不要 CTA”），逐条用他的原话记下；Phase 6 委派前读它 |
| `composition_requests` | 可选，字符串列表，默认不填。用户对画面与视觉风格提出的长期要求（“强调方法图”“不要人物区”“用 github 主题”“仅第 2 场用深色科技风”），逐条用原话记下；Phase 8 委派前读它 |
| `cover_requests` | 可选，字符串列表，默认不填。用户对视频封面提出的长期要求（“只发小红书竖版”“封面只要 1920x1080”“封面主推成本降幅数字”），逐条用原话记下；Phase 11 委派前读它 |
| `material_search_requests` | 可选，字符串列表，默认不填。用户点名要用某个平台找素材（“去 Google 图片搜某产品的界面”“在 B 站找演示视频”）时，把原话逐条记下；Phase 4 读它。它只是记录，不会自动让素材阶段重做：用户新提或修改这类要求时，另按 `references/pipeline-control.md` 登记 Phase 4 重做。不主动要求平台搜索 |
| `qa_level` | 可选，渲染后 QA 档位：`quick` / `standard`（缺省）/ `strict`。只按用户明确要求写，不主动问；三档的完整流程见 Phase 9 |
| `bgm` | 可选，是否混入背景音乐（布尔，缺省 `true`）；仅在用户明确要求不要背景音乐 / BGM 时写 `false`（跳过 Phase 10，直接交付 `final.mp4`）。只按用户明确要求写，不主动问 |
| `cover` | 可选，是否生成视频封面（布尔，缺省 `true`）；仅在用户明确要求不要封面时写 `false`（跳过 Phase 11）。只按用户明确要求写，不主动问 |

## 完成判据

`inputs.json` 存在、非空、JSON 可解析，且上表非可选字段齐全（`fetch_materials` 必须是布尔；`duration` 必须是分钟数；`orientation` 必须是三个规范朝向之一；`qa_level`、`bgm`、`cover`、`approval_gates`、`narration_requests`、`composition_requests`、`cover_requests`、`material_search_requests` 和 `delegation` 都可缺省，填写时按上表类型校验）。

## 执行后自检

写入前核对（格式与类型由 `pipeline-status` 校验）：

- 用户提过的来源、时长、语言、朝向、风格、素材、BGM、封面与审稿要求均已落入对应字段；未提项使用上表默认值，不臆测编造。
- 用户原话完整分流：旁白要求记 `narration_requests`，画面要求记 `composition_requests`，封面要求记 `cover_requests`，指定平台找素材记 `material_search_requests`，素材理解 / 筛选要求记 `catalog-instructions.md`，阶段级 agent / model 要求记 `delegation`（同一要求不重复记两处）。
- 缺少默认值且无法开工的关键歧义（如只说“做个短视频”但看不出主题重点）或互相冲突的要求，先向用户提问（一次只问一个）。

修改 `inputs.json` 后重跑状态脚本，并按已知修改范围用 `--redo` 显式登记受影响的下游阶段。

## 下一步

跑 `python3 scripts/pipeline-status.py {work_dir}/{topic_name}` 确认下一个 phase：论文模式（`input_mode = "paper"`）进 Phase 2（解析论文），其余直接进 Phase 3（调研）。

## 护栏

- **先读已有需求，能默认的不问。** 仅在缺乏可默认的关键信息或用户要求冲突时提问（一次一问），不重问用户已说明的参数，也不把字段表当问卷逐项确认。
- **用户原话必须落盘，不只留在对话或 Scratchpad。** 下游 agent 只读工作区文件，不回看当前对话。
- **外观主题（design）、模板和字幕排版归 Phase 8 决定。** 本阶段只把视觉风格要求记入 `composition_requests`，不预选主题，也不为迁就某个模板提前改叙事、时长或朝向。

---

按下面的要点把输入集齐：

1. **朝向细分**：默认横屏 `landscape`（`1920×1080`）；用户只说“竖屏”未指定比例时写 `portrait-3:4`（`1080×1440`），明确要求 9:16 时才写 `portrait`（`1080×1920`）。
2. **视觉素材**：默认 `fetch_materials = true`（联网搜索）；用户明确不要素材时写 `false`（论文模式即使不联网搜索，论文自己的关键图也照样进视频）。用户点名要在某个平台找素材时，把原话记进 `material_search_requests`；没提就不加。
3. **旁白、画面、背景乐与封面的额外要求**：用户对旁白说的（“语气更口语”“结尾不要 CTA”）进 `narration_requests`；对画面、视觉风格、配色或主题说的（“强调实验对比图”“不要人物区”“全片用 github 风格”“仅第 2 场用深色科技风”）原话进 `composition_requests`，由 Phase 8 按 `modules/designs/designs.md` 处理；对封面说的（指定发布平台、封面尺寸或钩子重点）原话进 `cover_requests`，由 Phase 11 处理；明确说不要背景音乐 / BGM 时置 `bgm = false`，明确说不要封面时置 `cover = false`（没提就不填，默认开启）。同一件事不要两处都记。
4. **审稿**：默认不审稿（`approval_gates` 为 `[]`）。只有用户明确要求时才填 `research-brief` / `script`，不主动询问。
5. **输入类型识别：**
   - 来源是 `.pdf` 文件路径 → 置 `input_mode = "paper"`
   - 来源是以 `.pdf` 结尾的 URL（例如 arXiv） → 置 `input_mode = "paper"`，并将该 URL 保留用于 `parse-pdf.py --url`
   - 否则 → 置 `input_mode = "standard"`（默认；后续所有 "paper mode" 段落都跳过）

**如果用户要求沿用另一个项目的风格**（例如“用和 `xxx-video/` 一样的风格”），读取目标项目的 `composition/design.json`，将对应主题或风格要求整理写入本项目的 `composition_requests`。

落盘 `inputs.json` 后运行 `python3 scripts/pipeline-status.py {work_dir}/{topic_name}` 进入下一阶段。
