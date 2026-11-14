"""CLI integration tests for scripts/cut-clips.py.

The seam is the command line: the workspace argument, one JSON document on
stdout, exit codes 0 / 1 / 2, the files under <ws>/clips/ and the clip_path
written back into <ws>/material-catalog.json.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import media
from cli_helpers import parse_stdout as parse_result

pytestmark = pytest.mark.usefixtures('require_ffmpeg')

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / 'scripts' / 'cut-clips.py'
PIPELINE_STATUS_SCRIPT = REPO_ROOT / 'scripts' / 'pipeline-status.py'

SOURCE_SECONDS = 5
CLIP_A = (0.5, 2.0)
CLIP_B = (2.5, 4.5)
CLIP_A_PATH = 'clips/vid_001_0.50-2.00.mp4'
CLIP_B_PATH = 'clips/vid_001_2.50-4.50.mp4'
DURATION_TOLERANCE_S = 0.1


def make_source_with_audio(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
            '-f', 'lavfi', '-i', f'testsrc=duration={SOURCE_SECONDS}:size=160x120:rate=25',
            '-f', 'lavfi', '-i', f'sine=frequency=440:duration={SOURCE_SECONDS}',
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
            '-shortest', str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return path


def video_item(video_id: str, local_path: str, windows: list[tuple[float, float]]) -> dict:
    return {
        'id': video_id,
        'local_path': local_path,
        'semantic_description': '演示录屏',
        'selected_clips': [
            {'start': start, 'end': end, 'reason': '关键操作', 'frame_paths': []} for start, end in windows
        ],
    }


def write_catalog(ws: Path, videos: list[dict]) -> dict:
    catalog = {
        'topic_name': 'demo',
        'entries': [{'slug': 'example', 'images': [{'id': 'img_001', 'semantic_description': '图'}], 'videos': videos}],
    }
    ws.mkdir(parents=True, exist_ok=True)
    (ws / 'material-catalog.json').write_text(json.dumps(catalog, ensure_ascii=False), encoding='utf-8')
    return catalog


def read_catalog(ws: Path) -> dict:
    return json.loads((ws / 'material-catalog.json').read_text(encoding='utf-8'))


def clips_of(catalog: dict) -> list[dict]:
    return [clip for entry in catalog['entries'] for video in entry['videos'] for clip in video['selected_clips']]


@pytest.fixture(scope='module')
def source_video_bytes(tmp_path_factory: pytest.TempPathFactory, require_ffmpeg) -> bytes:
    source = make_source_with_audio(tmp_path_factory.mktemp('cut_clips_src') / 'vid_001.mp4')
    return source.read_bytes()


@pytest.fixture
def ws(tmp_path: Path, source_video_bytes: bytes) -> Path:
    """A workspace whose vid_001 has two selected clips; local_path is relative to harvest_page/."""
    workspace = tmp_path / 'ws'
    target = workspace / 'harvest_page' / 'example' / 'videos' / 'vid_001.mp4'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source_video_bytes)
    write_catalog(workspace, [video_item('vid_001', 'example/videos/vid_001.mp4', [CLIP_A, CLIP_B])])
    return workspace


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_cut_clips_lifecycle_cuts_skips_recovers_and_recuts_empty_files(ws: Path):
    catalog_file = ws / 'material-catalog.json'
    catalog_file.chmod(0o644)
    before = read_catalog(ws)
    proc = run_cli(str(ws))

    assert proc.returncode == 0, proc.stderr
    result = parse_result(proc)
    assert result == {
        'success': True,
        'clips': [
            {'ref': 'example/vid_001:0.5-2.0', 'clip_path': CLIP_A_PATH, 'skipped': False},
            {'ref': 'example/vid_001:2.5-4.5', 'clip_path': CLIP_B_PATH, 'skipped': False},
        ],
        'errors': [],
    }
    assert catalog_file.stat().st_mode & 0o777 == 0o644  # not the mkstemp default 0600
    for clip_path, (start, end) in ((CLIP_A_PATH, CLIP_A), (CLIP_B_PATH, CLIP_B)):
        info = media.probe(ws / clip_path)
        assert info['has_audio'] is False
        assert info['duration_seconds'] == pytest.approx(end - start, abs=DURATION_TOLERANCE_S)
        assert (info['width'], info['height']) == (160, 120)
    after = read_catalog(ws)
    assert [clip['clip_path'] for clip in clips_of(after)] == [CLIP_A_PATH, CLIP_B_PATH]
    for clip in clips_of(after):
        del clip['clip_path']
    assert after == before
    assert media.probe(ws / 'harvest_page' / 'example' / 'videos' / 'vid_001.mp4')['has_audio'] is True

    # 2. Second run skips clips that are already cut without rewriting catalog or targets.
    clip_files = [ws / CLIP_A_PATH, ws / CLIP_B_PATH]
    cut_at = [path.stat().st_mtime_ns for path in clip_files]
    catalog_bytes = catalog_file.read_bytes()
    second = parse_result(run_cli(str(ws)))
    assert [(clip['clip_path'], clip['skipped']) for clip in second['clips']] == [
        (CLIP_A_PATH, True),
        (CLIP_B_PATH, True),
    ]
    assert [path.stat().st_mtime_ns for path in clip_files] == cut_at
    assert catalog_file.read_bytes() == catalog_bytes

    # 3. Missing clip_path in catalog recovers existing non-empty files without probing/recutting.
    (ws / CLIP_B_PATH).write_bytes(b'any nonempty target counts as cut')
    catalog = read_catalog(ws)
    for clip in clips_of(catalog):
        del clip['clip_path']
    catalog_file.write_text(json.dumps(catalog), encoding='utf-8')
    recovered = parse_result(run_cli(str(ws)))
    assert [clip['skipped'] for clip in recovered['clips']] == [True, True]
    assert [clip['clip_path'] for clip in clips_of(read_catalog(ws))] == [CLIP_A_PATH, CLIP_B_PATH]
    assert (ws / CLIP_A_PATH).stat().st_mtime_ns == cut_at[0]
    assert (ws / CLIP_B_PATH).read_bytes() == b'any nonempty target counts as cut'

    # 4. An empty target file is cut again while non-empty siblings stay skipped.
    (ws / CLIP_A_PATH).write_bytes(b'')
    recut = parse_result(run_cli(str(ws)))
    assert [clip['skipped'] for clip in recut['clips']] == [False, True]
    assert media.probe(ws / CLIP_A_PATH)['duration_seconds'] == pytest.approx(
        CLIP_A[1] - CLIP_A[0], abs=DURATION_TOLERANCE_S
    )

    # 5. Editing an already-cut clip to an invalid window while its sibling stays skipped
    #    (changed=False) still flushes the popped stale clip_path in the finally save path.
    catalog = read_catalog(ws)
    clips_of(catalog)[0].update(start=3.0, end=3.0)
    catalog_file.write_text(json.dumps(catalog), encoding='utf-8')
    stale_proc = run_cli(str(ws))
    assert stale_proc.returncode == 1
    stale_res = parse_result(stale_proc)
    assert [(c['clip_path'], c['skipped']) for c in stale_res['clips']] == [(CLIP_B_PATH, True)]
    failed, kept = clips_of(read_catalog(ws))
    assert 'clip_path' not in failed
    assert kept['clip_path'] == CLIP_B_PATH


def test_a_failed_clip_clears_stale_clip_path_and_keeps_other_clips(
    tmp_path: Path, source_video_bytes: bytes
):
    ws = tmp_path / 'ws'
    good_source = ws / 'harvest_page' / 'example' / 'videos' / 'vid_001.mp4'
    good_source.parent.mkdir(parents=True, exist_ok=True)
    good_source.write_bytes(source_video_bytes)
    broken = ws / 'harvest_page' / 'example' / 'videos' / 'vid_002.mp4'
    broken.write_bytes(b'not a video')
    bad_item = video_item('vid_002', 'example/videos/vid_002.mp4', [CLIP_A])
    bad_item['selected_clips'][0]['clip_path'] = 'clips/stale_from_earlier_window.mp4'
    write_catalog(ws, [
        bad_item,
        video_item('vid_001', 'example/videos/vid_001.mp4', [CLIP_A]),
    ])

    proc = run_cli(str(ws))

    assert proc.returncode == 1
    result = parse_result(proc)
    assert result['success'] is False
    assert [clip['clip_path'] for clip in result['clips']] == [CLIP_A_PATH]
    assert [error['ref'] for error in result['errors']] == ['example/vid_002:0.5-2.0']
    assert result['errors'][0]['error']
    assert result['errors'][0]['stderr_tail']
    assert media.probe(ws / CLIP_A_PATH)['has_audio'] is False
    assert [path.name for path in (ws / 'clips').rglob('*.mp4')] == ['vid_001_0.50-2.00.mp4']
    failed, kept = clips_of(read_catalog(ws))
    assert 'clip_path' not in failed
    assert kept['clip_path'] == CLIP_A_PATH


def test_unusable_clips_are_collected_as_error_entries_without_crashing(
    ws: Path, tmp_path: Path, source_video_bytes: bytes
):
    outside = tmp_path / 'elsewhere' / 'vid_001.mp4'
    outside.parent.mkdir(parents=True)
    outside.write_bytes(source_video_bytes)
    write_catalog(ws, [
        video_item('miss', 'example/videos/missing.mp4', [CLIP_A]),
        video_item('nopath', '', [CLIP_A]),
        video_item('abspath', str(outside), [CLIP_A]),
        video_item('empty', 'example/videos/vid_001.mp4', [(3.0, 3.0)]),
        video_item('neg', 'example/videos/vid_001.mp4', [(-1.0, 2.0)]),
        video_item('../evil', 'example/videos/vid_001.mp4', [CLIP_A]),
        video_item('past', 'example/videos/vid_001.mp4', [(10.0, 12.0)]),
        video_item('partial', 'example/videos/vid_001.mp4', [(4.0, 9.0)]),
    ])

    proc = run_cli(str(ws))

    assert proc.returncode == 1
    result = parse_result(proc)
    assert result['success'] is False
    assert result['clips'] == []
    errors_by_ref = {err['ref']: err['error'] for err in result['errors']}
    assert len(errors_by_ref) == 8
    assert 'source video not found' in errors_by_ref['example/miss:0.5-2.0']
    assert 'local_path' in errors_by_ref['example/nopath:0.5-2.0']
    assert 'not relative to the harvest directory' in errors_by_ref['example/abspath:0.5-2.0']
    assert 'start < end' in errors_by_ref['example/empty:3.0-3.0']
    assert 'start < end' in errors_by_ref['example/neg:-1.0-2.0']
    assert 'file name' in errors_by_ref['example/../evil:0.5-2.0']
    assert 'no video' in errors_by_ref['example/past:10.0-12.0']
    assert 'extends past the end of the source' in errors_by_ref['example/partial:4.0-9.0']
    assert not (ws / 'clips').exists() or list((ws / 'clips').rglob('*.mp4')) == []


def test_a_catalog_without_video_clips_is_a_successful_no_op(tmp_path: Path):
    ws = tmp_path / 'ws'
    write_catalog(ws, [])

    proc = run_cli(str(ws))

    assert proc.returncode == 0, proc.stderr
    assert parse_result(proc) == {'success': True, 'clips': [], 'errors': []}
    assert not (ws / 'clips').exists()


def test_missing_or_unparseable_workspace_catalog_is_a_runtime_error(tmp_path: Path):
    missing_ws = run_cli(str(tmp_path / 'nope'))
    assert missing_ws.returncode == 1
    assert parse_result(missing_ws)['success'] is False

    missing_cat = run_cli(str(tmp_path))
    assert missing_cat.returncode == 1
    assert 'material-catalog.json' in parse_result(missing_cat)['error']

    (tmp_path / 'material-catalog.json').write_text('{not json', encoding='utf-8')
    bad_cat = run_cli(str(tmp_path))
    assert bad_cat.returncode == 1
    assert parse_result(bad_cat)['success'] is False


def test_missing_workspace_argument_exits_2():
    proc = run_cli()

    assert proc.returncode == 2
    assert parse_result(proc)['success'] is False


def test_a_video_shared_by_two_entries_reuses_the_same_target(ws: Path):
    catalog = read_catalog(ws)
    other = json.loads(json.dumps(catalog['entries'][0]))
    other['slug'] = 'other'
    catalog['entries'].append(other)
    (ws / 'material-catalog.json').write_text(json.dumps(catalog), encoding='utf-8')

    proc = run_cli(str(ws))

    assert proc.returncode == 0, proc.stderr
    result = parse_result(proc)
    assert [(clip['clip_path'], clip['skipped']) for clip in result['clips']] == [
        (CLIP_A_PATH, False),
        (CLIP_B_PATH, False),
        (CLIP_A_PATH, True),
        (CLIP_B_PATH, True),
    ]
    assert {path.relative_to(ws).as_posix() for path in (ws / 'clips').rglob('*.mp4')} == {
        CLIP_A_PATH,
        CLIP_B_PATH,
    }
    assert all('clip_path' in clip for clip in clips_of(read_catalog(ws)))


def test_missing_ffmpeg_is_a_runtime_error(ws: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv('FFMPEG_BIN', str(ws / 'no-such-ffmpeg'))

    proc = run_cli(str(ws))

    assert proc.returncode == 1
    result = parse_result(proc)
    assert result['success'] is False
    assert 'ffmpeg' in result['error']
    assert not (ws / 'clips').exists()


def run_pipeline_status_cli(ws: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(PIPELINE_STATUS_SCRIPT), str(ws), *args],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def complete_pipeline_prerequisites(ws: Path) -> None:
    (ws / 'inputs.json').write_text(json.dumps({
        'source': 'https://example.com/article',
        'input_mode': 'standard',
        'duration': '5min',
        'language': 'zh',
        'orientation': 'landscape',
        'template': None,
        'design': 'default',
        'layout': 'stage',
        'coding_agent': 'pi-coding-agent',
        'fetch_materials': True,
    }), encoding='utf-8')
    (ws / 'research-brief.md').write_text(
        '# research brief\n\n'
        '## Key facts (verified)\n- fact [source]\n\n'
        '## Quotes (verbatim if possible)\n- "quote" — Person, [source]\n\n'
        '## Numbers / dates\n- 1, unit, [source]\n\n'
        '## Source URLs (for Phase 4 harvest)\n- https://example.com/article — official site\n',
        encoding='utf-8',
    )
    (ws / 'harvest_page' / 'manifest.json').write_text(json.dumps({
        'version': 2,
        'entries': [{'slug': 'example', 'images': [], 'videos': []}],
        'harvest_batches': [{
            'at': '2026-01-01T00:00:00Z',
            'urls': ['https://example.com/article'],
            'succeeded': 1,
            'failed': 0,
            'rejected': [],
        }],
    }), encoding='utf-8')


def test_an_ffmpeg_that_hangs_times_out_and_leaves_no_file(
    ws: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # Half-writes its output, then hangs: the CLI must report both timeouts as JSON.
    hanging = tmp_path / 'hanging-ffmpeg'
    hanging.write_text(
        f'#!{sys.executable}\n'
        'import sys, time\n'
        "open(sys.argv[-1], 'wb').write(b'half a file')\n"
        'time.sleep(60)\n',
        encoding='utf-8',
    )
    hanging.chmod(0o755)
    monkeypatch.setenv('FFMPEG_BIN', str(hanging))
    monkeypatch.setenv('CUT_CLIPS_FFMPEG_TIMEOUT', '0.5')

    proc = run_cli(str(ws))

    assert proc.returncode == 1, proc.stderr
    result = parse_result(proc)
    assert result['success'] is False
    assert [error['ref'] for error in result['errors']] == [
        'example/vid_001:0.5-2.0', 'example/vid_001:2.5-4.5'
    ]
    assert list((ws / 'clips').rglob('*.mp4')) == []
    assert all('clip_path' not in clip for clip in clips_of(read_catalog(ws)))


def test_pipeline_status_gates_catalog_on_present_cut_clips(ws: Path):
    complete_pipeline_prerequisites(ws)

    before_proc = run_pipeline_status_cli(ws)
    assert before_proc.returncode == 0, before_proc.stderr
    before = parse_result(before_proc)
    assert before['next_phase']['id'] == '5-material-catalog'
    assert 'material-catalog.json' in before['corrupt_products']
    assert 'clip_path' in before['next_phase']['problems']['material-catalog.json']

    assert run_cli(str(ws)).returncode == 0

    after_proc = run_pipeline_status_cli(ws)
    assert after_proc.returncode == 0, after_proc.stderr
    after = parse_result(after_proc)
    assert '5-material-catalog' in after['completed_phases']
    assert after['next_phase']['id'] == '6-script-scene-plan'

    (ws / CLIP_A_PATH).unlink()
    missing_proc = run_pipeline_status_cli(ws)
    assert missing_proc.returncode == 0, missing_proc.stderr
    missing = parse_result(missing_proc)
    assert missing['next_phase']['id'] == '5-material-catalog'
    assert 'material-catalog.json' in missing['corrupt_products']
    assert CLIP_A_PATH in missing['next_phase']['problems']['material-catalog.json']


def test_ffmpeg_receives_exactly_the_specified_cut_options(
    ws: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    real_ffmpeg = shutil.which('ffmpeg')
    args_log = tmp_path / 'ffmpeg-args.json'
    recording_ffmpeg = tmp_path / 'recording-ffmpeg'
    recording_ffmpeg.write_text(
        f'#!{sys.executable}\n'
        'import json, os, sys\n'
        'from pathlib import Path\n'
        f'Path({str(args_log)!r}).write_text(json.dumps(sys.argv[1:]), encoding="utf-8")\n'
        f'os.execv({real_ffmpeg!r}, [{real_ffmpeg!r}, *sys.argv[1:]])\n',
        encoding='utf-8',
    )
    recording_ffmpeg.chmod(0o755)
    monkeypatch.setenv('FFMPEG_BIN', str(recording_ffmpeg))
    catalog = read_catalog(ws)
    catalog['entries'][0]['videos'][0]['selected_clips'] = [clips_of(catalog)[0]]
    (ws / 'material-catalog.json').write_text(json.dumps(catalog), encoding='utf-8')

    proc = run_cli(str(ws))

    assert proc.returncode == 0, proc.stderr
    assert json.loads(args_log.read_text(encoding='utf-8')) == [
        '-hide_banner', '-loglevel', 'error', '-nostdin', '-y',
        '-ss', '0.500', '-to', '2.000',
        '-i', str(ws / 'harvest_page' / 'example' / 'videos' / 'vid_001.mp4'),
        '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18',
        '-movflags', '+faststart',
        str(ws / 'clips' / '.vid_001_0.50-2.00.part.mp4'),
    ]
