# Glossary

Every term in this book, one line each. Terms are marked with the day that introduces them.
Terms from Weeks 2–4 are included so you can look ahead.

← [Back to the main index](../README.md)

---

## A

**Adaptive RAG** *(Day 13)* — Routing each query to a different retrieval strategy (or none) based on its type and complexity.

**Agent** *(Day 16)* — An LLM in a loop that decides which tools to call, observes the results, and repeats until it can answer. Distinguished from a chain by having *control flow the model decides*.

**Agentic RAG** *(Day 13)* — RAG where an agent decides whether to retrieve, what to search for, and whether the results were good enough — rather than always retrieving once.

**AIMessage** *(Day 04)* — The message type representing model output. Carries `content`/`text`, `tool_calls`, `usage_metadata` and `response_metadata`.

**AIMessageChunk** *(Day 04)* — A partial `AIMessage` yielded during streaming. Chunks are addable (`concat` / `+`) so they can be reassembled into a complete message.

**Async iterator** *(Day 03)* — Anything consumable with `for await...of` / `async for`. Streaming responses are async iterators.

---

## B

**Backoff** *(Day 24)* — Waiting longer between each retry (e.g. 0.5 s, 1 s, 2 s). Combine with *jitter* so clients that failed together don't retry together.

**BaseChatModel** *(Day 04)* — The LangChain interface every chat model implements. Takes `BaseMessage[]`, returns `AIMessage`.

**Batch** *(Day 04)* — Running many **independent** inputs concurrently with a concurrency cap. Not for conversation turns, which are sequentially dependent.

**BM25** *(Day 11)* — A classic keyword-ranking algorithm. Combined with vector search to make *hybrid search*.

---

## C

**Calibration (of a judge)** *(Day 25)* — Measuring how often an LLM judge agrees with human labels on the same examples. An uncalibrated judge's score is a number, not a measurement.

**Callback** *(Day 07, 25)* — A hook fired at each step of a Runnable's execution. The mechanism behind LangSmith tracing.

**Cancellation** *(Day 23)* — Stopping a run when nobody is waiting for it. In JS, leaving a stream loop doesn't stop the graph — pass an `AbortSignal`; in Python, closing the stream generator stops it before the next superstep.

**Capacity arithmetic** *(Day 27)* — Estimating peak runs per second, model calls and tokens per run before choosing infrastructure. It usually shows the bottleneck is the provider's rate limit or cost, not compute.

**Chain** *(Day 08)* — A fixed sequence of steps with control flow decided by *you*, not the model. Contrast with **agent**.

**Chain-of-Thought (CoT)** *(Day 02)* — Prompting the model to produce intermediate reasoning before its answer. Works because generated tokens act as working memory.

**Checkpointer** *(Day 20)* — A LangGraph component that saves graph state after each step, enabling persistence, resumption and time travel. Think of it as a video-game save file.

**Chunking** *(Day 09)* — Splitting documents into pieces small enough to embed and retrieve usefully.

**Circuit breaker** *(Day 24)* — A guard that stops calling a dependency after repeated failures, fails fast for a cooldown, then lets one trial call through.

**Command** *(Day 19)* — A node return value that updates state *and* routes (`goto`) in one step. Its destination is added to — not substituted for — any static edges from that node.

**Constrained decoding** *(Day 02, 06)* — Masking the sampler at each step so only schema-valid tokens can be generated. The strongest structured-output guarantee.

**Context engineering** *(Day 22)* — Deciding exactly what each model call sees — instructions, tools, history, retrieved data. Most multi-agent benefits are context-engineering benefits.

**Context window** *(Day 01)* — The maximum number of tokens a model can process in one call, counting **input and output together**. A hard architectural limit.

**Contextual compression** *(Day 13)* — Filtering or shortening retrieved documents to just the parts relevant to the query, before passing them to the model.

**Corrective RAG (CRAG)** *(Day 13)* — Grading retrieved documents and, if they're irrelevant, re-retrieving or falling back to web search.

**Cosine similarity** *(Day 10)* — A similarity metric between two vectors, based on the angle between them. The default for embedding comparison.

---

## D

**Dataset (evaluation)** *(Day 25)* — A fixed set of example inputs with reference outputs, answers, facts or trajectories, used to score a system the same way before and after a change.

**Dead letter queue** *(Day 24)* — Where repeatedly-failing items go so they don't block the pipeline and can be inspected later.

**Document** *(Day 09)* — LangChain's container for a piece of text plus its metadata (`pageContent` + `metadata`).

**Dot product** *(Day 10)* — A similarity metric that accounts for both angle and magnitude. Equivalent to cosine when vectors are normalised.

**Dynamic few-shot** *(Day 05, 13)* — Retrieving the k most similar examples per input from a vector store, rather than using a fixed example list.

---

## E

**Edge** *(Day 17)* — A connection between nodes in a LangGraph graph, defining what runs next.

**Embedding** *(Day 10)* — A list of numbers representing the *meaning* of text, such that similar meanings produce nearby vectors.

**Ensemble retriever** *(Day 13)* — Combining results from multiple retrievers (e.g. vector + BM25) with weighted fusion.

**ESM** *(Day 03)* — ECMAScript Modules — `import`/`export` plus top-level `await`. Enabled with `"type": "module"`. LangChain JS is ESM-first.

**Evaluator** *(Day 25)* — A function that scores an output: code checks (exact, contains, schema), trajectory matches, LLM-as-judge, or human review.

---

## F

**Fallback** *(Day 04)* — An alternative Runnable invoked when the primary fails. `.withFallbacks()` / `.with_fallbacks()`.

**Few-shot prompting** *(Day 02, 05)* — Including worked input→output examples in the prompt. In-context learning, not training.

**Finish reason** *(Day 01)* — Why generation stopped: `stop` (natural), `length` (hit `max_tokens`), `tool_calls`.

**Frequency penalty** *(Day 01)* — Reduces a token's probability each time it repeats. Fights literal repetition.

**Function calling** *(Day 02)* — The older name for **tool calling**. Same mechanism.

---

## G

**Graceful shutdown** *(Day 27)* — On `SIGTERM`, stop accepting work, let in-flight runs finish up to a deadline, then close pools — so deploys don't drop conversations.

**Graph RAG** *(Day 13)* — Retrieval over a knowledge graph of entities and relationships rather than (or alongside) flat text chunks.

**Greedy decoding** *(Day 01)* — Always picking the highest-probability token. What `temperature: 0` does. **Not** the same as deterministic.

---

## H

**Hallucination** *(Day 01)* — Fluent, confident output that isn't true. A consequence of next-token prediction having no truth-check step.

**Handoff** *(Day 22)* — A tool whose result transfers control to another agent (a `Command` with `graph: PARENT`) and records it as the active agent, so the user keeps talking to the specialist.

**HNSW** *(Day 11)* — Hierarchical Navigable Small World — the most common approximate-nearest-neighbour index in vector databases.

**Human-in-the-loop (HITL)** *(Day 21)* — Pausing execution for human approval, rejection or editing before continuing.

**HumanMessage** *(Day 04)* — The message type representing user input.

**Hybrid search** *(Day 11)* — Combining keyword (BM25) and vector search, then fusing the rankings.

**HyDE** *(Day 13)* — Hypothetical Document Embeddings: generate a fake ideal answer, embed *that*, and retrieve with it. Often beats embedding the raw question.

---

## I

**Idempotency key** *(Day 24)* — A unique id for one logical action (a refund, an email, a run submission) so a retry or replay is recognised and not executed twice.

**Interrupt** *(Day 21)* — LangGraph's mechanism for pausing a graph mid-execution and resuming later, used for human-in-the-loop.

**invoke** *(Day 04)* — The Runnable method that takes one input and returns one complete output.

---

## J

**Jitter** *(Day 03)* — Randomness added to retry delays so many clients don't retry in lockstep (the *thundering herd*).

**JSON mode** *(Day 02, 06)* — A provider setting guaranteeing syntactically valid JSON output — but *not* your schema.

**JSON Schema** *(Day 06)* — The format Zod/Pydantic schemas are converted into before being sent to the model.

---

## K

**KV-cache** *(Day 01)* — Cached attention keys/values for already-processed tokens. Why input tokens are cheaper than output tokens, and what prompt caching exploits.

---

## L

**LangGraph** *(Day 17+)* — LangChain's library for stateful, cyclic workflows: nodes, edges, typed state, checkpointing, interrupts. Use it when control flows in a loop.

**LangGraph server** *(Day 27)* — A runtime that serves graphs listed in `langgraph.json` as an HTTP API — threads, runs, streaming, interrupts, background runs. Run locally with `langgraph dev`; it rejects graphs compiled with their own checkpointer.

**LangSmith** *(Day 25)* — LangChain's observability and evaluation platform: traces, datasets, evaluators, experiments.

**LCEL** *(Day 07)* — LangChain Expression Language. Composition via `.pipe()` / `|` on the `Runnable` interface. Builds a directed **acyclic** graph.

**LLM-as-judge** *(Day 25)* — Using a model to grade outputs against a rubric (correctness, groundedness, helpfulness). Prefer binary scores with reasoning, a different model family, and calibration against humans.

**Logits** *(Day 01)* — Raw scores the model produces for every token in its vocabulary, before softmax turns them into probabilities.

**Lost in the middle** *(Day 01)* — Models attend more reliably to the start and end of a long context than to the middle. An argument for retrieving few, relevant chunks.

---

## M

**max_tokens** *(Day 01)* — A cap on **output** tokens. Truncates mid-sentence; does not make the model concise.

**MCP** *(Day 26)* — Model Context Protocol. A standard for exposing tools, resources and prompts to LLM applications over stdio/HTTP/SSE.

**Memory** *(Day 14)* — Any strategy for deciding what past information to include in the next request. LLMs have none natively.

**MessagesPlaceholder** *(Day 05)* — A slot in a chat template where an **array** of messages is spliced in, preserving roles. Usually conversation history.

**Middleware (agent)** *(Day 24)* — Hooks passed to `createAgent` / `create_agent` that run before or after model calls or wrap model and tool calls — retries, fallbacks, call limits, PII redaction, summarisation.

**MMR** *(Day 13)* — Maximal Marginal Relevance. Retrieval that balances relevance against diversity, avoiding five near-duplicate chunks.

**Model Context Protocol (MCP)** *(Day 26)* — An open protocol for exposing tools, resources and prompts from a server to any AI client over stdio or Streamable HTTP. Build a capability once; any MCP client can use it.

**Multi-query retrieval** *(Day 13)* — Generating several rephrasings of a question, retrieving for each, and merging results.

---

## N

**Namespace (store)** *(Day 18)* — The tuple/array path that scopes long-term store entries, e.g. `("students", id)` — what makes store memory cross threads but stay per user.

**Node** *(Day 17)* — A step in a LangGraph graph. A function that receives state and returns a state update.

**Nucleus sampling** — See **top_p**.

---

## O

**Ollama** *(Setup)* — A tool for running open models locally. Free, offline, no rate limits.

**Output parser** *(Day 06)* — A Runnable that transforms model output into something more useful — a string, a parsed object, a list.

---

## P

**Parent document retriever** *(Day 13)* — Embedding small chunks for precise matching but returning their larger parent chunks for richer context.

**Partial** *(Day 05)* — Pre-filling some template variables, returning a template needing only the rest. Supports functions evaluated at render time.

**pgvector** *(Day 11)* — A Postgres extension adding vector similarity search. Lets you keep vectors next to relational data.

**PII redaction** *(Day 24)* — Detecting personal data (emails, cards, IPs…) and redacting, masking, hashing or blocking it before it reaches the model — via PII middleware.

**Presence penalty** *(Day 01)* — A flat penalty once a token appears at all. Pushes toward new topics.

**Prompt caching** *(Day 01, 24)* — Providers reusing computation for an identical prompt *prefix*, reducing cost and latency. Why stable content goes first.

**Prompt injection** *(Day 02)* — Untrusted input containing instructions the model follows. Mitigated at the prompt layer; *solved* at the authorisation layer.

**PromptTemplate** *(Day 05)* — A parameterised prompt rendering to a single string. `ChatPromptTemplate` renders to a message list — prefer that.

**Pydantic** *(Day 03, 06)* — Python's runtime schema/validation library. The Python equivalent of Zod.

---

## R

**RAG** *(Day 12)* — Retrieval-Augmented Generation. Retrieve relevant documents, put them in the prompt, generate an answer grounded in them.

**Rate limiter** *(Day 24)* — A token bucket or concurrency cap that queues requests instead of exceeding a provider's quota. Share one limiter per provider account.

**ReAct** *(Day 02, 16)* — Reason + Act. The `Thought → Action → Observation` loop underlying every tool-using agent.

**Recursion limit** *(Day 17)* — The maximum number of supersteps in one run (default 25). Hitting it raises `GraphRecursionError` — a sign the loop needs a budget exit.

**Reducer** *(Day 18)* — A function defining how a state key is updated when a node returns a value for it. E.g. append vs overwrite.

**Reranking** *(Day 13)* — Re-scoring retrieved documents with a more accurate (usually cross-encoder) model. Retrieve 20 cheaply, rerank to 5 accurately.

**Retriever** *(Day 13)* — Anything that takes a query and returns relevant documents. A vector store is one source; a retriever is the interface.

**Runnable** *(Day 07)* — LangChain's core interface: `invoke`, `stream`, `batch`, `pipe`. Everything implements it, which is why composition works uniformly.

**RunnableAssign** *(Day 07)* — Adds keys to a dict input, **keeping** existing ones. `RunnablePassthrough.assign()`.

**RunnableBranch** *(Day 07)* — Declarative if/elif/else routing between Runnables.

**RunnableLambda** *(Day 07)* — Wraps any single-argument function as a Runnable.

**RunnableParallel** *(Day 07)* — Runs several Runnables concurrently on the same input, collecting results into an object. **Replaces** the input.

**RunnablePassthrough** *(Day 07)* — The identity Runnable. Carries the input forward alongside computed values.

**RunnableSequence** *(Day 07)* — Sequential composition. What `.pipe()` / `|` builds.

---

## S

**Sampling** *(Day 01)* — Selecting one token from the probability distribution. Where temperature and top_p apply.

**Self-consistency** *(Day 02)* — Running the same CoT prompt N times and taking the majority answer. The vote spread doubles as a confidence signal.

**Self-query retriever** *(Day 13)* — The model translates a natural-language query into a structured filter plus a semantic query.

**Self-RAG** *(Day 13)* — RAG where the model critiques its own retrieval and generation, deciding whether to retrieve again or revise.

**Send** *(Day 19)* — LangGraph's mechanism for fanning out to a dynamic number of parallel node executions (map-reduce).

**Server-Sent Events (SSE)** *(Day 23)* — A one-way streaming HTTP format: `event:` and `data:` lines, each event ending with a blank line. The default way to stream agent output to a browser.

**State** *(Day 18)* — The typed object flowing through a LangGraph graph, updated by nodes according to reducers.

**Store** *(Day 20)* — LangGraph's long-term memory, persisting facts *across* threads. Distinct from a checkpointer, which persists one thread's state.

**Stream** *(Day 04)* — Receiving output incrementally as it's generated. Doesn't reduce total time; dramatically improves perceived latency.

**Stream mode** *(Day 23)* — What a graph stream emits: `values` (full state), `updates` (node deltas), `messages` (tokens + metadata), `custom` (your events), plus `debug`, `tasks`, `checkpoints`.

**streamEvents** *(Day 07, 23)* — Streaming every intermediate step of a chain, not just the final output. How you build "Searching… Reading… Writing…" UIs.

**Structured output** *(Day 06)* — Getting a validated object matching your schema. Implemented as a forced tool call under the hood.

**Subgraph** *(Day 19)* — A compiled graph used as a node inside another graph.

**Superstep** *(Day 17)* — One round of graph execution: all active nodes run on the same state snapshot, their updates merge through reducers, then edges choose the next nodes. Checkpoints are written after each.

**Supervisor** *(Day 22)* — A coordinating agent that delegates to specialists and answers the user. The recommended form calls specialist agents *as tools*, so each sees only its brief.

**Swarm** *(Day 22)* — A multi-agent pattern built from handoffs: whichever agent is active talks to the user. Needs a checkpointer (or the `activeAgent` value) to remember who's active.

**SystemMessage** *(Day 04)* — Instructions and persona. Weighted heavily by the model; usually one, at the front.

---

## T

**Temperature** *(Day 01)* — Scales logits before softmax, flattening or sharpening the distribution. Affects *sampling*, not knowledge.

**Thread** *(Day 20)* — A conversation identifier in LangGraph. State is checkpointed per thread.

**Thundering herd** *(Day 03)* — Many clients retrying simultaneously and re-causing the overload. Prevented with jitter.

**Time travel** *(Day 20)* — Rewinding a checkpointed graph to an earlier state and re-running from there.

**Token** *(Day 01)* — A chunk of text (~4 characters in English) mapped to an integer ID. Models see tokens, never characters.

**Tokenizer** *(Day 01)* — Converts text to token IDs and back. Provider-specific — never assume token counts transfer.

**Tool** *(Day 15)* — A function the model can request, described by a name, description and schema. The description is prompt text.

**Tool calling** *(Day 02, 15)* — The model emits a structured request naming a function and arguments; **your code** executes it and returns the result.

**ToolMessage** *(Day 04, 15)* — The message type carrying a tool's result back to the model, linked by `tool_call_id`.

**ToolNode** *(Day 17)* — A prebuilt graph node that executes the tool calls in the last AI message and returns tool messages. JS returns tool errors as content; Python re-raises unless `handle_tool_errors` is set.

**top_p** *(Day 01)* — Nucleus sampling. Keeps the smallest set of top tokens summing to probability `p` and discards the rest. Tune this *or* temperature, not both.

**Trajectory evaluation** *(Day 25)* — Scoring the sequence of tool calls an agent made against a reference — strict, unordered, subset or superset — not just its final answer.

**trimMessages / trim_messages** *(Day 04, 14)* — Bounding conversation history to a token budget while preserving the system message and a valid message order.

---

## V

**Vector database** *(Day 11)* — A store optimised for approximate nearest-neighbour search over embeddings, usually with metadata filtering.

**venv** *(Day 03)* — A Python virtual environment. Per-project package isolation. If your prompt doesn't show `(.venv)`, you're in the wrong one.

**Vercel AI SDK** *(Day 26)* — A TypeScript toolkit for model calls, tool loops (`generateText` + `stopWhen`, `ToolLoopAgent`), structured output and streaming UIs. Strong for UI streaming; LangGraph adds persistence and HITL.

---

## W

**Workflow (vs agent)** *(Day 22)* — A graph whose steps are decided by your code, not the model. If you can draw the flowchart before the request arrives, build a workflow and call models inside its nodes.

---

## Z

**Zero-shot prompting** *(Day 02)* — Giving instructions with no examples.

**Zod** *(Day 03, 06)* — TypeScript's runtime schema/validation library. Used by LangChain JS for tool arguments and structured output. `.describe()` text is sent to the model.
