"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def sample_project() -> Path:
    """Return the root of the checked-in sample project."""
    return FIXTURES / "sample_project"
