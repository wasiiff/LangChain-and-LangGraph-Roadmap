# Day 18 — State & Reducers: What Goes Where

> ⏱ **Time:** ~2.5 hours · 🎯 **Prereqs:** [Day 17](day-17-langgraph-basics.md) · 🧩 **Difficulty:** ●●●○○

**Today you learn:** reducers properly — how to write them, the rules they must obey, and
what `addMessages` really does. Then the distinction that decides whether your app scales or
melts: **state vs context vs store vs checkpoint vs "memory."** By the end you'll be able to
look at any piece of data and say instantly where it belongs.

---

## 1. The problem

StudyBuddy is a graph now. Then five requests land in one sprint.

```
   1. "Remember that I prefer explanations in Urdu — in EVERY conversation."
   2. "Each node needs the Postgres connection."
   3. "Attach the student's 40-page textbook so the agent can quote it."
   4. "Don't show the internal scratchpad in the API response."
   5. "After 50 turns it's slow and expensive. Fix it."
```

The tempting move — the one nearly everyone makes first — is to put all five in state:

```js
const State = Annotation.Root({
  messages: Annotation({ reducer: addMessages, default: () => [] }),
  language: Annotation(),          // 1 ❌ belongs to the USER, not this conversation
  db: Annotation(),                // 2 ❌ not serialisable — it's a live socket
  textbook: Annotation(),          // 3 ❌ 2 MB, rewritten on every superstep
  scratchpad: Annotation(),        // 4 ❌ leaks into every response
  // 5 ❌ messages grows forever with no trimming rule
});
```

Every one of those is a real production incident:

| # | What actually happens |
|---|---|
| 1 | The preference is saved per-thread. New conversation → StudyBuddy speaks English again. |
| 2 | `TypeError: Converting circular structure to JSON` the moment you add a checkpointer. |
| 3 | 2 MB serialised **per node, per turn**. A 6-node graph over 20 turns writes 240 MB for one student. |
| 4 | Your public API returns the model's internal reasoning, including the raw prompt. |
| 5 | Token cost grows quadratically; turn 50 re-sends turns 1–49. |

Every one of them is the same mistake: **treating state as "the place where data goes."**

State is not a junk drawer. It is *specifically* the data that flows between nodes in one
run, and there are four other places data can live.

### The real-life version

Think about a doctor's consultation room.

```
   ┌───────────────────────────────────────────────────────────────┐
   │                                                                │
   │   THE DESK          the notes for THIS appointment             │  ← STATE
   │                     symptoms, today's readings, the plan       │
   │                                                                │
   │   THE FILING        this patient's history, allergies,         │  ← STORE
   │   CABINET           what worked last year — across ALL visits  │
   │                                                                │
   │   THE ROOM ITSELF   the lights, the stethoscope, which doctor  │  ← CONTEXT
   │                     is on shift — not written down, just here  │
   │                                                                │
   │   THE PHOTOCOPY     a copy of the desk, taken every few        │  ← CHECKPOINT
   │   TAKEN HOURLY      minutes, so a fire doesn't lose the notes  │
   │                                                                │
   └───────────────────────────────────────────────────────────────┘
```

You don't file the stethoscope. You don't photocopy the lights. You don't put last year's
allergy record on today's desk — you *look it up* from the cabinet when it's relevant, and
copy across only the one line that matters.

That's the whole of today.

---

## 2. Mental model

### The five places — the interview table

Learn this table. It's asked, in some form, in most LangGraph interviews.

| | **State** | **Context** (config) | **Store** | **Checkpoint** | **"Memory"** |
|---|---|---|---|---|---|
| **What it is** | data flowing between nodes | per-call inputs & handles | a key-value database | a saved snapshot of state | not an API |
| **Lives for** | one run (one thread with a checkpointer) | one invocation | forever | forever / TTL | — |
| **Scope** | one thread | one call | **across threads & users** | one thread | — |
| **Written by** | nodes, through reducers | the caller | nodes, explicitly | the framework, automatically | — |
| **Serialised?** | yes — **every superstep** | **no** | yes, by you | it *is* the serialisation | — |
| **Good for** | `messages`, `draft`, `score`, `stepCount` | `user_id`, model name, DB pool, API keys | "prefers Urdu", "is a beginner", past summaries | resume, replay, time travel | — |
| **Bad for** | connections, big blobs, cross-user facts | anything you need to persist | anything needed *this* turn only | — | — |

### The punchline: "memory" is not a thing

```
   ┌──────────────────────────────────────────────────────────────┐
   │                                                               │
   │   SHORT-TERM MEMORY   =   state  +  checkpointer              │
   │   (this conversation)     scoped by thread_id                 │
   │                                                               │
   │   LONG-TERM MEMORY    =   store                               │
   │   (this user, forever)    scoped by a namespace you choose    │
   │                                                               │
   └──────────────────────────────────────────────────────────────┘
```

In LangChain 0.x, "memory" *was* a class — `ConversationBufferMemory` and friends
([Day 14](../week-02-data-embeddings-and-rag/day-14-memory.md) covered why they were removed).
In 1.x, memory is an **outcome you build** out of the two mechanisms above. If an interviewer
asks "how does memory work in LangGraph?", the answer is that sentence, not a class name.

### Where the five requests actually belong

```
   1. "prefers Urdu"        → STORE      (crosses threads, outlives the run)
   2. Postgres connection   → CONTEXT    (not serialisable, per-process)
   3. 40-page textbook      → NEITHER    → vector store; keep a REFERENCE in state
   4. scratchpad            → STATE, but excluded from the OUTPUT schema
   5. growing history       → STATE, with a trimming rule in the reducer or a node
```

Note #3. The right answer wasn't one of the five places — it was "don't put it anywhere near
the graph." Recognising that is the difference between a system that works for ten users and
one that works for ten thousand.

### What a reducer actually is

```
                    node returns { tags: ["b", "c"] }
                                    │
                                    ▼
   existing ──────────►  ┌────────────────────┐
   ["a", "b"]            │      REDUCER        │ ────►  ["a", "b", "c"]
                         │ (existing, incoming)│         new channel value
                         └────────────────────┘
```

Three parts, every time: **what's there**, **what arrived**, **what should now be there.**
That's it. A reducer is a two-argument pure function. Everything below is just choosing the
right one.

---

## 3. First principles

### 3.1 The reducer contract

A reducer must satisfy four properties. Break any of them and you get bugs that only appear
under concurrency — the worst kind to debug.

```
   1. PURE          no side effects, no I/O, no clock, no random.
                    It may run more than once for the same write (on replay).

   2. TOTAL         it must handle (default, anything) — including the very
                    first write, when `existing` is the default value.

   3. NON-MUTATING  return a NEW value. Never `existing.push(...)`.
                    Other nodes in the same superstep hold that same reference.

   4. ASSOCIATIVE   (a ⊕ b) ⊕ c  must equal  a ⊕ (b ⊕ c)
                    because parallel writes are folded in pairs, in an order
                    you do not control.
```

Property 4 is the subtle one. When three nodes write the same channel in one superstep,
LangGraph folds their writes pairwise:

```
   existing ⊕ write1  →  r1
   r1       ⊕ write2  →  r2
   r2       ⊕ write3  →  final
```

Concatenation is associative, so append reducers are safe. So are `+` on numbers, `max`, set
union, and object merge. **Subtraction and division are not** — never write a reducer that
subtracts, because the result depends on an ordering you can't see.

```
   ✅ SAFE:   concat · add · max · min · set-union · object-merge · last-write-wins
   ❌ UNSAFE: subtract · divide · "append then truncate to first N" · anything using Date.now()
```

> ⚠️ "Append then keep the **last** N" is safe (it's a windowed fold). "Append then keep the
> **first** N" is not — with parallel writes, which items arrive first is non-deterministic.

### 3.2 What `addMessages` actually does

`addMessages` (JS) / `add_messages` (Python) is the reducer behind `MessagesAnnotation` /
`MessagesState`. It does four things, and only the first is obvious. All four are verified
below:

```
   1. APPENDS      new messages go on the end
   2. UPSERTS BY ID   a message with an EXISTING id REPLACES it instead of duplicating
   3. AUTO-IDS     messages without an id get a fresh UUID on the way in
   4. HANDLES REMOVALS  a RemoveMessage with an id deletes that message
                        a RemoveMessage with REMOVE_ALL_MESSAGES clears the list
```

Verified, both languages:

```
   existing:  [ {id:"1", "hi"},  {id:"2", "hello"} ]

   + [ {id:"2", "HELLO EDITED"} ]  →  [ {id:"1","hi"}, {id:"2","HELLO EDITED"} ]   ← upsert
   + [ RemoveMessage(id:"1") ]     →  [ {id:"2","hello"} ]                          ← delete
   + [ RemoveMessage(REMOVE_ALL) ] →  [ ]                                           ← clear
   + [ HumanMessage("x") ]         →  [ ..., {id:"<uuid>", "x"} ]                   ← auto-id
```

Property 2 is what makes human-in-the-loop message editing possible on Day 21: to change what
the user "said", you re-send the message with the same ID. Property 4 is how you implement
"forget this turn" and history trimming.

> 💡 It also accepts plain dicts and coerces them:
> `add_messages([], [{"role": "user", "content": "hey"}])` → `[HumanMessage(content='hey', id='…')]`.
> Convenient when messages arrive as JSON from a web request.

### 3.3 Three schemas, not one

A graph can declare **three** different shapes:

```
   INPUT SCHEMA     what callers are allowed to pass in
        │
        ▼
   INTERNAL STATE   everything the nodes need, including scratch work
        │
        ▼
   OUTPUT SCHEMA    what invoke() returns — a filtered view
```

Verified — the same graph, with a node that writes both `scratch` and `answer`:

```
   input:  { question: "q" }
   node:   returns { scratch: "thinking...", answer: "42" }
   output: { answer: "42" }        ← `scratch` and `question` are filtered out
```

That's request #4 from §1, solved in one constructor argument. It matters because a graph is
often exposed over HTTP, and your internal scratchpad — which may contain raw prompts,
retrieved documents, or another user's data in a shared-tenant bug — should not be in the
response body by default.

> 🔒 Treat the output schema as a **security boundary**, not a convenience. Default to
> returning the minimum, and add fields deliberately.

### 3.4 State vs context: the serialisation test

The rule that decides it, every time:

```
   Can it survive being turned into JSON and back?

     NO  → context (config).  Connections, clients, file handles, functions, class instances.
     YES → then ask: does it need to outlive this run?
             NO  → state
             YES → does it belong to the USER rather than the CONVERSATION?
                     NO  → state + checkpointer      (short-term memory)
                     YES → store                     (long-term memory)
```

Context is passed per-invocation and **never persisted**:

```js
await app.invoke(input, { configurable: { user_id: "u42", db: pool } });
```
```python
app.invoke(input, {"configurable": {"user_id": "u42", "db": pool}})
```

Nodes receive it as a second argument. It never touches a checkpoint, which is exactly why
it's the right home for secrets and handles.

### 3.5 The cost model of state

This is the part people learn the expensive way.

```
   With a checkpointer, the ENTIRE state is serialised and written
   after EVERY superstep.

   cost ≈ sizeof(state) × supersteps × turns × concurrent_users
```

Put a 2 MB textbook in state, run a 6-node graph, 20 turns, 1000 students:

```
   2 MB × 6 × 20 × 1000  =  240 GB written
```

Keep a reference instead:

```js
❌ textbook: Annotation()                      // the whole document
✅ textbookId: Annotation()                    // "doc_8891" — 8 bytes
   // nodes fetch the chunks they need from the vector store
```

```
   8 B × 6 × 20 × 1000  ≈  1 MB
```

Same functionality, five orders of magnitude less I/O. **State holds pointers and decisions,
not payloads.**

---

## 4. Code — JavaScript

### 4.1 A reducer cookbook

Six reducers that cover ~95% of real graphs.

```js
import { Annotation } from "@langchain/langgraph";

const State = Annotation.Root({

  // 1. LAST WRITE WINS — the default. Use for single-writer scalars.
  status: Annotation(),

  // 2. APPEND — the workhorse. Traces, logs, collected results.
  trace: Annotation({
    reducer: (existing, incoming) => existing.concat(incoming),
    default: () => [],
  }),

  // 3. COUNTER — nodes send a delta, not a total.
  steps: Annotation({
    reducer: (existing, incoming) => existing + incoming,
    default: () => 0,
  }),

  // 4. DEDUPING MERGE — safe under fan-out, order-independent.
  tags: Annotation({
    reducer: (existing, incoming) => {
      const seen = new Set(existing);
      return existing.concat(incoming.filter((t) => !seen.has(t) && (seen.add(t), true)));
    },
    default: () => [],
  }),

  // 5. CAPPED WINDOW — append, then keep the LAST n. (Keeping the FIRST n is unsafe.)
  recent: Annotation({
    reducer: (existing, incoming) => existing.concat(incoming).slice(-10),
    default: () => [],
  }),

  // 6. OBJECT MERGE — accumulate structured facts across nodes.
  profile: Annotation({
    reducer: (existing, incoming) => ({ ...existing, ...incoming }),
    default: () => ({}),
  }),
});
```

Verified for #4 — three nodes fanning out with overlapping tags:

```js
// x returns ["a","b"], y returns ["b","c"], both in superstep 1
await app.invoke({});
// { tags: [ 'a', 'b', 'c' ] }     ← "b" appears once, order preserved
```

> 🧪 **Test reducers directly.** They're pure two-argument functions, so they don't need a
> graph, a model, or a network:
> ```js
> assert.deepEqual(merge([], ["a"]), ["a"]);            // total: handles the default
> assert.deepEqual(merge(["a"], ["a", "b"]), ["a","b"]); // dedupes
> const orig = ["a"]; merge(orig, ["b"]); assert.deepEqual(orig, ["a"]);  // non-mutating
> ```
> This is the cheapest test in your whole suite and it catches the bug class that's hardest
> to reproduce.

### 4.2 `addMessages` in detail

```js
import { addMessages, REMOVE_ALL_MESSAGES } from "@langchain/langgraph";
import { HumanMessage, AIMessage, RemoveMessage } from "@langchain/core/messages";

const existing = [
  new HumanMessage({ content: "hi", id: "1" }),
  new AIMessage({ content: "hello", id: "2" }),
];

// APPEND
addMessages(existing, [new HumanMessage("how are you?")]);
// → 3 messages; the new one gets a generated UUID

// UPSERT — same id replaces
addMessages(existing, [new AIMessage({ content: "HELLO EDITED", id: "2" })]);
// → [ {id:"1", "hi"}, {id:"2", "HELLO EDITED"} ]      still 2 messages

// DELETE ONE
addMessages(existing, [new RemoveMessage({ id: "1" })]);
// → [ {id:"2", "hello"} ]

// CLEAR ALL
addMessages(existing, [new RemoveMessage({ id: REMOVE_ALL_MESSAGES })]);
// → []
```

> 📦 `addMessages` and `messagesStateReducer` are **the same function** — both exported from
> `@langchain/langgraph`, and `addMessages === messagesStateReducer` is `true`. You'll see
> both names in the wild. Prefer `addMessages`; it matches the Python name.

### 4.3 Trimming history *inside* the graph

Request #5. A node that keeps the conversation bounded:

```js
import { trimMessages } from "@langchain/core/messages";
import { RemoveMessage } from "@langchain/core/messages";

async function trim(state) {
  const kept = await trimMessages(state.messages, {
    maxTokens: 2000,
    strategy: "last",
    tokenCounter: model,          // the model counts its own tokens
    startOn: "human",             // never start on a tool result — the API rejects that
    includeSystem: true,
  });

  const keptIds = new Set(kept.map((m) => m.id));
  const toRemove = state.messages
    .filter((m) => !keptIds.has(m.id))
    .map((m) => new RemoveMessage({ id: m.id }));

  return { messages: toRemove };   // deletions ARE the update
}

const app = new StateGraph(MessagesAnnotation)
  .addNode("trim", trim)
  .addNode("agent", agentNode)
  .addEdge(START, "trim")
  .addEdge("trim", "agent")        // trim BEFORE the model sees the history
  .addEdge("agent", END)
  .compile();
```

Two design points:

- **Trimming is a node, not a hidden feature.** It shows up in your diagram, in your stream
  events, and in your checkpoints — you can see exactly when history was cut.
- **It emits `RemoveMessage`s.** Because `addMessages` understands removals, "delete these
  messages" is just another state update. Nothing special.

> ⚠️ `startOn: "human"` is not optional. Cut a window that begins with a `ToolMessage` whose
> matching `AIMessage` was trimmed away, and the provider rejects the whole request. This is
> the most common cause of a 400 after adding trimming.

### 4.4 Three schemas — hide the scratchpad

```js
import { StateGraph, Annotation, START, END } from "@langchain/langgraph";

const InputSchema  = Annotation.Root({ question: Annotation() });
const OutputSchema = Annotation.Root({ answer: Annotation() });
const FullState    = Annotation.Root({
  question: Annotation(),
  scratch: Annotation(),        // internal only
  answer: Annotation(),
});

const app = new StateGraph({
  stateSchema: FullState,
  input: InputSchema,
  output: OutputSchema,
})
  .addNode("think", (s) => ({ scratch: `reasoning about ${s.question}...` }))
  .addNode("answer", (s) => ({ answer: "42" }))
  .addEdge(START, "think")
  .addEdge("think", "answer")
  .addEdge("answer", END)
  .compile();

console.log(await app.invoke({ question: "meaning of life?" }));
// { answer: '42' }         ← no `scratch`, no `question`
```

Nodes still see the full state. Only what leaves the graph is filtered.

### 4.5 Context — the things that must not be persisted

```js
import { StateGraph, Annotation, START, END } from "@langchain/langgraph";

const State = Annotation.Root({ answer: Annotation() });

// nodes take (state, config)
async function lookup(state, config) {
  const { user_id, db, tier } = config.configurable;
  const rows = await db.query("SELECT * FROM progress WHERE user_id = $1", [user_id]);
  return { answer: `${user_id} (${tier}) has ${rows.length} completed lessons` };
}

const app = new StateGraph(State)
  .addNode("lookup", lookup)
  .addEdge(START, "lookup")
  .addEdge("lookup", END)
  .compile();

await app.invoke({}, {
  configurable: {
    user_id: "u42",
    tier: "premium",
    db: pgPool,               // a live connection — NEVER put this in state
  },
});
// { answer: 'u42 (premium) has 7 completed lessons' }
```

```
   config.configurable
     ├─ is passed fresh on every invocation
     ├─ is NOT serialised into checkpoints
     ├─ is the right home for secrets, handles, and per-request flags
     └─ also carries `thread_id` — which is how checkpointing finds your conversation (Day 20)
```

### 4.6 The Store — memory that crosses conversations

Request #1: "remember I prefer Urdu, in *every* conversation."

```js
import { InMemoryStore, StateGraph, Annotation, START, END } from "@langchain/langgraph";

const store = new InMemoryStore();

// namespace = a tuple/array. key = a string. value = any JSON.
await store.put(["users", "u42"], "prefs", { lang: "ur", level: "beginner" });

console.log((await store.get(["users", "u42"], "prefs")).value);
// { lang: 'ur', level: 'beginner' }
console.log((await store.search(["users", "u42"])).map((i) => i.key));
// [ 'prefs' ]

// Nodes reach it through config.store — available because we compiled with it
const State = Annotation.Root({ answer: Annotation() });

const app = new StateGraph(State)
  .addNode("personalise", async (state, config) => {
    const prefs = await config.store.get(["users", config.configurable.user_id], "prefs");
    const lang = prefs?.value?.lang ?? "en";
    return { answer: `answering in ${lang}` };
  })
  .addEdge(START, "personalise")
  .addEdge("personalise", END)
  .compile({ store });                       // ← the store is compiled in, not passed per call

console.log(await app.invoke({}, { configurable: { user_id: "u42" } }));
// { answer: 'answering in ur' }
```

```
   STATE                       STORE
   ─────                       ─────
   scoped to a thread_id       scoped to a namespace YOU choose
   written by reducers         written by explicit .put()
   read implicitly (it's       read explicitly (.get / .search)
     the node's argument)
   "what's happening now"      "what we know about this user"
```

`InMemoryStore` is for development. Production swaps in a Postgres-backed store — the node
code doesn't change, which is the whole point of the abstraction.

### 4.7 Typed state that actually validates

Plain `Annotation()` gives you no runtime checking — that's why a typo'd channel name fails
silently ([Day 17](day-17-langgraph-basics.md), §7). In TypeScript you get compile-time
safety:

```ts
const State = Annotation.Root({
  question: Annotation<string>(),
  score: Annotation<number>(),
  tags: Annotation<string[]>({
    reducer: (a: string[], b: string[]) => a.concat(b),
    default: () => [],
  }),
});

// node return values are now type-checked against the channel set
```

If you're in plain JS, the pragmatic defence is to define channel names once and reference
them, so a typo is a `ReferenceError` rather than a silent drop:

```js
const K = { QUESTION: "question", SCORE: "score", TAGS: "tags" };
return { [K.SCORE]: 7 };          // typo → ReferenceError, immediately
```

---

## 5. Code — Python

### 5.1 A reducer cookbook

```python
import operator
from typing import Annotated, TypedDict

def merge_unique(existing: list[str], incoming: list[str]) -> list[str]:
    seen, out = set(existing), list(existing)
    for x in incoming:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out

def last_10(existing: list, incoming: list) -> list:
    return (existing + incoming)[-10:]

def merge_dicts(existing: dict, incoming: dict) -> dict:
    return {**existing, **incoming}

class State(TypedDict):
    status: str                                         # 1. last write wins (no reducer)
    trace: Annotated[list[str], operator.add]           # 2. append
    steps: Annotated[int, operator.add]                 # 3. counter
    tags: Annotated[list[str], merge_unique]            # 4. deduping merge
    recent: Annotated[list, last_10]                    # 5. capped window
    profile: Annotated[dict, merge_dicts]               # 6. object merge
```

Verified for #4 with parallel writers `["a","b"]` and `["b","c"]`:

```python
app.invoke({"tags": []})
# {'tags': ['a', 'b', 'c']}      ← "b" appears once
```

> 📦 **`Annotated[T, reducer]`** — the second element is the reducer. It's a two-argument
> callable `(existing, incoming) -> merged`; `operator.add` works for both lists (concat) and
> ints (sum), which is why it shows up everywhere.
>
> A channel with `Annotated[..., reducer]` starts from an empty value; a channel **without** a
> reducer has no default at all and simply won't appear in the output dict until something
> writes it.

```python
# reducers are pure functions — test them with no graph at all
assert merge_unique([], ["a"]) == ["a"]
assert merge_unique(["a"], ["a", "b"]) == ["a", "b"]
orig = ["a"]; merge_unique(orig, ["b"]); assert orig == ["a"]     # non-mutating
```

### 5.2 `add_messages` in detail

```python
from langgraph.graph.message import add_messages, REMOVE_ALL_MESSAGES
from langchain_core.messages import HumanMessage, AIMessage, RemoveMessage

existing = [HumanMessage(content="hi", id="1"), AIMessage(content="hello", id="2")]

# APPEND (and auto-id)
add_messages(existing, [HumanMessage("how are you?")])
# → 3 messages; the new one gets a generated UUID

# UPSERT — same id replaces
add_messages(existing, [AIMessage(content="HELLO EDITED", id="2")])
# → [('1','hi'), ('2','HELLO EDITED')]        still 2 messages

# DELETE ONE
add_messages(existing, [RemoveMessage(id="1")])
# → [('2','hello')]

# CLEAR ALL
add_messages(existing, [RemoveMessage(id=REMOVE_ALL_MESSAGES)])
# → []

# dicts are coerced
add_messages([], [{"role": "user", "content": "hey"}])
# → [HumanMessage(content='hey', id='d8c664e5-...')]
```

### 5.3 Trimming history inside the graph

```python
from langchain_core.messages import trim_messages, RemoveMessage

def trim(state: MessagesState) -> dict:
    kept = trim_messages(
        state["messages"],
        max_tokens=2000,
        strategy="last",
        token_counter=model,        # the model counts its own tokens
        start_on="human",           # never start on a tool result
        include_system=True,
    )
    kept_ids = {m.id for m in kept}
    removals = [RemoveMessage(id=m.id) for m in state["messages"] if m.id not in kept_ids]
    return {"messages": removals}   # deletions ARE the update

builder = StateGraph(MessagesState)
builder.add_node("trim", trim)
builder.add_node("agent", agent_node)
builder.add_edge(START, "trim")
builder.add_edge("trim", "agent")   # trim BEFORE the model sees the history
builder.add_edge("agent", END)
app = builder.compile()
```

### 5.4 Three schemas — hide the scratchpad

```python
from typing import TypedDict
from langgraph.graph import StateGraph, START, END

class InputSchema(TypedDict):
    question: str

class OutputSchema(TypedDict):
    answer: str

class FullState(TypedDict):
    question: str
    scratch: str          # internal only
    answer: str

builder = StateGraph(FullState, input_schema=InputSchema, output_schema=OutputSchema)
builder.add_node("think", lambda s: {"scratch": f'reasoning about {s["question"]}...'})
builder.add_node("answer", lambda s: {"answer": "42"})
builder.add_edge(START, "think")
builder.add_edge("think", "answer")
builder.add_edge("answer", END)
app = builder.compile()

print(app.invoke({"question": "meaning of life?"}))
# {'answer': '42'}        ← no 'scratch', no 'question'
```

> 📦 Note the keyword names: Python uses `input_schema=` / `output_schema=` on the
> `StateGraph` constructor; JS uses an object — `new StateGraph({ stateSchema, input, output })`.
> Older tutorials show Python's `input=` / `output=`; prefer the `_schema` names.

### 5.5 Context — the things that must not be persisted

```python
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END

class State(TypedDict):
    answer: str

# nodes take (state, config)
def lookup(state: State, config: RunnableConfig) -> dict:
    cfg = config["configurable"]
    rows = cfg["db"].query("SELECT * FROM progress WHERE user_id = %s", (cfg["user_id"],))
    return {"answer": f'{cfg["user_id"]} ({cfg["tier"]}) has {len(rows)} completed lessons'}

builder = StateGraph(State)
builder.add_node("lookup", lookup)
builder.add_edge(START, "lookup")
builder.add_edge("lookup", END)
app = builder.compile()

app.invoke({}, {"configurable": {
    "user_id": "u42",
    "tier": "premium",
    "db": pg_pool,          # a live connection — NEVER put this in state
}})
```

Verified minimal version:

```python
def node(state, config: RunnableConfig) -> dict:
    return {"out": f'user={config["configurable"].get("user_id")}'}

app.invoke({}, {"configurable": {"user_id": "u42"}})
# {'out': 'user=u42'}
```

### 5.6 The Store — memory that crosses conversations

```python
from langgraph.store.memory import InMemoryStore

store = InMemoryStore()

# namespace = a tuple. key = a string. value = any JSON.
store.put(("users", "u42"), "prefs", {"lang": "ur", "level": "beginner"})

print(store.get(("users", "u42"), "prefs").value)
# {'lang': 'ur', 'level': 'beginner'}
print([i.key for i in store.search(("users", "u42"))])
# ['prefs']

# Nodes receive the store as a KEYWORD-ONLY argument
class State(TypedDict):
    answer: str

def personalise(state: State, config: RunnableConfig, *, store) -> dict:
    item = store.get(("users", config["configurable"]["user_id"]), "prefs")
    lang = item.value["lang"] if item else "en"
    return {"answer": f"answering in {lang}"}

builder = StateGraph(State)
builder.add_node("personalise", personalise)
builder.add_edge(START, "personalise")
builder.add_edge("personalise", END)
app = builder.compile(store=store)          # ← compiled in, not passed per call

print(app.invoke({}, {"configurable": {"user_id": "u42"}}))
# {'answer': 'answering in ur'}
```

> ⚠️ **The signature differs across languages.** Python injects the store as a keyword-only
> parameter — `def node(state, config, *, store)`. JavaScript hands it to you on the config
> object — `config.store`. Forgetting the `*,` in Python gives you a store positional
> argument that never gets filled, and a confusing `TypeError`.

### 5.7 Pydantic state — validation for real

Python has an option JS doesn't: use a Pydantic model as your state schema and get **runtime
validation**.

```python
from pydantic import BaseModel

class State(BaseModel):
    n: int = 0

def bump(state: State) -> dict:
    return {"n": state.n + 1}        # note: ATTRIBUTE access, not state["n"]

builder = StateGraph(State)
builder.add_node("bump", bump)
builder.add_edge(START, "bump")
builder.add_edge("bump", END)
app = builder.compile()

print(app.invoke({"n": 5}))
# {'n': 6}

app.invoke({"n": "not-an-int"})
# pydantic_core.ValidationError: 1 validation error for State
#   n  Input should be a valid integer, unable to parse string as an integer
```

Three verified details that surprise people:

1. **Nodes receive a model instance** — `type(state).__name__` is `State`, so it's
   `state.n`, not `state["n"]`.
2. **`invoke` still returns a plain `dict`** — the Pydantic model validates going *in*, it
   doesn't wrap what comes *out*.
3. **Nodes still return dicts** — patches are dicts regardless of the state schema type.

Trade-off: validation costs a little speed on every superstep. Worth it for a public-facing
graph; usually not worth it for an internal one.

### 5.8 The full JS ↔ Python translation for today

| Concept | JavaScript | Python |
|---|---|---|
| append reducer | `reducer: (a, b) => a.concat(b)` | `Annotated[list, operator.add]` |
| counter reducer | `reducer: (a, b) => a + b, default: () => 0` | `Annotated[int, operator.add]` |
| custom reducer | `Annotation({ reducer: myFn, default: () => [] })` | `Annotated[list, my_fn]` |
| messages reducer | `addMessages` (= `messagesStateReducer`) | `add_messages` |
| clear all messages | `new RemoveMessage({ id: REMOVE_ALL_MESSAGES })` | `RemoveMessage(id=REMOVE_ALL_MESSAGES)` |
| trim history | `trimMessages(msgs, { maxTokens, startOn: "human" })` | `trim_messages(msgs, max_tokens=..., start_on="human")` |
| input/output schemas | `new StateGraph({ stateSchema, input, output })` | `StateGraph(S, input_schema=I, output_schema=O)` |
| node signature | `(state, config) => patch` | `def node(state, config)` |
| read config | `config.configurable.user_id` | `config["configurable"]["user_id"]` |
| store in node | `config.store` | `def node(state, config, *, store)` |
| compile with store | `.compile({ store })` | `.compile(store=store)` |
| store write | `await store.put(["users","u42"], "prefs", {...})` | `store.put(("users","u42"), "prefs", {...})` |
| store namespace type | **array** `["users", "u42"]` | **tuple** `("users", "u42")` |
| validated state | TypeScript `Annotation<string>()` (compile-time) | Pydantic `BaseModel` (runtime) |
| state access in node | `state.messages` | `state["messages"]` or `state.messages` (Pydantic) |

---

## 6. Under the hood

### 6.1 How a write becomes a state change

```
   node returns { tags: ["b","c"], steps: 1 }
        │
        ├─ 1. FILTER      keys not in the channel set are DROPPED, silently
        │                 { tags: [...], steps: 1, typo: "x" } → typo is gone
        │
        ├─ 2. QUEUE       each surviving key becomes a pending write on its channel
        │
        ├─ 3. FOLD        at end of superstep, per channel:
        │                    value = reducer(value, write₁)
        │                    value = reducer(value, write₂)     ← if fan-out
        │                    ...
        │
        ├─ 4. CHECKPOINT  if a checkpointer is set, the ENTIRE state is serialised
        │                 and written — Day 20
        │
        └─ 5. EMIT        stream subscribers get the patch (updates mode)
                          or the whole state (values mode) — Day 23
```

Step 1 is the silent-typo trap from Day 17. Step 3 is why associativity matters. Step 4 is
why state size is a throughput problem.

### 6.2 Why the reducer isn't just "merge the objects"

You could imagine LangGraph doing `{...state, ...patch}` and skipping reducers entirely.
That fails on three counts:

```
   1. ACCUMULATION   {...state, ...patch} on `messages` REPLACES the list.
                     Every conversation would be one message long.

   2. FAN-OUT        three nodes writing `notes` in one superstep — a plain spread
                     keeps whichever landed last. Two results vanish.

   3. DOMAIN LOGIC   "keep the last 10", "dedupe", "take the max", "sum" —
                     these are decisions about YOUR data. The framework can't guess.
```

The reducer is the extension point where you tell the framework what merging *means* for each
piece of your data. Once you see it that way, "which reducer?" becomes a design question
you ask about every channel, and the answer is usually obvious.

### 6.3 What actually goes into a checkpoint

```
   CHECKPOINTED                       NOT CHECKPOINTED
   ────────────                       ────────────────
   every channel's current value      config.configurable (your handles, keys, user_id)
   which nodes are next               the store's contents (it has its own storage)
   pending writes                     anything a node kept in a closure or module scope
   metadata (step number, source)     the model client, the DB pool
```

The consequence you must design for: **after a resume, config is supplied fresh by the
caller.** A node that read `config.configurable.tier` on turn 1 and expected it to still be
there on turn 40 will get whatever the caller passed *that* time. Config is per-call, always.
If something must survive, it belongs in state or the store.

### 6.4 Choosing where data goes — the decision tree

```
   Is it a live object? (connection, client, function, socket)
     └─ YES → CONTEXT.  It can't be serialised; don't try.

   Is it > ~100 KB?
     └─ YES → EXTERNAL STORAGE.  Keep a reference (id, URL, doc id) in state.

   Does it belong to the USER rather than this conversation?
     └─ YES → STORE.  Namespace it by user id.

   Do nodes in THIS run need to read or write it?
     └─ YES → STATE.  Pick the reducer deliberately.

   Otherwise → it probably shouldn't exist. Delete it.
```

Run every field through this before adding it. The last branch catches more than you'd think
— fields added "just in case" are the ones that turn into 40-key state objects nobody
understands six months later.

---

## 7. Common mistakes

### ❌ 1. A mutating reducer

```js
❌ reducer: (existing, incoming) => { existing.push(...incoming); return existing; }
✅ reducer: (existing, incoming) => existing.concat(incoming)
```
```python
❌ def r(existing, incoming): existing.extend(incoming); return existing
✅ def r(existing, incoming): return existing + incoming
```

The old array is still referenced by the snapshot other nodes are holding, and by the
previous checkpoint. Mutating it corrupts both — and produces the classic symptom where
**time travel shows the wrong history**, because the "past" checkpoint was edited in place.

### ❌ 2. A non-associative reducer

```js
❌ reducer: (existing, incoming) => existing - incoming        // order-dependent
❌ reducer: (existing, incoming) => existing.concat(incoming).slice(0, 10)  // keeps FIRST 10
✅ reducer: (existing, incoming) => existing.concat(incoming).slice(-10)    // keeps LAST 10
```

With parallel writes, the fold order is not yours to control. Anything where `(a⊕b)⊕c ≠ a⊕(b⊕c)`
gives non-deterministic results that pass every test and fail once a week in production.

### ❌ 3. Non-serialisable values in state

```js
❌ const State = Annotation.Root({ db: Annotation(), model: Annotation() });
✅ // pass them in config.configurable instead
```

Without a checkpointer this silently "works", which is the trap — it breaks the day you add
persistence, with `TypeError: Converting circular structure to JSON` (JS) or a pickling error
(Python). By then it's threaded through twelve nodes.

### ❌ 4. Big blobs in state

```js
❌ textbook: Annotation()            // 2 MB, serialised every superstep
✅ textbookId: Annotation()          // "doc_8891" — fetch chunks in the node
```

State is written on **every superstep**. Multiply by nodes × turns × users before putting
anything large in it.

### ❌ 5. User-level facts in thread-level state

```js
❌ preferredLanguage: Annotation()   // gone when the user opens a new chat
✅ await store.put(["users", userId], "prefs", { lang: "ur" });
```

The symptom is the classic "it forgot me" bug report: it works perfectly during testing
(you're in one thread) and fails for real users (who start new conversations).

### ❌ 6. `default` on the wrong side in Python

```python
❌ trace: Annotated[list[str], operator.add] = []      # this does nothing useful
✅ trace: Annotated[list[str], operator.add]           # the reducer implies the empty start
```

A `TypedDict` field assignment isn't a default value — `TypedDict` has no defaults. If you
need a genuine default, use a Pydantic state model with `Field(default_factory=list)`.

### ❌ 7. Forgetting `*` before `store` in Python

```python
❌ def node(state, config, store): ...      # store never gets injected
✅ def node(state, config, *, store): ...   # keyword-only — this is how it's detected
```

LangGraph inspects the signature and injects `store` only as a keyword argument. Without the
`*`, you get a `TypeError` about a missing positional argument that reads like a bug in the
framework.

### ❌ 8. Exposing internal state over HTTP

```js
❌ res.json(await app.invoke(input));                            // returns scratch, prompts, docs
✅ new StateGraph({ stateSchema: Full, input: In, output: Out }) // filter at the boundary
```

Treat the output schema as a security boundary. Retrieved documents in particular can contain
another tenant's content if your filter logic has a bug — don't ship them to the client by
accident on top of that.

### ❌ 9. Trimming without `startOn: "human"`

```js
❌ trimMessages(msgs, { maxTokens: 2000, strategy: "last" })
✅ trimMessages(msgs, { maxTokens: 2000, strategy: "last", startOn: "human" })
```

A window that starts with a `ToolMessage` whose `AIMessage` was trimmed away is an invalid
conversation. The provider returns a 400, and the error message rarely mentions trimming.

### ❌ 10. Thinking "memory" is a class you import

```js
❌ import { ConversationBufferMemory } from "langchain/memory";   // 0.x — gone
✅ // short-term: state + a checkpointer, scoped by thread_id
   // long-term:  a store, scoped by a namespace
```

There is no `Memory` class in 1.x. If a tutorial imports one, it's teaching a version that no
longer exists. This is also the single most common wrong answer in LangGraph interviews.

### ❌ 11. One giant state object

```js
❌ Annotation.Root({ /* 40 channels, every value the app has ever needed */ })
```

If you can't say in one sentence why each channel exists and who writes it, the graph has
outgrown its state design. Split it — subgraphs get their own state (Day 19), and most
"needed" fields turn out to be derivable or belong in the store.

---

## 8. Exercises

### Exercise 1 — Write four reducers and prove they're correct ●●○○○

Write and test, with **no graph involved**:

1. `mergeUnique` — append while removing duplicates, preserving first-seen order.
2. `lastN(n)` — a factory returning a reducer that keeps only the last `n` items.
3. `maxScore` — keeps the higher of two numbers.
4. `mergeProfiles` — deep-ish merge of two objects where array values concatenate.

For each, assert: **total** (handles the empty default), **non-mutating**, and
**associative**.

<details>
<summary>✅ Solution</summary>

**JavaScript**

```js
import assert from "node:assert";

// 1
const mergeUnique = (existing, incoming) => {
  const seen = new Set(existing);
  return existing.concat(incoming.filter((x) => !seen.has(x) && (seen.add(x), true)));
};

// 2 — a FACTORY, because the reducer signature is fixed at two arguments
const lastN = (n) => (existing, incoming) => existing.concat(incoming).slice(-n);

// 3
const maxScore = (existing, incoming) => Math.max(existing, incoming);

// 4
const mergeProfiles = (existing, incoming) => {
  const out = { ...existing };
  for (const [k, v] of Object.entries(incoming)) {
    out[k] = Array.isArray(v) && Array.isArray(existing[k]) ? existing[k].concat(v) : v;
  }
  return out;
};

// ── TOTAL: every reducer must handle the default as `existing` ──────────
assert.deepEqual(mergeUnique([], ["a"]), ["a"]);
assert.deepEqual(lastN(3)([], [1, 2]), [1, 2]);
assert.equal(maxScore(0, 5), 5);
assert.deepEqual(mergeProfiles({}, { lang: "ur" }), { lang: "ur" });

// ── NON-MUTATING ────────────────────────────────────────────────────────
const orig = ["a"];
mergeUnique(orig, ["b"]);
assert.deepEqual(orig, ["a"], "mergeUnique mutated its input");

const origObj = { tags: ["x"] };
mergeProfiles(origObj, { tags: ["y"] });
assert.deepEqual(origObj, { tags: ["x"] }, "mergeProfiles mutated its input");

// ── ASSOCIATIVE: (a⊕b)⊕c === a⊕(b⊕c) ────────────────────────────────────
const assoc = (f, a, b, c) =>
  assert.deepEqual(f(f(a, b), c), f(a, f(b, c)), `${f.name || "reducer"} is not associative`);

assoc(mergeUnique, ["a"], ["b"], ["a", "c"]);
assoc(maxScore, 3, 9, 5);
assoc(mergeProfiles, { tags: ["x"] }, { tags: ["y"] }, { tags: ["z"] });

// lastN IS associative — the fold order doesn't change which items are last
assoc(lastN(2), [1], [2], [3]);

// ── the counter-example, for contrast ───────────────────────────────────
const firstN = (n) => (existing, incoming) => existing.concat(incoming).slice(0, n);
try {
  assoc(firstN(2), [1], [2], [3]);
  console.log("firstN looked associative here — but only by luck");
} catch {
  console.log("✓ firstN is correctly detected as NON-associative");
}

const subtract = (a, b) => a - b;
try {
  assoc(subtract, 10, 3, 2);
} catch {
  console.log("✓ subtract is correctly detected as NON-associative");
}

console.log("all reducer laws hold");
```

**Python**

```python
from functools import reduce

# 1
def merge_unique(existing: list, incoming: list) -> list:
    seen, out = set(existing), list(existing)
    for x in incoming:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out

# 2 — a FACTORY
def last_n(n: int):
    def r(existing: list, incoming: list) -> list:
        return (existing + incoming)[-n:]
    r.__name__ = f"last_{n}"
    return r

# 3
def max_score(existing: int, incoming: int) -> int:
    return max(existing, incoming)

# 4
def merge_profiles(existing: dict, incoming: dict) -> dict:
    out = dict(existing)
    for k, v in incoming.items():
        if isinstance(v, list) and isinstance(existing.get(k), list):
            out[k] = existing[k] + v
        else:
            out[k] = v
    return out

# ── TOTAL ───────────────────────────────────────────────────────────────
assert merge_unique([], ["a"]) == ["a"]
assert last_n(3)([], [1, 2]) == [1, 2]
assert max_score(0, 5) == 5
assert merge_profiles({}, {"lang": "ur"}) == {"lang": "ur"}

# ── NON-MUTATING ────────────────────────────────────────────────────────
orig = ["a"]
merge_unique(orig, ["b"])
assert orig == ["a"], "merge_unique mutated its input"

orig_obj = {"tags": ["x"]}
merge_profiles(orig_obj, {"tags": ["y"]})
assert orig_obj == {"tags": ["x"]}, "merge_profiles mutated its input"

# ── ASSOCIATIVE ─────────────────────────────────────────────────────────
def assoc(f, a, b, c):
    assert f(f(a, b), c) == f(a, f(b, c)), f"{f.__name__} is not associative"

assoc(merge_unique, ["a"], ["b"], ["a", "c"])
assoc(max_score, 3, 9, 5)
assoc(merge_profiles, {"tags": ["x"]}, {"tags": ["y"]}, {"tags": ["z"]})
assoc(last_n(2), [1], [2], [3])

# ── counter-examples ────────────────────────────────────────────────────
def first_n(n):
    def r(existing, incoming): return (existing + incoming)[:n]
    r.__name__ = f"first_{n}"
    return r

for f, args in [(first_n(2), ([1], [2], [3])), (lambda a, b: a - b, (10, 3, 2))]:
    try:
        assoc(f, *args)
        print(f"{getattr(f, '__name__', 'lambda')}: looked associative here — but only by luck")
    except AssertionError:
        print(f"✓ {getattr(f, '__name__', 'subtract')} correctly detected as NON-associative")

print("all reducer laws hold")
```

**Why `lastN` passes and `firstN` doesn't.** "Keep the last n" is stable under regrouping —
the last n items of a concatenation are the same regardless of how you parenthesise it. "Keep
the first n" throws away items *early*, so a different fold order discards different items.
The general rule: a reducer that **discards from the end being appended** is unsafe; one that
**discards from the start** is safe.

**Why `maxScore` is fine but `subtract` isn't.** `max` is associative and commutative — the
canonical safe reducer. Subtraction is neither. If you catch yourself wanting a "decrement"
reducer, send a negative delta to an `add` reducer instead.
</details>

---

### Exercise 2 — Classify twelve fields ●●○○○

For each field in a real customer-support agent, say where it belongs — **state, context,
store, external storage, or nowhere** — and give the one-line reason.

```
 1. messages                      7. the OpenAI client instance
 2. ticketId                      8. the customer's full order history (400 KB)
 3. customerTier ("gold")         9. escalatedToHuman (bool)
 4. "this customer is rude to     10. resolutionAttempts (int)
     bots, escalate fast"         11. thread_id
 5. the Postgres pool             12. the current draft reply
 6. OPENAI_API_KEY
```

<details>
<summary>✅ Solution</summary>

| # | Field | Where | Why |
|---|---|---|---|
| 1 | `messages` | **State** (+ checkpointer) | The conversation *is* what flows between nodes. Needs a trimming rule. |
| 2 | `ticketId` | **State** | Small, scoped to this run, needed for routing and tool calls. |
| 3 | `customerTier` | **Context** | Comes from your auth layer per request. Putting it in state means a stale copy after a plan upgrade. |
| 4 | "rude to bots, escalate fast" | **Store**, namespaced `("customers", id)` | Crosses threads and outlives every conversation. This is long-term memory. |
| 5 | Postgres pool | **Context** | A live socket. Fails serialisation the moment you add a checkpointer. |
| 6 | `OPENAI_API_KEY` | **Neither** — environment | Never in state (checkpointed to disk), never in the store. Read from env inside the node or the client. |
| 7 | OpenAI client | **Context**, or a module-level singleton | Not serialisable; also expensive to recreate per call. |
| 8 | 400 KB order history | **External storage** | Query it in a node and keep only the *relevant* rows in state. 400 KB × supersteps × turns is your I/O budget. |
| 9 | `escalatedToHuman` | **State** | A decision made *in* this run that later nodes route on. |
| 10 | `resolutionAttempts` | **State**, with an `add` reducer | A counter nodes increment; the loop's budget exit reads it. |
| 11 | `thread_id` | **Context** (`configurable.thread_id`) | It's the *key* the checkpointer stores state under. It can't live in the thing it identifies. |
| 12 | current draft reply | **State** | Written by a node, read by the reviewer node, replaced on revision. Last-write-wins. |

**The three that catch people:**

- **#3 `customerTier`.** It feels like a fact about the user, so people reach for the store.
  But it's *authoritative in your billing system*, and a cached copy in the store goes stale
  the moment someone upgrades. Context means every run gets the current truth. The rule:
  **facts you can look up cheaply belong in context; facts only this system knows belong in
  the store.** #4 is the opposite case — nothing else knows the customer is rude to bots.

- **#6 the API key.** Every place except env is wrong, and state is the *most* wrong, because
  a checkpointer writes state to a database that probably has different access controls than
  your secrets manager. Secrets have leaked exactly this way.

- **#11 `thread_id`.** A classic chicken-and-egg. The checkpointer stores your state keyed by
  `thread_id`, so it must arrive from outside. It's always `config.configurable.thread_id`.
</details>

---

### Exercise 3 — Break it five ways ●●○○○

Predict the symptom, then run it.

1. Give a `notes` channel a reducer that does `existing.push(...incoming); return existing;`,
   then fan out three writers into it.
2. Give a `recent` channel the reducer `(a, b) => a.concat(b).slice(0, 3)` (first 3) and fan
   out three writers.
3. Put a function in state — `handler: Annotation()` — and compile with a `MemorySaver`.
4. Store a user preference in state instead of the store, then invoke twice with **different**
   `thread_id`s.
5. In Python, write `def node(state, config, store)` without the `*`.

<details>
<summary>✅ Solution</summary>

| # | Symptom | Why |
|---|---|---|
| 1 | Usually "works" in a single-writer test; under fan-out you get duplicated or missing entries, and — the tell — **time-travelling to an old checkpoint shows the *new* notes**. | The reducer mutated the array the previous checkpoint still references. The past was rewritten. This is the single hardest LangGraph bug to diagnose, which is why "reducers must not mutate" is a law and not a style preference. |
| 2 | Non-deterministic: you keep 3 of the writes, but **which** 3 changes between runs. | `slice(0, 3)` discards from the end of each fold, so the result depends on fold order. `slice(-3)` would be deterministic. |
| 3 | Works with no checkpointer. Add `MemorySaver` and it throws on the first superstep — a serialisation error (JS: a `TypeError` about converting to JSON; Python: a pickling/serialisation error). | Checkpointing serialises the entire state. Functions have no JSON representation. This is why "can it round-trip through JSON?" is *the* state-vs-context test. |
| 4 | Thread A remembers the preference. Thread B doesn't. Ship it, and users report "it forgot me" while it works perfectly on your machine. | State is scoped to `thread_id`. Cross-thread facts need the store. You never see this in development because you test in one thread. |
| 5 | `TypeError: node() missing 1 required positional argument: 'store'` | LangGraph detects the store dependency by looking for a **keyword-only** parameter named `store`. Without `*`, it's positional, isn't injected, and never gets filled. |

**Quick repro for #4** (no API key needed):

```js
const app = new StateGraph(S).addNode("set", () => ({ lang: "ur" }))
  .addEdge(START, "set").addEdge("set", END)
  .compile({ checkpointer: new MemorySaver() });

await app.invoke({}, { configurable: { thread_id: "chat-1" } });
console.log(await app.invoke({}, { configurable: { thread_id: "chat-2" } }));
// chat-2 starts from scratch — the preference didn't cross threads
```

```python
app = builder.compile(checkpointer=InMemorySaver())
app.invoke({}, {"configurable": {"thread_id": "chat-1"}})
print(app.invoke({}, {"configurable": {"thread_id": "chat-2"}}))
# chat-2 starts from scratch
```

**Ranking by danger.** #3 and #5 are loud — you get a stack trace and fix them in a minute.
#1, #2 and #4 are quiet: they pass tests, work in demos, and fail intermittently in
production. Build habits against the quiet ones. Two habits cover all three: **never mutate
in a reducer**, and **ask "does this cross threads?" before every channel you add.**
</details>

---

### Exercise 4 — StudyBuddy with real long-term memory ●●●○○

Build a graph that:

1. Loads the student's profile from the **store** (`("students", <id>)` → `"profile"`) at the
   start of every run.
2. Answers the question, adapting to `profile.level` (`beginner` / `advanced`) and
   `profile.language`.
3. Runs an `extract` node that spots durable new facts in the conversation ("I'm actually a
   university student now", "I prefer short answers") and **writes them back to the store**.
4. Keeps only the **last 6 messages** in state, using a capped reducer.
5. Exposes an output schema containing only `answer` — no internal profile, no messages.

Then run it across **two different `thread_id`s** and show that the profile carries over
while the conversation doesn't.

<details>
<summary>✅ Solution</summary>

**JavaScript**

```js
import { StateGraph, Annotation, InMemoryStore, MemorySaver, START, END } from "@langchain/langgraph";
import { HumanMessage } from "@langchain/core/messages";
import { addMessages } from "@langchain/langgraph";
import { ChatGroq } from "@langchain/groq";
import { z } from "zod";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0.3 });
const store = new InMemoryStore();

// ── schemas ──────────────────────────────────────────────────────────────
const InputSchema = Annotation.Root({
  messages: Annotation({ reducer: addMessages, default: () => [] }),
});
const OutputSchema = Annotation.Root({ answer: Annotation() });

const FullState = Annotation.Root({
  // capped window: keep the LAST 6 (never the first — see Exercise 1)
  messages: Annotation({
    reducer: (existing, incoming) => addMessages(existing, incoming).slice(-6),
    default: () => [],
  }),
  profile: Annotation({
    reducer: (existing, incoming) => ({ ...existing, ...incoming }),
    default: () => ({}),
  }),
  answer: Annotation(),
});

// ── 1. load from the store ───────────────────────────────────────────────
async function loadProfile(state, config) {
  const ns = ["students", config.configurable.student_id];
  const item = await config.store.get(ns, "profile");
  return { profile: item?.value ?? { level: "beginner", language: "en" } };
}

// ── 2. answer, adapted to the profile ────────────────────────────────────
async function answer(state) {
  const { level, language } = state.profile;
  const res = await model.invoke([
    {
      role: "system",
      content:
        `You are StudyBuddy. The student's level is "${level}". ` +
        `Reply in language code "${language}". ` +
        (level === "beginner"
          ? "Use one everyday analogy and avoid jargon."
          : "Be precise and technical; skip the basics."),
    },
    ...state.messages,
  ]);
  return { answer: res.content, messages: [res] };
}

// ── 3. extract durable facts and write them back ─────────────────────────
const extractor = model.withStructuredOutput(
  z.object({
    level: z.enum(["beginner", "advanced", "unknown"]),
    language: z.string().describe('ISO code, or "unknown"'),
    note: z.string().describe('one durable preference, or "none"'),
  })
);

async function extract(state, config) {
  const transcript = state.messages
    .map((m) => `${m.getType()}: ${m.content}`)
    .join("\n");

  const found = await extractor.invoke(
    "From this conversation, extract ONLY facts that will still be true next week. " +
      'Use "unknown"/"none" when nothing durable was said.\n\n' + transcript
  );

  // only write what actually changed — never blindly overwrite the store
  const patch = {};
  if (found.level !== "unknown" && found.level !== state.profile.level) patch.level = found.level;
  if (found.language !== "unknown" && found.language !== state.profile.language) patch.language = found.language;
  if (found.note !== "none") patch.notes = [...(state.profile.notes ?? []), found.note];

  if (Object.keys(patch).length === 0) return {};

  const ns = ["students", config.configurable.student_id];
  const merged = { ...state.profile, ...patch };
  await config.store.put(ns, "profile", merged);      // ← the write that crosses threads
  return { profile: patch };
}

// ── wire it up ───────────────────────────────────────────────────────────
const app = new StateGraph({
  stateSchema: FullState,
  input: InputSchema,
  output: OutputSchema,
})
  .addNode("loadProfile", loadProfile)
  .addNode("answer", answer)
  .addNode("extract", extract)
  .addEdge(START, "loadProfile")
  .addEdge("loadProfile", "answer")
  .addEdge("answer", "extract")
  .addEdge("extract", END)
  .compile({ store, checkpointer: new MemorySaver() });

// ── prove it ─────────────────────────────────────────────────────────────
const cfg = (thread) => ({ configurable: { student_id: "s1", thread_id: thread } });

console.log("── conversation 1 ──");
console.log(
  (await app.invoke(
    { messages: [new HumanMessage("Explain recursion. I'm a CS undergrad, keep it technical.")] },
    cfg("chat-1")
  )).answer
);
console.log("\nstored profile:", (await store.get(["students", "s1"], "profile")).value);

console.log("\n── conversation 2 (NEW thread) ──");
console.log(
  (await app.invoke(
    { messages: [new HumanMessage("Now explain memoization.")] },
    cfg("chat-2")
  )).answer
);
// → technical, because `level: "advanced"` came from the STORE, not the thread
```

**Python**

```python
import operator
from typing import Annotated, TypedDict, Literal
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.store.memory import InMemoryStore
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_groq import ChatGroq

model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.3)
store = InMemoryStore()

# ── schemas ──────────────────────────────────────────────────────────────
def last_6(existing: list, incoming: list) -> list:
    return add_messages(existing, incoming)[-6:]

def merge(existing: dict, incoming: dict) -> dict:
    return {**existing, **incoming}

class InputSchema(TypedDict):
    messages: Annotated[list, add_messages]

class OutputSchema(TypedDict):
    answer: str

class FullState(TypedDict):
    messages: Annotated[list, last_6]      # capped window: keep the LAST 6
    profile: Annotated[dict, merge]
    answer: str

# ── 1. load from the store ───────────────────────────────────────────────
def load_profile(state: FullState, config: RunnableConfig, *, store) -> dict:
    ns = ("students", config["configurable"]["student_id"])
    item = store.get(ns, "profile")
    return {"profile": item.value if item else {"level": "beginner", "language": "en"}}

# ── 2. answer, adapted to the profile ────────────────────────────────────
def answer(state: FullState) -> dict:
    level = state["profile"].get("level", "beginner")
    language = state["profile"].get("language", "en")
    system = (
        f'You are StudyBuddy. The student\'s level is "{level}". '
        f'Reply in language code "{language}". '
        + ("Use one everyday analogy and avoid jargon."
           if level == "beginner"
           else "Be precise and technical; skip the basics.")
    )
    res = model.invoke([{"role": "system", "content": system}, *state["messages"]])
    return {"answer": res.content, "messages": [res]}

# ── 3. extract durable facts and write them back ─────────────────────────
class Extracted(BaseModel):
    level: Literal["beginner", "advanced", "unknown"]
    language: str = Field(description='ISO code, or "unknown"')
    note: str = Field(description='one durable preference, or "none"')

extractor = model.with_structured_output(Extracted)

def extract(state: FullState, config: RunnableConfig, *, store) -> dict:
    transcript = "\n".join(f"{m.type}: {m.content}" for m in state["messages"])
    found = extractor.invoke(
        "From this conversation, extract ONLY facts that will still be true next week. "
        'Use "unknown"/"none" when nothing durable was said.\n\n' + transcript
    )

    profile = state["profile"]
    patch: dict = {}
    if found.level != "unknown" and found.level != profile.get("level"):
        patch["level"] = found.level
    if found.language != "unknown" and found.language != profile.get("language"):
        patch["language"] = found.language
    if found.note != "none":
        patch["notes"] = profile.get("notes", []) + [found.note]

    if not patch:
        return {}

    ns = ("students", config["configurable"]["student_id"])
    store.put(ns, "profile", {**profile, **patch})     # ← the write that crosses threads
    return {"profile": patch}

# ── wire it up ───────────────────────────────────────────────────────────
builder = StateGraph(FullState, input_schema=InputSchema, output_schema=OutputSchema)
builder.add_node("load_profile", load_profile)
builder.add_node("answer", answer)
builder.add_node("extract", extract)
builder.add_edge(START, "load_profile")
builder.add_edge("load_profile", "answer")
builder.add_edge("answer", "extract")
builder.add_edge("extract", END)
app = builder.compile(store=store, checkpointer=InMemorySaver())

# ── prove it ─────────────────────────────────────────────────────────────
def cfg(thread): return {"configurable": {"student_id": "s1", "thread_id": thread}}

print("── conversation 1 ──")
print(app.invoke(
    {"messages": [HumanMessage("Explain recursion. I'm a CS undergrad, keep it technical.")]},
    cfg("chat-1"),
)["answer"])
print("\nstored profile:", store.get(("students", "s1"), "profile").value)

print("\n── conversation 2 (NEW thread) ──")
print(app.invoke({"messages": [HumanMessage("Now explain memoization.")]}, cfg("chat-2"))["answer"])
# → technical, because level="advanced" came from the STORE, not the thread
```

**The four design decisions worth defending in a code review:**

1. **`load` and `extract` are separate nodes, at the two ends.** Loading first means every
   node downstream sees a populated profile. Extracting last means it sees the completed
   turn. It also makes both steps visible in the diagram and in stream events — you can watch
   memory being written.

2. **`extract` writes a *patch*, not the whole profile.** Blindly `put`-ing an extracted
   profile lets one bad extraction ("level: beginner") wipe a correct value. Comparing
   against what's stored and writing only genuine changes makes memory
   **monotonic-ish** — it degrades slowly rather than catastrophically.

3. **The capped reducer composes with `addMessages` rather than replacing it.**
   `addMessages(existing, incoming).slice(-6)` keeps upsert-by-ID and removal handling, then
   caps. Writing a bare `.slice` reducer would silently break message editing on Day 21.

4. **The output schema is `{ answer }` only.** The profile contains inferred facts about a
   real person; that isn't something to return in an HTTP response by default. Filtering at
   the graph boundary means you can't leak it by forgetting to filter at the API layer.

**One honest limitation:** this runs an extra model call on every single turn just to check
whether anything durable was said, and most turns have nothing. In production you'd run
`extract` on a cheaper model, sample it (every Nth turn), or move it off the request path
entirely into a background job. That's a Day 27 concern, but it's worth noticing now that
"memory" has a per-turn cost you're choosing to pay.
</details>

---

### Exercise 5 — Design review: fix a bad state schema ●●●●○

Here's a real-shaped state from a support agent that "works in dev and falls over in prod."
Find **every** problem and rewrite it. There are at least eight.

```js
const State = Annotation.Root({
  messages: Annotation(),
  db: Annotation(),
  openaiClient: Annotation(),
  apiKey: Annotation(),
  customerRecord: Annotation(),          // full record, ~300 KB
  knownIssues: Annotation({              // fan-out: 4 nodes write this
    reducer: (a, b) => { a.push(...b); return a; },
    default: [],
  }),
  attemptCount: Annotation(),            // 3 nodes each try to increment it
  topThreeSignals: Annotation({
    reducer: (a, b) => a.concat(b).slice(0, 3),
    default: () => [],
  }),
  customerPrefersEmail: Annotation(),    // a standing preference
  scratchpad: Annotation(),
  threadId: Annotation(),
});
```

<details>
<summary>✅ Solution</summary>

**The problems, in severity order:**

| # | Field | Problem | Severity |
|---|---|---|---|
| 1 | `apiKey` | A **secret written to the checkpoint database** on every superstep. | 🔴 security |
| 2 | `db`, `openaiClient` | Not serialisable. Works until you add a checkpointer, then crashes. | 🔴 crash |
| 3 | `knownIssues` reducer | **Mutates** `a` — corrupts previous checkpoints and other nodes' snapshots. | 🔴 silent corruption |
| 4 | `customerRecord` | 300 KB × supersteps × turns × users. | 🟠 throughput |
| 5 | `attemptCount` | No reducer, but **3 nodes increment it**. Two increments vanish. | 🟠 silent wrong |
| 6 | `topThreeSignals` | `slice(0, 3)` keeps the **first** 3 — non-associative, non-deterministic under fan-out. | 🟠 silent wrong |
| 7 | `messages` | No reducer → each turn **replaces** history. The conversation is always one message long. | 🟠 silent wrong |
| 8 | `customerPrefersEmail` | Thread-scoped, so it's forgotten in every new conversation. Belongs in the store. | 🟡 wrong behaviour |
| 9 | `threadId` | Circular — the checkpointer keys state *by* thread id. It comes from config. | 🟡 confusion |
| 10 | `knownIssues` default | `default: []` (not `() => []`) — one array shared across every run and user. | 🔴 cross-user leak |
| 11 | `scratchpad` | Fine to keep, but it will be returned to callers without an output schema. | 🟡 leak |

**The rewrite — JavaScript**

```js
import { Annotation, addMessages, StateGraph } from "@langchain/langgraph";

// ── what flows between nodes in ONE run ──────────────────────────────────
const FullState = Annotation.Root({
  // 7 ✅ the messages reducer, with a cap so it can't grow forever
  messages: Annotation({
    reducer: (existing, incoming) => addMessages(existing, incoming).slice(-20),
    default: () => [],
  }),

  // 4 ✅ a REFERENCE, not the record. Nodes fetch the fields they need.
  customerId: Annotation(),

  // 3, 10 ✅ non-mutating reducer + a default FACTORY
  knownIssues: Annotation({
    reducer: (existing, incoming) => existing.concat(incoming),
    default: () => [],
  }),

  // 5 ✅ nodes send a delta of 1; the reducer sums them
  attemptCount: Annotation({
    reducer: (existing, incoming) => existing + incoming,
    default: () => 0,
  }),

  // 6 ✅ keep the LAST 3 — associative, deterministic under fan-out
  topThreeSignals: Annotation({
    reducer: (existing, incoming) => existing.concat(incoming).slice(-3),
    default: () => [],
  }),

  // decisions made in this run — single writer, last-write-wins is correct
  escalated: Annotation(),
  draftReply: Annotation(),

  // 11 ✅ still here, but excluded from the output schema below
  scratchpad: Annotation(),
});

// 11 ✅ the boundary: only these fields leave the graph
const OutputSchema = Annotation.Root({
  draftReply: Annotation(),
  escalated: Annotation(),
});

const InputSchema = Annotation.Root({
  messages: Annotation({ reducer: addMessages, default: () => [] }),
  customerId: Annotation(),
});

const app = new StateGraph({ stateSchema: FullState, input: InputSchema, output: OutputSchema })
  /* ...nodes... */
  .compile({ store, checkpointer });

// ── 1, 2, 9 ✅ CONTEXT: per-call, never persisted ────────────────────────
await app.invoke(input, {
  configurable: {
    thread_id: "ticket-8891",          // 9 ✅ the key, supplied from outside
    customer_tier: "gold",             // looked up fresh each call — never stale
    db: pgPool,                        // 2 ✅ live handle
    openaiClient,                      // 2 ✅ live handle
  },
});
// 1 ✅ apiKey: nowhere near the graph. process.env, read by the client at construction.

// ── 8 ✅ STORE: crosses threads ──────────────────────────────────────────
await store.put(["customers", customerId], "prefs", { prefersEmail: true });
```

**The rewrite — Python**

```python
import operator
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages

def last_20_messages(existing: list, incoming: list) -> list:
    return add_messages(existing, incoming)[-20:]          # 7 ✅

def last_3(existing: list, incoming: list) -> list:
    return (existing + incoming)[-3:]                      # 6 ✅ LAST, not first

class InputSchema(TypedDict):
    messages: Annotated[list, add_messages]
    customer_id: str

class OutputSchema(TypedDict):                             # 11 ✅ the boundary
    draft_reply: str
    escalated: bool

class FullState(TypedDict):
    messages: Annotated[list, last_20_messages]
    customer_id: str                                       # 4 ✅ a reference, not 300 KB
    known_issues: Annotated[list[str], operator.add]       # 3, 10 ✅ pure + no shared default
    attempt_count: Annotated[int, operator.add]            # 5 ✅ nodes send deltas
    top_three_signals: Annotated[list[str], last_3]
    escalated: bool
    draft_reply: str
    scratchpad: str

builder = StateGraph(FullState, input_schema=InputSchema, output_schema=OutputSchema)
# ...nodes...
app = builder.compile(store=store, checkpointer=checkpointer)

# 1, 2, 9 ✅ CONTEXT
app.invoke(input, {"configurable": {
    "thread_id": "ticket-8891",
    "customer_tier": "gold",
    "db": pg_pool,
    "openai_client": client,
}})
# 1 ✅ api key: os.environ, read by the client at construction. Never in state.

# 8 ✅ STORE
store.put(("customers", customer_id), "prefs", {"prefers_email": True})
```

**The meta-lesson.** Nine of the eleven problems are invisible in a single-threaded
development test with no checkpointer. The schema is where you pay for or avoid an entire
class of production incidents, and it's ten lines of code — which makes **state schema
review** one of the highest-leverage code reviews in an agent codebase. Read every new
channel and ask the four questions: *Who writes it? Can two writers collide? Does it
serialise? Does it need to outlive this thread?*
</details>

---

## 9. Interview questions

### Basic

**Q1. What is a reducer in LangGraph?**

A function `(existing, incoming) => merged` attached to a state channel, deciding how a
node's write combines with the current value. The default is last-write-wins. Common ones:
concat for lists, `+` for counters, `addMessages` for conversation history.

---

**Q2. What's the default reducer and when is it wrong?**

Last-write-wins. It's wrong whenever a channel should accumulate (history, traces, collected
results) and whenever **more than one node writes it in the same superstep** — parallel
writes silently discard all but one, with no error.

---

**Q3. What does `addMessages` do beyond appending?**

Three more things: it **upserts by ID** (a message with an existing ID replaces it rather
than duplicating), it **auto-assigns UUIDs** to messages that lack one, and it **handles
`RemoveMessage`** — by ID to delete one, or with `REMOVE_ALL_MESSAGES` to clear the list.
The upsert behaviour is what makes editing conversation history possible.

---

**Q4. Where do you put a database connection?**

Context — `config.configurable`. It isn't serialisable, so putting it in state crashes the
moment you add a checkpointer, and it shouldn't be persisted anyway.

---

**Q5. How do you stop a graph from returning its internal scratchpad?**

Declare an output schema. `new StateGraph({ stateSchema, input, output })` in JS,
`StateGraph(S, input_schema=I, output_schema=O)` in Python. Nodes still see the full state;
only what leaves the graph is filtered.

---

### Intermediate

**Q6. Explain state vs memory vs context vs store vs checkpoint.**

The one they're actually asking, so answer it structurally:

- **State** — data flowing between nodes in one run, written through reducers, scoped to a
  thread, serialised on every superstep.
- **Context** (`config.configurable`) — per-invocation inputs and live handles: `user_id`,
  DB pools, API clients, `thread_id`. Never persisted.
- **Checkpoint** — a snapshot of state saved automatically after each superstep, keyed by
  `thread_id`. It's the mechanism, not a place you put things.
- **Store** — a key-value database scoped by a namespace you choose, so it crosses threads
  and users. Written explicitly with `.put()`.
- **Memory** — **not an API.** Short-term memory *is* state + a checkpointer; long-term memory
  *is* the store. The `Memory` classes from 0.x were removed.

Finish with the decision rule: not serialisable → context; needs to outlive the thread →
store; large → external storage with a reference in state; otherwise state.

---

**Q7. What properties must a reducer have, and why?**

Pure, total, non-mutating, associative.

- **Pure** — it may re-run during replay, so side effects would happen twice.
- **Total** — it must handle the default value as `existing`, since the first write always
  sees it.
- **Non-mutating** — the old value is still referenced by other nodes' snapshots and by the
  previous checkpoint; mutating it corrupts your time-travel history.
- **Associative** — parallel writes are folded pairwise in an order you don't control, so
  `(a⊕b)⊕c` must equal `a⊕(b⊕c)`.

Concat, add, max, min, set-union and object-merge are safe. Subtraction and "keep the first N"
are not.

---

**Q8. Why is "keep the last N" a safe reducer but "keep the first N" isn't?**

"Last N" is stable under regrouping — the last N of a concatenation are the same however you
parenthesise the folds. "First N" discards items early, so a different fold order discards
different items, and under fan-out the fold order is non-deterministic. General rule: a
reducer that discards from the *end being appended* is unsafe.

---

**Q9. A user says "it forgot my language preference when I started a new chat." What happened?**

The preference is in state, which is scoped to `thread_id`. A new chat means a new thread,
which starts from the channel defaults. It belongs in the **store**, namespaced by user id,
and loaded by a node at the start of each run.

The reason it survived testing is that you tested in one thread — this bug is invisible until
real users start second conversations.

---

**Q10. How do you keep conversation history from growing forever?**

A trimming node before the model, using `trimMessages` / `trim_messages` with
`strategy: "last"` and a token budget, emitting `RemoveMessage`s for everything it dropped —
`addMessages` understands removals, so deletion is just a state update. Alternatively cap
inside the reducer: `addMessages(existing, incoming).slice(-20)`.

Two details: set `startOn: "human"` so the window never begins with an orphaned tool result
(the provider rejects that with a 400), and prefer a **node** over a hidden reducer cap when
you want the trimming to be visible in your diagram and stream events.

---

**Q11. When would you use a Pydantic model as state instead of a TypedDict?**

When the graph is exposed to untrusted input and you want **runtime validation** — a
`TypedDict` annotation is erased at runtime, a Pydantic model raises `ValidationError` on bad
input. The costs: validation runs on every superstep, and the ergonomics shift (nodes receive
a model instance, so `state.n` not `state["n"]`, though `invoke` still returns a plain dict
and nodes still return dicts).

Rule of thumb: Pydantic at the edge, TypedDict inside. JS has no direct equivalent — you get
compile-time safety from `Annotation<T>()` in TypeScript and nothing at runtime.

---

### Advanced

**Q12. Your agent works in dev, but in production state grows until checkpointing dominates latency. Diagnose it.**

The cost model is `sizeof(state) × supersteps × turns × concurrent_users` — the entire state
is serialised after every superstep. So:

1. **Measure the state size**, not the message count. Serialise a real production state and
   look at the byte count per channel.
2. **Find the blob.** It's almost always retrieved documents, a full customer record, or raw
   tool output kept "for debugging". Replace it with a reference and fetch on demand.
3. **Check for unbounded channels.** `messages` with no cap, or a `trace` that appends every
   node on every turn forever.
4. **Check for accidental duplication** — a reducer doing the concat that the node already
   did, which grows the channel quadratically.
5. **Reduce superstep count** if the graph has fat sequential chains that could be one node
   or run in parallel.
6. Only then consider infrastructure: a faster checkpointer backend, or checkpointing less
   often for low-value runs.

The framing that lands: **state is a write-amplified data structure.** Design it like a
database row you're going to `UPDATE` thousands of times, not like a scratch object.

---

**Q13. Three nodes concurrently update a shared `counters` dict. Design the reducer.**

The naive `{...existing, ...incoming}` is wrong — two nodes incrementing the same key means
one increment is lost, because each node computed its new total from the same stale snapshot.

The fix is to make nodes send **deltas** and have the reducer add:

```js
counters: Annotation({
  reducer: (existing, incoming) => {
    const out = { ...existing };
    for (const [k, delta] of Object.entries(incoming)) out[k] = (out[k] ?? 0) + delta;
    return out;
  },
  default: () => ({}),
})
// node returns { counters: { errors: 1 } }  — a DELTA, never a total
```

```python
def add_counters(existing: dict, incoming: dict) -> dict:
    out = dict(existing)
    for k, delta in incoming.items():
        out[k] = out.get(k, 0) + delta
    return out
```

This is associative and commutative, so it's correct under any fold order. The general
principle — and the reason it's a good interview question — is that **it's the same problem
as a CRDT**: when concurrent writers can't see each other, you must send operations, not
resulting values.

---

**Q14. Design the memory architecture for a tutoring app: 50k students, months-long relationships, multi-turn sessions.**

Four layers, each with a different lifetime:

```
   1. WORKING (state, this run)
      messages capped to ~20 turns or a token budget, current topic, current problem

   2. SESSION (checkpointer, keyed by thread_id)
      the full transcript of one tutoring session — resumable, replayable, time-travellable
      TTL: keep hot for ~30 days, then archive

   3. PROFILE (store, namespaced ("students", id))
      level, language, goals, learning-style notes, mastered/struggling topics
      written by an extraction step, MERGED not overwritten

   4. CONTENT (vector store + relational DB)
      curriculum, past submissions, grades. Never in state — nodes query it and keep
      only the retrieved snippets for the current turn.
```

The decisions worth defending:

- **Session summaries flow 2→3.** At session end, a summarisation job writes durable
  conclusions ("struggles with recursion base cases") into the profile. Don't do this
  per-turn — it's expensive and noisy.
- **The profile is merged, never replaced.** A single bad extraction shouldn't erase months
  of accumulated understanding. Write patches, and keep a `notes` list that appends rather
  than overwrites.
- **State holds pointers.** `currentProblemId`, not the problem text. At 50k students the
  difference is gigabytes of checkpoint I/O.
- **Extraction is off the request path.** A background job after the session, not a node on
  every turn — otherwise you pay an extra model call per message for information that changes
  once a week.
- **The store is namespaced per student**, which also gives you a clean GDPR deletion story:
  drop the namespace, drop the threads.

---

**Q15. When would you use multiple state schemas, beyond hiding fields?**

Four cases:

1. **Security boundary** — the output schema keeps retrieved documents, raw prompts, and
   inferred user facts out of HTTP responses by construction rather than by remembering to
   filter.
2. **API stability** — the input schema is your public contract. Internal state can be
   refactored freely without breaking callers.
3. **Subgraphs** (Day 19) — a subgraph has its own state; input/output schemas define exactly
   what crosses the boundary, so a subgraph is genuinely encapsulated rather than sharing one
   global bag of fields.
4. **Private node-to-node channels** — a field that two adjacent nodes use to pass working
   data, declared in the internal schema only, so it never appears in input or output and
   nobody outside those two nodes depends on it.

The theme: schemas turn your state from one shared global into something with **interfaces**.
That matters at exactly the point a graph gets big enough for more than one person to work
on it.

---

**Q16. How do you test state and reducer logic?**

In three layers, cheapest first:

1. **Reducers alone.** Pure two-argument functions. Assert totality (handles the default),
   non-mutation (the input is unchanged afterwards), and associativity
   (`f(f(a,b),c) === f(a,f(b,c))`). No graph, no model, no network — this catches the entire
   class of concurrency bugs that are otherwise unreproducible.
2. **Nodes alone.** `(state) => patch`. Hand-build a state object, call the node, assert on
   the patch. Assert it returns *only* the keys it should.
3. **The graph with a fake model** and a real `InMemoryStore`, asserting on cross-thread
   behaviour: run thread A, then thread B, and check that profile facts carried over while
   conversation history did not.

Add one schema test that asserts `invoke` returns exactly the output-schema keys — that's
your regression test against accidentally leaking internal fields when someone adds a channel
six months from now.

---

## 10. Recap

### What you learned

- ✅ A reducer is `(existing, incoming) => merged` — and it must be **pure, total,
  non-mutating and associative**
- ✅ Parallel writes are folded **pairwise in an order you don't control** — hence associativity
- ✅ "Keep the last N" is safe; "keep the first N" and subtraction are not
- ✅ `addMessages` **appends, upserts by ID, auto-assigns IDs, and handles removals**
- ✅ Trimming is a **node** that emits `RemoveMessage`s — visible in your diagram
- ✅ `startOn: "human"` prevents the orphaned-tool-result 400
- ✅ A graph can have **three schemas**: input, internal, output — the output one is a
  security boundary
- ✅ **Context** (`config.configurable`) holds handles and secrets and is **never persisted**
- ✅ The **store** is memory that crosses threads; state is memory that doesn't
- ✅ **"Memory" is not an API** — short-term = state + checkpointer, long-term = store
- ✅ State is written **every superstep**: `size × supersteps × turns × users`
- ✅ State holds **pointers and decisions, not payloads**

### The decision rule, one more time

```
   live object?          → context
   > ~100 KB?            → external storage, keep a reference in state
   belongs to the USER?  → store
   needed by nodes now?  → state (pick the reducer deliberately)
   none of the above?    → delete it
```

### Tomorrow

**[Day 19 — Control Flow](day-19-control-flow.md)**: your routers so far have been `if/else`
returning a node name. Tomorrow you get the real tools — `Command` (update state *and* route
in one return), `Send` (fan out to N copies of a node with different inputs — genuine
map-reduce), and subgraphs (a graph as a node, with its own state and its own schemas). You'll
build a research graph that splits a question into sub-questions, researches all of them in
parallel, and merges the findings.

### Quick self-check

1. Two nodes in one superstep each return `{ total: state.total + 1 }` for a `total` channel
   with an `add` reducer, starting from 0. What's the final value, and what did the author
   intend?
2. Where does `thread_id` live, and why can't it be in state?
3. You need "the user's timezone." State, context, or store?

<details>
<summary>Answers</summary>

1. **`2`** if `state.total` was 0 for both (each sent `0 + 1 = 1`, and the reducer added
   them) — which is accidentally right. But the author wrote it wrong: with an `add` reducer
   nodes must send **deltas**, not totals. Start from 5 and both nodes send `6`, so the
   reducer produces `17`. The correct node body is `return { total: 1 }`. This is the
   send-operations-not-values rule from Q13, and it's the most common subtle reducer bug
   after double-appending.

2. In **context** — `config.configurable.thread_id`. It can't be in state because it's the
   *key the checkpointer stores state under*; the state can't contain its own address. It
   arrives from outside on every invocation, which is also what lets one graph serve many
   concurrent conversations.

3. **Context**, in almost every case. The timezone is authoritative in your user table or the
   browser, so read it fresh per request; a cached copy in the store goes stale when someone
   travels. Put it in the store only if the *agent itself* inferred it from conversation and
   nothing else knows it. The general rule: **facts you can look up cheaply → context; facts
   only this system knows → store.**
</details>

---

<div align="center">

**[← Day 17 — LangGraph Basics](day-17-langgraph-basics.md)** · **[Week 3 index](README.md)** · **[Day 19 — Control Flow →](day-19-control-flow.md)**

</div>
