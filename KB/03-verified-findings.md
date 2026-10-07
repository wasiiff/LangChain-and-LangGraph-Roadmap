# 03 — Verified findings

Every technical claim in this book that was established by **running code**, not by recall.
Verified against the versions in [04-versions-and-environment.md](04-versions-and-environment.md)
during September–October 2026.

**Use this file two ways:** before changing a technical claim, check what was measured; after
re-verifying anything, update the row and note the version.

Legend: **JS** = JavaScript only · **PY** = Python only · **both** = same in both languages.

---

## Import paths and packaging (Weeks 1–2)

| Finding | Detail | Day |
|---|---|---|
| Canonical message imports | `@langchain/core/messages` / `langchain_core.messages` work on 0.3 **and** 1.x; `from "langchain"` / `langchain.messages` also work on 1.x but are not portable | 04 |
| 🚨 Legacy components moved in 1.x | chains, legacy retrievers, memory, `MemoryVectorStore` → `@langchain/classic/*` and `langchain_classic.*`. Most online tutorials import paths that no longer exist | 08 |
| Loader paths | `@langchain/classic/document_loaders` exposes only `base`, `fs/buffer`, `fs/directory`, `fs/json`, `fs/multi_file`, `fs/text`. PDF/CSV/web loaders live in `@langchain/community/document_loaders/*` (otherwise `ERR_PACKAGE_PATH_NOT_EXPORTED`) | 09 |
| Vector store asymmetry | **PY** `InMemoryVectorStore` ships in `langchain-core`; Chroma persists to a directory with no server. **JS** needs `@langchain/classic` and a running Chroma | 11 |
| Embeddings providers | Groq has **no** embeddings endpoint → Ollama `nomic-embed-text` or Google. **PY** Google embeddings need the `models/` prefix; **JS** does not | 10 |
| Splitter semantics | `chunkSize` is a **maximum**, not a target; `splitDocuments` preserves metadata, `splitText` does not | 09 |

## Graphs: construction and execution (Day 17)

| Finding | Evidence | Lang |
|---|---|---|
| No entrypoint | **JS** `UnreachableNodeError: Node \`z\` is not reachable.` · **PY** `ValueError: Graph must have an entrypoint: add at least one edge from START to another node` | differs |
| Edge to unknown node | `Found edge ending at unknown node \`nope\`` (JS `Error`, PY `ValueError`) | both |
| Duplicate / reserved node names | `Node \`z\` already present.` · `Node \`__start__\` is reserved.` | both |
| Writes to undeclared channels are dropped **silently** | a node returning only `{nokey: 1}` → `invoke` returned `undefined` (JS) / `None` (PY), no error | both |
| Node returning nothing is fine | `undefined`/`None` return → state unchanged | both |
| Chunk counts, 2-node graph | `values` 3 · `updates` 2 (values includes the pre-run state) | both |
| Fan-out folding | 3 parallel writers + append reducer → all three merged, order **not** guaranteed | both |
| Recursion limit | default 25 supersteps → `GraphRecursionError: Recursion limit of N reached without hitting a stop condition` | both |
| Conditional-edge destinations | **JS** requires the 3rd array arg for diagrams/validation; **PY** can infer | differs |
| `toolsCondition` | returns `"tools"` with tool calls, `"__end__"` without | both |
| Compiled graph is a Runnable | class `CompiledStateGraph`; has `invoke`/`stream`/`batch` (+`pipe` in JS) | both |
| Diagrams | conditional edges render as dotted lines; `await app.getGraphAsync()` / `app.get_graph()` | differs |
| Python defaults materialise differently | **JS** `Annotation` defaults appear in output; **PY** `TypedDict` keys with no reducer are absent until written | differs |

## State and reducers (Day 18)

| Finding | Evidence | Lang |
|---|---|---|
| `addMessages` does four things | appends · **upserts by id** · auto-assigns UUIDs · handles `RemoveMessage` (by id, or `REMOVE_ALL_MESSAGES` = `"__remove_all__"`) | both |
| Message dicts are coerced | `add_messages([], [{"role": "user", "content": "hey"}])` → `HumanMessage` with an id | both |
| Three schemas | **PY** `StateGraph(S, input_schema=I, output_schema=O)` · **JS** `new StateGraph({ stateSchema, input, output })`; verified that `scratch` and `question` were filtered from output | differs |
| Store injection | **JS** `config.store` · **PY** keyword-only `def node(state, config, *, store)` — without the `*` you get a `TypeError` | differs |
| Store API | `put(namespace, key, value)` / `get` / `search`; namespace is an **array** in JS, a **tuple** in PY; `"me"` resolves to the current user with the `user` capability | differs |
| Pydantic state | node receives a **model instance** (`state.n`), `invoke` still returns a **dict**, bad input raises `ValidationError` | PY |
| Deduping reducer under fan-out | writers `["a","b"]` + `["b","c"]` → `["a","b","c"]` | both |
| `default` must be a factory | `default: []` is shared across runs and threads; `default: () => []` is not | JS |

## Control flow (Day 19)

| Finding | Evidence | Lang |
|---|---|---|
| `Command` = update + route | verified both branches; renders as dotted edges | both |
| Declaring `Command` targets | **JS** `{ ends: [...] }` on `addNode` · **PY** `-> Command[Literal[...]]` return annotation (or `destinations=`) | differs |
| ⚠️ `Command` **adds to** static edges | `decide → Command(goto="agent")` **plus** `decide → tools` ran **both**: `['decide→agent','agent ran','TOOLS RAN']`. In an approval gate this executes rejected actions | both |
| `Send` payload replaces state | a worker read `state.secret` as `undefined`/`None` — it sees only its payload | both |
| `Send` merge | N workers → one superstep, append reducer merges; the join node runs **once**; order not guaranteed (carry an index) | both |
| Empty `Send` list | activates nothing — that branch halts silently | both |
| ⚠️ Subgraph duplication | shared appending channel: parent `["before"]` → subgraph returns its **whole** state → `['before','before','inner1','inner2','after']` | both |
| Fix | a wrapper node with its own channel names → `['before','inner1','inner2','after']` | both |
| `Command.PARENT` | equals `"__parent__"`; works from a subgraph. **JS** also needs `ends` on the parent's subgraph node | differs |
| Debugging nesting | `xray: true` / `xray=True` renders nested `subgraph` blocks; streaming with `subgraphs` yields `[namespace, update]` | both |

## Persistence (Day 20)

| Finding | Evidence | Lang |
|---|---|---|
| Checkpoint cadence | 2 runs of a 2-node graph → **8** checkpoints (≈ supersteps + 2 per run) | both |
| History order | **newest first**; `next` tells you what would run on resume; `step` starts at `-1` (the input checkpoint) | both |
| Checkpoint ids | time-ordered UUIDs — slice ≥13 chars when printing or they all look identical | both |
| Replay | `invoke(null/None, snapshot.config)` runs forward **without** re-executing earlier nodes | both |
| Fork | `updateState` applies the patch **through reducers** (appends on append channels) and creates a child checkpoint; the original timeline survives | both |
| `asNode` | makes the write look like that node produced it, so `next` becomes its successors | both |
| Cross-process persistence | SQLite: process A ran to `n=1`, a **new** saver in process B continued to `n=2`, 20 KB file | both |
| SQLite API shape | **JS** `SqliteSaver.fromConnString(path)` returns the saver · **PY** `with SqliteSaver.from_conn_string(path) as cp:` (context manager) | differs |
| Missing checkpointer | `No checkpointer set` (JS `GraphValueError`, PY `ValueError`) | both |
| Missing `thread_id` | **JS** `Failed to put checkpoint … missing a required "thread_id"` · **PY** `Checkpointer requires one or more of the following 'configurable' keys: thread_id, checkpoint_ns, checkpoint_id` | both |
| Postgres packaging | **PY** `from langgraph.checkpoint.postgres import PostgresSaver` → `ModuleNotFoundError` on the base install; needs `langgraph-checkpoint-postgres` | PY |

## Human-in-the-loop (Day 21)

| Finding | Evidence | Lang |
|---|---|---|
| Interrupt surfaces in the result | `__interrupt__: [{ id, value }]`; also `getState().tasks[].interrupts` | both |
| ⚠️ The node **re-runs from the top** on resume | a counter before `interrupt()` read **2** after one approval | both |
| Resume | `Command({ resume })` / `Command(resume=…)` on the **same** thread | both |
| Multiple pending interrupts | a bare value raises `RuntimeError: When there are multiple pending interrupts, you must specify the interrupt id when resuming`; a map `{id: value}` works | both |
| `update` + `resume` together | applied through reducers, then the node re-runs | both |
| Static breakpoints | `interruptBefore` / `interrupt_before` leave `next` set; resume with `invoke(null/None, config)` | both |
| Parallel interrupts | each gets its own id; answering one leaves the rest pending | both |

## Multi-agent (Day 22)

| Finding | Evidence | Lang |
|---|---|---|
| Cost of delegation | same single-hop question: **1 agent = 2 model calls**, **agent-as-tool = 4**, **library supervisor = 4** | both |
| Context isolation | agent-as-tool worker saw 1 then 3 messages; library-supervisor worker saw 3 then 5; the boss's 2nd call saw 3 (last_message) vs 6, or 8 with `full_history` | both |
| Supervisor message trace | 7 messages with `last_message`, 9 with `full_history`; includes **two synthetic transfer-back messages** per round trip | both |
| JS `createAgent` return | a `ReactAgent` wrapper — `.name` is `undefined`, the named `CompiledStateGraph` is on **`.graph`**; passing the wrapper to `createSupervisor` throws the misleading "Please specify a name…" | JS |
| Unnamed agent | **JS** `Error` · **PY** `ValueError` — "Please specify a name when you create your agent…" | both |
| Agent graph node names | **JS** `__start__`, `model_request`, `tools` · **PY** `__start__`, `model`, `tools`, `__end__` | differs |
| Swarm memory | with a checkpointer, turn 2 went straight to the last active agent (alice 1 call, bob 2); **without** one (history passed manually) it reset to the default agent | both |
| Ping-pong handoffs | `GraphRecursionError`; 12 model calls at `recursionLimit: 12`, **37** at the JS default | both |
| Parallel delegation | two 400 ms subagent tools in one turn: **411 ms** (JS) / **414 ms** (PY), not ~800 ms | both |
| Library status (as tested) | PY `langgraph-supervisor` README recommends the **tool-based** supervisor instead; JS `langgraph-swarm` README recommends `createReactAgent` over `createAgent` | — |

## Streaming (Day 23)

| Finding | Evidence | Lang |
|---|---|---|
| Mode chunk counts (2-node graph) | `values` 3 · `updates` 2 · `messages` many · `custom` 2 · `debug` 4 · `tasks` 4 · `checkpoints` 3 | both |
| `checkpoints` without a checkpointer | **JS** `TypeError: Cannot read properties of undefined (reading 'slice')` · **PY** `IndexError: list index out of range` | both |
| Checkpoint key naming | `parentConfig` (JS) vs `parent_config` (PY) | differs |
| Token metadata | `[chunk, { langgraph_node, tags, … }]`; **every** model in the graph streams, so filter by a `final` tag | both |
| Custom events | `config.writer?.()` (JS) / `get_stream_writer()` (PY) work from nodes **and** from tools inside `ToolNode`; also from sync **and** async tools under `astream` | both |
| Nested agents' tokens | **JS**: included by default (`langgraph_node: "sub_llm"`) · **PY**: only with `subgraphs=True`; passing `config` made no difference either way | differs |
| Namespaced streaming | items arrive as `[namespace, payload]`, e.g. `delegate:<id>/sub_llm:<id>` | both |
| ⚠️ Cancellation | **JS** `break` → the graph **ran to completion** (`first > second > third`). Abort signal → `AbortError` and the graph stops at the next superstep; the in-flight node finishes **unless** it honours `config.signal`. **PY** `break` (sync and async) → stopped before the next superstep | differs |
| SSE round-trip | verified with Node `http` + a `fetch` reader, and with FastAPI `StreamingResponse` + `TestClient`: `text/event-stream`, events in order | both |
| `streamEvents` v2 | event kinds and counts differ between languages — don't build a UI on exact counts | differs |

## Reliability (Day 24)

| Finding | Evidence | Lang |
|---|---|---|
| ⚠️ Model-retry default | `onFailure`/`on_failure` defaults to `"continue"`: after retries the **error text becomes the AI reply** — "Model call failed after 2 attempts with …" | both |
| `onFailure: "error"` | **JS** throws `MiddlewareError` · **PY** re-raises the **original** exception | differs |
| Model-call limit | `"end"` → run ends with a limit message (JS "…run level call limit reached with 2 model calls" / PY "…run limit (2/2)"); `"error"` → `ModelCallLimitMiddlewareError` (JS) / `ModelCallLimitExceededError` (PY) | differs |
| Tool-call limit | blocked calls answered with "Tool call limit exceeded. Do not make additional tool calls."; PY kept looping (5 model calls), JS ended after the first blocked call | differs |
| Fallback middleware | primary 1 failed call, backup 1 call, answer from backup | both |
| Retry middleware | fails twice then succeeds on attempt 3; retried `RuntimeError`/`TimeoutError` (unlike the **node** policy below) | both |
| ⚠️ Tool exceptions | **JS** `ToolNode` returns `"Error: db unreachable\n Please fix your mistakes."` as content · **PY** re-raises (even `ToolException`); only **argument-validation** errors become content. `handle_tool_errors=True` → `"Error: ConnectionError('db unreachable')\n Please fix your mistakes."`; a string replaces the message | differs |
| ⚠️ Node `retry_policy` default (PY) | `default_retry_on` retries `ConnectionError` and HTTP 5xx; returns **False** for `ValueError`, `TypeError`, `RuntimeError`, `LookupError`, `OSError` (so **`TimeoutError` is not retried**); unknown types retry. Verified: ConnectionError 3 attempts, TimeoutError 1, RuntimeError 1, custom `retry_on` 3 | PY |
| Node retry (JS) | retried a plain `Error`; defaults `maxAttempts` 3, `initialInterval` 500 ms, `jitter` on, `logWarning` on | JS |
| JS jitter is large | `initialInterval: 10` → **242 ms** and **666 ms** across two runs; `jitter: false` → **80 ms** | JS |
| Node timeout | **JS** `NodeTimeoutError: Node "slow" exceeded its run timeout of 50ms` · **PY async** equivalent; **PY sync** → `ValueError: Node timeouts are only supported for async nodes because sync Python execution cannot be safely cancelled` | differs |
| `error_handler` | a node-shaped fallback: the failed node's update becomes the handler's return (`{"out": "handled"}`) | PY |
| Call-option timeout | `invoke(x, { timeout: 50 })` → `DOMException: The operation was aborted due to timeout` | JS |
| Runnable retry / fallbacks | `withRetry({ stopAfterAttempt })`, `withFallbacks([…])` **and** `({ fallbacks: […] })` both work; `with_retry(stop_after_attempt=…)`, `with_fallbacks([…])` | both |
| Rate limiter | `InMemoryRateLimiter(requests_per_second=5, max_bucket_size=1)`: 4 calls took **833 ms** | PY |
| PII strategies | redact → `[REDACTED_EMAIL]` (both) · mask → **JS** `a***@example.com`, **PY** `ayesha.khan@****.com` · hash → different digests per language · block → `PIIDetectionError` | differs |
| PY PII defaults | input only (`apply_to_input=True`, output and tool results off) | PY |
| Client retry defaults | `ChatGroq` `maxRetries` **6** (JS) vs `max_retries` **2** (PY); PY has `request_timeout`, JS uses a call-option timeout | differs |

## Observability & evaluation (Day 25)

| Finding | Evidence | Lang |
|---|---|---|
| ⚠️ Chat models don't fire LLM-start | agent run with 2 model calls: `handleChatModelStart`/`on_chat_model_start` 2, `handleLLMStart`/`on_llm_start` **0**; end events arrive as `handleLLMEnd`/`on_llm_end` | both |
| Chain-event counts differ | JS chainStart 7 / PY chain_start 4 for the same run — don't build metrics on them | differs |
| Token totals agree | messages sum = handler sum = 300 (250 in / 50 out) | both |
| Per-model usage | `get_usage_metadata_callback()` → `{'scripted-1': {'input_tokens': 250, 'output_tokens': 50, 'total_tokens': 300}}` | PY |
| `traceable` offline | with `LANGSMITH_TRACING` unset the decorated function runs normally and nothing is sent | both |
| LLM-as-judge | `create_llm_as_judge` / `createLLMAsJudge` → `{key, score, comment}`; the judge is asked for a `{reasoning, score}` schema (tool named `score`); `continuous` → numeric; `use_reasoning=False` → `comment: None` | both |
| Judge prompt placeholders | `CORRECTNESS_PROMPT` wants `inputs`, `outputs`, `reference_outputs`; `RAG_GROUNDEDNESS_PROMPT` wants `context`, `outputs` (reference-free) | both |
| Trajectory evaluators | `strict`/`unordered`/`subset`/`superset` all scored true for identical trajectories, false for a different tool; `tool_args_match_mode` `exact` vs `ignore` behaved as named; keys like `trajectory_strict_match` | both |
| `evaluate` offline | **PY** works with `data=[Example(...)]` and `upload_results=False` (logs a beta warning) · **JS** failed without credentials: `Received status [401]: Unauthorized` | differs |

## MCP & the AI SDK (Day 26)

| Finding | Evidence | Lang |
|---|---|---|
| Raw MCP round-trip | `tools/list`, `tools/call`, `resources/list`, `resources/read`, `prompts/list`, `prompts/get` all verified against a local stdio server | both |
| Tool schemas on the wire | **JS** Zod → draft-07 JSON Schema with descriptions · **PY** type hints → schema titled `search_notesArguments` | differs |
| Structured results | PY FastMCP also returned `structuredContent: {"result": …}` | PY |
| Adapter config | **JS** `new MultiServerMCPClient({ mcpServers: { name: { transport: "stdio", command, args } } })` · **PY** `MultiServerMCPClient({"name": {"command", "args", "transport"}})`; tool names are **not** prefixed | differs |
| ⚠️ Adapter tool results | **JS** returns a **string** · **PY** returns a **list of content blocks**; **PY** tools are async-only — sync `invoke` raises `NotImplementedError: StructuredTool does not support sync invocation.` | differs |
| Resource helpers | **JS** `mcp.readResource(server, uri)` → `[{uri, text}]` · **PY** `client.get_resources(server, uris=[…])` → `list[Blob]`, read with `.as_string()` | differs |
| ⚠️ Handler exceptions leak | an uncaught exception becomes an **error result containing the raw text**; PY prefixes it: `Error executing tool boom: postgres://notes_rw@db-internal refused`. `ToolError` behaves the same way with your message | both |
| stdout pollution | stray `console.log`/`print` produced client parse errors (`Unexpected token 's', "starting server..." is not valid JSON`) but the session **survived** in both SDKs — it's unreliable, not instantly fatal | both |
| ⚠️ AI SDK `generateText` default | with tools and **no** `stopWhen`: 1 step, `text: ""`, `finishReason: "tool-calls"`, the tool **did** run. With `stopWhen: stepCountIs(5)`: 2 steps, correct answer; the 2nd call's prompt was `[user, assistant, tool]` | JS |
| AI SDK usage | `usage` and `totalUsage` both reported the two-step total (250 in / 30 out / 280) | JS |
| AI SDK structured output | `Output.object({ schema })` and `generateObject({ schema })` both parsed | JS |
| AI SDK streaming | `textStream` yields deltas; `toUIMessageStreamResponse()` → `text/event-stream` with `data: {"type":"start"}`, `text-delta`, `finish-step`… | JS |
| `ToolLoopAgent` | loops through a tool call and answers (2 steps) with **no** `stopWhen` set | JS |
| AI SDK + MCP | `createMCPClient` + `Experimental_StdioMCPTransport` (from `@ai-sdk/mcp/mcp-stdio`) drove our MCP server; the tool result is the raw MCP object `{"content":[…],"isError":false}` | JS |

## Deployment (Day 27)

| Finding | Evidence | Lang |
|---|---|---|
| LangGraph server end-to-end | ran `langgraph dev` and drove it from **both** SDKs: `assistants.search`, `threads.create`, `runs.wait` (interrupt surfaced in `__interrupt__`), `threads.get_state` (`next: ['gate']`), resume via `Command(resume=…)`, `threads.get_history` (4), `runs.stream` (events `metadata, values, updates…`), `runs.create` → `pending` → `runs.join` → `success`, and threads accumulating messages | both |
| ⚠️ Server rejects a checkpointer-compiled graph | `ValueError: Heads up! Your graph 'graph' … includes a custom checkpointer (type InMemorySaver). With LangGraph API, persistence is handled automatically by the platform … please set the \`POSTGRES_URI\` environment variable.` | both |
| Dockerfile generation | `langgraph dockerfile Dockerfile` works offline; builds on `langchain/langgraph-api:3.11` and registers graphs via `LANGSERVE_GRAPHS` | — |
| 🪟 Windows: PY server | needs `colorama` (`ConsoleRenderer with colors=True on Windows requires the colorama package installed`) and `PYTHONUTF8=1` (CLI emoji output) | PY |
| 🪟 Windows: JS CLI | `langgraphjs dev` failed on Node 24: `node.exe: bad option: --clear-screen=false`. The JS **client** was verified against the Python server instead | JS |
| Self-hosted start/poll/resume | identical results in both languages: `202` → `running` → `interrupted` with the pending payload → resume → `success`; a run requested under the wrong thread → `404` | both |
| Two instances, in-memory state | round-robin across two `MemorySaver` graphs: turn 1 "seen 1", turn 2 "seen 1" (forgot), turn 3 "seen 3" | both |
| Postgres APIs (signatures, no DB) | **PY** `PostgresSaver.from_conn_string` is a context manager; `.setup()`, `.delete_thread()`, `AsyncPostgresSaver`, `PostgresStore` · **JS** `fromConnString` returns the saver with `setup()`, `deleteThread()`, `end()`; store at `@langchain/langgraph-checkpoint-postgres/store` | differs |

## Corrections made to earlier weeks

| What was wrong | Correct behaviour | Fixed in |
|---|---|---|
| `createAgent({ prompt })` / `create_agent(prompt=…)` | **JS silently ignores** `prompt` (the agent runs with no system message); **PY raises** `TypeError: create_agent() got an unexpected keyword argument 'prompt'`. The option is `systemPrompt` / `system_prompt` | Day 16 (6 places + a ⚠️ note) |
| "`ToolNode` catches tool errors and returns them as content" | True in **JS** only; PY re-raises unless `handle_tool_errors` is set | Day 17 (3 passages + a translation-table row) |
| Day 09 loader import paths | moved from `@langchain/classic/document_loaders/fs/pdf` to `@langchain/community/document_loaders/*` | Day 09 + RAG cheatsheet |
| Week 1 message imports | switched to `@langchain/core/messages` / `langchain_core.messages` | Days 04, 05, 07 |
