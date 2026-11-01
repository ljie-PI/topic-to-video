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
| `design` | 所选 design：`default` / `github` / `producthunt`，对应 `modules/designs/<design>/<design>.md` |
| `coding_agent` | 委派目标，默认 `pi-coding-agent`（命令 `pi`） |
| `fetch_materials` | 是否联网抓取视觉素材（布尔） |
| `approval_gates` | 可选，默认 `[]`（全自动、不停下来审稿）；不主动询问是否审稿。用户要求审稿时按入口的表填：只看调研用 `["research-brief"]`，只看旁白用 `["script"]`，只说“中途让我审稿”就两处都填。续跑保留已有要求，用户明确改才动 |
| `narration_requests` | 可选，字符串列表，默认不填。用户对旁白提出的长期要求（“语气更口语”“结尾不要 CTA”），逐条用他的原话记下；Phase 6 委派前读它 |
| `composition_requests` | 可选，字符串列表，默认不填。用户对画面提出的长期要求（“强调方法图”“不要人物区”），逐条记下；Phase 8 委派前读它 |
| `material_search_requests` | 可选，字符串列表，默认不填。用户点名要用某个平台找素材（“去 Google 图片搜某产品的界面”“在 B 站找演示视频”）时，把原话逐条记下；Phase 4 读它。它只是记录，不会自动让素材阶段重做：用户新提或修改这类要求时，另按 `references/pipeline-control.md` 登记 Phase 4 重做。不主动要求平台搜索 |
| `qa_level` | 可选，渲染后 QA 档位：`quick` / `standard`（缺省）/ `strict`。只按用户明确要求写，不主动问；三档的完整流程见 Phase 9 |

## 完成判据

`inputs.json` 存在、非空、JSON 可解析，且上表字段齐全（`design` 必须是 `modules/designs/` 下现有的主题，旧项目里已删除的主题会被判为不合格、回到本 phase 重选；`fetch_materials` 必须是布尔；`duration` 必须是分钟数；`orientation` 必须是三个规范朝向之一；`qa_level`、`approval_gates`、`narration_requests`、`composition_requests`、`material_search_requests` 都可缺省，填写时按上表类型校验）。

## 执行后自检

程序能判断的由 `pipeline-status` 检查（见上）。写入前自己再过一遍：

- 用户说过的每一项（来源、时长、语言、朝向、风格、要不要素材、要不要审稿）是否都有对应字段；用户没提的项是否用了默认值，而不是编的。
- 用户的原话有没有丢：旁白要求进 `narration_requests`，画面要求进 `composition_requests`，点名要在某平台找素材的进 `material_search_requests`。
- 拿不准、又没有可默认项的字段（比如用户只说了“做个短视频”却看不出用途和重点）是问过了，还是猜的。猜的要先问，一次只问一个。

发现问题就改 `inputs.json` 再查状态。已经有下游产物时，改输入会让依赖它的阶段变 stale，按状态脚本的提示处理，不要自己另找一套记录。

## 下一步

跑 `python3 scripts/pipeline-status.py {work_dir}/{topic_name}` 确认下一个 phase：论文模式（`input_mode = "paper"`）下一个是 Phase 2（解析论文），否则直接进 Phase 3（调研）。

## 护栏

- **先读已有需求，再补默认值；能默认的不问。** 只问两类问题：缺了就没法开工、又没有默认值的，以及用户的要求互相冲突的。需要问时一次问一个，不要把整张字段表当问卷逐项确认。
  ↳ DO NOT：把用户已经说过的来源、语言、时长再问一遍；为了凑齐字段而编值。
- **用户的原话要落地，不要只留在对话里。** 旁白要求写进 `narration_requests`，画面要求写进 `composition_requests`，平台搜索要求写进 `material_search_requests`。下游 agent 只读文件，不回看本次对话。
  ↳ DO NOT：把要求记在 Scratchpad 或只在回复里复述一遍。
- **模板和字幕排版不在本阶段决定。** 模板是 Phase 8 的画面选择，本阶段不选，也不为将来可能选的模板改旁白或时长。
  ↳ DO NOT：为了让某个模板好看而提前改叙事或朝向。

---

按下面的顺序把输入集齐：

1. 来源：要抓取的 URL、粘贴的文本，或仅一个主题。
2. 朝向：默认横屏 `1920×1080`。用户说“竖屏”但没给比例时用 `1080×1440`（`orientation` 写 `portrait-3:4`）；明确要 9:16 时才用 `1080×1920`（`portrait`）。
3. 风格：只确定 `design` 的值。
   - 三个主题都在 `modules/designs/` 里（契约见 `modules/designs/designs.md`）：
   - 默认：`default`——燕麦纸，安静的编辑风（`modules/designs/default/default.md`）
   - 主题是 GitHub trending / repo launch / open source 项目介绍 → **github**（`modules/designs/github/github.md`）
   - 主题是 Product Hunt 周榜 / SaaS launch / 新产品发布 → **producthunt**（`modules/designs/producthunt/producthunt.md`）
   - 用户要求手绘、深色等现有主题都没有的风格 → 告诉用户目前没有对应主题，`design` 写 **default**，并把这条要求记进 `composition_requests`；Phase 8 按 `modules/designs/designs.md` 的草案覆盖配色前会先和用户确认
   - 未指定时保持默认主题。
4. 时长：用户说了就用他的值，不设上下限；没说用 3 分钟。
5. 语言：默认中文；用户要其他语言时照他说的写。
6. 视觉素材：默认联网搜索。用户说不要就用 `fetch_materials = false`；论文模式即使不联网搜索，论文自己的关键图也照样进视频。用户点名要在某个平台找素材（图片搜索、视频网站等）时，把原话记进 `material_search_requests`；没提就不加。
7. 旁白与画面的额外要求：用户对旁白说的（“语气更口语”“结尾不要 CTA”）进 `narration_requests`；对画面说的（“强调实验对比图”“不要人物区”）进 `composition_requests`。同一件事不要两处都记。
8. 审稿：默认不审稿（`approval_gates` 为 `[]`）。只有用户明确要求时才填 `research-brief` / `script`，不主动询问。
9. **输入类型识别：**
   - 来源是 `.pdf` 文件路径 → 置 `input_mode = "paper"`
   - 来源是以 `.pdf` 结尾的 URL（例如 arXiv） → 置 `input_mode = "paper"`，并将该 URL 保留用于 `parse-pdf.py --url`
   - 否则 → 置 `input_mode = "standard"`（默认；后续所有 "paper mode" 段落都跳过）

**如果用户要求沿用另一个项目的风格**（例如“用和 `xxx-video/` 一样的风格”），去那个项目读它实际保存的 `inputs.json`，采用相同的 `design`；它自己的主题相关要求不要照搬，只把与本项目主题相关的部分按第 7 条记进本项目的列表。外观 token 只从所选 design 的文档取，不要复制任何 DESIGN.md。

把结果落盘为 `inputs.json`，再运行 `python3 scripts/pipeline-status.py {work_dir}/{topic_name}` 进入下一个 phase。续跑 / 回退永远以状态脚本的输出为准，不要自己扫描工作区猜进度。
