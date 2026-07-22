"""Tests for CLI utility functions in pyshock.cli.utils."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pyshock.cli.config import Config
from pyshock.cli.utils import (
    Session,
    confirm_operation,
    get_session_for_account,
    resolve_shocker_id,
    send_operation,
    validate_duration,
)
from pyshock.errors import CliError
from pyshock.models.operation import ShockerOperation
from pyshock.models.shocker import Shocker
from pyshock.openshockapi import OpenShockAPI
from pyshock.pishockapi import PiShockAPI


class TestValidateDuration:
    """Tests for duration validation and normalisation."""

    def test_seconds_to_milliseconds(self) -> None:
        """Durations below 16 are treated as seconds and converted to ms."""
        assert validate_duration(5, "pishock") == 5000

    def test_milliseconds_passthrough(self) -> None:
        """Durations at or above 16 are treated as milliseconds directly."""
        assert validate_duration(5000, "pishock") == 5000


class TestValidateDurationRange:
    """Tests for duration validation."""

    def test_valid(self) -> None:
        """Valid duration passes through unchanged."""
        assert validate_duration(5000, "pishock") == 5000

    def test_duration_too_low(self) -> None:
        """Duration below minimum raises CliError."""
        with pytest.raises(CliError):
            validate_duration(0.015, "pishock")

    def test_duration_too_high(self) -> None:
        """Duration above maximum raises CliError."""
        with pytest.raises(CliError):
            validate_duration(20000, "pishock")


class TestResolveShockerId:
    """Tests for shocker ID resolution logic."""

    def test_uses_default(self) -> None:
        """Config default_shocker_id is returned when set."""
        config = Config()
        config._data = {"default_shocker_id": "abc123"}
        with patch("pyshock.cli.utils.get_config", return_value=config):
            assert resolve_shocker_id(MagicMock()) == "abc123"

    def test_single_shocker(self) -> None:
        """When no default, a single shocker from API is returned."""
        config = Config()
        config._data = {}
        api = MagicMock()
        api.list_shockers.return_value = [
            Shocker(
                shocker_id="only_one",
                name="Solo",
                can_shock=True,
                can_vibrate=True,
                can_beep=True,
                can_hold=True,
                max_intensity=100,
                max_duration=15000,
            )
        ]
        with patch("pyshock.cli.utils.get_config", return_value=config):
            assert resolve_shocker_id(api) == "only_one"

    def test_multiple_raises(self) -> None:
        """Multiple shockers with no default raises CliError."""
        config = Config()
        config._data = {}
        api = MagicMock()
        api.list_shockers.return_value = [
            Shocker(
                shocker_id="first",
                name="One",
                can_shock=True,
                can_vibrate=True,
                can_beep=True,
                can_hold=True,
                max_intensity=100,
                max_duration=15000,
            ),
            Shocker(
                shocker_id="second",
                name="Two",
                can_shock=True,
                can_vibrate=True,
                can_beep=True,
                can_hold=True,
                max_intensity=100,
                max_duration=15000,
            ),
        ]
        with patch("pyshock.cli.utils.get_config", return_value=config):
            with pytest.raises(CliError):
                resolve_shocker_id(api)


class TestSendOperation:
    """Tests for the send_operation function."""

    def test_explicit_shocker(
        self,
        mock_pishock_api: MagicMock,
        mock_config: Config,
    ) -> None:
        """When shocker_id is provided, it is used directly."""
        session = Session(api=mock_pishock_api, account_id="pishock_1", provider="pishock")
        with (
            patch("pyshock.cli.utils.get_config", return_value=mock_config),
            patch("pyshock.cli.utils.resolve_shocker_id"),
            patch("pyshock.cli.utils.confirm_operation"),
            patch("pyshock.cli.utils.json_mode", MagicMock(get=lambda: False)),
            patch("pyshock.cli.display.render_operation_result"),
        ):
            send_operation(session, "abc123", ShockerOperation.SHOCK, 5000, 50)

        mock_pishock_api.operate_shocker.assert_called_once_with(
            shocker="abc123",
            operation=ShockerOperation.SHOCK,
            duration=5000,
            intensity=50,
        )

    def test_resolved_shocker(
        self,
        mock_pishock_api: MagicMock,
        mock_config: Config,
    ) -> None:
        """When shocker_id is None, resolve_shocker_id provides the target."""
        session = Session(api=mock_pishock_api, account_id="pishock_1", provider="pishock")
        with (
            patch("pyshock.cli.utils.get_config", return_value=mock_config),
            patch("pyshock.cli.utils.resolve_shocker_id", return_value="def456"),
            patch("pyshock.cli.utils.confirm_operation"),
            patch("pyshock.cli.utils.json_mode", MagicMock(get=lambda: False)),
            patch("pyshock.cli.display.render_operation_result"),
        ):
            send_operation(session, None, ShockerOperation.SHOCK, 5000, 50)

        mock_pishock_api.operate_shocker.assert_called_once_with(
            shocker="def456",
            operation=ShockerOperation.SHOCK,
            duration=5000,
            intensity=50,
        )


class TestConfirmOperation:
    """Tests for the confirm_operation function."""

    def test_disabled_returns(self) -> None:
        """When confirmations are disabled, confirm_operation returns without error."""
        config = Config()
        config._data = {
            "confirmations": {"shock": False, "vibrate": False, "beep": False},
        }
        with patch("pyshock.cli.utils.get_config", return_value=config):
            confirm_operation("shock")

    def test_enabled_declined(self) -> None:
        """When confirmation is enabled and user declines, SystemExit(0) is raised."""
        config = Config()
        config._data = {
            "confirmations": {"shock": True, "vibrate": False, "beep": False},
        }
        mock_prompt = MagicMock()
        mock_prompt.lower.side_effect = SystemExit(0)
        with (
            patch("pyshock.cli.utils.get_config", return_value=config),
            patch("rich.prompt.Prompt.ask", return_value=mock_prompt),
        ):
            with pytest.raises(SystemExit) as exc_info:
                confirm_operation("shock")
            assert exc_info.value.code == 0


class TestGetSessionForAccount:
    """Tests for get_session_for_account."""

    def _make_config(self, accounts: dict) -> Config:
        config = Config()
        config._data["accounts"] = accounts
        return config

    def test_get_pishock_api(self) -> None:
        """PiShock account returns Session with PiShockAPI instance."""
        config = self._make_config({
            "pishock_1": {"provider": "pishock", "api_key": "test_key"},
        })
        with patch("pyshock.cli.utils.get_config", return_value=config):
            session = get_session_for_account("pishock_1")
        assert isinstance(session.api, PiShockAPI)
        assert session.provider == "pishock"
        assert session.account_id == "pishock_1"
        session.api.close()

    def test_get_openshock_api(self) -> None:
        """OpenShock account returns Session with OpenShockAPI instance."""
        config = self._make_config({
            "openshock_1": {"provider": "openshock", "api_token": "test_token"},
        })
        with patch("pyshock.cli.utils.get_config", return_value=config):
            session = get_session_for_account("openshock_1")
        assert isinstance(session.api, OpenShockAPI)
        assert session.provider == "openshock"
        assert session.account_id == "openshock_1"
        session.api.close()

    def test_legacy_openshock_cookie_account_requires_reauthentication(self) -> None:
        config = self._make_config({
            "openshock_1": {"provider": "openshock", "session_cookie": "obsolete"},
        })
        with (
            patch("pyshock.cli.utils.get_config", return_value=config),
            pytest.raises(CliError, match=r"requires an API token.*Re-authenticate"),
        ):
            get_session_for_account("openshock_1")

    def test_unknown_provider_raises(self) -> None:
        """Unknown provider raises CliError."""
        config = self._make_config({
            "weird_1": {"provider": "weird"},
        })
        with (
            patch("pyshock.cli.utils.get_config", return_value=config),
            pytest.raises(CliError, match="Unknown provider"),
        ):
            get_session_for_account("weird_1")


class TestValidateDurationProvider:
    """Tests for provider-aware duration validation."""

    def test_pishock_duration_range(self) -> None:
        """PiShock: 16-15000ms accepted, outside rejected."""
        assert validate_duration(16, "pishock") == 16
        assert validate_duration(15000, "pishock") == 15000
        with pytest.raises(CliError):
            validate_duration(0.015, "pishock")
        with pytest.raises(CliError):
            validate_duration(15001, "pishock")

    def test_openshock_duration_range(self) -> None:
        """OpenShock: 300-65535ms accepted, outside rejected."""
        assert validate_duration(300, "openshock") == 300
        assert validate_duration(65535, "openshock") == 65535
        with pytest.raises(CliError):
            validate_duration(299, "openshock")
        with pytest.raises(CliError):
            validate_duration(65536, "openshock")
