# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Six security rules (`security/*`) backed by AST signal extraction: dynamic
  execution, shell execution, unsafe deserialization, weak hashes, insecure
  temporary files and hardcoded secrets. Import aliases are resolved and secret
  values are never copied into findings.
- A documentation rule (`documentation/missing-docstring`) for public modules,
  classes, functions and methods, with private names, framework hooks and test
  modules exempt.

## [0.1.0] - 2026-09-22

### Added

- CLI (`repomind analyze`, `repomind baseline`, `repomind rules`) built with
  Typer and Rich, with progress rendering and CI-friendly exit codes.
- Deterministic static analysis for Python: cyclomatic complexity, cognitive
  complexity, nesting depth, function, parameter and file size metrics.
- Module dependency graph with import-cycle detection (strongly connected
  components), fan-in/fan-out statistics and DOT export.
- Git history analysis: per-file churn, authors, recency and
  complexity x churn hotspots.
- Twelve built-in rules across complexity, maintainability, design, dead code,
  dependencies, correctness and history.
- Reports in five formats: terminal, Markdown, JSON, SARIF 2.1.0 and a
  self-contained HTML report with severity filtering.
- Baseline support (`.repomind-baseline.json`) with `--fail-on-new` for
  incremental adoption in legacy repositories.
- Diff mode (`--since <rev>`) for pull-request style reviews.
- Configuration via `repomind.toml` or `[tool.repomind]`: excludes, per-rule
  `ignore` entries, thresholds and history window.
- Decorator-aware dead-code detection: framework entry points (CLI commands,
  pytest fixtures, handlers) are exempt from false positives.
- Size-normalised health score (0-100) with letter grades.
- Composite GitHub Action with SARIF upload to GitHub code scanning.
- CI (ruff, mypy strict, pytest with coverage, self-analysis gate),
  pre-commit hooks and a release workflow with PyPI trusted publishing.
- Benchmarks against requests, flask, tqdm and black, with methodology and
  limitations (`docs/benchmarks.md`).

### Changed

- The PyPI distribution is named `repomind-analyzer` (the plain `repomind`
  name is taken by an unrelated project); the import package and the CLI
  command remain `repomind`.
- Project metadata, SARIF `informationUri` and documentation links point at
  the real repository.

[Unreleased]: https://github.com/PeterCode-cmd/RepoMind/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/PeterCode-cmd/RepoMind/releases/tag/v0.1.0
