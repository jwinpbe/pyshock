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
from pyshock.errors import APIError, CliError, NotAuthorizedError
from pyshock.providers import PROVIDERS

if TYPE_CHECKING:
    from pyshock.cli.config import Config
    from pyshock.models.account import AccountInfo
    from pyshock.models.shocker import Shocker


def _verify_credentials_with_retry(
    credential: str | None,
    provider: str | None,
    *,
    is_tty: bool,
    key: str | None,
) -> tuple[str, str, dict[str, str]]:
    """Verify API credentials with retry on NotAuthorizedError.

    Returns (credential, provider, creds) on success.
    Raises SystemExit(1) after max attempts.
    """
    from pyshock.cli.commands.init_creds import prompt_credentials

    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        if credential is None:
            credential, provider = prompt_credentials(is_tty=is_tty)
        spec = PROVIDERS.get(provider or "pishock")
        if spec is None:
            console_err.print(f"[red]Unknown provider '{provider or 'pishock'}'.[/red]")
            raise SystemExit(1) from None
        creds = {spec.cred_key: credential}
        try:
            with (
                spec.client_cls(**creds) as api,
                console.status("Verifying credentials...", spinner="bouncingBar"),
            ):
                api.get_account()
            return credential, provider or "pishock", creds
        except NotAuthorizedError as e:
            if key is not None:
                console_err.print(f"[red]{e.message}[/red]")
                raise SystemExit(1) from None
            if attempt >= max_attempts:
                console_err.print("[bold red]Failed to authorize after 3 attempts[/bold red]")
                raise SystemExit(1) from None
            console_err.print(f"[red]{e.message}[/red]")
            console_err.print(f"[yellow]Attempt {attempt}/{max_attempts} failed, please try again.[/yellow]")
            credential = None
    raise SystemExit(1)


def _fetch_shockers(creds: dict[str, str], provider: str) -> list[Shocker]:
    """Build API client and fetch shockers from the provider.

    Args:
        creds: Keyword arguments to pass to the client constructor.
        provider: Provider key (e.g. "pishock" / "openshock").

    Returns:
        List of shockers from the API.

    Raises:
        SystemExit(1): If the provider is unknown (corrupted config).
    """
    spec = PROVIDERS.get(provider)
    if spec is None:
        console_err.print(f"[red]Unknown provider '{provider}'.[/red]")
        raise SystemExit(1) from None
    with (
        spec.client_cls(**creds) as api,
        console.status(
            f"Credentials verified! Fetching information from {spec.label} API...",
            spinner="bouncingBar",
        ),
    ):
        return list(api.list_shockers())


def _register_shockers(config: Config, account_id: str, all_shockers: list[Shocker]) -> None:
    """Write shockers to the config and auto-set a default if there's only one."""
    config.refresh_account_shockers(account_id, all_shockers)
    all_shocker_ids = list(config.shocker_index.keys())
    if len(all_shocker_ids) == 1 and not config.default_shocker_id:
        config.default_shocker_id = all_shocker_ids[0]
    config.save()


def auth(
    *,
    force: bool = False,
    key: Annotated[str | None, Parameter(name="key")] = None,
    account_id: Annotated[str | None, Parameter(name="account")] = None,
    json_output: Annotated[bool, Parameter(name="json")] = False,
) -> None:
    """Initialize API credentials and fetch shockers.

    Supports adding multiple accounts. Use --account to specify an account ID.
    """
    from rich.prompt import Confirm, Prompt

    from pyshock.cli.commands.init_creds import (
        fix_account_prefix,
        resolve_account_id,
        resolve_credential,
    )

    config = get_config()
    json_mode.set(json_output)
    is_tty = terminal_check.isatty()

    try:
        credential, provider = resolve_credential(key)
    except CliError as e:
        console_err.print(f"[red]{e}[/red]")
        raise SystemExit(1) from None

    user_provided_id = account_id is not None
    account_id = resolve_account_id(config, provider or "pishock", account_id, force=force)
    if account_id is None:
        return

    account_id = fix_account_prefix(config, account_id, provider or "pishock", user_provided_id=user_provided_id)

    if is_tty and credential is None:
        from pyshock.cli.display import render_init_welcome

        render_init_welcome()

    credential, provider, creds = _verify_credentials_with_retry(credential, provider, is_tty=is_tty, key=key)

    account_id = fix_account_prefix(config, account_id, provider, user_provided_id=user_provided_id)

    if account_id in config.accounts:
        config.remove_account(account_id)
    config.add_account(account_id, provider, **creds)

    all_shockers = _fetch_shockers(creds, provider)

    if not all_shockers:
        config.save()
        if not json_mode.get():
            console.print("[yellow]No shockers found.[/yellow]")
        return

    _register_shockers(config, account_id, all_shockers)

    all_shocker_ids = list(config.shocker_index.keys())

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
            cred_hint = entry.get("api_key") or entry.get("api_token") or "?"
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


def _verify_one_account(acct_id: str) -> tuple[AccountInfo, str]:
    """Build a session for one account and fetch its account info.

    Returns (account_info, provider). Raises on API/auth errors.
    """
    session = utils.get_session_for_account(acct_id)
    with session.api, console.status(f"Verifying [bold]{acct_id}[/bold]...", spinner="bouncingBar"):
        account = session.api.get_account()
    return account, session.provider


def _render_verify_ok(account: AccountInfo, provider: str, acct_id: str) -> None:
    """Render a successful verification for one account."""
    render_verify_panel(account, provider, acct_id)
    spec = PROVIDERS.get(provider)
    display_label = spec.label if spec else provider.capitalize()
    console.print(f"{display_label} API reports credentials OK for [bold]{acct_id}[/bold].")


def verify(account_id: Annotated[str | None, Parameter(name="account")] = None) -> None:
    """Verify API credentials.

    With --account: verify one account.
    Without --account: verify all accounts.
    """
    from niquests import RequestException

    config = get_config()
    console.print()

    if account_id is not None:
        if config.get_account(account_id) is None:
            console_err.print(f"[red]Account '{account_id}' not found.[/red]")
            raise SystemExit(1)
        session = utils.get_session_for_account(account_id)
        with session.api, console.status(f"Verifying [bold]{account_id}[/bold]...", spinner="bouncingBar"):
            account = session.api.get_account()
        if json_mode.get():
            print_output({
                "ok": True,
                "account_id": account_id,
                "provider": session.provider,
                "username": account.username,
                "user_id": account.user_id,
            })
        else:
            _render_verify_ok(account, session.provider, account_id)
        return

    results: list[dict] = []
    for acct_id in config.accounts:
        try:
            account, provider = _verify_one_account(acct_id)
        except (APIError, CliError, NotAuthorizedError, RequestException) as e:
            if json_mode.get():
                results.append({"ok": False, "account_id": acct_id, "error": str(e)})
            else:
                console_err.print(f"[red]Verification failed for [bold]{acct_id}[/bold]: {e}[/red]")
            continue
        if json_mode.get():
            results.append({
                "ok": True,
                "account_id": acct_id,
                "provider": provider,
                "username": account.username,
                "user_id": account.user_id,
            })
        else:
            _render_verify_ok(account, provider, acct_id)

    if json_mode.get():
        print_output(results)


def devices() -> None:
    """List all devices across all accounts."""
    from rich.prompt import Confirm, Prompt

    config = get_config()
    all_shockers: list[tuple[str, Shocker]] = []

    for acct_id in config.accounts:
        session = utils.get_session_for_account(acct_id)
        with session.api, console.status(f"Querying [bold]{acct_id}[/bold]...", spinner="bouncingBar"):
            shocker_list = session.api.list_shockers()
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
