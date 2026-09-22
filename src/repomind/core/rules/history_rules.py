"""Rules that combine Git history with static metrics."""

from __future__ import annotations

from repomind.core.rules.base import AnalysisContext
from repomind.models.enums import Category, Severity
from repomind.models.findings import Finding


class ComplexityHotspotRule:
    """Flag complex functions living in frequently changed files.

    This is the classic hotspot heuristic: complexity alone is a smell, churn
    alone is a smell, but complexity combined with churn is where defects and
    maintenance cost concentrate.
    """

    id = "history/complexity-hotspot"
    title = "Complexity hotspot"
    description = (
        "Functions in the most frequently changed files that also carry high "
        "cyclomatic complexity deserve refactoring priority."
    )
    category = Category.HISTORY

    def analyze(self, context: AnalysisContext) -> list[Finding]:
        """Return one finding per complex function in a high-churn file."""
        history = context.history
        if history is None or not history.files:
            return []

        thresholds = context.config.thresholds
        churn_floor = max(
            thresholds.hotspot_min_commits,
            int(history.churn_percentile(0.75)),
        )

        findings: list[Finding] = []
        for module in context.modules:
            file_history = history.files.get(module.rel_path)
            if file_history is None or file_history.commits < churn_floor:
                continue
            for function in module.all_functions:
                if function.cyclomatic < thresholds.hotspot_min_cyclomatic:
                    continue
                findings.append(
                    Finding(
                        rule_id=self.id,
                        title=self.title,
                        message=(
                            f"`{function.qualname}` has cyclomatic complexity "
                            f"{function.cyclomatic} and lives in a file changed "
                            f"{file_history.commits} times "
                            f"({file_history.churn} lines changed)."
                        ),
                        severity=(
                            Severity.HIGH
                            if function.cyclomatic >= thresholds.cyclomatic_high
                            else Severity.MEDIUM
                        ),
                        category=self.category,
                        path=module.rel_path,
                        line=function.lineno,
                        symbol=function.qualname,
                        suggestion=(
                            "Refactor this function first: it is both complex and "
                            "under constant change, so improvements compound."
                        ),
                        details={
                            "cyclomatic": function.cyclomatic,
                            "commits": file_history.commits,
                            "churn": file_history.churn,
                            "authors": file_history.author_count,
                            "churn_floor": churn_floor,
                        },
                    )
                )
        return findings
