"""Init credential helpers for PyShock CLI."""

from __future__ import annotations

from sys import stdin as terminal_check
from typing import TYPE_CHECKING

from pyshock.cli.display import console_err

if TYPE_CHECKING:
    from pyshock.cli.config import Config


def resolve_account_id(config: Config, _provider: str | None, account_id: str | None, *, force: bool) -> str | None:
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

    prefix = "pishock"
    n = 1
    while f"{prefix}_{n}" in config.accounts:
        n += 1
    return f"{prefix}_{n}"


def resolve_provider(_provider: str | None = None) -> str:
    """Resolve API provider: use 'pishock'."""
    return "pishock"


def fix_account_prefix(config: Config, account_id: str, provider: str, *, user_provided_id: bool) -> str:
    """Re-assign account_id prefix if auto-generated before provider was known."""
    if user_provided_id or account_id.startswith(provider):
        return account_id

    n = 1
    while f"{provider}_{n}" in config.accounts:
        n += 1
    return f"{provider}_{n}"


def prompt_pishock_credentials(
    *,
    api_key: str | None = None,
    is_tty: bool,
    skip_env: bool = False,
) -> dict:
    """Prompt for PiShock credentials.

    When skip_env is True, bypasses environment variables and always prompts interactively.
    When api_key is provided, it takes priority over env vars.

    Returns (creds, api_kwargs) dicts.
    """
    from os import environ as env_vars

    from rich.prompt import Prompt

    if api_key is None and not skip_env:
        api_key = env_vars.get("PISHOCK_API_KEY")
    if not api_key:
        if not is_tty:
            console_err.print("[red]Cannot prompt without a terminal. Use --pishock-key.[/red]")
            raise SystemExit(1)
        api_key = Prompt.ask("PiShock API key", password=True).strip()
    return {"api_key": api_key}
