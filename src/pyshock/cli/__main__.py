"""Entry point for PyShock CLI."""

from __future__ import annotations

import logging
from importlib.util import find_spec
from json import dumps as json_dumps
from sys import stderr

if find_spec("cyclopts") is None or find_spec("platformdirs") is None or find_spec("rich") is None:
    print(
        "\n\033[1;91mError:\033[0m PyShock is missing components needed for the program to run!"
        "\nRun the following command to install the missing components:\n"
        '\033[1muv tool install "pyshock[cli]"\033[0m\n',
        file=stderr,
    )
    raise SystemExit(1)

from cyclopts.exceptions import CoercionError, MissingArgumentError, ValidationError
from niquests import RequestException
from rich.console import Console
from rich.logging import RichHandler

from pyshock.cli.context import json_mode
from pyshock.cli.display import error_json
from pyshock.cli.main import app
from pyshock.errors import APIError, CliError

stderr_console = Console(stderr=True)


def _exit_with_error(error: Exception, *, prefix: str = "") -> None:
    if json_mode.get():
        print(json_dumps(error_json(error), indent=2), file=stderr)
    else:
        stderr_console.print(f"[red]{prefix}{error}[/red]")
    raise SystemExit(1) from None


def main() -> None:
    """Parse args and dispatch to the appropriate app."""
    _launcher_command, bound, _unused_tokens, _ignored = app.meta.parse_known_args()
    json_mode.set(bound.kwargs.get("json_output", False))

    if bound.kwargs.get("_debug", False):
        logging.getLogger("pyshock").setLevel(logging.DEBUG)
        if not logging.getLogger("pyshock").handlers:
            logging.getLogger("pyshock").addHandler(
                RichHandler(
                    console=stderr_console,
                    show_time=False,
                    show_level=True,
                    show_path=False,
                )
            )

    try:
        app.meta()
    except (CliError, APIError, ValidationError, CoercionError, MissingArgumentError) as error:
        _exit_with_error(error)
    except RequestException as error:
        _exit_with_error(error, prefix="Network error: ")


if __name__ == "__main__":
    main()
