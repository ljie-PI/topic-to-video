"""Per-stage agent/model requests must not be dropped or silently replaced."""
from __future__ import annotations

import pytest

from delegation_config import STEPS, resolve_delegation, validate_delegation


@pytest.mark.parametrize('step', STEPS)
def test_no_overrides_preserves_the_global_agent_and_infers_no_model(step):
    assert resolve_delegation({'coding_agent': 'pi-coding-agent'}, step) == ('pi-coding-agent', None)
    assert resolve_delegation({'coding_agent': 'claude-code'}, step) == ('claude-code', None)


def test_catalog_override_is_scoped_and_preserves_the_exact_model():
    inputs = {
        'coding_agent': 'claude-code',
        'delegation': {'catalog': {'agent': 'pi-coding-agent', 'model': 'provider/exact-model'}},
    }
    assert resolve_delegation(inputs, 'catalog') == ('pi-coding-agent', 'provider/exact-model')
    assert resolve_delegation(inputs, 'script') == ('claude-code', None)
    assert resolve_delegation(inputs, 'composition') == ('claude-code', None)


@pytest.mark.parametrize('config, expected', [
    ({}, ('pi-coding-agent', None)),
    ({'model': 'provider/model'}, ('pi-coding-agent', 'provider/model')),
    ({'agent': 'codex'}, ('codex', None)),
])
def test_partial_overrides_do_not_invent_unspecified_fields(config, expected):
    assert resolve_delegation({'coding_agent': 'pi-coding-agent', 'delegation': {'catalog': config}}, 'catalog') == expected


@pytest.mark.parametrize('overrides, message', [
    (None, 'delegation must be an object'),
    ([], 'delegation must be an object'),
    ({'catlog': {}}, 'unknown step'),
    ({'catalog': 'pi-coding-agent'}, 'catalog must be an object'),
    ({'catalog': {'modle': 'provider/model'}}, 'unknown field'),
    ({'catalog': {'agent': ''}}, 'catalog.agent must be a non-empty string'),
    ({'catalog': {'model': '  '}}, 'catalog.model must be a non-empty string'),
    ({'catalog': {'model': None}}, 'catalog.model must be a non-empty string'),
    ({'catalog': {'model': 123}}, 'catalog.model must be a non-empty string'),
])
def test_malformed_overrides_are_rejected(overrides, message):
    with pytest.raises(ValueError, match=message):
        validate_delegation({'delegation': overrides})


def test_unknown_step_is_rejected():
    with pytest.raises(ValueError, match='Unknown delegation step'):
        resolve_delegation({'coding_agent': 'pi-coding-agent'}, 'harvest')
