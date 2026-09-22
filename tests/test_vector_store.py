"""Tests for the local vector store."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from repomind.semantic.chunking import CodeChunk
from repomind.semantic.store import StoredChunk, VectorStore, load_store, save_store


def _chunk(chunk_id: str, text: str = "def x(): pass") -> CodeChunk:
    return CodeChunk(
        chunk_id=chunk_id,
        kind="function",
        path="app.py",
        symbol="app.x",
        lineno=1,
        end_lineno=1,
        text=text,
    )


def _store() -> VectorStore:
    chunks = [
        StoredChunk.from_chunk(_chunk("a", "def alpha(): pass")),
        StoredChunk.from_chunk(_chunk("b", "def beta(): pass")),
    ]
    vectors = np.asarray([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    return VectorStore(model_name="fake/model", chunks=chunks, vectors=vectors)


def test_store_round_trip(tmp_path: Path) -> None:
    store = _store()

    save_store(tmp_path / ".repomind", store)
    loaded = load_store(tmp_path / ".repomind", "fake/model")

    assert loaded is not None
    assert loaded.dimensions == 2
    assert [chunk.chunk_id for chunk in loaded.chunks] == ["a", "b"]
    assert loaded.chunks[0].content_hash == store.chunks[0].content_hash
    assert loaded.chunks[0].text == "def alpha(): pass"


def test_load_store_rejects_other_models(tmp_path: Path) -> None:
    save_store(tmp_path / ".repomind", _store())

    assert load_store(tmp_path / ".repomind", "other/model") is None


def test_load_store_returns_none_without_files(tmp_path: Path) -> None:
    assert load_store(tmp_path / ".repomind", "fake/model") is None


def test_search_ranks_by_cosine_similarity() -> None:
    hits = _store().search([1.0, 0.0], limit=2, min_score=-1.0)

    assert [hit.chunk.chunk_id for hit in hits] == ["a", "b"]
    assert hits[0].score > hits[1].score


def test_search_applies_min_score_and_limit() -> None:
    store = _store()

    assert [hit.chunk.chunk_id for hit in store.search([1.0, 0.0], limit=5, min_score=0.0)] == ["a"]
    assert len(store.search([1.0, 0.0], limit=1, min_score=-1.0)) == 1
    assert [hit.chunk.chunk_id for hit in store.search([1.0, 0.0], limit=5, min_score=0.9)] == ["a"]
    assert store.search([1.0, 0.0], limit=5, min_score=1.0) == []
    assert store.search([0.0, 0.0], limit=5, min_score=0.0) == []
