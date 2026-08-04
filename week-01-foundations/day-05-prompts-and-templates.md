# Day 05 — Prompts & Templates

> ⏱ **Time:** ~2 hours · 🎯 **Prereqs:** [Day 04](day-04-langchain-models.md) · 🧩 **Difficulty:** ●●○○○

**Today you learn:** `PromptTemplate`, `ChatPromptTemplate`, `MessagesPlaceholder`, few-shot
templates, partials and prompt composition — and why every one of them is a `Runnable`, which
sets up tomorrow's LCEL.

---

## 1. The problem

Your prompts are currently string concatenation. Here's how that dies.

```js
// Week 1 of the project — fine.
const prompt = `Summarise this in ${style}: ${text}`;

// Week 3 — a system message, history, and a format instruction.
const prompt =
  `You are a ${persona} assistant.\n` +
  `Tone: ${tone}\n` +
  history.map((m) => `${m.role}: ${m.content}`).join("\n") + "\n" +
  `Summarise this in ${style}: ${text}\n` +
  `Respond in ${language}.`;

// Week 6 — now with few-shot examples, and it must work for 4 different tasks.
// 😱
```

Four specific things break:

| Problem | Symptom |
|---|---|
| **No validation** | Typo `${stlye}` → `"undefined"` silently lands in your prompt |
| **Roles are fake** | You hand-render `"user: ..."` into one string; the model loses the role structure |
| **Not reusable** | Same prompt in 3 files, edited in 2 of them |
| **Not composable** | You can't `.pipe()` a string into a model, so nothing chains |

A prompt template fixes all four: it declares its variables, produces **real messages**, is a
single reusable object, and is a `Runnable`.

---

## 2. Mental model

```
    A TEMPLATE IS A FUNCTION FROM VARIABLES TO MESSAGES.

    ┌─────────────────┐        ┌──────────────────────────┐
    │  { topic: "AI", │        │  [ SystemMessage(...),   │
    │    level: "12" }│───────▶│    HumanMessage(...) ]   │
    └─────────────────┘        └──────────────────────────┘
        input variables            real message objects
                                            │
                                            ▼
                                      model.invoke()


    THE FAMILY:

    PromptTemplate ─────────── one string, for old-style completion models
                               (you'll rarely use this directly)

    ChatPromptTemplate ─────── a LIST of messages ← use this 95% of the time
        │
        ├── ("system", "...")           a fixed role + templated text
        ├── ("human", "{question}")
        ├── MessagesPlaceholder("history")  ← a HOLE where a message ARRAY goes
        └── FewShotChatMessagePromptTemplate  ← generates example turns

    All of them are Runnables:   template.pipe(model)   →   template | model
```

The key distinction to hold onto:

```
   "{question}"                → a STRING slot. One value.
   MessagesPlaceholder("hist") → a MESSAGE-LIST slot. Zero or many messages.
```

---

## 3. First principles

### 3.1 `PromptTemplate` — a single string

```js
import { PromptTemplate } from "@langchain/core/prompts";

const t = PromptTemplate.fromTemplate("Summarise this in {style}:\n\n{text}");

await t.format({ style: "3 bullets", text: "..." });   // → a string
await t.invoke({ style: "3 bullets", text: "..." });   // → a StringPromptValue
```

`{name}` is the variable syntax. To output a literal brace, double it: `{{` and `}}`.

> ⚠️ **The JSON trap.** If your prompt contains a JSON example, every brace is a variable:
> ```
> "Respond like: {"name": "x"}"     ❌ error: missing variable "name"
> "Respond like: {{"name": "x"}}"   ✅
> ```
> This is the single most common template error. Templates are literally the reason we prefer
> structured output (Day 06) over writing JSON examples in prompts.

You'll mostly meet `PromptTemplate` inside document chains (Day 08). For chat models, use:

### 3.2 `ChatPromptTemplate` — a list of messages

```js
import { ChatPromptTemplate } from "@langchain/core/prompts";

const prompt = ChatPromptTemplate.fromMessages([
  ["system", "You are a tutor. Explain at a {level} level."],
  ["human", "{question}"],
]);

const messages = await prompt.invoke({ level: "beginner", question: "What is RAG?" });
// → ChatPromptValue containing [SystemMessage, HumanMessage]
```

Roles you can use as the first tuple element: `"system"`, `"human"` (or `"user"`),
`"ai"` (or `"assistant"`), `"placeholder"`.

**Three ways to write the same template:**

```js
// tuples — most common, most readable
ChatPromptTemplate.fromMessages([["system", "..."], ["human", "{q}"]]);

// message class templates — when you need per-message options
ChatPromptTemplate.fromMessages([
  SystemMessagePromptTemplate.fromTemplate("..."),
  HumanMessagePromptTemplate.fromTemplate("{q}"),
]);

// mixing static messages with templated ones
ChatPromptTemplate.fromMessages([
  new SystemMessage("A fixed instruction with no variables."),
  ["human", "{q}"],
]);
```

### 3.3 `MessagesPlaceholder` — the hole for history

This is the piece that makes chatbots clean.

```js
import { ChatPromptTemplate, MessagesPlaceholder } from "@langchain/core/prompts";

const prompt = ChatPromptTemplate.fromMessages([
  ["system", "You are StudyBuddy, a {level}-level tutor."],
  new MessagesPlaceholder("history"),      // ← an ARRAY of messages goes here
  ["human", "{question}"],
]);

await prompt.invoke({
  level: "beginner",
  history: [new HumanMessage("Hi"), new AIMessage("Hello!")],
  question: "What is a token?",
});
// → [System, Human("Hi"), AI("Hello!"), Human("What is a token?")]
```

Shorthand: `["placeholder", "{history}"]` does the same thing.

Optional placeholders (so the first turn doesn't crash):

```js
new MessagesPlaceholder({ variableName: "history", optional: true })
```

**Why this matters:** without it, you'd concatenate history into a string and lose the role
structure — which measurably degrades quality, because the model was trained on role-formatted
conversations.

### 3.4 Few-shot templates

Day 02 taught few-shot by hand-writing examples into a string. Templates make examples **data**:

```js
import { FewShotChatMessagePromptTemplate, ChatPromptTemplate } from "@langchain/core/prompts";

const examples = [
  { input: "I was charged twice.",     output: "BILLING" },
  { input: "The app crashes.",         output: "BUG" },
  { input: "Please add dark mode.",    output: "FEATURE" },
];

const fewShot = new FewShotChatMessagePromptTemplate({
  examplePrompt: ChatPromptTemplate.fromMessages([
    ["human", "{input}"],
    ["ai", "{output}"],
  ]),
  examples,
});

const prompt = ChatPromptTemplate.fromMessages([
  ["system", "Classify support tickets. Reply with the label only."],
  fewShot,                              // ← expands into 6 messages
  ["human", "{input}"],
]);
```

This renders the examples as **real alternating Human/AI turns**, which models follow more
reliably than the same examples flattened into one string.

> 💡 **The upgrade path:** swap `examples` for an `exampleSelector` that retrieves the *k most
> similar* examples from a vector store per input. Same template, dynamic examples. That's a
> Week 2 technique (`SemanticSimilarityExampleSelector`) and a great interview answer to
> "how would you improve a few-shot classifier?"

### 3.5 Partials — fill in some variables now, the rest later

```js
const base = ChatPromptTemplate.fromMessages([
  ["system", "You are a {role}. Today is {date}."],
  ["human", "{question}"],
]);

// Bake in the values you already know:
const tutorPrompt = await base.partial({ role: "patient tutor" });
await tutorPrompt.invoke({ date: "2026-08-04", question: "..." });   // only 2 vars left

// Or a FUNCTION, evaluated at render time:
const dated = await base.partial({ date: () => new Date().toISOString().slice(0, 10) });
```

Function partials are how you inject "now", a request ID, or a feature flag without threading
it through every call site.

### 3.6 Composition

Templates compose with `+` (JS: `.concat`, or the `+` operator on prompt objects in Python):

```python
system = ChatPromptTemplate.from_messages([("system", "You are terse.")])
task   = ChatPromptTemplate.from_messages([("human", "Summarise: {text}")])
prompt = system + task
```

For bigger structures there's `PipelinePromptTemplate`, which builds a final prompt out of
named sub-prompts. In practice, most teams compose with partials and plain string building —
`PipelinePromptTemplate` is worth *recognising* more than reaching for.

### 3.7 Templates are Runnables

```js
await prompt.invoke({ ... })                    // → ChatPromptValue
prompt.pipe(model)                              // → a Runnable chain
await prompt.pipe(model).invoke({ ... })        // → AIMessage
```

That last line is tomorrow's entire lesson in one expression. A `ChatPromptValue` knows how to
become `BaseMessage[]` (`.toChatMessages()`) or a plain string (`.toString()`), which is why the
same template works with both chat models and old completion models.

---

## 4. Code — JavaScript

### 4.1 The basics

```js
// day05-basics.js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";
import { PromptTemplate, ChatPromptTemplate } from "@langchain/core/prompts";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });

// ── PromptTemplate: one string ───────────────────────────────────────────
const single = PromptTemplate.fromTemplate(
  "Summarise the following in exactly {n} bullet points:\n\n{text}"
);
console.log(await single.format({ n: 3, text: "LangChain is a framework for LLM apps..." }));
console.log("declared variables:", single.inputVariables);   // [ 'n', 'text' ]

// ── ChatPromptTemplate: a message list ───────────────────────────────────
const chat = ChatPromptTemplate.fromMessages([
  ["system", "You are StudyBuddy. Explain at a {level} level. Be concise."],
  ["human", "{question}"],
]);

const value = await chat.invoke({ level: "beginner", question: "What is an embedding?" });
console.log(value.toChatMessages());     // real SystemMessage + HumanMessage objects

// ── It's a Runnable, so it pipes ─────────────────────────────────────────
const chain = chat.pipe(model);
const res = await chain.invoke({ level: "expert", question: "What is an embedding?" });
console.log("\n", res.text);

// ── Escaping literal braces ──────────────────────────────────────────────
const withJson = ChatPromptTemplate.fromMessages([
  ["system", 'Respond as JSON like {{"label": "BUG"}} — nothing else.'],
  ["human", "{ticket}"],
]);
console.log((await withJson.invoke({ ticket: "App crashes" })).toChatMessages()[0].content);
```

### 4.2 MessagesPlaceholder — a clean chatbot

```js
// day05-placeholder.js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";
import { ChatPromptTemplate, MessagesPlaceholder } from "@langchain/core/prompts";
import { HumanMessage } from "@langchain/core/messages";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0.5 });

const prompt = ChatPromptTemplate.fromMessages([
  ["system", "You are StudyBuddy, a {level}-level tutor. Answer in 2 sentences."],
  new MessagesPlaceholder({ variableName: "history", optional: true }),
  ["human", "{question}"],
]);

const chain = prompt.pipe(model);

let history = [];

async function turn(question, level = "beginner") {
  const res = await chain.invoke({ level, history, question });
  history = [...history, new HumanMessage(question), res];   // grow history
  return res.text;
}

console.log("1:", await turn("What is a vector database?"));
console.log("2:", await turn("Why not just use Postgres?"));
console.log("3:", await turn("Summarise what we discussed."));
console.log(`\nhistory: ${history.length} messages`);
```

Compare this to Day 04's chatbot: the prompt structure is now **declarative and reusable**,
and the history is just a variable.

### 4.3 Few-shot

```js
// day05-fewshot.js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";
import { ChatPromptTemplate, FewShotChatMessagePromptTemplate } from "@langchain/core/prompts";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });

const examples = [
  { input: "I was charged twice this month.",   output: "BILLING" },
  { input: "The app crashes when I tap Settings.", output: "BUG" },
  { input: "Can you add dark mode?",            output: "FEATURE" },
  { input: "My invoice shows the wrong VAT.",   output: "BILLING" },
];

const fewShot = new FewShotChatMessagePromptTemplate({
  examplePrompt: ChatPromptTemplate.fromMessages([["human", "{input}"], ["ai", "{output}"]]),
  examples,
  inputVariables: [],
});

const prompt = ChatPromptTemplate.fromMessages([
  ["system", "Classify support tickets as BILLING, BUG, or FEATURE. Reply with the label only."],
  fewShot,
  ["human", "{input}"],
]);

// See exactly what gets sent:
const preview = await prompt.invoke({ input: "Login does nothing on Safari." });
console.log(preview.toChatMessages().map((m) => `${m.getType()}: ${m.content}`).join("\n"));

console.log("\n─── results ───");
const chain = prompt.pipe(model);
for (const t of ["Login does nothing on Safari.",
                 "I'd love a CSV export button.",
                 "Refund never arrived."]) {
  console.log(`${t.padEnd(40)} → ${(await chain.invoke({ input: t })).text.trim()}`);
}
```

### 4.4 Partials and composition

```js
// day05-partials.js
import { ChatPromptTemplate } from "@langchain/core/prompts";

const base = ChatPromptTemplate.fromMessages([
  ["system", "You are a {role}. Today is {date}. Respond in {language}."],
  ["human", "{question}"],
]);

// Bake in what you know; leave the rest.
const tutor = await base.partial({
  role: "patient tutor",
  date: () => new Date().toISOString().slice(0, 10),   // evaluated at RENDER time
});

console.log("remaining variables:", tutor.inputVariables);   // [ 'language', 'question' ]

const value = await tutor.invoke({ language: "English", question: "What is LCEL?" });
console.log(value.toChatMessages()[0].content);

// Composition
const persona = ChatPromptTemplate.fromMessages([["system", "You are terse and precise."]]);
const task    = ChatPromptTemplate.fromMessages([["human", "Summarise: {text}"]]);
const combined = persona.concat(task);
console.log("\ncombined vars:", combined.inputVariables);
```

### 4.5 A reusable prompt library

This is how real projects organise prompts — one module, versioned, testable.

```js
// prompts.js
import { ChatPromptTemplate, MessagesPlaceholder } from "@langchain/core/prompts";

export const TUTOR = ChatPromptTemplate.fromMessages([
  ["system",
    "You are StudyBuddy, a patient tutor.\n" +
    "Level: {level}\n" +
    "Rules:\n" +
    "- Use one everyday analogy.\n" +
    "- Maximum {maxSentences} sentences.\n" +
    "- End with one question that checks understanding."],
  new MessagesPlaceholder({ variableName: "history", optional: true }),
  ["human", "{question}"],
]);

export const SUMMARISER = ChatPromptTemplate.fromMessages([
  ["system", "Summarise text into exactly {n} bullets. No preamble."],
  ["human", "{text}"],
]);

export const CLASSIFIER = ChatPromptTemplate.fromMessages([
  ["system", "Classify the ticket. Reply with exactly one of: {labels}. No other text."],
  ["human", "{ticket}"],
]);
```

```js
// day05-library.js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";
import { TUTOR, SUMMARISER, CLASSIFIER } from "./prompts.js";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });

console.log((await TUTOR.pipe(model).invoke({
  level: "beginner", maxSentences: 3, history: [], question: "What is an API?",
})).text);

console.log("\n" + (await CLASSIFIER.pipe(model).invoke({
  labels: "BILLING, BUG, FEATURE", ticket: "Charged twice again.",
})).text);
```

---

## 5. Code — Python

### 5.1 The basics

```python
# day05_basics.py
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

# ── PromptTemplate: one string ───────────────────────────────────────────
single = PromptTemplate.from_template(
    "Summarise the following in exactly {n} bullet points:\n\n{text}"
)
print(single.format(n=3, text="LangChain is a framework for LLM apps..."))
print("declared variables:", single.input_variables)   # ['n', 'text']

# ── ChatPromptTemplate: a message list ───────────────────────────────────
chat = ChatPromptTemplate.from_messages([
    ("system", "You are StudyBuddy. Explain at a {level} level. Be concise."),
    ("human", "{question}"),
])

value = chat.invoke({"level": "beginner", "question": "What is an embedding?"})
print(value.to_messages())     # real SystemMessage + HumanMessage objects

# ── It's a Runnable, so it pipes ─────────────────────────────────────────
chain = chat | model
res = chain.invoke({"level": "expert", "question": "What is an embedding?"})
print("\n", res.content)

# ── Escaping literal braces ──────────────────────────────────────────────
with_json = ChatPromptTemplate.from_messages([
    ("system", 'Respond as JSON like {{"label": "BUG"}} — nothing else.'),
    ("human", "{ticket}"),
])
print(with_json.invoke({"ticket": "App crashes"}).to_messages()[0].content)
```

> 🔑 Look at `chat | model`. Python's `|` operator is LCEL's pipe. JS uses `.pipe()`.
> That's the whole syntactic difference — tomorrow's topic.

### 5.2 MessagesPlaceholder — a clean chatbot

```python
# day05_placeholder.py
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.5)

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are StudyBuddy, a {level}-level tutor. Answer in 2 sentences."),
    MessagesPlaceholder("history", optional=True),
    ("human", "{question}"),
])

chain = prompt | model

history = []

def turn(question, level="beginner"):
    global history
    res = chain.invoke({"level": level, "history": history, "question": question})
    history = history + [HumanMessage(question), res]      # grow history
    return res.content

print("1:", turn("What is a vector database?"))
print("2:", turn("Why not just use Postgres?"))
print("3:", turn("Summarise what we discussed."))
print(f"\nhistory: {len(history)} messages")
```

### 5.3 Few-shot

```python
# day05_fewshot.py
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, FewShotChatMessagePromptTemplate

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

examples = [
    {"input": "I was charged twice this month.",      "output": "BILLING"},
    {"input": "The app crashes when I tap Settings.", "output": "BUG"},
    {"input": "Can you add dark mode?",               "output": "FEATURE"},
    {"input": "My invoice shows the wrong VAT.",      "output": "BILLING"},
]

few_shot = FewShotChatMessagePromptTemplate(
    example_prompt=ChatPromptTemplate.from_messages([("human", "{input}"), ("ai", "{output}")]),
    examples=examples,
)

prompt = ChatPromptTemplate.from_messages([
    ("system", "Classify support tickets as BILLING, BUG, or FEATURE. Reply with the label only."),
    few_shot,
    ("human", "{input}"),
])

# See exactly what gets sent:
preview = prompt.invoke({"input": "Login does nothing on Safari."})
print("\n".join(f"{m.type}: {m.content}" for m in preview.to_messages()))

print("\n─── results ───")
chain = prompt | model
for t in ["Login does nothing on Safari.",
          "I'd love a CSV export button.",
          "Refund never arrived."]:
    print(f"{t:<40} → {chain.invoke({'input': t}).content.strip()}")
```

### 5.4 Partials and composition

```python
# day05_partials.py
from datetime import date
from langchain_core.prompts import ChatPromptTemplate

base = ChatPromptTemplate.from_messages([
    ("system", "You are a {role}. Today is {date}. Respond in {language}."),
    ("human", "{question}"),
])

# Bake in what you know; leave the rest.
tutor = base.partial(
    role="patient tutor",
    date=lambda: date.today().isoformat(),      # evaluated at RENDER time
)

print("remaining variables:", tutor.input_variables)   # ['language', 'question']

value = tutor.invoke({"language": "English", "question": "What is LCEL?"})
print(value.to_messages()[0].content)

# Composition — Python supports `+` on prompt templates
persona = ChatPromptTemplate.from_messages([("system", "You are terse and precise.")])
task    = ChatPromptTemplate.from_messages([("human", "Summarise: {text}")])
combined = persona + task
print("\ncombined vars:", combined.input_variables)
```

### 5.5 A reusable prompt library

```python
# prompts.py
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

TUTOR = ChatPromptTemplate.from_messages([
    ("system",
     "You are StudyBuddy, a patient tutor.\n"
     "Level: {level}\n"
     "Rules:\n"
     "- Use one everyday analogy.\n"
     "- Maximum {max_sentences} sentences.\n"
     "- End with one question that checks understanding."),
    MessagesPlaceholder("history", optional=True),
    ("human", "{question}"),
])

SUMMARISER = ChatPromptTemplate.from_messages([
    ("system", "Summarise text into exactly {n} bullets. No preamble."),
    ("human", "{text}"),
])

CLASSIFIER = ChatPromptTemplate.from_messages([
    ("system", "Classify the ticket. Reply with exactly one of: {labels}. No other text."),
    ("human", "{ticket}"),
])
```

```python
# day05_library.py
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from prompts import TUTOR, CLASSIFIER

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

print((TUTOR | model).invoke({
    "level": "beginner", "max_sentences": 3, "history": [], "question": "What is an API?",
}).content)

print("\n" + (CLASSIFIER | model).invoke({
    "labels": "BILLING, BUG, FEATURE", "ticket": "Charged twice again.",
}).content)
```

### 🔁 JS ↔ Python differences you just saw

| | JavaScript | Python |
|---|---|---|
| Import path | `@langchain/core/prompts` | `langchain_core.prompts` |
| Factory | `ChatPromptTemplate.fromMessages([...])` | `ChatPromptTemplate.from_messages([...])` |
| Render | `await t.format({...})` / `.invoke({...})` | `t.format(...)` / `.invoke({...})` |
| Pipe | `prompt.pipe(model)` | `prompt \| model` |
| Placeholder | `new MessagesPlaceholder({variableName, optional})` | `MessagesPlaceholder("history", optional=True)` |
| To messages | `value.toChatMessages()` | `value.to_messages()` |
| Message role | `m.getType()` | `m.type` |
| Compose | `a.concat(b)` | `a + b` |
| Declared vars | `t.inputVariables` | `t.input_variables` |
| Partial | `await t.partial({...})` — async | `t.partial(...)` — sync |
| Variable naming | `maxSentences` | `max_sentences` |

---

## 6. Under the hood

### What `.invoke()` on a template actually does

```
prompt.invoke({ level: "beginner", question: "What is RAG?" })
        │
        ▼
 1. Validate: every declared inputVariable is present
    missing → "Missing value for input variable `level`"
        │
        ▼
 2. Merge partial variables (calling any functions NOW)
        │
        ▼
 3. For each message template:
      ("system", "...{level}...")  → format the string → SystemMessage
      MessagesPlaceholder("hist")  → SPLICE the array in, unchanged
      FewShot template             → expand into N messages
        │
        ▼
 4. Wrap in ChatPromptValue
        │
        ▼
    .toChatMessages() → BaseMessage[]     (what a chat model wants)
    .toString()       → "System: ...\nHuman: ..."  (what an old LLM wants)
```

**Step 1 is the underrated one.** String concatenation fails silently — a typo gives you the
literal text `"undefined"` in your prompt and a subtly worse answer that you'll debug for an
hour. A template throws immediately, with the variable name.

**Step 4 is why the same template works with both model types.** `ChatPromptValue` is a
two-faced object: chat models call `toChatMessages()`, completion models call `toString()`.

### Why `{` needs escaping

The formatter is (by default) f-string-style: it scans for `{...}` and substitutes. It has no
way to know your `{"label": "BUG"}` is JSON rather than a variable named `"label": "BUG"`.
Doubling (`{{`) is the standard escape.

If you have a lot of literal braces, use mustache templating instead:

```js
ChatPromptTemplate.fromMessages([["human", "Hello {{name}}"]], { templateFormat: "mustache" });
```
```python
ChatPromptTemplate.from_messages([("human", "Hello {{name}}")], template_format="mustache")
```

With mustache, `{single}` braces are literal and `{{double}}` are variables — the inverse. Handy
for prompts full of JSON or code.

### Why templates are Runnables

Because `ChatPromptTemplate` implements `invoke`/`stream`/`batch`, `prompt.pipe(model)` gives
you a chain where:

- `chain.invoke({vars})` renders then calls the model
- `chain.stream({vars})` renders then **streams** the model — stream propagation is free
- `chain.batch([{vars}, {vars}])` renders and calls in parallel
- callbacks fire for *both* steps, so tracing shows the rendered prompt

You get all of that without writing a line of glue. That's the payoff of yesterday's interface
discussion, and it's tomorrow's whole topic.

<details>
<summary>📜 Legacy note: prompt patterns in old tutorials</summary>

| Legacy (0.x) | Modern (1.x) |
|---|---|
| `LLMChain(llm=model, prompt=prompt)` | `prompt \| model` |
| `chain.run(text="...")` | `chain.invoke({"text": "..."})` |
| `chain.predict(x="y")` | `chain.invoke({"x": "y"})` |
| `ConversationChain` + memory object | `MessagesPlaceholder` + LangGraph checkpointer |
| `FewShotPromptTemplate` (string-based) | `FewShotChatMessagePromptTemplate` (message-based) |

If an interviewer asks "what replaced `LLMChain`?" the answer is: **LCEL composition**. It's not
a renamed class — it's the realisation that a chain is just `prompt | model | parser`, and you
don't need a class for that.
</details>

---

## 7. Common mistakes

**❌ Unescaped braces in JSON examples**

```js
["system", 'Reply like {"label": "BUG"}']
// Error: Missing value for input variable `"label": "BUG"`
```
✅ Double them: `{{"label": "BUG"}}` — or use `templateFormat: "mustache"`.

---

**❌ Passing a string where a `MessagesPlaceholder` expects an array**

```js
await prompt.invoke({ history: "Human: hi\nAI: hello" });   // ❌
```
✅ Pass real message objects: `history: [new HumanMessage("hi"), new AIMessage("hello")]`.

---

**❌ A non-optional placeholder on the first turn**

```js
new MessagesPlaceholder("history")
await prompt.invoke({ question: "hi" });   // ❌ Missing value for `history`
```
✅ Either mark it `optional: true`, or always pass `history: []`.

---

**❌ Putting user input in the template *string* instead of a variable**

```js
ChatPromptTemplate.fromMessages([["human", userInput]]);   // ❌
```
If `userInput` contains `{` you get a template error — and worse, the user now controls your
template. ✅ Always `["human", "{question}"]` with the value passed to `invoke`.

---

**❌ Rebuilding the template on every request**

```js
app.post("/chat", async (req) => {
  const prompt = ChatPromptTemplate.fromMessages([...]);   // parsed every request
});
```
✅ Build once at module scope. Templates are immutable and reusable.

---

**❌ Baking the user's question into the system message**

```js
["system", `You are a tutor. Answer this: ${question}`]
```
✅ System = stable instructions, human = the question. It's better for quality, better for
prompt caching (a stable prefix caches; a changing one doesn't), and safer against injection.

---

**❌ Trusting `.format()` output as your source of truth for a chat model**

`.format()` gives you a *string* rendering. What actually gets sent is `.invoke().toChatMessages()`.
✅ Debug with the message list, not the flattened string.

---

## 8. Exercises

### Exercise 1 — Template a Day 02 prompt ●○○○○

Take the sentiment+aspect classifier you wrote on Day 02 (a giant template string) and convert
it to a `ChatPromptTemplate` with a `FewShotChatMessagePromptTemplate`. Print the rendered
messages to confirm the examples become real Human/AI turns.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";
import { ChatPromptTemplate, FewShotChatMessagePromptTemplate } from "@langchain/core/prompts";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });

const examples = [
  { review: "Screen is gorgeous but it's overpriced.", sentiment: "mixed",    aspect: "price" },
  { review: "Dies after three hours. Useless.",          sentiment: "negative", aspect: "battery" },
  { review: "Everything about it is perfect.",           sentiment: "positive", aspect: "none" },
  { review: "Feels cheap and plasticky for the money.",  sentiment: "negative", aspect: "build" },
];

const fewShot = new FewShotChatMessagePromptTemplate({
  examplePrompt: ChatPromptTemplate.fromMessages([
    ["human", "{review}"],
    ["ai", "SENTIMENT: {sentiment}\nASPECT: {aspect}"],
  ]),
  examples,
  inputVariables: [],
});

const prompt = ChatPromptTemplate.fromMessages([
  ["system",
   "Analyse product reviews. Output exactly two lines:\n" +
   "SENTIMENT: positive|negative|mixed\n" +
   "ASPECT: {aspects}"],
  fewShot,
  ["human", "{review}"],
]);

const ASPECTS = "battery|camera|price|build|software|none";

// Inspect what actually gets sent:
const preview = await prompt.invoke({ aspects: ASPECTS, review: "Camera is amazing." });
console.log(preview.toChatMessages().map((m) => `[${m.getType()}] ${m.content}`).join("\n"));

console.log("\n─── results ───");
const chain = prompt.pipe(model);
for (const r of ["Battery lasts two days but the camera is mediocre.",
                 "Oh fantastic, another update that broke the alarm. Love it."]) {
  const out = (await chain.invoke({ aspects: ASPECTS, review: r })).text.replace(/\n/g, " | ");
  console.log(`${r.slice(0, 45).padEnd(47)} → ${out}`);
}
```

**Python**
```python
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, FewShotChatMessagePromptTemplate

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

examples = [
    {"review": "Screen is gorgeous but it's overpriced.", "sentiment": "mixed",    "aspect": "price"},
    {"review": "Dies after three hours. Useless.",         "sentiment": "negative", "aspect": "battery"},
    {"review": "Everything about it is perfect.",          "sentiment": "positive", "aspect": "none"},
    {"review": "Feels cheap and plasticky for the money.", "sentiment": "negative", "aspect": "build"},
]

few_shot = FewShotChatMessagePromptTemplate(
    example_prompt=ChatPromptTemplate.from_messages([
        ("human", "{review}"),
        ("ai", "SENTIMENT: {sentiment}\nASPECT: {aspect}"),
    ]),
    examples=examples,
)

prompt = ChatPromptTemplate.from_messages([
    ("system",
     "Analyse product reviews. Output exactly two lines:\n"
     "SENTIMENT: positive|negative|mixed\n"
     "ASPECT: {aspects}"),
    few_shot,
    ("human", "{review}"),
])

ASPECTS = "battery|camera|price|build|software|none"

preview = prompt.invoke({"aspects": ASPECTS, "review": "Camera is amazing."})
print("\n".join(f"[{m.type}] {m.content}" for m in preview.to_messages()))

print("\n─── results ───")
chain = prompt | model
for r in ["Battery lasts two days but the camera is mediocre.",
          "Oh fantastic, another update that broke the alarm. Love it."]:
    out = chain.invoke({"aspects": ASPECTS, "review": r}).content.replace("\n", " | ")
    print(f"{r[:45]:<47} → {out}")
```

**What the preview shows:** the four examples became **eight messages** — alternating human/ai
turns. The model now sees a conversation it should continue, not a wall of text it should
imitate. That structural difference is measurably more reliable, and it's free.

Notice the aspect list is now a *variable* (`{aspects}`), so adding a new category is a
one-line config change instead of a prompt edit.
</details>

---

### Exercise 2 — A prompt with a dynamic system message ●●○○○

Build a template where the system message adapts to a `mode` variable (`"explain"`, `"quiz"`,
`"debug"`), using partials so each mode is a separate reusable prompt object built from one
base. Test all three modes on the same question.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";
import { ChatPromptTemplate, MessagesPlaceholder } from "@langchain/core/prompts";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0.4 });

const MODES = {
  explain: "Explain the concept clearly with one everyday analogy. Max 4 sentences.",
  quiz:    "Do NOT explain. Ask 3 short questions that test whether the user understands.",
  debug:   "Assume the user has a bug. List the 3 most likely causes and how to check each.",
};

const BASE = ChatPromptTemplate.fromMessages([
  ["system",
   "You are StudyBuddy, a {level}-level tutor.\n" +
   "MODE INSTRUCTIONS: {modeInstructions}\n" +
   "Never break character."],
  new MessagesPlaceholder({ variableName: "history", optional: true }),
  ["human", "{question}"],
]);

// One base, three specialised prompts:
const PROMPTS = Object.fromEntries(
  await Promise.all(
    Object.entries(MODES).map(async ([mode, instructions]) => [
      mode,
      await BASE.partial({ modeInstructions: instructions }),
    ])
  )
);

const QUESTION = "How does a vector database find similar items?";

for (const [mode, prompt] of Object.entries(PROMPTS)) {
  const res = await prompt.pipe(model).invoke({ level: "beginner", question: QUESTION });
  console.log(`\n═══ ${mode.toUpperCase()} ═══\n${res.text.trim()}`);
}
```

**Python**
```python
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.4)

MODES = {
    "explain": "Explain the concept clearly with one everyday analogy. Max 4 sentences.",
    "quiz":    "Do NOT explain. Ask 3 short questions that test whether the user understands.",
    "debug":   "Assume the user has a bug. List the 3 most likely causes and how to check each.",
}

BASE = ChatPromptTemplate.from_messages([
    ("system",
     "You are StudyBuddy, a {level}-level tutor.\n"
     "MODE INSTRUCTIONS: {mode_instructions}\n"
     "Never break character."),
    MessagesPlaceholder("history", optional=True),
    ("human", "{question}"),
])

# One base, three specialised prompts:
PROMPTS = {mode: BASE.partial(mode_instructions=instr) for mode, instr in MODES.items()}

QUESTION = "How does a vector database find similar items?"

for mode, prompt in PROMPTS.items():
    res = (prompt | model).invoke({"level": "beginner", "question": QUESTION})
    print(f"\n═══ {mode.upper()} ═══\n{res.content.strip()}")
```

**Why partials rather than an `if`:** each specialised prompt is a real object you can export,
test, trace and version independently — while the shared structure (persona, history, rules)
lives in exactly one place. Change the persona once and all three modes update.

This pattern scales directly to production: mode-per-partial for a handful, and a router chain
picking between them for many (Day 08).
</details>

---

### Exercise 3 — Template validator ●●●○○

Write `validateTemplate(template, sampleVars)` that: lists declared variables, reports which
sample vars are missing/extra, attempts a render, and catches unescaped-brace errors with a
helpful message. Test it against a deliberately broken template containing raw JSON.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import { ChatPromptTemplate } from "@langchain/core/prompts";

async function validateTemplate(name, template, sampleVars) {
  console.log(`\n═══ ${name} ═══`);

  const declared = new Set(template.inputVariables);
  const provided = new Set(Object.keys(sampleVars));

  const missing = [...declared].filter((v) => !provided.has(v));
  const extra   = [...provided].filter((v) => !declared.has(v));

  console.log("declared:", [...declared].join(", ") || "(none)");
  if (missing.length) console.log("❌ missing:", missing.join(", "));
  if (extra.length)   console.log("⚠️  extra (ignored):", extra.join(", "));

  try {
    const value = await template.invoke(sampleVars);
    const msgs = value.toChatMessages();
    console.log(`✅ renders — ${msgs.length} messages`);
    msgs.forEach((m) => console.log(`   [${m.getType()}] ${String(m.content).slice(0, 70)}`));
    return true;
  } catch (err) {
    console.log(`❌ render failed: ${err.message}`);
    if (/Missing value for input variable/.test(err.message)) {
      const v = err.message.match(/`(.+?)`/)?.[1] ?? "";
      if (/["':{}]/.test(v)) {
        console.log(
          `   💡 "${v}" looks like literal JSON, not a variable.\n` +
          `      Escape the braces: {{ and }} — or use templateFormat: "mustache".`
        );
      }
    }
    return false;
  }
}

// ── good ──
await validateTemplate(
  "tutor",
  ChatPromptTemplate.fromMessages([["system", "You are a {role}."], ["human", "{question}"]]),
  { role: "tutor", question: "What is RAG?", unused: "x" }
);

// ── broken: raw JSON in the template ──
await validateTemplate(
  "json-broken",
  ChatPromptTemplate.fromMessages([["system", 'Reply like {"label": "BUG"}'], ["human", "{t}"]]),
  { t: "app crashes" }
);

// ── fixed ──
await validateTemplate(
  "json-fixed",
  ChatPromptTemplate.fromMessages([["system", 'Reply like {{"label": "BUG"}}'], ["human", "{t}"]]),
  { t: "app crashes" }
);
```

**Python**
```python
import re
from langchain_core.prompts import ChatPromptTemplate

def validate_template(name, template, sample_vars):
    print(f"\n═══ {name} ═══")

    declared = set(template.input_variables)
    provided = set(sample_vars)

    missing = declared - provided
    extra = provided - declared

    print("declared:", ", ".join(sorted(declared)) or "(none)")
    if missing:
        print("❌ missing:", ", ".join(sorted(missing)))
    if extra:
        print("⚠️  extra (ignored):", ", ".join(sorted(extra)))

    try:
        msgs = template.invoke(sample_vars).to_messages()
        print(f"✅ renders — {len(msgs)} messages")
        for m in msgs:
            print(f"   [{m.type}] {str(m.content)[:70]}")
        return True
    except Exception as err:
        print(f"❌ render failed: {err}")
        m = re.search(r"'(.+?)'", str(err))
        var = m.group(1) if m else ""
        if re.search(r"[\"':{}]", var):
            print(f'   💡 "{var}" looks like literal JSON, not a variable.\n'
                  '      Escape the braces: {{ and }} — or use template_format="mustache".')
        return False


# ── good ──
validate_template(
    "tutor",
    ChatPromptTemplate.from_messages([("system", "You are a {role}."), ("human", "{question}")]),
    {"role": "tutor", "question": "What is RAG?", "unused": "x"},
)

# ── broken: raw JSON in the template ──
try:
    broken = ChatPromptTemplate.from_messages([
        ("system", 'Reply like {"label": "BUG"}'), ("human", "{t}")
    ])
    validate_template("json-broken", broken, {"t": "app crashes"})
except Exception as e:
    print(f"\n═══ json-broken ═══\n❌ construction failed: {e}")

# ── fixed ──
validate_template(
    "json-fixed",
    ChatPromptTemplate.from_messages([("system", 'Reply like {{"label": "BUG"}}'), ("human", "{t}")]),
    {"t": "app crashes"},
)
```

**Note the language difference you'll hit:** Python often raises at *construction* time when it
parses the template, while JS tends to raise at *render* time. Hence the extra `try` around
construction in the Python version.

**Why write this at all:** in a real codebase this becomes a unit test that runs in CI —
"every prompt in `prompts.py` renders with its sample variables." That catches the entire class
of template bugs before deploy, which is exactly the kind of thing that separates a prompt
*library* from prompt *strings*.
</details>

---

### Exercise 4 — Prompt A/B test with templates ●●●○○

Build two versions of a summarisation prompt (v1: minimal, v2: detailed with constraints and a
few-shot example). Run both over 5 texts, and score outputs on: bullet count correctness,
average length, and whether any preamble ("Here's a summary:") leaked in. Report which wins.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";
import { ChatPromptTemplate, FewShotChatMessagePromptTemplate } from "@langchain/core/prompts";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });

const TEXTS = [
  "LangChain is a framework for building applications with LLMs. It provides abstractions for models, prompts, and retrieval, plus LCEL for composing them into pipelines.",
  "Vector databases store high-dimensional embeddings and support approximate nearest-neighbour search using indexes like HNSW. They trade a little recall for large speed gains.",
  "RAG combines retrieval with generation. Documents are chunked, embedded and stored; at query time the most relevant chunks are retrieved and passed to the model as context.",
  "Prompt injection occurs when untrusted input contains instructions the model follows. Mitigations include role separation and delimiting, but the real boundary is authorisation.",
  "Streaming sends tokens as they are generated. It does not reduce total generation time, but it dramatically improves perceived latency by lowering time-to-first-token.",
];

const V1 = ChatPromptTemplate.fromMessages([
  ["human", "Summarise this in {n} bullets:\n\n{text}"],
]);

const exampleFewShot = new FewShotChatMessagePromptTemplate({
  examplePrompt: ChatPromptTemplate.fromMessages([["human", "{input}"], ["ai", "{output}"]]),
  examples: [{
    input: "HTTP caching stores responses so repeat requests are faster. Cache-Control headers govern freshness, and ETags allow revalidation.",
    output: "- Caching stores responses to speed up repeat requests\n- Cache-Control headers set freshness rules\n- ETags let clients revalidate stale entries",
  }],
  inputVariables: [],
});

const V2 = ChatPromptTemplate.fromMessages([
  ["system",
   "You produce summaries as bullet lists.\n" +
   "Rules:\n" +
   "- Output EXACTLY {n} bullets, each starting with '- '\n" +
   "- Each bullet is one line, max 15 words\n" +
   "- No preamble, no heading, no closing remark\n" +
   "- Never start with 'Here' or 'This'"],
  exampleFewShot,
  ["human", "{text}"],
]);

const PREAMBLE = /^(here|this|sure|certainly|below|the following)/i;

async function score(name, prompt, n = 3) {
  const chain = prompt.pipe(model);
  let correctCount = 0, preambles = 0, totalWords = 0;

  for (const text of TEXTS) {
    const out = (await chain.invoke({ n, text })).text.trim();
    const bullets = out.split("\n").filter((l) => /^\s*[-•*]/.test(l));

    if (bullets.length === n) correctCount++;
    if (PREAMBLE.test(out)) preambles++;
    totalWords += out.split(/\s+/).length;
  }

  console.log(
    `${name.padEnd(4)} | exact ${n} bullets: ${correctCount}/${TEXTS.length} | ` +
    `preamble leaks: ${preambles} | avg words: ${(totalWords / TEXTS.length).toFixed(0)}`
  );
  return correctCount;
}

console.log("prompt | bullet accuracy | preamble leaks | length");
console.log("-".repeat(66));
const v1 = await score("V1", V1);
const v2 = await score("V2", V2);
console.log(`\nwinner: ${v2 >= v1 ? "V2" : "V1"}`);
```

**Python**
```python
import re
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, FewShotChatMessagePromptTemplate

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

TEXTS = [
    "LangChain is a framework for building applications with LLMs. It provides abstractions for models, prompts, and retrieval, plus LCEL for composing them into pipelines.",
    "Vector databases store high-dimensional embeddings and support approximate nearest-neighbour search using indexes like HNSW. They trade a little recall for large speed gains.",
    "RAG combines retrieval with generation. Documents are chunked, embedded and stored; at query time the most relevant chunks are retrieved and passed to the model as context.",
    "Prompt injection occurs when untrusted input contains instructions the model follows. Mitigations include role separation and delimiting, but the real boundary is authorisation.",
    "Streaming sends tokens as they are generated. It does not reduce total generation time, but it dramatically improves perceived latency by lowering time-to-first-token.",
]

V1 = ChatPromptTemplate.from_messages([
    ("human", "Summarise this in {n} bullets:\n\n{text}"),
])

example_few_shot = FewShotChatMessagePromptTemplate(
    example_prompt=ChatPromptTemplate.from_messages([("human", "{input}"), ("ai", "{output}")]),
    examples=[{
        "input": "HTTP caching stores responses so repeat requests are faster. Cache-Control headers govern freshness, and ETags allow revalidation.",
        "output": "- Caching stores responses to speed up repeat requests\n- Cache-Control headers set freshness rules\n- ETags let clients revalidate stale entries",
    }],
)

V2 = ChatPromptTemplate.from_messages([
    ("system",
     "You produce summaries as bullet lists.\n"
     "Rules:\n"
     "- Output EXACTLY {n} bullets, each starting with '- '\n"
     "- Each bullet is one line, max 15 words\n"
     "- No preamble, no heading, no closing remark\n"
     "- Never start with 'Here' or 'This'"),
    example_few_shot,
    ("human", "{text}"),
])

PREAMBLE = re.compile(r"^(here|this|sure|certainly|below|the following)", re.I)

def score(name, prompt, n=3):
    chain = prompt | model
    correct = preambles = total_words = 0

    for text in TEXTS:
        out = chain.invoke({"n": n, "text": text}).content.strip()
        bullets = [l for l in out.split("\n") if re.match(r"^\s*[-•*]", l)]

        if len(bullets) == n:
            correct += 1
        if PREAMBLE.match(out):
            preambles += 1
        total_words += len(out.split())

    print(f"{name:<4} | exact {n} bullets: {correct}/{len(TEXTS)} | "
          f"preamble leaks: {preambles} | avg words: {total_words / len(TEXTS):.0f}")
    return correct

print("prompt | bullet accuracy | preamble leaks | length")
print("-" * 66)
v1 = score("V1", V1)
v2 = score("V2", V2)
print(f"\nwinner: {'V2' if v2 >= v1 else 'V1'}")
```

**Typical result:** V1 gets the bullet count right maybe 3/5 and leaks a preamble 2–3 times.
V2 gets 5/5 with no preamble, at the cost of ~150 extra input tokens per call.

**The generalisable lesson:** the single most effective anti-preamble technique is the few-shot
example — showing one output that starts directly with `- ` beats any amount of "do not include
a preamble" instruction. Models imitate examples more faithfully than they obey prohibitions.
</details>

---

### Exercise 5 — StudyBuddy v1 prompt system ●●●●○

Build a proper prompt module for StudyBuddy with: a shared persona partial, three modes
(explain/quiz/review), a level variable, an optional history placeholder, a few-shot block for
the quiz mode only, and a `renderPreview(mode, vars)` debug helper that prints exactly what will
be sent. Then wire it to a CLI where `/mode` switches templates mid-conversation with history
intact.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
// studybuddy-prompts.js
import { ChatPromptTemplate, MessagesPlaceholder,
         FewShotChatMessagePromptTemplate } from "@langchain/core/prompts";

const PERSONA =
  "You are StudyBuddy, a patient technical tutor.\n" +
  "Audience level: {level}\n" +
  "Never invent facts. If unsure, say so.";

const quizFewShot = new FewShotChatMessagePromptTemplate({
  examplePrompt: ChatPromptTemplate.fromMessages([["human", "{topic}"], ["ai", "{questions}"]]),
  examples: [{
    topic: "HTTP caching",
    questions:
      "1. What does Cache-Control: max-age=60 tell the browser?\n" +
      "2. When would an ETag be more useful than an expiry time?\n" +
      "3. Why can caching cause users to see stale data after a deploy?",
  }],
  inputVariables: [],
});

const MODE_RULES = {
  explain: "Explain the concept with exactly one everyday analogy, then a 2-sentence technical " +
           "definition. Maximum {maxSentences} sentences total.",
  quiz:    "Do NOT explain anything. Output exactly 3 numbered questions that test understanding. " +
           "Increasing difficulty. No answers.",
  review:  "The user will paste code or a design. Identify the 3 most important issues, each as " +
           "'ISSUE: ... / WHY: ... / FIX: ...'. Be direct.",
};

function buildPrompt(mode) {
  const messages = [["system", `${PERSONA}\n\nMODE: ${mode}\n${MODE_RULES[mode]}`]];
  if (mode === "quiz") messages.push(quizFewShot);
  messages.push(
    new MessagesPlaceholder({ variableName: "history", optional: true }),
    ["human", "{input}"]
  );
  return ChatPromptTemplate.fromMessages(messages);
}

export const PROMPTS = {
  explain: buildPrompt("explain"),
  quiz:    buildPrompt("quiz"),
  review:  buildPrompt("review"),
};

export async function renderPreview(mode, vars) {
  const msgs = (await PROMPTS[mode].invoke(vars)).toChatMessages();
  console.log(`\n┌─ rendered prompt: ${mode} (${msgs.length} messages) ─`);
  for (const m of msgs) {
    const body = String(m.content).split("\n").map((l) => `│   ${l}`).join("\n");
    console.log(`│ [${m.getType()}]\n${body}`);
  }
  console.log("└" + "─".repeat(40));
}
```

```js
// studybuddy-v1.js
import "dotenv/config";
import readline from "node:readline/promises";
import { ChatGroq } from "@langchain/groq";
import { HumanMessage } from "@langchain/core/messages";
import { PROMPTS, renderPreview } from "./studybuddy-prompts.js";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0.5 });

let mode = "explain";
let level = "beginner";
let history = [];

const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
console.log("StudyBuddy v1 — /mode explain|quiz|review · /level · /preview · /reset · /exit\n");

while (true) {
  const input = (await rl.question(`you [${mode}|${level}] › `)).trim();
  if (!input) continue;
  if (input === "/exit") break;

  if (input === "/reset") { history = []; console.log("  cleared\n"); continue; }

  if (input.startsWith("/mode")) {
    const next = input.split(/\s+/)[1];
    if (!PROMPTS[next]) { console.log(`  modes: ${Object.keys(PROMPTS).join(", ")}\n`); continue; }
    mode = next;
    console.log(`  mode → ${mode} (history kept: ${history.length})\n`);
    continue;
  }

  if (input.startsWith("/level")) {
    level = input.split(/\s+/)[1] ?? level;
    console.log(`  level → ${level}\n`);
    continue;
  }

  if (input === "/preview") {
    await renderPreview(mode, {
      level, maxSentences: 5, history, input: "<your next question>",
    });
    console.log();
    continue;
  }

  // ── chat turn ─────────────────────────────────────────────────────────
  const chain = PROMPTS[mode].pipe(model);

  process.stdout.write("bot › ");
  let full;
  try {
    for await (const chunk of await chain.stream({ level, maxSentences: 5, history, input })) {
      process.stdout.write(chunk.content);
      full = full ? full.concat(chunk) : chunk;
    }
    console.log("\n");
    history = [...history, new HumanMessage(input), full].slice(-10);   // bounded
  } catch (err) {
    console.log(`\n  ⚠️ ${err.message.slice(0, 90)}\n`);
  }
}
rl.close();
```

**Python**
```python
# studybuddy_prompts.py
from langchain_core.prompts import (
    ChatPromptTemplate, MessagesPlaceholder, FewShotChatMessagePromptTemplate
)

PERSONA = (
    "You are StudyBuddy, a patient technical tutor.\n"
    "Audience level: {level}\n"
    "Never invent facts. If unsure, say so."
)

quiz_few_shot = FewShotChatMessagePromptTemplate(
    example_prompt=ChatPromptTemplate.from_messages([("human", "{topic}"), ("ai", "{questions}")]),
    examples=[{
        "topic": "HTTP caching",
        "questions": (
            "1. What does Cache-Control: max-age=60 tell the browser?\n"
            "2. When would an ETag be more useful than an expiry time?\n"
            "3. Why can caching cause users to see stale data after a deploy?"
        ),
    }],
)

MODE_RULES = {
    "explain": ("Explain the concept with exactly one everyday analogy, then a 2-sentence technical "
                "definition. Maximum {max_sentences} sentences total."),
    "quiz":    ("Do NOT explain anything. Output exactly 3 numbered questions that test understanding. "
                "Increasing difficulty. No answers."),
    "review":  ("The user will paste code or a design. Identify the 3 most important issues, each as "
                "'ISSUE: ... / WHY: ... / FIX: ...'. Be direct."),
}

def build_prompt(mode):
    messages = [("system", f"{PERSONA}\n\nMODE: {mode}\n{MODE_RULES[mode]}")]
    if mode == "quiz":
        messages.append(quiz_few_shot)
    messages += [MessagesPlaceholder("history", optional=True), ("human", "{input}")]
    return ChatPromptTemplate.from_messages(messages)

PROMPTS = {m: build_prompt(m) for m in MODE_RULES}

def render_preview(mode, variables):
    msgs = PROMPTS[mode].invoke(variables).to_messages()
    print(f"\n┌─ rendered prompt: {mode} ({len(msgs)} messages) ─")
    for m in msgs:
        body = "\n".join(f"│   {line}" for line in str(m.content).split("\n"))
        print(f"│ [{m.type}]\n{body}")
    print("└" + "─" * 40)
```

```python
# studybuddy_v1.py
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from studybuddy_prompts import PROMPTS, render_preview

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.5)

mode, level, history = "explain", "beginner", []

print("StudyBuddy v1 — /mode explain|quiz|review · /level · /preview · /reset · /exit\n")

while True:
    try:
        user_input = input(f"you [{mode}|{level}] › ").strip()
    except (EOFError, KeyboardInterrupt):
        break
    if not user_input:
        continue
    if user_input == "/exit":
        break

    if user_input == "/reset":
        history = []
        print("  cleared\n")
        continue

    if user_input.startswith("/mode"):
        parts = user_input.split()
        nxt = parts[1] if len(parts) > 1 else None
        if nxt not in PROMPTS:
            print(f"  modes: {', '.join(PROMPTS)}\n")
            continue
        mode = nxt
        print(f"  mode → {mode} (history kept: {len(history)})\n")
        continue

    if user_input.startswith("/level"):
        parts = user_input.split()
        level = parts[1] if len(parts) > 1 else level
        print(f"  level → {level}\n")
        continue

    if user_input == "/preview":
        render_preview(mode, {
            "level": level, "max_sentences": 5,
            "history": history, "input": "<your next question>",
        })
        print()
        continue

    # ── chat turn ─────────────────────────────────────────────────────────
    chain = PROMPTS[mode] | model

    print("bot › ", end="", flush=True)
    full = None
    try:
        for chunk in chain.stream({"level": level, "max_sentences": 5,
                                   "history": history, "input": user_input}):
            print(chunk.content, end="", flush=True)
            full = chunk if full is None else full + chunk
        print("\n")
        history = (history + [HumanMessage(user_input), full])[-10:]     # bounded
    except Exception as err:
        print(f"\n  ⚠️ {str(err)[:90]}\n")
```

**Four things this design gets right:**

1. **`/preview` is not a toy.** Being able to see the exact rendered messages is the single most
   useful debugging tool in prompt work. Most "the model ignored my instruction" bugs are
   actually "my instruction never made it into the prompt."
2. **Mode switching preserves history** because history is a *variable*, not baked into the
   prompt string. Try that with concatenation.
3. **Few-shot only where it's needed.** The quiz mode gets examples; explain and review don't
   pay for tokens they don't need.
4. **The prompt module is importable and testable.** You can unit-test `renderPreview` output in
   CI without calling a model at all — free, fast, deterministic prompt tests.
</details>

---

## 9. Interview questions

### Basic

<details>
<summary><b>Q: What is a PromptTemplate?</b></summary>

A reusable, parameterised prompt. It declares its input variables, validates that they're all
provided, substitutes them into the template text, and returns a prompt value. It's a
`Runnable`, so it composes with models via `.pipe()` / `|`. Compared to string concatenation it
gives you validation, reuse, and composability.
</details>

<details>
<summary><b>Q: Difference between PromptTemplate and ChatPromptTemplate?</b></summary>

`PromptTemplate` renders to a **single string** — the format old completion models expect.
`ChatPromptTemplate` renders to a **list of messages** with roles (system/human/ai), which is
what modern chat models expect. Use `ChatPromptTemplate` for essentially all new work; roles
carry real signal that a flattened string loses.
</details>

<details>
<summary><b>Q: What is MessagesPlaceholder for?</b></summary>

It reserves a slot in a chat template where an **array of messages** is spliced in at render
time — normally conversation history. Unlike a `{variable}`, which substitutes one string, a
placeholder inserts zero or many real message objects, preserving their roles. Mark it
`optional` so the first turn (empty history) doesn't fail.
</details>

<details>
<summary><b>Q: How do you include a literal `{` in a prompt template?</b></summary>

Double it: `{{` and `}}`. This trips people up constantly when a prompt contains a JSON example.
Alternatively switch to mustache templating (`templateFormat: "mustache"`), where `{{var}}` is
the variable syntax and single braces are literal — convenient for prompts full of JSON or code.
</details>

### Intermediate

<details>
<summary><b>Q: Why use a template instead of a formatted string?</b></summary>

Four reasons: **validation** (a missing variable throws with its name instead of silently
inserting `undefined`); **structure** (you get real messages with roles, not a flattened
string); **reuse** (one definition, importable, versionable, testable); and **composability**
(it's a `Runnable`, so `prompt | model | parser` works and streaming/batching/tracing propagate
for free). The validation point alone catches a whole class of silent quality bugs.
</details>

<details>
<summary><b>Q: What are partial variables and when are they useful?</b></summary>

`partial()` pre-fills some variables and returns a new template needing only the rest. Two main
uses: **specialisation** — one base template becomes several ready-to-use prompts (per mode, per
tenant, per language) sharing one definition; and **dynamic values** — a partial can be a
*function* evaluated at render time, so things like today's date, a feature flag, or a request
ID get injected without threading them through every call site.
</details>

<details>
<summary><b>Q: How would you build a few-shot prompt where the examples change per input?</b></summary>

Use an **example selector** instead of a static list. `SemanticSimilarityExampleSelector`
embeds your example pool, embeds the incoming input, and retrieves the k nearest examples,
which the few-shot template then renders. Benefits: relevance (examples match the input's
domain), and you can hold a large example pool while only paying tokens for k of them.
Alternatives include length-based selection (fit as many as the budget allows) and MMR
selection (relevant *and* diverse). This is usually the highest-ROI upgrade to a plateaued
few-shot classifier.
</details>

<details>
<summary><b>Q: A teammate concatenates history into one string instead of using MessagesPlaceholder. What's wrong with that?</b></summary>

Three things. **Quality**: chat models were fine-tuned on role-structured conversations;
flattening to `"Human: ...\nAI: ..."` inside a single user message is off-distribution and
measurably worse. **Correctness**: tool calls and multimodal content can't survive
stringification, so agents break. **Maintainability**: you can no longer trim, filter, or
summarise messages as objects, and your history rendering is duplicated everywhere. Providers
also apply their own chat templating to real messages — you'd be fighting it.
</details>

### Advanced

<details>
<summary><b>Q: How would you design a prompt management system for a team of 10 shipping to production?</b></summary>

**Storage & versioning** — prompts as code in a dedicated module, in git, code-reviewed. Every
prompt gets a stable ID and a version. For non-engineers editing prompts, a prompt registry
(LangSmith Hub or your own DB) with the app pinning a version, never "latest".

**Testing** — two layers. Cheap deterministic tests in CI: every prompt renders with its sample
variables, declares no unused variables, produces the expected message count/roles. Then eval
tests against a labelled dataset per prompt, gated on a minimum score before merge (Day 25).

**Rollout** — treat a prompt change like a code change: canary it on a traffic slice, compare
online metrics (thumbs-down rate, escalation rate, cost/latency) against control, and keep a
one-click revert. Prompt changes have caused more production incidents than model changes.

**Observability** — tag every trace with prompt ID + version so you can attribute a quality
regression to a specific edit. Log the *rendered* prompt, not just the variables.

**Structure** — one persona/shared block, specialised via partials, so a persona change is one
edit. Keep the stable prefix first for prompt-cache hits; put variable content last.

**Governance** — a checklist for prompts touching untrusted input (delimiting, role separation),
and a rule that no prompt hard-codes a model-specific quirk without a comment explaining it.
</details>

<details>
<summary><b>Q: Your prompt works with Groq but produces preambles on Gemini. How do you handle provider differences in prompts?</b></summary>

First, diagnose rather than patch: render the prompt for both and confirm they're identical, and
check whether the difference is instruction-following or *system-message handling* — some
providers weight the system message differently, and Anthropic takes it as a separate top-level
field entirely.

Then, in order of preference:
1. **Make the instruction structural rather than verbal** — a few-shot example whose output
   starts directly with the desired first character beats any "do not add a preamble" sentence.
   This generalises across providers.
2. **Constrain the output space** — structured output/tool calling makes a preamble
   unrepresentable. This is the real fix, and it's tomorrow's topic.
3. **Post-process** — strip a known preamble pattern in an output parser. Cheap, reliable,
   but hides the problem.
4. **Provider-specific overrides as a last resort** — a `promptOverrides[provider]` map. Keep it
   small and documented, because it re-introduces exactly the provider coupling the abstraction
   removed.

And the process point: this is why you need an eval set that runs against *every* provider you
support. Provider swaps are cheap in code and expensive in behaviour — the abstraction makes
the call site identical, not the output.
</details>

---

## 10. Recap

- ✅ `ChatPromptTemplate.fromMessages([...])` is your default — real messages, real roles
- ✅ `{var}` is a string slot; `MessagesPlaceholder` is a message-**array** slot
- ✅ Escape literal braces with `{{ }}`, or switch to mustache format
- ✅ `FewShotChatMessagePromptTemplate` turns examples into real alternating turns
- ✅ `partial()` specialises one base template into many, and supports functions for dynamic values
- ✅ Templates validate their variables — no more silent `undefined` in your prompt
- ✅ Templates are `Runnable`s: `prompt.pipe(model)` / `prompt | model` already works

### Tomorrow

**[Day 06 — Output parsers & structured output](day-06-output-parsers-structured-output.md)**:
right now every response is a blob of text you regex. Tomorrow you get typed, validated objects
out of the model — `withStructuredOutput`, Zod ↔ Pydantic schemas, JSON parsers, and
retry-on-invalid. This is the piece that makes LLM output safe to put into a database.

### Quick self-check

1. Your template contains `Reply like {"ok": true}` and it throws. What's the fix?
2. Why is `MessagesPlaceholder` better than joining history into a string?
3. What does `prompt.pipe(model)` return, and why is that significant?

<details>
<summary>Answers</summary>

1. Escape the braces: `{{"ok": true}}`. The formatter reads `{...}` as a variable name.
   (Or use mustache format if the prompt is full of JSON.)
2. It preserves role structure, which chat models were trained on; it keeps tool calls and
   multimodal content intact; and it keeps history as objects you can trim/filter/summarise.
3. A `Runnable` — a composed chain. Significant because the composition itself implements
   `invoke`/`stream`/`batch`, so streaming, batching and tracing propagate through the whole
   pipeline with no glue code. That's tomorrow-and-Day-07's core idea.
</details>
