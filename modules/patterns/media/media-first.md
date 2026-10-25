# Pattern：media-first（媒体优先）

一张主图（screenshot、figure、照片）是这个 scene 的核心证据，文字只作少量辅助。本文件是建议，不是规则。

## 适用场景和触发信号

- 单个主图片 / screenshot / figure，且没有命中更高优先级的特殊呈现（viewport-reveal、band、detail-callout 等）。
- 场景规划里 `layout_role = "media_first"`，或旁白以「看图说话」的方式围绕一张图展开。
- 图片证据占据内容区主体，信息在外部或分时解释；跨朝向时保留 media-first 语义，另选合法的 reveal 策略。

## 区域尺寸建议

- 主图按可用宽高共同计算尺寸：先算内容区里能放下的最大等比矩形，再给外置信息留位置。
- 横屏内容区参考：`layouts/presenter.md` 主展示区 1048×788、`layouts/stage.md` 主展示区 1728×764；竖屏见 `layouts/portrait.md`（940×1240 或 940×880）。
- 标题、信息块不适合压得主媒体过小；文字放不下的处理顺序建议：换行（区域允许时）→ 区域内缩小 → 删减次要文字。

## 横屏摆法

- 宽幅图：主体 + 外置信息区 / metadata band / 分时解释区，不要压缩素材。
- 方形或 UI screenshot：居中或偏侧主体 + 外置信息块；信息过多时只保留最重要的信息单元。
- 论文 figure / 表格 / 图表类素材：保留来源图形、轴线、图例、caption、关键曲线 / 行，外置解释 1–3 个结论。

## 竖屏摆法

- 横图 / 横截图：原比例的 wide media slab 放在上部或中上部。
- 竖图：宽度驱动，必要时改用 `patterns/media/viewport-reveal.md` 沿长轴 reveal。
- 横屏竖图想做侧栏时，建议要么配足够的短 callout / data units 填满侧栏，要么收窄侧栏改用 reveal；避免只放一个小标题造成大留白。
- 内容区先扣除底部字幕区再规划（见 `layouts/portrait.md`）。

## 动效候选与应避免

候选：camera intent、focal traversal、外置 annotation、分时信息出现。

避免：文字动画抢占或覆盖素材关键区域；主媒体不必要地压小或让位给文字；整图一次性淡入后画面静止到结束。

## 用色

- 外观全部来自所选主题的 token（`designs/designs.md`），pattern 本身不引入新颜色。
- 图中标注 / pin / marker 可用 `--c-focus` 或真实状态色（信息 / 警示 / 危险语义）；标注文字保持 `--c-ink` / `--c-ink2`，标注尽量放在素材外部。
- 各主题没有特殊覆盖。

## 已有实现

尚无。
