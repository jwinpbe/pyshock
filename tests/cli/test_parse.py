"""Layer 1: Parse assertions — verify cyclopts maps token strings to Python arguments.

Pure binding tests: no API calls, no side effects.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable
from cyclopts.exceptions import UnknownCommandError

from pyshock.cli.commands.code import add, delete, list_codes
from pyshock.cli.commands.meta import auth, confirm, devices, logout, verify
from pyshock.cli.commands.shocker import beep, info, shock, vibrate

# -- Shocker command parse tests --


def test_shock_parse_positional(assert_parse_args: Callable[..., tuple]) -> None:
    """Positional duration and intensity bind correctly."""
    assert_parse_args(
        "shock 2 75",
        shock,
        expected_args=(2.0, 75),
        expected_kwargs={},
    )


def test_shock_parse_named(assert_parse_args: Callable[..., tuple]) -> None:
    """Named --duration, --intensity, --shocker-id bind correctly.

    duration and intensity are positional (before *), so they go into args
    even when specified by name. shocker_id is keyword-only (after *).
    """
    assert_parse_args(
        "shock --duration 2 --intensity 75 --shocker-id 00000",
        shock,
        expected_args=(2.0, 75),
        expected_kwargs={"shocker_id": "00000"},
    )


def test_shock_with_force(assert_parse_args: Callable[..., tuple]) -> None:
    """--force flag binds to force=True."""
    assert_parse_args(
        "shock 2 75 --force",
        shock,
        expected_args=(2.0, 75),
        expected_kwargs={"force": True},
    )


def test_shock_with_id_alias(assert_parse_args: Callable[..., tuple]) -> None:
    """--id alias binds to shocker_id."""
    assert_parse_args(
        "shock 2 75 --id 00000",
        shock,
        expected_args=(2.0, 75),
        expected_kwargs={"shocker_id": "00000"},
    )


def test_vibrate_parse(assert_parse_args: Callable[..., tuple]) -> None:
    """Positional duration and intensity bind correctly for vibrate."""
    assert_parse_args(
        "vibrate 1 50",
        vibrate,
        expected_args=(1.0, 50),
        expected_kwargs={},
    )


def test_beep_parse(assert_parse_args: Callable[..., tuple]) -> None:
    """Beep has no positional args."""
    assert_parse_args(
        "beep",
        beep,
        expected_args=(),
        expected_kwargs={},
    )


def test_info_parse(assert_parse_args: Callable[..., tuple]) -> None:
    """Info takes shocker_id as keyword-only (--id alias)."""
    assert_parse_args(
        "info --id 00000",
        info,
        expected_args=(),
        expected_kwargs={"shocker_id": "00000"},
    )


# -- Meta command parse tests --


def test_devices_parse(assert_parse_args: Callable[..., tuple]) -> None:
    """Devices has no args."""
    assert_parse_args(
        "devices",
        devices,
        expected_args=(),
        expected_kwargs={},
    )


def test_verify_parse(assert_parse_args: Callable[..., tuple]) -> None:
    """Verify with --account binds account_id as positional (no * in signature)."""
    assert_parse_args(
        "verify --account foo",
        verify,
        expected_args=("foo",),
        expected_kwargs={},
    )


def test_init_alias_resolves(assert_parse_args: Callable[..., tuple]) -> None:
    """'init' alias resolves to the auth command."""
    assert_parse_args(
        "init",
        auth,
        expected_args=(),
        expected_kwargs={},
    )


def test_logout_parse(assert_parse_args: Callable[..., tuple]) -> None:
    """Logout with --account binds account_id as positional (no * in signature)."""
    assert_parse_args(
        "logout --account foo",
        logout,
        expected_args=("foo",),
        expected_kwargs={},
    )


def test_confirm_parse(assert_parse_args: Callable[..., tuple]) -> None:
    """Confirm with no args."""
    assert_parse_args(
        "confirm",
        confirm,
        expected_args=(),
        expected_kwargs={},
    )


# -- Code sub-app parse tests --


def test_code_add_parse(assert_parse_args: Callable[..., tuple]) -> None:
    """Code add with share code."""
    assert_parse_args(
        "code add ABC123",
        add,
        expected_args=("ABC123",),
        expected_kwargs={},
    )


def test_code_delete_parse(assert_parse_args: Callable[..., tuple]) -> None:
    """Code delete with share code."""
    assert_parse_args(
        "code delete ABC123",
        delete,
        expected_args=("ABC123",),
        expected_kwargs={},
    )


def test_code_list_parse(assert_parse_args: Callable[..., tuple]) -> None:
    """Code list with no args."""
    assert_parse_args(
        "code list",
        list_codes,
        expected_args=(),
        expected_kwargs={},
    )


def test_code_list_with_info_parse(assert_parse_args: Callable[..., tuple]) -> None:
    """Code list --show-info binds show_info=True."""
    assert_parse_args(
        "code list --show-info",
        list_codes,
        expected_args=(),
        expected_kwargs={"show_info": True},
    )


# -- Error cases --


def test_unknown_command(app) -> None:  # type: ignore[no-untyped-def]
    """Unknown command raises UnknownCommandError."""
    with pytest.raises(UnknownCommandError):
        app.parse_args("bogus", print_error=False, exit_on_error=False)
