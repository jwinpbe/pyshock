"""Account data models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict


class AccountEntry(TypedDict, total=False):
    """Single account configuration entry."""

    provider: str  # "pishock" | "openshock"
    api_key: str  # pishock only
    api_token: str  # openshock, limited endpoints
    session_cookie: str  # openshock, full v1+v2 access
    shockers: list[dict[str, Any]]  # cached shocker dicts
    browser_type: str  # openshock cookie auth
    browser_cookie_path: str  # openshock cookie auth: path to Cookies DB
    browser_key_path: str  # openshock cookie auth: path to Login Data


@dataclass(frozen=True, kw_only=True)
class AccountInfo:
    """Authenticated user account details."""

    user_id: str
    username: str
    email: str | None = None
    image: str | None = None
    roles: list[str] | None = None
    rank: str | None = None

    def __repr__(self) -> str:
        return f"AccountInfo({self.username!r}, id={self.user_id!r})"

    @classmethod
    def from_api(cls, data: dict) -> AccountInfo:
        """Construct from a raw PiShock API response dict.

        Args:
            data: Raw API response with UserId and Username.

        Returns:
            AccountInfo instance.

        Raises:
            ValueError: If required fields are missing.
        """
        required = {"UserId", "Username"}
        missing = required - data.keys()
        if missing:
            raise ValueError(f"AccountInfo: missing API fields {sorted(missing)}")

        return cls(
            user_id=str(data["UserId"]),
            username=data["Username"],
        )

    @classmethod
    def from_openshock_api(cls, data: dict) -> AccountInfo:
        """Construct from an OpenShock /1/users/self response.

        Args:
            data: Raw OpenShock UserSelfResponse dict.

        Returns:
            AccountInfo instance.

        Raises:
            ValueError: If required fields are missing.
        """
        required = {"id", "name"}
        missing = required - data.keys()
        if missing:
            raise ValueError(f"AccountInfo: missing OpenShock fields {sorted(missing)}")

        return cls(
            user_id=data["id"],
            username=data["name"],
            email=data.get("email"),
            image=data.get("image"),
            roles=data.get("roles"),
            rank=data.get("rank"),
        )
