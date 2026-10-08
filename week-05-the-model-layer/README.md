# Week 5 — The Model Layer

> **Goal:** go below the API. Run a model on your own machine, serve it, teach it a new habit,
> feed it clean data, give it eyes and ears, make it cheap and fast, and attack it before someone
> else does. Every example runs on a laptop CPU with no API key.

← [Back to the main index](../README.md) · [Week 4](../week-04-production-projects-and-interviews/README.md) · [Week 6](../week-06-advanced-agents-product-and-career/README.md)

---

## The week at a glance

| Day | Topic | Time | Difficulty | You'll build |
|---|---|---|---|---|
| [29](day-29-open-and-local-models.md) | Open & local models | 3h | ●●●○○ | A tiny model running in Python and Node · file-size arithmetic checked against real files · StudyBuddy v6.1 offline |
| [30](day-30-inference-and-serving.md) | Inference & serving | 3h | ●●●●○ | TTFT, KV-cache and batching measurements · your own OpenAI-compatible server · StudyBuddy v6.2 |
| [31](day-31-fine-tuning.md) | Fine-tuning | 3.5h | ●●●●○ | A real LoRA adapter trained on a CPU (habit 0/16 → 13/16) · StudyBuddy v6.3 quiz cards |
| [32](day-32-dataset-engineering.md) | Dataset engineering | 3h | ●●●○○ | A dedupe → PII → split → version pipeline with a data gate · StudyBuddy v6.4 question bank |
| [33](day-33-multimodal.md) | Multimodal: images, documents and voice | 3h | ●●●○○ | Image content blocks, local captioning and speech-to-text · StudyBuddy v6.5 |
| [34](day-34-cost-and-latency.md) | Cost & latency | 3h | ●●●●○ | Exact and semantic caches, a cheap-first cascade, a budget guard · StudyBuddy v6.6 dashboard |
| [35](day-35-ai-security.md) | AI security | 3h | ●●●●○ | A red-team harness (0/11 → 10/11 blocked) · StudyBuddy v6.7 security gate in CI |

**Total: ~21.5 hours.**

> 🐍 **A note on languages.** Training (Day 31) and parts of serving (Day 30) are Python-only in
> the real world. Those days say so, and the JavaScript sections do the practical JS part instead:
> preparing the data, and calling the model you built through a server.

---

## What you'll be able to do by the end of the week

- [ ] Read a model card and licence, and work out how much memory a model needs
- [ ] Explain quantisation and why a 4-bit model fits on a laptop — with real file sizes
- [ ] Measure time-to-first-token, decode speed and batching, and explain the KV cache
- [ ] Serve your own model behind an OpenAI-compatible API and call it from both languages
- [ ] Decide when to fine-tune (habits) and when not to (facts), and train a LoRA adapter
- [ ] Build clean, de-duplicated, leak-free datasets, including synthetic ones
- [ ] Send images and audio to models, and build RAG over documents with pictures
- [ ] Cut cost and latency with caching, routing and budgets — and know each trick's trap
- [ ] Run a red-team suite against your own app and explain the OWASP Top 10 for LLM apps

---

## The through-line

```
Day 29  You can run a model yourself          → but calling it in-process doesn't scale
Day 30  You serve it like a real API          → but it doesn't behave the way you need
Day 31  You fine-tune a habit into it         → but training data is messy and leaks
Day 32  You build clean, versioned data       → but the world isn't only text
Day 33  It reads images and hears voice       → and the bill and the wait keep growing
Day 34  You make it cheap and fast            → but every new feature is a new way in
Day 35  You attack it before anyone else does → Week 6: design, product and the final capstone
```

---

## Version traps this week

| Trap | What we measured | Day |
|---|---|---|
| transformers 5.x default dtype | `from_pretrained` without `dtype` loads **bf16** — on this CPU it was much slower than fp32 | 29, 30 |
| Transformers.js dtype typos | an unknown dtype such as `"int4"` **silently** loads the fp32 file | 29 |
| `ChatOpenAI` retries | JS `maxRetries` defaults to **6** (93 s to report a dead local server); Python uses 2 | 30 |
| JS `ChatGroq` cache key | contains no model name — a shared cache returned the small model's answer to the big one | 34 |
| `torch.load` | `weights_only=True` is the default — untrusted pickles now raise `UnpicklingError` | 35 |

---

## Extra installs

| For | Python | JavaScript |
|---|---|---|
| Local models (29–31) | `torch` (CPU wheel) `transformers` `peft` `accelerate` `langchain-huggingface` | `@huggingface/transformers` |
| Your own server (30) | `fastapi` `uvicorn` `langchain-openai` | `@langchain/openai` |
| Security (35) | `nh3` `safetensors` | `sanitize-html` |

> 💾 Models are small (SmolLM2-135M is about 270 MB) but they add up. Point `HF_HOME` at a disk
> with space before you start.

---

## Common Week 5 blockers

| Symptom | Day | Fix |
|---|---|---|
| Local model returns `''`, or echoes the prompt | 29 | Use the chat template: pass messages / `apply_chat_template`, or wrap in `ChatHuggingFace` |
| `ChatHuggingFace` reply starts with `<\|im_start\|>system…` | 29 | Add `return_full_text: False` to `pipeline_kwargs` |
| Answer cut at 20 tokens (Python) or rambles to ~256 (JS) | 29 | Always set `max_new_tokens` |
| `ChatOpenAI` against a local server gives 404 Not Found | 30 | Base URL must end in `/v1` and must not include `/chat/completions` |
| JS client takes ~90 s to report a dead local server | 30 | Set `maxRetries: 0` and add `withFallbacks` |
| JS `.stream()` returns nothing, but `.invoke()` works | 30 | The server ignores `"stream": true`; it must send `text/event-stream` |
| Batched `generate()` answers short prompts with `'\n'` | 30 | Set `tok.padding_side = "left"` |
| Low training loss, but the habit never appears when served | 31 | Train with the same chat template the server applies |
| Fine-tuned model never stops talking | 31 | SmolLM2's pad token is its stop token — mask padding by position, not by `pad_token_id` |
| Loss jumps from ~3 to 12–20 within a few steps | 31 | Learning rate too high |
| Hashes differ between JS and Python for the same JSONL | 32 | Python: `json.dumps(r, ensure_ascii=False, separators=(",", ":"))` and `newline="\n"` |
| Boilerplate filter randomly lets rows through (JS) | 32 | Remove the `g` flag from regexes used with `.test()` |
| JS: the wrong model's cached answer comes back | 34 | Give each model its own `new InMemoryCache()` instead of `cache: true` |
| 429s when using `batch` | 34 | Set `maxConcurrency` / `max_concurrency` below the provider limit |
| Approval prompt shows actions your policy would refuse | 35 | HITL middleware runs before `wrapToolCall` — add a `when` predicate |
| `torch.load` raises `UnpicklingError … Unsupported global` | 35 | Use safetensors; never pass `weights_only=False` for untrusted files |

---

## Interview topics covered this week

1. **Prompt vs RAG vs fine-tune** (Day 31) — and "fine-tuning teaches habits, not facts"
2. **Memory and serving arithmetic** (Days 29–30) — weights, KV cache, batching, TTFT
3. **Prompt injection and the OWASP Top 10 for LLM apps** (Day 35)
4. **Cost reduction** (Day 34) — caching, routing, budgets, and each one's failure mode
5. **Data quality and leakage** (Day 32)
6. **Multimodal pipelines** (Day 33) — what images and audio cost, voice-agent latency

---

## StudyBuddy — the running project

```
Day 29  v6.1   runs offline with a local model, falls back when the server is down
Day 30  v6.2   talks to its own OpenAI-compatible model server
Day 31  v6.3   a LoRA adapter turns answers into {answer, quiz} cards
Day 32  v6.4   a versioned, leak-free question bank behind a data gate
Day 33  v6.5   reads a photo of notes or a spoken question
Day 34  v6.6   cached, routed, budgeted — with its own cost dashboard
Day 35  v6.7   a red-team suite runs in CI and fails on new breaches
```

---

→ Start with **[Day 29](day-29-open-and-local-models.md)**
