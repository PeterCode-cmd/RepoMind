"""Incremental semantic index: embed only new or changed chunks.

Unchanged chunks are reused by content hash, new or modified chunks are
embedded in batches, and chunks that no longer exist are dropped. A model
change invalidates the whole index because the store validates its model name.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from repomind.errors import RepoMindError
from repomind.semantic.chunking import CodeChunk
from repomind.semantic.embedder import Embedder
from repomind.semantic.store import StoredChunk, VectorStore, load_store, save_store

BATCH_SIZE = 64


@dataclass(frozen=True, slots=True)
class IndexStats:
    """Outcome of one index build."""

    model: str
    chunks: int
    embedded: int
    reused: int
    removed: int
    dimensions: int
    path: Path


def build_index(
    index_dir: Path,
    chunks: Sequence[CodeChunk],
    embedder: Embedder,
    *,
    rebuild: bool = False,
    progress: Callable[[int, int], None] | None = None,
) -> IndexStats:
    """Build or refresh the semantic index for *chunks*."""
    existing = None if rebuild else load_store(index_dir, embedder.model_name)
    entries, vectors, pending = _plan(chunks, existing)

    if pending:
        embedded = _embed_all(embedder, [entries[index].text for index in pending], progress)
        for position, vector in zip(pending, embedded, strict=True):
            vectors[position] = vector

    store = VectorStore(
        model_name=embedder.model_name,
        chunks=entries,
        vectors=_matrix(vectors),
    )
    save_store(index_dir, store)

    reused = len(entries) - len(pending)
    return IndexStats(
        model=embedder.model_name,
        chunks=len(entries),
        embedded=len(pending),
        reused=reused,
        removed=max(0, len(existing.chunks) - reused) if existing else 0,
        dimensions=store.dimensions,
        path=index_dir,
    )


def _plan(
    chunks: Sequence[CodeChunk],
    existing: VectorStore | None,
) -> tuple[list[StoredChunk], list[np.ndarray | None], list[int]]:
    """Decide which chunks to reuse and which to embed."""
    previous_chunks = {entry.chunk_id: entry for entry in existing.chunks} if existing else {}
    previous_vectors = (
        {entry.chunk_id: existing.vectors[index] for index, entry in enumerate(existing.chunks)}
        if existing
        else {}
    )

    entries: list[StoredChunk] = []
    vectors: list[np.ndarray | None] = []
    pending: list[int] = []
    for chunk in chunks:
        stored = StoredChunk.from_chunk(chunk)
        previous = previous_chunks.get(stored.chunk_id)
        if previous is not None and previous.content_hash == stored.content_hash:
            entries.append(previous)
            vectors.append(previous_vectors[stored.chunk_id])
        else:
            entries.append(stored)
            vectors.append(None)
            pending.append(len(entries) - 1)
    return entries, vectors, pending


def _matrix(vectors: Sequence[np.ndarray | None]) -> np.ndarray:
    """Stack the filled vectors into a matrix."""
    filled = [vector for vector in vectors if vector is not None]
    return np.vstack(filled) if filled else np.zeros((0, 0), dtype=np.float32)


def load_index(index_dir: Path, embedder: Embedder) -> VectorStore:
    """Load the index for *embedder*.

    Raises:
        RepoMindError: When no index exists for the embedder's model.
    """
    store = load_store(index_dir, embedder.model_name)
    if store is None:
        raise RepoMindError(
            f"no semantic index for model {embedder.model_name!r} in {index_dir}; "
            "run 'repomind index' first"
        )
    return store


def _embed_all(
    embedder: Embedder,
    texts: Sequence[str],
    progress: Callable[[int, int], None] | None,
) -> list[np.ndarray]:
    """Embed *texts* in batches, returning L2-normalised vectors."""
    vectors: list[np.ndarray] = []
    total = len(texts)
    for start in range(0, total, BATCH_SIZE):
        batch = texts[start : start + BATCH_SIZE]
        vectors.extend(
            _normalise(np.asarray(vector, dtype=np.float32)) for vector in embedder.embed(batch)
        )
        if progress is not None:
            progress(min(start + BATCH_SIZE, total), total)
    return vectors


def _normalise(vector: np.ndarray) -> np.ndarray:
    """Return the L2-normalised vector (or the zero vector unchanged)."""
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm else vector
