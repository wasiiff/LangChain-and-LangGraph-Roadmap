# Cheat Sheet — RAG Patterns

Which pattern for which problem, at a glance. Every import here was verified against
`langchain@1.5.10` / `@langchain/core@1.2.9` and `langchain==1.3.17` / `langchain-classic==1.0.8`.

← [Back to the main index](../README.md) · [Week 2](../week-02-data-embeddings-and-rag/README.md)

---

## 🚨 Import paths in LangChain 1.x

Legacy chains, retrievers and memory live in a **separate package**.

```bash
npm install @langchain/classic
pip install langchain-classic
```

| What | JavaScript | Python |
|---|---|---|
| Document | `@langchain/core/documents` | `langchain_core.documents` |
| Splitters | `@langchain/textsplitters` | `langchain_text_splitters` |
| In-memory store | `@langchain/classic/vectorstores/memory` → `MemoryVectorStore` | `langchain_core.vectorstores` → `InMemoryVectorStore` ✅ no extra install |
| Chroma | `@langchain/community/vectorstores/chroma` | `langchain_chroma` |
| Loaders (PDF/CSV/web) | `@langchain/community/document_loaders/...` ⚠️ needs peer deps | `langchain_community.document_loaders` |
| Loaders (text/json/dir) | `@langchain/classic/document_loaders/fs/...` | `langchain_community.document_loaders` |
| Retrievers | `@langchain/classic/retrievers/<name>` | `langchain_classic.retrievers` |
| Compressors | `@langchain/classic/retrievers/document_compressors/<name>` | `langchain_classic.retrievers.document_compressors` |
| Doc chains | `@langchain/classic/chains/combine_documents` | `langchain_classic.chains.combine_documents` |
| Retrieval chain | `@langchain/classic/chains/retrieval` | `langchain_classic.chains.retrieval` |
| Byte store | `@langchain/classic/storage/in_memory` → `InMemoryStore` | `langchain_core.stores` → `InMemoryByteStore` |
| Embeddings cache | `@langchain/classic/embeddings/cache_backed` | `langchain_classic.embeddings` |

---

## The decision tree

```
Does the answer fit in one context window?
├─ YES → STUFF. Stop. Don't overthink it.
└─ NO  → Do you need to process EVERY document?
         ├─ YES → summarising a whole corpus?
         │        ├─ need a synthesis → MAP-REDUCE (parallel, fast)
         │        └─ need every detail → REFINE (serial, slow, preserves context)
         └─ NO  → RAG: retrieve the few that matter, then STUFF them
                  │
                  └─ retrieval not good enough?
                     ├─ misses exact codes/names  → HYBRID SEARCH
                     ├─ right chunk in top-20 not top-4 → RERANK
                     ├─ top-k are near-duplicates → MMR or dedupe at ingest
                     ├─ query phrased unlike docs → MULTI-QUERY or HyDE
                     ├─ follow-up questions fail  → QUERY REWRITING
                     ├─ needs numeric/date filters → SELF-QUERY
                     ├─ chunks too small to answer → PARENT-DOCUMENT
                     └─ retrieval quality varies   → CORRECTIVE RAG
```

---

## Document chains (Day 08)

| Strategy | Calls | Speed | Cross-doc reasoning | Use for |
|---|---|---|---|---|
| **Stuff** | 1 | fastest | ✅ full | **Default.** Anything that fits |
| Map-reduce | N+1 | parallel | ❌ limited | Summarising a whole corpus |
| Refine | N | serial (slow) | ✅ good | Chronologies, running analysis |
| Map-rerank | N | parallel | ❌ none | Find one fact in one document |

```python
# The only helper that survives in 1.x
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
chain = create_stuff_documents_chain(model, prompt)   # prompt needs {context}
chain.invoke({"input": question, "context": docs})    # note: input + context
```
```js
import { createStuffDocumentsChain } from "@langchain/classic/chains/combine_documents";
const chain = await createStuffDocumentsChain({ llm: model, prompt });   // ← await
```

**Recursive reduce** (map-reduce that never overflows): batch by *token budget*, give any
oversized item its own batch, short-circuit when everything already fits.

---

## Chunking (Day 09)

| Content | Size | Overlap | Note |
|---|---|---|---|
| Prose / articles | 800–1000 chars | 100–200 | Paragraphs are the unit |
| Technical docs | 500–800 | 100 | Dense; precision matters |
| Code | 800–1500 | 0–100 | Use `fromLanguage` / `from_language` |
| FAQ / Q&A | 1 per pair | 0 | Already semantic |
| Legal | 1 per clause | 0–50 | Clauses are self-contained |
| CSV rows | 1 per row | 0 | Already atomic |

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter
splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
chunks = splitter.split_documents(docs)     # split_documents keeps metadata!
```

**Rules:**
- `chunkSize` is a **maximum**, not a target — smaller chunks are normal
- `CharacterTextSplitter` silently exceeds `chunkSize` — avoid it
- **Inject header breadcrumbs into chunk text** — highest-ROI fix for structured docs
- `splitDocuments` keeps metadata; `splitText` discards it
- Choose size by **measuring recall@k**, not by feel

---

## Embeddings (Day 10)

| Model | Dims | Cost | Note |
|---|---|---|---|
| `nomic-embed-text` (Ollama) | 768 | free, local | **Default for this book** |
| `text-embedding-004` (Google) | 768 | free tier | Python needs `models/` prefix |
| `text-embedding-3-small` (OpenAI) | 1536 | $0.02/1M | Strong baseline |
| `text-embedding-3-large` (OpenAI) | 3072 | $0.13/1M | Best general purpose |
| `BGE-M3` | 1024 | free, local | Multilingual |

```
cosine     = A·B / (|A||B|)      angle only         ← the default
euclidean  = √Σ(aᵢ-bᵢ)²          distance
dot        = Σ aᵢbᵢ              angle + magnitude  ← fastest

For NORMALISED vectors: cosine == dot, and euclidean gives the SAME RANKING.
```

**Rules:**
- Never mix models in one index — namespace embedding caches by model name
- `embedDocuments` for bulk (batched, applies document-side prefixes); `embedQuery` for queries
- Long chunks **dilute** via pooling and **truncate silently** past the context limit
- Unrelated text scores ~0.4, not 0 — rank relatively, don't copy absolute thresholds
- Embeddings fail on: exact identifiers, negation, numeric comparison → hybrid + self-query

---

## Vector stores (Day 11)

| Store | Persistence | Pre-filters? | Best for |
|---|---|---|---|
| In-memory | ❌ | function filter | Tests, <10k |
| Chroma | ✅ | ✅ | Local dev, small prod |
| Qdrant | ✅ | ✅ excellent | Self-hosted production |
| **pgvector** | ✅ | ✅ SQL | **Already have Postgres? Use this** |
| Pinecone | ✅ | ✅ | Zero ops |
| Weaviate | ✅ | ✅ | Native hybrid search |

```python
from langchain_core.vectorstores import InMemoryVectorStore    # no extra install
store = InMemoryVectorStore.from_documents(docs, embeddings)
retriever = store.as_retriever(search_kwargs={"k": 4})
```
```js
import { MemoryVectorStore } from "@langchain/classic/vectorstores/memory";
const store = await MemoryVectorStore.fromDocuments(docs, embeddings);
const retriever = store.asRetriever({ k: 4 });
```

**Index tuning:**

| Index | Dial | Rule |
|---|---|---|
| HNSW | `ef` / `efSearch` | Must be ≥ `k`; use `2×k` minimum. Sweep it against measured recall |
| HNSW | `M` | ↑ recall, ↑ memory |
| IVF | `nprobe` | ↑ recall, ↑ latency. `nlist ≈ √N` |

**Pre-filter vs post-filter:** post-filtering returns *fewer results than you asked for*, worst
for your most selective filters. Verify your store, over-fetch by ~`1/selectivity`, or —
best for multi-tenancy — **partition into separate collections**.

---

## Hybrid search (Day 11)

Fixes the one thing embeddings genuinely cannot do: exact identifiers.

```
RRF_score(doc) = Σ over ranked lists  1 / (k + rank)        k ≈ 60
```

Fuse **ranks**, not scores — cosine (0–1) and BM25 (unbounded) are incomparable scales.

```python
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers import EnsembleRetriever

hybrid = EnsembleRetriever(
    retrievers=[BM25Retriever.from_documents(docs), store.as_retriever()],
    weights=[0.5, 0.5],
)
```

---

## The RAG pipeline (Day 12)

```python
from langchain_core.runnables import RunnableParallel, RunnablePassthrough

rag = (
    RunnableParallel(docs=retriever, question=RunnablePassthrough())
    .assign(context=lambda x: format_docs(x["docs"]))
    .assign(answer=prompt | model | StrOutputParser())
)
```

**The grounding contract — all four rules:**

```
1. Use ONLY the context below. Never use outside knowledge.
2. Cite every claim as [1], [2].
3. If the context lacks the answer, reply exactly:
   "I don't have that information in the provided documents."
4. Never invent a citation number.
```

Rule 3 needs an **exact phrase** — "say you don't know" is far less reliable. Better still, a
structured `answerFound: boolean` you branch on in code.

**Verify citations:** ask for the verbatim quote, then check it appears in that chunk. Classify:

| Status | Meaning | Action |
|---|---|---|
| VERIFIED | exact match | show |
| PARAPHRASED | reworded | usually fine |
| WRONG_SOURCE | right quote, wrong number | renumber |
| FABRICATED | appears nowhere | **suppress or flag** |

**`k` = 3–6.** Larger triggers lost-in-the-middle.

---

## Advanced retrieval (Day 13)

| Technique | Extra cost | Gain | Use when |
|---|---|---|---|
| **Hybrid search** | ~0 | ⭐⭐⭐ | Always |
| **Reranking** | 1 call | ⭐⭐⭐ | Almost always — biggest single win |
| MMR | ~0 | ⭐⭐ | Redundant corpora |
| Multi-query | 1 call | ⭐⭐ | Short/vague queries |
| HyDE | 1 call | ⭐⭐ | Technical domains, query/doc mismatch |
| Parent-document | storage | ⭐⭐ | Chunks too small to answer from |
| Compression | N calls | ⭐ | Long chunks, tight budget |
| Self-query | 1 call | ⭐⭐⭐ | Numeric/categorical filters |
| Corrective RAG | 1–3 calls | ⭐⭐ | Inconsistent retrieval |

> **Do only two things: hybrid search + reranking.**

```
RETRIEVE WIDE (20)  ──▶  RERANK NARROW (4)  ──▶  prompt
bi-encoder, ~10ms        cross-encoder, ~200ms
```

Bi-encoder embeds query and doc *separately* (scales); cross-encoder sees them *together*
(accurate). Reranking 4→4 is pointless — the value is **selection**, not ordering.

```python
from langchain_classic.retrievers import ContextualCompressionRetriever
from langchain_classic.retrievers.document_compressors import EmbeddingsFilter

retriever = ContextualCompressionRetriever(
    base_compressor=EmbeddingsFilter(embeddings=embeddings, similarity_threshold=0.55),
    base_retriever=store.as_retriever(search_kwargs={"k": 20}),
)
```

**MMR needs `fetchK` ≫ `k`** or it's a no-op. And recall is the *wrong metric* for MMR — it
optimises diversity.

---

## Adaptive patterns (Day 13)

```
CORRECTIVE   retrieve → grade DOCS → bad? rewrite query, retry → still bad? fall back
SELF-RAG     generate → grade ANSWER
                        ├─ ungrounded  → REGENERATE (same docs, stricter prompt)
                        └─ not useful  → RE-RETRIEVE (new query)
ADAPTIVE     classify first → route: no-retrieval | simple | multi | filtered
AGENTIC      the model decides whether/what/how often to search  → Week 3
```

**Every loop needs:** a hard attempt cap, previously-tried queries fed to the rewriter, and a
terminal fallback. Use the **cheap model** for graders and rewriters.

The two Self-RAG grades imply **different actions** — conflating them wastes retrievals on
hallucinations.

---

## Memory (Day 14)

| Strategy | Cost | Recall | Use when |
|---|---|---|---|
| Buffer | O(n²) | perfect | <10 turns |
| Window(N) | bounded | recent only | Simple bots |
| `trimMessages` | bounded | recent only | Token-budget control |
| **Summary + buffer** | bounded | good | **Default for long chats** |
| Entity/fact | tiny | permanent | Cross-session personalisation |
| Vector | constant | selective | Users reference old conversations |

```python
from langchain_core.messages import trim_messages

trimmed = trim_messages(
    history, max_tokens=800, strategy="last", token_counter=model,
    include_system=True, start_on="human",   # ← prevents provider 400s
)
```

**The three-layer architecture:**

```
SHORT  last ~6 messages verbatim      → conversational coherence
MID    rolling summary                → "we discussed X, decided Y"
LONG   structured facts in a DB       → survives sessions, can't drift
```

**Rules:**
- Progressive summarisation **drifts** — keep hard facts structured, not in prose
- Contradictions must **replace**, not append
- Store the whole **exchange** in vector memory, not single messages
- Key everything by session ID — no shared mutable state
- Persist every turn, not on exit
- The 0.x `Memory` classes were removed for hidden state, concurrency bugs and no persistence

---

## Debugging RAG — the one diagnostic that matters

```
For each failing question: WAS THE CORRECT CHUNK RETRIEVED?

NOT RETRIEVED → retrieval problem
  1. Is the answer in a chunk INTACT, or split across a boundary?   (Day 09)
  2. Did the chunk lose its heading?                                (Day 09)
  3. Is the query lexical — codes, names, IDs?                      (Day 11 hybrid)
  4. Phrasing gap between query and docs?                           (Day 13 rewrite/HyDE)
  5. Filters over-restricting, or post-filtering?                   (Day 11)
  6. Near-duplicates crowding top-k?                                (Day 10/13)

RETRIEVED BUT WRONG ANSWER → generation problem
  1. Buried mid-context? → smaller k, or rerank                     (Day 12)
  2. Grounding instruction present and specific?                    (Day 12)
  3. Model overriding context? → verify citations                   (Day 12)
  4. Context formatted so chunks are distinguishable?               (Day 08)
```

**Retrieval recall is an upper bound on answer accuracy.** At 65% recall, no prompt engineering
gets you past 65%. Measure the two halves separately or you'll tune the prompt for a week while
the real problem is chunking.

Every diagnosed failure becomes a permanent eval case.

---

## Cost reference

| Operation | Rough cost |
|---|---|
| Embedding 1M chunks (OpenAI 3-small) | ~$10 one-off |
| Embedding 1M chunks (Ollama) | $0 + GPU time |
| Storage, 1M × 768 dims float32 | ~3 GB (+ index overhead) |
| Storage, 1M × 3072 dims float32 | ~12 GB |
| One RAG query (k=4, 70B answer) | ~$0.001–0.005 |
| Adding LLM reranking (20 docs) | ~10–20× the query cost ⚠️ |
| Adding hosted reranking (Cohere) | ~1 extra API call, ~200ms |

**Use the cheap model for grading, reranking, rewriting and fact extraction. Reserve the strong
model for the final answer.**
