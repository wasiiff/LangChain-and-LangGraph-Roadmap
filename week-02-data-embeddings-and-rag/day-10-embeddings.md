# Day 10 — Embeddings: Vectors, Similarity & Model Choice

> ⏱ **Time:** ~2.5 hours · 🎯 **Prereqs:** [Day 09](day-09-documents-and-splitting.md) · 🧩 **Difficulty:** ●●●○○

**Today you learn:** what an embedding actually *is*, the three similarity metrics worked out by
hand, how to choose an embedding model, and the practical concerns — dimensions, cost, batching,
caching, normalisation — that decide whether your retrieval is fast and cheap or slow and
expensive.

By the end you'll have built a working semantic search engine with no vector database at all.

---

## 1. The problem

You have 400 well-formed chunks from yesterday. A user asks:

> *"How long before I get my money back?"*

Now find the chunk that says:

> *"Refunds are processed within 5 business days of approval."*

**Keyword search fails completely.** Count the shared words: "how", "long", "before", "I", "get",
"my", "money", "back" versus "refunds", "processed", "within", "5", "business", "days",
"approval". The overlap is *zero*. Not one content word matches.

Yet any human sees instantly that these are about the same thing.

```
   KEYWORD SEARCH                     SEMANTIC SEARCH
   ──────────────                     ───────────────
   matches CHARACTERS                 matches MEANING

   "money back"  ✗  "refund"          "money back"  ✓  "refund"
   "car"         ✗  "automobile"      "car"         ✓  "automobile"
   "NYC"         ✗  "New York City"   "NYC"         ✓  "New York City"

   ✓ exact IDs: "ERR_4471"            ✗ exact IDs: often misses
   ✓ rare terms, part numbers         ✗ can confuse similar-but-opposite
   ✓ instant, no model needed         ✗ needs an embedding call
```

Embeddings are how you get the right-hand column. (And note the bottom rows — that's why
production systems use *both*, which is Day 11's hybrid search.)

---

## 2. Mental model

### What an embedding is

```
   "refund"  ──▶ [ 0.21, -0.48, 0.77, ..., 0.03 ]   768 numbers
   "money back" ▶ [ 0.19, -0.51, 0.74, ..., 0.05 ]   768 numbers
                       ↑ almost the same numbers ↑

   "pizza"   ──▶ [-0.62, 0.11, -0.30, ..., 0.88 ]   768 very different numbers
```

An embedding is a **point in high-dimensional space** where distance means dissimilarity. Every
piece of text becomes a point; texts about similar things land near each other.

> 🧠 **Analogy.** Think of a map of a country. Every town has a (latitude, longitude) — two
> numbers. Towns near each other on the map are near each other in reality. An embedding is the
> same idea with 768 or 1536 coordinates instead of 2, and "nearness" means *similar meaning*
> instead of *physical proximity*.
>
> You can't picture 768 dimensions. You don't need to — all the maths works exactly the same as
> it does in 2D.

### The three similarity metrics

```
              B
             ╱│
            ╱ │
           ╱  │          COSINE     — the ANGLE between them  (ignores length)
          ╱   │          EUCLIDEAN  — the straight-line DISTANCE
         ╱ θ  │          DOT PRODUCT — angle AND length combined
        ╱_____│
       O       A


   COSINE                    EUCLIDEAN                 DOT PRODUCT
   cos(θ) = A·B / (|A||B|)   √Σ(aᵢ-bᵢ)²                A·B = Σ aᵢbᵢ

   range: -1 to 1            range: 0 to ∞             range: -∞ to ∞
   1 = identical direction   0 = identical             bigger = more similar
   0 = unrelated             bigger = more different
   -1 = opposite

   ✅ THE DEFAULT           ✅ when magnitude matters  ✅ fastest to compute
```

**The crucial fact that makes this simple:** most modern embedding models return
**normalised** vectors (length exactly 1). When vectors are normalised:

```
   cosine similarity  ==  dot product        (identical results)
   cosine ranking     ==  euclidean ranking  (same order, different numbers)
```

So for normalised embeddings, *the choice of metric doesn't change which documents you retrieve*
— only the numbers you see. Use cosine, understand why, and move on.

### The pipeline

```
   INGEST (once)                          QUERY (every request)
   ─────────────                          ─────────────────────
   chunks                                 "how long for my money back?"
     │ embed (batched)                      │ embed (1 call)
     ▼                                      ▼
   [[0.2,...], [0.9,...], ...]            [0.21, ...]
     │                                      │
     └──────────► store ◄──────────────────┘
                    │  compare query vector to all chunk vectors
                    ▼
                 top-k most similar chunks
```

---

## 3. First principles

### 3.1 Where embeddings come from

An embedding model is a neural network trained so that **texts with similar meaning produce
nearby vectors**. Training typically uses pairs known to be related — a question and its answer,
a title and its article, two paraphrases — and pushes their vectors together while pushing
unrelated pairs apart (contrastive learning).

The consequence that matters practically: **an embedding model is only good at the kind of
similarity it was trained on.** A model trained on question→passage pairs is good at retrieval.
A model trained on sentence paraphrases is good at deduplication. They're not interchangeable,
which is why benchmark scores are task-specific.

### 3.2 Cosine similarity, by hand

Take two tiny 3-dimensional vectors:

```
A = [1, 2, 3]
B = [2, 4, 6]        ← exactly 2× A: same DIRECTION, different LENGTH
```

**Dot product:** multiply element-wise, sum.

```
A·B = (1×2) + (2×4) + (3×6) = 2 + 8 + 18 = 28
```

**Magnitudes:** square root of the sum of squares.

```
|A| = √(1² + 2² + 3²) = √14  ≈ 3.742
|B| = √(2² + 4² + 6²) = √56  ≈ 7.483
```

**Cosine:**

```
cos = 28 / (3.742 × 7.483) = 28 / 28.0 = 1.0
```

**Exactly 1.0** — perfectly similar, because they point the same way. That's the key property:
cosine ignores magnitude. `[1,2,3]` and `[100,200,300]` are identical in direction, and for text
that's what you want — a long document about refunds and a short sentence about refunds should
match.

**Euclidean on the same pair:**

```
√((1-2)² + (2-4)² + (3-6)²) = √(1 + 4 + 9) = √14 ≈ 3.742
```

Not zero — euclidean says they're *different*, because it cares about length. This is why
euclidean on un-normalised text embeddings behaves oddly: a longer document gets a
longer vector and looks "further away" purely because of length.

### 3.3 Normalisation

Normalising means scaling a vector to length 1 while keeping its direction:

```
Â = A / |A| = [1, 2, 3] / 3.742 = [0.267, 0.535, 0.802]
```

Check: `√(0.267² + 0.535² + 0.802²) = 1.0` ✅

Once both vectors are normalised, `|A| = |B| = 1`, so:

```
cos = A·B / (1 × 1) = A·B
```

The cosine **is** the dot product. That's why vector databases store normalised vectors and use
dot product — it's the same answer with fewer operations.

> ⚠️ **Check whether your model normalises.** OpenAI and most modern models return normalised
> vectors. Some local/HuggingFace models don't. If yours doesn't and you use dot product, long
> documents will dominate your results for no good reason. Exercise 1 shows how to check in one
> line.

### 3.4 Dimensions

| Dimensions | Typical models | Trade-off |
|---|---|---|
| 384 | all-MiniLM, BGE-small | Fastest, smallest, slightly weaker |
| 768 | nomic-embed-text, BGE-base | **Sweet spot for most work** |
| 1024 | BGE-large, Voyage | Better quality, 33% more storage |
| 1536 | OpenAI text-embedding-3-small | Strong, widely supported |
| 3072 | OpenAI text-embedding-3-large | Best quality, 4× the storage of 768 |

Storage maths, so it's concrete:

```
1,000,000 chunks × 768 dims × 4 bytes (float32) = 3.07 GB
1,000,000 chunks × 3072 dims × 4 bytes          = 12.3 GB
```

Plus index overhead (often 1.5–2×). Dimensions also drive **query latency** — every comparison
touches every dimension.

**Matryoshka embeddings** are worth knowing about: some models (OpenAI v3, Nomic) are trained so
you can *truncate* the vector and keep most of the quality. Ask for 1536 dimensions from a
3072-dim model and lose only a little accuracy. That's a real lever when storage matters.

### 3.5 Choosing a model

| Model | Dims | Cost | Notes |
|---|---|---|---|
| **`nomic-embed-text`** (Ollama) | 768 | **free, local** | Our default. Good quality, 8K context |
| `all-MiniLM-L6-v2` | 384 | free, local | Tiny and fast; weaker but often enough |
| **`text-embedding-004`** (Google) | 768 | free tier | Our cloud default |
| `gemini-embedding-001` (Google) | 3072 | free tier | Higher quality, truncatable |
| `text-embedding-3-small` (OpenAI) | 1536 | $0.02/1M | Excellent baseline, very widely used |
| `text-embedding-3-large` (OpenAI) | 3072 | $0.13/1M | Best-in-class general purpose |
| `voyage-3` (Voyage) | 1024 | paid | Often tops retrieval benchmarks |
| `BGE-M3` | 1024 | free, local | Multilingual, strong |

**How to choose, in order of importance:**

1. **Does it handle your language?** Most models are English-first. For multilingual content,
   BGE-M3 or Cohere multilingual are meaningfully better.
2. **Does it handle your domain?** Code, legal and medical text have specialised models that beat
   general ones substantially.
3. **What's your context limit?** If your chunks are 2000 tokens and the model truncates at 512,
   you're silently discarding most of every chunk. This is a common, invisible bug.
4. **Cost and latency at your volume.** Embedding 10M chunks is a real bill.
5. **Benchmark scores** (MTEB) — useful but *last*, because they're averages over tasks that may
   not resemble yours.

> 🚨 **The rule that will save you a re-index:** you cannot mix embedding models. Vectors from
> different models are in different spaces and comparing them is meaningless. Changing model
> means **re-embedding everything**. Choose deliberately, and record the model name in your
> store's metadata so you can detect a mismatch.

### 3.6 Asymmetric search: queries vs documents

A subtle but important point. In retrieval, the query and the document are *different kinds of
text*:

```
query:    "how long for a refund?"          ← short, a question
document: "Refunds are processed within…"   ← longer, a statement
```

Some models are trained for this asymmetry and expect a **prefix** telling them which side
they're embedding:

```
nomic-embed-text:   "search_query: how long for a refund?"
                    "search_document: Refunds are processed within…"

BGE:                "Represent this sentence for searching relevant passages: {query}"
                    (documents get no prefix)
```

**Using the wrong prefix, or none, measurably degrades retrieval.** LangChain's integrations
usually handle this via `embedQuery` vs `embedDocuments` — which is exactly why those are two
separate methods rather than one.

> 🔑 **This is the answer to "why does the embeddings interface have two methods?"** It's not
> just batching convenience. `embedQuery` and `embedDocuments` can apply different prefixes,
> and for asymmetric models they produce different vectors for identical text.

### 3.7 The embeddings interface

```js
embeddings.embedQuery("text")            // → number[]        one query
embeddings.embedDocuments(["a", "b"])    // → number[][]      batched documents
```

```python
embeddings.embed_query("text")           # → list[float]
embeddings.embed_documents(["a", "b"])   # → list[list[float]]
```

Always use `embedDocuments` for bulk work — it batches into far fewer HTTP requests.

### 3.8 Caching

Embedding the same text twice is pure waste. Two levels:

- **Ingest-time:** hash the chunk text; skip anything already embedded (Day 09's `contentHash`).
- **Query-time:** cache query embeddings. In support-style traffic, repeated questions are common.

LangChain ships `CacheBackedEmbeddings` for this, shown in §4.5 / §5.5.

---

## 4. Code — JavaScript

```bash
npm install langchain @langchain/core @langchain/ollama @langchain/google-genai \
            @langchain/classic dotenv
```

For local, free embeddings (recommended for this whole week):

```bash
ollama pull nomic-embed-text
```

### 4.1 Your first embedding

```js
// day10-first.js
import "dotenv/config";
import { OllamaEmbeddings } from "@langchain/ollama";

const embeddings = new OllamaEmbeddings({ model: "nomic-embed-text" });

const vector = await embeddings.embedQuery("How long until I get a refund?");

console.log("dimensions:", vector.length);              // 768
console.log("first 8:", vector.slice(0, 8).map((v) => v.toFixed(4)));

// Is it normalised? (length should be ~1.0 if so)
const magnitude = Math.sqrt(vector.reduce((s, v) => s + v * v, 0));
console.log("magnitude:", magnitude.toFixed(6),
            magnitude > 0.99 && magnitude < 1.01 ? "→ normalised ✅" : "→ NOT normalised ⚠️");
```

<details>
<summary>☁️ Using Google Gemini embeddings instead (no local install)</summary>

```js
import { GoogleGenerativeAIEmbeddings } from "@langchain/google-genai";

const embeddings = new GoogleGenerativeAIEmbeddings({
  model: "text-embedding-004",          // 768 dims, free tier
});
```
Everything else in this file is identical — that's the `Embeddings` interface doing its job.
</details>

### 4.2 The three metrics, implemented

```js
// day10-metrics.js
export const dot = (a, b) => a.reduce((s, v, i) => s + v * b[i], 0);

export const magnitude = (a) => Math.sqrt(a.reduce((s, v) => s + v * v, 0));

export const cosine = (a, b) => dot(a, b) / (magnitude(a) * magnitude(b));

export const euclidean = (a, b) =>
  Math.sqrt(a.reduce((s, v, i) => s + (v - b[i]) ** 2, 0));

export const normalise = (a) => {
  const m = magnitude(a);
  return m === 0 ? a : a.map((v) => v / m);
};

// ── prove the hand-worked example from §3.2 ──────────────────────────────
const A = [1, 2, 3];
const B = [2, 4, 6];        // exactly 2× A

console.log("A·B        =", dot(A, B));                    // 28
console.log("|A|        =", magnitude(A).toFixed(3));      // 3.742
console.log("|B|        =", magnitude(B).toFixed(3));      // 7.483
console.log("cosine     =", cosine(A, B).toFixed(6));      // 1.000000  ← same direction
console.log("euclidean  =", euclidean(A, B).toFixed(3));   // 3.742     ← different length

// ── after normalising, cosine == dot product ─────────────────────────────
const An = normalise(A), Bn = normalise(B);
console.log("\nnormalised A:", An.map((v) => v.toFixed(3)));
console.log("dot(Ân,B̂n) =", dot(An, Bn).toFixed(6));       // 1.000000
console.log("cos(Ân,B̂n) =", cosine(An, Bn).toFixed(6));    // 1.000000  ← identical
```

### 4.3 Semantic vs keyword search

```js
// day10-semantic-vs-keyword.js
import "dotenv/config";
import { OllamaEmbeddings } from "@langchain/ollama";
import { cosine } from "./day10-metrics.js";

const embeddings = new OllamaEmbeddings({ model: "nomic-embed-text" });

const CHUNKS = [
  "Refunds are processed within 5 business days of approval by the billing team.",
  "Our offices are located in Manchester and Leeds.",
  "Domestic orders ship within 2 business days.",
  "To reset your password, click the 'Forgot password' link on the sign-in page.",
  "The API returns HTTP 429 when you exceed the rate limit.",
];

const QUERY = "how long until I get my money back?";

// ── keyword score: word overlap ──────────────────────────────────────────
const words = (s) => new Set(s.toLowerCase().match(/[a-z]+/g) ?? []);
const keywordScore = (q, d) => {
  const qw = words(q), dw = words(d);
  return [...qw].filter((w) => dw.has(w)).length / qw.size;
};

// ── semantic score: cosine of embeddings ─────────────────────────────────
const [queryVec, ...docVecs] = await Promise.all([
  embeddings.embedQuery(QUERY),
  ...CHUNKS.map((c) => embeddings.embedQuery(c)),
]);

console.log(`query: "${QUERY}"\n`);
console.log("keyword  semantic  chunk");
console.log("-".repeat(80));

CHUNKS.map((c, i) => ({
  chunk: c,
  keyword: keywordScore(QUERY, c),
  semantic: cosine(queryVec, docVecs[i]),
}))
  .sort((a, b) => b.semantic - a.semantic)
  .forEach((r) =>
    console.log(
      `${r.keyword.toFixed(2).padStart(7)}  ${r.semantic.toFixed(3).padStart(8)}  ` +
      `${r.chunk.slice(0, 60)}`
    )
  );
```

The refund chunk scores **0.00 on keywords** and highest on semantics. That gap is the entire
reason embeddings exist.

### 4.4 embedQuery vs embedDocuments

```js
// day10-query-vs-documents.js
import "dotenv/config";
import { OllamaEmbeddings } from "@langchain/ollama";
import { cosine } from "./day10-metrics.js";

const embeddings = new OllamaEmbeddings({ model: "nomic-embed-text" });

const TEXT = "Refunds are processed within 5 business days.";

const asQuery = await embeddings.embedQuery(TEXT);
const [asDocument] = await embeddings.embedDocuments([TEXT]);

const same = cosine(asQuery, asDocument);
console.log(`same text, both methods → cosine = ${same.toFixed(6)}`);
console.log(same > 0.9999
  ? "identical — this model is SYMMETRIC"
  : "different — this model is ASYMMETRIC (applies query/document prefixes)");

// ── batching matters for speed ───────────────────────────────────────────
const DOCS = Array.from({ length: 30 }, (_, i) => `Document number ${i} about topic ${i % 7}.`);

let t0 = Date.now();
for (const d of DOCS) await embeddings.embedQuery(d);      // ❌ 30 round trips
const oneByOne = Date.now() - t0;

t0 = Date.now();
await embeddings.embedDocuments(DOCS);                      // ✅ batched
const batched = Date.now() - t0;

console.log(`\none-by-one: ${oneByOne}ms · batched: ${batched}ms · ` +
            `${(oneByOne / batched).toFixed(1)}× faster`);
```

### 4.5 Caching embeddings

```js
// day10-cache.js
import "dotenv/config";
import { OllamaEmbeddings } from "@langchain/ollama";
import { CacheBackedEmbeddings } from "@langchain/classic/embeddings/cache_backed";
import { InMemoryStore } from "@langchain/classic/storage/in_memory";

const underlying = new OllamaEmbeddings({ model: "nomic-embed-text" });
const store = new InMemoryStore();

const cached = CacheBackedEmbeddings.fromBytesStore(underlying, store, {
  namespace: underlying.model,        // ⚠️ namespace by MODEL — never mix vector spaces
});

const DOCS = [
  "Refunds take 5 business days.",
  "Shipping takes 2 days domestically.",
  "Support is open 9-6 GMT.",
];

let t0 = Date.now();
await cached.embedDocuments(DOCS);
console.log(`first pass  (cold): ${Date.now() - t0}ms`);

t0 = Date.now();
await cached.embedDocuments(DOCS);
console.log(`second pass (warm): ${Date.now() - t0}ms   ← served from cache`);

const keys = [];
for await (const k of store.yieldKeys()) keys.push(k);
console.log(`cached vectors: ${keys.length}`);
```

> ⚠️ **The `namespace` is not optional.** Without it, switching embedding models would return
> the *old* model's cached vectors for the same text — silently corrupting your index with mixed
> vector spaces. Always namespace by model name.

### 4.6 A complete semantic search engine — no database

```js
// day10-search-engine.js
import "dotenv/config";
import { OllamaEmbeddings } from "@langchain/ollama";
import { Document } from "@langchain/core/documents";
import { cosine } from "./day10-metrics.js";

class TinyVectorStore {
  constructor(embeddings) {
    this.embeddings = embeddings;
    this.vectors = [];
    this.documents = [];
  }

  async addDocuments(docs) {
    const texts = docs.map((d) => d.pageContent);
    const vecs = await this.embeddings.embedDocuments(texts);   // batched
    this.vectors.push(...vecs);
    this.documents.push(...docs);
  }

  async search(query, k = 3, filter = null) {
    const q = await this.embeddings.embedQuery(query);

    return this.documents
      .map((doc, i) => ({ doc, score: cosine(q, this.vectors[i]) }))
      .filter(({ doc }) => !filter || filter(doc))       // metadata filtering (Day 09!)
      .sort((a, b) => b.score - a.score)
      .slice(0, k);
  }
}

// ── build ────────────────────────────────────────────────────────────────
const store = new TinyVectorStore(new OllamaEmbeddings({ model: "nomic-embed-text" }));

await store.addDocuments([
  new Document({ pageContent: "Refunds are processed within 5 business days of approval.",
                 metadata: { section: "Refunds", dept: "billing" } }),
  new Document({ pageContent: "Basic plans allow refunds within 30 days; Pro within 60 days.",
                 metadata: { section: "Refunds", dept: "billing" } }),
  new Document({ pageContent: "Domestic orders ship within 2 business days.",
                 metadata: { section: "Shipping", dept: "ops" } }),
  new Document({ pageContent: "International orders take 10-14 days and may incur customs fees.",
                 metadata: { section: "Shipping", dept: "ops" } }),
  new Document({ pageContent: "Support is available 9am-6pm GMT, Monday to Friday.",
                 metadata: { section: "Support", dept: "ops" } }),
  new Document({ pageContent: "The API returns HTTP 429 when the rate limit is exceeded.",
                 metadata: { section: "API", dept: "eng" } }),
]);

// ── query ────────────────────────────────────────────────────────────────
for (const q of [
  "how long until I get my money back?",
  "when will my parcel arrive abroad?",
  "can I reach someone on Saturday?",
]) {
  console.log(`\n❓ ${q}`);
  for (const { doc, score } of await store.search(q, 2)) {
    console.log(`   ${score.toFixed(3)}  [${doc.metadata.section}] ${doc.pageContent.slice(0, 58)}`);
  }
}

// ── metadata filtering ───────────────────────────────────────────────────
console.log(`\n❓ "delivery time" (filtered to dept=ops)`);
for (const { doc, score } of await store.search("delivery time", 2, (d) => d.metadata.dept === "ops")) {
  console.log(`   ${score.toFixed(3)}  [${doc.metadata.section}] ${doc.pageContent.slice(0, 58)}`);
}
```

**You just built a vector store.** Tomorrow's real ones add persistence, approximate indexes for
speed at scale, and native metadata filtering — but this is the whole idea.

---

## 5. Code — Python

```bash
pip install langchain langchain-classic langchain-ollama langchain-google-genai \
            numpy python-dotenv
```

### 5.1 Your first embedding

```python
# day10_first.py
import math
from dotenv import load_dotenv
from langchain_ollama import OllamaEmbeddings

load_dotenv()
embeddings = OllamaEmbeddings(model="nomic-embed-text")

vector = embeddings.embed_query("How long until I get a refund?")

print("dimensions:", len(vector))                     # 768
print("first 8:", [round(v, 4) for v in vector[:8]])

# Is it normalised? (length should be ~1.0 if so)
magnitude = math.sqrt(sum(v * v for v in vector))
print(f"magnitude: {magnitude:.6f}",
      "→ normalised ✅" if 0.99 < magnitude < 1.01 else "→ NOT normalised ⚠️")
```

<details>
<summary>☁️ Using Google Gemini embeddings instead (no local install)</summary>

```python
from langchain_google_genai import GoogleGenerativeAIEmbeddings

embeddings = GoogleGenerativeAIEmbeddings(
    model="models/text-embedding-004",     # 768 dims, free tier
)
```
Everything else is identical — that's the `Embeddings` interface doing its job.
</details>

### 5.2 The three metrics, implemented

```python
# day10_metrics.py
import math

def dot(a, b):
    return sum(x * y for x, y in zip(a, b))

def magnitude(a):
    return math.sqrt(sum(x * x for x in a))

def cosine(a, b):
    return dot(a, b) / (magnitude(a) * magnitude(b))

def euclidean(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

def normalise(a):
    m = magnitude(a)
    return a if m == 0 else [x / m for x in a]

if __name__ == "__main__":
    # ── prove the hand-worked example from §3.2 ──────────────────────────
    A = [1, 2, 3]
    B = [2, 4, 6]        # exactly 2× A

    print("A·B        =", dot(A, B))                    # 28
    print(f"|A|        = {magnitude(A):.3f}")           # 3.742
    print(f"|B|        = {magnitude(B):.3f}")           # 7.483
    print(f"cosine     = {cosine(A, B):.6f}")           # 1.000000  ← same direction
    print(f"euclidean  = {euclidean(A, B):.3f}")        # 3.742     ← different length

    # ── after normalising, cosine == dot product ─────────────────────────
    An, Bn = normalise(A), normalise(B)
    print("\nnormalised A:", [round(v, 3) for v in An])
    print(f"dot(Ân,B̂n) = {dot(An, Bn):.6f}")            # 1.000000
    print(f"cos(Ân,B̂n) = {cosine(An, Bn):.6f}")         # 1.000000  ← identical
```

> 💡 **In production use numpy**, not loops — it's 50–100× faster:
> ```python
> import numpy as np
> a, b = np.array(vec_a), np.array(vec_b)
> cos = a @ b / (np.linalg.norm(a) * np.linalg.norm(b))
> ```
> For a whole corpus at once: `matrix @ query / (norms * np.linalg.norm(query))` scores every
> document in one vectorised operation.

### 5.3 Semantic vs keyword search

```python
# day10_semantic_vs_keyword.py
import re
from dotenv import load_dotenv
from langchain_ollama import OllamaEmbeddings
from day10_metrics import cosine

load_dotenv()
embeddings = OllamaEmbeddings(model="nomic-embed-text")

CHUNKS = [
    "Refunds are processed within 5 business days of approval by the billing team.",
    "Our offices are located in Manchester and Leeds.",
    "Domestic orders ship within 2 business days.",
    "To reset your password, click the 'Forgot password' link on the sign-in page.",
    "The API returns HTTP 429 when you exceed the rate limit.",
]

QUERY = "how long until I get my money back?"

# ── keyword score: word overlap ──────────────────────────────────────────
words = lambda s: set(re.findall(r"[a-z]+", s.lower()))

def keyword_score(q, d):
    qw, dw = words(q), words(d)
    return len(qw & dw) / len(qw)

# ── semantic score: cosine of embeddings ─────────────────────────────────
query_vec = embeddings.embed_query(QUERY)
doc_vecs = embeddings.embed_documents(CHUNKS)

print(f'query: "{QUERY}"\n')
print("keyword  semantic  chunk")
print("-" * 80)

rows = [
    {"chunk": c, "keyword": keyword_score(QUERY, c), "semantic": cosine(query_vec, doc_vecs[i])}
    for i, c in enumerate(CHUNKS)
]

for r in sorted(rows, key=lambda r: -r["semantic"]):
    print(f"{r['keyword']:>7.2f}  {r['semantic']:>8.3f}  {r['chunk'][:60]}")
```

### 5.4 embed_query vs embed_documents

```python
# day10_query_vs_documents.py
import time
from dotenv import load_dotenv
from langchain_ollama import OllamaEmbeddings
from day10_metrics import cosine

load_dotenv()
embeddings = OllamaEmbeddings(model="nomic-embed-text")

TEXT = "Refunds are processed within 5 business days."

as_query = embeddings.embed_query(TEXT)
as_document = embeddings.embed_documents([TEXT])[0]

same = cosine(as_query, as_document)
print(f"same text, both methods → cosine = {same:.6f}")
print("identical — this model is SYMMETRIC" if same > 0.9999
      else "different — this model is ASYMMETRIC (applies query/document prefixes)")

# ── batching matters for speed ───────────────────────────────────────────
DOCS = [f"Document number {i} about topic {i % 7}." for i in range(30)]

t0 = time.time()
for d in DOCS:
    embeddings.embed_query(d)                    # ❌ 30 round trips
one_by_one = time.time() - t0

t0 = time.time()
embeddings.embed_documents(DOCS)                 # ✅ batched
batched = time.time() - t0

print(f"\none-by-one: {one_by_one * 1000:.0f}ms · batched: {batched * 1000:.0f}ms · "
      f"{one_by_one / batched:.1f}× faster")
```

### 5.5 Caching embeddings

```python
# day10_cache.py
import time
from dotenv import load_dotenv
from langchain_ollama import OllamaEmbeddings
from langchain_core.stores import InMemoryByteStore
from langchain_classic.embeddings import CacheBackedEmbeddings

load_dotenv()
underlying = OllamaEmbeddings(model="nomic-embed-text")
store = InMemoryByteStore()

cached = CacheBackedEmbeddings.from_bytes_store(
    underlying, store,
    namespace=underlying.model,      # ⚠️ namespace by MODEL — never mix vector spaces
)

DOCS = [
    "Refunds take 5 business days.",
    "Shipping takes 2 days domestically.",
    "Support is open 9-6 GMT.",
]

t0 = time.time()
cached.embed_documents(DOCS)
print(f"first pass  (cold): {(time.time() - t0) * 1000:.0f}ms")

t0 = time.time()
cached.embed_documents(DOCS)
print(f"second pass (warm): {(time.time() - t0) * 1000:.0f}ms   ← served from cache")

print(f"cached vectors: {len(list(store.yield_keys()))}")
```

<details>
<summary>💾 Persisting the cache to disk (so it survives restarts)</summary>

```python
from langchain_classic.storage import LocalFileStore

store = LocalFileStore("./.embedding_cache/")
cached = CacheBackedEmbeddings.from_bytes_store(
    underlying, store, namespace=underlying.model
)
```
Now re-running your ingest script costs nothing for unchanged chunks.
</details>

### 5.6 A complete semantic search engine — no database

```python
# day10_search_engine.py
import numpy as np
from dotenv import load_dotenv
from langchain_ollama import OllamaEmbeddings
from langchain_core.documents import Document

load_dotenv()

class TinyVectorStore:
    def __init__(self, embeddings):
        self.embeddings = embeddings
        self.vectors = None          # numpy matrix, shape (n_docs, dims)
        self.documents = []

    def add_documents(self, docs):
        texts = [d.page_content for d in docs]
        vecs = np.array(self.embeddings.embed_documents(texts))    # batched
        self.vectors = vecs if self.vectors is None else np.vstack([self.vectors, vecs])
        self.documents.extend(docs)

    def search(self, query, k=3, filter_fn=None):
        q = np.array(self.embeddings.embed_query(query))

        # Vectorised cosine against EVERY document in one operation.
        norms = np.linalg.norm(self.vectors, axis=1) * np.linalg.norm(q)
        scores = (self.vectors @ q) / np.where(norms == 0, 1, norms)

        pairs = [
            (doc, float(score))
            for doc, score in zip(self.documents, scores)
            if filter_fn is None or filter_fn(doc)       # metadata filtering (Day 09!)
        ]
        return sorted(pairs, key=lambda p: -p[1])[:k]

# ── build ────────────────────────────────────────────────────────────────
store = TinyVectorStore(OllamaEmbeddings(model="nomic-embed-text"))

store.add_documents([
    Document(page_content="Refunds are processed within 5 business days of approval.",
             metadata={"section": "Refunds", "dept": "billing"}),
    Document(page_content="Basic plans allow refunds within 30 days; Pro within 60 days.",
             metadata={"section": "Refunds", "dept": "billing"}),
    Document(page_content="Domestic orders ship within 2 business days.",
             metadata={"section": "Shipping", "dept": "ops"}),
    Document(page_content="International orders take 10-14 days and may incur customs fees.",
             metadata={"section": "Shipping", "dept": "ops"}),
    Document(page_content="Support is available 9am-6pm GMT, Monday to Friday.",
             metadata={"section": "Support", "dept": "ops"}),
    Document(page_content="The API returns HTTP 429 when the rate limit is exceeded.",
             metadata={"section": "API", "dept": "eng"}),
])

# ── query ────────────────────────────────────────────────────────────────
for q in [
    "how long until I get my money back?",
    "when will my parcel arrive abroad?",
    "can I reach someone on Saturday?",
]:
    print(f"\n❓ {q}")
    for doc, score in store.search(q, 2):
        print(f"   {score:.3f}  [{doc.metadata['section']}] {doc.page_content[:58]}")

# ── metadata filtering ───────────────────────────────────────────────────
print('\n❓ "delivery time" (filtered to dept=ops)')
for doc, score in store.search("delivery time", 2,
                               filter_fn=lambda d: d.metadata["dept"] == "ops"):
    print(f"   {score:.3f}  [{doc.metadata['section']}] {doc.page_content[:58]}")
```

### 🔁 JS ↔ Python differences you just saw

| | JavaScript | Python |
|---|---|---|
| Ollama embeddings | `new OllamaEmbeddings({ model })` | `OllamaEmbeddings(model=...)` |
| Google embeddings | `model: "text-embedding-004"` | `model="models/text-embedding-004"` ⚠️ prefix |
| Query | `await embeddings.embedQuery(s)` | `embeddings.embed_query(s)` |
| Documents | `await embeddings.embedDocuments([...])` | `embeddings.embed_documents([...])` |
| Cache class | `@langchain/classic/embeddings/cache_backed` | `langchain_classic.embeddings` |
| Cache factory | `CacheBackedEmbeddings.fromBytesStore(...)` | `CacheBackedEmbeddings.from_bytes_store(...)` |
| Byte store | `InMemoryStore` (`@langchain/classic/storage/in_memory`) | `InMemoryByteStore` (`langchain_core.stores`) |
| Vector maths | manual loops (or a lib) | **numpy** — use it |

> ⚠️ **Google model-name gotcha:** Python needs the `models/` prefix
> (`"models/text-embedding-004"`), JS does not (`"text-embedding-004"`). This trips people up
> constantly when porting code between the two.

---

## 6. Under the hood

### What the model does to your text

```
   "How long for a refund?"
            │
            ▼
     tokenize  →  [2129, 1263, 1111, 1037, 25416, 1029]        (Day 01!)
            │
            ▼
   ┌────────────────────────────────────────┐
   │  transformer encoder                   │
   │  → one vector PER TOKEN                │
   │    [768] [768] [768] [768] [768] [768] │
   └────────────────────────────────────────┘
            │
            ▼
     POOLING  — collapse many token vectors into ONE
            │
            ├── mean pooling   average all token vectors     (most common)
            ├── CLS pooling    take the special [CLS] token
            └── last-token     take the final token           (LLM-based embedders)
            │
            ▼
     NORMALISE  → divide by length so |v| = 1
            │
            ▼
     [0.21, -0.48, 0.77, ..., 0.03]
```

**Two consequences that explain real bugs:**

1. **Pooling is why long chunks dilute.** Averaging 2,000 token vectors covering five topics
   produces a vector near the centroid of all five — close to nothing in particular. That's the
   mechanical reason behind Day 09's chunk-size advice.

2. **Truncation is silent.** If the model's limit is 512 tokens and your chunk is 2,000, most
   models just **drop the rest without an error**. Your chunk's vector represents only its first
   quarter. Always check your model's context limit against your chunk size — this bug is
   invisible until you go looking for it.

### Why cosine and not euclidean

For **normalised** vectors, the two are mathematically linked:

```
euclidean² = |A|² + |B|² - 2(A·B) = 1 + 1 - 2cos = 2(1 - cos)
```

So euclidean distance is a strictly decreasing function of cosine similarity — **the ranking is
identical**. Cosine wins on convention because its range (-1 to 1) is interpretable and it's
what nearly all documentation and vector stores assume.

For **un-normalised** vectors they genuinely differ, and euclidean will favour documents of
similar *length* to the query — almost never what you want in retrieval.

### Why the numbers cluster around 0.5–0.9

New users are often puzzled that unrelated texts score 0.5 rather than 0.

```
"refund policy"  vs  "pizza toppings"     →  cosine ≈ 0.45
```

Real embedding spaces are **anisotropic** — the vectors don't spread evenly over the whole
sphere; they occupy a narrow cone. So even unrelated text shares a baseline similarity.

**The practical implication:** an absolute threshold like `score > 0.8` is model-specific and
brittle. What matters is the *relative* ranking and the *gap* between the top result and the
rest. If you must threshold, calibrate it on your own data and re-calibrate whenever you change
models.

### Cost at scale

| Corpus | Model | One-off ingest cost |
|---|---|---|
| 10k chunks (~5M tokens) | OpenAI 3-small ($0.02/1M) | ~$0.10 |
| 1M chunks (~500M tokens) | OpenAI 3-small | ~$10 |
| 1M chunks | OpenAI 3-large ($0.13/1M) | ~$65 |
| 1M chunks | Ollama local | $0 + your GPU time |

Ingest is a one-off; **queries are forever**. One embedding per query is cheap individually but
at 1M queries/day it adds up, which is why query-embedding caches earn their keep.

---

## 7. Common mistakes

**❌ Mixing embedding models**

Vectors from different models live in different spaces. Comparing them produces meaningless
numbers — and no error.
✅ One model per index. Store the model name in metadata. Changing model = full re-index.

---

**❌ Using `embedQuery` in a loop for bulk work**

```js
for (const d of docs) await embeddings.embedQuery(d);   // N round trips
```
✅ `embedDocuments(docs)` — batched, often 10× faster, and applies document-side prefixes.

---

**❌ Chunks longer than the model's context limit**

A 2,000-token chunk in a 512-token model is silently truncated to its first 512 tokens.
✅ Check the limit. Keep chunks comfortably under it.

---

**❌ Absolute similarity thresholds copied from a blog post**

`if (score > 0.8)` — thresholds are model-specific and shift with anisotropy.
✅ Rank relatively, take top-k, and calibrate any threshold on your own data.

---

**❌ Assuming cosine 0.0 means "unrelated"**

Unrelated text typically scores 0.3–0.5, not 0.
✅ Judge by relative gaps, not absolute values.

---

**❌ Not caching, and re-embedding unchanged content every deploy**

✅ `CacheBackedEmbeddings` with a persistent store, namespaced by model. Content-hash your
chunks (Day 09) and skip unchanged ones.

---

**❌ Forgetting the `namespace` on a cache**

Switch models, and the cache happily returns the old model's vectors for the same text — mixing
vector spaces invisibly.
✅ `namespace: model.name`, always.

---

**❌ Expecting embeddings to handle exact identifiers**

`"ERR_4471"` and `"ERR_4472"` embed almost identically — the model sees them as
"an error code", not as distinct strings.
✅ Hybrid search (Day 11): keyword matching for identifiers, vectors for meaning.

---

**❌ Python: forgetting the `models/` prefix on Google embeddings**

`"text-embedding-004"` fails in Python; it needs `"models/text-embedding-004"`. JS doesn't.

---

## 8. Exercises

### Exercise 1 — Embedding inspector ●○○○○

Write a tool that takes several texts and reports, for each: dimensions, magnitude (is it
normalised?), min/max/mean component values, and a cosine similarity matrix between all pairs.
Include an obvious pair (two paraphrases) and an obvious non-pair.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import "dotenv/config";
import { OllamaEmbeddings } from "@langchain/ollama";
import { cosine, magnitude } from "./day10-metrics.js";

const embeddings = new OllamaEmbeddings({ model: "nomic-embed-text" });

const TEXTS = [
  "How do I get a refund?",
  "What's the process for getting my money back?",   // paraphrase of above
  "Refunds are processed within 5 business days.",
  "The best pizza toppings are mushroom and olive.", // unrelated
  "ERR_4471",
  "ERR_4472",                                        // near-identical string
];

const vecs = await embeddings.embedDocuments(TEXTS);

console.log("── per-text stats ──");
console.log("dims  magnitude  min      max      mean     text");
TEXTS.forEach((t, i) => {
  const v = vecs[i];
  const mean = v.reduce((a, b) => a + b, 0) / v.length;
  console.log(
    `${String(v.length).padStart(4)}  ${magnitude(v).toFixed(4).padStart(9)}  ` +
    `${Math.min(...v).toFixed(4).padStart(7)}  ${Math.max(...v).toFixed(4).padStart(7)}  ` +
    `${mean.toFixed(4).padStart(7)}  ${t.slice(0, 40)}`
  );
});

console.log("\n── cosine similarity matrix ──");
process.stdout.write("      ");
TEXTS.forEach((_, i) => process.stdout.write(`  [${i}]  `));
console.log();

TEXTS.forEach((_, i) => {
  process.stdout.write(`[${i}]   `);
  TEXTS.forEach((_, j) => {
    const s = cosine(vecs[i], vecs[j]);
    const mark = i === j ? " " : s > 0.75 ? "*" : " ";
    process.stdout.write(`${s.toFixed(3)}${mark} `);
  });
  console.log(`  ${TEXTS[i].slice(0, 35)}`);
});
console.log("\n(* = similarity above 0.75)");
```

**Python**
```python
from dotenv import load_dotenv
from langchain_ollama import OllamaEmbeddings
from day10_metrics import cosine, magnitude

load_dotenv()
embeddings = OllamaEmbeddings(model="nomic-embed-text")

TEXTS = [
    "How do I get a refund?",
    "What's the process for getting my money back?",   # paraphrase of above
    "Refunds are processed within 5 business days.",
    "The best pizza toppings are mushroom and olive.", # unrelated
    "ERR_4471",
    "ERR_4472",                                        # near-identical string
]

vecs = embeddings.embed_documents(TEXTS)

print("── per-text stats ──")
print("dims  magnitude  min      max      mean     text")
for t, v in zip(TEXTS, vecs):
    print(f"{len(v):>4}  {magnitude(v):>9.4f}  {min(v):>7.4f}  {max(v):>7.4f}  "
          f"{sum(v) / len(v):>7.4f}  {t[:40]}")

print("\n── cosine similarity matrix ──")
print("      " + "".join(f"  [{i}]  " for i in range(len(TEXTS))))

for i, vi in enumerate(vecs):
    row = f"[{i}]   "
    for vj in vecs:
        s = cosine(vi, vj)
        mark = " " if vi is vj else ("*" if s > 0.75 else " ")
        row += f"{s:.3f}{mark} "
    print(row + f"  {TEXTS[i][:35]}")

print("\n(* = similarity above 0.75)")
```

**What to look for in the output:**

1. **Magnitude ≈ 1.0** → the model normalises. Note it; it means cosine and dot product agree.
2. **`[0]` vs `[1]` ≈ 0.85–0.95** — the paraphrases match strongly despite sharing almost no
   words. That's the whole point of embeddings.
3. **`[3]` (pizza) ≈ 0.4–0.5 against everything** — *not* 0. This is the anisotropy from §6.
   Unrelated does not mean zero.
4. **`[4]` vs `[5]` (ERR_4471 vs ERR_4472) ≈ 0.97+** — nearly identical, despite being different
   error codes. **This is the embedding failure mode that motivates hybrid search.** If a user
   searches for one error code, semantic search cannot reliably distinguish it from the other.

That last row is the most valuable thing in this exercise. It's a concrete, reproducible
demonstration of when *not* to trust embeddings.
</details>

---

### Exercise 2 — Metric comparison ●●○○○

Take a set of documents and one query. Rank the documents three ways: cosine, euclidean, and dot
product — first with the raw vectors, then with explicitly normalised vectors. Show that after
normalisation all three produce the same *ordering*.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import "dotenv/config";
import { OllamaEmbeddings } from "@langchain/ollama";
import { cosine, euclidean, dot, normalise, magnitude } from "./day10-metrics.js";

const embeddings = new OllamaEmbeddings({ model: "nomic-embed-text" });

const DOCS = [
  "Refunds are processed within 5 business days.",
  "Domestic orders ship within 2 business days.",
  "Support is open 9am to 6pm GMT.",
  "The API rate limit is 1000 requests per minute.",
  "You can request your money back within 30 days of purchase.",
];
const QUERY = "how do I get a refund?";

const q = await embeddings.embedQuery(QUERY);
const ds = await embeddings.embedDocuments(DOCS);

console.log(`vectors normalised by the model? |q| = ${magnitude(q).toFixed(4)}\n`);

function rank(label, qv, dvs) {
  const byCosine    = DOCS.map((d, i) => [i, cosine(qv, dvs[i])]).sort((a, b) => b[1] - a[1]);
  const byDot       = DOCS.map((d, i) => [i, dot(qv, dvs[i])]).sort((a, b) => b[1] - a[1]);
  const byEuclidean = DOCS.map((d, i) => [i, euclidean(qv, dvs[i])]).sort((a, b) => a[1] - b[1]);

  console.log(`── ${label} ──`);
  console.log("rank  cosine        dot           euclidean");
  for (let r = 0; r < DOCS.length; r++) {
    console.log(
      `  ${r + 1}   #${byCosine[r][0]} ${byCosine[r][1].toFixed(4)}   ` +
      `#${byDot[r][0]} ${byDot[r][1].toFixed(4)}   ` +
      `#${byEuclidean[r][0]} ${byEuclidean[r][1].toFixed(4)}`
    );
  }

  const orderC = byCosine.map((x) => x[0]).join(",");
  const orderD = byDot.map((x) => x[0]).join(",");
  const orderE = byEuclidean.map((x) => x[0]).join(",");
  console.log(`orders match: cosine==dot ${orderC === orderD ? "✅" : "❌"} · ` +
              `cosine==euclidean ${orderC === orderE ? "✅" : "❌"}\n`);
}

rank("RAW vectors", q, ds);
rank("EXPLICITLY NORMALISED", normalise(q), ds.map(normalise));

console.log("documents:");
DOCS.forEach((d, i) => console.log(`  #${i} ${d}`));
```

**Python**
```python
from dotenv import load_dotenv
from langchain_ollama import OllamaEmbeddings
from day10_metrics import cosine, euclidean, dot, normalise, magnitude

load_dotenv()
embeddings = OllamaEmbeddings(model="nomic-embed-text")

DOCS = [
    "Refunds are processed within 5 business days.",
    "Domestic orders ship within 2 business days.",
    "Support is open 9am to 6pm GMT.",
    "The API rate limit is 1000 requests per minute.",
    "You can request your money back within 30 days of purchase.",
]
QUERY = "how do I get a refund?"

q = embeddings.embed_query(QUERY)
ds = embeddings.embed_documents(DOCS)

print(f"vectors normalised by the model? |q| = {magnitude(q):.4f}\n")

def rank(label, qv, dvs):
    by_cosine    = sorted(((i, cosine(qv, d)) for i, d in enumerate(dvs)), key=lambda x: -x[1])
    by_dot       = sorted(((i, dot(qv, d)) for i, d in enumerate(dvs)),    key=lambda x: -x[1])
    by_euclidean = sorted(((i, euclidean(qv, d)) for i, d in enumerate(dvs)), key=lambda x: x[1])

    print(f"── {label} ──")
    print("rank  cosine        dot           euclidean")
    for r in range(len(DOCS)):
        print(f"  {r + 1}   #{by_cosine[r][0]} {by_cosine[r][1]:.4f}   "
              f"#{by_dot[r][0]} {by_dot[r][1]:.4f}   "
              f"#{by_euclidean[r][0]} {by_euclidean[r][1]:.4f}")

    order_c = [i for i, _ in by_cosine]
    order_d = [i for i, _ in by_dot]
    order_e = [i for i, _ in by_euclidean]
    print(f"orders match: cosine==dot {'✅' if order_c == order_d else '❌'} · "
          f"cosine==euclidean {'✅' if order_c == order_e else '❌'}\n")

rank("RAW vectors", q, ds)
rank("EXPLICITLY NORMALISED", normalise(q), [normalise(d) for d in ds])

print("documents:")
for i, d in enumerate(DOCS):
    print(f"  #{i} {d}")
```

**Expected findings:**

- With a model that already normalises, **all three orderings match even on the raw vectors** —
  because the vectors were already unit length.
- The *numbers* differ wildly (cosine ~0.7, euclidean ~0.75, dot ~0.7) but the *ranking* is
  identical, which is all retrieval cares about.
- Documents `#0` and `#4` both rank top: one says "refunds", the other "money back". Neither
  shares meaningful words with the query, and both are found.

**The takeaway for interviews:** for normalised embeddings the metric choice is a performance
and convention decision, not a quality one. Vector databases use dot product internally because
it's the cheapest operation, and report cosine because it's the interpretable one. The place the
choice *does* matter is un-normalised vectors, where euclidean starts ranking by document length.
</details>

---

### Exercise 3 — Model bake-off ●●●○○

Compare two embedding models on the same retrieval task using an eval set. Measure recall@1 and
recall@3, embedding latency, and dimensions. Reuse the eval-harness idea from Day 09 but with
real embeddings this time.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import "dotenv/config";
import { OllamaEmbeddings } from "@langchain/ollama";
import { GoogleGenerativeAIEmbeddings } from "@langchain/google-genai";
import { cosine } from "./day10-metrics.js";

const CHUNKS = [
  "Customers may request a refund within 30 days for Basic plans and 60 days for Pro plans.",
  "Refunds are processed within 5 business days of approval by the billing team.",
  "Domestic orders ship within 2 business days of dispatch confirmation.",
  "International orders take 10 to 14 days and may incur customs fees.",
  "Users can change their plan from the billing settings page at any time.",
  "Downgrades take effect at the end of the current billing cycle.",
  "Support is available from 9am to 6pm GMT, Monday through Friday.",
  "Enterprise customers have access to a 24/7 emergency support line.",
  "Deleted projects are retained in cold storage for 90 days before permanent deletion.",
  "The API allows 1000 requests per minute for Pro and 100 for Basic accounts.",
  "Exceeding the rate limit returns HTTP 429 with a Retry-After header.",
  "All plans include SSO, audit logs, and role-based access control.",
];

// question → index of the chunk that answers it
const CASES = [
  ["how long until I get my money back?", 1],
  ["can I get a refund on the Pro plan?", 0],
  ["when will my parcel arrive from abroad?", 3],
  ["what happens if I move to a cheaper plan?", 5],
  ["is anyone available at the weekend?", 7],
  ["how long before deleted work is gone forever?", 8],
  ["what error do I get if I send too many requests?", 10],
  ["do you support single sign-on?", 11],
];

const MODELS = {
  "nomic (768d, local)": new OllamaEmbeddings({ model: "nomic-embed-text" }),
  "gemini (768d, cloud)": new GoogleGenerativeAIEmbeddings({ model: "text-embedding-004" }),
};

console.log("model                   dims  ingestMs  queryMs  R@1   R@3");
console.log("-".repeat(66));

for (const [name, embeddings] of Object.entries(MODELS)) {
  try {
    const t0 = Date.now();
    const docVecs = await embeddings.embedDocuments(CHUNKS);
    const ingestMs = Date.now() - t0;

    const t1 = Date.now();
    const queryVecs = await embeddings.embedDocuments(CASES.map((c) => c[0]));
    const queryMs = Math.round((Date.now() - t1) / CASES.length);

    let hits1 = 0, hits3 = 0;
    CASES.forEach(([, correct], ci) => {
      const ranked = docVecs
        .map((dv, i) => ({ i, s: cosine(queryVecs[ci], dv) }))
        .sort((a, b) => b.s - a.s);
      if (ranked[0].i === correct) hits1++;
      if (ranked.slice(0, 3).some((r) => r.i === correct)) hits3++;
    });

    console.log(
      `${name.padEnd(22)}  ${String(docVecs[0].length).padStart(4)}  ` +
      `${String(ingestMs).padStart(8)}  ${String(queryMs).padStart(7)}  ` +
      `${(hits1 / CASES.length).toFixed(2)}  ${(hits3 / CASES.length).toFixed(2)}`
    );
  } catch (e) {
    console.log(`${name.padEnd(22)}  skipped: ${e.message.slice(0, 40)}`);
  }
}
```

**Python**
```python
import time
from dotenv import load_dotenv
from langchain_ollama import OllamaEmbeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from day10_metrics import cosine

load_dotenv()

CHUNKS = [
    "Customers may request a refund within 30 days for Basic plans and 60 days for Pro plans.",
    "Refunds are processed within 5 business days of approval by the billing team.",
    "Domestic orders ship within 2 business days of dispatch confirmation.",
    "International orders take 10 to 14 days and may incur customs fees.",
    "Users can change their plan from the billing settings page at any time.",
    "Downgrades take effect at the end of the current billing cycle.",
    "Support is available from 9am to 6pm GMT, Monday through Friday.",
    "Enterprise customers have access to a 24/7 emergency support line.",
    "Deleted projects are retained in cold storage for 90 days before permanent deletion.",
    "The API allows 1000 requests per minute for Pro and 100 for Basic accounts.",
    "Exceeding the rate limit returns HTTP 429 with a Retry-After header.",
    "All plans include SSO, audit logs, and role-based access control.",
]

# question → index of the chunk that answers it
CASES = [
    ("how long until I get my money back?", 1),
    ("can I get a refund on the Pro plan?", 0),
    ("when will my parcel arrive from abroad?", 3),
    ("what happens if I move to a cheaper plan?", 5),
    ("is anyone available at the weekend?", 7),
    ("how long before deleted work is gone forever?", 8),
    ("what error do I get if I send too many requests?", 10),
    ("do you support single sign-on?", 11),
]

MODELS = {
    "nomic (768d, local)": OllamaEmbeddings(model="nomic-embed-text"),
    "gemini (768d, cloud)": GoogleGenerativeAIEmbeddings(model="models/text-embedding-004"),
}

print("model                   dims  ingestMs  queryMs  R@1   R@3")
print("-" * 66)

for name, embeddings in MODELS.items():
    try:
        t0 = time.time()
        doc_vecs = embeddings.embed_documents(CHUNKS)
        ingest_ms = (time.time() - t0) * 1000

        t1 = time.time()
        query_vecs = embeddings.embed_documents([c[0] for c in CASES])
        query_ms = (time.time() - t1) * 1000 / len(CASES)

        hits1 = hits3 = 0
        for ci, (_, correct) in enumerate(CASES):
            ranked = sorted(
                range(len(doc_vecs)),
                key=lambda i: -cosine(query_vecs[ci], doc_vecs[i]),
            )
            hits1 += ranked[0] == correct
            hits3 += correct in ranked[:3]

        print(f"{name:<22}  {len(doc_vecs[0]):>4}  {ingest_ms:>8.0f}  "
              f"{query_ms:>7.0f}  {hits1 / len(CASES):.2f}  {hits3 / len(CASES):.2f}")
    except Exception as e:
        print(f"{name:<22}  skipped: {str(e)[:40]}")
```

**Typical result:**

```
model                   dims  ingestMs  queryMs  R@1   R@3
------------------------------------------------------------------
nomic (768d, local)      768       340       28  0.88  1.00
gemini (768d, cloud)     768       610       74  0.88  1.00
```

**Four things worth drawing out:**

1. **A free local model matches a cloud model** on a task like this. Reaching for the most
   expensive embedding model by default is a common and costly reflex.
2. **R@3 saturates at 1.00 while R@1 doesn't.** If your pipeline retrieves 3–5 chunks and
   reranks (Day 13), embedding-model choice matters far less than if you retrieve exactly one.
3. **Latency differs by ~3×** — local wins on round-trip time, which matters per query, forever.
4. **Both models fail the same case.** Look at which one: it's usually the query whose phrasing
   is furthest from the document's. That's a *query rewriting* problem (Day 13), not an
   embedding-model problem — and swapping models will never fix it.

**Extend this** with your own corpus and 20+ real questions before committing to a model. The
decision is expensive to reverse: changing models means re-embedding everything.
</details>

---

### Exercise 4 — Semantic deduplication ●●●○○

Build a tool that finds near-duplicate chunks in a corpus using embeddings — the same problem
Day 09's exact content hash *couldn't* solve, because near-duplicates differ by a word or two.
Cluster chunks above a similarity threshold and report the groups.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import "dotenv/config";
import { OllamaEmbeddings } from "@langchain/ollama";
import { cosine } from "./day10-metrics.js";

const embeddings = new OllamaEmbeddings({ model: "nomic-embed-text" });

const CHUNKS = [
  "Refunds are processed within 5 business days of approval.",
  "Refunds are processed within five business days after approval.",   // near-dup of 0
  "Refund requests are handled within 5 working days once approved.",  // near-dup of 0
  "Domestic orders ship within 2 business days.",
  "Orders within the country ship in two business days.",              // near-dup of 3
  "Support is available 9am-6pm GMT.",
  "The API rate limit is 1000 requests per minute.",
  "Deleted projects are kept for 90 days.",
];

const THRESHOLD = 0.90;

const vecs = await embeddings.embedDocuments(CHUNKS);

// Union-Find so transitive near-duplicates end up in one cluster.
const parent = CHUNKS.map((_, i) => i);
const find = (i) => (parent[i] === i ? i : (parent[i] = find(parent[i])));
const union = (a, b) => { parent[find(a)] = find(b); };

const pairs = [];
for (let i = 0; i < CHUNKS.length; i++) {
  for (let j = i + 1; j < CHUNKS.length; j++) {
    const s = cosine(vecs[i], vecs[j]);
    if (s >= THRESHOLD) {
      pairs.push([i, j, s]);
      union(i, j);
    }
  }
}

// Group by root
const clusters = new Map();
CHUNKS.forEach((_, i) => {
  const root = find(i);
  if (!clusters.has(root)) clusters.set(root, []);
  clusters.get(root).push(i);
});

console.log(`threshold ${THRESHOLD} · ${pairs.length} similar pairs found\n`);

let removed = 0;
for (const [, members] of clusters) {
  if (members.length === 1) continue;

  // Keep the LONGEST — it usually carries the most information.
  const keep = members.reduce((a, b) => (CHUNKS[a].length >= CHUNKS[b].length ? a : b));

  console.log(`cluster of ${members.length}:`);
  for (const m of members) {
    const mark = m === keep ? "KEEP  " : "DROP  ";
    if (m !== keep) removed++;
    console.log(`  ${mark}[${m}] ${CHUNKS[m]}`);
  }
  console.log();
}

console.log(`${CHUNKS.length} chunks → ${CHUNKS.length - removed} after dedup ` +
            `(${removed} removed)`);
```

**Python**
```python
from dotenv import load_dotenv
from langchain_ollama import OllamaEmbeddings
from day10_metrics import cosine

load_dotenv()
embeddings = OllamaEmbeddings(model="nomic-embed-text")

CHUNKS = [
    "Refunds are processed within 5 business days of approval.",
    "Refunds are processed within five business days after approval.",   # near-dup of 0
    "Refund requests are handled within 5 working days once approved.",  # near-dup of 0
    "Domestic orders ship within 2 business days.",
    "Orders within the country ship in two business days.",              # near-dup of 3
    "Support is available 9am-6pm GMT.",
    "The API rate limit is 1000 requests per minute.",
    "Deleted projects are kept for 90 days.",
]

THRESHOLD = 0.90

vecs = embeddings.embed_documents(CHUNKS)

# Union-Find so transitive near-duplicates end up in one cluster.
parent = list(range(len(CHUNKS)))

def find(i):
    while parent[i] != i:
        parent[i] = parent[parent[i]]
        i = parent[i]
    return i

def union(a, b):
    parent[find(a)] = find(b)

pairs = []
for i in range(len(CHUNKS)):
    for j in range(i + 1, len(CHUNKS)):
        s = cosine(vecs[i], vecs[j])
        if s >= THRESHOLD:
            pairs.append((i, j, s))
            union(i, j)

clusters = {}
for i in range(len(CHUNKS)):
    clusters.setdefault(find(i), []).append(i)

print(f"threshold {THRESHOLD} · {len(pairs)} similar pairs found\n")

removed = 0
for members in clusters.values():
    if len(members) == 1:
        continue

    # Keep the LONGEST — it usually carries the most information.
    keep = max(members, key=lambda m: len(CHUNKS[m]))

    print(f"cluster of {len(members)}:")
    for m in members:
        mark = "KEEP  " if m == keep else "DROP  "
        if m != keep:
            removed += 1
        print(f"  {mark}[{m}] {CHUNKS[m]}")
    print()

print(f"{len(CHUNKS)} chunks → {len(CHUNKS) - removed} after dedup ({removed} removed)")
```

**Why this matters in production, and why it's not just tidiness:**

Near-duplicate chunks actively *damage* retrieval. If your top-5 results are five paraphrases of
the same sentence, you've spent your entire context budget on one fact and starved the answer of
everything else. Deduplicating at ingest is one of the cheapest quality wins available.

Real corpora are full of these: boilerplate footers, the same policy restated across pages,
documentation copied between versions, minutes repeating the previous meeting's decisions.

**Three implementation notes:**

1. **Union-Find handles transitivity.** If A≈B and B≈C but A and C fall just below the
   threshold, they should still be one cluster. Naive pairwise grouping splits them.
2. **The threshold is model-specific.** 0.90 works for nomic; calibrate on your own data by
   printing the score distribution and finding where genuine duplicates separate from merely
   related content.
3. **This is O(n²).** Fine for thousands of chunks, hopeless for millions — at that scale you
   use the approximate index in your vector database to find candidate neighbours first, then
   compare only those. That's tomorrow's topic.

**The alternative to dropping duplicates** is MMR retrieval (Day 13), which selects for
*diversity* at query time instead. Deduping at ingest is cheaper; MMR handles duplicates you
didn't catch. Mature systems do both.
</details>

---

### Exercise 5 — 🏆 Production embedding pipeline ●●●●●

Build an ingestion pipeline that: loads chunks, deduplicates by content hash, embeds in batches
with a concurrency limit, retries on failure, caches to disk so re-runs are free, tracks cost and
progress, and saves the index to a JSON file that can be reloaded for search. Then build a search
CLI over it.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
// embed-pipeline.js
import "dotenv/config";
import fs from "node:fs/promises";
import crypto from "node:crypto";
import { OllamaEmbeddings } from "@langchain/ollama";
import { Document } from "@langchain/core/documents";
import { RecursiveCharacterTextSplitter } from "@langchain/textsplitters";
import { cosine } from "./day10-metrics.js";

const MODEL = "nomic-embed-text";
const BATCH_SIZE = 32;
const CONCURRENCY = 3;
const CACHE_FILE = "./.embed-cache.json";

const hash = (s) => crypto.createHash("sha256").update(`${MODEL}:${s}`).digest("hex").slice(0, 16);

// ── disk cache, namespaced by model ──────────────────────────────────────
async function loadCache() {
  try {
    return JSON.parse(await fs.readFile(CACHE_FILE, "utf8"));
  } catch {
    return {};
  }
}

// ── retry with backoff (Day 03) ──────────────────────────────────────────
async function withRetry(fn, retries = 3) {
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      return await fn();
    } catch (err) {
      if (attempt === retries) throw err;
      const delay = 400 * 2 ** attempt + Math.random() * 200;
      console.warn(`    retry ${attempt + 1}/${retries} in ${Math.round(delay)}ms`);
      await new Promise((r) => setTimeout(r, delay));
    }
  }
}

// ── bounded-concurrency batch runner ─────────────────────────────────────
async function pool(items, limit, fn) {
  const results = new Array(items.length);
  let cursor = 0;

  const workers = Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (cursor < items.length) {
      const i = cursor++;
      results[i] = await fn(items[i], i);
    }
  });

  await Promise.all(workers);
  return results;
}

export async function buildIndex(chunks) {
  const embeddings = new OllamaEmbeddings({ model: MODEL });
  const cache = await loadCache();

  // ── 1. dedupe by content hash ──────────────────────────────────────────
  const seen = new Set();
  const unique = [];
  let dupes = 0;
  for (const c of chunks) {
    const h = hash(c.pageContent);
    if (seen.has(h)) { dupes++; continue; }
    seen.add(h);
    unique.push({ doc: c, h });
  }

  // ── 2. split into cached vs needs-embedding ────────────────────────────
  const needed = unique.filter((u) => !cache[u.h]);
  console.log(`\n${chunks.length} chunks → ${unique.length} unique (${dupes} exact dupes)`);
  console.log(`${unique.length - needed.length} cached · ${needed.length} to embed`);

  // ── 3. batch + embed with bounded concurrency ──────────────────────────
  if (needed.length) {
    const batches = [];
    for (let i = 0; i < needed.length; i += BATCH_SIZE) {
      batches.push(needed.slice(i, i + BATCH_SIZE));
    }

    let done = 0;
    const t0 = Date.now();

    await pool(batches, CONCURRENCY, async (batch, bi) => {
      const vectors = await withRetry(() =>
        embeddings.embedDocuments(batch.map((b) => b.doc.pageContent))
      );
      batch.forEach((b, i) => { cache[b.h] = vectors[i]; });

      done += batch.length;
      const pct = ((done / needed.length) * 100).toFixed(0);
      const rate = done / ((Date.now() - t0) / 1000);
      process.stdout.write(
        `\r  batch ${bi + 1}/${batches.length} · ${done}/${needed.length} (${pct}%) · ` +
        `${rate.toFixed(1)}/s   `
      );
    });

    console.log(`\n  embedded in ${((Date.now() - t0) / 1000).toFixed(1)}s`);
    await fs.writeFile(CACHE_FILE, JSON.stringify(cache));
  }

  // ── 4. assemble the index ──────────────────────────────────────────────
  const index = {
    model: MODEL,                                   // ⚠️ record it — prevents mixing spaces
    dims: cache[unique[0].h].length,
    createdAt: new Date().toISOString(),
    entries: unique.map((u) => ({
      text: u.doc.pageContent,
      metadata: u.doc.metadata,
      vector: cache[u.h],
    })),
  };

  const estTokens = unique.reduce((s, u) => s + Math.ceil(u.doc.pageContent.length / 4), 0);
  console.log(`index: ${index.entries.length} vectors × ${index.dims} dims`);
  console.log(`       ~${estTokens} tokens · ` +
              `${(index.entries.length * index.dims * 4 / 1e6).toFixed(2)} MB as float32`);

  return index;
}

export async function saveIndex(index, path = "./index.json") {
  await fs.writeFile(path, JSON.stringify(index));
  const { size } = await fs.stat(path);
  console.log(`saved → ${path} (${(size / 1e6).toFixed(2)} MB on disk as JSON)`);
}

export async function loadIndex(path = "./index.json") {
  return JSON.parse(await fs.readFile(path, "utf8"));
}

export async function search(index, query, k = 3) {
  const embeddings = new OllamaEmbeddings({ model: index.model });   // same model as ingest
  const q = await embeddings.embedQuery(query);

  return index.entries
    .map((e) => ({ text: e.text, metadata: e.metadata, score: cosine(q, e.vector) }))
    .sort((a, b) => b.score - a.score)
    .slice(0, k);
}

// ── build from a file ────────────────────────────────────────────────────
if (process.argv[2] === "build") {
  const text = await fs.readFile(process.argv[3] ?? "./alice.txt", "utf8");
  const splitter = new RecursiveCharacterTextSplitter({ chunkSize: 800, chunkOverlap: 120 });
  const pieces = await splitter.splitText(text);

  const docs = pieces.map((p, i) => new Document({
    pageContent: p,
    metadata: { source: process.argv[3] ?? "alice.txt", chunkIndex: i },
  }));

  await saveIndex(await buildIndex(docs));
}

// ── search ───────────────────────────────────────────────────────────────
if (process.argv[2] === "search") {
  const index = await loadIndex();
  const readline = (await import("node:readline/promises")).default;
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });

  console.log(`index: ${index.entries.length} vectors · model ${index.model}\n`);

  while (true) {
    const q = (await rl.question("search › ")).trim();
    if (!q || q === "/exit") break;

    const t0 = Date.now();
    for (const r of await search(index, q, 3)) {
      console.log(`\n  ${r.score.toFixed(3)}  [chunk ${r.metadata.chunkIndex}]`);
      console.log(`  ${r.text.replace(/\s+/g, " ").slice(0, 150)}…`);
    }
    console.log(`\n  (${Date.now() - t0}ms)\n`);
  }
  rl.close();
}
```

```bash
node embed-pipeline.js build alice.txt
node embed-pipeline.js search
```

**Python**
```python
# embed_pipeline.py
import hashlib, json, random, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from dotenv import load_dotenv
import numpy as np
from langchain_ollama import OllamaEmbeddings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

MODEL = "nomic-embed-text"
BATCH_SIZE = 32
CONCURRENCY = 3
CACHE_FILE = Path("./.embed-cache.json")

def short_hash(s):
    return hashlib.sha256(f"{MODEL}:{s}".encode()).hexdigest()[:16]

def load_cache():
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text())
    return {}

# ── retry with backoff (Day 03) ──────────────────────────────────────────
def with_retry(fn, retries=3):
    for attempt in range(retries + 1):
        try:
            return fn()
        except Exception:
            if attempt == retries:
                raise
            delay = 0.4 * 2 ** attempt + random.random() * 0.2
            print(f"    retry {attempt + 1}/{retries} in {delay:.1f}s")
            time.sleep(delay)

def build_index(chunks):
    embeddings = OllamaEmbeddings(model=MODEL)
    cache = load_cache()

    # ── 1. dedupe by content hash ──────────────────────────────────────────
    seen, unique, dupes = set(), [], 0
    for c in chunks:
        h = short_hash(c.page_content)
        if h in seen:
            dupes += 1
            continue
        seen.add(h)
        unique.append((c, h))

    # ── 2. split into cached vs needs-embedding ────────────────────────────
    needed = [(c, h) for c, h in unique if h not in cache]
    print(f"\n{len(chunks)} chunks → {len(unique)} unique ({dupes} exact dupes)")
    print(f"{len(unique) - len(needed)} cached · {len(needed)} to embed")

    # ── 3. batch + embed with bounded concurrency ──────────────────────────
    if needed:
        batches = [needed[i:i + BATCH_SIZE] for i in range(0, len(needed), BATCH_SIZE)]
        done = 0
        t0 = time.time()

        def run_batch(batch):
            return with_retry(
                lambda: embeddings.embed_documents([c.page_content for c, _ in batch]))

        with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            for bi, (batch, vectors) in enumerate(
                zip(batches, pool.map(run_batch, batches)), 1
            ):
                for (_, h), vec in zip(batch, vectors):
                    cache[h] = vec
                done += len(batch)
                pct = done / len(needed) * 100
                rate = done / max(time.time() - t0, 1e-6)
                print(f"\r  batch {bi}/{len(batches)} · {done}/{len(needed)} "
                      f"({pct:.0f}%) · {rate:.1f}/s   ", end="", flush=True)

        print(f"\n  embedded in {time.time() - t0:.1f}s")
        CACHE_FILE.write_text(json.dumps(cache))

    # ── 4. assemble the index ──────────────────────────────────────────────
    index = {
        "model": MODEL,                              # ⚠️ record it — prevents mixing spaces
        "dims": len(cache[unique[0][1]]),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "entries": [
            {"text": c.page_content, "metadata": c.metadata, "vector": cache[h]}
            for c, h in unique
        ],
    }

    est_tokens = sum(-(-len(c.page_content) // 4) for c, _ in unique)
    print(f"index: {len(index['entries'])} vectors × {index['dims']} dims")
    print(f"       ~{est_tokens} tokens · "
          f"{len(index['entries']) * index['dims'] * 4 / 1e6:.2f} MB as float32")

    return index

def save_index(index, path="./index.json"):
    Path(path).write_text(json.dumps(index))
    print(f"saved → {path} ({Path(path).stat().st_size / 1e6:.2f} MB on disk as JSON)")

def load_index(path="./index.json"):
    return json.loads(Path(path).read_text())

def search(index, query, k=3):
    embeddings = OllamaEmbeddings(model=index["model"])   # same model as ingest
    q = np.array(embeddings.embed_query(query))

    matrix = np.array([e["vector"] for e in index["entries"]])
    norms = np.linalg.norm(matrix, axis=1) * np.linalg.norm(q)
    scores = (matrix @ q) / np.where(norms == 0, 1, norms)

    order = np.argsort(-scores)[:k]
    return [
        {"text": index["entries"][i]["text"],
         "metadata": index["entries"][i]["metadata"],
         "score": float(scores[i])}
        for i in order
    ]

# ── CLI ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"

    if cmd == "build":
        path = sys.argv[2] if len(sys.argv) > 2 else "./alice.txt"
        text = Path(path).read_text(encoding="utf8")
        pieces = RecursiveCharacterTextSplitter(
            chunk_size=800, chunk_overlap=120).split_text(text)

        docs = [Document(page_content=p, metadata={"source": path, "chunk_index": i})
                for i, p in enumerate(pieces)]

        save_index(build_index(docs))

    elif cmd == "search":
        index = load_index()
        print(f"index: {len(index['entries'])} vectors · model {index['model']}\n")

        while True:
            try:
                q = input("search › ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not q or q == "/exit":
                break

            t0 = time.time()
            for r in search(index, q, 3):
                print(f"\n  {r['score']:.3f}  [chunk {r['metadata']['chunk_index']}]")
                print(f"  {' '.join(r['text'].split())[:150]}…")
            print(f"\n  ({(time.time() - t0) * 1000:.0f}ms)\n")
```

```bash
python embed_pipeline.py build alice.txt
python embed_pipeline.py search
```

**Seven production behaviours packed in here:**

1. **The cache key includes the model name** (`hash(`${MODEL}:${text}`)`). This is the safeguard
   from §7 made concrete — switching models can never return stale vectors from the old space.
2. **The index records its model and dimensions.** At search time you construct the *same*
   embedder. Without this, an index and a query can silently drift into different spaces.
3. **Bounded concurrency, not unbounded `Promise.all`.** Firing 500 batches at once gets you
   rate-limited (Day 03). Three concurrent batches of 32 is a sane default.
4. **Retry with jittered backoff** around each batch, so one transient failure doesn't kill a
   30-minute ingest.
5. **Deduplication before embedding**, so you never pay to embed identical text twice.
6. **Progress output with a rate.** On a real corpus this runs for minutes; a silent script that
   might be hung is genuinely stressful, and the rate lets you estimate completion.
7. **Re-running is nearly free.** Change one chunk in a 10,000-chunk corpus and only that chunk
   is re-embedded. This is what makes iterating on chunk size (Day 09's Exercise 5) practical
   rather than punishing.

**What this deliberately isn't:** it loads every vector into memory and scans all of them per
query — O(n) per search. Fine to a few tens of thousands of chunks; hopeless at millions.
Persistence is a JSON blob, there's no incremental delete, and no metadata-filtered index.

Those three gaps — approximate indexes for sub-linear search, real persistence, and native
filtering — are exactly what a vector database provides. **That's tomorrow.**
</details>

---

## 9. Interview questions

### Basic

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

### Intermediate

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

### Advanced

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

## 10. Recap

- ✅ An embedding is a point in high-dimensional space where nearness means similar meaning
- ✅ Cosine = angle (the default); euclidean = distance; dot product = both combined
- ✅ **For normalised vectors, all three give the same ranking** — cosine equals dot product exactly
- ✅ Most models normalise; check with `magnitude(v) ≈ 1.0`
- ✅ `embedQuery` vs `embedDocuments` differ by batching *and* by query/document prefixes
- ✅ Dimensions drive storage and latency; Matryoshka models let you truncate
- ✅ **Never mix models in one index** — namespace caches by model name
- ✅ Long chunks dilute through pooling and truncate silently past the context limit
- ✅ Unrelated text scores ~0.4, not 0 — rank relatively, don't copy absolute thresholds
- ✅ Embeddings fail on exact identifiers, negation and numbers → hybrid search (tomorrow)

### Tomorrow

**[Day 11 — Vector databases](day-11-vector-databases.md)**: your search engine scans every
vector on every query. At 50,000 chunks that's already too slow, and it forgets everything on
restart. Tomorrow: HNSW and IVF indexes, the recall/latency trade-off, Chroma / FAISS / Qdrant /
pgvector / Pinecone compared, metadata filtering done properly, and **hybrid search** — the fix
for the `ERR_4471` problem you found today.

### Quick self-check

1. Your model returns vectors with magnitude 1.0. Does choosing cosine over euclidean change which documents you retrieve?
2. Why might a 2,000-token chunk retrieve worse than two 1,000-token chunks?
3. You switch embedding models and reuse the same index. What happens?

<details>
<summary>Answers</summary>

1. **No.** For normalised vectors, euclidean distance is a strictly decreasing function of cosine
   similarity, so the ranking is identical — only the reported numbers differ. Cosine also equals
   the dot product exactly.
2. Two reasons. **Pooling dilution**: the chunk's vector is the average of all its token vectors,
   so a chunk spanning several topics lands near the centroid of all of them and matches none
   sharply. And **silent truncation**: if 2,000 tokens exceeds the model's context limit, the tail
   is dropped with no error, so the vector represents only the opening text.
3. Nothing visibly — and that's the danger. Queries embed into the new model's space, documents
   sit in the old one, similarity scores come back as plausible numbers, and results are subtly
   wrong with no error raised. You must re-embed the entire corpus, and namespace embedding
   caches by model so stale vectors can't be served.
</details>
