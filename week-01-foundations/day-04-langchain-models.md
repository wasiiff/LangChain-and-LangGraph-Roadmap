# Day 04 — LangChain Models: invoke, stream, batch & Message Types

> ⏱ **Time:** ~2.5 hours · 🎯 **Prereqs:** [Day 03](day-03-js-python-essentials-and-why-langchain.md) · 🧩 **Difficulty:** ●●○○○

**Today you learn:** your first real LangChain code. The chat-model interface, every
constructor parameter, `invoke` / `stream` / `batch`, the four message types, token usage,
provider swapping in one line, and a multi-turn chatbot with proper history handling.

---

## 1. The problem

Yesterday you saw three provider SDKs, three request shapes, three response shapes:

```js
// Groq
r.choices[0].message.content

// Gemini
r.response.text()

// Anthropic
r.content[0].text
```

Now imagine you built a summariser on Groq, and your PM says *"can we try Gemini, it's cheaper
at our volume?"* You go and change every call site, every response accessor, every streaming
loop, every tool-calling block.

**The chat-model abstraction fixes exactly this.** One interface, one message type, one
response shape — and the provider becomes a one-line config change.

---

## 2. Mental model

```
   YOUR CODE                                        THE PROVIDERS
   ─────────                                        ─────────────

   model.invoke(messages)  ──┐
   model.stream(messages)  ──┤    ┌─────────────┐   ┌──────────┐
   model.batch([...])      ──┼───▶│ BaseChatModel│──▶│ Groq API │
   model.bindTools([...])  ──┤    │  (interface) │   ├──────────┤
                             ┘    └─────────────┘   │ Gemini   │
                                        ▲            ├──────────┤
             one interface ─────────────┘            │ OpenAI   │
                                                     ├──────────┤
   always returns AIMessage                          │ Ollama   │
   ┌──────────────────────────┐                      └──────────┘
   │ .content     the text    │
   │ .text        the text    │      swap the provider,
   │ .tool_calls  requests    │      keep all your code
   │ .usage_metadata  tokens  │
   │ .response_metadata       │
   └──────────────────────────┘
```

And the four message types — the vocabulary of every conversation:

```
   ┌──────────────────┬──────────────────────────────────────────────┐
   │ SystemMessage    │ Instructions. Who the model is. Set ONCE.    │
   │ HumanMessage     │ What the user said.                          │
   │ AIMessage        │ What the model said (and any tool requests). │
   │ ToolMessage      │ The result of running a tool. Day 15.        │
   └──────────────────┴──────────────────────────────────────────────┘

   A conversation is just an array of these, in order:

   [ System("You are a tutor")            ← set once, at the front
     Human("Explain gravity")
     AI("Gravity is...")
     Human("Simpler please")              ← the model sees ALL of this
     AI("Things fall down because...") ]
```

---

## 3. First principles

### 3.1 Two ways to create a model

**Direct class** — explicit, gives you provider-specific options:

```js
import { ChatGroq } from "@langchain/groq";
const model = new ChatGroq({ model: "llama-3.3-70b-versatile" });
```

**`initChatModel` / `init_chat_model`** — the universal loader. Provider becomes a string:

```js
import { initChatModel } from "langchain";
const model = await initChatModel("groq:llama-3.3-70b-versatile");
```

Use the direct class when you want provider-specific parameters or clarity. Use the universal
loader when the provider should be **configuration** — e.g. read from an env var so ops can
switch models without a deploy.

> ⚠️ **JS gotcha:** `initChatModel` is `await`ed (it lazily imports the provider package);
> Python's `init_chat_model` is not.

### 3.2 The constructor parameters — every one explained

```js
new ChatGroq({
  // ─── Identity ──────────────────────────────────────────────────────────
  model: "llama-3.3-70b-versatile",  // REQUIRED. Which model.
  apiKey: process.env.GROQ_API_KEY,  // Optional — read from env by convention.

  // ─── Sampling (see Day 01) ─────────────────────────────────────────────
  temperature: 0.7,      // 0–2. Randomness. 0 for extraction, 0.7 for chat.
  topP: 1,               // Nucleus sampling. Tune this OR temperature.
  maxTokens: 1024,       // Cap on OUTPUT tokens. Truncates; doesn't summarise.
  stop: ["\n\n"],        // Stop sequences. Generation halts before these.

  // ─── Reliability ───────────────────────────────────────────────────────
  maxRetries: 2,         // Automatic retries on transient errors. Default 2.
  timeout: 30_000,       // ms. Abort a hanging request.

  // ─── Behaviour ─────────────────────────────────────────────────────────
  streaming: false,      // Rarely needed — .stream() handles this per call.
  cache: false,          // Cache identical requests (Day 24).
  callbacks: [],         // Observability hooks (Day 25).
  metadata: { app: "studybuddy" },   // Attached to traces.
  tags: ["production"],              // Filterable in LangSmith.
});
```

**Naming reminder from Day 01:** LangChain **JS uses camelCase** (`maxTokens`), LangChain
**Python uses snake_case** (`max_tokens`). The raw provider SDKs use snake_case in both.

### 3.3 The three core methods

| Method | Input | Output | Use when |
|---|---|---|---|
| `invoke` | one input | one `AIMessage` | Normal single request |
| `stream` | one input | async iterator of chunks | You want tokens as they arrive |
| `batch` | array of inputs | array of `AIMessage` | Many **independent** inputs |

**`batch` is not just a loop.** It runs requests concurrently with a configurable concurrency
limit, so you get parallelism without hand-rolling `Promise.all` + a semaphore (which you did
on Day 03).

```js
// These are equivalent in result, but batch handles concurrency for you:
await model.batch(["a", "b", "c"], { maxConcurrency: 2 });
```

> ⚠️ `batch` is for **independent** inputs. A conversation is not independent — each turn
> depends on the last. Never use `batch` for chat turns.

### 3.4 What `invoke` accepts

All four of these work:

```js
await model.invoke("What is 2+2?");                            // 1. plain string
await model.invoke([{ role: "user", content: "What is 2+2?" }]); // 2. plain objects
await model.invoke([new HumanMessage("What is 2+2?")]);          // 3. message classes
await model.invoke([                                             // 4. tuples (JS: arrays)
  ["system", "You are terse."],
  ["human", "What is 2+2?"],
]);
```

A bare string is sugar for `[new HumanMessage(str)]`. Use message classes when you need
type safety, tool calls, or multimodal content; use plain objects for quick scripts.

### 3.5 What you get back: `AIMessage`

```js
const res = await model.invoke("Say hello");

res.content            // "Hello!" — string, OR an array of content blocks (multimodal)
res.text                // always a string, even when content is blocks ← prefer this
res.tool_calls          // [] or [{ name, args, id }]  (Day 15)
res.usage_metadata      // { input_tokens, output_tokens, total_tokens }
res.response_metadata   // provider-specific: finish_reason, model name, logprobs...
res.id                  // message id
```

> 🔑 **Prefer `.text` over `.content`.** With multimodal models `content` can be an *array* of
> blocks (`[{type:"text",...}, {type:"image",...}]`), so `res.content.toUpperCase()` explodes.
> `.text` always gives you the concatenated text.

### 3.6 Streaming

```js
const stream = await model.stream("Count to 5");
for await (const chunk of stream) {
  process.stdout.write(chunk.content);
}
```

Each chunk is an `AIMessageChunk`. Chunks are **addable** — a genuinely useful design:

```js
let full;
for await (const chunk of stream) {
  full = full ? full.concat(chunk) : chunk;   // JS: .concat()   Python: full += chunk
}
console.log(full.text);            // the complete message
console.log(full.usage_metadata);  // usage arrives in the FINAL chunk
```

> ⚠️ `usage_metadata` is `undefined` on early chunks — token counts only arrive at the end.
> If you need usage while streaming, accumulate chunks and read it from the total.

### 3.7 Memory = re-sending history (Day 01, now with types)

```js
const history = [new SystemMessage("You are a helpful tutor.")];

async function chat(userText) {
  history.push(new HumanMessage(userText));
  const res = await model.invoke(history);   // send EVERYTHING
  history.push(res);                          // remember the AI's reply too
  return res.text;
}
```

The two mistakes people make here:

1. **Forgetting to push the AI response.** The model then can't see what it said, and repeats itself.
2. **Never trimming.** Turn 50 sends 50 turns of tokens. See §4.6.

### 3.8 Swapping providers

```js
const model =
  provider === "groq"   ? new ChatGroq({ model: "llama-3.3-70b-versatile" }) :
  provider === "gemini" ? new ChatGoogleGenerativeAI({ model: "gemini-2.5-flash" }) :
                          new ChatOllama({ model: "llama3.2" });

// EVERYTHING downstream is identical.
await model.invoke(history);
```

**This is the payoff.** Not "less code" — *isolation*. The provider decision stops leaking into
every file.

---

## 4. Code — JavaScript

```bash
npm install langchain @langchain/core @langchain/groq @langchain/google-genai @langchain/ollama dotenv
```

### 4.1 Hello, model

```js
// day04-hello.js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";

const model = new ChatGroq({
  model: "llama-3.3-70b-versatile",
  temperature: 0.7,
  maxTokens: 500,
});

const res = await model.invoke("Explain recursion to a 10-year-old in 3 sentences.");

console.log(res.text);
console.log("---");
console.log("tokens:", res.usage_metadata);
console.log("finish:", res.response_metadata.finish_reason);
```

### 4.2 Message types

```js
// day04-messages.js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";
import { SystemMessage, HumanMessage, AIMessage } from "@langchain/core/messages";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });

const messages = [
  new SystemMessage(
    "You are StudyBuddy, a patient tutor. Always answer in exactly two sentences."
  ),
  new HumanMessage("What is a variable in programming?"),
  new AIMessage("A variable is a labelled box that holds a value. You can change what's inside."),
  new HumanMessage("Give me an analogy that isn't a box."),
];

const res = await model.invoke(messages);
console.log(res.text);

// The three ways to write the same thing:
await model.invoke("hi");                                  // string
await model.invoke([{ role: "user", content: "hi" }]);     // object
await model.invoke([["human", "hi"]]);                     // tuple
```

### 4.3 invoke vs stream vs batch

```js
// day04-three-methods.js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });

// ── INVOKE ───────────────────────────────────────────────────────────────
console.log("── invoke ──");
const one = await model.invoke("Name one planet. One word.");
console.log(one.text);

// ── STREAM ───────────────────────────────────────────────────────────────
console.log("\n── stream ──");
const t0 = Date.now();
let firstTokenAt = null;
let full;

for await (const chunk of await model.stream("List 5 planets, one per line.")) {
  firstTokenAt ??= Date.now() - t0;
  process.stdout.write(chunk.content);
  full = full ? full.concat(chunk) : chunk;      // chunks are addable
}

console.log(`\ntime to first token: ${firstTokenAt}ms | total: ${Date.now() - t0}ms`);
console.log("usage (from accumulated chunks):", full.usage_metadata);

// ── BATCH ────────────────────────────────────────────────────────────────
console.log("\n── batch ──");
const questions = [
  "Capital of Japan? One word.",
  "Capital of France? One word.",
  "Capital of Peru? One word.",
  "Capital of Kenya? One word.",
];

const t1 = Date.now();
const answers = await model.batch(questions, { maxConcurrency: 2 });
console.log(answers.map((a) => a.text.trim()));
console.log(`batch of ${questions.length} took ${Date.now() - t1}ms`);
```

### 4.4 Provider swapping in one line

```js
// day04-providers.js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";
import { ChatGoogleGenerativeAI } from "@langchain/google-genai";
import { ChatOllama } from "@langchain/ollama";

function getModel(name = process.env.MODEL_PROVIDER ?? "groq") {
  switch (name) {
    case "groq":   return new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });
    case "gemini": return new ChatGoogleGenerativeAI({ model: "gemini-2.5-flash", temperature: 0 });
    case "ollama": return new ChatOllama({ model: "llama3.2", temperature: 0 });
    default: throw new Error(`Unknown provider: ${name}`);
  }
}

// Identical code path for all three:
for (const name of ["groq", "gemini", "ollama"]) {
  try {
    const res = await getModel(name).invoke("Reply with exactly one word: ready");
    console.log(`${name.padEnd(8)} → ${res.text.trim()}`);
  } catch (e) {
    console.log(`${name.padEnd(8)} → skipped (${e.message.slice(0, 50)})`);
  }
}
```

<details>
<summary>💳 Same thing with OpenAI / Anthropic</summary>

```bash
npm install @langchain/openai @langchain/anthropic
```
```js
import { ChatOpenAI } from "@langchain/openai";
import { ChatAnthropic } from "@langchain/anthropic";

case "openai":    return new ChatOpenAI({ model: "gpt-4.1", temperature: 0 });
case "anthropic": return new ChatAnthropic({ model: "claude-sonnet-4-5", temperature: 0 });
```
Nothing else in your app changes.
</details>

### 4.5 The universal loader

```js
// day04-init-chat-model.js
import "dotenv/config";
import { initChatModel } from "langchain";

// Provider is now a STRING — perfect for env-driven config.
const model = await initChatModel(process.env.MODEL ?? "groq:llama-3.3-70b-versatile", {
  temperature: 0,
  maxTokens: 200,
});

console.log((await model.invoke("Say READY")).text);

// Runtime-configurable: pick the model per call.
const flexible = await initChatModel(undefined, { configurableFields: ["model"] });
console.log((await flexible.invoke("Say A", {
  configurable: { model: "groq:llama-3.1-8b-instant" },
})).text);
```

### 4.6 StudyBuddy v0 — a chatbot with real history handling

```js
// day04-studybuddy.js
import "dotenv/config";
import readline from "node:readline/promises";
import { ChatGroq } from "@langchain/groq";
import { SystemMessage, HumanMessage, trimMessages } from "@langchain/core/messages";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0.6 });

const SYSTEM = new SystemMessage(
  "You are StudyBuddy, a patient tutor. Explain simply, use analogies, and end every " +
  "answer with one short question that checks understanding."
);

let history = [SYSTEM];

// Keep the system message + the most recent messages that fit in a token budget.
const trim = (msgs) =>
  trimMessages(msgs, {
    maxTokens: 800,
    strategy: "last",              // keep the most RECENT messages
    tokenCounter: model,           // ask the model to count accurately
    includeSystem: true,           // never drop the system prompt
    startOn: "human",              // a valid history starts on a human turn
  });

const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
console.log("StudyBuddy ready. Type 'exit' to quit, 'stats' for token info.\n");

while (true) {
  const input = (await rl.question("you › ")).trim();
  if (input === "exit") break;
  if (input === "stats") {
    console.log(`  ${history.length} messages in history\n`);
    continue;
  }

  history.push(new HumanMessage(input));
  history = await trim(history);          // ← keeps cost bounded

  process.stdout.write("bot › ");
  let full;
  for await (const chunk of await model.stream(history)) {
    process.stdout.write(chunk.content);
    full = full ? full.concat(chunk) : chunk;
  }
  console.log(`\n      [${full.usage_metadata?.total_tokens ?? "?"} tokens]\n`);

  history.push(full);                     // ⚠️ remember what the AI said
}
rl.close();
```

Try it: ask a question, then say *"simpler"*, then *"what did I first ask you?"*. Then run 20
turns and watch `stats` — trimming keeps history bounded instead of growing forever.

---

## 5. Code — Python

```bash
pip install langchain langchain-groq langchain-google-genai langchain-ollama python-dotenv
```

### 5.1 Hello, model

```python
# day04_hello.py
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

model = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.7,
    max_tokens=500,
)

res = model.invoke("Explain recursion to a 10-year-old in 3 sentences.")

print(res.text)
print("---")
print("tokens:", res.usage_metadata)
print("finish:", res.response_metadata.get("finish_reason"))
```

> ⚠️ **Python detail:** on some versions `text` is a *property* and on others a *method*.
> If `res.text` prints `<bound method ...>`, call it: `res.text()`. `res.content` always works
> for text-only models.

### 5.2 Message types

> 📦 **Import paths.** This book imports messages from **`langchain_core.messages`** (Python)
> and **`@langchain/core/messages`** (JS). These are the canonical paths and work on both
> LangChain 1.x and 0.3.
>
> LangChain 1.x *also* re-exports them from the top-level package — you'll see
> `from langchain.messages import HumanMessage` in the 1.x docs, and `from "langchain"` in the
> JS docs. Both are correct on 1.x; the `core` paths are correct on more versions, so that's
> what we use. (`initChatModel` is the exception — it genuinely lives in the `langchain` root.)

```python
# day04_messages.py
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

messages = [
    SystemMessage(
        "You are StudyBuddy, a patient tutor. Always answer in exactly two sentences."
    ),
    HumanMessage("What is a variable in programming?"),
    AIMessage("A variable is a labelled box that holds a value. You can change what's inside."),
    HumanMessage("Give me an analogy that isn't a box."),
]

res = model.invoke(messages)
print(res.content)

# The three ways to write the same thing:
model.invoke("hi")                                   # string
model.invoke([{"role": "user", "content": "hi"}])    # dict
model.invoke([("human", "hi")])                      # tuple
```

### 5.3 invoke vs stream vs batch

```python
# day04_three_methods.py
import time
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

# ── INVOKE ───────────────────────────────────────────────────────────────
print("── invoke ──")
print(model.invoke("Name one planet. One word.").content)

# ── STREAM ───────────────────────────────────────────────────────────────
print("\n── stream ──")
t0 = time.time()
first_token_at = None
full = None

for chunk in model.stream("List 5 planets, one per line."):
    if first_token_at is None:
        first_token_at = time.time() - t0
    print(chunk.content, end="", flush=True)
    full = chunk if full is None else full + chunk      # chunks are addable

print(f"\ntime to first token: {first_token_at * 1000:.0f}ms | total: {(time.time() - t0) * 1000:.0f}ms")
print("usage (from accumulated chunks):", full.usage_metadata)

# ── BATCH ────────────────────────────────────────────────────────────────
print("\n── batch ──")
questions = [
    "Capital of Japan? One word.",
    "Capital of France? One word.",
    "Capital of Peru? One word.",
    "Capital of Kenya? One word.",
]

t1 = time.time()
answers = model.batch(questions, config={"max_concurrency": 2})
print([a.content.strip() for a in answers])
print(f"batch of {len(questions)} took {(time.time() - t1) * 1000:.0f}ms")
```

### 5.4 Provider swapping in one line

```python
# day04_providers.py
import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama

load_dotenv()

def get_model(name=None):
    name = name or os.getenv("MODEL_PROVIDER", "groq")
    if name == "groq":
        return ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
    if name == "gemini":
        return ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    if name == "ollama":
        return ChatOllama(model="llama3.2", temperature=0)
    raise ValueError(f"Unknown provider: {name}")

# Identical code path for all three:
for name in ("groq", "gemini", "ollama"):
    try:
        res = get_model(name).invoke("Reply with exactly one word: ready")
        print(f"{name:<8} → {res.content.strip()}")
    except Exception as e:
        print(f"{name:<8} → skipped ({str(e)[:50]})")
```

<details>
<summary>💳 Same thing with OpenAI / Anthropic</summary>

```bash
pip install langchain-openai langchain-anthropic
```
```python
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

if name == "openai":    return ChatOpenAI(model="gpt-4.1", temperature=0)
if name == "anthropic": return ChatAnthropic(model="claude-sonnet-4-5", temperature=0)
```
</details>

### 5.5 The universal loader

```python
# day04_init_chat_model.py
import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

load_dotenv()

# Provider is now a STRING — perfect for env-driven config. (No await in Python.)
model = init_chat_model(
    os.getenv("MODEL", "groq:llama-3.3-70b-versatile"),
    temperature=0,
    max_tokens=200,
)
print(model.invoke("Say READY").content)

# Runtime-configurable: pick the model per call.
flexible = init_chat_model(configurable_fields=["model"])
print(flexible.invoke(
    "Say A",
    config={"configurable": {"model": "groq:llama-3.1-8b-instant"}},
).content)
```

### 5.6 StudyBuddy v0 — a chatbot with real history handling

```python
# day04_studybuddy.py
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, trim_messages

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.6)

SYSTEM = SystemMessage(
    "You are StudyBuddy, a patient tutor. Explain simply, use analogies, and end every "
    "answer with one short question that checks understanding."
)

history = [SYSTEM]

# Keep the system message + the most recent messages that fit in a token budget.
def trim(msgs):
    return trim_messages(
        msgs,
        max_tokens=800,
        strategy="last",             # keep the most RECENT messages
        token_counter=model,         # ask the model to count accurately
        include_system=True,         # never drop the system prompt
        start_on="human",            # a valid history starts on a human turn
    )

print("StudyBuddy ready. Type 'exit' to quit, 'stats' for token info.\n")

while True:
    user_input = input("you › ").strip()
    if user_input == "exit":
        break
    if user_input == "stats":
        print(f"  {len(history)} messages in history\n")
        continue

    history.append(HumanMessage(user_input))
    history = trim(history)                 # ← keeps cost bounded

    print("bot › ", end="", flush=True)
    full = None
    for chunk in model.stream(history):
        print(chunk.content, end="", flush=True)
        full = chunk if full is None else full + chunk

    usage = (full.usage_metadata or {}).get("total_tokens", "?")
    print(f"\n      [{usage} tokens]\n")

    history.append(full)                    # ⚠️ remember what the AI said
```

### 🔁 JS ↔ Python differences you just saw

| | JavaScript | Python |
|---|---|---|
| Params | `maxTokens`, `topP`, `maxRetries` | `max_tokens`, `top_p`, `max_retries` |
| Universal loader | `await initChatModel("groq:...")` | `init_chat_model("groq:...")` — no await |
| Chunk accumulation | `full.concat(chunk)` | `full + chunk` |
| Batch concurrency | `{ maxConcurrency: 2 }` | `config={"max_concurrency": 2}` |
| Message import | `from "@langchain/core/messages"` | `from langchain_core.messages import ...` |
| Trimming | `trimMessages(msgs, {...})` | `trim_messages(msgs, ...)` |
| Text accessor | `res.text` | `res.content` (or `res.text` / `res.text()`) |
| Async variants | none — always async | `ainvoke`, `astream`, `abatch` |

---

## 6. Under the hood

### What `invoke` actually does

```
model.invoke(messages)
        │
        ▼
  1. Coerce input to BaseMessage[]
     "hi" → [HumanMessage("hi")]
     {role:"user"} → HumanMessage
        │
        ▼
  2. Merge config: constructor params + per-call options + runtime config
        │
        ▼
  3. Fire callbacks: on_chat_model_start   ← this is how LangSmith tracing works
        │
        ▼
  4. Translate to the PROVIDER's wire format
     BaseMessage[] → [{role, content}]  (Groq/OpenAI style)
                  → {contents:[{parts}]} (Gemini style)
                  → {system, messages}   (Anthropic — system is separate!)
        │
        ▼
  5. HTTP request, with retry on transient errors (maxRetries)
        │
        ▼
  6. Translate the response BACK into AIMessage
     Normalises content, tool_calls, and token usage across providers
        │
        ▼
  7. Fire callbacks: on_llm_end
        │
        ▼
  8. Return AIMessage
```

**Steps 4 and 6 are the entire value proposition.** Notice Anthropic puts `system` in a
*separate top-level field*, not in the messages array. LangChain hides that. If you swapped
providers by hand, that's the kind of detail that bites you.

### Why `AIMessageChunk` supports `+` / `.concat()`

Streaming produces partial messages. Merging them is fiddly: concatenate `content`, but *merge*
tool-call fragments by index (a tool call's JSON arguments arrive across many chunks), and
take usage from whichever chunk has it.

```js
chunk1: { content: "Hel", tool_calls: [] }
chunk2: { content: "lo",  tool_calls: [] }
chunk3: { content: "",    usage_metadata: { total_tokens: 12 } }

chunk1.concat(chunk2).concat(chunk3)
→ { content: "Hello", usage_metadata: { total_tokens: 12 } }
```

Implementing that correctly for streamed tool calls is genuinely annoying. It's free here.

### What `batch` does that a loop doesn't

```
batch(["a","b","c","d","e"], { maxConcurrency: 2 })

   time →
   ├── a ──┤├── c ──┤├── e ──┤
   ├── b ──┤├── d ──┤

   Not 5 at once (rate limits), not 1 at a time (slow).
   Preserves input order in the output array, regardless of completion order.
```

It also propagates per-item callbacks so tracing works, and (in Python) exposes
`batch_as_completed` if you want results as they finish rather than in order.

### Legacy note

<details>
<summary>📜 Patterns you'll see in old tutorials (and interviews)</summary>

| Legacy (0.x) | Modern (1.x) |
|---|---|
| `from langchain.llms import OpenAI` | `from langchain_openai import ChatOpenAI` |
| `llm("some text")` — callable | `model.invoke("some text")` |
| `llm.predict(...)`, `predict_messages(...)` | `invoke(...)` |
| `LLMChain(llm=..., prompt=...)` | `prompt \| model` (Day 07) |
| Completion models (`text-davinci-003`) | Chat models everywhere |

The important conceptual split: **LLMs** (`BaseLLM`, string → string) vs **Chat models**
(`BaseChatModel`, messages → message). Chat models won; nearly every provider is chat-only now.
An interviewer asking "difference between an LLM and a Chat model in LangChain" wants exactly
this: the input/output types and the fact that chat models understand roles.
</details>

---

## 7. Common mistakes

**❌ Not appending the AI response to history**

```js
history.push(new HumanMessage(input));
const res = await model.invoke(history);
// forgot: history.push(res)
```
The model can't see its own previous answers → it repeats itself and contradicts itself.
✅ Push both sides of every turn.

---

**❌ Using `batch` for a conversation**

```js
await model.batch([turn1, turn2, turn3]);   // three INDEPENDENT calls
```
These run concurrently and share no context. ✅ `batch` = independent inputs only.

---

**❌ Reading `usage_metadata` from the first stream chunk**

```js
for await (const chunk of stream) {
  console.log(chunk.usage_metadata);   // undefined, undefined, undefined... then a value
}
```
✅ Accumulate chunks and read usage from the total.

---

**❌ `res.content.toUpperCase()` on a multimodal model**

`content` can be an array of blocks. ✅ Use `res.text` in JS; in Python use `res.text` or handle
the list form.

---

**❌ camelCase in Python / snake_case in LangChain JS**

```python
ChatGroq(model="...", maxTokens=500)   # ❌ silently ignored or errors
```
✅ `max_tokens` in Python, `maxTokens` in LangChain JS, `max_tokens` in raw SDKs both languages.

---

**❌ Creating a new model instance inside a request handler**

```js
app.post("/chat", async (req, res) => {
  const model = new ChatGroq({ ... });   // new HTTP client per request
});
```
✅ Create once at module scope and reuse — connection pooling matters under load.

---

**❌ Assuming every provider supports every parameter**

`frequency_penalty` doesn't exist on Anthropic; `top_k` doesn't exist on OpenAI. LangChain
passes unknown params through, and the provider may error or silently ignore them.
✅ Check the integration docs when you leave the common set (temperature, max tokens, top_p).

---

## 8. Exercises

### Exercise 1 — Model report card ●○○○○

Write a script that asks the same question to 3 models (two Groq models + Gemini or Ollama) and
prints a table: model, answer, input tokens, output tokens, latency in ms. Which is the best
value for a simple factual question?

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";
import { ChatGoogleGenerativeAI } from "@langchain/google-genai";

const MODELS = {
  "llama-70b": new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 }),
  "llama-8b":  new ChatGroq({ model: "llama-3.1-8b-instant",    temperature: 0 }),
  "gemini":    new ChatGoogleGenerativeAI({ model: "gemini-2.5-flash", temperature: 0 }),
};

const Q = "In one sentence, what causes the seasons on Earth?";

console.log("model      | ms    | in  | out | answer");
console.log("-".repeat(90));

for (const [name, model] of Object.entries(MODELS)) {
  try {
    const t0 = Date.now();
    const res = await model.invoke(Q);
    const ms = Date.now() - t0;
    const u = res.usage_metadata ?? {};
    console.log(
      `${name.padEnd(10)} | ${String(ms).padEnd(5)} | ` +
      `${String(u.input_tokens ?? "?").padEnd(3)} | ${String(u.output_tokens ?? "?").padEnd(3)} | ` +
      res.text.trim().slice(0, 60)
    );
  } catch (e) {
    console.log(`${name.padEnd(10)} | error: ${e.message.slice(0, 60)}`);
  }
}
```

**Python**
```python
import time
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

MODELS = {
    "llama-70b": ChatGroq(model="llama-3.3-70b-versatile", temperature=0),
    "llama-8b":  ChatGroq(model="llama-3.1-8b-instant",    temperature=0),
    "gemini":    ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0),
}

Q = "In one sentence, what causes the seasons on Earth?"

print("model      | ms    | in  | out | answer")
print("-" * 90)

for name, model in MODELS.items():
    try:
        t0 = time.time()
        res = model.invoke(Q)
        ms = int((time.time() - t0) * 1000)
        u = res.usage_metadata or {}
        print(f"{name:<10} | {ms:<5} | {u.get('input_tokens', '?'):<3} | "
              f"{u.get('output_tokens', '?'):<3} | {res.content.strip()[:60]}")
    except Exception as e:
        print(f"{name:<10} | error: {str(e)[:60]}")
```

**What to notice:** the 8B model is often 3–5× faster and just as correct on simple factual
questions. Reflexively reaching for the biggest model is one of the most common ways teams
overspend. Pick the smallest model that passes your eval set (Exercise 5 on Day 02).
</details>

---

### Exercise 2 — Streaming with stats ●●○○○

Build `streamWithStats(model, prompt)` that streams to stdout while measuring: time to first
token, total time, token count, and tokens/second. Compare a 70B and an 8B model — is
time-to-first-token or tokens/sec the bigger difference?

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";

async function streamWithStats(model, prompt, label) {
  const t0 = Date.now();
  let ttft = null, chunks = 0, full;

  process.stdout.write(`\n── ${label} ──\n`);
  for await (const chunk of await model.stream(prompt)) {
    ttft ??= Date.now() - t0;
    chunks++;
    process.stdout.write(chunk.content);
    full = full ? full.concat(chunk) : chunk;
  }

  const total = Date.now() - t0;
  const out = full.usage_metadata?.output_tokens ?? chunks;
  return {
    label,
    ttftMs: ttft,
    totalMs: total,
    outputTokens: out,
    tokensPerSec: +(out / (total / 1000)).toFixed(1),
  };
}

const PROMPT = "Explain how a rainbow forms, in about 120 words.";
const stats = [];
for (const [label, id] of [["70B", "llama-3.3-70b-versatile"], ["8B", "llama-3.1-8b-instant"]]) {
  stats.push(await streamWithStats(new ChatGroq({ model: id, temperature: 0 }), PROMPT, label));
}
console.log("\n");
console.table(stats);
```

**Python**
```python
import time
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

def stream_with_stats(model, prompt, label):
    t0 = time.time()
    ttft, chunks, full = None, 0, None

    print(f"\n── {label} ──")
    for chunk in model.stream(prompt):
        if ttft is None:
            ttft = time.time() - t0
        chunks += 1
        print(chunk.content, end="", flush=True)
        full = chunk if full is None else full + chunk

    total = time.time() - t0
    out = (full.usage_metadata or {}).get("output_tokens", chunks)
    return {
        "label": label,
        "ttft_ms": int(ttft * 1000),
        "total_ms": int(total * 1000),
        "output_tokens": out,
        "tokens_per_sec": round(out / total, 1),
    }

PROMPT = "Explain how a rainbow forms, in about 120 words."
stats = [
    stream_with_stats(ChatGroq(model=mid, temperature=0), PROMPT, label)
    for label, mid in [("70B", "llama-3.3-70b-versatile"), ("8B", "llama-3.1-8b-instant")]
]

print("\n")
for s in stats:
    print(s)
```

**What you'll find:** the 8B model wins hugely on **tokens/sec** but the gap in
**time-to-first-token** is smaller. TTFT is dominated by queueing and prompt processing;
throughput is dominated by model size.

**Why it matters:** for a chat UI, TTFT is what users perceive as "fast". For a batch
summarisation job, throughput is what matters. Optimise the metric your product actually feels.
</details>

---

### Exercise 3 — Fallback chain ●●●○○

Build `resilientModel()` that tries Groq → Gemini → Ollama and returns the first success, using
LangChain's built-in `.withFallbacks()` / `.with_fallbacks()`. Prove it works by giving the
primary model an invalid API key. Then do it *manually* too, and compare the code.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";
import { ChatGoogleGenerativeAI } from "@langchain/google-genai";
import { ChatOllama } from "@langchain/ollama";

// ── The LangChain way ────────────────────────────────────────────────────
const broken = new ChatGroq({ model: "llama-3.3-70b-versatile", apiKey: "gsk_invalid" });

const resilient = broken.withFallbacks([
  new ChatGoogleGenerativeAI({ model: "gemini-2.5-flash" }),
  new ChatOllama({ model: "llama3.2" }),
]);

console.log("built-in  →", (await resilient.invoke("Say READY")).text.trim());

// ── The manual way, for comparison ───────────────────────────────────────
async function manualFallback(models, input) {
  const errors = [];
  for (const m of models) {
    try {
      return await m.invoke(input);
    } catch (e) {
      errors.push(`${m.constructor.name}: ${e.message.slice(0, 40)}`);
    }
  }
  throw new AggregateError([], `All models failed:\n  ${errors.join("\n  ")}`);
}

const res = await manualFallback(
  [broken, new ChatGoogleGenerativeAI({ model: "gemini-2.5-flash" })],
  "Say READY"
);
console.log("manual    →", res.text.trim());
```

**Python**
```python
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama

load_dotenv()

# ── The LangChain way ────────────────────────────────────────────────────
broken = ChatGroq(model="llama-3.3-70b-versatile", api_key="gsk_invalid")

resilient = broken.with_fallbacks([
    ChatGoogleGenerativeAI(model="gemini-2.5-flash"),
    ChatOllama(model="llama3.2"),
])

print("built-in  →", resilient.invoke("Say READY").content.strip())

# ── The manual way, for comparison ───────────────────────────────────────
def manual_fallback(models, user_input):
    errors = []
    for m in models:
        try:
            return m.invoke(user_input)
        except Exception as e:
            errors.append(f"{type(m).__name__}: {str(e)[:40]}")
    raise RuntimeError("All models failed:\n  " + "\n  ".join(errors))

res = manual_fallback(
    [broken, ChatGoogleGenerativeAI(model="gemini-2.5-flash")],
    "Say READY",
)
print("manual    →", res.content.strip())
```

**The real insight:** `.withFallbacks()` returns a **`Runnable`**, so it composes. You can
attach it to a whole chain, not just a model — `(prompt | model | parser).with_fallbacks([...])`
falls back the *entire pipeline*. Your manual version only works on one model call and would
have to be rewritten for every new composition. That's the `Runnable` interface paying rent.

**Production caveat:** fall back across *providers*, not just models, or a single provider
outage takes down every option. And log which fallback fired — silent degradation to a weaker
model is how quality regressions hide.
</details>

---

### Exercise 4 — History strategies compared ●●●○○

Implement three history strategies and compare them over a 12-turn conversation:
1. **Keep all** — send everything
2. **Sliding window** — system + last N messages
3. **`trimMessages` token budget** — system + as many recent messages as fit

For each, print total tokens used across the whole conversation, and test whether the bot can
still answer *"what was the first thing I asked you?"*

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";
import { SystemMessage, HumanMessage, trimMessages } from "@langchain/core/messages";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });
const SYSTEM = new SystemMessage("You are a concise assistant. Answer in one short sentence.");

const TURNS = [
  "My favourite colour is teal.",
  "I have a dog named Pixel.",
  "I live in Lahore.",
  "I'm learning LangChain.",
  "What is 12 * 12?",
  "Name a fruit.",
  "Name a country.",
  "Name a planet.",
  "Name an element.",
  "Name a musical instrument.",
  "Name a programming language.",
  "What was the first thing I told you?",     // ← the memory test
];

const STRATEGIES = {
  keepAll: async (msgs) => msgs,

  window4: async (msgs) => [msgs[0], ...msgs.slice(1).slice(-4)],

  trimmed: async (msgs) =>
    trimMessages(msgs, {
      maxTokens: 300,
      strategy: "last",
      tokenCounter: model,
      includeSystem: true,
      startOn: "human",
    }),
};

for (const [name, strategy] of Object.entries(STRATEGIES)) {
  let history = [SYSTEM];
  let totalTokens = 0;
  let lastAnswer = "";

  for (const turn of TURNS) {
    history.push(new HumanMessage(turn));
    const toSend = await strategy(history);
    const res = await model.invoke(toSend);
    totalTokens += res.usage_metadata?.total_tokens ?? 0;
    history.push(res);
    lastAnswer = res.text.trim();
  }

  const remembered = /teal/i.test(lastAnswer);
  console.log(
    `${name.padEnd(9)} tokens=${String(totalTokens).padEnd(6)} ` +
    `remembered=${remembered ? "✅" : "❌"}  "${lastAnswer.slice(0, 55)}"`
  );
}
```

**Python**
```python
import re
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, trim_messages

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
SYSTEM = SystemMessage("You are a concise assistant. Answer in one short sentence.")

TURNS = [
    "My favourite colour is teal.",
    "I have a dog named Pixel.",
    "I live in Lahore.",
    "I'm learning LangChain.",
    "What is 12 * 12?",
    "Name a fruit.",
    "Name a country.",
    "Name a planet.",
    "Name an element.",
    "Name a musical instrument.",
    "Name a programming language.",
    "What was the first thing I told you?",     # ← the memory test
]

STRATEGIES = {
    "keepAll": lambda msgs: msgs,
    "window4": lambda msgs: [msgs[0]] + msgs[1:][-4:],
    "trimmed": lambda msgs: trim_messages(
        msgs, max_tokens=300, strategy="last",
        token_counter=model, include_system=True, start_on="human",
    ),
}

for name, strategy in STRATEGIES.items():
    history = [SYSTEM]
    total_tokens = 0
    last_answer = ""

    for turn in TURNS:
        history.append(HumanMessage(turn))
        res = model.invoke(strategy(history))
        total_tokens += (res.usage_metadata or {}).get("total_tokens", 0)
        history.append(res)
        last_answer = res.content.strip()

    remembered = bool(re.search("teal", last_answer, re.I))
    print(f"{name:<9} tokens={total_tokens:<6} "
          f"remembered={'✅' if remembered else '❌'}  \"{last_answer[:55]}\"")
```

**Typical result:**

| Strategy | Tokens | Remembered "teal"? |
|---|---|---|
| keepAll | ~4,800 | ✅ |
| window4 | ~1,900 | ❌ |
| trimmed | ~2,600 | ❌ or ✅ (borderline) |

**The lesson — and it's the whole reason Day 14 and Day 20 exist:** trimming trades memory for
cost, and there is no window size that's both cheap and remembers everything. The real fix
isn't a better trimming rule; it's a *different mechanism* — summarise old turns into a running
summary, or store facts in a vector store / long-term memory and retrieve the relevant ones.
Both are Week 2/3 topics. You've now felt exactly why they're needed.
</details>

---

### Exercise 5 — StudyBuddy v0.5 ●●●●○

Upgrade the StudyBuddy chatbot with: (a) a `/level <beginner|intermediate|expert>` command that
rewrites the system message, (b) `/model <groq|gemini|ollama>` to hot-swap providers mid-chat
with history intact, (c) a `/cost` command showing cumulative tokens and estimated USD,
(d) graceful error handling that doesn't crash the loop.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
// studybuddy-v05.js
import "dotenv/config";
import readline from "node:readline/promises";
import { ChatGroq } from "@langchain/groq";
import { ChatGoogleGenerativeAI } from "@langchain/google-genai";
import { ChatOllama } from "@langchain/ollama";
import { SystemMessage, HumanMessage, trimMessages } from "@langchain/core/messages";

// Rough public rates per 1M tokens (USD). Update for your provider.
const PRICING = {
  groq:   { in: 0.59, out: 0.79 },
  gemini: { in: 0.075, out: 0.30 },
  ollama: { in: 0, out: 0 },
};

const LEVELS = {
  beginner:     "Explain like the user is 12. Use everyday analogies. No jargon.",
  intermediate: "Explain like the user is a junior developer. Some jargon is fine; define it.",
  expert:       "Explain like the user is a senior engineer. Be dense and precise. Skip basics.",
};

const makeModel = (name) => ({
  groq:   () => new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0.6 }),
  gemini: () => new ChatGoogleGenerativeAI({ model: "gemini-2.5-flash", temperature: 0.6 }),
  ollama: () => new ChatOllama({ model: "llama3.2", temperature: 0.6 }),
}[name]());

let providerName = "groq";
let model = makeModel(providerName);
let level = "beginner";
let history = [];
const usage = { in: 0, out: 0 };

const systemFor = (lvl) =>
  new SystemMessage(
    `You are StudyBuddy, a patient tutor. ${LEVELS[lvl]} ` +
    "End every answer with one short question that checks understanding."
  );

const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
console.log("StudyBuddy v0.5 — /level /model /cost /reset /exit\n");

while (true) {
  let input;
  try {
    input = (await rl.question(`you [${level}|${providerName}] › `)).trim();
  } catch { break; }

  if (!input) continue;

  // ── commands ──────────────────────────────────────────────────────────
  if (input === "/exit") break;

  if (input === "/reset") {
    history = [];
    console.log("  history cleared\n");
    continue;
  }

  if (input.startsWith("/level")) {
    const next = input.split(/\s+/)[1];
    if (!LEVELS[next]) { console.log(`  levels: ${Object.keys(LEVELS).join(", ")}\n`); continue; }
    level = next;
    console.log(`  level → ${level}\n`);
    continue;
  }

  if (input.startsWith("/model")) {
    const next = input.split(/\s+/)[1];
    try {
      model = makeModel(next);
      providerName = next;
      console.log(`  provider → ${next} (history kept: ${history.length} messages)\n`);
    } catch {
      console.log("  models: groq, gemini, ollama\n");
    }
    continue;
  }

  if (input === "/cost") {
    const p = PRICING[providerName];
    const usd = (usage.in / 1e6) * p.in + (usage.out / 1e6) * p.out;
    console.log(`  in=${usage.in} out=${usage.out} ≈ $${usd.toFixed(5)}\n`);
    continue;
  }

  // ── chat turn ─────────────────────────────────────────────────────────
  history.push(new HumanMessage(input));

  // System message is rebuilt every turn so /level takes effect immediately.
  let toSend = [systemFor(level), ...history];
  toSend = await trimMessages(toSend, {
    maxTokens: 1000, strategy: "last", tokenCounter: model,
    includeSystem: true, startOn: "human",
  });

  try {
    process.stdout.write("bot › ");
    let full;
    for await (const chunk of await model.stream(toSend)) {
      process.stdout.write(chunk.content);
      full = full ? full.concat(chunk) : chunk;
    }
    console.log("\n");

    history.push(full);
    usage.in  += full.usage_metadata?.input_tokens  ?? 0;
    usage.out += full.usage_metadata?.output_tokens ?? 0;
  } catch (err) {
    console.log(`\n  ⚠️ ${err.message.slice(0, 100)}`);
    console.log("  (try /model gemini to switch providers)\n");
    history.pop();               // ⚠️ don't leave an unanswered human message in history
  }
}
rl.close();
```

**Python**
```python
# studybuddy_v05.py
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage, trim_messages

load_dotenv()

# Rough public rates per 1M tokens (USD). Update for your provider.
PRICING = {
    "groq":   {"in": 0.59,  "out": 0.79},
    "gemini": {"in": 0.075, "out": 0.30},
    "ollama": {"in": 0.0,   "out": 0.0},
}

LEVELS = {
    "beginner":     "Explain like the user is 12. Use everyday analogies. No jargon.",
    "intermediate": "Explain like the user is a junior developer. Some jargon is fine; define it.",
    "expert":       "Explain like the user is a senior engineer. Be dense and precise. Skip basics.",
}

def make_model(name):
    return {
        "groq":   lambda: ChatGroq(model="llama-3.3-70b-versatile", temperature=0.6),
        "gemini": lambda: ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.6),
        "ollama": lambda: ChatOllama(model="llama3.2", temperature=0.6),
    }[name]()

provider_name = "groq"
model = make_model(provider_name)
level = "beginner"
history = []
usage = {"in": 0, "out": 0}

def system_for(lvl):
    return SystemMessage(
        f"You are StudyBuddy, a patient tutor. {LEVELS[lvl]} "
        "End every answer with one short question that checks understanding."
    )

print("StudyBuddy v0.5 — /level /model /cost /reset /exit\n")

while True:
    try:
        user_input = input(f"you [{level}|{provider_name}] › ").strip()
    except (EOFError, KeyboardInterrupt):
        break

    if not user_input:
        continue

    # ── commands ──────────────────────────────────────────────────────────
    if user_input == "/exit":
        break

    if user_input == "/reset":
        history = []
        print("  history cleared\n")
        continue

    if user_input.startswith("/level"):
        parts = user_input.split()
        nxt = parts[1] if len(parts) > 1 else None
        if nxt not in LEVELS:
            print(f"  levels: {', '.join(LEVELS)}\n")
            continue
        level = nxt
        print(f"  level → {level}\n")
        continue

    if user_input.startswith("/model"):
        parts = user_input.split()
        nxt = parts[1] if len(parts) > 1 else None
        try:
            model = make_model(nxt)
            provider_name = nxt
            print(f"  provider → {nxt} (history kept: {len(history)} messages)\n")
        except KeyError:
            print("  models: groq, gemini, ollama\n")
        continue

    if user_input == "/cost":
        p = PRICING[provider_name]
        usd = usage["in"] / 1e6 * p["in"] + usage["out"] / 1e6 * p["out"]
        print(f"  in={usage['in']} out={usage['out']} ≈ ${usd:.5f}\n")
        continue

    # ── chat turn ─────────────────────────────────────────────────────────
    history.append(HumanMessage(user_input))

    # System message is rebuilt every turn so /level takes effect immediately.
    to_send = trim_messages(
        [system_for(level)] + history,
        max_tokens=1000, strategy="last", token_counter=model,
        include_system=True, start_on="human",
    )

    try:
        print("bot › ", end="", flush=True)
        full = None
        for chunk in model.stream(to_send):
            print(chunk.content, end="", flush=True)
            full = chunk if full is None else full + chunk
        print("\n")

        history.append(full)
        u = full.usage_metadata or {}
        usage["in"] += u.get("input_tokens", 0)
        usage["out"] += u.get("output_tokens", 0)
    except Exception as err:
        print(f"\n  ⚠️ {str(err)[:100]}")
        print("  (try /model gemini to switch providers)\n")
        history.pop()            # ⚠️ don't leave an unanswered human message in history
```

**Three design points worth internalising:**

1. **Provider swapping works mid-conversation with history intact.** That's only possible
   because `BaseMessage` is provider-neutral. Try that with raw SDKs and you'd be rewriting the
   whole history into a different shape.
2. **The system message is rebuilt every turn** rather than stored in `history`. Prompt state
   and conversation state are different things — conflating them is why `/level` would
   otherwise need a history rewrite.
3. **`history.pop()` on error.** If the call fails, the user's message is still in history with
   no answer after it. Next turn you'd send two consecutive human messages, which some providers
   reject outright. Small detail; real production bug.
</details>

---

## 9. Interview questions

### Basic

<details>
<summary><b>Q: Difference between `invoke`, `stream` and `batch`?</b></summary>

`invoke` sends one input and returns one complete `AIMessage`. `stream` sends one input and
returns an async iterator of `AIMessageChunk`s as they're generated — same total time, much
better perceived latency. `batch` sends *multiple independent* inputs concurrently (with a
configurable concurrency cap) and returns results in input order. Use `batch` only for
independent inputs — never for conversation turns, which are sequentially dependent.
</details>

<details>
<summary><b>Q: What are the message types and when do you use each?</b></summary>

- **SystemMessage** — instructions/persona/constraints. Usually exactly one, at the front.
- **HumanMessage** — user input.
- **AIMessage** — model output; also carries `tool_calls` when the model requests a tool.
- **ToolMessage** — the *result* of executing a tool, linked back by `tool_call_id`.

A conversation is an ordered array of these. The role is rendered into provider-specific
formatting tokens at request time.
</details>

<details>
<summary><b>Q: Difference between an LLM and a Chat model in LangChain?</b></summary>

An LLM (`BaseLLM`) takes a string and returns a string — the old completion-model interface.
A Chat model (`BaseChatModel`) takes a **list of messages** and returns an `AIMessage`, so it
understands roles, tool calls and multimodal content. Nearly every modern provider is chat-only;
chat models are what you should use. LLM-style classes remain mostly for legacy compatibility.
</details>

<details>
<summary><b>Q: How do you count tokens for a request?</b></summary>

Read `usage_metadata` on the response — `{ input_tokens, output_tokens, total_tokens }`,
normalised across providers. When streaming, usage arrives in the **final** chunk, so accumulate
chunks (`concat` / `+`) and read it from the total. To count *before* sending, use
`getNumTokens` / `get_num_tokens` on the model, or the provider's tokenizer directly.
</details>

### Intermediate

<details>
<summary><b>Q: Why do `AIMessageChunk`s support addition?</b></summary>

Because reassembling a streamed response is non-trivial: text content concatenates, but tool
calls arrive as *fragments* that must be merged by index (a single tool call's JSON arguments
are split across many chunks), and usage metadata appears only in the final chunk. Making
chunks addable puts that merge logic in one tested place, so `full = full.concat(chunk)` gives
you a correct complete message including assembled tool calls.
</details>

<details>
<summary><b>Q: How does LangChain make providers interchangeable when their APIs differ so much?</b></summary>

Each integration package implements `BaseChatModel` with two translation layers: outbound,
converting `BaseMessage[]` into that provider's wire format (Anthropic takes `system` as a
separate top-level field, Gemini uses `contents`/`parts`, OpenAI-style uses a flat `messages`
array); and inbound, normalising the response into `AIMessage` with consistent `content`,
`tool_calls` and `usage_metadata`. Your code only ever sees the normalised types, so provider
choice stops leaking into call sites. The trade-off is that provider-specific features need
either explicit support or an escape hatch (`modelKwargs` / `model_kwargs`).
</details>

<details>
<summary><b>Q: What is `initChatModel` / `init_chat_model` and when would you use it?</b></summary>

A universal factory that takes a `"provider:model"` string and returns the right chat model,
lazily importing the integration package. Use it when the provider should be *configuration*
rather than code — e.g. `MODEL=groq:llama-3.3-70b-versatile` in env, so ops can switch models
without a deploy. It also supports `configurableFields`, letting you pick the model per call at
runtime. Use the direct class when you need provider-specific constructor options or want the
dependency to be explicit. Note the JS version is awaited; the Python one isn't.
</details>

<details>
<summary><b>Q: How would you implement conversation memory with just a chat model?</b></summary>

Keep an array of messages; append the `HumanMessage` before each call and the returned
`AIMessage` after. Send the whole array each turn. Then bound it, because cost is O(n²) over a
conversation: a sliding window, or `trimMessages`/`trim_messages` with a token budget that
preserves the system message and starts on a human turn.

The important caveat: trimming *loses* information — no window size is both cheap and
remembers everything. The real solutions are summarising older turns into a rolling summary, or
storing facts externally and retrieving the relevant ones. Persisting across sessions needs a
store — which is what LangGraph checkpointers provide.
</details>

### Advanced

<details>
<summary><b>Q: Walk through everything that happens between `model.invoke(messages)` and the response.</b></summary>

1. **Input coercion** — strings/dicts/tuples normalised to `BaseMessage[]`.
2. **Config resolution** — constructor params merged with per-call options and runtime config
   (callbacks, tags, metadata, concurrency).
3. **Callback dispatch** — `on_chat_model_start` fires; this is the hook LangSmith tracing uses.
4. **Outbound translation** — messages converted to the provider's wire format, including
   provider quirks (system-as-separate-field, content-block shapes, tool schema format).
5. **HTTP request** — with the client's timeout and automatic retries on transient errors.
6. **Inbound translation** — provider response normalised into `AIMessage`: content, assembled
   `tool_calls`, `usage_metadata`, `response_metadata`.
7. **Callback dispatch** — `on_llm_end` (or `on_llm_error`).
8. **Return.**

Steps 4 and 6 are where the abstraction earns its keep; step 3/7 are why tracing works without
you instrumenting anything.
</details>

<details>
<summary><b>Q: Design a model layer for a product serving 3 tiers: free, pro, enterprise.</b></summary>

**Routing by tier** — free gets a small fast model (8B), pro gets a mid-tier, enterprise gets
the frontier model plus a dedicated-capacity provider. Implement as a factory keyed by tier so
the choice lives in one place.

**Reliability** — every tier gets `.withFallbacks()` across *providers*, not just models, so one
provider outage doesn't take you down. Log every fallback: silent degradation to a weaker model
is how quality regressions hide.

**Cost control** — per-tenant token budgets tracked from `usage_metadata`; a hard cap that
returns a friendly error rather than a surprise bill. Cache identical requests. Trim history
aggressively on free tier, generously on enterprise.

**Latency** — stream everywhere for perceived speed. Route by task, not just tier: even
enterprise should use the 8B model for classification and routing, reserving the big model for
generation. Most overspending comes from using one big model for everything.

**Observability** — tags/metadata on every call (`tenant`, `tier`, `feature`) so you can slice
cost and quality per segment in LangSmith.

**Configurability** — model IDs in env/config, not code, so you can shift traffic during an
incident without a deploy. `initChatModel` with `configurableFields` fits this well.
</details>

<details>
<summary><b>Q: Your streaming endpoint shows the first token after 4 seconds. How do you debug it?</b></summary>

Separate the three contributors:

1. **Your server's pre-model work** — instrument the time from request receipt to the first
   `on_chat_model_start` callback. If retrieval or auth is slow, the model isn't the problem.
2. **Provider queue + prompt processing (TTFT)** — measure time from request sent to first
   chunk. If the prompt is huge (long history, many retrieved chunks, big tool schemas), prompt
   processing dominates: trim history, retrieve fewer chunks, prune unused tools.
3. **Your transport** — a buffering proxy, compression, or a framework that batches the
   response will hide chunks that already arrived. Verify with `curl -N` directly against the
   provider vs against your endpoint. Check `Cache-Control: no-transform` and disable buffering
   for SSE.

Common real causes, in the order I'd check: response buffering in the reverse proxy; awaiting
the *whole* response server-side then re-emitting it; a large prompt; and a cold model.
Fixes: stream end-to-end (never `await` the full response), shrink the prompt, use a smaller
model for the first-response path, and send an early keepalive so the connection opens fast.
</details>

---

## 10. Recap

- ✅ `new ChatGroq({...})` for explicit control; `initChatModel("groq:...")` when the provider is config
- ✅ JS is camelCase, Python is snake_case; JS is async-only, Python has `a`-prefixed async twins
- ✅ `invoke` (one), `stream` (chunks), `batch` (many independent, with concurrency control)
- ✅ Four message types: System, Human, AI, Tool — a conversation is an ordered array of them
- ✅ `AIMessage` gives `.text`, `.tool_calls`, `.usage_metadata`, `.response_metadata`
- ✅ Stream chunks are addable; usage arrives in the final chunk
- ✅ Memory = re-sending history; `trimMessages` bounds the cost but loses information
- ✅ Swapping providers is one line — that isolation is the point, not the brevity

### Tomorrow

**[Day 05 — Prompts and templates](day-05-prompts-and-templates.md)**: right now your prompts
are string concatenation, which breaks the moment you need variables, few-shot examples, or a
history placeholder. `PromptTemplate`, `ChatPromptTemplate`, `MessagesPlaceholder` and few-shot
templates fix that — and they're `Runnable`s, which sets up Day 07's LCEL.

### Quick self-check

1. Why can't you use `batch` for a multi-turn conversation?
2. You're streaming and `chunk.usage_metadata` is `undefined`. Bug or expected?
3. What's the one-line change to move a whole app from Groq to Gemini, and why does it work?

<details>
<summary>Answers</summary>

1. `batch` runs inputs concurrently and independently — no shared context. Conversation turns
   are sequentially dependent: turn 2 needs turn 1's answer in its input.
2. Expected. Token usage arrives in the final chunk. Accumulate chunks with `concat`/`+` and
   read `usage_metadata` from the total.
3. Swap the model constructor (`new ChatGroq(...)` → `new ChatGoogleGenerativeAI(...)`). It
   works because every chat model implements `BaseChatModel`: same input types
   (`BaseMessage[]`), same output type (`AIMessage`), same methods. The provider's wire-format
   differences are handled inside the integration package.
</details>
