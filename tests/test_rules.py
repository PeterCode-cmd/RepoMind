"""Tests for the built-in rules as exercised through the engine."""

from __future__ import annotations

from pathlib import Path

from repomind.core.engine import AnalysisResult, analyze_repository
from repomind.models.enums import Category, Severity


def _analyze(sample_project: Path) -> AnalysisResult:
    return analyze_repository(sample_project, use_history=False)


def test_engine_reports_expected_rules(sample_project: Path) -> None:
    rule_ids = {finding.rule_id for finding in _analyze(sample_project).findings}

    assert {
        "design/god-object",
        "complexity/high-cyclomatic-complexity",
        "complexity/high-cognitive-complexity",
        "complexity/deep-nesting",
        "maintainability/long-function",
        "maintainability/too-many-parameters",
        "dead-code/unused-import",
        "dead-code/unused-private-function",
        "dependencies/cyclic-import",
        "correctness/syntax-error",
    } <= rule_ids


def test_findings_are_complete(sample_project: Path) -> None:
    for finding in _analyze(sample_project).findings:
        assert finding.path
        assert finding.title
        assert finding.message
        assert isinstance(finding.severity, Severity)
        assert isinstance(finding.category, Category)


def test_god_object_targets_god_class(sample_project: Path) -> None:
    findings = [
        finding
        for finding in _analyze(sample_project).findings
        if finding.rule_id == "design/god-object"
    ]
    assert [finding.symbol for finding in findings] == ["samplepkg.god.GodClass"]
    assert findings[0].severity is Severity.HIGH


def test_unused_imports_point_at_dead_module(sample_project: Path) -> None:
    findings = [
        finding
        for finding in _analyze(sample_project).findings
        if finding.rule_id == "dead-code/unused-import"
    ]
    assert {finding.path for finding in findings} == {"samplepkg/dead.py"}
    assert all(finding.severity is Severity.LOW for finding in findings)


def test_unused_private_function_is_reported_once(sample_project: Path) -> None:
    findings = [
        finding
        for finding in _analyze(sample_project).findings
        if finding.rule_id == "dead-code/unused-private-function"
    ]
    assert [finding.symbol for finding in findings] == ["samplepkg.dead._never_used"]


def test_cycle_finding_lists_module_group(sample_project: Path) -> None:
    cycle = next(
        finding
        for finding in _analyze(sample_project).findings
        if finding.rule_id == "dependencies/cyclic-import"
    )
    assert cycle.category is Category.DEPENDENCIES
    assert set(cycle.details["modules"]) == {"samplepkg.a", "samplepkg.b"}


def test_findings_are_sorted_by_severity(sample_project: Path) -> None:
    findings = _analyze(sample_project).findings
    levels = [int(finding.severity) for finding in findings]
    assert levels == sorted(levels, reverse=True)


def test_health_score_is_bounded(sample_project: Path) -> None:
    result = _analyze(sample_project)
    assert 0 <= result.score.value <= 100
    assert result.score.grade in {"A", "B", "C", "D", "F"}
    assert sum(result.score.counts.values()) == len(result.findings)
    assert result.score.grade != "A"


def test_analysis_is_deterministic(sample_project: Path) -> None:
    first = _analyze(sample_project)
    second = _analyze(sample_project)
    assert [(f.rule_id, f.path, f.line) for f in first.findings] == [
        (f.rule_id, f.path, f.line) for f in second.findings
    ]
    assert first.score.value == second.score.value


def test_decorated_private_functions_are_not_reported(tmp_path: Path) -> None:
    module = tmp_path / "app.py"
    module.write_text(
        "class App:\n"
        "    def callback(self) -> object:\n"
        "        def decorator(function: object) -> object:\n"
        "            return function\n"
        "        return decorator\n"
        "\n"
        "\n"
        "app = App()\n"
        "\n"
        "\n"
        "@app.callback()\n"
        "def _root() -> None:\n"
        "    return None\n"
        "\n"
        "\n"
        "def _plain() -> None:\n"
        "    return None\n",
        encoding="utf-8",
    )

    result = analyze_repository(tmp_path, use_history=False)
    dead = [
        finding.symbol
        for finding in result.findings
        if finding.rule_id == "dead-code/unused-private-function"
    ]

    assert dead == ["app._plain"]
