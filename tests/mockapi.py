"""Shared mock API infrastructure for tests."""

from __future__ import annotations

import json
from collections.abc import Callable


class _MockRoute:
    __slots__ = ("exc", "json_body", "status", "text")

    def __init__(
        self,
        *,
        status: int = 200,
        json_body: dict | list | None = None,
        text: str | None = None,
        exc: Exception | None = None,
    ) -> None:
        self.status = status
        self.json_body = json_body
        self.text = text
        self.exc = exc


class MockAPI:
    """WSGI app for intercepting niquests calls during tests.

    Routes are matched by (method, path) with prefix matching on the path.
    Register more specific routes first.
    """

    def __init__(self) -> None:
        self._routes: dict[tuple[str, str], _MockRoute] = {}
        self._last_request: dict[str, object] = {}

    def route(
        self,
        method: str,
        path: str,
        *,
        status: int = 200,
        json: dict | list | None = None,
        text: str | None = None,
        exc: Exception | None = None,
    ) -> None:
        self._routes[method, path] = _MockRoute(status=status, json_body=json, text=text, exc=exc)

    def clear(self) -> None:
        self._routes.clear()
        self._last_request.clear()

    def __call__(self, environ: dict, start_response: Callable) -> list[bytes]:
        method = environ["REQUEST_METHOD"]
        path = environ["PATH_INFO"]

        body = None
        content_length = int(environ.get("CONTENT_LENGTH", 0))
        if content_length > 0:
            raw = environ["wsgi.input"].read(content_length)
            try:
                body = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                body = raw

        self._last_request = {"method": method, "path": path, "body": body}

        for (m, p), route in self._routes.items():
            if m == method and (p == path or path.startswith(p)):
                if route.exc is not None:
                    raise route.exc
                if route.text is not None:
                    start_response(f"{route.status} OK", [("Content-Type", "text/plain")])
                    return [route.text.encode()]
                if route.json_body is not None:
                    start_response(f"{route.status} OK", [("Content-Type", "application/json")])
                    return [json.dumps(route.json_body).encode()]
                start_response(f"{route.status} OK", [("Content-Type", "application/json")])
                return [b""]

        start_response("404 Not Found", [("Content-Type", "application/json")])
        return [json.dumps({"error": "not found"}).encode()]
