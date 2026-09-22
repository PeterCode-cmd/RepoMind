"""Parse Python source files into structured metrics.

This is the only module that touches the ``ast`` module directly. Everything
downstream (graphs, rules, reporters) consumes the dataclasses defined in
:mod:`repomind.models.metrics`.
"""

from __future__ import annotations

import ast
import io
import tokenize
from pathlib import Path

from repomind.core.astutils import call_name
from repomind.core.cohesion import lcom4
from repomind.core.complexity import (
    cognitive_complexity,
    cyclomatic_complexity,
    max_nesting_depth,
)
from repomind.core.signals import collect_security_signals
from repomind.models.metrics import ClassMetrics, FunctionMetrics, ImportInfo, ParsedModule

_SKIPPED_TOKEN_TYPES = frozenset(
    {
        tokenize.COMMENT,
        tokenize.DEDENT,
        tokenize.INDENT,
        tokenize.NEWLINE,
        tokenize.NL,
        tokenize.ENDMARKER,
    }
)


def parse_module(path: Path, root: Path) -> ParsedModule:
    """Parse a single file into a :class:`ParsedModule`.

    Files that cannot be decoded or parsed are returned with ``syntax_error``
    set and empty metrics instead of raising, so that one broken file never
    aborts an analysis run.
    """
    rel_path = path.relative_to(root).as_posix()
    module_name = _module_name(rel_path, fallback=root.name)

    try:
        with tokenize.open(path) as handle:
            source = handle.read()
    except (OSError, SyntaxError, UnicodeDecodeError) as exc:
        return ParsedModule(
            path=path,
            rel_path=rel_path,
            module_name=module_name,
            total_lines=0,
            loc=0,
            syntax_error=f"{type(exc).__name__}: {exc}",
        )

    total_lines = len(source.splitlines())
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return ParsedModule(
            path=path,
            rel_path=rel_path,
            module_name=module_name,
            total_lines=total_lines,
            loc=0,
            syntax_error=_format_syntax_error(exc),
        )

    references = _collect_references(tree)
    functions, classes, imports, exports = _collect_definitions(tree, module_name)
    loc = _count_source_lines(source)

    return ParsedModule(
        path=path,
        rel_path=rel_path,
        module_name=module_name,
        total_lines=total_lines,
        loc=loc,
        functions=functions,
        classes=classes,
        imports=imports,
        unused_imports=_find_unused_imports(imports, references, exports),
        security_signals=collect_security_signals(tree),
        all_exports=exports,
        references=references,
        has_docstring=ast.get_docstring(tree) is not None,
    )


def _module_name(rel_path: str, *, fallback: str) -> str:
    """Derive the dotted module name from a repository-relative path.

    A leading ``src/`` directory is stripped so that ``src``-layout projects
    resolve their own absolute imports (``src/pkg/mod.py`` becomes ``pkg.mod``).
    """
    parts = rel_path.split("/")
    if len(parts) > 1 and parts[0] == "src":
        parts = parts[1:]
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    elif parts[-1].endswith(".py"):
        parts[-1] = parts[-1][:-3]
    return ".".join(parts) or fallback


def _format_syntax_error(error: SyntaxError) -> str:
    """Render a :class:`SyntaxError` as a compact single-line message."""
    return f"line {error.lineno}: {error.msg}"


def _count_source_lines(source: str) -> int:
    """Count physical lines containing code, excluding blanks and comments."""
    code_lines: set[int] = set()
    reader = io.StringIO(source).readline
    try:
        for token in tokenize.generate_tokens(reader):
            if token.type not in _SKIPPED_TOKEN_TYPES:
                code_lines.add(token.start[0])
    except tokenize.TokenError:
        pass
    return len(code_lines)


def _collect_references(tree: ast.Module) -> frozenset[str]:
    """Collect every name-like identifier referenced anywhere in the module."""
    collector = _ReferenceCollector()
    collector.visit(tree)
    return frozenset(collector.names)


def _collect_definitions(
    tree: ast.Module,
    module_name: str,
) -> tuple[list[FunctionMetrics], list[ClassMetrics], list[ImportInfo], frozenset[str]]:
    """Extract functions, classes, imports and ``__all__`` from a module."""
    functions: list[FunctionMetrics] = []
    classes: list[ClassMetrics] = []
    imports: list[ImportInfo] = []
    exports: set[str] = set()

    for statement in tree.body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(_function_metrics(statement, module_name, class_name=None))
        elif isinstance(statement, ast.ClassDef):
            classes.append(_class_metrics(statement, module_name))
        elif isinstance(statement, (ast.Import, ast.ImportFrom)):
            imports.extend(_import_infos(statement))
        else:
            exports.update(_dunder_all(statement))

    return functions, classes, imports, frozenset(exports)


def _function_metrics(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    module_name: str,
    *,
    class_name: str | None,
) -> FunctionMetrics:
    """Build :class:`FunctionMetrics` for one function or method."""
    end_lineno = node.end_lineno if node.end_lineno is not None else node.lineno
    is_method = class_name is not None
    decorators = _decorator_names(node)
    qualname = (
        f"{module_name}.{class_name}.{node.name}" if is_method else f"{module_name}.{node.name}"
    )
    return FunctionMetrics(
        name=node.name,
        qualname=qualname,
        lineno=node.lineno,
        end_lineno=end_lineno,
        length=end_lineno - node.lineno + 1,
        parameters=_count_parameters(
            node,
            is_method=is_method,
            is_static="staticmethod" in decorators,
        ),
        cyclomatic=cyclomatic_complexity(node),
        cognitive=cognitive_complexity(node),
        nesting_depth=max_nesting_depth(node),
        is_method=is_method,
        class_name=class_name,
        decorators=decorators,
        calls=_collect_calls(node),
        attributes=_self_references(node),
        is_stub=_is_stub(node),
        has_docstring=ast.get_docstring(node) is not None,
    )


def _count_parameters(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    is_method: bool,
    is_static: bool,
) -> int:
    """Count declared parameters, dropping ``self``/``cls`` for methods."""
    positional = [*node.args.posonlyargs, *node.args.args]
    if is_method and not is_static and positional:
        positional = positional[1:]
    count = len(positional) + len(node.args.kwonlyargs)
    count += int(node.args.vararg is not None)
    count += int(node.args.kwarg is not None)
    return count


def _collect_calls(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[str, ...]:
    """Return distinct call targets used directly inside *node*.

    Nested functions, lambdas and classes are measured separately, so their
    calls are not attributed to the enclosing function.
    """
    names: set[str] = set()
    stack = list(ast.iter_child_nodes(node))
    while stack:
        current = stack.pop()
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(current, ast.Call):
            name = call_name(current.func)
            if name is not None:
                names.add(name)
        stack.extend(ast.iter_child_nodes(current))
    return tuple(sorted(names))


def _decorator_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[str, ...]:
    """Return readable names of all decorators applied to *node*."""
    return tuple(_decorator_name(decorator) for decorator in node.decorator_list)


def _decorator_name(decorator: ast.expr) -> str:
    """Return a readable name for one decorator expression."""
    target = decorator.func if isinstance(decorator, ast.Call) else decorator
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        return target.attr
    return ast.unparse(target)


def _class_metrics(node: ast.ClassDef, module_name: str) -> ClassMetrics:
    """Build :class:`ClassMetrics` for one class definition."""
    methods, attributes = _class_members(node, module_name)
    end_lineno = node.end_lineno if node.end_lineno is not None else node.lineno
    return ClassMetrics(
        name=node.name,
        lineno=node.lineno,
        end_lineno=end_lineno,
        length=end_lineno - node.lineno + 1,
        methods=methods,
        attribute_count=len(attributes),
        base_count=len(node.bases),
        lcom=lcom4(methods),
        has_docstring=ast.get_docstring(node) is not None,
    )


def _class_members(
    node: ast.ClassDef,
    module_name: str,
) -> tuple[list[FunctionMetrics], set[str]]:
    """Collect methods and attribute names declared directly on the class."""
    methods: list[FunctionMetrics] = []
    attributes: set[str] = set()

    for child in node.body:
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.append(_function_metrics(child, module_name, class_name=node.name))
            attributes.update(_self_attributes(child))
        else:
            attributes.update(_assigned_names(child))

    return methods, attributes


def _assigned_names(statement: ast.stmt) -> set[str]:
    """Return names assigned by a class-level assignment statement."""
    if isinstance(statement, ast.Assign):
        targets: list[ast.expr] = list(statement.targets)
    elif isinstance(statement, ast.AnnAssign):
        targets = [statement.target]
    else:
        return set()
    return {target.id for target in targets if isinstance(target, ast.Name)}


def _is_stub(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Return ``True`` for protocol-style methods without a real body."""
    for statement in node.body:
        if isinstance(statement, (ast.Pass, ast.Raise)):
            continue
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant):
            continue
        return False
    return True


def _self_references(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[str, ...]:
    """Return distinct ``self.<name>`` references inside a method."""
    names: set[str] = set()
    for child in ast.walk(node):
        if (
            isinstance(child, ast.Attribute)
            and isinstance(child.value, ast.Name)
            and child.value.id == "self"
        ):
            names.add(child.attr)
    return tuple(sorted(names))


def _self_attributes(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Collect attribute names assigned through ``self`` inside a method."""
    names: set[str] = set()
    for child in ast.walk(node):
        targets: list[ast.expr] = []
        if isinstance(child, ast.Assign):
            targets = list(child.targets)
        elif isinstance(child, ast.AnnAssign):
            targets = [child.target]
        for target in targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
            ):
                names.add(target.attr)
    return names


def _import_infos(node: ast.Import | ast.ImportFrom) -> list[ImportInfo]:
    """Convert an ``Import``/``ImportFrom`` node into :class:`ImportInfo` items."""
    if isinstance(node, ast.Import):
        return [
            ImportInfo(
                module=alias.name,
                name=None,
                alias=alias.asname,
                lineno=node.lineno,
                is_from=False,
            )
            for alias in node.names
        ]
    module = node.module or ""
    return [
        ImportInfo(
            module=module,
            name=alias.name,
            alias=alias.asname,
            lineno=node.lineno,
            is_from=True,
            level=node.level,
        )
        for alias in node.names
    ]


def _find_unused_imports(
    imports: list[ImportInfo],
    references: frozenset[str],
    exports: frozenset[str],
) -> list[ImportInfo]:
    """Return imports whose bound name is never referenced in the module."""
    unused: list[ImportInfo] = []
    for imported in imports:
        if imported.module == "__future__" or imported.is_reexport:
            continue
        bound = imported.bound_name
        if bound is None or bound in references or bound in exports:
            continue
        unused.append(imported)
    return unused


def _dunder_all(statement: ast.stmt) -> set[str]:
    """Extract string entries from an ``__all__`` assignment."""
    if isinstance(statement, ast.Assign):
        targets = statement.targets
    elif isinstance(statement, ast.AnnAssign):
        targets = [statement.target]
    else:
        return set()

    if not any(isinstance(target, ast.Name) and target.id == "__all__" for target in targets):
        return set()
    return _string_sequence(statement.value)


def _string_sequence(value: ast.expr | None) -> set[str]:
    """Return all string constants inside a list/tuple/set literal."""
    if not isinstance(value, (ast.List, ast.Tuple, ast.Set)):
        return set()
    return {
        element.value
        for element in value.elts
        if isinstance(element, ast.Constant) and isinstance(element.value, str)
    }


class _ReferenceCollector(ast.NodeVisitor):
    """Collect loaded names, attribute names and identifier-like strings.

    Strings are included on purpose: dynamic access such as
    ``getattr(obj, "_helper")`` or ``"private_method"`` in a registry should
    not be reported as dead code.
    """

    def __init__(self) -> None:
        """Initialize an empty reference set."""
        self.names: set[str] = set()

    def visit_Name(self, node: ast.Name) -> None:
        """Record names that are read, then keep visiting children."""
        if isinstance(node.ctx, ast.Load):
            self.names.add(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Record attribute accesses such as ``self._helper``."""
        self.names.add(node.attr)
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        """Record string constants that look like identifiers."""
        if isinstance(node.value, str) and node.value.isidentifier():
            self.names.add(node.value)
