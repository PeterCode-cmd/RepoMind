"""Local vector store: a numpy matrix plus JSON metadata.

Vectors are L2-normalised before they are saved, so semantic search is a dot
product. The store lives under the configured index directory (``.repomind/``
by default) and is validated against the embedder's model name, which makes a
model change invalidate the index automatically.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from repomind.semantic.chunking import CodeChunk
from repomind.semantic.search import SearchHit

VECTORS_FILENAME = "embeddings.npz"
METADATA_FILENAME = "embeddings.json"
STORE_VERSION = 1


@dataclass(frozen=True, slots=True)
class StoredChunk:
    """A chunk as persisted in the index, with its content hash."""

    chunk_id: str
    kind: str
    path: str
    symbol: str | None
    lineno: int
    end_lineno: int
    text: str
    content_hash: str

    @classmethod
    def from_chunk(cls, chunk: CodeChunk) -> StoredChunk:
        """Build a stored chunk from a fresh chunk, hashing its text."""
        return cls(
            chunk_id=chunk.chunk_id,
            kind=chunk.kind,
            path=chunk.path,
            symbol=chunk.symbol,
            lineno=chunk.lineno,
            end_lineno=chunk.end_lineno,
            text=chunk.text,
            content_hash=content_hash(chunk.text),
        )

    def to_chunk(self) -> CodeChunk:
        """Return the search-facing chunk representation."""
        return CodeChunk(
            chunk_id=self.chunk_id,
            kind=self.kind,
            path=self.path,
            symbol=self.symbol,
            lineno=self.lineno,
            end_lineno=self.end_lineno,
            text=self.text,
        )


def content_hash(text: str) -> str:
    """Return a stable hash of chunk text, used for incremental updates."""
    return hashlib.sha1(text.encode("utf-8"), usedforsecurity=False).hexdigest()


@dataclass(slots=True)
class VectorStore:
    """Embeddings for one model plus their chunk metadata."""

    model_name: str
    chunks: list[StoredChunk]
    vectors: np.ndarray

    @property
    def dimensions(self) -> int:
        """Return the embedding dimensionality."""
        return int(self.vectors.shape[1]) if self.vectors.size else 0

    def search(
        self,
        query_vector: Sequence[float],
        *,
        limit: int,
        min_score: float,
    ) -> list[SearchHit]:
        """Return the closest chunks by cosine similarity."""
        query = np.asarray(query_vector, dtype=np.float32)
        norm = float(np.linalg.norm(query))
        if norm == 0.0 or not len(self.chunks):
            return []

        similarities = self.vectors @ (query / norm)
        hits = [
            SearchHit(chunk=self.chunks[index].to_chunk(), score=round(float(score), 4))
            for index, score in enumerate(similarities.tolist())
            if score > min_score
        ]
        hits.sort(key=lambda hit: (-hit.score, hit.chunk.path, hit.chunk.lineno))
        return hits[:limit]


def load_store(index_dir: Path, model_name: str) -> VectorStore | None:
    """Load the index when it exists and matches *model_name*."""
    entries = _load_metadata(index_dir, model_name)
    if entries is None:
        return None

    try:
        chunks = [_stored_chunk(entry) for entry in entries]
        with np.load(index_dir / VECTORS_FILENAME, allow_pickle=False) as data:
            vectors = data["vectors"].astype(np.float32)
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if len(chunks) != int(vectors.shape[0]):
        return None
    return VectorStore(model_name=model_name, chunks=chunks, vectors=vectors)


def _load_metadata(index_dir: Path, model_name: str) -> list[object] | None:
    """Return the chunk metadata list when the index matches *model_name*."""
    metadata_path = index_dir / METADATA_FILENAME
    vectors_path = index_dir / VECTORS_FILENAME
    if not metadata_path.is_file() or not vectors_path.is_file():
        return None

    try:
        document = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(document, dict) or document.get("version") != STORE_VERSION:
        return None
    if document.get("model") != model_name:
        return None
    entries = document.get("chunks")
    return entries if isinstance(entries, list) else None


def save_store(index_dir: Path, store: VectorStore) -> None:
    """Persist the store, creating the index directory when needed."""
    index_dir.mkdir(parents=True, exist_ok=True)
    document: dict[str, Any] = {
        "version": STORE_VERSION,
        "model": store.model_name,
        "chunks": [asdict(chunk) for chunk in store.chunks],
    }
    metadata_path = index_dir / METADATA_FILENAME
    metadata_path.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    np.savez_compressed(index_dir / VECTORS_FILENAME, vectors=store.vectors.astype(np.float32))


def _stored_chunk(entry: object) -> StoredChunk:
    """Build a :class:`StoredChunk` from one metadata entry."""
    if not isinstance(entry, dict):
        raise TypeError("chunk metadata must be an object")
    return StoredChunk(
        chunk_id=str(entry["chunk_id"]),
        kind=str(entry["kind"]),
        path=str(entry["path"]),
        symbol=entry.get("symbol"),
        lineno=int(entry["lineno"]),
        end_lineno=int(entry["end_lineno"]),
        text=str(entry["text"]),
        content_hash=str(entry["content_hash"]),
    )
