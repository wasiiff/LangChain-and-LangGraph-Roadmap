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

### Added October 2026 (course expansion and model migration)

✅ **Done on 8 October 2026** (owner approved code changes): items 10–13 below — every listed code bug
was fixed and re-run in both languages, the Groq/Gemini model names were migrated (and run live
for the first time), and Day 22's ping-pong numbers were corrected. Kept for history:

| # | Item | Status |
|---|---|---|
| 10 | Verified code bugs (Day 21 Fix C, Day 19 §5.8, Day 17 fan-out output/comment, Day 14 template literal, Day 10 embed methods + Ex5 backticks, Day 21 async/`approveSql`, Day 19 Ex4 no-op) | ✅ fixed, plus ~10 more bugs the migration found by running (see KB/03 "What the migration measured") |
| 11 | Shut-down Google models | ✅ `gemini-3.8-flash` / `gemini-embedding-2` |
| 12 | Day 20 history step numbering, §5.8 output | ✅ measured and made consistent |
| 13 | Day 22 ping-pong "37 calls" | ✅ 25 (JS default limit) |

**Still open:**

| # | Item | Why it matters | Effort |
|---|---|---|---|
| 15 | OWASP 2026 edition (Day 35) and EU AI Act dates incl. Reg. (EU) 2026/1744 (Day 39) came from agents' web research — spot-check the primary sources | facts change | small |
| 16 | GPU paths (vLLM, QLoRA, bitsandbytes) labelled not executed | honest but untested | needs a GPU |
| 17 | **Ollama isn't installed** here — no `nomic-embed-text` retrieval result in Days 10–14 has been measured; Ollama snippets show only the no-server error | retrieval claims rest on stand-ins | install Ollama, re-run Days 10–14 |
| 18 | **Snippets renamed but not run live** (rate limits / interactive / needs Chroma): Day 04 Ex3–Ex5; Days 05–08 non-core snippets; Day 12 Ex2, Ex5; Day 13 Ex1, Ex2, Ex5 + JS HyDE/rerank/compression; Day 14 §4.1/§5.1, Ex1, Ex4, Ex5; Day 15 most of §4.2–4.5; Day 16 Ex1, Ex3–Ex5; Day 19 §4.3/§5.3 `Send` research graph + Ex4 model version; Day 21 Ex5; Days 23, 28, 36–40 real-model swaps | outputs there are labelled illustrative | a quiet key + time; run serially (30 RPM / 8k TPM free tier) |
| 19 | `qwen/qwen3.8-27b` is a Groq **preview** model (used only for text-ReAct in Days 02 and 16) | could disappear at short notice | re-check the models page |
| 20 | No successful live `gemini-3.8-flash` chat run is quoted yet (503 high demand / quota during the session); Day 33's vision call and real image-token counts unmeasured | Gemini sections rest on request captures | small, when Gemini quota allows |
| 21 | "(no key)" wording — swept outside Days 04, 06–08, 14, 18, 21, 24 (scripted-model "no API key" notes are correct and kept) | wording | trivial |
| 22 | Day 18 §4.7 TypeScript type-checking claim not run (`tsc` not installed); Day 15 "~200ms router" latency unmeasured | small claims | small |
| 23 | Day 08 still has ~8 `withStructuredOutput` calls on the default (tool-calling) method (≈ lines 475, 613, 754, 890, 1140, 1198, 1341, 1449) — flaky on GPT-OSS; switch to JSON-schema mode and run each | readers may hit `400 tool_use_failed` | small, needs quota |
| 24 | Day 06 Ex4 Gemini tiers 3–4 unverified (Gemini 429); Day 06 Ex3 broken-receipt hint comments let the model "fix" the receipt | small | small |
| 25 | Day 21 §7 ❌/✅ comparison blocks in `js` fences aren't valid JS (common-mistakes style) | cosmetic | small |
| 26 | JS and PY trim different numbers of messages for the same budget (JS GPT-2 encoding vs PY approximate) — a JS `countTokensApproximately` helper would make them match | parity | small |

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

Since 7 October 2026 examples use `openai/gpt-oss-120b` and `openai/gpt-oss-20b` on Groq (the
old `llama-3.3-70b-versatile` / `llama-3.1-8b-instant` returned `404 model_not_found` for the
owner's account), `qwen/qwen3.8-27b` (Groq **preview**) only for text-protocol ReAct with stop
sequences, `nomic-embed-text` on Ollama, and `gemini-3.8-flash` / `gemini-embedding-2` on Google
(`gemini-2.5-flash` is closed to new users; `text-embedding-004` and `gemini-2.0-flash` are shut
down). Provider model names get retired — check a key's real list first:

```bash
curl -s https://api.groq.com/openai/v1/models -H "Authorization: Bearer $GROQ_API_KEY"
curl -s "https://generativelanguage.googleapis.com/v1beta/models?key=$GEMINI_API_KEY"
```

Then sweep with `grep -rn "openai/gpt-oss-120b" --include=*.md .` to refresh them all. Note that
Groq's docs page can list a model that an account's `/models` endpoint does not — trust the
endpoint and a real call.

## Git state

As of October 2026: Weeks 0 and 4–6, `KB/`, `tools/`, `CONTRIBUTING.md` and most `resources/` changes are
**staged but uncommitted** (the owner staged them; no commit has been made). Weeks 1–3 are committed (`cea649d Week 3`). Check `git status` at the start of
a session — and if you commit, the repo's default branch is `main`.
