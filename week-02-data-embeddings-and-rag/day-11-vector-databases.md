# Day 11 — Vector Databases: Indexes, Filtering & Hybrid Search

> ⏱ **Time:** ~2.5 hours · 🎯 **Prereqs:** [Day 10](day-10-embeddings.md) · 🧩 **Difficulty:** ●●●○○

**Today you learn:** why exact search stops working, how HNSW and IVF make search sub-linear,
the recall/latency trade-off you're actually choosing, how to compare the major vector stores,
metadata filtering done properly — and **hybrid search**, the fix for yesterday's `ERR_4471`
problem.

---

## 1. The problem

Yesterday's search engine works. Here's what happens when it grows:

```
   corpus size    vectors scanned    time per query
   ───────────    ───────────────    ──────────────
        1,000              1,000            ~3 ms     ✅ fine
       50,000             50,000          ~150 ms     😐 noticeable
    1,000,000          1,000,000        ~3,000 ms     ❌ unusable
   50,000,000         50,000,000      ~150,000 ms     💀
```

Every query compares against **every** vector. That's O(n), and it never gets better.

And there are three more problems you can't fix with faster maths:

```
   ❌ Restart the process → your entire index is gone
   ❌ Add one document    → you rebuild the whole thing
   ❌ Filter by tenant    → you scan everything, THEN filter
```

That last one is a security issue, not just a performance one. If you scan all tenants' vectors
and filter afterwards, a bug in the filter is a data leak.

**A vector database solves all four.** Today you learn how, and — more usefully — what it costs
you in exchange.

---

## 2. Mental model

### The core trade: exact vs approximate

```
   EXACT (brute force)                 APPROXIMATE (ANN)
   ──────────────────                  ─────────────────
   compare against ALL n vectors       compare against ~log(n) vectors

   100% recall, guaranteed             95-99% recall, tunable
   O(n) — hopeless at scale            O(log n) — scales to billions
   no index to build                   index build takes time + RAM

   ✅ use under ~10k vectors            ✅ use above that
```

**"Approximate" means you may miss a true nearest neighbour.** For retrieval that's almost always
fine — if the 5th-best chunk is returned instead of the 4th-best, your answer is unchanged. It
matters far more for exact-match use cases like deduplication.

### HNSW — the index you'll actually use

Hierarchical Navigable Small World. The mental model is **express trains and local trains**:

```
   layer 2   ●───────────────────────●              few nodes, long hops
              \                     /
   layer 1   ●───●─────────●───────●───●            more nodes, medium hops
              \   \       /       /   /
   layer 0   ●─●─●─●─●─●─●─●─●─●─●─●─●─●            ALL nodes, short hops

   SEARCH:
   1. Enter at the top layer, greedily walk toward the query
   2. Drop a layer, walk again — now with finer resolution
   3. Repeat to layer 0, collect the best neighbours found

   You visit ~hundreds of nodes, not millions.
```

The key parameters:

| Parameter | What it does | Effect |
|---|---|---|
| `M` | edges per node | ↑ better recall, ↑ memory |
| `efConstruction` | candidates considered while *building* | ↑ better index, ↑ build time |
| `ef` / `efSearch` | candidates considered while *searching* | ↑ better recall, ↑ query latency |

**`ef` is the one you tune at runtime.** It's the recall/latency dial, and it must be ≥ your `k`.

### IVF — the other common index

Inverted File. Cluster the vectors, then only search the nearest clusters:

```
   BUILD: k-means the vectors into `nlist` clusters
   ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐
   │ ● ● ● │ │ ● ● ● │ │ ● ● ● │ │ ● ● ● │   nlist = 4 clusters
   │  ● ●  │ │  ● ●  │ │  ● ●  │ │  ● ●  │
   └───────┘ └───────┘ └───────┘ └───────┘

   SEARCH: find the `nprobe` nearest cluster CENTROIDS, search only those
                     ▲                        ▲
                     └── nprobe=1: fast, may miss
                         nprobe=4: slower, better recall
```

**HNSW vs IVF:** HNSW has better recall/latency and needs no training, but uses more memory and
is slower to build. IVF is more memory-efficient and better for very large static datasets, but
needs a training step on a sample. **Default to HNSW** unless memory is your binding constraint.

### Hybrid search — the fix for yesterday's failure

```
   query: "ERR_4471 rate limit"

   VECTOR SEARCH                  KEYWORD SEARCH (BM25)
   ─────────────                  ─────────────────────
   ERR_4472 doc   0.97  ❌         ERR_4471 doc   8.2  ✅
   ERR_4471 doc   0.96            ERR_4472 doc   0.0
   rate limit doc 0.91  ✅         rate limit doc 3.1  ✅

                    │        │
                    └────┬───┘
                         ▼
                    FUSE (RRF)
                         ▼
              ERR_4471 doc  ✅ correct
              rate limit doc
              ERR_4472 doc
```

Vectors find meaning; keywords find exact strings. **Real systems use both.**

---

## 3. First principles

### 3.1 What a vector database gives you

| Capability | Why you can't easily hand-roll it |
|---|---|
| **ANN index** | HNSW is a real algorithm with real edge cases |
| **Persistence** | Survives restarts, no re-embedding |
| **Incremental writes** | Add/update/delete one document without a rebuild |
| **Metadata filtering** | Filter *inside* the index, not after |
| **Scale** | Sharding, replication, memory-mapped storage |
| **Concurrency** | Safe reads during writes |

### 3.2 Pre-filter vs post-filter — the detail that matters

This is the most important implementation detail in vector search, and it's usually invisible
until it bites.

```
   POST-FILTER (naive)                    PRE-FILTER (correct)
   ───────────────────                    ────────────────────
   1. ANN search → top 10                 1. Restrict the search to
   2. drop those failing the filter          matching vectors
   3. return what's left                  2. ANN search within those
                                          3. return top 10

   ask for k=10 with filter tenant=A      ask for k=10 with filter tenant=A
   → search returns 10 mixed tenants      → search returns 10 from tenant A
   → 9 belong to tenant B                 → correct
   → you return 1 result 😱               ✅
```

Post-filtering silently returns **fewer results than you asked for**, and gets worse as the
filter gets more selective. If your filter matches 1% of documents, a top-10 search returns
roughly *zero* usable results.

**Workarounds if your store post-filters:** over-fetch (ask for `k * 20` then filter), or
partition into separate collections per tenant. Qdrant, Weaviate and pgvector do proper
pre-filtering; check your store's docs rather than assuming.

> 🚨 **The multi-tenant rule:** never rely on filtering alone for tenant isolation if you can
> partition instead. A separate collection per tenant makes cross-tenant leakage structurally
> impossible rather than one bug away.

### 3.3 The stores compared

| Store | Type | Persistence | Best for | Watch out |
|---|---|---|---|---|
| **In-memory** | library | ❌ none | Tests, demos, <10k | Gone on restart |
| **FAISS** | library | file | Fast local, research | No metadata filtering built in |
| **Chroma** | embedded/server | ✅ | **Local dev, small prod** | Not built for huge scale |
| **Qdrant** | server | ✅ | **Production, self-host** | Needs Docker |
| **pgvector** | Postgres ext | ✅ | **You already have Postgres** | Slower than dedicated at scale |
| **Pinecone** | managed | ✅ | Zero ops, scale | Paid, vendor lock-in |
| **Weaviate** | server | ✅ | Hybrid search built in | Heavier to run |
| **MongoDB Atlas** | managed | ✅ | Already on Mongo | Atlas only |
| **Supabase** | managed PG | ✅ | Already on Supabase | It's pgvector |

**How to actually choose:**

1. **Already have Postgres and under ~1M vectors?** → **pgvector.** One database, transactional
   consistency with your relational data, real SQL filtering. This is the right answer far more
   often than the vector-database marketing suggests.
2. **Prototyping locally?** → **Chroma.** Zero setup, persists to disk.
3. **Self-hosting at scale?** → **Qdrant.** Excellent filtering, good performance, sane ops.
4. **Don't want to run anything?** → **Pinecone.**
5. **Need best-in-class hybrid search out of the box?** → **Weaviate.**

> 💡 **The under-rated answer is pgvector.** Keeping vectors next to your relational data means
> you can `JOIN` search results against users, permissions and timestamps in one query, with real
> transactions. Teams routinely add a dedicated vector database they didn't need.

### 3.4 The vector store interface

Every LangChain vector store implements roughly:

```js
await store.addDocuments(docs)                        // embeds + stores
await store.similaritySearch(query, k, filter)        // → Document[]
await store.similaritySearchWithScore(query, k)       // → [Document, score][]
await store.maxMarginalRelevanceSearch(query, {k})    // diversity (Day 13)
await store.delete({ ids })
const retriever = store.asRetriever({ k, filter })    // → a Runnable!
```

That last line matters: **`asRetriever` turns a store into a `Runnable`**, so it drops straight
into an LCEL chain. That's how tomorrow's RAG pipeline is built.

### 3.5 BM25 and hybrid fusion

BM25 is the classic keyword ranking function. Roughly: a document scores higher when it contains
more of the query's *rare* terms, with diminishing returns for repetition and a penalty for
length.

To combine two rankings, use **Reciprocal Rank Fusion** — simple, robust, and it needs no score
normalisation:

```
RRF_score(doc) = Σ  1 / (k + rank_in_that_list)         k ≈ 60 by convention
                over each ranked list
```

```
   doc      vector rank   keyword rank   RRF score
   ─────    ───────────   ────────────   ─────────
   A            1              5         1/61 + 1/65 = 0.0318
   B            2              1         1/62 + 1/61 = 0.0325  ← wins
   C            3             —          1/63        = 0.0159
```

**Why RRF beats weighted score averaging:** cosine similarity (0–1) and BM25 (unbounded) live on
incomparable scales. Fusing *ranks* sidesteps normalisation entirely, and it's remarkably hard to
beat in practice.

---

## 4. Code — JavaScript

```bash
npm install langchain @langchain/core @langchain/classic @langchain/ollama \
            @langchain/community dotenv
```

### 4.1 Your first vector store

```js
// day11-memory-store.js
import "dotenv/config";
import { MemoryVectorStore } from "@langchain/classic/vectorstores/memory";
import { OllamaEmbeddings } from "@langchain/ollama";
import { Document } from "@langchain/core/documents";

const embeddings = new OllamaEmbeddings({ model: "nomic-embed-text" });

const DOCS = [
  new Document({ pageContent: "Refunds are processed within 5 business days of approval.",
                 metadata: { section: "Refunds", dept: "billing", year: 2024 } }),
  new Document({ pageContent: "Basic plans allow refunds within 30 days; Pro within 60 days.",
                 metadata: { section: "Refunds", dept: "billing", year: 2024 } }),
  new Document({ pageContent: "Domestic orders ship within 2 business days.",
                 metadata: { section: "Shipping", dept: "ops", year: 2023 } }),
  new Document({ pageContent: "International orders take 10-14 days and may incur customs fees.",
                 metadata: { section: "Shipping", dept: "ops", year: 2024 } }),
  new Document({ pageContent: "Support is available 9am-6pm GMT, Monday to Friday.",
                 metadata: { section: "Support", dept: "ops", year: 2024 } }),
  new Document({ pageContent: "The API returns HTTP 429 when the rate limit is exceeded.",
                 metadata: { section: "API", dept: "eng", year: 2024 } }),
];

const store = await MemoryVectorStore.fromDocuments(DOCS, embeddings);

// ── plain search ─────────────────────────────────────────────────────────
console.log("❓ how long for my money back?\n");
for (const d of await store.similaritySearch("how long for my money back?", 2)) {
  console.log(`   [${d.metadata.section}] ${d.pageContent.slice(0, 60)}`);
}

// ── with scores ──────────────────────────────────────────────────────────
console.log("\n❓ with scores:\n");
for (const [d, score] of await store.similaritySearchWithScore("delivery abroad", 3)) {
  console.log(`   ${score.toFixed(3)}  [${d.metadata.section}] ${d.pageContent.slice(0, 50)}`);
}

// ── metadata filtering ───────────────────────────────────────────────────
console.log("\n❓ 'policy' filtered to dept=ops:\n");
const filtered = await store.similaritySearch(
  "policy", 3,
  (doc) => doc.metadata.dept === "ops"          // MemoryVectorStore takes a FUNCTION
);
for (const d of filtered) {
  console.log(`   [${d.metadata.dept}/${d.metadata.section}] ${d.pageContent.slice(0, 50)}`);
}

// ── as a Runnable — this is the bridge to tomorrow ───────────────────────
const retriever = store.asRetriever({ k: 2 });
const docs = await retriever.invoke("what happens if I send too many requests?");
console.log("\n❓ via retriever:\n");
docs.forEach((d) => console.log(`   ${d.pageContent.slice(0, 60)}`));
```

### 4.2 Chroma — persistence that survives restarts

```bash
npm install @langchain/community chromadb
pip install chromadb          # the server; or: docker run -p 8000:8000 chromadb/chroma
chroma run --path ./chroma_db
```

```js
// day11-chroma.js
import "dotenv/config";
import { Chroma } from "@langchain/community/vectorstores/chroma";
import { OllamaEmbeddings } from "@langchain/ollama";
import { Document } from "@langchain/core/documents";

const embeddings = new OllamaEmbeddings({ model: "nomic-embed-text" });

const COLLECTION = "handbook";

// ── first run: create and populate ───────────────────────────────────────
async function ingest() {
  const docs = [
    new Document({ pageContent: "Refunds are processed within 5 business days.",
                   metadata: { section: "Refunds", dept: "billing" } }),
    new Document({ pageContent: "International orders take 10-14 days.",
                   metadata: { section: "Shipping", dept: "ops" } }),
    new Document({ pageContent: "The API returns HTTP 429 when rate limited.",
                   metadata: { section: "API", dept: "eng" } }),
  ];

  const store = await Chroma.fromDocuments(docs, embeddings, {
    collectionName: COLLECTION,
    url: "http://localhost:8000",
    collectionMetadata: { "hnsw:space": "cosine" },   // ← the distance metric
  });

  console.log("ingested ✅");
  return store;
}

// ── later runs: connect to the EXISTING collection, no re-embedding ──────
async function connect() {
  return Chroma.fromExistingCollection(embeddings, {
    collectionName: COLLECTION,
    url: "http://localhost:8000",
  });
}

const store = process.argv[2] === "ingest" ? await ingest() : await connect();

// ── Chroma uses a WHERE-clause object, not a function ────────────────────
console.log("\n❓ 'delivery' where dept=ops:\n");
const results = await store.similaritySearch("delivery", 2, { dept: "ops" });
results.forEach((d) => console.log(`   [${d.metadata.section}] ${d.pageContent}`));

// Operators: $eq $ne $gt $gte $lt $lte $in $nin, plus $and / $or
console.log("\n❓ 'policy' where dept in [billing, eng]:\n");
const multi = await store.similaritySearch("policy", 3, {
  dept: { $in: ["billing", "eng"] },
});
multi.forEach((d) => console.log(`   [${d.metadata.dept}] ${d.pageContent.slice(0, 50)}`));
```

> ⚠️ **Filter syntax is store-specific and does not port.** `MemoryVectorStore` takes a
> *function*; Chroma takes a Mongo-style *object*; pgvector uses SQL; Pinecone has its own
> dialect. This is the main thing that leaks through the vector-store abstraction, so isolate
> filter construction behind your own helper if you might switch stores.

### 4.3 Hybrid search — BM25 + vectors with RRF

```js
// day11-hybrid.js
import "dotenv/config";
import { MemoryVectorStore } from "@langchain/classic/vectorstores/memory";
import { OllamaEmbeddings } from "@langchain/ollama";
import { Document } from "@langchain/core/documents";

const embeddings = new OllamaEmbeddings({ model: "nomic-embed-text" });

const DOCS = [
  new Document({ pageContent: "Error ERR_4471 means the request payload exceeded 10MB.",
                 metadata: { id: 1 } }),
  new Document({ pageContent: "Error ERR_4472 means the request timed out after 30 seconds.",
                 metadata: { id: 2 } }),
  new Document({ pageContent: "Error ERR_5010 indicates an internal server fault.",
                 metadata: { id: 3 } }),
  new Document({ pageContent: "The API rate limit is 1000 requests per minute for Pro accounts.",
                 metadata: { id: 4 } }),
  new Document({ pageContent: "If you send too many requests you will be throttled.",
                 metadata: { id: 5 } }),
  new Document({ pageContent: "Payload size limits apply to all upload endpoints.",
                 metadata: { id: 6 } }),
];

// ── BM25, from scratch ───────────────────────────────────────────────────
class BM25 {
  constructor(docs, k1 = 1.5, b = 0.75) {
    this.k1 = k1; this.b = b;
    this.docs = docs;
    this.tokenised = docs.map((d) => this.tokenize(d.pageContent));
    this.avgLen = this.tokenised.reduce((s, t) => s + t.length, 0) / docs.length;

    this.df = new Map();
    for (const tokens of this.tokenised) {
      for (const t of new Set(tokens)) this.df.set(t, (this.df.get(t) ?? 0) + 1);
    }
    this.N = docs.length;
  }

  // Keep alphanumerics together so ERR_4471 survives as err_4471
  tokenize(s) {
    return s.toLowerCase().match(/[a-z0-9_]+/g) ?? [];
  }

  idf(term) {
    const df = this.df.get(term) ?? 0;
    return Math.log(1 + (this.N - df + 0.5) / (df + 0.5));
  }

  search(query, k = 5) {
    const qTerms = this.tokenize(query);

    return this.tokenised
      .map((tokens, i) => {
        let score = 0;
        for (const term of qTerms) {
          const tf = tokens.filter((t) => t === term).length;
          if (!tf) continue;
          const norm = 1 - this.b + this.b * (tokens.length / this.avgLen);
          score += this.idf(term) * (tf * (this.k1 + 1)) / (tf + this.k1 * norm);
        }
        return { doc: this.docs[i], score };
      })
      .filter((r) => r.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, k);
  }
}

// ── Reciprocal Rank Fusion ───────────────────────────────────────────────
function rrf(rankedLists, k = 60) {
  const scores = new Map();

  for (const list of rankedLists) {
    list.forEach((item, rank) => {
      const key = item.doc.pageContent;
      const prev = scores.get(key) ?? { doc: item.doc, score: 0 };
      prev.score += 1 / (k + rank + 1);          // rank is 0-based, so +1
      scores.set(key, prev);
    });
  }

  return [...scores.values()].sort((a, b) => b.score - a.score);
}

// ── compare all three ────────────────────────────────────────────────────
const vectorStore = await MemoryVectorStore.fromDocuments(DOCS, embeddings);
const bm25 = new BM25(DOCS);

for (const QUERY of [
  "ERR_4471",                                  // exact identifier — keywords win
  "what happens if I send too many requests",  // semantic — vectors win
]) {
  console.log(`\n${"═".repeat(70)}\n❓ "${QUERY}"\n${"═".repeat(70)}`);

  const vecResults = (await vectorStore.similaritySearchWithScore(QUERY, 4))
    .map(([doc, score]) => ({ doc, score }));
  const kwResults = bm25.search(QUERY, 4);
  const fused = rrf([vecResults, kwResults]).slice(0, 3);

  console.log("\nVECTOR:");
  vecResults.forEach((r, i) =>
    console.log(`  ${i + 1}. ${r.score.toFixed(3)}  ${r.doc.pageContent.slice(0, 55)}`));

  console.log("\nKEYWORD (BM25):");
  kwResults.length
    ? kwResults.forEach((r, i) =>
        console.log(`  ${i + 1}. ${r.score.toFixed(3)}  ${r.doc.pageContent.slice(0, 55)}`))
    : console.log("  (no lexical matches)");

  console.log("\nHYBRID (RRF):");
  fused.forEach((r, i) =>
    console.log(`  ${i + 1}. ${r.score.toFixed(4)}  ${r.doc.pageContent.slice(0, 55)}`));
}
```

Run it. On `"ERR_4471"` the vector search ranks `ERR_4472` competitively — yesterday's failure,
reproduced. BM25 nails it. **Hybrid gets both queries right.**

### 4.4 Benchmarking exact vs approximate

```js
// day11-benchmark.js
import "dotenv/config";
import { OllamaEmbeddings } from "@langchain/ollama";

const embeddings = new OllamaEmbeddings({ model: "nomic-embed-text" });

// Synthetic vectors — we're measuring the ALGORITHM, not the model.
const DIMS = 768;
const randomVec = () => {
  const v = Array.from({ length: DIMS }, () => Math.random() * 2 - 1);
  const m = Math.sqrt(v.reduce((s, x) => s + x * x, 0));
  return v.map((x) => x / m);                     // normalised
};

const dot = (a, b) => a.reduce((s, v, i) => s + v * b[i], 0);

function exactSearch(vectors, query, k) {
  return vectors
    .map((v, i) => ({ i, score: dot(query, v) }))
    .sort((a, b) => b.score - a.score)
    .slice(0, k)
    .map((r) => r.i);
}

// A crude IVF stand-in: cluster by nearest of `nlist` random centroids,
// then search only the `nprobe` closest clusters.
function buildIVF(vectors, nlist) {
  const centroids = Array.from({ length: nlist }, () =>
    vectors[Math.floor(Math.random() * vectors.length)]
  );
  const buckets = Array.from({ length: nlist }, () => []);

  vectors.forEach((v, i) => {
    let best = 0, bestScore = -Infinity;
    centroids.forEach((c, ci) => {
      const s = dot(v, c);
      if (s > bestScore) { bestScore = s; best = ci; }
    });
    buckets[best].push(i);
  });

  return { centroids, buckets, vectors };
}

function ivfSearch(index, query, k, nprobe) {
  const nearest = index.centroids
    .map((c, ci) => ({ ci, score: dot(query, c) }))
    .sort((a, b) => b.score - a.score)
    .slice(0, nprobe)
    .map((r) => r.ci);

  const candidates = nearest.flatMap((ci) => index.buckets[ci]);

  return candidates
    .map((i) => ({ i, score: dot(query, index.vectors[i]) }))
    .sort((a, b) => b.score - a.score)
    .slice(0, k)
    .map((r) => r.i);
}

// ── run ──────────────────────────────────────────────────────────────────
const N = 20000, K = 10;
console.log(`building ${N} × ${DIMS}-dim vectors…`);
const vectors = Array.from({ length: N }, randomVec);
const queries = Array.from({ length: 20 }, randomVec);

// exact baseline
let t0 = Date.now();
const truth = queries.map((q) => exactSearch(vectors, q, K));
const exactMs = (Date.now() - t0) / queries.length;
console.log(`\nEXACT:  ${exactMs.toFixed(1)}ms/query · recall 1.000 (by definition)\n`);

const index = buildIVF(vectors, 100);

console.log("nprobe   ms/query   recall@10   vectors scanned");
console.log("-".repeat(52));

for (const nprobe of [1, 2, 5, 10, 25, 50, 100]) {
  t0 = Date.now();
  const results = queries.map((q) => ivfSearch(index, q, K, nprobe));
  const ms = (Date.now() - t0) / queries.length;

  const recall = results.reduce((sum, r, qi) => {
    const hits = r.filter((i) => truth[qi].includes(i)).length;
    return sum + hits / K;
  }, 0) / queries.length;

  const scanned = index.centroids
    .map((_, ci) => index.buckets[ci].length)
    .sort((a, b) => b - a)
    .slice(0, nprobe)
    .reduce((a, b) => a + b, 0);

  console.log(
    `${String(nprobe).padStart(6)}   ${ms.toFixed(1).padStart(8)}   ` +
    `${recall.toFixed(3).padStart(9)}   ${String(scanned).padStart(15)}`
  );
}
```

This is the recall/latency curve in your own terminal. You'll see recall climb steeply then
plateau — the classic shape, and the reason `nprobe`/`ef` tuning is worth doing once.

---

## 5. Code — Python

```bash
pip install langchain langchain-classic langchain-ollama langchain-chroma \
            rank-bm25 numpy python-dotenv
```

### 5.1 Your first vector store

```python
# day11_memory_store.py
from dotenv import load_dotenv
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings

load_dotenv()
embeddings = OllamaEmbeddings(model="nomic-embed-text")

DOCS = [
    Document(page_content="Refunds are processed within 5 business days of approval.",
             metadata={"section": "Refunds", "dept": "billing", "year": 2024}),
    Document(page_content="Basic plans allow refunds within 30 days; Pro within 60 days.",
             metadata={"section": "Refunds", "dept": "billing", "year": 2024}),
    Document(page_content="Domestic orders ship within 2 business days.",
             metadata={"section": "Shipping", "dept": "ops", "year": 2023}),
    Document(page_content="International orders take 10-14 days and may incur customs fees.",
             metadata={"section": "Shipping", "dept": "ops", "year": 2024}),
    Document(page_content="Support is available 9am-6pm GMT, Monday to Friday.",
             metadata={"section": "Support", "dept": "ops", "year": 2024}),
    Document(page_content="The API returns HTTP 429 when the rate limit is exceeded.",
             metadata={"section": "API", "dept": "eng", "year": 2024}),
]

store = InMemoryVectorStore.from_documents(DOCS, embeddings)

# ── plain search ─────────────────────────────────────────────────────────
print("❓ how long for my money back?\n")
for d in store.similarity_search("how long for my money back?", k=2):
    print(f"   [{d.metadata['section']}] {d.page_content[:60]}")

# ── with scores ──────────────────────────────────────────────────────────
print("\n❓ with scores:\n")
for d, score in store.similarity_search_with_score("delivery abroad", k=3):
    print(f"   {score:.3f}  [{d.metadata['section']}] {d.page_content[:50]}")

# ── metadata filtering ───────────────────────────────────────────────────
print("\n❓ 'policy' filtered to dept=ops:\n")
for d in store.similarity_search("policy", k=3,
                                 filter=lambda doc: doc.metadata["dept"] == "ops"):
    print(f"   [{d.metadata['dept']}/{d.metadata['section']}] {d.page_content[:50]}")

# ── as a Runnable — this is the bridge to tomorrow ───────────────────────
retriever = store.as_retriever(search_kwargs={"k": 2})
print("\n❓ via retriever:\n")
for d in retriever.invoke("what happens if I send too many requests?"):
    print(f"   {d.page_content[:60]}")
```

### 5.2 Chroma — persistence that survives restarts

```bash
pip install langchain-chroma
```

```python
# day11_chroma.py
import sys
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings

load_dotenv()
embeddings = OllamaEmbeddings(model="nomic-embed-text")

PERSIST_DIR = "./chroma_db"
COLLECTION = "handbook"

# Chroma in Python can persist to a local directory — no server needed.
store = Chroma(
    collection_name=COLLECTION,
    embedding_function=embeddings,
    persist_directory=PERSIST_DIR,
    collection_metadata={"hnsw:space": "cosine"},     # ← the distance metric
)

# ── first run: populate ──────────────────────────────────────────────────
if len(sys.argv) > 1 and sys.argv[1] == "ingest":
    store.add_documents([
        Document(page_content="Refunds are processed within 5 business days.",
                 metadata={"section": "Refunds", "dept": "billing"}),
        Document(page_content="International orders take 10-14 days.",
                 metadata={"section": "Shipping", "dept": "ops"}),
        Document(page_content="The API returns HTTP 429 when rate limited.",
                 metadata={"section": "API", "dept": "eng"}),
    ])
    print("ingested ✅")

# ── Chroma uses a WHERE-clause dict, not a function ──────────────────────
print("\n❓ 'delivery' where dept=ops:\n")
for d in store.similarity_search("delivery", k=2, filter={"dept": "ops"}):
    print(f"   [{d.metadata['section']}] {d.page_content}")

# Operators: $eq $ne $gt $gte $lt $lte $in $nin, plus $and / $or
print("\n❓ 'policy' where dept in [billing, eng]:\n")
for d in store.similarity_search("policy", k=3,
                                 filter={"dept": {"$in": ["billing", "eng"]}}):
    print(f"   [{d.metadata['dept']}] {d.page_content[:50]}")
```

### 5.3 Hybrid search — BM25 + vectors with RRF

```python
# day11_hybrid.py
import math, re
from dotenv import load_dotenv
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings

load_dotenv()
embeddings = OllamaEmbeddings(model="nomic-embed-text")

DOCS = [
    Document(page_content="Error ERR_4471 means the request payload exceeded 10MB.",
             metadata={"id": 1}),
    Document(page_content="Error ERR_4472 means the request timed out after 30 seconds.",
             metadata={"id": 2}),
    Document(page_content="Error ERR_5010 indicates an internal server fault.",
             metadata={"id": 3}),
    Document(page_content="The API rate limit is 1000 requests per minute for Pro accounts.",
             metadata={"id": 4}),
    Document(page_content="If you send too many requests you will be throttled.",
             metadata={"id": 5}),
    Document(page_content="Payload size limits apply to all upload endpoints.",
             metadata={"id": 6}),
]

# ── BM25, from scratch ───────────────────────────────────────────────────
class BM25:
    def __init__(self, docs, k1=1.5, b=0.75):
        self.k1, self.b, self.docs = k1, b, docs
        self.tokenised = [self.tokenize(d.page_content) for d in docs]
        self.avg_len = sum(len(t) for t in self.tokenised) / len(docs)

        self.df = {}
        for tokens in self.tokenised:
            for t in set(tokens):
                self.df[t] = self.df.get(t, 0) + 1
        self.N = len(docs)

    # Keep alphanumerics together so ERR_4471 survives as err_4471
    @staticmethod
    def tokenize(s):
        return re.findall(r"[a-z0-9_]+", s.lower())

    def idf(self, term):
        df = self.df.get(term, 0)
        return math.log(1 + (self.N - df + 0.5) / (df + 0.5))

    def search(self, query, k=5):
        q_terms = self.tokenize(query)
        results = []

        for i, tokens in enumerate(self.tokenised):
            score = 0.0
            for term in q_terms:
                tf = tokens.count(term)
                if not tf:
                    continue
                norm = 1 - self.b + self.b * (len(tokens) / self.avg_len)
                score += self.idf(term) * (tf * (self.k1 + 1)) / (tf + self.k1 * norm)
            if score > 0:
                results.append({"doc": self.docs[i], "score": score})

        return sorted(results, key=lambda r: -r["score"])[:k]

# ── Reciprocal Rank Fusion ───────────────────────────────────────────────
def rrf(ranked_lists, k=60):
    scores = {}
    for lst in ranked_lists:
        for rank, item in enumerate(lst):
            key = item["doc"].page_content
            entry = scores.setdefault(key, {"doc": item["doc"], "score": 0.0})
            entry["score"] += 1 / (k + rank + 1)        # rank is 0-based, so +1
    return sorted(scores.values(), key=lambda r: -r["score"])

# ── compare all three ────────────────────────────────────────────────────
vector_store = InMemoryVectorStore.from_documents(DOCS, embeddings)
bm25 = BM25(DOCS)

for QUERY in [
    "ERR_4471",                                  # exact identifier — keywords win
    "what happens if I send too many requests",  # semantic — vectors win
]:
    print(f"\n{'═' * 70}\n❓ \"{QUERY}\"\n{'═' * 70}")

    vec_results = [{"doc": d, "score": s}
                   for d, s in vector_store.similarity_search_with_score(QUERY, k=4)]
    kw_results = bm25.search(QUERY, 4)
    fused = rrf([vec_results, kw_results])[:3]

    print("\nVECTOR:")
    for i, r in enumerate(vec_results, 1):
        print(f"  {i}. {r['score']:.3f}  {r['doc'].page_content[:55]}")

    print("\nKEYWORD (BM25):")
    if kw_results:
        for i, r in enumerate(kw_results, 1):
            print(f"  {i}. {r['score']:.3f}  {r['doc'].page_content[:55]}")
    else:
        print("  (no lexical matches)")

    print("\nHYBRID (RRF):")
    for i, r in enumerate(fused, 1):
        print(f"  {i}. {r['score']:.4f}  {r['doc'].page_content[:55]}")
```

<details>
<summary>📦 Using LangChain's built-in BM25Retriever + EnsembleRetriever instead</summary>

```bash
pip install rank-bm25
```

```python
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers import EnsembleRetriever

bm25_retriever = BM25Retriever.from_documents(DOCS)
bm25_retriever.k = 4

vector_retriever = vector_store.as_retriever(search_kwargs={"k": 4})

# EnsembleRetriever fuses with RRF internally
hybrid = EnsembleRetriever(
    retrievers=[bm25_retriever, vector_retriever],
    weights=[0.5, 0.5],
)

for d in hybrid.invoke("ERR_4471"):
    print(d.page_content[:60])
```

We built it by hand first so the fusion isn't a black box — but use the built-in in production.
JS has `EnsembleRetriever` too, in `@langchain/classic/retrievers/ensemble`.
</details>

### 5.4 Benchmarking exact vs approximate

```python
# day11_benchmark.py
import time
import numpy as np

DIMS, N, K = 768, 20000, 10
rng = np.random.default_rng(42)

def random_vectors(n):
    v = rng.standard_normal((n, DIMS))
    return v / np.linalg.norm(v, axis=1, keepdims=True)      # normalised

print(f"building {N} × {DIMS}-dim vectors…")
vectors = random_vectors(N)
queries = random_vectors(20)

def exact_search(vectors, query, k):
    scores = vectors @ query
    return set(np.argsort(-scores)[:k].tolist())

# A crude IVF stand-in: assign to nearest of `nlist` centroids,
# then search only the `nprobe` closest clusters.
def build_ivf(vectors, nlist):
    idx = rng.choice(len(vectors), nlist, replace=False)
    centroids = vectors[idx]
    assignments = np.argmax(vectors @ centroids.T, axis=1)
    buckets = [np.where(assignments == c)[0] for c in range(nlist)]
    return centroids, buckets

def ivf_search(centroids, buckets, vectors, query, k, nprobe):
    nearest = np.argsort(-(centroids @ query))[:nprobe]
    candidates = np.concatenate([buckets[c] for c in nearest if len(buckets[c])])
    if candidates.size == 0:
        return set()
    scores = vectors[candidates] @ query
    top = candidates[np.argsort(-scores)[:k]]
    return set(top.tolist())

# ── exact baseline ───────────────────────────────────────────────────────
t0 = time.time()
truth = [exact_search(vectors, q, K) for q in queries]
exact_ms = (time.time() - t0) * 1000 / len(queries)
print(f"\nEXACT:  {exact_ms:.1f}ms/query · recall 1.000 (by definition)\n")

centroids, buckets = build_ivf(vectors, 100)

print("nprobe   ms/query   recall@10   vectors scanned")
print("-" * 52)

for nprobe in [1, 2, 5, 10, 25, 50, 100]:
    t0 = time.time()
    results = [ivf_search(centroids, buckets, vectors, q, K, nprobe) for q in queries]
    ms = (time.time() - t0) * 1000 / len(queries)

    recall = sum(len(r & t) / K for r, t in zip(results, truth)) / len(queries)
    scanned = sum(sorted((len(b) for b in buckets), reverse=True)[:nprobe])

    print(f"{nprobe:>6}   {ms:>8.1f}   {recall:>9.3f}   {scanned:>15}")
```

### 🔁 JS ↔ Python differences you just saw

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

---

## 6. Under the hood

### How HNSW search actually runs

```
   query q, ef = 40, k = 10

   layer 2:  start at a fixed entry point
             greedily move to the neighbour closest to q
             stop when no neighbour improves → this is the entry to layer 1

   layer 1:  same greedy walk, starting from where layer 2 left off
             the graph is denser here, so steps are finer

   layer 0:  now do a BEST-FIRST search, not just greedy:
             - maintain a candidate heap and a result heap of size `ef`
             - pop the closest unvisited candidate
             - add its neighbours to the candidate heap
             - stop when the closest candidate is worse than the worst result
             - return the top `k` of the `ef` results
```

**Why `ef` must be ≥ `k`:** the result heap holds `ef` items and you return `k` of them. Setting
`ef = 10, k = 10` gives you no room to explore — recall collapses. A common default is
`ef = 2×k` or higher.

**Why it's approximate:** the greedy descent can enter a region of the graph that doesn't contain
the true nearest neighbour, and never find its way out. Higher `ef` and higher `M` both reduce
the chance, at a cost.

### Filtering inside an ANN index is genuinely hard

This is why pre-filtering isn't universal — it's not laziness, it's a real algorithmic problem.

```
   HNSW navigates by GRAPH EDGES. Removing nodes that fail the filter
   can disconnect the graph:

   ●───●───✗───●───●          the path to the answer ran THROUGH
                              a filtered-out node
```

Stores solve this differently:

- **Qdrant** builds additional links so filtered subgraphs stay connected, and switches to brute
  force when the filter is very selective (a full scan of 1% of your data is fast anyway).
- **pgvector** can use a regular B-tree index on the metadata column first, then vector-search
  the surviving rows — real SQL query planning.
- **Chroma** applies the filter during traversal.
- Some stores simply post-filter.

**The practical rule:** if your filters are highly selective, either verify your store
pre-filters, or over-fetch and filter yourself, or partition into separate collections.

### Why RRF is so hard to beat

Score-based fusion requires normalising incomparable scales:

```
cosine:  0.72   (bounded 0-1, clustered around 0.4-0.9 — Day 10 anisotropy)
BM25:    8.34   (unbounded, depends on corpus statistics and query length)

normalise how? min-max over this result set? z-score? over what population?
```

Every normalisation choice introduces assumptions that break on some queries — a query where
every result scores 0.8 min-maxes into a meaningless spread.

RRF uses only **rank**, which is scale-free. It also has a useful property: the `k` constant
(≈60) damps the influence of top ranks, so a document ranked #1 by one retriever and #50 by the
other doesn't automatically win. It's a robustness/precision trade that works well in practice.

### Distance metric configuration

Getting this wrong is a silent, top-to-bottom failure:

```js
collectionMetadata: { "hnsw:space": "cosine" }    // or "l2", "ip"
```

If your embeddings are normalised (Day 10) then cosine, `ip` (inner product) and `l2` all rank
identically — so a mistake is harmless. **If they're not normalised**, choosing `l2` on
un-normalised vectors ranks partly by document length.

**Set it explicitly at collection creation.** It usually cannot be changed afterwards without
rebuilding the index.

---

## 7. Common mistakes

**❌ Assuming your store pre-filters**

Ask for `k=10` with a selective filter and get 1 result back.
✅ Check the docs. Over-fetch (`k * 20`) and filter yourself if it post-filters, or partition.

---

**❌ Filtering for multi-tenancy instead of partitioning**

One bug in filter construction leaks another customer's data.
✅ Separate collections per tenant where practical. Structural isolation beats a conditional.

---

**❌ Setting `ef` equal to `k`**

No room to explore; recall drops sharply.
✅ `ef ≥ 2 × k`, and tune it against a measured recall curve.

---

**❌ Re-embedding on every startup**

```js
const store = await MemoryVectorStore.fromDocuments(docs, embeddings);  // every boot
```
✅ Use a persistent store and connect to the existing collection. Ingest is a separate script.

---

**❌ Using vector search alone for identifiers**

Error codes, SKUs, part numbers, usernames — embeddings can't distinguish `ERR_4471` from
`ERR_4472`.
✅ Hybrid search. This is the single most common quality gap in production RAG.

---

**❌ Portable filter syntax that isn't**

`MemoryVectorStore` wants a function, Chroma wants an object, pgvector wants SQL.
✅ Wrap filter construction in your own helper so switching stores touches one file.

---

**❌ Adding a vector database you don't need**

You already run Postgres, you have 200k vectors, and you add a separate service to operate,
monitor, back up and keep in sync.
✅ pgvector. One database, real transactions, `JOIN`s against your actual data.

---

**❌ Not setting the distance metric explicitly**

Defaults vary by store, and it usually can't be changed without a rebuild.
✅ Set it at creation. Use cosine unless you have a specific reason.

---

**❌ Forgetting to delete vectors when source documents are deleted**

Your bot confidently cites a document that no longer exists.
✅ Deletion is part of the ingest contract, not an afterthought (Day 09's incremental ingest).

---

## 8. Exercises

### Exercise 1 — Store round-trip with persistence ●○○○○

Build a script that ingests documents into Chroma on first run and, on subsequent runs, connects
to the existing collection without re-embedding. Prove it by timing both runs and printing the
collection count.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
// requires: chroma run --path ./chroma_db
import "dotenv/config";
import { Chroma } from "@langchain/community/vectorstores/chroma";
import { OllamaEmbeddings } from "@langchain/ollama";
import { Document } from "@langchain/core/documents";

const embeddings = new OllamaEmbeddings({ model: "nomic-embed-text" });
const COLLECTION = "roundtrip_demo";

const DOCS = Array.from({ length: 50 }, (_, i) => new Document({
  pageContent: `Policy item ${i}: this clause covers scenario ${i % 7} in detail.`,
  metadata: { id: i, group: i % 7 },
}));

const t0 = Date.now();
let store, mode;

try {
  store = await Chroma.fromExistingCollection(embeddings, {
    collectionName: COLLECTION, url: "http://localhost:8000",
  });
  const count = await store.collection.count();
  if (count === 0) throw new Error("empty");
  mode = `connected to existing (${count} vectors)`;
} catch {
  store = await Chroma.fromDocuments(DOCS, embeddings, {
    collectionName: COLLECTION,
    url: "http://localhost:8000",
    collectionMetadata: { "hnsw:space": "cosine" },
  });
  mode = `ingested ${DOCS.length} documents`;
}

console.log(`${mode} in ${Date.now() - t0}ms`);

const results = await store.similaritySearch("scenario 3", 3);
results.forEach((d) => console.log(`  [${d.metadata.id}] ${d.pageContent.slice(0, 55)}`));
```

**Python**
```python
import sys, time
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings

load_dotenv()
embeddings = OllamaEmbeddings(model="nomic-embed-text")

PERSIST_DIR = "./chroma_db"
COLLECTION = "roundtrip_demo"

DOCS = [
    Document(page_content=f"Policy item {i}: this clause covers scenario {i % 7} in detail.",
             metadata={"id": i, "group": i % 7})
    for i in range(50)
]

t0 = time.time()

store = Chroma(
    collection_name=COLLECTION,
    embedding_function=embeddings,
    persist_directory=PERSIST_DIR,
    collection_metadata={"hnsw:space": "cosine"},
)

existing = store._collection.count()
if existing == 0:
    store.add_documents(DOCS)
    mode = f"ingested {len(DOCS)} documents"
else:
    mode = f"connected to existing ({existing} vectors)"

print(f"{mode} in {(time.time() - t0) * 1000:.0f}ms")

for d in store.similarity_search("scenario 3", k=3):
    print(f"  [{d.metadata['id']}] {d.page_content[:55]}")
```

**Expected:**

```
$ python day11_ex1.py
ingested 50 documents in 1840ms

$ python day11_ex1.py
connected to existing (50 vectors) in 47ms      ← 40× faster
```

**The point:** ingest is a *separate lifecycle* from serving. In production these are different
processes — ingest runs in CI or a worker when documents change; the API server only ever
connects. Re-embedding on every boot is one of the most common and most expensive beginner
mistakes, and it makes cold starts unusable.

Note the `count() == 0` check rather than a try/catch on connection — connecting to an empty
collection usually *succeeds*, so catching an error isn't enough to detect "not yet ingested".
</details>

---

### Exercise 2 — Pre-filter vs post-filter, demonstrated ●●○○○

Build a store with documents across 5 tenants where one tenant owns only 2% of documents. Search
with `k=10` filtered to that tenant, two ways: (a) filter passed to the store, (b) fetch `k=10`
unfiltered then filter in your code. Show how many results each returns.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import "dotenv/config";
import { MemoryVectorStore } from "@langchain/classic/vectorstores/memory";
import { OllamaEmbeddings } from "@langchain/ollama";
import { Document } from "@langchain/core/documents";

const embeddings = new OllamaEmbeddings({ model: "nomic-embed-text" });

// 200 docs; tenant "rare" owns only 4 of them (2%).
const TOPICS = ["billing and refunds", "shipping and delivery", "account settings",
                "API rate limits", "support hours"];

const DOCS = Array.from({ length: 200 }, (_, i) => {
  const tenant = i < 4 ? "rare" : ["acme", "globex", "initech", "umbrella"][i % 4];
  return new Document({
    pageContent: `Document ${i} about ${TOPICS[i % 5]} for customer ${tenant}.`,
    metadata: { tenant, id: i },
  });
});

const store = await MemoryVectorStore.fromDocuments(DOCS, embeddings);
const QUERY = "refund policy";
const K = 10;

// ── (a) filter passed to the store ───────────────────────────────────────
const preFiltered = await store.similaritySearch(
  QUERY, K, (doc) => doc.metadata.tenant === "rare"
);

// ── (b) fetch then filter yourself ───────────────────────────────────────
const unfiltered = await store.similaritySearch(QUERY, K);
const postFiltered = unfiltered.filter((d) => d.metadata.tenant === "rare");

// ── (c) the over-fetch workaround ────────────────────────────────────────
const overFetched = (await store.similaritySearch(QUERY, K * 20))
  .filter((d) => d.metadata.tenant === "rare")
  .slice(0, K);

console.log(`corpus: ${DOCS.length} docs · "rare" tenant owns ` +
            `${DOCS.filter((d) => d.metadata.tenant === "rare").length} (2%)`);
console.log(`query: "${QUERY}" · k=${K}\n`);

console.log(`(a) filter in store   → ${preFiltered.length} results ` +
            `${preFiltered.length >= 4 ? "✅" : "⚠️"}`);
console.log(`(b) filter after k=10 → ${postFiltered.length} results ` +
            `${postFiltered.length < 4 ? "❌ starved!" : ""}`);
console.log(`(c) over-fetch k=200  → ${overFetched.length} results ✅`);

console.log("\ntenants in the unfiltered top-10:");
console.log("  " + unfiltered.map((d) => d.metadata.tenant).join(", "));
```

**Python**
```python
from dotenv import load_dotenv
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings

load_dotenv()
embeddings = OllamaEmbeddings(model="nomic-embed-text")

# 200 docs; tenant "rare" owns only 4 of them (2%).
TOPICS = ["billing and refunds", "shipping and delivery", "account settings",
          "API rate limits", "support hours"]

DOCS = []
for i in range(200):
    tenant = "rare" if i < 4 else ["acme", "globex", "initech", "umbrella"][i % 4]
    DOCS.append(Document(
        page_content=f"Document {i} about {TOPICS[i % 5]} for customer {tenant}.",
        metadata={"tenant": tenant, "id": i},
    ))

store = InMemoryVectorStore.from_documents(DOCS, embeddings)
QUERY, K = "refund policy", 10

# ── (a) filter passed to the store ───────────────────────────────────────
pre_filtered = store.similarity_search(
    QUERY, k=K, filter=lambda d: d.metadata["tenant"] == "rare")

# ── (b) fetch then filter yourself ───────────────────────────────────────
unfiltered = store.similarity_search(QUERY, k=K)
post_filtered = [d for d in unfiltered if d.metadata["tenant"] == "rare"]

# ── (c) the over-fetch workaround ────────────────────────────────────────
over_fetched = [d for d in store.similarity_search(QUERY, k=K * 20)
                if d.metadata["tenant"] == "rare"][:K]

rare_count = sum(1 for d in DOCS if d.metadata["tenant"] == "rare")
print(f"corpus: {len(DOCS)} docs · \"rare\" tenant owns {rare_count} (2%)")
print(f'query: "{QUERY}" · k={K}\n')

print(f"(a) filter in store   → {len(pre_filtered)} results "
      f"{'✅' if len(pre_filtered) >= 4 else '⚠️'}")
print(f"(b) filter after k=10 → {len(post_filtered)} results "
      f"{'❌ starved!' if len(post_filtered) < 4 else ''}")
print(f"(c) over-fetch k=200  → {len(over_fetched)} results ✅")

print("\ntenants in the unfiltered top-10:")
print("  " + ", ".join(d.metadata["tenant"] for d in unfiltered))
```

**Typical output:**

```
corpus: 200 docs · "rare" tenant owns 4 (2%)
query: "refund policy" · k=10

(a) filter in store   → 4 results ✅
(b) filter after k=10 → 0 results ❌ starved!
(c) over-fetch k=200  → 4 results ✅

tenants in the unfiltered top-10:
  globex, acme, umbrella, initech, acme, globex, initech, umbrella, acme, globex
```

**Case (b) returns nothing at all.** The rare tenant's 4 documents are relevant, but they never
appear in an unfiltered top-10 out of 200 — the other 196 documents crowd them out.

**Why this matters more than it looks:** this failure is silent and *load-dependent*. It works
fine in development with 20 documents and one tenant. It breaks in production as the corpus
grows, and it breaks *worst for your smallest customers* — exactly the ones least likely to be in
your test data.

**The three fixes, in order of preference:** partition into per-tenant collections (structural,
also the right security answer); use a store that genuinely pre-filters (Qdrant, pgvector,
Weaviate); or over-fetch by a factor of roughly `1 / selectivity` and filter yourself, accepting
the extra latency.
</details>

---

### Exercise 3 — Tune the recall/latency curve ●●●○○

Using the IVF benchmark from §4.4/§5.4, find the smallest `nprobe` that achieves ≥95% recall@10.
Then repeat for `nlist` values of 50, 100 and 400 and explain how the two parameters interact.

<details>
<summary>✅ Solution</summary>

**Python** (numpy makes the sweep fast — JS version follows the same structure)
```python
import time
import numpy as np

DIMS, N, K = 768, 20000, 10
TARGET_RECALL = 0.95
rng = np.random.default_rng(42)

def random_vectors(n):
    v = rng.standard_normal((n, DIMS))
    return v / np.linalg.norm(v, axis=1, keepdims=True)

vectors = random_vectors(N)
queries = random_vectors(30)
truth = [set(np.argsort(-(vectors @ q))[:K].tolist()) for q in queries]

def build_ivf(vectors, nlist):
    idx = rng.choice(len(vectors), nlist, replace=False)
    centroids = vectors[idx]
    assignments = np.argmax(vectors @ centroids.T, axis=1)
    return centroids, [np.where(assignments == c)[0] for c in range(nlist)]

def ivf_search(centroids, buckets, vectors, query, k, nprobe):
    nearest = np.argsort(-(centroids @ query))[:nprobe]
    parts = [buckets[c] for c in nearest if len(buckets[c])]
    if not parts:
        return set()
    candidates = np.concatenate(parts)
    scores = vectors[candidates] @ query
    return set(candidates[np.argsort(-scores)[:k]].tolist())

def evaluate(centroids, buckets, nprobe):
    t0 = time.time()
    results = [ivf_search(centroids, buckets, vectors, q, K, nprobe) for q in queries]
    ms = (time.time() - t0) * 1000 / len(queries)
    recall = sum(len(r & t) / K for r, t in zip(results, truth)) / len(queries)
    scanned = sum(sorted((len(b) for b in buckets), reverse=True)[:nprobe])
    return ms, recall, scanned

print(f"{N} vectors · target recall@{K} ≥ {TARGET_RECALL}\n")
print("nlist  minNprobe  ms/query  recall  scanned  %ofCorpus")
print("-" * 60)

for nlist in [50, 100, 400]:
    centroids, buckets = build_ivf(vectors, nlist)

    found = None
    for nprobe in range(1, nlist + 1):
        ms, recall, scanned = evaluate(centroids, buckets, nprobe)
        if recall >= TARGET_RECALL:
            found = (nprobe, ms, recall, scanned)
            break

    if found:
        nprobe, ms, recall, scanned = found
        print(f"{nlist:>5}  {nprobe:>9}  {ms:>8.1f}  {recall:>6.3f}  "
              f"{scanned:>7}  {scanned / N * 100:>8.1f}%")
    else:
        print(f"{nlist:>5}  never reached {TARGET_RECALL}")
```

**JavaScript** — same structure, reusing the helpers from §4.4:
```js
const TARGET_RECALL = 0.95;

for (const nlist of [50, 100, 400]) {
  const index = buildIVF(vectors, nlist);
  let found = null;

  for (let nprobe = 1; nprobe <= nlist; nprobe++) {
    const t0 = Date.now();
    const results = queries.map((q) => ivfSearch(index, q, K, nprobe));
    const ms = (Date.now() - t0) / queries.length;

    const recall = results.reduce((sum, r, qi) =>
      sum + r.filter((i) => truth[qi].includes(i)).length / K, 0) / queries.length;

    if (recall >= TARGET_RECALL) {
      const scanned = index.buckets.map((b) => b.length)
        .sort((a, b) => b - a).slice(0, nprobe).reduce((a, b) => a + b, 0);
      found = { nprobe, ms, recall, scanned };
      break;
    }
  }

  console.log(found
    ? `nlist=${nlist}: nprobe=${found.nprobe} · ${found.ms.toFixed(1)}ms · ` +
      `recall ${found.recall.toFixed(3)} · scanned ${found.scanned} ` +
      `(${(found.scanned / N * 100).toFixed(1)}%)`
    : `nlist=${nlist}: never reached ${TARGET_RECALL}`);
}
```

**Typical output:**

```
20000 vectors · target recall@10 ≥ 0.95

nlist  minNprobe  ms/query  recall  scanned  %ofCorpus
------------------------------------------------------------
   50          7      12.4   0.953     3820      19.1%
  100         12      10.1   0.951     3140      15.7%
  400         38       8.7   0.958     2410      12.1%
```

**How the parameters interact — this is the actual lesson:**

1. **More clusters → smaller clusters → you need more of them (`nprobe` rises) but scan fewer
   vectors overall.** Finer partitioning gives finer control.
2. **The percentage of the corpus scanned falls as `nlist` rises**, which is why large systems
   use many clusters. FAISS's rule of thumb is `nlist ≈ √N`, so ~140 for 20k vectors — and note
   our 100 and 400 rows bracket that nicely.
3. **The ratio `nprobe / nlist` is roughly stable** (~14%, ~12%, ~10%) — that's the fraction of
   the space you must examine for a given recall, and it's a property of the data's intrinsic
   dimensionality more than of your parameters.
4. **There's a floor.** With random high-dimensional vectors, recall is genuinely hard — real
   embeddings cluster far more, so real systems hit 95% recall scanning a much smaller fraction.

**Do this measurement on your own data.** Random vectors are a worst case; the curve on real
embeddings is much friendlier, and knowing where *your* knee is tells you whether to spend on
latency or on recall.

The HNSW equivalent is `ef` — same shape of curve, same method: sweep it, plot recall against
latency, pick the knee.
</details>

---

### Exercise 4 — Hybrid retriever as a Runnable ●●●○○

Wrap hybrid search (BM25 + vector + RRF) in a proper LangChain `Runnable` so it composes in an
LCEL chain. Add a `weights` option so you can bias toward keywords or semantics, and test it on
queries of both kinds.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import "dotenv/config";
import { MemoryVectorStore } from "@langchain/classic/vectorstores/memory";
import { OllamaEmbeddings } from "@langchain/ollama";
import { Document } from "@langchain/core/documents";
import { RunnableLambda } from "@langchain/core/runnables";
import { ChatGroq } from "@langchain/groq";
import { ChatPromptTemplate } from "@langchain/core/prompts";
import { StringOutputParser } from "@langchain/core/output_parsers";

// (BM25 class from §4.3 — import or paste it here)
import { BM25 } from "./bm25.js";

function createHybridRetriever({ vectorStore, bm25, k = 4, weights = [0.5, 0.5], rrfK = 60 }) {
  return RunnableLambda.from(async (query) => {
    const [vecHits, kwHits] = await Promise.all([
      vectorStore.similaritySearchWithScore(query, k * 2)
        .then((r) => r.map(([doc]) => ({ doc }))),
      Promise.resolve(bm25.search(query, k * 2)),
    ]);

    const scores = new Map();
    [[vecHits, weights[0]], [kwHits, weights[1]]].forEach(([list, weight]) => {
      list.forEach((item, rank) => {
        const key = item.doc.pageContent;
        const entry = scores.get(key) ?? { doc: item.doc, score: 0 };
        entry.score += weight / (rrfK + rank + 1);
        scores.set(key, entry);
      });
    });

    return [...scores.values()]
      .sort((a, b) => b.score - a.score)
      .slice(0, k)
      .map((r) => r.doc);                       // ← returns Document[], like any retriever
  }).withConfig({ runName: "hybrid_retriever" });
}

// ── build ────────────────────────────────────────────────────────────────
const embeddings = new OllamaEmbeddings({ model: "nomic-embed-text" });

const DOCS = [
  new Document({ pageContent: "Error ERR_4471 means the request payload exceeded 10MB." }),
  new Document({ pageContent: "Error ERR_4472 means the request timed out after 30 seconds." }),
  new Document({ pageContent: "The API rate limit is 1000 requests per minute for Pro accounts." }),
  new Document({ pageContent: "If you send too many requests you will be throttled." }),
  new Document({ pageContent: "Payload size limits apply to all upload endpoints." }),
  new Document({ pageContent: "Refunds are processed within 5 business days." }),
];

const vectorStore = await MemoryVectorStore.fromDocuments(DOCS, embeddings);
const bm25 = new BM25(DOCS);

const retriever = createHybridRetriever({ vectorStore, bm25, k: 3 });

// ── it's a Runnable, so it composes ──────────────────────────────────────
const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });

const chain = RunnableLambda.from(async (question) => {
  const docs = await retriever.invoke(question);
  return { question, context: docs.map((d, i) => `[${i + 1}] ${d.pageContent}`).join("\n") };
})
  .pipe(ChatPromptTemplate.fromMessages([
    ["system", "Answer using only the context. Cite sources like [1]."],
    ["human", "Context:\n{context}\n\nQuestion: {question}"],
  ]))
  .pipe(model)
  .pipe(new StringOutputParser());

// ── compare weightings ───────────────────────────────────────────────────
for (const [label, weights] of [
  ["balanced", [0.5, 0.5]],
  ["keyword-heavy", [0.2, 0.8]],
  ["semantic-heavy", [0.8, 0.2]],
]) {
  const r = createHybridRetriever({ vectorStore, bm25, k: 2, weights });
  console.log(`\n── ${label} ──`);
  for (const q of ["ERR_4471", "what if I make too many API calls"]) {
    const docs = await r.invoke(q);
    console.log(`  "${q}" → ${docs[0].pageContent.slice(0, 50)}`);
  }
}

console.log("\n── full chain ──");
console.log(await chain.invoke("what does ERR_4471 mean?"));
```

**Python**
```python
from dotenv import load_dotenv
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_ollama import OllamaEmbeddings
from langchain_groq import ChatGroq

from day11_hybrid import BM25          # the class from §5.3

load_dotenv()

def create_hybrid_retriever(vector_store, bm25, k=4, weights=(0.5, 0.5), rrf_k=60):
    def _retrieve(query):
        vec_hits = [{"doc": d} for d, _ in
                    vector_store.similarity_search_with_score(query, k=k * 2)]
        kw_hits = bm25.search(query, k * 2)

        scores = {}
        for lst, weight in ((vec_hits, weights[0]), (kw_hits, weights[1])):
            for rank, item in enumerate(lst):
                key = item["doc"].page_content
                entry = scores.setdefault(key, {"doc": item["doc"], "score": 0.0})
                entry["score"] += weight / (rrf_k + rank + 1)

        ranked = sorted(scores.values(), key=lambda r: -r["score"])[:k]
        return [r["doc"] for r in ranked]       # ← returns list[Document], like any retriever

    return RunnableLambda(_retrieve).with_config(run_name="hybrid_retriever")

# ── build ────────────────────────────────────────────────────────────────
embeddings = OllamaEmbeddings(model="nomic-embed-text")

DOCS = [
    Document(page_content="Error ERR_4471 means the request payload exceeded 10MB."),
    Document(page_content="Error ERR_4472 means the request timed out after 30 seconds."),
    Document(page_content="The API rate limit is 1000 requests per minute for Pro accounts."),
    Document(page_content="If you send too many requests you will be throttled."),
    Document(page_content="Payload size limits apply to all upload endpoints."),
    Document(page_content="Refunds are processed within 5 business days."),
]

vector_store = InMemoryVectorStore.from_documents(DOCS, embeddings)
bm25 = BM25(DOCS)

retriever = create_hybrid_retriever(vector_store, bm25, k=3)

# ── it's a Runnable, so it composes ──────────────────────────────────────
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

def to_context(question):
    docs = retriever.invoke(question)
    return {"question": question,
            "context": "\n".join(f"[{i}] {d.page_content}" for i, d in enumerate(docs, 1))}

chain = (
    RunnableLambda(to_context)
    | ChatPromptTemplate.from_messages([
        ("system", "Answer using only the context. Cite sources like [1]."),
        ("human", "Context:\n{context}\n\nQuestion: {question}"),
    ])
    | model | StrOutputParser()
)

# ── compare weightings ───────────────────────────────────────────────────
for label, weights in [("balanced", (0.5, 0.5)),
                       ("keyword-heavy", (0.2, 0.8)),
                       ("semantic-heavy", (0.8, 0.2))]:
    r = create_hybrid_retriever(vector_store, bm25, k=2, weights=weights)
    print(f"\n── {label} ──")
    for q in ["ERR_4471", "what if I make too many API calls"]:
        docs = r.invoke(q)
        print(f'  "{q}" → {docs[0].page_content[:50]}')

print("\n── full chain ──")
print(chain.invoke("what does ERR_4471 mean?"))
```

**Three things this exercise establishes:**

1. **A retriever is just a `Runnable` that returns `Document[]`.** That's the entire contract.
   Once yours honours it, it drops into any chain that expects a retriever — which is why
   tomorrow's RAG pipeline will work with this unchanged.
2. **Weights let you bias per use case.** A documentation search with lots of error codes and API
   names wants keyword-heavy; a conversational FAQ wants semantic-heavy. You can even route
   dynamically — detect an identifier pattern in the query and shift the weights.
3. **`k * 2` over-fetch before fusion matters.** Fusing two top-3 lists gives RRF very little to
   work with. Retrieve more, fuse, then truncate.

**The production note:** LangChain's `EnsembleRetriever` does this for you and is what you should
actually use. Building it once by hand means that when its results surprise you, you know exactly
what it's doing — RRF over ranks, not scores.
</details>

---

### Exercise 5 — 🏆 Production-shaped vector store service ●●●●●

Build a `DocumentStore` class that wraps a vector store with the things production needs:
incremental upsert by content hash, deletion by source, tenant-scoped collections, hybrid search
with RRF, and stats. Then build a CLI over it.

<details>
<summary>✅ Solution</summary>

**Python** (Chroma persists without a server, so this is the cleaner language for the demo)
```python
# document_store.py
import hashlib, re, sys, time
from pathlib import Path
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from day11_hybrid import BM25          # from §5.3

load_dotenv()

EMBEDDING_MODEL = "nomic-embed-text"
PERSIST_DIR = "./doc_store"

def content_hash(text):
    return hashlib.sha256(f"{EMBEDDING_MODEL}:{text}".encode()).hexdigest()[:16]

class DocumentStore:
    """A vector store wrapper with upsert, delete-by-source and hybrid search."""

    def __init__(self, tenant):
        self.tenant = tenant
        self.embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)

        # ⭐ ONE COLLECTION PER TENANT — structural isolation, not a filter
        self.store = Chroma(
            collection_name=f"tenant_{re.sub(r'[^a-z0-9_]', '_', tenant.lower())}",
            embedding_function=self.embeddings,
            persist_directory=PERSIST_DIR,
            collection_metadata={"hnsw:space": "cosine"},
        )
        self._bm25 = None          # rebuilt lazily after writes

    # ── ingest ───────────────────────────────────────────────────────────
    def upsert(self, docs):
        """Add documents, skipping any whose content is already stored."""
        existing = set(self.store.get(include=["metadatas"])["ids"])

        to_add, skipped = [], 0
        for d in docs:
            h = content_hash(d.page_content)
            if h in existing:
                skipped += 1
                continue
            d.metadata["content_hash"] = h
            d.metadata["ingested_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            to_add.append((h, d))

        if to_add:
            self.store.add_documents(
                [d for _, d in to_add],
                ids=[h for h, _ in to_add],       # ⭐ hash AS the id → idempotent upsert
            )
            self._bm25 = None

        return {"added": len(to_add), "skipped": skipped}

    def ingest_file(self, path, chunk_size=800, overlap=120):
        text = Path(path).read_text(encoding="utf8")
        pieces = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=overlap).split_text(text)

        docs = [Document(page_content=p,
                         metadata={"source": str(path), "chunk_index": i})
                for i, p in enumerate(pieces)]
        return self.upsert(docs)

    # ── deletion — the part everyone forgets ─────────────────────────────
    def delete_source(self, source):
        """Remove every chunk that came from one source document."""
        found = self.store.get(where={"source": source}, include=["metadatas"])
        ids = found["ids"]
        if ids:
            self.store.delete(ids=ids)
            self._bm25 = None
        return len(ids)

    # ── search ───────────────────────────────────────────────────────────
    def _ensure_bm25(self):
        if self._bm25 is None:
            raw = self.store.get(include=["documents", "metadatas"])
            docs = [Document(page_content=t, metadata=m)
                    for t, m in zip(raw["documents"], raw["metadatas"])]
            self._bm25 = BM25(docs) if docs else None
        return self._bm25

    def search(self, query, k=4, mode="hybrid", where=None):
        if mode == "vector":
            return self.store.similarity_search(query, k=k, filter=where)

        if mode == "keyword":
            bm25 = self._ensure_bm25()
            return [r["doc"] for r in bm25.search(query, k)] if bm25 else []

        # hybrid: RRF over both rankings
        vec = self.store.similarity_search(query, k=k * 2, filter=where)
        bm25 = self._ensure_bm25()
        kw = [r["doc"] for r in bm25.search(query, k * 2)] if bm25 else []

        scores, rrf_k = {}, 60
        for lst in (vec, kw):
            for rank, doc in enumerate(lst):
                key = doc.page_content
                entry = scores.setdefault(key, {"doc": doc, "score": 0.0})
                entry["score"] += 1 / (rrf_k + rank + 1)

        return [r["doc"] for r in
                sorted(scores.values(), key=lambda r: -r["score"])[:k]]

    # ── observability ────────────────────────────────────────────────────
    def stats(self):
        raw = self.store.get(include=["metadatas"])
        sources = {}
        for m in raw["metadatas"]:
            src = m.get("source", "(unknown)")
            sources[src] = sources.get(src, 0) + 1
        return {"tenant": self.tenant, "chunks": len(raw["ids"]), "sources": sources}

# ── CLI ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    tenant = sys.argv[2] if len(sys.argv) > 2 else "demo"
    store = DocumentStore(tenant)

    if cmd == "ingest":
        result = store.ingest_file(sys.argv[3])
        print(f"added {result['added']} · skipped {result['skipped']} (already present)")

    elif cmd == "delete":
        n = store.delete_source(sys.argv[3])
        print(f"deleted {n} chunks from {sys.argv[3]}")

    elif cmd == "stats":
        s = store.stats()
        print(f"tenant: {s['tenant']} · {s['chunks']} chunks")
        for src, n in s["sources"].items():
            print(f"  {n:>5}  {src}")

    elif cmd == "search":
        query = " ".join(sys.argv[3:])
        for mode in ("vector", "keyword", "hybrid"):
            print(f"\n── {mode} ──")
            for d in store.search(query, k=3, mode=mode):
                print(f"  [{d.metadata.get('chunk_index', '?')}] "
                      f"{' '.join(d.page_content.split())[:70]}")

    else:
        print("usage: python document_store.py <ingest|delete|stats|search> <tenant> [args]")
```

```bash
python document_store.py ingest acme ./handbook.md
python document_store.py ingest acme ./handbook.md    # second run: all skipped
python document_store.py stats acme
python document_store.py search acme refund policy
python document_store.py delete acme ./handbook.md
```

**JavaScript** — the same design, with a Chroma server running:
```js
// document-store.js  (requires: chroma run --path ./doc_store)
import "dotenv/config";
import fs from "node:fs/promises";
import crypto from "node:crypto";
import { Chroma } from "@langchain/community/vectorstores/chroma";
import { OllamaEmbeddings } from "@langchain/ollama";
import { Document } from "@langchain/core/documents";
import { RecursiveCharacterTextSplitter } from "@langchain/textsplitters";
import { BM25 } from "./bm25.js";

const EMBEDDING_MODEL = "nomic-embed-text";
const CHROMA_URL = "http://localhost:8000";

const contentHash = (text) =>
  crypto.createHash("sha256").update(`${EMBEDDING_MODEL}:${text}`).digest("hex").slice(0, 16);

export class DocumentStore {
  constructor(tenant) {
    this.tenant = tenant;
    this.embeddings = new OllamaEmbeddings({ model: EMBEDDING_MODEL });
    this.collectionName = `tenant_${tenant.toLowerCase().replace(/[^a-z0-9_]/g, "_")}`;
    this._bm25 = null;
  }

  async connect() {
    // ⭐ ONE COLLECTION PER TENANT — structural isolation, not a filter
    this.store = new Chroma(this.embeddings, {
      collectionName: this.collectionName,
      url: CHROMA_URL,
      collectionMetadata: { "hnsw:space": "cosine" },
    });
    await this.store.ensureCollection();
    return this;
  }

  async upsert(docs) {
    const existing = new Set((await this.store.collection.get()).ids ?? []);

    const toAdd = [];
    let skipped = 0;
    for (const d of docs) {
      const h = contentHash(d.pageContent);
      if (existing.has(h)) { skipped++; continue; }
      d.metadata.contentHash = h;
      d.metadata.ingestedAt = new Date().toISOString();
      toAdd.push({ h, d });
    }

    if (toAdd.length) {
      await this.store.addDocuments(toAdd.map((x) => x.d), {
        ids: toAdd.map((x) => x.h),         // ⭐ hash AS the id → idempotent upsert
      });
      this._bm25 = null;
    }
    return { added: toAdd.length, skipped };
  }

  async ingestFile(path, chunkSize = 800, overlap = 120) {
    const text = await fs.readFile(path, "utf8");
    const pieces = await new RecursiveCharacterTextSplitter({
      chunkSize, chunkOverlap: overlap,
    }).splitText(text);

    return this.upsert(pieces.map((p, i) => new Document({
      pageContent: p, metadata: { source: path, chunkIndex: i },
    })));
  }

  async deleteSource(source) {
    const found = await this.store.collection.get({ where: { source } });
    const ids = found.ids ?? [];
    if (ids.length) {
      await this.store.delete({ ids });
      this._bm25 = null;
    }
    return ids.length;
  }

  async ensureBm25() {
    if (!this._bm25) {
      const raw = await this.store.collection.get();
      const docs = (raw.documents ?? []).map((t, i) =>
        new Document({ pageContent: t, metadata: raw.metadatas?.[i] ?? {} }));
      this._bm25 = docs.length ? new BM25(docs) : null;
    }
    return this._bm25;
  }

  async search(query, { k = 4, mode = "hybrid", where = undefined } = {}) {
    if (mode === "vector") return this.store.similaritySearch(query, k, where);

    if (mode === "keyword") {
      const bm25 = await this.ensureBm25();
      return bm25 ? bm25.search(query, k).map((r) => r.doc) : [];
    }

    const vec = await this.store.similaritySearch(query, k * 2, where);
    const bm25 = await this.ensureBm25();
    const kw = bm25 ? bm25.search(query, k * 2).map((r) => r.doc) : [];

    const scores = new Map();
    for (const list of [vec, kw]) {
      list.forEach((doc, rank) => {
        const key = doc.pageContent;
        const entry = scores.get(key) ?? { doc, score: 0 };
        entry.score += 1 / (60 + rank + 1);
        scores.set(key, entry);
      });
    }

    return [...scores.values()].sort((a, b) => b.score - a.score).slice(0, k).map((r) => r.doc);
  }

  async stats() {
    const raw = await this.store.collection.get();
    const sources = {};
    for (const m of raw.metadatas ?? []) {
      const src = m.source ?? "(unknown)";
      sources[src] = (sources[src] ?? 0) + 1;
    }
    return { tenant: this.tenant, chunks: (raw.ids ?? []).length, sources };
  }
}
```

**Seven production behaviours worth naming:**

1. **One collection per tenant.** Cross-tenant leakage is structurally impossible, not one buggy
   filter away. This is the correct answer to Exercise 2's lesson, and it's a security decision
   before it's a performance one.
2. **The content hash *is* the document ID.** That makes `upsert` idempotent for free: re-ingest
   the same file and Chroma overwrites the same IDs rather than creating duplicates. Very few
   tutorials do this and it eliminates an entire class of bug.
3. **Delete-by-source exists.** Documents get removed from wikis and drives; if you never delete
   their vectors, your assistant confidently cites content that no longer exists. This is the
   most commonly missing operation in hand-rolled ingest pipelines.
4. **The BM25 index is invalidated on write** (`this._bm25 = null`) and rebuilt lazily. A stale
   keyword index that silently misses new documents is a nasty, hard-to-spot bug.
5. **Hybrid over-fetches (`k * 2`) before fusing**, so RRF has enough candidates to work with.
6. **Stats by source** tell you whether an ingest actually landed — the first thing you want when
   someone reports "it can't find the new policy doc".
7. **The embedding model name is baked into the content hash**, so switching models produces
   entirely new IDs rather than silently reusing vectors from a different space (Day 10's rule).

**What's still missing for real production** — and worth saying in an interview: the BM25 index
lives in process memory and is rebuilt from a full collection scan, which won't survive multiple
API replicas or scale past a few hundred thousand chunks. At that point you move keyword search
into the database itself — Postgres full-text search alongside pgvector, or a store with native
hybrid support like Weaviate or Qdrant. There's also no batching of Chroma writes, no retry
around the embedding calls, and no metrics.
</details>

---

## 9. Interview questions

### Basic

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

### Intermediate

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

### Advanced

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

## 10. Recap

- ✅ Exact search is O(n) — fine under ~10k vectors, hopeless above
- ✅ **HNSW** = layered proximity graph, ~O(log n); `ef` is the runtime recall/latency dial (must be ≥ k)
- ✅ **IVF** = cluster then search the nearest clusters; `nprobe` is the dial
- ✅ "Approximate" means 95–99% recall — nearly always fine for retrieval
- ✅ **Pre-filter vs post-filter** — post-filtering starves selective queries; verify your store
- ✅ **Partition per tenant** rather than relying on filters — structural isolation
- ✅ pgvector is the under-rated default if you already run Postgres
- ✅ Filter syntax is store-specific and does not port — isolate it
- ✅ **Hybrid search (vectors + BM25, fused with RRF)** fixes the exact-identifier failure
- ✅ Deletion and incremental upsert are part of the ingest contract, not extras

### Tomorrow

**[Day 12 — Naive RAG end-to-end](day-12-naive-rag.md)**: every piece is now in place — chunks,
embeddings, a store, retrieval. Tomorrow you assemble the full pipeline: PDF → split → embed →
store → retrieve → answer **with citations**. Then you deliberately break it in six different
ways and diagnose each one, which is the fastest way to learn what actually matters.

### Quick self-check

1. You ask for `k=10` filtered to a tenant owning 2% of documents, and get 1 result. What's happening?
2. Why does `ef = k` give poor recall?
3. Your users search by error code and get the wrong code's documentation. What's the fix?

<details>
<summary>Answers</summary>

1. Your store is **post-filtering** — it ran the ANN search first, returned the global top 10,
   then discarded everything not matching the tenant. Fix: use a store that pre-filters,
   over-fetch by roughly `1/selectivity` and filter yourself, or (best) partition into a
   per-tenant collection.
2. HNSW's bottom-layer search keeps a result heap of size `ef` and returns the top `k` from it.
   With `ef = k` there's no room to explore beyond what you'll return, so the greedy traversal
   can't recover from entering a poor region. Use `ef ≥ 2×k` and tune against a measured curve.
3. **Hybrid search.** Embeddings encode `ERR_4471` and `ERR_4472` as "an error code" and score
   them nearly identically. BM25 treats them as distinct rare tokens and matches exactly. Fuse
   both rankings with RRF.
</details>
