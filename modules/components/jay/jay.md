# 组件：jay（人物动作）

一个坐在笔记本前的卡通主持人 Jay。他会呼吸、眨眼，跟着配音动嘴，看向讲到的区域，按剧本做 15 个动作（挥手、点头、摇头、歪头、惊讶、惊喜、灵感、微笑、大笑、思考、叹气……）和打字。表情走写实一些的路线：笑靠嘴角上扬，不用眯眼和脸红。

画面全部由两张图片切块、变形而来，用 WebGL 绘制。每一帧的姿态只由时间决定，同样的输入每次渲染结果完全一样。

## 文件

| 文件 | 说明 |
|---|---|
| `components/jay/jay.html` | 组件本体：静态标记和样式（`<template>`），由工程的 adapter 克隆挂载 |
| `components/jay/jay.mjs` | 初始化脚本：导出 `init(root, { params, data, duration, gsap })`，接口见 [modules.md](../../modules.md) 的「模块初始化接口」 |
| `components/jay/images/jay-base.png` | 基础图层：身体、头、五官、键盘上的左手、笔记本和杯子，以及所有动作的来源。2048×2048，透明背景 |
| `components/jay/images/jay-wave.png` | 挥手部件：只取抬起的右手。和 `jay-base.png` 同一构图、同一尺寸，像素对齐 |
| `components/jay/make-envelope.mjs` | 从配音生成嘴型数据（见下文） |

两张图的切割坐标都写死在 `jay.html` 里。**不能换成别的图**，也不能重新裁切或缩放这两张图；调色可以，只要尺寸和位置不变。

## 依赖（来自设计主题，视频的 `index.html` 必须提供）

| 变量 | 用在哪里 |
|---|---|
| `--c-ink` | 思考气泡的描边和文字、“!”的描边、挥动线、脚下的阴影 |
| `--c-card` | 思考气泡的底、“!”的白色笔画 |
| `--c-focus` | “!”的圆底 |
| `--c-border` | 咖啡杯的热气 |
| `--c-highlight` | 灯泡 |
| `--font-sans` | 思考气泡里的文字、问号 |

人物本身的颜色（皮肤、衣服、嘴巴内部）是美术的一部分，不跟随主题变化。

## 最小用法

Jay 由视频工程的 adapter 接线（普通浏览器和 HyperFrames 工程都用同一个 `init` 入口，不需要任何厂商全局变量）：

```html
<!-- index.html 根节点里：从 0 秒挂到片尾，最上层 -->
<div id="jay" data-composition-id="jay" data-composition-src="compositions/jay.html"
     data-start="0" data-duration="27.2" data-width="1920" data-height="1080"
     data-variable-values='{"x":1294,"y":642,"size":420}' style="z-index: 20"></div>
```

```js
// 工程 adapter：克隆模板、取参数和剧本、调 init、驱动 seek。
// 选用 HyperFrames 时，把返回的 timeline 按核心协议注册进 scene host、
// 在 hf-seek 里 seek(timeline) 后 await ready 再调 seek(t)——这段桥接住在工程里。
import { init } from './compositions/jay.mjs';
const host = document.querySelector('[data-composition-id="jay"]');
// 从 compositions/jay.html 取出 <template> 克隆进 host，root 是里面的 #root 节点
const root = host.querySelector('#root');
const params = JSON.parse(host.dataset.variableValues || '{}');
const instance = init(root, {
  params,
  data: window.VIDEO[params.data || 'jay'],   // 动作剧本，adapter 负责选键
  duration: Number(host.dataset.duration) || 0,
  gsap,
});
await instance.ready;              // 图层/WebGL 构建完成；失败会 reject
instance.seek(12.5);               // 局部秒：data-start="0" 时就是视频秒
// instance.timeline 暂停的 GSAP timeline，只声明时长；instance.destroy() 拆除驱动
```

```js
// data/video-data.js（在 index.html 的 <head> 里引入），时间都是视频秒
// （Jay 从 0 秒挂到片尾时，视频秒 = init/seek 的局部秒）
window.VIDEO = { jay: {
  acts:     [[0.45, "wave", 3000], [25.0, "eureka", 2700]],
  typing:   [[19.85, 20.75]],
  glances:  [[1.467, 1.0, "U"], [3.167, 1.0, "L"]],
  envelopeFps: 30,
  envelope: [ /* node components/jay/make-envelope.mjs 配音.wav */ ],
  // 可选：视觉 scene 的显示与位置；映射规则见下文
  placements: [{ begin_s: 0, end_s: 27.2, visible: true, x: 1294, y: 642, size: 420 }],
} };
```

数据（`acts` 动作脚本、`placements` 显示区间等）建议用脚本从字幕和配音时间生成，别手写秒数。

## 安装

1. 把 `components/jay/jay.html` 和 `components/jay/jay.mjs` 一起复制到视频工程的 `compositions/`（文件名不变）。
2. 把 `components/jay/images/` 下的两张图复制到视频工程的 `assets/jay/`（组件按这个路径加载）。
3. 在 `index.html` 根节点里加一个挂载点：
   - `id="jay"`，`data-composition-id="jay"`，`data-composition-src="compositions/jay.html"`；
   - `data-start="0"`，`data-duration` 等于整支视频时长；
   - `style="z-index: 20"`（最上层）；
   - `data-variable-values` 写位置参数（见下表）。
4. 在视频的 `data/video-data.js` 里写 `window.VIDEO.jay` 动作剧本（见下文），并在 `index.html` 的 `<head>` 里用 `<script src="data/video-data.js">` 引入。
5. 按上面的最小用法接线：调 `init`、等待 `ready`、用 `seek(t)` 驱动每一帧；选用 HyperFrames 时由工程 adapter 接其核心协议（hf-seek 桥接等）。

一支视频只挂一个 Jay（组件用固定的元素 id）。组件不读 `window.__hyperframes`、host 的 data 属性或全局 `VIDEO`/`JAY_SCRIPT`，也不向 `window.__timelines` 注册；这些读取和桥接都属于工程 adapter。

## 挂载参数（`init` 的 `params`；HyperFrames 工程写在 `data-variable-values` 上，由 adapter 读出传入）

| 参数 | 默认 | 说明 |
|---|---|---|
| `x`, `y` | 1294, 642 | 人物舞台左上角，单位 px。默认就是讲解模式布局的人物区 |
| `size` | 420 | 舞台边长，单位 px（原图 2048 等比缩放）。600 是 100%，420 是 70% |
| `fxScale` | 1 | 思考气泡和“!”的额外放大倍数。人物缩小后可以设 1.2–1.4 |

## 视觉 scene 放置（剧本里的 `placements`）

`placements` 是可选数组，时间在**局部秒**（挂载从 0 秒开始时就是视频秒）。提供非空数组后，Jay 仍然是**从 0 秒挂到整片结束的唯一一个挂载点**，只在一个组件实例里按局部秒切换显示与位置；不要按 scene 重复挂载 Jay。自由布局的几何与显示全部来自这些显式数据——组件不知道也不关心某个 layout 叫什么。

每一项形状为：

```js
{ begin_s, end_s, visible, x?, y?, size? }
```

- 命中规则是 `begin_s <= t < end_s`；数组按 `begin_s` 排序，重叠时最后开始的一项生效。
- `visible: false` 将 `#jay-stage` 设为 `display: none`，用于 `stage` / `portrait` 等非主持人场景；`visible: true` 恢复显示。
- 可见项可用 `x` / `y` / `size` 覆盖舞台左边、上边和边长（px）。省略的字段不修改当前值；通常每个可见项都写明完整位置，避免依赖前一项留下的值。
- 只要 `placements` 非空，没有命中任何一项时就隐藏 Jay；这也包括 `t` 恰好等于最后一项 `end_s` 的片尾时刻。完全不提供 `placements`（或提供空数组）时保留旧行为：Jay 全片显示。

从 `composition/scene-config.json` 到 `placements` 的映射是确定的：每个视觉 scene 产生一项，`begin_s` / `end_s` 原样复制，只有 regions 有人物区（`component` 为 `jay` 的 reserved 区）时可见。可见项的几何值取该 scene 人物区的 rect，而不是另估坐标：

```js
// scene-config 的 scene.layout.regions 中 component === "jay" 的 reserved 区即人物区
window.VIDEO.jay.placements = sceneConfig.scenes.map((scene) => {
  const personRegion = scene.layout.regions.find(
    (region) => region.kind === "reserved" && region.component === "jay",
  );
  const placement = {
    begin_s: scene.begin_s,
    end_s: scene.end_s,
    visible: personRegion !== undefined,
  };
  if (placement.visible) {
    placement.x = personRegion.rect.x;
    placement.y = personRegion.rect.y;
    placement.size = personRegion.rect.width; // 人物区是正方形，width === height
  }
  return placement;
});
```

因此，没有人物区的 scene 的 Jay 必须在同一常驻实例中隐藏；进入下一个人物区 scene 时再显示。

## 动作剧本（`init` 的 `data`；adapter 从 `window.VIDEO` 选键传入）

所有时间都是**挂载的局部时间（秒）**：挂载点从 0 秒开始时就是视频时间。嘴型 `envelope` 按 `envelopeFps` 对局部秒采样（`envelope[Math.floor(t * envelopeFps)]`），和动作、placements 用同一个时间基准；scene 在非零时刻开始或只覆盖一部分配音时，由 adapter 把剧本时间换算成局部秒，组件不会自行偏移。

```js
jay: {
  acts:     [[0.45, "wave", 3000], [25.0, "eureka", 2700]],   // [开始秒, 动作, 时长毫秒]
  thoughts: [[64.4, "授权？"]],                                // [开始秒, 气泡文字]，配合 think 动作
  typing:   [[19.85, 20.75]],                                  // [开始秒, 结束秒]，低头打字
  glances:  [[1.467, 1.0, "U"], [3.167, 1.0, "L"]],            // [开始秒, 时长秒, 方向]
  envelopeFps: 30,
  envelope: [11, 100, 100, 2, 0, …],                          // 嘴型：配音响度 0–100，每秒 30 个
  seed: 20261018,                                              // 可选：眨眼、视线小跳动的随机种子
}
```

### 通用演法

时间都是视频秒（Jay 从 0 秒挂载时即组件的局部秒）。以下演法适用于所有带 Jay 的视频；有模板时，再叠加模板专属的动作。

| 时刻 | 动作 |
|---|---|
| 开场后 0.45 秒 | `["wave", 3000]` |
| 每次转场前约 0.85 秒 | `typing [切点 - 0.85, 切点 + 0.05]` |
| 主展示区换内容时 | 瞥视 `[该时刻, 1.0, "L"]` |
| 副展示区换内容时 | 瞥视 `[该时刻, 1.0, "U"]` |
| 旁白讲到提问、结论、关键数字、反例或转场 | 从下面的动作库挑一个合适的动作；需要卡准秒数时用该句在 `timeline.json` 的段落 / cue |
| 结尾 | `["laugh", 2200]`，再 `["wave", 3200]` 告别 |

### 动作库（`acts`）

每个动作的表现见下表（推荐时长、头部与手势细节）。

**挥手和头部动作**

| 动作 | 推荐时长 | 表现 | 适合的时刻 |
|---|---|---|---|
| `wave` | 3000–3200 | 右手从笔记本后抬起，以手肘为轴左右挥，手掌比小臂慢半拍，旁边有挥动线；然后放回去。眉毛微抬，嘴角上扬 | 开场欢迎、结尾告别 |
| `eureka` | 2700 | 睁大眼、挑眉、张嘴，头往上一跳；头的右上方冒出“!”（主题焦点色 `--c-focus`，离头约一个圆的距离）；眼镜闪光 | 亮出关键数字（如 star 数） |
| `nod` | 1400–1500 | 点头两下 | 确认、讲完一个要点 |
| `think` | 1950–2900 | 看向右上方，歪头，单边挑眉，轻轻晃动；头顶出现思考气泡（文字取自 `thoughts` 里同一时间点的那条） | 讲注意事项、提问 |
| `laugh` | 2200 | 嘴角上扬，嘴快速开合，身体跟着抖 | 轻松的点评、结尾 |
| `nod-small` | 1000 | 一下轻点头 | 边讲边认同，比 `nod` 轻 |
| `shake` | 1600 | 头左右摇三下，眉毛压低 | 否定、不推荐、“别这样做” |
| `tilt` | 2000 | 头歪向一侧，单边挑眉，眼睛稍睁大 | 提出问题、好奇 |
| `startle` | 1800 | 头往后一缩，眼睛睁大，眉毛高挑，嘴张开；不出“!” | 意外的信息，比 `eureka` 轻 |
| `smile` | 2200 | 嘴角上扬，头微微歪，眉毛轻抬，不出声 | 讲到好东西、温和的认可 |
| `sigh` | 2600 | 先吸气抬头，再把头沉下去，眼皮半闭，嘴微张 | 遗憾、限制条件 |
| `lean` | 2400 | 头往前凑近（画面上略微放大），眼睛微眯、专注；方向由同时间的瞥视决定 | “仔细看这里”，配合 `L` 或 `U` 瞥视 |
| `doubletake` | 2400 | 看向左边、回到镜头、再猛地看回左边并睁大眼 | 反转、意外的细节 |

**带头顶提示的动作**（提示出现在头的右上方，和“!”同一个位置）

| 动作 | 推荐时长 | 表现 | 适合的时刻 |
|---|---|---|---|
| `question` | 2400 | 歪头好奇，同时冒出一个白底蓝字的“?”，轻轻摇摆 | 抛出问题 |
| `idea` | 2400 | 眼睛一亮、挑眉、头往上一跳，冒出一个黄色灯泡，光线闪烁；眼镜闪光 | 想到办法、关键思路 |

同一时间只做一个动作。前一个动作没结束时，后一个动作要等它结束才开始，所以排时间时不要让它们重叠。

### 常驻动作（不用写，自动发生）

- 呼吸：4.2 秒一个周期。
- 头部慢速轻晃，头发随之摆动。
- 每隔 2.2–5.2 秒眨一次眼，偶尔连眨两下。
- 视线看镜头，并有小幅随机跳动。
- 咖啡杯冒热气。
- 跟着 `envelope` 动嘴：声音越大，嘴张得越开，眉毛和头也微微上抬。
- 打字时低头看笔记本，眼皮自然下垂。

### 打字（`typing`）

在这段时间里，Jay 低头看笔记本敲键盘。适合放在换章节之前 0.8 秒左右，正好在转场盖住画面之前。

### 瞥视（`glances`）

| 方向 | 看哪里 |
|---|---|
| `L` | 左边：讲解模式的主展示区。眼珠移到左侧，脸转向左，头稍往左偏 |
| `U` | 上方：副展示区（他头顶上方的榜单或步骤）。眼珠往上，头抬起，眉毛上扬 |
| `R` | 右边。和 `L` 对称 |
| `D` | 低头看笔记本。眼珠往左下，头低下，眼皮下垂 |

一次 1–1.5 秒，讲到哪个区域就看哪个区域，看完自动回到镜头。

### 嘴型数据（`envelope`）

用配音生成，需要 ffmpeg：

```
node components/jay/make-envelope.mjs 配音.wav > envelope.json
```

在仓库根目录（仓库本身就是工作区，或者已物化 `modules/` 的工作区根目录）为 composition 生成时，可运行：

```bash
node modules/components/jay/make-envelope.mjs voice_clone/narration.mp3 > composition/assets/jay-envelope.json
```

- 输出是一个数组，每秒 30 个值，0–100。
- 静音阈值为 -45 dBFS；有声部分的 95 百分位响度记为 100。
- 把生成数组放入 `VIDEO.jay.envelope`，`envelopeFps` 与生成参数保持一致（默认 `30`）；`composition/assets/jay-envelope.json` 只是示例保存路径，不是新增的阶段产物门槛。没有配音时可以留空数组，Jay 就不动嘴。

**换了配音，就要重新生成 envelope，并且按新配音的时间重排剧本。**

## 限制

- 组件只认局部秒：挂载从 0 秒开始时局部秒 = 视频秒；若 Jay 挂进一个从其他时刻开始的 scene，剧本（动作、placements、envelope）里的时间要由 adapter 统一换算成 scene 局部秒，envelope 采样基准跟着局部秒走，不另设偏移。
- 嘴的控制有两个：张合（`open`）和嘴角上扬（`grin`）。嘴角上扬是在嘴角附近把脸部网格往上、往外提，下唇和口腔跟着走，幅度适合微笑，不适合咧嘴大笑。
- 现在的动作都只用到头、脸和右手挥动。需要手部动作的（指向、点赞、托腮、鼓掌等），要先画一张和 `jay-base.png` 对齐的姿势图。要新增姿势（比如指向），需要再画一张和 `jay-base.png` 对齐的姿势图，比如 `jay-point.png`，然后在 `jay.html` 里加一个对应的部件，做法同 `jay-wave.png`。
