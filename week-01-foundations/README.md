# Week 1 — Foundations & LangChain Core

> **Goal:** understand what an LLM actually is, then build composable, streaming, typed
> pipelines with LangChain. By Friday you'll have shipped a real multi-mode study assistant.

← [Back to the main index](../README.md) · [SETUP.md](../SETUP.md)

---

## The week at a glance

| Day | Topic | Time | Difficulty | You'll build |
|---|---|---|---|---|
| [01](day-01-llms-tokens-and-inference.md) | LLMs, tokens, context windows, inference | 2h | ●○○○○ | A token counter, history trimmer & context budgeter |
| [02](day-02-prompt-engineering-and-raw-apis.md) | Prompt engineering + raw APIs | 2.5h | ●●○○○ | **A working ReAct agent, by hand, no framework** |
| [03](day-03-choosing-a-model-and-why-langchain.md) | Choosing a model · why LangChain | 2h | ●●○○○ | A cost estimator, a tiny model eval, a framework decision doc |
| [04](day-04-langchain-models.md) | LangChain models: invoke/stream/batch | 2.5h | ●●○○○ | StudyBuddy v0.5 — provider hot-swapping chatbot |
| [05](day-05-prompts-and-templates.md) | Prompts, templates, placeholders, few-shot | 2h | ●●○○○ | A reusable, testable prompt library |
| [06](day-06-output-parsers-structured-output.md) | Output parsers & structured output | 2.5h | ●●●○○ | An invoice extractor with business-rule validation |
| [07](day-07-lcel-and-runnables.md) | **LCEL & Runnables** + Week 1 project | 3h | ●●●○○ | 🏆 **StudyBuddy v1** |

**Total: ~16 hours.** One day per day is the intended pace — the exercises are where the
learning happens.

---

## What you'll be able to do by Sunday

- [ ] Explain how an LLM generates text, token by token, and why that causes hallucinations
- [ ] Choose temperature, top-p and max_tokens deliberately per task instead of copying defaults
- [ ] Predict and prevent context-window and cost problems before shipping
- [ ] Write zero-shot, few-shot, CoT and ReAct prompts — and know which one a problem needs
- [ ] Implement tool calling from the raw wire format up
- [ ] Choose a model on purpose — size, price, speed, licence — and test it on your own cases
- [ ] Call Groq, Gemini, Ollama, OpenAI or Anthropic through one interface
- [ ] Build reusable prompt templates with history placeholders and few-shot examples
- [ ] Get validated, typed objects out of a model with Zod or Pydantic
- [ ] Compose streaming pipelines with LCEL and debug them when the seams don't line up
- [ ] Answer the most common LangChain interview questions with real understanding

---

## The through-line

Each day removes a problem the previous day created:

```
Day 01  You learn models are stateless        → so you re-send history by hand
Day 02  You hand-parse output with regex      → and it breaks constantly
Day 03  You choose a model and compare SDKs   → and switching providers is a lot of code
Day 04  LangChain gives you one model API     → but prompts are still strings
Day 05  Templates fix the strings             → but output is still text
Day 06  Structured output fixes the output    → but composing steps is manual
Day 07  LCEL composes everything              → but it can't loop  →  Week 3
```

That last gap — LCEL is acyclic, agents need cycles — is the door into LangGraph.

---

## Before you start

1. **[SETUP.md](../SETUP.md)** — free API keys (Groq + Gemini), Node 20+ and/or Python 3.10+, a
   passing `check.js` / `check.py`. 15 minutes, $0. New to programming, async or Zod/Pydantic?
   Do **[Week 0](../week-00-start-here/README.md)** first.
2. **Pick a lane.** Read your language's code block carefully, skim the other. Both are always
   provided, same example.
3. **Do the exercises.** Solutions are in `<details>` dropdowns — try first.

---

## Common Week 1 blockers

| Symptom | Day | Fix |
|---|---|---|
| `Cannot use import statement outside a module` | 0B | npm 11 writes `"type": "commonjs"` — run `npm pkg set type=module` |
| `Promise { <pending> }` in a log | 0B | Missing `await` |
| `ModuleNotFoundError` after installing | 0A | Activate the venv — prompt must show `(.venv)` |
| `Missing value for input variable "label": "BUG"` | 05 | Unescaped braces in a template — use `{{ }}` |
| `messages with role 'tool' must be a response to...` | 02 | Push the assistant `tool_calls` message back into history |
| Chain streams, then suddenly doesn't | 07 | A non-streaming lambda after the model is buffering |
| Keys vanish mid-chain | 07 | You used `RunnableParallel` where you wanted `.assign()` |
| `429 Rate limit` while doing exercises | — | Switch to `openai/gpt-oss-20b`, or use Ollama offline |
| Cost estimate is 1,000× off | 03 | Prices are quoted per **1M** tokens, not per 1K |

---

## Interview topics covered this week

Ranked by how often they come up:

1. **LCEL & Runnables** (Day 07) — the single most-asked LangChain topic
2. **Structured output & how it works under the hood** (Day 06)
3. **Tool calling mechanics** (Day 02) — "what happens when an agent calls a tool?"
4. **Why LangChain instead of the SDK, and how you'd pick a model** (Day 03) — judgement questions, not trivia
5. **Tokens, context windows, cost** (Day 01) — the system-design warm-up
6. **Prompting techniques and when each applies** (Day 02)
7. **Chat models vs LLMs, message types, memory** (Day 04)

Each day ends with basic/intermediate/advanced questions and full answers.

---

## StudyBuddy — the running project

```
Day 03  —      first eval set: 5 labelled student messages + a pick-a-model rule
Day 04  v0.5   CLI chatbot · provider hot-swap · token/cost tracking
Day 05  v1.0   prompt module · 3 modes · /preview debugging
Day 06  —      quiz engine with structured output & validation
Day 07  v1.0   🏆 parallel analysis · routing · streaming · retries · fallbacks
```

Next week it learns to read your PDFs.

---

→ Start with **[Day 01](day-01-llms-tokens-and-inference.md)**
