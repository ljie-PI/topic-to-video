"""Direct public-API tests for shared backend resolution."""
from __future__ import annotations

import pytest

from backend_select import (
    BackendUnavailableError,
    UnknownBackendError,
    backend_error_response,
    environment_probes,
    resolve_backend_cli,
    resolve_backend_name,
)


@pytest.fixture
def probe_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv('TEST_DETECT_PLATFORM', 'test-platform')
    monkeypatch.setenv('TEST_DETECT_MACHINE', 'test-machine')
    monkeypatch.setenv('TEST_DETECT_CUDA', '0')
    monkeypatch.setenv('TEST_DETECT_MLX_AUDIO', '1')
    monkeypatch.delenv('DASHSCOPE_API_KEY', raising=False)


def resolve(cli_backend=None):
    return resolve_backend_name(
        cli_backend,
        env_var='TEST_BACKEND',
        probe_prefix='TEST_DETECT',
        backends={'fake': object()},
        auto_resolve=lambda probes: ('auto-backend', probes),
        label='test',
        include_mlx=True,
    )


def test_cli_backend_wins_over_environment_and_auto(probe_env, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv('TEST_BACKEND', 'other')

    name, source, probes = resolve('fake')

    assert (name, source) == ('fake', 'cli')
    assert probes == {
        'platform': 'test-platform',
        'machine': 'test-machine',
        'mlx_audio': True,
        'cuda': False,
        'dashscope_key': False,
    }


def test_environment_backend_is_used_when_cli_is_absent(probe_env, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv('TEST_BACKEND', 'fake')

    assert resolve()[:2] == ('fake', 'env')


def test_auto_backend_receives_the_environment_probes(probe_env, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv('TEST_BACKEND', raising=False)
    seen = []

    name, source, probes = resolve_backend_name(
        None,
        env_var='TEST_BACKEND',
        probe_prefix='TEST_DETECT',
        backends={},
        auto_resolve=lambda current: (seen.append(current) or ('chosen', current)),
        include_mlx=True,
    )

    assert (name, source) == ('chosen', 'auto')
    assert seen == [probes]


def test_unknown_explicit_backend_names_the_caller_label(probe_env):
    with pytest.raises(UnknownBackendError, match='unknown test backend: bogus'):
        resolve('bogus')


def test_environment_probes_detect_dashscope_key(probe_env, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv('DASHSCOPE_API_KEY', 'secret')

    assert environment_probes('TEST_DETECT')['dashscope_key'] is True


def test_resolve_cli_prints_one_success_payload():
    payloads = []
    code = resolve_backend_cli(
        lambda: ('fake', 'cli', {'cuda': False}),
        log=lambda message: pytest.fail(f'unexpected log: {message}'),
        print_json=payloads.append,
    )

    assert code == 0
    assert payloads == [{
        'success': True, 'backend': 'fake', 'backend_source': 'cli', 'probes': {'cuda': False}
    }]


@pytest.mark.parametrize(
    ('error', 'expected_code'),
    [
        (UnknownBackendError('unknown test backend'), 2),
        (BackendUnavailableError('none available', ['CUDA'], {'cuda': False}), 1),
    ],
)
def test_resolve_cli_maps_resolution_errors_to_json_and_exit_codes(error, expected_code):
    payloads = []
    logs = []

    def fail_resolution():
        raise error

    code = resolve_backend_cli(fail_resolution, log=logs.append, print_json=payloads.append)

    assert code == expected_code
    assert logs == [f'error: {error}']
    assert payloads[0]['success'] is False
    assert payloads[0]['error'] == str(error)


def test_backend_error_response_does_not_hide_unrelated_exceptions():
    error = RuntimeError('implementation bug')
    with pytest.raises(RuntimeError, match='implementation bug'):
        backend_error_response(error, log=lambda message: None, print_json=lambda payload: None)
