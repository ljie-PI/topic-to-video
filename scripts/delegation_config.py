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
