"""Rules that report files RepoMind could not analyze."""

from __future__ import annotations

from repomind.core.rules.base import AnalysisContext
from repomind.models.enums import Category, Severity
from repomind.models.findings import Finding


class SyntaxErrorRule:
    """Flag Python files that fail to parse."""

    id = "correctness/syntax-error"
    title = "Syntax error"
    description = (
        "A file that does not parse is excluded from every metric, so its "
        "quality is invisible until the error is fixed."
    )
    category = Category.CORRECTNESS

    def analyze(self, context: AnalysisContext) -> list[Finding]:
        """Return one finding per unparsable module."""
        findings: list[Finding] = []
        for module in context.modules:
            if module.syntax_error is None:
                continue
            findings.append(
                Finding(
                    rule_id=self.id,
                    title=self.title,
                    message=f"`{module.rel_path}` cannot be parsed: {module.syntax_error}.",
                    severity=Severity.HIGH,
                    category=self.category,
                    path=module.rel_path,
                    line=1,
                    suggestion="Fix the syntax error, then run RepoMind again.",
                    details={"error": module.syntax_error},
                )
            )
        return findings
