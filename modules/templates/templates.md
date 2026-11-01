# 模板

模板是**某一类视频专用**的东西。它在通用模块之上，加入这类视频自己的内容和风格：

- 选一个**布局**（`layouts/`），规定每个区域放什么；
- 组合**组件**（`components/`），并给它们定好这类视频的参数，例如导航栏的标志和路径、转场卡片的写法；
- 加入这类视频**专属的配色和元素**，例如 GitHub 的标志、语言色点、仓库卡片、Star 按钮；方格转场在这里换成贡献图的绿色；
- 提供这类视频的**场景**（HTML），只要往里填内容就能用。

设计主题、布局、组件对所有类型的视频都通用；模板只服务于它那一类视频。

## 现有模板

| 模板 | 视频类型 | 支持的 layout | 场景 |
|---|---|---|---|
| `github` | GitHub 热榜 / 开源项目盘点（讲解模式，人物主持） | `presenter` | `trending-overview`（榜单总览）、`project-cover`（项目封面） |

每个模板一个目录，文档和代码放在一起：

```
templates/<类型>/
  <类型>.md          这类视频怎么组装：布局、组件及其参数、专属配色和元素、数据怎么填、人物怎么演
  <类型>.json        机器声明：supported_layouts、场景名与每个场景需要的锚点字段
  <场景>.md          每个场景的说明：参数、数据、时间、限制
  <场景>.html        场景本体，复制到视频工程的 compositions/
  brand/ …           这类视频专属的资源（如品牌标志）
```

`<类型>.json` 是模板与 layout 是否兼容的唯一依据：`supported_layouts` 列出它能配的 layout，`prepare-handoff.py` 与状态检查都读它。

**模板由 composition 阶段选。** Phase 6 / 7 不为旁白或场景规划选模板；Phase 8 委派的 composition agent 读本目录，按内容、当前 layout 与用户要求决定用哪个模板或不用（只读上面的 `supported_layouts`，不从模板文档猜），再把结果写进 `inputs.json` 的 `template`（模板名或 `null`）并写进 storyboard。模板与 layout 冲突时（例如用户拒绝人物、或项目是竖屏而模板只支持 `presenter`），选兼容的 layout 或写 `template: null`，不要为了套模板改朝向或 design。
