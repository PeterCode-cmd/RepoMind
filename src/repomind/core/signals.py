"""Security signal extraction from Python ASTs.

The parser calls :func:`collect_security_signals` so that security rules stay
pure consumers of prepared data. Import aliases are resolved (``import
subprocess as sp``) before matching, and secret values are never recorded: a
hardcoded-secret signal only carries the variable name.
"""

from __future__ import annotations

import ast

from repomind.core.astutils import call_name
from repomind.models.metrics import SecuritySignal

_DYNAMIC_EXECUTION_NAMES = frozenset({"eval", "exec"})
_SHELL_NAMES = frozenset({"os.system", "os.popen"})
_UNSAFE_DESERIALIZERS = frozenset({"pickle", "cPickle", "marshal", "dill"})
_WEAK_HASH_NAMES = frozenset({"hashlib.md5", "hashlib.sha1"})
_WEAK_HASH_ALGORITHMS = frozenset({"md5", "sha1"})
_SECRET_NAME_PARTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "access_key",
    "private_key",
    "credential",
)
_SECRET_PLACEHOLDERS = (
    "example",
    "placeholder",
    "changeme",
    "change_me",
    "dummy",
    "fake",
    "sample",
    "xxxx",
    "your_",
    "todo",
    "<",
    "${",
    "{{",
    "test",
)
_SECRET_MIN_LENGTH = 8


def collect_security_signals(tree: ast.Module) -> list[SecuritySignal]:
    """Extract security-relevant patterns from a parsed module."""
    aliases = _import_aliases(tree)
    signals: list[SecuritySignal] = []
    for node in ast.walk(tree):
        signal: SecuritySignal | None = None
        if isinstance(node, ast.Call):
            signal = _call_signal(node, aliases)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            signal = _secret_signal(node)
        if signal is not None:
            signals.append(signal)
    return sorted(signals, key=lambda signal: (signal.lineno, signal.kind))


def _import_aliases(tree: ast.Module) -> dict[str, str]:
    """Map local import names to fully qualified module paths."""
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        aliases.update(_node_aliases(node))
    return aliases


def _node_aliases(node: ast.AST) -> dict[str, str]:
    """Return the alias mapping contributed by one import statement."""
    if isinstance(node, ast.Import):
        return {alias.asname: alias.name for alias in node.names if alias.asname}
    if isinstance(node, ast.ImportFrom) and node.module:
        return {alias.asname or alias.name: f"{node.module}.{alias.name}" for alias in node.names}
    return {}


def _resolve_alias(name: str, aliases: dict[str, str]) -> str:
    """Rewrite the first segment of *name* through the import alias map."""
    head, separator, tail = name.partition(".")
    resolved = aliases.get(head, head)
    return f"{resolved}.{tail}" if separator else resolved


def _call_signal(node: ast.Call, aliases: dict[str, str]) -> SecuritySignal | None:
    """Return the security signal for one call expression, if any."""
    name = call_name(node.func)
    if name is None:
        return None
    resolved = _resolve_alias(name, aliases)
    return (
        _execution_signal(resolved, node)
        or _deserialization_signal(resolved, node)
        or _weak_hash_signal(resolved, node)
        or _temp_file_signal(resolved, node)
    )


def _execution_signal(resolved: str, node: ast.Call) -> SecuritySignal | None:
    """Detect dynamic execution and shell command execution."""
    if resolved in _DYNAMIC_EXECUTION_NAMES:
        return SecuritySignal("dynamic-execution", node.lineno, f"{resolved}()")
    if resolved in _SHELL_NAMES:
        return SecuritySignal("shell-execution", node.lineno, f"{resolved}()")
    if _has_shell_true(node):
        return SecuritySignal("shell-execution", node.lineno, f"{resolved}(shell=True)")
    return None


def _temp_file_signal(resolved: str, node: ast.Call) -> SecuritySignal | None:
    """Detect insecure temporary file creation."""
    if resolved == "tempfile.mktemp":
        return SecuritySignal("insecure-temp-file", node.lineno, "tempfile.mktemp()")
    return None


def _deserialization_signal(resolved: str, node: ast.Call) -> SecuritySignal | None:
    """Detect unsafe deserialization calls."""
    head = resolved.split(".", maxsplit=1)[0]
    if head in _UNSAFE_DESERIALIZERS and resolved.endswith((".load", ".loads")):
        return SecuritySignal("unsafe-deserialization", node.lineno, f"{resolved}()")
    if resolved != "yaml.load":
        return None
    loader = _keyword_value(node, "Loader")
    if loader is None:
        return SecuritySignal(
            "unsafe-deserialization",
            node.lineno,
            "yaml.load() without SafeLoader",
        )
    if _is_safe_loader(loader):
        return None
    return SecuritySignal(
        "unsafe-deserialization",
        node.lineno,
        "yaml.load() with an unsafe Loader",
    )


def _weak_hash_signal(resolved: str, node: ast.Call) -> SecuritySignal | None:
    """Detect weak hash usage, honouring ``usedforsecurity=False``."""
    if _has_false_keyword(node, "usedforsecurity"):
        return None
    if resolved in _WEAK_HASH_NAMES:
        return SecuritySignal("weak-hash", node.lineno, f"{resolved}()")
    if resolved == "hashlib.new" and node.args:
        first = node.args[0]
        if (
            isinstance(first, ast.Constant)
            and isinstance(first.value, str)
            and first.value.lower() in _WEAK_HASH_ALGORITHMS
        ):
            return SecuritySignal(
                "weak-hash",
                node.lineno,
                f'hashlib.new("{first.value.lower()}")',
            )
    return None


def _secret_signal(node: ast.Assign | ast.AnnAssign) -> SecuritySignal | None:
    """Detect a secret-looking name assigned a non-placeholder string literal."""
    targets: list[ast.expr] = [node.target] if isinstance(node, ast.AnnAssign) else node.targets
    value = node.value
    if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
        return None
    if not _looks_like_secret(value.value):
        return None
    for target in targets:
        if isinstance(target, ast.Name) and _is_secret_name(target.id):
            return SecuritySignal(
                "hardcoded-secret",
                node.lineno,
                f"`{target.id}` is assigned a string literal",
            )
    return None


def _is_secret_name(name: str) -> bool:
    """Return ``True`` for identifiers that usually hold credentials."""
    lowered = name.lower()
    return any(part in lowered for part in _SECRET_NAME_PARTS)


def _looks_like_secret(text: str) -> bool:
    """Return ``True`` for strings that are long enough and not placeholders."""
    if len(text) < _SECRET_MIN_LENGTH:
        return False
    lowered = text.lower()
    return not any(marker in lowered for marker in _SECRET_PLACEHOLDERS)


def _has_shell_true(node: ast.Call) -> bool:
    """Return ``True`` when the call passes ``shell=True``."""
    return any(
        keyword.arg == "shell"
        and isinstance(keyword.value, ast.Constant)
        and keyword.value.value is True
        for keyword in node.keywords
    )


def _has_false_keyword(node: ast.Call, name: str) -> bool:
    """Return ``True`` when the call passes ``<name>=False``."""
    return any(
        keyword.arg == name
        and isinstance(keyword.value, ast.Constant)
        and keyword.value.value is False
        for keyword in node.keywords
    )


def _keyword_value(node: ast.Call, name: str) -> ast.expr | None:
    """Return the value of a keyword argument, if present."""
    for keyword in node.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def _is_safe_loader(value: ast.expr) -> bool:
    """Return ``True`` for ``yaml.SafeLoader``/``CSafeLoader`` style loaders."""
    name = call_name(value)
    return name is not None and name.endswith("SafeLoader")
