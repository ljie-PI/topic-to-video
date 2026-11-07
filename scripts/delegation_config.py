"""Validate and resolve optional per-step coding agent/model requests."""
from __future__ import annotations

from typing import Any

STEPS = ('catalog', 'script', 'composition')


def validate_delegation(inputs: dict[str, Any]) -> None:
    """Reject misspelled or empty overrides rather than silently ignoring them."""
    overrides = inputs.get('delegation', {})
    if not isinstance(overrides, dict):
        raise ValueError('inputs.json field delegation must be an object')
    for step, config in overrides.items():
        if step not in STEPS:
            raise ValueError(f'inputs.json delegation has unknown step {step!r}')
        if not isinstance(config, dict):
            raise ValueError(f'inputs.json delegation.{step} must be an object')
        for name, value in config.items():
            if name not in ('agent', 'model'):
                raise ValueError(f'inputs.json delegation.{step} has unknown field {name!r}')
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f'inputs.json delegation.{step}.{name} must be a non-empty string')


def resolve_delegation(inputs: dict[str, Any], step: str) -> tuple[str, str | None]:
    """Inherit the global agent, but never infer an unspecified model."""
    validate_delegation(inputs)
    if step not in STEPS:
        raise ValueError(f'Unknown delegation step {step!r}')
    config = inputs.get('delegation', {}).get(step, {})
    return config.get('agent', inputs['coding_agent']), config.get('model')


def resolve_models(requested: str | None, resolved: str | None) -> tuple[str | None, str | None]:
    """把原始请求与解析结果配成 handoff 用的 (coding_model, requested_model)。

    requested 是用户在 inputs.json 里写的原始请求，原样保留；resolved 是主 agent
    按统一约定经目标 CLI 查询得到、要真正派发的原生标识。规则：

    - 无请求、无解析：(None, None)——使用目标 agent 自身配置，两者都是 null。
    - 有请求、有解析：(resolved, requested)——handoff / JSON / 实际派发都用真实
      标识，模糊请求不再冒充执行模型。
    - 有请求、无解析：阻塞。不生成把模糊名称当成执行模型的 handoff。
    - 无请求、有解析：参数矛盾，说明解析流程弄错了阶段或写错了输入。

    空字符串与纯空白不算解析结果，一律按未解析处理（与 requested 的非空校验
    对齐），因此有请求时它们同样落到阻塞分支。
    """
    if resolved is not None and not resolved.strip():
        resolved = None
    if requested is None:
        if resolved is not None:
            raise ValueError(
                '--resolved-model was given but no model was requested for this step'
            )
        return None, None
    if resolved is None:
        raise ValueError(
            'a model was requested but not resolved: query the target CLI first '
            'and pass --resolved-model with the real model id'
        )
    return resolved, requested
