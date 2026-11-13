# 调度与重做（主 agent 的通用规则）

状态脚本判断文件是否合格、哪些步骤需要重做；内容是否值得放进视频由 agent 和用户判断。本文说明两者怎么对接。各阶段的具体检查项写在各自的阶段文档里。

## 谁决定下一步

- 进度只看 `python3 scripts/pipeline-status.py <workspace>` 的 `next_phase`，不自己扫描工作区猜。
- 状态脚本不读自然语言：它看不到“这稿不好”“把时长改成 3 分钟”这类要求，除非有人把要求写成输入或登记成重做。把这个判断交给主 agent。
- 委派步骤（素材 catalog / 旁白与场景规划 / 画面）里，执行 agent 自己先按阶段文档自检，再把问题和产物一起报给主 agent。执行 agent 不自行批准稿件，也不决定取消审稿。

## 三种要求的区别

| 用户或自检说了什么 | 怎么处理 |
| --- | --- |
| “改成 3 分钟”“语气更口语”“画面用深色”这类长期要求 | 写进 `inputs.json` 对应的字段（时长等基础字段、`narration_requests`、`composition_requests`）；依赖它的阶段是否重做由主 agent 按修改范围显式登记，状态脚本不从文件变化推断 |
| “这一段不满意，重写”这类一次性修复意见 | 定位到要改的阶段，用 `--redo` 登记并写明原因；改完后用 `--finish` 结束。不要把一次修复意见当成风格规则追加进项目指令 |
| “后面不用再审了”这类审稿策略变化 | 改 `inputs.json` 的 `approval_gates`，不要用 `--approve` 代替用户确认 |

拿不准用户要哪种时先问一句；“不好看”这类没有定位的反馈，先问清是旁白、素材还是画面。

## 登记重做

产物齐全但内容不合格、或用户要求重写时，文件本身往往还没有变化，状态脚本不可能发现。这时明确登记：

```bash
source .venv/bin/activate && python3 scripts/pipeline-status.py <workspace> --redo <phase_id> --reason "要改什么、为什么"
```

登记后旧产物保留，但该阶段不再算完成（`next_phase.reason` 为 `redo`，并带 `redo_reason`），其后的阶段为 `pending`。普通查询不会清掉这条记录，改文件也不会：

```bash
source .venv/bin/activate && python3 scripts/pipeline-status.py <workspace> --finish <phase_id>
```

`--finish` 先清掉这条要求，再让该阶段走它平时的产物检查：全部通过才算结束。检查不过就报失败；它不要求产物字节与上次不同——确定性重跑得到相同字节也是正常结束。只影响被结束的那一个阶段：它不会替主 agent 登记下游重做，下游是否需要重做由主 agent 按已知修改范围显式登记。

它不证明内容合格——内容要按该阶段文档自检；也不代替用户审稿：启用了审稿的关卡该确认还要确认，显式重做带 gate 的阶段会撤销该 gate 的旧确认，重做完成后要重新找用户确认。

一条重要的分工：**要不要重做由人说的话决定，不由文件变没变推定。** 脚本不会因为某个输入文字改了、或某个文件被重写，就要求某个阶段重做；反过来，只改输入就能说明白的长期要求（时长、语言、风格）也不必登记重做。

几条边界：

- 只改输入就能说明白的要求（时长、语言、风格）不必登记重做，改输入即可。
- 不要用 `--approve` 跳过待重做的阶段；脚本也会拒绝。
- 不要靠删产物触发回退：论文解析和网页抓取共用 `harvest_page/manifest.json`，删它会连带丢掉别的阶段的结果。
- 后台中断也不丢要求：记录在 `.pipeline/redos.json`，下次查询照样报告。这份记录整个文件读不出来时，状态脚本直接报错停下，而不是当作没有要求；单条记录的格式不单独校验，因为要求最终由阶段自己的检查兑现。

## 把意见落到阶段

先找出要紧的那一处，映射到阶段编号：

| 问题 | 阶段 |
| --- | --- |
| 时长、语言、朝向、用户明确指定的 design 约束、是否抓素材、审稿要求写错，或旁白 / 画面要求漏记 | `1-gather-inputs` |
| 论文解析缺页、乱码、图注错配 | `2-paper-parse` |
| 事实不准、数字没依据、讲不清核心问题 | `3-research` |
| 素材与主题无关、明显偏题、来源可疑；用户点名要去的平台没去搜 | `4-material-harvest` |
| 素材描述不符、片段选错、该用的图没用上 | `5-material-catalog` |
| 叙事重复或跳跃、旁白不忠于简报、场景计划误导 | `6-script-scene-plan` |
| 漏读、读音不对 | `7-voice-subtitles` |
| preset / custom design 选择或契约错误、模板选错、layout 选错、版式、素材容器、字幕错位或溢出、必用图表没上、渲染不完整 | `8-composition` |
| 黑屏、冻结、音画时长不符、成片观感 | `9-check-mix` |

一次反馈涉及多个阶段时，先登记最早的那一个，后面的阶段等它完成后再按已知修改范围逐项登记；用户明确要求后面的步骤也全部重做时，逐项登记。

全片 preset / custom design、最终视觉 scenes 与逐场景 template / layout 是 Phase 8 的画面选择，由 composition agent 分别写在 `composition/design.json` / `composition/scene-config.json`（storyboard 记录理由）；主 agent 只维护全片 orientation、用户明确指定的 design 约束与 `composition_requests`（含作用范围），不替它预选默认 design 或任何 scene 方案，也不要求准备 handoff 前安装字体或决定全局 template / layout。用户改画面主意时登记 Phase 8 重做并交回 composition agent；这些变化只让 Phase 8 及其登记的下游重做，音频、transcript 和时间轴都不重建。旧工作区的 `inputs.json.layout` / `template` 原样保留，但新流程不拿它们当门槛。

重做仍由原负责人做：委派步骤交回原执行 agent，并附上具体修改点；改旁白后要重新生成朗读稿与偏移表；改画面后要重跑渲染前检查并重新渲染。

## 记录在 .pipeline/ 里的状态

只由状态脚本写，不要手改：

- `approvals.json`：按 gate 记录的用户确认事实与时间，不绑定文件哈希；显式重做对应阶段时撤销该 gate 的旧确认。
- `redos.json`：已登记、尚未完成的重做要求。

状态脚本不再读写 `stamps.json`、`fpcache.json` 或任何指纹缓存：旧工作区里残留的这些文件不影响扫描，也不替用户清理。
