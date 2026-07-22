"""CLI utility functions."""

from __future__ import annotations

from contextlib import nullcontext
from sys import stdin as terminal_check
from typing import TYPE_CHECKING

from rich.prompt import Prompt as RichPrompt

from pyshock.cli.config import get_config
from pyshock.cli.context import json_mode
from pyshock.cli.display import console, console_err
from pyshock.errors import CliError
from pyshock.protocols import Session, ShockerClient
from pyshock.providers import PROVIDERS

if TYPE_CHECKING:
    from inspect import BoundArguments

    from pyshock.cli.config import Config
    from pyshock.models.operation import OperationName, ShockerOperation


def validate_duration(dur: float, provider: str) -> int:
    """Normalise and validate a duration value for a provider.

    Durations < 16 are treated as seconds and converted to milliseconds.
    Range depends on provider.

    Args:
        dur: Duration in seconds (<16) or milliseconds (>=16).
        provider: API provider ("pishock" or "openshock").

    Returns:
        Duration in milliseconds.

    Raises:
        CliError: If duration is out of range.
    """
    spec = PROVIDERS.get(provider)
    if spec is None:
        raise CliError(f"Unknown provider '{provider}'.")
    min_ms = spec.min_duration_ms
    max_ms = spec.max_duration_ms
    if dur < 16:  # ruff:ignore[magic-value-comparison]
        dur = dur * 1000
    if dur < min_ms or dur > max_ms:
        raise CliError(f"Duration must be {min_ms}-{max_ms}ms (or {min_ms / 1000:g}-{max_ms / 1000:g}s).")
    return int(dur)


def resolve_account(
    shocker_id: str | None = None,
    account_id: str | None = None,
) -> str:
    """Resolve the account ID for an operation.

    Priority: account_id > shocker_id (via shocker_index) > default_shocker_id > raise.

    Args:
        shocker_id: Optional shocker ID to resolve from.
        account_id: Optional explicit account ID.

    Returns:
        The resolved account ID.

    Raises:
        CliError: If no account can be resolved.
    """
    config = get_config()

    if account_id is not None:
        if account_id not in config.accounts:
            raise CliError(f"Account '{account_id}' not found.")
        return account_id

    if shocker_id is not None:
        resolved = config.shocker_index.get(shocker_id)
        if resolved is not None:
            return resolved

    default = config.default_shocker_id
    if default is not None:
        resolved = config.shocker_index.get(default)
        if resolved is not None:
            return resolved

    raise CliError("No account resolved. Run 'pyshock auth' to configure accounts.")


def get_session_for_account(account_id: str) -> Session:
    """Build a Session from an account entry (single config lookup).

    Args:
        account_id: The account ID to build the session for.

    Returns:
        A Session with the API client and provider.

    Raises:
        CliError: If the account is not found, has an unknown provider,
            or lacks credentials.
    """
    config = get_config()
    entry = config.get_account(account_id)
    if entry is None:
        raise CliError(f"Account '{account_id}' not found.")

    provider = entry.get("provider", "")
    spec = PROVIDERS.get(provider)
    if spec is None:
        raise CliError(f"Unknown provider '{provider}' for account '{account_id}'.")

    cred = entry.get(spec.cred_key)
    if not cred:
        if provider == "openshock":
            raise CliError(
                f"OpenShock account '{account_id}' requires an API token. "
                f"Re-authenticate it with 'pyshock auth --account {account_id} --force'."
            )
        raise CliError(f"Account '{account_id}' missing {spec.label} API key.")
    api = spec.client_cls(**{spec.cred_key: cred})
    return Session(api=api, account_id=account_id, provider=provider)


def resolve_shocker_id(api: ShockerClient) -> str:
    """Resolve shocker_id: config default > solo shocker > error.

    Args:
        api: The API client instance.

    Returns:
        The resolved shocker id (string).

    Raises:
        CliError: If multiple shockers exist and no default is set.
    """
    config = get_config()

    if config.default_shocker_id:
        return config.default_shocker_id

    all_shockers = api.list_shockers()
    if len(all_shockers) == 1:
        return all_shockers[0].shocker_id

    raise CliError("Multiple shockers found. Specify --shocker-id or run 'pyshock auth' to set a default.")


def send_operation(
    session: Session,
    shocker_id: str | None,
    operation: ShockerOperation,
    duration: float,
    intensity: int,
) -> None:
    """Send an operation to a shocker.

    Validates duration, resolves shocker id, calls API.

    Args:
        session: The active session with API client and provider.
        shocker_id: Shocker id, or None to auto-resolve.
        operation: Operation type.
        duration: Duration in seconds or milliseconds.
        intensity: Intensity 0-100.
    """
    duration = validate_duration(duration, session.provider)
    resolved_id = shocker_id if shocker_id is not None else resolve_shocker_id(session.api)
    label = operation.name.capitalize()

    ctx = console.status(f"Sending {label.lower()}...", spinner="bouncingBar") if not json_mode.get() else nullcontext()
    with ctx:
        session.api.operate_shocker(
            shocker=resolved_id,
            operation=operation,
            duration=duration,
            intensity=intensity,
        )

    from pyshock.cli.display import render_operation_result

    render_operation_result(resolved_id, label, duration, intensity)


def confirm_operation(label: OperationName) -> None:
    """Prompt for confirmation with an 'always' option.

    Args:
        label: Operation label to display.

    Raises:
        SystemExit: On 'n' (abort).
    """
    config = get_config()

    if not config.confirmation_enabled(label):
        return

    answer = RichPrompt.ask(
        f"Send {label}? (y)es / (N)o / Yes, (d)on't ask again.",
        choices=["y", "n", "D"],
        default="n",
    ).lower()
    if answer == "n":
        raise SystemExit(0)
    if answer == "d":
        config.set_confirmation(label, enabled=False)
        config.save()


def resolve_account_interactive(config: Config, bound: BoundArguments, account_id: str | None) -> str:
    """Resolve account ID from: --account > shocker index > default > interactive prompt.

    Raises SystemExit(1) on failure.
    """
    if account_id is not None:
        return account_id

    shocker_id = bound.kwargs.get("shocker_id")
    if shocker_id and isinstance(shocker_id, str):
        resolved = config.shocker_index.get(shocker_id)
        if resolved is not None:
            return resolved

    if config.default_shocker_id:
        resolved = config.shocker_index.get(config.default_shocker_id)
        if resolved is not None:
            return resolved

    if not terminal_check.isatty():
        console_err.print("[red]No terminal detected. Use --account or set a default shocker.[/red]")
        raise SystemExit(1)

    display_name_to_acct = {
        f"{acct_id} — {s.get('name', '?')} ({s.get('shocker_id', '?')[:8]}...)": acct_id
        for acct_id, entry in config.accounts.items()
        for s in entry.get("shockers", [])
    }
    if not display_name_to_acct:
        console_err.print("[red]No shockers found. Run 'pyshock devices' to refresh.[/red]")
        raise SystemExit(1)
    choice = RichPrompt.ask("Select shocker", choices=list(display_name_to_acct))
    return display_name_to_acct[choice]


def build_session(config: Config, bound: BoundArguments, account_id: str | None) -> Session:
    """Resolve account and return a Session for the command."""
    resolved_account = resolve_account_interactive(config, bound, account_id)
    return get_session_for_account(resolved_account)
