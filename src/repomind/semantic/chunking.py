"""AST-aware code chunks for search.

Chunks come from the parser's metrics (modules, classes, functions, methods),
so retrieval works on real code boundaries instead of fixed line windows. The
module reads each source file once and slices it by the recorded line ranges.
"""

from __future__ import annotations

import hashlib
import tokenize
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from repomind.models.metrics import ParsedModule

_MODULE_PREVIEW_LINES = 20


@dataclass(frozen=True, slots=True)
class CodeChunk:
    """A searchable unit of code."""

    chunk_id: str
    kind: str
    path: str
    symbol: str | None
    lineno: int
    end_lineno: int
    text: str

    @property
    def location(self) -> str:
        """Return a human readable ``file:line`` location."""
        return f"{self.path}:{self.lineno}"

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation of the chunk."""
        return {
            "chunk_id": self.chunk_id,
            "kind": self.kind,
            "path": self.path,
            "symbol": self.symbol,
            "lineno": self.lineno,
            "end_lineno": self.end_lineno,
            "location": self.location,
        }


def build_chunks(modules: Sequence[ParsedModule]) -> list[CodeChunk]:
    """Build searchable chunks for every parsed module.

    Modules with syntax errors are skipped: their structure is unknown, so
    chunk boundaries would be guesses.
    """
    chunks: list[CodeChunk] = []
    for module in modules:
        chunks.extend(_module_chunks(module))
    return [chunk for chunk in chunks if chunk.text.strip()]


def _module_chunks(module: ParsedModule) -> list[CodeChunk]:
    """Build the chunks of one module, reading its source once."""
    if module.syntax_error is not None:
        return []
    lines = _read_lines(module.path)
    if lines is None:
        return []

    chunks = [_module_chunk(module, lines)]
    chunks.extend(
        _symbol_chunk(
            module,
            function.qualname,
            "function",
            (function.lineno, function.end_lineno),
            lines,
        )
        for function in module.functions
    )
    for cls in module.classes:
        chunks.append(
            _symbol_chunk(
                module,
                f"{module.module_name}.{cls.name}",
                "class",
                (cls.lineno, cls.end_lineno),
                lines,
            )
        )
        chunks.extend(
            _symbol_chunk(
                module,
                method.qualname,
                "method",
                (method.lineno, method.end_lineno),
                lines,
            )
            for method in cls.methods
        )
    return chunks


def _module_chunk(module: ParsedModule, lines: list[str]) -> CodeChunk:
    """Build the preview chunk for a whole module."""
    end = min(len(lines), _MODULE_PREVIEW_LINES)
    return CodeChunk(
        chunk_id=_chunk_id(module.rel_path, "module", module.module_name),
        kind="module",
        path=module.rel_path,
        symbol=module.module_name,
        lineno=1,
        end_lineno=end,
        text="\n".join(lines[:end]),
    )


def _symbol_chunk(
    module: ParsedModule,
    symbol: str,
    kind: str,
    span: tuple[int, int],
    lines: list[str],
) -> CodeChunk:
    """Build a chunk for a function, method or class definition."""
    lineno, end_lineno = span
    return CodeChunk(
        chunk_id=_chunk_id(module.rel_path, kind, symbol),
        kind=kind,
        path=module.rel_path,
        symbol=symbol,
        lineno=lineno,
        end_lineno=end_lineno,
        text="\n".join(lines[lineno - 1 : end_lineno]),
    )


def _chunk_id(rel_path: str, kind: str, symbol: str) -> str:
    """Return a stable identifier for a chunk."""
    key = "\x00".join((rel_path, kind, symbol))
    digest = hashlib.sha1(key.encode("utf-8"), usedforsecurity=False)
    return digest.hexdigest()


def _read_lines(path: Path) -> list[str] | None:
    """Read a source file honouring its encoding, or ``None`` on failure."""
    try:
        with tokenize.open(path) as handle:
            return handle.read().splitlines()
    except (OSError, SyntaxError, UnicodeDecodeError):
        return None
