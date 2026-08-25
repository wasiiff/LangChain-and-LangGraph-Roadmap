# Day 08 — Chains: Sequential, Parallel, Router & Document Chains

> ⏱ **Time:** ~2.5 hours · 🎯 **Prereqs:** [Day 07](../week-01-foundations/day-07-lcel-and-runnables.md) · 🧩 **Difficulty:** ●●○○○

**Today you learn:** what "a chain" actually means, the four classic chain shapes (sequential,
parallel, router, conversation), and the **document chains** — stuff, map-reduce, refine,
map-rerank — that decide how you feed 500 pages into an 8K context window.

That last part is the bridge into RAG. You can't retrieve documents usefully until you know how
to *combine* them.

---

## 1. The problem

You have a 90-page contract and a question: *"What are the termination clauses?"*

```
   90 pages ≈ 45,000 tokens
   your model's context window ≈ 8,000 tokens
```

It doesn't fit. So what do you do?

- **Truncate it?** You'd throw away 80% of the contract, probably including the answer.
- **Use a 1M-context model?** Expensive per call, slow, and "lost in the middle" (Day 01) means
  it may ignore the clause anyway.
- **Split it and ask 90 times?** Now you have 90 answers and no way to combine them.

That last option is *almost* right — you just need a strategy for the combining step. That
strategy is a **document chain**, and there are four of them, each with a different
cost/quality/latency trade-off.

By the end of today you'll know which one to reach for and why.

---

## 2. Mental model

### What is a chain?

```
   CHAIN                                    AGENT
   ─────                                    ─────
   YOU decide the steps.                    THE MODEL decides the steps.
   Fixed at build time.                     Chosen at run time.
   Predictable cost & latency.              Unbounded until it stops.
   Easy to test.                            Hard to test.

   retrieve → prompt → generate → parse     "call a tool… hmm, now call another…"

   Use when the process is known.           Use when the process depends on the answer.
```

**A chain is a fixed sequence of steps.** That's the whole definition. In modern LangChain a
chain is just an LCEL composition — there's no `Chain` class you need any more.

### The four classic shapes

```
   SEQUENTIAL          A → B → C
                       each step needs the previous one's output

   PARALLEL            A ─┬→ B ─┐
                          └→ C ─┴→ merge
                       independent steps, run at once

   ROUTER              classify → ┬→ chain A
                                  ├→ chain B
                                  └→ chain C
                       pick one path

   CONVERSATION        history + input → model → response → append to history
                       sequential, but state accumulates
```

You built all four on Day 07 — `RunnableSequence`, `RunnableParallel`, `RunnableBranch`, and
`MessagesPlaceholder`. Today we name them and add the fifth, most important shape:

### Document chains — the four strategies

```
   ┌─ STUFF ────────────────────────────────────────────────────────┐
   │  [doc1][doc2][doc3] ──all at once──▶ LLM ──▶ answer            │
   │  1 call · cheapest · best quality · ❌ must fit in context      │
   └────────────────────────────────────────────────────────────────┘

   ┌─ MAP-REDUCE ───────────────────────────────────────────────────┐
   │  [doc1]──▶LLM──▶summary1 ┐                                     │
   │  [doc2]──▶LLM──▶summary2 ├──▶ LLM ──▶ final answer             │
   │  [doc3]──▶LLM──▶summary3 ┘                                     │
   │  N+1 calls · parallel (fast) · ❌ loses cross-document context  │
   └────────────────────────────────────────────────────────────────┘

   ┌─ REFINE ───────────────────────────────────────────────────────┐
   │  [doc1]──▶LLM──▶draft1                                         │
   │  draft1+[doc2]──▶LLM──▶draft2                                  │
   │  draft2+[doc3]──▶LLM──▶final                                   │
   │  N calls · SEQUENTIAL (slow) · ✅ keeps context · ❌ drift       │
   └────────────────────────────────────────────────────────────────┘

   ┌─ MAP-RERANK ───────────────────────────────────────────────────┐
   │  [doc1]──▶LLM──▶answer1 + score 0.3 ┐                          │
   │  [doc2]──▶LLM──▶answer2 + score 0.9 ├──▶ pick highest ──▶ done  │
   │  [doc3]──▶LLM──▶answer3 + score 0.1 ┘                          │
   │  N calls · parallel · ✅ great for "find the one fact"          │
   │  ❌ useless when the answer spans documents                     │
   └────────────────────────────────────────────────────────────────┘
```

**The decision rule, memorised:**

```
   Does everything fit in the context window?
        │
       YES ──▶ STUFF. Always. Don't overthink it.
        │
        NO ──▶ Is the answer in ONE document, or spread across many?
                    │
              ONE ──┴──▶ MAP-RERANK  (or better: retrieve less — that's RAG)
                    │
             MANY ──┴──▶ Do you need every detail, or a synthesis?
                              │
                   SYNTHESIS ─┴──▶ MAP-REDUCE  (fast, parallel)
                              │
                 EVERY DETAIL ┴──▶ REFINE      (slow, but nothing is dropped)
```

---

## 3. First principles

### 3.1 Sequential chains

Each step consumes the previous step's output.

```js
outline = generateOutline(topic)
draft   = writeDraft(outline)      // needs outline
edited  = edit(draft)              // needs draft
```

In LCEL that's just `.pipe()` / `|`. The only real skill is **managing the seams** — step N's
output must match step N+1's input. Two techniques:

```js
// A) Reshape with a lambda between steps
a.pipe((out) => ({ outline: out, topic })).pipe(b)

// B) Accumulate with assign (usually better — nothing gets lost)
RunnablePassthrough.assign({ outline: a }).pipe(RunnablePassthrough.assign({ draft: b }))
```

> 💡 **Prefer (B).** With `assign`, every earlier value stays available to every later step.
> With (A) you have to manually forward anything you might need later, and you *will* forget one.

### 3.2 Parallel chains

Independent steps on the same input, run concurrently. Turns *sum* of latencies into *max*.

```js
RunnableParallel.from({ summary: sumChain, sentiment: sentChain, topics: topicChain })
```

The trap from Day 07, restated because it bites everyone: **`RunnableParallel` replaces the
input**; `RunnablePassthrough.assign` *extends* it.

### 3.3 Router chains

Classify, then dispatch. Two implementations:

```js
// Declarative
RunnableBranch.from([
  [(x) => x.category === "BILLING", billingChain],
  [(x) => x.category === "BUG", bugChain],
  defaultChain,
])

// Or just return a Runnable from a lambda — LangChain will invoke it
RunnableLambda.from((x) => CHAINS[x.category] ?? defaultChain)
```

**Why route at all?** Three real reasons:

| Reason | Example |
|---|---|
| **Different prompts** | A billing reply and a bug reply need different instructions |
| **Different models** | Route simple queries to an 8B model, hard ones to a 70B |
| **Different tools/data** | A code question searches your docs; a billing question hits Stripe |

That second one is where the money is. Most production systems route *by difficulty* to control
cost, not just by topic.

### 3.4 Conversation chains

A sequential chain whose input includes accumulated history. You built this on Day 05:

```js
ChatPromptTemplate.fromMessages([
  ["system", "..."],
  new MessagesPlaceholder("history"),
  ["human", "{input}"],
])
```

The chain itself is stateless — **you** own the history array. Making that automatic and
persistent is what LangGraph checkpointers do (Day 20). We cover the interim options on Day 14.

### 3.5 Document chains — the details that matter

#### Stuff

```
prompt = "Answer using this context:\n\n{context}\n\nQuestion: {question}"
context = docs.map(d => d.pageContent).join("\n\n")
```

One call. Best quality, because the model sees everything at once and can reason across
documents. **This is what you should use 90% of the time** — and the entire point of RAG
(Day 12) is to *make* stuffing viable by retrieving only the 5 chunks that matter.

The formatting matters more than people expect:

```js
// ❌ documents run together, model can't tell them apart or cite them
docs.map(d => d.pageContent).join(" ")

// ✅ separated, numbered, with metadata for citation
docs.map((d, i) => `[${i + 1}] (source: ${d.metadata.source}, page ${d.metadata.page})\n${d.pageContent}`)
    .join("\n\n---\n\n")
```

#### Map-reduce

Two prompts: a **map** prompt applied to each document, and a **reduce** prompt applied to the
collected results.

```
map:    "Summarise this excerpt: {doc}"
reduce: "Combine these summaries into one answer: {summaries}"
```

Parallel, so it's fast. The cost is **cross-document reasoning** — if the answer requires
connecting a fact on page 3 to a fact on page 60, map-reduce will likely miss it, because
neither map call saw both.

> ⚠️ If the summaries themselves overflow the context window, you need a **recursive** reduce:
> reduce in batches, then reduce the reductions. Production map-reduce implementations do this;
> a naive one silently breaks on large inputs.

#### Refine

Sequential. Carries a running answer forward and updates it with each new document.

```
initial: "Answer the question using: {doc1}"
refine:  "Here is your current answer: {answer}
          Here is more context: {doc_n}
          Improve the answer if the new context helps. Otherwise return it unchanged."
```

Keeps full context, so cross-document reasoning works. Two real costs:

1. **It's serial** — N documents means N sequential round trips. Slow, and you can't parallelise it.
2. **Drift** — each rewrite can degrade the answer. Later documents get more influence than
   early ones, and the model sometimes "improves" a correct answer into a wrong one.

#### Map-rerank

Each document produces an answer *and* a self-reported confidence score. Take the highest.

Great for needle-in-a-haystack lookups. Useless when the answer is a synthesis. Also note the
score is the model's own opinion, which is only loosely calibrated.

### 3.6 The modern API

LangChain still ships helpers for the stuff pattern:

```js
createStuffDocumentsChain({ llm, prompt })   // JS  — @langchain/classic/chains/combine_documents
create_stuff_documents_chain(llm, prompt)    # Python — langchain_classic.chains.combine_documents
```

These handle document formatting and the `{context}` variable for you. Map-reduce and refine no
longer have blessed helper functions in 1.x — **you compose them from LCEL**, which is what
we'll do below. That's a deliberate design decision: the old `MapReduceDocumentsChain` was
opaque and hard to customise, and the LCEL version is about 15 lines and fully inspectable.

> 🚨 **Version warning — this is the big one for Week 2.**
>
> In LangChain **1.x**, all the legacy chains and retrievers moved into a separate package.
> Most tutorials you'll find online use the old paths, which **no longer exist**:
>
> | ❌ Old (0.x, broken in 1.x) | ✅ New (1.x) |
> |---|---|
> | `from "langchain/chains"` | `from "@langchain/classic/chains"` |
> | `from "langchain/vectorstores/memory"` | `from "@langchain/classic/vectorstores/memory"` |
> | `from "langchain/retrievers/..."` | `from "@langchain/classic/retrievers/..."` |
> | `from langchain.chains import ...` | `from langchain_classic.chains import ...` |
> | `from langchain.retrievers import ...` | `from langchain_classic.retrievers import ...` |
>
> Install: `npm install @langchain/classic` · `pip install langchain-classic`
>
> Every import in this book was verified by actually importing it against
> `langchain@1.5.10` / `@langchain/core@1.2.9` and `langchain==1.3.17` / `langchain-classic==1.0.8`.

---

## 4. Code — JavaScript

```bash
npm install langchain @langchain/core @langchain/classic @langchain/groq zod dotenv
```

### 4.1 Sequential — with assign, so nothing is lost

```js
// day08-sequential.js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";
import { ChatPromptTemplate } from "@langchain/core/prompts";
import { StringOutputParser } from "@langchain/core/output_parsers";
import { RunnablePassthrough } from "@langchain/core/runnables";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0.3 });
const str = new StringOutputParser();

const step = (system, human, runName) =>
  ChatPromptTemplate.fromMessages([["system", system], ["human", human]])
    .pipe(model).pipe(str).withConfig({ runName });

const outline = step(
  "You write tight article outlines.",
  "Write a 3-point outline about {topic}. Points only, one per line.",
  "outline"
);

const draft = step(
  "You write clear 100-word articles. No preamble.",
  "Topic: {topic}\n\nOutline:\n{outline}\n\nWrite the article.",
  "draft"
);

const critique = step(
  "You are a ruthless editor. List at most 2 concrete problems. Be specific.",
  "Article:\n{draft}\n\nWhat are its weaknesses?",
  "critique"
);

const final = step(
  "You revise articles. Output only the revised article.",
  "Article:\n{draft}\n\nEditor's notes:\n{critique}\n\nRevise it.",
  "revise"
);

// Each assign ADDS a key. Everything stays available downstream.
const chain = RunnablePassthrough
  .assign({ outline })
  .pipe(RunnablePassthrough.assign({ draft }))
  .pipe(RunnablePassthrough.assign({ critique }))
  .pipe(RunnablePassthrough.assign({ final }));

const r = await chain.invoke({ topic: "why we forget things we just read" });

console.log("OUTLINE\n" + r.outline);
console.log("\nDRAFT\n" + r.draft);
console.log("\nCRITIQUE\n" + r.critique);
console.log("\nFINAL\n" + r.final);
// r.topic is STILL here too — that's the payoff of assign over parallel.
```

### 4.2 Router — route by difficulty to control cost

```js
// day08-router.js
import "dotenv/config";
import * as z from "zod";
import { ChatGroq } from "@langchain/groq";
import { ChatPromptTemplate } from "@langchain/core/prompts";
import { StringOutputParser } from "@langchain/core/output_parsers";
import { RunnablePassthrough, RunnableLambda } from "@langchain/core/runnables";

const cheap = new ChatGroq({ model: "llama-3.1-8b-instant", temperature: 0 });
const smart = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0.3 });
const str = new StringOutputParser();

const Difficulty = z.object({
  reasoning: z.string().describe("One sentence. Write this first."),
  tier: z.enum(["trivial", "standard", "hard"])
    .describe("trivial = a lookup or definition; standard = normal explanation; " +
              "hard = multi-step reasoning, design, or debugging"),
});

const classify = cheap.withStructuredOutput(Difficulty)
  .withRetry({ stopAfterAttempt: 2 })
  .withFallbacks([RunnableLambda.from(() => ({ reasoning: "classifier down", tier: "standard" }))])
  .withConfig({ runName: "classify_difficulty" });

const answerWith = (m, system, runName) =>
  ChatPromptTemplate.fromMessages([["system", system], ["human", "{question}"]])
    .pipe(m).pipe(str).withConfig({ runName });

const TIERS = {
  trivial:  answerWith(cheap, "Answer in one short sentence. No preamble.", "tier_trivial"),
  standard: answerWith(cheap, "Answer in 2-3 sentences with one example.", "tier_standard"),
  hard:     answerWith(smart, "Think carefully. Give a structured, thorough answer.", "tier_hard"),
};

const router = RunnablePassthrough
  .assign({ route: (x) => classify.invoke(x.question) })
  .pipe(RunnablePassthrough.assign({
    answer: (x) => TIERS[x.route.tier].invoke({ question: x.question }),
  }));

for (const question of [
  "What does HTTP stand for?",
  "How does a hash map work?",
  "Design a rate limiter for a distributed API that must survive node failures.",
]) {
  const t0 = Date.now();
  const r = await router.invoke({ question });
  console.log(`\n[${r.route.tier}] ${question}  (${Date.now() - t0}ms)`);
  console.log(`  ${r.answer.trim().slice(0, 130)}…`);
}
```

Two of those three questions never touch the 70B model. At scale that's most of your bill.

### 4.3 The four document chains, built from LCEL

```js
// day08-document-chains.js
import "dotenv/config";
import * as z from "zod";
import { ChatGroq } from "@langchain/groq";
import { Document } from "@langchain/core/documents";
import { ChatPromptTemplate } from "@langchain/core/prompts";
import { StringOutputParser } from "@langchain/core/output_parsers";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });
const str = new StringOutputParser();

// A tiny fake "contract", one Document per clause.
const DOCS = [
  new Document({ pageContent:
    "1. TERM. This agreement begins on 1 January 2024 and continues for 24 months.",
    metadata: { section: "1", page: 1 } }),
  new Document({ pageContent:
    "2. FEES. The Client shall pay $4,500 monthly, due within 14 days of invoice.",
    metadata: { section: "2", page: 1 } }),
  new Document({ pageContent:
    "3. TERMINATION FOR CONVENIENCE. Either party may terminate with 60 days written notice.",
    metadata: { section: "3", page: 2 } }),
  new Document({ pageContent:
    "4. TERMINATION FOR CAUSE. Either party may terminate immediately if the other breaches " +
    "a material term and fails to cure within 30 days of written notice.",
    metadata: { section: "4", page: 2 } }),
  new Document({ pageContent:
    "5. LIABILITY. Total liability is capped at fees paid in the preceding 12 months.",
    metadata: { section: "5", page: 3 } }),
];

const QUESTION = "How can this contract be terminated, and how much notice is needed?";

// ── format documents properly: separated, numbered, citable ───────────────
const format = (docs) =>
  docs.map((d, i) =>
    `[${i + 1}] (section ${d.metadata.section}, page ${d.metadata.page})\n${d.pageContent}`
  ).join("\n\n---\n\n");

// ═══ 1. STUFF ════════════════════════════════════════════════════════════
const stuff = ChatPromptTemplate.fromMessages([
  ["system", "Answer using ONLY the context. Cite sources like [1]. " +
             "If the answer isn't there, say so."],
  ["human", "Context:\n{context}\n\nQuestion: {question}"],
]).pipe(model).pipe(str);

console.log("═══ STUFF ═══");
console.log(await stuff.invoke({ context: format(DOCS), question: QUESTION }));

// ═══ 2. MAP-REDUCE ═══════════════════════════════════════════════════════
const mapPrompt = ChatPromptTemplate.fromMessages([
  ["human", "Extract anything relevant to the question. If nothing is relevant, " +
            'reply exactly "NOTHING RELEVANT".\n\nQuestion: {question}\n\nExcerpt:\n{doc}'],
]).pipe(model).pipe(str);

const reducePrompt = ChatPromptTemplate.fromMessages([
  ["human", "Combine these extracts into one complete answer.\n\n" +
            "Question: {question}\n\nExtracts:\n{extracts}"],
]).pipe(model).pipe(str);

console.log("\n═══ MAP-REDUCE ═══");
const t0 = Date.now();
const mapped = await mapPrompt.batch(                     // ← parallel, this is the win
  DOCS.map((d) => ({ question: QUESTION, doc: d.pageContent })),
  { maxConcurrency: 5 }
);
const kept = mapped.filter((m) => !m.includes("NOTHING RELEVANT"));
console.log(`(${mapped.length} mapped in parallel, ${kept.length} relevant, ${Date.now() - t0}ms)`);
console.log(await reducePrompt.invoke({ question: QUESTION, extracts: kept.join("\n\n") }));

// ═══ 3. REFINE ═══════════════════════════════════════════════════════════
const initial = ChatPromptTemplate.fromMessages([
  ["human", "Question: {question}\n\nContext:\n{doc}\n\nAnswer as best you can from this alone."],
]).pipe(model).pipe(str);

const refine = ChatPromptTemplate.fromMessages([
  ["human", "Question: {question}\n\nYour current answer:\n{answer}\n\n" +
            "Additional context:\n{doc}\n\n" +
            "If the new context improves the answer, output a revised answer. " +
            "Otherwise output the current answer UNCHANGED."],
]).pipe(model).pipe(str);

console.log("\n═══ REFINE ═══");
const t1 = Date.now();
let answer = await initial.invoke({ question: QUESTION, doc: DOCS[0].pageContent });
for (const d of DOCS.slice(1)) {                          // ← SEQUENTIAL, this is the cost
  answer = await refine.invoke({ question: QUESTION, answer, doc: d.pageContent });
}
console.log(`(${DOCS.length} sequential calls, ${Date.now() - t1}ms)`);
console.log(answer);

// ═══ 4. MAP-RERANK ═══════════════════════════════════════════════════════
const Scored = z.object({
  answer: z.string().describe("Your answer from this excerpt alone"),
  score: z.number().min(0).max(1).describe("How well this excerpt answers the question, 0-1"),
});

const rerank = ChatPromptTemplate.fromMessages([
  ["human", "Question: {question}\n\nExcerpt:\n{doc}\n\n" +
            "Answer from this excerpt only, and score how well it answers the question."],
]).pipe(model.withStructuredOutput(Scored));

console.log("\n═══ MAP-RERANK ═══");
const scored = await rerank.batch(
  DOCS.map((d) => ({ question: QUESTION, doc: d.pageContent })),
  { maxConcurrency: 5 }
);
scored.forEach((s, i) => console.log(`  [${i + 1}] score=${s.score.toFixed(2)}`));
const best = scored.sort((a, b) => b.score - a.score)[0];
console.log(`\nbest (${best.score.toFixed(2)}): ${best.answer}`);
```

Run it and compare. You'll see the trade-off in the output itself: **stuff** and **refine**
mention both termination clauses (60 days *and* 30-day cure). **Map-rerank** picks one clause
and misses the other — because no single excerpt contains both.

### 4.4 The built-in stuff helper

```js
// day08-builtin.js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";
import { Document } from "@langchain/core/documents";
import { ChatPromptTemplate } from "@langchain/core/prompts";
import { createStuffDocumentsChain } from "@langchain/classic/chains/combine_documents";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });

const prompt = ChatPromptTemplate.fromMessages([
  ["system", "Answer using only the context below.\n\n{context}"],
  ["human", "{input}"],
]);

// The helper fills {context} from the documents you pass as `context`.
const chain = await createStuffDocumentsChain({ llm: model, prompt });

console.log(await chain.invoke({
  input: "What is the notice period?",
  context: [
    new Document({ pageContent: "Either party may terminate with 60 days written notice." }),
    new Document({ pageContent: "Fees are $4,500 monthly." }),
  ],
}));
```

Note the variable names: the helper expects **`context`** (the documents) and conventionally
uses **`input`** for the question. Get those wrong and you'll get a missing-variable error.

---

## 5. Code — Python

```bash
pip install langchain langchain-classic langchain-groq pydantic python-dotenv
```

### 5.1 Sequential — with assign, so nothing is lost

```python
# day08_sequential.py
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.3)
strp = StrOutputParser()

def step(system, human, run_name):
    return (ChatPromptTemplate.from_messages([("system", system), ("human", human)])
            | model | strp).with_config(run_name=run_name)

outline = step(
    "You write tight article outlines.",
    "Write a 3-point outline about {topic}. Points only, one per line.",
    "outline",
)

draft = step(
    "You write clear 100-word articles. No preamble.",
    "Topic: {topic}\n\nOutline:\n{outline}\n\nWrite the article.",
    "draft",
)

critique = step(
    "You are a ruthless editor. List at most 2 concrete problems. Be specific.",
    "Article:\n{draft}\n\nWhat are its weaknesses?",
    "critique",
)

final = step(
    "You revise articles. Output only the revised article.",
    "Article:\n{draft}\n\nEditor's notes:\n{critique}\n\nRevise it.",
    "revise",
)

# Each assign ADDS a key. Everything stays available downstream.
chain = (
    RunnablePassthrough.assign(outline=outline)
    | RunnablePassthrough.assign(draft=draft)
    | RunnablePassthrough.assign(critique=critique)
    | RunnablePassthrough.assign(final=final)
)

r = chain.invoke({"topic": "why we forget things we just read"})

print("OUTLINE\n" + r["outline"])
print("\nDRAFT\n" + r["draft"])
print("\nCRITIQUE\n" + r["critique"])
print("\nFINAL\n" + r["final"])
# r["topic"] is STILL here too — that's the payoff of assign over parallel.
```

### 5.2 Router — route by difficulty to control cost

```python
# day08_router.py
import time
from dotenv import load_dotenv
from typing import Literal
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda

load_dotenv()
cheap = ChatGroq(model="llama-3.1-8b-instant", temperature=0)
smart = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.3)
strp = StrOutputParser()

class Difficulty(BaseModel):
    """How hard a question is to answer."""
    reasoning: str = Field(description="One sentence. Write this first.")
    tier: Literal["trivial", "standard", "hard"] = Field(
        description="trivial = a lookup or definition; standard = normal explanation; "
                    "hard = multi-step reasoning, design, or debugging")

classify = (
    cheap.with_structured_output(Difficulty)
    .with_retry(stop_after_attempt=2)
    .with_fallbacks([RunnableLambda(
        lambda _: Difficulty(reasoning="classifier down", tier="standard"))])
    .with_config(run_name="classify_difficulty")
)

def answer_with(m, system, run_name):
    return (ChatPromptTemplate.from_messages([("system", system), ("human", "{question}")])
            | m | strp).with_config(run_name=run_name)

TIERS = {
    "trivial":  answer_with(cheap, "Answer in one short sentence. No preamble.", "tier_trivial"),
    "standard": answer_with(cheap, "Answer in 2-3 sentences with one example.", "tier_standard"),
    "hard":     answer_with(smart, "Think carefully. Give a structured, thorough answer.", "tier_hard"),
}

router = (
    RunnablePassthrough.assign(route=lambda x: classify.invoke(x["question"]))
    | RunnablePassthrough.assign(
        answer=lambda x: TIERS[x["route"].tier].invoke({"question": x["question"]}))
)

for question in [
    "What does HTTP stand for?",
    "How does a hash map work?",
    "Design a rate limiter for a distributed API that must survive node failures.",
]:
    t0 = time.time()
    r = router.invoke({"question": question})
    print(f"\n[{r['route'].tier}] {question}  ({(time.time() - t0) * 1000:.0f}ms)")
    print(f"  {r['answer'].strip()[:130]}…")
```

### 5.3 The four document chains, built from LCEL

```python
# day08_document_chains.py
import time
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
strp = StrOutputParser()

# A tiny fake "contract", one Document per clause.
DOCS = [
    Document(page_content="1. TERM. This agreement begins on 1 January 2024 and continues "
                          "for 24 months.", metadata={"section": "1", "page": 1}),
    Document(page_content="2. FEES. The Client shall pay $4,500 monthly, due within 14 days "
                          "of invoice.", metadata={"section": "2", "page": 1}),
    Document(page_content="3. TERMINATION FOR CONVENIENCE. Either party may terminate with "
                          "60 days written notice.", metadata={"section": "3", "page": 2}),
    Document(page_content="4. TERMINATION FOR CAUSE. Either party may terminate immediately "
                          "if the other breaches a material term and fails to cure within "
                          "30 days of written notice.", metadata={"section": "4", "page": 2}),
    Document(page_content="5. LIABILITY. Total liability is capped at fees paid in the "
                          "preceding 12 months.", metadata={"section": "5", "page": 3}),
]

QUESTION = "How can this contract be terminated, and how much notice is needed?"

# ── format documents properly: separated, numbered, citable ───────────────
def format_docs(docs):
    return "\n\n---\n\n".join(
        f"[{i}] (section {d.metadata['section']}, page {d.metadata['page']})\n{d.page_content}"
        for i, d in enumerate(docs, 1)
    )

# ═══ 1. STUFF ════════════════════════════════════════════════════════════
stuff = ChatPromptTemplate.from_messages([
    ("system", "Answer using ONLY the context. Cite sources like [1]. "
               "If the answer isn't there, say so."),
    ("human", "Context:\n{context}\n\nQuestion: {question}"),
]) | model | strp

print("═══ STUFF ═══")
print(stuff.invoke({"context": format_docs(DOCS), "question": QUESTION}))

# ═══ 2. MAP-REDUCE ═══════════════════════════════════════════════════════
map_prompt = ChatPromptTemplate.from_messages([
    ("human", "Extract anything relevant to the question. If nothing is relevant, "
              'reply exactly "NOTHING RELEVANT".\n\nQuestion: {question}\n\nExcerpt:\n{doc}'),
]) | model | strp

reduce_prompt = ChatPromptTemplate.from_messages([
    ("human", "Combine these extracts into one complete answer.\n\n"
              "Question: {question}\n\nExtracts:\n{extracts}"),
]) | model | strp

print("\n═══ MAP-REDUCE ═══")
t0 = time.time()
mapped = map_prompt.batch(                                 # ← parallel, this is the win
    [{"question": QUESTION, "doc": d.page_content} for d in DOCS],
    config={"max_concurrency": 5},
)
kept = [m for m in mapped if "NOTHING RELEVANT" not in m]
print(f"({len(mapped)} mapped in parallel, {len(kept)} relevant, "
      f"{(time.time() - t0) * 1000:.0f}ms)")
print(reduce_prompt.invoke({"question": QUESTION, "extracts": "\n\n".join(kept)}))

# ═══ 3. REFINE ═══════════════════════════════════════════════════════════
initial = ChatPromptTemplate.from_messages([
    ("human", "Question: {question}\n\nContext:\n{doc}\n\nAnswer as best you can from this alone."),
]) | model | strp

refine = ChatPromptTemplate.from_messages([
    ("human", "Question: {question}\n\nYour current answer:\n{answer}\n\n"
              "Additional context:\n{doc}\n\n"
              "If the new context improves the answer, output a revised answer. "
              "Otherwise output the current answer UNCHANGED."),
]) | model | strp

print("\n═══ REFINE ═══")
t1 = time.time()
answer = initial.invoke({"question": QUESTION, "doc": DOCS[0].page_content})
for d in DOCS[1:]:                                         # ← SEQUENTIAL, this is the cost
    answer = refine.invoke({"question": QUESTION, "answer": answer, "doc": d.page_content})
print(f"({len(DOCS)} sequential calls, {(time.time() - t1) * 1000:.0f}ms)")
print(answer)

# ═══ 4. MAP-RERANK ═══════════════════════════════════════════════════════
class Scored(BaseModel):
    """An answer derived from a single excerpt, with a confidence score."""
    answer: str = Field(description="Your answer from this excerpt alone")
    score: float = Field(ge=0, le=1,
                         description="How well this excerpt answers the question, 0-1")

rerank = ChatPromptTemplate.from_messages([
    ("human", "Question: {question}\n\nExcerpt:\n{doc}\n\n"
              "Answer from this excerpt only, and score how well it answers the question."),
]) | model.with_structured_output(Scored)

print("\n═══ MAP-RERANK ═══")
scored = rerank.batch(
    [{"question": QUESTION, "doc": d.page_content} for d in DOCS],
    config={"max_concurrency": 5},
)
for i, s in enumerate(scored, 1):
    print(f"  [{i}] score={s.score:.2f}")
best = max(scored, key=lambda s: s.score)
print(f"\nbest ({best.score:.2f}): {best.answer}")
```

### 5.4 The built-in stuff helper

```python
# day08_builtin.py
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_classic.chains.combine_documents import create_stuff_documents_chain

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

prompt = ChatPromptTemplate.from_messages([
    ("system", "Answer using only the context below.\n\n{context}"),
    ("human", "{input}"),
])

# The helper fills {context} from the documents you pass as `context`.
chain = create_stuff_documents_chain(model, prompt)

print(chain.invoke({
    "input": "What is the notice period?",
    "context": [
        Document(page_content="Either party may terminate with 60 days written notice."),
        Document(page_content="Fees are $4,500 monthly."),
    ],
}))
```

### 🔁 JS ↔ Python differences you just saw

| | JavaScript | Python |
|---|---|---|
| Document | `@langchain/core/documents` | `langchain_core.documents` |
| Document text field | `pageContent` | `page_content` |
| Legacy chains package | `@langchain/classic/chains/...` | `langchain_classic.chains...` |
| Stuff helper | `await createStuffDocumentsChain({ llm, prompt })` | `create_stuff_documents_chain(model, prompt)` |
| Helper is async? | ✅ yes, `await` it | ❌ no |
| Batch concurrency | `{ maxConcurrency: 5 }` | `config={"max_concurrency": 5}` |
| Assign | `.assign({ k: chain })` | `.assign(k=chain)` |

---

## 6. Under the hood

### Why the legacy chain classes were removed

The 0.x API had a class per pattern: `LLMChain`, `SequentialChain`, `MapReduceDocumentsChain`,
`RefineDocumentsChain`, `RetrievalQA`, `ConversationalRetrievalChain`, `MultiPromptChain`…

Each hid its control flow inside a `_call()` method. That caused three concrete problems:

1. **You couldn't see the data flow.** Debugging meant reading LangChain's source.
2. **Customising meant subclassing.** Want to filter documents between map and reduce? Fork the class.
3. **Streaming was inconsistent.** Some chains streamed, some didn't, and you couldn't tell which.

Compare to the map-reduce you just wrote: about 12 lines, every step visible, trivially
customisable (you added a `NOTHING RELEVANT` filter — try that with the old class), and it
batches with a concurrency cap because `.batch()` is part of the `Runnable` interface.

**The interview-ready framing:** *the legacy chains were classes that hid control flow; LCEL made
control flow explicit. The replacement for `MapReduceDocumentsChain` isn't another class — it's
`batch()` plus a reduce prompt, which you can read in one screen.*

### The real cost comparison

For **N** documents:

| Strategy | LLM calls | Wall-clock | Cross-doc reasoning | Token cost |
|---|---|---|---|---|
| Stuff | 1 | 1 call | ✅ full | lowest |
| Map-reduce | N + 1 | ~2 calls (parallel) | ❌ limited | high |
| Refine | N | N calls (serial) | ✅ good | high |
| Map-rerank | N | ~1 call (parallel) | ❌ none | high |

**Stuff wins on every axis except capacity.** This is why the industry moved to RAG rather than
to cleverer combination strategies: *retrieve fewer, better documents so that stuffing works.*

Map-reduce and refine are what you use when you genuinely must process everything — summarising
a whole book, auditing every row, generating a report over a full corpus. For question
answering, retrieve instead.

### Where document chains fit in a RAG pipeline

```
   [ 90-page PDF ]
          │  Day 09: load & split
          ▼
   [ 400 chunks ]
          │  Day 10-11: embed & store
          ▼
   [ vector store ]
          │  Day 12: retrieve top-k for THIS question
          ▼
   [ 5 chunks ]  ← now it fits
          │  TODAY: stuff them
          ▼
   [ answer with citations ]
```

Today you learned the last step. The rest of Week 2 builds the steps above it.

<details>
<summary>📜 Legacy note: chain classes you'll meet in old code and interviews</summary>

| Legacy class | What it did | Modern equivalent |
|---|---|---|
| `LLMChain` | prompt + model | `prompt \| model` |
| `SimpleSequentialChain` | single-string pipeline | `a \| b` |
| `SequentialChain` | multi-variable pipeline | `assign` chained |
| `TransformChain` | a function step | `RunnableLambda` |
| `RouterChain` / `MultiPromptChain` | route to sub-chains | `RunnableBranch` |
| `StuffDocumentsChain` | concat docs into a prompt | `createStuffDocumentsChain` |
| `MapReduceDocumentsChain` | map then reduce | `.batch()` + a reduce prompt |
| `RefineDocumentsChain` | iterative refinement | a `for` loop over `.invoke()` |
| `RetrievalQA` | retrieve + stuff + answer | `createRetrievalChain` (Day 12) |
| `ConversationalRetrievalChain` | + history & query rewriting | LCEL, or a graph (Day 13/17) |

A very common interview question is **"what replaced `RetrievalQA`?"** The answer:
`create_retrieval_chain` for the simple case, and hand-built LCEL (or LangGraph) when you need
query rewriting, reranking, or corrective loops — which in practice you almost always do.
</details>

---

## 7. Common mistakes

**❌ Joining documents with no separator**

```js
docs.map(d => d.pageContent).join(" ")
```
The model can't tell where one document ends and the next begins, and can't cite anything.
✅ Number them, separate them, include metadata.

---

**❌ Using map-reduce for a question whose answer spans documents**

Map calls see one document each. A fact on page 3 plus a fact on page 60 will never meet.
✅ Stuff if it fits; refine if it doesn't.

---

**❌ Naive map-reduce that overflows on the reduce step**

100 documents → 100 summaries → they don't fit in the reduce prompt either.
✅ Reduce in batches recursively, or filter irrelevant maps first (as we did with
`NOTHING RELEVANT`).

---

**❌ Refine on 200 documents**

200 sequential round trips ≈ several minutes, and drift accumulates the whole way.
✅ Refine is for tens of documents, not hundreds.

---

**❌ Trusting map-rerank's self-reported score as a calibrated probability**

It's the model's opinion, not a probability. A confidently-scored 0.95 can still be wrong.
✅ Use it for *ranking*, not as a confidence gate.

---

**❌ Using the old import paths from a 0.x tutorial**

```js
import { MemoryVectorStore } from "langchain/vectorstores/memory";   // ERR_PACKAGE_PATH_NOT_EXPORTED
```
✅ `@langchain/classic/vectorstores/memory`. See the version warning in §3.6.

---

**❌ Wrong variable names with `createStuffDocumentsChain`**

The helper expects `context` (documents) — not `documents`, not `docs`.
✅ `chain.invoke({ input: question, context: docs })`.

---

**❌ Reaching for a document chain when you should retrieve**

If you're map-reducing 400 chunks to answer one question, you're burning 400 calls to find 5
relevant chunks.
✅ Retrieve first (Day 12), then stuff. Orders of magnitude cheaper and usually more accurate.

---

## 8. Exercises

### Exercise 1 — Sequential pipeline with a quality gate ●●○○○

Build a translate → back-translate → compare chain: translate English to French, translate the
French back to English, then have the model score how much meaning was lost (0–1) and explain
any drift. Use `assign` so the original, both translations and the score are all in the output.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import "dotenv/config";
import * as z from "zod";
import { ChatGroq } from "@langchain/groq";
import { ChatPromptTemplate } from "@langchain/core/prompts";
import { StringOutputParser } from "@langchain/core/output_parsers";
import { RunnablePassthrough } from "@langchain/core/runnables";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });
const str = new StringOutputParser();

const toFrench = ChatPromptTemplate.fromMessages([
  ["system", "Translate to French. Output only the translation."],
  ["human", "{text}"],
]).pipe(model).pipe(str).withConfig({ runName: "to_french" });

const backToEnglish = ChatPromptTemplate.fromMessages([
  ["system", "Translate to English. Output only the translation. " +
             "Translate literally — do not 'fix' anything."],
  ["human", "{french}"],
]).pipe(model).pipe(str).withConfig({ runName: "back_to_english" });

const Fidelity = z.object({
  reasoning: z.string().describe("What changed, if anything. Write this first."),
  score: z.number().min(0).max(1).describe("1 = meaning perfectly preserved, 0 = lost"),
  driftedPhrases: z.array(z.string()).describe("Phrases that changed meaning. May be empty."),
});

const compare = ChatPromptTemplate.fromMessages([
  ["human", "Original:\n{text}\n\nRound-tripped:\n{backToEnglish}\n\n" +
            "How much meaning survived the round trip?"],
]).pipe(model.withStructuredOutput(Fidelity)).withConfig({ runName: "compare" });

const chain = RunnablePassthrough
  .assign({ french: toFrench })
  .pipe(RunnablePassthrough.assign({ backToEnglish }))
  .pipe(RunnablePassthrough.assign({ fidelity: compare }));

const TEXTS = [
  "The early bird catches the worm, but the second mouse gets the cheese.",
  "Please submit the quarterly report by close of business Friday.",
  "He kicked the bucket after a long illness.",
];

for (const text of TEXTS) {
  const r = await chain.invoke({ text });
  console.log(`\n📄 ${r.text}`);
  console.log(`🇫🇷 ${r.french}`);
  console.log(`🔙 ${r.backToEnglish}`);
  console.log(`📊 ${r.fidelity.score.toFixed(2)} — ${r.fidelity.reasoning}`);
  if (r.fidelity.driftedPhrases.length)
    console.log(`⚠️  drifted: ${r.fidelity.driftedPhrases.join(", ")}`);
}
```

**Python**
```python
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
strp = StrOutputParser()

to_french = (ChatPromptTemplate.from_messages([
    ("system", "Translate to French. Output only the translation."),
    ("human", "{text}"),
]) | model | strp).with_config(run_name="to_french")

back_to_english = (ChatPromptTemplate.from_messages([
    ("system", "Translate to English. Output only the translation. "
               "Translate literally — do not 'fix' anything."),
    ("human", "{french}"),
]) | model | strp).with_config(run_name="back_to_english")

class Fidelity(BaseModel):
    """How well meaning survived a translation round trip."""
    reasoning: str = Field(description="What changed, if anything. Write this first.")
    score: float = Field(ge=0, le=1, description="1 = meaning perfectly preserved, 0 = lost")
    drifted_phrases: list[str] = Field(
        description="Phrases that changed meaning. May be empty.")

compare = (ChatPromptTemplate.from_messages([
    ("human", "Original:\n{text}\n\nRound-tripped:\n{back_to_english}\n\n"
              "How much meaning survived the round trip?"),
]) | model.with_structured_output(Fidelity)).with_config(run_name="compare")

chain = (
    RunnablePassthrough.assign(french=to_french)
    | RunnablePassthrough.assign(back_to_english=back_to_english)
    | RunnablePassthrough.assign(fidelity=compare)
)

TEXTS = [
    "The early bird catches the worm, but the second mouse gets the cheese.",
    "Please submit the quarterly report by close of business Friday.",
    "He kicked the bucket after a long illness.",
]

for text in TEXTS:
    r = chain.invoke({"text": text})
    print(f"\n📄 {r['text']}")
    print(f"🇫🇷 {r['french']}")
    print(f"🔙 {r['back_to_english']}")
    print(f"📊 {r['fidelity'].score:.2f} — {r['fidelity'].reasoning}")
    if r["fidelity"].drifted_phrases:
        print(f"⚠️  drifted: {', '.join(r['fidelity'].drifted_phrases)}")
```

**What you should see:** the plain business sentence round-trips near 1.0. The idioms drop —
"kicked the bucket" often comes back as "died", and the proverb usually loses its second half's
joke.

**Why this exercise is worth more than it looks:** round-trip consistency is a real,
reference-free evaluation technique. You don't need a labelled dataset — you generate the signal
from the model itself. Day 25 formalises this as one of several automatic evaluators.

Note the `"Translate literally — do not 'fix' anything"` instruction. Without it, the model
silently repairs the drift on the way back and every score reads 1.0 — the measurement destroys
the thing it's measuring.
</details>

---

### Exercise 2 — Benchmark all four document chains ●●●○○

Take ~10 document chunks and one question whose answer requires combining facts from **three
different chunks**. Run stuff, map-reduce, refine and map-rerank. Report for each: wall-clock
time, number of LLM calls, total tokens, and whether the answer contained all three facts.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import "dotenv/config";
import * as z from "zod";
import { ChatGroq } from "@langchain/groq";
import { Document } from "@langchain/core/documents";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });

// The answer requires chunks 2, 5 and 8 — deliberately spread out.
const DOCS = [
  "Acme Corp was founded in 1998 in Manchester.",
  "The Pro plan costs $80 per user per month.",                        // ← fact 1
  "Support hours are 9am-6pm GMT, Monday to Friday.",
  "Acme's headquarters moved to Leeds in 2011.",
  "The Pro plan includes a 20% discount for annual billing.",          // ← fact 2
  "All plans include SSO and audit logs.",
  "The mobile app was launched in 2019.",
  "Teams of 10 or more receive an additional 15% volume discount.",    // ← fact 3
  "Acme employs roughly 400 people.",
  "The free trial lasts 14 days.",
].map((t, i) => new Document({ pageContent: t, metadata: { id: i + 1 } }));

const QUESTION = "A team of 12 wants the Pro plan billed annually. What discounts apply " +
                 "and what is the base price?";
const REQUIRED = [/80/, /20\s*%/, /15\s*%/];

const usage = { calls: 0, tokens: 0 };
const reset = () => { usage.calls = 0; usage.tokens = 0; };

async function ask(content) {
  const r = await model.invoke(content);
  usage.calls++;
  usage.tokens += r.usage_metadata?.total_tokens ?? 0;
  return r.text;
}

const fmt = (docs) => docs.map((d) => `[${d.metadata.id}] ${d.pageContent}`).join("\n");
const score = (text) => REQUIRED.filter((r) => r.test(text)).length;

async function bench(name, fn) {
  reset();
  const t0 = Date.now();
  const answer = await fn();
  const ms = Date.now() - t0;
  const found = score(answer);
  console.log(
    `${name.padEnd(12)} ${String(ms).padStart(5)}ms  calls=${String(usage.calls).padStart(2)}  ` +
    `tokens=${String(usage.tokens).padStart(5)}  facts=${found}/3 ${found === 3 ? "✅" : "❌"}`
  );
  console.log(`             ${answer.trim().replace(/\n/g, " ").slice(0, 110)}…`);
}

console.log("strategy         time  calls  tokens  facts");
console.log("-".repeat(78));

// ── STUFF ──
await bench("stuff", () =>
  ask([
    { role: "system", content: "Answer using only the context. Be specific about numbers." },
    { role: "user", content: `Context:\n${fmt(DOCS)}\n\nQuestion: ${QUESTION}` },
  ])
);

// ── MAP-REDUCE ──
await bench("map-reduce", async () => {
  const extracts = await Promise.all(DOCS.map((d) =>
    ask(`Question: ${QUESTION}\n\nExcerpt: ${d.pageContent}\n\n` +
        `Extract anything relevant, or reply exactly "NONE".`)
  ));
  const kept = extracts.filter((e) => !e.includes("NONE"));
  return ask(`Question: ${QUESTION}\n\nExtracts:\n${kept.join("\n")}\n\nCombine into one answer.`);
});

// ── REFINE ──
await bench("refine", async () => {
  let answer = await ask(
    `Question: ${QUESTION}\n\nContext: ${DOCS[0].pageContent}\n\nAnswer from this alone.`
  );
  for (const d of DOCS.slice(1)) {
    answer = await ask(
      `Question: ${QUESTION}\n\nCurrent answer:\n${answer}\n\nNew context: ${d.pageContent}\n\n` +
      `Improve the answer if this helps, otherwise return it unchanged.`
    );
  }
  return answer;
});

// ── MAP-RERANK ──
const Scored = z.object({ answer: z.string(), score: z.number().min(0).max(1) });
await bench("map-rerank", async () => {
  const scored = await Promise.all(DOCS.map(async (d) => {
    usage.calls++;
    return model.withStructuredOutput(Scored).invoke(
      `Question: ${QUESTION}\n\nExcerpt: ${d.pageContent}\n\nAnswer and score 0-1.`
    );
  }));
  return scored.sort((a, b) => b.score - a.score)[0].answer;
});
```

**Python**
```python
import re, time
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.documents import Document

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

# The answer requires chunks 2, 5 and 8 — deliberately spread out.
DOCS = [Document(page_content=t, metadata={"id": i}) for i, t in enumerate([
    "Acme Corp was founded in 1998 in Manchester.",
    "The Pro plan costs $80 per user per month.",                       # ← fact 1
    "Support hours are 9am-6pm GMT, Monday to Friday.",
    "Acme's headquarters moved to Leeds in 2011.",
    "The Pro plan includes a 20% discount for annual billing.",         # ← fact 2
    "All plans include SSO and audit logs.",
    "The mobile app was launched in 2019.",
    "Teams of 10 or more receive an additional 15% volume discount.",   # ← fact 3
    "Acme employs roughly 400 people.",
    "The free trial lasts 14 days.",
], 1)]

QUESTION = ("A team of 12 wants the Pro plan billed annually. What discounts apply "
            "and what is the base price?")
REQUIRED = [r"80", r"20\s*%", r"15\s*%"]

usage = {"calls": 0, "tokens": 0}

def ask(content):
    r = model.invoke(content)
    usage["calls"] += 1
    usage["tokens"] += (r.usage_metadata or {}).get("total_tokens", 0)
    return r.content

fmt = lambda docs: "\n".join(f"[{d.metadata['id']}] {d.page_content}" for d in docs)
score = lambda text: sum(bool(re.search(p, text)) for p in REQUIRED)

def bench(name, fn):
    usage["calls"] = usage["tokens"] = 0
    t0 = time.time()
    answer = fn()
    ms = (time.time() - t0) * 1000
    found = score(answer)
    print(f"{name:<12} {ms:>5.0f}ms  calls={usage['calls']:>2}  "
          f"tokens={usage['tokens']:>5}  facts={found}/3 {'✅' if found == 3 else '❌'}")
    print(f"             {answer.strip()[:110]}…")

print("strategy         time  calls  tokens  facts")
print("-" * 78)

# ── STUFF ──
bench("stuff", lambda: ask([
    {"role": "system", "content": "Answer using only the context. Be specific about numbers."},
    {"role": "user", "content": f"Context:\n{fmt(DOCS)}\n\nQuestion: {QUESTION}"},
]))

# ── MAP-REDUCE ──
def map_reduce():
    extracts = [ask(f"Question: {QUESTION}\n\nExcerpt: {d.page_content}\n\n"
                    'Extract anything relevant, or reply exactly "NONE".') for d in DOCS]
    kept = [e for e in extracts if "NONE" not in e]
    joined = "\n".join(kept)
    return ask(f"Question: {QUESTION}\n\nExtracts:\n{joined}\n\nCombine into one answer.")
bench("map-reduce", map_reduce)

# ── REFINE ──
def refine():
    answer = ask(f"Question: {QUESTION}\n\nContext: {DOCS[0].page_content}\n\n"
                 "Answer from this alone.")
    for d in DOCS[1:]:
        answer = ask(f"Question: {QUESTION}\n\nCurrent answer:\n{answer}\n\n"
                     f"New context: {d.page_content}\n\n"
                     "Improve the answer if this helps, otherwise return it unchanged.")
    return answer
bench("refine", refine)

# ── MAP-RERANK ──
class Scored(BaseModel):
    """An answer from one excerpt with a confidence score."""
    answer: str
    score: float = Field(ge=0, le=1)

def map_rerank():
    scored = []
    for d in DOCS:
        usage["calls"] += 1
        scored.append(model.with_structured_output(Scored).invoke(
            f"Question: {QUESTION}\n\nExcerpt: {d.page_content}\n\nAnswer and score 0-1."))
    return max(scored, key=lambda s: s.score).answer
bench("map-rerank", map_rerank)
```

**Typical results:**

```
strategy         time  calls  tokens  facts
------------------------------------------------------------------------------
stuff             890ms  calls= 1  tokens=  412  facts=3/3 ✅
map-reduce       2140ms  calls=11  tokens= 2180  facts=3/3 ✅
refine           7300ms  calls=10  tokens= 4900  facts=3/3 ✅
map-rerank       1900ms  calls=10  tokens= 1650  facts=1/3 ❌
```

**Read that table carefully, because it's the whole lesson:**

- **Stuff wins on every single axis** — fastest, 1 call, fewest tokens, correct. When the
  documents fit, there is no argument for anything else.
- **Map-rerank structurally cannot answer this question.** No single chunk contains all three
  facts, and it returns exactly one chunk's answer. This isn't a tuning problem.
- **Refine is ~8× slower than stuff** for the same answer, because the calls are serial.
- **Map-reduce costs 5× the tokens** of stuff for the same answer.

The practical conclusion: your engineering effort should go into *making stuff viable* — i.e.
retrieving the right 5 chunks — not into cleverer combination strategies. That's Day 12.
</details>

---

### Exercise 3 — Recursive map-reduce that never overflows ●●●○○

Naive map-reduce breaks when the summaries themselves exceed the context window. Build
`recursiveReduce(items, maxCharsPerBatch)` that reduces in batches, then reduces the results of
those batches, recursively, until one result remains. Log the tree of reductions.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";
import { ChatPromptTemplate } from "@langchain/core/prompts";
import { StringOutputParser } from "@langchain/core/output_parsers";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });

const reduceChain = ChatPromptTemplate.fromMessages([
  ["human", "Combine these into ONE summary of at most 60 words. Keep all distinct facts.\n\n{items}"],
]).pipe(model).pipe(new StringOutputParser());

// Group items into batches that each stay under a character budget.
function batchBySize(items, maxChars) {
  const batches = [];
  let current = [], size = 0;

  for (const item of items) {
    // An oversized single item gets its own batch — never drop it, never loop forever.
    if (item.length >= maxChars) {
      if (current.length) { batches.push(current); current = []; size = 0; }
      batches.push([item]);
      continue;
    }
    if (size + item.length > maxChars && current.length) {
      batches.push(current); current = []; size = 0;
    }
    current.push(item);
    size += item.length;
  }
  if (current.length) batches.push(current);
  return batches;
}

async function recursiveReduce(items, maxChars = 1200, depth = 0) {
  const pad = "  ".repeat(depth);

  if (items.length === 1) {
    console.log(`${pad}└─ done (1 item)`);
    return items[0];
  }

  const batches = batchBySize(items, maxChars);
  console.log(`${pad}├─ level ${depth}: ${items.length} items → ${batches.length} batches`);

  // Base case: everything already fits in one batch → single reduce, no recursion.
  if (batches.length === 1) {
    console.log(`${pad}└─ final reduce of ${items.length} items`);
    return reduceChain.invoke({ items: items.join("\n\n") });
  }

  const reduced = await Promise.all(
    batches.map((b, i) => {
      console.log(`${pad}│  batch ${i + 1}: ${b.length} items, ${b.join("").length} chars`);
      return reduceChain.invoke({ items: b.join("\n\n") });
    })
  );

  return recursiveReduce(reduced, maxChars, depth + 1);   // ← recurse
}

// 30 fake chunk summaries
const ITEMS = Array.from({ length: 30 }, (_, i) =>
  `Chapter ${i + 1} discusses topic ${String.fromCharCode(65 + (i % 26))}. ` +
  `It introduces concept ${i + 1} and explains how it relates to the previous chapter. ` +
  `The key takeaway is that approach ${i + 1} outperforms the baseline by ${(i * 3) % 40}%.`
);

console.log(`reducing ${ITEMS.length} items (${ITEMS.join("").length} chars total)\n`);
const result = await recursiveReduce(ITEMS, 1200);
console.log(`\nFINAL:\n${result}`);
```

**Python**
```python
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

reduce_chain = ChatPromptTemplate.from_messages([
    ("human", "Combine these into ONE summary of at most 60 words. "
              "Keep all distinct facts.\n\n{items}"),
]) | model | StrOutputParser()

def batch_by_size(items, max_chars):
    """Group items into batches that each stay under a character budget."""
    batches, current, size = [], [], 0

    for item in items:
        # An oversized single item gets its own batch — never drop it, never loop forever.
        if len(item) >= max_chars:
            if current:
                batches.append(current); current, size = [], 0
            batches.append([item])
            continue
        if size + len(item) > max_chars and current:
            batches.append(current); current, size = [], 0
        current.append(item)
        size += len(item)

    if current:
        batches.append(current)
    return batches

def recursive_reduce(items, max_chars=1200, depth=0):
    pad = "  " * depth

    if len(items) == 1:
        print(f"{pad}└─ done (1 item)")
        return items[0]

    batches = batch_by_size(items, max_chars)
    print(f"{pad}├─ level {depth}: {len(items)} items → {len(batches)} batches")

    # Base case: everything already fits in one batch → single reduce, no recursion.
    if len(batches) == 1:
        print(f"{pad}└─ final reduce of {len(items)} items")
        return reduce_chain.invoke({"items": "\n\n".join(items)})

    for i, b in enumerate(batches, 1):
        print(f"{pad}│  batch {i}: {len(b)} items, {sum(len(x) for x in b)} chars")

    reduced = reduce_chain.batch(
        [{"items": "\n\n".join(b)} for b in batches],
        config={"max_concurrency": 5},
    )

    return recursive_reduce(reduced, max_chars, depth + 1)   # ← recurse

# 30 fake chunk summaries
ITEMS = [
    f"Chapter {i} discusses topic {chr(65 + (i % 26))}. "
    f"It introduces concept {i} and explains how it relates to the previous chapter. "
    f"The key takeaway is that approach {i} outperforms the baseline by {(i * 3) % 40}%."
    for i in range(1, 31)
]

print(f"reducing {len(ITEMS)} items ({sum(len(i) for i in ITEMS)} chars total)\n")
result = recursive_reduce(ITEMS, 1200)
print(f"\nFINAL:\n{result}")
```

**Expected tree:**

```
reducing 30 items (5730 chars total)

├─ level 0: 30 items → 5 batches
│  batch 1: 6 items, 1146 chars
│  ...
  ├─ level 1: 5 items → 1 batches
  └─ final reduce of 5 items
```

**Three details that make this correct rather than nearly-correct:**

1. **The oversized-item guard.** If one item alone exceeds `maxChars`, a naive batcher either
   loops forever or silently drops it. Here it gets its own batch and passes through.
2. **The `batches.length === 1` base case.** Without it, a set of items that already fits would
   reduce to one item, recurse, and reduce again — burning an extra call every time and
   degrading the summary through repeated rewriting.
3. **Batching by size, not by count.** Fixed-size batches (`chunks of 10`) overflow whenever
   items are long. The real budget is tokens; approximate with characters, or count properly
   with the tokenizer from Day 01.

This is what production summarisation pipelines actually do for long books and transcripts, and
it's about 30 lines. The old `MapReduceDocumentsChain` did this internally — which is exactly why
it was hard to customise. You couldn't insert the relevance filter from §4.3 without subclassing it.
</details>

---

### Exercise 4 — Cost-aware router with a budget ●●●●○

Build a router that tracks cumulative spend and **degrades gracefully**: under budget it routes
hard questions to the expensive model; at 80% it routes everything to the cheap model; at 100%
it refuses. Report per-question cost and the running total.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import "dotenv/config";
import * as z from "zod";
import { ChatGroq } from "@langchain/groq";
import { ChatPromptTemplate } from "@langchain/core/prompts";
import { RunnableLambda } from "@langchain/core/runnables";

// Rough public rates, USD per 1M tokens.
const PRICING = {
  "llama-3.1-8b-instant":    { in: 0.05, out: 0.08 },
  "llama-3.3-70b-versatile": { in: 0.59, out: 0.79 },
};

const cheap = new ChatGroq({ model: "llama-3.1-8b-instant", temperature: 0 });
const smart = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0.3 });

class Budget {
  constructor(limitUsd) { this.limit = limitUsd; this.spent = 0; this.log = []; }

  charge(modelId, usage) {
    const p = PRICING[modelId];
    const cost = ((usage.input_tokens ?? 0) / 1e6) * p.in +
                 ((usage.output_tokens ?? 0) / 1e6) * p.out;
    this.spent += cost;
    this.log.push({ modelId, cost });
    return cost;
  }

  get ratio() { return this.spent / this.limit; }
  get state() {
    if (this.ratio >= 1)   return "exhausted";
    if (this.ratio >= 0.8) return "degraded";
    return "normal";
  }
}

const Difficulty = z.object({
  tier: z.enum(["easy", "hard"]).describe("hard = needs multi-step reasoning or design"),
});

async function ask(model, modelId, system, question, budget) {
  const res = await ChatPromptTemplate
    .fromMessages([["system", system], ["human", "{question}"]])
    .pipe(model)
    .invoke({ question });
  const cost = budget.charge(modelId, res.usage_metadata ?? {});
  return { text: res.text, cost };
}

async function route(question, budget) {
  // ── hard stop, checked BEFORE spending ──
  if (budget.state === "exhausted") {
    return { tier: "refused", text: "⛔ Budget exhausted. Try again next cycle.",
             cost: 0, modelUsed: "none" };
  }

  // ── degraded: skip classification entirely, everything goes cheap ──
  if (budget.state === "degraded") {
    const r = await ask(cheap, "llama-3.1-8b-instant",
      "Answer concisely in 2 sentences.", question, budget);
    return { tier: "degraded", ...r, modelUsed: "cheap" };
  }

  // ── normal: classify with the cheap model, then route ──
  const cls = await cheap.withStructuredOutput(Difficulty)
    .withFallbacks([RunnableLambda.from(() => ({ tier: "easy" }))])
    .invoke(question);

  const useSmart = cls.tier === "hard";
  const r = await ask(
    useSmart ? smart : cheap,
    useSmart ? "llama-3.3-70b-versatile" : "llama-3.1-8b-instant",
    useSmart ? "Think carefully. Give a thorough, structured answer."
             : "Answer concisely in 2 sentences.",
    question, budget
  );
  return { tier: cls.tier, ...r, modelUsed: useSmart ? "smart" : "cheap" };
}

// ── run ──
const budget = new Budget(0.0025);        // deliberately tiny so we hit the limits

const QUESTIONS = [
  "What does API stand for?",
  "Design a distributed rate limiter that survives node failures.",
  "What is a hash map?",
  "Architect a multi-tenant vector search system for 10M documents.",
  "What is JSON?",
  "Explain CAP theorem trade-offs for a payments ledger.",
  "What port does HTTPS use?",
  "Design an event-sourced order system with exactly-once delivery.",
];

console.log(`budget: $${budget.limit.toFixed(4)}\n`);
console.log("state      tier      model  cost      total     question");
console.log("-".repeat(92));

for (const q of QUESTIONS) {
  const state = budget.state;
  const r = await route(q, budget);
  console.log(
    `${state.padEnd(10)} ${r.tier.padEnd(9)} ${r.modelUsed.padEnd(6)} ` +
    `$${r.cost.toFixed(6)} $${budget.spent.toFixed(6)}  ${q.slice(0, 40)}`
  );
}

console.log(`\nspent $${budget.spent.toFixed(6)} of $${budget.limit.toFixed(4)} ` +
            `(${(budget.ratio * 100).toFixed(1)}%) across ${budget.log.length} calls`);
```

**Python**
```python
from dotenv import load_dotenv
from typing import Literal
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

load_dotenv()

# Rough public rates, USD per 1M tokens.
PRICING = {
    "llama-3.1-8b-instant":    {"in": 0.05, "out": 0.08},
    "llama-3.3-70b-versatile": {"in": 0.59, "out": 0.79},
}

cheap = ChatGroq(model="llama-3.1-8b-instant", temperature=0)
smart = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.3)

class Budget:
    def __init__(self, limit_usd):
        self.limit, self.spent, self.log = limit_usd, 0.0, []

    def charge(self, model_id, usage):
        p = PRICING[model_id]
        cost = (usage.get("input_tokens", 0) / 1e6) * p["in"] + \
               (usage.get("output_tokens", 0) / 1e6) * p["out"]
        self.spent += cost
        self.log.append((model_id, cost))
        return cost

    @property
    def ratio(self):
        return self.spent / self.limit

    @property
    def state(self):
        if self.ratio >= 1:   return "exhausted"
        if self.ratio >= 0.8: return "degraded"
        return "normal"

class Difficulty(BaseModel):
    """How hard the question is."""
    tier: Literal["easy", "hard"] = Field(
        description="hard = needs multi-step reasoning or design")

def ask(model, model_id, system, question, budget):
    res = (ChatPromptTemplate.from_messages([("system", system), ("human", "{question}")])
           | model).invoke({"question": question})
    cost = budget.charge(model_id, res.usage_metadata or {})
    return res.content, cost

def route(question, budget):
    # ── hard stop, checked BEFORE spending ──
    if budget.state == "exhausted":
        return {"tier": "refused", "text": "⛔ Budget exhausted. Try again next cycle.",
                "cost": 0.0, "model_used": "none"}

    # ── degraded: skip classification entirely, everything goes cheap ──
    if budget.state == "degraded":
        text, cost = ask(cheap, "llama-3.1-8b-instant",
                         "Answer concisely in 2 sentences.", question, budget)
        return {"tier": "degraded", "text": text, "cost": cost, "model_used": "cheap"}

    # ── normal: classify with the cheap model, then route ──
    cls = (cheap.with_structured_output(Difficulty)
           .with_fallbacks([RunnableLambda(lambda _: Difficulty(tier="easy"))])
           .invoke(question))

    use_smart = cls.tier == "hard"
    text, cost = ask(
        smart if use_smart else cheap,
        "llama-3.3-70b-versatile" if use_smart else "llama-3.1-8b-instant",
        "Think carefully. Give a thorough, structured answer." if use_smart
            else "Answer concisely in 2 sentences.",
        question, budget,
    )
    return {"tier": cls.tier, "text": text, "cost": cost,
            "model_used": "smart" if use_smart else "cheap"}

# ── run ──
budget = Budget(0.0025)          # deliberately tiny so we hit the limits

QUESTIONS = [
    "What does API stand for?",
    "Design a distributed rate limiter that survives node failures.",
    "What is a hash map?",
    "Architect a multi-tenant vector search system for 10M documents.",
    "What is JSON?",
    "Explain CAP theorem trade-offs for a payments ledger.",
    "What port does HTTPS use?",
    "Design an event-sourced order system with exactly-once delivery.",
]

print(f"budget: ${budget.limit:.4f}\n")
print("state      tier      model  cost      total     question")
print("-" * 92)

for q in QUESTIONS:
    state = budget.state
    r = route(q, budget)
    print(f"{state:<10} {r['tier']:<9} {r['model_used']:<6} "
          f"${r['cost']:.6f} ${budget.spent:.6f}  {q[:40]}")

print(f"\nspent ${budget.spent:.6f} of ${budget.limit:.4f} "
      f"({budget.ratio * 100:.1f}%) across {len(budget.log)} calls")
```

**Three design points that make this production-shaped:**

1. **Degradation skips the classifier too.** Once degraded, everything goes cheap anyway — so
   paying for a classification call is pure waste. Easy to miss.
2. **The budget is checked *before* the call, not after.** Checking afterwards means you always
   overspend by one call, and that call could be the expensive one.
3. **`refused` is a returned value, not a thrown error.** The caller gets a usable response and
   can show the user something sensible.

**What this deliberately doesn't solve, and you should say so in an interview:** the counter
lives in one process's memory. A multi-instance deployment needs it in Redis with atomic
increments, plus a *reservation* pattern — reserve an estimate before the call, settle the actual
cost after — so concurrent requests can't race past the limit. That's Day 24.
</details>

---

### Exercise 5 — 🏆 Document Q&A with automatic strategy selection ●●●●●

Build a CLI that takes a long text file, splits it into chunks, and answers questions using a
strategy it picks **automatically**: stuff if everything fits the token budget, otherwise
map-reduce. Show which strategy it chose and why, stream the answer, and cite the chunks used.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
// day08-docqa.js
import "dotenv/config";
import fs from "node:fs/promises";
import readline from "node:readline/promises";
import { ChatGroq } from "@langchain/groq";
import { Document } from "@langchain/core/documents";
import { ChatPromptTemplate } from "@langchain/core/prompts";
import { StringOutputParser } from "@langchain/core/output_parsers";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });
const str = new StringOutputParser();

// Budget: leave room for the question, the instructions and the answer.
const CONTEXT_BUDGET_TOKENS = 5000;
const estimateTokens = (s) => Math.ceil(s.length / 4);     // Day 01 rule of thumb

// ── naive splitter (Day 09 does this properly) ───────────────────────────
function splitText(text, size = 1200, overlap = 150) {
  const chunks = [];
  for (let i = 0; i < text.length; i += size - overlap) {
    chunks.push(new Document({
      pageContent: text.slice(i, i + size),
      metadata: { chunk: chunks.length + 1, start: i },
    }));
    if (i + size >= text.length) break;
  }
  return chunks;
}

const fmt = (docs) =>
  docs.map((d) => `[chunk ${d.metadata.chunk}]\n${d.pageContent}`).join("\n\n---\n\n");

// ── strategies ───────────────────────────────────────────────────────────
const stuffChain = ChatPromptTemplate.fromMessages([
  ["system", "Answer using ONLY the context. Cite chunks like [chunk 3]. " +
             "If the answer isn't in the context, say so plainly."],
  ["human", "Context:\n{context}\n\nQuestion: {question}"],
]).pipe(model).pipe(str);

const mapChain = ChatPromptTemplate.fromMessages([
  ["human", "Question: {question}\n\nExcerpt [chunk {chunk}]:\n{doc}\n\n" +
            'Extract ONLY information relevant to the question, prefixed with "[chunk {chunk}]". ' +
            'If nothing is relevant, reply exactly "NONE".'],
]).pipe(model).pipe(str);

const reduceChain = ChatPromptTemplate.fromMessages([
  ["system", "Combine the extracts into one answer. Preserve the [chunk N] citations. " +
             "If the extracts don't answer the question, say so."],
  ["human", "Question: {question}\n\nExtracts:\n{extracts}"],
]).pipe(model).pipe(str);

// ── the automatic strategy choice ────────────────────────────────────────
async function answer(question, chunks) {
  const totalTokens = estimateTokens(fmt(chunks));

  if (totalTokens <= CONTEXT_BUDGET_TOKENS) {
    console.log(`\n  📌 STUFF — ${totalTokens} est. tokens fits in ${CONTEXT_BUDGET_TOKENS}`);
    return { stream: await stuffChain.stream({ context: fmt(chunks), question }),
             used: chunks.map((c) => c.metadata.chunk) };
  }

  console.log(`\n  📌 MAP-REDUCE — ${totalTokens} est. tokens exceeds ${CONTEXT_BUDGET_TOKENS}`);
  console.log(`     mapping ${chunks.length} chunks in parallel…`);

  const extracts = await mapChain.batch(
    chunks.map((d) => ({ question, doc: d.pageContent, chunk: d.metadata.chunk })),
    { maxConcurrency: 6 }
  );

  const kept = extracts
    .map((e, i) => ({ text: e, chunk: chunks[i].metadata.chunk }))
    .filter((e) => !e.text.trim().startsWith("NONE"));

  console.log(`     ${kept.length}/${chunks.length} chunks had relevant content`);

  if (kept.length === 0) {
    return { stream: null, text: "No relevant information found in the document.", used: [] };
  }

  return {
    stream: await reduceChain.stream({
      question, extracts: kept.map((e) => e.text).join("\n\n"),
    }),
    used: kept.map((e) => e.chunk),
  };
}

// ── CLI ──────────────────────────────────────────────────────────────────
const path = process.argv[2];
if (!path) {
  console.error("usage: node day08-docqa.js <file.txt>");
  process.exit(1);
}

const text = await fs.readFile(path, "utf8");
const chunks = splitText(text);

console.log(`📄 ${path}`);
console.log(`   ${text.length} chars · ${chunks.length} chunks · ` +
            `~${estimateTokens(text)} est. tokens\n`);

const rl = readline.createInterface({ input: process.stdin, output: process.stdout });

while (true) {
  const question = (await rl.question("ask › ")).trim();
  if (!question || question === "/exit") break;

  const t0 = Date.now();
  const result = await answer(question, chunks);

  process.stdout.write("\n  ");
  if (result.stream) {
    for await (const c of result.stream) process.stdout.write(c.replace(/\n/g, "\n  "));
  } else {
    process.stdout.write(result.text);
  }

  console.log(`\n\n  ⏱  ${Date.now() - t0}ms · chunks used: ` +
              `${result.used.length ? result.used.join(", ") : "none"}\n`);
}
rl.close();
```

**Python**
```python
# day08_docqa.py
import sys, time
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
strp = StrOutputParser()

# Budget: leave room for the question, the instructions and the answer.
CONTEXT_BUDGET_TOKENS = 5000
estimate_tokens = lambda s: -(-len(s) // 4)          # Day 01 rule of thumb

# ── naive splitter (Day 09 does this properly) ───────────────────────────
def split_text(text, size=1200, overlap=150):
    chunks, i = [], 0
    while i < len(text):
        chunks.append(Document(
            page_content=text[i:i + size],
            metadata={"chunk": len(chunks) + 1, "start": i},
        ))
        if i + size >= len(text):
            break
        i += size - overlap
    return chunks

def fmt(docs):
    return "\n\n---\n\n".join(
        f"[chunk {d.metadata['chunk']}]\n{d.page_content}" for d in docs)

# ── strategies ───────────────────────────────────────────────────────────
stuff_chain = ChatPromptTemplate.from_messages([
    ("system", "Answer using ONLY the context. Cite chunks like [chunk 3]. "
               "If the answer isn't in the context, say so plainly."),
    ("human", "Context:\n{context}\n\nQuestion: {question}"),
]) | model | strp

map_chain = ChatPromptTemplate.from_messages([
    ("human", "Question: {question}\n\nExcerpt [chunk {chunk}]:\n{doc}\n\n"
              'Extract ONLY information relevant to the question, prefixed with "[chunk {chunk}]". '
              'If nothing is relevant, reply exactly "NONE".'),
]) | model | strp

reduce_chain = ChatPromptTemplate.from_messages([
    ("system", "Combine the extracts into one answer. Preserve the [chunk N] citations. "
               "If the extracts don't answer the question, say so."),
    ("human", "Question: {question}\n\nExtracts:\n{extracts}"),
]) | model | strp

# ── the automatic strategy choice ────────────────────────────────────────
def answer(question, chunks):
    total = estimate_tokens(fmt(chunks))

    if total <= CONTEXT_BUDGET_TOKENS:
        print(f"\n  📌 STUFF — {total} est. tokens fits in {CONTEXT_BUDGET_TOKENS}")
        return (stuff_chain.stream({"context": fmt(chunks), "question": question}),
                [c.metadata["chunk"] for c in chunks], None)

    print(f"\n  📌 MAP-REDUCE — {total} est. tokens exceeds {CONTEXT_BUDGET_TOKENS}")
    print(f"     mapping {len(chunks)} chunks in parallel…")

    extracts = map_chain.batch(
        [{"question": question, "doc": d.page_content, "chunk": d.metadata["chunk"]}
         for d in chunks],
        config={"max_concurrency": 6},
    )

    kept = [(e, chunks[i].metadata["chunk"])
            for i, e in enumerate(extracts)
            if not e.strip().startswith("NONE")]

    print(f"     {len(kept)}/{len(chunks)} chunks had relevant content")

    if not kept:
        return None, [], "No relevant information found in the document."

    return (reduce_chain.stream({
                "question": question,
                "extracts": "\n\n".join(e for e, _ in kept)}),
            [c for _, c in kept], None)

# ── CLI ──────────────────────────────────────────────────────────────────
if len(sys.argv) < 2:
    print("usage: python day08_docqa.py <file.txt>")
    sys.exit(1)

path = sys.argv[1]
with open(path, encoding="utf8") as f:
    text = f.read()

chunks = split_text(text)

print(f"📄 {path}")
print(f"   {len(text)} chars · {len(chunks)} chunks · ~{estimate_tokens(text)} est. tokens\n")

while True:
    try:
        question = input("ask › ").strip()
    except (EOFError, KeyboardInterrupt):
        break
    if not question or question == "/exit":
        break

    t0 = time.time()
    stream, used, fallback_text = answer(question, chunks)

    print("\n  ", end="")
    if stream:
        for c in stream:
            print(c.replace("\n", "\n  "), end="", flush=True)
    else:
        print(fallback_text, end="")

    print(f"\n\n  ⏱  {(time.time() - t0) * 1000:.0f}ms · chunks used: "
          f"{', '.join(map(str, used)) if used else 'none'}\n")
```

**Test it** on any long text file — a book from Project Gutenberg works well:

```bash
curl -s https://www.gutenberg.org/files/11/11-0.txt -o alice.txt
node day08-docqa.js alice.txt          # or: python day08_docqa.py alice.txt
```

Try `"Who does Alice meet at the tea party?"` and watch it choose map-reduce.

**Four things this design gets right:**

1. **The strategy choice is measured, not guessed.** It estimates tokens and compares against a
   budget. A hard-coded "always map-reduce" wastes 10× the tokens on short documents.
2. **Chunk IDs are threaded into the map prompt**, so citations survive the reduce step. Without
   that, map-reduce loses all provenance and you can't tell the user where the answer came from.
3. **Irrelevant chunks are filtered before reducing.** On a book, 95% of chunks return `NONE`.
   Reducing over all of them would overflow and cost a fortune.
4. **It streams the final answer** in both strategies, so time-to-first-token stays low even
   though map-reduce does seconds of preparatory work.

**And now the punchline for the whole week.** Run it on a full novel and watch it map over 200
chunks — 200 LLM calls, tens of seconds, real money — to answer one question about a tea party
that appears in *three* chunks.

That is enormously wasteful. What you actually want is to find those three chunks *first*, then
stuff only those. Finding them cheaply, without an LLM call per chunk, requires **embeddings**
and a **vector store**.

That's Days 09–12, and you've just earned the motivation for them.
</details>

---

## 9. Interview questions

### Basic

<details>
<summary><b>Q: What is a chain in LangChain?</b></summary>

A fixed sequence of steps where *you* define the control flow — typically prompt → model →
parser, or retrieve → prompt → generate. In modern LangChain a chain is just an LCEL composition
of `Runnable`s; there's no `Chain` base class you need any more. Chains are predictable in cost
and latency and easy to test, which is why you prefer them over agents whenever the process is
known in advance.
</details>

<details>
<summary><b>Q: Difference between a chain and an agent?</b></summary>

Control flow. In a chain the sequence of steps is decided by the developer and fixed at build
time. In an agent the model decides at runtime which tool to call next and when to stop, so the
number of steps is unknown in advance.

Consequences: chains have bounded cost and latency and are easy to unit-test; agents are flexible
but need step limits, error handling and monitoring. Use a chain when the process is known; use
an agent when the process depends on what you find.
</details>

<details>
<summary><b>Q: What are the document chain strategies?</b></summary>

Four ways to handle more documents than fit in the context window:

- **Stuff** — put them all in one prompt. One call, best quality, only works if it fits.
- **Map-reduce** — process each document in parallel, then combine. Fast, but each map call sees
  only one document, so cross-document reasoning suffers.
- **Refine** — build an answer iteratively, passing the running answer plus the next document.
  Preserves context but is sequential (slow) and can drift.
- **Map-rerank** — answer from each document with a self-score, return the best. Good for finding
  one fact, useless when the answer spans documents.

Default to stuff, and use retrieval to make stuffing viable.
</details>

<details>
<summary><b>Q: What replaced `LLMChain`?</b></summary>

LCEL composition: `prompt | model` (Python) or `prompt.pipe(model)` (JS). It's not a renamed
class — the insight was that a chain doesn't need a class at all, just a shared interface plus
composition. `LLMChain` and the other legacy chains now live in `@langchain/classic` /
`langchain-classic` for backwards compatibility.
</details>

### Intermediate

<details>
<summary><b>Q: When would you use map-reduce over stuff, and what do you lose?</b></summary>

Use map-reduce when the documents genuinely don't fit *and* you need to process all of them —
summarising a whole book, auditing every record, generating a report over a corpus.

You lose cross-document reasoning: each map call sees exactly one document, so a question whose
answer requires connecting a fact on page 3 to a fact on page 60 will usually fail. You also pay
N+1 calls instead of 1.

The important follow-up: for *question answering*, map-reduce is usually the wrong tool entirely.
Retrieving the handful of relevant chunks and stuffing those is faster, cheaper and more accurate.
Map-reduce is for when you truly must touch everything.
</details>

<details>
<summary><b>Q: Why is refine slow, and when is it worth it?</b></summary>

Refine is inherently **sequential** — each call needs the previous call's answer as input, so N
documents means N serial round trips that cannot be parallelised. Map-reduce with the same N
finishes in roughly the time of two calls.

It's worth it when you need cross-document context preserved *and* can't fit everything in one
prompt — building a chronology, or a running analysis where each new document genuinely changes
the interpretation of earlier ones.

Its other failure mode is **drift**: each rewrite can degrade the answer, and later documents get
disproportionate influence. Mitigate by instructing the model to return the current answer
unchanged when new context doesn't help, and by keeping N small.
</details>

<details>
<summary><b>Q: How do you handle map-reduce when the summaries themselves overflow?</b></summary>

Reduce recursively: batch the summaries into groups that fit the context budget, reduce each
group, then reduce those results, repeating until one remains — a reduction tree.

Three implementation details matter: batch by *token budget* rather than fixed count, since item
lengths vary; give any single oversized item its own batch instead of dropping it or looping
forever; and short-circuit when everything already fits in one batch, or you burn an extra call
and degrade the summary through needless rewriting.

Filtering irrelevant map outputs before reducing is usually the biggest win — on a large corpus
most chunks contribute nothing.
</details>

<details>
<summary><b>Q: How would you route between models to control cost?</b></summary>

Classify the request with a cheap model, then dispatch to a model matched to difficulty — a small
model for lookups and classification, a large one for reasoning and generation. Most traffic is
easy, so this typically cuts spend substantially with no quality loss on the easy path.

Production details: the classifier must itself be cheap and must have a *fallback value* (not an
error) so a classifier outage degrades rather than fails; track cumulative spend and degrade
deliberately near a budget, skipping the classifier once everything is going cheap anyway; check
budget *before* the call; and log which tier each request took so you can see the distribution
shift.
</details>

### Advanced

<details>
<summary><b>Q: Why did LangChain remove the legacy chain classes, and what's the general lesson?</b></summary>

The 0.x chains were classes that hid control flow inside a `_call()` method. Three concrete
problems followed: you couldn't see the data flow without reading LangChain's source; any
customisation required subclassing; and streaming support was inconsistent and undiscoverable.

The replacement isn't another class — it's composition over a shared interface.
`MapReduceDocumentsChain` becomes `.batch()` plus a reduce prompt, roughly a dozen readable lines
you can modify freely (adding a relevance filter between map and reduce is trivial in LCEL and
required a fork before).

The general lesson, and the part worth saying out loud: **abstractions should hide implementation,
not control flow.** Hiding *how* a model call is made across providers is valuable — that's
`BaseChatModel`, and it earns its keep. Hiding *what order your steps run in* removes the
developer's ability to reason about, debug and modify their own program. LangChain 1.x moves
consistently toward less magic in orchestration and more in integration.
</details>

<details>
<summary><b>Q: Design a system that answers questions over a 500-page technical manual, for 10,000 users a day.</b></summary>

**Don't use document chains as the primary path.** Map-reducing 500 pages per question is roughly
1,500 LLM calls per query — unaffordable and slow at 10k/day. The architecture is retrieval-first:

**Ingest (offline, once per manual version)** — load, split into ~500-token chunks with overlap,
preserving section headers in metadata; embed; store in a vector database. Run this in CI when
the manual changes, not per request. Tag by version so a bad ingest can be rolled back.

**Query path (online)** — rewrite the question using conversation history so follow-ups are
retrievable; retrieve ~20 candidates with hybrid search (vector + BM25, since manuals are full of
exact part numbers and error codes that embeddings handle poorly); rerank to the top 5; then
**stuff** those 5 into one call with citations. Two to three model calls per question, not 1,500.

**Caching** — semantic caching on the question embedding catches near-duplicate questions, which
in support traffic is a large fraction. Cache retrieval results too.

**Quality** — a golden set of question/answer pairs run in CI on every prompt, chunking or model
change. Track **retrieval recall separately from answer quality**: if the right chunk was never
retrieved, no prompt work will fix the answer, and conflating the two is the most common way RAG
debugging goes in circles.

**Where document chains still belong** — genuinely corpus-wide tasks: "summarise everything new
in version 7", "list every deprecated API". Those touch everything by definition, so map-reduce
with recursive reduction is correct. Run offline, cache the result.

**Ops** — stream answers, rate-limit per user, monitor cost per query and retrieval latency
separately, keep a cross-provider fallback.
</details>

<details>
<summary><b>Q: Your map-reduce summariser produces bland, generic summaries. Diagnose it.</b></summary>

Bland output from map-reduce is usually **compounding lossy compression**, not a bad prompt. Each
map call compresses a chunk, the reduce compresses the compressions, and specifics — numbers,
names, caveats — get smoothed away at every level. Recursive reduction makes it worse, since each
level is another lossy pass.

How I'd work through it:

1. **Inspect intermediate outputs first.** Are the *map* outputs already generic, or only the
   final? That localises the problem immediately, and people routinely skip it.
2. **If maps are generic** — the map prompt asks for a summary when it should ask for
   *extraction*. "Summarise this chunk" invites paraphrase; "extract every specific figure, name,
   date and claim relevant to X, verbatim where possible" preserves detail. Biggest single fix.
3. **If maps are good but the reduce is bland** — the reduce is over-compressing. Raise the length
   allowance and forbid generalising away a number. Consider reducing into a *structured* schema
   (Day 06) with explicit fields for figures and claims, which makes dropping them harder.
4. **Filter irrelevant chunks before reducing.** Diluting five relevant extracts with ninety-five
   "this chunk covers general background" entries pushes the model toward generic phrasing.
5. **Reconsider the strategy.** If the goal is answering a question rather than summarising
   everything, retrieval + stuff avoids the compression entirely and is both better and cheaper.
6. **Check reduction depth.** At three or four levels, raise the batch budget or use a
   larger-context model for the reduce so the tree is shallower.

The framing: every map-reduce level is a lossy compression step — minimise the number of levels,
and make each level *extract* rather than *summarise*.
</details>

---

## 10. Recap

- ✅ A chain is a fixed sequence of steps *you* control — an agent lets the model choose
- ✅ Sequential (`assign` chained), parallel (`RunnableParallel`), router (`RunnableBranch`), conversation (`MessagesPlaceholder`)
- ✅ Route by **difficulty**, not just topic — that's where the cost savings live
- ✅ Four document strategies: **stuff** (default), map-reduce (parallel, loses cross-doc context), refine (serial, preserves context, drifts), map-rerank (one fact only)
- ✅ Format documents with separators, numbers and metadata so the model can cite them
- ✅ Naive map-reduce overflows — reduce recursively, batch by token budget, filter irrelevant maps
- ✅ Legacy chains left the main package → `@langchain/classic` / `langchain-classic`
- ✅ **Stuff wins on every axis except capacity** — so the real goal is retrieving fewer, better documents

### Tomorrow

**[Day 09 — Documents, loaders & splitting](day-09-documents-and-splitting.md)**: today you split
text with `slice()`, which cuts sentences in half and destroys tables and code blocks. Tomorrow
you learn real splitting — recursive, markdown-aware, HTML-aware, token-aware — plus loaders for
PDF, CSV, JSON and the web, and how chunk size quietly determines whether your whole RAG system
works or fails.

### Quick self-check

1. Your answer needs facts from chunks 2, 7 and 15. Which document strategies can find it?
2. Why is refine slower than map-reduce for the same documents?
3. You're map-reducing 400 chunks to answer one question. What should you do instead?

<details>
<summary>Answers</summary>

1. **Stuff** (sees everything at once) and **refine** (carries a running answer across all
   documents). **Map-reduce** may find them but often fails to connect them, since no map call
   sees more than one chunk. **Map-rerank** structurally cannot — it returns a single chunk's
   answer.
2. Refine is sequential: each call needs the previous call's answer, so N documents means N serial
   round trips. Map-reduce's map calls are independent and run concurrently, finishing in roughly
   the time of two calls.
3. Retrieve first. Embed the chunks once, find the ~5 relevant to *this* question, and stuff only
   those — 1 call instead of 401, and usually a better answer. That's Days 10–12.
</details>
