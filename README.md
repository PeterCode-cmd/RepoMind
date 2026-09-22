# RepoMind

> Local-first code intelligence for Python repositories: deep static analysis, repository health and risk hotspots — with an optional LLM layer on top.

[![CI](https://github.com/repomind/repomind/actions/workflows/ci.yml/badge.svg)](https://github.com/repomind/repomind/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

RepoMind answers one question: **where should a team spend its refactoring budget?**

It parses a Python repository, builds a module dependency graph, computes complexity
metrics, finds dead code, and correlates everything with Git churn to rank the
highest-risk parts of the codebase. The result is a health score, a ranked list of
explainable findings, and shareable Markdown/JSON reports.

- **Deterministic first** — the entire analysis works offline, with no API keys and no LLM.
- **Explainable** — every finding carries the measured values and thresholds that produced it.
- **Fast** — pure AST analysis plus a linear-time dependency graph; no code is executed.
- **Extensible** — rules, parsers and reporters are separate layers with stable contracts.
- **Local-first** — your code never leaves your machine unless you explicitly opt into a cloud model.

## Features

| Area | What RepoMind detects |
| --- | --- |
| Complexity | cyclomatic complexity, cognitive complexity, deep nesting |
| Maintainability | long functions, wide parameter lists, oversized files |
| Design | god objects (method count, class size, weighted methods per class) |
| Dead code | unused imports, unreferenced private functions and methods |
| Dependencies | import cycles (strongly connected components), external package usage, hub modules |
| History | churn per file, authors, recency, and **complexity × churn hotspots** |
| Correctness | files that fail to parse |

Reports: rich terminal output, Markdown for pull requests, JSON for automation
(`--fail-under` turns RepoMind into a CI quality gate).

## Quick start

Requires Python 3.12+.

```console
# with uv (recommended)
uv venv
uv pip install -e .

# or with pip
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS
pip install -e .
```

Analyze a repository:

```console
repomind analyze /path/to/repository
```

```text
╭──────────────────────────────── RepoMind ─────────────────────────────────╮
│ Repository   /home/dev/RepoMind                                           │
│ Python code  45 files | 3,235 source lines                                │
│ Duration     0.49 s                                                       │
│ Git history  analyzed                                                     │
╰───────────────────────────────────────────────────────────────────────────╯

████████░░  86/100 | grade B

Severity                          Category
 Level     Count                    Group           Count
 HIGH          3                    complexity         18
 MEDIUM       21                    dead-code           1
 LOW           1                    history             2
                                   maintainability     4

Top findings (6 of 25)
 Severity   Rule                                 Location                            Message
 HIGH       maintainability/too-many-parameters  src/repomind/cli/app.py:82          `repomind.cli.app.analyze` takes 9 parameters
 HIGH       complexity/high-cognitive-complexity src/repomind/core/complexity.py:144 `repomind.core.complexity._max_depth` has cognitive
                                                                                    complexity 26 (warn >= 15).
 HIGH       complexity/high-cyclomatic-comple... src/repomind/git/history.py:90      `repomind.git.history.analyze_history` has
                                                                                    cyclomatic complexity 16 (warn >= 10).
 ...

Dependency graph
 Metric            Value
 Internal modules     45
 Internal imports    100
 Import cycles         0
 External packages    23

Change hotspots (last 6 commits on master)
 File                               Commits   Churn   Authors   Last change   Heat
 src/repomind/core/complexity.py          6     187         1   2026-09-22     100
 src/repomind/core/pyparser.py            1     347         1   2026-09-22      66
 src/repomind/cli/app.py                  1     280         1   2026-09-22      53

Tip: use --format markdown --output report.md for a shareable report or --format json for machine-readable output.
```

Output above is trimmed and uncolored; borders and the score bar adapt to your
terminal's encoding.

Generate shareable reports:

```console
repomind analyze . --format markdown --output report.md
repomind analyze . --format json --output report.json
repomind analyze . --min-severity high --top 10
repomind analyze . --exclude migrations --exclude "*_pb2.py"
repomind analyze . --fail-under 70     # exit code 1 when the score drops
repomind rules                          # list every built-in rule
```

Useful flags:

| Flag | Description |
| --- | --- |
| `-f, --format` | `terminal` (default), `markdown` or `json` |
| `-o, --output` | write markdown/JSON to a file instead of stdout |
| `--min-severity` | hide findings below `info`, `low`, `medium`, `high` or `critical` |
| `--top` | number of findings shown in the report |
| `--history/--no-history` | force Git history analysis on/off (default: auto) |
| `-x, --exclude` | glob pattern to skip; repeatable, matches any path segment |
| `--config` | explicit configuration file |
| `--fail-under` | CI gate: exit code 1 below the given health score |

## Configuration

Drop a `repomind.toml` at the repository root, or use `[tool.repomind]` in
`pyproject.toml`:

```toml
[tool.repomind]
exclude = ["migrations", "*/generated/*"]
use_git_history = true
history_commits = 500

[tool.repomind.thresholds]
cyclomatic_warn = 10
cyclomatic_high = 15
cyclomatic_critical = 20
function_length_warn = 60
god_object_methods = 15
hotspot_min_commits = 5
```

Unknown keys are rejected loudly, so typos never silently change your analysis.

## How the health score works

1. Every finding adds penalty points: `critical 8`, `high 4`, `medium 1.5`, `low 0.5`, `info 0.1`.
2. The penalty is normalised per 100 source lines: `density = penalty / (loc / 100)`.
3. `score = 100 - density × 10` (clamped to 0–100), grade `A` < 1.0, `B` < 2.0, `C` < 4.0, `D` < 7.0, else `F`.

Size normalisation keeps large legacy repositories from being punished for their
sheer size; the score measures *density* of problems, not their absolute count.

## Architecture

```text
repomind/
├── src/repomind/
│   ├── cli/           # Typer + Rich command line interface
│   ├── core/          # discovery, AST parser, complexity, graph, rules, engine
│   │   └── rules/     # one module per rule family, registered in default_rules()
│   ├── git/           # history analysis: churn, authors, hotspots
│   ├── models/        # shared dataclasses: findings, metrics, enums
│   ├── reporters/     # terminal, Markdown and JSON renderers
│   ├── semantic/      # (roadmap) embeddings + local vector search
│   ├── agents/        # (roadmap) LLM agents fed with prepared metrics
│   └── dashboard/     # (roadmap) Streamlit dashboard
├── tests/
│   └── fixtures/sample_project/   # deliberately flawed package used by tests
├── docs/
├── pyproject.toml
└── README.md
```

Pipeline: `discover → parse → graph → history → rules → score → report`.
Rules never read files: they consume prepared metrics, graphs and history, which
keeps them fast, deterministic and easy to test. See
[docs/architecture.md](docs/architecture.md) for details and extension guides.

## Roadmap

- [x] MVP: CLI, static analysis, dependency graph, terminal + Markdown reports
- [x] Git history analysis with complexity × churn hotspots
- [x] JSON output and `--fail-under` CI gate
- [ ] Semantic layer: local embeddings + natural-language questions about the code
- [ ] Agent layer: Architect / Quality / Security / Maintainability / Documentation
- [ ] Streamlit dashboard
- [ ] GitHub URL input (clone + analyze) and PR comment bot
- [ ] Additional languages (tree-sitter based)

## Development

```console
uv pip install -e ".[dev]"

ruff format .          # formatting
ruff check .           # linting
mypy                   # strict type checking
pytest --cov           # tests + coverage
pre-commit install     # optional: run checks on every commit
```

The test suite includes a deliberately flawed sample project
(`tests/fixtures/sample_project`) that exercises every built-in rule, plus
temporary Git repositories for history analysis.

## Contributing

Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Good first
issues: new rules, new reporters, language support, and the roadmap items above.

## License

MIT — see [LICENSE](LICENSE).
