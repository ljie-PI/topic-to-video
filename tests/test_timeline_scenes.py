"""Tests for the shared timeline scene normalization contract."""
from __future__ import annotations

from timeline_scenes import normalize_scenes, scene_ranges


def test_normalize_scenes_emits_only_canonical_fields():
    scenes, warnings = normalize_scenes(
        {
            'scenes': [
                {'scene_id': 'later', 'begin_s': 2, 'end_s': 4},
                {'scene_id': 'first', 'begin_s': 0, 'end_s': 2},
            ]
        }
    )

    assert warnings == []
    assert scenes == [
        {'scene_id': 'first', 'begin_s': 0.0, 'end_s': 2.0},
        {'scene_id': 'later', 'begin_s': 2.0, 'end_s': 4.0},
    ]
    assert scene_ranges(scenes) == [('first', 0.0, 2.0), ('later', 2.0, 4.0)]


def test_normalize_scenes_does_not_read_legacy_field_aliases():
    scenes, warnings = normalize_scenes(
        {
            'scenes': [
                {'id': 'alias-id', 'begin_s': 0, 'end_s': 1},
                {'scene_id': 'alias-start', 'start_s': 1, 'end_s': 2},
                {'scene_id': 'canonical', 'begin_s': 2, 'end_s': 3},
            ]
        }
    )

    assert scenes == [
        {'scene_id': 'scene_1', 'begin_s': 0.0, 'end_s': 1.0},
        {'scene_id': 'canonical', 'begin_s': 2.0, 'end_s': 3.0},
    ]
    assert len(warnings) == 1
    assert 'alias-start' in warnings[0] and 'skipped' in warnings[0]
