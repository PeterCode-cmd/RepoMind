"""Rules that surface complexity hot spots inside functions."""

from __future__ import annotations

from repomind.core.rules.base import AnalysisContext, scaled_severity
from repomind.models.enums import Category, Severity
from repomind.models.findings import Finding


class HighCyclomaticComplexityRule:
    """Flag functions with many independent execution paths."""

    id = "complexity/high-cyclomatic-complexity"
    title = "High cyclomatic complexity"
    description = (
        "Cyclomatic complexity counts independent paths; high values mean the "
        "function is hard to test, review and change safely."
    )
    category = Category.COMPLEXITY

    def analyze(self, context: AnalysisContext) -> list[Finding]:
        """Return one finding per function above the warning threshold."""
        thresholds = context.config.thresholds
        findings: list[Finding] = []
        for module in context.modules:
            for function in module.all_functions:
                if function.cyclomatic < thresholds.cyclomatic_warn:
                    continue
                findings.append(
                    Finding(
                        rule_id=self.id,
                        title=self.title,
                        message=(
                            f"`{function.qualname}` has cyclomatic complexity "
                            f"{function.cyclomatic} "
                            f"(warn >= {thresholds.cyclomatic_warn}, critical >= "
                            f"{thresholds.cyclomatic_critical})."
                        ),
                        severity=scaled_severity(
                            function.cyclomatic,
                            thresholds.cyclomatic_warn,
                            thresholds.cyclomatic_high,
                            thresholds.cyclomatic_critical,
                        ),
                        category=self.category,
                        path=module.rel_path,
                        line=function.lineno,
                        symbol=function.qualname,
                        suggestion=(
                            "Split the function into smaller pieces, extract helpers "
                            "or replace nested branches with early returns."
                        ),
                        details={
                            "cyclomatic": function.cyclomatic,
                            "warn": thresholds.cyclomatic_warn,
                            "high": thresholds.cyclomatic_high,
                            "critical": thresholds.cyclomatic_critical,
                        },
                    )
                )
        return findings


class HighCognitiveComplexityRule:
    """Flag functions that are hard for humans to follow."""

    id = "complexity/high-cognitive-complexity"
    title = "High cognitive complexity"
    description = (
        "Cognitive complexity weights nesting and flow breaks; high values "
        "correlate with review effort and defect density."
    )
    category = Category.COMPLEXITY

    def analyze(self, context: AnalysisContext) -> list[Finding]:
        """Return one finding per function above the warning threshold."""
        thresholds = context.config.thresholds
        findings: list[Finding] = []
        for module in context.modules:
            for function in module.all_functions:
                if function.cognitive < thresholds.cognitive_warn:
                    continue
                findings.append(
                    Finding(
                        rule_id=self.id,
                        title=self.title,
                        message=(
                            f"`{function.qualname}` has cognitive complexity "
                            f"{function.cognitive} "
                            f"(warn >= {thresholds.cognitive_warn})."
                        ),
                        severity=scaled_severity(
                            function.cognitive,
                            thresholds.cognitive_warn,
                            thresholds.cognitive_high,
                            thresholds.cognitive_critical,
                        ),
                        category=self.category,
                        path=module.rel_path,
                        line=function.lineno,
                        symbol=function.qualname,
                        suggestion=(
                            "Flatten nesting with guard clauses or extract the "
                            "nested logic into a well-named helper."
                        ),
                        details={
                            "cognitive": function.cognitive,
                            "warn": thresholds.cognitive_warn,
                            "high": thresholds.cognitive_high,
                            "critical": thresholds.cognitive_critical,
                        },
                    )
                )
        return findings


class DeepNestingRule:
    """Flag functions with deeply nested control flow."""

    id = "complexity/deep-nesting"
    title = "Deeply nested control flow"
    description = (
        "Every nesting level adds state a reader must hold in mind; four or "
        "more levels usually hide extractable logic."
    )
    category = Category.COMPLEXITY

    def analyze(self, context: AnalysisContext) -> list[Finding]:
        """Return one finding per function above the nesting threshold."""
        thresholds = context.config.thresholds
        findings: list[Finding] = []
        for module in context.modules:
            for function in module.all_functions:
                if function.nesting_depth < thresholds.nesting_warn:
                    continue
                severity = (
                    Severity.HIGH
                    if function.nesting_depth >= thresholds.nesting_high
                    else Severity.MEDIUM
                )
                findings.append(
                    Finding(
                        rule_id=self.id,
                        title=self.title,
                        message=(
                            f"`{function.qualname}` nests control flow "
                            f"{function.nesting_depth} levels deep "
                            f"(warn >= {thresholds.nesting_warn})."
                        ),
                        severity=severity,
                        category=self.category,
                        path=module.rel_path,
                        line=function.lineno,
                        symbol=function.qualname,
                        suggestion=(
                            "Use guard clauses, early returns or extract the inner "
                            "blocks into separate functions."
                        ),
                        details={
                            "nesting_depth": function.nesting_depth,
                            "warn": thresholds.nesting_warn,
                            "high": thresholds.nesting_high,
                        },
                    )
                )
        return findings
