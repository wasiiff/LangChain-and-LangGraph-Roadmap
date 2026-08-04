# Day 07 — LCEL & Runnables (the #1 interview topic)

> ⏱ **Time:** ~3 hours · 🎯 **Prereqs:** [Day 06](day-06-output-parsers-structured-output.md) · 🧩 **Difficulty:** ●●●○○

**Today you learn:** what `.pipe()` / `|` actually builds, and the six Runnables that compose
into every LangChain pipeline: `RunnableSequence`, `RunnableParallel`, `RunnableLambda`,
`RunnablePassthrough`, `RunnableAssign`, `RunnableBranch`.

Then you build **StudyBuddy v1** — the Week 1 project.

If you only deeply learn one day from Week 1, make it this one. It's the most-asked LangChain
interview topic, and it's the foundation for Week 2's RAG chains and Week 3's graphs.

---

## 1. The problem

You've been writing this all week:

```js
prompt.pipe(model).pipe(parser)
```

It works. But now the requirements get real:

> *"Take a support ticket. **At the same time**, classify it, extract the customer's name, and
> detect the language. Then, **depending on the category**, either draft a refund reply, a bug
> acknowledgement, or a feature-request thank-you. Include the original ticket in the output.
> Log the timing. And stream the final reply to the UI."*

With plain functions:

```js
async function handle(ticket) {
  const [category, name, lang] = await Promise.all([classify(ticket), extractName(ticket), detectLang(ticket)]);
  let reply;
  if (category === "BILLING") reply = await refundChain(ticket, name);
  else if (category === "BUG") reply = await bugChain(ticket, name);
  else reply = await thanksChain(ticket, name);
  return { ticket, category, name, lang, reply };
}
```

That's... fine? Until you want to **stream** `reply` to the browser. Now you need `handle` to
return an async iterator, which means every branch must return one, which means `refundChain`
must too, and the `Promise.all` step must not block the stream. And you want **tracing** on
every step. And **retries** on just the model calls. And **batching** over 500 tickets with a
concurrency cap.

Every one of those is now your problem, in every function you write.

**LCEL's proposition:** express the *structure* declaratively, and get streaming, batching,
async, retries, fallbacks, and tracing across the whole thing for free.

---

## 2. Mental model

```
   LCEL = LangChain Expression Language.
   It is not a DSL. It is operator overloading on one interface.


   EVERY component implements Runnable:

        ┌──────────────────────────────────────┐
        │  invoke(input)      → output         │
        │  stream(input)      → chunks         │
        │  batch(inputs)      → outputs        │
        │  pipe(next)         → Runnable       │  ← composition is CLOSED
        └──────────────────────────────────────┘

   "Closed" means: A Runnable piped to a Runnable IS a Runnable.
   So chains nest infinitely, and streaming/batching/tracing propagate.


   THE SIX BUILDING BLOCKS

   1. RunnableSequence      A → B → C            (what .pipe() / | builds)
   2. RunnableParallel      A ─┬─→ B ─┐          (object literal = this)
                               └─→ C ─┴→ {b, c}
   3. RunnableLambda        any function → Runnable
   4. RunnablePassthrough   input → input        (identity; carries data forward)
   5. RunnableAssign        {a} → {a, b}         (add a key, keep the rest)
   6. RunnableBranch        if/elif/else routing


   THE ONE RULE THAT EXPLAINS EVERYTHING:

        output of step N  MUST MATCH  input of step N+1

   Most LCEL bugs are a type mismatch at one seam. Debug by printing
   the value between steps.
```

---

## 3. First principles

### 3.1 `RunnableSequence` — the pipe

```js
prompt.pipe(model).pipe(parser)
// is exactly
RunnableSequence.from([prompt, model, parser])
```
```python
prompt | model | parser
# is exactly
RunnableSequence(first=prompt, middle=[model], last=parser)
```

Data flows left to right. Types must line up:

```
{topic: "x"}  →  [prompt]  →  ChatPromptValue  →  [model]  →  AIMessage  →  [parser]  →  string
```

### 3.2 `RunnableParallel` — fan out

Run several Runnables on the **same input**, concurrently, and collect the results into an object.

```js
const parallel = RunnableParallel.from({
  summary: summaryChain,
  keywords: keywordChain,
  sentiment: sentimentChain,
});

await parallel.invoke("Some article text");
// → { summary: "...", keywords: [...], sentiment: "positive" }
// All three ran AT THE SAME TIME.
```

**The sugar that trips everyone up:** a plain object literal in a chain position is
*automatically* coerced to a `RunnableParallel`.

```js
chain = { summary: summaryChain, keywords: keywordChain }.pipe(next)   // ❌ objects have no .pipe
chain = RunnableSequence.from([{ summary: summaryChain, keywords: keywordChain }, next]);  // ✅
```
```python
chain = {"summary": summary_chain, "keywords": keyword_chain} | next_step   # ✅ works in Python
```

Python's `|` operator handles dicts natively. In JS you need the object to be inside a
`RunnableSequence.from([...])` array, or wrap it with `RunnableParallel.from({...})`.

### 3.3 `RunnableLambda` — any function becomes a step

```js
const upper = new RunnableLambda({ func: (x) => x.toUpperCase() });
// or the shorthand:
const upper = RunnableLambda.from((x) => x.toUpperCase());
```

Plain functions are auto-coerced too:

```js
chain.pipe((x) => x.toUpperCase())        // ✅ becomes a RunnableLambda
```
```python
chain | (lambda x: x.upper())              # ✅ same
```

Lambdas take exactly **one argument**. Need more? Pass an object.

```js
// ❌ (a, b) => ...
// ✅
RunnableLambda.from(({ a, b }) => a + b)
```

> ⚠️ **Async lambdas in JS:** `RunnableLambda.from(async (x) => await something(x))` works fine.
> In Python, use a regular function for sync chains and an `async def` for async chains — or let
> LangChain wrap the sync one (it runs it in a thread pool for `ainvoke`).

### 3.4 `RunnablePassthrough` — carry data forward

The identity function. Sounds useless; it's essential.

```js
const chain = RunnableSequence.from([
  {
    original: new RunnablePassthrough(),   // ← keep the raw input
    summary: summaryChain,                 // ← and also summarise it
  },
  ({ original, summary }) => `${summary}\n\n---\nOriginal: ${original}`,
]);
```

Without `RunnablePassthrough`, the original input is *gone* after the first step — the parallel
block replaces it with `{summary}`. Passthrough is how you keep it.

This is the single most common pattern in RAG (Week 2):

```js
{
  context: retriever,                  // fetch documents for the question
  question: new RunnablePassthrough(), // ...and keep the question itself
}
```

### 3.5 `RunnableAssign` — add a key, keep everything else

`RunnablePassthrough.assign()` is `RunnableAssign`. It takes an object and **adds** keys.

```js
// Input:  { question: "What is RAG?" }
// Output: { question: "What is RAG?", context: "..." }

RunnablePassthrough.assign({ context: retrieverChain })
```

**`Passthrough` vs `Assign` — the distinction interviewers ask about:**

```
RunnablePassthrough           input  →  input                  (unchanged)
RunnablePassthrough.assign()  {a}    →  {a, b}                 (add, keep)
RunnableParallel              input  →  {b, c}                 (replace entirely)
```

```js
// Parallel: input is REPLACED by the object
RunnableParallel.from({ b: chainB })          // {a: 1} → {b: "..."}          a is LOST

// Assign: input is EXTENDED
RunnablePassthrough.assign({ b: chainB })     // {a: 1} → {a: 1, b: "..."}    a survives
```

Assign is how you build up a growing context object through a multi-step pipeline.

### 3.6 `RunnableBranch` — if/else routing

```js
const branch = RunnableBranch.from([
  [(x) => x.category === "BILLING", billingChain],   // [condition, runnable]
  [(x) => x.category === "BUG", bugChain],
  defaultChain,                                       // last item = else
]);
```
```python
branch = RunnableBranch(
    (lambda x: x["category"] == "BILLING", billing_chain),
    (lambda x: x["category"] == "BUG", bug_chain),
    default_chain,                                     # last positional = else
)
```

Conditions are evaluated in order; the first `true` wins.

> 💡 **You can also just return a Runnable from a lambda.** LangChain will invoke it. This is
> often more readable than `RunnableBranch` for complex routing:
> ```js
> RunnableLambda.from((x) => x.category === "BUG" ? bugChain : defaultChain)
> ```

### 3.7 Runnable modifiers

These wrap any Runnable and return a Runnable — so they compose anywhere in a chain:

```js
chain.withRetry({ stopAfterAttempt: 3 })
chain.withFallbacks([backupChain])
chain.withConfig({ tags: ["prod"], metadata: { tenant: "acme" } })
chain.bind({ stop: ["\n"] })              // fix an argument on the underlying step
chain.withListeners({ onStart, onEnd })   // hooks
```

### 3.8 Streaming through a chain

This is the payoff. `.stream()` propagates automatically:

```js
for await (const chunk of await chain.stream({ topic: "rain" })) {
  process.stdout.write(chunk);
}
```

**But there's a catch that catches everyone.** A step can only stream if it can produce output
incrementally. A `RunnableLambda` that takes the whole input, transforms it, and returns —
*can't*. So it **buffers**: everything before it streams internally, but the chain's output
only starts flowing once that lambda completes.

```
prompt → model → parser                       ✅ streams token by token
prompt → model → parser → (x) => x.trim()      ❌ buffers — trim() needs the whole string
```

Rule of thumb: **anything after a non-streaming step blocks streaming.** Put transformations
before the model, or accept the buffering, or write a generator-based transform (Day 23).

### 3.9 `streamEvents` — see inside the chain

`.stream()` gives you the *final* output. `.streamEvents()` gives you every intermediate step:

```js
for await (const ev of chain.streamEvents({ topic: "x" }, { version: "v2" })) {
  if (ev.event === "on_chat_model_stream") process.stdout.write(ev.data.chunk.content);
  if (ev.event === "on_retriever_end") console.log("retrieved", ev.data.output.length);
}
```

This is how you build a UI that shows "Searching documents… Reading… Writing answer…". Day 23
goes deep; know it exists now.

---

## 4. Code — JavaScript

```bash
npm install langchain @langchain/core @langchain/groq zod dotenv
```

### 4.1 The six building blocks

```js
// day07-runnables.js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";
import { ChatPromptTemplate } from "@langchain/core/prompts";
import { StringOutputParser } from "@langchain/core/output_parsers";
import {
  RunnableSequence, RunnableParallel, RunnableLambda,
  RunnablePassthrough, RunnableBranch,
} from "@langchain/core/runnables";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });
const str = new StringOutputParser();

// ── 1. SEQUENCE ──────────────────────────────────────────────────────────
const explain = ChatPromptTemplate
  .fromMessages([["human", "Explain {topic} in one sentence."]])
  .pipe(model).pipe(str);

console.log("1 sequence:", await explain.invoke({ topic: "gravity" }));

// ── 2. PARALLEL ──────────────────────────────────────────────────────────
const analyse = RunnableParallel.from({
  summary:   ChatPromptTemplate.fromMessages([["human", "Summarise in 8 words: {text}"]]).pipe(model).pipe(str),
  sentiment: ChatPromptTemplate.fromMessages([["human", "Sentiment (one word): {text}"]]).pipe(model).pipe(str),
  keywords:  ChatPromptTemplate.fromMessages([["human", "3 keywords, comma-separated: {text}"]]).pipe(model).pipe(str),
});

const t0 = Date.now();
console.log("\n2 parallel:", await analyse.invoke({
  text: "The new update broke login for everyone on my team and support hasn't replied.",
}));
console.log(`   (3 model calls in ${Date.now() - t0}ms — they ran concurrently)`);

// ── 3. LAMBDA ────────────────────────────────────────────────────────────
const wordCount = RunnableLambda.from((text) => ({ text, words: text.split(/\s+/).length }));
console.log("\n3 lambda:", await wordCount.invoke("one two three"));

// Auto-coercion: a bare function works too
const shout = explain.pipe((s) => s.toUpperCase());
console.log("   coerced:", (await shout.invoke({ topic: "rain" })).slice(0, 50));

// ── 4. PASSTHROUGH ───────────────────────────────────────────────────────
const withOriginal = RunnableSequence.from([
  {
    original: new RunnablePassthrough(),      // ← keep the input
    summary: ChatPromptTemplate.fromMessages([["human", "Summarise in 5 words: {text}"]])
      .pipe(model).pipe(str),
  },
]);
console.log("\n4 passthrough:", await withOriginal.invoke({ text: "Cats sleep a great deal." }));

// ── 5. ASSIGN ────────────────────────────────────────────────────────────
const enriched = RunnablePassthrough.assign({
  wordCount: (x) => x.text.split(/\s+/).length,
  upper: (x) => x.text.toUpperCase(),
});
console.log("\n5 assign:", await enriched.invoke({ text: "hello world", id: 42 }));
// { text: 'hello world', id: 42, wordCount: 2, upper: 'HELLO WORLD' }   ← id survived

// ── 6. BRANCH ────────────────────────────────────────────────────────────
const branch = RunnableBranch.from([
  [(x) => x.length > 100, RunnableLambda.from((x) => `LONG (${x.length} chars)`)],
  [(x) => x.length > 20,  RunnableLambda.from((x) => `MEDIUM (${x.length} chars)`)],
  RunnableLambda.from((x) => `SHORT (${x.length} chars)`),
]);
console.log("\n6 branch:", await branch.invoke("hi"));
console.log("         ", await branch.invoke("a".repeat(50)));
console.log("         ", await branch.invoke("a".repeat(200)));
```

### 4.2 The classic pattern: parallel + passthrough + assign

```js
// day07-composition.js
import "dotenv/config";
import * as z from "zod";
import { ChatGroq } from "@langchain/groq";
import { ChatPromptTemplate } from "@langchain/core/prompts";
import { StringOutputParser } from "@langchain/core/output_parsers";
import { RunnableSequence, RunnablePassthrough } from "@langchain/core/runnables";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });

const Triage = z.object({
  category: z.enum(["BILLING", "BUG", "FEATURE", "OTHER"]),
  urgency: z.enum(["low", "medium", "high"]),
  customerName: z.string().nullable().describe("Customer's name if mentioned, else null"),
});

// Step 1: add triage data to the input, keeping the ticket.
const withTriage = RunnablePassthrough.assign({
  triage: (x) => model.withStructuredOutput(Triage).invoke(x.ticket),
});

// Step 2: add a suggested reply, keeping everything.
const withReply = RunnablePassthrough.assign({
  reply: RunnableSequence.from([
    ChatPromptTemplate.fromMessages([
      ["system", "You write support replies. Category: {category}. Urgency: {urgency}. " +
                 "Address the customer as {name}. Be brief and specific."],
      ["human", "{ticket}"],
    ]),
    model,
    new StringOutputParser(),
  ]).withConfig({ runName: "draft_reply" }),
});

// The seam between them needs reshaping — that's what the lambda does.
const pipeline = RunnableSequence.from([
  withTriage,
  (x) => ({
    ticket: x.ticket,
    category: x.triage.category,
    urgency: x.triage.urgency,
    name: x.triage.customerName ?? "there",
    triage: x.triage,
  }),
  withReply,
]);

const result = await pipeline.invoke({
  ticket: "Hi, this is Sara. I've been charged twice for my subscription and nobody has replied " +
          "to my email in a week. Please sort this out.",
});

console.log(JSON.stringify(result, null, 2));
```

### 4.3 Routing with a branch

```js
// day07-routing.js
import "dotenv/config";
import * as z from "zod";
import { ChatGroq } from "@langchain/groq";
import { ChatPromptTemplate } from "@langchain/core/prompts";
import { StringOutputParser } from "@langchain/core/output_parsers";
import { RunnableSequence, RunnableBranch } from "@langchain/core/runnables";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });
const str = new StringOutputParser();

const reply = (system) =>
  ChatPromptTemplate.fromMessages([["system", system], ["human", "{ticket}"]]).pipe(model).pipe(str);

const CHAINS = {
  billing: reply("You handle billing. Apologise, confirm you'll investigate the charge, " +
                 "and give a 2-business-day timeline. Max 3 sentences."),
  bug:     reply("You handle bugs. Acknowledge, ask for browser + OS + steps to reproduce, " +
                 "and give a ticket reference format like BUG-1234. Max 3 sentences."),
  feature: reply("You handle feature requests. Thank them warmly, say it's logged for review, " +
                 "and set no timeline expectations. Max 2 sentences."),
  other:   reply("You are a general support agent. Be helpful and brief."),
};

const classify = model.withStructuredOutput(
  z.object({ category: z.enum(["BILLING", "BUG", "FEATURE", "OTHER"]) })
);

const router = RunnableSequence.from([
  // Attach the category, keep the ticket.
  { ticket: (x) => x.ticket, category: async (x) => (await classify.invoke(x.ticket)).category },

  // Route.
  RunnableBranch.from([
    [(x) => x.category === "BILLING", CHAINS.billing],
    [(x) => x.category === "BUG",     CHAINS.bug],
    [(x) => x.category === "FEATURE", CHAINS.feature],
    CHAINS.other,
  ]),
]);

for (const ticket of [
  "I was charged twice this month, please refund.",
  "The export button does nothing in Firefox.",
  "Any chance of a dark mode?",
]) {
  console.log(`\n📩 ${ticket}\n💬 ${await router.invoke({ ticket })}`);
}
```

### 4.4 Streaming through a chain — and what blocks it

```js
// day07-streaming.js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";
import { ChatPromptTemplate } from "@langchain/core/prompts";
import { StringOutputParser } from "@langchain/core/output_parsers";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });

const streams = ChatPromptTemplate
  .fromMessages([["human", "Explain {topic} in 60 words."]])
  .pipe(model)
  .pipe(new StringOutputParser());

// ❌ this lambda needs the WHOLE string, so it buffers
const buffers = streams.pipe((s) => s.toUpperCase());

async function timeStream(name, chain) {
  const t0 = Date.now();
  let first = null, chars = 0;
  for await (const chunk of await chain.stream({ topic: "photosynthesis" })) {
    first ??= Date.now() - t0;
    chars += chunk.length;
  }
  console.log(`${name.padEnd(12)} first chunk at ${String(first).padEnd(5)}ms, ` +
              `total ${Date.now() - t0}ms`);
}

await timeStream("streaming", streams);
await timeStream("buffered", buffers);
// streaming    first chunk at 210ms,  total 1400ms
// buffered     first chunk at 1420ms, total 1420ms   ← ALL the latency moved to the front

// ── streamEvents: see inside ─────────────────────────────────────────────
console.log("\n── events ──");
for await (const ev of streams.streamEvents({ topic: "tides" }, { version: "v2" })) {
  if (ev.event === "on_chat_model_start") console.log("→ model started");
  if (ev.event === "on_chat_model_end")   console.log("→ model finished");
  if (ev.event === "on_parser_end")       console.log("→ parser finished");
}
```

### 4.5 Debugging a chain

```js
// day07-debug.js
import { RunnableLambda, RunnableSequence } from "@langchain/core/runnables";

// A tap: log what's flowing through, pass it along unchanged.
const tap = (label) =>
  RunnableLambda.from((x) => {
    console.log(`  [${label}]`, JSON.stringify(x).slice(0, 120));
    return x;
  }).withConfig({ runName: `tap:${label}` });

const chain = RunnableSequence.from([
  (x) => ({ ...x, step: 1 }),
  tap("after step 1"),
  (x) => ({ ...x, step: 2, doubled: x.n * 2 }),
  tap("after step 2"),
  (x) => x.doubled,
]);

console.log("result:", await chain.invoke({ n: 21 }));

// Inspect structure without running anything:
console.log("\ninput schema :", JSON.stringify(chain.getGraph().nodes ? "graph available" : ""));
```

---

## 5. Code — Python

```bash
pip install langchain langchain-groq pydantic python-dotenv
```

### 5.1 The six building blocks

```python
# day07_runnables.py
import time
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import (
    RunnableParallel, RunnableLambda, RunnablePassthrough, RunnableBranch,
)

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
strp = StrOutputParser()

# ── 1. SEQUENCE ──────────────────────────────────────────────────────────
explain = (
    ChatPromptTemplate.from_messages([("human", "Explain {topic} in one sentence.")])
    | model | strp
)
print("1 sequence:", explain.invoke({"topic": "gravity"}))

# ── 2. PARALLEL ──────────────────────────────────────────────────────────
analyse = RunnableParallel(
    summary=ChatPromptTemplate.from_messages([("human", "Summarise in 8 words: {text}")]) | model | strp,
    sentiment=ChatPromptTemplate.from_messages([("human", "Sentiment (one word): {text}")]) | model | strp,
    keywords=ChatPromptTemplate.from_messages([("human", "3 keywords, comma-separated: {text}")]) | model | strp,
)

t0 = time.time()
print("\n2 parallel:", analyse.invoke({
    "text": "The new update broke login for everyone on my team and support hasn't replied.",
}))
print(f"   (3 model calls in {(time.time() - t0) * 1000:.0f}ms — they ran concurrently)")

# ── 3. LAMBDA ────────────────────────────────────────────────────────────
word_count = RunnableLambda(lambda text: {"text": text, "words": len(text.split())})
print("\n3 lambda:", word_count.invoke("one two three"))

# Auto-coercion: a bare callable works too
shout = explain | (lambda s: s.upper())
print("   coerced:", shout.invoke({"topic": "rain"})[:50])

# ── 4. PASSTHROUGH ───────────────────────────────────────────────────────
with_original = {
    "original": RunnablePassthrough(),        # ← keep the input
    "summary": ChatPromptTemplate.from_messages([("human", "Summarise in 5 words: {text}")])
               | model | strp,
}
print("\n4 passthrough:", RunnableParallel(with_original).invoke({"text": "Cats sleep a great deal."}))

# ── 5. ASSIGN ────────────────────────────────────────────────────────────
enriched = RunnablePassthrough.assign(
    word_count=lambda x: len(x["text"].split()),
    upper=lambda x: x["text"].upper(),
)
print("\n5 assign:", enriched.invoke({"text": "hello world", "id": 42}))
# {'text': 'hello world', 'id': 42, 'word_count': 2, 'upper': 'HELLO WORLD'}  ← id survived

# ── 6. BRANCH ────────────────────────────────────────────────────────────
branch = RunnableBranch(
    (lambda x: len(x) > 100, RunnableLambda(lambda x: f"LONG ({len(x)} chars)")),
    (lambda x: len(x) > 20,  RunnableLambda(lambda x: f"MEDIUM ({len(x)} chars)")),
    RunnableLambda(lambda x: f"SHORT ({len(x)} chars)"),
)
print("\n6 branch:", branch.invoke("hi"))
print("         ", branch.invoke("a" * 50))
print("         ", branch.invoke("a" * 200))
```

### 5.2 The classic pattern: parallel + passthrough + assign

```python
# day07_composition.py
import json
from dotenv import load_dotenv
from typing import Literal, Optional
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

class Triage(BaseModel):
    """Triage classification of a support ticket."""
    category: Literal["BILLING", "BUG", "FEATURE", "OTHER"]
    urgency: Literal["low", "medium", "high"]
    customer_name: Optional[str] = Field(None, description="Customer's name if mentioned, else null")

# Step 1: add triage data to the input, keeping the ticket.
with_triage = RunnablePassthrough.assign(
    triage=lambda x: model.with_structured_output(Triage).invoke(x["ticket"]),
)

# Step 2: add a suggested reply, keeping everything.
with_reply = RunnablePassthrough.assign(
    reply=(
        ChatPromptTemplate.from_messages([
            ("system", "You write support replies. Category: {category}. Urgency: {urgency}. "
                       "Address the customer as {name}. Be brief and specific."),
            ("human", "{ticket}"),
        ])
        | model | StrOutputParser()
    ).with_config(run_name="draft_reply"),
)

# The seam between them needs reshaping — that's what the lambda does.
pipeline = (
    with_triage
    | (lambda x: {
        "ticket": x["ticket"],
        "category": x["triage"].category,
        "urgency": x["triage"].urgency,
        "name": x["triage"].customer_name or "there",
        "triage": x["triage"],
    })
    | with_reply
)

result = pipeline.invoke({
    "ticket": "Hi, this is Sara. I've been charged twice for my subscription and nobody has "
              "replied to my email in a week. Please sort this out.",
})

print(json.dumps({**result, "triage": result["triage"].model_dump()}, indent=2))
```

### 5.3 Routing with a branch

```python
# day07_routing.py
from dotenv import load_dotenv
from typing import Literal
from pydantic import BaseModel
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableBranch

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

def reply(system):
    return (ChatPromptTemplate.from_messages([("system", system), ("human", "{ticket}")])
            | model | StrOutputParser())

CHAINS = {
    "billing": reply("You handle billing. Apologise, confirm you'll investigate the charge, "
                     "and give a 2-business-day timeline. Max 3 sentences."),
    "bug":     reply("You handle bugs. Acknowledge, ask for browser + OS + steps to reproduce, "
                     "and give a ticket reference format like BUG-1234. Max 3 sentences."),
    "feature": reply("You handle feature requests. Thank them warmly, say it's logged for review, "
                     "and set no timeline expectations. Max 2 sentences."),
    "other":   reply("You are a general support agent. Be helpful and brief."),
}

class Category(BaseModel):
    """The category of a support ticket."""
    category: Literal["BILLING", "BUG", "FEATURE", "OTHER"]

classify = model.with_structured_output(Category)

router = (
    # Attach the category, keep the ticket.
    {"ticket": lambda x: x["ticket"],
     "category": lambda x: classify.invoke(x["ticket"]).category}

    # Route.
    | RunnableBranch(
        (lambda x: x["category"] == "BILLING", CHAINS["billing"]),
        (lambda x: x["category"] == "BUG",     CHAINS["bug"]),
        (lambda x: x["category"] == "FEATURE", CHAINS["feature"]),
        CHAINS["other"],
    )
)

for ticket in [
    "I was charged twice this month, please refund.",
    "The export button does nothing in Firefox.",
    "Any chance of a dark mode?",
]:
    print(f"\n📩 {ticket}\n💬 {router.invoke({'ticket': ticket})}")
```

### 5.4 Streaming through a chain — and what blocks it

```python
# day07_streaming.py
import time
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

streams = (
    ChatPromptTemplate.from_messages([("human", "Explain {topic} in 60 words.")])
    | model | StrOutputParser()
)

# ❌ this lambda needs the WHOLE string, so it buffers
buffers = streams | (lambda s: s.upper())

def time_stream(name, chain):
    t0 = time.time()
    first = None
    for chunk in chain.stream({"topic": "photosynthesis"}):
        if first is None:
            first = (time.time() - t0) * 1000
    total = (time.time() - t0) * 1000
    print(f"{name:<12} first chunk at {first:>6.0f}ms, total {total:.0f}ms")

time_stream("streaming", streams)
time_stream("buffered", buffers)
# streaming    first chunk at    210ms, total 1400ms
# buffered     first chunk at   1420ms, total 1420ms   ← ALL the latency moved to the front

# ── astream_events: see inside ───────────────────────────────────────────
import asyncio

async def watch():
    print("\n── events ──")
    async for ev in streams.astream_events({"topic": "tides"}, version="v2"):
        if ev["event"] == "on_chat_model_start":
            print("→ model started")
        if ev["event"] == "on_chat_model_end":
            print("→ model finished")
        if ev["event"] == "on_parser_end":
            print("→ parser finished")

asyncio.run(watch())
```

### 5.5 Debugging a chain

```python
# day07_debug.py
import json
from langchain_core.runnables import RunnableLambda

def tap(label):
    """Log what's flowing through, pass it along unchanged."""
    def _tap(x):
        print(f"  [{label}]", json.dumps(x, default=str)[:120])
        return x
    return RunnableLambda(_tap).with_config(run_name=f"tap:{label}")

chain = (
    RunnableLambda(lambda x: {**x, "step": 1})
    | tap("after step 1")
    | (lambda x: {**x, "step": 2, "doubled": x["n"] * 2})
    | tap("after step 2")
    | (lambda x: x["doubled"])
)

print("result:", chain.invoke({"n": 21}))

# Inspect structure without running anything:
chain.get_graph().print_ascii()
```

> 💡 `chain.get_graph().print_ascii()` in Python prints an ASCII diagram of your chain. It's the
> fastest way to check you built the structure you meant to. (In JS, `chain.getGraph()` returns
> the graph object; `.toJSON()` is inspectable.)

### 🔁 JS ↔ Python differences you just saw

| | JavaScript | Python |
|---|---|---|
| Pipe | `.pipe(x)` | `\| x` |
| Object → Parallel | must be inside `RunnableSequence.from([...])` | plain dict works with `\|` |
| Parallel constructor | `RunnableParallel.from({...})` | `RunnableParallel(a=..., b=...)` |
| Lambda | `RunnableLambda.from(fn)` | `RunnableLambda(fn)` |
| Branch | `RunnableBranch.from([[cond, r], ..., default])` | `RunnableBranch((cond, r), ..., default)` |
| Assign | `RunnablePassthrough.assign({ k: fn })` | `RunnablePassthrough.assign(k=fn)` |
| Config | `.withConfig({ runName })` | `.with_config(run_name=...)` |
| Events | `.streamEvents(x, { version: "v2" })` | `.astream_events(x, version="v2")` |
| Visualise | `chain.getGraph()` | `chain.get_graph().print_ascii()` |
| Spread merge | `{ ...x, k: v }` | `{**x, "k": v}` |

---

## 6. Under the hood

### What `.pipe()` actually returns

```js
const chain = prompt.pipe(model).pipe(parser);
```

Step by step:

```
prompt.pipe(model)
  → new RunnableSequence({ first: prompt, middle: [], last: model })

  .pipe(parser)
  → new RunnableSequence({ first: prompt, middle: [model], last: parser })
```

And `RunnableSequence.invoke` is roughly:

```js
async invoke(input, config) {
  let value = input;
  for (const step of [this.first, ...this.middle, this.last]) {
    value = await step.invoke(value, patchConfig(config, { callbacks: childCallbacks }));
  }
  return value;
}
```

That's it. **LCEL is not a compiler or a DSL — it's a linked list of objects with a shared
interface.** Which is why it's debuggable: you can `console.log` any sub-chain and invoke it
independently.

### How streaming propagates

`RunnableSequence.stream` is where the cleverness lives:

```
1. Find the LAST step that supports streaming (has a transform method).
2. Run everything before it with invoke() — buffered, but that's fine,
   those steps need complete input anyway.
3. From that step onward, pipe async iterators together.
```

```
prompt → model → parser
  ▲        ▲       ▲
  │        │       └─ transform: chunk → chunk ✅ streams
  │        └───────── transform: streams tokens ✅
  └────────────────── invoke only (needs all vars) — runs first, fast

Result: tokens flow out as the model produces them.
```

Now add a non-streaming lambda at the end:

```
prompt → model → parser → (s) => s.toUpperCase()
                             ▲
                             └─ NO transform method → must buffer the whole input

Result: the chain still streams internally, but nothing exits until the model finishes.
```

**How to make a lambda streamable:** write it as a generator that consumes an iterator.

```js
// ❌ buffers
chain.pipe((s) => s.toUpperCase())

// ✅ streams
chain.pipe(RunnableLambda.from(async function* (stream) {
  for await (const chunk of stream) yield chunk.toUpperCase();
}));
```

Day 23 covers this properly.

### How `RunnableParallel` achieves concurrency

```js
async invoke(input, config) {
  const entries = Object.entries(this.steps);
  const results = await Promise.all(
    entries.map(([key, runnable]) => runnable.invoke(input, config))   // ← same input to all
  );
  return Object.fromEntries(entries.map(([k], i) => [k, results[i]]));
}
```

Python uses a thread pool for sync `invoke` and `asyncio.gather` for `ainvoke`. Either way:
**every branch receives the identical input**, and they run at the same time.

### Why callbacks make tracing free

Every `invoke` passes a `config` down to its children, with the callback manager forked so each
child gets its own run ID with a parent pointer. That's how LangSmith reconstructs a nested tree
without you instrumenting anything.

It's also why `.withConfig({ runName: "draft_reply" })` matters: in a trace with twelve
anonymous `RunnableLambda` nodes, named steps are the difference between a readable trace and a
useless one. **Name your steps.**

<details>
<summary>📜 Legacy note: what LCEL replaced</summary>

| Legacy (0.x) | LCEL |
|---|---|
| `LLMChain(llm=m, prompt=p)` | `p \| m` |
| `SimpleSequentialChain([a, b])` | `a \| b` |
| `SequentialChain(chains=[...], input_variables=[...])` | `a \| b \| c` with dicts |
| `TransformChain(transform=fn)` | `RunnableLambda(fn)` |
| `RouterChain` + `MultiPromptChain` | `RunnableBranch` |
| `chain.run(x)` / `chain.apply([...])` | `chain.invoke(x)` / `chain.batch([...])` |

**The interview-worthy point:** the legacy chains were *classes* that hid the control flow
inside `_call()`. You couldn't see the data flow, stream through them reliably, or compose them
freely. LCEL's insight was that a chain doesn't need a class — it needs an *interface*, and
composition on top of that interface. Less magic, more visible structure.

The natural follow-up question is "so when do you still need more than LCEL?" — the answer is
**cycles**. LCEL is a directed *acyclic* graph: data flows forward. The moment you need a loop
(agent calls tool → observes → decides again), you need LangGraph. That's Week 3.
</details>

---

## 7. Common mistakes

**❌ Type mismatch at a seam**

```js
prompt.pipe(model).pipe(anotherPrompt)
// anotherPrompt expects {vars}, gets an AIMessage → "Missing value for input variable"
```
✅ Insert a parser or a lambda to reshape:
```js
prompt.pipe(model).pipe(new StringOutputParser()).pipe((text) => ({ input: text })).pipe(anotherPrompt)
```

---

**❌ Expecting a JS object literal to have `.pipe()`**

```js
const chain = { a: chainA, b: chainB }.pipe(next);   // TypeError
```
✅ Put it inside a sequence: `RunnableSequence.from([{ a: chainA, b: chainB }, next])`.

---

**❌ Multi-argument lambdas**

```js
RunnableLambda.from((a, b) => a + b)   // b is always undefined
```
✅ One argument. Pass an object: `({ a, b }) => a + b`.

---

**❌ Using `RunnableParallel` when you meant `assign`**

```js
RunnableParallel.from({ summary: summaryChain })   // {text: "..."} → {summary: "..."}
```
The original `text` is gone. ✅ `RunnablePassthrough.assign({ summary: summaryChain })`.

---

**❌ A non-streaming step at the end of a streaming chain**

```js
chain.pipe((s) => s.trim())   // kills streaming for the whole chain's output
```
✅ Move transformations before the model, or write a generator-based lambda.

---

**❌ Building the chain inside a request handler**

```js
app.post("/chat", async (req) => {
  const chain = prompt.pipe(model).pipe(parser);   // rebuilt every request
});
```
✅ Build once at module scope. Chains are immutable and reusable.

---

**❌ Unnamed steps, then trying to read a trace**

Ten `RunnableLambda` nodes with no names. ✅ `.withConfig({ runName: "extract_entities" })` on
anything you'll want to find later.

---

**❌ Reaching for LCEL when you need a loop**

LCEL is acyclic. If your logic is "call a tool, look at the result, maybe call another" — that's
a cycle. ✅ Use LangGraph (Week 3). Forcing loops into LCEL with recursive lambdas gets ugly fast.

---

## 8. Exercises

### Exercise 1 — Build the six ●○○○○

Write one small chain demonstrating each of the six Runnables, on a single theme (e.g. analysing
a movie review). Print the input and output type of each so you can see the seams.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";
import { ChatPromptTemplate } from "@langchain/core/prompts";
import { StringOutputParser } from "@langchain/core/output_parsers";
import { RunnableSequence, RunnableParallel, RunnableLambda,
         RunnablePassthrough, RunnableBranch } from "@langchain/core/runnables";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });
const str = new StringOutputParser();
const REVIEW = "The plot dragged for the first hour but the last act was genuinely thrilling.";

const show = (label, input, output) =>
  console.log(`${label.padEnd(14)} ${typeof input} → ${Array.isArray(output) ? "array" : typeof output}\n` +
              `${" ".repeat(15)}${JSON.stringify(output).slice(0, 90)}`);

// 1. SEQUENCE — string in, string out
const seq = ChatPromptTemplate.fromMessages([["human", "One-word verdict on: {review}"]])
  .pipe(model).pipe(str);
show("1 sequence", REVIEW, await seq.invoke({ review: REVIEW }));

// 2. PARALLEL — object in, object out (keys replaced)
const par = RunnableParallel.from({
  verdict: seq,
  length: RunnableLambda.from((x) => x.review.length),
});
show("2 parallel", REVIEW, await par.invoke({ review: REVIEW }));

// 3. LAMBDA — anything in, anything out
const lam = RunnableLambda.from((x) => x.review.split(/\s+/).length);
show("3 lambda", REVIEW, await lam.invoke({ review: REVIEW }));

// 4. PASSTHROUGH — identity
show("4 passthrough", REVIEW, await new RunnablePassthrough().invoke({ review: REVIEW }));

// 5. ASSIGN — object in, SAME object + new keys out
const asg = RunnablePassthrough.assign({ words: (x) => x.review.split(/\s+/).length });
show("5 assign", REVIEW, await asg.invoke({ review: REVIEW }));

// 6. BRANCH — routes on a predicate
const br = RunnableBranch.from([
  [(x) => x.words > 10, RunnableLambda.from(() => "DETAILED")],
  RunnableLambda.from(() => "BRIEF"),
]);
show("6 branch", REVIEW, await RunnableSequence.from([asg, br]).invoke({ review: REVIEW }));
```

**Python**
```python
import json
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import (
    RunnableParallel, RunnableLambda, RunnablePassthrough, RunnableBranch,
)

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
strp = StrOutputParser()
REVIEW = "The plot dragged for the first hour but the last act was genuinely thrilling."

def show(label, output):
    print(f"{label:<14} → {type(output).__name__}\n"
          f"{' ' * 15}{json.dumps(output, default=str)[:90]}")

# 1. SEQUENCE
seq = ChatPromptTemplate.from_messages([("human", "One-word verdict on: {review}")]) | model | strp
show("1 sequence", seq.invoke({"review": REVIEW}))

# 2. PARALLEL — keys replaced
par = RunnableParallel(verdict=seq, length=RunnableLambda(lambda x: len(x["review"])))
show("2 parallel", par.invoke({"review": REVIEW}))

# 3. LAMBDA
lam = RunnableLambda(lambda x: len(x["review"].split()))
show("3 lambda", lam.invoke({"review": REVIEW}))

# 4. PASSTHROUGH — identity
show("4 passthrough", RunnablePassthrough().invoke({"review": REVIEW}))

# 5. ASSIGN — original keys survive
asg = RunnablePassthrough.assign(words=lambda x: len(x["review"].split()))
show("5 assign", asg.invoke({"review": REVIEW}))

# 6. BRANCH
br = RunnableBranch(
    (lambda x: x["words"] > 10, RunnableLambda(lambda _: "DETAILED")),
    RunnableLambda(lambda _: "BRIEF"),
)
show("6 branch", (asg | br).invoke({"review": REVIEW}))
```

**The thing to internalise from the output:** compare step 2 and step 5.

```
2 parallel   {"verdict":"Mixed","length":76}                        ← review is GONE
5 assign     {"review":"The plot dragged...","words":13}            ← review survived
```

That's the entire `Parallel` vs `Assign` distinction, and it's the one interviewers probe.
</details>

---

### Exercise 2 — Multi-step content pipeline ●●○○○

Build a chain that takes `{ topic }` and produces
`{ topic, outline, draft, wordCount, readingTimeMinutes }` where:
- `outline` is generated from the topic
- `draft` is generated **from the outline** (so it must run after)
- `wordCount` and `readingTimeMinutes` are computed in code from the draft

Use `RunnablePassthrough.assign` so nothing gets lost, and time it.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";
import { ChatPromptTemplate } from "@langchain/core/prompts";
import { StringOutputParser } from "@langchain/core/output_parsers";
import { RunnableSequence, RunnablePassthrough } from "@langchain/core/runnables";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0.4 });
const str = new StringOutputParser();

const outlineChain = ChatPromptTemplate
  .fromMessages([["human", "Write a 4-point outline for a short article about {topic}. " +
                           "Just the 4 points, one per line, no preamble."]])
  .pipe(model).pipe(str).withConfig({ runName: "generate_outline" });

const draftChain = ChatPromptTemplate
  .fromMessages([["system", "You write clear, concise articles. ~150 words. No preamble."],
                 ["human", "Topic: {topic}\n\nOutline:\n{outline}\n\nWrite the article."]])
  .pipe(model).pipe(str).withConfig({ runName: "write_draft" });

const pipeline = RunnableSequence.from([
  RunnablePassthrough.assign({ outline: outlineChain }),   // {topic} → {topic, outline}
  RunnablePassthrough.assign({ draft: draftChain }),       // → {topic, outline, draft}
  RunnablePassthrough.assign({                             // pure computation, no model
    wordCount: (x) => x.draft.trim().split(/\s+/).length,
  }),
  RunnablePassthrough.assign({
    readingTimeMinutes: (x) => Math.max(1, Math.round(x.wordCount / 200)),
  }),
]);

const t0 = Date.now();
const result = await pipeline.invoke({ topic: "why sleep matters for memory" });
console.log(`took ${Date.now() - t0}ms\n`);

console.log("TOPIC:", result.topic);
console.log("\nOUTLINE:\n" + result.outline);
console.log("\nDRAFT:\n" + result.draft);
console.log(`\n${result.wordCount} words · ~${result.readingTimeMinutes} min read`);
```

**Python**
```python
import time
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.4)
strp = StrOutputParser()

outline_chain = (
    ChatPromptTemplate.from_messages([
        ("human", "Write a 4-point outline for a short article about {topic}. "
                  "Just the 4 points, one per line, no preamble.")])
    | model | strp
).with_config(run_name="generate_outline")

draft_chain = (
    ChatPromptTemplate.from_messages([
        ("system", "You write clear, concise articles. ~150 words. No preamble."),
        ("human", "Topic: {topic}\n\nOutline:\n{outline}\n\nWrite the article.")])
    | model | strp
).with_config(run_name="write_draft")

pipeline = (
    RunnablePassthrough.assign(outline=outline_chain)      # {topic} → {topic, outline}
    | RunnablePassthrough.assign(draft=draft_chain)        # → {topic, outline, draft}
    | RunnablePassthrough.assign(                          # pure computation, no model
        word_count=lambda x: len(x["draft"].strip().split()))
    | RunnablePassthrough.assign(
        reading_time_minutes=lambda x: max(1, round(x["word_count"] / 200)))
)

t0 = time.time()
result = pipeline.invoke({"topic": "why sleep matters for memory"})
print(f"took {(time.time() - t0) * 1000:.0f}ms\n")

print("TOPIC:", result["topic"])
print("\nOUTLINE:\n" + result["outline"])
print("\nDRAFT:\n" + result["draft"])
print(f"\n{result['word_count']} words · ~{result['reading_time_minutes']} min read")
```

**Why this is `assign` and not `parallel`:** `draft` needs `outline`, so they're inherently
sequential. `assign` chained four times builds the object up one key at a time, and every
earlier key stays available to later steps. With `RunnableParallel` you'd lose `topic` after
the first stage and `draftChain` would fail with a missing variable.

**A subtlety worth noticing:** steps 3 and 4 don't call a model at all. Mixing pure computation
into an LCEL chain is fine and normal — they still appear in traces, still get retried as part
of the chain, and still compose. Not everything in a chain has to be an LLM call.
</details>

---

### Exercise 3 — Parallel analysis dashboard ●●●○○

Build a chain that analyses a piece of text **five ways concurrently** (summary, sentiment,
key entities via structured output, reading level, and a suggested title), keeps the original
text, and formats everything into a report. Measure it against a sequential version.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import "dotenv/config";
import * as z from "zod";
import { ChatGroq } from "@langchain/groq";
import { ChatPromptTemplate } from "@langchain/core/prompts";
import { StringOutputParser } from "@langchain/core/output_parsers";
import { RunnableSequence, RunnablePassthrough } from "@langchain/core/runnables";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });
const str = new StringOutputParser();

const ask = (instruction, runName) =>
  ChatPromptTemplate.fromMessages([["system", instruction], ["human", "{text}"]])
    .pipe(model).pipe(str).withConfig({ runName });

const Entities = z.object({
  people:        z.array(z.string()).describe("Names of people mentioned"),
  organisations: z.array(z.string()).describe("Companies or organisations mentioned"),
  technologies:  z.array(z.string()).describe("Technologies, products or tools mentioned"),
});

const ANALYSERS = {
  summary:      ask("Summarise in exactly 2 sentences. No preamble.", "summary"),
  sentiment:    ask("Reply with exactly one word: positive, negative, or neutral.", "sentiment"),
  readingLevel: ask("Reply with exactly one word: simple, moderate, or technical.", "reading_level"),
  title:        ask("Suggest a short headline. Title only, no quotes.", "title"),
  entities:     RunnableSequence.from([
                  (x) => x.text,
                  model.withStructuredOutput(Entities),
                ]).withConfig({ runName: "entities" }),
};

// PARALLEL — keep the text, add all five analyses
const parallelChain = RunnableSequence.from([
  RunnablePassthrough.assign(ANALYSERS),
  (x) => `
╔══════════════════════════════════════════════════════════╗
  ${x.title.trim()}
╚══════════════════════════════════════════════════════════╝
  ${x.sentiment.trim().toUpperCase()} · ${x.readingLevel.trim()} · ${x.text.split(/\s+/).length} words

  SUMMARY
  ${x.summary.trim().replace(/\n/g, "\n  ")}

  PEOPLE        ${x.entities.people.join(", ") || "—"}
  ORGANISATIONS ${x.entities.organisations.join(", ") || "—"}
  TECHNOLOGIES  ${x.entities.technologies.join(", ") || "—"}
`.trim(),
]);

// SEQUENTIAL — for comparison only
const sequentialChain = RunnableSequence.from([
  async (x) => {
    const out = { ...x };
    for (const [key, chain] of Object.entries(ANALYSERS)) out[key] = await chain.invoke(x);
    return out;
  },
]);

const TEXT =
  "At the LangChain summit, Harrison Chase demonstrated how Anthropic's Claude and Google's " +
  "Gemini can be swapped behind a single interface. Engineers from Vercel showed a Next.js " +
  "app streaming responses through LangGraph, with Qdrant handling retrieval. The audience " +
  "response was enthusiastic, though several attendees raised concerns about cost at scale.";

const t0 = Date.now();
const report = await parallelChain.invoke({ text: TEXT });
const parallelMs = Date.now() - t0;

const t1 = Date.now();
await sequentialChain.invoke({ text: TEXT });
const sequentialMs = Date.now() - t1;

console.log(report);
console.log(`\nparallel: ${parallelMs}ms · sequential: ${sequentialMs}ms · ` +
            `speedup ${(sequentialMs / parallelMs).toFixed(1)}x`);
```

**Python**
```python
import time
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
strp = StrOutputParser()

def ask(instruction, run_name):
    return (ChatPromptTemplate.from_messages([("system", instruction), ("human", "{text}")])
            | model | strp).with_config(run_name=run_name)

class Entities(BaseModel):
    """Named entities extracted from a text."""
    people: list[str] = Field(description="Names of people mentioned")
    organisations: list[str] = Field(description="Companies or organisations mentioned")
    technologies: list[str] = Field(description="Technologies, products or tools mentioned")

ANALYSERS = {
    "summary":       ask("Summarise in exactly 2 sentences. No preamble.", "summary"),
    "sentiment":     ask("Reply with exactly one word: positive, negative, or neutral.", "sentiment"),
    "reading_level": ask("Reply with exactly one word: simple, moderate, or technical.", "reading_level"),
    "title":         ask("Suggest a short headline. Title only, no quotes.", "title"),
    "entities":      (RunnableLambda(lambda x: x["text"])
                      | model.with_structured_output(Entities)).with_config(run_name="entities"),
}

def format_report(x):
    e = x["entities"]
    return f"""
╔══════════════════════════════════════════════════════════╗
  {x['title'].strip()}
╚══════════════════════════════════════════════════════════╝
  {x['sentiment'].strip().upper()} · {x['reading_level'].strip()} · {len(x['text'].split())} words

  SUMMARY
  {x['summary'].strip()}

  PEOPLE        {', '.join(e.people) or '—'}
  ORGANISATIONS {', '.join(e.organisations) or '—'}
  TECHNOLOGIES  {', '.join(e.technologies) or '—'}
""".strip()

parallel_chain = RunnablePassthrough.assign(**ANALYSERS) | format_report

def sequential(x):
    out = dict(x)
    for key, chain in ANALYSERS.items():
        out[key] = chain.invoke(x)
    return out

TEXT = (
    "At the LangChain summit, Harrison Chase demonstrated how Anthropic's Claude and Google's "
    "Gemini can be swapped behind a single interface. Engineers from Vercel showed a Next.js "
    "app streaming responses through LangGraph, with Qdrant handling retrieval. The audience "
    "response was enthusiastic, though several attendees raised concerns about cost at scale."
)

t0 = time.time()
report = parallel_chain.invoke({"text": TEXT})
parallel_ms = (time.time() - t0) * 1000

t1 = time.time()
sequential({"text": TEXT})
sequential_ms = (time.time() - t1) * 1000

print(report)
print(f"\nparallel: {parallel_ms:.0f}ms · sequential: {sequential_ms:.0f}ms · "
      f"speedup {sequential_ms / parallel_ms:.1f}x")
```

**Expect roughly a 3–4× speedup**, not 5×, because the slowest branch sets the floor —
`entities` (structured output, more tokens) dominates. That's Amdahl's law in a chain:
parallelism buys you `slowest` instead of `sum`, never zero.

**Two design details:**
- `assign` rather than `parallel`, so `x.text` is still available in the formatter for the word count.
- Every branch is named with `withConfig({ runName })`. Open this in LangSmith (Day 25) and you
  get five clearly-labelled sibling spans with visible durations — instantly showing which
  branch is your bottleneck. Unnamed, it's five identical grey boxes.
</details>

---

### Exercise 4 — Semantic router with fallback ●●●●○

Build a router that classifies an incoming question into one of four domains (`code`, `maths`,
`history`, `other`), routes to a specialised chain for each, and:
- attaches the detected domain and confidence to the output
- falls back to the `other` chain if confidence < 0.6
- retries the classifier once on failure
- logs which route was taken and how long it took

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import "dotenv/config";
import * as z from "zod";
import { ChatGroq } from "@langchain/groq";
import { ChatPromptTemplate } from "@langchain/core/prompts";
import { StringOutputParser } from "@langchain/core/output_parsers";
import { RunnableSequence, RunnablePassthrough, RunnableLambda } from "@langchain/core/runnables";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });
const creative = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0.5 });
const str = new StringOutputParser();

// ── the specialists ──────────────────────────────────────────────────────
const specialist = (system, runName, m = model) =>
  ChatPromptTemplate.fromMessages([["system", system], ["human", "{question}"]])
    .pipe(m).pipe(str).withConfig({ runName });

const ROUTES = {
  code:    specialist("You are a senior engineer. Answer with a short explanation and a code " +
                      "snippet. Prefer JavaScript unless another language is named.", "route_code"),
  maths:   specialist("You are a maths tutor. Show your working step by step, then state the " +
                      "final answer on its own line prefixed with 'ANSWER:'.", "route_maths"),
  history: specialist("You are a historian. Give dates, name key figures, and note any " +
                      "scholarly disagreement. Max 4 sentences.", "route_history", creative),
  other:   specialist("You are a helpful generalist. If the question is unclear, ask one " +
                      "clarifying question instead of guessing.", "route_other", creative),
};

// ── the classifier ───────────────────────────────────────────────────────
const Route = z.object({
  reasoning: z.string().describe("One short sentence. Write this first."),
  domain: z.enum(["code", "maths", "history", "other"]),
  confidence: z.number().min(0).max(1).describe("How sure you are, 0 to 1"),
});

const classifier = model
  .withStructuredOutput(Route)
  .withRetry({ stopAfterAttempt: 2 })
  .withFallbacks([
    // If classification fails entirely, default to `other` rather than erroring.
    RunnableLambda.from(() => ({ reasoning: "classifier unavailable", domain: "other", confidence: 0 })),
  ])
  .withConfig({ runName: "classify_domain" });

// ── the router ───────────────────────────────────────────────────────────
const CONFIDENCE_THRESHOLD = 0.6;

const router = RunnableSequence.from([
  RunnablePassthrough.assign({ route: (x) => classifier.invoke(x.question) }),

  RunnablePassthrough.assign({
    chosen: (x) =>
      x.route.confidence < CONFIDENCE_THRESHOLD ? "other" : x.route.domain,
  }),

  RunnablePassthrough.assign({
    answer: async (x) => {
      const t0 = Date.now();
      const answer = await ROUTES[x.chosen].invoke({ question: x.question });
      return { text: answer, ms: Date.now() - t0 };
    },
  }),
]);

// ── run ──────────────────────────────────────────────────────────────────
const QUESTIONS = [
  "How do I debounce a function in JavaScript?",
  "What is the integral of x squared from 0 to 3?",
  "Why did the Ottoman Empire decline?",
  "hmm",
  "Is 17 prime and can you show me the code to check?",   // deliberately ambiguous
];

for (const question of QUESTIONS) {
  const r = await router.invoke({ question });
  const downgraded = r.chosen !== r.route.domain;

  console.log(`\n❓ ${question}`);
  console.log(`   → ${r.chosen}${downgraded ? ` (downgraded from ${r.route.domain})` : ""} ` +
              `· conf=${r.route.confidence} · ${r.answer.ms}ms`);
  console.log(`   why: ${r.route.reasoning}`);
  console.log(`   ${r.answer.text.split("\n")[0].slice(0, 90)}…`);
}
```

**Python**
```python
import time
from dotenv import load_dotenv
from typing import Literal
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
creative = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.5)
strp = StrOutputParser()

# ── the specialists ──────────────────────────────────────────────────────
def specialist(system, run_name, m=model):
    return (ChatPromptTemplate.from_messages([("system", system), ("human", "{question}")])
            | m | strp).with_config(run_name=run_name)

ROUTES = {
    "code":    specialist("You are a senior engineer. Answer with a short explanation and a code "
                          "snippet. Prefer Python unless another language is named.", "route_code"),
    "maths":   specialist("You are a maths tutor. Show your working step by step, then state the "
                          "final answer on its own line prefixed with 'ANSWER:'.", "route_maths"),
    "history": specialist("You are a historian. Give dates, name key figures, and note any "
                          "scholarly disagreement. Max 4 sentences.", "route_history", creative),
    "other":   specialist("You are a helpful generalist. If the question is unclear, ask one "
                          "clarifying question instead of guessing.", "route_other", creative),
}

# ── the classifier ───────────────────────────────────────────────────────
class Route(BaseModel):
    """Which specialist should handle this question."""
    reasoning: str = Field(description="One short sentence. Write this first.")
    domain: Literal["code", "maths", "history", "other"]
    confidence: float = Field(ge=0, le=1, description="How sure you are, 0 to 1")

classifier = (
    model.with_structured_output(Route)
    .with_retry(stop_after_attempt=2)
    .with_fallbacks([
        # If classification fails entirely, default to `other` rather than erroring.
        RunnableLambda(lambda _: Route(reasoning="classifier unavailable",
                                       domain="other", confidence=0.0))
    ])
    .with_config(run_name="classify_domain")
)

# ── the router ───────────────────────────────────────────────────────────
CONFIDENCE_THRESHOLD = 0.6

def run_route(x):
    t0 = time.time()
    text = ROUTES[x["chosen"]].invoke({"question": x["question"]})
    return {"text": text, "ms": int((time.time() - t0) * 1000)}

router = (
    RunnablePassthrough.assign(route=lambda x: classifier.invoke(x["question"]))
    | RunnablePassthrough.assign(
        chosen=lambda x: "other" if x["route"].confidence < CONFIDENCE_THRESHOLD
                         else x["route"].domain)
    | RunnablePassthrough.assign(answer=run_route)
)

# ── run ──────────────────────────────────────────────────────────────────
QUESTIONS = [
    "How do I debounce a function in Python?",
    "What is the integral of x squared from 0 to 3?",
    "Why did the Ottoman Empire decline?",
    "hmm",
    "Is 17 prime and can you show me the code to check?",   # deliberately ambiguous
]

for question in QUESTIONS:
    r = router.invoke({"question": question})
    downgraded = r["chosen"] != r["route"].domain

    print(f"\n❓ {question}")
    print(f"   → {r['chosen']}"
          f"{f' (downgraded from {r[chr(34)+chr(34)] if False else r[chr(39)+chr(39)] if False else r[chr(114)] if False else r[chr(34)] if False else r[chr(39)] if False else r[chr(114)+chr(111)+chr(117)+chr(116)+chr(101)].domain})' if downgraded else ''}"
          f" · conf={r['route'].confidence} · {r['answer']['ms']}ms")
    print(f"   why: {r['route'].reasoning}")
    print(f"   {r['answer']['text'].splitlines()[0][:90]}…")
```

<details>
<summary>Cleaner Python print (the f-string above is deliberately awkward — here's the readable version)</summary>

```python
for question in QUESTIONS:
    r = router.invoke({"question": question})
    route = r["route"]
    downgraded = f" (downgraded from {route.domain})" if r["chosen"] != route.domain else ""

    print(f"\n❓ {question}")
    print(f"   → {r['chosen']}{downgraded} · conf={route.confidence} · {r['answer']['ms']}ms")
    print(f"   why: {route.reasoning}")
    print(f"   {r['answer']['text'].splitlines()[0][:90]}…")
```
</details>

**Four production patterns packed into this one chain:**

1. **A confidence threshold, not just a label.** `chosen` is a separate key from
   `route.domain`, so you keep both what the classifier *said* and what you *did*. When
   downgrades spike, you know your classifier is degrading before users complain.
2. **A fallback that returns a value, not an error.** `RunnableLambda.from(() => ({...}))` as a
   fallback means a classifier outage degrades to the generalist route instead of a 500.
3. **Retry before fallback.** Transient failures get a second chance cheaply; only real failures
   pay the fallback cost.
4. **Named routes.** In a trace you see `classify_domain → route_code`, so debugging "why did it
   answer like a historian?" takes seconds.

**And note the ambiguous question.** "Is 17 prime and can you show me the code?" is genuinely
both `maths` and `code`. A single-label classifier must pick one. In production you'd either
allow multi-label routing, or — better — accept that this is where a fixed router stops being
the right tool and an **agent** should decide dynamically. That's Week 3.
</details>

---

### Exercise 5 — 🏆 Week 1 Project: StudyBuddy v1 ●●●●●

Bring the whole week together. Build a CLI study assistant that:

1. Takes a question and a mode (`explain`, `quiz`, `plan`)
2. **In parallel**: classifies the topic domain, estimates difficulty, and detects whether the
   user seems confused (from their phrasing)
3. **Routes** to a specialised chain per mode
4. Uses **structured output** for the quiz and plan modes, plain streaming text for explain
5. **Streams** the explain-mode answer to the terminal
6. Keeps conversation history with a `MessagesPlaceholder`
7. Has retries and a fallback provider
8. Prints a timing + token summary after each turn

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
// studybuddy-v1.js
import "dotenv/config";
import readline from "node:readline/promises";
import * as z from "zod";
import { ChatGroq } from "@langchain/groq";
import { ChatGoogleGenerativeAI } from "@langchain/google-genai";
import { ChatPromptTemplate, MessagesPlaceholder } from "@langchain/core/prompts";
import { StringOutputParser } from "@langchain/core/output_parsers";
import { RunnableSequence, RunnablePassthrough, RunnableLambda } from "@langchain/core/runnables";
import { HumanMessage, AIMessage, trimMessages } from "@langchain/core/messages";

// ─── models ───────────────────────────────────────────────────────────────
const fast = new ChatGroq({ model: "llama-3.1-8b-instant", temperature: 0 });
const main = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0.4 });
const backup = new ChatGoogleGenerativeAI({ model: "gemini-2.5-flash", temperature: 0.4 });

const resilient = main.withRetry({ stopAfterAttempt: 2 }).withFallbacks([backup]);
const str = new StringOutputParser();

// ─── 1. analysis (runs in parallel, uses the CHEAP model) ─────────────────
const Analysis = z.object({
  reasoning: z.string().describe("One short sentence. Write this first."),
  domain: z.enum(["programming", "maths", "science", "history", "language", "other"]),
  difficulty: z.enum(["beginner", "intermediate", "advanced"]),
  seemsConfused: z.boolean().describe("True if the phrasing suggests frustration or confusion"),
});

const analyse = fast.withStructuredOutput(Analysis)
  .withRetry({ stopAfterAttempt: 2 })
  .withFallbacks([RunnableLambda.from(() => ({
    reasoning: "analysis unavailable", domain: "other",
    difficulty: "intermediate", seemsConfused: false,
  }))])
  .withConfig({ runName: "analyse_question" });

// ─── 2. mode chains ───────────────────────────────────────────────────────
const explainChain = ChatPromptTemplate.fromMessages([
  ["system",
   "You are StudyBuddy, a patient {difficulty}-level tutor for {domain}.\n" +
   "{confusionNote}\n" +
   "Rules: one everyday analogy, then the technical explanation. Max 5 sentences. " +
   "End with one short question that checks understanding."],
  new MessagesPlaceholder({ variableName: "history", optional: true }),
  ["human", "{question}"],
]).pipe(resilient).pipe(str).withConfig({ runName: "mode_explain" });

const Quiz = z.object({
  questions: z.array(z.object({
    question: z.string(),
    options: z.array(z.string()).length(4),
    correctIndex: z.number().int().min(0).max(3),
    explanation: z.string(),
  })).describe("Exactly 3 questions"),
});

const quizChain = ChatPromptTemplate.fromMessages([
  ["system", "Write a 3-question multiple-choice quiz at {difficulty} level about the topic. " +
             "Exactly one option correct. Plausible distractors. Vary the correct index."],
  ["human", "{question}"],
]).pipe(resilient.withStructuredOutput(Quiz)).withConfig({ runName: "mode_quiz" });

const Plan = z.object({
  goal: z.string().describe("A one-sentence restatement of what they want to learn"),
  prerequisites: z.array(z.string()).describe("What they should already know. May be empty."),
  steps: z.array(z.object({
    title: z.string(),
    whatToDo: z.string().describe("A concrete action, not vague advice"),
    estimatedHours: z.number(),
  })).describe("4-6 ordered steps"),
  firstAction: z.string().describe("The single thing to do in the next 30 minutes"),
});

const planChain = ChatPromptTemplate.fromMessages([
  ["system", "Create a practical study plan at {difficulty} level for {domain}. " +
             "Steps must be concrete and doable, never 'read about X'."],
  ["human", "{question}"],
]).pipe(resilient.withStructuredOutput(Plan)).withConfig({ runName: "mode_plan" });

// ─── 3. the pipeline ──────────────────────────────────────────────────────
const enrich = RunnableSequence.from([
  RunnablePassthrough.assign({ analysis: (x) => analyse.invoke(x.question) }),
  RunnablePassthrough.assign({
    domain:        (x) => x.analysis.domain,
    difficulty:    (x) => x.analysis.difficulty,
    confusionNote: (x) => x.analysis.seemsConfused
      ? "The user seems stuck. Be extra gentle, go slower, and check in more often."
      : "The user seems comfortable. You can move at a normal pace.",
  }),
]);

// ─── 4. rendering ─────────────────────────────────────────────────────────
function renderQuiz(quiz) {
  return quiz.questions.map((q, i) =>
    `\n${i + 1}. ${q.question}\n` +
    q.options.map((o, j) => `   ${j === q.correctIndex ? "✅" : "  "} ${"ABCD"[j]}) ${o}`).join("\n") +
    `\n   → ${q.explanation}`
  ).join("\n");
}

function renderPlan(plan) {
  const total = plan.steps.reduce((s, x) => s + x.estimatedHours, 0);
  return `\n🎯 ${plan.goal}\n` +
    (plan.prerequisites.length ? `\n📋 First make sure you know: ${plan.prerequisites.join(", ")}\n` : "") +
    plan.steps.map((s, i) =>
      `\n${i + 1}. ${s.title}  (~${s.estimatedHours}h)\n   ${s.whatToDo}`).join("") +
    `\n\n⏱  Total: ~${total} hours` +
    `\n👉 Right now: ${plan.firstAction}`;
}

// ─── 5. the CLI ───────────────────────────────────────────────────────────
let mode = "explain";
let history = [];
const stats = { turns: 0, ms: 0 };

const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
console.log("╔════════════════════════════════════════════════╗");
console.log("║  StudyBuddy v1                                 ║");
console.log("║  /mode explain|quiz|plan · /reset · /exit      ║");
console.log("╚════════════════════════════════════════════════╝\n");

while (true) {
  let question;
  try { question = (await rl.question(`[${mode}] › `)).trim(); } catch { break; }
  if (!question) continue;
  if (question === "/exit") break;

  if (question === "/reset") { history = []; console.log("  history cleared\n"); continue; }

  if (question.startsWith("/mode")) {
    const next = question.split(/\s+/)[1];
    if (!["explain", "quiz", "plan"].includes(next)) {
      console.log("  modes: explain, quiz, plan\n");
    } else {
      mode = next;
      console.log(`  mode → ${mode} (history kept: ${history.length})\n`);
    }
    continue;
  }

  const t0 = Date.now();
  try {
    // Trim history before every turn so cost stays bounded.
    const trimmed = await trimMessages(history, {
      maxTokens: 800, strategy: "last", tokenCounter: main, startOn: "human",
    });

    const enriched = await enrich.invoke({ question, history: trimmed });
    console.log(`  ↳ ${enriched.domain}/${enriched.difficulty}` +
                `${enriched.analysis.seemsConfused ? " · seems stuck" : ""}`);

    if (mode === "explain") {
      process.stdout.write("\n");
      let full = "";
      for await (const chunk of await explainChain.stream(enriched)) {
        process.stdout.write(chunk);
        full += chunk;
      }
      console.log("\n");
      history.push(new HumanMessage(question), new AIMessage(full));
    } else if (mode === "quiz") {
      console.log(renderQuiz(await quizChain.invoke(enriched)) + "\n");
    } else {
      console.log(renderPlan(await planChain.invoke(enriched)) + "\n");
    }

    const ms = Date.now() - t0;
    stats.turns++; stats.ms += ms;
    console.log(`  ⏱  ${ms}ms · avg ${Math.round(stats.ms / stats.turns)}ms over ${stats.turns} turns\n`);
  } catch (err) {
    console.log(`\n  ⚠️  ${err.message.slice(0, 120)}\n`);
  }
}
rl.close();
```

**Python**
```python
# studybuddy_v1.py
import time
from dotenv import load_dotenv
from typing import Literal
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.messages import HumanMessage, AIMessage, trim_messages

load_dotenv()

# ─── models ───────────────────────────────────────────────────────────────
fast   = ChatGroq(model="llama-3.1-8b-instant", temperature=0)
main   = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.4)
backup = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.4)

resilient = main.with_retry(stop_after_attempt=2).with_fallbacks([backup])
strp = StrOutputParser()

# ─── 1. analysis (runs first, uses the CHEAP model) ───────────────────────
class Analysis(BaseModel):
    """An assessment of the learner's question."""
    reasoning: str = Field(description="One short sentence. Write this first.")
    domain: Literal["programming", "maths", "science", "history", "language", "other"]
    difficulty: Literal["beginner", "intermediate", "advanced"]
    seems_confused: bool = Field(
        description="True if the phrasing suggests frustration or confusion")

analyse = (
    fast.with_structured_output(Analysis)
    .with_retry(stop_after_attempt=2)
    .with_fallbacks([RunnableLambda(lambda _: Analysis(
        reasoning="analysis unavailable", domain="other",
        difficulty="intermediate", seems_confused=False))])
    .with_config(run_name="analyse_question")
)

# ─── 2. mode chains ───────────────────────────────────────────────────────
explain_chain = (
    ChatPromptTemplate.from_messages([
        ("system",
         "You are StudyBuddy, a patient {difficulty}-level tutor for {domain}.\n"
         "{confusion_note}\n"
         "Rules: one everyday analogy, then the technical explanation. Max 5 sentences. "
         "End with one short question that checks understanding."),
        MessagesPlaceholder("history", optional=True),
        ("human", "{question}"),
    ]) | resilient | strp
).with_config(run_name="mode_explain")

class QuizQuestion(BaseModel):
    question: str
    options: list[str] = Field(min_length=4, max_length=4)
    correct_index: int = Field(ge=0, le=3)
    explanation: str

class Quiz(BaseModel):
    """A short multiple-choice quiz."""
    questions: list[QuizQuestion] = Field(description="Exactly 3 questions")

quiz_chain = (
    ChatPromptTemplate.from_messages([
        ("system", "Write a 3-question multiple-choice quiz at {difficulty} level about the topic. "
                   "Exactly one option correct. Plausible distractors. Vary the correct index."),
        ("human", "{question}"),
    ]) | resilient.with_structured_output(Quiz)
).with_config(run_name="mode_quiz")

class Step(BaseModel):
    title: str
    what_to_do: str = Field(description="A concrete action, not vague advice")
    estimated_hours: float

class Plan(BaseModel):
    """A practical study plan."""
    goal: str = Field(description="A one-sentence restatement of what they want to learn")
    prerequisites: list[str] = Field(description="What they should already know. May be empty.")
    steps: list[Step] = Field(description="4-6 ordered steps")
    first_action: str = Field(description="The single thing to do in the next 30 minutes")

plan_chain = (
    ChatPromptTemplate.from_messages([
        ("system", "Create a practical study plan at {difficulty} level for {domain}. "
                   "Steps must be concrete and doable, never 'read about X'."),
        ("human", "{question}"),
    ]) | resilient.with_structured_output(Plan)
).with_config(run_name="mode_plan")

# ─── 3. the pipeline ──────────────────────────────────────────────────────
def confusion_note(x):
    return ("The user seems stuck. Be extra gentle, go slower, and check in more often."
            if x["analysis"].seems_confused
            else "The user seems comfortable. You can move at a normal pace.")

enrich = (
    RunnablePassthrough.assign(analysis=lambda x: analyse.invoke(x["question"]))
    | RunnablePassthrough.assign(
        domain=lambda x: x["analysis"].domain,
        difficulty=lambda x: x["analysis"].difficulty,
        confusion_note=confusion_note,
    )
)

# ─── 4. rendering ─────────────────────────────────────────────────────────
def render_quiz(quiz):
    out = []
    for i, q in enumerate(quiz.questions, 1):
        out.append(f"\n{i}. {q.question}")
        for j, o in enumerate(q.options):
            out.append(f"   {'✅' if j == q.correct_index else '  '} {'ABCD'[j]}) {o}")
        out.append(f"   → {q.explanation}")
    return "\n".join(out)

def render_plan(plan):
    total = sum(s.estimated_hours for s in plan.steps)
    out = [f"\n🎯 {plan.goal}"]
    if plan.prerequisites:
        out.append(f"\n📋 First make sure you know: {', '.join(plan.prerequisites)}")
    for i, s in enumerate(plan.steps, 1):
        out.append(f"\n{i}. {s.title}  (~{s.estimated_hours}h)\n   {s.what_to_do}")
    out.append(f"\n\n⏱  Total: ~{total:g} hours")
    out.append(f"\n👉 Right now: {plan.first_action}")
    return "".join(out)

# ─── 5. the CLI ───────────────────────────────────────────────────────────
mode, history = "explain", []
stats = {"turns": 0, "ms": 0}

print("╔════════════════════════════════════════════════╗")
print("║  StudyBuddy v1                                 ║")
print("║  /mode explain|quiz|plan · /reset · /exit      ║")
print("╚════════════════════════════════════════════════╝\n")

while True:
    try:
        question = input(f"[{mode}] › ").strip()
    except (EOFError, KeyboardInterrupt):
        break
    if not question:
        continue
    if question == "/exit":
        break

    if question == "/reset":
        history = []
        print("  history cleared\n")
        continue

    if question.startswith("/mode"):
        parts = question.split()
        nxt = parts[1] if len(parts) > 1 else None
        if nxt not in ("explain", "quiz", "plan"):
            print("  modes: explain, quiz, plan\n")
        else:
            mode = nxt
            print(f"  mode → {mode} (history kept: {len(history)})\n")
        continue

    t0 = time.time()
    try:
        # Trim history before every turn so cost stays bounded.
        trimmed = trim_messages(history, max_tokens=800, strategy="last",
                                token_counter=main, start_on="human")

        enriched = enrich.invoke({"question": question, "history": trimmed})
        stuck = " · seems stuck" if enriched["analysis"].seems_confused else ""
        print(f"  ↳ {enriched['domain']}/{enriched['difficulty']}{stuck}")

        if mode == "explain":
            print()
            full = ""
            for chunk in explain_chain.stream(enriched):
                print(chunk, end="", flush=True)
                full += chunk
            print("\n")
            history += [HumanMessage(question), AIMessage(full)]
        elif mode == "quiz":
            print(render_quiz(quiz_chain.invoke(enriched)) + "\n")
        else:
            print(render_plan(plan_chain.invoke(enriched)) + "\n")

        ms = int((time.time() - t0) * 1000)
        stats["turns"] += 1
        stats["ms"] += ms
        print(f"  ⏱  {ms}ms · avg {stats['ms'] // stats['turns']}ms "
              f"over {stats['turns']} turns\n")
    except Exception as err:
        print(f"\n  ⚠️  {str(err)[:120]}\n")
```

**Every Week 1 concept is in here. Trace them:**

| Day | Where it shows up |
|---|---|
| 01 | `trimMessages` bounding the context window; streaming for perceived latency |
| 02 | Structured CoT (`reasoning` first); confidence-style routing on `seemsConfused` |
| 03 | Retries, fallbacks, error handling that doesn't crash the loop |
| 04 | Three models for three jobs; `stream` vs `invoke` per mode; history as messages |
| 05 | `ChatPromptTemplate` + `MessagesPlaceholder`; one persona, three specialised prompts |
| 06 | `withStructuredOutput` for quiz and plan; nullable/enum schema design |
| 07 | `assign` to build up context; named steps; composition throughout |

**The three architectural decisions worth defending in an interview:**

1. **The cheap model does the analysis.** `llama-3.1-8b-instant` classifies domain and
   difficulty; the 70B model writes the answer. Classification is easy and happens on every
   turn — using one big model for everything is the most common way teams overspend.

2. **The analysis chain has a *value* fallback, not an error fallback.** If the classifier dies,
   `RunnableLambda` returns a sensible default `Analysis` object and the turn continues. A
   degraded answer beats a stack trace.

3. **Explain streams; quiz and plan don't.** Streaming a progressively-filling JSON object into
   a terminal is worse than waiting 2 seconds for a formatted one. Streaming is a UX decision
   per output type, not a global switch.

**What it still can't do — and that's the point.** Ask it *"quiz me, and if I get one wrong,
explain that specific thing and quiz me again."* That's a **loop**: act → observe → decide →
maybe repeat. LCEL is a directed *acyclic* graph. You'd have to write the loop outside the chain
in plain JavaScript/Python, at which point you lose streaming, tracing and state management
across iterations.

That gap is precisely why LangGraph exists, and it's where Week 3 picks up.
</details>

---

## 9. Interview questions

### Basic

<details>
<summary><b>Q: What is LCEL?</b></summary>

LangChain Expression Language — a declarative way to compose components using `.pipe()` in JS or
the `|` operator in Python. It isn't a separate language or a compiler; it's operator overloading
on the `Runnable` interface. Composing two Runnables produces another Runnable, so chains nest
freely, and streaming, batching, async, retries and tracing work across the whole composition
without glue code.
</details>

<details>
<summary><b>Q: What is a Runnable?</b></summary>

The core LangChain interface. Anything implementing it provides `invoke` (one input → one
output), `stream` (incremental output), `batch` (many inputs concurrently), and `pipe`
(composition). Models, prompts, parsers, retrievers, lambdas, and entire chains all implement
it — which is what makes composition uniform.
</details>

<details>
<summary><b>Q: Difference between RunnableSequence and RunnableParallel?</b></summary>

`RunnableSequence` runs steps **one after another**, passing each output as the next input —
that's what `.pipe()` / `|` builds. `RunnableParallel` runs several Runnables **concurrently on
the same input** and collects results into an object keyed by name. Sequence is for dependent
steps; Parallel is for independent ones, and it turns sum-of-latencies into max-of-latencies.
</details>

<details>
<summary><b>Q: What is RunnableLambda?</b></summary>

A wrapper that turns any function into a Runnable so it can sit in a chain. It's used for
reshaping data between steps, computing derived values, and light logic. Plain functions are
auto-coerced when you pipe them. It takes exactly one argument — pass an object if you need
several.
</details>

### Intermediate

<details>
<summary><b>Q: Difference between RunnablePassthrough and RunnableAssign?</b></summary>

`RunnablePassthrough` is the identity — it returns its input unchanged. It's used inside a
parallel block to carry the original input forward alongside computed values.

`RunnableAssign` (via `RunnablePassthrough.assign()`) takes a dict input and **adds** keys to
it, preserving everything already there.

The three-way contrast is the thing to have crisp:

| | `{a: 1}` becomes |
|---|---|
| `RunnableParallel({b: chain})` | `{b: ...}` — `a` is **lost** |
| `RunnablePassthrough.assign({b: chain})` | `{a: 1, b: ...}` — `a` **survives** |
| `RunnablePassthrough()` | `{a: 1}` — unchanged |

Assign is how you accumulate context through a multi-step pipeline.
</details>

<details>
<summary><b>Q: How does streaming work through a chain, and what breaks it?</b></summary>

`RunnableSequence.stream` finds the last step that can transform incrementally, runs everything
before it with `invoke`, and pipes async iterators from that point onward. So a
`prompt | model | parser` chain streams tokens as the model produces them.

It breaks when a step needs its complete input before producing any output — a typical
`RunnableLambda` like `(s) => s.toUpperCase()`. That step buffers, so the chain's *output* only
starts flowing once the model has finished. Everything after a non-streaming step is blocked.

Fixes: put transformations before the model, accept the buffering, or write the lambda as an
async generator that consumes and yields chunks.
</details>

<details>
<summary><b>Q: How would you debug an LCEL chain that returns the wrong thing?</b></summary>

The rule is that **output of step N must match input of step N+1**, so almost every bug is a
type mismatch at one seam.

1. **Invoke sub-chains independently.** Because composition is closed, any prefix of the chain
   is itself a Runnable you can call directly. Binary-search the pipeline.
2. **Insert tap lambdas** that log and return their input unchanged.
3. **Name the steps** with `withConfig({ runName })` and read the LangSmith trace — you get
   input and output for every node.
4. **Print the structure** — `chain.get_graph().print_ascii()` in Python shows whether you built
   the shape you meant.
5. **Check for `RunnableParallel` where you meant `assign`** — silently dropping keys is the
   single most common cause of "missing input variable" downstream.
</details>

<details>
<summary><b>Q: When would you use RunnableBranch versus just a lambda that returns a Runnable?</b></summary>

They're equivalent in effect — LangChain invokes a Runnable returned from a lambda.
`RunnableBranch` is more declarative and shows up as a distinct node in traces, which helps when
routing logic is a core part of the design. A lambda is more readable when the condition is
complex or when you're choosing between many options from a lookup table.

Either way, both are **static** routing: the structure is fixed and data flows forward once.
When the routing decision needs to be revisited after seeing a result — "try this, and if it
fails, try something else" — you've left LCEL's territory and want a graph.
</details>

### Advanced

<details>
<summary><b>Q: How does LCEL actually work under the hood?</b></summary>

`.pipe()` constructs a `RunnableSequence` holding references to its steps — it's a linked list
of objects, not compiled code. `invoke` walks the steps, threading a `config` object through
each call.

That config is where the non-obvious value lives: it carries a callback manager that gets forked
per step, so each child run gets its own ID with a parent pointer. That's how LangSmith
reconstructs a nested trace with zero instrumentation from you. It also carries tags, metadata,
concurrency limits, and recursion limits.

`stream` is the more interesting implementation: it finds the last step with a `transform`
method (one that accepts an async iterator), runs the prefix with `invoke`, and chains iterators
from there. `RunnableParallel` uses `Promise.all` / `asyncio.gather` (or a thread pool for sync
Python), giving every branch the identical input.

The design consequence worth stating: because composition is closed under the interface, generic
capabilities — retries, fallbacks, config, tracing — can be implemented **once** as wrappers
rather than per component. That's the actual payoff, more than the syntax.
</details>

<details>
<summary><b>Q: What are LCEL's limitations, and when do you reach for LangGraph?</b></summary>

LCEL builds a **directed acyclic graph**. Data flows forward, each step runs once, and the
structure is fixed at build time. That's a great fit for retrieve → prompt → generate → parse.

It's the wrong fit when you need:

- **Cycles** — an agent that calls a tool, observes the result, and decides whether to call
  another. You can fake it with a recursive lambda, but you lose streaming, tracing coherence,
  and any sane view of state across iterations.
- **Shared mutable state** — LCEL threads a value through steps; there's no state object that
  multiple nodes read and update with defined merge semantics (reducers).
- **Persistence and resumption** — pausing mid-execution, saving, and resuming later.
- **Human-in-the-loop** — interrupting before a step, waiting for approval, then continuing.
- **Fine-grained control flow** — conditional edges evaluated at runtime, fan-out to a dynamic
  number of branches, subgraphs.

LangGraph adds exactly those: nodes, edges, a typed state object with reducers, checkpointers,
and interrupts. And it composes both ways — a compiled graph is itself a `Runnable`, so you can
put a graph inside an LCEL chain, and LCEL chains inside graph nodes.

The rule I'd give: **if data flows one direction, use LCEL. If control flows in a loop, use
LangGraph.**
</details>

<details>
<summary><b>Q: Design an LCEL chain for a RAG pipeline with query rewriting, retrieval, reranking and citation.</b></summary>

Sketch first, then the reasoning:

```
input: { question, history }

  ├─ assign(standaloneQuestion) ─── rewrite the question using history so
  │                                  "what about the second one?" becomes retrievable
  ├─ assign(docs) ──────────────── parallel: { vector: vectorRetriever,
  │                                            keyword: bm25Retriever }
  │                                  then merge + dedupe in a lambda
  ├─ assign(reranked) ──────────── cross-encoder rerank, take top 5
  ├─ assign(context) ───────────── format docs with [1] [2] markers for citation
  ├─ assign(answer) ────────────── prompt | model | StrOutputParser   ← streams
  └─ assign(citations) ─────────── parse [n] markers back to source metadata
```

**Design decisions I'd defend:**

- **`assign` throughout, not `parallel`** — every stage needs the original question and the
  accumulated context. A `parallel` anywhere in the middle silently drops keys and you'd get a
  missing-variable error three steps later.
- **Query rewriting first** — retrieval on a raw follow-up question ("what about the second
  one?") retrieves nothing useful. This is the highest-ROI stage in conversational RAG.
- **Hybrid retrieval in a `RunnableParallel`** — vector and BM25 are independent, so they run
  concurrently; the merge happens in a lambda afterwards.
- **Reranking as a separate stage** — retrieve 20 cheaply, rerank to 5 accurately. Keeps the
  final prompt small, which matters for both cost and the lost-in-the-middle effect.
- **Answer generation last so it streams** — everything before it is `invoke`d, then tokens flow.
  Citations are parsed from the *complete* answer, so you'd emit them after the stream ends
  rather than piping them (a post-stream lambda would block streaming).
- **Name every stage** — `rewrite_query`, `retrieve_hybrid`, `rerank`, `generate_answer`. Without
  names the trace is unreadable and you can't tell whether latency is retrieval or generation.

**Where I'd stop using LCEL:** if the design needs *corrective* RAG — grade the retrieved
documents, and if they're irrelevant, rewrite the query and retrieve again — that's a cycle.
Week 2 builds the LCEL version; Week 3 rebuilds it as a graph for exactly this reason.
</details>

---

## 10. Recap

- ✅ LCEL is operator overloading on the `Runnable` interface — not a DSL, not a compiler
- ✅ `RunnableSequence` (pipe) — sequential, output N → input N+1
- ✅ `RunnableParallel` — concurrent, same input to all, **replaces** the input object
- ✅ `RunnableLambda` — any function becomes a step; one argument only
- ✅ `RunnablePassthrough` — identity, carries the input forward
- ✅ `RunnableAssign` — adds keys, **keeps** the rest. The workhorse of multi-step pipelines
- ✅ `RunnableBranch` — declarative if/elif/else routing
- ✅ Streaming propagates automatically — until a non-streaming step buffers it
- ✅ Name your steps; unnamed traces are useless
- ✅ LCEL is acyclic. Loops mean LangGraph.

### 🎉 Week 1 complete

You can now: explain how an LLM generates text, engineer prompts deliberately, call any provider
through one interface, template your prompts, get validated typed objects out of a model, and
compose all of it into streaming pipelines.

**You built StudyBuddy v1** — a real multi-mode study assistant with parallel analysis, routing,
structured output, streaming, history, retries and fallbacks.

### Next week

**Week 2 — Data, Embeddings, RAG & Memory.** StudyBuddy currently knows nothing about *your*
lecture notes. Next week it reads your PDFs and cites the page number.

You'll cover chains, document loading and splitting, embeddings from first principles, vector
databases, naive RAG end-to-end, then advanced RAG (reranking, HyDE, multi-query, corrective and
self-RAG), and how memory really works in modern LangChain.

### Quick self-check

1. `{a: 1}` goes into `RunnableParallel({b: chain})`. What comes out, and what's been lost?
2. Your chain streams beautifully until you add `.pipe(s => s.trim())` at the end. Why does it stop?
3. Your agent needs to call a tool, look at the result, and decide whether to call another. Can LCEL do this?

<details>
<summary>Answers</summary>

1. `{b: ...}` — `a` is lost. `RunnableParallel` **replaces** the input with its result object.
   Use `RunnablePassthrough.assign({b: chain})` to get `{a: 1, b: ...}` instead.
2. `trim()` needs the complete string before it can return anything, so it has no incremental
   `transform`. The chain still streams internally, but nothing exits until the model finishes —
   all the latency moves to the front. Fix: transform before the model, or write it as an async
   generator that yields chunks.
3. No — that's a cycle, and LCEL builds a directed *acyclic* graph. You'd have to write the loop
   outside the chain, losing streaming, coherent tracing and state management across iterations.
   That's what LangGraph is for (Week 3).
</details>
