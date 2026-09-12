# Day 15 — Tools: Creating, Calling, Schemas, Errors & Retries

> ⏱ **Time:** ~2.5 hours · 🎯 **Prereqs:** [Day 14](../week-02-data-embeddings-and-rag/day-14-memory.md) · 🧩 **Difficulty:** ●●●○○

**Today you learn:** how to turn any function into something a model can call — `tool()`,
schemas, descriptions that actually work, the execution loop, error handling that lets the model
recover, and the security boundary you must not cross.

You built raw tool calling on Day 02. Today you build it *properly*.

---

## 1. The problem

Your RAG system from Week 2 is excellent at one thing: answering from documents you indexed
yesterday. Ask it anything else and it fails:

```
   "What's 8,342 × 991?"                 → plausible wrong number (Day 01)
   "What's the weather in Lahore?"       → invented, or "I can't browse"
   "How many orders did we get today?"   → not in any document
   "Email this summary to my manager"    → it physically cannot
```

The model can *reason*. It cannot *act*, *compute reliably*, or *see live data*.

**Tools fix all four** — and the mechanism is simple: the model emits a structured request, and
**your code** runs the function.

```
   WITHOUT TOOLS                      WITH TOOLS
   ─────────────                      ──────────
   model recalls / guesses            model requests → you execute → model reads result
   frozen at training time            live data
   arithmetic is pattern-matching     arithmetic is arithmetic
   read-only                          can change the world ⚠️
```

That last row is why half of today is about safety.

---

## 2. Mental model

### What a tool actually is

```
   ┌─────────────────────────────────────────────────────────────┐
   │  A TOOL = three things                                      │
   ├─────────────────────────────────────────────────────────────┤
   │  1. name          "get_weather"        the model picks by this
   │  2. description   "Get current..."     ← THIS IS A PROMPT   │
   │  3. schema        { city: string }     constrains arguments │
   │     + the function itself, which the MODEL NEVER SEES       │
   └─────────────────────────────────────────────────────────────┘
```

**The model never sees your code.** It sees a name, a description and a JSON schema. That's the
whole interface — which is why a vague description produces wrong tool choices.

### The execution loop

```
      user question
           │
           ▼
     ┌───────────┐   tools + schemas serialised into the prompt
     │   MODEL   │
     └───────────┘
           │
      tool_calls? ──── no ──▶ final answer
           │ yes
           ▼
     ┌───────────┐
     │ YOUR CODE │   ← execution happens HERE, never in the model
     │ runs the  │
     │ function  │
     └───────────┘
           │
           ▼
     ToolMessage(result, tool_call_id)
           │
           └──────▶ back to the model  ↺  (bounded!)
```

### The three failure modes to design against

```
   ❌ MODEL PICKS THE WRONG TOOL       → fix the DESCRIPTIONS
   ❌ TOOL THROWS AND KILLS THE LOOP   → return the error TO THE MODEL
   ❌ MODEL CALLS A DESTRUCTIVE TOOL   → authorisation, not prompting
```

---

## 3. First principles

### 3.1 Creating a tool

```js
import { tool } from "@langchain/core/tools";
import * as z from "zod";

const getWeather = tool(
  async ({ city }) => {                       // the implementation
    const r = await fetch(`https://api.example.com/weather?q=${city}`);
    return JSON.stringify(await r.json());
  },
  {
    name: "get_weather",
    description: "Get the CURRENT weather for a city. Use for questions about " +
                 "temperature, rain or conditions right now. Not for forecasts.",
    schema: z.object({
      city: z.string().describe("City name, e.g. 'Lahore' or 'London, UK'"),
    }),
  }
);
```

```python
from langchain_core.tools import tool

@tool
def get_weather(city: str) -> str:
    """Get the CURRENT weather for a city.

    Use for questions about temperature, rain or conditions right now.
    Not for forecasts.

    Args:
        city: City name, e.g. 'Lahore' or 'London, UK'
    """
    return fetch_weather(city)
```

> 🔑 **In Python the docstring IS the description.** The `@tool` decorator reads it, along with
> the type hints, to build the schema. A tool without a docstring gives the model nothing to go
> on — this is the single most common Python tool mistake.

### 3.2 Descriptions are prompts, not documentation

This is the highest-leverage idea today.

```js
// ❌ the model has no idea when to use this
description: "Search"

// 🟡 better
description: "Search the web"

// ✅ tells the model WHEN, and when NOT
description: "Search the web for current events, news, or facts that change over time. " +
             "Use when the answer depends on information after your training cutoff. " +
             "Do NOT use for maths, or for questions about the user's own documents."
```

**A good description answers three questions:** what it does, when to use it, and when *not* to.
That third one is what stops the model reaching for a web search to add two numbers.

### 3.3 Argument schemas

Everything from Day 06 applies — the schema *is* the constraint:

```js
schema: z.object({
  query: z.string().describe("The search query"),
  maxResults: z.number().int().min(1).max(10).default(5)
    .describe("How many results, 1-10"),
  category: z.enum(["news", "academic", "general"]).default("general"),
  since: z.string().nullable().describe("ISO date, or null for no limit"),
})
```

- **Enums** over free strings — the wrong value becomes unrepresentable
- **Defaults** so the model can omit optional arguments
- **Nullable** so "not applicable" is expressible instead of invented
- **Describe every field** — it's prompt text

### 3.4 Binding tools to a model

```js
const modelWithTools = model.bindTools([getWeather, calculator]);
const res = await modelWithTools.invoke("What's the weather in Lahore?");

res.tool_calls;
// [{ name: "get_weather", args: { city: "Lahore" }, id: "call_abc123", type: "tool_call" }]
```

The model **requests**; nothing has executed yet.

### 3.5 The execution loop, done right

```js
const messages = [new HumanMessage(question)];

for (let step = 0; step < MAX_STEPS; step++) {      // ⚠️ ALWAYS bounded
  const ai = await modelWithTools.invoke(messages);
  messages.push(ai);                                 // ⚠️ push verbatim

  if (!ai.tool_calls?.length) return ai.text;        // done

  for (const call of ai.tool_calls) {
    const tool = TOOLS_BY_NAME[call.name];

    let content;
    try {
      content = tool
        ? String(await tool.invoke(call.args))
        : `Error: unknown tool "${call.name}"`;
    } catch (err) {
      content = `Error: ${err.message}`;             // ⚠️ feed errors BACK
    }

    messages.push(new ToolMessage({ content, tool_call_id: call.id }));
  }
}
```

Three rules, each one a bug you'd otherwise ship:

1. **Bound the loop.** A confused model calls tools forever, and that's an unbounded bill.
2. **Push the assistant message verbatim** before the tool results, or the provider rejects it
   with a 400 (Day 02).
3. **Return errors to the model as content**, don't throw. The model can then correct itself —
   `"Error: city not found"` often produces a retry with a better argument.

### 3.6 `ToolNode` — the prebuilt executor

LangGraph ships the loop body:

```js
import { ToolNode } from "@langchain/langgraph/prebuilt";
const toolNode = new ToolNode([getWeather, calculator]);
```

It takes state containing messages, executes every `tool_call` on the last AI message **in
parallel**, and returns `ToolMessage`s. It handles errors, unknown tools and ID matching.

You'll wire this into a graph on Day 17.

### 3.7 Error handling that helps the model

```
   error type              what to return to the model
   ──────────              ──────────────────────────
   bad argument            "Error: 'city' must be a city name, got '12345'"
   not found               "No results for 'xyz'. Try a broader search term."
   transient (429/500)     retry internally FIRST; only surface after retries
   permanent (401)         don't surface — this is your config bug, fail loudly
   too much data           truncate + "showing first 10 of 4,382 results"
```

**Actionable error messages are prompt engineering.** `"Error: ValidationError"` tells the model
nothing; `"Error: date must be YYYY-MM-DD, got '14 March'"` gets a correct retry.

### 3.8 The security boundary

Day 02 established that prompt injection is not solvable at the prompt layer. Tools are where
that stops being theoretical:

```
   ⚠️ Every tool is an ACTION the model can take on your behalf,
      driven by text that may include untrusted user input.

   READ-ONLY tools        search, lookup, calculate     → low risk
   WRITE tools            send email, create ticket     → needs approval
   DESTRUCTIVE tools      delete, refund, deploy        → needs approval + audit
```

**The rules:**

1. **Least privilege** — the DB tool gets a read-only connection scoped to the tenant.
2. **Validate inside the tool**, never trust the arguments. The model can emit anything.
3. **Allow-lists over free text** — an email tool validates recipients against a list; the model
   cannot invent an address.
4. **Human approval for anything irreversible** — that's Day 21's `interrupt`.
5. **Log every call with arguments** — you need the audit trail when something goes wrong.

```js
// ❌ catastrophic
const runSql = tool(async ({ sql }) => db.execute(sql), { ... });

// ✅ parameterised, allow-listed, read-only
const QUERIES = {
  orders_by_day: "SELECT date, COUNT(*) FROM orders WHERE tenant=$1 AND date>=$2 GROUP BY date",
};
const runQuery = tool(
  async ({ queryName, since }) => {
    const sql = QUERIES[queryName];
    if (!sql) throw new Error(`Unknown query. Available: ${Object.keys(QUERIES).join(", ")}`);
    return JSON.stringify(await readOnlyDb.query(sql, [currentTenantId, since]));
  },
  { name: "run_query", schema: z.object({
      queryName: z.enum(Object.keys(QUERIES)), since: z.string() }) }
);
```

### 3.9 How many tools?

Every tool's schema is in the prompt on **every** call.

| Tools | Overhead | Model accuracy |
|---|---|---|
| 1–5 | small | excellent |
| 5–15 | ~1–3k tokens | good |
| 15–30 | noticeable | degrading — similar tools get confused |
| 30+ | expensive | poor without routing |

**Above ~15, route.** Classify the request first, then bind only the relevant subset — the same
Day 08 routing idea applied to tools.

---

## 4. Code — JavaScript

```bash
npm install langchain @langchain/core @langchain/langgraph @langchain/groq zod dotenv
```

### 4.1 Your first tools

```js
// day15-tools.js
import "dotenv/config";
import * as z from "zod";
import { tool } from "@langchain/core/tools";

// ── a pure computation ───────────────────────────────────────────────────
const calculator = tool(
  async ({ expression }) => {
    if (!/^[\d\s+\-*/().%]+$/.test(expression)) {
      return "Error: only numbers and + - * / ( ) % are allowed.";
    }
    try {
      // eval is acceptable ONLY because of the character guard above
      const result = eval(expression);
      return `${expression} = ${result}`;
    } catch {
      return `Error: '${expression}' is not a valid arithmetic expression.`;
    }
  },
  {
    name: "calculator",
    description:
      "Evaluate an arithmetic expression. ALWAYS use this for any calculation, " +
      "however simple — never compute in your head. Supports + - * / ( ) and %.",
    schema: z.object({
      expression: z.string().describe("An arithmetic expression, e.g. '(24 * 9/5) + 32'"),
    }),
  }
);

// ── a fake API ───────────────────────────────────────────────────────────
const WEATHER = {
  lahore: { tempC: 34, condition: "hazy sunshine", humidity: 45 },
  london: { tempC: 12, condition: "light rain", humidity: 82 },
  tokyo:  { tempC: 19, condition: "clear", humidity: 60 },
};

const getWeather = tool(
  async ({ city }) => {
    const data = WEATHER[city.toLowerCase().trim()];
    if (!data) {
      // ⭐ actionable error — tells the model how to succeed next time
      return `No weather data for "${city}". Available cities: ${Object.keys(WEATHER).join(", ")}.`;
    }
    return JSON.stringify({ city, ...data });
  },
  {
    name: "get_weather",
    description:
      "Get the CURRENT weather for a city. Use for questions about temperature, " +
      "rain or conditions right now. Do NOT use for forecasts or historical weather.",
    schema: z.object({
      city: z.string().describe("City name, e.g. 'Lahore'"),
    }),
  }
);

// ── inspect what the model will actually see ─────────────────────────────
console.log("name:       ", calculator.name);
console.log("description:", calculator.description);
console.log("schema:     ", JSON.stringify(z.toJSONSchema(calculator.schema), null, 2));

// ── tools are Runnables ──────────────────────────────────────────────────
console.log("\ndirect invoke:", await calculator.invoke({ expression: "(24 * 9/5) + 32" }));
console.log("bad city:     ", await getWeather.invoke({ city: "Atlantis" }));

export { calculator, getWeather };
```

### 4.2 Binding and inspecting tool calls

```js
// day15-binding.js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";
import { calculator, getWeather } from "./day15-tools.js";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });
const modelWithTools = model.bindTools([calculator, getWeather]);

for (const q of [
  "What's 8342 * 991?",
  "What's the weather in Lahore?",
  "What's the weather in Lahore in Fahrenheit?",   // needs BOTH tools
  "Who wrote Hamlet?",                              // needs NEITHER
]) {
  const res = await modelWithTools.invoke(q);

  console.log(`\n❓ ${q}`);
  if (res.tool_calls?.length) {
    for (const c of res.tool_calls) {
      console.log(`   🔧 ${c.name}(${JSON.stringify(c.args)})`);
    }
  } else {
    console.log(`   💬 ${res.text.slice(0, 70)}   (no tools needed)`);
  }
}
```

Notice the Fahrenheit question: a good model requests `get_weather` first, because it can't
convert a temperature it doesn't have yet. Tool calls can be **sequential by necessity**.

### 4.3 The full execution loop

```js
// day15-loop.js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";
import { HumanMessage, ToolMessage, SystemMessage } from "@langchain/core/messages";
import { calculator, getWeather } from "./day15-tools.js";

const TOOLS = [calculator, getWeather];
const BY_NAME = Object.fromEntries(TOOLS.map((t) => [t.name, t]));

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 })
  .bindTools(TOOLS);

async function run(question, maxSteps = 6) {
  const messages = [
    new SystemMessage("You are a helpful assistant. Use tools for anything factual or numeric."),
    new HumanMessage(question),
  ];

  const trace = [];

  for (let step = 1; step <= maxSteps; step++) {          // ⚠️ bounded
    const ai = await model.invoke(messages);
    messages.push(ai);                                    // ⚠️ verbatim, before tool results

    if (!ai.tool_calls?.length) {
      return { answer: ai.text, steps: step, trace };
    }

    // Execute every requested call — in PARALLEL where possible
    const results = await Promise.all(
      ai.tool_calls.map(async (call) => {
        const t = BY_NAME[call.name];
        let content;

        try {
          content = t
            ? String(await t.invoke(call.args))
            : `Error: unknown tool "${call.name}". Available: ${Object.keys(BY_NAME).join(", ")}`;
        } catch (err) {
          content = `Error: ${err.message}`;              // ⚠️ back to the model, not thrown
        }

        trace.push({ step, tool: call.name, args: call.args, result: content.slice(0, 60) });
        return new ToolMessage({ content, tool_call_id: call.id });
      })
    );

    messages.push(...results);
  }

  return { answer: "⚠️ Hit the step limit without finishing.", steps: maxSteps, trace };
}

for (const q of [
  "What's the weather in Lahore, and what is that in Fahrenheit?",
  "What's the weather in Atlantis?",              // triggers the actionable error
  "What is 15% of 8342, plus 991?",
]) {
  console.log(`\n${"═".repeat(72)}\n❓ ${q}\n${"═".repeat(72)}`);
  const r = await run(q);
  r.trace.forEach((t) =>
    console.log(`  [${t.step}] 🔧 ${t.tool}(${JSON.stringify(t.args)}) → ${t.result}`));
  console.log(`\n  💬 ${r.answer}\n  (${r.steps} model calls)`);
}
```

Watch the Atlantis case: the tool returns a helpful error, the model reads it and **tells the
user which cities are available** rather than crashing or inventing weather.

### 4.4 `ToolNode` — the prebuilt executor

```js
// day15-toolnode.js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";
import { ToolNode } from "@langchain/langgraph/prebuilt";
import { HumanMessage } from "@langchain/core/messages";
import { calculator, getWeather } from "./day15-tools.js";

const toolNode = new ToolNode([calculator, getWeather]);

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 })
  .bindTools([calculator, getWeather]);

const ai = await model.invoke([new HumanMessage("Weather in Lahore and London?")]);
console.log("requested:", ai.tool_calls.map((c) => `${c.name}(${JSON.stringify(c.args)})`));

// ToolNode takes state with messages, runs every call, returns ToolMessages
const result = await toolNode.invoke({ messages: [ai] });

for (const m of result.messages) {
  console.log(`   ← ${m.name}: ${String(m.content).slice(0, 60)}`);
}
```

That's the loop body from §4.3, minus the code you wrote. Day 17 wires it into a graph.

### 4.5 Six real tools

```js
// day15-toolkit.js
import "dotenv/config";
import fs from "node:fs/promises";
import path from "node:path";
import * as z from "zod";
import { tool } from "@langchain/core/tools";

// ── 1. calculator (see §4.1) ─────────────────────────────────────────────

// ── 2. web search (Tavily — free tier) ───────────────────────────────────
const webSearch = tool(
  async ({ query, maxResults }) => {
    if (!process.env.TAVILY_API_KEY) {
      return "Error: web search is not configured. Tell the user this capability is unavailable.";
    }
    const r = await fetch("https://api.tavily.com/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        api_key: process.env.TAVILY_API_KEY, query, max_results: maxResults,
      }),
    });
    if (!r.ok) return `Error: search failed with status ${r.status}.`;
    const data = await r.json();
    return data.results
      .map((x, i) => `[${i + 1}] ${x.title}\n${x.content.slice(0, 200)}\n${x.url}`)
      .join("\n\n");
  },
  {
    name: "web_search",
    description:
      "Search the web for current events, news, or facts that change over time. " +
      "Use when the answer depends on information after your training cutoff. " +
      "Do NOT use for arithmetic or for the user's own documents.",
    schema: z.object({
      query: z.string().describe("Search query. Be specific."),
      maxResults: z.number().int().min(1).max(5).default(3),
    }),
  }
);

// ── 3. filesystem read — SANDBOXED ───────────────────────────────────────
const SANDBOX = path.resolve("./workspace");

const readFile = tool(
  async ({ filename }) => {
    // ⚠️ THE critical check: resolve, then verify it's still inside the sandbox
    const full = path.resolve(SANDBOX, filename);
    if (!full.startsWith(SANDBOX + path.sep)) {
      return "Error: access denied — path escapes the workspace directory.";
    }
    try {
      const text = await fs.readFile(full, "utf8");
      return text.length > 4000
        ? text.slice(0, 4000) + `\n…[truncated, ${text.length} chars total]`
        : text;
    } catch (e) {
      if (e.code === "ENOENT") {
        const files = await fs.readdir(SANDBOX).catch(() => []);
        return `File not found. Available: ${files.join(", ") || "(empty)"}`;
      }
      return `Error reading file: ${e.message}`;
    }
  },
  {
    name: "read_file",
    description: "Read a text file from the workspace directory. Use to inspect files " +
                 "the user mentions. Only files inside the workspace are accessible.",
    schema: z.object({
      filename: z.string().describe("Filename relative to the workspace, e.g. 'notes.md'"),
    }),
  }
);

// ── 4. database — ALLOW-LISTED queries only ──────────────────────────────
const FAKE_DB = {
  orders: [
    { id: 1, customer: "acme", total: 240, date: "2024-06-01", status: "shipped" },
    { id: 2, customer: "globex", total: 890, date: "2024-06-01", status: "pending" },
    { id: 3, customer: "acme", total: 120, date: "2024-06-02", status: "shipped" },
  ],
};

const QUERIES = {
  orders_by_customer: (p) => FAKE_DB.orders.filter((o) => o.customer === p.customer),
  orders_by_status:   (p) => FAKE_DB.orders.filter((o) => o.status === p.status),
  revenue_total:      () => [{ total: FAKE_DB.orders.reduce((s, o) => s + o.total, 0) }],
};

const queryDatabase = tool(
  async ({ queryName, customer, status }) => {
    const fn = QUERIES[queryName];
    if (!fn) return `Error: unknown query. Available: ${Object.keys(QUERIES).join(", ")}`;
    const rows = fn({ customer, status });
    return rows.length ? JSON.stringify(rows) : "No matching rows.";
  },
  {
    name: "query_database",
    description: "Run a pre-approved read-only query against the orders database. " +
                 "Use for questions about orders, customers or revenue.",
    schema: z.object({
      queryName: z.enum(["orders_by_customer", "orders_by_status", "revenue_total"]),
      customer: z.string().nullable().describe("Required for orders_by_customer"),
      status: z.enum(["shipped", "pending", "cancelled"]).nullable()
        .describe("Required for orders_by_status"),
    }),
  }
);

// ── 5. GitHub (read-only, public API) ────────────────────────────────────
const githubRepo = tool(
  async ({ owner, repo }) => {
    const r = await fetch(`https://api.github.com/repos/${owner}/${repo}`);
    if (r.status === 404) return `Repository ${owner}/${repo} not found.`;
    if (!r.ok) return `Error: GitHub returned ${r.status}.`;
    const d = await r.json();
    return JSON.stringify({
      name: d.full_name, stars: d.stargazers_count, language: d.language,
      description: d.description, openIssues: d.open_issues_count,
    });
  },
  {
    name: "github_repo",
    description: "Look up public information about a GitHub repository: stars, language, " +
                 "description, open issue count.",
    schema: z.object({
      owner: z.string().describe("Repository owner, e.g. 'langchain-ai'"),
      repo: z.string().describe("Repository name, e.g. 'langchainjs'"),
    }),
  }
);

// ── 6. a WRITE tool — requires approval (Day 21) ─────────────────────────
const sendEmail = tool(
  async ({ to, subject, body }) => {
    const ALLOWED = ["manager@acme.com", "team@acme.com"];
    if (!ALLOWED.includes(to)) {
      return `Error: '${to}' is not an approved recipient. Allowed: ${ALLOWED.join(", ")}`;
    }
    console.log(`\n      📧 [would send] to=${to} subject="${subject}"\n`);
    return `Email queued to ${to}.`;
  },
  {
    name: "send_email",
    description: "Send an email. ONLY use when the user explicitly asks to send one. " +
                 "Recipients are restricted to an approved list.",
    schema: z.object({
      to: z.string().describe("Recipient — must be on the approved list"),
      subject: z.string(),
      body: z.string(),
    }),
  }
);

export const TOOLKIT = [webSearch, readFile, queryDatabase, githubRepo, sendEmail];
```

---

## 5. Code — Python

```bash
pip install langchain langgraph langchain-groq pydantic python-dotenv
```

### 5.1 Your first tools

```python
# day15_tools.py
import json, re
from dotenv import load_dotenv
from langchain_core.tools import tool

load_dotenv()

@tool
def calculator(expression: str) -> str:
    """Evaluate an arithmetic expression.

    ALWAYS use this for any calculation, however simple — never compute in your head.
    Supports + - * / ( ) and %.

    Args:
        expression: An arithmetic expression, e.g. '(24 * 9/5) + 32'
    """
    if not re.fullmatch(r"[\d\s+\-*/().%]+", expression):
        return "Error: only numbers and + - * / ( ) % are allowed."
    try:
        # eval is acceptable ONLY because of the character guard above
        return f"{expression} = {eval(expression)}"
    except Exception:
        return f"Error: '{expression}' is not a valid arithmetic expression."

WEATHER = {
    "lahore": {"tempC": 34, "condition": "hazy sunshine", "humidity": 45},
    "london": {"tempC": 12, "condition": "light rain", "humidity": 82},
    "tokyo":  {"tempC": 19, "condition": "clear", "humidity": 60},
}

@tool
def get_weather(city: str) -> str:
    """Get the CURRENT weather for a city.

    Use for questions about temperature, rain or conditions right now.
    Do NOT use for forecasts or historical weather.

    Args:
        city: City name, e.g. 'Lahore'
    """
    data = WEATHER.get(city.lower().strip())
    if not data:
        # ⭐ actionable error — tells the model how to succeed next time
        return f'No weather data for "{city}". Available cities: {", ".join(WEATHER)}.'
    return json.dumps({"city": city, **data})

if __name__ == "__main__":
    # ── inspect what the model will actually see ─────────────────────────
    print("name:       ", calculator.name)
    print("description:", calculator.description)
    print("args:       ", json.dumps(calculator.args, indent=2))

    # ── tools are Runnables ──────────────────────────────────────────────
    print("\ndirect invoke:", calculator.invoke({"expression": "(24 * 9/5) + 32"}))
    print("bad city:     ", get_weather.invoke({"city": "Atlantis"}))
```

> 🔑 **The docstring becomes the description.** Notice `calculator.description` prints the whole
> docstring including the "ALWAYS use this" instruction. A tool with no docstring gives the model
> nothing — always write one.

### 5.2 Binding and inspecting tool calls

```python
# day15_binding.py
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from day15_tools import calculator, get_weather

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
model_with_tools = model.bind_tools([calculator, get_weather])

for q in [
    "What's 8342 * 991?",
    "What's the weather in Lahore?",
    "What's the weather in Lahore in Fahrenheit?",   # needs BOTH tools
    "Who wrote Hamlet?",                              # needs NEITHER
]:
    res = model_with_tools.invoke(q)

    print(f"\n❓ {q}")
    if res.tool_calls:
        for c in res.tool_calls:
            print(f"   🔧 {c['name']}({c['args']})")
    else:
        print(f"   💬 {res.content[:70]}   (no tools needed)")
```

### 5.3 The full execution loop

```python
# day15_loop.py
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from day15_tools import calculator, get_weather

load_dotenv()

TOOLS = [calculator, get_weather]
BY_NAME = {t.name: t for t in TOOLS}

model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0).bind_tools(TOOLS)

def run(question, max_steps=6):
    messages = [
        SystemMessage("You are a helpful assistant. Use tools for anything factual or numeric."),
        HumanMessage(question),
    ]
    trace = []

    for step in range(1, max_steps + 1):                  # ⚠️ bounded
        ai = model.invoke(messages)
        messages.append(ai)                                # ⚠️ verbatim, before tool results

        if not ai.tool_calls:
            return {"answer": ai.content, "steps": step, "trace": trace}

        for call in ai.tool_calls:
            t = BY_NAME.get(call["name"])
            try:
                content = (str(t.invoke(call["args"])) if t
                           else f'Error: unknown tool "{call["name"]}". '
                                f'Available: {", ".join(BY_NAME)}')
            except Exception as err:
                content = f"Error: {err}"                  # ⚠️ back to the model, not raised

            trace.append({"step": step, "tool": call["name"],
                          "args": call["args"], "result": content[:60]})
            messages.append(ToolMessage(content=content, tool_call_id=call["id"]))

    return {"answer": "⚠️ Hit the step limit without finishing.",
            "steps": max_steps, "trace": trace}

for q in [
    "What's the weather in Lahore, and what is that in Fahrenheit?",
    "What's the weather in Atlantis?",              # triggers the actionable error
    "What is 15% of 8342, plus 991?",
]:
    print(f"\n{'═' * 72}\n❓ {q}\n{'═' * 72}")
    r = run(q)
    for t in r["trace"]:
        print(f"  [{t['step']}] 🔧 {t['tool']}({t['args']}) → {t['result']}")
    print(f"\n  💬 {r['answer']}\n  ({r['steps']} model calls)")
```

### 5.4 `ToolNode` — the prebuilt executor

```python
# day15_toolnode.py
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage
from day15_tools import calculator, get_weather

load_dotenv()

tool_node = ToolNode([calculator, get_weather])
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0) \
    .bind_tools([calculator, get_weather])

ai = model.invoke([HumanMessage("Weather in Lahore and London?")])
print("requested:", [f"{c['name']}({c['args']})" for c in ai.tool_calls])

# ToolNode takes state with messages, runs every call, returns ToolMessages
result = tool_node.invoke({"messages": [ai]})

for m in result["messages"]:
    print(f"   ← {m.name}: {str(m.content)[:60]}")
```

### 5.5 Six real tools

```python
# day15_toolkit.py
import json, os
from pathlib import Path
from typing import Literal, Optional
import requests
from dotenv import load_dotenv
from langchain_core.tools import tool
from pydantic import BaseModel, Field

load_dotenv()

# ── 2. web search (Tavily — free tier) ───────────────────────────────────
@tool
def web_search(query: str, max_results: int = 3) -> str:
    """Search the web for current events, news, or facts that change over time.

    Use when the answer depends on information after your training cutoff.
    Do NOT use for arithmetic or for the user's own documents.

    Args:
        query: Search query. Be specific.
        max_results: How many results, 1-5.
    """
    if not os.getenv("TAVILY_API_KEY"):
        return "Error: web search is not configured. Tell the user this is unavailable."

    r = requests.post("https://api.tavily.com/search", json={
        "api_key": os.environ["TAVILY_API_KEY"],
        "query": query, "max_results": min(max_results, 5),
    }, timeout=15)

    if not r.ok:
        return f"Error: search failed with status {r.status_code}."

    return "\n\n".join(
        f"[{i}] {x['title']}\n{x['content'][:200]}\n{x['url']}"
        for i, x in enumerate(r.json()["results"], 1)
    )

# ── 3. filesystem read — SANDBOXED ───────────────────────────────────────
SANDBOX = Path("./workspace").resolve()

@tool
def read_file(filename: str) -> str:
    """Read a text file from the workspace directory.

    Use to inspect files the user mentions. Only files inside the workspace
    are accessible.

    Args:
        filename: Filename relative to the workspace, e.g. 'notes.md'
    """
    # ⚠️ THE critical check: resolve, then verify it's still inside the sandbox
    full = (SANDBOX / filename).resolve()
    if not str(full).startswith(str(SANDBOX) + os.sep):
        return "Error: access denied — path escapes the workspace directory."

    try:
        text = full.read_text(encoding="utf8")
        return (text[:4000] + f"\n…[truncated, {len(text)} chars total]"
                if len(text) > 4000 else text)
    except FileNotFoundError:
        available = [p.name for p in SANDBOX.iterdir()] if SANDBOX.exists() else []
        return f"File not found. Available: {', '.join(available) or '(empty)'}"
    except Exception as e:
        return f"Error reading file: {e}"

# ── 4. database — ALLOW-LISTED queries only ──────────────────────────────
FAKE_DB = {
    "orders": [
        {"id": 1, "customer": "acme", "total": 240, "date": "2024-06-01", "status": "shipped"},
        {"id": 2, "customer": "globex", "total": 890, "date": "2024-06-01", "status": "pending"},
        {"id": 3, "customer": "acme", "total": 120, "date": "2024-06-02", "status": "shipped"},
    ]
}

@tool
def query_database(
    query_name: Literal["orders_by_customer", "orders_by_status", "revenue_total"],
    customer: Optional[str] = None,
    status: Optional[Literal["shipped", "pending", "cancelled"]] = None,
) -> str:
    """Run a pre-approved read-only query against the orders database.

    Use for questions about orders, customers or revenue.

    Args:
        query_name: Which approved query to run.
        customer: Required for orders_by_customer.
        status: Required for orders_by_status.
    """
    orders = FAKE_DB["orders"]

    if query_name == "orders_by_customer":
        rows = [o for o in orders if o["customer"] == customer]
    elif query_name == "orders_by_status":
        rows = [o for o in orders if o["status"] == status]
    else:
        rows = [{"total": sum(o["total"] for o in orders)}]

    return json.dumps(rows) if rows else "No matching rows."

# ── 5. GitHub (read-only, public API) ────────────────────────────────────
@tool
def github_repo(owner: str, repo: str) -> str:
    """Look up public information about a GitHub repository.

    Returns stars, language, description and open issue count.

    Args:
        owner: Repository owner, e.g. 'langchain-ai'
        repo: Repository name, e.g. 'langchain'
    """
    r = requests.get(f"https://api.github.com/repos/{owner}/{repo}", timeout=15)
    if r.status_code == 404:
        return f"Repository {owner}/{repo} not found."
    if not r.ok:
        return f"Error: GitHub returned {r.status_code}."

    d = r.json()
    return json.dumps({
        "name": d["full_name"], "stars": d["stargazers_count"],
        "language": d["language"], "description": d["description"],
        "openIssues": d["open_issues_count"],
    })

# ── 6. a WRITE tool — requires approval (Day 21) ─────────────────────────
@tool
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email.

    ONLY use when the user explicitly asks to send one.
    Recipients are restricted to an approved list.

    Args:
        to: Recipient — must be on the approved list.
        subject: Email subject line.
        body: Email body.
    """
    ALLOWED = ["manager@acme.com", "team@acme.com"]
    if to not in ALLOWED:
        return f"Error: '{to}' is not an approved recipient. Allowed: {', '.join(ALLOWED)}"

    print(f'\n      📧 [would send] to={to} subject="{subject}"\n')
    return f"Email queued to {to}."

TOOLKIT = [web_search, read_file, query_database, github_repo, send_email]
```

### 🔁 JS ↔ Python differences you just saw

| | JavaScript | Python |
|---|---|---|
| Create | `tool(fn, { name, description, schema })` | `@tool` decorator |
| **Description** | the `description` option | **the docstring** ⚠️ |
| Schema | Zod object | type hints + docstring `Args:` |
| Import | `@langchain/core/tools` (also re-exported from `langchain`) | `langchain_core.tools` (also `langchain.tools`) |
| Bind | `model.bindTools([...])` | `model.bind_tools([...])` |
| Read calls | `res.tool_calls[0].name` / `.args` | `res.tool_calls[0]["name"]` / `["args"]` ⚠️ dicts |
| ToolMessage | `new ToolMessage({ content, tool_call_id })` | `ToolMessage(content=..., tool_call_id=...)` |
| ToolNode | `new ToolNode([...])` from `@langchain/langgraph/prebuilt` | `ToolNode([...])` from `langgraph.prebuilt` |
| Inspect schema | `z.toJSONSchema(tool.schema)` | `tool.args` |
| Parallel exec | `Promise.all(calls.map(...))` | loop, or `asyncio.gather` with `ainvoke` |

> ⚠️ **`tool_calls` entries are dicts in Python, objects in JS.** `call["name"]` vs `call.name`.
> This is the single most common porting error in agent code.

---

## 6. Under the hood

### What the model actually receives

```
Your tools are serialised into the request as JSON Schema:

{
  "tools": [{
    "type": "function",
    "function": {
      "name": "get_weather",
      "description": "Get the CURRENT weather for a city. Use for questions about
                      temperature, rain or conditions right now. Do NOT use for forecasts.",
      "parameters": {
        "type": "object",
        "properties": {
          "city": { "type": "string", "description": "City name, e.g. 'Lahore'" }
        },
        "required": ["city"]
      }
    }
  }]
}
```

**Every word of that is prompt text**, and it's sent on *every* call. Which explains:

- Vague descriptions → wrong tool selection
- 30 tools → thousands of tokens of overhead per turn, plus confusion between similar tools
- Field descriptions materially affect argument quality
- Your function body is completely invisible to the model

### Why tool calls can be parallel *or* sequential

```
   PARALLEL — independent
   "Weather in Lahore and London?"
   → tool_calls: [get_weather(Lahore), get_weather(London)]     one round trip

   SEQUENTIAL — the second needs the first's result
   "Weather in Lahore in Fahrenheit?"
   → tool_calls: [get_weather(Lahore)]                          round trip 1
   ← 34°C
   → tool_calls: [calculator("(34 * 9/5) + 32")]                round trip 2
   ← 93.2
   → final answer                                                round trip 3
```

The model decides. Execute all calls in one AI message **in parallel** (as §4.3 does) — they're
independent by construction, since the model emitted them together.

This is why `maxSteps` counts **model round trips**, not tool executions.

### Why errors must go back as content

```js
// ❌ throws → the loop dies, the user gets a 500
const result = await tool.invoke(call.args);

// ✅ the model sees the problem and can recover
try { content = await tool.invoke(call.args); }
catch (e) { content = `Error: ${e.message}`; }
```

With the second version, this happens:

```
🔧 get_weather({city: "Atlantis"})
←  No weather data for "Atlantis". Available: lahore, london, tokyo.
💬 "I don't have weather data for Atlantis. I can check Lahore, London or Tokyo."
```

The model **recovered**. That's only possible because the error was information, not an exception.

> 💡 LangChain has `ToolException` (Python) and `handleToolError` options for exactly this
> pattern — but returning an error string from the function is simpler and works everywhere.

### Where tools sit in the security model

```
   ┌──────────────────────────────────────────────────────────┐
   │  UNTRUSTED: the user's message, retrieved documents,     │
   │             web content, previous tool outputs           │
   │                          │                               │
   │                          ▼                               │
   │  the model produces tool_calls — ALSO UNTRUSTED          │
   │                          │                               │
   │  ══════════ THE SECURITY BOUNDARY ══════════             │
   │                          │                               │
   │  YOUR CODE: validate, authorise, scope, log              │
   │                          ▼                               │
   │  TRUSTED: the actual action                              │
   └──────────────────────────────────────────────────────────┘
```

Treat `tool_calls` exactly as you'd treat a form submission from the public internet — because
via prompt injection, that's effectively what it is.

**The path-traversal check in §4.5 is the concrete example.** Without
`full.startsWith(SANDBOX)`, a model that read a poisoned document could be induced to call
`read_file("../../.env")`.

<details>
<summary>📜 Legacy note: older tool APIs</summary>

| Legacy | Modern |
|---|---|
| `new DynamicTool({ name, description, func })` | `tool(fn, { name, description, schema })` |
| `new DynamicStructuredTool({ ... })` | same — `tool()` handles structured args |
| `Tool` subclassing | `tool()` factory, or `StructuredTool` for complex cases |
| `functions` / `function_call` params | `tools` / `tool_calls` |
| `initialize_agent(tools, llm, agent=...)` | `create_agent` / `createAgent`, or a graph |

The old `Tool` class took a single string argument, so multi-argument tools required parsing the
string yourself. `StructuredTool` fixed that, and `tool()` is now the one factory for both cases.
</details>

---

## 7. Common mistakes

**❌ Vague descriptions**

```js
description: "Search"     // the model has no idea when to use this
```
✅ Say what it does, when to use it, and when *not* to.

---

**❌ Python: no docstring**

```python
@tool
def get_weather(city: str) -> str:
    return fetch(city)          # description is empty — model is blind
```
✅ The docstring *is* the description. Always write one, with an `Args:` section.

---

**❌ Throwing instead of returning the error**

Kills the loop and denies the model any chance to recover.
✅ `catch` and return an actionable message.

---

**❌ Unbounded loops**

A model that misreads a result can call the same tool forever.
✅ `maxSteps` on every loop, always.

---

**❌ Forgetting to push the assistant message before tool results**

→ `400: messages with role 'tool' must be a response to a preceding message with 'tool_calls'`
✅ Push the AI message verbatim, then the `ToolMessage`s.

---

**❌ Raw SQL or shell as a tool argument**

```js
tool(async ({ sql }) => db.execute(sql))     // catastrophic
```
✅ Allow-listed, parameterised queries against a read-only, tenant-scoped connection.

---

**❌ Path traversal in a filesystem tool**

`read_file("../../.env")` is one poisoned document away.
✅ Resolve the path, then verify it's still inside the sandbox.

---

**❌ Returning enormous output**

A tool returning 50,000 characters blows the context window in one step.
✅ Truncate, and say so: `"…showing first 10 of 4,382 results"`.

---

**❌ 30 tools bound at once**

Thousands of tokens per call and the model confuses similar tools.
✅ Route first, bind the relevant subset.

---

**❌ Treating tool arguments as trusted**

They're model output, influenced by untrusted text.
✅ Validate inside the tool, every time.

---

## 8. Exercises

### Exercise 1 — Description A/B test ●●○○○

Create three versions of a `web_search` tool with descriptions of increasing specificity (bare,
descriptive, with explicit "do NOT use for…"). Bind each alongside a calculator, then ask five
questions — some needing search, some needing maths, some needing neither. Count how often the
model picks correctly.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import "dotenv/config";
import * as z from "zod";
import { tool } from "@langchain/core/tools";
import { ChatGroq } from "@langchain/groq";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });

const calculator = tool(async ({ expression }) => `${expression} = ...`, {
  name: "calculator",
  description: "Evaluate an arithmetic expression. ALWAYS use for any calculation.",
  schema: z.object({ expression: z.string() }),
});

const makeSearch = (description) =>
  tool(async ({ query }) => `results for ${query}`, {
    name: "web_search", description, schema: z.object({ query: z.string() }),
  });

const VERSIONS = {
  bare: makeSearch("Search"),
  descriptive: makeSearch("Search the web for information"),
  explicit: makeSearch(
    "Search the web for current events, news, prices, or facts that change over time. " +
    "Use when the answer depends on information after your training cutoff. " +
    "Do NOT use for arithmetic, and do NOT use for well-known historical facts."
  ),
};

// question → the tool that SHOULD be chosen (null = none)
const CASES = [
  ["What is the current price of Bitcoin?", "web_search"],
  ["What is 8342 * 991?",                   "calculator"],
  ["Who wrote Hamlet?",                      null],
  ["What is 15% of 200?",                    "calculator"],
  ["What happened in the news today?",       "web_search"],
  ["What is the capital of France?",         null],
];

console.log("version      correct  choices");
console.log("-".repeat(70));

for (const [name, search] of Object.entries(VERSIONS)) {
  const withTools = model.bindTools([calculator, search]);
  let correct = 0;
  const choices = [];

  for (const [q, expected] of CASES) {
    const res = await withTools.invoke(q);
    const chosen = res.tool_calls?.[0]?.name ?? null;
    if (chosen === expected) correct++;
    choices.push(chosen ?? "none");
  }

  console.log(`${name.padEnd(12)} ${correct}/${CASES.length}      ${choices.join(", ")}`);
}
```

**Python**
```python
from dotenv import load_dotenv
from langchain_core.tools import StructuredTool
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

class CalcArgs(BaseModel):
    expression: str = Field(description="An arithmetic expression")

calculator = StructuredTool.from_function(
    func=lambda expression: f"{expression} = ...",
    name="calculator",
    description="Evaluate an arithmetic expression. ALWAYS use for any calculation.",
    args_schema=CalcArgs,
)

class SearchArgs(BaseModel):
    query: str = Field(description="Search query")

def make_search(description):
    return StructuredTool.from_function(
        func=lambda query: f"results for {query}",
        name="web_search", description=description, args_schema=SearchArgs,
    )

VERSIONS = {
    "bare": make_search("Search"),
    "descriptive": make_search("Search the web for information"),
    "explicit": make_search(
        "Search the web for current events, news, prices, or facts that change over time. "
        "Use when the answer depends on information after your training cutoff. "
        "Do NOT use for arithmetic, and do NOT use for well-known historical facts."
    ),
}

# question → the tool that SHOULD be chosen (None = none)
CASES = [
    ("What is the current price of Bitcoin?", "web_search"),
    ("What is 8342 * 991?",                   "calculator"),
    ("Who wrote Hamlet?",                      None),
    ("What is 15% of 200?",                    "calculator"),
    ("What happened in the news today?",       "web_search"),
    ("What is the capital of France?",         None),
]

print("version      correct  choices")
print("-" * 70)

for name, search in VERSIONS.items():
    with_tools = model.bind_tools([calculator, search])
    correct, choices = 0, []

    for q, expected in CASES:
        res = with_tools.invoke(q)
        chosen = res.tool_calls[0]["name"] if res.tool_calls else None
        correct += chosen == expected
        choices.append(chosen or "none")

    print(f"{name:<12} {correct}/{len(CASES)}      {', '.join(choices)}")
```

**Typical output:**

```
version      correct  choices
----------------------------------------------------------------------
bare         3/6      web_search, web_search, web_search, calculator, web_search, web_search
descriptive  4/6      web_search, calculator, web_search, calculator, web_search, web_search
explicit     6/6      web_search, calculator, none, calculator, web_search, none
```

**Three things to take from this:**

1. **`"Search"` makes the model search for everything**, including arithmetic and Shakespeare.
   With no guidance about *when*, the model treats an available tool as one it should use.
2. **The "do NOT use for" clause is what produces the `none` answers.** Getting the model to
   *decline* to use a tool is harder than getting it to use one, and it needs explicit permission.
3. **This is a repeatable test.** Descriptions are prompts, so they deserve the same eval
   treatment as any other prompt (Day 02's regression harness). When someone adds a tool and
   accuracy drops, this is how you find out.

**Note the deliberate JS/Python asymmetry here:** JS `tool()` takes the description as an
option, so varying it is trivial. Python's `@tool` reads the docstring, which you can't easily
parameterise — hence `StructuredTool.from_function`, which accepts `description` explicitly.
That's the idiomatic way to build tools dynamically in Python.
</details>

---

### Exercise 2 — Error recovery ●●○○○

Build a tool that fails in four distinct ways (bad argument, not found, transient error,
too much data). For each, write an error message that lets the model recover, then verify it
actually does by running the loop and reading the trace.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import "dotenv/config";
import * as z from "zod";
import { tool } from "@langchain/core/tools";
import { ChatGroq } from "@langchain/groq";
import { HumanMessage, ToolMessage, SystemMessage } from "@langchain/core/messages";

const USERS = {
  1: { id: 1, name: "Wasif", plan: "pro", city: "Lahore" },
  2: { id: 2, name: "Aisha", plan: "basic", city: "Karachi" },
};
let transientCount = 0;

const lookupUser = tool(
  async ({ userId }) => {
    // ── 1. BAD ARGUMENT — say what's wrong AND what's valid ──────────────
    if (!Number.isInteger(userId) || userId < 1) {
      return `Error: userId must be a positive integer, got ${JSON.stringify(userId)}. ` +
             `Valid IDs are 1 and 2.`;
    }

    // ── 3. TRANSIENT — retry internally, only surface if it persists ─────
    if (userId === 99) {
      transientCount++;
      if (transientCount < 3) {
        return "Error: service temporarily unavailable (503). This is transient — " +
               "you may retry the same call once.";
      }
      return "Error: service still unavailable after retries. Report this to the user.";
    }

    // ── 2. NOT FOUND — suggest the recovery path ────────────────────────
    const user = USERS[userId];
    if (!user) {
      return `No user with ID ${userId}. Existing IDs: ${Object.keys(USERS).join(", ")}. ` +
             `If you have a name instead, use search_users.`;
    }

    return JSON.stringify(user);
  },
  {
    name: "lookup_user",
    description: "Look up a user by their numeric ID.",
    schema: z.object({ userId: z.number().int().describe("The user's numeric ID") }),
  }
);

const searchUsers = tool(
  async ({ name }) => {
    const matches = Object.values(USERS).filter((u) =>
      u.name.toLowerCase().includes(name.toLowerCase()));

    // ── 4. TOO MUCH DATA — truncate and SAY SO ──────────────────────────
    if (matches.length > 1) {
      return `Found ${matches.length} matches (showing first 1): ` +
             `${JSON.stringify(matches[0])}. Ask the user to narrow the search.`;
    }
    return matches.length ? JSON.stringify(matches[0]) : `No users matching "${name}".`;
  },
  {
    name: "search_users",
    description: "Find a user by name. Use when you have a name but not an ID.",
    schema: z.object({ name: z.string().describe("Full or partial name") }),
  }
);

const TOOLS = [lookupUser, searchUsers];
const BY_NAME = Object.fromEntries(TOOLS.map((t) => [t.name, t]));
const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 })
  .bindTools(TOOLS);

async function run(question, maxSteps = 6) {
  const messages = [
    new SystemMessage("You are a support assistant. Use tools. If a tool returns an error, " +
                      "read it carefully and adapt — do not give up on the first failure."),
    new HumanMessage(question),
  ];

  for (let step = 1; step <= maxSteps; step++) {
    const ai = await model.invoke(messages);
    messages.push(ai);
    if (!ai.tool_calls?.length) return ai.text;

    for (const call of ai.tool_calls) {
      let content;
      try { content = String(await BY_NAME[call.name].invoke(call.args)); }
      catch (e) { content = `Error: ${e.message}`; }

      console.log(`  [${step}] 🔧 ${call.name}(${JSON.stringify(call.args)})`);
      console.log(`      ← ${content.slice(0, 90)}`);
      messages.push(new ToolMessage({ content, tool_call_id: call.id }));
    }
  }
  return "⚠️ step limit";
}

for (const q of [
  "Look up user 5.",                       // not found → should try search or report
  "What plan is Wasif on?",                // no ID → should use search_users
  "Look up user 99.",                      // transient → should retry
]) {
  console.log(`\n${"═".repeat(74)}\n❓ ${q}\n${"═".repeat(74)}`);
  transientCount = 0;
  console.log(`\n  💬 ${await run(q)}`);
}
```

**Python**
```python
import json
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_groq import ChatGroq

load_dotenv()

USERS = {
    1: {"id": 1, "name": "Wasif", "plan": "pro", "city": "Lahore"},
    2: {"id": 2, "name": "Aisha", "plan": "basic", "city": "Karachi"},
}
transient_count = 0

@tool
def lookup_user(user_id: int) -> str:
    """Look up a user by their numeric ID.

    Args:
        user_id: The user's numeric ID.
    """
    global transient_count

    # ── 1. BAD ARGUMENT — say what's wrong AND what's valid ──────────────
    if not isinstance(user_id, int) or user_id < 1:
        return (f"Error: user_id must be a positive integer, got {user_id!r}. "
                f"Valid IDs are 1 and 2.")

    # ── 3. TRANSIENT — retry internally, only surface if it persists ─────
    if user_id == 99:
        transient_count += 1
        if transient_count < 3:
            return ("Error: service temporarily unavailable (503). This is transient — "
                    "you may retry the same call once.")
        return "Error: service still unavailable after retries. Report this to the user."

    # ── 2. NOT FOUND — suggest the recovery path ────────────────────────
    user = USERS.get(user_id)
    if not user:
        return (f"No user with ID {user_id}. Existing IDs: {', '.join(map(str, USERS))}. "
                f"If you have a name instead, use search_users.")

    return json.dumps(user)

@tool
def search_users(name: str) -> str:
    """Find a user by name. Use when you have a name but not an ID.

    Args:
        name: Full or partial name.
    """
    matches = [u for u in USERS.values() if name.lower() in u["name"].lower()]

    # ── 4. TOO MUCH DATA — truncate and SAY SO ──────────────────────────
    if len(matches) > 1:
        return (f"Found {len(matches)} matches (showing first 1): "
                f"{json.dumps(matches[0])}. Ask the user to narrow the search.")
    return json.dumps(matches[0]) if matches else f'No users matching "{name}".'

TOOLS = [lookup_user, search_users]
BY_NAME = {t.name: t for t in TOOLS}
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0).bind_tools(TOOLS)

def run(question, max_steps=6):
    messages = [
        SystemMessage("You are a support assistant. Use tools. If a tool returns an error, "
                      "read it carefully and adapt — do not give up on the first failure."),
        HumanMessage(question),
    ]

    for step in range(1, max_steps + 1):
        ai = model.invoke(messages)
        messages.append(ai)
        if not ai.tool_calls:
            return ai.content

        for call in ai.tool_calls:
            try:
                content = str(BY_NAME[call["name"]].invoke(call["args"]))
            except Exception as e:
                content = f"Error: {e}"

            print(f"  [{step}] 🔧 {call['name']}({call['args']})")
            print(f"      ← {content[:90]}")
            messages.append(ToolMessage(content=content, tool_call_id=call["id"]))

    return "⚠️ step limit"

for q in [
    "Look up user 5.",                       # not found → should try search or report
    "What plan is Wasif on?",                # no ID → should use search_users
    "Look up user 99.",                      # transient → should retry
]:
    print(f"\n{'═' * 74}\n❓ {q}\n{'═' * 74}")
    transient_count = 0
    print(f"\n  💬 {run(q)}")
```

**What you should observe:**

```
❓ Look up user 5.
  [1] 🔧 lookup_user({'user_id': 5})
      ← No user with ID 5. Existing IDs: 1, 2. If you have a name instead, use search_users.
  💬 There's no user with ID 5. The existing user IDs are 1 and 2.

❓ Look up user 99.
  [1] 🔧 lookup_user({'user_id': 99})
      ← Error: service temporarily unavailable (503). This is transient — you may retry…
  [2] 🔧 lookup_user({'user_id': 99})          ← IT RETRIED
      ← Error: service temporarily unavailable (503)…
  [3] 🔧 lookup_user({'user_id': 99})
      ← Error: service still unavailable after retries. Report this to the user.
  💬 The service is currently unavailable. Please try again later.
```

**The retry behaviour is the striking result.** The model retried because the error message
*told it that retrying was appropriate*. An error saying only `"Error: 503"` produces an immediate
give-up.

**The design principle:** an error message to a model is an instruction, not a log line. Include
what went wrong, whether it's retryable, and what to try instead. That transforms failures from
dead ends into recoverable steps.

**One production caveat:** transient errors are usually better retried *inside* the tool with
backoff (Day 03), so the model never sees them. Surface an error to the model only when the model
can do something different — a bad argument, a wrong lookup key, an alternative tool. Making the
model your retry loop wastes round trips.
</details>

---

### Exercise 3 — A safe filesystem toolkit ●●●○○

Build read, write and list tools scoped to a sandbox directory. Defend against path traversal,
oversized files and writes outside the sandbox. Then try to break your own sandbox with five
malicious paths.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import "dotenv/config";
import fs from "node:fs/promises";
import path from "node:path";
import * as z from "zod";
import { tool } from "@langchain/core/tools";

const SANDBOX = path.resolve("./workspace");
const MAX_READ = 4000;
const MAX_WRITE = 100_000;

// ⭐ THE security primitive — every tool goes through this
function safePath(filename) {
  if (typeof filename !== "string" || !filename.trim()) {
    return { ok: false, error: "Error: filename must be a non-empty string." };
  }
  // Reject absolute paths and null bytes outright
  if (path.isAbsolute(filename) || filename.includes("\0")) {
    return { ok: false, error: "Error: access denied — absolute paths are not allowed." };
  }

  const full = path.resolve(SANDBOX, filename);

  // resolve() collapses ".." — so compare AFTER resolving
  if (full !== SANDBOX && !full.startsWith(SANDBOX + path.sep)) {
    return { ok: false, error: "Error: access denied — path escapes the workspace." };
  }
  return { ok: true, full };
}

const listFiles = tool(
  async () => {
    await fs.mkdir(SANDBOX, { recursive: true });
    const entries = await fs.readdir(SANDBOX, { withFileTypes: true });
    if (!entries.length) return "The workspace is empty.";
    const rows = await Promise.all(entries.map(async (e) => {
      if (e.isDirectory()) return `${e.name}/  (directory)`;
      const { size } = await fs.stat(path.join(SANDBOX, e.name));
      return `${e.name}  (${size} bytes)`;
    }));
    return rows.join("\n");
  },
  { name: "list_files", description: "List all files in the workspace directory.",
    schema: z.object({}) }
);

const readFile = tool(
  async ({ filename }) => {
    const p = safePath(filename);
    if (!p.ok) return p.error;

    try {
      const text = await fs.readFile(p.full, "utf8");
      return text.length > MAX_READ
        ? text.slice(0, MAX_READ) + `\n…[truncated: showing ${MAX_READ} of ${text.length} chars]`
        : text;
    } catch (e) {
      if (e.code === "ENOENT") return `File not found. Use list_files to see what exists.`;
      if (e.code === "EISDIR") return `"${filename}" is a directory, not a file.`;
      return `Error reading file: ${e.message}`;
    }
  },
  { name: "read_file", description: "Read a text file from the workspace. " +
      "Only files inside the workspace are accessible.",
    schema: z.object({ filename: z.string().describe("Relative filename, e.g. 'notes.md'") }) }
);

const writeFile = tool(
  async ({ filename, content }) => {
    const p = safePath(filename);
    if (!p.ok) return p.error;

    if (content.length > MAX_WRITE) {
      return `Error: content is ${content.length} chars, limit is ${MAX_WRITE}.`;
    }
    // Refuse to write outside the top level — no creating nested trees
    if (path.dirname(p.full) !== SANDBOX) {
      return "Error: files can only be written to the top level of the workspace.";
    }

    await fs.mkdir(SANDBOX, { recursive: true });
    await fs.writeFile(p.full, content, "utf8");
    return `Wrote ${content.length} chars to ${filename}.`;
  },
  { name: "write_file", description: "Write a text file to the workspace. Overwrites if it exists.",
    schema: z.object({
      filename: z.string().describe("Relative filename"),
      content: z.string().describe("File contents"),
    }) }
);

// ── attack the sandbox ───────────────────────────────────────────────────
const ATTACKS = [
  "../../../etc/passwd",
  "../../.env",
  "/etc/passwd",
  "notes/../../../secrets.txt",
  "..\\..\\windows\\system32\\config\\sam",
  "subdir/nested.txt",              // legitimate-looking, but nested writes are blocked
  "normal.txt",                     // should succeed
];

await fs.mkdir(SANDBOX, { recursive: true });
await fs.writeFile(path.join(SANDBOX, "notes.md"), "# My notes\nHello world.", "utf8");

console.log("── read attempts ──");
for (const a of ATTACKS) {
  const r = await readFile.invoke({ filename: a });
  const blocked = r.startsWith("Error: access denied");
  console.log(`  ${blocked ? "🛡️  BLOCKED" : "⚠️  allowed"}  ${a.padEnd(42)} ${r.slice(0, 40)}`);
}

console.log("\n── write attempts ──");
for (const a of ["../escape.txt", "subdir/nested.txt", "report.txt"]) {
  console.log(`  ${a.padEnd(24)} ${(await writeFile.invoke({ filename: a, content: "x" })).slice(0, 60)}`);
}

console.log("\n── legitimate use ──");
console.log(await listFiles.invoke({}));
console.log(await readFile.invoke({ filename: "notes.md" }));
```

**Python**
```python
import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_core.tools import tool

load_dotenv()

SANDBOX = Path("./workspace").resolve()
MAX_READ, MAX_WRITE = 4000, 100_000

# ⭐ THE security primitive — every tool goes through this
def safe_path(filename):
    if not isinstance(filename, str) or not filename.strip():
        return None, "Error: filename must be a non-empty string."
    if os.path.isabs(filename) or "\0" in filename:
        return None, "Error: access denied — absolute paths are not allowed."

    full = (SANDBOX / filename).resolve()

    # resolve() collapses ".." — so compare AFTER resolving
    if full != SANDBOX and not str(full).startswith(str(SANDBOX) + os.sep):
        return None, "Error: access denied — path escapes the workspace."
    return full, None

@tool
def list_files() -> str:
    """List all files in the workspace directory."""
    SANDBOX.mkdir(parents=True, exist_ok=True)
    entries = sorted(SANDBOX.iterdir())
    if not entries:
        return "The workspace is empty."
    return "\n".join(
        f"{e.name}/  (directory)" if e.is_dir() else f"{e.name}  ({e.stat().st_size} bytes)"
        for e in entries
    )

@tool
def read_file(filename: str) -> str:
    """Read a text file from the workspace.

    Only files inside the workspace are accessible.

    Args:
        filename: Relative filename, e.g. 'notes.md'
    """
    full, err = safe_path(filename)
    if err:
        return err

    try:
        text = full.read_text(encoding="utf8")
        return (text[:MAX_READ] + f"\n…[truncated: showing {MAX_READ} of {len(text)} chars]"
                if len(text) > MAX_READ else text)
    except FileNotFoundError:
        return "File not found. Use list_files to see what exists."
    except IsADirectoryError:
        return f'"{filename}" is a directory, not a file.'
    except Exception as e:
        return f"Error reading file: {e}"

@tool
def write_file(filename: str, content: str) -> str:
    """Write a text file to the workspace. Overwrites if it exists.

    Args:
        filename: Relative filename.
        content: File contents.
    """
    full, err = safe_path(filename)
    if err:
        return err

    if len(content) > MAX_WRITE:
        return f"Error: content is {len(content)} chars, limit is {MAX_WRITE}."
    # Refuse to write outside the top level — no creating nested trees
    if full.parent != SANDBOX:
        return "Error: files can only be written to the top level of the workspace."

    SANDBOX.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf8")
    return f"Wrote {len(content)} chars to {filename}."

# ── attack the sandbox ───────────────────────────────────────────────────
ATTACKS = [
    "../../../etc/passwd",
    "../../.env",
    "/etc/passwd",
    "notes/../../../secrets.txt",
    "..\\..\\windows\\system32\\config\\sam",
    "subdir/nested.txt",
    "normal.txt",
]

SANDBOX.mkdir(parents=True, exist_ok=True)
(SANDBOX / "notes.md").write_text("# My notes\nHello world.", encoding="utf8")

print("── read attempts ──")
for a in ATTACKS:
    r = read_file.invoke({"filename": a})
    blocked = r.startswith("Error: access denied")
    print(f"  {'🛡️  BLOCKED' if blocked else '⚠️  allowed'}  {a:<42} {r[:40]}")

print("\n── write attempts ──")
for a in ["../escape.txt", "subdir/nested.txt", "report.txt"]:
    print(f"  {a:<24} {write_file.invoke({'filename': a, 'content': 'x'})[:60]}")

print("\n── legitimate use ──")
print(list_files.invoke({}))
print(read_file.invoke({"filename": "notes.md"}))
```

**Expected:**

```
── read attempts ──
  🛡️  BLOCKED  ../../../etc/passwd                        Error: access denied — path escapes
  🛡️  BLOCKED  ../../.env                                 Error: access denied — path escapes
  🛡️  BLOCKED  /etc/passwd                                Error: access denied — absolute paths
  🛡️  BLOCKED  notes/../../../secrets.txt                 Error: access denied — path escapes
  ⚠️  allowed  ..\..\windows\system32\config\sam          File not found. Use list_files…
  ⚠️  allowed  subdir/nested.txt                          File not found. Use list_files…
  ⚠️  allowed  normal.txt                                 File not found. Use list_files…
```

**Four things worth noting:**

1. **`resolve()` before comparing is the whole trick.** `workspace/notes/../../../secrets.txt`
   *looks* nested but resolves outside. Comparing the raw string would let it through — this is
   the classic path-traversal bug.

2. **The Windows-style path shows a platform subtlety.** On Linux, `..\..\windows\...` is a
   single weird *filename*, not a traversal, so it's "allowed" but harmless — it just doesn't
   exist. On Windows the separator is real and `resolve()` catches it. Test on your target OS.

3. **Absolute paths are rejected before resolving.** `SANDBOX / "/etc/passwd"` in Python resolves
   to `/etc/passwd`, silently escaping — so the `isabs` check must come first. This is a real
   `pathlib` footgun.

4. **Writes are more restricted than reads.** Reads allow nesting; writes are top-level only.
   Asymmetric permissions are normal — the blast radius of a bad write is larger.

**The bigger point:** none of this is prompt engineering. You cannot instruct a model into being
safe, because the arguments it emits are influenced by untrusted text (Day 02). The boundary is
in `safePath()`, in code, where it can be tested — and it *should* have unit tests, because this
is exactly the kind of function that quietly regresses.
</details>

---

### Exercise 4 — Tool routing at scale ●●●●○

Binding 20 tools degrades accuracy and wastes tokens. Build a router that classifies the request
into a category, binds only that category's tools, and falls back to a small default set.
Measure token overhead and selection accuracy against binding everything.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import "dotenv/config";
import * as z from "zod";
import { tool } from "@langchain/core/tools";
import { ChatGroq } from "@langchain/groq";

const fast = new ChatGroq({ model: "llama-3.1-8b-instant", temperature: 0 });
const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });

// ── 20 tools across 4 categories ─────────────────────────────────────────
const mk = (name, description) =>
  tool(async (a) => `${name} result`, {
    name, description, schema: z.object({ input: z.string().describe("Input") }),
  });

const CATEGORIES = {
  finance: [
    mk("get_stock_price", "Get the current share price for a ticker symbol."),
    mk("get_exchange_rate", "Get the current exchange rate between two currencies."),
    mk("calculate_interest", "Calculate compound interest over a period."),
    mk("get_portfolio", "Retrieve the user's investment portfolio holdings."),
    mk("record_expense", "Record a business expense in the ledger."),
  ],
  calendar: [
    mk("list_events", "List calendar events in a date range."),
    mk("create_event", "Create a new calendar event."),
    mk("find_free_slot", "Find a free time slot for a meeting."),
    mk("cancel_event", "Cancel an existing calendar event."),
    mk("get_timezone", "Get the timezone for a location."),
  ],
  documents: [
    mk("search_documents", "Search the user's indexed documents semantically."),
    mk("read_document", "Read the full text of a document by ID."),
    mk("summarise_document", "Produce a summary of a document."),
    mk("list_documents", "List all indexed documents."),
    mk("delete_document", "Delete a document from the index."),
  ],
  communication: [
    mk("send_email", "Send an email to an approved recipient."),
    mk("send_slack", "Post a message to a Slack channel."),
    mk("list_contacts", "List the user's saved contacts."),
    mk("draft_reply", "Draft a reply to a received message."),
    mk("schedule_send", "Schedule an email to send later."),
  ],
};

const ALL = Object.values(CATEGORIES).flat();
const ALWAYS = [
  tool(async ({ expression }) => `${expression} = ...`, {
    name: "calculator", description: "Evaluate an arithmetic expression. Use for ALL maths.",
    schema: z.object({ expression: z.string() }),
  }),
];

// ── the router ───────────────────────────────────────────────────────────
const Route = z.object({
  reasoning: z.string().describe("One sentence. Write this first."),
  category: z.enum(["finance", "calendar", "documents", "communication", "none"])
    .describe("Which tool category this request needs, or 'none' for general questions"),
});

const router = fast.withStructuredOutput(Route)
  .withFallbacks([{ invoke: async () => ({ reasoning: "router failed", category: "none" }) }]);

async function routedInvoke(question) {
  const { category, reasoning } = await router.invoke(
    `Classify which tool category this request needs.\n\n` +
    `finance: stock prices, exchange rates, interest, portfolio, expenses\n` +
    `calendar: events, meetings, scheduling, timezones\n` +
    `documents: searching, reading, summarising the user's files\n` +
    `communication: email, Slack, contacts, drafting messages\n` +
    `none: general questions, arithmetic, chitchat\n\n` +
    `Request: ${question}`
  );

  const tools = [...ALWAYS, ...(CATEGORIES[category] ?? [])];
  const res = await model.bindTools(tools).invoke(question);

  return {
    category, reasoning, toolCount: tools.length,
    chosen: res.tool_calls?.[0]?.name ?? null,
    inputTokens: res.usage_metadata?.input_tokens ?? 0,
  };
}

async function bindAllInvoke(question) {
  const tools = [...ALWAYS, ...ALL];
  const res = await model.bindTools(tools).invoke(question);
  return {
    toolCount: tools.length,
    chosen: res.tool_calls?.[0]?.name ?? null,
    inputTokens: res.usage_metadata?.input_tokens ?? 0,
  };
}

// ── evaluate ─────────────────────────────────────────────────────────────
const CASES = [
  ["What's the price of AAPL?",                    "get_stock_price"],
  ["Am I free on Thursday afternoon?",             "find_free_slot"],
  ["Find my notes about the Q3 roadmap",           "search_documents"],
  ["Email the summary to my manager",              "send_email"],
  ["What is 15% of 8342?",                          "calculator"],
  ["Cancel my 3pm meeting",                         "cancel_event"],
];

console.log("question                          strategy  tools  tokens  chosen");
console.log("-".repeat(88));

let routedCorrect = 0, allCorrect = 0, routedTokens = 0, allTokens = 0;

for (const [q, expected] of CASES) {
  const r = await routedInvoke(q);
  const a = await bindAllInvoke(q);

  routedCorrect += r.chosen === expected ? 1 : 0;
  allCorrect += a.chosen === expected ? 1 : 0;
  routedTokens += r.inputTokens;
  allTokens += a.inputTokens;

  console.log(`${q.slice(0, 32).padEnd(32)}  routed    ${String(r.toolCount).padStart(5)}  ` +
              `${String(r.inputTokens).padStart(6)}  ${r.chosen ?? "none"} ` +
              `${r.chosen === expected ? "✅" : "❌"}`);
  console.log(`${"".padEnd(32)}  all       ${String(a.toolCount).padStart(5)}  ` +
              `${String(a.inputTokens).padStart(6)}  ${a.chosen ?? "none"} ` +
              `${a.chosen === expected ? "✅" : "❌"}`);
}

console.log(`\nrouted: ${routedCorrect}/${CASES.length} correct, ${routedTokens} input tokens`);
console.log(`all:    ${allCorrect}/${CASES.length} correct, ${allTokens} input tokens`);
console.log(`token saving: ${(100 * (1 - routedTokens / allTokens)).toFixed(0)}%`);
```

**Python**
```python
from typing import Literal
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool
from langchain_groq import ChatGroq

load_dotenv()
fast = ChatGroq(model="llama-3.1-8b-instant", temperature=0)
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

class ToolArgs(BaseModel):
    input: str = Field(description="Input")

def mk(name, description):
    return StructuredTool.from_function(
        func=lambda input, _n=name: f"{_n} result",
        name=name, description=description, args_schema=ToolArgs,
    )

CATEGORIES = {
    "finance": [
        mk("get_stock_price", "Get the current share price for a ticker symbol."),
        mk("get_exchange_rate", "Get the current exchange rate between two currencies."),
        mk("calculate_interest", "Calculate compound interest over a period."),
        mk("get_portfolio", "Retrieve the user's investment portfolio holdings."),
        mk("record_expense", "Record a business expense in the ledger."),
    ],
    "calendar": [
        mk("list_events", "List calendar events in a date range."),
        mk("create_event", "Create a new calendar event."),
        mk("find_free_slot", "Find a free time slot for a meeting."),
        mk("cancel_event", "Cancel an existing calendar event."),
        mk("get_timezone", "Get the timezone for a location."),
    ],
    "documents": [
        mk("search_documents", "Search the user's indexed documents semantically."),
        mk("read_document", "Read the full text of a document by ID."),
        mk("summarise_document", "Produce a summary of a document."),
        mk("list_documents", "List all indexed documents."),
        mk("delete_document", "Delete a document from the index."),
    ],
    "communication": [
        mk("send_email", "Send an email to an approved recipient."),
        mk("send_slack", "Post a message to a Slack channel."),
        mk("list_contacts", "List the user's saved contacts."),
        mk("draft_reply", "Draft a reply to a received message."),
        mk("schedule_send", "Schedule an email to send later."),
    ],
}

ALL = [t for group in CATEGORIES.values() for t in group]

class CalcArgs(BaseModel):
    expression: str = Field(description="An arithmetic expression")

ALWAYS = [StructuredTool.from_function(
    func=lambda expression: f"{expression} = ...",
    name="calculator",
    description="Evaluate an arithmetic expression. Use for ALL maths.",
    args_schema=CalcArgs,
)]

class Route(BaseModel):
    """Which tool category a request needs."""
    reasoning: str = Field(description="One sentence. Write this first.")
    category: Literal["finance", "calendar", "documents", "communication", "none"]

router = fast.with_structured_output(Route)

def routed_invoke(question):
    r = router.invoke(
        "Classify which tool category this request needs.\n\n"
        "finance: stock prices, exchange rates, interest, portfolio, expenses\n"
        "calendar: events, meetings, scheduling, timezones\n"
        "documents: searching, reading, summarising the user's files\n"
        "communication: email, Slack, contacts, drafting messages\n"
        "none: general questions, arithmetic, chitchat\n\n"
        f"Request: {question}"
    )
    tools = ALWAYS + CATEGORIES.get(r.category, [])
    res = model.bind_tools(tools).invoke(question)
    return {
        "category": r.category, "tool_count": len(tools),
        "chosen": res.tool_calls[0]["name"] if res.tool_calls else None,
        "input_tokens": (res.usage_metadata or {}).get("input_tokens", 0),
    }

def bind_all_invoke(question):
    tools = ALWAYS + ALL
    res = model.bind_tools(tools).invoke(question)
    return {
        "tool_count": len(tools),
        "chosen": res.tool_calls[0]["name"] if res.tool_calls else None,
        "input_tokens": (res.usage_metadata or {}).get("input_tokens", 0),
    }

CASES = [
    ("What's the price of AAPL?",           "get_stock_price"),
    ("Am I free on Thursday afternoon?",    "find_free_slot"),
    ("Find my notes about the Q3 roadmap",  "search_documents"),
    ("Email the summary to my manager",     "send_email"),
    ("What is 15% of 8342?",                 "calculator"),
    ("Cancel my 3pm meeting",                "cancel_event"),
]

print("question                          strategy  tools  tokens  chosen")
print("-" * 88)

routed_correct = all_correct = routed_tokens = all_tokens = 0

for q, expected in CASES:
    r, a = routed_invoke(q), bind_all_invoke(q)
    routed_correct += r["chosen"] == expected
    all_correct += a["chosen"] == expected
    routed_tokens += r["input_tokens"]
    all_tokens += a["input_tokens"]

    print(f"{q[:32]:<32}  routed    {r['tool_count']:>5}  {r['input_tokens']:>6}  "
          f"{r['chosen'] or 'none'} {'✅' if r['chosen'] == expected else '❌'}")
    print(f"{'':<32}  all       {a['tool_count']:>5}  {a['input_tokens']:>6}  "
          f"{a['chosen'] or 'none'} {'✅' if a['chosen'] == expected else '❌'}")

print(f"\nrouted: {routed_correct}/{len(CASES)} correct, {routed_tokens} input tokens")
print(f"all:    {all_correct}/{len(CASES)} correct, {all_tokens} input tokens")
print(f"token saving: {100 * (1 - routed_tokens / all_tokens):.0f}%")
```

**Typical result:**

```
routed: 6/6 correct, 2140 input tokens
all:    5/6 correct, 8960 input tokens
token saving: 76%
```

**Three conclusions:**

1. **~75% fewer input tokens.** Twenty tool schemas is roughly 1,200 tokens *on every call*.
   At scale that's most of your input bill, paid to describe tools the request will never use.

2. **Accuracy improves too, which surprises people.** With 21 tools bound, models confuse
   similar ones — `send_email` vs `schedule_send` vs `draft_reply`. Narrowing the choice removes
   the confusion. **Fewer options is a feature**, not just an optimisation.

3. **The `ALWAYS` set matters.** The calculator is bound regardless of category, because maths
   comes up in every domain. Most real systems have a few universal tools plus category-specific
   ones.

**The trade-offs to state honestly:**
- The router adds a call and ~200ms to every request. Use the cheap model.
- **Cross-category requests break it.** "Find my Q3 notes and email them to my manager" needs
  *documents* and *communication*. Fixes: allow multi-label classification, or let the agent
  request more tools mid-run. This is where a fixed router stops being enough and you want an
  agent that can expand its own toolset — which is Week 3's later material.
- The router must fail safe. If classification fails, bind a sensible default rather than erroring.
</details>

---

### Exercise 5 — 🏆 A tool-using research assistant ●●●●●

Build a CLI assistant with 5+ tools (calculator, search or a fake corpus, filesystem, a fake
database, and one write tool), a bounded execution loop, parallel tool execution, a full trace
view, cost tracking, and a confirmation prompt before any write action.

<details>
<summary>✅ Solution</summary>

**Python**
```python
# research_assistant.py
"""A tool-using assistant with a bounded loop, tracing, and write confirmation."""
import json, os, re, time
from pathlib import Path
from typing import Literal, Optional
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage
from langchain_groq import ChatGroq

load_dotenv()

model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

SANDBOX = Path("./workspace").resolve()
MAX_STEPS = 8

# Tools whose effects are not undoable — these require confirmation.
WRITE_TOOLS = {"write_file", "send_email"}

PRICING = {"in": 0.59 / 1e6, "out": 0.79 / 1e6}   # llama-3.3-70b, USD per token

# ══════════════════ TOOLS ════════════════════════════════════════════════
def safe_path(filename):
    if os.path.isabs(filename) or "\0" in filename:
        return None, "Error: access denied — absolute paths are not allowed."
    full = (SANDBOX / filename).resolve()
    if full != SANDBOX and not str(full).startswith(str(SANDBOX) + os.sep):
        return None, "Error: access denied — path escapes the workspace."
    return full, None

@tool
def calculator(expression: str) -> str:
    """Evaluate an arithmetic expression.

    ALWAYS use this for any calculation, however simple. Never compute in your head.

    Args:
        expression: e.g. '(240 + 890) * 0.15'
    """
    if not re.fullmatch(r"[\d\s+\-*/().%]+", expression):
        return "Error: only numbers and + - * / ( ) % are allowed."
    try:
        return f"{expression} = {eval(expression)}"
    except Exception:
        return f"Error: '{expression}' is not valid arithmetic."

KNOWLEDGE = {
    "langchain": "LangChain is a framework for building LLM applications. Version 1.0 "
                 "moved legacy chains and retrievers into the langchain-classic package.",
    "langgraph": "LangGraph adds stateful, cyclic workflows: nodes, edges, typed state "
                 "with reducers, checkpointers for persistence, and interrupts for "
                 "human-in-the-loop.",
    "rag": "Retrieval-Augmented Generation retrieves relevant documents and puts them in "
           "the prompt. Key stages: load, split, embed, store, retrieve, generate.",
    "embeddings": "Embeddings map text to vectors where distance means dissimilarity. "
                  "Typical sizes are 384 to 3072 dimensions. Cosine similarity is standard.",
}

@tool
def search_knowledge(query: str) -> str:
    """Search the internal knowledge base about AI engineering topics.

    Use for questions about LangChain, LangGraph, RAG or embeddings.
    Do NOT use for arithmetic or for the user's own files.

    Args:
        query: What to look up.
    """
    q = query.lower()
    hits = [f"[{k}] {v}" for k, v in KNOWLEDGE.items() if k in q or any(
        w in v.lower() for w in q.split() if len(w) > 4)]
    if not hits:
        return f'Nothing found for "{query}". Topics available: {", ".join(KNOWLEDGE)}.'
    return "\n\n".join(hits[:2])

ORDERS = [
    {"id": 1, "customer": "acme", "total": 240, "date": "2024-06-01", "status": "shipped"},
    {"id": 2, "customer": "globex", "total": 890, "date": "2024-06-01", "status": "pending"},
    {"id": 3, "customer": "acme", "total": 120, "date": "2024-06-02", "status": "shipped"},
    {"id": 4, "customer": "initech", "total": 450, "date": "2024-06-03", "status": "cancelled"},
]

@tool
def query_orders(
    query_name: Literal["by_customer", "by_status", "all", "revenue_total"],
    customer: Optional[str] = None,
    status: Optional[Literal["shipped", "pending", "cancelled"]] = None,
) -> str:
    """Run a pre-approved read-only query against the orders database.

    Use for any question about orders, customers or revenue.

    Args:
        query_name: Which approved query to run.
        customer: Required for by_customer.
        status: Required for by_status.
    """
    if query_name == "by_customer":
        if not customer:
            return "Error: 'customer' is required for by_customer. Known: acme, globex, initech."
        rows = [o for o in ORDERS if o["customer"] == customer]
    elif query_name == "by_status":
        if not status:
            return "Error: 'status' is required for by_status."
        rows = [o for o in ORDERS if o["status"] == status]
    elif query_name == "revenue_total":
        rows = [{"revenue": sum(o["total"] for o in ORDERS)}]
    else:
        rows = ORDERS

    return json.dumps(rows) if rows else "No matching rows."

@tool
def list_files() -> str:
    """List files in the workspace directory."""
    SANDBOX.mkdir(parents=True, exist_ok=True)
    files = sorted(p.name for p in SANDBOX.iterdir() if p.is_file())
    return "\n".join(files) if files else "The workspace is empty."

@tool
def read_file(filename: str) -> str:
    """Read a text file from the workspace.

    Args:
        filename: Relative filename, e.g. 'report.md'
    """
    full, err = safe_path(filename)
    if err:
        return err
    try:
        text = full.read_text(encoding="utf8")
        return text[:4000] + ("\n…[truncated]" if len(text) > 4000 else "")
    except FileNotFoundError:
        return "File not found. Use list_files to see what exists."

@tool
def write_file(filename: str, content: str) -> str:
    """Write a text file to the workspace. Overwrites if it exists.

    Only use when the user explicitly asks you to save or write something.

    Args:
        filename: Relative filename.
        content: The full file contents.
    """
    full, err = safe_path(filename)
    if err:
        return err
    if full.parent != SANDBOX:
        return "Error: files can only be written to the top level of the workspace."

    SANDBOX.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf8")
    return f"Wrote {len(content)} chars to {filename}."

TOOLS = [calculator, search_knowledge, query_orders, list_files, read_file, write_file]
BY_NAME = {t.name: t for t in TOOLS}
model_with_tools = model.bind_tools(TOOLS)

# ══════════════════ THE LOOP ═════════════════════════════════════════════
SYSTEM = SystemMessage(
    "You are a research assistant with tools.\n"
    "Rules:\n"
    "- ALWAYS use the calculator for arithmetic. Never compute in your head.\n"
    "- Use query_orders for anything about orders or revenue.\n"
    "- Use search_knowledge for AI engineering concepts.\n"
    "- Only write files when explicitly asked.\n"
    "- If a tool returns an error, read it and adapt rather than giving up."
)

def run(question, history, auto_approve=False):
    messages = [SYSTEM] + history + [HumanMessage(question)]
    trace, usage = [], {"in": 0, "out": 0}

    for step in range(1, MAX_STEPS + 1):
        ai = model_with_tools.invoke(messages)
        messages.append(ai)

        u = ai.usage_metadata or {}
        usage["in"] += u.get("input_tokens", 0)
        usage["out"] += u.get("output_tokens", 0)

        if not ai.tool_calls:
            return {"answer": ai.content, "trace": trace, "usage": usage,
                    "messages": messages, "steps": step}

        for call in ai.tool_calls:
            name, args = call["name"], call["args"]

            # ── confirmation gate for irreversible actions ───────────────
            if name in WRITE_TOOLS and not auto_approve:
                print(f"\n  ⚠️  The assistant wants to run: {name}({json.dumps(args)[:120]})")
                ok = input("     approve? [y/N] ").strip().lower() == "y"
                if not ok:
                    content = "The user DENIED this action. Do not retry it. " \
                              "Explain to the user what you would have done."
                    trace.append((step, name, args, "DENIED"))
                    messages.append(ToolMessage(content=content, tool_call_id=call["id"]))
                    continue

            t0 = time.time()
            try:
                content = str(BY_NAME[name].invoke(args)) if name in BY_NAME \
                    else f'Error: unknown tool "{name}". Available: {", ".join(BY_NAME)}'
            except Exception as e:
                content = f"Error: {e}"

            trace.append((step, name, args, f"{content[:55]} ({(time.time()-t0)*1000:.0f}ms)"))
            messages.append(ToolMessage(content=content, tool_call_id=call["id"]))

    return {"answer": "⚠️ Reached the step limit without finishing.",
            "trace": trace, "usage": usage, "messages": messages, "steps": MAX_STEPS}

# ══════════════════ CLI ══════════════════════════════════════════════════
def main():
    history = []
    total = {"in": 0, "out": 0}

    print("╔" + "═" * 62 + "╗")
    print("║  Research Assistant — 6 tools, bounded loop, write gate      ║")
    print("║  /tools /trace /cost /reset /exit                            ║")
    print("╚" + "═" * 62 + "╝\n")

    last_trace = []

    while True:
        try:
            q = input("you › ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q or q == "/exit":
            break

        if q == "/tools":
            for t in TOOLS:
                print(f"  {t.name:<18} {t.description.splitlines()[0]}")
            print()
            continue
        if q == "/trace":
            for step, name, args, result in last_trace:
                print(f"  [{step}] {name}({json.dumps(args)[:60]})\n      → {result}")
            print()
            continue
        if q == "/cost":
            cost = total["in"] * PRICING["in"] + total["out"] * PRICING["out"]
            print(f"  in={total['in']} out={total['out']} ≈ ${cost:.5f}\n")
            continue
        if q == "/reset":
            history = []
            print("  history cleared\n")
            continue

        t0 = time.time()
        r = run(q, history)
        last_trace = r["trace"]

        for step, name, args, result in r["trace"]:
            print(f"  [{step}] 🔧 {name}({json.dumps(args)[:60]})")
            print(f"      → {result}")

        print(f"\nbot › {r['answer']}\n")

        total["in"] += r["usage"]["in"]
        total["out"] += r["usage"]["out"]
        cost = r["usage"]["in"] * PRICING["in"] + r["usage"]["out"] * PRICING["out"]
        print(f"  ⏱  {(time.time()-t0)*1000:.0f}ms · {r['steps']} model calls · "
              f"{len(r['trace'])} tool calls · ${cost:.5f}\n")

        # Keep the conversation, bounded
        history = r["messages"][1:][-8:]

if __name__ == "__main__":
    main()
```

**JavaScript** — the same architecture; the distinctive pieces:
```js
// Bounded loop with PARALLEL tool execution and a write gate
const WRITE_TOOLS = new Set(["write_file", "send_email"]);

for (let step = 1; step <= MAX_STEPS; step++) {
  const ai = await modelWithTools.invoke(messages);
  messages.push(ai);
  if (!ai.tool_calls?.length) return { answer: ai.text, trace, usage };

  // Split into gated and ungated so ungated ones still run in parallel
  const gated = ai.tool_calls.filter((c) => WRITE_TOOLS.has(c.name));
  const free  = ai.tool_calls.filter((c) => !WRITE_TOOLS.has(c.name));

  const freeResults = await Promise.all(free.map(async (call) => {
    let content;
    try { content = String(await BY_NAME[call.name].invoke(call.args)); }
    catch (e) { content = `Error: ${e.message}`; }
    trace.push({ step, name: call.name, args: call.args, result: content.slice(0, 55) });
    return new ToolMessage({ content, tool_call_id: call.id });
  }));

  const gatedResults = [];
  for (const call of gated) {                       // sequential — each needs a prompt
    const ok = await confirm(`run ${call.name}(${JSON.stringify(call.args).slice(0,100)})?`);
    const content = ok
      ? String(await BY_NAME[call.name].invoke(call.args))
      : "The user DENIED this action. Do not retry it. Explain what you would have done.";
    gatedResults.push(new ToolMessage({ content, tool_call_id: call.id }));
  }

  messages.push(...freeResults, ...gatedResults);
}
```

**Try it:**

```
you › How much revenue did we make, and what's 15% of that?
  [1] 🔧 query_orders({"query_name": "revenue_total"})
      → [{"revenue": 1700}] (0ms)
  [2] 🔧 calculator({"expression": "1700 * 0.15"})
      → 1700 * 0.15 = 255.0 (0ms)
bot › Total revenue is $1,700, and 15% of that is $255.

you › Save that as a report
  ⚠️  The assistant wants to run: write_file({"filename": "report.md", ...})
     approve? [y/N] y
  [1] 🔧 write_file({"filename": "report.md", "content": "# Revenue Report\n..."})
      → Wrote 84 chars to report.md. (1ms)
bot › Saved to report.md.
```

**Seven design decisions worth defending:**

1. **The write gate is a hard boundary, not a prompt instruction.** `WRITE_TOOLS` is checked in
   code before execution. A prompt saying "ask before writing" is advisory; this is enforced.

2. **Denial is fed back as information.** `"The user DENIED this action. Do not retry it."` —
   without the "do not retry", the model often tries the same call again on the next step.
   Telling it to explain instead produces a graceful outcome.

3. **Ungated tools still run in parallel** (see the JS version). Splitting gated from ungated
   preserves the latency benefit for reads while serialising the calls that need a human.

4. **Errors are actionable.** `"Error: 'customer' is required for by_customer. Known: acme,
   globex, initech."` — the model retries correctly instead of failing.

5. **The loop is bounded and reports how many steps it used.** Watching `steps` climb is your
   early warning that a tool description is confusing the model.

6. **Cost is tracked per turn and cumulatively.** Tool loops multiply model calls — a three-tool
   question costs four model calls, not one. This is the number that surprises people in production.

7. **`/trace` exists.** When an agent does something odd, the tool trace is the first thing you
   need. Building it in from the start beats adding it during an incident.

**What it can't do yet — the bridge to tomorrow.** This loop is fine, but look at what's
hard-coded: the step limit, the state (a `messages` array threaded by hand), the confirmation
flow (a blocking `input()` that would be impossible in a web server), and there's no way to
*pause* the run, persist it, and resume tomorrow.

Tomorrow you'll build the ReAct pattern that underlies this properly. Then from Day 17 the whole
loop becomes a **graph**, where state, persistence, and pausing for approval are infrastructure
rather than code you maintain.
</details>

---

## 9. Interview questions

### Basic

<details>
<summary><b>Q: What is a tool in LangChain?</b></summary>

A function the model can request, wrapped with three pieces of metadata: a **name** (how the
model refers to it), a **description** (when to use it — this is prompt text), and a **schema**
(what arguments it takes). The function body itself is never seen by the model.

Created with `tool(fn, { name, description, schema })` in JS or the `@tool` decorator in Python,
where the docstring becomes the description and type hints become the schema.
</details>

<details>
<summary><b>Q: What happens when a model "calls" a tool?</b></summary>

It doesn't execute anything. The model emits a structured request — a `tool_call` with a name
and JSON arguments — and generation stops. **Your application** looks up the function, executes
it, and appends a `ToolMessage` containing the result plus the matching `tool_call_id`. Then you
call the model again with the extended history, and it either requests another tool or answers.

The key point for interviews: the model only ever *requests*. Execution, validation, error
handling and looping are all the application's responsibility.
</details>

<details>
<summary><b>Q: Why do tool descriptions matter so much?</b></summary>

Because they're the only thing the model has to decide with. The name, description and schema are
serialised into the prompt on every call; the implementation is invisible.

A description saying just `"Search"` makes the model search for everything, including arithmetic.
A good description says what the tool does, **when** to use it, and **when not to** — that last
clause is what lets the model decline. Field descriptions in the schema matter equally, since
they determine argument quality.
</details>

<details>
<summary><b>Q: What is `ToolNode`?</b></summary>

A LangGraph prebuilt that executes the tool loop's body: it takes state containing messages,
finds the `tool_calls` on the last AI message, runs them in parallel, and returns `ToolMessage`s
with matching IDs. It handles unknown tools and errors for you.

It's the ~20 lines of execution code you'd otherwise write by hand, packaged as a graph node.
</details>

### Intermediate

<details>
<summary><b>Q: How should a tool handle errors?</b></summary>

Return the error **to the model as content**, don't throw. Throwing kills the loop and produces a
500; returning gives the model a chance to recover — try a different argument, use another tool,
or explain the limitation to the user.

The error message is effectively an instruction, so make it actionable: what went wrong, whether
it's retryable, and what to try instead. `"Error: no user with ID 5. Existing IDs: 1, 2. If you
have a name, use search_users."` produces a correct recovery; `"Error: NotFound"` produces a
give-up.

One caveat: **transient** errors (429, 503) are usually better retried inside the tool with
backoff, so the model never sees them. Only surface errors the model can act on differently —
otherwise you're using expensive round trips as a retry loop.
</details>

<details>
<summary><b>Q: How do you keep tools secure?</b></summary>

The critical framing is that **tool arguments are untrusted input**. They're generated by a model
whose context may contain user text, retrieved documents or web content — so via prompt injection,
they're effectively attacker-influenceable. You cannot prompt your way to safety.

Concretely: least privilege (read-only, tenant-scoped connections); never accept raw SQL or shell
commands as arguments — use allow-listed, parameterised operations; validate inside the tool, not
in the prompt; allow-list destinations for anything that leaves the system, like email recipients;
resolve-then-verify for filesystem paths to prevent traversal; human approval for irreversible
actions; and log every call with its arguments for the audit trail.

The mental model: treat `tool_calls` exactly as you'd treat a form submission from the public
internet.
</details>

<details>
<summary><b>Q: What happens with 30 tools bound to a model?</b></summary>

Two problems. **Cost**: every tool's name, description and JSON schema is in the prompt on every
call — 30 tools is easily 1,500–2,500 tokens of overhead per request, paid whether or not any are
used. **Accuracy**: models confuse similar tools, so selection quality degrades noticeably beyond
roughly 15.

The fix is routing: classify the request with a cheap model, then bind only that category's tools
plus a small always-available set. In practice this cuts input tokens by ~75% *and* improves
selection accuracy, because fewer options means less confusion.

The limitation to acknowledge: cross-category requests ("find my notes and email them") break a
single-label router. You either allow multi-label classification or let the agent request
additional tools mid-run.
</details>

<details>
<summary><b>Q: Can a model call multiple tools at once?</b></summary>

Yes — a single AI message can contain several `tool_calls`, and you should execute those in
parallel since the model emitted them together, meaning they're independent.

But some sequences are inherently **sequential**: "weather in Lahore in Fahrenheit" requires
`get_weather` first, because the conversion needs a temperature that doesn't exist yet. The model
requests one tool, reads the result, then requests the calculator.

This is why a step limit counts **model round trips**, not tool executions — one round trip may
execute five tools in parallel.
</details>

### Advanced

<details>
<summary><b>Q: Design the tool layer for an agent with access to a production database.</b></summary>

I'd start from the position that the agent must not be able to express a dangerous operation at
all — not that it must be persuaded not to.

**No raw SQL.** The tool takes a query *name* from an enum plus typed parameters, and the SQL
lives in my code, parameterised. That removes SQL injection and unbounded queries in one move. If
the product genuinely needs ad-hoc querying, it goes through a generated-SQL path that is parsed,
validated against an allow-list of tables and operations, forced read-only, and run with a
statement timeout and row cap — and even then I'd want a human in the loop for anything outside
a known shape.

**Connection scoping.** A read-only replica, a role with SELECT on specific tables only, and
tenant scoping injected server-side from the authenticated session — never from a tool argument,
or the model can be talked into reading another tenant's data.

**Result bounding.** Row limits and truncation with an explicit "showing 10 of 4,382" message, so
a broad query can't blow the context window or the bill.

**Writes are a separate tier.** Different tools, human approval via an interrupt, idempotency
keys so a retry can't double-apply, and an audit log recording who approved what.

**Observability.** Every call logged with arguments, duration, row count and the originating
conversation ID. Alert on unusual patterns — a spike in queries or repeated failures often means
either a prompt regression or an injection attempt.

**Testing.** The validation layer gets unit tests including adversarial inputs, because it's the
actual security boundary and it's exactly the kind of code that silently regresses.
</details>

<details>
<summary><b>Q: Your agent keeps choosing the wrong tool. Walk through fixing it.</b></summary>

I'd treat this as a prompt-engineering problem with a measurable target, because that's what it
is — the descriptions *are* the prompt.

**First, build the eval.** A set of questions with the tool that should be selected, including
cases where the answer is *no tool*. Without this you're guessing, and tool selection is exactly
the kind of thing that regresses when someone adds a tool.

**Then look at what's actually being chosen.** The pattern usually tells you the cause:
- **Everything routes to one tool** → its description is too broad, or the others are too vague.
- **Two similar tools get confused** → their descriptions overlap. Make the boundary explicit in
  both ("use X for current data, use Y for historical").
- **It uses a tool when none is needed** → no description says when *not* to use it. Models treat
  an available tool as one they should use unless told otherwise.
- **Right tool, wrong arguments** → the schema needs work: enums instead of free strings,
  descriptions on every field, nullable for genuinely optional values.

**Then reduce the choice.** If there are more than ~15 tools, route by category first. Fewer
options measurably improves selection, independent of description quality.

**Then consider structure.** Merging near-duplicate tools into one with a mode enum often works
better than trying to describe the distinction. And a system-prompt policy ("always use the
calculator for arithmetic") reinforces per-tool descriptions.

**Finally, check the model.** Tool selection varies substantially across models; a smaller model
may simply not be capable of a 15-way choice, in which case routing isn't an optimisation, it's a
requirement.

Throughout, every fixed case goes into the eval set so it can't come back.
</details>

<details>
<summary><b>Q: When should a capability be a tool versus part of the chain?</b></summary>

The deciding question is **who chooses** — the model or you.

Make it part of the chain when the step always happens and its position is known. Retrieval in a
standard RAG pipeline is the clearest example: you always retrieve, then always generate. Putting
it in the chain is cheaper (no tool schema in the prompt, no extra round trip), more predictable,
and easier to test.

Make it a tool when the decision depends on the request. Should we search the web? Query the
database? Look at a file? If the answer varies per request and the model is best placed to judge,
it's a tool.

The interesting middle case is **retrieval as a tool** — Agentic RAG. That's the right choice when
the model should decide *whether* to retrieve (skipping it for greetings), *what* to search for
(reformulating), and *whether to search again* after seeing poor results. You're paying extra
round trips for adaptivity, which is worth it when retrieval quality is inconsistent and not
worth it when it's reliable.

The trade-off in one line: chains give you predictable cost and latency and easy testing; tools
give you adaptivity at the price of unbounded steps and harder evaluation. Default to the chain,
and promote a step to a tool when you find yourself wanting the model to make that call.
</details>

---

## 10. Recap

- ✅ A tool = name + **description** + schema; the model never sees your code
- ✅ **Descriptions are prompts** — say what, when, and *when not*
- ✅ The model *requests*; your code *executes*; results go back as `ToolMessage`
- ✅ Always bound the loop; always push the AI message verbatim before tool results
- ✅ **Return errors to the model**, actionably — it can recover
- ✅ Execute a message's tool calls in parallel; sequences happen across round trips
- ✅ `ToolNode` is the prebuilt executor — Day 17 wires it into a graph
- ✅ Tool arguments are **untrusted input** — validate, scope, allow-list, resolve-then-verify
- ✅ Above ~15 tools, route — it cuts tokens ~75% *and* improves accuracy

### Tomorrow

**[Day 16 — Agents from first principles](day-16-agents.md)**: you now have tools and a loop.
Tomorrow you build a **ReAct agent by hand in about 40 lines**, understand the reasoning trace
that makes it work, then compare against `createAgent` / `create_react_agent` — so the prebuilt
is never a black box.

### Quick self-check

1. Your tool throws an exception on bad input. What happens to the agent, and what should you do instead?
2. Why does a 30-tool agent perform worse than a 5-tool agent, in two distinct ways?
3. A model emits `read_file("../../.env")`. What stopped it — the prompt or the code?

<details>
<summary>Answers</summary>

1. The exception propagates and **kills the loop** — the user gets an error instead of an answer.
   Instead, catch it and return an actionable error string as the tool result, so the model can
   read it and adapt (retry with a corrected argument, use a different tool, or explain the
   limitation).
2. **Cost**: all 30 schemas are in the prompt on every call — 1,500+ tokens of overhead per
   request whether used or not. **Accuracy**: models confuse similar tools, so selection quality
   degrades. Routing fixes both simultaneously.
3. **The code** — specifically a resolve-then-verify check confirming the path is still inside the
   sandbox. Prompt instructions cannot prevent this, because tool arguments are influenced by
   untrusted text (a poisoned document can induce the call). The security boundary is in your
   validation function, where it can be unit-tested.
</details>
