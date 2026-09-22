"""Tests for the explain agent."""

from __future__ import annotations

from pathlib import Path

from repomind.agents.explain import Explanation, explain_finding
from repomind.core.engine import AnalysisResult, analyze_repository

_REFERENCE = "design/god-object@samplepkg/god.py"


class FakeClient:
    """Deterministic LLM client used by the tests."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[tuple[str, str]] = []

    @property
    def model(self) -> str:
        return "fake/model"

    def complete(self, *, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self.response


class BrokenClient:
    """LLM client that always fails, like an unreachable server."""

    @property
    def model(self) -> str:
        return "fake/broken"

    def complete(self, *, system: str, user: str) -> str:
        raise RuntimeError("connection refused")


def _result(sample_project: Path) -> AnalysisResult:
    return analyze_repository(sample_project, use_history=False)


def test_fallback_without_client(sample_project: Path) -> None:
    explanation = explain_finding(_result(sample_project), _REFERENCE, client=None)

    assert isinstance(explanation, Explanation)
    assert explanation.model is None
    assert explanation.summary == explanation.facts.message
    assert explanation.actions == (explanation.facts.suggestion,)
    assert explanation.notes


def test_model_response_is_parsed(sample_project: Path) -> None:
    client = FakeClient(
        '{"summary": "God object.", "why": ["18 methods"], "risks": ["hard to test"], '
        '"actions": ["split it"]}'
    )

    explanation = explain_finding(
        _result(sample_project), _REFERENCE, client=client, model="fake/model"
    )

    assert explanation.summary == "God object."
    assert explanation.why == ("18 methods",)
    assert explanation.risks == ("hard to test",)
    assert explanation.actions == ("split it",)
    assert explanation.model == "fake/model"
    system, user = client.calls[0]
    assert "never invent" in system
    assert "design/god-object" in user
    assert "samplepkg/god.py" in user


def test_code_fences_are_tolerated(sample_project: Path) -> None:
    client = FakeClient('```json\n{"summary": "Ok.", "why": [], "risks": [], "actions": []}\n```')

    explanation = explain_finding(_result(sample_project), _REFERENCE, client=client)

    assert explanation.summary == "Ok."


def test_invalid_json_falls_back(sample_project: Path) -> None:
    client = FakeClient("I think this is bad code.")

    explanation = explain_finding(_result(sample_project), _REFERENCE, client=client)

    assert explanation.model is None
    assert any("not a JSON object" in note for note in explanation.notes)


def test_model_failure_falls_back(sample_project: Path) -> None:
    explanation = explain_finding(_result(sample_project), _REFERENCE, client=BrokenClient())

    assert explanation.model is None
    assert any("model call failed" in note for note in explanation.notes)
