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


def test_upsert_lifecycle_preserves_papers_downloads_and_refreshes_metadata(tmp_path: Path):
    paper = {
        'slug': 'main-paper', 'success': True, 'source_type': 'paper_pdf',
        'paper_metadata': {'full_markdown_path': 'main-paper/mineru/full.md'},
        'images': [], 'videos': [],
    }
    first = web_entry(tmp_path, 'first')
    first['images'] = [{
        'id': 'img_001',
        'local_path': str(tmp_path / 'first' / 'images' / 'img_001.png'),
    }]

    # 1. Idempotent upsert writes relative manifest, per-slug metadata mirror, and pending_downloads.
    harvest_manifest.upsert_entries(tmp_path, [paper, first])
    harvest_manifest.upsert_entries(tmp_path, [paper, first])
    manifest = read_json(tmp_path / 'manifest.json')
    assert manifest['version'] == 2
    assert len(manifest['entries']) == 2
    first_saved = next(e for e in manifest['entries'] if e['slug'] == 'first')
    assert first_saved['images'][0]['local_path'] == 'first/images/img_001.png'
    assert manifest['pending_downloads'] == [{
        'url': URL,
        'platform': 'youtube',
        'suggested_output_dir': 'first/videos',
        'source_slug': 'first',
    }]
    assert read_json(tmp_path / 'first' / 'metadata.json') == first_saved
    assert manifest['harvest_batches'] == []
    assert manifest['updated_at']

    # 2. Apply download, refresh same slug metadata, and add a second batch without erasing papers/downloads.
    harvest_manifest.record_harvest_batch(tmp_path, {
        'urls': [first['url']], 'succeeded': 1, 'failed': 0, 'rejected': [],
    })
    clip_path = tmp_path / 'first' / 'videos' / 'clip.mp4'
    harvest_manifest.apply_download(tmp_path, URL, {
        'files': [str(clip_path)],
        'videos': [{'path': str(clip_path), 'width': 640, 'height': 360, 'duration_seconds': 1.0}],
    })
    refreshed = web_entry(tmp_path, 'first')
    refreshed['title'] = 'refreshed harvest title'
    refreshed['videos'][0]['width'] = 1920
    second = web_entry(tmp_path, 'second', 'https://youtu.be/second123')
    harvest_manifest.upsert_entries(tmp_path, [refreshed, second])
    harvest_manifest.record_harvest_batch(tmp_path, {
        'urls': [second['url']], 'succeeded': 1, 'failed': 0, 'rejected': [],
    })

    loaded = harvest_manifest.load(tmp_path)
    assert {entry['slug'] for entry in loaded['entries']} == {'main-paper', 'first', 'second'}
    assert len(loaded['harvest_batches']) == 2
    first_after = next(e for e in loaded['entries'] if e['slug'] == 'first')
    assert first_after['title'] == 'refreshed harvest title'
    assert first_after['videos'][0]['download_required'] is False
    assert first_after['videos'][0]['downloaded'] is True
    assert first_after['videos'][0]['local_path'] == 'first/videos/clip.mp4'
    assert (first_after['videos'][0]['width'], first_after['videos'][0]['height']) == (1920, 360)
    assert [item['url'] for item in loaded['pending_downloads']] == ['https://youtu.be/second123']


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


def test_v2_manifest_initializes_fresh_ignores_legacy_paper_file_and_rejects_unversioned(tmp_path: Path):
    fresh_dir = tmp_path / 'fresh'
    fresh_dir.mkdir()
    fresh = harvest_manifest.load(fresh_dir)
    assert fresh['version'] == 2 and fresh['entries'] == []
    assert not (fresh_dir / 'manifest.json').exists()

    # manifest_papers.json is never merged into a new v2 manifest.
    (fresh_dir / 'manifest_papers.json').write_text(
        json.dumps({'entries': [{'slug': 'main-paper', 'title': 'stale legacy title'}]}),
        encoding='utf-8',
    )
    harvest_manifest.upsert_entries(fresh_dir, [web_entry(fresh_dir, 'one')])
    assert [entry['slug'] for entry in harvest_manifest.load(fresh_dir)['entries']] == ['one']

    # Existing manifest without version 2 is rejected without mutating or merging legacy files.
    legacy_dir = tmp_path / 'legacy_ws'
    legacy_dir.mkdir()
    legacy_video = str(legacy_dir / 'legacy' / 'videos' / 'old.mp4')
    (legacy_dir / 'manifest.json').write_text(json.dumps({
        'entries': [{
            'slug': 'legacy', 'success': True, 'images': [],
            'videos': [{'url': URL, 'local_path': legacy_video, 'download_required': False}],
        }],
        'pending_downloads': [],
    }), encoding='utf-8')
    (legacy_dir / 'manifest_papers.json').write_text(json.dumps({
        'entries': [{'slug': 'main-paper', 'success': True, 'source_type': 'paper_pdf', 'images': [], 'videos': []}],
    }), encoding='utf-8')
    with pytest.raises(ValueError, match='not a version 2 manifest'):
        harvest_manifest.load(legacy_dir)
    with pytest.raises(ValueError, match='not a version 2 manifest'):
        harvest_manifest.upsert_entries(legacy_dir, [web_entry(legacy_dir, 'incoming')])
    assert 'main-paper' not in (legacy_dir / 'manifest.json').read_text(encoding='utf-8')


def test_persisted_paths_normalize_on_write_and_reject_escapes(tmp_path: Path):
    assert harvest_manifest.resolve(tmp_path, 'legacy/videos/old.mp4') == tmp_path / 'legacy/videos/old.mp4'
    for bad in (str(tmp_path / 'legacy' / 'videos' / 'old.mp4'), '~/videos/old.mp4', '../escape/old.mp4'):
        with pytest.raises(ValueError, match='stored path is unusable'):
            harvest_manifest.resolve(tmp_path, bad)
    assert harvest_manifest.stored_path_problem('ok/x.png') is None
    assert 'not relative' in harvest_manifest.stored_path_problem('/abs/x.png')
    assert 'leaves' in harvest_manifest.stored_path_problem('a/../../x.png')

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

    # Persisted bad paths in an existing manifest are rejected before load or upsert mutates disk.
    manifest_path = tmp_path / 'manifest.json'
    for bad_persisted in ('/old-project/a.png', '~/a.png', '../a.png', 'C:/old/a.png'):
        manifest = read_json(manifest_path)
        manifest['entries'][0]['images'] = [{'id': 'img', 'local_path': bad_persisted}]
        manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
        before = manifest_path.read_bytes()
        with pytest.raises(ValueError, match='local_path'):
            harvest_manifest.load(tmp_path)
        with pytest.raises(ValueError, match='local_path'):
            harvest_manifest.upsert_entries(tmp_path, [{'slug': 'two', 'images': [], 'videos': []}])
        assert manifest_path.read_bytes() == before
        assert not (tmp_path / 'two').exists()


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
