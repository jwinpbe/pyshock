"""Shared API constants."""

from __future__ import annotations

from niquests import RetryConfiguration

# HTTP request timeout in seconds
TIMEOUT_SECONDS: float = 10.0

# Retry configuration for API sessions
API_RETRY_CONFIG = RetryConfiguration(
    total=1,
    backoff_factor=1,
    status_forcelist={500, 502, 503, 504, 510},
)
# OpenShock maximum command duration in milliseconds
OPENSHOCK_MAX_DURATION_MS = 65535
OPENSHOCK_MIN_DURATION_MS = 300

# PiShock duration range in milliseconds
PISHOCK_MIN_DURATION_MS = 100
PISHOCK_MAX_DURATION_MS = 15000

MIN_INTENSITY = 0
MAX_INTENSITY = 100

DURATION_DISPLAY_THRESHOLD_MS = 15
