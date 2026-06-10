### Phase 8 — 委派 HyperFrames Composition + Render

从这一步开始，composition 由一个使用 `hyperframes` 与 `hyperframes-cli` skills 的 coding sub-agent 拥有。`topic-to-video` 主 agent 只负责准备上游资源、写一份精简的 composition handoff、物化固定 rules / design references、调用 sub-agent，并对返回的 MP4 做 sanity check。

HyperFrames sub-agent 执行以下流程：
- 读取时间轴输入：`narration.txt` 是纯文本解说脚本（段落通常用空行分隔）；`transcribe/transcript.json` 是句子数组，每项形如 `{ "begin": <ms>, "end": <ms>, "text": "...", "words": [{"text": "...", "begin": <ms>, "end": <ms>}] }`
- 生成 scene timeline：按 `narration.txt` 的语义段落 / 完整句子组织视觉段落，并用 `transcribe/transcript.json` 的词级时间戳确定每个 scene 的 start/end；必要时按 5-8 秒约束拆分或合并相邻句子
- 如需可复现或便于调试，把 scene timeline 写成 `transcribe/scene-timeline.json`，记录每个 scene 的 `scene_id`、`start`、`end`、覆盖的句子文本和对应 word range；这只是辅助产物，不取代 `composition/index.html` 中的 `data-scene-start/end`
- 不把 scene timeline 固定成主 agent 脚本：scene 切分需要同时考虑旁白语义、素材映射、视觉节奏和 5-8 秒约束，归 HyperFrames sub-agent 决策；只有格式校验、锚点对齐等确定性辅助才适合脚本化
- 基于 `material-catalog.json` 完成 material-to-scene 映射
- 视觉信息设计、布局、排版、动画与转场
- `composition/index.html` 和 `composition/DESIGN.md`
- `hyperframes lint`、`hyperframes inspect`，以及渲染迭代

#### 8.1 — 写 `composition-handoff.md`

从 `references/composition-handoff-template.md` 出发，写出 `{work_dir}/{topic_name}/composition-handoff.md`，填入项目 metadata、输入路径、来自 Phase 1 的 style hint，以及从用户输入 / follow-up feedback / `style-prompt.md` 提取的 `User-derived Customized Rules`。handoff 要简短，但 customized rules 必须可执行，不能只写抽象审美词。

同时把固定 references 复制到项目工作区，供 sub-agent 从磁盘读取本地副本：

- 必需：`references/composition-rules.md` → `{work_dir}/{topic_name}/references/composition-rules.md`
- 如 handoff 指定 design route：`references/design-<theme>.md` → `{work_dir}/{topic_name}/references/design-<theme>.md`

`composition-handoff.md` 只记录项目变量和 customized rules，不复制 / 摘要 rules 文件中的 hard constraints。若 customized rule 与 rules 文件中的 hard constraints 冲突，必须在 handoff 的 Conflict handling 中写明；不能静默放宽 rules 文件。

Legacy fallback：旧项目若已存在 `{work_dir}/{topic_name}/composition-brief.md`，可以作为 legacy handoff 继续读取；新项目一律生成 `composition-handoff.md`。

#### 8.2 — 调用一个 coding sub-agent

优先使用当前客户端 / runtime 原生的 sub-agent 或委派工具。prompt 要简短，且应让 sub-agent 自己从磁盘读 handoff / rules / design 文件，而不是把整份 rules 文件 拼进 shell 命令里。

Prompt 示例：

```text
读取当前工作区的 composition-handoff.md，以及工作区本地 references/composition-rules.md。
如果 handoff 指定了 references/design-*.md，也读取对应 design 文件。若任一必需文件缺失，
停止并反馈主 agent，不要凭默认审美继续制作。产出所有 deliverables。
使用 hyperframes 和 hyperframes-cli skills。scene 切分、素材映射、
composition 设计、动画、lint/inspect 修复和最终渲染都由你负责。
在编写最终 HTML/CSS/GSAP 之前，先在 composition/DESIGN.md 中创建
「Reference Read Check」：确认已读取 composition-handoff.md、
references/composition-rules.md 和指定 design 文件，并保留 rules 文件的
Upstream / Critical / Style 规则编号。
再创建
「Scene Layout Inventory（逐 scene 版式清单）」：每个 scene 记录旁白摘要、
material_ref、素材 width/height + aspect ratio、text beats、选择的 layout
archetype、peak-state layout audit，以及句子级显示时机。第一次 render
之前，对 composition rules + handoff customized rules 做 self-audit，
尤其检查：字幕是单个全局 fixed 底部元素且不换行；字幕背景宽度随文本
shrink-to-fit，不使用固定宽 / 100% 宽；没有元素溢出 viewport；同时显示
的元素不重叠；foreground 文本 / tag / callout 不覆盖图片或视频素材；
素材没有可见 border / padding / 卡片框 / shadow / glow；标题文本框不折成
2+ 行；同一 scene 字号 max/min <= 3；Moon / 深色技术 scene 没有 radial
spotlight / glow / orb；entrance tween 不要 blanket 使用
immediateRender:false，非素材元素必须有确定的 hidden 初态。先修复静态检查
能发现的问题，再开始 render。迭代直到 composition/renders/final.mp4 存在，
且 HyperFrames lint/inspect 无错误。render 必须使用 `--workers 1`，避免
本机出现奇数高度帧问题。
```

如果环境里没有原生 sub-agent 工具，仅当 CLI fallback 能把上面那段 prompt 原样传过去、并让 coding sub-agent 自己去读 `composition-handoff.md`、`references/composition-rules.md` 与指定 design 文件时，才可以接受。

**不要**在主 agent 的会话里驱动 composition。

#### 8.2a — 首次 render 前 static / layout self-audit

要求 sub-agent 在第一次 render 前完成并在 `composition/DESIGN.md` 中留下可读记录：

1. **逐 scene 版式清单覆盖每个 scene**：每行包含 `scene_id`、旁白摘要、`material_ref`、素材尺寸 / aspect ratio、text beats、layout archetype、peak-state audit 结果、以及每个非素材元素对应的完整旁白句子和出现时间点。
2. **Peak-state layout audit**：对每个 scene，先按“所有非字幕元素都显示”的状态检查元素是否溢出 viewport / 内容区、是否互相覆盖、是否覆盖 catalog 素材、素材是否 letterbox / pillarbox、内容区空白面积是否 > 10%、构图是否明显失衡 / 不成型。失败先调整布局，再写动画。
3. **句子级显示时序**：把 transcript 按完整句子切分；每个非素材文本元素在它服务的句子开始前短暂提前出现，而不是 scene start 一次性出现。旧 text beat 需要淡出或降级，不能永久累积。
4. **禁用模式扫描**：检查 `composition/index.html` / CSS / GSAP 中不得出现固定宽字幕框、`width:100%` 字幕遮罩、大 `min-width` 字幕框、素材 `width + max-height/height` 同时约束、素材 border / outline / padding / shadow / glow / 卡片底、前景覆盖素材、`radial-gradient` spotlight / ambient orb / localized glow，以及所有 entrance tween blanket `immediateRender:false`。
5. **Customized rules coverage**：逐条读取 `composition-handoff.md` 的 `User-derived Customized Rules`，在 `composition/DESIGN.md` 记录每条如何被布局 / 动画 / QA 方案覆盖；若发现它与 rules 文件中的 hard constraints 冲突，以 rules 文件为底线并反馈主 agent。

#### 8.3 — sanity-check 结果

sub-agent 返回后，从主 agent 验证：

```bash
ffprobe -v error -show_entries format=duration -of csv=p=0 \
  {work_dir}/{topic_name}/composition/renders/final.mp4
ls -la {work_dir}/{topic_name}/composition/renders/final.mp4
```

预期：duration 接近目标解说时长，文件大小 > 1 MB，且包含一条音频流。如果有异常，把症状反馈给 HyperFrames sub-agent。**不要**在主 agent 里手工 patch `composition/index.html`。

#### 8.4 — Post-Render Visual QA Audit

8.3 基础 sanity-check 通过后，主 agent 必须对 final.mp4 跑视觉抽帧 QA，覆盖 3 项**必须 render 后才能查**的质量项（静帧 ≤ 2s / 同图不跨 scene 复用 / 旁白与画面一致），以及 15 项静帧检查的复核。

**两种 QA 轮模式（控制成本，见 Step 4/5/7）**：
- **首轮 = 全量审计**：对全片抽帧，旁白对齐按下方公式**抽样**（非逐句），静帧 / 复用 / spot-check 全片跑。
- **重渲轮 = 限定范围审计**：只对上一轮 `affected_scenes` 中 scene 覆盖的帧重跑昂贵的 vision 检查（Step 4/5）。未被改动的 scene 凭 Upstream Contract #11 字节不变，不重审；无 vision 成本的 static-frame / reuse 检测（Step 2/3）仍可全片跑以兜底。

**Step 1 — 每秒抽帧**

```bash
mkdir -p {work_dir}/{topic_name}/composition/qa-frames
ffmpeg -y -i {work_dir}/{topic_name}/composition/renders/final.mp4 \
  -vf fps=1 -q:v 2 \
  {work_dir}/{topic_name}/composition/qa-frames/frame_%04d.jpg
```

**Step 2 — 静帧检测（违反 Visual Constraint #2：> 2s 静止）**

用 ffmpeg scene 变化滤波器统计场景切换时间戳：

```bash
ffmpeg -i {work_dir}/{topic_name}/composition/renders/final.mp4 \
  -vf "select='gt(scene,0.03)',showinfo" -f null - 2>&1 | grep showinfo
```

或对相邻抽帧两两计算感知 hash（如 `imagehash` 库的 `phash`）。任意连续 ≥ 3 张 1fps 抽帧（即 ≥ 2 秒）的 hash 距离低于阈值 → 标记 `static_frame` 违规，记录 `[start_s, end_s, duration_s]`。**通过解析 `composition/index.html` 中各 scene 根元素的 `data-scene-start` / `data-scene-end`（Upstream Contract #10），把每个违规的 `[start_s, end_s]` 反查到对应的 `scene_id`，写入 finding 的 `scene_id` 字段**（若违规跨多个 scene，列出所有相关 `scene_id`）。

**Step 3 — 同图跨 scene 复用检测**

扫 `composition/index.html` 与各 scene 子模板（如有），按 Upstream Contract #10 的 `data-scene-id` 划分 scene 块，提取每个块内的 `<img src=>`、`<video src=>`、`background-image: url(...)`。建立 `src → [scene_ids]` 映射（仅统计可追溯到 `material-catalog.json` 的素材 src；通用 UI 贴图 / 装饰纹理 / 蒙版等非 catalog 资源不计）；同一 src 出现在 ≥ 2 个 `scene_id` 内 → 标记 `reused_material` 违规，finding 中列出所有命中的 `scene_ids`。**任何跨 scene 复用一律 fail（对应 Upstream Contract #11 素材唯一性），取消原 "intentional callback" 豁免。**

**Step 4 — 旁白对齐检测**

按 `transcribe/transcript.json` 中的句子（句号 / 问号 / 感叹号边界）切分。**为控制成本，不逐句全检**：

- **首轮**：从全片句子中**抽样** `M = max(8, scene 数)` 句（保证每个 scene 至少覆盖 1 句，其余按时间均匀抽），只对抽中句子对应的帧调 `vision-analyze.py`。
- **重渲轮**：只检查上一轮 `affected_scenes` 中 scene 覆盖秒数内的句子（同样保证每个受影响 scene 至少 1 句）。

每句覆盖的秒数对应若干抽帧。对每个 `(句, 帧集合)` 调 `vision-analyze.py`：

```bash
python3 scripts/vision-analyze.py \
  --prompt "旁白说：'<句子原文>'。下列帧画面是否在视觉上表达了这句旁白的含义？回答 yes/partial/no + 一句话理由。注意检查：① 帧中是否出现该句提到的实体（人名、产品、数字）；② 多元素逐个出现的场景，逐帧出现节奏是否与旁白同步" \
  --images <该句覆盖秒数对应的 frame_XXXX.jpg 列表>
```

任何 `no` / `partial` 标记为 `narration_mismatch` 违规。**每条 finding 必须带 `scene_id`（用句子覆盖的秒数中点查 `data-scene-start/end` 区间得到，跨 scene 时列出所有命中）。**

**Step 5 — 静帧 15 项复核（spot-check）**

随机抽 `N = max(5, ceil(total_seconds / 30))` 张帧，对每张调 `vision-analyze.py`。**重渲轮**：只从上一轮 `affected_scenes` 中 scene 覆盖秒数对应的帧里抽样，不抽未改 scene 的帧。**例外**：若 `affected_scenes` 含 `global`（全局字幕容器被改动），字幕位置/遮罩会影响全片所有 scene（可能与未改 scene 的底部内容产生新遮挡或侵入安全带），此时字幕相关检查（⑦⑪⑫）**恢复全片抽样**，其余检查项仍可限定在被改 scene。

```bash
python3 scripts/vision-analyze.py \
  --prompt "检查这帧画面 15 项视觉质量（参考 composition rules + handoff：Critical #2/#6/#7-#11、Upstream Contract #8/#9/#12-#15、Style #13/#14，以及 handoff 中的 User-derived Customized Rules）：① 图片有无模糊 / 关键信息被裁切；② 任何元素是否超出画面边界 / 被截断；③ 同时显示的元素之间有无重叠遮挡，尤其检查 foreground 文本/tag/callout 是否压在图片或视频素材之上；④ DOM 层次是否扁平（无 '框中套框'）+ 颜色对比度是否达标；⑤ 字号最大/最小比是否 ≤ 3；⑥ 内容区（视口去掉底部约 12-18% 字幕安全带后）有无 > 10% 视口的纯空白区域；⑦ 底部字幕安全带内除字幕条外是否混入了其他前景文本/callout/素材（侵入即 fail，全幅背景素材垫底不算）；⑧ 素材是否出现 letterbox / pillarbox：素材边缘外有无露出容器底色的等宽空带（上下或左右）—— 有则 fail；⑨ 画面上是否有横贯/纵贯的扫描线、扫光、sweep、进度扫描条等覆盖层（用来糊弄'非静止'要求的运动条纹）—— 有则 fail；⑩ 标题文本框是否折成 2+ 行（任一标题/主标题位文本出现换行即 fail，参考 Critical #11）；⑪ 底部字幕是否位置稳定：水平居中、垂直锚定在底部字幕安全带内（不偏上压住内容、不在画面中部漂移），参考 Upstream Contract #12；⑫ 字幕是否单行 + 背景遮罩宽度贴合当前文字（无固定宽/整行宽/大 min-width 造成的大片空遮罩），参考 Critical #6；⑬ 图片/视频素材是否有可见 border、outline、padding、卡片底、shadow、glow 或 inset 框感—— 有则 fail；⑭ 当前 scene 构图是否像固定模板硬套：与前后 scene 相同的素材位置/文本轨/卡片结构无明显内容理由，或没有根据素材横竖/方形比例调整布局；⑮ 非素材文字是否明显早于其对应完整句子大段提前出现，或多个 text beat 累积堆满屏幕。逐项回答 pass/fail + 理由" \
  --images <随机抽的 frame_XXXX.jpg>
```

每项 fail 加入 `spot_check_fails`。**每条 finding 必须带 `scene_id`（用该帧秒数查 `data-scene-start/end` 区间得到）。** 字幕类问题（⑪⑫）若源于全局字幕容器而非某个 scene，`scene_id` 记为 `global`。

**Step 6 — 汇总 qa-report.json**

写到 `{work_dir}/{topic_name}/composition/qa-report.json`：

```json
{
  "static_frames": [
    {"scene_id": "s4", "start_s": 12, "end_s": 17, "duration_s": 5}
  ],
  "reused_materials": [
    {"src": "materials/.../foo.png", "scene_ids": ["s3", "s7"]}
  ],
  "narration_mismatches": [
    {"scene_id": "s5", "sentence": "...", "frames": ["frame_0034.jpg"], "verdict": "no", "reason": "..."}
  ],
  "spot_check_fails": [
    {"scene_id": "s8", "frame": "frame_0123.jpg", "issue": "字号比超过 3", "detail": "标题 96px 同 scene 出现 24px 注脚"}
  ],
  "affected_scenes": ["s3", "s4", "s5", "s7", "s8"],
  "verdict": "fail"
}
```

`affected_scenes` = 上述 4 个数组中所有 finding 涉及的 `scene_id` 去重并按视频时间顺序排序。哨兵值 `global`（全局字幕容器等不属于任何单一 scene 的问题）不参与时间排序，**固定排在列表最末**。`verdict = "pass"` 当且仅当 4 个数组都为空（此时 `affected_scenes` 也为空）。

**同时追加一条记录到累积日志 `composition/qa-history.md`**（不存在则创建），每轮一节，便于事后追踪反复点、优化后续流程：

```markdown
## Round <N> — <ISO 时间戳> — verdict: <pass|fail>
- 模式：<首轮全量 | 重渲轮(限定 affected_scenes=[...])>
- static_frames：<条数，列 scene_id>
- reused_materials：<条数，列 src + scene_ids>
- narration_mismatches：<条数，列 scene_id>
- spot_check_fails：<条数，列 scene_id + issue>
- affected_scenes：[...]
- 本轮反馈给 sub-agent 的修复要求摘要：<一句话>
```

**Step 7 — 决策**

维护两个跨轮状态：`round`（从 1 起）和 `prev_total_findings`（上一轮 4 个数组的 finding 总数；**首轮 `round == 1` 时初始化为 `+inf`**，使无进展守卫只在 `round > 1`、确实有上一轮基线时才生效）。

- `verdict == "pass"` → 在 `qa-history.md` 末尾写一段**人类可读总结**（共几轮、哪些 scene 反复出现在 `affected_scenes`、最终 verdict），然后进 Phase 9（bgm-mix）。
- `verdict == "fail"` → 先判止损，再决定是否重渲：

  **止损判定（命中任一即停）**：
  - **全局轮数上限**：`round >= 3`（已完成 3 轮仍 fail）。
  - **无进展守卫**：`round > 1` 且本轮 finding 总数 `>= prev_total_findings`（相邻两轮没有严格下降，说明在打地鼠 / 反复返工）。首轮不触发本守卫。
  - **同集合早停**：同一 `affected_scenes` **集合**连续 2 次重渲仍 fail。比较按**集合**判等（忽略元素顺序，`global` 也按集合成员参与），不要按数组字符串相等。

  命中止损 → **停**，在 `qa-history.md` 写人类可读总结（含止损原因），把当前 `qa-report.json` 与总结要点交还用户，由用户决定接受降级 / 人工修 HTML / 回退更早 phase 调整素材 / 解说脚本。**不要继续自动重渲。**

  未止损 → 把 `qa-report.json` 与症状原文反馈给 HyperFrames sub-agent，**明确要求**：
  - **先写全局修复计划再动手**：结合全片 `DESIGN.md` 与**全部 finding**，识别共因（如同一布局模式导致多 scene 重叠 / 标题换行 / 字幕漂移），判断是逐 scene 局部修还是需要整片调整，把计划写入 `composition/qa-fix-plan-round-<N>.md` 后再改 HTML。避免逐 scene 试错反复返工。
  - **只修改 `affected_scenes` 列表中的 scene**（按 `data-scene-id` 定位）；未在该列表中的 scene 的 DOM 结构、CSS、动画时间轴必须**逐字节保持不变**，包括其 `data-scene-id` / `data-scene-start` / `data-scene-end`。字幕类（`scene_id = global`）问题改全局字幕容器，同样不得连带改动各 scene 内容。
  - 修复时如果 scene 时长变化（违反 Critical #1 的 5-8 秒约束），需要在 DESIGN.md 中记录新的时间布局，并更新所有受影响 scene 的 `data-scene-start` / `data-scene-end`；但**未受影响 scene 的时间区间不得调整**——若 sub-agent 认为必须重排整片时间轴，应在反馈中明确说明并升级为整片重渲。
  - 修复完成后 `round += 1`、记录 `prev_total_findings`，回到 8.3 重新跑 sanity-check + 8.4（**重渲轮 = 限定范围审计**），直到 `verdict == "pass"` 或命中止损。

**不要**在主 agent 里手工 patch `composition/index.html`。所有视觉问题的修复都必须委派回 sub-agent；主 agent 只是质检员，不是作者。

#### 8.5 — 约束 → QA 覆盖映射

下表列出 `references/composition-rules.md` 中每条 Visual Quality Constraint 由哪一步 QA 覆盖。标「仅创建期」的项渲染后不可（或难以）从抽帧静态判定，主要靠 8.2 的创建期 self-audit 与 sub-agent 自查保证，不进入 post-render fail/重渲循环。`composition-handoff.md` 中的 User-derived Customized Rules 需要由 sub-agent 在创建期 self-audit 中逐项覆盖；能从抽帧判断的项目也应进入 Step 5 spot-check 反馈。

| 约束 | QA 覆盖 |
|------|---------|
| Critical #1（每个 scene 5-8s） | 每轮解析 `data-scene-start/end` 区间校验时长（确定性、无 vision 成本，post-render 每轮都查）；时长是否「合理对应内容节奏」仅创建期 |
| Critical #2（静止 ≤ 2s） | Step 2（ffmpeg scene 滤波 / phash） |
| Critical #3（多文本按句子级节奏逐个出现） | 8.2a 句子级显示时序 + Step 4 部分覆盖 + Step 5 ⑮ |
| Critical #4（图片持续动效） | Step 2 间接（静帧检测）；动效类型仅创建期 |
| Critical #5（素材占主体 ≥ 50%） | 仅创建期（未进 spot-check） |
| Critical #6（字幕单行 / shrink-to-fit） | Step 5 ⑪⑫ |
| Critical #7（图片清晰完整） | Step 5 ① |
| Critical #8（不超界 / 不截断） | Step 5 ② |
| Critical #9（不重叠） | Step 5 ③ |
| Critical #10（DOM 扁平 + 对比度） | Step 5 ④ |
| Critical #11（字号比 / 标题不换行） | Step 5 ⑤（字号比）+ ⑩（标题不换行） |
| Upstream #8/#9（素材比例 / 无 letterbox） | Step 5 ⑧ |
| Upstream #9（素材无边框 / 无卡片底 / 无 padding / 无 shadow/glow） | 8.2a 禁用模式扫描 + Step 5 ⑬ |
| Upstream #11（素材唯一性） | Step 3 |
| Upstream #12（字幕安全区 / 锚点） | Step 5 ⑦（侵入）+ ⑪（锚点稳定） |
| Upstream #13（每 scene 按旁白与素材尺寸自适应布局） | 8.2a 逐 scene 版式清单 + Step 5 ⑭ |
| Upstream #14（peak-state layout audit） | 8.2a peak-state audit 记录 + Step 5 ②③⑥⑧⑬⑭ |
| Upstream #15（DESIGN.md scene inventory） | 8.2a 静态检查 |
| Style #12（scene 间过渡） | 仅创建期 |
| Style #13（居中 / 无大块留白） | Step 5 ⑥ |
| Style #14（Moon / 深色技术风无 glow/orb/spotlight） | 8.2a 禁用模式扫描 + Step 5 ⑨ |
| 句子级文本显示 / text beat 不累积 | 8.2a 句子级显示时序 + Step 4 部分覆盖 + Step 5 ⑮ |
| 旁白与画面一致 | Step 4 |

新增/调整 QA 检查项时，同步更新本表，保持「规则 ↔ 检查」一一对账。
