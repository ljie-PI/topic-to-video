"""Shared backend selection for the TTS / ASR pipeline scripts.

``voice-clone.py`` and ``transcribe.py`` both pick a backend from the same
three inputs — ``--backend``, an environment variable, then a documented
environment probe — and both expose ``--resolve-backend`` to print that
decision as one JSON document. This module holds the common half:

* the platform / machine / CUDA / mlx-audio probes, each reading a
  documented ``<PREFIX>_DETECT_*`` override so the decision is testable
  without the hardware (the script docstrings name the prefix), plus the
  ``DASHSCOPE_API_KEY`` check;
* :func:`resolve_backend_name` — CLI > env > auto resolution, with the
  per-script auto order injected as ``auto_resolve``;
* the error types auto resolution raises;
* :func:`resolve_backend_cli` and :func:`backend_error_response` — the
  shared ``--resolve-backend`` output and the exit-code mapping
  (unknown backend -> 2, no usable backend -> 1).

Only stdlib is imported at module load; the torch probe imports torch
lazily (heavy imports stay function-local in this repo).
"""

from __future__ import annotations

import importlib.util
import os
import platform
import sys
from collections.abc import Callable, Mapping

# Default probe prefix; each script passes its documented one.
DEFAULT_PROBE_PREFIX = 'TTS_DETECT'


class BackendUnavailableError(Exception):
    """Auto resolution found no usable backend; carries the missing list."""

    def __init__(
        self,
        message: str,
        missing: list[str] | None = None,
        probes: dict[str, object] | None = None,
    ) -> None:
        self.missing = list(missing or [])
        self.probes = dict(probes or {})
        super().__init__(message)


class UnknownBackendError(Exception):
    """The requested backend name is not registered by the calling script."""


# --- environment probes (auto backend) -----------------------------------------
#
# Every probe reads a ``<PREFIX>_DETECT_*`` override first so the auto decision
# is testable without the hardware (documented in each script's docstring).


def detect_platform(probe_prefix: str = DEFAULT_PROBE_PREFIX) -> str:
    return os.environ.get(f'{probe_prefix}_PLATFORM') or sys.platform


def detect_machine(probe_prefix: str = DEFAULT_PROBE_PREFIX) -> str:
    return os.environ.get(f'{probe_prefix}_MACHINE') or platform.machine()


def detect_cuda(probe_prefix: str = DEFAULT_PROBE_PREFIX) -> bool:
    override = os.environ.get(f'{probe_prefix}_CUDA')
    if override is not None:
        return override == '1'
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:  # noqa: BLE001 - no torch / broken torch => no CUDA
        return False


def detect_mlx_audio(probe_prefix: str = DEFAULT_PROBE_PREFIX) -> bool:
    override = os.environ.get(f'{probe_prefix}_MLX_AUDIO')
    if override is not None:
        return override == '1'
    return importlib.util.find_spec('mlx_audio') is not None


def environment_probes(
    probe_prefix: str = DEFAULT_PROBE_PREFIX, *, include_mlx: bool = False
) -> dict[str, object]:
    """Snapshot the probes: platform, machine, [mlx_audio,] cuda, dashscope_key."""
    probes: dict[str, object] = {
        'platform': detect_platform(probe_prefix),
        'machine': detect_machine(probe_prefix),
    }
    if include_mlx:
        probes['mlx_audio'] = detect_mlx_audio(probe_prefix)
    probes['cuda'] = detect_cuda(probe_prefix)
    probes['dashscope_key'] = bool(os.environ.get('DASHSCOPE_API_KEY'))
    return probes


def resolve_backend_name(
    cli_backend: str | None,
    *,
    env_var: str,
    probe_prefix: str,
    backends: Mapping[str, object],
    auto_resolve: Callable[[dict[str, object]], tuple[str, dict[str, object]]],
    label: str = 'backend',
    include_mlx: bool = False,
) -> tuple[str, str, dict[str, object]]:
    """Resolve the effective backend. Returns (name, source, probes).

    ``source`` is ``'cli'`` (``--backend``), ``'env'`` (``env_var``) or
    ``'auto'``. Explicit values must be registered in ``backends`` (or be
    ``'auto'``); "auto" delegates the decision to ``auto_resolve(probes)``,
    which returns ``(name, probes)`` or raises :class:`BackendUnavailableError`.
    Raises :class:`UnknownBackendError` for unregistered explicit values.
    """
    env_backend = os.environ.get(env_var)
    explicit = cli_backend or env_backend
    source = 'cli' if cli_backend else ('env' if env_backend else 'auto')
    probes = environment_probes(probe_prefix, include_mlx=include_mlx)
    if explicit and explicit != 'auto':
        if explicit not in backends:
            raise UnknownBackendError(f'unknown {label} backend: {explicit}')
        return explicit, source, probes
    backend_name, probes = auto_resolve(probes)
    return backend_name, 'auto', probes


# --- CLI: --resolve-backend + error payloads -----------------------------------


def backend_error_response(
    exc: Exception,
    *,
    log: Callable[[str], None],
    print_json: Callable[[dict[str, object]], None],
) -> int:
    """Print the JSON error for a backend-resolution failure; return its exit code.

    Unknown backend (a bad ``--backend`` / env value) is a usage error -> 2;
    no usable backend is a runtime/environment failure -> 1.
    """
    if isinstance(exc, UnknownBackendError):
        log(f'error: {exc}')
        print_json({'success': False, 'error': str(exc)})
        return 2
    if isinstance(exc, BackendUnavailableError):
        log(f'error: {exc}')
        print_json(
            {
                'success': False,
                'error': str(exc),
                'missing': exc.missing,
                'probes': exc.probes,
            }
        )
        return 1
    raise exc


def resolve_backend_cli(
    resolve: Callable[[], tuple[str, str, dict[str, object]]],
    *,
    log: Callable[[str], None],
    print_json: Callable[[dict[str, object]], None],
) -> int:
    """Shared ``--resolve-backend`` body: print the decision, no model is loaded.

    ``resolve`` is the calling script's zero-argument resolver, so this module
    stays independent of the TTS / ASR backend registries. Always exits 0 with
    a JSON decision on success; 1 / 2 via :func:`backend_error_response`.
    """
    try:
        backend_name, source, probes = resolve()
    except (UnknownBackendError, BackendUnavailableError) as exc:
        return backend_error_response(exc, log=log, print_json=print_json)
    print_json(
        {
            'success': True,
            'backend': backend_name,
            'backend_source': source,
            'probes': probes,
        }
    )
    return 0
