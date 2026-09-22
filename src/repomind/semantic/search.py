"""Lexical search over code chunks with BM25 ranking.

Pure Python and dependency-free: this is the always-available search mode.
Semantic search (embeddings) is an optional upgrade layered on top of the
same chunks.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from repomind.semantic.chunking import CodeChunk

_K1 = 1.5
_B = 0.75
_SYMBOL_BOOST = 2.0
_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_CAMEL_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "was",
        "with",
    }
)


@dataclass(frozen=True, slots=True)
class SearchHit:
    """One ranked search result."""

    chunk: CodeChunk
    score: float


@dataclass(frozen=True, slots=True)
class _Corpus:
    """Corpus statistics shared by every document in one search."""

    average_length: float
    document_frequency: Counter[str]
    total: int


def tokenize(text: str) -> list[str]:
    """Split *text* into lowercase tokens, aware of snake_case and camelCase."""
    tokens: list[str] = []
    for raw in _TOKEN_RE.findall(text):
        for part in _CAMEL_RE.sub(" ", raw).replace("_", " ").split():
            lowered = part.lower()
            if len(lowered) > 1 and lowered not in _STOPWORDS:
                tokens.append(lowered)
    return tokens


def search_chunks(
    chunks: Sequence[CodeChunk],
    query: str,
    *,
    limit: int = 10,
    min_score: float = 0.0,
) -> list[SearchHit]:
    """Rank *chunks* against *query* with BM25.

    Args:
        chunks: Code chunks to search.
        query: Free-text query; symbols, snake_case and camelCase all work.
        limit: Maximum number of hits to return.
        min_score: Hits with a score at or below this value are dropped.

    Returns:
        Hits ordered by descending score, then path and line for determinism.
    """
    query_tokens = tokenize(query)
    if not query_tokens or not chunks:
        return []

    documents = [tokenize(chunk.text) for chunk in chunks]
    lengths = [len(document) for document in documents]
    average_length = sum(lengths) / len(lengths) if lengths else 0.0

    document_frequency: Counter[str] = Counter()
    for document in documents:
        document_frequency.update(set(document))

    corpus = _Corpus(
        average_length=average_length,
        document_frequency=document_frequency,
        total=len(documents),
    )
    hits: list[SearchHit] = []
    for chunk, document, length in zip(chunks, documents, lengths, strict=True):
        score = _bm25_score(query_tokens, document, length, corpus)
        score *= _symbol_boost(chunk, query_tokens)
        if score > min_score:
            hits.append(SearchHit(chunk=chunk, score=round(score, 4)))

    hits.sort(key=lambda hit: (-hit.score, hit.chunk.path, hit.chunk.lineno))
    return hits[:limit]


def _symbol_boost(chunk: CodeChunk, query_tokens: Sequence[str]) -> float:
    """Boost chunks whose symbol covers every query token.

    Searching for ``tangled branches`` should surface the function
    ``tangled_branches`` before the module that merely contains it.
    """
    symbol_tokens = set(tokenize(chunk.symbol or ""))
    if symbol_tokens and all(token in symbol_tokens for token in query_tokens):
        return _SYMBOL_BOOST
    return 1.0


def _bm25_score(
    query_tokens: Sequence[str],
    document: Sequence[str],
    length: int,
    corpus: _Corpus,
) -> float:
    """Return the BM25 score of one document for the query tokens."""
    frequencies = Counter(document)
    score = 0.0
    for token in query_tokens:
        term_frequency = frequencies.get(token, 0)
        if term_frequency == 0:
            continue
        frequency = corpus.document_frequency[token]
        inverse_frequency = math.log(1.0 + (corpus.total - frequency + 0.5) / (frequency + 0.5))
        normalisation = (
            _K1 * (1.0 - _B + _B * length / corpus.average_length) if corpus.average_length else _K1
        )
        score += inverse_frequency * term_frequency * (_K1 + 1.0) / (term_frequency + normalisation)
    return score
