"""Layer 6: Integration tests — full CLI parse-to-API flow.

Verifies that cyclopts routing, command functions, and API calls wire together
correctly end-to-end using a launcher wrapper that mimics _launcher's dispatch.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    from collections.abc import Callable

import pytest

from pyshock.cli.config import Config
from pyshock.cli.utils import Session
from pyshock.models.account import AccountInfo
from pyshock.models.operation import ShockerOperation
from pyshock.models.shocker import Shocker
from pyshock.pishockapi import PiShockAPI

if TYPE_CHECKING:
    from cyclopts import App


@pytest.fixture
def mock_api() -> MagicMock:
    """MagicMock with PiShockAPI spec that works as context manager."""
    mock = MagicMock(spec=PiShockAPI)
    mock.__enter__ = MagicMock(return_value=mock)
    mock.__exit__ = MagicMock(return_value=False)
    return mock


@pytest.fixture
def config_with_account() -> Config:
    """Config with one PiShock account and one shocker."""
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


def _execute_via_parse(
    app: App,
    cmd_str: str,
    mock_api: MagicMock,
) -> tuple[Callable[..., Any], Any]:
    """Parse cmd_str via app, then execute the resolved command inside mock_api context.

    Mimics _launcher's dispatch: parse_args -> with api: -> command(*args, **kwargs).
    """
    command, bound, ignored = app.parse_args(
        cmd_str,
        print_error=False,
        exit_on_error=False,
    )

    extra: dict[str, Any] = {}
    if "session" in ignored:
        extra["session"] = Session(api=mock_api, account_id="pishock_1", provider="pishock")

    with mock_api:
        command(*bound.args, **bound.kwargs, **extra)  # type: ignore[operator]

    return command, bound


class TestIntegration:
    """End-to-end integration tests for CLI commands."""

    def test_shock_end_to_end(
        self,
        app: App,
        mock_api: MagicMock,
        config_with_account: Config,
    ) -> None:
        """Parse 'shock 2 75 --force' and verify operate_shocker is called with correct params."""

        with (
            patch("pyshock.cli.utils.get_config", return_value=config_with_account),
            patch("pyshock.cli.config.get_config", return_value=config_with_account),
            patch("pyshock.cli.utils.resolve_shocker_id", return_value="abc123"),
            patch("pyshock.cli.display.render_operation_result"),
        ):
            _execute_via_parse(app, "shock 2 75 --force", mock_api)

        mock_api.operate_shocker.assert_called_once_with(
            shocker="abc123",
            operation=ShockerOperation.SHOCK,
            duration=2000,
            intensity=75,
        )

    def test_vibrate_end_to_end(
        self,
        app: App,
        mock_api: MagicMock,
        config_with_account: Config,
    ) -> None:
        """Parse 'vibrate 3 50 --force' and verify VIBRATE operation with correct params."""

        with (
            patch("pyshock.cli.utils.get_config", return_value=config_with_account),
            patch("pyshock.cli.config.get_config", return_value=config_with_account),
            patch("pyshock.cli.utils.resolve_shocker_id", return_value="abc123"),
            patch("pyshock.cli.display.render_operation_result"),
        ):
            _execute_via_parse(app, "vibrate 3 50 --force", mock_api)

        mock_api.operate_shocker.assert_called_once_with(
            shocker="abc123",
            operation=ShockerOperation.VIBRATE,
            duration=3000,
            intensity=50,
        )

    def test_beep_end_to_end(
        self,
        app: App,
        mock_api: MagicMock,
        config_with_account: Config,
    ) -> None:
        """Parse 'beep --force' and verify operate_shocker is called with beep defaults."""

        with (
            patch("pyshock.cli.utils.get_config", return_value=config_with_account),
            patch("pyshock.cli.config.get_config", return_value=config_with_account),
            patch("pyshock.cli.utils.resolve_shocker_id", return_value="abc123"),
            patch("pyshock.cli.display.render_operation_result"),
        ):
            _execute_via_parse(app, "beep --force", mock_api)

        mock_api.operate_shocker.assert_called_once_with(
            shocker="abc123",
            operation=ShockerOperation.BEEP,
            duration=500,
            intensity=50,
        )

    def test_info_end_to_end(
        self,
        app: App,
        mock_api: MagicMock,
        test_shocker: Shocker,
    ) -> None:
        """Parse 'info --id abc123' and verify get_shocker_by_id is called."""
        mock_api.get_shocker_by_id.return_value = test_shocker

        with patch("pyshock.cli.commands.shocker.render_info_table"):
            _execute_via_parse(app, "info --id abc123", mock_api)

        mock_api.get_shocker_by_id.assert_called_once_with("abc123")

    def test_devices_end_to_end(
        self,
        app: App,
        mock_api: MagicMock,
        config_with_account: Config,
        test_shocker: Shocker,
    ) -> None:
        """Parse 'devices' and verify list_shockers is called for each account."""
        mock_api.list_shockers.return_value = [test_shocker]

        with (
            patch("pyshock.cli.commands.meta.get_config", return_value=config_with_account),
            patch("pyshock.cli.config.get_config", return_value=config_with_account),
            patch(
                "pyshock.cli.commands.meta.utils.get_session_for_account",
                return_value=Session(
                    api=mock_api,
                    account_id="pishock_1",
                    provider="pishock",
                ),
            ),
            patch("pyshock.cli.commands.meta.render_shocker_table_by_account"),
            patch.object(Config, "save"),
        ):
            _execute_via_parse(app, "devices", mock_api)

        mock_api.list_shockers.assert_called_once()

    def test_verify_end_to_end(
        self,
        app: App,
        mock_api: MagicMock,
        config_with_account: Config,
    ) -> None:
        """Parse 'verify --account pishock_1' and verify get_account is called."""
        mock_api.get_account.return_value = AccountInfo(user_id="12345", username="testuser")

        with (
            patch("pyshock.cli.commands.meta.get_config", return_value=config_with_account),
            patch("pyshock.cli.config.get_config", return_value=config_with_account),
            patch(
                "pyshock.cli.commands.meta.utils.get_session_for_account",
                return_value=Session(
                    api=mock_api,
                    account_id="pishock_1",
                    provider="pishock",
                ),
            ),
            patch("pyshock.cli.commands.meta.render_verify_panel"),
        ):
            _execute_via_parse(app, "verify --account pishock_1", mock_api)

        mock_api.get_account.assert_called_once()

    def test_logout_end_to_end(
        self,
        app: App,
        config_with_account: Config,
    ) -> None:
        """Parse 'logout --account pishock_1' and verify account is removed."""
        with (
            patch("pyshock.cli.commands.meta.get_config", return_value=config_with_account),
            patch("pyshock.cli.config.get_config", return_value=config_with_account),
            patch("pyshock.cli.utils.get_config", return_value=config_with_account),
            patch("pyshock.cli.commands.meta.console"),
            patch.object(Config, "save"),
        ):
            command, bound, _ignored = app.parse_args(
                "logout --account pishock_1",
                print_error=False,
                exit_on_error=False,
            )
            command(*bound.args, **bound.kwargs)

        assert "pishock_1" not in config_with_account.accounts

    def test_code_add_end_to_end(
        self,
        app: App,
        mock_api: MagicMock,
    ) -> None:
        """Parse 'code add ABC123' and verify add_share_code is called."""
        _execute_via_parse(app, "code add ABC123", mock_api)

        mock_api.add_share_code.assert_called_once_with("ABC123")
