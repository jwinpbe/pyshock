"""Tests for the auth CLI command (meta.auth)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pyshock.cli.config import Config
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
    pishock_hub_id=1,
)


class TestAuth:
    """Tests for the auth command."""

    def _make_config(self, accounts: dict | None = None) -> Config:
        config = Config()
        if accounts is not None:
            config._data["accounts"] = accounts
        return config

    def _make_api_mock(
        self,
        *,
        get_account_return: AccountInfo = test_account,
        list_shockers_return: list[Shocker] | None = None,
        get_account_side_effect: Exception | None = None,
    ) -> MagicMock:
        mock = MagicMock(spec=PiShockAPI)
        mock.__enter__ = MagicMock(return_value=mock)
        mock.__exit__ = MagicMock(return_value=False)
        if get_account_side_effect is not None:
            mock.get_account.side_effect = get_account_side_effect
        else:
            mock.get_account.return_value = get_account_return
        mock.list_shockers.return_value = (
            list_shockers_return if list_shockers_return is not None else [test_shocker]
        )
        return mock

    def test_new_account_with_api_key_flag(
        self,
    ) -> None:
        """api_key via flag creates new account, fetches shockers, auto-generates pishock_1."""
        config = self._make_config()
        api_mock = self._make_api_mock()

        with (
            patch("pyshock.cli.commands.meta.get_config", return_value=config),
            patch("pyshock.cli.config.get_config", return_value=config),
            patch("pyshock.cli.commands.meta.terminal_check.isatty", return_value=False),
            patch(
                "pyshock.cli.commands.init_creds.prompt_pishock_credentials",
                return_value={"api_key": "test_key"},
            ),
            patch("pyshock.cli.commands.meta.PiShockAPI", return_value=api_mock),
            patch.object(Config, "save"),
        ):
            from pyshock.cli.commands.meta import auth

            auth(api_key="test_key")

        assert "pishock_1" in config.accounts
        assert config.accounts["pishock_1"]["provider"] == "pishock"
        assert config.accounts["pishock_1"]["api_key"] == "test_key"
        api_mock.get_account.assert_called_once()
        api_mock.list_shockers.assert_called_once()

    def test_existing_account_forced(
        self,
    ) -> None:
        """--account=pishock_1 --force overwrites existing account (including old shockers)."""
        config = self._make_config({
            "pishock_1": {
                "provider": "pishock",
                "api_key": "old_key",
                "shockers": [
                    {
                        "shocker_id": "old_shocker",
                        "name": "Old Shocker",
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
        })
        api_mock = self._make_api_mock(list_shockers_return=[])

        with (
            patch("pyshock.cli.commands.meta.get_config", return_value=config),
            patch("pyshock.cli.config.get_config", return_value=config),
            patch("pyshock.cli.commands.meta.terminal_check.isatty", return_value=False),
            patch(
                "pyshock.cli.commands.init_creds.prompt_pishock_credentials",
                return_value={"api_key": "new_key"},
            ),
            patch("pyshock.cli.commands.meta.PiShockAPI", return_value=api_mock),
            patch.object(Config, "save"),
        ):
            from pyshock.cli.commands.meta import auth

            auth(api_key="new_key", account_id="pishock_1", force=True)

        assert config.accounts["pishock_1"]["api_key"] == "new_key"
        # Old shocker removed by remove_account (clears shocker_index)
        assert "old_shocker" not in config.shocker_index
        api_mock.get_account.assert_called_once()

    def test_duplicate_account_no_force(
        self,
    ) -> None:
        """--account=pishock_1 without --force raises SystemExit(1)."""
        config = self._make_config({
            "pishock_1": {
                "provider": "pishock",
                "api_key": "test_key",
                "shockers": [],
            }
        })

        with (
            patch("pyshock.cli.commands.meta.get_config", return_value=config),
            patch("pyshock.cli.config.get_config", return_value=config),
            patch("pyshock.cli.commands.init_creds.console_err") as mock_err,
            pytest.raises(SystemExit) as exc_info,
        ):
            from pyshock.cli.commands.meta import auth

            auth(account_id="pishock_1")

        assert exc_info.value.code == 1
        mock_err.print.assert_called_once()
        assert "pishock_1" in mock_err.print.call_args.args[0]
        assert "already exists" in mock_err.print.call_args.args[0]

    def test_invalid_credentials_retry(
        self,
    ) -> None:
        """After 3 NotAuthorizedError failures, SystemExit(1) is raised."""
        config = self._make_config()
        fail_mock = self._make_api_mock(
            get_account_side_effect=NotAuthorizedError()
        )

        with (
            patch("pyshock.cli.commands.meta.get_config", return_value=config),
            patch("pyshock.cli.config.get_config", return_value=config),
            patch("pyshock.cli.commands.meta.terminal_check.isatty", return_value=False),
            patch(
                "pyshock.cli.commands.init_creds.prompt_pishock_credentials",
                return_value={"api_key": "bad_key"},
            ),
            patch("pyshock.cli.commands.meta.PiShockAPI", return_value=fail_mock),
            patch("pyshock.cli.commands.meta.console_err") as mock_err,
            pytest.raises(SystemExit) as exc_info,
        ):
            from pyshock.cli.commands.meta import auth

            auth(api_key="bad_key")

        assert exc_info.value.code == 1
        assert fail_mock.get_account.call_count == 3
        assert mock_err.print.call_count >= 3
        assert "Failed to authorize after 3 attempts" in str(mock_err.print.call_args)

    def test_tty_required_for_interactive(
        self,
    ) -> None:
        """isatty=False with no --pishock-key raises SystemExit(1)."""
        config = self._make_config()

        with (
            patch("pyshock.cli.commands.meta.get_config", return_value=config),
            patch("pyshock.cli.config.get_config", return_value=config),
            patch("pyshock.cli.commands.meta.terminal_check.isatty", return_value=False),
            patch(
                "pyshock.cli.commands.init_creds.prompt_pishock_credentials",
                side_effect=SystemExit(1),
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            from pyshock.cli.commands.meta import auth

            auth()

        assert exc_info.value.code == 1

    def test_env_variable_used(
        self,
    ) -> None:
        """PISHOCK_API_KEY env var is used when isatty=False and no --pishock-key."""
        config = self._make_config()
        api_mock = self._make_api_mock(list_shockers_return=[])

        with (
            patch("pyshock.cli.commands.meta.get_config", return_value=config),
            patch("pyshock.cli.config.get_config", return_value=config),
            patch("pyshock.cli.commands.meta.terminal_check.isatty", return_value=False),
            patch(
                "pyshock.cli.commands.init_creds.prompt_pishock_credentials",
                return_value={"api_key": "env_key"},
            ),
            patch("pyshock.cli.commands.meta.PiShockAPI", return_value=api_mock),
            patch.object(Config, "save"),
            patch.dict("os.environ", {"PISHOCK_API_KEY": "env_key"}, clear=False),
        ):
            from pyshock.cli.commands.meta import auth

            auth()

        assert "pishock_1" in config.accounts
        assert config.accounts["pishock_1"]["api_key"] == "env_key"
        api_mock.get_account.assert_called_once()

    def test_json_output(
        self,
    ) -> None:
        """json_mode=True outputs shocker JSON instead of rendering table."""
        config = self._make_config()
        api_mock = self._make_api_mock()

        with (
            patch("pyshock.cli.commands.meta.get_config", return_value=config),
            patch("pyshock.cli.config.get_config", return_value=config),
            patch("pyshock.cli.commands.meta.terminal_check.isatty", return_value=False),
            patch(
                "pyshock.cli.commands.init_creds.prompt_pishock_credentials",
                return_value={"api_key": "test_key"},
            ),
            patch("pyshock.cli.commands.meta.PiShockAPI", return_value=api_mock),
            patch("pyshock.cli.commands.meta.print_output") as mock_print_output,
            patch("pyshock.cli.commands.meta.render_shocker_table") as mock_render,
            patch("pyshock.cli.commands.meta.shocker_json", return_value={"shocker_id": "abc123"}),
            patch.object(Config, "save"),
        ):
            from pyshock.cli.commands.meta import auth

            auth(api_key="test_key", json_output=True)

        mock_render.assert_not_called()
        mock_print_output.assert_called_once()
        output = mock_print_output.call_args.args[0]
        assert "shockers" in output
        assert len(output["shockers"]) == 1
        assert output["shockers"][0]["shocker_id"] == "abc123"
