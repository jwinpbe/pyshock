"""PiShock HTTP API client."""

from __future__ import annotations

__all__ = [
    "PiShockAPI",
    "health_check",
]

import logging
import time
from dataclasses import replace
from typing import TYPE_CHECKING, Literal

import niquests

from pyshock.constants import (
    API_RETRY_CONFIG,
    MAX_INTENSITY,
    MIN_INTENSITY,
    PISHOCK_MAX_DURATION_MS,
    PISHOCK_MIN_DURATION_MS,
    TIMEOUT_SECONDS,
)
from pyshock.errors import (
    AccountNotFoundError,
    APIError,
    DeviceNotV3Error,
    DurationOutOfRangeError,
    ForbiddenError,
    HubNotFoundError,
    IntensityOutOfRangeError,
    NoSharesProvidedError,
    NotAuthorizedError,
    OperationNotAllowedError,
    ShareAlreadyClaimedError,
    ShareLockedError,
    ShareNotFoundError,
    ShockerNotFoundError,
    ShockerPausedError,
    TooManySharesError,
)
from pyshock.models.account import AccountInfo
from pyshock.models.shocker import Shocker

if TYPE_CHECKING:
    from pyshock.models.operation import ShockerOperation

logger = logging.getLogger(__name__)


def _truncate(text: str, limit: int = 512) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def _apply_owned_fields(shared: Shocker, owned: Shocker) -> Shocker:
    """Copy identifying metadata from the owned record onto the shared record."""
    return replace(
        shared,
        name=owned.name,
        is_v3=owned.is_v3,
        pishock_hub_id=owned.pishock_hub_id,
    )


BASE_URL = "https://api.pishock.com"

_API_ERROR_MAP: dict[int, type[APIError]] = {
    401: NotAuthorizedError,
    403: ForbiddenError,
    405: OperationNotAllowedError,
    406: DeviceNotV3Error,
    410: ShareLockedError,
    412: IntensityOutOfRangeError,
    416: DurationOutOfRangeError,
    503: ShockerPausedError,
}

_404_NOT_FOUND_MAP: dict[str, type[APIError]] = {
    "Account": AccountNotFoundError,
    "Shockers": ShockerNotFoundError,
    "Share": ShareNotFoundError,
    "Hub": HubNotFoundError,
}


def _handle_error(response: niquests.Response) -> APIError:
    """Map HTTP error responses to typed exceptions.

    Routes 404s by resource name from the path. Reinterprets reused status
    codes for PUT /Share. Returns generic APIError for unhandled codes.
    """
    status = response.status_code

    if status is None:
        return APIError(
            message=(
                "Response had no status code. "
                "Please open a github issue immediately "
                "and send vitriolic abuse to the maintainer."
            ),
            status_code=None,
        )

    request = response.request
    method = request.method if request is not None else None
    path = request.path_url if request is not None else ""

    if status == 404:  # ruff:ignore[magic-value-comparison]
        resource = path.split("/", 2)[1]  # ope just gonna squeeze by ya there bud
        error_cls = _404_NOT_FOUND_MAP.get(resource)
        if error_cls is not None:
            return error_cls()
        return APIError(message="Resource not found.", status_code=404)

    if method == "PUT" and path == "/Share":
        match status:
            case 410:
                return ShareAlreadyClaimedError()
            case 412:
                return NoSharesProvidedError()
            case 416:
                return TooManySharesError()

    error_cls = _API_ERROR_MAP.get(status)
    if error_cls is not None:
        return error_cls()

    return APIError(message=f"Unexpected error: {status}", status_code=status)


def health_check(session: niquests.Session | None = None) -> bool:
    """Check API health.

    Args:
        session: Optional session to reuse. Creates a new one if None.

    Returns:
        True for 200 or 204, False for errors or timeouts.
    """
    try:
        if session is not None:
            resp = session.request("GET", f"{BASE_URL}/Health", timeout=TIMEOUT_SECONDS)
        else:
            with niquests.Session() as session:
                resp = session.request("GET", f"{BASE_URL}/Health", timeout=TIMEOUT_SECONDS)
        return resp.status_code in (200, 204)
    except niquests.RequestException:
        return False


class PiShockAPI:
    """HTTP API client for PiShock.

    Use as a context manager or call ``close()`` explicitly.
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._session = niquests.Session(retries=API_RETRY_CONFIG)
        self._session.headers.update({
            "X-PiShock-Api-Key": api_key,
        })
        self._shockers: dict[str, Shocker] | None = None
        self._share_code_index: dict[str, str] | None = None

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self._session.close()

    def __enter__(self) -> PiShockAPI:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _request(
        self,
        method: Literal["GET", "POST", "PUT", "DELETE"],
        endpoint: str,
        body: dict[str, object] | None = None,
        params: dict[str, str] | None = None,
    ) -> dict[str, object] | list[dict[str, object]] | None:
        """Send an authenticated request.

        Raises on 4xx/5xx and transport errors. Returns parsed JSON or
        None for empty responses.

        Args:
            method: HTTP method.
            endpoint: API path without leading slash.
            body: Optional JSON body.
            params: Optional query parameters.

        Returns:
            Parsed JSON response, or None for empty responses.

        Raises:
            APIError: On HTTP 4xx/5xx.
            niquests.RequestException: On transport errors.
        """
        url = f"{BASE_URL}/{endpoint}"

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

        if response.status_code is not None and response.status_code >= 400:  # ruff:ignore[magic-value-comparison]
            raise _handle_error(response)

        if not response.text:
            return None

        try:
            return response.json()
        except niquests.JSONDecodeError:
            logger.debug(
                "JSON parse failed: %s %s status=%d body=%s",
                method,
                url,
                response.status_code,
                _truncate(response.text),
            )
            raise APIError(
                message=f"Invalid JSON in API response, received payload was: {response.text[:200]}",
                status_code=response.status_code,
            ) from None

    def get_account(self) -> AccountInfo:
        """Fetch the authenticated user's account info.

        Returns:
            AccountInfo for the current user.

        Raises:
            APIError: On unexpected response or HTTP error.
        """
        data = self._request("GET", "Account")
        if not isinstance(data, dict):
            data_type = type(data).__name__
            data_snippet = repr(data)[:200]
            raise APIError(
                message=f'''\
Unexpected response from Account endpoint.

Response received:

("{data_type}")
{data_snippet}'''
            )
        return AccountInfo.from_api(data)

    def list_shockers(self, *, refresh: bool = False) -> list[Shocker]:
        """Fetch shockers from /Shockers and /Share/GetShared, merge by id, and cache.

        Returns the cached list on subsequent calls unless ``refresh`` is true.

        Args:
            refresh: Fetch current data even when this client has a cached result.

        Returns:
            List of all shockers (owned and shared).
        """
        if self._shockers is not None and not refresh:
            return list(self._shockers.values())

        claimed_data = self._request("GET", "Shockers")
        shared_data = self._request("GET", "Share/GetShared")

        if not isinstance(claimed_data, list):
            raise APIError(message="Unexpected response from Shockers endpoint")
        if not isinstance(shared_data, list):
            raise APIError(message="Unexpected response from Share/GetShared endpoint")
        if not all(isinstance(item, dict) for item in claimed_data):
            raise APIError(message="Unexpected response from Shockers endpoint")
        if not all(isinstance(item, dict) for item in shared_data):
            raise APIError(message="Unexpected response from Share/GetShared endpoint")

        claimed = {s.shocker_id: s for s in (Shocker.from_api(item) for item in claimed_data)}

        for item in shared_data:
            shared = Shocker.from_api(item)
            if shared.shocker_id in claimed:
                base = claimed[shared.shocker_id]
                claimed[shared.shocker_id] = _apply_owned_fields(shared, base)
            else:
                # Shared shocker not in claimed -- currently not possible but this is defensive
                claimed[shared.shocker_id] = shared

        self._share_code_index = {s.share_code: s.shocker_id for s in claimed.values() if s.share_code is not None}

        self._shockers = claimed
        return list(self._shockers.values())

    def get_shocker_by_id(self, shocker_id: str) -> Shocker:
        """Look up a shocker by id.

        Fetches and caches shockers if the cache is empty.

        Args:
            shocker_id: The shocker's string id.

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

    def get_shocker_by_share_code(self, share_code: str) -> Shocker:
        """Look up a shocker by share code.

        Fetches and caches shockers if the cache is empty.

        Args:
            share_code: The share code string.

        Returns:
            The matching Shocker.

        Raises:
            ShareNotFoundError: If the code does not exist.
        """
        if self._shockers is None:
            self.list_shockers()
        shockers = self._shockers
        index = self._share_code_index
        if shockers is None or index is None:
            raise ShareNotFoundError()
        shocker_id = index.get(share_code)
        if shocker_id is None or shocker_id not in shockers:
            raise ShareNotFoundError()
        return shockers[shocker_id]

    def add_share_code(self, code: str) -> None:
        """Claim a share code.

        Invalidates the shocker cache.

        Args:
            code: The share code to claim.

        Raises:
            NoSharesProvidedError: If the code is empty.
        """
        if not code or not code.strip():
            raise NoSharesProvidedError()

        self._request("PUT", "Share", body={"Shares": [code]})
        self._shockers = None
        self._share_code_index = None

    def add_share_codes(self, codes: list[str]) -> None:
        """Claim multiple share codes.

        Max 20 per call. Invalidates the shocker cache.

        Args:
            codes: List of share codes to claim.

        Raises:
            NoSharesProvidedError: If the list is empty.
            TooManySharesError: If more than 20 codes.
        """
        if not codes:
            raise NoSharesProvidedError()
        if len(codes) > 20:  # ruff:ignore[magic-value-comparison]
            raise TooManySharesError()

        self._request("PUT", "Share", body={"Shares": codes})
        self._shockers = None
        self._share_code_index = None

    def delete_share(self, share_id: int | str) -> None:
        """Remove a share by id.

        Invalidates the shocker cache.

        Args:
            share_id: The share identifier returned by ``Share/GetShared``.
        """
        self._request("DELETE", f"Share/{share_id}")
        self._shockers = None
        self._share_code_index = None

    def operate_shocker(
        self,
        shocker: str | Shocker,
        operation: ShockerOperation,
        duration: int,
        intensity: int,
    ) -> None:
        """Operate a PiShock shocker.

        Args:
            shocker: Shocker id (string) or Shocker instance.
            operation: Operation type.
            duration: Duration in milliseconds (16-15000).
            intensity: Intensity 0-100.

        Raises:
            ValueError: If duration or intensity is out of range.
        """
        shocker_id = shocker.shocker_id if isinstance(shocker, Shocker) else shocker
        if not PISHOCK_MIN_DURATION_MS <= duration <= PISHOCK_MAX_DURATION_MS:
            raise ValueError(
                f"duration must be {PISHOCK_MIN_DURATION_MS}-{PISHOCK_MAX_DURATION_MS}ms, got {duration!r}"
            )
        if not 0 <= intensity <= MAX_INTENSITY:
            raise ValueError(f"intensity must be {MIN_INTENSITY}-{MAX_INTENSITY}, got {intensity!r}")

        body: dict = {
            "Operation": operation,
            "Duration": duration,
            "Intensity": intensity,
        }

        self._request("POST", f"Shockers/{shocker_id}", body=body)
