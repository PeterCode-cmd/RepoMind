"""Tests for configuration-based suppression of findings."""

from __future__ import annotations

from pathlib import Path

import pytest

from repomind.config import AnalysisConfig
from repomind.core.engine import analyze_repository
from repomind.core.suppression import (
    Suppression,
    apply_suppressions,
    parse_suppression,
    parse_suppressions,
)
from repomind.errors import ConfigurationError
from repomind.models.enums import Category, Severity
from repomind.models.findings import Finding


def _finding(rule_id: str, path: str) -> Finding:
    return Finding(
        rule_id=rule_id,
        title="Test finding",
        message="Test message",
        severity=Severity.MEDIUM,
        category=Category.COMPLEXITY,
        path=path,
    )


def _complex_module(tmp_path: Path) -> Path:
    branches = "".join(f"    if value > {index}:\n        result += 1\n" for index in range(10))
    module = tmp_path / "app.py"
    module.write_text(
        f"def tangled(value: int) -> int:\n    result = 0\n{branches}    return result\n",
        encoding="utf-8",
    )
    return module


def test_parse_suppression_with_pattern() -> None:
    entry = parse_suppression("complexity/deep-nesting@src/app/mod.py")
    assert entry == Suppression(rule_id="complexity/deep-nesting", pattern="src/app/mod.py")


def test_parse_suppression_without_pattern() -> None:
    entry = parse_suppression("dead-code/unused-import")
    assert entry == Suppression(rule_id="dead-code/unused-import", pattern=None)


@pytest.mark.parametrize("entry", ["@src/app.py", "", "  "])
def test_parse_suppression_rejects_missing_rule(entry: str) -> None:
    with pytest.raises(ConfigurationError, match="missing rule id"):
        parse_suppression(entry)


def test_parse_suppression_rejects_empty_pattern() -> None:
    with pytest.raises(ConfigurationError, match="empty path pattern"):
        parse_suppression("complexity/deep-nesting@")


def test_parse_suppressions_parses_every_entry() -> None:
    entries = parse_suppressions(["rule-a", "rule-b@pkg/mod.py"])
    assert [entry.rule_id for entry in entries] == ["rule-a", "rule-b"]


def test_rule_only_suppression_matches_any_path() -> None:
    suppression = Suppression(rule_id="rule-a")
    assert suppression.matches(_finding("rule-a", "src/one.py"))
    assert suppression.matches(_finding("rule-a", "src/two.py"))
    assert not suppression.matches(_finding("rule-b", "src/one.py"))


def test_scoped_suppression_matches_glob() -> None:
    suppression = Suppression(rule_id="rule-a", pattern="src/pkg/*.py")
    assert suppression.matches(_finding("rule-a", "src/pkg/mod.py"))
    assert not suppression.matches(_finding("rule-a", "src/other/mod.py"))


def test_apply_suppressions_splits_findings() -> None:
    findings = [
        _finding("rule-a", "src/one.py"),
        _finding("rule-b", "src/two.py"),
    ]
    kept, suppressed = apply_suppressions(findings, [Suppression(rule_id="rule-a")])
    assert [finding.rule_id for finding in kept] == ["rule-b"]
    assert [finding.rule_id for finding in suppressed] == ["rule-a"]


def test_apply_suppressions_without_entries_is_noop() -> None:
    findings = [_finding("rule-a", "src/one.py")]
    kept, suppressed = apply_suppressions(findings, [])
    assert kept == findings
    assert suppressed == []


def test_engine_applies_suppressions(tmp_path: Path) -> None:
    _complex_module(tmp_path)
    baseline = analyze_repository(tmp_path, use_history=False)
    assert any(
        finding.rule_id == "complexity/high-cyclomatic-complexity" for finding in baseline.findings
    )

    config = AnalysisConfig(ignore=("complexity/high-cyclomatic-complexity@app.py",))
    result = analyze_repository(tmp_path, config=config, use_history=False)

    assert all(
        finding.rule_id != "complexity/high-cyclomatic-complexity" for finding in result.findings
    )
    assert [finding.rule_id for finding in result.suppressed] == [
        "complexity/high-cyclomatic-complexity"
    ]
    assert result.score.value >= baseline.score.value
    assert result.suppressed[0].path == "app.py"


def test_engine_without_ignore_has_no_suppressed_findings(tmp_path: Path) -> None:
    _complex_module(tmp_path)
    result = analyze_repository(tmp_path, use_history=False)
    assert result.suppressed == []


def test_engine_warns_about_unknown_rule_in_ignore(tmp_path: Path) -> None:
    _complex_module(tmp_path)
    config = AnalysisConfig(ignore=("not-a-rule@app.py",))
    result = analyze_repository(tmp_path, config=config, use_history=False)
    assert any("unknown rule" in warning for warning in result.warnings)
