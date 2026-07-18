"""Tests for multi-account utils."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import patch

import pytest

from pyshock.cli import utils
from pyshock.cli.config import Config, reset_config_cache
from pyshock.errors import CliError


@pytest.fixture(autouse=True)
def _clean_config() -> Generator[None]:
    reset_config_cache()
    yield
    reset_config_cache()


def _mock_config_with_accounts() -> Config:
    config = Config()
    config.add_account("pishock_1", "pishock", api_key="key123")
    config.add_account("pishock_2", "pishock", api_key="key456")
    config.refresh_account_shockers(
        "pishock_1",
        [{"shocker_id": "s1", "name": "A"}, {"shocker_id": "s2", "name": "B"}],
    )
    config.refresh_account_shockers(
        "pishock_2",
        [{"shocker_id": "s3", "name": "C"}],
    )
    config.default_shocker_id = "s1"
    return config


class TestResolveAccount:
    def test_resolve_by_account_id(self) -> None:
        config = _mock_config_with_accounts()
        with patch("pyshock.cli.utils.get_config", return_value=config):
            result = utils.resolve_account(account_id="pishock_1")
        assert result == "pishock_1"

    def test_resolve_by_shocker_id(self) -> None:
        config = _mock_config_with_accounts()
        with patch("pyshock.cli.utils.get_config", return_value=config):
            result = utils.resolve_account(shocker_id="s2")
        assert result == "pishock_1"

    def test_resolve_by_default_shocker_id(self) -> None:
        config = _mock_config_with_accounts()
        with patch("pyshock.cli.utils.get_config", return_value=config):
            result = utils.resolve_account()
        assert result == "pishock_1"

    def test_resolve_missing_account_raises(self) -> None:
        config = _mock_config_with_accounts()
        with patch("pyshock.cli.utils.get_config", return_value=config):
            with pytest.raises(CliError, match="not found"):
                utils.resolve_account(account_id="nonexistent")

    def test_resolve_no_account_raises(self) -> None:
        config = Config()
        with patch("pyshock.cli.utils.get_config", return_value=config):
            with pytest.raises(CliError, match="No account resolved"):
                utils.resolve_account()


class TestGetApiForAccount:
    def test_get_pishock_api(self) -> None:
        config = _mock_config_with_accounts()
        with patch("pyshock.cli.utils.get_config", return_value=config):
            api = utils.get_api_for_account("pishock_1")
        from pyshock.pishockapi import PiShockAPI

        assert isinstance(api, PiShockAPI)
        api.close()

    def test_get_missing_account_raises(self) -> None:
        config = Config()
        with patch("pyshock.cli.utils.get_config", return_value=config):
            with pytest.raises(CliError, match="not found"):
                utils.get_api_for_account("nonexistent")


class TestSetApiClientForAccount:
    def test_set_api_client_for_account(self) -> None:
        config = _mock_config_with_accounts()
        with patch("pyshock.cli.utils.get_config", return_value=config):
            client = utils.get_api_for_account("pishock_1")
            utils.set_api_client(client)
            api = utils.get_api()
        from pyshock.pishockapi import PiShockAPI

        assert isinstance(api, PiShockAPI)
        api.close()


class TestConfirmOperation:
    def test_confirm_skips_when_disabled(self) -> None:
        config = _mock_config_with_accounts()
        config.set_confirmation("shock", enabled=False)
        with patch("pyshock.cli.utils.get_config", return_value=config):
            utils.confirm_operation("shock")  # Should not prompt

    def test_confirm_prompts_when_enabled(self) -> None:
        config = _mock_config_with_accounts()
        with (
            patch("pyshock.cli.utils.get_config", return_value=config),
            patch("rich.prompt.Prompt.ask", return_value="n"),
        ):
            with pytest.raises(SystemExit):
                utils.confirm_operation("shock")
