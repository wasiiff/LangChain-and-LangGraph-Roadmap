# 04 — Versions and environment

The book's claims are true **at these versions**. When something stops matching, re-verify and
update [03-verified-findings.md](03-verified-findings.md).

---

## Runtimes used for verification

| | Version |
|---|---|
| Node.js | 24.15.0 |
| Python | 3.14.4 |
| OS | Windows 11 (PowerShell + Git Bash) |

## JavaScript packages

| Package | Version verified | Used by |
|---|---|---|
| `langchain` | 1.5.11 (1.5.10 in Week 2) | agents, `createAgent`, middleware |
| `@langchain/core` | 1.2.10 | messages, tools, runnables, fakes |
| `@langchain/langgraph` | 1.4.14 | graphs, checkpointers, interrupts |
| `@langchain/langgraph-checkpoint-sqlite` | 1.0.4 | Day 20 persistence |
| `@langchain/langgraph-checkpoint-postgres` | not recorded | Day 27 (signatures only) |
| `@langchain/langgraph-supervisor` | 1.1.1 | Day 22 |
| `@langchain/langgraph-swarm` | 1.0.2 | Day 22 |
| `@langchain/langgraph-sdk` | 1.10.2 | Day 27 client |
| `@langchain/langgraph-cli` | 1.4.5 | Day 27 (`langgraphjs dev` fails on Node 24 here) |
| `@langchain/mcp-adapters` | 1.1.4 | Day 26 |
| `@modelcontextprotocol/sdk` | 1.30.0 | Day 26 server/client |
| `langsmith` | 0.10.2 | Day 25 |
| `openevals` | 0.2.2 | Day 25 judges |
| `agentevals` | 0.0.7 | Day 25 trajectories |
| `ai` | **7.0.97** | Day 26 (v7 API: `inputSchema`, `stopWhen`, `ToolLoopAgent`) |
| `@ai-sdk/groq` | 4.0.40 | Day 26 |
| `@ai-sdk/mcp` | 2.0.48 | Day 26 (`createMCPClient`) |
| `@ai-sdk/langchain` | 3.0.97 | installed, not used in the book (`toUIMessageStream`, `toBaseMessages`) |
| `zod` | installed as a dependency; version not recorded | tool schemas |

## Python packages

| Package | Version verified | Used by |
|---|---|---|
| `langchain` | 1.4.0 (1.3.17 in Week 2) | `create_agent`, middleware |
| `langchain-core` | 1.6.2 | messages, tools, runnables, fakes |
| `langchain-classic` | 1.0.8 | Week 2 legacy chains/retrievers |
| `langgraph` | 1.2.11 | graphs, `RetryPolicy`, `CachePolicy` |
| `langgraph-checkpoint-sqlite` | installed; version not recorded | Day 20 |
| `langgraph-checkpoint-postgres` | 3.1.2 | Day 27 (signatures only) |
| `langgraph-supervisor` | 0.0.31 | Day 22 |
| `langgraph-swarm` | 0.1.0 | Day 22 |
| `langgraph-cli[inmem]` | 0.4.31 (`langgraph-api` 0.14.1) | Day 27 server |
| `langgraph-sdk` | 0.4.4 | Day 27 client |
| `langchain-mcp-adapters` | 0.3.2 | Day 26 |
| `mcp` | 1.30.0 | Day 26 FastMCP + client |
| `langsmith` | 0.12.4 | Day 25 |
| `openevals` | 0.2.0 | Day 25 |
| `agentevals` | 0.0.9 | Day 25 |
| `fastapi`, `httpx`, `uvicorn` | installed; versions not recorded | Days 23, 27 |
| `colorama` | required on Windows for `langgraph dev` | Day 27 |

> Rows marked "not recorded" were installed but their version wasn't captured — record them next
> time you rebuild.

## Rebuilding the sandbox

Never install into the repo. The scratchpad path is printed in each session's environment
block; it is **periodically cleared**, so expect to rebuild.

```bash
D="<scratchpad>/apicheck"; mkdir -p "$D" && cd "$D" || exit 1

# JavaScript
echo '{"name":"apicheck","private":true,"type":"module"}' > package.json
npm i --silent @langchain/langgraph @langchain/core langchain zod \
  @langchain/langgraph-checkpoint-sqlite @langchain/langgraph-supervisor \
  @langchain/langgraph-swarm @langchain/langgraph-sdk @langchain/mcp-adapters \
  @modelcontextprotocol/sdk ai @ai-sdk/groq @ai-sdk/mcp langsmith openevals agentevals

# Python
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -q langgraph langchain langchain-core \
  langgraph-checkpoint-sqlite langgraph-checkpoint-postgres langgraph-supervisor \
  langgraph-swarm "langgraph-cli[inmem]" langgraph-sdk langchain-mcp-adapters mcp \
  langsmith openevals agentevals fastapi httpx colorama
```

Then confirm what you actually got — the book quotes behaviour, so the version matters:

```bash
node -e "for (const p of ['langchain','@langchain/langgraph','ai']) console.log(p, require('./node_modules/'+p+'/package.json').version)"
./.venv/Scripts/python.exe -c "from importlib.metadata import version as v; print(v('langchain'), v('langgraph'))"
```

## No API keys needed

Everything in Weeks 3–4 was verified with **scripted/fake models** (see
[05-verification-playbook.md](05-verification-playbook.md)). Keep it that way: a reader with no
key can run the examples, and CI can run the eval suites.

Not exercised for lack of credentials or services: LangSmith's hosted UI/datasets/experiments
(JS `evaluate` returned 401), real provider calls, Postgres/Redis-backed checkpointers, and
remote (Streamable HTTP) MCP transports. These are described in the book but marked as not
executed — see [06-maintenance-backlog.md](06-maintenance-backlog.md).

## Shell and OS gotchas

| Symptom | Cause | Do this |
|---|---|---|
| `unexpected EOF while looking for matching ''` | long heredocs through the Bash tool | write the file with the Write tool, then run it |
| `cd: …: No such file or directory` then commands run in the repo | the sandbox was cleared | always `cd "<abs>" || exit 1` |
| `UnicodeEncodeError: 'charmap' codec` | Windows console + emoji | `PYTHONIOENCODING=utf-8`, `PYTHONUTF8=1` |
| `ConsoleRenderer with colors=True on Windows…` | `langgraph dev` | `pip install colorama` |
| `node.exe: bad option: --clear-screen=false` | `langgraphjs dev` on Node 24 | use a supported Node, WSL or Docker |
| A background server "fails" instantly | port still bound, or a startup crash | read its log file; stop the old one (`Get-NetTCPConnection -LocalPort <p>` → `Stop-Process`) |
