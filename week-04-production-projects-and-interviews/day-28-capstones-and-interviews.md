# Day 28 — Capstones & Interview Crash Course: Prove It

> ⏱ **Time:** ~3 hours today, then a capstone at your own pace · 🎯 **Prereqs:** Days 1–27 · 🧩 **Difficulty:** ●●●●●

**Today you learn:** you know a lot after 27 days, but nobody can see it yet. Today you turn
that knowledge into a **capstone** project that proves you can build, and interview answers
that prove you understand. You get a **starter kit** that runs with no API key (verified in
both languages) and twelve projects with **acceptance criteria**. You also practise answer
shapes for each kind of question, three **mock interviews** and the book's most-asked questions.

> 📖 **Words you'll meet today**
>
> - **Capstone** — one larger, finished project that combines what you've learned.
> - **Portfolio** — the set of projects you show employers as proof of your skills.
> - **Starter kit** — a small, working project you copy and extend instead of starting empty.
> - **Acceptance criteria** — the tests a project must pass before you call it done.
> - **Eval table** — a table of measured scores, before and after each change.
> - **System-design question** — an interview question where you design a whole system out
>   loud.
> - **Trade-off** — what you give up to get something else, such as speed for cost.
> - **Mock interview** — a practice interview with realistic questions and model answers.

**This is the mid-course checkpoint.** After four weeks, you can build and ship an LLM
application: chains, RAG, agents, graphs, memory, approvals, streaming, evaluation and
deployment. The course continues past Day 28. Week 5 goes down to the model layer: open and
local models, inference, fine-tuning, data, multimodal models, cost and security. Week 6
covers advanced agents, product and career, and ends with a final capstone on Day 40. Today's
capstone is the halfway proof. Finish one before you move on.

---

## 1. The problem

You can explain supersteps, reducers, checkpoints and interrupts. You've built StudyBuddy
from a chat loop to a multi-agent, streamed, evaluated, deployable system. And yet:

```
   Recruiter:     "Do you have LangChain experience?"
   You:           "Yes, I did a 28-day course."
   Recruiter:     "Anything I can look at?"

   Interviewer:   "How would you design a support agent for 50,000 customers?"
   You:           (knows every piece, starts talking about vector databases, runs out of time
                   before reaching state, failures, evaluation or cost)
```

Knowing things and *demonstrating* them are different skills. Both are learnable, and both
follow patterns.

### The real-life version

A cooking-school graduate applying to a restaurant:

```
   ❌ "I completed a 28-week programme."                     → a claim
   ✅ "Here's a dinner I cooked for 40 people. Here's what    → evidence
       went wrong at table 6 and how I fixed it. Taste it."

   ❌ In the trial shift, freezes when the head chef           → knowledge without a method
      says "table of twelve, two allergies, twenty minutes"
   ✅ Asks two questions, plans the order of work out loud,    → a method
      starts the slow dish first, flags the risk early
```

Your capstone is the dinner for 40. Your interview method is the trial shift.

---

## 2. Mental model

### The capstone ladder

```
   TIER 3 — PRODUCTION           a system someone else could run
   ├─ deployed (Day 27) · evaluated (Day 25) · reliable (Day 24) · observable
   │
   TIER 2 — AGENTIC              a system that decides and acts
   ├─ tools · graphs · persistence · human approval · multi-agent (Days 15–22)
   │
   TIER 1 — FOUNDATIONS          a system that answers well
   └─ prompts · structured output · chains · RAG · memory (Days 1–14)
```

One finished Tier 2 project with an evaluation table beats three unfinished Tier 3 ideas.
Climb one rung at a time. Each rung produces something you can show.

### What makes a portfolio project credible

```
   ┌────────────────────────────────────────────────────────────────────┐
   │  A DEMO shows it works once.                                         │
   │  A CREDIBLE PROJECT shows you know WHEN it works, WHY, and WHAT IT    │
   │  COSTS — and what you did when it didn't.                            │
   └────────────────────────────────────────────────────────────────────┘

   □ a README that starts with the problem, not the tech stack
   □ an architecture diagram generated from code (drawMermaid, Day 17)
   □ an evaluation table: dataset size, metrics, before/after a change (Day 25)
   □ a "failures I found" section with traces and fixes
   □ cost and latency per request, measured (Days 22–25)
   □ one command to run it — ideally without an API key (this chapter's starter kit)
```

### The interview loop

```
   CONCEPTS        "What is a reducer?"               → define · example · trade-off
   CODE/DEBUGGING  "Why does this return undefined?"  → hypothesis · evidence · fix · prevention
   SYSTEM DESIGN   "Design a support agent."          → requirements · numbers · architecture ·
                                                         state · failures · evals · cost
   PROJECT DEEP    "Tell me about your capstone."     → problem · decision · evidence · what you'd
     DIVE                                                change
   JUDGEMENT       "When would you NOT use an agent?" → the honest answer is usually the senior one
```

Every question type has a shape. Learning the shapes is most of the preparation.

---

## 3. First principles

### 3.1 Answering a concept question

> 💬 **In plain words:** define it, give an example, name a trade-off and a pitfall, then stop.
> Short and specific beats long and general.

```
   1. DEFINE in one sentence           "A reducer is a function that merges a node's
                                         update into a state channel."
   2. EXAMPLE, concrete                 "messages uses addMessages: it appends, and
                                         replaces a message that has the same id."
   3. WHY IT EXISTS / TRADE-OFF         "Parallel nodes write in the same superstep, so
                                         without a combining reducer one write is lost."
   4. A PITFALL (optional, strong)      "The classic bug is returning the whole list from
                                         a node — the reducer appends it again."
```

Stop there. A 45-second answer with a pitfall signals experience. A five-minute answer
signals that you can't prioritise.

### 3.2 Answering a debugging question

> 💬 **In plain words:** restate the symptom, guess the likely causes, say how you'd confirm,
> then fix it and stop it coming back.

```
   1. RESTATE THE SYMPTOM precisely     "invoke returns undefined, with no error"
   2. HYPOTHESES, most likely first     "a node writes a key that isn't a declared channel"
   3. HOW YOU'D CONFIRM                 "log each node's returned keys vs the state schema"
   4. FIX                               "rename the key / declare the channel"
   5. PREVENTION                        "a typed state schema and a node-level unit test"
```

Most debugging questions in this area come from a short list you've already met:

- silent channel typos (Day 17)
- missing reducers under fan-out (Days 17–19)
- subgraph duplication (Day 19)
- `thread_id` problems (Day 20)
- node re-execution on resume (Day 21)
- unfiltered streamed tokens (Day 23)
- retry defaults (Day 24)
- missing `stopWhen` (Day 26)
- in-process state in deployment (Day 27).

### 3.3 Answering a system-design question

> 💬 **In plain words:** follow the same eight steps every time, out loud. Start with
> questions and numbers, not with technology.

Use the same eight steps every time. Say them out loud, because interviewers score the
structure as much as the content.

```
   1. CLARIFY        who uses it, what "good" means, what's out of scope          (2 min)
   2. NUMBERS        users, requests/s at peak, model calls & tokens per request   (3 min)
   3. SHAPE          chain, workflow graph, single agent, or multi-agent — and why (5 min)
   4. STATE          what's in state, context, store, checkpoints (Day 18)         (5 min)
   5. FAILURE MODES  provider down, loops, injection, bad retrieval, humans slow   (5 min)
   6. HUMAN GATES    which actions need approval, and how resume works             (3 min)
   7. EVALUATION     datasets, metrics, online monitoring                          (5 min)
   8. COST & SCALE   the bottleneck from step 2, and the levers                    (5 min)
```

Step 2 is the one most candidates skip, and the one that most changes the design. Step 3 is
where judgement shows. Saying "this part is a fixed workflow, only this part needs an agent"
is worth more than any diagram.

### 3.4 Answering "tell me about your project"

> 💬 **In plain words:** tell a two-minute story: the problem, one key decision, a number, a
> failure you fixed, and what you'd do next.

```
   PROBLEM     one sentence a non-engineer would understand
   DECISION    the most interesting choice you made, and the alternative you rejected
   EVIDENCE    a number: accuracy before/after, latency, cost, failure rate
   FAILURE     something that broke, how you found it (a trace, an eval), how you fixed it
   NEXT        what you'd change with more time — shows you see the limits
```

Two minutes. Then let them pull on whichever thread interests them.

### 3.5 What "senior" sounds like

> 💬 **In plain words:** experienced engineers back each claim with how it works, a number, or
> what it costs. Vague claims sound junior.

```
   JUNIOR SIGNAL                              SENIOR SIGNAL
   ─────────────                              ─────────────
   "I'd use a multi-agent system"             "I'd start with one agent, measure, and split
                                               only the part whose context pollutes the rest"
   "LangGraph handles persistence"            "the checkpointer writes state every superstep,
                                               so I'd keep state to ids and decisions"
   "I'd add a retry"                          "retries at one layer, only on transient errors,
                                               with jitter — and idempotency keys on side effects"
   "the LLM judges the answers"               "an LLM judge calibrated against 40 human labels"
   "it scales horizontally"                   "compute is cheap here; the provider rate limit
                                               is the bottleneck at ~50 calls/s"
```

The pattern: senior answers name a **mechanism**, a **number**, or a **trade-off**. This book
has given you all three for every topic. Use them.

---

## 4. Code — JavaScript

### 4.1 The capstone starter kit

A complete StudyBuddy in one file: a retrieval tool, an agent graph, an approval gate on a
write tool, a checkpointer, and an evaluation check. With `GROQ_API_KEY` set, it uses a real
model. Without one, a scripted model drives the same graph, so it runs anywhere. Verified: all
four eval checks pass, and both the approve and reject paths behave correctly.

```js
// capstone-starter.mjs
// Install: npm i @langchain/langgraph @langchain/core zod   (+ @langchain/groq for a real model)
import { StateGraph, MessagesAnnotation, MemorySaver, Command, interrupt, START, END } from "@langchain/langgraph";
import { ToolNode } from "@langchain/langgraph/prebuilt";
import { BaseChatModel } from "@langchain/core/language_models/chat_models";
import { AIMessage, HumanMessage, SystemMessage, ToolMessage } from "@langchain/core/messages";
import { tool } from "@langchain/core/tools";
import { z } from "zod";

// ── 1. DATA: the student's notes (swap for a vector store — Days 9–12) ──────
const NOTES = [
  { id: "https-1", text: "HTTPS is HTTP over TLS. TLS encrypts traffic and authenticates the server." },
  { id: "https-2", text: "TLS 1.3 uses ephemeral Diffie-Hellman (ECDHE), which gives forward secrecy." },
  { id: "rec-1", text: "A recursive function needs a base case and must move toward it on every call." },
];

// ── 2. TOOLS (Day 15) ───────────────────────────────────────────────────────
const searchNotes = tool(
  async ({ query }) => {
    const words = query.toLowerCase().split(/\W+/).filter((w) => w.length > 2);
    const hits = NOTES
      .map((n) => ({ ...n, score: words.filter((w) => n.text.toLowerCase().includes(w)).length }))
      .filter((n) => n.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 2);
    return hits.length ? hits.map((h) => `[${h.id}] ${h.text}`).join("\n") : "No matching notes.";
  },
  { name: "search_notes", description: "Search the student's course notes. Use for any course question.",
    schema: z.object({ query: z.string() }) }
);

const FLASHCARDS = [];
const saveFlashcard = tool(
  async ({ front, back }) => { FLASHCARDS.push({ front, back }); return `Saved flashcard: ${front}`; },
  { name: "save_flashcard", description: "Save a flashcard to the student's deck. Requires approval.",
    schema: z.object({ front: z.string(), back: z.string() }) }
);
const tools = [searchNotes, saveFlashcard];

// ── 3. MODEL: real if a key is set, scripted otherwise (Day 22's test double) ─
class Scripted extends BaseChatModel {
  constructor(script) { super({}); this.script = script; this.i = 0; }
  _llmType() { return "scripted"; }
  bindTools() { return this; }
  async _generate(messages) {
    const message = this.script[Math.min(this.i++, this.script.length - 1)](messages);
    return { generations: [{ message, text: "" }] };
  }
}
let n = 0;
const call = (name, args) => () =>
  new AIMessage({ content: "", tool_calls: [{ name, args, id: `c${n++}`, type: "tool_call" }] });

async function createModel(script) {
  if (process.env.GROQ_API_KEY) {
    const { ChatGroq } = await import("@langchain/groq");
    return new ChatGroq({ model: "openai/gpt-oss-120b", temperature: 0 }).bindTools(tools);
  }
  return new Scripted(script);
}

// ── 4. GRAPH (Days 17–21) ───────────────────────────────────────────────────
const SYSTEM = new SystemMessage(
  "You are StudyBuddy. Answer course questions from search_notes and cite note ids like [https-1]. " +
  "Offer flashcards with save_flashcard when helpful."
);
const GATED = new Set(["save_flashcard"]);

export function buildGraph(model, checkpointer) {
  return new StateGraph(MessagesAnnotation)
    .addNode("agent", async (s) => ({ messages: [await model.invoke([SYSTEM, ...s.messages])] }))
    .addNode("approve", (s) => {                                     // Day 21: interrupt FIRST
      const last = s.messages.at(-1);
      const gated = last.tool_calls.filter((c) => GATED.has(c.name));
      if (!gated.length) return new Command({ goto: "tools" });
      const decision = interrupt({ type: "approval", calls: gated.map((c) => ({ name: c.name, args: c.args })) });
      if (decision === "approve") return new Command({ goto: "tools" });
      return new Command({                                           // answer EVERY call, then back to the agent
        update: { messages: last.tool_calls.map((c) =>
          new ToolMessage({ tool_call_id: c.id, content: "The student declined this action." })) },
        goto: "agent",
      });
    }, { ends: ["agent", "tools"] })                                 // Command routes — no static edge out
    .addNode("tools", new ToolNode(tools))
    .addEdge(START, "agent")
    .addConditionalEdges("agent", (s) => (s.messages.at(-1).tool_calls?.length ? "approve" : END), ["approve", END])
    .addEdge("tools", "agent")
    .compile({ checkpointer });
}

// ── 5. RUN + EVAL (Day 25) ──────────────────────────────────────────────────
const model = await createModel([
  call("search_notes", { query: "how does HTTPS work" }),
  (msgs) => new AIMessage(`HTTPS is HTTP over TLS [https-1]. Notes: ${String(msgs.at(-1).content).split("\n")[0]}`),
  call("save_flashcard", { front: "What does HTTPS add to HTTP?", back: "TLS encryption and server authentication" }),
  () => new AIMessage("Saved a flashcard for you."),
]);
const app = buildGraph(model, new MemorySaver());
const config = { configurable: { thread_id: "student-42" } };

const turn1 = await app.invoke({ messages: [new HumanMessage("How does HTTPS work?")] }, config);
const answer = turn1.messages.at(-1).content;
console.log("turn 1:", answer);

const turn2 = await app.invoke({ messages: [new HumanMessage("Make me a flashcard for that.")] }, config);
console.log("turn 2 paused for approval:", JSON.stringify(turn2.__interrupt__?.[0]?.value));
const turn2b = await app.invoke(new Command({ resume: "approve" }), config);
console.log("after approval:", turn2b.messages.at(-1).content, "| deck:", FLASHCARDS.length);

const toolsUsed = turn1.messages.flatMap((m) => m.tool_calls?.map((c) => c.name) ?? []);
const checks = {
  mentionsTLS: /tls/i.test(answer),
  citesANote: /\[https-\d\]/.test(answer),
  searchedFirst: toolsUsed[0] === "search_notes",
  gatedTheWrite: Boolean(turn2.__interrupt__),
};
console.log("eval:", JSON.stringify(checks), Object.values(checks).every(Boolean) ? "PASS" : "FAIL");
```

**Verified output (no API key)**

```
turn 1: HTTPS is HTTP over TLS [https-1]. Notes: [https-1] HTTPS is HTTP over TLS. TLS encrypts…
turn 2 paused for approval: {"type":"approval","calls":[{"name":"save_flashcard","args":{"front":"What does HTTPS add to HTTP?",…}}]}
after approval: Saved a flashcard for you. | deck: 1
eval: {"mentionsTLS":true,"citesANote":true,"searchedFirst":true,"gatedTheWrite":true} PASS
```

And the reject path (resume with `"reject"`): the tool never ran (`deck: 0`) and the agent's
next call saw the tool message `"The student declined this action."`.

> ⚠️ **Why the approval node routes with `Command` and has no outgoing edge.** An earlier
> draft of this kit had `.addEdge("approve", "tools")` *and* returned `Command({ goto: "agent" })`
> on rejection. Verified in both languages: **`Command` goto adds to static edges. It doesn't
> replace them.** So both `agent` and `tools` ran, and a *rejected* flashcard was saved anyway.
> When a node routes with `Command`, route every path with `Command`.

### 4.2 Growing the starter into a capstone

Each extension is a day you've already done. Keep the eval checks passing as you go.

```js
// ① real retrieval (Days 10–12): replace the keyword search inside search_notes
const hits = await vectorStore.similaritySearch(query, 4);

// ② persistence (Day 20): swap MemorySaver
import { PostgresSaver } from "@langchain/langgraph-checkpoint-postgres";
const checkpointer = PostgresSaver.fromConnString(process.env.DATABASE_URL);
await checkpointer.setup();

// ③ reliability (Day 24) — sketch: a step budget checked in the agent node's router,
//    or move to createAgent({ middleware: [modelCallLimitMiddleware(...)] })
const tooManySteps = (s) => s.messages.filter((m) => m.getType() === "ai").length > 8;

// ④ streaming (Day 23): tag the agent's model and stream tagged tokens over SSE
const model = baseModel.withConfig({ tags: ["final"] });

// ⑤ evaluation (Day 25): move `checks` into a dataset loop with a regression gate

// ⑥ deployment (Day 27): export buildGraph(...).compile() WITHOUT a checkpointer
//    for the LangGraph server, or wrap it in the start/poll/resume service
```

### 4.3 A capstone repository layout

```
studybuddy/
├── README.md                 problem · demo gif · architecture diagram · eval table · costs
├── src/
│   ├── graph.mjs             buildGraph — the only place the graph is defined
│   ├── tools/                one file per tool, each with its own tests
│   ├── prompts.mjs           versioned prompts (promptVersion in run metadata)
│   └── server.mjs            the API (Day 27)
├── evals/
│   ├── dataset.jsonl         real questions + references (grows with every bug)
│   ├── run-evals.mjs         the suite
│   └── baseline.json         the regression gate
├── test/                     reducers, routers, tools, scripted-model graph tests
├── docs/architecture.md      generated mermaid + the design decisions
├── compose.yaml              Postgres + the app, one command
└── .env.example              every variable, no secrets
```

A reviewer should be able to run `npm test` and `npm run evals` with no API key, and see the
graph diagram in the README without running anything.

---

## 5. Code — Python

### 5.1 The capstone starter kit

Verified: all four eval checks pass, and the reject path leaves the deck empty with the
declined tool message in the history.

```python
"""capstone_starter.py
Install: pip install langgraph langchain-core   (+ langchain-groq for a real model)"""
import itertools
import os
import re
from typing import Literal

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode
from langgraph.types import Command, interrupt

# ── 1. DATA: the student's notes (swap for a vector store — Days 9–12) ──────
NOTES = [
    {"id": "https-1", "text": "HTTPS is HTTP over TLS. TLS encrypts traffic and authenticates the server."},
    {"id": "https-2", "text": "TLS 1.3 uses ephemeral Diffie-Hellman (ECDHE), which gives forward secrecy."},
    {"id": "rec-1", "text": "A recursive function needs a base case and must move toward it on every call."},
]

# ── 2. TOOLS (Day 15) ───────────────────────────────────────────────────────
@tool
def search_notes(query: str) -> str:
    """Search the student's course notes. Use for any course question."""
    words = [w for w in re.split(r"\W+", query.lower()) if len(w) > 2]
    hits = sorted(
        ({**n, "score": sum(w in n["text"].lower() for w in words)} for n in NOTES),
        key=lambda n: n["score"], reverse=True,
    )
    hits = [h for h in hits if h["score"] > 0][:2]
    return "\n".join(f'[{h["id"]}] {h["text"]}' for h in hits) or "No matching notes."

FLASHCARDS: list[dict] = []

@tool
def save_flashcard(front: str, back: str) -> str:
    """Save a flashcard to the student's deck. Requires approval."""
    FLASHCARDS.append({"front": front, "back": back})
    return f"Saved flashcard: {front}"

tools = [search_notes, save_flashcard]

# ── 3. MODEL: real if a key is set, scripted otherwise ──────────────────────
class Scripted(GenericFakeChatModel):
    def bind_tools(self, tools, **kw):
        return self

ids = itertools.count()
def call(name, args):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"c{next(ids)}", "type": "tool_call"}])

def create_model(script):
    if os.environ.get("GROQ_API_KEY"):
        from langchain_groq import ChatGroq
        return ChatGroq(model="openai/gpt-oss-120b", temperature=0).bind_tools(tools)
    return Scripted(messages=iter(script))

# ── 4. GRAPH (Days 17–21) ───────────────────────────────────────────────────
SYSTEM = SystemMessage(
    "You are StudyBuddy. Answer course questions from search_notes and cite note ids like [https-1]. "
    "Offer flashcards with save_flashcard when helpful."
)
GATED = {"save_flashcard"}

def build_graph(model, checkpointer):
    def agent(state: MessagesState):
        return {"messages": [model.invoke([SYSTEM, *state["messages"]])]}

    def approve(state: MessagesState) -> Command[Literal["agent", "tools"]]:
        last = state["messages"][-1]
        gated = [c for c in last.tool_calls if c["name"] in GATED]
        if not gated:
            return Command(goto="tools")
        decision = interrupt({"type": "approval", "calls": [{"name": c["name"], "args": c["args"]} for c in gated]})
        if decision == "approve":
            return Command(goto="tools")
        return Command(                                   # answer EVERY call, then back to the agent
            update={"messages": [ToolMessage("The student declined this action.", tool_call_id=c["id"])
                                 for c in last.tool_calls]},
            goto="agent",
        )

    b = StateGraph(MessagesState)
    b.add_node("agent", agent)
    b.add_node("approve", approve)                        # routes with Command — no static edge out
    b.add_node("tools", ToolNode(tools))
    b.add_edge(START, "agent")
    b.add_conditional_edges("agent", lambda s: "approve" if s["messages"][-1].tool_calls else END, ["approve", END])
    b.add_edge("tools", "agent")
    return b.compile(checkpointer=checkpointer)

# ── 5. RUN + EVAL (Day 25) ──────────────────────────────────────────────────
if __name__ == "__main__":
    model = create_model([
        call("search_notes", {"query": "how does HTTPS work"}),
        AIMessage("HTTPS is HTTP over TLS [https-1]. It encrypts traffic and authenticates the server."),
        call("save_flashcard", {"front": "What does HTTPS add to HTTP?", "back": "TLS encryption and server authentication"}),
        AIMessage("Saved a flashcard for you."),
    ])
    app = build_graph(model, InMemorySaver())
    config = {"configurable": {"thread_id": "student-42"}}

    turn1 = app.invoke({"messages": [HumanMessage("How does HTTPS work?")]}, config)
    answer = turn1["messages"][-1].content
    print("turn 1:", answer)

    turn2 = app.invoke({"messages": [HumanMessage("Make me a flashcard for that.")]}, config)
    print("turn 2 paused for approval:", turn2["__interrupt__"][0].value if "__interrupt__" in turn2 else None)
    turn2b = app.invoke(Command(resume="approve"), config)
    print("after approval:", turn2b["messages"][-1].content, "| deck:", len(FLASHCARDS))

    tools_used = [c["name"] for m in turn1["messages"] for c in (getattr(m, "tool_calls", None) or [])]
    checks = {
        "mentions_tls": bool(re.search(r"tls", answer, re.I)),
        "cites_a_note": bool(re.search(r"\[https-\d\]", answer)),
        "searched_first": bool(tools_used) and tools_used[0] == "search_notes",
        "gated_the_write": "__interrupt__" in turn2,
    }
    print("eval:", checks, "PASS" if all(checks.values()) else "FAIL")
```

**Verified output (no API key)**

```
turn 1: HTTPS is HTTP over TLS [https-1]. It encrypts traffic and authenticates the server.
turn 2 paused for approval: {'type': 'approval', 'calls': [{'name': 'save_flashcard', 'args': {...}}]}
after approval: Saved a flashcard for you. | deck: 1
eval: {'mentions_tls': True, 'cites_a_note': True, 'searched_first': True, 'gated_the_write': True} PASS
```

Python's approval node declares its destinations with `Command[Literal["agent", "tools"]]`
(Day 19). JS uses `{ ends: [...] }`. Same graph, same behaviour.

### 5.2 Growing the starter into a capstone

```python
# ① real retrieval (Days 10–12)
hits = vector_store.similarity_search(query, k=4)

# ② persistence (Day 20) — in a server, enter this in the lifespan (Day 27)
from langgraph.checkpoint.postgres import PostgresSaver
with PostgresSaver.from_conn_string(os.environ["DATABASE_URL"]) as checkpointer:
    checkpointer.setup()
    app = build_graph(model, checkpointer)

# ③ reliability (Day 24): budgets, retries, fallbacks — or create_agent(middleware=[...])
# ④ streaming (Day 23): model.with_config(tags=["final"]) + astream over SSE
# ⑤ evaluation (Day 25): dataset loop + regression gate
# ⑥ deployment (Day 27): compile() without a checkpointer for the LangGraph server
```

### 5.3 A capstone repository layout

```
studybuddy/
├── README.md
├── pyproject.toml              pinned dependencies (uv / poetry lockfile)
├── src/studybuddy/
│   ├── graph.py                build_graph — the only place the graph is defined
│   ├── tools/
│   ├── prompts.py
│   └── server.py               FastAPI (Day 27)
├── evals/
│   ├── dataset.jsonl
│   ├── run_evals.py
│   └── baseline.json
├── tests/                      pytest: reducers, routers, tools, scripted-model graph tests
├── docs/architecture.md
├── compose.yaml
└── .env.example
```

---

## 6. Under the hood

### 6.1 The README that gets read

```markdown
# StudyBuddy — a tutor that answers from your own notes

Students ask questions; StudyBuddy answers only from their course notes, cites them,
and asks before changing anything.

![demo](docs/demo.gif)

## Results (60 real student questions)
<!-- illustrative numbers: replace with your own measurements -->
| metric                  | naive RAG | + reranking | + query rewrite |
|-------------------------|-----------|-------------|-----------------|
| answer correctness      | 71%       | 79%         | 86%             |
| groundedness            | 82%       | 90%         | 93%             |
| p95 latency             | 2.1 s     | 2.6 s       | 3.0 s           |
| cost / 1k questions     | $0.40     | $0.52       | $0.61           |

## Architecture
(mermaid generated by `npm run diagram`)

## What broke, and how I fixed it
- Follow-up questions retrieved nothing ("what about the second one?") → query rewriting (Day 12)
- A rejected flashcard was still saved → Command goto + static edge ran both nodes (Day 28)

## Run it
npm install && npm test && npm run evals   # no API key needed
```

The numbers above are **illustrative**. The point is the format. Every row in your own table
should be a claim backed by an eval run you can reproduce. That's the whole difference between
a project and a tutorial you followed.

### 6.2 How interviewers read a repository

```
   30 seconds   README: is there a problem, a result, a diagram?
   2 minutes    graph.* : is the control flow understandable? is state small?
   2 minutes    tests/ and evals/ : does the author know when it works?
   1 minute     a tool file: error handling, validation, secrets
   1 minute     commit history: steady progress, meaningful messages
```

Optimise for those six minutes. A clean graph file and a real eval folder outweigh a large
feature list.

### 6.3 Why the eval table matters more than the model

Anyone can call a strong model. What employers pay for is the loop: define quality, measure
it, change one thing, measure again, and know when to stop. An eval table is visible proof
that you run that loop. It also gives every interview conversation something concrete to
discuss. "Why did reranking add 8 points but query rewriting add 7 more?" is a question you
can answer and most candidates can't.

---

## 7. Common mistakes

### ❌ 1. `Command` goto alongside a static edge

```js
❌ .addNode("approve", fn, { ends: ["agent"] })   // fn returns Command({ goto: "agent" }) on reject
   .addEdge("approve", "tools")                    // ...and this edge ALSO fires
✅ route every path with Command; no static edge out of that node
```

Verified in both languages: `decide → Command(goto="agent")` plus `decide → tools` ran
**both** nodes (`['decide→agent', 'agent ran', 'TOOLS RAN']`). In an approval gate, that means
rejected actions execute. `Command` adds a destination. It never removes static edges.

### ❌ 2. A portfolio of tutorials

Three projects that each follow a tutorial read as zero projects. One project with your own
data, your own evaluation, and a documented failure reads as experience.

### ❌ 3. No numbers

"It works well" is not a result. Give dataset size, metric, before/after, latency and cost.
Even small, honest numbers beat adjectives.

### ❌ 4. A project that needs your API key to see anything

Reviewers won't create accounts to evaluate you. Scripted models (Days 22–28) let tests,
evals and a demo run without a key. Record a short demo GIF for the real-model version.

### ❌ 5. Starting a design answer with technology

```
❌ "I'd use LangGraph with Pinecone and a supervisor agent..."
✅ "Who uses it, what counts as a good answer, and how many requests at peak?"
```

### ❌ 6. Multi-agent by reflex in interviews

Proposing five agents for a problem that's a fixed workflow is the most common design warning
sign (red flag). Say what's a workflow, what needs an agent, and what you'd measure before
splitting.

### ❌ 7. Skipping failure modes and evaluation

Most candidates run out of time before steps 5–8 of the design framework. Save time for them,
because they're where experience shows.

### ❌ 8. Memorised definitions without mechanisms

"A checkpointer saves state" is a definition. "It writes the full state after every superstep,
keyed by thread_id, which is why state size drives write volume" is understanding. Every day of
this book gave you the second kind. Use it.

### ❌ 9. Claiming more than you built

Interviewers probe. If you say "deployed at scale", expect questions about queue depth and
connection pools. Describe exactly what you built and tested. "I ran it locally against the
LangGraph dev server and measured X" is strong and defensible.

### ❌ 10. Not reading the question behind the question

"How would you add memory?" is often really "do you know the difference between thread state
and long-term store?" (Day 18). Answer the literal question, then the underlying one.

---

## 8. Exercises

These are bigger than any day's exercises. Pick **one capstone** and finish it properly rather
than starting three. The solutions give an architecture, a build order and acceptance tests.
The implementation is yours, and every piece is a day you've already done.

### Exercise 1 — Tier 1 capstones (foundations) ●●●○○

Choose one:

| # | Project | What it proves | Days |
|---|---|---|---|
| 1 | **Syllabus Q&A with citations** — answer questions over a course's PDFs, cite page numbers, refuse when the answer isn't there | RAG done properly | 9–12 |
| 2 | **Lecture-to-flashcards pipeline** — transcript in, deduplicated flashcards out as validated JSON | chains + structured output | 5–8 |
| 3 | **Retrieval benchmark** — compare chunk sizes, embedding models and reranking on 50 labelled questions | measurement discipline | 9–13, 25 |
| 4 | **A tutor that remembers you** — preferences and weak topics persist across sessions; history trimmed | memory design | 14, 18 |

**Acceptance criteria (all Tier 1):** runs with one command; an eval set of at least 30 real
questions; a results table; one documented failure and fix.

<details>
<summary>✅ Architectures, build order and acceptance tests</summary>

**1 — Syllabus Q&A**

```
   PDFs → loader (page metadata) → splitter (headers kept) → embeddings → vector store
   question → query rewrite (follow-ups) → retrieve k=8 → rerank to 4 → answer with [p.N] citations
                                                                      → verify citations exist
```

Build order, measuring each step:

1. Ingest one PDF and print chunks with page numbers.
2. Retrieval-only eval (hit rate on 20 questions).
3. Answer with citations.
4. Citation verifier (every `[p.N]` must be in the retrieved chunks).
5. Refusal path.
6. Query rewriting.
7. Reranking.

Acceptance tests (both languages, sketch):

```js
for (const ex of dataset) {
  const { answer, sources } = await qa.invoke(ex.question);
  assert(ex.answerable ? !/I don't know/i.test(answer) : /I don't know/i.test(answer));
  for (const cite of answer.match(/\[p\.\d+\]/g) ?? []) assert(sources.some((s) => `[p.${s.page}]` === cite));
}
```

```python
for ex in dataset:
    out = qa.invoke(ex["question"])
    assert (("I don't know" in out["answer"]) != ex["answerable"])
    for cite in re.findall(r"\[p\.\d+\]", out["answer"]):
        assert any(f"[p.{s['page']}]" == cite for s in out["sources"])
```

**2 — Lecture-to-flashcards**

```
   transcript → split by topic → map: extract cards (structured output, schema-validated)
             → reduce: embed fronts, drop near-duplicates (cosine > 0.9) → export JSON / Anki CSV
```

Acceptance:

- 100% of outputs parse against the schema.
- Duplicate rate below 5% on a hand-checked sample.
- Every card's answer is supported by the transcript (LLM judge, calibrated on 30 cards).

**3 — Retrieval benchmark**

```
   fixed corpus + 50 questions with labelled relevant chunk ids
   grid: chunk size {300, 800, 1500} × overlap {0, 15%} × embeddings {2 models} × rerank {on, off}
   metrics: hit@4, recall@8, MRR, p95 latency, cost per 1k queries
```

Acceptance: a results table and a written recommendation that names the trade-off, not just the
winner. This project is small in code and very strong in interviews.

**4 — A tutor that remembers you**

```
   thread state (this chat) ─ trimmed history (Day 18)
   store namespace ("students", id) ─ preferences, weak topics (merged, never overwritten)
   extraction node at session end ─ writes durable facts to the store
```

Acceptance: a two-thread test.

- Facts learned in thread A are used in thread B.
- Conversation text from A does **not** appear in B.
- A contradiction ("actually I'm advanced now") updates the store rather than adding a second
  value.
</details>

---

### Exercise 2 — Tier 2 capstones (agentic) ●●●●○

Choose one:

| # | Project | What it proves | Days |
|---|---|---|---|
| 5 | **SQL study-analytics agent** with an approval gate on writes | tools, safety, HITL | 15–21 |
| 6 | **Research assistant** — plan sub-questions, research in parallel with `Send`, verify, write a cited report | control flow, map-reduce | 19, 22 |
| 7 | **Essay grader** — rubric workflow, per-criterion scores, teacher approval before posting | workflow vs agent judgement, HITL | 17–21 |
| 8 | **Supervisor tutor** — researcher, quizmaster and analyst as tools, streamed to a web UI | multi-agent, streaming | 22–23 |

**Acceptance criteria (all Tier 2):**

- the architecture diagram generated from code;
- trajectory evals (Day 25) for at least three behaviours;
- an approval gate on anything that writes;
- a restart test (pause in one process, resume in another).

<details>
<summary>✅ Architectures, build order and acceptance tests</summary>

**5 — SQL analytics agent**

Start from Day 21's Week 3 project. These additions make it a capstone:

- a read-only database role for queries (so the database enforces safety, not a regex);
- an allow-list of tables;
- an approval payload that shows the SQL *and* an estimated row count from `EXPLAIN`;
- an audit table of approvals;
- a trajectory eval that **fails if `run_write` ever executes without an approval record**.

**6 — Research assistant**

```
   plan (structured sub-questions) → Send × N → research (search tool) → verify (judge per claim)
        ▲                                                                      │
        └──────────── replan if < 2 supported findings (max 2) ────────────────┘
   → outline → write with citations → citation check
```

Start from Day 19's Exercise 4. Acceptance:

- findings merged with an append reducer (no lost results);
- results sorted by index;
- a budget exit on replans;
- every claim in the report traceable to a source.

**7 — Essay grader**

```
   essay → per-criterion scoring (Send over rubric criteria, structured output)
         → aggregate → feedback draft → interrupt(teacher reviews scores + feedback, may edit)
         → post grade (idempotency key)
```

The interesting judgement: this is a **workflow**, not an agent, because the steps are known.
Say so in the README. Acceptance: calibration against 30 teacher-graded essays (agreement per
criterion); teacher edits recorded; posting is idempotent across a resume.

**8 — Supervisor tutor, streamed**

Day 22's tool-based supervisor plus Day 23's SSE endpoint. Acceptance:

- only `final`-tagged tokens reach the UI;
- progress events per specialist;
- the Stop button cancels server-side work (verify no model calls after abort);
- measured cost per question vs a single-agent baseline, in the README.

**Restart test (all Tier 2), sketch**

```js
// process 1
const p1 = buildGraph(model, PostgresSaver.fromConnString(url));
await p1.invoke(input, cfg);                       // pauses at an interrupt
// process 2 — a fresh process, same database
const p2 = buildGraph(model, PostgresSaver.fromConnString(url));
const done = await p2.invoke(new Command({ resume: "approve" }), cfg);
assert(!done.__interrupt__);
```

```python
with PostgresSaver.from_conn_string(url) as cp:     # process 1
    build_graph(model, cp).invoke(inp, cfg)         # pauses
with PostgresSaver.from_conn_string(url) as cp:     # process 2
    done = build_graph(model, cp).invoke(Command(resume="approve"), cfg)
    assert "__interrupt__" not in done
```
</details>

---

### Exercise 3 — Tier 3 capstones (production) ●●●●●

Choose one:

| # | Project | What it proves | Days |
|---|---|---|---|
| 9 | **StudyBuddy, deployed** — the starter kit grown into a service with auth, Postgres, streaming, start/poll/resume | the whole stack | 20–27 |
| 10 | **An MCP server others can use** — notes/progress tools over Streamable HTTP with auth, consumed by a LangChain agent and an AI SDK app | interoperability, security | 26–27 |
| 11 | **An evaluation platform for your own agent** — datasets from production traces, judges calibrated, a CI regression gate, dashboards | quality engineering | 25 |
| 12 | **A reliability lab** — fault injection (429s, timeouts, tool failures, injected documents) with measured recovery | reliability engineering | 24 |

**Acceptance criteria (all Tier 3):** `compose.yaml` brings the system up locally; a written
capacity estimate; reliability and cost controls, with evidence they work; an eval gate in CI.

<details>
<summary>✅ Architectures, build order and acceptance tests</summary>

**9 — StudyBuddy, deployed**

```
   Next.js UI ──SSE──► API (auth, thread ownership, start/poll/resume, streaming chat)
                          │                     │
                          ▼                     ▼
                   Postgres (checkpoints,   LangGraph server or workers
                   store, runs, approvals)   (long runs: study plans)
```

Build order:

1. Starter kit.
2. Postgres checkpointer.
3. Day 27 service with ownership checks.
4. SSE chat with cancellation.
5. Long runs via background runs.
6. Middleware (limits, retries, fallback, PII).
7. Tracing and an eval gate.
8. `compose.yaml`.
9. A load test that reports p95 latency (the time 95% of requests finish within) and cost at a
   chosen concurrency.

Acceptance: every item on Day 27's Exercise 3 "break it" list shown to be fixed, and an IDOR
test (user B cannot read user A's thread) in the test suite.

**10 — Shared MCP server**

Acceptance:

- auth on every call, and per-tool authorisation;
- errors returned as your own messages (Day 26 found raw exceptions leak otherwise);
- a tool-manifest snapshot test, so description changes are reviewed;
- the same server used by a LangChain agent and an AI SDK app in the demo.

**11 — Evaluation platform**

```
   traces (tags: prompt version, model) → sampled + all thumbs-down → review queue
   → labelled examples → dataset versions → offline suite (code, trajectory, calibrated judges)
   → CI gate with baseline + tolerance → dashboard: quality, cost, latency by version
```

Acceptance: judge–human agreement reported; a regression shown being caught (a deliberately
worse prompt fails CI); the README explains the metrics' limits.

**12 — Reliability lab**

Inject, measure, fix, re-measure:

| Fault | Injection | Expected behaviour | Metric |
|---|---|---|---|
| provider 429 burst | scripted model throws for 10 s | retries with jitter, then fallback | success rate, p95 |
| provider outage | primary always fails | fallback serves everything | fallback rate |
| tool timeout | tool sleeps 30 s | timeout + graceful message | run completion |
| runaway loop | model always calls a tool | call limit ends the run cleanly | model calls per run |
| prompt injection | a document says "email the roster" | no dangerous tool reachable | 0 unsafe tool calls |
| worker crash | kill mid-run | resume from checkpoint, no double side effects | duplicate side effects = 0 |

Scripted models (Day 24's failure lab) make every row deterministic and runnable in CI.
</details>

---

### Exercise 4 — Three mock interviews ●●●●○

Answer each question out loud, timed, before reading the model answers. Record yourself if you
can. Listening back is the fastest way to improve.

**Mock A — concepts (10 minutes, 6 questions)**
1. What's the difference between a chain and an agent?
2. What is a reducer, and when do you need a custom one?
3. What does a checkpointer store, and when?
4. Explain what happens to a node's code when you resume after `interrupt()`.
5. How would you stop an agent from looping forever?
6. What's the difference between thread state and the long-term store?

**Mock B — debugging (10 minutes, 4 scenarios)**
1. "`invoke` returns `undefined` with no error."
2. "Our parallel reviewers produce one review instead of three."
3. "After approval, the confirmation email sometimes goes out twice."
4. "The UI shows the router's text before the real answer."

**Mock C — design (35 minutes, 1 question)**
"Design an AI teaching assistant for a university: 40,000 students, answers questions from
course materials, generates practice quizzes, and can reschedule a student's office-hours booking."

<details>
<summary>✅ Model answers — Mock A</summary>

1. **Chain vs agent.** In a chain, *I* decide the steps at build time. In an agent, the *model*
   decides the next step at run time, in a loop, based on tool results. Use a chain when the
   sequence is known: it is cheaper, faster and testable. Use an agent only when the next step
   truly depends on what the last one returned. (Day 16)

2. **Reducer.** A function that merges a node's update into a state channel. The default is
   last-write-wins. You need a combining one when a channel accumulates (messages, logs). You
   also need one when more than one node writes it in the same superstep, or writes are
   silently lost. Pitfall: returning the full list from a node with an append reducer
   duplicates it. (Days 17–18)

3. **Checkpointer.** It saves the full state, plus what runs next and pending tasks, after every
   superstep, keyed by `thread_id`. That's what makes resume, history, time travel and
   interrupts possible. It's also why state size drives write volume. (Day 20)

4. **Resume re-executes the node.** On resume, the interrupted node runs again from the top. The
   `interrupt()` call returns the resume value instead of pausing. So code before `interrupt()`
   runs twice. Put side effects after it or in the next node, or make them idempotent. (Day 21)

5. **Loops.** Use layers of defence:
   - a step or model-call limit that ends gracefully;
   - repeat detection that tells the model it already has the result;
   - a recursion limit as the backstop;
   - tool-call limits on expensive tools, and a token budget.

   And fix the cause, usually an overlapping tool description or a tool that keeps failing.
   (Days 16, 24)

6. **State vs store.** Thread state is this conversation, checkpointed per `thread_id`. The store
   is long-term, namespaced memory that crosses threads: preferences, learned facts. Short-term
   memory is state + checkpointer. Long-term memory is the store. (Day 18)
</details>

<details>
<summary>✅ Model answers — Mock B</summary>

1. **`undefined` with no error.** Most likely a node returns a key that isn't a declared
   channel. Updates to unknown keys are dropped silently. Confirm by logging each node's
   returned keys against the schema. Fix the key. Prevent it with a typed schema and a unit
   test per node. (Day 17)

2. **One review instead of three.** Fan-out into a last-write-wins channel: three writes in one
   superstep, and only one survives. Add a combining reducer (append), and carry an index so
   the merge node can sort. If it's a subgraph, also check that it isn't returning its whole
   state into an appending parent channel, which duplicates instead. (Days 17, 19)

3. **Email twice.** The send happens inside the node that calls `interrupt()`, before the
   interrupt, and resume re-runs the node. Move the send into the next node, or after
   `interrupt()`. Give the email an idempotency key so a retry or replay can't send it twice.
   (Days 21, 24)

4. **Router text in the UI.** Every model call streams in `messages` mode. Tag the answering model
   `final` and forward only chunks tagged `final`. In JS, nested specialist agents stream into the
   parent too, so the tag matters even more. (Day 23)
</details>

<details>
<summary>✅ Model answer — Mock C (the 8-step framework)</summary>

**1. Clarify.** Users: students (and staff for materials). "Good" means:

- answers grounded in the course's own materials, with citations;
- quizzes answerable from those materials;
- bookings changed only with the student's confirmation.

Out of scope: grading, email.

**2. Numbers.**

- 40,000 students × 30% weekly active ≈ 12,000/week.
- Exam-week peak: ~6,000/day × 6 questions = 36,000 runs/day.
- Peak hour 15% ≈ 5,400 runs/h ≈ 1.5 runs/s.
- ~3 model calls/run ⇒ ~5 calls/s.
- ~4,000 tokens/run ⇒ ~150M tokens/day at peak.

Compute is trivial. Provider quota and token cost matter. This fits one provider with a
fallback.

**3. Shape.** Three capabilities, three shapes:
- *Q&A*: a RAG **workflow** (rewrite → retrieve → rerank → answer with citations → verify), not an
  agent, because the steps are fixed.
- *Quizzes*: a workflow using structured output, grounded in retrieved materials.
- *Rescheduling*: a small **agent** with two tools (find slots, rebook), because it's a dialogue
  with a consequential action.

A thin router (a classifier call, not a supervisor agent) picks the path. A single agent
everywhere would cost more and be harder to evaluate.

**4. State.**

- Thread state: messages (trimmed), current course id, retrieved chunk *ids*.
- Context: student id, enrolments, timezone (fresh per request, from the auth layer).
- Store: learning preferences, weak topics.
- Checkpointer: Postgres.
- Materials and embeddings: a vector store, with per-course namespaces and enrolment filtering
  at query time (pre-filter, Day 11).

**5. Failure modes.**

- Provider errors: client retries on 429/5xx, and a fallback provider.
- Bad retrieval: refusal path + citation verification.
- Loops in the booking agent: model-call limit.
- Prompt injection via uploaded materials: the Q&A path has **no tools** that act, and the
  booking agent never reads course documents.
- Cross-course leakage: enrolment filter enforced in the retriever, and tested.

**6. Human gates.** Rebooking uses `interrupt()` showing old slot → new slot. Resume only with
the matching interrupt id. The rebook tool uses an idempotency key. Everything else is
read-only.

**7. Evaluation.** Per course:

- 50 real questions with references;
- retrieval metrics (recall@8), and groundedness/correctness judges calibrated on 40 staff
  labels;
- a quiz answerability judge;
- a trajectory test that rebook never runs without approval.

Online: sample 5% plus all thumbs-down, and alert on groundedness and cost per conversation.

**8. Cost & scale.** Bottleneck: tokens and quota, not compute. Levers:

- a cheaper model for the router and quiz generation, after evals confirm;
- cached embeddings of materials;
- small prompts (chunk ids in state, 4 chunks after reranking);
- streaming, so the wait feels shorter.

Deployment: a stateless API behind a load balancer, streaming chat in-request, and Postgres for
checkpoints, store and audit.

*What makes this answer strong:* numbers before architecture, three shapes instead of "an
agent", and injection handled by separating capabilities rather than by prompt wording.
</details>

---

### Exercise 5 — System-design walkthroughs ●●●●●

Outline answers (8 steps, bullet points) for four common prompts. Then compare them with the
model outlines:

1. A customer-support agent for an e-commerce company that can issue refunds.
2. An internal "ask the docs" assistant for a 5,000-person company with permissioned documents.
3. A coding assistant that can run tests and open pull requests.
4. A meeting assistant that summarises calls and creates follow-up tasks in a project tool.

<details>
<summary>✅ Model outlines</summary>

**1. Support agent with refunds**
- *Numbers:* tickets/day, peak concurrency, % needing refunds; refunds are rare and consequential.
- *Shape:* swarm-style handoffs (front desk → orders / billing / technical), because customers
  keep talking to the specialist. Or a single agent if there are about 10 tools or fewer.
- *State:* order *ids* in state; customer tier from context; conversation checkpointed.
- *Gates:* refunds above a threshold need human approval, with order history in the payload.
  Below it, tool-level limits (amount, one per order) replace the human.
- *Failures:* ping-pong handoffs (use a counter). Injection via order notes (the billing agent
  never treats free text from customers' notes as instructions). Duplicate refunds (an
  idempotency key per order).
- *Evals:* trajectory "refund never without eligibility check", resolution rate, CSAT proxy.

**2. Permissioned "ask the docs"**
- *The core problem is authorisation, not retrieval.* Filter by the user's permissions **inside**
  retrieval (pre-filter with document ACL metadata), never after generation.
- *State:* user identity and groups in context, refreshed per request (permissions change).
- *Freshness:* incremental ingestion, and deletions reach the index quickly. Stale ACLs (old
  access rules) are an incident.
- *Evals:* retrieval recall, groundedness, and a **leakage test suite**. Users asking for
  documents they can't see must get nothing from them.

**3. Coding assistant that runs tests and opens PRs**
- *Sandbox:* tests run in an isolated container with no secrets and no network by default.
- *Shape:* an agent with tools (read files, edit, run tests) in a loop with step and time limits.
  Opening a PR is gated (human approval) or restricted to draft PRs on a bot branch.
- *Injection:* repository content (READMEs, comments, issues) is untrusted. The agent that reads
  it can't push to protected branches or read secrets.
- *Evals:* a benchmark of real past issues with their tests. Measure pass rate and cost per
  solved issue, and add a regression gate on the benchmark.

**4. Meeting assistant**
- *Shape:* a workflow: transcribe → segment → summarise (map-reduce over segments) → extract
  action items (structured output) → draft tasks.
- *Gate:* tasks are created only after the meeting owner reviews the list (edit/approve).
  Wrong tasks assigned to real people are costly.
- *Privacy:* PII handling, retention limits on transcripts, per-meeting access control.
- *Evals:* action-item precision/recall against human-labelled meetings; assignee accuracy; summary
  faithfulness judge.

*The pattern across all four:* each design turns on **one hard constraint**: consequential
actions, permissions, untrusted repository content, or wrong assignments. The architecture is
organised around containing it. Find that constraint early and say it out loud.
</details>

---

## 9. Interview questions — the crash course

The most-asked questions across the whole book, with short model answers and where to go deeper.
Each day's own section has more, and `resources/interview-bank.md` collects them.

### Foundations (Days 1–8)

**Q1. What is a token, and why does it matter?** A unit of text the model reads and writes (often
part of a word). Context limits, latency and cost are all measured in tokens, so prompt size is a
budget. *(Day 1)*

**Q2. What does temperature do?** It scales the probability distribution before sampling. Low
values make outputs more deterministic, and high values more varied. Use low for extraction and
tools, and higher for brainstorming. *(Day 1)*

**Q3. What is LCEL?** LangChain's composition model. Every component is a Runnable with
`invoke`/`stream`/`batch`. `pipe` / `|` composes them into sequences, with `RunnableParallel`,
`RunnableLambda` and branching for the rest. Composition gives streaming, batching and tracing for
free. *(Day 7)*

**Q4. How do you get reliable structured output?** Use `withStructuredOutput` /
`with_structured_output` with a Zod or Pydantic schema. It uses tool calling or native JSON modes
under the hood. Validate the result, and handle the failure path. *(Day 6)*

### Data & RAG (Days 9–14)

**Q5. Walk me through a RAG pipeline.** At ingest time: load → split (with metadata) → embed →
store. At query time: rewrite (for follow-ups) → retrieve → (rerank) → answer grounded in the
retrieved context with citations → refuse when the answer isn't there. Evaluate retrieval and
generation separately. *(Days 9–12, 25)*

**Q6. How do you choose chunk size?** By measuring. Build a labelled question set and compare hit
rate/recall across sizes and overlaps. Too small loses context. Too large dilutes embeddings and
wastes tokens. *(Day 9)*

**Q7. Why does reranking help?** Bi-encoder embeddings are fast but coarse. A cross-encoder reads
query and document together and ranks more precisely. Retrieve broadly (say 20), then rerank to
a few. *(Day 13)*

**Q8. What's hybrid search?** Combining vector similarity with keyword search (BM25), usually with
reciprocal rank fusion. It catches exact identifiers and rare terms that embeddings blur.
*(Day 11)*

**Q9. How does memory work in modern LangChain?** Short-term: message history in graph state,
checkpointed per thread, trimmed or summarised. Long-term: a store namespaced by user. The old
`Memory` classes were removed. *(Days 14, 18)*

### Tools & agents (Days 15–16)

**Q10. What makes a good tool?** A precise name and description (the model reads them), a narrow
schema, validation, errors returned as useful messages, least privilege, and idempotency for side
effects. *(Day 15)*

**Q11. Explain the ReAct loop.** Reason about what to do, act by calling a tool, observe the
result, and repeat until done. Native tool calling builds this into the API. Guards (step limits,
repeat detection, budgets) keep it bounded. *(Day 16)*

### LangGraph (Days 17–21)

**Q12. Why LangGraph instead of a while loop?** State becomes explicit data owned by the framework.
So runs can be checkpointed, resumed, rewound, streamed per node, interrupted for humans, and drawn
as a diagram. *(Day 17)*

**Q13. What's a superstep?** A round in which all active nodes run against the same state
snapshot. Their updates are merged through reducers at the end. Then edges decide the next active
set. *(Day 17)*

**Q14. State vs context vs store vs checkpoint?** State: data flowing through nodes (serialised every
superstep). Context/config: per-request handles and identities, never persisted. Store: long-term,
cross-thread memory. Checkpoint: a saved snapshot of state. *(Day 18)*

**Q15. `Command` vs a conditional edge?** A conditional edge is a pure routing function of state.
`Command` lets a node update state and route in one return. That is useful when the node already
did the work the decision depends on. It adds to static edges; it doesn't replace them.
*(Days 19, 28)*

**Q16. What does `Send` do?** It fans out to N copies of a node, in one superstep. Each copy gets
its own payload as its entire state. Results merge through a reducer. It's map-reduce with N known
only at runtime. *(Day 19)*

**Q17. How does time travel work?** Every superstep's checkpoint is addressable. Invoke with a past
checkpoint's config to replay from there, or use `updateState` to fork with a change. *(Day 20)*

**Q18. How do you implement human approval?** `interrupt()` inside a node pauses the run and
checkpoints it. The caller shows the payload. `Command({ resume })` continues. The node re-runs
from the top on resume, so keep side effects after the interrupt. *(Day 21)*

### Production (Days 22–27)

**Q19. When is multi-agent worth it?** When one agent's tools, instructions or context have become
the source of errors, when work parallelises, or to isolate a dangerous capability. Measured: a
single-hop question went from 2 to 4 model calls under any supervisor pattern. *(Day 22)*

**Q20. Supervisor or swarm?** Use a supervisor when one voice should answer and combine the
specialists' work. Use handoffs when the user should keep talking to the specialist. The
tool-based supervisor is the recommended default for context control. *(Day 22)*

**Q21. How do you stream an agent to a UI?** Use stream modes over SSE: `updates` for progress,
`messages` filtered by a `final` tag for tokens, and `custom` for events. Wire cancellation to
client disconnects. *(Day 23)*

**Q22. What reliability defences do you put around an agent?** Retries on transient errors at one
layer with jitter, a fallback provider, timeouts, call limits, circuit breakers on tools,
idempotency keys, PII redaction, and capability limits against injection. *(Day 24)*

**Q23. How do you evaluate an LLM application?** Build a dataset from real traffic and failures.
Run code evaluators first, trajectory evaluators for agents, and calibrated LLM judges for quality.
Add a regression gate in CI and sampled online evaluation. *(Day 25)*

**Q24. What is MCP and when do you use it?** An open protocol for exposing tools, resources and
prompts to any AI client. Use it when a capability must cross app, language, team or vendor
boundaries. Keep single-app tools in-process. *(Day 26)*

**Q25. How do you deploy an agent that can run for minutes?** Decouple the run from the request.
Start it (202 + run id), stream or poll its status, and resume interrupts with a separate request.
Keep state in Postgres, let workers or the LangGraph server execute runs, and make submission
idempotent. *(Day 27)*

### Judgement

**Q26. When should you not use an agent?** When the steps are known (use a chain or workflow).
Also when latency or cost budgets are tight, when the task is a single structured call, or when
you can't yet evaluate whether it helps.

**Q27. What's the most common mistake you see in LLM apps?** Shipping without an evaluation set,
so every change is judged by a few hand-picked examples. Close runners-up: state bloat, unfiltered
retries, and trusting tool output.

**Q28. How do you keep up with fast-changing libraries?** Pin versions. Keep an evaluation suite
and a small set of behaviour tests (like this book's scripted-model checks). Upgrade on purpose.
This book found behaviour that differed between minor versions and between the JS and Python
libraries.

---

## 10. Recap — and the halfway point

### What you learned today

- ✅ A **capstone starter kit** that runs keylessly in both languages: retrieval tool, agent graph,
  approval gate, checkpointer, eval checks
- ✅ `Command` goto **adds** to static edges — in an approval gate that's a safety bug (verified)
- ✅ Twelve capstones in **three tiers**, each with acceptance criteria
- ✅ Credible projects show **numbers, failures and a one-command run**
- ✅ Answer shapes:
  - **concept**: define, example, trade-off, pitfall
  - **debugging**: hypothesis, confirm, fix, prevent
  - **design**: the 8 steps
  - **project**: problem, decision, evidence, failure, next
- ✅ Senior answers name a **mechanism, a number, or a trade-off**
- ✅ This is the **mid-course checkpoint**: you can now build and ship an LLM application.
  Weeks 5–6 continue with the model layer and advanced agents, product and career, ending in a
  final capstone on Day 40

### The whole book in one table

| Week | You learned to… | StudyBuddy became… |
|---|---|---|
| 1 — Foundations | call models well: tokens, prompts, structured output, LCEL | a streaming CLI chatbot |
| 2 — Data & RAG | answer from documents: splitting, embeddings, vector stores, RAG, memory | a tutor that cites your notes and remembers you |
| 3 — Tools, agents, LangGraph | let it act and decide: tools, agents, graphs, state, persistence, approval | an agent you can pause, rewind and trust with a database |
| 4 — Production | run it for real: multi-agent, streaming, reliability, evaluation, MCP, deployment | a system someone else could operate |

### The ideas that mattered most

```
   1. Every model call is a budget of tokens, latency and money.            (Day 1)
   2. Separate retrieval failures from generation failures.                  (Day 12)
   3. An agent is a loop where the model chooses the next step —
      so you need guards, and often you need a workflow instead.             (Day 16)
   4. State is data you own: small, typed, merged by reducers.               (Days 17–18)
   5. Checkpoints make pause, resume, rewind and restarts possible.          (Days 20–21)
   6. Consequential actions need constraints first, humans second.           (Days 21, 24)
   7. Measure before you split, retry, or switch models.                     (Days 22, 25)
   8. Compute is stateless; the database holds the truth.                    (Day 27)
```

### What to do next

```
   THIS WEEK     pick ONE capstone; get the starter kit running with your own data
   THIS MONTH    finish it: eval table, failure write-up, diagram, one-command run
   ONGOING       do Mock A–C again in two weeks; answer the day-level interview questions
                 aloud; keep your eval suite running as libraries upgrade
```

### Tomorrow

**[Day 29 — Open & local models](../week-05-the-model-layer/day-29-open-and-local-models.md)**:
everything so far called a hosted API. Week 5 goes one level down, to the model itself. You run a
model on your own machine, learn what a model file is, and see why a 4-bit model fits on a laptop.
Start your capstone first — then continue, because Weeks 5–6 make it cheaper, safer and better.

### Quick self-check

1. Your approval node returns `Command(goto="agent")` on rejection, and the graph also has an edge
   from that node to `tools`. What happens when a user rejects?
2. In a design interview, what do you do before choosing an architecture?
3. What three things turn a demo into a credible portfolio project?

<details>
<summary>Answers</summary>

1. **Both `agent` and `tools` run.** `Command` adds a destination, and the static edge still
   fires (verified in both languages). The rejected action executes anyway. Route every path out
   of that node with `Command`, and remove the static edge.

2. Clarify users, what "good" means and scope. Then **estimate the numbers**: peak requests,
   model calls and tokens per request. Those numbers decide whether the bottleneck is compute,
   provider quota, cost or state size, and they usually change the design.

3. Three things:
   - **Evidence**: an evaluation table on real questions, with cost and latency.
   - **Honesty about failure**: what broke, how you found it, how you fixed it.
   - **Reproducibility**: one command to run tests and evals, ideally without an API key, plus a
     diagram generated from the code.
</details>

---

<div align="center">

**[← Day 27 — Deployment](day-27-deployment-and-architecture.md)** · **[Week 4 index](README.md)** · **[Day 29 — Open & local models →](../week-05-the-model-layer/day-29-open-and-local-models.md)**

🎓 **Halfway there.** You can build and ship an LLM application. Next: the model layer.

</div>
