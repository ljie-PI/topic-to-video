# Phase 9 — 成片检查

## 输入

- `composition/renders/final.mp4`（Phase 8 渲染成片）；
- `composition/design.json`（Phase 8 落盘的 preset / custom 外观基线）；
- `composition/scene-config.json`（最终视觉场景机器配置与全片秒；本阶段抽帧、`scene_id` 归属与反馈范围均以它为准）；
- `composition/check-composition.json` 与 `composition/storyboard.md`（供 vision 检查定向复核渲染前留下的非阻塞 `warnings` 及场景设计意图）；
- `inputs.json`（`qa_level`、可选布尔开关 `bgm` / `cover`）；
- `search-notes.md`（可选，Phase 4 记录的来源限制；`bgm = false` 且 `cover = false` 在本阶段直接交付时一并说明）。

## 输出

- `qa/`（contact sheet 拼图 `qa/sheet_NNN.jpg` + `qa/qa-report.json`）。

## 完成判据

- `qa/qa-report.json` 存在且只含 `findings` + `verdict` 两个字段（修复轮收尾后 `verdict` 为 `pass` 或 `handed_off`）。

## 执行后自检

按下方 9.1–9.4 完成确定性检查、contact sheet 与按 `qa_level` 的 vision 检查后，按问题性质定向回退（最多修复 2 轮）：

- **交回 Phase 8 composition agent（限定受影响 scene 修复）**：黑屏、冻结、音画时长不符、渲染残缺；`required_material_refs` 必用图 / 表未上屏或看不清；贴合场景的可用通用素材被无故弃用；非技术深讲违规跨场复用素材，或连续深讲同一张技术图时加了打断性过场 / 未推进局部 zoom；无真实素材场景退化为纯排版静态卡片而未做动态内容演绎。
- **回退更早阶段**（按 `references/pipeline-control.md` 定位）：画面与旁白逻辑错位属叙事或场景规划问题，不靠硬改画面掩盖。
- **两轮未收敛**：2 轮修复后 finding 数未继续下降时，置 `verdict: "handed_off"` 连同 contact sheet 交由用户定夺，禁无限重试或伪造 `pass`。

## 下一步

运行 `python3 scripts/pipeline-status.py {work_dir}/{topic_name}`：

- `bgm` 缺省或为 `true`：进入 Phase 10（`10-mix`）混入背景乐；
- `bgm = false` 且 `cover` 缺省或为 `true`：跳过 Phase 10，进入 Phase 11（`11-cover`）生成多尺寸封面后统一交付；
- `bgm = false` 且 `cover = false`：跳过 Phase 10 与 Phase 11（`next_phase` 为 `null`），直接交付 `composition/renders/final.mp4` 与 contact sheet，并按 9.5 汇总可选的素材限制。

## 护栏

- **全程禁止全片逐秒密集抽帧。** 统一用 `scripts/check-render.py` 做容器 / 黑屏 / 冻结检测，再用 `scripts/make-contact-sheet.py` 按视觉 scene 抽帧拼成 2×2 sheet 供视觉检查。
- **修复轮改过画面必须重跑 `check-composition` 并重新渲染 `final.mp4`（最多 2 轮）。** 禁只改源码不重渲染就复检。

---

成片 QA 按 `inputs.json` 的 `qa_level`（缺省为 `standard`）分四步执行：

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

脚本一次输出三类检查结果 JSON（`verdict` 为 `pass` / `fail`）：

- **ffprobe 容器检查**：含音轨；容器与音轨时长差 ≤ 0.5s；分辨率精确匹配 `orientation`（横屏 `1920×1080`、9:16 竖屏 `1080×1920`、3:4 竖屏 `1080×1440`，两档竖屏不互代）。
- **黑屏检测**：ffmpeg `blackdetect`（默认 ≥ 0.5s 报警，另报片尾黑尾）。
- **冻结检测**：ffmpeg `freezedetect`（默认 ≥ 4s 报警，`--freeze-threshold` 可调）。

黑屏 / 冻结按 `composition/scene-config.json` 的 `[begin_s, end_s)` 归属 `scene_id`（落点在区间外时取中点最近的 scene）。

#### 9.2 — contact sheet（所有档位都生成，quick 到此为止）

```bash
python3 scripts/make-contact-sheet.py \
  --video {work_dir}/{topic_name}/composition/renders/final.mp4 \
  --timeline {work_dir}/{topic_name}/composition/scene-config.json \
  --inputs {work_dir}/{topic_name}/inputs.json \
  --output-dir {work_dir}/{topic_name}/qa
```

脚本按 `qa_level` 抽帧并每 4 帧拼一张 2×2 `qa/sheet_NNN.jpg`（标注 `scene_id` + 帧类型 + 时间戳；vision 调用次数约为 scene 数的 1/4）：

- `quick` / `standard`：每个视觉 scene 中点抽 1 帧（`quick` 档输出 `vision_check_required: false`，仅供用户预览）；
- `strict`：除中点帧外，额外抽**每个视觉 scene 入场帧**（起点 + 0.25s）与**每个切点前后三帧**（切点前 0.4s / 切点 / 切点后 0.4s）。

#### 9.3 — vision 检查（`vision_check_required` 为 true 时，主 agent 执行）

结合 `composition/check-composition.json` 的 `warnings` 与 `composition/storyboard.md`，用看图工具逐张检查 `qa/sheet_NNN.jpg`（同时交用户过目），核对 5 项：

1. **渲染完整性**：无缺帧或渲染中断残帧；
2. **内容与动画演绎**：画面符合旁白与 `content_plan`；无真实素材场景已用具体视觉图示与分步动画（`SVG → WebGL → Three.js → GSAP`）生动演进，未退化为静态文字卡片、纯排版列表或无关装饰图形；
3. **素材清晰度与单场景分配**：复核 `warnings` 中的可视占比、源片失焦/压缩马赛克或过度缩放模糊；非技术深讲未跨场重复素材；连续深讲同一张技术图的相邻场景切点无打断性过场，并推进局部 zoom 焦点（而非整图静止只换文字）；
4. **主题质感与作用域**：符合 `composition/design.json` 的配色、细线层级与透纸纹质感，单 scene 限定的 token 覆盖未外泄；
5. **版式清爽无复读**：无明显空洞、错位、文字出框/遮挡，主副展示区（`main` / `side`）无重复文案堆砌。

单张中点帧不足以确认“连续技术图切点无过场 / 局部 zoom 推进”或“无素材分步动画演进”时，对照 `storyboard.md` 对涉及时刻按需单点抽帧核对（`strict` 档可直接看入场帧与切点三帧）；纯审美层面的缓动观感默认交给用户在预览中判断。

#### 9.4 — qa-report.json 与修复轮

合并确定性检查与 vision 结果写入 `qa/qa-report.json`（仅含两个顶层键）：

```json
{
  "findings": [{"scene_id": "scene_3", "check": "black_screen", "issue": "...", "time_s": 12.5, "frame": null}],
  "verdict": "pass"
}
```

每条 finding 统一为 `{"scene_id": str, "check": str, "issue": str, "time_s": float|null, "frame": str|null}`：`time_s` 填检测或快照时刻，没有对应时刻填 `null`；确定性 finding 原样拷入且 `frame: null`，vision finding 的 `frame` 填对应 sheet 路径。`verdict == "fail"` 时进入修复轮：

1. 将 findings 交回 Phase 8 composition agent，**只改受影响的 scene**；
2. 若修改了 composition 源码或契约文件，**必须重跑 `check-composition --output` 并重新渲染 `final.mp4`**；随后全片重跑 `check-render.py`，vision 仅抽帧复核受影响 scene（无需重拼整套 sheet）；
3. **最多 2 轮**；finding 数不再下降则置 `verdict: "handed_off"` 连同 sheet 交用户定夺。

#### 9.5 — 无 BGM 且无封面（`bgm = false` 且 `cover = false`）直接交付时的素材限制说明

`bgm = false` 且 `cover = false` 跳过 Phase 10 / 11 直接交付 `final.mp4` 与 contact sheet 时，若工作区存在 `search-notes.md`，按 `references/phases/10-mix.md` 的「10.2 交付时说明素材限制」一并向用户说明受限来源与补抓方式（不计入 `qa-report.json`）。
