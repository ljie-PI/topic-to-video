# composition scene-config 数据契约

`composition/scene-config.json` 是 Phase 8 视觉场景的**唯一机器配置来源**，由
composition agent 产出：它存脚本需要的数据（`scripts/scene_config.py` 读取），
`storyboard.md` 存设计说明与理由（人读）。状态验收（`pipeline-status.py`）、
字幕（`align-narration.py --mode subtitles --scene-config`）和渲染前检查
（`check-composition.py --scene-config`）都经同一个公共入口
`scene_config.load_scene_config(path, *, expected_canvas=None, known_scene_ids=None, modules_root=None)`
校验后消费，错误会定位到 `scene_id` 和字段。

每个视觉场景**独立**按「用户要求 → 特别匹配模块 → 即时生成」的统一顺序（完整规则见 `base-instructions.md` 第四部分）决定自己的方案，写进本文件：

1. 先应用该场景的明确用户要求（`inputs.json` 的 `composition_requests`；
   整片要求只在其作用范围内应用）；
2. 用户指定 template / layout 时先处理它；未指定时，只有非常匹配（特别匹配）的预定义 template 或 layout preset 才采用；
3. 采用模板后，根据它的 `preferred_layouts`（建议而非门槛）及用户要求确定本 scene 的布局；
   没有模板时，只在现有 layout preset 与该 scene 特别匹配时才借用；
4. 没有指定或非常匹配的预定义模块时，即时生成自主构图——`template: null`、`preset: null` 加自由布局是
   正常完成路径，不是失败。

## 根对象

| 字段 | 规则 |
|---|---|
| `version` | 整数，当前必须为 `1`。 |
| `canvas` | `{width, height}`，与已定 orientation 对应的尺寸完全一致（1920×1080 / 1080×1920 / 1080×1440）。 |
| `total_s` | 正的有限秒数，以交付视频的配音时长为边界，包含语音前后的静音画面；不靠改 Phase 7 时间轴凑时长。 |
| `scenes` | 非空列表，见下。 |

## scene

| 字段 | 规则 |
|---|---|
| `scene_id` | 非空字符串，全文件唯一。 |
| `source_scene_ids` | 非空字符串列表，指向 Phase 6 `scene-plan.json` 的叙事 scene；合并 / 拆分的映射及理由写在 storyboard。 |
| `begin_s` / `end_s` | 有限秒数，`0 <= begin_s < end_s`；主区间按 `[begin_s, end_s)` 归属并覆盖 `[0, total_s]`，有序、不重叠。视觉转场重叠由画面实现处理，不写进主区间。 |
| `template` | `null`（本 scene 不用模板）或 `{"name": ..., "scene": ...}`：`name` 是模块库注册的模板名，`scene` 是该模板声明的场景部分（如 `github-trending` 的 `project-cover` / `trending-overview`）。两者都必须真实存在。 |
| `layout` | 见下。**实际的 regions / caption 必须完整落盘**：检查不从 `preset` 名猜坐标。 |

## layout

| 字段 | 规则 |
|---|---|
| `preset` | `null`（自由布局，无需注册）或借用的注册 layout 名（记录出处，便于复用与排查）。 |
| `regions` | 非空列表，见下。自由布局不需要注册到 `modules/layouts/`，也不默认加人物、导航或固定分区。 |
| `caption` | `{width_px, font_size_px, max_lines}`，三者都是正整数（`max_lines >= 1`）。 |

## region

| 字段 | 规则 |
|---|---|
| `id` | 非空字符串，同一 layout 内唯一。 |
| `kind` | `content`（可自由放内容）或 `reserved`（只放指定组件）。 |
| `rect` | `{x, y, width, height}`，全部为有限数值；`width` / `height` 为正，`x` / `y` 非负，且整个 rect 不超出 canvas。 |
| `component` | `reserved` 区必填：明确该区域归属的组件（如 `caption-bar`、`presenter`、`nav-bar`）。 |

## 明确不要的东西

不加入哈希、源文件修改时间、构建版本号或“是否最新”的追踪字段；读取接口对
未知字段报错，而不是静默忽略。

## 字幕产物（composition/assets/subtitle-units.json）

`align-narration.py --mode subtitles --scene-config` 一次对齐显示稿 / 朗读稿 /
transcript（不重复 ASR），把每个对齐 atom 按真实时间完整归属到一个视觉
scene（重叠最多者，平手归较早 scene；atom 的真实时间不改），再按各 scene
自己的 `caption` 预算（`width_px / font_size_px` 取整 × `max_lines`）切字幕
单元。不用全片最小预算冒充逐场景规格。

每个单元保留既有字段 `index` / `text` / `begin_ms` / `end_ms` / `begin_s` /
`end_s` / `fallback` / `paragraph`，并增加 `scene_id`（该单元归属的视觉
scene）。产物还带 `caption_segments`（各 scene 的显示区间与 caption 规格），
组件与 QA 消费同一组派生边界。

切点规则：

- 短字幕自动合并不跨「不同版面」的切点（相邻 scene 的 caption 规格完全一
  致才算同一版面）；合并超预算会被拒绝并给出诊断。
- 英文 / 数字 token 的 atoms 分属不同 scene（切点落在 token 时间内部）时，
  工具报出涉及的 `scene_id` 与两侧真实可用的时间边界（ms）后失败，由
  composition agent 调整视觉切点或编辑字幕；不静默截断、重复或丢弃文字。

编辑规则：初稿默认由脚本生成；实际制作中可以编辑字幕文本与边界，已有用户
编辑是有效输入。显示（composition 组件）与检查（check-composition）都以当
前文件为准，仅改画面 / 重渲染不会覆盖已有字幕；没有锁文件、指纹或编辑审批。

## 可验证示例

下面两个示例覆盖了“采用模板的场景 + 预设布局”与“无模板 + 自由布局”两种正常
路径，都经 `scripts/scene_config.py` 的公共读取接口测试（见
`tests/test_scene_config.py`）：示例不是只给人看的，格式以读取接口的校验为准。

采用模板（github-trending 的 project-cover）并借用 presenter 预设的 scene，与无模板、
自由布局的 scene 同片共存：

```json
{
  "version": 1,
  "canvas": {"width": 1920, "height": 1080},
  "total_s": 12.0,
  "scenes": [
    {
      "scene_id": "visual_001",
      "source_scene_ids": ["scene_1"],
      "begin_s": 0.0,
      "end_s": 6.0,
      "template": {"name": "github-trending", "scene": "project-cover"},
      "layout": {
        "preset": "presenter",
        "regions": [
          {"id": "main", "kind": "content", "rect": {"x": 96, "y": 196, "width": 1048, "height": 788}},
          {"id": "person", "kind": "reserved", "component": "presenter", "rect": {"x": 1294, "y": 642, "width": 420, "height": 420}},
          {"id": "caption-text", "kind": "reserved", "component": "caption-bar", "rect": {"x": 96, "y": 1008, "width": 1166, "height": 72}}
        ],
        "caption": {"width_px": 1166, "font_size_px": 36, "max_lines": 1}
      }
    },
    {
      "scene_id": "visual_002",
      "source_scene_ids": ["scene_2"],
      "begin_s": 6.0,
      "end_s": 12.0,
      "template": null,
      "layout": {
        "preset": null,
        "regions": [
          {"id": "main", "kind": "content", "rect": {"x": 96, "y": 80, "width": 1728, "height": 820}},
          {"id": "caption", "kind": "reserved", "component": "caption-bar", "rect": {"x": 96, "y": 930, "width": 1728, "height": 120}}
        ],
        "caption": {"width_px": 1728, "font_size_px": 36, "max_lines": 2}
      }
    }
  ]
}
```

单个完整自由布局场景的最小形态（与计划文档 4.1 的结构示例一致）：

```json
{
  "version": 1,
  "canvas": {"width": 1920, "height": 1080},
  "total_s": 8.0,
  "scenes": [
    {
      "scene_id": "visual_001",
      "source_scene_ids": ["scene_1"],
      "begin_s": 0.0,
      "end_s": 8.0,
      "template": null,
      "layout": {
        "preset": null,
        "regions": [
          {"id": "main", "kind": "content", "rect": {"x": 96, "y": 80, "width": 1728, "height": 820}},
          {"id": "caption", "kind": "reserved", "component": "caption-bar", "rect": {"x": 96, "y": 930, "width": 1728, "height": 120}}
        ],
        "caption": {"width_px": 1728, "font_size_px": 36, "max_lines": 2}
      }
    }
  ]
}
```
