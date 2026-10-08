# Day 03 — Choosing a Model · Why LangChain Exists

> ⏱ **Time:** ~2.5 hours · 🎯 **Prereqs:** [Day 02](day-02-prompt-engineering-and-raw-apis.md) and [Day 0B](../week-00-start-here/day-00b-programming-for-ai.md) · 🧩 **Difficulty:** ●●○○○

**Today you learn:** Yesterday you called one model through its own SDK. Two questions follow
at once: *which* model should you call, and what does it cost to switch? Today you learn to
compare models on quality, price, speed, context size, licence and privacy. Then you test them
on **your own** examples with a tiny evaluation, instead of trusting a leaderboard. Finally you
see why switching models by hand is so much code. That is the honest reason LangChain exists —
and you learn when *not* to use it.

This is the day you stop picking models by reputation.

> 📖 **Words you'll meet today**
>
> - **Open-weight model** — a model whose trained numbers (weights) you can download and run
>   yourself. A **closed** model is only available through the maker's API.
> - **Parameters** — the numbers inside a model that were learned in training. "20B" means
>   20 billion of them.
> - **Context window** — the most tokens a model can handle in one call, input and output
>   together (Day 01).
> - **Reasoning model** — a model that writes hidden "thinking" tokens before its answer. It is
>   slower and costs more, but is better at multi-step problems.
> - **Price per million tokens** — how providers charge: one price for input tokens, a usually
>   higher one for output tokens.
> - **Time to first token (TTFT)** — how long until the first word of the answer appears.
> - **Benchmark** — a public test set used to score models, such as a set of exam questions.
> - **Eval** — your own small test set: real inputs from your app, with the answers you expect.

---

## 1. The problem

Your Day 02 study bot works. It runs on Groq's `openai/gpt-oss-120b`. Then the messages
start:

```
   manager:   "Why this model? A blog says Model X is top of the leaderboard."
   finance:   "Model Y is much cheaper. Can we switch?"
   security:  "Do student messages leave the EU? Does the provider train on them?"
   a student: "Why does it take so long before anything appears?"
```

You can't answer any of them. You picked the model because a tutorial used it. You don't know
what a request costs, how fast the first word appears, or whether a cheaper model would do the
job just as well **on your task**.

Then you try to test Model X. It comes from a different provider, so it has a different SDK, a
different request shape, a different response shape, and a different way to ask for JSON. Your
Day 02 code needs rewriting just to *try* it. Now imagine trying three models.

Two problems, then: **how to choose a model**, and **how to make switching cheap**. The first
half of today solves the first. The second half explains why LangChain exists, which solves
the second.

### The real-life version

Hiring someone. A CV lists impressive exam results — that is a **benchmark**. But you don't hire
from the CV alone. You give the best few candidates a short work test, using real tasks from
*your* job — that is an **eval**. You also check the salary (**price**), how soon they can start
(**latency**), and whether they can sign your confidentiality agreement (**privacy and
licence**).

And if every candidate needed a different office layout before they could even start the test,
you would test fewer candidates. A common layout that everyone fits into is what a framework
gives you.

---

## 2. Mental model

Choosing a model is a funnel. Hard rules remove candidates first, then a test on your own
examples decides between the rest:

```
   all models
      │   1. HARD RULES — data may not leave the EU? must read images? licence allows our use?
      ▼
   allowed models
      │   2. SHORTLIST — 2–3 candidates: one big, one small, maybe one open-weight
      ▼
   shortlist
      │   3. YOUR EVAL — 5 cases today, 50+ later, graded by a rule you wrote first
      ▼
   quality + latency + cost per request, measured
      │   4. DECIDE BY RULE — cheapest model that passes the quality and latency bars
      ▼
   chosen model  +  a fallback from a different provider
```

| Dimension | The question it answers | Where you read it | Measure it yourself? |
|---|---|---|---|
| Quality | Does it do **my** task well? | benchmarks (a hint only) | ✅ always — your eval |
| Price | What does one request cost? | provider's pricing page | ✅ token counts × prices |
| Latency | How soon does the answer start and finish? | rarely published reliably | ✅ time it |
| Context window | Do my prompt and documents fit? | model card | — |
| Modalities | Can it read images, audio, PDFs? | model card | ✅ try one |
| Reasoning | Does it "think" before answering? | model card | ✅ count output tokens |
| Licence & privacy | May I use it this way? Where does my data go? | licence, terms, data policy | — read them |

And the framework decision, up front:

```
                  Do you need MORE than one model call?
                              │
              ┌───────────────┴────────────────┐
             NO                                YES
              │                                 │
      Just use the SDK.              Do you need retrieval, tools,
      LangChain adds nothing.        loops, persistence, or streaming
                                     through multiple steps?
                                              │
                              ┌───────────────┴───────────────┐
                             NO                               YES
                              │                                │
                    SDK + 50 lines of glue.        Use LangChain / LangGraph.
                    Honestly fine.                 You'd be rebuilding it.
```

---

## 3. First principles

### 3.1 Closed models vs open-weight models

> 💬 **In plain words:** a closed model lives only on its maker's servers, and you rent it by
> the token. An open-weight model can be downloaded, so you can run it on your own machine.

A model is, in the end, a very large file of numbers — its **weights**. The question is who
holds that file.

| | Closed model | Open-weight model |
|---|---|---|
| How you use it | only through the maker's API | download and run it yourself, **or** call a host's API |
| Who sees your data | the provider | only you, if you run it yourself |
| Cost model | pay per token | pay for the hardware (or a host's per-token price) |
| Can you change it? | only through the provider's options | yes — fine-tune it, quantise it (shrink it) |
| Typical examples | the big commercial chat models | GPT-OSS, Llama, Mistral, Qwen, Gemma families |

Groq is a useful example of the middle path. It **hosts** open-weight models and charges per
token, so you use an open-weight model through a closed-style API. Its model page describes
GPT-OSS 120B, this course's default, as "OpenAI's flagship open-weight MoE model". Ollama, which
you meet in Week 2, runs open-weight models on your own laptop.

> ⚠️ **"Open-weight" is not the same as "open source".** You usually get the weights, but not
> the training data or code. The licence may also add conditions, such as rules about how the
> model may be used. Read it before you build a product on it (§3.9).

### 3.2 Model size: what "20B" and "120B" cost you

> 💬 **In plain words:** bigger models usually know more and reason better, but they are slower
> and need much more memory to run.

The number in a name like `openai/gpt-oss-20b` or `openai/gpt-oss-120b` is the parameter
count: 20 billion and 120 billion. More parameters usually means more knowledge and better
reasoning. It also means more computing per token, so the model is slower and dearer to run.

You can work out the memory a model needs with simple arithmetic. Each parameter is stored in
a few bytes; 16-bit storage uses 2 bytes:

```
    20 billion parameters × 2 bytes =  40 GB   ← more than a gaming GPU holds
   120 billion parameters × 2 bytes = 240 GB   ← needs several data-centre GPUs
```

That is arithmetic, not a measurement, and it covers only the weights; running the model
needs extra memory on top. It explains a real pattern, though: small models are cheap and fast,
and big models usually live in the cloud. Storing each parameter in fewer bits (called
**quantisation**) shrinks the file, at some cost in quality.

> 💡 **The name is not the whole story.** Groq's page says GPT-OSS 120B is a
> "Mixture-of-Experts (MoE)" model with "5.1B active per forward pass". A mixture-of-experts
> model is split into many smaller parts, and only a few of them work on each token. So it
> stores 120 billion numbers but uses about 5 billion per token. Speed depends on that second
> number. Read the model card, not just the name.

The practical lesson: **don't assume you need the biggest model.** For a simple task — sorting
messages into three labels — a small model may score just as well. Only your eval can tell you.

### 3.3 Context window: how much fits

> 💬 **In plain words:** the context window is the size of the model's desk. Your
> instructions, the chat so far, any documents, and the answer must all fit on it at once.

Day 01 showed that the context window counts input **and** output tokens together. When you
compare models, ask two questions:

1. **Does my biggest real request fit?** Add the system prompt, the longest chat history you
   keep, the documents you include, and the longest answer you allow.
2. **Do I want to fill it?** A bigger window is not free. Every input token is billed, and
   long inputs take longer to read. Some published studies also report that models use facts
   in the middle of a very long prompt less reliably (not measured here — test it on your
   model). Retrieving the *right* few pages (Week 2) often beats pasting in everything.

### 3.4 Reasoning models vs non-reasoning models

> 💬 **In plain words:** a reasoning model "thinks out loud" privately before it answers. That
> helps on hard problems, but you wait for the thinking and you pay for it.

On Day 02 you saw chain-of-thought: asking a model to write its steps improves accuracy on
multi-step problems. **Reasoning models** are trained to do this by themselves. They produce
many hidden "thinking" tokens before the visible answer.

| | Non-reasoning (chat) model | Reasoning model |
|---|---|---|
| Good at | chat, extraction, classification, rewriting | maths, code, planning, multi-step logic |
| Time to first visible token | short | long — the thinking comes first |
| Output tokens billed | the answer | the answer **plus** the thinking (check your provider) |
| Use it when | the task is simple or speed matters | a cheaper model fails your eval on hard cases |

Exercise 3 measures the effect with pretend models: a 1.5-second "think" made the first token
appear about **ten times later**, even though the reasoning model then wrote faster.

### 3.5 Modalities: text, images, audio

> 💬 **In plain words:** "modality" means the kind of input or output: text, pictures, sound.
> Not every model handles every kind.

A **multimodal** model can take more than text — for example a photo of a whiteboard, a PDF
page with a chart, or a voice note. Check the model card for two lists: what it accepts and
what it produces. Images and audio are also turned into tokens, so they cost money and use
context space like text does. If your app only handles text, ignore this column. If it must read
scanned worksheets, it is a hard rule in step 1 of the funnel.

### 3.6 Pricing: per million input and output tokens

> 💬 **In plain words:** you pay for every token you send and every token you get back. The two
> have different prices, and the output price is usually higher.

Providers list prices **per million tokens** (sometimes written "per 1M" or "/MTok"), with
separate prices for input and output. One request costs:

```
   cost = input_tokens × input_price / 1,000,000  +  output_tokens × output_price / 1,000,000
```

**Why output usually costs more.** Day 01 explained the mechanism. The model reads all your
input tokens in one parallel pass. But it writes the output one token at a time, and each new
token needs its own pass through the network. More GPU time per token means a higher price.

Three things make real bills bigger than first guesses:

- **Chat history.** Models are stateless (Day 01), so every turn re-sends the whole
  conversation. Input grows each turn. In Exercise 2, a 10-turn chat used **11,500** input
  tokens, not the 2,500 a naive estimate gives.
- **Hidden reasoning tokens.** They are output tokens, and output is the expensive side.
- **Retries.** A retried call is billed again.

Some providers also offer discounts — for example cheaper **cached** input when you re-send
the same long prompt, or cheaper batch jobs. Free tiers usually limit requests per minute
instead of charging. Prices change often, so every price in today's code is **illustrative**.
§3.11 quotes real Groq prices, with the date they were read. Copy current numbers from your
provider's pricing page before you rely on them.

### 3.7 Latency: time to first token and tokens per second

> 💬 **In plain words:** two numbers describe speed. How long until the answer *starts*, and how
> fast it *flows* once it has started.

```
   request sent ─┬─ waiting in the queue
                 ├─ reading your prompt (one parallel pass)
                 ├─ thinking (reasoning models only)
   first token ──┘  ← TIME TO FIRST TOKEN (TTFT)
                 ├─ token, token, token …   ← TOKENS PER SECOND (decode speed)
   last token ───┘

   total time ≈ TTFT + (output tokens ÷ tokens per second)
```

Which one matters depends on the job:

| Job | What the user feels | Optimise |
|---|---|---|
| a chat window with streaming | the wait before anything appears | **TTFT** |
| a background batch of 10,000 summaries | nothing — only the total time and the bill | tokens per second, then cost |
| a voice assistant | silence before it speaks | TTFT, strongly |

Measure latency on **your** prompts, several times, and report the **median** (the middle
value), not the average. One slow first call — a "cold start" — can drag the average far from
the truth (Exercise 2, break 6).

### 3.8 Benchmarks and their limits

> 💬 **In plain words:** a benchmark is a public exam for models. It tells you something, but not
> whether a model is good at *your* job.

Benchmarks are shared test sets. Some test knowledge with multiple-choice questions (MMLU is a
well-known example). Some test code by running the model's programs (HumanEval). Some collect
human votes between two anonymous answers (LMArena). They are useful for a first shortlist.
They are dangerous as a final answer, for four reasons:

1. **Your task is not the benchmark.** A model that wins at exam questions may be worse at
   your label set, your language, or your tone.
2. **Contamination.** Benchmark questions are public. If they leaked into a model's training
   data, the model may have *memorised* answers, so its score is inflated.
3. **Different settings.** Scores depend on the prompt, the number of examples, and other
   settings. Numbers from different sources are often not comparable.
4. **Saturation.** When top models all score near the maximum, the remaining differences are
   noise.

The fix is not a better leaderboard. It is **your own eval**: a small set of real inputs from
your app, with the answers you expect, graded by a rule you wrote *before* looking at results.

### 3.9 Licence and data privacy

> 💬 **In plain words:** before you send real user data anywhere, read where it goes and what
> the provider may do with it. Before you build on an open-weight model, read its licence.

Questions to answer for every candidate, from its documents — not from memory or a blog:

| Question | Where to look |
|---|---|
| Does the provider use my API data to train its models? | data-usage or privacy policy |
| How long does it keep my prompts and outputs? | data retention section |
| In which country or region is my data processed? | terms, enterprise or region options |
| May I use this model commercially, and at my scale? | the model's licence |
| Are some uses forbidden? | acceptable-use policy |

If the answers rule out every hosted option, that is a strong reason to **self-host an
open-weight model**: the data never leaves your machines. This is a hard rule, so it belongs in
step 1 of the funnel. A model that fails it is out, however well it scores.

> 🔒 Never send personal data (names, emails, health or school records) to a provider whose
> data policy you have not read. Day 24 shows how to redact it first.

### 3.10 A decision procedure, step by step

> 💬 **In plain words:** write your rules down, test a few models on your own examples, and
> pick the cheapest one that passes. Then keep testing.

1. **Describe the task in one sentence**, and collect 5 real inputs with the answers you
   expect. (Today: 5. Before launch: 50 or more.)
2. **Write the hard rules.** Data location, modalities, licence, the context size you need.
3. **Filter**, then **shortlist 2–3 models** — usually one large, one small, and maybe one
   open-weight model.
4. **Write the decision rule before you run anything.** For example: "accuracy ≥ 80 %, median
   latency ≤ 500 ms, then the cheapest wins." Writing it first stops you from bending the rule
   to fit a favourite.
5. **Run the same cases against every candidate.** Record accuracy, median latency and token
   counts (§4.2).
6. **Turn token counts into money** at your expected volume (§4.1).
7. **Apply the rule.** Pick the winner, and choose a **fallback from a different provider**
   for outages (Day 24).
8. **Re-run the eval** whenever a model, a price or your prompt changes. The eval is now a
   permanent part of your project — Day 25 turns it into a full test suite.

The most important step is the one most people skip: **build a tiny eval on YOUR cases.**
A leaderboard tells you which model is best on average. Your eval tells you which model is
best for you.

### 3.11 A worked example: Groq's models on 7 October 2026

> 💬 **In plain words:** here is the funnel used on real models with real prices. It also shows
> why you must expect model names to change.

**Why this course changed its default model.** Earlier versions of this course used Groq's
Llama 3.3 70B model. On 7 October 2026, a call with a normal Groq key returned this:

```
404 The model `llama-3.3-70b-versatile` does not exist or you do not have access to it.
```

Groq's models page now lists that model under "Enterprise", with "Contact Sales" instead of a
price. Nothing in our code was wrong. The model simply left the plan we use. This is a common way
for an LLM app to break, and it is why step 8 above says: re-run your eval when a model changes.

These are the chat models a normal key could use that day, copied from
[console.groq.com/docs/models](https://console.groq.com/docs/models) on 7 October 2026:

| Model ID | Status | US$ per 1M tokens (in / out) | Speed Groq publishes | Context window | Max output |
|---|---|---|---|---|---|
| `openai/gpt-oss-120b` | production | 0.15 / 0.60 | 500 tokens/s | 131,072 | 65,536 |
| `openai/gpt-oss-20b` | production | 0.075 / 0.30 | 1,000 tokens/s | 131,072 | 65,536 |
| `qwen/qwen3.8-27b` | **preview** | 0.80 / 4.00 | 450 tokens/s | 131,072 | 16,384 |

Now walk the funnel from §2.

1. **Hard rules.** Groq's page says preview models are "for evaluation purposes only". They
   "may be discontinued at short notice". So Qwen is out for StudyBuddy's main path. The
   course uses it only for one teaching demo on Day 02, a text format that the GPT-OSS models
   do not follow.
2. **Shortlist.** One big model and one small one: GPT-OSS 120B and GPT-OSS 20B. Both are
   reasoning models (§3.4). They write hidden thinking tokens, and those are billed as output.
   On Day 04, a three-sentence answer from the 120B model used 156 output tokens. 49 of them
   were thinking.
3. **Price.** Here is the §4.1 workload (1,200 tokens in, 300 out, 300,000 requests a month)
   with the real prices from the table. This is arithmetic, not a bill:

   ```
   openai/gpt-oss-120b  $0.000360 per request   $108.00 per month
   openai/gpt-oss-20b   $0.000180 per request   $54.00 per month
   qwen/qwen3.8-27b     $0.002160 per request   $648.00 per month
   ```

   Add the thinking tokens to the output count for a real estimate. Also note that the free
   tier limits requests per minute instead of charging. Our key got `429` errors above 30
   requests a minute to GPT-OSS 120B.
4. **Speed.** The speeds in the table are Groq's own figures, not a measurement on your
   prompts. In Day 04, Exercise 2 you measure time to first token and tokens per second
   yourself.
5. **Decide by rule.** The 20B model costs half as much, and Groq says it is twice as fast.
   Whether it is good enough for StudyBuddy is a question only your eval can answer. Day 04,
   Exercise 1 sends the same question to both models.

> 📦 **Re-check before you copy.** The names, prices, speeds and status above were read on
> 7 October 2026. If a name returns 404, open console.groq.com/docs/models and pick a current
> production model.

---

## 4. Code — JavaScript

Both files run with plain Node — no packages, no key.

### 4.1 A cost estimator

```js
// cost.js — turn token counts into money.
// ⚠️ ILLUSTRATIVE PRICES. These are made-up numbers for made-up models.
// Real prices change often: copy them from your provider's pricing page.
const PRICES = {                        // US$ per 1,000,000 tokens
  "model-small":     { input: 0.10, output: 0.30 },
  "model-large":     { input: 0.60, output: 1.80 },
  "model-reasoning": { input: 1.00, output: 4.00 },
};

function costPerRequest(model, inputTokens, outputTokens) {
  const p = PRICES[model];
  return (inputTokens * p.input + outputTokens * p.output) / 1_000_000;
}

// One StudyBuddy question: system prompt + notes + question in, a short answer out.
const INPUT = 1_200;
const OUTPUT = 300;
const THINKING = 1_500;                 // hidden reasoning tokens, billed as output
const REQUESTS_PER_MONTH = 1_000 * 10 * 30;   // 1,000 users × 10 questions × 30 days

for (const model of Object.keys(PRICES)) {
  const out = model === "model-reasoning" ? OUTPUT + THINKING : OUTPUT;
  const one = costPerRequest(model, INPUT, out);
  console.log(
    model.padEnd(16),
    `$${one.toFixed(6)} per request`.padEnd(26),
    `$${(one * REQUESTS_PER_MONTH).toFixed(2)} per month for 1,000 users`,
  );
}
```

Expected output (verified):

```
model-small      $0.000210 per request      $63.00 per month for 1,000 users
model-large      $0.001260 per request      $378.00 per month for 1,000 users
model-reasoning  $0.008400 per request      $2520.00 per month for 1,000 users
```

Look at the last line. The reasoning model's price per token is not wildly higher, but the
**1,500 hidden thinking tokens** are billed at the output price. They turn a $378 month into a
$2,520 month. With these made-up prices, that is a factor of more than six — for the same
visible answer.

### 4.2 A tiny model-comparison harness

This is the heart of today: the same test cases, run against each candidate, with accuracy and
**measured** latency. The two models are pretend ones with scripted answers, so the result is
the same every time and you need no key.

```js
// compare.js — the same 5 test cases against two models: accuracy + measured latency.
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// Two pretend models. They have the same invoke() method as a real chat model,
// but their answers are scripted, so every run gives the same accuracy.
function scriptedModel(name, delayMs, answers) {
  return {
    name,
    async invoke(prompt) {
      await sleep(delayMs);
      return { content: answers[prompt] ?? "no idea" };
    },
  };
}

// YOUR task: sort a student's message into question / quiz / off-topic.
const CASES = [
  { input: "What is photosynthesis?", expected: "question" },
  { input: "Test me on chapter 3", expected: "quiz" },
  { input: "Who won the match last night?", expected: "off-topic" },
  { input: "Can you explain mitosis again, slower?", expected: "question" },
  { input: "Give me 5 questions on the French Revolution", expected: "quiz" },
];

const large = scriptedModel("model-large", 400, {
  [CASES[0].input]: "question", [CASES[1].input]: "quiz", [CASES[2].input]: "off-topic",
  [CASES[3].input]: "question", [CASES[4].input]: "Quiz.",
});
const small = scriptedModel("model-small", 80, {
  [CASES[0].input]: "question", [CASES[1].input]: "quiz", [CASES[2].input]: "question",
  [CASES[3].input]: "Question", [CASES[4].input]: "question",
});

// Grade the meaning, not the formatting: "Quiz." and "quiz" are the same label.
const normalise = (s) => s.trim().toLowerCase().replace(/[.!]+$/, "");

async function evaluate(model) {
  let correct = 0;
  const times = [];
  for (const c of CASES) {
    const t0 = performance.now();
    const reply = await model.invoke(c.input);
    times.push(performance.now() - t0);
    if (normalise(reply.content) === c.expected) correct++;
  }
  times.sort((a, b) => a - b);
  return {
    model: model.name,
    accuracy: `${correct}/${CASES.length}`,
    medianMs: Math.round(times[Math.floor(times.length / 2)]),
    slowestMs: Math.round(times.at(-1)),
  };
}

for (const model of [large, small]) console.log(await evaluate(model));
```

Expected output (verified; latency varies a little per run):

```
{
  model: 'model-large',
  accuracy: '5/5',
  medianMs: 411,
  slowestMs: 454
}
{ model: 'model-small', accuracy: '3/5', medianMs: 91, slowestMs: 97 }
```

The latencies come from the pretend models' fixed waits (400 ms and 80 ms). So here they test
the **harness**, not a real model. Swap in real models on Day 04 and the same code measures
real ones — every LangChain chat model has the same `invoke` method.

That last sentence is the bridge to the second half of today. The harness only works because
both models share **one interface**. Real providers don't.

### 4.3 The framework-vs-no-framework comparison

**Task:** ask three models the same question, pick the fastest successful answer, retry on
rate limit, and return structured JSON. (`withRetry` is the helper from
[Day 0B §3.10](../week-00-start-here/day-00b-programming-for-ai.md).)

> The *WITH LangChain* snippet was run against Groq in October 2026, and its real result is in
> the comment. The *WITHOUT* snippet was not executed: it uses Google's older SDK package, and
> SDK names change over time. Check your versions.

```js
// ─── WITHOUT a framework ──────────────────────────────────────────────────
import Groq from "groq-sdk";
import { GoogleGenerativeAI } from "@google/generative-ai";

const groq = new Groq({ apiKey: process.env.GROQ_API_KEY });
const gem = new GoogleGenerativeAI(process.env.GOOGLE_API_KEY);

async function askGroq(model, prompt) {
  const r = await groq.chat.completions.create({
    model,
    messages: [{ role: "user", content: prompt }],
    response_format: { type: "json_object" },
  });
  return JSON.parse(r.choices[0].message.content);      // shape unvalidated
}

async function askGemini(prompt) {
  const m = gem.getGenerativeModel({
    model: "gemini-3.8-flash",
    generationConfig: { responseMimeType: "application/json" },   // ← different API entirely
  });
  const r = await m.generateContent(prompt);
  return JSON.parse(r.response.text());                 // ← different response shape
}

async function race(prompt) {
  const attempts = [
    withRetry(() => askGroq("openai/gpt-oss-120b", prompt)),
    withRetry(() => askGroq("openai/gpt-oss-20b", prompt)),
    withRetry(() => askGemini(prompt)),
  ];
  return Promise.any(attempts);        // and you still have to validate the shape yourself
}
```

Three providers = three SDKs, three request shapes, three response shapes, three JSON-mode
mechanisms. Now add streaming (three more shapes) and tool calling (three more).

```js
// ─── WITH LangChain ───────────────────────────────────────────────────────
import { ChatGroq } from "@langchain/groq";
import { ChatGoogleGenerativeAI } from "@langchain/google-genai";
import * as z from "zod";

const Answer = z.object({ answer: z.string(), confidence: z.number() });

const primary = new ChatGroq({ model: "openai/gpt-oss-120b" })
  .withStructuredOutput(Answer, { method: "jsonSchema" })   // the mode GPT-OSS handles (Day 06)
  .withRetry({ stopAfterAttempt: 3 })
  .withFallbacks([
    new ChatGoogleGenerativeAI({ model: "gemini-3.8-flash" }).withStructuredOutput(Answer),
  ]);

const result = await primary.invoke("What is the capital of Japan?");
// → { answer: 'Tokyo', confidence: 1 }   validated, typed, retried, with fallback
```

**That's the pitch in one screen.** One interface, one response shape, and retries, fallbacks
and schema validation as add-on modifiers. Your comparison harness would work with any of
these models unchanged. You'll build all of this properly on Days 04–07.

> ⚠️ **Why `jsonSchema`?** Structured output can be produced in more than one way. With GPT-OSS
> on Groq, the default way (a forced tool call) failed in this course's Python tests with
> `400 Tool choice is required, but model did not call a tool`. JSON-schema mode worked in both
> languages, so the snippets ask for it. Day 06 explains the modes.

---

## 5. Code — Python

Both files run with plain Python — no packages, no key.

### 5.1 A cost estimator

```python
# cost.py — turn token counts into money.
# ⚠️ ILLUSTRATIVE PRICES. These are made-up numbers for made-up models.
# Real prices change often: copy them from your provider's pricing page.
PRICES = {                              # US$ per 1,000,000 tokens
    "model-small":     {"input": 0.10, "output": 0.30},
    "model-large":     {"input": 0.60, "output": 1.80},
    "model-reasoning": {"input": 1.00, "output": 4.00},
}

def cost_per_request(model, input_tokens, output_tokens):
    p = PRICES[model]
    return (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000

# One StudyBuddy question: system prompt + notes + question in, a short answer out.
INPUT = 1_200
OUTPUT = 300
THINKING = 1_500                        # hidden reasoning tokens, billed as output
REQUESTS_PER_MONTH = 1_000 * 10 * 30    # 1,000 users × 10 questions × 30 days

for model in PRICES:
    out = OUTPUT + THINKING if model == "model-reasoning" else OUTPUT
    one = cost_per_request(model, INPUT, out)
    print(f"{model:<16} {'$' + format(one, '.6f') + ' per request':<26} "
          f"${one * REQUESTS_PER_MONTH:.2f} per month for 1,000 users")
```

Expected output (verified): the same three lines as the JavaScript version.

```
model-small      $0.000210 per request      $63.00 per month for 1,000 users
model-large      $0.001260 per request      $378.00 per month for 1,000 users
model-reasoning  $0.008400 per request      $2520.00 per month for 1,000 users
```

### 5.2 A tiny model-comparison harness

```python
# compare.py — the same 5 test cases against two models: accuracy + measured latency.
import statistics, time
from types import SimpleNamespace


class ScriptedModel:
    """A pretend model with the same invoke() as a real one; answers are scripted."""

    def __init__(self, name, delay, answers):
        self.name, self.delay, self.answers = name, delay, answers

    def invoke(self, prompt):
        time.sleep(self.delay)
        return SimpleNamespace(content=self.answers.get(prompt, "no idea"))


# YOUR task: sort a student's message into question / quiz / off-topic.
CASES = [
    {"input": "What is photosynthesis?", "expected": "question"},
    {"input": "Test me on chapter 3", "expected": "quiz"},
    {"input": "Who won the match last night?", "expected": "off-topic"},
    {"input": "Can you explain mitosis again, slower?", "expected": "question"},
    {"input": "Give me 5 questions on the French Revolution", "expected": "quiz"},
]
q = [c["input"] for c in CASES]

large = ScriptedModel("model-large", 0.400, {
    q[0]: "question", q[1]: "quiz", q[2]: "off-topic", q[3]: "question", q[4]: "Quiz."})
small = ScriptedModel("model-small", 0.080, {
    q[0]: "question", q[1]: "quiz", q[2]: "question", q[3]: "Question", q[4]: "question"})

# Grade the meaning, not the formatting: "Quiz." and "quiz" are the same label.
def normalise(s):
    return s.strip().lower().rstrip(".!")

def evaluate(model):
    correct, times = 0, []
    for c in CASES:
        t0 = time.perf_counter()
        reply = model.invoke(c["input"])
        times.append((time.perf_counter() - t0) * 1000)
        if normalise(reply.content) == c["expected"]:
            correct += 1
    return {"model": model.name, "accuracy": f"{correct}/{len(CASES)}",
            "median_ms": round(statistics.median(times)), "slowest_ms": round(max(times))}

for model in (large, small):
    print(evaluate(model))
```

Expected output (verified; latency varies a little per run):

```
{'model': 'model-large', 'accuracy': '5/5', 'median_ms': 403, 'slowest_ms': 409}
{'model': 'model-small', 'accuracy': '3/5', 'median_ms': 88, 'slowest_ms': 90}
```

### 5.3 The framework-vs-no-framework comparison

> The *WITH LangChain* snippet was run against Groq in October 2026, and its real result is in
> the comment. The *WITHOUT* snippet was not executed: it uses Google's older SDK package, and
> SDK names change over time. Check your versions.

```python
# ─── WITHOUT a framework ──────────────────────────────────────────────────
import json, os
from groq import Groq
import google.generativeai as genai

groq = Groq(api_key=os.environ["GROQ_API_KEY"])
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

def ask_groq(model, prompt):
    r = groq.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    return json.loads(r.choices[0].message.content)      # shape unvalidated

def ask_gemini(prompt):
    m = genai.GenerativeModel(
        "gemini-3.8-flash",
        generation_config={"response_mime_type": "application/json"},  # different API
    )
    return json.loads(m.generate_content(prompt).text)    # different response shape

# ...plus your own racing, retry, fallback and validation logic.
```

```python
# ─── WITH LangChain ───────────────────────────────────────────────────────
from pydantic import BaseModel
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI

class Answer(BaseModel):
    answer: str
    confidence: float

primary = (
    ChatGroq(model="openai/gpt-oss-120b")
    # the mode GPT-OSS handles (Day 06)
    .with_structured_output(Answer, method="json_schema", strict=True)
    .with_retry(stop_after_attempt=3)
    .with_fallbacks([
        ChatGoogleGenerativeAI(model="gemini-3.8-flash").with_structured_output(Answer)
    ])
)

result = primary.invoke("What is the capital of Japan?")
print(result)   # answer='Tokyo' confidence=1.0
```

### 5.4 The JS ↔ Python translation for today

| Concept | JavaScript | Python |
|---|---|---|
| a price table | object of objects | dict of dicts |
| big numbers readable | `1_000_000` | `1_000_000` |
| money to 6 places | `one.toFixed(6)` | `f"{one:.6f}"` |
| pad a column | `str.padEnd(16)` | `f"{s:<16}"` |
| precise timer | `performance.now()` (ms) | `time.perf_counter()` (s — × 1000 for ms) |
| median | sort, take the middle | `statistics.median(times)` |
| a fake model | object with `async invoke()` | class with `invoke()` |
| strip trailing dots | `s.replace(/[.!]+$/, "")` | `s.rstrip(".!")` |
| structured output | `.withStructuredOutput(Zod)` | `.with_structured_output(Pydantic)` |
| retry / fallback | `.withRetry({ stopAfterAttempt })` / `.withFallbacks([...])` | `.with_retry(stop_after_attempt=)` / `.with_fallbacks([...])` |
| sync option | ❌ none — always async | ✅ `invoke` (sync) and `ainvoke` (async) |

---

## 6. Under the hood — why LangChain exists

### The honest version

LangChain is not "a way to call an LLM". Calling an LLM is `fetch()`. LangChain is **a set of
interfaces** so that everything downstream of the model call doesn't have to know which model
you used.

Here's what it actually gives you, ranked by how much work it saves:

| # | What | Without it you'd write |
|---|---|---|
| 1 | **The `Runnable` interface** | Your own `invoke`/`stream`/`batch` contract, implemented consistently across every step, plus composition |
| 2 | **Provider abstraction** | An adapter per provider for messages, streaming, tool calls, JSON mode, token usage |
| 3 | **Structured output** | Schema → JSON Schema → tool call → parse → validate → retry |
| 4 | **Retrieval plumbing** | Loaders, splitters, embedding batching, vector store adapters, retrievers (Week 2) |
| 5 | **Agent/graph runtime** | The loop you wrote yesterday, plus persistence, interrupts, streaming, branching (Week 3) |
| 6 | **Observability hooks** | Callbacks threaded through every step so tracing works (Day 25) |

The single most valuable one is **#1**, and it's the one people notice least.

### Why `Runnable` is the actual product

Every LangChain component — models, prompts, parsers, retrievers, whole chains, whole graphs —
implements the same interface:

```
                     ┌──────────────────────────────┐
                     │        Runnable              │
                     ├──────────────────────────────┤
                     │  .invoke(input)   → output   │
                     │  .stream(input)   → chunks   │
                     │  .batch(inputs)   → outputs  │
                     │  .pipe(next)      → Runnable │
                     └──────────────────────────────┘
                                  ▲
      ┌──────────┬─────────────┬──┴───────┬─────────────┬──────────────┐
   ChatModel   Prompt      Parser     Retriever    RunnableLambda   Your graph
```

Because a *chain* is also a `Runnable`, you can nest chains inside chains inside graphs — and
`.stream()` works end-to-end without you writing a single line of stream plumbing. That's
Day 07, and it's the highest-leverage idea in the framework.

### When NOT to use LangChain

Be able to say this in an interview. It signals judgement.

**Skip the framework when:**

1. **One prompt, one response, one provider.** A `fetch` call is clearer and has no dependencies.
2. **Latency is critical and you're at the edge.** Framework overhead is small but the bundle isn't.
3. **You need exotic provider features** the abstraction doesn't expose yet. You'll fight it.
4. **Your team doesn't know it.** A 200-line hand-rolled pipeline your team understands beats
   a 20-line chain nobody can debug at 3 a.m.
5. **You're building a product where the orchestration IS the product.** At some point you want
   full control of the loop.

**Use it when:**

1. You have **multiple steps** — retrieve, then prompt, then parse, then route.
2. You need **swappable providers** — model choice is a config value, not a rewrite.
3. You're doing **RAG**. The loader/splitter/embedding/store/retriever plumbing is genuinely a lot.
4. You need **agents/loops/persistence/human-in-the-loop** → LangGraph. Rebuilding checkpointing
   and interrupts correctly is weeks of work.
5. You need **observability**. Tracing every step for free is worth the dependency alone.

> 🎯 **The framing that wins interviews:** *"LangChain's value isn't that it calls the model.
> It's that every step gets the same interface, so composition, streaming, retries and tracing
> work the same way everywhere. If I only have one step, there's nothing to compose, so I skip
> it."*

### The criticism you should know about

LangChain has a reputation in some circles for being over-abstracted. That criticism is mostly
aimed at **the 0.x-era high-level chains** (`LLMChain`, `ConversationalRetrievalChain`,
`initialize_agent`) — opaque wrappers that were hard to debug and hard to customise.

LangChain 1.x is a direct response: LCEL makes composition explicit, LangGraph makes control
flow explicit, and the legacy chains are deprecated. Knowing this history — and that the fix
was *less* magic, not more — is a strong signal you've followed the ecosystem rather than read
one tutorial.

---

## 7. Common mistakes

### ❌ 1. Choosing from the leaderboard

"Model X is number one, so we use Model X." The leaderboard measures someone else's task,
possibly with contaminated questions. ✅ Use benchmarks to build a shortlist, then decide with
your own eval (§3.10).

### ❌ 2. Mixing up per-1K and per-1M prices

```js
const wrong = (1_200 * 0.60 + 300 * 1.80) / 1_000;       // $1.26 per request
const right = (1_200 * 0.60 + 300 * 1.80) / 1_000_000;   // $0.00126 per request
```
✅ Check the unit on the pricing page. Dividing a per-million price by a thousand made the
estimate **1,000 times** too high in Exercise 2. The opposite slip makes it 1,000 times too low.

### ❌ 3. Counting only input tokens

For a short question with a long answer (200 in, 800 out), input alone came to $0.000120. The
real cost was $0.001560 — **13 times** more. ✅ Always count output, and for reasoning models
count the thinking tokens too.

### ❌ 4. Forgetting that chat history grows

```python
naive_in = TURNS * (SYSTEM + USER)                       # 2,500 tokens
real_in = sum(SYSTEM + t * USER + (t - 1) * ANSWER       # 11,500 tokens
              for t in range(1, TURNS + 1))
```
✅ Every turn re-sends the whole conversation (Day 01). Estimate cost per **conversation**, not
per message. Trimming history (Day 14) is a cost control.

### ❌ 5. Testing on one example

With one test case, both pretend models scored **1/1** — a "tie" between a model that is right
5 times out of 5 and one that is right 3 times. ✅ Start with at least 5 cases, and grow
towards 50 before launch.

### ❌ 6. Grading the format instead of the meaning

```js
if (reply.content === c.expected) correct++;              // "Quiz." ≠ "quiz"
```
Exact matching scored the large model **4/5** and the small one **2/5**. After normalising
(trim, lowercase, drop a final full stop) they scored 5/5 and 3/5. ✅ Decide what "correct"
means, write it as code, and check that the grader is right before you trust it.

### ❌ 7. Timing one call, or averaging a cold start

One slow first call (900 ms, then 100 ms each) gave an **average of 270 ms** but a **median of
109 ms**. ✅ Run several calls, drop or report warm-up separately, and use the median.

### ❌ 8. Sending user data before reading the data policy

✅ Read the provider's training, retention and region terms first (§3.9). If they don't fit,
the model is out — however well it scores.

### ❌ 9. Using a reasoning model for a simple task

A reasoning model on a three-label classifier is slow (late first token) and expensive (billed
thinking). ✅ Start with the smallest model that passes your eval. Move up only for the cases
it fails.

### ❌ 10. Hard-wiring one provider's SDK everywhere

When every file calls `groq.chat.completions.create(...)` directly, trying another model means
editing every file. ✅ Keep model calls behind one interface — your own small wrapper, or
LangChain's (§6). Then switching is one line, and your eval can compare models freely.

---

## 8. Exercises

### Exercise 1 — What does one request really cost? ●○○○○

Use the illustrative prices for `model-small` and `model-large`. Work out the cost per request
and per 1,000 requests for two jobs: **summarise** (3,000 tokens in, 200 out) and **explain**
(200 in, 800 out). For each job, what share of the bill is input? Which price would you
negotiate hardest on for each job?

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
// ILLUSTRATIVE prices, US$ per 1M tokens — not real ones.
const PRICES = {
  "model-small": { input: 0.10, output: 0.30 },
  "model-large": { input: 0.60, output: 1.80 },
};

function breakdown(model, inputTokens, outputTokens) {
  const p = PRICES[model];
  const inCost = (inputTokens * p.input) / 1_000_000;
  const outCost = (outputTokens * p.output) / 1_000_000;
  const total = inCost + outCost;
  return `${model}: $${total.toFixed(6)} per request · $${(total * 1000).toFixed(3)} per 1,000` +
    ` · input is ${Math.round((inCost / total) * 100)}% of the bill`;
}

const JOBS = {
  summarise: { input: 3_000, output: 200 },     // long article in, short summary out
  explain: { input: 200, output: 800 },         // short question in, long answer out
};

for (const [job, t] of Object.entries(JOBS)) {
  for (const model of Object.keys(PRICES)) {
    console.log(job.padEnd(10), breakdown(model, t.input, t.output));
  }
}
```

**Python**
```python
# ILLUSTRATIVE prices, US$ per 1M tokens — not real ones.
PRICES = {
    "model-small": {"input": 0.10, "output": 0.30},
    "model-large": {"input": 0.60, "output": 1.80},
}

def breakdown(model, input_tokens, output_tokens):
    p = PRICES[model]
    in_cost = input_tokens * p["input"] / 1_000_000
    out_cost = output_tokens * p["output"] / 1_000_000
    total = in_cost + out_cost
    return (f"{model}: ${total:.6f} per request · ${total * 1000:.3f} per 1,000"
            f" · input is {in_cost / total:.0%} of the bill")

JOBS = {
    "summarise": {"input": 3_000, "output": 200},   # long article in, short summary out
    "explain": {"input": 200, "output": 800},       # short question in, long answer out
}

for job, t in JOBS.items():
    for model in PRICES:
        print(f"{job:<10}", breakdown(model, t["input"], t["output"]))
```

Expected output, identical in both languages (verified):

```
summarise  model-small: $0.000360 per request · $0.360 per 1,000 · input is 83% of the bill
summarise  model-large: $0.002160 per request · $2.160 per 1,000 · input is 83% of the bill
explain    model-small: $0.000260 per request · $0.260 per 1,000 · input is 8% of the bill
explain    model-large: $0.001560 per request · $1.560 per 1,000 · input is 8% of the bill
```

**Reading it.** Summarising is **input-heavy**: 83 % of the bill is the article you send in.
There, the input price and features such as cached input matter most. Explaining is
**output-heavy**: 92 % of the bill is the answer, so the output price matters most, and so does
a `max_tokens` cap. The same model can be the right choice for one job and the wrong one for
the other.
</details>

---

### Exercise 2 — Break it six ways ●●○○○

Predict, then run. Each break is a real way teams fool themselves when they choose a model.

1. Use a **per-million** price but divide by **1,000**.
2. Count only **input** tokens for the "explain" job (200 in, 800 out).
3. Estimate a 10-turn chat as "10 × one turn" — ignore that history is re-sent. (System prompt
   200 tokens, each user message 50, each answer 150.)
4. Grade the harness with **exact** string matching, without normalising.
5. Run the harness on **one** test case.
6. Time 5 calls when the first one is a **cold start** (900 ms, then 100 ms each), and report the
   average.

<details>
<summary>✅ Solution</summary>

| # | Symptom (verified, both languages) | Why |
|---|---|---|
| 1 | $1.260000 instead of $0.001260 — **1,000×** too high | the unit on the pricing page is per million tokens |
| 2 | $0.000120 instead of $0.001560 — **13×** too low | output is most of this job, and output is the dear side |
| 3 | 2,500 input tokens estimated, **11,500** real; cost $0.0042 vs $0.0096 | each turn re-sends all earlier turns (Day 01) |
| 4 | large **4/5**, small **2/5** (normalised: 5/5 and 3/5) | `"Quiz."` and `"Question"` are right answers in the wrong format |
| 5 | large **1/1**, small **1/1** — a false tie | one case can't separate a 100 % model from a 60 % one |
| 6 | times `[906, 109, 109, 108, 116]` → average **270**, median **109** (JS); `[904, 100, 100, 101, 100]` → 261 vs 100 (Python) | one outlier drags the average; the median ignores it |

**Repro — JavaScript**
```js
// break-it.js — six ways to fool yourself when choosing a model.
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const PRICE = { input: 0.60, output: 1.80 };              // ILLUSTRATIVE, $ per 1M tokens
const cost = (i, o) => (i * PRICE.input + o * PRICE.output) / 1_000_000;

// 1. Per-million price, divided by a thousand
const right = cost(1_200, 300);
const wrong = (1_200 * PRICE.input + 300 * PRICE.output) / 1_000;
console.log("1", { right: right.toFixed(6), wrong: wrong.toFixed(6), times: Math.round(wrong / right) });

// 2. Counting only input tokens, for a long answer
console.log("2", { inputOnly: cost(200, 0).toFixed(6), real: cost(200, 800).toFixed(6) });

// 3. Ignoring history: a 10-turn chat re-sends everything each turn (Day 01)
const SYSTEM = 200, USER = 50, ANSWER = 150, TURNS = 10;
let naiveIn = 0, realIn = 0;
for (let turn = 1; turn <= TURNS; turn++) {
  naiveIn += SYSTEM + USER;                                 // "each turn is the same size"
  realIn += SYSTEM + turn * USER + (turn - 1) * ANSWER;     // all earlier turns come along
}
console.log("3", { naiveIn, realIn, naive$: cost(naiveIn, TURNS * ANSWER).toFixed(6),
  real$: cost(realIn, TURNS * ANSWER).toFixed(6) });

// 4–6 use the harness from §4.2, cut down.
const CASES = [
  ["What is photosynthesis?", "question"], ["Test me on chapter 3", "quiz"],
  ["Who won the match last night?", "off-topic"],
  ["Can you explain mitosis again, slower?", "question"],
  ["Give me 5 questions on the French Revolution", "quiz"],
];
const LARGE = ["question", "quiz", "off-topic", "question", "Quiz."];
const SMALL = ["question", "quiz", "question", "Question", "question"];
const normalise = (s) => s.trim().toLowerCase().replace(/[.!]+$/, "");
const score = (answers, cases, grade) =>
  cases.filter(([, expected], i) => grade(answers[i]) === expected).length + "/" + cases.length;

// 4. Exact string match, no normalising
console.log("4", { large: score(LARGE, CASES, (s) => s), small: score(SMALL, CASES, (s) => s),
  largeNormalised: score(LARGE, CASES, normalise), smallNormalised: score(SMALL, CASES, normalise) });

// 5. One test case
const one = CASES.slice(0, 1);
console.log("5", { large: score(LARGE, one, normalise), small: score(SMALL, one, normalise) });

// 6. Timing that includes a cold start (the first call is slow)
let calls = 0;
async function coldModel() {
  await sleep(calls++ === 0 ? 900 : 100);
}
const times = [];
for (let i = 0; i < 5; i++) {
  const t0 = performance.now();
  await coldModel();
  times.push(performance.now() - t0);
}
const mean = times.reduce((a, b) => a + b, 0) / times.length;
const median = [...times].sort((a, b) => a - b)[2];
console.log("6", { times: times.map(Math.round), mean: Math.round(mean), median: Math.round(median) });
```

**Repro — Python**
```python
# break_it.py — six ways to fool yourself when choosing a model.
import statistics, time

PRICE = {"input": 0.60, "output": 1.80}                     # ILLUSTRATIVE, $ per 1M tokens
def cost(i, o):
    return (i * PRICE["input"] + o * PRICE["output"]) / 1_000_000

# 1. Per-million price, divided by a thousand
right = cost(1_200, 300)
wrong = (1_200 * PRICE["input"] + 300 * PRICE["output"]) / 1_000
print("1", {"right": f"{right:.6f}", "wrong": f"{wrong:.6f}", "times": round(wrong / right)})

# 2. Counting only input tokens, for a long answer
print("2", {"input_only": f"{cost(200, 0):.6f}", "real": f"{cost(200, 800):.6f}"})

# 3. Ignoring history: a 10-turn chat re-sends everything each turn (Day 01)
SYSTEM, USER, ANSWER, TURNS = 200, 50, 150, 10
naive_in = sum(SYSTEM + USER for _ in range(TURNS))
real_in = sum(SYSTEM + t * USER + (t - 1) * ANSWER for t in range(1, TURNS + 1))
print("3", {"naive_in": naive_in, "real_in": real_in,
            "naive$": f"{cost(naive_in, TURNS * ANSWER):.6f}",
            "real$": f"{cost(real_in, TURNS * ANSWER):.6f}"})

# 4–6 use the harness from §5.2, cut down.
CASES = [
    ("What is photosynthesis?", "question"), ("Test me on chapter 3", "quiz"),
    ("Who won the match last night?", "off-topic"),
    ("Can you explain mitosis again, slower?", "question"),
    ("Give me 5 questions on the French Revolution", "quiz"),
]
LARGE = ["question", "quiz", "off-topic", "question", "Quiz."]
SMALL = ["question", "quiz", "question", "Question", "question"]
def normalise(s):
    return s.strip().lower().rstrip(".!")
def score(answers, cases, grade):
    right = sum(grade(answers[i]) == expected for i, (_, expected) in enumerate(cases))
    return f"{right}/{len(cases)}"

# 4. Exact string match, no normalising
same = lambda s: s
print("4", {"large": score(LARGE, CASES, same), "small": score(SMALL, CASES, same),
            "large_normalised": score(LARGE, CASES, normalise),
            "small_normalised": score(SMALL, CASES, normalise)})

# 5. One test case
one = CASES[:1]
print("5", {"large": score(LARGE, one, normalise), "small": score(SMALL, one, normalise)})

# 6. Timing that includes a cold start (the first call is slow)
calls = 0
def cold_model():
    global calls
    time.sleep(0.9 if calls == 0 else 0.1)
    calls += 1

times = []
for _ in range(5):
    t0 = time.perf_counter()
    cold_model()
    times.append((time.perf_counter() - t0) * 1000)
print("6", {"times": [round(t) for t in times], "mean": round(statistics.mean(times)),
            "median": round(statistics.median(times))})
```

**The lesson.** None of these six is a model problem. Each is a measurement problem — a wrong
unit, a missing term, a bad grader, too little data, or a misleading statistic. A model choice
is only as good as the numbers behind it, so test the numbers too.
</details>

---

### Exercise 3 — Measure time to first token ●●●○○

Build two pretend **streaming** models. A chat model waits 150 ms before its first token, then
writes one token every 20 ms. A reasoning model "thinks" for 1,500 ms, then writes one every
10 ms. Each writes 50 tokens. Measure, for each: time to first token, tokens per second after
the first token, and total time. Which would you put behind a chat window? Which in a nightly
batch job?

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
// ttft.js — time to first token vs tokens per second, with two pretend streaming models.
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function streamingModel(name, { firstTokenMs, msPerToken, tokens }) {
  return {
    name,
    async *stream() {
      await sleep(firstTokenMs);                 // queueing + reading the prompt (+ thinking)
      for (let i = 0; i < tokens; i++) {
        if (i > 0) await sleep(msPerToken);      // one token at a time
        yield { content: "word " };
      }
    },
  };
}

async function measure(model) {
  const t0 = performance.now();
  let firstMs = null;
  let n = 0;
  for await (const _chunk of model.stream()) {
    if (firstMs === null) firstMs = performance.now() - t0;
    n++;
  }
  const totalMs = performance.now() - t0;
  const tokensPerSecond = (n - 1) / ((totalMs - firstMs) / 1000);
  return { model: model.name, ttftMs: Math.round(firstMs), tokensPerSecond: Math.round(tokensPerSecond),
           totalMs: Math.round(totalMs) };
}

const chat = streamingModel("chat-model", { firstTokenMs: 150, msPerToken: 20, tokens: 50 });
const reasoner = streamingModel("reasoning-model", { firstTokenMs: 1500, msPerToken: 10, tokens: 50 });

for (const m of [chat, reasoner]) console.log(await measure(m));
```

**Python**
```python
# ttft.py — time to first token vs tokens per second, with two pretend streaming models.
import time
from types import SimpleNamespace


class StreamingModel:
    def __init__(self, name, first_token_ms, ms_per_token, tokens):
        self.name, self.first, self.per, self.tokens = name, first_token_ms, ms_per_token, tokens

    def stream(self):
        time.sleep(self.first / 1000)            # queueing + reading the prompt (+ thinking)
        for i in range(self.tokens):
            if i > 0:
                time.sleep(self.per / 1000)      # one token at a time
            yield SimpleNamespace(content="word ")


def measure(model):
    t0 = time.perf_counter()
    first_ms, n = None, 0
    for _chunk in model.stream():
        if first_ms is None:
            first_ms = (time.perf_counter() - t0) * 1000
        n += 1
    total_ms = (time.perf_counter() - t0) * 1000
    tokens_per_second = (n - 1) / ((total_ms - first_ms) / 1000)
    return {"model": model.name, "ttft_ms": round(first_ms),
            "tokens_per_second": round(tokens_per_second), "total_ms": round(total_ms)}


chat = StreamingModel("chat-model", first_token_ms=150, ms_per_token=20, tokens=50)
reasoner = StreamingModel("reasoning-model", first_token_ms=1500, ms_per_token=10, tokens=50)

for m in (chat, reasoner):
    print(measure(m))
```

Measured on this Windows machine (Node 24.15, Python 3.14.4; varies per run):

```
JS      chat-model       ttft 154 ms   32 tokens/s   total 1687 ms
        reasoning-model  ttft 1508 ms  65 tokens/s   total 2266 ms
Python  chat-model       ttft 151 ms   48 tokens/s   total 1172 ms
        reasoning-model  ttft 1500 ms  88 tokens/s   total 2056 ms
```

**Reading it.** The reasoning model's first token arrived about **ten times later**, even
though it then wrote about twice as fast. In a chat window, users feel the 1.5 s of silence,
so the chat model wins. In a batch job nobody watches the first token. There, total time and
cost decide, and quality on hard cases may justify the reasoning model.

**A second lesson, for free.** We asked for 50 tokens per second (one every 20 ms). JavaScript
measured 32 and Python 48–50, because each small timer wait on this machine took a little
longer than requested. Real systems have the same kind of hidden overhead. **Measure, don't
assume** — the published speed is not the speed you get.
</details>

---

### Exercise 4 — Let a rule pick the model ●●●○○

Extend the harness. Add a third pretend model, `model-medium` (200 ms, gets 4 of 5 right), and
an illustrative price for it. Write the decision rule **before** you run anything: accuracy at
least 80 %, median latency at most 500 ms, then the cheapest wins. Let the code apply the rule
and print the winner.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
// pick.js — let a written rule choose the model, not your mood.
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const PRICES = {                       // ILLUSTRATIVE, US$ per 1M tokens
  "model-small":  { input: 0.10, output: 0.30 },
  "model-medium": { input: 0.25, output: 0.75 },
  "model-large":  { input: 0.60, output: 1.80 },
};
const cost = (m, i, o) => (i * PRICES[m].input + o * PRICES[m].output) / 1_000_000;

const CASES = [
  ["What is photosynthesis?", "question"], ["Test me on chapter 3", "quiz"],
  ["Who won the match last night?", "off-topic"],
  ["Can you explain mitosis again, slower?", "question"],
  ["Give me 5 questions on the French Revolution", "quiz"],
];
const scripted = (name, delayMs, labels) => ({
  name,
  async invoke(prompt) {
    await sleep(delayMs);
    return { content: labels[CASES.findIndex(([input]) => input === prompt)] };
  },
});
const MODELS = [
  scripted("model-small", 80, ["question", "quiz", "question", "Question", "question"]),
  scripted("model-medium", 200, ["question", "quiz", "off-topic", "question", "question"]),
  scripted("model-large", 400, ["question", "quiz", "off-topic", "question", "Quiz."]),
];

const normalise = (s) => s.trim().toLowerCase().replace(/[.!]+$/, "");

async function evaluate(model) {
  let correct = 0;
  const times = [];
  for (const [input, expected] of CASES) {
    const t0 = performance.now();
    const reply = await model.invoke(input);
    times.push(performance.now() - t0);
    if (normalise(reply.content) === expected) correct++;
  }
  times.sort((a, b) => a - b);
  return {
    model: model.name,
    accuracy: correct / CASES.length,
    medianMs: Math.round(times[Math.floor(times.length / 2)]),
    dollarsPerRequest: cost(model.name, 1_200, 300),
  };
}

// The rule, written down BEFORE looking at the results.
const RULE = { minAccuracy: 0.8, maxMedianMs: 500 };

const results = [];
for (const m of MODELS) results.push(await evaluate(m));
for (const r of results) console.log(r);

const passing = results.filter((r) => r.accuracy >= RULE.minAccuracy && r.medianMs <= RULE.maxMedianMs);
const winner = passing.sort((a, b) => a.dollarsPerRequest - b.dollarsPerRequest)[0];
console.log("passing:", passing.map((r) => r.model), "→ pick:", winner?.model ?? "none — relax the rule or find another model");
```

**Python**
```python
# pick.py — let a written rule choose the model, not your mood.
import statistics, time
from types import SimpleNamespace

PRICES = {                             # ILLUSTRATIVE, US$ per 1M tokens
    "model-small":  {"input": 0.10, "output": 0.30},
    "model-medium": {"input": 0.25, "output": 0.75},
    "model-large":  {"input": 0.60, "output": 1.80},
}
def cost(m, i, o):
    return (i * PRICES[m]["input"] + o * PRICES[m]["output"]) / 1_000_000

CASES = [
    ("What is photosynthesis?", "question"), ("Test me on chapter 3", "quiz"),
    ("Who won the match last night?", "off-topic"),
    ("Can you explain mitosis again, slower?", "question"),
    ("Give me 5 questions on the French Revolution", "quiz"),
]

class Scripted:
    def __init__(self, name, delay, labels):
        self.name, self.delay, self.labels = name, delay, labels
    def invoke(self, prompt):
        time.sleep(self.delay)
        index = [inp for inp, _ in CASES].index(prompt)
        return SimpleNamespace(content=self.labels[index])

MODELS = [
    Scripted("model-small", 0.080, ["question", "quiz", "question", "Question", "question"]),
    Scripted("model-medium", 0.200, ["question", "quiz", "off-topic", "question", "question"]),
    Scripted("model-large", 0.400, ["question", "quiz", "off-topic", "question", "Quiz."]),
]

def normalise(s):
    return s.strip().lower().rstrip(".!")

def evaluate(model):
    correct, times = 0, []
    for inp, expected in CASES:
        t0 = time.perf_counter()
        reply = model.invoke(inp)
        times.append((time.perf_counter() - t0) * 1000)
        correct += normalise(reply.content) == expected
    return {"model": model.name, "accuracy": correct / len(CASES),
            "median_ms": round(statistics.median(times)),
            "dollars_per_request": cost(model.name, 1_200, 300)}

# The rule, written down BEFORE looking at the results.
RULE = {"min_accuracy": 0.8, "max_median_ms": 500}

results = [evaluate(m) for m in MODELS]
for r in results:
    print(r)

passing = [r for r in results
           if r["accuracy"] >= RULE["min_accuracy"] and r["median_ms"] <= RULE["max_median_ms"]]
winner = min(passing, key=lambda r: r["dollars_per_request"], default=None)
print("passing:", [r["model"] for r in passing], "→ pick:",
      winner["model"] if winner else "none — relax the rule or find another model")
```

Expected output (verified; latencies vary a little):

```
{'model': 'model-small', 'accuracy': 0.6, 'median_ms': 80, 'dollars_per_request': 0.00021}
{'model': 'model-medium', 'accuracy': 0.8, 'median_ms': 200, 'dollars_per_request': 0.000525}
{'model': 'model-large', 'accuracy': 1.0, 'median_ms': 400, 'dollars_per_request': 0.00126}
passing: ['model-medium', 'model-large'] → pick: model-medium
```

(JavaScript prints the same values, one object per model, and
`passing: [ 'model-medium', 'model-large' ] → pick: model-medium`.)

**Why this design.** Neither the best model nor the cheapest one won. The small model is
cheapest but fails the quality bar. The large one passes but costs more than twice as much as
the medium one. A written rule makes that trade-off visible and repeatable. When prices or
models change, you re-run the script instead of re-arguing in a meeting. If you would rather
pay for the large model's extra accuracy, change the rule — openly.
</details>

---

### Exercise 5 — Write the decision doc ●●●●○

You're the tech lead. Write a one-page decision doc (in markdown) for this scenario:

> *We're adding an AI feature to our Next.js e-commerce app: a "find products by describing
> what you want" search. It needs to search our 40,000-product catalogue, handle follow-up
> questions ("cheaper ones", "in blue"), and stream results. Should we use LangChain?*

Cover: the requirements, the two options, what each costs, your recommendation, and what would
change your mind. Then compare with the answer below.

<details>
<summary>✅ Sample answer</summary>

```markdown
# Decision: LangChain for conversational product search

## Requirements
1. Semantic search over 40k products (not keyword — "something warm for winter hiking")
2. Multi-turn refinement, so conversation state must persist
3. Streaming results to a Next.js UI
4. Must not degrade if one provider has an outage
5. Team of 3, none with prior LLM production experience

## Option A — raw SDK + our own glue
We'd write: an embedding pipeline for 40k products, a vector-store client, a retriever with
metadata filters (price, colour, stock), conversation history management with trimming,
a streaming adapter for Next.js route handlers, retry/fallback logic, and tracing.

Estimate: ~3 weeks to a working v1, and every one of those components is a thing we'd own,
debug, and maintain forever.

## Option B — LangChain + LangGraph
- Embeddings + vector store + retriever: existing integrations (~2 days)
- Conversation state + follow-ups: LangGraph checkpointer, thread per user (~2 days)
- Streaming: `.stream()` works end-to-end through the whole graph (~half a day)
- Fallbacks: `.withFallbacks([gemini])` (~1 hour)
- Tracing: LangSmith, one env var

Estimate: ~1 week to v1.

Costs: a dependency with its own release cadence and breaking changes; an abstraction the team
must learn; some provider features are behind the abstraction.

## Recommendation: **Option B**

The decisive factor is not "it's less code" — it's that this feature is *four* of the five
things LangChain is actually good at (retrieval plumbing, multi-step composition, streaming
through composition, persistent conversational state). With a team that hasn't shipped LLM
features before, hand-rolling those means learning the same lessons the framework already
encodes, on a deadline.

Specifically we'll use:
- LangChain for the retrieval chain and model abstraction
- LangGraph for conversation state (checkpointer keyed by session ID)
- Not using: agents. Search doesn't need tool-choosing autonomy; a fixed retrieve → rerank →
  answer chain is more predictable and cheaper.

## What would change my mind
- **If it were one prompt with no retrieval** → skip the framework entirely, it'd be ~40 lines.
- **If we needed a provider feature the abstraction doesn't expose** (e.g. a specific reranking
  API) → drop to the SDK for that one step; LangChain composes fine with plain functions.
- **If p99 latency budget were under 200ms** → re-evaluate; measure framework overhead first.
- **If the team already had a working in-house LLM platform** → use that; consistency beats
  best-of-breed.

## Risks & mitigations
- *Breaking changes on upgrade* → pin exact versions, upgrade deliberately with the eval suite green.
- *Debugging opaque behaviour* → LangSmith tracing from day one, not after the first incident.
- *Over-abstraction creep* → rule: if a chain needs more than 3 custom `RunnableLambda`s,
  it should be a LangGraph graph or plain code instead.
```

**What makes this a good answer in an interview:** it names *which specific capabilities*
justify the dependency. It openly declines a capability (agents) that would be
over-engineering. And it states testable conditions that would reverse the decision.
"LangChain is good/bad" is not an engineering opinion. "LangChain earns its place when you have
≥3 composed steps and swappable providers" is.
</details>

---

## 9. Interview questions

### Basic

<details>
<summary><b>Q: What is the difference between a closed model and an open-weight model?</b></summary>

A closed model is only available through its maker's API; you never see the weights. An
open-weight model's weights can be downloaded. You can run it on your own hardware, fine-tune
it or quantise it — or call it through a host such as Groq. The trade-off: closed models are
easy to start with and often strongest, but your data goes to the provider and you pay per
token. Open-weight models give you control and privacy, but you run (and pay for) the hardware.
"Open-weight" is not "open source": the training data is usually not released, and the licence
may add conditions.
</details>

<details>
<summary><b>Q: How do you estimate what an LLM feature will cost?</b></summary>

Count tokens for a typical request — input and output separately — and multiply by the
per-million prices: `in × in_price / 1M + out × out_price / 1M`. Then multiply by the expected
volume. Three adjustments catch most surprises: chat history makes input grow every turn,
reasoning models add hidden output tokens, and retries are billed again. Output is usually
priced higher because each output token needs its own pass through the model, while input is
read in one parallel pass.
</details>

<details>
<summary><b>Q: What is time to first token, and when does it matter more than total time?</b></summary>

TTFT is the delay between sending a request and receiving the first token of the answer. It
includes queueing, reading the prompt, and any hidden "thinking". It matters most when a person
is watching: chat windows and voice assistants feel slow if nothing appears. For background
batch jobs, total time (driven by tokens per second) and cost matter more. Reasoning models
usually have a much higher TTFT, because the thinking happens before the first visible token.
</details>

### Intermediate

<details>
<summary><b>Q: Why shouldn't you choose a model from a leaderboard?</b></summary>

Because a benchmark measures a public task, not yours. Scores can be inflated by
contamination — test questions leaking into training data — and they depend on prompts and
settings that differ between sources. At the top, many models score so close that the
differences are noise. Use benchmarks to build a shortlist, then decide with your own eval:
real inputs, expected answers, and a grading rule written before you look at the results.
</details>

<details>
<summary><b>Q: When would you choose a reasoning model, and what does it cost you?</b></summary>

When the task needs several dependent steps — maths, code, planning — and a cheaper chat model
fails your eval on those cases. You pay in three ways: a much later first token, more output
tokens (the thinking is usually billed as output), and therefore a higher bill per request. A
common pattern is routing: a small model for easy requests, and the reasoning model only for
the hard ones.
</details>

<details>
<summary><b>Q: What does the `Runnable` interface give you that plain functions don't?</b></summary>

A uniform contract — `invoke`, `stream`, `batch`, plus config (callbacks, tags, concurrency) —
implemented by every component. Because a composed chain is itself a `Runnable`, composition is
closed under the interface: you can nest chains in chains, and `.stream()` propagates through
the whole pipeline without custom plumbing. It also means retries, fallbacks, and tracing can
be added as generic modifiers rather than reimplemented per component.
</details>

### Advanced

<details>
<summary><b>Q: Walk me through how you would choose a model for a new feature.</b></summary>

1. **Define the task** and collect real examples with expected answers — five to start, fifty
   before launch.
2. **Apply hard rules first:** data location and retention, licence, modalities, context size.
3. **Shortlist** two or three models, mixing sizes, possibly one open-weight.
4. **Write the decision rule before running:** for example, accuracy ≥ 80 %, median latency
   ≤ 500 ms, then cheapest wins.
5. **Run the eval**, measuring accuracy, median latency (and TTFT if streaming) and tokens.
6. **Convert tokens into cost** at expected volume, including history growth and retries.
7. **Pick**, and add a fallback from a different provider.
8. **Re-run the eval** on every model, price or prompt change.

The signal an interviewer looks for: you trust measurements on your own cases over reputation,
and you wrote the rule before you saw the results.
</details>

<details>
<summary><b>Q: Why use LangChain instead of calling the provider SDK directly?</b></summary>

For a single call, don't — the SDK is clearer with fewer dependencies. LangChain earns its
place when you have **composition**. That means multiple steps whose interfaces must line up,
and streaming that must flow through all of them. It also means retries, fallbacks and tracing
applied the same way at every step.

Concretely it gives you six things:

1. the `Runnable` interface, so composition, streaming and batching work uniformly;
2. provider abstraction, so model choice is config, not a rewrite;
3. structured output (schema → JSON Schema → tool call → validate → retry);
4. the entire retrieval stack;
5. LangGraph's agent runtime with persistence and interrupts;
6. observability hooks.

The honest counterpoint: it's a dependency with its own upgrade cost, and its 0.x-era
high-level chains earned a reputation for opacity. LangChain 1.x's answer was to make
composition (LCEL) and control flow (LangGraph) explicit rather than hidden.
</details>

<details>
<summary><b>Q: When would you deliberately choose NOT to use a framework?</b></summary>

- **Single-step features.** One prompt, one response. Nothing to compose.
- **Extreme latency/bundle constraints**, e.g. edge functions where every KB counts.
- **Provider features not yet exposed** by the abstraction — you'd spend more time fighting it
  than the abstraction saves.
- **Team capability.** Code your on-call engineer can debug beats code that's shorter.
- **Orchestration is your product.** If the control loop is your differentiator, own it.

A pragmatic middle path: use LangChain for the pieces where it's strongest (retrieval,
structured output, provider abstraction) and plain functions elsewhere. Because plain functions
compose into chains via `RunnableLambda`, this isn't all-or-nothing — which is itself a good
argument for the `Runnable` design.
</details>

<details>
<summary><b>Q: A teammate says "LangChain is bloated, we should write it ourselves." How do you respond?</b></summary>

Agree with the part that's true, then make it concrete:

1. **Separate the criticism from the target.** The bloat complaint is mostly about 0.x
   high-level chains. 1.x's LCEL and LangGraph are explicit, inspectable composition.
2. **List the specific capabilities we need** and ask what each costs to build and maintain:
   embedding batching, vector-store adapters, retrievers with metadata filters, checkpointing,
   interrupt/resume, stream propagation, tracing. Usually 2–3 of those alone justify it.
3. **Ask what "ourselves" means at month six** — a homegrown framework is still a framework,
   just one with no docs, no community, and one maintainer who might leave.
4. **Propose a decision rule instead of a preference**: use the framework where we need ≥3
   composed steps or swappable providers; drop to the SDK for single-step calls. Both can
   coexist in one codebase.
5. **Reduce the risk**: pin versions, keep an eval suite green across upgrades, and keep the
   provider-specific escape hatch open.

The meta-point: "framework vs no framework" is rarely the real question. "Which specific
capabilities do we need, and what's the cheapest credible way to get them?" is.
</details>

---

## 10. Recap

- ✅ Choose a model with a funnel: hard rules → shortlist → **your own eval** → decide by a written rule
- ✅ Closed models are API-only; open-weight models can be self-hosted — "open-weight" isn't "open source"
- ✅ More parameters usually means better quality, but slower and dearer; memory ≈ parameters × bytes each
- ✅ The context window holds input **and** output; filling it costs money and time
- ✅ Reasoning models think before answering: later first token, billed thinking, better on hard multi-step tasks
- ✅ Cost = in × in-price / 1M + out × out-price / 1M; output is usually dearer (one pass per token)
- ✅ History growth, hidden thinking tokens and retries make real bills bigger than first guesses
- ✅ Latency = time to first token + output ÷ tokens per second; report the **median**
- ✅ Benchmarks build a shortlist; contamination and different settings make them a poor final answer
- ✅ Read the licence and the data policy before sending real user data
- ✅ Model names change — Groq's Llama 3.3 70B left the plan we use, so this course moved to GPT-OSS 120B (§3.11)
- ✅ LangChain's real product is the `Runnable` interface — composition, streaming, retries and tracing that work uniformly
- ✅ Skip the framework for single-step features; use it when you have composition, retrieval, or agent loops

```
   pick a model:   rules → shortlist → eval on YOUR cases → cost + latency → written rule → winner + fallback
   switch cheaply: one interface for every model  →  that is what LangChain is for
```

### Tomorrow

**[Day 04 — LangChain models](day-04-langchain-models.md)**: your first real LangChain code.
Today's harness needed one interface for every model; tomorrow you get it. You meet `ChatGroq`
and `initChatModel`, with every constructor parameter explained. You use `invoke` / `stream` /
`batch`, the message types (System / Human / AI / Tool) and token usage. You finish with your
first multi-turn chatbot with proper history handling.

### Quick self-check

1. A model tops a public leaderboard. Why is that not enough reason to use it for your app?
2. A 10-turn chat costs far more than "10 × the cost of the first turn". Why?
3. Name two situations where you'd deliberately not use LangChain.

<details>
<summary>Answers</summary>

1. The benchmark measures a different task, its questions may have leaked into training data,
   and scores depend on settings. Only an eval on your own cases, graded by a rule written in
   advance, shows how the model does on your job.
2. Models are stateless, so every turn re-sends the whole conversation. Input tokens grow each
   turn: in our example, 11,500 instead of 2,500.
3. Any two of these:
   - single-step features, where there's nothing to compose;
   - extreme latency or bundle-size limits;
   - provider features the abstraction doesn't expose;
   - a team that can't debug it;
   - the orchestration loop is your product.
</details>

---

<div align="center">

**[← Day 02 — Prompt engineering](day-02-prompt-engineering-and-raw-apis.md)** · **[Week 1 index](README.md)** · **[Day 04 — LangChain models →](day-04-langchain-models.md)**

</div>
