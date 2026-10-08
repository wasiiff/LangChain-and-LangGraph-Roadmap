# Week 4 — Multi-agent, Production, Projects & Interviews

> **Goal:** take StudyBuddy from "works on my machine" to a system someone else could run —
> then prove what you've learned with a capstone and an interview method.

← [Back to the main index](../README.md) · [Week 3](../week-03-tools-agents-and-langgraph/README.md)

---

## The week at a glance

| Day | Topic | Time | Difficulty | You'll build |
|---|---|---|---|---|
| [22](day-22-multi-agent.md) | Multi-agent: supervisor via tools, handoffs, hierarchies — **and when it backfires** | 3h | ●●●●○ | 🎯 StudyBuddy v5 — a tool-based supervisor |
| [23](day-23-streaming-and-events.md) | Streaming: stream modes, filtered tokens, custom events, **SSE**, cancellation | 2.5h | ●●●○○ | v5 streamed to a browser |
| [24](day-24-reliability.md) | Reliability: retries, fallbacks, timeouts, limits, breakers, PII, injection | 3h | ●●●●○ | A hardened StudyBuddy + a failure lab |
| [25](day-25-observability-and-evaluation.md) | Observability & evaluation: callbacks, LangSmith, datasets, judges, trajectories | 3h | ●●●●○ | An eval suite with a CI regression gate |
| [26](day-26-mcp-and-ai-sdk.md) | **MCP** servers & clients + the **Vercel AI SDK** | 3h | ●●●○○ | One MCP server, three consumers |
| [27](day-27-deployment-and-architecture.md) | Deployment: start/poll/resume, the LangGraph server, Docker, scaling | 3h | ●●●●○ | A production architecture for 100k students |
| [28](day-28-capstones-and-interviews.md) | **Capstones** + interview crash course & mock interviews | 3h+ | ●●●●● | 🏆 Your capstone, from a keyless starter kit |

**Total: ~20.5 hours**, plus capstone time.

---

## What you'll be able to do by Sunday

- [ ] Decide between a single agent, a workflow, a supervisor and handoffs — **with measurements**
- [ ] Build a supervisor whose specialists are tools, controlling exactly what each model sees
- [ ] Stream progress and **only the user-facing tokens** to a browser over SSE
- [ ] Wire cancellation end to end — and explain why a JS `break` isn't enough
- [ ] Put retries, fallbacks, timeouts and call limits in the right layer, once each
- [ ] Explain the retry and tool-error defaults that differ between JS and Python
- [ ] Defend an agent against prompt injection with capability limits, not just prompt wording
- [ ] Trace runs, count tokens per model, and label runs by prompt version
- [ ] Build a dataset, calibrate an LLM judge, and gate deploys on an eval suite
- [ ] Evaluate an agent's **trajectory**, not just its final answer
- [ ] Expose tools over MCP and consume them from LangChain (JS and Python) and the AI SDK
- [ ] Deploy long, human-gated runs with start / poll / resume and a shared checkpointer
- [ ] Do the capacity arithmetic that tells you the real bottleneck
- [ ] Present a capstone with evidence, and answer design questions with a repeatable method

---

## The through-line

```
Day 21  StudyBuddy can act, pause and resume          → but one agent is doing everything
Day 22  Specialists behind a supervisor                → and it thinks in silence for 8 seconds
Day 23  Streaming, filtered, cancellable               → and it falls over on a bad day
Day 24  Retries, fallbacks, limits, guardrails         → but is it actually any good?
Day 25  Traces, datasets, judges, a regression gate    → and other apps want its tools
Day 26  MCP and the AI SDK                             → and it still only runs on a laptop
Day 27  A production architecture                      → so prove you can build it
Day 28  Capstones and interviews                       → 🎓
```

---

## Verified, not recalled

Week 4 leans on fast-moving libraries, so every behaviour claimed was **run** — against scripted
models (no API key needed) in both languages, and for Day 27 against a real local LangGraph server.
Some findings that most tutorials get wrong:

| Finding | Day |
|---|---|
| A single-hop question costs **2 model calls** with one agent and **4** under any supervisor pattern | 22 |
| JS `createAgent` returns a wrapper; libraries need **`.graph`**. Python returns the graph | 22 |
| JS: breaking out of a stream **does not stop the graph**. Python: it stops before the next superstep | 23 |
| JS includes nested agents' tokens in `messages` streams by default; Python needs `subgraphs=True` | 23 |
| Python's node `retry_on` default **does not retry `TimeoutError`** (it's an `OSError`) | 24 |
| Python node timeouts require **async** nodes | 24 |
| Tool exceptions: JS `ToolNode` returns them as content; **Python re-raises** unless `handle_tool_errors` | 24 |
| Model-retry middleware defaults to turning the error **into the assistant's reply** | 24 |
| JS: a Groq 429 is **never retried** by `maxRetries` (its text links to a billing page); Python's client retries it | 24 |
| When every fallback fails, the error you see is the **primary's** | 24 |
| Chat models fire `handleChatModelStart`, **not** `handleLLMStart` | 25 |
| Python MCP tools are **async-only**; uncaught MCP handler exceptions **leak their raw text** | 26 |
| AI SDK `generateText` with tools and no `stopWhen` **stops after the tool call** with empty text | 26 |
| The LangGraph server **rejects a graph compiled with a checkpointer** | 27 |
| `Command` goto **adds to** static edges — in an approval gate, rejected actions ran | 28 |

---

## Extra installs for this week

```bash
# JavaScript
npm install langchain @langchain/langgraph-supervisor @langchain/langgraph-swarm \
            langsmith openevals agentevals \
            @modelcontextprotocol/sdk @langchain/mcp-adapters \
            ai @ai-sdk/groq @ai-sdk/mcp \
            @langchain/langgraph-sdk @langchain/langgraph-checkpoint-postgres

# Python
pip install langchain langgraph-supervisor langgraph-swarm \
            langsmith openevals agentevals \
            mcp langchain-mcp-adapters \
            "langgraph-cli[inmem]" langgraph-sdk langgraph-checkpoint-postgres "psycopg[binary]" \
            fastapi uvicorn
```

Nothing this week *requires* a paid key: every day's verification ran on scripted models, and
LangSmith tracing is optional (Day 25 shows how to do everything without it).

---

## Common Week 4 blockers

| Symptom | Day | Fix |
|---|---|---|
| `Please specify a name when you create your agent` — but you did | 22 | Pass `agent.graph` (JS `createAgent` returns a wrapper) |
| The front desk answers after a handoff to billing | 22 | Swarm needs a checkpointer, or carry `activeAgent` |
| Specialist gives an answer to the wrong question | 22 | The brief: specialists see only the tool arguments |
| UI shows router/specialist text before the answer | 23 | Tag the answering model `final`; filter on the tag |
| Clicking Stop doesn't reduce the bill | 23 | JS: pass a `signal` to `stream()` and `config.signal` into nodes |
| Streaming works locally, arrives all at once in production | 23 | Buffering: disable compression, `X-Accel-Buffering: no` |
| `checkpoints` stream mode crashes with an odd error | 23 | It needs a checkpointer |
| Python node never retries a timeout | 24 | Pass an explicit `retry_on` |
| `Node timeouts are only supported for async nodes` | 24 | Make the node `async def` |
| Python agent crashes when a tool raises | 24 | Catch in the tool, or `ToolNode(..., handle_tool_errors=...)` |
| Users see "Model call failed after 3 attempts…" as the answer | 24 | `onFailure: "error"` / `on_failure="error"` |
| JS gives up on the first Groq 429 despite `maxRetries: 6` | 24 | `.withRetry(...)` on the model (429/5xx only), or a fallback |
| Metrics show zero model calls | 25 | Listen for `handleChatModelStart` / `on_chat_model_start` |
| JS `evaluate` fails with 401 | 25 | It needs LangSmith credentials; use a local harness offline |
| `StructuredTool does not support sync invocation` | 26 | MCP tools in Python: `await tool.ainvoke(...)` |
| AI SDK returns empty text though the tool ran | 26 | Add `stopWhen: stepCountIs(n)` |
| `Heads up! Your graph ... includes a custom checkpointer` | 27 | Export `builder.compile()` for the LangGraph server |
| Python `langgraph dev` crashes on Windows at startup | 27 | `pip install colorama`; set `PYTHONUTF8=1` |
| A rejected action still executed | 28 | `Command` goto plus a static edge runs both — route every path with `Command` |

---

## Interview topics covered this week

Ranked by how often they come up:

1. **System design for an agent product** (Days 27–28) — the 8-step framework
2. **How do you evaluate an LLM app / an agent?** (Day 25)
3. **Reliability: retries, fallbacks, limits, injection** (Day 24)
4. **When is multi-agent worth it?** (Day 22) — answer with measurements
5. **Deploying long-running, human-gated agents** (Day 27)
6. **Streaming to a UI and cancellation** (Day 23)
7. **What is MCP and when would you use it?** (Day 26)
8. **LangChain vs the Vercel AI SDK** (Day 26)
9. **Tell me about a project** (Day 28) — problem · decision · evidence · failure · next

---

## StudyBuddy — the running project

```
Week 1  v1.0   parallel analysis · routing · streaming · retries
Week 2  v2–3   reads YOUR documents · citations · memory across sessions
Week 3  v4.0   tools · agent graph · persistence · approval gate on writes
Day 22  v5.0   🎯 supervisor with researcher, quizmaster and analyst as tools
Day 23  v5.1   streamed to a browser, with Stop that actually stops
Day 24  v5.2   hardened: retries, fallback, limits, breaker, PII redaction
Day 25  v5.3   traced, evaluated, gated in CI
Day 26  v5.4   its tools shared over MCP
Day 27  v6.0   designed for production at 100k students
Day 28  ─────  🏆 your capstone
```

---

→ Start with **[Day 22](day-22-multi-agent.md)**
