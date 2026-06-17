"""Layer 2: Command execution tests for the code sub-app (add, delete, list).

Verifies that share code commands correctly wire up API calls and display
rendering through share_code helpers.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pyshock.cli.commands.code import add, delete, list_codes
from pyshock.cli.config import Config
from pyshock.cli.context import json_mode
from pyshock.errors import CliError
from pyshock.models.shocker import Shocker
from pyshock.pishockapi import PiShockAPI

shared_shocker = Shocker(
    shocker_id="shared123",
    name="Shared Shocker",
    can_shock=True,
    can_vibrate=True,
    can_beep=True,
    can_hold=True,
    max_intensity=100,
    max_duration=15000,
    is_v3=True,
    can_pause=True,
    share_code="ABC123",
    owned_by="other_user",
    share_id=1,
    owner_id=2,
    client_id=3,
)


class TestCodeAdd:
    """Tests for the code add command."""

    def test_add_share_code(
        self,
        mock_pishock_api: MagicMock,
    ) -> None:
        """Calling add with a valid code calls api.add_share_code."""
        with patch("pyshock.cli.commands.code.utils.get_api", return_value=mock_pishock_api):
            add("ABC123")

        mock_pishock_api.add_share_code.assert_called_once_with("ABC123")

    def test_add_empty_code(
        self,
        mock_pishock_api: MagicMock,
    ) -> None:
        """Calling add with an empty string raises CliError."""
        with patch("pyshock.cli.commands.code.utils.get_api", return_value=mock_pishock_api):
            with pytest.raises(CliError, match="Share code cannot be empty"):
                add("")


class TestCodeDelete:
    """Tests for the code delete command."""

    def test_delete_share_code(
        self,
        mock_pishock_api: MagicMock,
    ) -> None:
        """Calling delete with a code calls api.delete_share."""
        with patch("pyshock.cli.commands.code.utils.get_api", return_value=mock_pishock_api):
            delete("ABC123")

        mock_pishock_api.delete_share.assert_called_once_with("ABC123")


class TestCodeList:
    """Tests for the code list command."""

    def test_list_codes_for_account(
        self,
        mock_config_with_account: Config,
        mock_pishock_api: MagicMock,
    ) -> None:
        """List codes for a specific account calls code_list with shared shockers."""
        mock_pishock_api.list_shockers.return_value = [shared_shocker]

        with (
            patch(
                "pyshock.cli.commands.code.get_config",
                return_value=mock_config_with_account,
            ),
            patch(
                "pyshock.cli.commands.code.utils.get_api_for_account",
                return_value=mock_pishock_api,
            ),
            patch("pyshock.cli.commands.code.share_code.code_list") as mock_code_list,
            patch("pyshock.cli.commands.code.console.status"),
        ):
            list_codes(account_id="pishock_1")

        mock_code_list.assert_called_once_with(show_info=False, shockers=[shared_shocker])

    def test_list_codes_all_accounts(
        self,
        mock_config_with_account: Config,
        mock_pishock_api: MagicMock,
    ) -> None:
        """List codes without account_id processes all configured accounts."""
        mock_pishock_api.list_shockers.return_value = [shared_shocker]

        mock_api_2 = MagicMock(spec=PiShockAPI)
        mock_api_2.__enter__ = MagicMock(return_value=mock_api_2)
        mock_api_2.__exit__ = MagicMock(return_value=False)
        mock_api_2.list_shockers.return_value = [
            Shocker(
                shocker_id="shared456",
                name="Shared Shocker 2",
                can_shock=True,
                can_vibrate=True,
                can_beep=True,
                can_hold=True,
                max_intensity=100,
                max_duration=15000,
                is_v3=True,
                can_pause=True,
                share_code="DEF456",
                owned_by="other_user_2",
                share_id=4,
                owner_id=5,
                client_id=6,
            )
        ]

        mock_config_with_account._data["accounts"]["pishock_2"] = {
            "provider": "pishock",
            "api_key": "test_api_key_2",
            "shockers": [],
        }

        def api_side_effect(account_id: str) -> MagicMock:
            return mock_pishock_api if account_id == "pishock_1" else mock_api_2

        with (
            patch(
                "pyshock.cli.commands.code.get_config",
                return_value=mock_config_with_account,
            ),
            patch(
                "pyshock.cli.commands.code.utils.get_api_for_account",
                side_effect=api_side_effect,
            ),
            patch("pyshock.cli.commands.code.share_code.code_list") as mock_code_list,
            patch("pyshock.cli.commands.code.console.status"),
        ):
            list_codes()

        assert mock_code_list.call_count == 2

    def test_list_codes_with_show_info(
        self,
        mock_config_with_account: Config,
        mock_pishock_api: MagicMock,
    ) -> None:
        """Passing show_info=True forwards the flag to code_list."""
        mock_pishock_api.list_shockers.return_value = [shared_shocker]

        with (
            patch(
                "pyshock.cli.commands.code.get_config",
                return_value=mock_config_with_account,
            ),
            patch(
                "pyshock.cli.commands.code.utils.get_api_for_account",
                return_value=mock_pishock_api,
            ),
            patch("pyshock.cli.commands.code.share_code.code_list") as mock_code_list,
            patch("pyshock.cli.commands.code.console.status"),
        ):
            list_codes(show_info=True)

        mock_code_list.assert_called_once_with(show_info=True, shockers=[shared_shocker])

    def test_json_output(
        self,
        mock_config_with_account: Config,
        mock_pishock_api: MagicMock,
    ) -> None:
        """JSON mode outputs a list of shocker JSON dicts via print_output."""
        mock_pishock_api.list_shockers.return_value = [shared_shocker]

        with (
            patch(
                "pyshock.cli.commands.code.get_config",
                return_value=mock_config_with_account,
            ),
            patch(
                "pyshock.cli.commands.code.utils.get_api_for_account",
                return_value=mock_pishock_api,
            ),
            patch("pyshock.cli.commands.code.print_output") as mock_print_output,
            patch("pyshock.cli.commands.code.console.status"),
        ):
            json_mode.set(True)
            list_codes(account_id="pishock_1")

        mock_print_output.assert_called_once()
        output = mock_print_output.call_args.args[0]
        assert isinstance(output, list)
        assert len(output) == 1
        assert output[0]["shocker_id"] == "shared123"
