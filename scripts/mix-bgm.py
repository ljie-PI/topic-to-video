#!/usr/bin/env python3
"""Mix a background-music track onto a finished video.

Two-step pipeline backed by ffmpeg:

  1. Prepare a loopable BGM clip from a source mp3 (trim the first N seconds
     and write a clean mp3 at the requested target). Stored alongside the
     final video as `bgm.mp3` by default so it can be reused/inspected.
  2. Mux the BGM into the video with the original narration:
       - narration kept at full volume (vocals)
       - bgm scaled down (default 0.03) and looped to match video duration
       - the two are mixed; output preserves the video stream as-is.

Usage:
  python3 mix-bgm.py \\
      --video composition/renders/final.mp4 \\
      --bgm-source ~/Downloads/The_Daily_Ledger.mp3 \\
      --bgm-trim-start 0 --bgm-trim-end 24 \\
      --bgm-volume 0.03 \\
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
    p.add_argument('--bgm-source', required=True, help='Source mp3 for BGM (will be trimmed).')
    p.add_argument('--bgm-trim-start', type=float, default=0.0, help='Start second to cut from bgm-source. Default 0.')
    p.add_argument('--bgm-trim-end', type=float, default=24.0, help='End second to cut from bgm-source. Default 24.')
    p.add_argument('--bgm-volume', type=float, default=0.03, help='Linear gain for BGM (0-1). Default 0.03.')
    p.add_argument('--bgm-path', default=None,
                   help='Where to write the trimmed bgm.mp3. Default: next to --output as bgm.mp3.')
    p.add_argument('--output', required=True, help='Output video path.')
    p.add_argument('--ffmpeg', default='ffmpeg', help='ffmpeg binary path. Default `ffmpeg`.')
    p.add_argument('--ffprobe', default='ffprobe', help='ffprobe binary path. Default `ffprobe`.')
    return p.parse_args()


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


def trim_bgm(ffmpeg: str, source: Path, start: float, end: float, dest: Path) -> None:
    if end <= start:
        raise ValueError(f'--bgm-trim-end ({end}) must be greater than --bgm-trim-start ({start})')
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg, '-y', '-v', 'error',
        '-ss', f'{start:g}', '-to', f'{end:g}',
        '-i', str(source),
        '-vn', '-c:a', 'libmp3lame', '-b:a', '192k',
        str(dest),
    ]
    log(f'trim bgm: {source} [{start}-{end}s] -> {dest}')
    subprocess.run(cmd, check=True)


def mux_bgm(ffmpeg: str, video: Path, bgm: Path, volume: float, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    # -stream_loop -1 on the bgm input causes ffmpeg to loop it; -shortest
    # then cuts the mix at the original video duration so the bgm stretches
    # to cover the whole timeline regardless of bgm length vs video length.
    filter_complex = (
        f'[1:a]volume={volume}[bgm];'
        f'[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=0[aout]'
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
    subprocess.run(cmd, check=True)


def main() -> int:
    try:
        args = parse_args()

        video = Path(args.video).expanduser().resolve()
        source = Path(args.bgm_source).expanduser().resolve()
        output = Path(args.output).expanduser().resolve()
        bgm_path = (Path(args.bgm_path).expanduser().resolve()
                    if args.bgm_path else output.parent / 'bgm.mp3')

        if not video.is_file():
            raise FileNotFoundError(f'--video not found: {video}')
        if not source.is_file():
            raise FileNotFoundError(f'--bgm-source not found: {source}')

        # 1. trim bgm (skip if already exists and matches requested duration)
        wanted_dur = args.bgm_trim_end - args.bgm_trim_start
        if bgm_path.is_file():
            existing_dur = probe_duration(args.ffprobe, bgm_path) or 0
            if abs(existing_dur - wanted_dur) < 0.5:
                log(f'reusing existing bgm: {bgm_path} ({existing_dur:.2f}s)')
            else:
                trim_bgm(args.ffmpeg, source, args.bgm_trim_start, args.bgm_trim_end, bgm_path)
        else:
            trim_bgm(args.ffmpeg, source, args.bgm_trim_start, args.bgm_trim_end, bgm_path)

        # 2. mux
        mux_bgm(args.ffmpeg, video, bgm_path, args.bgm_volume, output)
        out_dur = probe_duration(args.ffprobe, output)

        log(f'wrote {output} ({(output.stat().st_size / 1024 / 1024):.2f} MB, {out_dur}s)')
        print_json({
            'success': True,
            'output_path': str(output),
            'bgm_path': str(bgm_path),
            'duration_s': out_dur,
        })
        return 0
    except SystemExit:
        raise
    except subprocess.CalledProcessError as exc:
        log(f'ffmpeg failed: {exc}')
        print_json({'success': False, 'error': f'ffmpeg failed: {exc}'})
        return 1
    except Exception as exc:
        log(f'error: {exc}')
        print_json({'success': False, 'error': str(exc)})
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
