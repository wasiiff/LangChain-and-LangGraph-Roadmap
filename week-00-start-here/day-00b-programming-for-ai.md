# Day 0B — Programming for AI: JSON, HTTP, Async & Schemas in JS and Python

> ⏱ **Time:** ~2.5 hours · 🎯 **Prereqs:** [Day 0A](day-00a-your-toolkit.md) (or "you already code") · 🧩 **Difficulty:** ●●○○○

**Today you learn:** Every call to a language model is a message sent over the internet. The
answer comes back later, as text in a fixed format, and sometimes it comes back as an error. If
JSON, HTTP and `await` are new to you, the code on Day 1 looks like magic. Today you learn the
six tools that every AI example quietly uses, in both languages. They are JSON, HTTP requests,
async code, streams, schemas (Zod and Pydantic), and safe handling of keys and errors. You need
no API key: you will run a small pretend AI API on your own computer.

This is the day that stops you copy-pasting code you don't understand.

> 📖 **Words you'll meet today**
>
> - **JSON** — a text format for data, with objects `{…}` and lists `[…]`. Every AI API speaks it.
> - **HTTP request** — a message your program sends to a server: a method, an address, headers
>   and a body.
> - **Status code** — the three-digit number at the top of the reply, such as 200 (OK) or 429
>   (too many requests).
> - **API key** — a secret password that identifies you to a provider. It travels in a header.
> - **Async / await** — a way to start slow work, such as a network call, and wait for the
>   result without freezing the program.
> - **Stream** — a reply that arrives in small pieces over time, instead of all at once.
> - **Schema** — a description of the exact shape your data must have. Zod (JavaScript) and
>   Pydantic (Python) check data against one.
> - **Environment variable** — a named setting that lives outside your code, such as
>   `GROQ_API_KEY`.

---

## 1. The problem

You open an AI provider's documentation. The first example looks like this:

```
POST https://api.groq.com/openai/v1/chat/completions
Authorization: Bearer $GROQ_API_KEY
Content-Type: application/json

{"model": "openai/gpt-oss-120b", "messages": [{"role": "user", "content": "Hi"}]}
```

You try to turn it into code. Your first attempt looks like this:

```js
const res = fetch(URL, { method: "POST", body: { messages: [{ role: "user", content: "Hi" }] } });
console.log(res.choices[0]);
// TypeError: Cannot read properties of undefined (reading '0')
```

There are three bugs in two lines. `fetch` was not awaited, so `res` is a promise of a reply,
not the reply. The body is an object, not JSON text, so the server cannot read it. And there
is no key, so even a perfect request would be refused with status 401.

**None of these are AI problems.** They are JSON, HTTP and async problems. Most hours people
spend "debugging LangChain" are really hours spent on these three things. Today you clear
them out of the way, once, in both languages.

### The real-life version

Think of ordering food by post from a restaurant.

```
   you fill in an order form             → JSON         (a fixed format both sides understand)
   you post it to the restaurant address → HTTP request (method + address + envelope + form)
   you include your membership card      → API key      (proves who you are)
   you carry on with your day            → async        (you don't stand frozen at the door)
   the meal arrives in several boxes     → streaming    (pieces arrive one after another)
   the kitchen checks the form           → schema       (wrong form = sent back)
   "kitchen too busy, try in 5 minutes"  → status 429   (rate limit, with a wait time)
```

If you understand that picture, you understand today's whole lesson. The rest is syntax.

---

## 2. Mental model

One model call is a round trip. Here is every step, and the tool you use at each one:

```
   your code                                                     the provider
   ─────────                                                     ────────────
   object / dict ──JSON.stringify / json.dumps──► JSON text
                                                  │
                         HTTP POST + headers (key, content type)
                                                  ▼
                                             ┌─────────┐
                                             │  model  │   (slow: hundreds of ms or more)
                                             └─────────┘
                                                  │
                         status code + headers + JSON body (maybe streamed in pieces)
                                                  ▼
   object / dict ◄──JSON.parse / json.loads─── JSON text
        │
        └──► schema check (Zod / Pydantic) ──► safe to use in your app
```

What you need to know, and where it shows up later in the course:

```
   ┌──────────────────┬──────────────────────┬────────────────────────────┐
   │ Feature          │ JS form              │ You'll meet it on…         │
   ├──────────────────┼──────────────────────┼────────────────────────────┤
   │ data format      │ JSON.parse/stringify │ every API reply            │
   │ requests         │ fetch                │ every provider SDK (Day 02)│
   │ modules          │ import / export      │ literally every file       │
   │ async            │ async / await        │ every model call           │
   │ concurrency      │ Promise.all          │ RunnableParallel (Day 07)  │
   │ async iteration  │ for await…of         │ .stream()  (Day 04, 23)    │
   │ generators       │ async function*      │ custom streaming (Day 23)  │
   │ schemas          │ Zod                  │ tools & structured output  │
   │ types            │ TS generics          │ reading every doc example  │
   │ env + secrets    │ dotenv               │ every project              │
   │ errors           │ try/catch + custom   │ retries, fallbacks (Day 24)│
   └──────────────────┴──────────────────────┴────────────────────────────┘
```

| Step | JavaScript | Python | What goes wrong if you skip it |
|---|---|---|---|
| Make JSON text | `JSON.stringify(obj)` | `json.dumps(d)` | the server gets `[object Object]` and answers 400 |
| Send the request | `await fetch(url, {…})` | `httpx.post(url, json=…)` | no `await` → a promise, not a reply |
| Prove who you are | `Authorization: Bearer <key>` header | same header | 401 |
| Check the status | `res.ok` / `res.status` | `res.is_success` / `raise_for_status()` | you read an error body as if it were an answer |
| Read the JSON | `await res.json()` | `res.json()` | — |
| Check the shape | `Schema.parse(data)` (Zod) | `Model.model_validate(data)` (Pydantic) | bad data reaches your database |

---

## 3. First principles

### 3.1 JSON — the format every AI API speaks

> 💬 **In plain words:** JSON is data written as text, so two programs can swap it. You turn
> your data into text before sending, and turn text back into data after receiving.

A program keeps data in memory as objects (JavaScript) or dicts (Python). The network can only
carry text. **JSON** (JavaScript Object Notation) is the agreed text format in between. It has
only six kinds of value:

| JSON value | Example | JavaScript | Python |
|---|---|---|---|
| object | `{"name": "Wasif"}` | object | `dict` |
| array (list) | `["dev", "ai"]` | array | `list` |
| string | `"hello"` (double quotes only) | string | `str` |
| number | `27`, `0.5` | number | `int` / `float` |
| true / false | `true` | boolean | `True` / `False` |
| null | `null` | `null` | `None` |

Two functions do all the work. One turns data into text; the other turns text back into data.

```js
const obj = { name: "Wasif", age: 27, tags: ["dev"], admin: false, manager: null };
const text = JSON.stringify(obj);          // data → text, ready to send
console.log(text, typeof text);
// {"name":"Wasif","age":27,"tags":["dev"],"admin":false,"manager":null} string

const back = JSON.parse(text);             // text → data, ready to use
console.log(back.tags[0], typeof back);    // dev object
```

```python
import json

obj = {"name": "Wasif", "age": 27, "tags": ["dev"], "admin": False, "manager": None}
text = json.dumps(obj)                     # data → text, ready to send
print(text, type(text).__name__)
# {"name": "Wasif", "age": 27, "tags": ["dev"], "admin": false, "manager": null} str

back = json.loads(text)                    # text → data, ready to use
print(back["tags"][0], type(back).__name__)   # dev dict
```

Notice that Python's `True` and `None` became JSON's `true` and `null`. Add `indent=2`
(`JSON.stringify(obj, null, 2)` in JS) when you want text that people can read.

**JSON is strict.** These all fail, and you will see each of them when a model writes "JSON"
that isn't quite right:

| Text you try to parse | JavaScript error (verified) | Python error (verified) |
|---|---|---|
| `{'name': 'Wasif'}` (single quotes) | `SyntaxError: Expected property name or '}' in JSON at position 1` | `JSONDecodeError: Expecting property name enclosed in double quotes` |
| `{"a": 1,}` (trailing comma) | `SyntaxError: Expected double-quoted property name in JSON at position 8` | `JSONDecodeError: Illegal trailing comma before end of object` |
| `` (empty body) | `SyntaxError: Unexpected end of JSON input` | `JSONDecodeError: Expecting value: line 1 column 1 (char 0)` |
| `<html>502 Bad Gateway</html>` | `SyntaxError: Unexpected token '<', "<html>502 "... is not valid JSON` | `JSONDecodeError: Expecting value: line 1 column 1 (char 0)` |

The last row matters. When a server is broken, it often answers with an HTML error page. Your
code then tries to parse HTML as JSON. The error mentions `'<'`, not the real problem, so
**check the status code before you parse**.

**What JSON cannot hold.** It has no dates and no "undefined". The two languages handle this
differently, and we measured it:

| You try to send | JavaScript | Python |
|---|---|---|
| a date | becomes a string: `"2026-10-07T09:00:00.000Z"` | `TypeError: Object of type datetime is not JSON serializable` |
| `undefined` / missing value | the key is silently dropped | (no `undefined` in Python) |
| `NaN` | becomes `null` | — |
| the integer `12345678901234567890` | parsed as `12345678901234567000` (precision lost) | parsed exactly |

> ⚠️ **Large IDs.** JavaScript numbers lose precision above about 9 quadrillion. If an API
> sends long numeric IDs, keep them as strings. Python's integers have no such limit.

### 3.2 HTTP in plain terms

> 💬 **In plain words:** HTTP is the envelope your JSON travels in. You send a request with an
> address, some labels and a body. You get back a status number, some labels and a body.

A **request** has four parts:

| Part | Example | Meaning |
|---|---|---|
| method | `POST` | what you want: `GET` reads, `POST` sends data to be processed |
| URL | `http://127.0.0.1:8787/v1/chat` | the address of the thing you want |
| headers | `Authorization: Bearer test-key-123` | labels on the envelope: who you are, what the body is |
| body | `{"messages": [...]}` | the JSON itself |

A **response** has three parts: a **status code**, headers, and a body. The status code tells
you what happened before you read anything else. These are the ones you will meet every week:

| Code | Name | What it means for an AI call | Retry? |
|---|---|---|---|
| 200 | OK | it worked; the answer is in the body | — |
| 400 | Bad Request | your request is wrong: bad JSON, a missing field, too many tokens | ❌ fix it first |
| 401 | Unauthorized | the key is missing or wrong | ❌ never — fix the config |
| 404 / 405 | Not Found / Method Not Allowed | wrong address, or `GET` where `POST` was needed | ❌ |
| 429 | Too Many Requests | you hit the rate limit; often sends a `Retry-After` header | ✅ after waiting |
| 500 / 502 / 503 | server errors | the provider has a problem | ✅ a few times, then fall back |

Codes in the 200s mean success. Codes in the 400s mean **you** did something wrong. Codes in
the 500s mean **they** did. That one rule tells you what to retry.

**The API key header.** Most providers want the key in a header like
`Authorization: Bearer <your key>`. "Bearer" just means "whoever carries this key is allowed
in". That is why a leaked key is dangerous: anyone who has it can spend your money.

**`fetch` and `httpx`.** JavaScript has `fetch` built in. In Python we use the `httpx` library,
because it offers both a normal (sync) client and an async one with the same API.

```js
const res = await fetch(URL, {
  method: "POST",
  headers: { "Content-Type": "application/json", Authorization: `Bearer ${key}` },
  body: JSON.stringify({ messages: [{ role: "user", content: "Hello!" }] }),
});
console.log(res.status, res.ok);       // 200 true
const data = await res.json();         // reading the body is async too
```

```python
import httpx

res = httpx.post(URL, headers={"Authorization": f"Bearer {key}"},
                 json={"messages": [{"role": "user", "content": "Hello!"}]})
print(res.status_code, res.is_success)  # 200 True
data = res.json()
```

Two details we checked by running them. With `fetch`, a string body is labelled
`text/plain;charset=UTF-8` unless you set `Content-Type` yourself. With `httpx`, `json=` turns
your dict into JSON text **and** sets `Content-Type: application/json` for you.

> ⚠️ **Neither `fetch` nor `httpx` raises an error on a 401, 429 or 500.** A bad status is
> still "a reply". You must check `res.ok` (JS) or call `res.raise_for_status()` (Python).
> Exercise 3 shows what happens when you forget.

You will see the full round trip, with a real server, in §4.1 and §5.1.

### 3.3 JavaScript: ESM vs CommonJS

> 💬 **In plain words:** JavaScript has two ways to share code between files. AI libraries use
> the modern one, `import`, and you switch it on with one line in `package.json`.

Two module systems exist. LangChain JS is **ESM-first**.

| | CommonJS (old) | ESM (modern) |
|---|---|---|
| Import | `const x = require("y")` | `import x from "y"` |
| Export | `module.exports = x` | `export default x` / `export { x }` |
| Top-level `await` | ❌ not allowed | ✅ allowed |
| Enabled by | `"type": "commonjs"`, or `.cjs` | `"type": "module"` in package.json, or `.mjs` |

The fix is one line in `package.json`:

```json
{ "type": "module" }
```

We tested what happens without it, on Node 24.15 and npm 11.12:

- `npm init -y` writes `"type": "commonjs"` into `package.json`. Then any `import` fails with
  `SyntaxError: Cannot use import statement outside a module`.
- If `package.json` has **no** `"type"` at all, Node guesses. It sees `import`, prints a
  `MODULE_TYPELESS_PACKAGE_JSON` warning, and runs the file as ESM anyway.
- A `require(...)` inside an ESM file fails with
  `ReferenceError: require is not defined in ES module scope, you can use import instead`.

So set `"type": "module"` yourself. Don't rely on the guess.

```js
// ❌ SyntaxError: Cannot use import statement outside a module
import { ChatGroq } from "@langchain/groq";
```

**Why ESM matters here:** top-level `await`. Nearly every LangChain example does
`await model.invoke(...)` at the top level of a file. In CommonJS that line fails with
`SyntaxError: await is only valid in async functions and the top level bodies of modules`, so
you'd have to wrap everything in `(async () => { ... })()`.

```js
// ESM — clean
const res = await model.invoke("hi");

// CommonJS — the wrapper you'd need
(async () => {
  const res = await model.invoke("hi");
})();
```

**Named vs default imports:**

```js
import { ChatGroq } from "@langchain/groq";      // named — the common case
import Groq from "groq-sdk";                     // default
import Groq, { toFile } from "groq-sdk";         // both
import * as z from "zod";                        // namespace — how LangChain docs import Zod
```

### 3.4 Async, everywhere

> 💬 **In plain words:** a network call takes a long time in computer terms. `async` code
> starts the call, does other work while it waits, and `await` picks up the answer when it
> arrives.

**Every** LLM call is network I/O (input/output), so it's async in both languages.

```js
// A Promise is a box that will contain a value later.
const promise = model.invoke("hi");   // no await → a Promise, not the answer
console.log(promise);                  // Promise { <pending> }  ← the classic bug

const answer = await model.invoke("hi");  // await unwraps it
```

We ran exactly this. Without `await`, `promise.content` is `undefined`, and putting the promise
in a string prints `[object Promise]`. Python has the same trap: an un-awaited call gives you
a `coroutine` object, and `.content` fails with
`AttributeError: 'coroutine' object has no attribute 'content'`.

> 🐛 **The #1 async bug in AI code:** forgetting `await` and then getting
> `undefined`, `[object Promise]`, or `TypeError: Cannot read properties of undefined (reading 'content')`.
> If you see `Promise { <pending> }` in a log, you missed an `await`.

**Sequential vs parallel — this is a real money/latency difference:**

```js
// ❌ SEQUENTIAL — 3 seconds (1s each, one after another)
const a = await model.invoke("Summarise chapter 1");
const b = await model.invoke("Summarise chapter 2");
const c = await model.invoke("Summarise chapter 3");

// ✅ PARALLEL — 1 second (all three in flight at once)
const [a, b, c] = await Promise.all([
  model.invoke("Summarise chapter 1"),
  model.invoke("Summarise chapter 2"),
  model.invoke("Summarise chapter 3"),
]);
```

The seconds in those comments are illustrative. §4.3 measures real numbers with a pretend
model that takes 300 ms per call: **931 ms** one after another, **316 ms** in parallel.

**`Promise.all` vs `Promise.allSettled`:**

```js
// Promise.all — ONE rejection kills everything, you lose the successful results
try {
  const results = await Promise.all(tasks);
} catch (e) { /* which one failed? what about the others? */ }

// Promise.allSettled — always resolves; inspect each outcome
const results = await Promise.allSettled(tasks);
const ok = results.filter((r) => r.status === "fulfilled").map((r) => r.value);
const bad = results.filter((r) => r.status === "rejected").map((r) => r.reason);
```

With one failing task out of three, we measured: `Promise.all` threw `429 rate limit`, and
`Promise.allSettled` returned `[ 'fulfilled', 'rejected', 'fulfilled' ]`. For batch LLM work,
such as embedding 500 chunks, `allSettled` is almost always what you want. One rate-limit error
shouldn't throw away 499 successes.

### 3.5 Async iterators & generators — how streaming works

> 💬 **In plain words:** a stream is a list whose items arrive one at a time. You read it with a
> special loop, and you can write a function that hands out items one at a time too.

An **async iterator** is anything you can `for await...of`. Streaming responses are async
iterators.

```js
for await (const chunk of stream) {
  process.stdout.write(chunk.content);
}
```

An **async generator** is how you *create* one. This is exactly how you'd pipe LLM tokens to a
web response:

```js
async function* upperCaseStream(stream) {
  for await (const chunk of stream) {
    yield chunk.content.toUpperCase();      // transform each token as it arrives
  }
}

for await (const t of upperCaseStream(await model.stream("hi"))) {
  process.stdout.write(t);
}
```

`yield` means "hand out this value now, pause, and continue when the reader asks for more."
Understanding `async function*` is the difference between *using* streaming and *building*
streaming (Day 23).

### 3.6 Zod — runtime schemas for JavaScript

> 💬 **In plain words:** a model can send back data in the wrong shape. A schema is a checklist
> for the shape, and Zod checks data against it while the program runs.

TypeScript types vanish when your code runs. Zod schemas exist at runtime, which is why
LangChain uses Zod for tool arguments and structured output.

```js
import * as z from "zod";

const User = z.object({
  name: z.string().describe("Full name"),          // .describe() → goes into the LLM prompt!
  age: z.number().int().min(0).max(150),
  email: z.string().email().optional(),
  role: z.enum(["admin", "user", "guest"]).default("user"),
  tags: z.array(z.string()),
});

// throws on invalid
const user = User.parse({ name: "Wasif", age: 27, tags: ["dev"] });

// doesn't throw
const result = User.safeParse({ name: "Wasif", age: -5, tags: [] });
if (!result.success) console.log(result.error.issues);
```

Verified with Zod 4.6.5. `user` came back as `{ name: 'Wasif', age: 27, role: 'user', tags: [ 'dev' ] }`
— the default role was filled in. The bad one printed one issue:
`path: [ 'age' ], message: 'Too small: expected number to be >=0'`. Calling `User.parse` on
the bad data threw a `ZodError`.

> 🔑 **`.describe()` is not documentation.** LangChain converts your Zod schema into a JSON
> Schema that goes into the prompt, and `.describe()` becomes the field description the model
> reads. A good description is the difference between the model filling a field correctly and
> filling it with garbage. Descriptions are prompts.

You can see this yourself: `z.toJSONSchema(User)` printed
`"name":{"type":"string","description":"Full name"}`. That text is what the model reads.

Common patterns you'll use all book:

```js
z.string().describe("The city to look up")
z.number().describe("Temperature in Celsius")
z.boolean()
z.array(z.string()).describe("List of key topics")
z.enum(["positive", "negative", "neutral"])
z.object({ nested: z.object({ deep: z.string() }) })
z.string().nullable()          // string | null
z.string().optional()          // string | undefined — field may be absent
z.union([z.string(), z.number()])
```

### 3.7 TypeScript survival kit (for JS devs)

> 💬 **In plain words:** most AI docs are written in TypeScript, which is JavaScript plus type
> labels. You only need to read it, and usually you just delete the labels.

You'll read TS in every doc even if you write JS. You need to *read* it, not write it.

```ts
let name: string = "Wasif";                 // annotation — delete it, it's still valid JS
function greet(n: string): string { }       // param and return types

interface Config { model: string; temperature?: number; }   // ? = optional
type Role = "system" | "user" | "assistant";                // union of literals

Array<string>                               // generic: "array OF string"
Promise<AIMessage>                          // "a promise resolving to an AIMessage"
Annotation<BaseMessage[]>                   // "an Annotation OF an array of BaseMessage"

const x = y as SomeType;                    // cast — trust me, compiler
const z = w!;                               // non-null assertion
```

Here is a real line from a LangGraph tutorial. It looks frightening, but it is five language
features stacked together — a generic, an object with a function inside, two arrow functions
and an array method. None of it is LangChain magic:

```ts
const graph = new StateGraph(Annotation.Root({
  messages: Annotation<BaseMessage[]>({ reducer: (a, b) => a.concat(b), default: () => [] }),
}));
```

**Translating a TS example to JS is usually just deleting the annotations:**

```ts
// TypeScript from the docs
const model: ChatGroq = new ChatGroq({ model: "openai/gpt-oss-120b" });
async function run(input: string): Promise<string> {
  const res: AIMessage = await model.invoke(input);
  return res.content as string;
}
```
```js
// The JavaScript you write
const model = new ChatGroq({ model: "openai/gpt-oss-120b" });
async function run(input) {
  const res = await model.invoke(input);
  return res.content;
}
```

If you paste TS into a `.js` file, Node stops at the first label. We got
`SyntaxError: Missing initializer in const declaration` for `const model: string = "x";`.

Generics inside `<>` that appear at *runtime* (like `Annotation<...>`) are the one exception —
those you keep in TS and rewrite differently in JS. Day 18 covers that specific case.

### 3.8 Python: the equivalents

> 💬 **In plain words:** Python has the same ideas with different names. Pydantic plays Zod's
> role, `asyncio` plays the role of promises, and `httpx` plays the role of `fetch`.

| Concept | JavaScript | Python |
|---|---|---|
| Module import | `import { X } from "y"` | `from y import X` |
| Async function | `async function f() {}` | `async def f(): ...` |
| Await | `await f()` | `await f()` |
| Parallel | `Promise.all([a, b])` | `asyncio.gather(a, b)` |
| Tolerant parallel | `Promise.allSettled` | `asyncio.gather(..., return_exceptions=True)` |
| Async iteration | `for await (const x of s)` | `async for x in s:` |
| Generator | `function*` / `yield` | `def gen(): yield` |
| Async generator | `async function*` | `async def gen(): yield` |
| HTTP client | `fetch` (built in) | `httpx` (sync and async) |
| JSON | `JSON.parse` / `JSON.stringify` | `json.loads` / `json.dumps` |
| Runtime schema | Zod | **Pydantic** |
| Static types | TypeScript | type hints + mypy |
| Env vars | `process.env.X` | `os.environ["X"]` |
| Isolation | `node_modules/` | `.venv/` |

**Pydantic — Python's Zod:**

```python
from pydantic import BaseModel, Field
from typing import Literal, Optional

class User(BaseModel):
    name: str = Field(description="Full name")        # description → goes into the prompt!
    age: int = Field(ge=0, le=150)
    email: Optional[str] = None
    role: Literal["admin", "user", "guest"] = "user"
    tags: list[str] = []

user = User(name="Wasif", age=27, tags=["dev"])        # raises ValidationError if invalid
user.model_dump()                                       # → dict
user.model_dump_json()                                  # → JSON string
User.model_validate({"name": "W", "age": 27, "tags": []})   # from a dict
User.model_json_schema()                                # → JSON Schema (what the LLM sees)
```

Verified with Pydantic 2.13.5. `model_dump()` gave
`{'name': 'Wasif', 'age': 27, 'email': None, 'role': 'user', 'tags': ['dev']}`, and
`User(name="Wasif", age=-5, tags=[])` raised
`age — Input should be greater than or equal to 0 [type=greater_than_equal, ...]`.

Zod ↔ Pydantic, line for line:

| Zod | Pydantic |
|---|---|
| `z.string()` | `str` |
| `z.number()` | `float` |
| `z.number().int()` | `int` |
| `z.boolean()` | `bool` |
| `z.array(z.string())` | `list[str]` |
| `z.enum(["a","b"])` | `Literal["a","b"]` |
| `z.string().optional()` | `Optional[str] = None` |
| `.describe("...")` | `Field(description="...")` |
| `.default(x)` | `= x` or `Field(default=x)` |
| `.min(0).max(10)` | `Field(ge=0, le=10)` |
| `Schema.parse(d)` | `Schema.model_validate(d)` (raises) |
| `Schema.safeParse(d)` | wrap in `try/except ValidationError` |

> ⚠️ **Pydantic is more forgiving than Zod by default.** We gave both the same data:
> `{"ok": "yes", "n": "40"}` for a boolean and an integer. Zod rejected both. Pydantic
> accepted them as `ok=True n=40`. Pass `strict=True` to `model_validate` if you want Zod's
> behaviour; then Pydantic said `Input should be a valid boolean`.

**Python async gotcha JS devs hit:**

```python
# ❌ SyntaxError — await only works inside async def
result = await model.ainvoke("hi")

# ✅ Option 1: run an async entry point
import asyncio
async def main():
    return await model.ainvoke("hi")
asyncio.run(main())

# ✅ Option 2: just use the sync method (very common in Python LangChain)
result = model.invoke("hi")
```

In a script, the first line fails with `SyntaxError: 'await' outside function`.

> 🔑 **Big JS↔Python difference.** In LangChain **JS, everything is async** — there is no sync
> version. In **Python, every method has both**: `invoke`/`ainvoke`, `stream`/`astream`,
> `batch`/`abatch`. The `a` prefix means async. Scripts and notebooks use the sync ones;
> web servers (FastAPI) should use the async ones.

We checked this on `@langchain/core` 1.2.17 and `langchain-core` 1.6.7. In JS, `invoke`
returned a `Promise` and there was no sync method. In Python, `invoke` returned an `AIMessage`
and `ainvoke` returned a coroutine.

### 3.9 Environment variables & secrets

> 💬 **In plain words:** keys and settings live outside your code, in a `.env` file or the
> system. Your code reads them at start-up and stops at once if one is missing.

```js
// JS — must be the FIRST import, before anything reads process.env
import "dotenv/config";
const key = process.env.GROQ_API_KEY;
if (!key) throw new Error("GROQ_API_KEY is not set");
```

```python
# Python — must run BEFORE you construct any client
from dotenv import load_dotenv
import os

load_dotenv()
key = os.environ["GROQ_API_KEY"]       # raises KeyError if missing — good, fail loudly
# os.getenv("X", "default")            # returns None/default — for optional config
```

**Fail fast on missing config.** A missing key found at start-up takes two seconds to fix. The
same key missing inside a request handler at 3 a.m. is an incident.

```js
const REQUIRED = ["GROQ_API_KEY", "GOOGLE_API_KEY"];
const missing = REQUIRED.filter((k) => !process.env[k]);
if (missing.length) throw new Error(`Missing env vars: ${missing.join(", ")}`);
```

> 🔒 **Never paste a key into code or commit `.env` to git.** Add `.env` to `.gitignore`
> (Day 0A). A key in a public repository can be found and used by strangers.

### 3.10 Error handling for LLM code

> 💬 **In plain words:** model calls fail in a few repeating ways. Some failures go away if you
> wait and try again; others never will, so retrying them only wastes time.

LLM calls fail in specific, recurring ways. Learn the list:

| Error | Retry? | Handling |
|---|---|---|
| `429 Rate limit` | ✅ yes, with backoff | Exponential backoff + jitter |
| `500/502/503` provider error | ✅ yes | Retry, then fall back to another model |
| `timeout` | ✅ yes, carefully | May have partially succeeded — beware side effects |
| `401 Invalid key` | ❌ never | Config bug — fail loudly at startup |
| `400 context length exceeded` | ❌ not as-is | Trim/summarise input, then retry |
| `JSON parse failure` | ✅ once | Feed the error back and ask for a correction |
| Tool threw | ✅ yes | Return the error **to the model** as an observation |

**Exponential backoff** means waiting longer after each failure: 0.5 s, then 1 s, then 2 s.
**Jitter** means adding a small random amount to each wait.

```js
async function withRetry(fn, { retries = 3, baseMs = 500 } = {}) {
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      return await fn();
    } catch (err) {
      const retryable = [429, 500, 502, 503].includes(err.status);
      if (!retryable || attempt === retries) throw err;

      const delay = baseMs * 2 ** attempt + Math.random() * 200;   // backoff + jitter
      console.warn(`retry ${attempt + 1}/${retries} in ${Math.round(delay)}ms — ${err.message}`);
      await new Promise((r) => setTimeout(r, delay));
    }
  }
}
```

> The **jitter** (`Math.random()`) matters. Without it, 100 clients that were all
> rate-limited retry at the same millisecond and rate-limit each other again. This real
> production failure is called the **thundering herd**.

---

## 4. Code — JavaScript

Set up a folder once. Every file below runs with no API key.

```bash
mkdir day00b && cd day00b
npm init -y
npm pkg set type=module          # replaces the "commonjs" that npm init wrote
npm install zod dotenv
echo "MOCK_API_KEY=test-key-123" > .env
```

`MOCK_API_KEY` is the "API key" of the pretend API you are about to build. It is not a secret,
but you treat it exactly like a real one.

> 🪟 **Windows PowerShell 5 trap.** There, `echo ... > .env` saves the file as UTF-16, not
> UTF-8. We tried it: Node's `dotenv` silently read the key as `undefined`, and `python-dotenv`
> crashed with `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 0`.
> PowerShell 7 and Git Bash write UTF-8 and work. If in doubt, create `.env` in your editor.

### 4.1 A pretend AI API on your own computer

Real providers need a key and an internet connection. This 50-line server behaves like one: it
checks the key, reads JSON, answers in JSON, and rate-limits you. Run it in one terminal and
leave it running.

```js
// mock-server.js — a pretend LLM API on your own machine. Run: node mock-server.js
import "dotenv/config";
import http from "node:http";

const KEY = process.env.MOCK_API_KEY;          // the "API key" clients must send
const LIMIT = 3;                               // at most 3 answers…
const WINDOW_MS = 5000;                        // …per 5 seconds
const recent = [];                             // times of recent successful answers

function send(res, status, body, headers = {}) {
  res.writeHead(status, { "Content-Type": "application/json", ...headers });
  res.end(JSON.stringify(body));               // object → JSON text → bytes on the wire
}

const server = http.createServer((req, res) => {
  if (req.url !== "/v1/chat") return send(res, 404, { error: "no such endpoint" });
  if (req.method !== "POST") return send(res, 405, { error: "use POST" });
  if (req.headers.authorization !== `Bearer ${KEY}`) {
    return send(res, 401, { error: "invalid API key" });
  }

  let raw = "";
  req.on("data", (piece) => (raw += piece));   // the body arrives in pieces
  req.on("end", () => {
    let body;
    try {
      body = JSON.parse(raw);                  // JSON text → object
    } catch {
      return send(res, 400, { error: "body is not valid JSON" });
    }
    if (!Array.isArray(body.messages) || body.messages.length === 0) {
      return send(res, 400, { error: "messages must be a non-empty array" });
    }

    const now = Date.now();
    while (recent.length && now - recent[0] > WINDOW_MS) recent.shift();
    if (recent.length >= LIMIT) {
      const wait = Math.ceil((recent[0] + WINDOW_MS - now) / 1000);
      return send(res, 429, { error: "rate limit reached" }, { "Retry-After": String(wait) });
    }
    recent.push(now);

    const question = body.messages.at(-1).content;
    send(res, 200, {
      model: "mock-1",
      choices: [{ message: { role: "assistant", content: `You said: ${question}` } }],
    });
  });
});

server.listen(8787, "127.0.0.1", () => console.log("mock API on http://127.0.0.1:8787"));
```

Even the server is just JSON in and JSON out. Notice the reply shape:
`choices[0].message.content`. It copies the shape of the real providers you meet on Day 02.

### 4.2 Calling it with `fetch`

Open a second terminal. This client sends one good request and three bad ones.

```js
// call-mock.js — talk to the mock API with fetch. Start mock-server.js first.
import "dotenv/config";

const URL = "http://127.0.0.1:8787/v1/chat";

async function chat(content, { key = process.env.MOCK_API_KEY, body } = {}) {
  const res = await fetch(URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",          // "my body is JSON"
      Authorization: `Bearer ${key}`,              // "here is my key"
    },
    body: body ?? JSON.stringify({ messages: [{ role: "user", content }] }),
  });
  const data = await res.json();                   // reading the body is async too
  return { status: res.status, ok: res.ok, retryAfter: res.headers.get("retry-after"), data };
}

// 1. A good request
const good = await chat("Hello!");
console.log(good.status, good.data.choices[0].message.content);

// 2. A wrong key
console.log((await chat("Hello!", { key: "wrong" })).status);

// 3. A body that is not JSON
console.log((await chat("", { body: "{ messages: oops" })).data);

// 4. Too many requests at once
const burst = await Promise.all([1, 2, 3, 4].map((i) => chat(`question ${i}`)));
const limited = burst.find((r) => r.status === 429);
console.log(burst.map((r) => r.status).sort(), "retry after:", limited?.retryAfter, "s");
```

Expected output (verified):

```
200 You said: Hello!
401
{ error: 'body is not valid JSON' }
[ 200, 200, 429, 429 ] retry after: 5 s
```

The burst is the interesting line. The first request used one of the three answers allowed in
five seconds. Two more fit, and the last two got **429** with a `Retry-After` header. The
number of seconds depends on timing; we saw values from 2 to 5. A real provider behaves the
same way, only with bigger limits.

You can also look at the raw HTTP with `curl -i`. The status line and headers come first:

```
HTTP/1.1 429 Too Many Requests
Content-Type: application/json
Retry-After: 5

{"error":"rate limit reached"}
```

### 4.3 Everything else, in one runnable file

The rest of today's ideas need a model to call. Instead of a real one, use this **fake model**.
It has the same `invoke` and `stream` methods as the real models you meet on Day 04, so the
code you write against it will not change later.

```js
// fake-model.js — a stand-in for a real chat model: same methods, no key, no network.
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export function fakeModel({ delayMs = 300, replies = {} } = {}) {
  const replyTo = (prompt) => replies[prompt] ?? `OK: ${prompt}`;

  return {
    // Like a real model's invoke(): wait, then resolve to a message object.
    async invoke(prompt) {
      await sleep(delayMs);
      return { content: replyTo(prompt) };
    },
    // Like a real model's stream(): yield the reply in small pieces ("tokens").
    async *stream(prompt) {
      const text = replyTo(prompt);
      for (let i = 0; i < text.length; i += 3) {
        await sleep(10);
        yield { content: text.slice(i, i + 3) };
      }
    },
  };
}
```

```js
// day00b-js-essentials.js
import "dotenv/config";
import * as z from "zod";
import { fakeModel } from "./fake-model.js";

// ── 1. Fail fast on config ───────────────────────────────────────────────
const REQUIRED = ["MOCK_API_KEY"];
const missing = REQUIRED.filter((k) => !process.env[k]);
if (missing.length) throw new Error(`Missing env vars: ${missing.join(", ")}`);

const model = fakeModel({
  delayMs: 300,
  replies: {
    "Count 1 to 10.": "1 2 3 4 5 6 7 8 9 10",
    "Write two sentences about rain.":
      "Rain is water that falls from clouds. It fills rivers and helps plants grow.",
  },
});

// ── 2. Sequential vs parallel ────────────────────────────────────────────
const CHAPTERS = ["photosynthesis", "the water cycle", "plate tectonics"];
const prompt = (t) => `Explain ${t} in one sentence for a 10-year-old.`;

console.time("sequential");
const seq = [];
for (const c of CHAPTERS) seq.push((await model.invoke(prompt(c))).content);
console.timeEnd("sequential");

console.time("parallel");
const par = (await Promise.all(CHAPTERS.map((c) => model.invoke(prompt(c)))))
  .map((m) => m.content);
console.timeEnd("parallel");

// ── 3. allSettled — survive partial failure ──────────────────────────────
const results = await Promise.allSettled([
  model.invoke("Say OK"),
  model.invoke("Say OK"),
  Promise.reject(new Error("simulated rate limit")),
]);
console.log({
  ok: results.filter((r) => r.status === "fulfilled").length,
  failed: results.filter((r) => r.status === "rejected").map((r) => r.reason.message),
});

// ── 4. Async iteration (streaming) ───────────────────────────────────────
const stream = await model.stream("Count 1 to 10.");
for await (const chunk of stream) process.stdout.write(chunk.content);
console.log();

// ── 5. Async generator: transform a stream as it flows ───────────────────
async function* words(stream) {
  let buffer = "";
  for await (const chunk of stream) {
    buffer += chunk.content;
    const parts = buffer.split(" ");
    buffer = parts.pop() ?? "";              // keep the incomplete tail
    for (const w of parts) yield w;
  }
  if (buffer) yield buffer;
}

let n = 0;
for await (const w of words(await model.stream("Write two sentences about rain."))) n++;
console.log("streamed words:", n);

// ── 6. Zod ───────────────────────────────────────────────────────────────
const Recipe = z.object({
  title: z.string().describe("Name of the dish"),
  minutes: z.number().int().describe("Total cooking time in minutes"),
  vegetarian: z.boolean(),
  ingredients: z.array(z.string()).describe("Ingredient list with quantities"),
  difficulty: z.enum(["easy", "medium", "hard"]).default("easy"),
});

const good = Recipe.safeParse({
  title: "Daal", minutes: 40, vegetarian: true, ingredients: ["1 cup lentils"],
});
const bad = Recipe.safeParse({ title: "Daal", minutes: "forty", vegetarian: "yes" });

console.log("valid:", good.success, "| invalid issues:",
  bad.success ? [] : bad.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`));

// ── 7. Retry with backoff ────────────────────────────────────────────────
async function withRetry(fn, { retries = 3, baseMs = 400 } = {}) {
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      return await fn();
    } catch (err) {
      const retryable = [429, 500, 502, 503].includes(err.status);
      if (!retryable || attempt === retries) throw err;
      const delay = baseMs * 2 ** attempt + Math.random() * 200;
      await new Promise((r) => setTimeout(r, delay));
    }
  }
}
console.log((await withRetry(() => model.invoke("Say READY"))).content);
```

Expected output (verified on Node 24.15, Zod 4.6.5; timings vary a little per run):

```
sequential: 930.969ms
parallel: 316.415ms
{ ok: 2, failed: [ 'simulated rate limit' ] }
1 2 3 4 5 6 7 8 9 10
streamed words: 14
valid: true | invalid issues: [
  'minutes: Invalid input: expected number, received string',
  'vegetarian: Invalid input: expected boolean, received string',
  'ingredients: Invalid input: expected array, received undefined'
]
OK: Say READY
```

Delete `.env` and run it again. Step 1 stops the program at once with
`Error: Missing env vars: MOCK_API_KEY`. That is "fail fast" working as designed.

> 💡 **Swapping in a real model later.** On Day 04 you replace the `fakeModel(...)` line with
> `new ChatGroq({ model: "openai/gpt-oss-120b", temperature: 0 })`. Everything below it
> keeps working, because the methods have the same names. (Real calls not executed here —
> they need a key.)

---

## 5. Code — Python

Set up a folder and a virtual environment once:

```bash
mkdir day00b && cd day00b
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install pydantic httpx python-dotenv
echo "MOCK_API_KEY=test-key-123" > .env
```

### 5.1 A pretend AI API on your own computer

The same server, written with Python's built-in `http.server`. Run only one of the two servers
at a time — both use port 8787, so either client can talk to either server. We checked all
four pairs.

```python
# mock_server.py — a pretend LLM API on your own machine. Run: python mock_server.py
import json, math, os, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from dotenv import load_dotenv

load_dotenv()
KEY = os.environ["MOCK_API_KEY"]           # the "API key" clients must send
LIMIT, WINDOW = 3, 5.0                     # at most 3 answers per 5 seconds
recent = []                                # times of recent successful answers


class Handler(BaseHTTPRequestHandler):
    def send(self, status, body, headers=None):
        data = json.dumps(body).encode()   # dict → JSON text → bytes on the wire
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self.send(405, {"error": "use POST"})

    def do_POST(self):
        if self.path != "/v1/chat":
            return self.send(404, {"error": "no such endpoint"})
        if self.headers.get("Authorization") != f"Bearer {KEY}":
            return self.send(401, {"error": "invalid API key"})

        raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        try:
            body = json.loads(raw)         # JSON text → dict
        except json.JSONDecodeError:
            return self.send(400, {"error": "body is not valid JSON"})
        if not isinstance(body.get("messages"), list) or not body["messages"]:
            return self.send(400, {"error": "messages must be a non-empty array"})

        now = time.time()
        while recent and now - recent[0] > WINDOW:
            recent.pop(0)
        if len(recent) >= LIMIT:
            wait = math.ceil(recent[0] + WINDOW - now)
            return self.send(429, {"error": "rate limit reached"}, {"Retry-After": str(wait)})
        recent.append(now)

        question = body["messages"][-1]["content"]
        self.send(200, {
            "model": "mock-1",
            "choices": [{"message": {"role": "assistant", "content": f"You said: {question}"}}],
        })

    def log_message(self, *args):          # keep the terminal quiet
        pass


print("mock API on http://127.0.0.1:8787")
ThreadingHTTPServer(("127.0.0.1", 8787), Handler).serve_forever()
```

### 5.2 Calling it with `httpx`

```python
# call_mock.py — talk to the mock API with httpx. Start mock_server.py first.
import asyncio, os
import httpx
from dotenv import load_dotenv

load_dotenv()
URL = "http://127.0.0.1:8787/v1/chat"


def chat(content, key=None, body=None):
    key = key or os.environ["MOCK_API_KEY"]
    headers = {"Authorization": f"Bearer {key}"}        # "here is my key"
    if body is None:                                     # json= sets Content-Type for you
        res = httpx.post(URL, headers=headers,
                         json={"messages": [{"role": "user", "content": content}]})
    else:                                                # send raw text as-is
        res = httpx.post(URL, headers={**headers, "Content-Type": "application/json"},
                         content=body)
    return {"status": res.status_code, "ok": res.is_success,
            "retry_after": res.headers.get("retry-after"), "data": res.json()}


# 1. A good request
good = chat("Hello!")
print(good["status"], good["data"]["choices"][0]["message"]["content"])

# 2. A wrong key
print(chat("Hello!", key="wrong")["status"])

# 3. A body that is not JSON
print(chat("", body="{ messages: oops")["data"])

# 4. Too many requests at once — the async client sends them together
async def burst():
    async with httpx.AsyncClient() as client:
        key = os.environ["MOCK_API_KEY"]
        tasks = [client.post(URL, headers={"Authorization": f"Bearer {key}"},
                             json={"messages": [{"role": "user", "content": f"question {i}"}]})
                 for i in range(1, 5)]
        return await asyncio.gather(*tasks)

replies = asyncio.run(burst())
limited = next((r for r in replies if r.status_code == 429), None)
print(sorted(r.status_code for r in replies), "retry after:",
      limited and limited.headers.get("retry-after"), "s")
```

Expected output (verified with httpx 0.28.1; the wait in seconds varies):

```
200 You said: Hello!
401
{'error': 'body is not valid JSON'}
[200, 200, 429, 429] retry after: 2 s
```

Python needs two clients for this file. `httpx.post` is the simple sync call. The burst needs
`httpx.AsyncClient`, because only async code can have four requests in flight at once.

### 5.3 Everything else, in one runnable file

The fake model in Python has both `invoke` and `ainvoke`, like LangChain's Python models.

```python
# fake_model.py — a stand-in for a real chat model: same methods, no key, no network.
import asyncio
import time
from types import SimpleNamespace


class FakeModel:
    def __init__(self, delay=0.3, replies=None):
        self.delay = delay
        self.replies = replies or {}

    def _reply_to(self, prompt):
        return self.replies.get(prompt, f"OK: {prompt}")

    def invoke(self, prompt):                    # like a real model's invoke()
        time.sleep(self.delay)
        return SimpleNamespace(content=self._reply_to(prompt))

    async def ainvoke(self, prompt):             # the async twin, like ainvoke()
        await asyncio.sleep(self.delay)
        return SimpleNamespace(content=self._reply_to(prompt))

    def stream(self, prompt):                    # yield the reply in small pieces
        text = self._reply_to(prompt)
        for i in range(0, len(text), 3):
            time.sleep(0.01)
            yield SimpleNamespace(content=text[i:i + 3])
```

```python
# day00b_python_essentials.py
import asyncio, os, random, time
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError
from typing import Literal, Optional
from fake_model import FakeModel

load_dotenv()

# ── 1. Fail fast on config ───────────────────────────────────────────────
REQUIRED = ["MOCK_API_KEY"]
missing = [k for k in REQUIRED if not os.getenv(k)]
if missing:
    raise RuntimeError(f"Missing env vars: {', '.join(missing)}")

model = FakeModel(delay=0.3, replies={
    "Count 1 to 10.": "1 2 3 4 5 6 7 8 9 10",
    "Write two sentences about rain.":
        "Rain is water that falls from clouds. It fills rivers and helps plants grow.",
})

CHAPTERS = ["photosynthesis", "the water cycle", "plate tectonics"]
prompt = lambda t: f"Explain {t} in one sentence for a 10-year-old."

# ── 2. Sequential vs parallel ────────────────────────────────────────────
t0 = time.time()
seq = [model.invoke(prompt(c)).content for c in CHAPTERS]
print(f"sequential: {time.time() - t0:.2f}s")

async def parallel():
    t0 = time.time()
    msgs = await asyncio.gather(*(model.ainvoke(prompt(c)) for c in CHAPTERS))
    print(f"parallel:   {time.time() - t0:.2f}s")
    return [m.content for m in msgs]

par = asyncio.run(parallel())

# ── 3. gather with return_exceptions — survive partial failure ───────────
async def tolerant():
    async def boom():
        raise RuntimeError("simulated rate limit")

    results = await asyncio.gather(
        model.ainvoke("Say OK"), model.ainvoke("Say OK"), boom(),
        return_exceptions=True,                       # ← the allSettled equivalent
    )
    ok = [r for r in results if not isinstance(r, Exception)]
    bad = [str(r) for r in results if isinstance(r, Exception)]
    print({"ok": len(ok), "failed": bad})

asyncio.run(tolerant())

# ── 4. Iteration (streaming) — sync version ──────────────────────────────
for chunk in model.stream("Count 1 to 10."):
    print(chunk.content, end="", flush=True)
print()

# ── 5. Generator: transform a stream as it flows ─────────────────────────
def words(stream):
    buffer = ""
    for chunk in stream:
        buffer += chunk.content
        parts = buffer.split(" ")
        buffer = parts.pop()                          # keep the incomplete tail
        yield from parts
    if buffer:
        yield buffer

n = sum(1 for _ in words(model.stream("Write two sentences about rain.")))
print("streamed words:", n)

# ── 6. Pydantic ──────────────────────────────────────────────────────────
class Recipe(BaseModel):
    title: str = Field(description="Name of the dish")
    minutes: int = Field(description="Total cooking time in minutes")
    vegetarian: bool
    ingredients: list[str] = Field(description="Ingredient list with quantities")
    difficulty: Literal["easy", "medium", "hard"] = "easy"

good = Recipe(title="Daal", minutes=40, vegetarian=True, ingredients=["1 cup lentils"])
print("valid:", good.model_dump())

try:
    Recipe(title="Daal", minutes="forty", vegetarian="definitely")
except ValidationError as e:
    print("invalid issues:", [f"{err['loc'][0]}: {err['msg']}" for err in e.errors()])

# ── 7. Retry with backoff ────────────────────────────────────────────────
def with_retry(fn, retries=3, base=0.4):
    for attempt in range(retries + 1):
        try:
            return fn()
        except Exception as err:
            status = getattr(err, "status_code", None) or getattr(err, "status", None)
            if status not in (429, 500, 502, 503) or attempt == retries:
                raise
            time.sleep(base * 2 ** attempt + random.random() * 0.2)

print(with_retry(lambda: model.invoke("Say READY")).content)
```

Expected output (verified on Python 3.14.4, Pydantic 2.13.5):

```
sequential: 0.91s
parallel:   0.32s
{'ok': 2, 'failed': ['simulated rate limit']}
1 2 3 4 5 6 7 8 9 10
streamed words: 14
valid: {'title': 'Daal', 'minutes': 40, 'vegetarian': True, 'ingredients': ['1 cup lentils'], 'difficulty': 'easy'}
invalid issues: ['minutes: Input should be a valid integer, unable to parse string as an integer', 'vegetarian: Input should be a valid boolean, unable to interpret input', 'ingredients: Field required']
OK: Say READY
```

Why `vegetarian="definitely"` here, when the JS file used `"yes"`? Because Pydantic would
**accept** `"yes"` as `True` (see the warning in §3.8). We needed a value it really rejects.

### 5.4 The JS ↔ Python translation for today

| Concept | JavaScript | Python |
|---|---|---|
| data → JSON text | `JSON.stringify(obj)` | `json.dumps(d)` |
| JSON text → data | `JSON.parse(text)` | `json.loads(text)` |
| pretty JSON | `JSON.stringify(obj, null, 2)` | `json.dumps(d, indent=2)` |
| a date in JSON | becomes an ISO string | `TypeError` — convert it yourself |
| huge integer | loses precision | exact |
| HTTP POST with JSON | `fetch(url, { method, headers, body: JSON.stringify(x) })` | `httpx.post(url, json=x)` |
| status | `res.status`, `res.ok` | `res.status_code`, `res.is_success` |
| raise on 4xx/5xx | do it yourself: `if (!res.ok) throw …` | `res.raise_for_status()` |
| read the body | `await res.json()` — only once | `res.json()` — as often as you like |
| a header | `res.headers.get("retry-after")` | `res.headers.get("retry-after")` |
| sync option | ❌ none — always async | ✅ `invoke` (sync) and `ainvoke` (async) |
| parallel | `Promise.all([...])` | `asyncio.gather(*tasks)` |
| tolerant parallel | `Promise.allSettled` | `gather(..., return_exceptions=True)` |
| un-awaited call | `Promise { <pending> }` | `<coroutine object …>` |
| timing | `console.time` / `timeEnd` | `time.time()` deltas |
| spread into call | `f(...args)` | `f(*args)` |
| yield many | `for (const p of parts) yield p` | `yield from parts` |
| schema errors | `result.error.issues` | `e.errors()` |
| schema → JSON Schema | `z.toJSONSchema(Schema)` | `Model.model_json_schema()` |
| `"yes"` for a boolean | rejected | accepted as `True` (unless `strict=True`) |
| method names | `withStructuredOutput`, `withRetry` | `with_structured_output`, `with_retry` |

---

## 6. Under the hood

### 6.1 How one thread waits for three calls at once

Both Node and Python's `asyncio` run your code on **one thread**. So how did three 300 ms calls
finish in 316 ms?

The answer is the **event loop**. When your code reaches `await` on a network call, it does not
sit and wait. It registers "wake me when the reply arrives" and hands control back to the
loop. The loop then runs whatever else is ready — here, the next two calls. When a reply
arrives, the loop resumes the code that was waiting for it.

```
   time ─────────────────────────────────────────────►
   sequential:  [call 1 ······ ][call 2 ······ ][call 3 ······ ]     ≈ 3 × 300 ms
   parallel:    [call 1 ······ ]
                [call 2 ······ ]                                     ≈ 1 × 300 ms
                [call 3 ······ ]
                 ▲ the thread is free while all three wait on the network
```

This only works while the code is **waiting**. If one task does heavy computing, nothing else
runs until it finishes. That is why async helps with network calls but not with number
crunching. It is also why a sync `time.sleep` inside an `async def` blocks everything. We
gathered three tasks that each wait 0.3 s: with `time.sleep` they took **0.92 s**, with
`await asyncio.sleep` they took **0.31 s**.

### 6.2 What actually travels over the wire

Your object never leaves your computer. Only **bytes** do. `JSON.stringify` makes text, and
the text is encoded as UTF-8 bytes. On the other side, the server turns bytes back into text
and text back into its own objects. Two programs in two languages can talk only because both
agree on JSON.

Two consequences follow:

- **Types do not survive the trip.** A date becomes a string. A JS number above about
  9 quadrillion loses digits. The receiver must rebuild real types — which is exactly what
  Zod and Pydantic do.
- **Non-English text is safe, but may look odd.** Python's `json.dumps({"city": "Zürich"})`
  printed `{"city": "Zürich"}`. That is the same text, escaped. Pass
  `ensure_ascii=False` to keep the `ü`.

### 6.3 Why schemas exist twice

You will meet the same shape in three forms:

```
   Zod / Pydantic class  ──►  JSON Schema  ──►  the model reads it (tools, structured output)
          ▲                                                 │
          └────── validates the model's JSON reply ◄────────┘
```

One definition gives you three things: a validator, a type for your editor, and a description
the model reads. That is why `.describe()` and `Field(description=...)` matter so much. The
model never sees your code. It sees the JSON Schema, including those descriptions.

The two libraries make slightly different JSON Schema. In Exercise 2 we saw that Zod listed a
field with a default (`priority`) as **required**, while Pydantic did not. Both are valid. It
just means the schema text the model reads depends on the library.

### 6.4 Why `fetch` doesn't throw on a 500

To `fetch`, a 500 is a perfectly good reply: the server answered. `fetch` only throws when no
reply arrives at all. With no server running, we got `TypeError: fetch failed` (cause
`ECONNREFUSED`), and `httpx` raised `ConnectError`. So
"`fetch` succeeded" means "a reply came back", not "the call worked". `httpx` makes the same
choice, but gives you `raise_for_status()` to turn bad statuses into exceptions. In both
languages, checking the status is your job.

---

## 7. Common mistakes

### ❌ 1. Forgetting `await`

```js
const res = model.invoke("hi");
console.log(res.content);   // undefined — res is a Promise
```
✅ `const res = await model.invoke("hi");`

In Python the same mistake with `ainvoke` gives
`AttributeError: 'coroutine' object has no attribute 'content'`.

### ❌ 2. `await` inside a non-async callback

```js
items.forEach(async (i) => { await model.invoke(i); });
console.log("done");   // prints IMMEDIATELY — forEach doesn't await
```
We ran it: `done` printed first, then both `forEach finished` lines. ✅ Use `for...of`
(sequential) or `Promise.all` + `map` (parallel):

```js
await Promise.all(items.map((i) => model.invoke(i)));
```

### ❌ 3. Not checking the status code

```js
const data = await (await fetch(URL, options)).json();
console.log(data.choices[0].message.content);
// with a wrong key: TypeError: Cannot read properties of undefined (reading '0')
```
The 401 reply had no `choices`, so the error points at the wrong line. ✅ Check first:

```js
if (!res.ok) throw new Error(`HTTP ${res.status}: ${JSON.stringify(await res.json())}`);
```

In Python, call `res.raise_for_status()`. Without it we got `KeyError: 'choices'`.

### ❌ 4. Sending an object instead of JSON text

```js
await fetch(URL, { method: "POST", headers, body: { messages } });   // 400
```
`fetch` turned the object into the text `[object Object]`, and the server answered
`400 {"error":"body is not valid JSON"}`. ✅ `body: JSON.stringify({ messages })`. In
Python, use `json=`. `data=` sends form-encoded text (`{"a": 1}` became `a=1`), which also got a 400.

### ❌ 5. Reading a setting before `.env` is loaded

The mistake is not "dotenv on the wrong line". ESM runs every `import` before the rest of the
file, so a late `import "dotenv/config"` still runs early. The real trap is **another module**
that reads `process.env` while it is being imported:

```js
// config.js
export const key = process.env.MOCK_API_KEY;   // read at import time

// app.js
import { key } from "./config.js";             // runs first — .env not loaded yet
import "dotenv/config";
console.log(key);                              // undefined
```
We ran it: `key` was `undefined`, although `process.env.MOCK_API_KEY` was set a moment later.
✅ Make `import "dotenv/config";` the **first** import of your entry file. In Python, call
`load_dotenv()` before you import or build anything that reads settings.

### ❌ 6. Python: forgetting the venv

```
pip install langchain            # goes to system python
python script.py                 # ModuleNotFoundError
```
✅ Activate first. If your prompt doesn't say `(.venv)`, you're in the wrong environment. The
error looks like `ModuleNotFoundError: No module named 'langchain_groq'`.

### ❌ 7. Using `Promise.all` for a big batch and losing everything to one failure

```js
const embeddings = await Promise.all(chunks.map(embed));   // 1 of 500 rate-limits → all lost
```
✅ `Promise.allSettled`, or batch with concurrency limits (LangChain's `.batch()` does this).

### ❌ 8. Copying TypeScript into a `.js` file

```js
const model: ChatGroq = new ChatGroq({ ... });   // SyntaxError
```
✅ Delete the annotations. `const model = new ChatGroq({ ... });`

### ❌ 9. Zod schema fields with no `.describe()`

```js
z.object({ x: z.string(), y: z.number() })   // model has no idea what x and y mean
```
✅ Describe every field. Those strings go into the prompt and directly affect accuracy.

### ❌ 10. Expecting Pydantic to be as strict as Zod

```python
class Flag(BaseModel):
    ok: bool
    n: int

Flag(ok="yes", n="40")      # accepted: ok=True n=40
```
✅ If "yes" should be an error, validate with `Flag.model_validate(data, strict=True)`.

---

## 8. Exercises

### Exercise 1 — Sequential vs parallel, measured ●○○○○

Write a script that "summarises" 5 topics twice — once sequentially, once in parallel — and
prints both timings and the speedup. Use the fake model from §4.3 / §5.3 with a 300 ms delay.
Then add a version that runs at most 2 calls at a time, and explain when you'd want that.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import { fakeModel } from "./fake-model.js";

const model = fakeModel({ delayMs: 300 });
const TOPICS = ["gravity", "photosynthesis", "inflation", "DNA", "tides"];
const p = (t) => `Explain ${t} in one sentence.`;

// sequential
let t0 = Date.now();
for (const t of TOPICS) await model.invoke(p(t));
const seq = Date.now() - t0;

// parallel (unbounded)
t0 = Date.now();
await Promise.all(TOPICS.map((t) => model.invoke(p(t))));
const par = Date.now() - t0;

// parallel, bounded to 2 concurrent
async function pool(items, limit, fn) {
  const results = [];
  const running = new Set();
  for (const item of items) {
    const task = Promise.resolve(fn(item)).finally(() => running.delete(task));
    running.add(task);
    results.push(task);
    if (running.size >= limit) await Promise.race(running);
  }
  return Promise.all(results);
}

t0 = Date.now();
await pool(TOPICS, 2, (t) => model.invoke(p(t)));
const bounded = Date.now() - t0;

console.log({ seq, par, bounded, speedup: (seq / par).toFixed(1) + "x" });
// { seq: 1578, par: 325, bounded: 931, speedup: '4.9x' }
```

**Python**
```python
import asyncio, time
from fake_model import FakeModel

model = FakeModel(delay=0.3)
TOPICS = ["gravity", "photosynthesis", "inflation", "DNA", "tides"]
p = lambda t: f"Explain {t} in one sentence."

# sequential
t0 = time.time()
for t in TOPICS:
    model.invoke(p(t))
seq = time.time() - t0

async def unbounded():
    t0 = time.time()
    await asyncio.gather(*(model.ainvoke(p(t)) for t in TOPICS))
    return time.time() - t0

async def bounded(limit=2):
    sem = asyncio.Semaphore(limit)

    async def one(t):
        async with sem:                       # ← the concurrency gate
            return await model.ainvoke(p(t))

    t0 = time.time()
    await asyncio.gather(*(one(t) for t in TOPICS))
    return time.time() - t0

par = asyncio.run(unbounded())
bnd = asyncio.run(bounded())

print({"seq": round(seq, 2), "par": round(par, 2), "bounded": round(bnd, 2),
       "speedup": f"{seq / par:.1f}x"})
# {'seq': 1.52, 'par': 0.31, 'bounded': 0.94, 'speedup': '4.9x'}
```

**Reading the numbers.** Five calls of 300 ms took about 1.5 s in a row and about 0.3 s
together. With a limit of 2, they ran in three waves (2 + 2 + 1), so about 0.9 s.

**When to bound concurrency:** free tiers allow only a limited number of requests per minute
(check your provider's limits page), so 500 parallel calls will hit 429 at once. Bounding also
helps fairness and memory, when each task holds a large document. LangChain's `.batch()`
accepts `maxConcurrency` / `max_concurrency` for exactly this — you just built it by hand.
</details>

---

### Exercise 2 — Schema round-trip ●●○○○

Define the *same* schema in Zod and Pydantic: a `MeetingNotes` object. It has `title`
(string) and `attendees` (array of strings). It has `decisions` (array of objects with
`decision` and `owner`). It also has `followUpDate` (optional string) and `priority` (enum
low/medium/high, default medium).

Then: (a) validate a good object, (b) validate a bad one and print readable errors,
(c) print the generated **JSON Schema** — the thing the LLM actually sees.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import * as z from "zod";

const MeetingNotes = z.object({
  title: z.string().describe("Short title of the meeting"),
  attendees: z.array(z.string()).describe("Full names of everyone present"),
  decisions: z.array(
    z.object({
      decision: z.string().describe("What was decided"),
      owner: z.string().describe("Person responsible"),
    })
  ).describe("Concrete decisions made"),
  followUpDate: z.string().optional().describe("ISO date of the follow-up, if any"),
  priority: z.enum(["low", "medium", "high"]).default("medium"),
});

const good = {
  title: "Q3 roadmap",
  attendees: ["Wasif", "Aisha"],
  decisions: [{ decision: "Ship RAG v2", owner: "Wasif" }],
  priority: "high",
};
console.log("✅", MeetingNotes.parse(good));

const bad = { title: 42, attendees: "Wasif", decisions: [{ decision: "x" }], priority: "urgent" };
const r = MeetingNotes.safeParse(bad);
if (!r.success) {
  for (const i of r.error.issues) console.log(`❌ ${i.path.join(".") || "(root)"}: ${i.message}`);
}

// What the LLM actually receives:
console.log(JSON.stringify(z.toJSONSchema(MeetingNotes), null, 2));
```

**Python**
```python
import json
from pydantic import BaseModel, Field, ValidationError
from typing import Literal, Optional

class Decision(BaseModel):
    decision: str = Field(description="What was decided")
    owner: str = Field(description="Person responsible")

class MeetingNotes(BaseModel):
    title: str = Field(description="Short title of the meeting")
    attendees: list[str] = Field(description="Full names of everyone present")
    decisions: list[Decision] = Field(description="Concrete decisions made")
    follow_up_date: Optional[str] = Field(None, description="ISO date of the follow-up, if any")
    priority: Literal["low", "medium", "high"] = "medium"

good = {
    "title": "Q3 roadmap",
    "attendees": ["Wasif", "Aisha"],
    "decisions": [{"decision": "Ship RAG v2", "owner": "Wasif"}],
    "priority": "high",
}
print("✅", MeetingNotes.model_validate(good).model_dump())

bad = {"title": 42, "attendees": "Wasif", "decisions": [{"decision": "x"}], "priority": "urgent"}
try:
    MeetingNotes.model_validate(bad)
except ValidationError as e:
    for err in e.errors():
        print(f"❌ {'.'.join(str(x) for x in err['loc'])}: {err['msg']}")

# What the LLM actually receives:
print(json.dumps(MeetingNotes.model_json_schema(), indent=2))
```

The errors, as printed (verified, Zod 4.6.5 and Pydantic 2.13.5):

```
JS                                                        Python
❌ title: Invalid input: expected string, received number  ❌ title: Input should be a valid string
❌ attendees: Invalid input: expected array, received string ❌ attendees: Input should be a valid list
❌ decisions.0.owner: Invalid input: expected string, …     ❌ decisions.0.owner: Field required
❌ priority: Invalid option: expected one of "low"|"medium"|"high"   ❌ priority: Input should be 'low', 'medium' or 'high'
```

Look closely at the JSON Schema output. Every `.describe()` / `Field(description=...)` shows up
as a `"description"` key — and that text is inserted into the model's prompt. **Vague
descriptions are vague prompts.** This is why Day 06 spends so long on schema design.

Two differences you can see in the output. Pydantic put `Decision` in a separate `$defs`
section and linked to it; Zod wrote it inline. And Zod listed `priority` as required, while
Pydantic left it out of `required` because it has a default.
</details>

---

### Exercise 3 — Break it six ways: HTTP and JSON ●●○○○

Start one of the mock servers from §4.1 / §5.1. For each break, **predict** the result, then
run it.

1. Call `fetch` (or the async `httpx` client) without `await`, and read the status.
2. Send the message object itself instead of JSON text (Python: use `data=` instead of `json=`).
3. Leave out the `Authorization` header.
4. Use a wrong key and read `choices[0]` without checking the status.
5. Write the JSON body by hand with single quotes.
6. Read the response body twice.

<details>
<summary>✅ Solution</summary>

| # | JavaScript (verified) | Python (verified) | Why |
|---|---|---|---|
| 1 | `res.status` is `undefined` | `AttributeError: 'coroutine' object has no attribute 'status_code'` | without `await` you hold a promise / coroutine, not a reply |
| 2 | `400 {"error":"body is not valid JSON"}` — the body sent was `[object Object]` | `400` — `data=` sent form-encoded text, not JSON | the network carries text; you must make JSON text yourself (or use `json=`) |
| 3 | `401` | `401` | no key, no entry — and retrying will never fix it |
| 4 | `TypeError: Cannot read properties of undefined (reading '0')` | `KeyError: 'choices'` | an error reply has a different shape; check the status first |
| 5 | `400 {"error":"body is not valid JSON"}` | `400 {'error': 'body is not valid JSON'}` | JSON needs double quotes |
| 6 | `TypeError: Body is unusable: Body has already been read` | works — returns `You said: Hi` again | `fetch` bodies are a one-time stream; `httpx` keeps the bytes |

With `res.raise_for_status()`, break 4 in Python becomes a clear error instead:
`HTTPStatusError: Client error '401 Unauthorized' for url 'http://127.0.0.1:8787/v1/chat'`.

**Repro — JavaScript**
```js
// break-http.js — six ways to break one HTTP call. Start the mock server first.
import "dotenv/config";

const URL = "http://127.0.0.1:8787/v1/chat";
const KEY = process.env.MOCK_API_KEY;
const auth = { "Content-Type": "application/json", Authorization: `Bearer ${KEY}` };
const good = JSON.stringify({ messages: [{ role: "user", content: "Hi" }] });

async function attempt(label, fn) {
  try {
    console.log(label, "→", await fn());
  } catch (err) {
    console.log(label, "→", `${err.name}: ${err.message}`);
  }
}

// 1. Forget await on fetch
await attempt("1 no await", async () => {
  const res = fetch(URL, { method: "POST", headers: auth, body: good });
  await res;                                   // (only so the request finishes cleanly)
  return res.status;
});

// 2. Send the object itself, not JSON text
await attempt("2 no stringify", async () => {
  const res = await fetch(URL, { method: "POST", headers: auth,
    body: { messages: [{ role: "user", content: "Hi" }] } });
  return `${res.status} ${JSON.stringify(await res.json())}`;
});

// 3. Forget the key
await attempt("3 no key", async () => {
  const res = await fetch(URL, { method: "POST",
    headers: { "Content-Type": "application/json" }, body: good });
  return res.status;
});

// 4. Assume it worked without checking the status
await attempt("4 no status check", async () => {
  const res = await fetch(URL, { method: "POST",
    headers: { ...auth, Authorization: "Bearer wrong" }, body: good });
  const data = await res.json();
  return data.choices[0].message.content;
});

// 5. Write JSON by hand, with single quotes
await attempt("5 hand-written JSON", async () => {
  const res = await fetch(URL, { method: "POST", headers: auth,
    body: "{'messages': [{'role': 'user', 'content': 'Hi'}]}" });
  return `${res.status} ${JSON.stringify(await res.json())}`;
});

// 6. Read the body twice
await attempt("6 read body twice", async () => {
  const res = await fetch(URL, { method: "POST", headers: auth, body: good });
  console.log("  first read:", (await res.json()).choices[0].message.content);
  return await res.json();
});
```

**Repro — Python**
```python
# break_http.py — six ways to break one HTTP call. Start the mock server first.
import asyncio, os
import httpx
from dotenv import load_dotenv

load_dotenv()
URL = "http://127.0.0.1:8787/v1/chat"
AUTH = {"Authorization": f"Bearer {os.environ['MOCK_API_KEY']}"}
GOOD = {"messages": [{"role": "user", "content": "Hi"}]}


def attempt(label, fn):
    try:
        print(label, "→", fn())
    except Exception as err:
        print(label, "→", f"{type(err).__name__}: {err}")


# 1. Forget await on the async client
async def no_await():
    async with httpx.AsyncClient() as client:
        res = client.post(URL, headers=AUTH, json=GOOD)
        try:
            return res.status_code
        finally:
            await res                          # (only so the request finishes cleanly)
attempt("1 no await", lambda: asyncio.run(no_await()))

# 2. Send the dict as form data instead of JSON
attempt("2 data= not json=", lambda: (lambda r: f"{r.status_code} {r.json()}")(
    httpx.post(URL, headers=AUTH, data=GOOD)))

# 3. Forget the key
attempt("3 no key", lambda: httpx.post(URL, json=GOOD).status_code)

# 4. Assume it worked without checking the status
attempt("4 no status check", lambda: httpx.post(
    URL, headers={"Authorization": "Bearer wrong"}, json=GOOD).json()["choices"][0])

# 4b. The fix: raise_for_status() turns 4xx/5xx into an exception you can catch
attempt("4b raise_for_status", lambda: httpx.post(
    URL, headers={"Authorization": "Bearer wrong"}, json=GOOD).raise_for_status())

# 5. Write JSON by hand, with single quotes
attempt("5 hand-written JSON", lambda: (lambda r: f"{r.status_code} {r.json()}")(
    httpx.post(URL, headers=AUTH, content="{'messages': [{'role': 'user', 'content': 'Hi'}]}")))

# 6. Read the body twice
def twice():
    res = httpx.post(URL, headers=AUTH, json=GOOD)
    print("  first read:", res.json()["choices"][0]["message"]["content"])
    return res.json()["choices"][0]["message"]["content"]
attempt("6 read body twice", twice)
```

**The lesson.** Four of the six breaks are about the envelope, not the AI. A real provider
answers them the same way: 400 for a bad body, 401 for a bad key. When an AI call fails,
read the **status code first**. It tells you whether to fix your request, fix your config, or
wait and retry.
</details>

---

### Exercise 4 — Build a streaming transformer ●●●○○

Write an async generator that consumes a model stream and yields **complete sentences** instead
of tokens (buffer until you see `.`, `!` or `?`). Then use it to print each sentence on its own
numbered line as it completes. Handle the final partial sentence. Use the fake model, and make
its reply end **without** a trailing space, so you can test the last sentence.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import { fakeModel } from "./fake-model.js";

const model = fakeModel({
  replies: {
    "Write a 4-sentence explanation of how rainbows form.":
      "Sunlight enters a raindrop and bends. Inside, it reflects off the back of the drop! " +
      "Each colour bends by a different amount. So white light leaves as a band of colours.",
  },
});

async function* sentences(stream) {
  let buffer = "";
  for await (const chunk of stream) {
    buffer += chunk.content;

    // Emit every complete sentence currently in the buffer.
    let match;
    while ((match = buffer.match(/^(.*?[.!?])(\s+)/s))) {
      yield match[1].trim();
      buffer = buffer.slice(match[0].length);
    }
  }
  if (buffer.trim()) yield buffer.trim();          // the tail
}

const stream = await model.stream(
  "Write a 4-sentence explanation of how rainbows form."
);

let n = 1;
for await (const s of sentences(stream)) {
  console.log(`${n++}. ${s}`);
}
```

**Python**
```python
import re
from fake_model import FakeModel

model = FakeModel(replies={
    "Write a 4-sentence explanation of how rainbows form.":
        "Sunlight enters a raindrop and bends. Inside, it reflects off the back of the drop! "
        "Each colour bends by a different amount. So white light leaves as a band of colours.",
})

def sentences(stream):
    buffer = ""
    pattern = re.compile(r"^(.*?[.!?])(\s+)", re.S)

    for chunk in stream:
        buffer += chunk.content
        while (m := pattern.match(buffer)):          # emit every complete sentence
            yield m.group(1).strip()
            buffer = buffer[m.end():]

    if buffer.strip():                                # the tail
        yield buffer.strip()

stream = model.stream("Write a 4-sentence explanation of how rainbows form.")

for n, s in enumerate(sentences(stream), start=1):
    print(f"{n}. {s}")
```

Expected output, identical in both languages (verified):

```
1. Sunlight enters a raindrop and bends.
2. Inside, it reflects off the back of the drop!
3. Each colour bends by a different amount.
4. So white light leaves as a band of colours.
```

**Why this is a real pattern, not a toy:** streaming *sentences* rather than tokens is exactly
what text-to-speech needs, because a speech engine needs whole clauses. It also helps when you
translate as you go, and when you render markdown (you can't parse half a code block). You've now written
a stream transformer — Day 23 builds on this directly.

**The subtle bug to notice:** you must handle the tail *outside* the loop. The last sentence
has no space after it, so the regex never matches it. We deleted the tail line and ran it
again: only sentences 1–3 printed. Sentence 4 vanished without any error.
</details>

---

### Exercise 5 — Production-grade retry wrapper ●●●●○

Build `resilient(fn, options)`. It retries only retryable errors, with exponential backoff and
jitter. It respects a `Retry-After` header if present. It gives up after a total time budget
(not just an attempt count), and it logs each attempt. Test it against a fake function that
fails twice then succeeds.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
const RETRYABLE = new Set([408, 409, 429, 500, 502, 503, 504]);

async function resilient(fn, {
  maxAttempts = 5,
  baseMs = 300,
  maxMs = 10_000,
  totalBudgetMs = 30_000,
  onRetry = () => {},
} = {}) {
  const deadline = Date.now() + totalBudgetMs;

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await fn(attempt);
    } catch (err) {
      const status = err.status ?? err.statusCode;
      const isLast = attempt === maxAttempts;

      if (!RETRYABLE.has(status) || isLast) throw err;

      // Honour Retry-After (seconds or HTTP date) if the server sent one.
      const header = err.headers?.["retry-after"];
      const serverDelay = header
        ? (Number.isNaN(Number(header))
            ? new Date(header).getTime() - Date.now()
            : Number(header) * 1000)
        : 0;

      const backoff = Math.min(baseMs * 2 ** (attempt - 1), maxMs);
      const jitter = Math.random() * backoff * 0.3;          // ±30% to break herds
      const delay = Math.max(serverDelay, backoff + jitter);

      if (Date.now() + delay > deadline) {
        throw new Error(`Retry budget exhausted after ${attempt} attempts: ${err.message}`);
      }

      onRetry({ attempt, status, delay: Math.round(delay), message: err.message });
      await new Promise((r) => setTimeout(r, delay));
    }
  }
}

// ── test ──
let calls = 0;
const flaky = async () => {
  calls++;
  if (calls <= 2) {
    const e = new Error("rate limited");
    e.status = 429;
    throw e;
  }
  return `succeeded on call ${calls}`;
};

console.log(await resilient(flaky, {
  onRetry: (i) => console.log(`  ↻ attempt ${i.attempt} failed (${i.status}), waiting ${i.delay}ms`),
}));
```

**Python**
```python
import random, time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

RETRYABLE = {408, 409, 429, 500, 502, 503, 504}

def resilient(fn, max_attempts=5, base=0.3, max_delay=10.0,
              total_budget=30.0, on_retry=lambda **kw: None):
    deadline = time.time() + total_budget

    for attempt in range(1, max_attempts + 1):
        try:
            return fn(attempt)
        except Exception as err:
            status = getattr(err, "status_code", None) or getattr(err, "status", None)
            is_last = attempt == max_attempts

            if status not in RETRYABLE or is_last:
                raise

            # Honour Retry-After (seconds or HTTP date) if the server sent one.
            header = (getattr(err, "headers", None) or {}).get("retry-after")
            server_delay = 0.0
            if header:
                try:
                    server_delay = float(header)
                except ValueError:
                    when = parsedate_to_datetime(header)
                    server_delay = max(0.0, (when - datetime.now(timezone.utc)).total_seconds())

            backoff = min(base * 2 ** (attempt - 1), max_delay)
            jitter = random.random() * backoff * 0.3          # ±30% to break herds
            delay = max(server_delay, backoff + jitter)

            if time.time() + delay > deadline:
                raise RuntimeError(
                    f"Retry budget exhausted after {attempt} attempts: {err}"
                ) from err

            on_retry(attempt=attempt, status=status, delay=round(delay, 2), message=str(err))
            time.sleep(delay)


# ── test ──
calls = 0

def flaky(attempt):
    global calls
    calls += 1
    if calls <= 2:
        err = RuntimeError("rate limited")
        err.status = 429
        raise err
    return f"succeeded on call {calls}"

print(resilient(flaky, on_retry=lambda **kw:
    print(f"  ↻ attempt {kw['attempt']} failed ({kw['status']}), waiting {kw['delay']}s")))
```

One run of each (verified; the waits differ every run because of the jitter):

```
JS                                         Python
  ↻ attempt 1 failed (429), waiting 375ms    ↻ attempt 1 failed (429), waiting 0.36s
  ↻ attempt 2 failed (429), waiting 725ms    ↻ attempt 2 failed (429), waiting 0.63s
succeeded on call 3                        succeeded on call 3
```

**The four things that make this production-grade rather than a toy:**
1. **Only retryable statuses** — retrying a 401 just burns time; it will never succeed.
2. **Jitter** — prevents the thundering herd where every client retries in lockstep.
3. **`Retry-After`** — the server told you exactly how long to wait. Ignoring it gets you
   rate-limited harder.
4. **A total time budget** — 5 attempts with exponential backoff can take 30+ seconds, which is
   far past the point where your user's HTTP request has timed out anyway.

LangChain's `.withRetry()` / `.with_retry()` gives you 1 and 2. Day 24 covers the rest.

**Try it for real:** point `resilient` at the mock server's burst from §4.2. Turn a 429 reply
into an error with `status` and `headers` set, and watch it wait for `Retry-After`.
</details>

---

## 9. Interview questions

### Basic

**Q1. What is JSON, and why does every AI API use it?**

JSON is a text format for data: objects, arrays, strings, numbers, booleans and null. The
network can only carry text, and JSON is a format that every language can read and write. So
your program turns its data into JSON text (`JSON.stringify` / `json.dumps`) before sending.
The server parses it back into its own objects. It is strict: double quotes only, no trailing
commas, and no dates.

---

**Q2. A model call returns 401, 429 or 503. What does each mean, and which do you retry?**

401 means the key is missing or wrong — a config bug, so never retry; fail loudly. 429 means
you hit the rate limit — retry after waiting, ideally for the `Retry-After` time. 503 means
the provider is overloaded — retry a few times with backoff, then fall back to another model.
The rule of thumb: 4xx is your fault (fix it), 5xx and 429 are temporary (retry with care).

---

**Q3. ESM vs CommonJS — what's the practical difference for an AI project?**

CommonJS uses `require`/`module.exports` and is Node's historical default; ESM uses
`import`/`export`, is the standard, and supports **top-level await**. LangChain JS is ESM-first,
and nearly every example awaits at the top level of a module, so you set `"type": "module"` in
`package.json`. With `"type": "commonjs"` — which `npm init -y` writes — you get
`Cannot use import statement outside a module`.

---

**Q4. What is Zod and why does LangChain use it?**

Zod is a runtime schema-validation library for JS/TS. TypeScript types are erased at compile
time. But tool arguments and structured output must be checked at *runtime*, and converted to
**JSON Schema** to send to the model. Zod gives you one
definition that serves as validator, type source, and model-facing schema. Pydantic plays the
same role in Python.

---

**Q5. What does `.describe()` on a Zod field actually do?**

It sets the `description` in the generated JSON Schema, and that description is sent to the
model as part of the tool or schema definition. It is prompt text, not a code comment. A clear
description helps the model fill that field correctly.

---

**Q6. Difference between `invoke` and `ainvoke` in LangChain Python?**

`invoke` is synchronous and blocks; `ainvoke` is the `async` version you `await`. The `a`
prefix marks async variants across the API (`astream`, `abatch`, `ainvoke`). Use sync in
scripts and notebooks, async in web servers, so one request doesn't block the event loop.
LangChain **JS has no sync variants** — everything returns a Promise.

---

### Intermediate

**Q7. `Promise.all` vs `Promise.allSettled` — when does the choice matter in AI code?**

`Promise.all` rejects as soon as any promise rejects, and you lose the results of the ones that
succeeded. `allSettled` always resolves with a status per item.

For LLM work this matters constantly. Embedding 500 chunks where one hits a 429 shouldn't
discard 499 successful embeddings. Use `allSettled` (or `asyncio.gather(..., return_exceptions=True)`)
for batch work, and add concurrency limits so you don't cause the rate limit in the first place.

---

**Q8. Why do LLM streaming APIs use async iterators?**

Streaming is a sequence of values arriving over time, which is exactly what an async iterator
models. Each `next()` returns a promise that resolves when the next chunk arrives.
`for await...of` consumes them; `async function*` produces them. This lets you chain
transformations (token → sentence → translated sentence) without waiting for the whole
response, so the first words appear quickly.

---

**Q9. Why does jitter matter in retry logic?**

Without jitter, all clients that fail at the same moment retry at the same moment, recreating
the overload — the thundering herd. Randomising each delay spreads retries out. Also honour
`Retry-After` when the server provides it, and cap total retry time rather than just attempts,
since exponential backoff can easily exceed the caller's timeout.

---

**Q10. Does `fetch` throw when the server returns a 500? What about `httpx`?**

No to both. A 500 is still a reply, so `fetch` resolves normally with `res.ok === false`. It
throws only when no reply arrives, such as `TypeError: fetch failed` when the connection is
refused. `httpx` also returns the response; you call `raise_for_status()` to turn 4xx/5xx into
an `HTTPStatusError`. If you skip the check, your code reads an error body as if it were an
answer, and fails later with a confusing `TypeError` or `KeyError`.

---

### Advanced

**Q11. Your JS service and your Python service read the same JSON and disagree on a user ID.
What's going on?**

Probably a large integer. JSON numbers have no size limit, but JavaScript stores every number
as a 64-bit float, which is exact only up to about 9 quadrillion (2^53). We parsed
`12345678901234567890`: JavaScript gave `12345678901234567000`, while Python kept it exactly.
The fix is to send IDs as strings. The same kind of bug appears with dates, which JSON can't
hold: JavaScript turns them into ISO strings, and Python refuses to serialise them.

---

**Q12. Design a client for a rate-limited LLM API that must process 10,000 documents.**

Five parts. (1) **Bound concurrency** with a pool or semaphore, sized below the provider's
limit, so you rarely trigger 429 at all. (2) **Retry only retryable errors** — 429, 5xx and
timeouts — with exponential backoff and jitter. (3) **Honour `Retry-After`** when present.
(4) **Use a settled-style gather**, so one failure doesn't discard the batch; collect failures
for a second pass. (5) **Check every status and validate every reply** with a schema before
storing it. Add a total time budget per document and log attempts, so you can see whether you
are limited by rate, errors or speed.

---

## 10. Recap

- ✅ JSON is the shared text format: `stringify`/`dumps` to send, `parse`/`loads` to read
- ✅ JSON is strict (double quotes, no trailing commas) and has no dates; JS loses precision on huge integers
- ✅ An HTTP request is method + URL + headers + body; a response is status + headers + body
- ✅ 4xx means fix your request or key; 429 and 5xx mean wait and retry
- ✅ `fetch` and `httpx` don't throw on bad statuses — check `res.ok` / call `raise_for_status()`
- ✅ `"type": "module"` in `package.json` — ESM and top-level `await` (`npm init -y` writes `"commonjs"`)
- ✅ Missing `await` is the #1 bug; `Promise { <pending> }` is the tell
- ✅ `Promise.all` / `asyncio.gather` for parallel; `allSettled` / `return_exceptions=True` for tolerant batch
- ✅ `for await...of` consumes streams; `async function*` creates them
- ✅ Zod ↔ Pydantic are the same idea; `.describe()` / `Field(description=)` is **prompt text**
- ✅ Pydantic accepts `"yes"` and `"40"` by default; Zod doesn't
- ✅ JS LangChain is async-only; Python has `invoke`/`ainvoke` pairs
- ✅ Retry only retryable errors, with backoff **and jitter**, honouring `Retry-After`

```
   one model call =  object ─JSON─► HTTP request (+key) ─► status? ─JSON─► object ─schema─► app
```

### Tomorrow

**[Day 0C — Just-enough maths](day-00c-just-enough-maths.md)**: you can now send a request and
trust the reply. But from Day 01 on, the course talks about probabilities, "temperature",
softmax and cosine similarity. Day 0C gives you just enough maths for those words — vectors,
dot products, probability and softmax — each with a picture and ten lines of code.

### Quick self-check

1. Your code logs `Promise { <pending> }` and then crashes on `.content`. What happened?
2. A call returns status 401. Should your retry wrapper try again? Why or why not?
3. You embed 500 chunks with `Promise.all` and one 429s. What do you lose, and what should you
   have used?

<details>
<summary>Answers</summary>

1. You forgot `await`. The variable holds a promise of the reply, not the reply, so
   `.content` is `undefined`.
2. No. 401 means the key is missing or wrong, and retrying sends the same wrong key. Fail
   loudly so someone fixes the configuration. Retry 429 and 5xx instead.
3. All 499 successful embeddings — `Promise.all` rejects on the first failure and discards the
   rest. Use `Promise.allSettled` (or `asyncio.gather(..., return_exceptions=True)`), plus a
   concurrency limit so you don't trip the rate limit at all.
</details>

---

<div align="center">

**[← Day 0A — Your toolkit](day-00a-your-toolkit.md)** · **[Week 0 index](README.md)** · **[Day 0C — Just-enough maths →](day-00c-just-enough-maths.md)**

</div>
