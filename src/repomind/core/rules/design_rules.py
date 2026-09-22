"""Rules about class and module design."""

from __future__ import annotations

from repomind.config import Thresholds
from repomind.core.rules.base import AnalysisContext
from repomind.models.enums import Category, Severity
from repomind.models.findings import Finding
from repomind.models.metrics import ClassMetrics, ParsedModule


class GodObjectRule:
    """Flag classes that accumulated too many responsibilities."""

    id = "design/god-object"
    title = "God object"
    description = (
        "Classes that combine many methods, attributes and responsibilities "
        "become change magnets and resist testing in isolation."
    )
    category = Category.DESIGN

    def analyze(self, context: AnalysisContext) -> list[Finding]:
        """Return one finding per class that violates any size threshold."""
        thresholds = context.config.thresholds
        findings: list[Finding] = []
        for module in context.modules:
            for cls in module.classes:
                criteria = _violated_criteria(cls, thresholds)
                if criteria:
                    findings.append(_god_object_finding(self, module, cls, criteria))
        return findings


def _violated_criteria(cls: ClassMetrics, thresholds: Thresholds) -> list[str]:
    """Return human readable descriptions of every violated size threshold."""
    criteria: list[str] = []
    if cls.public_method_count >= thresholds.god_object_methods:
        criteria.append(f"{cls.public_method_count} methods >= {thresholds.god_object_methods}")
    if cls.length >= thresholds.god_object_loc:
        criteria.append(f"{cls.length} lines >= {thresholds.god_object_loc}")
    if cls.wmc >= thresholds.god_object_wmc:
        criteria.append(f"WMC {cls.wmc} >= {thresholds.god_object_wmc}")
    return criteria


def _god_object_finding(
    rule: GodObjectRule,
    module: ParsedModule,
    cls: ClassMetrics,
    criteria: list[str],
) -> Finding:
    """Build the finding for a class that violated one or more thresholds."""
    severity = Severity.CRITICAL if len(criteria) > 1 else Severity.HIGH
    return Finding(
        rule_id=rule.id,
        title=rule.title,
        message=(
            f"Class `{cls.name}` in {module.rel_path} looks like a god "
            f"object ({'; '.join(criteria)})."
        ),
        severity=severity,
        category=rule.category,
        path=module.rel_path,
        line=cls.lineno,
        symbol=f"{module.module_name}.{cls.name}",
        suggestion=(
            "Identify cohesive responsibilities and extract them "
            "into collaborators; keep the class focused on one reason "
            "to change."
        ),
        details={
            "methods": cls.public_method_count,
            "loc": cls.length,
            "wmc": cls.wmc,
            "attributes": cls.attribute_count,
            "criteria": criteria,
        },
    )
