"""Configuration management for PyShock."""

from __future__ import annotations

import logging
from dataclasses import asdict
from json import JSONDecodeError, dumps, loads
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict, cast

if TYPE_CHECKING:
    from pyshock.models.account import AccountEntry

from platformdirs import user_config_dir

from pyshock.cli.display import console_err

logger = logging.getLogger(__name__)

CONFIG_FILENAME = "config.json"

_cached_current_config: Config | None = None


class _MultiConfigData(TypedDict, total=False):
    """Top-level config file structure."""

    accounts: dict[str, AccountEntry]
    default_shocker_id: str | None
    confirmations: dict[str, Any]


def get_config() -> Config:
    """Return the cached Config instance, loading from disk on first call."""
    global _cached_current_config
    if _cached_current_config is None:
        _cached_current_config = Config()
        _cached_current_config.load()
    return _cached_current_config


def reset_config_cache() -> None:
    """Clear the cached Config instance."""
    global _cached_current_config
    _cached_current_config = None


class Config:
    """PyShock configuration, stored as JSON in the user config directory.

    Manages multiple accounts across PiShock and OpenShock providers.
    """

    def __init__(self) -> None:
        self._path = Path(user_config_dir("PyShock")) / CONFIG_FILENAME
        self._data: _MultiConfigData = {}

    def load(self) -> None:
        if not self._path.exists():
            self._data = {}
            return
        try:
            self._data = loads(self._path.read_text(encoding="utf-8"))
        except (JSONDecodeError, OSError) as e:
            console_err.print(f"[red]Warning: failed to load config.\nError returned: {e}[/red]")
            self._data = {}
            return
        self._validate_default_shocker_id()

    def save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                dumps(dict(self._data), indent=2),
                encoding="utf-8",
            )
            self._path.chmod(0o600)
        except OSError as e:
            console_err.print(f"[red]Warning: failed to save config.\nError returned: {e}[/red]")

    # -- Account properties --

    @property
    def accounts(self) -> dict[str, AccountEntry]:
        """Return accounts dict, auto-init empty."""
        return self._data.setdefault("accounts", {})

    @property
    def shocker_index(self) -> dict[str, str]:
        """Return shocker_id -> account_id mapping, computed from accounts."""
        index: dict[str, str] = {}
        for account_id, entry in self.accounts.items():
            for s in entry.get("shockers", []):
                sid = s.get("shocker_id")
                if sid:
                    index[str(sid)] = account_id
        return index

    @property
    def is_configured(self) -> bool:
        return bool(self.accounts)

    @property
    def default_shocker_id(self) -> str | None:
        return self._data.get("default_shocker_id")

    @default_shocker_id.setter
    def default_shocker_id(self, value: str | None) -> None:
        if value is not None:
            self._data["default_shocker_id"] = value
        elif "default_shocker_id" in self._data:
            del self._data["default_shocker_id"]

    def confirmation_enabled(self, operation: str) -> bool:
        """Return whether the confirmation prompt is enabled for *operation*.

        Missing keys default to enabled (True).
        """
        return self.confirmations.get(operation, True)

    def set_confirmation(self, operation: str, *, enabled: bool) -> None:
        """Set global confirmation toggle for an operation."""
        self.confirmations[operation] = enabled

    @property
    def confirmations(self) -> dict[str, Any]:
        """Return confirmations dict, auto-creating if needed."""
        raw = self._data.get("confirmations")
        if not isinstance(raw, dict):
            self._data["confirmations"] = {}
            return self._data["confirmations"]
        return raw

    # -- Account management --

    def add_account(self, account_id: str, provider: str, **creds: Any) -> None:
        """Add or update an account entry.

        Args:
            account_id: Unique account identifier.
            provider: "pishock".
            **creds: Provider-specific credentials and optional browser metadata.
        """
        accounts = self.accounts
        if account_id in accounts:
            raise ValueError(f"Account '{account_id}' already exists. Use remove_account first.")

        accounts[account_id] = cast(
            "AccountEntry",
            {"provider": provider, **{k: v for k, v in creds.items() if v is not None}},
        )

    def remove_account(self, account_id: str) -> None:
        """Remove an account and clean up related state.

        Clears default_shocker_id if it pointed to a shocker in the removed account.
        """
        accounts = self.accounts
        if account_id not in accounts:
            return

        default = self._data.get("default_shocker_id")
        if default and self.shocker_index.get(default) == account_id:
            self.default_shocker_id = None

        del accounts[account_id]

    def get_account(self, account_id: str) -> AccountEntry | None:
        """Return account entry or None."""
        return self.accounts.get(account_id)

    def get_account_for_shocker(self, shocker_id: str) -> AccountEntry | None:
        """Lookup shocker_id in shocker_index, return the owning account entry."""
        account_id = self.shocker_index.get(shocker_id)
        if account_id is None:
            return None
        return self.accounts.get(account_id)

    def refresh_account_shockers(self, account_id: str, shocker_list: list) -> None:
        """Update an account's shockers list.

        Args:
            account_id: The account to update.
            shocker_list: List of Shocker objects or dicts.
        """
        accounts = self.accounts
        if account_id not in accounts:
            return

        entry = accounts[account_id]
        entry["shockers"] = [asdict(s) if hasattr(s, "__dataclass_fields__") else s for s in shocker_list]

    def _validate_default_shocker_id(self) -> None:
        """Clear default_shocker_id if it no longer exists in shocker_index."""
        default = self._data.get("default_shocker_id")
        if default and default not in self.shocker_index:
            self.default_shocker_id = None

    def __repr__(self) -> str:
        account_count = len(self.accounts)
        return f"Config(accounts={account_count}, default_shocker_id={self.default_shocker_id!r})"
