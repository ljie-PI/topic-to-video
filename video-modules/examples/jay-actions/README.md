# 示例：Jay 动作演示（59.9 秒）

把 Jay 组件的动作逐个演一遍，用来挑动作、检查效果，也可以当作动作目录看。路径相对 skill 根目录。

- Jay 放大到 840px，放在画面中间（`x 540, y 260, size 840`）。
- 字幕条挪到画面顶部当标签条（`y 0`，`fontSize 40`），显示“动作名 · 中文名 — 用途”。
- 每个动作之间停 0.9 秒。这里没有配音，所以嘴只在动作本身需要张嘴时才动。

演示顺序：
1. 挥手、点头、小点头；
2. 摇头、歪头、疑问；
3. 惊讶后仰、惊喜、灵感；
4. 微笑、大笑（都是嘴角上扬）；
5. 思考（气泡里是“这是什么？”）、叹气；
6. 凑近看（同时看向左边）、回头再看；
7. 打字，最后是四个方向的瞥视 L、U、R、D，每个 1.5 秒。

## 文件

- `index.html`：主题变量（纸本）、背景，以及两个挂载点：`caption-bar` 当标签条，`jay`。
- `tools/build-data.mjs`：动作清单。改顺序、改时长或加动作都在这里改，然后重新生成 `data/video-data.js`；它会打印总时长，把总时长填进 `index.html` 的 `data-duration`。
- `compositions/`：从 skill 的 `assets/components/` 原样复制。

## 运行

```
node tools/build-data.mjs
npx hyperframes check
npx hyperframes preview
```
