"""Tests for configuration management."""

from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest

from pyshock.cli.config import Config, get_config, reset_config_cache


@pytest.fixture(autouse=True)
def _clean_config() -> Generator[None]:
    reset_config_cache()
    yield
    reset_config_cache()


class TestConfigLoad:
    def test_load_missing_file(self) -> None:
        config = Config()
        with patch.object(config, "_path") as mock_path:
            mock_path.exists.return_value = False
            config.load()
        assert config._data == {}

    def test_load_corrupt_json(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.json"
        config_path.write_text("not valid json")
        config = Config()
        config._path = config_path
        config.load()
        assert config._data == {}

    def test_load_os_error(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.json"
        config_path.touch()
        with patch.object(Path, "read_text", side_effect=OSError("permission denied")):
            config = Config()
            config._path = config_path
            config.load()
        assert config._data == {}

    def test_load_valid_new_format(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "accounts": {
                        "pishock_1": {
                            "provider": "pishock",
                            "api_key": "key123",
                            "shockers": [{"shocker_id": "abc-123", "name": "Test"}],
                        }
                    },
                    "default_shocker_id": "abc-123",
                }
            )
        )
        config = Config()
        config._path = config_path
        config.load()
        account = config.get_account("pishock_1")
        assert account is not None
        assert account["api_key"] == "key123"
        assert config.default_shocker_id == "abc-123"
        assert config.shocker_index["abc-123"] == "pishock_1"

    def test_load_rebuilds_shocker_index(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "accounts": {
                        "pishock_1": {
                            "provider": "pishock",
                            "api_key": "key123",
                            "shockers": [
                                {"shocker_id": "s1", "name": "A"},
                                {"shocker_id": "s2", "name": "B"},
                            ],
                        },
                        "openshock_1": {
                            "provider": "openshock",
                            "api_token": "tok",
                            "shockers": [{"shocker_id": "s3", "name": "C"}],
                        },
                    }
                }
            )
        )
        config = Config()
        config._path = config_path
        config.load()
        assert config.shocker_index == {"s1": "pishock_1", "s2": "pishock_1", "s3": "openshock_1"}

    def test_load_clears_stale_default(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "accounts": {
                        "pishock_1": {
                            "provider": "pishock",
                            "shockers": [{"shocker_id": "s1", "name": "A"}],
                        }
                    },
                    "default_shocker_id": "nonexistent",
                }
            )
        )
        config = Config()
        config._path = config_path
        config.load()
        assert config.default_shocker_id is None


class TestConfigSave:
    def test_save_creates_directory(self, tmp_path: Path) -> None:
        config_path = tmp_path / "subdir" / "config.json"
        config = Config()
        config._path = config_path
        config._data = {"accounts": {}}
        config.save()
        assert config_path.exists()

    def test_save_os_error(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.json"
        config = Config()
        config._path = config_path
        config._data = {"accounts": {}}
        with patch.object(Path, "write_text", side_effect=OSError("disk full")):
            config.save()

    def test_save_round_trip(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.json"
        config = Config()
        config._path = config_path
        config.add_account("pishock_1", "pishock", api_key="key123")
        config.save()

        config2 = Config()
        config2._path = config_path
        config2.load()
        account = config2.get_account("pishock_1")
        assert account is not None
        assert account["api_key"] == "key123"


class TestConfigProperties:
    def test_is_configured_empty(self) -> None:
        config = Config()
        assert not config.is_configured

    def test_is_configured_with_accounts(self) -> None:
        config = Config()
        config.add_account("pishock_1", "pishock", api_key="key123")
        assert config.is_configured

    def test_default_shocker_id_getter_setter(self) -> None:
        config = Config()
        assert config.default_shocker_id is None
        config.add_account("pishock_1", "pishock", api_key="key123")
        config.refresh_account_shockers("pishock_1", [{"shocker_id": "abc-123", "name": "Test"}])
        config.default_shocker_id = "abc-123"
        assert config.default_shocker_id == "abc-123"
        config.default_shocker_id = None
        assert config.default_shocker_id is None

    def test_confirmations_auto_created(self) -> None:
        config = Config()
        assert config.confirmation_enabled("shock") is True
        assert "confirmations" in config._data

    def test_confirmation_enabled_default(self) -> None:
        config = Config()
        assert config.confirmation_enabled("shock") is True
        assert config.confirmation_enabled("beep") is True

    def test_confirmations_set_and_read(self) -> None:
        config = Config()
        config.set_confirmation("shock", enabled=False)
        assert config.confirmation_enabled("shock") is False
        assert config.confirmation_enabled("beep") is True

    def test_confirmations_clear(self) -> None:
        config = Config()
        config.set_confirmation("shock", enabled=False)
        config.set_confirmation("beep", enabled=False)
        config.confirmations.clear()
        assert config.confirmation_enabled("shock") is True


class TestMultiAccount:
    def test_add_account_pishock(self) -> None:
        config = Config()
        config.add_account("pishock_1", "pishock", api_key="key123")
        account = config.get_account("pishock_1")
        assert account is not None
        assert account["provider"] == "pishock"
        assert account["api_key"] == "key123"

    def test_add_account_openshock_token(self) -> None:
        config = Config()
        config.add_account("openshock_1", "openshock", api_token="tok123")
        account = config.get_account("openshock_1")
        assert account is not None
        assert account["provider"] == "openshock"
        assert account["api_token"] == "tok123"

    def test_add_account_openshock_cookie(self) -> None:
        config = Config()
        config.add_account(
            "openshock_1",
            "openshock",
            session_cookie="cookie123",
            browser_type="firefox",
        )
        account = config.get_account("openshock_1")
        assert account is not None
        assert account["session_cookie"] == "cookie123"
        assert account["browser_type"] == "firefox"

    def test_add_account_duplicate_raises(self) -> None:
        config = Config()
        config.add_account("pishock_1", "pishock", api_key="key123")
        with pytest.raises(ValueError, match="already exists"):
            config.add_account("pishock_1", "pishock", api_key="other")

    def test_add_account_ignores_none_values(self) -> None:
        config = Config()
        config.add_account(
            "openshock_1",
            "openshock",
            api_token="tok",
            browser_type=None,
            browser_cookie_path=None,
        )
        account = config.get_account("openshock_1")
        assert account is not None
        assert "browser_type" not in account
        assert "browser_cookie_path" not in account

    def test_remove_account(self) -> None:
        config = Config()
        config.add_account("pishock_1", "pishock", api_key="key123")
        config.add_account("openshock_1", "openshock", api_token="tok")
        config.remove_account("pishock_1")
        assert config.get_account("pishock_1") is None
        assert config.get_account("openshock_1") is not None

    def test_remove_account_nonexistent(self) -> None:
        config = Config()
        config.remove_account("nonexistent")
        assert config.accounts == {}

    def test_remove_account_clears_default(self) -> None:
        config = Config()
        config.add_account("pishock_1", "pishock", api_key="key123")
        config.refresh_account_shockers("pishock_1", [{"shocker_id": "s1", "name": "A"}])
        config.default_shocker_id = "s1"
        config.remove_account("pishock_1")
        assert config.default_shocker_id is None

    def test_remove_account_cleans_shocker_index(self) -> None:
        config = Config()
        config.add_account("pishock_1", "pishock", api_key="key123")
        config.add_account("openshock_1", "openshock", api_token="tok")
        config.refresh_account_shockers("pishock_1", [{"shocker_id": "s1", "name": "A"}])
        config.refresh_account_shockers("openshock_1", [{"shocker_id": "s2", "name": "B"}])
        config.remove_account("pishock_1")
        assert config.shocker_index.get("s1") is None
        assert config.shocker_index.get("s2") == "openshock_1"

    def test_get_account_for_shocker_hit(self) -> None:
        config = Config()
        config.add_account("pishock_1", "pishock", api_key="key123")
        config.refresh_account_shockers("pishock_1", [{"shocker_id": "s1", "name": "A"}])
        account = config.get_account_for_shocker("s1")
        assert account is not None
        assert account["api_key"] == "key123"

    def test_get_account_for_shocker_miss(self) -> None:
        config = Config()
        config.add_account("pishock_1", "pishock", api_key="key123")
        account = config.get_account_for_shocker("nonexistent")
        assert account is None

    def test_update_shocker_index(self) -> None:
        config = Config()
        config.add_account("pishock_1", "pishock", api_key="key123")
        config.add_account("openshock_1", "openshock", api_token="tok")
        config._data["accounts"]["pishock_1"]["shockers"] = [
            {"shocker_id": "s1", "name": "A"},
            {"shocker_id": "s2", "name": "B"},
        ]
        config._data["accounts"]["openshock_1"]["shockers"] = [{"shocker_id": "s3", "name": "C"}]
        assert config.shocker_index == {"s1": "pishock_1", "s2": "pishock_1", "s3": "openshock_1"}

    def test_refresh_account_shockers(self) -> None:
        config = Config()
        config.add_account("pishock_1", "pishock", api_key="key123")
        config.refresh_account_shockers(
            "pishock_1",
            [{"shocker_id": "s1", "name": "A"}, {"shocker_id": "s2", "name": "B"}],
        )
        account = config.get_account("pishock_1")
        assert account is not None
        assert len(account["shockers"]) == 2
        assert config.shocker_index["s1"] == "pishock_1"
        assert config.shocker_index["s2"] == "pishock_1"

    def test_refresh_account_shockers_nonexistent(self) -> None:
        config = Config()
        config.refresh_account_shockers("nonexistent", [{"shocker_id": "s1"}])
        assert config.accounts == {}

    def test_confirmation_enabled_global(self) -> None:
        config = Config()
        assert config.confirmation_enabled("shock") is True
        config.set_confirmation("shock", enabled=False)
        assert config.confirmation_enabled("shock") is False

    def test_set_confirmation_stores_flat(self) -> None:
        config = Config()
        config.set_confirmation("shock", enabled=False)
        config.set_confirmation("vibrate", enabled=True)
        raw = config.confirmations
        assert raw == {"shock": False, "vibrate": True}


class TestGetConfig:
    def test_returns_cached_instance(self) -> None:
        c1 = get_config()
        c2 = get_config()
        assert c1 is c2

    def test_reset_forces_reload(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "accounts": {
                        "pishock_1": {
                            "provider": "pishock",
                            "api_key": "key123",
                            "shockers": [],
                        }
                    }
                }
            )
        )

        config = Config()
        config._path = config_path

        with patch("pyshock.cli.config.Config") as mock_config:
            mock_config.return_value = config
            reset_config_cache()
            result = get_config()
        account = result.get_account("pishock_1")
        assert account is not None
        assert account["api_key"] == "key123"
