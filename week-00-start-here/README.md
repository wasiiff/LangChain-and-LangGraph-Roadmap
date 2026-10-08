# Week 0 — Start Here

> **Goal:** get every reader to the same starting line. In three short days you set up your
> computer, learn the programming ideas every AI example uses, and learn the small amount of
> maths behind tokens and embeddings. Already a developer? Read "Which track are you?" below —
> you may be able to skip most of this week.

← [Back to the main index](../README.md) · [SETUP.md](../SETUP.md)

---

## Which track are you?

This course teaches AI engineering from zero to production. People arrive with very different
backgrounds, so there are three ways in. Pick the first row that describes you.

| Track | You are… | Start at | You can skip |
|---|---|---|---|
| 🟢 **Beginner** | New to programming, or new to JavaScript/Python | [Day 0A](day-00a-your-toolkit.md) | nothing — do all of Week 0 |
| 🔵 **Developer, new to AI** | You write code every week but have never built with an LLM | [SETUP.md](../SETUP.md) → [Day 01](../week-01-foundations/day-01-llms-tokens-and-inference.md) | Day 0A. Skim [Day 0B](day-00b-programming-for-ai.md) for async + Zod/Pydantic and [Day 0C](day-00c-just-enough-maths.md) for softmax and cosine |
| 🟣 **Already used LangChain** | You have built a chain or a small RAG app | the self-check below | the days your score says you know |

> 💡 Not sure? Start one track lower. A day that feels easy takes an hour; a missing basic
> costs you days of confusion later.

### Self-check for the 🟣 track

Answer out loud, then open the answers. Count one point for each answer that names the same
mechanism.

1. Why does a chatbot "forget" earlier messages, and what actually fixes it?
2. What does temperature change inside the model?
3. What is the difference between `invoke`, `stream` and `batch`?
4. How does `withStructuredOutput` / `with_structured_output` get typed data out of a model?
5. What does the pipe in `prompt | model | parser` produce?
6. Why split documents into chunks before embedding them?
7. What does cosine similarity measure, in one sentence?
8. Name two reasons a RAG answer can be wrong even when the right document exists.
9. In a tool-calling loop, who runs the tool — the model or your code?
10. Why does LangGraph exist when LCEL already composes steps?

<details>
<summary>✅ Answers and where to start</summary>

1. Models are stateless; you re-send the history each call (Day 01, Day 14).
2. It rescales the probability distribution before a token is sampled (Day 01, Day 0C).
3. One input → one output; one input → a stream of chunks; many inputs → many outputs (Day 04).
4. The schema is sent as a tool/JSON schema, the model fills it, and the result is validated (Day 06).
5. A `RunnableSequence` — itself a Runnable with `invoke`/`stream`/`batch` (Day 07).
6. Embeddings and context windows work best on small, focused pieces of text (Day 09).
7. How closely two vectors point the same way, ignoring their length (Day 10).
8. Retrieval missed it (bad chunking, bad query) or the model ignored or misread it (Day 12–13).
9. Your code. The model only asks for a call; you run it and send back the result (Day 15).
10. LCEL is a one-way pipeline; agents need loops, state and pauses (Day 16–17).

| Score | Start at |
|---|---|
| 0–4 | [Day 01](../week-01-foundations/day-01-llms-tokens-and-inference.md) — the foundations will pay off |
| 5–7 | [Day 07](../week-01-foundations/day-07-lcel-and-runnables.md), then read the recap of Days 1–6 |
| 8–10 | [Day 12](../week-02-data-embeddings-and-rag/day-12-naive-rag.md) if RAG answers were your misses, otherwise [Day 15](../week-03-tools-agents-and-langgraph/day-15-tools.md) |

</details>

---

## The week at a glance

| Day | Topic | Time | Difficulty | You'll build |
|---|---|---|---|---|
| [0A](day-00a-your-toolkit.md) | Terminal, git, Node, Python, `.env`, reading errors | 2h | ●○○○○ | An environment checker · StudyBuddy v0 project folder |
| [0B](day-00b-programming-for-ai.md) | JSON, HTTP, async, Zod ↔ Pydantic, errors and retries | 2.5h | ●●○○○ | A typed HTTP call with validation and a retry wrapper |
| [0C](day-00c-just-enough-maths.md) | Vectors, dot product, cosine, probability, softmax, percentiles | 2h | ●●○○○ | A tiny maths toolkit that ranks documents by similarity |

**Total: ~6.5 hours.** Go slowly. Every later day assumes these ideas.

---

## What you'll be able to do by the end of Week 0

- [ ] Move around your computer in a terminal and run a JavaScript and a Python file
- [ ] Install packages in the right place (npm project, Python virtual environment)
- [ ] Save your work with git and keep secrets out of it with `.env` and `.gitignore`
- [ ] Read an error message and find the line that caused it
- [ ] Explain JSON, an HTTP request and a status code like `401` or `429`
- [ ] Write `async`/`await` code and validate data with Zod or Pydantic
- [ ] Compute a dot product, a cosine similarity and a softmax by hand and in code
- [ ] Explain why p95 latency matters more than the average

---

## The through-line

Each day removes a problem the previous day created:

```
Day 0A  You can run code and keep secrets safe   → but AI code is full of async, JSON and HTTP
Day 0B  You can call an API and validate replies → but models speak in vectors and probabilities
Day 0C  You can compute with vectors and probabilities → so Day 01 can open the model itself
```

---

## Before you start

1. You need a computer (Windows, macOS or Linux) and an internet connection. Everything in this
   course can be done for **$0**.
2. Day 0A installs the tools. You do **not** need API keys this week — [SETUP.md](../SETUP.md)
   gets them right before Day 01.

---

## Common Week 0 blockers

Every error text below was produced by running the code in Week 0.

| Symptom | Day | Fix |
|---|---|---|
| `nod: The term 'nod' is not recognized…` / `command not found` | 0A | A typo, or the program isn't installed / not on PATH — check spelling, then open a **new** terminal after installing |
| `SyntaxError: Cannot use import statement outside a module` right after `npm init -y` | 0A | npm 11 writes `"type": "commonjs"` — run `npm pkg set type=module` |
| `ModuleNotFoundError: No module named 'dotenv'` although you installed it | 0A | Activate `.venv` in this terminal (prompt shows `(.venv)`), or run `.venv\Scripts\python.exe` |
| `Activate.ps1 cannot be loaded because running scripts is disabled` | 0A | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, or call `.venv\Scripts\python.exe` directly |
| Key shows as "not set" (JS) / `UnicodeDecodeError … byte 0xff` (Python) | 0A | Windows PowerShell 5.1 `>` saved `.env` as UTF-16 — recreate it in VS Code; run from the project folder |
| `Promise { <pending> }` or `[object Promise]` in output | 0B | Missing `await` |
| `TypeError: Cannot read properties of undefined (reading '0')` after `fetch` | 0B | The request returned 4xx/5xx — check `res.ok` / `raise_for_status()` before reading the body |
| `softmax` returns `[NaN, NaN, NaN]` (JS) / `OverflowError: math range error` (Python) | 0C | Subtract the largest score before `exp`; treat temperature 0 as "pick the biggest" |
| Median or percentile is wrong in JS | 0C | Plain `.sort()` sorts numbers as text — use `.sort((a, b) => a - b)` |
| `UnicodeEncodeError: 'charmap' codec can't encode character` | 0C | Windows console encoding — set `PYTHONIOENCODING=utf-8` |

---|---|---|
| `'node' is not recognized` / `command not found: python` | 0A | Reinstall with "Add to PATH" ticked, then open a **new** terminal |
| `Cannot use import statement outside a module` | 0B | Add `"type": "module"` to `package.json` |
| `Promise { <pending> }` in a log | 0B | Missing `await` |
| `ModuleNotFoundError` after installing | 0A | Activate the venv — the prompt must show `(.venv)` |
| A `.env` value is `undefined` / `None` | 0A | Load it first (`dotenv` / `python-dotenv`) and run from the folder that holds `.env` |

---

## Interview topics covered this week

Week 0 is groundwork, but these come up in junior interviews:

1. **Keeping secrets out of code** (Day 0A) — env vars, `.gitignore`, key rotation
2. **async/await and concurrency** (Day 0B) — sequential vs parallel calls
3. **HTTP status codes and retries** (Day 0B) — which errors to retry, which to fix
4. **Cosine similarity and softmax** (Day 0C) — the maths behind search and sampling

---

## StudyBuddy — the running project

```
Day 0A  v0     an empty, correctly configured JS + Python project (.gitignore, .env.example)
Day 0C  —      first retrieval idea: rank documents by cosine similarity, by hand
```

From Day 04 it becomes a real chatbot.

---

→ Start with **[Day 0A](day-00a-your-toolkit.md)** — or jump to your track above.
