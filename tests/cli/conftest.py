"""CLI test fixtures — cyclopts app, config, API mock, and console."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import platformdirs
import pytest
from rich.console import Console

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from cyclopts import App

    from pyshock.models.shocker import Shocker

from pyshock.cli.config import Config
from pyshock.cli.context import _current_account_id, json_mode
from pyshock.pishockapi import PiShockAPI


@pytest.fixture(autouse=True)
def _clean_config() -> Generator[None]:
    """Isolate CLI tests from the user's persisted configuration."""
    from pyshock.cli.config import reset_config_cache

    config_path = Path(platformdirs.user_config_dir("PyShock")) / "config.json"
    if config_path.exists():
        config_path.unlink()
    reset_config_cache()
    yield
    if config_path.exists():
        config_path.unlink()
    reset_config_cache()


@pytest.fixture
def console() -> Console:
    """Deterministic Rich console for capturing output in tests."""
    return Console(
        width=80,
        force_terminal=True,
        highlight=False,
        color_system=None,
        legacy_windows=False,
    )


@pytest.fixture
def app(console: Console) -> Generator[App]:
    """Return the real cyclopts App with test console and result_action.

    The real ``_launcher`` (registered as ``app.meta.default``) references
    the module-level ``app`` for ``app.parse_args`` and ``app.help_print``,
    so we must use the actual app object rather than constructing a clone.

    The fixture swaps in the deterministic ``console`` and sets
    ``result_action="return_value"`` so that command functions return
    their result instead of exiting.  Both values are restored on teardown.
    """
    from pyshock.cli.main import app as real_app

    old_console = real_app.console
    old_result_action = real_app.result_action

    real_app.console = console
    real_app.result_action = "return_value"

    yield real_app

    real_app.console = old_console
    real_app.result_action = old_result_action


@pytest.fixture
def assert_parse_args(app: App) -> Callable[..., tuple]:
    """Return a callable that validates cyclopts argument parsing.

    Args:
        cmd_str: The CLI token string to parse (e.g. ``"shock 1 50"``).
        expected_command: The command function that should be resolved.
        expected_args: Positional args to assert on the bound arguments.
        expected_kwargs: Keyword args to assert on the bound arguments.

    Returns:
        The ``(command, bound, ignored)`` tuple from ``app.parse_args``.

    Raises:
        AssertionError: If command identity or bound args/kwargs differ.
    """

    def _assert(
        cmd_str: str,
        expected_command: Callable[..., Any],
        expected_args: tuple | None = None,
        expected_kwargs: dict[str, Any] | None = None,
    ) -> tuple:
        command, bound, ignored = app.parse_args(
            cmd_str,
            print_error=False,
            exit_on_error=False,
        )

        if command is not expected_command:
            raise AssertionError(
                f"Expected command {expected_command.__name__!r}, "
                f"got {getattr(command, '__name__', command)!r}"
            )

        if expected_args is not None:
            actual_args = tuple(bound.args)
            if actual_args != tuple(expected_args):
                raise AssertionError(
                    f"Expected args {expected_args!r}, got {actual_args!r}"
                )

        if expected_kwargs is not None:
            actual_kwargs = dict(bound.kwargs)
            if actual_kwargs != expected_kwargs:
                raise AssertionError(
                    f"Expected kwargs {expected_kwargs!r}, got {actual_kwargs!r}"
                )

        return command, bound, ignored

    return _assert


@pytest.fixture
def queue() -> list:
    """Bare list appended to by mocked handlers to trace execution order."""
    return []


@pytest.fixture
def mock_pishock_api() -> MagicMock:
    """MagicMock with PiShockAPI spec that also works as a context manager.

    Distinct from the root ``mock_api`` (MockAPI WSGI app) — this is a
    plain mock of the Python client used by CLI command tests.
    """
    mock = MagicMock(spec=PiShockAPI)
    mock.__enter__ = MagicMock(return_value=mock)
    mock.__exit__ = MagicMock(return_value=False)
    return mock


@pytest.fixture
def mock_config() -> Config:
    """Config with one PiShock account (``pishock_1``) and one shocker."""
    config = Config()
    config._data = {
        "accounts": {
            "pishock_1": {
                "provider": "pishock",
                "api_key": "test_api_key_123",
                "shockers": [
                    {
                        "shocker_id": "abc123",
                        "name": "Test Shocker",
                        "can_shock": True,
                        "can_vibrate": True,
                        "can_beep": True,
                        "can_hold": True,
                        "max_intensity": 100,
                        "max_duration": 15000,
                        "is_v3": True,
                        "can_pause": True,
                        "pishock_hub_id": 1,
                    }
                ],
            }
        },
        "default_shocker_id": "abc123",
        "confirmations": {"shock": False, "vibrate": False, "beep": False},
    }
    return config


@pytest.fixture
def test_shocker() -> Shocker:
    """Return a standard test Shocker instance."""
    from pyshock.models.shocker import Shocker

    return Shocker(
        shocker_id="abc123",
        name="Test Shocker",
        can_shock=True,
        can_vibrate=True,
        can_beep=True,
        can_hold=True,
        max_intensity=100,
        max_duration=15000,
        is_v3=True,
        can_pause=True,
        pishock_hub_id=1,
    )


@pytest.fixture(autouse=True)
def patch_sys_argv() -> Generator[None]:
    """Set ``sys.argv`` to a minimal ``["pyshock"]`` for every CLI test."""
    old_argv = sys.argv
    sys.argv = ["pyshock"]
    yield
    sys.argv = old_argv


@pytest.fixture(autouse=True)
def _reset_context_vars() -> Generator[None]:
    """Reset ContextVars and config cache to defaults before/after every CLI test."""
    from pyshock.cli.config import reset_config_cache

    json_mode.set(False)
    _current_account_id.set("")
    reset_config_cache()
    yield
    json_mode.set(False)
    _current_account_id.set("")
    reset_config_cache()


@pytest.fixture
def mock_config_with_account(mock_config: Config) -> Generator[Config]:
    """Patch ``get_config`` in both config and utils modules to return ``mock_config``.

    ``pyshock.cli.utils`` imports ``get_config`` at module level, so we must
    patch the name in both modules to ensure every call site sees the mock.
    """
    with (
        patch("pyshock.cli.config.get_config", return_value=mock_config),
        patch("pyshock.cli.utils.get_config", return_value=mock_config),
    ):
        yield mock_config
