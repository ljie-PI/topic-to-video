# Phase 9 — 检查与混音

## 输入

- Phase 8 产出的 `composition/renders/final.mp4`；
- `composition/design.json`（Phase 8 落盘的 preset / custom 全片外观基线，QA 不看 `inputs.json` 猜设计）；
- `composition/scene-config.json`（最终视觉场景机器配置与全片秒；本阶段 QA 的 scene_id、抽帧和反馈范围以它为准；旧单 layout 工程才沿用 `transcribe/timeline.json` 的可选叙事 scenes）；
- `inputs.json`（`qa_level`、BGM 选择）；
- `search-notes.md`（可选，Phase 4 记录的来源限制，用于交付说明）。

## 输出

- `qa/`（contact sheet 拼图 + `qa/qa-report.json`）；
- `composition/renders/final_with_bgm.mp4`（解说 + 低音量背景乐的最终成片）。

## 完成判据

- `qa/qa-report.json` 存在且含 `findings` + `verdict` 两部分（修复轮结束后 verdict 为 `pass` 或 `handed_off`）；
- `composition/renders/final_with_bgm.mp4` 存在且非空；
- 解说音量不变，BGM 按默认线性增益 `0.03` 垫在底下。

## 执行后自检

本阶段的检查已经写在下面的流程里（确定性检查 + 按 `qa_level` 的 vision 检查 + 最多两轮修复），不需要额外再看别的东西。根据问题类型决定退回哪一层，而不是硬改：

- catalog 阶段适用时，必用素材（catalog 的 `required_material_refs`）没在成片里出现，或关键图看不清：交回 Phase 8 补上，不要只记一笔就放行。

- 黑屏、冻结、音画时长不符、渲染残缺：留在本阶段，交回 composition agent 修。
- 画面与旁白对不上：可能是叙事或场景计划的问题，按 `references/pipeline-control.md` 找到对应阶段，不要只改画面。
- 两轮后 finding 数不再下降：把报告标为 `handed_off` 连同 sheet 交回用户，不要反复重试。

## 下一步

无——这是最后一个 phase。把成片与 contact sheet 交给用户过目。

## 护栏

无

---

渲染完成后，QA 分确定性检查、vision 检查、修复轮三步，全程**不做全片抽帧**；最后混入 BGM。检查集由 `inputs.json` 的 `qa_level` 决定（缺省视为 `standard`）：

| 档位 | 渲染前检查（Phase 8） | 确定性检查 | contact sheet | vision 检查 |
| --- | --- | --- | --- | --- |
| `quick` | 做 | 做 | 生成（仅给用户过目，不做 vision） | 不做 |
| `standard` | 做 | 做 | 做 | 做 |
| `strict` | 做 | 做 | 做（额外帧见下） | 做 |

#### 9.1 — 确定性检查（所有档位都做，主 agent 执行）

```bash
python3 scripts/check-render.py \
  --video {work_dir}/{topic_name}/composition/renders/final.mp4 \
  --inputs {work_dir}/{topic_name}/inputs.json \
  --timeline {work_dir}/{topic_name}/composition/scene-config.json
```

一个脚本跑完三类检查（stdout 一个 JSON，verdict 为 pass / fail）：

- **ffprobe 容器检查**：有音轨；容器时长与音轨时长偏差 ≤ 0.5s；分辨率等于 `inputs.json` 的 `orientation` 对应的精确画布（横屏 1920×1080；显式 9:16 为 1080×1920；竖屏 3:4 为 1080×1440）；两个竖屏比例不互相代替。
- **黑屏检测**：ffmpeg `blackdetect`（默认 ≥ 0.5s 的黑段报警，另报片尾黑尾）。
- **冻结检测**：ffmpeg `freezedetect`，默认阈值 4s，`--freeze-threshold` 可调。

黑屏 / 冻结的发现带 `scene_id`：按 `composition/scene-config.json` 的最终视觉场景时间范围映射（`--timeline` 直接读它的 `scenes`，只取 scene_id / begin_s / end_s）；主区间按 `[begin_s, end_s)` 归属，不在任何 scene 内时取中点最近的 scene。旧单 layout 工程没有 scene-config 时，才传入 `timeline.json` 的可选叙事 scenes（没有则为 null）。

#### 9.2 — contact sheet（所有档位都生成，quick 到此为止）

```bash
python3 scripts/make-contact-sheet.py \
  --video {work_dir}/{topic_name}/composition/renders/final.mp4 \
  --timeline {work_dir}/{topic_name}/composition/scene-config.json \
  --inputs {work_dir}/{topic_name}/inputs.json \
  --output-dir {work_dir}/{topic_name}/qa
```

脚本直接读取 `inputs.json` 的 `qa_level`：缺省、`quick`、`standard` 都按 standard 抽帧，`strict` 按 strict 抽帧；输出 JSON 的 `vision_check_required` 在 quick 档为 `false`，其余为 `true`。quick 档同样生成拼图给用户过目，只是不做 vision 检查。

每个最终视觉 scene 在 scene 中点抽 1 帧，每 4 帧拼一张 2×2 拼图（Pillow 标注 scene_id + 帧类型 + 时间戳），写入 `qa/sheet_NNN.jpg`。strict 档额外帧：**每个视觉 scene 一张入场帧**（scene 起点 + 0.25s）+ **每个切点三张**（下一个 scene 的实际 `begin_s` 前 0.4s / 切点 / 切点后 0.4s，切点即上一个 scene 的 `end_s`）。旧工程才用 timeline 的叙事 scenes。

**vision 成本**：contact sheet 按 4 帧一张组织，vision 以 sheet 为单位调用——一支约 40 scene 的片子，standard 档抽 40 帧 ≈ `ceil(40/4)` = 10 张 sheet，vision 调用 ≈ 10 次，正好是 scene 数的四分之一。

#### 9.3 — vision 检查（`vision_check_required` 为 true 时，主 agent 执行）

看 9.2 输出 JSON 的 `vision_check_required` 决定是否执行本节；为 `false` 时跳过。为 `true` 时，主 agent 自己逐张看 `qa/sheet_NNN.jpg`（用 `view` 工具；sheet 同时交给用户过目），每张只回答 4 项：

1. 渲染是否完整（无缺帧、无渲染中断导致的残帧）；
2. 画面与旁白是否相符；
3. 是否符合 `composition/design.json` 的 preset 或 custom 配色与观感；scene 限定的 token 覆盖是否只作用于声明的 scene，没有外泄到其他 scene；
4. 有没有明显的空洞或错位。

除此之外不做别的视觉判断；动效与转场的观感默认交给用户在预览中判断。

#### 9.4 — qa-report.json 与修复轮

把确定性检查结果与 vision 判断合并写入 `qa/qa-report.json`，**只含两部分**：

```json
{
  "findings": [{"scene_id": "scene_3", "check": "black_screen", "issue": "...", "time_s": 12.5, "frame": null}],
  "verdict": "pass"
}
```

所有 finding 统一为 `{"scene_id": str, "check": str, "issue": str, "time_s": float|null, "frame": str|null}`。确定性检查（check-render / check-composition）的 finding 原样拷进 qa-report；vision 检查的 finding 由主 agent 按同样形状写。`time_s` 填检测或快照时刻，没有对应时刻填 `null`；vision finding 的 `frame` 填相关 sheet 路径，确定性检查的 `frame` 为 `null`。`verdict` 为 `fail` 时进入修复轮，规则：

1. 把 findings 反馈给 composition agent（Phase 8 委派约定），**只改受影响的 scene**；
2. 修复若改了 composition 的源文件或视觉契约（`design.json`、`scene-config.json`、`index.html`、`compositions/`、`assets/`、`storyboard.md`），必须重跑 check-composition 用 `--output` 保存新报告，并**重新渲染** `final.mp4`——只重跑 check-render 会让报告和渲染比源文件旧，`pipeline-status` 会回退 Phase 8、卡住 Phase 9；然后确定性检查全片重跑；vision 只看受影响视觉 scene 的帧（单独抽帧看即可，不必重拼整组 sheet）；
3. **最多 2 轮**；finding 数不再下降就停止，把报告标为 `handed_off` 连同 sheet 一起交还用户定夺。

修复轮结束（verdict 为 `pass`，或 `handed_off` 交给用户）后 `pipeline-status` 才会放行进 BGM 混音。

#### 9.5 — BGM 混音（逻辑不变）

```bash
python3 scripts/mix-bgm.py \
  --video {work_dir}/{topic_name}/composition/renders/final.mp4 \
  --output {work_dir}/{topic_name}/composition/renders/final_with_bgm.mp4
```

混音脚本逻辑保持不变：一次 ffmpeg pass 循环 `--bgm`（默认 `resources/bgm.mp3`，24 秒可循环片段）填满整个视频时长、以 `--bgm-volume`（默认线性增益 `0.03`）垫在解说底下、`-c:v copy` 不重编码视频流。如需换曲或调音量用 `--bgm` / `--bgm-volume`。**BGM 混的是修复轮之后的 `final.mp4`**——QA 通过后才生成最终交付文件。

#### 9.6 — 交付时说明素材限制

把成片与 contact sheet 交给用户时，一并说明素材阶段留下的限制。信息来自工作区的 `search-notes.md`（Phase 4 写的可选记录，不是阶段产物，缺失就不提）：

- 哪些来源未被获取（需登录 / 地区限制 / 反机器人验证 / 已下线），以及用什幺替代或是否接受 B-roll 少一些。
- 只能匿名抓到的站点：说明共享 profile 里已有登录态时会尽量用上，但登录不保证绕过平台其他限制。
- 用户希望补抓时的入口：在 `{work_dir}/chrome_profile` 里登录后要求重跑 Phase 4（按 `references/pipeline-control.md` 登记 `--redo 4-material-harvest`），再按依赖让下游重做。

这不影响 QA 结果，不写成 `qa-report.json` 的 finding，也不是新的审稿环节。
