"""Tests for BM25 lexical search."""

from __future__ import annotations

from pathlib import Path

from repomind.core.discovery import find_python_files
from repomind.core.pyparser import parse_module
from repomind.semantic.chunking import CodeChunk, build_chunks
from repomind.semantic.search import search_chunks, tokenize


def _chunks(sample_project: Path) -> list[CodeChunk]:
    modules = [parse_module(path, sample_project) for path in find_python_files(sample_project)]
    return build_chunks(modules)


def test_matching_symbol_ranks_first(sample_project: Path) -> None:
    hits = search_chunks(_chunks(sample_project), "tangled branches", limit=5)

    assert hits
    assert hits[0].chunk.symbol == "samplepkg.complex.tangled_branches"
    assert hits[0].score > 0


def test_search_is_deterministic(sample_project: Path) -> None:
    chunks = _chunks(sample_project)

    first = search_chunks(chunks, "god object", limit=5)
    second = search_chunks(chunks, "god object", limit=5)

    assert [hit.chunk.chunk_id for hit in first] == [hit.chunk.chunk_id for hit in second]


def test_tokenizer_splits_snake_and_camel_case() -> None:
    assert tokenize("fetchUserData") == ["fetch", "user", "data"]
    assert tokenize("tangled_branches") == ["tangled", "branches"]
    assert tokenize("the a of") == []


def test_empty_query_returns_no_hits(sample_project: Path) -> None:
    assert search_chunks(_chunks(sample_project), "   ") == []


def test_limit_and_min_score(sample_project: Path) -> None:
    chunks = _chunks(sample_project)

    assert len(search_chunks(chunks, "def", limit=2)) <= 2
    assert search_chunks(chunks, "tangled", min_score=1000.0) == []
