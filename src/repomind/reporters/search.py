"""Renderers for code search results."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text

from repomind.semantic.search import SearchHit

_PREVIEW_LIMIT = 60


def render_search_terminal(query: str, hits: Sequence[SearchHit], console: Console) -> None:
    """Print the ranked search hits."""
    if not hits:
        console.print(f"[yellow]No matches for[/yellow] {query!r}.")
        return

    table = Table(
        title=f"Search results ({len(hits)})",
        box=box.SIMPLE_HEAD,
        title_justify="left",
    )
    table.add_column("Score", justify="right", no_wrap=True)
    table.add_column("Kind", no_wrap=True)
    table.add_column("Location", style="cyan", no_wrap=True)
    table.add_column("Symbol", overflow="fold", min_width=18)
    table.add_column("Preview", overflow="fold", min_width=18)

    for hit in hits:
        table.add_row(
            f"{hit.score:.2f}",
            hit.chunk.kind,
            hit.chunk.location,
            hit.chunk.symbol or "",
            _preview(hit),
        )
    console.print(table)


def search_to_dict(query: str, hits: Sequence[SearchHit]) -> dict[str, Any]:
    """Convert search hits into a JSON-serialisable dictionary."""
    return {
        "query": query,
        "hits": [{**hit.chunk.to_payload(), "score": hit.score} for hit in hits],
    }


def render_search_json(query: str, hits: Sequence[SearchHit]) -> str:
    """Render search hits as a JSON document."""
    return json.dumps(search_to_dict(query, hits), indent=2, ensure_ascii=False)


def _preview(hit: SearchHit) -> Text:
    """Return the first non-empty line of a chunk, trimmed."""
    for line in hit.chunk.text.splitlines():
        stripped = line.strip()
        if stripped:
            if len(stripped) > _PREVIEW_LIMIT:
                stripped = stripped[: _PREVIEW_LIMIT - 3] + "..."
            return Text(stripped, style="dim")
    return Text("", style="dim")
