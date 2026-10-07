# Capstone Projects

Twelve projects in three tiers, each mapped to the days it exercises. Full architectures, build
orders and acceptance-test sketches (JS and Python) are in
[Day 28 — Exercises 1–3](../week-04-production-projects-and-interviews/day-28-capstones-and-interviews.md#8-exercises);
this page is the catalogue for choosing one.

> **Pick one. Finish it.** A finished Tier 2 project with an evaluation table beats three
> unfinished Tier 3 ideas. Start from the keyless
> [capstone starter kit](../week-04-production-projects-and-interviews/day-28-capstones-and-interviews.md#41-the-capstone-starter-kit)
> — it already has a tool, an agent graph, an approval gate, a checkpointer and eval checks,
> in both languages.

---

## How to choose

```
   Do you want to show you can build ANSWERS well?        → Tier 1  (Days 1–14)
   Do you want to show you can build SYSTEMS THAT ACT?    → Tier 2  (Days 15–23)
   Do you want to show you can RUN them for real?         → Tier 3  (Days 20–27)

   Aiming at an AI engineer role? Tier 2 with Tier 3 habits (evals, tracing, compose.yaml)
   is the strongest single project for most portfolios.
```

---

## Tier 1 — Foundations

| # | Project | One-line pitch | Days | Effort |
|---|---|---|---|---|
| 1 | **Syllabus Q&A with citations** | Answers from a course's PDFs, cites pages, refuses when it doesn't know | 9–12 | 1–2 weeks |
| 2 | **Lecture-to-flashcards pipeline** | Transcript in, validated, deduplicated flashcards out | 5–8 | ~1 week |
| 3 | **Retrieval benchmark** | Chunking × embeddings × reranking measured on 50 labelled questions | 9–13, 25 | ~1 week |
| 4 | **A tutor that remembers you** | Preferences and weak topics persist across sessions; history stays bounded | 14, 18 | ~1 week |

**Acceptance (all Tier 1):** one-command run · ≥30 real evaluation questions · a results table ·
one documented failure and its fix.

**Interview story it gives you:** "Retrieval recall was 64%; header-aware chunking took it to 81%;
reranking added 6 points of answer correctness at +0.4 s p95." *(Your numbers, measured.)*

---

## Tier 2 — Agentic

| # | Project | One-line pitch | Days | Effort |
|---|---|---|---|---|
| 5 | **SQL study-analytics agent** | Answers questions over a database; writes need approval | 15–21 | 1–2 weeks |
| 6 | **Research assistant** | Plans sub-questions, researches in parallel, verifies claims, writes a cited report | 19, 22 | 2 weeks |
| 7 | **Essay grader** | Per-criterion rubric scoring, teacher approval before posting | 17–21, 25 | 2 weeks |
| 8 | **Supervisor tutor, streamed** | Researcher, quizmaster and analyst as tools, streamed to a web UI | 22–23 | 2 weeks |

**Acceptance (all Tier 2):** a diagram generated from code · trajectory evals for ≥3 behaviours ·
an approval gate on every write · a restart test (pause in one process, resume in another).

**Interview story it gives you:** "The grader is a workflow, not an agent — the steps are known.
It agrees with teachers on 84% of criterion scores; teacher edits are logged and fed back into the
eval set." *(Your numbers, measured.)*

---

## Tier 3 — Production

| # | Project | One-line pitch | Days | Effort |
|---|---|---|---|---|
| 9 | **StudyBuddy, deployed** | Auth, Postgres, streaming, start/poll/resume, long runs, CI eval gate | 20–27 | 3–4 weeks |
| 10 | **A shared MCP server** | Notes/progress tools over Streamable HTTP with auth, used by LangChain and the AI SDK | 26–27 | 2 weeks |
| 11 | **An evaluation platform** | Traces → review queue → datasets → calibrated judges → CI gate → dashboard | 25 | 2–3 weeks |
| 12 | **A reliability lab** | Inject 429s, outages, timeouts, loops, injections and crashes; measure recovery | 24 | 2 weeks |

**Acceptance (all Tier 3):** `compose.yaml` brings it up locally · a written capacity estimate ·
reliability and cost controls with evidence · an eval gate in CI.

**Interview story it gives you:** "At 100k students the bottleneck is the provider quota at about
25 calls a second, not compute — so I sized a shared rate limiter at 80% of quota, made worker
concurrency the valve, and added a fallback provider. The fault-injection suite shows 99.2%
completion through a simulated 10-minute outage." *(Your numbers, measured.)*

---

## Skills matrix

Which capstone exercises which skill — useful for filling gaps in a portfolio.

| Skill | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Prompting & structured output | ● | ● | | ● | ● | ● | ● | ● | ● | | | |
| RAG & retrieval | ● | | ● | | | ● | | ● | ● | | | |
| Memory & state design | | | | ● | ● | ● | ● | ● | ● | | | |
| Tools & security | | | | | ● | ● | | ● | ● | ● | | ● |
| LangGraph control flow | | | | | ● | ● | ● | ● | ● | | | |
| Persistence & HITL | | | | ● | ● | | ● | | ● | | | ● |
| Multi-agent | | | | | | ● | | ● | | | | |
| Streaming & UI | | | | | | | | ● | ● | | | |
| Reliability | | | | | ● | | | | ● | ● | | ● |
| Evaluation | ● | ● | ● | ● | ● | ● | ● | ● | ● | | ● | ● |
| MCP / AI SDK | | | | | | | | | | ● | | |
| Deployment & scale | | | | | | | | | ● | ● | ● | |

---

## The capstone README checklist

```
   □ the problem in one sentence, before any technology
   □ a demo GIF or screenshots
   □ an architecture diagram generated from the code
   □ an evaluation table: dataset size, metrics, before/after
   □ latency and cost per request, measured
   □ "what broke and how I fixed it" — with a trace or eval as evidence
   □ one command for tests and evals, without an API key
   □ limitations and what you'd do next
```

See [Day 28 §6](../week-04-production-projects-and-interviews/day-28-capstones-and-interviews.md#6-under-the-hood)
for a README template and how reviewers read a repository in six minutes.

> The example numbers in the "interview story" lines above are illustrations of the *shape* of a
> good answer. Replace them with your own measurements — an invented number collapses under the
> first follow-up question.
