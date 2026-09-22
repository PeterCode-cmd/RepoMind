"""Repository health scoring derived from findings and code size."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from repomind.models.enums import Severity
from repomind.models.findings import Finding

SEVERITY_PENALTIES: dict[Severity, float] = {
    Severity.CRITICAL: 8.0,
    Severity.HIGH: 4.0,
    Severity.MEDIUM: 1.5,
    Severity.LOW: 0.5,
    Severity.INFO: 0.1,
}

_GRADE_THRESHOLDS: tuple[tuple[float, str], ...] = (
    (1.0, "A"),
    (2.0, "B"),
    (4.0, "C"),
    (7.0, "D"),
)


@dataclass(frozen=True, slots=True)
class HealthScore:
    """Aggregated repository health derived from findings and code size.

    Attributes:
        value: Score between 0 and 100, where 100 is a perfectly clean run.
        grade: Letter grade from ``A`` (best) to ``F``.
        penalty: Sum of severity penalties across all findings.
        density: Penalty per 100 source lines, used for the grade.
        counts: Number of findings per severity.
    """

    value: int
    grade: str
    penalty: float
    density: float
    counts: dict[Severity, int]


def compute_health_score(findings: Sequence[Finding], loc: int) -> HealthScore:
    """Compute the repository health score.

    Findings are converted into penalty points (weights per severity), the
    penalty is normalised per 100 source lines and the result is mapped onto
    a 0-100 scale. Size normalisation keeps large legacy repositories from
    being punished for their sheer size.

    Args:
        findings: All findings produced by the analysis.
        loc: Total number of source lines of code in the repository.

    Returns:
        The computed :class:`HealthScore`.
    """
    counts = dict.fromkeys(Severity, 0)
    penalty = 0.0
    for finding in findings:
        counts[finding.severity] += 1
        penalty += SEVERITY_PENALTIES[finding.severity]

    density = penalty / max(1.0, loc / 100.0)
    value = round(max(0.0, min(100.0, 100.0 - density * 10.0)))
    return HealthScore(
        value=value,
        grade=_grade(density),
        penalty=round(penalty, 2),
        density=round(density, 2),
        counts=counts,
    )


def _grade(density: float) -> str:
    """Map a penalty density onto a letter grade."""
    for limit, grade in _GRADE_THRESHOLDS:
        if density < limit:
            return grade
    return "F"
