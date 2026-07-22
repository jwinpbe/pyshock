"""CLI display helpers."""

from __future__ import annotations

import os
from dataclasses import asdict, fields
from json import dumps as json_dumps
from typing import TYPE_CHECKING, Any

from rich import box
from rich.cells import cell_len
from rich.console import Console, ConsoleOptions, RenderResult
from rich.measure import Measurement
from rich.padding import Padding
from rich.panel import Panel
from rich.segment import Segment
from rich.style import Style as RichStyle
from rich.table import Table

from pyshock.cli.context import json_mode
from pyshock.constants import DURATION_DISPLAY_THRESHOLD_MS, OPENSHOCK_MAX_DURATION_MS
from pyshock.errors import APIError

if TYPE_CHECKING:
    from pyshock.models.account import AccountInfo
    from pyshock.models.shocker import Shocker

console = Console()
console_err = Console(stderr=True)


def _is_unicode_terminal() -> bool:
    """Return False for non-UTF-8 encodings or cmd.exe without Windows Terminal."""
    if console.encoding != "utf-8":
        return False
    return not (os.name == "nt" and "WT_SESSION" not in os.environ)


_TERMINAL_HAS_UNICODE = _is_unicode_terminal()

CHECK_MARK: str = "✔" if _TERMINAL_HAS_UNICODE else "Y"
X_MARK: str = "✖" if _TERMINAL_HAS_UNICODE else "N"


def _styled_table(**kwargs: Any) -> Table:
    defaults: dict[str, Any] = {
        "show_header": False,
        "padding": (0, 1),
        "box": box.ROUNDED,
        "border_style": "dim white",
    }
    defaults.update(kwargs)
    return Table(**defaults)


def _styled_panel(renderable: str | Table, *, title: str | None = None, style: str = "blue", **kwargs: Any) -> Panel:
    defaults: dict[str, Any] = {
        "border_style": style,
        "expand": False,
        "padding": (1, 1, 1, 2),
    }
    defaults.update(kwargs)
    return Panel(renderable, title=title, **defaults)


def _styled_print(renderable: Panel | Table, *, err: bool = False) -> None:
    out = console_err if err else console
    out.print()
    out.print(Padding(renderable, (0, 0, 0, 2)))
    out.print()


def error_json(err: BaseException) -> dict[str, str | int]:
    """Build a JSON-serialisable error dict."""
    name = err.__class__.__name__
    out: dict[str, str | int] = {"error": name, "message": str(err)}
    if isinstance(err, APIError) and err.status_code:
        out["status_code"] = err.status_code
    return out


def shocker_json(shocker: Shocker, account_id: str | None = None) -> dict[str, Any]:
    """Convert a Shocker to a JSON dict, dropping internal IDs."""
    excluded_fields = {
        dataclass_field.name for dataclass_field in fields(shocker) if dataclass_field.metadata.get("cli_json_exclude")
    }
    raw_dict = asdict(shocker)
    result = {field_name: value for field_name, value in raw_dict.items() if field_name not in excluded_fields}
    if account_id is not None:
        result["account_id"] = account_id
    return result


class _Badge:
    """
    This class is the result of 2 days of OCD related to rendering badges
    with my desired style as seen in the program.

    I really didn't want to just have the checkmark emoji or whatever like
    every other mass produced AI slop rich cli, I wanted something ~aesthetic~

    Rich renderable that preserves trailing space in styled badge text.

    Rich's table justification strips trailing whitespace from Text objects.
    This renderable outputs raw Segments so rstrip is never called.
    """

    def __init__(self, text: str, style: str) -> None:
        self._text = text
        self._style = RichStyle.parse(style)

    def __rich_measure__(self, _console: Console, _options: ConsoleOptions) -> Measurement:
        width = cell_len(self._text)
        return Measurement(width, width)

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        width = options.max_width
        text_len = cell_len(self._text)
        pad = max(0, (width - text_len) // 2)
        if pad:
            yield Segment(" " * pad)
        yield Segment(self._text, self._style)
        remaining = width - text_len - pad
        if remaining > 0:
            yield Segment(" " * remaining)


def badge(*, value: bool, yes_text: str, no_text: str, yes_fg: str = "black", no_fg: str = "black") -> _Badge:
    """Build a styled green/red status badge.

    If true, it returns a green background with yes_text colored with yes_fg.
    If false, it returns a red background with no_text colored with no_fg."""

    if value:
        style = f"bold {yes_fg} on green"
        label = yes_text
    else:
        style = f"bold {no_fg} on red"
        label = no_text
    return _Badge(label, style)


def _classify_shocker(s: Shocker) -> tuple[str, str]:
    """Return (shock_type, owner_display) for a shocker.

    shock_type: one of "claimed", "owned", "shared", "unknown".
    owner_display: Rich-markup string for the owner column.
    """
    match (s.is_owned, s.is_shared):
        case (True, True):
            return "claimed", f"[bold italic]{s.owned_by}[/bold italic]" if s.owned_by else "—"
        case (True, False):
            return "owned", "[bold italic]you[/bold italic]"
        case (False, True):
            return "shared", f"[bold italic]{s.owned_by}[/bold italic]" if s.owned_by else "—"
        case _:
            return "unknown", "[bold italic]???[/bold italic]"


def print_output(data: Any) -> None:
    """Print data as JSON when json_mode is active."""
    if json_mode.get():
        console.print(json_dumps(data, indent=2))
    else:
        console.print(data)


def render_operation_result(shocker_id: str, label: str, duration_ms: int, intensity: int) -> None:
    """Render the result of a shock/vibrate/beep operation."""
    if json_mode.get():
        console.print(
            json_dumps({
                "ok": True,
                "shocker_id": shocker_id,
                "operation": label,
                "duration_ms": duration_ms,
                "intensity": intensity,
            })
        )
    else:
        console.print(
            f"{label} sent to shocker [bold]{shocker_id}[/bold] "
            f"(duration={duration_ms / 1000:g}s, intensity={intensity})"
        )


def _add_shocker_columns(table: Table) -> None:
    """Add standard shocker table columns."""
    table.add_column("ID", style="bold", width=8, overflow="ellipsis")
    table.add_column("Device Name", style="italic", overflow="ellipsis", no_wrap=True, max_width=16)
    table.add_column("Type", width=8)
    table.add_column("Owner")
    table.add_column("Shock")
    table.add_column("Vibrate")
    table.add_column("Beep")
    table.add_column("Continuous")
    table.add_column("Max duration", justify="center")
    table.add_column("Max intensity")


def _build_shocker_row(s: Shocker) -> tuple:
    """Build a table row for a single shocker."""
    shock_type, owner = _classify_shocker(s)
    shock_status = badge(value=s.can_shock, yes_text=" Access ", no_text=" No Access ")
    vibrate_status = badge(value=s.can_vibrate, yes_text=" Access ", no_text=" No Access ")
    beep_status = badge(value=s.can_beep, yes_text=" Access ", no_text=" No Access ")
    continuous_status = badge(value=s.is_owned or s.can_hold, yes_text=" Access ", no_text=" No Access ")
    return (
        s.shocker_id,
        s.name,
        shock_type,
        owner,
        shock_status,
        vibrate_status,
        beep_status,
        continuous_status,
        (
            "[bold italic]Unlimited[/bold italic]"
            if s.max_duration == OPENSHOCK_MAX_DURATION_MS
            else f"{s.max_duration}s"
            if s.max_duration <= DURATION_DISPLAY_THRESHOLD_MS
            else f"{s.max_duration / 1000:.1f}s"
        ),
        f"{s.max_intensity} / 100",
    )


def render_shocker_table_by_account(shockers_by_account: dict[str, list[Shocker]]) -> None:
    """Print shocker tables grouped by account."""
    for acct_id, shockers in shockers_by_account.items():
        if not shockers:
            continue
        console.print()
        console.print(f"[bold]{acct_id}[/bold]")
        table = _styled_table(
            show_header=True,
            header_style="bold",
        )
        _add_shocker_columns(table)

        for s in shockers:
            table.add_row(*_build_shocker_row(s))

        _styled_print(table)


def render_shocker_table(shockers: list[Shocker], title: str) -> None:
    """Print a table of shockers."""
    table = _styled_table(
        title=title,
        title_justify="center",
        show_header=True,
        header_style="bold",
    )
    _add_shocker_columns(table)

    for s in shockers:
        table.add_row(*_build_shocker_row(s))

    _styled_print(table)


def render_info_table(shocker: Shocker, account_id: str | None = None) -> None:
    """Print a detail table for a single shocker."""
    device_type, owner = _classify_shocker(shocker)

    table = _styled_table(
        title=f"[bold underline]{shocker.name}[/bold underline]",
        title_justify="center",
    )
    table.add_column("", style="bold")
    table.add_column("", justify="center")

    table.add_row("ID", str(shocker.shocker_id))
    if account_id:
        table.add_row("Account", account_id)
    table.add_row("Relationship", device_type)
    table.add_row("Owner", owner)
    table.add_row("", "")
    table.add_row("Shock", badge(value=shocker.can_shock, yes_text=f"  {CHECK_MARK}  ", no_text=f"  {X_MARK}  "))
    table.add_row(
        "Vibrate",
        badge(value=shocker.can_vibrate, yes_text=f"  {CHECK_MARK}  ", no_text=f"  {X_MARK}  "),
    )
    table.add_row("Beep", badge(value=shocker.can_beep, yes_text=f"  {CHECK_MARK}  ", no_text=f"  {X_MARK}  "))
    table.add_row("Pause", badge(value=shocker.can_pause, yes_text=f"  {CHECK_MARK}  ", no_text=f"  {X_MARK}  "))
    table.add_row(
        "Continuous Mode",
        badge(value=shocker.can_hold, yes_text=f"  {CHECK_MARK}  ", no_text=f"  {X_MARK}  "),
    )
    table.add_row("", "")
    table.add_row("Max duration", f"{shocker.max_duration}s")
    table.add_row("Max intensity", f"{shocker.max_intensity} / 100")

    _styled_print(table)


def render_confirmation_panel(
    operations: list[tuple[str, bool]],
) -> None:
    """Print confirmation toggle states."""
    table = _styled_table()
    table.add_column("", style="bold")
    table.add_column("", justify="center")

    for name, enabled in operations:
        table.add_row(
            name.capitalize(),
            badge(value=enabled, yes_text=f"  {CHECK_MARK}  ", no_text=f"  {X_MARK}  "),
        )

    _styled_print(_styled_panel(table, title="Confirmation Settings", title_align="center"))

    console.print("[dim]To toggle: pyshock confirm <shock|beep|vibrate>[/dim]")
    console.print()


def render_compact_code_table(shockers: list[Shocker]) -> None:
    """Print share codes and device names."""
    table = _styled_table(show_edge=False)
    table.add_column("Share Code", justify="center")
    table.add_column("Device Name", justify="center")

    for item in shockers:
        table.add_row(f"[bold]{item.share_code}[/bold]", item.name)

    _styled_print(table)


def render_full_code_table(shockers: list[Shocker]) -> None:
    """Print per-shocker panels with share details."""
    for item in shockers:
        table = _styled_table(
            title=f"[bold underline]{item.name}[/bold underline]",
            title_justify="center",
        )
        table.add_column("", style="bold")
        table.add_column("", justify="center")

        table.add_row("Code", item.share_code)
        table.add_row("", "")
        table.add_row("ID", item.shocker_id)
        table.add_row("Owner", f"[bold italic]{item.owned_by or '—'}[/bold italic]")
        table.add_row("", "")
        table.add_row("Shock", badge(value=item.can_shock, yes_text=f" {CHECK_MARK} ", no_text=f" {X_MARK} "))
        table.add_row("Vibrate", badge(value=item.can_vibrate, yes_text=f" {CHECK_MARK} ", no_text=f" {X_MARK} "))
        table.add_row("Beep", badge(value=item.can_beep, yes_text=f" {CHECK_MARK} ", no_text=f" {X_MARK} "))
        table.add_row("", "")
        table.add_row("Paused?", badge(value=item.paused, yes_text=f" {CHECK_MARK} ", no_text=f" {X_MARK} "))
        table.add_row("Locked?", badge(value=item.locked, yes_text=f" {CHECK_MARK} ", no_text=f" {X_MARK} "))
        table.add_row("", "")
        table.add_row("Max duration", f"{item.max_duration}s")
        table.add_row("Max intensity", f"{item.max_intensity} / 100")

        _styled_print(table)


def render_init_welcome() -> None:
    """Print the init welcome panel (provider-neutral)."""
    _styled_print(
        _styled_panel(
            """\
This tool will help you
configure PyShock and set
up your API credentials.

[bold]PiShock and OpenShock keys
are both accepted — the
provider is detected
automatically from your key.[/bold]

[bold]Please do not enter your
Account password into this
program, only API Keys.[/bold]""",
            title="[bold]Welcome to PyShock![/bold]",
            style="bright_cyan",
            padding=(0, 1),
        )
    )
    _styled_print(
        _styled_panel(
            "PiShock: https://login.pishock.com/Account\nOpenShock: https://openshock.app/#/dashboard/tokens",
            title="[bold]Get an API Key at:[/bold]",
            padding=(1, 2),
        )
    )


def render_verify_panel(account: AccountInfo, provider: str = "pishock", account_id: str | None = None) -> None:
    """Print a verification panel."""
    header = f"[bold]{account.username}[/bold]\nID: {account.user_id}"
    if account_id:
        header = f"[bold]{account.username}[/bold] ({account_id})\nID: {account.user_id}"
    _styled_print(
        _styled_panel(
            header,
            title=f"{CHECK_MARK} OK ({provider})",
            padding=(1,),
        )
    )


def render_no_creds_panel() -> None:
    """Print credential setup instructions."""
    _styled_print(
        _styled_panel(
            "[white]"
            "Use --key, set PISHOCK_API_KEY or OPENSHOCK_API_TOKEN, "
            "or run 'pyshock auth' to configure credentials interactively[/white]",
            title="[bold black on white] API credentials not found [/bold black on white]",
            style="red",
            padding=(1, 1),
        ),
        err=True,
    )
