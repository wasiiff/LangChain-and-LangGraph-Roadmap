# Week 3 — Tools, Agents & LangGraph

> **Goal:** stop writing the steps yourself. Give the model real capabilities, let it decide
> what to do next — and then make that decision process something you can **save, pause,
> rewind, inspect and draw**.

← [Back to the main index](../README.md) · [Week 2](../week-02-data-embeddings-and-rag/README.md)

---

## The week at a glance

| Day | Topic | Time | Difficulty | You'll build |
|---|---|---|---|---|
| [15](day-15-tools.md) | Tools: schemas, the calling loop, errors, **security** | 3h | ●●●○○ | Six real tools + a safe SQL tool |
| [16](day-16-agents.md) | **Agents from scratch** — hand-build ReAct, then the framework | 2.5h | ●●●○○ | A ReAct agent in ~40 lines, no framework |
| [17](day-17-langgraph-basics.md) | LangGraph basics: state, nodes, edges, **your first graph** | 3h | ●●●○○ | Yesterday's agent in **20 lines** |
| [18](day-18-state-and-reducers.md) | State & reducers · **state vs memory vs context vs store** | 2.5h | ●●●○○ | A multi-schema graph with custom reducers |
| [19](day-19-control-flow.md) | Conditional edges, loops, `Command`, `Send` fan-out, subgraphs | 3h | ●●●●○ | A map-reduce research graph |
| [20](day-20-persistence-and-checkpointing.md) | Checkpointers, threads, replay, **time travel** | 2.5h | ●●●○○ | A bot that survives a restart |
| [21](day-21-human-in-the-loop.md) | `interrupt` / resume · approve, reject, edit · Week project | 3h | ●●●●○ | 🏆 **StudyBuddy v4** — SQL agent with an approval gate |

**Total: ~19.5 hours.**

---

## What you'll be able to do by Sunday

- [ ] Write a tool whose description is good enough that the model picks it correctly
- [ ] Explain why tool errors should be **returned as content**, not thrown
- [ ] Defend a tool against path traversal and SQL injection — and say why that matters more here
- [ ] Hand-build a ReAct loop and explain why text ReAct needs a stop sequence
- [ ] Name the five ways agents fail in production and the guard for each
- [ ] Explain **supersteps** and why two parallel nodes can't see each other's writes
- [ ] Choose the right reducer for a channel — and spot the double-append bug on sight
- [ ] Draw the line between **state, memory, context, store and checkpoint** in one breath
- [ ] Build a loop with two exits and know why one is never enough
- [ ] Fan out with `Send` and merge results without losing any of them
- [ ] Resume a conversation after a process restart, from a database
- [ ] Rewind to any past checkpoint and re-run from there with different input
- [ ] Pause a graph before a destructive action, show a human the plan, and resume on approval

---

## The through-line

Each day exists because the previous day created a problem:

```
Day 14  Memory works — but the bot can only ever TALK           → give it capabilities
Day 15  Tools: it can now act                                   → but YOU still order the steps
Day 16  An agent: the model orders the steps                    → but state lives in local vars
Day 17  A graph: state is an object you own                     → reducers are subtle, get them right
Day 18  Reducers & the state/memory/context/store split         → control flow is still just if/else
Day 19  Command, Send, subgraphs, real routing                  → all of it dies on restart
Day 20  Checkpointers: save, resume, rewind                     → so we CAN pause... for a human
Day 21  interrupt() — approve / reject / edit                   →  Week 4: many agents, in production
```

Week 2 ended with you hand-writing state machines and hating it. Week 3 is the answer, and
it lands in the middle of the week: **Day 17 is the hinge of the entire book.** Everything
before it is "call a model well." Everything after it is "run a system you can operate."

---

## The four superpowers, and where they come from

Days 18–21 look like four separate topics. They're really four consequences of one decision
made on Day 17 — **the state is a plain object the framework owns, not local variables**:

```
                     ┌─────────────────────────────────┐
                     │  STATE IS AN OBJECT WE OWN      │   ← Day 17
                     └─────────────────────────────────┘
                        │        │         │        │
              ┌─────────┘        │         │        └──────────┐
              ▼                  ▼         ▼                   ▼
        save the object    print it   keep every       hold it and wait
              │            after      version              │
              ▼            each node      │                ▼
        PERSISTENCE        │              ▼          HUMAN-IN-THE-LOOP
          (Day 20)      STREAMING     TIME TRAVEL         (Day 21)
                        (Day 23)       (Day 20)
```

If you understand that diagram, the rest of the week is detail.

---

## 🚨 The version trap, part 2

Week 2 warned that legacy chains and retrievers moved to `@langchain/classic` /
`langchain-classic`. Agents have their own version story, and it's worse — there are **three
generations** of agent API still findable online:

| Generation | ❌ Don't learn from this | Status |
|---|---|---|
| 0.x | `initialize_agent(...)`, `AgentType.ZERO_SHOT_REACT_DESCRIPTION` | Removed |
| 0.1–0.3 | `AgentExecutor`, `createReactAgent` from `langchain/agents` | Legacy, in `classic` |
| **1.x** | **`createAgent` (JS) / `create_agent` (Python)** | ✅ **Current** |

```js
// ✅ current
import { createAgent } from "langchain";
```
```python
# ✅ current
from langchain.agents import create_agent
```

`createReactAgent` / `create_react_agent` from **`@langchain/langgraph/prebuilt`** /
**`langgraph.prebuilt`** also still exists and works — it's the LangGraph-native one, and it's
what `createAgent` is built on. Not to be confused with the identically named legacy function
in `langchain/agents`, which is the 0.x one. Yes, really.

**Every import in this week was verified by actually importing and running it.**

---

## Extra installs for this week

```bash
# JavaScript
npm install @langchain/langgraph @langchain/core zod

# Python
pip install langgraph langchain-core

# Day 20 only — a real checkpointer instead of the in-memory one
npm install @langchain/langgraph-checkpoint-sqlite
pip install langgraph-checkpoint-sqlite
```

Chat still comes from Groq (free). Nothing this week needs a paid key.

---

## The API-name minefield (JS ↔ Python)

LangGraph is one of the places where the two SDKs diverge most in naming. Bookmark this:

| Concept | JavaScript | Python |
|---|---|---|
| declare state | `Annotation.Root({...})` | `class S(TypedDict)` |
| channel + reducer | `Annotation({ reducer, default })` | `Annotated[list, operator.add]` |
| messages state | `MessagesAnnotation` | `MessagesState` |
| messages reducer | `addMessages` | `add_messages` |
| tool router | `toolsCondition` | `tools_condition` |
| get the diagram | `await app.getGraphAsync()` | `app.get_graph()` |
| mermaid | `.drawMermaid()` | `.draw_mermaid()` |
| in-memory checkpointer | `MemorySaver` | `InMemorySaver` |
| recursion cap | `{ recursionLimit: 50 }` | `{"recursion_limit": 50}` |
| thread id | `{ configurable: { thread_id } }` | `{"configurable": {"thread_id": ...}}` |
| state history | `app.getStateHistory(config)` | `app.get_state_history(config)` |

Note `thread_id` is **snake_case in both languages** — it's a config key, not a method name.
That inconsistency has cost more debugging hours than it has any right to.

---

## Common Week 3 blockers

| Symptom | Day | Fix |
|---|---|---|
| Model never calls your tool | 15 | The description is the prompt. Say *when* to use it, not just what it does |
| `400 invalid messages` after a tool call | 15 | `tool_call_id` doesn't match. Use `ToolNode` rather than building `ToolMessage` by hand |
| Tool throws and kills the run | 15 | Return the error as content so the model can recover |
| Agent invents "Observation:" text | 16 | Text ReAct without `stop: ["Observation:"]`. Or just use native tool calling |
| Agent calls the same tool forever | 16 | Add repeat detection that returns a *message*, not the same result |
| Agent costs 10× your estimate | 16 | History is re-sent every step — cost is super-linear in steps |
| `UnreachableNodeError` / "must have an entrypoint" | 17 | Missing `addEdge(START, ...)` |
| `invoke()` returns `undefined` / `None`, no error | 17 | A node is writing a channel name that doesn't exist. Typo. Silent by design |
| Parallel node reads stale/`undefined` data | 17 | Same superstep = same snapshot. If B needs A, add an edge A→B |
| Items appear twice in a list channel | 17 | You did the reducer's job: send the delta, not the merged value |
| Two parallel results, only one survives | 17 | Last-write-wins channel. Fan-out needs a combining reducer |
| `GraphRecursionError` | 17 | Your loop has no budget exit. Fix the router, don't raise the limit |
| State leaks between users | 17/20 | `default: []` instead of `default: () => []`, or a missing `thread_id` |
| `GraphValueError: No checkpointer set` | 20 | `getState`/`getStateHistory` need `compile({ checkpointer })` |
| Conversation resets on every message | 20 | Same `thread_id` per conversation — that's the whole mechanism |
| `interrupt()` fires again after resume | 21 | The node re-runs from its start on resume. Put `interrupt` first in the node |

---

## Interview topics covered this week

Ranked by how often they come up:

1. **LangGraph vs LCEL — when do you reach for a graph?** (Day 17) — asked in almost every
   LangChain interview in 2025-26
2. **State, reducers and supersteps** (Days 17–18) — the question that separates people who
   have used LangGraph from people who have read about it
3. **State vs memory vs context vs store vs checkpoint** (Day 18)
4. **How agents actually work: the ReAct loop** (Day 16)
5. **Tool design and what makes a tool description good** (Day 15)
6. **Persistence, threads and time travel** (Day 20)
7. **Human-in-the-loop: how do you gate a destructive action?** (Day 21)
8. **Agent failure modes and guardrails** (Day 16)
9. **`Send` / map-reduce fan-out** (Day 19)
10. **Tool security — injection, traversal, and why it's worse with an LLM** (Day 15)

---

## StudyBuddy — the running project

```
Week 1  v1.0   parallel analysis · routing · streaming · retries
Week 2  v2/v3  reads YOUR documents · citations · memory across sessions
Day 16  v3.5   + tools: it can calculate, search, and query your progress DB
Day 17  v3.6   + rebuilt as a graph — and it draws its own architecture diagram
Day 21  v4.0   🏆 + persistence · time travel · a human approval gate before any DB write
```

Week 4 turns v4 into a deployed, observable, multi-agent system.

---

## A note on difficulty

Day 17 is the steepest single step in this book. If supersteps and reducers don't click on
the first read, that's the expected experience — do **Exercise 1** of Day 17 (it needs no API
key and takes five minutes) and the model will snap into place. Nearly everything in Weeks
3 and 4 rests on it.

---

→ Start with **[Day 15](day-15-tools.md)**
