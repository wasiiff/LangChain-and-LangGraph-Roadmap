# JS ↔ Python Mapping

Every API pair used in this book, day by day — copied from each day's own translation table, so
it matches the code you read there. Use your browser's find (Ctrl/Cmd+F) on either name.

> **Behaviour differences that bite** (all verified in the day files — the names differ in many
> places, but these are the ones where the *behaviour* differs):
>
> | Area | JavaScript | Python | Day |
> |---|---|---|---|
> | `createAgent` / `create_agent` return value | a `ReactAgent` wrapper — the graph is on `.graph` | the compiled graph itself | 22 |
> | System prompt option | `systemPrompt` (`prompt` is silently ignored) | `system_prompt` (`prompt=` raises `TypeError`) | 16 |
> | `checkpointer` from `fromConnString` / `from_conn_string` | returns the saver | a context manager | 20, 27 |
> | Tool raises inside `ToolNode` | returned as tool-message content | re-raised unless `handle_tool_errors` | 24 |
> | Node `retryPolicy` / `retry_policy` default | retried a plain `Error` | skips `RuntimeError`, `ValueError`, `OSError` (incl. `TimeoutError`) | 24 |
> | Node timeouts | any node | async nodes only | 24 |
> | Leaving a stream loop early | the graph keeps running | the graph stops before the next superstep | 23 |
> | Nested graphs' tokens in `messages` mode | included by default | only with `subgraphs=True` | 23 |
> | Destinations for `Command` routing | `{ ends: [...] }` on `addNode` | `Command[Literal[...]]` return annotation | 19 |
> | MCP adapter tool results | a string | a list of content blocks; tools are async-only | 26 |
> | ChatGroq default retries | 6 | 2 | 24 |
> | PII `mask` strategy on an email | `a***@example.com` | `ayesha.khan@****.com` | 24 |

## Week 0 — Start Here

### Day 0A — [Your Toolkit: Terminal, Git, Node, Python & Reading Errors](../week-00-start-here/day-00a-your-toolkit.md)

| Idea | JavaScript (Node.js) | Python |
|---|---|---|
| Run a file | `node env-check.js` | `python env_check.py` |
| Check the version | `node --version` | `python --version` |
| Package tool | `npm` | `pip` (use `python -m pip` when unsure) |
| Project package list | `package.json` → `dependencies` | `requirements.txt` |
| Exact versions | `package-lock.json` (automatic) | `pip freeze > requirements.txt` |
| Where packages go | `node_modules/` in the project | `.venv/` after you activate it |
| Install everything | `npm install` | `pip install -r requirements.txt` |
| Isolation | automatic, per folder | manual: `python -m venv .venv` + activate |
| Module setting | `"type": "module"` in `package.json` | none needed |
| Load `.env` | `import "dotenv/config";` | `from dotenv import load_dotenv` + `load_dotenv()` |
| Package name vs import name | `dotenv` / `dotenv` | `python-dotenv` / `dotenv` |
| Read a variable | `process.env.NAME` → `undefined` if missing | `os.environ.get("NAME")` → `None` if missing |
| Runtime version | `process.version` | `platform.python_version()` |
| Current folder | `process.cwd()` | `os.getcwd()` |
| Which program is running | `process.execPath` | `sys.executable` |
| Exit with an error | `process.exit(1)` | `sys.exit(1)` |
| "Nothing" value | `undefined` / `null` | `None` |
| Where the error type is | top of the trace | last line of the trace |
| Where `.env` is searched | the current folder only | from the script's folder upwards |

### Day 0B — [Programming for AI: JSON, HTTP, Async & Schemas in JS and Python](../week-00-start-here/day-00b-programming-for-ai.md)

| Concept | JavaScript | Python |
|---|---|---|
| data → JSON text | `JSON.stringify(obj)` | `json.dumps(d)` |
| JSON text → data | `JSON.parse(text)` | `json.loads(text)` |
| pretty JSON | `JSON.stringify(obj, null, 2)` | `json.dumps(d, indent=2)` |
| a date in JSON | becomes an ISO string | `TypeError` — convert it yourself |
| huge integer | loses precision | exact |
| HTTP POST with JSON | `fetch(url, { method, headers, body: JSON.stringify(x) })` | `httpx.post(url, json=x)` |
| status | `res.status`, `res.ok` | `res.status_code`, `res.is_success` |
| raise on 4xx/5xx | do it yourself: `if (!res.ok) throw …` | `res.raise_for_status()` |
| read the body | `await res.json()` — only once | `res.json()` — as often as you like |
| a header | `res.headers.get("retry-after")` | `res.headers.get("retry-after")` |
| sync option | ❌ none — always async | ✅ `invoke` (sync) and `ainvoke` (async) |
| parallel | `Promise.all([...])` | `asyncio.gather(*tasks)` |
| tolerant parallel | `Promise.allSettled` | `gather(..., return_exceptions=True)` |
| un-awaited call | `Promise { <pending> }` | `<coroutine object …>` |
| timing | `console.time` / `timeEnd` | `time.time()` deltas |
| spread into call | `f(...args)` | `f(*args)` |
| yield many | `for (const p of parts) yield p` | `yield from parts` |
| schema errors | `result.error.issues` | `e.errors()` |
| schema → JSON Schema | `z.toJSONSchema(Schema)` | `Model.model_json_schema()` |
| `"yes"` for a boolean | rejected | accepted as `True` (unless `strict=True`) |
| method names | `withStructuredOutput`, `withRetry` | `with_structured_output`, `with_retry` |

### Day 0C — [Just-Enough Maths: Vectors, Probability & Softmax](../week-00-start-here/day-00c-just-enough-maths.md)

| Concept | JavaScript | Python |
|---|---|---|
| file / import | `toolkit.mjs` · `import { dot } from "./toolkit.mjs"` | `toolkit.py` · `from toolkit import dot` |
| square root, e^x, natural log | `Math.sqrt` · `Math.exp` · `Math.log` | `math.sqrt` · `math.exp` · `math.log` |
| biggest value | `Math.max(...xs)` | `max(xs)` |
| add up a list | `xs.reduce((s, x) => s + x, 0)` | `sum(xs)` |
| transform every item | `xs.map((x) => x / n)` | `[x / n for x in xs]` |
| round up | `Math.ceil` | `math.ceil` |
| sort numbers | `[...xs].sort((a, b) => a - b)` — **comparator required** | `sorted(xs)` — numeric by default |
| whole number vs decimal | one `number` type: prints `5` | `int` and `float`: `math.sqrt` prints `5.0` |
| raise an error | `throw new Error("…")` | `raise ValueError("…")` |
| divide by zero | `1 / 0` → `Infinity`, `0 / 0` → `NaN` (no error) | `ZeroDivisionError` |
| `exp` of a huge number | `Math.exp(710)` → `Infinity` | `math.exp(710)` → `OverflowError: math range error` |
| seeded random | none built in — write `makeRng` | `random.Random(seed)` (different numbers from JS) |
| state inside a closure | `let state` in the outer function | `nonlocal state` in the inner function |
| fast vector maths | (plain loops are fast enough here) | numpy: `D @ q`, `np.dot`, `np.linalg.norm` |


## Week 1 — Foundations

### Day 01 — [What an LLM Actually Is: Tokens, Context & Inference](../week-01-foundations/day-01-llms-tokens-and-inference.md)

| | JavaScript | Python |
|---|---|---|
| Load env | `import "dotenv/config"` | `load_dotenv()` |
| Async | `await` everywhere (SDK is async-first) | sync by default; `AsyncGroq` for async |
| Streaming loop | `for await (const c of stream)` | `for chunk in stream:` |
| Null-safe access | `chunk.choices[0]?.delta?.content ?? ""` | `chunk.choices[0].delta.content or ""` |
| Naming | `camelCase` params in LangChain, `snake_case` in raw SDK | `snake_case` everywhere |
| Tokenizer lib | `gpt-tokenizer` | `tiktoken` |
| Reasoning tokens used | `usage.completion_tokens_details?.reasoning_tokens` | `usage.completion_tokens_details.reasoning_tokens` |
| Dot product (attention) | `a.reduce((sum, x, i) => sum + x * b[i], 0)` | `sum(x * y for x, y in zip(a, b))` |

> ⚠️ **Naming trap you'll meet all week.** The raw provider SDKs use `snake_case` in *both*
> languages (`max_tokens`), because that's what the HTTP API uses. But **LangChain JS** uses
> `camelCase` (`maxTokens`). So in JS you'll write `max_tokens` today and `maxTokens` on Day 04.
> That's not a typo — it's two different layers.

### Day 02 — [Prompt Engineering & Talking to Models With No Framework](../week-01-foundations/day-02-prompt-engineering-and-raw-apis.md)

| | JavaScript | Python |
|---|---|---|
| Parallel calls | `await Promise.all([...])` | `for` loop, or `asyncio.gather` with `AsyncGroq` |
| Regex | `text.match(/Action:\s*(\w+)/)` → array | `re.search(r"Action:\s*(\w+)", text)` → match object |
| Regex "dotall" | `/.../s` flag | `re.S` / `re.DOTALL` flag |
| Optional chaining | `msg.tool_calls?.length` | `if not msg.tool_calls:` |
| Counting votes | `{}` + manual increment | `collections.Counter` |
| JSON | `JSON.parse` / `JSON.stringify` | `json.loads` / `json.dumps` |
| Spread kwargs | `...rest` | `**rest` |
| Reasoning text (raw SDK) | `msg.reasoning` | `msg.reasoning` |

### Day 03 — [Choosing a Model · Why LangChain Exists](../week-01-foundations/day-03-choosing-a-model-and-why-langchain.md)

| Concept | JavaScript | Python |
|---|---|---|
| a price table | object of objects | dict of dicts |
| big numbers readable | `1_000_000` | `1_000_000` |
| money to 6 places | `one.toFixed(6)` | `f"{one:.6f}"` |
| pad a column | `str.padEnd(16)` | `f"{s:<16}"` |
| precise timer | `performance.now()` (ms) | `time.perf_counter()` (s — × 1000 for ms) |
| median | sort, take the middle | `statistics.median(times)` |
| a fake model | object with `async invoke()` | class with `invoke()` |
| strip trailing dots | `s.replace(/[.!]+$/, "")` | `s.rstrip(".!")` |
| structured output | `.withStructuredOutput(Zod)` | `.with_structured_output(Pydantic)` |
| retry / fallback | `.withRetry({ stopAfterAttempt })` / `.withFallbacks([...])` | `.with_retry(stop_after_attempt=)` / `.with_fallbacks([...])` |
| sync option | ❌ none — always async | ✅ `invoke` (sync) and `ainvoke` (async) |

### Day 04 — [LangChain Models: invoke, stream, batch & Message Types](../week-01-foundations/day-04-langchain-models.md)

| | JavaScript | Python |
|---|---|---|
| Params | `maxTokens`, `topP`, `maxRetries` | `max_tokens`, `top_p`, `max_retries` |
| Universal loader | `await initChatModel("groq:...")` | `init_chat_model("groq:...")` — no await |
| Chunk accumulation | `full.concat(chunk)` | `full + chunk` |
| Batch concurrency | `{ maxConcurrency: 2 }` | `config={"max_concurrency": 2}` |
| Message import | `from "@langchain/core/messages"` | `from langchain_core.messages import ...` |
| Trimming | `trimMessages(msgs, {...})` | `trim_messages(msgs, ...)` |
| Token counter (an estimate either way) | `tokenCounter: model` (GPT-2's tokenizer) | `token_counter=count_tokens_approximately` |
| Text accessor | `res.text` | `res.content` (or `res.text` / `res.text()`) |
| Async variants | none — always async | `ainvoke`, `astream`, `abatch` |
| Reasoning effort | `reasoningEffort: "low"` | `reasoning_effort="low"` |
| Hidden reasoning (Groq) | not exposed | `additional_kwargs["reasoning_content"]`, `usage_metadata["output_token_details"]["reasoning"]` |
| Streamed usage (Groq) | `response_metadata.usage` — `usage_metadata` is missing (§3.6) | `usage_metadata`, as normal |
| Model chosen per call | `initChatModel("openai/gpt-oss-120b", { modelProvider: "groq", configurableFields: ["model"] })`, then `{ model: "openai/gpt-oss-20b" }` | `init_chat_model(configurable_fields=["model"])`, then `{"model": "groq:openai/gpt-oss-20b"}` |

### Day 05 — [Prompts & Templates](../week-01-foundations/day-05-prompts-and-templates.md)

| | JavaScript | Python |
|---|---|---|
| Import path | `@langchain/core/prompts` | `langchain_core.prompts` |
| Factory | `ChatPromptTemplate.fromMessages([...])` | `ChatPromptTemplate.from_messages([...])` |
| Render | `await t.format({...})` / `.invoke({...})` | `t.format(...)` / `.invoke({...})` |
| Pipe | `prompt.pipe(model)` | `prompt \| model` |
| Placeholder | `new MessagesPlaceholder({variableName, optional})` | `MessagesPlaceholder("history", optional=True)` |
| To messages | `value.toChatMessages()` | `value.to_messages()` |
| Message role | `m.getType()` | `m.type` |
| Compose | `a.concat(b)` | `a + b` |
| Declared vars | `t.inputVariables` | `t.input_variables` |
| Partial | `await t.partial({...})` — async | `t.partial(...)` — sync |
| Variable naming | `maxSentences` | `max_sentences` |

### Day 06 — [Output Parsers & Structured Output (Zod ↔ Pydantic)](../week-01-foundations/day-06-output-parsers-structured-output.md)

| | JavaScript | Python |
|---|---|---|
| Schema library | Zod | Pydantic |
| String parser | `StringOutputParser` | `StrOutputParser` ⚠️ |
| Method | `withStructuredOutput(S)` | `with_structured_output(S)` |
| JSON schema mode | `{ method: "jsonSchema" }` (always strict) | `method="json_schema", strict=True` |
| Raw included | `{ includeRaw: true }` → `{raw, parsed}` | `include_raw=True` → `{"raw", "parsed"}` |
| Return type | plain object | Pydantic model instance (use `.model_dump()` for a dict) |
| Field description | `.describe("...")` | `Field(description="...")` |
| Schema description | schema-level `.describe()` | the **class docstring** |
| Enum | `z.enum([...])` | `Literal[...]` |
| Nullable | `.nullable()` | `Optional[X] = None` |
| Array length | `.length(4)` | `Field(min_length=4, max_length=4)` |
| Import path | `@langchain/core/output_parsers` | `langchain_core.output_parsers` |

### Day 07 — [LCEL & Runnables (the #1 interview topic)](../week-01-foundations/day-07-lcel-and-runnables.md)

| | JavaScript | Python |
|---|---|---|
| Pipe | `.pipe(x)` | `\| x` |
| Object → Parallel | must be inside `RunnableSequence.from([...])` | plain dict works with `\|` |
| Parallel constructor | `RunnableParallel.from({...})` | `RunnableParallel(a=..., b=...)` |
| Lambda | `RunnableLambda.from(fn)` | `RunnableLambda(fn)` |
| Branch | `RunnableBranch.from([[cond, r], ..., default])` | `RunnableBranch((cond, r), ..., default)` |
| Assign | `RunnablePassthrough.assign({ k: fn })` | `RunnablePassthrough.assign(k=fn)` |
| Config | `.withConfig({ runName })` | `.with_config(run_name=...)` |
| Events | `.streamEvents(x, { version: "v2" })` | `.astream_events(x, version="v2")` |
| Visualise | `chain.getGraph()` | `chain.get_graph().print_ascii()` |
| Spread merge | `{ ...x, k: v }` | `{**x, "k": v}` |


## Week 2 — Data, Embeddings, RAG & Memory

### Day 08 — [Chains: Sequential, Parallel, Router & Document Chains](../week-02-data-embeddings-and-rag/day-08-chains.md)

| | JavaScript | Python |
|---|---|---|
| Document | `@langchain/core/documents` | `langchain_core.documents` |
| Document text field | `pageContent` | `page_content` |
| Legacy chains package | `@langchain/classic/chains/...` | `langchain_classic.chains...` |
| Stuff helper | `await createStuffDocumentsChain({ llm, prompt })` | `create_stuff_documents_chain(model, prompt)` |
| Helper is async? | ✅ yes, `await` it | ❌ no |
| Batch concurrency | `{ maxConcurrency: 5 }` | `config={"max_concurrency": 5}` |
| Assign | `.assign({ k: chain })` | `.assign(k=chain)` |

### Day 09 — [Documents, Loaders, Splitting & Chunking Strategy](../week-02-data-embeddings-and-rag/day-09-documents-and-splitting.md)

| | JavaScript | Python |
|---|---|---|
| Text field | `pageContent` | `page_content` |
| Splitter package | `@langchain/textsplitters` | `langchain_text_splitters` |
| Split text | `await splitter.splitText(s)` | `splitter.split_text(s)` |
| Split docs | `await splitter.splitDocuments(d)` | `splitter.split_documents(d)` |
| Params | `chunkSize`, `chunkOverlap` | `chunk_size`, `chunk_overlap` |
| Code splitting | `.fromLanguage("js", {...})` | `.from_language(Language.PYTHON, ...)` |
| Markdown headers | ❌ manual (see §4.4) | ✅ `MarkdownHeaderTextSplitter` |
| HTML headers | ❌ manual | ✅ `HTMLHeaderTextSplitter` |
| JSON splitting | ❌ manual | ✅ `RecursiveJsonSplitter` |
| Loaders (basic) | `@langchain/classic/document_loaders/fs/text` | `langchain_community.document_loaders` |
| Loaders (PDF/CSV/web) | `@langchain/community/document_loaders/...` | `langchain_community.document_loaders` |
| Async | everything `await`ed | sync by default |

### Day 10 — [Embeddings: Vectors, Similarity & Model Choice](../week-02-data-embeddings-and-rag/day-10-embeddings.md)

| | JavaScript | Python |
|---|---|---|
| Ollama embeddings | `new OllamaEmbeddings({ model })` | `OllamaEmbeddings(model=...)` |
| Google embeddings | `model: "gemini-embedding-2"` | `model="models/gemini-embedding-2"` |
| Query | `await embeddings.embedQuery(s)` | `embeddings.embed_query(s)` |
| Documents | `await embeddings.embedDocuments([...])` | `embeddings.embed_documents([...])` |
| Cache class | `@langchain/classic/embeddings/cache_backed` | `langchain_classic.embeddings` |
| Cache factory | `CacheBackedEmbeddings.fromBytesStore(...)` | `CacheBackedEmbeddings.from_bytes_store(...)` |
| Byte store | `InMemoryStore` (`@langchain/classic/storage/in_memory`) | `InMemoryByteStore` (`langchain_core.stores`) |
| Vector maths | manual loops (or a lib) | **numpy** — use it |

> 📦 **The `models/` prefix.** Older versions of `langchain-google-genai` needed it in Python
> (`"models/..."`) and older JS did not, which tripped people up when porting code. With the
> current packages both spellings work: we measured `"gemini-embedding-2"` and
> `"models/gemini-embedding-2"` in Python 4.4.0 (both 3072 dims), and the JS class strips the
> prefix itself. This course keeps `models/` in Python so the code also runs on older versions.

### Day 11 — [Vector Databases: Indexes, Filtering & Hybrid Search](../week-02-data-embeddings-and-rag/day-11-vector-databases.md)

| | JavaScript | Python |
|---|---|---|
| In-memory store | `MemoryVectorStore` (`@langchain/classic/vectorstores/memory`) | `InMemoryVectorStore` (`langchain_core.vectorstores`) ✅ no extra install |
| Build from docs | `await MemoryVectorStore.fromDocuments(docs, emb)` | `InMemoryVectorStore.from_documents(docs, emb)` |
| Search | `similaritySearch(q, k, filter)` | `similarity_search(q, k=..., filter=...)` |
| In-memory filter | a **function** | a **function** (`filter=lambda d: ...`) |
| Chroma package | `@langchain/community/vectorstores/chroma` | `langchain_chroma` |
| Chroma persistence | needs a running server (`chroma run`) | `persist_directory=` — **no server needed** |
| Chroma filter | Mongo-style object | Mongo-style dict |
| As retriever | `store.asRetriever({ k: 2 })` | `store.as_retriever(search_kwargs={"k": 2})` |
| BM25 built-in | `@langchain/community/retrievers/bm25` | `langchain_community.retrievers.BM25Retriever` |
| Vector maths | manual | **numpy** |

> 💡 **Python is meaningfully nicer here.** `InMemoryVectorStore` ships in `langchain-core` with
> no extra package, and Chroma persists to a directory without running a server. In JS you need
> `@langchain/classic` and a Chroma server process.

### Day 12 — [Naive RAG End-to-End (and Six Ways to Break It)](../week-02-data-embeddings-and-rag/day-12-naive-rag.md)

| | JavaScript | Python |
|---|---|---|
| Store | `MemoryVectorStore` (`@langchain/classic`) | `InMemoryVectorStore` (`langchain_core`) |
| Markdown headers | manual walk (Day 09 §4.4) | `MarkdownHeaderTextSplitter` ✅ built in |
| Retriever | `store.asRetriever({ k: 3 })` | `store.as_retriever(search_kwargs={"k": 3})` |
| Parallel + passthrough | `RunnableParallel.from({ docs: retriever, question: new RunnablePassthrough() })` | `RunnableParallel(docs=retriever, question=RunnablePassthrough())` |
| Retrieval helper | `await createRetrievalChain({ retriever, combineDocsChain })` | `create_retrieval_chain(retriever, combine_docs_chain)` |
| Helper is async? | ✅ yes | ❌ no |
| Result key | `result.context` (Documents) | `result["context"]` |

### Day 13 — [Advanced RAG: Reranking, HyDE, Multi-Query & Self-Correction](../week-02-data-embeddings-and-rag/day-13-advanced-rag.md)

| | JavaScript | Python |
|---|---|---|
| MMR params | `{ searchType: "mmr", searchKwargs: { fetchK, lambda } }` | `search_type="mmr", search_kwargs={"fetch_k", "lambda_mult"}` |
| Lambda param name | `lambda` | `lambda_mult` ⚠️ (`lambda` is a keyword) |
| Multi-query | `MultiQueryRetriever.fromLLM({ llm, retriever })` | `MultiQueryRetriever.from_llm(retriever, llm)` |
| Compression | `@langchain/classic/retrievers/contextual_compression` | `langchain_classic.retrievers` |
| Compressors | `.../document_compressors/embeddings_filter` | `langchain_classic.retrievers.document_compressors` |
| Self-query | `@langchain/classic/retrievers/self_query` | `langchain_classic.retrievers.self_query.base` |
| Parallel grading | `Promise.all(docs.map(...))` | loop, or `asyncio.gather` with `ainvoke` |

### Day 14 — [Memory: Buffer, Summary, Entity & What Actually Changed](../week-02-data-embeddings-and-rag/day-14-memory.md)

| | JavaScript | Python |
|---|---|---|
| Trim | `await trimMessages(msgs, {...})` | `trim_messages(msgs, ...)` |
| Trim params | `maxTokens`, `tokenCounter`, `includeSystem`, `startOn` | `max_tokens`, `token_counter`, `include_system`, `start_on` |
| Message role | `m.getType()` | `m.type` |
| Message text | `m.content` / `res.text` | `m.content` |
| Store | `MemoryVectorStore` (`@langchain/classic`) | `InMemoryVectorStore` (`langchain_core`) |
| Legacy memory | `@langchain/classic/memory` | `langchain_classic.memory` |
| Dict merge | `{ ...ctx, input: turn }` | `{**ctx, "input": turn}` |


## Week 3 — Tools, Agents & LangGraph

### Day 15 — [Tools: Creating, Calling, Schemas, Errors & Retries](../week-03-tools-agents-and-langgraph/day-15-tools.md)

| | JavaScript | Python |
|---|---|---|
| Create | `tool(fn, { name, description, schema })` | `@tool` decorator |
| **Description** | the `description` option | **the docstring** ⚠️ |
| Schema | Zod object | type hints + docstring `Args:` |
| Import | `@langchain/core/tools` (also re-exported from `langchain`) | `langchain_core.tools` (also `langchain.tools`) |
| Bind | `model.bindTools([...])` | `model.bind_tools([...])` |
| Read calls | `res.tool_calls[0].name` / `.args` | `res.tool_calls[0]["name"]` / `["args"]` ⚠️ dicts |
| ToolMessage | `new ToolMessage({ content, tool_call_id })` | `ToolMessage(content=..., tool_call_id=...)` |
| ToolNode | `new ToolNode([...])` from `@langchain/langgraph/prebuilt` | `ToolNode([...])` from `langgraph.prebuilt` |
| Inspect schema | `z.toJSONSchema(tool.schema)` | `tool.args` |
| Parallel exec | `Promise.all(calls.map(...))` | loop, or `asyncio.gather` with `ainvoke` |

> ⚠️ **`tool_calls` entries are dicts in Python, objects in JS.** `call["name"]` vs `call.name`.
> This is the single most common porting error in agent code.

### Day 16 — [Agents From First Principles: Build ReAct by Hand](../week-03-tools-agents-and-langgraph/day-16-agents.md)

| | JavaScript | Python |
|---|---|---|
| Prebuilt (LangChain) | `createAgent({ model, tools, systemPrompt })` | `create_agent(model, tools, system_prompt=...)` |
| Prebuilt (LangGraph) | `createReactAgent({ llm, tools, checkpointer })` | `create_react_agent(model, tools, checkpointer=...)` |
| Stop sequence | `model.invoke(msgs, { stop: ["Observation:"] })` | `model.invoke(msgs, stop=["Observation:"])` |
| Tool call fields | `call.name`, `call.args`, `call.id` | `call["name"]`, `call["args"]`, `call["id"]` ⚠️ |
| Message type | `m.getType()` | `m.type` |
| Result shape | `result.messages` | `result["messages"]` |
| Regex dotall | `/.../s` | `re.S` |

### Day 17 — [LangGraph Basics: From a Loop to a Graph](../week-03-tools-agents-and-langgraph/day-17-langgraph-basics.md)

| Concept | JavaScript | Python |
|---|---|---|
| declare state | `Annotation.Root({ ... })` | `class S(TypedDict): ...` |
| plain channel | `x: Annotation()` | `x: str` |
| channel + reducer | `Annotation({ reducer, default })` | `Annotated[list[str], operator.add]` |
| append list | `reducer: (a, b) => a.concat(b)` | `operator.add` |
| counter | `reducer: (a, b) => a + b, default: () => 0` | `Annotated[int, operator.add]` |
| messages state | `MessagesAnnotation` | `MessagesState` |
| builder | `new StateGraph(State)` | `StateGraph(State)` |
| add node | `.addNode("a", fn)` | `.add_node("a", fn)` |
| add edge | `.addEdge("a", "b")` | `.add_edge("a", "b")` |
| conditional | `.addConditionalEdges("a", fn, ["b", END])` | `.add_conditional_edges("a", fn, ["b", END])` or a dict |
| compile | `.compile()` | `.compile()` |
| run | `await app.invoke({...})` | `app.invoke({...})` |
| stream | `for await (const c of await app.stream(x, { streamMode: "updates" }))` | `for c in app.stream(x, stream_mode="updates")` |
| read state | `state.topic` | `state["topic"]` |
| tool node | `new ToolNode(tools)` | `ToolNode(tools)` |
| tool errors (default) | caught → returned as content | re-raised (only bad arguments caught) — use `handle_tool_errors=True` |
| tool router | `toolsCondition` | `tools_condition` |
| recursion cap | `{ recursionLimit: 50 }` | `{"recursion_limit": 50}` |
| diagram | `(await app.getGraphAsync()).drawMermaid()` | `app.get_graph().draw_mermaid()` |

Chaining differs slightly too. JS `.addNode()` returns the builder, so you can chain every call
into one statement. Python's methods return the builder as well, so they *can* be chained. But
the usual Python style is one statement per line. That's what the docs use, and what your
reviewers will expect.

### Day 18 — [State & Reducers: What Goes Where](../week-03-tools-agents-and-langgraph/day-18-state-and-reducers.md)

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

### Day 19 — [Control Flow: `Command`, `Send` & Subgraphs](../week-03-tools-agents-and-langgraph/day-19-control-flow.md)

| Concept | JavaScript | Python |
|---|---|---|
| import | `from "@langchain/langgraph"` | `from langgraph.types import Command, Send` |
| command | `new Command({ update, goto })` | `Command(update=..., goto=...)` |
| declare destinations | `.addNode("n", fn, { ends: [...] })` | `-> Command[Literal[...]]` return annotation |
| …or explicitly | — | `.add_node("n", fn, destinations=(...))` |
| send | `new Send("worker", payload)` | `Send("worker", payload)` |
| fan-out edge | `.addConditionalEdges("split", fanOut, ["worker"])` | `.add_conditional_edges("split", fan_out, ["worker"])` |
| subgraph as node | `.addNode("sub", compiledGraph)` | `.add_node("sub", compiled_graph)` |
| escape to parent | `graph: Command.PARENT` | `graph=Command.PARENT` |
| parent needs ends? | **yes** — `{ ends: ["rescue"] }` | no |
| nested diagram | `await app.getGraphAsync({ xray: true })` | `app.get_graph(xray=True)` |
| stream subgraphs | `{ streamMode: "updates", subgraphs: true }` | `stream_mode="updates", subgraphs=True` |
| stream chunk shape | `[namespaceArray, update]` | `(namespace_tuple, update)` |

### Day 20 — [Persistence & Checkpointing: Save, Resume, Rewind](../week-03-tools-agents-and-langgraph/day-20-persistence-and-checkpointing.md)

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

### Day 21 — [Human-in-the-Loop: Pause, Ask, Resume](../week-03-tools-agents-and-langgraph/day-21-human-in-the-loop.md)

| Concept | JavaScript | Python |
|---|---|---|
| import | `from "@langchain/langgraph"` | `from langgraph.types import interrupt, Command` |
| pause | `const v = interrupt(payload)` | `v = interrupt(payload)` |
| async? | **synchronous** — no `await` | synchronous |
| what invoke returns | `result.__interrupt__` → `[{ id, value }]` | `result["__interrupt__"]` → `[Interrupt(value=, id=)]` |
| pending, from state | `snap.tasks[0].interrupts[0].value` | `snap.tasks[0].interrupts[0].value` |
| resume | `new Command({ resume: v })` | `Command(resume=v)` |
| resume many | `new Command({ resume: { [id]: v } })` | `Command(resume={id: v})` |
| update + resume | `new Command({ update, resume })` | `Command(update=..., resume=...)` |
| static breakpoint | `.compile({ interruptBefore: ["n"] })` | `.compile(interrupt_before=["n"])` |
| resume a breakpoint | `app.invoke(null, config)` | `app.invoke(None, config)` |
| requires | a checkpointer | a checkpointer |


## Week 4 — Multi-agent, Production & Interviews

### Day 22 — [Multi-Agent Systems: Supervisors, Handoffs & When Not To](../week-04-production-projects-and-interviews/day-22-multi-agent.md)

| Concept | JavaScript | Python |
|---|---|---|
| make an agent | `createAgent({ model, tools, name, systemPrompt })` | `create_agent(model, tools, name=..., system_prompt=...)` |
| what it returns | `ReactAgent` wrapper — graph on **`.graph`** | `CompiledStateGraph` directly |
| agent as a tool | `tool(async ({ task }) => (await agent.invoke(...)).messages.at(-1).content, {...})` | `@tool def ask_x(task: str): return agent.invoke(...)["messages"][-1].content` |
| supervisor library | `createSupervisor({ agents: [a.graph], llm, prompt, outputMode })` | `create_supervisor([a], model=..., prompt=..., output_mode=...)` |
| output mode values | `"last_message"` / `"full_history"` | `"last_message"` / `"full_history"` |
| handoff tool | `createHandoffTool({ agentName, description })` | `create_handoff_tool(agent_name=..., description=...)` |
| swarm | `createSwarm({ agents, defaultActiveAgent })` | `create_swarm(agents, default_active_agent=...)` |
| active agent key | `state.activeAgent` | `state["active_agent"]` |
| swarm agent (per README) | `createReactAgent` from `@langchain/langgraph/prebuilt` | `create_agent` |
| scripted test model | subclass `BaseChatModel`, implement `_generate` | subclass `GenericFakeChatModel`, add `bind_tools` |

### Day 23 — [Streaming & Events: Make It Feel Fast](../week-04-production-projects-and-interviews/day-23-streaming-and-events.md)

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

### Day 24 — [Reliability: Surviving a Bad Day in Production](../week-04-production-projects-and-interviews/day-24-reliability.md)

| Concept | JavaScript | Python |
|---|---|---|
| client retries | `new ChatGroq({ maxRetries })` — default **6**, but a Groq 429 is never retried | `ChatGroq(max_retries=...)` — default **2**, 429s included (waits for `retry-after`) |
| client timeout | call option `{ timeout: ms }` → `DOMException` | `ChatGroq(request_timeout=seconds)` |
| rate limiter | hand-rolled / library | `InMemoryRateLimiter` → `rate_limiter=` |
| runnable retry | `.withRetry({ stopAfterAttempt })` | `.with_retry(stop_after_attempt=...)` |
| runnable fallback | `.withFallbacks([b])` or `({ fallbacks: [b] })` | `.with_fallbacks([b])` |
| middleware param | `createAgent({ middleware: [...] })` | `create_agent(..., middleware=[...])` |
| model retry | `modelRetryMiddleware({ maxRetries, onFailure, initialDelayMs })` | `ModelRetryMiddleware(max_retries=, on_failure=, initial_delay=)` |
| model fallback | `modelFallbackMiddleware(m1, m2)` | `ModelFallbackMiddleware(m1, m2)` |
| model call limit | `modelCallLimitMiddleware({ runLimit, threadLimit, exitBehavior })` | `ModelCallLimitMiddleware(run_limit=, thread_limit=, exit_behavior=)` |
| limit error (`"error"`) | `ModelCallLimitMiddlewareError` | `ModelCallLimitExceededError` |
| tool retry | `toolRetryMiddleware({ maxRetries, tools })` | `ToolRetryMiddleware(max_retries=, tools=)` |
| tool call limit | `toolCallLimitMiddleware({ toolName, runLimit })` | `ToolCallLimitMiddleware(tool_name=, run_limit=)` |
| PII | `piiMiddleware("email", { strategy })` | `PIIMiddleware("email", strategy=, apply_to_tool_results=)` |
| PII mask output | `a***@example.com` | `ayesha.khan@****.com` |
| node retry | `addNode(n, fn, { retryPolicy: { maxAttempts, initialInterval(ms), retryOn } })` | `add_node(n, fn, retry_policy=RetryPolicy(max_attempts=, initial_interval=(s), retry_on=))` |
| node retry default | retried a plain `Error` | **skips** `RuntimeError`, `ValueError`, `OSError` (incl. `TimeoutError`) |
| node timeout | `{ timeout: ms }` | `timeout=seconds` — **async nodes only** |
| node error handler | — | `error_handler=fallback_node` |
| ToolNode on exception | **returns content** (raw message) | **re-raises** unless `handle_tool_errors=` |

### Day 25 — [Observability & Evaluation: Know Whether It Works](../week-04-production-projects-and-interviews/day-25-observability-and-evaluation.md)

| Concept | JavaScript | Python |
|---|---|---|
| callback: chat model start | `handleChatModelStart` | `on_chat_model_start` |
| callback: model end | `handleLLMEnd(output)` | `on_llm_end(response)` |
| callback: tool | `handleToolStart` / `handleToolEnd` / `handleToolError` | `on_tool_start` / `on_tool_end` / `on_tool_error` |
| handler shape | plain object with methods | subclass `BaseCallbackHandler` |
| run labels | `{ runName, tags, metadata }` | `{"run_name", "tags", "metadata"}` |
| usage per model | sum `usage_metadata` yourself | `get_usage_metadata_callback()` |
| trace a function | `traceable(fn, { name })` from `langsmith/traceable` | `@traceable(name=...)` from `langsmith` |
| LLM-as-judge | `createLLMAsJudge({ prompt, judge, feedbackKey })` | `create_llm_as_judge(prompt=, judge=, feedback_key=)` |
| judge call | `await ev({ inputs, outputs, referenceOutputs })` | `ev(inputs=, outputs=, reference_outputs=)` |
| trajectory match | `createTrajectoryMatchEvaluator({ trajectoryMatchMode })` | `create_trajectory_match_evaluator(trajectory_match_mode=)` |
| LangSmith experiment | `evaluate(target, { data, evaluators })` | `evaluate(target, data=, evaluators=)` |
| offline experiment | not available in our tests (401 without a key) | `upload_results=False` (beta) |

### Day 26 — [MCP & the Vercel AI SDK: Tools Across Boundaries](../week-04-production-projects-and-interviews/day-26-mcp-and-ai-sdk.md)

| Concept | JavaScript | Python |
|---|---|---|
| server | `new McpServer({ name, version })` | `FastMCP("name")` |
| tool | `server.registerTool(name, { description, inputSchema }, handler)` | `@mcp.tool()` + type hints + docstring |
| resource | `server.registerResource(name, uri, meta, handler)` | `@mcp.resource("notes://syllabus")` |
| prompt | `server.registerPrompt(name, { argsSchema }, handler)` | `@mcp.prompt()` |
| run on stdio | `server.connect(new StdioServerTransport())` | `mcp.run(transport="stdio")` |
| run on HTTP | `StreamableHTTPServerTransport` in your framework | `mcp.run(transport="streamable-http")` |
| raw client | `Client` + `StdioClientTransport` | `ClientSession` + `stdio_client` |
| adapter | `new MultiServerMCPClient({ mcpServers: {...} })` | `MultiServerMCPClient({...})` |
| get tools | `await client.getTools()` | `await client.get_tools()` |
| tool result | a **string** | a **list of content blocks** |
| sync invoke | works | **`NotImplementedError`** — async only |
| logging | `console.error` (stderr) | `logging` (stderr) — never `print` |
| AI SDK | `ai`, `@ai-sdk/*` | none — use LangChain |

### Day 27 — [Deployment & Architecture: From Laptop to a Million Students](../week-04-production-projects-and-interviews/day-27-deployment-and-architecture.md)

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


## Week 5 — The Model Layer

### Day 29 — [Open & Local Models: Run AI on Your Own Machine](../week-05-the-model-layer/day-29-open-and-local-models.md)

| Task | JavaScript | Python |
|---|---|---|
| Install the runner | `npm i @huggingface/transformers` | `pip install torch transformers` |
| Weight format used | ONNX (`onnx/*.onnx`) | safetensors (`model.safetensors`) |
| Load a model | `await pipeline("text-generation", id, { dtype: "q4" })` | `AutoModelForCausalLM.from_pretrained(id, dtype=...)` |
| Choose precision | `dtype: "fp32" \| "fp16" \| "q8" \| "q4"` (picks a file) | `dtype=torch.float32 \| torch.bfloat16` (converts on load) |
| Default precision on CPU | fp32 (and unknown strings fall back to fp32) | the model's own `torch_dtype` (bf16 here) |
| Apply the chat template | pass `[{ role, content }]` to the pipeline | `tok.apply_chat_template(messages, add_generation_prompt=True)` |
| Limit the answer | `max_new_tokens: 60` (pipeline default 256) | `max_new_tokens=60` (`generate()` default: 20 new tokens) |
| Repeatable output | `do_sample: false` | `do_sample=False` |
| LangChain chat model | your own `BaseChatModel` subclass (§4.3) | `ChatHuggingFace(llm=HuggingFacePipeline...)` |
| Token counts | you fill `usage_metadata` yourself | `usage_metadata` is `None`; count with `chat.tokenizer` |
| Strip the prompt from output | `generated_text.at(-1).content` | `return_full_text: False` |
| Offline switch | `env.allowRemoteModels = false` | `HF_HUB_OFFLINE=1` before import |
| Licence lookup | `fetch("https://huggingface.co/api/models/<id>")` → `cardData.license`, `gated` | `HfApi().model_info(id)` → `card_data.license`, `gated` |
| Local server client | `new ChatOllama({ model })` | `ChatOllama(model=...)` |
| Free memory | `await generator.dispose()` | `del model` |

### Day 30 — [Inference & Serving: What Happens Between Request and Token](../week-05-the-model-layer/day-30-inference-and-serving.md)

| Task | JavaScript | Python |
|---|---|---|
| Install the client | `npm i @langchain/openai` | `pip install langchain-openai` |
| Point at your server | `configuration: { baseURL: "http://127.0.0.1:8030/v1" }` | `base_url="http://127.0.0.1:8030/v1"` |
| Dummy key | `apiKey: "not-needed"` | `api_key="not-needed"` |
| Answer length | `maxTokens: 40` | `max_tokens=40` |
| Timeout unit | `timeout: 60_000` (milliseconds) | `timeout=60` (seconds) |
| Default retries | `maxRetries: 6` → 93 s on a dead server | `max_retries=None` → openai default 2 → 7.4 s |
| Fail fast | `maxRetries: 0` | `max_retries=0` |
| Timeout error | `TimeoutError: Request timed out.` | `OpenAITimeoutError: Request timed out.` |
| Wrong path (404) | `Error: 404 {"detail":"Not Found"}` | `OpenAIModelNotFoundError: Error code: 404 - {'detail': 'Not Found'}` |
| Server down | `Error: Connection error.` | `OpenAIConnectionError: Connection error.` |
| Stream | `for await (const c of await llm.stream(q))` | `for c in llm.stream(q)` |
| Join stream chunks | `full = full ? full.concat(c) : c` | `full = c if full is None else full + c` |
| Token usage | `reply.usage_metadata` | `reply.usage_metadata` |
| Finish reason | `reply.response_metadata.finish_reason` | `reply.response_metadata["finish_reason"]` |
| Run 8 at once | `await Promise.all(qs.map(ask))` | `await asyncio.gather(*(ask(q) for q in qs))` |
| Clock | `performance.now()` (ms) | `time.perf_counter()` (s) |
| The server itself | — (Python only today) | FastAPI + transformers, §5.5 |

### Day 31 — [Fine-Tuning: Teaching a Model New Habits](../week-05-the-model-layer/day-31-fine-tuning.md)

| Job | JavaScript | Python |
|---|---|---|
| Validate a training row | Zod `z.object(...).superRefine(...)` | Pydantic `BaseModel` + `@model_validator` |
| Exact keys only | `z.strictObject({...})` | `set(reply) == {"answer", "quiz"}` |
| Compact JSON | `JSON.stringify(obj)` (no spaces by default) | `json.dumps(obj, separators=(",", ":"))` |
| Write JSONL | `xs.map(JSON.stringify).join("\n")` | `f.write(e.model_dump_json() + "\n")` |
| Count LoRA parameters | — (arithmetic: `r * (dIn + dOut)`) | `model.print_trainable_parameters()` |
| Train the adapter | — (Python only) | `get_peft_model` + a PyTorch loop |
| Save / load / merge | — | `save_pretrained` · `PeftModel.from_pretrained` · `merge_and_unload()` |
| Call the tuned model | `new ChatOpenAI({ configuration: { baseURL } })` | `ChatOpenAI(base_url=...)` |
| Check the habit | `Reply.safeParse(JSON.parse(text))` | `json.loads` + key check |

### Day 32 — [Dataset Engineering: Good Data In, Good Model Out](../week-05-the-model-layer/day-32-dataset-engineering.md)

| Task | JavaScript | Python |
|---|---|---|
| SHA-256 of text | `createHash("sha256").update(s, "utf8").digest("hex")` | `hashlib.sha256(s.encode("utf-8")).hexdigest()` |
| Unicode NFKC | `s.normalize("NFKC")` | `unicodedata.normalize("NFKC", s)` |
| Lower-case key (same result) | `toLowerCase()` | `.lower()` — not `.casefold()` |
| Collapse whitespace | `s.replace(/\s+/g, " ").trim()` | `re.sub(r"\s+", " ", s).strip()` |
| Words in any language | `t.match(/[\p{L}\p{N}]+/gu)` | `re.findall(r"[^\W_]+", t)` |
| Shingles | loop + `text.slice(i, i + k)` (UTF-16 units) | `{text[i:i+k] for i in …}` (code points) |
| Set intersection | loop with `b.has(x)` | `a & b` |
| Regex test, many strings | `/…/i` with `.test` — **no `g`** | `re.compile(…, re.I).search` (no state) |
| Replace all matches | `.replace(/…/g, fn)` | `rx.sub(fn, text)` |
| Scripted model | `FakeListChatModel` from `@langchain/core/utils/testing` | `FakeListChatModel` from `langchain_core.language_models.fake_chat_models` |
| Schema check | `z.object({...}).safeParse(item)` | `QA.model_validate(item)` + `except ValidationError` |
| "Ends with ?" | `z.string().endsWith("?")` | `Field(pattern=r"\?$")` |
| Bad JSON error | `Unexpected token 'S', "Sure! Here"... is not valid JSON` | `Expecting value: line 1 column 1 (char 0)` |
| Missing field message | `Invalid input: expected string, received undefined` | `Field required` |
| JSONL line | `JSON.stringify(r)` | `json.dumps(r, ensure_ascii=False, separators=(",", ":"))` |
| Write text file | `writeFileSync(name, text)` (writes `\n` as is) | `open(name, "w", encoding="utf-8", newline="\n")` |
| Keep insertion order, unique | `new Set(...)` | `dict.fromkeys(...)` |

### Day 33 — [Multimodal: Images, Documents and Voice](../week-05-the-model-layer/day-33-multimodal.md)

| Concept | JavaScript | Python |
|---|---|---|
| Standard image block | `{ type: "image", data, mimeType }` | `{"type": "image", "base64": ..., "mime_type": ...}` |
| Normalised view of blocks | `msg.contentBlocks` | `msg.content_blocks` |
| Old 0.3 block (`source_type`) | passed to your model **unchanged** | **converted** to v1 before your model sees it |
| `data:` prefix inside the base64 field | sent to Gemini as-is | `binascii.Error` before sending |
| Wrong MIME type | sent as-is | sent as-is |
| Read the reply text | `res.text` | `res.text` |
| Local VLM class | `AutoModelForImageTextToText` (Transformers.js) | `AutoModelForImageTextToText` (transformers) |
| Image splitting option | `processor(prompt, images, { do_image_splitting })` | `AutoProcessor.from_pretrained(..., do_image_splitting=...)` |
| Bytes → image | `RawImage.fromBlob(new Blob([buf]))` | `Image.open(io.BytesIO(raw))` |
| Read a WAV file | `wavefile` package | standard `wave` + NumPy |
| Resample to 16 kHz | `wav.toSampleRate(16000)` (built in) | needs `torchaudio` (else `ImportError`) |
| Wrong-rate audio, undeclared | wrong words, no error | wrong words (a 25–40 s loop here), no error |
| Image in a text-only chat template | base64 pasted into the prompt as text (§8 Ex 3) | `TypeError` (§8 Ex 3) |
| Run a TTS process safely | `execFileSync(cmd, [args])` | `subprocess.run([cmd, *args], check=True)` |
| Image generation result | `result.data[0].b64_json` | `result.data[0].b64_json` |

### Day 34 — [Cost & Latency: Making It Cheap and Fast](../week-05-the-model-layer/day-34-cost-and-latency.md)

| Concept | JavaScript | Python |
|---|---|---|
| Custom chat model | `class X extends BaseChatModel` + `_generate`, `_llmType()` | `class X(BaseChatModel)` + `_generate`, `_llm_type` property |
| Custom streaming | `async *_streamResponseChunks(messages)` | `def _stream(self, messages, ...)` |
| Model params in the cache key | `_identifyingParams()` | `_identifying_params` property |
| Global cache | `cache: true` on each model (`InMemoryCache.global()`) | `set_llm_cache(InMemoryCache())` — every model |
| Per-model cache | `new ChatX({ cache: new InMemoryCache() })` | `ChatX(cache=InMemoryCache())` |
| Cache-hit `usage_metadata` | **all zeros** — and the first message is zeroed too | original counts **plus** `total_cost: 0` |
| `ChatGroq` cache key | **no** model name, **no** temperature (1.3.1) | model name, temperature, every constructor setting |
| Inspect the key (internal) | `m._getSerializedCacheKeyParametersForCall({})` | `m._get_llm_string()` |
| Batch with a cap | `batch(xs, { maxConcurrency: 4 })` | `batch(xs, config={"max_concurrency": 4})` |
| Batch default with no cap | all inputs at once (40 of 40 measured) | thread pool default (12 on 8 cores) |
| Errors in a batch | `batch(xs, opts, { returnExceptions: true })` | `batch(xs, return_exceptions=True)` |
| Output cap on `ChatGroq` | `maxTokens` → sent as `max_completion_tokens` | `max_tokens` → sent as `max_tokens` |
| Cached-input tokens (if reported) | `usage_metadata.input_token_details?.cache_read` | `usage_metadata["input_token_details"]["cache_read"]` |
| Timing | `performance.now()` (ms) | `time.perf_counter()` (s) |

### Day 35 — [AI Security: Attack Your Own App Before Someone Else Does](../week-05-the-model-layer/day-35-ai-security.md)

| Concept | JavaScript | Python |
|---|---|---|
| secure random token | `randomBytes(4).toString("hex")` | `secrets.token_hex(4)` |
| tag characters in a regex | `/[\u{E0000}-\u{E007F}]/gu` (needs `u`) | `"[\U000E0000-\U000E007F]"` (normal string) |
| make a tag character | `String.fromCodePoint(0xe0000 + c)` | `chr(0xE0000 + c)` |
| host of a URL | `new URL(u).hostname` (throws on bad URL) | `urlparse(u).hostname` (may be `None`) |
| strict email domain | `/^[^@\s]+@([^@\s]+)$/.exec(a)` | `re.fullmatch(r"[^@\s]+@([^@\s]+)", a)` |
| HTML escape | hand-written map (or `sanitize-html` 2.18.0) | `.replace(...)` chain (or `html.escape`, `nh3` 0.3.7) |
| custom tool guard | `createMiddleware({ wrapToolCall })` | `@wrap_tool_call` |
| check / replace the answer | `createMiddleware({ afterModel })` | `@after_model` |
| replace a message | return `AIMessage` with the **same `id`** | same |
| approval middleware | `humanInTheLoopMiddleware({ interruptOn })` | `HumanInTheLoopMiddleware(interrupt_on=...)` |
| skip approval for some calls | `when: (req) => …` on the tool's config | `"when": lambda req: …` |
| read the pending action | `result.__interrupt__[0].value.actionRequests` | `result["__interrupt__"][0].value["action_requests"]` |
| reject message reaches the model as | **exactly** your text | wrapped: ``User rejected the tool call for `name` with reason: …`` |
| install-time code | npm `postinstall` (silent by default) | build scripts in source packages |
| safe weight format | read safetensors by hand (JSON + typed array) | `safetensors` library; `torch.load` defaults to `weights_only=True` |


## Week 6 — Advanced Agents, Product & Career

### Day 36 — [Context Engineering & the Five Agent Patterns](../week-06-advanced-agents-product-and-career/day-36-context-engineering-and-agent-patterns.md)

| Concept | JavaScript | Python |
|---|---|---|
| State with an adding counter | `round: Annotation({ reducer: (a, b) => a + b, default: () => 0 })` | `round: Annotated[int, operator.add]` (pass `"round": 0` at the start) |
| Gate / router edge | `.addConditionalEdges("a", fn, ["b", END])` | `b.add_conditional_edges("a", fn, ["b", END])` |
| Join after a fan-out | `.addEdge(["x", "y", "z"], "combine")` | `b.add_edge(["x", "y", "z"], "combine")` |
| Orchestrator fan-out | `new Send("work", payload)` | `Send("work", payload)` |
| Node named like a state key | **error**: "already being used as a state attribute" | accepted (measured) |
| Unknown route label | `Error: Branch condition returned unknown or null destination` | `KeyError: 'history'` |
| Default recursion limit | 25 | **10,007** (`LANGGRAPH_DEFAULT_RECURSION_LIMIT`) |
| Agent | `createAgent({ model, tools, systemPrompt, middleware })` | `create_agent(model, tools, system_prompt=..., middleware=[...])` |
| Clear old tool results | `contextEditingMiddleware({ edits: [new ClearToolUsesEdit({ trigger: { tokens: 500 }, keep: { messages: 1 } })] })` | `ContextEditingMiddleware(edits=[ClearToolUsesEdit(trigger=500, keep=1)])` |
| Where clearing happens | written **into state** | only in the request sent to the model |
| Message text / type | `m.text`, `m.type` | `m.text`, `m.type` |
| To-do list | `todoListMiddleware()` from `langchain` | `TodoListMiddleware()` from `langchain.agents.middleware` |
| Deep agent | `createDeepAgent({ model, systemPrompt, middleware })` from `deepagents` | `create_deep_agent(model=..., system_prompt=..., middleware=[...])` |

### Day 37 — [Advanced Retrieval: Graphs, SQL and Agentic Search](../week-06-advanced-agents-product-and-career/day-37-advanced-retrieval.md)

| Concept | JavaScript | Python |
|---|---|---|
| Built-in SQLite | `import { DatabaseSync } from "node:sqlite"` (Node 24) | `import sqlite3` |
| Open read-only | `new DatabaseSync(path, { readOnly: true })` | `sqlite3.connect(f"file:{path}?mode=ro", uri=True)` |
| Write on read-only | `Error: attempt to write a readonly database` | `OperationalError: attempt to write a readonly database` |
| Authorizer | `db.setAuthorizer((action, a1, a2, dbName, view) => …)` | `db.set_authorizer(fn)` — same five arguments |
| Constants | `constants.SQLITE_READ` (from `node:sqlite`) | `sqlite3.SQLITE_READ` |
| Denied read | `Error: access to students.email is prohibited` | `DatabaseError: access to students.email is prohibited` |
| Denied write | `Error: not authorized` | `DatabaseError: not authorized` |
| Two statements in one string | `prepare()` **silently runs only the first** | `execute()` raises `ProgrammingError` |
| Runs every statement | `db.exec()` — never for model SQL | `executescript()` — never for model SQL |
| Lazy rows for a cap | `stmt.iterate(...params)` + `break` | `cur.fetchmany(n + 1)` |
| Parameters | `prepare(sql).all(a, b)` | `execute(sql, (a, b))` |
| Row shape | plain object `{ title, avg_score }` | `sqlite3.Row` → `dict(row)` |
| `ROUND(59.0, 1)` | prints `59` | prints `59.0` |
| Stop a long query | no progress handler in `node:sqlite` | `set_progress_handler(fn, n)` → `OperationalError: interrupted` |
| Structured output validates? | **No** (base class) — call `Schema.parse()` | **Yes** — raises `ValidationError` |
| Scripted model message for structured output | must be `AIMessageChunk` | `AIMessage` works |
| Graph lookup "into a node" | `g.in(o, r)` | `g.into(o, r)` (`in` is a keyword) |

### Day 38 — [Emerging Agents: Browsers, Computers and Agents That Talk to Agents](../week-06-advanced-agents-product-and-career/day-38-emerging-agents.md)

| Concept | JavaScript | Python |
|---|---|---|
| install the browser | `npx playwright install chromium` | `playwright install chromium` |
| start | `await chromium.launch()` | `sync_playwright().start().chromium.launch()` |
| fresh profile | `await browser.newContext()` | `browser.new_context()` |
| intercept every request | `await context.route("**/*", handler)` | `context.route("**/*", handler)` |
| serve / block | `route.fulfill({ contentType, body })` / `route.abort("blockedbyclient")` | `route.fulfill(content_type=, body=)` / `route.abort("blockedbyclient")` |
| accessibility tree | `await page.locator("body").ariaSnapshot()` | `page.locator("body").aria_snapshot()` |
| find by label | `page.getByLabel("Email")` | `page.get_by_label("Email")` |
| find by role + name | `page.getByRole("button", { name: "Register" })` | `page.get_by_role("button", name="Register")` |
| pick an option | `.selectOption({ label }, { timeout })` | `.select_option(label=, timeout=)` |
| timeout error | `locator.fill: Timeout 2000ms exceeded.` | `TimeoutError`: `Locator.fill: Timeout 2000ms exceeded.` |
| blocked navigation | `page.goto: net::ERR_BLOCKED_BY_CLIENT at …` | `Page.goto: net::ERR_BLOCKED_BY_CLIENT at …` |
| a tool | `tool(fn, { name, description, schema: z.object(...) })` | `@tool` + type hints + docstring |
| scripted model | `class extends BaseChatModel` + `_generate` | `class (BaseChatModel)` + `_generate` → `ChatResult` |
| A2A package | `@a2a-js/sdk` (+ `express`) | `a2a-sdk[http-server]` (+ `uvicorn`) |
| A2A server | `DefaultRequestHandler(card, store, executor)` + `jsonRpcHandler` | `DefaultRequestHandler(agent_executor=, task_store=, agent_card=)` + `create_jsonrpc_routes` |
| publish results | `bus.publish(AgentEvent.task / artifactUpdate / statusUpdate)` | `TaskUpdater.add_artifact` / `.update_status` |
| A2A client | `new ClientFactory().createFromUrl(base)` | `A2ACardResolver` + `create_client(agent=card)` |
| send | `await client.sendMessage({ message })` → a Task or Message | `async for event in client.send_message(req)` |
| state name | `taskStateToJSON(state)` | `TaskState.Name(state)` |
| skill frontmatter | regex with `\r?\n` | regex with `\n` (`read_text` normalises) |

### Day 39 — [AI Product Engineering: Building Something People Trust and Use](../week-06-advanced-agents-product-and-career/day-39-ai-product-engineering.md)

| Idea | JavaScript | Python |
|---|---|---|
| Choose the root run id | `invoke(input, { runId })` | `invoke(inp, {"run_id": run_id})` |
| Id made by the library (none passed) | a string | a `uuid.UUID` object |
| New UUID | `randomUUID()` from `node:crypto` | `str(uuid.uuid4())` |
| SHA-256 hex | `createHash("sha256").update(s).digest("hex")` | `hashlib.sha256(s.encode()).hexdigest()` |
| Hex → integer | `parseInt(hex.slice(0, 8), 16)` | `int(hex_digest[:8], 16)` |
| Normal curve | no `erf`: approximation (error < 2 × 10⁻⁷) | `math.erf` (exact) |
| p-value for z = 4.483 | `7.360e-6` | `7.353e-06` — both print `0.000007` at 6 decimals |
| Seeded random numbers | Day 0C's `makeRng` | Day 0C's `make_rng` — identical sequence |
| Tiny HTTP server | `http.createServer`, `listen(0, host, cb)` | `ThreadingHTTPServer`, `BaseHTTPRequestHandler` |
| 4xx reply in the client | `fetch` resolves; read `res.status` | `urllib` raises `HTTPError`; read `err.code` |
| Validate a thumb | `v === 1 \|\| v === -1` (a `true` fails) | needs `not isinstance(v, bool)` (`True == 1`) |
| JSON `4.0` as a rating | parsed as `4`, accepted | parsed as `4.0` (a float), rejected by `isinstance(v, int)` |
| Append a JSONL line | `appendFileSync(path, line)` | `open(path, "a").write(line)` |
| LangSmith feedback | `client.createFeedback(runId, key, { score })` | `client.create_feedback(run_id, key=…, score=…)` |
| Peeking simulation time (measured) | about 1 s | about 9 s |

### Day 40 — [Final Capstone & Career: Ship It, Prove It, Get Hired](../week-06-advanced-agents-product-and-career/day-40-final-capstone-and-career.md)

| Concept | JavaScript | Python |
|---|---|---|
| A custom chat model | `class X extends BaseChatModel`, `_generate` returns `{ generations: [{ message, text }] }` | `class X(BaseChatModel)`, `_generate` returns `ChatResult(generations=[ChatGeneration(message=...)])` |
| Fields on the model | plain properties set in the constructor | Pydantic fields: `ms_per_call: float = 40` |
| Per-request data in a node | second argument: `(state, config) => config.configurable.route` | a `config: RunnableConfig` parameter: `config["configurable"]["route"]` |
| Where a `Command` node can go | `{ ends: ["agent", "tools"] }` | `-> Command[Literal["agent", "tools"]]` |
| The paused payload | `out.__interrupt__[0].value` | `out["__interrupt__"][0].value` |
| Step cap | `recursionLimit: 10` | `"recursion_limit": 10` |
| A tool | `tool(fn, { name, description, schema: z.object(...) })` | `@tool` with a docstring and type hints |
| Wall-clock timing | `performance.now()` (ms) | `time.perf_counter()` (seconds × 1000) |
| Tokens from a tool call | `JSON.stringify(tool_calls)` | `json.dumps(tool_calls, separators=(",", ":"))` |
| Run only when called directly | `import.meta.url === pathToFileURL(process.argv[1]).href` | `if __name__ == "__main__":` |
| Fail the CI step | `process.exitCode = 1` | `sys.exit(1)` |
| Printing $0.0008955 to 6 places | `0.000895` | `0.000896` |
