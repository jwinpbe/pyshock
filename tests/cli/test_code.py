"""Layer 2: Command execution tests for the code sub-app (add, delete, list).

Verifies that share code commands correctly wire up API calls and display
rendering through share_code helpers.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pyshock.cli.commands.code import add, delete, list_codes
from pyshock.cli.context import json_mode
from pyshock.cli.utils import Session
from pyshock.errors import CliError
from pyshock.models.shocker import Shocker
from pyshock.openshockapi import OpenShockAPI

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
        add("ABC123", session=Session(api=mock_pishock_api, account_id="pishock_1", provider="pishock"))

        mock_pishock_api.add_share_code.assert_called_once_with("ABC123")

    def test_add_empty_code(
        self,
        mock_pishock_api: MagicMock,
    ) -> None:
        """Calling add with an empty string raises CliError."""
        with pytest.raises(CliError, match="Share code cannot be empty"):
            add("", session=Session(api=mock_pishock_api, account_id="pishock_1", provider="pishock"))

    def test_add_openshock_directs_user_to_web_interface(self) -> None:
        api = MagicMock(spec=OpenShockAPI)
        with pytest.raises(CliError, match="OpenShock web interface"):
            add("ABC123", session=Session(api=api, account_id="pishock_1", provider="openshock"))


class TestCodeDelete:
    """Tests for the code delete command."""

    def test_delete_share_code(
        self,
        mock_pishock_api: MagicMock,
    ) -> None:
        """Calling delete resolves the code and deletes the matching share id."""
        mock_pishock_api.get_shocker_by_share_code.return_value = shared_shocker
        delete("ABC123", session=Session(api=mock_pishock_api, account_id="pishock_1", provider="pishock"))

        mock_pishock_api.get_shocker_by_share_code.assert_called_once_with("ABC123")
        mock_pishock_api.delete_share.assert_called_once_with(1)

    def test_delete_openshock_directs_user_to_web_interface(self) -> None:
        api = MagicMock(spec=OpenShockAPI)
        with pytest.raises(CliError, match="OpenShock web interface"):
            delete("ABC123", session=Session(api=api, account_id="pishock_1", provider="openshock"))


class TestCodeList:
    """Tests for the code list command."""

    def test_list_codes_uses_selected_account(self, mock_pishock_api: MagicMock) -> None:
        mock_pishock_api.list_shockers.return_value = [shared_shocker]

        with (
            patch("pyshock.cli.commands.code.share_code.code_list") as mock_code_list,
            patch("pyshock.cli.commands.code.console.status"),
        ):
            list_codes(session=Session(api=mock_pishock_api, account_id="pishock_1", provider="pishock"))

        mock_code_list.assert_called_once_with(show_info=False, shockers=[shared_shocker])

    def test_list_codes_openshock_directs_user_to_web_interface(self) -> None:
        api = MagicMock(spec=OpenShockAPI)
        with pytest.raises(CliError, match="OpenShock web interface"):
            list_codes(session=Session(api=api, account_id="pishock_1", provider="openshock"))

    def test_list_codes_with_show_info(self, mock_pishock_api: MagicMock) -> None:
        """Passing show_info=True forwards the flag to code_list."""
        mock_pishock_api.list_shockers.return_value = [shared_shocker]

        with (
            patch("pyshock.cli.commands.code.share_code.code_list") as mock_code_list,
            patch("pyshock.cli.commands.code.console.status"),
        ):
            list_codes(
                show_info=True, session=Session(api=mock_pishock_api, account_id="pishock_1", provider="pishock")
            )

        mock_code_list.assert_called_once_with(show_info=True, shockers=[shared_shocker])

    def test_json_output(self, mock_pishock_api: MagicMock) -> None:
        """JSON mode outputs a list of shocker JSON dicts via print_output."""
        mock_pishock_api.list_shockers.return_value = [shared_shocker]

        with (
            patch("pyshock.cli.commands.code.print_output") as mock_print_output,
            patch("pyshock.cli.commands.code.console.status"),
        ):
            json_mode.set(True)
            list_codes(session=Session(api=mock_pishock_api, account_id="pishock_1", provider="pishock"))

        mock_print_output.assert_called_once()
        output = mock_print_output.call_args.args[0]
        assert isinstance(output, list)
        assert len(output) == 1
        assert output[0]["shocker_id"] == "shared123"
