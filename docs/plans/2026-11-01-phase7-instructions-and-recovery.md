# Phase 7 指令与恢复流程执行计划

状态：已完成。改动只涉及 Phase 7 文档、`SKILL.md`、composition 委派包与测试；未修改任何脚本。

## 执行约束

- 仅修改流程文档、相关约定与测试。
- 保持现有 CLI、产物路径、JSON schema、字幕算法和调度行为不变。
- 不新增分段 TTS、时间戳拼接、模型调用接口或全流程文档重构。

## Work item 1：整理输入、输出与文档结构

文件：`references/phases/07-voice-subtitles.md`

- [x] 输入、输出和完成判据改为逐项列表。
- [x] 输入逐项标明生产者与用途：
  - `inputs.json`：Phase 1 生成，Phase 7 使用 `layout`。
  - `script.txt`：Phase 6 的 script agent 撰写。
  - `narration.txt`、`narration-offsets.json`：script agent 在 Phase 6 最后运行 `make-narration.py` 生成。
  - `scene-plan.json`：script agent 撰写；正常 pipeline 必需，Phase 7 脚本独立运行时可缺省。
- [x] 输出保留四个路径及用途，不重复枚举全部内部字段。
- [x] 删除 TTS/字幕合并历史、重复职责说明和字体迁移段落。
- [x] 章节按“输入 → 输出 → 完成判据 → 下一步 → 护栏 → 执行与重跑 → 时间戳与字幕 → 异常恢复”排列。

## Work item 2：合并检查项，统一时间戳契约

文件：`references/phases/07-voice-subtitles.md`、`SKILL.md`

- [x] 保留顶层“完成判据”，合并独立“执行后自检”；内部区分“状态脚本校验”和“执行者核对”。
- [x] 自动检查项与当前检查器一致；音频时长、词级时间范围等未自动保证的条件列入执行者核对。
- [x] 保留命令退出码、`transcript_method`、fallback、漏读和断词告警的核对要求。
- [x] 将“TTS / ASR 接口契约”改为共同的时间戳契约，覆盖 `direct_align` 与 `asr`。
- [x] 区分音频到朗读稿的直接对齐，以及根据偏移表还原显示稿的字幕对齐。
- [x] 保留必要句级/词级字段和时间单位：原始 transcript 为毫秒，字幕/timeline 的 `_s` 字段为秒。
- [x] 删除不需要 agent 手动调用的子命令参数枚举；模型 SDK 细节留在脚本和适配器中。
- [x] 同步 `SKILL.md` 的章节约定，允许完成判据包含自检，不删除自检责任。

## Work item 3：校正字幕切分说明

文件：`references/phases/07-voice-subtitles.md`、`references/delegation/composition/base-instructions.md`

- [x] 区分原始 transcript 的句子与最终字幕单元；不直接用原始句子边界上屏。
- [x] 标明直接对齐按原文分组、云端 ASR 沿用服务边界；不承诺统一的原始句子最大长度或时长。
- [x] 写明最终字幕按显示稿句末标点、layout 的 caption 宽度/字号/行数切分。
- [x] 将“只在标点处断开、绝不切断单词或数字”改为实际保证：优先软标点，允许其他合法边界，超宽 token 强制切分并告警。
- [x] 写明长中文串可能句中切开、短于 0.6 秒的单元合并可能超宽、当前没有最长显示时长限制。
- [x] 保留 composition 逐单元原样使用、不得重新排序/合并/拆分的约束。

## Work item 4：修复 cue 来源与匹配指令

文件：`references/phases/07-voice-subtitles.md`、`tests/test_align_narration.py`

- [x] cue / beat 统一取自显示稿，限定在所属 scene 的段落范围内。
- [x] 删除从 transcript 或朗读稿取品牌读法作为 cue 的建议。
- [x] 删除“大小写、标点一变就匹配不到”的错误断言，保留归一化规则。
- [x] 告警处理指向显示稿、段落范围和漏读检查；scene-plan 修改交回 script agent。
- [x] 补回归：显示稿 `NVIDIA`、朗读形式 `英伟达`；显示稿 cue 成功，朗读形式 cue 失败，小写/标点变化仍成功，错误段落范围失败。

## Work item 5：接通外部 transcript 恢复路径

文件：`references/phases/07-voice-subtitles.md`、`tests/test_voice_subtitles.py`

- [x] 将恢复前提限定为本轮 TTS 音频有效、转写路径失败；请求对应本轮音频的外部词级 transcript。
- [x] 要求核对当前朗读稿、词级字段、时间范围和覆盖情况；不接受无时间戳纯文本，不手写时间戳。
- [x] 将合格结果保存到 `transcribe/transcript.json`，通过统一入口的 `--align-only` 恢复；不重新 TTS，不手动补跑 ASR。
- [x] 明确默认重跑会删除已有 transcript，禁止导入后直接按默认命令重试。
- [x] 恢复后核对全部产物，按状态脚本处理 stale/redo；需要接受正确复用时使用 `--restamp`，有待完成的 redo 时先 `--finish`。
- [x] 补回归：转写失败后音频保留，导入合法 transcript 后仅对齐成功且音频不变，默认重跑删除导入结果，无词级时间戳被拒绝。

## Work item 6：移除不完整的 OOM 分段建议

文件：`references/phases/07-voice-subtitles.md`、`tests/test_guardrail_docs.py`

- [x] 删除“分段合成再用 ffmpeg 拼接”的执行建议。
- [x] 改为切换已配置且可用的后端后，通过统一入口完整重跑；无可用后端时报告阻塞并请求环境配置。
- [x] 不新增 chunk 功能，不复制模型调参手册。
- [x] 将要求保留“分段合成”的测试改为验证可用后端重跑/报告阻塞。

## Work item 7：明确上游修改与选择性重跑

文件：`references/phases/07-voice-subtitles.md`、`tests/test_pipeline_status.py`

- [x] 读音修正交回 script agent 修改词表并重新生成朗读稿/偏移表；不手改 `narration.txt`，不直接拿旧朗读稿重跑 Phase 7。
- [x] 增加操作表：朗读内容改变完整生成；仅 scene-plan/layout 变化且音频仍正确时使用 `--align-only`。
- [x] 音色/后端变化但输入未变时，由主 agent 显式登记 Phase 7 redo。
- [x] 区分下游暂时 `pending`、按依赖判定 `stale`、用户明确要求的 redo；不规定下游一律重做。
- [x] 保留 Phase 8 依据音频/字幕/timeline 等、Phase 9 依据成片等依赖判断的规则。
- [x] 写清阶段内复用由执行者选择；正确复用或字节相同重算按通用流程 `--finish` / `--restamp` 收尾，不改无关文件凑指纹。
- [x] 复用现有测试，缺失时补齐：下游 pending、依赖变化后的 stale、仅对齐后接受正确复用、字节相同重算。

## Work item 8：同步测试并验收

- [x] 更新 `tests/test_phase_docs.py`：验证 Phase 7 合并后的两类检查，保留其他 phase 的章节顺序与输出路径校验。
- [x] 更新 `tests/test_guardrail_docs.py`：在对应章节验证恢复规则，不要求所有排障说明塞进护栏。
- [x] 按需调整 `tests/test_doc_references.py`，保留路径与调用归属检查。
- [x] 复用 `tests/test_aligner_adapters.py`、`tests/test_text_align_transcript.py`；补齐缺失的长句分组、跨边界 token 不丢词测试。
- [x] 增加或复用字幕特征测试：无软标点长中文、超宽 Latin token、短时单元合并超宽；不改变算法。
- [x] 用 fake 后端和临时工作区验证完整生成、仅对齐、外部 transcript 恢复、词表修改后的上游重做。
- [x] 运行定向测试、完整套件与差异检查：

```bash
source .venv/bin/activate && python3 -m pytest tests/test_guardrail_docs.py tests/test_phase_docs.py tests/test_doc_references.py tests/test_align_narration.py tests/test_voice_subtitles.py tests/test_aligner_adapters.py tests/test_text_align_transcript.py tests/test_pipeline_status.py -q
source .venv/bin/activate && python3 -m pytest -q
git diff --check
```

- [x] 确认 cue、外部 transcript、OOM 三项均有执行指令和回归/文档覆盖。
- [x] 确认未改变 CLI、schema、字幕算法、调度依赖或其他 phase 的运行行为。
