"""Provider dispatch table for PiShock and OpenShock."""

from __future__ import annotations

from dataclasses import dataclass

from pyshock.constants import (
    OPENSHOCK_MAX_DURATION_MS,
    OPENSHOCK_MIN_DURATION_MS,
    PISHOCK_MAX_DURATION_MS,
    PISHOCK_MIN_DURATION_MS,
)
from pyshock.openshockapi import OpenShockAPI
from pyshock.pishockapi import PiShockAPI

__all__ = [
    "PROVIDERS",
    "ProviderSpec",
]


@dataclass(frozen=True)
class ProviderSpec:
    """Static metadata for a shocker API provider."""

    label: str  # "PiShock" / "OpenShock"
    client_cls: type
    cred_key: str  # "api_key" / "api_token"
    min_duration_ms: int
    max_duration_ms: int


PROVIDERS: dict[str, ProviderSpec] = {
    "pishock": ProviderSpec("PiShock", PiShockAPI, "api_key", PISHOCK_MIN_DURATION_MS, PISHOCK_MAX_DURATION_MS),
    "openshock": ProviderSpec(
        "OpenShock", OpenShockAPI, "api_token", OPENSHOCK_MIN_DURATION_MS, OPENSHOCK_MAX_DURATION_MS
    ),
}
