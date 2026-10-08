# Day 34 — Cost & Latency: Making It Cheap and Fast

> ⏱ **Time:** ~3 hours · 🎯 **Prereqs:** [Day 33](day-33-multimodal.md), [Day 24](../week-04-production-projects-and-interviews/day-24-reliability.md) · 🧩 **Difficulty:** ●●●●○

**Today you learn:** StudyBuddy works, but the bill and the slow-request time both grow with
every new student. Today you find out where the money and the waiting actually come from, then
remove them one by one. You build a cost ledger from `usage_metadata` and measure LangChain's
exact-match cache. You build a semantic cache by hand and lay out prompts for provider prompt
caching. Then you route easy questions to a cheap model, cap concurrency, and stop runaway
spending with a budget guard. Everything runs with scripted models, so no API key is needed. At the end, StudyBuddy
v6.6 is cached, routed and budgeted — and it prints its own dashboard.

> 📖 **Words you'll meet today**
>
> - **Cost ledger** — a record of every model call: which feature made it, its tokens and its
>   price.
> - **Cache hit / cache miss** — a hit means you reuse a saved answer; a miss means you must call
>   the model.
> - **Exact-match cache** — reuses an answer only when the request is identical, character for
>   character.
> - **Semantic cache** — reuses an answer when a new question *means* nearly the same as an old
>   one, judged by embeddings.
> - **Prompt caching** — a provider feature: the provider reuses its work on a long, unchanged
>   start of your prompt.
> - **Model cascade** — try a cheap model first, and call an expensive one only if a check fails.
> - **p95 latency** — the waiting time that 95 % of requests beat. It describes your slow days.
> - **TTFT (time to first token)** — how long the user waits before the first word appears.

---

## 1. The problem

StudyBuddy has been live for a month. Here is the weekly summary from your dashboard. The
numbers are **illustrative** — they show the shape of the problem, not a real bill.

```
   week   students   model calls   bill      p50 wait   p95 wait
   1         200        9,000      $   41      1.2 s      3.1 s
   2         800       41,000      $  198      1.3 s      4.0 s
   3       2,500      140,000      $  690      1.4 s      6.8 s
   4       6,000      390,000      $1,950      1.6 s     11.2 s     ← and exam week is next
```

Three things are wrong at once. The bill grows **faster** than the number of students, because
agent loops make several calls per question. The slow requests (p95) get much slower than the
typical ones (p50), because 429 rate-limit errors trigger retries. And nobody can say *which*
feature costs the most, because nothing records it.

None of this is a bug. Every request is correct. It's just expensive and slow — and the same
student asks "what is a token?" on Monday, Tuesday and Wednesday, and you pay full price each
time.

### The real-life version

Think of a busy café.

```
   the same coffee ordered 50 times a day   → keep a pot ready              EXACT CACHE
   "a latte" vs "one latte, please"         → the barista knows it's the same order
                                                                            SEMANTIC CACHE
   the espresso machine stays warm          → the next cup starts faster    PROMPT CACHING
   tea goes to the junior, wedding cake
     goes to the head baker                 → match the job to the cost     ROUTING / CASCADE
   ten orders arrive at once                → the counter takes four at a time
                                                                            CONCURRENCY LIMIT
   a customer's tab                         → stop serving at the limit     BUDGET GUARD
   hand over the first sip early            → it *feels* faster             STREAMING
```

The café doesn't make each coffee cheaper. It avoids making coffees it doesn't need to, and it
gives the expensive ones to the right person. That's today.

---

## 2. Mental model

### Where the money and the time go

```
   one student question
          │
          ▼
   ┌───────────────┐   hit: $0, ~0 ms
   │ exact cache   │─────────────────────────────────────────────▶ answer
   └──────┬────────┘
          │ miss
   ┌──────▼────────┐   hit (similar enough): $0, ~0 ms
   │ semantic cache│─────────────────────────────────────────────▶ answer
   └──────┬────────┘
          │ miss
   ┌──────▼────────┐   over budget → refuse or downgrade
   │ budget guard  │─────────────────────────────────────────────▶ polite message
   └──────┬────────┘
          │ ok
   ┌──────▼────────┐  check passes   ┌───────────────┐
   │ small model   │────────────────▶│ answer        │   cost = input × price + output × price
   └──────┬────────┘                 └───────────────┘   time = queue + prompt + output tokens
          │ check fails
   ┌──────▼────────┐
   │ large model   │──────────────────▶ answer  (you paid for BOTH calls)
   └───────────────┘
```

Every layer in this picture removes cost or time from the layer below it. The order matters:
the cheapest check goes first.

### The levers

| Lever | Saves money? | Saves time? | The catch |
|---|---|---|---|
| Exact-match cache | ✅ repeats cost $0 | ✅ ~0 ms | only identical requests hit |
| Semantic cache | ✅ near-repeats cost $0 | ✅ | can serve a **wrong** answer |
| Provider prompt caching | ✅ cheaper repeated input | ✅ faster start | needs a stable prefix; provider-specific |
| Routing / cascade | ✅ most traffic on a cheap model | ✅ usually | escalations pay twice and are slower |
| Concurrency cap | — | ✅ fewer 429s and retries | too low wastes capacity |
| Shorter output | ✅ output tokens cost more | ✅ fewer tokens to generate | answers can get too short |
| Streaming | — | ✅ *perceived* wait | total time is the same |
| Budget guard | ✅ caps the worst case | — | some students hit the wall |

Two ideas hold the whole day together. **Measure before you optimise** — the ledger comes first.
And **every saving has a quality risk** — a cache can be stale, a cheap model can be wrong. So
each lever comes with a check.

---

## 3. First principles

### 3.1 Where cost comes from

> 💬 **In plain words:** you pay per token, in and out. Anything that sends the same text again
> — history, retrieved notes, agent steps, retries — makes you pay for it again.

You met the cost formula on [Day 01](../week-01-foundations/day-01-llms-tokens-and-inference.md)
and read the numbers from `usage_metadata` on
[Day 04](../week-01-foundations/day-04-langchain-models.md):

```
   cost of one call = input_tokens × input price  +  output_tokens × output price
```

Output tokens usually cost more than input tokens, because each one needs its own pass through
the model (Day 01 explains why). So the biggest cost drivers are:

| Driver | Why it costs | Measured below (§4.2) |
|---|---|---|
| **Input size** | the system prompt and history are re-sent on every call | chat: 190 input tokens |
| **Retrieved context** | RAG adds notes to the prompt | the same question with notes: 620 |
| **Agent loops** | each step re-sends everything so far | 3 calls: 190 → 336 → 482 input tokens |
| **Model size** | a large model has a higher price per token | illustrative: 10× the small model |
| **Retries** | a retry re-sends the whole input | Day 24 §3.2: retries multiply |

The agent row is the one that surprises people. Three steps did not cost three times one call.
They cost 190 + 336 + 482 = 1,008 input tokens, because the history grows at every step.
[Day 22](../week-04-production-projects-and-interviews/day-22-multi-agent.md) measured the same
effect for multi-agent systems: a single-hop question cost 2 model calls with one agent, and 4
with a supervisor.

### 3.2 Where latency comes from

> 💬 **In plain words:** a model call waits in a queue, reads your prompt, then writes its answer
> one token at a time. Long answers take longer. Streaming shows the first words early.

```
   send ─▶ [ queue ] ─▶ [ read the prompt ] ─▶ [ token ][ token ][ token ] ... ─▶ done
           └──────── time to first token (TTFT) ──┘└──── grows with output length ───┘
```

Our scripted model simulates this: 300 ms before the first token, then 20 ms per token. Here is
what we measured (§4.8):

```
   JS      short invoke: user waits 494 ms  | stream: first token 368 ms, done 638 ms
           long  invoke: user waits 1974 ms | stream: first token 345 ms, done 2994 ms
   Python  short invoke: user waits 516 ms  | stream: first token 321 ms, done 486 ms
           long  invoke: user waits 1963 ms | stream: first token 326 ms, done 2183 ms
```

Two lessons. First, **output length drives total time**: 83 tokens took about four times longer
than 9. Second, **streaming does not make the answer faster** — it makes the *first word*
faster. The user starts reading after ~0.3 s instead of ~2 s. (On Windows, JS timers round small
sleeps up, so the JS stream finished later than the Python one. That is our simulation, not
LangChain.) [Day 23](../week-04-production-projects-and-interviews/day-23-streaming-and-events.md)
showed how to get those tokens to a browser.

Then add the things around the model: several calls per agent run, retries after 429 errors,
and requests queueing behind each other. Those are why p95 grows faster than p50.

### 3.3 Exact-match caching — and what is in the key

> 💬 **In plain words:** LangChain can save each answer under a key built from the prompt and the
> model settings. The same key later returns the saved answer for free.

A cache is a lookup table: **key → saved answer**. LangChain builds the key from two parts:

1. **The prompt** — all the messages, turned into one string.
2. **The "LLM string"** — a description of the model and the call options.

We measured what causes a miss (§4.3):

```
   1st:  1 call       (miss — the model runs)
   2nd:  1 call       (hit — identical text)
   lower-case:     2 calls   ← one letter changed: miss
   trailing space: 3 calls   ← one space added: miss
   temperature 0.7: 1 call on a second model   ← different settings: miss
   with stop:      4 calls   ← a call option: miss
```

The cache is literal. "What is a token?" and "what is a token?" are different keys. That is why
Exercise 1 normalises the question first (trim, collapse spaces, lower-case). It cut 6 model
calls to 2 on the same 8 questions.

**What the model class puts in the key matters, and the languages differ.** We built two real
`ChatGroq` objects with a fake API key and looked at their keys. No network call is needed for
that:

```
   Python ChatGroq (langchain-groq 1.1.3)
     temperature 0 vs 0.7          → different keys
     gpt-oss-120b vs gpt-oss-20b   → different keys
     key includes model_name, temperature, max_retries, n, service_tier ...

   JavaScript ChatGroq (@langchain/groq 1.3.1)
     key for EVERY ChatGroq:  _model:"base_chat_model",_type:"groq"
     → no model name and no temperature in the key
```

Then we proved the JS gap matters. We saved an answer from the 20B model in a shared
`InMemoryCache`, and asked the 120B model the same question:

```
   big model got: SMALL MODEL ANSWER
```

> ⚠️ **In JavaScript, never share one cache between different `ChatGroq` models or settings.** The
> 120B model returned the 20B model's cached answer. Give each model its own `InMemoryCache`
> instance. Check any other provider class before you share a cache: print
> `model._getSerializedCacheKeyParametersForCall({})` (JS) or `model._get_llm_string()`
> (Python). These are internal methods, so they may change — but they show you the truth today.

### 3.4 Cache hits and your ledger — the languages differ again

> 💬 **In plain words:** when a cached answer comes back, JS reports zero tokens and Python
> reports the original tokens. Your cost code must know which.

```
   JS      2nd (hit) usage_metadata: { input_tokens: 0, output_tokens: 0, total_tokens: 0 }
   Python  2nd (hit) usage_metadata: {'input_tokens': 4, 'output_tokens': 6,
                                      'total_tokens': 10, 'total_cost': 0}
```

So a Python ledger that only adds up tokens **charges you for free answers**. Our Python
`cost_of` checks `total_cost == 0` first and returns $0 (measured: `2.8e-05` for the miss,
`0.0` for the hit).

JS has a stranger trap. A cache hit returns **the same message object** as the first call
(`same object: true`), and LangChain sets its usage to zero. So the *first* answer's usage
changes too:

```
   first.usage_metadata now: { input_tokens: 0, output_tokens: 0, total_tokens: 0 }
   costOf(first) before the hit: 0.000028   after the hit: 0
```

> ⚠️ **Record cost the moment a call returns.** If your JS code reads `usage_metadata` later —
> say, at the end of the request — a cache hit in between can wipe it. Python copies the message,
> so the first answer keeps its numbers.

### 3.5 Semantic caching — and the false hit

> 💬 **In plain words:** turn each question into a vector. If a new question's vector is close
> enough to a saved one, reuse that answer. "Close enough" is a number you choose, and choosing
> it badly gives wrong answers.

An exact cache misses "In an LLM, what does temperature do?" when it has saved "What does
temperature do in an LLM?". A semantic cache fixes that. It embeds each question
([Day 10](../week-02-data-embeddings-and-rag/day-10-embeddings.md)) and compares vectors with
cosine similarity. [Day 08](../week-02-data-embeddings-and-rag/day-08-chains.md) mentioned this
idea for support traffic; today you build it.

We use a stand-in for an embedding model that counts words. It is not a real embedding model,
but it makes every number predictable. Against the saved question "What does temperature do in
an LLM?":

```
   1.000  what does temperature do in an llm                  same words
   0.882  What does the temperature setting do in an LLM?     a real paraphrase
   0.857  What does top_p do in an LLM?                       a DIFFERENT question
   0.169  How do I install Python?                            unrelated

   threshold 0.95: HIT   miss  miss  miss
   threshold 0.88: HIT   HIT   miss  miss
   threshold 0.8:  HIT   HIT   HIT   miss      ← top_p gets the temperature answer
```

The right paraphrase scored 0.882. The wrong question scored 0.857. Only 0.025 separates a
useful hit from a wrong answer. A loose threshold (0.8) served the temperature answer to a
student who asked about `top_p`. That is a **false hit**: confident, fast, free and wrong.

And a high threshold does not save you from every false hit. In Exercise 4, "Convert 100 Celsius
to Fahrenheit" and "Convert 100 Fahrenheit to Celsius" score **1.000** with our word counter,
because they use the same words. Real embedding models are not word counters, but don't assume
yours separates such pairs — test it with your own examples.

Defences that work:

- **Tune the threshold on real pairs.** Collect questions that should and shouldn't match, and
  measure where the scores fall (Day 25's datasets).
- **Exclude risky questions.** Questions with numbers, names, dates or user data skip the
  semantic layer.
- **Scope the cache.** Key it by course, language or prompt version, so answers can't leak across
  contexts.
- **Expire entries.** A saved answer goes stale when your notes change.

> 🔒 Never share a semantic cache across users for personal questions. "What's my grade?" from
> two students is the same text and a different answer.

### 3.6 Provider prompt caching

> 💬 **In plain words:** if many requests start with the same long text, some providers keep
> their work on that text and reuse it. Repeated input then costs less and starts faster. It
> only works if the start of the prompt is exactly the same.

On Day 01 you learned that the model builds a **KV cache** — its internal notes about every
input token — before it writes anything. Prompt caching keeps those notes on the provider's
side after the request ends. If your next request starts with the **same tokens**, the provider
skips that work.

Two rules follow, and both are about **prefixes** (the start of the prompt):

1. **Stable content goes first.** System rules, tool definitions, long reference notes.
2. **Changing content goes last.** The time, the student's name, the question.

[Day 05](../week-01-foundations/day-05-prompts-and-templates.md) gave the same advice for
another reason: don't bake the question into the system message. We measured how much of two
requests is identical from the start (§4.5):

```
   JS      bad  request 2276 chars, shared prefix 38 chars (~10 tokens, 2%)
           good request 2277 chars, shared prefix 2217 chars (~555 tokens, 97%)
   Python  bad  request 2291 chars, shared prefix 41 chars (~11 tokens, 2%)
           good request 2292 chars, shared prefix 2224 chars (~556 tokens, 97%)
```

The "bad" layout put the student's name and the time at the top of the system message. One
changed character near the start breaks the whole prefix, so only 2 % is shared. The "good"
layout moved them into the user message: 97 % shared.

> ⏱ **Not executed here — check your provider's docs.** Provider prompt caching needs a real
> API call, and we had no key. What the provider pages said when we read them (October 2026):
> OpenAI caches long prefixes **automatically**; Anthropic needs a `cache_control` marker (on
> the request or on a block). Both need an identical prefix and a minimum length — from a few
> hundred to a few thousand tokens, depending on the model. Cached entries expire on their own,
> after minutes to an hour by default. We don't quote discounts here: they differ by provider and model, and they change.
> When a provider reports cached tokens, LangChain puts them in
> `usage_metadata.input_token_details.cache_read` (a field in both `@langchain/core` and
> `langchain-core`). Whether your provider class fills it in is something to check.

### 3.7 Routing and cascades

> 💬 **In plain words:** most questions are easy. Send them to a cheap model. Use the expensive
> model only when you need it — either decided before the call (routing) or after a check
> (cascade).

A **router** decides *before* calling: a rule or a small classifier looks at the question. A
**cascade** decides *after*: the cheap model answers, a check looks at the answer, and if it
fails, the large model answers instead.

We measured both on the same 10 StudyBuddy questions. Three are hard. The prices are
**illustrative**: the small model is 10× cheaper per token than the large one.

```
   large only:  $0.003714   (10 large calls)
   cascade:     $0.001434   (10 small + 3 large; 3 of 10 escalated)       −61 %
   router:      $0.001371   (7 small + 3 large)                            −63 %
```

The router was a little cheaper, because it never wasted a small call on a hard question. But a
router **never looks at the answer**. If its rule sends a hard question to the small model, a
weak answer goes straight to the student. A cascade checks every answer. Many systems combine
them: route the obvious cases, cascade the rest.

The cascade has two costs you must watch:

- **Escalations pay twice.** An escalated question pays for the small call *and* the large call.
- **Escalations are slower.** The two calls run one after the other. In Exercise 2, the median
  request took ~160 ms, but p95 took ~1,070 ms — the escalated ones.

And the check is everything. In Exercise 4, a check that was too strict escalated **10 of 10**
questions. The cascade then cost **$0.003940**, *more* than large-only ($0.003714). A cascade
with a bad check is worse than no cascade at all.

Good checks are cheap and specific: valid JSON against your schema (Day 06), the answer cites a
retrieved source (Day 12), no "I'm not sure", a minimum length. A judge model (Day 25) also
works, but it adds a call to every request.

### 3.8 Batching and concurrency

> 💬 **In plain words:** many calls at once finish sooner than one after another. But your
> provider allows only so many at a time. Above that, it answers with 429 errors.

`batch` runs many inputs at once; `maxConcurrency` / `max_concurrency` caps how many are in
flight ([Day 04](../week-01-foundations/day-04-langchain-models.md) introduced it). Measured
with a simulated 200 ms model and 12 inputs:

```
                      JS          Python
   concurrency 1     2510 ms     2467 ms      one after another
   concurrency 4      641 ms      645 ms      three waves of four
   concurrency 12     203 ms      231 ms      all at once
```

Now give the "provider" a limit of 4 requests in flight, like a rate limit:

```
   no cap   → 8 of 12 failed with 429      (both languages)
   cap of 4 → 0 of 12 failed
```

> ⚠️ **The default is different in each language.** With no cap, JS started **all 40** of 40
> inputs at once. Python started at most **12** — its thread pool's default size, which depends
> on your CPU count (this machine has 8 cores). Neither default knows your provider's limit. Set
> the cap yourself.

A failed request is not free either. A 429 triggers a retry, which waits and then re-sends the
whole input. That's how p95 grows. Day 24's rate limiter does this job across a whole process;
`maxConcurrency` does it inside one `batch` call.

> ⏱ **Provider batch APIs (not executed here).** Some providers also offer an asynchronous batch
> endpoint: you upload many requests, and the results come back later, often within hours. It
> suits work nobody is waiting for — nightly grading, re-embedding notes. Read your provider's
> docs for the current price and time limits.

### 3.9 Output length and the budget guard

> 💬 **In plain words:** shorter answers are cheaper and faster. A budget guard stops one student
> or one runaway loop from spending without limit.

You control output length two ways (Day 01 §3.4 explains both):

- **Ask for it.** "Answer in at most three sentences." This changes what the model writes.
- **Cap it.** `maxTokens` / `max_tokens` cuts the answer off at a limit. It is a safety net, not
  a style guide — a cut-off answer stops mid-sentence.

We checked how the cap reaches Groq (keyless — we read the request parameters, no call):

```
   JS     new ChatGroq({ maxTokens: 200 })   → sends max_completion_tokens: 200
   Python ChatGroq(max_tokens=200)           → sends max_tokens: 200
   both:  temperature defaults to 0.7 when you don't set it
```

Leave room for thinking. Groq's GPT-OSS models are **reasoning models**: they write hidden
reasoning tokens first, and those count toward the cap. With a cap of 20, the answer came back
**empty** with `finish_reason: "length"` and `output_tokens: 20` (verified with JS `ChatGroq`).
You paid for 20 tokens and got nothing. Keep the cap well above the answer length — 300 worked
(§4.8).

A **budget guard** caps money, not tokens. Day 24 §4.8 built a token budget for one run. Today's
guard tracks **dollars per student per day**, and it degrades gently:

```
   ok        $0.000023 What is a token?
   ok        $0.000046 What is an embedding?
   ok        $0.000069 What does temperature do?
   ok        $0.000504 Compare RAG and fine-tuning for
   ok        $0.000527 What is a vector store?
   ok        $0.000957 Explain why agents loop and how
   downgrade $0.000981 What is a context window?          ← past 80 %: small model only
   downgrade $0.001005 What is a prompt template?
   block     $0.001005 Design a cache for 10,000 studen    ← over the limit: refused
   block     $0.001005 What is streaming?
```

Notice the final spend: **$0.001005** against a limit of **$0.001** (illustrative). The guard
checks *before* each call, so the last call can go over. If you need a hard cap, estimate the
cost before calling (input tokens are known; cap the output with `maxTokens`).

---

## 4. Code — JavaScript

```bash
npm install @langchain/core langchain
# optional, only for the cache-key check in §3.3:
npm install @langchain/groq
```

Every file below runs without an API key. Put them in one folder; later files import earlier
ones.

### 4.1 A model that reports usage and takes time

A real model costs money and takes time. To measure cost and latency without a key, we need a
fake model that does both on purpose. It answers from a function, counts its calls, sleeps like
a real model, and reports `usage_metadata` (1 token per 4 characters — Day 01's rule of thumb).

```js
// d34_model.js — a keyless stand-in for a real chat model.
// It answers from a function, counts its calls, waits like a real model, and reports usage.
import { BaseChatModel } from "@langchain/core/language_models/chat_models";
import { AIMessage, AIMessageChunk } from "@langchain/core/messages";
import { ChatGenerationChunk } from "@langchain/core/outputs";

export const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
export const countTokens = (text) => Math.ceil(text.length / 4);   // Day 01's rough rule

export class ScriptedModel extends BaseChatModel {
  constructor({ model = "small", answer = (q) => `Answer: ${q}`, temperature = 0,
                delayMs = 0, msPerToken = 0, cache } = {}) {
    super({ cache });                       // LangChain's own cache option (§4.3)
    Object.assign(this, { model, answer, temperature, delayMs, msPerToken });
    this.calls = 0;                         // how many times the "provider" really ran
  }
  _llmType() { return "scripted"; }
  // What makes two calls "the same model" for the cache key. Real classes report more.
  _identifyingParams() { return { model: this.model, temperature: this.temperature }; }

  _reply(messages) {
    this.calls++;
    const prompt = messages.map((m) => m.content).join("\n");
    const text = this.answer(messages.at(-1).content);
    const usage = { input_tokens: countTokens(prompt), output_tokens: countTokens(text) };
    usage.total_tokens = usage.input_tokens + usage.output_tokens;
    return { text, usage };
  }

  async _generate(messages) {
    const { text, usage } = this._reply(messages);
    await sleep(this.delayMs + this.msPerToken * usage.output_tokens);  // queue + decoding
    const message = new AIMessage({
      content: text, usage_metadata: usage, response_metadata: { model_name: this.model } });
    return { generations: [{ message, text }] };
  }

  async *_streamResponseChunks(messages) {
    const { text, usage } = this._reply(messages);
    await sleep(this.delayMs);                                   // time to first token
    const pieces = text.match(/.{1,4}/gs) ?? [];                 // one "token" = 4 characters
    for (const [i, piece] of pieces.entries()) {
      await sleep(this.msPerToken);                              // each token takes time
      const last = i === pieces.length - 1;
      yield new ChatGenerationChunk({ text: piece, message: new AIMessageChunk({
        content: piece, ...(last ? { usage_metadata: usage } : {}) }) });
    }
  }
}
```

> 💡 To use a real model later, swap `ScriptedModel` for `ChatGroq` (`openai/gpt-oss-120b`).
> Everything else in this chapter stays the same, because both are LangChain chat models.

### 4.2 A cost ledger

You can't cut what you can't see. The ledger turns each `AIMessage` into a row: feature, tokens,
dollars. The prices are **made up** — replace them with your provider's.

```js
// d34_ledger.js — a per-request cost ledger built from usage_metadata
// ILLUSTRATIVE prices in US dollars per 1 million tokens. Made up for this lesson —
// read your provider's pricing page for real ones.
export const PRICES = {
  small: { input: 0.10, output: 0.40 },
  large: { input: 1.00, output: 4.00 },
};

export function costOf(ai) {
  const u = ai.usage_metadata ?? { input_tokens: 0, output_tokens: 0 };
  const p = PRICES[ai.response_metadata?.model_name] ?? { input: 0, output: 0 };
  return (u.input_tokens * p.input + u.output_tokens * p.output) / 1_000_000;
}

export class CostLedger {
  rows = [];
  record(feature, ai) {
    const u = ai.usage_metadata ?? { input_tokens: 0, output_tokens: 0 };
    const cost = costOf(ai);
    this.rows.push({ feature, input: u.input_tokens, output: u.output_tokens, cost });
    return cost;
  }
  total() { return this.rows.reduce((sum, r) => sum + r.cost, 0); }
  report() {
    const groups = Object.groupBy(this.rows, (r) => r.feature);
    for (const [feature, rows] of Object.entries(groups)) {
      const sum = (k) => rows.reduce((s, r) => s + r[k], 0);
      console.log(`${feature.padEnd(6)} calls ${rows.length}  in ${String(sum("input")).padStart(5)}` +
        `  out ${String(sum("output")).padStart(4)}  $${sum("cost").toFixed(6)}`);
    }
    console.log(`total  $${this.total().toFixed(6)}`);
  }
}
```

Now three kinds of request — plain chat, RAG, and a three-step agent loop:

```js
// d34_where_cost.js — three kinds of request, one ledger
import { SystemMessage, HumanMessage, AIMessage } from "@langchain/core/messages";
import { ScriptedModel } from "./d34_model.js";
import { CostLedger } from "./d34_ledger.js";

const SYSTEM = new SystemMessage("You are StudyBuddy, a patient tutor. ".repeat(20)); // 740 chars
const NOTES = "Retrieved note: tokens are pieces of text. ".repeat(40);              // 1,720 chars
const large = new ScriptedModel({ model: "large", answer: () => "A token is a piece of text. ".repeat(6) });
const ledger = new CostLedger();

// 1. a plain question
ledger.record("chat", await large.invoke([SYSTEM, new HumanMessage("What is a token?")]));

// 2. a RAG question: the same question, plus retrieved notes
ledger.record("rag", await large.invoke([SYSTEM, new HumanMessage(`${NOTES}\nWhat is a token?`)]));

// 3. an agent loop: 3 model calls, and each call re-sends everything so far
let history = [SYSTEM, new HumanMessage("Quiz me on tokens.")];
for (let step = 0; step < 3; step++) {
  const ai = await large.invoke(history);
  ledger.record("agent", ai);
  history = [...history, new AIMessage(ai.content), new HumanMessage("Tool result: " + "x".repeat(400))];
}

ledger.report();
console.log("model calls:", large.calls);
console.log("agent inputs per call:", ledger.rows.filter((r) => r.feature === "agent").map((r) => r.input));
```

```
chat   calls 1  in   190  out   42  $0.000358
rag    calls 1  in   620  out   42  $0.000788
agent  calls 3  in  1008  out  126  $0.001512
total  $0.002658
model calls: 5
agent inputs per call: [ 190, 336, 482 ]
```

The agent feature made 60 % of the calls and 57 % of the cost. That is the line to look at first.
In production, `feature` comes from your route or graph node, and the rows go to your metrics
system (Day 25) instead of the console.

### 4.3 LangChain's exact-match cache

Pass a cache to the model. Every call checks it first.

```js
// d34_exact_cache.js — LangChain's exact-match cache, measured
import { InMemoryCache } from "@langchain/core/caches";
import { ScriptedModel } from "./d34_model.js";

const cache = new InMemoryCache();
const model = new ScriptedModel({ model: "large", cache });

const first = await model.invoke("What is a token?");
console.log("1st:", model.calls, "call(s)", first.usage_metadata);

const second = await model.invoke("What is a token?");          // identical text
console.log("2nd:", model.calls, "call(s)", second.usage_metadata);
console.log("same answer:", first.content === second.content);

await model.invoke("what is a token?");                          // one letter differs
console.log("lower-case:", model.calls, "call(s)");

await model.invoke("What is a token? ");                         // a trailing space
console.log("trailing space:", model.calls, "call(s)");

const warm = new ScriptedModel({ model: "large", temperature: 0.7, cache });  // same cache
await warm.invoke("What is a token?");
console.log("temperature 0.7:", warm.calls, "call(s) on the second model");

await model.invoke("What is a token?", { stop: ["\n"] });       // a call option
console.log("with stop:", model.calls, "call(s)");

console.log("first.usage_metadata now:", first.usage_metadata);
```

```
1st: 1 call(s) { input_tokens: 4, output_tokens: 6, total_tokens: 10 }
2nd: 1 call(s) { input_tokens: 0, output_tokens: 0, total_tokens: 0 }
same answer: true
lower-case: 2 call(s)
trailing space: 3 call(s)
temperature 0.7: 1 call(s) on the second model
with stop: 4 call(s)
first.usage_metadata now: { input_tokens: 0, output_tokens: 0, total_tokens: 0 }
```

Read the last line twice. The hit zeroed the usage of the **first** message too (§3.4). Our
`ScriptedModel` puts temperature in its key on purpose. JS `ChatGroq` doesn't, so give each real
model its own cache:

```js
// one cache per model and settings — never shared (see §3.3)
const fast = new ChatGroq({ model: "openai/gpt-oss-20b", temperature: 0, cache: new InMemoryCache() });
const smart = new ChatGroq({ model: "openai/gpt-oss-120b", temperature: 0, cache: new InMemoryCache() });
```

> 📦 `cache: true` uses one **global** `InMemoryCache` shared by every model that sets it
> (`InMemoryCache.global()` in `@langchain/core`). With JS `ChatGroq`, that is exactly the
> sharing you want to avoid. `InMemoryCache` also lives in one process and never expires; for
> several servers, use a shared store such as Redis (Day 27).

### 4.4 A semantic cache, by hand

```js
// d34_semantic.js — a semantic cache, built by hand
// embed() is a stand-in for a real embedding model (Day 10): it counts words, so every
// number below is predictable. A real model returns a dense vector; the cache logic is the same.
export function embed(text) {
  const vector = new Map();
  for (const word of text.toLowerCase().match(/[a-z0-9_]+/g) ?? []) {
    vector.set(word, (vector.get(word) ?? 0) + 1);
  }
  return vector;
}

export function cosine(a, b) {
  let dot = 0, normA = 0, normB = 0;
  for (const [word, x] of a) { dot += x * (b.get(word) ?? 0); normA += x * x; }
  for (const x of b.values()) normB += x * x;
  return normA && normB ? dot / Math.sqrt(normA * normB) : 0;
}

export class SemanticCache {
  constructor(threshold) { this.threshold = threshold; this.entries = []; }
  lookup(question) {
    const v = embed(question);
    let best = null, score = 0;
    for (const entry of this.entries) {
      const s = cosine(v, entry.vector);
      if (s > score) { best = entry; score = s; }
    }
    return score >= this.threshold ? { answer: best.answer, score, matched: best.question } : null;
  }
  update(question, answer) { this.entries.push({ question, vector: embed(question), answer }); }
}
```

```js
// d34_semantic_demo.js — the same questions against three thresholds
import { SemanticCache, embed, cosine } from "./d34_semantic.js";

const CACHED = "What does temperature do in an LLM?";
const ASKED = [
  "what does temperature do in an llm",               // same words, different case
  "What does the temperature setting do in an LLM?",  // a real paraphrase
  "What does top_p do in an LLM?",                    // a DIFFERENT question
  "How do I install Python?",                         // unrelated
];

for (const q of ASKED) console.log(cosine(embed(CACHED), embed(q)).toFixed(3), q);

for (const threshold of [0.95, 0.88, 0.80]) {
  const cache = new SemanticCache(threshold);
  cache.update(CACHED, "Temperature rescales the probabilities before sampling...");
  const results = ASKED.map((q) => (cache.lookup(q) ? "HIT " : "miss"));
  console.log(`threshold ${threshold}:`, results.join("  "));
}
```

```
1.000 what does temperature do in an llm
0.882 What does the temperature setting do in an LLM?
0.857 What does top_p do in an LLM?
0.169 How do I install Python?
threshold 0.95: HIT   miss  miss  miss
threshold 0.88: HIT   HIT   miss  miss
threshold 0.8: HIT   HIT   HIT   miss
```

To use a real embedding model, replace `embed` with `await embeddings.embedQuery(text)` and
`cosine` with the dense version from Day 10 §4.2. The lookup is a linear scan here; with
thousands of entries, store the vectors in a vector store (Day 11) and search it instead.

### 4.5 Prompts that a provider can cache

```js
// d34_prefix.js — how much of two requests is the same from the start?
// Provider prompt caching can only reuse a shared PREFIX, so measure it.
const RULES = "You are StudyBuddy. Explain step by step, cite the notes, end with one quiz question. ".repeat(25);

const bad = (student, question) => [
  { role: "system", content: `Student: ${student}. Time: ${new Date().toISOString()}. ${RULES}` },
  { role: "user", content: question },
];
const good = (student, question) => [
  { role: "system", content: RULES },                                // stable: identical every time
  { role: "user", content: `Student: ${student}. Time: ${new Date().toISOString()}.\n${question}` },
];

function sharedPrefixChars(a, b) {
  let i = 0;
  while (i < a.length && i < b.length && a[i] === b[i]) i++;
  return i;
}

for (const [name, build] of [["bad", bad], ["good", good]]) {
  const one = JSON.stringify(build("Ayesha", "What is a token?"));
  const two = JSON.stringify(build("Bilal", "What is an embedding?"));
  const shared = sharedPrefixChars(one, two);
  console.log(`${name.padEnd(4)} request ${one.length} chars, shared prefix ${shared} chars ` +
    `(~${Math.ceil(shared / 4)} tokens, ${Math.round((100 * shared) / one.length)}%)`);
}
```

```
bad  request 2276 chars, shared prefix 38 chars (~10 tokens, 2%)
good request 2277 chars, shared prefix 2217 chars (~555 tokens, 97%)
```

This measures **your side** of prompt caching: is the prefix stable? The provider side (does it
actually cache, and what does it charge?) was not executed here — see §3.6. With a real model,
check `usage_metadata.input_token_details?.cache_read` on the second request.

### 4.6 A cascade: cheap first, escalate on a failed check

```js
// d34_cascade.js — cheap model first; escalate only when a check fails
import { SystemMessage } from "@langchain/core/messages";
import { ScriptedModel } from "./d34_model.js";
import { costOf } from "./d34_ledger.js";

export const SYSTEM = new SystemMessage("You are StudyBuddy, a patient tutor. ".repeat(20));
export const QUESTIONS = [
  "What is a token?", "What is an embedding?", "What does temperature do?",
  "Compare RAG and fine-tuning for a support bot.", "What is a vector store?",
  "Explain why agents loop and how to stop them.", "What is a context window?",
  "What is a prompt template?", "Design a cache for 10,000 students.", "What is streaming?",
];
const isHard = (q) => /^(compare|explain why|design)/i.test(q);

export const small = new ScriptedModel({ model: "small",
  answer: (q) => (isHard(q) ? "I'm not sure." : `In short: ${q.replace("?", "")} means...`) });
export const large = new ScriptedModel({ model: "large",
  answer: (q) => `A careful, detailed answer to "${q}" with an example and a quiz. `.repeat(2) });

// the check: cheap to run, and specific about what "good enough" means
export const looksGood = (text) => text.length >= 20 && !/not sure/i.test(text);

export async function cascade(messages, check = looksGood) {
  const first = await small.invoke(messages);
  if (check(first.content)) return { ai: first, cost: costOf(first), escalated: false };
  const second = await large.invoke(messages);          // pay for both calls
  return { ai: second, cost: costOf(first) + costOf(second), escalated: true };
}
```

```js
// d34_cascade_demo.js — everything on the large model vs the cascade
import { HumanMessage } from "@langchain/core/messages";
import { SYSTEM, QUESTIONS, small, large, cascade } from "./d34_cascade.js";
import { costOf } from "./d34_ledger.js";

let largeOnly = 0, cascaded = 0, escalations = 0;
for (const q of QUESTIONS) {
  const messages = [SYSTEM, new HumanMessage(q)];
  largeOnly += costOf(await large.invoke(messages));
  const r = await cascade(messages);
  cascaded += r.cost;
  if (r.escalated) escalations++;
}
console.log(`large only: $${largeOnly.toFixed(6)}`);
console.log(`cascade:    $${cascaded.toFixed(6)}  (${escalations} of ${QUESTIONS.length} escalated)`);
console.log(`calls: small ${small.calls}, large ${large.calls} (10 of them for the large-only run)`);
```

```
large only: $0.003714
cascade:    $0.001434  (3 of 10 escalated)
calls: small 10, large 13 (10 of them for the large-only run)
```

With real models, `small` would be `ChatGroq({ model: "openai/gpt-oss-20b" })` and `large`
would be `ChatGroq({ model: "openai/gpt-oss-120b" })`. Our scripted small model says "I'm
not sure" on hard questions. A real one fails in less polite ways — wrong JSON, no citation, a
vague answer — so your check has to look for those.

### 4.7 Batching with a concurrency cap

```js
// d34_batch.js — batching with a concurrency cap, and what "no cap" does to a rate limit
import { ScriptedModel } from "./d34_model.js";

const questions = Array.from({ length: 12 }, (_, i) => `Question ${i + 1}`);

// 1. wall time: each call takes 200 ms (simulated)
for (const maxConcurrency of [1, 4, 12]) {
  const model = new ScriptedModel({ delayMs: 200 });
  const t0 = performance.now();
  await model.batch(questions, { maxConcurrency });
  console.log(`maxConcurrency ${String(maxConcurrency).padStart(2)}: ` +
    `${Math.round(performance.now() - t0)} ms for ${model.calls} calls`);
}

// 2. a provider that allows at most 4 requests in flight, like a rate limit
class RateLimited extends ScriptedModel {
  inFlight = 0;
  async _generate(messages) {
    if (this.inFlight >= 4) throw new Error("429 Too Many Requests");   // simulated
    this.inFlight++;
    try { return await super._generate(messages); } finally { this.inFlight--; }
  }
}
for (const maxConcurrency of [undefined, 4]) {
  const model = new RateLimited({ delayMs: 200 });
  const results = await model.batch(questions, { maxConcurrency }, { returnExceptions: true });
  const failed = results.filter((r) => r instanceof Error).length;
  console.log(`maxConcurrency ${maxConcurrency ?? "unset"}: ${failed} of ${questions.length} failed with 429`);
}
```

```
maxConcurrency  1: 2510 ms for 12 calls
maxConcurrency  4: 641 ms for 12 calls
maxConcurrency 12: 203 ms for 12 calls
maxConcurrency unset: 8 of 12 failed with 429
maxConcurrency 4: 0 of 12 failed with 429
```

Your times will differ by a few tens of milliseconds; the shape won't. `returnExceptions: true`
(the third argument) returns errors in the results array instead of throwing on the first one.
That lets you count failures — and retry only those.

### 4.8 Output length and time to first token

```js
// d34_ttft.js — output length drives total time; streaming hides most of it
import { ScriptedModel } from "./d34_model.js";

const short = "A token is a small piece of text.";          // 9 "tokens"
const long = short.repeat(10);                              // 83 "tokens"

for (const [name, text] of [["short", short], ["long", long]]) {
  // simulated: 300 ms before the first token, then 20 ms per output token
  const model = new ScriptedModel({ answer: () => text, delayMs: 300, msPerToken: 20 });

  let t0 = performance.now();
  await model.invoke("What is a token?");
  const blocking = performance.now() - t0;

  t0 = performance.now();
  let first = null;
  for await (const chunk of await model.stream("What is a token?")) first ??= performance.now() - t0;
  const streamed = performance.now() - t0;

  console.log(`${name.padEnd(5)} invoke: user waits ${Math.round(blocking)} ms | ` +
    `stream: first token ${Math.round(first)} ms, done ${Math.round(streamed)} ms`);
}
```

```
short invoke: user waits 494 ms | stream: first token 368 ms, done 638 ms
long  invoke: user waits 1974 ms | stream: first token 345 ms, done 2994 ms
```

For a real model, ask for short answers in the prompt *and* set a cap as a safety net:

```js
import { ChatGroq } from "@langchain/groq";
// run once against Groq: a three-sentence answer to "What is a token?" used 100 output tokens
// (reasoning included), finish_reason "stop" — 300 leaves room for the hidden reasoning
const tutor = new ChatGroq({ model: "openai/gpt-oss-120b", temperature: 0, maxTokens: 300 });
```

### 4.9 A budget guard

```js
// d34_budget.js — a money budget per student per day
import { HumanMessage } from "@langchain/core/messages";
import { SYSTEM, QUESTIONS, small, cascade } from "./d34_cascade.js";
import { costOf } from "./d34_ledger.js";

export class BudgetGuard {
  constructor(dailyLimit) { this.dailyLimit = dailyLimit; this.spent = new Map(); }
  status(user) {
    const used = this.spent.get(user) ?? 0;
    if (used >= this.dailyLimit) return "block";
    if (used >= 0.8 * this.dailyLimit) return "downgrade";        // last 20%: cheap model only
    return "ok";
  }
  charge(user, cost) { this.spent.set(user, (this.spent.get(user) ?? 0) + cost); }
}

export async function ask(guard, user, question) {
  const messages = [SYSTEM, new HumanMessage(question)];
  const status = guard.status(user);
  if (status === "block") return { status, text: "Daily limit reached. Try again tomorrow." };
  if (status === "downgrade") {                                    // no escalation allowed
    const ai = await small.invoke(messages);
    guard.charge(user, costOf(ai));
    return { status, text: ai.content };
  }
  const r = await cascade(messages);
  guard.charge(user, r.cost);
  return { status, text: r.ai.content };
}

if (process.argv[1].endsWith("d34_budget.js")) {                  // run the demo directly
  const guard = new BudgetGuard(0.001);               // ILLUSTRATIVE: $0.001 per student per day
  for (const q of QUESTIONS) {
    const r = await ask(guard, "ayesha", q);
    console.log(r.status.padEnd(9), `$${guard.spent.get("ayesha").toFixed(6)}`, q.slice(0, 32));
  }
}
```

The output is in §3.9. The `Map` lives in one process and never resets; in production, keep
the totals in Redis or Postgres with a key per student per day (Day 27).

---

## 5. Code — Python

```bash
pip install langchain-core langchain
# optional, only for the cache-key check in §3.3:
pip install langchain-groq
```

Same files, same results. Run each with `python <file>.py` from one folder.

### 5.1 A model that reports usage and takes time

```python
# d34_model.py — a keyless stand-in for a real chat model.
# It answers from a function, counts its calls, waits like a real model, and reports usage.
import math
import time
from typing import Any, Callable

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult


def count_tokens(text: str) -> int:
    return math.ceil(len(text) / 4)                      # Day 01's rough rule


class ScriptedModel(BaseChatModel):
    model: str = "small"
    answer: Callable[[str], str] = lambda q: f"Answer: {q}"
    temperature: float = 0.0
    delay_s: float = 0.0                                 # queue + prompt processing
    s_per_token: float = 0.0                             # decoding time per output token
    calls: int = 0                                       # how many times the "provider" ran

    @property
    def _llm_type(self) -> str:
        return "scripted"

    @property
    def _identifying_params(self) -> dict[str, Any]:      # part of the cache key
        return {"model": self.model, "temperature": self.temperature}

    def _reply(self, messages):
        self.calls += 1
        prompt = "\n".join(str(m.content) for m in messages)
        text = self.answer(str(messages[-1].content))
        usage = {"input_tokens": count_tokens(prompt), "output_tokens": count_tokens(text)}
        usage["total_tokens"] = usage["input_tokens"] + usage["output_tokens"]
        return text, usage

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        text, usage = self._reply(messages)
        time.sleep(self.delay_s + self.s_per_token * usage["output_tokens"])
        message = AIMessage(content=text, usage_metadata=usage,
                            response_metadata={"model_name": self.model})
        return ChatResult(generations=[ChatGeneration(message=message)])

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        text, usage = self._reply(messages)
        time.sleep(self.delay_s)                         # time to first token
        pieces = [text[i:i + 4] for i in range(0, len(text), 4)]   # one "token" = 4 chars
        for i, piece in enumerate(pieces):
            time.sleep(self.s_per_token)                 # each token takes time
            last = i == len(pieces) - 1
            yield ChatGenerationChunk(message=AIMessageChunk(
                content=piece, usage_metadata=usage if last else None))
```

### 5.2 A cost ledger

```python
# d34_ledger.py — a per-request cost ledger built from usage_metadata
from collections import defaultdict

# ILLUSTRATIVE prices in US dollars per 1 million tokens. Made up for this lesson —
# read your provider's pricing page for real ones.
PRICES = {
    "small": {"input": 0.10, "output": 0.40},
    "large": {"input": 1.00, "output": 4.00},
}


def cost_of(ai) -> float:
    u = ai.usage_metadata or {"input_tokens": 0, "output_tokens": 0}
    if u.get("total_cost") == 0:          # a LangChain cache hit: Python keeps the token counts
        return 0.0
    p = PRICES.get(ai.response_metadata.get("model_name"), {"input": 0, "output": 0})
    return (u["input_tokens"] * p["input"] + u["output_tokens"] * p["output"]) / 1_000_000


class CostLedger:
    def __init__(self):
        self.rows = []

    def record(self, feature: str, ai) -> float:
        u = ai.usage_metadata or {"input_tokens": 0, "output_tokens": 0}
        cost = cost_of(ai)
        self.rows.append({"feature": feature, "input": u["input_tokens"],
                          "output": u["output_tokens"], "cost": cost})
        return cost

    def total(self) -> float:
        return sum(r["cost"] for r in self.rows)

    def report(self):
        groups = defaultdict(list)
        for r in self.rows:
            groups[r["feature"]].append(r)
        for feature, rows in groups.items():
            s = lambda k: sum(r[k] for r in rows)
            print(f"{feature:<6} calls {len(rows)}  in {s('input'):>5}  out {s('output'):>4}"
                  f"  ${s('cost'):.6f}")
        print(f"total  ${self.total():.6f}")
```

```python
# d34_where_cost.py — three kinds of request, one ledger
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from d34_model import ScriptedModel
from d34_ledger import CostLedger

SYSTEM = SystemMessage("You are StudyBuddy, a patient tutor. " * 20)   # 740 chars
NOTES = "Retrieved note: tokens are pieces of text. " * 40               # 1,720 chars
large = ScriptedModel(model="large", answer=lambda q: "A token is a piece of text. " * 6)
ledger = CostLedger()

# 1. a plain question
ledger.record("chat", large.invoke([SYSTEM, HumanMessage("What is a token?")]))

# 2. a RAG question: the same question, plus retrieved notes
ledger.record("rag", large.invoke([SYSTEM, HumanMessage(f"{NOTES}\nWhat is a token?")]))

# 3. an agent loop: 3 model calls, and each call re-sends everything so far
history = [SYSTEM, HumanMessage("Quiz me on tokens.")]
for step in range(3):
    ai = large.invoke(history)
    ledger.record("agent", ai)
    history += [AIMessage(ai.content), HumanMessage("Tool result: " + "x" * 400)]

ledger.report()
print("model calls:", large.calls)
print("agent inputs per call:", [r["input"] for r in ledger.rows if r["feature"] == "agent"])
```

```
chat   calls 1  in   190  out   42  $0.000358
rag    calls 1  in   620  out   42  $0.000788
agent  calls 3  in  1008  out  126  $0.001512
total  $0.002658
model calls: 5
agent inputs per call: [190, 336, 482]
```

### 5.3 LangChain's exact-match cache

Python has two ways to switch the cache on: one global cache for every model
(`set_llm_cache`), or a cache per model (`cache=InMemoryCache()`, used in Exercise 1).

```python
# d34_exact_cache.py — LangChain's exact-match cache, measured
from langchain_core.caches import InMemoryCache
from langchain_core.globals import set_llm_cache
from d34_model import ScriptedModel

set_llm_cache(InMemoryCache())                  # every chat model now checks this cache
model = ScriptedModel(model="large")

first = model.invoke("What is a token?")
print("1st:", model.calls, "call(s)", first.usage_metadata)

second = model.invoke("What is a token?")      # identical text
print("2nd:", model.calls, "call(s)", second.usage_metadata)
print("same answer:", first.content == second.content)

model.invoke("what is a token?")               # one letter differs
print("lower-case:", model.calls, "call(s)")

model.invoke("What is a token? ")              # a trailing space
print("trailing space:", model.calls, "call(s)")

warm = ScriptedModel(model="large", temperature=0.7)   # same global cache
warm.invoke("What is a token?")
print("temperature 0.7:", warm.calls, "call(s) on the second model")

model.invoke("What is a token?", stop=["\n"])  # a call option
print("with stop:", model.calls, "call(s)")

print("first.usage_metadata now:", first.usage_metadata)
```

```
1st: 1 call(s) {'input_tokens': 4, 'output_tokens': 6, 'total_tokens': 10}
2nd: 1 call(s) {'input_tokens': 4, 'output_tokens': 6, 'total_tokens': 10, 'total_cost': 0}
same answer: True
lower-case: 2 call(s)
trailing space: 3 call(s)
temperature 0.7: 1 call(s) on the second model
with stop: 4 call(s)
first.usage_metadata now: {'input_tokens': 4, 'output_tokens': 6, 'total_tokens': 10}
```

The hit kept its token counts and added `'total_cost': 0`. That is why `cost_of` checks for it.
The first message was not changed. Python `ChatGroq` includes the model name and temperature in
its key (§3.3), so a global cache is safe across Groq models — but every constructor setting
counts, even `max_retries`. Change one and the old entries stop matching.

Python's `InMemoryCache` also takes `maxsize`. When it is full, it drops the oldest entry. We
measured `InMemoryCache(maxsize=2)` with the questions a, b, c, a: **4** model calls, because
"a" had been pushed out. JS `InMemoryCache` has no size limit.

### 5.4 A semantic cache, by hand

```python
# d34_semantic.py — a semantic cache, built by hand
# embed() is a stand-in for a real embedding model (Day 10): it counts words, so every
# number below is predictable. A real model returns a dense vector; the cache logic is the same.
import math
import re
from collections import Counter


def embed(text: str) -> Counter:
    return Counter(re.findall(r"[a-z0-9_]+", text.lower()))


def cosine(a: Counter, b: Counter) -> float:
    dot = sum(x * b[word] for word, x in a.items())
    norm_a = math.sqrt(sum(x * x for x in a.values()))
    norm_b = math.sqrt(sum(x * x for x in b.values()))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


class SemanticCache:
    def __init__(self, threshold: float):
        self.threshold = threshold
        self.entries = []

    def lookup(self, question: str):
        v = embed(question)
        best, score = None, 0.0
        for entry in self.entries:
            s = cosine(v, entry["vector"])
            if s > score:
                best, score = entry, s
        if score >= self.threshold:
            return {"answer": best["answer"], "score": score, "matched": best["question"]}
        return None

    def update(self, question: str, answer: str):
        self.entries.append({"question": question, "vector": embed(question), "answer": answer})
```

```python
# d34_semantic_demo.py — the same questions against three thresholds
from d34_semantic import SemanticCache, embed, cosine

CACHED = "What does temperature do in an LLM?"
ASKED = [
    "what does temperature do in an llm",               # same words, different case
    "What does the temperature setting do in an LLM?",  # a real paraphrase
    "What does top_p do in an LLM?",                    # a DIFFERENT question
    "How do I install Python?",                         # unrelated
]

for q in ASKED:
    print(f"{cosine(embed(CACHED), embed(q)):.3f}", q)

for threshold in [0.95, 0.88, 0.80]:
    cache = SemanticCache(threshold)
    cache.update(CACHED, "Temperature rescales the probabilities before sampling...")
    results = ["HIT " if cache.lookup(q) else "miss" for q in ASKED]
    print(f"threshold {threshold}:", "  ".join(results))
```

```
1.000 what does temperature do in an llm
0.882 What does the temperature setting do in an LLM?
0.857 What does top_p do in an LLM?
0.169 How do I install Python?
threshold 0.95: HIT   miss  miss  miss
threshold 0.88: HIT   HIT   miss  miss
threshold 0.8: HIT   HIT   HIT   miss
```

### 5.5 Prompts that a provider can cache

```python
# d34_prefix.py — how much of two requests is the same from the start?
# Provider prompt caching can only reuse a shared PREFIX, so measure it.
import json
from datetime import datetime, timezone

RULES = "You are StudyBuddy. Explain step by step, cite the notes, end with one quiz question. " * 25


def now():
    return datetime.now(timezone.utc).isoformat()


def bad(student, question):
    return [
        {"role": "system", "content": f"Student: {student}. Time: {now()}. {RULES}"},
        {"role": "user", "content": question},
    ]


def good(student, question):
    return [
        {"role": "system", "content": RULES},                    # stable: identical every time
        {"role": "user", "content": f"Student: {student}. Time: {now()}.\n{question}"},
    ]


def shared_prefix_chars(a: str, b: str) -> int:
    i = 0
    while i < len(a) and i < len(b) and a[i] == b[i]:
        i += 1
    return i


for name, build in [("bad", bad), ("good", good)]:
    one = json.dumps(build("Ayesha", "What is a token?"))
    two = json.dumps(build("Bilal", "What is an embedding?"))
    shared = shared_prefix_chars(one, two)
    print(f"{name:<4} request {len(one)} chars, shared prefix {shared} chars "
          f"(~{-(-shared // 4)} tokens, {round(100 * shared / len(one))}%)")
```

```
bad  request 2291 chars, shared prefix 41 chars (~11 tokens, 2%)
good request 2292 chars, shared prefix 2224 chars (~556 tokens, 97%)
```

The character counts differ a little from JS because `json.dumps` adds spaces after `:` and `,`,
and the two languages print the time differently. The percentages match.

### 5.6 A cascade: cheap first, escalate on a failed check

```python
# d34_cascade.py — cheap model first; escalate only when a check fails
import re
from langchain_core.messages import SystemMessage
from d34_model import ScriptedModel
from d34_ledger import cost_of

SYSTEM = SystemMessage("You are StudyBuddy, a patient tutor. " * 20)
QUESTIONS = [
    "What is a token?", "What is an embedding?", "What does temperature do?",
    "Compare RAG and fine-tuning for a support bot.", "What is a vector store?",
    "Explain why agents loop and how to stop them.", "What is a context window?",
    "What is a prompt template?", "Design a cache for 10,000 students.", "What is streaming?",
]


def is_hard(q: str) -> bool:
    return re.match(r"(compare|explain why|design)", q, re.I) is not None


small = ScriptedModel(model="small", answer=lambda q: "I'm not sure." if is_hard(q)
                      else f"In short: {q.replace('?', '')} means...")
large = ScriptedModel(model="large", answer=lambda q:
                      f'A careful, detailed answer to "{q}" with an example and a quiz. ' * 2)


def looks_good(text: str) -> bool:                # cheap to run, specific about "good enough"
    return len(text) >= 20 and "not sure" not in text.lower()


def cascade(messages, check=looks_good):
    first = small.invoke(messages)
    if check(first.content):
        return {"ai": first, "cost": cost_of(first), "escalated": False}
    second = large.invoke(messages)               # pay for both calls
    return {"ai": second, "cost": cost_of(first) + cost_of(second), "escalated": True}
```

```python
# d34_cascade_demo.py — everything on the large model vs the cascade
from langchain_core.messages import HumanMessage
from d34_cascade import SYSTEM, QUESTIONS, small, large, cascade
from d34_ledger import cost_of

large_only = cascaded = 0.0
escalations = 0
for q in QUESTIONS:
    messages = [SYSTEM, HumanMessage(q)]
    large_only += cost_of(large.invoke(messages))
    r = cascade(messages)
    cascaded += r["cost"]
    escalations += r["escalated"]

print(f"large only: ${large_only:.6f}")
print(f"cascade:    ${cascaded:.6f}  ({escalations} of {len(QUESTIONS)} escalated)")
print(f"calls: small {small.calls}, large {large.calls} (10 of them for the large-only run)")
```

```
large only: $0.003714
cascade:    $0.001434  (3 of 10 escalated)
calls: small 10, large 13 (10 of them for the large-only run)
```

### 5.7 Batching with a concurrency cap

```python
# d34_batch.py — batching with a concurrency cap, and what "no cap" does to a rate limit
import threading
import time
from d34_model import ScriptedModel

questions = [f"Question {i + 1}" for i in range(12)]

# 1. wall time: each call takes 200 ms (simulated)
for max_concurrency in [1, 4, 12]:
    model = ScriptedModel(delay_s=0.2)
    t0 = time.perf_counter()
    model.batch(questions, config={"max_concurrency": max_concurrency})
    print(f"max_concurrency {max_concurrency:>2}: "
          f"{(time.perf_counter() - t0) * 1000:.0f} ms for {model.calls} calls")


# 2. a provider that allows at most 4 requests in flight, like a rate limit
LOCK = threading.Lock()


class RateLimited(ScriptedModel):
    in_flight: int = 0

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        with LOCK:
            if self.in_flight >= 4:
                raise RuntimeError("429 Too Many Requests")      # simulated
            self.in_flight += 1
        try:
            return super()._generate(messages, stop, run_manager, **kwargs)
        finally:
            with LOCK:
                self.in_flight -= 1


for max_concurrency in [None, 4]:
    model = RateLimited(delay_s=0.2)
    config = {"max_concurrency": max_concurrency} if max_concurrency else {}
    results = model.batch(questions, config=config, return_exceptions=True)
    failed = sum(isinstance(r, Exception) for r in results)
    print(f"max_concurrency {max_concurrency or 'unset'}: {failed} of {len(questions)} failed with 429")
```

```
max_concurrency  1: 2467 ms for 12 calls
max_concurrency  4: 645 ms for 12 calls
max_concurrency 12: 231 ms for 12 calls
max_concurrency unset: 8 of 12 failed with 429
max_concurrency 4: 0 of 12 failed with 429
```

Sync `batch` runs the calls on a thread pool, so `time.sleep` in one call doesn't block the
others. The lock matters: several threads change `in_flight` at once. (Once, on a busy machine,
we saw 7 failures instead of 8 — threads started a little later. The lesson is the same.)

### 5.8 Output length and time to first token

```python
# d34_ttft.py — output length drives total time; streaming hides most of it
import time
from d34_model import ScriptedModel

short = "A token is a small piece of text."              # 9 "tokens"
long = short * 10                                        # 83 "tokens"

for name, text in [("short", short), ("long", long)]:
    # simulated: 300 ms before the first token, then 20 ms per output token
    model = ScriptedModel(answer=lambda q, t=text: t, delay_s=0.3, s_per_token=0.02)

    t0 = time.perf_counter()
    model.invoke("What is a token?")
    blocking = time.perf_counter() - t0

    t0 = time.perf_counter()
    first = None
    for chunk in model.stream("What is a token?"):
        if first is None:
            first = time.perf_counter() - t0
    streamed = time.perf_counter() - t0

    print(f"{name:<5} invoke: user waits {blocking * 1000:.0f} ms | "
          f"stream: first token {first * 1000:.0f} ms, done {streamed * 1000:.0f} ms")
```

```
short invoke: user waits 516 ms | stream: first token 321 ms, done 486 ms
long  invoke: user waits 1963 ms | stream: first token 326 ms, done 2183 ms
```

```python
from langchain_groq import ChatGroq
# Python not executed against Groq; the JS twin ran once (100 output tokens, "stop") — see §4.8
tutor = ChatGroq(model="openai/gpt-oss-120b", temperature=0, max_tokens=300)
```

### 5.9 A budget guard

```python
# d34_budget.py — a money budget per student per day
from collections import defaultdict
from langchain_core.messages import HumanMessage
from d34_cascade import SYSTEM, QUESTIONS, small, cascade
from d34_ledger import cost_of


class BudgetGuard:
    def __init__(self, daily_limit: float):
        self.daily_limit = daily_limit
        self.spent = defaultdict(float)

    def status(self, user: str) -> str:
        used = self.spent[user]
        if used >= self.daily_limit:
            return "block"
        if used >= 0.8 * self.daily_limit:                 # last 20%: cheap model only
            return "downgrade"
        return "ok"

    def charge(self, user: str, cost: float):
        self.spent[user] += cost


def ask(guard, user, question):
    messages = [SYSTEM, HumanMessage(question)]
    status = guard.status(user)
    if status == "block":
        return {"status": status, "text": "Daily limit reached. Try again tomorrow."}
    if status == "downgrade":                              # no escalation allowed
        ai = small.invoke(messages)
        guard.charge(user, cost_of(ai))
        return {"status": status, "text": ai.content}
    r = cascade(messages)
    guard.charge(user, r["cost"])
    return {"status": status, "text": r["ai"].content}


if __name__ == "__main__":
    guard = BudgetGuard(0.001)                  # ILLUSTRATIVE: $0.001 per student per day
    for q in QUESTIONS:
        r = ask(guard, "ayesha", q)
        print(f"{r['status']:<9} ${guard.spent['ayesha']:.6f}", q[:32])
```

The output matches JS exactly (§3.9).

### 5.10 The JS ↔ Python translation for today

| Concept | JavaScript | Python |
|---|---|---|
| Custom chat model | `class X extends BaseChatModel` + `_generate`, `_llmType()` | `class X(BaseChatModel)` + `_generate`, `_llm_type` property |
| Custom streaming | `async *_streamResponseChunks(messages)` | `def _stream(self, messages, ...)` |
| Model params in the cache key | `_identifyingParams()` | `_identifying_params` property |
| Global cache | `cache: true` on each model (`InMemoryCache.global()`) | `set_llm_cache(InMemoryCache())` — every model |
| Per-model cache | `new ChatX({ cache: new InMemoryCache() })` | `ChatX(cache=InMemoryCache())` |
| Cache-hit `usage_metadata` | **all zeros** — and the first message is zeroed too | original counts **plus** `total_cost: 0` |
| `ChatGroq` cache key | **no** model name, **no** temperature (1.3.1) | model name, temperature, every constructor setting |
| Inspect the key (internal) | `m._getSerializedCacheKeyParametersForCall({})` | `m._get_llm_string()` |
| Batch with a cap | `batch(xs, { maxConcurrency: 4 })` | `batch(xs, config={"max_concurrency": 4})` |
| Batch default with no cap | all inputs at once (40 of 40 measured) | thread pool default (12 on 8 cores) |
| Errors in a batch | `batch(xs, opts, { returnExceptions: true })` | `batch(xs, return_exceptions=True)` |
| Output cap on `ChatGroq` | `maxTokens` → sent as `max_completion_tokens` | `max_tokens` → sent as `max_tokens` |
| Cached-input tokens (if reported) | `usage_metadata.input_token_details?.cache_read` | `usage_metadata["input_token_details"]["cache_read"]` |
| Timing | `performance.now()` (ms) | `time.perf_counter()` (s) |

---

## 6. Under the hood

### 6.1 How LangChain's cache sits in the call path

```
   model.invoke(input)
      │
      ├─ build the prompt string from the messages
      ├─ build the "LLM string" from the model's params + call options
      ├─ cache.lookup(prompt, llmString)
      │     hit  → mark usage (JS: zeros · Python: total_cost 0) → return, no provider call
      │     miss → _generate() → provider → cache.update(prompt, llmString, result) → return
```

In JS, the two strings are joined and hashed with SHA-256 to make the map key. Python's
`InMemoryCache` keys a dict by the `(prompt, llm_string)` pair. Message ids are not part of the
key in either language: two `HumanMessage("hi")` objects with different ids made **1** model
call. (Python removes the ids before building the key; JS turns the messages into plain text
like `Human: hi`.)

Because the cache sits **inside** the model call, it sees only one call at a time. It can't
know that an agent run is "the same question as yesterday". For that, cache at the level of the
whole request — your own exact and semantic layers, as StudyBuddy v6.6 does in Exercise 5.

### 6.2 Why provider prompt caching is a prefix

A model reads its input left to right. The internal notes it builds for token 500 depend on
tokens 1 to 499. So the notes for a prefix can be reused **only if every token before it is
the same**. Change token 3 and the notes for tokens 4 to 2,000 are all different. This is why
§4.5 found one timestamp near the top destroyed 98 % of the shared prefix.

It also explains the other rules on the provider pages: tool definitions and images count as
part of the prefix, and changing them invalidates it. Order your prompt from "never changes" to
"changes every time".

### 6.3 Cost per request vs cost per user

A ledger row is one model call. A product decision needs bigger units:

```
   cost per request   = sum of its rows (an agent run has several)
   cost per user/day  = what the budget guard tracks
   cost per 1,000 requests = what you compare across designs (Exercise 2)
```

Use [Day 27](../week-04-production-projects-and-interviews/day-27-deployment-and-architecture.md)'s
capacity arithmetic with your *measured* cost per request. "400,000 runs a day × $X" is a far
better forecast than a guess about tokens.

### 6.4 Latency: mean, p50, p95

The mean hides the slow tail. In Exercise 2, the cascade's mean was ~435 ms, p50 ~160 ms, and
p95 ~1,070 ms. No single request took 435 ms. Students either got a fast answer or a slow one.
Day 0C explains percentiles; Day 25 shows where to record them. Always report p50 **and** p95.

Tail latency has its own levers: cap concurrency (fewer 429 retries), stream (the wait feels
shorter), shorten outputs, and avoid serial escalations for time-critical paths. A router adds
no extra call on the slow path; a cascade does.

### 6.5 What each lever costs in quality

| Lever | Quality risk | How you notice |
|---|---|---|
| Exact cache | stale answers after your notes change | version the cache key with your prompt/notes version |
| Semantic cache | false hits | log the matched question and score; sample and review |
| Cascade / router | the cheap model's weaker answers | Day 25 evals per model; track the escalation rate |
| Output caps | cut-off answers | count `finish_reason: "length"` |
| Budget guard | blocked students | count blocks per day; alert on spikes |

Every saving should come with a number on a dashboard. A cache hit rate that jumps from 20 % to
60 % overnight is not good news until you know why.

> 📚 **Sources** (read October 2026; provider features change — check the current pages)
>
> - OpenAI, *Prompt caching*: <https://developers.openai.com/api/docs/guides/prompt-caching>
> - Anthropic, *Prompt caching*: <https://platform.claude.com/docs/en/docs/build-with-claude/prompt-caching>

---

## 7. Common mistakes

### ❌ 1. One cache shared by different JS models

```js
// ❌ both models use the same global cache, and JS ChatGroq's key has no model name
const fast = new ChatGroq({ model: "openai/gpt-oss-20b", cache: true });
const smart = new ChatGroq({ model: "openai/gpt-oss-120b", cache: true });
```

**Symptom (measured, §3.3):** the 120B model returned `SMALL MODEL ANSWER` — the 20B model's
cached reply. Your escalation path silently serves the cheap model's answer.

```js
// ✅ one cache per model and settings
const fast = new ChatGroq({ model: "openai/gpt-oss-20b", cache: new InMemoryCache() });
const smart = new ChatGroq({ model: "openai/gpt-oss-120b", cache: new InMemoryCache() });
```

### ❌ 2. A Python ledger that charges for cache hits

```python
# ❌ counts tokens only
cost = (u["input_tokens"] * p["input"] + u["output_tokens"] * p["output"]) / 1_000_000
```

**Symptom:** Python cache hits keep their token counts (`{'input_tokens': 4, ...,
'total_cost': 0}`), so free answers appear on your bill. Your measured savings look like zero.

```python
# ✅ check for the cache marker first
if u.get("total_cost") == 0:
    return 0.0
```

### ❌ 3. Reading `usage_metadata` late in JavaScript

```js
// ❌ collect messages, add up the cost at the end of the request
const answers = [await model.invoke(q1), await model.invoke(q1)];
const total = answers.reduce((s, a) => s + costOf(a), 0);
```

**Symptom (measured, §3.4):** the cache hit returned the same message object and zeroed its
usage. `costOf(first)` went from `0.000028` to `0`. Your real first call disappears from the
ledger.

```js
// ✅ record the moment each call returns
const a = await model.invoke(q1); ledger.record("chat", a);
```

### ❌ 4. Something that changes at the top of the prompt

```js
// ❌
["system", `Time: ${new Date().toISOString()}. You are StudyBuddy...`]
```

**Symptom (measured):** the same question asked 5 times made **5** model calls with a
LangChain cache switched on (Exercise 4). The provider's prefix cache also breaks: only 2 % of
the prompt was shared (§4.5).

✅ Stable text first, changing text last. Put the time, name and question in the user message.

### ❌ 5. A loose semantic threshold

```js
const cache = new SemanticCache(0.8);    // ❌ chosen because it "gets more hits"
```

**Symptom (measured):** "What does top_p do in an LLM?" received the cached *temperature*
answer (score 0.857). Nothing errors; the student just learns the wrong thing.

✅ Choose the threshold from real pairs that should and shouldn't match. Log every semantic hit
with its score and the matched question, and review a sample.

### ❌ 6. Semantic caching for questions with numbers or personal data

**Symptom (measured, Exercise 4):** "Convert 100 Fahrenheit to Celsius" got the answer `212 °F`
with a score of **1.000**, at a strict 0.95 threshold. Personal questions ("What's my grade?")
are worse: the same text, a different correct answer for each student.

✅ Skip the semantic layer for questions with digits, names or user-specific data. Scope the
cache per user where answers are personal.

### ❌ 7. A cascade check that nothing passes

```js
await cascade(messages, (text) => text.length >= 200);   // ❌ the small model never writes that much
```

**Symptom (measured):** 10 of 10 escalated. The cascade cost **$0.003940**, more than sending
everything to the large model (**$0.003714**), and every request was slower.

✅ Track the escalation rate. If it is high, fix the check — or route those questions straight
to the large model.

### ❌ 8. No concurrency cap

```js
await model.batch(allQuestions);         // ❌ JS starts every input at once
```

**Symptom (measured):** against a limit of 4 in flight, **8 of 12** failed with a simulated 429,
and 16 of 20 in Exercise 4. Each failure becomes a retry, which re-sends the input and adds
waiting time.

✅ `batch(xs, { maxConcurrency: 4 })` / `batch(xs, config={"max_concurrency": 4})`, set below
your provider's limit. Add Day 24's rate limiter for traffic that doesn't go through `batch`.

### ❌ 9. Using `maxTokens` to make answers short

**Symptom:** answers stop mid-sentence, with `finish_reason: "length"`. Day 01 §3.4 shows an
example.

✅ Ask for the length you want in the prompt ("three sentences at most"). Keep `maxTokens` as a
safety net above that length.

### ❌ 10. Optimising without a ledger — or with the mean only

**Symptom:** you add a cache and can't tell whether it helped. Or the mean latency looks fine
(~435 ms) while one in ten students waits over a second (Exercise 2).

✅ Ledger first, by feature. Report cost per 1,000 requests and p50 **and** p95, before and
after each change.

---

## 8. Exercises

### Exercise 1 — Normalise, then cache ●○○○○

Eight questions arrive. Some differ only in case or spacing. Run them through LangChain's cache
twice: once as typed, and once after normalising each question (trim, collapse spaces,
lower-case). **Predict** the number of model calls each way before you run it.

<details>
<summary>✅ Solution</summary>

```js
// ex1.js — normalise, then cache
import { InMemoryCache } from "@langchain/core/caches";
import { ScriptedModel } from "./d34_model.js";

const STREAM = [
  "What is a token?", "what is a token?", "What is a token? ", "  What is a  token?",
  "What is an embedding?", "WHAT IS AN EMBEDDING?", "What is a token?", "What is an embedding?",
];
const normalise = (q) => q.trim().replace(/\s+/g, " ").toLowerCase();

const raw = new ScriptedModel({ cache: new InMemoryCache() });
for (const q of STREAM) await raw.invoke(q);

const clean = new ScriptedModel({ cache: new InMemoryCache() });
for (const q of STREAM) await clean.invoke(normalise(q));

console.log(`raw:        ${raw.calls} model calls for ${STREAM.length} questions`);
console.log(`normalised: ${clean.calls} model calls for ${STREAM.length} questions`);
```

```python
# ex1.py — normalise, then cache
import re
from langchain_core.caches import InMemoryCache
from d34_model import ScriptedModel

STREAM = [
    "What is a token?", "what is a token?", "What is a token? ", "  What is a  token?",
    "What is an embedding?", "WHAT IS AN EMBEDDING?", "What is a token?", "What is an embedding?",
]


def normalise(q: str) -> str:
    return re.sub(r"\s+", " ", q.strip()).lower()


raw = ScriptedModel(cache=InMemoryCache())       # a per-model cache, not the global one
for q in STREAM:
    raw.invoke(q)

clean = ScriptedModel(cache=InMemoryCache())
for q in STREAM:
    clean.invoke(normalise(q))

print(f"raw:        {raw.calls} model calls for {len(STREAM)} questions")
print(f"normalised: {clean.calls} model calls for {len(STREAM)} questions")
```

**Expected output (both languages):**

```
raw:        6 model calls for 8 questions
normalised: 2 model calls for 8 questions
```

**Why this design:** normalising is free and safe — it can't produce a wrong hit, because
"What is a token?" and "what is a token?" really are the same question. It belongs **before**
the semantic layer, so the risky layer only sees what the safe one couldn't handle. Don't
normalise text where case matters (code, names in a lookup).
</details>

### Exercise 2 — p50, p95 and cost per 1,000 requests ●●○○○

Give the cascade's models simulated latencies: 150 ms for the small model, 900 ms for the
large one. Run the 10 questions. Report p50, p95, the mean, and the cost per 1,000 requests.
Which number would you put on the team dashboard, and why not the mean?

<details>
<summary>✅ Solution</summary>

```js
// ex2.js — p50, p95 and cost per 1,000 requests for the cascade
import { HumanMessage } from "@langchain/core/messages";
import { SYSTEM, QUESTIONS, small, large, cascade } from "./d34_cascade.js";

small.delayMs = 150;                       // simulated: the small model answers in ~150 ms
large.delayMs = 900;                       // simulated: the large model takes ~900 ms

// nearest-rank percentile: sort, then take the value p% of the way up
const percentile = (xs, p) => [...xs].sort((a, b) => a - b)[Math.ceil((p / 100) * xs.length) - 1];

const latencies = [];
let cost = 0;
for (const q of QUESTIONS) {
  const t0 = performance.now();
  const r = await cascade([SYSTEM, new HumanMessage(q)]);
  latencies.push(performance.now() - t0);
  cost += r.cost;
}
const mean = latencies.reduce((a, b) => a + b, 0) / latencies.length;
console.log(`p50 ${Math.round(percentile(latencies, 50))} ms | p95 ${Math.round(percentile(latencies, 95))} ms` +
  ` | mean ${Math.round(mean)} ms`);
console.log(`cost per 1,000 requests: $${((cost / QUESTIONS.length) * 1000).toFixed(4)} (illustrative prices)`);
```

```python
# ex2.py — p50, p95 and cost per 1,000 requests for the cascade
import math
import time
from langchain_core.messages import HumanMessage
from d34_cascade import SYSTEM, QUESTIONS, small, large, cascade

small.delay_s = 0.15                     # simulated: the small model answers in ~150 ms
large.delay_s = 0.9                      # simulated: the large model takes ~900 ms


def percentile(xs, p):                   # nearest-rank: sort, take the value p% of the way up
    return sorted(xs)[math.ceil(p / 100 * len(xs)) - 1]


latencies, cost = [], 0.0
for q in QUESTIONS:
    t0 = time.perf_counter()
    r = cascade([SYSTEM, HumanMessage(q)])
    latencies.append((time.perf_counter() - t0) * 1000)
    cost += r["cost"]

mean = sum(latencies) / len(latencies)
print(f"p50 {percentile(latencies, 50):.0f} ms | p95 {percentile(latencies, 95):.0f} ms"
      f" | mean {mean:.0f} ms")
print(f"cost per 1,000 requests: ${cost / len(QUESTIONS) * 1000:.4f} (illustrative prices)")
```

**Measured:**

```
JS      p50 167 ms | p95 1073 ms | mean 435 ms
        cost per 1,000 requests: $0.1434 (illustrative prices)
Python  p50 158 ms | p95 1077 ms | mean 436 ms
        cost per 1,000 requests: $0.1434 (illustrative prices)
```

**Why this design:** the latencies fall into two groups. Seven requests took ~150 ms (the small
model was enough). Three took ~1,050 ms (small, then large, one after the other). The mean,
~435 ms, describes no real request. Put p50 and p95 on the dashboard: p50 tells you the normal
experience, p95 tells you what the cascade costs your slowest students. With only 10 requests,
p95 is simply the slowest one; use hundreds before you trust it.
</details>

### Exercise 3 — Router vs cascade ●●●○○

Build a **router**: a cheap rule that sends questions containing "compare", "why", "design" or
"trade-off" straight to the large model, and everything else to the small one. Compare its calls
and cost with the cascade on the same 10 questions. Then answer: when would you still choose the
cascade?

<details>
<summary>✅ Solution</summary>

```js
// ex3.js — a router decides BEFORE the call; a cascade decides AFTER
import { HumanMessage } from "@langchain/core/messages";
import { SYSTEM, QUESTIONS, small, large, cascade } from "./d34_cascade.js";
import { costOf } from "./d34_ledger.js";

// the router: a cheap rule on the question. (A real one might be a small classifier model.)
const routeTo = (q) => (/compare|why|design|trade-?off/i.test(q) ? large : small);

async function measure(name, answerOne) {
  const before = { small: small.calls, large: large.calls };
  let cost = 0;
  for (const q of QUESTIONS) cost += await answerOne([SYSTEM, new HumanMessage(q)], q);
  console.log(`${name.padEnd(8)} small ${small.calls - before.small}  large ${large.calls - before.large}` +
    `  $${cost.toFixed(6)}`);
}

await measure("router", async (messages, q) => costOf(await routeTo(q).invoke(messages)));
await measure("cascade", async (messages) => (await cascade(messages)).cost);
```

```python
# ex3.py — a router decides BEFORE the call; a cascade decides AFTER
import re
from langchain_core.messages import HumanMessage
from d34_cascade import SYSTEM, QUESTIONS, small, large, cascade
from d34_ledger import cost_of


def route_to(q):            # a cheap rule on the question (a real one might be a small classifier)
    return large if re.search(r"compare|why|design|trade-?off", q, re.I) else small


def measure(name, answer_one):
    before = {"small": small.calls, "large": large.calls}
    cost = sum(answer_one([SYSTEM, HumanMessage(q)], q) for q in QUESTIONS)
    print(f"{name:<8} small {small.calls - before['small']}  large {large.calls - before['large']}"
          f"  ${cost:.6f}")


measure("router", lambda messages, q: cost_of(route_to(q).invoke(messages)))
measure("cascade", lambda messages, q: cascade(messages)["cost"])
```

**Expected output (both languages):**

```
router   small 7  large 3  $0.001371
cascade  small 10  large 3  $0.001434
```

**Why this design:** the router saved three small calls, because it knew in advance which
questions were hard. But it only knew because our rule matched our test questions exactly. A
router never checks the answer, so a hard question with an unusual wording goes to the small
model and the weak answer reaches the student. Choose the cascade when you **can** check the
answer cheaply (a schema, a citation) and your traffic is hard to classify. Choose the router
when the classification is easy and latency matters, since it never makes two calls in a row.
Many teams use both: route the obvious cases, cascade the uncertain ones.
</details>

### Exercise 4 — Break it four ways ●●●●○

**Predict, then run.** Each case below looks reasonable. Write down what you expect, run the
code, then explain the symptom.

1. A timestamp in the system prompt, with the cache on. Ask the same question 5 times.
2. A semantic cache at a **strict** 0.95 threshold. Save "Convert 100 Celsius to Fahrenheit",
   then ask "Convert 100 Fahrenheit to Celsius".
3. A cascade whose check is `text.length >= 200`.
4. `batch` with no concurrency cap, 20 inputs, against a provider that allows 4 in flight.

<details>
<summary>✅ Solution</summary>

```js
// ex4.js — break it four ways
import { InMemoryCache } from "@langchain/core/caches";
import { SystemMessage, HumanMessage } from "@langchain/core/messages";
import { ScriptedModel } from "./d34_model.js";
import { SemanticCache } from "./d34_semantic.js";
import { SYSTEM, QUESTIONS, large, cascade } from "./d34_cascade.js";
import { costOf } from "./d34_ledger.js";

// 1. a timestamp in the system prompt
const m = new ScriptedModel({ cache: new InMemoryCache() });
for (let i = 0; i < 5; i++) {
  const system = new SystemMessage(`You are StudyBuddy. Time: ${performance.now()}`);
  await m.invoke([system, new HumanMessage("What is a token?")]);
}
console.log("1. same question 5 times →", m.calls, "model calls");

// 2. a semantic false hit
const sem = new SemanticCache(0.95);                    // a STRICT threshold
sem.update("Convert 100 Celsius to Fahrenheit", "212 °F");
const hit = sem.lookup("Convert 100 Fahrenheit to Celsius");
console.log("2. reversed question →", hit && `${hit.answer} (score ${hit.score.toFixed(3)})`);

// 3. a cascade check that nothing passes
let largeOnly = 0, strict = 0, escalated = 0;
for (const q of QUESTIONS) {
  const messages = [SYSTEM, new HumanMessage(q)];
  largeOnly += costOf(await large.invoke(messages));
  const r = await cascade(messages, (text) => text.length >= 200);   // too strict
  strict += r.cost; escalated += r.escalated;
}
console.log(`3. escalated ${escalated}/10 → cascade $${strict.toFixed(6)} vs large only $${largeOnly.toFixed(6)}`);

// 4. no concurrency cap against a 4-in-flight limit
class RateLimited extends ScriptedModel {
  inFlight = 0;
  async _generate(messages) {
    if (this.inFlight >= 4) throw new Error("429 Too Many Requests");
    this.inFlight++;
    try { return await super._generate(messages); } finally { this.inFlight--; }
  }
}
const limited = new RateLimited({ delayMs: 100 });
const inputs = Array.from({ length: 20 }, (_, i) => `Question ${i}`);
const results = await limited.batch(inputs, {}, { returnExceptions: true });
console.log("4. no cap →", results.filter((r) => r instanceof Error).length, "of 20 failed");
```

```python
# ex4.py — break it four ways
import threading
import time
from langchain_core.caches import InMemoryCache
from langchain_core.messages import SystemMessage, HumanMessage
from d34_model import ScriptedModel
from d34_semantic import SemanticCache
from d34_cascade import SYSTEM, QUESTIONS, large, cascade
from d34_ledger import cost_of

# 1. a timestamp in the system prompt
m = ScriptedModel(cache=InMemoryCache())
for _ in range(5):
    system = SystemMessage(f"You are StudyBuddy. Time: {time.perf_counter()}")
    m.invoke([system, HumanMessage("What is a token?")])
print("1. same question 5 times →", m.calls, "model calls")

# 2. a semantic false hit
sem = SemanticCache(0.95)                                # a STRICT threshold
sem.update("Convert 100 Celsius to Fahrenheit", "212 °F")
hit = sem.lookup("Convert 100 Fahrenheit to Celsius")
print("2. reversed question →", hit and f"{hit['answer']} (score {hit['score']:.3f})")

# 3. a cascade check that nothing passes
large_only = strict = 0.0
escalated = 0
for q in QUESTIONS:
    messages = [SYSTEM, HumanMessage(q)]
    large_only += cost_of(large.invoke(messages))
    r = cascade(messages, check=lambda text: len(text) >= 200)      # too strict
    strict += r["cost"]
    escalated += r["escalated"]
print(f"3. escalated {escalated}/10 → cascade ${strict:.6f} vs large only ${large_only:.6f}")

# 4. no concurrency cap against a 4-in-flight limit
LOCK = threading.Lock()


class RateLimited(ScriptedModel):
    in_flight: int = 0

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        with LOCK:
            if self.in_flight >= 4:
                raise RuntimeError("429 Too Many Requests")
            self.in_flight += 1
        try:
            return super()._generate(messages, stop, run_manager, **kwargs)
        finally:
            with LOCK:
                self.in_flight -= 1


limited = RateLimited(delay_s=0.1)
results = limited.batch([f"Question {i}" for i in range(20)], return_exceptions=True)
print("4. no cap →", sum(isinstance(r, Exception) for r in results), "of 20 failed")
```

**Measured (identical in both languages):**

```
1. same question 5 times → 5 model calls
2. reversed question → 212 °F (score 1.000)
3. escalated 10/10 → cascade $0.003940 vs large only $0.003714
4. no cap → 16 of 20 failed
```

| # | Symptom | Why | Fix |
|---|---|---|---|
| 1 | 5 calls, 0 hits | the prompt is part of the key, and the time makes every prompt unique | stable text first; the time goes in the user message, or nowhere |
| 2 | a wrong answer, score 1.000 | word-count vectors ignore word order; test whether your real embedding model separates such pairs | no semantic hits for questions with numbers; test real pairs |
| 3 | costs **more** than no cascade | every question paid for two calls | measure the escalation rate; fix the check |
| 4 | 16 of 20 fail | JS started all 20 at once; Python's pool started 12 | `maxConcurrency` below the provider's limit |

**Why these four:** each one is a saving that turns into a cost. Number 1 makes the cache
useless. Number 2 makes it harmful. Number 3 makes the cascade a tax. Number 4 makes "faster"
slower, because every 429 becomes a retry.
</details>

### Exercise 5 — 🎯 StudyBuddy v6.6: cached, routed, budgeted ●●●●●

Put the whole day together. StudyBuddy v6.6 answers each question through these layers, in
order:

1. an **exact cache** on the normalised question (free);
2. a **semantic cache** at 0.9 — skipped for questions that contain digits (free);
3. a **budget guard**, at an illustrative $0.0009 per student per day (block or downgrade);
4. the **cascade** (small first, large on a failed check).

Run the 16-request traffic below from three students. Print a dashboard: hits per cache layer,
blocks, model calls, escalations, cost against an "all-large, no cache" baseline, p50 and p95
latency, and spend per student.

<details>
<summary>✅ Solution</summary>

```js
// studybuddy_v66.js — StudyBuddy v6.6: cached, routed, budgeted, and measured
import { HumanMessage } from "@langchain/core/messages";
import { ScriptedModel } from "./d34_model.js";
import { costOf } from "./d34_ledger.js";
import { SemanticCache } from "./d34_semantic.js";
import { SYSTEM, small, large, cascade } from "./d34_cascade.js";
import { BudgetGuard } from "./d34_budget.js";

small.delayMs = 150;                                   // simulated latencies
large.delayMs = 900;

class StudyBuddy {
  exact = new Map();                                   // normalised question → answer
  semantic = new SemanticCache(0.9);
  budget = new BudgetGuard(0.0009);                    // ILLUSTRATIVE daily limit per student
  stats = { requests: 0, exact: 0, semantic: 0, blocked: 0, escalations: 0, cost: 0 };
  latencies = [];

  async ask(student, question) {
    const t0 = performance.now();
    const r = await this.#answer(student, question);
    this.latencies.push(performance.now() - t0);
    this.stats.requests++;
    return r;
  }

  async #answer(student, question) {
    const key = question.trim().replace(/\s+/g, " ").toLowerCase();
    if (this.exact.has(key)) { this.stats.exact++; return this.exact.get(key); }   // free
    const hasNumbers = /\d/.test(question);           // numbers change the answer: no fuzzy match
    const near = hasNumbers ? null : this.semantic.lookup(question);
    if (near) { this.stats.semantic++; return near.answer; }                        // free

    const status = this.budget.status(student);
    if (status === "block") { this.stats.blocked++; return "Daily limit reached. Try again tomorrow."; }
    const messages = [SYSTEM, new HumanMessage(question)];
    let text, cost;
    if (status === "downgrade") {
      const ai = await small.invoke(messages);
      [text, cost] = [ai.content, costOf(ai)];
    } else {
      const r = await cascade(messages);
      [text, cost] = [r.ai.content, r.cost];
      if (r.escalated) this.stats.escalations++;
    }
    this.budget.charge(student, cost);
    this.stats.cost += cost;
    this.exact.set(key, text);
    if (!hasNumbers) this.semantic.update(question, text);
    return text;
  }
}

const TRAFFIC = [
  ["ayesha", "What is a token?"], ["bilal", "what is a token?"],
  ["chen", "What does temperature do in an LLM?"], ["bilal", "In an LLM, what does temperature do?"],
  ["ayesha", "Compare RAG and fine-tuning for a support bot."], ["chen", "What is an embedding?"],
  ["ayesha", "Explain why agents loop and how to stop them."],
  ["bilal", "Compare RAG and fine-tuning for a support bot."],
  ["ayesha", "Design a cache for 10,000 students."], ["chen", "What is a vector store?"],
  ["ayesha", "What is a context window?"], ["ayesha", "What is a prompt template?"],
  ["bilal", "What is streaming?"], ["ayesha", "What is streaming?"],
  ["ayesha", "Design a study plan for week 5."], ["chen", "What is a token budget?"],
];

const buddy = new StudyBuddy();
const baseline = new ScriptedModel({ model: "large", answer: (q) => large.answer(q) });
let baselineCost = 0;
for (const [student, question] of TRAFFIC) {
  await buddy.ask(student, question);
  baselineCost += costOf(await baseline.invoke([SYSTEM, new HumanMessage(question)]));
}

// ── the dashboard ────────────────────────────────────────────────────────────
const pct = (xs, p) => [...xs].sort((a, b) => a - b)[Math.ceil((p / 100) * xs.length) - 1];
const s = buddy.stats;
console.log(`StudyBuddy v6.6 — ${s.requests} requests`);
console.log(`  exact-cache hits     ${s.exact}`);
console.log(`  semantic-cache hits  ${s.semantic}`);
console.log(`  blocked by budget    ${s.blocked}`);
console.log(`  model calls          small ${small.calls}, large ${large.calls} (escalations ${s.escalations})`);
console.log(`  cost                 $${s.cost.toFixed(6)} vs $${baselineCost.toFixed(6)} all-large, uncached ` +
  `(${Math.round(100 * (1 - s.cost / baselineCost))}% saved)`);
console.log(`  latency              p50 ${Math.round(pct(buddy.latencies, 50))} ms, ` +
  `p95 ${Math.round(pct(buddy.latencies, 95))} ms`);
for (const [student, spent] of buddy.budget.spent) console.log(`  ${student.padEnd(7)} $${spent.toFixed(6)}`);
```

```python
# studybuddy_v66.py — StudyBuddy v6.6: cached, routed, budgeted, and measured
import math
import re
import time
from langchain_core.messages import HumanMessage
from d34_model import ScriptedModel
from d34_ledger import cost_of
from d34_semantic import SemanticCache
from d34_cascade import SYSTEM, small, large, cascade
from d34_budget import BudgetGuard

small.delay_s = 0.15                                 # simulated latencies
large.delay_s = 0.9


class StudyBuddy:
    def __init__(self):
        self.exact = {}                              # normalised question → answer
        self.semantic = SemanticCache(0.9)
        self.budget = BudgetGuard(0.0009)            # ILLUSTRATIVE daily limit per student
        self.stats = dict(requests=0, exact=0, semantic=0, blocked=0, escalations=0, cost=0.0)
        self.latencies = []

    def ask(self, student, question):
        t0 = time.perf_counter()
        r = self._answer(student, question)
        self.latencies.append((time.perf_counter() - t0) * 1000)
        self.stats["requests"] += 1
        return r

    def _answer(self, student, question):
        key = re.sub(r"\s+", " ", question.strip()).lower()
        if key in self.exact:                                        # free
            self.stats["exact"] += 1
            return self.exact[key]
        has_numbers = bool(re.search(r"\d", question))   # numbers change the answer: no fuzzy match
        near = None if has_numbers else self.semantic.lookup(question)
        if near:                                                     # free
            self.stats["semantic"] += 1
            return near["answer"]

        status = self.budget.status(student)
        if status == "block":
            self.stats["blocked"] += 1
            return "Daily limit reached. Try again tomorrow."
        messages = [SYSTEM, HumanMessage(question)]
        if status == "downgrade":
            ai = small.invoke(messages)
            text, cost = ai.content, cost_of(ai)
        else:
            r = cascade(messages)
            text, cost = r["ai"].content, r["cost"]
            self.stats["escalations"] += r["escalated"]
        self.budget.charge(student, cost)
        self.stats["cost"] += cost
        self.exact[key] = text
        if not has_numbers:
            self.semantic.update(question, text)
        return text


TRAFFIC = [
    ("ayesha", "What is a token?"), ("bilal", "what is a token?"),
    ("chen", "What does temperature do in an LLM?"), ("bilal", "In an LLM, what does temperature do?"),
    ("ayesha", "Compare RAG and fine-tuning for a support bot."), ("chen", "What is an embedding?"),
    ("ayesha", "Explain why agents loop and how to stop them."),
    ("bilal", "Compare RAG and fine-tuning for a support bot."),
    ("ayesha", "Design a cache for 10,000 students."), ("chen", "What is a vector store?"),
    ("ayesha", "What is a context window?"), ("ayesha", "What is a prompt template?"),
    ("bilal", "What is streaming?"), ("ayesha", "What is streaming?"),
    ("ayesha", "Design a study plan for week 5."), ("chen", "What is a token budget?"),
]

buddy = StudyBuddy()
baseline = ScriptedModel(model="large", answer=large.answer)
baseline_cost = 0.0
for student, question in TRAFFIC:
    buddy.ask(student, question)
    baseline_cost += cost_of(baseline.invoke([SYSTEM, HumanMessage(question)]))

# ── the dashboard ────────────────────────────────────────────────────────────
pct = lambda xs, p: sorted(xs)[math.ceil(p / 100 * len(xs)) - 1]
s = buddy.stats
print(f"StudyBuddy v6.6 — {s['requests']} requests")
print(f"  exact-cache hits     {s['exact']}")
print(f"  semantic-cache hits  {s['semantic']}")
print(f"  blocked by budget    {s['blocked']}")
print(f"  model calls          small {small.calls}, large {large.calls} (escalations {s['escalations']})")
print(f"  cost                 ${s['cost']:.6f} vs ${baseline_cost:.6f} all-large, uncached "
      f"({round(100 * (1 - s['cost'] / baseline_cost))}% saved)")
print(f"  latency              p50 {pct(buddy.latencies, 50):.0f} ms, "
      f"p95 {pct(buddy.latencies, 95):.0f} ms")
for student, spent in buddy.budget.spent.items():
    print(f"  {student:<7} ${spent:.6f}")
```

**Measured (Python; JS printed the same counts and costs, with p50 157 ms and p95 1088 ms):**

```
StudyBuddy v6.6 — 16 requests
  exact-cache hits     3
  semantic-cache hits  1
  blocked by budget    3
  model calls          small 9, large 2 (escalations 2)
  cost                 $0.001026 vs $0.005972 all-large, uncached (83% saved)
  latency              p50 152 ms, p95 1063 ms
  ayesha  $0.000908
  chen    $0.000095
  bilal   $0.000023
```

**Reading the dashboard honestly:**

- **Where the saving came from.** 4 of 16 requests were free (3 exact, 1 semantic). Most
  questions ran on the small model. Only 2 escalated.
- **Not all of it is good news.** Part of the 83 % comes from Ayesha's 3 **blocked** requests.
  That saving was paid for by a student who got no answer. "Design a cache for 10,000 students" also ran in
  downgrade mode, so it got the small model's "I'm not sure." Track blocks and downgrades as
  carefully as you track dollars.
- **Cache hits ignore the budget.** "What is streaming?" reached Ayesha even after she was
  blocked, because a cached answer costs nothing. That's a deliberate choice: a block protects
  your bill, not the student's access.
- **The question with digits** never touched the semantic cache — the guard from Exercise 4.
- **p95 is the escalations.** The large model's 900 ms sits behind the small model's 150 ms.

**Why this design:** the layers are ordered from cheapest-and-safest to most expensive. Exact
hits cost nothing and can't be wrong. Semantic hits cost nothing but can be wrong, so they come
second and skip risky questions. The budget check comes before any money is spent. The cascade
spends the least it can. Every layer adds a counter to the dashboard, so each saving has a
number you can check. In production, the two caches and the budget move to Redis, the ledger
rows go to your traces (Day 25), and the dashboard becomes a metrics panel.
</details>

---

## 9. Interview questions

### Basic

**Q1. Where does the cost of an LLM feature come from?**

Tokens in and tokens out, times the price per token of the model you call. So the drivers are
input size (system prompt, history, retrieved context), output length, model size, and the
number of calls — agent steps, retries, escalations. Agent loops are the surprise: each step
re-sends the growing history. In our ledger, three agent steps used 190 + 336 + 482 = 1,008
input tokens, not 3 × 190.

---

**Q2. What is the difference between an exact-match cache and a semantic cache?**

An exact cache reuses an answer only when the key is identical — in LangChain, the prompt
string plus the model's parameters. It can't serve a wrong answer, but one changed character
misses. A semantic cache embeds the question and reuses an answer when cosine similarity
passes a threshold. It catches paraphrases, but it can return a confident wrong answer (a
false hit). Use exact first, semantic second, and log every semantic hit.

---

**Q3. What does streaming do for latency?**

It cuts the time to the first token, not the total time. The user starts reading as soon as
the first words arrive. In our simulation, a long answer took ~2 s with `invoke`, and the first
streamed token arrived after ~0.3 s. The total was the same or slightly longer. It improves
*perceived* latency, which is what users judge.

---

**Q4. Why should you report p95 latency and not just the average?**

Because the mean hides the slow tail. Our cascade had a mean of ~435 ms, but no request took
that long: most took ~160 ms and the escalated ones ~1,070 ms. p50 describes the typical
experience; p95 describes the slow one that users complain about. Retries, 429s and
escalations live in the tail.

---

### Intermediate

**Q5. What is in LangChain's cache key, and what surprised you?**

Two parts: the prompt serialised to a string, and an "LLM string" describing the model and the
call options. Case, spaces, a `stop` option or a different temperature all cause misses. The
surprise is that each model class decides what goes in. Python `ChatGroq` includes the model
name, temperature and every constructor setting. JS `ChatGroq` 1.3.1 includes neither the model
nor the temperature — so in a shared JS cache, the 120B model returned the 20B model's answer. One
cache per model fixes it.

---

**Q6. How do cache hits show up in `usage_metadata`?**

Differently per language. JS sets all token counts to zero — and because the hit returns the
same message object, the first call's usage is zeroed too. Python keeps the original counts and
adds `total_cost: 0`. So a Python ledger that sums tokens charges you for free answers, and a JS
ledger that reads usage late loses real calls. Record cost as soon as each call returns, and
check for the hit marker.

---

**Q7. How does provider prompt caching work, and how do you design prompts for it?**

The provider keeps its processed state (the KV cache) for a prompt's prefix for a short time.
A later request with exactly the same prefix skips that work, so repeated input is cheaper and
starts faster. Since it's a prefix, put stable content first (system rules, tools, long
reference text) and changing content last (time, user, question). One timestamp at the top cut
our shared prefix from 97 % to 2 %. Some providers cache automatically; others need a marker,
and there is a minimum length.

---

**Q8. Router or cascade — how do you choose?**

A router classifies the question *before* calling, so it never pays for two calls and adds no
serial latency. But it never sees the answer. A cascade calls the cheap model and checks the
answer, escalating on failure. It catches misclassified questions but pays twice and is slower
on escalations. In our test the router was slightly cheaper ($0.001371 vs $0.001434). Choose a
cascade when you have a cheap, reliable check; a router when classification is easy and latency
matters.

---

**Q9. What makes a good cascade check?**

It must be cheap, fast and specific. Examples: the output parses against your schema; it cites
a retrieved source; it doesn't say "I'm not sure"; it meets a minimum length. A judge model works
too but adds a call to every request. Watch the escalation rate: a check that's too strict
escalated 10 of 10 questions, and the cascade cost more than using the large model alone.

---

**Q10. How do you choose `maxConcurrency`?**

From your provider's limits and your own measurements, not the defaults. JS `batch` with no cap
started all inputs at once; Python used its thread pool's default (12 on our 8-core machine).
Against a 4-in-flight limit, no cap meant 8 of 12 requests failed with 429, and each failure
becomes a retry. Set it just below the provider's limit, measure the wall time, and use a shared
rate limiter (Day 24) across processes.

---

### Advanced

**Q11. Design the cost and latency layers for a tutoring app with 100,000 daily users.**

Start with a ledger by feature, model and user, so every decision has a number. Then order the
layers from cheap-and-safe to expensive:

1. an exact cache on the normalised question, scoped by course and prompt version;
2. a semantic cache with a tuned threshold, skipped for personal or numeric questions;
3. a per-user daily budget that downgrades, then blocks;
4. a router or cascade that puts most traffic on a small model.

Lay prompts out for provider prefix caching. Cap concurrency below the provider limit and stream
answers. Store caches and budgets in Redis. Track hit rates, escalation rate, blocks, cost per
1,000 requests, p50 and p95. Finally, evaluate answer quality per model (Day 25), because every
saving has a quality risk.

---

**Q12. Your semantic cache's hit rate jumped from 20 % to 60 % overnight. Good news?**

Not until you know why. Likely causes: someone lowered the threshold, the embedding model
changed (scores shift between models), or a new kind of traffic arrived that looks similar but
isn't. Sample the new hits and read the matched question next to the asked one. We saw a
0.025 gap between a correct paraphrase (0.882) and a wrong question (0.857), so small threshold
changes have large effects. Keep a labelled set of should-match and shouldn't-match pairs and
re-run it on every change.

---

**Q13. A budget guard checks spend before each call, but users still go over their limit. Why, and does it matter?**

Because the check uses spend so far, and the next call's cost isn't known until it returns. In
our run, the limit was $0.001 and the final spend was $0.001005. One call over is usually fine
for a daily student budget. For a hard cap (a prepaid plan), estimate the cost first: input
tokens are known before the call, and `maxTokens` bounds the output. Charge the estimate, then
correct it from `usage_metadata`. For agents, combine it with call limits (Day 24), because one
run can make many calls.

---

**Q14. When is caching the wrong tool?**

When answers must be fresh (live data, today's schedule), personal (grades, account details),
or deliberately varied (practice questions that should differ each time). Also when traffic
rarely repeats: a cache with a 2 % hit rate adds lookup time and storage for little saving.
Measure the hit rate first. And remember stale answers: when your notes or prompt change, the
cache key needs a version, or old answers keep coming back.

---

## 10. Recap

- ✅ Cost = input tokens × price + output tokens × price, summed over **every** call — agent
  steps, retries and escalations included
- ✅ A **ledger by feature** comes first; you can't cut what you can't see
- ✅ LangChain's exact cache is literal: case, spaces, `stop` and settings all cause misses
- ✅ **JS `ChatGroq`'s cache key has no model name or temperature** — one cache per model
- ✅ Cache hits: **JS zeros usage (even on the first message); Python keeps tokens + `total_cost: 0`**
- ✅ Semantic caching catches paraphrases but can serve **false hits** — tune on real pairs, skip
  numbers and personal questions
- ✅ Provider prompt caching needs an **identical prefix**: stable content first
- ✅ Routers decide before the call; cascades check after — and a bad check costs more than no
  cascade
- ✅ Cap concurrency yourself: JS `batch` starts everything; Python uses its pool default
- ✅ Streaming improves time to first token, not total time; output length drives total time
- ✅ A budget guard caps dollars per user, degrading before it blocks

### The one-glance summary

```
   question ─▶ normalise ─▶ exact cache ─▶ semantic cache ─▶ budget ─▶ router/cascade ─▶ model
                  free         free          free, risky      $0       cheap first
   prompts:   stable prefix first  → provider caching
   batches:   maxConcurrency below the provider limit
   answers:   short by prompt, capped by maxTokens, streamed
   measure:   ledger by feature · hit rates · escalation rate · blocks · cost/1k · p50 + p95
```

### Tomorrow

**[Day 35 — AI security](day-35-ai-security.md)**: StudyBuddy is now cheap and fast — and
every layer you added today is something an attacker can use. A shared cache can leak one
student's answer to another. A semantic cache can be poisoned. A budget can be drained on
purpose. Tomorrow you look at your system the way an attacker does. You meet the OWASP Top 10 for LLM
applications, red-team your own app, add guardrails, and check the models and packages you
trust.

### Quick self-check

1. Your JS app uses `cache: true` on two `ChatGroq` models, GPT-OSS 20B and 120B, in a cascade.
   Escalated answers look as weak as the small model's. Why?
2. Your Python cost dashboard shows no savings after you switched on `set_llm_cache`. The hit
   rate is 40 %. What is wrong?
3. You moved the student's name from the top of the system message into the user message. Does
   that help LangChain's exact cache, the provider's prompt cache, or both?

<details>
<summary>Answers</summary>

1. `cache: true` gives both models the same global `InMemoryCache`, and JS `ChatGroq`'s cache
   key contains no model name. When the 120B model gets the same prompt, it hits the 20B model's
   saved answer (measured: `big model got: SMALL MODEL ANSWER`). Give each model its own
   `new InMemoryCache()`.

2. Python cache hits keep their original `input_tokens` and `output_tokens` and only add
   `total_cost: 0`. A ledger that multiplies tokens by price charges for every hit. Return $0
   when `usage_metadata.get("total_cost") == 0`.

3. Only the provider's prompt cache. The long system message is now an identical prefix for
   every student. In §4.5 that raised the shared prefix from 2 % to 97 %, so the provider can
   reuse its work on it. LangChain's exact cache still sees a different prompt for each student,
   because its key is the **whole** prompt. To get exact hits across students, cache at the app
   level on the normalised question (Exercise 5), and keep per-student data out of what you
   cache.
</details>

---

<div align="center">

**[← Day 33 — Multimodal](day-33-multimodal.md)** · **[Week 5 index](README.md)** · **[Day 35 — AI security →](day-35-ai-security.md)**

</div>
