"""Complexity metrics computed directly from Python's abstract syntax trees.

The functions in this module operate on a single ``FunctionDef``,
``AsyncFunctionDef`` or any other AST node and never descend into nested
function or class scopes: every function is measured on its own.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Iterator

_BRANCH_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.ExceptHandler,
    ast.With,
    ast.AsyncWith,
    ast.Assert,
    ast.IfExp,
)

_SCOPE_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)

_NESTING_NODES = (
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.With,
    ast.AsyncWith,
)


def cyclomatic_complexity(node: ast.AST) -> int:
    """Return McCabe's cyclomatic complexity for a function node.

    The score is one plus the number of independent decision points:
    ``if``/``elif``, loops, ``except`` handlers, ``with`` statements,
    ``assert``, conditional expressions, comprehension ``if`` clauses,
    boolean operators and ``match`` cases.
    """
    score = 1
    for child in _iter_own_nodes(node):
        if isinstance(child, _BRANCH_NODES):
            score += 1
        elif isinstance(child, ast.BoolOp):
            score += len(child.values) - 1
        elif isinstance(child, ast.comprehension):
            score += len(child.ifs)
        elif isinstance(child, ast.Match):
            score += len(child.cases)
    return score


def cognitive_complexity(node: ast.AST) -> int:
    """Return a Sonar-inspired cognitive complexity score.

    Structural constructs (``if``, loops, ``except``, ``match``) are scored
    ``1 + nesting level``, flat constructs (``else``, boolean operators,
    ternary expressions, comprehension filters) are scored ``1`` without a
    nesting penalty.
    """
    return sum(_cognitive_score(child, 0) for child in ast.iter_child_nodes(node))


def max_nesting_depth(node: ast.AST) -> int:
    """Return the maximum depth of nested control structures in *node*."""
    return _max_depth(getattr(node, "body", ()), 0)


def _iter_own_nodes(node: ast.AST) -> Iterator[ast.AST]:
    """Yield descendant nodes without entering nested function scopes."""
    stack = list(ast.iter_child_nodes(node))
    while stack:
        current = stack.pop()
        yield current
        if isinstance(current, _SCOPE_NODES):
            continue
        stack.extend(ast.iter_child_nodes(current))


def _cognitive_score(node: ast.AST, nesting: int) -> int:
    """Return the cognitive score of *node* at the given *nesting* level."""
    if isinstance(node, _SCOPE_NODES):
        return 0
    if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
        score = 1 + nesting + _cognitive_body(node.body, nesting + 1)
        if node.orelse:
            score += 1 + _cognitive_body(node.orelse, nesting)
        return score
    if isinstance(node, ast.If):
        return _if_score(node, nesting)
    if isinstance(node, ast.ExceptHandler):
        return 1 + nesting + _cognitive_body(node.body, nesting + 1)
    if isinstance(node, ast.Try):
        score = _cognitive_body(node.body, nesting)
        score += sum(_cognitive_score(handler, nesting) for handler in node.handlers)
        score += _cognitive_body(node.orelse, nesting)
        score += _cognitive_body(node.finalbody, nesting)
        return score
    if isinstance(node, ast.Match):
        score = 1 + nesting
        for case in node.cases:
            score += _cognitive_score(case, nesting + 1)
        return score
    if isinstance(node, ast.IfExp):
        return 1 + nesting + _cognitive_children(node, nesting)
    if isinstance(node, ast.BoolOp):
        return len(node.values) - 1 + _cognitive_children(node, nesting)
    if isinstance(node, ast.comprehension):
        score = len(node.ifs)
        score += _cognitive_score(node.iter, nesting)
        for condition in node.ifs:
            score += _cognitive_score(condition, nesting)
        return score
    return _cognitive_children(node, nesting)


def _if_score(node: ast.If, nesting: int) -> int:
    """Score an ``if``/``elif`` chain without double counting ``elif``."""
    score = 1 + nesting
    score += _cognitive_score(node.test, nesting)
    score += _cognitive_body(node.body, nesting + 1)
    if node.orelse:
        if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
            score += _cognitive_score(node.orelse[0], nesting)
        else:
            score += 1 + _cognitive_body(node.orelse, nesting)
    return score


def _cognitive_children(node: ast.AST, nesting: int) -> int:
    """Score every direct child of *node*."""
    return sum(_cognitive_score(child, nesting) for child in ast.iter_child_nodes(node))


def _cognitive_body(statements: Iterable[ast.AST], nesting: int) -> int:
    """Score a sequence of statements at the given *nesting* level."""
    return sum(_cognitive_score(statement, nesting) for statement in statements)


def _max_depth(items: Iterable[ast.AST], depth: int) -> int:
    """Return the deepest nesting level found in *items*."""
    deepest = depth
    for statement in items:
        if isinstance(statement, _SCOPE_NODES):
            continue
        if isinstance(statement, ast.Match):
            inner = depth + 1
            deepest = max(deepest, inner)
            for case in statement.cases:
                deepest = max(deepest, _max_depth(case.body, inner))
            continue
        if isinstance(statement, ast.If):
            inner = depth + 1
            deepest = max(deepest, _max_depth(statement.body, inner))
            if len(statement.orelse) == 1 and isinstance(statement.orelse[0], ast.If):
                deepest = max(deepest, _max_depth(statement.orelse, depth))
            else:
                deepest = max(deepest, _max_depth(statement.orelse, inner))
            continue
        if isinstance(statement, ast.Try):
            inner = depth + 1
            for group in (statement.body, statement.orelse, statement.finalbody):
                deepest = max(deepest, _max_depth(group, inner))
            for handler in statement.handlers:
                deepest = max(deepest, _max_depth(handler.body, inner))
            continue
        if isinstance(statement, _NESTING_NODES):
            inner = depth + 1
            deepest = max(
                deepest,
                _max_depth(getattr(statement, "body", ()), inner),
                _max_depth(getattr(statement, "orelse", ()), inner),
                _max_depth(getattr(statement, "finalbody", ()), inner),
                _max_depth(getattr(statement, "handlers", ()), inner),
            )
        else:
            deepest = max(deepest, _max_depth(getattr(statement, "body", ()), depth))
    return deepest
