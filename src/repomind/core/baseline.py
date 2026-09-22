"""Baseline support: accept existing findings and fail only on new ones.

A baseline stores fingerprints of findings that were reviewed and accepted.
It is the adoption path for legacy repositories: generate a baseline once,
then let CI fail only when *new* problems appear.

Fingerprints deliberately exclude line numbers and measured values, so a known
issue stays known when it moves or grows, and only disappears when the rule,
file or symbol changes.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from repomind.errors import ConfigurationError
from repomind.models.findings import Finding, sort_findings

BASELINE_FILENAME = ".repomind-baseline.json"
BASELINE_VERSION = 1


def fingerprint(finding: Finding) -> str:
    """Return a stable fingerprint for *finding*."""
    key = "\x00".join((finding.rule_id, finding.path, finding.symbol or ""))
    digest = hashlib.sha1(key.encode("utf-8"), usedforsecurity=False)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class Baseline:
    """Fingerprints of findings accepted by an earlier analysis run."""

    fingerprints: frozenset[str]
    path: Path | None = None

    @classmethod
    def from_findings(
        cls,
        findings: Iterable[Finding],
        *,
        path: Path | None = None,
    ) -> Baseline:
        """Build a baseline accepting every finding in *findings*."""
        return cls(fingerprints=frozenset(fingerprint(finding) for finding in findings), path=path)

    @property
    def size(self) -> int:
        """Return the number of accepted findings."""
        return len(self.fingerprints)

    def contains(self, finding: Finding) -> bool:
        """Return ``True`` when *finding* is part of the baseline."""
        return fingerprint(finding) in self.fingerprints

    def split(self, findings: Sequence[Finding]) -> tuple[list[Finding], list[Finding]]:
        """Split *findings* into ``(new, known)``."""
        new: list[Finding] = []
        known: list[Finding] = []
        for finding in findings:
            target = known if self.contains(finding) else new
            target.append(finding)
        return new, known


def load_baseline(path: Path) -> Baseline:
    """Load a baseline file.

    Raises:
        ConfigurationError: If the file cannot be read or is malformed.
    """
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigurationError(f"{path}: cannot be read: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigurationError(f"{path}: invalid JSON: {exc}") from exc

    if not isinstance(document, dict):
        raise ConfigurationError(f"{path}: expected a JSON object")
    version = document.get("version")
    if version != BASELINE_VERSION:
        raise ConfigurationError(
            f"{path}: unsupported baseline version {version!r} (expected {BASELINE_VERSION})"
        )
    entries = document.get("findings")
    if not isinstance(entries, list):
        raise ConfigurationError(f"{path}: missing 'findings' list")

    fingerprints: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("fingerprint"), str):
            raise ConfigurationError(f"{path}: every finding needs a string 'fingerprint'")
        fingerprints.add(entry["fingerprint"])

    return Baseline(fingerprints=frozenset(fingerprints), path=path)


def save_baseline(findings: Iterable[Finding], path: Path) -> None:
    """Write a human-reviewable baseline file for *findings*."""
    entries = [
        {
            "fingerprint": fingerprint(finding),
            "rule_id": finding.rule_id,
            "path": finding.path,
            "symbol": finding.symbol,
            "severity": finding.severity.label,
        }
        for finding in sort_findings(list(findings))
    ]
    document: dict[str, Any] = {"version": BASELINE_VERSION, "findings": entries}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
