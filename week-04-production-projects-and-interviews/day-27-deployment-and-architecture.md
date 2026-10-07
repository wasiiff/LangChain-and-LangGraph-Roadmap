# Day 27 — Deployment & Architecture: From Laptop to a Million Students

> ⏱ **Time:** ~3 hours · 🎯 **Prereqs:** [Day 26](day-26-mcp-and-ai-sdk.md) · 🧩 **Difficulty:** ●●●●○

**Today you learn:** how to run StudyBuddy for real users. The three ways to ship a LangGraph
application — inside your web app, as your own service, or on the LangGraph server — and how
to choose. The **start / poll / resume** run pattern that survives long jobs and restarts.
Docker, serverless and its limits, Postgres and Redis in the right roles, graceful shutdown,
and the capacity arithmetic for scaling to a million students. The LangGraph server, its
client SDKs in both languages, and a self-hosted service were all run locally for this
chapter.

---

## 1. The problem

StudyBuddy v5 works beautifully in `node studybuddy.mjs`. Then:

```
   Monday     You put it behind an Express route on one small VM. 40 students. Fine.
   Tuesday    A deploy restarts the process mid-conversation. 12 students lose their chat
              and one approval request vanishes.
   Wednesday  "Generate my exam study plan" takes 90 seconds. The load balancer times out
              at 60. The student retries. Two plans get generated and billed.
   Thursday   Exam week traffic. One VM, 800 concurrent students. Memory climbs, then OOM.
   Friday     Someone says "just put it on serverless". The first request with a 3-step
              agent hits the function's time limit.
```

Every one of those is an **architecture** problem, not a LangChain problem. You already have
the pieces that fix them — checkpointers (Day 20), interrupts (Day 21), streaming (Day 23),
reliability (Day 24), observability (Day 25). Today is about assembling them into a system
that runs.

### The real-life version

A restaurant that works for a dinner party of eight doesn't automatically work as a restaurant.

```
   HOME KITCHEN                         RESTAURANT
   ────────────                         ──────────
   one cook remembers every order       orders are written on tickets     ← STATE IN A DATABASE
   you wait at the stove                you get a buzzer, sit down        ← START / POLL
   the cook gets sick → dinner's off    any cook can pick up a ticket     ← STATELESS WORKERS
   everyone arrives at once → chaos     a host seats people, kitchen      ← QUEUES & LIMITS
                                        works at its own pace
```

---

## 2. Mental model

### The golden rule

```
   ┌──────────────────────────────────────────────────────────────────┐
   │   COMPUTE IS STATELESS.  STATE LIVES IN A DATABASE.               │
   │                                                                   │
   │   Any process can serve any request for any conversation,         │
   │   because nothing about the conversation lives in the process.    │
   └──────────────────────────────────────────────────────────────────┘
```

Day 20 already made this possible: with a shared checkpointer, the graph holds nothing and
the `thread_id` finds everything. Deployment is mostly the discipline of not breaking it.

### Three ways to ship a graph

```
   A. IN YOUR APP                 B. YOUR OWN SERVICE              C. THE LANGGRAPH SERVER
   ──────────────                 ───────────────────              ───────────────────────
   Next.js route / Express /      a small API you write:           langgraph.json → a ready-made
   FastAPI handler calls          threads, runs, resume,           API: assistants, threads,
   graph.invoke / stream          status — around your graph       runs, streaming, interrupts,
                                                                   background runs, crons
   + simplest                     + full control, any infra        + the most features, least code
   − request lifetime limits      − you build run management       − another runtime to operate
   − scaling = your web tier      − you build it all                 (self-hosted or managed)
```

| | A. In your app | B. Your own service | C. LangGraph server |
|---|---|---|---|
| Good for | short chats, one team, one app | custom infra or compliance needs | agents with long runs, HITL, many clients |
| Persistence | your checkpointer | your checkpointer | built in (`POSTGRES_URI`) |
| Long runs | ❌ bound to the request | ✅ if you build background runs | ✅ background runs + join |
| Interrupts / resume | you wire endpoints | you wire endpoints | ✅ `command: { resume }` over the API |
| Streaming | you write SSE (Day 23) | you write SSE | ✅ `runs.stream` |
| Client | your own fetch code | your own fetch code | `@langchain/langgraph-sdk` / `langgraph_sdk` |

Many teams start with **A**, move long or stateful work to **B** or **C** when it hurts, and
keep simple chat in **A**. That's fine; it's the same graph code in all three.

### The shape of a production system

```
                    ┌──────────────── EDGE ────────────────┐
   browser/app ───► │ CDN · TLS · auth · rate limit · WAF  │
                    └──────────────────┬────────────────────┘
                                       ▼
                    ┌──────────── API (stateless) ─────────┐
                    │ validate · own thread_id · start run │──┐
                    │ stream / poll status · resume         │  │ enqueue long runs
                    └──────────┬───────────────────┬────────┘  │
                               │                   │           ▼
                               │                   │   ┌── WORKERS (stateless) ──┐
                               │                   │   │ execute graph runs       │
                               │                   │   │ concurrency-limited      │
                               │                   │   └────────────┬─────────────┘
                               ▼                   ▼                ▼
                    ┌─────────────────── DATA ────────────────────────────────────┐
                    │ Postgres: checkpoints · store · runs · users · audit         │
                    │ Redis:    queue · rate limits · locks · stream pub/sub · cache│
                    │ Vector DB: embeddings (Day 11)                                │
                    └──────────────────────────────────────────────────────────────┘
                                       │
                    model providers (Groq, Gemini, …) + MCP servers (Day 26)
```

---

## 3. First principles

### 3.1 Request lifetime vs run lifetime

An HTTP request lives for seconds. An agent run can live for minutes — or, with an interrupt
waiting for a teacher, for days. Tying the two together is the root of most deployment pain:

```
   BOUND TO THE REQUEST                        DECOUPLED
   ────────────────────                        ─────────
   POST /chat  ─── run ───► response           POST /runs      → 202 { run_id }   (instant)
                                               GET  /runs/:id  → status           (poll or stream)
   load balancer timeout = run timeout         POST /resume    → 202 { run_id }
   client disconnect = lost work                the run lives in a worker + the database
   retry = duplicate run                        retry of POST can be de-duplicated
```

Rule of thumb: **if a run can exceed ~20 seconds, or can pause for a human, decouple it.**
Short streaming chat can stay bound to the request (Day 23) — with cancellation wired.

### 3.2 The start / poll / resume pattern — verified

This chapter's self-hosted service (§4.2, §5.2) was run in both languages with an identical
result:

```
   POST /threads/t1/runs {text: "hello"}   → 202 { run_id }
   GET  immediately                        → status: "running"
   GET  after it pauses                    → status: "interrupted", next: ["gate"],
                                             pending: [{ question: "Post this answer?", draft: "echo: hello" }]
   POST /threads/t1/resume {decision}      → 202 { run_id }
   GET  after                              → status: "success", next: []
   GET  the run under a DIFFERENT thread   → 404
```

That last line is Day 20's IDOR lesson built into the API: a run is only visible through the
thread that owns it.

### 3.3 The LangGraph server — verified

The LangGraph server (the "Agent Server", run locally with `langgraph dev`) turns a compiled
graph into that whole API. You describe the project in `langgraph.json`:

```json
{
  "dependencies": ["."],
  "graphs": { "studybuddy": "./graph.py:graph" },
  "env": ".env"
}
```

Run against it with the Python and JS SDKs (both verified against the same server):

```
   assistants.search()                      → [("studybuddy", …)]   one per graph in langgraph.json
   threads.create()                         → { thread_id, status, values, metadata, … }
   runs.wait(thread, "studybuddy", input)   → { messages, __interrupt__: [{ value, id }] }
   threads.get_state(thread)                → next: ["gate"], tasks[].interrupts
   runs.wait(thread, …, command={resume})   → { approved: true, messages: [...] }
   threads.get_history(thread)              → 4 checkpoints
   runs.stream(…, stream_mode=["updates","values"]) → events: metadata, values, updates, …
   runs.create(…)                           → status "pending";  runs.join(…) → "success"
```

Three things the server did that you'd otherwise build yourself: persistence per thread,
interrupts surfaced and resumable over HTTP, and background runs you can join later.

**Verified trap:** a graph compiled *with* its own checkpointer is rejected at load:

```
   ValueError: Heads up! Your graph 'graph' from './graph.py' includes a custom checkpointer
   (type InMemorySaver). With LangGraph API, persistence is handled automatically by the
   platform ... please remove the custom checkpointer ... If you are looking to customize which
   postgres database to connect to, please set the `POSTGRES_URI` environment variable.
```

Export the graph compiled **without** a checkpointer — `builder.compile()` — and keep a separate
`compile({ checkpointer })` for local scripts and tests if you like.

> 🪟 **Windows notes from running it:** the Python server needed `colorama` installed
> (`ConsoleRenderer with colors=True on Windows requires the colorama package`) and a UTF-8
> console (`PYTHONUTF8=1`). The JS CLI's `langgraphjs dev` failed to start on Node 24 here
> (`node.exe: bad option: --clear-screen=false`) — check the CLI's supported Node versions,
> or run it under WSL or Docker. The server's HTTP protocol is the same for both languages, so
> the JS SDK client code in §4.3 was verified against the Python server.

### 3.4 Docker

`langgraph dockerfile Dockerfile` generates a Dockerfile from `langgraph.json` (verified,
offline): it builds on the `langchain/langgraph-api` base image, installs your project, and
registers the graphs through an environment variable. `langgraph build` builds the image.

For a self-hosted service (option B) you write a normal Dockerfile. The principles are the
usual ones, and they matter more for AI services because images get large fast:

```
   small base image · dependencies before source (layer cache) · non-root user ·
   no secrets in the image (env / secret manager at runtime) · a /healthz endpoint ·
   SIGTERM handled (graceful shutdown) · one process per container
```

### 3.5 Serverless: what fits and what doesn't

```
   FITS                                          DOESN'T
   ────                                          ───────
   short chat turns, streamed                    runs longer than the platform's time limit
   stateless routes with a shared checkpointer   in-memory checkpointers (each call may be a new instance)
   webhooks that ENQUEUE work                    background work after the response is sent
   burst traffic, scale to zero                  stdio MCP servers (subprocess per invocation)
                                                 connection-hungry clients without a pooler
```

The pattern that works: **serverless for the API, dedicated workers for long runs.** And use a
connection pooler (PgBouncer, or your provider's pooled endpoint) — hundreds of short-lived
function instances each opening a Postgres connection will exhaust it.

### 3.6 Postgres and Redis: the right jobs

```
   POSTGRES (durable truth)                    REDIS (fast, disposable)
   ────────────────────────                    ────────────────────────
   checkpoints (PostgresSaver)                 job queue / run dispatch
   long-term store (PostgresStore)             rate limits, concurrency caps
   runs table, users, conversations            circuit-breaker state shared by workers (Day 24)
   audit log of approvals and tool calls       pub/sub fan-out of stream events
   (pgvector for embeddings, if you like)      short-TTL caches (embeddings, retrieval)
```

The test for Redis: **if Redis is wiped, does anyone lose data they care about?** The answer
must be no. Conversations and approvals belong in Postgres.

Verified APIs: Python `PostgresSaver.from_conn_string(...)` is a context manager (as SQLite's
was on Day 20) with `.setup()` and `.delete_thread()`; `AsyncPostgresSaver` for async
servers; `PostgresStore` is available. JS `PostgresSaver.fromConnString(...)` returns the saver
directly, with `setup()`, `deleteThread()` and `end()`; `PostgresStore` lives at
`@langchain/langgraph-checkpoint-postgres/store`.

### 3.7 Capacity arithmetic

Model calls are I/O-bound: a worker spends almost all its time waiting on the provider. So the
constraint is rarely CPU — it's **provider rate limits, concurrent connections and tokens**.

```
   1,000,000 registered students
   ×  5%   daily active                =  50,000 students/day
   ×  8    questions per student/day   = 400,000 runs/day
   peak hour ≈ 15% of the day          =  60,000 runs/hour ≈ 17 runs/second at peak
   ×  3    model calls per run         ≈  50 model calls/second
   ×  6 s  average run duration        ≈ 100 runs in flight at peak

   tokens: 400,000 runs × ~4,000 tokens  = 1.6 billion tokens/day
```

What that tells you:

- **100 concurrent runs is small** for async workers — a handful of processes. Compute is not
  the problem.
- **50 model calls/second is the real constraint.** It must fit inside your provider's rate
  limits — which is why Day 24's rate limiter, fallback provider and queue matter.
- **1.6 billion tokens a day is the bill.** Day 25's per-request token metrics and Day 18's
  "keep state small" are the cost levers; so is routing easy questions to a cheaper model.
- **Checkpoint writes:** ~4 per run (Day 20) × 400,000 = 1.6 million writes/day ≈ 70/s at
  peak — comfortable for Postgres *if state is small*. With 2 MB of state, it isn't.

Do this arithmetic with your own numbers before choosing infrastructure. It changes the
conversation from "will it scale?" to "which of these three numbers is the bottleneck?".

### 3.8 Configuration and secrets

```
   CONFIG (per environment)     model names, limits, feature flags, POSTGRES_URI host
   SECRETS (secret manager)     API keys, DB passwords, signing keys — never in images or repos
   CONTEXT (per request)        user id, tier, thread id (Day 18) — never in env vars
```

And pin versions. LangChain, LangGraph and the provider SDKs move quickly; this book found
behaviour differences between minor versions and between languages. A lockfile plus the Day 25
evaluation suite in CI is what makes an upgrade a routine task instead of an incident.

---

## 4. Code — JavaScript

### 4.1 Option A — inside your app (short, streamed chat)

Day 23's route handler is already a deployment. The production additions are small:

```js
// app/api/chat/route.js
import { HumanMessage } from "@langchain/core/messages";
import { getGraph } from "@/lib/studybuddy";          // built ONCE per process (see below)
import { requireUser, threadIdFor } from "@/lib/auth";

export const maxDuration = 60;                       // the platform's limit — know it

export async function POST(request) {
  const user = await requireUser(request);                          // auth first
  const { chatId, text } = await request.json();
  const thread_id = await threadIdFor(user, chatId);                // server-derived (Day 20)

  const graph = await getGraph();
  const stream = await graph.stream(
    { messages: [new HumanMessage(text)] },
    { configurable: { thread_id }, streamMode: "messages", signal: request.signal }
  );
  // ...encode as SSE exactly as in Day 23 §4.7
}
```

```js
// lib/studybuddy.js — one graph and one checkpointer per process, created lazily
import { PostgresSaver } from "@langchain/langgraph-checkpoint-postgres";
let graphPromise;

export function getGraph() {
  graphPromise ??= (async () => {
    const checkpointer = PostgresSaver.fromConnString(process.env.DATABASE_URL);
    await checkpointer.setup();                      // idempotent table creation
    return buildStudyBuddy().compile({ checkpointer });
  })();
  return graphPromise;
}
```

The `??=` memoisation matters: building the graph and opening a pool per request is the
classic serverless connection leak.

### 4.2 Option B — your own service with background runs

The full service, verified (the test harness is at the bottom of the source this was run
from; in production `RUNS` is a Postgres table and the checkpointer is `PostgresSaver`):

```js
import http from "node:http";
import { randomUUID } from "node:crypto";
import { StateGraph, MessagesAnnotation, Annotation, Command, interrupt, START, END } from "@langchain/langgraph";
import { PostgresSaver } from "@langchain/langgraph-checkpoint-postgres";
import { AIMessage, HumanMessage } from "@langchain/core/messages";

const State = Annotation.Root({ ...MessagesAnnotation.spec, approved: Annotation() });

const checkpointer = PostgresSaver.fromConnString(process.env.DATABASE_URL);
await checkpointer.setup();

const graph = new StateGraph(State)
  .addNode("answer", async (s) => ({ messages: [new AIMessage(`echo: ${s.messages.at(-1).content}`)] }))
  .addNode("gate", (s) => {
    const decision = interrupt({ question: "Post this answer?", draft: s.messages.at(-1).content });
    return { approved: decision === "approve" };
  })
  .addEdge(START, "answer").addEdge("answer", "gate").addEdge("gate", END)
  .compile({ checkpointer });

const RUNS = new Map();                 // production: runs table (run_id, thread_id, status, error)
const inFlight = new Set();

function launch(threadId, payload) {
  const runId = randomUUID();
  RUNS.set(runId, { threadId, status: "pending" });
  const task = (async () => {
    RUNS.get(runId).status = "running";
    try {
      const result = await graph.invoke(payload, { configurable: { thread_id: threadId } });
      RUNS.get(runId).status = result.__interrupt__ ? "interrupted" : "success";
    } catch {
      RUNS.get(runId).status = "error";
    }
  })();
  inFlight.add(task);
  task.finally(() => inFlight.delete(task));
  return runId;
}

const readJson = async (req) => { let b = ""; for await (const c of req) b += c; return b ? JSON.parse(b) : {}; };
const send = (res, code, body) => { res.writeHead(code, { "Content-Type": "application/json" }); res.end(JSON.stringify(body)); };

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, "http://x");
  const parts = url.pathname.split("/").filter(Boolean);
  try {
    if (req.method === "GET" && url.pathname === "/healthz") return send(res, 200, { ok: true });

    // POST /threads/:tid/runs  → 202 { run_id }
    if (req.method === "POST" && parts[0] === "threads" && parts[2] === "runs" && parts.length === 3) {
      const { text } = await readJson(req);
      return send(res, 202, { run_id: launch(parts[1], { messages: [new HumanMessage(text)] }) });
    }

    // GET /threads/:tid/runs/:rid  → status + pending interrupts
    if (req.method === "GET" && parts[0] === "threads" && parts[2] === "runs" && parts.length === 4) {
      const run = RUNS.get(parts[3]);
      if (!run || run.threadId !== parts[1]) return send(res, 404, { error: "not found" });
      const snap = await graph.getState({ configurable: { thread_id: parts[1] } });
      return send(res, 200, {
        status: run.status,
        next: snap.next,
        pending: snap.tasks.flatMap((t) => t.interrupts.map((i) => i.value)),
        last_message: snap.values.messages?.at(-1)?.content ?? null,
      });
    }

    // POST /threads/:tid/resume  → 202 { run_id }
    if (req.method === "POST" && parts[0] === "threads" && parts[2] === "resume") {
      const { decision } = await readJson(req);
      return send(res, 202, { run_id: launch(parts[1], new Command({ resume: decision })) });
    }
    send(res, 404, { error: "not found" });
  } catch (err) {
    console.error(err);
    send(res, 500, { error: "internal error" });
  }
});

server.listen(process.env.PORT ?? 3000);

// graceful shutdown: stop accepting, let in-flight runs finish, close the pool
process.on("SIGTERM", () =>
  server.close(async () => {
    await Promise.allSettled([...inFlight]);
    await checkpointer.end();
    process.exit(0);
  })
);
```

> 🔒 **Omitted for length, required in production:** authentication, and checking that the
> authenticated user owns `:tid` before every read, run or resume (Day 20's IDOR warning, and
> Day 21's interrupt-id staleness check on resume).

This keeps runs in the API process. It survives client disconnects and long runs, but not a
process crash mid-run (the checkpoint survives; the *task* doesn't). §4.4 moves execution to
workers so a crash only costs a retry from the last checkpoint.

### 4.3 Option C — the LangGraph server and its client

```json
// langgraph.json
{
  "node_version": "20",
  "dependencies": ["."],
  "graphs": { "studybuddy": "./graph.mjs:graph" },
  "env": ".env"
}
```

```js
// graph.mjs — export the graph compiled WITHOUT a checkpointer
export const graph = new StateGraph(State)
  /* ...nodes and edges... */
  .compile();
```

```bash
npx @langchain/langgraph-cli dev          # local in-memory server on :2024
```

The client, from any Node service or browser-side code with an appropriate proxy:

```js
import { Client } from "@langchain/langgraph-sdk";

const client = new Client({ apiUrl: process.env.LANGGRAPH_URL });   // e.g. http://localhost:2024

// a conversation
const thread = await client.threads.create();

// run until done — or until it pauses
const result = await client.runs.wait(thread.thread_id, "studybuddy", {
  input: { messages: [{ role: "user", content: "hello from JS" }] },
});
console.log(result.__interrupt__?.[0]?.value);
// { question: "Post this answer?", draft: "echo: hello from JS" }

// resume the interrupt over HTTP
const done = await client.runs.wait(thread.thread_id, "studybuddy", { command: { resume: "reject" } });
console.log(done.approved);                                          // false

// stream a run
for await (const chunk of client.runs.stream(thread.thread_id, "studybuddy", {
  input: { messages: [{ role: "user", content: "stream" }] },
  streamMode: ["updates"],
})) {
  console.log(chunk.event, chunk.data);                              // "metadata", "updates", …
}

// a background run: returns immediately
const run = await client.runs.create(thread.thread_id, "studybuddy", {
  input: { messages: [{ role: "user", content: "make my study plan" }] },
});
console.log(run.status);                                             // "pending"
await client.runs.join(thread.thread_id, run.run_id);                // wait for it elsewhere

const state = await client.threads.getState(thread.thread_id);
```

All of those calls were verified against a running server. The client also exposes
`threads.getHistory`, `threads.updateState`, `runs.cancel`, `assistants.getGraph` and cron
jobs — Days 20–21's features, over HTTP.

### 4.4 Workers and a queue

When runs are long or bursty, separate *accepting* work from *doing* it. The contract is small
and the implementation depends on your queue (BullMQ, SQS, Postgres `SKIP LOCKED`, …):

```js
// api.js — enqueue and return
app.post("/threads/:tid/runs", requireUser, async (req, res) => {
  await assertOwnsThread(req.user, req.params.tid);
  const runId = randomUUID();
  await db.runs.insert({ runId, threadId: req.params.tid, status: "pending",
                         idempotencyKey: req.get("Idempotency-Key") });      // de-dupe retries
  await queue.add("run", { runId, threadId: req.params.tid, text: req.body.text });
  res.status(202).json({ run_id: runId });
});

// worker.js — pull, execute, record
queue.process("run", CONCURRENCY, async ({ runId, threadId, text }) => {
  await db.runs.update(runId, { status: "running", startedAt: new Date() });
  try {
    const result = await graph.invoke(
      text ? { messages: [new HumanMessage(text)] } : null,      // null = resume from checkpoint
      { configurable: { thread_id: threadId } }
    );
    await db.runs.update(runId, { status: result.__interrupt__ ? "interrupted" : "success" });
  } catch (err) {
    await db.runs.update(runId, { status: "error", error: String(err.message).slice(0, 500) });
    throw err;                                          // let the queue retry with backoff
  }
});
```

Why this is robust:

- **A worker crash loses nothing.** The checkpoint has every completed step; the queue
  redelivers the job; `invoke(null, config)` resumes from the last checkpoint (Day 20).
- **`CONCURRENCY` is your provider-rate-limit valve.** Queue depth absorbs bursts instead of
  429s.
- **The idempotency key** turns a client's retried POST into the same run, not a second one.

### 4.5 Docker for a self-hosted service

```dockerfile
# Dockerfile
FROM node:20-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

FROM node:20-slim
WORKDIR /app
ENV NODE_ENV=production
COPY --from=deps /app/node_modules ./node_modules
COPY . .
USER node                                        # never run as root
EXPOSE 3000
HEALTHCHECK CMD node -e "fetch('http://127.0.0.1:3000/healthz').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "server.mjs"]
```

```yaml
# compose.yaml — local production-like stack
services:
  api:
    build: .
    ports: ["3000:3000"]
    environment:
      DATABASE_URL: postgres://studybuddy:studybuddy@db:5432/studybuddy
      GROQ_API_KEY: ${GROQ_API_KEY}              # from your shell / .env, never baked in
    depends_on: [db]
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: studybuddy
      POSTGRES_PASSWORD: studybuddy
      POSTGRES_DB: studybuddy
    volumes: ["pgdata:/var/lib/postgresql/data"]
volumes:
  pgdata:
```

For the LangGraph server, let the CLI write the Dockerfile: `npx @langchain/langgraph-cli dockerfile Dockerfile`.

### 4.6 Health, readiness and shutdown

```js
// liveness: is the process alive?
if (url.pathname === "/healthz") return send(res, 200, { ok: true });

// readiness: can it serve? (dependencies reachable)
if (url.pathname === "/readyz") {
  try {
    await pool.query("SELECT 1");
    return send(res, 200, { ready: true });
  } catch {
    return send(res, 503, { ready: false });
  }
}
```

Keep liveness cheap (a slow database shouldn't get healthy processes restarted); make
readiness honest (a process that can't reach Postgres shouldn't receive traffic). And handle
`SIGTERM` as in §4.2: stop accepting, drain in-flight runs up to a deadline, close pools. On
a rolling deploy, that's the difference between "deploys are invisible" and "every deploy
drops conversations".

---

## 5. Code — Python

### 5.1 Option A — inside your app

```python
# app.py — FastAPI, one graph per process via the lifespan
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncPostgresSaver.from_conn_string(os.environ["DATABASE_URL"]) as checkpointer:
        await checkpointer.setup()                                  # idempotent
        app.state.graph = build_studybuddy().compile(checkpointer=checkpointer)
        yield                                                       # the pool lives for the process

api = FastAPI(lifespan=lifespan)

@api.post("/chat")
async def chat(body: ChatBody, user=Depends(require_user)):
    thread_id = await thread_id_for(user, body.chat_id)             # server-derived
    # ...stream app.state.graph.astream(...) as SSE, exactly as Day 23 §5.6
```

`from_conn_string` is a context manager (verified), so the lifespan is the right place for it:
entered once at startup, closed at shutdown.

### 5.2 Option B — your own service with background runs

Verified (with `InMemorySaver` and FastAPI's `TestClient`; swap in `AsyncPostgresSaver` and a
runs table for production):

```python
import asyncio, os, uuid
from contextlib import asynccontextmanager
from typing import Annotated, TypedDict

from fastapi import FastAPI, HTTPException
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.types import Command, interrupt
from pydantic import BaseModel


class State(TypedDict):
    messages: Annotated[list, add_messages]
    approved: bool


async def answer(state: State) -> dict:
    return {"messages": [AIMessage(f"echo: {state['messages'][-1].content}")]}


def gate(state: State) -> dict:
    decision = interrupt({"question": "Post this answer?", "draft": state["messages"][-1].content})
    return {"approved": decision == "approve"}


def build(checkpointer):
    b = StateGraph(State)
    b.add_node("answer", answer)
    b.add_node("gate", gate)
    b.add_edge(START, "answer")
    b.add_edge("answer", "gate")
    b.add_edge("gate", END)
    return b.compile(checkpointer=checkpointer)


RUNS: dict[str, dict] = {}          # production: runs table (run_id, thread_id, status, error)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncPostgresSaver.from_conn_string(os.environ["DATABASE_URL"]) as checkpointer:
        await checkpointer.setup()
        app.state.graph = build(checkpointer)
        app.state.tasks = set()
        yield
        # graceful shutdown: let in-flight runs finish before the pool closes
        if app.state.tasks:
            await asyncio.wait(app.state.tasks, timeout=30)


api = FastAPI(lifespan=lifespan)


class StartBody(BaseModel):
    text: str


class ResumeBody(BaseModel):
    decision: str


async def execute(run_id: str, thread_id: str, payload):
    RUNS[run_id]["status"] = "running"
    try:
        result = await api.state.graph.ainvoke(payload, {"configurable": {"thread_id": thread_id}})
        RUNS[run_id]["status"] = "interrupted" if "__interrupt__" in result else "success"
    except Exception:
        RUNS[run_id]["status"] = "error"


def launch(thread_id: str, payload) -> str:
    run_id = str(uuid.uuid4())
    RUNS[run_id] = {"thread_id": thread_id, "status": "pending"}
    task = asyncio.create_task(execute(run_id, thread_id, payload))
    api.state.tasks.add(task)
    task.add_done_callback(api.state.tasks.discard)           # keep a reference until done
    return run_id


@api.post("/threads/{thread_id}/runs", status_code=202)
async def start_run(thread_id: str, body: StartBody):
    return {"run_id": launch(thread_id, {"messages": [HumanMessage(body.text)]})}


@api.get("/threads/{thread_id}/runs/{run_id}")
async def get_run(thread_id: str, run_id: str):
    run = RUNS.get(run_id)
    if not run or run["thread_id"] != thread_id:
        raise HTTPException(404)
    snap = await api.state.graph.aget_state({"configurable": {"thread_id": thread_id}})
    return {
        "status": run["status"],
        "next": list(snap.next),
        "pending": [i.value for t in snap.tasks for i in t.interrupts],
        "last_message": snap.values["messages"][-1].content if snap.values.get("messages") else None,
    }


@api.post("/threads/{thread_id}/resume", status_code=202)
async def resume(thread_id: str, body: ResumeBody):
    return {"run_id": launch(thread_id, Command(resume=body.decision))}


@api.get("/healthz")
async def health():
    return {"ok": True}
```

> ⚠️ **Keep a reference to background tasks.** `asyncio.create_task` holds only a weak
> reference; a task nobody references can be garbage-collected mid-run. The `tasks` set plus
> `add_done_callback(discard)` is the standard fix — and it's also what graceful shutdown
> waits on.

Same security note as JS: authenticate, and check thread ownership on every route.

### 5.3 Option C — the LangGraph server and its client

```json
// langgraph.json
{
  "dependencies": ["."],
  "graphs": { "studybuddy": "./graph.py:graph" },
  "env": ".env"
}
```

```python
# graph.py — compiled WITHOUT a checkpointer (the server rejects one — verified)
graph = builder.compile()
```

```bash
pip install "langgraph-cli[inmem]"
langgraph dev                     # local in-memory server on :2024 (verified)
langgraph dockerfile Dockerfile   # generate a Dockerfile (verified, offline)
langgraph build -t studybuddy     # build the image
```

```python
from langgraph_sdk import get_client
from langgraph_sdk.schema import Command

client = get_client(url="http://127.0.0.1:2024")

thread = await client.threads.create()
tid = thread["thread_id"]

result = await client.runs.wait(tid, "studybuddy", input={"messages": [{"role": "user", "content": "hello"}]})
print(result["__interrupt__"])
# [{'value': {'question': 'Post this answer?', 'draft': 'echo: hello'}, 'id': 'd3108f77…'}]

state = await client.threads.get_state(tid)
print(state["next"])                                        # ['gate']

resumed = await client.runs.wait(tid, "studybuddy", command=Command(resume="approve"))
print(resumed["approved"])                                  # True

print(len(await client.threads.get_history(tid)))           # 4

async for chunk in client.runs.stream(tid, "studybuddy",
        input={"messages": [{"role": "user", "content": "stream me"}]},
        stream_mode=["updates", "values"]):
    print(chunk.event)                                      # metadata, values, updates, …

run = await client.runs.create(tid, "studybuddy", input={"messages": [{"role": "user", "content": "bg"}]})
print(run["status"])                                        # pending
await client.runs.join(tid, run["run_id"])
```

`get_sync_client` gives the same API without `await`. For production, the server reads
`POSTGRES_URI` (and a Redis URI for its task queue) from the environment.

### 5.4 Workers and a queue

```python
# api.py — enqueue and return
@api.post("/threads/{thread_id}/runs", status_code=202)
async def start_run(thread_id: str, body: StartBody, user=Depends(require_user),
                    idempotency_key: str | None = Header(default=None)):
    await assert_owns_thread(user, thread_id)
    existing = await db.find_run_by_key(idempotency_key) if idempotency_key else None
    if existing:
        return {"run_id": existing.run_id}                  # retried POST → same run
    run_id = str(uuid.uuid4())
    await db.insert_run(run_id, thread_id, "pending", idempotency_key)
    await queue.enqueue("run", run_id=run_id, thread_id=thread_id, text=body.text)
    return {"run_id": run_id}

# worker.py — pull, execute, record
async def handle_run(run_id: str, thread_id: str, text: str | None):
    await db.update_run(run_id, status="running")
    try:
        payload = {"messages": [HumanMessage(text)]} if text else None     # None = resume
        result = await graph.ainvoke(payload, {"configurable": {"thread_id": thread_id}})
        await db.update_run(run_id, status="interrupted" if "__interrupt__" in result else "success")
    except Exception as e:
        await db.update_run(run_id, status="error", error=str(e)[:500])
        raise                                               # let the queue retry
```

Celery, RQ, Arq, SQS consumers or a Postgres `SKIP LOCKED` loop all fit this shape. The
properties are the same as in JS: crash-safe via checkpoints, concurrency as a rate-limit
valve, idempotent submission.

### 5.5 Docker for a self-hosted service

```dockerfile
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --create-home app
USER app
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz').status==200 else 1)"
CMD ["uvicorn", "service:api", "--host", "0.0.0.0", "--port", "8000"]
```

Pin exact versions in `requirements.txt` (or use `uv`/`poetry` lockfiles). Run the uvicorn
process count according to your CPU, not your expected concurrency: async workers already
handle many in-flight runs each.

### 5.6 Health, readiness and shutdown

```python
@api.get("/healthz")
async def healthz():
    return {"ok": True}

@api.get("/readyz")
async def readyz():
    try:
        await db_pool.execute("SELECT 1")
        return {"ready": True}
    except Exception:
        raise HTTPException(503, "not ready")
```

Shutdown is handled by the lifespan in §5.2: uvicorn stops accepting on `SIGTERM`, the lifespan
waits for in-flight tasks up to a deadline, and exiting the `async with` closes the pool.

### 5.7 The JS ↔ Python translation for today

| Concept | JavaScript | Python |
|---|---|---|
| Postgres checkpointer | `PostgresSaver.fromConnString(url)` → saver | `PostgresSaver.from_conn_string(url)` → **context manager** |
| async variant | same class | `AsyncPostgresSaver.from_conn_string` |
| create tables | `await saver.setup()` | `saver.setup()` / `await saver.setup()` |
| close | `await saver.end()` | exit the `with` / `async with` |
| long-term store | `@langchain/langgraph-checkpoint-postgres/store` | `langgraph.store.postgres.PostgresStore` |
| server CLI | `npx @langchain/langgraph-cli dev` | `langgraph dev` (`pip install "langgraph-cli[inmem]"`) |
| config | `langgraph.json` with `node_version` | `langgraph.json` |
| client | `new Client({ apiUrl })` from `@langchain/langgraph-sdk` | `get_client(url=...)` from `langgraph_sdk` |
| blocking run | `client.runs.wait(tid, "graph", { input })` | `await client.runs.wait(tid, "graph", input=...)` |
| resume | `{ command: { resume: "approve" } }` | `command=Command(resume="approve")` |
| state | `client.threads.getState(tid)` | `await client.threads.get_state(tid)` |
| background run | `client.runs.create(...)` + `client.runs.join(...)` | `client.runs.create(...)` + `client.runs.join(...)` |
| background task in-process | a promise kept in a `Set` | `asyncio.create_task` kept in a `set` |
| graceful shutdown | `SIGTERM` → `server.close` → drain | lifespan exit → `asyncio.wait(tasks)` |

---

## 6. Under the hood

### 6.1 What the LangGraph server is made of

```
   HTTP API          assistants · threads · runs · crons · store
   task queue        runs are enqueued and picked up by workers (Redis in production)
   checkpointer      Postgres, per thread  (in-memory for `dev`)
   workers           execute graph runs; `--n-jobs-per-worker` caps concurrency per worker
   streaming         runs publish events; runs.stream / runs.join subscribe
```

That's the architecture of §4.4 — API, queue, workers, Postgres — packaged. Knowing it lets you
reason about the server the same way you'd reason about your own: queue depth, worker
concurrency, Postgres load.

### 6.2 A database schema for option B

```sql
-- your application tables, alongside the checkpointer's own tables
CREATE TABLE conversations (
  thread_id    text PRIMARY KEY,               -- the checkpointer's key
  user_id      text NOT NULL REFERENCES users(id),
  title        text,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON conversations (user_id, updated_at DESC);

CREATE TABLE runs (
  run_id          uuid PRIMARY KEY,
  thread_id       text NOT NULL REFERENCES conversations(thread_id) ON DELETE CASCADE,
  status          text NOT NULL CHECK (status IN ('pending','running','interrupted','success','error','cancelled')),
  idempotency_key text UNIQUE,
  error           text,
  model           text,
  prompt_version  text,                          -- Day 25: slice metrics by version
  input_tokens    int, output_tokens int,
  created_at      timestamptz NOT NULL DEFAULT now(),
  finished_at     timestamptz
);
CREATE INDEX ON runs (thread_id, created_at DESC);
CREATE INDEX ON runs (status) WHERE status IN ('pending','running');

CREATE TABLE approvals (                          -- Day 21: who approved what
  id            bigserial PRIMARY KEY,
  run_id        uuid NOT NULL REFERENCES runs(run_id),
  interrupt_id  text NOT NULL,
  decided_by    text NOT NULL,
  decision      jsonb NOT NULL,
  decided_at    timestamptz NOT NULL DEFAULT now()
);
```

`conversations.thread_id` is where ownership lives — the IDOR check is a join against it.
Deleting a user cascades to their conversations and runs; delete their checkpoints
(`delete_thread`) and their store namespace in the same job (Day 20's GDPR note).

### 6.3 Where time goes in a run

```
   model calls           ████████████████████████████████  ~85–95%
   tool calls (network)  ████                                ~5–10%
   checkpoint writes     ▌                                   ~1%   (small state!)
   your code             ▏                                   <1%
```

That's why horizontal scaling of *workers* rarely helps latency, and why the real levers are:
fewer model calls (Day 22's measurements), smaller prompts (Day 18), parallel tool calls
(Day 19 and 22), streaming for perceived speed (Day 23), and faster or cheaper models where
quality allows (Day 25 tells you where it does).

### 6.4 Scaling milestones

```
   10 students        one process, SQLite or Postgres, option A. Ship it.
   1,000              Postgres checkpointer, two instances behind a load balancer,
                      streaming with cancellation, tracing on.
   100,000            decoupled runs (B or C), a queue, worker concurrency tuned to
                      provider limits, a fallback provider, Redis for rate limits,
                      eval suite gating deploys, cost dashboards.
   1,000,000          multiple providers or reserved capacity, model routing (cheap
                      model for easy questions), aggressive state and prompt size
                      discipline, per-tenant limits, regional deployment, read replicas
                      for history views, retention jobs for checkpoints.
```

Each step adds something because a number from §3.7 forced it — not because a diagram said so.

---

## 7. Common mistakes

### ❌ 1. State in the process

```js
❌ const conversations = new Map();              // lost on deploy; wrong with 2+ instances
❌ .compile({ checkpointer: new MemorySaver() })  // same thing, with extra steps
✅ .compile({ checkpointer: PostgresSaver.fromConnString(process.env.DATABASE_URL) })
```

Tuesday's lost conversations. The golden rule: compute stateless, state in a database.

### ❌ 2. Long runs bound to a request

```
❌ POST /study-plan  → waits 90 s → load balancer times out at 60 → client retries → 2 runs
✅ POST /threads/:tid/runs → 202 { run_id } ; GET status ; idempotency key on the POST
```

Wednesday's duplicate bill.

### ❌ 3. Shipping a graph compiled with a checkpointer to the LangGraph server

```python
❌ graph = builder.compile(checkpointer=InMemorySaver())
   # ValueError: Heads up! Your graph ... includes a custom checkpointer ... (verified)
✅ graph = builder.compile()          # the server supplies persistence; set POSTGRES_URI
```

### ❌ 4. Building the graph (and the pool) per request

```js
❌ export async function POST(req) { const cp = PostgresSaver.fromConnString(url); ... }
✅ const getGraph = memoised once per process   // §4.1
```

On serverless this exhausts Postgres connections within minutes of real traffic.

### ❌ 5. Unreferenced background tasks in Python

```python
❌ asyncio.create_task(execute(...))                 # may be garbage-collected mid-run
✅ task = asyncio.create_task(execute(...)); tasks.add(task); task.add_done_callback(tasks.discard)
```

### ❌ 6. No graceful shutdown

Every rolling deploy kills in-flight runs. Handle `SIGTERM`: stop accepting, drain up to a
deadline, close pools. With checkpoints, even a hard kill is recoverable — but only if
something re-queues the run.

### ❌ 7. Secrets in images or `langgraph.json`

```
❌ ENV GROQ_API_KEY=gsk_...            ❌ committed .env
✅ injected at runtime from a secret manager; .env only for local dev, git-ignored
```

### ❌ 8. Redis as the source of truth

If wiping Redis loses conversations or approvals, the design is wrong. Queue, locks, rate
limits, caches: yes. Checkpoints and audit logs: Postgres.

### ❌ 9. Scaling compute to fix a provider bottleneck

Adding workers when the constraint is 50 model calls/second against a rate limit only produces
more 429s. Do §3.7's arithmetic first; the bottleneck is usually the provider, tokens or
state size — not CPU.

### ❌ 10. Liveness checks that touch dependencies

A slow database makes `/healthz` fail, the orchestrator restarts every healthy process, and a
blip becomes an outage. Liveness: cheap. Readiness: checks dependencies.

### ❌ 11. Unpinned dependencies

```
❌ "langchain": "^1"          ❌ langgraph>=1
✅ lockfiles + the Day 25 eval suite on every upgrade
```

This book found behaviour differences across minor versions and between languages. An
unpinned deploy is an unreviewed upgrade.

### ❌ 12. Trusting a client-supplied `thread_id` in the API

Still the most common vulnerability in agent backends (Day 20). Every route that takes a
thread or run id checks ownership.

---

## 8. Exercises

### Exercise 1 — Start, poll, resume ●●○○○

Build option B's service with a graph that pauses for approval. Test it end to end (no API key,
no network): start a run, poll until it's no longer running, show the pending interrupt,
resume it, and confirm a run can't be read through a different thread.

<details>
<summary>✅ Solution</summary>

The complete services are §4.2 (JavaScript) and §5.2 (Python). The test harnesses that
verified them:

**JavaScript** — append to the §4.2 service, using `MemorySaver` instead of Postgres, and run
with `node service.mjs test`:

```js
if (process.argv[2] === "test") {
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  const base = `http://127.0.0.1:${server.address().port}`;
  const call = (method, path, body) =>
    fetch(base + path, { method, headers: { "Content-Type": "application/json" }, body: body && JSON.stringify(body) });

  const poll = async (tid, rid) => {
    for (let i = 0; i < 30; i++) {
      const s = await (await call("GET", `/threads/${tid}/runs/${rid}`)).json();
      if (!["pending", "running"].includes(s.status)) return s;
      await new Promise((r) => setTimeout(r, 100));
    }
  };

  const start = await call("POST", "/threads/t1/runs", { text: "hello" });
  const { run_id } = await start.json();
  console.log("start ->", start.status);                                     // 202
  console.log("after polling:", await poll("t1", run_id));
  const { run_id: resumeId } = await (await call("POST", "/threads/t1/resume", { decision: "approve" })).json();
  console.log("after resume:", await poll("t1", resumeId));
  console.log("wrong thread ->", (await call("GET", `/threads/other/runs/${run_id}`)).status);   // 404
  server.close();
}
```

**Python** — the §5.2 service with `InMemorySaver`, tested with FastAPI's `TestClient`:

```python
import time
from fastapi.testclient import TestClient

def poll(client, tid, rid):
    for _ in range(30):
        s = client.get(f"/threads/{tid}/runs/{rid}").json()
        if s["status"] not in ("pending", "running"):
            return s
        time.sleep(0.1)

with TestClient(api) as client:                       # runs the lifespan
    run_id = client.post("/threads/t1/runs", json={"text": "hello"}).json()["run_id"]
    print("after polling:", poll(client, "t1", run_id))
    resume_id = client.post("/threads/t1/resume", json={"decision": "approve"}).json()["run_id"]
    print("after resume:", poll(client, "t1", resume_id))
    print("wrong thread ->", client.get(f"/threads/other/runs/{run_id}").status_code)
```

**Verified output (identical in both languages)**

```
start -> 202 · immediately: running
after polling: { status: "interrupted", next: ["gate"],
                 pending: [{ question: "Post this answer?", draft: "echo: hello" }], last_message: "echo: hello" }
after resume:  { status: "success", next: [], pending: [], last_message: "echo: hello" }
wrong thread -> 404
```

**What to notice.** The status comes from *your* runs table; `next` and `pending` come from the
*checkpointer*. Two sources of truth that agree: the runs table answers "what happened to this
job?", the checkpoint answers "where is the conversation?". The 404 on the wrong thread is the
ownership rule expressed in the URL structure — and in production it's joined against the
authenticated user, too.
</details>

---

### Exercise 2 — Run the LangGraph server locally ●●○○○

1. Put a graph that pauses for approval behind `langgraph.json`.
2. Start the dev server.
3. From a client script (either language): create a thread, run until the interrupt, resume
   it, stream a second run, and start a background run you `join`.
4. Then compile the graph *with* `InMemorySaver`, restart, and record what happens.

<details>
<summary>✅ Solution</summary>

**Project**

```
studybuddy-server/
├── langgraph.json
├── graph.py            (or graph.mjs)
└── .env
```

```json
{
  "dependencies": ["."],
  "graphs": { "studybuddy": "./graph.py:graph" },
  "env": ".env"
}
```

**Python graph** (`graph.py`)

```python
from typing import Annotated, TypedDict
from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.types import interrupt

class State(TypedDict):
    messages: Annotated[list, add_messages]
    approved: bool

def answer(state: State) -> dict:
    return {"messages": [AIMessage(f"echo: {state['messages'][-1].content}")]}

def gate(state: State) -> dict:
    decision = interrupt({"question": "Post this answer?", "draft": state["messages"][-1].content})
    return {"approved": decision == "approve"}

builder = StateGraph(State)
builder.add_node("answer", answer)
builder.add_node("gate", gate)
builder.add_edge(START, "answer")
builder.add_edge("answer", "gate")
builder.add_edge("gate", END)
graph = builder.compile()             # no checkpointer
```

**JavaScript graph** (`graph.mjs`, with `"node_version": "20"` and `"./graph.mjs:graph"` in `langgraph.json`)

```js
import { StateGraph, MessagesAnnotation, Annotation, START, END, interrupt } from "@langchain/langgraph";
import { AIMessage } from "@langchain/core/messages";

const State = Annotation.Root({ ...MessagesAnnotation.spec, approved: Annotation() });

export const graph = new StateGraph(State)
  .addNode("answer", (s) => ({ messages: [new AIMessage(`echo: ${s.messages.at(-1).content}`)] }))
  .addNode("gate", (s) => {
    const decision = interrupt({ question: "Post this answer?", draft: s.messages.at(-1).content });
    return { approved: decision === "approve" };
  })
  .addEdge(START, "answer").addEdge("answer", "gate").addEdge("gate", END)
  .compile();
```

**Start**

```bash
pip install "langgraph-cli[inmem]" && langgraph dev --no-browser     # Python
npx @langchain/langgraph-cli dev --no-browser                         # JavaScript
```

**Client — Python**

```python
import asyncio
from langgraph_sdk import get_client
from langgraph_sdk.schema import Command

async def main():
    client = get_client(url="http://127.0.0.1:2024")
    tid = (await client.threads.create())["thread_id"]

    r = await client.runs.wait(tid, "studybuddy", input={"messages": [{"role": "user", "content": "hello"}]})
    print("interrupt:", r["__interrupt__"][0]["value"])

    r = await client.runs.wait(tid, "studybuddy", command=Command(resume="approve"))
    print("approved:", r["approved"])

    t2 = (await client.threads.create())["thread_id"]
    async for chunk in client.runs.stream(t2, "studybuddy",
            input={"messages": [{"role": "user", "content": "stream me"}]}, stream_mode=["updates"]):
        print("event:", chunk.event)

    t3 = (await client.threads.create())["thread_id"]
    run = await client.runs.create(t3, "studybuddy", input={"messages": [{"role": "user", "content": "bg"}]})
    print("created:", run["status"])
    await client.runs.join(t3, run["run_id"])
    print("joined:", (await client.runs.get(t3, run["run_id"]))["status"])

asyncio.run(main())
```

**Client — JavaScript**

```js
import { Client } from "@langchain/langgraph-sdk";
const client = new Client({ apiUrl: "http://127.0.0.1:2024" });

const { thread_id } = await client.threads.create();
const r1 = await client.runs.wait(thread_id, "studybuddy", { input: { messages: [{ role: "user", content: "hello" }] } });
console.log("interrupt:", r1.__interrupt__[0].value);

const r2 = await client.runs.wait(thread_id, "studybuddy", { command: { resume: "approve" } });
console.log("approved:", r2.approved);

const t2 = await client.threads.create();
for await (const chunk of client.runs.stream(t2.thread_id, "studybuddy", {
  input: { messages: [{ role: "user", content: "stream me" }] }, streamMode: ["updates"],
})) console.log("event:", chunk.event);

const t3 = await client.threads.create();
const run = await client.runs.create(t3.thread_id, "studybuddy", { input: { messages: [{ role: "user", content: "bg" }] } });
console.log("created:", run.status);
await client.runs.join(t3.thread_id, run.run_id);
console.log("joined:", (await client.runs.get(t3.thread_id, run.run_id)).status);
```

**Verified results**

```
interrupt: {'question': 'Post this answer?', 'draft': 'echo: hello'}
approved: True
event: metadata · event: updates · …
created: pending
joined: success
```

**Step 4 — compiled with a checkpointer:** the server refuses to load the graph —
`ValueError: Heads up! Your graph 'graph' from './graph.py' includes a custom checkpointer (type
InMemorySaver). With LangGraph API, persistence is handled automatically by the platform…` — and
points you to `POSTGRES_URI`.

**What you got for free:** per-thread persistence, interrupts over HTTP, streaming, background
runs and joins — exactly what Exercise 1 made you build by hand. That trade (features vs another
runtime to operate) is the whole A/B/C decision.
</details>

---

### Exercise 3 — Break it five ways ●●○○○

Predict, then check your reasoning.

1. Two API instances behind a load balancer, each with `MemorySaver`. A student sends three
   messages.
2. A 90-second run behind a 60-second load-balancer timeout, with a client that retries on
   failure.
3. A Python service that starts runs with `asyncio.create_task` and never stores the task.
4. A serverless route that opens a new Postgres checkpointer on every request, under 300
   concurrent requests.
5. A rolling deploy with no `SIGTERM` handling while 40 runs are in flight.

<details>
<summary>✅ Solution</summary>

| # | Symptom | Why | Fix |
|---|---|---|---|
| 1 | Conversation randomly "forgets" — roughly half the turns land on the instance that never saw the earlier ones | state lives in each process | shared checkpointer (Day 20) |
| 2 | The client sees an error at 60 s, retries, and the run executes twice — two results, two bills | the run is bound to the request; retries aren't idempotent | start/poll with an idempotency key |
| 3 | Occasional runs that start and silently never finish | the event loop holds only a weak reference to tasks | keep tasks in a set until done |
| 4 | `too many connections` errors from Postgres, then total failure | each invocation opens its own pool | memoise per instance + a connection pooler |
| 5 | 40 runs die mid-step; users see errors or stuck "running" statuses | the process is killed with work in flight | drain on `SIGTERM`; mark orphaned runs and re-queue from the last checkpoint |

**Repro for #1 (no servers needed)** — two "instances" are just two graphs with separate
in-memory checkpointers, alternating:

```js
import { StateGraph, MessagesAnnotation, MemorySaver, START, END } from "@langchain/langgraph";
import { AIMessage, HumanMessage } from "@langchain/core/messages";

const build = () => new StateGraph(MessagesAnnotation)
  .addNode("echo", (s) => ({ messages: [new AIMessage(`I have seen ${s.messages.length} messages`)] }))
  .addEdge(START, "echo").addEdge("echo", END)
  .compile({ checkpointer: new MemorySaver() });

const instances = [build(), build()];                         // two processes behind a load balancer
const config = { configurable: { thread_id: "student-42" } };

for (let turn = 0; turn < 3; turn++) {
  const instance = instances[turn % 2];                       // round-robin
  const out = await instance.invoke({ messages: [new HumanMessage(`turn ${turn + 1}`)] }, config);
  console.log(`turn ${turn + 1} (instance ${turn % 2}):`, out.messages.at(-1).content);
}
// turn 1 (instance 0): I have seen 1 messages
// turn 2 (instance 1): I have seen 1 messages     ← forgot turn 1
// turn 3 (instance 0): I have seen 3 messages
```

```python
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, MessagesState, START, END

def build():
    b = StateGraph(MessagesState)
    b.add_node("echo", lambda s: {"messages": [AIMessage(f"I have seen {len(s['messages'])} messages")]})
    b.add_edge(START, "echo"); b.add_edge("echo", END)
    return b.compile(checkpointer=InMemorySaver())

instances = [build(), build()]
config = {"configurable": {"thread_id": "student-42"}}
for turn in range(3):
    out = instances[turn % 2].invoke({"messages": [HumanMessage(f"turn {turn + 1}")]}, config)
    print(f"turn {turn + 1} (instance {turn % 2}):", out["messages"][-1].content)
```

Replace both `MemorySaver`s with one shared checkpointer object (standing in for Postgres) and
every turn sees the full history. That one-line change is the whole golden rule.

**Ranking.** #4 is loud. #1, #3 and #5 are intermittent, which makes them hard to reproduce and
easy to blame on "the AI". #2 costs money quietly. All five are prevented by the same short list:
**shared state, decoupled runs, idempotent submission, referenced tasks, graceful shutdown.**
</details>

---

### Exercise 4 — 🎯 StudyBuddy's production architecture ●●●●○

Write the deployment design for StudyBuddy at 100,000 students, as a short design doc with:

1. traffic and capacity estimates (show the arithmetic),
2. which option (A/B/C) serves chat and which serves long jobs,
3. the data layer (what's in Postgres, what's in Redis),
4. reliability and cost controls, referencing Days 24–25,
5. a `compose.yaml` for a production-like local stack.

<details>
<summary>✅ Solution</summary>

**1 — Capacity**

```
   100,000 registered · 20% daily active          = 20,000 students/day
   × 10 chat turns/day                             = 200,000 chat runs/day
   + 1 study plan per 5 active students            =   4,000 long runs/day

   peak hour ≈ 15% of the day                      = 30,000 chat runs/hour ≈ 8.3/s
   chat: ~2.5 model calls, ~4 s each run           ≈ 21 model calls/s, ~33 chat runs in flight
   study plans: ~12 model calls, ~60 s, peak ≈ 0.2/s ≈ 12 in flight, +2.4 model calls/s

   tokens: 200,000 × 3,000 + 4,000 × 25,000        ≈ 700 million tokens/day
   checkpoints: 204,000 runs × ~4 writes            ≈ 820,000 writes/day (~35/s peak)
```

Conclusions: compute is small; the provider's rate limit (≈25 calls/s at peak, with headroom
for retries) and the token bill are the constraints; Postgres load is modest *if state stays
small*.

**2 — Serving**

| Workload | Option | Why |
|---|---|---|
| chat turns | **A** — Next.js route handlers, streamed (Day 23) | short, interactive, cancellable |
| study plans, essay grading with approval | **C** — LangGraph server, background runs | long, pause for teachers, must survive deploys |
| notes & progress tools | **MCP servers** (Day 26) | shared by chat, graders and staff tools |

**3 — Data**

```
   Postgres  checkpoints (chat via PostgresSaver; the LangGraph server via POSTGRES_URI)
             store: student profiles & preferences (Day 18)
             conversations, runs, approvals, audit
             pgvector: note embeddings (Day 11)
   Redis     LangGraph server task queue · rate limits per student and per provider ·
             circuit-breaker state (Day 24) · short-TTL retrieval cache
```

**4 — Reliability and cost**

- Provider: client retries on 429/5xx only; fallback to a second provider (Day 24); a shared
  limiter sized at 80% of quota; worker concurrency as the valve for long runs.
- Agents: model-call limits (chat 6, study plans 20), tool retries only on idempotent tools,
  PII redaction, approval gates on anything that posts or emails.
- Cost: per-run token metrics labelled with prompt version and model (Day 25); route easy
  questions to a cheaper model after evals show no quality loss; alert at 2× baseline cost per
  conversation.
- Quality: the eval suite gates deploys; online groundedness sampling; thumbs-down → dataset.

**5 — `compose.yaml`** (production-like local stack for option A + Postgres + Redis)

```yaml
services:
  web:
    build: ./web
    ports: ["3000:3000"]
    environment:
      DATABASE_URL: postgres://studybuddy:studybuddy@db:5432/studybuddy
      REDIS_URL: redis://cache:6379
      LANGGRAPH_URL: http://agents:8000
      GROQ_API_KEY: ${GROQ_API_KEY}
    depends_on: [db, cache]
  agents:
    image: studybuddy-agents          # built with: langgraph build -t studybuddy-agents
    ports: ["8123:8000"]
    environment:
      POSTGRES_URI: postgres://studybuddy:studybuddy@db:5432/studybuddy?sslmode=disable
      REDIS_URI: redis://cache:6379
      GROQ_API_KEY: ${GROQ_API_KEY}
    depends_on: [db, cache]
  db:
    image: pgvector/pgvector:pg16
    environment: { POSTGRES_USER: studybuddy, POSTGRES_PASSWORD: studybuddy, POSTGRES_DB: studybuddy }
    volumes: ["pgdata:/var/lib/postgresql/data"]
  cache:
    image: redis:7
volumes:
  pgdata:
```

> The environment variable names the LangGraph server image reads (`POSTGRES_URI`, the Redis
> URI, and any licence or LangSmith keys a self-hosted deployment needs) vary by version and
> deployment type — confirm them in the docs for the version you run. `POSTGRES_URI` is the one
> the server's own error message pointed to in our test.

**Why this design holds up in review:** every component exists because a number in part 1 or a
failure from this week forced it; the interactive path stays simple; the durable path uses the
runtime built for it; and cost, quality and reliability each have a metric and an owner.
</details>

---

### Exercise 5 — Design review: "just put it on serverless" ●●●○○

A team proposes: *"Deploy the whole StudyBuddy agent — including the essay grader that runs 3–5
minutes and waits for teacher approval — as serverless functions with a 60-second limit. Store
conversations in a global variable for speed. Use Redis for checkpoints because Postgres is
slow."* Review it.

<details>
<summary>✅ Solution</summary>

| # | Problem | Consequence | Fix |
|---|---|---|---|
| 1 | 3–5 minute grader vs a 60 s limit | every grading run is killed mid-way | background runs on workers or the LangGraph server; functions only enqueue |
| 2 | waiting for teacher approval inside a function | approvals take hours; a function can't wait | `interrupt()` + checkpointer; resume is a separate request (Day 21) |
| 3 | conversations in a global variable | each instance has its own globals; cold starts wipe them | shared checkpointer |
| 4 | Redis as the checkpoint store "because Postgres is slow" | an eviction or restart loses conversations and pending approvals | Postgres for checkpoints; keep state small (the real cause of slowness); Redis for queue/cache |
| 5 | (implicit) a pool per invocation | connection exhaustion under load | memoised clients + a pooler |
| 6 | (implicit) no idempotency | retries after timeouts double-grade and double-post | idempotency keys on run creation and on posting grades |

**What to keep from the proposal:** serverless is a good fit for the *interactive API* — chat
turns, starting runs, reading status, resuming approvals. Those are short and bursty.

**The corrected shape**

```
   serverless API ── POST /essays/:id/grade ──► enqueue ──► workers / LangGraph server
         │                                                     │  grade (3–5 min)
         │                                                     │  interrupt() → awaiting teacher
         ├── GET  /runs/:id  (status, pending approval)  ◄──────┤  checkpoints in Postgres
         └── POST /runs/:id/resume  (teacher decision)   ──────►┘  resume → post grade (idempotent)
```

**On "Postgres is slow".** Ask what's slow. If checkpoint writes are slow, state is almost
certainly too big — retrieved essays, rubric text or full grading transcripts in graph state
(Day 18). Store the essay once, keep its id in state, and a checkpoint write is a few kilobytes.
Swapping to an in-memory store to hide that trades a performance problem for a data-loss one.
</details>

---

## 9. Interview questions

### Basic

**Q1. What does "stateless compute, state in a database" mean for an agent?**

No conversation or run state lives in the process: the graph is built once per process, and
every request loads and saves state through a shared checkpointer keyed by `thread_id`. Then any
instance can serve any turn, deploys don't lose conversations, and you scale by adding instances.

---

**Q2. Why shouldn't a long agent run be tied to an HTTP request?**

Requests have timeouts (load balancers, serverless limits, clients), disconnects cancel work,
and retries duplicate it. Decouple: start the run and return 202 with a run id, then stream or
poll its status, and resume interrupts with a separate request.

---

**Q3. What is the LangGraph server?**

A runtime that serves compiled graphs described in `langgraph.json` as an HTTP API: assistants,
threads with built-in persistence, blocking/streaming/background runs, interrupts and resume,
state history, crons. You run it locally with `langgraph dev` and talk to it with
`@langchain/langgraph-sdk` or `langgraph_sdk`.

---

**Q4. Why does the LangGraph server reject a graph compiled with a checkpointer?**

Because the server manages persistence itself (Postgres, via `POSTGRES_URI`). A graph-level
checkpointer would be ignored when deployed, so the server fails the load with an explicit error
telling you to remove it. Export `builder.compile()` without one.

---

**Q5. What belongs in Postgres and what in Redis?**

Postgres: durable truth — checkpoints, long-term store, conversations, runs, approvals, audit.
Redis: fast and disposable — queues, rate limits, locks, circuit-breaker state, pub/sub, caches.
The test: wiping Redis must not lose anything a user cares about.

---

### Intermediate

**Q6. Serverless for an agent — yes or no?**

Yes for the interactive API: short streamed chat turns, starting runs, status, resuming approvals
— as long as state is in a shared checkpointer and clients are memoised with a connection pooler.
No for long runs, waiting on humans, stdio MCP subprocesses, or background work after the
response. The common split: serverless API, dedicated workers or the LangGraph server for runs.

---

**Q7. Walk me through the start/poll/resume API.**

`POST /threads/:tid/runs` validates ownership, records a run (with an idempotency key), enqueues
it and returns 202 + run id. `GET /threads/:tid/runs/:rid` returns the run's status from the runs
table and `next`/pending interrupts from the checkpoint. `POST /threads/:tid/resume` enqueues a
run with `Command(resume=…)` after checking the interrupt id. Workers execute runs; a crash is
recovered by re-queuing and resuming from the last checkpoint with a null input.

---

**Q8. How do you handle graceful shutdown?**

On `SIGTERM`: stop accepting new work, let in-flight runs finish up to a deadline, then close
database pools. In Python keep references to background tasks so you can wait on them. Anything
still running at the deadline is recoverable because of checkpoints — mark those runs so a worker
re-queues them.

---

**Q9. What's the difference between liveness and readiness checks?**

Liveness asks "is the process alive?" and should be cheap, so dependency blips don't trigger
restarts of healthy processes. Readiness asks "can it serve traffic right now?" and checks
dependencies like Postgres, so the load balancer routes around instances that can't.

---

**Q10. What usually limits an LLM application's scale?**

Rarely CPU: runs spend most of their time waiting on model providers. The limits are provider rate
limits (calls and tokens per minute), token cost, connection counts to databases, and state size
driving checkpoint write volume. Do the arithmetic — runs per second at peak, model calls per run,
tokens per run — before choosing infrastructure.

---

**Q11. How do you make run submission idempotent?**

Clients send an `Idempotency-Key` header; the API stores it with a unique constraint on the runs
table and returns the existing run id on a repeat. Side-effecting tools get their own idempotency
keys derived from the action (Day 24), so a retried or replayed step can't double-post.

---

### Advanced

**Q12. Design the deployment for an agent product at a million users.**

Start from arithmetic: daily actives, runs per user, peak factor, model calls and tokens per run —
that tells you the provider budget and rate limits dominate. Serve interactive chat from a
stateless, horizontally scaled API with streaming and cancellation; run long and human-gated work
through a queue and workers or the LangGraph server; keep checkpoints, store, runs and audit in
Postgres (pooled, with read replicas for history views and retention jobs); use Redis for queues,
rate limits and breaker state. Multiple providers or reserved capacity with fallback and
per-tenant limits; model routing to cheaper models where evals allow; strict state and prompt size
discipline; regional deployments if latency or data residency demand it; tracing, cost and quality
dashboards; and an evaluation gate on every deploy.

---

**Q13. A worker crashes halfway through a 12-step run. What happens in a well-designed system?**

The checkpoint holds every completed superstep. The queue's visibility timeout expires and the job
is redelivered (or a reaper marks runs stuck in `running` and re-queues them). The worker calls
`invoke(null, config)` for that thread, which resumes from the last checkpoint — the completed
steps aren't re-executed or re-billed. Side effects in the interrupted step are protected by
idempotency keys. The runs table records the retry for observability.

---

**Q14. When would you choose your own service over the LangGraph server?**

When you need something the server doesn't fit: an existing platform with its own job system,
strict infrastructure or compliance constraints, a very simple workload where the extra runtime
isn't worth operating, or tight integration with an existing API and auth layer. The trade is that
you build run management, streaming, interrupt endpoints and background execution yourself. If you
find yourself re-implementing most of the server's API, that's the signal to use the server.

---

**Q15. How do you roll out a new prompt or model safely?**

Treat it as a deploy. Pin it as a versioned config value; run the offline evaluation suite against
it (Day 25); ship behind a flag to a small percentage of traffic with the version in every run's
metadata; compare online quality, cost and latency by version; then ramp up or roll back by
flipping the flag. Because checkpointed threads outlive deploys, make sure a conversation that
started on the old version behaves sensibly on the new one — or pin a thread's version until it
ends.

---

## 10. Recap

### What you learned

- ✅ The golden rule: **stateless compute, state in a database**
- ✅ Three ways to ship: **in your app · your own service · the LangGraph server**
- ✅ Decouple long or human-gated runs: **start (202) → poll/stream → resume**
- ✅ Verified: the self-hosted pattern behaves identically in JS and Python, with ownership checks per thread
- ✅ Verified: the LangGraph server serves threads, interrupts, resume, streaming and background runs — to both SDKs
- ✅ The server **rejects graphs compiled with a checkpointer**; it uses `POSTGRES_URI`
- ✅ `langgraph dockerfile` generates a Dockerfile; self-hosted images: small, non-root, no secrets, health checks
- ✅ Serverless fits the **interactive API**, not long runs or waiting on humans
- ✅ **Postgres for truth, Redis for speed** — wiping Redis must lose nothing
- ✅ Python `PostgresSaver.from_conn_string` is a context manager; JS returns the saver
- ✅ Keep references to Python background tasks; drain in-flight runs on `SIGTERM`
- ✅ Capacity is limited by **provider rate limits, tokens and state size** — do the arithmetic
- ✅ Pin versions; let the eval suite gate every upgrade

### The deployment checklist

```
   □ shared checkpointer, no in-process state        □ thread ownership checked on every route
   □ long runs decoupled with idempotent submission  □ graceful shutdown + orphaned-run recovery
   □ clients and pools created once per process      □ liveness cheap, readiness honest
   □ secrets injected at runtime                     □ Redis holds nothing irreplaceable
   □ capacity arithmetic written down                □ versions pinned, evals gate deploys
```

### Tomorrow

**[Day 28 — Capstones & Interview Crash Course](day-28-capstones-and-interviews.md)**: the last
day. Twelve capstone projects from beginner to advanced, each mapped to the days it exercises,
and an interview crash course: the questions that come up most, how to structure system-design
answers, and three mock interviews with model answers.

### Quick self-check

1. After a deploy, students report "StudyBuddy forgot our conversation." Name two likely causes.
2. Why does the LangGraph server refuse your graph, and how do you fix it?
3. Your agent product hits provider 429s at peak. Your teammate proposes doubling the worker
   count. What do you say?

<details>
<summary>Answers</summary>

1. State in the process — an in-memory checkpointer or a global dictionary, lost on restart and
   split across instances — and no graceful shutdown, so in-flight runs were killed. Also check
   whether `thread_id` is stable across requests (derived from the user and chat, not generated
   per request).

2. The graph was compiled with its own checkpointer. The server manages persistence itself and
   rejects the graph with "includes a custom checkpointer … please remove" (verified). Export
   `builder.compile()` without a checkpointer and configure the database with `POSTGRES_URI`.

3. More workers make it worse: the constraint is the provider's rate limit, not compute, so more
   concurrency means more 429s and more retries. Instead: a shared rate limiter sized to the
   quota, worker concurrency as a valve with a queue absorbing bursts, retries with jitter at one
   layer only, a fallback provider, fewer model calls per run, and a quota increase or second
   provider if the arithmetic says demand genuinely exceeds capacity.
</details>

---

<div align="center">

**[← Day 26 — MCP & AI SDK](day-26-mcp-and-ai-sdk.md)** · **[Week 4 index](README.md)** · **[Day 28 — Capstones & Interviews →](day-28-capstones-and-interviews.md)**

</div>
