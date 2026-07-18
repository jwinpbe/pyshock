"""Share code management CLI commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyshock.cli.display import console, render_compact_code_table, render_full_code_table
from pyshock.errors import CliError
from pyshock.openshockapi import OpenShockAPI

if TYPE_CHECKING:
    from pyshock.models.shocker import Shocker
    from pyshock.pishockapi import PiShockAPI


def code_add(code: str, api: PiShockAPI | OpenShockAPI) -> None:
    """Claim a share code.

    Args:
        code: Share code string.
        api: API client.

    Raises:
        CliError: If the code is empty.
    """
    if not code or not code.strip():
        raise CliError("Share code cannot be empty.")

    code = code.strip()

    with console.status("Adding share code...", spinner="bouncingBar"):
        if isinstance(api, OpenShockAPI):
            if not api.is_cookie_auth:
                raise CliError("OpenShock share codes require cookie auth. Use a PiShock account instead.")
            api.link_share_code(code)
        else:
            api.add_share_code(code)
    console.print(f"Share code '[bold]{code}[/bold]' added successfully.")


def code_delete(share_code: str, api: PiShockAPI | OpenShockAPI) -> None:
    """Remove a share code.

    Args:
        share_code: Share code string.
        api: API client.
    """
    with console.status("Deleting share code...", spinner="bouncingBar"):
        if isinstance(api, OpenShockAPI):
            if not api.is_cookie_auth:
                raise CliError("OpenShock share codes require cookie auth. Use a PiShock account instead.")
            api.unlink_share_code(share_code)
        else:
            shocker = api.get_shocker_by_share_code(share_code)
            if shocker.share_id is None:
                raise CliError("PiShock did not return an id for this share.")
            api.delete_share(shocker.share_id)
    console.print(f"Share code '[bold]{share_code}[/bold]' deleted successfully.")


def code_list(*, show_info: bool, shockers: list[Shocker]) -> None:
    """List shared shockers.

    Args:
        show_info: Show additional shocker details.
        shockers: Pre-fetched list of shockers to filter and display.
    """
    shared = [s for s in shockers if s.is_shared]

    if not shared:
        console.print("No share codes found.")
        return

    console.print()
    if show_info:
        render_full_code_table(shared)
    else:
        render_compact_code_table(shared)
