"""CLI utility functions."""

from __future__ import annotations

from contextlib import nullcontext
from contextvars import ContextVar
from sys import stdin as terminal_check
from typing import TYPE_CHECKING

from rich.prompt import Prompt as RichPrompt

from pyshock.cli.config import get_config
from pyshock.cli.context import _current_account_id, json_mode
from pyshock.cli.display import console, console_err
from pyshock.constants import (
    MAX_INTENSITY,
    OPENSHOCK_MAX_DURATION_MS,
    OPENSHOCK_MIN_DURATION_MS,
    PISHOCK_MAX_DURATION_MS,
    PISHOCK_MIN_DURATION_MS,
)
from pyshock.errors import CliError
from pyshock.openshockapi import OpenShockAPI
from pyshock.pishockapi import PiShockAPI

if TYPE_CHECKING:
    from inspect import BoundArguments

    from pyshock.cli.config import Config
    from pyshock.models.operation import OperationName, ShockerOperation

_ApiClient = PiShockAPI | OpenShockAPI


def validate_duration(dur: float, *, min_ms: int, max_ms: int) -> int:
    """Normalise and validate a duration value.

    Durations < 16 are treated as seconds and converted to milliseconds.
    """
    if dur < 16:  # noqa: PLR2004
        dur = dur * 1000
    if dur < min_ms or dur > max_ms:
        raise CliError(f"Duration must be {min_ms}-{max_ms}ms (or {min_ms / 1000:g}-{max_ms / 1000:g}s).")
    return int(dur)


def validate_operation_params(duration: float, intensity: int, provider: str = "pishock") -> int:
    """Validate and normalise duration/intensity for an operation.

    Durations < 16 are treated as seconds. Range depends on provider.

    Args:
        duration: Duration in seconds (<16) or milliseconds (>=16).
        intensity: Intensity 0-100.
        provider: API provider ("pishock" or "openshock").

    Returns:
        Duration in milliseconds.

    Raises:
        CliError: If duration or intensity is out of range.
    """
    if intensity < 0 or intensity > MAX_INTENSITY:
        raise CliError("Intensity must be 0-100.")
    min_dur = OPENSHOCK_MIN_DURATION_MS if provider == "openshock" else PISHOCK_MIN_DURATION_MS
    max_dur = OPENSHOCK_MAX_DURATION_MS if provider == "openshock" else PISHOCK_MAX_DURATION_MS
    return validate_duration(duration, min_ms=min_dur, max_ms=max_dur)


_current_api_client: ContextVar[_ApiClient] = ContextVar("_current_api_client")


def get_api() -> _ApiClient:
    """Return the current API client for the active request.

    Returns:
        The current API client (_ApiClient).

    Raises:
        LookupError: If no client is set.
    """
    return _current_api_client.get()


def set_api_client(client: _ApiClient) -> None:
    """Set the current API client for the active request context.

    Args:
        client: The API client instance.
    """
    _current_api_client.set(client)


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


def get_api_for_account(account_id: str) -> _ApiClient:
    """Build an API client from an account entry.

    Args:
        account_id: The account ID to build the client for.

    Returns:
        An _ApiClient instance.

    Raises:
        CliError: If the account is not found or lacks credentials.
    """
    config = get_config()
    entry = config.get_account(account_id)
    if entry is None:
        raise CliError(f"Account '{account_id}' not found.")

    provider = entry.get("provider", "")

    if provider == "pishock":
        api_key = entry.get("api_key")
        if not api_key:
            raise CliError(f"Account '{account_id}' missing PiShock API key.")
        return PiShockAPI(api_key)

    if provider == "openshock":
        api_token = entry.get("api_token")
        if not api_token:
            raise CliError(f"Account '{account_id}' missing OpenShock API token.")
        return OpenShockAPI(api_token=api_token)

    raise CliError(f"Unknown provider '{provider}' for account '{account_id}'.")


def resolve_shocker_id(api: _ApiClient) -> str:
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
    shocker_id: str | None,
    operation: ShockerOperation,
    duration: float,
    intensity: int,
) -> None:
    """Send an operation to a shocker.

    Validates duration, resolves shocker id, calls API.

    Args:
        shocker_id: Shocker id, or None to auto-resolve.
        operation: Operation type.
        duration: Duration in seconds or milliseconds.
        intensity: Intensity 0-100.
    """
    config = get_config()
    account_id = _current_account_id.get()
    entry = config.get_account(account_id)
    if entry is None:
        raise CliError(f"Account '{account_id}' not found.")

    provider = entry.get("provider", "pishock")
    duration = validate_operation_params(duration, intensity, provider)
    api = get_api()
    resolved_id = shocker_id if shocker_id is not None else resolve_shocker_id(api)
    label = operation.name.capitalize()

    ctx = console.status(f"Sending {label.lower()}...", spinner="bouncingBar") if not json_mode.get() else nullcontext()
    with ctx:
        api.operate_shocker(
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


def prepare_api_session(config: Config, bound: BoundArguments, account_id: str | None) -> tuple[_ApiClient, str]:
    """Resolve account, create API client, and set it as the current session."""
    resolved_account = resolve_account_interactive(config, bound, account_id)
    api = get_api_for_account(resolved_account)
    set_api_client(api)
    _current_account_id.set(resolved_account)
    return api, resolved_account
