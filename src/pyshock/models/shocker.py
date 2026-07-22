"""Shocker data model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pyshock.constants import OPENSHOCK_MAX_DURATION_MS


def _omit_from_json(default: Any = None):  # ruff:ignore[missing-return-type-private-function]
    """Field excluded from CLI JSON output."""
    return field(metadata={"cli_json_exclude": True}, default=default)


@dataclass(frozen=True, kw_only=True)
class Shocker:
    """PiShock / OpenShock shocker device."""

    shocker_id: str
    name: str
    is_v3: bool = False
    can_shock: bool
    can_vibrate: bool
    can_beep: bool
    can_pause: bool = False
    can_hold: bool
    max_intensity: int
    max_duration: int
    pishock_hub_id: int | None = _omit_from_json()
    device_id: str | None = _omit_from_json()
    share_code: str | None = None
    owned_by: str | None = None
    locked: bool = False
    paused: bool = False
    share_paused: bool = False
    can_log: bool = False
    share_id: int | None = _omit_from_json()
    owner_id: int | None = _omit_from_json()
    client_id: int | None = _omit_from_json()
    shared_by: str | None = _omit_from_json()
    owner_image: str | None = _omit_from_json()
    model: str | None = None
    rf_id: int | None = None
    created_on: str | None = None

    @property
    def is_owned(self) -> bool:
        is_pishock = self.pishock_hub_id is not None
        is_openshock = self.device_id is not None
        is_shared = self.shared_by is not None
        return is_pishock or (is_openshock and not is_shared)

    @property
    def is_shared(self) -> bool:
        """Return True if this shocker is shared with the account.

        PiShock shared shockers have a share_code.
        OpenShock shared shockers have a shared_by.
        """
        return self.share_code is not None or self.shared_by is not None

    def __repr__(self) -> str:
        extra = ""
        if self.is_shared:
            extra = f", shared_by={self.shared_by!r}"
        return f"Shocker({self.name!r}, id={self.shocker_id!r}{extra})"

    def __str__(self) -> str:
        if self.is_shared:
            owner = self.owned_by or "?"
            if self.share_code:
                return f"{self.name} (code={self.share_code}, owner={owner})"
            return f"{self.name} (owner={owner})"
        return f"{self.name} (id={self.shocker_id})"

    @classmethod
    def from_api(cls, data: dict) -> Shocker:
        """Construct from a raw PiShock API response dict.

        Args:
            data: Raw API response with camelCase keys.

        Returns:
            Shocker instance.

        Raises:
            ValueError: If required fields are missing.
        """
        return cls(**cls._normalize_api(data))

    @classmethod
    def _normalize_api(cls, data: dict) -> dict:
        """Normalize camelCase API keys to snake-case kwargs."""
        is_shared = "ShareCode" in data

        if is_shared:
            required = {
                "ShareId",
                "OwnerId",
                "ClientId",
                "Id",
                "Name",
                "IsV3",
                "Paused",
                "CanPause",
                "CanHold",
                "CanBeep",
                "CanVibrate",
                "CanShock",
                "CanLog",
                "SharePaused",
                "ShareCode",
                "Locked",
                "MaxIntensity",
                "MaxDuration",
                "OwnedBy",
            }
        else:
            required = {
                "HubId",
                "ShockerId",
                "Name",
                "IsV3",
                "CanBeep",
                "CanVibrate",
                "CanShock",
                "CanPause",
                "MaxDuration",
                "MaxIntensity",
            }

        missing = required - data.keys()
        if missing:
            raise ValueError(f"Shocker: missing API fields {sorted(missing)}")

        result: dict = {
            "name": data["Name"],
            "is_v3": data["IsV3"],
            "can_shock": data["CanShock"],
            "can_vibrate": data["CanVibrate"],
            "can_beep": data["CanBeep"],
            "can_pause": data["CanPause"],
            "max_intensity": data["MaxIntensity"],
            "max_duration": data["MaxDuration"],
        }

        if is_shared:
            result.update({
                "shocker_id": str(data["Id"]),
                "can_hold": data["CanHold"],
                "share_code": data["ShareCode"],
                "owned_by": data["OwnedBy"],
                "locked": data["Locked"],
                "paused": data["Paused"],
                "share_paused": data["SharePaused"],
                "can_log": data["CanLog"],
                "share_id": data["ShareId"],
                "owner_id": data["OwnerId"],
                "client_id": data["ClientId"],
            })
        else:
            result.update({
                "shocker_id": str(data["ShockerId"]),
                "can_hold": data.get("CanHold", False),
                "pishock_hub_id": data["HubId"],
            })

        return result

    @classmethod
    def from_openshock_owned(
        cls,
        data: dict,
        *,
        device_id: str | None = None,
    ) -> Shocker:
        """Construct from an OpenShock owned shocker response.

        Source: ``GET /1/shockers/own`` → ``data[].shockers[]`` (nested inside device).

        Args:
            data: Raw OpenShock ShockerResponse dict.
            device_id: Parent device UUID (from DeviceWithShockersResponse.id).

        Returns:
            Shocker instance.

        Raises:
            ValueError: If required fields are missing.
        """
        required = {"id", "name", "isPaused"}
        missing = required - data.keys()
        if missing:
            raise ValueError(f"Shocker.from_openshock_owned: missing fields {sorted(missing)}")

        return cls(
            shocker_id=data["id"],
            name=data["name"],
            can_shock=True,
            can_vibrate=True,
            can_beep=True,
            can_hold=True,
            max_intensity=100,
            max_duration=OPENSHOCK_MAX_DURATION_MS,
            paused=data["isPaused"],
            device_id=device_id,
            model=data.get("model"),
            rf_id=data.get("rfId"),
            created_on=data.get("createdOn"),
        )

    @classmethod
    def from_openshock_shared(
        cls,
        data: dict,
        owner_info: dict,
        *,
        device_id: str | None = None,
    ) -> Shocker:
        """Construct from an OpenShock shared shocker response.

        Source: ``GET /1/shockers/shared`` → ``data[].devices[].shockers[]`` (triple-nested).

        Args:
            data: Raw OpenShock SharedShocker dict.
            owner_info: Dict with ``name``, ``id``, ``image`` keys from OwnerShockerResponse.
            device_id: Parent device UUID (from SharedDevice.id).

        Returns:
            Shocker instance.

        Raises:
            ValueError: If required fields are missing.
        """
        required = {"id", "name", "isPaused", "permissions", "limits"}
        missing = required - data.keys()
        if missing:
            raise ValueError(f"Shocker.from_openshock_shared: missing fields {sorted(missing)}")

        perms = data["permissions"]
        limits = data["limits"]

        return cls(
            shocker_id=data["id"],
            name=data["name"],
            can_shock=perms.get("shock", False),
            can_vibrate=perms.get("vibrate", False),
            can_beep=perms.get("sound", False),
            can_hold=perms.get("live", False),
            max_intensity=limits.get("intensity") if limits.get("intensity") is not None else 100,
            max_duration=limits.get("duration") if limits.get("duration") is not None else OPENSHOCK_MAX_DURATION_MS,
            paused=data["isPaused"],
            owned_by=owner_info.get("name"),
            shared_by=owner_info.get("id"),
            owner_image=owner_info.get("image"),
            device_id=device_id,
        )
