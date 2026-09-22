"""The explain agent: turn one finding into an explanation with next steps.

Without a client (``--no-llm`` or no model configured) the agent returns a
deterministic explanation built from the finding itself. When the model fails
or answers something unusable, the deterministic explanation is returned with
a note instead of an error.
"""

from __future__ import annotations

from dataclasses import dataclass

from repomind.agents.client import LLMClient
from repomind.agents.context import FindingFacts, build_explain_pack
from repomind.agents.parsing import parse_json_object, string_tuple
from repomind.agents.prompts import SYSTEM_PROMPT, explain_prompt
from repomind.core.engine import AnalysisResult


@dataclass(frozen=True, slots=True)
class Explanation:
    """An explanation of one finding, from the model or from the facts."""

    facts: FindingFacts
    summary: str
    why: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    actions: tuple[str, ...] = ()
    model: str | None = None
    notes: tuple[str, ...] = ()


def explain_finding(
    result: AnalysisResult,
    reference: str,
    *,
    client: LLMClient | None,
    model: str | None = None,
) -> Explanation:
    """Explain the finding addressed by *reference*.

    Raises:
        RepoMindError: When *reference* matches no finding in *result*.
    """
    pack = build_explain_pack(result, reference)
    facts = pack.facts[0]
    if client is None:
        return _fallback(facts, note="deterministic explanation (no model configured)")

    try:
        raw = client.complete(system=SYSTEM_PROMPT, user=explain_prompt(pack.to_payload()))
    except Exception as error:  # the model layer must never break the command
        return _fallback(facts, note=f"model call failed: {error}")

    document = parse_json_object(raw)
    if document is None:
        return _fallback(facts, note="model response was not a JSON object")
    summary = document.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        return _fallback(facts, note="model response is missing a summary")

    return Explanation(
        facts=facts,
        summary=summary.strip(),
        why=string_tuple(document.get("why")),
        risks=string_tuple(document.get("risks")),
        actions=string_tuple(document.get("actions")),
        model=model,
    )


def _fallback(facts: FindingFacts, *, note: str) -> Explanation:
    """Build the deterministic explanation used when no model output is usable."""
    why = [facts.message]
    measured = ", ".join(f"{key}={value}" for key, value in sorted(facts.details.items()))
    if measured:
        why.append(f"measured values: {measured}")
    actions = (facts.suggestion,) if facts.suggestion else ()
    return Explanation(
        facts=facts,
        summary=facts.message,
        why=tuple(why),
        actions=actions,
        notes=(note,),
    )
