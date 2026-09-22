"""Domain models shared across RepoMind's analysis pipeline.

The models in this package are deliberately free of behaviour: they describe
findings, metrics and configuration so that every other layer (rules,
reporters, future agents) can depend on a stable vocabulary.
"""

from __future__ import annotations

from repomind.models.enums import Category, Severity
from repomind.models.findings import Finding
from repomind.models.metrics import (
    ClassMetrics,
    FunctionMetrics,
    ImportInfo,
    ParsedModule,
    SecuritySignal,
)

__all__ = [
    "Category",
    "ClassMetrics",
    "Finding",
    "FunctionMetrics",
    "ImportInfo",
    "ParsedModule",
    "SecuritySignal",
    "Severity",
]
