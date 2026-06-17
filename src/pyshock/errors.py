"""Error types for PyShock."""

from __future__ import annotations

__all__ = [
    "APIError",
    "AccountNotFoundError",
    "CliError",
    "DeviceNotV3Error",
    "DurationOutOfRangeError",
    "ForbiddenError",
    "HubNotFoundError",
    "IntensityOutOfRangeError",
    "NoSharesProvidedError",
    "NotAuthorizedError",
    "OperationNotAllowedError",
    "PermissionMissingError",
    "SessionOnlyError",
    "ShareAlreadyClaimedError",
    "ShareLockedError",
    "ShareNotFoundError",
    "ShockerNotFoundError",
    "ShockerPausedError",
    "TokenAuthNotSupportedError",
    "TooManySharesError",
]


class APIError(Exception):
    """Base API error."""

    message: str = ""
    status_code: int | None = None

    def __init__(self, *, message: str | None = None, status_code: int | None = None) -> None:
        self.message = message if message is not None else self.__class__.message
        self.status_code = status_code if status_code is not None else self.__class__.status_code
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.status_code:
            return f"{self.message} (status: {self.status_code})"
        return self.message


class NotAuthorizedError(APIError):
    """Authentication failed."""

    message = "Not authorized. Check your API key."
    status_code = 401


class ForbiddenError(APIError):
    """Access forbidden."""

    message = "Forbidden. You do not have permission for this action."
    status_code = 403


class AccountNotFoundError(APIError):
    """Account not found."""

    message = "Account not found."
    status_code = 404


class HubNotFoundError(APIError):
    """Hub not found."""

    message = "Hub not found."
    status_code = 404


class ShareNotFoundError(APIError):
    """Share not found."""

    message = "Could not find share."
    status_code = 404


class ShockerNotFoundError(APIError):
    """Shocker not found."""

    message = "Shocker not found."
    status_code = 404


class OperationNotAllowedError(APIError):
    """Operation not allowed by share settings."""

    message = "Operation not allowed by share settings."
    status_code = 405


class DeviceNotV3Error(APIError):
    """Device is not V3."""

    message = "Device is not V3. Please flash V3 firmware or contact support."
    status_code = 406


class ShareLockedError(APIError):
    """Share is locked."""

    message = "Share is locked."
    status_code = 410


class IntensityOutOfRangeError(APIError):
    """Intensity out of bounds."""

    message = "Intensity is out of bounds (<0, >100, or higher than max intensity)."
    status_code = 412


class DurationOutOfRangeError(APIError):
    """Duration exceeds limits."""

    message = "Duration exceeds limits (<16ms or >15000ms)."
    status_code = 416


class ShockerPausedError(APIError):
    """Share or shocker is paused."""

    message = "Share or shocker is paused."
    status_code = 503


class ShareAlreadyClaimedError(APIError):
    """Share code is already claimed."""

    message = "Share code is already claimed."
    status_code = 410


class NoSharesProvidedError(APIError):
    """Must provide at least 1 share code."""

    message = "Must provide at least 1 share code."
    status_code = 412


class TooManySharesError(APIError):
    """Cannot batch claim more than 20 codes."""

    message = "Cannot batch claim more than 20 codes."
    status_code = 416


class CliError(Exception):
    """CLI error caught at top level and printed."""


class PermissionMissingError(APIError):
    """OpenShock token lacks required permission."""

    message = "API token lacks the required permission."
    status_code = 403

    def __init__(
        self,
        *,
        required_permission: str | None = None,
        granted_permissions: list[str] | None = None,
        message: str | None = None,
    ) -> None:
        self.required_permission = required_permission
        self.granted_permissions = granted_permissions
        if required_permission:
            msg = f"Missing permission: {required_permission}."
            if granted_permissions:
                msg += f" Granted: {', '.join(granted_permissions)}."
        elif message is not None:
            msg = message
        else:
            msg = self.message
        super().__init__(message=msg, status_code=403)


class SessionOnlyError(APIError):
    """Operation requires session authentication, not available with API token."""

    message = "This operation requires session authentication. Use the OpenShock web interface."
    status_code = 403


class TokenAuthNotSupportedError(APIError):
    """Operation requires cookie authentication, not available with API token."""

    message = "This operation requires cookie authentication. Re-run 'pyshock init' with browser cookie auth."
    status_code = 403
