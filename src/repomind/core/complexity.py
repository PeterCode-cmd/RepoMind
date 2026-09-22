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
        return _score_loop(node, nesting)
    if isinstance(node, ast.If):
        return _if_score(node, nesting)
    if isinstance(node, ast.ExceptHandler):
        return _score_handler(node, nesting)
    if isinstance(node, ast.Try):
        return _score_try(node, nesting)
    if isinstance(node, ast.Match):
        return _score_match(node, nesting)
    return _flat_score(node, nesting)


def _flat_score(node: ast.AST, nesting: int) -> int:
    """Score non-structural constructs without a nesting penalty."""
    if isinstance(node, ast.IfExp):
        return 1 + nesting + _cognitive_children(node, nesting)
    if isinstance(node, ast.BoolOp):
        return len(node.values) - 1 + _cognitive_children(node, nesting)
    if isinstance(node, ast.comprehension):
        return _score_comprehension(node, nesting)
    return _cognitive_children(node, nesting)


def _score_loop(node: ast.For | ast.AsyncFor | ast.While, nesting: int) -> int:
    """Score a loop with its body and optional ``else`` clause."""
    score = 1 + nesting + _cognitive_body(node.body, nesting + 1)
    if node.orelse:
        score += 1 + _cognitive_body(node.orelse, nesting)
    return score


def _score_handler(node: ast.ExceptHandler, nesting: int) -> int:
    """Score an ``except`` handler, which carries the try's nesting penalty."""
    return 1 + nesting + _cognitive_body(node.body, nesting + 1)


def _score_try(node: ast.Try, nesting: int) -> int:
    """Score a ``try`` statement; only its handlers add complexity."""
    score = _cognitive_body(node.body, nesting)
    score += sum(_cognitive_score(handler, nesting) for handler in node.handlers)
    score += _cognitive_body(node.orelse, nesting)
    score += _cognitive_body(node.finalbody, nesting)
    return score


def _score_match(node: ast.Match, nesting: int) -> int:
    """Score a ``match`` statement and its cases."""
    score = 1 + nesting
    for case in node.cases:
        score += _cognitive_score(case, nesting + 1)
    return score


def _score_comprehension(node: ast.comprehension, nesting: int) -> int:
    """Score a comprehension; filters are flat, generators recurse."""
    score = len(node.ifs)
    score += _cognitive_score(node.iter, nesting)
    for condition in node.ifs:
        score += _cognitive_score(condition, nesting)
    return score


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
        for group, offset in _child_groups(statement):
            deepest = max(deepest, _max_depth(group, depth + offset))
    return deepest


def _child_groups(statement: ast.AST) -> list[tuple[Iterable[ast.AST], int]]:
    """Return statement groups to descend into and their nesting offsets.

    ``elif`` chains keep the depth of the original ``if`` (matching cognitive
    complexity, which does not penalise ``elif``); every other control
    structure nests its bodies one level deeper.
    """
    if isinstance(statement, ast.Match):
        return [(case.body, 1) for case in statement.cases]
    if isinstance(statement, ast.If):
        if len(statement.orelse) == 1 and isinstance(statement.orelse[0], ast.If):
            return [(statement.body, 1), (statement.orelse, 0)]
        return [(statement.body, 1), (statement.orelse, 1)]
    if isinstance(statement, ast.Try):
        groups: list[tuple[Iterable[ast.AST], int]] = [
            (statement.body, 1),
            (statement.orelse, 1),
            (statement.finalbody, 1),
        ]
        groups.extend((handler.body, 1) for handler in statement.handlers)
        return groups
    if isinstance(statement, _NESTING_NODES):
        return [
            (getattr(statement, "body", ()), 1),
            (getattr(statement, "orelse", ()), 1),
            (getattr(statement, "finalbody", ()), 1),
            (getattr(statement, "handlers", ()), 1),
        ]
    return [(getattr(statement, "body", ()), 0)]
