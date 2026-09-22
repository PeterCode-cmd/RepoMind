"""LLM agent layer (roadmap).

Specialized agents (Architect, Quality, Security, Maintainability,
Documentation) will consume the deterministic artifacts produced by
:mod:`repomind.core` - metrics, graphs, findings and history - instead of
raw source text. Agents explain, rank and propose fixes; they never replace
the static analysis itself.

LLM support is optional and local-first: Ollama is the default backend and
cloud providers are used only with the user's own API key (via ``litellm``).
"""

from __future__ import annotations
