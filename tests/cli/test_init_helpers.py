"""Tests for init helper functions extracted from main.init."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from pyshock.cli.commands.init_creds import fix_account_prefix, resolve_account_id, resolve_provider
from pyshock.cli.config import Config


class TestResolveAccountId:
    """Tests for resolve_account_id."""

    def _make_config(self, accounts: dict | None = None) -> Config:
        config = Config()
        if accounts:
            config._data["accounts"] = accounts
        return config

    def test_provided_id_not_in_config(self) -> None:
        config = self._make_config()
        result = resolve_account_id(config, None, "my_account", force=False)
        assert result == "my_account"

    def test_provided_id_in_config_without_force_exits(self) -> None:
        config = self._make_config({"my_account": {"provider": "pishock"}})
        with pytest.raises(SystemExit):
            resolve_account_id(config, None, "my_account", force=False)

    def test_provided_id_in_config_with_force(self) -> None:
        config = self._make_config({"my_account": {"provider": "pishock"}})
        result = resolve_account_id(config, None, "my_account", force=True)
        assert result == "my_account"

    def test_auto_assign_no_existing_accounts(self) -> None:
        config = self._make_config()
        result = resolve_account_id(config, None, None, force=False)
        assert result == "pishock_1"

    def test_auto_assign_with_existing_pishock(self) -> None:
        config = self._make_config({"pishock_1": {"provider": "pishock"}})
        result = resolve_account_id(config, None, None, force=True)
        assert result == "pishock_2"

    def test_early_exit_when_user_declines(self) -> None:
        config = self._make_config({"pishock_1": {"provider": "pishock"}})
        with (
            patch("pyshock.cli.commands.init_creds.terminal_check") as mock_term,
            patch("rich.prompt.Confirm.ask", return_value=False),
        ):
            mock_term.isatty.return_value = True
            result = resolve_account_id(config, None, None, force=False)
        assert result is None

    def test_skips_prompt_when_no_terminal(self) -> None:
        config = self._make_config({"pishock_1": {"provider": "pishock"}})
        with (
            patch("pyshock.cli.commands.init_creds.terminal_check") as mock_term,
            patch("rich.prompt.Confirm.ask") as mock_confirm,
        ):
            mock_term.isatty.return_value = False
            result = resolve_account_id(config, None, None, force=False)
        assert result == "pishock_2"
        mock_confirm.assert_not_called()


class TestResolveProvider:
    """Tests for resolve_provider."""

    def test_always_returns_pishock(self) -> None:
        result = resolve_provider(None)
        assert result == "pishock"


class TestFixAccountPrefix:
    """Tests for fix_account_prefix."""

    def _make_config(self, accounts: dict | None = None) -> Config:
        config = Config()
        if accounts:
            config._data["accounts"] = accounts
        return config

    def test_user_provided_unchanged(self) -> None:
        config = self._make_config()
        result = fix_account_prefix(config, "my_custom_id", "pishock", user_provided_id=True)
        assert result == "my_custom_id"

    def test_already_correct_prefix(self) -> None:
        config = self._make_config()
        result = fix_account_prefix(config, "pishock_1", "pishock", user_provided_id=False)
        assert result == "pishock_1"

    def test_corrects_wrong_prefix(self) -> None:
        config = self._make_config()
        result = fix_account_prefix(config, "pishock_1", "pishock", user_provided_id=False)
        assert result == "pishock_1"
