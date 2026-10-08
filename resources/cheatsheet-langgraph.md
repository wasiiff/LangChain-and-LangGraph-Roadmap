# LangGraph Cheatsheet

The graph API at a glance, in both languages — from
[Days 17–21](../week-03-tools-agents-and-langgraph/README.md) and
[Days 22–27](../week-04-production-projects-and-interviews/README.md). Every form below was run
in those chapters.

---

## The mental model

```
   STATE     named channels, each with a reducer            what the graph knows
   NODES     (state) → partial update                        what the graph does
   EDGES     fixed, conditional, Command, Send               what runs next
   SUPERSTEP all active nodes run on ONE snapshot → updates merged via reducers → route
   CHECKPOINT the full state saved after every superstep, keyed by thread_id
```

## Imports

```js
import { StateGraph, Annotation, MessagesAnnotation, START, END,
         MemorySaver, Command, Send, interrupt, addMessages } from "@langchain/langgraph";
import { ToolNode, toolsCondition } from "@langchain/langgraph/prebuilt";
```
```python
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command, Send, interrupt, RetryPolicy
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.config import get_stream_writer
```

## State

| | JavaScript | Python |
|---|---|---|
| declare | `Annotation.Root({ topic: Annotation(), ... })` | `class S(TypedDict): topic: str` |
| append list | `Annotation({ reducer: (a, b) => a.concat(b), default: () => [] })` | `Annotated[list, operator.add]` |
| counter | `Annotation({ reducer: (a, b) => a + b, default: () => 0 })` | `Annotated[int, operator.add]` |
| messages | `MessagesAnnotation` (reducer `addMessages`) | `MessagesState` (reducer `add_messages`) |
| extend messages | `Annotation.Root({ ...MessagesAnnotation.spec, extra: Annotation() })` | `class S(MessagesState): extra: str` |
| input/output schemas | `new StateGraph({ stateSchema, input, output })` | `StateGraph(S, input_schema=I, output_schema=O)` |

**Reducer rules:** pure, total (handles the default), non-mutating, associative. A node returns
only the **delta** — never the full list with an append reducer.

**`addMessages` / `add_messages`:** appends; replaces a message with the same `id`; assigns ids;
`RemoveMessage(id)` deletes; `RemoveMessage(REMOVE_ALL_MESSAGES)` clears.

## Building

```js
const app = new StateGraph(State)
  .addNode("agent", agentFn)
  .addNode("tools", new ToolNode(tools))
  .addEdge(START, "agent")
  .addConditionalEdges("agent", toolsCondition, ["tools", END])
  .addEdge("tools", "agent")
  .compile({ checkpointer: new MemorySaver() });
```
```python
b = StateGraph(MessagesState)
b.add_node("agent", agent_fn)
b.add_node("tools", ToolNode(tools))
b.add_edge(START, "agent")
b.add_conditional_edges("agent", tools_condition, ["tools", END])
b.add_edge("tools", "agent")
app = b.compile(checkpointer=InMemorySaver())
```

## Control flow

| Need | JavaScript | Python |
|---|---|---|
| fixed edge | `.addEdge("a", "b")` | `.add_edge("a", "b")` |
| router | `.addConditionalEdges("a", fn, ["b", "c", END])` | `.add_conditional_edges("a", fn, ["b", "c", END])` |
| update **and** route | `return new Command({ update, goto: "b" })` | `return Command(update=..., goto="b")` |
| declare Command targets | `.addNode("a", fn, { ends: ["b", "c"] })` | `def a(s) -> Command[Literal["b", "c"]]:` |
| fan out, N at runtime | router returns `items.map((x) => new Send("work", { x }))` | router returns `[Send("work", {"x": x}) for x in items]` |
| subgraph | `.addNode("sub", compiledGraph)` — prefer a wrapper node | `.add_node("sub", compiled_graph)` — prefer a wrapper node |
| jump to parent graph | `new Command({ goto, graph: Command.PARENT })` (+ `ends` on the parent node) | `Command(goto=..., graph=Command.PARENT)` |

⚠️ **`Command` goto adds to static edges** — it doesn't replace them. A node that routes with
`Command` should have no static outgoing edge.
⚠️ A `Send` payload is the worker's **entire** state. Pass everything it needs.
⚠️ A subgraph returns its **whole** final state; shared appending channels duplicate.

## Running

| | JavaScript | Python |
|---|---|---|
| run | `await app.invoke(input, config)` | `app.invoke(input, config)` |
| thread | `{ configurable: { thread_id: "t1" } }` | `{"configurable": {"thread_id": "t1"}}` |
| recursion cap | `{ recursionLimit: 50 }` (default 25) | `{"recursion_limit": 50}` (default **10007** in langgraph 1.2.x — always set it) |
| stream | `for await (const c of await app.stream(input, { streamMode: "updates" }))` | `for c in app.stream(input, config, stream_mode="updates")` |
| several modes | `streamMode: ["updates", "messages", "custom"]` → `[mode, chunk]` | `stream_mode=[...]` → `(mode, chunk)` |
| nested graphs | `subgraphs: true` → `[namespace, chunk]` | `subgraphs=True` → `(namespace, chunk)` |
| custom events | `config.writer?.({ ... })` | `get_stream_writer()({ ... })` |
| cancel | `signal` option + `config.signal` in nodes | close the generator |
| diagram | `(await app.getGraphAsync()).drawMermaid()` | `app.get_graph().draw_mermaid()` |

Stream modes: `values` (full state), `updates` (node deltas), `messages` (tokens + metadata),
`custom`, `debug`, `tasks`, `checkpoints` (needs a checkpointer).

## Persistence & time travel

| | JavaScript | Python |
|---|---|---|
| current state | `await app.getState(config)` → `values`, `next`, `tasks` | `app.get_state(config)` |
| history (newest first) | `for await (const s of app.getStateHistory(config))` | `list(app.get_state_history(config))` |
| replay from a checkpoint | `await app.invoke(null, snapshot.config)` | `app.invoke(None, snapshot.config)` |
| fork with a change | `await app.updateState(snapshot.config, patch, asNode?)` | `app.update_state(snapshot.config, patch, as_node=...)` |
| SQLite | `SqliteSaver.fromConnString(path)` | `with SqliteSaver.from_conn_string(path) as cp:` |
| Postgres | `PostgresSaver.fromConnString(url)`; `await cp.setup()` | `with PostgresSaver.from_conn_string(url) as cp: cp.setup()` |
| long-term store | `InMemoryStore` / `PostgresStore`; node reads `config.store` | `InMemoryStore` / `PostgresStore`; node param `*, store` |

## Human-in-the-loop

```js
function gate(state) {
  const decision = interrupt({ question: "Approve?", plan: state.plan });   // FIRST line
  return decision === "approve" ? new Command({ goto: "act" }) : new Command({ goto: END });
}
// .addNode("gate", gate, { ends: ["act", END] })     ← declare Command targets in JS
// caller
const r = await app.invoke(input, config);           // r.__interrupt__ → [{ id, value }]
await app.invoke(new Command({ resume: "approve" }), config);
```
```python
def gate(state) -> Command[Literal["act", "__end__"]]:
    decision = interrupt({"question": "Approve?", "plan": state["plan"]})   # FIRST line
    return Command(goto="act" if decision == "approve" else END)

r = app.invoke(inp, config)                           # r["__interrupt__"] → [Interrupt(value, id)]
app.invoke(Command(resume="approve"), config)
```

- The node **re-runs from the top** on resume — no side effects before `interrupt()`.
- Several pending interrupts → resume with `{ [interruptId]: value }`.
- Static breakpoints for debugging: `compile({ interruptBefore: ["node"] })` / `interrupt_before=[...]`.

## Reliability on nodes

| | JavaScript | Python |
|---|---|---|
| retry | `addNode(n, fn, { retryPolicy: { maxAttempts: 3, initialInterval: 500, retryOn } })` | `add_node(n, fn, retry_policy=RetryPolicy(max_attempts=3, retry_on=...))` |
| timeout | `addNode(n, fn, { timeout: 10_000 })` (ms) | `add_node(n, fn, timeout=10)` (s) — **async nodes only** |
| fallback node | — | `add_node(n, fn, error_handler=fallback_fn)` |

Python's default `retry_on` does **not** retry `ValueError`, `TypeError`, `RuntimeError` or any
`OSError` (including `TimeoutError`) — pass your own.

## Serving

```json
{ "dependencies": ["."], "graphs": { "studybuddy": "./graph.py:graph" }, "env": ".env" }
```

- Export `builder.compile()` **without** a checkpointer — the server rejects one and uses `POSTGRES_URI`.
- `langgraph dev` (Python, `pip install "langgraph-cli[inmem]"`) / `npx @langchain/langgraph-cli dev`.
- Clients: `get_client(url=...)` / `new Client({ apiUrl })` → `threads.create`, `runs.wait`,
  `runs.stream`, `runs.create` + `runs.join`, `threads.get_state` / `getState`,
  resume with `command=Command(resume=...)` / `{ command: { resume } }`.

## The ten bugs to recognise on sight

| Symptom | Cause |
|---|---|
| `invoke` returns `undefined` / `None` | a node wrote an undeclared key |
| `InvalidUpdateError: … can only receive one value per step` after fan-out | last-write-wins channel — add a combining reducer |
| list items doubled | returning the full list with an append reducer; subgraph sharing a channel |
| `GraphRecursionError` | a loop without a budget exit |
| conversation resets | unstable `thread_id` or in-memory checkpointer across processes |
| side effect runs twice after approval | code before `interrupt()` |
| rejected action still runs | `Command` goto + static edge |
| worker can't see a parent value | `Send` payload missing it |
| Python node never retries a timeout | default `retry_on` |
| server refuses the graph | compiled with a checkpointer |
