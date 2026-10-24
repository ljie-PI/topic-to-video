# Phase 1 — 收集输入（一次问用户一个问题）

## 输入

用户在对话中给出的主题、文章 URL、粘贴的文本或论文 PDF / URL；项目工作区里可选的 `style-prompt.md`（自由文本风格备注）。

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
| `design` | 所选 design（如 `default` / `github` / `producthunt` / `moon` / `dawn`） |
| `layout` | 所选 layout，未选为 `null` |
| `coding_agent` | 委派目标，默认 `claude-code` |
| `fetch_materials` | 是否联网抓取视觉素材（布尔） |
| `qa_level` | `quick` / `standard`（默认）/ `strict` |

## 完成判据

`inputs.json` 存在、非空、JSON 可解析，且上表字段齐全（`fetch_materials` 必须是布尔）。

## 下一步

跑 `python3 scripts/pipeline-status.py {work_dir}/{topic_name}` 确认下一个 phase：论文模式（`input_mode = "paper"`）下一个是 Phase 2（解析论文），否则直接进 Phase 3（调研）。

---

一次问一个问题，逐项确认：

1. 来源：要抓取的 URL、粘贴的文本，或仅一个主题。
2. 朝向：`1920×1080`（横屏）、`1080×1920`（竖屏）或 `1080×1440`（3:4 竖向）。
3. 风格：从用户措辞推断，或在项目工作区里有 `style-prompt.md` 时读取它。`style-prompt.md` 是一份可选的自由文本备注，其内容会覆盖默认的风格推断，并作为 style hint 传给下游 composition。
   - 默认：Frag Note 安静明亮编辑风（`references/design-default.md`）
   - 主题是 GitHub trending / repo launch / open source 项目介绍 → **GitHub 预设**（`references/design-github.md`）
   - 主题是 Product Hunt 周榜 / SaaS launch / 新产品发布 → **Product Hunt 预设**（`references/design-producthunt.md`）
   - 用户明确要求手绘、深色编辑或品牌主题时，再选择对应预设；未指定时保持默认主题。
4. 时长：通常 3-10 分钟——从用户需求中提取，默认 5 分钟。
5. 语言：默认中文。若用户想要其他语言要询问确认。
6. 询问是否需要搜索视觉素材（图片/视频片段）来丰富场景。默认：是。
7. **输入类型识别：**
   - 来源是 `.pdf` 文件路径 → 置 `input_mode = "paper"`
   - 来源是以 `.pdf` 结尾的 URL（例如 arXiv） → 置 `input_mode = "paper"`，并将该 URL 保留用于 `parse-pdf.py --url`
   - 否则 → `input_mode = "standard"`（默认；后续所有 "paper mode" 段落都跳过）

**如果已经存在一个姊妹项目**（例如用户说 "用和 `claude-code-video/` 一样的风格"），从该项目复制 `composition/DESIGN.md` + `fonts/` 过来，并在 `composition-handoff.md` 里注明 "reuse this DESIGN.md"；HyperFrames sub-agent 会决定该如何复用这个设计。

全部确认后，把结果落盘为 `inputs.json`，再运行 `scripts/pipeline-status.py` 进入下一个 phase。续跑 / 回退永远以状态脚本的输出为准，不要自己扫描工作区猜进度。
