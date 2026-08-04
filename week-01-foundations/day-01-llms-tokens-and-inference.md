# Day 01 — What an LLM Actually Is: Tokens, Context & Inference

> ⏱ **Time:** ~2 hours · 🎯 **Prereqs:** [SETUP.md](../SETUP.md) done · 🧩 **Difficulty:** ●○○○○

**Today you learn:** what a token is, why context windows exist, what temperature *really*
does, and the exact path a message takes from your keyboard to the model's answer. No
LangChain today — you can't use a tool well if you don't know what it's wrapping.

---

## 1. The problem

Imagine you hire an assistant with a very unusual condition.

- She has read most of the internet and remembers the *patterns* in it, but not the facts as facts.
- She has **no memory between conversations**. Every time you talk to her, she starts blank.
- She can only hold a fixed amount of paper on her desk at once. Give her more and the oldest pages fall off.
- When you ask her something, she doesn't "look up" an answer. She writes the answer **one word at a time**, each time picking the word that feels most likely to come next.
- She will never say "I don't know" unless you tell her she's allowed to.

That's an LLM. Every weird behaviour you've heard about — hallucinations, forgetting the start
of a long chat, giving different answers to the same question — falls directly out of those
five properties.

**Concrete pain this causes:**

> A junior dev builds a customer support bot. It works great in testing. In production,
> customers complain it "forgets what they said two messages ago" and "makes up refund
> policies." The dev thinks the model is broken. It isn't. He never sent the chat history
> (property 2), and he never gave it the real policy document (property 1).

Today's goal: make those five properties concrete enough that you'd predict that bug before shipping it.

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
It generates **one token**, then gets fed its own output and generates one more. A 500-word
answer is 600-ish forward passes through the network. That's why:

- streaming is possible (tokens exist one at a time anyway),
- output tokens cost more than input tokens (each one is a full pass),
- and long outputs are slow but long inputs are fast.

---

## 3. First principles

### 3.1 Tokens — the atoms

Models don't see letters and they don't see words. They see **tokens**: chunks of characters
that the tokenizer learned are statistically useful. Roughly:

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
can cost 2–4× the tokens of English, because the tokenizer's vocabulary was built mostly from
English text. If you're building for a non-English market, your cost model is not the one in
the blog posts.

> 🧠 **Analogy.** Tokens are LEGO bricks. Common words like `" the"` got their own custom
> moulded brick because they show up constantly. Rare words get built from smaller generic
> bricks. Your name is probably 2–4 bricks.

### 3.2 The context window — the desk

The **context window** is the maximum number of tokens the model can look at in a single call.
Crucially, it covers **input + output together**.

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

1. **Bigger context ≠ better answers.** Models exhibit a *"lost in the middle"* effect —
   information at the very start and very end of a long context is used reliably; stuff buried
   in the middle gets ignored. This is a big reason RAG (Week 2) beats "just paste the whole book in."
2. **Context is not memory.** Nothing persists between calls. If a chatbot "remembers" your
   name, it's because your app re-sent the whole conversation. You'll build that on Day 04.
3. **Cost scales with context.** You pay for every input token, on **every turn**. A 50-message
   conversation re-sends all 50 messages on message 51. Naive chatbots get quadratically expensive.

### 3.3 The probability distribution — where "creativity" comes from

After the forward pass, the model produces a score (a *logit*) for **every token in its
vocabulary** — typically 30,000–200,000 numbers. Softmax turns those into probabilities:

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

### 3.4 The sampling knobs

#### `temperature` — flatten or sharpen the distribution

Temperature divides the logits before softmax.

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

> ⚠️ **`temperature: 0` is not "deterministic".** It's *greedy* — always pick the top token.
> You'll still get different answers across runs, because floating-point non-determinism on
> GPUs, batching, and provider-side model updates all shift the top choice on near-ties.
> Never build a test that asserts exact string equality on LLM output.

#### `top_p` (nucleus sampling) — truncate the tail

Instead of scaling probabilities, `top_p` **cuts off** the long tail. `top_p = 0.9` means:
sort tokens by probability, keep adding until they sum to 90%, discard the rest, sample from
what's left.

```
top_p = 0.9

" Paris"    78%  ✅ running total 78%
" located"  11%  ✅ running total 89%
" the"       6%  ✅ running total 95% → crossed 90%, stop here
" Lyon"      1%  ❌ discarded
" banana"  0.001% ❌ discarded — can NEVER be chosen
```

This is why `top_p` is good at preventing "the model said something insane" — the insane
tokens are removed from the pool entirely, no matter what temperature does.

> 🎯 **Practical advice:** tune **one** of temperature or top_p, not both. Most teams set
> `top_p = 1` and adjust temperature. Adjusting both makes the effect impossible to reason about.

#### `frequency_penalty` and `presence_penalty`

Both fight repetition, differently:

| Parameter | Rule | Effect |
|---|---|---|
| `frequency_penalty` | Penalty grows **with each repeat** | Stops "very very very very good" |
| `presence_penalty` | Flat penalty once a token appears **at all** | Pushes toward new topics/vocabulary |

Range is typically `-2.0` to `2.0`; `0` is off. Useful values are small: `0.1`–`0.6`. Note that
these are OpenAI-style parameters — not every provider supports them (Anthropic doesn't).

#### `max_tokens` — a budget, not an instruction

`max_tokens` caps the **output**. It does not make the model write concisely; it makes the
model get **cut off mid-sentence**. If you want short answers, say so in the prompt *and* set
`max_tokens` as a safety net.

```
❌ max_tokens: 50, prompt: "Explain photosynthesis"
   → "Photosynthesis is the process by which plants convert light energy into chemical
      energy. It occurs in the chloroplasts, specifically in structures called thyla"   ✂️

✅ prompt: "Explain photosynthesis in exactly two sentences."  + max_tokens: 200
   → complete, short answer
```

Check `finish_reason` / `stop_reason` in the response: `"length"` means you got truncated,
`"stop"` means the model finished naturally.

### 3.5 Why hallucinations are inevitable

Sampling picks the *statistically plausible* next token. It has no truth-check step. If you ask
about a nonexistent library, "I don't know" is a rare continuation in the training data —
confident documentation is common. So the model writes confident documentation.

```
"How do I use the getUserPreferences() method in Express?"

Model's internal reality:  "Express docs usually look like this →"
Model's output:            confident, well-formatted, completely invented API
```

**Fixes, in order of effectiveness:**

1. **Give it the facts** — retrieval (RAG, Week 2). By far the biggest lever.
2. **Give it tools** — let it look things up (Week 3).
3. **Give it permission to fail** — "If the context doesn't contain the answer, say 'I don't know.'"
4. **Lower temperature** — helps a little.
5. **Ask for citations** — makes hallucination visible even if it doesn't prevent it.

---

## 4. Code — JavaScript

We're using the **raw provider SDK**, not LangChain, so you see exactly what's happening.

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
  model: "llama-3.3-70b-versatile",

  // The conversation. Always an ARRAY of role/content objects.
  messages: [
    { role: "system", content: "You are a concise physics tutor for 12-year-olds." },
    { role: "user", content: "Why do things fall down?" },
  ],

  temperature: 0.7,          // 0 = deterministic-ish, 2 = chaotic
  top_p: 1,                  // 1 = no truncation (tune temperature OR this, not both)
  max_tokens: 200,           // hard cap on OUTPUT tokens
  frequency_penalty: 0,      // >0 discourages repeating the same token
  presence_penalty: 0,       // >0 pushes toward new topics
  stop: null,                // e.g. ["\n\n"] to stop at a blank line
});

console.log(response.choices[0].message.content);

// Everything you should be logging in production:
console.log({
  finishReason: response.choices[0].finish_reason,  // "stop" | "length" | "tool_calls"
  inputTokens:  response.usage.prompt_tokens,
  outputTokens: response.usage.completion_tokens,
  totalTokens:  response.usage.total_tokens,
});
```

### 4.2 Proving the model has no memory

```js
// day01-no-memory.js
import "dotenv/config";
import Groq from "groq-sdk";
const groq = new Groq({ apiKey: process.env.GROQ_API_KEY });

const ask = async (messages) => {
  const r = await groq.chat.completions.create({
    model: "llama-3.3-70b-versatile",
    messages,
  });
  return r.choices[0].message.content;
};

// ❌ Two separate calls — the second knows nothing about the first
console.log(await ask([{ role: "user", content: "My name is Wasif." }]));
console.log(await ask([{ role: "user", content: "What is my name?" }]));
// → "I don't have access to your name..."

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

```
token count: 12
pieces:      "The" | " un" | "bel" | "ie" | "vable" | " cat" | " sat" | " on" | " the" | " mat" | "." | " 🦄"
```

Try these and watch the count explode:

```js
["hello world",
 "नमस्ते दुनिया",                 // Hindi — same meaning, ~4x the tokens
 "def f(x): return x**2",
 "a".repeat(100),
].forEach((s) => console.log(encode(s).length, "←", s.slice(0, 30)));
```

### 4.4 Streaming — watching tokens arrive

```js
// day01-stream.js
import "dotenv/config";
import Groq from "groq-sdk";
const groq = new Groq({ apiKey: process.env.GROQ_API_KEY });

const stream = await groq.chat.completions.create({
  model: "llama-3.3-70b-versatile",
  messages: [{ role: "user", content: "Count from 1 to 20 slowly." }],
  stream: true,                                   // ← the only change
});

for await (const chunk of stream) {               // async iterator
  process.stdout.write(chunk.choices[0]?.delta?.content ?? "");
}
console.log();
```

Streaming doesn't make generation faster. It makes **time-to-first-token** the thing the user
perceives instead of time-to-last-token. A 12-second answer feels instant if the first word
lands in 300 ms.

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
      model: "llama-3.3-70b-versatile",
      messages: [{ role: "user", content: "Write a 6-word story about the sea." }],
      temperature,
      max_tokens: 30,
    });
    console.log(" ", r.choices[0].message.content.trim());
  }
}
```

At `0` the three runs will be near-identical. At `1.5` they'll barely be the same genre.

---

## 5. Code — Python

Same five programs, same outputs.

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
    model="llama-3.3-70b-versatile",

    # The conversation. Always a LIST of role/content dicts.
    messages=[
        {"role": "system", "content": "You are a concise physics tutor for 12-year-olds."},
        {"role": "user",   "content": "Why do things fall down?"},
    ],

    temperature=0.7,          # 0 = deterministic-ish, 2 = chaotic
    top_p=1,                  # 1 = no truncation (tune temperature OR this, not both)
    max_tokens=200,           # hard cap on OUTPUT tokens
    frequency_penalty=0,      # >0 discourages repeating the same token
    presence_penalty=0,       # >0 pushes toward new topics
    stop=None,                # e.g. ["\n\n"] to stop at a blank line
)

print(response.choices[0].message.content)

print({
    "finish_reason": response.choices[0].finish_reason,
    "input_tokens":  response.usage.prompt_tokens,
    "output_tokens": response.usage.completion_tokens,
    "total_tokens":  response.usage.total_tokens,
})
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
        model="llama-3.3-70b-versatile",
        messages=messages,
    )
    return r.choices[0].message.content

# ❌ Two separate calls — the second knows nothing about the first
print(ask([{"role": "user", "content": "My name is Wasif."}]))
print(ask([{"role": "user", "content": "What is my name?"}]))
# → "I don't have access to your name..."

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

```python
for s in ["hello world",
          "नमस्ते दुनिया",              # Hindi — same meaning, ~4x the tokens
          "def f(x): return x**2",
          "a" * 100]:
    print(len(enc.encode(s)), "←", s[:30])
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
    model="llama-3.3-70b-versatile",
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
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": "Write a 6-word story about the sea."}],
            temperature=temperature,
            max_tokens=30,
        )
        print(" ", r.choices[0].message.content.strip())
```

### 🔁 JS ↔ Python differences you just saw

| | JavaScript | Python |
|---|---|---|
| Load env | `import "dotenv/config"` | `load_dotenv()` |
| Async | `await` everywhere (SDK is async-first) | sync by default; `AsyncGroq` for async |
| Streaming loop | `for await (const c of stream)` | `for chunk in stream:` |
| Null-safe access | `chunk.choices[0]?.delta?.content ?? ""` | `chunk.choices[0].delta.content or ""` |
| Naming | `camelCase` params in LangChain, `snake_case` in raw SDK | `snake_case` everywhere |
| Tokenizer lib | `gpt-tokenizer` | `tiktoken` |

> ⚠️ **Naming trap you'll hit all week.** The raw provider SDKs use `snake_case` in *both*
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

Two things worth internalising:

1. **The `role` field is not magic.** It gets rendered into special text tokens
   (`<|start_header_id|>system<|end_header_id|>`). The "system" role is powerful because the
   model was *trained* to weight text in that position heavily — not because it's a different code path.
2. **The KV-cache** is why input tokens are ~4× cheaper than output tokens. Input is processed
   in one parallel pass; output is a serial loop.

### Why the same prompt costs different amounts on different providers

Every provider uses a different tokenizer. The same sentence might be 18 tokens on Llama and
21 on GPT. Never hard-code token counts across providers — always count with the right tokenizer.

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

**What you should notice:** plain English gets ~4 chars/token. URLs and code get ~2–3 because
punctuation and slashes fragment. Non-English gets the worst ratio because those characters
weren't common enough in training to earn their own tokens.
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
  (await groq.chat.completions.create({ model: "llama-3.3-70b-versatile", messages }))
    .choices[0].message.content;

function trimHistory(messages, n) {
  const [system, ...rest] = messages;
  return system.role === "system" ? [system, ...rest.slice(-n)] : messages.slice(-n);
}

const history = [
  { role: "system", content: "You are a helpful assistant." },
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
        model="llama-3.3-70b-versatile", messages=messages
    ).choices[0].message.content

def trim_history(messages, n):
    if messages and messages[0]["role"] == "system":
        return [messages[0]] + messages[1:][-n:]
    return messages[-n:]

history = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user",   "content": "I'm planning a trip to Japan."},
]
history.append({"role": "assistant", "content": ask(history)})

history.append({"role": "user", "content": "I'll be there for 10 days in April."})
history.append({"role": "assistant", "content": ask(history)})

history.append({"role": "user", "content": "How long did I say I'd be there, and where?"})

print("FULL   :", ask(history))
print("TRIM(2):", ask(trim_history(history, 2)))
```

`TRIM(2)` will have lost Japan and/or the 10 days. You've just discovered the exact problem
that Day 14 (memory) and Day 20 (checkpointers) solve properly.
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
      model: "llama-3.3-70b-versatile",
      messages: [{ role: "user", content: prompt }],
      temperature,
      max_tokens: 30,
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
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=30,
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

**Expected shape:** the factual prompt stays at 1–2 unique answers even at high temperature —
the probability mass on `" Tokyo"` is so dominant that temperature can't easily dislodge it.
The creative prompt goes 1 → 3 → 5 → 5.

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
3. Now fix it **three ways** and compare: (a) add "If you're not certain this exists, say so"
   to the system prompt, (b) drop temperature to 0, (c) paste real Zod docs into the prompt.

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
    model: "llama-3.3-70b-versatile", messages, temperature, max_tokens: 200,
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
        model="llama-3.3-70b-versatile", messages=messages,
        temperature=temperature, max_tokens=200,
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

**Typical result ranking:** C ≫ A > B.
Temperature barely helps — the wrong answer is the *most likely* answer, so making the model
more confident doesn't make it more correct. Permission-to-fail helps meaningfully. Giving it
the actual facts basically eliminates the problem. **That ordering is the entire reason Week 2
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
time is more expensive than parallel, so providers price output at roughly 2–5× input.
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

`temperature: 0` means greedy decoding — pick the argmax. But the logits themselves vary
slightly run-to-run due to non-deterministic floating-point reduction order on GPUs, variable
batch composition on the server, and mixed-precision arithmetic. When two tokens are nearly
tied, tiny differences flip the argmax. Providers also silently update model weights. Never
assert exact string equality on model output.
</details>

<details>
<summary><b>Q: A user says your chatbot "gets slower and more expensive over a long conversation." Why?</b></summary>

Because the app re-sends the entire history on every turn. Turn *n* sends O(n) tokens, so total
cost across a conversation is O(n²). Fixes: sliding window, summarising older turns, or
retrieving only relevant past messages. Prompt caching (where supported) reduces the cost but
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
Measure with real traffic ASAP — estimates are usually 2× off.
</details>

<details>
<summary><b>Q: What is a KV-cache and why does it matter to you as an application developer?</b></summary>

During generation, the attention keys and values for already-processed tokens are cached so
each new token only computes attention against the cache rather than recomputing everything.
Application-level consequences: (a) long *inputs* are relatively cheap and fast, long *outputs*
are not; (b) **prompt caching** exposes this to you — if you keep a long, stable prefix (system
prompt + few-shot examples + documents) *byte-identical* across calls, providers can reuse the
cache and charge much less. This is why you put the stable parts first and the variable parts
last in your prompt.
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

- ✅ A token is ~4 characters; models see token IDs, never letters
- ✅ The context window covers input **+** output, and is a hard limit
- ✅ Generation is a loop: one token → append → run again
- ✅ Temperature rescales the distribution; top_p truncates it
- ✅ `max_tokens` truncates, it does not summarise
- ✅ LLMs are stateless — "memory" is your app re-sending history
- ✅ Hallucination is a property of next-token prediction, and retrieval is the strongest fix

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
2. **False.** Greedy ≠ deterministic; GPU float non-determinism and provider-side batching flip near-ties.
3. You're re-sending the whole history every turn. Cost per conversation is O(n²) in turns.
</details>
