# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-09-22

### Fixed

- Parsing a repository no longer floods the terminal with `SyntaxWarning`s
  raised by analyzed files, such as test fixtures with invalid escape
  sequences (both `ast.parse` and the tokenizer were affected).
- Transient LLM provider failures (rate limits, 5xx) are retried twice with
  backoff before the deterministic fallback kicks in.
- The `llm` extra now includes `tenacity`, which litellm requires for the
  retry path; without it model calls failed with an import error and silently
  fell back to the deterministic summary.
- litellm's feedback banner no longer leaks to stderr when a retry succeeds
  after a transient provider failure.
- The review prompt now ranks by risk (using `callers` and `churn` when
  present), asks the model to report generated, vendored or benchmark data as
  such instead of treating it as review-worthy code, and merges findings that
  concern the same symbol into a single item.

### Added

- Six security rules (`security/*`) backed by AST signal extraction: dynamic
  execution, shell execution, unsafe deserialization, weak hashes, insecure
  temporary files and hardcoded secrets. Import aliases are resolved and secret
  values are never copied into findings.
- A documentation rule (`documentation/missing-docstring`) for public modules,
  classes, functions and methods, with private names, framework hooks and test
  modules exempt.
- Function-level churn via `git log -L` for the hottest files
  (`blame_files`, default 10): hotspot findings now use a function's own commit
  history, authors and recency, and fall back to file churn when unavailable.
- A function-level call graph (`core/callgraph.py`) resolving local, method,
  constructor and imported call targets; findings gain a `callers` count and
  reports list the most-called functions.
- Class cohesion via LCOM4 (`core/cohesion.py`) with a `design/low-cohesion`
  rule, plus afferent/efferent coupling and instability per module in reports.
- `repomind trend`: health score across sampled commits, each analyzed in a
  detached Git worktree, with terminal, Markdown and JSON output.
- `repomind search`: dependency-free lexical search over AST-aware chunks
  (modules, classes, functions, methods) with BM25 ranking, snake_case and
  camelCase aware tokenization, and JSON output for automation.
- Semantic search: pluggable embeddings (`fastembed` ONNX locally, or any
  embedding API through litellm with a key from the environment), an
  incremental local index under `.repomind/` that re-embeds only changed
  chunks and invalidates itself on model changes, `repomind index`, and
  `repomind search --mode semantic`. Configuration via `[semantic]`.
- `repomind explain` and `repomind review`: optional LLM agents that consume
  the prepared findings (metrics, caller counts, churn) and never raw source.
  Ollama is the default backend, cloud providers work through litellm with an
  API key from the environment, and every command degrades to a deterministic
  summary without the `llm` extra. Model answers are validated and citations
  outside the context are dropped. Configuration via `[llm]` (`model`,
  `timeout`, `max_findings`); API keys are rejected in configuration files.

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

[Unreleased]: https://github.com/PeterCode-cmd/RepoMind/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/PeterCode-cmd/RepoMind/releases/tag/v0.2.0
[0.1.0]: https://github.com/PeterCode-cmd/RepoMind/releases/tag/v0.1.0
