"""Tests for OpenShockAPI cookie auth and share code methods."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from niquests.extensions.sgi import WebServerGatewayInterface

from pyshock.errors import APIError, TokenAuthNotSupportedError
from pyshock.openshockapi import OpenShockAPI
from tests.mockapi import MockAPI


@pytest.fixture
def cookie_api(mock_api: MockAPI) -> Generator[OpenShockAPI]:
    api = OpenShockAPI(session_cookie="test_cookie")
    adapter = WebServerGatewayInterface(app=mock_api)
    api._session.mount("https://", adapter)
    api._session.mount("http://", adapter)
    yield api
    api.close()


@pytest.fixture
def token_api(mock_api: MockAPI) -> Generator[OpenShockAPI]:
    api = OpenShockAPI(api_token="test_token")
    adapter = WebServerGatewayInterface(app=mock_api)
    api._session.mount("https://", adapter)
    api._session.mount("http://", adapter)
    yield api
    api.close()


def _wrap(data):
    return {"message": "", "data": data}


class TestCookieAuthInit:
    def test_init_with_session_cookie(self, cookie_api: OpenShockAPI) -> None:
        assert cookie_api.is_cookie_auth is True
        assert cookie_api._session_cookie == "test_cookie"

    def test_init_with_api_token(self, token_api: OpenShockAPI) -> None:
        assert token_api.is_cookie_auth is False
        assert token_api._api_token == "test_token"

    def test_init_with_both_raises(self) -> None:
        with pytest.raises(ValueError, match="exactly one"):
            OpenShockAPI(api_token="tok", session_cookie="cookie")

    def test_init_with_neither_raises(self) -> None:
        with pytest.raises(ValueError, match="exactly one"):
            OpenShockAPI()

    def test_cookie_set_on_session(self, cookie_api: OpenShockAPI) -> None:
        cookies = list(cookie_api._session.cookies)
        assert any(c.name == "openShockSession" for c in cookies)


class TestCookieAuthRequest:
    def test_request_with_cookie_auth(self, cookie_api: OpenShockAPI, mock_api: MockAPI) -> None:
        mock_api.route(
            "GET",
            "/1/users/self",
            status=200,
            json=_wrap({"id": "123", "name": "test"}),
        )
        result = cookie_api._request("GET", "1/users/self")
        assert result == {"id": "123", "name": "test"}


class TestLinkShareCode:
    def test_link_share_code_success(self, cookie_api: OpenShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("POST", "/1/shares/code/abc123", status=200, json=_wrap(None))
        cookie_api.link_share_code("abc123")
        assert mock_api._last_request["method"] == "POST"
        assert mock_api._last_request["path"] == "/1/shares/code/abc123"

    def test_link_share_code_token_mode_raises(self, token_api: OpenShockAPI) -> None:
        with pytest.raises(TokenAuthNotSupportedError, match="cookie authentication"):
            token_api.link_share_code("abc123")

    def test_link_share_code_already_linked_400(
        self, cookie_api: OpenShockAPI, mock_api: MockAPI
    ) -> None:
        mock_api.route(
            "POST",
            "/1/shares/code/abc123",
            status=400,
            json={
                "type": "Share.AlreadyLinked",
                "title": "Already linked",
                "status": 400,
                "message": "You already have this shocker linked to your account",
            },
        )
        with pytest.raises(APIError, match="Validation error"):
            cookie_api.link_share_code("abc123")

    def test_link_share_code_not_found_404(
        self, cookie_api: OpenShockAPI, mock_api: MockAPI
    ) -> None:
        mock_api.route(
            "POST",
            "/1/shares/code/nonexistent",
            status=404,
            json={
                "type": "Share.NotFound",
                "title": "Not found",
                "status": 404,
                "message": "Share code not found",
            },
        )
        with pytest.raises(APIError, match="not found"):
            cookie_api.link_share_code("nonexistent")

    def test_link_share_code_invalidates_cache(
        self, cookie_api: OpenShockAPI, mock_api: MockAPI
    ) -> None:
        mock_api.route(
            "GET",
            "/1/shockers/own",
            status=200,
            json=_wrap([
                {
                    "id": "device-1",
                    "name": "Hub",
                    "shockers": [
                        {"id": "shocker-1", "name": "My Shocker", "isPaused": False},
                    ],
                }
            ]),
        )
        mock_api.route("GET", "/1/shockers/shared", status=200, json=_wrap([]))
        cookie_api.list_shockers()
        assert cookie_api._shockers is not None

        mock_api.route("POST", "/1/shares/code/newcode", status=200, json=_wrap(None))
        cookie_api.link_share_code("newcode")
        assert cookie_api._shockers is None


class TestUnlinkShareCode:
    def test_unlink_share_code_success(self, cookie_api: OpenShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("DELETE", "/1/shares/code/abc123", status=200, json=_wrap(None))
        cookie_api.unlink_share_code("abc123")
        assert mock_api._last_request["method"] == "DELETE"
        assert mock_api._last_request["path"] == "/1/shares/code/abc123"

    def test_unlink_share_code_token_mode_raises(self, token_api: OpenShockAPI) -> None:
        with pytest.raises(TokenAuthNotSupportedError, match="cookie authentication"):
            token_api.unlink_share_code("abc123")

    def test_unlink_share_code_not_found_404(
        self, cookie_api: OpenShockAPI, mock_api: MockAPI
    ) -> None:
        mock_api.route(
            "DELETE",
            "/1/shares/code/nonexistent",
            status=404,
            json={
                "type": "Share.NotFound",
                "title": "Not found",
                "status": 404,
                "message": "Share code not found",
            },
        )
        with pytest.raises(APIError, match="not found"):
            cookie_api.unlink_share_code("nonexistent")

    def test_unlink_share_code_invalidates_cache(
        self, cookie_api: OpenShockAPI, mock_api: MockAPI
    ) -> None:
        mock_api.route(
            "GET",
            "/1/shockers/own",
            status=200,
            json=_wrap([
                {
                    "id": "device-1",
                    "name": "Hub",
                    "shockers": [
                        {"id": "shocker-1", "name": "My Shocker", "isPaused": False},
                    ],
                }
            ]),
        )
        mock_api.route("GET", "/1/shockers/shared", status=200, json=_wrap([]))
        cookie_api.list_shockers()
        assert cookie_api._shockers is not None

        mock_api.route("DELETE", "/1/shares/code/abc123", status=200, json=_wrap(None))
        cookie_api.unlink_share_code("abc123")
        assert cookie_api._shockers is None


class TestListShareCodes:
    def test_list_share_codes_success(self, cookie_api: OpenShockAPI, mock_api: MockAPI) -> None:
        mock_api.route(
            "GET",
            "/2/shares/user",
            status=200,
            json=_wrap(
                {
                    "outgoing": [
                        {
                            "id": "owner-1",
                            "name": "owner1",
                            "image": "https://example.com/img.png",
                            "shares": [
                                {
                                    "id": "shocker-1",
                                    "name": "Shared Shocker",
                                    "createdOn": "2024-01-01T00:00:00Z",
                                    "permissions": {"shock": True, "vibrate": True, "sound": True, "live": False},
                                    "limits": {"intensity": 50, "duration": 3000},
                                    "paused": 0,
                                }
                            ],
                        }
                    ],
                    "incoming": [],
                }
            ),
        )
        result = cookie_api.list_share_codes()
        assert len(result) == 1
        assert result[0].shocker_id == "shocker-1"
        assert result[0].name == "Shared Shocker"
        assert result[0].can_shock is True
        assert result[0].max_intensity == 50
        assert result[0].max_duration == 3000

    def test_list_share_codes_token_mode_raises(self, token_api: OpenShockAPI) -> None:
        with pytest.raises(TokenAuthNotSupportedError, match="cookie authentication"):
            token_api.list_share_codes()

    def test_list_share_codes_empty(self, cookie_api: OpenShockAPI, mock_api: MockAPI) -> None:
        mock_api.route("GET", "/2/shares/user", status=200, json=_wrap({"outgoing": [], "incoming": []}))
        result = cookie_api.list_share_codes()
        assert result == []

    def test_list_share_codes_multiple_owners(
        self, cookie_api: OpenShockAPI, mock_api: MockAPI
    ) -> None:
        mock_api.route(
            "GET",
            "/2/shares/user",
            status=200,
            json=_wrap({
                "outgoing": [
                    {
                        "id": "owner-1",
                        "name": "alice",
                        "image": "https://example.com/alice.png",
                        "shares": [
                            {
                                "id": "shocker-a",
                                "name": "Alice Shocker",
                                "createdOn": "2024-01-01T00:00:00Z",
                                "permissions": {"shock": True, "vibrate": True, "sound": False, "live": False},
                                "limits": {"intensity": 80, "duration": 5000},
                                "paused": 0,
                            },
                        ],
                    },
                    {
                        "id": "owner-2",
                        "name": "bob",
                        "image": "https://example.com/bob.png",
                        "shares": [
                            {
                                "id": "shocker-b",
                                "name": "Bob Shocker",
                                "createdOn": "2024-02-01T00:00:00Z",
                                "permissions": {"shock": False, "vibrate": True, "sound": True, "live": True},
                                "limits": {"intensity": None, "duration": None},
                                "paused": 0,
                            },
                        ],
                    },
                ],
                "incoming": [],
            }),
        )
        result = cookie_api.list_share_codes()
        assert len(result) == 2
        assert result[0].shocker_id == "shocker-a"
        assert result[0].can_shock is True
        assert result[0].max_intensity == 80
        assert result[0].max_duration == 5000
        assert result[0].owned_by == "alice"
        assert result[1].shocker_id == "shocker-b"
        assert result[1].can_shock is False
        assert result[1].can_hold is True
        assert result[1].max_intensity == 100
        assert result[1].max_duration == 65535
        assert result[1].owned_by == "bob"

    def test_list_share_codes_multiple_shares_per_owner(
        self, cookie_api: OpenShockAPI, mock_api: MockAPI
    ) -> None:
        mock_api.route(
            "GET",
            "/2/shares/user",
            status=200,
            json=_wrap({
                "outgoing": [
                    {
                        "id": "owner-1",
                        "name": "alice",
                        "image": "https://example.com/alice.png",
                        "shares": [
                            {
                                "id": "shocker-1",
                                "name": "Shocker 1",
                                "createdOn": "2024-01-01T00:00:00Z",
                                "permissions": {"shock": True, "vibrate": True, "sound": True, "live": False},
                                "limits": {"intensity": 50, "duration": 3000},
                                "paused": 0,
                            },
                            {
                                "id": "shocker-2",
                                "name": "Shocker 2",
                                "createdOn": "2024-01-02T00:00:00Z",
                                "permissions": {"shock": True, "vibrate": False, "sound": False, "live": False},
                                "limits": {"intensity": 100, "duration": 65535},
                                "paused": 0,
                            },
                        ],
                    },
                ],
                "incoming": [],
            }),
        )
        result = cookie_api.list_share_codes()
        assert len(result) == 2
        assert result[0].shocker_id == "shocker-1"
        assert result[1].shocker_id == "shocker-2"
        assert result[0].owned_by == "alice"
        assert result[1].owned_by == "alice"

    def test_list_share_codes_paused_shocker(
        self, cookie_api: OpenShockAPI, mock_api: MockAPI
    ) -> None:
        mock_api.route(
            "GET",
            "/2/shares/user",
            status=200,
            json=_wrap({
                "outgoing": [
                    {
                        "id": "owner-1",
                        "name": "alice",
                        "image": "https://example.com/alice.png",
                        "shares": [
                            {
                                "id": "shocker-1",
                                "name": "Paused Shocker",
                                "createdOn": "2024-01-01T00:00:00Z",
                                "permissions": {"shock": True, "vibrate": True, "sound": True, "live": False},
                                "limits": {"intensity": 50, "duration": 3000},
                                "paused": 1,
                            },
                        ],
                    },
                ],
                "incoming": [],
            }),
        )
        result = cookie_api.list_share_codes()
        assert len(result) == 1
        assert result[0].paused is True

    def test_list_share_codes_incoming_ignored(
        self, cookie_api: OpenShockAPI, mock_api: MockAPI
    ) -> None:
        mock_api.route(
            "GET",
            "/2/shares/user",
            status=200,
            json=_wrap({
                "outgoing": [],
                "incoming": [
                    {
                        "id": "owner-1",
                        "name": "alice",
                        "image": "https://example.com/alice.png",
                        "shares": [
                            {
                                "id": "shocker-1",
                                "name": "Incoming Shocker",
                                "createdOn": "2024-01-01T00:00:00Z",
                                "permissions": {"shock": True, "vibrate": True, "sound": True, "live": False},
                                "limits": {"intensity": 50, "duration": 3000},
                                "paused": 0,
                            },
                        ],
                    },
                ],
            }),
        )
        result = cookie_api.list_share_codes()
        assert result == []

    def test_list_share_codes_non_dict_response(
        self, cookie_api: OpenShockAPI, mock_api: MockAPI
    ) -> None:
        mock_api.route("GET", "/2/shares/user", status=200, json=_wrap([]))
        result = cookie_api.list_share_codes()
        assert result == []
