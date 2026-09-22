"""Stable, documented Python API for RepoMind.

This module is the supported public surface of the package: names re-exported
here follow semantic versioning. Everything else (``core``, ``semantic``,
``agents``, ...) is internal implementation detail and may change between
minor releases.

Example:
    >>> from repomind import api
    >>> result = api.analyze(".")                     # doctest: +SKIP
    >>> result.score.value                            # doctest: +SKIP
    100
    >>> hits = api.search_code(".", "retry backoff")  # doctest: +SKIP
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from repomind.agents.client import LiteLLMClient, LLMClient
from repomind.agents.explain import Explanation, explain_finding
from repomind.agents.review import ReviewNotes, review_findings
from repomind.config import AnalysisConfig, Thresholds, load_config
from repomind.core.baseline import Baseline
from repomind.core.engine import (
    AnalysisOptions,
    AnalysisResult,
    AnalysisScope,
    ProgressCallback,
    analyze_repository,
)
from repomind.models.enums import Category, Severity
from repomind.models.findings import Finding
from repomind.semantic.chunking import CodeChunk, build_chunks
from repomind.semantic.search import SearchHit, search_chunks

if TYPE_CHECKING:
    from repomind.semantic.embedder import Embedder
    from repomind.semantic.index import IndexStats

__all__ = [
    "AnalysisConfig",
    "AnalysisOptions",
    "AnalysisResult",
    "AnalysisScope",
    "Baseline",
    "Category",
    "CodeChunk",
    "Explanation",
    "Finding",
    "LLMClient",
    "LiteLLMClient",
    "ReviewNotes",
    "SearchHit",
    "Severity",
    "Thresholds",
    "analyze",
    "build_search_index",
    "explain_finding",
    "load_config",
    "review_findings",
    "search_code",
]


def analyze(
    path: str | Path,
    *,
    config: AnalysisConfig | None = None,
    use_history: bool | None = None,
    options: AnalysisOptions | None = None,
    progress: ProgressCallback | None = None,
) -> AnalysisResult:
    """Analyze a repository and return the complete result.

    Args:
        path: Repository root.
        config: Explicit configuration; discovered from the repository when
            omitted.
        use_history: Force Git history analysis on/off; ``None`` follows the
            configuration.
        options: Accepted findings (baseline) and an optional path scope.
        progress: Optional callback receiving stage updates.

    Returns:
        Findings, health score, dependency and call graphs, history and churn.
    """
    return analyze_repository(
        Path(path),
        config=config,
        use_history=use_history,
        options=options,
        progress=progress,
    )


def search_code(
    path: str | Path,
    query: str,
    *,
    limit: int = 10,
    min_score: float = 0.0,
    config: AnalysisConfig | None = None,
) -> list[SearchHit]:
    """Search a repository lexically (BM25 over AST-aware chunks).

    This is the dependency-free search mode: no embeddings, no extra installs,
    no network. For semantic search, build an index with
    :func:`build_search_index` and query it through the CLI
    (``repomind search --mode semantic``).
    """
    result = analyze(path, config=config, use_history=False)
    return search_chunks(
        build_chunks(result.modules),
        query,
        limit=limit,
        min_score=min_score,
    )


def build_search_index(
    path: str | Path,
    *,
    rebuild: bool = False,
    config: AnalysisConfig | None = None,
    embedder: Embedder | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> IndexStats:
    """Build or refresh the local semantic index.

    Requires the ``semantic`` extra (``pip install "repomind-analyzer[semantic]"``)
    unless a custom *embedder* is supplied. Unchanged chunks are reused, so
    repeated calls are cheap.

    Args:
        path: Repository root.
        rebuild: Ignore the existing index and embed every chunk again.
        config: Explicit configuration; discovered when omitted.
        embedder: Custom embedding backend; defaults to the configured one.
        progress: Optional callback receiving ``(done, total)`` batch updates.

    Returns:
        Statistics about embedded, reused and removed chunks.
    """
    from repomind.semantic.embedder import create_embedder
    from repomind.semantic.index import build_index

    root = Path(path).resolve()
    resolved = config or load_config(root)
    result = analyze(root, config=resolved, use_history=False)
    backend = embedder or create_embedder(resolved.semantic)
    return build_index(
        root / resolved.semantic.index_dir,
        build_chunks(result.modules),
        backend,
        rebuild=rebuild,
        progress=progress,
    )
