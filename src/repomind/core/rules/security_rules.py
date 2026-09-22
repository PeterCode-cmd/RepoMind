"""Rules that surface security-relevant patterns found by the parser.

All checks are deterministic AST patterns extracted by
:mod:`repomind.core.pyparser`; the rules themselves only consume signals.
"""

from __future__ import annotations

from repomind.core.rules.base import AnalysisContext
from repomind.models.enums import Category, Severity
from repomind.models.findings import Finding


class _SecuritySignalRule:
    """Base class that turns one parser signal kind into findings."""

    kind: str
    severity: Severity
    id: str
    title: str
    description: str
    why: str
    suggestion: str
    category = Category.SECURITY

    def analyze(self, context: AnalysisContext) -> list[Finding]:
        """Return one finding per matching signal in the analyzed modules."""
        findings: list[Finding] = []
        for module in context.modules:
            for signal in module.security_signals:
                if signal.kind != self.kind:
                    continue
                findings.append(
                    Finding(
                        rule_id=self.id,
                        title=self.title,
                        message=f"{signal.detail}: {self.why}",
                        severity=self.severity,
                        category=self.category,
                        path=module.rel_path,
                        line=signal.lineno,
                        suggestion=self.suggestion,
                        details={"kind": signal.kind},
                    )
                )
        return findings


class DynamicExecutionRule(_SecuritySignalRule):
    """Flag ``eval`` and ``exec`` calls."""

    id = "security/dynamic-execution"
    title = "Dynamic code execution"
    description = (
        "eval() and exec() execute arbitrary code and are a direct path to remote code execution."
    )
    kind = "dynamic-execution"
    severity = Severity.HIGH
    why = "dynamic execution of untrusted input enables arbitrary code execution"
    suggestion = (
        "Replace eval/exec with a parser or an explicit whitelist of operations; "
        "use ast.literal_eval when the input is data."
    )


class ShellExecutionRule(_SecuritySignalRule):
    """Flag shell command execution."""

    id = "security/shell-execution"
    title = "Shell command execution"
    description = (
        "os.system and shell=True hand user input to the shell and enable command injection."
    )
    kind = "shell-execution"
    severity = Severity.HIGH
    why = "shell interpretation of input enables command injection"
    suggestion = (
        "Pass an argument list to subprocess.run without shell=True, and validate "
        "or reject untrusted values."
    )


class UnsafeDeserializationRule(_SecuritySignalRule):
    """Flag unsafe deserialization of untrusted data."""

    id = "security/unsafe-deserialization"
    title = "Unsafe deserialization"
    description = "pickle and yaml.load can execute arbitrary code while parsing untrusted data."
    kind = "unsafe-deserialization"
    severity = Severity.HIGH
    why = "deserializing untrusted data can execute arbitrary code"
    suggestion = (
        "Use json or a schema-validated format; for YAML use yaml.safe_load or "
        "Loader=yaml.SafeLoader."
    )


class WeakHashRule(_SecuritySignalRule):
    """Flag weak hashing algorithms."""

    id = "security/weak-hash"
    title = "Weak hash algorithm"
    description = "MD5 and SHA-1 are collision-prone and must not be used for security decisions."
    kind = "weak-hash"
    severity = Severity.MEDIUM
    why = "MD5/SHA-1 are unsuitable for security purposes"
    suggestion = (
        "Use SHA-256 or stronger; when the hash is not security related, pass "
        "usedforsecurity=False to document that."
    )


class InsecureTempFileRule(_SecuritySignalRule):
    """Flag insecure temporary file creation."""

    id = "security/insecure-temp-file"
    title = "Insecure temporary file"
    description = "tempfile.mktemp has a race condition between name creation and use."
    kind = "insecure-temp-file"
    severity = Severity.MEDIUM
    why = "mktemp is racy and can be hijacked"
    suggestion = "Use tempfile.NamedTemporaryFile or tempfile.TemporaryDirectory instead."


class HardcodedSecretRule(_SecuritySignalRule):
    """Flag hardcoded credentials.

    The heuristic matches credential-looking names assigned non-placeholder
    string literals. The value is never copied into the finding, so reports do
    not leak the secret itself.
    """

    id = "security/hardcoded-secret"
    title = "Hardcoded secret"
    description = "Credentials committed to source end up in every clone, fork and CI log."
    kind = "hardcoded-secret"
    severity = Severity.HIGH
    why = "the value is embedded in source control"
    suggestion = (
        "Load secrets from the environment or a secret manager; rotate the "
        "credential that was committed."
    )
