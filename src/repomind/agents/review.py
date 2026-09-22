"""The review agent: prioritise the findings that need attention.

The context contains only new findings when a baseline is active, so the
output is a review of what changed rather than of the whole repository.
Model items that cite paths outside the context are dropped before rendering.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from repomind.agents.client import LLMClient
from repomind.agents.context import ContextPack, FindingFacts, build_review_pack
from repomind.agents.parsing import parse_json_object
from repomind.agents.prompts import SYSTEM_PROMPT, review_prompt
from repomind.core.engine import AnalysisResult


@dataclass(frozen=True, slots=True)
class ReviewItem:
    """One prioritised review note."""

    severity: str
    path: str
    line: int | None
    rationale: str
    action: str


@dataclass(frozen=True, slots=True)
class ReviewNotes:
    """The prioritised review output for a scope."""

    summary: str
    items: tuple[ReviewItem, ...]
    model: str | None = None
    notes: tuple[str, ...] = ()
    facts: tuple[FindingFacts, ...] = ()


def review_findings(
    result: AnalysisResult,
    *,
    client: LLMClient | None,
    model: str | None = None,
    limit: int = 20,
    scope_label: str | None = None,
) -> ReviewNotes:
    """Summarise and prioritise the findings that need attention."""
    pack = build_review_pack(result, limit=limit, scope_label=scope_label)
    if not pack.facts:
        return ReviewNotes(summary="No findings need attention.", items=())
    if client is None:
        return _fallback(pack, note="deterministic summary (no model configured)")

    try:
        raw = client.complete(system=SYSTEM_PROMPT, user=review_prompt(pack.to_payload()))
    except Exception as error:  # the model layer must never break the command
        return _fallback(pack, note=f"model call failed: {error}")

    document = parse_json_object(raw)
    if document is None:
        return _fallback(pack, note="model response was not a JSON object")
    summary = document.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        return _fallback(pack, note="model response is missing a summary")

    items, dropped = _validated_items(document.get("items"), pack.paths)
    notes: list[str] = []
    if dropped:
        notes.append(
            f"dropped {len(dropped)} item(s) citing unknown paths: {', '.join(sorted(dropped))}"
        )
    return ReviewNotes(
        summary=summary.strip(),
        items=tuple(items),
        model=model,
        notes=tuple(notes),
        facts=pack.facts,
    )


def _validated_items(value: object, allowed: frozenset[str]) -> tuple[list[ReviewItem], list[str]]:
    """Keep only items whose path exists in the context."""
    items: list[ReviewItem] = []
    dropped: list[str] = []
    if not isinstance(value, list):
        return items, dropped
    for entry in value:
        if not isinstance(entry, dict):
            continue
        path = entry.get("path")
        if not isinstance(path, str) or path not in allowed:
            dropped.append(path if isinstance(path, str) else "<missing>")
            continue
        items.append(_item_from_entry(entry, path))
    return items, dropped


def _item_from_entry(entry: dict[str, Any], path: str) -> ReviewItem:
    """Build a review item from a validated model entry."""
    line = entry.get("line")
    return ReviewItem(
        severity=str(entry.get("severity", "medium")).lower(),
        path=path,
        line=line if isinstance(line, int) and not isinstance(line, bool) else None,
        rationale=str(entry.get("rationale", "")).strip(),
        action=str(entry.get("action", "")).strip(),
    )


def _fallback(pack: ContextPack, *, note: str) -> ReviewNotes:
    """Build the deterministic review used when no model output is usable."""
    items = tuple(
        ReviewItem(
            severity=fact.severity,
            path=fact.path,
            line=fact.line,
            rationale=fact.message,
            action=fact.suggestion or "",
        )
        for fact in pack.facts
    )
    return ReviewNotes(
        summary=f"{len(items)} finding(s) need attention.",
        items=items,
        notes=(note,),
        facts=pack.facts,
    )
