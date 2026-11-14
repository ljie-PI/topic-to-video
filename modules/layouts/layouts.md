# 布局目录

布局规定画布、区域（`regions`）和字幕规格（`caption`）。每个视觉 scene 按 [composition 基础指令第四部分](../../references/delegation/composition/base-instructions.md#四内容演绎与模板选择) 决定布局：只在用户明确指定，或某个 preset 的区域划分、保留区域与当前 scene 的素材比例、信息密度**特别匹配**时才借用该 preset（模板的 `preferred_layouts` 只作建议），选中后再读对应的文档与 JSON；JSON 是脚本和组件共用的机器契约，不能只凭示意图手算坐标。无特别匹配时写 `preset: null`，即时设计本 scene 的 `regions` / `caption`。

## 可选布局

布局预设按「画布规格 × 是否带主持人（`-presenter`）」正交命名：

| layout | 画布（宽×高，px） | 适用画面 | 字幕：宽 / 字号 / 最大行数 | 文档 | 机器契约 |
|---|---:|---|---|---|---|
| `landscape` | 1920×1080 | 横屏，无主持人；全宽内容舞台、导航和底部字幕条 | 1728 / 36 / 1 | [landscape.md](landscape.md) | [landscape.json](landscape.json) |
| `landscape-presenter` | 1920×1080 | 横屏，人物在右下角主持；主 / 副展示区、导航和字幕条 | 1166 / 36 / 1 | [landscape-presenter.md](landscape-presenter.md) | [landscape-presenter.json](landscape-presenter.json) |
| `portrait` | 1080×1920 | 9:16 竖屏，无主持人和顶部导航 | 940 / 42 / 2 | [portrait.md](portrait.md) | [portrait.json](portrait.json) |
| `portrait-3x4` | 1080×1440 | 3:4 竖屏，无主持人和顶部导航 | 940 / 40 / 2 | [portrait.md](portrait.md)（同一文档的 3:4 节） | [portrait-3x4.json](portrait-3x4.json) |
| `portrait-presenter` | 1080×1920 | 9:16 竖屏，人物在右下角主持；全宽页眉与主展示区、底部双行字幕条 | 600 / 38 / 2 | [portrait-presenter.md](portrait-presenter.md) | [portrait-presenter.json](portrait-presenter.json) |
| `portrait-3x4-presenter` | 1080×1440 | 3:4 竖屏，人物在右下角主持；全宽页眉与主展示区、底部双行字幕条 | 600 / 36 / 2 | [portrait-presenter.md](portrait-presenter.md)（同一文档的 3:4 节） | [portrait-3x4-presenter.json](portrait-3x4-presenter.json) |

每份 JSON 都有 `canvas` / `regions` / `caption`。`regions[]` 的 `rect` 是 `{x, y, width, height}`；`kind: "content"` 是可放场景内容的区域，`kind: "reserved"` 是保留区域，并由 `component` 指定谁可以填。`caption` 是 `{width_px, font_size_px, max_lines}`；`id: "caption-text"` 区域的 `rect` 同时决定字幕在画布上的实际位置和外框。

## 全片画布固定，视觉 scene 的布局可变

- **画布由 `inputs.json` 的 `orientation` 在全片固定**：`landscape` = 1920×1080，`portrait` = 1080×1920，`portrait-3:4` = 1080×1440。同一个视频不能逐 scene 改画布尺寸或朝向。
- `composition/scene-config.json` 中每个视觉 scene 落盘自己的 `layout`（可空 `preset` + 完整 `regions` / `caption`）；因此**区域坐标、保留区域和字幕规格可以随视觉 scene 改变**，rect 不得超出全片朝向固定的画布。
- 不要回到 `inputs.json` 指定全片 `layout`：preset 是逐 scene 的可选借用，也可以自主设计自由布局（`preset: null`，无需注册）。视觉 scene 的 `begin_s` / `end_s` 使用视频秒；合法配置必须主区间有序、不重叠，从 0 覆盖到 `total_s`。
- `landscape`、`portrait` 和 `portrait-3x4` 没有人物区；`landscape-presenter`、`portrait-presenter` 和 `portrait-3x4-presenter` 声明人物区并显示 `presenter` 组件。字幕与人物组件仍全片只挂一次，分别通过 `VIDEO.captionSegments` 与 `VIDEO.presenter.placements` 在视觉 scene 边界切换区域、显隐和字幕规格。

示例：

schema 以 `references/delegation/composition/scene-config.md` 契约为准，每个
scene 的 `layout` 必须落盘完整 `regions` / `caption`（下面是借用 `landscape`
预设的单个 scene 条目示例，区域坐标与 `landscape.json` 一致）：

```json
{
  "scene_id": "demo",
  "source_scene_ids": ["scene_1"],
  "begin_s": 0,
  "end_s": 4,
  "template": null,
  "layout": {
    "preset": "landscape",
    "regions": [
      {"id": "ground", "kind": "reserved", "component": "ground", "rect": {"x": 0, "y": 0, "width": 1920, "height": 1080}},
      {"id": "nav-bar", "kind": "reserved", "component": "nav-bar", "rect": {"x": 0, "y": 0, "width": 1920, "height": 72}},
      {"id": "header", "kind": "content", "rect": {"x": 96, "y": 100, "width": 1728, "height": 72}},
      {"id": "main", "kind": "content", "rect": {"x": 96, "y": 196, "width": 1728, "height": 764}},
      {"id": "caption-bar", "kind": "reserved", "component": "caption-bar", "rect": {"x": 0, "y": 1008, "width": 1920, "height": 72}},
      {"id": "caption-text", "kind": "reserved", "component": "caption-bar", "rect": {"x": 96, "y": 1008, "width": 1728, "height": 72}}
    ],
    "caption": {"width_px": 1728, "font_size_px": 36, "max_lines": 1}
  }
}
```

## 数据产物与组件的对应关系

用 `align-narration.py --mode subtitles --scene-config composition/scene-config.json` 生成 `composition/assets/subtitle-units.json`，不要在组装脚本里重新推导字幕边界或容量。产物直接映射到常驻组件数据：

- `subtitle-units.json` 的 `units[]` → `VIDEO.captions[]`：`begin_s` → `start`，`end_s` → `end`，`text` 原样复制；
- `caption_segments[]` → `VIDEO.captionSegments[]`：整项原样复制，保留 `begin_s` / `end_s`、`caption_rect`、`caption_bar_rect` 和 `caption`；
- scene-config 的 `scenes[]` → `VIDEO.presenter.placements[]`：`begin_s` / `end_s` 原样复制，仅 regions 有人物区（`component` 为 `presenter` 的 reserved 区）的 scene 为 `visible: true`，其余为 `visible: false`。可见项的位置取该 scene 人物区 rect：`x = rect.x`、`y = rect.y`、`size = rect.width`。

完整字段、缺省行为和动画边界见 [caption-bar 组件文档](../components/caption-bar/caption-bar.md) 与 [presenter 组件文档](../components/presenter/presenter.md)。
