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
rendering. Iterate until composition/renders/final.mp4 exists and HyperFrames
lint/inspect have no errors. Render with `--workers 1` to avoid
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

8.3 基础 sanity-check 通过后，主 agent 必须对 final.mp4 跑视觉抽帧 QA，覆盖 3 项**必须 render 后才能查**的质量项（静帧 ≤ 2s / 同图不跨 scene 复用 / 旁白与画面一致），以及 7 项静帧检查的复核。

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

扫 `composition/index.html` 与各 scene 子模板（如有），按 Upstream Contract #10 的 `data-scene-id` 划分 scene 块，提取每个块内的 `<img src=>`、`<video src=>`、`background-image: url(...)`。建立 `src → [scene_ids]` 映射；同一 src 出现在 ≥ 2 个 `scene_id` 内 → 标记 `reused_material` 违规，finding 中列出所有命中的 `scene_ids`。例外：DESIGN.md 中明确标注 "intentional callback" 的素材豁免。

**Step 4 — 旁白对齐检测**

按 `transcribe/transcript.json` 中的句子（句号 / 问号 / 感叹号边界）切分；每句覆盖的秒数对应若干抽帧。对每个 `(句, 帧集合)` 调 `vision-analyze.py`：

```bash
python3 scripts/vision-analyze.py \
  --prompt "旁白说：'<句子原文>'。下列帧画面是否在视觉上表达了这句旁白的含义？回答 yes/partial/no + 一句话理由。注意检查：① 帧中是否出现该句提到的实体（人名、产品、数字）；② 多元素逐个出现的场景，逐帧出现节奏是否与旁白同步" \
  --images <该句覆盖秒数对应的 frame_XXXX.jpg 列表>
```

任何 `no` / `partial` 标记为 `narration_mismatch` 违规。**每条 finding 必须带 `scene_id`（用句子覆盖的秒数中点查 `data-scene-start/end` 区间得到，跨 scene 时列出所有命中）。**

**Step 5 — 静帧 7 项复核（spot-check）**

随机抽 `N = max(5, ceil(total_seconds / 30))` 张帧，对每张调 `vision-analyze.py`：

```bash
python3 scripts/vision-analyze.py \
  --prompt "检查这帧画面 6 项视觉质量（参考 composition-brief.md Critical Constraints #7-#11 与 Style #13）：① 图片有无模糊 / 关键信息被裁切；② 任何元素是否超出画面边界 / 被截断；③ 同时显示的元素之间有无重叠遮挡；④ DOM 层次是否扁平（无 '框中套框'）+ 颜色对比度是否达标；⑤ 字号最大/最小比是否 ≤ 3 + 大标题是否未自动换行；⑥ 有无 > 10% 视口的纯空白区域。逐项回答 pass/fail + 理由" \
  --images <随机抽的 frame_XXXX.jpg>
```

每项 fail 加入 `spot_check_fails`。**每条 finding 必须带 `scene_id`（用该帧秒数查 `data-scene-start/end` 区间得到）。**

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

`affected_scenes` = 上述 4 个数组中所有 finding 涉及的 `scene_id` 去重并按视频时间顺序排序。`verdict = "pass"` 当且仅当 4 个数组都为空（此时 `affected_scenes` 也为空）。

**Step 7 — 决策**

- `verdict == "pass"` → 进 Phase 9（bgm-mix）
- `verdict == "fail"` → 把 `qa-report.json` 与症状原文反馈给 HyperFrames sub-agent，**明确要求**：
  - **只修改 `affected_scenes` 列表中的 scene**（按 `data-scene-id` 定位）；未在该列表中的 scene 的 DOM 结构、CSS、动画时间轴必须**逐字节保持不变**，包括其 `data-scene-id` / `data-scene-start` / `data-scene-end`。
  - 修复时如果 scene 时长变化（违反 Critical #1 的 5-8 秒约束），需要在 DESIGN.md 中记录新的时间布局，并更新所有受影响 scene 的 `data-scene-start` / `data-scene-end`；但**未受影响 scene 的时间区间不得调整**——若 sub-agent 认为必须重排整片时间轴，应在反馈中明确说明并升级为整片重渲。
  - 修复完成后回到 8.3 重新跑 sanity-check + 8.4 QA，直到 `verdict == "pass"`。
  - **重试次数**：同一 `affected_scenes` 集合连续 2 次重渲仍 fail，主 agent 应停下来汇总当前 `qa-report.json` 给用户，由用户决定是接受降级、人工介入修 HTML，还是回退到更早的 phase 调整素材 / 解说脚本。

**不要**在主 agent 里手工 patch `composition/index.html`。所有视觉问题的修复都必须委派回 sub-agent；主 agent 只是质检员，不是作者。
