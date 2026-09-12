# Day 20 — Persistence & Checkpointing: Save, Resume, Rewind

> ⏱ **Time:** ~2.5 hours · 🎯 **Prereqs:** [Day 19](day-19-control-flow.md) · 🧩 **Difficulty:** ●●●○○

**Today you learn:** the three lines that make everything you've built survive a restart.
Checkpointers, `thread_id` as the unit of a conversation, `getState` and the full state
history — and **time travel**: rewind to any past checkpoint, edit it, and re-run from there.
Everything on Day 21 depends on today.

---

## 1. The problem

Everything you've built so far has the same fatal property:

```
   $ node studybuddy.js
   > What's photosynthesis?
   StudyBuddy: Plants turn sunlight into food...
   > Can you make that simpler?
   StudyBuddy: Sure! Think of it like...

   ^C                                          ← or a deploy, or a crash, or a lambda timeout

   $ node studybuddy.js
   > Can you make that simpler?
   StudyBuddy: Make what simpler?              ← everything is gone
```

The conversation lived in a JavaScript variable in a process that no longer exists.

That's the obvious problem. Here are four you haven't hit yet, and they're worse:

```
   1. "Why did the agent refund that customer?"
      → you have the final state. You have no idea what it looked like at step 4.

   2. "It went wrong at the third step. Can you re-run from there with a fix?"
      → you can re-run the whole thing from scratch, paying for every step again,
        and it's non-deterministic so it might not even reproduce.

   3. "Two users are chatting at once."
      → one global `messages` array. User A sees user B's conversation.

   4. "Pause before the database write and ask me."
      → pause WHERE? The state is on a call stack. There's nowhere to put it.
```

All five are the same missing capability: **the state is never written down.**

### The real-life version

You're playing a hard video game.

```
   ┌──────────────────────────────────────────────────────────────────┐
   │  NO SAVE SYSTEM                                                   │
   │  Power cut at the final boss → start from the beginning.          │
   │  Made a bad choice 3 hours ago → too bad.                         │
   │  Want to see what your character had at level 5 → impossible.     │
   │  Your sibling wants to play → they overwrite your progress.       │
   ├──────────────────────────────────────────────────────────────────┤
   │  WITH SAVE FILES                                                  │
   │  Autosave after every room.                                       │
   │  Load any old save and play forward differently.                  │
   │  Separate save SLOTS, one per player.                             │
   │  Pause the game and walk away — the state is on disk.             │
   └──────────────────────────────────────────────────────────────────┘
```

A checkpointer is an autosave. A `thread_id` is a save slot. And LangGraph autosaves
**after every superstep**, automatically, once you pass one argument to `compile()`.

---

## 2. Mental model

### Three concepts, one diagram

```
   THREAD  "chat-8891"      ← one conversation. The save SLOT.
      │
      ├─ checkpoint #-1   { }                                    ← input received
      ├─ checkpoint #0    { messages: [q1] }          next: agent
      ├─ checkpoint #1    { messages: [q1, a1] }      next: tools
      ├─ checkpoint #2    { messages: [q1, a1, t1] }  next: agent
      └─ checkpoint #3    { messages: [q1,a1,t1,a2] } next: ()   ← done
                                                       ▲
                                    "next" is empty = nothing left to run
```

| Concept | Analogy | In code |
|---|---|---|
| **Checkpointer** | the save system | `compile({ checkpointer })` |
| **Thread** | a save slot | `configurable: { thread_id }` |
| **Checkpoint** | one save file | written after every superstep |
| **`getState`** | look at the current save | `app.getState(config)` |
| **`getStateHistory`** | list every save | `app.getStateHistory(config)` |
| **Time travel** | load an old save | `app.invoke(null, oldCheckpointConfig)` |
| **Fork** | load an old save, change something, play on | `updateState` then invoke |

### `thread_id` is the entire multi-user story

```
   thread_id: "chat-A"          thread_id: "chat-B"
   ┌──────────────────┐         ┌──────────────────┐
   │ messages: [...]  │         │ messages: [...]  │
   │ n: 2             │         │ n: 1             │
   └──────────────────┘         └──────────────────┘
        Ayesha's chat                Bilal's chat

   ONE compiled graph serves both. Completely isolated.
```

Verified: same graph, same process, two `thread_id`s —

```
   thread t1, run 1:  { log: ['bump->1','noted'],                        n: 1 }
   thread t1, run 2:  { log: ['bump->1','noted','bump->2','noted'],      n: 2 }   ← continued
   thread t2, run 1:  { log: ['bump->1','noted'],                        n: 1 }   ← fresh
```

That's it. There's no session object, no user context to thread through, no memory manager.
**One config key.**

### The mental shift

```
   BEFORE                              AFTER
   ──────                              ─────
   "the conversation is in a           "the conversation is rows in a database;
    variable while my function          my function loads it, appends, and saves"
    is running"

   the run owns the state              the THREAD owns the state
                                       a run is just "advance this thread"
```

Once you see it that way, resuming isn't a feature — it's the normal case. Starting fresh is
just a thread with no checkpoints yet.

---

## 3. First principles

### 3.1 What a checkpoint contains

```
   A CHECKPOINT
   ├─ values          every channel's value at this moment
   ├─ next            which node(s) run NEXT — ()/[] means finished
   ├─ config          { thread_id, checkpoint_ns, checkpoint_id }   ← its address
   ├─ parent_config   the checkpoint this one came from
   ├─ metadata        { source, step, parents }
   ├─ created_at      timestamp
   └─ tasks           pending work (this is where interrupts live — Day 21)
```

The two fields that make everything else possible are **`values`** and **`next`**. Together
they're a complete description of "where we are": what we know, and what we were about to do.
Give those to a fresh process and it can carry on as if nothing happened.

### 3.2 Checkpoints are written after *every* superstep

```
   invoke({n: 0}) on a 2-node graph
     ├─ checkpoint  step -1   source: "input"    ← before anything runs
     ├─ run bump
     ├─ checkpoint  step 0                        ← after superstep 1
     ├─ run note
     ├─ checkpoint  step 1                        ← after superstep 2
     └─ checkpoint  step 2    next: ()            ← final
```

Verified: two runs of a two-node graph produce **8 checkpoints**. That's ~4 per run — one per
superstep plus the input marker.

This is the cost model from [Day 18](day-18-state-and-reducers.md), made concrete:

```
   writes = supersteps × turns × concurrent_users
   bytes  = sizeof(state) × writes
```

Nothing is free. But it's what buys resumption, history, time travel and interrupts — and for
almost every application the trade is obviously worth it. The mistake isn't checkpointing;
it's putting a 2 MB document in the thing you checkpoint.

### 3.3 History is newest-first, and includes the "about to run" states

Verified output for two runs of `START → bump → note → END`:

```
   ckpt          next            n     step
   ───────────   ─────────────   ───   ────
   …3334         ()              2      6     ← newest
   …3331         ('note',)       2      5
   …332f         ('bump',)       1      4
   …332a         ('__start__',)  1      3     ← run 2's input
   …32f9         ()              1      2
   …32f7         ('note',)       1      1
   …32ed         ('bump',)       0      0
   …32d2         ('__start__',)  0     -1     ← run 1's input, oldest
```

Read `next` as **"if you resume from here, this is what runs."** That's the field you filter
on to pick a time-travel target: *"give me the checkpoint where we were about to run the tool
node."*

> 💡 Checkpoint IDs are time-ordered UUIDs, so they all share a long prefix within a run.
> Slice at least 13 characters when printing them, or every ID will look identical.

### 3.4 Replay vs fork — the two kinds of time travel

```
   REPLAY                                FORK
   ──────                                ────
   invoke(null, oldCheckpointConfig)     updateState(oldConfig, patch)
                                         → returns a NEW config
                                         invoke(null, newConfig)

   "run forward from this point,         "change something at this point,
    unchanged"                            THEN run forward"

   for: retry after a transient error,   for: fixing a bad decision, injecting
        re-running with a fixed tool           a correction, human edits
```

Verified — replay:

```
   target checkpoint values: { log: ['bump->1'], n: 1 }   next: ('note',)
   invoke(None, target.config)
   → { log: ['bump->1', 'noted'], n: 1 }        ← `note` ran again from that point
```

Verified — fork:

```
   updateState(target.config, { log: ['INJECTED'] })   → a new checkpoint config
   invoke(None, forkedConfig)
   → { log: ['bump->1', 'INJECTED', 'noted'], n: 1 }
```

Note what happened to `INJECTED`: it went **through the channel's reducer**, so it was
appended, not substituted. `updateState` is a state write like any other — same rules, same
reducers.

### 3.5 `updateState` and `asNode`

By default `updateState` writes a checkpoint that looks like it came from "outside", so `next`
is unchanged. Pass a node name and it looks like **that node produced it**, which changes what
runs next:

```
   updateState(config, { n: 99 }, as_node="bump")
   → state: { n: 99, ... }   next: ('note',)
                                   ▲
                      because `note` is what follows `bump`
```

Verified in both languages. This is the mechanism behind Day 21's "edit the agent's tool call
and continue": you overwrite what the agent node produced, then let the graph proceed as if
the agent had said that all along.

### 3.6 `null` / `None` as input means "resume, don't start"

```
   invoke({ messages: [...] }, config)   →  ADD this input, then run
   invoke(null, config)                  →  run from where the checkpoint left off
```

That single distinction covers resuming an interrupted run, replaying, and continuing after a
fork. You'll use it constantly tomorrow.

---

## 4. Code — JavaScript

> **Install:** `npm i @langchain/langgraph @langchain/langgraph-checkpoint-sqlite`

### 4.1 Three lines and it survives

```js
import { StateGraph, Annotation, MemorySaver, START, END } from "@langchain/langgraph";

const State = Annotation.Root({
  log: Annotation({ reducer: (a, b) => a.concat(b), default: () => [] }),
  n: Annotation({ reducer: (a, b) => b ?? a, default: () => 0 }),
});

const app = new StateGraph(State)
  .addNode("bump", (s) => ({ log: [`bump->${s.n + 1}`], n: s.n + 1 }))
  .addNode("note", () => ({ log: ["noted"] }))
  .addEdge(START, "bump").addEdge("bump", "note").addEdge("note", END)
  .compile({ checkpointer: new MemorySaver() });     // ← 1. the checkpointer

const config = { configurable: { thread_id: "t1" } };  // ← 2. the thread

console.log(await app.invoke({ n: 0 }, config));       // ← 3. pass it every time
// { log: [ 'bump->1', 'noted' ], n: 1 }

console.log(await app.invoke({}, config));             // same thread → CONTINUES
// { log: [ 'bump->1', 'noted', 'bump->2', 'noted' ], n: 2 }

console.log(await app.invoke({}, { configurable: { thread_id: "t2" } }));
// { log: [ 'bump->1', 'noted' ], n: 1 }               // different thread → FRESH
```

The second `invoke` passed `{}` — no input at all — and the graph picked up with `n: 1`
already in state. **That's persistence.** No session store, no memory class, no manual
loading.

> ⚠️ `MemorySaver` is a dictionary in RAM. It survives across `invoke` calls in one process
> and nothing else. It's for development and tests. §4.8 swaps in a real one.

### 4.2 One graph, many users

```js
// The SAME compiled app serves every conversation.
async function handleMessage(userId, chatId, text) {
  return await app.invoke(
    { messages: [new HumanMessage(text)] },
    { configurable: { thread_id: `${userId}:${chatId}` } }
  );
}
```

```
   thread_id = "u42:chat-1"     ──►  Ayesha's first chat
   thread_id = "u42:chat-2"     ──►  Ayesha's second chat
   thread_id = "u77:chat-1"     ──►  Bilal's chat
```

> 🔒 **`thread_id` is an authorisation boundary.** If a user can send you a `thread_id`, they
> can read any conversation whose id they can guess. Always **derive** it server-side from the
> authenticated user, or verify ownership before using a client-supplied one. This is a real
> vulnerability class in LangGraph apps and it's trivially avoidable.

### 4.3 `getState` — look at the save file

```js
const snapshot = await app.getState(config);

console.log(snapshot.values);
// { log: [ 'bump->1', 'noted', 'bump->2', 'noted' ], n: 2 }

console.log(snapshot.next);
// []                          ← nothing left to run; the graph finished

console.log(snapshot.config.configurable.checkpoint_id);
// '1f1a0bc5-3334-…'           ← this checkpoint's address

console.log(snapshot.metadata);
// { source: 'loop', step: 6, parents: {}, thread_id: 't1' }
```

`next` is the field to reach for when debugging. `[]` means finished. `["tools"]` means the
run stopped with the tools node pending — either it's mid-flight, or something interrupted it.

### 4.4 `getStateHistory` — the audit log you didn't write

```js
const history = [];
for await (const snap of app.getStateHistory(config)) history.push(snap);

console.log(`${history.length} checkpoints`);   // 8, after two runs

for (const h of history) {
  console.log(
    h.config.configurable.checkpoint_id.slice(0, 13),
    "next=", h.next,
    "n=", h.values.n,
    "step=", h.metadata?.step
  );
}
// 1f1a0bc5-3334 next= []            n= 2 step= 6      ← newest first
// 1f1a0bc5-3331 next= [ 'note' ]    n= 2 step= 5
// 1f1a0bc5-332f next= [ 'bump' ]    n= 1 step= 4
// 1f1a0bc5-332a next= [ '__start__' ] n= 1 step= 3
// 1f1a0bc5-32f9 next= []            n= 1 step= 2
// 1f1a0bc5-32f7 next= [ 'note' ]    n= 1 step= 1
// 1f1a0bc5-32ed next= [ 'bump' ]    n= 0 step= 0
// 1f1a0bc5-32d2 next= [ '__start__' ] n= 0 step= -1   ← oldest
```

You now have a per-step answer to "what did the agent know, and what was it about to do?" for
every run. When someone asks "why did it refund that customer?", this is the answer — not a
guess reconstructed from logs.

### 4.5 Time travel — replay from an old checkpoint

```js
// find the checkpoint where we were about to run `note`, on the first pass
const target = history.filter((h) => h.next?.[0] === "note").at(-1);

console.log(target.values);
// { log: [ 'bump->1' ], n: 1 }        ← the state as it was, mid-run

// resume from THERE — note the `null` input
console.log(await app.invoke(null, target.config));
// { log: [ 'bump->1', 'noted' ], n: 1 }
```

Passing `target.config` — which carries a `checkpoint_id` — means "start from this exact
save". Passing `null` as input means "don't add anything new, just continue."

```
   ┌────────────────────────────────────────────────────────────┐
   │  This is how you retry a failed step without paying for     │
   │  every step before it — and without hoping a stochastic     │
   │  model reproduces the same path.                            │
   └────────────────────────────────────────────────────────────┘
```

### 4.6 Fork — change the past, then run forward

```js
// write a patch INTO an old checkpoint; get back a config pointing at the fork
const forked = await app.updateState(target.config, { log: ["INJECTED"] });

console.log(await app.invoke(null, forked));
// { log: [ 'bump->1', 'INJECTED', 'noted' ], n: 1 }
//                     ^^^^^^^^^^ inserted at that point in history
```

Two things to notice:

- **The patch went through the reducer.** `log` appends, so `INJECTED` was added, not
  substituted. `updateState` is an ordinary state write.
- **The original history is untouched.** You created a branch. The old timeline still exists
  and is still replayable.

### 4.7 `updateState` with a node name

```js
const forked = await app.updateState(config, { n: 99 }, "bump");
//                                                       ↑ "pretend `bump` wrote this"

const s = await app.getState(forked);
console.log(s.values, s.next);
// { log: [...], n: 99 }   [ 'note' ]
//                          ↑ because `note` is what follows `bump`
```

Without the node name, `next` is unchanged. With it, the graph resumes as if that node had
just produced your value. **This is the mechanism behind "edit the agent's plan and
continue"** — tomorrow's lesson.

### 4.8 Real persistence — surviving an actual restart

`MemorySaver` dies with the process. Swap in SQLite and nothing else changes:

```js
import { SqliteSaver } from "@langchain/langgraph-checkpoint-sqlite";

// ── "process 1" ─────────────────────────────────────────────────────────
{
  const checkpointer = SqliteSaver.fromConnString("studybuddy.sqlite");
  const app = buildGraph().compile({ checkpointer });
  console.log(await app.invoke({ n: 0 }, { configurable: { thread_id: "p1" } }));
  // { log: [ 'bump->1', 'noted' ], n: 1 }
}

// ── "process 2" — a brand-new checkpointer from the same file ───────────
{
  const checkpointer = SqliteSaver.fromConnString("studybuddy.sqlite");
  const app = buildGraph().compile({ checkpointer });
  console.log(await app.invoke({}, { configurable: { thread_id: "p1" } }));
  // { log: [ 'bump->1', 'noted', 'bump->2', 'noted' ], n: 2 }
  //   ↑ it remembered, across a completely fresh checkpointer instance
}
```

Verified — a real file on disk, and the second block picks up exactly where the first left
off. **This is the whole feature.** Your API handler builds the graph once at startup and
passes a `thread_id` per request; the conversation lives in the database, not the process.

### 4.9 Choosing a production checkpointer

| Checkpointer | Use for | Notes |
|---|---|---|
| `MemorySaver` | tests, notebooks, demos | RAM only; dies with the process |
| `SqliteSaver` | single-node apps, desktop apps, local dev | one file; no concurrent writers across machines |
| Postgres | **the default production choice** | real concurrency, backups, you already run one |
| Redis | very high throughput, short-lived threads | set a TTL; not durable by default |
| MongoDB | you're already on Mongo | fine; nothing special |

> 📦 Each backend is a separate package (`@langchain/langgraph-checkpoint-sqlite`,
> `-postgres`, and so on) — install the one you need. **The node code never changes.** Swapping
> from SQLite to Postgres is a one-line change at `compile()`, which is the point of the
> abstraction. Postgres and Redis savers also need a one-time `setup()` call to create their
> tables; check the package's README for the exact call at your version.

### 4.10 Thread hygiene

Checkpoints accumulate forever unless you manage them:

```js
// ── delete a conversation ───────────────────────────────────────────────
await checkpointer.deleteThread("u42:chat-1");   // available on most savers

// ── cap history growth: trim state, not checkpoints ─────────────────────
// A 200-turn thread with 4 checkpoints/turn is 800 rows.
// The row COUNT is usually fine; the row SIZE is what hurts.
// Keep `messages` trimmed (Day 18) and the checkpoints stay small.
```

Three policies worth deciding before launch, not after:

```
   RETENTION   how long do threads live? (30 days is a common default)
   DELETION    GDPR: "delete my data" must delete the thread AND the store namespace
   SIZE        alert on the p99 checkpoint size — it's your early warning for a blob in state
```

---

## 5. Code — Python

> **Install:** `pip install langgraph langgraph-checkpoint-sqlite`

### 5.1 Three lines and it survives

```python
import operator
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver

class State(TypedDict):
    log: Annotated[list[str], operator.add]
    n: int

builder = StateGraph(State)
builder.add_node("bump", lambda s: {"log": [f'bump->{s.get("n", 0) + 1}'], "n": s.get("n", 0) + 1})
builder.add_node("note", lambda s: {"log": ["noted"]})
builder.add_edge(START, "bump")
builder.add_edge("bump", "note")
builder.add_edge("note", END)

app = builder.compile(checkpointer=InMemorySaver())          # ← 1. the checkpointer

config = {"configurable": {"thread_id": "t1"}}                # ← 2. the thread

print(app.invoke({"n": 0}, config))                           # ← 3. pass it every time
# {'log': ['bump->1', 'noted'], 'n': 1}

print(app.invoke({}, config))                                 # same thread → CONTINUES
# {'log': ['bump->1', 'noted', 'bump->2', 'noted'], 'n': 2}

print(app.invoke({}, {"configurable": {"thread_id": "t2"}}))
# {'log': ['bump->1', 'noted'], 'n': 1}                       # different thread → FRESH
```

> 📦 **Naming:** Python calls it `InMemorySaver`; JavaScript calls it `MemorySaver`. Python
> also still exports `MemorySaver` as an alias, so both names appear in tutorials. Same class.

### 5.2 One graph, many users

```python
def handle_message(user_id: str, chat_id: str, text: str):
    return app.invoke(
        {"messages": [HumanMessage(text)]},
        {"configurable": {"thread_id": f"{user_id}:{chat_id}"}},
    )
```

> 🔒 Derive `thread_id` server-side from the authenticated user, or verify ownership. A
> client-supplied `thread_id` is a direct read of someone else's conversation.

### 5.3 `get_state` — look at the save file

```python
snapshot = app.get_state(config)

print(snapshot.values)
# {'log': ['bump->1', 'noted', 'bump->2', 'noted'], 'n': 2}

print(snapshot.next)
# ()                                  ← empty tuple: nothing left to run

print(snapshot.config["configurable"]["checkpoint_id"])
# '1f1a0bc2-…'

print(snapshot.metadata)
# {'source': 'loop', 'step': 6, 'parents': {}}
```

> 📦 `next` is a **tuple** in Python and an **array** in JS. Check emptiness, not identity.
> Python's `metadata` omits `thread_id`; JS includes it. Don't rely on it in either.

### 5.4 `get_state_history` — the audit log you didn't write

```python
history = list(app.get_state_history(config))
print(f"{len(history)} checkpoints")     # 8, after two runs

for h in history:
    print(h.config["configurable"]["checkpoint_id"][:13],
          "next=", h.next, "n=", h.values.get("n"), "step=", h.metadata.get("step"))
# 1f1a0bc2-…  next= ()               n= 2  step= 6     ← newest first
# 1f1a0bc2-…  next= ('note',)        n= 2  step= 5
# 1f1a0bc2-…  next= ('bump',)        n= 1  step= 4
# 1f1a0bc2-…  next= ('__start__',)   n= 1  step= 3
# 1f1a0bc2-…  next= ()               n= 1  step= 2
# 1f1a0bc2-…  next= ('note',)        n= 1  step= 1
# 1f1a0bc2-…  next= ('bump',)        n= 0  step= 0
# 1f1a0bc2-…  next= ('__start__',)   n= None step= -1  ← oldest
```

`get_state_history` is a generator — wrap it in `list()` or iterate it. It yields
**newest-first**, so "the earliest point where X was about to happen" is the **last** match,
not the first.

### 5.5 Time travel — replay from an old checkpoint

```python
# the checkpoint where we were about to run `note`, on the first pass
target = [h for h in history if h.next == ("note",)][-1]

print(target.values)
# {'log': ['bump->1'], 'n': 1}

print(app.invoke(None, target.config))       # ← None input = "resume, don't add"
# {'log': ['bump->1', 'noted'], 'n': 1}
```

### 5.6 Fork — change the past, then run forward

```python
forked = app.update_state(target.config, {"log": ["INJECTED"]})
print(app.invoke(None, forked))
# {'log': ['bump->1', 'INJECTED', 'noted'], 'n': 1}
```

The patch went through `operator.add`, so it appended. `update_state` obeys your reducers
exactly like a node's return value does.

### 5.7 `update_state` with `as_node`

```python
forked = app.update_state(config, {"n": 99}, as_node="bump")

s = app.get_state(forked)
print(s.values, s.next)
# {'log': [...], 'n': 99}   ('note',)
#                            ↑ because `note` follows `bump`
```

### 5.8 Real persistence — surviving an actual restart

```python
from langgraph.checkpoint.sqlite import SqliteSaver

config = {"configurable": {"thread_id": "persist-1"}}

# ── "process 1" ─────────────────────────────────────────────────────────
with SqliteSaver.from_conn_string("studybuddy.sqlite") as checkpointer:
    app = builder.compile(checkpointer=checkpointer)
    print(app.invoke({"n": 0}, config))
    # {'log': ['bump->1'], 'n': 1}

# ── "process 2" — a brand-new saver from the same file ──────────────────
with SqliteSaver.from_conn_string("studybuddy.sqlite") as checkpointer:
    app = builder.compile(checkpointer=checkpointer)
    print(app.invoke({}, config))
    # {'log': ['bump->1', 'bump->2'], 'n': 2}          ← it remembered
    print(len(list(app.get_state_history(config))))    # 6
```

Verified: a real 20 KB file on disk, and the second block continues from the first.

> ⚠️ **`from_conn_string` is a context manager in Python.** Use `with`, or the connection
> leaks. In a long-running server you want the saver alive for the process lifetime — enter
> the context at startup (or use the async `AsyncSqliteSaver`), not per request. JS's
> `SqliteSaver.fromConnString(path)` returns the saver directly, no context manager.

### 5.9 Choosing a production checkpointer

```python
from langgraph.checkpoint.memory import InMemorySaver         # tests
from langgraph.checkpoint.sqlite import SqliteSaver           # pip install langgraph-checkpoint-sqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver  # async version
# from langgraph.checkpoint.postgres import PostgresSaver     # pip install langgraph-checkpoint-postgres
```

Verified: `SqliteSaver` and `AsyncSqliteSaver` come from `langgraph-checkpoint-sqlite`;
`PostgresSaver` is **not** in the base install — it needs `langgraph-checkpoint-postgres`.
A bare `from langgraph.checkpoint.postgres import PostgresSaver` raises `ModuleNotFoundError`,
which is exactly what you'll hit when copying a tutorial.

Postgres is the default production answer: real concurrency, backups, and you're probably
already running one. Remember its one-time `setup()` call to create the tables.

### 5.10 Thread hygiene

```python
# delete a conversation entirely
checkpointer.delete_thread("u42:chat-1")
```

Decide three policies before launch: **retention** (how long threads live), **deletion** (a
GDPR request must clear the thread *and* the store namespace from Day 18), and **size
monitoring** (alert on p99 checkpoint size — it's your early warning that someone put a blob
in state).

### 5.11 The full JS ↔ Python translation for today

| Concept | JavaScript | Python |
|---|---|---|
| in-memory saver | `new MemorySaver()` | `InMemorySaver()` |
| attach it | `.compile({ checkpointer })` | `.compile(checkpointer=cp)` |
| thread | `{ configurable: { thread_id: "t1" } }` | `{"configurable": {"thread_id": "t1"}}` |
| current state | `await app.getState(config)` | `app.get_state(config)` |
| history | `for await (const s of app.getStateHistory(config))` | `list(app.get_state_history(config))` |
| `next` type | array — `[]` when done | tuple — `()` when done |
| resume input | `await app.invoke(null, config)` | `app.invoke(None, config)` |
| edit state | `await app.updateState(config, patch)` | `app.update_state(config, patch)` |
| edit as a node | `app.updateState(config, patch, "bump")` | `app.update_state(config, patch, as_node="bump")` |
| sqlite saver | `SqliteSaver.fromConnString("db.sqlite")` | `with SqliteSaver.from_conn_string("db.sqlite") as cp:` |
| sqlite package | `@langchain/langgraph-checkpoint-sqlite` | `langgraph-checkpoint-sqlite` |
| delete a thread | `await checkpointer.deleteThread(id)` | `checkpointer.delete_thread(id)` |
| no checkpointer | `GraphValueError: No checkpointer set` | `ValueError: No checkpointer set` |

---

## 6. Under the hood

### 6.1 The invoke loop, with checkpointing

```
   invoke(input, { configurable: { thread_id, checkpoint_id? } })
     │
     ├─ 1. LOAD    checkpoint_id given?  → load THAT checkpoint
     │             otherwise             → load the LATEST for this thread
     │             none exists           → start from channel defaults
     │
     ├─ 2. APPLY   input given?  → merge it through the reducers, save a checkpoint
     │             input is null → skip; use the loaded state as-is
     │
     ├─ 3. LOOP    ┌───────────────────────────────────────────────┐
     │             │ run the active nodes                           │
     │             │ apply their patches through the reducers       │
     │             │ ►► SAVE A CHECKPOINT ◄◄                        │
     │             │ route to the next active set                   │
     │             └───────────────────────────────────────────────┘
     │             until nothing is active
     │
     └─ 4. RETURN  the final state
```

Step 1 is where resumption happens, and it explains everything: passing only a `thread_id`
means "continue the latest"; adding a `checkpoint_id` means "continue from that specific
point". There's no separate resume API because resuming *is* the normal path.

### 6.2 Replay is not re-running

A subtle but important point: replaying from a checkpoint does **not** re-execute the nodes
that produced it. It loads their *results* and continues from `next`.

```
   checkpoint at step 4:  values = { log: ['bump->1'], n: 1 }   next = ('note',)

   invoke(None, thatConfig)
     → loads those values           ← `bump` does NOT run again
     → runs `note`                  ← only what was pending
```

Which is why replay is cheap: you pay for the steps *after* the checkpoint, not the ones
before. That's the entire value proposition for debugging an agent that failed on step 9 of
12.

### 6.3 What `updateState` writes

```
   updateState(config, patch, asNode?)
     │
     ├─ loads the checkpoint `config` points at
     ├─ applies `patch` THROUGH THE REDUCERS      ← not a raw overwrite
     ├─ writes a NEW checkpoint whose parent is that one
     ├─ if asNode: records it as if that node produced it
     │             → `next` becomes that node's successors
     └─ returns a config pointing at the new checkpoint
```

Two consequences people trip on:

- **It appends on appending channels.** To *replace* a list you need a reducer that
  understands replacement — the way `addMessages` understands `RemoveMessage`. There's no
  generic "overwrite this channel" escape hatch.
- **It forks rather than rewrites.** The old checkpoint still exists and is still the parent.
  You never lose history; you branch it.

### 6.4 Thread isolation is a database key, nothing more

```
   checkpoints table (conceptually)
   ┌────────────┬─────────────────┬──────────┬─────────────────────┐
   │ thread_id  │ checkpoint_id   │ parent   │ values (serialised) │
   ├────────────┼─────────────────┼──────────┼─────────────────────┤
   │ u42:chat-1 │ 1f1a…32d2       │ null     │ {...}               │
   │ u42:chat-1 │ 1f1a…32ed       │ …32d2    │ {...}               │
   │ u77:chat-1 │ 1f1a…4401       │ null     │ {...}               │
   └────────────┴─────────────────┴──────────┴─────────────────────┘
```

Isolation is a `WHERE thread_id = ?`. That's why the security note in §4.2 matters so much:
there is no additional ownership check anywhere in the framework. If your handler trusts a
`thread_id` from the request body, you've built an IDOR vulnerability.

### 6.5 The real cost, and what to do about it

```
   per turn:  supersteps × (serialise(state) + one DB write)
```

Four levers, in the order you should pull them:

```
   1. SHRINK STATE      the biggest lever by far. Pointers, not payloads. (Day 18)
   2. TRIM MESSAGES     an unbounded `messages` channel grows every checkpoint
   3. FEWER SUPERSTEPS  merge trivially sequential nodes; parallelise independent ones
   4. FASTER BACKEND    Postgres with a connection pool; Redis if threads are short-lived
```

Note that #4 is *last*. Teams usually reach for it first and get a 20% win, when shrinking
state would have given them 50×.

---

## 7. Common mistakes

### ❌ 1. Forgetting `thread_id`

```js
❌ await app.invoke(input);
   // Error: ... missing a required "thread_id" field in its "configurable" property
✅ await app.invoke(input, { configurable: { thread_id: "chat-1" } });
```

Python's message is different but means the same thing: *"Checkpointer requires one or more of
the following 'configurable' keys: thread_id, checkpoint_ns, checkpoint_id."* At least this
one fails loudly.

### ❌ 2. Reusing one `thread_id` for everyone

```js
❌ const config = { configurable: { thread_id: "main" } };   // module-level constant
✅ const config = { configurable: { thread_id: `${userId}:${chatId}` } };
```

Every user shares one conversation. It works perfectly with one user in development, and is a
data breach in production.

### ❌ 3. Trusting a client-supplied `thread_id`

```js
❌ app.invoke(input, { configurable: { thread_id: req.body.threadId } });
✅ const threadId = `${req.user.id}:${await assertOwned(req.user.id, req.body.chatId)}`;
```

There is no ownership check inside LangGraph — isolation is a database key. Guessing or
enumerating ids reads other people's conversations.

### ❌ 4. Shipping `MemorySaver` to production

```js
❌ .compile({ checkpointer: new MemorySaver() })
✅ .compile({ checkpointer: SqliteSaver.fromConnString(process.env.DB_PATH) })
```

It works in staging (one process, no restarts) and silently loses every conversation on each
deploy. Worse on serverless, where each request may be a new process — so it appears to work
sometimes.

### ❌ 5. Expecting `getState` to work without a checkpointer

```js
❌ buildGraph().compile().getState(config)
   // GraphValueError: No checkpointer set          (Python: ValueError: No checkpointer set)
```

State inspection, history and time travel are *features of the checkpointer*, not of the
graph.

### ❌ 6. Assuming history is oldest-first

```js
❌ const first = history[0];                      // that's the NEWEST
✅ const first = history.at(-1);
✅ const target = history.filter((h) => h.next?.[0] === "tools").at(-1);   // earliest match
```

Both languages yield newest-first. Getting this backwards means your "replay from the start"
replays from the end and appears to do nothing.

### ❌ 7. Expecting `updateState` to replace a list

```js
❌ await app.updateState(config, { messages: [onlyThisOne] });   // APPENDS it
✅ await app.updateState(config, { messages: [new RemoveMessage({ id: REMOVE_ALL_MESSAGES }),
                                              onlyThisOne] });
```

`updateState` goes through the reducers. On an appending channel it appends. Use the
reducer's own removal protocol (Day 18) to clear.

### ❌ 8. Blobs in state

```js
❌ documents: Annotation()      // 40 retrieved chunks, checkpointed every superstep
✅ documentIds: Annotation()    // fetch in the node
```

Day 18's rule, now with teeth: whatever you put in state is written to a database ~4 times per
turn, per user. This is the number-one cause of "checkpointing is slow."

### ❌ 9. Never deleting anything

```
❌ threads accumulate forever; the checkpoints table becomes your largest table
✅ a retention policy, a deleteThread path, and an alert on p99 checkpoint size
```

Also a compliance problem: "delete my data" must clear the thread **and** the store namespace.

### ❌ 10. Leaking the SQLite connection in Python

```python
❌ cp = SqliteSaver.from_conn_string("db.sqlite")     # a context manager, not a saver
✅ with SqliteSaver.from_conn_string("db.sqlite") as cp:
       app = builder.compile(checkpointer=cp)
```

In a server, enter the context once at startup rather than per request — and use
`AsyncSqliteSaver` if your handlers are async. JS's `fromConnString` returns the saver
directly, so this trips people moving Python-first code to Node and vice versa.

### ❌ 11. Using time travel as an undo button in production

```
❌ "the agent did something bad → silently fork and re-run so nobody notices"
✅ time travel is for DEBUGGING and for HUMAN-DIRECTED correction (Day 21)
```

Forking a live conversation behind a user's back gives you two timelines and no record of
which one they saw. If you correct a run, record that you did.

---

## 8. Exercises

### Exercise 1 — See every save file ●○○○○

Build a 3-node graph with no model calls. Run it **twice** on the same thread, then print the
full history with `next`, `step` and the key state values. Answer:

1. How many checkpoints for two runs?
2. What's the `step` of the very first one, and what does that number mean?
3. Which checkpoint would you resume from to re-run only the last node?

<details>
<summary>✅ Solution</summary>

**JavaScript**

```js
import { StateGraph, Annotation, MemorySaver, START, END } from "@langchain/langgraph";

const S = Annotation.Root({
  log: Annotation({ reducer: (a, b) => a.concat(b), default: () => [] }),
  n: Annotation({ reducer: (a, b) => b ?? a, default: () => 0 }),
});

const app = new StateGraph(S)
  .addNode("one",   (s) => ({ log: ["one"],   n: s.n + 1 }))
  .addNode("two",   (s) => ({ log: ["two"]   }))
  .addNode("three", (s) => ({ log: ["three"] }))
  .addEdge(START, "one").addEdge("one", "two").addEdge("two", "three").addEdge("three", END)
  .compile({ checkpointer: new MemorySaver() });

const config = { configurable: { thread_id: "demo" } };
await app.invoke({ n: 0 }, config);
await app.invoke({}, config);

const history = [];
for await (const h of app.getStateHistory(config)) history.push(h);

console.log(`${history.length} checkpoints (newest first)\n`);
for (const h of history) {
  console.log(
    String(h.metadata?.step).padStart(3),
    (h.next.length ? h.next.join(",") : "(done)").padEnd(12),
    "n=" + h.values.n,
    JSON.stringify(h.values.log)
  );
}
```

**Python**

```python
import operator
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver

class S(TypedDict):
    log: Annotated[list[str], operator.add]
    n: int

b = StateGraph(S)
b.add_node("one",   lambda s: {"log": ["one"],   "n": s.get("n", 0) + 1})
b.add_node("two",   lambda s: {"log": ["two"]})
b.add_node("three", lambda s: {"log": ["three"]})
b.add_edge(START, "one"); b.add_edge("one", "two")
b.add_edge("two", "three"); b.add_edge("three", END)
app = b.compile(checkpointer=InMemorySaver())

config = {"configurable": {"thread_id": "demo"}}
app.invoke({"n": 0}, config)
app.invoke({}, config)

history = list(app.get_state_history(config))
print(f"{len(history)} checkpoints (newest first)\n")
for h in history:
    nxt = ",".join(h.next) if h.next else "(done)"
    print(f'{h.metadata["step"]:>3}  {nxt:<12} n={h.values.get("n")}  {h.values.get("log")}')
```

**Output**

```
10 checkpoints (newest first)

  8  (done)       n=2  ['one','two','three','one','two','three']
  7  three        n=2  ['one','two','three','one','two']
  6  two          n=2  ['one','two','three','one']
  5  one          n=1  ['one','two','three']
  4  __start__    n=1  ['one','two','three']
  3  (done)       n=1  ['one','two','three']
  2  three        n=1  ['one','two']
  1  two          n=1  ['one']
  0  one          n=0  []
 -1  __start__    n=0  []
```

**Answers**

1. **10** — five per run: one `__start__` marker for the input, then one after each of the
   three supersteps, plus the final. Rule of thumb: **supersteps + 2 per run.**

2. **`-1`**, and it's the **input** checkpoint — the state after your input was merged but
   before any node ran. Negative because it precedes superstep 0. It's the checkpoint you'd
   resume from to re-run the entire graph with the same input.

3. **The one with `next = ["three"]`** — `step 7` for the second run, `step 2` for the first.
   Resuming from it loads `['one','two',...]` and runs only `three`. Note there are **two**
   such checkpoints, one per run; since history is newest-first, `filter(...)[0]` gives you
   the most recent and `.at(-1)` / `[-1]` gives you the earliest. Choosing the wrong one is
   the most common time-travel mistake.
</details>

---

### Exercise 2 — Survive a real restart ●●○○○

Prove persistence is real, not a trick of the process:

1. Build a counter graph with `SqliteSaver` pointed at a file.
2. In **script A**, run it three times on thread `"restart-test"`.
3. In a **separate script B** (a genuinely new process), run it twice more on the same
   thread and confirm the counter continues from 3 to 5.
4. Print the file size and the checkpoint count.
5. Then run script B with a *different* `thread_id` and confirm it starts at 1.

<details>
<summary>✅ Solution</summary>

**JavaScript — `a.mjs`**

```js
import { StateGraph, Annotation, START, END } from "@langchain/langgraph";
import { SqliteSaver } from "@langchain/langgraph-checkpoint-sqlite";

export const S = Annotation.Root({
  count: Annotation({ reducer: (a, b) => a + b, default: () => 0 }),
  history: Annotation({ reducer: (a, b) => a.concat(b), default: () => [] }),
});

export function buildApp() {
  const checkpointer = SqliteSaver.fromConnString("counter.sqlite");
  return new StateGraph(S)
    .addNode("increment", (s) => ({ count: 1, history: [`run at count ${s.count} -> ${s.count + 1}`] }))
    .addEdge(START, "increment").addEdge("increment", END)
    .compile({ checkpointer });
}

const app = buildApp();
const config = { configurable: { thread_id: "restart-test" } };
for (let i = 0; i < 3; i++) console.log("A:", (await app.invoke({}, config)).count);
// A: 1
// A: 2
// A: 3
```

**JavaScript — `b.mjs`** (run with `node b.mjs` after `node a.mjs`)

```js
import fs from "node:fs";
import { buildApp } from "./a.mjs";

const app = buildApp();              // BRAND NEW checkpointer, new process
const config = { configurable: { thread_id: "restart-test" } };

console.log("B:", (await app.invoke({}, config)).count);   // 4
const final = await app.invoke({}, config);
console.log("B:", final.count);                            // 5
console.log("history:", final.history);

let n = 0;
for await (const _ of app.getStateHistory(config)) n++;
console.log(`${n} checkpoints · ${fs.statSync("counter.sqlite").size} bytes on disk`);

const fresh = await app.invoke({}, { configurable: { thread_id: "brand-new" } });
console.log("different thread:", fresh.count);             // 1
```

**Python — `a.py`**

```python
import operator
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

class S(TypedDict):
    count: Annotated[int, operator.add]
    history: Annotated[list[str], operator.add]

def build_builder():
    b = StateGraph(S)
    b.add_node("increment", lambda s: {
        "count": 1,
        "history": [f'run at count {s.get("count", 0)} -> {s.get("count", 0) + 1}'],
    })
    b.add_edge(START, "increment")
    b.add_edge("increment", END)
    return b

if __name__ == "__main__":
    config = {"configurable": {"thread_id": "restart-test"}}
    with SqliteSaver.from_conn_string("counter.sqlite") as cp:
        app = build_builder().compile(checkpointer=cp)
        for _ in range(3):
            print("A:", app.invoke({}, config)["count"])
    # A: 1
    # A: 2
    # A: 3
```

**Python — `b.py`**

```python
import os
from a import build_builder
from langgraph.checkpoint.sqlite import SqliteSaver

config = {"configurable": {"thread_id": "restart-test"}}
with SqliteSaver.from_conn_string("counter.sqlite") as cp:      # NEW saver, NEW process
    app = build_builder().compile(checkpointer=cp)

    print("B:", app.invoke({}, config)["count"])                # 4
    final = app.invoke({}, config)
    print("B:", final["count"])                                 # 5
    print("history:", final["history"])

    print(f'{len(list(app.get_state_history(config)))} checkpoints · '
          f'{os.path.getsize("counter.sqlite")} bytes on disk')

    print("different thread:", app.invoke({}, {"configurable": {"thread_id": "brand-new"}})["count"])
    # 1
```

**Output**

```
A: 1
A: 2
A: 3
──────── separate process ────────
B: 4
B: 5
history: ['run at count 0 -> 1', 'run at count 1 -> 2', 'run at count 2 -> 3',
          'run at count 3 -> 4', 'run at count 4 -> 5']
15 checkpoints · 20480 bytes on disk
different thread: 1
```

**What this actually proves.** Script B never saw script A's variables, its `MemorySaver`, or
its process. It built a fresh checkpointer from the same file and continued at 4. The
`history` channel contains entries written by a process that had already exited.

**The one line that matters for your architecture:**

```js
const app = buildApp();   // ← build ONCE, at server startup
// then per request:
await app.invoke(input, { configurable: { thread_id: threadForThisUser } });
```

The graph is stateless; the thread carries the state. That's what makes it safe to run behind
a load balancer with N replicas — any replica can serve any turn of any conversation, because
none of them hold anything.
</details>

---

### Exercise 3 — Break it six ways ●●○○○

Predict, then run.

1. Compile with a checkpointer, then `invoke` with no config at all.
2. Use one hard-coded `thread_id` and simulate two users.
3. Call `getState` on a graph compiled without a checkpointer.
4. Take `history[0]` believing it's the first checkpoint, and replay from it.
5. `updateState(config, { messages: [oneMessage] })` on a `MessagesAnnotation` graph,
   expecting it to replace the history.
6. Put a 1 MB string in state, run 20 turns, and measure the SQLite file.

<details>
<summary>✅ Solution</summary>

| # | Symptom | Why |
|---|---|---|
| 1 | **JS:** `Failed to put checkpoint. The passed RunnableConfig is missing a required "thread_id" field in its "configurable" property.`<br>**Python:** `ValueError: Checkpointer requires one or more of the following 'configurable' keys: thread_id, checkpoint_ns, checkpoint_id` | The checkpointer has no key to save under. One of the few loud failures today — be grateful. |
| 2 | Both "users" share one conversation. User B sees user A's messages and the counter is the sum of both. No error. | `thread_id` **is** the isolation. There is no other tenancy mechanism. Perfect in single-user testing; a data breach in production. |
| 3 | **JS:** `GraphValueError: No checkpointer set`. **Python:** `ValueError: No checkpointer set`. | State inspection is a feature of the checkpointer, not the graph. |
| 4 | Appears to do nothing — you "replay" from the newest checkpoint, which has `next = []`, so no nodes run and you get the final state back unchanged. | History is **newest-first** in both languages. Use `.at(-1)` / `[-1]` for the oldest, and filter on `next` rather than guessing at indices. |
| 5 | The message is **appended**, not substituted. History grows by one. | `updateState` applies the patch through the channel's reducer, and `addMessages` appends. To clear, send `RemoveMessage(REMOVE_ALL_MESSAGES)` first (Day 18). |
| 6 | The file grows by roughly `1 MB × supersteps × turns` — tens to hundreds of MB for one conversation — and each turn gets measurably slower. | The full state is serialised after every superstep. This is Day 18's cost model, now visible in bytes on disk. |

**Measuring #6 yourself** — the most useful five minutes in this exercise:

```js
const big = "x".repeat(1_000_000);
for (let i = 0; i < 20; i++) await app.invoke({ blob: big }, config);
console.log(fs.statSync("bloat.sqlite").size / 1e6, "MB");
```

```python
big = "x" * 1_000_000
for _ in range(20):
    app.invoke({"blob": big}, config)
print(os.path.getsize("bloat.sqlite") / 1e6, "MB")
```

Then delete the blob channel, keep an id instead, and run it again. The difference is the
argument for Day 18's decision tree, in a form nobody argues with.

**Ranking.** #1 and #3 are loud. #2, #4, #5 and #6 are quiet — #2 is a security incident and
#6 is a slow-burning outage. The habit that prevents both: **derive `thread_id` server-side**
and **review every channel for size** before it ships.
</details>

---

### Exercise 4 — A time-travel debugger for StudyBuddy ●●●○○

Build a CLI that operates on a persisted thread:

```
   > history              list every checkpoint: step, next, a summary of state
   > show <step>          print full state at that step
   > replay <step>        re-run forward from that checkpoint, print the result
   > fork <step> <text>   inject <text> into the log at that step, then run forward
   > threads              list known threads and their turn counts
```

Requirements: SQLite so it survives restarts; handle a bad step number; make `fork` show that
the original timeline still exists afterwards.

<details>
<summary>✅ Solution</summary>

**JavaScript**

```js
import readline from "node:readline/promises";
import { StateGraph, Annotation, START, END } from "@langchain/langgraph";
import { SqliteSaver } from "@langchain/langgraph-checkpoint-sqlite";

const S = Annotation.Root({
  topic: Annotation({ reducer: (a, b) => b ?? a, default: () => "" }),
  log: Annotation({ reducer: (a, b) => a.concat(b), default: () => [] }),
  step: Annotation({ reducer: (a, b) => a + b, default: () => 0 }),
});

const checkpointer = SqliteSaver.fromConnString("debugger.sqlite");

const app = new StateGraph(S)
  .addNode("research", (s) => ({ log: [`researched "${s.topic}"`], step: 1 }))
  .addNode("outline",  (s) => ({ log: [`outlined from ${s.log.length} note(s)`], step: 1 }))
  .addNode("write",    (s) => ({ log: [`wrote using: ${s.log.join(" | ")}`], step: 1 }))
  .addEdge(START, "research").addEdge("research", "outline")
  .addEdge("outline", "write").addEdge("write", END)
  .compile({ checkpointer });

const THREAD = process.argv[2] ?? "debug-1";
const config = { configurable: { thread_id: THREAD } };

async function getHistory() {
  const out = [];
  for await (const h of app.getStateHistory(config)) out.push(h);
  return out.reverse();                    // ← oldest-first, for a human-friendly CLI
}

// find by step number, with a clear error rather than a crash
async function checkpointAtStep(step) {
  const h = (await getHistory()).find((x) => x.metadata?.step === step);
  if (!h) throw new Error(`no checkpoint at step ${step}. Try "history".`);
  return h;
}

const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
console.log(`thread: ${THREAD}\ncommands: history | show N | replay N | fork N <text> | run <topic> | threads | quit\n`);

for (;;) {
  const line = (await rl.question("> ")).trim();
  const [cmd, ...rest] = line.split(" ");
  try {
    if (cmd === "quit") break;

    else if (cmd === "run") {
      const out = await app.invoke({ topic: rest.join(" ") || "recursion" }, config);
      console.log(`done · ${out.step} step(s) · ${out.log.length} log entries`);
    }

    else if (cmd === "history") {
      for (const h of await getHistory()) {
        const next = h.next.length ? h.next.join(",") : "(done)";
        console.log(
          `  step ${String(h.metadata?.step).padStart(3)}  ${next.padEnd(10)}  ` +
          `${h.values.log.length} entries  ${h.config.configurable.checkpoint_id.slice(0, 13)}`
        );
      }
    }

    else if (cmd === "show") {
      const h = await checkpointAtStep(Number(rest[0]));
      console.log(JSON.stringify(h.values, null, 2));
      console.log("next:", h.next);
    }

    else if (cmd === "replay") {
      const h = await checkpointAtStep(Number(rest[0]));
      console.log(`replaying from step ${rest[0]} (next: ${h.next})...`);
      const out = await app.invoke(null, h.config);      // ← null = don't add input
      console.log(out.log);
    }

    else if (cmd === "fork") {
      const step = Number(rest[0]);
      const text = rest.slice(1).join(" ");
      const h = await checkpointAtStep(step);
      const before = (await getHistory()).length;

      const forked = await app.updateState(h.config, { log: [`[INJECTED] ${text}`] });
      const out = await app.invoke(null, forked);
      console.log("forked result:", out.log);

      // prove the original is intact
      const original = await checkpointAtStep(step);
      console.log(`\noriginal step ${step} still has ${original.values.log.length} entries ` +
                  `(unchanged) · history grew ${before} -> ${(await getHistory()).length}`);
    }

    else if (cmd === "threads") {
      console.log(`  ${THREAD}: ${(await getHistory()).length} checkpoints`);
      console.log("  (a full listing needs a checkpointer-specific query — see the note below)");
    }

    else console.log("unknown command");
  } catch (err) {
    console.log("error:", err.message);
  }
}
rl.close();
```

**Python**

```python
import operator, sys
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

class S(TypedDict):
    topic: str
    log: Annotated[list[str], operator.add]
    step: Annotated[int, operator.add]

def build():
    b = StateGraph(S)
    b.add_node("research", lambda s: {"log": [f'researched "{s.get("topic","")}"'], "step": 1})
    b.add_node("outline",  lambda s: {"log": [f'outlined from {len(s["log"])} note(s)'], "step": 1})
    b.add_node("write",    lambda s: {"log": [f'wrote using: {" | ".join(s["log"])}'], "step": 1})
    b.add_edge(START, "research"); b.add_edge("research", "outline")
    b.add_edge("outline", "write"); b.add_edge("write", END)
    return b

THREAD = sys.argv[1] if len(sys.argv) > 1 else "debug-1"
config = {"configurable": {"thread_id": THREAD}}

with SqliteSaver.from_conn_string("debugger.sqlite") as cp:
    app = build().compile(checkpointer=cp)

    def history():
        return list(reversed(list(app.get_state_history(config))))   # oldest-first

    def checkpoint_at(step: int):
        for h in history():
            if h.metadata.get("step") == step:
                return h
        raise ValueError(f'no checkpoint at step {step}. Try "history".')

    print(f'thread: {THREAD}')
    print("commands: history | show N | replay N | fork N <text> | run <topic> | threads | quit\n")

    while True:
        line = input("> ").strip()
        if not line:
            continue
        cmd, *rest = line.split(" ")
        try:
            if cmd == "quit":
                break

            elif cmd == "run":
                out = app.invoke({"topic": " ".join(rest) or "recursion"}, config)
                print(f'done · {out["step"]} step(s) · {len(out["log"])} log entries')

            elif cmd == "history":
                for h in history():
                    nxt = ",".join(h.next) if h.next else "(done)"
                    print(f'  step {h.metadata.get("step"):>3}  {nxt:<10}  '
                          f'{len(h.values.get("log", []))} entries  '
                          f'{h.config["configurable"]["checkpoint_id"][:13]}')

            elif cmd == "show":
                h = checkpoint_at(int(rest[0]))
                print(h.values)
                print("next:", h.next)

            elif cmd == "replay":
                h = checkpoint_at(int(rest[0]))
                print(f'replaying from step {rest[0]} (next: {h.next})...')
                print(app.invoke(None, h.config)["log"])          # ← None = don't add input

            elif cmd == "fork":
                step, text = int(rest[0]), " ".join(rest[1:])
                h = checkpoint_at(step)
                before = len(history())

                forked = app.update_state(h.config, {"log": [f"[INJECTED] {text}"]})
                print("forked result:", app.invoke(None, forked)["log"])

                original = checkpoint_at(step)
                print(f'\noriginal step {step} still has {len(original.values["log"])} entries '
                      f'(unchanged) · history grew {before} -> {len(history())}')

            elif cmd == "threads":
                print(f'  {THREAD}: {len(history())} checkpoints')

            else:
                print("unknown command")
        except Exception as e:
            print("error:", e)
```

**A session**

```
> run photosynthesis
done · 3 step(s) · 3 log entries

> history
  step  -1  __start__   0 entries  1f1a0c11-8a2f
  step   0  research    0 entries  1f1a0c11-8a44
  step   1  outline     1 entries  1f1a0c11-8a51
  step   2  write       2 entries  1f1a0c11-8a5e
  step   3  (done)      3 entries  1f1a0c11-8a6b

> show 1
{ "topic": "photosynthesis", "log": [ "researched \"photosynthesis\"" ], "step": 1 }
next: [ "outline" ]

> replay 1
replaying from step 1 (next: outline)...
[ 'researched "photosynthesis"', 'outlined from 1 note(s)', 'wrote using: ...' ]

> fork 1 the textbook contradicts this
forked result: [ 'researched "photosynthesis"',
                 '[INJECTED] the textbook contradicts this',
                 'outlined from 2 note(s)',
                 'wrote using: ...' ]

original step 1 still has 1 entries (unchanged) · history grew 5 -> 9
```

**Four things this demonstrates:**

1. **`replay` re-ran only `outline` and `write`.** `research` didn't run again — its result
   was loaded from the checkpoint. That's why replay is cheap and why it's the right tool for
   "step 9 of 12 failed."
2. **`fork` changed what downstream nodes saw.** `outline` reported "2 note(s)" instead of 1,
   because the injected entry was really in state when it ran. This isn't a cosmetic edit —
   the graph genuinely re-executed with different inputs.
3. **The original timeline survives.** Step 1 still has one entry; history grew rather than
   being rewritten. `updateState` branches, never overwrites.
4. **`getStateHistory` is reversed for display.** Both APIs are newest-first; a human-facing
   tool almost always wants oldest-first. Doing the reverse once, in one helper, avoids the
   off-by-everything bugs from §7 #6.

**On `threads`:** LangGraph's graph API is deliberately scoped to *one* thread — there's no
`listThreads()` on the compiled graph, because "which threads exist" is an application
question, not a graph one. In a real app you keep your own `conversations` table (id, user_id,
title, updated_at) and use the `thread_id` as the join key. Some checkpointer backends expose
a `list()` for their own storage, but querying the checkpoint table directly to enumerate user
conversations couples your app to a schema you don't own.
</details>

---

### Exercise 5 — Design review: production persistence ●●●●○

A team is launching a support agent. Here's their setup. Find every problem and propose the
fix.

```js
const app = graph.compile({ checkpointer: new MemorySaver() });

app.post("/chat", async (req, res) => {
  const result = await app.invoke(
    { messages: [new HumanMessage(req.body.text)] },
    { configurable: { thread_id: req.body.threadId } }
  );
  res.json(result);
});
```

State schema:
```js
Annotation.Root({
  messages: Annotation({ reducer: addMessages, default: () => [] }),
  retrievedDocs: Annotation(),         // 15 chunks, ~40 KB
  customerRecord: Annotation(),        // ~200 KB
  internalNotes: Annotation(),
  dbPool: Annotation(),
})
```

They run 4 replicas behind a load balancer. Threads are never deleted. Average conversation:
30 turns, 6-node graph.

<details>
<summary>✅ Solution</summary>

**Nine problems, in severity order.**

| # | Problem | Impact | Fix |
|---|---|---|---|
| 1 | `thread_id` comes straight from the request body | 🔴 **IDOR** — anyone can read any conversation by guessing an id | Derive it server-side: `` `${req.user.id}:${chatId}` ``, after verifying the user owns `chatId` |
| 2 | `MemorySaver` **with 4 replicas** | 🔴 Broken, not just non-durable: each replica has its own memory, so turn 2 hits a different replica and the conversation restarts. Symptom: "it randomly forgets" | Postgres checkpointer |
| 3 | `dbPool` in state | 🔴 Crashes on the first checkpoint write — not serialisable | Move to `config.configurable` (Day 18) |
| 4 | `customerRecord` (200 KB) in state | 🟠 200 KB × 6 supersteps × 30 turns = **36 MB written per conversation** | Keep `customerId`; fetch fields in the node |
| 5 | `retrievedDocs` (40 KB) in state | 🟠 Another 7 MB per conversation, and it's re-checkpointed long after it's needed | Keep doc ids; or clear the channel after the generate node |
| 6 | `messages` never trimmed | 🟠 Grows every turn; by turn 30 each checkpoint carries the whole conversation | Cap in the reducer or add a trim node (Day 18) |
| 7 | `res.json(result)` returns the whole state | 🟠 Ships `internalNotes`, retrieved documents, and possibly another tenant's content to the browser | Output schema — `{ reply }` only |
| 8 | Threads never deleted | 🟡 The checkpoints table becomes the largest table; also blocks GDPR deletion | Retention policy + a `deleteThread` path that also clears the store namespace |
| 9 | No `thread_id` validation | 🟡 A malformed or absent id produces a raw framework error to the client | Validate, and return a clean 400 |

**The fixed version**

```js
// ── build ONCE at startup ────────────────────────────────────────────────
const checkpointer = PostgresSaver.fromConnString(process.env.DATABASE_URL);
await checkpointer.setup();                       // one-time table creation

const FullState = Annotation.Root({
  messages: Annotation({
    reducer: (a, b) => addMessages(a, b).slice(-20),      // 6 ✅ capped
    default: () => [],
  }),
  customerId: Annotation(),                                // 4 ✅ a reference
  retrievedDocIds: Annotation({ reducer: (a, b) => b ?? a, default: () => [] }),  // 5 ✅
  internalNotes: Annotation(),
  reply: Annotation(),
});

const OutputSchema = Annotation.Root({ reply: Annotation() });   // 7 ✅ the boundary

const app = new StateGraph({ stateSchema: FullState, output: OutputSchema })
  /* ...nodes... */
  .compile({ checkpointer });                                    // 2 ✅ shared across replicas

// ── per request ─────────────────────────────────────────────────────────
server.post("/chat", requireAuth, async (req, res) => {
  const { chatId, text } = req.body;

  if (typeof chatId !== "string" || !/^[\w-]{1,64}$/.test(chatId)) {   // 9 ✅
    return res.status(400).json({ error: "invalid chatId" });
  }
  if (!(await userOwnsChat(req.user.id, chatId))) {                     // 1 ✅
    return res.status(403).json({ error: "forbidden" });
  }

  const result = await app.invoke(
    { messages: [new HumanMessage(text)], customerId: req.user.customerId },
    {
      configurable: {
        thread_id: `${req.user.id}:${chatId}`,    // 1 ✅ derived, never trusted
        db: pgPool,                                // 3 ✅ context, not state
        tier: req.user.tier,
      },
    }
  );

  res.json(result);                                // 7 ✅ output schema already filtered it
});

// ── retention ───────────────────────────────────────────────────────────
// nightly: delete threads untouched for 30 days
// on account deletion: deleteThread(...) for every chat AND clear the store namespace  // 8 ✅
```

**The same fix in Python**

```python
import operator, os, re
from typing import Annotated, TypedDict
from fastapi import FastAPI, Depends, HTTPException
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.checkpoint.postgres import PostgresSaver

def last_20(existing, incoming):
    return add_messages(existing, incoming)[-20:]                 # 6 ✅ capped

class InputSchema(TypedDict):
    messages: Annotated[list, add_messages]
    customer_id: str

class OutputSchema(TypedDict):                                    # 7 ✅ the boundary
    reply: str

class FullState(TypedDict):
    messages: Annotated[list, last_20]
    customer_id: str                                              # 4 ✅ a reference, not 200 KB
    retrieved_doc_ids: list[str]                                  # 5 ✅ ids, not 40 KB of text
    internal_notes: str
    reply: str

# ── build ONCE at startup ────────────────────────────────────────────────
checkpointer_cm = PostgresSaver.from_conn_string(os.environ["DATABASE_URL"])
checkpointer = checkpointer_cm.__enter__()      # held for the process lifetime
checkpointer.setup()                            # one-time table creation

builder = StateGraph(FullState, input_schema=InputSchema, output_schema=OutputSchema)
# ...nodes...
app_graph = builder.compile(checkpointer=checkpointer)            # 2 ✅ shared across replicas

api = FastAPI()
CHAT_ID = re.compile(r"^[\w-]{1,64}$")

@api.post("/chat")
def chat(body: ChatBody, user=Depends(require_auth)):
    if not CHAT_ID.match(body.chat_id):                           # 9 ✅
        raise HTTPException(400, "invalid chat_id")
    if not user_owns_chat(user.id, body.chat_id):                 # 1 ✅
        raise HTTPException(403, "forbidden")

    return app_graph.invoke(
        {"messages": [HumanMessage(body.text)], "customer_id": user.customer_id},
        {"configurable": {
            "thread_id": f"{user.id}:{body.chat_id}",   # 1 ✅ derived, never trusted
            "db": pg_pool,                               # 3 ✅ context, not state
            "tier": user.tier,
        }},
    )                                                    # 7 ✅ already filtered by OutputSchema

# ── retention ────────────────────────────────────────────────────────────
# nightly: delete threads untouched for 30 days
# on account deletion: checkpointer.delete_thread(...) for every chat
#                      AND clear the store namespace                        # 8 ✅
```

> 📦 Note the Python-specific detail: `PostgresSaver.from_conn_string` is a **context
> manager** (like `SqliteSaver` in §5.8). In a long-running server you enter it once at
> startup rather than per request — or use `AsyncPostgresSaver` with your framework's
> lifespan hook. JS's `fromConnString` returns the saver directly.

**The two that would page you at 3am:**

- **#2 is the sneaky one.** `MemorySaver` behind 4 replicas doesn't fail — it *degrades
  probabilistically*. Roughly 3 turns in 4 land on a replica that's never seen the
  conversation. QA on one instance sees nothing wrong; production gets "the bot keeps
  forgetting" tickets that nobody can reproduce. **Any checkpointer that isn't shared storage
  is broken the moment you have more than one process** — and that includes serverless, where
  every request may be a fresh process.

- **#1 is the one that ends up in a disclosure.** There is no ownership check anywhere in
  LangGraph; thread isolation is `WHERE thread_id = ?`. If the id crosses the network from the
  client, you have an IDOR. It costs three lines to fix and it is not optional.

**The number worth quoting in the review:** 4 + 5 + 6 together mean roughly **45 MB of
checkpoint writes per conversation**. At 10k conversations a day that's 450 GB/day of writes
for an agent that could be doing 5 GB. Nobody signs off on that once it's written as a
number — which is why "what's in state, and how big is it?" should be a standing question in
every design review.
</details>

---

## 9. Interview questions

### Basic

**Q1. What is a checkpointer?**

The component that saves graph state after every superstep, keyed by `thread_id`. Attach one
at `compile()` and you get persistence, resumption, state history, time travel and
human-in-the-loop. Without one, state exists only for the duration of a single `invoke`.

---

**Q2. What is a `thread_id`?**

The identifier of one conversation — passed as `config.configurable.thread_id`. It's the key
checkpoints are stored under, so it's also the entire mechanism for isolating one user's
conversation from another's. Same graph, different `thread_id` → completely separate state.

---

**Q3. How do you resume a conversation?**

Invoke with the same `thread_id`. The checkpointer loads the latest checkpoint for that
thread and continues. There's no separate "resume" API — resuming is the normal path, and
starting fresh is just a thread with no checkpoints yet.

---

**Q4. What does passing `null` / `None` as input mean?**

"Don't add new input; continue from the checkpoint." Used for resuming an interrupted run,
replaying from a past checkpoint, and continuing after a fork. Passing an actual input object
merges it into state first, then runs.

---

**Q5. Which checkpointer would you use in production?**

Postgres, in almost every case — real concurrency, backups, and you're probably running one
already. `MemorySaver`/`InMemorySaver` is for tests only. SQLite is fine for a single-node or
desktop app. Redis suits very high throughput with short-lived threads, with a TTL set.

---

### Intermediate

**Q6. Explain time travel and the two forms it takes.**

Every superstep writes a checkpoint, and each one is addressable by `checkpoint_id`, so you
can re-enter the graph at any past point.

- **Replay** — `invoke(null, oldCheckpointConfig)` runs forward from that point unchanged.
  Note it does *not* re-execute the nodes before it; their results are loaded. That's why
  it's cheap, and why it's the right tool for "step 9 of 12 failed."
- **Fork** — `updateState(oldConfig, patch)` writes a new checkpoint whose parent is the old
  one, then you invoke from the result. Used for correcting a bad decision or injecting human
  input.

Both branch rather than rewrite: the original timeline still exists and is still replayable.

---

**Q7. What's in a state snapshot?**

`values` (every channel), `next` (which nodes run next — empty means finished), `config` (the
checkpoint's address: thread_id, checkpoint_ns, checkpoint_id), `parent_config`, `metadata`
(source, step), `created_at`, and `tasks` (pending work, which is where interrupts appear).

`values` and `next` together are a complete description of "where we are": what we know and
what we were about to do. That's precisely what makes resumption possible.

---

**Q8. `getStateHistory` returns snapshots in what order, and how do you pick a target?**

Newest-first, in both languages. Don't index blindly — filter on `next`: *"the checkpoint
where we were about to run the tools node"* is `history.filter(h => h.next[0] === "tools")`,
and since it's newest-first, `.at(-1)` gives you the earliest such point and `[0]` the most
recent. Getting that backwards is the most common time-travel bug.

---

**Q9. How does `updateState` interact with reducers?**

It applies the patch through them, exactly like a node's return value. On an appending
channel it appends — so `updateState(config, {messages: [m]})` adds a message rather than
replacing the history. To clear, you use the reducer's own protocol
(`RemoveMessage(REMOVE_ALL_MESSAGES)` for `addMessages`). There's no generic overwrite escape
hatch.

The optional third argument, `asNode`, makes the write look like it came from that node, so
`next` becomes that node's successors. That's the mechanism behind "edit the agent's plan and
continue."

---

**Q10. Your bot works in staging and "randomly forgets" in production. What's your first hypothesis?**

`MemorySaver` behind multiple replicas (or on serverless). Each process has its own in-memory
store, so a turn that lands on a different instance starts from nothing. It's probabilistic —
with 4 replicas, roughly 3 turns in 4 look broken — which is why it's unreproducible in
staging on one instance.

Fix: a shared checkpointer backend. The general rule: **any checkpointer that isn't shared
storage is broken the moment you have more than one process.**

Second hypothesis if that's not it: a `thread_id` that isn't stable across turns — a new
UUID per request, or one derived from something that changes.

---

**Q11. What are the costs of checkpointing, and how do you reduce them?**

Cost is `sizeof(state) × supersteps × turns × users`, since the full state is serialised after
every superstep. Levers, in order of impact:

1. **Shrink state** — pointers not payloads. Usually a 10–100× win on its own.
2. **Trim messages** — an uncapped history channel grows every checkpoint.
3. **Fewer supersteps** — merge trivially sequential nodes, parallelise independent ones.
4. **Faster backend** — pooled Postgres, or Redis for short-lived threads.

Teams reach for #4 first and get 20%. #1 is where the real win is.

---

### Advanced

**Q12. Design thread management for a multi-tenant SaaS agent.**

```
   IDENTITY     thread_id = `${tenantId}:${userId}:${chatId}` — derived server-side,
                never accepted from the client. Isolation is a database key with no
                ownership check inside LangGraph, so an id from the request body is an IDOR.

   OWNERSHIP    your own `conversations` table (id, tenant_id, user_id, title, updated_at)
                is the source of truth for "which chats exist". The checkpoint table is
                LangGraph's storage, not your application schema — don't query it to
                list a user's conversations.

   RETENTION    a TTL by tenant plan (30 days free / 1 year enterprise), a nightly job,
                and an alert on p99 checkpoint size as the early warning for state bloat.

   DELETION     GDPR/account deletion must clear: every thread's checkpoints, the store
                namespace for that user (Day 18), and your conversations rows. Test it —
                the store is the one people forget.

   ISOLATION    tenant id FIRST in the key so a prefix scan is per-tenant. For strict
                isolation, a schema or database per tenant, which also makes
                "delete this customer" a DROP.

   SCALE        the graph is stateless — compile once at startup, scale replicas freely.
                All the state is in the checkpointer, which is where your capacity
                planning belongs.
```

The line worth saying out loud: **the graph holds nothing, so it scales trivially; your
database holds everything, so that's the thing to design.**

---

**Q13. An agent made a bad tool call at step 4 of 12. Walk me through diagnosing and fixing it, in production.**

```
   1. GET THE THREAD    from the ticket or trace. The thread_id is the case number.

   2. READ THE HISTORY  get_state_history(config) → the full per-step record of what the
                        agent knew and what it was about to do. This is the answer to
                        "why did it do that", not a reconstruction from logs.

   3. FIND STEP 4       filter on `next` for the checkpoint about to run the tools node,
                        and read `values.messages` for the exact tool call and arguments.

   4. FORM A HYPOTHESIS bad tool description? missing data in state? a genuinely
                        ambiguous question? The state at step 3 tells you what it had
                        to work with.

   5. TEST BY FORKING   update_state at step 3 with a corrected message or tool result,
                        then invoke(None, forked). You've now re-run steps 4-12 with
                        the fix, without paying for steps 1-3 and without hoping a
                        stochastic model reproduces the path.

   6. FIX THE CAUSE     the fork proved the hypothesis; now change the tool description,
                        the prompt, or the guard. Add the case to your eval set (Day 25).

   7. DECIDE ON REPAIR  do you replay the customer's actual conversation with the fix?
                        Only with a record that you did. Silently forking a live thread
                        leaves two timelines and no note of which one the user saw.
```

Step 5 is the part that impresses: **this is a debugger for a non-deterministic distributed
system**, and very few frameworks give it to you for free.

---

**Q14. What are the security implications of checkpointing?**

Four, and they're all easy to get wrong:

1. **`thread_id` is an authorisation boundary with no built-in enforcement.** Isolation is
   `WHERE thread_id = ?`. A client-supplied id is a direct read of another user's
   conversation. Derive it server-side or verify ownership.
2. **Everything in state is written to a database.** API keys, PII, retrieved documents,
   internal reasoning — all persisted, replicated, and backed up, possibly with weaker access
   controls than your secrets manager. Secrets belong in context, which is never checkpointed.
3. **History is permanent by default.** "Delete that message" doesn't delete it from the
   checkpoints that already contain it. A real deletion story means deleting the thread.
4. **Time travel is a privileged operation.** `updateState` lets you rewrite what the agent
   "saw." Anyone who can call it can make the agent believe anything — that endpoint needs
   admin auth and an audit trail, and it should never be reachable from a user-facing route.

---

**Q15. When would you not use a checkpointer?**

- **Genuinely stateless one-shot calls** — classification, extraction, a single summary. No
  conversation, nothing to resume; checkpointing is pure overhead.
- **Extreme latency budgets** where a DB round-trip per superstep is unacceptable and the
  work is short enough to just retry from scratch.
- **Regulatory contexts where you must not persist content.** Some medical and financial
  settings require no retention; then you keep state in memory for the request's lifetime and
  accept losing resumability. (An in-memory saver is fine here — its non-durability is the
  feature.)

Everything else: use one. The cost is a database write per superstep; the benefit is
resumption, history, debuggability and human-in-the-loop. That trade is rarely close.

---

**Q16. How do checkpoints interact with `Send` fan-out and subgraphs?**

Checkpoints are per-superstep, so a `Send` fan-out of N workers produces **one** checkpoint
after that superstep, containing all N merged results — not N checkpoints. That's a
consequence of supersteps, and it's what makes fan-out cheap to persist.

Subgraphs get their own checkpoint namespace (`checkpoint_ns`), which is why streaming with
`subgraphs: true` returns a namespace path alongside each update, and why a subgraph can be
interrupted independently. It also means state history for a thread includes nested
namespaces — worth knowing when you're reading a history and see checkpoints you didn't
expect.

One practical consequence: a subgraph that shares an appending channel with its parent
(Day 19's duplication trap) makes every one of those checkpoints bigger too, so the bug shows
up as a storage problem as well as a correctness one.

---

## 10. Recap

### What you learned

- ✅ A checkpointer saves state **after every superstep** — three lines to add
- ✅ `thread_id` is the conversation, the save slot, **and the isolation boundary**
- ✅ Same graph + same `thread_id` = **continue**; different `thread_id` = **fresh**
- ✅ `getState` gives you `values` and `next` — what we know, what's about to run
- ✅ `getStateHistory` is a **free audit log**, newest-first
- ✅ **Replay** = `invoke(null, oldConfig)` — nodes before the checkpoint don't re-run
- ✅ **Fork** = `updateState` then invoke — branches, never rewrites
- ✅ `updateState` goes **through the reducers**; `asNode` changes what runs next
- ✅ `MemorySaver` is a dev tool — **broken with more than one process**
- ✅ Never trust a client-supplied `thread_id`
- ✅ Cost = `sizeof(state) × supersteps × turns × users` — **shrink state first**

### The mental shift

```
   BEFORE   the conversation lives in a variable while my function runs
   AFTER    the conversation lives in a database; my function loads it, appends, saves

   the graph holds NOTHING → it scales trivially
   the checkpointer holds EVERYTHING → that's the thing to design
```

### Tomorrow

**[Day 21 — Human-in-the-Loop](day-21-human-in-the-loop.md)**: the payoff. Today you learned
the graph can stop and be resumed from a saved state. Tomorrow you make it stop **on purpose**
— `interrupt()` pauses mid-node, surfaces a question to a human, and `Command({ resume })`
continues with their answer. Approve, reject, or **edit** the agent's plan before it runs.
Then the Week 3 project: a SQL agent that can read anything but must ask before it writes.

### Quick self-check

1. Your bot forgets everything on each deploy, but works fine locally. What's wrong?
2. What's the difference between `invoke(input, config)` and `invoke(null, config)`?
3. You want to re-run a 12-step agent from step 9. What do you call, and what does it cost?

<details>
<summary>Answers</summary>

1. **`MemorySaver` in production.** It's a dictionary in RAM, so it dies with the process — a
   deploy wipes every conversation. It works locally because you have one long-lived process.
   Swap in Postgres (or SQLite for a single node). The related failure to check for: with
   multiple replicas it doesn't just die on deploy, it fails *per request*, because each
   replica has its own memory.

2. `invoke(input, config)` **merges `input` into state through the reducers, then runs**.
   `invoke(null, config)` **adds nothing and continues from the checkpoint** — used for
   resuming an interrupted run, replaying from a past point, and continuing after a fork. If
   the config also carries a `checkpoint_id`, it resumes from that specific checkpoint rather
   than the latest.

3. Get the history, filter for the checkpoint whose `next` is the step-9 node, then
   `invoke(null, thatCheckpoint.config)`. The cost is **steps 9–12 only** — replay loads the
   earlier results rather than re-executing them, so you don't pay for steps 1–8 and you
   don't depend on a stochastic model reproducing the same path. If you want to *change*
   something at step 9 first, `updateState` on that checkpoint and invoke from the config it
   returns.
</details>

---

<div align="center">

**[← Day 19 — Control Flow](day-19-control-flow.md)** · **[Week 3 index](README.md)** · **[Day 21 — Human-in-the-Loop →](day-21-human-in-the-loop.md)**

</div>
