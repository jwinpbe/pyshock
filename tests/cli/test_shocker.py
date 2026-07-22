"""Layer 2: Command execution tests for shock, vibrate, beep, and info.

Verifies that command functions correctly wire up API calls, context vars,
and display rendering.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from cyclopts.exceptions import CoercionError, ValidationError

from pyshock.cli.commands.shocker import beep, info, shock, vibrate
from pyshock.cli.context import json_mode
from pyshock.cli.utils import Session
from pyshock.errors import ShockerNotFoundError
from pyshock.models.operation import ShockerOperation
from pyshock.models.shocker import Shocker

if TYPE_CHECKING:
    from cyclopts import App

    from pyshock.cli.config import Config


@pytest.fixture
def test_shocker() -> Shocker:
    """Return a standard test Shocker instance."""
    return Shocker(
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


class TestShock:
    """Tests for the shock command."""

    def test_sends_operation_with_resolved_shocker(
        self,
        mock_pishock_api: MagicMock,
        mock_config: Config,
    ) -> None:
        """When shocker_id is omitted, resolve_shocker_id provides the target."""
        session = Session(api=mock_pishock_api, account_id="pishock_1", provider="pishock")
        with (
            patch("pyshock.cli.utils.get_config", return_value=mock_config),
            patch("pyshock.cli.utils.resolve_shocker_id", return_value="abc123"),
        ):
            shock(2, 75, force=True, session=session)

        mock_pishock_api.operate_shocker.assert_called_once_with(
            shocker="abc123",
            operation=ShockerOperation.SHOCK,
            duration=2000,
            intensity=75,
        )

    def test_sends_operation_with_explicit_shocker(
        self,
        mock_pishock_api: MagicMock,
        mock_config: Config,
    ) -> None:
        """When shocker_id is provided, it is used directly."""
        session = Session(api=mock_pishock_api, account_id="pishock_1", provider="pishock")
        with (
            patch("pyshock.cli.utils.get_config", return_value=mock_config),
            patch("pyshock.cli.utils.resolve_shocker_id", return_value="abc123"),
        ):
            shock(2, 75, shocker_id="00000", force=True, session=session)

        mock_pishock_api.operate_shocker.assert_called_once_with(
            shocker="00000",
            operation=ShockerOperation.SHOCK,
            duration=2000,
            intensity=75,
        )

    def test_confirmation_prompt_accepted(
        self,
        mock_pishock_api: MagicMock,
        mock_config: Config,
    ) -> None:
        """When confirm_operation returns normally, the operation proceeds."""
        session = Session(api=mock_pishock_api, account_id="pishock_1", provider="pishock")
        with (
            patch("pyshock.cli.utils.get_config", return_value=mock_config),
            patch("pyshock.cli.utils.resolve_shocker_id", return_value="abc123"),
            patch("pyshock.cli.utils.confirm_operation"),
        ):
            shock(2, 75, session=session)

        mock_pishock_api.operate_shocker.assert_called_once()

    def test_confirmation_prompt_declined(
        self,
        mock_pishock_api: MagicMock,
        mock_config: Config,
    ) -> None:
        """When confirm_operation raises SystemExit(0), the operation is aborted."""
        session = Session(api=mock_pishock_api, account_id="pishock_1", provider="pishock")
        with (
            patch("pyshock.cli.utils.get_config", return_value=mock_config),
            patch("pyshock.cli.utils.confirm_operation", side_effect=SystemExit(0)),
        ):
            with pytest.raises(SystemExit):
                shock(2, 75, session=session)

        mock_pishock_api.operate_shocker.assert_not_called()

    def test_json_output(
        self,
        mock_pishock_api: MagicMock,
        mock_config: Config,
    ) -> None:
        """When json_mode is True, render_operation_result emits JSON."""
        session = Session(api=mock_pishock_api, account_id="pishock_1", provider="pishock")
        json_mode.set(True)
        with (
            patch("pyshock.cli.utils.get_config", return_value=mock_config),
            patch("pyshock.cli.utils.resolve_shocker_id", return_value="abc123"),
            patch("pyshock.cli.display.render_operation_result") as mock_render,
        ):
            shock(2, 75, force=True, session=session)

        mock_pishock_api.operate_shocker.assert_called_once()
        mock_render.assert_called_once_with(
            "abc123",
            "Shock",
            2000,
            75,
        )


class TestVibrate:
    """Tests for the vibrate command."""

    def test_sends_operation_with_resolved_shocker(
        self,
        mock_pishock_api: MagicMock,
        mock_config: Config,
    ) -> None:
        """When shocker_id is omitted, resolve_shocker_id provides the target."""
        session = Session(api=mock_pishock_api, account_id="pishock_1", provider="pishock")
        with (
            patch("pyshock.cli.utils.get_config", return_value=mock_config),
            patch("pyshock.cli.utils.resolve_shocker_id", return_value="abc123"),
        ):
            vibrate(2, 75, force=True, session=session)

        mock_pishock_api.operate_shocker.assert_called_once_with(
            shocker="abc123",
            operation=ShockerOperation.VIBRATE,
            duration=2000,
            intensity=75,
        )

    def test_sends_operation_with_explicit_shocker(
        self,
        mock_pishock_api: MagicMock,
        mock_config: Config,
    ) -> None:
        """When shocker_id is provided, it is used directly."""
        session = Session(api=mock_pishock_api, account_id="pishock_1", provider="pishock")
        with (
            patch("pyshock.cli.utils.get_config", return_value=mock_config),
            patch("pyshock.cli.utils.resolve_shocker_id", return_value="abc123"),
        ):
            vibrate(2, 75, shocker_id="00000", force=True, session=session)

        mock_pishock_api.operate_shocker.assert_called_once_with(
            shocker="00000",
            operation=ShockerOperation.VIBRATE,
            duration=2000,
            intensity=75,
        )

    def test_confirmation_prompt_accepted(
        self,
        mock_pishock_api: MagicMock,
        mock_config: Config,
    ) -> None:
        """When confirm_operation returns normally, the operation proceeds."""
        session = Session(api=mock_pishock_api, account_id="pishock_1", provider="pishock")
        with (
            patch("pyshock.cli.utils.get_config", return_value=mock_config),
            patch("pyshock.cli.utils.resolve_shocker_id", return_value="abc123"),
            patch("pyshock.cli.utils.confirm_operation"),
        ):
            vibrate(2, 75, session=session)

        mock_pishock_api.operate_shocker.assert_called_once()

    def test_confirmation_prompt_declined(
        self,
        mock_pishock_api: MagicMock,
        mock_config: Config,
    ) -> None:
        """When confirm_operation raises SystemExit(0), the operation is aborted."""
        session = Session(api=mock_pishock_api, account_id="pishock_1", provider="pishock")
        with (
            patch("pyshock.cli.utils.get_config", return_value=mock_config),
            patch("pyshock.cli.utils.confirm_operation", side_effect=SystemExit(0)),
        ):
            with pytest.raises(SystemExit):
                vibrate(2, 75, session=session)

        mock_pishock_api.operate_shocker.assert_not_called()

    def test_json_output(
        self,
        mock_pishock_api: MagicMock,
        mock_config: Config,
    ) -> None:
        """When json_mode is True, render_operation_result emits JSON."""
        session = Session(api=mock_pishock_api, account_id="pishock_1", provider="pishock")
        json_mode.set(True)
        with (
            patch("pyshock.cli.utils.get_config", return_value=mock_config),
            patch("pyshock.cli.utils.resolve_shocker_id", return_value="abc123"),
            patch("pyshock.cli.display.render_operation_result") as mock_render,
        ):
            vibrate(2, 75, force=True, session=session)

        mock_pishock_api.operate_shocker.assert_called_once()
        mock_render.assert_called_once_with(
            "abc123",
            "Vibrate",
            2000,
            75,
        )


class TestBeep:
    """Tests for the beep command."""

    def test_sends_operation_with_resolved_shocker(
        self,
        mock_pishock_api: MagicMock,
        mock_config: Config,
    ) -> None:
        """Beep uses fixed duration=500ms and intensity=50."""
        session = Session(api=mock_pishock_api, account_id="pishock_1", provider="pishock")
        with (
            patch("pyshock.cli.utils.get_config", return_value=mock_config),
            patch("pyshock.cli.utils.resolve_shocker_id", return_value="abc123"),
        ):
            beep(force=True, session=session)

        mock_pishock_api.operate_shocker.assert_called_once_with(
            shocker="abc123",
            operation=ShockerOperation.BEEP,
            duration=500,
            intensity=50,
        )

    def test_sends_operation_with_explicit_shocker(
        self,
        mock_pishock_api: MagicMock,
        mock_config: Config,
    ) -> None:
        """When shocker_id is provided, it is used directly."""
        session = Session(api=mock_pishock_api, account_id="pishock_1", provider="pishock")
        with (
            patch("pyshock.cli.utils.get_config", return_value=mock_config),
            patch("pyshock.cli.utils.resolve_shocker_id", return_value="abc123"),
        ):
            beep(shocker_id="00000", force=True, session=session)

        mock_pishock_api.operate_shocker.assert_called_once_with(
            shocker="00000",
            operation=ShockerOperation.BEEP,
            duration=500,
            intensity=50,
        )

    def test_confirmation_prompt_accepted(
        self,
        mock_pishock_api: MagicMock,
        mock_config: Config,
    ) -> None:
        """When confirm_operation returns normally, the operation proceeds."""
        session = Session(api=mock_pishock_api, account_id="pishock_1", provider="pishock")
        with (
            patch("pyshock.cli.utils.get_config", return_value=mock_config),
            patch("pyshock.cli.utils.resolve_shocker_id", return_value="abc123"),
            patch("pyshock.cli.utils.confirm_operation"),
        ):
            beep(session=session)

        mock_pishock_api.operate_shocker.assert_called_once()

    def test_confirmation_prompt_declined(
        self,
        mock_pishock_api: MagicMock,
        mock_config: Config,
    ) -> None:
        """When confirm_operation raises SystemExit(0), the operation is aborted."""
        session = Session(api=mock_pishock_api, account_id="pishock_1", provider="pishock")
        with (
            patch("pyshock.cli.utils.get_config", return_value=mock_config),
            patch("pyshock.cli.utils.confirm_operation", side_effect=SystemExit(0)),
        ):
            with pytest.raises(SystemExit):
                beep(session=session)

        mock_pishock_api.operate_shocker.assert_not_called()

    def test_json_output(
        self,
        mock_pishock_api: MagicMock,
        mock_config: Config,
    ) -> None:
        """When json_mode is True, render_operation_result emits JSON."""
        session = Session(api=mock_pishock_api, account_id="pishock_1", provider="pishock")
        json_mode.set(True)
        with (
            patch("pyshock.cli.utils.get_config", return_value=mock_config),
            patch("pyshock.cli.utils.resolve_shocker_id", return_value="abc123"),
            patch("pyshock.cli.display.render_operation_result") as mock_render,
        ):
            beep(force=True, session=session)

        mock_pishock_api.operate_shocker.assert_called_once()
        mock_render.assert_called_once_with(
            "abc123",
            "Beep",
            500,
            50,
        )


class TestInfo:
    """Tests for the info command."""

    def test_found_shocker(
        self,
        mock_pishock_api: MagicMock,
        test_shocker: Shocker,
    ) -> None:
        """When shocker exists, render_info_table is called with the result."""
        mock_pishock_api.get_shocker_by_id.return_value = test_shocker
        session = Session(api=mock_pishock_api, account_id="pishock_1", provider="pishock")
        with patch("pyshock.cli.commands.shocker.render_info_table") as mock_render:
            info(shocker_id="abc123", session=session)

        mock_pishock_api.get_shocker_by_id.assert_called_once_with("abc123")
        mock_render.assert_called_once()

    def test_shocker_not_found(
        self,
        mock_pishock_api: MagicMock,
    ) -> None:
        """When shocker does not exist, ShockerNotFoundError propagates."""
        mock_pishock_api.get_shocker_by_id.side_effect = ShockerNotFoundError()
        session = Session(api=mock_pishock_api, account_id="pishock_1", provider="pishock")
        with patch("pyshock.cli.commands.shocker.render_info_table"):
            with pytest.raises(ShockerNotFoundError):
                info(shocker_id="bad", session=session)

        mock_pishock_api.get_shocker_by_id.assert_called_once_with("bad")

    def test_json_output(
        self,
        mock_pishock_api: MagicMock,
        test_shocker: Shocker,
    ) -> None:
        """When json_mode is True, shocker_json is called and print_output renders."""
        mock_pishock_api.get_shocker_by_id.return_value = test_shocker
        session = Session(api=mock_pishock_api, account_id="pishock_1", provider="pishock")
        json_mode.set(True)
        with (
            patch(
                "pyshock.cli.commands.shocker.shocker_json",
                return_value={
                    "shocker_id": "abc123",
                    "name": "Test Shocker",
                    "can_shock": True,
                    "can_vibrate": True,
                    "can_beep": True,
                    "can_hold": True,
                    "max_intensity": 100,
                    "max_duration": 15000,
                    "is_v3": True,
                    "can_pause": True,
                    "account_id": "pishock_1",
                },
            ) as mock_json,
            patch("pyshock.cli.commands.shocker.print_output") as mock_print,
        ):
            info(shocker_id="abc123", session=session)

        mock_pishock_api.get_shocker_by_id.assert_called_once_with("abc123")
        mock_json.assert_called_once_with(test_shocker, account_id="pishock_1")
        mock_print.assert_called_once()


class TestIntensityValidation:
    """Tests for intensity validation at the cyclopts parse layer."""

    def test_intensity_above_max_raises_validation_error(
        self,
        app: App,
    ) -> None:
        """Intensity above 100 raises ValidationError at parse time."""
        with pytest.raises(ValidationError):
            app.parse_args(
                ["shock", "2", "150", "--force"],
                print_error=False,
                exit_on_error=False,
            )

    def test_intensity_below_min_raises_validation_error(
        self,
        app: App,
    ) -> None:
        """Intensity below 0 raises ValidationError at parse time."""
        with pytest.raises(ValidationError):
            app.parse_args(
                ["shock", "2", "-1", "--force"],
                print_error=False,
                exit_on_error=False,
            )

    def test_non_numeric_duration_raises_coercion_error(
        self,
        app: App,
    ) -> None:
        """Non-numeric duration raises CoercionError at parse time."""
        with pytest.raises(CoercionError):
            app.parse_args(
                ["shock", "abc", "50", "--force"],
                print_error=False,
                exit_on_error=False,
            )
