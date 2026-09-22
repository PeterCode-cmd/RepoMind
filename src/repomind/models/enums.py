"""Enumerations describing findings and metric categories."""

from __future__ import annotations

from enum import IntEnum, StrEnum


class Severity(IntEnum):
    """Relative importance of a finding.

    ``Severity`` is an ``IntEnum`` so that findings can be compared and
    filtered numerically (``finding.severity >= Severity.HIGH``).
    """

    INFO = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

    @property
    def label(self) -> str:
        """Return the lowercase name of the severity."""
        return self.name.lower()


class Category(StrEnum):
    """Coarse grouping of findings, used for summaries and report sections."""

    COMPLEXITY = "complexity"
    MAINTAINABILITY = "maintainability"
    DESIGN = "design"
    DEAD_CODE = "dead-code"
    DEPENDENCIES = "dependencies"
    SECURITY = "security"
    CORRECTNESS = "correctness"
    DOCUMENTATION = "documentation"
    HISTORY = "history"
