# Day 25 — Observability & Evaluation: Know Whether It Works

> ⏱ **Time:** ~3 hours · 🎯 **Prereqs:** [Day 24](day-24-reliability.md) · 🧩 **Difficulty:** ●●●●○

**Today you learn:** StudyBuddy is live, but you can't see why it gave a bad answer, and you
can't prove that a new prompt is *better* rather than just different. Today you record every
run as a **trace**, so you can read what happened inside it. Then you build an **evaluation**
suite: a **dataset**, code checks, an **LLM-as-judge**, **trajectory** checks for the agent and
a CI gate that fails the build when quality drops. Every evaluator in this chapter was run,
with scripted models, in both languages.

> 📖 **Words you'll meet today**
>
> - **Observability** — being able to see what happened inside one specific run.
> - **Trace** — the record of one request: a tree of every model call, tool call and step.
> - **Callback** — a hook the library calls at each step (start, end, error) of a run.
> - **Evaluation (eval)** — measuring how good the system is, the same way each time.
> - **Dataset** — a fixed set of example questions with the answers or facts you expect.
> - **Evaluator** — a function that scores one output, for example "contains the right facts".
> - **LLM-as-judge** — using a second model to grade answers against written rules (a rubric).
> - **Trajectory** — the sequence of tool calls an agent made on its way to the answer.

---

## 1. The problem

StudyBuddy v5 is in production. Three messages arrive on the same Monday:

```
   Student:     "It told me the derivative of x² is x. That's wrong!"
   Teammate:    "I tightened the system prompt on Friday — answers look better now."
   Your manager: "Should we switch to the cheaper model? Would anyone notice?"
```

Try answering them honestly:

| Question | What you'd need | What you have |
|---|---|---|
| Why did it say that? | the exact prompt, retrieved notes, tool calls and model output for *that* run | a log line saying "200 OK" |
| Is Friday's prompt better? | the same questions answered by both versions, scored the same way | your teammate's feeling |
| Would anyone notice the cheaper model? | quality and cost measured on realistic questions | a guess |

None of these is answerable without two capabilities you haven't built yet:

```
   OBSERVABILITY   see what happened inside a specific run          → traces
   EVALUATION      measure how good the system is, repeatably       → datasets + evaluators
```

### The real-life version

Aviation again, because it solved this decades ago:

```
   FLIGHT RECORDER     every input, every control movement, every instrument reading
                       → after an incident, you replay exactly what happened        TRACES
   INSTRUMENT PANEL    live gauges: fuel, speed, altitude, engine temperature
                       → you notice problems while they're small                     METRICS
   CHECKRIDES          pilots fly the same test scenarios, scored against a standard
                       → you know whether training worked                           EVALS
```

A pilot who says "I feel like I'm flying better" doesn't get certified. A prompt
shouldn't either.

---

## 2. Mental model

### Three loops

```
   ┌──────────── OBSERVE (per run) ────────────┐
   │ every request → a TRACE: a tree of runs    │
   │   agent → model call → tool call → ...     │
   └───────────────────┬────────────────────────┘
                       │ failures, surprises, samples
                       ▼
   ┌──────────── COLLECT ──────────────────────┐
   │ interesting runs → a DATASET              │
   │   { inputs, reference outputs }            │
   └───────────────────┬────────────────────────┘
                       ▼
   ┌──────────── EVALUATE (per change) ────────┐
   │ run version A and version B on the dataset │
   │ score both with the same EVALUATORS        │
   │ compare → ship, or don't                   │
   └───────────────────────────────────────────┘
```

Production feeds the dataset, and the dataset decides whether the next change may ship. That
loop is the whole discipline. Teams that have it improve steadily. Teams without it swing
between "better" and "worse" and can't tell which is which.

### Four kinds of evaluator

| Evaluator | Checks | Cost | Use for |
|---|---|---|---|
| **Code** | exact match, contains, regex, valid JSON, schema, length, latency | free, instant, deterministic | anything you can check with code — always first |
| **Trajectory** | did the agent call the right tools, in the right order, with the right args? | free | agents (Day 16+) |
| **LLM-as-judge** | correctness, groundedness, helpfulness, tone — against a rubric | a model call | qualities code can't check |
| **Human** | anything; the ground truth your judges are calibrated against | slow, expensive | calibration and the hardest cases |

Two more questions decide which evaluators you can use:

```
   REFERENCE-BASED   compares to a known good answer      offline, on a dataset
   REFERENCE-FREE    judges the output on its own         also works online, on live traffic
```

---

## 3. First principles

### 3.1 A trace is a tree of runs

> 💬 **In plain words:** the library tells you about every step as it happens. A tracer
> listens to those messages and draws them as a tree you can read later.

Every LangChain and LangGraph operation reports **lifecycle events** (start, end, error)
through **callbacks**. A chain starts, a chat model starts, a tool starts, and each one ends. A
**tracer** is simply a callback handler that records those events as a tree.

We ran one agent run (one tool call, two model calls) with a handler that counts every event.
Here are the counts in both languages:

```
                          JavaScript      Python
   chain start               7              4
   chain end                 7              —   (not tallied)
   chat model start          2              2
   llm end                   2              2
   tool start / end         1 / 1          1 / 1
   llm start                 0              0    ← chat models don't fire it
```

The table shows two things:

- **Chat models fire `handleChatModelStart` / `on_chat_model_start`, not `handleLLMStart` /
  `on_llm_start`.** A handler that only listens for "LLM start" silently records nothing for
  modern chat models. Both languages still fire the *end* event as `llmEnd` / `on_llm_end`.
- **The number of chain events is an implementation detail** — it differs between languages
  and versions. Count model and tool events, not chain events, if you're building metrics.

### 3.2 Tokens and cost

> 💬 **In plain words:** every answer reports how many tokens it used. Add them up per model,
> and you know what each request cost.

Every `AIMessage` carries `usage_metadata` (`input_tokens`, `output_tokens`,
`total_tokens`). There are three equivalent ways to total it. All three agreed on our test
run (250 input + 50 output = 300):

```
   1. sum usage_metadata over the result's messages
   2. a callback handler summing it in handleLLMEnd / on_llm_end
   3. Python only: get_usage_metadata_callback() — a context manager that totals usage
      PER MODEL NAME:  {'scripted-1': {'input_tokens': 250, 'output_tokens': 50, 'total_tokens': 300}}
```

Per-model totals matter once you use more than one model, such as Day 22's specialists or
Day 24's fallbacks. Cost is tokens multiplied by *that model's* price.

### 3.3 Label your runs

> 💬 **In plain words:** give every run a name, some tags and some details, so you can find it
> later and compare "before" with "after".

A trace you can't find is useless. Every invocation accepts three labels, and you should
always set them:

```js
agent.invoke(input, {
  runName: "studybuddy-chat",                                   // what this is
  tags: ["prod", "prompt-v7"],                                  // filterable labels
  metadata: { userId: "u42", threadId, promptVersion: "v7" },   // searchable context
});
```

```python
agent.invoke(inp, {"run_name": "studybuddy-chat", "tags": ["prod", "prompt-v7"],
                   "metadata": {"user_id": "u42", "thread_id": tid, "prompt_version": "v7"}})
```

`promptVersion` and `model` in metadata are what let you slice a dashboard by "before vs
after Friday's prompt change". Without them, you can see that quality changed but not why.

### 3.4 LangSmith, and tracing without it

> 💬 **In plain words:** LangSmith is a website that stores and shows your traces. It is
> useful, but everything today also works without it.

LangSmith is LangChain's hosted tracing and evaluation platform. You turn tracing on with
environment variables. No code changes are needed:

```bash
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_...
LANGSMITH_PROJECT=studybuddy-prod
```

Some of your code isn't a LangChain runnable, such as your own retrieval function or a
post-processing step (work done on the answer after the model). Wrap it with `traceable` so
it appears as a node in the same trace tree:

```
   JS       import { traceable } from "langsmith/traceable"
   Python   from langsmith import traceable
```

Verified: with `LANGSMITH_TRACING` unset, a `traceable` function runs normally and nothing is
sent. So you can leave the decorators in place and turn tracing on per environment.

You don't *need* LangSmith for any of today's chapter. Callbacks give you the raw events for
any backend, such as OpenTelemetry (an open standard for traces and metrics) or your logging
stack. Evaluation is ordinary code. What a platform adds is storage, a UI for reading trace
trees, dataset management and side-by-side comparison of experiments. Build the habits first.
Choose the tooling second.

### 3.5 Datasets: the part that decides everything

> 💬 **In plain words:** your test questions matter more than your scoring code. Real
> questions and past failures make the best tests.

An evaluator is only as good as the questions it's run on. Where good examples come from,
best first:

```
   1. PRODUCTION FAILURES    every bad answer a user reports becomes a test case
   2. PRODUCTION SAMPLES     real questions, in real proportions, with real phrasing
   3. EXPERT-WRITTEN         hard cases you know matter (edge cases, policy boundaries)
   4. SYNTHETIC              model-generated — useful for coverage, dangerous alone:
                             models write questions models find easy
```

Start small: **20–50 real examples** beat 1,000 synthetic ones. Each example is
`{ inputs, reference outputs }`. The reference can be a full answer, a list of facts that must
appear, or the tool trajectory an agent should take.

### 3.6 LLM-as-judge

> 💬 **In plain words:** when code can't check an answer, ask another model to grade it
> against clear rules. Then check the grader against human grades.

Some qualities can't be checked with code: is the explanation *correct*? *grounded* in the
retrieved notes? *helpful*? For those, you ask a model to grade against a **rubric** (a
written list of what counts as a good answer).

The `openevals` package ships tested rubrics. We verified it in both languages with a scripted
judge model:

```
   create_llm_as_judge / createLLMAsJudge(prompt=CORRECTNESS_PROMPT, judge=<model>,
                                          feedback_key="correctness")
     → the judge is asked for structured output: { reasoning, score }
     → evaluator(inputs, outputs, reference_outputs) returns:
          { key: "correctness", score: true, comment: "The answer matches the reference." }

   continuous=True        → score is a number (we returned 0.7)
   use_reasoning=False    → comment is None — faster, but you lose the "why"
```

Each prompt declares which fields it needs (read from the templates):

```
   CORRECTNESS_PROMPT          inputs, outputs, reference_outputs
   RAG_GROUNDEDNESS_PROMPT     context, outputs                   ← reference-free: works online
```

In the version we tested, the catalogue also includes these prompts:

- answer relevance, conciseness, hallucination
- RAG helpfulness, RAG retrieval relevance
- tool selection, trajectory accuracy
- toxicity, PII leakage, prompt injection, and more.

Read a prompt before using it. It *is* your definition of quality.

**Judges are models, so they have biases.** They favour longer answers, answers in the first
position, and answers written in their own style. Defences:

```
   binary judgments with a reasoning step   > 1–10 scales (far less noisy)
   a DIFFERENT model family as the judge    (self-preference is real)
   a clear rubric with examples              (few-shot examples are supported)
   CALIBRATION against human labels          ← the only way to know a judge is any good
```

Calibration is simple arithmetic: label 30–50 outputs yourself, run the judge on the same
ones, and measure agreement. A judge that agrees with you 70% of the time isn't measuring
what you think.

### 3.7 Evaluating agents: the path, not just the destination

> 💬 **In plain words:** for an agent, check *how* it got the answer — which tools it called —
> not only the final answer.

An agent can reach the right answer the wrong way. It might make six tool calls instead of
one, or guess the right number instead of reading it from the database. **Trajectory
evaluators** compare the tool calls an agent actually made to a reference.

We verified this with `agentevals` in both languages, on a "weather in Lahore" trajectory:

```
   mode          same trajectory    different tool used
   ──────────    ───────────────    ───────────────────
   strict           ✓ true              ✗ false        same tools, same order
   unordered        ✓ true              ✗ false        same tools, any order
   subset           ✓ true              ✗ false        agent used no tools beyond the reference
   superset         ✓ true              ✗ false        agent used at least the reference's tools

   tool_args_match_mode "exact"  + a different city  → false
   tool_args_match_mode "ignore" + a different city  → true
```

Choose the mode by what matters:

- `strict` for regulated workflows (where rules fix the exact steps).
- `superset` for "must at least have checked the database".
- `ignore` args when the arguments can legitimately vary.

### 3.8 RAG evaluation: two failure points, two sets of metrics

> 💬 **In plain words:** a bad RAG answer comes either from finding the wrong notes or from
> using good notes badly. Measure the two parts separately.

[Day 12](../week-02-data-embeddings-and-rag/day-12-naive-rag.md)'s central lesson applies
directly. A wrong RAG answer is one of two failures:

- a **retrieval** failure: the right chunk wasn't retrieved, or
- a **generation** failure: it was retrieved, but the model ignored or misused it.

Measure them separately:

```
   RETRIEVAL (code, needs labelled relevant chunk ids)
     hit rate / recall@k     did any / what fraction of relevant chunks appear in the top k?
     MRR                     how high was the first relevant chunk? (1/rank, averaged)

   GENERATION (judges)
     groundedness            is every claim supported by the retrieved context?
     answer relevance        does it answer the question asked?
     correctness             does it match the reference answer?
```

If recall@4 is 60%, no prompt change will fix the answers. Fix chunking, embeddings or
retrieval instead (Days 9–13). If recall is 95% and groundedness is poor, the retrieval is
fine and the prompt or model is the problem. One end-to-end score can't tell you which.

### 3.9 Offline vs online

> 💬 **In plain words:** test on a fixed dataset before you ship, and keep watching real
> traffic after you ship. Each catches problems the other misses.

```
   OFFLINE  — before you ship                    ONLINE — after you ship
   a fixed dataset, reference answers            live traffic, no references
   run on every change, in CI                    sampled (1–10% of runs)
   code + trajectory + judges                    reference-free judges, user feedback,
                                                 latency/cost/error metrics
   answers "is B better than A?"                 answers "is it still working?"
```

You need both. Offline evals stop **regressions** (things that used to work and now don't)
from shipping. Online evals catch the slow changes offline evals can't see: new kinds of
questions, a provider silently changing a model, or a data source going out of date.

---

## 4. Code — JavaScript

> **Install:** `npm i langsmith openevals agentevals`

### 4.1 A callback handler for metrics

```js
// counts model calls, tool calls and tokens for one request
function metricsHandler() {
  const m = { modelCalls: 0, toolCalls: 0, tokens: 0, toolErrors: 0, startedAt: Date.now() };
  return {
    metrics: m,
    handler: {
      handleChatModelStart() { m.modelCalls++; },          // NOT handleLLMStart — chat models don't fire it
      handleLLMEnd(output) {
        m.tokens += output.generations?.[0]?.[0]?.message?.usage_metadata?.total_tokens ?? 0;
      },
      handleToolStart() { m.toolCalls++; },
      handleToolError() { m.toolErrors++; },
    },
  };
}

const { metrics, handler } = metricsHandler();
const out = await studybuddy.invoke(
  { messages: [new HumanMessage("Explain HTTPS")] },
  {
    callbacks: [handler],
    runName: "studybuddy-chat",
    tags: ["prod", "prompt-v7"],
    metadata: { userId: "u42", promptVersion: "v7", model: "openai/gpt-oss-120b" },
  }
);
console.log({ ...metrics, ms: Date.now() - metrics.startedAt });
// { modelCalls: 2, toolCalls: 1, tokens: 300, toolErrors: 0, ms: … }
```

A handler is a plain object with the methods you care about. Send the result to whatever you
already use — logs, Prometheus, OpenTelemetry.

### 4.2 Token accounting without a handler

```js
const tokens = out.messages.reduce((sum, m) => sum + (m.usage_metadata?.total_tokens ?? 0), 0);
```

Verified to match the handler exactly (300 = 300). Use the handler when you need per-model
or per-step detail; use the sum when you just need a number per request.

### 4.3 Tracing with LangSmith

```bash
# .env
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_...
LANGSMITH_PROJECT=studybuddy-dev
```

Every LangChain and LangGraph run is now traced. For your own functions:

```js
import { traceable } from "langsmith/traceable";

const rerank = traceable(
  async (query, docs) => docs.sort((a, b) => score(b, query) - score(a, query)).slice(0, 4),
  { name: "rerank" }
);
```

It appears as a node in the same trace tree as the model and tool calls around it. With
`LANGSMITH_TRACING` unset, it's a transparent wrapper (verified).

### 4.4 A dataset and code evaluators

Start with code. It's free, instant and never disagrees with itself.

```js
const DATASET = [
  { inputs: { question: "What does HTTPS add to HTTP?" },
    reference: { mustInclude: ["TLS"], tools: ["search_notes"] } },
  { inputs: { question: "What must every recursive function have?" },
    reference: { mustInclude: ["base case"], tools: ["search_notes"] } },
  { inputs: { question: "What's my weakest topic?" },
    reference: { mustInclude: ["https", "62"], tools: ["get_progress"] } },
  // ...grow this from real questions and every reported failure
];

const evaluators = {
  containsFacts: ({ answer }, ref) =>
    ref.mustInclude.every((f) => answer.toLowerCase().includes(f.toLowerCase())),
  notTooLong: ({ answer }) => answer.split(/\s+/).length <= 250,
  usedRightTools: ({ toolsCalled }, ref) => ref.tools.every((t) => toolsCalled.includes(t)),
};

async function runTarget(inputs) {
  const out = await studybuddy.invoke({ messages: [new HumanMessage(inputs.question)] });
  return {
    answer: String(out.messages.at(-1).content),
    toolsCalled: out.messages.flatMap((m) => m.tool_calls?.map((c) => c.name) ?? []),
  };
}

async function evaluateAll() {
  const rows = [];
  for (const ex of DATASET) {
    const output = await runTarget(ex.inputs);
    const scores = Object.fromEntries(
      Object.entries(evaluators).map(([name, fn]) => [name, fn(output, ex.reference)])
    );
    rows.push({ question: ex.inputs.question, ...scores, answer: output.answer });
  }
  const summary = Object.fromEntries(
    Object.keys(evaluators).map((k) => [k, rows.filter((r) => r[k]).length / rows.length])
  );
  return { rows, summary };
}

const { rows, summary } = await evaluateAll();
console.table(summary);                                  // { containsFacts: 0.9, notTooLong: 1, ... }
console.log(rows.filter((r) => !r.containsFacts));       // read the failures — always
```

That last line matters more than the summary. **Read every failure.** The score tells you
*whether* something's wrong; only the examples tell you *what*.

### 4.5 LLM-as-judge

```js
import { createLLMAsJudge, CORRECTNESS_PROMPT, RAG_GROUNDEDNESS_PROMPT } from "openevals";
import { ChatOpenAI } from "@langchain/openai";

// a DIFFERENT model family from the one being judged
const judgeModel = new ChatOpenAI({ model: "gpt-4o-mini", temperature: 0 });

const correctness = createLLMAsJudge({
  prompt: CORRECTNESS_PROMPT,
  judge: judgeModel,
  feedbackKey: "correctness",
});

const result = await correctness({
  inputs: "How does HTTPS work?",
  outputs: "HTTPS is HTTP running over TLS, which encrypts the connection.",
  referenceOutputs: "HTTP over TLS; TLS provides encryption and server authentication.",
});
// { key: "correctness", score: true, comment: "…the judge's reasoning…" }

// reference-free, so it can run on live traffic too
const groundedness = createLLMAsJudge({
  prompt: RAG_GROUNDEDNESS_PROMPT,
  judge: judgeModel,
  feedbackKey: "groundedness",
});
await groundedness({ context: retrievedChunks.join("\n\n"), outputs: answer });
```

<details>
<summary>💰 Using a free judge</summary>

```js
import { ChatGroq } from "@langchain/groq";
// if StudyBuddy runs on GPT-OSS via Groq, judge with a different family — e.g. Gemini's free tier
import { ChatGoogleGenerativeAI } from "@langchain/google-genai";
const judgeModel = new ChatGoogleGenerativeAI({ model: "gemini-3.8-flash", temperature: 0 });
```

Judging a model with a model from the same family inflates scores (self-preference). Mixing
providers is the cheap fix.
</details>

Verified with a scripted judge: the judge is asked for a `{ reasoning, score }` object,
receives the rubric-filled prompt as a single message, and the evaluator returns
`{ key, score, comment }`. With `continuous: true`, `score` is a number.

### 4.6 Trajectory evaluation for agents

```js
import { createTrajectoryMatchEvaluator } from "agentevals";
import { AIMessage, HumanMessage, ToolMessage } from "@langchain/core/messages";

const reference = [
  new HumanMessage("What's my weakest topic?"),
  new AIMessage({ content: "", tool_calls: [{ name: "get_progress", args: {}, id: "r1", type: "tool_call" }] }),
  new ToolMessage({ content: "[...]", tool_call_id: "r1" }),
  new AIMessage("Your weakest topic is HTTPS (62)."),
];

const trajectory = createTrajectoryMatchEvaluator({
  trajectoryMatchMode: "superset",     // must at least have checked progress
  toolArgsMatchMode: "ignore",
});

const out = await studybuddy.invoke({ messages: [new HumanMessage("What's my weakest topic?")] });
console.log(await trajectory({ outputs: out.messages, referenceOutputs: reference }));
// { key: "trajectory_superset_match", score: true, ... }
```

It takes LangChain messages directly — pass `out.messages` from any agent run.

### 4.7 RAG retrieval metrics

```js
// each example: a question and the ids of the chunks that actually answer it
const RETRIEVAL_SET = [
  { question: "What does TLS 1.3 use for key exchange?", relevant: ["notes-https-03"] },
  { question: "Why does recursion need a base case?", relevant: ["notes-rec-01", "notes-rec-02"] },
];

async function retrievalMetrics(retriever, k = 4) {
  let hits = 0, recallSum = 0, rrSum = 0;
  for (const { question, relevant } of RETRIEVAL_SET) {
    const ids = (await retriever.invoke(question)).slice(0, k).map((d) => d.metadata.id);
    const found = relevant.filter((id) => ids.includes(id));
    if (found.length) hits++;
    recallSum += found.length / relevant.length;
    const firstRank = ids.findIndex((id) => relevant.includes(id));
    rrSum += firstRank >= 0 ? 1 / (firstRank + 1) : 0;
  }
  const n = RETRIEVAL_SET.length;
  return { hitRate: hits / n, recallAtK: recallSum / n, mrr: rrSum / n };
}

console.log(await retrievalMetrics(retriever));   // { hitRate: 1, recallAtK: 0.75, mrr: 0.83 }
```

Run this before touching prompts. If retrieval is the problem, no prompt will fix it.

### 4.8 Experiments in LangSmith

With an API key, `evaluate` runs a target over a stored dataset and applies evaluators. It
records the result as an **experiment** that you can compare side by side with others in the
UI:

```js
import { evaluate } from "langsmith/evaluation";

await evaluate(
  async (inputs) => runTarget(inputs),
  {
    data: "studybuddy-core-50",                        // a dataset stored in LangSmith
    evaluators: [
      ({ outputs, referenceOutputs }) => ({
        key: "contains_facts",
        score: referenceOutputs.mustInclude.every((f) => outputs.answer.includes(f)),
      }),
    ],
    experimentPrefix: "prompt-v7",
  }
);
```

> 📦 In our tests the JS `evaluate` needed valid LangSmith credentials. Without them, it failed
> while creating the experiment's project (`Received status [401]: Unauthorized`). For fully
> offline runs in JS, use your own harness (§4.4). Python's `evaluate` can run locally with
> `upload_results=False` (§5.8).

### 4.9 A regression gate for CI

```js
// eval-gate.mjs — fail the build if quality drops
import fs from "node:fs";

const BASELINE = JSON.parse(fs.readFileSync("eval-baseline.json", "utf8"));
const TOLERANCE = 0.05;                                   // allow 5 points of noise

const { summary } = await evaluateAll();
let failed = false;
for (const [metric, score] of Object.entries(summary)) {
  const base = BASELINE[metric] ?? 0;
  const status = score + TOLERANCE < base ? "REGRESSED" : "ok";
  if (status === "REGRESSED") failed = true;
  console.log(`${metric.padEnd(16)} ${base.toFixed(2)} → ${score.toFixed(2)}  ${status}`);
}
if (process.argv.includes("--update-baseline")) fs.writeFileSync("eval-baseline.json", JSON.stringify(summary, null, 2));
process.exit(failed ? 1 : 0);
```

Run the code evaluators on every pull request, because they are cheap. Run the judge-based
suite nightly or before a release, because it costs money. Update the **baseline** (the saved
scores you compare against) on purpose, in its own commit, once an improvement is confirmed.

---

## 5. Code — Python

> **Install:** `pip install langsmith openevals agentevals`

### 5.1 A callback handler for metrics

```python
import time
from langchain_core.callbacks import BaseCallbackHandler

class MetricsHandler(BaseCallbackHandler):
    def __init__(self):
        self.model_calls = self.tool_calls = self.tool_errors = self.tokens = 0
        self.started = time.monotonic()

    def on_chat_model_start(self, *args, **kwargs):     # NOT on_llm_start
        self.model_calls += 1

    def on_llm_end(self, response, **kwargs):
        for gen in response.generations[0]:
            usage = getattr(gen.message, "usage_metadata", None) or {}
            self.tokens += usage.get("total_tokens", 0)

    def on_tool_start(self, *args, **kwargs):
        self.tool_calls += 1

    def on_tool_error(self, *args, **kwargs):
        self.tool_errors += 1

m = MetricsHandler()
out = studybuddy.invoke(
    {"messages": [HumanMessage("Explain HTTPS")]},
    {"callbacks": [m], "run_name": "studybuddy-chat", "tags": ["prod", "prompt-v7"],
     "metadata": {"user_id": "u42", "prompt_version": "v7", "model": "openai/gpt-oss-120b"}},
)
print(m.model_calls, m.tool_calls, m.tokens, f"{time.monotonic() - m.started:.2f}s")
```

### 5.2 Token accounting — per model

```python
from langchain_core.callbacks import get_usage_metadata_callback

with get_usage_metadata_callback() as usage:
    studybuddy.invoke({"messages": [HumanMessage("Explain HTTPS")]})

print(usage.usage_metadata)
# {'openai/gpt-oss-120b': {'input_tokens': 77, 'output_tokens': 68, 'total_tokens': 145,
#                          'output_token_details': {'reasoning': 24}}}
```

Verified: totals are keyed by the model name each response reports. So a supervisor and its
specialists on different models get separate lines, which is exactly what you need to
compute cost. The output above is from one live call to `ChatGroq(model="openai/gpt-oss-120b")`
with "Explain HTTPS in one sentence." (your numbers will differ). Note `reasoning`: GPT-OSS is
a reasoning model. Its hidden reasoning tokens are counted inside `output_tokens` (24 of the 68
here), so a ledger that prices `output_tokens` already includes them.

### 5.3 Tracing with LangSmith

Same environment variables as §4.3. For your own functions:

```python
from langsmith import traceable

@traceable(name="rerank")
def rerank(query: str, docs: list) -> list:
    return sorted(docs, key=lambda d: score(d, query), reverse=True)[:4]
```

### 5.4 A dataset and code evaluators

```python
DATASET = [
    {"inputs": {"question": "What does HTTPS add to HTTP?"},
     "reference": {"must_include": ["TLS"], "tools": ["search_notes"]}},
    {"inputs": {"question": "What must every recursive function have?"},
     "reference": {"must_include": ["base case"], "tools": ["search_notes"]}},
    {"inputs": {"question": "What's my weakest topic?"},
     "reference": {"must_include": ["https", "62"], "tools": ["get_progress"]}},
]

EVALUATORS = {
    "contains_facts": lambda out, ref: all(f.lower() in out["answer"].lower() for f in ref["must_include"]),
    "not_too_long":   lambda out, ref: len(out["answer"].split()) <= 250,
    "used_right_tools": lambda out, ref: all(t in out["tools_called"] for t in ref["tools"]),
}

def run_target(inputs: dict) -> dict:
    out = studybuddy.invoke({"messages": [HumanMessage(inputs["question"])]})
    return {
        "answer": str(out["messages"][-1].content),
        "tools_called": [c["name"] for m in out["messages"] for c in (getattr(m, "tool_calls", None) or [])],
    }

def evaluate_all():
    rows = []
    for ex in DATASET:
        output = run_target(ex["inputs"])
        scores = {name: fn(output, ex["reference"]) for name, fn in EVALUATORS.items()}
        rows.append({"question": ex["inputs"]["question"], **scores, "answer": output["answer"]})
    summary = {k: sum(r[k] for r in rows) / len(rows) for k in EVALUATORS}
    return rows, summary

rows, summary = evaluate_all()
print(summary)
for r in rows:
    if not r["contains_facts"]:
        print("FAIL:", r["question"], "→", r["answer"][:120])
```

We verified this pattern with a stubbed target (a fake that returns fixed answers). There were
3 examples and one wrong answer ("Lyon" for the capital of France). The pass rate was 2/3,
and the failure was listed with its answer.

### 5.5 LLM-as-judge

```python
from openevals.llm import create_llm_as_judge
from openevals.prompts import CORRECTNESS_PROMPT, RAG_GROUNDEDNESS_PROMPT
from langchain_openai import ChatOpenAI

judge_model = ChatOpenAI(model="gpt-4o-mini", temperature=0)   # a different family

correctness = create_llm_as_judge(
    prompt=CORRECTNESS_PROMPT,
    judge=judge_model,
    feedback_key="correctness",
)
result = correctness(
    inputs="How does HTTPS work?",
    outputs="HTTPS is HTTP running over TLS, which encrypts the connection.",
    reference_outputs="HTTP over TLS; TLS provides encryption and server authentication.",
)
# {'key': 'correctness', 'score': True, 'comment': '…', 'metadata': None}

groundedness = create_llm_as_judge(prompt=RAG_GROUNDEDNESS_PROMPT, judge=judge_model,
                                   feedback_key="groundedness")
groundedness(context="\n\n".join(retrieved_chunks), outputs=answer)
```

Verified options with a scripted judge: `continuous=True` returned `score: 0.7`;
`use_reasoning=False` returned `comment: None`. The judge is bound to a tool named `score`
for its structured output.

### 5.6 Trajectory evaluation for agents

```python
from agentevals.trajectory.match import create_trajectory_match_evaluator

trajectory = create_trajectory_match_evaluator(
    trajectory_match_mode="superset",
    tool_args_match_mode="ignore",
)
out = studybuddy.invoke({"messages": [HumanMessage("What's my weakest topic?")]})
print(trajectory(outputs=out["messages"], reference_outputs=reference))
# {'key': 'trajectory_superset_match', 'score': True, ...}
```

### 5.7 RAG retrieval metrics

```python
RETRIEVAL_SET = [
    {"question": "What does TLS 1.3 use for key exchange?", "relevant": ["notes-https-03"]},
    {"question": "Why does recursion need a base case?", "relevant": ["notes-rec-01", "notes-rec-02"]},
]

def retrieval_metrics(retriever, k: int = 4) -> dict:
    hits = recall_sum = rr_sum = 0.0
    for ex in RETRIEVAL_SET:
        ids = [d.metadata["id"] for d in retriever.invoke(ex["question"])[:k]]
        found = [r for r in ex["relevant"] if r in ids]
        hits += bool(found)
        recall_sum += len(found) / len(ex["relevant"])
        first = next((i for i, doc_id in enumerate(ids) if doc_id in ex["relevant"]), None)
        rr_sum += 1 / (first + 1) if first is not None else 0
    n = len(RETRIEVAL_SET)
    return {"hit_rate": hits / n, "recall_at_k": recall_sum / n, "mrr": rr_sum / n}
```

### 5.8 Experiments with LangSmith — online or offline

```python
from langsmith import evaluate

def contains_facts(outputs: dict, reference_outputs: dict) -> bool:
    return all(f in outputs["answer"] for f in reference_outputs["must_include"])

# with an API key: a dataset stored in LangSmith, results uploaded as an experiment
evaluate(run_target, data="studybuddy-core-50", evaluators=[contains_facts],
         experiment_prefix="prompt-v7")
```

And locally, with no account — verified:

```python
import uuid
from langsmith.schemas import Example

examples = [
    Example(id=uuid.uuid4(), dataset_id=uuid.uuid4(),
            inputs={"question": "What does HTTPS add?"}, outputs={"must_include": ["TLS"]}),
]
results = evaluate(run_target, data=examples, evaluators=[contains_facts], upload_results=False)
for row in results:
    print([(r.key, r.score) for r in row["evaluation_results"]["results"]])
```

`upload_results=False` is marked beta (it logs a warning). Still, it lets you use the same
evaluator functions locally and in LangSmith. The evaluator signature is just the argument
names you need: `outputs`, `reference_outputs`, `inputs`.

### 5.9 A regression gate for CI

```python
# eval_gate.py — fail the build if quality drops
import json, sys

BASELINE = json.load(open("eval-baseline.json"))
TOLERANCE = 0.05

_, summary = evaluate_all()
failed = False
for metric, score in summary.items():
    base = BASELINE.get(metric, 0)
    regressed = score + TOLERANCE < base
    failed |= regressed
    print(f"{metric:<16} {base:.2f} → {score:.2f}  {'REGRESSED' if regressed else 'ok'}")

if "--update-baseline" in sys.argv:
    json.dump(summary, open("eval-baseline.json", "w"), indent=2)
sys.exit(1 if failed else 0)
```

### 5.10 The JS ↔ Python translation for today

| Concept | JavaScript | Python |
|---|---|---|
| callback: chat model start | `handleChatModelStart` | `on_chat_model_start` |
| callback: model end | `handleLLMEnd(output)` | `on_llm_end(response)` |
| callback: tool | `handleToolStart` / `handleToolEnd` / `handleToolError` | `on_tool_start` / `on_tool_end` / `on_tool_error` |
| handler shape | plain object with methods | subclass `BaseCallbackHandler` |
| run labels | `{ runName, tags, metadata }` | `{"run_name", "tags", "metadata"}` |
| usage per model | sum `usage_metadata` yourself | `get_usage_metadata_callback()` |
| trace a function | `traceable(fn, { name })` from `langsmith/traceable` | `@traceable(name=...)` from `langsmith` |
| LLM-as-judge | `createLLMAsJudge({ prompt, judge, feedbackKey })` | `create_llm_as_judge(prompt=, judge=, feedback_key=)` |
| judge call | `await ev({ inputs, outputs, referenceOutputs })` | `ev(inputs=, outputs=, reference_outputs=)` |
| trajectory match | `createTrajectoryMatchEvaluator({ trajectoryMatchMode })` | `create_trajectory_match_evaluator(trajectory_match_mode=)` |
| LangSmith experiment | `evaluate(target, { data, evaluators })` | `evaluate(target, data=, evaluators=)` |
| offline experiment | not available in our tests (401 without a key) | `upload_results=False` (beta) |

---

## 6. Under the hood

### 6.1 What a trace record holds

```
   run: studybuddy-chat           tags [prod, prompt-v7]   metadata {userId, promptVersion}
   ├─ model (chat model)           inputs: messages       outputs: AIMessage  tokens  latency
   ├─ tools                        inputs: tool call      outputs: ToolMessage        latency
   │   └─ search_notes (tool)
   │        └─ rerank (traceable)
   └─ model (chat model)           …
```

Each node has inputs, outputs, timing, errors and its parent. That's enough to answer
"why did it say that?" for any run, because you can read what the model was actually given.

### 6.2 Traces are production data

A trace contains whatever your users typed, whatever you retrieved, and whatever the model
said. Treat it with the same care as your database:

```
   PII          redact at the edge before it reaches the model and the tracer —
                PII middleware (Day 24) changes what the MODEL sees, but the top-level
                run still records the user's original input unless you redact earlier
   ACCESS       who can read traces? production traces are customer data
   RETENTION    set it; don't keep raw conversations forever by default
   SAMPLING     trace 100% in dev; in production, sample normal traffic and keep
                every error and every flagged conversation
```

### 6.3 Why evaluation beats "looks better"

Model outputs vary from run to run, and people remember the last few examples they read. A
change that improves 10 answers and breaks 3 feels like a win if you happened to look at the
10. A dataset with fixed questions, scored the same way every time, removes both problems.
And the habit of reading every failure keeps you honest about what the numbers mean.

### 6.4 Eval-driven development

```
   1. a user reports a bad answer
   2. find its trace → understand the cause
   3. add the question to the dataset (with the correct reference)
   4. fix the prompt / retrieval / tool
   5. run the suite: the new case passes AND nothing else regressed
   6. ship; the case guards against that failure forever
```

That's test-driven development for **non-deterministic** systems (systems that can give a
different output for the same input). The dataset becomes the team's memory of every mistake
StudyBuddy has made. It is also the reason StudyBuddy doesn't make them twice.

---

## 7. Common mistakes

### ❌ 1. Evaluating by reading a few outputs

```
❌ "I tried five questions and it looks better."
✅ a fixed dataset, scored the same way, before and after — and read every failure
```

People remember the examples they saw last. A dataset doesn't.

### ❌ 2. Listening for `handleLLMStart` with chat models

```js
❌ { handleLLMStart() { calls++; } }           // verified: never fires for chat models
✅ { handleChatModelStart() { calls++; } }
```

```python
❌ def on_llm_start(self, *a, **k): ...
✅ def on_chat_model_start(self, *a, **k): ...
```

Your metrics silently read zero model calls.

### ❌ 3. Only evaluating the final answer of an agent

The right answer via six unnecessary tool calls, or from a guess instead of the database,
still passes an answer-only check. Add trajectory evaluators.

### ❌ 4. Trusting an uncalibrated judge

```
❌ "The judge says 92% correct."
✅ "The judge agrees with our human labels 88% of the time, and says 92% correct."
```

Until you've measured agreement with humans, a judge's score is a number, not a measurement.

### ❌ 5. Judging a model with itself

Models prefer text in their own style. Use a different model family as the judge.

### ❌ 6. 1–10 scales without a rubric

```
❌ "Rate this answer 1-10"                         → noisy, drifts between runs
✅ binary with reasoning, against an explicit rubric → stable, debuggable
```

### ❌ 7. A dataset of easy synthetic questions

Model-written questions are the ones models find easy. Seed the dataset from production
failures and real traffic.

### ❌ 8. No version labels on runs

```js
❌ agent.invoke(input)
✅ agent.invoke(input, { tags: ["prompt-v7"], metadata: { promptVersion: "v7", model } })
```

Without them, you can see quality changed but not which change did it.

### ❌ 9. One end-to-end RAG score

A bad RAG answer is a retrieval failure or a generation failure, and the fixes are
completely different. Measure recall@k separately from groundedness.

### ❌ 10. PII in traces

The tracer records user input. Redact at the edge, restrict access, and set retention.

### ❌ 11. Assuming JS `evaluate` runs offline

In our tests it needed a valid LangSmith key (401 without one). Keep a local harness for
offline and CI runs. Use `evaluate` when you want the hosted experiment view.

### ❌ 12. Evaluating once

An eval suite that runs once is a report. One that runs on every change is a safety net.
Put the cheap evaluators in CI and the expensive ones on a schedule.

---

## 8. Exercises

### Exercise 1 — Instrument an agent ●●○○○

Using a scripted model (no API key), build a handler that produces a per-request summary:
model calls, tool calls, tool errors, total tokens and latency. Run it on an agent that makes
one tool call, and check the token total against the sum of `usage_metadata` on the result.

<details>
<summary>✅ Solution</summary>

**JavaScript**

```js
import { BaseChatModel } from "@langchain/core/language_models/chat_models";
import { AIMessage, HumanMessage } from "@langchain/core/messages";
import { tool } from "@langchain/core/tools";
import { createAgent } from "langchain";
import { z } from "zod";

class Scripted extends BaseChatModel {
  constructor(script) { super({}); this.script = script; this.i = 0; }
  _llmType() { return "scripted"; }
  bindTools() { return this; }
  async _generate() {
    const message = this.script[Math.min(this.i++, this.script.length - 1)]();
    return { generations: [{ message, text: "" }] };
  }
}
const usage = (i, o) => ({ input_tokens: i, output_tokens: o, total_tokens: i + o });

const model = new Scripted([
  () => new AIMessage({ content: "", usage_metadata: usage(100, 10),
    tool_calls: [{ name: "lookup", args: {}, id: "t1", type: "tool_call" }] }),
  () => new AIMessage({ content: "HTTPS is HTTP over TLS.", usage_metadata: usage(150, 40) }),
]);
const lookup = tool(async () => "TLS 1.3 uses ECDHE.", { name: "lookup", description: "Look up a fact.", schema: z.object({}) });

function requestMetrics() {
  const m = { modelCalls: 0, toolCalls: 0, toolErrors: 0, tokens: 0, started: Date.now() };
  const handler = {
    handleChatModelStart() { m.modelCalls++; },
    handleLLMEnd(out) { m.tokens += out.generations?.[0]?.[0]?.message?.usage_metadata?.total_tokens ?? 0; },
    handleToolStart() { m.toolCalls++; },
    handleToolError() { m.toolErrors++; },
  };
  const summary = () => ({ ...m, ms: Date.now() - m.started });
  return { handler, summary };
}

const { handler, summary } = requestMetrics();
const out = await createAgent({ model, tools: [lookup] })
  .invoke({ messages: [new HumanMessage("Explain HTTPS")] }, { callbacks: [handler], tags: ["exercise"] });

const fromMessages = out.messages.reduce((s, m) => s + (m.usage_metadata?.total_tokens ?? 0), 0);
console.log(summary());                           // { modelCalls: 2, toolCalls: 1, toolErrors: 0, tokens: 300, ms: … }
console.log("from messages:", fromMessages);      // 300
```

**Python**

```python
import time
from langchain_core.callbacks import BaseCallbackHandler, get_usage_metadata_callback
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langchain.agents import create_agent

class Scripted(GenericFakeChatModel):
    def bind_tools(self, tools, **kw): return self

def usage(i, o): return {"input_tokens": i, "output_tokens": o, "total_tokens": i + o}

model = Scripted(messages=iter([
    AIMessage(content="", usage_metadata=usage(100, 10), response_metadata={"model_name": "scripted-1"},
              tool_calls=[{"name": "lookup", "args": {}, "id": "t1", "type": "tool_call"}]),
    AIMessage("HTTPS is HTTP over TLS.", usage_metadata=usage(150, 40), response_metadata={"model_name": "scripted-1"}),
]))

@tool
def lookup() -> str:
    """Look up a fact."""
    return "TLS 1.3 uses ECDHE."

class RequestMetrics(BaseCallbackHandler):
    def __init__(self):
        self.model_calls = self.tool_calls = self.tool_errors = self.tokens = 0
        self.started = time.monotonic()
    def on_chat_model_start(self, *a, **k): self.model_calls += 1
    def on_llm_end(self, response, **k):
        for g in response.generations[0]:
            self.tokens += (getattr(g.message, "usage_metadata", None) or {}).get("total_tokens", 0)
    def on_tool_start(self, *a, **k): self.tool_calls += 1
    def on_tool_error(self, *a, **k): self.tool_errors += 1
    def summary(self):
        return {"model_calls": self.model_calls, "tool_calls": self.tool_calls, "tool_errors": self.tool_errors,
                "tokens": self.tokens, "ms": int((time.monotonic() - self.started) * 1000)}

metrics = RequestMetrics()
with get_usage_metadata_callback() as per_model:
    out = create_agent(model, tools=[lookup]).invoke(
        {"messages": [HumanMessage("Explain HTTPS")]}, {"callbacks": [metrics], "tags": ["exercise"]})

print(metrics.summary())                                  # model_calls 2, tool_calls 1, tokens 300
print("per model:", per_model.usage_metadata)             # {'scripted-1': {... 'total_tokens': 300}}
print("from messages:", sum((getattr(m, "usage_metadata", None) or {}).get("total_tokens", 0) for m in out["messages"]))
```

**Checks to notice:**

- The model-call count comes from the *chat-model* start hook.
- The three token totals agree (300).
- Python's per-model breakdown is keyed by the `model_name` each response reports.

In production, emit `summary()` as a structured log line per request. Then you have a
cost-and-latency dashboard with no platform at all.
</details>

---

### Exercise 2 — Your first eval suite ●●○○○

Write 8 examples for StudyBuddy with `mustInclude` facts, and three code evaluators
(`containsFacts`, `notTooLong`, `noApology` — the answer shouldn't start with "I'm sorry").
Use a stub target that answers from a dictionary, including two deliberately wrong answers.
Print per-evaluator pass rates and every failing example.

<details>
<summary>✅ Solution</summary>

**JavaScript**

```js
const DATASET = [
  { q: "What does HTTPS add to HTTP?", mustInclude: ["TLS"] },
  { q: "What must a recursive function have?", mustInclude: ["base case"] },
  { q: "What is a vector embedding?", mustInclude: ["vector", "meaning"] },
  { q: "What does RAG stand for?", mustInclude: ["retrieval", "generation"] },
  { q: "What does a checkpointer save?", mustInclude: ["state"] },
  { q: "What is prompt injection?", mustInclude: ["instructions"] },
  { q: "Capital of France?", mustInclude: ["Paris"] },
  { q: "What does SSE stand for?", mustInclude: ["server-sent events"] },
];

const STUB = {
  "What does HTTPS add to HTTP?": "It adds TLS encryption to HTTP.",
  "What must a recursive function have?": "A base case, and progress toward it.",
  "What is a vector embedding?": "A vector of numbers that represents meaning.",
  "What does RAG stand for?": "Retrieval-augmented generation.",
  "What does a checkpointer save?": "The graph's state after every superstep.",
  "What is prompt injection?": "I'm sorry, I can't discuss that.",                   // wrong
  "Capital of France?": "Lyon.",                                                     // wrong
  "What does SSE stand for?": "Server-sent events.",
};
const target = async (q) => STUB[q];

const evaluators = {
  containsFacts: (answer, ex) => ex.mustInclude.every((f) => answer.toLowerCase().includes(f.toLowerCase())),
  notTooLong: (answer) => answer.split(/\s+/).length <= 120,
  noApology: (answer) => !/^i'?m sorry/i.test(answer.trim()),
};

const rows = [];
for (const ex of DATASET) {
  const answer = await target(ex.q);
  rows.push({ q: ex.q, answer, ...Object.fromEntries(Object.entries(evaluators).map(([k, fn]) => [k, fn(answer, ex)])) });
}

for (const k of Object.keys(evaluators)) {
  const passed = rows.filter((r) => r[k]).length;
  console.log(`${k.padEnd(14)} ${passed}/${rows.length}`);
}
console.log("\nFAILURES:");
for (const r of rows) {
  const failed = Object.keys(evaluators).filter((k) => !r[k]);
  if (failed.length) console.log(`  [${failed.join(", ")}] ${r.q} → "${r.answer}"`);
}
```

**Python**

```python
import re

DATASET = [
    {"q": "What does HTTPS add to HTTP?", "must_include": ["TLS"]},
    {"q": "What must a recursive function have?", "must_include": ["base case"]},
    {"q": "What is a vector embedding?", "must_include": ["vector", "meaning"]},
    {"q": "What does RAG stand for?", "must_include": ["retrieval", "generation"]},
    {"q": "What does a checkpointer save?", "must_include": ["state"]},
    {"q": "What is prompt injection?", "must_include": ["instructions"]},
    {"q": "Capital of France?", "must_include": ["Paris"]},
    {"q": "What does SSE stand for?", "must_include": ["server-sent events"]},
]

STUB = {
    "What does HTTPS add to HTTP?": "It adds TLS encryption to HTTP.",
    "What must a recursive function have?": "A base case, and progress toward it.",
    "What is a vector embedding?": "A vector of numbers that represents meaning.",
    "What does RAG stand for?": "Retrieval-augmented generation.",
    "What does a checkpointer save?": "The graph's state after every superstep.",
    "What is prompt injection?": "I'm sorry, I can't discuss that.",      # wrong
    "Capital of France?": "Lyon.",                                         # wrong
    "What does SSE stand for?": "Server-sent events.",
}
target = STUB.get

EVALUATORS = {
    "contains_facts": lambda a, ex: all(f.lower() in a.lower() for f in ex["must_include"]),
    "not_too_long":   lambda a, ex: len(a.split()) <= 120,
    "no_apology":     lambda a, ex: not re.match(r"^i'?m sorry", a.strip(), re.I),
}

rows = []
for ex in DATASET:
    answer = target(ex["q"])
    rows.append({"q": ex["q"], "answer": answer, **{k: fn(answer, ex) for k, fn in EVALUATORS.items()}})

for k in EVALUATORS:
    print(f"{k:<15} {sum(r[k] for r in rows)}/{len(rows)}")
print("\nFAILURES:")
for r in rows:
    failed = [k for k in EVALUATORS if not r[k]]
    if failed:
        print(f'  [{", ".join(failed)}] {r["q"]} → "{r["answer"]}"')
```

**Output**

```
containsFacts  6/8
notTooLong     8/8
noApology      7/8

FAILURES:
  [containsFacts, noApology] What is prompt injection? → "I'm sorry, I can't discuss that."
  [containsFacts] Capital of France? → "Lyon."
```

**Two lessons in eight examples.** First, one failure can trip several evaluators. The
refusal fails both "contains facts" and "no apology". That tells you *what kind* of wrong it
is: an over-refusal, not a hallucination. Second, `notTooLong` passing 8/8 tells you nothing
useful yet. An evaluator that never fails on your dataset has one of two causes. Either it
checks something that never goes wrong, or your dataset lacks the cases that would break it.
</details>

---

### Exercise 3 — Calibrate a judge ●●●○○

You have 10 answers you've labelled by hand (`true` = correct). Run an LLM-as-judge over the
same 10 and compute agreement, plus the judge's false-positive and false-negative counts. Use
a scripted judge so the exercise gives the same result every run. But write the code so a
real judge can be swapped in.

<details>
<summary>✅ Solution</summary>

**JavaScript**

```js
import { createLLMAsJudge, CORRECTNESS_PROMPT } from "openevals";
import { BaseChatModel } from "@langchain/core/language_models/chat_models";
import { RunnableLambda } from "@langchain/core/runnables";

// A scripted judge that returns pre-set verdicts in order. Swap for a real chat model.
class ScriptedJudge extends BaseChatModel {
  constructor(verdicts) { super({}); this.verdicts = verdicts; this.i = 0; }
  _llmType() { return "scripted-judge"; }
  async _generate() { throw new Error("unused"); }
  withStructuredOutput() {
    return RunnableLambda.from(async () => this.verdicts[this.i++]);
  }
}

const LABELLED = [
  { q: "HTTPS adds?", out: "TLS encryption", ref: "TLS", human: true },
  { q: "Recursion needs?", out: "A base case", ref: "base case", human: true },
  { q: "Capital of France?", out: "Lyon", ref: "Paris", human: false },
  { q: "What is RAG?", out: "Retrieval-augmented generation", ref: "retrieval-augmented generation", human: true },
  { q: "SSE?", out: "Server-sent events", ref: "server-sent events", human: true },
  { q: "2+2?", out: "5", ref: "4", human: false },
  { q: "Largest planet?", out: "Jupiter", ref: "Jupiter", human: true },
  { q: "Boiling point of water at sea level?", out: "90°C", ref: "100°C", human: false },
  { q: "Author of Hamlet?", out: "Shakespeare", ref: "Shakespeare", human: true },
  { q: "Speed of light?", out: "About 300,000 km/s", ref: "~3×10^8 m/s", human: true },
];

// the judge disagrees with us twice: it passes "90°C" and fails the speed-of-light answer
const judgeVerdicts = [true, true, false, true, true, false, true, true, true, false]
  .map((score) => ({ reasoning: "…", score }));

const judge = createLLMAsJudge({
  prompt: CORRECTNESS_PROMPT,
  judge: new ScriptedJudge(judgeVerdicts),     // ← swap in e.g. new ChatOpenAI({ model: "gpt-4o-mini" })
  feedbackKey: "correctness",
});

let agree = 0, falsePos = 0, falseNeg = 0;
for (const ex of LABELLED) {
  const { score } = await judge({ inputs: ex.q, outputs: ex.out, referenceOutputs: ex.ref });
  if (score === ex.human) agree++;
  else if (score && !ex.human) falsePos++;          // judge says correct, human says wrong
  else falseNeg++;                                  // judge says wrong, human says correct
}
console.log(`agreement ${agree}/${LABELLED.length} = ${(agree / LABELLED.length * 100).toFixed(0)}%`);
console.log(`false positives ${falsePos} · false negatives ${falseNeg}`);
```

**Python**

```python
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.utils.function_calling import convert_to_openai_tool
from openevals.llm import create_llm_as_judge
from openevals.prompts import CORRECTNESS_PROMPT
from pydantic import Field

class ScriptedJudge(GenericFakeChatModel):
    """Returns pre-set verdicts in order. Swap for a real chat model."""
    verdicts: list = Field(default_factory=list)
    tool_name: str = "score"
    def bind_tools(self, tools, **kw):
        self.tool_name = convert_to_openai_tool(tools[0])["function"]["name"]
        return self
    def _generate(self, messages, stop=None, run_manager=None, **kw):
        verdict = self.verdicts.pop(0)
        msg = AIMessage(content="", tool_calls=[{"name": self.tool_name, "args": verdict, "id": "j", "type": "tool_call"}])
        return ChatResult(generations=[ChatGeneration(message=msg)])

LABELLED = [
    ("HTTPS adds?", "TLS encryption", "TLS", True),
    ("Recursion needs?", "A base case", "base case", True),
    ("Capital of France?", "Lyon", "Paris", False),
    ("What is RAG?", "Retrieval-augmented generation", "retrieval-augmented generation", True),
    ("SSE?", "Server-sent events", "server-sent events", True),
    ("2+2?", "5", "4", False),
    ("Largest planet?", "Jupiter", "Jupiter", True),
    ("Boiling point of water at sea level?", "90°C", "100°C", False),
    ("Author of Hamlet?", "Shakespeare", "Shakespeare", True),
    ("Speed of light?", "About 300,000 km/s", "~3×10^8 m/s", True),
]
verdicts = [{"reasoning": "…", "score": s} for s in [True, True, False, True, True, False, True, True, True, False]]

judge = create_llm_as_judge(
    prompt=CORRECTNESS_PROMPT,
    judge=ScriptedJudge(messages=iter([]), verdicts=verdicts),   # ← swap in ChatOpenAI(model="gpt-4o-mini")
    feedback_key="correctness",
)

agree = false_pos = false_neg = 0
for q, out, ref, human in LABELLED:
    score = judge(inputs=q, outputs=out, reference_outputs=ref)["score"]
    if score == human:
        agree += 1
    elif score and not human:
        false_pos += 1
    else:
        false_neg += 1
print(f"agreement {agree}/{len(LABELLED)} = {agree / len(LABELLED):.0%}")
print(f"false positives {false_pos} · false negatives {false_neg}")
```

**Output**

```
agreement 8/10 = 80%
false positives 1 · false negatives 1
```

**How to read it.** 80% agreement sounds fine until you look at the false positive. The judge
passed "90°C" for the boiling point of water, which is a factual error. For a tutoring
product, a false positive (a wrong answer marked correct) is worse than a false negative. So
you'd tighten the rubric ("any numeric error makes the answer incorrect"). You'd also add
few-shot examples of numeric mistakes, and re-measure. The false negative is "300,000 km/s" vs
"3×10⁸ m/s". Here the judge fails to see that two units mean the same value. An explicit
rubric line fixes that too.

Real calibration sets are 30–50 examples, labelled by the people who own the quality bar.
Re-run calibration whenever you change the judge model or the rubric.
</details>

---

### Exercise 4 — Trajectory evals for StudyBuddy ●●●○○

Write reference trajectories for three StudyBuddy behaviours and evaluate agent runs against
them with the right mode for each:

1. "What's my weakest topic?" — must call `get_progress` (**superset**, args ignored).
2. "Delete my progress" — must call **no** write tool without approval (a trajectory that
   calls `run_write` should **fail**; use **subset** against a reference with only reads).
3. "Explain HTTPS" — should call `search_notes` exactly once, nothing else (**strict**).

<details>
<summary>✅ Solution</summary>

**JavaScript**

```js
import { createTrajectoryMatchEvaluator } from "agentevals";
import { AIMessage, HumanMessage, ToolMessage } from "@langchain/core/messages";

let id = 0;
// build a trajectory from a question, a list of tool names, and a final answer
function trajectory(question, tools, answer = "done") {
  const msgs = [new HumanMessage(question)];
  for (const name of tools) {
    const callId = `t${id++}`;
    msgs.push(new AIMessage({ content: "", tool_calls: [{ name, args: {}, id: callId, type: "tool_call" }] }));
    msgs.push(new ToolMessage({ content: "ok", tool_call_id: callId }));
  }
  msgs.push(new AIMessage(answer));
  return msgs;
}

const checks = [
  {
    name: "weakest topic uses progress data",
    evaluator: createTrajectoryMatchEvaluator({ trajectoryMatchMode: "superset", toolArgsMatchMode: "ignore" }),
    reference: trajectory("What's my weakest topic?", ["get_progress"]),
    runs: {
      good: trajectory("What's my weakest topic?", ["get_progress", "search_notes"]),
      bad:  trajectory("What's my weakest topic?", ["search_notes"]),       // guessed without data
    },
  },
  {
    name: "no unapproved writes",
    evaluator: createTrajectoryMatchEvaluator({ trajectoryMatchMode: "subset", toolArgsMatchMode: "ignore" }),
    reference: trajectory("Delete my progress", ["list_tables", "describe_table", "run_query"]),
    runs: {
      good: trajectory("Delete my progress", ["list_tables", "run_query"]),
      bad:  trajectory("Delete my progress", ["list_tables", "run_write"]),   // tried to write
    },
  },
  {
    name: "explanation uses notes once",
    evaluator: createTrajectoryMatchEvaluator({ trajectoryMatchMode: "strict", toolArgsMatchMode: "ignore" }),
    reference: trajectory("Explain HTTPS", ["search_notes"]),
    runs: {
      good: trajectory("Explain HTTPS", ["search_notes"]),
      bad:  trajectory("Explain HTTPS", ["search_notes", "search_notes"]),   // redundant call
    },
  },
];

for (const c of checks) {
  const good = await c.evaluator({ outputs: c.runs.good, referenceOutputs: c.reference });
  const bad = await c.evaluator({ outputs: c.runs.bad, referenceOutputs: c.reference });
  console.log(`${c.name.padEnd(34)} good → ${good.score}   bad → ${bad.score}`);
}
```

**Python**

```python
import itertools
from agentevals.trajectory.match import create_trajectory_match_evaluator
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

ids = itertools.count()
def trajectory(question, tools, answer="done"):
    msgs = [HumanMessage(question)]
    for name in tools:
        call_id = f"t{next(ids)}"
        msgs.append(AIMessage(content="", tool_calls=[{"name": name, "args": {}, "id": call_id, "type": "tool_call"}]))
        msgs.append(ToolMessage(content="ok", tool_call_id=call_id))
    msgs.append(AIMessage(answer))
    return msgs

checks = [
    ("weakest topic uses progress data",
     create_trajectory_match_evaluator(trajectory_match_mode="superset", tool_args_match_mode="ignore"),
     trajectory("What's my weakest topic?", ["get_progress"]),
     trajectory("What's my weakest topic?", ["get_progress", "search_notes"]),
     trajectory("What's my weakest topic?", ["search_notes"])),
    ("no unapproved writes",
     create_trajectory_match_evaluator(trajectory_match_mode="subset", tool_args_match_mode="ignore"),
     trajectory("Delete my progress", ["list_tables", "describe_table", "run_query"]),
     trajectory("Delete my progress", ["list_tables", "run_query"]),
     trajectory("Delete my progress", ["list_tables", "run_write"])),
    ("explanation uses notes once",
     create_trajectory_match_evaluator(trajectory_match_mode="strict", tool_args_match_mode="ignore"),
     trajectory("Explain HTTPS", ["search_notes"]),
     trajectory("Explain HTTPS", ["search_notes"]),
     trajectory("Explain HTTPS", ["search_notes", "search_notes"])),
]

for name, ev, ref, good, bad in checks:
    g = ev(outputs=good, reference_outputs=ref)["score"]
    b = ev(outputs=bad, reference_outputs=ref)["score"]
    print(f"{name:<34} good → {g}   bad → {b}")
```

**Expected**

```
weakest topic uses progress data   good → true   bad → false
no unapproved writes               good → true   bad → false
explanation uses notes once        good → true   bad → false
```

**Why these modes.** *Superset* says "at least these tools". The agent may consult more, but
it must not skip the data. *Subset* says "nothing outside this set". It is a natural way to
express "never call a write tool" as a test. *Strict* says "exactly this", which catches
wasteful repeat calls. In practice, **subset against a read-only reference is one of the most
valuable safety tests you can write for an agent.** It turns "the agent must never write
without approval" into a CI check that fails the day someone breaks it.
</details>

---

### Exercise 5 — A regression gate, and an online plan ●●●●○

1. Wrap Exercise 2's suite in a CI gate: compare against `eval-baseline.json`, allow 5 points
   of tolerance, exit non-zero on regression, and support `--update-baseline`.
2. Write a one-page **online evaluation plan** for StudyBuddy: what you sample, which
   evaluators run on live traffic, what you alert on, and how failures flow back into the
   dataset.

<details>
<summary>✅ Solution</summary>

**1 — the gate, JavaScript** (`eval-gate.mjs`)

```js
import fs from "node:fs";

// runSuite() is Exercise 2's loop, returning { summary: { containsFacts: 0.75, ... }, rows }
import { runSuite } from "./suite.mjs";

const BASELINE_FILE = "eval-baseline.json";
const TOLERANCE = 0.05;

const { summary, rows } = await runSuite();
const baseline = fs.existsSync(BASELINE_FILE) ? JSON.parse(fs.readFileSync(BASELINE_FILE, "utf8")) : {};

let regressed = false;
for (const [metric, score] of Object.entries(summary)) {
  const base = baseline[metric];
  const status = base === undefined ? "new" : score + TOLERANCE < base ? "REGRESSED" : "ok";
  if (status === "REGRESSED") regressed = true;
  console.log(`${metric.padEnd(14)} ${base?.toFixed(2) ?? " -- "} → ${score.toFixed(2)}  ${status}`);
}

if (regressed) {
  console.log("\nFailing examples:");
  for (const r of rows) {
    const failed = Object.keys(summary).filter((k) => r[k] === false);
    if (failed.length) console.log(`  [${failed}] ${r.q}`);
  }
}

if (process.argv.includes("--update-baseline")) {
  fs.writeFileSync(BASELINE_FILE, JSON.stringify(summary, null, 2) + "\n");
  console.log("baseline updated");
  process.exit(0);
}
process.exit(regressed ? 1 : 0);
```

**1 — the gate, Python** (`eval_gate.py`)

```python
import json, os, sys
from suite import run_suite            # Exercise 2's loop, returning (rows, summary)

BASELINE_FILE, TOLERANCE = "eval-baseline.json", 0.05

rows, summary = run_suite()
baseline = json.load(open(BASELINE_FILE)) if os.path.exists(BASELINE_FILE) else {}

regressed = False
for metric, score in summary.items():
    base = baseline.get(metric)
    status = "new" if base is None else ("REGRESSED" if score + TOLERANCE < base else "ok")
    regressed |= status == "REGRESSED"
    print(f"{metric:<15} {'--' if base is None else f'{base:.2f}'} → {score:.2f}  {status}")

if regressed:
    print("\nFailing examples:")
    for r in rows:
        failed = [k for k in summary if r.get(k) is False]
        if failed:
            print(f"  {failed} {r['q']}")

if "--update-baseline" in sys.argv:
    json.dump(summary, open(BASELINE_FILE, "w"), indent=2)
    print("baseline updated")
    sys.exit(0)
sys.exit(1 if regressed else 0)
```

```yaml
# .github/workflows/evals.yml  (the cheap suite on every PR)
on: [pull_request]
jobs:
  evals:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 22 }
      - run: npm ci
      - run: node eval-gate.mjs
```

**2 — the online evaluation plan**

```
   SAMPLE
     • 5% of conversations, stratified by route (chat, quiz, analytics)
     • 100% of: errors, limit exits, fallbacks, thumbs-down, long conversations (>20 turns)

   EVALUATE ON LIVE TRAFFIC (reference-free)
     • groundedness judge on answers that used retrieved notes
     • code checks: refusal rate, empty answers, answers > 400 words, PII in outputs
     • trajectory safety: any write tool call without an approval record → page someone

   METRICS & ALERTS
     • thumbs-down rate (7-day baseline; alert at +50%)
     • groundedness pass rate (alert below 85%)
     • fallback rate (alert above 2% — the early outage signal from Day 24)
     • cost per conversation p95 (alert at 2× baseline)
     • p95 latency per route

   FEEDBACK LOOP
     • every thumbs-down and every failed online check lands in a review queue
     • reviewers label it; confirmed failures become dataset examples with references
     • the offline suite grows every week; the CI gate protects every fix

   PRIVACY
     • PII redacted before tracing; traces retained 30 days; access limited to the on-call
       rotation and the quality reviewers
```

**Why both halves.** The gate stops *known* failures from coming back. The online plan finds
*new* ones: questions nobody thought to write, a provider quietly changing a model, notes going
out of date. It feeds them into the dataset, which makes the gate stronger every week. A team
with only the first half gets surprised in production. A team with only the second keeps
breaking things it already fixed.
</details>

---

## 9. Interview questions

### Basic

**Q1. What's the difference between observability and evaluation?**

Observability is seeing what happened inside a specific run: the trace of model calls, tool
calls, inputs and outputs. Evaluation is measuring how good the system is, repeatably, on a
set of examples. You use observability to debug one bad answer, and evaluation to decide
whether a change made things better overall.

---

**Q2. What is a trace?**

A tree of runs for one request. At the top is the agent or chain. Inside it are nested model
calls, tool calls and custom steps, each with inputs, outputs, timing and errors. LangChain
produces the events through callbacks. A tracer (LangSmith, OpenTelemetry, your own handler)
records them.

---

**Q3. What kinds of evaluators are there?**

Four kinds:

- **Code evaluators** — exact match, contains, schema, regex. Free and deterministic (same
  result every time).
- **Trajectory evaluators** — did an agent call the right tools?
- **LLM-as-judge** — a model grades against a rubric, for qualities code can't check.
- **Human review** — the ground truth that calibrates the others.

---

**Q4. How do you track token usage and cost?**

Every `AIMessage` has `usage_metadata`. Sum it over a run's messages, or record it in a callback
handler's model-end hook. In Python, `get_usage_metadata_callback()` totals it per model name.
Cost is tokens multiplied by each model's price. So per-model totals matter when you use
several models.

---

**Q5. How do you turn on LangSmith tracing?**

Set `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY` and optionally `LANGSMITH_PROJECT`. LangChain
and LangGraph runs are traced automatically. Wrap your own functions with `traceable` to
include them. With tracing off, `traceable` is a transparent wrapper.

---

### Intermediate

**Q6. How do you build a good evaluation dataset?**

Start from production: every reported failure, plus a sample of real questions in real
proportions. Add expert-written edge cases. Use synthetic examples for coverage, but never
alone, because models generate questions that models find easy. Start with 20–50 real
examples. Give each a reference (an answer, required facts, or an expected trajectory). Grow
the dataset every time something breaks.

---

**Q7. How do you know an LLM-as-judge is trustworthy?**

Calibrate it: label 30–50 outputs yourself, run the judge on the same ones, and measure
agreement. Count false positives and false negatives separately, since they rarely cost the
same. Use binary judgments with reasoning, an explicit rubric, few-shot examples, and a
different model family from the one being judged. Re-calibrate whenever the judge model or
rubric changes.

---

**Q8. How do you evaluate an agent, beyond its final answer?**

Evaluate its trajectory: compare the tool calls it made to a reference. Pick the mode that
matches the requirement:

- **strict** — the exact sequence.
- **unordered** — the same tools, in any order.
- **subset** — "never call anything outside this set". A good safety check for write tools.
- **superset** — "must at least call these".

Combine this with final-answer evaluators and counts of cost and steps.

---

**Q9. How would you evaluate a RAG system?**

Separately at its two failure points. Retrieval, with labelled relevant chunks: hit rate,
recall@k, MRR. Generation, with judges: groundedness (claims supported by context), answer
relevance, and correctness against references. If recall is low, fix retrieval. If recall is
high but groundedness is low, fix the prompt or model. One end-to-end score hides which.

---

**Q10. Offline vs online evaluation?**

Offline runs a fixed dataset with references before shipping. It answers "is B better than
A?" and gates changes in CI. Online samples live traffic with reference-free evaluators,
user feedback and operational metrics. It answers "is it still working?" and finds new
failure types. Online findings feed the offline dataset.

---

**Q11. Why do callbacks matter if you use LangSmith?**

LangSmith's tracer *is* a callback handler. Knowing the callback model lets you add your own
metrics and logs, and send events to other backends. It also helps you avoid the classic
mistake of listening for `handleLLMStart` / `on_llm_start`. Chat models fire
`handleChatModelStart` / `on_chat_model_start` instead, so the naive handler records nothing.

---

### Advanced

**Q12. Your teammate says the new prompt is better. How do you decide?**

Run both versions on the same dataset, ideally 50+ real examples including past failures.
Use the same evaluators: code checks first, then a calibrated judge, then trajectory checks
for agent behaviour. Compare per metric, and read every example whose result changed in
either direction. Check cost and latency too. If the dataset is small, look at the size of
the difference relative to run-to-run noise (run each version twice). Then ship behind a flag
and watch the online metrics. "Better" means better on the metrics you agreed matter, not
better on the examples someone happened to read.

---

**Q13. Design the evaluation system for a production agent.**

```
   DATASET     seeded from production failures and samples; references per example;
               grows from a review queue fed by thumbs-down and failed online checks
   OFFLINE     code evaluators + trajectory checks on every PR (cheap, deterministic);
               calibrated judges nightly and before releases (costly); a regression gate
   ONLINE      sampled traffic + 100% of errors/limits/negative feedback; reference-free
               judges (groundedness), safety trajectory checks, cost/latency/error metrics
   LABELS      prompt version, model, route and user segment on every run
   CALIBRATION judges re-checked against human labels on a schedule
   PRIVACY     redaction before tracing, access control, retention
```

The piece people skip is the loop: without a path from production failures back into the
dataset, the offline suite slowly stops representing reality.

---

**Q14. What are the known biases of LLM judges and how do you mitigate them?**

The known biases:

- **Verbosity bias** — longer answers score higher.
- **Position bias** — in pairwise comparisons, the first or second answer is favoured.
- **Self-preference** — a model rates its own family's style higher.
- **Leniency** — models tend to pass borderline answers.

Mitigations:

- binary judgments with a reasoning step
- explicit rubrics that penalise padding
- swapping positions in pairwise comparisons and averaging
- a different model family as judge
- few-shot examples of hard negatives
- and, the only real proof, calibration against human labels.

---

**Q15. How do you handle PII and privacy in traces?**

Traces contain user input, retrieved documents and model output. Treat them as production
data. Redact at the edge, before content reaches the model and the tracer. The PII middleware
changes what the model sees, but the top-level run still records the original input.
Restrict who can read production traces, set a retention period, and sample normal traffic
rather than tracing everything forever. For the most sensitive routes, record only metadata
and scores, not content.

---

## 10. Recap

### What you learned

- ✅ **Observability** explains one run; **evaluation** measures the system
- ✅ A trace is a tree of runs, built from **callbacks**
- ✅ Chat models fire **`handleChatModelStart` / `on_chat_model_start`**, not the LLM-start hook
- ✅ Tokens from `usage_metadata`, a handler, or Python's **per-model** usage callback — all agree
- ✅ Label every run with **run name, tags, and metadata** (prompt version, model)
- ✅ LangSmith turns on with **env vars**; `traceable` covers your own code, and is a no-op when off
- ✅ Datasets come from **production failures first**; start with 20–50 real examples
- ✅ Evaluator order: **code, then trajectory, then LLM-as-judge, then humans**
- ✅ `openevals` judges return **`{ key, score, comment }`**; calibrate them against human labels
- ✅ `agentevals` trajectory modes: **strict, unordered, subset and superset**
- ✅ RAG: measure **retrieval and generation separately**
- ✅ Offline evals gate changes; online evals find new failures; the loop connects them
- ✅ Python's `evaluate` runs locally with `upload_results=False`; JS needed credentials in our tests

### The quality loop

```
   failure reported → read the trace → add to dataset → fix → suite passes → ship
          ▲                                                                   │
          └──────────────── online evals find the next one ◄──────────────────┘
```

### Tomorrow

**[Day 26 — MCP & the Vercel AI SDK](day-26-mcp-and-ai-sdk.md)**: your tools so far have lived
inside your codebase. Tomorrow you'll expose them over the Model Context Protocol, so any MCP
client can use StudyBuddy's notes. You'll also use other people's MCP servers from a LangChain
agent. Then you'll meet the Vercel AI SDK: what it does differently from LangChain, and when
to choose which.

### Quick self-check

1. Your metrics handler reports zero model calls, but the agent clearly answered. What's the
   likely bug?
2. A judge says your new prompt is 94% correct. What do you need to know before believing it?
3. RAG answers got worse after a change. How do you tell whether retrieval or generation is
   to blame?

<details>
<summary>Answers</summary>

1. It's listening for `handleLLMStart` / `on_llm_start`. Chat models fire
   `handleChatModelStart` / `on_chat_model_start` instead (verified: the LLM-start hook fired
   zero times on an agent run with two model calls). Count on the chat-model hook; model-end
   still arrives as `handleLLMEnd` / `on_llm_end`.

2. How well the judge agrees with human labels on the same kind of examples, and what its
   false-positive rate is. A judge that passes wrong answers inflates scores. Also ask:
   - Was it run on a representative dataset (not synthetic easy questions)?
   - Is the judge a different model family?
   - How does 94% compare to the old prompt on the *same* dataset with the same judge?

3. Measure them separately. Run retrieval metrics (hit rate, recall@k, MRR) on labelled
   questions: if recall dropped, the problem is chunking, embeddings or retrieval. If recall
   is unchanged, run groundedness and correctness judges on the answers: if they dropped, the
   problem is in the prompt or model. A single end-to-end score can't distinguish the two.
</details>

---

<div align="center">

**[← Day 24 — Reliability](day-24-reliability.md)** · **[Week 4 index](README.md)** · **[Day 26 — MCP & AI SDK →](day-26-mcp-and-ai-sdk.md)**

</div>
