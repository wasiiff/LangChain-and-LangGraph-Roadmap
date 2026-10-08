# Day 13 — Advanced RAG: Reranking, HyDE, Multi-Query & Self-Correction

> ⏱ **Time:** ~3 hours · 🎯 **Prereqs:** [Day 12](day-12-naive-rag.md) · 🧩 **Difficulty:** ●●●●○

**Today you learn:** Yesterday's pipeline searches once and hopes the right text comes back.
Often it doesn't: the results repeat each other, cover only half of a two-part question, or miss
the answer completely. Today you fix each of those failures with a named retrieval technique.
Then you build loops that check their own search results and try again when they are poor.

This is the day naive RAG becomes production RAG.

> 📖 **Words you'll meet today**
>
> - **Reranking** — fetch many chunks quickly, then let a slower, more accurate model re-score
>   them and keep the best few.
> - **MMR (Maximal Marginal Relevance)** — pick results that are relevant *and* different from
>   each other, so you don't get five copies of one fact.
> - **Multi-query** — ask the model to rephrase the question several ways, search with each, and
>   merge the results.
> - **HyDE (Hypothetical Document Embeddings)** — let the model write a fake answer, then search
>   with that answer instead of the question.
> - **Parent-document retrieval** — search over small chunks, but hand the model the larger chunk
>   each one came from.
> - **Self-query** — the model turns a question into a search phrase plus metadata filters, such
>   as "year 2024".
> - **Corrective RAG** — grade the retrieved documents; if they are poor, rewrite the query and
>   search again.
> - **Self-RAG** — grade the generated *answer*; regenerate it or search again, depending on what
>   went wrong.

---

## 1. The problem

Yesterday's pipeline retrieves once and hopes. Here's where that fails:

```
   ❌ "Compare the refund and cancellation policies"
      One query, one embedding. Retrieves refund chunks OR cancellation chunks,
      rarely a good spread of both.

   ❌ "How do I fix this?"  (short, vague)
      The query embedding barely resembles the prose in your documents.

   ❌ Top-5 results are five paraphrases of the same sentence.
      You spent your whole context budget on one fact.

   ❌ Retrieval returns nothing relevant. The system says "I don't know"
      and stops. A human would rephrase and search again.

   ❌ "Show me 2024 contracts over £50k mentioning indemnity"
      Embeddings can't do numeric comparisons. At all.

   ❌ Small chunks retrieve precisely but lack context to answer from.
      Large chunks have context but retrieve imprecisely.
```

Every one of these has a named solution. Today you learn all of them. More importantly, you learn
when each one is worth its cost.

---

## 2. Mental model

### The four places you can intervene

```
   QUESTION                                    ← ① transform the QUERY
       │                                          multi-query · HyDE · rewriting
       ▼                                          self-query (extract filters)
   ┌─────────────┐
   │  RETRIEVE   │                            ← ② change HOW you retrieve
   └─────────────┘                               hybrid · MMR · ensemble
       │                                          parent-document
       ▼
   CANDIDATES (20)                             ← ③ post-process the RESULTS
       │                                          rerank · compress · dedupe
       ▼
   TOP CHUNKS (4)
       │
       ▼
   ┌─────────────┐
   │  GENERATE   │                            ← ④ add a FEEDBACK LOOP
   └─────────────┘                               corrective · self-RAG · agentic
       │                                          "was that good enough? try again"
       ▼
    ANSWER
```

**Everything today fits in one of those four boxes.** When you hit a RAG problem, ask which box
it belongs in. That narrows eight techniques to two.

Three names in the diagram are not in the words box. **Hybrid search** combines keyword search
with vector search (Day 11). An **ensemble** retriever runs several retrievers and merges their
results; Day 11's `EnsembleRetriever` is how LangChain does hybrid search. **Compress** means
*contextual compression*: cutting each retrieved chunk down to the parts that match the question
(§3.6).

### The single highest-ROI pattern

```
   ┌──────────────────────────────────────────────────────────────┐
   │  RETRIEVE WIDE, RERANK NARROW                                │
   │                                                              │
   │  bi-encoder (fast)          cross-encoder (accurate)         │
   │  ┌────────────┐             ┌────────────┐                   │
   │  │ 100k docs  │──top 20────▶│  rerank    │──top 4──▶ prompt  │
   │  └────────────┘             └────────────┘                   │
   │  vectors precomputed        query+doc scored TOGETHER        │
   │  ~10ms                      ~200ms for 20                    │
   └──────────────────────────────────────────────────────────────┘
```

The timings in the diagram are rough orders of magnitude for illustration, not measurements.

ROI means *return on investment*: the most improvement for the least cost.

**Why a cross-encoder is better:** a **bi-encoder** (the model behind your vector store) embeds
the query and the document *separately* and compares the vectors. It never sees them together. A
**cross-encoder** feeds `[query, document]` into the model as one input. So it can judge real
relevance, not just how close two vectors are.

It's far too slow to run over 100k documents, and perfect for 20.

### The adaptive patterns

```
   NAIVE          retrieve → generate
                  (yesterday)

   CORRECTIVE     retrieve → GRADE docs → if bad: rewrite query, retrieve again
                                        → if still bad: fall back to web search

   SELF-RAG       retrieve → generate → GRADE the answer
                                      → hallucinated? regenerate
                                      → doesn't answer? re-retrieve

   ADAPTIVE       classify the question first → route to the right strategy
                  (no retrieval / single / multi-hop)

   AGENTIC        the model decides WHETHER, WHAT and HOW MANY times to search
                  (this is an agent — Week 3)
```

**Adaptive RAG** looks at the question first and picks a strategy, including "don't retrieve at
all". **Agentic RAG** gives the model a search tool and lets it decide when to use it.

Notice these all have **loops**. LCEL is acyclic (Day 07): a chain can only run forwards, never
back to an earlier step. So today you'll build them with bounded `while` loops — loops with a
fixed maximum number of turns. You'll feel exactly why LangGraph exists.

---

## 3. First principles

### 3.1 MMR — Maximal Marginal Relevance

> 💬 **In plain words:** MMR stops your results from repeating each other. Each new pick must be
> relevant *and* different from what you already picked.

Fixes: *"my top 5 are five paraphrases of one sentence."*

```
score(doc) = λ · relevance(doc, query) − (1 − λ) · max similarity(doc, already_selected)
                      ↑                              ↑
              how relevant is it?            how redundant is it?
```

Select greedily, one at a time: pick the most relevant document first. Then keep picking whichever
document has the highest combined score. `λ = 1` is pure relevance (identical to normal search).
`λ = 0` is pure diversity. **0.5–0.7 is the useful range.**

```js
store.asRetriever({ searchType: "mmr", searchKwargs: { fetchK: 20, lambda: 0.6, k: 4 } })
```

`fetchK` is the pool of candidates MMR selects *from*. It must be larger than `k`, or there's
nothing to diversify.

### 3.2 Multi-query — ask several ways

> 💬 **In plain words:** your user's wording may not match the document's wording. Asking the same
> question several ways gives the search more chances to hit.

Fixes: *"one phrasing doesn't match how the document is written."*

```
   "how do I get my money back?"
            │  LLM generates variations
            ├─▶ "What is the refund policy?"
            ├─▶ "How do I request a refund?"
            └─▶ "What are the conditions for reimbursement?"
                     │  retrieve for EACH, in parallel
                     ▼
              union + dedupe → richer candidate set
```

It costs one extra LLM call plus N retrievals (cheap, and they run in parallel). It reliably
improves **recall** — how many of the needed documents you actually find. The gain is largest for
short or vague queries.

### 3.3 HyDE — Hypothetical Document Embeddings

> 💬 **In plain words:** questions and documents are written differently. So you search with a
> made-up answer, because it looks more like the documents you want.

Fixes: *"queries and documents are different kinds of text."*

```
   query:    "how long for a refund?"           ← short, a question
   document: "Refunds are processed within…"    ← longer, a statement

   HyDE: generate a FAKE answer, embed THAT, retrieve with it

   "Refunds are typically processed within 5-10 business days
    of approval, depending on your payment method."
                    │ embed this (not the question)
                    ▼
            retrieve — now document-shaped
```

The hypothetical answer is often factually *wrong*. That doesn't matter. It only needs to be
*shaped* like the target documents. It sounds strange, but it works well, especially in technical
fields.

Cost: one extra LLM call and added latency. In the worst case, a hypothetical answer that is far
off topic retrieves worse than the raw query. So measure it.

### 3.4 Reranking with a cross-encoder

> 💬 **In plain words:** the right chunk is often found, just ranked too low. A second, more careful
> model re-scores the top results and moves it up.

Fixes: *"the right chunk is in my top 20 but not my top 4."*

This is the single change that improves a RAG pipeline the most. LangChain's
`ContextualCompressionRetriever` wraps a base retriever with a compressor. The compressor can be
a reranker or an LLM-based extractor.

Hosted rerankers exist (Cohere, Voyage, Jina). Without one, you can use an **LLM as the
reranker**. It is slower and costs more, but it works with the models you already have. That's
what we'll build.

### 3.5 Parent-document retrieval

> 💬 **In plain words:** small chunks are easy to find but too short to answer from. So you search
> the small chunks and hand the model the bigger chunk around them.

Fixes: *"small chunks retrieve well but lack context; large chunks have context but retrieve badly."*

```
   INDEX small child chunks (400 chars)  →  precise matching
   RETURN the large parent chunk (2000)  →  full context for the answer

   ┌─────────── parent (returned) ───────────┐
   │ child │ child │ child │ child │ child   │
   └───────────────────────────────────────────┘
              ▲ matched here
```

You get precision *and* context. The cost is a document store next to the vector store, and more
tokens per retrieved item.

### 3.6 Contextual compression

> 💬 **In plain words:** a retrieved chunk is often mostly noise. Compression keeps only the
> sentences that matter, so the prompt is shorter and clearer.

Fixes: *"my chunk is 1000 characters and only one sentence is relevant."*

Run each retrieved chunk through a filter. The filter keeps only the sentences that match the
query, or drops the chunk entirely. This shrinks the prompt and makes the useful text stand out.
It also reduces *lost-in-the-middle*: models pay less attention to text in the middle of a long
prompt.

There are two kinds:

- `LLMChainExtractor` — an LLM extracts the relevant text. Accurate, but costs one call per
  document.
- `EmbeddingsFilter` — drops chunks whose similarity score is below a threshold. Nearly free.

### 3.7 Self-query — natural language to metadata filters

> 💬 **In plain words:** embeddings can't compare numbers or dates. So the model pulls those
> conditions out of the question and turns them into exact filters.

Fixes: *"embeddings can't do 'over £50k in 2024'."*

```
   "2024 contracts over £50k mentioning indemnity"
                    │  LLM extracts structure
                    ▼
   query:  "indemnity"
   filter: year == 2024 AND value > 50000
                    │
                    ▼
   metadata-filtered vector search
```

This is how you handle numeric and categorical constraints (numbers, and fixed labels such as a
plan name). Embeddings simply cannot do this (Day 10's failure modes).

### 3.8 Corrective RAG — grade and retry

> 💬 **In plain words:** before answering, a small model checks whether the documents are any
> good. If they are not, you rephrase the search and try again.

```
   retrieve → grade each doc: relevant / ambiguous / irrelevant
        │
        ├─ enough relevant?  → generate
        ├─ some ambiguous?   → rewrite the query, retrieve again
        └─ all irrelevant?   → fall back (web search, or refuse)
```

**A bounded loop.** Cap the number of turns, or a confused grader (the model that judges the
documents) will loop forever. It's the same `maxSteps` lesson as Day 02's ReAct loop.

### 3.9 Self-RAG — grade the *answer*

> 💬 **In plain words:** after answering, you check the answer itself. Is it backed by the
> documents, and does it actually answer the question?

```
   generate → is it grounded in the docs?   no → regenerate
            → does it answer the question?  no → re-retrieve with a better query
```

Two graders, two different loops. Yesterday's citation check was a lightweight version of the
first one.

### 3.10 Choosing: the cost/benefit table

> 💬 **In plain words:** every technique costs time or money. Start with the cheap, big wins and
> add the others only when you can show they help.

| Technique | Extra cost | Typical gain | Use when |
|---|---|---|---|
| **Hybrid search** | ~0 | ⭐⭐⭐ | Always. Identifiers, codes, names |
| **Reranking** | 1 call / +200ms | ⭐⭐⭐ | Almost always. The biggest single win |
| **MMR** | ~0 | ⭐⭐ | Redundant corpora |
| **Multi-query** | 1 call + N retrievals | ⭐⭐ | Short or vague queries |
| **Parent-document** | storage | ⭐⭐ | Chunks too small to answer from |
| **HyDE** | 1 call | ⭐⭐ | Technical domains, query/doc mismatch |
| **Compression** | N calls | ⭐ | Long chunks, tight context budget |
| **Self-query** | 1 call | ⭐⭐⭐ | Numeric/categorical filters needed |
| **Corrective RAG** | 1–3 calls | ⭐⭐ | Retrieval quality is inconsistent |
| **Self-RAG** | 2–3 calls | ⭐⭐ | Hallucination is expensive |

> 🎯 **If you do only two things: hybrid search and reranking.** They cover most of the gap
> between a demo and a production system, and neither needs a loop.

---

## 4. Code — JavaScript

```bash
npm install langchain @langchain/core @langchain/classic @langchain/textsplitters \
            @langchain/ollama @langchain/groq zod dotenv
```

### 4.1 Shared setup

```js
// day13-setup.js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";
import { OllamaEmbeddings } from "@langchain/ollama";
import { MemoryVectorStore } from "@langchain/classic/vectorstores/memory";
import { Document } from "@langchain/core/documents";

export const fast = new ChatGroq({ model: "openai/gpt-oss-20b", temperature: 0 });
export const smart = new ChatGroq({ model: "openai/gpt-oss-120b", temperature: 0 });
export const embeddings = new OllamaEmbeddings({ model: "nomic-embed-text" });

export const DOCS = [
  // deliberately redundant — three near-identical refund chunks
  new Document({ pageContent: "Refund Policy\n\nCustomers may request a refund within 30 days for Basic plans.",
                 metadata: { section: "Refunds", year: 2024, plan: "Basic" } }),
  new Document({ pageContent: "Refund Policy\n\nRefund requests for Basic tier are accepted up to 30 days after purchase.",
                 metadata: { section: "Refunds", year: 2024, plan: "Basic" } }),
  new Document({ pageContent: "Refund Policy\n\nBasic plan purchases can be refunded within a 30-day window.",
                 metadata: { section: "Refunds", year: 2024, plan: "Basic" } }),
  new Document({ pageContent: "Refund Policy\n\nPro plans allow refunds within 60 days of purchase.",
                 metadata: { section: "Refunds", year: 2024, plan: "Pro" } }),
  new Document({ pageContent: "Cancellation\n\nSubscriptions can be cancelled at any time from billing settings. Cancellation takes effect at the end of the billing cycle.",
                 metadata: { section: "Cancellation", year: 2024, plan: "all" } }),
  new Document({ pageContent: "Cancellation\n\nCancelling does not automatically trigger a refund; refunds must be requested separately.",
                 metadata: { section: "Cancellation", year: 2023, plan: "all" } }),
  new Document({ pageContent: "API Rate Limits\n\nPro accounts get 1000 requests per minute. Exceeding this returns HTTP 429 with a Retry-After header.",
                 metadata: { section: "API", year: 2024, plan: "Pro" } }),
  new Document({ pageContent: "API Rate Limits\n\nBasic accounts are limited to 100 requests per minute.",
                 metadata: { section: "API", year: 2023, plan: "Basic" } }),
  new Document({ pageContent: "Shipping\n\nInternational orders take 10-14 days and may incur customs fees.",
                 metadata: { section: "Shipping", year: 2024, plan: "all" } }),
  new Document({ pageContent: "Data Retention\n\nDeleted projects are kept in cold storage for 90 days before permanent deletion.",
                 metadata: { section: "Retention", year: 2024, plan: "all" } }),
];

export const store = await MemoryVectorStore.fromDocuments(DOCS, embeddings);

export const formatDocs = (docs) =>
  docs.map((d, i) => `[${i + 1}] (${d.metadata.section}) ${d.pageContent.split("\n\n")[1] ?? d.pageContent}`)
      .join("\n");
```

> ⚠️ **Why every `fast.withStructuredOutput(...)` today passes `{ method: "jsonSchema" }`.** The
> default method asks the model to call a tool. On a short yes/no prompt such as "Is this
> relevant?", `openai/gpt-oss-20b` sometimes just answered in text. In our run (October 2026) the
> corrective-RAG grader (§5.7) failed on its first document: `400 Tool choice is required, but
> model did not call a tool` with `failed_generation: 'No'`. With JSON-schema mode the reply must
> match the schema, and the same script ran to the end. Multi-query, reranking and self-query
> also worked in this mode. Python spells it `method="json_schema", strict=True`. Keep
> `strict=True`: without it, one Self-RAG grader in our run sent back the *schema itself*
> instead of an answer. (JS's `jsonSchema` mode is already strict.) The methods are compared in
> [Day 06](../week-01-foundations/day-06-output-parsers-structured-output.md).

### 4.2 MMR — kill the redundancy

```js
// day13-mmr.js
import { store, formatDocs } from "./day13-setup.js";

const QUERY = "refund policy";

console.log("── PLAIN similarity (k=4) ──");
const plain = await store.asRetriever({ k: 4 }).invoke(QUERY);
console.log(formatDocs(plain));

console.log("\n── MMR (fetchK=8, lambda=0.5, k=4) ──");
const mmr = await store.asRetriever({
  searchType: "mmr",
  searchKwargs: { fetchK: 8, lambda: 0.5, k: 4 },
}).invoke(QUERY);
console.log(formatDocs(mmr));

const uniqueSections = (docs) => new Set(docs.map((d) => d.metadata.section)).size;
console.log(`\nsections covered — plain: ${uniqueSections(plain)} · mmr: ${uniqueSections(mmr)}`);
```

Plain returns three near-identical Basic-refund chunks. MMR returns refunds *and* cancellation.

### 4.3 Multi-query expansion

```js
// day13-multiquery.js
import * as z from "zod";
import { store, fast, formatDocs } from "./day13-setup.js";

const Variations = z.object({
  queries: z.array(z.string()).describe("3 alternative phrasings of the question, " +
                                        "using different vocabulary"),
});

async function multiQueryRetrieve(question, k = 3) {
  const { queries } = await fast.withStructuredOutput(Variations, { method: "jsonSchema" }).invoke(
    `Generate 3 alternative phrasings of this question for document search. ` +
    `Vary the vocabulary — use synonyms a document might use.\n\nQuestion: ${question}`
  );

  const all = [question, ...queries];
  console.log("  queries:");
  all.forEach((q) => console.log(`    · ${q}`));

  // Retrieve for each IN PARALLEL, then dedupe by content
  const resultSets = await Promise.all(
    all.map((q) => store.asRetriever({ k }).invoke(q))
  );

  const seen = new Set();
  const merged = [];
  for (const docs of resultSets) {
    for (const d of docs) {
      if (seen.has(d.pageContent)) continue;
      seen.add(d.pageContent);
      merged.push(d);
    }
  }
  return merged;
}

const QUESTION = "how do I get my money back?";

console.log("── SINGLE query ──");
const single = await store.asRetriever({ k: 3 }).invoke(QUESTION);
console.log(formatDocs(single));

console.log("\n── MULTI query ──");
const multi = await multiQueryRetrieve(QUESTION, 3);
console.log(formatDocs(multi));
console.log(`\n${single.length} docs → ${multi.length} docs`);
```

<details>
<summary>📦 Using the built-in MultiQueryRetriever</summary>

```js
import { MultiQueryRetriever } from "@langchain/classic/retrievers/multi_query";

const retriever = MultiQueryRetriever.fromLLM({
  llm: fast,
  retriever: store.asRetriever({ k: 3 }),
  queryCount: 3,
});

const docs = await retriever.invoke("how do I get my money back?");
```
Building it by hand first means the dedupe (duplicate-removal) behaviour isn't a mystery.
</details>

### 4.4 HyDE

```js
// day13-hyde.js
import { store, fast, embeddings, formatDocs } from "./day13-setup.js";
import { StringOutputParser } from "@langchain/core/output_parsers";
import { ChatPromptTemplate } from "@langchain/core/prompts";

const hydePrompt = ChatPromptTemplate.fromMessages([
  ["system", "Write a short passage that would plausibly appear in a company handbook " +
             "answering the user's question. Write it as a factual statement, not a question. " +
             "2-3 sentences. It does not need to be accurate — only realistic in style."],
  ["human", "{question}"],
]);

const hydeChain = hydePrompt.pipe(fast).pipe(new StringOutputParser());

async function hydeRetrieve(question, k = 3) {
  const hypothetical = await hydeChain.invoke({ question });
  console.log(`  hypothetical: "${hypothetical.trim().slice(0, 110)}…"`);

  // Retrieve using the HYPOTHETICAL ANSWER's embedding, not the question's
  return store.similaritySearch(hypothetical, k);
}

const QUESTION = "what if I go over my limit?";

console.log("── PLAIN ──");
console.log(formatDocs(await store.asRetriever({ k: 3 }).invoke(QUESTION)));

console.log("\n── HyDE ──");
console.log(formatDocs(await hydeRetrieve(QUESTION, 3)));
```

### 4.5 LLM reranking — the biggest win

```js
// day13-rerank.js
import * as z from "zod";
import { store, fast, smart, formatDocs } from "./day13-setup.js";

const Relevance = z.object({
  reasoning: z.string().describe("One short sentence. Write this first."),
  score: z.number().min(0).max(10)
    .describe("How well this document answers the question. 0 = irrelevant, 10 = directly answers"),
});

async function rerank(question, docs, topN = 3) {
  // Score each document against the query, in parallel.
  const scored = await Promise.all(
    docs.map(async (doc) => {
      const r = await fast.withStructuredOutput(Relevance, { method: "jsonSchema" }).invoke(
        `Question: ${question}\n\nDocument: ${doc.pageContent}\n\n` +
        `How relevant is this document to answering the question?`
      );
      return { doc, ...r };
    })
  );

  return scored.sort((a, b) => b.score - a.score).slice(0, topN);
}

const QUESTION = "can I cancel and get money back?";

// Retrieve WIDE (8), rerank NARROW (3)
const candidates = await store.asRetriever({ k: 8 }).invoke(QUESTION);

console.log(`── retrieved ${candidates.length} candidates ──`);
candidates.forEach((d, i) =>
  console.log(`  ${i + 1}. [${d.metadata.section}] ${d.pageContent.split("\n\n")[1]?.slice(0, 55)}`));

const reranked = await rerank(QUESTION, candidates, 3);

console.log("\n── after reranking ──");
reranked.forEach((r, i) =>
  console.log(`  ${i + 1}. score=${r.score} [${r.doc.metadata.section}] ` +
              `${r.doc.pageContent.split("\n\n")[1]?.slice(0, 50)}\n     ${r.reasoning}`));

// Where did the top reranked doc sit originally?
const originalRank = candidates.indexOf(reranked[0].doc) + 1;
console.log(`\ntop reranked doc was originally at position ${originalRank}`);
```

<details>
<summary>📦 Using ContextualCompressionRetriever with a hosted reranker</summary>

```bash
npm install @langchain/cohere
```
```js
import { CohereRerank } from "@langchain/cohere";
import { ContextualCompressionRetriever } from "@langchain/classic/retrievers/contextual_compression";

const retriever = new ContextualCompressionRetriever({
  baseCompressor: new CohereRerank({ topN: 3, model: "rerank-english-v3.0" }),
  baseRetriever: store.asRetriever({ k: 20 }),
});

const docs = await retriever.invoke("can I cancel and get money back?");
```
A hosted cross-encoder is typically much faster and cheaper than LLM reranking (one API call
instead of one LLM call per candidate). Use one in production.
The LLM version is the free fallback.
</details>

### 4.6 Contextual compression

```js
// day13-compression.js
import { ContextualCompressionRetriever } from "@langchain/classic/retrievers/contextual_compression";
import { EmbeddingsFilter } from "@langchain/classic/retrievers/document_compressors/embeddings_filter";
import { store, embeddings, formatDocs } from "./day13-setup.js";

// EmbeddingsFilter: drop chunks below a similarity threshold. Nearly free.
const retriever = new ContextualCompressionRetriever({
  baseCompressor: new EmbeddingsFilter({ embeddings, similarityThreshold: 0.55 }),
  baseRetriever: store.asRetriever({ k: 8 }),
});

const QUESTION = "refund window for Pro";

const before = await store.asRetriever({ k: 8 }).invoke(QUESTION);
const after = await retriever.invoke(QUESTION);

console.log(`before: ${before.length} docs, ` +
            `${before.reduce((s, d) => s + d.pageContent.length, 0)} chars`);
console.log(`after:  ${after.length} docs, ` +
            `${after.reduce((s, d) => s + d.pageContent.length, 0)} chars`);
console.log("\nkept:\n" + formatDocs(after));
```

### 4.7 Corrective RAG — grade and retry

```js
// day13-corrective.js
import * as z from "zod";
import { store, fast, smart, formatDocs } from "./day13-setup.js";
import { ChatPromptTemplate } from "@langchain/core/prompts";
import { StringOutputParser } from "@langchain/core/output_parsers";

const Grade = z.object({
  reasoning: z.string().describe("One sentence. Write this first."),
  relevant: z.boolean().describe("Does this document help answer the question?"),
});

const Rewrite = z.object({
  rewritten: z.string().describe("A better search query, using different vocabulary"),
});

const answerChain = ChatPromptTemplate.fromMessages([
  ["system", "Answer using ONLY the context. Cite as [1], [2]. If it's not there, say so.\n\n{context}"],
  ["human", "{question}"],
]).pipe(smart).pipe(new StringOutputParser());

async function correctiveRag(question, { maxAttempts = 3, minRelevant = 2 } = {}) {
  let query = question;
  const tried = [];

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    console.log(`\n  attempt ${attempt}: searching "${query}"`);
    tried.push(query);

    const docs = await store.asRetriever({ k: 4 }).invoke(query);

    // ── grade every document in parallel ────────────────────────────────
    const graded = await Promise.all(
      docs.map(async (doc) => ({
        doc,
        ...(await fast.withStructuredOutput(Grade, { method: "jsonSchema" }).invoke(
          `Question: ${question}\n\nDocument: ${doc.pageContent}\n\nIs this relevant?`
        )),
      }))
    );

    const relevant = graded.filter((g) => g.relevant).map((g) => g.doc);
    console.log(`    ${relevant.length}/${docs.length} graded relevant`);

    // ── enough? answer ──────────────────────────────────────────────────
    if (relevant.length >= minRelevant) {
      const answer = await answerChain.invoke({
        context: formatDocs(relevant), question,
      });
      return { answer, docs: relevant, attempts: attempt, tried };
    }

    // ── not enough, and attempts remain? rewrite and retry ───────────────
    if (attempt < maxAttempts) {
      const { rewritten } = await fast
        .withStructuredOutput(Rewrite, { method: "jsonSchema" }).invoke(
        `The search query "${query}" returned poor results for this question: "${question}".\n` +
        `Previously tried: ${tried.join(", ")}.\n` +
        `Write a DIFFERENT search query using other vocabulary.`
      );
      query = rewritten;
    }
  }

  // ── exhausted: fall back honestly ──────────────────────────────────────
  return {
    answer: "I couldn't find relevant information in the documents after several attempts.",
    docs: [], attempts: maxAttempts, tried,
  };
}

for (const q of [
  "can I get my money back on the professional tier?",   // needs rewriting
  "what is the airspeed velocity of a swallow?",         // genuinely absent
]) {
  console.log(`\n${"═".repeat(72)}\n❓ ${q}\n${"═".repeat(72)}`);
  const r = await correctiveRag(q);
  console.log(`\n${r.answer}`);
  console.log(`\n(${r.attempts} attempts · queries tried: ${r.tried.length})`);
}
```

**Note the bounded loop.** Without `maxAttempts`, a confused grader rewrites forever. It's the
same lesson as Day 02's ReAct step limit.

### 4.8 Self-query — natural language to filters

```js
// day13-selfquery.js
import * as z from "zod";
import { store, fast, DOCS, formatDocs } from "./day13-setup.js";

const StructuredQuery = z.object({
  reasoning: z.string().describe("One sentence. Write this first."),
  semanticQuery: z.string().describe("The topical part of the question, for vector search"),
  section: z.enum(["Refunds", "Cancellation", "API", "Shipping", "Retention", "any"])
    .describe("Which section to filter to, or 'any'"),
  plan: z.enum(["Basic", "Pro", "all", "any"]).describe("Which plan, or 'any'"),
  minYear: z.number().int().nullable().describe("Minimum year, or null for no constraint"),
});

async function selfQuery(question, k = 3) {
  const q = await fast.withStructuredOutput(StructuredQuery, { method: "jsonSchema" }).invoke(
    `Convert this question into a search query plus metadata filters.\n\n` +
    `Available metadata: section (Refunds|Cancellation|API|Shipping|Retention), ` +
    `plan (Basic|Pro|all), year (number).\n\nQuestion: ${question}`
  );

  console.log(`  semantic: "${q.semanticQuery}"`);
  console.log(`  filters:  section=${q.section} plan=${q.plan} minYear=${q.minYear ?? "-"}`);

  const filterFn = (doc) => {
    if (q.section !== "any" && doc.metadata.section !== q.section) return false;
    if (q.plan !== "any" && doc.metadata.plan !== q.plan && doc.metadata.plan !== "all") return false;
    if (q.minYear !== null && doc.metadata.year < q.minYear) return false;
    return true;
  };

  return store.similaritySearch(q.semanticQuery, k, filterFn);
}

for (const question of [
  "What are the Pro plan API limits from 2024?",
  "Tell me about refunds for Basic",
]) {
  console.log(`\n❓ ${question}`);
  console.log(formatDocs(await selfQuery(question)));
}
```

---

## 5. Code — Python

```bash
pip install langchain langchain-classic langchain-community langchain-ollama langchain-groq pydantic python-dotenv
```

### 5.1 Shared setup

```python
# day13_setup.py
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_ollama import OllamaEmbeddings
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_core.documents import Document

load_dotenv()

fast = ChatGroq(model="openai/gpt-oss-20b", temperature=0)
smart = ChatGroq(model="openai/gpt-oss-120b", temperature=0)
embeddings = OllamaEmbeddings(model="nomic-embed-text")

DOCS = [
    # deliberately redundant — three near-identical refund chunks
    Document(page_content="Refund Policy\n\nCustomers may request a refund within 30 days for Basic plans.",
             metadata={"section": "Refunds", "year": 2024, "plan": "Basic"}),
    Document(page_content="Refund Policy\n\nRefund requests for Basic tier are accepted up to 30 days after purchase.",
             metadata={"section": "Refunds", "year": 2024, "plan": "Basic"}),
    Document(page_content="Refund Policy\n\nBasic plan purchases can be refunded within a 30-day window.",
             metadata={"section": "Refunds", "year": 2024, "plan": "Basic"}),
    Document(page_content="Refund Policy\n\nPro plans allow refunds within 60 days of purchase.",
             metadata={"section": "Refunds", "year": 2024, "plan": "Pro"}),
    Document(page_content="Cancellation\n\nSubscriptions can be cancelled at any time from billing settings. Cancellation takes effect at the end of the billing cycle.",
             metadata={"section": "Cancellation", "year": 2024, "plan": "all"}),
    Document(page_content="Cancellation\n\nCancelling does not automatically trigger a refund; refunds must be requested separately.",
             metadata={"section": "Cancellation", "year": 2023, "plan": "all"}),
    Document(page_content="API Rate Limits\n\nPro accounts get 1000 requests per minute. Exceeding this returns HTTP 429 with a Retry-After header.",
             metadata={"section": "API", "year": 2024, "plan": "Pro"}),
    Document(page_content="API Rate Limits\n\nBasic accounts are limited to 100 requests per minute.",
             metadata={"section": "API", "year": 2023, "plan": "Basic"}),
    Document(page_content="Shipping\n\nInternational orders take 10-14 days and may incur customs fees.",
             metadata={"section": "Shipping", "year": 2024, "plan": "all"}),
    Document(page_content="Data Retention\n\nDeleted projects are kept in cold storage for 90 days before permanent deletion.",
             metadata={"section": "Retention", "year": 2024, "plan": "all"}),
]

store = InMemoryVectorStore.from_documents(DOCS, embeddings)

def format_docs(docs):
    return "\n".join(
        f"[{i}] ({d.metadata['section']}) "
        f"{d.page_content.split(chr(10) + chr(10))[-1]}"
        for i, d in enumerate(docs, 1)
    )
```

### 5.2 MMR — kill the redundancy

```python
# day13_mmr.py
from day13_setup import store, format_docs

QUERY = "refund policy"

print("── PLAIN similarity (k=4) ──")
plain = store.as_retriever(search_kwargs={"k": 4}).invoke(QUERY)
print(format_docs(plain))

print("\n── MMR (fetch_k=8, lambda_mult=0.5, k=4) ──")
mmr = store.as_retriever(
    search_type="mmr",
    search_kwargs={"k": 4, "fetch_k": 8, "lambda_mult": 0.5},
).invoke(QUERY)
print(format_docs(mmr))

unique_sections = lambda docs: len({d.metadata["section"] for d in docs})
print(f"\nsections covered — plain: {unique_sections(plain)} · mmr: {unique_sections(mmr)}")
```

### 5.3 Multi-query expansion

```python
# day13_multiquery.py
from pydantic import BaseModel, Field
from day13_setup import store, fast, format_docs

class Variations(BaseModel):
    """Alternative phrasings of a search question."""
    queries: list[str] = Field(
        description="3 alternative phrasings of the question, using different vocabulary")

def multi_query_retrieve(question, k=3):
    result = fast.with_structured_output(Variations, method="json_schema", strict=True).invoke(
        f"Generate 3 alternative phrasings of this question for document search. "
        f"Vary the vocabulary — use synonyms a document might use.\n\nQuestion: {question}"
    )

    all_queries = [question] + result.queries
    print("  queries:")
    for q in all_queries:
        print(f"    · {q}")

    seen, merged = set(), []
    for q in all_queries:
        for d in store.as_retriever(search_kwargs={"k": k}).invoke(q):
            if d.page_content in seen:
                continue
            seen.add(d.page_content)
            merged.append(d)
    return merged

QUESTION = "how do I get my money back?"

print("── SINGLE query ──")
single = store.as_retriever(search_kwargs={"k": 3}).invoke(QUESTION)
print(format_docs(single))

print("\n── MULTI query ──")
multi = multi_query_retrieve(QUESTION, 3)
print(format_docs(multi))
print(f"\n{len(single)} docs → {len(multi)} docs")
```

<details>
<summary>📦 Using the built-in MultiQueryRetriever</summary>

```python
from langchain_classic.retrievers import MultiQueryRetriever

retriever = MultiQueryRetriever.from_llm(
    retriever=store.as_retriever(search_kwargs={"k": 3}),
    llm=fast,
)
docs = retriever.invoke("how do I get my money back?")
```
</details>

### 5.4 HyDE

```python
# day13_hyde.py
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from day13_setup import store, fast, format_docs

hyde_chain = ChatPromptTemplate.from_messages([
    ("system", "Write a short passage that would plausibly appear in a company handbook "
               "answering the user's question. Write it as a factual statement, not a question. "
               "2-3 sentences. It does not need to be accurate — only realistic in style."),
    ("human", "{question}"),
]) | fast | StrOutputParser()

def hyde_retrieve(question, k=3):
    hypothetical = hyde_chain.invoke({"question": question})
    print(f'  hypothetical: "{hypothetical.strip()[:110]}…"')
    # Retrieve using the HYPOTHETICAL ANSWER's embedding, not the question's
    return store.similarity_search(hypothetical, k=k)

QUESTION = "what if I go over my limit?"

print("── PLAIN ──")
print(format_docs(store.as_retriever(search_kwargs={"k": 3}).invoke(QUESTION)))

print("\n── HyDE ──")
print(format_docs(hyde_retrieve(QUESTION, 3)))
```

### 5.5 LLM reranking — the biggest win

```python
# day13_rerank.py
from pydantic import BaseModel, Field
from day13_setup import store, fast

class Relevance(BaseModel):
    """How relevant a document is to a question."""
    reasoning: str = Field(description="One short sentence. Write this first.")
    score: float = Field(ge=0, le=10,
                         description="0 = irrelevant, 10 = directly answers the question")

def rerank(question, docs, top_n=3):
    scored = []
    for doc in docs:
        r = fast.with_structured_output(Relevance, method="json_schema", strict=True).invoke(
            f"Question: {question}\n\nDocument: {doc.page_content}\n\n"
            f"How relevant is this document to answering the question?"
        )
        scored.append({"doc": doc, "score": r.score, "reasoning": r.reasoning})
    return sorted(scored, key=lambda x: -x["score"])[:top_n]

QUESTION = "can I cancel and get money back?"

# Retrieve WIDE (8), rerank NARROW (3)
candidates = store.as_retriever(search_kwargs={"k": 8}).invoke(QUESTION)

print(f"── retrieved {len(candidates)} candidates ──")
for i, d in enumerate(candidates, 1):
    body = d.page_content.split("\n\n")[-1]
    print(f"  {i}. [{d.metadata['section']}] {body[:55]}")

reranked = rerank(QUESTION, candidates, 3)

print("\n── after reranking ──")
for i, r in enumerate(reranked, 1):
    body = r["doc"].page_content.split("\n\n")[-1]
    print(f"  {i}. score={r['score']} [{r['doc'].metadata['section']}] {body[:50]}")
    print(f"     {r['reasoning']}")

original_rank = candidates.index(reranked[0]["doc"]) + 1
print(f"\ntop reranked doc was originally at position {original_rank}")
```

### 5.6 Contextual compression

```python
# day13_compression.py
from langchain_classic.retrievers import ContextualCompressionRetriever
from langchain_classic.retrievers.document_compressors import EmbeddingsFilter, LLMChainExtractor
from day13_setup import store, embeddings, fast, format_docs

QUESTION = "refund window for Pro"

# ── EmbeddingsFilter: drop chunks below a threshold. Nearly free. ────────
cheap = ContextualCompressionRetriever(
    base_compressor=EmbeddingsFilter(embeddings=embeddings, similarity_threshold=0.55),
    base_retriever=store.as_retriever(search_kwargs={"k": 8}),
)

# ── LLMChainExtractor: extract only relevant sentences. Costs a call per doc.
accurate = ContextualCompressionRetriever(
    base_compressor=LLMChainExtractor.from_llm(fast),
    base_retriever=store.as_retriever(search_kwargs={"k": 8}),
)

before = store.as_retriever(search_kwargs={"k": 8}).invoke(QUESTION)
filtered = cheap.invoke(QUESTION)
extracted = accurate.invoke(QUESTION)

chars = lambda docs: sum(len(d.page_content) for d in docs)

print(f"baseline          : {len(before):>2} docs, {chars(before):>5} chars")
print(f"EmbeddingsFilter  : {len(filtered):>2} docs, {chars(filtered):>5} chars")
print(f"LLMChainExtractor : {len(extracted):>2} docs, {chars(extracted):>5} chars")

print("\nextracted content:")
for d in extracted:
    print(f"  · {d.page_content[:80]}")
```

> ⚠️ **Check what the extractor really returns.** `LLMChainExtractor` asks the model to copy
> the relevant sentences as plain text. We ran it with `openai/gpt-oss-20b` in October 2026.
> It kept the right document — *"Pro plans allow refunds within 60 days of purchase."* — but
> put its own heading, `Extracted relevant parts:`, in front of it. That heading then becomes part
> of your context. Print the extracted text before you trust it.

### 5.7 Corrective RAG — grade and retry

```python
# day13_corrective.py
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from day13_setup import store, fast, smart, format_docs

class Grade(BaseModel):
    """Whether a retrieved document helps answer the question."""
    reasoning: str = Field(description="One sentence. Write this first.")
    relevant: bool = Field(description="Does this document help answer the question?")

class Rewrite(BaseModel):
    """An improved search query."""
    rewritten: str = Field(description="A better search query, using different vocabulary")

answer_chain = ChatPromptTemplate.from_messages([
    ("system", "Answer using ONLY the context. Cite as [1], [2]. "
               "If it's not there, say so.\n\n{context}"),
    ("human", "{question}"),
]) | smart | StrOutputParser()

def corrective_rag(question, max_attempts=3, min_relevant=2):
    query = question
    tried = []

    for attempt in range(1, max_attempts + 1):
        print(f'\n  attempt {attempt}: searching "{query}"')
        tried.append(query)

        docs = store.as_retriever(search_kwargs={"k": 4}).invoke(query)

        # ── grade every document ────────────────────────────────────────
        graded = []
        for doc in docs:
            g = fast.with_structured_output(Grade, method="json_schema", strict=True).invoke(
                f"Question: {question}\n\nDocument: {doc.page_content}\n\nIs this relevant?")
            graded.append((doc, g.relevant))

        relevant = [d for d, ok in graded if ok]
        print(f"    {len(relevant)}/{len(docs)} graded relevant")

        # ── enough? answer ──────────────────────────────────────────────
        if len(relevant) >= min_relevant:
            answer = answer_chain.invoke(
                {"context": format_docs(relevant), "question": question})
            return {"answer": answer, "docs": relevant, "attempts": attempt, "tried": tried}

        # ── not enough, attempts remain? rewrite and retry ───────────────
        if attempt < max_attempts:
            r = fast.with_structured_output(Rewrite, method="json_schema", strict=True).invoke(
                f'The search query "{query}" returned poor results for this question: '
                f'"{question}".\nPreviously tried: {", ".join(tried)}.\n'
                f"Write a DIFFERENT search query using other vocabulary.")
            query = r.rewritten

    # ── exhausted: fall back honestly ───────────────────────────────────
    return {"answer": "I couldn't find relevant information in the documents "
                      "after several attempts.",
            "docs": [], "attempts": max_attempts, "tried": tried}

for q in [
    "can I get my money back on the professional tier?",   # needs rewriting
    "what is the airspeed velocity of a swallow?",         # genuinely absent
]:
    print(f"\n{'═' * 72}\n❓ {q}\n{'═' * 72}")
    r = corrective_rag(q)
    print(f"\n{r['answer']}")
    print(f"\n({r['attempts']} attempts · queries tried: {len(r['tried'])})")
```

### 5.8 Self-query — natural language to filters

```python
# day13_selfquery.py
from typing import Literal, Optional
from pydantic import BaseModel, Field
from day13_setup import store, fast, format_docs

class StructuredQuery(BaseModel):
    """A search question decomposed into semantics plus metadata filters."""
    reasoning: str = Field(description="One sentence. Write this first.")
    semantic_query: str = Field(description="The topical part of the question, for vector search")
    section: Literal["Refunds", "Cancellation", "API", "Shipping", "Retention", "any"] = Field(
        description="Which section to filter to, or 'any'")
    plan: Literal["Basic", "Pro", "all", "any"] = Field(description="Which plan, or 'any'")
    min_year: Optional[int] = Field(None, description="Minimum year, or null for no constraint")

def self_query(question, k=3):
    q = fast.with_structured_output(StructuredQuery, method="json_schema", strict=True).invoke(
        f"Convert this question into a search query plus metadata filters.\n\n"
        f"Available metadata: section (Refunds|Cancellation|API|Shipping|Retention), "
        f"plan (Basic|Pro|all), year (number).\n\nQuestion: {question}"
    )

    print(f'  semantic: "{q.semantic_query}"')
    print(f"  filters:  section={q.section} plan={q.plan} min_year={q.min_year or '-'}")

    def filter_fn(doc):
        m = doc.metadata
        if q.section != "any" and m["section"] != q.section:
            return False
        if q.plan != "any" and m["plan"] not in (q.plan, "all"):
            return False
        if q.min_year is not None and m["year"] < q.min_year:
            return False
        return True

    return store.similarity_search(q.semantic_query, k=k, filter=filter_fn)

for question in [
    "What are the Pro plan API limits from 2024?",
    "Tell me about refunds for Basic",
]:
    print(f"\n❓ {question}")
    print(format_docs(self_query(question)))
```

<details>
<summary>📦 Using the built-in SelfQueryRetriever</summary>

```python
from langchain_classic.retrievers.self_query.base import SelfQueryRetriever
from langchain_classic.chains.query_constructor.schema import AttributeInfo

metadata_field_info = [
    AttributeInfo(name="section", description="The handbook section", type="string"),
    AttributeInfo(name="plan", description="Which plan: Basic, Pro or all", type="string"),
    AttributeInfo(name="year", description="Year of the policy", type="integer"),
]

retriever = SelfQueryRetriever.from_llm(
    fast, store, "Company handbook policies", metadata_field_info,
)
docs = retriever.invoke("Pro plan API limits from 2024")
```
Requires a store whose translator LangChain supports (Chroma, Qdrant, pgvector and others).
</details>

### 🔁 JS ↔ Python differences you just saw

| | JavaScript | Python |
|---|---|---|
| MMR params | `{ searchType: "mmr", searchKwargs: { fetchK, lambda } }` | `search_type="mmr", search_kwargs={"fetch_k", "lambda_mult"}` |
| Lambda param name | `lambda` | `lambda_mult` ⚠️ (`lambda` is a keyword) |
| Multi-query | `MultiQueryRetriever.fromLLM({ llm, retriever })` | `MultiQueryRetriever.from_llm(retriever, llm)` |
| Compression | `@langchain/classic/retrievers/contextual_compression` | `langchain_classic.retrievers` |
| Compressors | `.../document_compressors/embeddings_filter` | `langchain_classic.retrievers.document_compressors` |
| Self-query | `@langchain/classic/retrievers/self_query` | `langchain_classic.retrievers.self_query.base` |
| Parallel grading | `Promise.all(docs.map(...))` | loop, or `asyncio.gather` with `ainvoke` |

---

## 6. Under the hood

### Bi-encoder vs cross-encoder — why reranking wins

```
   BI-ENCODER (your vector store)
   ┌─────────┐        ┌──────────┐
   │  query  │──▶[v1] │ document │──▶[v2]        embedded SEPARATELY
   └─────────┘        └──────────┘                (documents precomputed at ingest)
                cosine(v1, v2)
   ✅ documents embedded once, search is a vector op → scales to billions
   ❌ the model never sees query and document together

   CROSS-ENCODER (the reranker)
   ┌──────────────────────────────┐
   │ [CLS] query [SEP] document   │──▶ transformer ──▶ relevance score
   └──────────────────────────────┘
   ✅ full attention between query and document → far more accurate
   ❌ must run once PER PAIR → impossible over a whole corpus
```

The two-stage design uses each where it's strong. The bi-encoder cheaply narrows 100k to 20. The
cross-encoder accurately narrows 20 to 4.

**Typical impact** (illustrative, not a measurement — the size of the gain depends on your corpus
and queries; measure it with Exercise 1): reranking can move recall@4 by a large margin on a
corpus where naive retrieval is mediocre, say around 70%. (Recall@4 is the share of questions whose right chunk appears in the top
4.) That's a bigger gain than switching embedding models, for much less effort. And you don't
need to re-index.

### Why HyDE works despite generating false text

Retrieval quality depends on the *distance* between query and document embeddings. Questions and
statements sit in consistently different regions of embedding space (Day 10's asymmetry).

```
   embedding space (schematically)

        [questions live here]
              ↑
              │  ← a real gap
              ↓
        [statements/documents live here]

   HyDE moves the query INTO the document region before searching.
```

The hypothetical answer's *facts* are irrelevant. Only its *shape and vocabulary* matter. It uses
the right technical terms, the right sentence structure and the right tone.

**When HyDE hurts:** the model may know nothing about your field. Then its hypothetical answer
goes off-topic, and you retrieve for the wrong thing. Always measure rather than assume.

### Why MMR needs `fetchK > k`

```
   fetchK = 4, k = 4   →   MMR selects 4 from 4. Nothing to diversify. No-op.
   fetchK = 20, k = 4  →   MMR selects the 4 most diverse-and-relevant from 20. ✅
```

A common bug: setting them equal and concluding "MMR does nothing".

### Why the loops need bounds

Corrective and Self-RAG are loops driven by a model's judgement. They can fail in two ways:

1. **Infinite loop** — the grader never accepts, so you rewrite forever and keep paying.
2. **Oscillation** — the rewriter switches back and forth between two phrasings that both fail.

Mitigations:

- A hard `maxAttempts`.
- Pass the queries you already tried into the rewrite prompt (as in §4.7), so it must produce
  something new.
- Always have a terminal fallback: a last step that returns an honest failure instead of looping.

**And note what's awkward about all of this.** You're hand-writing a state machine: a loop with
counters, saved state and conditional exits. You do it because LCEL can't express cycles. That
works at this size. It becomes unmanageable when you add streaming, persistence and a human
approval step.

That gap is exactly what LangGraph fills, and it's where Week 3 starts.

<details>
<summary>📜 A note on RAG pattern names</summary>

Research papers and blogs name a lot of variants, and they overlap heavily. These are the
distinctions that actually matter.

| Name | Distinctive idea |
|---|---|
| **Naive RAG** | Retrieve once, generate |
| **Advanced RAG** | Umbrella term for pre-retrieval (query transforms) and post-retrieval (rerank, compress) improvements |
| **Corrective RAG (CRAG)** | Grade *documents*, retry or fall back |
| **Self-RAG** | Grade the *answer* for grounding and relevance |
| **Adaptive RAG** | Classify the question, route to a strategy (including "no retrieval") |
| **Agentic RAG** | Retrieval is a *tool* the model decides to call |
| **Graph RAG** | Retrieve over an entity/relationship graph rather than flat chunks |
| **Modular RAG** | Framing all of the above as swappable components |

In interviews, describe the *mechanism* instead of reciting names. "Grade retrieved documents and
re-query on failure" tells the interviewer more than "we use CRAG". The names are just labels for
combinations of the four intervention points in §2.
</details>

---

## 7. Common mistakes

**❌ Adding every technique at once**

You can't tell what helped, latency grows fast, and cost multiplies.
✅ Add one at a time, measure recall@k, and keep only what earns its cost.

---

**❌ MMR with `fetchK == k`**

There's nothing to diversify from, so it does nothing.
✅ `fetchK` should be 3–5× `k`.

---

**❌ Reranking without over-fetching first**

Retrieving 4 and reranking to 4 just reorders them.
✅ Retrieve 20–30, rerank to 3–5. The point is *selection*, not ordering.

---

**❌ Unbounded corrective loops**

A grader that never approves rewrites forever.
✅ `maxAttempts`, pass tried queries into the rewriter, and a terminal fallback.

---

**❌ Using the big model for grading and reranking**

Grading 20 documents with the 120B model per query is enormously expensive.
✅ Use a small, fast model for grading, reranking and rewriting. Use the big model only for the
final answer.

---

**❌ Multi-query without deduplication**

Four queries × k=5 returns 20 documents, many identical, wasting your context budget.
✅ Dedupe by content, then rerank the union.

---

**❌ Assuming HyDE always helps**

In domains the model doesn't know, the hypothetical can be misleading and retrieval gets *worse*.
✅ A/B test it: run your eval set (a fixed list of test questions) with and without HyDE.

---

**❌ Compression that discards the answer**

Aggressive thresholds or over-eager extraction can drop the one relevant sentence.
✅ Tune the threshold against recall, not against token savings.

---

**❌ Reaching for advanced RAG before fixing chunking**

No retriever recovers an answer split across a chunk boundary.
✅ Day 09 first. Fix the ingest (how documents are split and stored), then optimise retrieval.

---

## 8. Exercises

### Exercise 1 — Technique bake-off ●●●○○

Build an eval set of ~8 questions with known correct sections. Measure recall@3 for: baseline,
MMR, multi-query, HyDE, and rerank-after-wide-retrieval. Report recall, latency and LLM calls per
query for each, and decide which are worth their cost.

<details>
<summary>✅ Solution</summary>

**Python**
```python
# day13_bakeoff.py
import time
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from day13_setup import store, fast

# question → the section that should be retrieved
CASES = [
    ("how do I get my money back?",                   "Refunds"),
    ("refund window for the professional tier",       "Refunds"),
    ("what if I go over my request limit?",           "API"),
    ("how many calls can a Basic account make?",      "API"),
    ("how do I stop being billed?",                   "Cancellation"),
    ("does stopping my subscription refund me?",      "Cancellation"),
    ("when will my parcel arrive from overseas?",     "Shipping"),
    ("how long until deleted work is unrecoverable?", "Retention"),
]

stats = {"calls": 0}

def counted(fn):
    """Wrap an LLM call so we can count it."""
    def wrapper(*a, **kw):
        stats["calls"] += 1
        return fn(*a, **kw)
    return wrapper

# ── strategies ───────────────────────────────────────────────────────────
def baseline(q, k=3):
    return store.as_retriever(search_kwargs={"k": k}).invoke(q)

def mmr(q, k=3):
    return store.as_retriever(
        search_type="mmr",
        search_kwargs={"k": k, "fetch_k": 8, "lambda_mult": 0.5}).invoke(q)

class Variations(BaseModel):
    """Alternative phrasings."""
    queries: list[str] = Field(description="3 alternative phrasings, different vocabulary")

def multi_query(q, k=3):
    stats["calls"] += 1
    result = fast.with_structured_output(Variations, method="json_schema", strict=True).invoke(
        f"Generate 3 alternative phrasings for document search.\n\nQuestion: {q}")
    seen, merged = set(), []
    for query in [q] + result.queries:
        for d in store.as_retriever(search_kwargs={"k": 2}).invoke(query):
            if d.page_content not in seen:
                seen.add(d.page_content)
                merged.append(d)
    return merged[:k]

hyde_chain = ChatPromptTemplate.from_messages([
    ("system", "Write a 2-sentence passage from a company handbook answering the question. "
               "A factual statement, not a question. Accuracy doesn't matter — style does."),
    ("human", "{question}"),
]) | fast | StrOutputParser()

def hyde(q, k=3):
    stats["calls"] += 1
    return store.similarity_search(hyde_chain.invoke({"question": q}), k=k)

class Relevance(BaseModel):
    """Relevance of a document to a question."""
    score: float = Field(ge=0, le=10, description="0 = irrelevant, 10 = directly answers")

def rerank(q, k=3, fetch=8):
    candidates = store.as_retriever(search_kwargs={"k": fetch}).invoke(q)
    scored = []
    for d in candidates:
        stats["calls"] += 1
        r = fast.with_structured_output(Relevance, method="json_schema", strict=True).invoke(
            f"Question: {q}\n\nDocument: {d.page_content}\n\nRelevance?")
        scored.append((d, r.score))
    return [d for d, _ in sorted(scored, key=lambda x: -x[1])[:k]]

STRATEGIES = {
    "baseline":     baseline,
    "mmr":          mmr,
    "multi-query":  multi_query,
    "hyde":         hyde,
    "rerank(8→3)":  rerank,
}

# ── evaluate ─────────────────────────────────────────────────────────────
print("strategy       recall@3   ms/query   LLM calls/query")
print("-" * 58)

results = {}
for name, fn in STRATEGIES.items():
    stats["calls"] = 0
    t0 = time.time()
    hits = 0

    for question, expected in CASES:
        docs = fn(question, 3)
        if any(d.metadata["section"] == expected for d in docs):
            hits += 1

    ms = (time.time() - t0) * 1000 / len(CASES)
    calls = stats["calls"] / len(CASES)
    recall = hits / len(CASES)
    results[name] = (recall, ms, calls)

    print(f"{name:<14} {recall:>8.2f}   {ms:>8.0f}   {calls:>15.1f}")

# ── verdict ──────────────────────────────────────────────────────────────
base_recall = results["baseline"][0]
print(f"\nbaseline recall: {base_recall:.2f}\n")
for name, (recall, ms, calls) in results.items():
    if name == "baseline":
        continue
    delta = recall - base_recall
    verdict = "✅ worth it" if delta > 0.05 else "🟡 marginal" if delta > 0 else "❌ no gain"
    print(f"  {name:<14} {delta:+.2f} recall for {calls:.1f} extra calls  {verdict}")
```

**JavaScript** — same structure; the strategy signatures:
```js
const STRATEGIES = {
  baseline: (q, k) => store.asRetriever({ k }).invoke(q),
  mmr: (q, k) => store.asRetriever({
    searchType: "mmr", searchKwargs: { k, fetchK: 8, lambda: 0.5 } }).invoke(q),
  "multi-query": multiQuery,
  hyde: hydeRetrieve,
  "rerank(8→3)": (q, k) => rerankRetrieve(q, k, 8),
};
```

**Typical output:**

Your numbers will differ — this output is illustrative.

```
strategy       recall@3   ms/query   LLM calls/query
----------------------------------------------------------
baseline           0.75         38               0.0
mmr                0.75         52               0.0
multi-query        0.88        310               1.0
hyde               0.88        290               1.0
rerank(8→3)        1.00       1840               8.0

baseline recall: 0.75

  mmr            +0.00 recall for 0.0 extra calls  ❌ no gain
  multi-query    +0.13 recall for 1.0 extra calls  ✅ worth it
  hyde           +0.13 recall for 1.0 extra calls  ✅ worth it
  rerank(8→3)    +0.25 recall for 8.0 extra calls  ✅ worth it
```

**Four conclusions worth internalising:**

1. **Reranking wins on recall and loses on latency** — 8 extra calls and ~1.8s. In production
   you'd use a hosted cross-encoder (Cohere/Voyage) instead: one API call (typically a few
   hundred ms at most), similar benefit.
   The LLM version is the free proof of concept.
2. **MMR shows no recall gain here** — and that's *correct*, because MMR optimises for
   **diversity**, not recall. Measuring it with recall@k is measuring the wrong thing. Its real
   benefit shows up as unique-sections-covered, or in answer quality on comparison questions.
   A reminder that the metric has to match the technique's purpose.
3. **Multi-query and HyDE cost one call each for a real gain** — the best ratio in the table.
4. **Baseline is already 75%.** Advanced techniques are refinements, not rescues. If your
   baseline were 40%, the problem would be chunking or embedding, and none of these would fix it.

**Extend this** with your own corpus. The ranking of techniques is corpus-dependent — HyDE shines
on technical jargon, MMR on redundant corpora, self-query where metadata matters.
</details>

---

### Exercise 2 — Parent-document retrieval ●●●○○

Implement parent-document retrieval by hand: index small child chunks for precise matching, but
return the larger parent chunk for context. Compare answer quality against retrieving the small
chunks directly.

<details>
<summary>✅ Solution</summary>

**Python**
```python
# day13_parent_document.py
import uuid
from dotenv import load_dotenv
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_text_splitters import RecursiveCharacterTextSplitter
from day13_setup import embeddings, smart

load_dotenv()

DOCUMENT = """Refund Policy

Customers may request a refund within 30 days of purchase for Basic plans, and within 60 days for Pro plans. To request a refund, contact billing@acme.com with your order number. Refunds are processed within 5 business days of approval and returned to the original payment method. Note that refunds are not automatic on cancellation — they must be requested separately. Enterprise customers should contact their account manager, as enterprise refunds are handled case by case under the terms of the master agreement.

API Rate Limits

The API allows 1000 requests per minute for Pro accounts and 100 requests per minute for Basic accounts. Exceeding the limit returns HTTP 429 with a Retry-After header indicating how many seconds to wait. Persistent violation may result in temporary suspension. Enterprise accounts have custom limits negotiated per contract. Rate limits are applied per API key, not per account, so multiple keys can be used to increase effective throughput within fair-use terms."""

# ── build: big parents, small children ───────────────────────────────────
parent_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=0)
child_splitter = RecursiveCharacterTextSplitter(chunk_size=200, chunk_overlap=20)

parents = {}          # id → parent Document
children = []         # small chunks, each carrying its parent's id

for parent_text in parent_splitter.split_text(DOCUMENT):
    pid = str(uuid.uuid4())[:8]
    parents[pid] = Document(page_content=parent_text, metadata={"parent_id": pid})

    for child_text in child_splitter.split_text(parent_text):
        children.append(Document(page_content=child_text, metadata={"parent_id": pid}))

print(f"{len(parents)} parents (~800 chars) · {len(children)} children (~200 chars)\n")

# Only the CHILDREN are indexed — precise matching
child_store = InMemoryVectorStore.from_documents(children, embeddings)

def retrieve_children(question, k=3):
    return child_store.similarity_search(question, k=k)

def retrieve_parents(question, k=3):
    """Match on children, return their deduplicated parents."""
    hits = child_store.similarity_search(question, k=k)
    seen, out = set(), []
    for child in hits:
        pid = child.metadata["parent_id"]
        if pid in seen:
            continue
        seen.add(pid)
        out.append(parents[pid])
    return out

# ── compare ──────────────────────────────────────────────────────────────
answer_chain = ChatPromptTemplate.from_messages([
    ("system", "Answer using ONLY the context. Be specific and complete. "
               "If details are missing, say what's missing.\n\nContext:\n{context}"),
    ("human", "{question}"),
]) | smart | StrOutputParser()

QUESTIONS = [
    "How do I request a refund and how long does it take?",
    "What happens if I exceed the rate limit, and can I get around it?",
]

for question in QUESTIONS:
    print(f"{'═' * 76}\n❓ {question}\n{'═' * 76}")

    for label, retrieve in [("CHILD chunks", retrieve_children),
                            ("PARENT chunks", retrieve_parents)]:
        docs = retrieve(question, 3)
        context = "\n\n---\n\n".join(d.page_content for d in docs)
        answer = answer_chain.invoke({"context": context, "question": question})

        print(f"\n── {label} ({len(docs)} docs, {len(context)} chars) ──")
        print(f"{answer[:340]}")
    print()
```

**JavaScript** — the core mapping:
```js
const parents = new Map();          // id → parent Document
const children = [];

for (const parentText of await parentSplitter.splitText(DOCUMENT)) {
  const pid = crypto.randomUUID().slice(0, 8);
  parents.set(pid, new Document({ pageContent: parentText, metadata: { parentId: pid } }));

  for (const childText of await childSplitter.splitText(parentText)) {
    children.push(new Document({ pageContent: childText, metadata: { parentId: pid } }));
  }
}

const childStore = await MemoryVectorStore.fromDocuments(children, embeddings);

async function retrieveParents(question, k = 3) {
  const hits = await childStore.similaritySearch(question, k);
  const seen = new Set();
  return hits
    .map((c) => c.metadata.parentId)
    .filter((pid) => !seen.has(pid) && seen.add(pid))
    .map((pid) => parents.get(pid));
}
```

<details>
<summary>📦 The built-in ParentDocumentRetriever</summary>

**Python**
```python
from langchain_classic.retrievers import ParentDocumentRetriever
from langchain_core.stores import InMemoryStore

retriever = ParentDocumentRetriever(
    vectorstore=InMemoryVectorStore(embeddings),
    docstore=InMemoryStore(),
    child_splitter=RecursiveCharacterTextSplitter(chunk_size=200),
    parent_splitter=RecursiveCharacterTextSplitter(chunk_size=800),
)
retriever.add_documents([Document(page_content=DOCUMENT)])
docs = retriever.invoke("how do I request a refund?")
```

**JavaScript**
```js
import { ParentDocumentRetriever } from "@langchain/classic/retrievers/parent_document";
import { InMemoryStore } from "@langchain/classic/storage/in_memory";
```
</details>

**What you should observe:**

Child chunks retrieve *precisely* — the matched 200-char chunk is exactly on topic. But the
answer is incomplete: it might say refunds take 5 business days while missing that you email
billing@acme.com, because that sentence landed in a neighbouring child chunk.

Parent chunks give the model the full policy paragraph, so the answer covers the whole process.

**The trade-off, stated plainly:**

| | Child chunks | Parent chunks |
|---|---|---|
| Retrieval precision | ✅ high (small, focused vectors) | — |
| Answer completeness | ❌ fragmented | ✅ full context |
| Tokens per document | ~200 | ~800 |
| Deduplication | n/a | ⭐ essential — 3 children often share 1 parent |

**That dedup step is the detail people miss.** Three child hits often belong to one parent.
Without deduplication you'd send the same 800-character parent three times. Most of your context
budget would go on repeats.

**Where this shines:** technical documentation and legal text. There, the phrase you search for
and the passage you answer from are genuinely different sizes. It solves Day 09's chunk-size
dilemma by refusing to choose.
</details>

---

### Exercise 3 — Self-RAG with answer grading ●●●●○

Build a Self-RAG loop that grades the generated answer on two axes:

- **grounded** — supported by the retrieved documents;
- **relevant** — actually answers the question.

Take a different action for each failure: regenerate if ungrounded, re-retrieve if irrelevant.
Bound the loop and log every decision.

<details>
<summary>✅ Solution</summary>

**Python**
```python
# day13_self_rag.py
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from day13_setup import store, fast, smart, format_docs

class Groundedness(BaseModel):
    """Whether an answer is supported by the provided documents."""
    reasoning: str = Field(description="One sentence. Write this first.")
    grounded: bool = Field(description="Is EVERY claim supported by the documents?")
    unsupported_claims: list[str] = Field(description="Claims not found in the documents")

class Usefulness(BaseModel):
    """Whether an answer addresses the question."""
    reasoning: str = Field(description="One sentence. Write this first.")
    answers_question: bool = Field(description="Does this actually answer what was asked?")

class Rewrite(BaseModel):
    """An improved search query."""
    rewritten: str = Field(description="A different search query, new vocabulary")

answer_chain = ChatPromptTemplate.from_messages([
    ("system", "Answer using ONLY the context. Cite as [1], [2]. "
               "If the context lacks the answer, say so plainly.\n\nContext:\n{context}"),
    ("human", "{question}"),
]) | smart | StrOutputParser()

def self_rag(question, max_loops=3):
    query = question
    log = []

    for loop in range(1, max_loops + 1):
        # ── retrieve ─────────────────────────────────────────────────────
        docs = store.as_retriever(search_kwargs={"k": 4}).invoke(query)
        context = format_docs(docs)
        log.append(f"loop {loop}: retrieved {len(docs)} docs for \"{query}\"")

        # ── generate ─────────────────────────────────────────────────────
        answer = answer_chain.invoke({"context": context, "question": question})

        # ── grade 1: is it GROUNDED? ─────────────────────────────────────
        g = fast.with_structured_output(Groundedness, method="json_schema", strict=True).invoke(
            f"Documents:\n{context}\n\nAnswer:\n{answer}\n\n"
            f"Is every claim in the answer supported by the documents?")

        if not g.grounded:
            log.append(f"  ❌ ungrounded: {', '.join(g.unsupported_claims[:2])}")
            log.append("  → regenerating with a stricter prompt (same docs)")

            # Regenerate with the SAME docs but a harder constraint
            answer = (ChatPromptTemplate.from_messages([
                ("system", "Answer using ONLY the context. Every sentence must be directly "
                           "supported by a numbered source. If you cannot support a claim, "
                           "omit it. If nothing is supported, say you don't have the "
                           "information.\n\nContext:\n{context}"),
                ("human", "{question}"),
            ]) | smart | StrOutputParser()).invoke(
                {"context": context, "question": question})

            g2 = fast.with_structured_output(
                Groundedness, method="json_schema", strict=True).invoke(
                f"Documents:\n{context}\n\nAnswer:\n{answer}\n\nEvery claim supported?")
            if not g2.grounded:
                log.append("  ❌ still ungrounded after regeneration")
                if loop == max_loops:
                    return {"answer": "I couldn't produce a reliably grounded answer.",
                            "docs": docs, "log": log, "status": "ungrounded"}
                continue
            log.append("  ✅ grounded after regeneration")
        else:
            log.append("  ✅ grounded")

        # ── grade 2: does it ANSWER the question? ────────────────────────
        u = fast.with_structured_output(Usefulness, method="json_schema", strict=True).invoke(
            f"Question: {question}\n\nAnswer: {answer}\n\nDoes this answer the question?")

        if u.answers_question:
            log.append("  ✅ answers the question → done")
            return {"answer": answer, "docs": docs, "log": log, "status": "ok"}

        log.append(f"  ❌ doesn't answer: {u.reasoning}")

        # ── not useful → RE-RETRIEVE with a new query ────────────────────
        if loop < max_loops:
            r = fast.with_structured_output(Rewrite, method="json_schema", strict=True).invoke(
                f'The query "{query}" retrieved documents that did not answer: "{question}". '
                f"Write a DIFFERENT search query using other vocabulary.")
            query = r.rewritten
            log.append(f"  → re-retrieving with \"{query}\"")

    return {"answer": "I couldn't find an answer after several attempts.",
            "docs": [], "log": log, "status": "exhausted"}

# ── run ──────────────────────────────────────────────────────────────────
for q in [
    "How long do I have to get a refund on Pro?",       # should succeed turn one
    "can I get cash back on the professional tier?",    # odd phrasing, may need a retry
    "what is the company's annual revenue?",            # genuinely absent
]:
    print(f"\n{'═' * 76}\n❓ {q}\n{'═' * 76}")
    r = self_rag(q)
    for line in r["log"]:
        print(f"  {line}")
    print(f"\n  [{r['status']}] {r['answer'][:200]}")
```

**JavaScript** — the two-grader structure:
```js
// grade 1: grounded?
const g = await fast.withStructuredOutput(Groundedness, { method: "jsonSchema" }).invoke(
  `Documents:\n${context}\n\nAnswer:\n${answer}\n\nIs every claim supported?`);

if (!g.grounded) {
  // regenerate with the SAME docs, stricter prompt
  answer = await strictChain.invoke({ context, question });
}

// grade 2: useful?
const u = await fast.withStructuredOutput(Usefulness, { method: "jsonSchema" }).invoke(
  `Question: ${question}\n\nAnswer: ${answer}\n\nDoes this answer the question?`);

if (!u.answersQuestion && loop < maxLoops) {
  query = (await fast.withStructuredOutput(Rewrite, { method: "jsonSchema" })
    .invoke(/* ... */)).rewritten;
  continue;                                    // ← re-RETRIEVE, don't just regenerate
}
```

**The design insight this exercise teaches:** the two grades imply **different actions**.

| Failure | Diagnosis | Action |
|---|---|---|
| Ungrounded | The model invented something; the docs may be fine | **Regenerate** with the same docs and a stricter prompt |
| Not useful | The docs genuinely don't contain the answer | **Re-retrieve** with a different query |

Mixing the two up is the common mistake. Re-retrieving because of a hallucination (an invented
claim) wastes a retrieval when the documents were already correct. Regenerating from irrelevant
documents just produces a different wrong answer from the same bad context.

**The cost is real:** up to 3 loops × (retrieve + generate + 2 grades) — about 12 LLM calls in the
worst case. Mitigations: a cheap model for the graders (done here), Self-RAG only for high-stakes
queries, and heavy caching.

**And notice how awkward this code is.** You're managing loop counters, saved state, a log and
several exit conditions by hand, with `continue` statements controlling the flow. Adding streaming
or a human approval step would make it much worse.

This is a **state machine written as a while loop**. LangGraph's whole idea is to let you declare
it as nodes and conditional edges instead. It handles state, persistence and interrupts for you.
Week 3 rebuilds exactly this pattern as a graph, and the comparison teaches a lot.
</details>

---

### Exercise 4 — Adaptive RAG router ●●●●○

Not every question needs retrieval. Build a router that classifies each question and picks a
strategy: **no retrieval** (greetings, general knowledge), **simple retrieval** (one fact),
**multi-query** (comparison or multi-part), or **self-query** (has metadata constraints). Report
which path each question took and the cost saved.

<details>
<summary>✅ Solution</summary>

**Python**
```python
# day13_adaptive.py
import time
from typing import Literal
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from day13_setup import store, fast, smart, format_docs

class Route(BaseModel):
    """Which retrieval strategy a question needs."""
    reasoning: str = Field(description="One sentence. Write this first.")
    strategy: Literal["none", "simple", "multi", "filtered"] = Field(
        description="none = greeting/chitchat/general knowledge needing no documents; "
                    "simple = one specific fact from the docs; "
                    "multi = comparison or multi-part question needing several searches; "
                    "filtered = mentions a specific plan, year or section to filter by")

router = (fast.with_structured_output(Route, method="json_schema", strict=True)
          .with_config(run_name="route_question"))

class Variations(BaseModel):
    """Alternative phrasings."""
    queries: list[str] = Field(description="2-3 sub-queries covering each part of the question")

class Filters(BaseModel):
    """Extracted metadata constraints."""
    semantic_query: str
    section: Literal["Refunds", "Cancellation", "API", "Shipping", "Retention", "any"]
    plan: Literal["Basic", "Pro", "all", "any"]

answer_chain = ChatPromptTemplate.from_messages([
    ("system", "Answer using ONLY the context. Cite as [1], [2].\n\nContext:\n{context}"),
    ("human", "{question}"),
]) | smart | StrOutputParser()

direct_chain = ChatPromptTemplate.from_messages([
    ("system", "You are a friendly assistant. Answer briefly. "
               "If the question needs company-specific data you don't have, say so."),
    ("human", "{question}"),
]) | fast | StrOutputParser()

stats = {"calls": 0, "retrievals": 0}

def adaptive_rag(question):
    stats["calls"] += 1
    route = router.invoke(
        f"Classify what retrieval strategy this question needs.\n\n"
        f"The document corpus covers: refunds, cancellation, API rate limits, shipping, "
        f"data retention — for Basic and Pro plans.\n\nQuestion: {question}")

    # ── none: skip retrieval entirely ────────────────────────────────────
    if route.strategy == "none":
        stats["calls"] += 1
        return {"strategy": "none", "docs": [],
                "answer": direct_chain.invoke({"question": question}),
                "reasoning": route.reasoning}

    # ── simple: one retrieval ────────────────────────────────────────────
    if route.strategy == "simple":
        stats["retrievals"] += 1
        docs = store.as_retriever(search_kwargs={"k": 3}).invoke(question)

    # ── multi: decompose into sub-queries ────────────────────────────────
    elif route.strategy == "multi":
        stats["calls"] += 1
        v = fast.with_structured_output(Variations, method="json_schema", strict=True).invoke(
            f"Break this question into 2-3 focused search queries, one per part.\n\n"
            f"Question: {question}")
        seen, docs = set(), []
        for q in v.queries:
            stats["retrievals"] += 1
            for d in store.as_retriever(search_kwargs={"k": 2}).invoke(q):
                if d.page_content not in seen:
                    seen.add(d.page_content)
                    docs.append(d)

    # ── filtered: extract metadata constraints ───────────────────────────
    else:
        stats["calls"] += 1
        f = fast.with_structured_output(Filters, method="json_schema", strict=True).invoke(
            f"Extract the semantic query and metadata filters.\n"
            f"Sections: Refunds|Cancellation|API|Shipping|Retention. "
            f"Plans: Basic|Pro|all.\n\nQuestion: {question}")

        def filter_fn(d):
            m = d.metadata
            if f.section != "any" and m["section"] != f.section:
                return False
            if f.plan != "any" and m["plan"] not in (f.plan, "all"):
                return False
            return True

        stats["retrievals"] += 1
        docs = store.similarity_search(f.semantic_query, k=3, filter=filter_fn)

    stats["calls"] += 1
    answer = answer_chain.invoke({"context": format_docs(docs), "question": question})
    return {"strategy": route.strategy, "docs": docs, "answer": answer,
            "reasoning": route.reasoning}

# ── run ──────────────────────────────────────────────────────────────────
QUESTIONS = [
    "hello there!",                                          # none
    "what is 15% of 240?",                                   # none
    "How long for a refund on Pro?",                         # simple
    "Compare the refund policy with the cancellation policy", # multi
    "What are the API limits and refund window for Basic?",  # multi
    "Tell me about Pro plan API limits",                     # filtered
]

print("question                                    strategy    docs  reasoning")
print("-" * 100)

for q in QUESTIONS:
    r = adaptive_rag(q)
    print(f"{q[:42]:<42}  {r['strategy']:<10}  {len(r['docs']):>4}  {r['reasoning'][:38]}")

print(f"\ntotal: {stats['calls']} LLM calls · {stats['retrievals']} retrievals "
      f"across {len(QUESTIONS)} questions")

naive = len(QUESTIONS) * 1                    # naive: 1 retrieval each
print(f"naive RAG would do {naive} retrievals (including {2} pointless ones "
      f"for greetings/arithmetic)")
```

**JavaScript** — the routing switch:
```js
const route = await router.invoke(`Classify… Question: ${question}`);

switch (route.strategy) {
  case "none":
    return { strategy: "none", docs: [], answer: await directChain.invoke({ question }) };

  case "simple":
    docs = await store.asRetriever({ k: 3 }).invoke(question);
    break;

  case "multi": {
    const { queries } = await fast
      .withStructuredOutput(Variations, { method: "jsonSchema" }).invoke(/* ... */);
    const sets = await Promise.all(queries.map((q) => store.asRetriever({ k: 2 }).invoke(q)));
    docs = dedupe(sets.flat());
    break;
  }

  case "filtered": {
    const f = await fast.withStructuredOutput(Filters, { method: "jsonSchema" }).invoke(/* ... */);
    docs = await store.similaritySearch(f.semanticQuery, 3, buildFilter(f));
    break;
  }
}
```

**Typical output:**

Your numbers will differ — this output is illustrative.

```
question                                    strategy    docs  reasoning
----------------------------------------------------------------------------------------------------
hello there!                                none           0  A greeting requires no document lookup
what is 15% of 240?                         none           0  Arithmetic needs no company documents
How long for a refund on Pro?               simple         3  A single specific fact from the docs
Compare the refund policy with the cance…   multi          4  Comparison needs both policies retrieved
What are the API limits and refund windo…   multi          4  Two distinct facts from two sections
Tell me about Pro plan API limits           filtered       2  Names a specific plan and section
```

**Three things worth drawing out:**

1. **Skipping retrieval is a real saving, not a tiny one.** In a production assistant, a
   meaningful share of turns are greetings, thank-yous ("thanks!") or general questions.
   Retrieving for those wastes an embedding call and adds latency. Worse, it can pull in
   irrelevant documents that *degrade* the answer, because the model tries to use what you gave
   it.

2. **The `multi` path handles comparisons, which naive RAG genuinely can't.** "Compare refunds
   with cancellation" embedded as one query lands between the two topics. It often retrieves
   neither well. Splitting it into sub-queries retrieves both cleanly.

3. **The router itself must be cheap and must fail safe.** It runs on every request. Use the
   small model, and give it a fallback value: if classification fails, default to `simple`
   instead of throwing an error. A router that takes down the whole system when it misbehaves is
   worse than no router.

**The honest caveat:** the router adds one call to *every* request, including the simple ones.
It pays for itself when a good share of traffic skips retrieval or truly needs the multi path.
Measure your real mix of questions before assuming it's worth it. On a corpus where every
question is a simple lookup, a router is pure overhead.
</details>

---

### Exercise 5 — 🏆 Production RAG pipeline ●●●●●

Combine the techniques that earn their cost into one configurable pipeline. The stages, in order:

1. hybrid retrieval;
2. optional query transform;
3. wide retrieval;
4. rerank;
5. compress;
6. generate with verified citations;
7. optional corrective retry.

Make every stage something you can switch on or off, and report the time each stage takes. Show
the difference between a minimal and a full configuration.

<details>
<summary>✅ Solution</summary>

**Python**
```python
# production_rag.py
"""A configurable production RAG pipeline. Every stage can be toggled."""
import re, time
from dataclasses import dataclass, field
from typing import Literal, Optional
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from day13_setup import store, fast, smart, DOCS

# ══════════════════ CONFIG ═══════════════════════════════════════════════
@dataclass
class RagConfig:
    query_transform: Literal["none", "multi", "hyde"] = "none"
    hybrid: bool = False
    fetch_k: int = 4
    rerank: bool = False
    rerank_to: int = 3
    compress: bool = False
    corrective: bool = False
    max_attempts: int = 2
    verify_citations: bool = True

# ══════════════════ SCHEMAS ══════════════════════════════════════════════
class Variations(BaseModel):
    """Alternative phrasings for retrieval."""
    queries: list[str] = Field(description="2 alternative phrasings, different vocabulary")

class Relevance(BaseModel):
    """Document relevance to a question."""
    score: float = Field(ge=0, le=10, description="0 = irrelevant, 10 = directly answers")

class Citation(BaseModel):
    source_number: int = Field(description="The [n] number of the source")
    quote: str = Field(description="EXACT sentence from that source, verbatim")

class Answer(BaseModel):
    """A grounded answer with verifiable citations."""
    answer: str = Field(description="The answer in prose, no citation markers")
    citations: list[Citation] = Field(description="One per claim. Empty if not answerable.")
    answer_found: bool = Field(description="False if the context lacks the answer")

# ══════════════════ BM25 (Day 11) ════════════════════════════════════════
import math

class BM25:
    def __init__(self, docs, k1=1.5, b=0.75):
        self.k1, self.b, self.docs = k1, b, docs
        self.toks = [self.tok(d.page_content) for d in docs]
        self.avg = sum(len(t) for t in self.toks) / max(len(docs), 1)
        self.df = {}
        for t in self.toks:
            for w in set(t):
                self.df[w] = self.df.get(w, 0) + 1
        self.N = len(docs)

    @staticmethod
    def tok(s):
        return re.findall(r"[a-z0-9_]+", s.lower())

    def search(self, query, k=5):
        q = self.tok(query)
        out = []
        for i, toks in enumerate(self.toks):
            score = 0.0
            for w in q:
                tf = toks.count(w)
                if not tf:
                    continue
                idf = math.log(1 + (self.N - self.df.get(w, 0) + 0.5) / (self.df.get(w, 0) + 0.5))
                score += idf * (tf * (self.k1 + 1)) / (tf + self.k1 * (
                    1 - self.b + self.b * len(toks) / self.avg))
            if score > 0:
                out.append((self.docs[i], score))
        return [d for d, _ in sorted(out, key=lambda x: -x[1])[:k]]

bm25 = BM25(DOCS)

# ══════════════════ STAGES ═══════════════════════════════════════════════
hyde_chain = ChatPromptTemplate.from_messages([
    ("system", "Write a 2-sentence handbook passage answering the question. "
               "A factual statement. Style matters, accuracy does not."),
    ("human", "{question}"),
]) | fast | StrOutputParser()

def transform_query(question, cfg, timings):
    if cfg.query_transform == "none":
        return [question]

    t0 = time.time()
    if cfg.query_transform == "multi":
        v = fast.with_structured_output(Variations, method="json_schema", strict=True).invoke(
            f"Generate 2 alternative phrasings for search.\n\nQuestion: {question}")
        result = [question] + v.queries
    else:  # hyde
        result = [hyde_chain.invoke({"question": question})]

    timings["transform"] = (time.time() - t0) * 1000
    return result

def retrieve(queries, cfg, timings):
    t0 = time.time()
    seen, docs = set(), []

    for q in queries:
        for d in store.as_retriever(search_kwargs={"k": cfg.fetch_k}).invoke(q):
            if d.page_content not in seen:
                seen.add(d.page_content)
                docs.append(d)

        if cfg.hybrid:
            for d in bm25.search(q, cfg.fetch_k):
                if d.page_content not in seen:
                    seen.add(d.page_content)
                    docs.append(d)

    timings["retrieve"] = (time.time() - t0) * 1000
    return docs

def rerank(question, docs, cfg, timings):
    if not cfg.rerank or len(docs) <= cfg.rerank_to:
        return docs

    t0 = time.time()
    scored = []
    for d in docs:
        r = fast.with_structured_output(Relevance, method="json_schema", strict=True).invoke(
            f"Question: {question}\n\nDocument: {d.page_content}\n\nRelevance 0-10?")
        scored.append((d, r.score))

    timings["rerank"] = (time.time() - t0) * 1000
    return [d for d, _ in sorted(scored, key=lambda x: -x[1])[:cfg.rerank_to]]

def compress(question, docs, cfg, timings):
    if not cfg.compress:
        return docs

    from langchain_classic.retrievers.document_compressors import EmbeddingsFilter
    from day13_setup import embeddings

    t0 = time.time()
    kept = EmbeddingsFilter(embeddings=embeddings, similarity_threshold=0.4) \
        .compress_documents(docs, question)
    timings["compress"] = (time.time() - t0) * 1000
    return list(kept) or docs          # never compress to nothing

# ══════════════════ GENERATION ═══════════════════════════════════════════
answer_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "Answer using ONLY the numbered context. For every factual claim provide a citation "
     "with the source number and the EXACT sentence copied verbatim. "
     "If the context lacks the answer, set answer_found to false.\n\nContext:\n{context}"),
    ("human", "{question}"),
])

def format_docs(docs):
    return "\n\n---\n\n".join(
        f"[{i}] ({d.metadata.get('section', '?')}) {d.page_content}"
        for i, d in enumerate(docs, 1))

def verify(citation, docs):
    idx = citation.source_number - 1
    if not (0 <= idx < len(docs)):
        return False
    norm = lambda s: re.sub(r"\s+", " ", s.lower().strip())
    return norm(citation.quote)[:45] in norm(docs[idx].page_content)

# ══════════════════ PIPELINE ═════════════════════════════════════════════
def run(question, cfg: RagConfig):
    timings, log = {}, []
    total0 = time.time()

    for attempt in range(1, cfg.max_attempts + 1 if cfg.corrective else 2):
        queries = transform_query(question, cfg, timings)
        if len(queries) > 1 or queries[0] != question:
            log.append(f"transform → {len(queries)} query/queries")

        docs = retrieve(queries, cfg, timings)
        log.append(f"retrieve → {len(docs)} candidates"
                   f"{' (hybrid)' if cfg.hybrid else ''}")

        docs = rerank(question, docs, cfg, timings)
        if cfg.rerank:
            log.append(f"rerank → {len(docs)}")

        docs = compress(question, docs, cfg, timings)
        if cfg.compress:
            log.append(f"compress → {len(docs)}")

        t0 = time.time()
        answerer = answer_prompt | smart.with_structured_output(
            Answer, method="json_schema", strict=True)
        result = answerer.invoke(
            {"context": format_docs(docs), "question": question})
        timings["generate"] = (time.time() - t0) * 1000

        # ── corrective: retry once if nothing was found ──────────────────
        if cfg.corrective and not result.answer_found and attempt < cfg.max_attempts:
            log.append("❌ not found → retrying with multi-query")
            cfg = RagConfig(**{**cfg.__dict__, "query_transform": "multi"})
            continue
        break

    verified = 0
    if cfg.verify_citations and result.answer_found:
        verified = sum(1 for c in result.citations if verify(c, docs))

    timings["TOTAL"] = (time.time() - total0) * 1000

    return {"result": result, "docs": docs, "timings": timings, "log": log,
            "verified": verified, "citations": len(result.citations)}

# ══════════════════ COMPARE CONFIGURATIONS ═══════════════════════════════
CONFIGS = {
    "minimal": RagConfig(),
    "recommended": RagConfig(hybrid=True, fetch_k=8, rerank=True, rerank_to=3),
    "maximal": RagConfig(query_transform="multi", hybrid=True, fetch_k=8,
                         rerank=True, rerank_to=3, compress=True, corrective=True),
}

QUESTION = "can I cancel and get money back on the professional tier?"

for name, cfg in CONFIGS.items():
    print(f"\n{'═' * 76}\n{name.upper()}\n{'═' * 76}")
    out = run(QUESTION, cfg)

    for line in out["log"]:
        print(f"  {line}")

    print(f"\n  {out['result'].answer[:220]}\n")
    print(f"  citations: {out['verified']}/{out['citations']} verified")
    print("  timings: " + " · ".join(
        f"{k}={v:.0f}ms" for k, v in out["timings"].items()))
```

**JavaScript** — the config shape and stage pipeline:
```js
const CONFIGS = {
  minimal:     { queryTransform: "none", hybrid: false, fetchK: 4, rerank: false },
  recommended: { queryTransform: "none", hybrid: true,  fetchK: 8, rerank: true, rerankTo: 3 },
  maximal:     { queryTransform: "multi", hybrid: true, fetchK: 8, rerank: true, rerankTo: 3,
                 compress: true, corrective: true },
};

async function run(question, cfg) {
  const timings = {};
  const queries = await transformQuery(question, cfg, timings);
  let docs = await retrieve(queries, cfg, timings);
  docs = await rerank(question, docs, cfg, timings);
  docs = await compress(question, docs, cfg, timings);
  const result = await answerPrompt
    .pipe(smart.withStructuredOutput(Answer, { method: "jsonSchema" }))
    .invoke({ context: formatDocs(docs), question });
  return { result, docs, timings };
}
```

**Typical comparison:**

Your numbers will differ — this output is illustrative.

```
MINIMAL
  retrieve → 4 candidates
  citations: 1/2 verified
  timings: retrieve=41ms · generate=980ms · TOTAL=1021ms

RECOMMENDED
  retrieve → 9 candidates (hybrid)
  rerank → 3
  citations: 3/3 verified
  timings: retrieve=58ms · rerank=1610ms · generate=1040ms · TOTAL=2708ms

MAXIMAL
  transform → 3 query/queries
  retrieve → 10 candidates (hybrid)
  rerank → 3
  compress → 3
  citations: 3/3 verified
  timings: transform=340ms · retrieve=112ms · rerank=1580ms · compress=88ms ·
           generate=1010ms · TOTAL=3130ms
```

**Five things this pipeline demonstrates:**

1. **Reranking dominates the latency budget.** ~1.6s of a 2.7s total. In production you'd replace
   the LLM reranker with a hosted cross-encoder (Cohere, Voyage, Jina): one API call (typically
   a few hundred ms at most), a similar quality gain. This is the single most impactful production swap on this page.

2. **"Recommended" is the right default.** Hybrid + rerank captures most of the quality gain of
   "maximal" at about 87% of its latency in this illustrative run (2708 ms vs 3130 ms). Multi-query and compression add real cost for a smaller
   marginal benefit on most corpora — enable them where measurement justifies it.

3. **Citation verification catches the difference.** Minimal gets 1/2 verified; the reranked
   configurations get 3/3, because better documents make grounded answers easier. Verification
   rate is a useful *proxy* for retrieval quality that you can measure in production without
   labelled data.

4. **`compress()` never returns nothing.** Look at `return list(kept) or docs`. A threshold that
   is too strict could filter away every document. You would get an empty context and a
   guaranteed "I don't know". Optimisation stages need safety checks like this.

5. **Corrective retry changes the config for the next attempt.** It upgrades to multi-query
   instead of repeating the same failed search. Retrying the same query is pointless.

**What this design still can't do, and where Week 3 picks up:**

The corrective loop is a `for` loop with a `continue`. Suppose you add a third strategy, stream
progress to a UI, or pause for human approval before an expensive path. Each one means more flags
and more branches in an ever more tangled function.

You've now hand-built a state machine three times today: corrective RAG, self-RAG and this
pipeline. Each time the awkwardness is the same: **LCEL composes forward, but these problems
loop.** LangGraph makes the states and transitions explicit. It also gives you persistence,
streaming and interrupts for free.

That's Day 17 onward.
</details>

---

## 9. Interview questions

### Basic

<details>
<summary><b>Q: What is reranking and why does it help?</b></summary>

A two-stage retrieval pattern. First, a fast bi-encoder (your vector store) fetches a wide set of
candidates — say 20. Then a slower, more accurate cross-encoder scores them and keeps the best
3–5.

It helps because a bi-encoder embeds query and document *separately* and compares vectors. It
never sees them together. A cross-encoder reads `[query, document]` as a single input, with full
attention between them. So it judges actual relevance, not just vector closeness. It's far too
slow to run over a whole corpus, and ideal over 20 candidates.

In practice it's often the single biggest improvement you can add to a naive RAG pipeline, and
it needs no re-indexing. How many points of recall@k it buys depends on the corpus — measure it
on your own eval set.
</details>

<details>
<summary><b>Q: What is MMR?</b></summary>

Maximal Marginal Relevance — retrieval that balances relevance against diversity. Each candidate
is scored as `λ · relevance − (1−λ) · max_similarity_to_already_selected`. Documents are picked
greedily, one at a time.

It solves the problem where your top-5 are five paraphrases of the same sentence. That wastes the
context budget on one fact. `λ` around 0.5–0.7 is the useful range. Important detail: `fetchK`
must be much larger than `k`. Otherwise there's nothing to diversify from, and MMR does nothing.
</details>

<details>
<summary><b>Q: What is HyDE?</b></summary>

Hypothetical Document Embeddings. Instead of embedding the user's question, you have the model
write a hypothetical *answer* — a passage in the style of your documents. You embed that and
retrieve with it.

It works because questions and statements sit in consistently different regions of embedding
space. So a question's embedding is a poor stand-in for the document you want. The hypothetical
answer's factual accuracy is irrelevant. Only its vocabulary and shape matter. It's especially
effective in technical fields. It can hurt where the model knows nothing about the subject, so
measure it rather than assume.
</details>

<details>
<summary><b>Q: What is Corrective RAG?</b></summary>

RAG with a feedback loop on retrieval quality. You retrieve, grade each document for relevance,
and then branch:

- If enough documents are relevant, generate.
- If not, rewrite the query and retrieve again.
- If repeated attempts fail, fall back to another source or refuse honestly.

Two implementation details are essential. First, a hard attempt limit — a grader that never
approves would otherwise loop forever. Second, pass the queries you already tried into the
rewriter, so it must produce something genuinely different.
</details>

### Intermediate

<details>
<summary><b>Q: Bi-encoder vs cross-encoder — explain the trade-off.</b></summary>

A bi-encoder maps query and document to vectors *independently*. So document vectors can be
computed in advance, at ingest, and search is a cheap vector operation. That's what scales to
millions — and, with approximate-nearest-neighbour indexes, billions — of documents. The cost is that the model never sees the pair together. It judges how
close two vectors are, not real relevance.

A cross-encoder takes `[query, document]` as one input and runs the full transformer over both,
with attention flowing between them. It is much more accurate, but nothing can be computed in
advance. You pay for one forward pass (one full run of the model) per pair, so it can't run over a
whole corpus.

The production answer is to use both. The bi-encoder narrows 100k to 20 cheaply. The
cross-encoder narrows 20 to 4 accurately. That's the retrieve-wide-rerank-narrow pattern.
</details>

<details>
<summary><b>Q: When would you use parent-document retrieval?</b></summary>

When the ideal chunk size for *retrieval* differs from the ideal size for *answering*. Small
chunks embed sharply and match precisely. Large chunks carry enough context for the model to
produce a complete answer. Parent-document retrieval refuses to choose: index small children,
return their parents.

It's most valuable for technical documentation and legal text. There, the phrase you search for
is short, but the passage you answer from is a full paragraph or clause.

The implementation detail people miss is **deduplication**. Several child hits often belong to
the same parent. Returning that parent several times wastes most of your context budget.
</details>

<details>
<summary><b>Q: How do you decide which advanced RAG techniques to adopt?</b></summary>

Measure them one at a time, against an eval set with known correct chunks. And make sure the
metric matches the technique's purpose. Recall@k is right for reranking and multi-query. It's the
*wrong* metric for MMR. MMR optimises diversity, so it shows no recall gain even when it's working.

My default order, by return on cost:

1. **Hybrid search** first. It is nearly free, and it fixes the exact-identifier failure that
   embeddings can't handle.
2. **Reranking** next — the biggest single quality gain.

Those two cover most of the gap between demo and production. After that:

- query transforms (multi-query, HyDE) where queries are short or use different words from the
  documents;
- self-query where numeric or categorical filters matter;
- adaptive loops only where retrieval quality is genuinely inconsistent.

The prerequisite: fix chunking first. No retriever recovers an answer split across a chunk
boundary. Advanced retrieval on bad chunks is wasted effort.
</details>

<details>
<summary><b>Q: What's the difference between Corrective RAG and Self-RAG?</b></summary>

They grade different things and therefore take different actions.

**Corrective RAG** grades the *retrieved documents* before generating. If they're irrelevant it
rewrites the query and retrieves again, because the problem is upstream.

**Self-RAG** grades the *generated answer* — typically on two axes: is it grounded in the
retrieved documents, and does it actually address the question?

That two-axis split matters, because the failures need different fixes. Ungrounded means the
model invented something, while the documents may have been fine. So you **regenerate** with a
stricter prompt and the same documents. Not-useful means the documents genuinely lacked the
answer. So you **re-retrieve** with a different query. Mixing them up wastes retrievals on
hallucinations, and regenerates from context that was never going to work.

Both need bounded loops. In practice they compose.
</details>

### Advanced

<details>
<summary><b>Q: Design a RAG system where retrieval quality varies a lot across query types.</b></summary>

When quality varies across query types, that is the case for **Adaptive RAG**. Classify the
question first, then route it to a strategy that suits it. You stop paying for the most expensive
path on every request.

**Routing tiers.** A cheap classifier picks one of four routes:

- **No retrieval** — greetings, general knowledge, arithmetic. These are a meaningful share of
  real assistant traffic. Retrieving for them adds latency *and* can degrade the answer by adding
  irrelevant context.
- **Simple retrieval** — single-fact lookups.
- **Multi-query decomposition** — comparisons and multi-part questions. Naive RAG genuinely
  handles these badly, because one embedding of "compare A with B" lands between both topics.
- **Metadata-filtered retrieval** — the query carries numeric or categorical constraints that
  embeddings cannot express.

**The router must be cheap and fail safe.** It runs on every request, so use a small model. Give
it a fallback value, so a classification failure can't take down the system.

**Add a quality loop only where it pays.** Use corrective retry for query classes you've measured
as unreliable, and skip it for the reliable ones. Use cheap models for graders and rewriters, and
the strong model only for the final answer.

**Instrument by query class.** Track recall and answer quality *segmented by route* (measured
separately for each route). A global average hides the fact that comparisons are at 50% while
lookups are at 95%. That split tells you which route to invest in next. Most teams don't build
it.

**And be honest about the ceiling.** Some query classes need aggregation across the whole corpus
("how many contracts mention indemnity?"). No retrieval strategy fixes that. It's a
structured-data query, and the right answer is text-to-SQL or an agent with a database tool.
</details>

<details>
<summary><b>Q: Your RAG works well on simple questions but fails on complex multi-part ones. Diagnose and fix.</b></summary>

The mechanism is usually simple: a multi-part question produces **one embedding that is the
average of several topics**. "Compare the refund policy with the cancellation policy" lands
between the two regions. It retrieves a poor spread of both — often several chunks about one and
none about the other. It's the same dilution effect as an oversized chunk (one vector averaging
too many ideas), but on the query side.

**First, confirm that's actually the failure.** Check whether the required chunks for each
sub-part were retrieved at all. If they weren't, it's retrieval. If they were and the answer
still missed a part, it's generation.

**If retrieval:**
- **Query decomposition** is the main fix. Have the model split the question into focused
  sub-queries, retrieve for each, and merge with deduplication. This directly fixes the
  averaging problem.
- **Raise `k` and rerank**, so each sub-topic has room in the candidate set.
- **MMR** helps when one sub-topic's chunks crowd out the other's.

**If generation:**
- The relevant chunks may be buried in the middle of the context. Reduce `k` after reranking, or
  reorder them.
- The prompt may not ask for a complete answer. Ask explicitly for each part to be addressed, or
  use a structured output with one field per sub-question. Either forces full coverage.

**Genuinely multi-hop questions** are harder: the second retrieval depends on the first one's
answer ("what's the refund window for the plan with the highest rate limit?"). Decomposition
isn't enough here, because you can't write query two until query one returns. That needs
*iterative* retrieval, which is an agent loop: retrieve, reason, retrieve again. That's the point
where you move from LCEL to LangGraph.

Finally, build a multi-part section into the eval set and track it separately. A global accuracy
number will hide this class of failure entirely.
</details>

<details>
<summary><b>Q: You've added reranking, hybrid search, multi-query and compression. Latency is 6 seconds. Fix it.</b></summary>

First, **measure each stage** instead of guessing. Reranking is a common culprit: an LLM
scoring 20 documents one after another can take seconds on its own.

**The single biggest win: replace LLM reranking with a hosted cross-encoder.** Cohere, Voyage or
Jina rerank endpoints score 20 documents in one API call (typically a few hundred milliseconds at
most — check your provider). Compare that with 20 LLM calls in a row. You get a similar quality
benefit for a fraction of the latency and cost. If reranking was the dominant stage, this alone
can cut total latency substantially — re-measure to confirm.

**Then run in parallel what now runs one by one.** Multi-query retrievals are independent, so
send them at the same time. Document grading and scoring are independent, so batch them. Hybrid's
vector and BM25 halves are independent too. A surprising amount of RAG latency is sequential code
that didn't need to be.

**Then cut work that isn't earning its cost.** Measure how much each stage adds to recall, and
drop the ones with small gains. Compression in particular often costs more than it saves, unless
your chunks are large. Multi-query may be unnecessary if reranking is already doing the work.

**Then cache.** Cache query embeddings, retrieval results for repeated questions, and reranker
scores for (query, document) pairs. In real traffic a few questions are asked very often. So a
modest cache covers a large share of traffic.

**Then restructure for perceived latency** — how fast the system *feels* to users. Stream the
answer, and show the retrieved sources *before* generation starts. Retrieval typically finishes in a
fraction of a second, while generation takes seconds. Showing sources at once makes the system feel responsive, and lets
users start checking them.

**Finally, route adaptively.** Not every query needs the full pipeline. Simple lookups can skip
multi-query and compression entirely. Keep the expensive path for queries that need it.

The framing I'd give: latency work here is mostly about *choosing stages and running them in
parallel*, not tiny tweaks. It is also about separating true latency from perceived latency.
</details>

---

## 10. Recap

- ✅ Four intervention points: transform the **query**, change **retrieval**, post-process
  **results**, add a **feedback loop**
- ✅ **Hybrid search and reranking** give the most gain for the least cost — do these first
- ✅ Retrieve **wide** (20), rerank **narrow** (4) — the bi-encoder for scale, the cross-encoder
  for accuracy
- ✅ MMR fixes repeated results. It needs `fetchK` much larger than `k`, and recall is the wrong
  metric for it
- ✅ Multi-query fixes a wording mismatch. HyDE fixes the shape mismatch between questions and
  documents
- ✅ Parent-document: index small children, return large parents — **dedupe the parents**
- ✅ Self-query turns natural language into metadata filters that embeddings can't express
- ✅ Corrective RAG grades the **documents** and re-retrieves. Self-RAG grades the **answer** and
  regenerates
- ✅ **Bound every loop**, use cheap models for graders, and always have a terminal fallback
- ✅ Fix chunking before optimising retrieval — no retriever recovers a split answer

> 📏 **Measure it:** Take three questions from `CASES` in Exercise 1's `day13_bakeoff.py` and run
> each one through its `baseline` and `rerank` functions. Reranking counts as an improvement only
> if it finds the expected section for a question `baseline` missed, and loses none that
> `baseline` found. [Day 25](../week-04-production-projects-and-interviews/day-25-observability-and-evaluation.md)
> turns this quick check into a proper evaluation suite.

### Tomorrow

**[Day 14 — Memory](day-14-memory.md)**: the last piece of Week 2. You meet buffer, window,
summary, token and entity memory. You see what "memory" really means when the model is stateless
(it remembers nothing between calls). You see how memory works in modern LangChain:
`trimMessages`, history classes, and the shift to LangGraph checkpointers. And you build the
Week 2 project, which brings retrieval and memory together.

### Quick self-check

1. You retrieve 4 documents and rerank to 4. Why is this pointless?
2. Your Self-RAG grader says the answer is ungrounded. Should you re-retrieve or regenerate?
3. Which two techniques would you add first to a naive RAG pipeline, and why?

<details>
<summary>Answers</summary>

1. Reranking is about **selection**, not ordering. Reranking 4 down to 4 just reorders the same
   documents. The relevant one is either already there or it isn't. The value comes from
   retrieving 20–30 candidates cheaply and letting the cross-encoder pick the best few.
2. **Regenerate.** Ungrounded means the model invented a claim. The retrieved documents may be
   perfectly good. Regenerate with the same documents and a stricter prompt. Re-retrieve when the
   *usefulness* grader fails the answer — that's the signal the documents genuinely lack it.
3. **Hybrid search and reranking.** Hybrid is nearly free. It fixes the failures embeddings
   cannot handle (exact identifiers, error codes, names). Reranking is the largest single quality
   gain available, and needs no re-indexing. Neither requires a loop, so both are simple to add
   and easy to measure.
</details>

---

<div align="center">

**[← Day 12 — Naive RAG End-to-End (and Six Ways to Break It)](day-12-naive-rag.md)** · **[Week 2 index](README.md)** · **[Day 14 — Memory →](day-14-memory.md)**

</div>
