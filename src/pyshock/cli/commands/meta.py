"""Meta commands for PyShock CLI (init, logout, confirm, default, verify, devices)."""

from __future__ import annotations

from sys import stdin as terminal_check
from typing import TYPE_CHECKING, Annotated

from cyclopts import Parameter

from pyshock.cli import utils
from pyshock.cli.config import get_config
from pyshock.cli.context import json_mode
from pyshock.cli.display import (
    console,
    console_err,
    print_output,
    render_confirmation_panel,
    render_shocker_table,
    render_shocker_table_by_account,
    render_verify_panel,
    shocker_json,
)
from pyshock.errors import APIError, NotAuthorizedError
from pyshock.pishockapi import PiShockAPI

if TYPE_CHECKING:
    from pyshock.models.shocker import Shocker


def auth(  # noqa: PLR0915
    *,
    force: bool = False,
    api_key: Annotated[str | None, Parameter(name="pishock-key")] = None,
    account_id: Annotated[str | None, Parameter(name="account")] = None,
    json_output: Annotated[bool, Parameter(name="json")] = False,
) -> None:
    """Initialize PiShock API credentials and fetch shockers.

    Supports adding multiple accounts. Use --account to specify an account ID.
    """
    from rich.prompt import Confirm, Prompt

    from pyshock.cli.commands.init_creds import (
        fix_account_prefix,
        prompt_pishock_credentials,
        resolve_account_id,
        resolve_provider,
    )

    config = get_config()
    json_mode.set(json_output)

    user_provided_id = account_id is not None
    provider = resolve_provider(None)
    account_id = resolve_account_id(config, provider, account_id, force=force)
    if account_id is None:
        return

    account_id = fix_account_prefix(config, account_id, provider, user_provided_id=user_provided_id)

    is_tty = terminal_check.isatty()

    from os import environ as env_vars

    if is_tty and not env_vars.get("PISHOCK_API_KEY"):
        from pyshock.cli.display import render_init_welcome

        render_init_welcome(provider="pishock")

    api_cls = PiShockAPI

    creds: dict = {}
    skip_env = False
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        creds = prompt_pishock_credentials(api_key=api_key, is_tty=is_tty, skip_env=skip_env)
        try:
            with (
                api_cls(**creds) as api,
                console.status("Verifying credentials...", spinner="bouncingBar"),
            ):
                api.get_account()
            break
        except NotAuthorizedError as e:
            if attempt < max_attempts:
                console_err.print(f"[red]{e.message}[/red]")
                console_err.print(f"[yellow]Attempt {attempt}/{max_attempts} failed, please try again.[/yellow]")
                skip_env = True
            else:
                console_err.print("[bold red]Failed to authorize after 3 attempts[/bold red]")
                raise SystemExit(1) from None

    if account_id in config.accounts:
        config.remove_account(account_id)
    config.add_account(account_id, provider, **creds)

    with (
        api_cls(**creds) as api,
        console.status(
            "Credentials verified! Fetching information from PiShock API...",
            spinner="bouncingBar",
        ),
    ):
        all_shockers = api.list_shockers()

    if not all_shockers:
        config.save()
        if not json_mode.get():
            console.print("[yellow]No shockers found.[/yellow]")
        return

    config.refresh_account_shockers(account_id, all_shockers)

    all_shocker_ids = list(config.shocker_index.keys())
    if len(all_shocker_ids) == 1 and not config.default_shocker_id:
        config.default_shocker_id = all_shocker_ids[0]

    config.save()

    if json_mode.get():
        print_output({"shockers": [shocker_json(s) for s in all_shockers]})
    else:
        render_shocker_table(all_shockers, f"Found [bold]{len(all_shockers)}[/bold] shocker(s):")

        if (
            len(all_shocker_ids) > 1
            and not config.default_shocker_id
            and Confirm.ask("Multiple shockers found. Set a default?", default=True)
        ):
            console.print()
            default_name = Prompt.ask("Choose a default:", choices=[s.name for s in all_shockers])
            default_shocker = next(s for s in all_shockers if s.name == default_name)
            config.default_shocker_id = default_shocker.shocker_id
            config.save()
            console.print(f"Default shocker set to [bold]{default_shocker.shocker_id}[/bold].")

    if not json_mode.get():
        console.print(f"[green]Account [bold]{account_id}[/bold] saved successfully.[/green]")
        console.print()


def logout(account_id: Annotated[str | None, Parameter(name="account")] = None) -> None:
    """Remove saved account(s).

    With --account: remove that specific account.
    Without --account: prompt to select an account to remove.
    """
    from rich.prompt import Confirm, Prompt

    config = get_config()

    if not config.accounts:
        console.print("[yellow]No accounts configured.[/yellow]")
        return

    if account_id is None:
        if not terminal_check.isatty():
            console_err.print("[red]Cannot prompt without a terminal. Use --account.[/red]")
            raise SystemExit(1)
        choices = list(config.accounts.keys())
        console.print()
        for acct_id in choices:
            entry = config.accounts[acct_id]
            provider = entry.get("provider", "?")
            shocker_count = len(entry.get("shockers", []))
            cred_hint = entry.get("api_key") or "?"
            user_hint = cred_hint[:12]
            console.print(f"  [bold]{acct_id}[/bold] ({provider}, {user_hint}, {shocker_count} shocker(s))")
        console.print()
        account_id = Prompt.ask("Select account to remove", choices=choices)

    config.remove_account(account_id)

    if config.accounts and not config.default_shocker_id:
        all_ids = list(config.shocker_index.keys())
        if all_ids and terminal_check.isatty() and Confirm.ask("Set a new default shocker?", default=True):
            shocker_options = {
                f"{s.get('name', '?')} ({acct_id})": s["shocker_id"]
                for acct_id in config.accounts
                for s in config.accounts[acct_id].get("shockers", [])
            }
            if shocker_options:
                config.default_shocker_id = shocker_options[
                    Prompt.ask("Choose a default:", choices=list(shocker_options))
                ]

    config.save()
    console.print(f"[green]Account [bold]{account_id}[/bold] removed.[/green]")


def confirm(
    *operation: str,
) -> None:
    """Show or toggle confirmation prompt settings.

    No args: show global confirmation settings.
    With <operation>: toggle global default for that operation.
    """
    config = get_config()
    ops = ["shock", "beep", "vibrate"]

    op_value = " ".join(operation) if operation else None

    if op_value is not None:
        op = op_value.lower()
        if op not in ops:
            console.print()
            console.print(
                "[red]Unknown operation:[/red] "
                f"[bold red]{op_value}[/bold red]"
                "\n\n"
                "[red]Available commands:[/red] "
                "[bold red on white]shock[/bold red on white][red], "
                "[/red][bold red on white]beep[/bold red on white][red], "
                "or "
                "[/red][bold red on white]vibrate[/bold red on white][red].[/red]"
            )
            console.print()
            raise SystemExit(1)
        enabled = config.confirmation_enabled(op)
        config.set_confirmation(op, enabled=not enabled)
        config.save()
        new_status = "enabled" if not enabled else "disabled"
        console.print(f"Confirmation for [bold]{op}[/bold] is now [bold]{new_status}[/bold].")
    else:
        render_confirmation_panel(
            [(op, config.confirmation_enabled(op)) for op in ops],
        )


def default(shocker_id: str | None = None, /, *, unset: bool = False) -> None:
    """Manage default shocker.

    No args: show current default + its account.
    With <shocker_id>: set default to that shocker.
    With --unset: clear default.
    """
    config = get_config()

    if unset:
        config.default_shocker_id = None
        config.save()
        console.print("[green]Default shocker cleared.[/green]")
        return

    if shocker_id is None:
        if config.default_shocker_id:
            acct_id = config.shocker_index.get(config.default_shocker_id, "?")
            console.print(
                f"Default shocker: [bold]{config.default_shocker_id}[/bold] (account: [bold]{acct_id}[/bold])"
            )
        else:
            console.print("[yellow]No default shocker set.[/yellow]")
        return

    if shocker_id not in config.shocker_index:
        console_err.print(f"[red]Shocker '{shocker_id}' not found. Run 'pyshock devices' to refresh.[/red]")
        raise SystemExit(1)
    config.default_shocker_id = shocker_id
    config.save()
    console.print(f"[green]Default shocker set to [bold]{shocker_id}[/bold].[/green]")


def verify(account_id: Annotated[str | None, Parameter(name="account")] = None) -> None:
    """Verify API credentials.

    With --account: verify one account.
    Without --account: verify all accounts.
    """
    from niquests import RequestException

    config = get_config()
    console.print()

    if account_id is not None:
        entry = config.get_account(account_id)
        if entry is None:
            console_err.print(f"[red]Account '{account_id}' not found.[/red]")
            raise SystemExit(1)
        provider = entry.get("provider", "pishock")
        api = utils.get_api_for_account(account_id)
        with api, console.status(f"Verifying [bold]{account_id}[/bold]...", spinner="bouncingBar"):
            account = api.get_account()
        if json_mode.get():
            print_output({
                "ok": True,
                "account_id": account_id,
                "provider": provider,
                "username": account.username,
                "user_id": account.user_id,
            })
        else:
            render_verify_panel(account, provider, account_id)
            console.print(f"PiShock API reports credentials OK for [bold]{account_id}[/bold].")
        return

    results: list[dict] = []
    for acct_id, entry in config.accounts.items():
        prov = entry.get("provider", "pishock")
        api = utils.get_api_for_account(acct_id)
        try:
            with api, console.status(f"Verifying [bold]{acct_id}[/bold]...", spinner="bouncingBar"):
                account = api.get_account()
            if json_mode.get():
                results.append({
                    "ok": True,
                    "account_id": acct_id,
                    "provider": prov,
                    "username": account.username,
                    "user_id": account.user_id,
                })
            else:
                render_verify_panel(account, prov, acct_id)
                console.print(f"PiShock API reports credentials OK for [bold]{acct_id}[/bold].")
        except (APIError, NotAuthorizedError, RequestException) as e:
            if json_mode.get():
                results.append({"ok": False, "account_id": acct_id, "error": str(e)})
            else:
                console_err.print(f"[red]Verification failed for [bold]{acct_id}[/bold]: {e}[/red]")

    if json_mode.get():
        print_output(results)


def devices() -> None:
    """List all devices across all accounts."""
    from rich.prompt import Confirm, Prompt

    config = get_config()
    all_shockers: list[tuple[str, Shocker]] = []

    for acct_id in config.accounts:
        api = utils.get_api_for_account(acct_id)
        with api, console.status(f"Querying [bold]{acct_id}[/bold]...", spinner="bouncingBar"):
            shocker_list = api.list_shockers()
        config.refresh_account_shockers(acct_id, shocker_list)
        all_shockers.extend([(acct_id, s) for s in shocker_list])

    config.save()

    if not all_shockers:
        if json_mode.get():
            print_output([])
        else:
            console.print("No devices found.")
        return

    all_ids = list(config.shocker_index.keys())
    if len(all_ids) == 1 and not config.default_shocker_id:
        config.default_shocker_id = all_ids[0]
        config.save()
    elif len(all_ids) > 1 and not config.default_shocker_id and terminal_check.isatty():
        if Confirm.ask("Multiple shockers found. Set a default?", default=True):
            console.print()
            name_to_id = {s.name: s.shocker_id for _, s in all_shockers}
            choices = list(name_to_id.keys())
            default_name = Prompt.ask("Choose a default:", choices=choices)
            config.default_shocker_id = name_to_id[default_name]
            config.save()

    if json_mode.get():
        output = []
        for acct_id, s in all_shockers:
            output.append(shocker_json(s, account_id=acct_id))
        print_output(output)
        return

    all_shockers_by_account: dict[str, list] = {}
    for acct_id, s in all_shockers:
        all_shockers_by_account.setdefault(acct_id, []).append(s)

    render_shocker_table_by_account(all_shockers_by_account)
