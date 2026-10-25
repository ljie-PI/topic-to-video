# topic-to-video

把一个主题、文章链接、粘贴的文本或论文 PDF 变成一段有解说的视频（通常 3-10 分钟，横屏或竖屏）。底层使用可切换后端的 TTS 配音与词级 ASR、调研与抓取的素材，以及通过 HyperFrames 完成的画面渲染。

本仓库本身就是一个 skill 目录：主 agent 按 `SKILL.md` 描述的状态脚本循环逐 phase 执行，每步读哪份文档、产物契约、委派方式等**操作细节都在 `SKILL.md` 和 `references/phases/` 里**，README 不重复。

## 安装

把本仓库（整个目录）复制或软链到你使用的客户端的 skills 目录即可，例如 Claude Code 的 `~/.claude/skills/topic-to-video/`。之后用自然语言触发（见下），无需记任何命令。

### 环境依赖

一次性配置清单在 [SKILL.md](SKILL.md) 的「工具与依赖」一节（系统工具、Chrome、可选视觉模型、Gemini 登录）；TTS / ASR 后端的包与环境变量见两个脚本自己的 `--help`。

## 使用

直接用自然语言告诉主 agent 需求即可，例如：

- “给我做一个 90 秒讲 <某主题> 的视频。”
- “把这篇文章做成 5 分钟的解说视频：<文章 URL>。”
- “解读这篇论文：<arXiv PDF>。”（自动进入论文模式）
- “根据这段文字做一段竖屏讲解视频。”（随后粘贴文本）

Phase 1 会一次问一个问题来确认输入：来源、时长（默认 5 分钟）、语言（默认中文）、朝向、模板与 design、是否联网抓取素材、QA 档位。开始创作前你可以在工作区放项目指令文件（`narration-instructions.md` 旁白要求 / `composition-instructions.md` 画面要求），也可以在对话中随时追加要求。

### 可选项（高层）

| 选项 | 取值 |
|------|------|
| 模板 | `github`（GitHub 热榜 / repo 介绍）等，见 `modules/templates/`；不选模板则走通用 layout |
| design（外观） | `default` / `dawn` / `moon` / `github` / `producthunt`，见 `modules/designs/` |
| layout（版面） | `presenter`（讲解）/ `stage`（横屏无主持人）/ `portrait` / `portrait-3x4`（竖屏），见 `modules/layouts/` |
| 委派目标 | 默认 `claude-code`；可指定其他 coding agent |
| QA 档位 | `quick`（只做确定性检查）/ `standard`（默认，含 vision）/ `strict`（加入场帧与切点帧） |

### 产物在哪里

- 成片：`{工作区}/{主题}/composition/renders/final.mp4`
- 含背景乐的最终交付：`{工作区}/{主题}/composition/renders/final_with_bgm.mp4`
- QA 关键帧拼图与报告：`{工作区}/{主题}/qa/`

中途中断后直接对主 agent 说“继续”，状态脚本（`scripts/pipeline-status.py`）会扫描工作区、指出下一个 phase 并自动回退到产物缺失的 phase；细节见 `SKILL.md`。

## 开发

测试只走脚本的命令行接口（stdout 一个 JSON + 退出码 0 / 1 / 2），不测试内部函数：

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt   # pytest、Pillow
pytest
```

## 更多文档

- `SKILL.md` —— 主 agent 的工作循环与核心护栏（操作细节的唯一入口）
- `references/phases/` —— 每个 phase 一份的自包含执行文档
- `references/gotchas.md` —— 踩坑清单（症状、原因、恢复方式）
- `modules/modules.md` —— 可复用模块库（designs / layouts / components / patterns / templates）的入口
- `docs/smoke-checklist.md` —— 发布前的手动端到端冒烟步骤
