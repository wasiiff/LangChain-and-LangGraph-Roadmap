# Day 36 — Context Engineering & the Five Agent Patterns

> ⏱ **Time:** ~3 hours · 🎯 **Prereqs:** [Day 35](../week-05-the-model-layer/day-35-ai-security.md), [Day 22](../week-04-production-projects-and-interviews/day-22-multi-agent.md) · 🧩 **Difficulty:** ●●●●○

**Today you learn:** StudyBuddy now has many features, and most of them were built as "an
agent". Some are slow and unpredictable for no reason. The main agent's context also grows
with every tool call, so each call costs more than the one before. Today you learn the **five
workflow patterns** from Anthropic's essay "Building Effective Agents" and build all five as
small LangGraph graphs. You learn the one question that decides **workflow or agent**. Then you
measure an agent's context call by call, and shrink it with four strategies: **write, select,
compress and isolate**.

Every number in this chapter was measured with scripted models, so you need no API key.

> 📖 **Words you'll meet today**
>
> - **Workflow** — model calls joined by paths that *your code* decides in advance.
> - **Agent** — a model that decides its own next step and which tools to use, in a loop.
> - **Evaluator-optimizer** — one call writes an answer, another grades it, and the loop
>   repeats until it passes or hits a limit.
> - **Orchestrator-workers** — one call splits a job into parts at run time, and workers do
>   the parts.
> - **Context engineering** — deciding everything that goes into the model's context window
>   on each call.
> - **Compression** — making the context smaller by summarising or removing old content.
> - **Isolation** — giving a sub-task its own separate context, usually through a sub-agent.
> - **Deep agent** — a long-running agent with a to-do list, a file scratchpad and
>   sub-agents.

---

## 1. The problem

On [Day 35](../week-05-the-model-layer/day-35-ai-security.md) you saw that anything that
enters the context window can carry an attack. That made one question urgent: *what exactly
enters the context, and does it need to be there?* Today you answer it. You also fix a
second problem that has grown quietly since Week 3.

StudyBuddy v6 has six features. The team built most of them the same way: "give the model
some tools and let it work it out". Here is the kind of report a team writes after a month
(an illustrative example, not a measurement):

```
   feature          built as   what goes wrong
   ───────────────  ─────────  ─────────────────────────────────────────────────────
   flashcard        agent      2–3 model calls for a job that needs exactly 1
   essay feedback   agent      always the same 3 steps, but in a different order each time
   quiz pack        agent      summary, quiz and cards made one after another (slow)
   explain          1 call     answers break the house rules: too long, no example
   revision guide   agent      sometimes covers 2 subtopics, sometimes forgets 3
   homework help    agent      fine — the steps really do depend on the tools
```

And here is what the homework-help agent's model received on each call while it read four
chapters of notes (measured today in §4.7):

```
   call            1     2      3      4      5
   characters     94  1,288  2,487  3,694  4,901        total sent: 12,464
```

Each tool result stays in the window, so every call re-sends all the earlier ones. The fifth
call is fifty times bigger than the first.

So there are two problems:

| Problem | Symptom | Today's fix |
|---|---|---|
| **The wrong shape** | An agent where a fixed set of steps would do: more calls, less predictable | Pick the simplest of the five patterns |
| **Context bloat** | Every call re-sends everything that came before | Write, select, compress, isolate |

### The real-life version

Think about a restaurant kitchen. A set menu is a **workflow**: the chef knows every step
before service starts. Starter, main, dessert, always in that order. A chef cooking from
whatever the farmer delivered today is an **agent**: the next step depends on what is in the
box. Set menus are cheaper, faster and easier to check. You only cook "agent-style" when you
truly cannot plan ahead.

Now think about the chef's worktop. It is small. If every used bowl and every recipe card
stays on it, the chef slows down and grabs the wrong thing. A good chef writes notes on a
pad (**write**). They take out only the ingredients for this dish (**select**) and clear
away used bowls (**compress**). They give the pastry to a second cook at another bench
(**isolate**). That is context engineering.

---

## 2. Mental model

### The five patterns, plus the agent

```
   1. PROMPT CHAINING           2. ROUTING                     3. PARALLELISATION
   A ──► gate ──► B ──► C       classify ──┬──► maths          ┌──► summary ──┐
         (code check)                      ├──► essay    START─┼──► quiz    ──┼──► combine
                                           └──► general        └──► cards   ──┘

   4. ORCHESTRATOR-WORKERS      5. EVALUATOR-OPTIMIZER         THE AGENT
   plan ──Send×N──► work ──►    generate ──► evaluate          model ◄──► tools
        (N decided at run time) synthesise   ▲   │ fail &      (loops until the model
                                             └───┘ rounds<cap   says it is done)
                                                 │ pass → END
```

| Pattern | Use it when | LangGraph shape | Model calls (measured today) |
|---|---|---|---|
| **Prompt chaining** | The job splits into fixed steps, in a fixed order | edges in a line, plus a conditional "gate" | 3 (1 if the gate stops it) |
| **Routing** | Inputs fall into clear groups that need different handling | conditional edge after a classify node | 2 (router + one expert) |
| **Parallelisation** | Parts are independent (sectioning), or you want several opinions (voting) | several edges out of one node, then a join | 3, in ~0.3–0.4 s instead of ~0.9 s |
| **Orchestrator-workers** | You can't know the parts until you see the input | conditional edge returning `Send`s | 1 + N (N was 2 or 4) |
| **Evaluator-optimizer** | You have **clear criteria** and revising really helps | a loop: conditional edge back to the writer, with a cap | 6 for 3 rounds |
| **Agent** | The steps depend on what the tools return | model ⇄ tools loop (`createAgent`) | 5 for 4 tool calls |

### The one decision

```
   Can you write the steps down before you see the input?
        │
        ├── yes ─► WORKFLOW. Which shape?
        │            fixed order ......................... prompt chaining
        │            different kinds of input ............ routing
        │            independent parts ................... parallelisation
        │            parts unknown until run time ........ orchestrator-workers
        │            "good enough?" has a clear test ..... evaluator-optimizer
        │
        └── no ──► AGENT  (and keep its context small — Part 2)
```

### What fills the context window

```
   ┌──────────────── one model call ────────────────┐
   │ instructions (system prompt)                   │ ◄── you write it once
   │ tool definitions (names, descriptions, schema) │ ◄── grows with every tool
   │ memory (facts about the user)                  │ ◄── Day 14
   │ retrieved documents                            │ ◄── Days 12–13
   │ conversation history                           │
   │ tool calls and tool RESULTS                    │ ◄── usually the biggest part
   │ state you chose to show (todo list, notes)     │
   └────────────────────────────────────────────────┘
```

| Strategy | The question it asks | Example | Measured today |
|---|---|---|---|
| **Write** | Can this live *outside* the window until needed? | a notebook tool, a file, the graph state | kept all 4 facts after compression (Exercise 4) |
| **Select** | What is the smallest set of things this call needs? | retrieval, picking tools, reading one note | one `read_notes` call brought back 4 facts |
| **Compress** | Can old content be shorter or gone? | clear old tool results, summarise, trim | 12,464 → 5,331 characters, but 3 of 4 facts lost |
| **Isolate** | Can another context do this part? | sub-agents, `Send` workers | main agent 12,464 → 864 characters, all 4 facts kept |

---

## 3. First principles

### 3.1 Workflow or agent — the one question

> 💬 **In plain words:** if you can draw the flowchart before the user arrives, build the
> flowchart. Only let the model choose the path when you truly cannot.

In December 2024, Erik Schluntz and Barry Zhang at Anthropic published "Building Effective
Agents". They split "agentic systems" into two kinds:

- **Workflows** — "systems where LLMs and tools are orchestrated through predefined code
  paths".
- **Agents** — "systems where LLMs dynamically direct their own processes and tool usage".

The essay's main advice is to start simple. For many applications, it says, one well-built
model call with retrieval and good examples is enough. Add steps only when you can show that
they help.

Why does this matter so much? Each kind has a different cost profile:

| | Workflow | Agent |
|---|---|---|
| Number of calls | fixed, so you can predict cost | varies with each run |
| Testing | test each node on its own | test whole trajectories (Day 25) |
| Failure | fails at a known step | can loop, wander or stop early |
| Flexibility | only the paths you drew | can handle cases you never imagined |

You met this question on [Day 22](../week-04-production-projects-and-interviews/day-22-multi-agent.md):
"if you can draw the flowchart first, it's a workflow graph". Today you learn the five
standard flowcharts.

### 3.2 Each pattern is one graph shape

> 💬 **In plain words:** you already know every building block. Each pattern is just a
> different way of joining nodes with the edges you learned in Week 3.

[Day 8](../week-02-data-embeddings-and-rag/day-08-chains.md) named the first three patterns
and built them as LCEL chains. [Day 19](../week-03-tools-agents-and-langgraph/day-19-control-flow.md)
named orchestrator-workers and built it with `Send`. Here is the full map:

| Pattern | Graph building block | First met |
|---|---|---|
| Prompt chaining | `addEdge` in a line; a conditional edge as a **gate** | Day 8 §3.1, Day 17 |
| Routing | `addConditionalEdges` after a classify node | Day 8 §3.3, Day 17 |
| Parallelisation | several `addEdge(START, …)`, then a **join** edge from a list | Day 8 §3.2, Day 17 |
| Orchestrator-workers | a conditional edge that returns `Send` objects | Day 19 |
| Evaluator-optimizer | a conditional edge that points **back** to an earlier node | Day 17 (`shouldRevise`) |

Two details make these patterns safe in production.

**A gate is plain code.** In prompt chaining, Anthropic suggests a "gate" between steps: a
check that the first step's output is good enough to continue. Today's gate counts bullet
points. It costs nothing and always behaves the same way. When the outline had only one
bullet, the graph stopped after **1** model call instead of 3 (measured).

**A router can be code, too.** If you can tell the route from the input itself (a button the
user pressed, a file type), use an `if` statement. Use a model only when the input is free
text. StudyBuddy v7.0 (Exercise 5) routes by the feature the user picked, with no model call.

### 3.3 The evaluator-optimizer loop, measured

> 💬 **In plain words:** a writer drafts, a grader checks the draft against clear rules, and
> the writer fixes what the grader found. A counter stops the loop if it never passes.

This is the pattern Day 19 promised. The essay says it works best when two things are true:
there are **clear evaluation criteria**, and revising **measurably** improves the answer.
"Make it better" is not a criterion. "At most 40 words and one everyday example" is.

Today's run, with a scripted writer and a scripted grader:

```
  round 1: 28 words → FAIL: Add one everyday example.
  round 2: 59 words → FAIL: Too long: 59 words, limit 40.
  round 3: 35 words → PASS
passed=true rounds=3 model calls=6
writer saw (chars): 85, 270, 441
```

Three things to notice:

1. **Each round costs two calls**: one to write, one to grade. Three rounds cost 6 calls. A
   single call would have cost 1 and shipped the 28-word answer with no example.
2. **Fixing one problem can create another.** Round 2 added the example but broke the
   length rule. Real models do this too. That is why the grader checks *every* criterion on
   every round.
3. **The writer saw only the latest draft and the feedback** (85, 270, 441 characters). It
   did not see the whole history of drafts. That is a context engineering choice, and
   §7 shows what goes wrong without it.

**The cap is not optional.** If the grader never passes the draft, the loop never ends. The
recursion limit is the only thing that stops it, and the defaults differ between languages
(measured today):

| | Default limit | Writer calls before the error |
|---|---|---|
| JavaScript (`@langchain/langgraph` 1.4.20) | 25 supersteps | **13** |
| Python (`langgraph` 1.2.14) | **10,007** supersteps | **5,004** |

> ⚠️ **Python's default is not 25.** At `langgraph` 1.2.14 the default comes from the
> environment variable `LANGGRAPH_DEFAULT_RECURSION_LIMIT`, and it falls back to **10007**.
> An uncapped loop with a real model would make about ten thousand paid calls before it
> stops. Always count rounds in state and stop yourself.

### 3.4 What enters the context window

> 💬 **In plain words:** the model only knows what you send it on this call. Everything you
> send costs money, takes time to read, and can distract or mislead the model.

Andrej Karpathy described context engineering as "the delicate art and science of filling
the context window with just the right information for the next step". The list of things
that can enter the window is longer than most people expect:

| Source | Who controls it | Grows over time? |
|---|---|---|
| System prompt (instructions) | you | no |
| Tool definitions | you | with every tool you add (Day 22) |
| Memory | you, plus what you store about the user | slowly (Day 14) |
| Retrieved documents | your retriever | per question (Days 12–13) |
| Conversation history | the user and the model | every turn |
| Tool results | the outside world | **every tool call** |
| State you choose to show (todo list, notes) | you | as the task goes on |

Three costs grow with context size:

- **Money and time.** You pay for input tokens on every call. An agent re-sends its history
  each step, so the total grows much faster than the history itself. Today's baseline sent
  12,464 characters in total to say something that needed four short facts.
- **Accuracy.** Anthropic's September 2025 article "Effective context engineering for AI
  agents" calls this **context rot**: as the number of tokens grows, the model gets worse at
  recalling what is in them.
- **Attack surface.** Every tool result and retrieved page can hide instructions
  ([Day 35](../week-05-the-model-layer/day-35-ai-security.md)). Text that is not in the
  window cannot trick the model.

### 3.5 Four strategies: write, select, compress, isolate

> 💬 **In plain words:** keep notes outside the window, bring in only what this call needs,
> shrink what is old, and give big side-jobs their own separate window.

These four names come from the LangChain team's 2025 blog post "Context Engineering for
Agents". Anthropic's article uses similar ideas: note-taking, "just in time" retrieval,
compaction and sub-agents.

**Write** — save information *outside* the context window. A notebook tool, a file, a
database row or a key in graph state are all "outside". The model only sees it when
something brings it back.

**Select** — pull in only what the current call needs. Retrieval (Week 2) is select. So is
choosing a few tools out of fifty, or reading one note instead of the whole notebook.

**Compress** — keep fewer tokens for the same job. Trimming old messages
([Day 4](../week-01-foundations/day-04-langchain-models.md)), summarising history
([Day 14](../week-02-data-embeddings-and-rag/day-14-memory.md)) and clearing old tool
results all count. LangChain 1.x ships the last one as middleware. Measured today on the
four-chapter agent:

```
baseline  chars per call: 94, 1288, 2487, 3694, 4901       total 12464 · Exam briefing. Facts I can see: 1, 2, 3, 4
compress  chars per call: 94, 1288, 1302, 1319, 1328       total 5331 · Exam briefing. Facts I can see: 4
```

The context stopped growing, and the total fell by 57 %. But the final answer could only see
**one** of the four facts it needed. Compression always throws something away. The question
is whether you saved what matters first. That is why **write** usually comes before
**compress**. In Exercise 4 the agent saves each fact to a notebook before the chapter is
cleared. The final answer then sees all four facts again.

**Isolate** — let a separate context do the heavy reading. A sub-agent reads one chapter in
its own window and returns one line. The main agent never sees the chapter at all:

```
isolate   chars per call: 94, 128, 167, 214, 261           total 864 · Exam briefing. Facts I can see: 1, 2, 3, 4
          sub-agent chars per call: 63, 1257, 63, 1262, 63, 1270, 63, 1270
```

| Variant | Model calls | Biggest single call | Total characters sent | Facts kept |
|---|---|---|---|---|
| Baseline | 5 | 4,901 | 12,464 | 4 of 4 |
| Compress | 5 | 1,328 | 5,331 | **1 of 4** |
| Isolate | 5 main + 8 sub = 13 | 1,270 | 864 + 5,311 = 6,175 | 4 of 4 |

Isolation is not free: it more than doubled the number of calls. It wins when the side-job
is big, when side-jobs can run in parallel, or when their content would confuse the main
task. Day 22 measured the same trade-off for supervisors and specialists.

### 3.6 Long-running "deep" agents

> 💬 **In plain words:** an agent that works for an hour needs what a person needs for a
> long project. That means a to-do list, a folder of notes and some helpers.

In July 2025, Harrison Chase described "deep agents" on the LangChain blog. He looked at
long-running agents such as Claude Code, Deep Research and Manus, and named four parts:

1. **A detailed system prompt**, with instructions and examples.
2. **A planning tool** — a to-do list. Writing it changes nothing in the world. It is "a
   context engineering strategy to keep the agent on track": the plan stays visible.
3. **Sub-agents** for focused jobs, each with a clean context (isolate).
4. **A file system** for notes and large results (write, then select).

LangChain packages this as `deepagents` (Python) and `deepagents` (npm). Both installed and
ran here with a scripted model. In the versions tested (Python 0.7.22, JS 1.14.2), the
built-in tools were:

```
ls  read_file  write_file  edit_file  delete  glob  grep  task
```

There was no to-do tool by default in either language. You add one with LangChain's
`TodoListMiddleware` / `todoListMiddleware()`, which adds `write_todos`. The files live in
the graph state under a `files` key (a virtual file system), not on your disk. §4.10 runs a
minimal example.

---

## 4. Code — JavaScript

```bash
npm install @langchain/langgraph @langchain/core langchain zod
npm install deepagents          # only for §4.10
```

Verified with `@langchain/langgraph` 1.4.20, `@langchain/core` 1.2.17, `langchain` 1.5.15
and `deepagents` 1.14.2, on Node 24.

### 4.1 A keyless model for today

Every example uses a **fake model**. You give it a `reply` function. It looks at the prompt
and returns a fixed answer, so every run is the same and you need no API key. It also
records what each call received, which is how this chapter measures context.

```js
// fake.js — a keyless stand-in for a chat model.
// reply(lastText, messages) returns a string (or a whole AIMessage, for tool calls).
import { BaseChatModel } from "@langchain/core/language_models/chat_models";
import { AIMessage } from "@langchain/core/messages";

export class FakeModel extends BaseChatModel {
  constructor(reply, { delayMs = 0 } = {}) {
    super({});
    this.reply = reply;
    this.delayMs = delayMs;
    this.calls = 0;
    this.seen = [];                 // what each call received: message count and characters
  }
  _llmType() { return "fake"; }
  bindTools() { return this; }      // agents call this; the fake ignores the tool list
  async _generate(messages) {
    this.calls++;
    const chars = messages.reduce((n, m) => n + m.text.length, 0);   // .text flattens content blocks
    this.seen.push({ messages: messages.length, chars });
    if (this.delayMs) await new Promise((r) => setTimeout(r, this.delayMs));
    const out = this.reply(messages.at(-1).text, messages);
    const message = typeof out === "string" ? new AIMessage(out) : out;
    return { generations: [{ message, text: typeof out === "string" ? out : "" }] };
  }
}
```

> ⚠️ **Count `m.text`, not `String(m.content)`.** `createAgent` sends the system prompt as a
> list of content blocks. `String()` of that list is `"[object Object]"` (15 characters), so
> the first version of this probe under-counted the system prompt. `.text` joins the text
> blocks for you.

> 🎯 **With a real model:** replace each `new FakeModel(...)` with
> `new ChatGroq({ model: "openai/gpt-oss-120b" })` from `@langchain/groq`. The graphs
> stay the same. Not executed here; your outputs will vary from run to run.

### 4.2 Prompt chaining with a gate

Outline, then write, then simplify. A code gate stops the chain early if the outline is
weak.

```js
// Pattern 1 — prompt chaining with a gate
import { StateGraph, Annotation, START, END } from "@langchain/langgraph";
import { FakeModel } from "./fake.js";

const model = new FakeModel((p) =>
  p.includes("quantum foam") ? "- not sure"
  : p.startsWith("Outline") ? "- what a cell is\n- the nucleus\n- the membrane"
  : p.startsWith("Write") ? "A cell is the smallest living unit. The nucleus holds the DNA. The membrane controls what enters."
  : "Cells are tiny living rooms: the nucleus is the office, the membrane is the door."
);

const State = Annotation.Root({
  topic: Annotation(),
  outline: Annotation(),
  draft: Annotation(),
  final: Annotation(),
});

const outline = async (s) => ({
  outline: (await model.invoke(`Outline 3 points a beginner needs about: ${s.topic}`)).content,
});
// The gate is plain code: no model call, no cost, fully predictable.
const gate = (s) => (s.outline.split("\n").filter((l) => l.startsWith("- ")).length >= 3 ? "write" : END);
const write = async (s) => ({
  draft: (await model.invoke(`Write one paragraph that covers:\n${s.outline}`)).content,
});
const simplify = async (s) => ({
  final: (await model.invoke(`Rewrite for a 12-year-old:\n${s.draft}`)).content,
});

const chain = new StateGraph(State)
  .addNode("make_outline", outline)
  .addNode("write", write)
  .addNode("simplify", simplify)
  .addEdge(START, "make_outline")
  .addConditionalEdges("make_outline", gate, ["write", END])
  .addEdge("write", "simplify")
  .addEdge("simplify", END)
  .compile();

const out = await chain.invoke({ topic: "animal cells" });
console.log(out.final);
console.log("model calls:", model.calls);

const stopped = await chain.invoke({ topic: "quantum foam" });
console.log(stopped.final, "| total model calls:", model.calls);
```

```
Cells are tiny living rooms: the nucleus is the office, the membrane is the door.
model calls: 3
undefined | total model calls: 4
```

The second run made only **one** call (4 − 3). The gate saw one bullet and ended the graph.

> ⚠️ **The node is called `make_outline`, not `outline`.** In JavaScript a node can't share
> its name with a state key. The first version of this probe failed with:
> `Error: outline is already being used as a state attribute (a.k.a. a channel), cannot also
> be used as a node name.` Python accepted the same names (measured) — see §7.

### 4.3 Routing

One classify call picks a label. A conditional edge sends the question to the matching
expert.

```js
// Pattern 2 — routing
import { StateGraph, Annotation, START, END } from "@langchain/langgraph";
import { FakeModel } from "./fake.js";

// The router model answers with ONE label. A real model gets the same instruction.
const router = new FakeModel((p) => {
  const q = p.split("Question:")[1];
  return /\d/.test(q) ? "maths" : /essay|write/i.test(q) ? "essay" : "general";
});
const expert = (name) => new FakeModel(() => `[${name}] answered`);
const experts = { maths: expert("maths tutor"), essay: expert("essay coach"), general: expert("general helper") };

const State = Annotation.Root({ question: Annotation(), label: Annotation(), answer: Annotation() });

const classify = async (s) => ({
  label: (await router.invoke(
    `Label this question as exactly one of: maths, essay, general.\nQuestion: ${s.question}`
  )).content.trim(),
});
const answerWith = (name) => async (s) => ({
  answer: (await experts[name].invoke(s.question)).content,
});

const app = new StateGraph(State)
  .addNode("classify", classify)
  .addNode("maths", answerWith("maths"))
  .addNode("essay", answerWith("essay"))
  .addNode("general", answerWith("general"))
  .addEdge(START, "classify")
  .addConditionalEdges("classify", (s) => s.label, ["maths", "essay", "general"])
  .addEdge("maths", END).addEdge("essay", END).addEdge("general", END)
  .compile();

for (const q of ["What is 12 x 7?", "Check my essay intro", "Why is the sky blue?"]) {
  const out = await app.invoke({ question: q });
  console.log(`${q.padEnd(22)} → ${out.label.padEnd(8)} ${out.answer}`);
}
```

```
What is 12 x 7?        → maths    [maths tutor] answered
Check my essay intro   → essay    [essay coach] answered
Why is the sky blue?   → general  [general helper] answered
```

Why route at all? Each expert gets a short prompt written for one job. You can also send easy
questions to a small, cheap model and hard ones to a strong model (Day 8 §4.2).

### 4.4 Parallelisation (sectioning)

Three independent jobs run at the same time, then a join node combines them.

```js
// Pattern 3 — parallelisation (sectioning)
import { StateGraph, Annotation, START, END } from "@langchain/langgraph";
import { FakeModel } from "./fake.js";

// Each fake call takes 300 ms, like a short real model call.
const model = new FakeModel((p) => `${p.split(":")[0]} done`, { delayMs: 300 });

const State = Annotation.Root({
  notes: Annotation(),
  parts: Annotation({ reducer: (a, b) => a.concat(b), default: () => [] }), // all 3 results
  pack: Annotation(),
});

const section = (name, task) => async (s) => ({
  parts: [`${name}: ${(await model.invoke(`${task}: ${s.notes}`)).content}`],
});

const app = new StateGraph(State)
  .addNode("summary", section("summary", "Summarise"))
  .addNode("quiz", section("quiz", "Write 3 quiz questions"))
  .addNode("cards", section("cards", "Write 5 flashcards"))
  .addNode("combine", (s) => ({ pack: [...s.parts].sort().join(" | ") }))
  .addEdge(START, "summary").addEdge(START, "quiz").addEdge(START, "cards")
  .addEdge(["summary", "quiz", "cards"], "combine")   // wait for all three
  .addEdge("combine", END)
  .compile();

const t0 = Date.now();
const out = await app.invoke({ notes: "Photosynthesis turns light into sugar." });
console.log(out.pack);
console.log(`3 model calls in ${Date.now() - t0} ms`);
```

```
cards: Write 5 flashcards done | quiz: Write 3 quiz questions done | summary: Summarise done
3 model calls in 385 ms
```

A second run took 318 ms. Three 300 ms calls one after another would take at least 900 ms.
The `parts` channel needs an **append reducer**
([Day 18](../week-03-tools-agents-and-langgraph/day-18-state-and-reducers.md)). Without one,
the run fails when the three writes arrive together. Measured:
`InvalidUpdateError: Invalid update for channel "parts" with values [["a"],["b"],["c"]]:
LastValue can only receive one value per step.`

The results arrive in any order, so `combine` sorts them.

The other flavour, **voting**, runs the *same* task several times and takes the majority.
You build it in Exercise 2.

### 4.5 Orchestrator-workers

The orchestrator decides how many parts there are. `Send` starts one worker per part.

```js
// Pattern 4 — orchestrator-workers
import { StateGraph, Annotation, Send, START, END } from "@langchain/langgraph";
import { FakeModel } from "./fake.js";

// The orchestrator decides the subtasks at run time. A real model returns this JSON too.
const PLANS = {
  "photosynthesis": ["light reactions", "Calvin cycle"],
  "the French Revolution": ["causes", "the Terror", "Napoleon", "legacy"],
};
const orchestrator = new FakeModel((p) => JSON.stringify(PLANS[p.split("TOPIC: ")[1]]));
const worker = new FakeModel((p) => `notes on ${p.split("SUBTOPIC: ")[1]}`);

const State = Annotation.Root({
  topic: Annotation(),
  subtopics: Annotation(),
  notes: Annotation({ reducer: (a, b) => a.concat(b), default: () => [] }),
  guide: Annotation(),
});

const plan = async (s) => ({
  subtopics: JSON.parse((await orchestrator.invoke(
    `Split this revision topic into 2-5 subtopics. Reply with a JSON list.\nTOPIC: ${s.topic}`
  )).content),
});
// One Send per subtopic: the number of workers is decided by the plan, not by you.
const assign = (s) => s.subtopics.map((sub, i) => new Send("work", { sub, i }));
const work = async ({ sub, i }) => ({
  notes: [{ i, text: (await worker.invoke(`Write revision notes. SUBTOPIC: ${sub}`)).content }],
});
const synthesise = (s) => ({
  guide: [...s.notes].sort((a, b) => a.i - b.i).map((n) => n.text).join("; "),
});

const app = new StateGraph(State)
  .addNode("plan", plan)
  .addNode("work", work)
  .addNode("synthesise", synthesise)
  .addEdge(START, "plan")
  .addConditionalEdges("plan", assign, ["work"])
  .addEdge("work", "synthesise")
  .addEdge("synthesise", END)
  .compile();

for (const topic of Object.keys(PLANS)) {
  const before = worker.calls;
  const out = await app.invoke({ topic });
  console.log(`${topic}: ${worker.calls - before} workers → ${out.guide}`);
}
```

```
photosynthesis: 2 workers → notes on light reactions; notes on Calvin cycle
the French Revolution: 4 workers → notes on causes; notes on the Terror; notes on Napoleon; notes on legacy
```

Same graph, two different numbers of workers. That is the difference from parallelisation:
there, *you* drew three nodes; here, the *plan* decides. Each worker sees only its payload
(`{ sub, i }`), which is isolation for free. The index `i` lets `synthesise` restore the
order (Day 19 §7).

### 4.6 Evaluator-optimizer — the full loop

A writer, a grader with two clear criteria, a round counter, and a conditional edge that
loops back.

```js
// Pattern 5 — evaluator-optimizer: generate → evaluate → revise, with a cap
import { StateGraph, Annotation, START, END } from "@langchain/langgraph";
import { FakeModel } from "./fake.js";

const D1 = "Photosynthesis is how green plants make their own food. Inside the leaf, chlorophyll " +
  "captures light and uses it to turn water and carbon dioxide into glucose, releasing oxygen.";
const D2 = D1 + " For example, a sunflower in a sunny garden grows taller every week because its " +
  "leaves make glucose all day, while a plant left in a dark cupboard turns pale and weak.";
const D3 = "Photosynthesis is how plants make food from light. Chlorophyll turns water and carbon " +
  "dioxide into sugar and oxygen. For example, a plant on a sunny windowsill thrives, while " +
  "one in a dark cupboard turns pale.";

// The generator: a scripted writer that improves when it gets feedback.
const writer = new FakeModel((p) => {
  if (!p.includes("FEEDBACK:")) return D1;
  return p.split("FEEDBACK:")[1].includes("example") ? D2 : D3;
});

// The evaluator: checks two clear criteria and replies with JSON.
const words = (t) => t.trim().split(/\s+/).length;
const judge = new FakeModel((p) => {
  const draft = p.split("DRAFT:\n")[1];
  if (!/for example/i.test(draft)) return JSON.stringify({ pass: false, feedback: "Add one everyday example." });
  if (words(draft) > 40) return JSON.stringify({ pass: false, feedback: `Too long: ${words(draft)} words, limit 40.` });
  return JSON.stringify({ pass: true, feedback: "" });
});

const State = Annotation.Root({
  task: Annotation(),
  draft: Annotation(),
  feedback: Annotation(),
  passed: Annotation(),
  round: Annotation({ reducer: (a, b) => a + b, default: () => 0 }),
});

const generate = async (s) => {
  const prompt = s.feedback
    ? `Revise the draft. Fix only what the feedback asks.\nDRAFT: ${s.draft}\nFEEDBACK: ${s.feedback}`
    : `Explain for a beginner in at most 40 words, with one everyday example: ${s.task}`;
  return { draft: (await writer.invoke(prompt)).content, round: 1 };
};

const evaluate = async (s) => {
  const verdict = JSON.parse((await judge.invoke(
    `Criteria: (1) one everyday example, (2) at most 40 words.\nReply JSON {pass, feedback}.\nDRAFT:\n${s.draft}`
  )).content);
  console.log(`  round ${s.round}: ${words(s.draft)} words → ${verdict.pass ? "PASS" : "FAIL: " + verdict.feedback}`);
  return { passed: verdict.pass, feedback: verdict.feedback };
};

const MAX_ROUNDS = 3;
const next = (s) => (s.passed || s.round >= MAX_ROUNDS ? END : "generate");

const app = new StateGraph(State)
  .addNode("generate", generate)
  .addNode("evaluate", evaluate)
  .addEdge(START, "generate")
  .addEdge("generate", "evaluate")
  .addConditionalEdges("evaluate", next, ["generate", END])
  .compile();

const out = await app.invoke({ task: "photosynthesis" });
console.log(`passed=${out.passed} rounds=${out.round} model calls=${writer.calls + judge.calls}`);
console.log("writer saw (chars):", writer.seen.map((x) => x.chars).join(", "));
console.log(out.draft);
```

```
  round 1: 28 words → FAIL: Add one everyday example.
  round 2: 59 words → FAIL: Too long: 59 words, limit 40.
  round 3: 35 words → PASS
passed=true rounds=3 model calls=6
writer saw (chars): 85, 270, 441
Photosynthesis is how plants make food from light. Chlorophyll turns water and carbon dioxide into sugar and oxygen. For example, a plant on a sunny windowsill thrives, while one in a dark cupboard turns pale.
```

How the parts fit:

- **`round` has an adding reducer.** Each `generate` returns `round: 1`, and the reducer adds
  it to the total. The counter lives in state, so it survives checkpoints (Day 20).
- **`next` checks two things**: did it pass, and have we used up our rounds? Both lead to
  `END`. After the loop, check `out.passed` before you show the draft. A capped run that
  never passed should be flagged, not shipped as if it were fine.
- **The grader returns JSON.** With a real model, use `withStructuredOutput` and a Zod
  schema instead of `JSON.parse` ([Day 6](../week-01-foundations/day-06-output-parsers-structured-output.md)).
- **Could the grader be code?** Yes — both of today's rules are checkable with code, and code
  is free and exact. Use a model as the grader only for criteria that code cannot check,
  such as "is the example correct?" or "is the tone friendly?".

> 💡 **A bug in this probe taught the lesson.** The first scripted writer looked for the word
> "example" anywhere in the prompt. After round 2 the *draft itself* contained "For example",
> so the writer kept returning the 59-word draft. The run ended `passed=false rounds=3` — the
> cap stopped a loop that was stuck. Real loops get stuck too. The cap is what turns "stuck"
> into "flagged".

### 4.7 Measuring an agent's context, call by call

Now Part 2. The homework-help agent reads four chapters with a tool, then writes an exam
briefing. Each chapter is about 1,200 characters, with one key fact at the end. The scripted
model reads chapters 1–4 in turn. Then it reports which key facts it can still see.

```js
// ctx.js — context engineering: measure what each model call receives
import { createAgent, tool, contextEditingMiddleware, ClearToolUsesEdit } from "langchain";
import { AIMessage, HumanMessage } from "@langchain/core/messages";
import { z } from "zod";
import { FakeModel } from "./fake.js";

// ── the data: four chapters of notes, each with one fact the final answer needs ──
const FACTS = ["the exam is on 12 June", "calculators are not allowed",
  "Section B is worth 60% of the marks", "the 2023 paper is the best practice"];
const chapter = (n) =>
  `CHAPTER ${n}. ` + `Detailed background notes for chapter ${n}. `.repeat(28) +
  `KEY FACT ${n}: ${FACTS[n - 1]}.`;

const readChapter = tool(async ({ n }) => chapter(n), {
  name: "read_chapter",
  description: "Read one chapter of the course notes.",
  schema: z.object({ n: z.number() }),
});

// ── the scripted agent: read chapters 1-4, then answer from what it can still see ──
let id = 0;
const call = (name, args) =>
  new AIMessage({ content: "", tool_calls: [{ name, args, id: `c${id++}`, type: "tool_call" }] });
const factsVisible = (msgs) =>
  [...new Set(msgs.flatMap((m) => [...m.text.matchAll(/KEY FACT (\d)/g)].map((x) => x[1])))];
const reader = (toolName) => (_, msgs) => {
  const done = msgs.filter((m) => m.type === "tool").length;
  return done < 4 ? call(toolName, { n: done + 1 })
    : `Exam briefing. Facts I can see: ${factsVisible(msgs).join(", ") || "none"}`;
};
const SYSTEM = "You are StudyBuddy. Read all four chapters, then write an exam briefing.";
const ask = { messages: [new HumanMessage("Brief me for the exam.")] };
const report = (label, model, out) => {
  const chars = model.seen.map((s) => s.chars);
  console.log(`${label.padEnd(9)} chars per call: ${chars.join(", ").padEnd(32)} ` +
    `total ${chars.reduce((a, b) => a + b, 0)} · ${out.messages.at(-1).content}`);
};

// A. Baseline: every tool result stays in the window.
{
  const model = new FakeModel(reader("read_chapter"));
  const agent = createAgent({ model, tools: [readChapter], systemPrompt: SYSTEM });
  report("baseline", model, await agent.invoke(ask));
}
```

```
baseline  chars per call: 94, 1288, 2487, 3694, 4901       total 12464 · Exam briefing. Facts I can see: 1, 2, 3, 4
```

Each call is about 1,200 characters bigger than the one before: one more chapter. The total
is the sum of all five calls, because every call pays for its whole context. Characters are
a stand-in for tokens here; for English text, one token is roughly four characters
([Day 1](../week-01-foundations/day-01-llms-tokens-and-inference.md)).

### 4.8 Compress: clear old tool results

LangChain 1.x has middleware that replaces old tool results with a short placeholder once
the context passes a size you choose. Add this block to `ctx.js`:

```js
// B. Compress: clear old tool results once the context passes ~500 tokens.
{
  const model = new FakeModel(reader("read_chapter"));
  const agent = createAgent({
    model, tools: [readChapter], systemPrompt: SYSTEM,
    middleware: [contextEditingMiddleware({
      edits: [new ClearToolUsesEdit({ trigger: { tokens: 500 }, keep: { messages: 1 } })],
    })],
  });
  report("compress", model, await agent.invoke(ask));
}
```

```
compress  chars per call: 94, 1288, 1302, 1319, 1328       total 5331 · Exam briefing. Facts I can see: 4
```

- `trigger: { tokens: 500 }` — start clearing once the context is over about 500 tokens. The
  middleware estimates tokens from characters by default. Real apps use a much bigger number;
  500 keeps the demo small.
- `keep: { messages: 1 }` — always keep the most recent tool result.
- Cleared results become the text `[cleared]`.

The context stopped growing at about 1,300 characters. But the briefing lost three of its
four facts. **Compression needs a partner.** Exercise 4 adds a notebook (write) and a
`read_notes` tool (select), and all four facts come back.

> 🐞 **JavaScript and Python differ here** (measured). In JS, the `[cleared]` placeholder is
> written **into the agent's state**, so the original text is gone from the result and from
> any checkpoint. In Python, only the copy sent to the model is edited; the state keeps the
> full tool results. §6.3 explains why this matters.

### 4.9 Isolate: a sub-agent per chapter

The main agent no longer reads chapters. It calls `study_chapter`, which runs a sub-agent in
a fresh context and returns one line.

```js
// C. Isolate: a sub-agent reads each chapter in its OWN context and returns one line.
{
  const subModel = new FakeModel((_, msgs) => {
    const last = msgs.at(-1);
    if (last.type === "tool") return last.text.match(/KEY FACT \d: [^.]+/)[0];
    return call("read_chapter", { n: Number(last.text.match(/\d/)[0]) });
  });
  const sub = createAgent({ model: subModel, tools: [readChapter],
    systemPrompt: "Read the chapter. Reply with its key fact only." });
  const studyChapter = tool(async ({ n }) => {
    const r = await sub.invoke({ messages: [new HumanMessage(`Study chapter ${n}.`)] });
    return r.messages.at(-1).content;            // only the short report crosses back
  }, { name: "study_chapter", description: "Study one chapter; returns its key fact.",
       schema: z.object({ n: z.number() }) });

  const model = new FakeModel(reader("study_chapter"));
  const agent = createAgent({ model, tools: [studyChapter], systemPrompt: SYSTEM });
  report("isolate", model, await agent.invoke(ask));
  console.log(`          sub-agent chars per call: ${subModel.seen.map((s) => s.chars).join(", ")}`);
}
```

```
isolate   chars per call: 94, 128, 167, 214, 261           total 864 · Exam briefing. Facts I can see: 1, 2, 3, 4
          sub-agent chars per call: 63, 1257, 63, 1262, 63, 1270, 63, 1270
```

The main agent's biggest call fell from 4,901 to 261 characters, and it kept every fact. Each
sub-agent run is short: one call to ask for the chapter and one to read it. The sub-agent's
context is thrown away after each run, so chapter 1 never sits next to chapter 4.

This is the agent-as-a-tool design from Day 22, seen from the context side: **brief in,
report out, nothing else crosses**.

### 4.10 A minimal deep agent

`createDeepAgent` builds an agent with a file system, a `task` tool for sub-agents and
summarisation already wired in. This run adds the to-do list too.

```js
// A minimal deep agent: plan, a file-system scratchpad, and a sub-agent — all scripted
import { createDeepAgent } from "deepagents";
import { todoListMiddleware } from "langchain";
import { AIMessage, HumanMessage } from "@langchain/core/messages";
import { FakeModel } from "./fake.js";

let id = 0;
const call = (name, args) =>
  new AIMessage({ content: "", tool_calls: [{ name, args, id: `c${id++}`, type: "tool_call" }] });

const PLAN = [
  () => call("write_todos", { todos: [
    { content: "Find the key fact in chapter 1", status: "in_progress" },
    { content: "Write the briefing", status: "pending" }] }),
  () => call("task", { description: "Find the key fact in chapter 1.", subagent_type: "general-purpose" }),
  () => call("write_file", { file_path: "/notes.md", content: "KEY FACT 1: exam on 12 June" }),
  () => call("read_file", { file_path: "/notes.md" }),
];

const model = new FakeModel((_, msgs) => {
  if (msgs.find((m) => m.type === "human").text.startsWith("Find")) {
    return "KEY FACT 1: exam on 12 June";                // we are the sub-agent
  }
  const done = msgs.filter((m) => m.type === "tool").length;
  return done < PLAN.length ? PLAN[done]() : "Briefing: the exam is on 12 June.";
});

const agent = createDeepAgent({
  model, systemPrompt: "You are StudyBuddy.", middleware: [todoListMiddleware()],
});
const out = await agent.invoke({ messages: [new HumanMessage("Brief me for the exam.")] });

for (const m of out.messages.filter((m) => m.type === "tool")) {
  console.log(`  tool ${m.name.padEnd(12)} → ${JSON.stringify(m.text.slice(0, 60))}`);
}
console.log("answer:", out.messages.at(-1).text);
console.log("state keys:", Object.keys(out).sort().join(", "));
console.log("files:", Object.keys(out.files), "· todos:", out.todos.map((t) => t.status));
console.log("model calls:", model.calls, "· chars per call:", model.seen.map((s) => s.chars));
```

```
  tool write_todos  → "Updated todo list to [{\"content\":\"Find the key fact in chapt"
  tool task         → "KEY FACT 1: exam on 12 June"
  tool write_file   → "Successfully wrote to '/notes.md'"
  tool read_file    → "@@ lines 1-1 of 1 @@\nKEY FACT 1: exam on 12 June"
answer: Briefing: the exam is on 12 June.
state keys: files, messages, todos
files: [ '/notes.md' ] · todos: [ 'in_progress', 'pending' ]
model calls: 6 · chars per call: [ 1118, 1260, 139, 1287, 1320, 1368 ]
```

Read the `chars per call` line. Call 3 (139 characters) is the **sub-agent**: it saw only its
task, not the main agent's 1,260-character context. The other calls start at 1,118 because
the to-do middleware adds its own instructions to the system prompt. That is the "detailed
system prompt" part of a deep agent, and it costs tokens on every call.

> ⚠️ **The fake ignores the tool list**, so this proves the wiring, not the judgement. A real
> deep agent is only as good as its model's choices about when to plan, write and delegate.
> `deepagents` moves fast: check the tool list and defaults for your version.

---

## 5. Code — Python

```bash
pip install langgraph langchain langchain-core
pip install deepagents          # only for §5.10
```

Verified with `langgraph` 1.2.14, `langchain-core` 1.6.7, `langchain` 1.4.3 and
`deepagents` 0.7.22, on Python 3.14.

### 5.1 A keyless model for today

```python
# fake.py — a keyless stand-in for a chat model.
# reply(last_text, messages) returns a string (or a whole AIMessage, for tool calls).
import time
from typing import Any, Callable
from pydantic import Field
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class FakeModel(BaseChatModel):
    reply: Callable[..., Any]
    delay_s: float = 0.0
    calls: int = 0
    seen: list = Field(default_factory=list)   # message count and characters per call

    @property
    def _llm_type(self) -> str:
        return "fake"

    def bind_tools(self, tools, **kwargs):     # agents call this; the fake ignores it
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls += 1
        chars = sum(len(m.text) for m in messages)        # .text flattens content blocks
        self.seen.append({"messages": len(messages), "chars": chars})
        if self.delay_s:
            time.sleep(self.delay_s)
        out = self.reply(messages[-1].text, messages)
        message = AIMessage(content=out) if isinstance(out, str) else out
        return ChatResult(generations=[ChatGeneration(message=message)])
```

> 🎯 **With a real model:** use `ChatGroq(model="openai/gpt-oss-120b")` from
> `langchain_groq` in place of each `FakeModel(...)`. Not executed here (no API key).

### 5.2 Prompt chaining with a gate

```python
# Pattern 1 — prompt chaining with a gate
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from fake import FakeModel

model = FakeModel(reply=lambda p, msgs:
    "- not sure" if "quantum foam" in p
    else "- what a cell is\n- the nucleus\n- the membrane" if p.startswith("Outline")
    else "A cell is the smallest living unit. The nucleus holds the DNA. The membrane controls what enters."
    if p.startswith("Write")
    else "Cells are tiny living rooms: the nucleus is the office, the membrane is the door.")


class State(TypedDict, total=False):
    topic: str
    outline: str
    draft: str
    final: str


def outline(s: State) -> dict:
    return {"outline": model.invoke(f"Outline 3 points a beginner needs about: {s['topic']}").content}


# The gate is plain code: no model call, no cost, fully predictable.
def gate(s: State) -> str:
    bullets = [l for l in s["outline"].split("\n") if l.startswith("- ")]
    return "write" if len(bullets) >= 3 else END


def write(s: State) -> dict:
    return {"draft": model.invoke(f"Write one paragraph that covers:\n{s['outline']}").content}


def simplify(s: State) -> dict:
    return {"final": model.invoke(f"Rewrite for a 12-year-old:\n{s['draft']}").content}


b = StateGraph(State)
b.add_node("make_outline", outline)
b.add_node("write", write)
b.add_node("simplify", simplify)
b.add_edge(START, "make_outline")
b.add_conditional_edges("make_outline", gate, ["write", END])
b.add_edge("write", "simplify")
b.add_edge("simplify", END)
chain = b.compile()

out = chain.invoke({"topic": "animal cells"})
print(out["final"])
print("model calls:", model.calls)

stopped = chain.invoke({"topic": "quantum foam"})
print(stopped.get("final"), "| total model calls:", model.calls)
```

```
Cells are tiny living rooms: the nucleus is the office, the membrane is the door.
model calls: 3
None | total model calls: 4
```

`stopped.get("final")` is `None` because a `TypedDict` key that no node wrote is simply
absent from the result.

### 5.3 Routing

```python
# Pattern 2 — routing
import re
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from fake import FakeModel


# The router model answers with ONE label. A real model gets the same instruction.
def pick_label(prompt: str) -> str:
    q = prompt.split("Question:")[1]
    return "maths" if re.search(r"\d", q) else "essay" if re.search(r"essay|write", q, re.I) else "general"


router = FakeModel(reply=lambda p, msgs: pick_label(p))
experts = {name: FakeModel(reply=lambda p, msgs, n=label: f"[{n}] answered")
           for name, label in [("maths", "maths tutor"), ("essay", "essay coach"),
                               ("general", "general helper")]}


class State(TypedDict, total=False):
    question: str
    label: str
    answer: str


def classify(s: State) -> dict:
    out = router.invoke(
        f"Label this question as exactly one of: maths, essay, general.\nQuestion: {s['question']}")
    return {"label": out.content.strip()}


def answer_with(name):
    def node(s: State) -> dict:
        return {"answer": experts[name].invoke(s["question"]).content}
    return node


b = StateGraph(State)
b.add_node("classify", classify)
for name in ["maths", "essay", "general"]:
    b.add_node(name, answer_with(name))
    b.add_edge(name, END)
b.add_edge(START, "classify")
b.add_conditional_edges("classify", lambda s: s["label"], ["maths", "essay", "general"])
app = b.compile()

for q in ["What is 12 x 7?", "Check my essay intro", "Why is the sky blue?"]:
    out = app.invoke({"question": q})
    print(f"{q:<22} → {out['label']:<8} {out['answer']}")
```

```
What is 12 x 7?        → maths    [maths tutor] answered
Check my essay intro   → essay    [essay coach] answered
Why is the sky blue?   → general  [general helper] answered
```

### 5.4 Parallelisation (sectioning)

```python
# Pattern 3 — parallelisation (sectioning)
import operator
import time
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from fake import FakeModel

# Each fake call takes 0.3 s, like a short real model call.
model = FakeModel(reply=lambda p, msgs: f"{p.split(':')[0]} done", delay_s=0.3)


class State(TypedDict, total=False):
    notes: str
    parts: Annotated[list[str], operator.add]     # all 3 results
    pack: str


def section(name, task):
    def node(s: State) -> dict:
        reply = model.invoke(f"{task}: {s['notes']}").content
        return {"parts": [f"{name}: {reply}"]}
    return node


b = StateGraph(State)
b.add_node("summary", section("summary", "Summarise"))
b.add_node("quiz", section("quiz", "Write 3 quiz questions"))
b.add_node("cards", section("cards", "Write 5 flashcards"))
b.add_node("combine", lambda s: {"pack": " | ".join(sorted(s["parts"]))})
for name in ["summary", "quiz", "cards"]:
    b.add_edge(START, name)
b.add_edge(["summary", "quiz", "cards"], "combine")    # wait for all three
b.add_edge("combine", END)
app = b.compile()

t0 = time.perf_counter()
out = app.invoke({"notes": "Photosynthesis turns light into sugar."})
print(out["pack"])
print(f"3 model calls in {(time.perf_counter() - t0) * 1000:.0f} ms")
```

```
cards: Write 5 flashcards done | quiz: Write 3 quiz questions done | summary: Summarise done
3 model calls in 413 ms
```

A second run took 323 ms. Python runs the three synchronous nodes on worker threads, so the
`time.sleep` calls overlap. Without the `operator.add` reducer the run fails (measured):
`InvalidUpdateError: At key 'parts': Can receive only one value per step. Use an Annotated
key to handle multiple values.`

### 5.5 Orchestrator-workers

```python
# Pattern 4 — orchestrator-workers
import json
import operator
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from fake import FakeModel

# The orchestrator decides the subtasks at run time. A real model returns this JSON too.
PLANS = {
    "photosynthesis": ["light reactions", "Calvin cycle"],
    "the French Revolution": ["causes", "the Terror", "Napoleon", "legacy"],
}
orchestrator = FakeModel(reply=lambda p, msgs: json.dumps(PLANS[p.split("TOPIC: ")[1]]))
worker = FakeModel(reply=lambda p, msgs: f"notes on {p.split('SUBTOPIC: ')[1]}")


class State(TypedDict, total=False):
    topic: str
    subtopics: list[str]
    notes: Annotated[list[dict], operator.add]
    guide: str


def plan(s: State) -> dict:
    out = orchestrator.invoke(
        "Split this revision topic into 2-5 subtopics. Reply with a JSON list.\n"
        f"TOPIC: {s['topic']}")
    return {"subtopics": json.loads(out.content)}


# One Send per subtopic: the number of workers is decided by the plan, not by you.
def assign(s: State):
    return [Send("work", {"sub": sub, "i": i}) for i, sub in enumerate(s["subtopics"])]


def work(payload: dict) -> dict:
    text = worker.invoke(f"Write revision notes. SUBTOPIC: {payload['sub']}").content
    return {"notes": [{"i": payload["i"], "text": text}]}


def synthesise(s: State) -> dict:
    return {"guide": "; ".join(n["text"] for n in sorted(s["notes"], key=lambda n: n["i"]))}


b = StateGraph(State)
b.add_node("plan", plan)
b.add_node("work", work)
b.add_node("synthesise", synthesise)
b.add_edge(START, "plan")
b.add_conditional_edges("plan", assign, ["work"])
b.add_edge("work", "synthesise")
b.add_edge("synthesise", END)
app = b.compile()

for topic in PLANS:
    before = worker.calls
    out = app.invoke({"topic": topic})
    print(f"{topic}: {worker.calls - before} workers → {out['guide']}")
```

```
photosynthesis: 2 workers → notes on light reactions; notes on Calvin cycle
the French Revolution: 4 workers → notes on causes; notes on the Terror; notes on Napoleon; notes on legacy
```

### 5.6 Evaluator-optimizer — the full loop

```python
# Pattern 5 — evaluator-optimizer: generate → evaluate → revise, with a cap
import json
import operator
import re
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from fake import FakeModel

D1 = ("Photosynthesis is how green plants make their own food. Inside the leaf, chlorophyll "
      "captures light and uses it to turn water and carbon dioxide into glucose, releasing oxygen.")
D2 = D1 + (" For example, a sunflower in a sunny garden grows taller every week because its "
           "leaves make glucose all day, while a plant left in a dark cupboard turns pale and weak.")
D3 = ("Photosynthesis is how plants make food from light. Chlorophyll turns water and carbon "
      "dioxide into sugar and oxygen. For example, a plant on a sunny windowsill thrives, while "
      "one in a dark cupboard turns pale.")


# The generator: a scripted writer that improves when it gets feedback.
def write_reply(p, msgs):
    if "FEEDBACK:" not in p:
        return D1
    return D2 if "example" in p.split("FEEDBACK:")[1] else D3


writer = FakeModel(reply=write_reply)


# The evaluator: checks two clear criteria and replies with JSON.
def words(t: str) -> int:
    return len(t.split())


def judge_reply(p, msgs):
    draft = p.split("DRAFT:\n")[1]
    if not re.search(r"for example", draft, re.I):
        return json.dumps({"pass": False, "feedback": "Add one everyday example."})
    if words(draft) > 40:
        return json.dumps({"pass": False, "feedback": f"Too long: {words(draft)} words, limit 40."})
    return json.dumps({"pass": True, "feedback": ""})


judge = FakeModel(reply=judge_reply)


class State(TypedDict, total=False):
    task: str
    draft: str
    feedback: str
    passed: bool
    round: Annotated[int, operator.add]


def generate(s: State) -> dict:
    if s.get("feedback"):
        prompt = ("Revise the draft. Fix only what the feedback asks.\n"
                  f"DRAFT: {s['draft']}\nFEEDBACK: {s['feedback']}")
    else:
        prompt = f"Explain for a beginner in at most 40 words, with one everyday example: {s['task']}"
    return {"draft": writer.invoke(prompt).content, "round": 1}


def evaluate(s: State) -> dict:
    verdict = json.loads(judge.invoke(
        "Criteria: (1) one everyday example, (2) at most 40 words.\n"
        f"Reply JSON {{pass, feedback}}.\nDRAFT:\n{s['draft']}").content)
    status = "PASS" if verdict["pass"] else "FAIL: " + verdict["feedback"]
    print(f"  round {s['round']}: {words(s['draft'])} words → {status}")
    return {"passed": verdict["pass"], "feedback": verdict["feedback"]}


MAX_ROUNDS = 3


def next_step(s: State) -> str:
    return END if s["passed"] or s["round"] >= MAX_ROUNDS else "generate"


b = StateGraph(State)
b.add_node("generate", generate)
b.add_node("evaluate", evaluate)
b.add_edge(START, "generate")
b.add_edge("generate", "evaluate")
b.add_conditional_edges("evaluate", next_step, ["generate", END])
app = b.compile()

out = app.invoke({"task": "photosynthesis", "round": 0})
print(f"passed={out['passed']} rounds={out['round']} model calls={writer.calls + judge.calls}")
print("writer saw (chars):", ", ".join(str(x["chars"]) for x in writer.seen))
print(out["draft"])
```

```
  round 1: 28 words → FAIL: Add one everyday example.
  round 2: 59 words → FAIL: Too long: 59 words, limit 40.
  round 3: 35 words → PASS
passed=True rounds=3 model calls=6
writer saw (chars): 85, 270, 441
Photosynthesis is how plants make food from light. Chlorophyll turns water and carbon dioxide into sugar and oxygen. For example, a plant on a sunny windowsill thrives, while one in a dark cupboard turns pale.
```

> ⚠️ **Pass `"round": 0` at the start in Python.** A `TypedDict` key with a reducer has no
> starting value until something writes it, and `next_step` reads `s["round"]`. The JS
> `default: () => 0` handles this for you.

### 5.7 Measuring an agent's context, call by call

```python
# ctx.py — context engineering: measure what each model call receives
import itertools
import re
from langchain.agents import create_agent
from langchain.agents.middleware import ContextEditingMiddleware, ClearToolUsesEdit
from langchain.tools import tool
from langchain_core.messages import AIMessage, HumanMessage
from fake import FakeModel

# ── the data: four chapters of notes, each with one fact the final answer needs ──
FACTS = ["the exam is on 12 June", "calculators are not allowed",
         "Section B is worth 60% of the marks", "the 2023 paper is the best practice"]


def chapter(n: int) -> str:
    return (f"CHAPTER {n}. " + f"Detailed background notes for chapter {n}. " * 28
            + f"KEY FACT {n}: {FACTS[n - 1]}.")


@tool
def read_chapter(n: int) -> str:
    """Read one chapter of the course notes."""
    return chapter(n)


# ── the scripted agent: read chapters 1-4, then answer from what it can still see ──
ids = itertools.count()


def call(name, args):
    return AIMessage(content="", tool_calls=[
        {"name": name, "args": args, "id": f"c{next(ids)}", "type": "tool_call"}])


def facts_visible(msgs):
    return sorted({f for m in msgs for f in re.findall(r"KEY FACT (\d)", m.text)})


def reader(tool_name):
    def reply(_, msgs):
        done = sum(1 for m in msgs if m.type == "tool")
        if done < 4:
            return call(tool_name, {"n": done + 1})
        return f"Exam briefing. Facts I can see: {', '.join(facts_visible(msgs)) or 'none'}"
    return reply


SYSTEM = "You are StudyBuddy. Read all four chapters, then write an exam briefing."
ASK = {"messages": [HumanMessage("Brief me for the exam.")]}


def report(label, model, out):
    chars = [s["chars"] for s in model.seen]
    print(f"{label:<9} chars per call: {', '.join(map(str, chars)):<32} "
          f"total {sum(chars)} · {out['messages'][-1].content}")


# A. Baseline: every tool result stays in the window.
model = FakeModel(reply=reader("read_chapter"))
agent = create_agent(model, [read_chapter], system_prompt=SYSTEM)
report("baseline", model, agent.invoke(ASK))
```

```
baseline  chars per call: 94, 1288, 2487, 3694, 4901       total 12464 · Exam briefing. Facts I can see: 1, 2, 3, 4
```

The numbers match JavaScript character for character: the same prompts produce the same
context.

### 5.8 Compress: clear old tool results

```python
# B. Compress: clear old tool results once the context passes ~500 tokens.
model = FakeModel(reply=reader("read_chapter"))
agent = create_agent(model, [read_chapter], system_prompt=SYSTEM, middleware=[
    ContextEditingMiddleware(edits=[ClearToolUsesEdit(trigger=500, keep=1)])])
report("compress", model, agent.invoke(ASK))
```

```
compress  chars per call: 94, 1288, 1302, 1319, 1328       total 5331 · Exam briefing. Facts I can see: 4
```

Python's `ClearToolUsesEdit` takes plain numbers: `trigger=500` tokens and `keep=1` tool
result. JavaScript takes objects: `trigger: { tokens: 500 }`, `keep: { messages: 1 }`.

### 5.9 Isolate: a sub-agent per chapter

```python
# C. Isolate: a sub-agent reads each chapter in its OWN context and returns one line.
def sub_reply(_, msgs):
    last = msgs[-1]
    if last.type == "tool":
        return re.search(r"KEY FACT \d: [^.]+", last.text).group(0)
    return call("read_chapter", {"n": int(re.search(r"\d", last.text).group(0))})


sub_model = FakeModel(reply=sub_reply)
sub = create_agent(sub_model, [read_chapter],
                   system_prompt="Read the chapter. Reply with its key fact only.")


@tool
def study_chapter(n: int) -> str:
    """Study one chapter; returns its key fact."""
    r = sub.invoke({"messages": [HumanMessage(f"Study chapter {n}.")]})
    return r["messages"][-1].content          # only the short report crosses back


model = FakeModel(reply=reader("study_chapter"))
agent = create_agent(model, [study_chapter], system_prompt=SYSTEM)
report("isolate", model, agent.invoke(ASK))
print(f"          sub-agent chars per call: {', '.join(str(s['chars']) for s in sub_model.seen)}")
```

```
isolate   chars per call: 94, 128, 167, 214, 261           total 864 · Exam briefing. Facts I can see: 1, 2, 3, 4
          sub-agent chars per call: 63, 1257, 63, 1262, 63, 1270, 63, 1270
```

### 5.10 A minimal deep agent

```python
# A minimal deep agent: plan, a file-system scratchpad, and a sub-agent — all scripted
import itertools
from deepagents import create_deep_agent
from langchain.agents.middleware import TodoListMiddleware
from langchain_core.messages import AIMessage, HumanMessage
from fake import FakeModel

ids = itertools.count()


def call(name, args):
    return AIMessage(content="", tool_calls=[
        {"name": name, "args": args, "id": f"c{next(ids)}", "type": "tool_call"}])


PLAN = [
    lambda: call("write_todos", {"todos": [
        {"content": "Find the key fact in chapter 1", "status": "in_progress"},
        {"content": "Write the briefing", "status": "pending"}]}),
    lambda: call("task", {"description": "Find the key fact in chapter 1.",
                          "subagent_type": "general-purpose"}),
    lambda: call("write_file", {"file_path": "/notes.md", "content": "KEY FACT 1: exam on 12 June"}),
    lambda: call("read_file", {"file_path": "/notes.md"}),
]


def reply(_, msgs):
    first_human = next(m for m in msgs if m.type == "human").text
    if first_human.startswith("Find"):                  # we are the sub-agent
        return "KEY FACT 1: exam on 12 June"
    done = sum(1 for m in msgs if m.type == "tool")
    return PLAN[done]() if done < len(PLAN) else "Briefing: the exam is on 12 June."


model = FakeModel(reply=reply)
agent = create_deep_agent(model=model, system_prompt="You are StudyBuddy.",
                          middleware=[TodoListMiddleware()])
out = agent.invoke({"messages": [HumanMessage("Brief me for the exam.")]})

for m in out["messages"]:
    if m.type == "tool":
        print(f"  tool {m.name:<12} → {m.text[:60]!r}")
print("answer:", out["messages"][-1].text)
print("state keys:", sorted(out.keys()))
print("files:", list(out["files"].keys()), "· todos:", [t["status"] for t in out["todos"]])
print("model calls:", model.calls, "· chars per call:", [s["chars"] for s in model.seen])
```

```
  tool write_todos  → "Updated todo list to [{'content': 'Find the key fact in chap"
  tool task         → 'KEY FACT 1: exam on 12 June'
  tool write_file   → 'Updated file /notes.md'
  tool read_file    → '@@ lines 1-1 of 1 @@\nKEY FACT 1: exam on 12 June'
answer: Briefing: the exam is on 12 June.
state keys: ['files', 'messages', 'todos']
files: ['/notes.md'] · todos: ['in_progress', 'pending']
model calls: 6 · chars per call: [1413, 1562, 317, 1589, 1611, 1659]
```

Same shape as JavaScript, different details: the `write_file` message differs, and the
Python to-do prompt is longer (1,413 against 1,118 characters on the first call).

### 5.11 The JS ↔ Python translation for today

| Concept | JavaScript | Python |
|---|---|---|
| State with an adding counter | `round: Annotation({ reducer: (a, b) => a + b, default: () => 0 })` | `round: Annotated[int, operator.add]` (pass `"round": 0` at the start) |
| Gate / router edge | `.addConditionalEdges("a", fn, ["b", END])` | `b.add_conditional_edges("a", fn, ["b", END])` |
| Join after a fan-out | `.addEdge(["x", "y", "z"], "combine")` | `b.add_edge(["x", "y", "z"], "combine")` |
| Orchestrator fan-out | `new Send("work", payload)` | `Send("work", payload)` |
| Node named like a state key | **error**: "already being used as a state attribute" | accepted (measured) |
| Unknown route label | `Error: Branch condition returned unknown or null destination` | `KeyError: 'history'` |
| Default recursion limit | 25 | **10,007** (`LANGGRAPH_DEFAULT_RECURSION_LIMIT`) |
| Agent | `createAgent({ model, tools, systemPrompt, middleware })` | `create_agent(model, tools, system_prompt=..., middleware=[...])` |
| Clear old tool results | `contextEditingMiddleware({ edits: [new ClearToolUsesEdit({ trigger: { tokens: 500 }, keep: { messages: 1 } })] })` | `ContextEditingMiddleware(edits=[ClearToolUsesEdit(trigger=500, keep=1)])` |
| Where clearing happens | written **into state** | only in the request sent to the model |
| Message text / type | `m.text`, `m.type` | `m.text`, `m.type` |
| To-do list | `todoListMiddleware()` from `langchain` | `TodoListMiddleware()` from `langchain.agents.middleware` |
| Deep agent | `createDeepAgent({ model, systemPrompt, middleware })` from `deepagents` | `create_deep_agent(model=..., system_prompt=..., middleware=[...])` |

---

## 6. Under the hood

### 6.1 The cost model of each pattern

The patterns differ in how many calls they make and whether those calls wait for each other.
With *c* as the time of one model call:

| Pattern | Calls | Wall-clock time | Measured today |
|---|---|---|---|
| Single call | 1 | c | — |
| Prompt chaining, k steps | k | k·c | 3 calls; 1 when the gate stopped it |
| Routing | 2 | 2c | 1 router + 1 expert |
| Parallelisation, k parts | k | about c | 3 calls in 318–413 ms, with c = 300 ms |
| Orchestrator-workers, N parts | 1 + N (+1 if a model synthesises) | about 2c | N = 2 and N = 4 from the same graph |
| Evaluator-optimizer, r rounds | 2r | 2r·c | r = 3: 6 calls |
| Agent, t tool calls | t + 1 | (t + 1)·c, plus tools | t = 4: 5 calls |

Two lessons hide in this table. First, only the workflows have a fixed or bounded number of
calls, so only they have a predictable bill. Second, the evaluator-optimizer is the most
expensive workflow per answer. Use it where quality really pays: an answer shown to many
students, not a quick chat reply.

### 6.2 Why agent context costs grow faster than you expect

An agent re-sends its whole history on every call. If each tool result adds about *d*
characters, call *k* carries about *k·d* of them. The total over *n* calls is the sum
d + 2d + … + n·d, which grows with the **square** of *n*. Today's baseline shows the shape:
each call added about 1,200 characters, and the five calls sent 12,464 in total.

Compression and isolation both flatten this curve, in different ways:

```
   chars per call        baseline   ▁ ▂ ▄ ▆ █     grows every call
                         compress   ▁ ▂ ▂ ▂ ▂     flat after the trigger
                         isolate    ▁ ▁ ▁ ▁ ▁     main stays tiny; sub-agents start fresh
```

Prompt caching ([Day 34](../week-05-the-model-layer/day-34-cost-and-latency.md)) lowers the
*price* of re-sending the same start of the prompt, but it does nothing for context rot.
Provider caches match the prompt from the beginning, so clearing an old tool result changes
everything after it. The cached part then no longer matches. Not measured here: check your
provider's cache report before you combine the two.

### 6.3 Where the clearing happens: state or request

The measured difference from §4.8 has real consequences.

| | JavaScript (`langchain` 1.5.15) | Python (`langchain` 1.4.3) |
|---|---|---|
| What gets edited | the messages **in state** | a copy, sent to the model only |
| Tool results in `out.messages` afterwards | `[cleared]` (9 characters) | full text (about 1,200 characters each) |
| Checkpoint after the run (inferred from state; not run with a checkpointer) | would hold the placeholder | would hold the full text |
| Next call's trigger check | sees the smaller, already-cleared state | sees the full state again |

Exercise 4 shows the effect on cost. With the same script, JavaScript sent 9,790 characters
in total and Python sent 7,406. Python re-checks the full history on every call, so it
clears more often. JavaScript's state shrinks once, so later calls stay under the trigger.

Which is better? Python's way keeps the full record for debugging and audits. JavaScript's
way keeps your checkpoints small. If you need the full text later in JavaScript, **write**
it somewhere first.

### 6.4 Why loops need your own counter

The recursion limit counts **supersteps**, not rounds. Each evaluator round uses two
(generate, then evaluate). So JS's 25 allowed 12 full rounds and part of a 13th: the writer
ran 13 times. Python's default of 10,007 allowed 5,004 writer calls.

A recursion limit is a smoke alarm, not a plan. It throws an error, and without a
checkpointer you lose the run's result. A counter in state lets you end cleanly, keep the best draft, and mark it
`passed=false` so the caller can decide what to do.

### 6.5 What `deepagents` adds, and what it costs

The source of both packages (Python 0.7.22, JS 1.14.2) shows the same default stack. It has
file-system middleware and sub-agent middleware (the `task` tool, with a "general-purpose"
sub-agent). It also has summarisation and a fix-up step for broken tool calls. The Python source also
lists prompt-caching middleware, which does nothing for models that don't support it. In Python
0.7 the old built-in system prompt was deprecated. In both, the to-do list is not on by
default.

What it costs: more tools in every call (eight before you add your own), and longer system
prompts. A deep agent is worth that only for long, open-ended jobs. For the jobs in §4.2–4.6
it is the wrong tool — those have known steps.

> 📚 **Sources**
>
> - Erik Schluntz and Barry Zhang, "Building Effective Agents", Anthropic, 19 December 2024 —
>   https://www.anthropic.com/engineering/building-effective-agents
> - LangChain team, "Context Engineering for Agents", LangChain blog, 2025 —
>   https://www.langchain.com/blog/context-engineering-for-agents
> - Anthropic, "Effective context engineering for AI agents", 29 September 2025 —
>   https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
> - Harrison Chase, "Deep Agents", LangChain blog, 30 July 2025 —
>   https://www.langchain.com/blog/deep-agents

---

## 7. Common mistakes

### ❌ 1. Building an agent when the steps are known

```js
// ❌ "let the model work it out" — for a job that is always outline → write → simplify
const agent = createAgent({ model, tools: [outlineTool, writeTool, simplifyTool] });

// ✅ draw the flowchart: three nodes, two edges, one code gate (§4.2)
```

**Symptom:** the call count and the order of steps change from run to run, so cost and
quality change too. **Fix:** ask "can I write the steps down first?" If yes, build a workflow.

### ❌ 2. A loop with no cap

```python
# ❌ the only way out is a pass
def next_step(s):
    return END if s["passed"] else "generate"

# ✅ a counter in state, checked every round
def next_step(s):
    return END if s["passed"] or s["round"] >= MAX_ROUNDS else "generate"
```

**Symptom (measured, grader that never passes):** JS stops with `GraphRecursionError:
Recursion limit of 25 reached without hitting a stop condition` after **13** writer calls.
Python stops with `Recursion limit of 10007 reached` after **5,004** writer calls.

### ❌ 3. A grader with no real criteria

```js
// ❌ "Is this good? Reply pass or fail."  → the grader says pass to almost anything
// ✅ "Criteria: (1) one everyday example, (2) at most 40 words."
```

**Symptom (measured, grader that always passes):** `rounds=1 calls=2 words=28
hasExample=false`. You paid for a grader and shipped the draft that breaks the rules.
**Fix:** write criteria you could check by hand. Check with code where you can.

### ❌ 4. A route label with no edge

```js
// ❌ the model replies "history", or "Maths", or "maths."
.addConditionalEdges("classify", (s) => s.label, ["maths", "essay", "general"])

// ✅ normalise the label and give unknown labels a home
const ROUTES = new Set(["maths", "essay", "general"]);
.addConditionalEdges("classify", (s) => {
  const label = s.label.trim().toLowerCase().replace(/[^a-z]/g, "");
  return ROUTES.has(label) ? label : "general";
}, ["maths", "essay", "general"])
```

**Symptom (measured):** JS `Error: Branch condition returned unknown or null destination`;
Python `KeyError: 'history'`. The same error appeared with an object or dict path map. With
the fix, `"Maths."` went to `maths` and `"history"` went to `general` (measured in JS).

### ❌ 5. A node with the same name as a state key

```js
// ❌ state has `outline`, and so does the node
.addNode("outline", outline)
// ✅
.addNode("make_outline", outline)
```

**Symptom (measured):** JS throws `outline is already being used as a state attribute (a.k.a.
a channel), cannot also be used as a node name.` Python accepted the same graph and ran it.
Code that runs in Python can fail when you port it, so use different names in both.

### ❌ 6. Giving the writer the whole history of drafts

```python
# ❌ every old draft and every old critique, every round
prompt = "\n".join(all_drafts_and_feedback) + "\nRevise."
# ✅ only what this round needs (§5.6)
prompt = f"Revise the draft. Fix only what the feedback asks.\nDRAFT: {s['draft']}\nFEEDBACK: {s['feedback']}"
```

**Symptom:** the revise prompt grows every round, and old feedback that was already fixed
can pull the writer backwards. In §4.6 the writer saw 85, 270 and 441 characters: only the
latest draft and the latest feedback.

### ❌ 7. Compressing before you have written anything down

```python
# ❌ clear old tool results — and the facts inside them
ContextEditingMiddleware(edits=[ClearToolUsesEdit(trigger=500, keep=1)])
# ✅ save what matters first (a notebook tool), then clear (Exercise 4)
```

**Symptom (measured):** `Facts I can see: 4` instead of `1, 2, 3, 4`. Nothing failed, so no
error tells you. Only an evaluation of the final answer (Day 25) catches it.

### ❌ 8. A scripted router test that reads the instructions

```js
// ❌ the fake searches the WHOLE prompt — which includes "maths, essay, general"
const router = new FakeModel((p) => (/essay/i.test(p) ? "essay" : "general"));
// ✅ the fake reads only the user's question
const router = new FakeModel((p) => (/essay/i.test(p.split("Question:")[1]) ? "essay" : "general"));
```

**Symptom (measured, first version of §4.3):** `Why is the sky blue? → essay`. The list of
labels in the instructions contained the word "essay". Real models make the same kind of
mistake when an example in the prompt looks like the input. Test your fakes as well as your
graph.

### ❌ 9. Parallel nodes writing to a key with no reducer

```python
# ❌ three nodes write `parts` in the same step
parts: list[str]
# ✅
parts: Annotated[list[str], operator.add]
```

**Symptom (measured):** Python `InvalidUpdateError: At key 'parts': Can receive only one
value per step.` JS `InvalidUpdateError: ... LastValue can only receive one value per step.`
The same error appears with a `Send` fan-out.

---

## 8. Exercises

### Exercise 1 — Pick the pattern ●○○○○

No code. For each StudyBuddy request, name the simplest thing that works: **single call**,
one of the **five patterns**, or an **agent**. Give a one-line reason.

1. "Turn this one fact into a flashcard."
2. "Give feedback on my essay": check the structure, then comment, then soften the tone.
3. "Make a revision pack from these notes": summary, quiz and flashcards.
4. "Make a revision guide for *any* topic I type."
5. "Explain osmosis": at most 40 words, one everyday example, no jargon.
6. "Help with my homework": may need the calculator, a web search and my past marks.
7. "Is this quiz answer correct?" — and you want more confidence than one opinion.
8. A message box where students type anything: a question, an essay or a sum.

<details>
<summary>✅ Solution</summary>

| # | Pick | Why |
|---|---|---|
| 1 | **Single call** | One input, one output, no checks needed. Any pattern adds cost for nothing. |
| 2 | **Prompt chaining** | Three fixed steps in a fixed order. A code gate can stop early if the essay has no paragraphs. |
| 3 | **Parallelisation (sectioning)** | The three parts don't depend on each other, so run them at once (§4.4: ~0.3 s, not ~0.9 s). |
| 4 | **Orchestrator-workers** | The number of subtopics depends on the topic: 2 for photosynthesis, 4 for the French Revolution (§4.5). |
| 5 | **Evaluator-optimizer** | The criteria are clear and checkable, and revising helps (§4.6: passed in round 3). |
| 6 | **Agent** | The next step depends on what the tools return. You can't draw the flowchart in advance. |
| 7 | **Parallelisation (voting)** | Same task, several runs, take the majority (Exercise 2). |
| 8 | **Routing** | Different kinds of input need different prompts. Put it in front of the others. |

The pattern in the answers: **known steps → workflow; unknown steps → agent**. Only one of
the eight needs an agent.
</details>

### Exercise 2 — Voting: three graders, one verdict ●●○○○

Build the voting flavour of parallelisation. Three graders judge the same answer at the same
time; a `tally` node takes the majority. Use `Send` to start the three graders. Make grader 2
disagree, and check that the verdict is still ACCEPT. Time the run: does it take about one
call's time or three?

<details>
<summary>✅ Solution</summary>

**JavaScript**

```js
// Exercise 2 — parallelisation, the voting flavour
import { StateGraph, Annotation, Send, START, END } from "@langchain/langgraph";
import { FakeModel } from "./fake.js";

// Three independent graders. Voter 2 is the odd one out, as real samples sometimes are.
const grader = new FakeModel((p) => (p.includes("VOTER 2") ? "no" : "yes"), { delayMs: 300 });

const State = Annotation.Root({
  question: Annotation(), answer: Annotation(),
  votes: Annotation({ reducer: (a, b) => a.concat(b), default: () => [] }),
  verdict: Annotation(),
});

const fanOut = (s) => [0, 1, 2].map((i) => new Send("vote", { ...s, voter: i }));
const vote = async (s) => {
  const r = await grader.invoke(
    `VOTER ${s.voter}. Is this answer correct? Reply yes or no.\nQ: ${s.question}\nA: ${s.answer}`);
  return { votes: [r.content.trim()] };
};
const tally = (s) => {
  const yes = s.votes.filter((v) => v === "yes").length;
  return { verdict: `${yes}/${s.votes.length} yes → ${yes * 2 > s.votes.length ? "ACCEPT" : "REJECT"}` };
};

const app = new StateGraph(State)
  .addNode("vote", vote).addNode("tally", tally)
  .addConditionalEdges(START, fanOut, ["vote"])
  .addEdge("vote", "tally").addEdge("tally", END)
  .compile();

const t0 = Date.now();
const out = await app.invoke({ question: "What is 7 x 8?", answer: "56" });
console.log(out.verdict, `· ${grader.calls} calls in ${Date.now() - t0} ms`);
```

**Python**

```python
# Exercise 2 — parallelisation, the voting flavour
import operator
import time
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from fake import FakeModel

# Three independent graders. Voter 2 is the odd one out, as real samples sometimes are.
grader = FakeModel(reply=lambda p, m: "no" if "VOTER 2" in p else "yes", delay_s=0.3)


class State(TypedDict, total=False):
    question: str
    answer: str
    voter: int
    votes: Annotated[list[str], operator.add]
    verdict: str


def fan_out(s: State):
    return [Send("vote", {**s, "voter": i}) for i in range(3)]


def vote(s: State) -> dict:
    r = grader.invoke(f"VOTER {s['voter']}. Is this answer correct? Reply yes or no.\n"
                      f"Q: {s['question']}\nA: {s['answer']}")
    return {"votes": [r.content.strip()]}


def tally(s: State) -> dict:
    yes = s["votes"].count("yes")
    return {"verdict": f"{yes}/{len(s['votes'])} yes → {'ACCEPT' if yes * 2 > len(s['votes']) else 'REJECT'}"}


b = StateGraph(State)
b.add_node("vote", vote)
b.add_node("tally", tally)
b.add_conditional_edges(START, fan_out, ["vote"])
b.add_edge("vote", "tally")
b.add_edge("tally", END)
app = b.compile()

t0 = time.perf_counter()
out = app.invoke({"question": "What is 7 x 8?", "answer": "56"})
print(out["verdict"], f"· {grader.calls} calls in {(time.perf_counter() - t0) * 1000:.0f} ms")
```

**Expected output (measured):**

```
2/3 yes → ACCEPT · 3 calls in 494 ms        ← JavaScript
2/3 yes → ACCEPT · 3 calls in 438 ms        ← Python
```

About one call's time (300 ms plus overhead), not three. **Why `Send` here, and not three
`addEdge(START, …)`?** The three graders are the *same* node with a different payload. With
`Send` you can change the number of voters without redrawing the graph. With a real model,
voting only helps if the runs can disagree. Use a temperature above 0, or different prompts
or models for each voter.
</details>

### Exercise 3 — Break it four ways ●●●○○

Predict what happens, then run it.

1. The evaluator-optimizer's grader **always passes**.
2. The grader **never passes**, and the loop has **no cap**.
3. The router's model replies with a label that has **no edge** (`"history"`).
4. Compression clears old tool results, and the answer needs a fact from **chapter 1**.

<details>
<summary>✅ Solution</summary>

| # | Symptom (measured) | Why |
|---|---|---|
| 1 | `rounds=1 calls=2 words=28 hasExample=false` | The loop is only as good as its grader. A grader that always passes is a slower single call. |
| 2 | JS: `GraphRecursionError: Recursion limit of 25 reached without hitting a stop condition. You can increase the limit by setting the "recursionLimit" config key.` after **13** writer calls. Python: `Recursion limit of 10007 reached …` after **5,004** writer calls. With a cap of 3: `passed=false rounds=3 calls=6` | Two supersteps per round. Python's default limit is 10,007, not 25. |
| 3 | JS: `Error: Branch condition returned unknown or null destination` · Python: `KeyError: 'history'` — with a list or a path map | The edge function returned a name the graph doesn't know. Normalise the label and add a fallback (§7 ❌ 4). |
| 4 | `Facts I can see: 4` — no error, just a worse answer | `ClearToolUsesEdit` kept only the latest tool result. Exercise 4 fixes it. |

**Repro for 1–3 — JavaScript**

```js
import { StateGraph, Annotation, START, END } from "@langchain/langgraph";
import { FakeModel } from "./fake.js";

const words = (t) => t.trim().split(/\s+/).length;
const D1 = "Photosynthesis is how green plants make their own food. Inside the leaf, chlorophyll " +
  "captures light and uses it to turn water and carbon dioxide into glucose, releasing oxygen.";

function buildLoop({ judgeReply, maxRounds }) {
  const writer = new FakeModel(() => D1);
  const judge = new FakeModel(judgeReply);
  const State = Annotation.Root({
    draft: Annotation(), feedback: Annotation(), passed: Annotation(),
    round: Annotation({ reducer: (a, b) => a + b, default: () => 0 }),
  });
  const app = new StateGraph(State)
    .addNode("generate", async (s) => ({ draft: (await writer.invoke(`FEEDBACK: ${s.feedback ?? ""}`)).content, round: 1 }))
    .addNode("evaluate", async (s) => {
      const v = JSON.parse((await judge.invoke(`DRAFT:\n${s.draft}`)).content);
      return { passed: v.pass, feedback: v.feedback };
    })
    .addEdge(START, "generate").addEdge("generate", "evaluate")
    .addConditionalEdges("evaluate",
      (s) => (s.passed || (maxRounds && s.round >= maxRounds) ? END : "generate"), ["generate", END])
    .compile();
  return { app, writer, judge };
}

// 1. an evaluator that always passes
{
  const { app, writer, judge } = buildLoop({ judgeReply: () => '{"pass":true,"feedback":""}' });
  const out = await app.invoke({});
  console.log(`#1 rounds=${out.round} calls=${writer.calls + judge.calls} words=${words(out.draft)} hasExample=${/for example/i.test(out.draft)}`);
}
// 2. an evaluator that never passes, and no cap
{
  const { app, writer } = buildLoop({ judgeReply: () => '{"pass":false,"feedback":"Add an example."}' });
  try { await app.invoke({}); } catch (e) { console.log(`#2 ${e.name}: ${e.message.split("\n")[0]} | writer calls=${writer.calls}`); }
}
// 3. a router whose model returns a label the edge doesn't know
{
  const router = new FakeModel(() => "history");
  const State = Annotation.Root({ q: Annotation(), label: Annotation() });
  const app = new StateGraph(State)
    .addNode("classify", async (s) => ({ label: (await router.invoke(s.q)).content }))
    .addNode("maths", () => ({})).addNode("essay", () => ({})).addNode("general", () => ({}))
    .addEdge(START, "classify")
    .addConditionalEdges("classify", (s) => s.label, ["maths", "essay", "general"])
    .addEdge("maths", END).addEdge("essay", END).addEdge("general", END)
    .compile();
  try { await app.invoke({ q: "When did WW2 end?" }); }
  catch (e) { console.log(`#3 ${e.name}: ${e.message.split("\n")[0]}`); }
}
```

```
#1 rounds=1 calls=2 words=28 hasExample=false
#2 GraphRecursionError: Recursion limit of 25 reached without hitting a stop condition. You can increase the limit by setting the "recursionLimit" config key. | writer calls=13
#3 Error: Branch condition returned unknown or null destination
```

**Repro for 1–3 — Python**

```python
import json
import operator
import re
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from fake import FakeModel

D1 = ("Photosynthesis is how green plants make their own food. Inside the leaf, chlorophyll "
      "captures light and uses it to turn water and carbon dioxide into glucose, releasing oxygen.")


class LoopState(TypedDict, total=False):
    draft: str
    feedback: str
    passed: bool
    round: Annotated[int, operator.add]


def build_loop(judge_reply, max_rounds=None):
    writer = FakeModel(reply=lambda p, m: D1)
    judge = FakeModel(reply=judge_reply)

    def generate(s):
        return {"draft": writer.invoke(f"FEEDBACK: {s.get('feedback', '')}").content, "round": 1}

    def evaluate(s):
        v = json.loads(judge.invoke(f"DRAFT:\n{s['draft']}").content)
        return {"passed": v["pass"], "feedback": v["feedback"]}

    def nxt(s):
        return END if s["passed"] or (max_rounds and s["round"] >= max_rounds) else "generate"

    b = StateGraph(LoopState)
    b.add_node("generate", generate)
    b.add_node("evaluate", evaluate)
    b.add_edge(START, "generate")
    b.add_edge("generate", "evaluate")
    b.add_conditional_edges("evaluate", nxt, ["generate", END])
    return b.compile(), writer, judge


# 1. an evaluator that always passes
app, writer, judge = build_loop(lambda p, m: '{"pass": true, "feedback": ""}')
out = app.invoke({"round": 0})
print(f"#1 rounds={out['round']} calls={writer.calls + judge.calls} words={len(out['draft'].split())} "
      f"hasExample={bool(re.search('for example', out['draft'], re.I))}")

# 2. never passes, no cap
app, writer, judge = build_loop(lambda p, m: '{"pass": false, "feedback": "Add an example."}')
try:
    app.invoke({"round": 0})
except Exception as e:
    print(f"#2 {type(e).__name__}: {str(e).splitlines()[0]} | writer calls={writer.calls}")


# 3. a router whose model returns an unknown label
class RState(TypedDict, total=False):
    q: str
    label: str


router = FakeModel(reply=lambda p, m: "history")
b = StateGraph(RState)
b.add_node("classify", lambda s: {"label": router.invoke(s["q"]).content})
for n in ["maths", "essay", "general"]:
    b.add_node(n, lambda s: {})
    b.add_edge(n, END)
b.add_edge(START, "classify")
b.add_conditional_edges("classify", lambda s: s["label"], ["maths", "essay", "general"])
try:
    b.compile().invoke({"q": "When did WW2 end?"})
except Exception as e:
    print(f"#3 {type(e).__name__}: {str(e).splitlines()[0]}")
```

```
#1 rounds=1 calls=2 words=28 hasExample=False
#2 GraphRecursionError: Recursion limit of 10007 reached without hitting a stop condition. You can increase the limit by setting the `recursion_limit` config key. | writer calls=5004
#3 KeyError: 'history'
```

Break #2 took 26 seconds in Python, even with an instant fake model. It made **10,007**
model calls: 5,004 writes and 5,003 grades (JS: 13 and 12). With a real model at one second
per call, that is nearly three hours of paid calls. For break #4, run the `compress` block
from §4.8 / §5.8.

**Why this exercise matters:** breaks 1 and 4 raise **no error**. They make the product
quietly worse. Only an evaluation set (Day 25) catches them, so add a test for each.
</details>

### Exercise 4 — Compress without forgetting ●●●●○

Fix break #4. Keep `ClearToolUsesEdit` with the same settings, but give the agent two new
tools. `save_note` writes a fact to a notebook that lives **outside** the context window.
`read_notes` brings the notes back. Script the agent to save each chapter's key fact straight
after reading it, and to read its notes before answering. Measure the characters per call
and count the facts the final answer can see.

<details>
<summary>✅ Solution</summary>

**JavaScript**

```js
// Write + select fix the fact that compression dropped
import { createAgent, tool, contextEditingMiddleware, ClearToolUsesEdit } from "langchain";
import { AIMessage, HumanMessage } from "@langchain/core/messages";
import { z } from "zod";
import { FakeModel } from "./fake.js";

const FACTS = ["the exam is on 12 June", "calculators are not allowed",
  "Section B is worth 60% of the marks", "the 2023 paper is the best practice"];
const chapter = (n) =>
  `CHAPTER ${n}. ` + `Detailed background notes for chapter ${n}. `.repeat(28) +
  `KEY FACT ${n}: ${FACTS[n - 1]}.`;

const notebook = [];                                   // lives OUTSIDE the context window
const readChapter = tool(async ({ n }) => chapter(n), {
  name: "read_chapter", description: "Read one chapter of the course notes.",
  schema: z.object({ n: z.number() }),
});
const saveNote = tool(async ({ note }) => { notebook.push(note); return "saved"; }, {
  name: "save_note", description: "Save a short note to your notebook for later.",
  schema: z.object({ note: z.string() }),
});
const readNotes = tool(async () => notebook.join("\n"), {
  name: "read_notes", description: "Read every note you saved.", schema: z.object({}),
});

let id = 0;
const call = (name, args) =>
  new AIMessage({ content: "", tool_calls: [{ name, args, id: `c${id++}`, type: "tool_call" }] });
const count = (msgs, name) => msgs.filter((m) => m.type === "tool" && m.name === name).length;

const model = new FakeModel((_, msgs) => {
  const reads = count(msgs, "read_chapter"), saves = count(msgs, "save_note");
  if (saves < reads) return call("save_note", { note: msgs.at(-1).text.match(/KEY FACT \d: [^.]+/)[0] });
  if (reads < 4) return call("read_chapter", { n: reads + 1 });
  if (count(msgs, "read_notes") === 0) return call("read_notes", {});
  const seen = [...new Set(msgs.flatMap((m) => [...m.text.matchAll(/KEY FACT (\d)/g)].map((x) => x[1])))];
  return `Exam briefing. Facts I can see: ${seen.join(", ")}`;
});

const agent = createAgent({
  model, tools: [readChapter, saveNote, readNotes],
  systemPrompt: "You are StudyBuddy. After each chapter, save its key fact as a note.",
  middleware: [contextEditingMiddleware({
    edits: [new ClearToolUsesEdit({ trigger: { tokens: 500 }, keep: { messages: 1 } })],
  })],
});
const out = await agent.invoke({ messages: [new HumanMessage("Brief me for the exam.")] });
const chars = model.seen.map((s) => s.chars);
console.log(`chars per call: ${chars.join(", ")}`);
console.log(`calls ${chars.length} · total ${chars.reduce((a, b) => a + b, 0)} · ${out.messages.at(-1).content}`);
console.log("final state tool results:", out.messages.filter((m) => m.type === "tool").map((m) => `${m.name}:${m.text.length}`).join(" "));
```

```
chars per call: 90, 1284, 1289, 1307, 1312, 1333, 1338, 1351, 158, 328
calls 10 · total 9790 · Exam briefing. Facts I can see: 1, 2, 3, 4
final state tool results: read_chapter:9 save_note:9 read_chapter:9 save_note:9 read_chapter:9 save_note:9 read_chapter:9 save_note:5 read_notes:170
```

**Python**

```python
# Write + select fix the fact that compression dropped
import itertools
import re
from langchain.agents import create_agent
from langchain.agents.middleware import ContextEditingMiddleware, ClearToolUsesEdit
from langchain.tools import tool
from langchain_core.messages import AIMessage, HumanMessage
from fake import FakeModel

FACTS = ["the exam is on 12 June", "calculators are not allowed",
         "Section B is worth 60% of the marks", "the 2023 paper is the best practice"]


def chapter(n: int) -> str:
    return (f"CHAPTER {n}. " + f"Detailed background notes for chapter {n}. " * 28
            + f"KEY FACT {n}: {FACTS[n - 1]}.")


notebook: list[str] = []                             # lives OUTSIDE the context window


@tool
def read_chapter(n: int) -> str:
    """Read one chapter of the course notes."""
    return chapter(n)


@tool
def save_note(note: str) -> str:
    """Save a short note to your notebook for later."""
    notebook.append(note)
    return "saved"


@tool
def read_notes() -> str:
    """Read every note you saved."""
    return "\n".join(notebook)


ids = itertools.count()


def call(name, args):
    return AIMessage(content="", tool_calls=[
        {"name": name, "args": args, "id": f"c{next(ids)}", "type": "tool_call"}])


def count(msgs, name):
    return sum(1 for m in msgs if m.type == "tool" and m.name == name)


def reply(_, msgs):
    reads, saves = count(msgs, "read_chapter"), count(msgs, "save_note")
    if saves < reads:
        return call("save_note", {"note": re.search(r"KEY FACT \d: [^.]+", msgs[-1].text).group(0)})
    if reads < 4:
        return call("read_chapter", {"n": reads + 1})
    if count(msgs, "read_notes") == 0:
        return call("read_notes", {})
    seen = sorted({f for m in msgs for f in re.findall(r"KEY FACT (\d)", m.text)})
    return f"Exam briefing. Facts I can see: {', '.join(seen)}"


model = FakeModel(reply=reply)
agent = create_agent(
    model, [read_chapter, save_note, read_notes],
    system_prompt="You are StudyBuddy. After each chapter, save its key fact as a note.",
    middleware=[ContextEditingMiddleware(edits=[ClearToolUsesEdit(trigger=500, keep=1)])],
)
out = agent.invoke({"messages": [HumanMessage("Brief me for the exam.")]})
chars = [s["chars"] for s in model.seen]
print("chars per call:", ", ".join(map(str, chars)))
print(f"calls {len(chars)} · total {sum(chars)} · {out['messages'][-1].content}")
print("final state tool results:", " ".join(f"{m.name}:{len(m.text)}" for m in out["messages"] if m.type == "tool"))
```

```
chars per call: 90, 1284, 1289, 1307, 122, 1333, 140, 1351, 158, 332
calls 10 · total 7406 · Exam briefing. Facts I can see: 1, 2, 3, 4
final state tool results: read_chapter:1194 save_note:5 read_chapter:1199 save_note:5 read_chapter:1207 save_note:5 read_chapter:1207 save_note:5 read_notes:170
```

**What you just measured:**

| | Calls | Biggest call | Total characters | Facts |
|---|---|---|---|---|
| Compress only (§4.8) | 5 | 1,328 | 5,331 | 1 of 4 |
| Write + select + compress, JS | 10 | 1,351 | 9,790 | **4 of 4** |
| Write + select + compress, Python | 10 | 1,351 | 7,406 | **4 of 4** |

The context still never grows past about 1,350 characters, and every fact survives. The price
is five extra calls. The last line of each output shows the §6.3 difference. JS cleared the
tool results **in state** (9 characters each). Python kept the full text in state and cleared
only what it sent. Python re-checked the full history on calls 5 and 7 and cleared
more, so it sent fewer characters in total.

**Why this design:** the notebook is the **write** strategy, and `read_notes` is **select**.
Compression is safe only after the important part has been written somewhere else. In
production the notebook would be a store or a file
([Day 14](../week-02-data-embeddings-and-rag/day-14-memory.md)), not a list in memory.
</details>

### Exercise 5 — 🎯 StudyBuddy v7.0: the simplest pattern for each feature ●●●●○

Refactor StudyBuddy's front door. Every request arrives with a `kind` (the button the
student pressed). Build a top-level graph that routes each kind to the **simplest** pattern
that serves it. Unknown kinds must not crash the graph. Then fill in the design table: for
each feature, the pattern, why, and the model calls it costs.

<details>
<summary>✅ Solution</summary>

**The design**

| Feature (`kind`) | Pattern | Why this one, and not something simpler | Model calls (from today's runs) |
|---|---|---|---|
| `flashcard` | single call | One fact in, one card out. Nothing to check. | 1 |
| `essay_feedback` | prompt chaining + gate | Always the same three steps. A code gate skips the rest if there is no essay. | 3 (§4.2) |
| `quiz_pack` | parallelisation | The parts are independent, so run them at once. | 3, in about one call's time (§4.4) |
| `revision_guide` | orchestrator-workers | The number of subtopics depends on the topic. | 1 + N (§4.5) |
| `explain` | evaluator-optimizer | Clear rules (≤ 40 words, one example), and revising helped. | 2 per round, capped at 3 rounds (§4.6) |
| `homework_help` | agent, with a sub-agent per long document | The steps depend on tool results; isolation keeps its context small. | 5 for 4 tool calls (§4.7); 13 with isolation (§4.9) |
| anything else | falls back to the agent | Never crash on a new button. | — |

The router itself is **code**, not a model: the `kind` already says what the student wants.
That saves one call on every request.

**JavaScript**

```js
// StudyBuddy v7.0 — the front door: a code router to the simplest pattern per feature
import { StateGraph, Annotation, START, END } from "@langchain/langgraph";

// Which pattern serves each feature. Plain data: easy to review, easy to test.
const ROUTES = {
  flashcard: "single_call",       // one fact in, one card out
  essay_feedback: "chain",        // check outline → feedback → tone polish (fixed steps)
  quiz_pack: "parallel",          // summary, quiz, cards are independent
  revision_guide: "orchestrator", // number of subtopics unknown until you see the topic
  explain: "evaluator",           // clear criteria: ≤ 40 words + one example
  homework_help: "agent",         // tools, and the steps depend on what the tools return
};
const PATTERNS = [...new Set(Object.values(ROUTES))];

const State = Annotation.Root({ kind: Annotation(), text: Annotation(), handledBy: Annotation() });

// Stand-ins: in the real app each is the compiled graph from §4 used as a subgraph node.
const standIn = (pattern) => async () => ({ handledBy: pattern });

let graph = new StateGraph(State);
for (const p of PATTERNS) graph = graph.addNode(p, standIn(p)).addEdge(p, END);
const app = graph
  .addConditionalEdges(START, (s) => ROUTES[s.kind] ?? "agent", PATTERNS) // unknown → agent
  .compile();

for (const kind of [...Object.keys(ROUTES), "timetable"]) {
  const out = await app.invoke({ kind, text: "..." });
  console.log(`${kind.padEnd(15)} → ${out.handledBy}`);
}
```

**Python**

```python
# StudyBuddy v7.0 — the front door: a code router to the simplest pattern per feature
from typing import TypedDict
from langgraph.graph import StateGraph, START, END

# Which pattern serves each feature. Plain data: easy to review, easy to test.
ROUTES = {
    "flashcard": "single_call",        # one fact in, one card out
    "essay_feedback": "chain",         # check outline → feedback → tone polish (fixed steps)
    "quiz_pack": "parallel",           # summary, quiz, cards are independent
    "revision_guide": "orchestrator",  # number of subtopics unknown until you see the topic
    "explain": "evaluator",            # clear criteria: ≤ 40 words + one example
    "homework_help": "agent",          # tools, and the steps depend on what the tools return
}
PATTERNS = sorted(set(ROUTES.values()))


class State(TypedDict, total=False):
    kind: str
    text: str
    handled_by: str


# Stand-ins: in the real app each is the compiled graph from §5 used as a subgraph node.
def stand_in(pattern):
    return lambda s: {"handled_by": pattern}


b = StateGraph(State)
for p in PATTERNS:
    b.add_node(p, stand_in(p))
    b.add_edge(p, END)
b.add_conditional_edges(START, lambda s: ROUTES.get(s["kind"], "agent"), PATTERNS)  # unknown → agent
app = b.compile()

for kind in [*ROUTES, "timetable"]:
    out = app.invoke({"kind": kind, "text": "..."})
    print(f"{kind:<15} → {out['handled_by']}")
```

**Expected output (both languages, measured):**

```
flashcard       → single_call
essay_feedback  → chain
quiz_pack       → parallel
revision_guide  → orchestrator
explain         → evaluator
homework_help   → agent
timetable       → agent
```

**Finishing the job.** Replace each stand-in with the compiled graph from §4.2–4.9 (or
§5.2–5.9). A compiled graph can be added as a node directly
([Day 19](../week-03-tools-agents-and-langgraph/day-19-control-flow.md)). Map the parent's
`text` onto each subgraph's input keys with a small wrapper node. The routing table is plain
data, so you can unit-test it without running a single model.

**Why this design:** only one of the six features is an agent now. Five of them have a
fixed or capped number of calls, so you can predict their cost and test each node on its own.
The one agent left is the one that needs to be an agent, and its context stays small.
</details>

---

## 9. Interview questions

### Basic

**Q1. What's the difference between a workflow and an agent?**

In a workflow, your code decides the path: model calls are joined by edges you drew in
advance. In an agent, the model decides its own next step and which tools to use, in a loop.
Anthropic's "Building Effective Agents" (December 2024) draws the line this way. Workflows
are predictable and cheaper to test. Agents handle cases you could not plan for.

---

**Q2. Name the five workflow patterns from "Building Effective Agents".**

- **Prompt chaining** — fixed steps in order.
- **Routing** — classify, then pick a path.
- **Parallelisation** — independent parts at once, or several votes.
- **Orchestrator-workers** — a planner splits the job at run time; workers do the parts.
- **Evaluator-optimizer** — write, grade, revise; repeat until it passes or hits a cap.

---

**Q3. What is context engineering?**

Deciding what goes into the model's context window on each call: instructions, tool
definitions, memory, retrieved documents, history, tool results and any state you show it.
Karpathy called it filling the window with "just the right information for the next step".
Prompt engineering is one part of it.

---

**Q4. Why not always use an agent? It can do everything a workflow can.**

Cost, speed and testing. A workflow's call count is fixed or capped; an agent's varies per
run. In today's runs, the chained workflow always made 3 calls. You can test each workflow node
alone; an agent needs whole-trajectory tests. Anthropic's advice is to start with the
simplest thing and add steps only when they measurably help.

---

### Intermediate

**Q5. How do you decide between parallelisation and orchestrator-workers?**

Ask who decides the number of parts. If you know the parts when you build the graph (summary,
quiz, flashcards), it's parallelisation: draw one node per part. If only the input tells you
(subtopics of *this* topic), it's orchestrator-workers: a planner call returns the list and
`Send` starts one worker per item. Today the same orchestrator graph ran 2 workers for one
topic and 4 for another.

---

**Q6. When does evaluator-optimizer help, and what does it cost?**

It helps when there are **clear criteria** and revising measurably improves the answer.
Each round costs two calls (write and grade), so three rounds cost 6 calls against 1. Use it
where quality matters a lot, and check criteria with code where you can — code is free and
exact.

---

**Q7. Your evaluator-optimizer loop sometimes runs forever. What's wrong, and what's the fix?**

There's no cap, or the grader can never be satisfied. Keep a round counter in state and end
when `passed or round >= MAX`. Then mark capped results as not passed. Don't rely on the
recursion limit. It throws away the result, and its default differs: 25 supersteps in JS,
but 10,007 in Python's `langgraph` 1.2.14. That allowed 5,004 writer calls before the error
in today's run.

---

**Q8. What are the four context strategies? Give an example of each.**

**Write** — keep it outside the window (a notebook tool, a file, a state key). **Select** —
bring in only what this call needs (retrieval, choosing tools, reading one note). **Compress**
— keep fewer tokens (clear old tool results, summarise, trim). **Isolate** — give a sub-task
its own context (a sub-agent, a `Send` worker). The names come from LangChain's 2025 post
"Context Engineering for Agents".

---

**Q9. Why does an agent's cost grow faster than its history?**

Each call re-sends the whole history. If every tool result adds *d* characters, call *k*
carries about *k·d*, and the total over *n* calls grows with *n²*. Today's four-chapter
agent sent 94, then 1,288, 2,487, 3,694 and 4,901 characters: 12,464 in total.

---

### Advanced

**Q10. You turned on tool-result clearing and quality dropped, but nothing errors. Why?**

Compression throws information away. In today's run, clearing kept only the last tool result,
so the final answer could see 1 of 4 key facts — with no error. The fix is to **write** the
important part first (a notebook or store) and **select** it back before answering. With
that, all 4 facts survived. Add an evaluation for the final answer, because this failure is
silent.

---

**Q11. Compare compression and isolation for an agent that reads many long documents.**

Compression keeps one context and shrinks it. It is cheap in calls (5 in today's run) but
loses detail. Isolation gives each document to a sub-agent that returns a short report. The
main context stayed tiny (biggest call 261 characters, against 4,901) and kept every fact.
But it took 13 calls instead of 5. Isolate when side-jobs are large, can run in parallel or
would confuse each other. Compress when the old content really is no longer needed.

---

**Q12. Does LangChain's context-editing middleware change the agent's state?**

It differs by language (measured). In JS (`langchain` 1.5.15), cleared tool results are
replaced **in state** with `[cleared]`, so checkpoints lose the original text. In Python
(`langchain` 1.4.3), only the request sent to the model is edited; state keeps the full text.
That changes cost too: Python re-checks the full history each call and clears more often.
In one run that was 7,406 characters against 9,790 in JS.

---

**Q13. What is a "deep agent", and when is it worth it?**

A long-running agent with four parts. It has a detailed system prompt and a planning tool
(a to-do list that keeps the plan in context). It also has sub-agents for focused jobs, and
a file system for notes and large results. LangChain ships it as `deepagents`. Today,
versions 0.7.22 (Python) and 1.14.2 (JS) gave eight built-in tools (`ls`, `read_file`,
`write_file`, `edit_file`, `delete`, `glob`, `grep`, `task`). The to-do tool came from
adding `TodoListMiddleware`.
It's worth it for long, open-ended work like research or coding. It's the wrong tool for
jobs with known steps.

---

**Q14. How would you test a router in CI without an API key?**

Use a scripted model, and test both the routing table and the fallback. Make the fake read
only the user's input. In today's first attempt, the fake searched the whole prompt and
routed "Why is the sky blue?" to `essay`, because the instructions listed the word "essay".
Also test an unknown label. Without a fallback, JS throws "Branch condition returned unknown
or null destination" and Python throws `KeyError`.

---

**Q15. Where does context engineering meet security?**

Everything in the window can steer the model, including text hidden in tool results and
retrieved pages ([Day 35](../week-05-the-model-layer/day-35-ai-security.md)). Selecting less
and isolating risky reading in a sub-agent shrinks what an attacker can reach. A sub-agent
that only returns a short, structured report gives injected text far less room to pass on
instructions. It lowers the risk; it does not remove it.

---

## 10. Recap

### What you learned

- ✅ **Workflow or agent?** Ask: can I write the steps down before I see the input?
- ✅ The five patterns, each one graph shape: **chaining** (line + gate), **routing**
  (conditional edge), **parallelisation** (fan-out + join), **orchestrator-workers** (`Send`),
  **evaluator-optimizer** (a loop back, with a cap)
- ✅ A **gate** and a **router** can be plain code — free and predictable
- ✅ Evaluator-optimizer: **2 calls per round**; measured 3 rounds = 6 calls to pass
- ✅ The recursion limit is **25 in JS but 10,007 in Python** (`langgraph` 1.2.14) — keep your
  own counter
- ✅ Context = instructions + tools + memory + retrieved docs + history + **tool results** +
  shown state
- ✅ Agent context grows each call: **94 → 4,901 characters**, 12,464 in total
- ✅ **Compress** stopped the growth (5,331 total) but kept **1 of 4** facts
- ✅ **Isolate** kept the main agent tiny (864 total) and all facts, for 13 calls instead of 5
- ✅ **Write + select** before compress: all 4 facts survive
- ✅ JS context editing rewrites **state**; Python edits only the **request**
- ✅ Deep agents = detailed prompt + to-do list + sub-agents + file system (`deepagents`)

### The decision in one breath

```
   known steps?      → workflow: chain · route · parallel · orchestrate · evaluate-and-revise
   unknown steps?    → agent, and engineer its context:
                         write it down → select what's needed → compress the rest
                         → isolate big side-jobs in sub-agents
   always            → cap every loop; measure calls and context per step
```

### Tomorrow

**[Day 37 — Advanced retrieval](day-37-advanced-retrieval.md)**: today you met **select** —
bringing in only what the call needs. Retrieval is the biggest select step in most apps, and
plain vector search can't answer questions about *relationships* or *numbers in a table*.
Tomorrow you add knowledge graphs (GraphRAG), text-to-SQL agents and agentic search.

### Quick self-check

1. A feature always does "translate → check grammar → format as a table". Agent or
   workflow? Which pattern?
2. Your evaluator-optimizer runs fine in JS, but a Python user reports a huge bill from one
   request. What is the most likely cause?
3. You add tool-result clearing and your answer-quality eval drops. Name the fix in two
   strategy words.

<details>
<summary>Answers</summary>

1. **Workflow — prompt chaining.** The steps are fixed and in a fixed order. Add a code gate
   between steps if a step can fail in a way you can check (for example, "the translation is
   empty").

2. **An uncapped loop.** The grader never passed. JS stopped at its default recursion limit
   of 25 supersteps (13 writer calls). Python's default at `langgraph` 1.2.14 is 10,007
   (5,004 writer calls). Add a round counter to state and end at a cap.

3. **Write, then select.** Save the important facts outside the context (a notebook tool or
   store) before they are cleared, and read them back before answering (Exercise 4).
</details>

---

<div align="center">

**[← Day 35 — AI security](../week-05-the-model-layer/day-35-ai-security.md)** · **[Week 6 index](README.md)** · **[Day 37 — Advanced retrieval →](day-37-advanced-retrieval.md)**

</div>
