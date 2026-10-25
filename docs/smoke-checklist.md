# 端到端冒烟清单（人工执行）

发布前的人工验证。两条冒烟都依赖真实后端与账号（Gemini 登录、TTS / ASR 后端、Claude Code 委派、HyperFrames），**不要**自动化。执行方式：把每步的要求自然语言告诉主 agent，由它驱动 skill；本清单只列人要做的事情和要核对的结果。状态脚本（唯一的续跑入口）：

```bash
python3 scripts/pipeline-status.py {work_dir}/{topic_name}
```

## 冒烟 A：github 模板 60 秒主题，Phase 1 → 9

**前置**：Chrome 已登录 Gemini；TTS / ASR 后端环境变量已配置（见两个脚本的 `--help`）；`claude-code` 可用作主 agent 的原生 sub-agent 派发目标；`.venv` 已激活。

1. **触发**：对主 agent 说“用 github 模板做一个 60 秒讲 <某主题> 的视频”。
2. **Phase 1 核对**：主 agent 逐项确认输入后落盘 `inputs.json`，核对这些字段：`duration` ≈ 60 秒、`template` = `github`、`design` = `github`、`layout` = `presenter`、`orientation` = `landscape`、`fetch_materials` = `true`、`qa_level` = `standard`、`coding_agent` = `claude-code`。
3. **循环推进**：每完成一个 phase 重跑一次状态脚本，`next_phase` 应按 3 → 4 → 5 → 6 → 7 → 8 → 9 前进。
4. **Phase 3**：确认先跑了 `scripts/gemini-deep-research.py --self-check`（通过后才提交调研）；产出 `research-brief.md` 且先给你过目。
5. **Phase 6（委派 1/2）**：确认主 agent 只对 Claude Code sub-agent 发了一句话 prompt（`读取 {work_dir}/{topic_name}/script-handoff.md 并按它执行；完成后报告产物路径。`），产物为 `script.txt` / `tts-lexicon.json` / `narration.txt` / `narration-offsets.json` / `scene-plan.json`；主 agent 做 ±15% 字数、段落全覆盖、素材引用三项校验后把旁白与场景摘要给你确认。
6. **续跑测试（中断恢复）**：Phase 6 完成、Phase 7 配音之前，手动删掉一个中间产物（例如 `narration.txt`），重跑状态脚本——`next_phase` 必须回退到 Phase 6；让主 agent 继续，确认它能从 handoff 重新委派补齐产物，之后 `next_phase` 恢复正常前进。
7. **Phase 8（委派 2/2）**：确认 composition 同样经 Claude Code 委派（读 `composition-handoff.md`）；storyboard 的每个 scene 都标注了所用 content 区域；渲染前 `npx hyperframes check` 无错误、`check-composition` verdict 为 pass；产物含 `composition/index.html`、`composition/compositions/`、`composition/renders/final.mp4`。
8. **Phase 9（standard 档 QA）**：`check-render.py` 确定性检查 pass；`make-contact-sheet.py` 生成 `qa/sheet_NNN.jpg`（约 40 scene 的片子 vision 调用应 ≈ scene 数 ÷ 4）；主 agent 逐张过目并写 `qa/qa-report.json`（只含 `findings` + `verdict`）。若 verdict 为 `fail`，确认修复轮 ≤ 2 轮、每轮只改受影响 scene；finding 数不再下降时应标 `handed_off` 交还给你。
9. **最终交付**：`mix-bgm.py` 产出 `composition/renders/final_with_bgm.mp4` 存在且非空；状态脚本报告 `next_phase` 为 `null`（全部完成）。

**验收**：`final_with_bgm.mp4` 生成；两个委派步骤都由 Claude Code 完成；删中间产物后续跑正确；standard 档 QA 通过或 2 轮内停下交回报告。

## 冒烟 B：arXiv PDF 论文模式，至少跑到 Phase 6

**前置**：同冒烟 A；另需 `MINERU_API_TOKEN`（`.env`）或本地 `mineru`。

1. **触发**：对主 agent 说“解读这篇论文：<arXiv PDF URL 或本地路径>”。
2. **Phase 1 核对**：`inputs.json` 的 `input_mode` = `paper`，来源是 `.pdf` URL 或本地 `.pdf`。
3. **论文解析排程**：重跑状态脚本，`next_phase` 必须是 `2-paper-parse`（标准模式下不会有这一项）。
4. **Phase 2**：主 agent 用 `parse-pdf.py` 解析主论文；核对 `harvest_page/main-paper/metadata.json` 的 `source_type` = `paper_pdf`、`paper_metadata` 字段齐全（`full_markdown_path` / `figure_captions` / `table_captions`），`manifest_papers.json` 已写入。
5. **Phase 4**：论文条目并入统一素材流（`merge-paper-manifest.py` 之后 `manifest.json` 里存在论文来源的 entry，`source_type` = `paper_pdf`）。
6. **Phase 6**：script agent 的旁白采用论文叙事结构（Hook → Background → Key insight → Method walkthrough → Results → Impact → Takeaway，见 `references/phases/02-paper-parse.md` 的「论文模式解说结构」），论文 figure / table 是首选素材（`material_candidates` 引用 `paper_pdf` 条目）。跑到旁白与场景摘要给你确认即可停下。

**验收**：状态脚本把 2P 排进流程；manifest 含论文来源条目；script agent 采用论文叙事结构。
