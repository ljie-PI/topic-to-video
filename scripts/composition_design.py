"""composition/design.json 的公共读取与校验。

这份产物固定记录 Phase 8 根据内容确定的全片外观基线。默认必须从库内注册 preset
中选择，且与所选主题文档一致；仅当用户在 inputs.json 的 composition_requests
中提出视觉风格要求时才允许 custom，custom 也必须包含完整共享 token 与
reading / ui 字号下限。字体维护清单不属于这个产物，实际 CSS 与 WOFF2 仍在
composition/assets/fonts/。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import video_contract

COMPOSITION_DESIGN_VERSION = 1
COMPOSITION_DESIGN_PATH = 'composition/design.json'
ROOT_KEYS = {'version', 'source', 'preset', 'tokens', 'min_font_px'}
FONT_FLOOR_KEYS = {'reading', 'ui'}


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def composition_design_problem(
    data: Any,
    *,
    skill_root: Path,
    inputs: dict[str, Any] | None = None,
) -> str | None:
    """返回 design 产物不符合公共契约的原因；合格时返回 None。"""
    if not isinstance(data, dict):
        return 'JSON root is not an object'
    if set(data) != ROOT_KEYS:
        return f'root must contain exactly {", ".join(sorted(ROOT_KEYS))}'
    version = data['version']
    if not isinstance(version, int) or isinstance(version, bool) or version != COMPOSITION_DESIGN_VERSION:
        return f'version must be integer {COMPOSITION_DESIGN_VERSION}, got {version!r}'
    source = data['source']
    if source not in ('preset', 'custom'):
        return f'source must be "preset" or "custom", got {source!r}'
    preset_name = data['preset']
    if source == 'custom':
        if preset_name is not None:
            return f'preset must be null for a custom design, got {preset_name!r}'
    else:
        designs = video_contract.available_designs(skill_root)
        if not isinstance(preset_name, str) or preset_name not in designs:
            return (
                f'preset must be a registered design (choose one of: {", ".join(designs)}), '
                f'got {preset_name!r}'
            )

    if inputs is not None and source == 'custom':
        requests = video_contract.request_items(inputs, video_contract.COMPOSITION_REQUESTS_FIELD)
        if not requests:
            return (
                'custom design is only allowed when composition_requests explicitly requests '
                'an out-of-library style; select a registered preset from modules/designs/ instead'
            )

    tokens = data['tokens']
    if not isinstance(tokens, dict):
        return 'tokens must be an object'
    missing = sorted(video_contract.DESIGN_TOKEN_NAMES - set(tokens))
    if missing:
        return f'tokens is missing shared tokens: {", ".join(missing)}'
    invalid_tokens = [name for name, value in tokens.items() if not isinstance(value, str) or not value.strip()]
    if invalid_tokens:
        return f'token values must be non-empty strings: {", ".join(sorted(invalid_tokens))}'

    floors = data['min_font_px']
    if not isinstance(floors, dict) or set(floors) != FONT_FLOOR_KEYS:
        return 'min_font_px must contain exactly reading and ui'
    if not all(_positive_int(floors[name]) for name in FONT_FLOOR_KEYS):
        return 'min_font_px.reading and min_font_px.ui must be positive integers'
    if source == 'custom' and floors['ui'] < 22:
        return 'min_font_px.ui must be at least 22px for a custom design'

    if source == 'preset':
        try:
            preset = video_contract.load_design_preset(skill_root, preset_name)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            return f'preset {preset_name!r} contract cannot be read: {exc}'
        if tokens != preset.get('tokens'):
            return f'tokens must exactly match preset {preset_name!r}'
        if floors != preset.get('min_font_px'):
            return f'min_font_px must exactly match preset {preset_name!r}'
    return None


def load_composition_design(
    path: Path,
    *,
    skill_root: Path,
    inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """读取并校验一份 composition/design.json；失败时抛出 ValueError。"""
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f'{path} cannot be read as a design contract: {exc}') from exc
    problem = composition_design_problem(data, skill_root=skill_root, inputs=inputs)
    if problem:
        raise ValueError(f'{path}: {problem}')
    return data
