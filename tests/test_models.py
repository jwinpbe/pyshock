"""Tests for data models."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from pyshock.models.account import AccountInfo
from pyshock.models.operation import ShockerOperation
from pyshock.models.shocker import Shocker


class TestShocker:
    def test_from_api_owned(self) -> None:
        data = {
            "HubId": 1,
            "ShockerId": 2,
            "Name": "Test Shocker",
            "IsV3": True,
            "CanBeep": True,
            "CanVibrate": True,
            "CanShock": True,
            "CanPause": True,
            "MaxDuration": 15000,
            "MaxIntensity": 100,
        }

        shocker = Shocker.from_api(data)

        assert shocker.pishock_hub_id == 1
        assert shocker.shocker_id == "2"
        assert shocker.name == "Test Shocker"
        assert shocker.is_v3 is True
        assert shocker.can_beep is True
        assert shocker.can_vibrate is True
        assert shocker.can_shock is True
        assert shocker.can_pause is True
        assert shocker.max_duration == 15000
        assert shocker.max_intensity == 100
        assert shocker.is_owned is True
        assert shocker.is_shared is False

    def test_from_api_owned_missing_keys(self) -> None:
        with pytest.raises(ValueError, match="missing API fields"):
            Shocker.from_api({"HubId": 1})

    def test_from_api_shared(self) -> None:
        data = {
            "ShareId": 40,
            "OwnerId": 10,
            "ClientId": 20,
            "Id": 30,
            "Name": "Shared Device",
            "IsV3": True,
            "Paused": False,
            "CanPause": True,
            "CanHold": True,
            "CanBeep": True,
            "CanVibrate": False,
            "CanShock": True,
            "CanLog": True,
            "SharePaused": False,
            "ShareCode": "ABC123",
            "Locked": False,
            "MaxIntensity": 80,
            "MaxDuration": 10000,
            "OwnedBy": "owner123",
        }

        shocker = Shocker.from_api(data)

        assert shocker.shocker_id == "30"
        assert shocker.name == "Shared Device"
        assert shocker.share_code == "ABC123"
        assert shocker.owned_by == "owner123"
        assert shocker.can_shock is True
        assert shocker.can_vibrate is False
        assert shocker.is_v3 is True
        assert shocker.is_shared is True
        assert shocker.is_owned is False
        assert shocker.pishock_hub_id is None

    def test_from_api_shared_missing_keys(self) -> None:
        with pytest.raises(ValueError, match="missing API fields"):
            Shocker.from_api({"ShareId": 1})

    def test_frozen(self) -> None:
        shocker = Shocker(
            shocker_id="2",
            name="Test",
            is_v3=True,
            can_beep=True,
            can_vibrate=True,
            can_shock=True,
            can_pause=True,
            can_hold=True,
            max_duration=1000,
            max_intensity=50,
        )

        with pytest.raises(FrozenInstanceError):
            shocker.name = "Other"  # type: ignore[attr-defined]

    def test_str_owned(self) -> None:
        shocker = Shocker(
            shocker_id="1",
            name="My Shocker",
            is_v3=True,
            can_beep=True,
            can_vibrate=True,
            can_shock=True,
            can_pause=True,
            can_hold=True,
            max_duration=1000,
            max_intensity=50,
            pishock_hub_id=1,
        )
        assert str(shocker) == "My Shocker (id=1)"

    def test_str_shared(self) -> None:
        shocker = Shocker(
            shocker_id="1",
            name="My Shocker",
            is_v3=True,
            can_beep=True,
            can_vibrate=True,
            can_shock=True,
            can_pause=True,
            can_hold=True,
            max_duration=1000,
            max_intensity=50,
            share_code="ABC123",
            owned_by="owner123",
        )
        assert str(shocker) == "My Shocker (code=ABC123, owner=owner123)"

    def test_from_openshock_owned(self) -> None:
        data = {
            "id": "019df66b-e20d-7068-9fbc-ff152fc2dddc",
            "rfId": 29850,
            "model": "CaiXianlin",
            "name": "Test Shocker",
            "isPaused": False,
            "createdOn": "2026-05-05T04:35:58.624468Z",
        }
        shocker = Shocker.from_openshock_owned(data, device_id="device-uuid")

        assert shocker.shocker_id == "019df66b-e20d-7068-9fbc-ff152fc2dddc"
        assert shocker.name == "Test Shocker"
        assert shocker.is_v3 is False
        assert shocker.can_shock is True
        assert shocker.can_vibrate is True
        assert shocker.can_beep is True
        assert shocker.can_pause is False
        assert shocker.can_hold is True
        assert shocker.max_intensity == 100
        assert shocker.max_duration == 65535
        assert shocker.paused is False
        assert shocker.device_id == "device-uuid"
        assert shocker.is_owned is True
        assert shocker.is_shared is False

    def test_from_openshock_owned_missing_keys(self) -> None:
        with pytest.raises(ValueError, match="missing fields"):
            Shocker.from_openshock_owned({"id": "123"})

    def test_from_openshock_shared(self) -> None:
        data = {
            "id": "019df66b-e20d-7068-9fbc-ff152fc2dddc",
            "name": "Shared Shocker",
            "isPaused": False,
            "permissions": {"shock": True, "vibrate": True, "sound": True, "live": False},
            "limits": {"intensity": 80, "duration": 10000},
        }
        owner_info = {
            "name": "owner123",
            "id": "owner-uuid",
            "image": "https://gravatar.com/test",
        }
        shocker = Shocker.from_openshock_shared(data, owner_info)

        assert shocker.shocker_id == "019df66b-e20d-7068-9fbc-ff152fc2dddc"
        assert shocker.name == "Shared Shocker"
        assert shocker.can_shock is True
        assert shocker.can_vibrate is True
        assert shocker.can_beep is True
        assert shocker.can_pause is False
        assert shocker.can_hold is False
        assert shocker.max_intensity == 80
        assert shocker.max_duration == 10000
        assert shocker.paused is False
        assert shocker.owned_by == "owner123"
        assert shocker.shared_by == "owner-uuid"
        assert shocker.owner_image == "https://gravatar.com/test"
        assert shocker.device_id is None
        assert shocker.is_shared is True
        assert shocker.is_owned is False

    def test_from_openshock_shared_no_limits(self) -> None:
        data = {
            "id": "uuid-123",
            "name": "Shared",
            "isPaused": False,
            "permissions": {"shock": False, "vibrate": False, "sound": False, "live": False},
            "limits": {"intensity": None, "duration": None},
        }
        shocker = Shocker.from_openshock_shared(data, {"name": "owner", "id": "o-uuid"})
        assert shocker.max_intensity == 100
        assert shocker.max_duration == 65535
        assert shocker.can_shock is False

    def test_from_openshock_shared_missing_keys(self) -> None:
        with pytest.raises(ValueError, match="missing fields"):
            Shocker.from_openshock_shared({"id": "123"}, {"name": "owner"})


class TestAccountInfo:
    def test_from_api(self) -> None:
        data = {
            "UserId": 12345,
            "Username": "testuser",
            "EmailAddresses": [],
            "OAuthLinks": [],
        }

        account = AccountInfo.from_api(data)

        assert account.user_id == "12345"
        assert account.username == "testuser"

    def test_from_api_missing_keys(self) -> None:
        with pytest.raises(ValueError, match="missing API fields"):
            AccountInfo.from_api({"UserId": 12345})

    def test_from_openshock_api(self) -> None:
        data = {
            "id": "019df66b-08b2-71fd-b0d8-4cb650725974",
            "name": "testuser",
            "email": "test@example.com",
            "image": "https://gravatar.com/test",
            "roles": [],
            "rank": "User",
        }

        account = AccountInfo.from_openshock_api(data)

        assert account.user_id == "019df66b-08b2-71fd-b0d8-4cb650725974"
        assert account.username == "testuser"
        assert account.email == "test@example.com"
        assert account.image == "https://gravatar.com/test"

    def test_from_openshock_api_minimal(self) -> None:
        data = {"id": "uuid-123", "name": "user"}
        account = AccountInfo.from_openshock_api(data)
        assert account.user_id == "uuid-123"
        assert account.username == "user"
        assert account.email is None
        assert account.image is None

    def test_from_openshock_api_missing_keys(self) -> None:
        with pytest.raises(ValueError, match="missing OpenShock fields"):
            AccountInfo.from_openshock_api({"id": "123"})


class TestShockerOperation:
    def test_values(self) -> None:
        assert ShockerOperation.SHOCK == 0
        assert ShockerOperation.VIBRATE == 1
        assert ShockerOperation.BEEP == 2

    def test_int_compatible(self) -> None:
        assert ShockerOperation.SHOCK + 1 == 1
