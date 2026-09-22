"""Configuration-based suppression of findings.

Users silence known, accepted issues with ``ignore`` entries in the RepoMind
configuration::

    ignore = [
        "maintainability/too-many-parameters@src/app/cli.py",
        "dead-code/unused-import",
    ]

Suppressed findings are removed from scoring and from the main report, but
they are never hidden silently: they are reported as a separate count (and in
full in the JSON output).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from repomind.core.paths import matches_patterns
from repomind.errors import ConfigurationError
from repomind.models.findings import Finding


@dataclass(frozen=True, slots=True)
class Suppression:
    """A single ``rule-id`` or ``rule-id@glob`` ignore entry."""

    rule_id: str
    pattern: str | None = None

    def matches(self, finding: Finding) -> bool:
        """Return ``True`` when *finding* is suppressed by this entry."""
        if finding.rule_id != self.rule_id:
            return False
        if self.pattern is None:
            return True
        return matches_patterns(finding.path, [self.pattern])


def parse_suppression(text: str) -> Suppression:
    """Parse one suppression entry.

    Raises:
        ConfigurationError: If the entry is empty or has an empty path pattern.
    """
    rule_id, separator, pattern = text.partition("@")
    rule_id = rule_id.strip()
    pattern = pattern.strip()
    if not rule_id:
        raise ConfigurationError(f"invalid ignore entry {text!r}: missing rule id")
    if separator and not pattern:
        raise ConfigurationError(f"invalid ignore entry {text!r}: empty path pattern")
    return Suppression(rule_id=rule_id, pattern=pattern or None)


def parse_suppressions(entries: Iterable[str]) -> tuple[Suppression, ...]:
    """Parse every entry, failing fast on the first invalid one."""
    return tuple(parse_suppression(entry) for entry in entries)


def apply_suppressions(
    findings: Sequence[Finding],
    suppressions: Sequence[Suppression],
) -> tuple[list[Finding], list[Finding]]:
    """Split *findings* into ``(kept, suppressed)``."""
    if not suppressions:
        return list(findings), []

    kept: list[Finding] = []
    suppressed: list[Finding] = []
    for finding in findings:
        if any(suppression.matches(finding) for suppression in suppressions):
            suppressed.append(finding)
        else:
            kept.append(finding)
    return kept, suppressed
