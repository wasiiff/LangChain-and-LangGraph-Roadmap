# Week 6 — Advanced Agents, Product & Career

> **Goal:** design agents the way experienced teams do — the simplest pattern that works, with
> exactly the right context — then reach past vector search, let agents act in browsers and talk
> to other agents, build a product people trust, and finish with one capstone that proves all of it.

← [Back to the main index](../README.md) · [Week 5](../week-05-the-model-layer/README.md)

---

## The week at a glance

| Day | Topic | Time | Difficulty | You'll build |
|---|---|---|---|---|
| [36](day-36-context-engineering-and-agent-patterns.md) | Context engineering & the five agent patterns | 3h | ●●●●○ | All five Anthropic patterns as LangGraph graphs · context measured per call · StudyBuddy v7.0 router |
| [37](day-37-advanced-retrieval.md) | Advanced retrieval: graphs, SQL, agentic search | 3h | ●●●●○ | A knowledge graph with entity resolution · guarded text-to-SQL over SQLite · StudyBuddy v7.1 |
| [38](day-38-emerging-agents.md) | Emerging agents: browsers, computer use, A2A, skills | 3h | ●●●●○ | A Playwright browser agent with an allowlist and approval gate · an A2A agent in both languages · StudyBuddy v7.2 |
| [39](day-39-ai-product-engineering.md) | AI product engineering: UX, feedback, A/B tests, responsible AI | 3h | ●●●○○ | A feedback API tied to run ids · a sticky A/B test with a z-test · StudyBuddy v7.3 |
| [40](day-40-final-capstone-and-career.md) | **Final capstone & career** | 4h | ●●●●● | 🏆 **StudyBuddy v8.0** — one command runs evals, red-team, cost and latency checks |

**Total: ~16 hours.**

---

## What you'll be able to do by the end of the week

- [ ] Pick the simplest agent pattern for a feature — and defend why it isn't a full agent
- [ ] Measure what each model call sees, and cut it with write / select / compress / isolate
- [ ] Answer relationship and number questions that vector search can't: graphs and safe SQL
- [ ] Let an agent act on a web page without letting the page take control of the agent
- [ ] Explain A2A vs MCP, and package instructions as an on-demand skill
- [ ] Collect feedback that turns into eval cases, and run an A/B test you can trust
- [ ] Ship a capstone with evals, a red-team suite, a cost ledger and a release report

---

## The through-line

```
Day 36  Agents work, but you over-build them        → the five patterns + context engineering
Day 37  Some questions aren't "find similar text"   → graphs, SQL and search loops
Day 38  Some work only exists in a browser or in another team's agent → browser agents, A2A
Day 39  It works — but do people trust it, and did your change help? → feedback, A/B tests
Day 40  Prove all of it in one project              → the final capstone and your career plan
```

---

## Version traps this week

| Trap | What we measured | Day |
|---|---|---|
| Python's default `recursion_limit` | **10007** in langgraph 1.2.x (JS: 25) — a runaway loop runs for thousands of steps | 36 |
| Tool-result clearing | JS `contextEditingMiddleware` writes `[cleared]` into state; Python `ClearToolUsesEdit` edits only the request | 36 |
| `withStructuredOutput` (JS base class) | does **not** validate against your Zod schema — parse the result yourself | 37 |
| A2A versions | v1.0 servers reject calls without `A2A-Version: 1.0` (`-32009`), and the 0.3 method `message/send` (`-32601`) | 38 |

---

## Extra installs

| For | JavaScript | Python |
|---|---|---|
| Deep agents (Day 36, optional) | `deepagents` | `deepagents` |
| SQLite (Day 37) | built in: `node:sqlite` (Node 24) | built in: `sqlite3` |
| Browser agents (Day 38) | `playwright` + `npx playwright install --only-shell chromium` | `playwright` (reuses the same browser) |
| A2A (Day 38) | `@a2a-js/sdk` `express` | `"a2a-sdk[http-server]"` |

---

## Common Week 6 blockers

| Symptom | Day | Fix |
|---|---|---|
| Python loop runs thousands of times before `GraphRecursionError` | 36 | Python's default `recursion_limit` is 10007 — keep a round counter in state and stop at a cap |
| JS: `… is already being used as a state attribute … cannot also be used as a node name` | 36 | Rename the node (Python allows it, JS doesn't) |
| Answer quality drops after enabling tool-result clearing, no error | 36 | Compression dropped needed facts — write them to a notebook/store first, then select them back |
| `Error: Input is not an AIMessageChunk.` from a scripted model with `withStructuredOutput` | 37 | Return `AIMessageChunk` from the fake model |
| Graph query returns `[]` though the facts are there | 37 | Add entity resolution ("Dr Khan" / "Khan" / "Aisha Khan") |
| `not authorized to use function: LIKE` | 37 | SQLite reports `LIKE` in upper case — compare function names case-insensitively |
| `ModuleNotFoundError: No module named 'sse_starlette'` starting an A2A server | 38 | `pip install "a2a-sdk[http-server]"` |
| A2A returns `-32009 … version '0.3' is not supported` | 38 | Send `A2A-Version: 1.0` and use v1.0 method names, or use the SDK client |
| Browser agent hangs 30 s, then `Timeout 30000ms exceeded` | 38 | A label changed — set a short action `timeout` and re-read the snapshot |
| `It looks like you are using Playwright Sync API inside the asyncio loop.` | 38 | Use `playwright.async_api` inside async code |
| Python feedback server takes ~2 s per request on Windows | 39 | Bind to and call `127.0.0.1`, not `localhost` |
| An A/B "winner" disappears after launch | 39 | You peeked or stopped early — fix the sample size first, then look once |

---

## Interview topics covered this week

1. **Workflow vs agent, and the five patterns** (Day 36) — the most common design question now
2. **Context engineering** (Day 36) — "how do you stop a long-running agent getting worse?"
3. **When vector RAG fails** (Day 37) — graphs, SQL and agentic search, and how to keep SQL safe
4. **Measuring a change** (Day 39) — A/B tests, guardrail metrics, peeking
5. **Agents that act** (Day 38) — browser safety, approval gates, A2A vs MCP
6. **Talking about your project** (Day 40) — evidence, failure story, trade-offs

---

## StudyBuddy — the running project

```
Day 36  v7.0   a code router sends each feature to the simplest pattern that works
Day 37  v7.1   "ask my progress": guarded SQL over a per-student DB + a course graph
Day 38  v7.2   course-registration helper: fills the form, asks before submitting
Day 39  v7.3   feedback tied to run ids · A/B test of two tutor prompts with guardrails
Day 40  v8.0   🏆 the final capstone: one command runs evals, red-team, cost and latency checks
```

---

→ Start with **[Day 36](day-36-context-engineering-and-agent-patterns.md)**
