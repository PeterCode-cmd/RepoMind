"""Semantic code search and retrieval (roadmap).

This package will host the optional, local-first semantic layer:

* code-aware chunking and embedding generation via ``sentence-transformers``,
* a local vector index (ChromaDB or LanceDB),
* natural-language questions about the analyzed codebase ("RAG").

The layer stays strictly optional: RepoMind must produce its full
deterministic report without any model, API key or network access.
"""

from __future__ import annotations
