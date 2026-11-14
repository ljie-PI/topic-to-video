# Phase 10 — BGM 混音与交付（可选；`inputs.json` 的 `bgm = false` 时跳过）

本 phase 默认开启（`inputs.json` 的 `bgm` 缺省或为 `true` 时进入）；仅当用户明确不要背景音乐、在 `inputs.json` 写入 `bgm = false` 时，`pipeline-status` 跳过本阶段。

## 输入

- Phase 9（`9-check`）收尾后的 `composition/renders/final.mp4`；
- `qa/`（`qa/qa-report.json` 与 `qa/sheet_NNN.jpg` contact sheet，交付时一并给用户过目）；
- `inputs.json`（可选布尔字段 `bgm`）；
- `search-notes.md`（可选，Phase 4 记录的来源限制，用于交付说明）。

## 输出

- `composition/renders/final_with_bgm.mp4`（解说 + 低音量背景乐的最终成片）。

## 完成判据

- `composition/renders/final_with_bgm.mp4` 存在且非空（由状态脚本校验）；
- 解说音量不变，BGM 按默认线性增益 `0.03`（或用户指定的音量 / 曲目）循环垫在底下。

## 执行后自检

- 确认混音输入是 Phase 9 修复轮收尾后的最新 `composition/renders/final.mp4`（若此前登记重做过 Phase 8 / Phase 9，须对更新后的 `final.mp4` 重新运行 `mix-bgm.py` 覆盖旧混音成片）。
- 核对 `mix-bgm.py` 输出 JSON 的 `duration_s` 与 `final.mp4` 一致、旁白音量未被压低。
- 若 `qa/qa-report.json` 的 `verdict` 为 `handed_off`，交付成片时把未收敛的 findings 与 contact sheet 一并交给用户定夺。

## 下一步

无——这是最后一个 phase。把 `composition/renders/final_with_bgm.mp4` 与 `qa/` 下的 contact sheet 交给用户过目。

## 护栏

- **只在 Phase 9 收尾后混音，不重编码视频流、不衰减旁白。** 统一调用 `scripts/mix-bgm.py`（`-c:v copy`、`amix normalize=0`），不覆盖原 `composition/renders/final.mp4`。
  ↳ DO NOT：在 `qa/qa-report.json` 收尾前提前混音，或手写未关闭 `normalize` 的 `ffmpeg amix` 命令导致旁白音量被减半。

---

#### 10.1 — BGM 混音

```bash
source .venv/bin/activate && python3 scripts/mix-bgm.py \
  --video {work_dir}/{topic_name}/composition/renders/final.mp4 \
  --output {work_dir}/{topic_name}/composition/renders/final_with_bgm.mp4
```

一次 ffmpeg pass 循环 `--bgm`（默认 `resources/bgm.mp3`，24 秒可循环片段）填满整个视频时长、以 `--bgm-volume`（默认线性增益 `0.03`）垫在解说底下、`-c:v copy` 不重编码视频流。用户要求换曲或调音量时传 `--bgm` / `--bgm-volume`；只调整曲目或音量时只需 `--redo 10-mix`，不必重跑 Phase 9 的成片 QA。

#### 10.2 — 交付时说明素材限制

把成片与 contact sheet 交给用户时，一并说明素材阶段留下的限制。信息来自工作区的 `search-notes.md`（Phase 4 写的可选记录，不是阶段产物，缺失就不提）：

- 哪些来源未被获取（需登录 / 地区限制 / 反机器人验证 / 已下线），以及用什么替代或是否接受 B-roll 少一些。
- 只能匿名抓到的站点：说明共享 profile 里已有登录态时会尽量用上，但登录不保证绕过平台其他限制。
- 用户希望补抓时的入口：在 `{work_dir}/chrome_profile` 里登录后要求重跑 Phase 4（按 `references/pipeline-control.md` 登记 `--redo 4-material-harvest`），再按依赖让下游重做。

这不影响 QA 结果，不写成 `qa-report.json` 的 finding，也不是新的审稿环节。
