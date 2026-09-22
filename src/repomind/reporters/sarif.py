"""SARIF 2.1.0 output for GitHub code scanning and other SARIF consumers."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from repomind import __version__
from repomind.core.baseline import fingerprint
from repomind.core.engine import AnalysisResult
from repomind.models.enums import Severity
from repomind.models.findings import Finding

SARIF_VERSION = "2.1.0"
SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"
INFORMATION_URI = "https://github.com/PeterCode-cmd/RepoMind"

_LEVELS: dict[Severity, str] = {
    Severity.CRITICAL: "error",
    Severity.HIGH: "error",
    Severity.MEDIUM: "warning",
    Severity.LOW: "note",
    Severity.INFO: "note",
}


def render_sarif(
    result: AnalysisResult,
    *,
    findings: Sequence[Finding] | None = None,
) -> str:
    """Render the analysis result as a SARIF 2.1.0 JSON document."""
    return json.dumps(
        result_to_sarif(result, findings=findings),
        indent=2,
        ensure_ascii=False,
    )


def result_to_sarif(
    result: AnalysisResult,
    *,
    findings: Sequence[Finding] | None = None,
) -> dict[str, Any]:
    """Convert an analysis result into a SARIF 2.1.0 dictionary."""
    selected = list(result.findings if findings is None else findings)
    return {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "RepoMind",
                        "informationUri": INFORMATION_URI,
                        "version": __version__,
                        "rules": _rules(selected),
                    }
                },
                "results": [_result(finding) for finding in selected],
            }
        ],
    }


def _rules(findings: Sequence[Finding]) -> list[dict[str, Any]]:
    """Return the deduplicated rule descriptors used by the results."""
    unique: dict[str, Finding] = {}
    for finding in findings:
        unique.setdefault(finding.rule_id, finding)
    return [
        {
            "id": finding.rule_id,
            "name": finding.title,
            "shortDescription": {"text": finding.title},
            "helpUri": f"{INFORMATION_URI}#built-in-rules",
            "properties": {"category": finding.category.value},
        }
        for finding in unique.values()
    ]


def _result(finding: Finding) -> dict[str, Any]:
    """Convert one finding into a SARIF result object."""
    message: dict[str, str] = {"text": finding.message}
    if finding.suggestion:
        message["markdown"] = f"{finding.message}\n\n**Suggestion:** {finding.suggestion}"
    return {
        "ruleId": finding.rule_id,
        "level": _LEVELS[finding.severity],
        "message": message,
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": finding.path, "uriBaseId": "%SRCROOT%"},
                    "region": {"startLine": finding.line or 1},
                }
            }
        ],
        "partialFingerprints": {"repomind/v1": fingerprint(finding)},
        "properties": {
            "severity": finding.severity.label,
            "symbol": finding.symbol,
            "category": finding.category.value,
        },
    }
