# Day 16 — Agents From First Principles: Build ReAct by Hand

> ⏱ **Time:** ~2.5 hours · 🎯 **Prereqs:** [Day 15](day-15-tools.md) · 🧩 **Difficulty:** ●●●○○

**Today you learn:** what an agent actually is, by building one from nothing. The ReAct loop,
the agent lifecycle, why the reasoning trace matters, the failure modes that kill agents in
production — and only then, the prebuilt `createAgent` / `create_agent`, so it's never a black box.

---

## 1. The problem

Yesterday's tool loop works. But look at what it *can't* decide:

```
   "What's the weather in Lahore?"
   → get_weather(Lahore) → answer                      ✅ one obvious step

   "Which of our customers spent the most, and is it raining there?"
   → ??? which tool first?
     → query_orders → acme spent 360
     → but I need acme's CITY, which isn't in that result
     → query_orders again with a different query?
     → then get_weather(that city)
     → then answer
```

Four steps, and **step 3 depends on what step 2 returned**. You cannot write that sequence in
advance because you don't know acme is the top customer until you've asked.

```
   A CHAIN               YOU decide the steps, before running
   AN AGENT              THE MODEL decides the steps, while running
```

That's the entire distinction. Everything else today follows from it.

---

## 2. Mental model

### The ReAct loop

```
                   ┌──────────────────────────────┐
                   │        THE AGENT LOOP        │
                   └──────────────────────────────┘

   question
      │
      ▼
   ┌────────┐  "I need the top customer. I should query orders."
   │ REASON │  ← the model thinks about what to do next
   └────────┘
      │
      ▼
   ┌────────┐  query_orders(by_revenue)
   │  ACT   │  ← emits a tool call
   └────────┘
      │
      ▼
   ┌────────┐  [{"customer":"acme","total":360}]
   │OBSERVE │  ← YOUR code runs it, result goes back
   └────────┘
      │
      ├──── need more? ──── yes ──┐
      │                            │
      no                           └──▶ back to REASON  ↺
      │
      ▼
   final answer
```

**Reason → Act → Observe, repeated.** That's ReAct (Yao et al., 2022), and it's the foundation
of every tool-using agent you'll meet.

### Where the intelligence lives

```
   ┌─────────────────────────────────────────────────────────────┐
   │  THE MODEL decides:                                         │
   │    · which tool to call                                     │
   │    · what arguments to pass                                 │
   │    · whether it has enough information to answer            │
   │    · when to stop                                           │
   ├─────────────────────────────────────────────────────────────┤
   │  YOUR CODE decides:                                         │
   │    · the maximum number of steps        ← safety            │
   │    · what happens on error              ← recovery          │
   │    · which tools are even available     ← authorisation     │
   │    · whether an action needs approval   ← the real boundary │
   └─────────────────────────────────────────────────────────────┘
```

The model is the *planner*. Your code is the *runtime*. Confusing the two is where agents go wrong.

### Two implementations of the same idea

```
   TEXT ReAct (2022)                    NATIVE TOOL CALLING (today)
   ─────────────────                    ───────────────────────────
   model writes:                        model emits structured:
     Thought: I need X                    tool_calls: [{name, args, id}]
     Action: search[X]
   you PARSE the text                   you READ a field
   you inject "Observation: ..."        you append a ToolMessage

   ❌ brittle regex                      ✅ typed, validated
   ❌ needs a stop sequence              ✅ generation stops naturally
   ✅ works with ANY model               ❌ needs tool-calling support
```

Both are ReAct. Today you build both — the text version because it makes the *mechanism* visible,
the native version because it's what you'll ship.

### The failure modes

```
   🔁 LOOPING          calls the same tool with the same args forever
   🎯 WRONG TOOL       picks badly → bad answer, or wasted steps
   🛑 PREMATURE STOP   answers before gathering enough
   💸 STEP EXPLOSION   15 steps for a 2-step question
   👻 HALLUCINATED     claims a tool result it never received
```

Every one has a specific mitigation, and you'll implement all five.

---

## 3. First principles

### 3.1 What makes it an agent

Not the framework. Not the prompt. **The loop with model-chosen control flow.**

```js
// This is an agent. That's genuinely all it takes.
while (true) {
  const decision = await model.invoke(history);   // model REASONS
  if (!decision.tool_calls) return decision.text; // model decided to STOP
  const results = await execute(decision.tool_calls);  // your code ACTS
  history.push(decision, ...results);             // model OBSERVES next iteration
}
```

Add a step limit and error handling and you have a production agent. Everything else —
LangGraph, multi-agent systems, human-in-the-loop — is structure *around* this loop.

### 3.2 The agent lifecycle

```
   ┌──────────────────────────────────────────────────────────────┐
   │ 1. INITIALISE   system prompt + tools + user question        │
   │ 2. PLAN         model decides: tool call, or final answer?   │
   │ 3. EXECUTE      your code runs the tool(s)                   │
   │ 4. OBSERVE      results appended as ToolMessages             │
   │ 5. REFLECT      model reads results, decides what's next     │
   │ 6. LOOP         → step 2, until answer or limit              │
   │ 7. RESPOND      final answer, ideally with the trace         │
   └──────────────────────────────────────────────────────────────┘
```

Steps 2 and 5 are the same model call — the model plans *and* reflects in one pass. That's why
the reasoning trace matters: it's the only window into step 5.

### 3.3 Why the reasoning trace helps

In text ReAct, the model writes its thinking. That isn't decoration — it's Day 02's
chain-of-thought applied to tool selection:

```
   ❌ straight to action
      Action: search[customer revenue]          ← may be the wrong search

   ✅ reasoning first
      Thought: I need the highest-spending customer. The orders table has
               totals per order, so I need to aggregate by customer first.
      Action: query_orders[by_customer_totals]  ← better-formed
```

**Tokens are compute** (Day 01). Reasoning tokens before an action measurably improve tool
choice and argument quality.

With native tool calling the model doesn't write a visible thought by default — but you can ask
for one, and modern agent implementations often do.

### 3.4 The system prompt for an agent

An agent's system prompt has jobs a chat prompt doesn't:

```
You are a research assistant with access to tools.

PROCESS:
- Think about what information you need before acting.
- Use tools to gather facts. Never guess at data a tool can provide.
- ALWAYS use the calculator for arithmetic, however simple.
- If a tool returns an error, read it and adapt. Do not repeat a failing call.
- When you have enough information, answer. Do not call tools unnecessarily.

CONSTRAINTS:
- If you cannot answer with the available tools, say so plainly.
- Never claim a tool result you did not receive.
```

Three things earn their place: **"never guess at data a tool can provide"** (stops premature
answers), **"do not repeat a failing call"** (stops loops), and **"never claim a result you did
not receive"** (stops hallucinated observations).

### 3.5 Bounding the loop, properly

A step limit is the minimum. Production agents need more:

| Guard | Why |
|---|---|
| `maxSteps` | Hard stop on runaway loops |
| **Repeat detection** | Same tool + same args twice → intervene |
| Token budget | Cost ceiling independent of steps |
| Wall-clock timeout | The user's request has already timed out |
| Per-tool call caps | One tool called 8 times is usually a bug |

**Repeat detection is the one people skip**, and it's the most common real failure. When the
model calls `search("X")` three times identically, it's stuck — inject a message telling it so:

```js
if (seen.has(signature)) {
  content = `You already called ${name} with these exact arguments and got the same result. ` +
            `Try different arguments, a different tool, or answer with what you have.`;
}
```

That single message resolves most loops.

### 3.6 The prebuilt agents

Once you understand the loop, use the prebuilt:

```js
import { createAgent } from "langchain";
const agent = createAgent({ model, tools, systemPrompt: "You are a helpful assistant." });
const result = await agent.invoke({ messages: [{ role: "user", content: question }] });
```

```python
from langchain.agents import create_agent
agent = create_agent(model, tools, system_prompt="You are a helpful assistant.")
result = agent.invoke({"messages": [{"role": "user", "content": question}]})
```

> ⚠️ **`systemPrompt` / `system_prompt`, not `prompt`.** Many tutorials pass `prompt`. On
> current LangChain 1.x, Python's `create_agent(..., prompt=...)` raises `TypeError: create_agent()
> got an unexpected keyword argument 'prompt'` — and JavaScript's `createAgent({ prompt })` is
> worse: it **silently ignores** the option, so the agent runs with no system message at all
> (verified: the model's first message was the user's). If an agent seems to ignore its
> instructions, check this first.

There's also LangGraph's `create_react_agent` / `createReactAgent` from `langgraph.prebuilt`,
which is the graph-native version. Both are the loop you're about to build, compiled into a
graph — which is why Day 17 follows today.

> 🔑 **`create_agent` (LangChain 1.x) vs `create_react_agent` (LangGraph):** they're closely
> related; `create_agent` is the newer LangChain-level API with middleware support, and
> `create_react_agent` is the LangGraph prebuilt. Both return a compiled graph you can invoke,
> stream and checkpoint. Use `create_agent` for new LangChain work.

---

## 4. Code — JavaScript

```bash
npm install langchain @langchain/core @langchain/langgraph @langchain/groq zod dotenv
```

### 4.1 Shared tools

```js
// day16-tools.js
import * as z from "zod";
import { tool } from "@langchain/core/tools";

const ORDERS = [
  { id: 1, customer: "acme",    total: 240, city: "Lahore", date: "2024-06-01" },
  { id: 2, customer: "globex",  total: 890, city: "London", date: "2024-06-01" },
  { id: 3, customer: "acme",    total: 120, city: "Lahore", date: "2024-06-02" },
  { id: 4, customer: "initech", total: 450, city: "Tokyo",  date: "2024-06-03" },
  { id: 5, customer: "globex",  total: 310, city: "London", date: "2024-06-04" },
];

const WEATHER = {
  lahore: { tempC: 34, condition: "hazy sunshine" },
  london: { tempC: 12, condition: "light rain" },
  tokyo:  { tempC: 19, condition: "clear" },
};

export const queryOrders = tool(
  async ({ queryName, customer }) => {
    if (queryName === "totals_by_customer") {
      const totals = {};
      for (const o of ORDERS) totals[o.customer] = (totals[o.customer] ?? 0) + o.total;
      return JSON.stringify(
        Object.entries(totals).map(([c, t]) => ({ customer: c, total: t }))
                              .sort((a, b) => b.total - a.total)
      );
    }
    if (queryName === "customer_details") {
      if (!customer) return "Error: 'customer' is required for customer_details.";
      const rows = ORDERS.filter((o) => o.customer === customer);
      if (!rows.length) {
        return `No customer "${customer}". Known: ${[...new Set(ORDERS.map(o => o.customer))].join(", ")}`;
      }
      return JSON.stringify({ customer, city: rows[0].city, orders: rows.length });
    }
    return JSON.stringify(ORDERS);
  },
  {
    name: "query_orders",
    description:
      "Query the orders database. Use 'totals_by_customer' to find spending per customer " +
      "(sorted highest first), 'customer_details' to get a customer's city and order count, " +
      "or 'all' for every order.",
    schema: z.object({
      queryName: z.enum(["totals_by_customer", "customer_details", "all"]),
      customer: z.string().nullable().describe("Required for customer_details"),
    }),
  }
);

export const getWeather = tool(
  async ({ city }) => {
    const d = WEATHER[city.toLowerCase().trim()];
    return d ? JSON.stringify({ city, ...d })
             : `No weather for "${city}". Available: ${Object.keys(WEATHER).join(", ")}`;
  },
  {
    name: "get_weather",
    description: "Get the current weather for a city.",
    schema: z.object({ city: z.string().describe("City name") }),
  }
);

export const calculator = tool(
  async ({ expression }) => {
    if (!/^[\d\s+\-*/().%]+$/.test(expression)) return "Error: invalid characters.";
    try { return `${expression} = ${eval(expression)}`; }
    catch { return `Error: '${expression}' is not valid arithmetic.`; }
  },
  {
    name: "calculator",
    description: "Evaluate arithmetic. ALWAYS use for any calculation, however simple.",
    schema: z.object({ expression: z.string() }),
  }
);

export const TOOLS = [queryOrders, getWeather, calculator];
```

### 4.2 ReAct by hand — the text version

This makes the mechanism visible. It's how ReAct worked before native tool calling.

```js
// day16-react-text.js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });

// Plain functions — no tool wrapper, to show there's no magic
const ACTIONS = {
  query_orders: (input) => {
    if (input.includes("totals")) {
      return JSON.stringify([
        { customer: "globex", total: 1200 },
        { customer: "acme", total: 360 },
        { customer: "initech", total: 450 },
      ]);
    }
    if (input.includes("globex")) return JSON.stringify({ customer: "globex", city: "London" });
    if (input.includes("acme")) return JSON.stringify({ customer: "acme", city: "Lahore" });
    return "Unknown query. Try 'totals' or a customer name.";
  },
  get_weather: (input) => {
    const w = { lahore: "34°C hazy", london: "12°C light rain", tokyo: "19°C clear" };
    const key = Object.keys(w).find((k) => input.toLowerCase().includes(k));
    return key ? `${input}: ${w[key]}` : `No weather for "${input}".`;
  },
  calculator: (input) =>
    /^[\d\s+\-*/().%]+$/.test(input) ? String(eval(input)) : "Error: invalid expression",
};

const SYSTEM = `Answer the question using this EXACT format:

Thought: <what you need and why>
Action: <tool_name>[<input>]

Then STOP. The system will reply with an Observation. Continue reasoning.

When you have the answer:

Thought: I now know the final answer.
Final Answer: <your answer>

Available actions:
  query_orders[query]    - 'totals' for spending per customer, or a customer name for details
  get_weather[city]      - current weather for a city
  calculator[expression] - arithmetic

Rules:
- Never write an Observation yourself. The system provides them.
- Never repeat an identical Action.`;

async function reactText(question, maxSteps = 8) {
  const messages = [
    { role: "system", content: SYSTEM },
    { role: "user", content: `Question: ${question}` },
  ];
  const seen = new Set();

  for (let step = 1; step <= maxSteps; step++) {
    const res = await model.invoke(messages, { stop: ["Observation:"] });
    //                                          ↑ CRITICAL: without this the model
    //                                            invents its own observations
    const text = res.text.trim();
    console.log(`\n── step ${step} ──\n${text}`);
    messages.push({ role: "assistant", content: text });

    const final = text.match(/Final Answer:\s*(.+)/s);
    if (final) return final[1].trim();

    const action = text.match(/Action:\s*(\w+)\[(.*?)\]/s);
    if (!action) return "⚠️ No Action and no Final Answer — the model broke format.";

    const [, name, input] = action;
    const signature = `${name}:${input}`;

    let observation;
    if (seen.has(signature)) {
      observation = `You already ran ${name}[${input}] and got the same result. ` +
                    `Try something different, or give your Final Answer.`;
    } else {
      seen.add(signature);
      observation = ACTIONS[name]
        ? ACTIONS[name](input)
        : `Error: unknown action "${name}". Available: ${Object.keys(ACTIONS).join(", ")}`;
    }

    console.log(`Observation: ${observation}`);
    messages.push({ role: "user", content: `Observation: ${observation}` });
  }
  return "⚠️ Hit the step limit.";
}

console.log("\n🏁 " + await reactText(
  "Which customer spent the most, and what's the weather where they are?"
));
```

**Read the trace.** You'll see the model reason its way to `query_orders[totals]`, discover
globex, realise it needs globex's city, query again, then check London's weather. **Nobody
programmed that sequence.**

### 4.3 ReAct with native tool calling — what you'll actually ship

```js
// day16-react-native.js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";
import { HumanMessage, SystemMessage, ToolMessage } from "@langchain/core/messages";
import { TOOLS } from "./day16-tools.js";

const BY_NAME = Object.fromEntries(TOOLS.map((t) => [t.name, t]));
const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 })
  .bindTools(TOOLS);

const SYSTEM = new SystemMessage(
  "You are a data assistant with tools.\n\n" +
  "PROCESS:\n" +
  "- Think about what information you need before acting.\n" +
  "- Never guess at data a tool can provide.\n" +
  "- ALWAYS use the calculator for arithmetic, however simple.\n" +
  "- If a tool errors, read it and adapt. Do not repeat a failing call.\n" +
  "- Answer once you have enough information.\n\n" +
  "CONSTRAINTS:\n" +
  "- If the tools cannot answer, say so plainly.\n" +
  "- Never claim a tool result you did not receive."
);

async function agent(question, { maxSteps = 8, maxTokens = 20_000 } = {}) {
  const messages = [SYSTEM, new HumanMessage(question)];
  const trace = [];
  const seen = new Set();
  let tokensUsed = 0;

  for (let step = 1; step <= maxSteps; step++) {
    const ai = await model.invoke(messages);
    messages.push(ai);
    tokensUsed += ai.usage_metadata?.total_tokens ?? 0;

    // ── guard: token budget ─────────────────────────────────────────────
    if (tokensUsed > maxTokens) {
      return { answer: "⚠️ Token budget exceeded.", trace, steps: step, tokensUsed };
    }

    // ── the model decided to stop ───────────────────────────────────────
    if (!ai.tool_calls?.length) {
      return { answer: ai.text, trace, steps: step, tokensUsed };
    }

    // ── execute in parallel ─────────────────────────────────────────────
    const results = await Promise.all(ai.tool_calls.map(async (call) => {
      const signature = `${call.name}:${JSON.stringify(call.args)}`;

      let content;
      if (seen.has(signature)) {
        // ── guard: repeat detection ───────────────────────────────────
        content = `You already called ${call.name} with these exact arguments and got the ` +
                  `same result. Try different arguments, another tool, or answer with what ` +
                  `you have.`;
        trace.push({ step, name: call.name, args: call.args, result: "🔁 REPEAT BLOCKED" });
      } else {
        seen.add(signature);
        try {
          content = String(await BY_NAME[call.name].invoke(call.args));
        } catch (e) {
          content = `Error: ${e.message}`;
        }
        trace.push({ step, name: call.name, args: call.args, result: content.slice(0, 55) });
      }

      return new ToolMessage({ content, tool_call_id: call.id });
    }));

    messages.push(...results);
  }

  return { answer: "⚠️ Hit the step limit.", trace, steps: maxSteps, tokensUsed };
}

for (const q of [
  "Which customer spent the most, and what's the weather where they are?",
  "What's the total revenue across all customers, and what is 20% of that?",
  "What's the weather on Mars?",
]) {
  console.log(`\n${"═".repeat(74)}\n❓ ${q}\n${"═".repeat(74)}`);
  const r = await agent(q);
  r.trace.forEach((t) =>
    console.log(`  [${t.step}] 🔧 ${t.name}(${JSON.stringify(t.args)})\n      → ${t.result}`));
  console.log(`\n  💬 ${r.answer}`);
  console.log(`  (${r.steps} model calls · ${r.tokensUsed} tokens)`);
}
```

### 4.4 The prebuilt agent

```js
// day16-prebuilt.js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";
import { createAgent } from "langchain";
import { TOOLS } from "./day16-tools.js";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });

const agent = createAgent({
  model,
  tools: TOOLS,
  systemPrompt: "You are a data assistant. Use tools for all facts and arithmetic. " +
          "Never guess at data a tool can provide.",
});

const result = await agent.invoke({
  messages: [{ role: "user", content: "Which customer spent the most, and what's the weather there?" }],
});

// The full message history — every reasoning step and tool result
for (const m of result.messages) {
  const type = m.getType();
  if (type === "human") console.log(`\n👤 ${m.content}`);
  else if (type === "tool") console.log(`   ← ${String(m.content).slice(0, 70)}`);
  else if (m.tool_calls?.length) {
    m.tool_calls.forEach((c) => console.log(`   🔧 ${c.name}(${JSON.stringify(c.args)})`));
  } else console.log(`\n🤖 ${m.text}`);
}
```

<details>
<summary>🔧 The LangGraph prebuilt (<code>createReactAgent</code>)</summary>

```js
import { createReactAgent } from "@langchain/langgraph/prebuilt";
import { MemorySaver } from "@langchain/langgraph";

const agent = createReactAgent({
  llm: model,
  tools: TOOLS,
  checkpointer: new MemorySaver(),      // ← conversation persistence for free
});

const result = await agent.invoke(
  { messages: [{ role: "user", content: "..." }] },
  { configurable: { thread_id: "user-1" } }
);
```

This returns a **compiled graph**, which means it streams, checkpoints, and supports interrupts.
That's Days 17–21.
</details>

---

## 5. Code — Python

```bash
pip install langchain langgraph langchain-groq pydantic python-dotenv
```

### 5.1 Shared tools

```python
# day16_tools.py
import json, re
from typing import Literal, Optional
from langchain_core.tools import tool

ORDERS = [
    {"id": 1, "customer": "acme",    "total": 240, "city": "Lahore", "date": "2024-06-01"},
    {"id": 2, "customer": "globex",  "total": 890, "city": "London", "date": "2024-06-01"},
    {"id": 3, "customer": "acme",    "total": 120, "city": "Lahore", "date": "2024-06-02"},
    {"id": 4, "customer": "initech", "total": 450, "city": "Tokyo",  "date": "2024-06-03"},
    {"id": 5, "customer": "globex",  "total": 310, "city": "London", "date": "2024-06-04"},
]

WEATHER = {
    "lahore": {"tempC": 34, "condition": "hazy sunshine"},
    "london": {"tempC": 12, "condition": "light rain"},
    "tokyo":  {"tempC": 19, "condition": "clear"},
}

@tool
def query_orders(
    query_name: Literal["totals_by_customer", "customer_details", "all"],
    customer: Optional[str] = None,
) -> str:
    """Query the orders database.

    Use 'totals_by_customer' to find spending per customer (sorted highest first),
    'customer_details' to get a customer's city and order count, or 'all' for every order.

    Args:
        query_name: Which query to run.
        customer: Required for customer_details.
    """
    if query_name == "totals_by_customer":
        totals = {}
        for o in ORDERS:
            totals[o["customer"]] = totals.get(o["customer"], 0) + o["total"]
        rows = sorted(({"customer": c, "total": t} for c, t in totals.items()),
                      key=lambda r: -r["total"])
        return json.dumps(rows)

    if query_name == "customer_details":
        if not customer:
            return "Error: 'customer' is required for customer_details."
        rows = [o for o in ORDERS if o["customer"] == customer]
        if not rows:
            known = ", ".join(sorted({o["customer"] for o in ORDERS}))
            return f'No customer "{customer}". Known: {known}'
        return json.dumps({"customer": customer, "city": rows[0]["city"], "orders": len(rows)})

    return json.dumps(ORDERS)

@tool
def get_weather(city: str) -> str:
    """Get the current weather for a city.

    Args:
        city: City name.
    """
    d = WEATHER.get(city.lower().strip())
    if not d:
        return f'No weather for "{city}". Available: {", ".join(WEATHER)}'
    return json.dumps({"city": city, **d})

@tool
def calculator(expression: str) -> str:
    """Evaluate arithmetic. ALWAYS use for any calculation, however simple.

    Args:
        expression: e.g. '(240 + 890) * 0.2'
    """
    if not re.fullmatch(r"[\d\s+\-*/().%]+", expression):
        return "Error: invalid characters."
    try:
        return f"{expression} = {eval(expression)}"
    except Exception:
        return f"Error: '{expression}' is not valid arithmetic."

TOOLS = [query_orders, get_weather, calculator]
```

### 5.2 ReAct by hand — the text version

```python
# day16_react_text.py
import json, re
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

# Plain functions — no tool wrapper, to show there's no magic
def _query_orders(inp):
    if "totals" in inp:
        return json.dumps([
            {"customer": "globex", "total": 1200},
            {"customer": "acme", "total": 360},
            {"customer": "initech", "total": 450},
        ])
    if "globex" in inp:
        return json.dumps({"customer": "globex", "city": "London"})
    if "acme" in inp:
        return json.dumps({"customer": "acme", "city": "Lahore"})
    return "Unknown query. Try 'totals' or a customer name."

def _get_weather(inp):
    w = {"lahore": "34°C hazy", "london": "12°C light rain", "tokyo": "19°C clear"}
    key = next((k for k in w if k in inp.lower()), None)
    return f"{inp}: {w[key]}" if key else f'No weather for "{inp}".'

ACTIONS = {
    "query_orders": _query_orders,
    "get_weather": _get_weather,
    "calculator": lambda i: (str(eval(i)) if re.fullmatch(r"[\d\s+\-*/().%]+", i)
                             else "Error: invalid expression"),
}

SYSTEM = """Answer the question using this EXACT format:

Thought: <what you need and why>
Action: <tool_name>[<input>]

Then STOP. The system will reply with an Observation. Continue reasoning.

When you have the answer:

Thought: I now know the final answer.
Final Answer: <your answer>

Available actions:
  query_orders[query]    - 'totals' for spending per customer, or a customer name for details
  get_weather[city]      - current weather for a city
  calculator[expression] - arithmetic

Rules:
- Never write an Observation yourself. The system provides them.
- Never repeat an identical Action."""

def react_text(question, max_steps=8):
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Question: {question}"},
    ]
    seen = set()

    for step in range(1, max_steps + 1):
        res = model.invoke(messages, stop=["Observation:"])
        #                              ↑ CRITICAL: without this the model
        #                                invents its own observations
        text = res.content.strip()
        print(f"\n── step {step} ──\n{text}")
        messages.append({"role": "assistant", "content": text})

        final = re.search(r"Final Answer:\s*(.+)", text, re.S)
        if final:
            return final.group(1).strip()

        action = re.search(r"Action:\s*(\w+)\[(.*?)\]", text, re.S)
        if not action:
            return "⚠️ No Action and no Final Answer — the model broke format."

        name, inp = action.group(1), action.group(2)
        signature = f"{name}:{inp}"

        if signature in seen:
            observation = (f"You already ran {name}[{inp}] and got the same result. "
                           f"Try something different, or give your Final Answer.")
        else:
            seen.add(signature)
            observation = (ACTIONS[name](inp) if name in ACTIONS
                           else f'Error: unknown action "{name}". '
                                f'Available: {", ".join(ACTIONS)}')

        print(f"Observation: {observation}")
        messages.append({"role": "user", "content": f"Observation: {observation}"})

    return "⚠️ Hit the step limit."

print("\n🏁 " + react_text(
    "Which customer spent the most, and what's the weather where they are?"))
```

### 5.3 ReAct with native tool calling

```python
# day16_react_native.py
import json
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from day16_tools import TOOLS

load_dotenv()

BY_NAME = {t.name: t for t in TOOLS}
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0).bind_tools(TOOLS)

SYSTEM = SystemMessage(
    "You are a data assistant with tools.\n\n"
    "PROCESS:\n"
    "- Think about what information you need before acting.\n"
    "- Never guess at data a tool can provide.\n"
    "- ALWAYS use the calculator for arithmetic, however simple.\n"
    "- If a tool errors, read it and adapt. Do not repeat a failing call.\n"
    "- Answer once you have enough information.\n\n"
    "CONSTRAINTS:\n"
    "- If the tools cannot answer, say so plainly.\n"
    "- Never claim a tool result you did not receive."
)

def agent(question, max_steps=8, max_tokens=20_000):
    messages = [SYSTEM, HumanMessage(question)]
    trace, seen, tokens_used = [], set(), 0

    for step in range(1, max_steps + 1):
        ai = model.invoke(messages)
        messages.append(ai)
        tokens_used += (ai.usage_metadata or {}).get("total_tokens", 0)

        # ── guard: token budget ─────────────────────────────────────────
        if tokens_used > max_tokens:
            return {"answer": "⚠️ Token budget exceeded.", "trace": trace,
                    "steps": step, "tokens": tokens_used}

        # ── the model decided to stop ───────────────────────────────────
        if not ai.tool_calls:
            return {"answer": ai.content, "trace": trace,
                    "steps": step, "tokens": tokens_used}

        for call in ai.tool_calls:
            signature = f"{call['name']}:{json.dumps(call['args'], sort_keys=True)}"

            if signature in seen:
                # ── guard: repeat detection ─────────────────────────────
                content = (f"You already called {call['name']} with these exact arguments "
                           f"and got the same result. Try different arguments, another tool, "
                           f"or answer with what you have.")
                trace.append({"step": step, "name": call["name"],
                              "args": call["args"], "result": "🔁 REPEAT BLOCKED"})
            else:
                seen.add(signature)
                try:
                    content = str(BY_NAME[call["name"]].invoke(call["args"]))
                except Exception as e:
                    content = f"Error: {e}"
                trace.append({"step": step, "name": call["name"],
                              "args": call["args"], "result": content[:55]})

            messages.append(ToolMessage(content=content, tool_call_id=call["id"]))

    return {"answer": "⚠️ Hit the step limit.", "trace": trace,
            "steps": max_steps, "tokens": tokens_used}

for q in [
    "Which customer spent the most, and what's the weather where they are?",
    "What's the total revenue across all customers, and what is 20% of that?",
    "What's the weather on Mars?",
]:
    print(f"\n{'═' * 74}\n❓ {q}\n{'═' * 74}")
    r = agent(q)
    for t in r["trace"]:
        print(f"  [{t['step']}] 🔧 {t['name']}({t['args']})\n      → {t['result']}")
    print(f"\n  💬 {r['answer']}")
    print(f"  ({r['steps']} model calls · {r['tokens']} tokens)")
```

### 5.4 The prebuilt agent

```python
# day16_prebuilt.py
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain.agents import create_agent
from day16_tools import TOOLS

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

agent = create_agent(
    model,
    TOOLS,
    system_prompt="You are a data assistant. Use tools for all facts and arithmetic. "
           "Never guess at data a tool can provide.",
)

result = agent.invoke({
    "messages": [{"role": "user",
                  "content": "Which customer spent the most, and what's the weather there?"}]
})

# The full message history — every reasoning step and tool result
for m in result["messages"]:
    if m.type == "human":
        print(f"\n👤 {m.content}")
    elif m.type == "tool":
        print(f"   ← {str(m.content)[:70]}")
    elif getattr(m, "tool_calls", None):
        for c in m.tool_calls:
            print(f"   🔧 {c['name']}({c['args']})")
    else:
        print(f"\n🤖 {m.content}")
```

<details>
<summary>🔧 The LangGraph prebuilt (<code>create_react_agent</code>)</summary>

```python
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import InMemorySaver

agent = create_react_agent(
    model, TOOLS,
    checkpointer=InMemorySaver(),      # ← conversation persistence for free
)

result = agent.invoke(
    {"messages": [{"role": "user", "content": "..."}]},
    config={"configurable": {"thread_id": "user-1"}},
)
```

This returns a **compiled graph** — it streams, checkpoints, and supports interrupts. Days 17–21.
</details>

### 🔁 JS ↔ Python differences you just saw

| | JavaScript | Python |
|---|---|---|
| Prebuilt (LangChain) | `createAgent({ model, tools, systemPrompt })` | `create_agent(model, tools, system_prompt=...)` |
| Prebuilt (LangGraph) | `createReactAgent({ llm, tools, checkpointer })` | `create_react_agent(model, tools, checkpointer=...)` |
| Stop sequence | `model.invoke(msgs, { stop: ["Observation:"] })` | `model.invoke(msgs, stop=["Observation:"])` |
| Tool call fields | `call.name`, `call.args`, `call.id` | `call["name"]`, `call["args"]`, `call["id"]` ⚠️ |
| Message type | `m.getType()` | `m.type` |
| Result shape | `result.messages` | `result["messages"]` |
| Regex dotall | `/.../s` | `re.S` |

---

## 6. Under the hood

### What `createAgent` actually builds

```
createAgent({ model, tools, systemPrompt })
        │
        ▼
   a compiled StateGraph:

        START
          │
          ▼
     ┌─────────┐
     │  agent  │  model.bindTools(tools).invoke(state.messages)
     └─────────┘
          │
     tool_calls? ──── no ──▶ END
          │ yes
          ▼
     ┌─────────┐
     │  tools  │  ToolNode — runs them all, returns ToolMessages
     └─────────┘
          │
          └────────▶ back to `agent`  ↺
```

**That's your loop, expressed as a graph.** Two nodes and a conditional edge. You'll build this
exact graph tomorrow, by hand, in about 20 lines — and then everything the prebuilt does will be
visible.

The reason it's a graph rather than a `while` loop is what the graph gives you *for free*:
checkpointing between steps, streaming of intermediate state, interrupts before tool execution,
and time travel. Those are Days 17–21.

### Why the stop sequence is essential in text ReAct

The model has seen thousands of complete ReAct traces in training. After writing an `Action:`
line, it will cheerfully continue:

```
Action: query_orders[totals]
Observation: globex spent $50,000        ← COMPLETELY INVENTED
Thought: So globex is the top customer...
```

It's just continuing a pattern. `stop: ["Observation:"]` forcibly hands control back to your code
at the right moment.

**Native tool calling solves this structurally** — the model was fine-tuned to emit an end-of-turn
token after a tool call, so generation stops on its own. That's the single biggest practical
argument for native tool calling over text ReAct.

### The step-count economics

```
   a 3-tool question:

   model call 1  →  tool_calls: [query_orders]
   model call 2  →  tool_calls: [query_orders]        (needs the city)
   model call 3  →  tool_calls: [get_weather]
   model call 4  →  final answer

   4 MODEL CALLS for one user question.
```

Each call re-sends the entire growing history (Day 01). So an agent's cost is
**super-linear in steps** — not just 4× a single call, because call 4's input includes
everything from calls 1–3.

**Practical consequences:**

- Trim the message history in long-running agents
- Use a smaller model when the task allows — agents multiply the per-call cost
- A step limit is a *cost* control as much as a safety one
- Watch the average step count as a health metric; a rise usually means a tool description
  regressed

### The five failure modes, and what actually fixes them

| Failure | Cause | Fix |
|---|---|---|
| 🔁 Looping | Model can't tell it's repeating | **Repeat detection** + a message saying so |
| 🎯 Wrong tool | Vague descriptions | Better descriptions (Day 15), fewer tools |
| 🛑 Premature stop | Model guesses instead of checking | "Never guess at data a tool can provide" |
| 💸 Step explosion | No feedback on efficiency | Step limit + trace review + tool consolidation |
| 👻 Hallucinated result | Model fabricates an observation | Stop sequence (text) or native tool calling |

**Repeat detection deserves emphasis.** In practice it's the most common runaway, and the fix is
three lines: hash `(name, args)`, and when you see a repeat, return a message telling the model
so rather than the same result again.

<details>
<summary>📜 Legacy note: agent APIs you'll meet in old code</summary>

| Legacy | Modern |
|---|---|
| `initialize_agent(tools, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION)` | `create_agent` / `createAgent` |
| `AgentExecutor(agent=..., tools=...)` | a compiled graph |
| `AgentType.OPENAI_FUNCTIONS` | native tool calling, no agent type needed |
| `ZeroShotAgent` / `ConversationalAgent` | one agent + a system prompt |
| `agent.run("question")` | `agent.invoke({"messages": [...]})` |
| `AgentAction` / `AgentFinish` | `tool_calls` on an `AIMessage`, or its absence |

The old `AgentType` enum existed because different models needed different *formats* — XML
agents, JSON agents, ReAct text agents. Native tool calling collapsed all of them into one
mechanism.

A common interview question is **"what are the different agent types in LangChain?"** The honest,
current answer: they're historical. Modern agents use native tool calling, and the variation that
remains is in *architecture* (single agent, supervisor, hierarchical — Day 22), not in output
format.
</details>

---

## 7. Common mistakes

**❌ No step limit**

The single most expensive bug in agent code. A confused model loops until your budget is gone.
✅ `maxSteps` on every agent, always.

---

**❌ No repeat detection**

The model calls `search("X")` five times identically and never notices.
✅ Hash `(name, args)`; on a repeat, return a message telling it so.

---

**❌ Text ReAct without a stop sequence**

The model writes its own `Observation:` and reasons from invented data.
✅ `stop: ["Observation:"]` — or use native tool calling.

---

**❌ Throwing on tool errors**

Kills the loop; the model never gets a chance to adapt.
✅ Return the error as tool content (Day 15).

---

**❌ Letting history grow unbounded**

Step 8's input contains everything from steps 1–7. Cost is super-linear.
✅ Trim the history, or summarise older tool results.

---

**❌ Using an agent where a chain would do**

If the sequence is always the same, an agent adds latency, cost and unpredictability for nothing.
✅ Agent only when the *next step depends on the previous result*.

---

**❌ No trace**

When an agent misbehaves, the trace is the only diagnostic. Adding it during an incident is too late.
✅ Record every step's tool, arguments and result from day one.

---

**❌ Trusting the final answer over the trace**

An agent can produce a confident answer having received an error from every tool.
✅ Check the trace, and consider surfacing it to the user.

---

## 8. Exercises

### Exercise 1 — Trace a multi-step agent ●●○○○

Run the native ReAct agent on three questions of increasing complexity (1 tool, 2 tools
sequentially, 3+ tools). For each, record the number of model calls, tool calls, and total
tokens. Plot how tokens grow with step count and explain the shape.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";
import { HumanMessage, SystemMessage, ToolMessage } from "@langchain/core/messages";
import { TOOLS } from "./day16-tools.js";

const BY_NAME = Object.fromEntries(TOOLS.map((t) => [t.name, t]));
const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 })
  .bindTools(TOOLS);

const SYSTEM = new SystemMessage(
  "You are a data assistant. Use tools for all facts and arithmetic. " +
  "Never guess at data a tool can provide."
);

async function traced(question, maxSteps = 8) {
  const messages = [SYSTEM, new HumanMessage(question)];
  const perStep = [];

  for (let step = 1; step <= maxSteps; step++) {
    const ai = await model.invoke(messages);
    messages.push(ai);

    const u = ai.usage_metadata ?? {};
    perStep.push({
      step,
      inputTokens: u.input_tokens ?? 0,
      outputTokens: u.output_tokens ?? 0,
      toolCalls: ai.tool_calls?.length ?? 0,
    });

    if (!ai.tool_calls?.length) return { answer: ai.text, perStep };

    const results = await Promise.all(ai.tool_calls.map(async (c) => {
      let content;
      try { content = String(await BY_NAME[c.name].invoke(c.args)); }
      catch (e) { content = `Error: ${e.message}`; }
      return new ToolMessage({ content, tool_call_id: c.id });
    }));
    messages.push(...results);
  }
  return { answer: "⚠️ step limit", perStep };
}

const QUESTIONS = [
  ["1 tool",  "What's the weather in Lahore?"],
  ["2 tools", "What's the total revenue, and what is 20% of it?"],
  ["3+ tools","Which customer spent the most, what's the weather there, and what is that in Fahrenheit?"],
];

for (const [label, q] of QUESTIONS) {
  const r = await traced(q);
  const totalIn = r.perStep.reduce((s, x) => s + x.inputTokens, 0);
  const totalOut = r.perStep.reduce((s, x) => s + x.outputTokens, 0);
  const toolCalls = r.perStep.reduce((s, x) => s + x.toolCalls, 0);

  console.log(`\n═══ ${label}: ${q.slice(0, 55)} ═══`);
  console.log("step  inputTok  outputTok  toolCalls  growth");
  for (const [i, s] of r.perStep.entries()) {
    const growth = i === 0 ? "—" :
      `+${s.inputTokens - r.perStep[i - 1].inputTokens}`;
    console.log(`  ${s.step}   ${String(s.inputTokens).padStart(7)}  ` +
                `${String(s.outputTokens).padStart(8)}  ${String(s.toolCalls).padStart(8)}  ` +
                `${growth.padStart(6)}`);
  }
  console.log(`  TOTAL: ${r.perStep.length} model calls · ${toolCalls} tool calls · ` +
              `${totalIn} in + ${totalOut} out = ${totalIn + totalOut} tokens`);
  console.log(`  💬 ${r.answer.slice(0, 90)}`);
}
```

**Python**
```python
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from day16_tools import TOOLS

load_dotenv()
BY_NAME = {t.name: t for t in TOOLS}
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0).bind_tools(TOOLS)

SYSTEM = SystemMessage(
    "You are a data assistant. Use tools for all facts and arithmetic. "
    "Never guess at data a tool can provide."
)

def traced(question, max_steps=8):
    messages = [SYSTEM, HumanMessage(question)]
    per_step = []

    for step in range(1, max_steps + 1):
        ai = model.invoke(messages)
        messages.append(ai)

        u = ai.usage_metadata or {}
        per_step.append({
            "step": step,
            "input": u.get("input_tokens", 0),
            "output": u.get("output_tokens", 0),
            "tool_calls": len(ai.tool_calls or []),
        })

        if not ai.tool_calls:
            return {"answer": ai.content, "per_step": per_step}

        for c in ai.tool_calls:
            try:
                content = str(BY_NAME[c["name"]].invoke(c["args"]))
            except Exception as e:
                content = f"Error: {e}"
            messages.append(ToolMessage(content=content, tool_call_id=c["id"]))

    return {"answer": "⚠️ step limit", "per_step": per_step}

QUESTIONS = [
    ("1 tool",   "What's the weather in Lahore?"),
    ("2 tools",  "What's the total revenue, and what is 20% of it?"),
    ("3+ tools", "Which customer spent the most, what's the weather there, "
                 "and what is that in Fahrenheit?"),
]

for label, q in QUESTIONS:
    r = traced(q)
    total_in = sum(s["input"] for s in r["per_step"])
    total_out = sum(s["output"] for s in r["per_step"])
    tool_calls = sum(s["tool_calls"] for s in r["per_step"])

    print(f"\n═══ {label}: {q[:55]} ═══")
    print("step  inputTok  outputTok  toolCalls  growth")
    for i, s in enumerate(r["per_step"]):
        growth = "—" if i == 0 else f"+{s['input'] - r['per_step'][i-1]['input']}"
        print(f"  {s['step']}   {s['input']:>7}  {s['output']:>8}  "
              f"{s['tool_calls']:>8}  {growth:>6}")
    print(f"  TOTAL: {len(r['per_step'])} model calls · {tool_calls} tool calls · "
          f"{total_in} in + {total_out} out = {total_in + total_out} tokens")
    print(f"  💬 {r['answer'][:90]}")
```

**Typical output:**

```
═══ 3+ tools: Which customer spent the most, what's the weather there… ═══
step  inputTok  outputTok  toolCalls  growth
  1       412         28          1       —
  2       498         31          1    +86
  3       602         26          1   +104
  4       714         48          0   +112
  TOTAL: 4 model calls · 3 tool calls · 2226 in + 133 out = 2359 tokens
```

**The shape to notice: input tokens grow every step, and the growth *accelerates*.**

Each step appends an AI message plus a tool result to the history, and the *entire* history is
re-sent on the next call. So:

```
   total input tokens ≈ Σ (base + accumulated history at step n)
```

That's the O(n²) pattern from Day 01, now applied to agent steps rather than chat turns.

**Three practical consequences:**

1. **A 4-step agent costs far more than 4× a single call** — closer to 5–6× here, and the ratio
   worsens with more steps and larger tool outputs.
2. **Large tool results are expensive twice over** — once when returned, then again in every
   subsequent step's input. Truncating tool output (Day 15) matters more in agents than in chains.
3. **Step count is your primary cost lever.** Consolidating two tools into one that returns both
   pieces of data saves a whole round trip *and* all the re-sent history that comes with it.

This is why "average steps per query" belongs on your dashboard.
</details>

---

### Exercise 2 — Break the agent five ways ●●●○○

Deliberately induce each failure mode and observe it: (1) remove the step limit and give an
unanswerable question, (2) remove repeat detection, (3) use vague tool descriptions, (4) remove
"never guess" from the prompt, (5) run text ReAct without a stop sequence. Record what each
produces.

<details>
<summary>✅ Solution</summary>

**Python**
```python
# day16_break_it.py
import json, re
from dotenv import load_dotenv
from langchain_core.tools import StructuredTool
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

# ── tools with switchable descriptions ───────────────────────────────────
class SearchArgs(BaseModel):
    query: str = Field(description="Search query")

def _search(query):
    return "No results found."          # always empty — to provoke looping

GOOD_DESC = ("Search the internal knowledge base for company facts. "
             "Use ONLY for company-specific questions. Do NOT use for arithmetic "
             "or general knowledge.")
VAGUE_DESC = "Search"

def make_search(desc):
    return StructuredTool.from_function(
        func=_search, name="search", description=desc, args_schema=SearchArgs)

class CalcArgs(BaseModel):
    expression: str = Field(description="Arithmetic expression")

calculator = StructuredTool.from_function(
    func=lambda expression: (str(eval(expression))
                             if re.fullmatch(r"[\d\s+\-*/().%]+", expression)
                             else "Error: invalid"),
    name="calculator",
    description="Evaluate arithmetic. ALWAYS use for any calculation.",
    args_schema=CalcArgs,
)

STRICT = ("You are an assistant with tools.\n"
          "- Never guess at data a tool can provide.\n"
          "- If a tool errors or returns nothing, adapt. Do not repeat a failing call.\n"
          "- Never claim a tool result you did not receive.")
LOOSE = "You are an assistant with tools."

def run(question, *, tools, system, max_steps=10, repeat_detection=True, verbose=True):
    bound = model.bind_tools(tools)
    by_name = {t.name: t for t in tools}
    messages = [SystemMessage(system), HumanMessage(question)]
    seen, calls = set(), 0

    for step in range(1, max_steps + 1):
        ai = bound.invoke(messages)
        messages.append(ai)

        if not ai.tool_calls:
            return {"answer": ai.content, "steps": step, "tool_calls": calls}

        for c in ai.tool_calls:
            calls += 1
            sig = f"{c['name']}:{json.dumps(c['args'], sort_keys=True)}"

            if repeat_detection and sig in seen:
                content = ("You already made this exact call and got the same result. "
                           "Try something different, or answer with what you have.")
                if verbose: print(f"  [{step}] 🔁 REPEAT BLOCKED {c['name']}({c['args']})")
            else:
                seen.add(sig)
                content = str(by_name[c["name"]].invoke(c["args"]))
                if verbose: print(f"  [{step}] 🔧 {c['name']}({c['args']}) → {content[:40]}")

            messages.append(ToolMessage(content=content, tool_call_id=c["id"]))

    return {"answer": "⚠️ HIT STEP LIMIT", "steps": max_steps, "tool_calls": calls}

rule = lambda t: print(f"\n{'═'*76}\n{t}\n{'═'*76}")

# ── BREAK 1 + 2: no repeat detection, unanswerable question ─────────────
rule("BREAK 1&2 — no repeat detection, unanswerable question")
r = run("What is our company's founding date?",
        tools=[make_search(GOOD_DESC), calculator], system=STRICT,
        repeat_detection=False)
print(f"  → {r['steps']} steps, {r['tool_calls']} tool calls: {r['answer'][:80]}")

rule("FIXED — WITH repeat detection")
r = run("What is our company's founding date?",
        tools=[make_search(GOOD_DESC), calculator], system=STRICT,
        repeat_detection=True)
print(f"  → {r['steps']} steps, {r['tool_calls']} tool calls: {r['answer'][:80]}")

# ── BREAK 3: vague descriptions ─────────────────────────────────────────
rule("BREAK 3 — vague tool description ('Search')")
r = run("What is 847 * 23?", tools=[make_search(VAGUE_DESC), calculator], system=LOOSE)
print(f"  → {r['answer'][:80]}")

rule("FIXED — explicit description with 'do NOT use for arithmetic'")
r = run("What is 847 * 23?", tools=[make_search(GOOD_DESC), calculator], system=LOOSE)
print(f"  → {r['answer'][:80]}")

# ── BREAK 4: no "never guess" instruction ───────────────────────────────
rule("BREAK 4 — loose system prompt, question needing a tool")
r = run("How many orders did customer acme place?",
        tools=[make_search(GOOD_DESC), calculator], system=LOOSE)
print(f"  → {r['tool_calls']} tool calls: {r['answer'][:100]}")

rule("FIXED — strict prompt with 'never guess'")
r = run("How many orders did customer acme place?",
        tools=[make_search(GOOD_DESC), calculator], system=STRICT)
print(f"  → {r['tool_calls']} tool calls: {r['answer'][:100]}")

# ── BREAK 5: text ReAct without a stop sequence ─────────────────────────
rule("BREAK 5 — text ReAct WITHOUT stop sequence")
SYS = """Answer using this format:
Thought: <reasoning>
Action: search[<query>]
Observation: <the system fills this in>
...
Final Answer: <answer>"""

res = model.invoke([{"role": "system", "content": SYS},
                    {"role": "user", "content": "Question: What is our refund policy?"}])
print(res.content[:400])
print("\n  ⚠️  Notice: the model wrote its OWN Observation — that data is invented.")

rule("FIXED — with stop=['Observation:']")
res = model.invoke([{"role": "system", "content": SYS},
                    {"role": "user", "content": "Question: What is our refund policy?"}],
                   stop=["Observation:"])
print(res.content[:400])
print("\n  ✅ Generation stopped before the Observation. Your code fills it in.")
```

**JavaScript** — the same five breaks; the distinctive parts:
```js
// BREAK 2: repeat detection toggled off
const content = (repeatDetection && seen.has(sig))
  ? "You already made this exact call and got the same result. Try something different."
  : String(await byName[c.name].invoke(c.args));

// BREAK 5: stop sequence present vs absent
await model.invoke(messages);                          // ❌ invents Observations
await model.invoke(messages, { stop: ["Observation:"] }); // ✅ stops correctly
```

**What each break produces:**

| Break | Symptom |
|---|---|
| **1&2** no repeat detection | Calls `search({query: "founding date"})` **10 times identically**, hits the step limit, burns ~8 model calls for nothing |
| **1&2** *fixed* | Repeats once, gets told, then answers: *"I couldn't find that in the knowledge base."* — 3 steps |
| **3** vague description | Uses `search` for `847 * 23`, gets "No results", may then answer with a wrong number |
| **3** *fixed* | Goes straight to `calculator` |
| **4** loose prompt | **Zero tool calls** — confidently invents an order count |
| **4** *fixed* | Calls the tool, finds nothing, says so |
| **5** no stop sequence | Model writes `Observation: Our refund policy is 30 days...` — **entirely fabricated** |
| **5** *fixed* | Output ends after the `Action:` line |

**Break 5 is the one to sit with.** The model produces a complete, plausible ReAct trace with
invented observations, and every downstream step reasons from fabricated data. Nothing errors.
The output looks *more* convincing than a correct trace, because it's uninterrupted.

That's precisely why native tool calling replaced text ReAct: generation stops structurally,
not because you remembered a parameter.

**Break 4 is the most common in real systems.** Without an explicit "never guess" instruction,
models frequently answer from parametric knowledge when a tool was available — and you can't
tell from the output that no tool ran. Checking `tool_calls == 0` on questions that require data
is a cheap, effective monitor.
</details>

---

### Exercise 3 — Agent vs chain benchmark ●●●○○

Take one task that's genuinely fixed-sequence (summarise then translate) and one that's genuinely
adaptive (a multi-hop data question). Implement each **both** as a chain and as an agent. Compare
latency, tokens, model calls and correctness, then state when each wins.

<details>
<summary>✅ Solution</summary>

**Python**
```python
# day16_agent_vs_chain.py
import time
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from day16_tools import TOOLS, query_orders, get_weather

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
BY_NAME = {t.name: t for t in TOOLS}
bound = model.bind_tools(TOOLS)

usage = {"calls": 0, "tokens": 0}
def track(res):
    usage["calls"] += 1
    usage["tokens"] += (res.usage_metadata or {}).get("total_tokens", 0)
    return res

def reset():
    usage["calls"] = usage["tokens"] = 0

# ══════════════ TASK A: fixed sequence — summarise then translate ════════
TEXT = ("LangGraph adds stateful, cyclic workflows to LangChain. It provides nodes, edges, "
        "typed state with reducers, checkpointers for persistence, and interrupts for "
        "human-in-the-loop approval. Unlike LCEL, which builds acyclic pipelines, LangGraph "
        "supports loops, which is what agents fundamentally require.")

def task_a_chain():
    summarise = ChatPromptTemplate.from_messages([
        ("human", "Summarise in one sentence:\n\n{text}")]) | model | StrOutputParser()
    translate = ChatPromptTemplate.from_messages([
        ("human", "Translate to French, output only the translation:\n\n{summary}")
    ]) | model | StrOutputParser()

    chain = (RunnablePassthrough.assign(summary=summarise)
             | RunnablePassthrough.assign(french=translate))

    # count usage manually since StrOutputParser drops metadata
    s = track(model.invoke(f"Summarise in one sentence:\n\n{TEXT}")).content
    f = track(model.invoke(f"Translate to French, output only the translation:\n\n{s}")).content
    return f

def task_a_agent():
    messages = [
        SystemMessage("You are an assistant with tools. Complete the user's request."),
        HumanMessage(f"Summarise this in one sentence, then translate the summary to "
                     f"French. Output only the French.\n\n{TEXT}"),
    ]
    for _ in range(6):
        ai = track(bound.invoke(messages))
        messages.append(ai)
        if not ai.tool_calls:
            return ai.content
        for c in ai.tool_calls:
            content = str(BY_NAME[c["name"]].invoke(c["args"]))
            messages.append(ToolMessage(content=content, tool_call_id=c["id"]))
    return "⚠️ step limit"

# ══════════════ TASK B: adaptive — multi-hop data question ═══════════════
QUESTION_B = "Which customer spent the most, and what's the weather where they are?"

def task_b_chain():
    """A chain must GUESS the sequence in advance."""
    # We have to hard-code: get totals, then get details, then weather.
    totals = query_orders.invoke({"query_name": "totals_by_customer", "customer": None})
    # ...but which customer? The chain can't know without parsing, so we ask the model.
    top = track(model.invoke(
        f"Given this JSON, reply with ONLY the customer name with the highest total:\n{totals}"
    )).content.strip()
    details = query_orders.invoke({"query_name": "customer_details", "customer": top})
    city = __import__("json").loads(details)["city"]
    weather = get_weather.invoke({"city": city})
    return track(model.invoke(
        f"Question: {QUESTION_B}\nData: totals={totals} details={details} weather={weather}\n"
        f"Answer concisely."
    )).content

def task_b_agent():
    messages = [
        SystemMessage("You are a data assistant. Use tools for all facts. "
                      "Never guess at data a tool can provide."),
        HumanMessage(QUESTION_B),
    ]
    for _ in range(8):
        ai = track(bound.invoke(messages))
        messages.append(ai)
        if not ai.tool_calls:
            return ai.content
        for c in ai.tool_calls:
            content = str(BY_NAME[c["name"]].invoke(c["args"]))
            messages.append(ToolMessage(content=content, tool_call_id=c["id"]))
    return "⚠️ step limit"

# ══════════════ COMPARE ══════════════════════════════════════════════════
def bench(label, fn):
    reset()
    t0 = time.time()
    answer = fn()
    ms = (time.time() - t0) * 1000
    print(f"  {label:<8} {ms:>6.0f}ms  {usage['calls']} model calls  "
          f"{usage['tokens']:>5} tokens")
    print(f"           {answer.strip()[:100]}")
    return ms, usage["calls"], usage["tokens"]

print("═" * 76)
print("TASK A — FIXED SEQUENCE (summarise → translate)")
print("═" * 76)
a_chain = bench("chain", task_a_chain)
a_agent = bench("agent", task_a_agent)

print("\n" + "═" * 76)
print("TASK B — ADAPTIVE (multi-hop: top customer → their city → weather)")
print("═" * 76)
b_chain = bench("chain", task_b_chain)
b_agent = bench("agent", task_b_agent)

print("\n" + "─" * 76)
print(f"Task A: agent costs {a_agent[2]/a_chain[2]:.1f}× the tokens of the chain "
      f"for identical output")
print(f"Task B: the chain required hard-coding the sequence AND a parsing step; "
      f"the agent discovered it")
```

**JavaScript** — the structural contrast:
```js
// TASK B as a CHAIN — the sequence is hard-coded, and step 2 needs a parse
const totals  = await queryOrders.invoke({ queryName: "totals_by_customer", customer: null });
const top     = (await model.invoke(`Reply with ONLY the top customer name:\n${totals}`)).text.trim();
const details = await queryOrders.invoke({ queryName: "customer_details", customer: top });
const city    = JSON.parse(details).city;
const weather = await getWeather.invoke({ city });
const answer  = await model.invoke(`Question: ...\nData: ${totals} ${details} ${weather}`);

// TASK B as an AGENT — the sequence is DISCOVERED
const answer = await agent(QUESTION_B);   // the loop from §4.3
```

**Typical results:**

```
TASK A — FIXED SEQUENCE (summarise → translate)
  chain      1840ms  2 model calls    412 tokens
  agent      2960ms  3 model calls    987 tokens

TASK B — ADAPTIVE (multi-hop)
  chain      2100ms  2 model calls    520 tokens   ← but see below
  agent      3400ms  4 model calls   2180 tokens

Task A: agent costs 2.4× the tokens of the chain for identical output
```

**Read this carefully, because the naive conclusion is wrong.**

**Task A: the chain clearly wins.** Same output, half the tokens, faster. The agent adds a
decision step ("should I use a tool?") that has only one possible answer. Using an agent here is
pure waste — and this is the most common architectural mistake people make with agents.

**Task B: the chain *looks* cheaper, but that's misleading.** Look at what the chain code
actually required:

1. I had to **know the sequence in advance** — totals, then details, then weather.
2. I had to add a **model call just to parse** which customer was top.
3. I had to **hard-code `JSON.parse(details).city`** — brittle to any schema change.
4. If the question changed to *"which customer spent the least"*, the chain breaks entirely.

The agent handled all four without changes. **The chain's lower token count is bought with
developer-encoded knowledge that doesn't generalise.**

**The decision rule this establishes:**

| Use a chain when | Use an agent when |
|---|---|
| The sequence is always the same | The next step depends on the previous result |
| You know it at build time | The question shape varies |
| Cost/latency are tight | Flexibility is worth 2–4× the tokens |
| You need predictable testing | You accept variable step counts |

**And the honest middle ground:** many production systems are a chain *containing* an agent —
a fixed pipeline where one step is adaptive. Don't treat it as a binary choice for the whole
application.
</details>

---

### Exercise 4 — Add guardrails ●●●●○

Take the native ReAct agent and add all five production guards: step limit, repeat detection,
token budget, wall-clock timeout, and per-tool call caps. Make each one report *why* it fired,
and demonstrate each firing.

<details>
<summary>✅ Solution</summary>

**Python**
```python
# day16_guarded_agent.py
import json, time
from dataclasses import dataclass, field
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from day16_tools import TOOLS

load_dotenv()
BY_NAME = {t.name: t for t in TOOLS}
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0).bind_tools(TOOLS)

@dataclass
class Guards:
    max_steps: int = 8
    max_tokens: int = 15_000
    timeout_s: float = 30.0
    max_calls_per_tool: int = 3

@dataclass
class Result:
    answer: str
    stopped_by: str                       # why the loop ended
    steps: int = 0
    tool_calls: int = 0
    tokens: int = 0
    elapsed_ms: float = 0
    trace: list = field(default_factory=list)

SYSTEM = SystemMessage(
    "You are a data assistant with tools.\n"
    "- Never guess at data a tool can provide.\n"
    "- ALWAYS use the calculator for arithmetic.\n"
    "- If a tool errors or returns nothing useful, adapt. Do not repeat a failing call.\n"
    "- Never claim a tool result you did not receive."
)

def guarded_agent(question, guards=Guards()):
    messages = [SYSTEM, HumanMessage(question)]
    seen, per_tool = set(), {}
    r = Result(answer="", stopped_by="")
    t0 = time.time()

    for step in range(1, guards.max_steps + 1):
        # ── GUARD: wall clock (checked BEFORE spending) ──────────────────
        elapsed = time.time() - t0
        if elapsed > guards.timeout_s:
            r.stopped_by = f"timeout ({elapsed:.1f}s > {guards.timeout_s}s)"
            r.answer = "⚠️ The request took too long. Here's what I found so far."
            break

        ai = model.invoke(messages)
        messages.append(ai)
        r.steps = step
        r.tokens += (ai.usage_metadata or {}).get("total_tokens", 0)

        # ── GUARD: token budget ──────────────────────────────────────────
        if r.tokens > guards.max_tokens:
            r.stopped_by = f"token budget ({r.tokens} > {guards.max_tokens})"
            r.answer = "⚠️ Token budget exceeded before reaching an answer."
            break

        # ── natural completion ───────────────────────────────────────────
        if not ai.tool_calls:
            r.answer, r.stopped_by = ai.content, "completed"
            break

        for c in ai.tool_calls:
            name, args = c["name"], c["args"]
            r.tool_calls += 1
            sig = f"{name}:{json.dumps(args, sort_keys=True)}"
            per_tool[name] = per_tool.get(name, 0) + 1

            # ── GUARD: per-tool call cap ─────────────────────────────────
            if per_tool[name] > guards.max_calls_per_tool:
                content = (f"You have called {name} {per_tool[name]} times, which exceeds "
                           f"the limit of {guards.max_calls_per_tool}. Do not call it again. "
                           f"Answer with the information you already have.")
                r.trace.append((step, name, args, "🚫 TOOL CAP"))

            # ── GUARD: repeat detection ──────────────────────────────────
            elif sig in seen:
                content = ("You already made this exact call and got the same result. "
                           "Try different arguments, another tool, or answer with what "
                           "you have.")
                r.trace.append((step, name, args, "🔁 REPEAT"))

            else:
                seen.add(sig)
                try:
                    content = str(BY_NAME[name].invoke(args))
                except Exception as e:
                    content = f"Error: {e}"
                r.trace.append((step, name, args, content[:45]))

            messages.append(ToolMessage(content=content, tool_call_id=c["id"]))
    else:
        # ── GUARD: step limit (for-else runs if no break) ────────────────
        r.stopped_by = f"step limit ({guards.max_steps})"
        r.answer = "⚠️ Reached the step limit without finishing."

    r.elapsed_ms = (time.time() - t0) * 1000
    return r

def show(label, question, guards=Guards()):
    print(f"\n{'═' * 76}\n{label}\n❓ {question}\n{'═' * 76}")
    r = guarded_agent(question, guards)
    for step, name, args, res in r.trace:
        print(f"  [{step}] 🔧 {name}({json.dumps(args)[:50]}) → {res}")
    print(f"\n  💬 {r.answer[:130]}")
    print(f"  ⛔ stopped_by: {r.stopped_by}")
    print(f"  📊 {r.steps} steps · {r.tool_calls} tool calls · {r.tokens} tokens · "
          f"{r.elapsed_ms:.0f}ms")

# ── demonstrate each guard firing ────────────────────────────────────────
show("NORMAL — completes naturally",
     "Which customer spent the most, and what's the weather there?")

show("STEP LIMIT — max_steps=2 on a 4-step question",
     "Which customer spent the most, what's the weather there, and what is that in Fahrenheit?",
     Guards(max_steps=2))

show("TOKEN BUDGET — max_tokens=600",
     "Which customer spent the most, and what's the weather there?",
     Guards(max_tokens=600))

show("TOOL CAP — max_calls_per_tool=1",
     "Which customer spent the most, and what's the weather there?",
     Guards(max_calls_per_tool=1))

show("TIMEOUT — timeout_s=0.001",
     "What's the weather in Lahore?",
     Guards(timeout_s=0.001))
```

**JavaScript** — the guard structure:
```js
const GUARDS = { maxSteps: 8, maxTokens: 15_000, timeoutMs: 30_000, maxCallsPerTool: 3 };

for (let step = 1; step <= GUARDS.maxSteps; step++) {
  if (Date.now() - t0 > GUARDS.timeoutMs)      // ⏱ before spending
    return finish("timeout");

  const ai = await model.invoke(messages);
  tokens += ai.usage_metadata?.total_tokens ?? 0;

  if (tokens > GUARDS.maxTokens) return finish("token budget");
  if (!ai.tool_calls?.length)     return finish("completed", ai.text);

  for (const c of ai.tool_calls) {
    perTool[c.name] = (perTool[c.name] ?? 0) + 1;
    const sig = `${c.name}:${JSON.stringify(c.args)}`;

    const content =
      perTool[c.name] > GUARDS.maxCallsPerTool
        ? `You have called ${c.name} too many times. Answer with what you have.`
      : seen.has(sig)
        ? "You already made this exact call. Try something different."
      : await safeInvoke(c);

    seen.add(sig);
    messages.push(new ToolMessage({ content, tool_call_id: c.id }));
  }
}
return finish("step limit");
```

**Expected output pattern:**

```
NORMAL — completes naturally
  [1] 🔧 query_orders({"query_name": "totals_by_customer"}) → [{"customer":"globex"…
  [2] 🔧 query_orders({"query_name": "customer_details", "cus…) → {"customer":"globex"…
  [3] 🔧 get_weather({"city": "London"}) → {"city": "London", "tempC": 12…
  💬 Globex spent the most ($1,200). It's 12°C with light rain in London.
  ⛔ stopped_by: completed

TOOL CAP — max_calls_per_tool=1
  [1] 🔧 query_orders({"query_name": "totals_by_customer"}) → [{"customer":"globex"…
  [2] 🔧 query_orders({"query_name": "customer_details"…}) → 🚫 TOOL CAP
  💬 Globex spent the most ($1,200), but I wasn't able to look up their location.
  ⛔ stopped_by: completed
```

**Five design points:**

1. **`stopped_by` is the most valuable field here.** In production, the *distribution* of stop
   reasons is a health metric. A rise in "step limit" means a tool description regressed or
   questions got harder. A rise in "repeat" means the model is getting stuck. Without this
   field, all failures look identical.

2. **Every guard returns a message to the model, not an exception.** Look at the tool-cap case:
   the agent still produced a useful partial answer, because being told "answer with what you
   have" is actionable. Throwing would have produced nothing.

3. **The timeout is checked *before* the model call.** Checking afterwards means you always
   overrun by one call — and that call could be the slow one.

4. **Python's `for...else` is the idiomatic step-limit handler.** The `else` runs only if the
   loop completed without `break`, which is exactly "we exhausted the steps". JS needs an
   explicit post-loop return.

5. **Per-tool caps catch a different failure than repeat detection.** Repeat detection catches
   *identical* calls; the tool cap catches a model calling the same tool with *varying* arguments
   in a hunt — `search("X")`, `search("X policy")`, `search("company X policy")`. That pattern
   evades a signature check entirely.

**What this still can't do:** all this state — step count, seen signatures, per-tool counts,
tokens — is threaded through a function by hand. Adding streaming, or persisting the run so it
survives a restart, or pausing before a destructive tool for human approval, means threading more.
That's tomorrow's argument for graphs.
</details>

---

### Exercise 5 — 🏆 A self-correcting research agent ●●●●●

Build an agent that: uses a knowledge base and a calculator, **grades its own answer** for
groundedness before returning it, retries with a different approach if the answer is unsupported,
tracks the full trace and cost, and degrades gracefully when it can't answer. Compare its output
against an ungraded agent.

<details>
<summary>✅ Solution</summary>

**Python**
```python
# research_agent.py
"""A ReAct agent that grades its own answer and retries when ungrounded."""
import json, re, time
from dataclasses import dataclass, field
from typing import Literal
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage
from langchain_groq import ChatGroq

load_dotenv()

fast = ChatGroq(model="llama-3.1-8b-instant", temperature=0)      # grading
smart = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)  # reasoning

# ══════════════════ TOOLS ════════════════════════════════════════════════
KB = {
    "langgraph": "LangGraph adds stateful, cyclic workflows: nodes, edges, typed state with "
                 "reducers, checkpointers for persistence, and interrupts for human-in-the-loop. "
                 "It was released in January 2024.",
    "lcel": "LCEL (LangChain Expression Language) composes Runnables with the pipe operator. "
            "It builds a directed ACYCLIC graph, so it cannot express loops.",
    "rag": "Retrieval-Augmented Generation retrieves relevant chunks and puts them in the "
           "prompt. Typical k is 3-6. Reranking commonly improves recall@k by 10-20 points.",
    "embeddings": "Embeddings map text to vectors, typically 384-3072 dimensions. Cosine "
                  "similarity is standard. Models cannot be mixed within one index.",
}

@tool
def search_kb(query: str) -> str:
    """Search the internal knowledge base about AI engineering.

    Covers: LangGraph, LCEL, RAG, embeddings.
    Do NOT use for arithmetic or for topics outside this list.

    Args:
        query: What to look up.
    """
    q = query.lower()
    hits = [f"[{k}] {v}" for k, v in KB.items() if k in q]
    if not hits:
        hits = [f"[{k}] {v}" for k, v in KB.items()
                if any(w in v.lower() for w in q.split() if len(w) > 5)]
    if not hits:
        return f'Nothing found for "{query}". Topics available: {", ".join(KB)}.'
    return "\n\n".join(hits[:2])

@tool
def calculator(expression: str) -> str:
    """Evaluate arithmetic. ALWAYS use for any calculation.

    Args:
        expression: e.g. '(20 + 10) / 2'
    """
    if not re.fullmatch(r"[\d\s+\-*/().%]+", expression):
        return "Error: only numbers and + - * / ( ) % allowed."
    try:
        return f"{expression} = {eval(expression)}"
    except Exception:
        return f"Error: '{expression}' is not valid arithmetic."

TOOLS = [search_kb, calculator]
BY_NAME = {t.name: t for t in TOOLS}
bound = smart.bind_tools(TOOLS)

# ══════════════════ GRADING ══════════════════════════════════════════════
class Grade(BaseModel):
    """Assessment of whether an answer is supported by the gathered evidence."""
    reasoning: str = Field(description="One sentence. Write this first.")
    grounded: bool = Field(
        description="Is EVERY factual claim supported by the tool results?")
    unsupported: list[str] = Field(
        description="Claims not found in the tool results. Empty if fully grounded.")
    answers_question: bool = Field(description="Does it actually answer what was asked?")

grader = fast.with_structured_output(Grade)

# ══════════════════ THE AGENT ════════════════════════════════════════════
@dataclass
class Run:
    answer: str = ""
    stopped_by: str = ""
    attempts: int = 0
    steps: int = 0
    tokens: int = 0
    trace: list = field(default_factory=list)
    grades: list = field(default_factory=list)

BASE_SYSTEM = (
    "You are a research assistant with tools.\n"
    "- Never guess at data a tool can provide.\n"
    "- ALWAYS use the calculator for arithmetic.\n"
    "- If a tool returns nothing useful, adapt or say you don't know.\n"
    "- Never claim a tool result you did not receive."
)

def react_once(question, run, extra_instruction="", max_steps=6):
    """One pass of the ReAct loop. Returns (answer, evidence)."""
    messages = [SystemMessage(BASE_SYSTEM + extra_instruction), HumanMessage(question)]
    evidence, seen = [], set()

    for step in range(1, max_steps + 1):
        ai = bound.invoke(messages)
        messages.append(ai)
        run.steps += 1
        run.tokens += (ai.usage_metadata or {}).get("total_tokens", 0)

        if not ai.tool_calls:
            return ai.content, evidence

        for c in ai.tool_calls:
            sig = f"{c['name']}:{json.dumps(c['args'], sort_keys=True)}"
            if sig in seen:
                content = ("You already made this exact call. Try something different "
                           "or answer with what you have.")
                run.trace.append((run.attempts, step, c["name"], "🔁 REPEAT"))
            else:
                seen.add(sig)
                try:
                    content = str(BY_NAME[c["name"]].invoke(c["args"]))
                except Exception as e:
                    content = f"Error: {e}"
                evidence.append(f"{c['name']}({c['args']}) → {content}")
                run.trace.append((run.attempts, step, c["name"], content[:45]))

            messages.append(ToolMessage(content=content, tool_call_id=c["id"]))

    return "⚠️ Hit the step limit.", evidence

def self_correcting_agent(question, max_attempts=2):
    run = Run()

    for attempt in range(1, max_attempts + 1):
        run.attempts = attempt

        extra = "" if attempt == 1 else (
            "\n\nIMPORTANT: a previous attempt produced unsupported claims. "
            "Gather evidence with tools BEFORE answering, and state only what the "
            "tool results support. If they don't support an answer, say so."
        )

        answer, evidence = react_once(question, run, extra)

        # ── grade the answer against the evidence actually gathered ──────
        if not evidence:
            grade = Grade(reasoning="No tool evidence was gathered.",
                          grounded=False, unsupported=["entire answer"],
                          answers_question=False)
        else:
            grade = grader.invoke(
                f"Question: {question}\n\n"
                f"Tool results gathered:\n{chr(10).join(evidence)}\n\n"
                f"Proposed answer:\n{answer}\n\n"
                f"Is every factual claim in the answer supported by the tool results?"
            )

        run.grades.append(grade)

        if grade.grounded and grade.answers_question:
            run.answer, run.stopped_by = answer, f"grounded on attempt {attempt}"
            return run

        if attempt == max_attempts:
            # ── degrade gracefully rather than returning an ungrounded answer
            run.answer = (
                "I couldn't produce a reliably grounded answer. "
                + (f"What I did find: {evidence[0][:150]}" if evidence
                   else "The available tools returned no relevant information.")
            )
            run.stopped_by = "ungrounded after retries"
            return run

    return run

# ══════════════════ COMPARE WITH AN UNGRADED AGENT ═══════════════════════
def plain_agent(question, max_steps=6):
    run = Run()
    answer, _ = react_once(question, run, "", max_steps)
    run.answer, run.stopped_by = answer, "no grading"
    return run

QUESTIONS = [
    "What is LangGraph and when was it released?",          # fully in the KB
    "What is the typical k for RAG, and what is half of it?",  # KB + calculator
    "What is the market share of LangGraph versus CrewAI?",    # NOT in the KB
]

for q in QUESTIONS:
    print(f"\n{'═' * 78}\n❓ {q}\n{'═' * 78}")

    plain = plain_agent(q)
    print(f"\n── UNGRADED ──\n  {plain.answer.strip()[:210]}")

    graded = self_correcting_agent(q)
    print(f"\n── SELF-CORRECTING ──")
    for attempt, step, name, res in graded.trace:
        print(f"  [a{attempt}s{step}] 🔧 {name} → {res}")
    for i, g in enumerate(graded.grades, 1):
        flag = "✅" if g.grounded and g.answers_question else "❌"
        print(f"  grade {i}: {flag} grounded={g.grounded} answers={g.answers_question}"
              + (f" · unsupported: {', '.join(g.unsupported[:2])}" if g.unsupported else ""))
    print(f"\n  💬 {graded.answer.strip()[:210]}")
    print(f"  ⛔ {graded.stopped_by} · {graded.steps} steps · {graded.tokens} tokens")
```

**JavaScript** — the self-correction core:
```js
async function selfCorrectingAgent(question, maxAttempts = 2) {
  const run = { steps: 0, tokens: 0, trace: [], grades: [] };

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    const extra = attempt === 1 ? "" :
      "\n\nIMPORTANT: a previous attempt produced unsupported claims. Gather evidence " +
      "with tools BEFORE answering, and state only what the tool results support.";

    const { answer, evidence } = await reactOnce(question, run, extra);

    const grade = evidence.length
      ? await grader.invoke(
          `Question: ${question}\n\nTool results:\n${evidence.join("\n")}\n\n` +
          `Proposed answer:\n${answer}\n\nIs every claim supported?`)
      : { grounded: false, answersQuestion: false, unsupported: ["entire answer"] };

    run.grades.push(grade);

    if (grade.grounded && grade.answersQuestion) {
      return { ...run, answer, stoppedBy: `grounded on attempt ${attempt}` };
    }

    if (attempt === maxAttempts) {
      return { ...run,
        answer: "I couldn't produce a reliably grounded answer. " +
                (evidence[0] ? `What I did find: ${evidence[0].slice(0, 150)}` : ""),
        stoppedBy: "ungrounded after retries" };
    }
  }
}
```

**Typical output on the third question:**

```
❓ What is the market share of LangGraph versus CrewAI?

── UNGRADED ──
  LangGraph holds roughly 35% of the agent framework market while CrewAI has
  about 20%, with the remainder split between AutoGen and custom solutions.
  ← ENTIRELY INVENTED

── SELF-CORRECTING ──
  [a1s1] 🔧 search_kb → Nothing found for "market share". Topics available:…
  grade 1: ❌ grounded=False answers=False · unsupported: market share figures
  [a2s1] 🔧 search_kb → Nothing found for "LangGraph CrewAI comparison"…
  grade 2: ❌ grounded=False answers=False

  💬 I couldn't produce a reliably grounded answer. The available tools returned
     no relevant information.
  ⛔ ungrounded after retries · 4 steps · 1840 tokens
```

**Six design decisions worth defending:**

1. **The grader sees the *evidence*, not just the answer.** Grading an answer in isolation only
   checks plausibility. Grading it against the actual tool results is what detects fabrication —
   this is Day 12's citation verification applied to an agent loop.

2. **No evidence ⇒ automatically ungrounded.** If the agent answered without calling any tool on
   a question that needs one, that's a fail by construction — no grader call needed, and it saves
   a round trip.

3. **The retry changes the *instruction*, not just the seed.** Re-running the identical prompt
   usually produces the identical answer. Telling the model *why* the previous attempt failed is
   what makes attempt 2 different.

4. **Failure degrades to a partial answer, not an error.** "I couldn't produce a grounded answer.
   What I did find: …" is more useful than either a fabrication or a stack trace.

5. **The cheap model grades.** Grading is a simple classification; paying 70B rates for it on
   every attempt would double the cost of the whole loop.

6. **Both grades are kept.** Seeing that attempt 1 failed on *groundedness* and attempt 2 failed
   on *availability* tells you the knowledge base has a gap — which is a content problem, not a
   model problem. That distinction only exists because the grades are recorded.

**And now the friction that motivates the rest of Week 3.**

Look at `react_once` and `self_correcting_agent`. There's a loop inside a loop, `run` state
threaded through both by hand, a mutable trace, and multiple exit paths. It works — but now try
to add:

- **Streaming** the answer while grading happens after
- **Pausing** before an expensive third attempt to ask the user
- **Persisting** the run so a crash doesn't lose it
- **Resuming** from attempt 1's state to try a different tool

Each one means more parameters, deeper nesting, and more hand-threaded state. You have written a
state machine — this is the fourth time across this book — and the structure is fighting you.

**Tomorrow you stop writing loops and start declaring graphs.**
</details>

---

## 9. Interview questions

### Basic

<details>
<summary><b>Q: What is an agent?</b></summary>

An LLM in a loop where the **model decides the control flow**: which tool to call, with what
arguments, and when to stop. The loop is: model reasons → emits a tool call → your code executes
it → the result is appended → repeat until the model returns a final answer instead of a tool call.

That's the whole mechanism. Everything else — LangGraph, multi-agent systems, human-in-the-loop —
is structure around that loop.
</details>

<details>
<summary><b>Q: Difference between a chain and an agent?</b></summary>

Who decides the sequence. In a chain, the developer fixes the steps at build time. In an agent,
the model chooses at runtime, so the number and order of steps is unknown in advance.

Consequences: chains have predictable cost, latency and test behaviour; agents are flexible but
need step limits, guardrails and monitoring. Use a chain when the sequence is always the same;
use an agent when the next step depends on the previous result.
</details>

<details>
<summary><b>Q: What is ReAct?</b></summary>

Reason + Act — an interleaved loop of Thought → Action → Observation, repeated until the model
produces a final answer. The reasoning step matters because generated tokens are compute: writing
out what it needs before acting measurably improves tool selection and argument quality.

Originally implemented by having the model write a text trace that you parse. Modern
implementations use native tool calling, which is the same loop with structured output instead of
regex parsing.
</details>

<details>
<summary><b>Q: Why does text-based ReAct need a stop sequence?</b></summary>

The model has seen complete ReAct traces in training, so after writing an `Action:` line it will
continue by writing its own `Observation:` — with entirely fabricated data — and then reason from
it. Nothing errors, and the output looks convincing.

`stop: ["Observation:"]` forces generation to end so your code can insert the real result. Native
tool calling removes the problem structurally: the model was fine-tuned to emit an end-of-turn
token after a tool call.
</details>

### Intermediate

<details>
<summary><b>Q: How do you stop an agent looping forever?</b></summary>

A step limit is necessary but not sufficient — it caps the damage without addressing the cause.

The most effective addition is **repeat detection**: hash `(tool_name, arguments)`, and when you
see a repeat, instead of returning the same result again, return a message saying *"you already
made this exact call and got the same result; try something different or answer with what you
have."* That single message resolves most real loops, because the model genuinely can't tell it's
repeating otherwise.

Beyond that: per-tool call caps (which catch a different pattern — the same tool called with
*varying* arguments in a hunt, which evades a signature check), a token budget, and a wall-clock
timeout checked *before* each model call rather than after.

And the prompt should say "do not repeat a failing call" explicitly.
</details>

<details>
<summary><b>Q: Why is an agent's cost super-linear in steps?</b></summary>

Every step re-sends the entire accumulated history — the original question, every AI message,
every tool result. So step 4's input includes everything from steps 1–3. Summed across steps,
total input tokens grow roughly quadratically, not linearly.

This has practical consequences: a 4-step agent typically costs 5–6× a single call rather than
4×; large tool outputs are expensive twice over, because they're re-sent in every subsequent
step; and reducing step count (by consolidating tools, or improving descriptions so the model
chooses correctly first time) saves more than it appears to.

Mitigations: trim or summarise older tool results, truncate large outputs at the tool boundary,
and treat average step count as a monitored health metric.
</details>

<details>
<summary><b>Q: What does `create_agent` / `createAgent` actually build?</b></summary>

A compiled LangGraph state graph with two nodes: an **agent** node that calls the model bound to
your tools, and a **tools** node (a `ToolNode`) that executes any requested calls. A conditional
edge after the agent node routes to `tools` if there are tool calls and to `END` otherwise, and
the tools node always loops back to the agent.

That's the hand-written loop expressed as a graph. The reason it's a graph rather than a `while`
loop is what the graph provides: checkpointing between steps, streaming of intermediate state,
interrupts before tool execution, and time travel — none of which you get for free from a loop.
</details>

<details>
<summary><b>Q: When should you NOT use an agent?</b></summary>

When the sequence is known in advance. If every request follows retrieve → prompt → generate, an
agent adds a decision step with only one possible answer — costing latency, tokens and
predictability for nothing. This is the most common architectural mistake with agents.

Also avoid them when cost or latency budgets are tight (agents multiply model calls), when you
need deterministic, testable behaviour, or when the "agent" is really just one tool call that a
chain could make unconditionally.

The useful middle ground: a chain that *contains* an agent — a fixed pipeline where one step is
adaptive. It's rarely an all-or-nothing choice for the whole application.
</details>

### Advanced

<details>
<summary><b>Q: Your agent takes 12 steps for questions that should take 3. Diagnose it.</b></summary>

Step explosion is usually a tool-design problem wearing an agent-behaviour costume, so I'd read
traces before changing any prompt.

**Look at what the extra steps actually are:**

- **Identical repeated calls** → no repeat detection. The model can't tell it's looping. Add the
  signature check and the "you already called this" message.
- **Same tool, slightly varying arguments** → the model is hunting because results are unhelpful.
  The tool's output is the problem: it's returning "no results" for reasonable queries, or its
  output is too vague to act on. Improve what the tool returns, and make error messages
  actionable.
- **Tool A then tool B then tool A again** → the tools are too granular. If getting a customer's
  city always requires two calls, consolidate them into one tool that returns both. Each round
  trip saved removes a model call *and* all the re-sent history that comes with it.
- **Exploratory calls that don't contribute** → the description doesn't say when *not* to use the
  tool, so the model tries it speculatively.
- **The model re-deriving something it already has** → history is being trimmed too aggressively,
  or tool results are too verbose to locate. Structure tool output.

**Then check the prompt** for "answer once you have enough information" — without it, some models
keep gathering.

**Then check the model.** Step efficiency varies a lot; a smaller model may genuinely need more
steps for the same task, in which case the cost comparison isn't as favourable as the per-token
price suggests.

Throughout: instrument average steps per query segmented by question type, so you can tell
whether a change actually helped rather than relying on a few anecdotes.
</details>

<details>
<summary><b>Q: Design an agent for a customer support system with access to refunds.</b></summary>

The refund capability dominates the design — this is an agent that can move money.

**Tier the tools by blast radius.** Read-only tools (order lookup, policy search, shipping
status) run freely. Write tools that are reversible (add a note, tag a ticket) run with logging.
Irreversible tools (issue refund, cancel subscription) require **human approval via an interrupt**
— which is a hard code boundary, not a prompt instruction, because tool arguments are influenced
by untrusted user text and prompt injection is not solvable at the prompt layer.

**Constrain the refund tool itself.** It takes an order ID and a reason from an enum — not an
arbitrary amount. The amount is looked up server-side from the order. That way even a fully
compromised prompt cannot cause an arbitrary payout. Add per-agent daily limits and idempotency
keys so a retry can't double-refund.

**Ground the policy.** Refund eligibility comes from a policy document via retrieval, not from
the model's judgement, and the agent must cite the clause it relied on. That gives you an
auditable decision trail and makes policy changes a content update rather than a prompt change.

**Guardrails**: step limit, repeat detection, per-tool caps, and a check that the customer being
acted on matches the authenticated session — the agent must never be able to act on an account
the user doesn't own.

**Escalation as a first-class path.** Low confidence, an angry customer, an unusual amount, or a
policy edge case routes to a human with the full trace attached. An agent that knows when to stop
is more valuable than one that always answers.

**Observability**: log every tool call with arguments and the approving human; track the
distribution of stop reasons and approval/denial rates. A rising denial rate means the agent's
judgement is drifting and needs attention before it becomes an incident.

**Evaluation**: a golden set of tickets with expected outcomes, run before every prompt or tool
change, measuring both correctness and whether it *asked for approval when it should have*.
</details>

<details>
<summary><b>Q: How do you evaluate an agent, given the path varies between runs?</b></summary>

Non-determinism is the core difficulty: the same question can take different valid paths, so
exact-trace comparison is meaningless. I'd measure at three levels.

**Outcome level** — did it reach the right answer? This is the primary metric and it's
path-agnostic. Build a labelled set of questions with expected answers, and score with exact
match where possible, or an LLM-as-judge with a rubric where answers are free-form. Include
questions the agent *should refuse*, since over-answering is a common failure that outcome
metrics otherwise miss.

**Trajectory level** — was the path sensible? Not "did it match a reference path", but weaker,
more robust properties: did it call the necessary tools at least once; did it avoid tools it
shouldn't have used; did it stay within a step budget; did it repeat calls. These catch
regressions that outcome metrics miss — an agent taking 12 steps to reach the right answer is
degrading even though accuracy is unchanged.

**Efficiency level** — steps, tokens, latency, cost per query. Track distributions, not averages,
because tail behaviour is where agents fail.

**Practical machinery**: run each case several times and report a pass *rate* rather than a
boolean, since variance is real. Track the distribution of stop reasons (completed / step limit /
repeat / timeout) as a health signal. Log full traces so failures can be inspected rather than
guessed at.

**And the organisational part:** every production failure becomes a permanent eval case. Agent
quality regresses easily — a tool description change can shift behaviour globally — so the suite
has to run in CI on every prompt, tool or model change, or you'll rediscover the same bugs.
</details>

---

## 10. Recap

- ✅ An agent = a loop where **the model chooses the control flow**
- ✅ ReAct = Reason → Act → Observe, repeated until a final answer
- ✅ Text ReAct needs a **stop sequence** or the model invents observations
- ✅ Native tool calling solves that structurally — use it
- ✅ Agent cost is **super-linear in steps** — history is re-sent every time
- ✅ Five failure modes: looping, wrong tool, premature stop, step explosion, hallucinated results
- ✅ **Repeat detection** is the most valuable guard after a step limit
- ✅ Guards should return *messages* to the model, not throw
- ✅ Track `stopped_by` — the distribution of stop reasons is a health metric
- ✅ `createAgent` builds a two-node graph: agent ⇄ tools. That's tomorrow.

### Tomorrow

**[Day 17 — LangGraph basics](day-17-langgraph-basics.md)**: you've now hand-written a state
machine several times, and each time the state threading fought you. Tomorrow you declare it
instead — `StateGraph`, nodes, edges, `compile`, and a mermaid diagram of your own agent. The
loop you just built becomes about 20 lines of graph.

### Quick self-check

1. Your agent calls the same tool with identical arguments five times. What guard is missing, and what should it return?
2. Why does a 5-step agent cost more than 5× a single model call?
3. When is an agent the wrong choice?

<details>
<summary>Answers</summary>

1. **Repeat detection.** Hash `(tool_name, arguments)`; on a repeat, return a *message* — "you
   already made this exact call and got the same result, try something different or answer with
   what you have" — rather than the same result again. A step limit alone caps the damage but
   doesn't break the loop.
2. Because each step re-sends the **entire accumulated history**. Step 5's input includes the
   question plus all four previous AI messages and tool results, so total input tokens grow
   roughly quadratically in steps. Large tool outputs are especially costly, being re-sent every
   subsequent step.
3. When the sequence is fixed and known at build time — then a chain is cheaper, faster and
   testable. Also when cost or latency budgets are tight, or when you need deterministic
   behaviour. Use an agent only when the next step genuinely depends on the previous result.
</details>
