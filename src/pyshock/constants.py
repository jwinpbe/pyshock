"""Shared API constants."""

from __future__ import annotations

import string

from niquests import RetryConfiguration

BASE62_CHARS: set[str] = set(string.ascii_letters + string.digits)
OPENSHOCK_TOKEN_LENGTH = 64
MAX_PROMPT_ATTEMPTS = 3

TIMEOUT_SECONDS: float = 10.0

API_RETRY_CONFIG = RetryConfiguration(
    total=1,
    backoff_factor=1,
    status_forcelist={500, 502, 503, 504, 510},
)

MIN_INTENSITY = 0
MAX_INTENSITY = 100

PISHOCK_MIN_DURATION_MS = 16
PISHOCK_MAX_DURATION_MS = 15000
OPENSHOCK_MIN_DURATION_MS = 300
OPENSHOCK_MAX_DURATION_MS = 65535

DURATION_DISPLAY_THRESHOLD_MS = 15
