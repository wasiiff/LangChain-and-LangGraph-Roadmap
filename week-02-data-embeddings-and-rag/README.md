# Week 2 — Data, Embeddings, RAG & Memory

> **Goal:** take a folder of your own documents and build a system that answers questions from
> them — with citations, honestly refusing when it doesn't know, and remembering you across
> sessions.

← [Back to the main index](../README.md) · [Week 1](../week-01-foundations/README.md)

---

## The week at a glance

| Day | Topic | Time | Difficulty | You'll build |
|---|---|---|---|---|
| [08](day-08-chains.md) | Chains: sequential, parallel, router, **document chains** | 2.5h | ●●○○○ | Auto-strategy document Q&A |
| [09](day-09-documents-and-splitting.md) | Documents, loaders, splitting & chunking strategy | 2.5h | ●●○○○ | **A chunk-size eval harness** |
| [10](day-10-embeddings.md) | Embeddings, similarity metrics, model choice | 2.5h | ●●●○○ | A semantic search engine, no DB |
| [11](day-11-vector-databases.md) | Vector DBs, HNSW/IVF, filtering, **hybrid search** | 2.5h | ●●●○○ | A production document store |
| [12](day-12-naive-rag.md) | **Naive RAG end-to-end** + six ways to break it | 3h | ●●●○○ | StudyBuddy v2 — chat with PDFs |
| [13](day-13-advanced-rag.md) | Reranking, HyDE, multi-query, corrective & self-RAG | 3h | ●●●●○ | A configurable RAG pipeline |
| [14](day-14-memory.md) | Memory: buffer, summary, entity, vector · Week project | 2.5h | ●●●○○ | 🏆 **StudyBuddy v3** |

**Total: ~19 hours.**

---

## What you'll be able to do by Sunday

- [ ] Choose between stuff, map-reduce, refine and map-rerank — and know why stuff usually wins
- [ ] Split documents without destroying tables, code blocks or headings
- [ ] Pick chunk size by **measuring recall**, not by guessing
- [ ] Explain what an embedding is and compute cosine similarity by hand
- [ ] Choose an embedding model deliberately, and know why you can never mix two
- [ ] Explain HNSW, `ef`, and the recall/latency trade-off you're choosing
- [ ] Diagnose the pre-filter vs post-filter bug before it starves your smallest tenant
- [ ] Build hybrid search (vectors + BM25 + RRF) and know exactly which failure it fixes
- [ ] Build RAG end-to-end with verified citations and an honest refusal path
- [ ] **Separate retrieval failures from generation failures** — the core debugging skill
- [ ] Add reranking, multi-query, HyDE and corrective loops, and justify each one's cost
- [ ] Implement memory that survives restarts and handles contradictions

---

## The through-line

Each day exists because the previous day created a problem:

```
Day 08  Map-reduce over 200 chunks to answer 1 question   → absurdly wasteful
Day 09  So retrieve instead — but naive splitting         → breaks tables & headings
Day 10  Fix splitting; now compare meaning not keywords   → but O(n) scan, no persistence
Day 11  Add a vector DB + hybrid search                   → now assemble the pipeline
Day 12  Full RAG with citations                           → retrieves once and hopes
Day 13  Reranking, rewriting, corrective loops            → but forgets you every session
Day 14  Memory across sessions                            → and the loops are painful  →  Week 3
```

That last friction — **you hand-write a state machine four times in Days 13–14** — is the door
into LangGraph.

---

## 🚨 The version trap (read this first)

In LangChain **1.x**, the legacy chains, retrievers, memory and some vector stores moved into a
separate package. Most tutorials online still use the old paths, which **no longer exist**:

| ❌ Old (0.x — will fail) | ✅ New (1.x) |
|---|---|
| `from "langchain/chains"` | `from "@langchain/classic/chains"` |
| `from "langchain/vectorstores/memory"` | `from "@langchain/classic/vectorstores/memory"` |
| `from "langchain/retrievers/..."` | `from "@langchain/classic/retrievers/..."` |
| `from langchain.chains import ...` | `from langchain_classic.chains import ...` |
| `from langchain.retrievers import ...` | `from langchain_classic.retrievers import ...` |

```bash
npm install @langchain/classic
pip install langchain-classic
```

**Every import in this book was verified by actually importing it** against
`langchain@1.5.10` / `@langchain/core@1.2.9` and `langchain==1.3.17` / `langchain-classic==1.0.8`.

One useful asymmetry: **Python's `InMemoryVectorStore` ships in `langchain-core`** (no extra
install), and **Chroma persists to a directory without a server**. In JS you need
`@langchain/classic` and a running Chroma process.

---

## Extra installs for this week

```bash
# JavaScript
npm install @langchain/classic @langchain/textsplitters @langchain/ollama \
            @langchain/community chromadb

# Python
pip install langchain-classic langchain-text-splitters langchain-ollama \
            langchain-chroma

# Free local embeddings (recommended — Groq has no embeddings endpoint)
ollama pull nomic-embed-text
```

> ⚠️ **Groq does not offer embeddings.** From Day 10 onward, embeddings come from **Ollama**
> (`nomic-embed-text`, local and free) or **Google** (`text-embedding-004`, free tier). Chat still
> uses Groq.
>
> Python needs the `models/` prefix for Google embeddings (`"models/text-embedding-004"`); JS
> does not. This catches people porting code.

---

## Common Week 2 blockers

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

---

## Interview topics covered this week

Ranked by how often they come up:

1. **The RAG pipeline end to end** (Day 12) — the most-asked applied question in AI interviews
2. **Chunking strategy and how you choose chunk size** (Day 09) — "measure recall" is the answer
3. **Embeddings, cosine vs euclidean, why you can't mix models** (Day 10)
4. **Reranking: bi-encoder vs cross-encoder** (Day 13) — the highest-signal advanced answer
5. **Hybrid search and why embeddings fail on identifiers** (Day 11)
6. **How you evaluate RAG** (Day 12) — separating retrieval from generation
7. **HNSW, ANN, recall/latency trade-offs** (Day 11)
8. **How memory changed in LangChain and why** (Day 14)
9. **Document chain strategies** (Day 08)

---

## StudyBuddy — the running project

```
Week 1  v1.0   parallel analysis · routing · streaming · retries
Day 12  v2.0   + reads YOUR documents · verified citations · conversational
Day 14  v3.0   🏆 + memory across sessions · reranking · memory-enriched retrieval
```

Next week it gets tools and starts deciding for itself.

---

→ Start with **[Day 08](day-08-chains.md)**
