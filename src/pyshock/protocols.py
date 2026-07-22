"""Static protocols for shocker API clients and shared types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

__all__ = [
    "Session",
    "ShockerClient",
]

if TYPE_CHECKING:
    from pyshock.models.account import AccountInfo
    from pyshock.models.operation import ShockerOperation
    from pyshock.models.shocker import Shocker


class ShockerClient(Protocol):
    """Structural interface implemented by both PiShock and OpenShock clients."""

    def list_shockers(self, *, refresh: bool = False) -> list[Shocker]: ...

    def get_shocker_by_id(self, shocker_id: str) -> Shocker: ...

    def operate_shocker(
        self,
        shocker: str | Shocker,
        operation: ShockerOperation,
        duration: int,
        intensity: int,
    ) -> None: ...

    def get_account(self) -> AccountInfo: ...

    def close(self) -> None: ...

    def __enter__(self) -> ShockerClient: ...

    def __exit__(self, *args: object) -> None: ...


@dataclass(frozen=True)
class Session:
    """Per-request state bundling the API client, account ID, and provider."""

    api: ShockerClient
    account_id: str
    provider: str
