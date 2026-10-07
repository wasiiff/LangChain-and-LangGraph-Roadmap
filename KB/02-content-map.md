# 02 — Content map

What is in every file, what is generated, and how the days depend on one another.

---

## Days

| Day | Title | Lines | Teaches (key APIs / ideas) |
|---|---|---|---|
| 01 | What an LLM Actually Is: Tokens, Context & Inference | 1369 | tokenization, context window, sampling knobs, the inference pipeline |
| 02 | Prompt Engineering & Talking to Models With No Framework | 1968 | zero/few-shot, CoT, ReAct prompting, raw provider SDKs, JSON mode |
| 03 | JS & Python Essentials for AI · Why LangChain Exists | 1594 | ESM/async vs venv/asyncio, Zod ↔ Pydantic, when *not* to use a framework |
| 04 | LangChain Models: invoke, stream, batch & Message Types | 1773 | `ChatGroq`/`ChatOllama`, `initChatModel`, message types, `usage_metadata` |
| 05 | Prompts & Templates | 1777 | `ChatPromptTemplate`, `MessagesPlaceholder`, few-shot & partial prompts |
| 06 | Output Parsers & Structured Output (Zod ↔ Pydantic) | 2116 | `withStructuredOutput`/`with_structured_output`, retry/fixing parsers |
| 07 | LCEL & Runnables (the #1 interview topic) | 2376 | `pipe`/`\|`, Sequence/Parallel/Lambda/Passthrough/Assign/Branch, streaming |
| 08 | Chains: Sequential, Parallel, Router & Document Chains | 2339 | stuff/map-reduce/refine, `@langchain/classic` migration trap |
| 09 | Documents, Loaders, Splitting & Chunking Strategy | 2319 | loaders, `RecursiveCharacterTextSplitter`, header breadcrumbs, chunk sizing |
| 10 | Embeddings: Vectors, Similarity & Model Choice | 2282 | cosine/euclidean/dot by hand, model choice, caching, anisotropy |
| 11 | Vector Databases: Indexes, Filtering & Hybrid Search | 2280 | HNSW/IVF, pre- vs post-filter, BM25 + RRF hybrid search |
| 12 | Naive RAG End-to-End (and Six Ways to Break It) | 2302 | the full pipeline, grounding contract, verified citations, failure triage |
| 13 | Advanced RAG: Reranking, HyDE, Multi-Query & Self-Correction | 2581 | reranking, MMR, multi-query, parent-document, corrective/self/adaptive RAG |
| 14 | Memory: Buffer, Summary, Entity & What Actually Changed | 2695 | `trimMessages`, summary/entity memory, why 0.x `Memory` classes were removed |
| 15 | Tools: Creating, Calling, Schemas, Errors & Retries | 2867 | `tool()`/`@tool`, schemas, the calling loop, errors as content, tool security |
| 16 | Agents From First Principles: Build ReAct by Hand | 2503 | the ReAct loop by hand, five failure modes, guards, `createAgent`/`create_agent` |
| 17 | LangGraph Basics: From a Loop to a Graph | 2567 | `StateGraph`, `Annotation`/`TypedDict`, supersteps, `ToolNode`, `drawMermaid` |
| 18 | State & Reducers: What Goes Where | 2180 | reducer laws, `addMessages` semantics, state vs context vs store vs checkpoint |
| 19 | Control Flow: `Command`, `Send` & Subgraphs | 2437 | `Command`, `Send` map-reduce, subgraphs + the duplication trap, `Command.PARENT` |
| 20 | Persistence & Checkpointing: Save, Resume, Rewind | 2042 | checkpointers, `thread_id`, state history, replay vs fork, time travel |
| 21 | Human-in-the-Loop: Pause, Ask, Resume | 2825 | `interrupt()`, `Command({resume})`, four HITL patterns, node re-execution |
| 22 | Multi-Agent Systems: Supervisors, Handoffs & When Not To | 2273 | agent-as-tool supervisor, swarm handoffs, hierarchies, measured costs |
| 23 | Streaming & Events: Make It Feel Fast | 1907 | stream modes, tag-filtered tokens, custom events, SSE, cancellation |
| 24 | Reliability: Surviving a Bad Day in Production | 2044 | retries/jitter, fallbacks, timeouts, limits, breakers, PII, injection |
| 25 | Observability & Evaluation: Know Whether It Works | 1856 | callbacks, LangSmith, datasets, `openevals` judges, `agentevals` trajectories |
| 26 | MCP & the Vercel AI SDK: Tools Across Boundaries | 1701 | MCP server/client/transports, adapters, AI SDK v7 core, `stopWhen` |
| 27 | Deployment & Architecture: From Laptop to a Million Students | 1790 | start/poll/resume, LangGraph server + SDKs, Docker, capacity arithmetic |
| 28 | Capstones & Interview Crash Course: Prove It | 1321 | keyless capstone starter kit, 12 capstones, answer frameworks, mocks |

## Other files

| File | Lines | Notes |
|---|---|---|
| `README.md` | 184 | Master index: 28-day calendar (all linked), how to use, day template, reference table (incl. a maintainers' block pointing here), StudyBuddy map |
| `CLAUDE.md` | 57 | The five rules, verification command, shell notes, house style — auto-loaded each session |
| `SETUP.md` | 303 | Free keys (Groq/Gemini/Ollama), JS + Python envs, `.env`, verify script, troubleshooting |
| `week-01-foundations/README.md` | 114 | Week index — see conventions for the shape |
| `week-02-…/README.md` | 165 | Includes the 🚨 `@langchain/classic` version trap |
| `week-03-…/README.md` | 226 | Includes the three-generations-of-agent-API trap and the JS↔Python minefield table |
| `week-04-…/README.md` | 165 | Includes the "Verified, not recalled" findings table |

## Tooling

| File | Lines | What it does |
|---|---|---|
| `tools/verify.py` | 96 | The one command to run before finishing: links, 10-section structure, fence/`<details>` balance, language parity, exercise parity, README calendar, stats |
| `tools/gen_resources.py` | 259 | Regenerates the three generated reference files; holds their curated header tables |
| `tools/check_links.py` | 39 | Relative-link check on its own (exit code 1 on breakage), for a quick loop |
| `tools/sort_glossary.py` | 43 | Sorts glossary sections, asserting the entry count is unchanged |
| `KB/*.md` | 824 | This knowledge base (7 files) |

Both checkers skip fenced code blocks, because `KB/01-conventions.md` quotes example markdown
whose links don't resolve from `KB/`.

## Resources — hand-written vs generated

| File | Lines | Source |
|---|---|---|
| `resources/glossary.md` | 368 | **Hand-written** · 137 entries, `**Term** *(Day NN)* — def.`, alphabetical. Sort with `tools/sort_glossary.py`. |
| `resources/cheatsheet-lcel.md` | 147 | **Hand-written** · every form verified |
| `resources/cheatsheet-langgraph.md` | 181 | **Hand-written** · graph API + "ten bugs to recognise on sight" |
| `resources/cheatsheet-rag-patterns.md` | 371 | **Hand-written** (Week 2) · import paths + decision tree |
| `resources/capstone-projects.md` | 122 | **Hand-written** · 12 projects, tiers, skills matrix; links Day 28 anchors |
| `resources/js-vs-python-mapping.md` | 477 | **GENERATED** from each day's translation table + a curated behaviour-difference table in the header |
| `resources/interview-bank.md` | 5509 | **GENERATED** from every day's §9 · 378 questions |
| `resources/troubleshooting.md` | 138 | **GENERATED** from the four week blockers tables + a curated verified-error table and silent-failure table in the header |

> The curated header tables inside the generated files live in `tools/gen_resources.py` — edit
> them there, not in the output.

## StudyBuddy — the running project

```
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
| Capacity arithmetic | 27 | 28 (design answers) |
