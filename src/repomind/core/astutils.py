"""Small shared helpers for working with Python AST nodes."""

from __future__ import annotations

import ast


def call_name(func: ast.expr) -> str | None:
    """Return the dotted name of a call target, or ``None`` for expressions.

    Constructor calls are treated as their class name, so ``Service().run()``
    resolves to ``Service.run``.
    """
    parts: list[str] = []
    current: ast.expr = func
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Call):
        base = call_name(current.func)
        if base is None:
            return None
        parts.append(base)
    elif isinstance(current, ast.Name):
        parts.append(current.id)
    else:
        return None
    return ".".join(reversed(parts))
