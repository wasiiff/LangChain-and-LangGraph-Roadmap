# Day 13 — Advanced RAG: Reranking, HyDE, Multi-Query & Self-Correction

> ⏱ **Time:** ~3 hours · 🎯 **Prereqs:** [Day 12](day-12-naive-rag.md) · 🧩 **Difficulty:** ●●●●○

**Today you learn:** the retriever zoo — MMR, multi-query, HyDE, reranking, parent-document,
contextual compression, self-query, ensemble — and the *adaptive* patterns that grade their own
retrieval and try again: Corrective RAG, Self-RAG, Adaptive RAG and Agentic RAG.

This is the day naive RAG becomes production RAG.

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

Every one of these has a named solution. Today you learn all of them, and — more importantly —
when each is worth its cost.

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
it belongs in — that narrows eight techniques to two.

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

**Why a cross-encoder is better:** a bi-encoder embeds the query and the document *separately*
and compares vectors — it never sees them together. A cross-encoder feeds `[query, document]`
into the model as one input, so it can judge actual relevance rather than vector proximity.

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

Notice these all have **loops**. LCEL is acyclic (Day 07), so today you'll build them with
bounded `while` loops — and feel exactly why LangGraph exists.

---

## 3. First principles

### 3.1 MMR — Maximal Marginal Relevance

Fixes: *"my top 5 are five paraphrases of one sentence."*

```
score(doc) = λ · relevance(doc, query) − (1 − λ) · max similarity(doc, already_selected)
                      ↑                              ↑
              how relevant is it?            how redundant is it?
```

Select greedily: pick the most relevant, then repeatedly pick whatever maximises that combined
score. `λ = 1` is pure relevance (identical to normal search); `λ = 0` is pure diversity.
**0.5–0.7 is the useful range.**

```js
store.asRetriever({ searchType: "mmr", searchKwargs: { fetchK: 20, lambda: 0.6, k: 4 } })
```

`fetchK` is the candidate pool MMR selects *from* — it must be larger than `k` or there's nothing
to diversify.

### 3.2 Multi-query — ask several ways

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

Costs one extra LLM call plus N retrievals (cheap, parallel). Reliably improves recall,
especially for short or vague queries.

### 3.3 HyDE — Hypothetical Document Embeddings

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

The hypothetical answer is often factually *wrong* — that doesn't matter. It only needs to be
*shaped* like the target documents. Counter-intuitive and genuinely effective, especially in
technical domains.

Cost: one extra LLM call and added latency. Worst case, a badly-off hypothetical retrieves worse
than the raw query — so measure it.

### 3.4 Reranking with a cross-encoder

Fixes: *"the right chunk is in my top 20 but not my top 4."*

The highest-leverage single change you can make to a RAG pipeline. LangChain's
`ContextualCompressionRetriever` wraps a base retriever with a compressor; the compressor can be
a reranker or an LLM-based extractor.

Without a hosted reranker (Cohere, Voyage, Jina) you can use an **LLM as the reranker** — slower
and pricier, but works with the models you already have. That's what we'll build.

### 3.5 Parent-document retrieval

Fixes: *"small chunks retrieve well but lack context; large chunks have context but retrieve badly."*

```
   INDEX small child chunks (400 chars)  →  precise matching
   RETURN the large parent chunk (2000)  →  full context for the answer

   ┌─────────── parent (returned) ───────────┐
   │ child │ child │ child │ child │ child   │
   └───────────────────────────────────────────┘
              ▲ matched here
```

You get precision *and* context. The cost is a document store alongside the vector store, and
more tokens per retrieved item.

### 3.6 Contextual compression

Fixes: *"my chunk is 1000 characters and only one sentence is relevant."*

Run each retrieved chunk through a filter that extracts only the query-relevant sentences (or
drops the chunk entirely). Shrinks the prompt, sharpens the signal, reduces lost-in-the-middle.

Two flavours: `LLMChainExtractor` (an LLM extracts relevant text — accurate, costs a call per
document) and `EmbeddingsFilter` (drops chunks below a similarity threshold — nearly free).

### 3.7 Self-query — natural language to metadata filters

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

This is how you handle numeric and categorical constraints, which embeddings fundamentally
cannot do (Day 10's failure modes).

### 3.8 Corrective RAG — grade and retry

```
   retrieve → grade each doc: relevant / ambiguous / irrelevant
        │
        ├─ enough relevant?  → generate
        ├─ some ambiguous?   → rewrite the query, retrieve again
        └─ all irrelevant?   → fall back (web search, or refuse)
```

**A bounded loop.** Cap the iterations or a confused grader will spin forever — the same
`maxSteps` lesson from Day 02's ReAct loop.

### 3.9 Self-RAG — grade the *answer*

```
   generate → is it grounded in the docs?   no → regenerate
            → does it answer the question?  no → re-retrieve with a better query
```

Two graders, two different loops. Yesterday's citation verification was a lightweight version of
the first one.

### 3.10 Choosing: the cost/benefit table

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

export const fast = new ChatGroq({ model: "llama-3.1-8b-instant", temperature: 0 });
export const smart = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });
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
  const { queries } = await fast.withStructuredOutput(Variations).invoke(
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
Building it by hand first means the dedupe behaviour isn't a mystery.
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
      const r = await fast.withStructuredOutput(Relevance).invoke(
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
A hosted cross-encoder is ~10× faster and cheaper than LLM reranking. Use one in production;
the LLM version is the free fallback.
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
        ...(await fast.withStructuredOutput(Grade).invoke(
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
      const { rewritten } = await fast.withStructuredOutput(Rewrite).invoke(
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

**Note the bounded loop.** Without `maxAttempts` a confused grader rewrites forever — the same
lesson as Day 02's ReAct step limit.

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
  const q = await fast.withStructuredOutput(StructuredQuery).invoke(
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
pip install langchain langchain-classic langchain-ollama langchain-groq pydantic python-dotenv
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

fast = ChatGroq(model="llama-3.1-8b-instant", temperature=0)
smart = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
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
    result = fast.with_structured_output(Variations).invoke(
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
        r = fast.with_structured_output(Relevance).invoke(
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
            g = fast.with_structured_output(Grade).invoke(
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
            r = fast.with_structured_output(Rewrite).invoke(
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
    q = fast.with_structured_output(StructuredQuery).invoke(
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

The two-stage design uses each where it's strong: the bi-encoder cheaply narrows 100k to 20; the
cross-encoder accurately narrows 20 to 4.

**Typical impact:** reranking commonly moves recall@4 by 10–20 points on a corpus where naive
retrieval is around 70%. That's a bigger gain than switching embedding models, at a fraction of
the effort — and no re-indexing.

### Why HyDE works despite generating false text

Retrieval quality depends on the *distance* between query and document embeddings. Questions and
statements occupy systematically different regions of embedding space (Day 10's asymmetry).

```
   embedding space (schematically)

        [questions live here]
              ↑
              │  ← a real gap
              ↓
        [statements/documents live here]

   HyDE moves the query INTO the document region before searching.
```

The hypothetical answer's *facts* are irrelevant — only its *shape and vocabulary* matter. It
uses the right jargon, the right sentence structure, the right register.

**When HyDE hurts:** if the model's hypothetical goes off-topic (a domain it knows nothing
about), you retrieve for the wrong thing. Always measure rather than assuming.

### Why MMR needs `fetchK > k`

```
   fetchK = 4, k = 4   →   MMR selects 4 from 4. Nothing to diversify. No-op.
   fetchK = 20, k = 4  →   MMR selects the 4 most diverse-and-relevant from 20. ✅
```

A common bug: setting them equal and concluding "MMR does nothing".

### Why the loops need bounds

Corrective and Self-RAG are loops driven by a model's judgement. Two failure modes:

1. **Infinite loop** — the grader never accepts, so you rewrite forever, burning money.
2. **Oscillation** — the rewriter alternates between two phrasings that both fail.

Mitigations: a hard `maxAttempts`; pass previously-tried queries into the rewrite prompt (as in
§4.7) so it must produce something new; and always have a terminal fallback that returns an
honest failure rather than looping.

**And note what's awkward about all of this.** You're hand-writing a state machine — a loop with
counters, accumulated state, and conditional exits — because LCEL can't express cycles. That
works at this size and becomes unmanageable when you add streaming, persistence, and a human
approval step.

That gap is precisely what LangGraph fills, and it's where Week 3 starts.

<details>
<summary>📜 A note on RAG pattern names</summary>

The literature names a lot of variants and they overlap heavily. The distinctions that actually
matter:

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

In interviews, the useful move is to describe the *mechanism* rather than reciting names —
"grade retrieved documents and re-query on failure" tells the interviewer more than "we use
CRAG". The names are labels for combinations of the four intervention points in §2.
</details>

---

## 7. Common mistakes

**❌ Adding every technique at once**

You can't tell what helped, latency balloons, and cost multiplies.
✅ Add one at a time, measure recall@k, keep what earns its cost.

---

**❌ MMR with `fetchK == k`**

Nothing to diversify from; it's a no-op.
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

Grading 20 documents with a 70B model per query is enormously expensive.
✅ Small fast model for grading/reranking/rewriting; big model only for the final answer.

---

**❌ Multi-query without deduplication**

Four queries × k=5 returns 20 documents, many identical, wasting your context budget.
✅ Dedupe by content, then rerank the union.

---

**❌ Assuming HyDE always helps**

In domains the model doesn't know, the hypothetical can be misleading and retrieval gets *worse*.
✅ A/B it on your eval set.

---

**❌ Compression that discards the answer**

Aggressive thresholds or over-eager extraction can drop the one relevant sentence.
✅ Tune the threshold against recall, not against token savings.

---

**❌ Reaching for advanced RAG before fixing chunking**

No retriever recovers an answer split across a chunk boundary.
✅ Day 09 first. Fix the ingest, then optimise retrieval.

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
    result = fast.with_structured_output(Variations).invoke(
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
        r = fast.with_structured_output(Relevance).invoke(
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
   you'd use a hosted cross-encoder (Cohere/Voyage) instead: one API call, ~200ms, same benefit.
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

**That dedup step is the detail people miss.** Three child hits frequently belong to one parent;
without deduplication you'd send the same 800-character parent three times, wasting most of your
context budget on repeats.

**Where this shines:** technical documentation and legal text, where the retrievable phrase and
the answerable unit are genuinely different sizes. It resolves Day 09's chunk-size dilemma by
refusing to choose.
</details>

---

### Exercise 3 — Self-RAG with answer grading ●●●●○

Build a Self-RAG loop that grades the generated answer on two axes — **grounded** (supported by
the retrieved documents) and **relevant** (actually answers the question) — and takes a different
action for each failure: regenerate if ungrounded, re-retrieve if irrelevant. Bound the loop and
log every decision.

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
        g = fast.with_structured_output(Groundedness).invoke(
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

            g2 = fast.with_structured_output(Groundedness).invoke(
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
        u = fast.with_structured_output(Usefulness).invoke(
            f"Question: {question}\n\nAnswer: {answer}\n\nDoes this answer the question?")

        if u.answers_question:
            log.append("  ✅ answers the question → done")
            return {"answer": answer, "docs": docs, "log": log, "status": "ok"}

        log.append(f"  ❌ doesn't answer: {u.reasoning}")

        # ── not useful → RE-RETRIEVE with a new query ────────────────────
        if loop < max_loops:
            r = fast.with_structured_output(Rewrite).invoke(
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
const g = await fast.withStructuredOutput(Groundedness).invoke(
  `Documents:\n${context}\n\nAnswer:\n${answer}\n\nIs every claim supported?`);

if (!g.grounded) {
  // regenerate with the SAME docs, stricter prompt
  answer = await strictChain.invoke({ context, question });
}

// grade 2: useful?
const u = await fast.withStructuredOutput(Usefulness).invoke(
  `Question: ${question}\n\nAnswer: ${answer}\n\nDoes this answer the question?`);

if (!u.answersQuestion && loop < maxLoops) {
  query = (await fast.withStructuredOutput(Rewrite).invoke(/* ... */)).rewritten;
  continue;                                    // ← re-RETRIEVE, don't just regenerate
}
```

**The design insight this exercise teaches:** the two grades imply **different actions**.

| Failure | Diagnosis | Action |
|---|---|---|
| Ungrounded | The model invented something; the docs may be fine | **Regenerate** with the same docs and a stricter prompt |
| Not useful | The docs genuinely don't contain the answer | **Re-retrieve** with a different query |

Conflating them is the common mistake — re-retrieving because of a hallucination wastes a
retrieval when the documents were already correct, and regenerating on irrelevant documents just
produces a different wrong answer from the same bad context.

**The cost is real:** up to 3 loops × (retrieve + generate + 2 grades) ≈ 12 LLM calls worst case.
Mitigations: cheap model for the graders (done here), only enable Self-RAG for high-stakes
queries, and cache aggressively.

**And notice how awkward this code is.** You're hand-managing loop counters, accumulated state, a
log, and multiple exit conditions — with `continue` statements controlling flow. Adding streaming
or a human approval step would make it considerably worse.

This is a **state machine written as a while loop**. LangGraph's entire proposition is letting
you declare it as nodes and conditional edges instead, with state, persistence and interrupts
handled for you. Week 3 rebuilds exactly this pattern as a graph, and the comparison is
illuminating.
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

router = fast.with_structured_output(Route).with_config(run_name="route_question")

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
        v = fast.with_structured_output(Variations).invoke(
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
        f = fast.with_structured_output(Filters).invoke(
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
    const { queries } = await fast.withStructuredOutput(Variations).invoke(/* ... */);
    const sets = await Promise.all(queries.map((q) => store.asRetriever({ k: 2 }).invoke(q)));
    docs = dedupe(sets.flat());
    break;
  }

  case "filtered": {
    const f = await fast.withStructuredOutput(Filters).invoke(/* ... */);
    docs = await store.similaritySearch(f.semanticQuery, 3, buildFilter(f));
    break;
  }
}
```

**Typical output:**

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

1. **Skipping retrieval is a real optimisation, not a micro-optimisation.** In a production
   assistant a meaningful fraction of turns are greetings, acknowledgements ("thanks!"), or
   general questions. Retrieving for those wastes an embedding call, adds latency, and — worse —
   can pull in irrelevant documents that *degrade* the answer, because the model tries to use
   what you gave it.

2. **The `multi` path handles comparisons, which naive RAG genuinely can't.** "Compare refunds
   with cancellation" embedded as one query lands between the two topics and often retrieves
   neither well. Decomposing into sub-queries retrieves both cleanly.

3. **The router itself must be cheap and must fail safe.** It runs on every request. Use the
   small model, and give it a fallback value — if classification fails, default to `simple`
   rather than erroring. A router that takes down the whole system when it misbehaves is worse
   than no router.

**The honest caveat:** the router adds one call to *every* request, including the simple ones.
It pays for itself when a decent share of traffic skips retrieval or genuinely needs the multi
path. Measure your actual distribution before assuming it's worth it — on a corpus where every
question is a simple lookup, a router is pure overhead.
</details>

---

### Exercise 5 — 🏆 Production RAG pipeline ●●●●●

Combine the techniques that earn their cost into one configurable pipeline: hybrid retrieval →
optional query transform → wide retrieval → rerank → compress → generate with verified citations
→ optional corrective retry. Make every stage toggleable, report per-stage timing, and
demonstrate the difference between a minimal and a full configuration.

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
        v = fast.with_structured_output(Variations).invoke(
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
        r = fast.with_structured_output(Relevance).invoke(
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
        result = (answer_prompt | smart.with_structured_output(Answer)).invoke(
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
  const result = await answerPrompt.pipe(smart.withStructuredOutput(Answer))
    .invoke({ context: formatDocs(docs), question });
  return { result, docs, timings };
}
```

**Typical comparison:**

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
   the LLM reranker with a hosted cross-encoder (Cohere, Voyage, Jina): one API call, ~200ms,
   same quality gain. This is the single most impactful production swap on this page.

2. **"Recommended" is the right default.** Hybrid + rerank captures most of the quality gain of
   "maximal" at 85% of the latency. Multi-query and compression add real cost for a smaller
   marginal benefit on most corpora — enable them where measurement justifies it.

3. **Citation verification catches the difference.** Minimal gets 1/2 verified; the reranked
   configurations get 3/3, because better documents make grounded answers easier. Verification
   rate is a useful *proxy* for retrieval quality that you can measure in production without
   labelled data.

4. **`compress()` never returns nothing.** `return list(kept) or docs` — an over-aggressive
   threshold that filters away every document would otherwise produce an empty context and a
   guaranteed "I don't know". Guard rails on optimisation stages matter.

5. **Corrective retry mutates the config for the next attempt** — it upgrades to multi-query
   rather than repeating the identical failed search. Retrying the same query is pointless.

**What this design still can't do, and where Week 3 picks up:**

The corrective loop is a `for` loop with a `continue`. Adding a third strategy, or streaming
progress to a UI, or pausing for human approval before an expensive path, means more flags and
more branches in an increasingly tangled function.

You've now hand-built a state machine three times today — corrective RAG, self-RAG, and this
pipeline. Each time the awkwardness is the same: **LCEL composes forward, but these problems
loop.** LangGraph makes the states and transitions explicit, and hands you persistence,
streaming and interrupts for free.

That's Day 17 onward.
</details>

---

## 9. Interview questions

### Basic

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

### Intermediate

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

### Advanced

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

## 10. Recap

- ✅ Four intervention points: transform the **query**, change **retrieval**, post-process
  **results**, add a **feedback loop**
- ✅ **Hybrid search + reranking** are the two highest-ROI additions — do these first
- ✅ Retrieve **wide** (20), rerank **narrow** (4) — bi-encoder for scale, cross-encoder for accuracy
- ✅ MMR fixes redundancy — needs `fetchK` ≫ `k`, and recall is the wrong metric for it
- ✅ Multi-query fixes vocabulary mismatch; HyDE fixes query/document shape mismatch
- ✅ Parent-document: index small children, return large parents — **dedupe the parents**
- ✅ Self-query converts natural language into metadata filters embeddings can't express
- ✅ Corrective RAG grades **documents** → re-retrieve; Self-RAG grades the **answer** → regenerate
- ✅ **Bound every loop**, use cheap models for graders, and always have a terminal fallback
- ✅ Fix chunking before optimising retrieval — no retriever recovers a split answer

### Tomorrow

**[Day 14 — Memory](day-14-memory.md)**: the last piece of Week 2. Buffer, window, summary, token
and entity memory; what "memory" actually means when the model is stateless; how it really works
in modern LangChain (`trimMessages`, history classes, and the shift to LangGraph checkpointers);
and the Week 2 project bringing retrieval and memory together.

### Quick self-check

1. You retrieve 4 documents and rerank to 4. Why is this pointless?
2. Your Self-RAG grader says the answer is ungrounded. Should you re-retrieve or regenerate?
3. Which two techniques would you add first to a naive RAG pipeline, and why?

<details>
<summary>Answers</summary>

1. Reranking is about **selection**, not ordering. Reranking 4 down to 4 just reorders the same
   documents — the relevant one is either already there or it isn't. The value comes from
   retrieving 20–30 candidates cheaply and letting the cross-encoder pick the best few.
2. **Regenerate.** Ungrounded means the model invented a claim; the retrieved documents may be
   perfectly good. Regenerate with the same documents and a stricter prompt. Re-retrieve when the
   *usefulness* grader fires — that's the signal the documents genuinely lack the answer.
3. **Hybrid search and reranking.** Hybrid is nearly free and fixes the class of failure
   embeddings cannot handle (exact identifiers, error codes, names). Reranking is the largest
   single quality gain available and needs no re-indexing. Neither requires a loop, so both are
   simple to add and easy to measure.
</details>
