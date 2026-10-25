# 运动指南

这份指南回答 composition 时的运动问题：HyperFrames 有哪些动画能力、一个 scene 的动画按什么顺序选、runtime 怎么挑、全片保持什么节奏。它只提供建议和候选，不是规则；每个 scene 最终以旁白语义和素材实际情况为准。

转场（scene 之间的交接）不在这份指南里，见组件文档 `components/transitions/tile-wipe/tile-wipe.md`（目前唯一的转场组件）。

## 能力发现流程

HyperFrames 当前安装版本的动画能力以外部 skill 为准。写动画之前先加载 `/hyperframes-animation`，按需读取：

- `rules-index.md`：原子 motion recipes；
- `blueprints-index.md`：多阶段 scene choreography；
- `transitions/overview.md` 与 `transitions/catalog.md`：scene handoff；
- `techniques.md`：SVG、Canvas、CSS 3D、Lottie、MotionPath、shader 等技术菜单。

需要 shared element / FLIP、path、mask、SVG morph / draw、DOM 3D、Three.js / WebGL keyframes 时，再加载 `/hyperframes-keyframes`。确定 effect / blueprint 后只读对应的 recipe 和实际 runtime adapter；不要预读全部实现文件，也不要把任何索引当作能力全集。具体的组件级写法（组件、模板、示例工程）见 `components/components.md` 和各模板文档。

## 动画选择顺序

每个 scene 建议按以下顺序确定动画：

1. 完整旁白句子和这个 scene 的语义意图；
2. 主语（`primary_subject`）以及需要证明的状态变化；
3. 信息形态给的动画候选（`patterns/` 里对应 pattern 的「动效候选与应避免」小节）；
4. 布局角色、素材比例、重点区域、continuation 状态给运动划出的边界；
5. 输出朝向、信息密度、可读时间和与前后 scene 的连续性；
6. 选定一个主打机制（signature mechanism），按需加少量辅助机制；
7. 最后选最小合适的 runtime。

候选机制可以组合、替换或干脆不用。没用表里的候选时，只要替代方案更能表达 scene 语义，就是合理选择。

## Runtime 选择

Runtime 是实现手段，不是视觉丰富度指标。不建议为了「充分利用能力」在同一支视频里铺满所有 runtime。

| Runtime | 什么时候选 | 不建议只因 |
| --- | --- | --- |
| GSAP | 默认 timeline、stagger、transform、SVG、camera choreography、语义 label | 想给所有 scene 统一 fade / slide |
| CSS animations / WAAPI | 单元素、少量 keyframes、简单装饰或生成式 DOM keyframes | 复杂 scene sequencing 勉强拆成 delays |
| Anime.js | 用户明确要求、已有 Anime.js recipe，或其 API 明显更小更清楚 | 只是想和 GSAP 不同 |
| Lottie / dotLottie | 已有本地 `.json` / `.lottie` 资产或明确的 AE export | 没有资产却想让普通 DOM 动画显得高级 |
| Three.js / WebGL | 真实 depth、camera / object motion、GLTF、shader、canvas 内部运动 | 普通卡片 tilt / scale 已能说明语义 |
| TypeGPU / WebGPU | 明确需要 WGSL、compute、GPU particles、liquid / glass，且环境支持 | 只需要普通背景或简单粒子 |

HTML-as-texture、shader、Three.js、TypeGPU 这类 hero treatment 通常只值得用在少量关键节拍上；其余 scene 用清晰、可读、好维护的 DOM / SVG choreography，让关键节拍的差异真正成立。

## 全局运动原则

- **建立可复用的运动词汇**：全片用同一套 motion family，而不是每个 scene 换新效果。
- **转场分级**：普通的 scene 接缝用稳定的主转场；话题切换、高潮、结尾才用强调转场。转场的选择和参数见 `components/transitions/tile-wipe/tile-wipe.md`。
- **连续 scene 不重复同一套组合**：相邻 scene 可以同属一个 motion family，但建议错开 `入场 + 信息揭示 + 转场` 的组合，避免观感雷同。
- **一个 scene 一个主打机制**：effect 数量不是质量指标；一个 signature mechanism 加少量 supporting mechanisms 通常足够。
- **静态素材的持续运动要推进理解**：focal traversal、分步标注、camera intent、细节揭示都可以；idle drift、breathing、glow pulse 这类纯装饰运动不适合单独承担一个 scene 的运动。
- **入场节奏跟主题走**：时长、缓动、列表行间隔用所选主题的 motion token（`--motion-enter-duration` / `--motion-easing` / `--motion-list-interval`，见 `designs/designs.md`）。
- **只 animate opacity / transform**，动画只由时间决定：不用 `repeat: -1`，不用随机数（需要随机时用固定种子），不用定时器。
- **信息元素按旁白出现**：文本、条目、节点随对应的句子逐个出现；避免 scene 开头用统一 stagger 把所有叙事文本一次性铺开。

## 朝向对运动的影响

- 横屏可以使用横向 flow、左右 shared-axis、宽 chart scrub 和横向 camera travel，同时顾及素材比例和字幕区。
- 竖屏的流程、时间线、状态机优先纵向推进；榜单、表格、图表优先分页 / 分时 / 主项高亮；架构和网络图优先 focus window / primary path。
- 朝向只改变运动几何和信息密度，不改变 scene 的语义意图；不建议靠缩字号或缩素材把横屏的 choreography 搬进竖屏。
