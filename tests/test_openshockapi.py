"""Tests for OpenShock API client."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import patch

import niquests
import pytest
from niquests.extensions.sgi import WebServerGatewayInterface

from pyshock.errors import (
    APIError,
    NotAuthorizedError,
    PermissionMissingError,
    ShockerNotFoundError,
)
from pyshock.models.operation import ShockerOperation
from pyshock.openshockapi import OpenShockAPI
from tests.mockapi import MockAPI


@pytest.fixture
def api_client(mock_api: MockAPI) -> Generator[OpenShockAPI]:
    api = OpenShockAPI("test_token")
    adapter = WebServerGatewayInterface(app=mock_api)
    api._session.mount("https://", adapter)
    api._session.mount("http://", adapter)
    yield api
    api.close()


def _wrap(data):
    """Wrap data in OpenShock {message, data} pattern."""
    return {"message": "", "data": data}


def _owned_shocker(shocker_id: str = "019df66b-e20d-7068-9fbc-ff152fc2dddc") -> dict:
    return {
        "id": shocker_id,
        "rfId": 29850,
        "model": "CaiXianlin",
        "name": "Test Shocker",
        "isPaused": False,
        "createdOn": "2026-05-05T04:35:58.624468Z",
    }


def _owned_device(shocker_id: str = "019df66b-e20d-7068-9fbc-ff152fc2dddc") -> dict:
    return {
        "id": "019df66b-b53b-7fdf-b573-bae6dbeb6025",
        "name": "Test Hub",
        "createdOn": "2026-05-05T04:35:47.147589Z",
        "shockers": [_owned_shocker(shocker_id)],
    }


def _shared_shocker(shocker_id: str = "019df66b-e20d-7068-9fbc-ff152fc2dddc") -> dict:
    return {
        "id": shocker_id,
        "name": "Shared Shocker",
        "isPaused": False,
        "permissions": {"shock": True, "vibrate": True, "sound": True, "live": False},
        "limits": {"intensity": None, "duration": None},
    }


def _shared_device(shocker_id: str = "019df66b-e20d-7068-9fbc-ff152fc2dddc") -> dict:
    return {
        "id": "019df66b-b53b-7fdf-b573-bae6dbeb6026",
        "name": "Shared Hub",
        "shockers": [_shared_shocker(shocker_id)],
    }


def _shared_owner(shocker_id: str = "019df66b-e20d-7068-9fbc-ff152fc2dddc") -> dict:
    return {
        "id": "019df66b-08b2-71fd-b0d8-4cb650725974",
        "name": "owner123",
        "image": "https://gravatar.com/example",
        "devices": [_shared_device(shocker_id)],
    }


class TestOpenShockAPIInit:
    def test_sets_headers(self, api_client: OpenShockAPI) -> None:
        assert api_client._session.headers["OpenShockToken"] == "test_token"

    def test_close(self, api_client: OpenShockAPI) -> None:
        api_client.close()


class TestOpenShockAPIRequest:
    def test_request_success(self, api_client: OpenShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("GET", "/1", status=200, json={"status": "ok"})
        result = api_client._request("GET", "1")
        assert result == {"status": "ok"}

    def test_request_unwraps_wrapper(self, api_client: OpenShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("GET", "/1/users/self", status=200, json=_wrap({"id": "123", "name": "test"}))
        result = api_client._request("GET", "1/users/self")
        assert result == {"id": "123", "name": "test"}

    def test_request_wrapper_with_null_data(self, api_client: OpenShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("POST", "/2/shockers/control", status=200, json=_wrap(None))
        result = api_client._request("POST", "2/shockers/control")
        assert result is None

    def test_request_401_raises(self, api_client: OpenShockAPI, mock_api: MockAPI) -> None:
        mock_api.route(
            "GET",
            "/1/users/self",
            status=401,
            json={
                "type": "Authentication.Token.Invalid",
                "title": "Invalid token",
                "status": 401,
                "message": "Invalid token",
            },
        )
        with pytest.raises(NotAuthorizedError):
            api_client._request("GET", "1/users/self")

    def test_request_403_permission_missing(self, api_client: OpenShockAPI, mock_api: MockAPI) -> None:
        mock_api.route(
            "POST",
            "/2/shockers/control",
            status=403,
            json={
                "type": "Authorization.Token.PermissionMissing",
                "title": "Missing permission",
                "status": 403,
                "message": "Missing permission",
                "requiredPermission": "shockers.use",
                "grantedPermissions": [],
            },
        )
        with pytest.raises(PermissionMissingError) as exc_info:
            api_client._request("POST", "2/shockers/control")
        assert exc_info.value.required_permission == "shockers.use"

    def test_request_403_ignores_malformed_permission_metadata(
        self, api_client: OpenShockAPI, mock_api: MockAPI
    ) -> None:
        mock_api.route(
            "POST",
            "/2/shockers/control",
            status=403,
            json={
                "type": "Authorization.Token.PermissionMissing",
                "detail": "Missing permission",
                "requiredPermission": 1,
                "grantedPermissions": ["shockers.read", 2],
            },
        )
        with pytest.raises(PermissionMissingError) as exc_info:
            api_client._request("POST", "2/shockers/control")
        assert exc_info.value.required_permission is None
        assert exc_info.value.granted_permissions == []

    def test_request_404_raises(self, api_client: OpenShockAPI, mock_api: MockAPI) -> None:
        mock_api.route(
            "GET",
            "/1/shockers/bad",
            status=404,
            json={
                "type": "Shocker.NotFound",
                "title": "Not found",
                "status": 404,
                "message": "Shocker not found",
            },
        )
        with pytest.raises(ShockerNotFoundError):
            api_client._request("GET", "1/shockers/bad")

    def test_request_empty_response(self, api_client: OpenShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("GET", "/1", status=204)
        result = api_client._request("GET", "1")
        assert result is None

    def test_request_invalid_json(self, api_client: OpenShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("GET", "/1", status=200, text="not json")
        with pytest.raises(APIError, match="Invalid JSON"):
            api_client._request("GET", "1")

    def test_request_non_object_error(self, api_client: OpenShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("GET", "/1", status=500, json=[])
        with pytest.raises(APIError, match="Unexpected list error response"):
            api_client._request("GET", "1")


class TestGetAccount:
    def test_get_account_success(self, api_client: OpenShockAPI, mock_api: MockAPI) -> None:
        mock_api.route(
            "GET",
            "/1/users/self",
            status=200,
            json=_wrap(
                {
                    "id": "019df66b-08b2-71fd-b0d8-4cb650725974",
                    "name": "testuser",
                    "email": "test@example.com",
                    "image": "https://gravatar.com/test",
                    "roles": [],
                    "rank": "User",
                }
            ),
        )
        account = api_client.get_account()
        assert account.user_id == "019df66b-08b2-71fd-b0d8-4cb650725974"
        assert account.username == "testuser"
        assert account.email == "test@example.com"
        assert account.image == "https://gravatar.com/test"

    def test_get_account_unexpected_type(self, api_client: OpenShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("GET", "/1/users/self", status=200, json=_wrap([]))
        with pytest.raises(APIError, match="Unexpected response from /1/users/self"):
            api_client.get_account()


class TestListShockers:
    def test_list_shockers_owned_only(self, api_client: OpenShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("GET", "/1/shockers/own", status=200, json=_wrap([_owned_device()]))
        mock_api.route("GET", "/1/shockers/shared", status=200, json=_wrap([]))
        shockers = api_client.list_shockers()

        assert len(shockers) == 1
        assert shockers[0].name == "Test Shocker"
        assert shockers[0].is_owned is True
        assert shockers[0].is_shared is False

    def test_list_shockers_shared_only(self, api_client: OpenShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("GET", "/1/shockers/own", status=200, json=_wrap([]))
        mock_api.route("GET", "/1/shockers/shared", status=200, json=_wrap([_shared_owner()]))
        shockers = api_client.list_shockers()

        assert len(shockers) == 1
        assert shockers[0].name == "Shared Shocker"
        assert shockers[0].is_shared is True
        assert shockers[0].is_owned is False
        assert shockers[0].owned_by == "owner123"

    def test_owned_shocker_wins_duplicate(self, api_client: OpenShockAPI, mock_api: MockAPI) -> None:
        sid = "019df66b-e20d-7068-9fbc-ff152fc2dddc"
        mock_api.route("GET", "/1/shockers/own", status=200, json=_wrap([_owned_device(sid)]))
        mock_api.route("GET", "/1/shockers/shared", status=200, json=_wrap([_shared_owner(sid)]))
        shockers = api_client.list_shockers()

        assert len(shockers) == 1

        assert shockers[0].is_owned is True
        assert shockers[0].is_shared is False
        assert shockers[0].owned_by is None
        assert shockers[0].device_id is not None
        assert shockers[0].model is not None
        assert shockers[0].rf_id is not None

    def test_list_shockers_empty(self, api_client: OpenShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("GET", "/1/shockers/own", status=200, json=_wrap([]))
        mock_api.route("GET", "/1/shockers/shared", status=200, json=_wrap([]))
        shockers = api_client.list_shockers()
        assert len(shockers) == 0

    def test_list_shockers_caches(self, api_client: OpenShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("GET", "/1/shockers/own", status=200, json=_wrap([_owned_device()]))
        mock_api.route("GET", "/1/shockers/shared", status=200, json=_wrap([]))

        result1 = api_client.list_shockers()
        assert len(result1) == 1
        result2 = api_client.list_shockers()
        assert result2 is not result1  # different list object
        assert result2 == result1  # same content

    def test_list_shockers_refreshes(self, api_client: OpenShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("GET", "/1/shockers/own", status=200, json=_wrap([_owned_device()]))
        mock_api.route("GET", "/1/shockers/shared", status=200, json=_wrap([]))
        assert api_client.list_shockers()[0].name == "Test Shocker"

        updated = _owned_device()
        updated["shockers"][0]["name"] = "Updated"
        mock_api.route("GET", "/1/shockers/own", status=200, json=_wrap([updated]))

        assert api_client.list_shockers(refresh=True)[0].name == "Updated"

    def test_list_shockers_accepts_null_data(self, api_client: OpenShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("GET", "/1/shockers/own", status=200, json=_wrap(None))
        mock_api.route("GET", "/1/shockers/shared", status=200, json=_wrap(None))
        assert api_client.list_shockers() == []

    def test_list_shockers_rejects_wrong_shape(self, api_client: OpenShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("GET", "/1/shockers/own", status=200, json=_wrap({}))
        mock_api.route("GET", "/1/shockers/shared", status=200, json=_wrap([]))
        with pytest.raises(APIError, match="Unexpected response from /1/shockers/own"):
            api_client.list_shockers()

    def test_list_shockers_rejects_malformed_nested_collection(
        self, api_client: OpenShockAPI, mock_api: MockAPI
    ) -> None:
        mock_api.route(
            "GET",
            "/1/shockers/own",
            status=200,
            json=_wrap([{"id": "device-id", "shockers": None}]),
        )
        mock_api.route("GET", "/1/shockers/shared", status=200, json=_wrap([]))
        with pytest.raises(APIError, match="Unexpected owned device shockers response"):
            api_client.list_shockers()

    def test_list_shockers_translates_model_validation_error(
        self, api_client: OpenShockAPI, mock_api: MockAPI
    ) -> None:
        mock_api.route(
            "GET",
            "/1/shockers/own",
            status=200,
            json=_wrap([{"id": "device-id", "shockers": [{}]}]),
        )
        mock_api.route("GET", "/1/shockers/shared", status=200, json=_wrap([]))
        with pytest.raises(APIError, match="Unexpected OpenShock shocker response"):
            api_client.list_shockers()


class TestGetShockerById:
    def test_get_shocker_by_id_success(self, api_client: OpenShockAPI, mock_api: MockAPI) -> None:
        sid = "019df66b-e20d-7068-9fbc-ff152fc2dddc"
        mock_api.route("GET", "/1/shockers/own", status=200, json=_wrap([_owned_device(sid)]))
        mock_api.route("GET", "/1/shockers/shared", status=200, json=_wrap([]))
        shocker = api_client.get_shocker_by_id(sid)
        assert shocker.shocker_id == sid
        assert shocker.name == "Test Shocker"

    def test_get_shocker_by_id_not_found(self, api_client: OpenShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("GET", "/1/shockers/own", status=200, json=_wrap([]))
        mock_api.route("GET", "/1/shockers/shared", status=200, json=_wrap([]))
        with pytest.raises(ShockerNotFoundError):
            api_client.get_shocker_by_id("nonexistent")


class TestOperateShocker:
    def test_operate_shocker_success(self, api_client: OpenShockAPI, mock_api: MockAPI) -> None:
        sid = "019df66b-e20d-7068-9fbc-ff152fc2dddc"
        mock_api.route("POST", "/2/shockers/control", status=200, json=_wrap(None))

        api_client.operate_shocker(
            shocker=sid,
            operation=ShockerOperation.SHOCK,
            duration=1000,
            intensity=50,
        )

        body = mock_api._last_request["body"]
        assert isinstance(body, dict)
        assert len(body["shocks"]) == 1
        assert body["shocks"][0]["id"] == sid
        assert body["shocks"][0]["type"] == "Shock"
        assert body["shocks"][0]["intensity"] == 50
        assert body["shocks"][0]["duration"] == 1000

    def test_operate_shocker_vibrate(self, api_client: OpenShockAPI, mock_api: MockAPI) -> None:
        sid = "019df66b-e20d-7068-9fbc-ff152fc2dddc"
        mock_api.route("POST", "/2/shockers/control", status=200, json=_wrap(None))

        api_client.operate_shocker(
            shocker=sid,
            operation=ShockerOperation.VIBRATE,
            duration=300,
            intensity=75,
        )

        body = mock_api._last_request["body"]
        assert body["shocks"][0]["type"] == "Vibrate"

    def test_operate_shocker_beep(self, api_client: OpenShockAPI, mock_api: MockAPI) -> None:
        sid = "019df66b-e20d-7068-9fbc-ff152fc2dddc"
        mock_api.route("POST", "/2/shockers/control", status=200, json=_wrap(None))

        api_client.operate_shocker(
            shocker=sid,
            operation=ShockerOperation.BEEP,
            duration=500,
            intensity=50,
        )

        body = mock_api._last_request["body"]
        assert body["shocks"][0]["type"] == "Sound"

    def test_operate_shocker_invalid_duration(self, api_client: OpenShockAPI) -> None:
        with pytest.raises(ValueError, match="duration"):
            api_client.operate_shocker(
                shocker="1",
                operation=ShockerOperation.SHOCK,
                duration=200,
                intensity=50,
            )

    def test_operate_shocker_invalid_intensity(self, api_client: OpenShockAPI) -> None:
        with pytest.raises(ValueError, match="intensity"):
            api_client.operate_shocker(
                shocker="1",
                operation=ShockerOperation.SHOCK,
                duration=1000,
                intensity=150,
            )


class TestHealthCheck:
    def test_health_check_ok(self, mock_api: MockAPI) -> None:
        from pyshock.openshockapi import health_check

        mock_api.route("GET", "/1", status=200, json={"version": "1.0"})

        adapter = WebServerGatewayInterface(app=mock_api)
        real_session = niquests.Session

        def make_session(*args, **kwargs):
            s = real_session(*args, **kwargs)
            s.mount("https://", adapter)
            s.mount("http://", adapter)
            return s

        with patch("pyshock.openshockapi.niquests.Session", side_effect=make_session):
            result = health_check()
        assert result is True

    def test_health_check_down(self) -> None:
        from pyshock.openshockapi import health_check

        with patch(
            "pyshock.openshockapi.niquests.Session",
            side_effect=niquests.RequestException(),
        ):
            result = health_check()
        assert result is False
