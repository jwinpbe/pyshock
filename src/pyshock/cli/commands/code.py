"""Share code commands for PyShock CLI (add, delete, list)."""

from typing import Annotated

from cyclopts import Parameter

from pyshock.cli import share_code
from pyshock.cli.context import json_mode
from pyshock.cli.display import console, print_output, shocker_json
from pyshock.errors import CliError
from pyshock.pishockapi import PiShockAPI
from pyshock.protocols import Session


def _get_pishock_api(session: Session) -> PiShockAPI:
    """Keep provider policy at the boundary of the PiShock-only command group."""
    if not isinstance(session.api, PiShockAPI):
        raise CliError("Manage OpenShock share codes in the OpenShock web interface.")
    return session.api


def add(
    code: str,
    *,
    session: Annotated[Session, Parameter(parse=False)],
) -> None:
    """Add a PiShock share code."""
    share_code.code_add(code, _get_pishock_api(session))


def delete(
    code: str,
    *,
    session: Annotated[Session, Parameter(parse=False)],
) -> None:
    """Delete a PiShock share code."""
    share_code.code_delete(code, _get_pishock_api(session))


def list_codes(
    *,
    show_info: bool = False,
    session: Annotated[Session, Parameter(parse=False)],
) -> None:
    """List share codes for the selected PiShock account."""
    api = _get_pishock_api(session)
    with console.status("Querying PiShock...", spinner="bouncingBar"):
        shared = [shocker for shocker in api.list_shockers() if shocker.is_shared]

    if json_mode.get():
        print_output([shocker_json(shocker) for shocker in shared])
    else:
        share_code.code_list(show_info=show_info, shockers=shared)
