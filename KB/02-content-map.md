# 02 — Content map

What is in every file, what is generated, and how the days depend on one another.

---

## Days

| Day | Title | Lines | Teaches (key APIs / ideas) |
|---|---|---|---|
| 0A | Your Toolkit: Terminal, Git, Node, Python & Reading Errors | 2087 | terminal (PowerShell + bash), paths, Node/Python, npm (`npm pkg set type=module`), venv, git + `.gitignore`, `.env`, reading stack traces |
| 0B | Programming for AI: JSON, HTTP, Async & Schemas in JS and Python | 2311 | JSON, HTTP status codes via a local mock API (fetch / httpx), ESM, async/await, `Promise.all` / `gather`, async generators, Zod ↔ Pydantic, retries with jitter |
| 0C | Just-Enough Maths: Vectors, Probability & Softmax | 2218 | vectors, dot/norm/cosine, matrices as many dot products, softmax + max-subtraction, temperature, log-probs, seeded sampling, p50/p95, precision/recall, sample size |
| 01 | What an LLM Actually Is: Tokens, Context & Inference | 1877 | tokenization, context window, sampling knobs, the inference pipeline |
| 02 | Prompt Engineering & Talking to Models With No Framework | 2324 | zero/few-shot, CoT, ReAct prompting, raw provider SDKs, JSON mode |
| 03 | Choosing a Model · Why LangChain Exists | 1760 | closed vs open-weight, size, context, reasoning models, per-million pricing, TTFT, benchmark limits, licence/privacy, a keyless cost estimator and eval harness; why LangChain, when not to |
| 04 | LangChain Models: invoke, stream, batch & Message Types | 2261 | `ChatGroq`/`ChatOllama`, `initChatModel`, message types, `usage_metadata` |
| 05 | Prompts & Templates | 1854 | `ChatPromptTemplate`, `MessagesPlaceholder`, few-shot & partial prompts |
| 06 | Output Parsers & Structured Output (Zod ↔ Pydantic) | 2452 | `withStructuredOutput`/`with_structured_output`, retry/fixing parsers |
| 07 | LCEL & Runnables (the #1 interview topic) | 2518 | `pipe`/`\|`, Sequence/Parallel/Lambda/Passthrough/Assign/Branch, streaming |
| 08 | Chains: Sequential, Parallel, Router & Document Chains | 2523 | stuff/map-reduce/refine, `@langchain/classic` migration trap |
| 09 | Documents, Loaders, Splitting & Chunking Strategy | 2383 | loaders, `RecursiveCharacterTextSplitter`, header breadcrumbs, chunk sizing |
| 10 | Embeddings: Vectors, Similarity & Model Choice | 2403 | cosine/euclidean/dot by hand, model choice, caching, anisotropy |
| 11 | Vector Databases: Indexes, Filtering & Hybrid Search | 2390 | HNSW/IVF, pre- vs post-filter, BM25 + RRF hybrid search |
| 12 | Naive RAG End-to-End (and Six Ways to Break It) | 2475 | the full pipeline, grounding contract, verified citations, failure triage |
| 13 | Advanced RAG: Reranking, HyDE, Multi-Query & Self-Correction | 2739 | reranking, MMR, multi-query, parent-document, corrective/self/adaptive RAG |
| 14 | Memory: Buffer, Summary, Entity & What Actually Changed | 2838 | `trimMessages`, summary/entity memory, why 0.x `Memory` classes were removed |
| 15 | Tools: Creating, Calling, Schemas, Errors & Retries | 2966 | `tool()`/`@tool`, schemas, the calling loop, errors as content, tool security |
| 16 | Agents From First Principles: Build ReAct by Hand | 2674 | the ReAct loop by hand, five failure modes, guards, `createAgent`/`create_agent` |
| 17 | LangGraph Basics: From a Loop to a Graph | 2707 | `StateGraph`, `Annotation`/`TypedDict`, supersteps, `ToolNode`, `drawMermaid` |
| 18 | State & Reducers: What Goes Where | 2288 | reducer laws, `addMessages` semantics, state vs context vs store vs checkpoint |
| 19 | Control Flow: `Command`, `Send` & Subgraphs | 2545 | `Command`, `Send` map-reduce, subgraphs + the duplication trap, `Command.PARENT` |
| 20 | Persistence & Checkpointing: Save, Resume, Rewind | 2100 | checkpointers, `thread_id`, state history, replay vs fork, time travel |
| 21 | Human-in-the-Loop: Pause, Ask, Resume | 2936 | `interrupt()`, `Command({resume})`, four HITL patterns, node re-execution |
| 22 | Multi-Agent Systems: Supervisors, Handoffs & When Not To | 2364 | agent-as-tool supervisor, swarm handoffs, hierarchies, measured costs |
| 23 | Streaming & Events: Make It Feel Fast | 1977 | stream modes, tag-filtered tokens, custom events, SSE, cancellation |
| 24 | Reliability: Surviving a Bad Day in Production | 2200 | retries/jitter, fallbacks, timeouts, limits, breakers, PII, injection |
| 25 | Observability & Evaluation: Know Whether It Works | 1940 | callbacks, LangSmith, datasets, `openevals` judges, `agentevals` trajectories |
| 26 | MCP & the Vercel AI SDK: Tools Across Boundaries | 1782 | MCP server/client/transports, adapters, AI SDK v7 core, `stopWhen` |
| 27 | Deployment & Architecture: From Laptop to a Million Students | 1888 | start/poll/resume, LangGraph server + SDKs, Docker, capacity arithmetic |
| 28 | Capstones & Interview Crash Course: Prove It | 1455 | keyless capstone starter kit, 12 capstones, answer frameworks, mocks |
| 29 | Open & Local Models: Run AI on Your Own Machine | 1964 | model cards and licences, memory arithmetic vs real files, quantisation (GGUF/ONNX bits), chat templates, transformers + `ChatHuggingFace`, a Transformers.js `BaseChatModel`, `ChatOllama` |
| 30 | Inference & Serving: What Happens Between Request and Token | 2253 | prefill vs decode, TTFT, KV cache (`use_cache`, memory formula), batching + left padding, speculative / prompt-lookup decoding, an OpenAI-compatible FastAPI server called via `ChatOpenAI` |
| 31 | Fine-Tuning: Teaching a Model New Habits | 2094 | fine-tune vs prompt vs RAG, chat JSONL with Zod/Pydantic, loss masking, LoRA (rank, alpha, trainable counts), a real CPU LoRA run, overfitting, merge, serving through Day 30's server |
| 32 | Dataset Engineering: Good Data In, Good Model Out | 2361 | normalise + hash dedupe, shingles/Jaccard/MinHash, quality filters, regex PII limits, synthetic data checks, group vs record split, Cohen's kappa, dataset cards |
| 33 | Multimodal: Images, Documents and Voice | 2349 | image tokens and tiling, LangChain image blocks (JS/PY differences), a local VLM as `BaseChatModel`, Whisper STT and sample rates, TTS, multimodal RAG, a timed voice pipeline |
| 34 | Cost & Latency: Making It Cheap and Fast | 2624 | cost ledger from `usage_metadata`, exact cache (and the JS `ChatGroq` key gap), semantic cache + false hits, prompt-prefix layout, cascades vs routers, `maxConcurrency`, budget guard |
| 35 | AI Security: Attack Your Own App Before Someone Else Does | 2426 | OWASP Top 10 for LLM apps, direct/indirect injection, excessive agency (Rule of Two), output handling, canaries, supply chain (pickle vs safetensors), a red-team harness, HITL `when` |
| 36 | Context Engineering & the Five Agent Patterns | 2660 | the five Anthropic patterns as graphs, workflow vs agent, context measured per call, write/select/compress/isolate, context-editing middleware, `deepagents` |
| 37 | Advanced Retrieval: Graphs, SQL and Agentic Search | 2537 | triples + entity resolution, graph traversal, GraphRAG communities, guarded text-to-SQL (`node:sqlite` / `sqlite3`, authorizer, read-only), agentic search with stop rules |
| 38 | Emerging Agents: Browsers, Computers and Agents That Talk to Agents | 2335 | Playwright browser agent (ARIA snapshot, route allowlist, step limit, default-deny approval), computer use (concepts), A2A v1.0 in both languages, agent skills |
| 39 | AI Product Engineering: Building Something People Trust and Use | 2655 | AI UX patterns, feedback tied to run ids, sticky A/B assignment, two-proportion z-test, sample size, peeking, guardrail metrics, fairness checks, EU AI Act basics |
| 40 | Final Capstone & Career: Ship It, Prove It, Get Hired | 2577 | a keyless final capstone kit (RAG + agent + approval + ledger + evals + red team), one release gate with exit codes, portfolio, CV bullets, job shapes, Weeks 5–6 interview set |

## Other files

| File | Lines | Notes |
|---|---|---|
| `README.md` | 248 | Master index: the three tracks, 43-day calendar for Weeks 0–6 (all linked), how to use, day template, reference + maintainers' tables, StudyBuddy map |
| `CONTRIBUTING.md` | 71 | The six rules (incl. plain English + no code change in prose edits), verification commands, shell/disk notes, house style |
| `SETUP.md` | 305 | Free keys (Groq/Gemini/Ollama), JS + Python envs (npm 11 `type` trap), `.env`, verify script, troubleshooting |
| `week-00-start-here/README.md` | 160 | The three tracks, the 🟣 10-question self-check with routing, Week 0 at a glance |
| `week-01-foundations/README.md` | 118 | Week index — see conventions for the shape |
| `week-02-…/README.md` | 165 | Includes the 🚨 `@langchain/classic` version trap |
| `week-03-…/README.md` | 227 | Includes the three-generations-of-agent-API trap and the JS↔Python minefield table |
| `week-04-…/README.md` | 165 | Includes the "Verified, not recalled" findings table |
| `week-05-the-model-layer/README.md` | 132 | Model-layer week; 🐍 note on Python-only tooling; version traps (bf16 default, dtype typos, retries, cache key) |
| `week-06-advanced-agents-product-and-career/README.md` | 113 | Patterns, retrieval, emerging agents, product, final capstone |

## Tooling

| File | Lines | What it does |
|---|---|---|
| `tools/verify.py` | 96 | The one command to run before finishing: links, 10-section structure, fence/`<details>` balance, language parity, exercise parity, README calendar (one link per day file), stats |
| `tools/gen_resources.py` | 267 | Regenerates the three generated reference files for Weeks 0–6; holds their curated header tables |
| `tools/check_links.py` | 39 | Relative-link check on its own (exit code 1 on breakage), for a quick loop |
| `tools/sort_glossary.py` | 43 | Sorts glossary sections, asserting the entry count is unchanged |
| `tools/readability.py` | 101 | Flesch / grade / sentences over 30 words per day (prose only) |
| `tools/check_code_unchanged.py` | 72 | Proves a prose edit kept every code block and inline-code span (vs the git index) |
| `tools/add_footers.py` | 60 | Adds the missing ← / week index / → footer in course order |
| `KB/*.md` | ~1,330 | This knowledge base (8 files) |

Both checkers skip fenced code blocks, because `KB/01-conventions.md` quotes example markdown
whose links don't resolve from `KB/`.

## Resources — hand-written vs generated

| File | Lines | Source |
|---|---|---|
| `resources/glossary.md` | 714 | **Hand-written** · 308 entries, `**Term** *(Day NN)* — def.` (Week 0 tags are `Day 0A`–`0C`), alphabetical. Sort with `tools/sort_glossary.py`. |
| `resources/cheatsheet-lcel.md` | 147 | **Hand-written** · every form verified |
| `resources/cheatsheet-langgraph.md` | 181 | **Hand-written** · graph API + "ten bugs to recognise on sight" (recursion default and fan-out rows corrected Oct 2026) |
| `resources/cheatsheet-rag-patterns.md` | 371 | **Hand-written** (Week 2) · import paths + decision tree |
| `resources/capstone-projects.md` | 122 | **Hand-written** · 12 projects, tiers, skills matrix; links Day 28 anchors |
| `resources/js-vs-python-mapping.md` | 797 | **GENERATED** from each day's translation table + a curated behaviour-difference table in the header |
| `resources/interview-bank.md` | 8136 | **GENERATED** from every day's §9 · 587 questions |
| `resources/troubleshooting.md` | 202 | **GENERATED** from the seven week blockers tables + a curated verified-error table and silent-failure table in the header |

> The curated header tables inside the generated files live in `tools/gen_resources.py` — edit
> them there, not in the output.

## StudyBuddy — the running project

```
Week 0  v0     an empty, correctly configured JS + Python project              (Day 0A)
Week 1  v1.0   parallel analysis · routing · streaming · retries              (Day 07)
Week 2  v2.0   reads your documents · verified citations · conversational     (Day 12)
        v3.0   memory across sessions · reranking                            (Day 14)
Week 3  v3.5   tools: calculator, search, progress DB                        (Day 16)
        v3.6   rebuilt as a graph, draws its own diagram                     (Day 17)
        v4.0   persistence · time travel · approval gate before any write    (Day 21)
Week 4  v5.0   supervisor + researcher/quizmaster/analyst as tools           (Day 22)
        v5.1   streamed to a browser with working cancellation               (Day 23)
        v5.2   retries, fallback, limits, breaker, PII redaction             (Day 24)
        v5.3   traced, evaluated, CI-gated                                   (Day 25)
        v5.4   its tools exposed over MCP                                    (Day 26)
        v6.0   production architecture for 100k students                     (Day 27)
Week 5  v6.1   runs offline with a local model                               (Day 29)
        v6.2   talks to its own OpenAI-compatible server                     (Day 30)
        v6.3   LoRA adapter → {answer, quiz} cards                           (Day 31)
        v6.4   versioned, leak-free question bank behind a data gate         (Day 32)
        v6.5   reads a photo of notes or a voice question                    (Day 33)
        v6.6   cached, routed, budgeted, with a cost dashboard               (Day 34)
        v6.7   red-team suite in CI                                          (Day 35)
Week 6  v7.0   code router → simplest pattern per feature                    (Day 36)
        v7.1   "ask my progress": guarded SQL + course graph                 (Day 37)
        v7.2   course-registration browser helper with approval              (Day 38)
        v7.3   feedback tied to run ids + A/B test of tutor prompts          (Day 39)
        v8.0   🏆 final capstone: one release gate                            (Day 40)
```

## Cross-day dependencies

Changing these ideas means updating the days that build on them:

| Idea | Introduced | Reused in |
|---|---|---|
| Message types, `usage_metadata` | 04 | 14, 16, 18, 23, 25 |
| Structured output | 06 | 13, 19, 22, 25, 26 |
| LCEL composition | 07 | 08, 12, 13, 17 (graphs are Runnables) |
| RAG pipeline | 12 | 13, 25 (RAG metrics), 28 (capstones) |
| Tools & errors-as-content | 15 | 16, 17, 19, 21, 24, 26 |
| Reducers / state design | 18 | 19, 20, 21, 22, 27 |
| Checkpointers & `thread_id` | 20 | 21, 23, 24, 27 |
| `interrupt()` | 21 | 24, 26, 27, 28 |
| Scripted/fake models | 22 | 23, 24, 25, 26, 28 |
| Capacity arithmetic | 27 | 28 (design answers), 30, 40 |
| Maths (cosine, softmax, percentiles) | 0C | 01, 10, 23, 27, 30, 39 |
| Async / JSON / HTTP / Zod ↔ Pydantic | 0B | every code day |
| Choosing a model + a tiny eval | 03 | 25, 29, 34 |
| Local model + chat template | 29 | 30, 31, 33 |
| OpenAI-compatible server | 30 | 31, 33 |
| Five agent patterns, context engineering | 08, 14, 19, 22 | 36, 40 |
| Red-team suite, cost ledger, release gate | 35, 34 | 40 |
