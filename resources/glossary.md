# Glossary

Every term in this course, one line each. Terms are marked with the day that introduces them
(Days 0A–0C are Week 0). Later terms are included so you can look ahead.

← [Back to the main index](../README.md)

---

## A

**A/A test** *(Day 39)* — Both groups get the same version; it checks how often your experiment system shows a false difference.

**A/B test** *(Day 39)* — Comparing two versions on randomly split live users, using one metric chosen in advance.

**A2A (Agent2Agent protocol)** *(Day 38)* — An open standard for one agent to hand tasks to another, using agent cards, messages, tasks and artifacts. MCP connects agents to tools; A2A connects agents to agents.

**Accessibility tree** *(Day 38)* — The browser's list of page elements with their roles and names — a compact view of a page for agents.

**Adapter** *(Day 31)* — The small file of LoRA weights loaded on top of a base model.

**Adaptive RAG** *(Day 13)* — Routing each query to a different retrieval strategy (or none) based on its type and complexity.

**Agent** *(Day 16)* — An LLM in a loop that decides which tools to call, observes the results, and repeats until it can answer. Distinguished from a chain by having *control flow the model decides*.

**Agent card** *(Day 38)* — The JSON at `/.well-known/agent-card.json` that describes an A2A agent's skills and how to call it.

**Agent skill** *(Day 38)* — A folder with a `SKILL.md` (a short description plus instructions and optional scripts) that an agent loads only when needed.

**Agent-as-a-tool** *(Day 22)* — A specialist agent wrapped in a tool, so a supervisor calls it like any other tool.

**Agentic RAG** *(Day 13)* — RAG where an agent decides whether to retrieve, what to search for, and whether the results were good enough — rather than always retrieving once.

**Agentic search** *(Day 37)* — A loop where the model chooses each next search and code-enforced stop rules end it.

**AIMessage** *(Day 04)* — The message type representing model output. Carries `content`/`text`, `tool_calls`, `usage_metadata` and `response_metadata`.

**AIMessageChunk** *(Day 04)* — A partial `AIMessage` yielded during streaming. Chunks are addable (`concat` / `+`) so they can be reassembled into a complete message.

**ANN search** *(Day 11)* — Approximate nearest-neighbour search: finds *almost* the closest vectors, much faster than checking them all.

**Approval fatigue** *(Day 21)* — When people are asked to approve too often, they start approving without reading.

**Async iterator** *(Day 0B)* — Anything consumable with `for await...of` / `async for`. Streaming responses are async iterators.

**Attention** *(Day 01)* — The step inside the model where each token scores the tokens before it, turns the scores into weights with softmax, and mixes in their information.

---

## B

**Backoff** *(Day 24)* — Waiting longer between each retry (e.g. 0.5 s, 1 s, 2 s). Combine with *jitter* so clients that failed together don't retry together.

**BaseChatModel** *(Day 04)* — The LangChain interface every chat model implements. Takes `BaseMessage[]`, returns `AIMessage`.

**Batch** *(Day 04)* — Running many **independent** inputs concurrently with a concurrency cap. Not for conversation turns, which are sequentially dependent.

**Benchmark contamination** *(Day 03)* — Test questions leaking into a model's training data, which inflates its benchmark scores.

**Bi-encoder** *(Day 13)* — A model that embeds the query and each document separately, so document vectors can be computed in advance and searched cheaply.

**BM25** *(Day 11)* — A classic keyword-ranking algorithm. Combined with vector search to make *hybrid search*.

**Browser agent** *(Day 38)* — An agent whose tools open, read and act on web pages through a real browser.

**Budget guard** *(Day 34)* — Tracks spend per user or request and downgrades or refuses past a limit.

**Business rule** *(Day 06)* — A check on meaning that a schema can't express, such as "line items add up to the total".

---

## C

**Calibration (of a judge)** *(Day 25)* — Measuring how often an LLM judge agrees with human labels on the same examples. An uncalibrated judge's score is a number, not a measurement.

**Callback** *(Day 07, 25)* — A hook fired at each step of a Runnable's execution. The mechanism behind LangSmith tracing.

**Canary token** *(Day 35)* — A random marker planted somewhere secret so you can detect when it leaks.

**Cancellation** *(Day 23)* — Stopping a run when nobody is waiting for it. In JS, leaving a stream loop doesn't stop the graph — pass an `AbortSignal`; in Python, closing the stream generator stops it before the next superstep.

**Capacity arithmetic** *(Day 27)* — Estimating peak runs per second, model calls and tokens per run before choosing infrastructure. It usually shows the bottleneck is the provider's rate limit or cost, not compute.

**Capstone** *(Day 28, 40)* — One larger, finished project that combines what you have learned.

**Catastrophic forgetting** *(Day 31)* — New training damaging skills the model had before.

**Chain** *(Day 08)* — A fixed sequence of steps with control flow decided by *you*, not the model. Contrast with **agent**.

**Chain-of-Thought (CoT)** *(Day 02)* — Prompting the model to produce intermediate reasoning before its answer. Works because generated tokens act as working memory.

**Channel** *(Day 17)* — One named field in a LangGraph state, with its own reducer deciding how new values are combined.

**Chat model** *(Day 04)* — A model that takes a list of messages with roles and replies with one message.

**Chat template** *(Day 29)* — The exact text format, with role markers, that an instruct model was trained on. Without it a local model may return nothing.

**Checkpoint** *(Day 20)* — One saved copy of a graph's state, plus a note of which node runs next.

**Checkpointer** *(Day 20)* — A LangGraph component that saves graph state after each step, enabling persistence, resumption and time travel. Think of it as a video-game save file.

**Chunk overlap** *(Day 09)* — Text repeated at the end of one chunk and the start of the next, so sentences at the boundary stay whole.

**Chunking** *(Day 09)* — Splitting documents into pieces small enough to embed and retrieve usefully.

**Circuit breaker** *(Day 24)* — A guard that stops calling a dependency after repeated failures, fails fast for a cooldown, then lets one trial call through.

**Citation** *(Day 12)* — A marker such as [1] that links a claim in the answer to the chunk it came from.

**Cohen's kappa** *(Day 32)* — Agreement between two labellers after removing the agreement expected by chance.

**Command** *(Day 19)* — A node return value that updates state *and* routes (`goto`) in one step. Its destination is added to — not substituted for — any static edges from that node.

**Computer use** *(Day 38)* — A model tool that takes screenshots in and returns mouse and keyboard actions.

**Conditional edge** *(Day 17)* — An edge that calls a small router function to choose the next node while the graph runs.

**Constrained decoding** *(Day 02, 06)* — Masking the sampler at each step so only schema-valid tokens can be generated. The strongest structured-output guarantee.

**Context engineering** *(Day 14, 22, 36)* — Deciding everything that goes into the model's context window: instructions, tool definitions, history, retrieved documents, tool results and memory. Memory is one part of it; most multi-agent benefits are context-engineering benefits.

**Context rot** *(Day 36)* — Models recall information less reliably as the context grows longer.

**Context window** *(Day 01)* — The maximum number of tokens a model can process in one call, counting **input and output together**. A hard architectural limit.

**Contextual compression** *(Day 13)* — Filtering or shortening retrieved documents to just the parts relevant to the query, before passing them to the model.

**Continuous batching** *(Day 30)* — Re-forming the batch after every token step, so requests can join and leave at any time.

**Corpus** *(Day 12)* — The whole collection of documents a RAG system can search.

**Corrective RAG (CRAG)** *(Day 13)* — Grading retrieved documents and, if they're irrelevant, re-retrieving or falling back to web search.

**Cosine similarity** *(Day 10)* — A similarity metric between two vectors, based on the angle between them. The default for embedding comparison.

**Cost ledger** *(Day 34)* — A record of every model call: the feature that made it, its tokens and its price.

**Cross-encoder** *(Day 13)* — A model that reads the query and a document together and scores how relevant they are — accurate, but too slow for a whole corpus.

**Current working directory** *(Day 0A)* — The folder a terminal or program is "standing in". Relative paths — and JavaScript's dotenv — start from it.

---

## D

**Data leakage** *(Day 32)* — Test examples, or close copies of them, also present in the training data, which inflates scores.

**Dataset (evaluation)** *(Day 25)* — A fixed set of example inputs with reference outputs, answers, facts or trajectories, used to score a system the same way before and after a change.

**Dataset card** *(Day 32)* — A short description of a dataset: version, file hashes, counts, split, PII policy and limits.

**Dead letter queue** *(Day 24)* — Where repeatedly-failing items go so they don't block the pipeline and can be inspected later.

**Decode (phase)** *(Day 30)* — The second phase of generation: one forward pass per output token, in a serial loop.

**Deep agent** *(Day 36)* — A long-running agent with a detailed prompt, a to-do list, sub-agents and a file system to keep notes in.

**Denial of wallet** *(Day 35)* — An attack that makes an app spend excessive compute or money.

**Document** *(Day 09)* — LangChain's container for a piece of text plus its metadata (`pageContent` + `metadata`).

**Dot product** *(Day 10)* — A similarity metric that accounts for both angle and magnitude. Equivalent to cosine when vectors are normalised.

**DPO** *(Day 01)* — Direct preference optimisation: learn from pairs of preferred and rejected answers without a separate reward model.

**dtype** *(Day 29)* — The number format each parameter is stored in, such as fp32, bf16, int8 or int4. It decides the file size.

**Dynamic few-shot** *(Day 05, 13)* — Retrieving the k most similar examples per input from a vector store, rather than using a fixed example list.

---

## E

**.env.example** *(Day 0A)* — A committed file listing the environment variables a project needs, with no real values.

**Early stopping** *(Day 31)* — Stopping training when validation loss stops improving, and keeping the best epoch.

**Edge** *(Day 17)* — A connection between nodes in a LangGraph graph, defining what runs next.

**Embedding** *(Day 10)* — A list of numbers representing the *meaning* of text, such that similar meanings produce nearby vectors.

**Ensemble retriever** *(Day 13)* — Combining results from multiple retrievers (e.g. vector + BM25) with weighted fusion.

**Entity resolution** *(Day 37)* — Merging different names for the same thing ("Dr Khan", "Aisha Khan") into one node.

**Enum** *(Day 06)* — A field that may only hold one value from a fixed list.

**ESM** *(Day 0B)* — ECMAScript Modules — `import`/`export` plus top-level `await`. Enabled with `"type": "module"`. LangChain JS is ESM-first.

**EU AI Act** *(Day 39)* — The EU law that sorts AI systems into risk tiers (unacceptable, high, transparency, minimal) with different duties. Not legal advice — check the current rules.

**Eval** *(Day 03, 25)* — Your own test set of real inputs and expected results, graded by a rule written in advance.

**Eval leakage** *(Day 40)* — Eval questions or answers appearing in the prompt or data, so scores measure copying rather than skill.

**Evaluator** *(Day 25)* — A function that scores an output: code checks (exact, contains, schema), trajectory matches, LLM-as-judge, or human review.

**Evaluator-optimizer** *(Day 19, 36)* — A generate → critique → revise loop that repeats until a critic passes the output or a limit is hit.

**Event loop** *(Day 0B)* — The scheduler that runs other async tasks while one is waiting on the network.

**Exact-match cache** *(Day 34)* — Reuses a saved answer only when the prompt and model settings are identical.

**Excessive agency** *(Day 35)* — An agent holding more tools, permissions or autonomy than its job needs.

**Execution loop** *(Day 15)* — Call the model, run the tools it asks for, send back the results, repeat until it answers.

**Exit code** *(Day 0A)* — The number a program returns when it ends: 0 means success, anything else means a problem.

**Explicit feedback** *(Day 39)* — A signal the user gives on purpose, such as a thumbs-up or a rating.

**Exponential backoff** *(Day 0B)* — Waiting longer after each failed attempt (for example 0.5 s, 1 s, 2 s) before retrying. See also Jitter.

---

## F

**Fallback** *(Day 04)* — An alternative Runnable invoked when the primary fails. `.withFallbacks()` / `.with_fallbacks()`.

**Few-shot prompting** *(Day 02, 05)* — Including worked input→output examples in the prompt. In-context learning, not training.

**Fine-tuning** *(Day 31)* — Training an already-trained model a little more on your own examples, to change its habits. It teaches behaviour, not fresh facts.

**Finish reason** *(Day 01)* — Why generation stopped: `stop` (natural), `length` (hit `max_tokens`), `tool_calls`.

**Fork** *(Day 20)* — Editing an old checkpoint and running forward on a new branch; the original timeline survives.

**Forward pass** *(Day 01)* — One full run of the network over the input. Generating text takes one forward pass per output token.

**Frequency penalty** *(Day 01)* — Reduces a token's probability each time it repeats. Fights literal repetition.

**Function calling** *(Day 02)* — The older name for **tool calling**. Same mechanism.

---

## G

**.gitignore** *(Day 0A)* — A list of file patterns git must not add. It does not un-track files that were already committed.

**Gated model** *(Day 29)* — A model whose files download only after you accept its licence on the Hub.

**GGUF** *(Day 29)* — The single-file model format for llama.cpp and Ollama. It holds the weights, the tokenizer and the chat template.

**Golden set** *(Day 32)* — A small, human-checked, frozen test set that is never trained on.

**Graceful shutdown** *(Day 27)* — On `SIGTERM`, stop accepting work, let in-flight runs finish up to a deadline, then close pools — so deploys don't drop conversations.

**Graph RAG** *(Day 13, 37)* — Retrieval over a knowledge graph of entities and relationships rather than (or alongside) flat text chunks.

**Greedy decoding** *(Day 01)* — Always picking the highest-probability token. What `temperature: 0` does. **Not** the same as deterministic.

**Grounding** *(Day 12)* — Telling the model to answer only from the retrieved text, not from what it learned in training.

**Grouped-query attention** *(Day 30)* — Several query heads share one key/value head, which makes the KV cache smaller.

**Guard (agent)** *(Day 16)* — A code check that stops or redirects the agent loop: step limit, repeat detection, token budget, timeout.

**Guardrail metric** *(Day 39)* — A number that must not get worse while the main metric improves, such as latency, cost or refusals.

---

## H

**Hallucination** *(Day 01)* — Fluent, confident output that isn't true. A consequence of next-token prediction having no truth-check step.

**Handoff** *(Day 22)* — A tool whose result transfers control to another agent (a `Command` with `graph: PARENT`) and records it as the active agent, so the user keeps talking to the specialist.

**HNSW** *(Day 11)* — Hierarchical Navigable Small World — the most common approximate-nearest-neighbour index in vector databases.

**HTTP status code** *(Day 0B)* — The three-digit result of a web request: 2xx success, 4xx your mistake (401 bad key, 429 too many requests), 5xx the server's problem.

**Human-in-the-loop (HITL)** *(Day 21)* — Pausing execution for human approval, rejection or editing before continuing.

**HumanMessage** *(Day 04)* — The message type representing user input.

**Hybrid search** *(Day 11)* — Combining keyword (BM25) and vector search, then fusing the rankings.

**HyDE** *(Day 13)* — Hypothetical Document Embeddings: generate a fake ideal answer, embed *that*, and retrieve with it. Often beats embedding the raw question.

---

## I

**Idempotency key** *(Day 24)* — A unique id for one logical action (a refund, an email, a run submission) so a retry or replay is recognised and not executed twice.

**Idempotent** *(Day 21, 24)* — Safe to run twice: doing it again has no extra effect.

**Image splitting / tiling** *(Day 33)* — Cutting a large image into tiles plus an overview, to keep detail at a higher token cost.

**Image tokens** *(Day 33)* — The tokens a model makes from a picture's patches. They are billed like text tokens, so bigger images cost more.

**Implicit feedback** *(Day 39)* — A signal read from behaviour: copying, editing, regenerating or leaving.

**Indirect prompt injection** *(Day 35)* — Instructions hidden in content the app reads later — a document, web page or tool result — rather than typed by the user.

**Inference** *(Day 01)* — Running a finished, frozen model to get an answer. Every API call is inference.

**Instruction tuning (SFT)** *(Day 01)* — Supervised fine-tuning on examples of instructions with good responses, so the model answers instead of just continuing text.

**Inter-token latency** *(Day 30)* — The gap between one streamed token and the next.

**Interrupt** *(Day 21)* — LangGraph's mechanism for pausing a graph mid-execution and resuming later, used for human-in-the-loop.

**invoke** *(Day 04)* — The Runnable method that takes one input and returns one complete output.

---

## J

**Jaccard similarity** *(Day 32)* — Shared items divided by all distinct items of two sets: 0 means nothing shared, 1 means identical.

**Jitter** *(Day 0B)* — Randomness added to retry delays so many clients don't retry in lockstep (the *thundering herd*).

**JSON** *(Day 0B)* — A strict text format for data — objects, arrays, strings, numbers, booleans and null — used by every AI API.

**JSON mode** *(Day 02, 06)* — A provider setting guaranteeing syntactically valid JSON output — but *not* your schema.

**JSON Schema** *(Day 06)* — The format Zod/Pydantic schemas are converted into before being sent to the model.

**JSON-RPC** *(Day 26)* — A simple message format MCP uses: a JSON request naming a method, and a JSON reply.

---

## K

**Knowledge graph** *(Day 37)* — Data stored as named things joined by named links, so you can follow relationships.

**KV-cache** *(Day 01)* — Cached attention keys/values for already-processed tokens, so each new output token doesn't recompute the whole prefix. It is also what provider prompt caching reuses.

---

## L

**LangGraph** *(Day 17+)* — LangChain's library for stateful, cyclic workflows: nodes, edges, typed state, checkpointing, interrupts. Use it when control flows in a loop.

**LangGraph server** *(Day 27)* — A runtime that serves graphs listed in `langgraph.json` as an HTTP API — threads, runs, streaming, interrupts, background runs. Run locally with `langgraph dev`; it rejects graphs compiled with their own checkpointer.

**LangSmith** *(Day 25)* — LangChain's observability and evaluation platform: traces, datasets, evaluators, experiments.

**LCEL** *(Day 07)* — LangChain Expression Language. Composition via `.pipe()` / `|` on the `Runnable` interface. Builds a directed **acyclic** graph.

**Least privilege** *(Day 15, 35)* — Give each tool only the access it needs — for example a read-only, tenant-scoped database login.

**LLM (large language model)** *(Day 01)* — A program trained on huge amounts of text to predict the next token.

**LLM-as-judge** *(Day 25)* — Using a model to grade outputs against a rubric (correctness, groundedness, helpfulness). Prefer binary scores with reasoning, a different model family, and calibration against humans.

**Loader** *(Day 09)* — Code that reads a file (PDF, CSV, web page…) and turns it into Documents.

**Log-probability (logprob)** *(Day 0C)* — The natural log of a probability. Always ≤ 0; it turns products of tiny numbers into sums that don't underflow.

**Logits** *(Day 01)* — Raw scores the model produces for every token in its vocabulary, before softmax turns them into probabilities.

**LoRA** *(Day 31)* — Fine-tuning that freezes the model's weights and learns two small matrices (B·A) next to some of them.

**Loss masking** *(Day 31)* — Setting the prompt's labels to -100 so training learns only from the reply.

**Lost in the middle** *(Day 01)* — Models attend more reliably to the start and end of a long context than to the middle. An argument for retrieving few, relevant chunks.

---

## M

**Magic bytes** *(Day 33)* — The first bytes of a file, which reveal its real format whatever its name says.

**Map-reduce** *(Day 08, 19)* — Do the same job on many items separately (map), then combine the results in one final step (reduce).

**max_tokens** *(Day 01)* — A cap on **output** tokens. Truncates mid-sentence; does not make the model concise.

**MCP** *(Day 26)* — Model Context Protocol. A standard for exposing tools, resources and prompts to LLM applications over stdio/HTTP/SSE.

**Memory** *(Day 14)* — Any strategy for deciding what past information to include in the next request. LLMs have none natively.

**MessagesPlaceholder** *(Day 05)* — A slot in a chat template where an **array** of messages is spliced in, preserving roles. Usually conversation history.

**Metadata** *(Day 09)* — Facts about a text — source file, page, date — used for filtering and citing. It isn't embedded.

**Middleware (agent)** *(Day 24)* — Hooks passed to `createAgent` / `create_agent` that run before or after model calls or wrap model and tool calls — retries, fallbacks, call limits, PII redaction, summarisation.

**MinHash** *(Day 32)* — A short signature of a set whose matching positions estimate Jaccard similarity cheaply.

**MMR** *(Day 13)* — Maximal Marginal Relevance. Retrieval that balances relevance against diversity, avoiding five near-duplicate chunks.

**Model card** *(Day 29)* — A model's README and metadata: licence, size, context length and intended use.

**Model cascade** *(Day 34)* — Call a cheap model first and escalate to an expensive one only when a check fails.

**Model Context Protocol (MCP)** *(Day 26)* — An open protocol for exposing tools, resources and prompts from a server to any AI client over stdio or Streamable HTTP. Build a capability once; any MCP client can use it.

**Model router** *(Day 34)* — Chooses a model before the call, from the question alone.

**Multi-hop question** *(Day 37)* — A question answered only by following two or more links in a row.

**Multi-query retrieval** *(Day 13)* — Generating several rephrasings of a question, retrieving for each, and merging results.

**Multimodal RAG** *(Day 33)* — Retrieval over documents with pictures: embed a caption for each image, keep a pointer to the image, and answer with the original.

---

## N

**Namespace (store)** *(Day 18)* — The tuple/array path that scopes long-term store entries, e.g. `("students", id)` — what makes store memory cross threads but stay per user.

**Near-duplicate** *(Day 32)* — Two records that say the same thing with small differences in wording or punctuation.

**Node** *(Day 17)* — A step in a LangGraph graph. A function that receives state and returns a state update.

**Norm** *(Day 0C)* — A vector's length: the square root of the sum of its squared entries. Day 10 calls it magnitude.

**Nucleus sampling** *(Day 01)* — See **top_p**.

---

## O

**Observability** *(Day 25)* — Being able to see what happened inside one specific run, after the fact.

**Ollama** *(Setup)* — A tool for running open models locally. Free, offline, no rate limits.

**ONNX** *(Day 29)* — A portable model-graph format run by ONNX Runtime. Transformers.js uses it in Node and the browser.

**Open-weight model** *(Day 03)* — A model whose weights you can download and run yourself. Not the same as open source: the licence may still restrict use.

**OpenAI-compatible API** *(Day 30)* — A server that accepts OpenAI's `/v1/chat/completions` request shape, so any OpenAI client works by changing the base URL.

**Orchestrator-workers** *(Day 19, 36)* — One step splits a job at run time, workers do the parts in parallel, and a join step combines them. In LangGraph: `Send`.

**Output parser** *(Day 06)* — A Runnable that transforms model output into something more useful — a string, a parsed object, a list.

---

## P

**PagedAttention** *(Day 30)* — vLLM's way of storing the KV cache in fixed-size pages so less memory is wasted.

**Parallelisation** *(Day 08)* — Several model calls at once: *sectioning* runs different subtasks, *voting* runs the same task several times.

**Parent document retriever** *(Day 13)* — Embedding small chunks for precise matching but returning their larger parent chunks for richer context.

**Partial** *(Day 05)* — Pre-filling some template variables, returning a template needing only the rest. Supports functions evaluated at render time.

**Path** *(Day 0A)* — The address of a file or folder. Absolute paths start at the top of the disk; relative paths start from the current folder.

**PATH (variable)** *(Day 0A)* — The list of folders the terminal searches, in order, to find a command like `python`.

**Path traversal** *(Day 15)* — An attack that uses `..` in a file path to escape the folder a tool is allowed to read.

**Peeking** *(Day 39)* — Checking an experiment repeatedly and stopping early; it inflates false winners.

**Perceived latency** *(Day 23)* — How long the wait *feels* to the user, as opposed to the total time. Streaming lowers it.

**Percentile (p50 / p95)** *(Day 0C)* — The value that 50 % / 95 % of measurements are at or below. p95 latency is what your slowest users feel.

**pgvector** *(Day 11)* — A Postgres extension adding vector similarity search. Lets you keep vectors next to relational data.

**PII redaction** *(Day 24)* — Detecting personal data (emails, cards, IPs…) and redacting, masking, hashing or blocking it before it reaches the model — via PII middleware.

**Pre-filtering** *(Day 11)* — Applying a metadata filter before or during the vector search, rather than after it (post-filtering).

**Pre-training** *(Day 01)* — The first training stage: predicting the next token over a huge amount of text. It produces a base model.

**Precision** *(Day 0C)* — Of the items flagged "yes", the share that really were yes.

**Prefill** *(Day 30)* — The first phase of generation: the model reads the whole prompt in one parallel pass and fills the KV cache. It sets time to first token.

**Presence penalty** *(Day 01)* — A flat penalty once a token appears at all. Pushes toward new topics.

**Progressive disclosure** *(Day 38)* — Loading names first, full instructions only when needed, and extra files only on request — to save context.

**Prompt caching** *(Day 01, 05, 24, 34)* — Providers reusing computation for an identical prompt *prefix*, reducing cost and latency. Why stable content goes first.

**Prompt chaining** *(Day 08)* — Anthropic's name for a sequential chain: each model call works on the output of the call before it.

**Prompt engineering** *(Day 02)* — Writing the model's input so that it reliably does what you need.

**Prompt injection** *(Day 02)* — Untrusted input containing instructions the model follows. Mitigated at the prompt layer; *solved* at the authorisation layer.

**Prompt template** *(Day 05)* — A reusable prompt with named blanks, like `{topic}`, that you fill in later.

**PromptTemplate** *(Day 05)* — A parameterised prompt rendering to a single string. `ChatPromptTemplate` renders to a message list — prefer that.

**Provider** *(Day 04)* — The company or tool that runs the model for you, such as Groq, Gemini or Ollama.

**Pydantic** *(Day 0B, 06)* — Python's runtime schema/validation library. The Python equivalent of Zod.

---

## Q

**QLoRA** *(Day 31)* — LoRA trained on top of a base model stored in 4-bit precision, to save memory. Needs a GPU.

**Quantisation** *(Day 29)* — Storing weights in fewer bits (with a scale per block), so the model gets smaller at a small cost in accuracy.

**Queue** *(Day 27)* — A list of waiting jobs, so work can be accepted now and done later by workers.

---

## R

**RAG** *(Day 12)* — Retrieval-Augmented Generation. Retrieve relevant documents, put them in the prompt, generate an answer grounded in them.

**Rate limiter** *(Day 24)* — A token bucket or concurrency cap that queues requests instead of exceeding a provider's quota. Share one limiter per provider account.

**ReAct** *(Day 02, 16)* — Reason + Act. The `Thought → Action → Observation` loop underlying every tool-using agent.

**Reasoning model** *(Day 02)* — A model trained to produce reasoning tokens before its final answer. Better on multi-step problems; slower and uses more output tokens.

**Recall** *(Day 0C)* — Of the real "yes" items, the share that were found. In retrieval: the share of the right chunks that came back.

**Recall@k** *(Day 12, 13)* — The share of test questions whose correct chunk appears in the top k results.

**Recursion limit** *(Day 17)* — The maximum number of supersteps in one run (default 25 in JS; 10,007 in Python's langgraph 1.2.x, so set it yourself). Hitting it raises `GraphRecursionError` — a sign the loop needs a budget exit.

**Red-teaming** *(Day 35)* — Attacking your own system on purpose with a fixed, growing list of attacks.

**Reducer** *(Day 18)* — A function defining how a state key is updated when a node returns a value for it. E.g. append vs overwrite.

**Regression** *(Day 25)* — Something that used to work and now doesn't.

**Release gate** *(Day 40)* — An automatic check that must pass before a new version goes live.

**Replay** *(Day 20)* — Running forward again from an old checkpoint without changing anything.

**Reranking** *(Day 13)* — Re-scoring retrieved documents with a more accurate (usually cross-encoder) model. Retrieve 20 cheaply, rerank to 5 accurately.

**Retriever** *(Day 13)* — Anything that takes a query and returns relevant documents. A vector store is one source; a retriever is the interface.

**Retry-After** *(Day 0B)* — A response header telling the client how long to wait before trying again, usually sent with a 429.

**RLHF** *(Day 01)* — Reinforcement learning from human feedback: train a reward model on human preferences, then tune the LLM to score well with it.

**Router chain** *(Day 08)* — A chain that first classifies the input, then sends it down one of several paths. Industry name: routing.

**Rubric** *(Day 25)* — A written list of what counts as a good answer, used by a human or an LLM judge.

**Rule of Two** *(Day 35)* — An agent should combine at most two of: untrusted input, sensitive data, and the power to change state or communicate externally.

**Runnable** *(Day 07)* — LangChain's core interface: `invoke`, `stream`, `batch`, `pipe`. Everything implements it, which is why composition works uniformly.

**RunnableAssign** *(Day 07)* — Adds keys to a dict input, **keeping** existing ones. `RunnablePassthrough.assign()`.

**RunnableBranch** *(Day 07)* — Declarative if/elif/else routing between Runnables.

**RunnableLambda** *(Day 07)* — Wraps any single-argument function as a Runnable.

**RunnableParallel** *(Day 07)* — Runs several Runnables concurrently on the same input, collecting results into an object. **Replaces** the input.

**RunnablePassthrough** *(Day 07)* — The identity Runnable. Carries the input forward alongside computed values.

**RunnableSequence** *(Day 07)* — Sequential composition. What `.pipe()` / `|` builds.

**Runtime** *(Day 0A)* — The program that runs your code: Node.js for JavaScript, Python for Python.

---

## S

**safetensors** *(Day 35)* — A model-weight format of a JSON header plus raw numbers, with nothing to execute when loaded (unlike pickle).

**Sample rate** *(Day 33)* — How many audio measurements are taken per second. Whisper expects 16,000; the wrong rate gives fluent nonsense, not an error.

**Sampling** *(Day 01)* — Selecting one token from the probability distribution. Where temperature and top_p apply.

**Schema** *(Day 06)* — A description of the exact shape data must have: field names, types and allowed values.

**Seed** *(Day 0C)* — The starting number of a random-number generator. The same seed gives the same sequence.

**Self-consistency** *(Day 02)* — Running the same CoT prompt N times and taking the majority answer. The vote spread doubles as a confidence signal.

**Self-query retriever** *(Day 13)* — The model translates a natural-language query into a structured filter plus a semantic query.

**Self-RAG** *(Day 13)* — RAG where the model critiques its own retrieval and generation, deciding whether to retrieve again or revise.

**Semantic cache** *(Day 34)* — Reuses an answer when a new question's embedding is close enough to a saved one. Risk: a false hit returns the answer to a different question.

**Semantic search** *(Day 10)* — Search that matches by meaning rather than by shared words.

**Send** *(Day 19)* — LangGraph's mechanism for fanning out to a dynamic number of parallel node executions (map-reduce).

**Serialisable** *(Day 18)* — Can be turned into text (such as JSON) and back. Anything that gets checkpointed must be.

**Server-Sent Events (SSE)** *(Day 23)* — A one-way streaming HTTP format: `event:` and `data:` lines, each event ending with a blank line. The default way to stream agent output to a browser.

**Serverless** *(Day 27)* — A platform that runs your code per request, with short time limits.

**Shingle** *(Day 32)* — An overlapping piece of text of fixed length, used to compare documents as sets.

**Side effect** *(Day 21)* — Anything a node changes outside the graph's state, such as charging a card or sending an email.

**Softmax** *(Day 0C)* — A formula that turns any list of scores into probabilities that add up to 1.

**Speculative decoding** *(Day 30)* — A small draft model proposes several tokens and the big model checks them in one pass. The output is identical; it is only faster when guesses are often right.

**Speech-to-text (STT)** *(Day 33)* — Turning spoken audio into written words, for example with Whisper.

**Spotlighting** *(Day 35)* — Marking untrusted text as data (for example with random-named tags) so a model is less likely to follow it. Helps, but is not a control.

**Stack trace / traceback** *(Day 0A)* — The list of calls that were running when an error happened. Node lists the newest call first; Python lists it last.

**State** *(Day 18)* — The typed object flowing through a LangGraph graph, updated by nodes according to reducers.

**Stateless** *(Day 14, 27)* — Keeps nothing between calls: a model starts every request from zero, and a stateless server can serve any request.

**Stop sequence** *(Day 02)* — Text that makes the model stop generating as soon as it produces it, e.g. `Observation:` in text-based ReAct.

**Store** *(Day 18)* — LangGraph's long-term memory, persisting facts *across* threads. Distinct from a checkpointer, which persists one thread's state.

**Stream** *(Day 04)* — Receiving output incrementally as it's generated. Doesn't reduce total time; dramatically improves perceived latency.

**Stream mode** *(Day 23)* — What a graph stream emits: `values` (full state), `updates` (node deltas), `messages` (tokens + metadata), `custom` (your events), plus `debug`, `tasks`, `checkpoints`.

**streamEvents** *(Day 07, 23)* — Streaming every intermediate step of a chain, not just the final output. How you build "Searching… Reading… Writing…" UIs.

**Structured output** *(Day 06)* — Getting a validated object matching your schema. Implemented as a forced tool call under the hood.

**Subgraph** *(Day 19)* — A compiled graph used as a node inside another graph.

**Summary memory** *(Day 14)* — Older turns compressed into a short running summary by a model call.

**Superstep** *(Day 17)* — One round of graph execution: all active nodes run on the same state snapshot, their updates merge through reducers, then edges choose the next nodes. Checkpoints are written after each.

**Supervisor** *(Day 22)* — A coordinating agent that delegates to specialists and answers the user. The recommended form calls specialist agents *as tools*, so each sees only its brief.

**Swarm** *(Day 22)* — A multi-agent pattern built from handoffs: whichever agent is active talks to the user. Needs a checkpointer (or the `activeAgent` value) to remember who's active.

**Synthetic data** *(Day 32)* — Training or test examples written by a model instead of a person. Useful, but it can copy the model's mistakes.

**SystemMessage** *(Day 04)* — Instructions and persona. Weighted heavily by the model; usually one, at the front.

---

## T

**Temperature** *(Day 01)* — Scales logits before softmax, flattening or sharpening the distribution. Affects *sampling*, not knowledge.

**Tenant** *(Day 11)* — One customer in a shared system, whose data must stay separate from everyone else's.

**Terminal** *(Day 0A)* — A window where you type commands to the computer instead of clicking.

**Text splitter** *(Day 09)* — Code that cuts Documents into smaller chunks, ideally at natural breaks.

**Text-to-speech (TTS)** *(Day 33)* — Turning written words into spoken audio.

**Text-to-SQL** *(Day 37)* — A model writes a database query; your code checks and runs it, read-only.

**Thread** *(Day 20)* — A conversation identifier in LangGraph. State is checkpointed per thread.

**Threat model** *(Day 35)* — A written list of who might attack an app, how their input gets in, and what they could damage.

**Throughput** *(Day 30)* — Tokens produced per second across all requests together. Batching raises it; each single request may get slower.

**Thundering herd** *(Day 0B)* — Many clients retrying simultaneously and re-causing the overload. Prevented with jitter.

**Time to first token (TTFT)** *(Day 03)* — The delay before the first answer token arrives — the latency a chat user feels.

**Time travel** *(Day 20)* — Rewinding a checkpointed graph to an earlier state and re-running from there.

**Token** *(Day 01)* — A chunk of text (~4 characters in English) mapped to an integer ID. Models see tokens, never characters.

**Token usage** *(Day 04)* — How many tokens a request read and wrote (`usage_metadata`). It decides the cost.

**Tokenizer** *(Day 01)* — Converts text to token IDs and back. Provider-specific — never assume token counts transfer.

**Tool** *(Day 15)* — A function the model can request, described by a name, description and schema. The description is prompt text.

**Tool calling** *(Day 02, 15)* — The model emits a structured request naming a function and arguments; **your code** executes it and returns the result.

**ToolMessage** *(Day 04, 15)* — The message type carrying a tool's result back to the model, linked by `tool_call_id`.

**ToolNode** *(Day 17)* — A prebuilt graph node that executes the tool calls in the last AI message and returns tool messages. JS returns tool errors as content; Python re-raises unless `handle_tool_errors` is set.

**Top-k** *(Day 10, 12)* — How many of the best-matching results are returned for each query.

**top_p** *(Day 01)* — Nucleus sampling. Keeps the smallest set of top tokens summing to probability `p` and discards the rest. Tune this *or* temperature, not both.

**Trace** *(Day 07, 25)* — The recorded tree of every step in one run — model calls, tool calls, inputs, outputs and timings.

**Trajectory evaluation** *(Day 25)* — Scoring the sequence of tool calls an agent made against a reference — strict, unordered, subset or superset — not just its final answer.

**Transient failure** *(Day 24)* — A short-lived error, such as a busy server, that often works if you try again.

**Transport (MCP)** *(Day 26)* — How an MCP client and server exchange messages: stdio (a local pipe) or Streamable HTTP (over the network).

**trimMessages / trim_messages** *(Day 04, 14)* — Bounding conversation history to a token budget while preserving the system message and a valid message order.

**Triple** *(Day 37)* — One graph fact: subject, relation, object.

---

## V

**Vector** *(Day 0C)* — An ordered list of numbers. Text becomes vectors so that meaning can be calculated with.

**Vector database** *(Day 11)* — A store optimised for approximate nearest-neighbour search over embeddings, usually with metadata filtering.

**venv** *(Day 0A)* — A Python virtual environment. Per-project package isolation. If your prompt doesn't show `(.venv)`, you're in the wrong one.

**Vercel AI SDK** *(Day 26)* — A TypeScript toolkit for model calls, tool loops (`generateText` + `stopWhen`, `ToolLoopAgent`), structured output and streaming UIs. Strong for UI streaming; LangGraph adds persistence and HITL.

**Vision-language model (VLM)** *(Day 33)* — A model that reads images and text together and answers in text.

---

## W

**Workflow (vs agent)** *(Day 22)* — A graph whose steps are decided by your code, not the model. If you can draw the flowchart before the request arrives, build a workflow and call models inside its nodes.

---

## Z

**Zero-shot prompting** *(Day 02)* — Giving instructions with no examples.

**Zod** *(Day 0B, 06)* — TypeScript's runtime schema/validation library. Used by LangChain JS for tool arguments and structured output. `.describe()` text is sent to the model.
