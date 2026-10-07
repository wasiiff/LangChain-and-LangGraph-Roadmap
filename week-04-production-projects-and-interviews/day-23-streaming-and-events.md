# Day 23 — Streaming & Events: Make It Feel Fast

> ⏱ **Time:** ~2.5 hours · 🎯 **Prereqs:** [Day 22](day-22-multi-agent.md) · 🧩 **Difficulty:** ●●●○○

**Today you learn:** how to show the user what's happening *while* it happens. The five
kinds of things a LangGraph run can stream, how to pick out only the tokens a user should
see, custom progress events from inside nodes and tools, streaming a multi-agent system,
and how to get all of it to a browser over Server-Sent Events. Plus cancellation — where
JavaScript and Python behave **differently**, and the difference costs real money.

---

## 1. The problem

StudyBuddy v5 (Day 22) is smart. It's also silent:

```
   user:   "Explain my weakest topic and quiz me on it."
           ⏳ ... 1s ... 2s ... 4s ... 6s ... 8s ...
   user:   *refreshes the page*          ← the request is still running, and now it's running twice
```

The answer arrived at 8.2 seconds. Nothing was wrong except that **nothing appeared to be
happening.** People judge speed by how soon something moves, not by when the work finishes:

```
   TOTAL LATENCY                     8.2 s  — the same in both versions below
   TIME TO FIRST VISIBLE PROGRESS    8.2 s  →  0.1 s
   TIME TO FIRST ANSWER WORD         8.2 s  →  5.9 s
```

```
   ❌ SILENT                              ✅ STREAMED

   [spinner for 8 seconds]                ✓ Checking your progress...
                                          ✓ Weakest topic: HTTPS (62/100)
                                          ⋯ Asking the researcher...
                                          HTTPS is HTTP running over TLS. When your
                                          browser connects, it and the server agree on ▍
```

### The real-life version

A restaurant. Two kitchens, same food, same 20-minute wait.

```
   KITCHEN A   Nothing for 20 minutes. Then all the food arrives.
               Half the table has asked "did they forget us?" twice.

   KITCHEN B   Bread in 2 minutes. "Your mains are being plated" at 15.
               Starters one at a time as they're ready.
```

Kitchen B isn't faster. It's **legible**. Streaming is how you make an AI system legible:
progress (what stage are we at), partial results (the answer as it's written), and honest
status (it's still working, and here's what it's doing).

---

## 2. Mental model

### Five things a run can stream

```
   invoke()  →  one result at the end                    (what you've used so far)
   stream()  →  a sequence of chunks WHILE it runs       (today)

                    ┌──────────────────────── one run ────────────────────────┐
                    │                                                          │
   values      ●────────●──────────────●     full state after each superstep │
   updates          ●──────────────●         what each NODE just returned    │
   messages          ▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪      LLM TOKENS, as generated         │
   custom         ◆  ◆                        YOUR OWN events ("searching…")   │
   debug/tasks/     internal detail           for debugging tools              │
   checkpoints                                                                │
                    └──────────────────────────────────────────────────────────┘
```

| Mode | One chunk is… | Use it for |
|---|---|---|
| `values` | the **whole state**, after each superstep | debugging; tiny states |
| `updates` | `{ nodeName: whatItReturned }` | progress UI — "✓ checked your scores" |
| `messages` | `[tokenChunk, metadata]` | the typing effect |
| `custom` | whatever you emitted | fine-grained progress from inside a node or tool |
| `debug` / `tasks` / `checkpoints` | internal task and checkpoint records | tooling, not end users |

You can ask for several at once. Then each chunk is tagged with its mode:
`[mode, chunk]` in JS, `(mode, chunk)` in Python.

### From graph to browser

```
   ┌─────────┐   stream()    ┌──────────────┐   SSE over HTTP    ┌──────────┐
   │  graph  │ ────────────► │ your server  │ ─────────────────► │ browser  │
   │         │  [mode,chunk] │  translates  │  event: token      │ renders  │
   └─────────┘               │  to events   │  data: {"text":"H"}│          │
        ▲                    └──────┬───────┘                    └────┬─────┘
        │                           │  client disconnects             │
        └────── cancel ─────────────┴─────────────────────────────────┘
```

Three jobs, and each is today's subject: **choose what to stream**, **translate it into events
the UI understands**, and **stop the work when nobody's listening**.

---

## 3. First principles

### 3.1 How tokens escape a node

You've been writing nodes like this:

```js
async (state) => ({ messages: [await model.invoke(state.messages)] })
```

That's `invoke`, not `stream` — so how can the tokens be streamed? Because every LangChain
model call reports events through **callbacks**, and when you run a graph with
`streamMode: "messages"`, LangGraph attaches a handler that forwards each token as it's
generated. The node still receives the complete message at the end; your loop receives the
pieces along the way.

Verified: a node calling `model.invoke(...)` produced a stream of `AIMessageChunk`s tagged
with that node's name. **You don't rewrite nodes to support streaming.** You choose a
stream mode when you run the graph.

### 3.2 The modes, measured

A two-node graph — `research` emits two custom progress events, `answer` calls a model —
streamed in each mode (identical shape in both languages):

```
   mode         chunks   first chunk
   ──────────   ──────   ─────────────────────────────────────────────────────────
   values          3     { messages: [HumanMessage("what is photosynthesis?")] }
   updates         2     { research: { step: "researched" } }
   messages     many     [ AIMessageChunk("P…"), { langgraph_node: "answer", … } ]
   custom          2     { progress: "searching notes", pct: 30 }
   debug           4     { step: 1, type: "task", timestamp: …, payload: {…} }
   tasks           4     { id: …, name: "research", input: {…} }
   checkpoints     3     { config, values, metadata, next, tasks, parent config }
```

Things to notice:

- **`values` has one more chunk than `updates`** — it includes the state *before* any node
  ran. And each chunk is the whole state, which is why it's the wrong thing to send to a
  browser once state gets large.
- **`messages` chunk size depends on the model.** Real providers stream roughly token by
  token. The fake test models used here split differently (JS's `FakeListChatModel` by
  character, Python's `GenericFakeChatModel` by word), which is why the counts differ between
  languages in this chapter's tests — that's the fakes, not LangGraph.
- **`checkpoints` needs a checkpointer.** Without one it fails with an unhelpful error (JS:
  `Cannot read properties of undefined (reading 'slice')`; Python: `IndexError: list index out
  of range`). With one, you get each checkpoint's `next` as it's written: `[__start__]`,
  `[a]`, `[]`. The parent-config key is `parentConfig` in JS and `parent_config` in Python.

### 3.3 The `messages` tuple — and why you must filter it

Each `messages` chunk arrives with metadata:

```
   [ AIMessageChunk { content: "Pl" },
     { langgraph_node: "answer", tags: ["final"], … } ]
```

That metadata is what saves you, because **every model call in the graph streams** — the
router, the classifier, the grader, the supervisor deciding who to call. Verified: a graph
with a `route` node and a `write` node streamed tokens from *both*. If you forward
everything, the user watches your router think "ROUTE" before the answer starts.

Two ways to filter:

```
   BY NODE   meta.langgraph_node === "write"            simple; breaks if you rename nodes
   BY TAG    model.withConfig({ tags: ["final"] })      survives refactors; explicit intent
             meta.tags?.includes("final")
```

Verified: tagging the answering model `final` and filtering on the tag produced exactly
`"final answer"` — none of the router's tokens.

### 3.4 Custom events

Some progress lives *inside* a node: "fetched 3 of 10 sources", "retrying the database".
Custom events let a node or a tool emit anything, on demand:

```
   JS       config.writer?.({ progress: "searching notes", pct: 30 })
   Python   get_stream_writer()({"progress": "searching notes", "pct": 30})
```

Verified in both languages: events emitted from a node **and from inside a tool executed by
`ToolNode`** arrive in `custom` mode in order.

> 💡 Don't put progress in graph state. A `status` channel would be written to every
> checkpoint (Day 18's cost model) and would only update once per superstep. Custom events
> are free, immediate, and never persisted.

### 3.5 Streaming a multi-agent system — the languages differ

On Day 22 the specialists run *inside tools*: a separate graph invoked from a tool
function. Do their tokens reach the parent's `messages` stream? Verified, and the answer
depends on the language:

```
                             subgraphs: false (default)       subgraphs: true
                             ──────────────────────────       ───────────────────────────────
   JavaScript                YES — tokens appear, tagged      YES — and namespaced:
                             langgraph_node = "sub_llm"       "delegate:<id>/sub_llm:<id>"

   Python                    NO — only the parent's own       YES — namespaced:
                             messages appear                  "delegate:<id>"
```

Passing `config` into the nested `invoke` made no difference in either language (JS
propagates context through `AsyncLocalStorage`, Python through `contextvars`).

So:

- **In JS, specialists' tokens leak into your UI by default.** Filter by tag (tag the
  supervisor's model `final`) or by `langgraph_node`.
- **In Python, you opt in** with `subgraphs=True`, and each chunk comes with a namespace
  telling you which specialist is talking — useful for a "the researcher is typing…" UI.

### 3.6 `streamEvents` — the firehose

Before stream modes existed, the way to see inside a run was `streamEvents` (JS) /
`astream_events` (Python), version `"v2"`. It emits every start, stream and end event for
every runnable. Counted on the same two-node graph:

```
   JavaScript   on_chain_start 4 · on_chain_end 4 · on_chain_stream 2 ·
                on_chat_model_start 1 · on_chat_model_stream 31 · on_chat_model_end 1
   Python       on_chain_start 3 · on_chain_end 3 · on_chain_stream 4 ·
                on_chat_model_start 1 · on_chat_model_stream 9 · on_chat_model_end 1
```

It's powerful and noisy, and its exact counts are an implementation detail (note they
differ between languages). **For graphs, prefer stream modes**; reach for `streamEvents`
when you're streaming a plain LCEL chain, or you need an event stream modes don't provide.

### 3.7 Cancellation — where JS and Python differ

A user closes the tab. What happens to the run? Verified on a three-node chain
`first → second (150 ms) → third`, stopping the consumer after the first chunk:

```
   JavaScript
     break out of the for-await       first > second > third        ← THE GRAPH KEEPS RUNNING
     abort an AbortSignal             first > second(finishes) > ✗   ← stops at the next superstep
     abort + node honours signal      first > second(cut off)  > ✗   ← stops immediately

   Python
     break out of the for loop        first > ✗                     ← stops before the next superstep
     (sync and async alike)
```

That first JS row is the expensive one. Breaking out of the loop stops *you* reading; it
doesn't stop the graph, which runs to the end in the background — model calls and all. In
JS, cancellation is something you must wire:

```
   1. pass { signal } to stream()               so the graph stops between supersteps
   2. pass config.signal into slow calls        so the node in flight stops too
      (model.invoke(msgs, { signal: config.signal }), fetch(url, { signal }))
   3. abort when the client disconnects         req.on("close") / request.signal
```

In Python, closing the generator — which is what happens when you `break`, or when a web
framework cancels a streaming response because the client left — stops the graph before the
next superstep. The node already running still finishes.

### 3.8 Server-Sent Events in one screen

SSE is plain HTTP with a long-lived response and a tiny text format:

```
   HTTP/1.1 200 OK
   Content-Type: text/event-stream
   Cache-Control: no-cache

   event: progress
   data: {"progress":"searching notes"}
                                              ← a blank line ends each event
   event: token
   data: {"text":"Pl"}

   event: done
   data: {}
```

```
   ✅ SSE                                     WebSockets
   one-way, server → client                   two-way
   plain HTTP: auth, proxies, CDNs work       its own protocol and connection handling
   the browser reconnects automatically      you write reconnection
   exactly the shape of "stream a response"   more than you need for this
```

For "the server streams a response to a request", SSE is the right default. The one browser
limitation: the built-in `EventSource` only does GET and can't set headers, so for POST
bodies or an `Authorization` header you read the stream with `fetch` instead (§4.8).

---

## 4. Code — JavaScript

### 4.1 Progress from `updates`

The cheapest useful stream: one line per completed step.

```js
import { StateGraph, MessagesAnnotation, Annotation, START, END } from "@langchain/langgraph";
import { HumanMessage } from "@langchain/core/messages";
import { ChatGroq } from "@langchain/groq";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });

const State = Annotation.Root({
  ...MessagesAnnotation.spec,
  topic: Annotation(),
  notes: Annotation(),
});

const app = new StateGraph(State)
  .addNode("classify", async (s) => ({ topic: "https" }))
  .addNode("research", async (s) => ({ notes: "HTTPS = HTTP over TLS; ECDHE gives forward secrecy." }))
  .addNode("answer", async (s) => ({
    messages: [await model.invoke([
      { role: "system", content: `Explain using these notes: ${s.notes}` },
      ...s.messages,
    ])],
  }))
  .addEdge(START, "classify").addEdge("classify", "research")
  .addEdge("research", "answer").addEdge("answer", END)
  .compile();

const LABELS = {
  classify: "Understood your question",
  research: "Found your notes",
  answer: "Wrote the answer",
};

for await (const chunk of await app.stream(
  { messages: [new HumanMessage("How does HTTPS work?")] },
  { streamMode: "updates" }
)) {
  const node = Object.keys(chunk)[0];
  console.log(`✓ ${LABELS[node] ?? node}`);
}
// ✓ Understood your question
// ✓ Found your notes
// ✓ Wrote the answer
```

Map node names to **human labels** at the edge. Node names are for engineers; `"research"`
is fine, `"retrieve_v2_rerank"` is not something a student should read.

### 4.2 Tokens from `messages` — filtered

```js
// tag the model whose output the USER should see
const answerModel = model.withConfig({ tags: ["final"] });
const routerModel = model.withConfig({ tags: ["internal"] });

const app = new StateGraph(MessagesAnnotation)
  .addNode("route", async (s) => ({ messages: [await routerModel.invoke(s.messages)] }))
  .addNode("write", async (s) => ({ messages: [await answerModel.invoke(s.messages)] }))
  .addEdge(START, "route").addEdge("route", "write").addEdge("write", END)
  .compile();

for await (const [chunk, meta] of await app.stream(
  { messages: [new HumanMessage("How does HTTPS work?")] },
  { streamMode: "messages" }
)) {
  if (meta.tags?.includes("final")) process.stdout.write(chunk.content);   // only the answer
}
```

Without the filter you'd print the router's output first — verified, both nodes stream.
Tagging costs one `withConfig` per model and makes the intent explicit in code review.

### 4.3 Custom progress events — from nodes and tools

```js
import { tool } from "@langchain/core/tools";
import { ToolNode } from "@langchain/langgraph/prebuilt";
import { z } from "zod";

// from a node: (state, config) — config.writer is the custom-event emitter
async function research(state, config) {
  const sources = ["notes", "textbook", "past quizzes"];
  for (const [i, source] of sources.entries()) {
    config.writer?.({ stage: "research", message: `Reading ${source}`, done: i, total: sources.length });
    await readSource(source);
  }
  return { notes: "..." };
}

// from a tool: tools receive config as their second argument
const searchNotes = tool(
  async ({ query }, config) => {
    config.writer?.({ stage: "tool", message: `Searching notes for "${query}"` });
    const hits = await search(query);
    config.writer?.({ stage: "tool", message: `Found ${hits.length} matches` });
    return JSON.stringify(hits);
  },
  { name: "search_notes", description: "Search the course notes.", schema: z.object({ query: z.string() }) }
);

for await (const event of await app.stream(input, { streamMode: "custom" })) {
  console.log("…", event.message);
}
```

The `?.` is deliberate: it keeps the node working when it's run by `invoke` or in a unit test,
where nobody is listening for custom events.

### 4.4 Everything at once

A real UI wants progress *and* tokens. Ask for several modes and route on the tag:

```js
for await (const [mode, chunk] of await app.stream(input, {
  streamMode: ["updates", "messages", "custom"],
})) {
  if (mode === "custom") {
    ui.progress(chunk.message);
  } else if (mode === "updates") {
    const node = Object.keys(chunk)[0];
    ui.step(LABELS[node] ?? node);
  } else if (mode === "messages") {
    const [token, meta] = chunk;
    if (meta.tags?.includes("final")) ui.appendToken(token.content);
  }
}
```

Verified order for the research/answer graph: `custom, custom, updates, messages…, updates` —
the node's custom events arrive before its update, and the answer's tokens arrive before
the `answer` node's update (which lands when the node finishes).

### 4.5 Streaming a supervisor (Day 22)

In JS, tokens from specialists invoked inside tools appear in the parent's `messages`
stream by default (§3.5). Two choices:

```js
// A) show ONLY the supervisor's words to the student
const supervisorModel = model.withConfig({ tags: ["final"] });
// ...build the supervisor with supervisorModel...
if (meta.tags?.includes("final")) ui.appendToken(token.content);

// B) show who is working, but not their raw tokens
if (mode === "messages") {
  const [token, meta] = chunk;
  if (meta.tags?.includes("final")) ui.appendToken(token.content);
  else ui.status(`${meta.langgraph_node} is working…`);        // e.g. "researcher is working…"
}
```

For a namespaced view — which specialist, which nested node — add `subgraphs: true`; each
item then arrives as `[namespace, [token, meta]]` with namespaces like
`"delegate:<id>/sub_llm:<id>"`.

### 4.6 An SSE endpoint — Node's `http`, with cancellation

```js
import http from "node:http";

const server = http.createServer(async (req, res) => {
  if (req.url !== "/chat" || req.method !== "POST") { res.writeHead(404).end(); return; }
  const body = JSON.parse(await readBody(req));

  res.writeHead(200, {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    Connection: "keep-alive",
    "X-Accel-Buffering": "no",                 // tell nginx not to buffer the stream
  });
  const send = (event, data) => res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);

  // ── cancellation: the client leaving must stop the graph ──────────────
  const abort = new AbortController();
  req.on("close", () => abort.abort());

  try {
    for await (const [mode, chunk] of await app.stream(
      { messages: [new HumanMessage(body.text)] },
      {
        streamMode: ["updates", "messages", "custom"],
        signal: abort.signal,                                        // stop between supersteps
        configurable: { thread_id: body.threadId },
      }
    )) {
      if (mode === "custom") send("progress", chunk);
      else if (mode === "updates") send("step", { node: Object.keys(chunk)[0] });
      else if (chunk[1].tags?.includes("final")) send("token", { text: chunk[0].content });
    }
    send("done", {});
  } catch (err) {
    if (err.name !== "AbortError") send("error", { message: "Something went wrong." });
  } finally {
    res.end();
  }
});
server.listen(3000);
```

And inside nodes, pass the signal to slow calls, so the node in flight stops too:

```js
.addNode("answer", async (state, config) => ({
  messages: [await answerModel.invoke(state.messages, { signal: config.signal })],
}))
```

Verified end to end with a real `http` server and a `fetch` client: `Content-Type:
text/event-stream`, one `progress` event, two `step` events, the tokens, and `done`, in that
order.

> 🔒 Never send `err.message` to the browser. Internal errors carry file paths, SQL, and
> occasionally secrets. Log the details; send a generic message.

### 4.7 A Next.js route handler — `Response` + `ReadableStream`

Web-standard servers (Next.js route handlers, Hono, Bun, Deno, Cloudflare Workers) return a
`Response` wrapping a `ReadableStream`:

```js
// app/api/chat/route.js
export async function POST(request) {
  const { text, threadId } = await request.json();
  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    async start(controller) {
      const send = (event, data) =>
        controller.enqueue(encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`));
      try {
        for await (const [mode, chunk] of await app.stream(
          { messages: [new HumanMessage(text)] },
          {
            streamMode: ["updates", "messages", "custom"],
            signal: request.signal,               // the platform aborts this when the client leaves
            configurable: { thread_id: threadId },
          }
        )) {
          if (mode === "custom") send("progress", chunk);
          else if (mode === "updates") send("step", { node: Object.keys(chunk)[0] });
          else if (chunk[1].tags?.includes("final")) send("token", { text: chunk[0].content });
        }
        send("done", {});
      } catch (err) {
        if (err.name !== "AbortError") send("error", { message: "Something went wrong." });
      } finally {
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" },
  });
}
```

`request.signal` is the web-standard equivalent of `req.on("close")`. Verified: the
`Response` + `ReadableStream` shape produced a well-formed event stream in Node.

### 4.8 The browser side

`EventSource` is simplest, but GET-only and header-less. For a POST with a body or an
`Authorization` header, read the stream with `fetch`:

```js
async function streamChat(text, threadId, handlers) {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, threadId }),
  });

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let end;
    while ((end = buffer.indexOf("\n\n")) >= 0) {          // one event per blank line
      const raw = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      const event = raw.match(/^event: (.*)$/m)?.[1] ?? "message";
      const data = JSON.parse(raw.match(/^data: (.*)$/m)?.[1] ?? "null");
      handlers[event]?.(data);
    }
  }
}

streamChat("How does HTTPS work?", "student-42", {
  progress: (d) => setStatus(d.message),
  step: (d) => addStep(d.node),
  token: (d) => appendToAnswer(d.text),
  done: () => setStatus(""),
  error: (d) => showError(d.message),
});
```

Two details: `{ stream: true }` in `decode` handles multi-byte characters split across
network chunks, and keeping a `buffer` handles events split across chunks. Without either,
Urdu or emoji text arrives garbled and occasionally an event is dropped. (This parser is the
one used to verify §4.6.)

For cancellation from the browser, pass an `AbortController`'s `signal` to `fetch` and
call `abort()` when the user clicks "Stop" — the server sees the disconnect and aborts the
graph.

---

## 5. Code — Python

### 5.1 Progress from `updates`

```python
from typing import Annotated, TypedDict
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

class State(TypedDict):
    messages: Annotated[list, add_messages]
    topic: str
    notes: str

def classify(s): return {"topic": "https"}
def research(s): return {"notes": "HTTPS = HTTP over TLS; ECDHE gives forward secrecy."}
def answer(s):
    return {"messages": [model.invoke(
        [{"role": "system", "content": f'Explain using these notes: {s["notes"]}'}, *s["messages"]]
    )]}

b = StateGraph(State)
b.add_node("classify", classify); b.add_node("research", research); b.add_node("answer", answer)
b.add_edge(START, "classify"); b.add_edge("classify", "research")
b.add_edge("research", "answer"); b.add_edge("answer", END)
app = b.compile()

LABELS = {"classify": "Understood your question", "research": "Found your notes", "answer": "Wrote the answer"}

for chunk in app.stream({"messages": [HumanMessage("How does HTTPS work?")]}, stream_mode="updates"):
    node = next(iter(chunk))
    print(f"✓ {LABELS.get(node, node)}")
```

### 5.2 Tokens from `messages` — filtered

```python
answer_model = model.with_config(tags=["final"])
router_model = model.with_config(tags=["internal"])

b = StateGraph(MessagesState)
b.add_node("route", lambda s: {"messages": [router_model.invoke(s["messages"])]})
b.add_node("write", lambda s: {"messages": [answer_model.invoke(s["messages"])]})
b.add_edge(START, "route"); b.add_edge("route", "write"); b.add_edge("write", END)
app = b.compile()

for chunk, meta in app.stream({"messages": [HumanMessage("How does HTTPS work?")]},
                              stream_mode="messages"):
    if "final" in meta.get("tags", []):
        print(chunk.content, end="", flush=True)
```

(`MessagesState` comes from `langgraph.graph`.)

### 5.3 Custom progress events — from nodes and tools

```python
from langgraph.config import get_stream_writer
from langchain_core.tools import tool

def research(state):
    writer = get_stream_writer()
    sources = ["notes", "textbook", "past quizzes"]
    for i, source in enumerate(sources):
        writer({"stage": "research", "message": f"Reading {source}", "done": i, "total": len(sources)})
        read_source(source)
    return {"notes": "..."}

@tool
def search_notes(query: str) -> str:
    """Search the course notes."""
    writer = get_stream_writer()
    writer({"stage": "tool", "message": f'Searching notes for "{query}"'})
    hits = search(query)
    writer({"stage": "tool", "message": f"Found {len(hits)} matches"})
    return json.dumps(hits)

for event in app.stream(inp, stream_mode="custom"):
    print("…", event["message"])
```

Python fetches the writer with `get_stream_writer()` rather than receiving it as an
argument — so nodes and tools don't need a `config` parameter to emit progress.

### 5.4 Everything at once

```python
for mode, chunk in app.stream(inp, stream_mode=["updates", "messages", "custom"]):
    if mode == "custom":
        ui.progress(chunk["message"])
    elif mode == "updates":
        node = next(iter(chunk))
        ui.step(LABELS.get(node, node))
    elif mode == "messages":
        token, meta = chunk
        if "final" in meta.get("tags", []):
            ui.append_token(token.content)
```

### 5.5 Streaming a supervisor (Day 22)

In Python the specialists' tokens do **not** reach the parent stream unless you ask:

```python
for namespace, (token, meta) in supervisor.stream(inp, stream_mode="messages", subgraphs=True):
    who = namespace[0].split(":")[0] if namespace else "supervisor"
    if who == "supervisor" and "final" in meta.get("tags", []):
        ui.append_token(token.content)
    elif who != "supervisor":
        ui.status(f"{who} is working…")
```

With `subgraphs=True` each item is `(namespace, (token, meta))`; an empty namespace means
the top-level graph, and a specialist invoked inside a tool shows up under the tool-calling
node's namespace (verified: `"delegate:<id>"`).

### 5.6 An SSE endpoint — FastAPI

```python
import json
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

api = FastAPI()

class ChatBody(BaseModel):
    text: str
    thread_id: str

def sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"

@api.post("/chat")
async def chat(body: ChatBody):
    async def events():
        try:
            async for mode, chunk in app.astream(
                {"messages": [HumanMessage(body.text)]},
                {"configurable": {"thread_id": body.thread_id}},
                stream_mode=["updates", "messages", "custom"],
            ):
                if mode == "custom":
                    yield sse("progress", chunk)
                elif mode == "updates":
                    yield sse("step", {"node": next(iter(chunk))})
                elif "final" in chunk[1].get("tags", []):
                    yield sse("token", {"text": chunk[0].content})
            yield sse("done", {})
        except Exception:
            yield sse("error", {"message": "Something went wrong."})   # log the details, don't send them

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

Verified with FastAPI's `TestClient`: content type `text/event-stream; charset=utf-8`, one
`progress`, two `step`s, the tokens, and `done`.

**Cancellation comes almost for free.** When the client disconnects, the server cancels the
response's async generator; closing the generator closes `app.astream(...)`, which stops the
graph before its next superstep (verified: breaking out of `astream` meant the next node never
ran). The node in flight still finishes — for long model calls, set a request timeout on the
client (§ Day 24).

> ⚠️ Use `async def` and `astream` inside the endpoint. A synchronous `app.stream(...)` in an
> `async` endpoint blocks the event loop, and every other request waits behind it.

### 5.7 The JS ↔ Python translation for today

| Concept | JavaScript | Python |
|---|---|---|
| stream | `for await (const c of await app.stream(input, { streamMode }))` | `for c in app.stream(input, stream_mode=...)` |
| async stream | same as above | `async for c in app.astream(...)` |
| several modes | `streamMode: ["updates", "messages"]` → `[mode, chunk]` | `stream_mode=["updates", "messages"]` → `(mode, chunk)` |
| token metadata | `meta.langgraph_node`, `meta.tags` | `meta["langgraph_node"]`, `meta.get("tags")` |
| tag a model | `model.withConfig({ tags: ["final"] })` | `model.with_config(tags=["final"])` |
| custom event | `config.writer?.({...})` — node/tool receives `config` | `get_stream_writer()({...})` from `langgraph.config` |
| subagent tokens (default) | **included** | **not included** |
| subagent tokens (namespaced) | `subgraphs: true` → `[ns, [token, meta]]` | `subgraphs=True` → `(ns, (token, meta))` |
| event firehose | `app.streamEvents(input, { version: "v2" })` | `app.astream_events(input, version="v2")` |
| checkpoint parent key | `parentConfig` | `parent_config` |
| stop the graph | `signal` on `stream()` + `config.signal` in nodes | close the generator (`break`, or client disconnect) |
| `break` alone | **graph keeps running** | stops before the next superstep |
| SSE response | `res.write(...)` or `new Response(ReadableStream)` | `StreamingResponse(gen(), media_type="text/event-stream")` |

---

## 6. Under the hood

### 6.1 Where each mode comes from

```
   superstep completes ──► values   (the full state snapshot)
                       ──► updates  (each node's returned patch)
                       ──► checkpoints (if a checkpointer is set)

   model inside a node ──callbacks──► messages  (on each new token)

   config.writer / get_stream_writer() ──► custom  (whenever you call it)
```

Modes are views onto events the engine already produces. Asking for more modes doesn't make
the graph do more work — it just forwards more of what's happening. The cost is on the wire
and in your UI code, not in the graph.

### 6.2 Why `values` is the wrong wire format

`values` sends the entire state after every superstep. With a 20-message conversation and a
six-node graph, that's the whole conversation six times per request — to show the user one
new answer. `updates` sends only what changed; `messages` sends only tokens. Use `values` in
debuggers and tests.

### 6.3 Buffering: the silent killer

Your server streams perfectly on localhost and not at all in production. Something between
you and the browser is **buffering** the response until it's complete:

```
   gzip/compression middleware     compresses whole responses → disable for text/event-stream
   nginx / reverse proxies         buffer by default → "X-Accel-Buffering: no", or proxy_buffering off
   some serverless platforms       buffer unless the runtime supports streaming responses
   dev servers with hot reload     occasionally buffer; test against a production build
```

The symptom is always the same — everything arrives at once at the end — and the cause is
almost never your code. Check the headers in the browser's network tab: a streamed response
shows the body growing while the request is still pending.

### 6.4 Keeping connections alive

Long silences (a slow model call) can make proxies or load balancers close an idle
connection. The SSE format has comments for exactly this — a line starting with `:` is
ignored by clients:

```
   : keep-alive
                        ← send every ~15 s while waiting
```

Custom progress events double as keep-alives, which is another reason to emit them from slow
nodes.

### 6.5 Reconnection and duplicate work

`EventSource` reconnects automatically after a dropped connection — and a naive server
starts the whole request again. For an agent that can mean duplicated model calls or, worse,
duplicated side effects. Two defences:

```
   1. Separate "start a run" from "watch a run". POST /runs starts the work (with a
      checkpointer and a thread_id) and returns an id; GET /runs/:id/stream watches it.
      A reconnect re-attaches to the watch, not the work.
   2. Keep side effects idempotent (Day 21's rule), so a repeated step can't double-charge.
```

Pattern 1 is also how the LangGraph platform exposes runs (Day 27); it's worth designing
towards even in a hand-rolled server.

---

## 7. Common mistakes

### ❌ 1. Streaming `values` to the browser

```js
❌ app.stream(input, { streamMode: "values" })     // the whole state, every superstep
✅ app.stream(input, { streamMode: ["updates", "messages", "custom"] })
```

It works in the demo and melts under real conversation lengths. `values` is a debugging view.

### ❌ 2. Forwarding every token

```js
❌ for await (const [token] of await app.stream(input, { streamMode: "messages" })) send(token.content);
✅ if (meta.tags?.includes("final")) send(token.content);
```

Verified: the router's tokens stream too. So do the classifier's, the grader's and — in JS —
every Day 22 specialist's. Tag the model whose words the user should read.

### ❌ 3. Stopping a JS stream with `break`

```js
❌ for await (const c of await app.stream(input)) { if (userLeft) break; }
   // the graph keeps running to the end — verified: the third node still ran
✅ const abort = new AbortController();
   req.on("close", () => abort.abort());
   for await (const c of await app.stream(input, { signal: abort.signal })) { ... }
```

In JS, `break` stops you reading, not the work. Every abandoned request keeps spending tokens.

### ❌ 4. Aborting, but not passing the signal into the node

```js
❌ async (state) => ({ messages: [await model.invoke(state.messages)] })
   // abort: the stream throws AbortError, but this call runs to completion
✅ async (state, config) => ({ messages: [await model.invoke(state.messages, { signal: config.signal })] })
```

Verified: with the signal ignored, the in-flight node finished after the abort. With
`config.signal` honoured, it stopped immediately. A 30-second model call is exactly the
thing you want to stop.

### ❌ 5. `checkpoints` mode without a checkpointer

```
JS:     TypeError: Cannot read properties of undefined (reading 'slice')
Python: IndexError: list index out of range
```

Neither message mentions checkpointers. Compile with one, and pass a `thread_id`.

### ❌ 6. Expecting specialists' tokens in Python

```python
❌ for token, meta in supervisor.stream(inp, stream_mode="messages"): ...   # only the supervisor
✅ for ns, (token, meta) in supervisor.stream(inp, stream_mode="messages", subgraphs=True): ...
```

Verified: without `subgraphs=True`, a graph invoked inside a tool contributes nothing to the
parent's `messages` stream in Python — while in JS it does. Porting code between the two is
where this bites.

### ❌ 7. Progress in graph state

```js
❌ status: Annotation()             // written to every checkpoint, updated once per superstep
✅ config.writer?.({ status: "..." })
```

Custom events are immediate, free, and never persisted.

### ❌ 8. A malformed SSE event

```
❌ data: {"text":"Hi"}\n            ← missing the blank line: the event never "ends"
✅ data: {"text":"Hi"}\n\n
```

The client buffers until it sees a blank line. One missing `\n` and nothing renders — until
the next event arrives and both appear at once.

### ❌ 9. Sending raw errors to the client

```js
❌ send("error", { message: err.message })   // file paths, SQL, sometimes secrets
✅ log(err); send("error", { message: "Something went wrong." })
```

### ❌ 10. A synchronous stream in an async Python endpoint

```python
❌ async def chat(...):
       for chunk in app.stream(...): yield ...    # blocks the event loop
✅ async def chat(...):
       async for chunk in app.astream(...): yield ...
```

One slow request freezes every other request on that worker.

### ❌ 11. Testing streaming only on localhost

Compression, proxies and some platforms buffer responses. The code is right and the user
still sees everything arrive at once. Test through the real infrastructure, and set
`X-Accel-Buffering: no` / disable compression for `text/event-stream`.

---

## 8. Exercises

### Exercise 1 — See every mode ●○○○○

Build a two-node graph with no API key: `research` emits two custom events, `answer` calls a
fake streaming model. Stream it in every mode (`values`, `updates`, `messages`, `custom`,
`debug`, `tasks`, and `checkpoints` with a checkpointer) and print the number of chunks and
the first chunk of each.

<details>
<summary>✅ Solution</summary>

**JavaScript**

```js
import { StateGraph, MessagesAnnotation, Annotation, MemorySaver, START, END } from "@langchain/langgraph";
import { FakeListChatModel } from "@langchain/core/utils/testing";
import { HumanMessage } from "@langchain/core/messages";

const model = new FakeListChatModel({ responses: ["Plants turn sunlight into food."] });
const State = Annotation.Root({
  ...MessagesAnnotation.spec,
  step: Annotation({ reducer: (a, b) => b ?? a, default: () => "" }),
});

const app = new StateGraph(State)
  .addNode("research", async (s, config) => {
    config.writer?.({ progress: "searching notes", pct: 30 });
    config.writer?.({ progress: "reading 3 sources", pct: 60 });
    return { step: "researched" };
  })
  .addNode("answer", async (s) => ({ messages: [await model.invoke(s.messages)] }))
  .addEdge(START, "research").addEdge("research", "answer").addEdge("answer", END)
  .compile({ checkpointer: new MemorySaver() });          // so `checkpoints` works too

const input = { messages: [new HumanMessage("what is photosynthesis?")] };
let run = 0;

for (const mode of ["values", "updates", "messages", "custom", "debug", "tasks", "checkpoints"]) {
  const chunks = [];
  const config = { streamMode: mode, configurable: { thread_id: `demo-${run++}` } };
  for await (const c of await app.stream(input, config)) chunks.push(c);

  const first = mode === "messages"
    ? `[${chunks[0][0].constructor.name}("${chunks[0][0].content}"), node=${chunks[0][1].langgraph_node}]`
    : JSON.stringify(chunks[0]).slice(0, 90);
  console.log(`${mode.padEnd(12)} ${String(chunks.length).padStart(3)}  ${first}`);
}
```

**Python**

```python
import json
from typing import Annotated, TypedDict
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.config import get_stream_writer
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

model = GenericFakeChatModel(messages=iter([AIMessage("Plants turn sunlight into food.")] * 20))

class State(TypedDict):
    messages: Annotated[list, add_messages]
    step: str

def research(s):
    writer = get_stream_writer()
    writer({"progress": "searching notes", "pct": 30})
    writer({"progress": "reading 3 sources", "pct": 60})
    return {"step": "researched"}

def answer(s):
    return {"messages": [model.invoke(s["messages"])]}

b = StateGraph(State)
b.add_node("research", research); b.add_node("answer", answer)
b.add_edge(START, "research"); b.add_edge("research", "answer"); b.add_edge("answer", END)
app = b.compile(checkpointer=InMemorySaver())

inp = {"messages": [HumanMessage("what is photosynthesis?")]}
for run, mode in enumerate(["values", "updates", "messages", "custom", "debug", "tasks", "checkpoints"]):
    chunks = list(app.stream(inp, {"configurable": {"thread_id": f"demo-{run}"}}, stream_mode=mode))
    if mode == "messages":
        first = f'[{type(chunks[0][0]).__name__}({chunks[0][0].content!r}), node={chunks[0][1]["langgraph_node"]}]'
    else:
        first = str(chunks[0])[:90]
    print(f"{mode:<12} {len(chunks):>3}  {first}")
```

**Output (shape)**

```
values         3  {"messages":[...HumanMessage...]}
updates        2  {"research":{"step":"researched"}}
messages      31  [AIMessageChunk("P"), node=answer]          ← Python: 9 chunks, word-sized
custom         2  {"progress":"searching notes","pct":30}
debug          4  {"step":1,"type":"task",...}
tasks          4  {"id":"...","name":"research","input":{...}}
checkpoints    3  {"config":{...},"values":{...},"next":["__start__"],...}
```

**What to take from it:**

1. `values` = `updates` + 1: the extra chunk is the state before any node ran.
2. The `messages` count is a property of the model, not the graph. Real providers stream
   roughly per token; the two fake models split differently, which is the only reason the JS
   and Python counts differ.
3. Each run uses a fresh `thread_id`. Reusing one would append to the same conversation,
   and `values` would grow with every loop iteration — a nice demonstration of why threads
   matter (Day 20).
</details>

---

### Exercise 2 — A clean token stream ●●○○○

Build `classify → answer`, where both nodes call a model. Stream to the terminal so that:

- each finished step prints a human label (`✓ Understood your question`),
- **only** the `answer` model's tokens are printed, filtered by **tag**,
- the whole thing uses a single multi-mode stream.

<details>
<summary>✅ Solution</summary>

**JavaScript**

```js
import { StateGraph, MessagesAnnotation, START, END } from "@langchain/langgraph";
import { FakeListChatModel } from "@langchain/core/utils/testing";
import { HumanMessage } from "@langchain/core/messages";

// swap for ChatGroq in real use — the tags are what matter
const classifier = new FakeListChatModel({ responses: ["CONCEPT"] }).withConfig({ tags: ["internal"] });
const answerer = new FakeListChatModel({ responses: ["HTTPS is HTTP running over TLS."] })
  .withConfig({ tags: ["final"] });

const app = new StateGraph(MessagesAnnotation)
  .addNode("classify", async (s) => ({ messages: [await classifier.invoke(s.messages)] }))
  .addNode("answer", async (s) => ({ messages: [await answerer.invoke(s.messages)] }))
  .addEdge(START, "classify").addEdge("classify", "answer").addEdge("answer", END)
  .compile();

const LABELS = { classify: "Understood your question", answer: "Done" };

for await (const [mode, chunk] of await app.stream(
  { messages: [new HumanMessage("How does HTTPS work?")] },
  { streamMode: ["updates", "messages"] }
)) {
  if (mode === "updates") {
    const node = Object.keys(chunk)[0];
    process.stdout.write(`\n✓ ${LABELS[node] ?? node}\n`);
  } else {
    const [token, meta] = chunk;
    if (meta.tags?.includes("final")) process.stdout.write(token.content);
  }
}
```

**Python**

```python
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import StateGraph, MessagesState, START, END

classifier = GenericFakeChatModel(messages=iter([AIMessage("CONCEPT")])).with_config(tags=["internal"])
answerer = GenericFakeChatModel(messages=iter([AIMessage("HTTPS is HTTP running over TLS.")])) \
    .with_config(tags=["final"])

b = StateGraph(MessagesState)
b.add_node("classify", lambda s: {"messages": [classifier.invoke(s["messages"])]})
b.add_node("answer", lambda s: {"messages": [answerer.invoke(s["messages"])]})
b.add_edge(START, "classify"); b.add_edge("classify", "answer"); b.add_edge("answer", END)
app = b.compile()

LABELS = {"classify": "Understood your question", "answer": "Done"}

for mode, chunk in app.stream({"messages": [HumanMessage("How does HTTPS work?")]},
                              stream_mode=["updates", "messages"]):
    if mode == "updates":
        node = next(iter(chunk))
        print(f"\n✓ {LABELS.get(node, node)}")
    else:
        token, meta = chunk
        if "final" in meta.get("tags", []):
            print(token.content, end="", flush=True)
```

**Output**

```
✓ Understood your question
HTTPS is HTTP running over TLS.
✓ Done
```

**Why tag instead of node name?** Rename `answer` to `respond` and a node-name filter
silently shows nothing. A tag lives on the model and states the intent — "these are the
words the user reads" — which survives refactors and is obvious in code review.

**Notice the order:** the answer's tokens arrive *before* `✓ Done`, because an `updates` chunk
lands when the node finishes. If you want "Writing…" to show while tokens flow, emit it as a
custom event at the start of the node, or show it when the first `final` token arrives.
</details>

---

### Exercise 3 — Break it five ways ●●○○○

Predict, then run.

1. Stream in `checkpoints` mode without a checkpointer.
2. In JS, `break` out of the stream after the first chunk of a three-node chain. Did the third
   node run?
3. In JS, abort with a signal after the first chunk, with a slow second node that ignores
   `config.signal`. Then again with a node that honours it.
4. In Python, invoke a subagent graph inside a tool and stream the parent in `messages` mode,
   with and without `subgraphs=True`.
5. Write an SSE event with a single `\n` at the end instead of `\n\n`.

<details>
<summary>✅ Solution</summary>

| # | Symptom (verified) | Why |
|---|---|---|
| 1 | JS: `TypeError: Cannot read properties of undefined (reading 'slice')` · Python: `IndexError: list index out of range` | Checkpoint events come from the checkpointer; there isn't one. |
| 2 | `first > second > third` — **the graph finished in the background** | In JS, leaving the loop doesn't cancel the run. |
| 3 | Ignoring the signal: `first > second(finishes) > [stream throws AbortError]`, third never runs. Honouring it: `second` is cut off mid-wait. | The signal stops the graph between supersteps; only a node that listens can stop mid-step. |
| 4 | Without `subgraphs`: 1 chunk, all from the parent node. With it: 6 chunks, namespaced under the parent node. | Python only forwards nested graphs' tokens when you opt in. JS forwards them by default. |
| 5 | Nothing renders until the next event — then both appear at once | An SSE event ends at a blank line. |

**Repro for #2 and #3 — JavaScript**

```js
import { StateGraph, MessagesAnnotation, START, END } from "@langchain/langgraph";
import { HumanMessage } from "@langchain/core/messages";

const input = { messages: [new HumanMessage("x")] };
const wait = (ms, signal) => new Promise((resolve, reject) => {
  const t = setTimeout(resolve, ms);
  signal?.addEventListener("abort", () => { clearTimeout(t); reject(new Error("aborted-in-node")); });
});

function build(log, honourSignal) {
  return new StateGraph(MessagesAnnotation)
    .addNode("first", () => { log.push("first"); return {}; })
    .addNode("second", async (s, config) => {
      log.push("second:start");
      try { await wait(150, honourSignal ? config.signal : undefined); log.push("second:end"); }
      catch (e) { log.push("second:" + e.message); throw e; }
      return {};
    })
    .addNode("third", () => { log.push("third"); return {}; })
    .addEdge(START, "first").addEdge("first", "second")
    .addEdge("second", "third").addEdge("third", END)
    .compile();
}

// #2 — break only
{
  const log = [];
  for await (const _ of await build(log, false).stream(input, { streamMode: "updates" })) break;
  await wait(500);
  console.log("break:", log.join(" > "));          // first > second:start > second:end > third
}

// #3 — abort, with and without honouring the signal
for (const honour of [false, true]) {
  const log = [];
  const ac = new AbortController();
  try {
    for await (const _ of await build(log, honour).stream(input, { streamMode: "updates", signal: ac.signal })) ac.abort();
  } catch (e) { log.push("stream threw " + e.name); }
  await wait(500);
  console.log(`abort (honour=${honour}):`, log.join(" > "));
}
```

**Repro for #4 — Python**

```python
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, MessagesState, START, END

sub_model = GenericFakeChatModel(messages=iter([AIMessage("sub says hello")] * 5))
sb = StateGraph(MessagesState)
sb.add_node("sub_llm", lambda s: {"messages": [sub_model.invoke(s["messages"])]})
sb.add_edge(START, "sub_llm"); sb.add_edge("sub_llm", END)
sub = sb.compile()

@tool
def ask_sub(task: str) -> str:
    """Delegate to the sub-agent."""
    return sub.invoke({"messages": [HumanMessage(task)]})["messages"][-1].content

pb = StateGraph(MessagesState)
pb.add_node("delegate", lambda s: {"messages": [AIMessage(ask_sub.invoke({"task": "x"}))]})
pb.add_edge(START, "delegate"); pb.add_edge("delegate", END)
parent = pb.compile()

inp = {"messages": [HumanMessage("x")]}
print("default:", len(list(parent.stream(inp, stream_mode="messages"))), "chunks")
for ns, (token, meta) in parent.stream(inp, stream_mode="messages", subgraphs=True):
    print(ns or "(root)", meta["langgraph_node"], repr(token.content))
```

**The lesson in one line:** cancellation and nested streaming are exactly where the two
languages part ways, so test them explicitly when you port code — the happy path looks the
same in both.
</details>

---

### Exercise 4 — 🎯 Stream StudyBuddy v5 to a browser ●●●●○

Put Day 22's supervisor behind an SSE endpoint:

1. `POST /chat` with `{ text, threadId }`, persisting the conversation with a checkpointer.
2. Events: `progress` (custom events from specialist tools), `step` (human-labelled node
   updates), `token` (**only** the supervisor's words), `done`, `error`.
3. The client disconnecting must stop the work.
4. A minimal browser page that shows progress lines and the answer as it streams.

<details>
<summary>✅ Solution</summary>

**JavaScript — `server.mjs`**

```js
import http from "node:http";
import { readFile } from "node:fs/promises";
import { createAgent, tool } from "langchain";
import { ChatGroq } from "@langchain/groq";
import { HumanMessage } from "@langchain/core/messages";
import { MemorySaver } from "@langchain/langgraph";
import { z } from "zod";

const base = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });

// specialists (Day 22), untagged — their tokens are NOT for the student
const researcher = createAgent({ model: base, tools: [], name: "researcher",
  systemPrompt: "Explain study topics accurately in under 120 words." });
const quizmaster = createAgent({ model: base, tools: [], name: "quizmaster",
  systemPrompt: "Write exactly the number of quiz questions requested, numbered." });

function asTool(agent, name, description, label) {
  return tool(
    async ({ task, context }, config) => {
      config.writer?.({ message: `${label}…` });                       // progress event
      const out = await agent.invoke(
        { messages: [new HumanMessage(context ? `${task}\n\nContext:\n${context}` : task)] },
        { signal: config.signal }                                      // stop if the client leaves
      );
      config.writer?.({ message: `${label} — done` });
      return String(out.messages.at(-1).content).slice(0, 1500);
    },
    { name, description, schema: z.object({
        task: z.string().describe("Self-contained instruction; the specialist sees nothing else."),
        context: z.string().optional(),
    }) }
  );
}

// the supervisor's model is the ONLY one tagged "final"
const studybuddy = createAgent({
  model: base.withConfig({ tags: ["final"] }),
  tools: [
    asTool(researcher, "ask_researcher", "Explanations and facts.", "Asking the researcher"),
    asTool(quizmaster, "ask_quizmaster", "Quiz questions; pass material in context.", "Writing quiz questions"),
  ],
  name: "studybuddy",
  checkpointer: new MemorySaver(),
  systemPrompt: "You are StudyBuddy. Delegate real work to specialists; answer the student yourself.",
});

const LABELS = { model_request: "Thinking", tools: "Consulting specialists" };

const server = http.createServer(async (req, res) => {
  if (req.method === "GET" && req.url === "/") {
    res.writeHead(200, { "Content-Type": "text/html" });
    res.end(await readFile(new URL("./index.html", import.meta.url)));
    return;
  }
  if (req.method !== "POST" || req.url !== "/chat") { res.writeHead(404).end(); return; }

  let raw = "";
  for await (const part of req) raw += part;
  const { text, threadId } = JSON.parse(raw);

  res.writeHead(200, {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    Connection: "keep-alive",
    "X-Accel-Buffering": "no",
  });
  const send = (event, data) => res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);

  const abort = new AbortController();
  req.on("close", () => abort.abort());                                   // 3 ✅

  try {
    for await (const [mode, chunk] of await studybuddy.graph.stream(
      { messages: [new HumanMessage(text)] },
      {
        streamMode: ["updates", "messages", "custom"],
        signal: abort.signal,
        configurable: { thread_id: threadId },                            // 1 ✅
      }
    )) {
      if (mode === "custom") send("progress", chunk);                     // 2 ✅
      else if (mode === "updates") {
        const node = Object.keys(chunk)[0];
        send("step", { label: LABELS[node] ?? node });
      } else {
        const [token, meta] = chunk;
        if (meta.tags?.includes("final") && typeof token.content === "string" && token.content)
          send("token", { text: token.content });
      }
    }
    send("done", {});
  } catch (err) {
    if (err.name !== "AbortError") { console.error(err); send("error", { message: "Something went wrong." }); }
  } finally {
    res.end();
  }
});

server.listen(3000, () => console.log("http://localhost:3000"));
```

> 📦 `studybuddy.graph.stream(...)` — the JS `createAgent` wrapper's compiled graph lives on
> `.graph` (Day 22), which is what exposes the full `stream()` options. The node names inside
> an agent graph are an implementation detail of `createAgent`; map the ones you care about
> to labels and fall back to the raw name, as above.

**`index.html`** (shared by both servers)

```html
<!doctype html>
<meta charset="utf-8">
<title>StudyBuddy</title>
<style>
  body { font: 16px/1.5 system-ui; max-width: 40rem; margin: 2rem auto; padding: 0 1rem; }
  #steps { color: #666; font-size: 14px; }
  #answer { white-space: pre-wrap; margin-top: 1rem; }
</style>
<form id="f"><input id="q" size="50" value="Explain HTTPS and give me 2 quiz questions"> <button>Ask</button> <button type="button" id="stop">Stop</button></form>
<div id="steps"></div>
<div id="answer"></div>
<script>
  let controller;
  const threadId = "student-" + Math.random().toString(36).slice(2);
  const $ = (id) => document.getElementById(id);

  $("stop").onclick = () => controller?.abort();          // cancelling here stops the server's graph

  $("f").onsubmit = async (e) => {
    e.preventDefault();
    $("steps").textContent = ""; $("answer").textContent = "";
    controller = new AbortController();

    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: $("q").value, threadId }),
      signal: controller.signal,
    });
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    const handle = {
      progress: (d) => $("steps").insertAdjacentHTML("beforeend", `<div>… ${d.message}</div>`),
      step: (d) => $("steps").insertAdjacentHTML("beforeend", `<div>✓ ${d.label}</div>`),
      token: (d) => $("answer").textContent += d.text,
      error: (d) => $("answer").textContent = "⚠️ " + d.message,
      done: () => {},
    };

    try {
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let end;
        while ((end = buffer.indexOf("\n\n")) >= 0) {
          const raw = buffer.slice(0, end); buffer = buffer.slice(end + 2);
          const event = raw.match(/^event: (.*)$/m)?.[1];
          const data = JSON.parse(raw.match(/^data: (.*)$/m)?.[1] ?? "null");
          handle[event]?.(data);
        }
      }
    } catch (err) {
      if (err.name !== "AbortError") throw err;
    }
  };
</script>
```

(The progress and step text come from your own code, not from users, so `insertAdjacentHTML`
is safe here. If you ever render user- or model-supplied text that way, escape it first —
the answer uses `textContent` for exactly that reason.)

**Python — `server.py`**

```python
import json
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.config import get_stream_writer

base = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

researcher = create_agent(base, tools=[], name="researcher",
    system_prompt="Explain study topics accurately in under 120 words.")
quizmaster = create_agent(base, tools=[], name="quizmaster",
    system_prompt="Write exactly the number of quiz questions requested, numbered.")

async def run_specialist(agent, label: str, task: str, context: str) -> str:
    writer = get_stream_writer()
    writer({"message": f"{label}…"})
    brief = f"{task}\n\nContext:\n{context}" if context else task
    out = await agent.ainvoke({"messages": [HumanMessage(brief)]})
    writer({"message": f"{label} — done"})
    return str(out["messages"][-1].content)[:1500]

@tool
async def ask_researcher(task: str, context: str = "") -> str:
    """Explanations and facts. The specialist sees only `task` and `context`."""
    return await run_specialist(researcher, "Asking the researcher", task, context)

@tool
async def ask_quizmaster(task: str, context: str = "") -> str:
    """Quiz questions; pass the material in `context`."""
    return await run_specialist(quizmaster, "Writing quiz questions", task, context)

studybuddy = create_agent(
    base.with_config(tags=["final"]),                 # the ONLY model tagged "final"
    tools=[ask_researcher, ask_quizmaster],
    name="studybuddy",
    checkpointer=InMemorySaver(),
    system_prompt="You are StudyBuddy. Delegate real work to specialists; answer the student yourself.",
)

LABELS = {"model": "Thinking", "tools": "Consulting specialists"}
api = FastAPI()

class ChatBody(BaseModel):
    text: str
    threadId: str

def sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"

@api.get("/", response_class=HTMLResponse)
async def index():
    return Path("index.html").read_text(encoding="utf-8")

@api.post("/chat")
async def chat(body: ChatBody):
    async def events():
        try:
            async for mode, chunk in studybuddy.astream(
                {"messages": [HumanMessage(body.text)]},
                {"configurable": {"thread_id": body.threadId}},
                stream_mode=["updates", "messages", "custom"],
            ):
                if mode == "custom":
                    yield sse("progress", chunk)
                elif mode == "updates":
                    node = next(iter(chunk))
                    yield sse("step", {"label": LABELS.get(node, node)})
                else:
                    token, meta = chunk
                    if "final" in meta.get("tags", []) and isinstance(token.content, str) and token.content:
                        yield sse("token", {"text": token.content})
            yield sse("done", {})
        except Exception:
            yield sse("error", {"message": "Something went wrong."})

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

# run with:  uvicorn server:api --reload
```

**Design decisions worth defending:**

1. **Tag the supervisor, not the specialists.** One `withConfig({ tags: ["final"] })` decides
   what the student reads. In JS, where specialists' tokens reach the parent stream by
   default, this is what keeps their drafts out of the UI; in Python it's what separates the
   supervisor's words from its routing thoughts.
2. **Progress comes from the tool wrapper.** The wrapper already knows the human-readable
   label ("Asking the researcher"), so it emits the custom event. No state channel, no
   checkpoint writes.
3. **Cancellation is end to end.** Browser "Stop" → `fetch` aborts → the server sees the
   connection close → JS aborts the graph's signal (and the specialist call, via
   `config.signal`), Python's response generator is cancelled, closing `astream`. Without
   this chain, every "Stop" click keeps spending tokens.
4. **`typeof token.content === "string" && token.content`** skips empty chunks and the
   non-text content blocks some providers emit around tool calls — the supervisor's tool-call
   message has empty text content, which you don't want to send as an empty token event.
5. **One thread per browser tab.** The random `threadId` gives each tab its own conversation
   in the checkpointer. In a real app it comes from your server's session and is checked
   for ownership (Day 20's IDOR warning).
</details>

---

### Exercise 5 — Design review: a streaming architecture ●●●○○

A team ships this:

```
   • Each browser opens a WebSocket on page load and keeps it open all day.
   • The server keeps the user's LangGraph run object in memory for that socket.
   • Every superstep, it sends { streamMode: "values" } chunks over the socket.
   • If the socket drops, the client reconnects and re-sends the last message.
   • Behind nginx with default settings; responses are gzip-compressed.
```

Symptoms: memory grows through the day, answers sometimes arrive all at once, and some
users are charged twice for the same "generate a study plan" request. Find the problems and
redesign it.

<details>
<summary>✅ Solution</summary>

| # | Problem | Symptom it causes | Fix |
|---|---|---|---|
| 1 | Run state held in server memory per socket | Memory growth; lost runs on deploy; no horizontal scaling | Checkpointer + `thread_id`; the server holds nothing (Day 20) |
| 2 | `values` mode on the wire | Bandwidth grows with conversation length; sluggish UIs | `updates` + tagged `messages` + `custom` |
| 3 | Reconnect re-sends the message | **Duplicate runs** — the double charge | Separate *start* from *watch*: `POST /runs` returns a run id; reconnects re-attach to `GET /runs/:id/stream` |
| 4 | No idempotency on side effects | The duplicate run actually charges twice | Idempotency keys on tool side effects; gates from Day 21 |
| 5 | nginx buffering + gzip | "Arrives all at once" | `X-Accel-Buffering: no` (or `proxy_buffering off`), no compression for `text/event-stream` |
| 6 | WebSocket for one-way streaming | Custom reconnect logic, harder auth and proxying | SSE: plain HTTP, automatic reconnects, works with standard auth |
| 7 | No cancellation story | Abandoned requests keep running | Abort on disconnect (JS signal + `config.signal`; Python generator close) |

**The redesign**

```
   POST /threads/:threadId/runs          body: { text, idempotencyKey }
     → validates ownership of threadId
     → if idempotencyKey was seen: return the existing runId          (fixes #3/#4)
     → starts the run in the background with the checkpointer
     → 202 { runId }

   GET /threads/:threadId/runs/:runId/stream     (SSE)
     → streams updates / final tokens / custom events for that run
     → on reconnect: sends a short "state so far" summary from getState(),
       then continues with live events — it never restarts the run
     → on disconnect: stops STREAMING, not the run (the run owns its lifecycle;
       an explicit POST /runs/:id/cancel stops the work)

   Storage: checkpointer (Postgres) keyed by thread_id; a runs table
            (run_id, thread_id, idempotency_key, status)
   Edge:    nginx with proxy_buffering off for the stream route; no gzip on it
```

**The trade-off to state out loud:** decoupling the run from the connection means a closed
tab *doesn't* cancel the work automatically — which is what you want for "generate my study
plan" (the user expects it to be ready when they come back) and not what you want for a chat
reply nobody will read. Decide per endpoint: chat replies cancel on disconnect; long jobs
run to completion with an explicit cancel button. This is also the model the LangGraph
platform uses for runs (Day 27), so designing towards it now makes that migration trivial.
</details>

---

## 9. Interview questions

### Basic

**Q1. Why stream at all, if the total time doesn't change?**

Because users judge speed by time-to-first-feedback, not time-to-completion. Streaming
progress and tokens makes an 8-second response feel responsive, reduces abandonment and
double-submits, and shows the user the system is working on the right thing.

---

**Q2. Name LangGraph's stream modes.**

`values` (full state after each superstep), `updates` (each node's returned patch),
`messages` (LLM token chunks with metadata), `custom` (your own events), plus `debug`,
`tasks` and `checkpoints` for internals. You can request several; chunks then come tagged
with their mode.

---

**Q3. How do you get tokens out of a node that calls `model.invoke()`?**

Stream the graph with `streamMode: "messages"`. Model calls report tokens through callbacks
and LangGraph forwards them, tagged with the node that produced them — you don't need to
change `invoke` to `stream` inside the node.

---

**Q4. How do you emit custom progress events?**

JS: call `config.writer({...})` in a node or tool (it receives `config`). Python: call
`get_stream_writer()({...})` from `langgraph.config`. Stream with `custom` mode to receive
them. They're immediate and never persisted.

---

**Q5. Why SSE rather than WebSockets for streaming responses?**

The data flows one way, server to client. SSE is plain HTTP, so auth, proxies and CDNs work
normally; browsers reconnect automatically; and the format is trivial. WebSockets are for
genuinely bidirectional traffic. The one limitation — `EventSource` is GET-only with no
custom headers — is solved by reading the stream with `fetch`.

---

### Intermediate

**Q6. Your UI shows the router's output before the answer. Fix it.**

Every model call in the graph streams in `messages` mode, not just the one producing the
answer. Tag the answering model — `model.withConfig({ tags: ["final"] })` — and forward only
chunks whose metadata tags include `"final"`. Filtering by `langgraph_node` also works but
breaks when nodes are renamed; tags state intent.

---

**Q7. How does cancellation work when a client disconnects?**

It differs by language. In JS, leaving the `for await` loop doesn't stop the graph — it runs
to completion in the background (verified). You pass an `AbortSignal` to `stream()`, which
stops the graph between supersteps, and pass `config.signal` into slow calls inside nodes so
the in-flight step stops too. In Python, closing the stream generator — a `break`, or a web
framework cancelling the response on disconnect — stops the graph before the next superstep;
the running node still finishes.

---

**Q8. How do you stream a multi-agent system where specialists run inside tools?**

In JS, a nested graph's tokens reach the parent's `messages` stream by default, so filter by
tag to keep specialists' drafts out of the user's view. In Python they don't appear unless
you stream with `subgraphs=True`, which yields `(namespace, (token, meta))` — the namespace
tells you which specialist is talking, handy for "researcher is typing…" indicators. Tag the
supervisor's model `final` either way.

---

**Q9. Why is `values` mode a poor choice for a web client?**

It sends the whole state after every superstep. With a real conversation and a multi-node
graph, that's the entire history several times per request, to deliver one new message.
`updates` sends only diffs and `messages` only tokens.

---

**Q10. Everything streams on localhost; in production it arrives all at once. Why?**

Buffering between the server and the browser — compression middleware, nginx's proxy
buffering, or a platform that doesn't support streamed responses. Disable compression for
`text/event-stream`, send `X-Accel-Buffering: no` (or turn proxy buffering off), and verify
in the browser's network tab that the body grows while the request is pending.

---

**Q11. What's `streamEvents` / `astream_events` for, now that stream modes exist?**

It's the older, lower-level event stream: every start/stream/end event for every runnable in
the run. Useful for plain LCEL chains or for events stream modes don't expose. For graphs,
stream modes are simpler, more stable, and less noisy — the exact event counts differ between
the JS and Python implementations, which tells you not to build a UI on them.

---

### Advanced

**Q12. Design streaming for a long-running agent job (minutes) that users may leave and come back to.**

Separate starting a run from watching it. `POST /runs` validates ownership, deduplicates with
an idempotency key, starts the run in the background with a checkpointer, and returns a run
id. `GET /runs/:id/stream` streams events via SSE; a reconnect sends a "state so far" summary
from `getState` and then attaches to live events, never restarting the work. The connection
dropping stops streaming, not the run; an explicit cancel endpoint stops the work. Progress
comes from custom events emitted in long nodes, which also serve as keep-alives. Side effects
are idempotent so a retried step can't double-act. This is also the platform's run model, so
it migrates cleanly.

---

**Q13. How would you test streaming code?**

Use scripted or fake streaming models so token sequences are deterministic, and assert on
the *sequence of events*, not only the final text: the right progress events in order, only
`final`-tagged tokens forwarded, a `done` at the end, an `error` event with a generic message
on failure. Test cancellation explicitly — abort after the first chunk and assert that later
nodes did not run (and, in JS, that you passed the signal, since `break` alone won't pass
that test). Run one end-to-end test through a real HTTP server and a real stream parser, as
in §4.6, because framing bugs (a missing blank line, split multi-byte characters) only show
up there.

---

**Q14. What are the security considerations for streaming endpoints?**

The same as any endpoint, plus a few specific ones: authenticate the stream route and check
thread ownership (a stream is a read of the conversation); never forward raw exceptions,
since they end up in the browser; don't stream internal tokens (routers, graders,
specialists' drafts, tool arguments) that can reveal prompts or other data; bound
concurrency per user, because long-lived connections are a cheap way to exhaust a server; and
make sure cancellation works, since unstopped abandoned runs are a cost-exhaustion vector.

---

**Q15. How do streaming and human-in-the-loop interact?**

An interrupt ends the current stream: the run pauses, the checkpoint holds the pending
question, and the stream completes. The UI should treat that as a normal end state — show
the approval request (read it from the stream's final update or from `getState().tasks`) —
and resuming is a new request, which can itself be streamed. The design rule from Q12
applies: the pause lives in the checkpointer, not in a held-open connection, so a user can
approve from a different device an hour later.

---

## 10. Recap

### What you learned

- ✅ Streaming improves **perceived** latency — the total time doesn't change, the experience does
- ✅ Modes: **`values` · `updates` · `messages` · `custom`** (+ `debug`/`tasks`/`checkpoints`)
- ✅ A node calling `model.invoke()` still streams tokens — **no node changes needed**
- ✅ **Every** model call streams; filter to the user-facing one with a **`final` tag**
- ✅ Custom events: `config.writer` (JS) / `get_stream_writer()` (Python) — from nodes **and tools**
- ✅ Several modes at once → `[mode, chunk]` / `(mode, chunk)`
- ✅ Nested agents: **JS includes their tokens by default; Python needs `subgraphs=True`**
- ✅ Cancellation: **JS `break` does not stop the graph** — use a signal and `config.signal`;
  Python stops before the next superstep when the generator closes
- ✅ SSE: `event:` + `data:` + **a blank line**; `fetch` + a reader for POST and auth headers
- ✅ Buffering (gzip, nginx) is the usual reason streaming "doesn't work" in production
- ✅ For long jobs, **separate starting a run from watching it**

### The streaming checklist

```
   □ updates → human labels          □ only "final"-tagged tokens reach the user
   □ custom events for slow steps    □ cancellation wired end to end
   □ generic error events            □ no buffering between server and browser
   □ SSE framing tested for real     □ runs survive reconnects without restarting
```

### Tomorrow

**[Day 24 — Reliability](day-24-reliability.md)**: streaming made StudyBuddy feel fast.
Tomorrow it learns to survive a bad day — provider outages, rate limits, timeouts, flaky
tools, runaway loops and prompt injection. Retries with backoff, fallbacks, call limits,
LangChain 1.x's built-in agent middleware, and LangGraph's node-level retry and timeout
policies.

### Quick self-check

1. A user clicks "Stop", your JS server `break`s out of the stream loop, and the bill keeps
   climbing. Why?
2. Your Python supervisor streams, but you never see the researcher's progress tokens. What
   are you missing?
3. What do you send, and not send, in an `error` event?

<details>
<summary>Answers</summary>

1. In JS, `break` stops your loop reading chunks; it does **not** cancel the graph, which keeps
   running to the end in the background (verified). Pass an `AbortSignal` to `stream()`,
   abort it when the client disconnects (`req.on("close")` or `request.signal`), and pass
   `config.signal` into slow calls inside nodes so the step in flight stops too.

2. **`subgraphs=True`.** In Python a graph invoked inside a tool doesn't contribute to the
   parent's `messages` stream unless you opt in (verified). With it, each item arrives as
   `(namespace, (token, meta))`, and the namespace tells you which specialist produced it. For
   step-level progress rather than tokens, emit custom events from the tool wrapper.

3. Send a **generic, user-safe message** ("Something went wrong — please try again") and,
   if useful, a correlation id the user can quote to support. Don't send the exception text,
   stack traces, SQL, file paths or prompt contents; log those on the server where you can
   read them.
</details>

---

<div align="center">

**[← Day 22 — Multi-Agent](day-22-multi-agent.md)** · **[Week 4 index](README.md)** · **[Day 24 — Reliability →](day-24-reliability.md)**

</div>
