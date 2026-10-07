# Interview Bank

**378 questions with model answers**, collected verbatim from the interview section of every
day, grouped by week and level (Basic → Intermediate → Advanced).

**How to use it**

1. Cover the answer. Say yours out loud, timed — concept answers in under a minute.
2. Compare with the model answer: did you name a **mechanism**, a **number**, or a **trade-off**?
3. Mark the ones you missed and revisit that day's "Under the hood" section.
4. For system design and project questions, use the frameworks and mock interviews in
   [Day 28](../week-04-production-projects-and-interviews/day-28-capstones-and-interviews.md).

## Contents

- **Week 1 — Foundations**
  - Day 01 — What an LLM Actually Is: Tokens, Context & Inference (14)
  - Day 02 — Prompt Engineering & Talking to Models With No Framework (12)
  - Day 03 — JS & Python Essentials for AI · Why LangChain Exists (11)
  - Day 04 — LangChain Models: invoke, stream, batch & Message Types (11)
  - Day 05 — Prompts & Templates (10)
  - Day 06 — Output Parsers & Structured Output (Zod ↔ Pydantic) (11)
  - Day 07 — LCEL & Runnables (the #1 interview topic) (11)
- **Week 2 — Data, Embeddings, RAG & Memory**
  - Day 08 — Chains: Sequential, Parallel, Router & Document Chains (11)
  - Day 09 — Documents, Loaders, Splitting & Chunking Strategy (11)
  - Day 10 — Embeddings: Vectors, Similarity & Model Choice (11)
  - Day 11 — Vector Databases: Indexes, Filtering & Hybrid Search (11)
  - Day 12 — Naive RAG End-to-End (and Six Ways to Break It) (11)
  - Day 13 — Advanced RAG: Reranking, HyDE, Multi-Query & Self-Correction (11)
  - Day 14 — Memory: Buffer, Summary, Entity & What Actually Changed (11)
- **Week 3 — Tools, Agents & LangGraph**
  - Day 15 — Tools: Creating, Calling, Schemas, Errors & Retries (11)
  - Day 16 — Agents From First Principles: Build ReAct by Hand (11)
  - Day 17 — LangGraph Basics: From a Loop to a Graph (16)
  - Day 18 — State & Reducers: What Goes Where (16)
  - Day 19 — Control Flow: `Command`, `Send` & Subgraphs (16)
  - Day 20 — Persistence & Checkpointing: Save, Resume, Rewind (16)
  - Day 21 — Human-in-the-Loop: Pause, Ask, Resume (16)
- **Week 4 — Multi-agent, Production & Interviews**
  - Day 22 — Multi-Agent Systems: Supervisors, Handoffs & When Not To (16)
  - Day 23 — Streaming & Events: Make It Feel Fast (15)
  - Day 24 — Reliability: Surviving a Bad Day in Production (15)
  - Day 25 — Observability & Evaluation: Know Whether It Works (15)
  - Day 26 — MCP & the Vercel AI SDK: Tools Across Boundaries (15)
  - Day 27 — Deployment & Architecture: From Laptop to a Million Students (15)
  - Day 28 — Capstones & Interview Crash Course: Prove It (28)

## Week 1 — Foundations

### Day 01 — What an LLM Actually Is: Tokens, Context & Inference

*14 questions · [open the day](../week-01-foundations/day-01-llms-tokens-and-inference.md)*

#### Basic

<details>
<summary><b>Q: What is a token?</b></summary>

A chunk of text — roughly 4 characters or 0.75 English words — that the tokenizer maps to an
integer ID. Models operate on token IDs, not characters or words. Common words often get a
single token; rare words are split into several. Leading spaces are part of the token, so
`"cat"` and `" cat"` are distinct.
</details>

<details>
<summary><b>Q: What is a context window?</b></summary>

The maximum number of tokens a model can process in one call, counting **input and output
together**. Exceed it and you get an error or silent truncation. It's a hard architectural
limit, not a setting you can raise.
</details>

<details>
<summary><b>Q: What does temperature do?</b></summary>

It scales the logits before the softmax, which flattens or sharpens the probability
distribution over the next token. Low temperature concentrates probability on the top
candidates (predictable output); high temperature spreads it out (diverse output). It affects
**sampling**, not the model's knowledge — the underlying distribution is the same.
</details>

<details>
<summary><b>Q: Difference between temperature and top_p?</b></summary>

Temperature **rescales** every token's probability. `top_p` **truncates**: it keeps only the
smallest set of top tokens whose probabilities sum to `p`, then samples from those. Temperature
can still (rarely) pick a bizarre token; `top_p` removes bizarre tokens from consideration
entirely. Tune one, not both.
</details>

<details>
<summary><b>Q: Do LLMs have memory?</b></summary>

No. Every API call is stateless. Apparent memory is the application re-sending previous
messages as part of the input. Everything called "memory" in LangChain/LangGraph is a strategy
for deciding *what* to re-send within the context budget.
</details>

#### Intermediate

<details>
<summary><b>Q: Why do output tokens cost more than input tokens?</b></summary>

Input tokens are processed in a single parallel forward pass. Output tokens are generated
serially — one full forward pass per token, each conditioned on all previous ones. Serial GPU
time is more expensive than parallel, so providers price output at roughly 2–5× input.
</details>

<details>
<summary><b>Q: Why are hallucinations inherent rather than a bug?</b></summary>

The model is trained to maximise the likelihood of the next token given the context. There is
no separate "is this true?" step. When the training distribution makes a fluent, confident
answer more likely than an admission of ignorance, the model produces the fluent answer.
Mitigations work by changing the input distribution (retrieval, tools) or by explicitly making
"I don't know" a high-probability continuation (prompting).
</details>

<details>
<summary><b>Q: What is "lost in the middle"?</b></summary>

An empirical finding that models attend more reliably to information at the beginning and end
of a long context than to information in the middle. Practical implications: put the most
important instructions and the most relevant retrieved documents at the extremes, and prefer
retrieving 5 highly relevant chunks over dumping 100 mediocre ones.
</details>

<details>
<summary><b>Q: Why doesn't `temperature: 0` give byte-identical results?</b></summary>

`temperature: 0` means greedy decoding — pick the argmax. But the logits themselves vary
slightly run-to-run due to non-deterministic floating-point reduction order on GPUs, variable
batch composition on the server, and mixed-precision arithmetic. When two tokens are nearly
tied, tiny differences flip the argmax. Providers also silently update model weights. Never
assert exact string equality on model output.
</details>

<details>
<summary><b>Q: A user says your chatbot "gets slower and more expensive over a long conversation." Why?</b></summary>

Because the app re-sends the entire history on every turn. Turn *n* sends O(n) tokens, so total
cost across a conversation is O(n²). Fixes: sliding window, summarising older turns, or
retrieving only relevant past messages. Prompt caching (where supported) reduces the cost but
not the token count.
</details>

#### Advanced

<details>
<summary><b>Q: You must guarantee valid JSON output. Walk through your options, worst to best.</b></summary>

1. **Prompt only** — "respond in JSON". Fails a few percent of the time; the model adds prose or
   markdown fences.
2. **Prompt + parse-and-retry** — catch the parse error, feed it back, ask for a fix. Works, but
   costs an extra round trip and can loop.
3. **JSON mode** (`response_format: { type: "json_object" }`) — provider guarantees syntactically
   valid JSON, but *not* your schema.
4. **Tool/function calling with a schema** — the provider constrains generation to your schema.
   This is what `withStructuredOutput` / `with_structured_output` uses under the hood.
5. **Constrained decoding / grammar-based sampling** — the sampler is masked at each step so
   only schema-valid tokens are possible. Strongest guarantee; supported by some providers and
   local runtimes.

In production: use (4), validate with Zod/Pydantic anyway, and have a (2)-style retry as a
fallback. Day 06 builds all of this.
</details>

<details>
<summary><b>Q: How would you estimate the monthly cost of a chat product before building it?</b></summary>

```
cost/conversation ≈ Σ over turns [ (system + history_so_far + retrieved) × in_price
                                 + answer_len × out_price ]
```

Key drivers: average turns per conversation (this is the quadratic term), whether you do RAG
(retrieved chunks dominate input), and the history strategy. Then multiply by conversations/month
and add a 30–50% buffer for retries, evals and non-English users (worse token ratios).
Measure with real traffic ASAP — estimates are usually 2× off.
</details>

<details>
<summary><b>Q: What is a KV-cache and why does it matter to you as an application developer?</b></summary>

During generation, the attention keys and values for already-processed tokens are cached so
each new token only computes attention against the cache rather than recomputing everything.
Application-level consequences: (a) long *inputs* are relatively cheap and fast, long *outputs*
are not; (b) **prompt caching** exposes this to you — if you keep a long, stable prefix (system
prompt + few-shot examples + documents) *byte-identical* across calls, providers can reuse the
cache and charge much less. This is why you put the stable parts first and the variable parts
last in your prompt.
</details>

<details>
<summary><b>Q: Your RAG bot gives great answers in testing and bad ones in production. Give five hypotheses tied to today's material.</b></summary>

1. **Context overflow** — production docs are longer, so retrieved chunks push the question out
   of the window or get silently truncated.
2. **Lost in the middle** — you're stuffing 20 chunks; the relevant one lands in position 11.
3. **Non-English users** — token counts blow up, hitting limits your English tests never did.
4. **Temperature too high** for a factual task, so answers vary run to run and some are wrong.
5. **History unbounded** — by turn 15 the retrieved context is being crowded out by chat history.

Notice all five are today's concepts, not model quality.
</details>

---

### Day 02 — Prompt Engineering & Talking to Models With No Framework

*12 questions · [open the day](../week-01-foundations/day-02-prompt-engineering-and-raw-apis.md)*

#### Basic

<details>
<summary><b>Q: Difference between zero-shot and few-shot prompting?</b></summary>

Zero-shot gives instructions only. Few-shot includes worked input→output examples in the
prompt. Few-shot is more reliable for output *format*, domain-specific label vocabularies, and
edge cases, at the cost of extra input tokens on every call. Neither changes the model's
weights — few-shot is in-context learning, not training.
</details>

<details>
<summary><b>Q: What is chain-of-thought prompting?</b></summary>

Asking the model to produce intermediate reasoning before the final answer. Because the model
generates one token at a time and conditions on its own output, the reasoning tokens act as
working memory. It improves multi-step arithmetic, logic and planning tasks, and costs more
output tokens. Zero-shot CoT is "let's think step by step"; few-shot CoT shows examples that
include reasoning.
</details>

<details>
<summary><b>Q: What is ReAct?</b></summary>

Reason + Act: an interleaved loop of `Thought → Action → Observation`, repeated until the model
emits a final answer. The Observation contains real data from an external tool, so the model
grounds its reasoning in facts rather than recall. It's the foundational agent pattern — every
tool-using agent is a variation on it.
</details>

<details>
<summary><b>Q: Difference between "tool calling" and "function calling"?</b></summary>

They're the same mechanism. `functions`/`function_call` was OpenAI's original parameter naming;
`tools`/`tool_calls` replaced it and supports parallel calls. "Tool calling" is now the standard
term across providers. Both mean: the model emits a structured request naming a function and
arguments, and *your code* executes it.
</details>

#### Intermediate

<details>
<summary><b>Q: What happens internally when an agent invokes a tool?</b></summary>

1. Tool schemas are serialised into the prompt in a format the model was fine-tuned to recognise.
2. The model generates special tokens encoding a call: name + JSON arguments.
3. The provider parses those out of the token stream and returns `tool_calls` instead of `content`;
   generation stops.
4. **Your application** looks up and executes the function. The model executes nothing.
5. You append the assistant message (with `tool_calls`) plus a `role: "tool"` message carrying
   `tool_call_id` and a string result.
6. You call the model again with the extended history; it either calls another tool or answers.

Key point for interviews: the model only ever *requests*. Execution, validation, error handling
and looping are the application's job — which is precisely the job LangGraph structures.
</details>

<details>
<summary><b>Q: Why does text-based ReAct need a stop sequence?</b></summary>

The model has seen thousands of complete ReAct traces in training, so after writing an `Action:`
line it will happily continue with a fabricated `Observation:` and reason from invented data.
A stop sequence on `"Observation:"` forcibly ends generation so real tool output can be
inserted. Native tool calling removes the need — the model emits an end-of-turn token after
the call because that's how it was trained.
</details>

<details>
<summary><b>Q: When would you NOT use chain-of-thought?</b></summary>

- Simple classification/extraction — extra output tokens with no accuracy gain
- Latency-sensitive paths — reasoning tokens are serial time
- **Reasoning models** (o-series, R1, extended thinking) — they already reason internally;
  explicit CoT instructions are redundant and can degrade results
- When output must be strictly structured — reasoning text pollutes parsing unless you separate
  it (e.g. a `reasoning` field in a schema)
</details>

<details>
<summary><b>Q: How do you guarantee valid JSON from a model?</b></summary>

Escalating strength: (1) prompt only — unreliable; (2) JSON mode (`response_format`) — valid
JSON but arbitrary shape; (3) tool calling with a schema — provider constrains to your schema;
(4) constrained/grammar-based decoding — token-level masking, strongest.
In production: use (3), validate with Zod/Pydantic anyway, and keep a parse-and-retry fallback.
Never trust the model plus `JSON.parse` alone.
</details>

<details>
<summary><b>Q: What is self-consistency and when is it worth the cost?</b></summary>

Sample the same CoT prompt N times at moderate temperature and take the majority answer.
Correct reasoning paths converge; incorrect ones scatter. Costs N×, and requires comparable
answers (a number or label, not prose). Worth it when errors are expensive — and the vote
distribution doubles as a free **confidence score** you can route on.
</details>

#### Advanced

<details>
<summary><b>Q: Design a defence-in-depth strategy against prompt injection for an agent with database and email tools.</b></summary>

Prompt-level (weakest, still do it): system/user separation; delimit untrusted data in tags and
instruct the model to treat it as data; strip delimiter-escape attempts; restate key
constraints after the data.

Architectural (where the real security is):
- **Least privilege** — the DB tool gets a read-only connection scoped to the tenant; SQL goes
  through parameterised, allow-listed query templates, never raw model-generated SQL against prod.
- **Human-in-the-loop** on irreversible actions — email sending requires approval (Day 21).
- **Output validation** — the email tool validates recipients against an allow-list; the model
  can't invent an address.
- **Separate trust zones** — the agent summarising untrusted web content is a *different*
  agent with *no* tools; its output is treated as data by the privileged agent.
- **Monitoring** — log every tool call with arguments; alert on anomalies (Day 25).

The framing that lands in interviews: *prompt injection is not solvable at the prompt layer,
because the model has no mechanism to distinguish instructions from data. Treat all model
output as untrusted user input and put real authorisation boundaries around every side effect.*
</details>

<details>
<summary><b>Q: Your few-shot classifier is 94% accurate. Get it to 99% without fine-tuning.</b></summary>

1. **Build a labelled test set first** — you can't improve what you can't measure. Look at the
   6% failures and cluster them; usually 2–3 root causes dominate.
2. **Add examples targeting those clusters** — failures become few-shot examples. Highest ROI move.
3. **Dynamic few-shot** — retrieve the k most similar labelled examples per input from a vector
   store instead of fixed examples (Week 2).
4. **Constrain the output space** — tool calling with an enum makes off-vocabulary labels
   impossible.
5. **Route hard cases** — use self-consistency confidence or logprobs; when confidence is low,
   escalate to a bigger model or CoT. Cheap model on 95% of traffic, expensive path on 5%.
6. **Decompose** — if two labels are confused constantly, add a dedicated binary tie-breaker
   prompt for just that pair.
7. **Accept a ceiling** — some fraction of your "errors" are genuinely ambiguous or mislabelled.
   Check inter-annotator agreement before chasing 99%.

Fine-tuning is the last resort: it beats prompting on narrow, high-volume, stable tasks, but
costs a data pipeline and re-training on every taxonomy change.
</details>

<details>
<summary><b>Q: How would you decide between prompt engineering, RAG, and fine-tuning?</b></summary>

They solve different problems:

| Problem | Solution |
|---|---|
| Model doesn't know the *format* you want | Prompting / few-shot |
| Model doesn't know the *facts* (your docs, live data) | **RAG** |
| Model doesn't know the *behaviour/style* deeply, and you have thousands of examples | Fine-tuning |

Order of attempts: prompting → few-shot → RAG → fine-tuning. Cost and iteration speed get worse
at every step. The classic mistake is fine-tuning to inject knowledge — fine-tuning teaches
*patterns*, not facts, and the facts go stale immediately. RAG is the right tool for knowledge.
</details>

---

### Day 03 — JS & Python Essentials for AI · Why LangChain Exists

*11 questions · [open the day](../week-01-foundations/day-03-js-python-essentials-and-why-langchain.md)*

#### Basic

<details>
<summary><b>Q: ESM vs CommonJS — what's the practical difference for an AI project?</b></summary>

CommonJS uses `require`/`module.exports` and is Node's historical default; ESM uses
`import`/`export`, is the standard, and supports **top-level await**. LangChain JS is ESM-first,
and nearly every example awaits at the top level of a module, so you set `"type": "module"` in
`package.json`. Without it you get `Cannot use import statement outside a module`.
</details>

<details>
<summary><b>Q: What is Zod and why does LangChain use it?</b></summary>

Zod is a runtime schema-validation library for JS/TS. LangChain uses it because TypeScript types
are erased at compile time, but tool arguments and structured output must be validated at
*runtime* — and, crucially, converted to **JSON Schema** to send to the model. Zod gives you
one definition that serves as validator, type source, and model-facing schema.
Pydantic plays the identical role in Python.
</details>

<details>
<summary><b>Q: What does `.describe()` on a Zod field actually do?</b></summary>

It sets the `description` in the generated JSON Schema, and that description is sent to the
model as part of the tool/schema definition. It is prompt text, not a code comment — a clear
description measurably improves how correctly the model fills that field.
</details>

<details>
<summary><b>Q: Difference between `invoke` and `ainvoke` in LangChain Python?</b></summary>

`invoke` is synchronous and blocks; `ainvoke` is the `async` version you `await`. The `a`
prefix marks async variants across the API (`astream`, `abatch`, `ainvoke`). Use sync in
scripts and notebooks, async in web servers so one request doesn't block the event loop.
LangChain **JS has no sync variants** — everything returns a Promise.
</details>

#### Intermediate

<details>
<summary><b>Q: `Promise.all` vs `Promise.allSettled` — when does the choice matter in AI code?</b></summary>

`Promise.all` rejects as soon as any promise rejects, and you lose the results of the ones that
succeeded. `allSettled` always resolves with a status per item.

For LLM work this matters constantly: embedding 500 chunks where one hits a 429 shouldn't
discard 499 successful embeddings. Use `allSettled` (or `asyncio.gather(..., return_exceptions=True)`)
for batch work, and add concurrency limits so you don't cause the rate limit in the first place.
</details>

<details>
<summary><b>Q: Why do LLM streaming APIs use async iterators?</b></summary>

Streaming is inherently a sequence of values arriving over time, which is exactly what an async
iterator models: each `next()` returns a promise resolving when the next chunk arrives.
`for await...of` consumes them; `async function*` produces them. This lets you compose
transformations (token → sentence → translated sentence) without buffering the whole response,
so time-to-first-byte stays low.
</details>

<details>
<summary><b>Q: What does the `Runnable` interface give you that plain functions don't?</b></summary>

A uniform contract — `invoke`, `stream`, `batch`, plus config (callbacks, tags, concurrency) —
implemented by every component. Because a composed chain is itself a `Runnable`, composition is
closed under the interface: you can nest chains in chains, and `.stream()` propagates through
the whole pipeline without custom plumbing. It also means retries, fallbacks, and tracing can
be added as generic modifiers rather than reimplemented per component.
</details>

<details>
<summary><b>Q: Why does jitter matter in retry logic?</b></summary>

Without jitter, all clients that fail at the same moment retry at the same moment, recreating
the overload — the thundering herd. Randomising each delay spreads retries out. Also honour
`Retry-After` when the server provides it, and cap total retry time rather than just attempts,
since exponential backoff can easily exceed the caller's timeout.
</details>

#### Advanced

<details>
<summary><b>Q: Why use LangChain instead of calling the provider SDK directly?</b></summary>

For a single call, don't — the SDK is clearer with fewer dependencies. LangChain earns its
place when you have **composition**: multiple steps whose interfaces must line up, streaming
that must propagate through all of them, retries/fallbacks applied uniformly, and tracing
threaded through every step.

Concretely it gives you: (1) the `Runnable` interface so composition, streaming and batching
work uniformly; (2) provider abstraction so model choice is config, not a rewrite;
(3) structured output (schema → JSON Schema → tool call → validate → retry); (4) the entire
retrieval stack; (5) LangGraph's agent runtime with persistence and interrupts;
(6) observability hooks.

The honest counterpoint: it's a dependency with its own upgrade cost, and its 0.x-era
high-level chains earned a reputation for opacity. LangChain 1.x's answer was to make
composition (LCEL) and control flow (LangGraph) explicit rather than hidden.
</details>

<details>
<summary><b>Q: When would you deliberately choose NOT to use a framework?</b></summary>

- **Single-step features.** One prompt, one response. Nothing to compose.
- **Extreme latency/bundle constraints**, e.g. edge functions where every KB counts.
- **Provider features not yet exposed** by the abstraction — you'd spend more time fighting it
  than the abstraction saves.
- **Team capability.** Code your on-call engineer can debug beats code that's shorter.
- **Orchestration is your product.** If the control loop is your differentiator, own it.

A pragmatic middle path: use LangChain for the pieces where it's strongest (retrieval,
structured output, provider abstraction) and plain functions elsewhere. Because plain functions
compose into chains via `RunnableLambda`, this isn't all-or-nothing — which is itself a good
argument for the `Runnable` design.
</details>

<details>
<summary><b>Q: A teammate says "LangChain is bloated, we should write it ourselves." How do you respond?</b></summary>

Agree with the part that's true, then make it concrete:

1. **Separate the criticism from the target.** The bloat complaint is mostly about 0.x
   high-level chains. 1.x's LCEL and LangGraph are explicit, inspectable composition.
2. **List the specific capabilities we need** and ask what each costs to build and maintain:
   embedding batching, vector-store adapters, retrievers with metadata filters, checkpointing,
   interrupt/resume, stream propagation, tracing. Usually 2–3 of those alone justify it.
3. **Ask what "ourselves" means at month six** — a homegrown framework is still a framework,
   just one with no docs, no community, and one maintainer who might leave.
4. **Propose a decision rule instead of a preference**: use the framework where we need ≥3
   composed steps or swappable providers; drop to the SDK for single-step calls. Both can
   coexist in one codebase.
5. **Reduce the risk**: pin versions, keep an eval suite green across upgrades, and keep the
   provider-specific escape hatch open.

The meta-point: "framework vs no framework" is rarely the real question. "Which specific
capabilities do we need, and what's the cheapest credible way to get them?" is.
</details>

---

### Day 04 — LangChain Models: invoke, stream, batch & Message Types

*11 questions · [open the day](../week-01-foundations/day-04-langchain-models.md)*

#### Basic

<details>
<summary><b>Q: Difference between `invoke`, `stream` and `batch`?</b></summary>

`invoke` sends one input and returns one complete `AIMessage`. `stream` sends one input and
returns an async iterator of `AIMessageChunk`s as they're generated — same total time, much
better perceived latency. `batch` sends *multiple independent* inputs concurrently (with a
configurable concurrency cap) and returns results in input order. Use `batch` only for
independent inputs — never for conversation turns, which are sequentially dependent.
</details>

<details>
<summary><b>Q: What are the message types and when do you use each?</b></summary>

- **SystemMessage** — instructions/persona/constraints. Usually exactly one, at the front.
- **HumanMessage** — user input.
- **AIMessage** — model output; also carries `tool_calls` when the model requests a tool.
- **ToolMessage** — the *result* of executing a tool, linked back by `tool_call_id`.

A conversation is an ordered array of these. The role is rendered into provider-specific
formatting tokens at request time.
</details>

<details>
<summary><b>Q: Difference between an LLM and a Chat model in LangChain?</b></summary>

An LLM (`BaseLLM`) takes a string and returns a string — the old completion-model interface.
A Chat model (`BaseChatModel`) takes a **list of messages** and returns an `AIMessage`, so it
understands roles, tool calls and multimodal content. Nearly every modern provider is chat-only;
chat models are what you should use. LLM-style classes remain mostly for legacy compatibility.
</details>

<details>
<summary><b>Q: How do you count tokens for a request?</b></summary>

Read `usage_metadata` on the response — `{ input_tokens, output_tokens, total_tokens }`,
normalised across providers. When streaming, usage arrives in the **final** chunk, so accumulate
chunks (`concat` / `+`) and read it from the total. To count *before* sending, use
`getNumTokens` / `get_num_tokens` on the model, or the provider's tokenizer directly.
</details>

#### Intermediate

<details>
<summary><b>Q: Why do `AIMessageChunk`s support addition?</b></summary>

Because reassembling a streamed response is non-trivial: text content concatenates, but tool
calls arrive as *fragments* that must be merged by index (a single tool call's JSON arguments
are split across many chunks), and usage metadata appears only in the final chunk. Making
chunks addable puts that merge logic in one tested place, so `full = full.concat(chunk)` gives
you a correct complete message including assembled tool calls.
</details>

<details>
<summary><b>Q: How does LangChain make providers interchangeable when their APIs differ so much?</b></summary>

Each integration package implements `BaseChatModel` with two translation layers: outbound,
converting `BaseMessage[]` into that provider's wire format (Anthropic takes `system` as a
separate top-level field, Gemini uses `contents`/`parts`, OpenAI-style uses a flat `messages`
array); and inbound, normalising the response into `AIMessage` with consistent `content`,
`tool_calls` and `usage_metadata`. Your code only ever sees the normalised types, so provider
choice stops leaking into call sites. The trade-off is that provider-specific features need
either explicit support or an escape hatch (`modelKwargs` / `model_kwargs`).
</details>

<details>
<summary><b>Q: What is `initChatModel` / `init_chat_model` and when would you use it?</b></summary>

A universal factory that takes a `"provider:model"` string and returns the right chat model,
lazily importing the integration package. Use it when the provider should be *configuration*
rather than code — e.g. `MODEL=groq:llama-3.3-70b-versatile` in env, so ops can switch models
without a deploy. It also supports `configurableFields`, letting you pick the model per call at
runtime. Use the direct class when you need provider-specific constructor options or want the
dependency to be explicit. Note the JS version is awaited; the Python one isn't.
</details>

<details>
<summary><b>Q: How would you implement conversation memory with just a chat model?</b></summary>

Keep an array of messages; append the `HumanMessage` before each call and the returned
`AIMessage` after. Send the whole array each turn. Then bound it, because cost is O(n²) over a
conversation: a sliding window, or `trimMessages`/`trim_messages` with a token budget that
preserves the system message and starts on a human turn.

The important caveat: trimming *loses* information — no window size is both cheap and
remembers everything. The real solutions are summarising older turns into a rolling summary, or
storing facts externally and retrieving the relevant ones. Persisting across sessions needs a
store — which is what LangGraph checkpointers provide.
</details>

#### Advanced

<details>
<summary><b>Q: Walk through everything that happens between `model.invoke(messages)` and the response.</b></summary>

1. **Input coercion** — strings/dicts/tuples normalised to `BaseMessage[]`.
2. **Config resolution** — constructor params merged with per-call options and runtime config
   (callbacks, tags, metadata, concurrency).
3. **Callback dispatch** — `on_chat_model_start` fires; this is the hook LangSmith tracing uses.
4. **Outbound translation** — messages converted to the provider's wire format, including
   provider quirks (system-as-separate-field, content-block shapes, tool schema format).
5. **HTTP request** — with the client's timeout and automatic retries on transient errors.
6. **Inbound translation** — provider response normalised into `AIMessage`: content, assembled
   `tool_calls`, `usage_metadata`, `response_metadata`.
7. **Callback dispatch** — `on_llm_end` (or `on_llm_error`).
8. **Return.**

Steps 4 and 6 are where the abstraction earns its keep; step 3/7 are why tracing works without
you instrumenting anything.
</details>

<details>
<summary><b>Q: Design a model layer for a product serving 3 tiers: free, pro, enterprise.</b></summary>

**Routing by tier** — free gets a small fast model (8B), pro gets a mid-tier, enterprise gets
the frontier model plus a dedicated-capacity provider. Implement as a factory keyed by tier so
the choice lives in one place.

**Reliability** — every tier gets `.withFallbacks()` across *providers*, not just models, so one
provider outage doesn't take you down. Log every fallback: silent degradation to a weaker model
is how quality regressions hide.

**Cost control** — per-tenant token budgets tracked from `usage_metadata`; a hard cap that
returns a friendly error rather than a surprise bill. Cache identical requests. Trim history
aggressively on free tier, generously on enterprise.

**Latency** — stream everywhere for perceived speed. Route by task, not just tier: even
enterprise should use the 8B model for classification and routing, reserving the big model for
generation. Most overspending comes from using one big model for everything.

**Observability** — tags/metadata on every call (`tenant`, `tier`, `feature`) so you can slice
cost and quality per segment in LangSmith.

**Configurability** — model IDs in env/config, not code, so you can shift traffic during an
incident without a deploy. `initChatModel` with `configurableFields` fits this well.
</details>

<details>
<summary><b>Q: Your streaming endpoint shows the first token after 4 seconds. How do you debug it?</b></summary>

Separate the three contributors:

1. **Your server's pre-model work** — instrument the time from request receipt to the first
   `on_chat_model_start` callback. If retrieval or auth is slow, the model isn't the problem.
2. **Provider queue + prompt processing (TTFT)** — measure time from request sent to first
   chunk. If the prompt is huge (long history, many retrieved chunks, big tool schemas), prompt
   processing dominates: trim history, retrieve fewer chunks, prune unused tools.
3. **Your transport** — a buffering proxy, compression, or a framework that batches the
   response will hide chunks that already arrived. Verify with `curl -N` directly against the
   provider vs against your endpoint. Check `Cache-Control: no-transform` and disable buffering
   for SSE.

Common real causes, in the order I'd check: response buffering in the reverse proxy; awaiting
the *whole* response server-side then re-emitting it; a large prompt; and a cold model.
Fixes: stream end-to-end (never `await` the full response), shrink the prompt, use a smaller
model for the first-response path, and send an early keepalive so the connection opens fast.
</details>

---

### Day 05 — Prompts & Templates

*10 questions · [open the day](../week-01-foundations/day-05-prompts-and-templates.md)*

#### Basic

<details>
<summary><b>Q: What is a PromptTemplate?</b></summary>

A reusable, parameterised prompt. It declares its input variables, validates that they're all
provided, substitutes them into the template text, and returns a prompt value. It's a
`Runnable`, so it composes with models via `.pipe()` / `|`. Compared to string concatenation it
gives you validation, reuse, and composability.
</details>

<details>
<summary><b>Q: Difference between PromptTemplate and ChatPromptTemplate?</b></summary>

`PromptTemplate` renders to a **single string** — the format old completion models expect.
`ChatPromptTemplate` renders to a **list of messages** with roles (system/human/ai), which is
what modern chat models expect. Use `ChatPromptTemplate` for essentially all new work; roles
carry real signal that a flattened string loses.
</details>

<details>
<summary><b>Q: What is MessagesPlaceholder for?</b></summary>

It reserves a slot in a chat template where an **array of messages** is spliced in at render
time — normally conversation history. Unlike a `{variable}`, which substitutes one string, a
placeholder inserts zero or many real message objects, preserving their roles. Mark it
`optional` so the first turn (empty history) doesn't fail.
</details>

<details>
<summary><b>Q: How do you include a literal `{` in a prompt template?</b></summary>

Double it: `{{` and `}}`. This trips people up constantly when a prompt contains a JSON example.
Alternatively switch to mustache templating (`templateFormat: "mustache"`), where `{{var}}` is
the variable syntax and single braces are literal — convenient for prompts full of JSON or code.
</details>

#### Intermediate

<details>
<summary><b>Q: Why use a template instead of a formatted string?</b></summary>

Four reasons: **validation** (a missing variable throws with its name instead of silently
inserting `undefined`); **structure** (you get real messages with roles, not a flattened
string); **reuse** (one definition, importable, versionable, testable); and **composability**
(it's a `Runnable`, so `prompt | model | parser` works and streaming/batching/tracing propagate
for free). The validation point alone catches a whole class of silent quality bugs.
</details>

<details>
<summary><b>Q: What are partial variables and when are they useful?</b></summary>

`partial()` pre-fills some variables and returns a new template needing only the rest. Two main
uses: **specialisation** — one base template becomes several ready-to-use prompts (per mode, per
tenant, per language) sharing one definition; and **dynamic values** — a partial can be a
*function* evaluated at render time, so things like today's date, a feature flag, or a request
ID get injected without threading them through every call site.
</details>

<details>
<summary><b>Q: How would you build a few-shot prompt where the examples change per input?</b></summary>

Use an **example selector** instead of a static list. `SemanticSimilarityExampleSelector`
embeds your example pool, embeds the incoming input, and retrieves the k nearest examples,
which the few-shot template then renders. Benefits: relevance (examples match the input's
domain), and you can hold a large example pool while only paying tokens for k of them.
Alternatives include length-based selection (fit as many as the budget allows) and MMR
selection (relevant *and* diverse). This is usually the highest-ROI upgrade to a plateaued
few-shot classifier.
</details>

<details>
<summary><b>Q: A teammate concatenates history into one string instead of using MessagesPlaceholder. What's wrong with that?</b></summary>

Three things. **Quality**: chat models were fine-tuned on role-structured conversations;
flattening to `"Human: ...\nAI: ..."` inside a single user message is off-distribution and
measurably worse. **Correctness**: tool calls and multimodal content can't survive
stringification, so agents break. **Maintainability**: you can no longer trim, filter, or
summarise messages as objects, and your history rendering is duplicated everywhere. Providers
also apply their own chat templating to real messages — you'd be fighting it.
</details>

#### Advanced

<details>
<summary><b>Q: How would you design a prompt management system for a team of 10 shipping to production?</b></summary>

**Storage & versioning** — prompts as code in a dedicated module, in git, code-reviewed. Every
prompt gets a stable ID and a version. For non-engineers editing prompts, a prompt registry
(LangSmith Hub or your own DB) with the app pinning a version, never "latest".

**Testing** — two layers. Cheap deterministic tests in CI: every prompt renders with its sample
variables, declares no unused variables, produces the expected message count/roles. Then eval
tests against a labelled dataset per prompt, gated on a minimum score before merge (Day 25).

**Rollout** — treat a prompt change like a code change: canary it on a traffic slice, compare
online metrics (thumbs-down rate, escalation rate, cost/latency) against control, and keep a
one-click revert. Prompt changes have caused more production incidents than model changes.

**Observability** — tag every trace with prompt ID + version so you can attribute a quality
regression to a specific edit. Log the *rendered* prompt, not just the variables.

**Structure** — one persona/shared block, specialised via partials, so a persona change is one
edit. Keep the stable prefix first for prompt-cache hits; put variable content last.

**Governance** — a checklist for prompts touching untrusted input (delimiting, role separation),
and a rule that no prompt hard-codes a model-specific quirk without a comment explaining it.
</details>

<details>
<summary><b>Q: Your prompt works with Groq but produces preambles on Gemini. How do you handle provider differences in prompts?</b></summary>

First, diagnose rather than patch: render the prompt for both and confirm they're identical, and
check whether the difference is instruction-following or *system-message handling* — some
providers weight the system message differently, and Anthropic takes it as a separate top-level
field entirely.

Then, in order of preference:
1. **Make the instruction structural rather than verbal** — a few-shot example whose output
   starts directly with the desired first character beats any "do not add a preamble" sentence.
   This generalises across providers.
2. **Constrain the output space** — structured output/tool calling makes a preamble
   unrepresentable. This is the real fix, and it's tomorrow's topic.
3. **Post-process** — strip a known preamble pattern in an output parser. Cheap, reliable,
   but hides the problem.
4. **Provider-specific overrides as a last resort** — a `promptOverrides[provider]` map. Keep it
   small and documented, because it re-introduces exactly the provider coupling the abstraction
   removed.

And the process point: this is why you need an eval set that runs against *every* provider you
support. Provider swaps are cheap in code and expensive in behaviour — the abstraction makes
the call site identical, not the output.
</details>

---

### Day 06 — Output Parsers & Structured Output (Zod ↔ Pydantic)

*11 questions · [open the day](../week-01-foundations/day-06-output-parsers-structured-output.md)*

#### Basic

<details>
<summary><b>Q: What is an output parser?</b></summary>

A `Runnable` that transforms a model's output into something more useful — a plain string, a
parsed object, a list. It sits at the end of a chain: `prompt | model | parser`. Common ones are
`StringOutputParser` (extract text), `JsonOutputParser` (parse JSON, tolerating markdown
fences), and list parsers.
</details>

<details>
<summary><b>Q: What is structured output?</b></summary>

Getting a validated object matching a schema you define, rather than free text you must parse.
You define the schema in Zod or Pydantic and call `withStructuredOutput` /
`with_structured_output`. The schema is converted to JSON Schema and sent to the provider as a
constraint, so the model's output is shaped correctly by construction rather than by hope.
</details>

<details>
<summary><b>Q: What is Zod, and what's the Python equivalent?</b></summary>

Zod is a TypeScript-first runtime schema and validation library. Pydantic is the Python
equivalent. Both let you declare a schema once and use it for three things: runtime validation,
static types, and — critically here — generating the JSON Schema that gets sent to the model.
Field descriptions in either are sent to the model as prompt text.
</details>

<details>
<summary><b>Q: Why not just prompt "respond in JSON" and call JSON.parse?</b></summary>

It fails a few percent of the time, and the failures are the expensive kind: markdown code
fences, a leading "Sure, here's the JSON:", trailing commentary, or valid JSON with the wrong
keys. `JsonOutputParser` handles the formatting noise; only a schema constraint handles the
wrong-shape problem. At production volume, "a few percent" is a lot of 500s.
</details>

#### Intermediate

<details>
<summary><b>Q: How does `withStructuredOutput` work under the hood?</b></summary>

It converts your Zod/Pydantic schema to JSON Schema, binds it to the model as a **tool
definition**, and forces `tool_choice` to that single tool. The provider then constrains
generation so the emitted arguments match the schema. The response arrives as a `tool_call`
rather than as content; LangChain extracts `.args`, validates against the original schema, and
returns the typed object.

So it's tool calling with one forced tool where you keep the arguments and never execute
anything. Providers without tool support fall back to JSON mode with the schema described in
the prompt — a weaker guarantee.
</details>

<details>
<summary><b>Q: Why does the order of fields in a schema matter?</b></summary>

The model generates the object left to right, one token at a time, each token conditioned on the
previous ones. A `reasoning` field placed **before** `label` means the model works through the
problem before committing to an answer — chain-of-thought inside the schema. Placed after, it
commits first and rationalises, which is measurably worse on hard cases. Same reason CoT works
at all: tokens are compute.
</details>

<details>
<summary><b>Q: How do you handle a field the input might not contain?</b></summary>

Make it nullable/optional and say so in the description: `.nullable().describe("...or null if
not stated")`. If the field is required, the model has no valid way to express "not present", so
it invents a value — this is one of the largest sources of hallucinated data in extraction
pipelines. Making "unknown" representable is the fix. Adding a `confidence` field on top gives
you a routing signal for the remaining low-quality cases.
</details>

<details>
<summary><b>Q: Structured output guarantees the shape. What does it NOT guarantee?</b></summary>

The meaning. `subtotal: 12.00` is schema-valid regardless of whether the line items actually sum
to 12.00. Schemas enforce types, enums, ranges and required fields; they cannot enforce
cross-field arithmetic, referential integrity against your database, or factual correctness.

Production extraction therefore has two layers: schema validation (framework) and business-rule
validation (your code). The second layer's output should drive routing — clean records
auto-process, violating ones go to human review.
</details>

#### Advanced

<details>
<summary><b>Q: Design an extraction pipeline for 10,000 invoices/day that must be 99.5% accurate.</b></summary>

**Extraction** — structured output with a well-designed schema: nullable fields for anything
optional, enums for currency/status, a `reasoning` field first, a `confidence` field last,
`temperature: 0`. Batch with a concurrency cap to stay inside rate limits.

**Validation, in layers** — schema (framework), then business rules (line items sum to subtotal,
tax within a plausible band, total = subtotal + tax, date parseable and not in the future,
vendor resolvable against the supplier table). Each failing rule is a signal, not just a
rejection.

**Routing** — auto-post only when all rules pass *and* confidence is high. Everything else goes
to a human review queue, ordered by value at risk. This is how you get 99.5% end-to-end without
needing 99.5% from the model.

**Escalation** — cheap model first; on low confidence or rule violation, retry once with a
larger model before queuing for a human. Most teams find the small model handles 80–90% of
documents.

**Measurement** — a golden set of a few hundred hand-labelled invoices, field-level accuracy
(not document-level), run on every prompt/schema/model change. Track per-field error rates;
they're rarely uniform, and the fix for a bad `date` field is different from a bad `total`.

**Feedback loop** — human corrections in the review queue are labelled data. Feed them back as
few-shot examples (retrieved dynamically per input) and as new golden-set entries. This is what
actually moves you from 95% to 99.5%.

**Ops** — idempotency keys so a retry can't double-post; a dead-letter queue for repeated
failures; cost and latency dashboards per field; alerting on confidence-distribution drift,
which is your early warning that a provider changed a model underneath you.
</details>

<details>
<summary><b>Q: When would you NOT use structured output?</b></summary>

- **Free-form generation** — an essay, an explanation, a chat reply. Forcing it into a schema
  constrains the model unnecessarily and can hurt quality.
- **Streaming text to a UI** — you want tokens, not progressively complete objects. (Though
  structured output *can* stream partial objects when that's what you want.)
- **Providers without tool support** — you'd be on the weaker JSON-mode path, which sometimes
  isn't worth the added complexity versus a `JsonOutputParser`.
- **Very deep or highly variable shapes** — accuracy degrades with nesting depth. Split into
  multiple calls, or extract a flat shape and assemble in code.
- **When the schema constrains the answer wrongly** — a fixed enum forces the model to pick a
  category even when none fits. Always include an `OTHER` member plus a free-text field, or
  you'll get confidently miscategorised data.

There's also a subtler cost: a schema is a hypothesis about the data. If your schema says every
invoice has a `vendor`, you'll never discover the 2% that don't — you'll just get invented
vendors. Nullable fields and a `confidence` signal are how you keep the pipeline honest about
what it doesn't know.
</details>

<details>
<summary><b>Q: Your structured output works on 95% of inputs. Get to 99%. Walk through your approach.</b></summary>

**Diagnose before fixing.** Collect the 5% failures and cluster them. In my experience they
split into roughly: inputs genuinely missing the field, inputs where the field is ambiguous,
schema-too-deep failures, and provider flakiness. Each has a different fix, and guessing wastes
weeks.

Then, in rough ROI order:

1. **Make unknowns representable** — nullable fields with explicit "or null if absent"
   descriptions. Usually the single biggest win, because it converts "invents a value" into
   "correctly says nothing".
2. **Sharpen descriptions** — they're prompt text. Add a concrete example of the format inside
   the description (`"ISO date, e.g. 2024-03-14"`).
3. **Constrain harder** — replace free strings with enums wherever the value space is closed.
4. **Reasoning field first** — cheap, and it helps most on the ambiguous cluster.
5. **Flatten the schema** — if failures correlate with nesting depth, split into two calls and
   assemble in code.
6. **Dynamic few-shot** — retrieve the k most similar previously-corrected examples and include
   them. This is what specifically targets the ambiguous cluster.
7. **Escalate on low confidence** — route the bottom decile to a stronger model. Cheap model on
   90% of traffic, expensive path where it's needed.
8. **Retry + cross-provider fallback** — handles the flakiness cluster, and log which tier fired
   so silent degradation is visible.

**And know when to stop.** Some of that last 1% is genuinely ambiguous input where two humans
would disagree. Measure inter-annotator agreement on your golden set before targeting a number
above it — otherwise you're tuning against noise. At that point the right answer is a human
review queue, not a better prompt.
</details>

---

### Day 07 — LCEL & Runnables (the #1 interview topic)

*11 questions · [open the day](../week-01-foundations/day-07-lcel-and-runnables.md)*

#### Basic

<details>
<summary><b>Q: What is LCEL?</b></summary>

LangChain Expression Language — a declarative way to compose components using `.pipe()` in JS or
the `|` operator in Python. It isn't a separate language or a compiler; it's operator overloading
on the `Runnable` interface. Composing two Runnables produces another Runnable, so chains nest
freely, and streaming, batching, async, retries and tracing work across the whole composition
without glue code.
</details>

<details>
<summary><b>Q: What is a Runnable?</b></summary>

The core LangChain interface. Anything implementing it provides `invoke` (one input → one
output), `stream` (incremental output), `batch` (many inputs concurrently), and `pipe`
(composition). Models, prompts, parsers, retrievers, lambdas, and entire chains all implement
it — which is what makes composition uniform.
</details>

<details>
<summary><b>Q: Difference between RunnableSequence and RunnableParallel?</b></summary>

`RunnableSequence` runs steps **one after another**, passing each output as the next input —
that's what `.pipe()` / `|` builds. `RunnableParallel` runs several Runnables **concurrently on
the same input** and collects results into an object keyed by name. Sequence is for dependent
steps; Parallel is for independent ones, and it turns sum-of-latencies into max-of-latencies.
</details>

<details>
<summary><b>Q: What is RunnableLambda?</b></summary>

A wrapper that turns any function into a Runnable so it can sit in a chain. It's used for
reshaping data between steps, computing derived values, and light logic. Plain functions are
auto-coerced when you pipe them. It takes exactly one argument — pass an object if you need
several.
</details>

#### Intermediate

<details>
<summary><b>Q: Difference between RunnablePassthrough and RunnableAssign?</b></summary>

`RunnablePassthrough` is the identity — it returns its input unchanged. It's used inside a
parallel block to carry the original input forward alongside computed values.

`RunnableAssign` (via `RunnablePassthrough.assign()`) takes a dict input and **adds** keys to
it, preserving everything already there.

The three-way contrast is the thing to have crisp:

| | `{a: 1}` becomes |
|---|---|
| `RunnableParallel({b: chain})` | `{b: ...}` — `a` is **lost** |
| `RunnablePassthrough.assign({b: chain})` | `{a: 1, b: ...}` — `a` **survives** |
| `RunnablePassthrough()` | `{a: 1}` — unchanged |

Assign is how you accumulate context through a multi-step pipeline.
</details>

<details>
<summary><b>Q: How does streaming work through a chain, and what breaks it?</b></summary>

`RunnableSequence.stream` finds the last step that can transform incrementally, runs everything
before it with `invoke`, and pipes async iterators from that point onward. So a
`prompt | model | parser` chain streams tokens as the model produces them.

It breaks when a step needs its complete input before producing any output — a typical
`RunnableLambda` like `(s) => s.toUpperCase()`. That step buffers, so the chain's *output* only
starts flowing once the model has finished. Everything after a non-streaming step is blocked.

Fixes: put transformations before the model, accept the buffering, or write the lambda as an
async generator that consumes and yields chunks.
</details>

<details>
<summary><b>Q: How would you debug an LCEL chain that returns the wrong thing?</b></summary>

The rule is that **output of step N must match input of step N+1**, so almost every bug is a
type mismatch at one seam.

1. **Invoke sub-chains independently.** Because composition is closed, any prefix of the chain
   is itself a Runnable you can call directly. Binary-search the pipeline.
2. **Insert tap lambdas** that log and return their input unchanged.
3. **Name the steps** with `withConfig({ runName })` and read the LangSmith trace — you get
   input and output for every node.
4. **Print the structure** — `chain.get_graph().print_ascii()` in Python shows whether you built
   the shape you meant.
5. **Check for `RunnableParallel` where you meant `assign`** — silently dropping keys is the
   single most common cause of "missing input variable" downstream.
</details>

<details>
<summary><b>Q: When would you use RunnableBranch versus just a lambda that returns a Runnable?</b></summary>

They're equivalent in effect — LangChain invokes a Runnable returned from a lambda.
`RunnableBranch` is more declarative and shows up as a distinct node in traces, which helps when
routing logic is a core part of the design. A lambda is more readable when the condition is
complex or when you're choosing between many options from a lookup table.

Either way, both are **static** routing: the structure is fixed and data flows forward once.
When the routing decision needs to be revisited after seeing a result — "try this, and if it
fails, try something else" — you've left LCEL's territory and want a graph.
</details>

#### Advanced

<details>
<summary><b>Q: How does LCEL actually work under the hood?</b></summary>

`.pipe()` constructs a `RunnableSequence` holding references to its steps — it's a linked list
of objects, not compiled code. `invoke` walks the steps, threading a `config` object through
each call.

That config is where the non-obvious value lives: it carries a callback manager that gets forked
per step, so each child run gets its own ID with a parent pointer. That's how LangSmith
reconstructs a nested trace with zero instrumentation from you. It also carries tags, metadata,
concurrency limits, and recursion limits.

`stream` is the more interesting implementation: it finds the last step with a `transform`
method (one that accepts an async iterator), runs the prefix with `invoke`, and chains iterators
from there. `RunnableParallel` uses `Promise.all` / `asyncio.gather` (or a thread pool for sync
Python), giving every branch the identical input.

The design consequence worth stating: because composition is closed under the interface, generic
capabilities — retries, fallbacks, config, tracing — can be implemented **once** as wrappers
rather than per component. That's the actual payoff, more than the syntax.
</details>

<details>
<summary><b>Q: What are LCEL's limitations, and when do you reach for LangGraph?</b></summary>

LCEL builds a **directed acyclic graph**. Data flows forward, each step runs once, and the
structure is fixed at build time. That's a great fit for retrieve → prompt → generate → parse.

It's the wrong fit when you need:

- **Cycles** — an agent that calls a tool, observes the result, and decides whether to call
  another. You can fake it with a recursive lambda, but you lose streaming, tracing coherence,
  and any sane view of state across iterations.
- **Shared mutable state** — LCEL threads a value through steps; there's no state object that
  multiple nodes read and update with defined merge semantics (reducers).
- **Persistence and resumption** — pausing mid-execution, saving, and resuming later.
- **Human-in-the-loop** — interrupting before a step, waiting for approval, then continuing.
- **Fine-grained control flow** — conditional edges evaluated at runtime, fan-out to a dynamic
  number of branches, subgraphs.

LangGraph adds exactly those: nodes, edges, a typed state object with reducers, checkpointers,
and interrupts. And it composes both ways — a compiled graph is itself a `Runnable`, so you can
put a graph inside an LCEL chain, and LCEL chains inside graph nodes.

The rule I'd give: **if data flows one direction, use LCEL. If control flows in a loop, use
LangGraph.**
</details>

<details>
<summary><b>Q: Design an LCEL chain for a RAG pipeline with query rewriting, retrieval, reranking and citation.</b></summary>

Sketch first, then the reasoning:

```
input: { question, history }

  ├─ assign(standaloneQuestion) ─── rewrite the question using history so
  │                                  "what about the second one?" becomes retrievable
  ├─ assign(docs) ──────────────── parallel: { vector: vectorRetriever,
  │                                            keyword: bm25Retriever }
  │                                  then merge + dedupe in a lambda
  ├─ assign(reranked) ──────────── cross-encoder rerank, take top 5
  ├─ assign(context) ───────────── format docs with [1] [2] markers for citation
  ├─ assign(answer) ────────────── prompt | model | StrOutputParser   ← streams
  └─ assign(citations) ─────────── parse [n] markers back to source metadata
```

**Design decisions I'd defend:**

- **`assign` throughout, not `parallel`** — every stage needs the original question and the
  accumulated context. A `parallel` anywhere in the middle silently drops keys and you'd get a
  missing-variable error three steps later.
- **Query rewriting first** — retrieval on a raw follow-up question ("what about the second
  one?") retrieves nothing useful. This is the highest-ROI stage in conversational RAG.
- **Hybrid retrieval in a `RunnableParallel`** — vector and BM25 are independent, so they run
  concurrently; the merge happens in a lambda afterwards.
- **Reranking as a separate stage** — retrieve 20 cheaply, rerank to 5 accurately. Keeps the
  final prompt small, which matters for both cost and the lost-in-the-middle effect.
- **Answer generation last so it streams** — everything before it is `invoke`d, then tokens flow.
  Citations are parsed from the *complete* answer, so you'd emit them after the stream ends
  rather than piping them (a post-stream lambda would block streaming).
- **Name every stage** — `rewrite_query`, `retrieve_hybrid`, `rerank`, `generate_answer`. Without
  names the trace is unreadable and you can't tell whether latency is retrieval or generation.

**Where I'd stop using LCEL:** if the design needs *corrective* RAG — grade the retrieved
documents, and if they're irrelevant, rewrite the query and retrieve again — that's a cycle.
Week 2 builds the LCEL version; Week 3 rebuilds it as a graph for exactly this reason.
</details>

---


## Week 2 — Data, Embeddings, RAG & Memory

### Day 08 — Chains: Sequential, Parallel, Router & Document Chains

*11 questions · [open the day](../week-02-data-embeddings-and-rag/day-08-chains.md)*

#### Basic

<details>
<summary><b>Q: What is a chain in LangChain?</b></summary>

A fixed sequence of steps where *you* define the control flow — typically prompt → model →
parser, or retrieve → prompt → generate. In modern LangChain a chain is just an LCEL composition
of `Runnable`s; there's no `Chain` base class you need any more. Chains are predictable in cost
and latency and easy to test, which is why you prefer them over agents whenever the process is
known in advance.
</details>

<details>
<summary><b>Q: Difference between a chain and an agent?</b></summary>

Control flow. In a chain the sequence of steps is decided by the developer and fixed at build
time. In an agent the model decides at runtime which tool to call next and when to stop, so the
number of steps is unknown in advance.

Consequences: chains have bounded cost and latency and are easy to unit-test; agents are flexible
but need step limits, error handling and monitoring. Use a chain when the process is known; use
an agent when the process depends on what you find.
</details>

<details>
<summary><b>Q: What are the document chain strategies?</b></summary>

Four ways to handle more documents than fit in the context window:

- **Stuff** — put them all in one prompt. One call, best quality, only works if it fits.
- **Map-reduce** — process each document in parallel, then combine. Fast, but each map call sees
  only one document, so cross-document reasoning suffers.
- **Refine** — build an answer iteratively, passing the running answer plus the next document.
  Preserves context but is sequential (slow) and can drift.
- **Map-rerank** — answer from each document with a self-score, return the best. Good for finding
  one fact, useless when the answer spans documents.

Default to stuff, and use retrieval to make stuffing viable.
</details>

<details>
<summary><b>Q: What replaced `LLMChain`?</b></summary>

LCEL composition: `prompt | model` (Python) or `prompt.pipe(model)` (JS). It's not a renamed
class — the insight was that a chain doesn't need a class at all, just a shared interface plus
composition. `LLMChain` and the other legacy chains now live in `@langchain/classic` /
`langchain-classic` for backwards compatibility.
</details>

#### Intermediate

<details>
<summary><b>Q: When would you use map-reduce over stuff, and what do you lose?</b></summary>

Use map-reduce when the documents genuinely don't fit *and* you need to process all of them —
summarising a whole book, auditing every record, generating a report over a corpus.

You lose cross-document reasoning: each map call sees exactly one document, so a question whose
answer requires connecting a fact on page 3 to a fact on page 60 will usually fail. You also pay
N+1 calls instead of 1.

The important follow-up: for *question answering*, map-reduce is usually the wrong tool entirely.
Retrieving the handful of relevant chunks and stuffing those is faster, cheaper and more accurate.
Map-reduce is for when you truly must touch everything.
</details>

<details>
<summary><b>Q: Why is refine slow, and when is it worth it?</b></summary>

Refine is inherently **sequential** — each call needs the previous call's answer as input, so N
documents means N serial round trips that cannot be parallelised. Map-reduce with the same N
finishes in roughly the time of two calls.

It's worth it when you need cross-document context preserved *and* can't fit everything in one
prompt — building a chronology, or a running analysis where each new document genuinely changes
the interpretation of earlier ones.

Its other failure mode is **drift**: each rewrite can degrade the answer, and later documents get
disproportionate influence. Mitigate by instructing the model to return the current answer
unchanged when new context doesn't help, and by keeping N small.
</details>

<details>
<summary><b>Q: How do you handle map-reduce when the summaries themselves overflow?</b></summary>

Reduce recursively: batch the summaries into groups that fit the context budget, reduce each
group, then reduce those results, repeating until one remains — a reduction tree.

Three implementation details matter: batch by *token budget* rather than fixed count, since item
lengths vary; give any single oversized item its own batch instead of dropping it or looping
forever; and short-circuit when everything already fits in one batch, or you burn an extra call
and degrade the summary through needless rewriting.

Filtering irrelevant map outputs before reducing is usually the biggest win — on a large corpus
most chunks contribute nothing.
</details>

<details>
<summary><b>Q: How would you route between models to control cost?</b></summary>

Classify the request with a cheap model, then dispatch to a model matched to difficulty — a small
model for lookups and classification, a large one for reasoning and generation. Most traffic is
easy, so this typically cuts spend substantially with no quality loss on the easy path.

Production details: the classifier must itself be cheap and must have a *fallback value* (not an
error) so a classifier outage degrades rather than fails; track cumulative spend and degrade
deliberately near a budget, skipping the classifier once everything is going cheap anyway; check
budget *before* the call; and log which tier each request took so you can see the distribution
shift.
</details>

#### Advanced

<details>
<summary><b>Q: Why did LangChain remove the legacy chain classes, and what's the general lesson?</b></summary>

The 0.x chains were classes that hid control flow inside a `_call()` method. Three concrete
problems followed: you couldn't see the data flow without reading LangChain's source; any
customisation required subclassing; and streaming support was inconsistent and undiscoverable.

The replacement isn't another class — it's composition over a shared interface.
`MapReduceDocumentsChain` becomes `.batch()` plus a reduce prompt, roughly a dozen readable lines
you can modify freely (adding a relevance filter between map and reduce is trivial in LCEL and
required a fork before).

The general lesson, and the part worth saying out loud: **abstractions should hide implementation,
not control flow.** Hiding *how* a model call is made across providers is valuable — that's
`BaseChatModel`, and it earns its keep. Hiding *what order your steps run in* removes the
developer's ability to reason about, debug and modify their own program. LangChain 1.x moves
consistently toward less magic in orchestration and more in integration.
</details>

<details>
<summary><b>Q: Design a system that answers questions over a 500-page technical manual, for 10,000 users a day.</b></summary>

**Don't use document chains as the primary path.** Map-reducing 500 pages per question is roughly
1,500 LLM calls per query — unaffordable and slow at 10k/day. The architecture is retrieval-first:

**Ingest (offline, once per manual version)** — load, split into ~500-token chunks with overlap,
preserving section headers in metadata; embed; store in a vector database. Run this in CI when
the manual changes, not per request. Tag by version so a bad ingest can be rolled back.

**Query path (online)** — rewrite the question using conversation history so follow-ups are
retrievable; retrieve ~20 candidates with hybrid search (vector + BM25, since manuals are full of
exact part numbers and error codes that embeddings handle poorly); rerank to the top 5; then
**stuff** those 5 into one call with citations. Two to three model calls per question, not 1,500.

**Caching** — semantic caching on the question embedding catches near-duplicate questions, which
in support traffic is a large fraction. Cache retrieval results too.

**Quality** — a golden set of question/answer pairs run in CI on every prompt, chunking or model
change. Track **retrieval recall separately from answer quality**: if the right chunk was never
retrieved, no prompt work will fix the answer, and conflating the two is the most common way RAG
debugging goes in circles.

**Where document chains still belong** — genuinely corpus-wide tasks: "summarise everything new
in version 7", "list every deprecated API". Those touch everything by definition, so map-reduce
with recursive reduction is correct. Run offline, cache the result.

**Ops** — stream answers, rate-limit per user, monitor cost per query and retrieval latency
separately, keep a cross-provider fallback.
</details>

<details>
<summary><b>Q: Your map-reduce summariser produces bland, generic summaries. Diagnose it.</b></summary>

Bland output from map-reduce is usually **compounding lossy compression**, not a bad prompt. Each
map call compresses a chunk, the reduce compresses the compressions, and specifics — numbers,
names, caveats — get smoothed away at every level. Recursive reduction makes it worse, since each
level is another lossy pass.

How I'd work through it:

1. **Inspect intermediate outputs first.** Are the *map* outputs already generic, or only the
   final? That localises the problem immediately, and people routinely skip it.
2. **If maps are generic** — the map prompt asks for a summary when it should ask for
   *extraction*. "Summarise this chunk" invites paraphrase; "extract every specific figure, name,
   date and claim relevant to X, verbatim where possible" preserves detail. Biggest single fix.
3. **If maps are good but the reduce is bland** — the reduce is over-compressing. Raise the length
   allowance and forbid generalising away a number. Consider reducing into a *structured* schema
   (Day 06) with explicit fields for figures and claims, which makes dropping them harder.
4. **Filter irrelevant chunks before reducing.** Diluting five relevant extracts with ninety-five
   "this chunk covers general background" entries pushes the model toward generic phrasing.
5. **Reconsider the strategy.** If the goal is answering a question rather than summarising
   everything, retrieval + stuff avoids the compression entirely and is both better and cheaper.
6. **Check reduction depth.** At three or four levels, raise the batch budget or use a
   larger-context model for the reduce so the tree is shallower.

The framing: every map-reduce level is a lossy compression step — minimise the number of levels,
and make each level *extract* rather than *summarise*.
</details>

---

### Day 09 — Documents, Loaders, Splitting & Chunking Strategy

*11 questions · [open the day](../week-02-data-embeddings-and-rag/day-09-documents-and-splitting.md)*

#### Basic

<details>
<summary><b>Q: What is a Document in LangChain?</b></summary>

A container with two parts: `pageContent` (JS) / `page_content` (Python), the text, and
`metadata`, an arbitrary dictionary. Only the text is embedded; metadata is what you filter,
cite and access-control by. Loaders produce Documents, splitters consume and produce them, and
retrievers return them.
</details>

<details>
<summary><b>Q: What does a text splitter do and why is it needed?</b></summary>

It breaks documents into chunks small enough to embed meaningfully and to fit in a context
window alongside a question. It's needed because loaders produce units that are the wrong size —
a PDF page is too big, a CSV row often too small — and because an embedding of a huge chunk is a
blurry average of everything in it, which retrieves poorly.
</details>

<details>
<summary><b>Q: Why is `RecursiveCharacterTextSplitter` the default recommendation?</b></summary>

It tries a list of separators from coarsest to finest — paragraphs, then lines, then sentences,
then spaces, then raw characters — and only falls back to a finer one when a piece is still too
big. So it breaks at natural boundaries whenever possible and respects `chunkSize` regardless of
the content's structure.

`CharacterTextSplitter` splits on a single separator only, so a long block without that
separator silently exceeds `chunkSize`.
</details>

<details>
<summary><b>Q: What is chunk overlap and why use it?</b></summary>

Overlap repeats some content from the end of one chunk at the start of the next, so a sentence
straddling a boundary appears complete in at least one chunk. Typical values are 10–20% of chunk
size. Zero overlap risks splitting the answer; excessive overlap bloats storage and returns
near-duplicate chunks. Zero overlap *is* correct for atomic units like CSV rows or Q&A pairs.
</details>

#### Intermediate

<details>
<summary><b>Q: How do you decide chunk size?</b></summary>

Measure it. Build ~20–30 real questions with known answers, then for several chunk sizes compute
**retrieval recall@k** — how often the chunk containing the answer appears in the top *k*.

The trade-off you're navigating: small chunks give precise, sharp embeddings but fragment
context and may split the answer; large chunks preserve context but dilute the embedding across
multiple topics and pull irrelevant text into the prompt. Recall@1 typically peaks somewhere in
the middle, and where depends on your content.

Sensible starting points: 800–1000 chars for prose, 500–800 for dense technical docs, one chunk
per Q&A pair or contract clause where the content is already atomic. But start with those and
then measure.
</details>

<details>
<summary><b>Q: Why does putting headings into chunk text improve retrieval?</b></summary>

Only `pageContent` is embedded. A chunk consisting of a table's rows under a `## Refund Policy`
heading contains no occurrence of the word "refund" once the heading has been split away, so its
embedding means something like "tabular data about durations" — and a query about refunds won't
match it.

Prepending the header breadcrumb (`Handbook > Refund Policy`) puts that topical signal into the
embedded text. It costs a handful of tokens per chunk and routinely moves recall by double digits
on structured documents. It also gives you a natural citation string.
</details>

<details>
<summary><b>Q: What's the difference between `splitText` and `splitDocuments`?</b></summary>

`splitText` takes a string and returns strings — **metadata is lost**. `splitDocuments` takes
`Document[]` and returns `Document[]` with the parent's metadata copied onto every child chunk.

Use `splitDocuments` in any real pipeline, because you need `source` and `page` for citation and
filtering. Note it doesn't add positional metadata, so enrich afterwards with `chunkIndex` — which
is what lets you later fetch neighbouring chunks.
</details>

<details>
<summary><b>Q: How would you chunk source code, and why differently from prose?</b></summary>

Use a language-aware splitter (`fromLanguage` / `from_language`) so splits prefer function and
class boundaries. A function cut in half is both unparseable and semantically meaningless — the
fragment embeds to noise.

Differences from prose: overlap is usually zero or minimal, because functions are self-contained
and duplicated code fragments confuse retrieval; chunk size can be larger, since a whole function
is the natural unit; and you want file path, language and symbol name in metadata for filtering
and citation. Ideally you'd inject the enclosing class or module name into the chunk text — the
same header-injection idea as markdown.
</details>

#### Advanced

<details>
<summary><b>Q: Your RAG system fails to find answers that are definitely in the corpus. Walk through your debugging.</b></summary>

The critical first move is **separating retrieval failure from generation failure**, because
they have completely different fixes and conflating them is why RAG debugging goes in circles.

1. **Is the answer in any chunk, intact?** Search the raw chunk text for the expected string. If
   it's not there, it's a *chunking* bug — the answer is split across a boundary — and no
   retriever improvement will ever fix it. Fix with overlap or larger chunks.
2. **If it is in a chunk, does retrieval return that chunk?** Retrieve for the question and check
   whether the known-good chunk is in the results. If not, it's a retrieval problem.
3. **If retrieval fails**, ask why the chunk's embedding doesn't match. Most often the chunk lost
   its heading, so it lacks the topical vocabulary of the question. Also check: is the query
   phrased very differently from the document (fix with query rewriting or HyDE, Day 13)? Are
   there exact identifiers like error codes that embeddings handle badly (fix with hybrid BM25)?
   Is a metadata filter wrongly excluding it?
4. **If retrieval succeeds but the answer is wrong**, it's generation — check whether the chunk
   is buried among many others (lost in the middle: retrieve fewer, or rerank), whether the
   prompt actually instructs grounding, and whether the model is overriding context with
   parametric knowledge.
5. **Then make it a regression test.** Every bug found this way becomes a case in the eval set,
   so a future "improvement" to the splitter can't silently reintroduce it.

The single highest-yield check is step 1, and it's the one most people skip.
</details>

<details>
<summary><b>Q: Design an ingestion pipeline for a company wiki with 50,000 pages that changes daily.</b></summary>

**Incremental, not full re-ingest.** Re-embedding 50k pages nightly is wasteful and slow. Hash
each chunk's content; on re-ingest, compare hashes and only embed what's new or changed, and
delete vectors for chunks that disappeared. LangChain's indexing API (record manager) does this
bookkeeping, or implement it directly against your store.

**Per-type handling.** Wikis are heterogeneous — markdown pages, attached PDFs, tables, code
snippets. Route by type to the right loader and splitter profile, with markdown header injection
so chunks carry their section breadcrumb.

**Metadata is the design centre.** Space/team, author, last-modified, ACL group, page URL,
heading breadcrumb. This drives access-control filtering (mandatory — a shared vector store
without tenant/ACL filtering is a data-leak vector), freshness filtering, and citation.

**Handle deletions and moves explicitly.** A page deleted from the wiki must have its vectors
removed, or your bot will confidently cite content that no longer exists. This is the most
commonly missed requirement.

**Pipeline shape:** a change feed or webhook from the wiki → a queue → workers that load, split,
hash, diff, embed and upsert. Batch embedding calls with a concurrency cap and retry on 429.
Make it idempotent so a replayed message doesn't duplicate.

**Versioning and rollback.** Tag each ingest run; keep the previous index queryable so a bad
splitter change can be rolled back without a full re-embed.

**Observability.** Track chunks added/updated/deleted per run, embedding cost, failure rate per
source type, and — most importantly — run the retrieval eval set after each ingest. A chunking
regression is invisible until someone complains, unless you measure it.
</details>

<details>
<summary><b>Q: When is fixed-size chunking the wrong model entirely?</b></summary>

Whenever the content has natural semantic units that don't align with a character count:

- **Q&A pairs, FAQs, support tickets** — one chunk per pair. Splitting a question from its answer
  is catastrophic; merging two pairs dilutes both.
- **Legal contracts** — one chunk per clause. Clauses are self-contained and referenced by
  number, and a clause split in half is legally meaningless.
- **Tabular data** — one chunk per row (or per row-group with the header repeated). Fixed-size
  splitting destroys rows and orphans headers.
- **Code** — one chunk per function or class.
- **Chat transcripts** — windows of turns, because a single turn is meaningless without context,
  and speaker attribution must be preserved.
- **Slide decks** — one chunk per slide.

There's also a middle path worth knowing: **semantic chunking**, which embeds sentences and
splits where consecutive-sentence similarity drops, putting boundaries at genuine topic shifts.
It's more expensive at ingest and harder to reason about, and in practice good structure-aware
splitting plus header injection gets most of the benefit for far less complexity.

The general principle: fixed-size chunking is a *fallback* for unstructured prose. If your
content has structure, use it — the structure is information the author already encoded for you,
and throwing it away to hit a character count is almost always a downgrade.
</details>

---

### Day 10 — Embeddings: Vectors, Similarity & Model Choice

*11 questions · [open the day](../week-02-data-embeddings-and-rag/day-10-embeddings.md)*

#### Basic

<details>
<summary><b>Q: What is an embedding?</b></summary>

A fixed-length list of numbers representing the meaning of a piece of text, produced by a neural
network trained so that similar meanings map to nearby vectors. Typical sizes are 384 to 3072
dimensions. It lets you compare texts by *meaning* rather than by shared characters — "money
back" matches "refund" even with zero words in common.
</details>

<details>
<summary><b>Q: What is cosine similarity?</b></summary>

The cosine of the angle between two vectors: `A·B / (|A| |B|)`. It ranges from -1 (opposite)
through 0 (unrelated) to 1 (identical direction). Because it divides by the magnitudes, it
measures *direction only* — so a long document and a short sentence about the same topic score as
similar, which is exactly what you want for text retrieval.
</details>

<details>
<summary><b>Q: Cosine vs euclidean vs dot product — when does the choice matter?</b></summary>

For **normalised** vectors (length 1), which most modern embedding models produce, cosine equals
the dot product exactly, and euclidean produces the identical *ranking* — so the choice doesn't
affect which documents you retrieve, only the numbers you see.

For **un-normalised** vectors they differ: dot product favours longer vectors, and euclidean
treats magnitude as dissimilarity, so documents get ranked partly by length. That's rarely what
you want. Vector databases typically store normalised vectors and use dot product, because it's
the cheapest operation and gives the same answer as cosine.
</details>

<details>
<summary><b>Q: Why are there separate `embedQuery` and `embedDocuments` methods?</b></summary>

Two reasons. **Batching** — `embedDocuments` sends many texts in one request, which is much
faster for ingest. And more subtly, **asymmetry**: some models are trained for query→document
retrieval and expect a prefix telling them which side they're embedding (nomic uses
`search_query:` and `search_document:`). For those models the same text produces *different*
vectors depending on the method, and using the wrong one measurably degrades retrieval.
</details>

#### Intermediate

<details>
<summary><b>Q: How do you choose an embedding model?</b></summary>

In rough priority order: does it support your **language**; does it suit your **domain** (code,
legal and medical have specialised models that clearly beat general ones); what's its **context
limit** versus your chunk size; what are **cost and latency** at your volume; and only then
benchmark scores like MTEB, which are averages over tasks that may not resemble yours.

The decision is expensive to reverse — changing model means re-embedding the entire corpus — so
it's worth building a small eval set of real questions and measuring recall@k on two or three
candidates first. In practice a good free local model often matches a paid one on domain-specific
retrieval.
</details>

<details>
<summary><b>Q: Why can't you mix embedding models in one index?</b></summary>

Different models produce vectors in entirely different spaces — different dimensionality, and
even at the same dimensionality the axes mean different things. Comparing a vector from model A
to one from model B yields a number, but that number is meaningless, and nothing raises an error.

Practically: pin one model per index, record the model name in the index metadata, namespace any
embedding cache by model, and treat a model change as a full re-index. Failing to namespace the
cache is a classic way to silently corrupt an index with mixed vectors.
</details>

<details>
<summary><b>Q: Why do unrelated texts score around 0.4 rather than 0?</b></summary>

Embedding spaces are **anisotropic** — vectors don't spread evenly over the sphere but occupy a
relatively narrow cone, so any two texts share a baseline similarity.

The practical consequence is that absolute thresholds (`score > 0.8`) are model-specific and
brittle. Rank relatively and take top-k; if you need a threshold, calibrate it on your own data
and re-calibrate whenever you change models. Looking at the *gap* between the top hit and the
rest is usually more informative than the absolute score.
</details>

<details>
<summary><b>Q: Why does chunk size affect embedding quality?</b></summary>

An embedding is produced by pooling — usually averaging — the model's per-token vectors into one
vector. A large chunk covering several topics averages to something near the centroid of all of
them, which is close to nothing in particular. Small chunks produce sharper, more discriminative
vectors.

There's also a hard failure mode: if the chunk exceeds the model's context limit, most models
**silently truncate** it, so the vector represents only the first portion of the chunk with no
error raised. Always check the model's limit against your chunk size.
</details>

#### Advanced

<details>
<summary><b>Q: When do embeddings fail, and what do you do about it?</b></summary>

Several distinct failure modes, each with a different fix:

- **Exact identifiers.** `ERR_4471` and `ERR_4472` embed near-identically — the model encodes
  "an error code", not the specific string. Same for part numbers, SKUs, version strings. Fix:
  hybrid search with BM25 for lexical precision.
- **Negation and antonyms.** "The refund was approved" and "The refund was denied" are highly
  similar vectors, because they share almost all their semantics. Fix: this is genuinely hard —
  reranking with a cross-encoder helps, since it sees query and document together.
- **Numbers and comparisons.** "under £50" versus "over £50" barely differ. Fix: extract
  structured filters from the query and apply them as metadata filters (self-query retrieval,
  Day 13).
- **Domain jargon** the model never saw in training embeds as noise. Fix: a domain-specific
  model, or fine-tuning.
- **Long chunks** dilute through pooling; chunks past the context limit truncate silently.
- **Cross-lingual** retrieval fails unless the model was trained multilingually.

The general architectural answer: embeddings are one *signal*, not a complete retrieval system.
Production stacks combine vector search with keyword search and metadata filtering, then rerank —
which is exactly the progression through Days 11 and 13.
</details>

<details>
<summary><b>Q: Design the embedding layer for a system with 50M documents and 10M queries/day.</b></summary>

**Dimensions are the dominant cost lever.** 50M × 768 dims × 4 bytes ≈ 154 GB before index
overhead; at 3072 dims that's 614 GB. I'd start at 768, or use a Matryoshka-capable model and
truncate — you keep most of the quality at a fraction of the storage and get faster comparisons,
since every distance computation touches every dimension.

**Quantisation** is the next lever: int8 quantisation cuts memory ~4× with small recall loss;
binary quantisation cuts it ~32× and is often used as a fast first-pass filter, rescoring the top
candidates with full-precision vectors.

**Ingest** is a batch pipeline: content-hash and dedupe, embed in batches with bounded
concurrency and retries, cache by `model:hash` so re-runs are incremental. 50M documents is a
one-off cost you pay once and then only for deltas — so incremental ingest with deletion handling
is essential, not optional.

**Query path** is where the recurring cost lives. 10M queries/day is 10M embedding calls;
cache aggressively, because real query distributions are heavily skewed — a modest cache often
covers a large share of traffic. Normalise queries (lowercase, trim) before hashing to raise the
hit rate. Consider a small, fast model for query embedding if the model pair is trained for it.

**Serving** needs an approximate index (HNSW or IVF) — exact search over 50M vectors is
impossible at this latency. That's a recall/latency trade-off you tune deliberately, and it's
tomorrow's topic.

**Operationally**: pin the model version and record it with the index; plan for re-indexing as a
first-class migration (dual-write to a new index, shadow-read to compare, then cut over); monitor
recall against a golden set continuously, because quality drift from a changed provider model is
otherwise invisible.
</details>

<details>
<summary><b>Q: Your semantic search returns plausible-looking but wrong results. How do you debug?</b></summary>

I'd isolate the layer before changing anything, because these have completely different fixes.

1. **Is the right chunk even in the corpus, intact?** Grep the chunk texts for the expected
   answer. If it's split across a boundary, that's a chunking bug and no retrieval change fixes
   it (Day 09).
2. **Score the known-correct chunk directly** against the query. If its similarity is high but it
   ranked low, something else is scoring higher — look at what and why. If its similarity is
   genuinely low, the problem is in the embedding step.
3. **Check for a vector-space mismatch.** Was the index built with the same model *and the same
   query/document method* as the search? A cache without a model namespace, or `embedQuery` at
   ingest and `embedDocuments` at query time on an asymmetric model, both produce exactly this
   symptom — plausible but subtly wrong results.
4. **Check for silent truncation.** If chunks exceed the model's context limit, their vectors
   represent only the opening text. Long chunks that "should" match but don't are the tell.
5. **Look at what *is* winning.** Near-duplicate boilerplate crowding the top-k is common, and is
   fixed by deduplication or MMR rather than by a better model.
6. **Check the query-document phrasing gap.** If queries are terse keywords and documents are
   prose, embeddings struggle; query rewriting or HyDE helps (Day 13).
7. **Check whether it's a lexical query in disguise** — an error code, a name, a version number.
   Those need keyword search, not vectors.

The meta-point: "wrong results" is a symptom of at least five distinct causes across chunking,
embedding, indexing and querying. Bisecting layer by layer with one known-good example is far
faster than swapping models and hoping — and each bug you find should become a case in the eval
set so it can't come back.
</details>

---

### Day 11 — Vector Databases: Indexes, Filtering & Hybrid Search

*11 questions · [open the day](../week-02-data-embeddings-and-rag/day-11-vector-databases.md)*

#### Basic

<details>
<summary><b>Q: What is a vector database and why not just use an array?</b></summary>

A database optimised for approximate nearest-neighbour search over embeddings. An in-memory array
works up to a few thousand vectors, but it compares against every vector on every query (O(n)),
loses everything on restart, requires a full rebuild to add a document, and can only filter
*after* searching.

A vector database adds an ANN index for sub-linear search, persistence, incremental
insert/update/delete, metadata filtering integrated with the index, and operational concerns like
sharding, replication and concurrent access.
</details>

<details>
<summary><b>Q: What is HNSW?</b></summary>

Hierarchical Navigable Small World — the most common ANN index. It builds a layered proximity
graph: sparse upper layers with long-range links for fast coarse navigation, dense lower layers
for fine-grained search. A query greedily descends from the top, then does a best-first search at
the bottom layer.

That gives roughly O(log n) search instead of O(n). Key parameters: `M` (edges per node, affects
recall and memory), `efConstruction` (build-time quality), and `ef` (search-time
recall/latency dial, which must be ≥ `k`).
</details>

<details>
<summary><b>Q: What does "approximate" mean here, and is it acceptable?</b></summary>

The index may miss some true nearest neighbours — typical recall is 95–99% rather than 100% —
because the greedy graph traversal can settle in a region that doesn't contain the true best
match.

For retrieval this is almost always fine: if the 5th-best chunk is returned instead of the
4th-best, the generated answer is unchanged, and you're usually retrieving several chunks and
reranking anyway. It matters much more for exact-match tasks like deduplication or plagiarism
detection, where you'd use exact search or a higher `ef`.
</details>

<details>
<summary><b>Q: What is hybrid search?</b></summary>

Combining semantic vector search with lexical keyword search (usually BM25) and fusing the two
rankings. Vectors capture meaning — "money back" matches "refund" — while keywords capture exact
strings that embeddings blur together, like error codes, SKUs, names and version numbers.

Fusion is normally Reciprocal Rank Fusion: sum `1/(k + rank)` across both lists. It uses only
ranks, so it sidesteps the problem that cosine scores and BM25 scores are on incomparable scales.
</details>

#### Intermediate

<details>
<summary><b>Q: Pre-filtering vs post-filtering — why does it matter?</b></summary>

Post-filtering runs the ANN search first and then discards results that fail the metadata filter,
so you get **fewer results than you asked for** — and the more selective the filter, the worse it
gets. A filter matching 2% of documents can return zero results from a top-10 search, because the
other 98% crowd out everything relevant.

Pre-filtering restricts the search to matching vectors from the start, so `k=10` returns 10
matching results.

It's genuinely hard to implement, because removing nodes from an HNSW graph can disconnect the
paths the search navigates. Qdrant adds extra links and falls back to brute force when filters
are very selective; pgvector can use a B-tree on the metadata column first. If your store
post-filters, either over-fetch by roughly `1/selectivity` or partition into separate collections.
</details>

<details>
<summary><b>Q: How do you choose a vector database?</b></summary>

Start with what you already run. **If you have Postgres and under a million or so vectors,
pgvector is usually the right answer** — one database, transactional consistency with your
relational data, real SQL filtering and joins against users and permissions. Teams frequently add
a dedicated vector service they didn't need.

Beyond that: Chroma for local development (zero setup, persists to disk); Qdrant for self-hosted
production (excellent filtering and performance); Pinecone if you want zero operations; Weaviate
if you want native hybrid search.

The decision criteria that actually matter: does it pre-filter properly, what's the operational
burden, does it support the scale and write rate you need, and can you do incremental
upserts and deletes.
</details>

<details>
<summary><b>Q: Why RRF rather than averaging the scores?</b></summary>

Cosine similarity and BM25 are on incomparable scales — cosine is bounded 0–1 and clusters
around 0.4–0.9 because embedding spaces are anisotropic, while BM25 is unbounded and depends on
corpus statistics and query length. Averaging them requires a normalisation, and every
normalisation choice (min-max over the result set, z-score, global scaling) introduces
assumptions that break on some queries.

RRF fuses **ranks**, which are scale-free, so no normalisation is needed. The constant `k` (≈60)
also damps the influence of the very top ranks, so a document ranked #1 by one retriever and #50
by the other doesn't automatically dominate. It's simple, has no tuning to speak of, and is
consistently hard to beat.
</details>

<details>
<summary><b>Q: How do you handle multi-tenancy in a vector store?</b></summary>

Prefer **partitioning over filtering**: a separate collection or namespace per tenant makes
cross-tenant leakage structurally impossible rather than dependent on every query constructing
its filter correctly. It also keeps each index smaller and faster.

The trade-off is per-collection overhead, which becomes a problem with very many small tenants —
at that point you use metadata filtering with a store that genuinely pre-filters, and enforce the
tenant filter in a single shared data-access layer rather than at call sites.

Either way: never let the tenant scope be something an individual query author can forget.
</details>

#### Advanced

<details>
<summary><b>Q: Walk me through how you'd tune an HNSW index for a specific latency budget.</b></summary>

You can't tune what you don't measure, so the first step is a **ground-truth set**: take a
representative sample of real queries and compute exact nearest neighbours by brute force. That's
your recall denominator.

Then sweep `ef` — the runtime dial — and plot recall against p95 latency. The curve is
characteristically steep then flat: recall climbs quickly, plateaus, and beyond the knee you're
paying latency for nothing. Pick the smallest `ef` that meets your recall target within the
latency budget. `ef` must be at least `k`, and `2×k` is a reasonable floor.

If the knee doesn't fit the budget, the build-time parameters come next. Raising `M` improves
recall at the cost of memory (it's edges per node, so memory scales with it) and slightly slower
builds. Raising `efConstruction` improves index quality for a one-off build-time cost and no
query-time cost — usually the first thing to increase if you have build time to spare.

If it still doesn't fit: reduce dimensionality (a Matryoshka model truncated to fewer dimensions,
since every distance computation touches every dimension), or quantise — int8 for ~4× memory
reduction with modest recall loss, or binary quantisation as a fast first pass with full-precision
rescoring of the top candidates.

Two things people miss: recall must be measured **with your filters applied**, because filtered
search behaves very differently; and it must be re-measured after significant data growth, since
the graph's characteristics shift.
</details>

<details>
<summary><b>Q: Design the retrieval layer for a multi-tenant SaaS with 5,000 customers, some with 10 documents and some with 500,000.</b></summary>

The skew is the whole problem — a design that suits either extreme is wrong for the other.

**Tiered storage.** Small tenants get shared collections with enforced metadata filtering; the
per-collection overhead of 5,000 tiny indexes would dominate. Large tenants get dedicated
collections, or dedicated shards, giving isolation and predictable performance. A tenant migrates
tiers as it grows, so that migration path has to exist from day one.

**Enforce the tenant scope in one place.** A single data-access layer that takes tenant from the
authenticated session and injects it — never a filter that individual call sites can forget. For
shared collections, verify the store genuinely pre-filters, or you'll starve small tenants'
results exactly as in Exercise 2.

**Per-tenant configuration**, because one setting won't fit both ends: `ef`, `k`, and even chunk
size and embedding model can reasonably differ. Store this as tenant config, not code.

**Ingest** is a queue with per-tenant rate limiting so one customer's bulk upload can't starve
everyone else. Content-hash upserts for idempotency, and deletion handling as a first-class
operation.

**Noisy-neighbour control**: per-tenant quotas on query rate and corpus size, and monitoring of
p95 latency *segmented by tenant tier* — a global p95 hides the fact that your largest customer
is timing out.

**Cost attribution.** Track embedding and storage cost per tenant; with a 50,000× size range
between customers, flat pricing is a loss-maker on the large end.

**Operationally**: re-indexing must be online (dual-write to a new index, shadow-read, compare,
cut over), because with 5,000 tenants you cannot take a maintenance window, and an embedding
model upgrade will eventually be necessary.
</details>

<details>
<summary><b>Q: Your retrieval recall is 60%. Walk through improving it.</b></summary>

First, **define which recall**, because two different numbers get conflated. Retrieval recall
(did the correct chunk appear in top-k?) is an application-level metric. ANN recall (did the
index find the true nearest neighbours?) is an index-level metric. Fixing the wrong one wastes
weeks.

Measure ANN recall by comparing against brute-force results on a sample. If it's already 98%, the
index is fine and the problem is upstream — which is the usual case, and it means no amount of
`ef` tuning will help.

Then work up the pipeline, cheapest first:

1. **Is the answer in a chunk, intact?** If it straddles a boundary, no retriever can find it.
   Fix chunk size and overlap (Day 09). This caps your ceiling and people skip checking it.
2. **Did the chunk lose its heading?** Inject header breadcrumbs — routinely worth double-digit
   recall on structured documents, for a handful of tokens.
3. **Is the query lexical?** Error codes, names, SKUs — add hybrid search. Often the single
   biggest win, and today's `ERR_4471` demo is exactly this.
4. **Is there a phrasing gap** between terse queries and prose documents? Query rewriting,
   multi-query expansion or HyDE (Day 13).
5. **Are filters over-restricting**, or is post-filtering starving results? Check result counts
   against `k`.
6. **Are near-duplicates crowding the top-k?** Deduplicate at ingest or use MMR.
7. **Raise `k` and rerank.** Retrieving 20 and reranking to 5 usually beats retrieving 5 directly,
   and it's cheap to try.
8. **Only now**, consider a different embedding model — it's the most expensive change, since it
   means re-embedding everything, and it's rarely the binding constraint.

Throughout: every fixed case becomes a permanent test case, and recall is tracked in CI. Without
that, the next "improvement" to the splitter silently undoes the work.
</details>

---

### Day 12 — Naive RAG End-to-End (and Six Ways to Break It)

*11 questions · [open the day](../week-02-data-embeddings-and-rag/day-12-naive-rag.md)*

#### Basic

<details>
<summary><b>Q: What is RAG and why use it?</b></summary>

Retrieval-Augmented Generation: retrieve documents relevant to a question and put them in the
prompt so the model answers from real, current data rather than from its training weights.

It solves three problems: the model doesn't know your private data; its training data is stale;
and it hallucinates when asked about things it doesn't know. RAG also makes answers *verifiable*
through citations, and updating knowledge means re-ingesting a document rather than fine-tuning
a model.
</details>

<details>
<summary><b>Q: Walk through the RAG pipeline.</b></summary>

Two phases with very different cost profiles.

**Ingest (offline, per document version):** load files into Documents preserving page/section
metadata; split into chunks with overlap and injected header context; embed in batches; store in
a vector database with metadata.

**Query (online, per request):** embed the question; similarity search (optionally hybrid, with
metadata filters) for the top-k chunks; format them numbered for citation; prompt the model with
instructions to answer only from that context; return the answer with sources.

Keeping ingest separate from query is what makes it practical — you embed once and query
thousands of times.
</details>

<details>
<summary><b>Q: What is `k` and how do you choose it?</b></summary>

The number of chunks retrieved and passed to the model. Too small and the answer may not be in
context; too large and you pay more tokens, dilute the prompt with irrelevant text, and hit
"lost in the middle" where mid-context information gets less attention.

3–6 is a reasonable default for question answering. The better pattern is retrieve-then-rerank:
fetch 20 candidates cheaply, rerank them accurately, keep the top 4 — you get the recall of a
large `k` with the precision of a small one. Note `k` interacts with chunk size: your real budget
is `k × chunkSize`.
</details>

<details>
<summary><b>Q: How do you make a RAG system say "I don't know"?</b></summary>

Give it an exact phrase to output — "If the context does not contain the answer, reply exactly:
*I don't have that information in the provided documents*" — rather than a vague "say you don't
know". A concrete token sequence is far easier for the model to produce than an abstract
instruction, because it's fighting a training distribution where confident answers vastly
outnumber admissions of ignorance.

Even better, use structured output with a boolean `answerFound` field, so the model must commit
and you branch in code rather than parsing prose. Then test it explicitly with an out-of-corpus
question — it's the behaviour most likely to be silently missing.
</details>

#### Intermediate

<details>
<summary><b>Q: How do you evaluate a RAG system?</b></summary>

Measure the two halves separately, because they have different fixes and conflating them is why
RAG debugging goes in circles.

**Retrieval:** recall@k (was the chunk containing the answer retrieved?) and precision@k (how
much of what you retrieved was useful?). Build this from a set of questions with known
answer-locations.

**Generation:** faithfulness (is every claim supported by the retrieved context?), answer
relevance (does it address the question?), and citation accuracy (do the markers point at
sources that actually contain the quoted text?).

The key insight is that **retrieval recall is an upper bound on answer accuracy** — at 60%
recall, no prompt engineering gets you past 60%. So for every failure, the first diagnostic is:
was the correct chunk in the retrieved set? Not retrieved means a chunking, embedding or query
problem; retrieved but answered wrong means a prompt, ordering or model problem.
</details>

<details>
<summary><b>Q: Why does naive RAG fail on follow-up questions?</b></summary>

Because retrieval sees only the raw question. "What about Basic?" has no topical content — its
embedding is essentially noise and matches arbitrary documents. The context needed to interpret
it lives in the chat history, which the retriever never sees.

The fix is **query rewriting**: use the model plus history to turn the follow-up into a
standalone question ("How long do I have to get a refund on the Basic plan?"), then retrieve on
that. Two practical details: instruct it explicitly *not* to answer the question, or it often
will; and skip the rewrite on the first turn when there's no history, saving a call and latency.

Use a small fast model for the rewrite — it's an easy task.
</details>

<details>
<summary><b>Q: How do you make citations trustworthy?</b></summary>

Don't trust free-text `[1]` markers — they're generated tokens and can be wrong or invented.

Use structured output requiring, per claim, the source number **and the exact supporting quote
copied verbatim**. Then verify in code that the quote actually appears in that chunk. Classify
the outcome rather than using a boolean: verified (exact match), paraphrased (close — usually
fine), wrong-source (real quote, wrong number — the fact is sound), fabricated (appears nowhere —
dangerous).

That classification lets you act proportionately, and it doubles as a **runtime guardrail**: if
faithfulness is low, suppress the answer and show the retrieved documents instead. Converting a
hallucination into a degraded-but-honest response is the right trade wherever being wrong is
expensive.
</details>

<details>
<summary><b>Q: What is "lost in the middle" and how does it affect RAG?</b></summary>

Models attend more reliably to information at the start and end of a long context than to the
middle. So retrieving 20 chunks and placing the relevant one at position 11 can produce a worse
answer than retrieving 4 chunks where it sits at position 2.

Three mitigations: retrieve fewer chunks (smaller `k`); reorder so the highest-scoring chunks sit
at both ends with weaker ones in the middle (LangChain's `LongContextReorder`); and — the proper
fix — retrieve a large candidate set cheaply, rerank with a cross-encoder, and pass only the top
few. That gives you the recall of a large `k` and the precision of a small one.
</details>

#### Advanced

<details>
<summary><b>Q: Your RAG system gives wrong answers 30% of the time. Diagnose it systematically.</b></summary>

The first move is to **split retrieval failures from generation failures**, because everything
after depends on which it is. For each failing question, check whether the chunk containing the
answer was in the retrieved set. That single check partitions the 30% into two piles with
completely different fixes, and it takes minutes.

**If retrieval failed**, work up the ingest pipeline cheapest-first:
- Is the answer in any chunk *intact*, or split across a boundary? That caps your ceiling and no
  retrieval change can fix it — adjust chunk size and overlap.
- Did chunks lose their headings? Injecting header breadcrumbs is routinely worth double-digit
  recall on structured documents.
- Is the query lexical — an error code, name or identifier? Embeddings blur those; add hybrid
  search.
- Is there a phrasing gap between terse queries and prose documents? Add query rewriting or
  multi-query expansion.
- Are filters over-restricting, or is the store post-filtering and starving results?
- Are near-duplicates crowding the top-k? Deduplicate at ingest, or use MMR.

**If retrieval succeeded but the answer was wrong**:
- Was the right chunk buried mid-context? Reduce `k` or rerank.
- Is the grounding instruction present and specific? Test with an out-of-corpus question.
- Is the model overriding context with parametric knowledge? Verify citations to detect it.
- Is the context formatted so chunks are distinguishable and citable?

**Then institutionalise it.** Every diagnosed failure becomes a case in the eval set, with the
retrieval/generation label recorded, and the suite runs in CI. Without that, the next chunking
"improvement" silently reintroduces old bugs.

The mistake I'd call out explicitly: spending a week on prompt engineering when retrieval recall
is 70%. The ceiling is 70% and no prompt moves it.
</details>

<details>
<summary><b>Q: When is RAG the wrong tool?</b></summary>

- **Questions requiring aggregation over the whole corpus** — "how many contracts mention
  indemnity?", "what's the average deal size?". Retrieval returns k chunks, not a count. You need
  SQL, or an agent that queries structured data.
- **Questions needing the full document** — "summarise this contract" isn't a retrieval problem;
  you want the whole document, which is a document-chain job (Day 08).
- **Highly structured queries** — "orders over £500 from last quarter" is a database query.
  Embeddings are poor at numeric comparisons; use text-to-SQL or self-query with metadata filters.
- **When the model already knows** — general knowledge doesn't need retrieval, and retrieving
  anyway adds latency, cost and a chance of retrieving something misleading.
- **When behaviour, not knowledge, is the gap** — if you need a consistent tone, format or
  reasoning style, that's prompting or fine-tuning. RAG injects facts, not style.
- **Very small corpora** — under a few thousand tokens, just put everything in the prompt.
  Retrieval adds moving parts and a failure mode for no benefit.

The general framing: RAG solves "the model doesn't know this fact". It doesn't solve "the model
can't compute this", "the model doesn't behave this way", or "this needs all the data at once".
Knowing which problem you have is the actual skill.
</details>

<details>
<summary><b>Q: Design RAG for a legal firm: 100,000 contracts, answers must be auditable, strict access control.</b></summary>

The three constraints — auditability, access control, and the domain — drive almost every
decision.

**Access control comes first, because it's a correctness requirement, not a feature.** Matter-level
partitioning: separate collections per matter or client, not metadata filters, so cross-matter
leakage is structurally impossible rather than one bug away. Every query carries the user's
authorisation from the session, resolved in a single data-access layer that call sites can't
bypass. Log every retrieval with user, matter and documents returned.

**Chunking follows the document structure.** Contracts are clause-based: one chunk per clause,
with the clause number, section heading, contract ID and effective date in both metadata and
injected text. Fixed-size splitting would cut clauses in half, which is legally meaningless.

**Retrieval must be hybrid.** Legal queries are full of exact terms — clause numbers, defined
terms, party names, statute references — that embeddings blur together. BM25 handles those;
vectors handle "what are our termination rights". Fuse with RRF, then rerank.

**Auditability shapes generation.** Structured output with verbatim quotes per claim, verified
against the source chunk in code, and an answer that is suppressed rather than shown if
faithfulness fails. Store the full trace — question, rewritten query, retrieved chunk IDs and
versions, prompt, model version, answer, citations — immutably. "Which contract version did this
answer come from, on that date?" must be answerable.

**Versioning is non-negotiable.** Contracts get amended. Chunks carry a version and effective
date; queries default to current but can be time-scoped; superseded versions are retained, not
deleted, and clearly labelled so an answer never silently mixes versions.

**Human review by default** for anything advisory. This is a research assistant that surfaces
sources for a lawyer, not an oracle. The product framing matters as much as the architecture.

**Evaluation** uses a golden set built with the lawyers, measuring retrieval recall and citation
accuracy separately, run before every deploy. In this domain a confident wrong answer is far
worse than "I couldn't find it" — so tune toward abstention, and monitor the abstention rate as a
first-class metric.
</details>

---

### Day 13 — Advanced RAG: Reranking, HyDE, Multi-Query & Self-Correction

*11 questions · [open the day](../week-02-data-embeddings-and-rag/day-13-advanced-rag.md)*

#### Basic

<details>
<summary><b>Q: What is reranking and why does it help?</b></summary>

A two-stage retrieval pattern: use a fast bi-encoder (your vector store) to fetch a wide
candidate set — say 20 — then use a slower, more accurate cross-encoder to score and select the
best 3–5.

It helps because a bi-encoder embeds query and document *separately* and compares vectors, so it
never sees them together. A cross-encoder processes `[query, document]` as a single input with
full attention between them, judging actual relevance rather than vector proximity. It's far too
slow to run over a whole corpus and ideal over 20 candidates.

In practice it's the single highest-impact addition to a naive RAG pipeline — commonly worth
10–20 points of recall@k, with no re-indexing.
</details>

<details>
<summary><b>Q: What is MMR?</b></summary>

Maximal Marginal Relevance — retrieval that balances relevance against diversity. Each candidate
is scored as `λ · relevance − (1−λ) · max_similarity_to_already_selected`, and documents are
picked greedily.

It solves the problem where your top-5 are five paraphrases of the same sentence, wasting the
context budget on one fact. `λ` around 0.5–0.7 is the useful range. Important detail: `fetchK`
must be substantially larger than `k`, or there's nothing to diversify from and MMR is a no-op.
</details>

<details>
<summary><b>Q: What is HyDE?</b></summary>

Hypothetical Document Embeddings. Instead of embedding the user's question, you have the model
write a hypothetical *answer* — a passage in the style of your documents — and embed that for
retrieval.

It works because questions and statements occupy systematically different regions of embedding
space, so a question embedding is a poor proxy for the document you want. The hypothetical
answer's factual accuracy is irrelevant; only its vocabulary and shape matter. It's especially
effective in technical domains, and it can hurt where the model knows nothing about the subject —
so it needs measuring rather than assuming.
</details>

<details>
<summary><b>Q: What is Corrective RAG?</b></summary>

RAG with a feedback loop on retrieval quality: retrieve, grade each document for relevance, and
branch — if enough are relevant, generate; if not, rewrite the query and retrieve again; if
repeated attempts fail, fall back to another source or refuse honestly.

The essential implementation details are a hard attempt limit (a grader that never approves would
otherwise loop forever) and passing previously-tried queries into the rewriter so it must produce
something genuinely different.
</details>

#### Intermediate

<details>
<summary><b>Q: Bi-encoder vs cross-encoder — explain the trade-off.</b></summary>

A bi-encoder maps query and document to vectors *independently*, so document vectors can be
precomputed at ingest and search is a cheap vector operation — that's what scales to millions of
documents. The cost is that the model never sees the pair together, so it's judging vector
proximity rather than relevance.

A cross-encoder takes `[query, document]` as one input and runs the full transformer over both,
with attention flowing between them. Much more accurate, but nothing can be precomputed — you
pay a forward pass per pair, so it can't run over a corpus.

The production answer is to use both: bi-encoder narrows 100k → 20 cheaply, cross-encoder narrows
20 → 4 accurately. That's the retrieve-wide-rerank-narrow pattern.
</details>

<details>
<summary><b>Q: When would you use parent-document retrieval?</b></summary>

When the ideal chunk size for *retrieval* differs from the ideal size for *answering*. Small
chunks embed sharply and match precisely; large chunks carry enough context for the model to
produce a complete answer. Parent-document retrieval refuses to choose: index small children,
return their parents.

It's most valuable for technical documentation and legal text, where a retrievable phrase is
short but the answerable unit is a full paragraph or clause.

The implementation detail people miss is **deduplication** — several child hits frequently belong
to the same parent, and returning that parent multiple times wastes most of your context budget.
</details>

<details>
<summary><b>Q: How do you decide which advanced RAG techniques to adopt?</b></summary>

Measure, one at a time, against an eval set with known correct chunks — and make sure the metric
matches the technique's purpose. Recall@k is right for reranking and multi-query; it's the *wrong*
metric for MMR, which optimises diversity and will show no recall gain even when it's working.

My default ordering by return on cost: **hybrid search** first (near-free, fixes the
exact-identifier failure that embeddings can't), then **reranking** (biggest single quality gain).
Those two cover most of the gap between demo and production. Then query transforms (multi-query,
HyDE) where queries are short or vocabulary-mismatched, self-query where numeric or categorical
filters matter, and adaptive loops only where retrieval quality is genuinely inconsistent.

The prerequisite: fix chunking first. No retriever recovers an answer split across a chunk
boundary, so advanced retrieval on bad chunks is wasted effort.
</details>

<details>
<summary><b>Q: What's the difference between Corrective RAG and Self-RAG?</b></summary>

They grade different things and therefore take different actions.

**Corrective RAG** grades the *retrieved documents* before generating. If they're irrelevant it
rewrites the query and retrieves again, because the problem is upstream.

**Self-RAG** grades the *generated answer* — typically on two axes: is it grounded in the
retrieved documents, and does it actually address the question?

That two-axis split matters, because the failures imply different remedies. Ungrounded means the
model invented something while the documents may have been fine, so you **regenerate** with a
stricter prompt and the same documents. Not-useful means the documents genuinely lacked the
answer, so you **re-retrieve** with a different query. Conflating them wastes retrievals on
hallucinations and re-generates from context that was never going to work.

Both need bounded loops. In practice they compose.
</details>

#### Advanced

<details>
<summary><b>Q: Design a RAG system where retrieval quality varies a lot across query types.</b></summary>

Variable quality across query types is the case for **Adaptive RAG** — classify first, then route
to a strategy suited to the query, rather than paying for the most expensive path on every request.

**Routing tiers.** A cheap classifier decides: no retrieval (greetings, general knowledge,
arithmetic — a meaningful share of real assistant traffic, and retrieving for them adds latency
*and* can degrade the answer by injecting irrelevant context); simple retrieval for single-fact
lookups; multi-query decomposition for comparisons and multi-part questions, which naive RAG
genuinely handles badly because one embedding of "compare A with B" lands between both topics;
and metadata-filtered retrieval where the query carries numeric or categorical constraints that
embeddings cannot express.

**The router must be cheap and fail safe** — it runs on every request, so use a small model, and
give it a fallback value rather than letting a classification failure take down the system.

**Add a quality loop only where it pays.** Corrective retry for query classes you've measured as
unreliable; skip it for the reliable ones. Cheap models for graders and rewriters, the strong
model only for the final answer.

**Instrument by query class.** Track recall and answer quality *segmented by route* — a global
average hides the fact that comparisons are at 50% while lookups are at 95%. That segmentation
is what tells you which route to invest in next, and it's the thing most teams don't build.

**And be honest about the ceiling.** If some query class needs aggregation across the whole
corpus ("how many contracts mention indemnity?"), no retrieval strategy fixes it — that's a
structured-data query, and the right answer is text-to-SQL or an agent with a database tool.
</details>

<details>
<summary><b>Q: Your RAG works well on simple questions but fails on complex multi-part ones. Diagnose and fix.</b></summary>

The mechanism is usually straightforward: a multi-part question produces **one embedding that is
the average of several topics**. "Compare the refund policy with the cancellation policy" lands
between the two regions and retrieves a poor spread of both — often several chunks about one and
none about the other. It's the same pooling-dilution effect as an oversized chunk, but on the
query side.

**First, confirm that's actually the failure** by checking whether the required chunks for each
sub-part were retrieved at all. If they weren't, it's retrieval; if they were and the answer
still missed a part, it's generation.

**If retrieval:**
- **Query decomposition** is the main fix — have the model split the question into focused
  sub-queries, retrieve for each, and merge with deduplication. This directly addresses the
  averaging problem.
- **Raise `k` and rerank**, so each sub-topic has room in the candidate set.
- **MMR** helps when one sub-topic's chunks crowd out the other's.

**If generation:**
- The relevant chunks may be buried mid-context — reduce `k` after reranking, or reorder.
- The prompt may not require completeness; asking explicitly for each part to be addressed, or
  using a structured output with a field per sub-question, forces coverage.

**For genuinely multi-hop questions** — where the second retrieval depends on the first's answer
("what's the refund window for the plan with the highest rate limit?") — decomposition isn't
enough, because you can't formulate query two until query one returns. That needs *iterative*
retrieval, which is an agent loop: retrieve, reason, retrieve again. That's the point where you
move from LCEL to LangGraph.

Finally, build a multi-part section into the eval set and track it separately. A global accuracy
number will hide this class of failure entirely.
</details>

<details>
<summary><b>Q: You've added reranking, hybrid search, multi-query and compression. Latency is 6 seconds. Fix it.</b></summary>

First, **measure per stage** rather than guessing. In my experience reranking dominates — an LLM
scoring 20 documents serially is easily 2–3 seconds on its own.

**The single biggest win: replace LLM reranking with a hosted cross-encoder.** Cohere, Voyage or
Jina rerank endpoints score 20 documents in one API call in roughly 100–200ms, versus 20
sequential LLM calls. Same quality benefit, an order of magnitude less latency and cost. This
alone often takes 6s to 2.5s.

**Then parallelise what's serial.** Multi-query retrievals are independent — fire them
concurrently. Document grading and scoring are independent — batch them. Hybrid's vector and
BM25 legs are independent. A surprising amount of RAG latency is sequential code that didn't need
to be.

**Then cut work that isn't earning its cost.** Measure each stage's contribution to recall and
drop the ones with marginal gains — compression in particular often costs more than it saves
unless your chunks are large. Multi-query may be unnecessary if reranking is already doing the
work.

**Then cache.** Query embeddings, retrieval results for repeated questions, and reranker scores
for (query, document) pairs. Real query distributions are heavily skewed, so a modest cache
covers a large share of traffic.

**Then restructure for perceived latency**, which is what users actually experience: stream the
answer, and render retrieved sources *before* generation starts. Retrieval finishes in ~200ms
while generation takes seconds — showing sources immediately makes the system feel responsive
and lets users start verifying.

**Finally, route adaptively.** Not every query needs the full pipeline. Simple lookups can skip
multi-query and compression entirely; reserve the expensive path for queries that need it.

The framing I'd give: latency optimisation here is mostly about *stage selection and
parallelism*, not micro-optimisation — and about separating true latency from perceived latency.
</details>

---

### Day 14 — Memory: Buffer, Summary, Entity & What Actually Changed

*11 questions · [open the day](../week-02-data-embeddings-and-rag/day-14-memory.md)*

#### Basic

<details>
<summary><b>Q: Do LLMs have memory?</b></summary>

No. Every API call is stateless — the model retains nothing between requests. Apparent memory is
entirely the application re-sending previous messages as part of the input.

So "memory" in an LLM framework always means a *strategy for deciding what to re-send* within a
finite context budget: everything (buffer), the recent N (window), what fits a token budget
(trim), a compressed summary, extracted facts, or retrieved relevant past turns.
</details>

<details>
<summary><b>Q: What are the main memory strategies?</b></summary>

- **Buffer** — send everything. Perfect recall, but cost is O(n²) over a conversation and it
  eventually exceeds the context window.
- **Window** — send the last N messages. Bounded cost, hard forgetting at the boundary.
- **Token buffer** — send as many recent messages as fit a token budget. Same forgetting,
  predictable cost.
- **Summary** — compress older turns into a running summary. Bounded and long-lived, but lossy.
- **Summary + buffer** — summary of old turns plus recent turns verbatim. The practical default.
- **Entity/fact memory** — extract structured facts. Tiny, persists across sessions, updatable.
- **Vector memory** — embed past turns and retrieve the relevant ones. Constant cost regardless
  of history length.

Production systems usually layer three: recent verbatim, rolling summary, and durable facts.
</details>

<details>
<summary><b>Q: What does `trimMessages` do?</b></summary>

Bounds a message list to a token budget. Key options: `strategy` (keep first or last),
`tokenCounter` (use the model's tokenizer for accuracy), `includeSystem` (never drop the system
message), and `startOn: "human"` — which ensures the trimmed history begins on a valid turn.

That last one prevents a real class of bug: trimming can otherwise leave a dangling tool message
or start on an AI turn, which some providers reject with a 400.
</details>

<details>
<summary><b>Q: Difference between memory and RAG?</b></summary>

The same retrieval mechanism over different corpora. RAG retrieves from **documents** — external
knowledge the model never saw. Memory retrieves from **conversations** — what was previously said
between this user and the system.

"What's our refund policy?" is RAG. "What did I tell you last week?" is memory. They have
different lifetimes, different privacy implications, and different failure modes, so keep them as
separate retrievers and be explicit in the prompt about which context is which.
</details>

#### Intermediate

<details>
<summary><b>Q: How has memory changed in modern LangChain?</b></summary>

The 0.x `Memory` classes — `ConversationBufferMemory` and friends — were stateful objects that
mutated themselves as a side effect of running a chain. Three problems ended that design:
**hidden state** (you couldn't see what was in the prompt without inspecting the object),
**concurrency bugs** (a module-scope memory shared across web requests interleaved different
users' conversations — a bug that shipped to production), and **no persistence** (restart the
process, lose everything).

The modern approach separates three concerns explicitly: **storage** is yours (an array, a
database row, or a LangGraph checkpointer), **injection** is `MessagesPlaceholder`, and
**bounding** is `trimMessages` or a summarisation step you write. The legacy classes moved to
`langchain-classic` for migration, and the intended production path for persistent conversational
state is LangGraph checkpointers.

It's the same design lesson as the legacy chains: abstractions should hide implementation, not
control flow or state.
</details>

<details>
<summary><b>Q: Why does summary memory degrade over long conversations?</b></summary>

Progressive summarisation is repeated lossy compression. Each fold summarises *the previous
summary* plus new turns, so a detail from turn 2 has been compressed four or five times by turn
40. Specifics erode first — numbers, names, exact decisions — leaving increasingly generic prose.
It's the same dilution as map-reduce over many levels.

Mitigations: instruct the summariser explicitly to preserve names, numbers, dates and decisions;
keep critical values in **structured fact memory** instead, where they're fields that can't be
paraphrased away; and periodically re-summarise from the original transcript if you retain it.

That's the real argument for a layered design — prose summaries for gist, structured facts for
anything that must not drift.
</details>

<details>
<summary><b>Q: How would you implement memory that persists across sessions?</b></summary>

Separate the layers by lifetime. **Within a conversation**: recent messages verbatim plus a
rolling summary, stored per session. **Across conversations**: extracted structured facts —
preferences, identity, ongoing projects — stored as a database row keyed by user, not as messages.

Implementation essentials: key everything by session/user ID with no shared mutable state (that's
the structural fix for the old concurrency bug); persist on every turn rather than on exit,
because processes crash; handle contradictions by *replacing* values rather than appending, or
you accumulate conflicting facts; timestamp facts so stale ones can decay or be re-confirmed; and
give users a way to view and delete what you remember, which is both a compliance requirement and
good product design.

In LangGraph this is a checkpointer (per-thread conversation state) plus a Store (cross-thread
long-term facts) — the same split, provided as infrastructure.
</details>

<details>
<summary><b>Q: When would you use vector memory over summarisation?</b></summary>

When history is long and users reference *specific* past exchanges rather than needing continuous
context — a support assistant where someone says "you helped me with this three months ago", or a
tutor spanning many sessions.

Vector memory has constant cost regardless of history length, and preserves exact wording rather
than a lossy paraphrase. The trade-off is that it retrieves discrete fragments, so it can miss
context that a continuous summary would carry implicitly, and it needs the same care as document
RAG — store the whole exchange rather than individual messages, since a question without its
answer retrieves poorly.

In practice they're complementary: summary for recent continuity, vector retrieval for the long
tail.
</details>

#### Advanced

<details>
<summary><b>Q: Design the memory system for a personal AI assistant used daily for years.</b></summary>

The defining constraint is that history becomes unboundedly large while relevance stays sparse —
so no single strategy works, and the design is about **lifetimes**.

**Layered by lifetime.** Working memory: the last few turns verbatim, for conversational
coherence. Episodic: per-conversation summaries, retained and retrievable. Semantic: structured
facts about the user — preferences, relationships, ongoing projects — as database fields, not
prose. Archival: full transcripts, embedded and retrievable, never replayed wholesale.

**Retrieval across episodes.** A daily-use assistant will be asked "what did we decide about X?"
where X was months ago. That's RAG over conversation history, with all of Days 10–13 applying —
including hybrid search, since users reference exact names and dates that embeddings blur.

**Fact management is the hard part**, and it's where these systems actually fail. Contradictions
must replace rather than accumulate. Facts need timestamps and decay — "currently learning
Python" is meaningless two years on. Confidence matters: hedged statements shouldn't be asserted
back as fact. And you want an audit trail, because "why do you think that about me?" is a
question users genuinely ask.

**Privacy is a first-class requirement, not a feature.** Users must be able to see everything
remembered, edit it, delete selectively, and export it. Sensitive categories may need explicit
consent or exclusion. Memory should be encrypted at rest and scoped strictly per user.

**Cost control.** Constant per-turn cost regardless of history age: bounded working memory,
retrieval instead of replay, and cheap models for extraction and summarisation with the strong
model reserved for responses.

**Failure modes to design against:** memory poisoning (a user asserting false facts that then
shape all future answers — hence confidence and provenance); drift from repeated summarisation;
and over-personalisation, where the assistant becomes so anchored on a stale profile that it
answers the profile rather than the question. That last one argues for the model deciding when
memory is relevant, rather than injecting everything into every prompt.
</details>

<details>
<summary><b>Q: Your assistant "remembers" things the user never said. Diagnose it.</b></summary>

False memories are more damaging than forgetting, because the user can't tell where they came
from — so I'd isolate the source before changing anything.

**Where it can originate:**

1. **Extraction hallucination.** The fact-extractor inferred something implied rather than stated
   — the user mentioned a Python error and it recorded "prefers Python". Check by diffing extracted
   facts against the raw messages. Fix with a confidence field, a prompt requiring facts to be
   *directly stated*, and only asserting above a threshold.

2. **Summarisation drift.** Repeated lossy compression can invent connective tissue that reads
   plausibly but wasn't in the transcript. Check by comparing the summary against the original
   messages. Fix with preservation instructions and by keeping hard facts structured.

3. **Contradiction mishandling.** Appending rather than replacing produces facts like
   "JavaScript, Python", from which the assistant infers something the user never said. Check the
   fact history.

4. **Cross-session or cross-user contamination.** Shared mutable state, a caching bug, or a
   session ID collision leaking one user's facts into another's context. This is the most serious
   possibility — it's a privacy incident, not a quality bug — so I'd check session isolation
   early even though it's less likely.

5. **The model confabulating from the prompt.** Even with correct memory, a model may embellish
   ("as you mentioned earlier…" about something never mentioned). Fix by labelling the memory
   block explicitly and instructing that it must not claim the user said anything outside it.

**Structural mitigations:** store provenance with every fact — which message and when — so
"remembered" facts are traceable and can be shown to the user; separate *stated* facts from
*inferred* ones and treat them differently; expose memory in the UI so users can correct it; and
add eval cases where the correct behaviour is learning **nothing**, since over-extraction is
rarely tested for.
</details>

<details>
<summary><b>Q: How do memory and retrieval interact, and where does that go wrong?</b></summary>

They interact in three useful ways and fail in three characteristic ones.

**Useful.** Memory *resolves* queries — "what about the other one?" is unretrievable until
history disambiguates it, which is query rewriting. Memory *enriches* queries — knowing the user
works in Python and fintech makes "how do I handle rate limits?" retrieve far better documents.
And memory *is* a retrieval corpus — past conversations, searched the same way as documents.

**Where it goes wrong.**

*Over-enrichment.* Injecting the user's whole profile into every query narrows retrieval
harmfully — a general question becomes "capital of France for Python fintech developers". The fix
is letting the model decide which facts are relevant and permitting "none", then testing that
case explicitly.

*Confusing the two corpora.* If conversation history and documents are retrieved into the same
context block undifferentiated, the model may cite something the user said as though it were
documentation. Keep them separate and label them.

*Stale memory poisoning retrieval.* A fact from a year ago silently steering every search, long
after it stopped being true. Timestamps and decay.

**The architectural point:** memory should be *available* to retrieval, not *forced into* it. The
strongest design has the model decide per query whether retrieval is needed at all, which memory
facts are relevant, and how to phrase the search — which is one classification call, and it's
exactly the adaptive routing pattern from Day 13 with memory as an extra input.
</details>

---


## Week 3 — Tools, Agents & LangGraph

### Day 15 — Tools: Creating, Calling, Schemas, Errors & Retries

*11 questions · [open the day](../week-03-tools-agents-and-langgraph/day-15-tools.md)*

#### Basic

<details>
<summary><b>Q: What is a tool in LangChain?</b></summary>

A function the model can request, wrapped with three pieces of metadata: a **name** (how the
model refers to it), a **description** (when to use it — this is prompt text), and a **schema**
(what arguments it takes). The function body itself is never seen by the model.

Created with `tool(fn, { name, description, schema })` in JS or the `@tool` decorator in Python,
where the docstring becomes the description and type hints become the schema.
</details>

<details>
<summary><b>Q: What happens when a model "calls" a tool?</b></summary>

It doesn't execute anything. The model emits a structured request — a `tool_call` with a name
and JSON arguments — and generation stops. **Your application** looks up the function, executes
it, and appends a `ToolMessage` containing the result plus the matching `tool_call_id`. Then you
call the model again with the extended history, and it either requests another tool or answers.

The key point for interviews: the model only ever *requests*. Execution, validation, error
handling and looping are all the application's responsibility.
</details>

<details>
<summary><b>Q: Why do tool descriptions matter so much?</b></summary>

Because they're the only thing the model has to decide with. The name, description and schema are
serialised into the prompt on every call; the implementation is invisible.

A description saying just `"Search"` makes the model search for everything, including arithmetic.
A good description says what the tool does, **when** to use it, and **when not to** — that last
clause is what lets the model decline. Field descriptions in the schema matter equally, since
they determine argument quality.
</details>

<details>
<summary><b>Q: What is `ToolNode`?</b></summary>

A LangGraph prebuilt that executes the tool loop's body: it takes state containing messages,
finds the `tool_calls` on the last AI message, runs them in parallel, and returns `ToolMessage`s
with matching IDs. It handles unknown tools and errors for you.

It's the ~20 lines of execution code you'd otherwise write by hand, packaged as a graph node.
</details>

#### Intermediate

<details>
<summary><b>Q: How should a tool handle errors?</b></summary>

Return the error **to the model as content**, don't throw. Throwing kills the loop and produces a
500; returning gives the model a chance to recover — try a different argument, use another tool,
or explain the limitation to the user.

The error message is effectively an instruction, so make it actionable: what went wrong, whether
it's retryable, and what to try instead. `"Error: no user with ID 5. Existing IDs: 1, 2. If you
have a name, use search_users."` produces a correct recovery; `"Error: NotFound"` produces a
give-up.

One caveat: **transient** errors (429, 503) are usually better retried inside the tool with
backoff, so the model never sees them. Only surface errors the model can act on differently —
otherwise you're using expensive round trips as a retry loop.
</details>

<details>
<summary><b>Q: How do you keep tools secure?</b></summary>

The critical framing is that **tool arguments are untrusted input**. They're generated by a model
whose context may contain user text, retrieved documents or web content — so via prompt injection,
they're effectively attacker-influenceable. You cannot prompt your way to safety.

Concretely: least privilege (read-only, tenant-scoped connections); never accept raw SQL or shell
commands as arguments — use allow-listed, parameterised operations; validate inside the tool, not
in the prompt; allow-list destinations for anything that leaves the system, like email recipients;
resolve-then-verify for filesystem paths to prevent traversal; human approval for irreversible
actions; and log every call with its arguments for the audit trail.

The mental model: treat `tool_calls` exactly as you'd treat a form submission from the public
internet.
</details>

<details>
<summary><b>Q: What happens with 30 tools bound to a model?</b></summary>

Two problems. **Cost**: every tool's name, description and JSON schema is in the prompt on every
call — 30 tools is easily 1,500–2,500 tokens of overhead per request, paid whether or not any are
used. **Accuracy**: models confuse similar tools, so selection quality degrades noticeably beyond
roughly 15.

The fix is routing: classify the request with a cheap model, then bind only that category's tools
plus a small always-available set. In practice this cuts input tokens by ~75% *and* improves
selection accuracy, because fewer options means less confusion.

The limitation to acknowledge: cross-category requests ("find my notes and email them") break a
single-label router. You either allow multi-label classification or let the agent request
additional tools mid-run.
</details>

<details>
<summary><b>Q: Can a model call multiple tools at once?</b></summary>

Yes — a single AI message can contain several `tool_calls`, and you should execute those in
parallel since the model emitted them together, meaning they're independent.

But some sequences are inherently **sequential**: "weather in Lahore in Fahrenheit" requires
`get_weather` first, because the conversion needs a temperature that doesn't exist yet. The model
requests one tool, reads the result, then requests the calculator.

This is why a step limit counts **model round trips**, not tool executions — one round trip may
execute five tools in parallel.
</details>

#### Advanced

<details>
<summary><b>Q: Design the tool layer for an agent with access to a production database.</b></summary>

I'd start from the position that the agent must not be able to express a dangerous operation at
all — not that it must be persuaded not to.

**No raw SQL.** The tool takes a query *name* from an enum plus typed parameters, and the SQL
lives in my code, parameterised. That removes SQL injection and unbounded queries in one move. If
the product genuinely needs ad-hoc querying, it goes through a generated-SQL path that is parsed,
validated against an allow-list of tables and operations, forced read-only, and run with a
statement timeout and row cap — and even then I'd want a human in the loop for anything outside
a known shape.

**Connection scoping.** A read-only replica, a role with SELECT on specific tables only, and
tenant scoping injected server-side from the authenticated session — never from a tool argument,
or the model can be talked into reading another tenant's data.

**Result bounding.** Row limits and truncation with an explicit "showing 10 of 4,382" message, so
a broad query can't blow the context window or the bill.

**Writes are a separate tier.** Different tools, human approval via an interrupt, idempotency
keys so a retry can't double-apply, and an audit log recording who approved what.

**Observability.** Every call logged with arguments, duration, row count and the originating
conversation ID. Alert on unusual patterns — a spike in queries or repeated failures often means
either a prompt regression or an injection attempt.

**Testing.** The validation layer gets unit tests including adversarial inputs, because it's the
actual security boundary and it's exactly the kind of code that silently regresses.
</details>

<details>
<summary><b>Q: Your agent keeps choosing the wrong tool. Walk through fixing it.</b></summary>

I'd treat this as a prompt-engineering problem with a measurable target, because that's what it
is — the descriptions *are* the prompt.

**First, build the eval.** A set of questions with the tool that should be selected, including
cases where the answer is *no tool*. Without this you're guessing, and tool selection is exactly
the kind of thing that regresses when someone adds a tool.

**Then look at what's actually being chosen.** The pattern usually tells you the cause:
- **Everything routes to one tool** → its description is too broad, or the others are too vague.
- **Two similar tools get confused** → their descriptions overlap. Make the boundary explicit in
  both ("use X for current data, use Y for historical").
- **It uses a tool when none is needed** → no description says when *not* to use it. Models treat
  an available tool as one they should use unless told otherwise.
- **Right tool, wrong arguments** → the schema needs work: enums instead of free strings,
  descriptions on every field, nullable for genuinely optional values.

**Then reduce the choice.** If there are more than ~15 tools, route by category first. Fewer
options measurably improves selection, independent of description quality.

**Then consider structure.** Merging near-duplicate tools into one with a mode enum often works
better than trying to describe the distinction. And a system-prompt policy ("always use the
calculator for arithmetic") reinforces per-tool descriptions.

**Finally, check the model.** Tool selection varies substantially across models; a smaller model
may simply not be capable of a 15-way choice, in which case routing isn't an optimisation, it's a
requirement.

Throughout, every fixed case goes into the eval set so it can't come back.
</details>

<details>
<summary><b>Q: When should a capability be a tool versus part of the chain?</b></summary>

The deciding question is **who chooses** — the model or you.

Make it part of the chain when the step always happens and its position is known. Retrieval in a
standard RAG pipeline is the clearest example: you always retrieve, then always generate. Putting
it in the chain is cheaper (no tool schema in the prompt, no extra round trip), more predictable,
and easier to test.

Make it a tool when the decision depends on the request. Should we search the web? Query the
database? Look at a file? If the answer varies per request and the model is best placed to judge,
it's a tool.

The interesting middle case is **retrieval as a tool** — Agentic RAG. That's the right choice when
the model should decide *whether* to retrieve (skipping it for greetings), *what* to search for
(reformulating), and *whether to search again* after seeing poor results. You're paying extra
round trips for adaptivity, which is worth it when retrieval quality is inconsistent and not
worth it when it's reliable.

The trade-off in one line: chains give you predictable cost and latency and easy testing; tools
give you adaptivity at the price of unbounded steps and harder evaluation. Default to the chain,
and promote a step to a tool when you find yourself wanting the model to make that call.
</details>

---

### Day 16 — Agents From First Principles: Build ReAct by Hand

*11 questions · [open the day](../week-03-tools-agents-and-langgraph/day-16-agents.md)*

#### Basic

<details>
<summary><b>Q: What is an agent?</b></summary>

An LLM in a loop where the **model decides the control flow**: which tool to call, with what
arguments, and when to stop. The loop is: model reasons → emits a tool call → your code executes
it → the result is appended → repeat until the model returns a final answer instead of a tool call.

That's the whole mechanism. Everything else — LangGraph, multi-agent systems, human-in-the-loop —
is structure around that loop.
</details>

<details>
<summary><b>Q: Difference between a chain and an agent?</b></summary>

Who decides the sequence. In a chain, the developer fixes the steps at build time. In an agent,
the model chooses at runtime, so the number and order of steps is unknown in advance.

Consequences: chains have predictable cost, latency and test behaviour; agents are flexible but
need step limits, guardrails and monitoring. Use a chain when the sequence is always the same;
use an agent when the next step depends on the previous result.
</details>

<details>
<summary><b>Q: What is ReAct?</b></summary>

Reason + Act — an interleaved loop of Thought → Action → Observation, repeated until the model
produces a final answer. The reasoning step matters because generated tokens are compute: writing
out what it needs before acting measurably improves tool selection and argument quality.

Originally implemented by having the model write a text trace that you parse. Modern
implementations use native tool calling, which is the same loop with structured output instead of
regex parsing.
</details>

<details>
<summary><b>Q: Why does text-based ReAct need a stop sequence?</b></summary>

The model has seen complete ReAct traces in training, so after writing an `Action:` line it will
continue by writing its own `Observation:` — with entirely fabricated data — and then reason from
it. Nothing errors, and the output looks convincing.

`stop: ["Observation:"]` forces generation to end so your code can insert the real result. Native
tool calling removes the problem structurally: the model was fine-tuned to emit an end-of-turn
token after a tool call.
</details>

#### Intermediate

<details>
<summary><b>Q: How do you stop an agent looping forever?</b></summary>

A step limit is necessary but not sufficient — it caps the damage without addressing the cause.

The most effective addition is **repeat detection**: hash `(tool_name, arguments)`, and when you
see a repeat, instead of returning the same result again, return a message saying *"you already
made this exact call and got the same result; try something different or answer with what you
have."* That single message resolves most real loops, because the model genuinely can't tell it's
repeating otherwise.

Beyond that: per-tool call caps (which catch a different pattern — the same tool called with
*varying* arguments in a hunt, which evades a signature check), a token budget, and a wall-clock
timeout checked *before* each model call rather than after.

And the prompt should say "do not repeat a failing call" explicitly.
</details>

<details>
<summary><b>Q: Why is an agent's cost super-linear in steps?</b></summary>

Every step re-sends the entire accumulated history — the original question, every AI message,
every tool result. So step 4's input includes everything from steps 1–3. Summed across steps,
total input tokens grow roughly quadratically, not linearly.

This has practical consequences: a 4-step agent typically costs 5–6× a single call rather than
4×; large tool outputs are expensive twice over, because they're re-sent in every subsequent
step; and reducing step count (by consolidating tools, or improving descriptions so the model
chooses correctly first time) saves more than it appears to.

Mitigations: trim or summarise older tool results, truncate large outputs at the tool boundary,
and treat average step count as a monitored health metric.
</details>

<details>
<summary><b>Q: What does `create_agent` / `createAgent` actually build?</b></summary>

A compiled LangGraph state graph with two nodes: an **agent** node that calls the model bound to
your tools, and a **tools** node (a `ToolNode`) that executes any requested calls. A conditional
edge after the agent node routes to `tools` if there are tool calls and to `END` otherwise, and
the tools node always loops back to the agent.

That's the hand-written loop expressed as a graph. The reason it's a graph rather than a `while`
loop is what the graph provides: checkpointing between steps, streaming of intermediate state,
interrupts before tool execution, and time travel — none of which you get for free from a loop.
</details>

<details>
<summary><b>Q: When should you NOT use an agent?</b></summary>

When the sequence is known in advance. If every request follows retrieve → prompt → generate, an
agent adds a decision step with only one possible answer — costing latency, tokens and
predictability for nothing. This is the most common architectural mistake with agents.

Also avoid them when cost or latency budgets are tight (agents multiply model calls), when you
need deterministic, testable behaviour, or when the "agent" is really just one tool call that a
chain could make unconditionally.

The useful middle ground: a chain that *contains* an agent — a fixed pipeline where one step is
adaptive. It's rarely an all-or-nothing choice for the whole application.
</details>

#### Advanced

<details>
<summary><b>Q: Your agent takes 12 steps for questions that should take 3. Diagnose it.</b></summary>

Step explosion is usually a tool-design problem wearing an agent-behaviour costume, so I'd read
traces before changing any prompt.

**Look at what the extra steps actually are:**

- **Identical repeated calls** → no repeat detection. The model can't tell it's looping. Add the
  signature check and the "you already called this" message.
- **Same tool, slightly varying arguments** → the model is hunting because results are unhelpful.
  The tool's output is the problem: it's returning "no results" for reasonable queries, or its
  output is too vague to act on. Improve what the tool returns, and make error messages
  actionable.
- **Tool A then tool B then tool A again** → the tools are too granular. If getting a customer's
  city always requires two calls, consolidate them into one tool that returns both. Each round
  trip saved removes a model call *and* all the re-sent history that comes with it.
- **Exploratory calls that don't contribute** → the description doesn't say when *not* to use the
  tool, so the model tries it speculatively.
- **The model re-deriving something it already has** → history is being trimmed too aggressively,
  or tool results are too verbose to locate. Structure tool output.

**Then check the prompt** for "answer once you have enough information" — without it, some models
keep gathering.

**Then check the model.** Step efficiency varies a lot; a smaller model may genuinely need more
steps for the same task, in which case the cost comparison isn't as favourable as the per-token
price suggests.

Throughout: instrument average steps per query segmented by question type, so you can tell
whether a change actually helped rather than relying on a few anecdotes.
</details>

<details>
<summary><b>Q: Design an agent for a customer support system with access to refunds.</b></summary>

The refund capability dominates the design — this is an agent that can move money.

**Tier the tools by blast radius.** Read-only tools (order lookup, policy search, shipping
status) run freely. Write tools that are reversible (add a note, tag a ticket) run with logging.
Irreversible tools (issue refund, cancel subscription) require **human approval via an interrupt**
— which is a hard code boundary, not a prompt instruction, because tool arguments are influenced
by untrusted user text and prompt injection is not solvable at the prompt layer.

**Constrain the refund tool itself.** It takes an order ID and a reason from an enum — not an
arbitrary amount. The amount is looked up server-side from the order. That way even a fully
compromised prompt cannot cause an arbitrary payout. Add per-agent daily limits and idempotency
keys so a retry can't double-refund.

**Ground the policy.** Refund eligibility comes from a policy document via retrieval, not from
the model's judgement, and the agent must cite the clause it relied on. That gives you an
auditable decision trail and makes policy changes a content update rather than a prompt change.

**Guardrails**: step limit, repeat detection, per-tool caps, and a check that the customer being
acted on matches the authenticated session — the agent must never be able to act on an account
the user doesn't own.

**Escalation as a first-class path.** Low confidence, an angry customer, an unusual amount, or a
policy edge case routes to a human with the full trace attached. An agent that knows when to stop
is more valuable than one that always answers.

**Observability**: log every tool call with arguments and the approving human; track the
distribution of stop reasons and approval/denial rates. A rising denial rate means the agent's
judgement is drifting and needs attention before it becomes an incident.

**Evaluation**: a golden set of tickets with expected outcomes, run before every prompt or tool
change, measuring both correctness and whether it *asked for approval when it should have*.
</details>

<details>
<summary><b>Q: How do you evaluate an agent, given the path varies between runs?</b></summary>

Non-determinism is the core difficulty: the same question can take different valid paths, so
exact-trace comparison is meaningless. I'd measure at three levels.

**Outcome level** — did it reach the right answer? This is the primary metric and it's
path-agnostic. Build a labelled set of questions with expected answers, and score with exact
match where possible, or an LLM-as-judge with a rubric where answers are free-form. Include
questions the agent *should refuse*, since over-answering is a common failure that outcome
metrics otherwise miss.

**Trajectory level** — was the path sensible? Not "did it match a reference path", but weaker,
more robust properties: did it call the necessary tools at least once; did it avoid tools it
shouldn't have used; did it stay within a step budget; did it repeat calls. These catch
regressions that outcome metrics miss — an agent taking 12 steps to reach the right answer is
degrading even though accuracy is unchanged.

**Efficiency level** — steps, tokens, latency, cost per query. Track distributions, not averages,
because tail behaviour is where agents fail.

**Practical machinery**: run each case several times and report a pass *rate* rather than a
boolean, since variance is real. Track the distribution of stop reasons (completed / step limit /
repeat / timeout) as a health signal. Log full traces so failures can be inspected rather than
guessed at.

**And the organisational part:** every production failure becomes a permanent eval case. Agent
quality regresses easily — a tool description change can shift behaviour globally — so the suite
has to run in CI on every prompt, tool or model change, or you'll rediscover the same bugs.
</details>

---

### Day 17 — LangGraph Basics: From a Loop to a Graph

*16 questions · [open the day](../week-03-tools-agents-and-langgraph/day-17-langgraph-basics.md)*

#### Basic

**Q1. What is LangGraph and how is it different from an LCEL chain?**

LangGraph models an application as a **state machine**: a shared state object, nodes that
read it and return partial updates, and edges that decide what runs next. An LCEL chain is a
**directed acyclic pipeline** — data flows forward, each step's output is the next step's
input.

The practical difference: chains can't loop, can't be paused mid-run, and can't be resumed.
Graphs can, because the state lives in an object the framework owns rather than in local
variables on a call stack. Use a chain for a fixed sequence; use a graph the moment you have
a cycle or need persistence, interruption, or per-node observability.

---

**Q2. What are the four building blocks of a LangGraph application?**

State (the shared data, defined as named channels), nodes (functions taking state and
returning a partial update), edges (which node runs next — fixed or conditional), and the
compiled graph (an executable Runnable with `invoke`/`stream`/`batch`).

---

**Q3. What does a node return?**

Only the keys it changed — a *patch*, not the full state. LangGraph merges the patch into the
state through each channel's reducer. Omitting a key means "no opinion about this key", never
"delete this key".

---

**Q4. What are `START` and `END`?**

Sentinel nodes (`__start__` and `__end__` internally). `addEdge(START, "x")` declares the
entry point — there's no implicit "first node added". Routing to `END` means that branch is
finished; the graph halts when no nodes are active. Both names are reserved.

---

**Q5. What happens if you don't add an edge from `START`?**

`compile()` throws. In JS it's an `UnreachableNodeError` saying the node isn't reachable; in
Python a `ValueError` saying the graph must have an entrypoint. Same bug, caught statically
before anything runs.

---

#### Intermediate

**Q6. What is a reducer and when do you need a custom one?**

A reducer is a function `(existing, incoming) => merged` attached to a state channel; it
decides how a node's write is combined with what's already there. The default is
last-write-wins.

You need a custom one whenever a channel should **accumulate** (a message list, a trace, a
counter) or whenever **more than one node writes it in the same superstep** — with
last-write-wins, parallel writes silently discard all but one, with no error.

```js
notes: Annotation({ reducer: (a, b) => a.concat(b), default: () => [] })
```
```python
notes: Annotated[list[str], operator.add]
```

---

**Q7. Explain supersteps. Why can't two parallel nodes see each other's output?**

LangGraph executes in rounds called supersteps (the Pregel model). Each superstep: run all
active nodes concurrently against **one shared read-only snapshot**, then apply all their
patches together through the reducers, then follow edges to compute the next active set.

Parallel nodes can't see each other because they were all handed the *same* snapshot, taken
before any of them ran. If node B needs node A's output, they must be in different
supersteps — which means an edge from A to B. This is the most common silent bug in LangGraph
code: the graph runs, produces plausible output, and B was working from stale data.

---

**Q8. How do you implement a loop, and what must every loop have?**

A conditional edge out of a node plus a plain edge back into it:

```js
.addConditionalEdges("critique", route, ["revise", END])
.addEdge("revise", "critique")
```

Every loop needs **at least two exits**: a quality condition (score ≥ 8) *and* a
budget condition (revisions ≥ 3). The quality condition may never fire. The `recursionLimit`
(default 25 supersteps) is a backstop that throws `GraphRecursionError` — treat hitting it as
a bug, not a tuning knob, because by then you've already paid for 25 supersteps.

---

**Q9. What are `MessagesAnnotation` / `MessagesState` and what's special about the reducer?**

Prebuilt state with a single `messages` channel reduced by `addMessages` / `add_messages`.
The reducer appends — but it also **upserts by message ID**: re-sending a message with an
existing ID replaces it rather than duplicating. That's what makes editing conversation
history possible (human-in-the-loop message editing on Day 21).

Extend it when you need more channels — subclass `MessagesState` in Python, or declare
`messages: Annotation({ reducer: addMessages, default: () => [] })` alongside your own
channels in JS.

---

**Q10. Walk me through `ToolNode` and `toolsCondition`.**

`ToolNode(tools)` reads the last AI message, executes every tool call in it **in parallel**,
and returns matching `ToolMessage`s with the correct `tool_call_id`. In JS it catches tool
exceptions and returns them as message *content* rather than throwing, so the model can see
the error and recover. Python's `ToolNode` does that only for invalid arguments by default;
exceptions raised inside a tool propagate unless you pass `handle_tool_errors=True` or a
message string — worth mentioning in an interview, because code ported between the two
languages breaks exactly here.

`toolsCondition` is a router with two outcomes: `"tools"` if the last message has tool calls,
`END` otherwise. Together they turn the entire ReAct loop into three lines:

```js
.addNode("tools", new ToolNode(tools))
.addConditionalEdges("agent", toolsCondition, ["tools", END])
.addEdge("tools", "agent")
```

---

**Q11. Why does a node returning an unknown key not raise an error?**

Channels are declared up front; writes to undeclared channels are dropped silently. It's a
deliberate consequence of the patch model — nodes are allowed to return extra bookkeeping
without it becoming state.

The cost is that a typo'd channel name fails silently. Verified: a node returning only
unknown keys makes `invoke` return `undefined` in JS / `None` in Python — no exception at
all. Defend with TypeScript or a Pydantic state model so the typo is caught at type-check
time.

---

#### Advanced

**Q12. You have `agent ⇄ tools` and hit `GraphRecursionError` at the default limit. Walk me through your diagnosis.**

First, don't raise the limit. The error means the model never chose to stop, which is a
control-flow or prompt problem.

1. **Look at the trace.** Stream with `streamMode: "updates"` and inspect the tool calls. In
   practice you see one of three patterns.
2. **Identical repeated calls** — same tool, same args, over and over. The model isn't
   registering that it already has the answer. Fix: repeat detection that returns a *message*
   ("you already called this and got X"), not the same result again.
3. **Tool always erroring** — the model retries forever on a failure it can't fix. Fix: after
   N failures of the same tool, stop offering it and tell the model to answer without it.
4. **Genuinely long task** — the work really does need 30 steps. Only then raise the limit,
   and add a budget node that degrades gracefully instead of throwing (Exercise 5's `giveUp`
   pattern).
5. **Structural check:** does `recursionLimit` account for the two supersteps per agent turn?
   25 supersteps is ~12 tool-using turns, which is less than people expect.

The meta-point: the recursion limit is a smoke alarm. Turning it up is unplugging the alarm.

---

**Q13. Design the state for a customer-support graph handling 10k concurrent conversations. What goes in state and what doesn't?**

**In state** (small, serialisable, needed for routing or resumption): `messages` (trimmed or
summarised), `ticketId`, `customerTier`, `escalated`, `resolutionAttempts`, `toolsUsed`.

**Not in state:** database connections, HTTP clients, model instances, the entire knowledge
base, raw file contents, secrets. Those go in **config/context** (passed per-invocation,
never persisted) or are module-level singletons.

The rule is: **state is checkpointed on every superstep.** Anything you put there is
serialised and written repeatedly. A 2MB document in state means 2MB written per node, per
turn, per conversation — at 10k conversations that's your entire I/O budget. Store the
document in a vector store and keep the *reference* in state.

The second rule is that state must be JSON-serialisable, which rules out connections and
clients regardless of size. This distinction — state vs config vs store — is exactly what
Day 18 is about.

---

**Q14. Three parallel nodes write the same channel. One throws. What happens, and how should you design for it?**

Within a superstep, an unhandled exception in one node fails the superstep — the successful
nodes' writes for that superstep are **not** committed, because the patch application is
atomic per superstep. You don't get a partial merge.

Design for it three ways:

1. **Catch inside the node** and write a sentinel: `return { notes: ["[accuracy] FAILED: " + e.message] }`.
   Now the failure is data, the graph continues, and downstream nodes can decide what to do.
2. **Node-level retry policies** for transient failures, so a flaky API doesn't kill the run.
3. **Design the reducer to tolerate gaps** — downstream code should handle two notes instead
   of three rather than assuming a fixed count.

The principle carries over from tools on Day 15: in an agentic system, **failures should
usually become data rather than exceptions**, because the model (or a later node) is often
capable of routing around them. Exceptions are for bugs; sentinels are for expected failures.

---

**Q15. When is LangGraph the wrong tool?**

- **Straight-line flows.** `prompt → model → parse` is a chain. A graph adds ceremony and
  buys nothing.
- **Single stateless calls.** Classification, extraction, a one-shot summary — just call the
  model.
- **Hard latency budgets on simple work.** The graph machinery is cheap but not free, and
  checkpointing costs a write per superstep.
- **When a plain function would do.** If the "agent" always calls tool A then tool B, that's
  two lines of code, and it's faster, cheaper and testable.

The honest framing: LangGraph earns its complexity when you need **cycles, persistence,
human-in-the-loop, or per-node observability**. If you need none of those, using it is
resume-driven development. Saying that in an interview reads as senior; enthusiastically
graphing everything reads as junior.

---

**Q16. How would you unit-test a LangGraph application?**

Three levels, cheapest first:

1. **Nodes in isolation.** A node is `(state) => patch`. Call it with a hand-built state
   object and assert on the patch. No graph, no model, no network — most of your tests live
   here.
2. **Routers in isolation.** A router is `(state) => string`. Table-test every branch:
   `route({ score: 9 })` → `END`, `route({ score: 3, revisions: 3 })` → `END`,
   `route({ score: 3, revisions: 0 })` → `"revise"`. Check the count of assertions matches the
   count of `return`s.
3. **The graph with a fake model.** Substitute an object with an `invoke` that returns
   scripted `AIMessage`s — first a tool call, then a final answer. This is exactly how the
   snippets in this chapter were verified, and it tests the *wiring* deterministically with no
   API key and no cost:

   ```js
   let turn = 0;
   const fakeModel = { invoke: async (msgs) => {
     turn++;
     return turn === 1
       ? new AIMessage({ content: "", tool_calls: [{ name: "add", args: { a: 2, b: 3 }, id: "c1" }] })
       : new AIMessage({ content: `The answer is ${msgs.at(-1).content}.` });
   }};
   ```

Add a snapshot test on `drawMermaid()` output and you'll catch accidental topology changes in
code review. Reserve real-model integration tests for a small suite you run before release.

---

### Day 18 — State & Reducers: What Goes Where

*16 questions · [open the day](../week-03-tools-agents-and-langgraph/day-18-state-and-reducers.md)*

#### Basic

**Q1. What is a reducer in LangGraph?**

A function `(existing, incoming) => merged` attached to a state channel, deciding how a
node's write combines with the current value. The default is last-write-wins. Common ones:
concat for lists, `+` for counters, `addMessages` for conversation history.

---

**Q2. What's the default reducer and when is it wrong?**

Last-write-wins. It's wrong whenever a channel should accumulate (history, traces, collected
results) and whenever **more than one node writes it in the same superstep** — parallel
writes silently discard all but one, with no error.

---

**Q3. What does `addMessages` do beyond appending?**

Three more things: it **upserts by ID** (a message with an existing ID replaces it rather
than duplicating), it **auto-assigns UUIDs** to messages that lack one, and it **handles
`RemoveMessage`** — by ID to delete one, or with `REMOVE_ALL_MESSAGES` to clear the list.
The upsert behaviour is what makes editing conversation history possible.

---

**Q4. Where do you put a database connection?**

Context — `config.configurable`. It isn't serialisable, so putting it in state crashes the
moment you add a checkpointer, and it shouldn't be persisted anyway.

---

**Q5. How do you stop a graph from returning its internal scratchpad?**

Declare an output schema. `new StateGraph({ stateSchema, input, output })` in JS,
`StateGraph(S, input_schema=I, output_schema=O)` in Python. Nodes still see the full state;
only what leaves the graph is filtered.

---

#### Intermediate

**Q6. Explain state vs memory vs context vs store vs checkpoint.**

The one they're actually asking, so answer it structurally:

- **State** — data flowing between nodes in one run, written through reducers, scoped to a
  thread, serialised on every superstep.
- **Context** (`config.configurable`) — per-invocation inputs and live handles: `user_id`,
  DB pools, API clients, `thread_id`. Never persisted.
- **Checkpoint** — a snapshot of state saved automatically after each superstep, keyed by
  `thread_id`. It's the mechanism, not a place you put things.
- **Store** — a key-value database scoped by a namespace you choose, so it crosses threads
  and users. Written explicitly with `.put()`.
- **Memory** — **not an API.** Short-term memory *is* state + a checkpointer; long-term memory
  *is* the store. The `Memory` classes from 0.x were removed.

Finish with the decision rule: not serialisable → context; needs to outlive the thread →
store; large → external storage with a reference in state; otherwise state.

---

**Q7. What properties must a reducer have, and why?**

Pure, total, non-mutating, associative.

- **Pure** — it may re-run during replay, so side effects would happen twice.
- **Total** — it must handle the default value as `existing`, since the first write always
  sees it.
- **Non-mutating** — the old value is still referenced by other nodes' snapshots and by the
  previous checkpoint; mutating it corrupts your time-travel history.
- **Associative** — parallel writes are folded pairwise in an order you don't control, so
  `(a⊕b)⊕c` must equal `a⊕(b⊕c)`.

Concat, add, max, min, set-union and object-merge are safe. Subtraction and "keep the first N"
are not.

---

**Q8. Why is "keep the last N" a safe reducer but "keep the first N" isn't?**

"Last N" is stable under regrouping — the last N of a concatenation are the same however you
parenthesise the folds. "First N" discards items early, so a different fold order discards
different items, and under fan-out the fold order is non-deterministic. General rule: a
reducer that discards from the *end being appended* is unsafe.

---

**Q9. A user says "it forgot my language preference when I started a new chat." What happened?**

The preference is in state, which is scoped to `thread_id`. A new chat means a new thread,
which starts from the channel defaults. It belongs in the **store**, namespaced by user id,
and loaded by a node at the start of each run.

The reason it survived testing is that you tested in one thread — this bug is invisible until
real users start second conversations.

---

**Q10. How do you keep conversation history from growing forever?**

A trimming node before the model, using `trimMessages` / `trim_messages` with
`strategy: "last"` and a token budget, emitting `RemoveMessage`s for everything it dropped —
`addMessages` understands removals, so deletion is just a state update. Alternatively cap
inside the reducer: `addMessages(existing, incoming).slice(-20)`.

Two details: set `startOn: "human"` so the window never begins with an orphaned tool result
(the provider rejects that with a 400), and prefer a **node** over a hidden reducer cap when
you want the trimming to be visible in your diagram and stream events.

---

**Q11. When would you use a Pydantic model as state instead of a TypedDict?**

When the graph is exposed to untrusted input and you want **runtime validation** — a
`TypedDict` annotation is erased at runtime, a Pydantic model raises `ValidationError` on bad
input. The costs: validation runs on every superstep, and the ergonomics shift (nodes receive
a model instance, so `state.n` not `state["n"]`, though `invoke` still returns a plain dict
and nodes still return dicts).

Rule of thumb: Pydantic at the edge, TypedDict inside. JS has no direct equivalent — you get
compile-time safety from `Annotation<T>()` in TypeScript and nothing at runtime.

---

#### Advanced

**Q12. Your agent works in dev, but in production state grows until checkpointing dominates latency. Diagnose it.**

The cost model is `sizeof(state) × supersteps × turns × concurrent_users` — the entire state
is serialised after every superstep. So:

1. **Measure the state size**, not the message count. Serialise a real production state and
   look at the byte count per channel.
2. **Find the blob.** It's almost always retrieved documents, a full customer record, or raw
   tool output kept "for debugging". Replace it with a reference and fetch on demand.
3. **Check for unbounded channels.** `messages` with no cap, or a `trace` that appends every
   node on every turn forever.
4. **Check for accidental duplication** — a reducer doing the concat that the node already
   did, which grows the channel quadratically.
5. **Reduce superstep count** if the graph has fat sequential chains that could be one node
   or run in parallel.
6. Only then consider infrastructure: a faster checkpointer backend, or checkpointing less
   often for low-value runs.

The framing that lands: **state is a write-amplified data structure.** Design it like a
database row you're going to `UPDATE` thousands of times, not like a scratch object.

---

**Q13. Three nodes concurrently update a shared `counters` dict. Design the reducer.**

The naive `{...existing, ...incoming}` is wrong — two nodes incrementing the same key means
one increment is lost, because each node computed its new total from the same stale snapshot.

The fix is to make nodes send **deltas** and have the reducer add:

```js
counters: Annotation({
  reducer: (existing, incoming) => {
    const out = { ...existing };
    for (const [k, delta] of Object.entries(incoming)) out[k] = (out[k] ?? 0) + delta;
    return out;
  },
  default: () => ({}),
})
// node returns { counters: { errors: 1 } }  — a DELTA, never a total
```

```python
def add_counters(existing: dict, incoming: dict) -> dict:
    out = dict(existing)
    for k, delta in incoming.items():
        out[k] = out.get(k, 0) + delta
    return out
```

This is associative and commutative, so it's correct under any fold order. The general
principle — and the reason it's a good interview question — is that **it's the same problem
as a CRDT**: when concurrent writers can't see each other, you must send operations, not
resulting values.

---

**Q14. Design the memory architecture for a tutoring app: 50k students, months-long relationships, multi-turn sessions.**

Four layers, each with a different lifetime:

```
   1. WORKING (state, this run)
      messages capped to ~20 turns or a token budget, current topic, current problem

   2. SESSION (checkpointer, keyed by thread_id)
      the full transcript of one tutoring session — resumable, replayable, time-travellable
      TTL: keep hot for ~30 days, then archive

   3. PROFILE (store, namespaced ("students", id))
      level, language, goals, learning-style notes, mastered/struggling topics
      written by an extraction step, MERGED not overwritten

   4. CONTENT (vector store + relational DB)
      curriculum, past submissions, grades. Never in state — nodes query it and keep
      only the retrieved snippets for the current turn.
```

The decisions worth defending:

- **Session summaries flow 2→3.** At session end, a summarisation job writes durable
  conclusions ("struggles with recursion base cases") into the profile. Don't do this
  per-turn — it's expensive and noisy.
- **The profile is merged, never replaced.** A single bad extraction shouldn't erase months
  of accumulated understanding. Write patches, and keep a `notes` list that appends rather
  than overwrites.
- **State holds pointers.** `currentProblemId`, not the problem text. At 50k students the
  difference is gigabytes of checkpoint I/O.
- **Extraction is off the request path.** A background job after the session, not a node on
  every turn — otherwise you pay an extra model call per message for information that changes
  once a week.
- **The store is namespaced per student**, which also gives you a clean GDPR deletion story:
  drop the namespace, drop the threads.

---

**Q15. When would you use multiple state schemas, beyond hiding fields?**

Four cases:

1. **Security boundary** — the output schema keeps retrieved documents, raw prompts, and
   inferred user facts out of HTTP responses by construction rather than by remembering to
   filter.
2. **API stability** — the input schema is your public contract. Internal state can be
   refactored freely without breaking callers.
3. **Subgraphs** (Day 19) — a subgraph has its own state; input/output schemas define exactly
   what crosses the boundary, so a subgraph is genuinely encapsulated rather than sharing one
   global bag of fields.
4. **Private node-to-node channels** — a field that two adjacent nodes use to pass working
   data, declared in the internal schema only, so it never appears in input or output and
   nobody outside those two nodes depends on it.

The theme: schemas turn your state from one shared global into something with **interfaces**.
That matters at exactly the point a graph gets big enough for more than one person to work
on it.

---

**Q16. How do you test state and reducer logic?**

In three layers, cheapest first:

1. **Reducers alone.** Pure two-argument functions. Assert totality (handles the default),
   non-mutation (the input is unchanged afterwards), and associativity
   (`f(f(a,b),c) === f(a,f(b,c))`). No graph, no model, no network — this catches the entire
   class of concurrency bugs that are otherwise unreproducible.
2. **Nodes alone.** `(state) => patch`. Hand-build a state object, call the node, assert on
   the patch. Assert it returns *only* the keys it should.
3. **The graph with a fake model** and a real `InMemoryStore`, asserting on cross-thread
   behaviour: run thread A, then thread B, and check that profile facts carried over while
   conversation history did not.

Add one schema test that asserts `invoke` returns exactly the output-schema keys — that's
your regression test against accidentally leaking internal fields when someone adds a channel
six months from now.

---

### Day 19 — Control Flow: `Command`, `Send` & Subgraphs

*16 questions · [open the day](../week-03-tools-agents-and-langgraph/day-19-control-flow.md)*

#### Basic

**Q1. What is `Command` in LangGraph?**

A return value that carries both a state update and a routing decision:
`Command({ update: {...}, goto: "nodeName" })`. It lets one node do the work *and* say where
to go next, instead of returning state and having a separate router re-derive the decision.

---

**Q2. What is `Send` and what problem does it solve?**

`Send("nodeName", payload)` creates one invocation of a node with `payload` as that
invocation's entire state. Returned as a list from a conditional edge, it fans out to N
concurrent copies — where **N is decided at runtime**. It solves map-reduce: conditional edges
route to nodes by name, and you can't name nodes you don't know you'll need.

---

**Q3. What does a `Send` worker see?**

Only its payload. It does **not** inherit the parent's channels. Anything the worker needs
must be in the payload explicitly. This is the property that makes workers isolated and
testable as plain functions.

---

**Q4. What is a subgraph?**

A compiled graph used as a node in another graph — `addNode("sub", compiledGraph)`. It has
its own state, its own diagram, and its own tests. Same idea as a function call: encapsulate
steps the caller doesn't need to know about.

---

**Q5. How do you declare where a `Command` can route to?**

JS: `.addNode("n", fn, { ends: ["a", "b"] })`. Python: annotate the return type as
`Command[Literal["a", "b"]]`, or pass `destinations=("a","b")`. Without it, `compile()` fails
with an unreachable-node error, because the builder can't read inside a function body.

---

#### Intermediate

**Q6. `Send` vs a `for` loop inside a node — when does each win?**

`Send` gives you: real parallelism (wall-clock = slowest item, not the sum), visibility in
the diagram, per-item retry policies, per-item stream events, per-item failure isolation, and
interruptibility between items.

A loop wins when items are cheap and fast (no network), when N is large enough that N
concurrent calls would hit rate limits, or when items must be processed in order. In practice
a hybrid is common: `Send` batches of 10 and loop inside the worker, capping concurrency at
20 instead of 200.

---

**Q7. Three `Send` workers write `results`. What must be true, and what if it isn't?**

`results` must have a **combining reducer** (concat). Without one it's last-write-wins and
two of the three results are silently discarded — no error, and the output still looks
plausible. It's also non-deterministic which one survives, since fold order isn't specified.

Corollary: never rely on arrival order either. Carry an index in each payload and sort in the
merge node.

---

**Q8. Explain the subgraph state-sharing trap.**

A subgraph node receives the parent's state filtered to **shared channel names**, and returns
its **entire final state** as a patch to the parent. With an overwrite channel that's
harmless. With an appending channel, everything the subgraph inherited gets folded in a
second time:

```
parent ["before"] → subgraph returns ["before","inner"] → parent ["before","before","inner"]
```

Verified in both languages. Inside a loop it compounds per iteration, which can blow a
context window in three passes — and the resulting error is a provider token-limit rejection
that points nowhere near the cause.

The fix is a wrapper node: a plain function that invokes the subgraph with an explicit input
and returns an explicit output. Renaming channels also works but is fragile.

---

**Q9. When do you use `Command` over a conditional edge?**

When the routing decision requires work the node already did — a model call, an expensive
parse. Re-deriving it in a router means either doing the work twice or expressing the same
decision in two places.

Use a conditional edge when the router is a cheap pure function of state, because then it's
independently table-testable with no mocks. The trade-off is real: `Command` couples the
decision to the node's I/O.

---

**Q10. What happens if a fan-out returns an empty list of `Send`s?**

No nodes are activated by that branch. If nothing else is active, the graph halts — silently,
with downstream channels never written and no error. Always handle the zero case by returning
a node name instead (usually the join/merge node).

---

**Q11. How do you debug a graph with nested subgraphs?**

Two tools. `getGraphAsync({ xray: true })` / `get_graph(xray=True)` renders nested `subgraph`
blocks in the mermaid output, so you see the whole system rather than one opaque box.
And streaming with `subgraphs: true` yields `[namespacePath, update]` pairs, so you see which
subgraph instance emitted each update.

The second one is also how you catch the duplication bug: if the subgraph node's update
contains data the parent already had, you're sharing an appending channel.

---

#### Advanced

**Q12. Design a document-processing graph for 500 PDFs with rate limits and partial failures.**

Not 500 `Send`s — that's 500 concurrent calls and 500 429s. The design:

```
   1. CHUNK      Send batches of ~10 docs → ~50 concurrent workers, each looping internally.
                 Tune the batch size to your provider's limit, not to the doc count.

   2. ISOLATE    each worker try/catches per document and returns
                 { ok: [...], failed: [{id, error}] } — failures become DATA, never exceptions.
                 One bad PDF must not fail its batch, let alone the run.

   3. ACCUMULATE both channels get append reducers. Carry a doc id in every result.

   4. TRIAGE     a gather node splits transient failures (429, timeout) from permanent ones
                 (corrupt file, unsupported format).

   5. RETRY      Send only the transient failures back, with a retry counter in the payload
                 and a cap. Permanent failures go straight to the report.

   6. REPORT     always emit a manifest: processed, failed-permanent, failed-after-retries.
                 A silent partial success is worse than a loud failure.
```

Two things I'd say unprompted: **state holds document ids, never document text** (Day 18's
cost model — 500 PDFs in state is gigabytes of checkpoint I/O), and at this scale you should
ask whether this belongs in a graph at all. 500 documents with retries and rate limits is a
job queue. A graph is right if there's genuine per-document *reasoning* and you want
interruptibility; it's the wrong tool if it's mechanical extraction.

---

**Q13. Your graph has 30 nodes and every change breaks something. Walk me through the refactor.**

The root cause is almost always one shared state object: 30 nodes × 20 channels is 600
possible interactions, so nothing is locally reasonable.

1. **Map who writes what.** Grep every node's return keys. Channels written by one node and
   read by one adjacent node are private — they should move inside a subgraph.
2. **Group by contract, not adjacency.** For each candidate group, write the one-sentence
   contract *first*: "given a draft, return an approved draft or a rejection reason." If you
   can't write it, it isn't a subgraph — it's code folding, and it'll leak state.
3. **Extract with wrapper nodes.** Never wire a compiled subgraph directly as a node: the
   wrapper is where the contract, the translation, and the error handling live, and it makes
   the duplication bug structurally impossible.
4. **Shrink the parent state** to what genuinely crosses boundaries. Everything else moves
   into the subgraph that owns it.
5. **Add parallelism where the decomposition reveals it.** Independent loads and independent
   checks usually become plain parallel edges — most of the latency win, no `Send` needed.
6. **Test bottom-up.** Each subgraph gets its own tests against its contract; the parent gets
   a test with fake subgraphs.

The measurable goal: the parent diagram should fit on one screen and read like a description
of what the system does.

---

**Q14. When is a subgraph the wrong abstraction?**

- **When it's just long.** Extracting "nodes 4-9" without a contract gives you the same
  coupling with an extra layer.
- **When it shares most of the parent's channels.** Then it isn't encapsulated; it's a
  namespace, and you've taken on the duplication risk for nothing.
- **When it's used once and is three nodes.** The indirection costs more than it saves.
- **When it needs `Command.PARENT` for normal flow.** A subgraph that names its parent's
  nodes can only ever be used in that parent — you've paid for encapsulation and given it
  back.

The test: **can you describe what goes in and what comes out, in one sentence, without
mentioning the parent?** If not, it's not a subgraph yet.

---

**Q15. How do `Send` and supersteps interact? Walk through the execution.**

The fan-out happens during the **ROUTE** phase of a superstep. The conditional edge returns
N `Send` objects, and the engine activates N invocations of the target node for the *next*
superstep. All N run concurrently in that one superstep against their own payloads — they
cannot see each other's writes, exactly like any parallel nodes.

At the end, all N patches are folded into the channels pairwise through the reducers, in an
unspecified order. Then routing runs: all N copies share the same successor, and successors
are deduplicated, so the merge node is activated **once**, not N times.

Consequences worth stating: wall-clock is the slowest copy, not the sum; the merge node sees
a fully-reduced channel; and results are unordered, so carry an index.

---

**Q16. How do you test a graph that uses all three tools?**

Four layers:

1. **Workers as plain functions.** A `Send` worker takes its payload and returns a patch —
   no graph, no mocks, no network. `research({question: "x", index: 0, topic: "t"})`.
2. **Routers as tables.** Conditional edges are pure functions of state. Assert every branch,
   including the empty-fan-out case: `fanOut({subQuestions: []})` → `"gather"`.
3. **Subgraphs against their contract.** Each compiled subgraph is a Runnable; invoke it with
   its input schema and assert on its output schema. This is where the wrapper node pays off
   — the contract is written down, so you know what to assert.
4. **The parent with fake subgraphs.** Swap the wrapper node for a stub returning canned
   output. Now you're testing wiring — routing, loops, budget exits — deterministically and
   for free.

For `Command`-returning nodes, use a fake model and assert on both halves of the return: the
`update` and the `goto`. And add one snapshot test on the xray mermaid output — it catches
accidental topology changes in code review, which is exactly when they're cheap to fix.

---

### Day 20 — Persistence & Checkpointing: Save, Resume, Rewind

*16 questions · [open the day](../week-03-tools-agents-and-langgraph/day-20-persistence-and-checkpointing.md)*

#### Basic

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

#### Intermediate

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

#### Advanced

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

### Day 21 — Human-in-the-Loop: Pause, Ask, Resume

*16 questions · [open the day](../week-03-tools-agents-and-langgraph/day-21-human-in-the-loop.md)*

#### Basic

**Q1. What is `interrupt()`?**

A function you call inside a node that pauses the graph, checkpoints the state, and returns
control to the caller with a payload for a human. When someone resumes with
`Command({ resume: value })`, the node re-executes and that `interrupt()` call returns their
value.

---

**Q2. What does `invoke` return when a graph interrupts?**

The current state plus an `__interrupt__` key: a list of `{ id, value }` — the payload you
passed and a stable id. The same information is available from `getState().tasks[].interrupts`,
which is what you'd use to build an approvals queue without running anything.

---

**Q3. How do you resume?**

`app.invoke(new Command({ resume: value }), config)` — with the **same `thread_id`**. The
value can be any serialisable thing; it's whatever `interrupt()` returns.

---

**Q4. Why does human-in-the-loop require a checkpointer?**

Because the pause has to live somewhere. `interrupt()` writes a checkpoint and returns; the
process can then exit entirely. Without persistence there's no state to come back to — you'd
have a stop, not a pause.

---

**Q5. What's the difference between `interrupt()` and `interruptBefore`?**

`interrupt()` is dynamic: called inside a node, conditional, carries a payload, resumed with
`Command({ resume })`. `interruptBefore` is static: declared at compile time, fires every
time, has no payload, resumed with `invoke(null, config)`. The first is for production
approvals; the second is a debugger's breakpoint.

---

#### Intermediate

**Q6. What happens to the node's code when you resume? Why does it matter?**

**The node re-executes from the top.** It does not continue from the `interrupt()` line — so
everything before it runs a second time. Verified: a counter incremented before the interrupt
reads 2 after one approval.

It matters because side effects double. Charge a card, send an email or insert a row before
the interrupt and you do it twice. The rules: put `interrupt()` first, keep side effects in a
downstream node, and if neither is possible, guard with a state flag.

---

**Q7. Why can't LangGraph just suspend the function?**

No mainstream runtime lets you serialise a live call stack and resume it in another process.
Closures, open sockets and module state can't be serialised. So LangGraph does the only
portable thing: re-run the function and short-circuit the interrupt that already has an
answer. That's what makes a pause survive a restart, a redeploy, and a different machine —
and it's the source of the re-execution constraint.

---

**Q8. How do you implement "edit the agent's tool call before it runs"?**

Put a `review` node between the agent and the tool node. It interrupts with the pending tool
calls. On an edit, return a new `AIMessage` **with the same `id`** and corrected `args` —
`addMessages` upserts by id, so it replaces the original rather than appending. The tool node
then executes the corrected call, and the model's next turn sees only the edited version.

---

**Q9. What must you do when rejecting a tool call?**

Return a `ToolMessage` for **every** pending tool call, with matching `tool_call_id`s, whose
content explains the rejection. An unanswered tool call makes the conversation invalid and the
provider returns a 400 on the next turn — with an error that says nothing about approvals, so
it costs you an hour.

Good practice: make the rejection message actionable, e.g. "rejected: wrong date range. Do
not retry; explain what you'd need instead." The model handles that gracefully.

---

**Q10. Two nodes interrupt in the same superstep. How do you resume?**

`__interrupt__` contains two entries with distinct ids. A bare resume value raises
`RuntimeError: When there are multiple pending interrupts, you must specify the interrupt id
when resuming.` Resume with a map: `Command({ resume: { [idA]: valueA, [idB]: valueB } })`.

You can also answer one at a time — supply a map with a single id and the graph pauses again
for the rest, which is exactly the shape of a multi-approver workflow.

---

**Q11. How do you build an approvals inbox?**

For each open thread, `getState(config)` and check `snapshot.tasks` for interrupts. **It's a
pure read — never invoke the graph to find out whether it's waiting**, or rendering the page
could re-execute nodes.

Two things production needs: the interrupt **id** shown to the operator and re-checked on
submit (otherwise a stale tab approves a different request than it displayed), and a stuck-
thread alert, since a thread waiting on a human waits forever by default.

---

#### Advanced

**Q12. Design an approval system for an agent that can issue refunds.**

```
   WHAT'S GATED     amount > threshold, or the customer is flagged, or it's a repeat
                    refund. NOT every refund — approval fatigue makes gates worthless.

   THE GATE NODE    interrupt FIRST; nothing irreversible before it. It does nothing
                    but ask and interpret. The refund call lives in the next node.

   THE PAYLOAD      the amount, the reason, the order, the customer's refund history,
                    and the agent's justification. A reviewer who has to go look things
                    up in another tab will start rubber-stamping.

   THE DECISION     approve / edit-amount / reject-with-reason. Reject must produce a
                    ToolMessage so the conversation stays valid.

   IDENTITY         record WHO approved, in an append-only audit table — not in state.
                    "The system approved it" is not an answer in a dispute.

   STALENESS        compare the interrupt id the approver saw with the pending one;
                    409 on mismatch.

   TIMEOUT          a thread waiting on a human waits forever. A sweeper job resumes
                    stale threads with a rejection after N hours, and tells the customer.

   IDEMPOTENCY      the refund call itself carries an idempotency key, because
                    at-least-once delivery is the only guarantee any of this gives you.
```

The line worth saying: **the gate isn't the hard part — `interrupt()` is one line. The hard
parts are choosing what to gate, giving the reviewer enough context to decide well, and
handling the humans who never respond.**

---

**Q13. How do you test human-in-the-loop flows?**

Four layers, and the good news is that HITL is unusually easy to test because the pause is a
value:

1. **The gate node alone.** It's a function; `interrupt()` is the only thing you can't call
   directly. Test the *decision* logic by extracting it: `interpretDecision(decision, calls)`
   is pure and table-testable across approve / edit / reject.
2. **The graph, deterministically.** With a fake model, run to the interrupt, assert on
   `result.__interrupt__[0].value` — the exact payload the human would see. This is the test
   that catches "we forgot to include the SQL in the approval payload."
3. **Every resume branch.** Resume with approve, with an edit, and with a reject; assert final
   state for each. Assert the reject path produced `ToolMessage`s for every call.
4. **Re-execution safety.** The important one: put a counter in the gate node, run and resume,
   and **assert the counter is 1**. This is a regression test against someone adding a side
   effect above the interrupt six months from now, and it will eventually save you.

Add a restart test with a file-backed checkpointer: pause in one process, resume in another.

---

**Q14. What are the security considerations for HITL?**

1. **Authorisation to approve.** The resume endpoint must check that *this* user may approve
   *this* thread. Otherwise anyone with a thread id can approve destructive actions — worse
   than not having a gate, because it looks like oversight.
2. **Staleness / confused deputy.** Always compare the displayed interrupt id with the pending
   one. Without it, a stale tab approves whatever is pending now.
3. **Payload contents.** The interrupt payload goes to a human, often into a Slack message or
   an email. It's checkpointed and it leaves your system — don't put secrets or another
   tenant's data in it.
4. **Approval fatigue is a security control.** Gate too much and humans approve reflexively;
   your gate now provides false assurance. Fewer, higher-quality gates are strictly safer.
5. **Audit the decision, not just the outcome.** Who approved, when, what they saw, and
   whether they edited it. In a dispute, the payload the human was shown is the evidence.
6. **Stuck threads are a denial of service on yourself.** Thousands of never-answered pauses
   accumulate. Time them out.

---

**Q15. When is human-in-the-loop the wrong answer?**

- **When the action is cheap and reversible.** Approving something you could simply undo is
  pure latency; build undo instead.
- **When the volume makes review impossible.** 10,000 approvals a day will not be read. Use
  sampling, post-hoc review, or better constraints.
- **When a constraint would work.** "Never delete more than 100 rows" as a *tool-level*
  guard is better than asking a human every time — it's deterministic, instant and free.
  Gate what genuinely requires judgement, constrain the rest.
- **When the human has no basis to decide.** Asking "is this SQL correct?" of someone who
  can't read SQL produces a rubber stamp and the illusion of safety.

The strongest answer names the hierarchy: **constrain > gate > audit.** Make it impossible if
you can; ask a human when judgement is genuinely required; log everything either way.

---

**Q16. Compare `interrupt()` with `updateState` for injecting human input.**

`interrupt()` is **pull**: the graph reaches a point *it* decided needs a human, pauses, and
carries a payload describing the question. Resumed with `Command({ resume })`, and the node
re-executes.

`updateState` is **push**: you write into a checkpoint from outside, unprompted, then continue
with `invoke(null, config)`. No node re-runs — you wrote the result directly. It's the Day 20
time-travel mechanism.

Use `interrupt()` for designed decision points — approvals, clarification, review. Use
`updateState` for corrections after the fact, admin overrides, and debugging.

They compose: `Command({ update, resume })` does both in one call, which is what you want when
the human's decision also changes state the node will read when it re-runs.

---


## Week 4 — Multi-agent, Production & Interviews

### Day 22 — Multi-Agent Systems: Supervisors, Handoffs & When Not To

*16 questions · [open the day](../week-04-production-projects-and-interviews/day-22-multi-agent.md)*

#### Basic

**Q1. What is a multi-agent system?**

A system where more than one model-driven agent handles parts of a task, each with its own
prompt, tools and context. The point isn't the number of agents — it's that each specialist
works with a **short tool list, a single-purpose prompt and a clean context**, which a single
agent with everything loses as it grows.

---

**Q2. Name the main multi-agent architectures.**

Supervisor (a coordinator delegates to specialists and speaks to the user), handoffs/swarm
(agents transfer control and the active one speaks to the user), hierarchical (supervisors of
supervisors), and workflow graphs (the code routes; agents work inside the nodes). Plus the
baseline everyone should start from: a single agent.

---

**Q3. What is "agent-as-a-tool"?**

Wrapping a specialist agent in a tool function: the tool's arguments are the brief, the tool
calls `specialist.invoke(...)` on a fresh conversation, and returns only the final answer. The
supervisor calls it like any other tool. It's the pattern the LangChain team now recommends
for most supervisor use cases.

---

**Q4. What's a handoff?**

A tool whose result transfers control to another agent. In LangGraph it returns a
`Command({ goto: otherAgent, graph: Command.PARENT, update: {...} })` — jumping to a sibling
node in the parent graph — and records the new active agent so the next turn goes straight to
it.

---

**Q5. Why does every agent need a `name`?**

The name becomes the node name in the parent graph and the name of its handoff tool
(`transfer_to_<name>`). The supervisor and swarm libraries refuse unnamed agents.

---

#### Intermediate

**Q6. Supervisor or swarm — how do you choose?**

Ask **who should the user be talking to?** If one coordinator should always own the
conversation — combining specialists' work into one answer — use a supervisor. If the user
should be handed over and keep talking to the specialist (support triage: front desk →
billing), use handoffs.

Cost-wise, a supervisor stays in the loop on every turn; a swarm lets the active specialist
answer directly, which can be cheaper for long specialist conversations. Swarms need a
checkpointer (or you must carry `activeAgent`), or the next turn goes back to the default
agent.

---

**Q7. Why is the tool-based supervisor recommended over the supervisor library?**

Control over context. With agent-as-tool you write the boundary: the specialist sees only
the brief and the supervisor sees only the report. With the library, workers share the
parent's message history, so the worker sees the whole conversation and the supervisor
re-reads synthetic handoff messages every turn.

Measured on the same question: the worker saw 1→3 messages with agent-as-tool vs 3→5 with the
library, and the supervisor's second call saw 3 vs 6 messages. A tool is also easier to test,
time out, retry, cap and secure than a node sharing state.

---

**Q8. What does `output_mode` control in the supervisor library?**

What the worker adds to the shared history when it returns. `last_message` adds only its final
answer; `full_history` adds everything it did, including its tool calls and results. Measured:
9 vs 7 messages when the worker used one tool. Default to `last_message` — `full_history`
leaks the worker's scratch work into the supervisor's context for every later turn.

---

**Q9. How do you make specialists run in parallel?**

Have the supervisor emit multiple subagent tool calls **in one AI message** — the tool node
runs them concurrently. Measured: two 400 ms delegations completed in ~410 ms in both JS and
Python. In practice you get this by saying so in the supervisor's prompt: "delegate
independent tasks in the same step." For fixed fan-out, use `Send` in a workflow graph instead.

---

**Q10. What goes wrong with vague delegation?**

The specialist sees only the brief. "Look into what we discussed" gives it nothing: no
history, no user details, no earlier results. The fix is structural — make the tool schema
say "the specialist sees NOTHING else", provide a separate `context` argument, and pass
identifiers and numbers verbatim.

---

**Q11. How do you prevent agents handing off to each other forever?**

Non-overlapping descriptions (most ping-pong is two agents both thinking "that's not mine"), a
handoff counter in state with a cap, a prompt rule against transferring back without new
information, and the recursion limit as a backstop. Measured: two agents that always hand off
hit `GraphRecursionError` — after 37 model calls at the JS default limit — so the backstop
alone is expensive.

---

#### Advanced

**Q12. When is multi-agent worse than a single agent?**

When the task is single-hop (measured: 2 calls became 4), when the steps are fixed (that's a
workflow), when specialists need the same context anyway (you pay to copy it into briefs), and
when you can't measure the single agent's accuracy yet (you'll add complexity without knowing
whether it helped). Also when latency matters and delegations are sequential — every hop is at
least one more model round trip.

It's better when a single agent's tool list or prompt has become a source of errors, when one
job's context pollutes another's, when independent work can run in parallel, when roles want
different models, or when a dangerous capability should be isolated.

---

**Q13. How would you evaluate a multi-agent system?**

Evaluate the parts and the whole separately:

```
   1. SPECIALISTS alone     each is an agent with its own dataset — does the researcher
                            answer research briefs well? Test with fixed briefs.
   2. ROUTING               for a labelled set of requests, did the supervisor call the
                            right specialists, with self-contained briefs?
   3. END-TO-END            answer quality on real requests (Day 25's evaluators).
   4. COST & LATENCY        model calls, tokens and wall-clock per request, vs the
                            single-agent baseline. The baseline is non-negotiable.
```

Most regressions in multi-agent systems are routing or briefing failures, not specialist
failures — so layer 2 is where the leverage is. Scripted models make layers 2 and 4
deterministic in CI.

---

**Q14. Design a multi-agent customer-support system.**

```
   ENTRY        a front-desk agent with ONLY handoff tools and FAQ lookup — cheap model.
   SPECIALISTS  billing (read billing data; refunds gated by interrupt), technical
                (docs search, ticket creation), account (read-only profile).
   PATTERN      handoffs (swarm): customers should keep talking to billing once there.
   STATE        checkpointer per conversation; activeAgent persisted; messages trimmed.
   GUARDS       handoff counter (max 3), non-overlapping descriptions, a "human agent"
                handoff as the final escape.
   SECURITY     least privilege per specialist; refunds and account changes behind
                interrupt(); approval id checked on resume (Day 21).
   OBSERVE      per-agent traces, handoff counts, and a dashboard of "which agent
                resolved it" (Day 25).
```

Worth saying: I'd first check whether one agent with good tools handles 80% of tickets. If it
does, the multi-agent design is for the 20% — and maybe that 20% is just "hand off to a
human."

---

**Q15. What's context engineering, and how does multi-agent relate to it?**

Context engineering is deciding exactly what each model call sees: instructions, tools,
history, retrieved data. Most multi-agent benefits are context-engineering benefits: a
specialist gets a single-purpose prompt, a short tool list and a clean history; the
coordinator gets reports instead of raw tool noise. Seen that way, the questions become
concrete — what's in each brief, what's in each report, who sees the history — rather than
"how many agents should we have?"

---

**Q16. How do persistence and human-in-the-loop fit into a supervisor system?**

The checkpointer belongs on the top-level graph: that's the conversation. Specialists invoked
as tools are stateless workers unless you deliberately give them their own checkpointer and
thread — which is rarely needed, since anything durable should come back in the report.

Put `interrupt()` where the consequence happens — in the tool path of the specialist that
performs the action — not in a prompt asking the supervisor to "check first". And keep
dangerous tools in exactly one specialist, so the gate has one place to live.

---

### Day 23 — Streaming & Events: Make It Feel Fast

*15 questions · [open the day](../week-04-production-projects-and-interviews/day-23-streaming-and-events.md)*

#### Basic

**Q1. Why stream at all, if the total time doesn't change?**

Because users judge speed by time-to-first-feedback, not time-to-completion. Streaming
progress and tokens makes an 8-second response feel responsive, reduces abandonment and
double-submits, and shows the user the system is working on the right thing.

---

**Q2. Name LangGraph's stream modes.**

`values` (full state after each superstep), `updates` (each node's returned patch),
`messages` (LLM token chunks with metadata), `custom` (your own events), plus `debug`,
`tasks` and `checkpoints` for internals. You can request several; chunks then come tagged
with their mode.

---

**Q3. How do you get tokens out of a node that calls `model.invoke()`?**

Stream the graph with `streamMode: "messages"`. Model calls report tokens through callbacks
and LangGraph forwards them, tagged with the node that produced them — you don't need to
change `invoke` to `stream` inside the node.

---

**Q4. How do you emit custom progress events?**

JS: call `config.writer({...})` in a node or tool (it receives `config`). Python: call
`get_stream_writer()({...})` from `langgraph.config`. Stream with `custom` mode to receive
them. They're immediate and never persisted.

---

**Q5. Why SSE rather than WebSockets for streaming responses?**

The data flows one way, server to client. SSE is plain HTTP, so auth, proxies and CDNs work
normally; browsers reconnect automatically; and the format is trivial. WebSockets are for
genuinely bidirectional traffic. The one limitation — `EventSource` is GET-only with no
custom headers — is solved by reading the stream with `fetch`.

---

#### Intermediate

**Q6. Your UI shows the router's output before the answer. Fix it.**

Every model call in the graph streams in `messages` mode, not just the one producing the
answer. Tag the answering model — `model.withConfig({ tags: ["final"] })` — and forward only
chunks whose metadata tags include `"final"`. Filtering by `langgraph_node` also works but
breaks when nodes are renamed; tags state intent.

---

**Q7. How does cancellation work when a client disconnects?**

It differs by language. In JS, leaving the `for await` loop doesn't stop the graph — it runs
to completion in the background (verified). You pass an `AbortSignal` to `stream()`, which
stops the graph between supersteps, and pass `config.signal` into slow calls inside nodes so
the in-flight step stops too. In Python, closing the stream generator — a `break`, or a web
framework cancelling the response on disconnect — stops the graph before the next superstep;
the running node still finishes.

---

**Q8. How do you stream a multi-agent system where specialists run inside tools?**

In JS, a nested graph's tokens reach the parent's `messages` stream by default, so filter by
tag to keep specialists' drafts out of the user's view. In Python they don't appear unless
you stream with `subgraphs=True`, which yields `(namespace, (token, meta))` — the namespace
tells you which specialist is talking, handy for "researcher is typing…" indicators. Tag the
supervisor's model `final` either way.

---

**Q9. Why is `values` mode a poor choice for a web client?**

It sends the whole state after every superstep. With a real conversation and a multi-node
graph, that's the entire history several times per request, to deliver one new message.
`updates` sends only diffs and `messages` only tokens.

---

**Q10. Everything streams on localhost; in production it arrives all at once. Why?**

Buffering between the server and the browser — compression middleware, nginx's proxy
buffering, or a platform that doesn't support streamed responses. Disable compression for
`text/event-stream`, send `X-Accel-Buffering: no` (or turn proxy buffering off), and verify
in the browser's network tab that the body grows while the request is pending.

---

**Q11. What's `streamEvents` / `astream_events` for, now that stream modes exist?**

It's the older, lower-level event stream: every start/stream/end event for every runnable in
the run. Useful for plain LCEL chains or for events stream modes don't expose. For graphs,
stream modes are simpler, more stable, and less noisy — the exact event counts differ between
the JS and Python implementations, which tells you not to build a UI on them.

---

#### Advanced

**Q12. Design streaming for a long-running agent job (minutes) that users may leave and come back to.**

Separate starting a run from watching it. `POST /runs` validates ownership, deduplicates with
an idempotency key, starts the run in the background with a checkpointer, and returns a run
id. `GET /runs/:id/stream` streams events via SSE; a reconnect sends a "state so far" summary
from `getState` and then attaches to live events, never restarting the work. The connection
dropping stops streaming, not the run; an explicit cancel endpoint stops the work. Progress
comes from custom events emitted in long nodes, which also serve as keep-alives. Side effects
are idempotent so a retried step can't double-act. This is also the platform's run model, so
it migrates cleanly.

---

**Q13. How would you test streaming code?**

Use scripted or fake streaming models so token sequences are deterministic, and assert on
the *sequence of events*, not only the final text: the right progress events in order, only
`final`-tagged tokens forwarded, a `done` at the end, an `error` event with a generic message
on failure. Test cancellation explicitly — abort after the first chunk and assert that later
nodes did not run (and, in JS, that you passed the signal, since `break` alone won't pass
that test). Run one end-to-end test through a real HTTP server and a real stream parser, as
in §4.6, because framing bugs (a missing blank line, split multi-byte characters) only show
up there.

---

**Q14. What are the security considerations for streaming endpoints?**

The same as any endpoint, plus a few specific ones: authenticate the stream route and check
thread ownership (a stream is a read of the conversation); never forward raw exceptions,
since they end up in the browser; don't stream internal tokens (routers, graders,
specialists' drafts, tool arguments) that can reveal prompts or other data; bound
concurrency per user, because long-lived connections are a cheap way to exhaust a server; and
make sure cancellation works, since unstopped abandoned runs are a cost-exhaustion vector.

---

**Q15. How do streaming and human-in-the-loop interact?**

An interrupt ends the current stream: the run pauses, the checkpoint holds the pending
question, and the stream completes. The UI should treat that as a normal end state — show
the approval request (read it from the stream's final update or from `getState().tasks`) —
and resuming is a new request, which can itself be streamed. The design rule from Q12
applies: the pause lives in the checkpointer, not in a held-open connection, so a user can
approve from a different device an hour later.

---

### Day 24 — Reliability: Surviving a Bad Day in Production

*15 questions · [open the day](../week-04-production-projects-and-interviews/day-24-reliability.md)*

#### Basic

**Q1. When is it safe to retry an operation?**

When the failure is transient (429, 5xx, timeouts, connection resets) **and** the operation is
idempotent — doing it twice has the same effect as once. Model calls and reads are
idempotent; sending messages, charging cards and plain inserts are not, unless you add an
idempotency key.

---

**Q2. Why add jitter to backoff?**

Without it, clients that failed together retry together, hitting a recovering service with a
synchronised wave of traffic (the thundering herd). Jitter spreads retries out. Turn it off in
unit tests — in JS it added hundreds of milliseconds per retry in our measurements.

---

**Q3. What's the difference between a retry and a fallback?**

A retry repeats the same call, betting the failure was momentary. A fallback calls something
*else* — usually another provider — betting the primary is unavailable for a while. You often
use both: a couple of quick retries, then fall back.

---

**Q4. What is agent middleware in LangChain 1.x?**

Hooks that insert behaviour into the agent loop — before or after model calls, or wrapping
model and tool calls. Built-ins cover retries, fallbacks, call limits, PII handling,
summarisation, human-in-the-loop and more. You pass them as a list to `createAgent` /
`create_agent`.

---

**Q5. What does a circuit breaker do?**

It stops calling a dependency that keeps failing. After a threshold of failures it "opens"
and fails fast for a cooldown period, then lets one trial call through ("half-open"); success
closes it, failure re-opens it. It protects your workers and gives the dependency room to
recover.

---

#### Intermediate

**Q6. A Python LangGraph node with `retry_policy=RetryPolicy(max_attempts=3)` isn't retrying. Why?**

The default `retry_on` is conservative. It retries `ConnectionError` and HTTP 5xx, but returns
`False` for `ValueError`, `TypeError`, `RuntimeError`, `LookupError` and all `OSError`s — which
includes `TimeoutError`. A node raising `TimeoutError` gets one attempt. Pass an explicit
`retry_on` that names your transient errors. (JS's node retry retried a plain `Error` in our
tests, so this is a porting trap.)

---

**Q7. What happens when a tool raises inside an agent?**

It depends on the language. In JS, `ToolNode` returns the error as the tool message by
default (`"Error: …\n Please fix your mistakes."`) and the agent continues. In Python,
`ToolNode` only converts argument-validation errors; runtime exceptions — even `ToolException`
— are re-raised and crash the run, unless you set `handle_tool_errors` or catch inside the
tool. Either way, prefer returning your own message: the defaults forward raw exception text
into the model's context.

---

**Q8. What's wrong with retries at every layer?**

They multiply. With 6 client retries, 3 middleware attempts and 3 node attempts, one failing
call can become 54 attempts, stretching latency and cost and hammering a struggling provider.
Assign each failure type to one layer.

---

**Q9. What's the default failure behaviour of the model-retry middleware, and why does it matter?**

`onFailure: "continue"` — when retries run out, the error message becomes the agent's AI
reply ("Model call failed after 2 attempts with Error: 503 overloaded"). The user sees it as
the assistant's answer. Use `"error"` and render a friendly message in your application.

---

**Q10. How do you set node timeouts in Python LangGraph, and what's the catch?**

`add_node(..., timeout=seconds)`, which raises `NodeTimeoutError` when exceeded. The catch: it
only works for `async def` nodes — a sync node raises `ValueError`, because Python can't safely
cancel running synchronous code. For sync code, use client-level timeouts.

---

**Q11. How do you stop an agent from running up a huge bill?**

Layers: a model-call limit per run (and per thread), tool-call limits on expensive tools, the
recursion limit as a backstop, a token budget per request, and alerts on cost per request. Use
`exitBehavior: "end"` for interactive use so users get a graceful message. And track the
limit-exit rate: if it climbs, something upstream has changed.

---

#### Advanced

**Q12. Design the reliability strategy for an agent serving 10k users on a single provider.**

```
   CLIENT     modest retries on 429/5xx/timeouts only; request timeouts; a shared
              rate limiter sized to the account's quota
   AGENT      model fallback to a second provider (tool-compatible); model-call limits;
              per-tool retries only for idempotent tools; PII redaction
   TOOLS      circuit breakers around external services, returning guidance to the model;
              idempotency keys on every side effect
   GRAPH      node retry only on idempotent nodes, with explicit retry_on; async nodes
              with timeouts
   APP        token budgets per request; per-user concurrency caps; cancellation on
              disconnect (Day 23); dead-letter records with thread ids for replay
   OBSERVE    error rate by type, retry and fallback rates, p99 latency, cost per request,
              limit-exit rate — with alerts on fallback rate as the early outage signal
```

The principle: **one owner per failure type, and every side effect idempotent**. Then test
the whole configuration with scripted models in CI, because the defaults change between
versions and languages.

---

**Q13. How do you defend against prompt injection?**

Assume some injections will succeed and limit what they can do. Least privilege: the agent that
reads untrusted content has no dangerous tools. Constrain actions with allow-lists (recipients,
hosts, tables). Put consequential actions behind human approval. Mark untrusted content as data
with delimiters and instructions — this lowers success rates but isn't a boundary. Validate
outputs and redact PII from tool results so there's less to exfiltrate. Log tool calls with
their provenance. The prompt wording is the weakest layer; the capability design is the
strongest.

---

**Q14. How would you test reliability behaviour?**

With scripted models that fail on cue: fail twice then succeed (retries), always fail
(exhaustion behaviour and user-facing messages), primary fails (fallbacks), a model that calls
tools forever (limits), inputs with PII (redaction). Assert on call counts, final messages and
exception types. Use `jitter: false` and injectable clocks so tests are fast and exact. Run the
suite on every dependency upgrade — defaults like `onFailure`, `retry_on` and tool-error
handling are exactly where versions and languages differ.

---

**Q15. A provider's error rate climbs from 0.1% to 8% over ten minutes. What should your system do automatically, and what should a human do?**

Automatically: retries absorb the first part; as failures persist, the fallback rate rises and
traffic shifts to the backup provider; circuit breakers stop calls to any failing tool
dependency; limits keep retries from exploding cost; users get degraded-but-working answers.
Alerts fire on fallback rate and p99 latency. A human then confirms the provider incident,
decides whether to force traffic to the backup, watches the backup's quota and cost, and
afterwards reviews dead-lettered runs and replays the ones worth replaying from their
checkpoints. The design goal is that the automatic part keeps users served long enough for
the human part to be calm.

---

### Day 25 — Observability & Evaluation: Know Whether It Works

*15 questions · [open the day](../week-04-production-projects-and-interviews/day-25-observability-and-evaluation.md)*

#### Basic

**Q1. What's the difference between observability and evaluation?**

Observability is seeing what happened inside a specific run — the trace of model calls, tool
calls, inputs and outputs. Evaluation is measuring how good the system is, repeatably, on a
set of examples. You use observability to debug one bad answer, and evaluation to decide
whether a change made things better overall.

---

**Q2. What is a trace?**

A tree of runs for one request: the top-level agent or chain, and nested model calls, tool
calls and custom steps, each with inputs, outputs, timing and errors. LangChain produces the
events through callbacks; a tracer (LangSmith, OpenTelemetry, your own handler) records them.

---

**Q3. What kinds of evaluators are there?**

Code evaluators (exact match, contains, schema, regex — free and deterministic), trajectory
evaluators (did an agent call the right tools), LLM-as-judge (a model grades against a rubric
— for qualities code can't check), and human review (the ground truth that calibrates the
others).

---

**Q4. How do you track token usage and cost?**

Every `AIMessage` has `usage_metadata`. Sum it over a run's messages, or record it in a callback
handler's model-end hook; in Python, `get_usage_metadata_callback()` totals it per model name.
Cost is tokens × each model's price, so per-model totals matter when you use several models.

---

**Q5. How do you turn on LangSmith tracing?**

Set `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY` and optionally `LANGSMITH_PROJECT`. LangChain
and LangGraph runs are traced automatically; wrap your own functions with `traceable` to
include them. With tracing off, `traceable` is a transparent wrapper.

---

#### Intermediate

**Q6. How do you build a good evaluation dataset?**

Start from production: every reported failure, plus a sample of real questions in real
proportions. Add expert-written edge cases. Use synthetic examples for coverage but never
alone — models generate questions models find easy. Start with 20–50 real examples, give each
a reference (an answer, required facts, or an expected trajectory), and grow it every time
something breaks.

---

**Q7. How do you know an LLM-as-judge is trustworthy?**

Calibrate it: label 30–50 outputs yourself, run the judge on the same ones, and measure
agreement — including false positives and false negatives separately, since they rarely
cost the same. Use binary judgments with reasoning, an explicit rubric, few-shot examples, and
a different model family from the one being judged. Re-calibrate whenever the judge model or
rubric changes.

---

**Q8. How do you evaluate an agent, beyond its final answer?**

Evaluate its trajectory: compare the tool calls it made to a reference, with a mode that
matches the requirement — strict (exact sequence), unordered, subset ("never call anything
outside this set", which makes a good safety check for write tools) or superset ("must at
least call these"). Combine with final-answer evaluators and cost/step counts.

---

**Q9. How would you evaluate a RAG system?**

Separately at its two failure points. Retrieval, with labelled relevant chunks: hit rate,
recall@k, MRR. Generation, with judges: groundedness (claims supported by context), answer
relevance, and correctness against references. If recall is low, fix retrieval; if recall is
high but groundedness is low, fix the prompt or model. One end-to-end score hides which.

---

**Q10. Offline vs online evaluation?**

Offline runs a fixed dataset with references before shipping — it answers "is B better than
A?" and gates changes in CI. Online samples live traffic with reference-free evaluators,
user feedback and operational metrics — it answers "is it still working?" and finds new
failure types. Online findings feed the offline dataset.

---

**Q11. Why do callbacks matter if you use LangSmith?**

LangSmith's tracer *is* a callback handler. Knowing the callback model lets you add your own
metrics and logs, send events to other backends, and avoid the classic mistake of listening
for `handleLLMStart` / `on_llm_start` — chat models fire `handleChatModelStart` /
`on_chat_model_start` instead, so the naive handler records nothing.

---

#### Advanced

**Q12. Your teammate says the new prompt is better. How do you decide?**

Run both versions on the same dataset — ideally 50+ real examples including past failures —
with the same evaluators: code checks first, then a calibrated judge, then trajectory checks
for agent behaviour. Compare per metric, and read every example whose result changed in
either direction. Check cost and latency too. If the dataset is small, look at the size of
the difference relative to run-to-run noise (run each version twice). Then ship behind a flag
and watch the online metrics. "Better" means better on the metrics you agreed matter, not
better on the examples someone happened to read.

---

**Q13. Design the evaluation system for a production agent.**

```
   DATASET     seeded from production failures and samples; references per example;
               grows from a review queue fed by thumbs-down and failed online checks
   OFFLINE     code evaluators + trajectory checks on every PR (cheap, deterministic);
               calibrated judges nightly and before releases (costly); a regression gate
   ONLINE      sampled traffic + 100% of errors/limits/negative feedback; reference-free
               judges (groundedness), safety trajectory checks, cost/latency/error metrics
   LABELS      prompt version, model, route and user segment on every run
   CALIBRATION judges re-checked against human labels on a schedule
   PRIVACY     redaction before tracing, access control, retention
```

The piece people skip is the loop: without a path from production failures back into the
dataset, the offline suite slowly stops representing reality.

---

**Q14. What are the known biases of LLM judges and how do you mitigate them?**

Verbosity bias (longer answers score higher), position bias (in pairwise comparisons, the
first or second answer is favoured), self-preference (a model rates its own family's style
higher), and leniency (models tend to pass borderline answers). Mitigations: binary
judgments with a reasoning step, explicit rubrics that penalise padding, swapping positions
in pairwise comparisons and averaging, a different model family as judge, few-shot examples
of hard negatives, and — the only real proof — calibration against human labels.

---

**Q15. How do you handle PII and privacy in traces?**

Traces contain user input, retrieved documents and model output — treat them as production
data. Redact at the edge, before content reaches the model and the tracer (the PII middleware
changes what the model sees, but the top-level run still records the original input).
Restrict who can read production traces, set a retention period, and sample normal traffic
rather than tracing everything forever. For the most sensitive routes, record only metadata
and scores, not content.

---

### Day 26 — MCP & the Vercel AI SDK: Tools Across Boundaries

*15 questions · [open the day](../week-04-production-projects-and-interviews/day-26-mcp-and-ai-sdk.md)*

#### Basic

**Q1. What is MCP?**

The Model Context Protocol: an open standard for connecting AI applications to tools, data and
prompts. A capability is implemented once as an MCP **server**; any MCP **client** — an agent
framework, an IDE assistant, a desktop app — can then use it. It's JSON-RPC over a transport
(stdio for local subprocesses, Streamable HTTP for remote services).

---

**Q2. What are MCP's three primitives?**

Tools (functions the **model** chooses to call), resources (data the **application** reads and
attaches as context, addressed by URI), and prompts (parameterised templates the **user**
selects). The distinction is who controls each one.

---

**Q3. What's the difference between the stdio and Streamable HTTP transports?**

stdio launches the server as a local child process and talks over stdin/stdout — simple, no
network, but one process per client and only on that machine. Streamable HTTP runs the server
as a network service many clients can share — which means it needs authentication and normal
API operations.

---

**Q4. How do you use MCP tools in a LangChain agent?**

With the adapters: `MultiServerMCPClient` from `@langchain/mcp-adapters` (JS) or
`langchain-mcp-adapters` (Python). Configure servers, call `getTools()` / `get_tools()`, and pass
the result to `createAgent` / `create_agent` like any other tools. In Python they're async-only,
so use `ainvoke`.

---

**Q5. What is the Vercel AI SDK?**

A TypeScript toolkit for building AI features: a unified provider layer (`@ai-sdk/*`), core
functions (`generateText`, `streamText`, `tool`, structured output), an agent class
(`ToolLoopAgent`), UI hooks like `useChat`, and an MCP client. It's especially strong at
streaming model output into web UIs.

---

#### Intermediate

**Q6. LangChain or the Vercel AI SDK — how do you decide?**

By the job. For a streaming chat UI with a few tools in a JS app, the AI SDK is the shortest
path. For stateful agents — RAG pipelines, memory across sessions, persistence, pause-for-approval,
time travel, multi-agent graphs, or anything in Python — LangChain/LangGraph provides the
building blocks. They combine well: a LangGraph backend behind an API, consumed by an AI SDK UI.
MCP lets both use the same tools.

---

**Q7. Why must a stdio MCP server never print to stdout?**

stdout carries the protocol's JSON-RPC messages. Clients try to skip lines they can't parse — in
our tests both SDKs survived plain log lines, with the JS client reporting a parse error per line —
but output that looks like JSON or interleaves with a real message corrupts the stream, and the
errors don't mention logging. Log to stderr (`console.error`, Python's `logging`).

---

**Q8. What happens if you call `generateText` with tools but no `stopWhen`?**

It runs one step: if the model requests a tool, the tool executes, and the call returns with an
empty `text` and `finishReason: "tool-calls"` — the model never sees the result (verified). Set
`stopWhen: stepCountIs(n)` to let it loop, or use `ToolLoopAgent`, which loops by default.

---

**Q9. What are the security risks of MCP?**

A stdio server is code running with your privileges; tool descriptions from a server are text the
model follows and can be used to steer it; tool results are untrusted input subject to prompt
injection; remote servers are APIs that need authentication and authorisation; and a server
upgrade can change your agent's tools without a deploy. Mitigate with trusted and pinned servers,
allow-listed tools per agent, untrusted-data handling, auth on HTTP servers, approval gates for
consequential tools, and evals on upgrades.

---

**Q10. How does an MCP tool differ from a LangChain tool?**

A LangChain tool is an in-process function object in one language. An MCP tool is a capability
advertised by a server over a protocol — name, description, JSON Schema — and executed in the
server's process, in any language. The adapters bridge them by wrapping each MCP tool as a
LangChain tool whose function sends `tools/call`.

---

**Q11. When should you *not* use MCP?**

When the tool is only used by one application in one language — a plain in-process tool is
simpler, faster and has no process or network to manage. MCP pays off when a capability crosses
boundaries: several apps, several languages, several vendors' assistants, or a separate team
owning it.

---

#### Advanced

**Q12. Design how an organisation should roll out MCP servers.**

```
   OWNERSHIP     each capability has an owning team that runs its server (like any service)
   TRANSPORT     Streamable HTTP for shared servers; stdio only for local developer tools
   AUTH          OAuth / service tokens; authorise per tool and per caller; audit calls
   REGISTRY      an internal list of approved servers and versions; clients allow-list from it
   LEAST PRIV.   read-only tools by default; write tools separate, gated, and rare
   CHANGES       versioned releases; description and schema changes reviewed like API changes;
                 consumers run their eval suites against new versions
   OBSERVABILITY per-tool latency, error rate, and caller; tracing across client and server
```

The mindset: an MCP server is a public API whose "developers" include language models — so
descriptions are part of the contract, and any change is a behaviour change for every agent
using it.

---

**Q13. How would you migrate a large set of in-process tools to MCP?**

Not all at once, and not all of them. Start with tools that are genuinely shared or owned by other
teams. Wrap each as an MCP server behind the same interface, run the agent's evaluation suite with
the in-process version and the MCP version, and compare accuracy, latency and error rates (network
hops add latency and new failure modes — timeouts, retries, auth). Keep hot-path, single-consumer
tools in-process. Move writes last, with gates preserved. And remember the Python adapters are
async-only, which can force changes in synchronous codebases.

---

**Q14. Compare agent loops in the AI SDK and LangGraph.**

The AI SDK loop is a function call: `generateText` runs model → tools → model until a stop
condition, then returns steps and usage; `ToolLoopAgent` packages that with instructions and tools.
It's concise and well suited to request-scoped work. LangGraph models the loop as a graph with
explicit state, so it can be checkpointed after every step, paused for a human, resumed on another
machine, rewound, branched, composed into subgraphs and multi-agent systems, and streamed per node.
The trade is simplicity versus durability and control. If the loop must outlive a request, LangGraph.

---

**Q15. An agent's behaviour changed overnight and nobody deployed. What do you check?**

The things that can change without a deploy: the model version behind the provider's alias, and
**connected MCP servers** — their tool lists, descriptions and schemas are fetched at runtime, so a
server upgrade can rename a tool, reword a description or add new tools. Compare today's tool list
with yesterday's (log it at startup), check the servers' release notes, and run the evaluation suite
against the pinned previous server version. The fix is also the prevention: pin server versions and
record the tool manifest with every run's metadata.

---

### Day 27 — Deployment & Architecture: From Laptop to a Million Students

*15 questions · [open the day](../week-04-production-projects-and-interviews/day-27-deployment-and-architecture.md)*

#### Basic

**Q1. What does "stateless compute, state in a database" mean for an agent?**

No conversation or run state lives in the process: the graph is built once per process, and
every request loads and saves state through a shared checkpointer keyed by `thread_id`. Then any
instance can serve any turn, deploys don't lose conversations, and you scale by adding instances.

---

**Q2. Why shouldn't a long agent run be tied to an HTTP request?**

Requests have timeouts (load balancers, serverless limits, clients), disconnects cancel work,
and retries duplicate it. Decouple: start the run and return 202 with a run id, then stream or
poll its status, and resume interrupts with a separate request.

---

**Q3. What is the LangGraph server?**

A runtime that serves compiled graphs described in `langgraph.json` as an HTTP API: assistants,
threads with built-in persistence, blocking/streaming/background runs, interrupts and resume,
state history, crons. You run it locally with `langgraph dev` and talk to it with
`@langchain/langgraph-sdk` or `langgraph_sdk`.

---

**Q4. Why does the LangGraph server reject a graph compiled with a checkpointer?**

Because the server manages persistence itself (Postgres, via `POSTGRES_URI`). A graph-level
checkpointer would be ignored when deployed, so the server fails the load with an explicit error
telling you to remove it. Export `builder.compile()` without one.

---

**Q5. What belongs in Postgres and what in Redis?**

Postgres: durable truth — checkpoints, long-term store, conversations, runs, approvals, audit.
Redis: fast and disposable — queues, rate limits, locks, circuit-breaker state, pub/sub, caches.
The test: wiping Redis must not lose anything a user cares about.

---

#### Intermediate

**Q6. Serverless for an agent — yes or no?**

Yes for the interactive API: short streamed chat turns, starting runs, status, resuming approvals
— as long as state is in a shared checkpointer and clients are memoised with a connection pooler.
No for long runs, waiting on humans, stdio MCP subprocesses, or background work after the
response. The common split: serverless API, dedicated workers or the LangGraph server for runs.

---

**Q7. Walk me through the start/poll/resume API.**

`POST /threads/:tid/runs` validates ownership, records a run (with an idempotency key), enqueues
it and returns 202 + run id. `GET /threads/:tid/runs/:rid` returns the run's status from the runs
table and `next`/pending interrupts from the checkpoint. `POST /threads/:tid/resume` enqueues a
run with `Command(resume=…)` after checking the interrupt id. Workers execute runs; a crash is
recovered by re-queuing and resuming from the last checkpoint with a null input.

---

**Q8. How do you handle graceful shutdown?**

On `SIGTERM`: stop accepting new work, let in-flight runs finish up to a deadline, then close
database pools. In Python keep references to background tasks so you can wait on them. Anything
still running at the deadline is recoverable because of checkpoints — mark those runs so a worker
re-queues them.

---

**Q9. What's the difference between liveness and readiness checks?**

Liveness asks "is the process alive?" and should be cheap, so dependency blips don't trigger
restarts of healthy processes. Readiness asks "can it serve traffic right now?" and checks
dependencies like Postgres, so the load balancer routes around instances that can't.

---

**Q10. What usually limits an LLM application's scale?**

Rarely CPU: runs spend most of their time waiting on model providers. The limits are provider rate
limits (calls and tokens per minute), token cost, connection counts to databases, and state size
driving checkpoint write volume. Do the arithmetic — runs per second at peak, model calls per run,
tokens per run — before choosing infrastructure.

---

**Q11. How do you make run submission idempotent?**

Clients send an `Idempotency-Key` header; the API stores it with a unique constraint on the runs
table and returns the existing run id on a repeat. Side-effecting tools get their own idempotency
keys derived from the action (Day 24), so a retried or replayed step can't double-post.

---

#### Advanced

**Q12. Design the deployment for an agent product at a million users.**

Start from arithmetic: daily actives, runs per user, peak factor, model calls and tokens per run —
that tells you the provider budget and rate limits dominate. Serve interactive chat from a
stateless, horizontally scaled API with streaming and cancellation; run long and human-gated work
through a queue and workers or the LangGraph server; keep checkpoints, store, runs and audit in
Postgres (pooled, with read replicas for history views and retention jobs); use Redis for queues,
rate limits and breaker state. Multiple providers or reserved capacity with fallback and
per-tenant limits; model routing to cheaper models where evals allow; strict state and prompt size
discipline; regional deployments if latency or data residency demand it; tracing, cost and quality
dashboards; and an evaluation gate on every deploy.

---

**Q13. A worker crashes halfway through a 12-step run. What happens in a well-designed system?**

The checkpoint holds every completed superstep. The queue's visibility timeout expires and the job
is redelivered (or a reaper marks runs stuck in `running` and re-queues them). The worker calls
`invoke(null, config)` for that thread, which resumes from the last checkpoint — the completed
steps aren't re-executed or re-billed. Side effects in the interrupted step are protected by
idempotency keys. The runs table records the retry for observability.

---

**Q14. When would you choose your own service over the LangGraph server?**

When you need something the server doesn't fit: an existing platform with its own job system,
strict infrastructure or compliance constraints, a very simple workload where the extra runtime
isn't worth operating, or tight integration with an existing API and auth layer. The trade is that
you build run management, streaming, interrupt endpoints and background execution yourself. If you
find yourself re-implementing most of the server's API, that's the signal to use the server.

---

**Q15. How do you roll out a new prompt or model safely?**

Treat it as a deploy. Pin it as a versioned config value; run the offline evaluation suite against
it (Day 25); ship behind a flag to a small percentage of traffic with the version in every run's
metadata; compare online quality, cost and latency by version; then ramp up or roll back by
flipping the flag. Because checkpointed threads outlive deploys, make sure a conversation that
started on the old version behaves sensibly on the new one — or pin a thread's version until it
ends.

---

### Day 28 — Capstones & Interview Crash Course: Prove It

*28 questions · [open the day](../week-04-production-projects-and-interviews/day-28-capstones-and-interviews.md)*

The most-asked questions across the whole book, with short model answers and where to go deeper.
Each day's own section has more; `resources/interview-bank.md` collects them.

#### Foundations (Days 1–8)

**Q1. What is a token, and why does it matter?** A unit of text the model reads and writes (often
part of a word). Context limits, latency and cost are all measured in tokens, so prompt size is a
budget. *(Day 1)*

**Q2. What does temperature do?** It scales the probability distribution before sampling: low
values make outputs more deterministic, high values more varied. Use low for extraction and tools,
higher for brainstorming. *(Day 1)*

**Q3. What is LCEL?** LangChain's composition model: every component is a Runnable with
`invoke`/`stream`/`batch`, and `pipe` / `|` composes them into sequences, with `RunnableParallel`,
`RunnableLambda` and branching for the rest. Composition gives streaming, batching and tracing for
free. *(Day 7)*

**Q4. How do you get reliable structured output?** `withStructuredOutput` / `with_structured_output`
with a Zod or Pydantic schema, which uses tool calling or native JSON modes under the hood; validate,
and handle the failure path. *(Day 6)*

#### Data & RAG (Days 9–14)

**Q5. Walk me through a RAG pipeline.** Load → split (with metadata) → embed → store; at query time:
rewrite (for follow-ups) → retrieve → (rerank) → answer grounded in the retrieved context with
citations → refuse when it isn't there. Evaluate retrieval and generation separately. *(Days 9–12, 25)*

**Q6. How do you choose chunk size?** By measuring: build a labelled question set and compare hit
rate/recall across sizes and overlaps. Too small loses context; too large dilutes embeddings and
wastes tokens. *(Day 9)*

**Q7. Why does reranking help?** Bi-encoder embeddings are fast but coarse; a cross-encoder reads
query and document together and ranks more precisely. Retrieve broadly (say 20), rerank to a few. *(Day 13)*

**Q8. What's hybrid search?** Combining vector similarity with keyword search (BM25), usually with
reciprocal rank fusion — it catches exact identifiers and rare terms embeddings blur. *(Day 11)*

**Q9. How does memory work in modern LangChain?** Short-term: message history in graph state,
checkpointed per thread, trimmed or summarised. Long-term: a store namespaced by user. The old
`Memory` classes were removed. *(Days 14, 18)*

#### Tools & agents (Days 15–16)

**Q10. What makes a good tool?** A precise name and description (the model reads them), a narrow
schema, validation, errors returned as useful messages, least privilege, and idempotency for side
effects. *(Day 15)*

**Q11. Explain the ReAct loop.** Reason about what to do, act by calling a tool, observe the result,
repeat until done. Native tool calling implements this structurally; guards (step limits, repeat
detection, budgets) keep it bounded. *(Day 16)*

#### LangGraph (Days 17–21)

**Q12. Why LangGraph instead of a while loop?** State becomes explicit data owned by the framework,
so runs can be checkpointed, resumed, rewound, streamed per node, interrupted for humans, and drawn
as a diagram. *(Day 17)*

**Q13. What's a superstep?** A round in which all active nodes run against the same state snapshot;
their updates are merged through reducers at the end; then edges decide the next active set. *(Day 17)*

**Q14. State vs context vs store vs checkpoint?** State: data flowing through nodes (serialised every
superstep). Context/config: per-request handles and identities, never persisted. Store: long-term,
cross-thread memory. Checkpoint: a saved snapshot of state. *(Day 18)*

**Q15. `Command` vs a conditional edge?** A conditional edge is a pure routing function of state.
`Command` lets a node update state and route in one return — useful when the node already did the
work the decision depends on. It adds to static edges; it doesn't replace them. *(Days 19, 28)*

**Q16. What does `Send` do?** Fans out to N copies of a node, each with its own payload as its entire
state, in one superstep; results merge through a reducer. It's map-reduce with N known only at
runtime. *(Day 19)*

**Q17. How does time travel work?** Every superstep's checkpoint is addressable; invoke with a past
checkpoint's config to replay from there, or `updateState` to fork with a change. *(Day 20)*

**Q18. How do you implement human approval?** `interrupt()` inside a node pauses the run and
checkpoints it; the caller shows the payload; `Command({ resume })` continues. The node re-runs from
the top on resume, so keep side effects after the interrupt. *(Day 21)*

#### Production (Days 22–27)

**Q19. When is multi-agent worth it?** When one agent's tools, instructions or context have become
the source of errors, when work parallelises, or to isolate a dangerous capability. Measured: a
single-hop question went from 2 to 4 model calls under any supervisor pattern. *(Day 22)*

**Q20. Supervisor or swarm?** Supervisor when one voice should answer and combine specialists' work;
handoffs when the user should keep talking to the specialist. The tool-based supervisor is the
recommended default for context control. *(Day 22)*

**Q21. How do you stream an agent to a UI?** Stream modes (`updates` for progress, `messages` filtered
by a `final` tag for tokens, `custom` for events) over SSE, with cancellation wired to client
disconnects. *(Day 23)*

**Q22. What reliability defences do you put around an agent?** Retries on transient errors at one
layer with jitter, fallback provider, timeouts, call limits, circuit breakers on tools, idempotency
keys, PII redaction, and capability limits against injection. *(Day 24)*

**Q23. How do you evaluate an LLM application?** A dataset from real traffic and failures; code
evaluators first, trajectory evaluators for agents, calibrated LLM judges for quality; a regression
gate in CI; sampled online evaluation. *(Day 25)*

**Q24. What is MCP and when do you use it?** An open protocol for exposing tools, resources and
prompts to any AI client. Use it when a capability must cross app, language, team or vendor
boundaries; keep single-app tools in-process. *(Day 26)*

**Q25. How do you deploy an agent that can run for minutes?** Decouple the run from the request:
start (202 + run id), stream or poll status, resume interrupts with a separate request; state in
Postgres, workers or the LangGraph server executing runs, idempotent submission. *(Day 27)*

#### Judgement

**Q26. When should you not use an agent?** When the steps are known (use a chain or workflow), when
latency or cost budgets are tight, when the task is a single structured call, or when you can't yet
evaluate whether it helps.

**Q27. What's the most common mistake you see in LLM apps?** Shipping without an evaluation set — so
every change is judged by a few hand-picked examples. Close runners-up: state bloat, unfiltered
retries, and trusting tool output.

**Q28. How do you keep up with fast-changing libraries?** Pin versions, keep an evaluation suite and a
small set of behaviour tests (like this book's scripted-model checks), and upgrade deliberately —
this book found behaviour that differed between minor versions and between the JS and Python
libraries.

---
