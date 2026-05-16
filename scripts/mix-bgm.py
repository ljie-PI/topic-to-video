#!/usr/bin/env python3
"""Mix a background-music track onto a finished video.

Single ffmpeg pass: load the bundled `assets/bgm.mp3` (a 24-second loopable
clip that ships with the skill), loop it to cover the video, and mix it under
the existing narration. The narration stays at full volume; the BGM is
attenuated by `--bgm-volume` (default 0.03).

Usage:
  python3 scripts/mix-bgm.py \\
      --video composition/renders/final.mp4 \\
      --output composition/renders/final_with_bgm.mp4

  # Override the music file or its volume if needed:
  python3 scripts/mix-bgm.py \\
      --video composition/renders/final.mp4 \\
      --bgm /path/to/other.mp3 \\
      --bgm-volume 0.05 \\
      --output composition/renders/final_with_bgm.mp4

Output convention:
  stdout : JSON {success, output_path, bgm_path, duration_s}
  stderr : human-readable progress prefixed with `[mix-bgm]`
  exit   : 0 success, 1 runtime error, 2 invalid arguments
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

TOOL_NAME = 'mix-bgm'

# Bundled BGM lives at <skill_root>/assets/bgm.mp3. The path is derived
# from __file__ so the script works from any CWD.
DEFAULT_BGM_PATH = Path(__file__).resolve().parent.parent / 'assets' / 'bgm.mp3'


def log(message: str) -> None:
    print(f'[{TOOL_NAME}] {message}', file=sys.stderr)


def print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False))


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        log(f'bad arguments: {message}')
        print_json({'success': False, 'error': message})
        raise SystemExit(2)


def parse_args() -> argparse.Namespace:
    p = JsonArgumentParser(description='Mix a BGM track onto a video with ffmpeg.')
    p.add_argument('--video', required=True, help='Input video (must already contain narration audio).')
    p.add_argument('--bgm', default=str(DEFAULT_BGM_PATH),
                   help=f'BGM mp3 to loop under the narration. Default: bundled '
                        f'{DEFAULT_BGM_PATH.name} at {DEFAULT_BGM_PATH}.')
    p.add_argument('--bgm-volume', type=float, default=0.03,
                   help='Linear gain for BGM, 0.0-1.0. Default 0.03.')
    p.add_argument('--output', required=True, help='Output video path.')
    p.add_argument('--ffmpeg', default='ffmpeg', help='ffmpeg binary path. Default `ffmpeg`.')
    p.add_argument('--ffprobe', default='ffprobe', help='ffprobe binary path. Default `ffprobe`.')
    args = p.parse_args()
    if not 0.0 <= args.bgm_volume <= 1.0:
        p.error(f'--bgm-volume must be within [0.0, 1.0] (got {args.bgm_volume})')
    return args


def probe_duration(ffprobe: str, path: Path) -> Optional[float]:
    try:
        out = subprocess.check_output(
            [ffprobe, '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', str(path)],
            timeout=15,
        )
        return float(out.decode().strip())
    except Exception as exc:
        log(f'ffprobe failed for {path}: {exc}')
        return None


def run_ffmpeg(cmd: list, label: str) -> None:
    """Run an ffmpeg command and surface stderr on failure."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        stderr_tail = (result.stderr or '').strip().splitlines()
        # keep the last ~20 lines so the error stays useful but the
        # JSON payload doesn't explode
        tail = '\n'.join(stderr_tail[-20:]) if stderr_tail else '(no stderr)'
        raise RuntimeError(
            f'ffmpeg failed during {label} (exit={result.returncode}): {tail}'
        )


def mux_bgm(ffmpeg: str, video: Path, bgm: Path, volume: float, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    # `-stream_loop -1` on the bgm input causes ffmpeg to loop it forever.
    # `amix duration=longest` lets the mixed audio extend with the looping bgm;
    # `-shortest` then cuts the final container at whichever stream ends first.
    # Pairing `longest` with `-shortest` (instead of `duration=first` with
    # `-shortest`) avoids truncating the video stream when the narration audio
    # happens to be slightly shorter than the video — the mixed audio stretches
    # to cover the video, so `-shortest` clips on the video duration.
    # `normalize=0` disables amix's default 1/N input scaling — without it the
    # narration would be silently halved alongside the (already quiet) bgm,
    # making --bgm-volume affect both tracks instead of just the music.
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
    run_ffmpeg(cmd, 'mux')


def main() -> int:
    try:
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
        out_dur = probe_duration(args.ffprobe, output)
        if out_dur is None:
            raise RuntimeError(
                f'could not probe duration of {output}; ffprobe may be missing '
                f'or the output is unreadable'
            )

        log(f'wrote {output} ({(output.stat().st_size / 1024 / 1024):.2f} MB, {out_dur}s)')
        print_json({
            'success': True,
            'output_path': str(output),
            'bgm_path': str(bgm),
            'duration_s': out_dur,
        })
        return 0
    except SystemExit:
        raise
    except Exception as exc:
        log(f'error: {exc}')
        print_json({'success': False, 'error': str(exc)})
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
