"""Per-stage agent/model requests must not be dropped or silently replaced."""
from __future__ import annotations

import pytest

from delegation_config import STEPS, resolve_delegation, resolve_models, validate_delegation


def test_resolve_delegation_scopes_stage_overrides_without_inventing_fields():
    for step in STEPS:
        assert resolve_delegation({'coding_agent': 'pi-coding-agent'}, step) == ('pi-coding-agent', None)
        assert resolve_delegation({'coding_agent': 'claude-code'}, step) == ('claude-code', None)

    inputs = {
        'coding_agent': 'claude-code',
        'delegation': {'catalog': {'agent': 'pi-coding-agent', 'model': 'provider/exact-model'}},
    }
    assert resolve_delegation(inputs, 'catalog') == ('pi-coding-agent', 'provider/exact-model')
    assert resolve_delegation(inputs, 'script') == ('claude-code', None)
    assert resolve_delegation(inputs, 'composition') == ('claude-code', None)

    for config, expected in (
        ({}, ('pi-coding-agent', None)),
        ({'model': 'provider/model'}, ('pi-coding-agent', 'provider/model')),
        ({'agent': 'codex'}, ('codex', None)),
    ):
        assert resolve_delegation(
            {'coding_agent': 'pi-coding-agent', 'delegation': {'catalog': config}}, 'catalog'
        ) == expected

    with pytest.raises(ValueError, match='Unknown delegation step'):
        resolve_delegation({'coding_agent': 'pi-coding-agent'}, 'harvest')


def test_validate_delegation_rejects_malformed_overrides():
    for overrides, message in (
        (None, 'delegation must be an object'),
        ([], 'delegation must be an object'),
        ({'catlog': {}}, 'unknown step'),
        ({'catalog': 'pi-coding-agent'}, 'catalog must be an object'),
        ({'catalog': {'modle': 'provider/model'}}, 'unknown field'),
        ({'catalog': {'agent': ''}}, 'catalog.agent must be a non-empty string'),
        ({'catalog': {'model': '  '}}, 'catalog.model must be a non-empty string'),
        ({'catalog': {'model': None}}, 'catalog.model must be a non-empty string'),
        ({'catalog': {'model': 123}}, 'catalog.model must be a non-empty string'),
    ):
        with pytest.raises(ValueError, match=message):
            validate_delegation({'delegation': overrides})


def test_resolve_models_pairs_requests_with_resolutions_and_blocks_unresolved():
    assert resolve_models(None, None) == (None, None)
    assert resolve_models('provider/exact-model', 'provider/exact-model') == (
        'provider/exact-model', 'provider/exact-model',
    )
    assert resolve_models('模糊的请求名', 'provider/closest-real-id') == (
        'provider/closest-real-id', '模糊的请求名',
    )

    for unresolved in (None, '', '   '):
        with pytest.raises(ValueError, match='requested but not resolved'):
            resolve_models('模糊的请求名', unresolved)

    with pytest.raises(ValueError, match='no model was requested'):
        resolve_models(None, 'provider/exact-model')
