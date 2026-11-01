---
name: topic-to-video
description: 当用户提供一个主题、文章 URL、论文 PDF 或链接、一段粘贴的文本，并请求做成一段有解说的视频时使用。
---

# Topic → Video 工作流

## 本 skill 产出什么

一段有解说的视频，使用：

- **Web 调研** 在写脚本之前获取准确的内容
- **HyperFrames** 用于下游 HTML composition + 渲染（delegated）
- **TTS / ASR** 生成配音并拿回词级时间戳；后端由环境变量选择，参数和依赖见两个脚本的 `--help`
- 一份 design / layout / template 选择，约束下游 composition 的外观与版面

**输出：** `{work_dir}/{topic_name}/composition/renders/final.mp4`，可直接发布（由 Phase 8 coding sub-agent 产出）；Phase 9 混入 BGM 后得到 `final_with_bgm.mp4`。

## 工作流：一个循环

1. 运行 `python3 scripts/pipeline-status.py {work_dir}/{topic_name}`（工作区目录必填）。它输出一个 JSON：已完成的 phase、下一个 phase（`next_phase.reason` 说明原因：缺失 / 损坏 / stale / 要求重做 / 未确认 / 等审稿）、要读的文档、缺失或损坏的产物。
2. 先查状态，再读它指出的那一份阶段文档（`next_phase.doc`），不要提前读完所有阶段。需要核对前后步骤的输入输出、回退重做或排查问题时，可以查相关文档和文件；下一步仍由状态脚本确定。
3. 按该文档执行；文档头部的「输入 / 输出 / 完成判据 / 执行后自检 / 下一步」是自包含的，正常情况下不需要查其他阶段文档。
4. 回到第 1 步，直到脚本报告 `next_phase` 为 `null`（全部完成）。

**默认全自动跑完，不主动询问是否审稿，也不调用 `--approve`。** 审稿策略只记在 `inputs.json` 的可选字段 `approval_gates`，缺省或 `[]` 表示全自动。用户要求审稿时按下表填入即可，不要多问：

| 用户怎么说 | `approval_gates` | 在哪停下来 |
| --- | --- | --- |
| 没提审稿 | `[]` | 不停 |
| “先让我看调研 / 事实来源” | `["research-brief"]` | 调研简报写好后 |
| “先让我看旁白 / 场景规划” | `["script"]` | 旁白与场景计划写好后 |
| “中途让我审稿” | `["research-brief", "script"]` | 上面两处都停 |

- `next_phase.reason == "awaiting_approval"` 只会出现在已启用的 gate。按 `instruction` 展示内容并找用户确认：有询问工具就使用它，否则在对话中提问并结束本轮；sub-agent 报给主 agent，由主 agent 找用户确认。未明确确认前不得执行 `--approve` 或进入下游。
- 用户只确认当前稿件时，执行 `--approve <gate>`，保留其他审稿要求；用户明确授权“后面全自动 / 不用再审”时，把 `approval_gates` 改为 `[]`，再跑状态脚本。不要用批量 `--approve` 冒充全自动授权，也不要把普通“继续”擅自理解成取消后续审稿。
- 审稿策略变化不要求重做已有产物；自动模式仍必须通过缺失 / 损坏 / stale 和 QA 检查。旧工作区没有 `approval_gates` 时同样按全自动续跑。

续跑、回退与重做都由状态脚本驱动。状态由三部分组成：`inputs.json`、各 phase 的产物，以及 `.pipeline/`（状态脚本记下的上游指纹和请求，**只由状态脚本写，不要手改**）。

- 某个 phase 的产物被删掉或写坏时，脚本回退到那个 phase（`reason` 为 `missing` / `corrupt`）。
- 产物齐全，但它依赖的上游在它生成之后变过（比如改了 `script.txt`，或改了 `inputs.json` 的 layout），该 phase 判为 `stale`，`changed_upstream` 列出变化的上游，按它的 phase 文档重做。
- 产物齐全、上游也没变，但用户或自检认为内容不合格时，用 `--redo <phase_id> --reason "..."` 登记（`reason` 为 `redo`，带 `redo_reason`）；改完并用 `--finish <phase_id>` 结束。`--finish` 先清掉登记，再按该阶段平时的检查验收：产物不合格或还是旧构建就报失败，只影响这一个阶段。登记与结束的规则见 `references/pipeline-control.md`。
- `next_phase` 之后的 phase 一律是 `pending`：不进 `completed_phases`，也不检查；轮到它们时再判断。
- 用户说 "redo phase N" 时，先按上一条登记重做；只有确实要丢掉产物时才删文件。
- 某个 stale 的 phase 确认不用重新生成（比如确定性的重跑得到了字节完全相同的结果）时，运行 `python3 scripts/pipeline-status.py {work_dir}/{topic_name} --restamp <phase_id>`，让脚本按当前文件重写它的指纹；该 phase 的产物必须全部合格，否则退出码为 1。待重做的阶段不接受 `--restamp`。
- 输出里 `stamps_reset` 为 `true` 时，`.pipeline/stamps.json` 曾损坏并被隔离为 `stamps.json.quarantined`：脚本不会把任何 phase 标为可信，未确认的阶段报告为 `unverified`，后面的阶段先停住。逐个核对产物后，用 `--restamp <phase_id>`（或 `--finish`）接受那一个；所有适用阶段都接受完，隔离才解除、才重新写回指纹。

不要自己扫描工作区猜进度，也不要把 Scratchpad 当进度记录。

## 核心护栏

1. **写之前先调研。** Phase 3 是强制的。关键论断都要有可核实的出处，搜索按内容缺口推进，不靠凑次数。用户给了论文，就必须先解析，不能用训练数据描述论文。
   ↳ DO NOT：调研之前写脚本；没有明确条件就跳过 Gemini；用户给了 PDF 还跳过 Phase 2；用训练数据描述一篇论文。
2. **进度只看 pipeline-status。** 续跑、回退与重做都由状态脚本驱动。
   ↳ DO NOT：自己扫描工作区猜进度；把 Scratchpad 当进度记录；手改 `.pipeline/`。
3. **每步自检，但不把工具的“成功”当内容合格。** 文件、格式、时长、字数、引用这类能由程序判断的以脚本为准；事实、叙事、素材是否贴题、画面是否对得上旁白这类内容判断由执行者按该阶段文档做，发现问题按 `references/pipeline-control.md` 登记重做。
   ↳ DO NOT：跳过阶段的执行后自检；用改无关文件或 `--restamp` 过关；把内容不合格的产物交给下游。
4. **委派步骤（Phase 5 / 6 / 8）的内容由 sub-agent 产出。** 主 agent 只准备 handoff、派发并验收。唯一例外：Phase 5 当前环境没有 sub-agent 工具时，主 agent 按 `references/phases/05-material-catalog.md` 的兜底流程生成 catalog。
   ↳ DO NOT：主 agent 手写旁白或 composition HTML；有 sub-agent 工具时主 agent 手写 catalog。
5. **屏幕上的每个素材都能追溯到 `material-catalog.json`。** 没有 catalog 引用 → 屏幕上不出现该资源。
   ↳ DO NOT：让没有 catalog 引用的素材出现在屏幕上。
6. **跑 Python 前一律 `source .venv/bin/activate`。** 用 `python3`。
   ↳ DO NOT：在未激活项目 venv 的 shell 里运行 Python，或改用 `python`。

## 输出约定

状态脚本把结果作为一份 JSON 输出到 stdout，日志输出到 stderr；日志只说明运行情况，格式不作要求，也不能当作阶段完成的依据。退出码：`0`=成功，`1`=运行时错误，`2`=参数非法。`scripts/pipeline-status.py` 是整条流程唯一的续跑入口，取代了过去的人工 checkpoint 表；它的结果携带 `phases` / `completed_phases` / `stale_phases` / `pending_phases` / `redo_phases` / `next_phase` / `missing_products` / `corrupt_products`。

共享 Chrome profile：`{work_dir}/chrome_profile/` —— **不要**删除。

## 工具与依赖

真正要记住的只有两件事：每一步先跑 `python3 scripts/pipeline-status.py {work_dir}/{topic_name}`；具体工具、调用示例和失败处理写在当前阶段文档里，用不到的不必读。

**共同准备：** 在 skill 根目录 `source .venv/bin/activate`（用 `python3`）；系统依赖 `ffmpeg`、系统 Chrome、`yt-dlp`；`playwright` 用 `pip install playwright` 安装，**不要**执行 `playwright install chromium`。各后端自己的依赖、环境变量和硬件要求只写在 `scripts/voice-clone.py` 与 `scripts/transcribe.py` 的顶部说明里。

**Pipeline 之外的三个入口：**

- `scripts/prepare-handoff.py`：委派步骤的准备，输出可原样派发的 `dispatch_prompt`（用法见阶段 5 / 6 / 8）。
- `references/pipeline-control.md`：重做、审稿与用户意见的通用调度规则。
- `{work_dir}/chrome_profile/`：调研与抓取共用的 Chrome profile，**不要**删除。
