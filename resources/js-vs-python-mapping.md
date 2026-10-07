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

> ⚠️ **Naming trap you'll hit all week.** The raw provider SDKs use `snake_case` in *both*
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

### Day 03 — [JS & Python Essentials for AI · Why LangChain Exists](../week-01-foundations/day-03-js-python-essentials-and-why-langchain.md)

| | JavaScript | Python |
|---|---|---|
| Sync option | ❌ none — always async | ✅ `invoke` (sync) and `ainvoke` (async) |
| Parallel | `Promise.all([...])` | `asyncio.gather(*tasks)` |
| Tolerant parallel | `Promise.allSettled` | `gather(..., return_exceptions=True)` |
| Timing | `console.time` / `timeEnd` | `time.time()` deltas |
| Spread into call | `f(...args)` | `f(*args)` |
| Yield many | `for (const p of parts) yield p` | `yield from parts` |
| Schema errors | `result.error.issues` | `e.errors()` |
| Schema → dict | `schema.parse(x)` | `Model.model_validate(x)` |
| Method names | `withStructuredOutput`, `withRetry` | `with_structured_output`, `with_retry` |

### Day 04 — [LangChain Models: invoke, stream, batch & Message Types](../week-01-foundations/day-04-langchain-models.md)

| | JavaScript | Python |
|---|---|---|
| Params | `maxTokens`, `topP`, `maxRetries` | `max_tokens`, `top_p`, `max_retries` |
| Universal loader | `await initChatModel("groq:...")` | `init_chat_model("groq:...")` — no await |
| Chunk accumulation | `full.concat(chunk)` | `full + chunk` |
| Batch concurrency | `{ maxConcurrency: 2 }` | `config={"max_concurrency": 2}` |
| Message import | `from "@langchain/core/messages"` | `from langchain_core.messages import ...` |
| Trimming | `trimMessages(msgs, {...})` | `trim_messages(msgs, ...)` |
| Text accessor | `res.text` | `res.content` (or `res.text` / `res.text()`) |
| Async variants | none — always async | `ainvoke`, `astream`, `abatch` |

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
| Google embeddings | `model: "text-embedding-004"` | `model="models/text-embedding-004"` ⚠️ prefix |
| Query | `await embeddings.embedQuery(s)` | `embeddings.embed_query(s)` |
| Documents | `await embeddings.embedDocuments([...])` | `embeddings.embed_documents([...])` |
| Cache class | `@langchain/classic/embeddings/cache_backed` | `langchain_classic.embeddings` |
| Cache factory | `CacheBackedEmbeddings.fromBytesStore(...)` | `CacheBackedEmbeddings.from_bytes_store(...)` |
| Byte store | `InMemoryStore` (`@langchain/classic/storage/in_memory`) | `InMemoryByteStore` (`langchain_core.stores`) |
| Vector maths | manual loops (or a lib) | **numpy** — use it |

> ⚠️ **Google model-name gotcha:** Python needs the `models/` prefix
> (`"models/text-embedding-004"`), JS does not (`"text-embedding-004"`). This trips people up
> constantly when porting code between the two.

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

Chaining differs slightly too: JS `.addNode()` returns the builder so you can chain the whole
thing fluently. Python's methods return the builder as well and *can* be chained, but the
idiomatic style is one statement per line — that's what the docs use and what your reviewers
will expect.

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
| client retries | `new ChatGroq({ maxRetries })` — default **6** | `ChatGroq(max_retries=...)` — default **2** |
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
