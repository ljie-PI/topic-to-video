# 动效参考

这是一份**按需参考库**，提供动画能力查询入口、构思维度、runtime 候选与编排建议，不是每个 scene 的动效设计流程。查阅条件与借用记录见 [composition 基础指令第四部分](../references/delegation/composition/base-instructions.md#四内容演绎与模板选择)；每个 scene 最终以旁白语义和素材实际情况为准。

转场（scene 之间的交接）不在这份指南里，见组件文档 `components/transitions/tile-wipe/tile-wipe.md`（目前唯一的转场组件）。

## 需要核对实现能力时

本项目只依赖 `hyperframes` 与 `hyperframes-cli` 两个外部 skill；不允许加载其他 HyperFrames 扩展。实现已构思的动效、需要核对能力或 API 时，从这两个 skill 的文档按问题读取：工程结构、渲染与检查命令看 `hyperframes-cli`；核心协议与场景组装约定看 `hyperframes`。确定方案后只读与本次实现直接相关的部分；不要预读全部实现文件，也不要把任何索引当作能力全集。具体的组件级写法（组件、模板）见 `components/components.md` 和各模板文档。

## 动效构思的参考维度

需要梳理动效构想时，可参考以下维度；它们不是逐项必做的清单，也没有固定顺序：

- 旁白要表达的关系、状态变化，以及观众需要看清的重点；
- 素材实际内容、比例和可读尺寸，layout 区域给运动划出的边界；
- 输出朝向、信息密度、可读时间和与前后 scene 的连续性；
- 动效是否推进理解：静态、局部强调、视觉隐喻或多阶段编排都可成立；
- 已确定的画面与运动需要什么实现能力，再选合适的 runtime。

构思从表达目标与素材出发；借用的候选机制可以组合、替换或不用，自主方案不需要为了符合本指南而改写。

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

## 全片编排建议

以下是可选的编排建议，不要求每个 scene 有招牌机制或持续运动：

- **运动词汇与变化**：可以用相近的节奏保持全片连贯，再按内容关系调整具体机制。
- **转场分级**：接缝可以稳定，话题切换或高潮可以强调；采用转场组件时，其参数见 `components/transitions/tile-wipe/tile-wipe.md`。
- **焦点与编排**：需要视觉焦点时，可围绕一个主要变化组织动效；极简静态或多阶段演绎也同样成立。
- **素材与理解**：持续运动适合遍历重点、逐步揭示或解释变化；素材已经清楚时，可以保持静止。

主题节奏、语音同步与渲染确定性仍按输入和 runtime 契约执行：默认时长、缓动与列表间隔取所选 design 的 motion token；信息呈现对齐真实旁白时间；动画只由时间决定，不用无限循环或定时器，需要随机时用固定种子。具体机制不限于 opacity / transform。

## 朝向对运动的影响

- 横屏可以使用横向 flow、左右 shared-axis、宽 chart scrub 和横向 camera travel，同时顾及素材比例和字幕区。
- 竖屏的流程、时间线、状态机优先纵向推进；榜单、表格、图表优先分页 / 分时 / 主项高亮；架构和网络图优先 focus window / primary path。
- 朝向只改变运动几何和信息密度，不改变 scene 的语义意图；不建议靠缩字号或缩素材把横屏的 choreography 搬进竖屏。
