# LCEL Cheatsheet

Runnables at a glance, in both languages. Taught in
[Day 07](../week-01-foundations/day-07-lcel-and-runnables.md); every form below was run.

---

## The one idea

```
   Everything is a Runnable:  invoke · stream · batch  (+ async variants)
   Runnable ⟶ pipe ⟶ Runnable  =  a Runnable
```

Prompts, models, parsers, retrievers, functions, whole chains and compiled graphs all share
that interface — so they compose, stream, batch and trace the same way.

## Imports

```js
import { RunnableSequence, RunnableParallel, RunnableLambda, RunnablePassthrough, RunnableBranch }
  from "@langchain/core/runnables";
```
```python
from langchain_core.runnables import (
    RunnableParallel, RunnableLambda, RunnablePassthrough, RunnableBranch,
)
from operator import itemgetter        # Python's favourite way to pick a key
```

## The six building blocks

| Block | Does | JavaScript | Python |
|---|---|---|---|
| **Sequence** | output of one → input of the next | `a.pipe(b).pipe(c)` or `RunnableSequence.from([a, b, c])` | `a \| b \| c` |
| **Parallel** | same input → several steps concurrently → object | `RunnableParallel.from({ x: a, y: b })` | `RunnableParallel(x=a, y=b)` or a plain dict in a pipe |
| **Lambda** | any function as a step | `RunnableLambda.from(fn)` (bare functions auto-coerce in `.pipe`) | `RunnableLambda(fn)` (callables auto-coerce in `\|`) |
| **Passthrough** | keep the input as-is | `new RunnablePassthrough()` | `RunnablePassthrough()` |
| **Assign** | add keys, keep everything else | `RunnablePassthrough.assign({ k: fn })` | `RunnablePassthrough.assign(k=fn)` |
| **Branch** | if / else-if / else | `RunnableBranch.from([[cond, r], [cond, r], default])` | `RunnableBranch((cond, r), (cond, r), default)` |

Verified results:

```
   pipe + coercion        {topic: "rain"} → "RAIN!"
   parallel               "hi" → { a: "HI", b: 2 }
   passthrough in object  "hi" → { orig: "hi", up: "HI" }
   assign                 { text: "abc", id: 1 } → { text: "abc", id: 1, n: 3 }   ← id survives
   branch                 3 → "small"
```

## Recipes

### Prompt → model → string

```js
const chain = prompt.pipe(model).pipe(new StringOutputParser());
await chain.invoke({ topic: "gravity" });
```
```python
chain = prompt | model | StrOutputParser()
chain.invoke({"topic": "gravity"})
```

### Keep the input alongside a result (the RAG shape)

```js
const rag = RunnableSequence.from([
  { context: retriever.pipe(formatDocs), question: new RunnablePassthrough() },
  prompt, model, new StringOutputParser(),
]);
```
```python
rag = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | prompt | model | StrOutputParser()
)
```

> 📦 **JS:** a plain object only becomes a parallel step *inside* `RunnableSequence.from([...])`
> (or when piped into). **Python:** a plain dict coerces anywhere in a `|` chain.

### Pick one key from the input

```js
const chain = RunnableLambda.from((x) => x.question).pipe(retriever);
```
```python
chain = itemgetter("question") | retriever
```

### Enrich, don't replace

```js
const enriched = RunnablePassthrough.assign({ wordCount: (x) => x.text.split(/\s+/).length });
```
```python
enriched = RunnablePassthrough.assign(word_count=lambda x: len(x["text"].split()))
```

## Running

| | JavaScript | Python |
|---|---|---|
| one input | `await chain.invoke(x)` | `chain.invoke(x)` / `await chain.ainvoke(x)` |
| stream | `for await (const c of await chain.stream(x))` | `for c in chain.stream(x)` / `async for c in chain.astream(x)` |
| many inputs | `await chain.batch(xs, { maxConcurrency: 5 })` | `chain.batch(xs, config={"max_concurrency": 5})` |
| every intermediate event | `chain.streamEvents(x, { version: "v2" })` | `chain.astream_events(x, version="v2")` |

Verified: a batch of 5 with a concurrency limit of 2 never exceeded 2 in flight, in both
languages.

## Modifiers — each returns a Runnable

| Modifier | JavaScript | Python |
|---|---|---|
| retry | `.withRetry({ stopAfterAttempt: 3 })` | `.with_retry(stop_after_attempt=3)` |
| fallback | `.withFallbacks([backup])` | `.with_fallbacks([backup])` |
| name / tags / metadata | `.withConfig({ runName, tags, metadata })` | `.with_config(run_name=..., tags=[...], metadata={...})` |
| fix call arguments | `.bind({ stop: ["\n"] })` | `.bind(stop=["\n"])` |
| per-call config | `invoke(x, { callbacks, tags, timeout, signal })` | `invoke(x, {"callbacks": [...], "tags": [...]})` |

Verified: `withConfig({ runName: "shout", tags: ["t1"] })` was visible to a callback handler as
the run name and tags; `withRetry({ stopAfterAttempt: 3 })` succeeded on the third attempt.
For which layer should own retries, see
[Day 24](../week-04-production-projects-and-interviews/day-24-reliability.md).

## Debugging

```js
const chain = prompt.pipe(model).withConfig({ runName: "explain" });   // named runs in traces
for await (const ev of chain.streamEvents(input, { version: "v2" })) console.log(ev.event, ev.name);
```
```python
chain = (prompt | model).with_config(run_name="explain")
chain.get_graph().print_ascii()        # needs: pip install grandalf
```

## Five rules that prevent most LCEL bugs

1. **Anything after a non-streaming step buffers.** `model.pipe(parser).pipe((s) => s.trim())`
   stops token streaming — transform before the model, or stream-transform (Day 23).
2. **Lambdas take one argument.** Pass an object/dict if you need several values.
3. **Parallel steps get the same input.** If step B needs step A's output, it's a sequence.
4. **`assign` keeps keys; a parallel object replaces them.** Choose deliberately.
5. **Use a chain when the steps are known.** When the next step depends on a result, reach
   for a graph ([Day 17](../week-03-tools-agents-and-langgraph/day-17-langgraph-basics.md)).
