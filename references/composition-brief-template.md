# Composition Brief — <TOPIC>

## Project
- Topic：<Phase 1 中给出的一句话描述>
- Target duration：<N> 秒
- Orientation：<1920x1080 | 1080x1920 | 1080x1440>
- Output：./composition/renders/final.mp4

## Inputs
路径相对于本 brief，本 brief 位于工作区根目录。

- 最终解说音频：voice_clone/narration.mp3
- 解说脚本：narration.txt
- 带词级时间戳的 ASR transcript：transcribe/transcript.json
- 素材 catalog：material-catalog.json
- 场景-素材匹配建议：scene-material-suggestions.json（如存在；优先参考，可有充分理由偏离）
- 已预置字体：fonts/

## Style Hint
<来自 Phase 1 的自由格式 mood、受众、配色与节奏提示。示例：
"中文解说讲解视频，温暖的手绘笔记本氛围，节奏舒缓。"
"中文 AI/SaaS 技术编辑风，深色严肃语调，信息密集但易读，多 data callout。">

可选的风格路由参考：
- references/design-dawn.md —— 温暖手绘氛围参考
- references/design-moon.md —— 深色技术 / 编辑氛围参考
- references/palettes.md —— 备选的 mood / palette 路由

这些参考是 style hint，不是实现规范。所有实际的 composition、排版、布局、动画与渲染决策，请走 `hyperframes` skill 和项目自己的 `DESIGN.md` 流程。

## Upstream Contracts
1. 音频已是终稿。不要重新生成 TTS，也不要调用 HyperFrames 的 TTS。
2. 词级时间用 `transcribe/transcript.json`。如果需要一份确定性的 scene 时间轴文件，可以在 `transcribe/` 下生成，但 scene 切分和视觉提示时间归 HyperFrames sub-agent。
3. 所有以素材为底的视觉都必须通过 `material-catalog.json` 解析。需要 catalog 素材的地方，不要凭空造一个 stock 视觉。
4. 如果从 catalog 中切出一段源视频片段，要用 `-an` 剥掉它的原始音频；`narration.mp3` 是最终视频里唯一的解说人声。
5. 字体加载用 `fonts/` 下的本地资源，确保确定性。不要依赖系统的 `fc-match` 字体。
6. 所有 composition、动画、校验与渲染工作都用 `hyperframes` 和 `hyperframes-cli` skills。父 skill `topic-to-video` 只负责上面列出的上游资源。
7. 渲染时必须传 `--workers 1`。多 worker 在本机环境会产生奇数高度帧，导致编码异常。

## Deliverables
- composition/index.html
- composition/DESIGN.md
- composition/renders/final.mp4
- 一段简短的完成总结，包含输出路径、ffprobe 时长和文件大小。
