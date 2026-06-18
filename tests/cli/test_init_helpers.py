"""Tests for init helper functions extracted from main.init."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from pyshock.cli.commands.init_creds import (
    fix_account_prefix,
    prompt_credentials,
    resolve_account_id,
    resolve_credential,
    resolve_provider,
)
from pyshock.cli.config import Config
from pyshock.errors import CliError

PISHOCK_UUID = "550e8400-e29b-41d4-a716-446655440000"
OPENSHOCK_TOKEN = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ012345678901"  # 64 chars


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

    def test_auto_assign_openshock_prefix(self) -> None:
        config = self._make_config()
        result = resolve_account_id(config, "openshock", None, force=True)
        assert result == "openshock_1"

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
    """Tests for resolve_provider shape detection."""

    def test_resolves_pishock_from_uuid(self) -> None:
        assert resolve_provider(PISHOCK_UUID) == "pishock"

    def test_resolves_openshock_from_base62(self) -> None:
        assert resolve_provider(OPENSHOCK_TOKEN) == "openshock"

    def test_rejects_unrecognized_format(self) -> None:
        with pytest.raises(CliError):
            resolve_provider("not-a-valid-format")

    def test_uuid_case_insensitive(self) -> None:
        assert resolve_provider(PISHOCK_UUID.upper()) == "pishock"

    def test_rejects_short_base62(self) -> None:
        with pytest.raises(CliError):
            resolve_provider("abc")

    def test_rejects_base64_with_special_chars(self) -> None:
        with pytest.raises(CliError):
            resolve_provider("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+/abcd")


class TestResolveCredential:
    """Tests for resolve_credential."""

    def test_uses_key_flag(self) -> None:
        cred, prov = resolve_credential(PISHOCK_UUID)
        assert cred == PISHOCK_UUID
        assert prov == "pishock"

    def test_uses_pishock_env_var(self) -> None:
        with patch.dict("os.environ", {"PISHOCK_API_KEY": PISHOCK_UUID}, clear=False):
            cred, prov = resolve_credential(None)
        assert cred == PISHOCK_UUID
        assert prov == "pishock"

    def test_uses_openshock_env_var(self) -> None:
        with patch.dict("os.environ", {"OPENSHOCK_API_TOKEN": OPENSHOCK_TOKEN}, clear=False):
            cred, prov = resolve_credential(None)
        assert cred == OPENSHOCK_TOKEN
        assert prov == "openshock"

    def test_both_env_vars_raises(self) -> None:
        with patch.dict(
            "os.environ",
            {"PISHOCK_API_KEY": PISHOCK_UUID, "OPENSHOCK_API_TOKEN": OPENSHOCK_TOKEN},
            clear=False,
        ):
            with pytest.raises(CliError):
                resolve_credential(None)

    def test_returns_none_when_nothing_set(self) -> None:
        cred, prov = resolve_credential(None)
        assert cred is None
        assert prov is None

    def test_skip_env_bypasses_env_vars(self) -> None:
        with patch.dict("os.environ", {"PISHOCK_API_KEY": PISHOCK_UUID}, clear=False):
            cred, prov = resolve_credential(None, skip_env=True)
        assert cred is None
        assert prov is None

    def test_key_flag_bypasses_env_vars(self) -> None:
        with patch.dict("os.environ", {"PISHOCK_API_KEY": "different"}, clear=False):
            cred, prov = resolve_credential(PISHOCK_UUID)
        assert cred == PISHOCK_UUID
        assert prov == "pishock"


class TestPromptCredentials:
    """Tests for prompt_credentials."""

    def test_prompts_and_validates_shape(self) -> None:
        with (
            patch("rich.prompt.Prompt.ask", return_value=PISHOCK_UUID),
        ):
            cred, prov = prompt_credentials(is_tty=True)
        assert cred == PISHOCK_UUID
        assert prov == "pishock"

    def test_reprompts_on_bad_shape(self) -> None:
        with patch("rich.prompt.Prompt.ask", side_effect=["bad", PISHOCK_UUID]):
            cred, prov = prompt_credentials(is_tty=True)
        assert cred == PISHOCK_UUID
        assert prov == "pishock"

    def test_exits_after_three_failures(self) -> None:
        with (
            patch("rich.prompt.Prompt.ask", return_value="bad"),
            pytest.raises(SystemExit) as exc_info,
        ):
            prompt_credentials(is_tty=True)
        assert exc_info.value.code == 1

    def test_exits_without_tty(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            prompt_credentials(is_tty=False)
        assert exc_info.value.code == 1


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
