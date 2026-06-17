"""CLI context variables shared across command modules."""

from __future__ import annotations

from contextvars import ContextVar

json_mode: ContextVar[bool] = ContextVar("json_mode", default=False)
_current_account_id: ContextVar[str] = ContextVar("_current_account_id", default="")
