# Architecture

RepoMind is built as a pipeline of small, replaceable stages. Every stage has a
typed contract and can be tested in isolation; nothing in the core layer imports
the CLI, and nothing in the rule layer reads files.

```text
             ┌───────────┐   ┌───────┐   ┌───────┐   ┌─────────┐   ┌───────┐   ┌────────┐
 input ────▶ │ discovery │──▶│ parse │──▶│ graph │──▶│ history │──▶│ rules │──▶│ report │
             └───────────┘   └───────┘   └───────┘   └─────────┘   └───────┘   └────────┘
```

## Pipeline stages

| Stage | Module | Responsibility |
| --- | --- | --- |
| Discovery | `core/discovery.py` | Find `.py` files. Inside a Git repository it delegates to `git ls-files`, so `.gitignore` is respected for free; otherwise it walks the tree while skipping caches, virtualenvs and hidden directories. |
| Parsing | `core/pyparser.py` | The only module that touches `ast`. Produces `ParsedModule` objects: functions, classes, imports, references, LOC, `__all__`, and syntax errors (captured, never raised). |
| Complexity | `core/complexity.py` | Cyclomatic complexity (McCabe-style), Sonar-inspired cognitive complexity and maximum nesting depth. Nested functions are measured separately. |
| Graph | `core/graph.py` | Directed module graph from import statements. Relative imports are resolved against the package of the importing module. Cycles are strongly connected components. |
| History | `git/history.py` | Walks up to N commits, accumulating per-file commits, churn, authors and recency. Returns `None` outside Git repositories. |
| Rules | `core/rules/` | Each rule is a small class satisfying the `Rule` protocol and receiving an `AnalysisContext`. Rule failures are isolated and reported as warnings. |
| Scoring | `core/scoring.py` | Converts findings into a size-normalised 0–100 health score with a letter grade. |
| Reporting | `reporters/` | Terminal (Rich), Markdown and JSON renderers. All three consume the same `AnalysisResult`. |
| CLI | `cli/app.py` | Typer commands (`analyze`, `rules`), progress rendering, exit codes. |

## Why these design decisions

**Deterministic first.** The static analysis is complete on its own. LLM features
(semantic search, agents) are additive layers that consume the same artifacts;
they can never be required for the tool to work, which keeps RepoMind useful
offline and in CI.

**Rules consume prepared data.** A rule receives metrics, graphs and history —
not source files. This makes rules trivial to unit-test (construct a context,
assert findings) and guarantees consistent numbers across rules and reports.

**Severity is explicit, thresholds are configurable.** Every finding records the
measured value and the thresholds that produced its severity, so "why is this
critical?" is always answerable from the report itself.

**Heuristic transparency.** Dead-code detection is reference-based: a name counts
as used if it appears as a loaded name, an attribute access or an
identifier-like string constant anywhere in the analyzed code. This
deliberately trades a few false negatives (e.g. purely recursive private
functions) for very few false positives.

**Windows-first tolerance.** Source files are read with `tokenize.open` (PEP 263
encoding cookies and BOMs are handled), paths are compared after `resolve()`,
and reports avoid terminal-width assumptions.

## Adding a rule

1. Create a class in the right module under `core/rules/` (or a new module for a
   new family).
2. Implement the `Rule` protocol: `id`, `title`, `description`, `category` and
   `analyze(context) -> list[Finding]`.
3. Register an instance in `default_rules()` in `core/rules/__init__.py`.
4. Add a test using the sample project or a temporary repository.

Findings should include the measured values in `details` and a concrete
`suggestion`. Keep messages stable — reports and tests depend on them.

## Adding a language (roadmap)

`ParsedModule` is language-neutral. A new parser only needs to produce the same
dataclasses (`FunctionMetrics`, `ClassMetrics`, `ImportInfo`, references), after
which every rule, the graph, the scoring and all reporters work unchanged. The
planned implementation uses `tree-sitter` behind a `Parser` protocol, with the
Python AST parser as the reference implementation.

## Scoring formula

```text
penalty  = Σ severity weights (critical 8, high 4, medium 1.5, low 0.5, info 0.1)
density  = penalty / max(1, loc / 100)
score    = clamp(100 - density × 10, 0, 100)
grade    = A (< 1.0), B (< 2.0), C (< 4.0), D (< 7.0), F otherwise
```

The formula is intentionally simple and documented: a repository with one
`critical` finding per 1000 source lines loses about 8 points.

## Known limitations

- Python only (for now); dynamic dispatch, `getattr` with computed names and
  plugin registries can hide usage from the dead-code rule.
- Import resolution is best-effort: modules outside the analyzed root are
  reported as external packages rather than resolved.
- History analysis reads at most `history_commits` commits (default 500) for
  predictable runtime on large repositories.
