"""LLM clients for the agent layer.

The default backend is Ollama (local, free, private); any cloud provider works
through litellm with the user's own API key taken from the environment
(``OPENAI_API_KEY``, ``ANTHROPIC_API_KEY``, ``GEMINI_API_KEY``, ...). Keys are
never read from RepoMind configuration or written to reports.
"""

from __future__ import annotations

from typing import Protocol

from repomind.errors import RepoMindError

INSTALL_HINT = 'the llm extra is not installed: pip install "repomind-analyzer[llm]"'
_DEFAULT_RETRIES = 2


class MissingLLMError(RepoMindError):
    """Raised when the optional ``llm`` extra is not installed."""


class LLMClient(Protocol):
    """Minimal contract every LLM backend must satisfy."""

    @property
    def model(self) -> str:
        """Return the model identifier in litellm format."""
        ...

    def complete(self, *, system: str, user: str) -> str:
        """Return the raw model response for the given prompts."""
        ...


class LiteLLMClient:
    """LLM client backed by litellm (Ollama by default, cloud via env keys)."""

    def __init__(self, model: str, timeout: int = 60) -> None:
        """Store the model identifier and request timeout."""
        self._model = model
        self.timeout = timeout

    @property
    def model(self) -> str:
        """Return the model identifier in litellm format."""
        return self._model

    def complete(self, *, system: str, user: str) -> str:
        """Return the raw model response, importing litellm lazily.

        Transient provider failures (rate limits, 5xx) are retried by litellm
        with backoff, which keeps cloud hiccups from degrading a review.
        litellm's feedback banner is disabled so failed attempts that later
        succeed do not leak noise into the output.

        Raises:
            MissingLLMError: If the optional ``llm`` extra is not installed.
            RepoMindError: If the model returns an empty response.
        """
        try:
            import litellm
        except ImportError as exc:
            raise MissingLLMError(INSTALL_HINT) from exc

        litellm.suppress_debug_info = True
        response = litellm.completion(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            timeout=self.timeout,
            num_retries=_DEFAULT_RETRIES,
        )
        content = response.choices[0].message.content
        if not isinstance(content, str) or not content.strip():
            raise RepoMindError("the model returned an empty response")
        return content
