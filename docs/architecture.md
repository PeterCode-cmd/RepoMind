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
| Discovery | `core/discovery.py` | Find `.py` files. Inside a Git repository it delegates to `git ls-files`, so `.gitignore` is respected for free; otherwise it walks the tree while skipping caches, virtualenvs and hidden directories. In diff mode the discovered set is intersected with the changed paths. |
| Parsing | `core/pyparser.py` | The only module that touches `ast`. Produces `ParsedModule` objects: functions, classes, imports, references, LOC, `__all__`, and syntax errors (captured, never raised). |
| Signals | `core/signals.py` | Import-alias-aware extraction of security-relevant AST patterns (dynamic execution, shell usage, unsafe deserialization, weak hashes, insecure temp files, hardcoded secrets) so security rules stay AST-free. Secret values are never recorded. |
| Complexity | `core/complexity.py` | Cyclomatic complexity (McCabe-style), Sonar-inspired cognitive complexity and maximum nesting depth. Nested functions are measured separately. |
| Graph | `core/graph.py` | Directed module graph from import statements. Relative imports are resolved against the package of the importing module. Cycles are strongly connected components. Afferent/efferent coupling and instability (`Ce / (Ca + Ce)`) are derived from the same graph. |
| Call graph | `core/callgraph.py` | Resolves the call names recorded by the parser to analyzed functions (local names, `self.method`, constructor calls and imported targets) and powers the `callers` count attached to findings. |
| Cohesion | `core/cohesion.py` | LCOM4 per class: methods linked by shared `self.<name>` state or direct calls form connected components. Dunder and stub methods are excluded so constructors and protocol members do not distort the result. |
| Trend | `core/trend.py` | Samples commits and analyzes each snapshot in a detached Git worktree with the current configuration; history and blame are skipped per sample so the trend is comparable and cheap. |
| History | `git/history.py` | Walks up to N commits, accumulating per-file commits, churn, authors and recency. Returns `None` outside Git repositories. |
| Blame | `git/blame.py` | Tracks the most complex functions of the hottest files with `git log -L`, giving true per-function commit counts, authors and recency. Bounded by `blame_files` (default 10) because line-range walks dominate the cost of the stage. |
| Diff | `git/diff.py` | Resolves `--since <rev>` to the set of changed Python files (committed, staged, unstaged and untracked), which the engine turns into an analysis scope. |
| Rules | `core/rules/` | Each rule is a small class satisfying the `Rule` protocol and receiving an `AnalysisContext`. Rule failures are isolated and reported as warnings. |
| Suppression | `core/suppression.py` | Applies configured `ignore` entries after rules and before scoring. Suppressed findings stay visible as a count (and in full in JSON). |
| Baseline | `core/baseline.py` | Splits findings into known/new against accepted fingerprints, powering `--fail-on-new` for legacy adoption. |
| Scoring | `core/scoring.py` | Converts findings into a size-normalised 0–100 health score with a letter grade. |
| Reporting | `reporters/` | Terminal (Rich), Markdown, JSON, SARIF 2.1.0 and self-contained HTML renderers. All consume the same `AnalysisResult`; SARIF carries baseline fingerprints as `partialFingerprints` for code-scanning alert tracking. |
| CLI | `cli/app.py`, `cli/analyze.py` | Typer commands (`analyze`, `rules`), progress rendering, exit codes. |

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

## Suppression and decorator exemptions

Two escape hatches keep the analysis actionable without hiding anything:

- **`ignore` entries** (`rule-id` or `rule-id@glob`) remove findings from
  scoring and from the main report. Suppressed findings are always counted in
  terminal/Markdown output and listed in full in the JSON output, so a
  suppression can never silently swallow a regression. Entries referencing an
  unknown rule produce a warning instead of failing the run.
- **Decorated private definitions** are exempt from the dead-code rule.
  Decorators register callables with frameworks (Typer commands, pytest
  fixtures, event handlers), so the code never references them by name; without
  the exemption every framework entry point would be a false positive. The
  tradeoff is that genuinely dead decorated helpers are not reported.

Both behaviours are exercised by RepoMind itself: `repomind.toml` excludes the
intentionally broken test fixtures and suppresses the CLI declaration-surface
findings for `src/repomind/cli/*.py` with an inline justification.

## Baseline and incremental adoption

`core/baseline.py` implements the second escape hatch: a baseline file with one
fingerprint per accepted finding. Fingerprints hash `rule_id`, `path` and
`symbol` only — never line numbers or measured values — so refactoring a known
issue does not resurrect it, while a genuinely new issue always fails the gate.
The engine splits findings into known/new after suppression and before scoring;
reporters surface both counts, and the Markdown report gets a dedicated
"New findings" section for pull-request review.

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
  plugin registries can hide usage from the dead-code rule. Decorated private
  definitions are exempt from dead-code analysis (see above).
- Import resolution is best-effort: modules outside the analyzed root are
  reported as external packages rather than resolved.
- History analysis reads at most `history_commits` commits (default 500) for
  predictable runtime on large repositories.
- `ignore` entries are exact rule ids plus path globs; there is no severity
  override or inline `# noqa`-style pragma yet (planned alongside the baseline
  and diff features).
