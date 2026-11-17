"""yt-dlp subprocess tests using real ffmpeg/ffprobe and a fake downloader."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import harvest_manifest
import pytest
from cli_helpers import load_script_module

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
template = args[args.index('--output') + 1]
video = Path(template.replace('%(id)s', 'fixture').replace('%(ext)s', 'mp4'))
video.parent.mkdir(parents=True, exist_ok=True)

if os.environ.get('YTDLP_FAIL_STDERR'):
    video.with_name('fixture.mp4.part').write_bytes(b'partial')
    print(os.environ['YTDLP_FAIL_STDERR'], file=sys.stderr)
    raise SystemExit(1)
if os.environ.get('YTDLP_FAIL'):
    print('ERROR: video unavailable', file=sys.stderr)
    raise SystemExit(1)

mode = os.environ.get('YTDLP_MODE', 'valid')
if mode == 'storyboard_mhtml':
    video.with_name('fixture.mhtml').write_text('MIME-Version: 1.0\nstoryboard\n', encoding='utf-8')
    video.with_name('fixture.en.srt').write_text('1\n00:00:00,000 --> 00:00:01,000\nfixture\n', encoding='utf-8')
    raise SystemExit(0)
if mode == 'corrupt_zero_mp4':
    video.write_bytes(b'')
    video.with_name('fixture.en.srt').write_text('1\n00:00:00,000 --> 00:00:01,000\nfixture\n', encoding='utf-8')
    raise SystemExit(0)
if mode == 'empty_dir':
    raise SystemExit(0)

if '--skip-download' not in args:
    subprocess.run([
        'ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi',
        '-i', 'testsrc=size=320x240:rate=10', '-t', '1', '-pix_fmt', 'yuv420p', str(video),
    ], check=True)
subtitle = video.with_name('fixture.en.srt')
subtitle.write_text('1\n00:00:00,000 --> 00:00:01,000\nfixture\n', encoding='utf-8')
'''


def _make_valid_mp4(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            'ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi',
            '-i', 'testsrc=size=160x120:rate=10', '-t', '1', '-pix_fmt', 'yuv420p', str(path),
        ],
        check=True,
    )


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
    env['YTDLP_BIN'] = str(executable)
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
    args = Path(env['YTDLP_ARGS']).read_text(encoding='utf-8').splitlines()
    convert = args.index('--convert-subs')
    assert args[convert + 1] == 'srt'
    fmt = args.index('--format')
    assert args[fmt + 1] == 'bv*+ba/b'
    out_template = Path(args[args.index('--output') + 1])
    assert out_template.parent.name.startswith('.ytdlp-')
    videos_dir = harvest_dir / 'source' / 'videos'
    assert not [p for p in videos_dir.iterdir() if p.name.startswith('.ytdlp-')]
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
    assert result['failure_kind'] == 'unavailable'
    assert 'unavailable' in result['error'].lower()
    assert (harvest_dir / 'manifest.json').read_bytes() == before


def test_resolve_ytdlp_binary_prefers_override_then_venv_then_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    mod = load_script_module('video-download.py', 'video_download_resolve')

    fake_venv_bin = tmp_path / 'venv' / 'bin'
    fake_venv_bin.mkdir(parents=True)
    fake_python = fake_venv_bin / 'python3'
    fake_python.write_text('#!/bin/sh\n', encoding='utf-8')
    venv_ytdlp = fake_venv_bin / 'yt-dlp'
    venv_ytdlp.write_text('#!/bin/sh\n', encoding='utf-8')
    venv_ytdlp.chmod(0o755)

    homebrew_bin = tmp_path / 'homebrew' / 'bin'
    homebrew_bin.mkdir(parents=True)
    path_ytdlp = homebrew_bin / 'yt-dlp'
    path_ytdlp.write_text('#!/bin/sh\n', encoding='utf-8')
    path_ytdlp.chmod(0o755)

    monkeypatch.setattr(mod.sys, 'executable', str(fake_python))
    monkeypatch.setenv('PATH', str(homebrew_bin))

    # 1) YTDLP_BIN wins over both venv sibling and PATH.
    monkeypatch.setenv('YTDLP_BIN', '  /custom/override/yt-dlp  ')
    assert mod.resolve_ytdlp_binary() == '/custom/override/yt-dlp'

    # 2) Venv sibling wins over an earlier directory on PATH (e.g. /opt/homebrew/bin).
    monkeypatch.delenv('YTDLP_BIN', raising=False)
    assert mod.resolve_ytdlp_binary() == str(venv_ytdlp)

    # 3) Falls back to PATH when venv binary is absent, and 'yt-dlp' when PATH has none.
    venv_ytdlp.unlink()
    assert mod.resolve_ytdlp_binary() == str(path_ytdlp)
    monkeypatch.setenv('PATH', str(tmp_path / 'empty-bin'))
    assert mod.resolve_ytdlp_binary() == 'yt-dlp'


def test_preexisting_video_preserved_and_never_mistaken_for_new_download(
    tmp_path: Path, require_ffmpeg: None,
):
    harvest_dir, env = prepare(tmp_path)
    videos_dir = harvest_dir / 'source' / 'videos'
    existing_video = videos_dir / 'already_there.mp4'
    _make_valid_mp4(existing_video)
    existing_bytes = existing_video.read_bytes()
    before_manifest = (harvest_dir / 'manifest.json').read_bytes()

    for mode, fail_stderr, expected_kind in (
        ('storyboard_mhtml', None, 'storyboard_only'),
        ('empty_dir', None, 'storyboard_only'),
        ('valid', 'ERROR: [youtube] fixture123: Video unavailable', 'unavailable'),
    ):
        run_env = dict(env)
        run_env['YTDLP_MODE'] = mode
        if fail_stderr:
            run_env['YTDLP_FAIL_STDERR'] = fail_stderr
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), '--url', URL, '--harvest-dir', str(harvest_dir)],
            capture_output=True, text=True, env=run_env, timeout=60, check=False,
        )
        assert proc.returncode == 1, proc.stderr
        result = json.loads(proc.stdout)
        assert result['success'] is False
        assert result['failure_kind'] == expected_kind
        assert existing_video.read_bytes() == existing_bytes
        assert [p.name for p in videos_dir.iterdir()] == ['already_there.mp4']
        assert (harvest_dir / 'manifest.json').read_bytes() == before_manifest


@pytest.mark.parametrize('mode', ['storyboard_mhtml', 'corrupt_zero_mp4'])
def test_storyboard_or_zero_byte_video_rejected_without_touching_manifest(
    tmp_path: Path, require_ffmpeg: None, mode: str,
):
    harvest_dir, env = prepare(tmp_path)
    env['YTDLP_MODE'] = mode
    before_manifest = (harvest_dir / 'manifest.json').read_bytes()

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), '--url', URL, '--harvest-dir', str(harvest_dir)],
        capture_output=True, text=True, env=env, timeout=60, check=False,
    )

    assert proc.returncode == 1
    result = json.loads(proc.stdout)
    assert result['success'] is False
    assert result['failure_kind'] == 'storyboard_only'
    manifest = json.loads((harvest_dir / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['entries'][0]['videos'][0]['download_required'] is True
    assert (harvest_dir / 'manifest.json').read_bytes() == before_manifest
    videos_dir = harvest_dir / 'source' / 'videos'
    assert list(videos_dir.iterdir()) == []


@pytest.mark.parametrize(
    'stderr_line',
    [
        'ERROR: [youtube] abc: Sign in to confirm you\u2019re not a bot. Use --cookies-from-browser or --cookies for the authentication.',
        'ERROR: [youtube] abc: LOGIN_REQUIRED',
    ],
)
def test_bot_check_stderr_returns_bot_check_failure_kind(tmp_path: Path, stderr_line: str):
    harvest_dir, env = prepare(tmp_path)
    env['YTDLP_FAIL_STDERR'] = stderr_line
    before_manifest = (harvest_dir / 'manifest.json').read_bytes()

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), '--url', URL, '--harvest-dir', str(harvest_dir)],
        capture_output=True, text=True, env=env, timeout=60, check=False,
    )

    assert proc.returncode == 1
    result = json.loads(proc.stdout)
    assert result['success'] is False
    assert result['failure_kind'] == 'bot_check'
    assert (harvest_dir / 'manifest.json').read_bytes() == before_manifest
    assert list((harvest_dir / 'source' / 'videos').iterdir()) == []


def test_detect_common_issue_and_missing_binary_failure_kinds(tmp_path: Path):
    mod = load_script_module('video-download.py', 'video_download_issues')
    cases = [
        ("ERROR: [youtube] abc: Sign in to confirm you're not a bot", 'bot_check'),
        ('ERROR: [youtube] abc: Sign in to confirm your age', 'login_required'),
        ('ERROR: This video requires login', 'login_required'),
        (
            'WARNING: [youtube] abc: Only images are available for download.\n'
            'ERROR: [youtube] abc: Requested format is not available.',
            'storyboard_only',
        ),
        (
            'ERROR: [youtube] abc: Requested format is not available (only storyboard formats found)',
            'storyboard_only',
        ),
        ('ERROR: Requested format is not available', 'format_unavailable'),
        ('ERROR: HTTP Error 429: Too Many Requests', 'rate_limited'),
        ('ERROR: This video is private', 'unavailable'),
        ('ERROR: Unsupported URL: https://example.com/foo', 'invalid_url'),
        ('ERROR: File is larger than max-filesize', 'max_filesize'),
        ('ERROR: Unable to download webpage: certificate verify failed', 'network_error'),
        ('ERROR: Unable to extract player response', 'extract_error'),
        ('something completely unexpected', 'unknown'),
    ]
    for raw_output, expected_kind in cases:
        kind, message = mod.detect_common_issue(raw_output)
        assert kind == expected_kind
        assert message

    env = dict(os.environ)
    env['YTDLP_BIN'] = str(tmp_path / 'does-not-exist-yt-dlp')
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), '--url', URL, '--output-dir', str(tmp_path / 'out')],
        capture_output=True, text=True, env=env, timeout=30, check=False,
    )
    assert proc.returncode == 1
    result = json.loads(proc.stdout)
    assert result['success'] is False
    assert result['failure_kind'] == 'missing_binary'


def test_subtitles_only_moves_only_new_subtitles_without_format_flag(tmp_path: Path):
    _, env = prepare(tmp_path)
    out_dir = tmp_path / 'subs_out'
    out_dir.mkdir()
    stale = out_dir / 'stale.en.srt'
    stale.write_text('old\n', encoding='utf-8')

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), '--url', URL, '--output-dir', str(out_dir), '--subtitles-only'],
        capture_output=True, text=True, env=env, timeout=60, check=False,
    )

    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result['success'] is True
    assert result['files'] == [str((out_dir / 'fixture.en.srt').resolve())]
    assert result['videos'] == []
    assert stale.read_text(encoding='utf-8') == 'old\n'
    args = Path(env['YTDLP_ARGS']).read_text(encoding='utf-8').splitlines()
    assert '--skip-download' in args
    assert '--format' not in args


def test_missing_ffprobe_accepts_nonempty_video_and_rejects_empty_video(
    tmp_path: Path, require_ffmpeg: None,
):
    harvest_dir, env = prepare(tmp_path)
    env['FFPROBE_BIN'] = str(tmp_path / 'missing-ffprobe')

    # Empty video is rejected even without ffprobe.
    empty_env = dict(env, YTDLP_MODE='corrupt_zero_mp4')
    proc_empty = subprocess.run(
        [sys.executable, str(SCRIPT), '--url', URL, '--output-dir', str(tmp_path / 'empty_out')],
        capture_output=True, text=True, env=empty_env, timeout=60, check=False,
    )
    assert proc_empty.returncode == 1
    assert json.loads(proc_empty.stdout)['failure_kind'] == 'storyboard_only'

    # Non-empty video succeeds when ffprobe is unavailable.
    proc_ok = subprocess.run(
        [sys.executable, str(SCRIPT), '--url', URL, '--harvest-dir', str(harvest_dir)],
        capture_output=True, text=True, env=env, timeout=60, check=False,
    )
    assert proc_ok.returncode == 0, proc_ok.stderr
    result = json.loads(proc_ok.stdout)
    assert result['success'] is True
    assert result['videos'][0]['width'] is None
    assert result['videos'][0]['duration_seconds'] is None


def test_timeout_and_runtime_error_include_failure_kind_and_clean_temp_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
):
    mod = load_script_module('video-download.py', 'video_download_timeout')
    out_dir = tmp_path / 'downloads'
    out_dir.mkdir()

    def fake_timeout(cmd, **kwargs):
        out_template = Path(cmd[cmd.index('--output') + 1])
        (out_template.parent / 'partial.part').write_bytes(b'incomplete')
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs['timeout'], output=b'stalled')

    monkeypatch.setattr(mod.subprocess, 'run', fake_timeout)
    monkeypatch.setattr(mod.sys, 'argv', ['video-download.py', '--url', URL, '--output-dir', str(out_dir)])
    assert mod.main() == 1
    timeout_payload = json.loads(capsys.readouterr().out)
    assert timeout_payload['success'] is False
    assert timeout_payload['failure_kind'] == 'timeout'
    assert 'stalled' in timeout_payload['error']
    assert list(out_dir.iterdir()) == []

    regular_file = tmp_path / 'not_a_dir'
    regular_file.write_text('x', encoding='utf-8')
    monkeypatch.setattr(mod.sys, 'argv', ['video-download.py', '--url', URL, '--output-dir', str(regular_file)])
    assert mod.main() == 1
    err_payload = json.loads(capsys.readouterr().out)
    assert err_payload['success'] is False
    assert err_payload['failure_kind'] == 'unknown'
