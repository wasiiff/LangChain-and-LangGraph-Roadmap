# 03 — Verified findings

Every technical claim in this book that was established by **running code**, not by recall.
Verified against the versions in [04-versions-and-environment.md](04-versions-and-environment.md)
during September–October 2026.

**Use this file two ways:** before changing a technical claim, check what was measured; after
re-verifying anything, update the row and note the version.

Legend: **JS** = JavaScript only · **PY** = Python only · **both** = same in both languages.

---

## Week 0 (Days 0A–0C, and the new Day 03) — verified October 2026

### Toolkit and environment (Day 0A)

Versions: Node 24.15.0, npm 11.12.1, Python 3.14.4, pip 26.0.1, git 2.53.0.windows.3,
PowerShell 7.6.6 / 5.1.26100, dotenv 18.0.6 (17.4.2 also checked), python-dotenv 1.2.4.

| Finding | Evidence | Lang |
|---|---|---|
| 🚨 npm 11 `npm init -y` writes `"type": "commonjs"` | you must **change** the line, not add one: `npm pkg set type=module` | JS |
| `import` in a commonjs project | `SyntaxError: Cannot use import statement outside a module` (after a "Failed to load the ES module" warning) | JS |
| No `"type"` field on Node 24 | runs, with `[MODULE_TYPELESS_PACKAGE_JSON] Warning … Reparsing as ES module` | JS |
| `require` in ESM | `ReferenceError: require is not defined in ES module scope, you can use import instead` | JS |
| Missing package | JS `Error [ERR_MODULE_NOT_FOUND]: Cannot find package 'dotenv'` · PY `ModuleNotFoundError: No module named 'dotenv'` | differs |
| dotenv 18 logging | `import "dotenv/config"` is silent; `dotenv.config()` prints `◇ injected env (1) from .env` to stderr | JS |
| Where `.env` is searched | JS dotenv: current folder only · python-dotenv `load_dotenv()`: script folder, then upwards | differs |
| Override | a shell variable beats `.env` in both; `override: true` / `override=True` flips it | both |
| PowerShell 5.1 `"X=y" > .env` | writes UTF-16 LE → JS key silently missing; PY `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff`. PowerShell 7 writes UTF-8 | differs |
| Node built-in env loading | `node --env-file=.env` and `process.loadEnvFile()` work; missing file → `missing.env: not found`, exit 9; `--env-file-if-exists` continues | JS |
| Activate.ps1 under Restricted policy | `…cannot be loaded because running scripts is disabled on this system` | PY |
| git and secrets | `.gitignore` hides an untracked `.env`; `git add .env` refused; a `.env` committed earlier stays tracked; after `git rm --cached` the key is still in history (`git show HEAD~1:.env`) | — |
| Stack traces | Node: error type at the top, newest call first · Python: error type on the last line, newest call last | differs |
### Programming for AI (Day 0B) and choosing a model (Day 03)

Versions: zod 4.6.5, dotenv 18.0.6, @langchain/core 1.2.17, pydantic 2.13.5, httpx 0.28.1,
python-dotenv 1.2.4, langchain-core 1.6.7, npm 11.12.1.

| Finding | Evidence | Lang |
|---|---|---|
| No `"type"` field → Node 24 guesses ESM | runs with a `MODULE_TYPELESS_PACKAGE_JSON` warning; "import throws" is only true for `"type": "commonjs"` / `.cjs` | JS |
| Top-level await in CJS | `SyntaxError: await is only valid in async functions and the top level bodies of modules` | JS |
| TS annotation in a `.js` file | `SyntaxError: Missing initializer in const declaration` | JS |
| ⚠️ dotenv import order | a late `import "dotenv/config"` still runs before the body (imports are hoisted). The real bug: a module that reads `process.env` at import time, imported before dotenv → `undefined` | JS |
| Un-awaited call | JS `Promise { <pending> }`, `.content` is `undefined`, template gives `[object Promise]` · PY `AttributeError: 'coroutine' object has no attribute 'content'` | differs |
| `forEach(async …)` | `done` prints before the callbacks finish | JS |
| `Promise.all` vs `allSettled` | `all` throws on one failure; `allSettled` → `['fulfilled','rejected','fulfilled']` | JS |
| JSON types | JS: Date → ISO string, `undefined` dropped, `NaN` → `null` · PY: datetime → `TypeError: Object of type datetime is not JSON serializable` | differs |
| Big integers | `12345678901234567890` → JS `12345678901234567000`; PY exact | differs |
| `json.dumps("Zürich")` | `"Zürich"`; `ensure_ascii=False` keeps `ü` | PY |
| ⚠️ Lax validation | `{"ok":"yes","n":"40"}`: Zod rejects; Pydantic accepts `ok=True n=40`; `strict=True` rejects | differs |
| JSON Schema export | Zod `toJSONSchema` marks a defaulted field required and inlines nested objects; Pydantic omits it from `required` and uses `$defs` | differs |
| fetch body | an object body is sent as `[object Object]`; a string body defaults to `text/plain;charset=UTF-8` | JS |
| ⚠️ No raise on 4xx/5xx | fetch 401 → later `TypeError … reading '0'`; httpx → `KeyError: 'choices'`; `raise_for_status()` → `HTTPStatusError: Client error '401 Unauthorized'` | both |
| Body read twice | fetch: `TypeError: Body is unusable: Body has already been read`; httpx fine | differs |
| Connection refused | fetch `TypeError: fetch failed` (cause `ECONNREFUSED`); httpx `ConnectError` | both |
| Blocking in asyncio | 3 tasks with `time.sleep(0.3)` → 0.92 s; with `asyncio.sleep` → 0.31 s | PY |
| Sync vs async LangChain | JS `invoke` always returns a Promise; PY `invoke` → AIMessage, `ainvoke` → coroutine | differs |
| Day 03 eval harness | exact-match grading 4/5 and 2/5 vs normalised 5/5 and 3/5 — grading rule changes the winner | both |
### Maths for AI (Day 0C)

Versions: Node 24.15.0, Python 3.14.4, numpy 2.4.4 (optional).

| Finding | Evidence | Lang |
|---|---|---|
| Softmax of `[2,1,0]` | `0.665 0.245 0.090`; sum prints `0.9999999999999999` | both |
| Temperature on logits `[5,2.5,2,1,-2]` | T=0.7: 95.7/2.7/1.3/0.3/0.0 % · T=1: 86.9/7.1/4.3/1.6/0.1 % · T=2: 59.7/17.1/13.3/8.1/1.8 % | both |
| Shared seeded LCG (`a=1664525, c=1013904223, m=2^32`) | identical sequence in JS and Python; seed 42 starts `0.2523 0.0881 0.5773`; largest intermediate < 2^53 | both |
| `exp` overflow | `exp(710)`: JS `Infinity`, PY `OverflowError: math range error` | differs |
| Naive softmax of `[1000,999,998]` | JS `[NaN,NaN,NaN]`; PY `OverflowError: math range error` → fix: subtract the max | differs |
| Cosine with a zero vector | JS `NaN`; PY 3.14 `ZeroDivisionError: division by zero` (3.13: `float division by zero`) | differs |
| Dot product, different lengths | JS long·short `NaN`, short·long `5` (silent); PY `zip` silent `5`; `zip(strict=True)` raises `ValueError` | differs |
| JS `.sort()` on numbers | `[10,9,100,25]` → `[10,100,25,9]` (text order) | JS |
| Underflow | 0.01 multiplied 400× → `0`; sum of logs → `-1842.07` | both |
| Top-p without renormalising | removed token still picked 938/10,000 (seed 3) | both |
| Percentiles, 20 latencies | nearest-rank p50 1.1, p95 3.1; numpy default p95 `4.445…`, `method="inverted_cdf"` 3.1 | PY |
| Sample size (10,000 sims, seed 2026) | 5 tests at true 0.8 accuracy: p5–p95 0.40–1.00, all pass 32.7 %; 100 tests: 0.73–0.86 | both |
| 10,000 × 768 dot products | pure JS ~24 ms · pure PY ~1,470 ms · numpy ~4–5 ms (this machine) | both |

## Import paths and packaging (Weeks 1–2)

| Finding | Detail | Day |
|---|---|---|
| Canonical message imports | `@langchain/core/messages` / `langchain_core.messages` work on 0.3 **and** 1.x; `from "langchain"` / `langchain.messages` also work on 1.x but are not portable | 04 |
| 🚨 Legacy components moved in 1.x | chains, legacy retrievers, memory, `MemoryVectorStore` → `@langchain/classic/*` and `langchain_classic.*`. Most online tutorials import paths that no longer exist | 08 |
| Loader paths | `@langchain/classic/document_loaders` exposes only `base`, `fs/buffer`, `fs/directory`, `fs/json`, `fs/multi_file`, `fs/text`. PDF/CSV/web loaders live in `@langchain/community/document_loaders/*` (otherwise `ERR_PACKAGE_PATH_NOT_EXPORTED`) | 09 |
| Vector store asymmetry | **PY** `InMemoryVectorStore` ships in `langchain-core`; Chroma persists to a directory with no server. **JS** needs `@langchain/classic` and a running Chroma | 11 |
| Embeddings providers | Groq has **no** embeddings endpoint → Ollama `nomic-embed-text` or Google `gemini-embedding-2` (3072 dims, normalised; `outputDimensionality` / `output_dimensionality` 768 works; query and document embeddings identical). The `models/` prefix is optional in `langchain-google-genai` 4.4.0 and stripped by the JS class (re-verified live Oct 2026; the old "PY needs the prefix" note is out of date) | 10 |
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
| Recursion limit | **JS** default 25 supersteps · **PY** default **10007** (`DEFAULT_RECURSION_LIMIT`, env `LANGGRAPH_DEFAULT_RECURSION_LIMIT`, langgraph 1.2.x — corrected Oct 2026; a 100-step loop completes with default config) → `GraphRecursionError: Recursion limit of N reached without hitting a stop condition` | differs |
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
| `default` must be a factory | langgraph JS 1.4.20: `default: []` throws `TypeError: initialValueFactory is not a function` at `Annotation.Root` (corrected Oct 2026 — it used to be described as a leak). A real leak: `default: () => SHARED` + a mutating reducer → second run `[ 'hi', 'hi' ]` | JS |

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

## Weeks 5–6 (Days 29–40) — verified October 2026

### Open & local models (Day 29)

Machine: i5-8265U, 4 cores, 7.8 GB RAM, CPU only. Model `HuggingFaceTB/SmolLM2-135M-Instruct` (134,515,008 params). transformers 5.19.0, huggingface_hub 1.33.0, @huggingface/transformers 4.3.1.

| Finding | Evidence | Lang |
|---|---|---|
| File size vs params × bytes | safetensors bf16 269.1 MB (arithmetic 269.0) · ONNX fp32 540.3 · q8 137.1 · **q4 182.1 MB** (arithmetic 67.3 — the embedding table stays fp32; only matmuls are 4-bit) | both |
| GGUF Q4_K_M is a mix | 8B model: 4.90 bits per parameter; SmolLM2 Q4_K_M averaged 6.17 (narrow tensors get Q5_0/Q8_0) | — |
| transformers 5.x default dtype | `from_pretrained` without `dtype` loads **bf16**; `torch_dtype=` warns it is deprecated. bf16 was slower than fp32 on this CPU | PY |
| No chat template | PY plain text → `''`; JS plain string → prompt echoed back | differs |
| `generate()` default length | PY 20 new tokens (with a `max_length` warning) · Transformers.js pipeline `max_new_tokens` 256 | differs |
| `ChatHuggingFace` | applies the chat template; `usage_metadata` is `None`; without `return_full_text: False` the reply starts with `<\|im_start\|>system…` | PY |
| Transformers.js unknown dtype | `"int4"` silently falls back to the fp32 file | JS |
| `ChatOllama` with no server | PY `httpx.ConnectError: [WinError 10061]` · JS `TypeError: fetch failed` | differs |

### Inference & serving (Day 30)

langchain-openai 1.6.7, openai 3.26.0 · @langchain/openai 1.6.2, openai 7.30.0 · fastapi 0.142.2, uvicorn 0.54.0.

| Finding | Evidence | Lang |
|---|---|---|
| Prefill vs decode (fp32, 32 new tokens) | TTFT 698 / 1,414 / 4,160 ms for 34 / 248 / 878 prompt tokens; decode 8.6 / 8.4 / 5.6 tok/s | PY |
| `use_cache=False` | 5.9× slower for 16 tokens, 8.8× for 64; identical output | PY |
| KV cache size | 45.0 KB/token in fp32 = 2 × 30 layers × 3 KV heads × 64 × 4 bytes (measured 25.1 MB for 8 × 68 positions) | PY |
| Batching 1 / 4 / 8 | total throughput 3.7–4.2× higher at 8; each request about half as fast | PY |
| Default `padding_side` is `right` | batched short prompt answered `'\n'`; `padding_side = "left"` fixes it | PY |
| Speculative decoding on CPU | `assistant_model` 0.53–0.88× (slower) on open questions, 1.17× on copy-heavy; `prompt_lookup_num_tokens=10` 2.97× on copy-heavy | PY |
| Base URL without `/v1` | PY `OpenAIModelNotFoundError: Error code: 404` · JS `Error: 404 {"detail":"Not Found"}` | both |
| ⚠️ Retry defaults on a dead server | JS `ChatOpenAI` maxRetries 6 → **93 s**; PY 2 retries → 7.4 s; with 0 retries JS 0.0 s, PY 2.0 s (Windows) | differs |
| Server ignores `stream: true` | PY `ValueError: No generation chunks were returned` · JS 0 chunks, **no error** | differs |
| Abandoned requests | a server keeps generating for a disconnected client unless it is `async` and checks for disconnects (StoppingCriteria) | PY |
| FastAPI `@app.on_event` | DeprecationWarning — use `lifespan` | PY |

### Fine-tuning (Day 31)

peft 0.21.2, torch 2.14.1+cpu. SmolLM2-135M, LoRA r8 α16 on q,v, lr 1e-3, batch 8, 18 steps.

| Finding | Evidence |
|---|---|
| Trainable parameters | q,v: r4 230,400 · r8 460,800 (0.34 %) · r16 921,600 — equals `layers × Σ r(d_in + d_out)` |
| Fresh LoRA changes nothing | max logit diff 0.0 (`lora_B` starts at zero) |
| Training run | loss 3.16 → 0.75, val 2.96 → 1.10; 71 s on a quiet CPU |
| Habit on 16 held-out questions | base 0/16 · base + format prompt 0/16 · adapter **13/16** |
| Adapter vs model | adapter 1.86 MB; merged output identical (max logit diff 3e-5) |
| Wrong chat template in training | lower training loss, habit **0/16** when served |
| pad token == eos token (SmolLM2) | masking padding by id teaches the model never to stop |
| lr 5e-2 | loss 3.16 → 19.8 in 6 steps, output garbage (no NaN) |
| Overfitting (8 examples, 40 epochs) | val minimum at epoch 16; train 0.03; habit 10/16 |

### Dataset engineering (Day 32)

| Finding | Evidence | Lang |
|---|---|---|
| Normalise before hashing | raw hash removed 1 duplicate; NFKC + whitespace + lower-case removed 3 | both |
| Near-duplicates (5-char shingles + Jaccard) | planted copies 0.669–0.731, closest real pair 0.183; threshold 0.5 removes exactly the plants | both |
| JS regex `g` flag with `.test()` | `[true, true, false, true]` on four matching strings (`lastIndex` state) | JS |
| Regex PII limits | misses "ayesha dot khan at example dot com"; flags dates and ISBNs as phone numbers | both |
| Record split vs group split | near-duplicate leak in 79 of 100 seeds vs 0 | both |
| Cohen's kappa | 0.400 (matches scikit-learn); one-label case: JS `NaN`, PY `ZeroDivisionError` | both |
| Byte-identical JSONL across languages | PY needs `json.dumps(r, ensure_ascii=False, separators=(",", ":"))` and `newline="\n"` on Windows | both |
| Lower-casing | `"Straße".casefold()` → `strasse`; `.lower()` / JS `toLowerCase()` → `straße` | differs |

### Multimodal (Day 33)

JS @langchain/core 1.2.17, @huggingface/transformers 4.3.1, @langchain/google-genai 2.3.2 · PY transformers 5.19.0, langchain-google-genai 4.4.0. Models: SmolVLM-256M-Instruct, whisper-tiny.en.

| Finding | Evidence | Lang |
|---|---|---|
| Standard image block keys | JS `{type:"image", data, mimeType}` · PY `{"type":"image","base64","mime_type"}`; `.contentBlocks` / `.content_blocks` normalise v1, `image_url` data-URL and 0.3 `source_type` forms | differs |
| Gemini request shape (captured, no live call) | v1 block and data URL both become `parts:[{text},{inlineData:{mimeType,data}}]` | both |
| `data:` prefix inside the base64 field | JS sends it unchanged · PY raises `binascii.Error: Invalid base64-encoded string …` | differs |
| `.content` on a list-content reply | JS `TypeError: reply.content.toUpperCase is not a function` · PY `AttributeError: 'list' object has no attribute 'upper'`; use `.text` | both |
| Base64 growth | 3,739-byte PNG → 4,988 characters | both |
| SmolVLM image tokens | 64 per tile with splitting off; 832–1,088 with splitting on (identical JS/PY) | both |
| Whisper and sample rate | 44.1 kHz audio passed as 16 kHz → fluent nonsense, no error; PY pipeline with a file path needs ffmpeg, with a 44.1k dict needs torchaudio | both |
| Image sent to a text-only model | JS chat template pastes the base64 as text (3,864 tokens) and the model invents a description · PY `TypeError: can only concatenate str (not "list") to str` | differs |
| Windows SAPI TTS WAV | `fmt` chunk is 18 bytes, so audio data starts at byte 46, not 44 | — |
| Voice pipeline, two turns | JS ~3.0 s, PY ~3.9–4.5 s total (STT + LLM + TTS on CPU) | both |

### Cost & latency (Day 34)

Versions: JS `langchain` 1.5.15, `@langchain/core` 1.2.17, `@langchain/groq` 1.3.1 · PY `langchain` 1.4.3, `langchain-core` 1.6.7, `langchain-groq` 1.1.3.

| Finding | Evidence | Lang |
|---|---|---|
| Exact cache misses on | one changed letter, a trailing space, a different temperature, a `stop` option | both |
| 🚨 JS `ChatGroq` cache key has no model name or temperature | key `_model:"base_chat_model",_type:"groq"` for every instance; with a shared cache a 70B model returned the 8B answer (`big model got: SMALL MODEL ANSWER`). Give each model its own `new InMemoryCache()` | JS |
| PY `ChatGroq` cache key | includes `model_name`, temperature, `max_retries`, `n`, `service_tier` | PY |
| Usage on a cache hit | JS zeros all token counts (and, because the same message object is returned, zeroes the first call's usage too) · PY keeps counts and adds `'total_cost': 0` | differs |
| `cache: true` (JS) | uses the shared `InMemoryCache.global()` | JS |
| `InMemoryCache(maxsize=2)` | evicts the oldest; JS `InMemoryCache` has no size limit | PY |
| Message ids not in the key | two `HumanMessage("hi")` with different ids → 1 call | both |
| `batch` with no cap | JS ran 40/40 at once · PY peaked at 12 (thread-pool default, 8-core machine) | differs |
| Simulated 429 (4 in flight allowed) | no cap: 8/12 failed; `maxConcurrency` 4: 0 failed | both |
| `ChatGroq` output cap on the wire | JS `maxTokens` → `max_completion_tokens` · PY `max_tokens` → `max_tokens`; temperature default 0.7 in both | differs |
| Semantic cache (word-count stand-in embeddings) | paraphrase 0.882 vs wrong question 0.857 → wrong hit at threshold 0.8; reversed °C/°F question scores 1.000 | both |

### AI security (Day 35)

Versions: JS langchain 1.5.15, @langchain/core 1.2.17, @langchain/langgraph 1.4.20, sanitize-html 2.18.0 · PY langchain 1.4.3, langgraph 1.2.14, safetensors 0.8.0, nh3 0.3.7, torch 2.14.1+cpu.

| Finding | Evidence | Lang |
|---|---|---|
| Red-team harness, worst-case scripted model | `attacks blocked: vulnerable 0/11 · hardened 10/11`, benign 2/2 both; identical in JS and Python | both |
| Adaptive leak beats a canary | spaced-out output `Y o u   a r e …` passed `includes(CANARY)` | both |
| Spotlighting vs a worst-case model | 0 of 11 blocks credited to it — it helps real models, it is not a control | both |
| Weak domain checks | `endsWith("school.example")` and `split("@")[1]` both bypassed | both |
| HITL middleware order | runs after the model, before `wrapToolCall` — without a `when` predicate the human is asked about actions policy would refuse | both |
| HITL reject message | JS: exactly your text · PY: ``User rejected the tool call for `send_email` with reason: …`` | differs |
| Pickle runs code on load | `!!! code ran while LOADING model.pkl`; `pickletools` reveals it without loading | PY |
| `torch.load` default (2.14.1) | `UnpicklingError … Unsupported global: GLOBAL print was not an allowed global by default`; `weights_only=False` runs the payload | PY |
| npm 11.12.1 `postinstall` | runs silently by default; `--ignore-scripts` skips it | JS |

### Agent patterns and context (Day 36) — and two corrections

Versions: JS @langchain/langgraph 1.4.20, deepagents 1.14.2 · PY langgraph 1.2.14, deepagents 0.7.22.

| Finding | Evidence | Lang |
|---|---|---|
| ⚠️ Default recursion limit differs | **JS 25** (`GraphRecursionError: Recursion limit of 25 reached…`). **PY** `DEFAULT_RECURSION_LIMIT = int(getenv("LANGGRAPH_DEFAULT_RECURSION_LIMIT", "10007"))` in langgraph 1.2.x — a 100-step loop completes with default config (lead re-checked on 1.2.14) | differs |
| ⚠️ Parallel writes to a no-reducer channel **raise** | JS `InvalidUpdateError: Invalid update for channel "v" with values ["A","B"]: LastValue can only receive one value per step.` · PY `InvalidUpdateError: At key 'v': Can receive only one value per step. Use an Annotated key to handle multiple values.` — same for static-edge fan-out and `Send` (lead re-checked both) | both |
| Node name equal to a state key | JS throws `… is already being used as a state attribute (a.k.a. a channel), cannot also be used as a node name.`; PY accepts | differs |
| Unknown route label | JS `Error: Branch condition returned unknown or null destination` · PY `KeyError: 'history'` | differs |
| Tool-result clearing | JS `contextEditingMiddleware` writes `[cleared]` into state · PY `ClearToolUsesEdit` edits only the request | differs |
| deepagents built-ins | `ls read_file write_file edit_file delete glob grep task`; `write_todos` only with `TodoListMiddleware` | both |

### Advanced retrieval (Day 37)

Versions: JS @langchain/core 1.2.17, zod 4.6.5, `node:sqlite` (Node 24.15.0, SQLite 3.51.3) · PY langchain-core 1.6.7, pydantic 2.13.5, sqlite3 (SQLite 3.50.4).

| Finding | Evidence | Lang |
|---|---|---|
| Base `withStructuredOutput` doesn't validate against Zod | relation `"LIKES"` returned unchanged; `Triples.parse` → `ZodError: Invalid option…` · PY `with_structured_output` raises `ValidationError … literal_error` | differs |
| Scripted model + base `withStructuredOutput` (JS) | must return `AIMessageChunk`, else `Error: Input is not an AIMessageChunk.` | JS |
| `node:sqlite` on Node 24.15 | built in, no experimental warning; has `setAuthorizer`, `iterate` | JS |
| Read-only connection | writes fail `attempt to write a readonly database`; reads (incl. sensitive columns) still succeed | both |
| SQLite authorizer | denies per table/column/function: `access to students.email is prohibited`, `not authorized to use function: load_extension`; `LIKE` arrives upper-case | both |
| Two statements in one string | Node `prepare()` silently runs only the first · PY `execute()` → `ProgrammingError: You can only execute one statement at a time.` | differs |
| `WITH x AS (SELECT 1) DELETE …` | passes a "starts with SELECT/WITH" text check — must be stopped by read-only or the authorizer | both |
| Real embeddings on multi-hop notes | MiniLM-L6-v2: the second-hop note ranked 6th and 8th of 9 → needs k=8 | JS |

### Emerging agents (Day 38)

playwright 1.63.0 (both) · @a2a-js/sdk 1.3.0 · a2a-sdk 1.2.2.

| Finding | Evidence | Lang |
|---|---|---|
| Page views | HTML 1,162 chars · `ariaSnapshot()` 316 chars · screenshot 11,505 bytes | both |
| `getByLabel` survives an id rename; a renamed label times out | `locator.fill: Timeout 2000ms exceeded.` (default 30 s) | both |
| `context.route` as an allowlist | `abort("blockedbyclient")` → `net::ERR_BLOCKED_BY_CLIENT` | both |
| Hidden text | `display:none` absent from the ARIA tree and `innerText`, present in `textContent` | both |
| A2A v1.0 | no `A2A-Version` header → `-32009 … version '0.3' is not supported`; old `message/send` → `-32601` (both with HTTP 200) | both |
| `pip install a2a-sdk` alone | `ModuleNotFoundError: No module named 'sse_starlette'` — use `a2a-sdk[http-server]` | PY |
| Sync Playwright in asyncio | `It looks like you are using Playwright Sync API inside the asyncio loop.` | PY |

### AI product engineering (Day 39)

| Finding | Evidence | Lang |
|---|---|---|
| Own root run id | `invoke(x, {runId})` / `{"run_id": id}` becomes the root run id for every child run | both |
| Sticky SHA-256 bucketing | identical buckets in JS and PY; 10 % → 50 % ramp keeps every early B user in B | both |
| Two-proportion z-test | 300/500 vs 345/500 → z 2.974, p 0.0029 | both |
| Peeking (1,000 A/A tests) | 4.1 % false winners with one look vs 22.1 % with 20 looks | both |
| Windows `localhost` | PY server ~2.2 s per request via `localhost`, 30 ms via `127.0.0.1` (cause not proven) | PY |

### Final capstone (Day 40)

| Finding | Evidence | Lang |
|---|---|---|
| Release gate | evals 45/45, red team 5/5, ledger 55/55, exit code 0; any failed check → exit 1 | both |
| Flaky latency gate | a single p95 failed 2 of 6 runs on a busy machine; warm-up + median of five rounds' p95 passed 10 of 10 | both |
| Token estimate drift | PY `str(tool_calls)` vs JS `JSON.stringify` changed cost per request; compact `json.dumps` made them match | differs |

## Live providers and model names — measured 7 October 2026 (owner's keys)

The first live calls in the course's history. `@langchain/groq` 1.3.1, `langchain-groq` 1.1.3,
`groq-sdk` 1.6.0, `@langchain/google-genai` 2.3.2, `langchain-google-genai` 4.4.0.

| Finding | Evidence | Lang |
|---|---|---|
| 🚨 Old Groq defaults are gone for this account | `llama-3.3-70b-versatile` and `llama-3.1-8b-instant` → `404 The model … does not exist or you do not have access to it.` (`model_not_found`), although Groq's docs page still lists them. `GET /openai/v1/models` lists `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `qwen/qwen3.8-27b` (preview), whisper, guard and TTS models | — |
| New defaults work end to end | `openai/gpt-oss-120b` / `-20b`: `invoke`, `stream`, `batch`, `bindTools` / `bind_tools`, `withStructuredOutput` (functionCalling, jsonMode, jsonSchema), `initChatModel("groq:openai/gpt-oss-120b")`, raw `json_object` and `json_schema` modes | both |
| ⚠️ Reasoning eats `max_tokens` | `maxTokens: 20` → `text: ""`, `finish_reason: "length"` on both GPT-OSS models | both |
| Where the reasoning goes | PY `additional_kwargs["reasoning_content"]` + `usage_metadata.output_token_details.reasoning` (e.g. 32) · JS `@langchain/groq`: not exposed · raw SDK `message.reasoning` | differs |
| `reasoningEffort: "low"` | "2+2" → `4` with 16 output tokens (6 of them reasoning) | both |
| Hidden prompt overhead | "Hi" → 72 `prompt_tokens`; with a one-line system message 78 | — |
| ⚠️ Text protocols with `stop` | gpt-oss-120b ignores a Thought/Action format and answers directly; gpt-oss-20b returns `""`; `qwen/qwen3.8-27b` follows it and stops at `Observation:` | — |
| ⚠️ Unsupported on Groq models | `logprobs` → `400 \`logprobs\` is not supported with this model`; `n: 2` → `400 'n' : number must be at most 1` (gpt-oss and qwen) | — |
| PY `ChatGroq().max_retries` | 2 | PY |
| Gemini for new users | `gemini-2.5-flash` → `404 … no longer available to new users. Please update your code to use models/gemini-3.8-flash` (an older key still works) | — |
| Gemini load | `gemini-3.5-flash`, `3.6-flash`, `3.8-flash`, `flash-latest` intermittently `503 This model is currently experiencing high demand`; LangChain JS retries, so a call can appear to hang (measured 69–88 s before success, or a final 503). `gemini-3.1-flash-lite` answered in 0.9 s; `gemini-flash-latest` once gave `429 … exceeded your current quota` | — |
| Google embeddings | `text-embedding-004` → `404 … not found for API version v1beta`; `gemini-embedding-001` and `gemini-embedding-2` → **3072** dims by default (was 768); `gemini-embedding-2` has no `task_type` | — |

### What the migration measured (7–8 October 2026, live with the owner's keys unless marked)

| Finding | Evidence | Lang |
|---|---|---|
| ⚠️ Default (tool-calling) structured output on GPT-OSS is flaky | PY `with_structured_output(S)`: `400 Tool choice is required, but model did not call a tool` (`tool_use_failed`) — "hi" 3/3, Day 19 classifier 4/4, a yes/no grader on 20B; JS default answered the same "hi". **Use JSON-schema mode**: JS `{ method: "jsonSchema" }` (always sends `strict: true`), PY `method="json_schema", strict=True` (non-strict once returned the schema itself → `OutputParserException`) | both |
| `include_raw=True` / `includeRaw: true` | catches parse failures only — the provider's 400 `BadRequestError` still raises; with JSON-schema mode `raw.usage_metadata` is populated | both |
| `withStructuredOutput` after `withRetry().withFallbacks()` | JS `TypeError: resilient.withStructuredOutput is not a function` · PY `AttributeError: 'RunnableRetry' object has no attribute 'with_structured_output'` — add structured output per model first, then retry/fallbacks | both |
| 🚨 JS never retries Groq 429s | `@langchain/core` 1.2.17 classifies them `rateLimitType: 'stop', rateLimitReason: 'quota_message'` (its quota patterns include `/billing/i`, and Groq's 429 text links to the billing page) → fails immediately despite `maxRetries` 6. PY's Groq client retries (2) | JS |
| JS `RunnableWithFallbacks` when every option fails | throws the **primary's** error (Groq 429 shown while Gemini was returning 503) | JS |
| JS `.stream()` with `@langchain/groq` 1.3.1 | `usage_metadata` is `undefined`; counts are in `response_metadata.usage`, whose `total_tokens` is doubled by `concat` | JS |
| JS `initChatModel(undefined, { configurableFields: ["model"] })` | `TypeError: Cannot read properties of undefined (reading 'startsWith')` (langchain 1.5.15); pass a default model + `modelProvider: "groq"`; per call use the plain id | JS |
| Reasoning streams start empty | JS 29 of 41 chunks empty; PY 61 chunks, 26 empty `content`, 23 with `reasoning_content`, first text in chunk 25 | both |
| Small budgets | `max_tokens: 50` → `""` (47 of 50 tokens reasoning); a two-sentence answer at 200 used 188 (112 reasoning) | both |
| Prompt overhead vs local count | "Hi": `gpt-tokenizer` 4.0.0 (`o200k_base`) and `tiktoken` count 1; the API bills 72 `prompt_tokens` | both |
| Groq free-tier limits (from `x-ratelimit-*` headers) | gpt-oss-120b / -20b: 30 requests/min, 8,000 tokens/min, 1,000 requests/day per model; a single over-large request → `413 Request too large … TPM: Limit 8000`; `qwen/qwen3.8-27b`: 1,000 output tokens/min (checked against `max_tokens`) | — |
| Groq prices, models page, 7 Oct 2026 | gpt-oss-120b $0.15 / $0.60 per 1M in/out · gpt-oss-20b $0.075 / $0.30 · qwen3.8-27b (preview) $0.80 / $4.00; Llama 3.3 70B and 3.1 8B now "Enterprise / Contact Sales" | — |
| GPT-OSS skips trivial tools | "What is 2 + 3?" and "weather in Atlantis" answered without calling the tool — ask explicitly ("Use the add tool") or use inputs that need it | both |
| GPT-OSS citations | wrote `【1】` instead of `[1]` in 2 of 4 RAG answers | both |
| GPT-OSS and ungrounded prompts | refused ("I'm sorry, but I can't help with that.") rather than inventing an address | PY |
| `LLMChainExtractor` on the 20B model | prefixes its output with `Extracted relevant parts:` | PY |
| Qwen text ReAct | `qwen/qwen3.8-27b` followed Thought/Action/Observation and finished the Day 02 and Day 16 agents (3–7 steps); once it stopped after `Action:` even without `stop`; returns no reasoning field | both |
| PY `trim_messages(token_counter=ChatGroq)` | `UserWarning: Using fallback GPT-2 tokenizer…`, downloads gpt2 (needs `transformers`); one turn took 82 s | PY |
| `gemini-embedding-2` via LangChain | 3072 dims, normalised; 768 via `outputDimensionality` / `output_dimensionality`; query and document embeddings identical (cosine 1.000000); `models/` prefix optional | both |
| AI SDK + Groq | `generateText` + tool + `stopWhen` on `groq("openai/gpt-oss-120b")`: 2 steps, reports `reasoningTokens`; a 429 ends as `AI_RetryError` (ai 7.0.130, @ai-sdk/groq 4.0.57) | JS |
| LangGraph: node name = channel name | JS 1.4.20 throws `… is already being used as a state attribute (a.k.a. a channel), cannot also be used as a node name.`; PY 1.2.14 accepts | differs |
| LangGraph: input schema re-declares a channel with another reducer | `Channel "messages" already exists with a different type` (JS Error / PY ValueError) | both |
| LangGraph checkpoints per run | step -1 input (next `__start__`, input not yet applied), step 0 input applied, one per node, final empty `next` → nodes + 2 per run; 2 runs of a 2-node graph = 8 checkpoints, SQLite 28,672 bytes | both |
| A flag written before `interrupt()` in the same node | never checkpointed → the side effect runs twice; an idempotency key on `thread_id` → once | both |
| Typo'd keys | JS name-constant object `K.SCOER` → `undefined`, write dropped silently; PY Pydantic state also drops a typo'd patch key silently → use a `patch()` helper that checks `State.spec` keys | both |
| Day 22 ping-pong | JS default recursion limit → 25 model calls (the book said 37) | JS |
| Groq free tier daily cap | `429 … tokens per day (TPD): Limit 200000, Used 199721` on gpt-oss-120b; rolls over ("try again in 21m11s") | — |
| Fixes for the JS 429 problem | `.withRetry({ stopAfterAttempt: 3 })` retried a simulated Groq 429 (3 requests, success); an `onFailedAttempt` that throws for non-429/5xx stops a 400 after 1 request. PY `ChatGroq` retries the same 429 and honours `retry-after` (3 requests, 4.7 s); PY `with_retry(retry_if_exception_type=(groq.RateLimitError, groq.InternalServerError, groq.APIConnectionError))` | both |
| Structured `.stream()` on Groq | one chunk with the default and `jsonSchema` methods (JS jsonMode streaming failed to parse); `JsonOutputParser` streams 61–102 partial objects — then validate yourself | both |
| Strict JSON-schema mode never returns null | "The weather is nice today." → `{species: 'none', count: 0}` — model the "nothing found" case explicitly | both |
| JSON-schema mode can still fail | gpt-oss-20b, Day 06 §5.6 quiz: `400 json_validate_failed` at temperature 0 (2 of 2); 0.4 worked | PY |
| `count_tokens_approximately` | import from `langchain_core.messages.utils` (not re-exported from `langchain_core.messages` in 1.6.7); ceil((content + role)/4) + 3 per message; replaces `token_counter=ChatGroq` (no GPT-2 download, StudyBuddy turn 82 s → 12 s) | PY |
| JS `tokenCounter: model` on ChatGroq | uses GPT-2's encoding fetched once from tiktoken.pages.dev (913 ms); offline → characters ÷ 4 with a warning. Same 61-message history at 400 tokens: JS keeps 33, PY (approx) 21 | differs |

## Corrections made to earlier weeks

| What was wrong | Correct behaviour | Fixed in |
|---|---|---|
| `createAgent({ prompt })` / `create_agent(prompt=…)` | **JS silently ignores** `prompt` (the agent runs with no system message); **PY raises** `TypeError: create_agent() got an unexpected keyword argument 'prompt'`. The option is `systemPrompt` / `system_prompt` | Day 16 (6 places + a ⚠️ note) |
| "`ToolNode` catches tool errors and returns them as content" | True in **JS** only; PY re-raises unless `handle_tool_errors` is set | Day 17 (3 passages + a translation-table row) |
| Day 09 loader import paths | moved from `@langchain/classic/document_loaders/fs/pdf` to `@langchain/community/document_loaders/*` | Day 09 + RAG cheatsheet |
| Week 1 message imports | switched to `@langchain/core/messages` / `langchain_core.messages` | Days 04, 05, 07 |
| "`ToolNode` handles errors for you" (Day 15, 2 places) | same as the Day 17 row: JS returns errors as content, PY re-raises unless `handle_tool_errors=True` | Day 15 §3.6 + interview (Oct 2026) |
| "pgvector does proper pre-filtering" (Day 11) | pgvector's README: with HNSW/IVFFlat "filtering is applied *after* the index is scanned"; **iterative index scans** (0.8.0+, `hnsw.iterative_scan`) or a B-tree plan fix it | Day 11, 4 places + source (Oct 2026) |
| "The KV-cache is why input tokens are cheaper" (Day 01 + glossary) | two separate facts: output is priced higher because it is generated serially; the KV-cache stops each output step recomputing the prefix | Day 01 §6 + glossary (Oct 2026) |
| "Add `"type": "module"`" (SETUP, Week 1 README) | npm 11.12.1 `npm init -y` writes `"type": "commonjs"` — the line must be **changed** (`npm pkg set type=module`); with no `type` field Node 24 runs ESM with a warning | SETUP.md, Week 1 README, Day 0A/0B (Oct 2026) |
| "A late `import "dotenv/config"` breaks the client" (old Day 03 mistake) | ESM hoists imports, so it works; the real trap is a module that reads `process.env` at import time and is imported before dotenv | Day 0B §7 (Oct 2026) |
| Re-ingesting a changed file "overwrites cleanly" (Day 12 Ex5) | content-hash ids never delete the old chunks of a changed file → stale chunks remain; delete by `source` first | Day 12 Ex5 prose (Oct 2026) |

| "Parallel writes to a no-reducer channel silently keep one" (Days 17, 18, 19, Week 3 README, cheatsheet, troubleshooting) | both languages **raise** `InvalidUpdateError` — JS `LastValue can only receive one value per step.`, PY `At key '…': Can receive only one value per step.` (langgraph JS 1.4.20, PY 1.2.14; static edges and `Send`) | prose in Days 17–19 + resources (Oct 2026) |
| "Recursion limit default 25" for both languages (Day 17, glossary, cheatsheet, KB) | JS 25, **PY 10007** | Day 17 (6 places) + resources (Oct 2026) |

### Formerly open: verified bugs in code blocks — all fixed after the owner approved code changes (8 Oct 2026)

| Where | What was measured | Status |
|---|---|---|
| Day 21 Exercise 1 "Fix C" (state-flag guard) | PY, langgraph 1.2.14: prints `FIX C total charges: 2` (book says 1). The node never finishes before `interrupt()`, so the flag is never checkpointed. Prose "Why Fix C works" and self-check 1(c) repeat the claim | ✅ fixed Oct 2026 (owner approved) |
| Day 19 §5.8 Python output | real output `{'log': ['unrecoverable', 'rescued']}`; book shows `['escaping', 'rescued']` | ✅ fixed Oct 2026 (owner approved) |
| Google model names | `text-embedding-004` shut down 14 Jan 2026 → `gemini-embedding-2`; `gemini-2.0-flash` shut down 1 Jun 2026 → `gemini-3.6-flash` (ai.google.dev deprecations page, checked Oct 2026). Groq `llama-3.3-70b-versatile` and `llama-3.1-8b-instant` are **not** deprecated | ✅ fixed Oct 2026 (owner approved) |
| Day 17 §4 output `{ log: [ 'a', 'b', 'join' ], winner: 'b' }` and mistake #2 comment `// → two of them are silently discarded` | both now raise `InvalidUpdateError` (see corrections). Prose under each now carries a ⚠️ correction note; the code/output lines themselves are unchanged | ✅ fixed Oct 2026 (owner approved) |
