"""Shared test configuration."""

from __future__ import annotations

from collections.abc import Generator

import pytest

from tests.mockapi import MockAPI


@pytest.fixture
def mock_api() -> Generator[MockAPI]:
    m = MockAPI()
    yield m
    m.clear()
