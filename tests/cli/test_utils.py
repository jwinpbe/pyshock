"""Tests for CLI utility functions in pyshock.cli.utils."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pyshock.cli.config import Config
from pyshock.cli.context import _current_account_id
from pyshock.cli.utils import (
    _current_api_client,
    confirm_operation,
    get_api,
    resolve_shocker_id,
    send_operation,
    set_api_client,
    validate_operation_params,
)
from pyshock.errors import CliError
from pyshock.models.operation import ShockerOperation
from pyshock.models.shocker import Shocker


class TestValidateDuration:
    """Tests for duration validation and normalisation."""

    def test_seconds_to_milliseconds(self) -> None:
        """Durations below 16 are treated as seconds and converted to ms."""
        assert validate_operation_params(5, 50) == 5000

    def test_milliseconds_passthrough(self) -> None:
        """Durations at or above 16 are treated as milliseconds directly."""
        assert validate_operation_params(5000, 50) == 5000


class TestValidateOperationParams:
    """Tests for operation parameter validation."""

    def test_valid(self) -> None:
        """Valid duration and intensity pass through unchanged."""
        assert validate_operation_params(5000, 50) == 5000

    def test_duration_too_low(self) -> None:
        """Duration below minimum raises CliError."""
        with pytest.raises(CliError):
            validate_operation_params(50, 50)

    def test_duration_too_high(self) -> None:
        """Duration above maximum raises CliError."""
        with pytest.raises(CliError):
            validate_operation_params(20000, 50)

    def test_intensity_too_low(self) -> None:
        """Negative intensity raises CliError."""
        with pytest.raises(CliError):
            validate_operation_params(5000, -1)

    def test_intensity_too_high(self) -> None:
        """Intensity above 100 raises CliError."""
        with pytest.raises(CliError):
            validate_operation_params(5000, 101)


class TestGetSetApiClient:
    """Tests for API client context variable management."""

    def test_set_and_get(self) -> None:
        """Setting an API client makes it available via get_api."""
        mock = MagicMock()
        token = _current_api_client.set(mock)
        try:
            assert get_api() is mock
        finally:
            _current_api_client.reset(token)

    def test_get_no_client_raises(self) -> None:
        """get_api raises LookupError when no client has been set."""
        token = _current_api_client.set(MagicMock())
        _current_api_client.reset(token)
        try:
            with pytest.raises(LookupError):
                get_api()
        finally:
            _current_api_client.set(MagicMock())


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
        _current_account_id.set("pishock_1")
        set_api_client(mock_pishock_api)
        with (
            patch("pyshock.cli.utils.get_config", return_value=mock_config),
            patch("pyshock.cli.utils.resolve_shocker_id"),
            patch("pyshock.cli.utils.confirm_operation"),
            patch("pyshock.cli.utils.json_mode", MagicMock(get=lambda: False)),
            patch("pyshock.cli.display.render_operation_result"),
        ):
            send_operation("abc123", ShockerOperation.SHOCK, 5000, 50)

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
        _current_account_id.set("pishock_1")
        set_api_client(mock_pishock_api)
        with (
            patch("pyshock.cli.utils.get_config", return_value=mock_config),
            patch("pyshock.cli.utils.resolve_shocker_id", return_value="def456"),
            patch("pyshock.cli.utils.confirm_operation"),
            patch("pyshock.cli.utils.json_mode", MagicMock(get=lambda: False)),
            patch("pyshock.cli.display.render_operation_result"),
        ):
            send_operation(None, ShockerOperation.SHOCK, 5000, 50)

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
