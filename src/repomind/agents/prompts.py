"""Prompt templates for the agent layer.

Every prompt embeds a JSON context and asks for a single JSON object. The
system prompt forbids inventing facts, and the agents validate the answers
before they reach a report.
"""

from __future__ import annotations

import json
from typing import Any

SYSTEM_PROMPT = (
    "You are RepoMind's code-quality assistant. You explain and prioritise findings "
    "produced by deterministic static analysis. Use only the facts in the JSON "
    "context: never invent files, symbols, metrics, history or line numbers. Refer "
    "only to paths that appear in the context. Reply with a single JSON object and "
    "nothing else."
)

_EXPLAIN_INSTRUCTIONS = """Explain the finding in the context.
Return JSON with exactly these keys:
- "summary": string, one short paragraph.
- "why": array of strings, the concrete reasons supported by the measured values.
- "risks": array of strings, what could go wrong if it stays unchanged.
- "actions": array of strings, concrete next steps, most valuable first."""

_REVIEW_INSTRUCTIONS = """Prioritise the findings in the context for a reviewer.
Return JSON with exactly these keys:
- "summary": string, one short paragraph.
- "items": array of objects, most important first, each with:
  - "severity": one of critical, high, medium, low.
  - "path": string, must be one of the paths in the context.
  - "line": integer or null.
  - "rationale": string, why this matters, using the measured values.
  - "action": string, what to do about it.

Rank by risk, not by severity alone: use "callers" and "churn" when present to
prefer findings that are both complex and frequently changed. Findings that
look like generated, vendored or benchmark data (profiling/, generated/,
vendor/, *_pb2.py, huge data modules) should be reported as such and placed
last, because they are usually not worth a reviewer's time. When several
findings concern the same path and symbol, merge them into one item that names
each rule and combines the evidence instead of repeating the symbol."""


def explain_prompt(payload: dict[str, Any]) -> str:
    """Build the user prompt for the explain agent."""
    context = json.dumps(payload, indent=2, ensure_ascii=False)
    return f"{_EXPLAIN_INSTRUCTIONS}\n\nContext:\n{context}"


def review_prompt(payload: dict[str, Any]) -> str:
    """Build the user prompt for the review agent."""
    context = json.dumps(payload, indent=2, ensure_ascii=False)
    return f"{_REVIEW_INSTRUCTIONS}\n\nContext:\n{context}"
