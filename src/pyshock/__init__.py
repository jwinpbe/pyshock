"""PiShock and OpenShock API wrapper and CLI."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version

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
    PermissionMissingError,
    SessionOnlyError,
    ShareAlreadyClaimedError,
    ShareLockedError,
    ShareNotFoundError,
    ShockerNotFoundError,
    ShockerPausedError,
    TokenAuthNotSupportedError,
    TooManySharesError,
)
from pyshock.models import AccountInfo, OperationName, Shocker, ShockerOperation
from pyshock.openshockapi import OpenShockAPI
from pyshock.openshockapi import health_check as openshock_health_check
from pyshock.pishockapi import PiShockAPI, health_check

try:
    __version__ = _version("pyshock")
except PackageNotFoundError:
    __version__ = "dev"

__all__ = [
    "APIError",
    "AccountInfo",
    "AccountNotFoundError",
    "DeviceNotV3Error",
    "DurationOutOfRangeError",
    "ForbiddenError",
    "HubNotFoundError",
    "IntensityOutOfRangeError",
    "NoSharesProvidedError",
    "NotAuthorizedError",
    "OpenShockAPI",
    "OperationName",
    "OperationNotAllowedError",
    "PermissionMissingError",
    "PiShockAPI",
    "SessionOnlyError",
    "ShareAlreadyClaimedError",
    "ShareLockedError",
    "ShareNotFoundError",
    "Shocker",
    "ShockerNotFoundError",
    "ShockerOperation",
    "ShockerPausedError",
    "TokenAuthNotSupportedError",
    "TooManySharesError",
    "__version__",
    "health_check",
    "openshock_health_check",
]
