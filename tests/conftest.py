"""Shared pytest fixtures."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path

import pytest

from repomind.semantic.search import tokenize

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def sample_project() -> Path:
    """Return the root of the checked-in sample project."""
    return FIXTURES / "sample_project"


class FakeEmbedder:
    """Deterministic bag-of-tokens embedder for tests (no model, no network)."""

    def __init__(self, model: str = "fake/model", dimensions: int = 16) -> None:
        """Store the fake model identity and vector size."""
        self._model = model
        self._dimensions = dimensions

    @property
    def model_name(self) -> str:
        """Return a stable identifier used to validate indexes."""
        return self._model

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one deterministic vector per text."""
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self._dimensions
            for token in tokenize(text):
                digest = hashlib.sha1(token.encode("utf-8"), usedforsecurity=False)
                vector[int(digest.hexdigest(), 16) % self._dimensions] += 1.0
            vectors.append(vector)
        return vectors


@pytest.fixture()
def fake_embedder() -> FakeEmbedder:
    """Return a deterministic embedder for semantic tests."""
    return FakeEmbedder()
