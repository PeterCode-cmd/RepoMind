# RepoMind

> Local-first code intelligence for Python repositories: deep static analysis, repository health and risk hotspots — with an optional AI layer on top.

[![CI](https://github.com/PeterCode-cmd/RepoMind/actions/workflows/ci.yml/badge.svg)](https://github.com/PeterCode-cmd/RepoMind/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/repomind-analyzer.svg)](https://pypi.org/project/repomind-analyzer/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

RepoMind answers one question: **where should a team spend its refactoring budget?**

It parses a Python repository, builds a module dependency graph and a function-level
call graph, computes complexity, cohesion and coupling metrics, finds dead code and
security-relevant patterns, and correlates everything with Git churn to rank the
highest-risk parts of the codebase. The result is a health score, a ranked list of
explainable findings, and shareable reports.

- **Deterministic first** — the whole analysis works offline, with no API keys and no LLM.
- **Explainable** — every finding carries the measured values and thresholds that produced it.
- **Fast** — pure AST analysis plus linear-time graphs; no analyzed code is ever executed.
- **Local-first** — your code never leaves your machine unless you explicitly opt into a cloud model.
- **Extensible** — rules, parsers and reporters are separate layers with stable contracts.

## Features

| Area | What RepoMind detects |
| --- | --- |
| Complexity | cyclomatic complexity, cognitive complexity, deep nesting |
| Maintainability | long functions, wide parameter lists, oversized files |
| Design | god objects (method count, class size, WMC), low class cohesion (LCOM4) |
| Dead code | unused imports, unreferenced private functions and methods |
| Dependencies | import cycles (strongly connected components), external packages, hub modules |
| Call graph | function-level call edges; caller counts attached to findings, fan-in leaders in reports |
| Cohesion & coupling | LCOM4 per class; afferent/efferent coupling and instability per module |
| Security | `eval`/`exec`, `shell=True` and `os.system`, unsafe pickle/YAML deserialization, weak hashes, `tempfile.mktemp`, hardcoded secrets (values never reported) |
| Documentation | missing docstrings on public modules, classes, functions and methods |
| History | churn per file and per function (`git log -L`), authors, recency, **complexity × churn hotspots** |
| Correctness | files that fail to parse |

**20 built-in rules** across 9 categories — list them with `repomind rules`.
Reports come in five formats: terminal, Markdown, JSON, SARIF 2.1.0 and a
self-contained HTML file. `--fail-under` and `--fail-on-new` turn RepoMind into
a CI quality gate.

## Install

Requires **Python 3.12+**. The PyPI distribution is called `repomind-analyzer`
(the plain `repomind` name is taken by an unrelated project); it provides the
`repomind` command.

```console
pipx install repomind-analyzer            # core: no AI dependencies at all
```

Optional layers are installed through extras — the base install never pulls a
model runtime:

| Extra | Adds | Enables |
| --- | --- | --- |
| *(none)* | — | static analysis, history, reports, lexical search, `trend`, `baseline`, `doctor` |
| `semantic` | fastembed (ONNX), numpy | `repomind index`, `search --mode semantic` |
| `llm` | litellm, tenacity | `repomind explain`, `repomind review` (Ollama or cloud models) |

```console
pipx install "repomind-analyzer[semantic]"           # local embeddings
pipx install "repomind-analyzer[llm]"                # agents
pipx install "repomind-analyzer[semantic,llm]"       # both
```

With plain pip, inside a virtual environment:

```console
pip install "repomind-analyzer[llm]"
```

From source (for contributors):

```console
git clone https://github.com/PeterCode-cmd/RepoMind.git
cd RepoMind
uv venv
uv pip install -e ".[dev]"
```

## Quick start

```console
repomind analyze /path/to/repository
```

```text
╭──────────────────────────────── RepoMind ─────────────────────────────────╮
│ Repository   /home/dev/RepoMind                                           │
│ Python code  88 files | 8,027 source lines                                │
│ Duration     3.93 s                                                       │
│ Git history  analyzed                                                     │
╰───────────────────────────────────────────────────────────────────────────╯

██████████  100/100 | grade A

No findings above the configured thresholds.
7 finding(s) suppressed by configuration (details in --format json).

Dependency graph
 Metric            Value
 Internal modules     88
 Internal imports    265
 Import cycles         0
 External packages    26

Call graph: 572 functions, 648 call edges
 fan-in repomind.core.engine.analyze_repository (33 callers)
 fan-in repomind.config.load_config (22 callers)
 fan-in repomind.core.pyparser.parse_module (21 callers)
Most unstable modules: repomind.__main__ (1.00), repomind.agents (1.00), repomind.git (1.00)

Change hotspots (last 22 commits on master)
 File                              Commits   Churn   Authors   Last change   Heat
 src/repomind/core/engine.py             8     584         1   2026-09-22     100
 src/repomind/core/pyparser.py           7     478         1   2026-09-22      78
 src/repomind/cli/app.py                 4     504         1   2026-09-22      63

Tip: use --format markdown --output report.md for a shareable report or --format json for machine-readable output.
```

Output above is trimmed and uncolored; borders and the score bar adapt to your
terminal's encoding. The suppressed entries are deliberate and explained in
[Dogfooding](#dogfooding). A full HTML report generated from the deliberately
flawed sample project is checked in at
[docs/example-report.html](docs/example-report.html).

## Commands

| Command | What it does | Needs |
| --- | --- | --- |
| `repomind analyze [PATH]` | full static analysis, health score, reports | nothing |
| `repomind baseline [PATH]` | accept current findings into `.repomind-baseline.json` | nothing |
| `repomind trend [PATH]` | health score across sampled commits (each in a Git worktree) | nothing |
| `repomind search "query" [PATH]` | lexical (BM25) code search over AST-aware chunks | nothing |
| `repomind search "query" --mode semantic` | embedding-based search | `[semantic]` extra + `repomind index` |
| `repomind index [PATH]` | build/refresh the local semantic index (incremental) | `[semantic]` extra |
| `repomind explain "rule-id@path:line"` | explain one finding with an LLM (facts-only, citations validated) | `[llm]` extra + a model |
| `repomind review [PATH] [--since REV]` | prioritised review of findings, optionally only changed files | `[llm]` extra + a model |
| `repomind doctor [PATH]` | check Python, Git, extras, index and model availability | nothing |
| `repomind rules` | list every built-in rule | nothing |

Every command has `--help`; `--no-llm` forces deterministic output for the
agent commands.

## Reports and formats

```console
repomind analyze . --format markdown --output report.md
repomind analyze . --format json --output report.json
repomind analyze . --format sarif --output repomind.sarif    # GitHub code scanning
repomind analyze . --format html --output report.html        # self-contained
repomind analyze . --min-severity high --top 10
repomind analyze . --exclude migrations --exclude "*_pb2.py"
repomind analyze . --since main         # review only files changed since main
repomind analyze . --fail-under 70      # exit code 1 when the score drops
repomind trend .                        # health score across commits
repomind search "retry backoff"         # lexical search
repomind rules                          # list every built-in rule
```

Useful flags:

| Flag | Description |
| --- | --- |
| `-f, --format` | `terminal` (default), `markdown`, `json`, `sarif` or `html` |
| `-o, --output` | write markdown/JSON/SARIF/HTML to a file instead of stdout |
| `--min-severity` | hide findings below `info`, `low`, `medium`, `high` or `critical` |
| `--top` | number of findings shown in the report |
| `--history/--no-history` | force Git history analysis on/off (default: auto) |
| `-x, --exclude` | glob pattern to skip; repeatable, matches any path segment |
| `--config` | explicit configuration file |
| `--baseline` / `--no-baseline` | use or ignore a baseline file (auto-detected by default) |
| `--since` | only analyze Python files changed since a Git revision |
| `--fail-on-new` | CI gate: exit code 1 for findings not accepted by the baseline |
| `--fail-under` | CI gate: exit code 1 below the given health score |

## Semantic search

Local embeddings by default (fastembed, ONNX, no torch). Three steps:

```console
pipx install "repomind-analyzer[semantic]"   # 1. install the extra
repomind index .                             # 2. build the index (first run downloads ~130 MB model)
repomind search "how is the health score computed" --mode semantic --top 5
```

```text
Search results (5)
 Score | Kind     | Location                              | Symbol
  0.80 | function | src/repomind/core/scoring.py:46       | repomind.core.scoring.compute_health_score
  0.75 | function | src/repomind/reporters/terminal.py:88 | repomind.reporters.terminal._render_health
  0.73 | class    | src/repomind/core/scoring.py:28       | repomind.core.scoring.HealthScore
```

How the index works:

- chunks are real code units (module previews, classes, functions, methods) sliced
  by the parser's line ranges — not fixed-size text windows;
- unchanged chunks are reused by content hash, so re-indexing after an edit only
  embeds what changed (`--rebuild` forces everything);
- the index lives in `.repomind/` (add it to `.gitignore`) and validates its model
  name, so switching models invalidates it automatically;
- `--provider api` sends chunk text to your embedding provider instead (see
  [docs/ai.md](docs/ai.md)).

Configuration:

```toml
[tool.repomind.semantic]
provider = "fastembed"                  # or "api" (litellm, key from the environment)
model = "BAAI/bge-small-en-v1.5"        # e.g. "gemini/text-embedding-004" for provider = "api"
index_dir = ".repomind"
top_k = 8
min_score = 0.25
```

## AI agents: explain and review

Agents consume the **prepared facts** (findings, measured values, caller counts,
churn) — never raw source text — and their answers are validated: citations
outside the retrieved context are dropped, and every failure degrades to a
deterministic summary instead of an error.

```console
# default backend: a local Ollama model (free, private)
ollama pull qwen2.5-coder:7b
repomind explain "design/god-object@src/app/models.py:12"
repomind review . --since main --top 10

# cloud model instead: key from the environment, no config changes
export GEMINI_API_KEY=...          # Windows: $env:GEMINI_API_KEY = "..."
repomind explain "design/god-object@src/app/models.py:12" --model gemini/gemini-3.8-flash

# deterministic output, no model at all
repomind explain "design/god-object@src/app/models.py:12" --no-llm
```

Configuration:

```toml
[tool.repomind.llm]
model = "ollama/qwen2.5-coder:7b"   # or "gpt-4o-mini", "claude-3-5-haiku", "gemini/gemini-3.8-flash", ...
timeout = 60
max_findings = 20                   # context size cap for review
```

Provider details, privacy notes, cost guidance and troubleshooting live in
**[docs/ai.md](docs/ai.md)**.

## Use as a Python library

`repomind.api` is the supported public surface and follows semantic versioning;
everything else (`repomind.core`, `repomind.semantic`, ...) is internal and may
change between minor releases.

```python
from repomind import api

result = api.analyze(".")  # AnalysisResult
print(result.score.value, result.score.grade)
for finding in result.findings[:5]:
    print(finding.location, finding.message)

hits = api.search_code(".", "retry backoff")  # list[SearchHit], no extra needed
print(hits[0].chunk.symbol, hits[0].score)

stats = api.build_search_index(".", rebuild=False)  # needs the semantic extra
print(stats.chunks, stats.embedded, stats.reused)
```

The facade also re-exports `AnalysisConfig`, `AnalysisOptions`, `Baseline`,
`Severity`, `Category`, `Finding`, `SearchHit`, `CodeChunk`, `explain_finding`,
`review_findings` and the LLM client types. The CLI is built on the same
functions, so library and command line always agree.

## Adopting RepoMind in CI

Accept today's findings once, then let CI fail only on new problems:

```console
repomind baseline .                    # writes .repomind-baseline.json
repomind analyze . --fail-on-new       # exit code 1 only for new findings
```

The baseline file is plain JSON with one reviewable entry per accepted finding
(rule, path, symbol, severity). Fingerprints ignore line numbers and measured
values, so a known issue stays known when it moves or grows.

### GitHub Action

The composite action analyzes the repository, writes a SARIF report and uploads
it to GitHub code scanning, so findings appear as alerts on the pull request diff:

```yaml
name: repomind

on: [push, pull_request]

permissions:
  contents: read
  security-events: write

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: PeterCode-cmd/RepoMind@master
        with:
          fail-on-new: "true"   # optional: fail only on new findings
          fail-under: "85"      # optional: fail below this health score
```

Inputs: `path`, `fail-under`, `fail-on-new`, `baseline`, `sarif-file`,
`upload-sarif`. The action runs with `--no-history` so results stay
deterministic on shallow checkouts.

## Configuration

Drop a `repomind.toml` at the repository root, or use `[tool.repomind]` in
`pyproject.toml`:

```toml
[tool.repomind]
exclude = ["migrations", "*/generated/*"]
ignore = [
    "maintainability/too-many-parameters@src/app/cli.py",
    "dead-code/unused-import",
]
use_git_history = true
history_commits = 500
blame_files = 10          # hottest files tracked with git log -L (0 disables)

[tool.repomind.thresholds]
cyclomatic_warn = 10
cyclomatic_high = 15
cyclomatic_critical = 20
function_length_warn = 60
god_object_methods = 15
lcom_warn = 3
hotspot_min_commits = 5

[tool.repomind.semantic]
provider = "fastembed"
model = "BAAI/bge-small-en-v1.5"

[tool.repomind.llm]
model = "ollama/qwen2.5-coder:7b"
```

Unknown keys are rejected loudly, so typos never silently change your analysis
(API keys in configuration are rejected too — they belong in the environment).

`ignore` entries silence known, accepted findings: `rule-id` suppresses a rule
everywhere, `rule-id@glob` only for matching paths. Suppressed findings never
disappear silently — every report shows how many were suppressed and
`--format json` lists them in full.

## How the health score works

1. Every finding adds penalty points: `critical 8`, `high 4`, `medium 1.5`, `low 0.5`, `info 0.1`.
2. The penalty is normalised per 100 source lines: `density = penalty / (loc / 100)`.
3. `score = 100 - density × 10` (clamped to 0–100), grade `A` < 1.0, `B` < 2.0, `C` < 4.0, `D` < 7.0, else `F`.

Size normalisation keeps large legacy repositories from being punished for their
sheer size; the score measures *density* of problems, not their absolute count.

## Troubleshooting

Start with the built-in check — it reports exactly what is available and what to
do about the rest:

```console
$ repomind doctor .
Check          | Status | Detail                           | Hint
python         | OK     | 3.12.3 (>= 3.12 required)        |
configuration  | OK     | discovered or defaults           |
git repository | OK     | /home/dev/project                |
semantic extra | WARN   | missing: fastembed, numpy        | pip install "repomind-analyzer[semantic]"
llm extra      | OK     | litellm, tenacity                |
semantic index | WARN   | no index in /home/dev/project/.repomind | run 'repomind index .' to enable semantic search
ollama         | WARN   | not reachable on localhost:11434 | start it with 'ollama serve', or use --model for a cloud provider
```

| Symptom | Cause and fix |
| --- | --- |
| `the semantic extra is not installed` | `pipx install "repomind-analyzer[semantic]"` |
| `no semantic index ... run 'repomind index' first` | build the index once per repository |
| `repomind index` seems stuck on the first run | it downloads the ~130 MB embedding model to the fastembed cache; later runs are incremental |
| `model call failed: ...` note in `explain`/`review` | the model was unreachable; RepoMind already printed the deterministic fallback — start Ollama or fix the API key, or use `--no-llm` on purpose |
| Cloud model returns `503`/rate limits | transient failures are retried twice with backoff; retry later or pick another `--model` |
| Score dropped after adding `--exclude` | the score is density-based: excluding code shrinks the denominator. Keep one stable scope (in `repomind.toml`) and track the score over time |

## Architecture

```text
repomind/
├── src/repomind/
│   ├── api.py         # public Python API (stable surface)
│   ├── cli/           # Typer + Rich commands: analyze, baseline, trend, search,
│   │                  #   index, explain, review, doctor, rules
│   ├── core/          # discovery, AST parser, complexity, signals, cohesion,
│   │   │              #   call graph, module graph, rules, scoring, trend, doctor
│   │   └── rules/     # one module per rule family, registered in default_rules()
│   ├── git/           # history (churn), blame (git log -L), diff (--since)
│   ├── models/        # shared dataclasses: findings, metrics, enums
│   ├── reporters/     # terminal, Markdown, JSON, SARIF, HTML, agent output
│   ├── semantic/      # AST-aware chunks, BM25 search, embeddings, vector store
│   ├── agents/        # LLM clients, context packs, explain/review agents
│   └── dashboard/     # (roadmap) Streamlit dashboard
├── tests/
│   └── fixtures/sample_project/   # deliberately flawed package used by tests
├── docs/              # architecture, AI guide, benchmarks, releasing
├── pyproject.toml
└── README.md
```

Pipeline: `discover → parse → graph → history → rules → score → report`.
Rules never read files: they consume prepared metrics, graphs and history, which
keeps them fast, deterministic and easy to test. See
[docs/architecture.md](docs/architecture.md) for details and extension guides.

## Dogfooding

RepoMind analyzes itself in CI:

```console
repomind analyze . --no-history --fail-under 95
```

The repository ships a `repomind.toml` with two deliberate decisions:

- `exclude = ["tests/fixtures"]` — the sample project is *intentionally broken*
  (that is its job), so it must not count towards RepoMind's own health.
- two `ignore` globs covering the Typer declaration surfaces in
  `src/repomind/cli/*.py` — a command is one parameter per flag with rich help
  text and no logic, so parameter count and function length describe the CLI
  framework, not the code.

Everything else is clean: **100/100 (grade A)**, zero findings, zero import
cycles. The score only became meaningful after the exclusions above; before
them, RepoMind was grading its own test fixtures.

## Benchmarks

First-run results on popular open-source projects (default thresholds, no
configuration, 500-commit window):

| Project | Files | Source lines | Score | Findings | Wall time |
| --- | ---: | ---: | --- | ---: | ---: |
| psf/requests | 37 | 8,029 | 60/100 C | 159 | 21.9 s |
| pallets/flask | 83 | 10,740 | 68/100 C | 212 | 25.2 s |
| tqdm/tqdm | 65 | 5,901 | 30/100 D | 221 | 24.6 s |
| psf/black | 351 | 118,690 | 85/100 B | 886 | 25.3 s |

The full write-up — methodology, notable findings, and why excluding tests can
*lower* the score — is in [docs/benchmarks.md](docs/benchmarks.md).

## Trend

`repomind trend` samples commits, analyzes each one in a detached Git worktree
(same rules, thresholds and configuration every time) and reports how the
health score moved. RepoMind on itself:

```text
Health trend (last 50 commits)
 Date       Commit  Subject                                  Score  Grade  Findings
 2026-09-22 5f1eb37 Add semantic layer and comprehensive ...     87  B            22
 2026-09-22 c81f016 Reduce complexity in the analysis core       97  A             5
 2026-09-22 8db9318 Add baseline support and --fail-on-new      100  A             1
 2026-09-22 eab2bf1 Track function-level churn with git log -L  100  A             0
 2026-09-22 32aa381 Add LCOM4 cohesion and instability          100  A             0

Score 87 (5f1eb37) -> 100 (32aa381) (+13)  best 100 (8db9318), worst 87 (5f1eb37)
```

History and blame stages are skipped per sample (they would be expensive and
biased by each snapshot's own commit window); use `--samples` and `--commits`
to trade detail for runtime.

## Roadmap

- [x] MVP: CLI, static analysis, dependency graph, terminal + Markdown reports
- [x] Git history analysis with complexity × churn hotspots
- [x] JSON output and `--fail-under` CI gate
- [x] Configurable suppression (`ignore`) and decorator-aware dead-code detection
- [x] Baseline + `--fail-on-new` for incremental adoption in legacy repositories
- [x] Diff mode (`--since`) for pull-request reviews
- [x] SARIF output and a GitHub Action
- [x] Self-contained HTML report
- [x] Benchmarks against popular open-source projects ([docs/benchmarks.md](docs/benchmarks.md))
- [x] Published on PyPI as [`repomind-analyzer`](https://pypi.org/project/repomind-analyzer/) (v0.2.0)
- [x] Security, documentation, call-graph, cohesion and trend analyses
- [x] Semantic layer: local or API embeddings, incremental index, `search --mode semantic`
- [x] Agents: `explain` and `review` (Ollama or any cloud model, deterministic fallbacks)
- [x] Stable Python API (`repomind.api`) and `repomind doctor`
- [ ] `repomind ask`: natural-language questions answered from the index (retrieval-augmented)
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
temporary Git repositories for history analysis. AI features are tested with
fake embedders and fake LLM clients, so the suite needs no network and no
models.

## Contributing

Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Good first
issues: new rules, new reporters, language support, and the roadmap items above.

## License

MIT — see [LICENSE](LICENSE).
