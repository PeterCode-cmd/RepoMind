"""Built-in rule registry.

Adding a rule means writing a class that satisfies
:class:`repomind.core.rules.base.Rule` and appending an instance to
:func:`default_rules`.
"""

from __future__ import annotations

from repomind.core.rules.base import AnalysisContext, Rule, scaled_severity
from repomind.core.rules.complexity_rules import (
    DeepNestingRule,
    HighCognitiveComplexityRule,
    HighCyclomaticComplexityRule,
)
from repomind.core.rules.correctness_rules import SyntaxErrorRule
from repomind.core.rules.dead_code_rules import (
    UnusedImportRule,
    UnusedPrivateFunctionRule,
)
from repomind.core.rules.dependency_rules import CyclicDependencyRule
from repomind.core.rules.design_rules import GodObjectRule, LowCohesionRule
from repomind.core.rules.documentation_rules import MissingDocstringRule
from repomind.core.rules.history_rules import ComplexityHotspotRule
from repomind.core.rules.maintainability_rules import (
    LargeFileRule,
    LongFunctionRule,
    TooManyParametersRule,
)
from repomind.core.rules.security_rules import (
    DynamicExecutionRule,
    HardcodedSecretRule,
    InsecureTempFileRule,
    ShellExecutionRule,
    UnsafeDeserializationRule,
    WeakHashRule,
)


def default_rules() -> tuple[Rule, ...]:
    """Return the built-in rule set in execution order."""
    return (
        SyntaxErrorRule(),
        HighCyclomaticComplexityRule(),
        HighCognitiveComplexityRule(),
        DeepNestingRule(),
        LongFunctionRule(),
        TooManyParametersRule(),
        LargeFileRule(),
        GodObjectRule(),
        LowCohesionRule(),
        UnusedImportRule(),
        UnusedPrivateFunctionRule(),
        CyclicDependencyRule(),
        MissingDocstringRule(),
        DynamicExecutionRule(),
        ShellExecutionRule(),
        UnsafeDeserializationRule(),
        WeakHashRule(),
        InsecureTempFileRule(),
        HardcodedSecretRule(),
        ComplexityHotspotRule(),
    )


__all__ = [
    "AnalysisContext",
    "Rule",
    "default_rules",
    "scaled_severity",
]
