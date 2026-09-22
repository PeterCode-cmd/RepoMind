"""Tests for incremental semantic index building."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from conftest import FakeEmbedder
from repomind.core.discovery import find_python_files
from repomind.core.pyparser import parse_module
from repomind.errors import RepoMindError
from repomind.semantic.chunking import CodeChunk, build_chunks
from repomind.semantic.index import build_index, load_index
from repomind.semantic.store import load_store


def _chunks(sample_project: Path) -> list[CodeChunk]:
    modules = [parse_module(path, sample_project) for path in find_python_files(sample_project)]
    return build_chunks(modules)


def test_build_index_embeds_all_chunks(
    sample_project: Path, tmp_path: Path, fake_embedder: FakeEmbedder
) -> None:
    chunks = _chunks(sample_project)

    stats = build_index(tmp_path / ".repomind", chunks, fake_embedder)

    assert stats.chunks == len(chunks)
    assert stats.embedded == len(chunks)
    assert stats.reused == 0
    assert stats.dimensions == 16
    assert load_store(tmp_path / ".repomind", fake_embedder.model_name) is not None


def test_second_build_reuses_unchanged_chunks(
    sample_project: Path, tmp_path: Path, fake_embedder: FakeEmbedder
) -> None:
    chunks = _chunks(sample_project)
    build_index(tmp_path / ".repomind", chunks, fake_embedder)

    stats = build_index(tmp_path / ".repomind", chunks, fake_embedder)

    assert stats.embedded == 0
    assert stats.reused == stats.chunks
    assert stats.removed == 0


def test_changed_chunk_is_reembedded(
    sample_project: Path, tmp_path: Path, fake_embedder: FakeEmbedder
) -> None:
    chunks = _chunks(sample_project)
    build_index(tmp_path / ".repomind", chunks, fake_embedder)
    mutated = [
        replace(chunk, text=chunk.text + "\n# note")
        if chunk.symbol == "samplepkg.a.alpha"
        else chunk
        for chunk in chunks
    ]

    stats = build_index(tmp_path / ".repomind", mutated, fake_embedder)

    assert stats.embedded == 1
    assert stats.reused == len(chunks) - 1


def test_removed_chunks_are_dropped(
    sample_project: Path, tmp_path: Path, fake_embedder: FakeEmbedder
) -> None:
    chunks = _chunks(sample_project)
    build_index(tmp_path / ".repomind", chunks, fake_embedder)

    stats = build_index(tmp_path / ".repomind", chunks[:-1], fake_embedder)

    assert stats.removed == 1
    assert stats.chunks == len(chunks) - 1


def test_rebuild_embeds_everything(
    sample_project: Path, tmp_path: Path, fake_embedder: FakeEmbedder
) -> None:
    chunks = _chunks(sample_project)
    build_index(tmp_path / ".repomind", chunks, fake_embedder)

    stats = build_index(tmp_path / ".repomind", chunks, fake_embedder, rebuild=True)

    assert stats.embedded == len(chunks)
    assert stats.reused == 0


def test_model_change_invalidates_index(
    sample_project: Path, tmp_path: Path, fake_embedder: FakeEmbedder
) -> None:
    chunks = _chunks(sample_project)
    build_index(tmp_path / ".repomind", chunks, fake_embedder)

    other = FakeEmbedder(model="fake/other")
    stats = build_index(tmp_path / ".repomind", chunks, other)

    assert stats.embedded == len(chunks)
    assert stats.reused == 0


def test_load_index_without_store_raises(tmp_path: Path, fake_embedder: FakeEmbedder) -> None:
    with pytest.raises(RepoMindError, match="repomind index"):
        load_index(tmp_path / ".repomind", fake_embedder)
