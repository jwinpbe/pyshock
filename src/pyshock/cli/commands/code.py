"""Share code commands for PyShock CLI (add, delete, list)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from cyclopts import Parameter

from pyshock.cli import share_code, utils
from pyshock.cli.config import get_config
from pyshock.cli.context import json_mode
from pyshock.cli.display import console, print_output, shocker_json

if TYPE_CHECKING:
    from pyshock.models.shocker import Shocker


def add(code: str) -> None:
    """Add a share code."""
    api = utils.get_api()
    share_code.code_add(code, api)


def delete(code: str) -> None:
    """Delete a share code."""
    api = utils.get_api()
    share_code.code_delete(code, api)


def list_codes(
    *,
    show_info: bool = False,
    account_id: Annotated[str | None, Parameter(name="account")] = None,
) -> None:
    """List share codes."""
    config = get_config()
    collected: list[tuple[str, Shocker]] = []

    accounts = [account_id] if account_id else config.accounts
    for acct_id in accounts:
        api = utils.get_api_for_account(acct_id)
        with api, console.status(f"Querying [bold]{acct_id}[/bold]...", spinner="bouncingBar"):
            shocker_list = api.list_shockers()
        collected.extend((acct_id, s) for s in shocker_list if s.is_shared)

    if json_mode.get():
        print_output([shocker_json(s, account_id=acct_id) for acct_id, s in collected])
    else:
        by_account: dict[str, list[Shocker]] = {}
        for acct_id, s in collected:
            by_account.setdefault(acct_id, []).append(s)
        for acct_id, shared in by_account.items():
            console.print()
            console.print(f"[bold]{acct_id}[/bold]")
            share_code.code_list(show_info=show_info, shockers=shared)
