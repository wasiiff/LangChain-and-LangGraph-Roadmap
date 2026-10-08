# AI Engineering — From Zero to Production, in JavaScript **and** Python

> A complete, beginner-friendly course that takes you from *"what even is a token?"* to
> *"I shipped, measured and secured an AI system, and I can explain every line of it in an
> interview."* LangChain and LangGraph are the main tools; the ideas work with any stack.
>
> **Every concept is shown twice** — once in JavaScript, once in Python — using the **same
> example**, so the only thing that changes is the syntax.

---

## Who this is for

| You are... | This course gives you... |
|---|---|
| New to programming, or new to JS/Python | **Week 0** — terminal, git, JSON, HTTP, async and the maths you need, slowly and in plain English |
| A web developer who wants to build AI features | Real code you can paste into a Next.js / FastAPI app |
| Preparing for AI Engineer / Agentic AI interviews | Hundreds of interview questions with answers, plus system-design walkthroughs |
| A Python dev who keeps hitting JS-only tutorials (or the other way round) | Both languages, side by side, always |
| Someone who hates hand-wavy tutorials | Every behaviour in the course was **run and measured**, not recalled |

**Prerequisites:** none for the 🟢 track — Week 0 starts from the terminal. If you already code,
see the three tracks below.

---

## Where do I start?

| Track | You are… | Start at |
|---|---|---|
| 🟢 **Beginner** | New to programming, or to JavaScript/Python | [Week 0 — Start Here](week-00-start-here/README.md) |
| 🔵 **Developer, new to AI** | You code every week but have never built with an LLM | [SETUP.md](SETUP.md) → [Day 01](week-01-foundations/day-01-llms-tokens-and-inference.md) |
| 🟣 **Already used LangChain** | You have built a chain or a small RAG app | the [10-question self-check](week-00-start-here/README.md#self-check-for-the--track) |

---

## How to use this course

1. **Do [SETUP.md](SETUP.md) first** (developers) or **Week 0** (beginners). Everything can be
   done for **$0** — free providers (Groq, Google Gemini, Ollama) and local models.
2. **One day per day.** Each file is 2–4 hours. Don't binge — the exercises are where the
   learning happens.
3. **Pick a lane, then peek at the other.** Read your language's code carefully and skim the
   other. Half the docs and job posts you'll meet are in the other language.
4. **Start each day with the 📖 "Words you'll meet today" box.** If a word in it is new, read its
   one-line meaning before you start. The [glossary](resources/glossary.md) has every term.
5. **Actually do the exercises.** Solutions are hidden in dropdowns — try first, then peek.
6. **Answer the interview questions out loud.** Explaining is the difference between "I've used
   it" and "I understand it".

### The structure of every day file

```
# Day NN — Topic
> ⏱ Time  ·  🎯 Prereqs  ·  🧩 Difficulty
📖 Words you'll meet today   ← the new terms, one plain line each

 1. The problem          ← a real-life story, zero jargon
 2. Mental model         ← a diagram you can draw from memory
 3. First principles     ← how it actually works (each part starts with 💬 "In plain words")
 4. Code — JavaScript
 5. Code — Python        ← same example, line-for-line comparable
 6. Under the hood       ← what the library is doing for you
 7. Common mistakes      ← ❌ wrong / ✅ right, with the real error text
 8. Exercises            ← with hidden solutions in both languages
 9. Interview questions  ← Basic / Intermediate / Advanced, with answers
10. Recap + what's next
```

---

## The course calendar

### ⚪ Week 0 — Start Here
*Goal: get every reader to the same starting line. Optional for working developers.*

| Day | Topic | |
|---|---|---|
| 0A | Your toolkit: terminal, git, Node, Python, `.env` and reading errors | [→](week-00-start-here/day-00a-your-toolkit.md) |
| 0B | Programming for AI: JSON, HTTP, async, Zod ↔ Pydantic | [→](week-00-start-here/day-00b-programming-for-ai.md) |
| 0C | Just-enough maths: vectors, probability, softmax, percentiles | [→](week-00-start-here/day-00c-just-enough-maths.md) |

### 🟢 Week 1 — How LLMs Work & LangChain Core
*Goal: understand what an LLM is, choose one on purpose, then build chains with LCEL.*

| Day | Topic | |
|---|---|---|
| 01 | LLMs, tokens, context windows, how a model is made, attention by intuition | [→](week-01-foundations/day-01-llms-tokens-and-inference.md) |
| 02 | Prompt engineering, reasoning models, talking to models with **no framework** | [→](week-01-foundations/day-02-prompt-engineering-and-raw-apis.md) |
| 03 | **Choosing a model** (price, speed, licence, your own eval) · why LangChain exists | [→](week-01-foundations/day-03-choosing-a-model-and-why-langchain.md) |
| 04 | LangChain models: `invoke` / `stream` / `batch`, every parameter, message types | [→](week-01-foundations/day-04-langchain-models.md) |
| 05 | Prompts: templates, chat templates, placeholders, few-shot | [→](week-01-foundations/day-05-prompts-and-templates.md) |
| 06 | Output parsers & structured output: **Zod ↔ Pydantic** | [→](week-01-foundations/day-06-output-parsers-structured-output.md) |
| 07 | **LCEL & Runnables** — the #1 interview topic · Week 1 project | [→](week-01-foundations/day-07-lcel-and-runnables.md) |

### 🔵 Week 2 — Data, Embeddings, RAG & Memory
*Goal: make the model answer questions about **your** documents.*

| Day | Topic | |
|---|---|---|
| 08 | Chains: sequential, parallel, router & **document chains** (prompt chaining, routing) | [→](week-02-data-embeddings-and-rag/day-08-chains.md) |
| 09 | Documents, loaders, splitting & chunking strategy | [→](week-02-data-embeddings-and-rag/day-09-documents-and-splitting.md) |
| 10 | Embeddings deep dive & similarity metrics (worked by hand) | [→](week-02-data-embeddings-and-rag/day-10-embeddings.md) |
| 11 | Vector databases: HNSW, metadata filters, **hybrid search** | [→](week-02-data-embeddings-and-rag/day-11-vector-databases.md) |
| 12 | **Naive RAG end-to-end** — then break it six ways on purpose | [→](week-02-data-embeddings-and-rag/day-12-naive-rag.md) |
| 13 | Advanced RAG: reranking, HyDE, multi-query, Corrective/Self/Adaptive | [→](week-02-data-embeddings-and-rag/day-13-advanced-rag.md) |
| 14 | Memory — and context engineering · Week 2 project | [→](week-02-data-embeddings-and-rag/day-14-memory.md) |

### 🟠 Week 3 — Tools, Agents & LangGraph
*Goal: build things that decide, act, loop, and can be paused for a human.*

| Day | Topic | |
|---|---|---|
| 15 | Tools: creating, calling, schemas, errors, retries | [→](week-03-tools-agents-and-langgraph/day-15-tools.md) |
| 16 | Agents from first principles — hand-build ReAct in 40 lines | [→](week-03-tools-agents-and-langgraph/day-16-agents.md) |
| 17 | LangGraph basics: `StateGraph`, nodes, edges, compile, visualise | [→](week-03-tools-agents-and-langgraph/day-17-langgraph-basics.md) |
| 18 | State & reducers · state vs memory vs context vs store vs checkpoint | [→](week-03-tools-agents-and-langgraph/day-18-state-and-reducers.md) |
| 19 | Conditional edges, loops, `Command`, `Send` (orchestrator-workers), subgraphs | [→](week-03-tools-agents-and-langgraph/day-19-control-flow.md) |
| 20 | Persistence & checkpointing, threads, time travel | [→](week-03-tools-agents-and-langgraph/day-20-persistence-and-checkpointing.md) |
| 21 | Human-in-the-loop: `interrupt`, resume, approve/reject/edit · Week 3 project | [→](week-03-tools-agents-and-langgraph/day-21-human-in-the-loop.md) |

### 🔴 Week 4 — Multi-agent, Production & the Halfway Capstone
*Goal: ship it, watch it, and talk about it convincingly.*

| Day | Topic | |
|---|---|---|
| 22 | Multi-agent: supervisor, hierarchical, handoffs — and when it backfires | [→](week-04-production-projects-and-interviews/day-22-multi-agent.md) |
| 23 | Streaming & events: stream modes, token streaming to a UI, SSE | [→](week-04-production-projects-and-interviews/day-23-streaming-and-events.md) |
| 24 | Reliability: retries, fallbacks, timeouts, circuit breakers, guardrails | [→](week-04-production-projects-and-interviews/day-24-reliability.md) |
| 25 | Observability & evaluation: LangSmith, datasets, LLM-as-judge, RAG metrics | [→](week-04-production-projects-and-interviews/day-25-observability-and-evaluation.md) |
| 26 | **MCP** (servers, clients, transports, security) + **Vercel AI SDK** compared | [→](week-04-production-projects-and-interviews/day-26-mcp-and-ai-sdk.md) |
| 27 | Deployment & architecture: Docker, serverless, queues, scaling to 1M users | [→](week-04-production-projects-and-interviews/day-27-deployment-and-architecture.md) |
| 28 | **Halfway capstone** — 12 projects + interview crash course | [→](week-04-production-projects-and-interviews/day-28-capstones-and-interviews.md) |

### 🟣 Week 5 — The Model Layer
*Goal: go below the API — run, serve, fine-tune, feed, and secure models yourself.*

| Day | Topic | |
|---|---|---|
| 29 | Open & local models: model files, quantisation, run AI on your own machine | [→](week-05-the-model-layer/day-29-open-and-local-models.md) |
| 30 | Inference & serving: prefill vs decode, KV cache, batching, your own OpenAI-compatible server | [→](week-05-the-model-layer/day-30-inference-and-serving.md) |
| 31 | Fine-tuning: when (and when not), LoRA, train an adapter on a CPU | [→](week-05-the-model-layer/day-31-fine-tuning.md) |
| 32 | Dataset engineering: dedupe, PII, synthetic data, leak-free splits | [→](week-05-the-model-layer/day-32-dataset-engineering.md) |
| 33 | Multimodal: images, documents and voice | [→](week-05-the-model-layer/day-33-multimodal.md) |
| 34 | Cost & latency: caching, routing, budgets | [→](week-05-the-model-layer/day-34-cost-and-latency.md) |
| 35 | AI security: OWASP Top 10 for LLM apps, red-teaming, supply chain | [→](week-05-the-model-layer/day-35-ai-security.md) |

### ⚫ Week 6 — Advanced Agents, Product & Career
*Goal: design agents like experienced teams do, build a product people trust, and prove it.*

| Day | Topic | |
|---|---|---|
| 36 | Context engineering & the five agent patterns | [→](week-06-advanced-agents-product-and-career/day-36-context-engineering-and-agent-patterns.md) |
| 37 | Advanced retrieval: knowledge graphs/GraphRAG, guarded text-to-SQL, agentic search | [→](week-06-advanced-agents-product-and-career/day-37-advanced-retrieval.md) |
| 38 | Emerging agents: browser and computer use, A2A, agent skills | [→](week-06-advanced-agents-product-and-career/day-38-emerging-agents.md) |
| 39 | AI product engineering: UX, feedback, A/B tests, responsible AI, EU AI Act | [→](week-06-advanced-agents-product-and-career/day-39-ai-product-engineering.md) |
| 40 | **Final capstone & career** — ship it, prove it, get hired | [→](week-06-advanced-agents-product-and-career/day-40-final-capstone-and-career.md) |

---

## Reference material

| File | What's in it |
|---|---|
| [SETUP.md](SETUP.md) | Free API keys, Node & Python environments, `.env`, verification script |
| [resources/glossary.md](resources/glossary.md) | Every term in the course, one plain line each |
| [resources/cheatsheet-lcel.md](resources/cheatsheet-lcel.md) | Runnables at a glance |
| [resources/cheatsheet-langgraph.md](resources/cheatsheet-langgraph.md) | Graph API at a glance |
| [resources/cheatsheet-rag-patterns.md](resources/cheatsheet-rag-patterns.md) | Which RAG pattern for which problem |
| [resources/js-vs-python-mapping.md](resources/js-vs-python-mapping.md) | Every API, JS name ↔ Python name, day by day |
| [resources/interview-bank.md](resources/interview-bank.md) | Every interview question in the course, with model answers |
| [resources/capstone-projects.md](resources/capstone-projects.md) | 12 project specs, tiers and a skills matrix |
| [resources/troubleshooting.md](resources/troubleshooting.md) | Exact error text → cause → fix, plus silent failures |

### For maintainers of this course

| File | What's in it |
|---|---|
| [KB/README.md](KB/README.md) | The knowledge base: how to pick this course up and change it correctly |
| [KB/03-verified-findings.md](KB/03-verified-findings.md) | Every behaviour that was verified by running it, with the evidence |
| [KB/07-course-expansion-plan.md](KB/07-course-expansion-plan.md) | How the 28-day book became this 43-day course, and why |
| [CONTRIBUTING.md](CONTRIBUTING.md) | The rules any contributor (human or AI) follows here |
| `tools/verify.py` | Links, structure, language parity and stats for the whole repo |
| `tools/readability.py` | How easy each day is to read (Flesch score, long sentences) |
| `tools/check_code_unchanged.py` | Proves a prose edit didn't touch any code |
| `tools/gen_resources.py` | Regenerates the three generated reference files from the day files |

---

## The running project: **StudyBuddy**

Rather than 43 disconnected toy examples, one product grows through the whole course:

```
Week 0  v0     an empty, correctly configured JS + Python project              (Day 0A)
Week 1  v1.0   parallel analysis · routing · streaming · retries                (Day 07)
Week 2  v2.0   reads your documents · verified citations · conversational       (Day 12)
        v3.0   memory across sessions · reranking                              (Day 14)
Week 3  v3.5   tools: calculator, search, progress DB                          (Day 16)
        v4.0   a LangGraph agent · persistence · approval before any write     (Day 21)
Week 4  v5.x   team of agents · streamed · reliable · traced · MCP             (Days 22–26)
        v6.0   production architecture for 100k students                       (Day 27)
Week 5  v6.1–v6.7  offline local model · own server · fine-tuned habit ·
                   clean data · reads photos and voice · cached & budgeted ·
                   red-team suite in CI                                         (Days 29–35)
Week 6  v7.0–v7.3  simplest-pattern router · graph + SQL answers ·
                   browser helper with approval · feedback & A/B tests          (Days 36–39)
        v8.0   🏆 the final capstone: one command runs evals, red-team, cost and latency
```

Every day you add one capability to something real.

---

## Versions this course targets

| Thing | Version | Note |
|---|---|---|
| LangChain (Python / JS) | `langchain` **1.x** | `pip install langchain` / `npm install langchain` |
| LangGraph | **1.x** (both languages) | ships with `langchain` 1.x |
| Node.js | **20+** | ESM, top-level `await`; verified on 24.15 |
| Python | **3.10+** | modern typing syntax; verified on 3.14 |
| Default models | Groq `openai/gpt-oss-120b` (small: `openai/gpt-oss-20b`) · Google `gemini-3.8-flash`, embeddings `gemini-embedding-2` · Ollama `llama3.2`, `nomic-embed-text` | checked live on **7 October 2026** — model names change; see [SETUP.md](SETUP.md) |

Exact versions for every package are in [KB/04](KB/04-versions-and-environment.md).

> ⚠️ **Version warning.** LangChain changed a *lot* between 0.x and 1.x. Old blog posts will
> show you `LLMChain`, `initialize_agent` and `ConversationBufferMemory` — those are legacy.
> This course teaches the modern API, and marks legacy patterns so you still recognise them in
> interviews and old codebases.

---

## A note on cost

You can complete **the whole course for free**:

- **Groq** — free tier, very fast, our default chat provider (GPT-OSS reasoning models; free tier ≈ 30 requests and 8,000 tokens per minute per model)
- **Google Gemini** — generous free tier, our fallback + free embeddings
- **Ollama / Hugging Face** — models on your own laptop, fully offline, $0 forever (Week 5)
- **Chroma / FAISS / SQLite** — local storage, no cloud account
- **Scripted models** — from Week 3 on, most examples run with no API key at all

Paid options (OpenAI, Anthropic, Pinecone) appear in collapsed `<details>` blocks so you know
the production path, but you never *need* them.

---

Start here → 🟢 **[Week 0](week-00-start-here/README.md)** · 🔵 **[SETUP.md](SETUP.md) → [Day 01](week-01-foundations/day-01-llms-tokens-and-inference.md)**
