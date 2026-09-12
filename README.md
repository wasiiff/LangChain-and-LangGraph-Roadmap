# LangChain & LangGraph Masterbook — 28 Days, JavaScript **and** Python

> A complete, beginner-friendly course that takes you from *"what even is a token?"* to
> *"I deployed a multi-agent system and I can explain every line of it in an interview."*
>
> **Every single concept is shown twice** — once in JavaScript, once in Python — using the
> **same example**, so the only thing that changes is the syntax.

---

## Who this is for

| You are... | This book gives you... |
|---|---|
| A web dev who wants to build AI features | Real code you can paste into a Next.js / FastAPI app |
| Preparing for AI Engineer / Agentic AI interviews | ~150 interview questions with answers, 4 system-design walkthroughs |
| A Python dev who keeps hitting JS-only tutorials (or vice-versa) | Both languages, side by side, always |
| Someone who hates hand-wavy tutorials | "Under the hood" sections that explain what the library actually does |

**Prerequisites:** you can write a `for` loop and call an API. That's genuinely it.
Async/await, TypeScript basics, Pydantic and Zod are all taught in [Day 03](week-01-foundations/day-03-js-python-essentials-and-why-langchain.md).

---

## How to use this book

1. **Do [SETUP.md](SETUP.md) first.** It takes ~15 minutes and costs **$0** — we use free providers (Groq, Google Gemini, Ollama) everywhere.
2. **One day per day.** Each file is 1–3 hours. Don't binge — the exercises are where the learning happens.
3. **Pick a lane, then peek at the other.** If you're a JS dev, read the JS block carefully and *skim* the Python one. Reading both is how you get fluent in the ecosystem, because half the docs and job posts are in the other language.
4. **Actually do the exercises.** Solutions are hidden behind `<details>` dropdowns — try first, then peek.
5. **Answer the interview questions out loud.** Explaining is the difference between "I've used LangGraph" and "I understand LangGraph."

### The structure of every day file

```
# Day NN — Topic
> ⏱ Time  ·  🎯 Prereqs  ·  🧩 Difficulty

 1. The problem          ← a real-life story, zero jargon
 2. Mental model         ← a diagram you can draw from memory
 3. First principles     ← how it actually works
 4. Code — JavaScript
 5. Code — Python        ← same example, line-for-line comparable
 6. Under the hood       ← what the library is doing for you
 7. Common mistakes      ← ❌ wrong / ✅ right
 8. Exercises            ← with hidden solutions in both languages
 9. Interview questions  ← Basic / Intermediate / Advanced, with answers
10. Recap + what's next
```

---

## The 28-day calendar

### 🟢 Week 1 — Foundations & LangChain Core
*Goal: understand what an LLM is, then build chains with LCEL.*

| Day | Topic | |
|---|---|---|
| 01 | LLMs, tokens, context windows & how inference actually works | [→](week-01-foundations/day-01-llms-tokens-and-inference.md) |
| 02 | Prompt engineering + talking to models with **no framework at all** | [→](week-01-foundations/day-02-prompt-engineering-and-raw-apis.md) |
| 03 | JS & Python essentials for AI · **Why LangChain exists (and when not to use it)** | [→](week-01-foundations/day-03-js-python-essentials-and-why-langchain.md) |
| 04 | LangChain models: `invoke` / `stream` / `batch`, every parameter, message types | [→](week-01-foundations/day-04-langchain-models.md) |
| 05 | Prompts: templates, chat templates, placeholders, few-shot | [→](week-01-foundations/day-05-prompts-and-templates.md) |
| 06 | Output parsers & structured output: **Zod ↔ Pydantic** | [→](week-01-foundations/day-06-output-parsers-structured-output.md) |
| 07 | **LCEL & Runnables** — the #1 interview topic · Week-1 project | [→](week-01-foundations/day-07-lcel-and-runnables.md) |

### 🔵 Week 2 — Data, Embeddings, RAG & Memory
*Goal: make the model answer questions about **your** documents.*

| Day | Topic | |
|---|---|---|
| 08 | Chains: sequential, parallel, router & **document chains** | [→](week-02-data-embeddings-and-rag/day-08-chains.md) |
| 09 | Documents, loaders, splitting & chunking strategy | [→](week-02-data-embeddings-and-rag/day-09-documents-and-splitting.md) |
| 10 | Embeddings deep dive & similarity metrics (worked by hand) | [→](week-02-data-embeddings-and-rag/day-10-embeddings.md) |
| 11 | Vector databases: HNSW, metadata filters, **hybrid search** | [→](week-02-data-embeddings-and-rag/day-11-vector-databases.md) |
| 12 | **Naive RAG end-to-end** — then break it six ways on purpose | [→](week-02-data-embeddings-and-rag/day-12-naive-rag.md) |
| 13 | Advanced RAG: reranking, HyDE, multi-query, Corrective/Self/Adaptive | [→](week-02-data-embeddings-and-rag/day-13-advanced-rag.md) |
| 14 | Memory — and how it *really* works now · Week-2 project | [→](week-02-data-embeddings-and-rag/day-14-memory.md) |

### 🟠 Week 3 — Tools, Agents & LangGraph
*Goal: build things that decide, act, loop, and can be paused for a human.*

| Day | Topic | |
|---|---|---|
| 15 | Tools: creating, calling, schemas, errors, retries | [→](week-03-tools-agents-and-langgraph/day-15-tools.md) |
| 16 | Agents from first principles — hand-build ReAct in 40 lines | [→](week-03-tools-agents-and-langgraph/day-16-agents.md) |
| 17 | LangGraph basics: `StateGraph`, nodes, edges, compile, visualize | [→](week-03-tools-agents-and-langgraph/day-17-langgraph-basics.md) |
| 18 | State & reducers · state vs memory vs context vs store vs checkpoint | [→](week-03-tools-agents-and-langgraph/day-18-state-and-reducers.md) |
| 19 | Conditional edges, loops, `Command`, `Send` fan-out, subgraphs | [→](week-03-tools-agents-and-langgraph/day-19-control-flow.md) |
| 20 | Persistence & checkpointing, threads, time travel | [→](week-03-tools-agents-and-langgraph/day-20-persistence-and-checkpointing.md) |
| 21 | Human-in-the-loop: `interrupt`, resume, approve/reject/edit · Week-3 project | [→](week-03-tools-agents-and-langgraph/day-21-human-in-the-loop.md) |

### 🔴 Week 4 — Multi-agent, Production, Projects & Interviews
*Goal: ship it, watch it, and talk about it convincingly.*

| Day | Topic | |
|---|---|---|
| 22 | Multi-agent: supervisor, hierarchical, handoffs — and when it backfires | [→](week-04-production-projects-and-interviews/day-22-multi-agent.md) |
| 23 | Streaming & events: stream modes, token streaming to a UI, SSE | [→](week-04-production-projects-and-interviews/day-23-streaming-and-events.md) |
| 24 | Reliability: retries, fallbacks, timeouts, circuit breakers, guardrails | [→](week-04-production-projects-and-interviews/day-24-reliability.md) |
| 25 | Observability & evaluation: LangSmith, datasets, LLM-as-judge, RAG metrics | [→](week-04-production-projects-and-interviews/day-25-observability-and-evaluation.md) |
| 26 | **MCP** (servers, clients, transports, security) + **Vercel AI SDK** compared | *coming next* |
| 27 | Deployment & architecture: Docker, serverless, queues, scaling to 1M users | *coming next* |
| 28 | **12 capstone projects** + **interview crash course** & mock interviews | *coming next* |

---

## Reference material

| File | What's in it |
|---|---|
| [SETUP.md](SETUP.md) | Free API keys, Node & Python environments, `.env`, verification script |
| [resources/glossary.md](resources/glossary.md) | Every term in this book, one line each |
| `resources/cheatsheet-lcel.md` | Runnables at a glance |
| `resources/cheatsheet-langgraph.md` | Graph API at a glance |
| [resources/cheatsheet-rag-patterns.md](resources/cheatsheet-rag-patterns.md) | Which RAG pattern for which problem |
| `resources/js-vs-python-mapping.md` | Every API, JS name ↔ Python name |
| `resources/interview-bank.md` | ~150 questions with answers |
| `resources/capstone-projects.md` | 12 project specs with architecture |
| `resources/troubleshooting.md` | Error message → cause → fix |

---

## The running project: **StudyBuddy**

Rather than 28 disconnected toy examples, one product grows through the whole book:

```
Day 07  StudyBuddy v1   a CLI tutor that explains topics at your level
Day 12  StudyBuddy v2   + reads your documents and cites verified sources
Day 14  StudyBuddy v3   + reranking, and memory that survives across sessions
Day 16  StudyBuddy v4   + uses tools (calculator, web search, your notes)
Day 21  StudyBuddy v5   + a LangGraph agent that asks permission before acting
Day 22  StudyBuddy v6   + a team of agents: researcher, writer, quiz-master
Day 27  StudyBuddy v7   + deployed, streaming, observed, and rate-limited
```

Every day you add one capability to something real.

---

## Versions this book targets

| Thing | Version | Note |
|---|---|---|
| LangChain (Python) | `langchain` **1.x** | `pip install langchain` |
| LangChain (JS) | `langchain` **1.x** | `npm install langchain` |
| LangGraph | **1.x** (both languages) | ships with `langchain` 1.x |
| Node.js | **20+** | ESM, top-level `await` |
| Python | **3.10+** | needed for modern typing syntax |

> ⚠️ **Version warning.** LangChain changed a *lot* between 0.x and 1.x. Old blog posts will
> show you `LLMChain`, `initialize_agent` and `ConversationBufferMemory` — those are legacy.
> This book teaches the modern API, and marks legacy patterns in boxes like this so you still
> recognise them in interviews and old codebases.

---

## A note on cost

You can complete **all 28 days for free**:

- **Groq** — free tier, very fast, our default chat provider
- **Google Gemini** — generous free tier, our fallback + free embeddings
- **Ollama** — runs models on your own laptop, fully offline, $0 forever
- **Chroma / FAISS** — local vector stores, no cloud account

Paid options (OpenAI, Anthropic, Pinecone) appear in collapsed `<details>` blocks so you know
the production path, but you never *need* them.

---

Start here → **[SETUP.md](SETUP.md)** → **[Day 01](week-01-foundations/day-01-llms-tokens-and-inference.md)**
