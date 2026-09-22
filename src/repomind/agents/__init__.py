"""LLM agent layer (optional).

Agents consume the deterministic artifacts produced by :mod:`repomind.core` —
metrics, graphs, findings, call-graph caller counts and churn — instead of raw
source text. They explain, prioritise and propose next steps; the static
analysis remains the source of truth.

LLM support is optional and provider-agnostic: Ollama is the default backend
and any cloud provider works through litellm with the user's own API key taken
from the environment. Without the ``llm`` extra every command degrades to a
deterministic summary built from the same facts.
"""

from __future__ import annotations

from repomind.agents.client import LiteLLMClient, LLMClient, MissingLLMError
from repomind.agents.context import (
    ContextPack,
    FindingFacts,
    build_explain_pack,
    build_review_pack,
)
from repomind.agents.explain import Explanation, explain_finding
from repomind.agents.review import ReviewItem, ReviewNotes, review_findings

__all__ = [
    "ContextPack",
    "Explanation",
    "FindingFacts",
    "LLMClient",
    "LiteLLMClient",
    "MissingLLMError",
    "ReviewItem",
    "ReviewNotes",
    "build_explain_pack",
    "build_review_pack",
    "explain_finding",
    "review_findings",
]
