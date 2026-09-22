"""Tests for AST-aware code chunking."""

from __future__ import annotations

from pathlib import Path

from repomind.core.discovery import find_python_files
from repomind.core.pyparser import parse_module
from repomind.semantic.chunking import CodeChunk, build_chunks


def _chunks(sample_project: Path) -> list[CodeChunk]:
    modules = [parse_module(path, sample_project) for path in find_python_files(sample_project)]
    return build_chunks(modules)


def test_chunk_kinds_cover_every_definition(sample_project: Path) -> None:
    chunks = _chunks(sample_project)
    assert {"module", "class", "function", "method"} <= {chunk.kind for chunk in chunks}


def test_function_chunk_contains_its_source(sample_project: Path) -> None:
    tangled = next(
        chunk
        for chunk in _chunks(sample_project)
        if chunk.symbol == "samplepkg.complex.tangled_branches"
    )

    assert tangled.kind == "function"
    assert "def tangled_branches" in tangled.text
    assert tangled.end_lineno > tangled.lineno


def test_class_and_method_chunks_are_built(sample_project: Path) -> None:
    chunks = _chunks(sample_project)

    god = next(chunk for chunk in chunks if chunk.symbol == "samplepkg.god.GodClass")
    assert god.kind == "class"
    assert "class GodClass" in god.text

    method = next(chunk for chunk in chunks if chunk.symbol == "samplepkg.god.GodClass.step_01")
    assert method.kind == "method"


def test_chunk_ids_are_stable(sample_project: Path) -> None:
    first = [chunk.chunk_id for chunk in _chunks(sample_project)]
    second = [chunk.chunk_id for chunk in _chunks(sample_project)]

    assert first == second
    assert len(set(first)) == len(first)


def test_unparsable_modules_are_skipped(sample_project: Path) -> None:
    chunks = _chunks(sample_project)
    assert all(chunk.path != "samplepkg/broken.py" for chunk in chunks)


def test_module_chunk_is_a_preview(sample_project: Path) -> None:
    module_chunk = next(
        chunk
        for chunk in _chunks(sample_project)
        if chunk.kind == "module" and chunk.path == "samplepkg/a.py"
    )

    assert module_chunk.end_lineno <= 20
    assert "from .b import beta" in module_chunk.text
    assert module_chunk.location == "samplepkg/a.py:1"
