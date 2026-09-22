"""The ``repomind search`` command: lexical and semantic code search."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from repomind.cli.common import build_config, run_engine
from repomind.cli.console import console
from repomind.config import AnalysisConfig
from repomind.errors import RepoMindError
from repomind.reporters.search import render_search_json, render_search_terminal
from repomind.semantic.chunking import build_chunks
from repomind.semantic.search import SearchHit, search_chunks


class SearchFormat(StrEnum):
    """Supported search output formats."""

    TERMINAL = "terminal"
    JSON = "json"


class SearchMode(StrEnum):
    """Supported search modes."""

    LEXICAL = "lexical"
    SEMANTIC = "semantic"


def search(
    query: Annotated[
        str,
        typer.Argument(help="Search query: symbols, keywords or phrases."),
    ],
    path: Annotated[
        Path,
        typer.Argument(
            help="Repository root to search.",
            exists=True,
            file_okay=False,
            resolve_path=True,
        ),
    ] = Path(),
    mode: Annotated[
        SearchMode,
        typer.Option("--mode", help="lexical (BM25, always available) or semantic (embeddings)."),
    ] = SearchMode.LEXICAL,
    top: Annotated[
        int,
        typer.Option("--top", min=1, help="Maximum number of results."),
    ] = 10,
    min_score: Annotated[
        float | None,
        typer.Option("--min-score", min=0.0, help="Drop results at or below this score."),
    ] = None,
    output_format: Annotated[
        SearchFormat,
        typer.Option("--format", "-f", help="Output format: terminal or json."),
    ] = SearchFormat.TERMINAL,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Write the JSON report to this file."),
    ] = None,
    exclude: Annotated[
        list[str] | None,
        typer.Option("--exclude", "-x", help="Glob pattern to skip; repeated for lexical mode."),
    ] = None,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", exists=True, dir_okay=False, help="Explicit configuration file."),
    ] = None,
) -> None:
    """Search the codebase lexically (BM25) or semantically (embeddings)."""
    try:
        config = build_config(path, config_path, exclude or [])
        hits = (
            _semantic_hits(path, config, query, top=top, min_score=min_score)
            if mode is SearchMode.SEMANTIC
            else _lexical_hits(path, config, query, top=top, min_score=min_score)
        )
    except RepoMindError as error:
        console.print(f"[bold red]error:[/bold red] {error}")
        raise typer.Exit(code=2) from error

    if output_format is SearchFormat.JSON:
        text = render_search_json(query, hits)
        if output is None:
            console.print(text, markup=False, highlight=False, soft_wrap=True)
            return
        output.write_text(text, encoding="utf-8")
        console.print(f"[green]Report written to[/green] {output}")
        return

    render_search_terminal(query, hits, console)


def _lexical_hits(
    path: Path,
    config: AnalysisConfig,
    query: str,
    *,
    top: int,
    min_score: float | None,
) -> list[SearchHit]:
    """Rank AST-aware chunks with BM25."""
    result = run_engine(path, config, use_history=False)
    chunks = build_chunks(result.modules)
    return search_chunks(chunks, query, limit=top, min_score=min_score or 0.0)


def _semantic_hits(
    path: Path,
    config: AnalysisConfig,
    query: str,
    *,
    top: int,
    min_score: float | None,
) -> list[SearchHit]:
    """Rank indexed chunks by embedding similarity."""
    from repomind.semantic.embedder import create_embedder
    from repomind.semantic.index import load_index

    embedder = create_embedder(config.semantic)
    store = load_index(path / config.semantic.index_dir, embedder)
    vector = embedder.embed([query])[0]
    threshold = config.semantic.min_score if min_score is None else min_score
    return store.search(vector, limit=top, min_score=threshold)
