"""Unit tests for share_code CLI helpers (code_add, code_delete, code_list).

Verifies input validation, API call wiring, and display dispatch for the
share-code sub-commands without going through the cyclopts app layer.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pyshock.cli.share_code import code_add, code_delete, code_list
from pyshock.errors import CliError
from pyshock.models.shocker import Shocker

_SHARED_SHOCKER = Shocker(
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

_NON_SHARED_SHOCKER = Shocker(
    shocker_id="owned456",
    name="My Shocker",
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


class TestCodeAdd:
    """Tests for code_add."""

    def test_add_calls_api_and_prints_success(self, mock_pishock_api: MagicMock) -> None:
        """A valid code calls api.add_share_code and prints success."""
        with patch("pyshock.cli.share_code.console") as mock_console:
            code_add("ABC123", mock_pishock_api)

        mock_pishock_api.add_share_code.assert_called_once_with("ABC123")
        mock_console.print.assert_called_once()
        assert "added successfully" in mock_console.print.call_args.args[0]

    def test_add_empty_raises_cli_error(self, mock_pishock_api: MagicMock) -> None:
        """An empty string raises CliError."""
        with pytest.raises(CliError, match="Share code cannot be empty"):
            code_add("", mock_pishock_api)

        mock_pishock_api.add_share_code.assert_not_called()

    def test_add_whitespace_raises_cli_error(self, mock_pishock_api: MagicMock) -> None:
        """A whitespace-only string raises CliError."""
        with pytest.raises(CliError, match="Share code cannot be empty"):
            code_add("  ", mock_pishock_api)

        mock_pishock_api.add_share_code.assert_not_called()


class TestCodeDelete:
    """Tests for code_delete."""

    def test_delete_calls_api_and_prints_success(self, mock_pishock_api: MagicMock) -> None:
        """A valid code resolves and deletes its numeric share id."""
        mock_pishock_api.get_shocker_by_share_code.return_value = _SHARED_SHOCKER
        with patch("pyshock.cli.share_code.console") as mock_console:
            code_delete("ABC123", mock_pishock_api)

        mock_pishock_api.get_shocker_by_share_code.assert_called_once_with("ABC123")
        mock_pishock_api.delete_share.assert_called_once_with(1)
        mock_console.print.assert_called_once()
        assert "deleted successfully" in mock_console.print.call_args.args[0]

    def test_delete_missing_share_id_raises(self, mock_pishock_api: MagicMock) -> None:
        mock_pishock_api.get_shocker_by_share_code.return_value = _NON_SHARED_SHOCKER
        with pytest.raises(CliError, match="did not return an id"):
            code_delete("ABC123", mock_pishock_api)

        mock_pishock_api.delete_share.assert_not_called()


class TestCodeList:
    """Tests for code_list."""

    def test_no_shared_shockers(self) -> None:
        """An empty shocker list prints 'No share codes found'."""
        with patch("pyshock.cli.share_code.console") as mock_console:
            code_list(show_info=False, shockers=[])

        mock_console.print.assert_called_once_with("No share codes found.")

    def test_compact_table(self) -> None:
        """A non-empty shared list with show_info=False renders compact table."""
        with (
            patch("pyshock.cli.share_code.render_compact_code_table") as mock_compact,
            patch("pyshock.cli.share_code.render_full_code_table"),
            patch("pyshock.cli.share_code.console"),
        ):
            code_list(show_info=False, shockers=[_SHARED_SHOCKER])

        mock_compact.assert_called_once_with([_SHARED_SHOCKER])

    def test_full_table(self) -> None:
        """A non-empty shared list with show_info=True renders full table."""
        with (
            patch("pyshock.cli.share_code.render_compact_code_table"),
            patch("pyshock.cli.share_code.render_full_code_table") as mock_full,
            patch("pyshock.cli.share_code.console"),
        ):
            code_list(show_info=True, shockers=[_SHARED_SHOCKER])

        mock_full.assert_called_once_with([_SHARED_SHOCKER])

    def test_filters_non_shared(self) -> None:
        """Only shared shockers are passed to the render function."""
        shockers = [_SHARED_SHOCKER, _NON_SHARED_SHOCKER]
        with (
            patch("pyshock.cli.share_code.render_compact_code_table") as mock_compact,
            patch("pyshock.cli.share_code.render_full_code_table"),
            patch("pyshock.cli.share_code.console"),
        ):
            code_list(show_info=False, shockers=shockers)

        mock_compact.assert_called_once()
        assert mock_compact.call_args.args[0] == [_SHARED_SHOCKER]
