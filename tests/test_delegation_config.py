"""Per-stage agent/model requests must not be dropped or silently replaced."""
from __future__ import annotations

import pytest

from delegation_config import STEPS, resolve_delegation, resolve_models, validate_delegation


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


class TestResolveModels:
    """原始请求与解析结果配对：handoff / JSON / 实际派发共用一套规则。"""

    def test_no_request_gives_a_null_pair(self):
        # 未请求模型：二者都是 null，使用目标 agent 自身配置。
        assert resolve_models(None, None) == (None, None)

    @pytest.mark.parametrize('requested, resolved', [
        ('provider/exact-model', 'provider/exact-model'),
        ('模糊的请求名', 'provider/closest-real-id'),  # 近似候选：保留请求，实际值生效
    ])
    def test_a_resolved_request_pairs_the_real_id_with_the_original_request(
        self, requested: str, resolved: str
    ):
        assert resolve_models(requested, resolved) == (resolved, requested)

    def test_a_request_without_resolution_is_blocked(self):
        # 有请求但未解析：不生成把模糊名称冒充执行模型的 handoff。
        with pytest.raises(ValueError, match='requested but not resolved'):
            resolve_models('模糊的请求名', None)

    def test_a_resolution_without_a_request_is_rejected(self):
        with pytest.raises(ValueError, match='no model was requested'):
            resolve_models(None, 'provider/exact-model')
