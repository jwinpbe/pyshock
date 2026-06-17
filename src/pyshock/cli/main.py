"""Main CLI application for PyShock."""

from __future__ import annotations

from importlib.metadata import version as pkg_version
from json import dumps as json_dumps
from typing import Annotated

from cyclopts import App, Group, Parameter
from cyclopts.exceptions import UnknownCommandError
from niquests import RequestException

from pyshock.cli import utils
from pyshock.cli.config import get_config
from pyshock.cli.context import json_mode
from pyshock.cli.display import console_err, error_json
from pyshock.errors import APIError, NotAuthorizedError

_connection_group = Group("Connection", sort_key=1)

_shocker_group = Group.create_ordered("Shocker Commands")
_device_group = Group.create_ordered("Device Management")
_account_group = Group.create_ordered("Account")
_utility_group = Group.create_ordered("Utility")
_code_group = Group.create_ordered("Share Codes")

app = App(
    name="PyShock",
    version=pkg_version("pyshock"),
    version_flags=["--version"],
)
code_app = App(name="code", help="Manage share codes.")

app["--help"].group = _utility_group
app["--version"].group = _utility_group

app.command(code_app)
app["code"].group = _code_group


@app.meta.default
def _launcher(
    *tokens: Annotated[str, Parameter(show=False, allow_leading_hyphen=True)],
    account_id: Annotated[str | None, Parameter(name="account", group=_connection_group, show=False)] = None,
    _debug: Annotated[bool, Parameter(alias="d", group=_connection_group, show=False)] = False,
    json_output: Annotated[bool, Parameter(alias="j", name="json", show=False)] = False,
) -> None:
    # Resolve account, create API client, dispatch.
    if not tokens:
        app.help_print()
        return

    json_mode.set(json_output)
    config = get_config()

    if not config.is_configured:
        from pyshock.cli.display import render_no_creds_panel

        render_no_creds_panel()
        raise SystemExit(1)

    try:
        command, bound, _ignored = app.parse_args(tokens, print_error=False, exit_on_error=False)
    except UnknownCommandError:
        unknown = " ".join(tokens)
        console_err.print()
        console_err.print(f'[red bold]Unknown command:[/red bold] "[bold italic]{unknown}[/bold italic]"')
        console_err.print()
        app.help_print()
        raise SystemExit(1) from None

    api, account_id = utils.prepare_api_session(config, bound, account_id)

    with api:
        try:
            command(*bound.args, **bound.kwargs)  # type: ignore[operator]
        except NotAuthorizedError as e:
            _exit_with_error(e)
        except APIError as e:
            _exit_with_error(e)
        except RequestException as e:
            _exit_with_error(e, prefix="Network error: ")


def _exit_with_error(e: Exception, *, prefix: str = "") -> None:
    if json_mode.get():
        console_err.print(json_dumps(error_json(e), indent=2), markup=False)
    else:
        msg = f"{prefix}{e}" if prefix else str(e)
        console_err.print(f"[red]{msg}[/red]")
    raise SystemExit(1) from None


app.command("pyshock.cli.commands.shocker:info", help="View details for a device.", group=_device_group)
app.command("pyshock.cli.commands.shocker:shock", help="Shock a device.", group=_shocker_group, sort_key=0)
app.command("pyshock.cli.commands.shocker:vibrate", help="Vibrate a device.", group=_shocker_group, sort_key=1)
app.command("pyshock.cli.commands.shocker:beep", help="Beep a device.", group=_shocker_group, sort_key=2)

code_app.command("pyshock.cli.commands.code:add", help="Add a device by its share code.")
code_app.command("pyshock.cli.commands.code:delete", help="Remove a shared device by its share code.")
code_app.command("pyshock.cli.commands.code:list_codes", name="list", help="List shared devices.")

app.meta.command(
    "pyshock.cli.commands.meta:auth", name="auth", alias="init", help="Set up your account.", group=_account_group
)
app.meta.command("pyshock.cli.commands.meta:logout", help="Remove a saved account.", group=_account_group)
app.meta.command(
    "pyshock.cli.commands.meta:confirm", help="Show or change confirmation prompts for actions.", group=_utility_group
)
app.meta.command("pyshock.cli.commands.meta:default", help="Set or change your default device.", group=_utility_group)
app.meta.command(
    "pyshock.cli.commands.meta:verify", help="Check that your account is connected properly.", group=_account_group
)
app.meta.command(
    "pyshock.cli.commands.meta:devices", help="Find and list all your devices.", alias="list", group=_device_group
)
