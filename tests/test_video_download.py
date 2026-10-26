"""yt-dlp subprocess tests using real ffmpeg/ffprobe and a fake downloader."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import harvest_manifest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / 'scripts' / 'video-download.py'
URL = 'https://www.youtube.com/watch?v=fixture123'

FAKE_YTDLP = r'''#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path

args = sys.argv[1:]
Path(os.environ['YTDLP_ARGS']).write_text('\n'.join(args), encoding='utf-8')
if os.environ.get('YTDLP_FAIL'):
    print('ERROR: video unavailable', file=sys.stderr)
    raise SystemExit(1)
template = args[args.index('--output') + 1]
video = Path(template.replace('%(id)s', 'fixture').replace('%(ext)s', 'mp4'))
video.parent.mkdir(parents=True, exist_ok=True)
if '--skip-download' not in args:
    subprocess.run([
        'ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi',
        '-i', 'testsrc=size=320x240:rate=10', '-t', '1', '-pix_fmt', 'yuv420p', str(video),
    ], check=True)
subtitle = video.with_name('fixture.en.srt')
subtitle.write_text('1\n00:00:00,000 --> 00:00:01,000\nfixture\n', encoding='utf-8')
'''


def prepare(tmp_path: Path):
    fake_bin = tmp_path / 'bin'
    fake_bin.mkdir()
    executable = fake_bin / 'yt-dlp'
    executable.write_text(FAKE_YTDLP, encoding='utf-8')
    executable.chmod(0o755)
    harvest_dir = tmp_path / 'harvest_page'
    harvest_manifest.upsert_entries(harvest_dir, [{
        'slug': 'source', 'url': 'https://example.com/', 'success': True,
        'images': [], 'scroll_recording': None,
        'videos': [{
            'url': URL, 'platform': 'youtube', 'download_required': True,
            'suggested_output_dir': 'source/videos',
        }],
    }])
    env = dict(os.environ)
    env['PATH'] = f'{fake_bin}{os.pathsep}{env["PATH"]}'
    env['YTDLP_ARGS'] = str(tmp_path / 'yt-dlp-args.txt')
    return harvest_dir, env


def test_harvest_download_uses_suggested_dir_and_updates_manifest_and_mirror(
    tmp_path: Path, require_ffmpeg: None,
):
    harvest_dir, env = prepare(tmp_path)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), '--url', URL, '--harvest-dir', str(harvest_dir)],
        capture_output=True, text=True, env=env, timeout=60, check=False,
    )

    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result['success'] is True
    assert result['manifest_updated'] is True
    args = env and Path(env['YTDLP_ARGS']).read_text(encoding='utf-8').splitlines()
    convert = args.index('--convert-subs')
    assert args[convert + 1] == 'srt'
    manifest = json.loads((harvest_dir / 'manifest.json').read_text(encoding='utf-8'))
    video = manifest['entries'][0]['videos'][0]
    assert video['download_required'] is False
    assert video['local_path'] == 'source/videos/fixture.mp4'
    assert video['subtitle_path'] == 'source/videos/fixture.en.srt'
    assert video['id'] == 'fixture'
    assert video['width'] == 320
    assert video['height'] == 240
    assert video['duration_seconds'] == 1.0
    assert manifest['pending_downloads'] == []
    mirror = json.loads((harvest_dir / 'source' / 'metadata.json').read_text(encoding='utf-8'))
    assert mirror == manifest['entries'][0]


def test_subtitles_only_harvest_is_rejected_before_calling_ytdlp(tmp_path: Path):
    harvest_dir, env = prepare(tmp_path)
    before = (harvest_dir / 'manifest.json').read_bytes()

    proc = subprocess.run(
        [
            sys.executable, str(SCRIPT), '--url', URL,
            '--harvest-dir', str(harvest_dir), '--subtitles-only',
        ],
        capture_output=True, text=True, env=env, timeout=60, check=False,
    )

    assert proc.returncode == 2
    result = json.loads(proc.stdout)
    assert result['success'] is False
    assert '--subtitles-only' in result['error']
    assert '--harvest-dir' in result['error']
    assert not Path(env['YTDLP_ARGS']).exists()
    assert (harvest_dir / 'manifest.json').read_bytes() == before


def test_failed_download_outputs_json_and_leaves_manifest_unchanged(tmp_path: Path):
    harvest_dir, env = prepare(tmp_path)
    env['YTDLP_FAIL'] = '1'
    before = (harvest_dir / 'manifest.json').read_bytes()
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), '--url', URL, '--harvest-dir', str(harvest_dir)],
        capture_output=True, text=True, env=env, timeout=60, check=False,
    )

    assert proc.returncode == 1
    result = json.loads(proc.stdout)
    assert result['success'] is False
    assert 'unavailable' in result['error'].lower()
    assert (harvest_dir / 'manifest.json').read_bytes() == before
