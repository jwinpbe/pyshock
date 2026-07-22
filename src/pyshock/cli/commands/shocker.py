"""Shocker commands for PyShock CLI (info, shock, vibrate, beep)."""

from typing import Annotated

from cyclopts import Parameter, validators

from pyshock.cli import utils
from pyshock.cli.context import json_mode
from pyshock.cli.display import console, print_output, render_info_table, shocker_json
from pyshock.models.operation import ShockerOperation
from pyshock.protocols import Session


def info(
    *,
    shocker_id: Annotated[str, Parameter(alias="--id")],
    session: Annotated[Session, Parameter(parse=False)],
) -> None:
    """Get details for a shocker."""
    api = session.api
    acct_id = session.account_id
    with console.status(
        f"Fetching details for shocker [bold italic]'{shocker_id}'[/bold italic]...", spinner="bouncingBar"
    ):
        shocker = api.get_shocker_by_id(shocker_id)

    if json_mode.get():
        data = shocker_json(shocker, account_id=acct_id)
        data["shocker_id"] = shocker_id
        print_output(data)
    else:
        render_info_table(shocker, acct_id)


def shock(
    duration: float,
    intensity: Annotated[int, Parameter(validator=validators.Number(gte=0, lte=100))],
    *,
    shocker_id: Annotated[str | None, Parameter(alias="--id")] = None,
    force: Annotated[bool, Parameter(alias="f")] = False,
    session: Annotated[Session, Parameter(parse=False)],
) -> None:
    """Send a shock. Auto-resolves shocker-id if omitted."""
    if not force:
        utils.confirm_operation("shock")
    utils.send_operation(session, shocker_id, ShockerOperation.SHOCK, duration, intensity)


def vibrate(
    duration: float,
    intensity: Annotated[int, Parameter(validator=validators.Number(gte=0, lte=100))],
    *,
    shocker_id: Annotated[str | None, Parameter(alias="--id")] = None,
    force: Annotated[bool, Parameter(alias="f")] = False,
    session: Annotated[Session, Parameter(parse=False)],
) -> None:
    """Send a vibration. Auto-resolves shocker-id if omitted."""
    if not force:
        utils.confirm_operation("vibrate")
    utils.send_operation(session, shocker_id, ShockerOperation.VIBRATE, duration, intensity)


def beep(
    *,
    shocker_id: Annotated[str | None, Parameter(alias="--id")] = None,
    force: Annotated[bool, Parameter(alias="f")] = False,
    session: Annotated[Session, Parameter(parse=False)],
) -> None:
    """Send a beep. Auto-resolves shocker-id if omitted."""
    if not force:
        utils.confirm_operation("beep")
    utils.send_operation(session, shocker_id, ShockerOperation.BEEP, 500, 50)
