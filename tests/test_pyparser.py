"""Tests for the AST parser."""

from __future__ import annotations

from pathlib import Path

from repomind.core.pyparser import parse_module


def test_parse_module_extracts_definitions(sample_project: Path) -> None:
    module = parse_module(sample_project / "samplepkg" / "dead.py", sample_project)

    assert module.module_name == "samplepkg.dead"
    assert module.rel_path == "samplepkg/dead.py"
    assert module.syntax_error is None
    assert module.total_lines > 0
    assert module.loc > 0
    names = {function.name for function in module.functions}
    assert {"public_api", "_used_helper", "_never_used"} <= names


def test_unused_imports_are_detected(sample_project: Path) -> None:
    module = parse_module(sample_project / "samplepkg" / "dead.py", sample_project)
    assert {item.bound_name for item in module.unused_imports} == {"json", "Counter"}


def test_used_imports_are_not_reported(sample_project: Path) -> None:
    module = parse_module(sample_project / "samplepkg" / "a.py", sample_project)
    assert module.unused_imports == []


def test_reexports_are_not_reported(sample_project: Path) -> None:
    module = parse_module(sample_project / "samplepkg" / "__init__.py", sample_project)
    assert module.unused_imports == []
    assert module.all_exports == frozenset({"alpha"})
    assert module.is_package


def test_methods_and_wmc(sample_project: Path) -> None:
    module = parse_module(sample_project / "samplepkg" / "god.py", sample_project)
    god = next(cls for cls in module.classes if cls.name == "GodClass")

    assert god.public_method_count == 16
    assert god.method_count == 17
    assert god.wmc >= god.method_count
    assert god.attribute_count == 2
    assert module.all_functions


def test_parameters_exclude_self(sample_project: Path) -> None:
    module = parse_module(sample_project / "samplepkg" / "god.py", sample_project)
    god = next(cls for cls in module.classes if cls.name == "GodClass")
    init = next(method for method in god.methods if method.name == "__init__")
    assert init.parameters == 0
    assert init.is_method


def test_syntax_errors_are_captured(sample_project: Path) -> None:
    module = parse_module(sample_project / "samplepkg" / "broken.py", sample_project)
    assert module.syntax_error is not None
    assert module.functions == []
    assert module.classes == []


def test_src_layout_strips_source_root(tmp_path: Path) -> None:
    path = tmp_path / "src" / "pkg" / "mod.py"
    path.parent.mkdir(parents=True)
    path.write_text("value = 1\n", encoding="utf-8")

    module = parse_module(path, tmp_path)

    assert module.module_name == "pkg.mod"
    assert module.rel_path == "src/pkg/mod.py"


def test_decorators_are_recorded(tmp_path: Path) -> None:
    path = tmp_path / "mod.py"
    path.write_text(
        "import functools\n"
        "\n"
        "\n"
        "@functools.cache\n"
        "def cached() -> int:\n"
        "    return 1\n"
        "\n"
        "\n"
        "class Service:\n"
        "    @staticmethod\n"
        "    def build(alpha: int, beta: int) -> int:\n"
        "        return alpha + beta\n",
        encoding="utf-8",
    )

    module = parse_module(path, tmp_path)
    cached = module.functions[0]
    build = module.classes[0].methods[0]

    assert cached.decorators == ("cache",)
    assert cached.is_decorated
    assert build.decorators == ("staticmethod",)
    assert build.parameters == 2


def test_undecorated_functions_report_no_decorators(sample_project: Path) -> None:
    module = parse_module(sample_project / "samplepkg" / "dead.py", sample_project)
    assert all(not function.is_decorated for function in module.functions)
