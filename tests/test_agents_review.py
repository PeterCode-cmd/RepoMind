"""Tests for the review agent."""

from __future__ import annotations

from pathlib import Path

from repomind.agents.review import review_findings
from repomind.core.engine import AnalysisResult, analyze_repository


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


def _result(sample_project: Path) -> AnalysisResult:
    return analyze_repository(sample_project, use_history=False)


def test_fallback_lists_findings(sample_project: Path) -> None:
    notes = review_findings(_result(sample_project), client=None, limit=3)

    assert notes.model is None
    assert len(notes.items) == 3
    assert notes.summary.endswith("need attention.")
    assert notes.notes


def test_model_items_are_validated(sample_project: Path) -> None:
    response = (
        '{"summary": "Two things.", "items": ['
        '{"severity": "high", "path": "samplepkg/god.py", "line": 12, '
        '"rationale": "big class", "action": "split"},'
        '{"severity": "low", "path": "ghost/file.py", "line": 1, '
        '"rationale": "made up", "action": "n/a"}'
        "]}"
    )
    client = FakeClient(response)

    notes = review_findings(
        _result(sample_project),
        client=client,
        model="fake/model",
        limit=10,
    )

    assert notes.summary == "Two things."
    assert [item.path for item in notes.items] == ["samplepkg/god.py"]
    assert notes.items[0].line == 12
    assert any("unknown paths" in note for note in notes.notes)
    system, user = client.calls[0]
    assert "never invent" in system
    assert "callers" in user
    assert "generated" in user
    assert "merge them into one item" in user
    assert "samplepkg/god.py" in user


def test_empty_findings_short_circuit(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text('"""Module."""\n\n\nvalue = 1\n', encoding="utf-8")
    result = analyze_repository(tmp_path, use_history=False)

    notes = review_findings(result, client=FakeClient("{}"), limit=10)

    assert notes.items == ()
    assert notes.summary == "No findings need attention."
