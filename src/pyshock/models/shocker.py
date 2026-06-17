"""Shocker data model."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace

from pyshock.constants import OPENSHOCK_MAX_DURATION_MS


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
    hub_id: int | None = None
    device_id: str | None = None
    share_code: str | None = None
    owned_by: str | None = None
    locked: bool = False
    paused: bool = False
    share_paused: bool = False
    can_log: bool = False
    share_id: int | None = None
    owner_id: int | None = None
    client_id: int | None = None
    owner_uuid: str | None = None
    owner_image: str | None = None
    model: str | None = None
    rf_id: int | None = None
    created_on: str | None = None

    @property
    def is_owned(self) -> bool:
        # PiShock owned: hub_id is set.
        # OpenShock owned: device_id is set, owner_uuid is None.
        # OpenShock shared: device_id is set, owner_uuid is also set.
        # PiShock shared: neither hub_id nor device_id is set.
        return self.hub_id is not None or (self.device_id is not None and self.owner_uuid is None)

    @property
    def is_shared(self) -> bool:
        """Return True if this shocker is shared with the account.

        PiShock shared shockers have a share_code.
        OpenShock shared shockers have an owner_uuid.
        """
        return self.share_code is not None or self.owner_uuid is not None

    def __repr__(self) -> str:
        return f"Shocker({self.name!r}, id={self.shocker_id!r})"

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
                "hub_id": data["HubId"],
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
            owner_uuid=owner_info.get("id"),
            owner_image=owner_info.get("image"),
            device_id=device_id,
        )

    @staticmethod
    def merge(shared: Shocker, owned: Shocker) -> Shocker:
        """Overlay non-None owned fields onto a shared shocker.

        Used when the same device appears in both owned and shared lists.

        Args:
            shared: Shocker from the shared endpoint (has permissions/limits).
            owned: Shocker from the owned endpoint (has device metadata).

        Returns:
            Merged Shocker with owned fields taking precedence.
        """
        updates = {k: v for k, v in asdict(owned).items() if v is not None}
        return replace(shared, **updates)
