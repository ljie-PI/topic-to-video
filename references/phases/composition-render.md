### Phase 8 — 委派 HyperFrames Composition + Render

从这一步开始，composition 由一个使用 `hyperframes` 与 `hyperframes-cli` skills 的 coding sub-agent 拥有。`topic-to-video` 主 agent 只负责准备上游资源、写一份精简的 handoff brief、调用 sub-agent，并对返回的 MP4 做 sanity check。

HyperFrames sub-agent 拥有以下工作：
- 基于 `narration.txt` 和 `transcribe/transcript.json` 切分 scene
- 可选的 scene 时间轴文件生成
- 基于 `material-catalog.json` 完成 material-to-scene 映射
- 视觉信息设计、布局、排版、动画与转场
- `composition/index.html` 和 `composition/DESIGN.md`
- `hyperframes lint`、`hyperframes inspect`，以及渲染迭代

#### 8.1 — 写 `composition-brief.md`

从 `references/composition-brief-template.md` 出发，写出 `{work_dir}/{topic_name}/composition-brief.md`，填入项目 metadata、输入路径，以及来自 Phase 1 的 style hint。 brief 要简短。

#### 8.2 — 调用一个 coding sub-agent

优先使用当前客户端 / runtime 原生的 sub-agent 或委派工具。prompt 要简短，且应让 sub-agent 自己从磁盘读 brief 文件，而不是把整份 brief 拼进 shell 命令里。

Prompt 示例：

```text
Read composition-brief.md in the current workspace and produce the deliverables.
Use the hyperframes and hyperframes-cli skills. You own scene segmentation,
material mapping, composition design, animation, lint/inspect fixes, and final
rendering. Before the FIRST render, do a self-audit against the Critical
Constraints in composition-brief.md (especially: subtitle is a single global
fixed element anchored at the bottom and never wraps; no element overflows the
viewport; simultaneously-shown elements don't overlap; title text boxes never
wrap to 2+ lines; font max/min <= 3) and fix what static inspection can catch
before rendering. Iterate until composition/renders/final.mp4 exists and
HyperFrames lint/inspect have no errors. Render with `--workers 1` to avoid
odd-height frame issues on this machine.
```

如果环境里没有原生 sub-agent 工具，仅当 CLI fallback 能把上面那段 prompt 原样传过去、并让 coding sub-agent 自己去读 `composition-brief.md` 时，才可以接受。

**不要**在主 agent 的会话里驱动 composition。

#### 8.3 — sanity-check 结果

sub-agent 返回后，从主 agent 验证：

```bash
ffprobe -v error -show_entries format=duration -of csv=p=0 \
  {work_dir}/{topic_name}/composition/renders/final.mp4
ls -la {work_dir}/{topic_name}/composition/renders/final.mp4
```

预期：duration 接近目标解说时长，文件大小 > 1 MB，且包含一条音频流。如果有异常，把症状反馈给 HyperFrames sub-agent。**不要**在主 agent 里手工 patch `composition/index.html`。

#### 8.4 — Post-Render Visual QA Audit

8.3 基础 sanity-check 通过后，主 agent 必须对 final.mp4 跑视觉抽帧 QA，覆盖 3 项**必须 render 后才能查**的质量项（静帧 ≤ 2s / 同图不跨 scene 复用 / 旁白与画面一致），以及 12 项静帧检查的复核。

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

**Step 5 — 静帧 12 项复核（spot-check）**

随机抽 `N = max(5, ceil(total_seconds / 30))` 张帧，对每张调 `vision-analyze.py`。**重渲轮**：只从上一轮 `affected_scenes` 中 scene 覆盖秒数对应的帧里抽样，不抽未改 scene 的帧。**例外**：若 `affected_scenes` 含 `global`（全局字幕容器被改动），字幕位置/遮罩会影响全片所有 scene（可能与未改 scene 的底部内容产生新遮挡或侵入安全带），此时字幕相关检查（⑦⑪⑫）**恢复全片抽样**，其余检查项仍可限定在被改 scene。

```bash
python3 scripts/vision-analyze.py \
  --prompt "检查这帧画面 12 项视觉质量（参考 composition-brief.md：Critical #2/#6/#7-#11、Upstream Contract #8/#9/#12、Style #13）：① 图片有无模糊 / 关键信息被裁切；② 任何元素是否超出画面边界 / 被截断；③ 同时显示的元素之间有无重叠遮挡；④ DOM 层次是否扁平（无 '框中套框'）+ 颜色对比度是否达标；⑤ 字号最大/最小比是否 ≤ 3；⑥ 内容区（视口去掉底部约 12-18% 字幕安全带后）有无 > 10% 视口的纯空白区域；⑦ 底部字幕安全带内除字幕条外是否混入了其他前景文本/callout/素材（侵入即 fail，全幅背景素材垫底不算）；⑧ 素材容器边框内是否出现 letterbox / pillarbox：素材与边框之间有露出容器底色的等宽空带（上下或左右）—— 有则 fail；⑨ 画面上是否有横贯/纵贯的扫描线、扫光、sweep、进度扫描条等覆盖层（用来糊弄'非静止'要求的运动条纹）—— 有则 fail；⑩ 标题文本框是否折成 2+ 行（任一标题/主标题位文本出现换行即 fail，参考 Critical #11）；⑪ 底部字幕是否位置稳定：水平居中、垂直锚定在底部字幕安全带内（不偏上压住内容、不在画面中部漂移），参考 Upstream Contract #12；⑫ 字幕是否单行 + 背景遮罩宽度贴合文字（无固定宽/整行宽造成的大片空遮罩），参考 Critical #6。逐项回答 pass/fail + 理由" \
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

下表列出 `composition-brief.md` 中每条 Visual Quality Constraint 由哪一步 QA 覆盖。标「仅创建期」的项渲染后不可（或难以）从抽帧静态判定，主要靠 8.2 的创建期 self-audit 与 sub-agent 自查保证，不进入 post-render fail/重渲循环。

| 约束 | QA 覆盖 |
|------|---------|
| Critical #1（每个 scene 5-8s） | 每轮解析 `data-scene-start/end` 区间校验时长（确定性、无 vision 成本，post-render 每轮都查）；时长是否「合理对应内容节奏」仅创建期 |
| Critical #2（静止 ≤ 2s） | Step 2（ffmpeg scene 滤波 / phash） |
| Critical #3（多文本随旁白逐个出现） | Step 4 部分覆盖；逐个出现节奏主要仅创建期 |
| Critical #4（图片持续动效） | Step 2 间接（静帧检测）；动效类型仅创建期 |
| Critical #5（素材占主体 ≥ 50%） | 仅创建期（未进 spot-check） |
| Critical #6（字幕单行 / shrink-to-fit） | Step 5 ⑪⑫ |
| Critical #7（图片清晰完整） | Step 5 ① |
| Critical #8（不超界 / 不截断） | Step 5 ② |
| Critical #9（不重叠） | Step 5 ③ |
| Critical #10（DOM 扁平 + 对比度） | Step 5 ④ |
| Critical #11（字号比 / 标题不换行） | Step 5 ⑤（字号比）+ ⑩（标题不换行） |
| Upstream #8/#9（素材比例 / 无 letterbox） | Step 5 ⑧ |
| Upstream #11（素材唯一性） | Step 3 |
| Upstream #12（字幕安全区 / 锚点） | Step 5 ⑦（侵入）+ ⑪（锚点稳定） |
| Style #12（scene 间过渡） | 仅创建期 |
| Style #13（居中 / 无大块留白） | Step 5 ⑥ |
| 旁白与画面一致 | Step 4 |

新增/调整 QA 检查项时，同步更新本表，保持「规则 ↔ 检查」一一对账。
