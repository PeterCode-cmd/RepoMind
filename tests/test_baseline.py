"""Tests for baseline support and the fail-on-new workflow."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from repomind.core.baseline import (
    BASELINE_VERSION,
    Baseline,
    fingerprint,
    load_baseline,
    save_baseline,
)
from repomind.core.engine import analyze_repository
from repomind.errors import ConfigurationError
from repomind.models.enums import Category, Severity
from repomind.models.findings import Finding


def _finding(
    *,
    rule_id: str = "complexity/rule",
    path: str = "app.py",
    symbol: str | None = "app.func",
    line: int = 1,
    severity: Severity = Severity.MEDIUM,
) -> Finding:
    return Finding(
        rule_id=rule_id,
        title="Title",
        message="Message",
        severity=severity,
        category=Category.COMPLEXITY,
        path=path,
        line=line,
        symbol=symbol,
    )


def _project_with_findings(tmp_path: Path) -> Path:
    branches = "".join(f"    if value > {index}:\n        result += 1\n" for index in range(10))
    module = tmp_path / "app.py"
    module.write_text(
        f"def tangled(value: int) -> int:\n    result = 0\n{branches}    return result\n",
        encoding="utf-8",
    )
    return module


def test_fingerprint_ignores_line_numbers_and_values() -> None:
    assert fingerprint(_finding(line=10)) == fingerprint(_finding(line=99))


def test_fingerprint_changes_with_rule_path_and_symbol() -> None:
    assert fingerprint(_finding(rule_id="rule-a")) != fingerprint(_finding(rule_id="rule-b"))
    assert fingerprint(_finding(path="a.py")) != fingerprint(_finding(path="b.py"))
    assert fingerprint(_finding(symbol="a")) != fingerprint(_finding(symbol="b"))


def test_baseline_split() -> None:
    accepted = _finding(symbol="known")
    baseline = Baseline.from_findings([accepted])

    new, known = baseline.split([accepted, _finding(symbol="new")])

    assert [finding.symbol for finding in new] == ["new"]
    assert [finding.symbol for finding in known] == ["known"]
    assert baseline.size == 1
    assert baseline.contains(accepted)


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    findings = [_finding(), _finding(rule_id="other", symbol=None)]
    path = tmp_path / "baseline.json"

    save_baseline(findings, path)
    baseline = load_baseline(path)

    assert baseline.size == 2
    assert all(baseline.contains(finding) for finding in findings)
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["version"] == BASELINE_VERSION
    assert document["findings"][0]["rule_id"]


def test_save_creates_parent_directories(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "baseline.json"
    save_baseline([], path)
    assert path.is_file()


@pytest.mark.parametrize(
    ("content", "match"),
    [
        ("not json", "invalid JSON"),
        ('{"version": 1}', "missing 'findings'"),
        ('{"version": 99, "findings": []}', "unsupported baseline version"),
        ('{"version": 1, "findings": [{}]}', "needs a string 'fingerprint'"),
        ('["list"]', "expected a JSON object"),
    ],
)
def test_load_rejects_malformed_files(tmp_path: Path, content: str, match: str) -> None:
    path = tmp_path / "baseline.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ConfigurationError, match=match):
        load_baseline(path)


def test_engine_reports_new_findings_against_baseline(tmp_path: Path) -> None:
    _project_with_findings(tmp_path)
    first = analyze_repository(tmp_path, use_history=False)
    baseline = Baseline.from_findings(first.findings)

    second = analyze_repository(tmp_path, use_history=False, baseline=baseline)

    assert second.baseline_size == baseline.size
    assert second.new_findings == []
    assert second.findings


def test_engine_detects_findings_added_after_baseline(tmp_path: Path) -> None:
    module = _project_with_findings(tmp_path)
    baseline = Baseline.from_findings(analyze_repository(tmp_path, use_history=False).findings)

    module.write_text(
        module.read_text(encoding="utf-8")
        + "\n\ndef extra(a: int, b: int, c: int, d: int, e: int, f: int, g: int) -> int:\n"
        + "    return a + b + c + d + e + f + g\n",
        encoding="utf-8",
    )
    result = analyze_repository(tmp_path, use_history=False, baseline=baseline)

    assert [finding.rule_id for finding in result.new_findings] == [
        "maintainability/too-many-parameters"
    ]


def test_engine_without_baseline_reports_no_new_findings(tmp_path: Path) -> None:
    _project_with_findings(tmp_path)
    result = analyze_repository(tmp_path, use_history=False)
    assert result.new_findings == []
    assert result.baseline_size is None
