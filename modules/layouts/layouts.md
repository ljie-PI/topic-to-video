# 布局目录

布局规定画布、区域（`regions`）和字幕规格（`caption`）。**先逐个视觉 scene 选布局，再读对应的文档与 JSON**；JSON 是脚本和组件共用的机器契约，不能只凭示意图手算坐标。

## 可选布局

| layout | 画布（宽×高，px） | 适用画面 | 字幕：宽 / 字号 / 最大行数 | 文档 | 机器契约 |
|---|---:|---|---|---|---|
| `presenter` | 1920×1080 | 横屏，Jay 在右下角主持；主 / 副展示区、导航和字幕条 | 1166 / 36 / 1 | [presenter.md](presenter.md) | [presenter.json](presenter.json) |
| `stage` | 1920×1080 | 横屏，无主持人；全宽内容舞台 | 1728 / 36 / 1 | [stage.md](stage.md) | [stage.json](stage.json) |
| `portrait` | 1080×1920 | 9:16 竖屏，无主持人和顶部导航 | 940 / 42 / 2 | [portrait.md](portrait.md) | [portrait.json](portrait.json) |
| `portrait-3x4` | 1080×1440 | 3:4 竖屏，无主持人和顶部导航 | 940 / 40 / 2 | [portrait.md](portrait.md)（同一文档的 3:4 节） | [portrait-3x4.json](portrait-3x4.json) |

每份 JSON 都有 `canvas` / `regions` / `caption`。`regions[]` 的 `rect` 是 `{x, y, width, height}`；`kind: "content"` 是可放场景内容的区域，`kind: "reserved"` 是保留区域，并由 `component` 指定谁可以填。`caption` 是 `{width_px, font_size_px, max_lines}`；`id: "caption-text"` 区域的 `rect` 同时决定字幕在画布上的实际位置和外框。

## 全片画布固定，视觉 scene 的布局可变

- **画布由 `inputs.json` 的 `orientation` 在全片固定**：`landscape` = 1920×1080，`portrait` = 1080×1920，`portrait-3:4` = 1080×1440。同一个视频不能逐 scene 改画布尺寸或朝向。
- `composition/scene-config.json` 中每个视觉 scene 落盘自己的 `layout`（可空 `preset` + 完整 `regions` / `caption`）；因此**区域坐标、保留区域和字幕规格可以随视觉 scene 改变**，rect 不得超出全片朝向固定的画布。
- 不要回到 `inputs.json` 指定全片 `layout`：preset 是逐 scene 的可选借用，也可以自主设计自由布局（`preset: null`，无需注册）。视觉 scene 的 `begin_s` / `end_s` 使用视频秒；合法配置必须主区间有序、不重叠，从 0 覆盖到 `total_s`。
- `stage`、`portrait` 和 `portrait-3x4` 没有人物区；只有 `presenter` 显示 Jay。字幕组件仍全片只挂一次，通过 `VIDEO.captionSegments` 在视觉 scene 边界切换区域和字幕规格。

示例：

schema 以 `references/delegation/composition/scene-config.md` 契约为准，每个
scene 的 `layout` 必须落盘完整 `regions` / `caption`（下面是自由布局 scene 的
骨架，区域坐标须落在画布内）：

```json
{
  "scene_id": "demo",
  "begin_s": 0,
  "end_s": 4,
  "template": null,
  "layout": {
    "preset": "stage",
    "regions": [
      {"id": "main", "kind": "content", "rect": {"x": 96, "y": 100, "width": 1728, "height": 820}},
      {"id": "caption-text", "kind": "reserved", "component": "caption-bar", "rect": {"x": 96, "y": 1008, "width": 1728, "height": 72}}
    ],
    "caption": {"width_px": 1728, "font_size_px": 36, "max_lines": 1}
  }
}
```

## 数据产物与组件的对应关系

用 `align-narration.py --mode subtitles --scene-config composition/scene-config.json` 生成 `composition/assets/subtitle-units.json`，不要在组装脚本里重新推导字幕边界或容量。产物直接映射到常驻组件数据：

- `subtitle-units.json` 的 `units[]` → `VIDEO.captions[]`：`begin_s` → `start`，`end_s` → `end`，`text` 原样复制；
- `caption_segments[]` → `VIDEO.captionSegments[]`：整项原样复制，保留 `begin_s` / `end_s`、`caption_rect` 和 `caption`；
- scene-config 的 `scenes[]` → `VIDEO.jay.placements[]`：`begin_s` / `end_s` 原样复制，仅 regions 有人物区（`component` 为 `jay` 的 reserved 区）的 scene 为 `visible: true`，其余为 `visible: false`。可见项的位置取该 scene 人物区 rect：`x = rect.x`、`y = rect.y`、`size = rect.width`。

完整字段、缺省行为和动画边界见 [caption-bar 组件文档](../components/caption-bar/caption-bar.md) 与 [Jay 组件文档](../components/jay/jay.md)。
