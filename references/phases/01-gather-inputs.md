# Phase 1 — 收集输入（一次问用户一个问题）

## 输入

用户在对话中给出的主题、文章 URL、粘贴的文本或论文 PDF / URL；项目工作区里可选的项目指令文件：`narration-instructions.md`（旁白要求）、`composition-instructions.md`（画面要求）、旧的 `style-prompt.md`（视为 composition 指令的一部分）。

## 输出

`inputs.json`（工作区根目录）。字段：

| 字段 | 说明 |
| --- | --- |
| `source` | 来源：要抓取的 URL、粘贴的文本，或仅一个主题 |
| `input_mode` | `standard`（默认）/ `topic` / `article` / `text` / `paper`（论文模式） |
| `duration` | 目标时长，默认 5 分钟 |
| `language` | 解说语言，默认中文 |
| `orientation` | `landscape`（横屏 1920×1080）/ `portrait`（竖屏 1080×1920）/ `portrait-3:4`（1080×1440） |
| `template` | 所选模板，未选为 `null` |
| `design` | 所选 design：`default` / `dawn` / `moon` / `github` / `producthunt`，对应 `modules/designs/<design>/<design>.md` |
| `layout` | 所选 layout：`presenter` / `stage` / `portrait` / `portrait-3x4`，由模板或朝向决定，区域定义在 `modules/layouts/` |
| `coding_agent` | 委派目标，默认 `claude-code` |
| `fetch_materials` | 是否联网抓取视觉素材（布尔） |
| `qa_level` | 渲染后 QA 档位（缺省视为 `standard`）：`quick` = 渲染前检查 + 渲染后确定性检查，contact sheet 照常生成给用户看但不作 vision；`standard` = 全部检查（quick + 主 agent 逐张过 contact sheet，每张只看渲染完整 / 画面与旁白相符 / 符合 design / 明显空洞或错位 4 项）；`strict` = standard + 每个 scene 加一张入场帧、每个切点加前 / 中 / 后三帧。三档的完整流程见 Phase 10 |

## 完成判据

`inputs.json` 存在、非空、JSON 可解析，且上表字段齐全（`fetch_materials` 必须是布尔；`qa_level` 可缺省，缺省视为 `standard`，填写时必须是三档之一）。

## 下一步

跑 `python3 scripts/pipeline-status.py {work_dir}/{topic_name}` 确认下一个 phase：论文模式（`input_mode = "paper"`）下一个是 Phase 2（解析论文），否则直接进 Phase 3（调研）。

---

一次问一个问题，逐项确认：

1. 来源：要抓取的 URL、粘贴的文本，或仅一个主题。
2. 朝向：`1920×1080`（横屏）、`1080×1920`（竖屏）或 `1080×1440`（3:4 竖向）。
3. 模板与 layout：主题命中已有模板（如 GitHub 热榜，模板见 `modules/templates/`）→ 选模板，layout 用模板指定的那个（github 模板是讲解模式，用 `presenter`）。不选模板时按朝向选通用 layout：横屏用 `stage`（1920×1080，无主持人），竖屏用 `portrait`（1080×1920）或 `portrait-3x4`（1080×1440）。选定的 layout 写进 `inputs.json` 的 `layout` 字段（`pipeline-status` 会校验该字段），区域定义读 `modules/layouts/<layout>.md` + 同名的 `.json`。
4. 风格：从用户措辞推断。项目工作区里已有的 `narration-instructions.md` / `composition-instructions.md` 是用户为单个项目追加的旁白 / 画面要求（叠加顺序见 `references/delegation/conventions.md`）；旧项目的 `style-prompt.md` 视为 composition 指令的一部分。
   - 用户在对话中对旁白或画面提出的额外要求（例如“结尾不要 CTA”“语气更口语”），由主 agent **追加写入对应的项目指令文件**（旁白要求追加到 `narration-instructions.md`，画面要求追加到 `composition-instructions.md`），再进入对应 phase；追加前若文件不存在则新建。
   - 五个主题都在 `modules/designs/` 里（契约见 `modules/designs/designs.md`）：
   - 默认：`default`——Frag Note 安静明亮编辑风（`modules/designs/default/default.md`）
   - 主题是 GitHub trending / repo launch / open source 项目介绍，或选了 github 模板 → **github**（`modules/designs/github/github.md`）
   - 主题是 Product Hunt 周榜 / SaaS launch / 新产品发布 → **producthunt**（`modules/designs/producthunt/producthunt.md`）
   - 用户明确要求手绘 → **dawn**（`modules/designs/dawn/dawn.md`）；要求深色编辑 → **moon**（`modules/designs/moon/moon.md`）
   - 未指定时保持默认主题。
5. 时长：通常 3-10 分钟——从用户需求中提取，默认 5 分钟。
6. 语言：默认中文。若用户想要其他语言要询问确认。
7. 询问是否需要搜索视觉素材（图片/视频片段）来丰富场景。默认：是。
8. **输入类型识别：**
   - 来源是 `.pdf` 文件路径 → 置 `input_mode = "paper"`
   - 来源是以 `.pdf` 结尾的 URL（例如 arXiv） → 置 `input_mode = "paper"`，并将该 URL 保留用于 `parse-pdf.py --url`
   - 否则 → `input_mode = "standard"`（默认；后续所有 "paper mode" 段落都跳过）

**如果已经存在一个姊妹项目**（例如用户说 "用和 `claude-code-video/` 一样的风格"），把该项目的 `composition-instructions.md`（旧的 `style-prompt.md` 视为其中一部分）复制进本项目工作区，并在对话中向用户确认要选同一个 design / layout；外观 token 只从所选 design 的文档取，不再复制任何 DESIGN.md。

全部确认后，把结果落盘为 `inputs.json`，再运行 `scripts/pipeline-status.py` 进入下一个 phase。续跑 / 回退永远以状态脚本的输出为准，不要自己扫描工作区猜进度。
