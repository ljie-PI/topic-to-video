"""TTS / ASR 流水线脚本共享的后端选择逻辑。

``voice-clone.py`` 与 ``transcribe.py`` 都从同样的三个输入挑后端——``--backend``、
环境变量，以及一个有文档记录的环境探测——并且都提供 ``--resolve-backend`` 把该
决定打印成一个 JSON 文档。本模块持有其中公共的那一半：

* 平台 / 机器 / CUDA / mlx-audio 探测，每个都优先读取有文档记录的
  ``<PREFIX>_DETECT_*`` 覆盖值，使该决定在没有对应硬件时也可测试（各脚本的
  docstring 会写明自己的 prefix），另外还有 ``DASHSCOPE_API_KEY`` 检查；
* :func:`resolve_backend_name` —— CLI > 环境变量 > 自动解析，每个脚本的自动
  解析顺序通过 ``auto_resolve`` 注入；
* 自动解析抛出的错误类型；
* :func:`resolve_backend_cli` 与 :func:`backend_error_response` —— 共享的
  ``--resolve-backend`` 输出，以及退出码映射（未知后端 -> 2，无可用后端 -> 1）。

模块加载时只导入标准库；torch 探测才惰性导入 torch（本仓库把重的导入留在函数
内部）。
"""

from __future__ import annotations

import importlib.util
import os
import platform
import sys
from collections.abc import Callable, Mapping

# 默认探测前缀；每个脚本传入自己文档里写的那个。
DEFAULT_PROBE_PREFIX = 'TTS_DETECT'


class BackendUnavailableError(Exception):
    """自动解析没找到可用后端；携带缺失项清单。"""

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
    """调用方脚本没有注册所请求的后端名。"""


# --- 环境探测（自动后端） -------------------------------------------------------
#
# 每个探测都优先读取 ``<PREFIX>_DETECT_*`` 覆盖值，使自动决定在没有对应硬件时
# 也可测试（在各脚本的 docstring 中有说明）。


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
    except Exception:  # noqa: BLE001 - 没有 torch / torch 损坏 => 无 CUDA
        return False


def detect_mlx_audio(probe_prefix: str = DEFAULT_PROBE_PREFIX) -> bool:
    override = os.environ.get(f'{probe_prefix}_MLX_AUDIO')
    if override is not None:
        return override == '1'
    return importlib.util.find_spec('mlx_audio') is not None


def environment_probes(
    probe_prefix: str = DEFAULT_PROBE_PREFIX, *, include_mlx: bool = False
) -> dict[str, object]:
    """对各项探测做快照：platform、machine、[mlx_audio、]cuda、dashscope_key。"""
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
    """解析出实际生效的后端。返回 (name, source, probes)。

    ``source`` 是 ``'cli'``（``--backend``）、``'env'``（``env_var``）或
    ``'auto'``。显式取值必须已在 ``backends`` 中注册（或为 ``'auto'``）；
    "auto" 把决定交给 ``auto_resolve(probes)``，它返回 ``(name, probes)``，或
    抛出 :class:`BackendUnavailableError`。对未注册的显式取值抛出
    :class:`UnknownBackendError`。
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


# --- CLI：--resolve-backend 与错误载荷 ----------------------------------------


def backend_error_response(
    exc: Exception,
    *,
    log: Callable[[str], None],
    print_json: Callable[[dict[str, object]], None],
) -> int:
    """为后端解析失败打印 JSON 错误；返回其退出码。

    未知后端（非法的 ``--backend`` / 环境变量取值）属于用法错误 -> 2；无可用
    后端属于运行时 / 环境故障 -> 1。
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
    """共享的 ``--resolve-backend`` 主体：打印决定，不加载任何模型。

    ``resolve`` 是调用方脚本自己的无参解析函数，因此本模块不依赖 TTS / ASR
    的后端注册表。成功时总是以一条 JSON 决定退出 0；失败时经
    :func:`backend_error_response` 返回 1 / 2。
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
