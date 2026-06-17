"""Tests for _launcher and _exit_with_error in the CLI meta default.

The real ``_launcher`` (registered as ``app.meta.default``) is called directly
to verify dispatch and error-handling routing.  Because cyclopts' App is
attrs-based, ``app.parse_args`` and ``app.help_print`` are read-only and
cannot be patched.  Instead, we let ``_launcher`` dispatch to real commands
and mock the command's dependencies to inject exceptions.

``_exit_with_error`` is also tested directly for every error type the CLI
can produce.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from pyshock.cli.config import Config
from pyshock.cli.context import _current_account_id, json_mode
from pyshock.errors import APIError, CliError, NotAuthorizedError, ShockerNotFoundError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _call_launcher_with_exc(
    tokens: list[str],
    mock_api: MagicMock,
    config: Config,
    exc: Exception,
    account_id: str = "pishock_1",
) -> None:
    """Call ``_launcher`` so the dispatched command raises ``exc``.

    Because cyclopts App is attrs-based (read-only), we cannot patch
    ``app.parse_args``.  Instead we let the real ``app.parse_args`` dispatch
    to the actual command and mock the command's dependency (``send_operation``)
    to raise the desired exception.

    Parameters
    ----------
    tokens:
        CLI tokens (e.g. ``["shock", "2", "75"]``).
    mock_api:
        Mock API returned by ``prepare_api_session``.
    config:
        Config returned by ``get_config``.
    exc:
        Exception the command should raise.
    account_id:
        Account id to set in context.
    """
    from pyshock.cli.main import _launcher

    def _mock_prepare(_cfg: Config, _bound: Any, aid: str | None) -> tuple:
        _current_account_id.set(aid or account_id)
        return mock_api, aid or account_id

    with (
        patch("pyshock.cli.main.get_config", return_value=config),
        patch("pyshock.cli.config.get_config", return_value=config),
        patch("pyshock.cli.utils.get_config", return_value=config),
        patch("pyshock.cli.utils.prepare_api_session", side_effect=_mock_prepare),
        patch("pyshock.cli.utils.get_api", return_value=mock_api),
        patch("pyshock.cli.utils.resolve_shocker_id", return_value="abc123"),
        patch("pyshock.cli.utils.send_operation", side_effect=exc),
    ):
        _launcher(*tokens)


# ---------------------------------------------------------------------------
# _exit_with_error — direct tests for every error type
# ---------------------------------------------------------------------------


class TestExitWithError:
    """Test ``_exit_with_error`` directly for every error type the CLI produces."""

    def test_cli_error_formatted(self) -> None:
        """CliError is formatted and SystemExit(1) is raised."""
        from pyshock.cli.main import _exit_with_error

        with (
            patch("pyshock.cli.main.console_err") as mock_err,
            pytest.raises(SystemExit) as exc_info,
        ):
            _exit_with_error(CliError("Test cli error"))

        assert exc_info.value.code == 1
        mock_err.print.assert_called_once()
        assert "Test cli error" in mock_err.print.call_args.args[0]

    def test_not_authorized_error(self) -> None:
        """NotAuthorizedError is formatted and SystemExit(1) is raised."""
        from pyshock.cli.main import _exit_with_error

        with (
            patch("pyshock.cli.main.console_err") as mock_err,
            pytest.raises(SystemExit) as exc_info,
        ):
            _exit_with_error(NotAuthorizedError())

        assert exc_info.value.code == 1
        mock_err.print.assert_called_once()
        assert "Not authorized" in mock_err.print.call_args.args[0]

    def test_shocker_not_found_error(self) -> None:
        """ShockerNotFoundError (APIError subclass) is formatted and SystemExit(1) raised."""
        from pyshock.cli.main import _exit_with_error

        with (
            patch("pyshock.cli.main.console_err") as mock_err,
            pytest.raises(SystemExit) as exc_info,
        ):
            _exit_with_error(ShockerNotFoundError())

        assert exc_info.value.code == 1
        mock_err.print.assert_called_once()
        assert "Shocker not found" in mock_err.print.call_args.args[0]

    def test_api_error_formatted(self) -> None:
        """APIError is formatted with status code and SystemExit(1) is raised."""
        from pyshock.cli.main import _exit_with_error

        with (
            patch("pyshock.cli.main.console_err") as mock_err,
            pytest.raises(SystemExit) as exc_info,
        ):
            _exit_with_error(APIError(message="API failure", status_code=500))

        assert exc_info.value.code == 1
        mock_err.print.assert_called_once()
        assert "API failure" in mock_err.print.call_args.args[0]
        assert "500" in mock_err.print.call_args.args[0]

    def test_json_error_output(self) -> None:
        """JSON mode outputs structured error JSON instead of formatted text."""
        from pyshock.cli.main import _exit_with_error

        json_mode.set(True)
        with (
            patch("pyshock.cli.main.console_err") as mock_err,
            pytest.raises(SystemExit) as exc_info,
        ):
            _exit_with_error(CliError("Test cli error"))

        assert exc_info.value.code == 1
        mock_err.print.assert_called_once()
        output = mock_err.print.call_args.args[0]
        assert '"error": "CliError"' in output
        assert '"message": "Test cli error"' in output

    def test_request_error_prefix(self) -> None:
        """RequestException gets the 'Network error: ' prefix."""
        from niquests import RequestException

        from pyshock.cli.main import _exit_with_error

        with (
            patch("pyshock.cli.main.console_err") as mock_err,
            pytest.raises(SystemExit) as exc_info,
        ):
            _exit_with_error(RequestException("connection refused"), prefix="Network error: ")

        assert exc_info.value.code == 1
        mock_err.print.assert_called_once()
        assert "Network error: connection refused" in mock_err.print.call_args.args[0]


# ---------------------------------------------------------------------------
# _launcher — direct tests of the meta-default handler
# ---------------------------------------------------------------------------


class TestLauncherDispatch:
    """Test ``_launcher`` directly — dispatch and error routing."""

    def test_no_tokens_returns(
        self,
        mock_config: Config,
    ) -> None:
        """Calling _launcher with no tokens prints help and returns (no exit)."""
        with (
            patch("pyshock.cli.main.get_config", return_value=mock_config),
            patch("pyshock.cli.config.get_config", return_value=mock_config),
            patch("pyshock.cli.utils.get_config", return_value=mock_config),
        ):
            from pyshock.cli.main import _launcher
            _launcher()  # no tokens — should return, not raise

    def test_unconfigured_config_exits(
        self,
    ) -> None:
        """Unconfigured config renders no-creds panel and raises SystemExit(1)."""
        config = Config()
        with (
            patch("pyshock.cli.main.get_config", return_value=config),
            patch("pyshock.cli.config.get_config", return_value=config),
            patch("pyshock.cli.utils.get_config", return_value=config),
            patch("pyshock.cli.display.render_no_creds_panel"),
            pytest.raises(SystemExit) as exc_info,
        ):
            from pyshock.cli.main import _launcher
            _launcher("shock", "1", "50")

        assert exc_info.value.code == 1

    def test_unknown_command_exits(
        self,
        mock_config: Config,
    ) -> None:
        """Unknown command prints error, help, and raises SystemExit(1)."""
        with (
            patch("pyshock.cli.main.get_config", return_value=mock_config),
            patch("pyshock.cli.config.get_config", return_value=mock_config),
            patch("pyshock.cli.utils.get_config", return_value=mock_config),
            pytest.raises(SystemExit) as exc_info,
        ):
            from pyshock.cli.main import _launcher
            _launcher("bogus_command_xyz")

        assert exc_info.value.code == 1

    def test_not_authorized_routed(
        self,
        mock_pishock_api: MagicMock,
        mock_config: Config,
    ) -> None:
        """NotAuthorizedError from command is caught and formatted."""
        with (
            patch("pyshock.cli.main.console_err") as mock_err,
            pytest.raises(SystemExit) as exc_info,
        ):
            _call_launcher_with_exc(
                ["shock", "2", "75"],
                mock_pishock_api,
                mock_config,
                NotAuthorizedError(),
            )

        assert exc_info.value.code == 1
        mock_err.print.assert_called_once()
        assert "Not authorized" in mock_err.print.call_args.args[0]

    def test_shocker_not_found_routed(
        self,
        mock_pishock_api: MagicMock,
        mock_config: Config,
    ) -> None:
        """ShockerNotFoundError (APIError subclass) routed through except APIError."""
        with (
            patch("pyshock.cli.main.console_err") as mock_err,
            pytest.raises(SystemExit) as exc_info,
        ):
            _call_launcher_with_exc(
                ["shock", "2", "75"],
                mock_pishock_api,
                mock_config,
                ShockerNotFoundError(),
            )

        assert exc_info.value.code == 1
        mock_err.print.assert_called_once()
        assert "Shocker not found" in mock_err.print.call_args.args[0]

    def test_request_exception_routed(
        self,
        mock_pishock_api: MagicMock,
        mock_config: Config,
    ) -> None:
        """RequestException from command gets 'Network error: ' prefix."""
        from niquests import RequestException

        with (
            patch("pyshock.cli.main.console_err") as mock_err,
            pytest.raises(SystemExit) as exc_info,
        ):
            _call_launcher_with_exc(
                ["shock", "2", "75"],
                mock_pishock_api,
                mock_config,
                RequestException("connection refused"),
            )

        assert exc_info.value.code == 1
        mock_err.print.assert_called_once()
        assert "Network error: connection refused" in mock_err.print.call_args.args[0]

    def test_json_error_via_launcher(
        self,
        mock_pishock_api: MagicMock,
        mock_config: Config,
    ) -> None:
        """JSON mode via _launcher outputs structured error JSON."""
        from pyshock.cli.main import _launcher

        def _mock_prepare(_cfg: Config, _bound: Any, aid: str | None) -> tuple:
            _current_account_id.set(aid or "pishock_1")
            return mock_pishock_api, aid or "pishock_1"

        with (
            patch("pyshock.cli.main.get_config", return_value=mock_config),
            patch("pyshock.cli.config.get_config", return_value=mock_config),
            patch("pyshock.cli.utils.get_config", return_value=mock_config),
            patch("pyshock.cli.utils.prepare_api_session", side_effect=_mock_prepare),
            patch("pyshock.cli.utils.get_api", return_value=mock_pishock_api),
            patch("pyshock.cli.utils.resolve_shocker_id", return_value="abc123"),
            patch("pyshock.cli.utils.send_operation", side_effect=NotAuthorizedError()),
            patch("pyshock.cli.main.console_err") as mock_err,
            pytest.raises(SystemExit) as exc_info,
        ):
            _launcher("shock", "2", "75", json_output=True)

        assert exc_info.value.code == 1
        mock_err.print.assert_called_once()
        output = mock_err.print.call_args.args[0]
        assert '"error": "NotAuthorizedError"' in output
