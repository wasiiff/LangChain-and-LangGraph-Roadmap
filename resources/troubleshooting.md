# Troubleshooting

Symptom → cause → fix, for everything this book ran into. Search this page for the exact error
text you're seeing (Ctrl/Cmd+F); the "Day" column points to the full explanation.

## Exact error messages (verified)

These strings were produced by running the code in this book. If you see one, the fix is known.

| Error text (excerpt) | Cause | Fix | Day |
|---|---|---|---|
| `UnreachableNodeError: Node ... is not reachable` / `Graph must have an entrypoint` | no edge from `START` | `addEdge(START, "first")` | 17 |
| `GraphRecursionError: Recursion limit of 25 reached` | a loop with no working exit | add a budget exit to the router; don't just raise the limit | 17 |
| `No checkpointer set` | `getState` / history / interrupts without a checkpointer | `compile({ checkpointer })` | 20 |
| `Failed to put checkpoint ... missing a required "thread_id"` / `Checkpointer requires one or more of the following 'configurable' keys` | invoking a checkpointed graph without a thread | pass `configurable.thread_id` | 20 |
| `When there are multiple pending interrupts, you must specify the interrupt id when resuming` | resuming parallel interrupts with one value | resume with a map of interrupt id → value | 21 |
| `Please specify a name when you create your agent` | unnamed agent, or JS `createAgent` wrapper passed instead of `.graph` | add `name`; pass `agent.graph` | 22 |
| `Cannot read properties of undefined (reading 'slice')` / `IndexError: list index out of range` in `checkpoints` stream mode | streaming checkpoints without a checkpointer | compile with a checkpointer | 23 |
| `Node timeouts are only supported for async nodes` | `timeout=` on a sync Python node | make the node `async def` | 24 |
| `Model call failed after N attempts with ...` shown as the answer | retry middleware default `onFailure: "continue"` | `onFailure: "error"` / `on_failure="error"` | 24 |
| `Model call limits exceeded: run limit` | model-call limit reached | expected; raise the limit or fix the loop | 24 |
| `PIIDetectionError` | PII middleware with `strategy: "block"` | expected; choose `redact`/`mask` if blocking isn't wanted | 24 |
| `Received status [401]: Unauthorized` from JS `evaluate` | LangSmith credentials missing | set `LANGSMITH_API_KEY`, or use a local eval harness | 25 |
| `StructuredTool does not support sync invocation` | calling a Python MCP tool synchronously | `await tool.ainvoke(...)` | 26 |
| `Unexpected token ... is not valid JSON` (MCP client) | a stdio MCP server printing to stdout | log to stderr | 26 |
| `Heads up! Your graph ... includes a custom checkpointer` | LangGraph server given a checkpointer-compiled graph | export `builder.compile()`; use `POSTGRES_URI` | 27 |
| `ConsoleRenderer with colors=True on Windows requires the colorama package` | `langgraph dev` on Windows | `pip install colorama` | 27 |
| `UnicodeEncodeError: 'charmap' codec can't encode character` | Windows console encoding with emoji output | `PYTHONUTF8=1` / `PYTHONIOENCODING=utf-8` | 27 |
| `node.exe: bad option: --clear-screen=false` | `langgraphjs dev` on an unsupported Node version | use a supported Node version, WSL, or Docker | 27 |

## Silent failures (no error at all)

The most expensive bugs don't throw. Symptoms to recognise:

| Symptom | Cause | Day |
|---|---|---|
| `invoke` returns `undefined` / `None` | a node writes a key that isn't a declared channel | 17 |
| Parallel results: one survives instead of N | fan-out into a last-write-wins channel | 17, 19 |
| Items duplicated in a list channel | returning the full list with an append reducer; or a subgraph sharing an appending channel | 17, 19 |
| A new conversation every turn | unstable or per-request `thread_id`; in-memory checkpointer across instances | 20, 27 |
| A side effect happens twice after approval | code before `interrupt()` re-runs on resume | 21 |
| A rejected action still runs | `Command` goto plus a static edge from the same node | 28 |
| The front desk answers after a handoff | swarm without a checkpointer or `activeAgent` | 22 |
| Stop button doesn't reduce cost (JS) | breaking out of the stream without an abort signal | 23 |
| A Python node never retries a timeout | default `retry_on` excludes `OSError` subclasses | 24 |
| Metrics show zero model calls | listening for LLM-start instead of chat-model-start | 25 |
| AI SDK returns empty text though a tool ran | `generateText` without `stopWhen` | 26 |
| Tool errors leak hostnames or connection strings | raw exceptions forwarded as tool / MCP results | 24, 26 |

## Week 1 — Foundations

| Symptom | Day | Fix |
|---|---|---|
| `Cannot use import statement outside a module` | 03 | Add `"type": "module"` to `package.json` |
| `Promise { <pending> }` in a log | 03 | Missing `await` |
| `ModuleNotFoundError` after installing | 03 | Activate the venv — prompt must show `(.venv)` |
| `Missing value for input variable "label": "BUG"` | 05 | Unescaped braces in a template — use `{{ }}` |
| `messages with role 'tool' must be a response to...` | 02 | Push the assistant `tool_calls` message back into history |
| Chain streams, then suddenly doesn't | 07 | A non-streaming lambda after the model is buffering |
| Keys vanish mid-chain | 07 | You used `RunnableParallel` where you wanted `.assign()` |
| `429 Rate limit` while doing exercises | — | Switch to `llama-3.1-8b-instant`, or use Ollama offline |

## Week 2 — Data, Embeddings, RAG & Memory

| Symptom | Day | Fix |
|---|---|---|
| `ERR_PACKAGE_PATH_NOT_EXPORTED` on a retriever import | 08 | Use `@langchain/classic/...` — see the version trap |
| `ModuleNotFoundError: langchain.retrievers` | 08 | `pip install langchain-classic`, import from `langchain_classic` |
| Chunks cut mid-word, tables destroyed | 09 | Use `RecursiveCharacterTextSplitter`, not slicing or `CharacterTextSplitter` |
| Chunk sizes far below `chunkSize` | 09 | Expected — `chunkSize` is a **maximum**, not a target |
| Retrieval returns the wrong section | 09 | Inject header breadcrumbs into chunk text |
| Metadata gone after splitting | 09 | Use `splitDocuments`, not `splitText` |
| Similarity scores all ~0.5 for unrelated text | 10 | Expected — embedding spaces are anisotropic. Rank relatively |
| `ERR_4471` retrieves `ERR_4472` | 10/11 | Embeddings blur identifiers → add hybrid search |
| Results silently change after a model swap | 10 | You mixed vector spaces. Re-embed, and namespace caches by model |
| `k=10` with a filter returns 1 result | 11 | Post-filtering. Over-fetch, or partition per tenant |
| Ollama connection refused | 10+ | `ollama serve`, and `ollama pull nomic-embed-text` |
| RAG confidently invents an answer | 12 | Missing grounding contract + exact refusal phrase |
| Follow-up questions retrieve nonsense | 12 | Add query rewriting — "what about Basic?" has no topic |
| Reranking changes nothing | 13 | You reranked 4→4. Retrieve 20, rerank to 4 |
| MMR does nothing | 13 | `fetchK` must be ≫ `k` |
| Bot forgets facts from 20 turns ago | 14 | Summary drift — keep hard facts structured |

## Week 3 — Tools, Agents & LangGraph

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

## Week 4 — Multi-agent, Production & Interviews

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
| Metrics show zero model calls | 25 | Listen for `handleChatModelStart` / `on_chat_model_start` |
| JS `evaluate` fails with 401 | 25 | It needs LangSmith credentials; use a local harness offline |
| `StructuredTool does not support sync invocation` | 26 | MCP tools in Python: `await tool.ainvoke(...)` |
| AI SDK returns empty text though the tool ran | 26 | Add `stopWhen: stepCountIs(n)` |
| `Heads up! Your graph ... includes a custom checkpointer` | 27 | Export `builder.compile()` for the LangGraph server |
| Python `langgraph dev` crashes on Windows at startup | 27 | `pip install colorama`; set `PYTHONUTF8=1` |
| A rejected action still executed | 28 | `Command` goto plus a static edge runs both — route every path with `Command` |

## Setup

| Error | Cause | Fix |
|---|---|---|
| `Cannot use import statement outside a module` | Missing `"type": "module"` in `package.json` | Add it |
| `Error: Missing API key` / `GROQ_API_KEY not set` | `.env` not loaded, or wrong folder | JS: `import "dotenv/config"` as the **first** line. Python: `load_dotenv()` **before** creating the model |
| `ModuleNotFoundError: No module named 'langchain_groq'` | venv not activated, or installed globally | Activate `.venv`, reinstall |
| `401 Invalid API Key` | Key copied with a trailing space/newline | Re-copy; no quotes needed in `.env` |
| `429 Rate limit reached` | Free tier limit hit | Wait 60s, or switch to `llama-3.1-8b-instant`, or use Ollama |
| `fetch failed` / `ENOTFOUND` | Network / corporate proxy | Check firewall; try Ollama offline |
| Python `SSL: CERTIFICATE_VERIFY_FAILED` | macOS missing certs | Run `/Applications/Python\ 3.x/Install\ Certificates.command` |
