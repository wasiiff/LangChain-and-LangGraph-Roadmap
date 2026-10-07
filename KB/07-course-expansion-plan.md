# 07 — Plan: from LangChain book to full AI Engineering course

**Status: DRAFT — waiting for your review.** Nothing in the course has been changed yet.
Mark each row in the **Your call** column (`OK` / `Change: …` / `Skip`), or just reply with the
IDs, for example: *"All OK except D5 skip, D9 change to optional."*

How this was made:

- Read the whole KB (`KB/01`–`06`), the master README and the week READMEs.
- **Measured** the reading level of every day file with a script (code, tables and HTML removed
  first). The numbers in Part A come from that script, not from guessing.
- Searched current AI-engineering curricula and job posts (sources at the bottom) and compared
  their topic lists with what the 28 days already teach (`grep` across all day files).

---

## Part A — Is the English easy to understand?

**Short answer: mostly yes, with three hard days and one repeated habit to fix.**

Average across all 28 days: **Flesch reading ease 60** (60–70 = "plain English") and
**grade level 8.7**. These scores use an approximate syllable counter, so treat them as a
ranking of easy vs hard days, not as exact values.

| Day | Prose words | Avg sentence length | Flesch (higher = easier) | Grade | Sentences > 30 words |
|---|---|---|---|---|---|
| 02 | 4,826 | **19.5** | **51** | **11.0** | **12 %** |
| 13 | 4,334 | 15.5 | **48** | **10.4** | 7 % |
| 14 | 4,448 | 15.4 | **48** | **10.4** | 7 % |
| 10 | 4,357 | 14.7 | 53 | 9.5 | 6 % |
| 11 | 4,200 | 16.1 | 54 | 9.8 | 10 % |
| 12 | 4,064 | 14.9 | 54 | 9.4 | 8 % |
| 23, 25, 26, 27 | ~3,700–4,200 | 16.8–17.3 | 58–67 | 8.2–9.3 | 10–13 % |
| 17, 19, 20, 21 (easiest) | ~4,300–5,900 | 13.6–14.5 | **67–70** | **7.1–7.4** | 4–7 % |

What makes the hard days hard (real examples found by the script):

- **Very long sentences joined with semicolons.** Day 14 has a 77-word sentence starting
  *"Implementation essentials: key everything by session/user ID…"* and Day 13 has a 78-word one
  starting *"A cheap classifier decides: no retrieval…"*. These read fine to experts but lose
  beginners.
- **Jargon lists before definitions.** Day 13's opening line lists eight technique names
  (*MMR, multi-query, HyDE, reranking, parent-document…*) before any of them is explained.
- **Recap bullets packed with symbols** (`O(n²)`, `≫`, `·`) instead of words.

| ID | Proposed English fix | Your call |
|---|---|---|
| A1 | **Plain-English pass** on the 6 hardest days first (02, 13, 14, 10, 11, 12), then the rest. Target: Flesch ≥ 60 on every day, no prose sentence over ~30 words. Technical accuracy and code stay exactly the same. | |
| A2 | Add a **"Words you'll meet today"** box (5–8 terms, one simple line each) near the top of every day. Reuses the existing glossary entries. | |
| A3 | Add a one-line **"In plain words:"** summary under each `### 3.x` heading in §3 (the hardest section). | |
| A4 | Rewrite every **"Today you learn"** line so it names the problem first and saves the technique names for later. | |
| A5 | Keep British spelling (current house rule). | |
| A6 | Re-run the readability script after each day is edited and record the before/after numbers in this file. | |

---

## Part B — Problems with the beginner path (found while reading)

| ID | Problem | Evidence | Proposed fix | Your call |
|---|---|---|---|---|
| B1 | **Days 1–2 use things that Day 3 teaches.** | Day 1 uses `await` 24 times and Day 2 uses it 23 times; both mention Zod/Pydantic. Day 3 is where async, Zod and Pydantic are explained. | Move Day 3's "JS & Python essentials" (§3.1–3.8) into a new **Week 0, Day 0B** (see C1). Day 3 keeps "why LangChain exists" and gains "choosing a model" (D3). | |
| B2 | The README says the course needs only "a `for` loop and calling an API". A true beginner cannot yet do either. | README "Prerequisites" line. | Add a **Start Here** page with three entry tracks (below). | |
| B3 | README says **"~150 interview questions"**, but there are **378**. | README "Who this is for" table vs `tools/verify.py` output. | Fix the number. | |
| B4 | README's StudyBuddy map (v1–v7, 7 steps) doesn't match the KB's map (v1.0–v6.0, 12 steps). | README vs `KB/02-content-map.md`. | Make README match the detailed map, then extend it for new weeks. | |
| B5 | Evaluation is taught only on **Day 25**. Current practice (Huyen ch. 3–4, job posts) treats "measure first" as a habit from the start. | Topic grep: evals appear late. | Keep Day 25 as the deep dive, but add a small **"Measure it"** box with a 3-case test from Day 6 onward. | |

### Proposed "Start Here" — three ways in

| Track | Who | Start at | Can skip |
|---|---|---|---|
| 🟢 **Beginner** | New to programming or to JS/Python | Week 0 (Day 0A) | nothing |
| 🔵 **Developer, new to AI** | Writes code daily, never built with LLMs | SETUP → Day 1 | Week 0 (skim 0B) |
| 🟣 **Already used LangChain** | Has built a chain or a RAG app | 10-question self-check, then Day 7 or Day 15 | Days 3–6, maybe 8–9 |

---

## Part C — Where the existing 28 days fit in the new course

**Recommendation:** keep Days 1–28 **with their current numbers and files** (they are verified
and linked from 50 files), add **Week 0** before them and **Weeks 5–6** after them. This gives a
**43-day / 7-part AI Engineering course** without breaking a single existing link.

```
Week 0  Start Here (new)          programming + maths you need          Days 0A–0C
Week 1  How LLMs work + LC core   (existing, Day 3 re-focused)          Days 1–7
Week 2  Data, embeddings & RAG    (existing)                            Days 8–14
Week 3  Tools, agents & LangGraph (existing)                            Days 15–21
Week 4  Production                (existing)                            Days 22–28
Week 5  The model layer (new)     open models, fine-tuning, cost, ...   Days 29–35
Week 6  Advanced & career (new)   agent patterns, product, capstone     Days 36–40
```

| ID | Existing content | Stays where it is? | Change | Your call |
|---|---|---|---|---|
| C1 | Day 3 §3.1–3.8 (ESM, async, Zod, TypeScript, Python equivalents, env vars, errors) | ❌ Moves | Becomes **Day 0B**. Day 3 links to it. | |
| C2 | Day 1 — tokens, context, sampling | ✅ | Add a short §3 on **how a model is made** (pre-training → fine-tuning → RLHF) and **attention by intuition**. Today attention appears only as one KV-cache paragraph. | |
| C3 | Day 2 — prompting, raw APIs | ✅ | English pass (hardest day). Add a short note on **reasoning models** (they "think" before answering, cost more tokens). | |
| C4 | Day 8 — sequential / parallel / router chains | ✅ | Name them with the industry terms from Anthropic's *Building Effective Agents*: **prompt chaining, parallelisation, routing**. | |
| C5 | Day 19 — `Send` fan-out | ✅ | Name it **orchestrator-workers**. Add an exercise for the missing pattern, **evaluator-optimizer** (a generate → critique → fix loop). | |
| C6 | Day 14 memory + Day 22 multi-agent | ✅ | Introduce the term **context engineering** (now standard; Day 22 mentions it once). Full treatment in D8. | |
| C7 | Day 24 — reliability, PII, injection | ✅ | Stays as reliability. The deeper security material goes to D7. | |
| C8 | Day 28 — capstones & interviews | ✅ | Becomes the **mid-course** checkpoint ("you can now ship an LLM app"). Final capstone moves to Day 40. | |
| C9 | All resources (glossary, cheatsheets, generated files) | ✅ | Extend for new days; regenerate with `tools/gen_resources.py`. | |
| C10 | Course title "LangChain & LangGraph Masterbook — 28 Days" | ❌ | New title, e.g. **"AI Engineering — From Zero to Production, in JavaScript and Python"**. LangChain/LangGraph stay the main tools. | |

---

## Part D — New topics to add (the gaps)

Each row was checked against the current days with `grep`. "Covered now" shows what exists
today. **Can verify here?** says whether I can run it on this Windows machine with no GPU and no
paid keys — rule 1 of `CLAUDE.md` says every claim must be run, so anything marked ⚠️ would be
labelled "not executed" in the text.

| ID | New day | What it teaches (simple words) | Covered now | Why it belongs | Can verify here? | Your call |
|---|---|---|---|---|---|---|
| D1 | **0A — Your toolkit** | Terminal, git, Node, Python, VS Code, `.env`, how to read an error | Partly in SETUP.md | Beginners need it before Day 1 | ✅ | |
| D2 | **0B — Programming for AI** | JSON, HTTP requests, async/await, Zod ↔ Pydantic, in both languages | Day 3 (moved, see C1) | Fixes B1 | ✅ | |
| D3 | **0C — Just-enough maths** | Vectors, dot product, probability, softmax — with tiny code | Days 1 & 10 explain bits | Makes Day 1 (sampling) and Day 10 (cosine) easier | ✅ | |
| D4 | **Day 3 extra — Choosing a model** | Open vs closed models, sizes, context length, price per million tokens, benchmarks and their limits | Not covered | Huyen ch. 4 "Model selection"; asked in interviews | ✅ (no live prices quoted; explain how to read them) | |
| D5 | **29 — Open & local models** | Hugging Face, Ollama, **quantisation** (why a 4-bit model fits your laptop), memory arithmetic | Ollama used; quantisation **0 mentions** | Job posts ask for open-weight model skills | ✅ with Ollama / a tiny model | |
| D6 | **30 — Inference & serving** | KV cache, batching, time-to-first-token vs throughput, **vLLM**, speculative decoding | KV cache in Day 1; vLLM **0 mentions** | Huyen ch. 9; job posts list vLLM | ⚠️ vLLM needs Linux + GPU — concepts verified with a small CPU model, vLLM marked "not executed" | |
| D7 | **31 — Fine-tuning** | When to fine-tune (and when not), **LoRA / QLoRA**, train a tiny LoRA on CPU | Only "prompt → RAG → fine-tune" decision in Day 2; LoRA only as a word | Huyen ch. 7; rising demand in 2025–26 job posts | ✅ tiny model on CPU (slow but real) · ⚠️ **Python only** (see E3) | |
| D8 | **32 — Dataset engineering** | Collecting, cleaning, de-duplicating data; **synthetic data**; building eval sets | Synthetic data **0 mentions** | Huyen ch. 8; feeds D7 and Day 25 | ✅ | |
| D9 | **33 — Multimodal** | Images in, PDFs with pictures (multimodal RAG), image generation, speech-to-text / text-to-speech, voice agents basics | Content blocks shown in Day 4 only | Standard in 2026 curricula | ⚠️ needs a vision-capable free model (Gemini) or local (Ollama `llava`) — will check | |
| D10 | **34 — Cost & latency** | Prompt caching, semantic caching, model routing / cascades, batch APIs, token budgets | Prompt caching mentioned in Days 1, 5; semantic cache in Day 8 | Production concern every curriculum lists | ✅ with scripted models (keyless) | |
| D11 | **35 — AI security** | OWASP Top 10 for LLM apps, red-teaming your own app, guardrail tools, supply chain (model & package trust) | Injection + PII in Days 2, 24; red-teaming **0 mentions** | "Secure AI apps" in job posts | ✅ keyless attack suite | |
| D12 | **36 — Context engineering & agent patterns** | All five Anthropic patterns side by side, "workflow vs agent" decision, long-running and "deep" agents, context limits | Patterns spread over Days 8, 19, 22; never named together | Core 2026 skill; joins C4–C6 | ✅ | |
| D13 | **37 — Advanced retrieval** | GraphRAG / knowledge graphs, text-to-SQL agents, agentic search | GraphRAG **0 mentions** | Common interview / project topic | ✅ (in-memory graph, SQLite) | |
| D14 | **38 — Emerging agents** | Browser / computer-use agents, A2A agent-to-agent protocol, agent skills | **0 mentions** | Fast-moving; clearly labelled "emerging, check your version" | ⚠️ partly — will verify what installs and runs | |
| D15 | **39 — AI product engineering** | UX for AI, collecting user feedback, A/B tests, responsible AI, regulation basics (e.g. EU AI Act) | Not covered | Huyen ch. 10 "Architecture and user feedback" | ✅ (mostly concepts + small code) | |
| D16 | **40 — Final capstone & career** | One end-to-end project using Weeks 1–6, portfolio, interview update | Day 28 (mid-course) | Ends the course on a real build | ✅ keyless starter | |

Every new day follows the existing template exactly: 10 sections, JS **and** Python, 5 exercises
with bilingual solutions, interview questions, recap, and a StudyBuddy step.

**Size:** the 28 current days average **~2,150 lines** each (60,084 ÷ 28). At
that size, 15 new day files (D4 extends Day 3 instead of adding a file) come to roughly
**+32,000 lines** — about 54 % more course.

---

## Part E — Decisions I need from you

| ID | Question | My recommendation | Your call |
|---|---|---|---|
| E1 | **Scope:** all 15 new days, or a smaller first wave? | First wave: **Week 0 (D1–D3) + D4 + English pass on the 6 hard days**. That fixes the beginner path. Then Weeks 5–6. | |
| E2 | **Numbering:** append (Week 0 + Days 29–40, no renames) or renumber everything into modules? | **Append.** Renumbering touches every link in 50 files. | |
| E3 | **Language rule:** fine-tuning, vLLM and dataset work are Python-only in practice. Allow Python-only days there? | Yes for D6–D8, with a clear "why only Python" note and a JS section showing how to **call** the result (e.g. via Ollama). | |
| E4 | **Order of work:** English pass first, or new content first? | Beginner path + English pass first — it improves what readers already use. | |
| E5 | **Title / repo name** change (C10)? | Change the title in README only; leave the repo folder name alone. | |
| E6 | Should I commit to git as I go? | Only when you ask. (Weeks 4, `KB/`, `tools/` are still uncommitted from before.) | |

---

## Sources used for the gap analysis

- Chip Huyen, *AI Engineering* — table of contents:
  <https://github.com/chiphuyen/aie-book/blob/main/ToC.md>
- Anthropic, *Building Effective Agents* (workflow patterns), as summarised in the Spring AI docs:
  <https://docs.spring.io/spring-ai/reference/api/effective-agents.html>
- Context engineering overview (2026): <https://sourcegraph.com/blog/context-engineering>
- AI engineer roadmap, 2026: <https://www.youngju.dev/blog/culture/2026-07-02-how-to-become-ai-engineer-2026-llm-rag-agents-evals-career-roadmap-deep-dive.en>
- Skills in 2026 job posts (fine-tuning, vLLM, guardrails): <https://jobrise.io/en/blog/llm-engineer-jobs-2026-anthropic-openai/>
- General roadmaps: <https://opencv.org/ai-engineer-roadmap/>, <https://wscubetech.com/blog/ai-engineer-roadmap>
