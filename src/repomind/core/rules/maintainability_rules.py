"""Rules about function, parameter and file size."""

from __future__ import annotations

from repomind.core.rules.base import AnalysisContext, scaled_severity
from repomind.models.enums import Category, Severity
from repomind.models.findings import Finding


class LongFunctionRule:
    """Flag functions that grew beyond a readable size."""

    id = "maintainability/long-function"
    title = "Long function"
    description = (
        "Long functions mix several responsibilities, resist unit testing and "
        "attract merge conflicts."
    )
    category = Category.MAINTAINABILITY

    def analyze(self, context: AnalysisContext) -> list[Finding]:
        """Return one finding per function above the length threshold."""
        thresholds = context.config.thresholds
        findings: list[Finding] = []
        for module in context.modules:
            for function in module.all_functions:
                if function.length < thresholds.function_length_warn:
                    continue
                findings.append(
                    Finding(
                        rule_id=self.id,
                        title=self.title,
                        message=(
                            f"`{function.qualname}` is {function.length} lines long "
                            f"(warn >= {thresholds.function_length_warn})."
                        ),
                        severity=scaled_severity(
                            function.length,
                            thresholds.function_length_warn,
                            thresholds.function_length_high,
                            thresholds.function_length_critical,
                        ),
                        category=self.category,
                        path=module.rel_path,
                        line=function.lineno,
                        symbol=function.qualname,
                        suggestion=(
                            "Look for cohesive blocks inside the function and "
                            "extract them into named helpers."
                        ),
                        details={
                            "length": function.length,
                            "warn": thresholds.function_length_warn,
                            "high": thresholds.function_length_high,
                            "critical": thresholds.function_length_critical,
                        },
                    )
                )
        return findings


class TooManyParametersRule:
    """Flag functions that accept too many parameters."""

    id = "maintainability/too-many-parameters"
    title = "Too many parameters"
    description = (
        "Wide signatures hint at low cohesion and make call sites hard to "
        "read; long parameter lists are a classic refactoring trigger."
    )
    category = Category.MAINTAINABILITY

    def analyze(self, context: AnalysisContext) -> list[Finding]:
        """Return one finding per function above the parameter threshold."""
        thresholds = context.config.thresholds
        findings: list[Finding] = []
        for module in context.modules:
            for function in module.all_functions:
                if function.parameters <= thresholds.parameters_warn:
                    continue
                severity = (
                    Severity.HIGH
                    if function.parameters > thresholds.parameters_high
                    else Severity.MEDIUM
                )
                findings.append(
                    Finding(
                        rule_id=self.id,
                        title=self.title,
                        message=(
                            f"`{function.qualname}` takes {function.parameters} "
                            f"parameters (warn > {thresholds.parameters_warn})."
                        ),
                        severity=severity,
                        category=self.category,
                        path=module.rel_path,
                        line=function.lineno,
                        symbol=function.qualname,
                        suggestion=(
                            "Group related arguments into a dataclass or config "
                            "object, or split the function by responsibility."
                        ),
                        details={
                            "parameters": function.parameters,
                            "warn": thresholds.parameters_warn,
                            "high": thresholds.parameters_high,
                        },
                    )
                )
        return findings


class LargeFileRule:
    """Flag modules that grew beyond a readable size."""

    id = "maintainability/large-file"
    title = "Large file"
    description = (
        "Oversized modules concentrate unrelated responsibilities and are "
        "natural candidates for splitting."
    )
    category = Category.MAINTAINABILITY

    def analyze(self, context: AnalysisContext) -> list[Finding]:
        """Return one finding per module above the source line threshold."""
        thresholds = context.config.thresholds
        findings: list[Finding] = []
        for module in context.modules:
            if module.syntax_error is not None or module.loc < thresholds.file_loc_warn:
                continue
            findings.append(
                Finding(
                    rule_id=self.id,
                    title=self.title,
                    message=(
                        f"`{module.rel_path}` contains {module.loc} source lines "
                        f"(warn >= {thresholds.file_loc_warn})."
                    ),
                    severity=scaled_severity(
                        module.loc,
                        thresholds.file_loc_warn,
                        thresholds.file_loc_high,
                        thresholds.file_loc_critical,
                    ),
                    category=self.category,
                    path=module.rel_path,
                    line=1,
                    suggestion=(
                        "Group related definitions into a package or move "
                        "independent sections into dedicated modules."
                    ),
                    details={
                        "loc": module.loc,
                        "warn": thresholds.file_loc_warn,
                        "high": thresholds.file_loc_high,
                        "critical": thresholds.file_loc_critical,
                    },
                )
            )
        return findings
