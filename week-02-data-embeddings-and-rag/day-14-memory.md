# Day 14 — Memory: Buffer, Summary, Entity & What Actually Changed

> ⏱ **Time:** ~2.5 hours · 🎯 **Prereqs:** [Day 13](day-13-advanced-rag.md) · 🧩 **Difficulty:** ●●●○○

**Today you learn:** every memory strategy — buffer, window, summary, token-buffer, entity,
vector — what each costs, and **how memory actually works in modern LangChain** now that the
`Memory` classes are gone.

Then you build StudyBuddy v3, which remembers you across sessions *and* answers from your
documents.

---

## 1. The problem

Day 04 ended with an uncomfortable result. You tested three history strategies over a 12-turn
conversation:

| Strategy | Tokens | Remembered turn 1? |
|---|---|---|
| Keep everything | ~4,800 | ✅ |
| Sliding window (4) | ~1,900 | ❌ |
| Token trim (300) | ~2,600 | ❌ |

**There is no window size that is both cheap and remembers everything.** Trimming trades memory
for cost, and you always lose something.

That's because trimming is the wrong *shape* of solution. Consider what a human assistant does
over a long relationship:

```
   They don't replay every conversation you've ever had.
   They remember:

   · a SUMMARY of what you've discussed          ← compression
   · specific FACTS about you                     ← extraction
     ("prefers Python", "works in fintech")
   · and they can LOOK UP an old conversation     ← retrieval
     if you reference it
```

Three different mechanisms, not one bigger window. Today you build all three.

---

## 2. Mental model

### The strategies, ranked by cost

```
   ┌─ BUFFER ───────────────────────────────────────────────────┐
   │  send everything                                            │
   │  ✅ perfect recall   ❌ O(n²) cost, hits the context limit   │
   └─────────────────────────────────────────────────────────────┘

   ┌─ WINDOW ───────────────────────────────────────────────────┐
   │  send the last N messages                                   │
   │  ✅ bounded cost     ❌ hard forgetting at the boundary      │
   └─────────────────────────────────────────────────────────────┘

   ┌─ TOKEN BUFFER ─────────────────────────────────────────────┐
   │  send as many recent messages as fit a token budget         │
   │  ✅ predictable cost ❌ same hard forgetting                 │
   └─────────────────────────────────────────────────────────────┘

   ┌─ SUMMARY ──────────────────────────────────────────────────┐
   │  compress old turns into a running summary                  │
   │  ✅ bounded + long memory   ❌ lossy, costs a call            │
   └─────────────────────────────────────────────────────────────┘

   ┌─ SUMMARY + BUFFER  ★ the practical default ────────────────┐
   │  summary of old turns  +  verbatim recent turns             │
   │  ✅ detail where it matters, gist where it doesn't           │
   └─────────────────────────────────────────────────────────────┘

   ┌─ ENTITY / FACT ────────────────────────────────────────────┐
   │  extract structured facts: {name, prefers, timezone}        │
   │  ✅ survives forever, tiny   ❌ needs extraction, can go stale │
   └─────────────────────────────────────────────────────────────┘

   ┌─ VECTOR ───────────────────────────────────────────────────┐
   │  embed past turns, RETRIEVE the relevant ones               │
   │  ✅ unbounded history, constant cost   ❌ may miss context     │
   └─────────────────────────────────────────────────────────────┘
```

### The three-layer architecture that actually works

```
   ┌──────────────────────────────────────────────────────────────┐
   │  SHORT TERM   last ~6 messages, verbatim                     │
   │               → immediate conversational coherence           │
   ├──────────────────────────────────────────────────────────────┤
   │  MID TERM     rolling summary of everything older            │
   │               → "we discussed X, decided Y"                  │
   ├──────────────────────────────────────────────────────────────┤
   │  LONG TERM    extracted facts, stored across SESSIONS        │
   │               → "prefers Python, works in fintech, level:    │
   │                  intermediate"                               │
   └──────────────────────────────────────────────────────────────┘
                              ▲
              plus RETRIEVAL over old conversations
              when the user references something specific
```

Short and mid term live in the prompt. Long term is a **database row**, not a message.

### Memory vs RAG — the distinction people blur

```
   RAG              retrieves from DOCUMENTS (external knowledge)
   MEMORY           retrieves from CONVERSATIONS (what was said)

   Same mechanism (embed, store, retrieve).
   Different source, different lifetime, different failure modes.

   "What's our refund policy?"      → RAG
   "What did I tell you yesterday?" → memory
   "Explain that again, simpler"    → short-term memory only
```

---

## 3. First principles

### 3.1 What actually changed in LangChain 1.x

This is the part interviewers ask about, and the part most tutorials get wrong.

**The old way (0.x):**

```python
memory = ConversationBufferMemory(return_messages=True)
chain = ConversationChain(llm=model, memory=memory)
chain.predict(input="hi")          # memory updated implicitly
```

The `Memory` classes were **stateful objects that mutated themselves** inside a chain. Three
problems killed them:

1. **Hidden state.** You couldn't tell what was in the prompt without inspecting the object.
2. **Not thread-safe.** One memory instance shared across concurrent requests interleaved
   conversations — a real bug people shipped.
3. **Not persistent.** Restart the process and every conversation vanished.

**The modern way** splits it into three explicit pieces:

| Concern | Modern answer |
|---|---|
| Where history is stored | **You** own it — an array, a database, or a LangGraph checkpointer |
| How it enters the prompt | `MessagesPlaceholder` (Day 05) |
| How it's bounded | `trimMessages` / `trim_messages`, or a summarisation step you write |

```python
# Modern: everything explicit
history = load_history(session_id)                 # you control storage
trimmed = trim_messages(history, max_tokens=800, ...)
answer = (prompt | model).invoke({"history": trimmed, "input": text})
save_history(session_id, history + [HumanMessage(text), AIMessage(answer)])
```

More lines, but you can see exactly what's in the prompt, it's safe under concurrency, and
persistence is your choice.

> 🚨 **The 1.x reality:** the legacy `Memory` classes moved to `langchain-classic` /
> `@langchain/classic` alongside the legacy chains. `ConversationBufferMemory`,
> `ConversationSummaryMemory` and friends still exist there for migration, but **the intended
> path for persistent conversational state is LangGraph checkpointers** (Day 20). Today you build
> the mechanisms by hand so the checkpointer isn't magic when you meet it.

### 3.2 Buffer and window

```js
const buffer = history;                                    // everything
const window = [system, ...history.slice(-6)];             // last 6
```

Cost of buffer over a conversation is O(n²) — turn *n* re-sends all *n-1* previous turns.
That's Day 01's lesson, and it's why unbounded buffer is only viable for short interactions.

### 3.3 Token buffer — `trimMessages`

```js
await trimMessages(messages, {
  maxTokens: 800,
  strategy: "last",         // keep the most RECENT (vs "first")
  tokenCounter: model,      // accurate counting via the model's tokenizer
  includeSystem: true,      // never drop the system message
  startOn: "human",         // a valid history starts on a human turn
  allowPartial: false,      // don't cut a message in half
});
```

**`startOn: "human"` matters more than it looks.** If trimming leaves a dangling `ToolMessage` or
starts on an AI turn, some providers reject the request outright. This one option prevents a
whole class of 400 errors.

### 3.4 Summary memory

Compress old turns into a paragraph:

```
   [turns 1-10]  ──LLM──▶  "The user is building a RAG system in Python,
                            using Chroma. They struggled with chunk size and
                            settled on 800 chars. They prefer concise answers."
                            ↑ ~50 tokens replacing ~2000
```

Two flavours:

- **Recompute** — summarise all old turns each time. Accurate, expensive.
- **Progressive** — feed the *existing summary* plus the new turns, produce an updated summary.
  Cheap, but drifts over many iterations (each rewrite is lossy — Day 08's compression lesson).

**Summary + buffer** is the practical default: a summary of old turns *plus* the last few
verbatim. Recent detail stays exact; distant context becomes gist.

### 3.5 Entity / fact memory

Instead of prose, extract **structured facts**:

```json
{
  "name": "Wasif",
  "prefers_language": "JavaScript",
  "level": "intermediate",
  "current_project": "a RAG system for lecture notes",
  "timezone": "PKT"
}
```

Advantages over a summary: tiny, queryable, updatable field by field, and it survives across
sessions as a database row.

The hard part is **updating** rather than appending. If the user says "actually I've switched to
Python", you must *replace* `prefers_language`, not accumulate contradictions. That's a merge
policy decision, and it's where naive fact memory fails.

### 3.6 Vector memory — RAG over your own conversations

Embed each turn (or each summary), store it, and retrieve the relevant ones when the user
references something old.

```
   "What did we decide about chunk size?"
              │ retrieve over past conversation turns
              ▼
   "[3 weeks ago] You settled on 800 characters with 120 overlap."
```

Constant cost regardless of history length. The trade-off is that retrieval can miss context that
a full history would have carried implicitly.

**Every technique from Days 10–13 applies here** — chunking, hybrid search, reranking. Memory
retrieval is RAG with a different corpus.

### 3.7 Choosing

| Situation | Use |
|---|---|
| Short interactions (<10 turns) | Buffer |
| Long chats, cost matters | **Summary + buffer** ★ |
| Facts must persist across sessions | Entity/fact memory in a DB |
| Users reference conversations from weeks ago | Vector memory |
| Production conversational app | **All three layers** (§2) |

---

## 4. Code — JavaScript

```bash
npm install langchain @langchain/core @langchain/classic @langchain/groq \
            @langchain/ollama zod dotenv
```

### 4.1 Buffer, window and token-trim compared

```js
// day14-strategies.js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";
import { SystemMessage, HumanMessage, AIMessage, trimMessages }
  from "@langchain/core/messages";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });

const SYSTEM = new SystemMessage("You are a concise assistant. One short sentence per answer.");

const STRATEGIES = {
  buffer: async (msgs) => msgs,

  window: async (msgs) => [msgs[0], ...msgs.slice(1).slice(-6)],

  tokenTrim: async (msgs) =>
    trimMessages(msgs, {
      maxTokens: 400,
      strategy: "last",
      tokenCounter: model,
      includeSystem: true,
      startOn: "human",
    }),
};

const TURNS = [
  "My name is Wasif and I'm building a RAG system.",
  "I'm using Python with Chroma.",
  "My documents are lecture notes as PDFs.",
  "I settled on 800-character chunks.",
  "What is 7 times 8?",
  "Name a fruit.",
  "Name a planet.",
  "Name a colour.",
  "Name a country.",
  "What is my name, and what chunk size did I choose?",   // ← the memory test
];

for (const [name, strategy] of Object.entries(STRATEGIES)) {
  let history = [SYSTEM];
  let tokens = 0;
  let last = "";

  for (const turn of TURNS) {
    history.push(new HumanMessage(turn));
    const res = await model.invoke(await strategy(history));
    tokens += res.usage_metadata?.total_tokens ?? 0;
    history.push(res);
    last = res.text.trim();
  }

  const remembered = /wasif/i.test(last) && /800/.test(last);
  console.log(`${name.padEnd(11)} tokens=${String(tokens).padStart(5)} ` +
              `recall=${remembered ? "✅" : "❌"}  "${last.slice(0, 60)}"`);
}
```

### 4.2 Summary + buffer — the practical default

```js
// day14-summary-buffer.js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";
import { SystemMessage, HumanMessage, AIMessage } from "@langchain/core/messages";
import { ChatPromptTemplate, MessagesPlaceholder } from "@langchain/core/prompts";
import { StringOutputParser } from "@langchain/core/output_parsers";

const fast = new ChatGroq({ model: "llama-3.1-8b-instant", temperature: 0 });
const smart = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0.3 });

class SummaryBufferMemory {
  constructor({ keepRecent = 4, summariseAfter = 6 } = {}) {
    this.keepRecent = keepRecent;
    this.summariseAfter = summariseAfter;
    this.summary = "";
    this.recent = [];                       // verbatim recent messages
  }

  async add(human, ai) {
    this.recent.push(new HumanMessage(human), new AIMessage(ai));

    // Once we exceed the threshold, fold the OLDEST turns into the summary.
    if (this.recent.length > this.summariseAfter * 2) {
      const toFold = this.recent.slice(0, this.recent.length - this.keepRecent * 2);
      this.recent = this.recent.slice(-this.keepRecent * 2);
      await this.fold(toFold);
    }
  }

  async fold(messages) {
    const transcript = messages
      .map((m) => `${m.getType() === "human" ? "User" : "Assistant"}: ${m.content}`)
      .join("\n");

    const prompt = this.summary
      ? `Existing summary:\n${this.summary}\n\nNew exchanges:\n${transcript}\n\n` +
        `Produce an UPDATED summary. Preserve every specific fact, name, number and ` +
        `decision from the existing summary — never drop details to save space.`
      : `Summarise these exchanges, preserving every specific fact, name, number ` +
        `and decision:\n\n${transcript}`;

    this.summary = (await fast.invoke(prompt)).text.trim();
  }

  // What actually goes into the prompt.
  context() {
    return { summary: this.summary || "(no earlier conversation)", recent: this.recent };
  }
}

const prompt = ChatPromptTemplate.fromMessages([
  ["system",
   "You are a helpful assistant. Answer in one or two short sentences.\n\n" +
   "Summary of earlier conversation:\n{summary}"],
  new MessagesPlaceholder("recent"),
  ["human", "{input}"],
]);

const chain = prompt.pipe(smart).pipe(new StringOutputParser());

// ── run ──────────────────────────────────────────────────────────────────
const memory = new SummaryBufferMemory({ keepRecent: 3, summariseAfter: 5 });

const TURNS = [
  "My name is Wasif and I'm building a RAG system for my lecture notes.",
  "I'm using Python with Chroma as the vector store.",
  "After testing I settled on 800-character chunks with 120 overlap.",
  "I'm also adding hybrid search with BM25.",
  "What is 12 times 12?",
  "Name a fruit.",
  "Name a planet.",
  "Name a musical instrument.",
  "What's my name, what chunk size did I choose, and what store am I using?",
];

for (const turn of TURNS) {
  const { summary, recent } = memory.context();
  const answer = await chain.invoke({ summary, recent, input: turn });

  console.log(`\n👤 ${turn}`);
  console.log(`🤖 ${answer.trim()}`);

  await memory.add(turn, answer);
}

console.log(`\n${"─".repeat(70)}`);
console.log(`SUMMARY (${memory.summary.length} chars):\n${memory.summary}`);
console.log(`\nverbatim recent: ${memory.recent.length} messages`);
```

### 4.3 Entity / fact memory with proper updates

```js
// day14-entity.js
import "dotenv/config";
import * as z from "zod";
import { ChatGroq } from "@langchain/groq";

const fast = new ChatGroq({ model: "llama-3.1-8b-instant", temperature: 0 });

const FactUpdate = z.object({
  reasoning: z.string().describe("What you learned. Write this first."),
  updates: z.array(z.object({
    key: z.string().describe("snake_case fact key, e.g. 'preferred_language'"),
    value: z.string().describe("The value"),
    operation: z.enum(["set", "append", "delete"])
      .describe("set = replace any existing value; append = add to a list; " +
                "delete = the user contradicted or retracted this"),
  })).describe("Only NEW or CHANGED facts. Empty if nothing was learned."),
});

class FactMemory {
  constructor() { this.facts = {}; }

  async observe(userMessage) {
    const known = Object.entries(this.facts)
      .map(([k, v]) => `${k}: ${v}`).join("\n") || "(nothing known yet)";

    const { updates, reasoning } = await fast.withStructuredOutput(FactUpdate).invoke(
      `Extract durable facts about the user from their message.\n\n` +
      `Already known:\n${known}\n\n` +
      `New message: "${userMessage}"\n\n` +
      `Only report facts worth remembering long-term (preferences, identity, ongoing " +
      "projects, constraints). Ignore transient questions.\n` +
      `If the user CONTRADICTS something known, use "set" to replace it.`
    );

    for (const u of updates) {
      if (u.operation === "delete") delete this.facts[u.key];
      else if (u.operation === "append" && this.facts[u.key]) {
        this.facts[u.key] = `${this.facts[u.key]}, ${u.value}`;
      } else {
        this.facts[u.key] = u.value;        // "set" REPLACES — this is the key behaviour
      }
    }

    return { updates, reasoning };
  }

  render() {
    const entries = Object.entries(this.facts);
    return entries.length
      ? entries.map(([k, v]) => `- ${k.replace(/_/g, " ")}: ${v}`).join("\n")
      : "(nothing known about this user yet)";
  }
}

const memory = new FactMemory();

const MESSAGES = [
  "Hi, I'm Wasif. I'm a backend developer in Lahore.",
  "I mostly write JavaScript but I'm learning Python.",
  "I'm building a RAG system for university lecture notes.",
  "What's the capital of France?",                     // ← transient, learn nothing
  "Actually I've decided to build the whole thing in Python, not JavaScript.",  // ← CONTRADICTION
  "I prefer short answers with code examples.",
];

for (const msg of MESSAGES) {
  const { updates, reasoning } = await memory.observe(msg);
  console.log(`\n👤 ${msg}`);
  if (updates.length === 0) {
    console.log("   (no durable facts)");
  } else {
    updates.forEach((u) => console.log(`   ${u.operation.toUpperCase()} ${u.key} = ${u.value}`));
  }
}

console.log(`\n${"─".repeat(64)}\nWHAT I KNOW ABOUT YOU:\n${memory.render()}`);
```

Watch the contradiction turn: `preferred_language` should be **replaced**, not appended, so the
final state says Python and not "JavaScript, Python".

### 4.4 Vector memory — retrieve old conversations

```js
// day14-vector-memory.js
import "dotenv/config";
import { OllamaEmbeddings } from "@langchain/ollama";
import { MemoryVectorStore } from "@langchain/classic/vectorstores/memory";
import { Document } from "@langchain/core/documents";

const embeddings = new OllamaEmbeddings({ model: "nomic-embed-text" });

class VectorMemory {
  constructor(embeddings) {
    this.embeddings = embeddings;
    this.store = null;
    this.turns = [];
  }

  async record(human, ai, sessionId, timestamp) {
    // Store the EXCHANGE, not individual messages — a question without its
    // answer (or vice versa) retrieves poorly.
    const doc = new Document({
      pageContent: `User: ${human}\nAssistant: ${ai}`,
      metadata: { sessionId, timestamp, turn: this.turns.length + 1 },
    });
    this.turns.push(doc);

    this.store = this.store
      ? (await this.store.addDocuments([doc]), this.store)
      : await MemoryVectorStore.fromDocuments([doc], this.embeddings);
  }

  async recall(query, k = 2) {
    if (!this.store) return [];
    return this.store.similaritySearch(query, k);
  }
}

const memory = new VectorMemory(embeddings);

// ── simulate conversations across three sessions ─────────────────────────
const PAST = [
  ["session-1", "2024-03-01", "What chunk size should I use for lecture notes?",
   "For lecture notes, 800 characters with 120 overlap works well — big enough for a full concept, small enough to stay precise."],
  ["session-1", "2024-03-01", "Which vector store do you recommend for local dev?",
   "Chroma — it persists to a directory with no server needed."],
  ["session-2", "2024-03-08", "How do I handle PDFs with tables?",
   "Tables break under naive splitting. Use a markdown-aware splitter and inject the section heading into each chunk."],
  ["session-2", "2024-03-08", "What embedding model is free?",
   "nomic-embed-text via Ollama — 768 dimensions, runs locally, no API cost."],
  ["session-3", "2024-03-15", "My retrieval is missing error codes.",
   "Embeddings blur ERR_4471 and ERR_4472. Add BM25 keyword search and fuse with RRF."],
];

for (const [session, ts, human, ai] of PAST) {
  await memory.record(human, ai, session, ts);
}

// ── recall ───────────────────────────────────────────────────────────────
for (const query of [
  "what did we decide about chunk size?",
  "which embedding model did you suggest?",
  "why was my search missing exact codes?",
]) {
  console.log(`\n❓ ${query}`);
  for (const d of await memory.recall(query, 1)) {
    console.log(`   [${d.metadata.timestamp}] ${d.pageContent.replace(/\n/g, " | ").slice(0, 100)}…`);
  }
}
```

### 4.5 Persisting memory across process restarts

```js
// day14-persistence.js
import fs from "node:fs/promises";
import { HumanMessage, AIMessage, SystemMessage } from "@langchain/core/messages";

// Messages are objects — serialise to plain JSON, restore to classes.
const toJSON = (messages) =>
  messages.map((m) => ({ role: m.getType(), content: m.content }));

const fromJSON = (rows) =>
  rows.map((r) =>
    r.role === "human" ? new HumanMessage(r.content)
    : r.role === "ai"  ? new AIMessage(r.content)
    : new SystemMessage(r.content)
  );

class FileSessionStore {
  constructor(dir = "./.sessions") { this.dir = dir; }

  path(sessionId) { return `${this.dir}/${sessionId}.json`; }

  async load(sessionId) {
    try {
      const raw = JSON.parse(await fs.readFile(this.path(sessionId), "utf8"));
      return { messages: fromJSON(raw.messages), summary: raw.summary ?? "",
               facts: raw.facts ?? {} };
    } catch {
      return { messages: [], summary: "", facts: {} };
    }
  }

  async save(sessionId, { messages, summary, facts }) {
    await fs.mkdir(this.dir, { recursive: true });
    await fs.writeFile(this.path(sessionId), JSON.stringify({
      messages: toJSON(messages), summary, facts,
      updatedAt: new Date().toISOString(),
    }, null, 2));
  }
}

// ── demo ─────────────────────────────────────────────────────────────────
const store = new FileSessionStore();

await store.save("user-123", {
  messages: [new HumanMessage("I prefer Python"), new AIMessage("Noted!")],
  summary: "User is building a RAG system.",
  facts: { preferred_language: "Python", level: "intermediate" },
});

const restored = await store.load("user-123");
console.log("restored messages:", restored.messages.map((m) => m.content));
console.log("restored facts:", restored.facts);
```

> 💡 This is a simplified checkpointer. LangGraph's `SqliteSaver` / `PostgresSaver` do exactly
> this — plus versioning, time-travel and interrupt support — and you'll use them on Day 20.

---

## 5. Code — Python

```bash
pip install langchain langchain-classic langchain-groq langchain-ollama pydantic python-dotenv
```

### 5.1 Buffer, window and token-trim compared

```python
# day14_strategies.py
import re
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import (
    SystemMessage, HumanMessage, AIMessage, trim_messages,
)

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

SYSTEM = SystemMessage("You are a concise assistant. One short sentence per answer.")

STRATEGIES = {
    "buffer": lambda msgs: msgs,
    "window": lambda msgs: [msgs[0]] + msgs[1:][-6:],
    "token_trim": lambda msgs: trim_messages(
        msgs, max_tokens=400, strategy="last", token_counter=model,
        include_system=True, start_on="human",
    ),
}

TURNS = [
    "My name is Wasif and I'm building a RAG system.",
    "I'm using Python with Chroma.",
    "My documents are lecture notes as PDFs.",
    "I settled on 800-character chunks.",
    "What is 7 times 8?",
    "Name a fruit.",
    "Name a planet.",
    "Name a colour.",
    "Name a country.",
    "What is my name, and what chunk size did I choose?",   # ← the memory test
]

for name, strategy in STRATEGIES.items():
    history, tokens, last = [SYSTEM], 0, ""

    for turn in TURNS:
        history.append(HumanMessage(turn))
        res = model.invoke(strategy(history))
        tokens += (res.usage_metadata or {}).get("total_tokens", 0)
        history.append(res)
        last = res.content.strip()

    remembered = bool(re.search("wasif", last, re.I)) and "800" in last
    print(f"{name:<11} tokens={tokens:>5} recall={'✅' if remembered else '❌'}  "
          f'"{last[:60]}"')
```

### 5.2 Summary + buffer — the practical default

```python
# day14_summary_buffer.py
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser

load_dotenv()
fast = ChatGroq(model="llama-3.1-8b-instant", temperature=0)
smart = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.3)

class SummaryBufferMemory:
    def __init__(self, keep_recent=4, summarise_after=6):
        self.keep_recent = keep_recent
        self.summarise_after = summarise_after
        self.summary = ""
        self.recent = []                    # verbatim recent messages

    def add(self, human, ai):
        self.recent += [HumanMessage(human), AIMessage(ai)]

        # Once we exceed the threshold, fold the OLDEST turns into the summary.
        if len(self.recent) > self.summarise_after * 2:
            to_fold = self.recent[:-self.keep_recent * 2]
            self.recent = self.recent[-self.keep_recent * 2:]
            self._fold(to_fold)

    def _fold(self, messages):
        transcript = "\n".join(
            f"{'User' if m.type == 'human' else 'Assistant'}: {m.content}"
            for m in messages)

        if self.summary:
            prompt = (f"Existing summary:\n{self.summary}\n\nNew exchanges:\n{transcript}\n\n"
                      "Produce an UPDATED summary. Preserve every specific fact, name, number "
                      "and decision from the existing summary — never drop details to save space.")
        else:
            prompt = ("Summarise these exchanges, preserving every specific fact, name, "
                      f"number and decision:\n\n{transcript}")

        self.summary = fast.invoke(prompt).content.strip()

    # What actually goes into the prompt.
    def context(self):
        return {"summary": self.summary or "(no earlier conversation)",
                "recent": self.recent}

prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are a helpful assistant. Answer in one or two short sentences.\n\n"
     "Summary of earlier conversation:\n{summary}"),
    MessagesPlaceholder("recent"),
    ("human", "{input}"),
])

chain = prompt | smart | StrOutputParser()

# ── run ──────────────────────────────────────────────────────────────────
memory = SummaryBufferMemory(keep_recent=3, summarise_after=5)

TURNS = [
    "My name is Wasif and I'm building a RAG system for my lecture notes.",
    "I'm using Python with Chroma as the vector store.",
    "After testing I settled on 800-character chunks with 120 overlap.",
    "I'm also adding hybrid search with BM25.",
    "What is 12 times 12?",
    "Name a fruit.",
    "Name a planet.",
    "Name a musical instrument.",
    "What's my name, what chunk size did I choose, and what store am I using?",
]

for turn in TURNS:
    ctx = memory.context()
    answer = chain.invoke({**ctx, "input": turn})

    print(f"\n👤 {turn}")
    print(f"🤖 {answer.strip()}")

    memory.add(turn, answer)

print("\n" + "─" * 70)
print(f"SUMMARY ({len(memory.summary)} chars):\n{memory.summary}")
print(f"\nverbatim recent: {len(memory.recent)} messages")
```

### 5.3 Entity / fact memory with proper updates

```python
# day14_entity.py
from typing import Literal
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq

load_dotenv()
fast = ChatGroq(model="llama-3.1-8b-instant", temperature=0)

class FactChange(BaseModel):
    key: str = Field(description="snake_case fact key, e.g. 'preferred_language'")
    value: str = Field(description="The value")
    operation: Literal["set", "append", "delete"] = Field(
        description="set = replace any existing value; append = add to a list; "
                    "delete = the user contradicted or retracted this")

class FactUpdate(BaseModel):
    """Durable facts learned from a user message."""
    reasoning: str = Field(description="What you learned. Write this first.")
    updates: list[FactChange] = Field(
        description="Only NEW or CHANGED facts. Empty if nothing was learned.")

class FactMemory:
    def __init__(self):
        self.facts = {}

    def observe(self, user_message):
        known = "\n".join(f"{k}: {v}" for k, v in self.facts.items()) or "(nothing known yet)"

        result = fast.with_structured_output(FactUpdate).invoke(
            f"Extract durable facts about the user from their message.\n\n"
            f"Already known:\n{known}\n\n"
            f'New message: "{user_message}"\n\n'
            "Only report facts worth remembering long-term (preferences, identity, ongoing "
            "projects, constraints). Ignore transient questions.\n"
            'If the user CONTRADICTS something known, use "set" to replace it.'
        )

        for u in result.updates:
            if u.operation == "delete":
                self.facts.pop(u.key, None)
            elif u.operation == "append" and u.key in self.facts:
                self.facts[u.key] = f"{self.facts[u.key]}, {u.value}"
            else:
                self.facts[u.key] = u.value      # "set" REPLACES — the key behaviour

        return result

    def render(self):
        if not self.facts:
            return "(nothing known about this user yet)"
        return "\n".join(f"- {k.replace('_', ' ')}: {v}" for k, v in self.facts.items())

memory = FactMemory()

MESSAGES = [
    "Hi, I'm Wasif. I'm a backend developer in Lahore.",
    "I mostly write JavaScript but I'm learning Python.",
    "I'm building a RAG system for university lecture notes.",
    "What's the capital of France?",                     # ← transient, learn nothing
    "Actually I've decided to build the whole thing in Python, not JavaScript.",  # CONTRADICTION
    "I prefer short answers with code examples.",
]

for msg in MESSAGES:
    result = memory.observe(msg)
    print(f"\n👤 {msg}")
    if not result.updates:
        print("   (no durable facts)")
    for u in result.updates:
        print(f"   {u.operation.upper()} {u.key} = {u.value}")

print("\n" + "─" * 64)
print(f"WHAT I KNOW ABOUT YOU:\n{memory.render()}")
```

### 5.4 Vector memory — retrieve old conversations

```python
# day14_vector_memory.py
from dotenv import load_dotenv
from langchain_ollama import OllamaEmbeddings
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_core.documents import Document

load_dotenv()
embeddings = OllamaEmbeddings(model="nomic-embed-text")

class VectorMemory:
    def __init__(self, embeddings):
        self.embeddings = embeddings
        self.store = None
        self.count = 0

    def record(self, human, ai, session_id, timestamp):
        # Store the EXCHANGE, not individual messages — a question without its
        # answer (or vice versa) retrieves poorly.
        self.count += 1
        doc = Document(
            page_content=f"User: {human}\nAssistant: {ai}",
            metadata={"session_id": session_id, "timestamp": timestamp, "turn": self.count},
        )
        if self.store is None:
            self.store = InMemoryVectorStore.from_documents([doc], self.embeddings)
        else:
            self.store.add_documents([doc])

    def recall(self, query, k=2):
        return self.store.similarity_search(query, k=k) if self.store else []

memory = VectorMemory(embeddings)

# ── simulate conversations across three sessions ─────────────────────────
PAST = [
    ("session-1", "2024-03-01", "What chunk size should I use for lecture notes?",
     "For lecture notes, 800 characters with 120 overlap works well — big enough for a "
     "full concept, small enough to stay precise."),
    ("session-1", "2024-03-01", "Which vector store do you recommend for local dev?",
     "Chroma — it persists to a directory with no server needed."),
    ("session-2", "2024-03-08", "How do I handle PDFs with tables?",
     "Tables break under naive splitting. Use a markdown-aware splitter and inject the "
     "section heading into each chunk."),
    ("session-2", "2024-03-08", "What embedding model is free?",
     "nomic-embed-text via Ollama — 768 dimensions, runs locally, no API cost."),
    ("session-3", "2024-03-15", "My retrieval is missing error codes.",
     "Embeddings blur ERR_4471 and ERR_4472. Add BM25 keyword search and fuse with RRF."),
]

for session, ts, human, ai in PAST:
    memory.record(human, ai, session, ts)

# ── recall ───────────────────────────────────────────────────────────────
for query in [
    "what did we decide about chunk size?",
    "which embedding model did you suggest?",
    "why was my search missing exact codes?",
]:
    print(f"\n❓ {query}")
    for d in memory.recall(query, 1):
        snippet = d.page_content.replace("\n", " | ")[:100]
        print(f"   [{d.metadata['timestamp']}] {snippet}…")
```

### 5.5 Persisting memory across process restarts

```python
# day14_persistence.py
import json
from datetime import datetime, timezone
from pathlib import Path
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# Messages are objects — serialise to plain JSON, restore to classes.
def to_json(messages):
    return [{"role": m.type, "content": m.content} for m in messages]

def from_json(rows):
    cls = {"human": HumanMessage, "ai": AIMessage, "system": SystemMessage}
    return [cls.get(r["role"], HumanMessage)(r["content"]) for r in rows]

class FileSessionStore:
    def __init__(self, directory="./.sessions"):
        self.dir = Path(directory)

    def path(self, session_id):
        return self.dir / f"{session_id}.json"

    def load(self, session_id):
        p = self.path(session_id)
        if not p.exists():
            return {"messages": [], "summary": "", "facts": {}}
        raw = json.loads(p.read_text())
        return {"messages": from_json(raw["messages"]),
                "summary": raw.get("summary", ""),
                "facts": raw.get("facts", {})}

    def save(self, session_id, state):
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path(session_id).write_text(json.dumps({
            "messages": to_json(state["messages"]),
            "summary": state.get("summary", ""),
            "facts": state.get("facts", {}),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }, indent=2))

# ── demo ─────────────────────────────────────────────────────────────────
store = FileSessionStore()

store.save("user-123", {
    "messages": [HumanMessage("I prefer Python"), AIMessage("Noted!")],
    "summary": "User is building a RAG system.",
    "facts": {"preferred_language": "Python", "level": "intermediate"},
})

restored = store.load("user-123")
print("restored messages:", [m.content for m in restored["messages"]])
print("restored facts:", restored["facts"])
```

### 🔁 JS ↔ Python differences you just saw

| | JavaScript | Python |
|---|---|---|
| Trim | `await trimMessages(msgs, {...})` | `trim_messages(msgs, ...)` |
| Trim params | `maxTokens`, `tokenCounter`, `includeSystem`, `startOn` | `max_tokens`, `token_counter`, `include_system`, `start_on` |
| Message role | `m.getType()` | `m.type` |
| Message text | `m.content` / `res.text` | `m.content` |
| Store | `MemoryVectorStore` (`@langchain/classic`) | `InMemoryVectorStore` (`langchain_core`) |
| Legacy memory | `@langchain/classic/memory` | `langchain_classic.memory` |
| Dict merge | `{ ...ctx, input: turn }` | `{**ctx, "input": turn}` |

---

## 6. Under the hood

### Why the `Memory` classes were removed

The 0.x design looked convenient:

```python
memory = ConversationBufferMemory()
chain = ConversationChain(llm=model, memory=memory)
chain.predict(input="hi")           # memory silently mutated
```

Three concrete failures:

1. **Hidden mutation.** `memory` changed as a side effect of `predict()`. You couldn't tell what
   was in the prompt without inspecting the object, and two chains sharing a memory interfered
   invisibly.

2. **Concurrency bugs.** A single `memory` instance at module scope, shared across web requests,
   interleaved different users' conversations. This shipped to production more than once. The
   fix required a memory-per-session registry — which is state management you were doing anyway,
   just implicitly.

3. **No persistence story.** Restart the process, lose everything. Bolting on persistence meant
   subclassing.

**The modern answer separates the three concerns** — storage (yours), injection
(`MessagesPlaceholder`), bounding (`trimMessages` or your own summariser). More explicit, safe
under concurrency, and persistence becomes a choice rather than a fight.

This is the same design lesson as Day 08's chains: **abstractions should hide implementation, not
control flow or state.**

### The cost curves

```
   tokens sent per turn
        │
        │                                    ╱ BUFFER — O(n) per turn,
        │                                  ╱          O(n²) cumulative
        │                                ╱
        │                              ╱
        │  ─────────────────────────────── SUMMARY+BUFFER — bounded
        │  ─────────────────────────────── WINDOW — bounded
        │  ─────────────────────────────── VECTOR — constant
        └──────────────────────────────────▶ turns
```

For a 50-turn conversation with ~200 tokens per turn:

| Strategy | Total input tokens |
|---|---|
| Buffer | ~250,000 |
| Window (6) | ~60,000 |
| Summary + buffer | ~75,000 (incl. summarisation calls) |
| Vector (k=3) | ~45,000 |

Summary + buffer costs slightly more than a pure window but **remembers far more**, which is why
it's the usual default.

### Why progressive summarisation drifts

Each fold is a lossy rewrite of the previous summary:

```
   summary₁ = f(turns 1-5)
   summary₂ = f(summary₁ + turns 6-10)      ← summary₁ is compressed AGAIN
   summary₃ = f(summary₂ + turns 11-15)     ← and again
```

By summary₅, details from turn 2 have survived four compressions. Specifics — numbers, names,
decisions — erode first, exactly as in Day 08's map-reduce dilution.

**Mitigations:**
1. Explicitly instruct preservation of facts, names and numbers (as the code above does).
2. Keep critical facts in **structured fact memory** instead, where they're stored as fields
   rather than prose and can't be paraphrased away.
3. Periodically re-summarise from the **original** transcript rather than from the last summary,
   if you retain it.

That second point is the real argument for a three-layer design: prose summaries are for gist,
structured facts are for things that must not drift.

### Where LangGraph checkpointers fit

Everything you built today — history storage, trimming, summarising, persistence — is what a
LangGraph **checkpointer** provides as infrastructure:

| Today, by hand | LangGraph (Day 20) |
|---|---|
| `FileSessionStore` | `SqliteSaver` / `PostgresSaver` |
| `sessionId` | `thread_id` |
| Load, mutate, save | Automatic per-step checkpointing |
| — | Time travel: replay from any past step |
| — | Interrupt and resume mid-conversation |
| Fact memory in a dict | `Store` — long-term memory across threads |

Note the last row: LangGraph distinguishes the **checkpointer** (one thread's conversation state)
from the **Store** (facts shared across all of a user's threads). That's exactly the short/mid
versus long-term split from §2, made explicit in the framework.

You've now built the mechanisms by hand, so none of that will be magic.

<details>
<summary>📜 Legacy note: the memory classes you'll see in old code</summary>

| Legacy class | What it did | Modern equivalent |
|---|---|---|
| `ConversationBufferMemory` | Keep all messages | An array you own |
| `ConversationBufferWindowMemory` | Keep last k | `messages.slice(-k)` |
| `ConversationTokenBufferMemory` | Keep within a token budget | `trimMessages` |
| `ConversationSummaryMemory` | Replace history with a summary | Your own summarisation step |
| `ConversationSummaryBufferMemory` | Summary + recent | §4.2 above |
| `ConversationEntityMemory` | Extract entity facts | Structured output + a store (§4.3) |
| `VectorStoreRetrieverMemory` | Retrieve relevant past turns | A retriever over conversation docs (§4.4) |
| `ConversationChain` | Chain with implicit memory | `prompt \| model` + explicit history |
| `RunnableWithMessageHistory` | 0.3-era history wrapper | LangGraph checkpointer |

A frequent interview question is **"how has memory changed in LangChain?"** The strong answer
names the *reasons*: hidden mutation, concurrency hazards and no persistence — and that the
replacement makes storage, injection and bounding three separate explicit choices, with LangGraph
checkpointers as the production path.
</details>

---

## 7. Common mistakes

**❌ Unbounded buffer in production**

Cost is O(n²) over a conversation and eventually hits the context limit mid-chat.
✅ Bound it — window, token trim, or summary + buffer.

---

**❌ Trimming without `startOn: "human"`**

Trimming can leave a dangling tool message or start on an AI turn; some providers reject that
with a 400.
✅ `startOn: "human"`, `includeSystem: true`.

---

**❌ A single memory object shared across users**

The classic 0.x bug: module-scope memory interleaves different users' conversations.
✅ Key everything by session/user ID. This is *why* the framework stopped owning memory.

---

**❌ Appending instead of replacing on contradiction**

The user switches from JavaScript to Python and you store `"JavaScript, Python"`.
✅ A `set` operation that replaces, and a prompt that explicitly handles contradiction.

---

**❌ Storing every message in vector memory**

A question without its answer (or vice versa) retrieves poorly and doubles your storage.
✅ Store the **exchange** as one document.

---

**❌ Extracting facts from every message**

Most turns contain nothing durable. Running extraction on all of them wastes a call per turn.
✅ Extract only from user messages, and let the schema return an empty list.

---

**❌ Letting the summary drift**

Progressive summarisation is repeated lossy compression; specifics erode first.
✅ Instruct preservation of facts/names/numbers, and keep critical values in structured fact
memory instead of prose.

---

**❌ Confusing memory with RAG**

"What's our refund policy?" is RAG. "What did I tell you last week?" is memory. Same mechanism,
different corpus, different lifetime.
✅ Keep them as separate retrievers, and be explicit in the prompt about which is which.

---

**❌ Never expiring memory**

A fact learned two years ago ("currently learning Python") may be long stale.
✅ Timestamp facts, decay or re-confirm old ones, and let users view and edit what you remember.

---

## 8. Exercises

### Exercise 1 — Memory strategy bake-off ●●○○○

Run a 15-turn conversation through buffer, window, token-trim and summary+buffer. Measure total
tokens and whether each recalls a fact from turn 1, turn 5 and turn 12. Build the cost/recall
table for yourself.

<details>
<summary>✅ Solution</summary>

**Python**
```python
# day14_bakeoff.py
import re
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import (
    SystemMessage, HumanMessage, AIMessage, trim_messages,
)

load_dotenv()
fast = ChatGroq(model="llama-3.1-8b-instant", temperature=0)
smart = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

SYSTEM = SystemMessage("You are a concise assistant. Answer in one short sentence.")

TURNS = [
    "My name is Wasif and I work in fintech.",            # turn 1  — fact A
    "I'm building a document search system.",
    "I'm using Python.",
    "The documents are regulatory filings.",
    "I chose 900-character chunks after testing.",        # turn 5  — fact B
    "What is 9 times 7?",
    "Name a fruit.",
    "Name a planet.",
    "Name a colour.",
    "Name a country.",
    "Name an instrument.",
    "My deadline is the 14th of June.",                   # turn 12 — fact C
    "Name a programming language.",
    "Name a city.",
    "Tell me: my name, my chunk size, and my deadline.",  # ← the test
]

CHECKS = [("name (turn 1)", r"wasif"), ("chunk size (turn 5)", r"900"),
          ("deadline (turn 12)", r"14|june")]

def run_simple(strategy_fn, label):
    history, tokens = [SYSTEM], 0
    last = ""
    for turn in TURNS:
        history.append(HumanMessage(turn))
        res = smart.invoke(strategy_fn(history))
        tokens += (res.usage_metadata or {}).get("total_tokens", 0)
        history.append(res)
        last = res.content
    return label, tokens, last

def run_summary_buffer(label, keep_recent=3, summarise_after=5):
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
    from langchain_core.output_parsers import StrOutputParser

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a concise assistant. Answer in one short sentence.\n\n"
                   "Summary of earlier conversation:\n{summary}"),
        MessagesPlaceholder("recent"),
        ("human", "{input}"),
    ])

    summary, recent, tokens, last = "", [], 0, ""

    for turn in TURNS:
        msgs = prompt.invoke({"summary": summary or "(none)",
                              "recent": recent, "input": turn})
        res = smart.invoke(msgs)
        tokens += (res.usage_metadata or {}).get("total_tokens", 0)
        last = res.content

        recent += [HumanMessage(turn), AIMessage(res.content)]

        if len(recent) > summarise_after * 2:
            to_fold = recent[:-keep_recent * 2]
            recent = recent[-keep_recent * 2:]
            transcript = "\n".join(
                f"{'User' if m.type == 'human' else 'AI'}: {m.content}" for m in to_fold)
            fold_prompt = (
                f"Existing summary:\n{summary}\n\nNew exchanges:\n{transcript}\n\n"
                "Updated summary. PRESERVE every name, number, date and decision."
                if summary else
                f"Summarise, preserving every name, number, date and decision:\n\n{transcript}")
            r = fast.invoke(fold_prompt)
            tokens += (r.usage_metadata or {}).get("total_tokens", 0)
            summary = r.content.strip()

    return label, tokens, last

RESULTS = [
    run_simple(lambda m: m, "buffer"),
    run_simple(lambda m: [m[0]] + m[1:][-6:], "window(6)"),
    run_simple(lambda m: trim_messages(m, max_tokens=400, strategy="last",
                                       token_counter=smart, include_system=True,
                                       start_on="human"), "token_trim(400)"),
    run_summary_buffer("summary+buffer"),
]

header = "strategy         tokens  " + "  ".join(f"{n:<18}" for n, _ in CHECKS)
print(header)
print("-" * len(header))

for label, tokens, last in RESULTS:
    marks = "  ".join(
        f"{('✅' if re.search(pat, last, re.I) else '❌'):<18}" for _, pat in CHECKS)
    print(f"{label:<15} {tokens:>6}  {marks}")

print("\nfinal answers:")
for label, _, last in RESULTS:
    print(f"  {label:<15} {last.strip()[:80]}")
```

**JavaScript** — the same four strategies:
```js
const RESULTS = [
  await runSimple((m) => m, "buffer"),
  await runSimple((m) => [m[0], ...m.slice(1).slice(-6)], "window(6)"),
  await runSimple((m) => trimMessages(m, {
    maxTokens: 400, strategy: "last", tokenCounter: smart,
    includeSystem: true, startOn: "human" }), "tokenTrim(400)"),
  await runSummaryBuffer("summary+buffer"),
];
```

**Typical output:**

```
strategy         tokens  name (turn 1)       chunk size (turn 5)  deadline (turn 12)
------------------------------------------------------------------------------------
buffer            8420   ✅                  ✅                   ✅
window(6)         2980   ❌                  ❌                   ✅
token_trim(400)   3610   ❌                  ❌                   ✅
summary+buffer    4150   ✅                  ✅                   ✅
```

**Read the pattern in the window/trim rows: they remember turn 12 and forget turns 1 and 5.**
That's exactly what a sliding window does — recency without history. Notice this is a *predictable*
failure, not a random one, which is what makes it dangerous: it works fine in a short demo and
fails on real conversations.

**Summary+buffer gets all three at half the tokens of buffer.** That ratio is why it's the
practical default.

**Two caveats worth knowing.** Summary+buffer's advantage depends heavily on the folding prompt
— drop "PRESERVE every name, number, date and decision" and the specifics erode within a few
folds (§6's drift problem). And it costs extra *calls*, not just tokens: each fold is an LLM
invocation, which is why the fold uses the cheap model.
</details>

---

### Exercise 2 — Fact memory with contradiction handling ●●●○○

Extend the fact memory so it handles contradictions, confidence and staleness: each fact carries
a confidence score and a timestamp; contradictions replace rather than append; low-confidence
facts are re-confirmed rather than asserted. Test with a conversation containing two
contradictions and one uncertain statement.

<details>
<summary>✅ Solution</summary>

**Python**
```python
# day14_fact_memory_v2.py
from datetime import datetime, timezone
from typing import Literal
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq

load_dotenv()
fast = ChatGroq(model="llama-3.1-8b-instant", temperature=0)

class FactChange(BaseModel):
    key: str = Field(description="snake_case key, e.g. 'preferred_language'")
    value: str = Field(description="The value")
    operation: Literal["set", "append", "delete"] = Field(
        description="set = replace existing; append = add to a list; "
                    "delete = user retracted it")
    confidence: float = Field(ge=0, le=1,
        description="1.0 = user stated it directly; 0.5 = implied or hedged")
    contradicts: bool = Field(description="True if this contradicts a known fact")

class FactUpdate(BaseModel):
    """Durable facts learned from a message."""
    reasoning: str = Field(description="What you learned. Write this first.")
    updates: list[FactChange] = Field(description="Only new or changed facts")

class FactMemory:
    def __init__(self, confidence_floor=0.6):
        self.facts = {}          # key → {value, confidence, updated_at, history}
        self.floor = confidence_floor

    def observe(self, message):
        known = "\n".join(
            f"{k}: {v['value']} (confidence {v['confidence']:.1f})"
            for k, v in self.facts.items()) or "(nothing known yet)"

        result = fast.with_structured_output(FactUpdate).invoke(
            f"Extract durable facts about the user.\n\nAlready known:\n{known}\n\n"
            f'Message: "{message}"\n\n'
            "Only durable facts (identity, preferences, projects, constraints). "
            "Ignore transient questions.\n"
            "Set confidence 1.0 for direct statements, 0.5 for hedged ones "
            '("I think", "maybe", "probably").\n'
            "Set contradicts=true if this conflicts with something known."
        )

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        applied = []

        for u in result.updates:
            if u.operation == "delete":
                self.facts.pop(u.key, None)
                applied.append(("DELETE", u.key, "", u.confidence, False))
                continue

            prev = self.facts.get(u.key)

            # ── contradiction: REPLACE, and keep the old value in history ──
            if u.contradicts and prev:
                self.facts[u.key] = {
                    "value": u.value, "confidence": u.confidence, "updated_at": now,
                    "history": prev.get("history", []) + [
                        {"value": prev["value"], "until": now}],
                }
                applied.append(("REPLACE", u.key, f"{prev['value']} → {u.value}",
                                u.confidence, True))
                continue

            if u.operation == "append" and prev:
                self.facts[u.key] = {
                    "value": f"{prev['value']}, {u.value}",
                    "confidence": min(prev["confidence"], u.confidence),
                    "updated_at": now, "history": prev.get("history", []),
                }
                applied.append(("APPEND", u.key, u.value, u.confidence, False))
                continue

            self.facts[u.key] = {"value": u.value, "confidence": u.confidence,
                                 "updated_at": now, "history": []}
            applied.append(("SET", u.key, u.value, u.confidence, False))

        return applied

    def render(self):
        """Only assert confident facts; flag uncertain ones for confirmation."""
        confident, uncertain = [], []
        for k, v in self.facts.items():
            label = k.replace("_", " ")
            if v["confidence"] >= self.floor:
                confident.append(f"- {label}: {v['value']}")
            else:
                uncertain.append(f"- {label}: {v['value']} (unconfirmed — ask to verify)")

        parts = []
        if confident:
            parts.append("Known about the user:\n" + "\n".join(confident))
        if uncertain:
            parts.append("Possibly true (confirm before relying on):\n" + "\n".join(uncertain))
        return "\n\n".join(parts) or "(nothing known yet)"

# ── run ──────────────────────────────────────────────────────────────────
memory = FactMemory()

MESSAGES = [
    "Hi, I'm Wasif, a backend developer in Lahore.",
    "I write mostly JavaScript.",
    "I think I might be moving to Karachi soon, not sure yet.",     # ← hedged
    "I'm building a RAG system for regulatory filings.",
    "What's 12 times 12?",                                          # ← transient
    "Actually, I've switched entirely to Python for this project.", # ← CONTRADICTION 1
    "Confirmed — I've accepted the job, I'm definitely in Karachi now.",  # ← CONTRADICTION 2
]

for msg in MESSAGES:
    applied = memory.observe(msg)
    print(f"\n👤 {msg}")
    if not applied:
        print("   (nothing durable)")
    for op, key, detail, conf, contra in applied:
        flag = " ⚠️ contradiction" if contra else ""
        print(f"   {op:<8} {key} = {detail}  (conf {conf:.1f}){flag}")

print("\n" + "═" * 68)
print(memory.render())

print("\n" + "─" * 68)
print("fact history (audit trail):")
for k, v in memory.facts.items():
    if v.get("history"):
        past = " → ".join(h["value"] for h in v["history"])
        print(f"  {k}: {past} → {v['value']}")
```

**JavaScript** — the contradiction branch:
```js
// contradiction: REPLACE, and keep the old value in history
if (u.contradicts && prev) {
  this.facts[u.key] = {
    value: u.value,
    confidence: u.confidence,
    updatedAt: now,
    history: [...(prev.history ?? []), { value: prev.value, until: now }],
  };
}
```

**Expected behaviour:**

```
👤 I think I might be moving to Karachi soon, not sure yet.
   SET      location = Karachi (planned)  (conf 0.5)

👤 Actually, I've switched entirely to Python for this project.
   REPLACE  preferred_language = JavaScript → Python  (conf 1.0) ⚠️ contradiction

👤 Confirmed — I've accepted the job, I'm definitely in Karachi now.
   REPLACE  location = Karachi (planned) → Karachi  (conf 1.0) ⚠️ contradiction

════════════════════════════════════════════════════════════════════
Known about the user:
- name: Wasif
- role: backend developer
- preferred language: Python
- location: Karachi
- current project: RAG system for regulatory filings

────────────────────────────────────────────────────────────────────
fact history (audit trail):
  preferred_language: JavaScript → Python
  location: Karachi (planned) → Karachi
```

**Four production behaviours this demonstrates:**

1. **Contradictions replace, and the old value is kept as history.** Naive fact memory appends,
   producing `"JavaScript, Python"` — which then makes the assistant give advice in the wrong
   language. The audit trail matters when a user asks "why do you think that?".

2. **Confidence gates assertion.** The hedged "I might be moving" is stored but rendered as
   *unconfirmed*, so the assistant asks rather than asserting. Treating a 0.5-confidence guess as
   fact is how assistants develop confidently wrong opinions about people.

3. **Transient messages produce nothing.** "What's 12 times 12?" adds no facts — the schema
   returning an empty list is the correct outcome, and it's worth testing explicitly.

4. **Timestamps enable staleness handling.** A fact from two years ago ("currently learning
   Python") may be obsolete; with `updated_at` you can decay confidence over time or prompt for
   re-confirmation.

**The design point:** structured facts survive summarisation drift precisely *because* they're
fields rather than prose. A summary can paraphrase "prefers Python" into vagueness across five
rewrites; a `preferred_language` field cannot.
</details>

---

### Exercise 3 — Memory-aware retrieval ●●●○○

Combine memory and RAG: use the conversation's fact memory to **improve retrieval**. If the user
has told you they use Python and work in fintech, a question like "how do I handle rate limits?"
should retrieve Python and fintech-relevant documents. Show retrieval with and without the
memory-informed query.

<details>
<summary>✅ Solution</summary>

**Python**
```python
# day14_memory_aware_retrieval.py
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_ollama import OllamaEmbeddings
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_core.documents import Document

load_dotenv()
fast = ChatGroq(model="llama-3.1-8b-instant", temperature=0)
embeddings = OllamaEmbeddings(model="nomic-embed-text")

DOCS = [
    Document(page_content="Python rate limiting: use the tenacity library with exponential "
                          "backoff. Decorate the call with @retry(wait=wait_exponential()).",
             metadata={"lang": "python", "topic": "rate limits"}),
    Document(page_content="JavaScript rate limiting: use p-retry or implement setTimeout-based "
                          "backoff with jitter in a wrapper function.",
             metadata={"lang": "javascript", "topic": "rate limits"}),
    Document(page_content="Rate limiting in regulated finance: FCA guidance requires audit logs "
                          "of every throttled request, retained for 5 years.",
             metadata={"lang": "any", "topic": "rate limits", "domain": "fintech"}),
    Document(page_content="Rate limiting for e-commerce: prioritise checkout requests over "
                          "browsing when throttling to protect conversion.",
             metadata={"lang": "any", "topic": "rate limits", "domain": "ecommerce"}),
    Document(page_content="Python chunking: use RecursiveCharacterTextSplitter from "
                          "langchain_text_splitters with chunk_size and chunk_overlap.",
             metadata={"lang": "python", "topic": "chunking"}),
    Document(page_content="JavaScript chunking: import RecursiveCharacterTextSplitter from "
                          "@langchain/textsplitters and await splitText().",
             metadata={"lang": "javascript", "topic": "chunking"}),
]

store = InMemoryVectorStore.from_documents(DOCS, embeddings)

# ── the user's remembered facts ──────────────────────────────────────────
FACTS = {
    "preferred_language": "Python",
    "industry": "fintech (regulated)",
    "current_project": "document search over regulatory filings",
}

class EnrichedQuery(BaseModel):
    """A search query enriched with what we know about the user."""
    reasoning: str = Field(description="Which facts are relevant here. Write this first.")
    enriched: str = Field(description="The search query, enriched with relevant user context")
    used_facts: list[str] = Field(description="Which fact keys were relevant. May be empty.")

def enrich_query(question, facts):
    known = "\n".join(f"{k}: {v}" for k, v in facts.items())
    return fast.with_structured_output(EnrichedQuery).invoke(
        f"Known about the user:\n{known}\n\n"
        f'Question: "{question}"\n\n'
        "Rewrite the question as a document-search query, incorporating ONLY the user "
        "facts that are actually relevant to this question. If no facts are relevant, "
        "return the question unchanged and leave used_facts empty."
    )

QUESTIONS = [
    "how do I handle rate limits?",          # language + industry both relevant
    "how do I split documents?",             # only language relevant
    "what is the capital of France?",        # nothing relevant
]

for question in QUESTIONS:
    print(f"\n{'═' * 74}\n❓ {question}\n{'═' * 74}")

    # ── WITHOUT memory ───────────────────────────────────────────────────
    plain = store.similarity_search(question, k=2)
    print("\nWITHOUT memory:")
    for d in plain:
        print(f"   [{d.metadata.get('lang')}/{d.metadata.get('domain', '-')}] "
              f"{d.page_content[:62]}")

    # ── WITH memory ──────────────────────────────────────────────────────
    e = enrich_query(question, FACTS)
    enriched = store.similarity_search(e.enriched, k=2)

    print(f"\nWITH memory:")
    print(f'   enriched query: "{e.enriched}"')
    print(f"   used facts: {', '.join(e.used_facts) or '(none)'}")
    for d in enriched:
        print(f"   [{d.metadata.get('lang')}/{d.metadata.get('domain', '-')}] "
              f"{d.page_content[:62]}")
```

**JavaScript** — the enrichment step:
```js
const EnrichedQuery = z.object({
  reasoning: z.string().describe("Which facts are relevant here. Write this first."),
  enriched: z.string().describe("The search query, enriched with relevant user context"),
  usedFacts: z.array(z.string()).describe("Which fact keys were relevant. May be empty."),
});

const enrichQuery = (question, facts) =>
  fast.withStructuredOutput(EnrichedQuery).invoke(
    `Known about the user:\n${Object.entries(facts).map(([k, v]) => `${k}: ${v}`).join("\n")}\n\n` +
    `Question: "${question}"\n\n` +
    `Rewrite as a document-search query, incorporating ONLY relevant user facts. ` +
    `If none are relevant, return the question unchanged.`
  );
```

**Expected output:**

```
❓ how do I handle rate limits?
WITHOUT memory:
   [javascript/-]  JavaScript rate limiting: use p-retry or implement setTimeout…
   [python/-]      Python rate limiting: use the tenacity library with exponential…

WITH memory:
   enriched query: "Python rate limiting in regulated fintech with audit logging"
   used facts: preferred_language, industry
   [python/-]       Python rate limiting: use the tenacity library with exponential…
   [any/fintech]    Rate limiting in regulated finance: FCA guidance requires audit…

❓ what is the capital of France?
WITH memory:
   used facts: (none)                                     ← correctly ignored
```

**Three things worth extracting:**

1. **Memory improves *retrieval*, not just tone.** Without it, the top result is JavaScript
   documentation for a Python developer — useless, and the model will happily answer from it.
   Memory-informed retrieval surfaces both the right language *and* the domain-specific
   compliance document the user actually needs.

2. **`usedFacts` is essential, not decorative.** It makes the enrichment auditable, and it lets
   you verify the model isn't injecting irrelevant context. The "capital of France" case
   returning an empty list is the behaviour to test for — over-eager enrichment would produce
   "capital of France for Python fintech developers", which retrieves worse than the plain query.

3. **This is Day 13's query transformation, with memory as the source.** Same mechanism as
   multi-query or HyDE; the novelty is *where the extra signal comes from*. Combining it with
   metadata filters is the natural next step — the facts could set `lang=python` as a hard filter
   rather than a soft hint.

**Production caution:** enrichment can over-constrain. If the user asks a general question, forcing
their profile into every query narrows retrieval harmfully. The `usedFacts` field plus a prompt
that explicitly permits "no facts relevant" is what prevents that — and it's worth an eval case.
</details>

---

### Exercise 4 — Session persistence with resumption ●●●○○

Build a session store that persists messages, summary and facts to disk, and a CLI that resumes a
named session across process restarts. On resume, print what it remembers. Handle concurrent
sessions correctly.

<details>
<summary>✅ Solution</summary>

**Python**
```python
# day14_sessions.py
import json, sys
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser

load_dotenv()
fast = ChatGroq(model="llama-3.1-8b-instant", temperature=0)
smart = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.4)

SESSION_DIR = Path("./.sessions")

# ══════════════════ STORE ════════════════════════════════════════════════
class SessionStore:
    """Per-session persistence. Each session is an independent file — no shared state."""

    def __init__(self, directory=SESSION_DIR):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id):
        safe = "".join(c for c in session_id if c.isalnum() or c in "-_")
        return self.dir / f"{safe}.json"

    def load(self, session_id):
        p = self._path(session_id)
        if not p.exists():
            return {"messages": [], "summary": "", "facts": {},
                    "turns": 0, "created_at": None}

        raw = json.loads(p.read_text())
        cls = {"human": HumanMessage, "ai": AIMessage}
        return {
            "messages": [cls[m["role"]](m["content"]) for m in raw["messages"]],
            "summary": raw.get("summary", ""),
            "facts": raw.get("facts", {}),
            "turns": raw.get("turns", 0),
            "created_at": raw.get("created_at"),
        }

    def save(self, session_id, state):
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._path(session_id).write_text(json.dumps({
            "messages": [{"role": m.type, "content": m.content} for m in state["messages"]],
            "summary": state["summary"],
            "facts": state["facts"],
            "turns": state["turns"],
            "created_at": state.get("created_at") or now,
            "updated_at": now,
        }, indent=2))

    def list_sessions(self):
        out = []
        for p in sorted(self.dir.glob("*.json")):
            raw = json.loads(p.read_text())
            out.append({"id": p.stem, "turns": raw.get("turns", 0),
                        "updated_at": raw.get("updated_at", "?"),
                        "facts": len(raw.get("facts", {}))})
        return out

# ══════════════════ CHAT ═════════════════════════════════════════════════
prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are a helpful assistant with memory across sessions.\n\n"
     "What you know about this user:\n{facts}\n\n"
     "Summary of earlier conversation:\n{summary}"),
    MessagesPlaceholder("recent"),
    ("human", "{input}"),
])

chain = prompt | smart | StrOutputParser()

KEEP_RECENT = 3
SUMMARISE_AFTER = 5

def fold_summary(summary, messages):
    transcript = "\n".join(
        f"{'User' if m.type == 'human' else 'AI'}: {m.content}" for m in messages)
    p = (f"Existing summary:\n{summary}\n\nNew exchanges:\n{transcript}\n\n"
         "Updated summary. PRESERVE every name, number, date and decision."
         if summary else
         f"Summarise, preserving every name, number, date and decision:\n\n{transcript}")
    return fast.invoke(p).content.strip()

def extract_facts(message, facts):
    from pydantic import BaseModel, Field

    class Facts(BaseModel):
        """Durable facts about the user."""
        updates: dict[str, str] = Field(
            description="key→value of NEW or CHANGED durable facts. Empty if none.")

    known = "\n".join(f"{k}: {v}" for k, v in facts.items()) or "(nothing)"
    r = fast.with_structured_output(Facts).invoke(
        f"Known:\n{known}\n\nMessage: \"{message}\"\n\n"
        "Extract durable facts (identity, preferences, projects). "
        "Ignore transient questions. Replace contradicted values.")
    return r.updates

def chat(session_id):
    store = SessionStore()
    state = store.load(session_id)

    print("╔" + "═" * 62 + "╗")
    print(f"║  session: {session_id:<50} ║")
    if state["turns"]:
        print(f"║  resumed: {state['turns']} previous turns, "
              f"{len(state['facts'])} facts remembered{' ' * 13}║")
    else:
        print("║  new session" + " " * 49 + "║")
    print("╚" + "═" * 62 + "╝")

    if state["facts"]:
        print("\n🧠 I remember:")
        for k, v in state["facts"].items():
            print(f"   · {k.replace('_', ' ')}: {v}")
    if state["summary"]:
        print(f"\n📝 Earlier: {state['summary'][:150]}")
    print()

    recent = state["messages"][-KEEP_RECENT * 2:]

    while True:
        try:
            text = input("you › ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text or text == "/exit":
            break

        if text == "/forget":
            state = {"messages": [], "summary": "", "facts": {}, "turns": 0,
                     "created_at": state.get("created_at")}
            recent = []
            store.save(session_id, state)
            print("  memory cleared\n")
            continue

        if text == "/memory":
            print(f"  facts: {state['facts']}")
            print(f"  summary: {state['summary'][:200]}")
            print(f"  turns: {state['turns']}\n")
            continue

        facts_str = "\n".join(f"- {k}: {v}" for k, v in state["facts"].items()) or "(nothing yet)"
        answer = chain.invoke({
            "facts": facts_str,
            "summary": state["summary"] or "(no earlier conversation)",
            "recent": recent,
            "input": text,
        })

        print(f"bot › {answer.strip()}\n")

        # ── update all three memory layers ───────────────────────────────
        state["messages"] += [HumanMessage(text), AIMessage(answer)]
        state["turns"] += 1
        recent = state["messages"][-KEEP_RECENT * 2:]

        new_facts = extract_facts(text, state["facts"])
        if new_facts:
            state["facts"].update(new_facts)
            print(f"      🧠 learned: {', '.join(new_facts)}\n")

        if len(state["messages"]) > SUMMARISE_AFTER * 2:
            to_fold = state["messages"][:-KEEP_RECENT * 2]
            state["summary"] = fold_summary(state["summary"], to_fold)
            state["messages"] = state["messages"][-KEEP_RECENT * 2:]

        store.save(session_id, state)      # ⭐ persist EVERY turn

# ══════════════════ CLI ══════════════════════════════════════════════════
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "chat"

    if cmd == "list":
        for s in SessionStore().list_sessions():
            print(f"  {s['id']:<20} {s['turns']:>3} turns · {s['facts']} facts · "
                  f"{s['updated_at']}")
    else:
        chat(sys.argv[2] if len(sys.argv) > 2 else "default")
```

```bash
python day14_sessions.py chat wasif
# ...have a conversation, exit...
python day14_sessions.py chat wasif      # resumes with memory
python day14_sessions.py chat someone-else   # completely independent
python day14_sessions.py list
```

**JavaScript** — the store, which is the interesting half:
```js
class SessionStore {
  constructor(dir = "./.sessions") { this.dir = dir; }

  path(id) {
    const safe = id.replace(/[^a-zA-Z0-9-_]/g, "");
    return `${this.dir}/${safe}.json`;
  }

  async load(id) {
    try {
      const raw = JSON.parse(await fs.readFile(this.path(id), "utf8"));
      const cls = { human: HumanMessage, ai: AIMessage };
      return {
        messages: raw.messages.map((m) => new cls[m.role](m.content)),
        summary: raw.summary ?? "", facts: raw.facts ?? {}, turns: raw.turns ?? 0,
      };
    } catch {
      return { messages: [], summary: "", facts: {}, turns: 0 };
    }
  }

  async save(id, state) {
    await fs.mkdir(this.dir, { recursive: true });
    await fs.writeFile(this.path(id), JSON.stringify({
      messages: state.messages.map((m) => ({ role: m.getType(), content: m.content })),
      summary: state.summary, facts: state.facts, turns: state.turns,
      updatedAt: new Date().toISOString(),
    }, null, 2));
  }
}
```

**Five design points:**

1. **One file per session — no shared mutable state.** This is the structural fix for the 0.x
   concurrency bug from §6. Two users cannot interleave, because they never touch the same
   object. In a real deployment this is a database row keyed by session ID; the principle is
   identical.

2. **Save every turn, not on exit.** Processes crash, users close tabs. Losing a conversation
   because you batched the write is avoidable.

3. **All three layers persist:** recent messages (short-term), summary (mid-term), facts
   (long-term). Reloading restores the full picture.

4. **The session ID is sanitised** before becoming a filename — `../../etc/passwd` as a session
   ID would otherwise be a path-traversal vulnerability. Small detail, real class of bug.

5. **`/memory` and `/forget` exist.** Users should be able to see and delete what a system
   remembers about them. That's a GDPR requirement in many jurisdictions, and it's also just good
   product design — an assistant with invisible, unerasable memory is unsettling.

**What this is:** a hand-rolled checkpointer. LangGraph's `SqliteSaver` does this plus
versioning, time travel and interrupt support, keyed by `thread_id` instead of `session_id`.
Having built it, Day 20 will read as "oh, it's this, done properly".
</details>

---

### Exercise 5 — 🏆 StudyBuddy v3: memory + RAG ●●●●●

The Week 2 capstone. Combine everything: StudyBuddy now ingests your documents (Days 09–12),
retrieves with reranking (Day 13), remembers you across sessions (today), and uses memory to
improve retrieval. Persist everything, verify citations, and stream.

<details>
<summary>✅ Solution</summary>

**Python**
```python
# studybuddy_v3.py
"""StudyBuddy v3 — RAG over your documents, with memory across sessions.

    python studybuddy_v3.py ingest ./notes
    python studybuddy_v3.py chat wasif
"""
import hashlib, json, re, sys, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

load_dotenv()

EMBEDDING_MODEL = "nomic-embed-text"
DB_DIR = "./studybuddy_v3_db"
SESSION_DIR = Path("./.studybuddy_sessions")

fast = ChatGroq(model="llama-3.1-8b-instant", temperature=0)     # memory, rerank, rewrite
smart = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.3)  # answering
embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)

store = Chroma(collection_name="studybuddy_v3", embedding_function=embeddings,
               persist_directory=DB_DIR, collection_metadata={"hnsw:space": "cosine"})

# ═══════════════ INGEST (Days 09-11) ═════════════════════════════════════
def content_hash(text):
    return hashlib.sha256(f"{EMBEDDING_MODEL}:{text}".encode()).hexdigest()[:16]

def chunk_file(path: Path):
    raw = path.read_text(encoding="utf8", errors="replace")
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
    chunks = []

    if path.suffix.lower() == ".md":
        header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")], strip_headers=True)
        sections = splitter.split_documents(header_splitter.split_text(raw)) or []
        for s in sections:
            crumb = " > ".join(s.metadata[k] for k in ("h1", "h2", "h3") if k in s.metadata)
            chunks.append(Document(
                page_content=f"{crumb}\n\n{s.page_content}" if crumb else s.page_content,
                metadata={"source": path.name, "breadcrumb": crumb or path.stem}))
    else:
        for piece in splitter.split_text(raw):
            chunks.append(Document(page_content=f"{path.stem}\n\n{piece}",
                                   metadata={"source": path.name, "breadcrumb": path.stem}))

    return [c for c in chunks if len(c.page_content.strip()) >= 50]

def ingest(folder):
    files = [p for p in Path(folder).rglob("*") if p.suffix.lower() in {".md", ".txt"}]
    if not files:
        print(f"no .md/.txt files under {folder}")
        return

    existing = set(store.get(include=[])["ids"])
    added = skipped = 0

    for path in files:
        new = [(content_hash(c.page_content), c) for c in chunk_file(path)]
        fresh = [(h, c) for h, c in new if h not in existing]
        if fresh:
            store.add_documents([c for _, c in fresh], ids=[h for h, _ in fresh])
            existing.update(h for h, _ in fresh)
        added += len(fresh)
        skipped += len(new) - len(fresh)
        print(f"  {path.name:<40} {len(new):>4} chunks, {len(fresh):>4} new")

    print(f"\n✅ {added} added · {skipped} already present")

# ═══════════════ MEMORY (today) ══════════════════════════════════════════
class Sessions:
    def __init__(self, directory=SESSION_DIR):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, sid):
        return self.dir / f"{''.join(c for c in sid if c.isalnum() or c in '-_')}.json"

    def load(self, sid):
        p = self._path(sid)
        if not p.exists():
            return {"messages": [], "summary": "", "facts": {}, "turns": 0}
        raw = json.loads(p.read_text())
        cls = {"human": HumanMessage, "ai": AIMessage}
        return {"messages": [cls[m["role"]](m["content"]) for m in raw["messages"]],
                "summary": raw.get("summary", ""), "facts": raw.get("facts", {}),
                "turns": raw.get("turns", 0)}

    def save(self, sid, s):
        self._path(sid).write_text(json.dumps({
            "messages": [{"role": m.type, "content": m.content} for m in s["messages"]],
            "summary": s["summary"], "facts": s["facts"], "turns": s["turns"],
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }, indent=2))

class Facts(BaseModel):
    """Durable facts about the user."""
    updates: dict[str, str] = Field(
        description="key→value of NEW or CHANGED durable facts. Empty if none. "
                    "Replace contradicted values rather than appending.")

def extract_facts(message, known):
    k = "\n".join(f"{a}: {b}" for a, b in known.items()) or "(nothing)"
    return fast.with_structured_output(Facts).invoke(
        f"Known:\n{k}\n\nMessage: \"{message}\"\n\n"
        "Extract durable facts (identity, preferences, level, projects). "
        "Ignore transient questions.").updates

def fold_summary(summary, messages):
    transcript = "\n".join(
        f"{'User' if m.type == 'human' else 'AI'}: {m.content}" for m in messages)
    p = (f"Existing summary:\n{summary}\n\nNew:\n{transcript}\n\n"
         "Updated summary. PRESERVE every name, number, date and decision."
         if summary else f"Summarise, preserving specifics:\n\n{transcript}")
    return fast.invoke(p).content.strip()

# ═══════════════ RETRIEVAL (Days 12-13) ══════════════════════════════════
class SearchQuery(BaseModel):
    """A standalone, memory-enriched search query."""
    reasoning: str = Field(description="One sentence. Write this first.")
    query: str = Field(description="Standalone search query, enriched with relevant user context")
    needs_retrieval: bool = Field(
        description="False for greetings, thanks, or questions needing no documents")

class Relevance(BaseModel):
    """Document relevance."""
    score: float = Field(ge=0, le=10, description="0 = irrelevant, 10 = directly answers")

class Citation(BaseModel):
    source_number: int
    quote: str = Field(description="EXACT sentence from that source, verbatim")

class Answer(BaseModel):
    """A grounded answer."""
    answer: str = Field(description="The answer in prose, no citation markers")
    citations: list[Citation] = Field(description="One per claim. Empty if not answerable.")
    answer_found: bool

def build_query(question, history, facts):
    f = "\n".join(f"{k}: {v}" for k, v in facts.items()) or "(nothing known)"
    h = "\n".join(f"{m.type}: {m.content[:100]}" for m in history[-4:]) or "(no history)"
    return fast.with_structured_output(SearchQuery).invoke(
        f"User facts:\n{f}\n\nRecent conversation:\n{h}\n\n"
        f'Question: "{question}"\n\n'
        "Produce a STANDALONE document-search query. Resolve pronouns and references from "
        "the history. Add user context ONLY if genuinely relevant. "
        "Set needs_retrieval=false for greetings or chitchat.")

def retrieve_and_rerank(query, fetch_k=8, top_n=3):
    candidates = store.as_retriever(search_kwargs={"k": fetch_k}).invoke(query)
    if len(candidates) <= top_n:
        return candidates
    scored = []
    for d in candidates:
        r = fast.with_structured_output(Relevance).invoke(
            f"Question: {query}\n\nDocument: {d.page_content}\n\nRelevance 0-10?")
        scored.append((d, r.score))
    return [d for d, _ in sorted(scored, key=lambda x: -x[1])[:top_n]]

answer_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are StudyBuddy, a patient tutor.\n\n"
     "What you know about this learner:\n{facts}\n\n"
     "Earlier conversation:\n{summary}\n\n"
     "Answer using ONLY the numbered context below. For every factual claim give a citation "
     "with the source number and the EXACT sentence copied verbatim. "
     "If the context lacks the answer, set answer_found to false.\n\n"
     "Context:\n{context}"),
    MessagesPlaceholder("recent"),
    ("human", "{input}"),
])

chat_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are StudyBuddy, a friendly tutor.\n\nAbout this learner:\n{facts}\n\n"
               "Answer briefly. If they need document-specific info you don't have, say so."),
    MessagesPlaceholder("recent"),
    ("human", "{input}"),
])

def verify(c, docs):
    i = c.source_number - 1
    if not (0 <= i < len(docs)):
        return False
    norm = lambda s: re.sub(r"\s+", " ", s.lower().strip())
    return norm(c.quote)[:45] in norm(docs[i].page_content)

# ═══════════════ CHAT ════════════════════════════════════════════════════
KEEP_RECENT, SUMMARISE_AFTER = 3, 5

def chat(session_id):
    sessions = Sessions()
    state = sessions.load(session_id)
    n_chunks = store._collection.count()

    print("╔" + "═" * 64 + "╗")
    print(f"║  StudyBuddy v3 — {n_chunks:>5} chunks indexed" + " " * 26 + "║")
    print(f"║  session '{session_id}' · {state['turns']} previous turns · "
          f"{len(state['facts'])} facts{' ' * max(0, 14 - len(session_id))}║")
    print("╚" + "═" * 64 + "╝")

    if state["facts"]:
        print("\n🧠 " + " · ".join(f"{k.replace('_', ' ')}: {v}"
                                   for k, v in list(state["facts"].items())[:4]))
    print("\n/memory /forget /sources /exit\n")

    recent = state["messages"][-KEEP_RECENT * 2:]

    while True:
        try:
            text = input("you › ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text or text == "/exit":
            break

        if text == "/memory":
            print(f"  facts: {state['facts']}\n  summary: {state['summary'][:200]}\n")
            continue
        if text == "/forget":
            state = {"messages": [], "summary": "", "facts": {}, "turns": 0}
            recent = []
            sessions.save(session_id, state)
            print("  memory cleared\n")
            continue
        if text == "/sources":
            raw = store.get(include=["metadatas"])
            src = {}
            for m in raw["metadatas"]:
                src[m.get("source", "?")] = src.get(m.get("source", "?"), 0) + 1
            for s, n in sorted(src.items()):
                print(f"  {n:>5}  {s}")
            print()
            continue

        t0 = time.time()
        facts_str = "\n".join(f"- {k}: {v}" for k, v in state["facts"].items()) or "(nothing yet)"

        try:
            sq = build_query(text, state["messages"], state["facts"])

            # ── no retrieval needed → plain chat ─────────────────────────
            if not sq.needs_retrieval:
                answer = (chat_prompt | smart | StrOutputParser()).invoke(
                    {"facts": facts_str, "recent": recent, "input": text})
                print(f"bot › {answer.strip()}\n")
                docs = []
            else:
                if sq.query.strip().lower() != text.lower():
                    print(f"  ↳ searching: \"{sq.query}\"")

                docs = retrieve_and_rerank(sq.query)
                print("  📚 " + " · ".join(
                    f"[{i}] {d.metadata.get('breadcrumb', '?')[:26]}"
                    for i, d in enumerate(docs, 1)))

                context = "\n\n---\n\n".join(
                    f"[{i}] ({d.metadata.get('source')}) {d.page_content}"
                    for i, d in enumerate(docs, 1))

                result = (answer_prompt | smart.with_structured_output(Answer)).invoke({
                    "facts": facts_str,
                    "summary": state["summary"] or "(none)",
                    "context": context, "recent": recent, "input": text,
                })

                if not result.answer_found:
                    print("\n  ⚠️  I couldn't find that in your documents.\n")
                    answer = "I don't have that in the indexed documents."
                else:
                    answer = result.answer
                    print(f"\nbot › {answer.strip()}\n")
                    for c in result.citations:
                        ok = verify(c, docs)
                        d = docs[c.source_number - 1] if 0 < c.source_number <= len(docs) else None
                        label = f"{d.metadata.get('source')} · {d.metadata.get('breadcrumb')}" \
                                if d else "INVALID"
                        print(f"  {'✅' if ok else '⚠️ '} [{c.source_number}] {label}")
                    print()

            # ── update memory ────────────────────────────────────────────
            state["messages"] += [HumanMessage(text), AIMessage(answer)]
            state["turns"] += 1
            recent = state["messages"][-KEEP_RECENT * 2:]

            new_facts = extract_facts(text, state["facts"])
            if new_facts:
                state["facts"].update(new_facts)
                print(f"      🧠 learned: {', '.join(new_facts)}\n")

            if len(state["messages"]) > SUMMARISE_AFTER * 2:
                to_fold = state["messages"][:-KEEP_RECENT * 2]
                state["summary"] = fold_summary(state["summary"], to_fold)
                state["messages"] = state["messages"][-KEEP_RECENT * 2:]

            sessions.save(session_id, state)
            print(f"  ⏱  {(time.time() - t0) * 1000:.0f}ms\n")

        except Exception as e:
            print(f"\n  ⚠️  {str(e)[:130]}\n")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "chat"
    if cmd == "ingest":
        ingest(sys.argv[2] if len(sys.argv) > 2 else ".")
    else:
        chat(sys.argv[2] if len(sys.argv) > 2 else "default")
```

**JavaScript** — the distinctive integration points:
```js
// 1. Memory-enriched, history-resolved, retrieval-gated query
const sq = await fast.withStructuredOutput(SearchQuery).invoke(
  `User facts:\n${factsStr}\n\nRecent:\n${historyStr}\n\nQuestion: "${text}"\n\n` +
  `Produce a STANDALONE search query. Resolve references. Add user context only if relevant. ` +
  `Set needsRetrieval=false for greetings.`);

// 2. Skip retrieval entirely when it isn't needed (Day 13's adaptive routing)
if (!sq.needsRetrieval) { /* plain chat path */ }

// 3. Retrieve wide, rerank narrow (Day 13)
const docs = await retrieveAndRerank(sq.query, 8, 3);

// 4. Three memory layers persisted every turn (today)
state.messages.push(new HumanMessage(text), new AIMessage(answer));
Object.assign(state.facts, await extractFacts(text, state.facts));
await sessions.save(sessionId, state);
```

**Try it:**

```bash
python studybuddy_v3.py ingest ./my-notes
python studybuddy_v3.py chat wasif

you › I'm studying for a distributed systems exam. I prefer short answers.
      🧠 learned: current_goal, answer_preference

you › what does the CAP theorem say?
  📚 [1] Distributed Systems > CAP  · [2] …
bot › …
  ✅ [1] notes.md · Distributed Systems > CAP

you › /exit

python studybuddy_v3.py chat wasif        # resumes
🧠 current goal: distributed systems exam · answer preference: short
```

**The whole of Week 2 is in this one program:**

| Day | Where |
|---|---|
| 08 | Cheap model for memory/rerank/rewrite, strong model for answering |
| 09 | Markdown header injection, per-filetype chunking, minimum length |
| 10 | Batched embeddings, model-namespaced content hashing |
| 11 | Persistent Chroma, hash-as-id idempotent upsert |
| 12 | Grounding contract, verified citations, refusal path |
| 13 | Retrieve-wide-rerank-narrow, adaptive skip-retrieval routing |
| 14 | Three memory layers, cross-session persistence, memory-enriched retrieval |

**Six design decisions worth defending in an interview:**

1. **One model call decides three things at once** — is retrieval needed, what should the
   standalone query be, and which user facts are relevant. Three separate calls would triple the
   latency for no benefit.
2. **`needsRetrieval` gates the whole RAG path.** Greetings skip embedding, retrieval, reranking
   and the large context — a meaningful share of real turns.
3. **Memory enriches the query, not just the tone.** A Python user asking about rate limits
   retrieves Python documents.
4. **Facts replace on contradiction**, so switching languages updates rather than accumulates.
5. **Everything persists every turn**, keyed by session — no shared mutable state, so concurrent
   users can't interleave.
6. **Citations are verified**, and unverified ones are visibly flagged rather than silently shown.

**And here's the honest limitation — the bridge to Week 3.**

Look at the `chat()` function. It's a `while` loop containing branches, try/except, manual state
updates, and conditional summarisation. You've now hand-written a state machine four times across
Days 13–14: corrective RAG, self-RAG, the production pipeline, and this.

Now try to add: *streaming* the answer while still verifying citations afterwards; *pausing* for
the user to approve an expensive deep-search; *resuming* a conversation from three turns ago to
try a different path; or letting the model *decide for itself* to search twice.

Each one means more flags, deeper nesting, and more state threaded by hand. That's not a failure
of your code — it's LCEL reaching its limit. **Loops, persistent state, interrupts and
time-travel are exactly what LangGraph provides as infrastructure.**

Week 3 rebuilds this as a graph, and everything you hand-rolled becomes declarative.
</details>

---

## 9. Interview questions

### Basic

<details>
<summary><b>Q: Do LLMs have memory?</b></summary>

No. Every API call is stateless — the model retains nothing between requests. Apparent memory is
entirely the application re-sending previous messages as part of the input.

So "memory" in an LLM framework always means a *strategy for deciding what to re-send* within a
finite context budget: everything (buffer), the recent N (window), what fits a token budget
(trim), a compressed summary, extracted facts, or retrieved relevant past turns.
</details>

<details>
<summary><b>Q: What are the main memory strategies?</b></summary>

- **Buffer** — send everything. Perfect recall, but cost is O(n²) over a conversation and it
  eventually exceeds the context window.
- **Window** — send the last N messages. Bounded cost, hard forgetting at the boundary.
- **Token buffer** — send as many recent messages as fit a token budget. Same forgetting,
  predictable cost.
- **Summary** — compress older turns into a running summary. Bounded and long-lived, but lossy.
- **Summary + buffer** — summary of old turns plus recent turns verbatim. The practical default.
- **Entity/fact memory** — extract structured facts. Tiny, persists across sessions, updatable.
- **Vector memory** — embed past turns and retrieve the relevant ones. Constant cost regardless
  of history length.

Production systems usually layer three: recent verbatim, rolling summary, and durable facts.
</details>

<details>
<summary><b>Q: What does `trimMessages` do?</b></summary>

Bounds a message list to a token budget. Key options: `strategy` (keep first or last),
`tokenCounter` (use the model's tokenizer for accuracy), `includeSystem` (never drop the system
message), and `startOn: "human"` — which ensures the trimmed history begins on a valid turn.

That last one prevents a real class of bug: trimming can otherwise leave a dangling tool message
or start on an AI turn, which some providers reject with a 400.
</details>

<details>
<summary><b>Q: Difference between memory and RAG?</b></summary>

The same retrieval mechanism over different corpora. RAG retrieves from **documents** — external
knowledge the model never saw. Memory retrieves from **conversations** — what was previously said
between this user and the system.

"What's our refund policy?" is RAG. "What did I tell you last week?" is memory. They have
different lifetimes, different privacy implications, and different failure modes, so keep them as
separate retrievers and be explicit in the prompt about which context is which.
</details>

### Intermediate

<details>
<summary><b>Q: How has memory changed in modern LangChain?</b></summary>

The 0.x `Memory` classes — `ConversationBufferMemory` and friends — were stateful objects that
mutated themselves as a side effect of running a chain. Three problems ended that design:
**hidden state** (you couldn't see what was in the prompt without inspecting the object),
**concurrency bugs** (a module-scope memory shared across web requests interleaved different
users' conversations — a bug that shipped to production), and **no persistence** (restart the
process, lose everything).

The modern approach separates three concerns explicitly: **storage** is yours (an array, a
database row, or a LangGraph checkpointer), **injection** is `MessagesPlaceholder`, and
**bounding** is `trimMessages` or a summarisation step you write. The legacy classes moved to
`langchain-classic` for migration, and the intended production path for persistent conversational
state is LangGraph checkpointers.

It's the same design lesson as the legacy chains: abstractions should hide implementation, not
control flow or state.
</details>

<details>
<summary><b>Q: Why does summary memory degrade over long conversations?</b></summary>

Progressive summarisation is repeated lossy compression. Each fold summarises *the previous
summary* plus new turns, so a detail from turn 2 has been compressed four or five times by turn
40. Specifics erode first — numbers, names, exact decisions — leaving increasingly generic prose.
It's the same dilution as map-reduce over many levels.

Mitigations: instruct the summariser explicitly to preserve names, numbers, dates and decisions;
keep critical values in **structured fact memory** instead, where they're fields that can't be
paraphrased away; and periodically re-summarise from the original transcript if you retain it.

That's the real argument for a layered design — prose summaries for gist, structured facts for
anything that must not drift.
</details>

<details>
<summary><b>Q: How would you implement memory that persists across sessions?</b></summary>

Separate the layers by lifetime. **Within a conversation**: recent messages verbatim plus a
rolling summary, stored per session. **Across conversations**: extracted structured facts —
preferences, identity, ongoing projects — stored as a database row keyed by user, not as messages.

Implementation essentials: key everything by session/user ID with no shared mutable state (that's
the structural fix for the old concurrency bug); persist on every turn rather than on exit,
because processes crash; handle contradictions by *replacing* values rather than appending, or
you accumulate conflicting facts; timestamp facts so stale ones can decay or be re-confirmed; and
give users a way to view and delete what you remember, which is both a compliance requirement and
good product design.

In LangGraph this is a checkpointer (per-thread conversation state) plus a Store (cross-thread
long-term facts) — the same split, provided as infrastructure.
</details>

<details>
<summary><b>Q: When would you use vector memory over summarisation?</b></summary>

When history is long and users reference *specific* past exchanges rather than needing continuous
context — a support assistant where someone says "you helped me with this three months ago", or a
tutor spanning many sessions.

Vector memory has constant cost regardless of history length, and preserves exact wording rather
than a lossy paraphrase. The trade-off is that it retrieves discrete fragments, so it can miss
context that a continuous summary would carry implicitly, and it needs the same care as document
RAG — store the whole exchange rather than individual messages, since a question without its
answer retrieves poorly.

In practice they're complementary: summary for recent continuity, vector retrieval for the long
tail.
</details>

### Advanced

<details>
<summary><b>Q: Design the memory system for a personal AI assistant used daily for years.</b></summary>

The defining constraint is that history becomes unboundedly large while relevance stays sparse —
so no single strategy works, and the design is about **lifetimes**.

**Layered by lifetime.** Working memory: the last few turns verbatim, for conversational
coherence. Episodic: per-conversation summaries, retained and retrievable. Semantic: structured
facts about the user — preferences, relationships, ongoing projects — as database fields, not
prose. Archival: full transcripts, embedded and retrievable, never replayed wholesale.

**Retrieval across episodes.** A daily-use assistant will be asked "what did we decide about X?"
where X was months ago. That's RAG over conversation history, with all of Days 10–13 applying —
including hybrid search, since users reference exact names and dates that embeddings blur.

**Fact management is the hard part**, and it's where these systems actually fail. Contradictions
must replace rather than accumulate. Facts need timestamps and decay — "currently learning
Python" is meaningless two years on. Confidence matters: hedged statements shouldn't be asserted
back as fact. And you want an audit trail, because "why do you think that about me?" is a
question users genuinely ask.

**Privacy is a first-class requirement, not a feature.** Users must be able to see everything
remembered, edit it, delete selectively, and export it. Sensitive categories may need explicit
consent or exclusion. Memory should be encrypted at rest and scoped strictly per user.

**Cost control.** Constant per-turn cost regardless of history age: bounded working memory,
retrieval instead of replay, and cheap models for extraction and summarisation with the strong
model reserved for responses.

**Failure modes to design against:** memory poisoning (a user asserting false facts that then
shape all future answers — hence confidence and provenance); drift from repeated summarisation;
and over-personalisation, where the assistant becomes so anchored on a stale profile that it
answers the profile rather than the question. That last one argues for the model deciding when
memory is relevant, rather than injecting everything into every prompt.
</details>

<details>
<summary><b>Q: Your assistant "remembers" things the user never said. Diagnose it.</b></summary>

False memories are more damaging than forgetting, because the user can't tell where they came
from — so I'd isolate the source before changing anything.

**Where it can originate:**

1. **Extraction hallucination.** The fact-extractor inferred something implied rather than stated
   — the user mentioned a Python error and it recorded "prefers Python". Check by diffing extracted
   facts against the raw messages. Fix with a confidence field, a prompt requiring facts to be
   *directly stated*, and only asserting above a threshold.

2. **Summarisation drift.** Repeated lossy compression can invent connective tissue that reads
   plausibly but wasn't in the transcript. Check by comparing the summary against the original
   messages. Fix with preservation instructions and by keeping hard facts structured.

3. **Contradiction mishandling.** Appending rather than replacing produces facts like
   "JavaScript, Python", from which the assistant infers something the user never said. Check the
   fact history.

4. **Cross-session or cross-user contamination.** Shared mutable state, a caching bug, or a
   session ID collision leaking one user's facts into another's context. This is the most serious
   possibility — it's a privacy incident, not a quality bug — so I'd check session isolation
   early even though it's less likely.

5. **The model confabulating from the prompt.** Even with correct memory, a model may embellish
   ("as you mentioned earlier…" about something never mentioned). Fix by labelling the memory
   block explicitly and instructing that it must not claim the user said anything outside it.

**Structural mitigations:** store provenance with every fact — which message and when — so
"remembered" facts are traceable and can be shown to the user; separate *stated* facts from
*inferred* ones and treat them differently; expose memory in the UI so users can correct it; and
add eval cases where the correct behaviour is learning **nothing**, since over-extraction is
rarely tested for.
</details>

<details>
<summary><b>Q: How do memory and retrieval interact, and where does that go wrong?</b></summary>

They interact in three useful ways and fail in three characteristic ones.

**Useful.** Memory *resolves* queries — "what about the other one?" is unretrievable until
history disambiguates it, which is query rewriting. Memory *enriches* queries — knowing the user
works in Python and fintech makes "how do I handle rate limits?" retrieve far better documents.
And memory *is* a retrieval corpus — past conversations, searched the same way as documents.

**Where it goes wrong.**

*Over-enrichment.* Injecting the user's whole profile into every query narrows retrieval
harmfully — a general question becomes "capital of France for Python fintech developers". The fix
is letting the model decide which facts are relevant and permitting "none", then testing that
case explicitly.

*Confusing the two corpora.* If conversation history and documents are retrieved into the same
context block undifferentiated, the model may cite something the user said as though it were
documentation. Keep them separate and label them.

*Stale memory poisoning retrieval.* A fact from a year ago silently steering every search, long
after it stopped being true. Timestamps and decay.

**The architectural point:** memory should be *available* to retrieval, not *forced into* it. The
strongest design has the model decide per query whether retrieval is needed at all, which memory
facts are relevant, and how to phrase the search — which is one classification call, and it's
exactly the adaptive routing pattern from Day 13 with memory as an extra input.
</details>

---

## 10. Recap

- ✅ LLMs are stateless — "memory" is always a strategy for what to re-send
- ✅ Buffer O(n²) · window and trim forget hard · **summary + buffer is the practical default**
- ✅ `trimMessages` with `startOn: "human"` and `includeSystem` prevents a real class of 400 errors
- ✅ Progressive summarisation **drifts** — keep hard facts structured, not in prose
- ✅ Entity/fact memory must **replace on contradiction**, carry confidence, and be timestamped
- ✅ Vector memory = RAG over conversations — store the whole exchange, not single messages
- ✅ Three layers: recent verbatim (short) · rolling summary (mid) · facts in a DB (long)
- ✅ The `Memory` classes were removed for hidden state, concurrency bugs and no persistence
- ✅ Modern = **you own storage**, `MessagesPlaceholder` injects, `trimMessages` bounds
- ✅ Memory improves **retrieval**, not just tone — but must be able to say "no facts relevant"

### 🎉 Week 2 complete

You can now take a folder of documents and build a system that ingests, chunks, embeds, indexes,
retrieves with hybrid search and reranking, answers with verified citations, refuses honestly,
and remembers the user across sessions.

**StudyBuddy v3** does all of it.

### Next week

**Week 3 — Tools, Agents & LangGraph.** You've hand-written a state machine four times now
(corrective RAG, self-RAG, the production pipeline, the chat loop). Every time, the same
friction: LCEL composes forward but these problems *loop*.

Week 3 starts with tools and a hand-built ReAct agent, then introduces LangGraph — nodes, edges,
typed state with reducers, checkpointers, and interrupts — and everything you hand-rolled becomes
declarative infrastructure.

### Quick self-check

1. Why is unbounded buffer memory O(n²) over a conversation?
2. Your summary has lost the chunk size the user chose 20 turns ago. Why, and what's the fix?
3. Why were the `Memory` classes removed from LangChain?

<details>
<summary>Answers</summary>

1. Each turn re-sends the entire history. Turn *n* sends O(n) tokens, so summing across n turns
   gives O(n²) total. That's why cost per conversation grows quadratically, not linearly.
2. **Progressive summarisation drift** — each fold compresses the previous summary again, so
   specifics erode after several rewrites. Fixes: instruct the summariser to preserve names,
   numbers and decisions; keep critical values in **structured fact memory** where they're fields
   rather than prose; or periodically re-summarise from the original transcript.
3. Three reasons: **hidden state** (memory mutated as a side effect of running a chain, so you
   couldn't see what was in the prompt), **concurrency bugs** (a shared instance interleaved
   different users' conversations), and **no persistence** (restart lost everything). The
   replacement makes storage, injection and bounding three explicit choices, with LangGraph
   checkpointers as the production path.
</details>
