"""Semantic code search and retrieval.

The lexical layer (AST-aware chunks plus BM25 ranking) is dependency-free and
always available. The semantic layer (local or API embeddings) is an optional
upgrade built on the same chunks.
"""

from __future__ import annotations

from repomind.semantic.chunking import CodeChunk, build_chunks
from repomind.semantic.search import SearchHit, search_chunks, tokenize

__all__ = [
    "CodeChunk",
    "SearchHit",
    "build_chunks",
    "search_chunks",
    "tokenize",
]
