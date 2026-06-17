"""Entry point for PyShock CLI."""

from __future__ import annotations

import logging
from importlib.util import find_spec
from sys import argv, stderr

if find_spec("cyclopts") is None or find_spec("platformdirs") is None or find_spec("rich") is None:
    print(  # noqa: T201
        "\n\033[1;91mError:\033[0m PyShock is missing components needed for the program to run!"
        "\nRun the following command to install the missing components:\n"
        '\033[1muv tool install "pyshock[cli]"\033[0m\n',
        file=stderr,
    )
    raise SystemExit(1)

from niquests import RequestException
from rich.console import Console
from rich.logging import RichHandler

from pyshock.cli.main import app
from pyshock.errors import APIError, CliError

stderr_console = Console(stderr=True)


def main() -> None:
    """Parse args and dispatch to the appropriate app."""
    cli_args = argv[1:]

    if "--debug" in cli_args or "-d" in cli_args:
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
        app.meta(cli_args)
    except CliError as e:
        stderr_console.print(f"[red]{e}[/red]")
        raise SystemExit(1) from None
    except APIError as e:
        stderr_console.print(f"[red]{e}[/red]")
        raise SystemExit(1) from None
    except RequestException as e:
        stderr_console.print(f"[red]Network error: {e}[/red]")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
