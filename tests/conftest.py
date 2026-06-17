"""Shared test configuration."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import platformdirs
import pytest

from pyshock.cli.config import reset_config_cache
from tests.mockapi import MockAPI


@pytest.fixture
def mock_api() -> Generator[MockAPI]:
    m = MockAPI()
    yield m
    m.clear()


@pytest.fixture(autouse=True)
def _clean_config():
    """Remove PyShock config before each test."""
    config_path = Path(platformdirs.user_config_dir("PyShock")) / "config.json"
    if config_path.exists():
        config_path.unlink()
    reset_config_cache()
    yield
    if config_path.exists():
        config_path.unlink()
    reset_config_cache()
