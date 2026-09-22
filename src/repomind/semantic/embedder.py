"""Embedding backends: local ONNX (fastembed) or any API through litellm.

Both backends implement the same :class:`Embedder` protocol, so the index and
search layers never care where vectors come from. API keys are read from the
environment by litellm and are never stored in configuration.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterable, Sequence
from typing import Protocol

from repomind.config import SemanticConfig
from repomind.errors import RepoMindError

SEMANTIC_INSTALL_HINT = (
    'the semantic extra is not installed: pip install "repomind-analyzer[semantic]"'
)
LLM_INSTALL_HINT = 'the llm extra is not installed: pip install "repomind-analyzer[llm]"'
_API_RETRIES = 2


class MissingSemanticError(RepoMindError):
    """Raised when the optional semantic or llm extra is not installed."""


class Embedder(Protocol):
    """Contract every embedding backend must satisfy."""

    @property
    def model_name(self) -> str:
        """Return a stable identifier used to validate indexes."""
        ...

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""
        ...


class _TextEmbedding(Protocol):
    """Minimal fastembed surface used by :class:`FastEmbedEmbedder`."""

    def embed(self, texts: Sequence[str]) -> Iterable[Iterable[float]]:
        """Return one embedding vector per input text."""
        ...


class FastEmbedEmbedder:
    """Local embeddings through fastembed (ONNX runtime, no torch)."""

    def __init__(self, model: str) -> None:
        """Store the fastembed model name; the model loads on first use."""
        self._model = model
        self._engine: _TextEmbedding | None = None

    @property
    def model_name(self) -> str:
        """Return a stable identifier used to validate indexes."""
        return f"fastembed/{self._model}"

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return embeddings for *texts* using the local ONNX model."""
        engine = self._load()
        return [[float(value) for value in vector] for vector in engine.embed(list(texts))]

    def _load(self) -> _TextEmbedding:
        if self._engine is None:
            # huggingface_hub warns about symlink-less caches and anonymous
            # downloads on every fresh process; neither is actionable here.
            os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
            logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
            try:
                from fastembed import TextEmbedding
            except ImportError as exc:
                raise MissingSemanticError(SEMANTIC_INSTALL_HINT) from exc
            self._engine = TextEmbedding(model_name=self._model)
        return self._engine


class LiteLLMEmbedder:
    """Embeddings through litellm (cloud or any compatible endpoint)."""

    def __init__(self, model: str) -> None:
        """Store the litellm model identifier, e.g. ``gemini/text-embedding-004``."""
        self._model = model

    @property
    def model_name(self) -> str:
        """Return a stable identifier used to validate indexes."""
        return self._model

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return embeddings for *texts* through the configured API."""
        try:
            import litellm
        except ImportError as exc:
            raise MissingSemanticError(LLM_INSTALL_HINT) from exc

        litellm.suppress_debug_info = True
        response = litellm.embedding(
            model=self._model,
            input=list(texts),
            num_retries=_API_RETRIES,
        )
        return [[float(value) for value in item["embedding"]] for item in response.data]


def create_embedder(config: SemanticConfig) -> Embedder:
    """Build the embedder selected by the ``[semantic]`` configuration."""
    if config.provider == "api":
        return LiteLLMEmbedder(config.model)
    return FastEmbedEmbedder(config.model)
