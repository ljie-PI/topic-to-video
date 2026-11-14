"""CLI and workflow tests for scripts/stitch-frames.py."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / 'scripts' / 'stitch-frames.py'
EXTRACT = REPO_ROOT / 'scripts' / 'extract-frames.py'
VISION = REPO_ROOT / 'scripts' / 'vision-analyze.py'


def run_cli(frames_json: Path, output_dir: Path, *args: str, cwd: Path | None = None):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), '--frames-json', str(frames_json), '--output-dir', str(output_dir), *args],
        capture_output=True, text=True, check=False, timeout=30, cwd=cwd,
    )
    assert len(proc.stdout.splitlines()) == 1, proc.stderr + proc.stdout
    return proc, json.loads(proc.stdout)


def make_frames(tmp_path: Path, count: int):
    frames_dir = tmp_path / 'frames'
    frames_dir.mkdir()
    frames = []
    for index in range(count):
        path = frames_dir / f'frame_{index:03d}.png'
        Image.new('RGB', (120, 68), (index * 7 % 256, 80, 100)).save(path)
        frames.append({'path': str(path), 't_s': 90.5 + index})
    frames_json = tmp_path / 'frames.json'
    # Deliberately unordered: sorting must use JSON timestamps, not filenames or input order.
    frames_json.write_text(json.dumps({'success': True, 'interval_s': 1.0, 'frames': frames[::-1]}), encoding='utf-8')
    return frames_json, frames


def test_sixteen_frames_are_one_annotated_row_major_grid(tmp_path: Path):
    frames_json, frames = make_frames(tmp_path, 16)
    before = {Path(frame['path']): Path(frame['path']).read_bytes() for frame in frames}
    original_json = frames_json.read_bytes()
    output_dir = tmp_path / 'sheets'

    proc, result = run_cli(frames_json, output_dir, '--cell-width', '160')

    assert proc.returncode == 0, proc.stderr
    assert result['frame_count'] == 16
    assert result['sheet_count'] == 1
    sheet = result['sheets'][0]
    assert sheet['start_s'] == 90.5 and sheet['end_s'] == 105.5
    assert [frame['index'] for frame in sheet['frames']] == list(range(1, 17))
    assert [frame['cell'] for frame in sheet['frames']] == list(range(16))
    assert [frame['path'] for frame in sheet['frames']] == [frame['path'] for frame in frames]
    with Image.open(sheet['path']) as image:
        assert image.format == 'PNG'
        assert image.size == (160 * 4, (68 + 32) * 4)
        for cell in range(16):
            left, top = cell % 4 * 160, cell // 4 * 100
            assert image.getpixel((left + 80, top + 32 + 34)) == (cell * 7, 80, 100)
            # Labels are outside the source image and contain visible text.
            strip = image.crop((left + 1, top + 1, left + 159, top + 31))
            assert len(strip.getcolors(maxcolors=10000)) > 1
    assert json.loads((output_dir / 'manifest.json').read_text(encoding='utf-8')) == result
    assert frames_json.read_bytes() == original_json
    assert all(path.read_bytes() == contents for path, contents in before.items())


@pytest.mark.parametrize('count, sizes', [(1, [1]), (15, [15]), (17, [16, 1]), (32, [16, 16])])
def test_pagination_keeps_every_frame_and_marks_unused_cells(tmp_path: Path, count, sizes):
    frames_json, frames = make_frames(tmp_path, count)
    proc, result = run_cli(frames_json, tmp_path / 'sheets', '--cell-width', '160')

    assert proc.returncode == 0, proc.stderr
    assert [sheet['frame_count'] for sheet in result['sheets']] == sizes
    assert [frame['t_s'] for sheet in result['sheets'] for frame in sheet['frames']] == [frame['t_s'] for frame in frames]
    for sheet in result['sheets']:
        assert '4×4 拼图' in sheet['prompt']
        assert '连续多帧拼接' in sheet['prompt']
        assert '从左到右、从上到下' in sheet['prompt']
        assert f"{sheet['start_s']:.2f}s–{sheet['end_s']:.2f}s" in sheet['prompt']
        assert '末帧时刻不是片段终点' in sheet['prompt']
        assert 'EMPTY' in sheet['prompt']
        if sheet['frame_count'] < 16:
            with Image.open(sheet['path']) as image:
                # The last unused cell has no duplicated video pixels.
                assert image.getpixel((3 * 160 + 80, 3 * 100 + 66)) == (24, 24, 24)
                strip = image.crop((3 * 160 + 1, 3 * 100 + 1, 4 * 160 - 1, 3 * 100 + 31))
                assert len(strip.getcolors(maxcolors=10000)) > 1


def test_relative_frame_paths_are_relative_to_the_json_not_cwd(tmp_path: Path):
    frames_json, frames = make_frames(tmp_path, 1)
    frames[0]['path'] = 'frames/frame_000.png'
    frames_json.write_text(json.dumps({'frames': frames}), encoding='utf-8')
    unrelated = tmp_path / 'unrelated'
    unrelated.mkdir()

    proc, result = run_cli(frames_json, tmp_path / 'sheets', cwd=unrelated)

    assert proc.returncode == 0, proc.stderr
    assert result['sheets'][0]['frames'][0]['path'] == str(tmp_path / 'frames/frame_000.png')


def test_bad_timestamps_and_payloads_fail_before_writing_sheets(tmp_path: Path):
    frames_json, frames = make_frames(tmp_path, 1)
    for bad_time in (None, True, -1, '90', float('nan'), float('inf')):
        frames[0]['t_s'] = bad_time
        frames_json.write_text(json.dumps({'frames': frames}), encoding='utf-8')
        proc, result = run_cli(frames_json, tmp_path / 'sheets')
        assert proc.returncode == 1 and 't_s' in result['error']
        assert not (tmp_path / 'sheets').exists()

    bad_path = tmp_path / 'bad_frames.json'
    for payload in ([], {}, {'frames': []}, {'frames': [None]}, {'success': False, 'frames': [{}]}):
        bad_path.write_text(json.dumps(payload), encoding='utf-8')
        proc, result = run_cli(bad_path, tmp_path / 'sheets')
        assert proc.returncode == 1 and result['success'] is False
        assert 'Traceback' not in proc.stderr
        assert not (tmp_path / 'sheets').exists()


def test_invalid_cell_width_is_an_argument_error(tmp_path: Path):
    for width in ('0', '-1'):
        proc, result = run_cli(tmp_path / 'missing.json', tmp_path / 'sheets', '--cell-width', width)
        assert proc.returncode == 2 and 'cell-width' in result['error']


@pytest.mark.parametrize('failure', ['missing', 'corrupt', 'duplicate_time'])
def test_invalid_source_frames_are_not_silently_dropped(tmp_path: Path, failure):
    frames_json, frames = make_frames(tmp_path, 2)
    if failure == 'missing':
        Path(frames[-1]['path']).unlink()
    elif failure == 'corrupt':
        Path(frames[-1]['path']).write_bytes(b'not an image')
    else:
        frames[-1]['t_s'] = frames[0]['t_s']
    frames_json.write_text(json.dumps({'frames': frames}), encoding='utf-8')

    proc, result = run_cli(frames_json, tmp_path / 'sheets')

    assert proc.returncode == 1
    assert result['success'] is False
    assert not (tmp_path / 'sheets').exists()


def test_generation_does_not_overwrite_a_legacy_input_sheet(tmp_path: Path):
    path = tmp_path / 'sheet_001.png'
    Image.new('RGB', (120, 68), 'red').save(path)
    before = path.read_bytes()
    frames_json = tmp_path / 'frames.json'
    frames_json.write_text(json.dumps({'frames': [{'path': str(path), 't_s': 1}]}), encoding='utf-8')

    proc, result = run_cli(frames_json, tmp_path)

    assert proc.returncode == 0, proc.stderr
    assert Path(result['sheets'][0]['path']).parent.name.startswith('generation-')
    assert Path(result['sheets'][0]['path']) != path
    assert path.read_bytes() == before


def test_manifest_cannot_overwrite_the_input_json(tmp_path: Path):
    frames_json, _ = make_frames(tmp_path, 1)
    manifest = tmp_path / 'manifest.json'
    frames_json.rename(manifest)
    before = manifest.read_bytes()

    proc, result = run_cli(manifest, tmp_path)

    assert proc.returncode == 1
    assert 'overwrite' in result['error']
    assert manifest.read_bytes() == before
    assert not (tmp_path / 'sheet_001.png').exists()


def test_rerun_manifest_only_lists_the_current_sheets(tmp_path: Path):
    frames_json, frames = make_frames(tmp_path, 17)
    output = tmp_path / 'sheets'
    proc, previous = run_cli(frames_json, output)
    assert proc.returncode == 0
    old_images = {Path(sheet['path']): Path(sheet['path']).read_bytes() for sheet in previous['sheets']}
    frames_json.write_text(json.dumps({'frames': frames[:1]}), encoding='utf-8')

    proc, result = run_cli(frames_json, output)

    assert proc.returncode == 0, proc.stderr
    assert result['sheet_count'] == 1
    assert json.loads((output / 'manifest.json').read_text(encoding='utf-8')) == result
    current = Path(result['sheets'][0]['path'])
    assert current.name == 'sheet_001.png'
    assert current.parent.parent == output
    assert current.parent.name.startswith('generation-')
    assert current not in old_images
    assert all(path.read_bytes() == contents for path, contents in old_images.items())


def test_truncated_jpeg_on_later_sheet_keeps_previous_generation_intact(tmp_path: Path):
    frames_json, frames = make_frames(tmp_path, 17)
    jpeg = tmp_path / 'last.jpg'
    Image.new('RGB', (640, 360), 'red').save(jpeg, quality=90)
    frames[-1]['path'] = str(jpeg)
    frames_json.write_text(json.dumps({'success': True, 'frames': frames}), encoding='utf-8')
    output = tmp_path / 'sheets'
    proc, previous = run_cli(frames_json, output)
    assert proc.returncode == 0, proc.stderr
    before_manifest = (output / 'manifest.json').read_bytes()
    before_images = {Path(sheet['path']): Path(sheet['path']).read_bytes() for sheet in previous['sheets']}
    data = jpeg.read_bytes()
    jpeg.write_bytes(data[:len(data) // 2])
    with Image.open(jpeg) as image:
        image.verify()  # Reproduce the old bug: this check accepts the truncated JPEG.
    for frame in frames:
        frame['t_s'] += 100
    frames_json.write_text(json.dumps({'success': True, 'frames': frames}), encoding='utf-8')

    proc, result = run_cli(frames_json, output)

    assert proc.returncode == 1
    assert 'truncated' in result['error'].lower()
    assert (output / 'manifest.json').read_bytes() == before_manifest
    assert all(path.read_bytes() == contents for path, contents in before_images.items())


@pytest.mark.parametrize('failure', ['render', 'manifest_write', 'generation_publish', 'manifest_publish'])
def test_mid_generation_or_publication_failure_keeps_previous_manifest_and_images(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys, failure: str,
):
    frames_json, frames = make_frames(tmp_path, 17)
    output = tmp_path / 'sheets'
    proc, previous = run_cli(frames_json, output)
    assert proc.returncode == 0, proc.stderr
    before_manifest = (output / 'manifest.json').read_bytes()
    before_images = {Path(sheet['path']): Path(sheet['path']).read_bytes() for sheet in previous['sheets']}
    for frame in frames:
        frame['t_s'] += 100
    frames_json.write_text(json.dumps({'success': True, 'frames': frames}), encoding='utf-8')
    spec = importlib.util.spec_from_file_location('stitch_frames_review', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(sys, 'argv', [str(SCRIPT), '--frames-json', str(frames_json), '--output-dir', str(output)])

    if failure == 'render':
        original = module.write_sheet
        calls = []

        def fail_on_second_sheet(frames, path, cell_width):
            calls.append(path)
            if len(calls) == 2:
                path.write_bytes(b'partial PNG')
                raise OSError('injected render failure')
            original(frames, path, cell_width)

        monkeypatch.setattr(module, 'write_sheet', fail_on_second_sheet)
    elif failure == 'manifest_write':
        original = Path.write_text

        def fail_manifest_write(path, *args, **kwargs):
            if path.name == 'manifest.json' and path.parent.name.startswith('.stitch-'):
                raise OSError('injected manifest write failure')
            return original(path, *args, **kwargs)

        monkeypatch.setattr(Path, 'write_text', fail_manifest_write)
    else:
        original = module.os.replace

        def fail_publish(source, destination):
            if (failure == 'generation_publish' and Path(source).is_dir()) or (
                failure == 'manifest_publish' and Path(destination) == output / 'manifest.json'
            ):
                raise OSError('injected publication failure')
            return original(source, destination)

        monkeypatch.setattr(module.os, 'replace', fail_publish)

    exit_code = module.cli.run(module.main, module.TOOL_NAME)
    result = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert result['success'] is False
    assert 'injected' in result['error']
    assert (output / 'manifest.json').read_bytes() == before_manifest
    assert all(path.read_bytes() == contents for path, contents in before_images.items())
    assert not list(output.glob('.stitch-*'))


def test_concurrent_runs_publish_consistent_manifests_and_keep_both_generations(tmp_path: Path):
    first_json, frames = make_frames(tmp_path, 17)
    second_json = tmp_path / 'second.json'
    second_json.write_text(json.dumps({'frames': [{**frame, 't_s': frame['t_s'] + 100} for frame in frames]}), encoding='utf-8')
    output = tmp_path / 'sheets'
    processes = [
        subprocess.Popen(
            [sys.executable, str(SCRIPT), '--frames-json', str(path), '--output-dir', str(output)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        for path in (first_json, second_json)
    ]
    results = []
    try:
        for process in processes:
            stdout, stderr = process.communicate(timeout=30)
            assert process.returncode == 0, stderr
            results.append(json.loads(stdout))
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=30)

    assert json.loads((output / 'manifest.json').read_text(encoding='utf-8')) in results
    paths = [sheet['path'] for result in results for sheet in result['sheets']]
    assert len(set(paths)) == 4
    for path in paths:
        with Image.open(path) as image:
            image.load()
    assert not list(output.glob('.stitch-*'))


@pytest.mark.usefixtures('require_ffmpeg')
def test_extract_stitch_and_analyze_workflow_passes_one_grid_and_time_prompt(tmp_path: Path):
    video = tmp_path / 'input.mp4'
    subprocess.run([
        'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'lavfi',
        '-i', 'testsrc=duration=4:size=320x180:rate=25', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(video),
    ], check=True, capture_output=True, timeout=30)
    extracted = subprocess.run([
        sys.executable, str(EXTRACT), str(video), str(tmp_path / 'detail'),
        '--start-time', '00:00:01', '--end-time', '00:00:04', '--max-frames', '3', '--max-width', '1280',
    ], check=True, capture_output=True, text=True, timeout=30)
    frames_json = tmp_path / 'detail' / 'frames.json'
    frames_json.write_text(extracted.stdout, encoding='utf-8')
    proc, result = run_cli(frames_json, tmp_path / 'detail' / 'sheets')
    assert proc.returncode == 0, proc.stderr
    sheet = result['sheets'][0]
    context = tmp_path / 'topic-context.txt'
    context.write_text('演示界面的状态变化。', encoding='utf-8')
    env = {name: value for name, value in os.environ.items() if name not in ('VLM_API_KEY', 'VLM_BASE_URL', 'VLM_MODEL')}
    analyzed = subprocess.run([
        sys.executable, str(VISION), '--images', sheet['path'], '--prompt', sheet['prompt'],
        '--context-file', str(context), '--detail', 'high',
    ], check=True, capture_output=True, text=True, env=env, timeout=30)
    handoff = json.loads(analyzed.stdout)

    assert handoff['mode'] == 'delegate_to_agent'
    assert handoff['image_count'] == 1
    assert handoff['images']['local'] == [sheet['path']]
    assert handoff['prompt'] == sheet['prompt']
    assert '1.00s–3.00s' in handoff['prompt']
    assert handoff['context'] == '演示界面的状态变化。'
