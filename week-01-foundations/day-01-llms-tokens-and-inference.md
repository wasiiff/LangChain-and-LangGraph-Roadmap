# Day 01 — What an LLM Actually Is: Tokens, Context & Inference

> ⏱ **Time:** ~2 hours · 🎯 **Prereqs:** [SETUP.md](../SETUP.md) done (new to programming? start with [Week 0](../week-00-start-here/README.md)) · 🧩 **Difficulty:** ●○○○○

**Today you learn:** LLMs surprise new developers. They forget earlier messages, invent facts,
and answer the same question differently each time. Today you follow one message from your
keyboard to the model's answer, so you can predict those problems instead of being surprised by
them. You'll count tokens, budget a context window, and change the temperature to watch the
answers change. No LangChain today — you can't use a tool well if you don't know what it wraps.

> 📖 **Words you'll meet today**
>
> - **LLM (large language model)** — a program trained on huge amounts of text to predict the
>   next piece of text.
> - **Token** — a small chunk of text, often part of a word, that the model reads and writes.
> - **Context window** — the most tokens the model can handle in one call, input and output
>   together.
> - **Inference** — running a finished model to get an answer. Every API call is inference.
> - **Sampling** — choosing the next token from the model's list of likely options.
> - **Temperature** — a setting that makes sampling more predictable (low) or more varied (high).
> - **Hallucination** — a fluent, confident answer that is not true.
> - **Attention** — the step inside the model where each token decides which other tokens
>   matter to it.

---

## 1. The problem

Imagine you hire an assistant with a very unusual condition.

- She has read most of the internet and remembers the *patterns* in it, but not the facts as facts.
- She has **no memory between conversations**. Every time you talk to her, she starts blank.
- She can only hold a fixed amount of paper on her desk at once. Give her more and the oldest pages fall off.
- When you ask her something, she doesn't "look up" an answer. She writes the answer **one word at a time**, each time picking the word that feels most likely to come next.
- She will never say "I don't know" unless you tell her she's allowed to.

That's an LLM. Every strange behaviour you've heard about comes directly from those five
properties. That includes hallucinations (confident, invented answers), forgetting the start of
a long chat, and giving different answers to the same question.

**Concrete pain this causes:**

> A junior developer builds a customer support bot. It works well in testing. In production,
> customers complain it "forgets what they said two messages ago" and "makes up refund
> policies." The developer thinks the model is broken. It isn't. He never sent the chat history
> (property 2), and he never gave it the real policy document (property 1).

Today's goal: make those five properties so concrete that you would predict that bug before you
release the bot.

---

## 2. Mental model

```
        ┌──────────────────────────────────────────────────────────┐
        │                    ONE API CALL                          │
        └──────────────────────────────────────────────────────────┘

   "Explain gravity"
          │
          ▼
    ┌───────────┐     text  →  numbers
    │ TOKENIZER │     "Explain gravity"  →  [849, 3157, 24128]
    └───────────┘
          │
          ▼
    ┌───────────┐     a very large pile of matrix multiplications
    │    LLM    │     (billions of learned parameters)
    └───────────┘
          │
          ▼
    ┌────────────────────────┐    a score for EVERY token in the vocabulary
    │ PROBABILITY DISTRIBUTION│   " Gravity" 31%  " The"  12%  " Sure" 9% ...
    └────────────────────────┘
          │
          ▼
    ┌───────────┐     pick ONE token   ← temperature / top-p live HERE
    │ SAMPLING  │
    └───────────┘
          │
          ▼
      " Gravity"  ──────┐
                        │  append to the input and run the WHOLE thing again
          ┌─────────────┘
          ▼
    [849, 3157, 24128, 47324] → LLM → distribution → sample → " is"
          ▼
    ... repeat until the model emits a special "stop" token or hits max_tokens
```

**The single most important idea on this page:** the model does not generate a *response*.
It generates **one token**, then gets fed its own output and generates one more. Each step is a
*forward pass* — one full run of the network over the input. A 500-word answer is about 600
forward passes. That's why:

- streaming is possible (tokens exist one at a time anyway),
- output tokens cost more than input tokens (each one is a full pass),
- and long outputs are slow but long inputs are fast.

---

## 3. First principles

### 3.1 Tokens — the atoms

> 💬 **In plain words:** the model reads and writes text in small chunks called tokens. You pay
> per token, and the same idea can cost more tokens in some languages than others.

Models don't see letters and they don't see words. They see **tokens**: chunks of characters
that appear often enough in text to be worth their own entry. The *tokenizer* is the program
that splits text into tokens and turns each one into a number (its ID). Roughly:

```
"The cat sat on the mat"     →  ["The", " cat", " sat", " on", " the", " mat"]   6 tokens
"unbelievable"               →  ["un", "bel", "iev", "able"]                     4 tokens
"antidisestablishmentarian"  →  ["ant", "idis", "establish", "ment", "arian"]    5 tokens
"🦄"                          →  ["\xf0\x9f", "\xa6", "\x84"]                     3 tokens
"def calculate_total(x):"    →  ["def", " calculate", "_total", "(", "x", "):"]  6 tokens
```

Notice the leading spaces. `" cat"` and `"cat"` are **different tokens**. This is why a
trailing space in your prompt can subtly change output quality.

**Rules of thumb (English):**

| | |
|---|---|
| 1 token | ≈ 4 characters |
| 1 token | ≈ 0.75 words |
| 100 tokens | ≈ 75 words ≈ 1 short paragraph |
| 1,000 tokens | ≈ 750 words ≈ 1.5 pages |

**Other languages are more expensive.** The same sentence in Hindi, Arabic, Thai or Chinese
can cost 2–4 times as many tokens as English. That's because the tokenizer's vocabulary (its
list of known tokens) was built mostly from English text. If you're building for a non-English
market, your costs will not match the estimates in English-focused blog posts.

> 🧠 **Analogy.** Tokens are LEGO bricks. Common words like `" the"` got their own custom
> moulded brick because they show up constantly. Rare words get built from smaller generic
> bricks. Your name is probably 2–4 bricks.

### 3.2 The context window — the desk

> 💬 **In plain words:** there is a fixed limit on how much text one call can hold, question
> and answer together. Sending more text costs more, and it doesn't always give better answers.

The **context window** is the maximum number of tokens the model can look at in a single call.
The key point: it covers **input + output together**.

```
┌───────────────── context window: 128,000 tokens ──────────────────┐
│                                                                    │
│  system prompt   chat history      retrieved docs      your Q      │  ← INPUT
│  ▓▓▓             ▓▓▓▓▓▓▓▓▓▓▓▓      ▓▓▓▓▓▓▓▓▓▓▓▓▓▓      ▓▓          │
│  400 tok         12,000 tok        40,000 tok          80 tok      │
│                                                                    │
│  ░░░░░░░░░░░░░░░░ room left for the answer: ~75,000 ░░░░░░░░░░░░  │  ← OUTPUT
└────────────────────────────────────────────────────────────────────┘
```

Typical sizes today: 8K (small local models), 128K (most hosted models), 200K–1M (frontier models).

**Three things people get wrong:**

1. **Bigger context does not mean better answers.** Models show a *"lost in the middle"*
   effect. They use information at the very start and very end of a long context reliably.
   Information buried in the middle often gets ignored. This is a big reason RAG (Week 2) beats
   "just paste the whole book in". RAG, *retrieval-augmented generation*, means finding the few
   relevant passages and sending only those.
2. **Context is not memory.** Nothing persists between calls. If a chatbot "remembers" your
   name, it's because your app re-sent the whole conversation. You'll build that on Day 04.
3. **Cost scales with context.** You pay for every input token, on **every turn**. A 50-message
   conversation re-sends all 50 messages on message 51. So a simple chatbot gets *quadratically*
   expensive: the total cost grows with the square of the number of messages.

### 3.3 The probability distribution — where "creativity" comes from

> 💬 **In plain words:** the model never picks one word directly. It gives every possible next
> token a probability, and a separate step chooses one of them.

After the forward pass, the model produces a score (a *logit*) for **every token in its
vocabulary** — typically 30,000–200,000 numbers. *Softmax* is a small formula that turns any
list of scores into probabilities that add up to 100%:

```
Prompt: "The capital of France is"

  " Paris"      ████████████████████████████████████████  92.0%
  " located"    ██                                         3.1%
  " the"        █                                          2.0%
  " a"                                                     1.2%
  " Lyon"                                                  0.4%
  ... 128,000 more tokens, each with a tiny probability
```

**The model always knows the whole distribution. Sampling is what picks one.** And *that's*
the layer your parameters control.

> 📦 **Can you see these probabilities yourself?** Some APIs return them when you ask for
> `logprobs` (log-probabilities: the same numbers on a log scale). The current Groq models
> refuse. Our request in October 2026 returned
> ``400 `logprobs` is not supported with this model``. Providers that support it include OpenAI
> (a paid API, not executed here), so check your provider's docs before you rely on it.

### 3.4 The sampling knobs

> 💬 **In plain words:** a few settings control how the next token is chosen. Low temperature
> gives safe, repeatable answers; high temperature gives varied ones. `max_tokens` only cuts the
> answer off.

#### `temperature` — flatten or sharpen the distribution

Temperature divides the logits before softmax. A low temperature makes the top token even more
likely. A high temperature spreads the probability more evenly.

```
temperature = 0.0        temperature = 0.7        temperature = 2.0
(greedy: always top)     (balanced)               (chaotic)

" Paris"  100%           " Paris"   78%           " Paris"   31%
" located"  0%           " located" 11%           " located" 14%
" the"      0%           " the"      6%           " the"     11%
" Lyon"     0%           " Lyon"     1%           " Lyon"     7%
                                                  " banana"   2%
```

| Value | Use for |
|---|---|
| `0` | Classification, extraction, routing, SQL generation, anything you'll parse |
| `0.3` | Factual Q&A, RAG answers, summarisation |
| `0.7` | General chat, explanations (most defaults) |
| `1.0+` | Brainstorming, creative writing, generating diverse variations |
| `>1.5` | Rarely useful — output degrades into word salad |

> ⚠️ **`temperature: 0` is not "deterministic"** (it does not guarantee the same output every
> time). It's *greedy* — always pick the top token. You'll still get different answers across
> runs. When two tokens are almost tied, small things can change which one is on top. Examples
> are tiny floating-point rounding differences on GPUs, how the server batches requests
> together, and provider-side model updates. Never build a test that asserts exact string
> equality on LLM output.

#### `top_p` (nucleus sampling) — truncate the tail

Instead of scaling probabilities, `top_p` **cuts off** the long tail of unlikely tokens.
`top_p = 0.9` means:

1. Sort tokens by probability.
2. Keep adding them until their probabilities sum to 90%.
3. Discard the rest, and sample from what's left.

```
top_p = 0.9

" Paris"    78%  ✅ running total 78%
" located"  11%  ✅ running total 89%
" the"       6%  ✅ running total 95% → crossed 90%, stop here
" Lyon"      1%  ❌ discarded
" banana"  0.001% ❌ discarded — can NEVER be chosen
```

This is why `top_p` is good at preventing "the model said something absurd". The absurd tokens
are removed from the pool entirely, no matter what temperature does.

> 🎯 **Practical advice:** tune **one** of temperature or top_p, not both. Most teams set
> `top_p = 1` and adjust temperature. Adjusting both makes the effect impossible to reason about.

#### `frequency_penalty` and `presence_penalty`

Both fight repetition, differently:

| Parameter | Rule | Effect |
|---|---|---|
| `frequency_penalty` | Penalty grows **with each repeat** | Stops "very very very very good" |
| `presence_penalty` | Flat penalty once a token appears **at all** | Pushes toward new topics/vocabulary |

The range is typically `-2.0` to `2.0`, and `0` is off. Useful values are small: `0.1`–`0.6`.
These are OpenAI-style parameters, and not every provider supports them (Anthropic doesn't).

#### `max_tokens` — a budget, not an instruction

`max_tokens` caps the **output**. It does not make the model write concisely. It makes the
model get **cut off mid-sentence**. If you want short answers, say so in the prompt *and* set
`max_tokens` as a safety net.

```
❌ max_tokens: 50, prompt: "Explain photosynthesis"
   → ""   (empty!)   finish_reason: "length"   47 of the 50 tokens were hidden reasoning

✅ prompt: "Explain photosynthesis in exactly two sentences."  + max_tokens: 1024
   → "Photosynthesis is the process by which green plants, algae, and certain bacteria
      capture light energy to transform carbon dioxide and water into glucose, releasing
      oxygen as a by-product. This conversion takes place in chloroplasts, ..."
      finish_reason: "stop"   199 tokens used, 125 of them hidden reasoning
```

Both lines are real runs against `openai/gpt-oss-120b` on Groq. Your wording will differ.

Check `finish_reason` / `stop_reason` in the response: `"length"` means you got truncated,
`"stop"` means the model finished naturally.

> ⚠️ **Reasoning models spend `max_tokens` on thinking first.** This course's default model,
> `openai/gpt-oss-120b`, is a *reasoning model*. Before the answer, it writes hidden "thinking"
> tokens, and those count towards `max_tokens`. With a small limit, the thinking uses it all.
> You get an **empty** answer with `finish_reason: "length"` and no error. Even
> `max_tokens: 200` only just fitted the two-sentence answer above: 188 tokens used, 112 of them
> thinking. There are two fixes:
>
> - Raise the limit. 512–1024 is a safe start for short answers.
> - Ask for less thinking with `reasoning_effort: "low"` (`reasoningEffort` in LangChain JS).
>   In our test, "2+2" then used 16 output tokens instead of about 40–90.

### 3.5 Why hallucinations are inevitable

> 💬 **In plain words:** the model writes what *sounds* likely, not what it has checked. Giving
> it real facts in the prompt is the best fix.

Sampling picks the *statistically plausible* next token — the one that best fits the patterns
it learned. It has no truth-check step. Suppose you ask about a library that doesn't exist. In
the training data, "I don't know" is a rare continuation, and confident documentation is
common. So the model writes confident documentation.

```
"How do I use the getUserPreferences() method in Express?"

Model's internal reality:  "Express docs usually look like this →"
Model's output:            confident, well-formatted, completely invented API
```

**Fixes, in order of effectiveness:**

1. **Give it the facts** — retrieval (RAG, Week 2). By far the most effective fix.
2. **Give it tools** — let it look things up (Week 3).
3. **Give it permission to fail** — "If the context doesn't contain the answer, say 'I don't know.'"
4. **Lower temperature** — helps a little.
5. **Ask for citations** — makes hallucination visible even if it doesn't prevent it.

### 3.6 How a model is made

> 💬 **In plain words:** a model first learns to continue text, then learns to follow
> instructions, then learns which answers people prefer. After that it is frozen and served —
> your API calls never teach it anything.

The five strange properties from §1 make more sense once you know how a chat model is built. It
happens in stages. Exact recipes differ between labs and are often not published, so treat this
as the common outline, not a precise specification.

```
random parameters
      │  1. pre-training: predict the next token over a huge amount of text
      ▼
base model            continues text; doesn't "answer" anything yet
      │  2. instruction tuning: learn from examples of good answers
      ▼
instruction model     follows the chat format and roles
      │  3. preference tuning (RLHF / DPO): learn which answers people prefer
      ▼
chat model            helpful tone, refusals, "I can't help with that"
      │  4. serving: parameters frozen, loaded onto GPUs
      ▼
your API call         inference only — nothing is learned from it
```

**1. Pre-training.** The model starts as billions of random numbers, called *parameters* or
*weights*. It reads a very large collection of text (web pages, books, code) and plays one game
over and over: guess the next token. Each wrong guess nudges the parameters slightly, so the
right token becomes a little more likely next time. After enough text, the model has absorbed
grammar, style, many facts and many patterns of reasoning — but only as patterns. That is
property 1 from §1: she remembers the *patterns*, not the facts as facts.

The result is a **base model**. It continues text; it does not answer you. Give a base model a
question and it may carry on with more questions, because that is a likely continuation of a
list of questions.

**2. Instruction tuning** (also called *supervised fine-tuning*). The base model is trained
further on a much smaller, carefully chosen set of examples: an instruction, then a good
response. These examples are written or checked by people. This is where the model learns the
chat format from §6 — system, user and assistant turns — and learns that text after an
instruction should *answer* it.

**3. Preference tuning.** People compare two answers to the same prompt and pick the better one.
The model is then trained to produce more answers like the preferred ones. Two common methods:

- **RLHF** (*reinforcement learning from human feedback*) first trains a separate *reward model*
  to predict which answer people would prefer. It then adjusts the LLM to score well with it.
- **DPO** (*direct preference optimisation*) skips the reward model and learns from the pairs of
  preferred and rejected answers directly.

This stage explains a lot of "assistant" behaviour. The polite, helpful tone and the habit of
refusing some requests are largely *learned* preferences. They are not rules written in code.
Providers may also run separate safety filters around the model, but the refusal habit itself
comes from training. That is why it can be too cautious on some harmless requests, and why
cleverly worded prompts can sometimes get around it. Day 02 shows a related problem, *prompt
injection*.

**4. Serving.** The finished parameters are frozen and loaded onto GPUs. Every API call is
*inference*: the forward-pass loop from §2, running on fixed parameters. Nothing you send
changes the model during your call, which is why it has no memory (property 2). It also means
the model's knowledge stops at the end of its training data. Whether a provider later uses your
data to train *future* models is a policy question — check its terms.

> 💡 **Why this matters to you.** Prompting (Day 02) changes the *input* to a frozen model.
> Fine-tuning changes the *parameters*. RAG (Week 2) changes the input by adding facts. Most of
> this course works at the input level, because that is fast, cheap and under your control.

### 3.7 Attention, by intuition

> 💬 **In plain words:** inside the model, each token looks at the tokens before it and decides
> which ones matter most. Then it mixes in their meaning. That step is called attention.

Words get their meaning from other words. In *"The cat sat down because it was tired"*, the
token `" it"` means nothing on its own — it needs `" cat"`. In *"river bank"* and *"bank loan"*,
`" bank"` means different things. Before the model can predict a good next token, every token
needs some information from the tokens around it.

**Attention** is the step that does this. Inside the network, each token is a *vector* — a list
of numbers that stands for its meaning. Attention updates each token's vector in three steps:

1. **Score.** The token compares itself with every token before it, including itself. The
   comparison is a *dot product*: multiply two vectors number by number and add up the results.
   Vectors that point the same way give a high score.
2. **Weigh.** Softmax — the same formula from §3.3 — turns the scores into weights that add up
   to 1. A high score becomes a large share of the attention.
3. **Mix.** The token's new vector is the weighted average of the others. If `" it"` gives
   most of its weight to `" cat"`, its new vector carries a lot of "cat" meaning.

In a real model, each token's vector is turned into three learned versions first. The *query*
says "what am I looking for?", the *key* says "what do I contain?", and the *value* is "what I
pass on if chosen". Scores compare one token's query with the other tokens' keys, and the mix
uses their values. A model runs many attention steps side by side (*heads*) and stacks many
layers of them. Roughly speaking, each head can learn to look for a different kind of
relationship. You'll compute one attention step by hand in §4.6 / §5.6.

**This connects to two things you've already met:**

- **The KV-cache** (§6). In models like these, a token only looks *backwards*, so the keys and
  values of earlier tokens don't change when a new token arrives. The server stores them — that
  store is the KV-cache. Each new output token then computes only its own query, key and value,
  and compares against the stored keys instead of recomputing everything.
- **Long contexts cost more.** In the standard design every token is compared with every token
  before it. So the work grows roughly with the square of the context length, which is another
  reason "just paste in everything" is expensive.

> 💡 **Maths refresher.** Vectors, dot products and softmax are explained step by step in
> [Day 0C — Just enough maths](../week-00-start-here/day-00c-just-enough-maths.md).

---

## 4. Code — JavaScript

We're using the **raw provider SDK** (the provider's own client library), not LangChain, so you
see exactly what's happening.

```bash
npm install groq-sdk dotenv gpt-tokenizer
```

### 4.1 Your first call, with every parameter labelled

```js
// day01-basics.js
import "dotenv/config";
import Groq from "groq-sdk";

const groq = new Groq({ apiKey: process.env.GROQ_API_KEY });

const response = await groq.chat.completions.create({
  model: "openai/gpt-oss-120b",

  // The conversation. Always an ARRAY of role/content objects.
  messages: [
    { role: "system", content: "You are a concise physics tutor for 12-year-olds." },
    { role: "user", content: "Why do things fall down?" },
  ],

  temperature: 0.7,          // 0 = deterministic-ish, 2 = chaotic
  top_p: 1,                  // 1 = no truncation (tune temperature OR this, not both)
  max_tokens: 1024,          // hard cap on OUTPUT tokens — hidden reasoning counts too (§3.4)
  frequency_penalty: 0,      // >0 discourages repeating the same token
  presence_penalty: 0,       // >0 pushes toward new topics
  stop: null,                // e.g. ["\n\n"] to stop at a blank line
});

console.log(response.choices[0].message.content);

// Everything you should be logging in production:
console.log({
  finishReason: response.choices[0].finish_reason,  // "stop" | "length" | "tool_calls"
  inputTokens:  response.usage.prompt_tokens,
  outputTokens: response.usage.completion_tokens,   // includes the hidden reasoning tokens
  reasoningTokens: response.usage.completion_tokens_details?.reasoning_tokens,
  totalTokens:  response.usage.total_tokens,
});
```

Our run printed a friendly answer about gravity (your wording will differ), then:

```
{
  finishReason: 'stop',
  inputTokens: 92,
  outputTokens: 404,
  reasoningTokens: 40,
  totalTokens: 496
}
```

Two numbers deserve a second look. `inputTokens: 92` is far more than the 20 or so words you
sent; §4.3 explains the hidden extra. `reasoningTokens: 40` is the thinking you never see but
still pay for, as output.

### 4.2 Proving the model has no memory

```js
// day01-no-memory.js
import "dotenv/config";
import Groq from "groq-sdk";
const groq = new Groq({ apiKey: process.env.GROQ_API_KEY });

const ask = async (messages) => {
  const r = await groq.chat.completions.create({
    model: "openai/gpt-oss-120b",
    messages,
  });
  return r.choices[0].message.content;
};

// ❌ Two separate calls — the second knows nothing about the first
console.log(await ask([{ role: "user", content: "My name is Wasif." }]));
console.log(await ask([{ role: "user", content: "What is my name?" }]));
// → "I don’t actually know your name. If you’d like me to address you personally, …"

// ✅ Send the whole history. THIS is what "memory" means.
console.log(
  await ask([
    { role: "user",      content: "My name is Wasif." },
    { role: "assistant", content: "Nice to meet you, Wasif!" },
    { role: "user",      content: "What is my name?" },
  ])
);
// → "Your name is Wasif."
```

The `→` comments are from our run. Your wording will differ, but the pattern will not.

> 🔑 There is no memory feature anywhere in any LLM API. "Memory" is always *your* code
> deciding which past messages to re-send. LangChain and LangGraph automate that decision —
> that's most of what they do.

### 4.3 Counting tokens before you send

```js
// day01-tokens.js
import { encode, decode } from "gpt-tokenizer";

const text = "The unbelievable cat sat on the mat. 🦄";
const tokens = encode(text);

console.log("token count:", tokens.length);
console.log("token ids:  ", tokens);
console.log("pieces:     ", tokens.map((t) => JSON.stringify(decode([t]))).join(" | "));
```

Real output (`gpt-tokenizer` 4.0.0, which uses OpenAI's `o200k_base` tokenizer by default):

```
token count: 11
pieces:      "The" | " unbelievable" | " cat" | " sat" | " on" | " the" | " mat" | "." | " " | "" | "🦄"
```

`" unbelievable"` is common enough to be one token. The unicorn emoji is **three** tokens: three
pieces of raw bytes. Printed one at a time, the first two are broken halves of a character, so
they show up as a space and an empty string.

Try these and watch the count explode:

```js
["hello world",
 "नमस्ते दुनिया",                 // Hindi — same meaning, ~4x the tokens
 "def f(x): return x**2",
 "a".repeat(100),
].forEach((s) => console.log(encode(s).length, "←", s.slice(0, 30)));
```

**Your count is not the bill.** A local tokenizer counts only *your* text. The provider adds
more before the model sees it: the chat template from §6 and, for some models, built-in
instructions you never see. Compare the two numbers yourself:

```js
// day01-tokens-vs-api.js — your count vs the bill
import "dotenv/config";
import Groq from "groq-sdk";
import { encode } from "gpt-tokenizer";
const groq = new Groq({ apiKey: process.env.GROQ_API_KEY });

const r = await groq.chat.completions.create({
  model: "openai/gpt-oss-120b",
  messages: [{ role: "user", content: "Hi" }],
});

console.log("local count of 'Hi':", encode("Hi").length);
console.log("API prompt_tokens:  ", r.usage.prompt_tokens);
```

Real output:

```
local count of 'Hi': 1
API prompt_tokens:   72
```

One token of yours, 72 on the bill. The other 71 are the hidden wrapper. We can't see its text,
only its size. So use local counts to **estimate** and to compare prompts with each other. Use
`usage.prompt_tokens` from the response for what you actually pay.

### 4.4 Streaming — watching tokens arrive

```js
// day01-stream.js
import "dotenv/config";
import Groq from "groq-sdk";
const groq = new Groq({ apiKey: process.env.GROQ_API_KEY });

const stream = await groq.chat.completions.create({
  model: "openai/gpt-oss-120b",
  messages: [{ role: "user", content: "Count from 1 to 20 slowly." }],
  stream: true,                                   // ← the only change
});

for await (const chunk of stream) {               // async iterator
  process.stdout.write(chunk.choices[0]?.delta?.content ?? "");
}
console.log();
```

Streaming doesn't make generation faster. It changes what the user notices: the wait for the
**first token** instead of the wait for the last one (*time-to-first-token*). A 12-second answer
feels instant if the first word arrives in 300 ms.

### 4.5 Seeing temperature with your own eyes

```js
// day01-temperature.js
import "dotenv/config";
import Groq from "groq-sdk";
const groq = new Groq({ apiKey: process.env.GROQ_API_KEY });

for (const temperature of [0, 0.7, 1.5]) {
  console.log(`\n─── temperature ${temperature} ───`);
  for (let i = 0; i < 3; i++) {
    const r = await groq.chat.completions.create({
      model: "openai/gpt-oss-120b",
      messages: [{ role: "user", content: "Write a 6-word story about the sea." }],
      temperature,
      max_tokens: 1024,           // room for the hidden reasoning first (§3.4)
    });
    console.log(" ", r.choices[0].message.content.trim());
  }
}
```

Our run:

```
─── temperature 0 ───
  Waves whispered secrets; sailors listened eternally.
  Waves whispered secrets; sailors listened eternally.
  Waves whispered secrets; sailors listened eternally.

─── temperature 0.7 ───
  Waves whispered secrets, shore kept listening.
  Moonlit waves whispered secrets to sailors.
  Moonlit waves whispered secrets to sailors.

─── temperature 1.5 ───
  Moonlit waves whispered secrets to shore.
  Waves whispered secrets; sailors never listened.
  Waves whispered secrets; ships vanished eternally.
```

At `0` the three runs were identical. Higher temperatures gave more variety, but even at `1.5`
every story stayed sensible and on topic. This model's distribution is very *peaked* (one
option is far more likely than the rest), so temperature has less to spread. Exercise 3
measures the effect properly.

### 4.6 Attention, computed by hand

This one needs no API key and no packages. It runs one attention step from §3.7 for the token
`"it"` in the text *"the cat sat … it"*. The vectors are tiny and hand-picked so you can follow
the arithmetic. They are an illustration, not values from a real model. To keep it short, each
token's one vector plays all three roles: query, key and value.

```js
// day01-attention.js — one attention step, by hand. No packages, no API key.
// Toy 2-number vectors, hand-picked for illustration. Real models learn vectors with
// thousands of numbers, and learn separate query/key/value versions of each one.
const tokens = ["the", "cat", "sat", "it"];
const vectors = [
  [0.2, 0.1], // the
  [3.0, 0.5], // cat
  [0.5, 3.0], // sat
  [2.5, 1.0], // it   ← points roughly the same way as "cat"
];

const dot = (a, b) => a.reduce((sum, x, i) => sum + x * b[i], 0);
const softmax = (xs) => {
  const exps = xs.map((x) => Math.exp(x - Math.max(...xs)));
  const total = exps.reduce((a, b) => a + b, 0);
  return exps.map((e) => e / total);
};

const query = vectors[3]; // "it" asks: which tokens matter to me?
const scores = vectors.map((key) => dot(query, key) / Math.sqrt(query.length)); // 1. score
const weights = softmax(scores); // 2. scores → weights that sum to 1
const mixed = [0, 1].map((d) => weights.reduce((s, w, i) => s + w * vectors[i][d], 0)); // 3. mix

tokens.forEach((t, i) =>
  console.log(`${t.padEnd(4)} score ${scores[i].toFixed(2).padStart(5)}  weight ${weights[i].toFixed(2)}`)
);
console.log(`new vector for "it": [${mixed.map((x) => x.toFixed(2)).join(", ")}]`);
```

Real output (`node day01-attention.js`):

```
the  score  0.42  weight 0.00
cat  score  5.66  weight 0.60
sat  score  3.01  weight 0.04
it   score  5.13  weight 0.35
new vector for "it": [2.71, 0.78]
```

Read it from top to bottom:

- `"it"` gives **60%** of its attention to `"cat"` — even more than to itself (35%). Its new
  vector, `[2.71, 0.78]`, has moved towards `"cat"`'s `[3.0, 0.5]`.
- `"the"` gets almost nothing. Its weight shows as `0.00` but is not exactly zero. The four
  weights add up to 1; the printed ones sum to 0.99 only because of rounding.
- The division by `Math.sqrt(query.length)` is the standard *scaling* step. It stops scores
  from growing too large when vectors have thousands of numbers.
- Subtracting the largest score inside `softmax` doesn't change the result. It only stops
  `Math.exp` from overflowing on big scores.

In a real model this happens for every token, in every head, in every layer.

---

## 5. Code — Python

Same six programs, same outputs.

```bash
pip install groq python-dotenv tiktoken
```

### 5.1 Your first call, with every parameter labelled

```python
# day01_basics.py
from dotenv import load_dotenv
from groq import Groq
import os

load_dotenv()
groq = Groq(api_key=os.environ["GROQ_API_KEY"])

response = groq.chat.completions.create(
    model="openai/gpt-oss-120b",

    # The conversation. Always a LIST of role/content dicts.
    messages=[
        {"role": "system", "content": "You are a concise physics tutor for 12-year-olds."},
        {"role": "user",   "content": "Why do things fall down?"},
    ],

    temperature=0.7,          # 0 = deterministic-ish, 2 = chaotic
    top_p=1,                  # 1 = no truncation (tune temperature OR this, not both)
    max_tokens=1024,          # hard cap on OUTPUT tokens — hidden reasoning counts too (§3.4)
    frequency_penalty=0,      # >0 discourages repeating the same token
    presence_penalty=0,       # >0 pushes toward new topics
    stop=None,                # e.g. ["\n\n"] to stop at a blank line
)

print(response.choices[0].message.content)

details = response.usage.completion_tokens_details
print({
    "finish_reason": response.choices[0].finish_reason,
    "input_tokens":  response.usage.prompt_tokens,
    "output_tokens": response.usage.completion_tokens,   # includes the hidden reasoning tokens
    "reasoning_tokens": details.reasoning_tokens if details else None,
    "total_tokens":  response.usage.total_tokens,
})
```

Our run (after a shorter answer than the JS run got):

```
{'finish_reason': 'stop', 'input_tokens': 92, 'output_tokens': 248, 'reasoning_tokens': 94, 'total_tokens': 340}
```

### 5.2 Proving the model has no memory

```python
# day01_no_memory.py
from dotenv import load_dotenv
from groq import Groq
import os

load_dotenv()
groq = Groq(api_key=os.environ["GROQ_API_KEY"])

def ask(messages):
    r = groq.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=messages,
    )
    return r.choices[0].message.content

# ❌ Two separate calls — the second knows nothing about the first
print(ask([{"role": "user", "content": "My name is Wasif."}]))
print(ask([{"role": "user", "content": "What is my name?"}]))
# → "I’m sorry, but I don’t have any information about your name. …"

# ✅ Send the whole history. THIS is what "memory" means.
print(ask([
    {"role": "user",      "content": "My name is Wasif."},
    {"role": "assistant", "content": "Nice to meet you, Wasif!"},
    {"role": "user",      "content": "What is my name?"},
]))
# → "Your name is Wasif."
```

### 5.3 Counting tokens before you send

```python
# day01_tokens.py
import tiktoken

enc = tiktoken.get_encoding("cl100k_base")

text = "The unbelievable cat sat on the mat. 🦄"
tokens = enc.encode(text)

print("token count:", len(tokens))
print("token ids:  ", tokens)
print("pieces:     ", " | ".join(repr(enc.decode([t])) for t in tokens))
```

Real output (`tiktoken` 0.14.0 with `cl100k_base`, an older OpenAI tokenizer than the JS one):

```
token count: 11
token ids:   [791, 52229, 8415, 7731, 389, 279, 5634, 13, 11410, 99, 226]
pieces:      'The' | ' unbelievable' | ' cat' | ' sat' | ' on' | ' the' | ' mat' | '.' | ' �' | '�' | '�'
```

The same 11 tokens as JavaScript here, with different IDs. Python prints the broken emoji bytes
as `�`, the "unknown character" sign.

```python
for s in ["hello world",
          "नमस्ते दुनिया",              # Hindi — same meaning, ~4x the tokens
          "def f(x): return x**2",
          "a" * 100]:
    print(len(enc.encode(s)), "←", s[:30])
```

**Your count is not the bill** (see §4.3 for why):

```python
# day01_tokens_vs_api.py — your count vs the bill
from dotenv import load_dotenv
from groq import Groq
import os, tiktoken

load_dotenv()
groq = Groq(api_key=os.environ["GROQ_API_KEY"])
enc = tiktoken.get_encoding("cl100k_base")

r = groq.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[{"role": "user", "content": "Hi"}],
)

print("local count of 'Hi':", len(enc.encode("Hi")))
print("API prompt_tokens:  ", r.usage.prompt_tokens)
```

Real output — the same as JavaScript:

```
local count of 'Hi': 1
API prompt_tokens:   72
```

### 5.4 Streaming — watching tokens arrive

```python
# day01_stream.py
from dotenv import load_dotenv
from groq import Groq
import os

load_dotenv()
groq = Groq(api_key=os.environ["GROQ_API_KEY"])

stream = groq.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[{"role": "user", "content": "Count from 1 to 20 slowly."}],
    stream=True,                                  # ← the only change
)

for chunk in stream:                              # a generator
    print(chunk.choices[0].delta.content or "", end="", flush=True)
print()
```

### 5.5 Seeing temperature with your own eyes

```python
# day01_temperature.py
from dotenv import load_dotenv
from groq import Groq
import os

load_dotenv()
groq = Groq(api_key=os.environ["GROQ_API_KEY"])

for temperature in [0, 0.7, 1.5]:
    print(f"\n─── temperature {temperature} ───")
    for _ in range(3):
        r = groq.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": "Write a 6-word story about the sea."}],
            temperature=temperature,
            max_tokens=1024,          # room for the hidden reasoning first (§3.4)
        )
        print(" ", r.choices[0].message.content.strip())
```

Our Python run gave the same three identical stories at `0`, and three different ones at
`0.7` and again at `1.5`. For example: "Stormy sea swallowed the lighthouse's hope."

### 5.6 Attention, computed by hand

The same toy attention step as §4.6, in plain Python with only the standard library. Same
hand-picked vectors, same three steps: score, weigh, mix.

```python
# day01_attention.py — one attention step, by hand. No packages, no API key.
# Toy 2-number vectors, hand-picked for illustration. Real models learn vectors with
# thousands of numbers, and learn separate query/key/value versions of each one.
import math

tokens = ["the", "cat", "sat", "it"]
vectors = [
    [0.2, 0.1],  # the
    [3.0, 0.5],  # cat
    [0.5, 3.0],  # sat
    [2.5, 1.0],  # it   ← points roughly the same way as "cat"
]

def dot(a, b):
    return sum(x * y for x, y in zip(a, b))

def softmax(xs):
    exps = [math.exp(x - max(xs)) for x in xs]
    return [e / sum(exps) for e in exps]

query = vectors[3]  # "it" asks: which tokens matter to me?
scores = [dot(query, key) / math.sqrt(len(query)) for key in vectors]  # 1. score
weights = softmax(scores)  # 2. scores → weights that sum to 1
mixed = [sum(w * v[d] for w, v in zip(weights, vectors)) for d in range(2)]  # 3. mix

for t, s, w in zip(tokens, scores, weights):
    print(f"{t:<4} score {s:5.2f}  weight {w:.2f}")
print(f'new vector for "it": [{", ".join(f"{x:.2f}" for x in mixed)}]')
```

Real output (`python day01_attention.py`) — identical to the JavaScript version:

```
the  score  0.42  weight 0.00
cat  score  5.66  weight 0.60
sat  score  3.01  weight 0.04
it   score  5.13  weight 0.35
new vector for "it": [2.71, 0.78]
```

> 💡 Real code uses a library such as NumPy or PyTorch for this, and works on whole matrices at
> once. The arithmetic is the same.

### 🔁 JS ↔ Python differences you just saw

| | JavaScript | Python |
|---|---|---|
| Load env | `import "dotenv/config"` | `load_dotenv()` |
| Async | `await` everywhere (SDK is async-first) | sync by default; `AsyncGroq` for async |
| Streaming loop | `for await (const c of stream)` | `for chunk in stream:` |
| Null-safe access | `chunk.choices[0]?.delta?.content ?? ""` | `chunk.choices[0].delta.content or ""` |
| Naming | `camelCase` params in LangChain, `snake_case` in raw SDK | `snake_case` everywhere |
| Tokenizer lib | `gpt-tokenizer` | `tiktoken` |
| Reasoning tokens used | `usage.completion_tokens_details?.reasoning_tokens` | `usage.completion_tokens_details.reasoning_tokens` |
| Dot product (attention) | `a.reduce((sum, x, i) => sum + x * b[i], 0)` | `sum(x * y for x, y in zip(a, b))` |

> ⚠️ **Naming trap you'll meet all week.** The raw provider SDKs use `snake_case` in *both*
> languages (`max_tokens`), because that's what the HTTP API uses. But **LangChain JS** uses
> `camelCase` (`maxTokens`). So in JS you'll write `max_tokens` today and `maxTokens` on Day 04.
> That's not a typo — it's two different layers.

---

## 6. Under the hood

### What actually happens on the server

```
your JSON  →  HTTPS POST /v1/chat/completions
                    │
                    ▼
           ┌──────────────────────┐
           │ chat template applied│  your messages array is flattened into ONE string
           └──────────────────────┘  using the model's specific format, e.g.:
                    │
                    │   <|start_header_id|>system<|end_header_id|>
                    │   You are a concise physics tutor...<|eot_id|>
                    │   <|start_header_id|>user<|end_header_id|>
                    │   Why do things fall down?<|eot_id|>
                    │   <|start_header_id|>assistant<|end_header_id|>
                    ▼
           ┌──────────────────────┐
           │      tokenize        │
           └──────────────────────┘
                    │
                    ▼
           ┌──────────────────────┐   ← repeated once PER OUTPUT TOKEN
           │  forward pass (GPU)  │      (with a KV-cache so earlier tokens
           │  → logits            │       aren't recomputed each time)
           └──────────────────────┘
                    │
                    ▼
           ┌──────────────────────┐
           │   sampling loop      │  temperature / top_p / penalties applied here
           └──────────────────────┘
                    │
                    ▼
           detokenize → JSON response
```

The template in the diagram is Llama 3's. Each model family has its own, and GPT-OSS uses a
different one. Whatever the format, the template and any built-in instructions are billed as
input. That is where the 71 extra tokens in §4.3 come from.

Two things to remember:

1. **The `role` field is not magic.** It gets rendered into special text tokens
   (`<|start_header_id|>system<|end_header_id|>`). The "system" role is powerful because the
   model was *trained* to give text in that position a lot of weight (§3.6). It is not a
   different code path.
2. **Input and output are processed differently.** Input is read in one parallel pass. Output is
   a serial loop, one token after another — which is why providers usually charge more per
   output token (check your provider's price page for the real ratio). **The KV-cache** makes
   that loop affordable: it stores the attention keys and values of tokens already processed
   (§3.7), so each new token doesn't recompute everything before it.

### Why the same prompt costs different amounts on different providers

Every provider uses a different tokenizer. The same sentence might be 18 tokens on Llama and
21 on GPT (illustrative numbers). Never hard-code token counts across providers. Always count
with the right tokenizer. And remember the hidden wrapper: on `openai/gpt-oss-120b` via Groq, a
bare "Hi" is billed as 72 input tokens, and the same "Hi" after a short system message as 78.

---

## 7. Common mistakes

**❌ Thinking `max_tokens` limits total cost**

```js
// This can still cost a fortune — max_tokens only caps OUTPUT
await groq.chat.completions.create({
  messages: [{ role: "user", content: entireBookText }],  // 400,000 input tokens 💸
  max_tokens: 100,
});
```

✅ Count input tokens **before** sending, and truncate or retrieve instead.

---

**❌ Setting a small `max_tokens` on a reasoning model**

```js
await groq.chat.completions.create({
  model: "openai/gpt-oss-120b",
  messages: [{ role: "user", content: "Explain photosynthesis" }],
  max_tokens: 50,
});
// → content: ""   finish_reason: "length"   (47 of the 50 tokens were hidden reasoning)
```

✅ Leave room for the thinking (`max_tokens: 1024`), or lower it with `reasoning_effort: "low"`.
Always check `finish_reason` — an empty string is not an error, so nothing else will warn you.

---

**❌ Building a chatbot that re-sends unbounded history**

```js
messages.push({ role: "user", content: input });   // grows forever
await groq.chat.completions.create({ messages });   // turn 80 = 80x the cost of turn 1
```

✅ Cap it. Keep the system message + the last N turns, or summarise older ones (Day 14).

```js
const trimmed = [messages[0], ...messages.slice(-10)];
```

---

**❌ Using `temperature: 0` and asserting exact output in tests**

```python
assert response == "The answer is 42."   # will flake, guaranteed
```

✅ Assert on structure or semantics:

```python
assert "42" in response
# or parse JSON, or use an LLM-as-judge evaluator (Day 25)
```

---

**❌ Putting instructions in the user message when they belong in the system message**

```js
messages: [{ role: "user", content: "You are a helpful assistant. Also, what is 2+2?" }]
```

✅ Separate them — the system role is weighted more heavily and is harder for users to override:

```js
messages: [
  { role: "system", content: "You are a helpful assistant." },
  { role: "user",   content: "What is 2+2?" },
]
```

---

**❌ Assuming the model can count characters or do arithmetic reliably**

"Write exactly 100 words" and "what is 8,342 × 991" both fail often. The model sees tokens,
not characters, and it pattern-matches arithmetic rather than computing it.
✅ Use a tool (Day 15) for anything that needs to be *correct* rather than *plausible*.

---

**❌ Setting both `temperature: 1.5` and `top_p: 0.5`**

The interaction is unpredictable. ✅ Pick one knob.

---

## 8. Exercises

### Exercise 1 — Token detective ●○○○○

Write a script that takes an array/list of strings and prints a table of
`text | characters | tokens | chars-per-token`.

Test with: `"hello"`, a full English sentence, the same sentence in another language, a code
snippet, and a URL. Which is the most token-expensive per character, and why?

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import { encode } from "gpt-tokenizer";

const samples = [
  "hello",
  "The quick brown fox jumps over the lazy dog.",
  "El rápido zorro marrón salta sobre el perro perezoso.",
  "function add(a, b) { return a + b; }",
  "https://docs.langchain.com/oss/javascript/langchain/models",
];

console.log("chars | tokens | ratio | text");
for (const s of samples) {
  const t = encode(s).length;
  console.log(
    `${String(s.length).padStart(5)} | ${String(t).padStart(6)} | ` +
    `${(s.length / t).toFixed(2).padStart(5)} | ${s.slice(0, 40)}`
  );
}
```

**Python**
```python
import tiktoken
enc = tiktoken.get_encoding("cl100k_base")

samples = [
    "hello",
    "The quick brown fox jumps over the lazy dog.",
    "El rápido zorro marrón salta sobre el perro perezoso.",
    "function add(a, b): return a + b",
    "https://docs.langchain.com/oss/python/langchain/models",
]

print("chars | tokens | ratio | text")
for s in samples:
    t = len(enc.encode(s))
    print(f"{len(s):>5} | {t:>6} | {len(s)/t:>5.2f} | {s[:40]}")
```

**What you should notice:** plain English gets about 4 characters per token. URLs and code get
about 2–3, because punctuation and slashes break text into small pieces. Non-English text gets
the worst ratio, because its characters weren't common enough in training to earn their own
tokens.
</details>

---

### Exercise 2 — Prove the memory thing ●○○○○

Build a 3-turn conversation two ways: (a) three independent calls, (b) one call with full
history. Print both. Then add a `trimHistory(messages, n)` helper that keeps the system message
plus the last `n` messages, and show that trimming too aggressively breaks the conversation.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import "dotenv/config";
import Groq from "groq-sdk";
const groq = new Groq({ apiKey: process.env.GROQ_API_KEY });

const ask = async (messages) =>
  (await groq.chat.completions.create({ model: "openai/gpt-oss-120b", messages }))
    .choices[0].message.content;

function trimHistory(messages, n) {
  const [system, ...rest] = messages;
  return system.role === "system" ? [system, ...rest.slice(-n)] : messages.slice(-n);
}

const history = [
  { role: "system", content: "You are a helpful assistant. Keep every answer under 60 words." },
  { role: "user",   content: "I'm planning a trip to Japan." },
];
history.push({ role: "assistant", content: await ask(history) });

history.push({ role: "user", content: "I'll be there for 10 days in April." });
history.push({ role: "assistant", content: await ask(history) });

history.push({ role: "user", content: "How long did I say I'd be there, and where?" });

console.log("FULL   :", await ask(history));
console.log("TRIM(2):", await ask(trimHistory(history, 2)));
```

**Python**
```python
from dotenv import load_dotenv
from groq import Groq
import os

load_dotenv()
groq = Groq(api_key=os.environ["GROQ_API_KEY"])

def ask(messages):
    return groq.chat.completions.create(
        model="openai/gpt-oss-120b", messages=messages
    ).choices[0].message.content

def trim_history(messages, n):
    if messages and messages[0]["role"] == "system":
        return [messages[0]] + messages[1:][-n:]
    return messages[-n:]

history = [
    {"role": "system", "content": "You are a helpful assistant. Keep every answer under 60 words."},
    {"role": "user",   "content": "I'm planning a trip to Japan."},
]
history.append({"role": "assistant", "content": ask(history)})

history.append({"role": "user", "content": "I'll be there for 10 days in April."})
history.append({"role": "assistant", "content": ask(history)})

history.append({"role": "user", "content": "How long did I say I'd be there, and where?"})

print("FULL   :", ask(history))
print("TRIM(2):", ask(trim_history(history, 2)))
```

Why "under 60 words"? Without it, `openai/gpt-oss-120b` wrote a long travel plan for each turn.
By the last call the history was so big that Groq's free tier refused it. The error was
`413 Request too large for model openai/gpt-oss-120b … on tokens per minute (TPM): Limit 8000,
Requested 8774`. That is §3.2's "cost scales with context" in one error message.

Our run (JavaScript and Python gave the same pattern):

```
FULL   : You said you’ll be in Japan for **10 days** during **April**.
TRIM(2): You planned a 10‑day trip, all in Japan—starting in Tokyo, then Hakone, Kyoto, Nara, Osaka and finishing in Kobe (or back to Tokyo).
```

Look closely. `TRIM(2)` still knew "Japan" and "10 days", but only because the last assistant
reply happened to repeat them. It lost "April", and it presented the assistant's own suggested
route as *your* plan. Trimming kept some facts by luck and lost others silently. That is the
exact problem Day 14 (memory) and Day 20 (checkpointers) solve properly.
</details>

---

### Exercise 3 — The temperature grid ●●○○○

For temperatures `[0, 0.5, 1.0, 1.5]`, run the **same** prompt 5 times each and compute how
many *unique* responses you got. Plot it as a text bar chart. Then repeat with a factual prompt
("What is the capital of Japan?") and a creative one ("Invent a name for a coffee shop").

What's the difference in the shape of the two curves, and what does that tell you about
picking temperature per task?

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import "dotenv/config";
import Groq from "groq-sdk";
const groq = new Groq({ apiKey: process.env.GROQ_API_KEY });

async function uniqueness(prompt, temperature, runs = 5) {
  const outs = [];
  for (let i = 0; i < runs; i++) {
    const r = await groq.chat.completions.create({
      model: "openai/gpt-oss-120b",
      messages: [{ role: "user", content: prompt }],
      temperature,
      max_tokens: 512,
      reasoning_effort: "low",   // less hidden thinking: cheaper and faster (§3.4)
    });
    outs.push(r.choices[0].message.content.trim());
  }
  return new Set(outs).size;
}

for (const prompt of ["What is the capital of Japan?",
                      "Invent a name for a coffee shop. Name only."]) {
  console.log(`\n${prompt}`);
  for (const t of [0, 0.5, 1.0, 1.5]) {
    const n = await uniqueness(prompt, t);
    console.log(`  t=${t.toFixed(1)}  ${"█".repeat(n)} ${n}/5 unique`);
  }
}
```

**Python**
```python
from dotenv import load_dotenv
from groq import Groq
import os

load_dotenv()
groq = Groq(api_key=os.environ["GROQ_API_KEY"])

def uniqueness(prompt, temperature, runs=5):
    outs = []
    for _ in range(runs):
        r = groq.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=512,
            reasoning_effort="low",   # less hidden thinking: cheaper and faster (§3.4)
        )
        outs.append(r.choices[0].message.content.strip())
    return len(set(outs))

for prompt in ["What is the capital of Japan?",
               "Invent a name for a coffee shop. Name only."]:
    print(f"\n{prompt}")
    for t in [0, 0.5, 1.0, 1.5]:
        n = uniqueness(prompt, t)
        print(f"  t={t:.1f}  {'█' * n} {n}/5 unique")
```

Our JavaScript run:

```
What is the capital of Japan?
  t=0.0  █ 1/5 unique
  t=0.5  █ 1/5 unique
  t=1.0  █ 1/5 unique
  t=1.5  █ 1/5 unique

Invent a name for a coffee shop. Name only.
  t=0.0  █ 1/5 unique
  t=0.5  ████ 4/5 unique
  t=1.0  ████ 4/5 unique
  t=1.5  █████ 5/5 unique
```

Our Python run gave the same factual line and `1 → 3 → 4 → 4` for the coffee shop. Your counts
will differ a little. The shape won't: the factual prompt stays at one answer at every
temperature, because nearly all the probability sits on `" Tokyo"`. The creative prompt
spreads out as soon as temperature rises above 0.

Why `reasoning_effort: "low"`? This grid makes 40 calls. Less hidden thinking per call keeps
you inside the free tier's tokens-per-minute limit.

**The lesson:** temperature's effect depends on how *peaked* the distribution already is.
That's why "use 0.7 for everything" is bad advice — pick per task.
</details>

---

### Exercise 4 — Context budget calculator ●●●○○

Write a function `budget({ systemPrompt, history, documents, question, contextWindow, reserveForOutput })`
that returns how many tokens each part uses, how many are left, and whether it fits. If it
doesn't fit, it should drop the **oldest history messages** (never the system prompt, never the
question) until it does — and report what it dropped.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import { encode } from "gpt-tokenizer";
const count = (s) => encode(s).length;

function budget({
  systemPrompt = "",
  history = [],
  documents = [],
  question = "",
  contextWindow = 8192,
  reserveForOutput = 1024,
}) {
  const fixed =
    count(systemPrompt) +
    documents.reduce((a, d) => a + count(d), 0) +
    count(question);

  const available = contextWindow - reserveForOutput - fixed;
  if (available < 0) {
    return { fits: false, reason: "System + docs + question alone exceed the window" };
  }

  // Drop oldest history first until we fit.
  const kept = [];
  let used = 0;
  for (const msg of [...history].reverse()) {   // newest first
    const c = count(msg.content);
    if (used + c > available) break;
    kept.unshift(msg);
    used += c;
  }

  return {
    fits: true,
    breakdown: {
      system: count(systemPrompt),
      documents: documents.reduce((a, d) => a + count(d), 0),
      question: count(question),
      historyKept: used,
    },
    dropped: history.length - kept.length,
    remaining: available - used,
    history: kept,
  };
}

console.log(budget({
  systemPrompt: "You are a helpful research assistant.",
  history: Array.from({ length: 20 }, (_, i) => ({
    role: i % 2 ? "assistant" : "user",
    content: `Message number ${i} with some filler text to take up space.`,
  })),
  documents: ["A very long document. ".repeat(200)],
  question: "Summarise the key finding.",
  contextWindow: 2048,
  reserveForOutput: 512,
}));
```

**Python**
```python
import tiktoken
enc = tiktoken.get_encoding("cl100k_base")
count = lambda s: len(enc.encode(s))

def budget(system_prompt="", history=None, documents=None, question="",
           context_window=8192, reserve_for_output=1024):
    history = history or []
    documents = documents or []

    fixed = count(system_prompt) + sum(count(d) for d in documents) + count(question)
    available = context_window - reserve_for_output - fixed

    if available < 0:
        return {"fits": False,
                "reason": "System + docs + question alone exceed the window"}

    kept, used = [], 0
    for msg in reversed(history):                  # newest first
        c = count(msg["content"])
        if used + c > available:
            break
        kept.insert(0, msg)
        used += c

    return {
        "fits": True,
        "breakdown": {
            "system": count(system_prompt),
            "documents": sum(count(d) for d in documents),
            "question": count(question),
            "history_kept": used,
        },
        "dropped": len(history) - len(kept),
        "remaining": available - used,
        "history": kept,
    }

print(budget(
    system_prompt="You are a helpful research assistant.",
    history=[{"role": "assistant" if i % 2 else "user",
              "content": f"Message number {i} with some filler text to take up space."}
             for i in range(20)],
    documents=["A very long document. " * 200],
    question="Summarise the key finding.",
    context_window=2048,
    reserve_for_output=512,
))
```

You just hand-built the core of what LangChain's `trimMessages` / `trim_messages` does (Day 14)
and what every production RAG pipeline needs.
</details>

---

### Exercise 5 — Force a hallucination, then fix it ●●●○○

1. Ask the model to explain a method that doesn't exist, e.g.
   *"How do I use the `parseWithFallback()` method in Zod?"*
2. Observe the confident, invented answer.
3. Now fix it **three ways** and compare:
   - (a) add "If you're not certain this exists, say so" to the system prompt;
   - (b) drop temperature to 0;
   - (c) paste real Zod docs into the prompt.

Which fix worked best? (This is the argument for RAG, in one exercise.)

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import "dotenv/config";
import Groq from "groq-sdk";
const groq = new Groq({ apiKey: process.env.GROQ_API_KEY });

const Q = "How do I use the parseWithFallback() method in Zod? Show code.";

const run = async (label, messages, temperature = 0.7) => {
  const r = await groq.chat.completions.create({
    model: "openai/gpt-oss-120b", messages, temperature, max_tokens: 1024,
  });
  console.log(`\n═══ ${label} ═══\n${r.choices[0].message.content}`);
};

await run("BASELINE", [{ role: "user", content: Q }]);

await run("FIX A — permission to fail", [
  { role: "system", content:
      "You are a precise engineer. If you are not certain an API exists, say " +
      "'I'm not certain that exists' rather than guessing. Never invent method names." },
  { role: "user", content: Q },
]);

await run("FIX B — temperature 0", [{ role: "user", content: Q }], 0);

await run("FIX C — give it the facts (RAG, manually)", [
  { role: "system", content:
      "Answer ONLY from the documentation below. If the answer isn't there, say " +
      "'Not in the provided docs.'\n\n" +
      "=== ZOD DOCS ===\n" +
      "Zod schemas expose: .parse(data) throws on failure; .safeParse(data) returns " +
      "{ success, data | error }; .catch(value) supplies a fallback on failure; " +
      ".optional(); .default(value).\n=== END ===" },
  { role: "user", content: Q },
]);
```

**Python**
```python
from dotenv import load_dotenv
from groq import Groq
import os

load_dotenv()
groq = Groq(api_key=os.environ["GROQ_API_KEY"])

Q = "How do I use the parse_with_fallback() method in Pydantic? Show code."

def run(label, messages, temperature=0.7):
    r = groq.chat.completions.create(
        model="openai/gpt-oss-120b", messages=messages,
        temperature=temperature, max_tokens=1024,
    )
    print(f"\n═══ {label} ═══\n{r.choices[0].message.content}")

run("BASELINE", [{"role": "user", "content": Q}])

run("FIX A — permission to fail", [
    {"role": "system", "content":
        "You are a precise engineer. If you are not certain an API exists, say "
        "\"I'm not certain that exists\" rather than guessing. Never invent method names."},
    {"role": "user", "content": Q},
])

run("FIX B — temperature 0", [{"role": "user", "content": Q}], temperature=0)

run("FIX C — give it the facts (RAG, manually)", [
    {"role": "system", "content":
        "Answer ONLY from the documentation below. If the answer isn't there, say "
        "'Not in the provided docs.'\n\n"
        "=== PYDANTIC DOCS ===\n"
        "BaseModel exposes: model_validate(data) raises ValidationError on failure; "
        "model_validate_json(str); model_dump(); Field(default=...) supplies defaults.\n"
        "=== END ==="},
    {"role": "user", "content": Q},
])
```

**Our run, in both languages:** the baseline invented the method with full confidence, down to
example code and a made-up table of return types. Fix B (temperature 0) invented it too, and
even claimed it was "added in Zod v3.22". Fix A refused: "I’m not certain that a
`parseWithFallback()` method exists in Zod", then pointed to the real `.catch()` and
`.safeParse()`. Fix C answered exactly "Not in the provided docs."

So the ranking is C, then A, with B no better than the baseline. Temperature barely helps. The wrong answer is the *most likely* answer, so making the model
more confident doesn't make it more correct. Permission-to-fail helps meaningfully. Giving it
the actual facts almost removes the problem. **That ordering is the entire reason Week 2
exists.**
</details>

---

## 9. Interview questions

### Basic

<details>
<summary><b>Q: What is a token?</b></summary>

A chunk of text — roughly 4 characters or 0.75 English words — that the tokenizer maps to an
integer ID. Models operate on token IDs, not characters or words. Common words often get a
single token; rare words are split into several. Leading spaces are part of the token, so
`"cat"` and `" cat"` are distinct.
</details>

<details>
<summary><b>Q: What is a context window?</b></summary>

The maximum number of tokens a model can process in one call, counting **input and output
together**. Exceed it and you get an error or silent truncation. It's a hard architectural
limit, not a setting you can raise.
</details>

<details>
<summary><b>Q: What does temperature do?</b></summary>

It scales the logits before the softmax, which flattens or sharpens the probability
distribution over the next token. Low temperature concentrates probability on the top
candidates (predictable output); high temperature spreads it out (diverse output). It affects
**sampling**, not the model's knowledge — the underlying distribution is the same.
</details>

<details>
<summary><b>Q: Difference between temperature and top_p?</b></summary>

Temperature **rescales** every token's probability. `top_p` **truncates**: it keeps only the
smallest set of top tokens whose probabilities sum to `p`, then samples from those. Temperature
can still (rarely) pick a bizarre token; `top_p` removes bizarre tokens from consideration
entirely. Tune one, not both.
</details>

<details>
<summary><b>Q: Do LLMs have memory?</b></summary>

No. Every API call is stateless. Apparent memory is the application re-sending previous
messages as part of the input. Everything called "memory" in LangChain/LangGraph is a strategy
for deciding *what* to re-send within the context budget.
</details>

### Intermediate

<details>
<summary><b>Q: Why do output tokens cost more than input tokens?</b></summary>

Input tokens are processed in a single parallel forward pass. Output tokens are generated
serially — one full forward pass per token, each conditioned on all previous ones. Serial GPU
time is more expensive than parallel, so providers price output tokens higher than input —
often several times higher; check your provider's price page for the actual ratio.
</details>

<details>
<summary><b>Q: Why are hallucinations inherent rather than a bug?</b></summary>

The model is trained to maximise the likelihood of the next token given the context. There is
no separate "is this true?" step. When the training distribution makes a fluent, confident
answer more likely than an admission of ignorance, the model produces the fluent answer.
Mitigations work by changing the input distribution (retrieval, tools) or by explicitly making
"I don't know" a high-probability continuation (prompting).
</details>

<details>
<summary><b>Q: What is "lost in the middle"?</b></summary>

An empirical finding that models attend more reliably to information at the beginning and end
of a long context than to information in the middle. Practical implications: put the most
important instructions and the most relevant retrieved documents at the extremes, and prefer
retrieving 5 highly relevant chunks over dumping 100 mediocre ones.
</details>

<details>
<summary><b>Q: Why doesn't `temperature: 0` give byte-identical results?</b></summary>

`temperature: 0` means greedy decoding — pick the argmax (the single highest-scoring token). But
the logits themselves vary slightly from run to run. Three causes: the order of floating-point
additions on GPUs is not fixed, the server batches your request with different requests each
time, and mixed-precision arithmetic rounds differently. When two tokens are nearly
tied, tiny differences flip the argmax. Providers also silently update model weights. Never
assert exact string equality on model output.
</details>

<details>
<summary><b>Q: A user says your chatbot "gets slower and more expensive over a long conversation." Why?</b></summary>

Because the app re-sends the entire history on every turn. Turn *n* sends O(n) tokens, so total
cost across a conversation is O(n²) — it grows with the square of the number of turns. Fixes:
a sliding window (keep only the last few turns), summarising older turns, or retrieving only
relevant past messages. Prompt caching (where supported) reduces the cost but
not the token count.
</details>

### Advanced

<details>
<summary><b>Q: You must guarantee valid JSON output. Walk through your options, worst to best.</b></summary>

1. **Prompt only** — "respond in JSON". Fails a few percent of the time; the model adds prose or
   markdown fences.
2. **Prompt + parse-and-retry** — catch the parse error, feed it back, ask for a fix. Works, but
   costs an extra round trip and can loop.
3. **JSON mode** (`response_format: { type: "json_object" }`) — provider guarantees syntactically
   valid JSON, but *not* your schema.
4. **Tool/function calling with a schema** — the provider constrains generation to your schema.
   This is what `withStructuredOutput` / `with_structured_output` uses under the hood.
5. **Constrained decoding / grammar-based sampling** — the sampler is masked at each step so
   only schema-valid tokens are possible. Strongest guarantee; supported by some providers and
   local runtimes.

In production: use (4), validate with Zod/Pydantic anyway, and have a (2)-style retry as a
fallback. Day 06 builds all of this.
</details>

<details>
<summary><b>Q: How would you estimate the monthly cost of a chat product before building it?</b></summary>

```
cost/conversation ≈ Σ over turns [ (system + history_so_far + retrieved) × in_price
                                 + answer_len × out_price ]
```

Key drivers: average turns per conversation (this is the quadratic term), whether you do RAG
(retrieved chunks dominate input), and the history strategy. Then multiply by conversations/month
and add a 30–50% buffer for retries, evals and non-English users (worse token ratios).
Measure with real traffic as soon as you can — pre-launch estimates are often off by a wide
margin, and only measured usage tells you by how much.
</details>

<details>
<summary><b>Q: What is a KV-cache and why does it matter to you as an application developer?</b></summary>

During generation, the attention keys and values for already-processed tokens are cached. So
each new token only computes attention against the cache rather than recomputing everything
(§3.7). Two consequences for your application:

- (a) Long *inputs* are relatively cheap and fast; long *outputs* are not.
- (b) **Prompt caching** exposes this to you. Keep a long, stable prefix (system prompt +
  few-shot examples + documents) *byte-identical* across calls. Then providers can reuse the
  cache and charge much less.

This is why you put the stable parts first and the variable parts last in your prompt.
</details>

<details>
<summary><b>Q: Your RAG bot gives great answers in testing and bad ones in production. Give five hypotheses tied to today's material.</b></summary>

1. **Context overflow** — production docs are longer, so retrieved chunks push the question out
   of the window or get silently truncated.
2. **Lost in the middle** — you're stuffing 20 chunks; the relevant one lands in position 11.
3. **Non-English users** — token counts blow up, hitting limits your English tests never did.
4. **Temperature too high** for a factual task, so answers vary run to run and some are wrong.
5. **History unbounded** — by turn 15 the retrieved context is being crowded out by chat history.

Notice all five are today's concepts, not model quality.
</details>

---

## 10. Recap

You can now explain:

- ✅ A token is about 4 characters; models see token IDs, never letters
- ✅ The context window covers input **and** output, and is a hard limit
- ✅ Generation is a loop: one token → append → run again
- ✅ Temperature rescales the distribution; top_p truncates it
- ✅ `max_tokens` truncates, it does not summarise — and on a reasoning model the hidden
  thinking counts towards it, so a small limit can leave the answer empty
- ✅ Your local token count is an estimate; the API's `prompt_tokens` is the bill
- ✅ LLMs are stateless — "memory" is your app re-sending history
- ✅ Hallucination is a property of next-token prediction, and retrieval is the strongest fix
- ✅ A chat model is pre-trained, instruction-tuned, then preference-tuned — and frozen when you
  call it
- ✅ Attention lets each token weigh the tokens before it; the KV-cache stores their keys and values

**You also hand-built** a token counter, a history trimmer and a context budgeter. Those three
utilities are, in miniature, what a large chunk of LangChain does for you.

### Tomorrow

**[Day 02 — Prompt engineering + raw APIs](day-02-prompt-engineering-and-raw-apis.md)**:
zero-shot, few-shot, chain-of-thought, ReAct and self-consistency — plus tool calling and JSON
mode using nothing but the raw SDK. You'll build a working ReAct loop *by hand* before any
framework touches your code.

### Quick self-check

Answer without scrolling up:

1. If your context window is 8K and your prompt is 7.5K tokens, what's the largest answer you can get?
2. Same prompt, same seed, `temperature: 0`. Guaranteed identical output — true or false?
3. Your chatbot's turn-50 request costs 40× turn-1. Nothing is broken. Why?

<details>
<summary>Answers</summary>

1. ~500 tokens (≈375 words) — and the API may error or truncate rather than warn you.
2. **False.** Greedy is not the same as deterministic. Tiny GPU rounding differences and
   provider-side batching can flip near-ties.
3. You're re-sending the whole history every turn. Cost per conversation is O(n²) in turns: it
   grows with the square of the number of turns.
</details>

---

<div align="center">

**[← Day 0C — Just-Enough Maths](../week-00-start-here/day-00c-just-enough-maths.md)** · **[Week 1 index](README.md)** · **[Day 02 — Prompt Engineering & Talking to Models With No Framework →](day-02-prompt-engineering-and-raw-apis.md)**

</div>
