"""OpenShock HTTP API client."""

from __future__ import annotations

__all__ = [
    "OpenShockAPI",
    "health_check",
]

import logging
import time
from typing import Literal

import niquests
from niquests.utils import parse_url

from pyshock.constants import (
    API_RETRY_CONFIG,
    MAX_INTENSITY,
    MIN_INTENSITY,
    OPENSHOCK_MAX_DURATION_MS,
    OPENSHOCK_MIN_DURATION_MS,
    TIMEOUT_SECONDS,
)
from pyshock.errors import (
    APIError,
    ForbiddenError,
    NotAuthorizedError,
    PermissionMissingError,
    ShareNotFoundError,
    ShockerNotFoundError,
    TokenAuthNotSupportedError,
)
from pyshock.models.account import AccountInfo
from pyshock.models.operation import ShockerOperation
from pyshock.models.shocker import Shocker

_DEFAULT_BASE_URL = "https://api.openshock.app"

logger = logging.getLogger(__name__)


def _truncate(text: str, limit: int = 512) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def _require_dict_list(value: object, *, context: str, nullable: bool = False) -> list[dict]:
    """Keep malformed provider collections out of the model layer."""
    if value is None and nullable:
        return []
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise APIError(message=f"Unexpected {context} response")
    return value


_OPENSHOCK_CONTROL_TYPES: dict[ShockerOperation, str] = {
    ShockerOperation.SHOCK: "Shock",
    ShockerOperation.VIBRATE: "Vibrate",
    ShockerOperation.BEEP: "Sound",
}

_ERROR_TYPE_MAP: dict[str, type[APIError]] = {
    "Authentication.CookieMissingOrInvalid": NotAuthorizedError,
    "Authentication.Token.Invalid": NotAuthorizedError,
    "Authorization.Token.PermissionMissing": PermissionMissingError,
    "Share.NotFound": ShareNotFoundError,
    "Shocker.NotFound": ShockerNotFoundError,
    "Shocker.Control.NotFound": ShockerNotFoundError,
}


def _handle_openshock_error(response: niquests.Response) -> APIError:
    """Map OpenShock error responses to typed exceptions.

    Parses OpenShockProblem from non-wrapped error responses and maps
    error types to specific exception classes.
    """
    try:
        data = response.json()
    except niquests.JSONDecodeError:
        return APIError(
            message="Invalid JSON in error response",
            status_code=response.status_code,
        )

    if not isinstance(data, dict):
        return APIError(
            message=f"Unexpected {type(data).__name__} error response",
            status_code=response.status_code,
        )

    status = response.status_code
    error_type = data.get("type", "")
    if not isinstance(error_type, str):
        error_type = ""
    message = str(status)
    for key in ("detail", "message", "title"):
        value = data.get(key)
        if isinstance(value, str) and value:
            message = value
            break

    if "PermissionMissing" in error_type:
        required_permission = data.get("requiredPermission")
        if not isinstance(required_permission, str):
            required_permission = None
        granted_permissions = data.get("grantedPermissions")
        if not isinstance(granted_permissions, list) or not all(
            isinstance(permission, str) for permission in granted_permissions
        ):
            granted_permissions = []
        return PermissionMissingError(
            message=message,
            required_permission=required_permission,
            granted_permissions=granted_permissions,
        )

    error_cls = _ERROR_TYPE_MAP.get(error_type)
    if error_cls is not None:
        return error_cls(message=message)

    match status:
        case 401:
            return NotAuthorizedError(message=message)
        case 403:
            return ForbiddenError(message=message)
        case 404:
            return APIError(message=message, status_code=404)
        case 400:
            errors = data.get("errors", {})
            if errors:
                return APIError(message=f"Validation error: {errors}", status_code=400)
            return APIError(message=message, status_code=400)
        case _:
            return APIError(message=message, status_code=status)


def health_check(session: niquests.Session | None = None, base_url: str | None = None) -> bool:
    """Check OpenShock API health.

    Args:
        session: Optional session to reuse. Creates a new one if None.
        base_url: Base URL for the API (defaults to ``https://api.openshock.app``).

    Returns:
        True for 200 or 204, False for errors or timeouts.
    """
    url = f"{base_url or _DEFAULT_BASE_URL}/1"
    try:
        if session is not None:
            resp = session.request("GET", url, timeout=TIMEOUT_SECONDS)
        else:
            with niquests.Session(disable_http2=True, disable_http3=True) as session:
                resp = session.request("GET", url, timeout=TIMEOUT_SECONDS)
        return resp.status_code in (200, 204)
    except niquests.RequestException:
        return False


class OpenShockAPI:
    """HTTP API client for OpenShock.

    Supports two authentication modes:
    - API token: limited endpoints (no share codes)
    - Session cookie: full v1+v2 API access including share codes

    Use as a context manager or call ``close()`` explicitly.
    """

    def __init__(
        self,
        api_token: str | None = None,
        session_cookie: str | None = None,
        base_url: str | None = None,
    ) -> None:
        if (api_token is None) == (session_cookie is None):
            raise ValueError("Provide exactly one of api_token or session_cookie")

        self._base_url = base_url or _DEFAULT_BASE_URL
        host = parse_url(self._base_url).host
        if host is None:
            raise ValueError(f"Cannot extract host from {self._base_url!r}")
        self._cookie_domain = f".{host}"

        self._api_token = api_token
        self._session_cookie = session_cookie
        self._session = niquests.Session(retries=API_RETRY_CONFIG, disable_http2=True, disable_http3=True)
        self._shockers: dict[str, Shocker] | None = None
        if api_token is not None:
            self._session.headers.update({"OpenShockToken": api_token})
        elif session_cookie is not None:
            self._session.cookies.set(  # type: ignore[union-attr]
                "openShockSession", session_cookie, domain=self._cookie_domain
            )

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self._session.close()

    def __enter__(self) -> OpenShockAPI:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    @property
    def is_cookie_auth(self) -> bool:
        """Return True if using session cookie authentication."""
        return self._session_cookie is not None

    def _parse_response(self, response: niquests.Response) -> dict | list | None:
        """Parse and unwrap an OpenShock API response.

        Handles empty bodies, decodes JSON, and unwraps the ``{message, data}``
        envelope pattern.

        Returns:
            Parsed JSON response (unwrapped), or None for empty responses.

        Raises:
            APIError: On invalid JSON.
        """
        if not response.text:
            return None
        try:
            data = response.json()
        except niquests.JSONDecodeError:
            text_preview = response.text[:200] if response.text else "(empty)"
            raise APIError(
                message=f"Invalid JSON in API response, received payload was: {text_preview}",
                status_code=response.status_code,
            ) from None
        if isinstance(data, dict) and "data" in data and "message" in data:
            return data["data"]
        return data

    def _request(
        self,
        method: Literal["GET", "POST", "PUT", "DELETE"],
        endpoint: str,
        body: dict | None = None,
        params: dict | None = None,
    ) -> dict | list | None:
        """Send an authenticated request to OpenShock.

        Unwraps the ``{message, data}`` response pattern. Raises on 4xx/5xx
        and transport errors. Returns parsed JSON or None for empty responses.
        Args:
            method: HTTP method.
            endpoint: API path without leading slash (e.g. ``1/users/self``).
            body: Optional JSON body.
            params: Optional query parameters.

        Returns:
            Parsed JSON response (unwrapped), or None for empty responses.

        Raises:
            APIError: On HTTP 4xx/5xx.
            niquests.RequestException: On transport errors.
        """
        url = f"{self._base_url}/{endpoint}"

        body_str = "" if body is None else _truncate(str(body))
        logger.debug("Out:  %s %s  body=%s", method, url, body_str)

        try:
            start = time.monotonic()
            response = self._session.request(
                method=method,
                url=url,
                json=body,
                params=params,
                timeout=TIMEOUT_SECONDS,
            )
            elapsed_ms = (time.monotonic() - start) * 1000
        except niquests.RequestException as exc:
            logger.debug("Err:  %s %s  %s", method, url, exc)
            raise

        resp_body = _truncate(response.text) if response.text else ""
        logger.debug(
            "In:   %s %s -> %d  %.1fms  body=%s",
            method,
            url,
            response.status_code,
            elapsed_ms,
            resp_body,
        )
        if response.status_code is not None and response.status_code >= 400:  # noqa: PLR2004
            raise _handle_openshock_error(response)

        return self._parse_response(response)

    def link_share_code(self, code: str) -> None:
        """Link a share code to the authenticated account.

        Requires session cookie authentication.

        Args:
            code: The share code to link.

        Raises:
            TokenAuthNotSupportedError: If not using cookie auth.
            APIError: On API errors (400=already linked, 404=not found).
        """
        if not self.is_cookie_auth:
            raise TokenAuthNotSupportedError()
        self._request("POST", f"1/shares/code/{code}")
        self._shockers = None

    def unlink_share_code(self, code: str) -> None:
        """Unlink a share code from the authenticated account.

        Requires session cookie authentication.

        Args:
            code: The share code to unlink.

        Raises:
            TokenAuthNotSupportedError: If not using cookie auth.
            APIError: On API errors (404=not found).
        """
        if not self.is_cookie_auth:
            raise TokenAuthNotSupportedError()
        self._request("DELETE", f"1/shares/code/{code}")
        self._shockers = None

    def get_account(self) -> AccountInfo:
        """Fetch the authenticated user's account info.

        Returns:
            AccountInfo for the current user.

        Raises:
            APIError: On unexpected response or HTTP error.
        """
        data = self._request("GET", "1/users/self")
        if not isinstance(data, dict):
            data_type = type(data).__name__
            data_snippet = repr(data)[:200]
            raise APIError(
                message=f'''\
Unexpected response from /1/users/self.

Response received:

("{data_type}")
{data_snippet}'''
            )
        return AccountInfo.from_openshock_api(data)

    def list_shockers(self, *, refresh: bool = False) -> list[Shocker]:
        """Fetch shockers from /1/shockers/own and /1/shockers/shared, merge by id, and cache.

        Returns the cached list on subsequent calls unless ``refresh`` is true.

        Args:
            refresh: Fetch current data even when this client has a cached result.

        Returns:
            List of all shockers (owned and shared).
        """
        if self._shockers is not None and not refresh:
            return list(self._shockers.values())

        owned_devices = _require_dict_list(
            self._request("GET", "1/shockers/own"),
            context="response from /1/shockers/own",
            nullable=True,
        )
        shared_owners = _require_dict_list(
            self._request("GET", "1/shockers/shared"),
            context="response from /1/shockers/shared",
            nullable=True,
        )

        shockers_by_id: dict[str, Shocker] = {}

        try:
            for owned_device in owned_devices:
                device_id = owned_device.get("id")
                device_shockers = _require_dict_list(
                    owned_device.get("shockers"), context="owned device shockers"
                )
                for shocker_data in device_shockers:
                    shocker = Shocker.from_openshock_owned(shocker_data, device_id=device_id)
                    shockers_by_id[shocker.shocker_id] = shocker

            for shared_owner in shared_owners:
                owner_info = {
                    "name": shared_owner.get("name"),
                    "id": shared_owner.get("id"),
                    "image": shared_owner.get("image"),
                }
                shared_devices = _require_dict_list(
                    shared_owner.get("devices"), context="shared owner devices"
                )
                for shared_device in shared_devices:
                    device_id = shared_device.get("id")
                    device_shockers = _require_dict_list(
                        shared_device.get("shockers"), context="shared device shockers"
                    )
                    for shocker_data in device_shockers:
                        shocker = Shocker.from_openshock_shared(shocker_data, owner_info, device_id=device_id)
                        shockers_by_id.setdefault(shocker.shocker_id, shocker)
        except (AttributeError, TypeError, ValueError) as exc:
            raise APIError(message=f"Unexpected OpenShock shocker response: {exc}") from exc

        self._shockers = shockers_by_id
        return list(self._shockers.values())

    def get_shocker_by_id(self, shocker_id: str) -> Shocker:
        """Look up a shocker by id.

        Fetches and caches shockers if the cache is empty.

        Args:
            shocker_id: The shocker's string id (UUID).

        Returns:
            The matching Shocker.

        Raises:
            ShockerNotFoundError: If the id does not exist.
        """
        if self._shockers is None:
            self.list_shockers()
        if self._shockers is None:
            raise ShockerNotFoundError()
        shocker = self._shockers.get(shocker_id)
        if shocker is None:
            raise ShockerNotFoundError()
        return shocker

    def operate_shocker(
        self,
        shocker: str | Shocker,
        operation: ShockerOperation,
        duration: int,
        intensity: int,
    ) -> None:
        """Operate an OpenShock shocker via POST /2/shockers/control.

        Args:
            shocker: Shocker id (string) or Shocker instance.
            operation: Operation type.
            duration: Duration in milliseconds (300-65535).
            intensity: Intensity 0-100.

        Raises:
            ValueError: If duration or intensity is out of range, or operation is unsupported.
        """
        shocker_id = shocker.shocker_id if isinstance(shocker, Shocker) else shocker

        if not OPENSHOCK_MIN_DURATION_MS <= duration <= OPENSHOCK_MAX_DURATION_MS:
            raise ValueError(
                f"duration must be {OPENSHOCK_MIN_DURATION_MS}-{OPENSHOCK_MAX_DURATION_MS}ms, got {duration!r}"
            )
        if not 0 <= intensity <= MAX_INTENSITY:
            raise ValueError(f"intensity must be {MIN_INTENSITY}-{MAX_INTENSITY}, got {intensity!r}")

        control_type = _OPENSHOCK_CONTROL_TYPES.get(operation)
        if control_type is None:
            raise ValueError(f"unsupported operation: {operation}")

        body = {
            "shocks": [
                {
                    "id": shocker_id,
                    "type": control_type,
                    "intensity": intensity,
                    "duration": duration,
                }
            ]
        }

        self._request("POST", "2/shockers/control", body=body)
