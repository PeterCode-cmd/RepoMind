"""Size, complexity and structure metrics extracted from Python modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class FunctionMetrics:
    """Metrics for a single function or method definition."""

    name: str
    qualname: str
    lineno: int
    end_lineno: int
    length: int
    parameters: int
    cyclomatic: int
    cognitive: int
    nesting_depth: int
    is_method: bool = False
    class_name: str | None = None
    decorators: tuple[str, ...] = ()
    calls: tuple[str, ...] = ()
    attributes: tuple[str, ...] = ()
    is_stub: bool = False
    has_docstring: bool = False

    @property
    def is_private(self) -> bool:
        """Return ``True`` for private (single underscore) names."""
        return self.name.startswith("_") and not self.name.startswith("__")

    @property
    def is_decorated(self) -> bool:
        """Return ``True`` when the definition carries at least one decorator."""
        return bool(self.decorators)


@dataclass(slots=True)
class ClassMetrics:
    """Metrics for a class definition, including its methods."""

    name: str
    lineno: int
    end_lineno: int
    length: int
    methods: list[FunctionMetrics] = field(default_factory=list)
    attribute_count: int = 0
    base_count: int = 0
    lcom: int = 0
    has_docstring: bool = False

    @property
    def method_count(self) -> int:
        """Return the total number of methods, including dunder methods."""
        return len(self.methods)

    @property
    def public_method_count(self) -> int:
        """Return the number of non-dunder methods."""
        return sum(1 for method in self.methods if not method.name.startswith("__"))

    @property
    def wmc(self) -> int:
        """Return the Weighted Methods per Class (sum of method complexity)."""
        return sum(method.cyclomatic for method in self.methods)


@dataclass(frozen=True, slots=True)
class ImportInfo:
    """A single ``import`` or ``from ... import`` binding."""

    module: str
    name: str | None
    alias: str | None
    lineno: int
    is_from: bool
    level: int = 0

    @property
    def bound_name(self) -> str | None:
        """Return the local name introduced by the import, if any."""
        if self.name is None:
            if self.module:
                return self.alias or self.module.split(".")[0]
            return None
        if self.name == "*":
            return None
        return self.alias or self.name

    @property
    def is_reexport(self) -> bool:
        """Return ``True`` for explicit re-exports such as ``from x import y as y``."""
        if self.alias is None:
            return False
        return self.name is None or self.alias == self.name

    @property
    def display(self) -> str:
        """Return a readable representation of the imported symbol."""
        if self.is_from:
            prefix = "." * self.level + self.module
            return f"from {prefix} import {self.name}"
        return f"import {self.module}"


@dataclass(frozen=True, slots=True)
class SecuritySignal:
    """A security-relevant pattern found while parsing a module.

    Signals are extracted by the parser so that security rules never need to
    touch the AST themselves. ``detail`` is safe to display: it never contains
    the value of a detected secret.
    """

    kind: str
    lineno: int
    detail: str


@dataclass(slots=True)
class ParsedModule:
    """Everything RepoMind knows about a single Python source file."""

    path: Path
    rel_path: str
    module_name: str
    total_lines: int
    loc: int
    functions: list[FunctionMetrics] = field(default_factory=list)
    classes: list[ClassMetrics] = field(default_factory=list)
    imports: list[ImportInfo] = field(default_factory=list)
    unused_imports: list[ImportInfo] = field(default_factory=list)
    security_signals: list[SecuritySignal] = field(default_factory=list)
    all_exports: frozenset[str] = frozenset()
    references: frozenset[str] = frozenset()
    has_docstring: bool = False
    syntax_error: str | None = None

    @property
    def is_package(self) -> bool:
        """Return ``True`` when the module is a package ``__init__.py``."""
        return self.rel_path.endswith("__init__.py")

    @property
    def all_functions(self) -> list[FunctionMetrics]:
        """Return every function and method defined in the module."""
        methods = [method for cls in self.classes for method in cls.methods]
        return [*self.functions, *methods]
