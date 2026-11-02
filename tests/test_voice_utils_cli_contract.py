"""Model-free voice-utils import contracts.

The import check explicitly rejects mlx imports: both library modules must stay
cheap to import while keeping their model imports lazy inside the public calls.
"""
from __future__ import annotations

import builtins
import importlib
import sys

import pytest

import mlx_align
import text_align
import tts_qwen

def test_text_align_reexports_the_mlx_align_public_function():
    assert text_align.align_text is mlx_align.align_text
    assert text_align.__all__ == ['align_text']
    assert callable(tts_qwen.synthesize)


def test_mlx_library_functions_import_without_mlx(monkeypatch: pytest.MonkeyPatch):
    for module_name in ('tts_qwen', 'text_align', 'mlx_align', 'utils'):
        sys.modules.pop(module_name, None)

    real_import = builtins.__import__

    def reject_mlx_import(name, *args, **kwargs):
        if name == 'mlx' or name.startswith(('mlx.', 'mlx_audio')):
            raise AssertionError(f'top-level voice-utils import pulled in {name}')
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', reject_mlx_import)

    assert callable(importlib.import_module('tts_qwen').synthesize)
    assert callable(importlib.import_module('text_align').align_text)
