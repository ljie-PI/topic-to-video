"""The phase docs and pipeline-status's PHASES table describe the same products.

Each phase doc lists its products in the "## 输出" section; pipeline-status
validates them from PHASES. A product that PHASES checks but the doc never
names would be demanded of an agent that was never told to write it.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_pipeline_status():
    spec = importlib.util.spec_from_file_location('pipeline_status', REPO_ROOT / 'scripts' / 'pipeline-status.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # @dataclass looks its module up here
    spec.loader.exec_module(module)
    return module


PHASES = load_pipeline_status().PHASES


def output_section(doc: Path) -> str:
    """The text under the doc's '## 输出' heading, up to the next '## ' heading."""
    match = re.search(r'^## 输出\n(.*?)(?=^## |\Z)', doc.read_text(encoding='utf-8'), re.MULTILINE | re.DOTALL)
    assert match, f'{doc.relative_to(REPO_ROOT)} has no "## 输出" section'
    return match.group(1)


@pytest.mark.parametrize('phase', PHASES, ids=[phase['id'] for phase in PHASES])
def test_every_product_checked_by_pipeline_status_is_named_in_the_phase_doc_output(phase):
    section = output_section(REPO_ROOT / phase['doc'])
    missing = [relpath for relpath in phase['products'] if relpath not in section]
    assert not missing, f'{phase["doc"]} "## 输出" does not name: {missing}'


def test_phase7_offers_one_voice_clone_command_without_a_manual_asr_fallback():
    doc = (REPO_ROOT / 'references/phases/07-voice-subtitles.md').read_text(encoding='utf-8')
    section = doc.split('#### 7.1 —', 1)[1].split('#### 7.2 —', 1)[0]

    assert 'python3 scripts/voice-clone.py' in section
    assert 'python3 scripts/transcribe.py' not in section
    assert '单独补跑转录' not in section
