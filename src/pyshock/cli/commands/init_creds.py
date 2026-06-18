"""Init credential helpers for PyShock CLI."""

from __future__ import annotations

import uuid
from os import environ as env_vars
from sys import stdin as terminal_check
from typing import TYPE_CHECKING

from pyshock.cli.display import console_err
from pyshock.constants import BASE62_CHARS, MAX_PROMPT_ATTEMPTS, OPENSHOCK_TOKEN_LENGTH
from pyshock.errors import CliError

if TYPE_CHECKING:
    from pyshock.cli.config import Config


def resolve_account_id(config: Config, provider: str | None, account_id: str | None, *, force: bool) -> str | None:
    """Determine account ID for init.

    Returns the resolved account_id, or None if the user declined
    'Add another account?' (signals early exit to the caller).
    """
    from rich.prompt import Confirm

    if account_id is not None:
        if account_id in config.accounts and not force:
            console_err.print(f"[red]Account '{account_id}' already exists. Use --force to overwrite.[/red]")
            raise SystemExit(1)
        return account_id

    if (
        config.accounts
        and not force
        and terminal_check.isatty()
        and not Confirm.ask("Add another account?", default=True)
    ):
        return None

    prefix = "openshock" if provider == "openshock" else "pishock"
    n = 1
    while f"{prefix}_{n}" in config.accounts:
        n += 1
    return f"{prefix}_{n}"


def fix_account_prefix(config: Config, account_id: str, provider: str, *, user_provided_id: bool) -> str:
    """Re-assign account_id prefix if auto-generated before provider was known."""
    if user_provided_id or account_id.startswith(provider):
        return account_id

    n = 1
    while f"{provider}_{n}" in config.accounts:
        n += 1
    return f"{provider}_{n}"


def resolve_provider(credential: str) -> str:
    """Resolve API provider from credential shape."""
    try:
        uuid.UUID(credential)
        return "pishock"
    except ValueError:
        pass
    if len(credential) == OPENSHOCK_TOKEN_LENGTH and set(credential).issubset(BASE62_CHARS):
        return "openshock"
    raise CliError("Unrecognized credential format. Expected a PiShock UUID or a 64-character OpenShock token.")


def resolve_credential(key: str | None, *, skip_env: bool = False) -> tuple[str | None, str | None]:
    """Resolve credential and provider from flag, env vars, or signal prompt.

    Returns (credential, provider) — (None, None) signals the caller should prompt.
    """
    if key is not None:
        return (key, resolve_provider(key))
    if not skip_env:
        pishock = env_vars.get("PISHOCK_API_KEY")
        openshock = env_vars.get("OPENSHOCK_API_TOKEN")
        if pishock and openshock:
            raise CliError("Both PISHOCK_API_KEY and OPENSHOCK_API_TOKEN are set. Use --key to disambiguate.")
        if pishock:
            return (pishock, "pishock")
        if openshock:
            return (openshock, "openshock")
    return (None, None)


def prompt_credentials(*, is_tty: bool) -> tuple[str, str]:
    """Prompt for API key, validate by shape, return (credential, provider)."""
    from rich.prompt import Prompt

    if not is_tty:
        console_err.print("[red]Cannot prompt without a terminal. Use --key.[/red]")
        raise SystemExit(1)

    for attempt in range(1, MAX_PROMPT_ATTEMPTS + 1):
        value = Prompt.ask("API key", password=True).strip()
        try:
            provider = resolve_provider(value)
        except CliError as e:
            console_err.print(f"[red]{e}[/red]")
            if attempt < MAX_PROMPT_ATTEMPTS:
                console_err.print(f"[yellow]Attempt {attempt}/{MAX_PROMPT_ATTEMPTS} failed, please try again.[/yellow]")
            else:
                console_err.print("[bold red]Failed to recognize credential format after 3 attempts.[/bold red]")
                raise SystemExit(1) from None
        else:
            return (value, provider)

    raise SystemExit(1)
