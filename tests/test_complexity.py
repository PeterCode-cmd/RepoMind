"""Tests for the complexity metrics."""

from __future__ import annotations

import ast

from repomind.core.complexity import (
    cognitive_complexity,
    cyclomatic_complexity,
    max_nesting_depth,
)


def _function(source: str) -> ast.AST:
    tree = ast.parse(source)
    node = tree.body[0]
    assert isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    return node


def test_simple_function_has_base_complexity() -> None:
    node = _function("def f():\n    return 1\n")
    assert cyclomatic_complexity(node) == 1
    assert cognitive_complexity(node) == 0
    assert max_nesting_depth(node) == 0


def test_branches_increase_complexity() -> None:
    source = "def f(x):\n    if x > 0:\n        return 1\n    else:\n        return 2\n"
    node = _function(source)
    assert cyclomatic_complexity(node) == 2
    assert cognitive_complexity(node) == 2
    assert max_nesting_depth(node) == 1


def test_boolean_operators_and_ternaries() -> None:
    node = _function("def f(a, b, c):\n    return a if b and c else 0\n")
    assert cyclomatic_complexity(node) == 3
    assert cognitive_complexity(node) == 2


def test_nested_functions_are_measured_separately() -> None:
    source = (
        "def outer():\n"
        "    def inner(x):\n"
        "        if x:\n"
        "            return 1\n"
        "        return 0\n"
        "    return inner(1)\n"
    )
    node = _function(source)
    assert cyclomatic_complexity(node) == 1
    assert cognitive_complexity(node) == 0


def test_cognitive_penalises_nesting() -> None:
    source = (
        "def f(a):\n"
        "    if a:\n"
        "        if a > 1:\n"
        "            if a > 2:\n"
        "                return 3\n"
        "    return 0\n"
    )
    node = _function(source)
    assert cyclomatic_complexity(node) == 4
    assert cognitive_complexity(node) == 1 + 2 + 3
    assert max_nesting_depth(node) == 3


def test_else_if_is_scored_without_nesting_penalty() -> None:
    source = (
        "def f(a):\n"
        "    if a:\n"
        "        return 1\n"
        "    elif a > 1:\n"
        "        if a > 2:\n"
        "            return 3\n"
        "    return 0\n"
    )
    node = _function(source)
    assert cyclomatic_complexity(node) == 4
    assert cognitive_complexity(node) == 1 + 1 + 2
    assert max_nesting_depth(node) == 2


def test_comprehension_filters_count() -> None:
    node = _function("def f(items):\n    return [x for x in items if x > 0]\n")
    assert cyclomatic_complexity(node) == 2


def test_try_except_counts_handler() -> None:
    source = "def f():\n    try:\n        return 1\n    except ValueError:\n        return 0\n"
    node = _function(source)
    assert cyclomatic_complexity(node) == 2
    assert cognitive_complexity(node) == 1
    assert max_nesting_depth(node) == 1


def test_match_statement_counts_cases() -> None:
    source = (
        "def f(value):\n"
        "    match value:\n"
        "        case 1:\n"
        "            return 1\n"
        "        case _:\n"
        "            return 0\n"
    )
    node = _function(source)
    assert cyclomatic_complexity(node) == 3
    assert max_nesting_depth(node) == 1
