"""Shocker operation types."""

from __future__ import annotations

from enum import IntEnum
from typing import Literal

OperationName = Literal["shock", "vibrate", "beep"]
"""String names for config keys and capability fields."""


class ShockerOperation(IntEnum):
    """HTTP API operation values."""

    SHOCK = 0
    VIBRATE = 1
    BEEP = 2
