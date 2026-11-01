"""Direct-import tests for the single harvest manifest persistence module."""
from __future__ import annotations

import json
from pathlib import Path

import harvest_manifest
import pytest


URL = 'https://www.youtube.com/watch?v=shared123'


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def web_entry(harvest_dir: Path, slug: str, url: str = URL) -> dict:
    return {
        'slug': slug,
        'url': f'https://example.com/{slug}',
        'success': True,
        'images': [],
        'videos': [{
            'url': url,
            'platform': 'youtube',
            'download_required': True,
            'suggested_output_dir': str(harvest_dir / slug / 'videos'),
        }],
        'scroll_recording': None,
    }


def test_upsert_is_idempotent_and_writes_relative_manifest_and_mirror(tmp_path: Path):
    entry = web_entry(tmp_path, 'one')
    entry['images'] = [{
        'id': 'img_001',
        'local_path': str(tmp_path / 'one' / 'images' / 'img_001.png'),
    }]

    harvest_manifest.upsert_entries(tmp_path, [entry])
    harvest_manifest.upsert_entries(tmp_path, [entry])

    manifest = read_json(tmp_path / 'manifest.json')
    assert manifest['version'] == 2
    assert len(manifest['entries']) == 1
    assert manifest['entries'][0]['images'][0]['local_path'] == 'one/images/img_001.png'
    assert manifest['pending_downloads'] == [{
        'url': URL,
        'platform': 'youtube',
        'suggested_output_dir': 'one/videos',
        'source_slug': 'one',
    }]
    assert read_json(tmp_path / 'one' / 'metadata.json') == manifest['entries'][0]
    assert manifest['harvest_batches'] == []
    assert manifest['updated_at']


def test_later_batches_preserve_papers_and_applied_downloads(tmp_path: Path):
    paper = {
        'slug': 'main-paper', 'success': True, 'source_type': 'paper_pdf',
        'paper_metadata': {'full_markdown_path': 'main-paper/mineru/full.md'},
        'images': [], 'videos': [],
    }
    first = web_entry(tmp_path, 'first')
    harvest_manifest.upsert_entries(tmp_path, [paper, first])
    harvest_manifest.record_harvest_batch(tmp_path, {
        'urls': [first['url']], 'succeeded': 1, 'failed': 0, 'rejected': [],
    })
    harvest_manifest.apply_download(tmp_path, URL, {
        'files': [str(tmp_path / 'first' / 'videos' / 'clip.mp4')],
        'videos': [{
            'path': str(tmp_path / 'first' / 'videos' / 'clip.mp4'),
            'width': 640, 'height': 360, 'duration_seconds': 1.0,
        }],
    })

    second = web_entry(tmp_path, 'second', 'https://youtu.be/second123')
    harvest_manifest.upsert_entries(tmp_path, [second])
    harvest_manifest.record_harvest_batch(tmp_path, {
        'urls': [second['url']], 'succeeded': 1, 'failed': 0, 'rejected': [],
    })

    manifest = harvest_manifest.load(tmp_path)
    assert {entry['slug'] for entry in manifest['entries']} == {'main-paper', 'first', 'second'}
    assert len(manifest['harvest_batches']) == 2
    first_video = next(e for e in manifest['entries'] if e['slug'] == 'first')['videos'][0]
    assert first_video['download_required'] is False
    assert first_video['local_path'] == 'first/videos/clip.mp4'
    assert [item['url'] for item in manifest['pending_downloads']] == ['https://youtu.be/second123']


def test_same_slug_upsert_refreshes_metadata_and_allows_explicit_video_updates(tmp_path: Path):
    entry = web_entry(tmp_path, 'one')
    harvest_manifest.upsert_entries(tmp_path, [entry])
    video_path = tmp_path / 'one' / 'videos' / 'old.mp4'
    harvest_manifest.apply_download(tmp_path, URL, {
        'files': [str(video_path)],
        'videos': [{'path': str(video_path), 'width': 640, 'height': 360, 'duration_seconds': 1.0}],
    })
    refreshed = web_entry(tmp_path, 'one')
    refreshed['title'] = 'refreshed harvest title'
    refreshed['videos'][0]['width'] = 1920

    harvest_manifest.upsert_entries(tmp_path, [refreshed])

    saved = harvest_manifest.load(tmp_path)['entries'][0]
    assert saved['title'] == 'refreshed harvest title'
    assert saved['videos'][0]['download_required'] is False
    assert saved['videos'][0]['downloaded'] is True
    assert saved['videos'][0]['local_path'] == 'one/videos/old.mp4'
    assert saved['videos'][0]['height'] == 360
    assert saved['videos'][0]['width'] == 1920


def test_apply_download_fans_out_to_all_references_and_mirrors(tmp_path: Path):
    harvest_manifest.upsert_entries(tmp_path, [web_entry(tmp_path, 'one'), web_entry(tmp_path, 'two')])
    before = harvest_manifest.load(tmp_path)
    assert before['pending_downloads'][0]['also_referenced_by'] == ['two']
    video = tmp_path / 'one' / 'videos' / 'shared123.mp4'
    subtitle = tmp_path / 'one' / 'videos' / 'shared123.en.srt'
    ignored = tmp_path / 'one' / 'videos' / 'shared123.ass'

    harvest_manifest.apply_download(tmp_path, URL, {
        'files': [str(video), str(subtitle), str(ignored)],
        'videos': [{'path': str(video), 'width': 1280, 'height': 720, 'duration_seconds': 2.5}],
    })

    manifest = read_json(tmp_path / 'manifest.json')
    assert manifest['pending_downloads'] == []
    for slug in ('one', 'two'):
        entry = next(e for e in manifest['entries'] if e['slug'] == slug)
        downloaded = entry['videos'][0]
        assert downloaded == {
            **web_entry(tmp_path, slug)['videos'][0],
            'suggested_output_dir': f'{slug}/videos',
            'download_required': False,
            'downloaded': True,
            'local_path': 'one/videos/shared123.mp4',
            'subtitle_path': 'one/videos/shared123.en.srt',
            'id': 'shared123',
            'width': 1280,
            'height': 720,
            'duration_seconds': 2.5,
        }
        assert read_json(tmp_path / slug / 'metadata.json') == entry


def test_manifest_without_current_version_is_rejected(tmp_path: Path):
    """manifest 已存在时必须自报当前版本：不合并旧文件、不就地升级。"""
    legacy_video = str(tmp_path / 'legacy' / 'videos' / 'old.mp4')
    (tmp_path / 'manifest.json').write_text(json.dumps({
        'entries': [{
            'slug': 'legacy', 'success': True, 'images': [],
            'videos': [{'url': URL, 'local_path': legacy_video, 'download_required': False}],
        }],
        'pending_downloads': [],
    }), encoding='utf-8')
    (tmp_path / 'manifest_papers.json').write_text(json.dumps({
        'entries': [{'slug': 'main-paper', 'success': True, 'source_type': 'paper_pdf', 'images': [], 'videos': []}],
    }), encoding='utf-8')

    with pytest.raises(ValueError, match='not a version 2 manifest'):
        harvest_manifest.load(tmp_path)
    with pytest.raises(ValueError, match='not a version 2 manifest'):
        harvest_manifest.upsert_entries(tmp_path, [web_entry(tmp_path, 'incoming')])

    # 旧文件与旧 manifest_papers.json 都没被动过，也没有被合并进去。
    assert 'main-paper' not in (tmp_path / 'manifest.json').read_text(encoding='utf-8')


def test_missing_manifest_starts_a_new_v2_manifest(tmp_path: Path):
    """没有 manifest 是正常起点：建立 v2，而不是去读旧文件。"""
    manifest = harvest_manifest.load(tmp_path)
    assert manifest['version'] == 2
    assert manifest['entries'] == []
    assert not (tmp_path / 'manifest.json').exists()


def test_persisted_paths_must_be_relative_inside_the_harvest_dir(tmp_path: Path):
    """持久化路径只能是基准目录内的相对路径：读到的绝对 / ~ / .. 路径一律拒绝。"""
    assert harvest_manifest.resolve(tmp_path, 'legacy/videos/old.mp4') == tmp_path / 'legacy/videos/old.mp4'
    for bad in (str(tmp_path / 'legacy' / 'videos' / 'old.mp4'), '~/videos/old.mp4', '../escape/old.mp4'):
        with pytest.raises(ValueError, match='stored path is unusable'):
            harvest_manifest.resolve(tmp_path, bad)
    assert harvest_manifest.stored_path_problem('ok/x.png') is None
    assert 'not relative' in harvest_manifest.stored_path_problem('/abs/x.png')
    assert 'leaves' in harvest_manifest.stored_path_problem('a/../../x.png')


def test_producer_absolute_paths_are_normalized_on_write(tmp_path: Path):
    """写入时把生产者内部的绝对路径规范成相对路径（同时避免.. 跨出目录）。"""
    entry = web_entry(tmp_path, 'one')
    entry['paper_metadata'] = {'full_markdown_path': str(tmp_path / 'main-paper' / 'mineru' / 'full.md')}
    harvest_manifest.upsert_entries(tmp_path, [entry])

    saved = read_json(tmp_path / 'manifest.json')
    paper = saved['entries'][0]
    assert paper['videos'][0]['suggested_output_dir'] == 'one/videos'
    assert paper['paper_metadata']['full_markdown_path'] == 'main-paper/mineru/full.md'
    with pytest.raises(ValueError, match='leaves the harvest directory'):
        harvest_manifest.save(tmp_path, {'version': 2, 'entries': [{
            'slug': 'away', 'images': [{'id': 'img_001', 'local_path': '../outside/img.png'}],
        }]})


def test_paper_manifest_file_is_never_merged(tmp_path: Path):
    """manifest_papers.json 不是当前格式的一部分：即使存在也不参与读取。"""
    (tmp_path / 'manifest_papers.json').write_text(
        json.dumps({'entries': [{'slug': 'main-paper', 'title': 'stale legacy title'}]}),
        encoding='utf-8',
    )
    harvest_manifest.upsert_entries(tmp_path, [web_entry(tmp_path, 'one')])

    manifest = read_json(tmp_path / 'manifest.json')
    assert [entry['slug'] for entry in manifest['entries']] == ['one']
    assert harvest_manifest.load(tmp_path)['entries'][0]['slug'] == 'one'


def test_invalid_slug_leaves_original_manifest_and_mirrors_unchanged(tmp_path: Path):
    harvest_manifest.upsert_entries(tmp_path, [web_entry(tmp_path, 'original')])
    manifest_path = tmp_path / 'manifest.json'
    mirror_path = tmp_path / 'original' / 'metadata.json'
    original_manifest = manifest_path.read_bytes()
    original_mirror = mirror_path.read_bytes()

    with pytest.raises(ValueError, match='invalid entry slug'):
        harvest_manifest.upsert_entries(tmp_path, [web_entry(tmp_path, '../escape')])

    assert manifest_path.read_bytes() == original_manifest
    assert mirror_path.read_bytes() == original_mirror


def test_mirror_rename_failure_rolls_back_manifest_and_all_mirrors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    original_entries = [web_entry(tmp_path, 'one'), web_entry(tmp_path, 'two')]
    harvest_manifest.upsert_entries(tmp_path, original_entries)
    paths = [
        tmp_path / 'manifest.json',
        tmp_path / 'one' / 'metadata.json',
        tmp_path / 'two' / 'metadata.json',
    ]
    original_bytes = {path: path.read_bytes() for path in paths}
    real_replace = harvest_manifest.os.replace
    mirror_renames = 0
    failed = False

    def fail_second_mirror_rename(source, destination):
        nonlocal mirror_renames, failed
        if Path(destination).name == 'metadata.json' and not failed:
            mirror_renames += 1
            if mirror_renames == 2:
                failed = True
                raise OSError('injected mirror rename failure')
        return real_replace(source, destination)

    monkeypatch.setattr(harvest_manifest.os, 'replace', fail_second_mirror_rename)
    updated_entries = [{**entry, 'title': 'updated'} for entry in original_entries]
    with pytest.raises(OSError, match='injected mirror rename failure'):
        harvest_manifest.upsert_entries(tmp_path, updated_entries)

    assert mirror_renames == 2
    for path in paths:
        assert path.read_bytes() == original_bytes[path]


def test_slug_helpers_and_extensions_have_one_owner():
    assert harvest_manifest.slug_for_url('https://Example.com/A Path') == 'example-com-a-path-3b79fb'
    assert harvest_manifest.slug_for_pdf('https://arxiv.org/pdf/My Paper.123.pdf', None) == 'my-paper-123'
    assert harvest_manifest.slug_for_pdf(None, '/tmp/My Paper.pdf') == 'my-paper'
    assert '.mp4' in harvest_manifest.VIDEO_EXTS
    assert harvest_manifest.SUBTITLE_EXTS == {'.srt', '.vtt'}
