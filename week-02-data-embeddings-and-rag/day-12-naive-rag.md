# Day 12 — Naive RAG End-to-End (and Six Ways to Break It)

> ⏱ **Time:** ~3 hours · 🎯 **Prereqs:** [Day 11](day-11-vector-databases.md) · 🧩 **Difficulty:** ●●●○○

**Today you learn:** Sending a model every page of your documents to answer one question is slow
and expensive. Today you build **RAG** from the pieces you already have. It loads a file, splits
it, embeds and stores it, retrieves the few chunks that matter, and answers **with citations**.
Then you break it six ways on purpose and diagnose each failure, because knowing how it fails is
what separates a demo from a real system.

This is the most important day of Week 2.

> 📖 **Words you'll meet today**
>
> - **RAG (Retrieval-Augmented Generation)** — find the document pieces that match a question,
>   then let the model answer from those pieces.
> - **Naive RAG** — the simplest version: retrieve once, then answer. It is what you build today.
> - **Corpus** — the whole collection of documents your system can search.
> - **Chunk** — a small piece of a document, sized so it can be searched and fit in a prompt.
> - **Vector store** — a database of embeddings (lists of numbers that capture meaning) that finds
>   the ones closest to a question.
> - **k (top-k)** — how many of the best-matching chunks you retrieve for each question.
> - **Grounding** — telling the model to answer only from the retrieved text, not from memory.
> - **Citation** — a marker such as [1] that links a claim in the answer to the chunk it came from.

---

## 1. The problem

Day 08 ended with a working document Q&A that answered one question about a tea party by making
**200 LLM calls** across every chunk in a novel. That approach was *map-reduce*: ask the model
about every chunk, then combine the partial answers in one final call.

The answer lived in three chunks. You paid for 200. The time and token figures below are
illustrative estimates, not a measured run — the ratio between them is the point:

```
   DAY 08: map-reduce over everything          TODAY: retrieve, then answer
   ────────────────────────────────────        ───────────────────────────
   200 chunks → 200 LLM calls                  200 chunks → 1 embedding call
             → 1 reduce call                             → 1 LLM call
   ~40 seconds                                 ~1.5 seconds
   ~180,000 tokens                             ~2,000 tokens
   answer often diluted                        answer grounded + cited
```

Same corpus. Same question. **Roughly 90 times fewer tokens in this illustration
(180,000 ÷ 2,000) — and better.**

That's RAG: don't send the model everything. Send it the *right* things.

### The real-life version

You ask a librarian when the library closes on bank holidays. A bad librarian reads every book
in the building, then answers. A good librarian walks to one shelf, pulls out the opening-hours
leaflet, reads you the line, and points at it: "It says so here."

Finding the leaflet is **retrieval**. Reading you the line is **generation**. Pointing at the
page is the **citation**. And if no leaflet mentions bank holidays, a good librarian says "I
can't find that" instead of guessing. Today you build the good librarian.

---

## 2. Mental model

### The two halves

```
   ══════════ INGEST (offline, once per document version) ══════════

   PDF/MD/HTML
       │  load          → Document[] (one per page)
       ▼
   Documents
       │  split         → chunks + metadata + header breadcrumbs
       ▼
   chunks
       │  embed         → vectors (batched, cached)
       ▼
   vector store  ← persisted, incrementally updatable


   ══════════ QUERY (online, every request) ══════════

   "how long for a refund?"
       │  embed query
       ▼
   query vector
       │  similarity search (+ metadata filter)
       ▼
   top-k chunks
       │  format with [1] [2] markers
       ▼
   prompt: instructions + context + question
       │  LLM
       ▼
   answer + citations
```

*Ingest* is the preparation half: reading, splitting, embedding and storing your documents.
*Query* is the answering half. *Similarity search* finds the stored vectors closest to the
question's vector, and the *top-k chunks* are the k closest ones.

**The single most important property:** the two halves have completely different costs. Ingest
is expensive and happens rarely. Query is cheap and happens constantly. Keeping them separate is
most of what makes RAG practical.

### The grounding contract

```
   ┌─────────────────────────────────────────────────────────┐
   │  SYSTEM PROMPT — the four rules that make RAG work      │
   ├─────────────────────────────────────────────────────────┤
   │  1. Answer ONLY from the context below                  │
   │  2. Cite every claim as [1], [2]                        │
   │  3. If the context doesn't contain the answer,          │
   │     say so — do NOT use your own knowledge              │
   │  4. Never invent a citation number                      │
   └─────────────────────────────────────────────────────────┘
```

Rule 3 is the one people leave out. It turns a confident hallucination (a fluent answer that is
simply untrue) into an honest "I don't know". On Day 01 you gave the model permission to fail.
This is where that permission proves its worth.

### Where RAG breaks

```
   retrieval failed          →  the right chunk was never fetched
   chunking failed           →  the answer is split across a boundary
   grounding failed          →  model used its own knowledge instead
   citation failed           →  claims don't match the sources
   context overflow          →  chunks pushed the question out
   staleness                 →  the store still has the old version
```

Six categories. Six different fixes. Today you'll cause and diagnose each one.

---

## 3. First principles

### 3.1 The complete pipeline

> 💬 **In plain words:** RAG is six steps in a row. Learn these six, and every later improvement
> fits into one of them.

Every RAG system follows these six steps. Everything in Day 13 improves one of them.

| Step | Day | Key decision |
|---|---|---|
| 1. Load | 09 | Preserve page/section metadata |
| 2. Split | 09 | Chunk size + overlap + header injection |
| 3. Embed | 10 | Model choice, batching, caching |
| 4. Store | 11 | Persistence, filtering, hybrid |
| 5. Retrieve | 11 | `k`, filters, hybrid fusion |
| 6. Generate | 08 | Stuff the chunks, ground the prompt, cite |

*Header injection* means adding the section's heading path — a *breadcrumb* such as
"Acme Support Handbook > Refund Policy" — to the start of each chunk's text.

### 3.2 Formatting context so citations work

> 💬 **In plain words:** Give every chunk a number before the model sees it. Then the model can
> point to its sources, and you can check them.

The model can only cite what you let it see:

```js
// ❌ no way to cite anything
docs.map(d => d.pageContent).join("\n\n")

// ✅ numbered, separated, with source metadata
docs.map((d, i) =>
  `[${i + 1}] (${d.metadata.source}, page ${d.metadata.page})\n${d.pageContent}`
).join("\n\n---\n\n")
```

When you show the answer, map `[1]` back to `docs[0]`. That round trip lets a reader check each
citation, so the citations are evidence rather than decoration.

> ⚠️ **The model may not copy your marker style.** In our run of §4.1 with `openai/gpt-oss-120b`
> (October 2026), 2 of the 4 answers wrote `【1】` (wide brackets) instead of `[1]`, in both JS
> and Python. A regex that looks only for `[1]` would miss them. Accept both forms, or use
> structured citations (§4.3), which return the source number as a plain integer.

### 3.3 Choosing `k`

> 💬 **In plain words:** `k` is how many chunks you fetch. Too few can miss the answer. Too many
> hide it and cost more.

```
   k too small (1-2)              k too large (20+)
   ──────────────────             ─────────────────
   ❌ answer may be missing        ❌ lost in the middle (Day 01)
   ✅ cheap, focused               ❌ expensive prompts
                                  ❌ irrelevant chunks dilute the answer

   Sweet spot: 3-6 for most Q&A
   With reranking (Day 13): retrieve 20, rerank down to 4
```

"Lost in the middle" means the model pays less attention to text in the middle of a long prompt.
*Reranking* means a second, more accurate model re-scores the retrieved chunks and keeps the best.

Chunk size and `k` work together. With `k=4` and 1000-character chunks, you send about 4000
characters of context. Your real budget is `k × chunkSize`, and that total has to fit.

### 3.4 The modern helper: `createRetrievalChain`

> 💬 **In plain words:** LangChain has a ready-made function that retrieves and answers in one
> call. It expects the question under the name `input`.

LangChain provides a helper that connects retrieval and *stuffing* (putting all the retrieved
chunks into one prompt):

```js
const combineDocsChain = await createStuffDocumentsChain({ llm, prompt });
const chain = await createRetrievalChain({ retriever, combineDocsChain });

await chain.invoke({ input: "how long for a refund?" });
// → { input, context: Document[], answer: string }
```

Note the variable names: **`input`** holds the question and **`context`** holds the documents.
The result also includes the retrieved documents, so you can show citations.

We'll build it by hand first with LCEL (LangChain Expression Language, from Day 07), so nothing
is hidden. Then we'll show the helper.

### 3.5 Handling "the answer isn't here"

> 💬 **In plain words:** Tell the model the exact words to say when the documents don't contain
> the answer. Then test that it really says them.

This is the most valuable behaviour in a RAG system, and the easiest to leave out:

```
System: If the context does not contain the answer, reply exactly:
        "I don't have that information in the provided documents."
        Do not use knowledge from outside the context.
```

Test this on purpose: ask something your corpus definitely doesn't cover. Sometimes retrieval
fails and the system still answers confidently from *parametric knowledge* — facts the model
memorised during training. That is worse than returning nothing, because the output looks the
same as a real answer.

### 3.6 Evaluating RAG: measure the two halves separately

> 💬 **In plain words:** Check "did it find the right text?" and "did it answer well?" separately.
> If the right text is never found, no prompt can fix the answer.

This is the single most important working habit in RAG.

```
   RETRIEVAL QUALITY                  GENERATION QUALITY
   ────────────────                   ──────────────────
   recall@k    was the right          faithfulness   is the answer supported
               chunk fetched?                        by the retrieved chunks?
   precision@k how much of what       relevance      does it answer the
               we fetched was useful?                question asked?
                                      citation acc.  do the [n] markers
                                                     point at the right chunks?
```

In plain terms: *recall@k* asks whether the right chunk was among the k you fetched.
*Precision@k* asks how many of those k chunks were useful. *Faithfulness* asks whether every
claim in the answer is supported by the retrieved text.

**If retrieval recall is 60%, no prompt engineering will get you above 60% correct answers.**
Mixing up the two halves is why RAG debugging goes round in circles, making no progress. You
tune the prompt for a week while the real problem is chunking.

---

## 4. Code — JavaScript

```bash
npm install langchain @langchain/core @langchain/classic @langchain/textsplitters \
            @langchain/ollama @langchain/groq zod dotenv
```

### 4.1 The complete pipeline, by hand

```js
// day12-rag.js
import "dotenv/config";
import fs from "node:fs/promises";
import { ChatGroq } from "@langchain/groq";
import { OllamaEmbeddings } from "@langchain/ollama";
import { MemoryVectorStore } from "@langchain/classic/vectorstores/memory";
import { Document } from "@langchain/core/documents";
import { RecursiveCharacterTextSplitter } from "@langchain/textsplitters";
import { ChatPromptTemplate } from "@langchain/core/prompts";
import { StringOutputParser } from "@langchain/core/output_parsers";
import { RunnablePassthrough, RunnableLambda } from "@langchain/core/runnables";

const model = new ChatGroq({ model: "openai/gpt-oss-120b", temperature: 0 });
const embeddings = new OllamaEmbeddings({ model: "nomic-embed-text" });

// ══════════════ 1-2. LOAD & SPLIT (Day 09) ═══════════════════════════════
const HANDBOOK = `# Acme Support Handbook

## Refund Policy

Customers may request a refund within 30 days of purchase for Basic plans, and within 60 days for Pro plans. Refunds are processed within 5 business days of approval by the billing team. Enterprise refunds are handled case by case by your account manager.

## Shipping

Domestic orders ship within 2 business days of dispatch confirmation. International orders take 10 to 14 days and may incur customs fees, which are the responsibility of the recipient.

## Account Management

Users can change their plan at any time from the billing settings page. Downgrades take effect at the end of the current billing cycle. Upgrades are prorated immediately and charged to the card on file.

## Support Hours

Support is available from 9am to 6pm GMT, Monday through Friday. Enterprise customers have access to a 24/7 emergency line staffed by senior engineers.

## Data Retention

Deleted projects are retained in cold storage for 90 days before permanent deletion. Account data is removed within 30 days of account closure, except where we are legally required to retain it.

## API Rate Limits

The API allows 1000 requests per minute for Pro accounts and 100 requests per minute for Basic accounts. Exceeding the limit returns HTTP 429 with a Retry-After header indicating when to retry.`;

// Split by markdown headers, injecting the breadcrumb (Day 09's biggest win)
function splitWithHeaders(md, splitter) {
  const sections = [];
  let stack = [], buffer = [];

  const flush = () => {
    const content = buffer.join("\n").trim();
    if (content) sections.push({ headers: [...stack], content });
    buffer = [];
  };

  for (const line of md.split("\n")) {
    const m = line.match(/^(#{1,6})\s+(.*)$/);
    if (m) {
      flush();
      stack = stack.slice(0, m[1].length - 1);
      stack[m[1].length - 1] = m[2].trim();
      stack = stack.filter(Boolean);
    } else buffer.push(line);
  }
  flush();
  return sections;
}

const splitter = new RecursiveCharacterTextSplitter({ chunkSize: 500, chunkOverlap: 80 });

const chunks = [];
for (const { headers, content } of splitWithHeaders(HANDBOOK, splitter)) {
  const breadcrumb = headers.join(" > ");
  for (const piece of await splitter.splitText(content)) {
    chunks.push(new Document({
      pageContent: `${breadcrumb}\n\n${piece}`,     // ⭐ header injection
      metadata: { breadcrumb, section: headers.at(-1), source: "handbook.md",
                  chunkIndex: chunks.length },
    }));
  }
}

console.log(`📄 ${HANDBOOK.length} chars → ${chunks.length} chunks\n`);

// ══════════════ 3-4. EMBED & STORE (Days 10-11) ══════════════════════════
const store = await MemoryVectorStore.fromDocuments(chunks, embeddings);

// ══════════════ 5. RETRIEVE ══════════════════════════════════════════════
const retriever = store.asRetriever({ k: 3 });

// ══════════════ 6. GENERATE ══════════════════════════════════════════════
const formatContext = (docs) =>
  docs.map((d, i) => `[${i + 1}] (${d.metadata.breadcrumb})\n${d.pageContent}`)
      .join("\n\n---\n\n");

const prompt = ChatPromptTemplate.fromMessages([
  ["system",
   "You answer questions using ONLY the context provided below.\n\n" +
   "Rules:\n" +
   "1. Use only information in the context. Never use outside knowledge.\n" +
   "2. Cite every claim with the source number, like [1] or [2].\n" +
   "3. If the context does not contain the answer, reply exactly: " +
   '"I don\'t have that information in the provided documents."\n' +
   "4. Never invent a citation number.\n\n" +
   "Context:\n{context}"],
  ["human", "{question}"],
]);

// ── the chain: retrieve → format → prompt → model → parse ────────────────
const ragChain = RunnablePassthrough
  .assign({ docs: (x) => retriever.invoke(x.question) })
  .assign({ context: (x) => formatContext(x.docs) })
  .assign({
    answer: ChatPromptTemplate.fromMessages([
      ["system", prompt.promptMessages[0].prompt.template],
      ["human", "{question}"],
    ]).pipe(model).pipe(new StringOutputParser()),
  });

// ── run ──────────────────────────────────────────────────────────────────
const QUESTIONS = [
  "How long do I have to request a refund on the Pro plan?",
  "What happens if I exceed the API rate limit?",
  "How long before deleted projects are gone permanently?",
  "What is the CEO's home address?",           // ← not in the corpus
];

for (const question of QUESTIONS) {
  const t0 = Date.now();
  const result = await ragChain.invoke({ question });

  console.log(`\n${"═".repeat(76)}`);
  console.log(`❓ ${question}`);
  console.log("═".repeat(76));
  console.log(`\n${result.answer}\n`);
  console.log("📚 sources:");
  result.docs.forEach((d, i) =>
    console.log(`   [${i + 1}] ${d.metadata.breadcrumb}`));
  console.log(`\n⏱  ${Date.now() - t0}ms`);
}
```

### 4.2 A cleaner LCEL version

The version above passes `question` through each step by hand. Here is the more usual way to
write it:

```js
// day12-rag-clean.js
import { RunnablePassthrough, RunnableParallel } from "@langchain/core/runnables";

const formatContext = (docs) =>
  docs.map((d, i) => `[${i + 1}] (${d.metadata.breadcrumb})\n${d.pageContent}`)
      .join("\n\n---\n\n");

// Input is a plain STRING question — the classic RAG chain shape.
const ragChain = RunnableParallel.from({
  docs: retriever,                             // string → Document[]
  question: new RunnablePassthrough(),         // string → string
})
  .assign({ context: (x) => formatContext(x.docs) })
  .assign({ answer: prompt.pipe(model).pipe(new StringOutputParser()) });

const result = await ragChain.invoke("How long for a refund on Pro?");
console.log(result.answer);
console.log(result.docs.map((d) => d.metadata.breadcrumb));
```

That `RunnableParallel` with a `RunnablePassthrough` is the standard RAG pattern from Day 07. It
retrieves the documents *and* keeps the question. Then `assign` adds the context and the answer.

### 4.3 Structured output with verified citations

The model can invent free-text `[1]` markers. Force a fixed structure instead:

```js
// day12-structured-citations.js
import "dotenv/config";
import * as z from "zod";

const CitedAnswer = z.object({
  answer: z.string().describe("The answer, without citation markers"),
  citations: z.array(z.object({
    sourceNumber: z.number().int().describe("The [n] number of the source used"),
    quote: z.string().describe("The exact sentence from that source supporting the claim"),
  })).describe("One entry per source actually used. Empty if the answer isn't in the context."),
  answerFound: z.boolean().describe("False if the context doesn't contain the answer"),
});

const citedChain = RunnableParallel.from({
  docs: retriever,
  question: new RunnablePassthrough(),
})
  .assign({ context: (x) => formatContext(x.docs) })
  .assign({
    result: prompt.pipe(model.withStructuredOutput(CitedAnswer, { method: "jsonSchema" })),
  });

for (const q of ["How long for a Pro refund?", "What is the CEO's salary?"]) {
  const { docs, result } = await citedChain.invoke(q);

  console.log(`\n❓ ${q}`);

  if (!result.answerFound) {
    console.log("   ⚠️  not in the documents");
    continue;
  }

  console.log(`   ${result.answer}\n`);

  for (const c of result.citations) {
    const doc = docs[c.sourceNumber - 1];

    // ⭐ VERIFY the citation actually exists in that document
    const verified = doc && doc.pageContent.toLowerCase()
      .includes(c.quote.toLowerCase().slice(0, 40));

    console.log(`   ${verified ? "✅" : "❌ UNVERIFIED"} [${c.sourceNumber}] ` +
                `${doc?.metadata.breadcrumb ?? "INVALID SOURCE"}`);
    console.log(`      "${c.quote.slice(0, 70)}…"`);
  }
}
```

**That verification step is the point.** The model can invent a quote or a source number.
Checking the quote against the actual chunk catches it. An unverified citation is a signal to
flag the answer, not to show it confidently.

> ⚠️ **Why `method: "jsonSchema"`?** This chain reuses the §4.1 prompt, which says *reply
> exactly: "I don't have that information…"*. With the default method (function calling),
> `openai/gpt-oss-120b` sometimes obeyed that line and replied in plain text instead of calling
> the tool. Groq then rejected the call: `400 Tool choice is required, but model did not call a
> tool` (`tool_use_failed`). It happened for the CEO question in our run. With `jsonSchema`, the
> reply must match the schema. The same question then came back as `answerFound: false`. The
> real fix is to make the prompt and the schema agree: a structured prompt should say "set
> `answerFound` to false", not "reply exactly". Python spells it `method="json_schema",
> strict=True`. The methods are compared in
> [Day 06](../week-01-foundations/day-06-output-parsers-structured-output.md).

### 4.4 The built-in helper

```js
// day12-builtin.js
import { createStuffDocumentsChain } from "@langchain/classic/chains/combine_documents";
import { createRetrievalChain } from "@langchain/classic/chains/retrieval";
import { ChatPromptTemplate } from "@langchain/core/prompts";

const prompt = ChatPromptTemplate.fromMessages([
  ["system",
   "Answer using ONLY this context. Cite sources as [1], [2]. " +
   "If the answer isn't present, say you don't have that information.\n\n{context}"],
  ["human", "{input}"],
]);

const combineDocsChain = await createStuffDocumentsChain({ llm: model, prompt });
const chain = await createRetrievalChain({ retriever, combineDocsChain });

const result = await chain.invoke({ input: "How long for a Pro refund?" });

console.log(result.answer);
console.log("\nretrieved:", result.context.map((d) => d.metadata.breadcrumb));
```

Note the required variable names: **`input`** and **`context`**. The result has `input`,
`context` (the Documents) and `answer`.

### 4.5 Streaming the answer while keeping sources

```js
// day12-streaming.js
const question = "What are the refund windows for each plan?";

// Retrieve first so sources can be shown immediately.
const docs = await retriever.invoke(question);

console.log("📚 searching…");
docs.forEach((d, i) => console.log(`   [${i + 1}] ${d.metadata.breadcrumb}`));
console.log("\n💬 ");

const answerChain = prompt.pipe(model).pipe(new StringOutputParser());

for await (const chunk of await answerChain.stream({
  context: formatContext(docs), question,
})) {
  process.stdout.write(chunk);
}
console.log();
```

*Streaming* means printing the answer piece by piece as the model writes it.

**Show sources before the answer streams.** Retrieval typically takes tens of milliseconds; the
answer takes a second or more (typical figures — time your own pipeline). Showing sources first makes the whole thing feel instant. It also lets the user start
checking them while the answer is still being written.

---

## 5. Code — Python

```bash
pip install langchain langchain-classic langchain-text-splitters langchain-ollama \
            langchain-groq pydantic python-dotenv
```

### 5.1 The complete pipeline, by hand

```python
# day12_rag.py
import time
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_ollama import OllamaEmbeddings
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableParallel
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

load_dotenv()
model = ChatGroq(model="openai/gpt-oss-120b", temperature=0)
embeddings = OllamaEmbeddings(model="nomic-embed-text")

# ══════════════ 1-2. LOAD & SPLIT (Day 09) ═══════════════════════════════
HANDBOOK = """# Acme Support Handbook

## Refund Policy

Customers may request a refund within 30 days of purchase for Basic plans, and within 60 days for Pro plans. Refunds are processed within 5 business days of approval by the billing team. Enterprise refunds are handled case by case by your account manager.

## Shipping

Domestic orders ship within 2 business days of dispatch confirmation. International orders take 10 to 14 days and may incur customs fees, which are the responsibility of the recipient.

## Account Management

Users can change their plan at any time from the billing settings page. Downgrades take effect at the end of the current billing cycle. Upgrades are prorated immediately and charged to the card on file.

## Support Hours

Support is available from 9am to 6pm GMT, Monday through Friday. Enterprise customers have access to a 24/7 emergency line staffed by senior engineers.

## Data Retention

Deleted projects are retained in cold storage for 90 days before permanent deletion. Account data is removed within 30 days of account closure, except where we are legally required to retain it.

## API Rate Limits

The API allows 1000 requests per minute for Pro accounts and 100 requests per minute for Basic accounts. Exceeding the limit returns HTTP 429 with a Retry-After header indicating when to retry."""

header_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=[("#", "h1"), ("##", "h2")], strip_headers=True)
splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=80)

chunks = []
for section in splitter.split_documents(header_splitter.split_text(HANDBOOK)):
    breadcrumb = " > ".join(section.metadata[k] for k in ("h1", "h2")
                            if k in section.metadata)
    chunks.append(Document(
        page_content=f"{breadcrumb}\n\n{section.page_content}",     # ⭐ header injection
        metadata={"breadcrumb": breadcrumb,
                  "section": section.metadata.get("h2", ""),
                  "source": "handbook.md",
                  "chunk_index": len(chunks)},
    ))

print(f"📄 {len(HANDBOOK)} chars → {len(chunks)} chunks\n")

# ══════════════ 3-4. EMBED & STORE (Days 10-11) ══════════════════════════
store = InMemoryVectorStore.from_documents(chunks, embeddings)

# ══════════════ 5. RETRIEVE ══════════════════════════════════════════════
retriever = store.as_retriever(search_kwargs={"k": 3})

# ══════════════ 6. GENERATE ══════════════════════════════════════════════
def format_context(docs):
    return "\n\n---\n\n".join(
        f"[{i}] ({d.metadata['breadcrumb']})\n{d.page_content}"
        for i, d in enumerate(docs, 1)
    )

prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You answer questions using ONLY the context provided below.\n\n"
     "Rules:\n"
     "1. Use only information in the context. Never use outside knowledge.\n"
     "2. Cite every claim with the source number, like [1] or [2].\n"
     "3. If the context does not contain the answer, reply exactly: "
     '"I don\'t have that information in the provided documents."\n'
     "4. Never invent a citation number.\n\n"
     "Context:\n{context}"),
    ("human", "{question}"),
])

# ── the chain: retrieve → format → prompt → model → parse ────────────────
rag_chain = (
    RunnableParallel(docs=retriever, question=RunnablePassthrough())
    .assign(context=lambda x: format_context(x["docs"]))
    .assign(answer=prompt | model | StrOutputParser())
)

# ── run ──────────────────────────────────────────────────────────────────
QUESTIONS = [
    "How long do I have to request a refund on the Pro plan?",
    "What happens if I exceed the API rate limit?",
    "How long before deleted projects are gone permanently?",
    "What is the CEO's home address?",           # ← not in the corpus
]

for question in QUESTIONS:
    t0 = time.time()
    result = rag_chain.invoke(question)

    print(f"\n{'═' * 76}")
    print(f"❓ {question}")
    print("═" * 76)
    print(f"\n{result['answer']}\n")
    print("📚 sources:")
    for i, d in enumerate(result["docs"], 1):
        print(f"   [{i}] {d.metadata['breadcrumb']}")
    print(f"\n⏱  {(time.time() - t0) * 1000:.0f}ms")
```

> 🔑 Look at the chain shape. `RunnableParallel(docs=retriever, question=RunnablePassthrough())`
> is the standard RAG pattern: retrieve *and* keep the question, then add more keys with
> `.assign()`. This is Day 07's `Parallel` + `Passthrough` + `Assign` lesson, doing the job it
> was designed for.

### 5.2 Structured output with verified citations

```python
# day12_structured_citations.py
from pydantic import BaseModel, Field
from langchain_core.runnables import RunnableParallel, RunnablePassthrough

class Citation(BaseModel):
    source_number: int = Field(description="The [n] number of the source used")
    quote: str = Field(description="The exact sentence from that source supporting the claim")

class CitedAnswer(BaseModel):
    """An answer grounded in retrieved sources."""
    answer: str = Field(description="The answer, without citation markers")
    citations: list[Citation] = Field(
        description="One entry per source actually used. Empty if the answer isn't in the context.")
    answer_found: bool = Field(description="False if the context doesn't contain the answer")

cited_chain = (
    RunnableParallel(docs=retriever, question=RunnablePassthrough())
    .assign(context=lambda x: format_context(x["docs"]))
    .assign(result=prompt | model.with_structured_output(
        CitedAnswer, method="json_schema", strict=True))
)

for q in ["How long for a Pro refund?", "What is the CEO's salary?"]:
    out = cited_chain.invoke(q)
    docs, result = out["docs"], out["result"]

    print(f"\n❓ {q}")

    if not result.answer_found:
        print("   ⚠️  not in the documents")
        continue

    print(f"   {result.answer}\n")

    for c in result.citations:
        doc = docs[c.source_number - 1] if 0 < c.source_number <= len(docs) else None

        # ⭐ VERIFY the citation actually exists in that document
        verified = doc and c.quote.lower()[:40] in doc.page_content.lower()

        label = doc.metadata["breadcrumb"] if doc else "INVALID SOURCE"
        print(f"   {'✅' if verified else '❌ UNVERIFIED'} [{c.source_number}] {label}")
        print(f'      "{c.quote[:70]}…"')
```

### 5.3 The built-in helper

```python
# day12_builtin.py
from langchain_core.prompts import ChatPromptTemplate
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_classic.chains.retrieval import create_retrieval_chain

prompt = ChatPromptTemplate.from_messages([
    ("system",
     "Answer using ONLY this context. Cite sources as [1], [2]. "
     "If the answer isn't present, say you don't have that information.\n\n{context}"),
    ("human", "{input}"),
])

combine_docs_chain = create_stuff_documents_chain(model, prompt)
chain = create_retrieval_chain(retriever, combine_docs_chain)

result = chain.invoke({"input": "How long for a Pro refund?"})

print(result["answer"])
print("\nretrieved:", [d.metadata["breadcrumb"] for d in result["context"]])
```

### 5.4 Streaming the answer while keeping sources

```python
# day12_streaming.py
question = "What are the refund windows for each plan?"

# Retrieve first so sources can be shown immediately.
docs = retriever.invoke(question)

print("📚 searching…")
for i, d in enumerate(docs, 1):
    print(f"   [{i}] {d.metadata['breadcrumb']}")
print("\n💬 ", end="")

answer_chain = prompt | model | StrOutputParser()

for chunk in answer_chain.stream({"context": format_context(docs), "question": question}):
    print(chunk, end="", flush=True)
print()
```

### 🔁 JS ↔ Python differences you just saw

| | JavaScript | Python |
|---|---|---|
| Store | `MemoryVectorStore` (`@langchain/classic`) | `InMemoryVectorStore` (`langchain_core`) |
| Markdown headers | manual walk (Day 09 §4.4) | `MarkdownHeaderTextSplitter` ✅ built in |
| Retriever | `store.asRetriever({ k: 3 })` | `store.as_retriever(search_kwargs={"k": 3})` |
| Parallel + passthrough | `RunnableParallel.from({ docs: retriever, question: new RunnablePassthrough() })` | `RunnableParallel(docs=retriever, question=RunnablePassthrough())` |
| Retrieval helper | `await createRetrievalChain({ retriever, combineDocsChain })` | `create_retrieval_chain(retriever, combine_docs_chain)` |
| Helper is async? | ✅ yes | ❌ no |
| Result key | `result.context` (Documents) | `result["context"]` |

---

## 6. Under the hood

### What `createRetrievalChain` actually builds

```
createRetrievalChain({ retriever, combineDocsChain })

  ≈  RunnablePassthrough
       .assign({ context: (x) => retriever.invoke(x.input) })
       .assign({ answer: combineDocsChain })
```

That's it. It's the LCEL you wrote in §4.1, packaged. This is why you should know the manual
version. Sooner or later you need query rewriting (turning a vague question into a clear one),
reranking, hybrid retrieval or a corrective loop. At that moment the helper no longer fits, and
you go back to LCEL.

**The helper is a convenience, not a foundation.** Most production RAG pipelines outgrow it
within weeks. That is why Day 13 exists.

### Why retrieval quality caps everything downstream

```
   retrieval recall = 0.6
        │
        ▼
   40% of questions NEVER have the right chunk in context
        │
        ▼
   best possible answer accuracy = 60%
        │
        ▼
   prompt engineering can only improve the OTHER 60%
```

This is the argument for measuring the two halves separately, written as a limit. Suppose recall
is 60% and you spend a week on the prompt. Your ceiling — the best score you can possibly
reach — is still 60%.

**Diagnostic that takes two minutes:** for each failing question, check whether the correct
chunk was in the retrieved set.

- **Not retrieved** → chunking, embedding, or query problem
- **Retrieved but answered wrong** → prompt, context ordering, or model problem

Every RAG debugging session should start here.

### Context ordering and lost-in-the-middle

Day 01's finding applies directly: models pay more reliable attention to the beginning and end
of a long context than to the middle.

```
   k=10 chunks, the relevant one at position 6
        ↓
   [1][2][3][4][5][6][7][8][9][10]
                ↑
         weakest attention zone
```

There are two ways to reduce the problem. First, **retrieve fewer chunks** (k=3–5 rather than
10–20). Second, **reorder** them so the highest-scoring chunks sit at the start *and* the end,
with weaker ones in the middle. LangChain provides a `LongContextReorder` transformer for exactly
this.

The deeper fix is reranking (Day 13): retrieve 20 candidates cheaply, rerank them accurately and
keep 4. You get the recall benefit of a large `k` with the precision of a small one.

### Why "I don't know" is hard for a model

Rule 3 of the grounding contract works against how the model was trained. Its pretraining data
is the huge body of text it first learned from. In that text, a question is overwhelmingly more
often followed by a confident answer than by an admission of not knowing. This is Day 01's
hallucination mechanism.

What actually helps, in order:

1. **An exact phrase to output.** "reply exactly: I don't have that information" is far more
   reliable than "say you don't know". It turns the refusal into a concrete sequence of tokens
   the model can copy, instead of an abstract instruction.
2. **A boolean field in a structured schema** (`answerFound`). The model must choose true or
   false, and your code can branch on it instead of parsing prose.
3. **A few-shot example** showing a not-in-context question and the refusal.

Test this explicitly. It's the behaviour most likely to be silently missing.

---

## 7. Common mistakes

**❌ Re-ingesting on every startup**

```js
const store = await MemoryVectorStore.fromDocuments(chunks, embeddings);   // every boot
```
✅ Ingest is a separate script writing to a persistent store. The server only connects.

---

**❌ No "not in context" instruction**

The model falls back on parametric knowledge (what it memorised in training), and you can't tell
that retrieval failed.
✅ Give an exact refusal phrase, and test it with an out-of-corpus question.

---

**❌ Citations that are never verified**

`[3]` looks authoritative whether or not source 3 says anything of the sort.
✅ Ask for the supporting quote and check it appears in that chunk.

---

**❌ `k` too large**

k=20 buries the relevant chunk in the middle of the context and costs 5 times the tokens.
✅ k=3–6, or retrieve 20 and rerank to 4 (Day 13).

---

**❌ Measuring only end-to-end accuracy**

You can't tell whether a wrong answer is a retrieval failure or a generation failure.
✅ Measure recall@k and faithfulness separately.

---

**❌ Passing raw `Document[]` into a prompt variable**

```js
prompt.invoke({ context: docs })    // "[object Object],[object Object]"
```
✅ Format to a string first — numbered, separated, with metadata.

---

**❌ Wrong variable names with the built-in helpers**

`createRetrievalChain` requires **`input`**, and the docs chain fills **`context`**.
✅ `chain.invoke({ input: question })`.

---

**❌ Streaming the answer before showing sources**

Retrieval is fast (typically tens of milliseconds), generation slow (often seconds). Users
stare at a blank screen.
✅ Render sources immediately, then stream the answer.

---

**❌ Never testing an out-of-corpus question**

The most important behaviour in the system, and it's the one nobody tests.
✅ Put at least one "definitely not in the docs" question in your eval set (your fixed list of
test questions) permanently.

---

## 8. Exercises

### Exercise 1 — Break it six ways ●●○○○

Take the working pipeline and deliberately introduce each failure, then observe the symptom:

1. `chunkSize: 60` (answer split across chunks)
2. Remove header injection
3. `k = 1`
4. Remove the "only use the context" instruction
5. `k = 25` with the answer chunk placed mid-context
6. Ask a question that isn't in the corpus

Record the symptom for each. This builds the diagnostic instinct faster than any amount of reading.

<details>
<summary>✅ Solution</summary>

**Python** (the JavaScript version follows below)
```python
# day12_break_it.py
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_ollama import OllamaEmbeddings
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()
model = ChatGroq(model="openai/gpt-oss-120b", temperature=0)
embeddings = OllamaEmbeddings(model="nomic-embed-text")

SECTIONS = [
    ("Acme Handbook > Refund Policy",
     "Customers may request a refund within 30 days for Basic plans and within 60 days "
     "for Pro plans. Refunds are processed within 5 business days of approval."),
    ("Acme Handbook > Shipping",
     "Domestic orders ship within 2 business days. International orders take 10 to 14 days."),
    ("Acme Handbook > API Rate Limits",
     "The API allows 1000 requests per minute for Pro and 100 for Basic. "
     "Exceeding it returns HTTP 429."),
    ("Acme Handbook > Data Retention",
     "Deleted projects are retained in cold storage for 90 days before permanent deletion."),
    ("Acme Handbook > Support Hours",
     "Support is available 9am to 6pm GMT, Monday through Friday."),
]

GROUNDED = ("You answer using ONLY the context below. Cite sources as [1], [2]. "
            "If the context does not contain the answer, reply exactly: "
            '"I don\'t have that information in the provided documents."\n\nContext:\n{context}')

UNGROUNDED = "Answer the question. Here is some possibly relevant context:\n\n{context}"

def build(chunk_size=500, inject_headers=True, filler=0):
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=0)
    chunks = []
    for breadcrumb, body in SECTIONS:
        for piece in splitter.split_text(body):
            chunks.append(Document(
                page_content=f"{breadcrumb}\n\n{piece}" if inject_headers else piece,
                metadata={"breadcrumb": breadcrumb},
            ))
    # optional filler docs, to push k higher
    for i in range(filler):
        chunks.append(Document(
            page_content=f"Acme Handbook > Misc\n\nMiscellaneous note {i} about internal "
                         f"process {i % 5}, of no relevance to customer questions.",
            metadata={"breadcrumb": "Acme Handbook > Misc"}))
    return InMemoryVectorStore.from_documents(chunks, embeddings), chunks

def ask(store, question, k=3, system=GROUNDED):
    docs = store.as_retriever(search_kwargs={"k": k}).invoke(question)
    context = "\n\n---\n\n".join(
        f"[{i}] ({d.metadata['breadcrumb']})\n{d.page_content}"
        for i, d in enumerate(docs, 1))
    chain = (ChatPromptTemplate.from_messages([("system", system), ("human", "{question}")])
             | model | StrOutputParser())
    return chain.invoke({"context": context, "question": question}), docs

Q = "How long do I have to request a refund on the Pro plan?"
OUT_OF_CORPUS = "What is the CEO's home address?"

print("═" * 78)
print("BASELINE (chunk=500, headers ON, k=3, grounded)")
print("═" * 78)
store, _ = build()
answer, docs = ask(store, Q)
print(f"{answer}\n→ retrieved: {[d.metadata['breadcrumb'] for d in docs]}")

print("\n" + "═" * 78)
print("BREAK 1 — chunkSize=60 (answer split across chunks)")
print("═" * 78)
store, chunks = build(chunk_size=60)
answer, docs = ask(store, Q)
print(f"{len(chunks)} chunks. Sample: {chunks[0].page_content[-40:]!r}")
print(f"{answer}")

print("\n" + "═" * 78)
print("BREAK 2 — no header injection")
print("═" * 78)
store, _ = build(inject_headers=False)
answer, docs = ask(store, Q)
print(f"{answer}\n→ retrieved: {[d.metadata['breadcrumb'] for d in docs]}")

print("\n" + "═" * 78)
print("BREAK 3 — k=1")
print("═" * 78)
store, _ = build()
answer, docs = ask(store, Q, k=1)
print(f"{answer}\n→ retrieved: {[d.metadata['breadcrumb'] for d in docs]}")

print("\n" + "═" * 78)
print("BREAK 4 — ungrounded prompt, out-of-corpus question")
print("═" * 78)
answer, _ = ask(store, OUT_OF_CORPUS, system=UNGROUNDED)
print(f"UNGROUNDED: {answer[:180]}")
answer, _ = ask(store, OUT_OF_CORPUS, system=GROUNDED)
print(f"\nGROUNDED:   {answer[:180]}")

print("\n" + "═" * 78)
print("BREAK 5 — k=25 with 40 filler docs (lost in the middle)")
print("═" * 78)
store, _ = build(filler=40)
answer, docs = ask(store, Q, k=25)
positions = [i for i, d in enumerate(docs, 1) if "Refund" in d.metadata["breadcrumb"]]
print(f"relevant chunk at position(s): {positions} of {len(docs)}")
print(f"{answer[:200]}")

print("\n" + "═" * 78)
print("BREAK 6 — out-of-corpus with grounding (the CORRECT behaviour)")
print("═" * 78)
store, _ = build()
answer, _ = ask(store, OUT_OF_CORPUS)
print(answer)
```

**JavaScript**
```js
// day12-break-it.js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";
import { OllamaEmbeddings } from "@langchain/ollama";
import { MemoryVectorStore } from "@langchain/classic/vectorstores/memory";
import { Document } from "@langchain/core/documents";
import { ChatPromptTemplate } from "@langchain/core/prompts";
import { StringOutputParser } from "@langchain/core/output_parsers";
import { RecursiveCharacterTextSplitter } from "@langchain/textsplitters";

const model = new ChatGroq({ model: "openai/gpt-oss-120b", temperature: 0 });
const embeddings = new OllamaEmbeddings({ model: "nomic-embed-text" });

const SECTIONS = [
  ["Acme Handbook > Refund Policy",
   "Customers may request a refund within 30 days for Basic plans and within 60 days " +
   "for Pro plans. Refunds are processed within 5 business days of approval."],
  ["Acme Handbook > Shipping",
   "Domestic orders ship within 2 business days. International orders take 10 to 14 days."],
  ["Acme Handbook > API Rate Limits",
   "The API allows 1000 requests per minute for Pro and 100 for Basic. " +
   "Exceeding it returns HTTP 429."],
  ["Acme Handbook > Data Retention",
   "Deleted projects are retained in cold storage for 90 days before permanent deletion."],
  ["Acme Handbook > Support Hours",
   "Support is available 9am to 6pm GMT, Monday through Friday."],
];

const GROUNDED =
  "You answer using ONLY the context below. Cite sources as [1], [2]. " +
  "If the context does not contain the answer, reply exactly: " +
  '"I don\'t have that information in the provided documents."\n\nContext:\n{context}';

const UNGROUNDED = "Answer the question. Here is some possibly relevant context:\n\n{context}";

async function build({ chunkSize = 500, injectHeaders = true, filler = 0 } = {}) {
  const splitter = new RecursiveCharacterTextSplitter({ chunkSize, chunkOverlap: 0 });
  const chunks = [];

  for (const [breadcrumb, body] of SECTIONS) {
    for (const piece of await splitter.splitText(body)) {
      chunks.push(new Document({
        pageContent: injectHeaders ? `${breadcrumb}\n\n${piece}` : piece,
        metadata: { breadcrumb },
      }));
    }
  }

  // optional filler docs, to push k higher
  for (let i = 0; i < filler; i++) {
    chunks.push(new Document({
      pageContent: `Acme Handbook > Misc\n\nMiscellaneous note ${i} about internal ` +
                   `process ${i % 5}, of no relevance to customer questions.`,
      metadata: { breadcrumb: "Acme Handbook > Misc" },
    }));
  }

  return { store: await MemoryVectorStore.fromDocuments(chunks, embeddings), chunks };
}

async function ask(store, question, { k = 3, system = GROUNDED } = {}) {
  const docs = await store.asRetriever({ k }).invoke(question);
  const context = docs
    .map((d, i) => `[${i + 1}] (${d.metadata.breadcrumb})\n${d.pageContent}`)
    .join("\n\n---\n\n");

  const chain = ChatPromptTemplate
    .fromMessages([["system", system], ["human", "{question}"]])
    .pipe(model).pipe(new StringOutputParser());

  return { answer: await chain.invoke({ context, question }), docs };
}

const Q = "How long do I have to request a refund on the Pro plan?";
const OUT_OF_CORPUS = "What is the CEO's home address?";
const rule = (t) => console.log(`\n${"═".repeat(78)}\n${t}\n${"═".repeat(78)}`);

rule("BASELINE (chunk=500, headers ON, k=3, grounded)");
let { store } = await build();
let r = await ask(store, Q);
console.log(`${r.answer}\n→ retrieved: ${r.docs.map((d) => d.metadata.breadcrumb)}`);

rule("BREAK 1 — chunkSize=60 (answer split across chunks)");
let built = await build({ chunkSize: 60 });
r = await ask(built.store, Q);
console.log(`${built.chunks.length} chunks. Sample: ` +
            `${JSON.stringify(built.chunks[0].pageContent.slice(-40))}`);
console.log(r.answer);

rule("BREAK 2 — no header injection");
({ store } = await build({ injectHeaders: false }));
r = await ask(store, Q);
console.log(`${r.answer}\n→ retrieved: ${r.docs.map((d) => d.metadata.breadcrumb)}`);

rule("BREAK 3 — k=1");
({ store } = await build());
r = await ask(store, Q, { k: 1 });
console.log(`${r.answer}\n→ retrieved: ${r.docs.map((d) => d.metadata.breadcrumb)}`);

rule("BREAK 4 — ungrounded prompt, out-of-corpus question");
console.log("UNGROUNDED: " +
  (await ask(store, OUT_OF_CORPUS, { system: UNGROUNDED })).answer.slice(0, 180));
console.log("\nGROUNDED:   " +
  (await ask(store, OUT_OF_CORPUS)).answer.slice(0, 180));

rule("BREAK 5 — k=25 with 40 filler docs (lost in the middle)");
({ store } = await build({ filler: 40 }));
r = await ask(store, Q, { k: 25 });
const positions = r.docs
  .map((d, i) => (d.metadata.breadcrumb.includes("Refund") ? i + 1 : null))
  .filter(Boolean);
console.log(`relevant chunk at position(s): ${positions} of ${r.docs.length}`);
console.log(r.answer.slice(0, 200));

rule("BREAK 6 — out-of-corpus with grounding (the CORRECT behaviour)");
({ store } = await build());
console.log((await ask(store, OUT_OF_CORPUS)).answer);
```

**Symptoms to look for** (what each break *can* cause — whether you see it depends on your
embedder, your model and your corpus):

| Break | Symptom | Real-world cause |
|---|---|---|
| 1. chunk=60 | Answer says "30 days" or "60 days" but can't say **which plan** — the plan name and the number landed in different chunks | Chunk size below the natural unit |
| 2. no headers | Often retrieves *Shipping* instead of *Refunds* — both talk about "days" | Structure stripped at ingest |
| 3. k=1 | Answers about Basic only, missing Pro, or vice versa | Over-tight retrieval budget |
| 4. ungrounded | Answers from its own memory, or invents an answer | Missing grounding instruction |
| 5. k=25 | Relevant chunk lands mid-context; answer becomes vague or cites the wrong source | Lost in the middle |
| 6. grounded + missing | *"I don't have that information in the provided documents."* ✅ | This is correct |

**What we actually saw** (Python, `openai/gpt-oss-120b`, October 2026). Ollama was not
installed on the checking machine, so a simple keyword-based stand-in replaced
`nomic-embed-text`. On a corpus this small the strong model answered *"60 days"* correctly in
Breaks 1, 2, 3 and 5. In Break 4 it did **not** invent an address. The ungrounded prompt got
*"I'm sorry, but I can't help with that."* — a privacy refusal from the model's own training,
not from your rules. A harmless question ("What year was Acme founded?") also got a refusal
without the grounding rules.

**So think hardest about Break 4 versus Break 6.** Identical question, corpus and model. Only
one paragraph of system prompt differs. With the grounding paragraph, refusing is *your rule*,
with the exact wording you chose. Without it, you are relying on one model's habits — and a
model swap can change them silently. A strong model also hides retrieval mistakes on a tiny
corpus, which is why you check the retrieved chunks, not just the answer.

**The one that's hardest to spot in production is Break 2.** Nothing throws an error. Retrieval
returns results. The answer sounds believable. It's just about the wrong section, and you'd only
catch it by checking which chunks were retrieved.
</details>

---

### Exercise 2 — RAG evaluation harness ●●●○○

Build a harness (a small test program) that evaluates a RAG pipeline on both halves:

- **retrieval** (recall@k — was the correct chunk fetched?)
- **generation** (does the answer contain the expected fact? did it correctly refuse when it
  should?)

Report both, plus which failures are retrieval and which are generation.

<details>
<summary>✅ Solution</summary>

**Python**
```python
# day12_eval.py
import re, time
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_ollama import OllamaEmbeddings
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()
model = ChatGroq(model="openai/gpt-oss-120b", temperature=0)
embeddings = OllamaEmbeddings(model="nomic-embed-text")

SECTIONS = [
    ("Refund Policy", "Customers may request a refund within 30 days for Basic plans and "
                      "within 60 days for Pro plans. Refunds are processed within 5 business days."),
    ("Shipping", "Domestic orders ship within 2 business days. International orders take "
                 "10 to 14 days and may incur customs fees."),
    ("Account Management", "Downgrades take effect at the end of the current billing cycle. "
                           "Upgrades are prorated immediately."),
    ("Support Hours", "Support is available 9am to 6pm GMT, Monday through Friday. "
                      "Enterprise customers have a 24/7 emergency line."),
    ("Data Retention", "Deleted projects are retained in cold storage for 90 days before "
                       "permanent deletion."),
    ("API Rate Limits", "The API allows 1000 requests per minute for Pro and 100 for Basic. "
                        "Exceeding it returns HTTP 429 with a Retry-After header."),
]

# question, the section that answers it (None = should refuse), expected substring
CASES = [
    ("How long for a refund on Pro?",              "Refund Policy",      r"60"),
    ("When do international orders arrive?",       "Shipping",           r"10.{0,6}14"),
    ("What happens when I downgrade?",             "Account Management", r"end of the current billing cycle"),
    ("Is support available on Saturday?",          "Support Hours",      r"Monday|Friday|not"),
    ("How long before deleted projects are gone?", "Data Retention",     r"90"),
    ("What's the rate limit for Basic accounts?",  "API Rate Limits",    r"100"),
    ("What status code for rate limiting?",        "API Rate Limits",    r"429"),
    ("What is the CEO's home address?",            None,                 r"don't have that information"),
]

GROUNDED = ("You answer using ONLY the context below. Cite sources as [1], [2]. "
            "If the context does not contain the answer, reply exactly: "
            '"I don\'t have that information in the provided documents."\n\nContext:\n{context}')

def build_pipeline(chunk_size=400, k=3):
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=60)
    chunks = []
    for section, body in SECTIONS:
        for piece in splitter.split_text(body):
            chunks.append(Document(page_content=f"Acme Handbook > {section}\n\n{piece}",
                                   metadata={"section": section}))
    store = InMemoryVectorStore.from_documents(chunks, embeddings)
    return store.as_retriever(search_kwargs={"k": k})

def evaluate(retriever, label):
    chain = (ChatPromptTemplate.from_messages([("system", GROUNDED), ("human", "{question}")])
             | model | StrOutputParser())

    retrieval_hits = generation_hits = 0
    retrievable = 0
    failures = []
    t0 = time.time()

    for question, expected_section, expected_pattern in CASES:
        docs = retriever.invoke(question)
        sections = [d.metadata["section"] for d in docs]

        # ── retrieval metric (only meaningful when there IS a correct section)
        retrieved_ok = True
        if expected_section is not None:
            retrievable += 1
            retrieved_ok = expected_section in sections
            retrieval_hits += retrieved_ok

        # ── generation metric
        context = "\n\n---\n\n".join(
            f"[{i}] ({d.metadata['section']})\n{d.page_content}"
            for i, d in enumerate(docs, 1))
        answer = chain.invoke({"context": context, "question": question})
        answered_ok = bool(re.search(expected_pattern, answer, re.I))
        generation_hits += answered_ok

        if not answered_ok:
            # ⭐ THE KEY DIAGNOSTIC: which half failed?
            cause = "RETRIEVAL" if not retrieved_ok else "GENERATION"
            failures.append((cause, question, sections, answer[:70]))

    elapsed = time.time() - t0

    print(f"\n═══ {label} ═══")
    print(f"retrieval recall@k : {retrieval_hits}/{retrievable} "
          f"({retrieval_hits / retrievable * 100:.0f}%)")
    print(f"answer accuracy    : {generation_hits}/{len(CASES)} "
          f"({generation_hits / len(CASES) * 100:.0f}%)")
    print(f"time               : {elapsed:.1f}s")

    if failures:
        print("\nfailures:")
        for cause, q, sections, answer in failures:
            print(f"  [{cause}] {q}")
            print(f"      retrieved: {sections}")
            print(f"      answered : {answer}…")

    return retrieval_hits / retrievable, generation_hits / len(CASES)

# ── sweep configurations ─────────────────────────────────────────────────
for chunk_size, k in [(150, 3), (400, 3), (400, 1), (400, 6)]:
    evaluate(build_pipeline(chunk_size, k), f"chunk={chunk_size} k={k}")
```

**JavaScript** — same structure:
```js
// key part: the diagnostic that splits the two failure types
const docs = await retriever.invoke(question);
const sections = docs.map((d) => d.metadata.section);

const retrievedOk = expectedSection === null || sections.includes(expectedSection);
const answer = await chain.invoke({ context: format(docs), question });
const answeredOk = expectedPattern.test(answer);

if (!answeredOk) {
  failures.push({
    cause: retrievedOk ? "GENERATION" : "RETRIEVAL",   // ⭐ the whole point
    question, sections, answer: answer.slice(0, 70),
  });
}
```

**Typical output** (illustrative — the shape of the report, not a measured run; your numbers
will differ):

```
═══ chunk=150 k=3 ═══
retrieval recall@k : 5/7 (71%)
answer accuracy    : 5/8 (63%)

failures:
  [RETRIEVAL] What's the rate limit for Basic accounts?
      retrieved: ['Refund Policy', 'Shipping', 'Data Retention']
      answered : I don't have that information in the provided documents.…

═══ chunk=400 k=3 ═══
retrieval recall@k : 7/7 (100%)
answer accuracy    : 8/8 (100%)

═══ chunk=400 k=1 ═══
retrieval recall@k : 6/7 (86%)
answer accuracy    : 7/8 (88%)
```

**The `cause` column is the entire value of this harness.** Without it you see "63% accuracy" and
have no idea what to fix. With it you see "the failures are all RETRIEVAL". Then you know that
prompt work is wasted effort, and you go and fix chunking.

**Three things worth noticing:**

1. **Retrieval recall is an upper bound on answer accuracy.** At 71% recall you can't exceed 71%
   correct (excluding the refusal case, which needs no retrieval).
2. **A retrieval failure often surfaces as a *correct refusal*.** The model honestly says "not in
   the context" — because it genuinely wasn't. The grounding contract is working. Retrieval isn't.
   Without measuring both halves, this looks like a generation problem.
3. **The refusal case is in the eval set permanently.** It's the behaviour most likely to break
   silently when someone edits the prompt.
</details>

---

### Exercise 3 — Citation verification ●●●○○

Build a system that returns structured citations and **verifies** each one against the actual
retrieved chunks. Report: citations that check out, citations whose quote doesn't appear in the
cited source, and citations pointing at a source number that doesn't exist. Then compute a
faithfulness score.

<details>
<summary>✅ Solution</summary>

**Python**
```python
# day12_citation_verify.py
import re
from difflib import SequenceMatcher
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_ollama import OllamaEmbeddings
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()
model = ChatGroq(model="openai/gpt-oss-120b", temperature=0)
embeddings = OllamaEmbeddings(model="nomic-embed-text")

DOCS = [
    Document(page_content="Refund Policy\n\nCustomers may request a refund within 30 days for "
                          "Basic plans and within 60 days for Pro plans.",
             metadata={"section": "Refund Policy"}),
    Document(page_content="Refund Processing\n\nRefunds are processed within 5 business days "
                          "of approval by the billing team.",
             metadata={"section": "Refund Processing"}),
    Document(page_content="Shipping\n\nDomestic orders ship within 2 business days. "
                          "International orders take 10 to 14 days.",
             metadata={"section": "Shipping"}),
    Document(page_content="API Rate Limits\n\nThe API allows 1000 requests per minute for Pro "
                          "and 100 for Basic. Exceeding it returns HTTP 429.",
             metadata={"section": "API Rate Limits"}),
]

store = InMemoryVectorStore.from_documents(DOCS, embeddings)
retriever = store.as_retriever(search_kwargs={"k": 3})

class Citation(BaseModel):
    source_number: int = Field(description="The [n] number of the source")
    quote: str = Field(description="The EXACT sentence from that source, copied verbatim")
    claim: str = Field(description="The claim in your answer this supports")

class CitedAnswer(BaseModel):
    """An answer grounded in numbered sources."""
    answer: str = Field(description="The answer in prose, no citation markers")
    citations: list[Citation] = Field(description="One per claim. Empty if not answerable.")
    answer_found: bool = Field(description="False if the context lacks the answer")

prompt = ChatPromptTemplate.from_messages([
    ("system",
     "Answer using ONLY the numbered context. For every factual claim, provide a citation "
     "with the source number and the EXACT sentence copied verbatim from that source. "
     "Never paraphrase a quote. If the answer isn't present, set answer_found to false.\n\n"
     "Context:\n{context}"),
    ("human", "{question}"),
])

chain = prompt | model.with_structured_output(CitedAnswer, method="json_schema", strict=True)

def normalise(s):
    return re.sub(r"\s+", " ", s.lower().strip())

def verify_citation(citation, docs):
    """Returns (status, detail)."""
    idx = citation.source_number - 1
    if not (0 <= idx < len(docs)):
        return "INVALID_SOURCE", f"source [{citation.source_number}] does not exist"

    doc = docs[idx]
    quote, content = normalise(citation.quote), normalise(doc.page_content)

    if quote in content:
        return "VERIFIED", doc.metadata["section"]

    # Near-match: the model paraphrased instead of copying
    best = max(
        (SequenceMatcher(None, quote, content[i:i + len(quote)]).ratio()
         for i in range(0, max(1, len(content) - len(quote)), 10)),
        default=0.0,
    )
    if best > 0.75:
        return "PARAPHRASED", f"{best:.0%} match in {doc.metadata['section']}"

    # Is the quote in a DIFFERENT retrieved doc? (wrong source number)
    for j, other in enumerate(docs):
        if j != idx and quote in normalise(other.page_content):
            return "WRONG_SOURCE", f"quote is actually in [{j + 1}] {other.metadata['section']}"

    return "FABRICATED", "quote appears in no retrieved source"

QUESTIONS = [
    "How long do I have to request a refund, and how long does processing take?",
    "What is the rate limit and what error do I get when I exceed it?",
    "What is the company's annual revenue?",
]

for question in QUESTIONS:
    docs = retriever.invoke(question)
    context = "\n\n---\n\n".join(
        f"[{i}] {d.page_content}" for i, d in enumerate(docs, 1))
    result = chain.invoke({"context": context, "question": question})

    print(f"\n{'═' * 76}\n❓ {question}\n{'═' * 76}")

    if not result.answer_found:
        print("⚠️  correctly refused — not in the retrieved context")
        continue

    print(f"\n{result.answer}\n")

    counts = {}
    for c in result.citations:
        status, detail = verify_citation(c, docs)
        counts[status] = counts.get(status, 0) + 1

        icon = {"VERIFIED": "✅", "PARAPHRASED": "🟡",
                "WRONG_SOURCE": "🔶", "FABRICATED": "❌", "INVALID_SOURCE": "❌"}[status]
        print(f"  {icon} {status:<14} [{c.source_number}] {detail}")
        print(f'     claim: {c.claim[:60]}')
        print(f'     quote: "{c.quote[:60]}…"')

    verified = counts.get("VERIFIED", 0)
    total = len(result.citations)
    print(f"\n  faithfulness: {verified}/{total} citations verbatim-verified "
          f"({verified / total * 100:.0f}%)" if total else "\n  no citations given")
```

**JavaScript** — the verification core:
```js
function verifyCitation(citation, docs) {
  const idx = citation.sourceNumber - 1;
  if (idx < 0 || idx >= docs.length) {
    return { status: "INVALID_SOURCE", detail: `source [${citation.sourceNumber}] does not exist` };
  }

  const normalise = (s) => s.toLowerCase().replace(/\s+/g, " ").trim();
  const quote = normalise(citation.quote);
  const doc = docs[idx];

  if (normalise(doc.pageContent).includes(quote)) {
    return { status: "VERIFIED", detail: doc.metadata.section };
  }

  // Is it in a DIFFERENT retrieved doc? → wrong source number
  const elsewhere = docs.findIndex((d, j) =>
    j !== idx && normalise(d.pageContent).includes(quote));
  if (elsewhere >= 0) {
    return { status: "WRONG_SOURCE",
             detail: `quote is actually in [${elsewhere + 1}] ${docs[elsewhere].metadata.section}` };
  }

  return { status: "FABRICATED", detail: "quote appears in no retrieved source" };
}
```

**Why the four-way classification matters more than a boolean:**

| Status | What it means | What to do |
|---|---|---|
| `VERIFIED` | Quote copied verbatim from the cited source | Show confidently |
| `PARAPHRASED` | Close but reworded — the *claim* is probably fine | Usually acceptable; tighten the prompt |
| `WRONG_SOURCE` | Real quote, wrong number | Fix by renumbering in the UI; the fact is sound |
| `FABRICATED` | Quote exists nowhere | **Suppress the answer or flag for review** |

A simple `verified: true/false` would put paraphrasing (harmless) and fabrication (dangerous) in
the same group. You would then either raise an alarm on everything or miss the real problem.

**The production use:** this is a **runtime guardrail** (a check that runs on every live
request), not just an eval. If faithfulness for an answer drops below a threshold, don't show
that answer. Fall back to "I found relevant documents but couldn't produce a confident answer,
here they are." That turns a hallucination into a less helpful but honest experience. It is the
trade you want in any domain where being wrong is expensive.

Day 25 turns this into an offline metric run over a dataset. Here it runs on every request.
</details>

---

### Exercise 4 — Conversational RAG ●●●●○

Naive RAG breaks on follow-up questions: *"what about Basic?"* retrieves nothing useful because
the query has no context. Build a conversational RAG chain that uses the chat history to
**rewrite** the follow-up into a standalone question (one that makes sense on its own), then
retrieves. Show the before/after.

<details>
<summary>✅ Solution</summary>

**Python**
```python
# day12_conversational.py
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_ollama import OllamaEmbeddings
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnablePassthrough, RunnableBranch

load_dotenv()
model = ChatGroq(model="openai/gpt-oss-120b", temperature=0)
embeddings = OllamaEmbeddings(model="nomic-embed-text")

DOCS = [
    Document(page_content="Refund Policy\n\nBasic plans allow refunds within 30 days of purchase.",
             metadata={"section": "Refund Policy (Basic)"}),
    Document(page_content="Refund Policy\n\nPro plans allow refunds within 60 days of purchase.",
             metadata={"section": "Refund Policy (Pro)"}),
    Document(page_content="Refund Policy\n\nEnterprise refunds are handled case by case by "
                          "your account manager.",
             metadata={"section": "Refund Policy (Enterprise)"}),
    Document(page_content="API Rate Limits\n\nPro accounts get 1000 requests per minute.",
             metadata={"section": "Rate Limits (Pro)"}),
    Document(page_content="API Rate Limits\n\nBasic accounts get 100 requests per minute.",
             metadata={"section": "Rate Limits (Basic)"}),
    Document(page_content="Shipping\n\nInternational orders take 10 to 14 days.",
             metadata={"section": "Shipping"}),
]

store = InMemoryVectorStore.from_documents(DOCS, embeddings)
retriever = store.as_retriever(search_kwargs={"k": 2})

# ── 1. the query rewriter ────────────────────────────────────────────────
rewrite_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "Given the chat history and a follow-up question, rewrite the follow-up as a "
     "STANDALONE question that can be understood without the history.\n"
     "Do NOT answer it. Output only the rewritten question.\n"
     "If it is already standalone, return it unchanged."),
    MessagesPlaceholder("history"),
    ("human", "{question}"),
])

rewriter = (rewrite_prompt | model | StrOutputParser()).with_config(run_name="rewrite_query")

# Only rewrite when there IS history — saves a call on the first turn.
query_transform = RunnableBranch(
    (lambda x: not x.get("history"), lambda x: x["question"]),
    rewriter,
).with_config(run_name="query_transform")

# ── 2. the answer chain ──────────────────────────────────────────────────
answer_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "Answer using ONLY the context below. Cite sources as [1], [2]. "
     "If the context lacks the answer, say you don't have that information.\n\n"
     "Context:\n{context}"),
    MessagesPlaceholder("history"),
    ("human", "{question}"),
])

def format_docs(docs):
    return "\n\n---\n\n".join(f"[{i}] {d.page_content}" for i, d in enumerate(docs, 1))

conversational_rag = (
    RunnablePassthrough.assign(standalone=query_transform)
    .assign(docs=lambda x: retriever.invoke(x["standalone"]))
    .assign(context=lambda x: format_docs(x["docs"]))
    .assign(answer=answer_prompt | model | StrOutputParser())
)

# ── 3. compare with and without rewriting ────────────────────────────────
TURNS = [
    "How long do I have to get a refund on the Pro plan?",
    "What about Basic?",                    # ← meaningless standalone
    "And the rate limit for that one?",     # ← doubly ambiguous
]

print("═" * 78)
print("WITHOUT rewriting (naive RAG)")
print("═" * 78)
history = []
for turn in TURNS:
    docs = retriever.invoke(turn)           # raw question, no history
    print(f"\n❓ {turn}")
    print(f"   retrieved: {[d.metadata['section'] for d in docs]}")

print("\n" + "═" * 78)
print("WITH rewriting (conversational RAG)")
print("═" * 78)
history = []
for turn in TURNS:
    result = conversational_rag.invoke({"question": turn, "history": history})

    print(f"\n❓ {turn}")
    if result["standalone"].strip() != turn.strip():
        print(f"   ↳ rewritten: \"{result['standalone'].strip()}\"")
    print(f"   retrieved: {[d.metadata['section'] for d in result['docs']]}")
    print(f"   💬 {result['answer'][:110]}")

    history.extend([HumanMessage(turn), AIMessage(result["answer"])])
```

**JavaScript** — the rewriting core:
```js
const rewritePrompt = ChatPromptTemplate.fromMessages([
  ["system",
   "Given the chat history and a follow-up question, rewrite the follow-up as a " +
   "STANDALONE question understandable without the history.\n" +
   "Do NOT answer it. Output only the rewritten question."],
  new MessagesPlaceholder("history"),
  ["human", "{question}"],
]);

const rewriter = rewritePrompt.pipe(model).pipe(new StringOutputParser())
  .withConfig({ runName: "rewrite_query" });

// Only rewrite when there IS history
const queryTransform = RunnableBranch.from([
  [(x) => !x.history?.length, (x) => x.question],
  rewriter,
]);

const conversationalRag = RunnablePassthrough
  .assign({ standalone: queryTransform })
  .assign({ docs: (x) => retriever.invoke(x.standalone) })
  .assign({ context: (x) => formatDocs(x.docs) })
  .assign({ answer: answerPrompt.pipe(model).pipe(new StringOutputParser()) });
```

**Expected output** (illustrative — the retrieved lists depend on your embedding model). The
rewriter really does work this way. In our run with `openai/gpt-oss-120b` (October 2026) it
wrote *"What is the refund period for the Basic plan?"* and *"What is the rate limit for the
Basic plan?"*. Your wording will differ.

```
WITHOUT rewriting
❓ How long do I have to get a refund on the Pro plan?
   retrieved: ['Refund Policy (Pro)', 'Refund Policy (Basic)']       ✅
❓ What about Basic?
   retrieved: ['Shipping', 'Rate Limits (Basic)']                    ❌ wrong topic!
❓ And the rate limit for that one?
   retrieved: ['Rate Limits (Pro)', 'Rate Limits (Basic)']           ❌ which one?

WITH rewriting
❓ What about Basic?
   ↳ rewritten: "How long do I have to get a refund on the Basic plan?"
   retrieved: ['Refund Policy (Basic)', 'Refund Policy (Pro)']       ✅
❓ And the rate limit for that one?
   ↳ rewritten: "What is the API rate limit for the Basic plan?"
   retrieved: ['Rate Limits (Basic)', 'Rate Limits (Pro)']           ✅
```

**"What about Basic?" retrieves *Shipping*** without rewriting. Those three words have no topic,
so their embedding is essentially noise, and it matches whatever happens to be nearby.

**Four design points:**

1. **`RunnableBranch` skips the rewrite on turn one.** No history means nothing to resolve, and
   you save a model call plus latency on every conversation's first turn.
2. **"Do NOT answer it" is essential.** Without it the rewriter often answers the question
   instead of rewriting it, and you then search using an answer.
3. **History goes into *both* chains** — the rewriter needs it to resolve references, and the
   answer chain needs it for conversational tone and to avoid repeating itself.
4. **`standalone` is kept in the output.** Being able to see what was actually searched for is
   the first thing you want when a follow-up returns something strange.

**The cost:** one extra LLM call per turn after the first. Reduce it by using a small, fast model
for rewriting. It's an easy task and doesn't need the 120B model. This is exactly Day 08's
route-by-difficulty principle, applied inside a RAG pipeline.
</details>

---

### Exercise 5 — 🏆 StudyBuddy v2: chat with your PDFs ●●●●●

Upgrade StudyBuddy to answer from **your own documents**. Build a CLI (command-line program)
that:

- ingests a folder of files into a persistent store with incremental upsert (adding only new or
  changed chunks)
- supports conversational follow-ups with query rewriting
- streams answers with verified citations
- shows which chunks were used
- refuses honestly when the answer isn't there
- reports timing and token usage

<details>
<summary>✅ Solution</summary>

**Python**
```python
# studybuddy_v2.py
"""StudyBuddy v2 — conversational RAG over your own documents."""
import hashlib, re, sys, time
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnablePassthrough, RunnableBranch
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter, Language,
)

load_dotenv()

EMBEDDING_MODEL = "nomic-embed-text"
PERSIST_DIR = "./studybuddy_db"

fast = ChatGroq(model="openai/gpt-oss-20b", temperature=0)    # rewriting
smart = ChatGroq(model="openai/gpt-oss-120b", temperature=0)  # answering
embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)

store = Chroma(
    collection_name="studybuddy",
    embedding_function=embeddings,
    persist_directory=PERSIST_DIR,
    collection_metadata={"hnsw:space": "cosine"},
)

# ═══════════════════ INGEST ══════════════════════════════════════════════
PROFILES = {
    ".md":  {"size": 800, "overlap": 120, "markdown": True},
    ".txt": {"size": 1000, "overlap": 150, "markdown": False},
    ".py":  {"size": 1200, "overlap": 0, "language": Language.PYTHON},
    ".js":  {"size": 1200, "overlap": 0, "language": Language.JS},
}

def content_hash(text):
    return hashlib.sha256(f"{EMBEDDING_MODEL}:{text}".encode()).hexdigest()[:16]

def chunk_file(path: Path):
    profile = PROFILES.get(path.suffix.lower(),
                           {"size": 1000, "overlap": 150, "markdown": False})
    raw = path.read_text(encoding="utf8", errors="replace")

    splitter = (
        RecursiveCharacterTextSplitter.from_language(
            profile["language"], chunk_size=profile["size"], chunk_overlap=profile["overlap"])
        if profile.get("language")
        else RecursiveCharacterTextSplitter(
            chunk_size=profile["size"], chunk_overlap=profile["overlap"])
    )

    chunks = []
    if profile.get("markdown"):
        header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")],
            strip_headers=True)
        sections = splitter.split_documents(header_splitter.split_text(raw)) \
                   or [Document(page_content=raw, metadata={})]
        for s in sections:
            crumb = " > ".join(s.metadata[k] for k in ("h1", "h2", "h3") if k in s.metadata)
            chunks.append(Document(
                page_content=f"{crumb}\n\n{s.page_content}" if crumb else s.page_content,
                metadata={"source": path.name, "breadcrumb": crumb or path.stem},
            ))
    else:
        for piece in splitter.split_text(raw):
            chunks.append(Document(
                page_content=f"{path.stem}\n\n{piece}",
                metadata={"source": path.name, "breadcrumb": path.stem},
            ))

    return [c for c in chunks if len(c.page_content.strip()) >= 50]

def ingest(folder):
    files = [p for p in Path(folder).rglob("*") if p.suffix.lower() in PROFILES]
    if not files:
        print(f"no supported files in {folder} (looking for {', '.join(PROFILES)})")
        return

    existing = set(store.get(include=[])["ids"])
    added = skipped = 0
    t0 = time.time()

    for path in files:
        chunks = chunk_file(path)
        new = [(content_hash(c.page_content), c) for c in chunks]
        new = [(h, c) for h, c in new if h not in existing]

        if new:
            for h, c in new:
                c.metadata["content_hash"] = h
            store.add_documents([c for _, c in new], ids=[h for h, _ in new])
            existing.update(h for h, _ in new)

        added += len(new)
        skipped += len(chunks) - len(new)
        print(f"  {path.name:<40} {len(chunks):>4} chunks, {len(new):>4} new")

    print(f"\n✅ {added} chunks added · {skipped} already present · {time.time() - t0:.1f}s")

# ═══════════════════ QUERY ═══════════════════════════════════════════════
retriever = store.as_retriever(search_kwargs={"k": 4})

rewrite_prompt = ChatPromptTemplate.from_messages([
    ("system", "Rewrite the follow-up question as a STANDALONE question using the chat "
               "history. Do NOT answer it. Output only the rewritten question. "
               "If already standalone, return it unchanged."),
    MessagesPlaceholder("history"),
    ("human", "{question}"),
])

# Only rewrite when there IS history — saves a call on turn one.
query_transform = RunnableBranch(
    (lambda x: not x.get("history"), lambda x: x["question"]),
    rewrite_prompt | fast | StrOutputParser(),
).with_config(run_name="rewrite_query")

class Citation(BaseModel):
    source_number: int = Field(description="The [n] number of the source")
    quote: str = Field(description="The EXACT sentence from that source, copied verbatim")

class Answer(BaseModel):
    """A grounded answer with verifiable citations."""
    answer: str = Field(description="The answer in prose. No citation markers.")
    citations: list[Citation] = Field(description="One per claim. Empty if not answerable.")
    answer_found: bool = Field(description="False if the context lacks the answer")

answer_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are StudyBuddy. Answer using ONLY the numbered context below.\n"
     "For every factual claim provide a citation with the source number and the EXACT "
     "sentence copied verbatim. Never paraphrase a quote.\n"
     "If the context does not contain the answer, set answer_found to false.\n\n"
     "Context:\n{context}"),
    MessagesPlaceholder("history"),
    ("human", "{question}"),
])

def format_docs(docs):
    return "\n\n---\n\n".join(
        f"[{i}] ({d.metadata.get('source')} · {d.metadata.get('breadcrumb')})\n{d.page_content}"
        for i, d in enumerate(docs, 1))

pipeline = (
    RunnablePassthrough.assign(standalone=query_transform)
    .assign(docs=lambda x: retriever.invoke(x["standalone"]))
    .assign(context=lambda x: format_docs(x["docs"]))
)

def verify(citation, docs):
    idx = citation.source_number - 1
    if not (0 <= idx < len(docs)):
        return False
    norm = lambda s: re.sub(r"\s+", " ", s.lower().strip())
    return norm(citation.quote)[:50] in norm(docs[idx].page_content)

# ═══════════════════ CLI ═════════════════════════════════════════════════
def chat():
    count = store._collection.count()
    if count == 0:
        print("⚠️  the store is empty — run:  python studybuddy_v2.py ingest <folder>")
        return

    print("╔══════════════════════════════════════════════════════════╗")
    print("║  StudyBuddy v2 — chat with your documents                ║")
    print(f"║  {count:>5} chunks indexed · /sources /reset /exit          ║")
    print("╚══════════════════════════════════════════════════════════╝\n")

    history = []

    while True:
        try:
            question = input("you › ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not question or question == "/exit":
            break

        if question == "/reset":
            history = []
            print("  history cleared\n")
            continue

        if question == "/sources":
            raw = store.get(include=["metadatas"])
            sources = {}
            for m in raw["metadatas"]:
                sources[m.get("source", "?")] = sources.get(m.get("source", "?"), 0) + 1
            for src, n in sorted(sources.items()):
                print(f"  {n:>5}  {src}")
            print()
            continue

        t0 = time.time()
        try:
            state = pipeline.invoke({"question": question, "history": history})

            if state["standalone"].strip().lower() != question.lower():
                print(f"  ↳ searching: \"{state['standalone'].strip()}\"")

            # Show sources IMMEDIATELY — retrieval is fast, generation is slow.
            print("  📚 " + " · ".join(
                f"[{i}] {d.metadata.get('breadcrumb', '?')[:28]}"
                for i, d in enumerate(state["docs"], 1)))

            answerer = answer_prompt | smart.with_structured_output(
                Answer, method="json_schema", strict=True)
            result = answerer.invoke({
                "context": state["context"], "question": question, "history": history,
            })

            if not result.answer_found:
                print("\n  ⚠️  I don't have that in the indexed documents.\n")
                continue

            print(f"\n  {result.answer}\n")

            for c in result.citations:
                ok = verify(c, state["docs"])
                doc = state["docs"][c.source_number - 1] \
                      if 0 < c.source_number <= len(state["docs"]) else None
                label = f"{doc.metadata.get('source')} · {doc.metadata.get('breadcrumb')}" \
                        if doc else "INVALID"
                print(f"  {'✅' if ok else '⚠️ '} [{c.source_number}] {label}")

            history.extend([HumanMessage(question), AIMessage(result.answer)])
            history = history[-8:]                       # bound the history

            print(f"\n  ⏱  {(time.time() - t0) * 1000:.0f}ms\n")

        except Exception as e:
            print(f"\n  ⚠️  {str(e)[:120]}\n")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "chat"
    if cmd == "ingest":
        ingest(sys.argv[2] if len(sys.argv) > 2 else ".")
    else:
        chat()
```

```bash
python studybuddy_v2.py ingest ./my-notes
python studybuddy_v2.py ingest ./my-notes    # second run: all skipped
python studybuddy_v2.py
```

**JavaScript** — the same architecture; the distinctive pieces:
```js
// Two models: cheap for rewriting, strong for answering (Day 08's routing lesson)
const fast  = new ChatGroq({ model: "openai/gpt-oss-20b", temperature: 0 });
const smart = new ChatGroq({ model: "openai/gpt-oss-120b", temperature: 0 });

// Content hash AS the Chroma id → idempotent upsert (Day 11's lesson)
await store.addDocuments(newDocs, { ids: newDocs.map((d) => d.metadata.contentHash) });

// Sources shown before the answer streams
const state = await pipeline.invoke({ question, history });
console.log("📚 " + state.docs.map((d, i) => `[${i + 1}] ${d.metadata.breadcrumb}`).join(" · "));
const result = await answerPrompt
  .pipe(smart.withStructuredOutput(Answer, { method: "jsonSchema" }))
  .invoke({ context: state.context, question, history });
```

**Everything from Week 2 is in this one program:**

| Day | Where it appears |
|---|---|
| 08 | Stuff strategy; cheap model for rewriting, strong for answering |
| 09 | Per-filetype profiles, markdown header injection, minimum chunk length |
| 10 | Batched embeddings, content hashing namespaced by model |
| 11 | Persistent Chroma, hash-as-id idempotent upsert, cosine metric |
| 12 | Grounding contract, verified citations, conversational rewriting |

**Six design decisions worth defending:**

1. **Ingest and chat are separate commands.** Different lifecycles, different cost profiles. The
   chat process never re-embeds.
2. **The content hash is the document ID.** A content hash is a short fingerprint computed from
   the chunk's text. So re-ingesting an unchanged file is a no-op (it does nothing), and
   re-ingesting a changed file adds only the chunks whose text changed.
   ⚠️ It does **not** remove the old chunks of that file, so the old version can still be
   retrieved — the "staleness" failure from §2. A real system first deletes the file's chunks
   by their `source` metadata, then adds the new ones.
3. **Rewriting uses the 20B model.** It's an easy transformation. Paying 120B rates for it on
   every turn is waste.
4. **`RunnableBranch` skips rewriting on turn one** — no history, nothing to resolve.
5. **Sources render before the answer.** Retrieval is typically tens of milliseconds, generation
   often seconds (time yours). The user sees progress immediately and can start checking sources while the answer arrives.
6. **Citations are verified, not trusted.** An unverified citation gets a ⚠️ rather than a ✅, so
   the user knows which claims to check.

**What it still can't do — and this is the honest bridge to tomorrow.** Ask it something where
the first retrieval returns nothing useful. It answers *"I don't have that information"* and
stops. A human researcher would rephrase and search again.

It also can't decide *whether* to retrieve, so a greeting triggers a pointless search. It can't
combine several retrievals for a multi-part question. And it can't tell you that the retrieved
documents were irrelevant before it wastes a generation call on them.

Fixing those needs retrieval that **adapts** — reranking, multi-query, self-correction. That's
Day 13.
</details>

---

## 9. Interview questions

### Basic

<details>
<summary><b>Q: What is RAG and why use it?</b></summary>

Retrieval-Augmented Generation: retrieve documents relevant to a question and put them in the
prompt so the model answers from real, current data rather than from its training weights.

It solves three problems:

- the model doesn't know your private data
- its training data is stale (out of date)
- it hallucinates when asked about things it doesn't know

RAG also makes answers *verifiable* through citations. And updating knowledge means re-ingesting
a document rather than fine-tuning (retraining) a model.
</details>

<details>
<summary><b>Q: Walk through the RAG pipeline.</b></summary>

Two phases with very different cost profiles.

**Ingest (offline, per document version):**

1. Load files into Documents, keeping page and section metadata.
2. Split them into chunks with overlap and injected header context.
3. Embed the chunks in batches.
4. Store them in a vector database with their metadata.

**Query (online, per request):**

1. Embed the question.
2. Run a similarity search for the top-k chunks (optionally hybrid, with metadata filters).
3. Format the chunks with numbers so they can be cited.
4. Prompt the model with instructions to answer only from that context.
5. Return the answer with its sources.

Keeping ingest separate from query is what makes it practical — you embed once and query
thousands of times.
</details>

<details>
<summary><b>Q: What is `k` and how do you choose it?</b></summary>

The number of chunks retrieved and passed to the model. If it is too small, the answer may not
be in the context. If it is too large, you pay for more tokens and dilute the prompt with
irrelevant text. You also hit "lost in the middle", where information in the middle of the
context gets less attention.

3–6 is a reasonable default for question answering. The better pattern is retrieve-then-rerank:
fetch 20 candidates cheaply, rerank them accurately and keep the top 4. You get the recall of a
large `k` with the precision of a small one. Note `k` interacts with chunk size: your real budget
is `k × chunkSize`.
</details>

<details>
<summary><b>Q: How do you make a RAG system say "I don't know"?</b></summary>

Don't give a vague instruction like "say you don't know". Give it an exact phrase to output
instead: "If the context does not contain the answer, reply exactly: *I don't have that
information in the provided documents*". A concrete sequence of tokens is far easier for the
model to produce than an abstract instruction. That matters because the model is working
against its training data, where confident answers vastly outnumber admissions of not knowing.

Even better, use structured output with a boolean `answerFound` field. The model must commit to
true or false, and you branch in code instead of parsing prose. Then test it explicitly with an
out-of-corpus question — it's the behaviour most likely to be silently missing.
</details>

### Intermediate

<details>
<summary><b>Q: How do you evaluate a RAG system?</b></summary>

Measure the two halves separately. They have different fixes, and mixing them up is why RAG
debugging goes round in circles.

**Retrieval:** recall@k (was the chunk containing the answer retrieved?) and precision@k (how
much of what you retrieved was useful?). Build this from a set of questions with known
answer-locations.

**Generation:**

- faithfulness — is every claim supported by the retrieved context?
- answer relevance — does it address the question?
- citation accuracy — do the markers point at sources that actually contain the quoted text?

The key insight is that **retrieval recall is an upper bound on answer accuracy** — at 60%
recall, no prompt engineering gets you past 60%. So for every failure, the first diagnostic is:
was the correct chunk in the retrieved set? Not retrieved means a chunking, embedding or query
problem. Retrieved but answered wrong means a prompt, ordering or model problem.
</details>

<details>
<summary><b>Q: Why does naive RAG fail on follow-up questions?</b></summary>

Because retrieval sees only the raw question. "What about Basic?" has no topic in it. Its
embedding is essentially noise and matches unrelated documents. The context needed to understand
it lives in the chat history, which the retriever never sees.

The fix is **query rewriting**. Use the model plus the history to turn the follow-up into a
standalone question ("How long do I have to get a refund on the Basic plan?"). Then retrieve
using that question. Two practical details:

- Tell it explicitly *not* to answer the question, or it often will.
- Skip the rewrite on the first turn, when there's no history. That saves a call and some latency.

Use a small fast model for the rewrite — it's an easy task.
</details>

<details>
<summary><b>Q: How do you make citations trustworthy?</b></summary>

Don't trust free-text `[1]` markers — they're generated tokens and can be wrong or invented.

Use structured output that requires, for each claim, the source number **and the exact
supporting quote copied verbatim**. Then verify in code that the quote actually appears in that
chunk. Classify the outcome rather than using a true/false boolean:

- verified — exact match
- paraphrased — close; usually fine
- wrong-source — real quote, wrong number; the fact is sound
- fabricated — appears nowhere; dangerous

That classification lets you respond in proportion to the problem. It also works as a **runtime
guardrail**: if faithfulness is low, hide the answer and show the retrieved documents instead.
Turning a hallucination into a less helpful but honest response is the right trade wherever being
wrong is expensive.
</details>

<details>
<summary><b>Q: What is "lost in the middle" and how does it affect RAG?</b></summary>

Models pay more reliable attention to information at the start and end of a long context than
to the middle. So retrieving 20 chunks with the relevant one at position 11 can produce a worse
answer than retrieving 4 chunks where it sits at position 2.

Three ways to reduce it:

1. Retrieve fewer chunks (smaller `k`).
2. Reorder so the highest-scoring chunks sit at both ends, with weaker ones in the middle
   (LangChain's `LongContextReorder`).
3. The proper fix: retrieve a large candidate set cheaply, rerank it with a cross-encoder, and
   pass only the top few. A cross-encoder is a model that reads the question and a chunk
   together and scores how well they match.

That gives you the recall of a large `k` and the precision of a small one.
</details>

### Advanced

<details>
<summary><b>Q: Your RAG system gives wrong answers 30% of the time. Diagnose it systematically.</b></summary>

The first move is to **split retrieval failures from generation failures**, because everything
after depends on which it is. For each failing question, check whether the chunk containing the
answer was in the retrieved set. That single check partitions the 30% into two piles with
completely different fixes, and it takes minutes.

**If retrieval failed**, work up the ingest pipeline cheapest-first:
- Is the answer in any chunk *intact*, or split across a boundary? That caps your ceiling and no
  retrieval change can fix it — adjust chunk size and overlap.
- Did chunks lose their headings? Injecting header breadcrumbs often improves recall noticeably
  on structured documents — measure the before/after on your own eval set.
- Is the query lexical (about exact words) — an error code, name or identifier? Embeddings blur
  those, so add hybrid search (keyword search plus vector search).
- Is there a phrasing gap between short queries and full-sentence documents? Add query rewriting
  or multi-query expansion.
- Are filters too strict? Or is the store filtering after the search (post-filtering) and leaving
  too few results?
- Are near-duplicates crowding the top-k? Deduplicate at ingest, or use MMR (a search mode that
  prefers varied results).

**If retrieval succeeded but the answer was wrong**:
- Was the right chunk buried mid-context? Reduce `k` or rerank.
- Is the grounding instruction present and specific? Test with an out-of-corpus question.
- Is the model overriding context with parametric knowledge? Verify citations to detect it.
- Is the context formatted so chunks are distinguishable and citable?

**Then make it permanent.** Every diagnosed failure becomes a case in the eval set, labelled as
a retrieval or a generation failure. The suite runs in CI (continuous integration — automatic
checks on every change). Without that, the next chunking "improvement" silently brings old bugs
back.

The mistake I'd call out explicitly: spending a week on prompt engineering when retrieval recall
is 70%. The ceiling is 70% and no prompt moves it.
</details>

<details>
<summary><b>Q: When is RAG the wrong tool?</b></summary>

- **Questions requiring aggregation over the whole corpus** — "how many contracts mention
  indemnity?", "what's the average deal size?". Retrieval returns k chunks, not a count. You need
  SQL, or an agent that queries structured data.
- **Questions needing the full document** — "summarise this contract" isn't a retrieval problem;
  you want the whole document, which is a document-chain job (Day 08).
- **Highly structured queries** — "orders over £500 from last quarter" is a database query.
  Embeddings are poor at numeric comparisons. Use text-to-SQL or self-query with metadata filters.
- **When the model already knows** — general knowledge doesn't need retrieval, and retrieving
  anyway adds latency, cost and a chance of retrieving something misleading.
- **When behaviour, not knowledge, is the gap** — if you need a consistent tone, format or
  reasoning style, that's prompting or fine-tuning. RAG injects facts, not style.
- **Very small corpora** — under a few thousand tokens, just put everything in the prompt.
  Retrieval adds moving parts and a failure mode for no benefit.

The general framing: RAG solves "the model doesn't know this fact". It doesn't solve "the model
can't compute this", "the model doesn't behave this way", or "this needs all the data at once".
Knowing which problem you have is the actual skill.
</details>

<details>
<summary><b>Q: Design RAG for a legal firm: 100,000 contracts, answers must be auditable, strict access control.</b></summary>

The three constraints — auditability, access control, and the domain — drive almost every
decision.

**Access control comes first, because it's a correctness requirement, not a feature.** Use
matter-level partitioning: a separate collection per matter (legal case) or client, not metadata
filters. Then a leak between matters is structurally impossible, rather than one bug away. Every
query carries the user's authorisation from the session. A single data-access layer checks it,
and no calling code can go around that layer. Log every retrieval with user, matter and
documents returned.

**Chunking follows the document structure.** Contracts are clause-based: one chunk per clause,
with the clause number, section heading, contract ID and effective date in both metadata and
injected text. Fixed-size splitting would cut clauses in half, which is legally meaningless.

**Retrieval must be hybrid.** Legal queries are full of exact terms — clause numbers, defined
terms, party names, statute references — that embeddings blur together. BM25 (a classic keyword
ranking method) handles those. Vectors handle "what are our termination rights". Fuse the two
result lists with RRF (Reciprocal Rank Fusion), then rerank.

**Auditability shapes generation.** Use structured output with a verbatim quote for each claim.
Verify each quote against the source chunk in code. If faithfulness fails, suppress the answer
rather than show it. Store the full trace immutably (so it can never be changed): question,
rewritten query, retrieved chunk IDs and versions, prompt, model version, answer, citations.
"Which contract version did this answer come from, on that date?" must be answerable.

**Versioning is non-negotiable.** Contracts get amended. Each chunk carries a version and an
effective date. Queries use the current version by default but can be limited to a point in
time. Superseded (replaced) versions are kept, not deleted. They are clearly labelled, so an
answer never silently mixes versions.

**Human review by default** for anything advisory. This is a research assistant that surfaces
sources for a lawyer, not an oracle. The product framing matters as much as the architecture.

**Evaluation** uses a golden set (trusted questions with known correct answers) built with the
lawyers. It measures retrieval recall and citation accuracy separately, and runs before every
deploy. In this domain a confident wrong answer is far worse than "I couldn't find it". So tune
toward abstention (declining to answer), and track the abstention rate as a key metric.
</details>

---

## 10. Recap

- ✅ RAG means: retrieve the relevant chunks, then stuff **only those** into the prompt — far
  cheaper than map-reduce (roughly 90× fewer tokens in the §1 illustration)
- ✅ Ingest (offline, expensive, rare) and query (online, cheap, constant) are separate lifecycles
- ✅ The standard chain: `RunnableParallel({docs: retriever, question: passthrough})` then `.assign()`
- ✅ Format context numbered and separated so citations round-trip to real chunks
- ✅ The grounding contract: only the context, cite everything, **an exact refusal phrase**, no invented citations
- ✅ Verify citations against source text — classify verified / paraphrased / wrong-source / fabricated
- ✅ `k = 3–6`; large `k` triggers lost-in-the-middle
- ✅ **Measure retrieval and generation separately** — recall caps answer accuracy
- ✅ Follow-up questions need **query rewriting** or retrieval sees meaningless input
- ✅ Show sources before streaming the answer — retrieval is typically tens of ms, generation
  often seconds

> 📏 **Measure it:** Test today's pipeline with three questions, using code you already have. In
> `day12_rag.py` / `day12-rag.js`, the Pro refund question must answer 60 days with a citation,
> and the "CEO's address" question must say "I don't know" using the exact refusal phrase. In
> `day12_structured_citations.py` / `day12-structured-citations.js`, "How long for a Pro refund?"
> passes only if every citation prints ✅ — and Day 25 turns these checks into a full evaluation
> suite.

### Tomorrow

**[Day 13 — Advanced RAG & retrievers](day-13-advanced-rag.md)**: today's pipeline retrieves once
and hopes for the best. Tomorrow it gets smarter with MMR for diversity, multi-query expansion,
HyDE, reranking with cross-encoders, parent-document retrieval, contextual compression and
self-query with metadata filters. It also adds the corrective and self-RAG patterns that **grade
their own retrieval and try again**.

### Quick self-check

1. Retrieval recall is 65%. You spend a week improving the prompt. What's your ceiling?
2. A user asks "what about the Basic plan?" as a follow-up and gets shipping information. Why?
3. Your RAG confidently answers a question about something not in your documents. What's missing?

<details>
<summary>Answers</summary>

1. **65%.** If the chunk containing the answer isn't retrieved, no prompt can produce a correct
   grounded answer. Fix retrieval first — chunking, header injection, hybrid search — then tune
   the prompt.
2. No **query rewriting**. The retriever embeds "what about the Basic plan?" literally; with no
   topic in the query, the embedding is near-noise and matches arbitrary chunks. Rewrite the
   follow-up into a standalone question using chat history, then retrieve on that.
3. The **grounding contract**. Specifically: an explicit instruction to use only the provided
   context, plus an exact refusal phrase for when it doesn't contain the answer. Without it the
   model falls back on parametric knowledge, and you can't tell that apart from a real answer.
   Add a structured `answerFound` boolean and test with an out-of-corpus question.
</details>

---

<div align="center">

**[← Day 11 — Vector Databases](day-11-vector-databases.md)** · **[Week 2 index](README.md)** · **[Day 13 — Advanced RAG →](day-13-advanced-rag.md)**

</div>
