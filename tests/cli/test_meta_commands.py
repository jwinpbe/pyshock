"""Tests for meta CLI commands: verify, devices, logout, confirm."""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest

from pyshock.cli.config import Config
from pyshock.cli.context import json_mode
from pyshock.errors import NotAuthorizedError
from pyshock.models.account import AccountInfo
from pyshock.models.shocker import Shocker
from pyshock.pishockapi import PiShockAPI

test_account = AccountInfo(user_id="12345", username="testuser")

test_shocker = Shocker(
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
    hub_id=1,
)


class TestVerify:
    """Tests for the verify command."""

    def test_single_account_verify(
        self,
        mock_config_with_account: Config,
        mock_pishock_api: MagicMock,
    ) -> None:
        """Verify a single account by ID calls API and renders panel."""
        mock_pishock_api.get_account.return_value = test_account

        with (
            patch(
                "pyshock.cli.commands.meta.get_config",
                return_value=mock_config_with_account,
            ),
            patch(
                "pyshock.cli.commands.meta.utils.get_api_for_account",
                return_value=mock_pishock_api,
            ),
            patch("pyshock.cli.commands.meta.render_verify_panel") as mock_render,
        ):
            from pyshock.cli.commands.meta import verify

            verify(account_id="pishock_1")

        mock_pishock_api.get_account.assert_called_once()
        mock_render.assert_called_once_with(test_account, "pishock", "pishock_1")

    def test_verify_all_accounts(
        self,
        mock_config_with_account: Config,
        mock_pishock_api: MagicMock,
    ) -> None:
        """Verify all accounts when no account_id is provided."""
        mock_pishock_api.get_account.return_value = test_account
        mock_api_2 = MagicMock(spec=PiShockAPI)
        mock_api_2.__enter__ = MagicMock(return_value=mock_api_2)
        mock_api_2.__exit__ = MagicMock(return_value=False)
        mock_api_2.get_account.return_value = AccountInfo(
            user_id="67890", username="user2"
        )

        mock_config_with_account._data["accounts"]["pishock_2"] = {
            "provider": "pishock",
            "api_key": "test_api_key_2",
            "shockers": [],
        }

        def api_side_effect(account_id: str) -> MagicMock:
            return mock_pishock_api if account_id == "pishock_1" else mock_api_2

        with (
            patch(
                "pyshock.cli.commands.meta.get_config",
                return_value=mock_config_with_account,
            ),
            patch(
                "pyshock.cli.commands.meta.utils.get_api_for_account",
                side_effect=api_side_effect,
            ),
            patch("pyshock.cli.commands.meta.render_verify_panel") as mock_render,
        ):
            from pyshock.cli.commands.meta import verify

            verify()

        assert mock_pishock_api.get_account.call_count == 1
        assert mock_api_2.get_account.call_count == 1
        assert mock_render.call_count == 2
        calls = mock_render.call_args_list
        assert calls[0].args == (test_account, "pishock", "pishock_1")
        assert calls[1].args == (
            AccountInfo(user_id="67890", username="user2"),
            "pishock",
            "pishock_2",
        )

    def test_one_account_fails_auth(
        self,
        mock_config_with_account: Config,
        mock_pishock_api: MagicMock,
    ) -> None:
        """When one account raises NotAuthorizedError, error is reported."""
        mock_pishock_api.get_account.return_value = test_account
        mock_api_2 = MagicMock(spec=PiShockAPI)
        mock_api_2.__enter__ = MagicMock(return_value=mock_api_2)
        mock_api_2.__exit__ = MagicMock(return_value=False)
        mock_api_2.get_account.side_effect = NotAuthorizedError()

        mock_config_with_account._data["accounts"]["pishock_2"] = {
            "provider": "pishock",
            "api_key": "bad_key",
            "shockers": [],
        }

        def api_side_effect(account_id: str) -> MagicMock:
            return mock_pishock_api if account_id == "pishock_1" else mock_api_2

        with (
            patch(
                "pyshock.cli.commands.meta.get_config",
                return_value=mock_config_with_account,
            ),
            patch(
                "pyshock.cli.commands.meta.utils.get_api_for_account",
                side_effect=api_side_effect,
            ),
            patch("pyshock.cli.commands.meta.render_verify_panel") as mock_render,
            patch("pyshock.cli.commands.meta.console_err") as mock_err,
        ):
            from pyshock.cli.commands.meta import verify

            verify()

        mock_render.assert_called_once_with(test_account, "pishock", "pishock_1")
        mock_err.print.assert_called_once()
        assert "pishock_2" in mock_err.print.call_args.args[0]

    def test_account_not_found(
        self,
        mock_config_with_account: Config,
    ) -> None:
        """Raise SystemExit(1) when verifying a nonexistent account."""
        with (
            patch(
                "pyshock.cli.commands.meta.get_config",
                return_value=mock_config_with_account,
            ),
            patch("pyshock.cli.commands.meta.console_err") as mock_err,
            pytest.raises(SystemExit) as exc_info,
        ):
            from pyshock.cli.commands.meta import verify

            verify(account_id="nonexistent")

        assert exc_info.value.code == 1
        mock_err.print.assert_called_once()
        assert "nonexistent" in mock_err.print.call_args.args[0]

    def test_json_output(
        self,
        mock_config_with_account: Config,
        mock_pishock_api: MagicMock,
    ) -> None:
        """JSON mode outputs structured data instead of rendering panel."""
        mock_pishock_api.get_account.return_value = test_account

        with (
            patch(
                "pyshock.cli.commands.meta.get_config",
                return_value=mock_config_with_account,
            ),
            patch(
                "pyshock.cli.commands.meta.utils.get_api_for_account",
                return_value=mock_pishock_api,
            ),
            patch("pyshock.cli.commands.meta.render_verify_panel") as mock_render,
            patch("pyshock.cli.commands.meta.print_output") as mock_print_output,
        ):
            from pyshock.cli.commands.meta import verify

            json_mode.set(True)
            verify(account_id="pishock_1")

        mock_render.assert_not_called()
        mock_print_output.assert_called_once()
        output = mock_print_output.call_args.args[0]
        assert output["ok"] is True
        assert output["account_id"] == "pishock_1"
        assert output["username"] == "testuser"


class TestDevices:
    """Tests for the devices command."""

    def test_lists_all_devices_grouped(
        self,
        mock_config_with_account: Config,
        mock_pishock_api: MagicMock,
    ) -> None:
        """List shockers from all accounts and render grouped table."""
        shockers = [test_shocker, replace(test_shocker, shocker_id="def456", name="Second")]
        mock_pishock_api.list_shockers.return_value = shockers

        with (
            patch(
                "pyshock.cli.commands.meta.get_config",
                return_value=mock_config_with_account,
            ),
            patch(
                "pyshock.cli.commands.meta.utils.get_api_for_account",
                return_value=mock_pishock_api,
            ),
            patch("pyshock.cli.commands.meta.render_shocker_table_by_account") as mock_render,
            patch.object(Config, "save"),
        ):
            from pyshock.cli.commands.meta import devices

            devices()

        mock_pishock_api.list_shockers.assert_called_once()
        mock_render.assert_called_once()
        rendered = mock_render.call_args.args[0]
        assert "pishock_1" in rendered
        assert len(rendered["pishock_1"]) == 2

    def test_no_devices_found(
        self,
        mock_config_with_account: Config,
        mock_pishock_api: MagicMock,
    ) -> None:
        """Print 'No devices found' when all accounts return empty lists."""
        mock_pishock_api.list_shockers.return_value = []

        with (
            patch(
                "pyshock.cli.commands.meta.get_config",
                return_value=mock_config_with_account,
            ),
            patch(
                "pyshock.cli.commands.meta.utils.get_api_for_account",
                return_value=mock_pishock_api,
            ),
            patch("pyshock.cli.commands.meta.console") as mock_console,
            patch.object(Config, "save"),
        ):
            from pyshock.cli.commands.meta import devices

            devices()

        mock_console.print.assert_called_with("No devices found.")

    def test_json_output(
        self,
        mock_config_with_account: Config,
        mock_pishock_api: MagicMock,
    ) -> None:
        """JSON mode outputs shocker list as JSON."""
        mock_pishock_api.list_shockers.return_value = [test_shocker]

        with (
            patch(
                "pyshock.cli.commands.meta.get_config",
                return_value=mock_config_with_account,
            ),
            patch(
                "pyshock.cli.commands.meta.utils.get_api_for_account",
                return_value=mock_pishock_api,
            ),
            patch("pyshock.cli.commands.meta.print_output") as mock_print_output,
            patch("pyshock.cli.commands.meta.render_shocker_table_by_account") as mock_render,
            patch.object(Config, "save"),
        ):
            from pyshock.cli.commands.meta import devices

            json_mode.set(True)
            devices()

        mock_render.assert_not_called()
        mock_print_output.assert_called_once()
        output = mock_print_output.call_args.args[0]
        assert isinstance(output, list)
        assert len(output) == 1
        assert output[0]["shocker_id"] == "abc123"


class TestLogout:
    """Tests for the logout command."""

    def test_remove_specific_account(
        self,
        mock_config_with_account: Config,
    ) -> None:
        """Remove a specific account and save config."""
        with (
            patch(
                "pyshock.cli.commands.meta.get_config",
                return_value=mock_config_with_account,
            ),
            patch("pyshock.cli.commands.meta.console") as mock_console,
        ):
            from pyshock.cli.commands.meta import logout

            logout(account_id="pishock_1")

        assert "pishock_1" not in mock_config_with_account.accounts
        mock_console.print.assert_any_call(
            "[green]Account [bold]pishock_1[/bold] removed.[/green]"
        )

    def test_no_accounts(
        self,
        mock_config_with_account: Config,
    ) -> None:
        """Print 'No accounts configured' when there are no accounts."""
        mock_config_with_account._data["accounts"] = {}

        with (
            patch(
                "pyshock.cli.commands.meta.get_config",
                return_value=mock_config_with_account,
            ),
            patch("pyshock.cli.commands.meta.console") as mock_console,
        ):
            from pyshock.cli.commands.meta import logout

            logout()

        mock_console.print.assert_called_with("[yellow]No accounts configured.[/yellow]")

    def test_no_account_non_tty(
        self,
        mock_config_with_account: Config,
    ) -> None:
        """Raise SystemExit(1) when no account_id and not a TTY."""
        with (
            patch(
                "pyshock.cli.commands.meta.get_config",
                return_value=mock_config_with_account,
            ),
            patch("pyshock.cli.commands.meta.terminal_check.isatty", return_value=False),
            patch("pyshock.cli.commands.meta.console_err") as mock_err,
            pytest.raises(SystemExit) as exc_info,
        ):
            from pyshock.cli.commands.meta import logout

            logout()

        assert exc_info.value.code == 1
        mock_err.print.assert_called_once()
        assert "Cannot prompt" in mock_err.print.call_args.args[0]

    def test_account_not_in_config(
        self,
        mock_config_with_account: Config,
    ) -> None:
        """No error when removing a nonexistent account (remove_account is no-op)."""
        with (
            patch(
                "pyshock.cli.commands.meta.get_config",
                return_value=mock_config_with_account,
            ),
            patch("pyshock.cli.commands.meta.terminal_check.isatty", return_value=False),
            patch("pyshock.cli.commands.meta.console") as mock_console,
            patch.object(Config, "save"),
        ):
            from pyshock.cli.commands.meta import logout

            logout(account_id="nonexistent")

        assert "pishock_1" in mock_config_with_account.accounts
        mock_console.print.assert_called_with(
            "[green]Account [bold]nonexistent[/bold] removed.[/green]"
        )


class TestConfirm:
    """Tests for the confirm command."""

    def test_show_settings(
        self,
        mock_config_with_account: Config,
    ) -> None:
        """Show confirmation settings panel with all three operations."""
        with (
            patch(
                "pyshock.cli.commands.meta.get_config",
                return_value=mock_config_with_account,
            ),
            patch(
                "pyshock.cli.commands.meta.render_confirmation_panel"
            ) as mock_render,
        ):
            from pyshock.cli.commands.meta import confirm

            confirm()

        mock_render.assert_called_once()
        ops = mock_render.call_args.args[0]
        assert len(ops) == 3
        assert [op for op, _ in ops] == ["shock", "beep", "vibrate"]

    def test_toggle_shock(
        self,
        mock_config_with_account: Config,
    ) -> None:
        """Toggle shock confirmation from disabled to enabled."""
        assert mock_config_with_account.confirmation_enabled("shock") is False

        with (
            patch(
                "pyshock.cli.commands.meta.get_config",
                return_value=mock_config_with_account,
            ),
            patch("pyshock.cli.commands.meta.console") as mock_console,
        ):
            from pyshock.cli.commands.meta import confirm

            confirm("shock")

        assert mock_config_with_account.confirmation_enabled("shock") is True
        mock_console.print.assert_called_with(
            "Confirmation for [bold]shock[/bold] is now [bold]enabled[/bold]."
        )

    def test_toggle_vibrate(
        self,
        mock_config_with_account: Config,
    ) -> None:
        """Toggle vibrate confirmation from disabled to enabled."""
        assert mock_config_with_account.confirmation_enabled("vibrate") is False

        with (
            patch(
                "pyshock.cli.commands.meta.get_config",
                return_value=mock_config_with_account,
            ),
            patch("pyshock.cli.commands.meta.console") as mock_console,
        ):
            from pyshock.cli.commands.meta import confirm

            confirm("vibrate")

        assert mock_config_with_account.confirmation_enabled("vibrate") is True
        mock_console.print.assert_called_with(
            "Confirmation for [bold]vibrate[/bold] is now [bold]enabled[/bold]."
        )

    def test_unknown_operation(
        self,
        mock_config_with_account: Config,
    ) -> None:
        """Raise SystemExit(1) for an unknown operation name."""
        with (
            patch(
                "pyshock.cli.commands.meta.get_config",
                return_value=mock_config_with_account,
            ),
            patch("pyshock.cli.commands.meta.console") as mock_console,
            pytest.raises(SystemExit) as exc_info,
        ):
            from pyshock.cli.commands.meta import confirm

            confirm("jump")

        assert exc_info.value.code == 1
        assert any("jump" in str(call) for call in mock_console.print.call_args_list)
