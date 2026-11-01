#!/usr/bin/env python3
"""把一条背景音乐混音到成片视频上。

单次 ffmpeg 处理：载入随 skill 分发的 `resources/bgm.mp3`（一段 24 秒可循环的
片段），把它循环铺满视频时长，并混在已有旁白之下。旁白保持满音量；BGM 由
`--bgm-volume`（默认 0.03）衰减。

用法：
  python3 scripts/mix-bgm.py \\
      --video composition/renders/final.mp4 \\
      --output composition/renders/final_with_bgm.mp4

  # 需要时覆盖音乐文件或其音量：
  python3 scripts/mix-bgm.py \\
      --video composition/renders/final.mp4 \\
      --bgm /path/to/other.mp3 \\
      --bgm-volume 0.05 \\
      --output composition/renders/final_with_bgm.mp4

输出约定：
  stdout : JSON {success, output_path, bgm_path, duration_s}
  stderr : 带 `[mix-bgm]` 前缀的人类可读进度
  exit   : 0 成功，1 运行时错误，2 参数非法
"""
import argparse
from pathlib import Path

import cli
import media

TOOL_NAME = 'mix-bgm'

# 随 skill 分发的 BGM 位于 <skill_root>/resources/bgm.mp3。路径由 __file__ 推导，
# 因此在任何当前工作目录下都能工作。
DEFAULT_BGM_PATH = Path(__file__).resolve().parent.parent / 'resources' / 'bgm.mp3'


log = cli.make_logger(TOOL_NAME)


def parse_args() -> argparse.Namespace:
    p = cli.JsonArgumentParser(TOOL_NAME, description='Mix a BGM track onto a video with ffmpeg.')
    p.add_argument('--video', required=True, help='Input video (must already contain narration audio).')
    p.add_argument('--bgm', default=str(DEFAULT_BGM_PATH),
                   help=f'BGM mp3 to loop under the narration. Default: bundled '
                        f'{DEFAULT_BGM_PATH.name} at {DEFAULT_BGM_PATH}.')
    p.add_argument('--bgm-volume', type=float, default=0.03,
                   help='Linear gain for BGM, 0.0-1.0. Default 0.03.')
    p.add_argument('--output', required=True, help='Output video path.')
    p.add_argument('--ffmpeg', default=None, help='ffmpeg binary path. Overrides FFMPEG_BIN.')
    p.add_argument('--ffprobe', default=None, help='ffprobe binary path. Overrides FFPROBE_BIN.')
    args = p.parse_args()
    if not 0.0 <= args.bgm_volume <= 1.0:
        p.error(f'--bgm-volume must be within [0.0, 1.0] (got {args.bgm_volume})')
    return args


def mux_bgm(ffmpeg: str, video: Path, bgm: Path, volume: float, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    # bgm 输入上的 `-stream_loop -1` 让 ffmpeg 无限循环它。
    # `amix duration=longest` 让混合后的音频随循环的 bgm 一起延长；
    # `-shortest` 则在两条流中先结束的那条处截断最终容器。
    # 用 `longest` 配 `-shortest`（而不是 `duration=first` 配 `-shortest`），
    # 可避免旁白音频恰好比视频略短时把视频流截断——混合音频会拉长以覆盖整个
    # 视频，于是 `-shortest` 会在视频时长处收尾。
    # `normalize=0` 关掉 amix 默认的 1/N 输入缩放——否则旁白会和（本来就很轻的）
    # bgm 一起被悄悄减半，使 --bgm-volume 同时影响两条音轨而不只影响音乐。
    filter_complex = (
        f'[1:a]volume={volume}[bgm];'
        f'[0:a][bgm]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0[aout]'
    )
    cmd = [
        ffmpeg, '-y', '-v', 'error',
        '-i', str(video),
        '-stream_loop', '-1', '-i', str(bgm),
        '-filter_complex', filter_complex,
        '-map', '0:v:0', '-map', '[aout]',
        '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
        '-shortest',
        str(output),
    ]
    log(f'mux bgm (volume={volume}): {video} + {bgm} -> {output}')
    media.run_ffmpeg(cmd[1:], ffmpeg=ffmpeg, timeout=300)


def main() -> int:
    args = parse_args()

    video = Path(args.video).expanduser().resolve()
    bgm = Path(args.bgm).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()

    if not video.is_file():
        raise FileNotFoundError(f'--video not found: {video}')
    if not bgm.is_file():
        raise FileNotFoundError(
            f'--bgm not found: {bgm}. The skill ships a default at '
            f'{DEFAULT_BGM_PATH}; if that file is missing, regenerate it or '
            f'pass --bgm /path/to/your.mp3.'
        )

    mux_bgm(args.ffmpeg, video, bgm, args.bgm_volume, output)
    out_dur = media.probe_duration(output, ffprobe=args.ffprobe)

    log(f'wrote {output} ({(output.stat().st_size / 1024 / 1024):.2f} MB, {out_dur}s)')
    cli.print_json({
        'success': True,
        'output_path': str(output),
        'bgm_path': str(bgm),
        'duration_s': out_dur,
    })
    return 0


if __name__ == '__main__':
    raise SystemExit(cli.run(main, TOOL_NAME))
