# AI features: semantic search and agents

RepoMind is deterministic-first: static analysis, history, reports and lexical
search work with **no model, no API key and no network**. Everything described
here is an optional layer on top of the same facts.

| Feature | Extra | Network | What leaves your machine |
| --- | --- | --- | --- |
| analysis, reports, `trend`, `baseline`, `search` (lexical) | none | no | nothing |
| `search --mode semantic` with `provider = "fastembed"` | `semantic` | once, to download the model | nothing |
| `search --mode semantic` with `provider = "api"` | `semantic` | yes | the text of the embedded code chunks |
| `explain` / `review` with Ollama | `llm` | localhost only | nothing |
| `explain` / `review` with a cloud model | `llm` | yes | the prepared facts (findings, metrics, churn) |

Install what you need:

```console
pipx install "repomind-analyzer[semantic]"        # local embeddings
pipx install "repomind-analyzer[llm]"             # agents
pipx install "repomind-analyzer[semantic,llm]"    # both
```

Check the environment at any time with `repomind doctor .` — it reports the
Python version, configuration, Git repository, both extras, the semantic index
and the configured model backend, each with an actionable hint.

## Semantic search

### Local embeddings (default)

```console
repomind index .                       # first run downloads ~130 MB ONNX model
repomind search "where is retry handled" --mode semantic --top 5
repomind search "token refresh" --mode semantic --format json
```

- Model: `BAAI/bge-small-en-v1.5` (384 dimensions) through `fastembed`, which
  uses the ONNX runtime — **no PyTorch**.
- The model is cached by fastembed; subsequent `index` runs only embed chunks
  whose text changed (content-hash based), and drop chunks that no longer exist.
- `repomind index . --rebuild` re-embeds everything.

### API embeddings (opt-in)

```toml
[tool.repomind.semantic]
provider = "api"
model = "gemini/text-embedding-004"     # or "openai/text-embedding-3-small", ...
```

```console
export GEMINI_API_KEY=...               # Windows: $env:GEMINI_API_KEY = "..."
repomind index . --rebuild              # the model change invalidates the old index
repomind search "how are findings scored" --mode semantic
```

API keys are read from the environment by litellm and are **never** written to
configuration (a key in `repomind.toml` is rejected with an error) or to reports.

### The index

- Location: `.repomind/` inside the repository (`embeddings.json` +
  `embeddings.npz`). Add `.repomind/` to `.gitignore` — RepoMind does this in
  its own repository.
- Chunks are real code units: module previews, classes, functions and methods,
  sliced by the parser's line ranges.
- The index stores the model name; changing `model` or `provider` invalidates it
  automatically, so stale vectors can never mix with fresh ones.
- Vectors are L2-normalised, so search is an exact cosine scan — instant at the
  scale of typical repositories and fully offline.

## Agents: `explain` and `review`

### What agents see

Agents never read raw source. They receive a JSON context assembled from the
deterministic analysis:

- the finding with its measured values and thresholds,
- call-graph caller counts,
- function-level churn (commits, authors, last change) when tracked,
- repository summary (files, source lines, score, import cycles).

Their answers must stay inside that context: a review item or citation that
mentions a path outside the context is dropped before rendering, and any
malformed response falls back to the deterministic summary with a note.

### Ollama (default backend)

```console
ollama serve                       # once per session
ollama pull qwen2.5-coder:7b       # the default model in [llm]
repomind explain "design/god-object@src/app/models.py:12"
repomind review . --since main --top 10
```

### Cloud models

Any provider supported by litellm works; pass the model with `--model` and put
the key in the environment:

| Provider | Environment variable | Example `--model` |
| --- | --- | --- |
| OpenAI | `OPENAI_API_KEY` | `gpt-4o-mini` |
| Anthropic | `ANTHROPIC_API_KEY` | `claude-3-5-haiku-latest` |
| Google Gemini | `GEMINI_API_KEY` | `gemini/gemini-3.8-flash` |
| Groq | `GROQ_API_KEY` | `groq/llama-3.1-8b-instant` |

```console
repomind explain "security/dynamic-execution@src/app/plugins.py:88" --model gemini/gemini-3.8-flash
repomind review . --since main --model gpt-4o-mini
```

Transient provider failures (rate limits, 5xx) are retried twice with backoff
before the deterministic fallback is used.

### Configuration

```toml
[tool.repomind.llm]
model = "ollama/qwen2.5-coder:7b"   # any litellm model string
timeout = 60                        # seconds per request
max_findings = 20                   # cap on findings sent to `review`
```

### Fallbacks and flags

| Situation | What happens |
| --- | --- |
| `--no-llm` | deterministic output: `explain` prints the facts and suggestion, `review` prints the ranked findings table |
| `llm` extra missing | `MissingLLMError` is caught and reported as a note with the exact install command; the deterministic output is still printed |
| model unreachable / 503 | a note is printed (`model call failed: ...`); the deterministic output is still printed; `doctor` helps diagnose |
| response not JSON / missing fields | the deterministic output is used, with a note explaining why |
| citation outside context | dropped, with a note listing what was dropped |

Agent commands exit with code 0 even when the model fails, because the
deterministic fallback is a valid result. Configuration errors and missing
indexes exit with code 2.

## Choosing a model

- **Ollama + `qwen2.5-coder:7b`** — good default for code; free and private.
  Slower on CPU-only machines; `explain` (one finding) is much cheaper than
  `review` (up to `max_findings` findings).
- **Cloud flash/mini models** (`gemini-3.8-flash`, `gpt-4o-mini`,
  `claude-3-5-haiku-latest`) — fast and cheap, useful when you want a second
  opinion without local hardware. Keep `--top` small to bound cost.
- **Embeddings** — `BAAI/bge-small-en-v1.5` is the local default and works well
  for English identifiers and docstrings. For other languages or higher quality,
  use `provider = "api"` with a modern embedding model.

## Privacy summary

- With the base install, nothing ever leaves your machine.
- With `[semantic]` + fastembed, only the one-time model download touches the
  network.
- With `[llm]` + Ollama, requests go to `localhost`.
- With cloud models or API embeddings, the prepared facts (or chunk text for
  embeddings) are sent to the provider you configured; RepoMind stores no keys
  and logs no prompts.
