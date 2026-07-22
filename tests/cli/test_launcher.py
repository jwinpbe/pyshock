"""Tests for generic CLI dispatch and top-level error rendering."""

from __future__ import annotations

from io import StringIO
from json import loads as json_loads
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from niquests import RequestException

from pyshock.cli.config import Config
from pyshock.cli.context import json_mode
from pyshock.cli.utils import Session
from pyshock.errors import APIError, CliError, NotAuthorizedError


class TestExitWithError:
    def test_text_error(self) -> None:
        from pyshock.cli.__main__ import _exit_with_error

        json_mode.set(False)
        with (
            patch("pyshock.cli.__main__.stderr_console") as console,
            pytest.raises(SystemExit, match="1"),
        ):
            _exit_with_error(CliError("Test CLI error"))

        assert "Test CLI error" in console.print.call_args.args[0]

    def test_api_error(self) -> None:
        from pyshock.cli.__main__ import _exit_with_error

        json_mode.set(False)
        with (
            patch("pyshock.cli.__main__.stderr_console") as console,
            pytest.raises(SystemExit, match="1"),
        ):
            _exit_with_error(APIError(message="API failure", status_code=500))

        output = console.print.call_args.args[0]
        assert "API failure" in output
        assert "500" in output

    def test_json_error(self) -> None:
        from pyshock.cli.__main__ import _exit_with_error

        json_mode.set(True)
        stderr = StringIO()
        with (
            patch("pyshock.cli.__main__.stderr", stderr),
            pytest.raises(SystemExit, match="1"),
        ):
            _exit_with_error(
                CliError(
                    "OpenShock account requires an API token. "
                    "Re-authenticate it with a newly generated token before continuing."
                )
            )

        output = json_loads(stderr.getvalue())
        assert output["error"] == "CliError"
        assert "Re-authenticate" in output["message"]

    def test_network_error_prefix(self) -> None:
        from pyshock.cli.__main__ import _exit_with_error

        json_mode.set(False)
        with (
            patch("pyshock.cli.__main__.stderr_console") as console,
            pytest.raises(SystemExit, match="1"),
        ):
            _exit_with_error(RequestException("connection refused"), prefix="Network error: ")

        assert "Network error: connection refused" in console.print.call_args.args[0]


def _call_launcher_with_error(
    error: Exception,
    mock_api: MagicMock,
    config: Config,
) -> None:
    from pyshock.cli.main import _launcher

    def build(_config: Config, _bound: Any, account_id: str | None) -> Session:
        resolved = account_id or "pishock_1"
        return Session(api=mock_api, account_id=resolved, provider="pishock")

    with (
        patch("pyshock.cli.main.get_config", return_value=config),
        patch("pyshock.cli.utils.build_session", side_effect=build),
        patch("pyshock.cli.utils.confirm_operation"),
        patch("pyshock.cli.utils.send_operation", side_effect=error),
    ):
        _launcher("shock", "2", "75")


class TestLauncherDispatch:
    def test_no_tokens_returns(self, mock_config: Config) -> None:
        from pyshock.cli.main import _launcher

        with patch("pyshock.cli.main.get_config", return_value=mock_config):
            _launcher()

    def test_unconfigured_config_exits(self) -> None:
        from pyshock.cli.main import _launcher

        with (
            patch("pyshock.cli.main.get_config", return_value=Config()),
            patch("pyshock.cli.display.render_no_creds_panel"),
            pytest.raises(SystemExit, match="1"),
        ):
            _launcher("shock", "1", "50")

    def test_unknown_command_exits(self, mock_config: Config) -> None:
        from pyshock.cli.main import _launcher

        with (
            patch("pyshock.cli.main.get_config", return_value=mock_config),
            pytest.raises(SystemExit, match="1"),
        ):
            _launcher("bogus_command_xyz")

    @pytest.mark.parametrize(
        "error",
        [
            NotAuthorizedError(),
            APIError(message="API failure", status_code=500),
            RequestException("connection refused"),
            CliError("CLI failure"),
        ],
    )
    def test_command_errors_propagate_to_entrypoint(
        self,
        error: Exception,
        mock_pishock_api: MagicMock,
        mock_config: Config,
    ) -> None:
        with pytest.raises(type(error)) as exc_info:
            _call_launcher_with_error(error, mock_pishock_api, mock_config)
        assert exc_info.value is error

    def test_code_list_uses_normal_session_dispatch(
        self,
        mock_pishock_api: MagicMock,
        mock_config: Config,
    ) -> None:
        from pyshock.cli.main import _launcher

        mock_pishock_api.list_shockers.return_value = []
        with (
            patch("pyshock.cli.main.get_config", return_value=mock_config),
            patch(
                "pyshock.cli.utils.build_session",
                return_value=Session(api=mock_pishock_api, account_id="pishock_1", provider="pishock"),
            ) as prepare,
            patch("pyshock.cli.commands.code.console.status"),
            patch("pyshock.cli.commands.code.share_code.code_list"),
        ):
            _launcher("code", "list", account_id="pishock_1")

        prepare.assert_called_once()
        mock_pishock_api.list_shockers.assert_called_once_with()
