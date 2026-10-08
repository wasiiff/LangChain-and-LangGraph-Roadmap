# Day 04 — LangChain Models: invoke, stream, batch & Message Types

> ⏱ **Time:** ~2.5 hours · 🎯 **Prereqs:** [Day 03](day-03-choosing-a-model-and-why-langchain.md) · 🧩 **Difficulty:** ●●○○○

**Today you learn:** every provider has its own request and response shape, so moving from Groq
to Gemini means rewriting your code. Today you write your first real LangChain code: one
chat-model interface, with the same settings and methods for every provider. You call it with
`invoke` / `stream` / `batch`, use the four message types, read token usage and swap providers in
one line. Then you build StudyBuddy v0, a chatbot that keeps and trims its own history.

> 📖 **Words you'll meet today**
>
> - **Chat model** — a model that takes a list of messages with roles and replies with one message.
> - **Provider** — the company or tool that runs the model for you, such as Groq, Gemini or Ollama.
> - **Message types** — labels for who is speaking: system (instructions), human, AI, or tool.
> - **invoke / stream / batch** — get one full answer; get it in pieces as it is written; send
>   many unrelated inputs at once.
> - **Stream chunk** — one small piece of a streamed answer. Chunks add together into the full
>   message.
> - **Token usage** — how many tokens a request read and wrote. It decides the cost.
> - **Concurrency** — running several requests at the same time instead of one after another.
> - **Trimming** — dropping older messages so each request stays within a token budget.

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

Now imagine you built a summariser on Groq. Your product manager asks: *"can we try Gemini? It's
cheaper at our volume."* So you change every place you call the model, every line that reads a
response, every streaming loop and every tool-calling block.

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

> 💬 **In plain words:** you can build a model from its own class, or from a "provider:model"
> string. Use the string when you want to change models through config instead of code.

**Direct class** — explicit, gives you provider-specific options:

```js
import { ChatGroq } from "@langchain/groq";
const model = new ChatGroq({ model: "openai/gpt-oss-120b" });
```

**`initChatModel` / `init_chat_model`** — the universal loader. Provider becomes a string:

```js
import { initChatModel } from "langchain";
const model = await initChatModel("groq:openai/gpt-oss-120b");
```

Use the direct class when you want provider-specific parameters or clarity. Use the universal
loader when the provider should be **configuration**. For example, read it from an environment
variable, so the operations team can switch models without a new deploy.

> ⚠️ **JS gotcha:** `initChatModel` is `await`ed, because it loads the provider package only when
> it is needed (a "lazy" import). Python's `init_chat_model` is not.

Groq's model id contains a slash. That is fine. In `"groq:openai/gpt-oss-120b"`, the part
before the first colon is the provider (`groq`). The rest is Groq's own model id. Both loaders
handled it in our runs (§4.5 and §5.5).

> 📦 **Model names change — checked 7 October 2026.** This course was checked against Groq's
> model list on 7 October 2026. If a name 404s, open
> [console.groq.com/docs/models](https://console.groq.com/docs/models) and pick a current
> production model. It has already happened once. The course's old default now fails like this:
>
> ```
> 404 The model `llama-3.3-70b-versatile` does not exist or you do not have access to it.
> ```
>
> The error code is `model_not_found`. So every example moved to **`openai/gpt-oss-120b`**,
> and the small model to **`openai/gpt-oss-20b`**.
> [Day 03 §3.11](day-03-choosing-a-model-and-why-langchain.md) tells the story. Keep model
> names in config, not scattered through your code.

### 3.2 The constructor parameters — every one explained

> 💬 **In plain words:** these are the settings you can give a model when you create it. Only
> the model name is required; the rest control randomness, length, retries and tracing.

```js
new ChatGroq({
  // ─── Identity ──────────────────────────────────────────────────────────
  model: "openai/gpt-oss-120b",      // REQUIRED. Which model.
  apiKey: process.env.GROQ_API_KEY,  // Optional — read from env by convention.

  // ─── Sampling (see Day 01) ─────────────────────────────────────────────
  temperature: 0.7,      // 0–2. Randomness. 0 for extraction, 0.7 for chat.
  topP: 1,               // Nucleus sampling. Tune this OR temperature.
  maxTokens: 1024,       // Cap on OUTPUT tokens, hidden reasoning included (§3.9).
  stop: ["\n\n"],        // Stop sequences. Generation halts before these.

  // ─── Reasoning models only (§3.9) ──────────────────────────────────────
  reasoningEffort: "low", // How hard to "think" first. "low" = fewer hidden tokens.

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

**Naming reminder from Day 01:** LangChain **JS uses camelCase** (`maxTokens`,
`reasoningEffort`), LangChain **Python uses snake_case** (`max_tokens`, `reasoning_effort`).
The raw provider SDKs use snake_case in both.

### 3.3 The three core methods

> 💬 **In plain words:** use `invoke` for one answer, `stream` to show the answer as it is
> written, and `batch` to send many unrelated questions at once.

| Method | Input | Output | Use when |
|---|---|---|---|
| `invoke` | one input | one `AIMessage` | Normal single request |
| `stream` | one input | async iterator of chunks | You want tokens as they arrive |
| `batch` | array of inputs | array of `AIMessage` | Many **independent** inputs |

**`batch` is not just a loop.** It runs requests at the same time, up to a concurrency limit
you set. So you get parallelism without writing your own `Promise.all` plus a semaphore, as you
did on [Day 0B](../week-00-start-here/day-00b-programming-for-ai.md).

```js
// These are equivalent in result, but batch handles concurrency for you:
await model.batch(["a", "b", "c"], { maxConcurrency: 2 });
```

> ⚠️ `batch` is for **independent** inputs. A conversation is not independent — each turn
> depends on the last. Never use `batch` for chat turns.

### 3.4 What `invoke` accepts

> 💬 **In plain words:** you can pass a plain string, plain objects, message classes or
> role-and-text pairs. They all become the same list of messages.

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

A bare string is a shortcut ("syntactic sugar") for `[new HumanMessage(str)]`. Use message
classes when you need type safety, tool calls, or multimodal content (images or audio as well
as text). Use plain objects for quick scripts.

### 3.5 What you get back: `AIMessage`

> 💬 **In plain words:** every call gives back an `AIMessage`. Read the reply from `.text`,
> which is always a string.

```js
const res = await model.invoke("Say hello");

res.content            // "Hello!" — string, OR an array of content blocks (multimodal)
res.text                // always a string, even when content is blocks ← prefer this
res.tool_calls          // [] or [{ name, args, id }]  (Day 15)
res.usage_metadata      // { input_tokens, output_tokens, total_tokens }
res.response_metadata   // provider-specific: finish_reason and other details
res.id                  // message id
```

> 🔑 **Prefer `.text` over `.content`.** With multimodal models `content` can be an *array* of
> blocks (`[{type:"text",...}, {type:"image",...}]`), so `res.content.toUpperCase()` crashes.
> `.text` always gives you the concatenated text.

### 3.6 Streaming

> 💬 **In plain words:** streaming hands you the answer in small pieces. Add the pieces together
> to get the full message and its token counts.

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

> ⚠️ **JS with Groq (checked October 2026):** with `@langchain/groq` 1.3.1, streamed chunks
> carry **no** `usage_metadata` at all, not even the last one. The counts are in
> `full.response_metadata.usage` instead. There, `input_tokens` and `output_tokens` were right,
> but `total_tokens` came out doubled, because two chunks carry it and `concat` adds them up.
> Python's `ChatGroq` fills `usage_metadata` normally. So the JS code in §4 reads
> `full.usage_metadata ?? full.response_metadata.usage` and adds input and output itself.

### 3.7 Memory = re-sending history (Day 01, now with types)

> 💬 **In plain words:** the model remembers nothing between calls. You give it memory by sending
> the whole conversation every time, including its own replies.

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
2. **Never trimming.** Turn 50 sends 50 turns of tokens. See section 4.6.

### 3.8 Swapping providers

> 💬 **In plain words:** every model has the same methods and returns the same message type. So
> changing provider means changing only the line that creates the model.

```js
const model =
  provider === "groq"   ? new ChatGroq({ model: "openai/gpt-oss-120b" }) :
  provider === "gemini" ? new ChatGoogleGenerativeAI({ model: "gemini-3.8-flash" }) :
                          new ChatOllama({ model: "llama3.2" });

// EVERYTHING downstream is identical.
await model.invoke(history);
```

**This is the payoff.** Not "less code" but *isolation*: the choice of provider no longer
spreads into every file.

### 3.9 Reasoning models: the parameters that surprise you

> 💬 **In plain words:** GPT-OSS models "think" in hidden tokens before they answer. Those hidden
> tokens count against your limits and your bill, and a few old parameters no longer work.

Both Groq models in this course are **reasoning models**
([Day 03 §3.4](day-03-choosing-a-model-and-why-langchain.md)). Before the visible answer, they
write hidden "thinking" tokens. You never see them in `.text`,
but they are output tokens. That changes four things. We ran the same question, "What is
2+2? Answer with the number only.", against `openai/gpt-oss-120b` (§4.7 and §5.7):

| Setting | Visible answer | Output tokens | `finish_reason` |
|---|---|---|---|
| `maxTokens: 20` / `max_tokens=20` | `""` — **empty** | 20 | `length` |
| default | `"4"` | 46 (JS run), 47 (Python run) | `stop` |
| `reasoningEffort: "low"` / `reasoning_effort="low"` | `"4"` | 16 | `stop` |

**1. A small `maxTokens` can return nothing.** The limit covers thinking **and** answer. With
20 tokens, the model spent them all on thinking. It returned an empty string with
`finish_reason: "length"`, and no error. On a reasoning model, keep `maxTokens` generous (512
or more) and control length in the prompt instead.

**2. `reasoningEffort` controls the thinking.** `"low"` cut this answer from 46 output tokens to
16. That is cheaper and faster. Use it for simple jobs, and keep the default for hard ones.

**3. Where the thinking shows up depends on the language.**

| | JavaScript (`@langchain/groq` 1.3.1) | Python (`langchain-groq` 1.1.3) |
|---|---|---|
| The thinking text | not exposed | `res.additional_kwargs["reasoning_content"]` |
| The thinking token count | not exposed | `res.usage_metadata["output_token_details"]["reasoning"]` |

In our Python run with low effort, the thinking text was `'Just answer 4.'` and it used 6
tokens. In JS, `additional_kwargs` held only `tool_calls`, and `usage_metadata` had no
reasoning details. If you need the thinking in JS, call the raw `groq-sdk`, where it is
`message.reasoning`.

**4. Some parameters are rejected.** Current Groq models refuse two settings that older
tutorials use:

```
logprobs: true  →  400 `logprobs` is not supported with this model
n: 2            →  400 'n' : number must be at most 1
```

`logprobs` asks for the probability of each token (Day 01). Some other providers (for example
OpenAI) support it; Groq's current models do not. `n` asks for several answers to one prompt.
To get several answers here, use `batch` with the same input repeated, or a loop.

One more effect appears when you stream. The first chunks of a reasoning model carry no visible
text. In one JS run, 29 of 41 chunks had empty `content`. So a "time to first token" timer must
start counting at the first chunk **with text**, as §4.3 does.

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
  model: "openai/gpt-oss-120b",
  temperature: 0.7,
  maxTokens: 500,       // generous: hidden reasoning counts too (§3.9)
});

const res = await model.invoke("Explain recursion to a 10-year-old in 3 sentences.");

console.log(res.text);
console.log("---");
console.log("tokens:", res.usage_metadata);
console.log("finish:", res.response_metadata.finish_reason);
```

Output from a real run (October 2026 — your wording will differ):

```
Recursion is like a story that tells itself a smaller version of the same story over and over until it reaches a simple ending. Imagine a set of Russian nesting dolls: each doll opens to reveal a smaller doll inside, and you keep opening them until you get to the tiniest one that can’t be opened any more. In programming, a recursive function works the same way—it calls itself with a smaller problem until it hits a base case that stops the repeating.
---
tokens: { input_tokens: 84, output_tokens: 151, total_tokens: 235 }
finish: stop
```

Two numbers are worth a second look. The question has 13 words, but it was billed as 84 input
tokens, because the provider wraps every message in its own formatting. And 151 output tokens
is more than three sentences need: part of it is hidden thinking (§3.9). The Python run in §5.1
shows how much.

### 4.2 Message types

```js
// day04-messages.js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";
import { SystemMessage, HumanMessage, AIMessage } from "@langchain/core/messages";

const model = new ChatGroq({ model: "openai/gpt-oss-120b", temperature: 0 });

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

const model = new ChatGroq({ model: "openai/gpt-oss-120b", temperature: 0 });

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
  if (chunk.content) firstTokenAt ??= Date.now() - t0;   // first VISIBLE token (§3.9)
  process.stdout.write(chunk.content);
  full = full ? full.concat(chunk) : chunk;      // chunks are addable
}

console.log(`\ntime to first token: ${firstTokenAt}ms | total: ${Date.now() - t0}ms`);
// @langchain/groq 1.3.1 puts streamed counts in response_metadata.usage (§3.6)
const u = full.usage_metadata ?? full.response_metadata.usage;
console.log("usage (from accumulated chunks):", { input: u.input_tokens, output: u.output_tokens });

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

Output from a real run (October 2026 — timings change on every run):

```
── invoke ──
Mars

── stream ──
Mercury  
Venus  
Earth  
Mars  
Jupiter
time to first token: 399ms | total: 427ms
usage (from accumulated chunks): { input: 80, output: 52 }

── batch ──
[ 'Tokyo', 'Paris', 'Lima.', 'Nairobi' ]
batch of 4 took 1232ms
```

The usage line needed the `response_metadata.usage` fallback from §3.6. With plain
`full.usage_metadata`, the same run printed `undefined`.

### 4.4 Provider swapping in one line

```js
// day04-providers.js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";
import { ChatGoogleGenerativeAI } from "@langchain/google-genai";
import { ChatOllama } from "@langchain/ollama";

function getModel(name = process.env.MODEL_PROVIDER ?? "groq") {
  switch (name) {
    case "groq":   return new ChatGroq({ model: "openai/gpt-oss-120b", temperature: 0 });
    case "gemini": return new ChatGoogleGenerativeAI({ model: "gemini-3.8-flash", temperature: 0 });
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

Output from our run (October 2026), with no Ollama server running and a busy Gemini key:

```
groq     → ready
gemini   → skipped ([GoogleGenerativeAI Error]: Error fetching from ht)
ollama   → skipped (fetch failed)
```

The 50-character cut hides the reason. The full Gemini message was
`[429 Too Many Requests] You exceeded your current quota, please check your plan and billing
details.` Every provider failed in its own way, but the same `try` / `catch` handled all three.
That is the abstraction again.

> ⚠️ **Gemini: busy models and changing names.** `gemini-3.8-flash` is the current Flash model
> for new keys (checked 7 October 2026). Google answers older Flash names with a 404 that says
> the model is "no longer available to new users". A busy model can also fail with
> `503 This model is currently experiencing high demand`, and a free key that has used its quota
> gets the `429` above. The JS client retries these by default, so our Gemini call took over two
> minutes before it gave up. Retry later, or fall back to another provider (Exercise 3 here, and
> Day 24).

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
const model = await initChatModel(process.env.MODEL ?? "groq:openai/gpt-oss-120b", {
  temperature: 0,
  maxTokens: 512,       // not 200: hidden reasoning counts toward the cap (§3.9)
});

console.log((await model.invoke("Say READY")).text);

// Runtime-configurable: pick the model per call.
// JS needs a default model and the provider up front (see the warning below).
const flexible = await initChatModel("openai/gpt-oss-120b", {
  modelProvider: "groq",
  configurableFields: ["model"],
});
console.log((await flexible.invoke("Say A", {
  configurable: { model: "openai/gpt-oss-20b" },   // a plain model id, no "groq:" prefix
})).text);
```

Output from a real run:

```
READY
A
```

> ⚠️ **JS trap (`langchain` 1.5.15):** older examples write
> `initChatModel(undefined, { configurableFields: ["model"] })`. That line now throws at once:
> `TypeError: Cannot read properties of undefined (reading 'startsWith')`, because JS builds
> the default model straight away and there is no name to read. Give it a default model and a
> `modelProvider`, as above. And per call, JS wants the plain id: `"groq:openai/gpt-oss-20b"`
> there was sent to Groq unchanged, and Groq answered with a 404: that model "does not exist".
> Python's `init_chat_model(configurable_fields=["model"])` has neither
> problem, and it accepts `"groq:openai/gpt-oss-20b"` per call (§5.5).

### 4.6 StudyBuddy v0 — a chatbot with real history handling

```js
// day04-studybuddy.js
import "dotenv/config";
import readline from "node:readline/promises";
import { ChatGroq } from "@langchain/groq";
import { SystemMessage, HumanMessage, trimMessages } from "@langchain/core/messages";

const model = new ChatGroq({ model: "openai/gpt-oss-120b", temperature: 0.6 });

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
    tokenCounter: model,           // an estimate: GPT-2's tokenizer (see §5.6)
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
  const u = full.usage_metadata ?? full.response_metadata.usage;   // JS + Groq: §3.6
  console.log(`\n      [${u ? u.input_tokens + u.output_tokens : "?"} tokens]\n`);

  history.push(full);                     // ⚠️ remember what the AI said
}
rl.close();
```

Try it: ask a question, then say *"simpler"*, then *"what did I first ask you?"*. Then run 20
turns and watch `stats` — trimming keeps history bounded instead of growing forever.

### 4.7 Reasoning parameters, measured

This script produces the numbers in §3.9. Run it once and keep the output. It is your proof of
how your model handles `maxTokens`, `reasoningEffort`, `logprobs` and `n` today.

```js
// day04-reasoning.js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";

const MODEL = "openai/gpt-oss-120b";
const Q = "What is 2+2? Answer with the number only.";

// 1. A small maxTokens on a reasoning model: the hidden thinking uses it up.
const tiny = new ChatGroq({ model: MODEL, maxTokens: 20 });
const r1 = await tiny.invoke(Q);
console.log("maxTokens 20   →", JSON.stringify(r1.text), r1.response_metadata.finish_reason,
  r1.usage_metadata.output_tokens, "output tokens");

// 2. Default effort vs low effort.
const normal = new ChatGroq({ model: MODEL });
const r2 = await normal.invoke(Q);
console.log("default effort →", JSON.stringify(r2.text), r2.usage_metadata.output_tokens, "output tokens");

const quick = new ChatGroq({ model: MODEL, reasoningEffort: "low" });
const r3 = await quick.invoke(Q);
console.log("effort low     →", JSON.stringify(r3.text), r3.usage_metadata.output_tokens, "output tokens");

// 3. Where is the reasoning? Not on the JS message.
console.log("additional_kwargs keys:", Object.keys(r3.additional_kwargs));
console.log("usage_metadata:", r3.usage_metadata);

// 4. Parameters the current Groq models reject.
for (const [label, extra] of [["logprobs", { logprobs: true }], ["n: 2", { n: 2 }]]) {
  try {
    await new ChatGroq({ model: MODEL, ...extra }).invoke("Hi");
    console.log(label, "→ accepted");
  } catch (e) {
    console.log(label.padEnd(8), "→", e.message.split("\n")[0].slice(0, 90));
  }
}
```

Output from a real run (October 2026; token counts move a little between runs):

```
maxTokens 20   → "" length 20 output tokens
default effort → "4" 46 output tokens
effort low     → "4" 16 output tokens
additional_kwargs keys: [ 'tool_calls' ]
usage_metadata: { input_tokens: 84, output_tokens: 16, total_tokens: 100 }
logprobs → 400 {"error":{"message":"`logprobs` is not supported with this model","type":"invalid_requ
n: 2     → 400 {"error":{"message":"'n' : number must be at most 1","type":"invalid_request_error"}}
```

The first line is the trap from §3.9: no error, no text, just `length`. If an answer is ever
mysteriously empty, check `finish_reason` before anything else.

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
    model="openai/gpt-oss-120b",
    temperature=0.7,
    max_tokens=500,       # generous: hidden reasoning counts too (§3.9)
)

res = model.invoke("Explain recursion to a 10-year-old in 3 sentences.")

print(res.text)
print("---")
print("tokens:", res.usage_metadata)
print("finish:", res.response_metadata.get("finish_reason"))
```

Output from a real run (October 2026 — your wording will differ):

```
Imagine you have a set of Russian nesting dolls, and each doll opens to reveal a smaller doll that looks just like the one before it. Recursion is like a computer program that solves a problem by doing the same thing over and over, but each time with a smaller piece of the problem, just like opening the next smaller doll. The program keeps repeating this until it reaches the tiniest doll (the simplest case), and then it puts all the answers together to finish the whole task.
---
tokens: {'input_tokens': 84, 'output_tokens': 156, 'total_tokens': 240, 'output_token_details': {'reasoning': 49}}
finish: stop
```

Python shows what JS hides: 49 of the 156 output tokens were hidden reasoning. You pay for
them, but you never see them in the answer.

> ⚠️ **Python detail:** on some versions `text` is a *property* and on others a *method*.
> If `res.text` prints `<bound method ...>`, call it: `res.text()`. `res.content` always works
> for text-only models.

### 5.2 Message types

> 📦 **Import paths.** This book imports messages from **`langchain_core.messages`** (Python)
> and **`@langchain/core/messages`** (JS). These are the standard paths and work on both
> LangChain 1.x and 0.3.
>
> LangChain 1.x *also* re-exports them from the top-level package. You'll see
> `from langchain.messages import HumanMessage` in the 1.x docs, and `from "langchain"` in the
> JS docs. Both are correct on 1.x. The `core` paths are correct on more versions, so that's
> what we use. (`initChatModel` is the exception — it really does live in the `langchain` root.)

```python
# day04_messages.py
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

load_dotenv()
model = ChatGroq(model="openai/gpt-oss-120b", temperature=0)

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
model = ChatGroq(model="openai/gpt-oss-120b", temperature=0)

# ── INVOKE ───────────────────────────────────────────────────────────────
print("── invoke ──")
print(model.invoke("Name one planet. One word.").content)

# ── STREAM ───────────────────────────────────────────────────────────────
print("\n── stream ──")
t0 = time.time()
first_token_at = None
full = None

for chunk in model.stream("List 5 planets, one per line."):
    if chunk.content and first_token_at is None:
        first_token_at = time.time() - t0        # first VISIBLE token (§3.9)
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

Output from a real run (October 2026 — timings change on every run):

```
── invoke ──
Mars

── stream ──
Mercury
Venus
Earth
Mars
Jupiter
time to first token: 772ms | total: 799ms
usage (from accumulated chunks): {'input_tokens': 80, 'output_tokens': 48, 'total_tokens': 128, 'output_token_details': {'reasoning': 27}}

── batch ──
['Tokyo', 'Paris', 'Lima.', 'Nairobi']
batch of 4 took 933ms
```

Notice `'Lima.'` with a full stop, even at temperature 0. "One word" in a prompt is a request,
not a rule. Day 06 shows how to force a format.

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
        return ChatGroq(model="openai/gpt-oss-120b", temperature=0)
    if name == "gemini":
        return ChatGoogleGenerativeAI(model="gemini-3.8-flash", temperature=0)
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

Output from our run (October 2026), again with no Ollama and a Gemini key over its quota:

```
groq     → ready
gemini   → skipped (Error calling model 'gemini-3.8-flash' (RESOURCE_E)
ollama   → skipped ([WinError 10061] No connection could be made becau)
```

`RESOURCE_EXHAUSTED` is Google's name for the same 429 quota error. `WinError 10061` is Windows
saying nothing is listening on Ollama's port; on macOS or Linux the text differs.

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
    os.getenv("MODEL", "groq:openai/gpt-oss-120b"),
    temperature=0,
    max_tokens=512,       # not 200: hidden reasoning counts toward the cap (§3.9)
)
print(model.invoke("Say READY").content)

# Runtime-configurable: pick the model per call.
flexible = init_chat_model(configurable_fields=["model"])
print(flexible.invoke(
    "Say A",
    config={"configurable": {"model": "groq:openai/gpt-oss-20b"}},
).content)
```

Output from a real run:

```
READY
A
```

### 5.6 StudyBuddy v0 — a chatbot with real history handling

```python
# day04_studybuddy.py
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, trim_messages
from langchain_core.messages.utils import count_tokens_approximately

load_dotenv()
model = ChatGroq(model="openai/gpt-oss-120b", temperature=0.6)

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
        token_counter=count_tokens_approximately,   # ~4 characters per token (below)
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

> ⚠️ **Why `count_tokens_approximately`?** It guesses about four characters per token, plus a
> few tokens per message, so it needs no download, and a guess is all a budget needs. You may
> see `token_counter=model` in older code. With `ChatGroq` that is a guess too, and a slow one:
> Groq's model has no tokenizer in LangChain, so it printed `UserWarning: Using fallback GPT-2
> tokenizer for token counting`, needed the `transformers` package, and downloaded GPT-2 (one
> turn took 82 s in our tests). JavaScript's `tokenCounter: model` also uses GPT-2's tokenizer,
> fetched once from the web (under a second in our run), so it is an estimate as well. Treat
> `max_tokens=800` as a rough budget. The real count is in `usage_metadata` after each call
> (618 tokens for our first turn).

### 5.7 Reasoning parameters, measured

```python
# day04_reasoning.py
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()
MODEL = "openai/gpt-oss-120b"
Q = "What is 2+2? Answer with the number only."

# 1. A small max_tokens on a reasoning model: the hidden thinking uses it up.
tiny = ChatGroq(model=MODEL, max_tokens=20)
r1 = tiny.invoke(Q)
print("max_tokens 20  →", repr(r1.content), r1.response_metadata.get("finish_reason"),
      r1.usage_metadata["output_tokens"], "output tokens")

# 2. Default effort vs low effort.
r2 = ChatGroq(model=MODEL).invoke(Q)
print("default effort →", repr(r2.content), r2.usage_metadata["output_tokens"], "output tokens")

quick = ChatGroq(model=MODEL, reasoning_effort="low")
r3 = quick.invoke(Q)
print("effort low     →", repr(r3.content), r3.usage_metadata["output_tokens"], "output tokens")

# 3. Where is the reasoning? Python exposes it.
print("reasoning_content:", repr(r3.additional_kwargs.get("reasoning_content")))
print("usage_metadata:", r3.usage_metadata)

# 4. Parameters the current Groq models reject.
#    (Python's ChatGroq has no logprobs field, so it goes through model_kwargs.)
for label, extra in [("logprobs", {"model_kwargs": {"logprobs": True}}), ("n=2", {"n": 2})]:
    try:
        ChatGroq(model=MODEL, **extra).invoke("Hi")
        print(label, "→ accepted")
    except Exception as e:
        print(f"{label:<8} →", str(e).splitlines()[0][:90])
```

Output from a real run (October 2026; token counts move a little between runs):

```
max_tokens 20  → '' length 20 output tokens
default effort → '4' 47 output tokens
effort low     → '4' 16 output tokens
reasoning_content: 'Just answer 4.'
usage_metadata: {'input_tokens': 84, 'output_tokens': 16, 'total_tokens': 100, 'output_token_details': {'reasoning': 6}}
logprobs → Error code: 400 - {'error': {'message': '`logprobs` is not supported with this model', 'ty
n=2      → Error code: 400 - {'error': {'message': "'n' : number must be at most 1", 'type': 'invalid
```

Python shows the hidden thinking: `'Just answer 4.'`, counted as 6 of the 16 output tokens.

### 🔁 JS ↔ Python differences you just saw

| | JavaScript | Python |
|---|---|---|
| Params | `maxTokens`, `topP`, `maxRetries` | `max_tokens`, `top_p`, `max_retries` |
| Universal loader | `await initChatModel("groq:...")` | `init_chat_model("groq:...")` — no await |
| Chunk accumulation | `full.concat(chunk)` | `full + chunk` |
| Batch concurrency | `{ maxConcurrency: 2 }` | `config={"max_concurrency": 2}` |
| Message import | `from "@langchain/core/messages"` | `from langchain_core.messages import ...` |
| Trimming | `trimMessages(msgs, {...})` | `trim_messages(msgs, ...)` |
| Token counter (an estimate either way) | `tokenCounter: model` (GPT-2's tokenizer) | `token_counter=count_tokens_approximately` |
| Text accessor | `res.text` | `res.content` (or `res.text` / `res.text()`) |
| Async variants | none — always async | `ainvoke`, `astream`, `abatch` |
| Reasoning effort | `reasoningEffort: "low"` | `reasoning_effort="low"` |
| Hidden reasoning (Groq) | not exposed | `additional_kwargs["reasoning_content"]`, `usage_metadata["output_token_details"]["reasoning"]` |
| Streamed usage (Groq) | `response_metadata.usage` — `usage_metadata` is missing (§3.6) | `usage_metadata`, as normal |
| Model chosen per call | `initChatModel("openai/gpt-oss-120b", { modelProvider: "groq", configurableFields: ["model"] })`, then `{ model: "openai/gpt-oss-20b" }` | `init_chat_model(configurable_fields=["model"])`, then `{"model": "groq:openai/gpt-oss-20b"}` |

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

**Steps 4 and 6 are the whole value of the abstraction.** Step 4 turns your messages into the
provider's *wire format* — the exact request shape it expects over the network. Notice
Anthropic puts `system` in a *separate top-level field*, not in the messages array. LangChain
hides that. If you swapped providers by hand, details like this are what cause bugs.

### Why `AIMessageChunk` supports `+` / `.concat()`

Streaming produces partial messages, and merging them is tricky. You join the `content` text.
But you must *merge* tool-call fragments by index, because a tool call's JSON arguments arrive
across many chunks. And you take usage from whichever chunk has it.

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

It also passes callbacks (hooks that fire at each step) through for every item, so tracing
works. In Python it also offers `batch_as_completed`, if you want results as they finish rather
than in order.

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
The model can't see its own previous answers, so it repeats itself and contradicts itself.
✅ Push both sides of every turn.

---

**❌ Using `batch` for a conversation**

```js
await model.batch([turn1, turn2, turn3]);   // three INDEPENDENT calls
```
These run concurrently and share no context. ✅ Use `batch` for independent inputs only.

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
✅ `max_tokens` in Python, `maxTokens` in LangChain JS, `max_tokens` in raw SDKs in both languages.

---

**❌ Creating a new model instance inside a request handler**

```js
app.post("/chat", async (req, res) => {
  const model = new ChatGroq({ ... });   // new HTTP client per request
});
```
✅ Create once at module scope (the top level of the file) and reuse it. Connection pooling —
reusing open network connections — matters under load.

---

**❌ Assuming every provider supports every parameter**

`frequency_penalty` doesn't exist on Anthropic, and `top_k` doesn't exist on OpenAI. LangChain
passes unknown parameters through, and the provider may return an error or silently ignore them.
Current Groq models, for example, reject `logprobs` and any `n` above 1 with a `400` (§3.9).
✅ Check the integration docs when you leave the common set (temperature, max tokens, top_p).

---

**❌ A small `maxTokens` on a reasoning model**

```js
new ChatGroq({ model: "openai/gpt-oss-120b", maxTokens: 20 });   // ❌ answers ""
```
The hidden thinking used all 20 tokens. The reply was an empty string with
`finish_reason: "length"`, and there was no error (§4.7). ✅ Keep `maxTokens` at 512 or more on
a reasoning model. For simple jobs, add `reasoningEffort: "low"`, and ask for a short answer in
the prompt.

---

## 8. Exercises

### Exercise 1 — Model report card ●○○○○

Write a script that asks the same question to 3 models: two Groq models (GPT-OSS 120B and
20B), plus Gemini or Ollama.
Print a table with the model, answer, input tokens, output tokens and latency (response time)
in ms. Which is the best value for a simple factual question?

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";
import { ChatGoogleGenerativeAI } from "@langchain/google-genai";

const MODELS = {
  "oss-120b": new ChatGroq({ model: "openai/gpt-oss-120b", temperature: 0 }),
  "oss-20b":  new ChatGroq({ model: "openai/gpt-oss-20b",  temperature: 0 }),
  "gemini":   new ChatGoogleGenerativeAI({ model: "gemini-3.8-flash", temperature: 0 }),
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
    "oss-120b": ChatGroq(model="openai/gpt-oss-120b", temperature=0),
    "oss-20b":  ChatGroq(model="openai/gpt-oss-20b",  temperature=0),
    "gemini":   ChatGoogleGenerativeAI(model="gemini-3.8-flash", temperature=0),
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

Output of the JavaScript run (October 2026):

```
model      | ms    | in  | out | answer
------------------------------------------------------------------------------------------
oss-120b   | 570   | 82  | 89  | The seasons occur because Earth’s axis is tilted about 23.5°
oss-20b    | 398   | 82  | 115 | The seasons on Earth are caused by the planet’s axial tilt r
gemini     | error: [GoogleGenerativeAI Error]: Error fetching from https://gene
```

The Python run gave the same token counts (82 in; 89 and 115 out) and the same answers, with
times of 2,050 ms and 656 ms. Gemini failed in both runs with the quota error from §4.4.

**What to notice:** both GPT-OSS models were correct, and the 20B model was faster in both
runs. But it wrote **more** output tokens (115 against 89), because it spent more on hidden
thinking. At the prices in Day 03 §3.11, the 20B call cost about $0.000041 and the 120B call
about $0.000066. The small model is still cheaper, but by less than its price per token
suggests. Choosing the biggest model out of habit is one of the most common ways teams
overspend. Pick the smallest model that passes your eval set (Exercise 5 on Day 02), and
measure its real token use.
</details>

---

### Exercise 2 — Streaming with stats ●●○○○

Build `streamWithStats(model, prompt)` that streams to stdout while measuring: time to first
token (TTFT), total time, token count, and tokens per second. Compare the 120B and the 20B
model. Is time-to-first-token or tokens/sec the bigger difference?

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
    if (chunk.content) ttft ??= Date.now() - t0;   // first VISIBLE token (§3.9)
    chunks++;
    process.stdout.write(chunk.content);
    full = full ? full.concat(chunk) : chunk;
  }

  const total = Date.now() - t0;
  // JS + Groq: streamed counts live in response_metadata.usage (§3.6)
  const out = (full.usage_metadata ?? full.response_metadata.usage)?.output_tokens ?? chunks;
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
for (const [label, id] of [["120B", "openai/gpt-oss-120b"], ["20B", "openai/gpt-oss-20b"]]) {
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
        if chunk.content and ttft is None:
            ttft = time.time() - t0              # first VISIBLE token (§3.9)
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
    for label, mid in [("120B", "openai/gpt-oss-120b"), ("20B", "openai/gpt-oss-20b")]
]

print("\n")
for s in stats:
    print(s)
```

Output from our runs (October 2026). The answers are left out here; both were about 120
words. JavaScript:

```
┌─────────┬────────┬────────┬─────────┬──────────────┬──────────────┐
│ (index) │ label  │ ttftMs │ totalMs │ outputTokens │ tokensPerSec │
├─────────┼────────┼────────┼─────────┼──────────────┼──────────────┤
│ 0       │ '120B' │ 610    │ 967     │ 233          │ 241          │
│ 1       │ '20B'  │ 1429   │ 1589    │ 1136         │ 714.9        │
└─────────┴────────┴────────┴─────────┴──────────────┴──────────────┘
```

Python:

```
{'label': '120B', 'ttft_ms': 945, 'total_ms': 1308, 'output_tokens': 233, 'tokens_per_sec': 178.1}
{'label': '20B', 'ttft_ms': 1421, 'total_ms': 1609, 'output_tokens': 973, 'tokens_per_sec': 604.6}
```

**What you'll find:** the 20B model wins clearly on **tokens per second**, as Groq's published
speeds suggest. But its first visible token came **later** (about 1.4 s against 0.6–0.9 s).
It also wrote four or five times as many output tokens for an answer of the same length.
Almost all of the extra was hidden thinking, and that thinking is why the first visible token
was late. Tokens per second here counts the thinking too.

So for this prompt the "cheap" model cost more: 973 output tokens at $0.30 per million is
more than 233 at $0.60 (Day 03 §3.11 prices). With reasoning models, smaller is not
automatically cheaper. Measure it on your own prompts.

**Why it matters:** for a chat UI, TTFT is what users perceive as "fast". For a batch
summarisation job, throughput is what matters. Optimise the metric your product actually feels.
</details>

---

### Exercise 3 — Fallback chain ●●●○○

Build `resilientModel()` that tries Groq, then Gemini, then Ollama, and returns the first
success. Use LangChain's built-in `.withFallbacks()` / `.with_fallbacks()`. Prove it works by
giving the primary model an invalid API key. Then do it *manually* too, and compare the code.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";
import { ChatGoogleGenerativeAI } from "@langchain/google-genai";
import { ChatOllama } from "@langchain/ollama";

// ── The LangChain way ────────────────────────────────────────────────────
const broken = new ChatGroq({ model: "openai/gpt-oss-120b", apiKey: "gsk_invalid" });

const resilient = broken.withFallbacks([
  new ChatGoogleGenerativeAI({ model: "gemini-3.8-flash" }),
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
  [broken, new ChatGoogleGenerativeAI({ model: "gemini-3.8-flash" })],
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
broken = ChatGroq(model="openai/gpt-oss-120b", api_key="gsk_invalid")

resilient = broken.with_fallbacks([
    ChatGoogleGenerativeAI(model="gemini-3.8-flash"),
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
    [broken, ChatGoogleGenerativeAI(model="gemini-3.8-flash")],
    "Say READY",
)
print("manual    →", res.content.strip())
```

> Not re-run after the October 2026 model change: our Gemini key was over its free quota
> (§4.4), so there was nothing healthy to fall back to. Only the model names changed here.

**The real insight:** `.withFallbacks()` returns a **`Runnable`**, so it composes. (A Runnable
is LangChain's shared interface for anything you can invoke, stream or batch — Day 07.) You can
attach it to a whole chain, not just a model. `(prompt | model | parser).with_fallbacks([...])`
falls back the *entire pipeline*. Your manual version only works on one model call, and you
would have to rewrite it for every new composition. That's the benefit of the `Runnable`
interface.

**Production caveat:** fall back across *providers*, not just models. Otherwise a single
provider outage takes down every option. And log which fallback fired. If the app silently
drops to a weaker model, drops in quality go unnoticed.
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

const model = new ChatGroq({ model: "openai/gpt-oss-120b", temperature: 0 });
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
from langchain_core.messages.utils import count_tokens_approximately

load_dotenv()
model = ChatGroq(model="openai/gpt-oss-120b", temperature=0)
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
        token_counter=count_tokens_approximately, include_system=True, start_on="human",
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

**Typical result** (illustrative — your token counts will differ by model and by how long the
answers are; the *ordering* is what matters):

| Strategy | Tokens | Remembered "teal"? |
|---|---|---|
| keepAll | ~4,800 | ✅ |
| window4 | ~1,900 | ❌ |
| trimmed | ~2,600 | ❌ or ✅ (borderline) |

**The lesson — and it's the whole reason Day 14 and Day 20 exist:** trimming trades memory for
cost. No window size is both cheap and remembers everything. The real fix isn't a better
trimming rule. It's a *different mechanism*:

- summarise old turns into a running summary, or
- store facts in a vector store (a database that finds text by meaning) or long-term memory,
  and retrieve the relevant ones.

Both are Week 2/3 topics. You've now felt exactly why they're needed.
</details>

---

### Exercise 5 — StudyBuddy v0.5 ●●●●○

Upgrade the StudyBuddy chatbot with:

- (a) a `/level <beginner|intermediate|expert>` command that rewrites the system message;
- (b) `/model <groq|gemini|ollama>` to switch providers in the middle of a chat, keeping the
  history;
- (c) a `/cost` command showing total tokens so far and the estimated cost in USD;
- (d) error handling that reports the error and doesn't crash the loop.

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

// US$ per 1M tokens. Groq = GPT-OSS 120B, read from console.groq.com/docs/models
// on 7 Oct 2026. Gemini = ILLUSTRATIVE: copy the real price from Google's pricing page.
const PRICING = {
  groq:   { in: 0.15, out: 0.60 },
  gemini: { in: 0.30, out: 2.50 },
  ollama: { in: 0, out: 0 },
};

const LEVELS = {
  beginner:     "Explain like the user is 12. Use everyday analogies. No jargon.",
  intermediate: "Explain like the user is a junior developer. Some jargon is fine; define it.",
  expert:       "Explain like the user is a senior engineer. Be dense and precise. Skip basics.",
};

const makeModel = (name) => ({
  groq:   () => new ChatGroq({ model: "openai/gpt-oss-120b", temperature: 0.6 }),
  gemini: () => new ChatGoogleGenerativeAI({ model: "gemini-3.8-flash", temperature: 0.6 }),
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
    const u = full.usage_metadata ?? full.response_metadata.usage ?? {};   // JS + Groq: §3.6
    usage.in  += u.input_tokens  ?? 0;
    usage.out += u.output_tokens ?? 0;
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
from langchain_core.messages.utils import count_tokens_approximately

load_dotenv()

# US$ per 1M tokens. Groq = GPT-OSS 120B, read from console.groq.com/docs/models
# on 7 Oct 2026. Gemini = ILLUSTRATIVE: copy the real price from Google's pricing page.
PRICING = {
    "groq":   {"in": 0.15,  "out": 0.60},
    "gemini": {"in": 0.30,  "out": 2.50},
    "ollama": {"in": 0.0,   "out": 0.0},
}

LEVELS = {
    "beginner":     "Explain like the user is 12. Use everyday analogies. No jargon.",
    "intermediate": "Explain like the user is a junior developer. Some jargon is fine; define it.",
    "expert":       "Explain like the user is a senior engineer. Be dense and precise. Skip basics.",
}

def make_model(name):
    return {
        "groq":   lambda: ChatGroq(model="openai/gpt-oss-120b", temperature=0.6),
        "gemini": lambda: ChatGoogleGenerativeAI(model="gemini-3.8-flash", temperature=0.6),
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
        max_tokens=1000, strategy="last", token_counter=count_tokens_approximately,
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
   and conversation state are different things. If you mixed them up, `/level` would need a
   history rewrite.
3. **`history.pop()` on error.** If the call fails, the user's message is still in history with
   no answer after it. Next turn you'd send two human messages in a row, which some providers
   reject outright. Small detail; real production bug.
</details>

---

## 9. Interview questions

### Basic

<details>
<summary><b>Q: Difference between `invoke`, `stream` and `batch`?</b></summary>

`invoke` sends one input and returns one complete `AIMessage`. `stream` sends one input and
returns an async iterator of `AIMessageChunk`s as they're generated. The total time is the same,
but perceived latency (how fast it *feels*) is much better. `batch` sends *multiple independent*
inputs concurrently, with a concurrency cap you can set, and returns results in input order.
Use `batch` only for independent inputs. Never use it for conversation turns, because each turn
depends on the one before.
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
understands roles, tool calls and multimodal content. Nearly every modern provider is chat-only,
so chat models are what you should use. LLM-style classes remain mostly so old code keeps
working.
</details>

<details>
<summary><b>Q: How do you count tokens for a request?</b></summary>

Read `usage_metadata` on the response — `{ input_tokens, output_tokens, total_tokens }`,
normalised across providers. When streaming, usage arrives in the **final** chunk, so accumulate
chunks (`concat` / `+`) and read it from the total. To count *before* sending, use
`getNumTokens` / `get_num_tokens` on the model, or the provider's tokenizer directly. For
Groq's models both fall back to GPT-2's tokenizer, so they are estimates; for a budget, Python's
cheaper `count_tokens_approximately` is enough.
</details>

### Intermediate

<details>
<summary><b>Q: Why do `AIMessageChunk`s support addition?</b></summary>

Because putting a streamed response back together is harder than it looks. Text content simply
joins up. But tool calls arrive as *fragments* that must be merged by index, because a single
tool call's JSON arguments are split across many chunks. And usage metadata appears only in the
final chunk. Making chunks addable puts that merge logic in one tested place. So
`full = full.concat(chunk)` gives you a correct complete message, including assembled tool
calls.
</details>

<details>
<summary><b>Q: How does LangChain make providers interchangeable when their APIs differ so much?</b></summary>

Each integration package implements `BaseChatModel` with two translation layers:

- **Outbound:** it converts `BaseMessage[]` into that provider's wire format (the exact request
  shape it expects). Anthropic takes `system` as a separate top-level field. Gemini uses
  `contents`/`parts`. OpenAI-style APIs use a flat `messages` array.
- **Inbound:** it normalises the response into `AIMessage`, with consistent `content`,
  `tool_calls` and `usage_metadata`.

Your code only ever sees the normalised types, so the provider choice stays out of your calling
code. The trade-off: provider-specific features need either explicit support or an escape hatch
(`modelKwargs` / `model_kwargs`).
</details>

<details>
<summary><b>Q: What is `initChatModel` / `init_chat_model` and when would you use it?</b></summary>

A universal factory that takes a `"provider:model"` string and returns the right chat model. It
loads the integration package only when needed (a lazy import). Use it when the provider should
be *configuration* rather than code. For example, set `MODEL=groq:openai/gpt-oss-120b` in
the environment, so the operations team can switch models without a deploy. That matters more
than it sounds: model names get retired, and a config change is faster than a code release. It also supports
`configurableFields`, letting you pick the model per call at runtime. Use the direct class when you need provider-specific constructor options or want the
dependency to be explicit. Note the JS version is awaited; the Python one isn't.
</details>

<details>
<summary><b>Q: How would you implement conversation memory with just a chat model?</b></summary>

Keep an array of messages. Append the `HumanMessage` before each call and the returned
`AIMessage` after. Send the whole array each turn. Then put a limit on it, because cost is O(n²)
over a conversation: it grows with the square of the number of turns. Use a sliding window, or
`trimMessages`/`trim_messages` with a token budget that keeps the system message and starts on a
human turn.

The important caveat: trimming *loses* information. No window size is both cheap and remembers
everything. The real solutions are summarising older turns into a rolling summary, or storing
facts externally and retrieving the relevant ones. Persisting across sessions needs a
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

Steps 4 and 6 are where the abstraction proves its value. Steps 3 and 7 are why tracing works
without you adding any instrumentation.
</details>

<details>
<summary><b>Q: Design a model layer for a product serving 3 tiers: free, pro, enterprise.</b></summary>

**Routing by tier** — free gets a small fast model (such as a 20B model), and pro gets a
mid-tier model.
Enterprise gets the frontier model (the newest, most capable one) plus a dedicated-capacity
provider. Implement it as a factory keyed by tier, so the choice lives in one place.

**Reliability** — every tier gets `.withFallbacks()` across *providers*, not just models, so one
provider outage doesn't take you down. Log every fallback. If the app silently drops to a weaker
model, drops in quality go unnoticed.

**Cost control** — track per-tenant (per-customer) token budgets from `usage_metadata`. Add a
hard cap that returns a friendly error rather than a surprise bill. Cache identical requests.
Trim history hard on the free tier and lightly on enterprise.

**Latency** — stream everywhere for perceived speed. Route by task, not just tier. Even
enterprise should use the small model for classification and routing, and keep the big model for
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
   provider, then against your endpoint. Check `Cache-Control: no-transform` and disable
   buffering for SSE (Server-Sent Events, the usual streaming format).

Common real causes, in the order I'd check them:

- response buffering in the reverse proxy;
- awaiting the *whole* response on the server, then re-emitting it;
- a large prompt;
- a cold model (one that has to start up before it can answer).

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
- ✅ Memory means re-sending history; `trimMessages` limits the cost but loses information
- ✅ Swapping providers is one line — that isolation is the point, not the brevity
- ✅ Reasoning models (GPT-OSS) think in hidden tokens: they count toward `maxTokens` and the bill; use `reasoningEffort: "low"` for simple jobs
- ✅ Groq's current models reject `logprobs` and `n` above 1; model names change, so keep them in config

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

1. `batch` runs inputs concurrently and independently, with no shared context. Conversation
   turns depend on each other in order: turn 2 needs turn 1's answer in its input.
2. Expected. Token usage arrives in the final chunk. Accumulate chunks with `concat`/`+` and
   read `usage_metadata` from the total.
3. Swap the model constructor (`new ChatGroq(...)` → `new ChatGoogleGenerativeAI(...)`). It
   works because every chat model implements `BaseChatModel`: same input types
   (`BaseMessage[]`), same output type (`AIMessage`), same methods. The provider's wire-format
   differences are handled inside the integration package.
</details>

---

<div align="center">

**[← Day 03 — Choosing a Model](day-03-choosing-a-model-and-why-langchain.md)** · **[Week 1 index](README.md)** · **[Day 05 — Prompts & Templates →](day-05-prompts-and-templates.md)**

</div>
