"""Direct-import tests for the pure selected-clip path library."""
from __future__ import annotations

import pytest

import clip_paths


def test_clip_relpath_is_flat_and_formats_window_to_two_decimals():
    assert clip_paths.clip_relpath('vid_001', 0.5, 2.0) == 'clips/vid_001_0.50-2.00.mp4'


@pytest.mark.parametrize('video_id', ['', '../evil', '.hidden', 'a/b', 'a\\b'])
def test_clip_relpath_rejects_an_unsafe_video_id(video_id: str):
    with pytest.raises(ValueError):
        clip_paths.clip_relpath(video_id, 0.5, 2.0)
