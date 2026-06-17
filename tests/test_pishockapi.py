"""Tests for HTTP API client."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import patch

import niquests
import pytest
from niquests.extensions.sgi import WebServerGatewayInterface

from pyshock.errors import (
    AccountNotFoundError,
    APIError,
    NoSharesProvidedError,
    NotAuthorizedError,
    ShareNotFoundError,
    ShockerNotFoundError,
    ShockerPausedError,
    TooManySharesError,
)
from pyshock.models.operation import ShockerOperation
from pyshock.pishockapi import PiShockAPI
from tests.mockapi import MockAPI


@pytest.fixture
def api_client(mock_api: MockAPI) -> Generator[PiShockAPI]:
    api = PiShockAPI("test_key")
    adapter = WebServerGatewayInterface(app=mock_api)
    api._session.mount("https://", adapter)
    api._session.mount("http://", adapter)
    yield api
    api.close()


def _mock_config(shockers: list[dict] | None = None) -> object:
    """Return a minimal config mock with shockers and save()."""
    return type(
        "Config",
        (),
        {"shockers": shockers, "save": lambda self: None, "is_configured": True},
    )()


def _shocker_json(shocker_id: int = 1, name: str = "Test", shared: bool = False, share_code: str = "abc123") -> dict:
    if shared:
        return {
            "ShareId": 40,
            "OwnerId": 10,
            "ClientId": 20,
            "Id": shocker_id,
            "Name": name,
            "IsV3": True,
            "Paused": False,
            "CanPause": True,
            "CanHold": True,
            "CanBeep": True,
            "CanVibrate": True,
            "CanShock": True,
            "CanLog": True,
            "SharePaused": False,
            "ShareCode": share_code,
            "Locked": False,
            "MaxDuration": 15000,
            "MaxIntensity": 100,
            "OwnedBy": "owner123",
        }
    return {
        "HubId": 1,
        "ShockerId": shocker_id,
        "Name": name,
        "IsV3": True,
        "CanBeep": True,
        "CanVibrate": True,
        "CanShock": True,
        "CanPause": True,
        "MaxDuration": 15000,
        "MaxIntensity": 100,
    }


class TestPiShockAPIInit:
    def test_sets_api_key_header(self, api_client: PiShockAPI) -> None:
        assert api_client._session.headers["X-PiShock-Api-Key"] == "test_key"

    def test_close(self, api_client: PiShockAPI) -> None:
        api_client.close()


class TestPiShockAPIRequest:
    def test_request_success(self, api_client: PiShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("GET", "/Health", status=200, json={"status": "ok"})
        result = api_client._request("GET", "Health")
        assert result == {"status": "ok"}

    def test_request_401_raises(self, api_client: PiShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("GET", "/Account", status=401)
        with pytest.raises(NotAuthorizedError):
            api_client._request("GET", "Account")

    def test_request_503_raises(self, api_client: PiShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("POST", "/Shockers/1", status=503)
        with pytest.raises(ShockerPausedError):
            api_client._request("POST", "Shockers/1")

    def test_request_unknown_error(self, api_client: PiShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("GET", "/Account", status=500)
        with pytest.raises(APIError):
            api_client._request("GET", "Account")

    def test_request_empty_response(self, api_client: PiShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("GET", "/Health", status=204)
        result = api_client._request("GET", "Health")
        assert result is None

    def test_request_invalid_json(self, api_client: PiShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("GET", "/Health", status=200, text="not json")
        with pytest.raises(APIError, match="Invalid JSON"):
            api_client._request("GET", "Health")


class TestListShockers:
    def test_list_shockers_success(self, api_client: PiShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("GET", "/Shockers", status=200, json=[_shocker_json()])
        mock_api.route("GET", "/Share/GetShared", status=200, json=[])
        shockers = api_client.list_shockers()

        assert len(shockers) == 1
        assert shockers[0].name == "Test"

    def test_list_shockers_empty(self, api_client: PiShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("GET", "/Shockers", status=200, json=[])
        mock_api.route("GET", "/Share/GetShared", status=200, json=[])
        shockers = api_client.list_shockers()

        assert len(shockers) == 0

    def test_list_shockers_not_authorized(self, api_client: PiShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("GET", "/Shockers", status=401)
        with pytest.raises(NotAuthorizedError):
            api_client.list_shockers()

    def test_list_shockers_merges_shared_metadata(self, api_client: PiShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("GET", "/Shockers", status=200, json=[_shocker_json(1, "Test")])
        mock_api.route("GET", "/Share/GetShared", status=200, json=[_shocker_json(1, "Test", shared=True)])
        shockers = api_client.list_shockers()

        assert len(shockers) == 1
        assert shockers[0].shocker_id == "1"
        assert shockers[0].name == "Test"
        assert shockers[0].is_owned is True
        assert shockers[0].is_shared is True
        assert shockers[0].share_code == "abc123"
        assert shockers[0].owned_by == "owner123"

    def test_list_shockers_shared_only(self, api_client: PiShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("GET", "/Shockers", status=200, json=[])
        mock_api.route("GET", "/Share/GetShared", status=200, json=[_shocker_json(99, "Shared", shared=True)])
        shockers = api_client.list_shockers()

        assert len(shockers) == 1
        assert shockers[0].shocker_id == "99"
        assert shockers[0].is_shared is True


class TestGetAccount:
    def test_get_account_success(self, api_client: PiShockAPI, mock_api: MockAPI) -> None:
        mock_api.route(
            "GET",
            "/Account",
            status=200,
            json={
                "UserId": 12345,
                "Username": "testuser",
                "EmailAddresses": [],
                "OAuthLinks": [],
            },
        )
        account = api_client.get_account()
        assert account.user_id == "12345"
        assert account.username == "testuser"

    def test_get_account_not_found(self, api_client: PiShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("GET", "/Account", status=404)
        with pytest.raises(AccountNotFoundError):
            api_client.get_account()

    def test_get_account_unexpected_type(self, api_client: PiShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("GET", "/Account", status=200, json=[])
        with pytest.raises(APIError, match="Unexpected response from Account endpoint"):
            api_client.get_account()


class TestHealthCheck:
    def test_health_check_ok(self, mock_api: MockAPI) -> None:
        mock_api.route("GET", "/Health", status=204)
        from pyshock.pishockapi import health_check

        adapter = WebServerGatewayInterface(app=mock_api)
        real_session = niquests.Session

        def make_session(*args, **kwargs):
            s = real_session(*args, **kwargs)
            s.mount("https://", adapter)
            s.mount("http://", adapter)
            return s

        with patch("pyshock.pishockapi.niquests.Session", side_effect=make_session):
            result = health_check()
        assert result is True

    def test_health_check_500(self, mock_api: MockAPI) -> None:
        mock_api.route("GET", "/Health", status=500)
        from pyshock.pishockapi import health_check

        adapter = WebServerGatewayInterface(app=mock_api)
        real_session = niquests.Session

        def make_session(*args, **kwargs):
            s = real_session(*args, **kwargs)
            s.mount("https://", adapter)
            s.mount("http://", adapter)
            return s

        with patch("pyshock.pishockapi.niquests.Session", side_effect=make_session):
            result = health_check()
        assert result is False

    def test_health_check_down(self) -> None:
        from pyshock.pishockapi import health_check

        with patch(
            "pyshock.pishockapi.niquests.Session",
            side_effect=niquests.RequestException(),
        ):
            result = health_check()
        assert result is False


class TestListShockersCache:
    def test_second_call_uses_instance_cache(self, api_client: PiShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("GET", "/Shockers", status=200, json=[_shocker_json(1, "Alpha")])
        mock_api.route("GET", "/Share/GetShared", status=200, json=[])

        result1 = api_client.list_shockers()
        assert len(result1) == 1
        assert result1[0].name == "Alpha"

        result2 = api_client.list_shockers()
        assert result2 == result1


class TestGetShockerById:
    def test_get_shocker_by_id_success(self, api_client: PiShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("GET", "/Shockers", status=200, json=[_shocker_json(1, "Test")])
        mock_api.route("GET", "/Share/GetShared", status=200, json=[])
        shocker = api_client.get_shocker_by_id("1")
        assert shocker.shocker_id == "1"
        assert shocker.name == "Test"

    def test_get_shocker_by_id_merged(self, api_client: PiShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("GET", "/Shockers", status=200, json=[_shocker_json(1, "Test")])
        mock_api.route("GET", "/Share/GetShared", status=200, json=[_shocker_json(1, "Test", shared=True)])
        shocker = api_client.get_shocker_by_id("1")
        assert shocker.shocker_id == "1"
        assert shocker.is_owned is True
        assert shocker.is_shared is True
        assert shocker.share_code == "abc123"
        shocker = api_client.get_shocker_by_id("1")
        assert shocker.shocker_id == "1"
        assert shocker.is_owned is True
        assert shocker.is_shared is True
        assert shocker.share_code == "abc123"

    def test_get_shocker_by_id_not_found(self, api_client: PiShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("GET", "/Shockers", status=200, json=[])
        mock_api.route("GET", "/Share/GetShared", status=200, json=[])
        with pytest.raises(ShockerNotFoundError):
            api_client.get_shocker_by_id("999")


class TestOperateShocker:
    def test_operate_shocker_success(self, api_client: PiShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("POST", "/Shockers/42", status=200)

        api_client.operate_shocker(
            shocker="42",
            operation=ShockerOperation.VIBRATE,
            duration=1000,
            intensity=50,
        )

        assert mock_api._last_request["path"] == "/Shockers/42"

    def test_operate_shocker_invalid_duration(self, api_client: PiShockAPI) -> None:
        with pytest.raises(ValueError, match="duration"):
            api_client.operate_shocker(
                shocker="1",
                operation=ShockerOperation.VIBRATE,
                duration=20000,
                intensity=50,
            )

    def test_operate_shocker_duration_below_minimum(self, api_client: PiShockAPI) -> None:
        with pytest.raises(ValueError, match="duration"):
            api_client.operate_shocker(
                shocker="1",
                operation=ShockerOperation.VIBRATE,
                duration=50,
                intensity=50,
            )

    def test_operate_shocker_invalid_intensity(self, api_client: PiShockAPI) -> None:
        with pytest.raises(ValueError, match="intensity"):
            api_client.operate_shocker(
                shocker="1",
                operation=ShockerOperation.VIBRATE,
                duration=1000,
                intensity=150,
            )


class TestGetShockerByShareCode:
    def test_get_shocker_by_share_code_success(self, api_client: PiShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("GET", "/Shockers", status=200, json=[_shocker_json(1, "Test")])
        mock_api.route("GET", "/Share/GetShared", status=200, json=[_shocker_json(1, "Test", shared=True)])
        shocker = api_client.get_shocker_by_share_code("abc123")
        assert shocker.share_code == "abc123"

    def test_get_shocker_by_share_code_not_found(self, api_client: PiShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("GET", "/Shockers", status=200, json=[])
        mock_api.route("GET", "/Share/GetShared", status=200, json=[])
        with pytest.raises(ShareNotFoundError):
            api_client.get_shocker_by_share_code("missing")


class TestShareCodes:
    def test_add_share_code(self, api_client: PiShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("PUT", "/Share", status=200)
        api_client.add_share_code("abc123")

    def test_add_share_code_empty_raises(self, api_client: PiShockAPI) -> None:
        with pytest.raises(NoSharesProvidedError):
            api_client.add_share_code("")

    def test_add_share_codes(self, api_client: PiShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("PUT", "/Share", status=200)
        api_client.add_share_codes(["abc123", "def456"])

    def test_add_share_codes_empty_raises(self, api_client: PiShockAPI) -> None:
        with pytest.raises(NoSharesProvidedError):
            api_client.add_share_codes([])

    def test_add_share_codes_too_many_raises(self, api_client: PiShockAPI) -> None:
        with pytest.raises(TooManySharesError):
            api_client.add_share_codes(["a"] * 21)

    def test_delete_share(self, api_client: PiShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("DELETE", "/Share/abc123", status=200)
        api_client.delete_share("abc123")


class TestOperateShockerValidation:
    def test_duration_out_of_range(self, api_client: PiShockAPI) -> None:
        with pytest.raises(ValueError, match="duration"):
            api_client.operate_shocker(
                shocker="1",
                operation=ShockerOperation.VIBRATE,
                duration=20000,
                intensity=50,
            )

    def test_intensity_out_of_range(self, api_client: PiShockAPI) -> None:
        with pytest.raises(ValueError, match="intensity"):
            api_client.operate_shocker(
                shocker="1",
                operation=ShockerOperation.VIBRATE,
                duration=1000,
                intensity=150,
            )


class TestHandleError:
    def test_404_unmapped_resource(self, api_client: PiShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("GET", "/Unknown", status=404)
        with pytest.raises(APIError):
            api_client._request("GET", "Unknown")
