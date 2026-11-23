# 调度与重做（主 agent 的通用规则）

状态脚本校验文件与结构，内容质量由 agent 与用户判断。各阶段具体检查项见对应阶段文档。

## 谁决定下一步

- 进度只看 `python3 scripts/pipeline-status.py <workspace>` 的 `next_phase`，不自行扫描工作区猜进度。
- 状态脚本不监控文件变更或对话反馈；是否修改输入或登记重做由主 agent 判断。
- 委派步骤（素材 catalog / 旁白与场景规划 / 画面 / 封面）按对应阶段文档划分职责；执行 agent 不自行批准稿件或取消审稿。

## 三种要求的区别

| 用户或自检说了什么 | 怎么处理 |
| --- | --- |
| “改成 3 分钟”“语气更口语”“画面用深色”“封面只出 16:9”这类长期要求 | 写入 `inputs.json` 对应字段（基础字段、`narration_requests`、`composition_requests`、`cover_requests`）；受影响下游由主 agent 按修改范围显式登记重做 |
| “这一段不满意，重写”这类一次性修复意见 | 定位阶段并用 `--redo` 登记原因，改完用 `--finish` 结束；不把单次修复意见追加为长期规则 |
| “后面不用再审了”这类审稿策略变化 | 修改 `inputs.json` 的 `approval_gates`，不用 `--approve` 冒充用户确认 |

意图不明或反馈无具体定位（如“不好看”）时先问清对象（旁白、素材还是画面）。

## 登记重做

产物齐全但内容不合格或用户要求重写时，显式登记：

```bash
source .venv/bin/activate && python3 scripts/pipeline-status.py <workspace> --redo <phase_id> --reason "要改什么、为什么"
```

登记后旧产物保留，该阶段变为待重做（`next_phase.reason == "redo"`，附 `redo_reason`），后续阶段变为 `pending`。改文件或普通查询不会自动清除登记，完成后须显式结束：

```bash
source .venv/bin/activate && python3 scripts/pipeline-status.py <workspace> --finish <phase_id>
```

`--finish` 先清除该阶段重做记录，再运行其常规产物校验（不要求产物字节变化，确定性重跑同字节同样通过）。它只结束当前阶段，下游是否重做由主 agent 按修改范围显式登记；它也不替代阶段内容自检或用户审稿（重做带 gate 的阶段会撤销旧确认，完成后须重新找用户确认）。

边界约束：

- 只改输入即可表达的长期要求（时长、语言、风格）直接改 `inputs.json`，仅对需重建产物的阶段显式登记重做。
- 禁对处于 redo 的阶段用 `--approve` 跳过（脚本亦会拒绝）。
- 禁靠删产物触发回退：论文解析与网页抓取共用 `harvest_page/manifest.json`，误删会丢失其他阶段结果。
- `.pipeline/redos.json` 持久化保存重做请求，损坏不可读时状态脚本会直接报错停机。

## 把意见落到阶段

| 问题 | 阶段 |
| --- | --- |
| 时长、语言、朝向、是否抓素材、审稿要求写错，或旁白 / 画面要求漏记 | `1-gather-inputs` |
| 论文解析缺页、乱码、图注错配 | `2-paper-parse` |
| 事实不准、数字没依据、讲不清核心问题 | `3-research` |
| 素材与主题无关、明显偏题、来源可疑；用户点名要去的平台没去搜 | `4-material-harvest` |
| 素材描述不符、片段选错、该用的图没用上 | `5-material-catalog` |
| 叙事重复或跳跃、旁白不忠于简报、场景计划误导 | `6-script-scene-plan` |
| 漏读、读音不对 | `7-voice-subtitles` |
| preset / custom design 选择或契约错误、模板选错、layout 选错、版式、素材容器、字幕错位或溢出、必用图表没上、渲染不完整 | `8-composition` |
| 黑屏、冻结、音画时长不符、成片观感 | `9-check` |
| BGM 曲目、背景乐音量或开关变化 | `10-mix`（开关变化先改 `inputs.json` 的 `bgm`） |
| 封面钩子、重要数字、选帧构图、尺寸或封面开关变化 | `11-cover`（开关或长期要求变化先改 `inputs.json` 的 `cover` / `cover_requests`） |

反馈涉及多阶段时先登记最早阶段，完成后再按影响范围逐项登记下游（用户明确要求后续全部重做时逐项登记）。

全片 design、视觉 scenes 与逐场景 template / layout 由 Phase 8 composition agent 决定并写入 `composition/design.json` 与 `composition/scene-config.json`（storyboard 记录理由）；主 agent 只维护 `orientation` 与 `composition_requests`（含作用范围），不在派发前预选 design / template / layout 或预装字体。修改画面方案只登记 Phase 8 及受影响下游重做，不重建 Phase 7 音频、transcript 与时间轴。

重做按阶段分工执行：委派产物交回 sub-agent 小批定向修改；改旁白重跑 `make-narration`；改画面由主会话重跑 `check-composition` 并重新渲染；改封面由主会话重跑 `render-cover` 与 `400px` 缩略图检查。

## 记录在 .pipeline/ 里的状态

只由状态脚本写入，禁止手改：

- `approvals.json`：按 gate 记录用户确认事实与时间（不绑定文件哈希）；显式重做对应阶段时自动撤销旧确认。
- `redos.json`：已登记且未完成的重做请求。
