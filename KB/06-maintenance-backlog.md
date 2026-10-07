# 06 — Maintenance backlog

Known gaps, deliberate choices, and what to watch on upgrades. Keep this honest — it's the list
a future session should read before promising anything.

---

## Open items

| # | Item | Why it matters | Effort |
|---|---|---|---|
| 1 | **Days 12–14 exercise solutions**: full Python, with JavaScript shown as distinctive sections rather than two complete programs in places | breaks the book's own "both languages, complete" promise in those three days | medium |
| 2 | **JS LangGraph server path not executed**: `langgraphjs dev` fails on this machine (Node 24). The JS *client* was verified against the Python server | Day 27's JS server instructions are untested end-to-end | small, needs a supported Node / WSL / Docker |
| 3 | **Postgres & Redis paths verified by signature only** — no database was available | Day 27's production snippets are shaped correctly but unexecuted | medium, needs Docker |
| 4 | **Remote (Streamable HTTP) MCP** transports: classes verified to exist, never run | Day 26 §4.4 / §5.4 are the least-tested part of that chapter | small, local HTTP server |
| 5 | **LangSmith hosted features** (traces UI, datasets, experiments) never exercised; JS `evaluate` returned 401 without a key | Day 25's hosted sections rest on documentation, not measurement — they're labelled as such | needs an account |
| 6 | **Real-provider runs**: no chapter was executed against a live model | prose about model *quality* (not API behaviour) is reasoned, not measured | needs a key + budget |
| 7 | **Glossary nits**: `**Store**` is tagged *(Day 20)* though Day 18 introduces it; `**Nucleus sampling**` has no Day tag | tiny accuracy issues | trivial |
| 8 | **`@ai-sdk/langchain` bridge** (`toUIMessageStream`, `toBaseMessages`) is installed and documented nowhere | would let Day 26 show a LangGraph backend feeding an AI SDK `useChat` UI | small |
| 9 | **Day 28 capstone acceptance tests** are sketches, not runnable suites | readers would benefit from a runnable starter test file | medium |

## Deliberate choices (don't "fix" these)

- **Markdown only** — no runnable project folders, no `package.json` for examples. Chosen so
  nothing drifts or breaks; code lives in fenced blocks.
- **Two interview formats** — Days 1–16 use collapsed `<details>` Q blocks, Days 17–28 use open
  `**Qn.**`. Both counted by the generator; match the local file rather than normalising.
- **Scripted models everywhere in Weeks 3–4** — keeps every example runnable without an API key.
- **Free-first providers** in the main path, paid alternates collapsed.
- **No CI pipeline in the repo** — `tools/verify.py` is run manually (the repo ships no code to
  test, and the reader's own project is where CI belongs).
- **The root `package.json`** belongs to the reader's practice work (`dotenv`, `gpt-tokenizer`,
  `groq-sdk`). Don't add book dependencies to it.

## Upgrade watchlist

These are the fast-moving surfaces where this book has already seen behaviour change. On any
upgrade, re-run the probes for the rows cited in
[03-verified-findings.md](03-verified-findings.md):

| Surface | What tends to move | Days affected |
|---|---|---|
| `langchain` agent middleware | new middlewares, renamed options, changed defaults (`onFailure` especially) | 24 |
| `createAgent` / `create_agent` options | this is where `prompt` → `systemPrompt`/`system_prompt` bit us | 16, 22, 24, 26, 28 |
| LangGraph node policies | `retry_policy` defaults, `timeout`, `error_handler`, `cache_policy` | 24 |
| Tool error handling | `handle_tool_errors` defaults; JS vs PY divergence | 15, 17, 24 |
| `langgraph-supervisor` / `-swarm` | both READMEs currently steer you elsewhere; could be deprecated | 22 |
| `@langchain/mcp-adapters` / `langchain-mcp-adapters` | config keys, result types, resource helpers | 26 |
| Vercel AI SDK majors | v7 renamed things older tutorials use; v8 will move more | 26 |
| `langgraph-cli` / `langgraph-api` | Windows startup requirements, CLI flags, `POSTGRES_URI` handling | 27 |
| `openevals` / `agentevals` | prompt catalogue and evaluator signatures | 25 |
| Provider defaults | e.g. `ChatGroq` `maxRetries` 6 (JS) vs 2 (PY); model name retirements | 04, 24 |

## Model-name maintenance

Examples use `llama-3.3-70b-versatile` on Groq, `nomic-embed-text` on Ollama, and
`text-embedding-004` / `gemini-2.0-flash` on Google. Provider model names get retired — a
sweep with `grep -rn "llama-3.3-70b-versatile" --include=*.md .` is the quickest way to refresh
them all.

## Git state

As of the last session: Week 4, `KB/`, `tools/`, `CLAUDE.md` and the new `resources/` files were
**uncommitted**. Weeks 1–3 are committed (`cea649d Week 3`). Check `git status` at the start of
a session — and if you commit, the repo's default branch is `main`.
