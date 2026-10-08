# Day 39 — AI Product Engineering: Building Something People Trust and Use

> ⏱ **Time:** ~3 hours · 🎯 **Prereqs:** [Day 38](day-38-emerging-agents.md), [Day 25](../week-04-production-projects-and-interviews/day-25-observability-and-evaluation.md) · 🧩 **Difficulty:** ●●●○○

**Today you learn:** a feature can pass every eval and still fail. Students may not trust it.
They may not be able to fix its mistakes. And your team may not be able to tell whether last
week's prompt change helped. Today you fix all three. You learn the **UX patterns** that build
trust, and you build a small **feedback API** that ties every thumb to a run id. You turn bad
runs into eval cases. Then you run an **A/B test** of two tutor prompts with a significance
test written by hand. Finally you check **fairness**, and you learn the basics of the
**EU AI Act**.

> 📖 **Words you'll meet today**
>
> - **Explicit feedback** — a signal the user gives on purpose, such as a thumbs-up or a star
>   rating.
> - **Implicit feedback** — a signal you read from behaviour: the user copies, edits,
>   regenerates or leaves.
> - **Run id** — a unique label for one answer. Feedback is useless unless it carries one.
> - **A/B test** — show version A to some users and version B to others, then compare a
>   number you chose in advance.
> - **p-value** — how often a gap this big would appear by pure luck if A and B were the same.
> - **Guardrail metric** — a number that must not get worse (cost, speed, refusals), even when
>   the main number improves.
> - **Selection rate** — the share of a group that gets a positive result. Comparing it across
>   groups is a simple fairness check.
> - **EU AI Act** — the European Union's law on AI. It puts AI systems into risk tiers with
>   different duties.

---

## 1. The problem

StudyBuddy works. The eval suite from [Day 25](../week-04-production-projects-and-interviews/day-25-observability-and-evaluation.md)
passes, and the costs from [Day 34](../week-05-the-model-layer/day-34-cost-and-latency.md) are
under control. Then the product team brings you this
week's notes:

```
   MON  "The tutor told me the wrong date for my exam. I can't see where it got that."
   TUE  Support: 40 students asked "is this a real teacher?"
   WED  We changed the tutor prompt on Friday. Thumbs-up went from 61 % to 64 %.
        Is that real? Nobody knows.
   THU  A thumbs-down arrived with no run id. Which answer was it about?
   FRI  A student's comment in the feedback table contains their phone number.
   SAT  A teacher asks: "Does the essay checker mark down students whose
        first language isn't English?"
   SUN  Legal asks: "Does the EU AI Act apply to us? From when?"
```

None of these is a model problem. A better model fixes none of them. They are **product
engineering** problems: how people see the answer, how you learn from them, how you prove a
change helped, and how you stay fair and legal.

### The real-life version

Think of a new restaurant.

```
   the menu says what each dish contains            SET EXPECTATIONS, SHOW SOURCES
   you can send a dish back, or ask for changes     EDIT, UNDO, REGENERATE
   a waiter asks "how was it?" (few people answer)  EXPLICIT FEEDBACK
   the chef sees which plates come back half-eaten  IMPLICIT FEEDBACK
   a new recipe is tried on half the tables first   A/B TEST
   ...for a full week, not just one busy evening    SAMPLE SIZE, NO PEEKING
   ...and it must not slow the kitchen or cost more GUARDRAIL METRICS
   every guest gets the same care                   FAIRNESS
   the health inspector has rules                   REGULATION
```

A great chef with no feedback loop cooks the same mistakes every night. Today you build the
loop.

---

## 2. Mental model

### The product loop

```
        ┌────────────────────────────────────────────────────────────────────┐
        │                                                                    │
        ▼                                                                    │
   ┌─────────┐  answer + run id   ┌──────────┐  👍 👎 edit copy retry   ┌───────────┐
   │ variant │ ─────────────────▶ │   user   │ ─────────────────────▶ │ feedback  │
   │  A / B  │   sources, undo,   │ (trusts? │   each tied to the     │  log      │
   └─────────┘   AI disclosure    │  fixes?) │   run id               └─────┬─────┘
        ▲                         └──────────┘                              │
        │                                                                   ▼
   ┌─────────────┐   ship B only if the main metric wins       ┌──────────────────────┐
   │  decision   │ ◀────────────── AND no guardrail breaks ───  │ analysis             │
   └─────────────┘                                              │ • online metrics     │
        ▲                                                       │ • z-test per variant │
        │                                                       │ • fairness by group  │
   ┌─────────────┐   bad runs become test cases                 └──────────┬───────────┘
   │ offline     │ ◀───────────────────────────────────────────────────────┘
   │ eval suite  │   (Day 25 runs them, Day 32 cleans them)
   └─────────────┘
```

### Four questions, four tools

| Question | Tool | Built in |
|---|---|---|
| Will users trust it and recover from its mistakes? | UX patterns: sources, streaming, edit/undo, honest refusals, handoff | §3.1, §4.1 |
| What do users think of each answer? | Feedback log keyed by **run id**; explicit + implicit signals | §3.2–3.4, §4.2–4.3 |
| Did the change really help? | **A/B test**: sticky hash assignment, a z-test, guardrails | §3.5–3.9, §4.4–4.6 |
| Is it fair and legal? | Group comparison, consent and retention rules, EU AI Act tiers | §3.10–3.11, §4.7 |

The loop matters more than any single box. Feedback without a run id can't reach the eval
suite. An A/B test without guardrails can ship a slower, costlier product. A fairness check
without feedback data has nothing to check.

---

## 3. First principles

### 3.1 Trust is designed: UX patterns for AI

> 💬 **In plain words:** an AI will be wrong sometimes. Good design tells users what to expect,
> shows where answers come from, and makes mistakes easy to spot and fix.

Normal software is right or it has a bug. An AI feature is right *most* of the time, and it
sounds just as confident when it's wrong. So the interface has to do work the model can't.
Chip Huyen's *AI Engineering* (chapter 10, "AI Engineering Architecture and User Feedback")
treats this as part of the system design, not decoration. These are the patterns that matter
most:

| Pattern | The problem it solves | How | Where in this course |
|---|---|---|---|
| **Set expectations** | Users trust it too much, or not at all | Say what it can and can't do, and that it's AI | §3.11 (a legal duty in the EU) |
| **Show sources** | "Where did it get that?" — no way to check | Citations linked to the exact note and page | [Day 12](../week-02-data-embeddings-and-rag/day-12-naive-rag.md) |
| **Stream the answer** | A blank screen for 5 seconds feels broken | Show tokens as they arrive; allow Stop | [Day 23](../week-04-production-projects-and-interviews/day-23-streaming-and-events.md) |
| **Edit, undo, regenerate** | A wrong answer is a dead end | Let users fix it, roll it back or ask again | [Day 20](../week-03-tools-agents-and-langgraph/day-20-persistence-and-checkpointing.md) (time travel) |
| **Show uncertainty** | Confident tone hides weak evidence | "I found only one note on this" when retrieval is thin | [Day 13](../week-02-data-embeddings-and-rag/day-13-advanced-rag.md) (grading retrieval) |
| **Refuse well** | "I can't help with that" with no reason or next step | Say why, and offer what it *can* do | [Day 35](../week-05-the-model-layer/day-35-ai-security.md) |
| **Human handoff** | Stuck users have nowhere to go | An "Ask a teacher" button that passes the context | [Day 21](../week-03-tools-agents-and-langgraph/day-21-human-in-the-loop.md) |
| **Approve before acting** | The AI does something you can't undo | Ask before writes, sends and payments | [Day 21](../week-03-tools-agents-and-langgraph/day-21-human-in-the-loop.md) |
| **Collect feedback in context** | You never learn what went wrong | A thumb and an edit box *on each answer* | §3.3 (today) |

You already built most of the machinery. What's new today is the **response shape** that
carries it to the screen. Every answer StudyBuddy returns now includes a run id, the sources,
the variant, a short AI disclosure and the actions the user can take:

```
   { runId, answer, sources[], variant, promptVersion, aiDisclosure, actions[], latencyMs }
```

### 3.2 Every answer needs an id you control

> 💬 **In plain words:** if a thumbs-down can't say which answer it is about, you can't learn
> from it. So give each answer an id, send it to the screen, and send it back with the thumb.

[Day 25](../week-04-production-projects-and-interviews/day-25-observability-and-evaluation.md)
showed that a trace is a tree of runs. The **root run** is the whole request. The simplest
design is to **choose the root run id yourself**, before you call the chain. Then the same id
goes into the trace, the response, the screen and the feedback.

Both languages accept a run id in the call's config. We checked with a callback handler that
records every run's id and parent id (`@langchain/core` 1.2.17, `langchain-core` 1.6.7):

```
   JavaScript: invoke(input, { runId })          Python: invoke(inp, {"run_id": run_id})

   chain:OURS:no-parent           ← the root run has exactly the id we passed
   chain:child:parent=OURS        ← the prompt step hangs under it
   model:child:parent=OURS        ← so does the model call

   no runId given → the library makes a fresh one (JS: a string, Python: a UUID object)
```

If you don't pass an id, the library still makes one. But then you have to fish it out of a
callback to show it to the user. Passing your own id is one line, and it can't get lost.

### 3.3 Explicit and implicit feedback

> 💬 **In plain words:** few people press a thumb. Many more copy, edit, retry or leave. Both
> kinds of signal are useful, and each has its own blind spots.

| | Explicit | Implicit |
|---|---|---|
| **Examples** | 👍/👎, 1–5 stars, a comment, "report a problem" | copies the answer, edits it, presses Regenerate, asks the same thing again, leaves mid-answer |
| **Volume** | low — most users never press anything | high — every session produces some |
| **Meaning** | clear, but only from people who chose to answer | noisy: a copy may mean "great" or "I'll fix this elsewhere" |
| **Bias** | angry and delighted users answer most | depends on your UI; a hidden Regenerate button gets few presses |
| **Best use** | the main A/B metric; a queue for human review | guardrails and early warnings; edits give you **free reference answers** |

Huyen's chapter 10 has sections on extracting feedback from the conversation itself, on
feedback design, and on the limits of feedback. Two ideas guide today's design:

- **Ask at the right moment, with little effort.** A thumb on each answer costs one click. A
  five-question survey after each answer gets ignored.
- **Feedback is biased.** The people who rate are not a random sample of users. If you train
  or tune only on what raters liked, you risk a loop that serves the raters, not everyone.

An **edit** is the most valuable implicit signal. The student has told you what the right
answer looked like. That is a reference answer for your eval suite, written by a real user,
for free.

### 3.4 From feedback to eval cases

> 💬 **In plain words:** a thumbs-down is a test case waiting to be written. Save the
> question, the bad answer and (if the user edited it) the fix.

The **flywheel** works like this:

```
   thumbs-down / low rating / edit
        │
        ▼  look up the run by its id → question, answer, prompt version, variant
   { input, badOutput, reference?, notes, sourceRunId, tags: [promptVersion, variant] }
        │
        ▼  a human checks it (Day 32: label, de-duplicate, remove PII)
   offline eval suite (Day 25) ── runs on every change in CI
```

Three rules keep this honest:

1. **Keep the source run id.** When a case fails later, you can open the original trace.
2. **Tag with the prompt version and variant.** You'll see which version produced the
   failures.
3. **Have a human check before a case becomes a test.** Some thumbs-downs are wrong, rude or
   about something else. [Day 32](../week-05-the-model-layer/day-32-dataset-engineering.md)
   covers cleaning and de-duplicating such data.

### 3.5 A/B testing: a fair split that sticks

> 💬 **In plain words:** decide each user's version with a hash of their id. The same user
> always gets the same version, on any server, and about half get each.

To compare two tutor prompts, you need two groups of users who differ only in the prompt. The
split has three jobs:

- **Random** — so the groups are alike in every other way.
- **Sticky** — so a user sees one version. If a student sees both, you can't say which one
  earned their thumb.
- **Stateless** — so any server can work it out without a database lookup.

A **hash** does all three. Hash the text `"experiment-name:user-id"` with SHA-256, take the
first 8 hex digits as a number, and keep the remainder after dividing by 100. That gives a
**bucket** from 0 to 99. Buckets below 50 get B.

```
   bucket("tutor-prompt-2026-10:u0001") = 44  → B
   bucket("tutor-prompt-2026-10:u0002") = 71  → A
   10,000 users → A 5,012 · B 4,988          (same numbers in JS and Python)
```

Two details matter:

- **Put the experiment name in the hash** (this is called a *salt*). Without it, the same users
  land in B for *every* experiment. They get every new feature at once, and the effects mix.
- **Ramp by moving the threshold.** Start B at 10 % (buckets 0–9), then go to 50 %. Everyone
  who was in B at 10 % stays in B at 50 %. We checked: 1,020 of 1,020.

### 3.6 Is the difference real? The two-proportion z-test

> 💬 **In plain words:** if A and B were truly the same, how often would luck alone produce a
> gap this big? If the answer is "rarely", the gap is probably real.

Say A got **300 thumbs-up from 500 ratings** (60 %) and B got **345 from 500** (69 %). These
counts are illustrative. Is 9 points real? Work it out step by step:

```
   1. Pooled rate — the rate if A and B were the same:
        (300 + 345) / (500 + 500) = 0.645

   2. Standard error — how much the gap wobbles by luck alone:
        √( 0.645 × 0.355 × (1/500 + 1/500) ) = 0.0303

   3. z — the gap measured in "wobbles":
        (0.69 − 0.60) / 0.0303 = 2.974

   4. p-value — the chance of |z| ≥ 2.974 if A = B:
        2 × (1 − Φ(2.974)) = 0.0029             (Φ is the normal curve's area function)

   5. 95 % confidence interval for the gap (uses each group's own rate):
        0.09 ± 1.96 × √(0.6×0.4/500 + 0.69×0.31/500) = [0.031, 0.149]
```

Our code prints exactly these numbers (§4.4): `z 2.974`, `p 0.0029`, `ci95 [0.0309, 0.1491]`.

Read the result in plain words. If the prompts were truly equal, a gap this big would appear
about 3 times in 1,000 tests. The true lift is probably between 3 and 15 points. The usual
cut-off is **p < 0.05** (1 in 20). Set it before the test starts, not after you see the data.

> 💡 **A p-value is not "the chance B is better".** It is the chance of seeing data like this
> *if there were no difference*. A small p says "luck is a poor explanation". The interval
> tells you how big the effect probably is. Report both.

### 3.7 How many users do you need?

> 💬 **In plain words:** small improvements need a lot of data to see. Work out the number
> before you start, so you know how long to run the test.

[Day 0C](../week-00-start-here/day-00c-just-enough-maths.md) showed that five tests can't tell
a 60 % bot from an 80 % bot. A/B tests have the same problem at a larger scale. The standard
formula for ratings needed **per variant** (5 % false-alarm rate, 80 % chance to detect a real
lift) is:

```
   n = (1.96 + 0.8416)² × (p₁(1−p₁) + p₂(1−p₂)) / (p₂ − p₁)²
```

Our code gives:

| Baseline → hoped-for | Lift | Ratings per variant |
|---|---|---|
| 60 % → 69 % | 9 points | 440 |
| 60 % → 63 % | 3 points | 4,126 |
| 60 % → 61 % | 1 point | 37,511 |
| 5 % → 6 % | 1 point | 8,156 |

The pattern is the lesson. **Halve the lift and you need about four times the data**, because
the gap is squared in the formula. And remember these are *ratings*, not users. If 3 in 10
users press a thumb, 4,126 ratings per variant means about 27,500 users in total.

### 3.8 Four ways A/B tests lie

> 💬 **In plain words:** the maths is easy. The traps are in how you run the test.

**1. Peeking.** You check the p-value every day and stop the first time it dips below 0.05.
Each look is another chance for luck to cross the line. We simulated 1,000 **A/A tests**
(both variants identical, so every "winner" is false), with 2,000 ratings each:

```
   look once, at the planned end      4.1 % false winners    (≈ the 5 % you signed up for)
   look every 100 ratings (20 looks) 22.1 % false winners    (more than four times as many)
```

Fix: decide the sample size first (§3.7) and look once. If you must monitor, use a method
designed for it (§6.3).

**2. The novelty effect.** Users click on anything new for a few days, then settle. A test
that runs for two days measures curiosity. Run for at least one full week, so every weekday is
included, and compare week one with week two.

**3. The wrong unit.** One keen student rates 50 answers. Those 50 ratings are not 50
independent people. The z-test assumes independence, so it becomes over-confident. Analyse per
**user** (each user's share of thumbs-up), or cap ratings per user.

**4. Many metrics, one lucky winner.** Test 20 metrics at p < 0.05 and, on average, one will
"win" by luck. Choose **one primary metric** in advance. Everything else is a guardrail or a
clue.

### 3.9 Online metrics, offline evals and guardrails

> 💬 **In plain words:** offline evals check answers on your test set. Online metrics check
> whether real users like the change, and whether you can afford it. A change must pass both.

[Day 25 §3.9](../week-04-production-projects-and-interviews/day-25-observability-and-evaluation.md)
split evaluation into offline and online. A/B testing is the strongest form of online
evaluation, because it compares two versions on the same kind of traffic at the same time.

| | Offline eval | Online A/B test |
|---|---|---|
| Data | a fixed dataset with reference answers | live users, no references |
| Speed | minutes, in CI | days to weeks |
| Answers | "is B correct on known cases?" | "do users prefer B, at what cost?" |
| Catches | regressions before release | effects you can't predict: tone, trust, behaviour |
| Risk | none to users | some users get the worse version |

Run offline evals first. Only a change that passes them earns an A/B test.

An online test has **one primary metric** and several **guardrail metrics**. The primary
metric is what you hope to improve, such as the thumbs-up rate. Guardrails are things that
must not get worse: p95 latency, cost (tokens per answer), refusal rate and error rate. Set
the guardrail limits before the test.

Our simulated StudyBuddy test (§4.6, 8,000 users, illustrative "true" rates planted in the
simulation) shows why guardrails matter:

```
          rated  thumbs-up rate   p95 ms   refusal rate   tokens/answer
   A      1178      0.5696         1469       0.0232            199
   B      1175      0.6596         1768       0.0426            310

   diff 0.0900  z 4.483  p 0.000007  95% CI [0.0508, 0.1291]
     PASS primary: B's thumbs-up rate is higher (p < 0.05)
     PASS guardrail: p95 latency within 1.25x
     FAIL guardrail: refusal rate up by at most 1 point
     FAIL guardrail: tokens per answer within 1.5x
   decision: KEEP A (fix B and re-test)
```

B wins clearly on the primary metric. But it refuses almost twice as often and uses 56 % more
tokens. Shipping it would trade a happier majority for more stuck students and a bigger bill.
The right move is to fix B's refusals and length, then test again.

Notice one more thing. We planted a true lift of 6 points, but the test measured 9. The 95 %
interval (5.1 to 12.9 points) still contains 6. A single test's estimate is noisy, so read the
interval, not just the point.

### 3.10 Responsible AI: fairness, transparency, consent

> 💬 **In plain words:** check whether your feature treats groups of users differently. Tell
> people what you are doing. Keep only the data you need, and only for as long as you need it.

**Fairness.** StudyBuddy's essay checker says "ready to submit" or "needs work". A teacher
asks if it is harder on students whose first language isn't English. You can check with
counts. Ask teachers to mark a sample of essays too, then compare (illustrative counts):

```
                            essays  model said "ready"  selection rate  true-positive rate
   English first language     200        132               0.66             0.917
   English second language    100         51               0.51             0.75

   selection-rate ratio 0.51 / 0.66 = 0.773 → FLAG (below 0.8)
   selection gap 0.150, p = 0.0120 · true-positive-rate gap 0.167, p = 0.0023
```

Two different questions are hiding here:

- **Selection rate**: what share of each group gets "ready"? A common rule of thumb flags a
  ratio below 0.8 — the "four-fifths rule" from US hiring guidance. Here it's 0.773.
- **True-positive rate**: of the essays that *teachers* said were ready, what share did the
  model pass? This is the sharper test. Groups can differ in real quality, which affects the
  selection rate. But a good essay should pass whoever wrote it. Here the model misses 25 % of
  good essays by second-language writers, and only 8 % for first-language writers.

The p-values say the gaps are unlikely to be luck. The fix is not in the statistics. Look at
the missed essays. You may find the prompt rewards "native-sounding" style rather than the
rubric. Then re-run the check after every prompt change, like any other eval.

> ⚠️ **To check fairness you need group data, and that is sensitive data.** Collect it only
> with consent, keep it apart from the user's identity, and use it only for the check.

**Transparency.** Tell users they are talking to an AI, what it is for, and how their data is
used. Show sources. Explain refusals. In the EU this is partly a legal duty (§3.11).

**Data retention and consent.** Feedback logs hold questions, answers and comments, which are
personal data. In the EU, the GDPR's principles apply. Use data only for the purpose you
stated (*purpose limitation*), collect only what you need (*data minimisation*), and keep it
only as long as needed (*storage limitation*). In practice:

- store a **pseudonym**, not the raw user id;
- **redact** emails and phone numbers before saving comments (and know that regex redaction
  misses names and addresses, see §7);
- set a retention period, such as 30 days for raw logs, and delete on schedule;
- ask before using a student's conversations to improve the product, and honour "no".

### 3.11 Regulation basics: the EU AI Act

> 💬 **In plain words:** the EU sorts AI systems into risk levels. Most LLM apps land in the
> "transparency" level: tell people they are talking to an AI and label generated content.
> Some uses, such as grading students, count as high-risk and carry much heavier duties.

> ⚖️ **Not legal advice.** This section summarises public sources as of October 2026. Laws
> change and the details depend on your exact use. Check the current rules for your country,
> and ask a lawyer before you rely on any of this.

The **EU AI Act** (Regulation (EU) 2024/1689) entered into force on **1 August 2024**. It sorts
AI systems into four tiers, according to the European Commission's summary:

| Tier | What it covers | What you must do |
|---|---|---|
| **Unacceptable** | Practices that threaten people's safety or rights — e.g. social scoring, harmful manipulation, emotion recognition in workplaces and schools | Banned |
| **High risk** | Uses listed in the Act, including **education** (admissions, grading, steering learning, detecting cheating in tests), jobs, credit, essential services | Risk management, data quality, logging, documentation, human oversight, robustness |
| **Transparency** | Chatbots and systems that generate content | Tell people they are dealing with an AI; mark or label generated content |
| **Minimal** | Most other AI, e.g. spam filters, video games | No new rules |

**Key dates** (from the Commission's timeline and the 2026 amendment):

```
   1 Aug 2024   the Act enters into force
   2 Feb 2025   bans on prohibited practices apply; AI literacy duty (Article 4)
   2 Aug 2025   rules for general-purpose AI models apply (the model makers)
   2 Aug 2026   general application, including Article 50 transparency duties
   2 Dec 2026   end of the grace period for machine-readable marking (Art. 50(2)) for
                systems already on the market before 2 Aug 2026
   2 Dec 2027   high-risk duties for Annex III uses (education, jobs, ...)
   2 Aug 2028   high-risk duties for AI inside regulated products (Annex I)
```

The high-risk dates moved in 2026. The **Digital Omnibus on AI** (Regulation (EU) 2026/1744)
was published on 24 July 2026 and entered into force on 27 July 2026. It moved Annex III
high-risk duties from August 2026 to **2 December 2027**. It did **not** delay the Article 50
transparency duties.

**What typically applies to an LLM app like StudyBuddy?**

- **Article 50(1)**: if your system talks with people, design it so they are told they are
  interacting with an AI, unless that is obvious. That is the `aiDisclosure` field in §4.1.
- **Article 50(2)**: providers of systems that generate synthetic audio, images, video or text
  must mark outputs in a machine-readable way, with some exceptions (for example, simple
  editing help). Read the Commission's current guidance to see what this means for chat text.
- **Article 50(4)**: deepfakes, and AI text published to inform the public, must be disclosed,
  unless a human reviewed the text and takes editorial responsibility.
- **Article 4**: providers and deployers should support AI literacy among their staff.
- **High risk depends on the use, not the model.** A homework helper is usually a transparency
  case. The *same model* used to grade exams, decide admissions or flag cheating falls under
  Annex III point 3 (education), with the full high-risk duties from 2 December 2027.

The penalties are in Article 99. Legal summaries put the maximum fine for breaking the Article
50 duties at €15 million or 3 % of worldwide turnover, whichever is higher.

**Other regions.** Many countries have their own AI rules, privacy laws and education rules.
We could not source them well enough for this page, so we don't summarise them here. Check
the rules where your users live, not only where your company is.

---

## 4. Code — JavaScript

> **Install:** `npm i @langchain/core` — only `tutor.mjs` needs it. Everything else uses
> Node's built-in `node:crypto`, `node:http` and `node:fs`. No API key: the tutor is a
> scripted model, so every number below is repeatable. Swap in `ChatGroq` later. Versions
> used: Node 24.15, `@langchain/core` 1.2.17.

You build six small files that work together:

```
   abtest.mjs    sticky assignment · z-test · sample size · seeded random numbers
   tutor.mjs     the tutor: picks the variant, sets the run id, returns the response shape
   feedback.mjs  run log + feedback log + eval cases, with redaction
   server.mjs    POST /feedback and GET /eval-cases over HTTP
   simulate.mjs  fake traffic for practising the analysis
   decide.mjs    one primary metric + guardrails → a decision
```

### 4.1 A response built for trust

`tutor.mjs` answers a question and returns everything the screen needs. Read the comments on
the `response` object: each field serves one pattern from §3.1.

```js
// tutor.mjs — a keyless StudyBuddy tutor that returns a UX-ready response envelope.
import { randomUUID } from "node:crypto";
import { BaseChatModel } from "@langchain/core/language_models/chat_models";
import { AIMessage } from "@langchain/core/messages";
import { ChatPromptTemplate } from "@langchain/core/prompts";
import { assignVariant } from "./abtest.mjs";

// A scripted model: replies depend on the style in the system prompt. Swap in ChatGroq later.
class FakeTutor extends BaseChatModel {
  _llmType() { return "fake-tutor"; }
  async _generate(messages) {
    const socratic = messages[0].content.includes("question");
    const text = socratic
      ? "Good question! What do plants take in from the air? Start there, then add sunlight."
      : "Photosynthesis turns light, water and carbon dioxide into glucose and oxygen [1].";
    return { generations: [{ message: new AIMessage(text), text }] };
  }
}

export const PROMPTS = {
  A: { version: "direct-v1", text: "You are a tutor. Answer clearly in two sentences. Cite notes." },
  B: { version: "socratic-v1", text: "You are a tutor. Guide with one question at a time. Cite notes." },
};
export const EXPERIMENT = "tutor-prompt-2026-10";

const chain = ChatPromptTemplate.fromMessages([["system", "{style}"], ["human", "{question}"]])
  .pipe(new FakeTutor({}));

export async function ask(userId, question, log = null) {
  const variant = assignVariant(userId, EXPERIMENT);
  const prompt = PROMPTS[variant];
  const runId = randomUUID(); // WE choose the id, so the UI can send feedback for it
  const t0 = performance.now();
  const msg = await chain.invoke(
    { style: prompt.text, question },
    { runId, runName: "studybuddy-tutor",
      metadata: { variant, promptVersion: prompt.version, experiment: EXPERIMENT } },
  );
  const response = {
    runId,                                   // → feedback buttons
    answer: msg.content,
    sources: [{ id: 1, title: "Biology notes, week 3", page: 12 }], // → citations (Day 12)
    variant, promptVersion: prompt.version,  // → analysis
    aiDisclosure: "StudyBuddy is an AI tutor. It can be wrong — check your notes.",
    actions: ["copy", "regenerate", "edit", "thumbs", "ask-a-teacher"],
    latencyMs: Math.round(performance.now() - t0),
  };
  log?.logRun({ userId, question, ...response }); // the server logs every run it answers
  return response;
}
```

Three design choices are worth noticing:

- **The server picks the variant**, from the user id. The browser never decides, so a user
  can't switch versions by reloading.
- **The run id is created before the call** and passed as `runId`. §3.2 showed it becomes the
  root run's id, so the trace and the feedback share one key.
- **Metadata carries the variant and prompt version** into the trace, so Day 25's dashboards
  can split results by version.

### 4.2 The feedback log

`feedback.mjs` stores two kinds of rows: **runs** (what was answered) and **feedback** (what
the user did about it). It checks that the run exists, checks the value, removes PII, and can
turn bad runs into eval cases.

```js
// feedback.mjs — a run log + feedback log that turns bad runs into eval cases.
import { appendFileSync } from "node:fs";
import { createHash } from "node:crypto";

// What kinds of feedback we accept, and which values are valid for each.
const KINDS = {
  thumbs: (v) => v === 1 || v === -1,                      // explicit
  rating: (v) => Number.isInteger(v) && v >= 1 && v <= 5,  // explicit
  edit: (v) => typeof v === "string" && v.length > 0,      // implicit: the user fixed the answer
  copy: (v) => v === null,                                 // implicit: the user kept it
  regenerate: (v) => v === null,                           // implicit: the user wanted another
};

// Remove the two commonest kinds of PII before anything is stored.
export function redact(text) {
  return text
    .replace(/[\w.+-]+@[\w-]+(\.[\w-]+)+/g, "[email]")
    .replace(/\+?\d[\d\s().-]{7,}\d/g, "[phone]");
}

// Store a stable pseudonym, not the raw user id.
export const pseudonym = (userId) =>
  createHash("sha256").update(`studybuddy:${userId}`).digest("hex").slice(0, 12);

export class FeedbackLog {
  constructor(path = null) {
    this.path = path;          // a JSONL file, or null for memory only
    this.runs = new Map();     // runId → run record
    this.feedback = [];
  }

  #write(type, row) {
    if (this.path) appendFileSync(this.path, JSON.stringify({ type, ...row }) + "\n");
  }

  logRun({ runId, userId, variant, promptVersion, question, answer, latencyMs }) {
    const row = { runId, user: pseudonym(userId), variant, promptVersion,
      question: redact(question), answer, latencyMs, at: new Date().toISOString() };
    this.runs.set(runId, row);
    this.#write("run", row);
    return row;
  }

  addFeedback({ runId, kind, value = null, comment = "" }) {
    if (!this.runs.has(runId)) {
      const err = new Error(`unknown runId: ${runId}`);
      err.status = 404;
      throw err;
    }
    if (!(kind in KINDS)) throw Object.assign(new Error(`unknown kind: ${kind}`), { status: 400 });
    if (!KINDS[kind](value)) throw Object.assign(new Error(`bad value for ${kind}`), { status: 400 });
    const row = {
      runId, kind,
      value: typeof value === "string" ? redact(value) : value,
      comment: redact(String(comment)).slice(0, 500),
      at: new Date().toISOString(),
    };
    this.feedback.push(row);
    this.#write("feedback", row);
    return row;
  }

  // Bad runs become eval cases: a thumbs-down, a rating of 1–2, or an edit.
  evalCases() {
    const cases = new Map();
    for (const f of this.feedback) {
      const bad = (f.kind === "thumbs" && f.value === -1) || (f.kind === "rating" && f.value <= 2)
        || f.kind === "edit";
      if (!bad) continue;
      const run = this.runs.get(f.runId);
      const c = cases.get(f.runId) ?? {
        input: run.question, badOutput: run.answer, reference: null, notes: [],
        sourceRunId: f.runId, tags: [run.promptVersion, `variant-${run.variant}`],
      };
      if (f.kind === "edit") c.reference = f.value; // the user's fix is a free reference answer
      if (f.comment) c.notes.push(f.comment);
      cases.set(f.runId, c);
    }
    return [...cases.values()];
  }
}
```

> 🔒 **Validate on the server, always.** The browser sends the feedback, so a user (or a bot)
> can send anything: a fake run id, a rating of 500, a comment with someone's phone number.
> The checks above reject the first two and redact the third.

### 4.3 The feedback API

A real app needs an HTTP endpoint the browser can call. Node's built-in `http` module is
enough for two routes:

```js
// server.mjs — a tiny feedback API with node:http (no framework needed).
import http from "node:http";

export function feedbackServer(log) {
  return http.createServer(async (req, res) => {
    const send = (status, body) => {
      res.writeHead(status, { "content-type": "application/json" });
      res.end(JSON.stringify(body));
    };
    try {
      if (req.method === "POST" && req.url === "/feedback") {
        let body = "";
        for await (const chunk of req) body += chunk;
        return send(201, log.addFeedback(JSON.parse(body)));
      }
      if (req.method === "GET" && req.url === "/eval-cases") return send(200, log.evalCases());
      return send(404, { error: "not found" });
    } catch (err) {
      return send(err.status ?? 400, { error: err.message });
    }
  });
}
```

Now try the whole flow: three answers, then feedback the way a browser would send it,
including two bad requests.

```js
// try-feedback.mjs — run with: node try-feedback.mjs
import { rmSync, readFileSync } from "node:fs";
import { ask } from "./tutor.mjs";
import { FeedbackLog } from "./feedback.mjs";
import { feedbackServer } from "./server.mjs";

rmSync("feedback.jsonl", { force: true });
const log = new FeedbackLog("feedback.jsonl");

// 1. Three answers, each logged with the run id the UI will send back.
const r1 = await ask("u0001", "What is photosynthesis?", log);
const r2 = await ask("u0002", "What is photosynthesis?", log);
const r3 = await ask("u0003", "Why are leaves green?", log);
console.log("response keys:", Object.keys(r1).join(", "));
console.log(r1.variant, r1.promptVersion, "|", r1.answer);
console.log(r2.variant, r2.promptVersion, "|", r2.answer);

// 2. Start the API on a free port and post feedback like a browser would.
const server = feedbackServer(log);
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve)); // wait until listening
const base = `http://127.0.0.1:${server.address().port}`;
const post = async (body) => {
  const res = await fetch(`${base}/feedback`, { method: "POST", body: JSON.stringify(body) });
  return `${res.status} ${JSON.stringify(await res.json())}`;
};
console.log(await post({ runId: r1.runId, kind: "thumbs", value: 1 }));
console.log(await post({ runId: r2.runId, kind: "thumbs", value: -1,
  comment: "Too short, no example. Email me at sam@example.com" }));
console.log(await post({ runId: r3.runId, kind: "edit",
  value: "Leaves look green because chlorophyll reflects green light." }));
console.log(await post({ runId: "not-a-real-run", kind: "thumbs", value: 1 }));
console.log(await post({ runId: r1.runId, kind: "thumbs", value: 5 }));

// 3. Bad runs come back as eval cases.
const cases = await (await fetch(`${base}/eval-cases`)).json();
console.log(JSON.stringify(cases, null, 2));
server.close();
console.log("lines in feedback.jsonl:", readFileSync("feedback.jsonl", "utf8").trim().split("\n").length);
```

Expected output (run ids and times differ on every run):

```
response keys: runId, answer, sources, variant, promptVersion, aiDisclosure, actions, latencyMs
B socratic-v1 | Good question! What do plants take in from the air? Start there, then add sunlight.
A direct-v1 | Photosynthesis turns light, water and carbon dioxide into glucose and oxygen [1].
201 {"runId":"cdd9a13d-…","kind":"thumbs","value":1,"comment":"","at":"2026-10-07T08:48:14.282Z"}
201 {"runId":"7fdbc80c-…","kind":"thumbs","value":-1,"comment":"Too short, no example. Email me at [email]","at":"…"}
201 {"runId":"4f31efc9-…","kind":"edit","value":"Leaves look green because chlorophyll reflects green light.","comment":"","at":"…"}
404 {"error":"unknown runId: not-a-real-run"}
400 {"error":"bad value for thumbs"}
[
  {
    "input": "What is photosynthesis?",
    "badOutput": "Photosynthesis turns light, water and carbon dioxide into glucose and oxygen [1].",
    "reference": null,
    "notes": [ "Too short, no example. Email me at [email]" ],
    "sourceRunId": "7fdbc80c-…",
    "tags": [ "direct-v1", "variant-A" ]
  },
  {
    "input": "Why are leaves green?",
    "badOutput": "Photosynthesis turns light, water and carbon dioxide into glucose and oxygen [1].",
    "reference": "Leaves look green because chlorophyll reflects green light.",
    "notes": [],
    "sourceRunId": "4f31efc9-…",
    "tags": [ "direct-v1", "variant-A" ]
  }
]
lines in feedback.jsonl: 6
```

Everything from §3.2–3.4 is visible here. The email is gone before storage. A fake run id gets
a `404`. A thumb of `5` gets a `400`. And the student's edit has become a **reference answer**
for a wrong reply. The scripted tutor answered "Why are leaves green?" with its photosynthesis
line. A real model makes exactly this kind of mistake.

> ⚠️ **Wait for `listen` before reading the port.** With a host argument,
> `server.listen(0, "127.0.0.1")` is asynchronous: `server.address()` was `null` straight after
> the call in our test (Node 24.15). Without a host it returned an address at once. The
> `await new Promise(...)` line makes the order explicit.

### 4.4 Sticky assignment and the z-test

`abtest.mjs` holds the statistics from §3.5–3.7. JavaScript has no built-in `erf` (the
function behind the normal curve), so it uses a well-known approximation.

```js
// abtest.mjs — sticky assignment, a two-proportion test, and sample size. No libraries.
import { createHash } from "node:crypto";

// ── 1. Sticky assignment ──────────────────────────────────────────────────────
// Hash "experiment:user" → a bucket from 0 to 99. Same inputs → same bucket, on any server,
// in any language. Putting the experiment name in the hash gives each experiment its own split.
export function bucket(userId, experiment) {
  const hex = createHash("sha256").update(`${experiment}:${userId}`).digest("hex");
  return parseInt(hex.slice(0, 8), 16) % 100; // first 32 bits → 0..99
}

// percentB = how much traffic gets the new variant (ramp it: 5 → 20 → 50).
export function assignVariant(userId, experiment, percentB = 50) {
  return bucket(userId, experiment) < percentB ? "B" : "A";
}

// ── 2. The normal curve ───────────────────────────────────────────────────────
// JavaScript has no Math.erf, so we use a classic approximation
// (Abramowitz & Stegun 7.1.26, error below 0.0000002).
function erf(x) {
  const sign = x < 0 ? -1 : 1;
  const a = Math.abs(x);
  const t = 1 / (1 + 0.3275911 * a);
  const poly = ((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - 0.284496736) * t
    + 0.254829592) * t;
  return sign * (1 - poly * Math.exp(-a * a));
}
export const normalCdf = (z) => 0.5 * (1 + erf(z / Math.SQRT2));

// ── 3. Two-proportion z-test ──────────────────────────────────────────────────
// "Is B's success rate really different from A's, or is the gap just luck?"
export function twoProportionTest(successA, nA, successB, nB) {
  const pA = successA / nA;
  const pB = successB / nB;
  const pooled = (successA + successB) / (nA + nB); // the rate if A and B were the same
  const sePooled = Math.sqrt(pooled * (1 - pooled) * (1 / nA + 1 / nB));
  const z = (pB - pA) / sePooled;
  const pValue = 2 * (1 - normalCdf(Math.abs(z))); // two-sided
  const se = Math.sqrt((pA * (1 - pA)) / nA + (pB * (1 - pB)) / nB);
  const diff = pB - pA;
  return { pA, pB, diff, z, pValue, ci95: [diff - 1.96 * se, diff + 1.96 * se] };
}

// ── 4. Sample size per variant ────────────────────────────────────────────────
// 1.96 → 5 % false-alarm rate (two-sided). 0.8416 → 80 % chance to detect a real lift.
export function sampleSizePerArm(p1, p2, zAlpha = 1.96, zPower = 0.8416) {
  const variance = p1 * (1 - p1) + p2 * (1 - p2);
  return Math.ceil(((zAlpha + zPower) ** 2 * variance) / (p2 - p1) ** 2);
}

// ── 5. Seeded randomness for simulations (Day 0C's makeRng) ───────────────────
export function makeRng(seed) {
  let state = seed % 4294967296;
  return () => {
    state = (state * 1664525 + 1013904223) % 4294967296;
    return state / 4294967296;
  };
}
```

```js
// try-abtest.mjs — run with: node try-abtest.mjs
import { assignVariant, bucket, twoProportionTest, sampleSizePerArm } from "./abtest.mjs";

const EXP = "tutor-prompt-2026-10";
for (const user of ["u0001", "u0002", "u0003", "u0004", "u0005"]) {
  console.log(user, bucket(user, EXP), assignVariant(user, EXP));
}

// Sticky? Ask 3 times for the same user.
console.log("u0001 three times:", [1, 2, 3].map(() => assignVariant("u0001", EXP)).join(" "));

// Balanced? 10,000 users.
const counts = { A: 0, B: 0 };
for (let i = 1; i <= 10000; i++) counts[assignVariant(`u${String(i).padStart(4, "0")}`, EXP)]++;
console.log("10,000 users:", counts);

// Illustrative counts: 300 of 500 thumbs-up for A, 345 of 500 for B.
const r = twoProportionTest(300, 500, 345, 500);
console.log({
  pA: r.pA, pB: r.pB, diff: +r.diff.toFixed(4), z: +r.z.toFixed(3),
  pValue: +r.pValue.toFixed(4), ci95: r.ci95.map((x) => +x.toFixed(4)),
});

// How many rated answers per variant to detect each lift?
for (const [p1, p2] of [[0.6, 0.69], [0.6, 0.63], [0.6, 0.61], [0.05, 0.06]]) {
  console.log(`${p1} → ${p2}: ${sampleSizePerArm(p1, p2)} per variant`);
}
```

Expected output:

```
u0001 44 B
u0002 71 A
u0003 63 A
u0004 38 B
u0005 62 A
u0001 three times: B B B
10,000 users: { A: 5012, B: 4988 }
{
  pA: 0.6,
  pB: 0.69,
  diff: 0.09,
  z: 2.974,
  pValue: 0.0029,
  ci95: [ 0.0309, 0.1491 ]
}
0.6 → 0.69: 440 per variant
0.6 → 0.63: 4126 per variant
0.6 → 0.61: 37511 per variant
0.05 → 0.06: 8156 per variant
```

### 4.5 Peeking, measured

An **A/A test** gives both groups the same version. Any "winner" is a false alarm, so it is
the perfect way to measure how often a method fools you.

```js
// peeking.mjs — run with: node peeking.mjs
// An A/A test: A and B are IDENTICAL (both 60 % thumbs-up). Any "winner" is a false alarm.
import { makeRng, twoProportionTest } from "./abtest.mjs";

const rng = makeRng(2026);
const EXPERIMENTS = 1000, RATINGS = 2000, PEEK_EVERY = 100, RATE = 0.6;
let falseAtEnd = 0, falseWithPeeking = 0;

for (let e = 0; e < EXPERIMENTS; e++) {
  const n = { A: 0, B: 0 }, up = { A: 0, B: 0 };
  let stoppedEarly = false;
  for (let i = 1; i <= RATINGS; i++) {
    const v = i % 2 ? "A" : "B";      // alternate: equal group sizes
    n[v]++;
    if (rng() < RATE) up[v]++;
    if (i % PEEK_EVERY === 0 && !stoppedEarly) {
      // The impatient analyst looks after every 100 ratings and stops at the first p < 0.05.
      if (twoProportionTest(up.A, n.A, up.B, n.B).pValue < 0.05) stoppedEarly = true;
    }
  }
  if (stoppedEarly) falseWithPeeking++;
  if (twoProportionTest(up.A, n.A, up.B, n.B).pValue < 0.05) falseAtEnd++; // the patient analyst
}
console.log(`look once at the end:  ${(100 * falseAtEnd / EXPERIMENTS).toFixed(1)} % false winners`);
console.log(`peek 20 times:         ${(100 * falseWithPeeking / EXPERIMENTS).toFixed(1)} % false winners`);
```

Expected output (about 1 second here):

```
look once at the end:  4.1 % false winners
peek 20 times:         22.1 % false winners
```

### 4.6 Guardrails and the decision

`simulate.mjs` produces fake traffic with "true" rates we plant, so you can practise the
analysis and check it finds them. `decide.mjs` turns the numbers into a decision.

```js
// simulate.mjs — fake StudyBuddy traffic for an A/B test, so you can practise the analysis.
import { assignVariant, makeRng } from "./abtest.mjs";

// The "truth" we plant (ILLUSTRATIVE numbers): B is liked a little more,
// but it is slower, longer (more tokens) and refuses more often.
export const TRUTH = {
  A: { thumbsUp: 0.6, baseMs: 900, spreadMs: 600, refuse: 0.02, baseTokens: 150 },
  B: { thumbsUp: 0.66, baseMs: 1100, spreadMs: 700, refuse: 0.04, baseTokens: 260 },
};

// Day 0C's nearest-rank percentile.
export function percentile(xs, p) {
  const sorted = [...xs].sort((a, b) => a - b);
  return sorted[Math.max(Math.ceil((p * sorted.length) / 100), 1) - 1];
}

export function simulate(nUsers, { seed = 7, experiment = "tutor-prompt-2026-10" } = {}) {
  const rng = makeRng(seed);
  const s = {};
  for (const v of ["A", "B"]) s[v] = { users: 0, rated: 0, up: 0, refused: 0, tokens: 0, ms: [] };
  for (let i = 1; i <= nUsers; i++) {
    const v = assignVariant(`u${String(i).padStart(5, "0")}`, experiment);
    const t = TRUTH[v];
    // Always draw five numbers per user, in the same order, so JS and Python stay in step.
    const [rRated, rLiked, rMs, rRefuse, rTokens] = [rng(), rng(), rng(), rng(), rng()];
    const refused = rRefuse < t.refuse;
    s[v].users++;
    s[v].ms.push(t.baseMs + rMs * t.spreadMs);
    s[v].tokens += t.baseTokens + Math.floor(rTokens * 100);
    if (refused) s[v].refused++;
    else if (rRated < 0.3) { // only about 3 in 10 users press a thumb at all
      s[v].rated++;
      if (rLiked < t.thumbsUp) s[v].up++;
    }
  }
  const metrics = {};
  for (const v of ["A", "B"]) {
    metrics[v] = {
      users: s[v].users, rated: s[v].rated, up: s[v].up,
      thumbsUpRate: +(s[v].up / s[v].rated).toFixed(4),
      p95Ms: Math.round(percentile(s[v].ms, 95)),
      refusalRate: +(s[v].refused / s[v].users).toFixed(4),
      tokensPerAnswer: Math.round(s[v].tokens / s[v].users),
    };
  }
  return metrics;
}
```

```js
// decide.mjs — one primary metric, three guardrails, one decision.
import { twoProportionTest } from "./abtest.mjs";

// Guardrail limits (ILLUSTRATIVE — your team sets these before the test starts).
export const GUARDRAILS = { maxP95Ratio: 1.25, maxRefusalIncrease: 0.01, maxTokenRatio: 1.5 };

export function decide(m) {
  const test = twoProportionTest(m.A.up, m.A.rated, m.B.up, m.B.rated);
  const checks = {
    "primary: B's thumbs-up rate is higher (p < 0.05)": test.pValue < 0.05 && test.diff > 0,
    "guardrail: p95 latency within 1.25x": m.B.p95Ms <= m.A.p95Ms * GUARDRAILS.maxP95Ratio,
    "guardrail: refusal rate up by at most 1 point":
      m.B.refusalRate - m.A.refusalRate <= GUARDRAILS.maxRefusalIncrease,
    "guardrail: tokens per answer within 1.5x":
      m.B.tokensPerAnswer <= m.A.tokensPerAnswer * GUARDRAILS.maxTokenRatio,
  };
  const ship = Object.values(checks).every(Boolean);
  return { test, checks, decision: ship ? "SHIP B" : "KEEP A (fix B and re-test)" };
}
```

```js
// try-experiment.mjs — run with: node try-experiment.mjs
import { simulate } from "./simulate.mjs";
import { decide } from "./decide.mjs";

const m = simulate(8000);
console.table(m);
const { test, checks, decision } = decide(m);
console.log(`diff ${test.diff.toFixed(4)}  z ${test.z.toFixed(3)}  p ${test.pValue.toFixed(6)}`
  + `  95% CI [${test.ci95.map((x) => x.toFixed(4)).join(", ")}]`);
for (const [name, ok] of Object.entries(checks)) console.log(ok ? "  PASS" : "  FAIL", name);
console.log("decision:", decision);
```

Expected output:

```
┌─────────┬───────┬───────┬─────┬──────────────┬───────┬─────────────┬─────────────────┐
│ (index) │ users │ rated │ up  │ thumbsUpRate │ p95Ms │ refusalRate │ tokensPerAnswer │
├─────────┼───────┼───────┼─────┼──────────────┼───────┼─────────────┼─────────────────┤
│ A       │ 4010  │ 1178  │ 671 │ 0.5696       │ 1469  │ 0.0232      │ 199             │
│ B       │ 3990  │ 1175  │ 775 │ 0.6596       │ 1768  │ 0.0426      │ 310             │
└─────────┴───────┴───────┴─────┴──────────────┴───────┴─────────────┴─────────────────┘
diff 0.0900  z 4.483  p 0.000007  95% CI [0.0508, 0.1291]
  PASS primary: B's thumbs-up rate is higher (p < 0.05)
  PASS guardrail: p95 latency within 1.25x
  FAIL guardrail: refusal rate up by at most 1 point
  FAIL guardrail: tokens per answer within 1.5x
decision: KEEP A (fix B and re-test)
```

Refused answers are not counted as rated here, because a student can't judge an answer they
never got. That is a design choice. Write yours down before the test starts.

### 4.7 A fairness check

The same z-test answers a fairness question: is the gap between two groups bigger than luck?

```js
// fairness.mjs — run with: node fairness.mjs
// Does StudyBuddy's "ready to submit" verdict treat two groups of students alike?
// Each row compares the model's verdict with a teacher's verdict on the same essay.
// ILLUSTRATIVE counts from a pretend review of 300 essays.
import { twoProportionTest } from "./abtest.mjs";

const groups = {
  "English first language": { tp: 110, fn: 10, fp: 22, tn: 58 },  // tp = both said "ready"
  "English second language": { tp: 45, fn: 15, fp: 6, tn: 34 },   // fn = teacher yes, model no
};

const rows = {};
for (const [name, g] of Object.entries(groups)) {
  const n = g.tp + g.fn + g.fp + g.tn;
  rows[name] = {
    essays: n,
    selected: g.tp + g.fp,                          // model said "ready"
    selectionRate: +((g.tp + g.fp) / n).toFixed(3),
    truePositiveRate: +(g.tp / (g.tp + g.fn)).toFixed(3), // of essays a teacher passed
  };
}
console.table(rows);

const [hi, lo] = Object.values(rows).sort((a, b) => b.selectionRate - a.selectionRate);
const ratio = lo.selectionRate / hi.selectionRate;
console.log(`selection-rate ratio: ${ratio.toFixed(3)} → ${ratio < 0.8 ? "FLAG (below 0.8)" : "ok"}`);

const t = twoProportionTest(lo.selected, lo.essays, hi.selected, hi.essays);
console.log(`gap ${t.diff.toFixed(3)}, p = ${t.pValue.toFixed(4)}`);

const [g1, g2] = Object.values(groups);
const tpr = twoProportionTest(g2.tp, g2.tp + g2.fn, g1.tp, g1.tp + g1.fn);
console.log(`true-positive-rate gap ${tpr.diff.toFixed(3)}, p = ${tpr.pValue.toFixed(4)}`);
```

Expected output:

```
┌─────────────────────────┬────────┬──────────┬───────────────┬──────────────────┐
│ (index)                 │ essays │ selected │ selectionRate │ truePositiveRate │
├─────────────────────────┼────────┼──────────┼───────────────┼──────────────────┤
│ English first language  │ 200    │ 132      │ 0.66          │ 0.917            │
│ English second language │ 100    │ 51       │ 0.51          │ 0.75             │
└─────────────────────────┴────────┴──────────┴───────────────┴──────────────────┘
selection-rate ratio: 0.773 → FLAG (below 0.8)
gap 0.150, p = 0.0120
true-positive-rate gap 0.167, p = 0.0023
```

### 4.8 Sending feedback to LangSmith

If you trace with LangSmith ([Day 25](../week-04-production-projects-and-interviews/day-25-observability-and-evaluation.md)),
you can attach the same feedback to the trace. You then see the thumb next to the full run
tree.

```js
// Not executed here — needs LANGSMITH_API_KEY and tracing switched on.
// Signature read from the installed langsmith 0.10.8: createFeedback(runId, key, options).
import { Client } from "langsmith";

const client = new Client();
await client.createFeedback(runId, "thumbs", { score: 1, comment: redact(comment) });
// an edit can travel as a correction:
await client.createFeedback(runId, "edit", { correction: { answer: editedText } });
```

Keep your own log as well. It is yours to query, join and delete, and it works without a
vendor account.

---

## 5. Code — Python

> **Install:** `pip install langchain-core` — only `tutor.py` needs it. Everything else uses
> the standard library (`hashlib`, `http.server`, `json`, `math`). Versions used: Python 3.14,
> `langchain-core` 1.6.7.

The same six files, with the same names and the same numbers.

### 5.1 A response built for trust

```python
# tutor.py — a keyless StudyBuddy tutor that returns a UX-ready response envelope.
import time
import uuid

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.prompts import ChatPromptTemplate

from abtest import assign_variant


class FakeTutor(GenericFakeChatModel):
    """A scripted model: replies depend on the style in the system prompt."""
    messages: object = iter([])  # required by the parent class; unused here

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        socratic = "question" in messages[0].content
        text = ("Good question! What do plants take in from the air? Start there, then add sunlight."
                if socratic else
                "Photosynthesis turns light, water and carbon dioxide into glucose and oxygen [1].")
        return ChatResult(generations=[ChatGeneration(message=AIMessage(text))])


PROMPTS = {
    "A": {"version": "direct-v1", "text": "You are a tutor. Answer clearly in two sentences. Cite notes."},
    "B": {"version": "socratic-v1", "text": "You are a tutor. Guide with one question at a time. Cite notes."},
}
EXPERIMENT = "tutor-prompt-2026-10"

chain = ChatPromptTemplate.from_messages([("system", "{style}"), ("human", "{question}")]) | FakeTutor()


def ask(user_id: str, question: str, log=None) -> dict:
    variant = assign_variant(user_id, EXPERIMENT)
    prompt = PROMPTS[variant]
    run_id = str(uuid.uuid4())  # WE choose the id, so the UI can send feedback for it
    t0 = time.perf_counter()
    msg = chain.invoke(
        {"style": prompt["text"], "question": question},
        {"run_id": run_id, "run_name": "studybuddy-tutor",
         "metadata": {"variant": variant, "prompt_version": prompt["version"],
                      "experiment": EXPERIMENT}})
    response = {
        "run_id": run_id,                                         # -> feedback buttons
        "answer": msg.content,
        "sources": [{"id": 1, "title": "Biology notes, week 3", "page": 12}],  # -> Day 12
        "variant": variant, "prompt_version": prompt["version"],  # -> analysis
        "ai_disclosure": "StudyBuddy is an AI tutor. It can be wrong — check your notes.",
        "actions": ["copy", "regenerate", "edit", "thumbs", "ask-a-teacher"],
        "latency_ms": round((time.perf_counter() - t0) * 1000),
    }
    if log is not None:
        log.log_run(user_id=user_id, question=question, **response)  # log every run
    return response
```

> 📦 **`GenericFakeChatModel` needs a `messages` field** even when you override `_generate`.
> The class attribute `messages: object = iter([])` satisfies it.

### 5.2 The feedback log

```python
# feedback.py — a run log + feedback log that turns bad runs into eval cases.
import hashlib
import json
import re
from datetime import datetime, timezone

# What kinds of feedback we accept, and which values are valid for each.
KINDS = {
    "thumbs": lambda v: v in (1, -1) and not isinstance(v, bool),        # explicit
    "rating": lambda v: isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 5,
    "edit": lambda v: isinstance(v, str) and len(v) > 0,      # implicit: the user fixed it
    "copy": lambda v: v is None,                              # implicit: the user kept it
    "regenerate": lambda v: v is None,                        # implicit: wanted another
}

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
PHONE = re.compile(r"\+?\d[\d\s().-]{7,}\d")


class FeedbackError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def redact(text: str) -> str:
    """Remove the two commonest kinds of PII before anything is stored."""
    return PHONE.sub("[phone]", EMAIL.sub("[email]", text))


def pseudonym(user_id: str) -> str:
    """Store a stable pseudonym, not the raw user id."""
    return hashlib.sha256(f"studybuddy:{user_id}".encode()).hexdigest()[:12]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class FeedbackLog:
    def __init__(self, path=None):
        self.path = path   # a JSONL file, or None for memory only
        self.runs = {}     # run_id -> run record
        self.feedback = []

    def _write(self, kind, row):
        if self.path:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"type": kind, **row}) + "\n")

    def log_run(self, *, run_id, user_id, variant, prompt_version, question, answer,
                latency_ms, **_ignored):
        row = {"run_id": run_id, "user": pseudonym(user_id), "variant": variant,
               "prompt_version": prompt_version, "question": redact(question),
               "answer": answer, "latency_ms": latency_ms, "at": now()}
        self.runs[run_id] = row
        self._write("run", row)
        return row

    def add_feedback(self, run_id, kind, value=None, comment=""):
        if run_id not in self.runs:
            raise FeedbackError(f"unknown run_id: {run_id}", status=404)
        if kind not in KINDS:
            raise FeedbackError(f"unknown kind: {kind}")
        if not KINDS[kind](value):
            raise FeedbackError(f"bad value for {kind}")
        row = {"run_id": run_id, "kind": kind,
               "value": redact(value) if isinstance(value, str) else value,
               "comment": redact(str(comment))[:500], "at": now()}
        self.feedback.append(row)
        self._write("feedback", row)
        return row

    def eval_cases(self):
        """Bad runs become eval cases: a thumbs-down, a rating of 1-2, or an edit."""
        cases = {}
        for f in self.feedback:
            bad = ((f["kind"] == "thumbs" and f["value"] == -1)
                   or (f["kind"] == "rating" and f["value"] <= 2) or f["kind"] == "edit")
            if not bad:
                continue
            run = self.runs[f["run_id"]]
            c = cases.setdefault(f["run_id"], {
                "input": run["question"], "bad_output": run["answer"], "reference": None,
                "notes": [], "source_run_id": f["run_id"],
                "tags": [run["prompt_version"], f"variant-{run['variant']}"]})
            if f["kind"] == "edit":
                c["reference"] = f["value"]  # the user's fix is a free reference answer
            if f["comment"]:
                c["notes"].append(f["comment"])
        return list(cases.values())
```

> ⚠️ **In Python, `True` is a number.** `True in (1, -1)` is `True`, because `bool` is a
> subclass of `int` (verified). Without the `isinstance(v, bool)` guard, a JSON `true` would be
> stored as a thumbs-up. In JavaScript, `true === 1` is `false`, so the problem doesn't arise.

### 5.3 The feedback API

The standard library's `http.server` is enough for two routes:

```python
# server.py — a tiny feedback API with the standard library (no framework needed).
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from feedback import FeedbackError


def feedback_server(log, port=0):
    class Handler(BaseHTTPRequestHandler):
        def send(self, status, body):
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            if self.path != "/feedback":
                return self.send(404, {"error": "not found"})
            try:
                body = json.loads(self.rfile.read(int(self.headers["content-length"])))
                self.send(201, log.add_feedback(**body))
            except FeedbackError as err:
                self.send(err.status, {"error": str(err)})
            except (ValueError, TypeError) as err:  # bad JSON or unexpected fields
                self.send(400, {"error": str(err)})

        def do_GET(self):
            if self.path == "/eval-cases":
                return self.send(200, log.eval_cases())
            self.send(404, {"error": "not found"})

        def log_message(self, *args):  # keep the console quiet
            pass

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)  # not "localhost": see §7
```

```python
# try_feedback.py — run with: python try_feedback.py
import json
import os
import threading
import urllib.error
import urllib.request

from feedback import FeedbackLog
from server import feedback_server
from tutor import ask

if os.path.exists("feedback.jsonl"):
    os.remove("feedback.jsonl")
log = FeedbackLog("feedback.jsonl")

# 1. Three answers, each logged with the run id the UI will send back.
r1 = ask("u0001", "What is photosynthesis?", log)
r2 = ask("u0002", "What is photosynthesis?", log)
r3 = ask("u0003", "Why are leaves green?", log)
print("response keys:", ", ".join(r1))
print(r1["variant"], r1["prompt_version"], "|", r1["answer"])
print(r2["variant"], r2["prompt_version"], "|", r2["answer"])

# 2. Start the API on a free port and post feedback like a browser would.
server = feedback_server(log)
threading.Thread(target=server.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{server.server_address[1]}"


def post(body):
    req = urllib.request.Request(f"{base}/feedback", data=json.dumps(body).encode(), method="POST",
                                 headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(req) as res:
            return f"{res.status} {res.read().decode()}"
    except urllib.error.HTTPError as err:  # 4xx answers arrive as exceptions in urllib
        return f"{err.code} {err.read().decode()}"


print(post({"run_id": r1["run_id"], "kind": "thumbs", "value": 1}))
print(post({"run_id": r2["run_id"], "kind": "thumbs", "value": -1,
            "comment": "Too short, no example. Email me at sam@example.com"}))
print(post({"run_id": r3["run_id"], "kind": "edit",
            "value": "Leaves look green because chlorophyll reflects green light."}))
print(post({"run_id": "not-a-real-run", "kind": "thumbs", "value": 1}))
print(post({"run_id": r1["run_id"], "kind": "thumbs", "value": 5}))

# 3. Bad runs come back as eval cases.
with urllib.request.urlopen(f"{base}/eval-cases") as res:
    print(json.dumps(json.loads(res.read()), indent=2))
server.shutdown()
with open("feedback.jsonl", encoding="utf-8") as f:
    print("lines in feedback.jsonl:", len(f.read().strip().splitlines()))
```

Expected output (run ids and times differ on every run):

```
response keys: run_id, answer, sources, variant, prompt_version, ai_disclosure, actions, latency_ms
B socratic-v1 | Good question! What do plants take in from the air? Start there, then add sunlight.
A direct-v1 | Photosynthesis turns light, water and carbon dioxide into glucose and oxygen [1].
201 {"run_id": "d5eabdb7-…", "kind": "thumbs", "value": 1, "comment": "", "at": "2026-10-07T08:47:25.494219+00:00"}
201 {"run_id": "d5712197-…", "kind": "thumbs", "value": -1, "comment": "Too short, no example. Email me at [email]", "at": "…"}
201 {"run_id": "6c98d5fe-…", "kind": "edit", "value": "Leaves look green because chlorophyll reflects green light.", "comment": "", "at": "…"}
404 {"error": "unknown run_id: not-a-real-run"}
400 {"error": "bad value for thumbs"}
[ …the same two eval cases as JavaScript, with snake_case keys… ]
lines in feedback.jsonl: 6
```

> 🪟 **Use `127.0.0.1`, not `localhost`, for a Python server on Windows.** With the server
> bound to `"localhost"`, each `urllib` request took **2,227 ms** in our test. Bound to and
> called on `127.0.0.1`, it took **30 ms**. The likely cause is that `localhost` also means
> the IPv6 address `::1`, and the client waits on that before it tries IPv4. We measured the
> delay, not the cause.

### 5.4 Sticky assignment and the z-test

Python ships an exact `math.erf`, so `normal_cdf` is one line.

```python
# abtest.py — sticky assignment, a two-proportion test, and sample size. No libraries.
import hashlib
import math


# ── 1. Sticky assignment ──────────────────────────────────────────────────────
def bucket(user_id: str, experiment: str) -> int:
    """Hash "experiment:user" to a bucket from 0 to 99. Same inputs, same bucket, anywhere."""
    hex_digest = hashlib.sha256(f"{experiment}:{user_id}".encode()).hexdigest()
    return int(hex_digest[:8], 16) % 100  # first 32 bits -> 0..99


def assign_variant(user_id: str, experiment: str, percent_b: int = 50) -> str:
    """percent_b = how much traffic gets the new variant (ramp it: 5 -> 20 -> 50)."""
    return "B" if bucket(user_id, experiment) < percent_b else "A"


# ── 2. The normal curve ───────────────────────────────────────────────────────
def normal_cdf(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))  # Python ships an exact erf


# ── 3. Two-proportion z-test ──────────────────────────────────────────────────
def two_proportion_test(success_a, n_a, success_b, n_b):
    """Is B's success rate really different from A's, or is the gap just luck?"""
    p_a, p_b = success_a / n_a, success_b / n_b
    pooled = (success_a + success_b) / (n_a + n_b)  # the rate if A and B were the same
    se_pooled = math.sqrt(pooled * (1 - pooled) * (1 / n_a + 1 / n_b))
    z = (p_b - p_a) / se_pooled
    p_value = 2 * (1 - normal_cdf(abs(z)))  # two-sided
    se = math.sqrt(p_a * (1 - p_a) / n_a + p_b * (1 - p_b) / n_b)
    diff = p_b - p_a
    return {"p_a": p_a, "p_b": p_b, "diff": diff, "z": z, "p_value": p_value,
            "ci95": (diff - 1.96 * se, diff + 1.96 * se)}


# ── 4. Sample size per variant ────────────────────────────────────────────────
def sample_size_per_arm(p1, p2, z_alpha=1.96, z_power=0.8416):
    """1.96 -> 5 % false-alarm rate (two-sided). 0.8416 -> 80 % chance to detect a real lift."""
    variance = p1 * (1 - p1) + p2 * (1 - p2)
    return math.ceil((z_alpha + z_power) ** 2 * variance / (p2 - p1) ** 2)


# ── 5. Seeded randomness for simulations (Day 0C's make_rng) ──────────────────
def make_rng(seed):
    state = seed % 4294967296

    def next_number():
        nonlocal state
        state = (state * 1664525 + 1013904223) % 4294967296
        return state / 4294967296

    return next_number
```

```python
# try_abtest.py — run with: python try_abtest.py
from abtest import assign_variant, bucket, two_proportion_test, sample_size_per_arm

EXP = "tutor-prompt-2026-10"
for user in ["u0001", "u0002", "u0003", "u0004", "u0005"]:
    print(user, bucket(user, EXP), assign_variant(user, EXP))

print("u0001 three times:", " ".join(assign_variant("u0001", EXP) for _ in range(3)))

counts = {"A": 0, "B": 0}
for i in range(1, 10001):
    counts[assign_variant(f"u{i:04d}", EXP)] += 1
print("10,000 users:", counts)

# Illustrative counts: 300 of 500 thumbs-up for A, 345 of 500 for B.
r = two_proportion_test(300, 500, 345, 500)
print({"p_a": r["p_a"], "p_b": r["p_b"], "diff": round(r["diff"], 4), "z": round(r["z"], 3),
       "p_value": round(r["p_value"], 4), "ci95": tuple(round(x, 4) for x in r["ci95"])})

for p1, p2 in [(0.6, 0.69), (0.6, 0.63), (0.6, 0.61), (0.05, 0.06)]:
    print(f"{p1} -> {p2}: {sample_size_per_arm(p1, p2)} per variant")
```

Expected output — the same buckets, counts and statistics as JavaScript:

```
u0001 44 B
u0002 71 A
u0003 63 A
u0004 38 B
u0005 62 A
u0001 three times: B B B
10,000 users: {'A': 5012, 'B': 4988}
{'p_a': 0.6, 'p_b': 0.69, 'diff': 0.09, 'z': 2.974, 'p_value': 0.0029, 'ci95': (0.0309, 0.1491)}
0.6 -> 0.69: 440 per variant
0.6 -> 0.63: 4126 per variant
0.6 -> 0.61: 37511 per variant
0.05 -> 0.06: 8156 per variant
```

### 5.5 Peeking, measured

```python
# peeking.py — run with: python peeking.py
# An A/A test: A and B are IDENTICAL (both 60 % thumbs-up). Any "winner" is a false alarm.
from abtest import make_rng, two_proportion_test

rng = make_rng(2026)
EXPERIMENTS, RATINGS, PEEK_EVERY, RATE = 1000, 2000, 100, 0.6
false_at_end = false_with_peeking = 0

for _ in range(EXPERIMENTS):
    n, up = {"A": 0, "B": 0}, {"A": 0, "B": 0}
    stopped_early = False
    for i in range(1, RATINGS + 1):
        v = "A" if i % 2 else "B"  # alternate: equal group sizes
        n[v] += 1
        if rng() < RATE:
            up[v] += 1
        if i % PEEK_EVERY == 0 and not stopped_early:
            # The impatient analyst looks after every 100 ratings and stops at the first p < 0.05.
            if two_proportion_test(up["A"], n["A"], up["B"], n["B"])["p_value"] < 0.05:
                stopped_early = True
    false_with_peeking += stopped_early
    if two_proportion_test(up["A"], n["A"], up["B"], n["B"])["p_value"] < 0.05:
        false_at_end += 1  # the patient analyst

print(f"look once at the end:  {100 * false_at_end / EXPERIMENTS:.1f} % false winners")
print(f"peek 20 times:         {100 * false_with_peeking / EXPERIMENTS:.1f} % false winners")
```

Expected output (about 9 seconds here, against about 1 second in Node):

```
look once at the end:  4.1 % false winners
peek 20 times:         22.1 % false winners
```

### 5.6 Guardrails and the decision

```python
# simulate.py — fake StudyBuddy traffic for an A/B test, so you can practise the analysis.
import math

from abtest import assign_variant, make_rng

# The "truth" we plant (ILLUSTRATIVE numbers): B is liked a little more,
# but it is slower, longer (more tokens) and refuses more often.
TRUTH = {
    "A": {"thumbs_up": 0.60, "base_ms": 900, "spread_ms": 600, "refuse": 0.02, "base_tokens": 150},
    "B": {"thumbs_up": 0.66, "base_ms": 1100, "spread_ms": 700, "refuse": 0.04, "base_tokens": 260},
}


def percentile(xs, p):
    """Day 0C's nearest-rank percentile."""
    s = sorted(xs)
    return s[max(math.ceil(p * len(s) / 100), 1) - 1]


def simulate(n_users, seed=7, experiment="tutor-prompt-2026-10"):
    rng = make_rng(seed)
    s = {v: {"users": 0, "rated": 0, "up": 0, "refused": 0, "tokens": 0, "ms": []} for v in "AB"}
    for i in range(1, n_users + 1):
        v = assign_variant(f"u{i:05d}", experiment)
        t = TRUTH[v]
        # Always draw five numbers per user, in the same order, so JS and Python stay in step.
        r_rated, r_liked, r_ms, r_refuse, r_tokens = rng(), rng(), rng(), rng(), rng()
        refused = r_refuse < t["refuse"]
        s[v]["users"] += 1
        s[v]["ms"].append(t["base_ms"] + r_ms * t["spread_ms"])
        s[v]["tokens"] += t["base_tokens"] + math.floor(r_tokens * 100)
        if refused:
            s[v]["refused"] += 1
        elif r_rated < 0.3:  # only about 3 in 10 users press a thumb at all
            s[v]["rated"] += 1
            if r_liked < t["thumbs_up"]:
                s[v]["up"] += 1
    return {v: {"users": s[v]["users"], "rated": s[v]["rated"], "up": s[v]["up"],
                "thumbs_up_rate": round(s[v]["up"] / s[v]["rated"], 4),
                "p95_ms": round(percentile(s[v]["ms"], 95)),
                "refusal_rate": round(s[v]["refused"] / s[v]["users"], 4),
                "tokens_per_answer": round(s[v]["tokens"] / s[v]["users"])}
            for v in "AB"}
```

```python
# decide.py — one primary metric, three guardrails, one decision.
from abtest import two_proportion_test

# Guardrail limits (ILLUSTRATIVE — your team sets these before the test starts).
GUARDRAILS = {"max_p95_ratio": 1.25, "max_refusal_increase": 0.01, "max_token_ratio": 1.5}


def decide(m):
    a, b = m["A"], m["B"]
    test = two_proportion_test(a["up"], a["rated"], b["up"], b["rated"])
    checks = {
        "primary: B's thumbs-up rate is higher (p < 0.05)": test["p_value"] < 0.05 and test["diff"] > 0,
        "guardrail: p95 latency within 1.25x": b["p95_ms"] <= a["p95_ms"] * GUARDRAILS["max_p95_ratio"],
        "guardrail: refusal rate up by at most 1 point":
            b["refusal_rate"] - a["refusal_rate"] <= GUARDRAILS["max_refusal_increase"],
        "guardrail: tokens per answer within 1.5x":
            b["tokens_per_answer"] <= a["tokens_per_answer"] * GUARDRAILS["max_token_ratio"],
    }
    ship = all(checks.values())
    return {"test": test, "checks": checks, "decision": "SHIP B" if ship else "KEEP A (fix B and re-test)"}
```

```python
# try_experiment.py — run with: python try_experiment.py
from decide import decide
from simulate import simulate

m = simulate(8000)
for v, row in m.items():
    print(v, row)
r = decide(m)
t = r["test"]
print(f"diff {t['diff']:.4f}  z {t['z']:.3f}  p {t['p_value']:.6f}"
      f"  95% CI [{t['ci95'][0]:.4f}, {t['ci95'][1]:.4f}]")
for name, ok in r["checks"].items():
    print("  PASS" if ok else "  FAIL", name)
print("decision:", r["decision"])
```

Expected output:

```
A {'users': 4010, 'rated': 1178, 'up': 671, 'thumbs_up_rate': 0.5696, 'p95_ms': 1469, 'refusal_rate': 0.0232, 'tokens_per_answer': 199}
B {'users': 3990, 'rated': 1175, 'up': 775, 'thumbs_up_rate': 0.6596, 'p95_ms': 1768, 'refusal_rate': 0.0426, 'tokens_per_answer': 310}
diff 0.0900  z 4.483  p 0.000007  95% CI [0.0508, 0.1291]
  PASS primary: B's thumbs-up rate is higher (p < 0.05)
  PASS guardrail: p95 latency within 1.25x
  FAIL guardrail: refusal rate up by at most 1 point
  FAIL guardrail: tokens per answer within 1.5x
decision: KEEP A (fix B and re-test)
```

### 5.7 A fairness check

```python
# fairness.py — run with: python fairness.py
# Does StudyBuddy's "ready to submit" verdict treat two groups of students alike?
# Each row compares the model's verdict with a teacher's verdict on the same essay.
# ILLUSTRATIVE counts from a pretend review of 300 essays.
from abtest import two_proportion_test

groups = {
    "English first language": {"tp": 110, "fn": 10, "fp": 22, "tn": 58},  # tp = both said "ready"
    "English second language": {"tp": 45, "fn": 15, "fp": 6, "tn": 34},   # fn = teacher yes, model no
}

rows = {}
for name, g in groups.items():
    n = sum(g.values())
    rows[name] = {
        "essays": n,
        "selected": g["tp"] + g["fp"],                       # model said "ready"
        "selection_rate": round((g["tp"] + g["fp"]) / n, 3),
        "true_positive_rate": round(g["tp"] / (g["tp"] + g["fn"]), 3),  # of essays a teacher passed
    }
for name, r in rows.items():
    print(f"{name:24} {r}")

hi, lo = sorted(rows.values(), key=lambda r: r["selection_rate"], reverse=True)
ratio = lo["selection_rate"] / hi["selection_rate"]
print(f"selection-rate ratio: {ratio:.3f} -> {'FLAG (below 0.8)' if ratio < 0.8 else 'ok'}")

t = two_proportion_test(lo["selected"], lo["essays"], hi["selected"], hi["essays"])
print(f"gap {t['diff']:.3f}, p = {t['p_value']:.4f}")

g1, g2 = groups.values()
tpr = two_proportion_test(g2["tp"], g2["tp"] + g2["fn"], g1["tp"], g1["tp"] + g1["fn"])
print(f"true-positive-rate gap {tpr['diff']:.3f}, p = {tpr['p_value']:.4f}")
```

Expected output:

```
English first language   {'essays': 200, 'selected': 132, 'selection_rate': 0.66, 'true_positive_rate': 0.917}
English second language  {'essays': 100, 'selected': 51, 'selection_rate': 0.51, 'true_positive_rate': 0.75}
selection-rate ratio: 0.773 -> FLAG (below 0.8)
gap 0.150, p = 0.0120
true-positive-rate gap 0.167, p = 0.0023
```

### 5.8 Sending feedback to LangSmith

```python
# Not executed here — needs LANGSMITH_API_KEY and tracing switched on.
# Signature read from the installed langsmith 0.14.4: create_feedback(run_id, key, *, score, ...)
from langsmith import Client

client = Client()
client.create_feedback(run_id, key="thumbs", score=1, comment=redact(comment))
client.create_feedback(run_id, key="edit", correction={"answer": edited_text})
```

### 5.9 The JS ↔ Python translation for today

| Idea | JavaScript | Python |
|---|---|---|
| Choose the root run id | `invoke(input, { runId })` | `invoke(inp, {"run_id": run_id})` |
| Id made by the library (none passed) | a string | a `uuid.UUID` object |
| New UUID | `randomUUID()` from `node:crypto` | `str(uuid.uuid4())` |
| SHA-256 hex | `createHash("sha256").update(s).digest("hex")` | `hashlib.sha256(s.encode()).hexdigest()` |
| Hex → integer | `parseInt(hex.slice(0, 8), 16)` | `int(hex_digest[:8], 16)` |
| Normal curve | no `erf`: approximation (error < 2 × 10⁻⁷) | `math.erf` (exact) |
| p-value for z = 4.483 | `7.360e-6` | `7.353e-06` — both print `0.000007` at 6 decimals |
| Seeded random numbers | Day 0C's `makeRng` | Day 0C's `make_rng` — identical sequence |
| Tiny HTTP server | `http.createServer`, `listen(0, host, cb)` | `ThreadingHTTPServer`, `BaseHTTPRequestHandler` |
| 4xx reply in the client | `fetch` resolves; read `res.status` | `urllib` raises `HTTPError`; read `err.code` |
| Validate a thumb | `v === 1 \|\| v === -1` (a `true` fails) | needs `not isinstance(v, bool)` (`True == 1`) |
| JSON `4.0` as a rating | parsed as `4`, accepted | parsed as `4.0` (a float), rejected by `isinstance(v, int)` |
| Append a JSONL line | `appendFileSync(path, line)` | `open(path, "a").write(line)` |
| LangSmith feedback | `client.createFeedback(runId, key, { score })` | `client.create_feedback(run_id, key=…, score=…)` |
| Peeking simulation time (measured) | about 1 s | about 9 s |

---

## 6. Under the hood

### 6.1 Why a hash makes a fair split

SHA-256 mixes its input so thoroughly that its output bits behave like coin flips. Change one
character of the user id and about half the output bits change. So the first 32 bits, taken
`% 100`, spread users almost evenly over the 100 buckets. "Almost", because 2³² is not a
multiple of 100: 96 buckets get one extra value out of about 43 million. That bias is far too
small to matter.

The hash is also **deterministic**. Every server, in every language, computes the same bucket
from the same text. JavaScript and Python gave identical buckets for every user we tried. So
you need no database of assignments, and a user keeps their variant after a deploy, a restart
or a switch of language.

What a hash can't do is fix a **wrong unit**. If you hash the session id, a student who logs
in on two devices may see both variants. Hash the id of the thing you want to keep consistent:
usually the user, sometimes the class or the school.

### 6.2 Why the z-test works, and when it doesn't

A thumbs-up rate from *n* ratings wobbles from sample to sample. For large *n*, that wobble
follows the bell-shaped **normal curve**, with a width (standard error) of `√(p(1−p)/n)`. The
gap between two independent rates also follows a normal curve. Dividing the gap by its
standard error gives *z*: "how many wobbles away from zero". The normal curve then tells you
how rare that is.

The approximation needs three things:

- **Enough data.** A common rule of thumb is at least about 10 successes and 10 failures in
  each group. Below that, use an exact test, such as Fisher's exact test.
- **Independent ratings.** One user's 50 ratings are not 50 independent facts (§3.8).
- **A fixed plan.** The test assumes you look once, at a sample size chosen in advance.

### 6.3 Why peeking breaks the test

A p-value threshold of 0.05 promises a 5 % false-alarm rate **for one look**. Every extra look
is another draw. Early on, with few ratings, the rate jumps around a lot, so luck crosses the
line easily. Our A/A simulation turned 5 % into 22.1 % with 20 looks.

Teams that need to watch a test as it runs use **sequential testing** methods. These are
designed for repeated looks. They make each look stricter, so the total false-alarm rate stays
at 5 %. Many experiment platforms offer them. If yours doesn't, fix the sample size and look
once.

### 6.4 What "online" costs

Every online signal has a price:

- **Feedback buttons** cost screen space and attention. Too many prompts annoy users, and
  annoyed users stop answering.
- **A/B tests** cost exposure. Half your users get the version that turns out worse, for as
  long as the test runs. That's why you run offline evals first (Day 25), and why you ramp
  from 5–10 % before going to 50 %.
- **Logging** costs privacy. Every stored question is personal data with a retention clock.

The guardrails in `decide` are the product version of [Day 24](../week-04-production-projects-and-interviews/day-24-reliability.md)'s
reliability limits. A change that wins on quality but breaks a limit has not won.

### 6.5 Feedback data is product data, and personal data

The feedback log is now one of your most valuable datasets. It holds real questions, real
failures and real corrections. It is also personal data. Treat it like a database, not a log
file:

- **One owner and a schema.** Run ids, pseudonyms, variants and prompt versions, all typed.
- **Deletion that works.** When a student asks to be forgotten, you must find their rows. A
  pseudonym made by a keyed hash lets you do that, as long as the key exists. Delete the key
  and the rows can no longer be linked to the student.
- **Retention on a schedule.** Raw rows expire. Approved eval cases are reviewed, stripped of
  PII and kept for longer, for a stated purpose.

> 📚 **Sources**
>
> - Chip Huyen, *AI Engineering* (O'Reilly, 2024), chapter 10 "AI Engineering Architecture
>   and User Feedback" — table of contents: <https://github.com/chiphuyen/aie-book/blob/main/ToC.md>
> - European Commission, *AI Act* — risk tiers and application timeline (read October 2026):
>   <https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai>
> - EU AI Act, Article 50 (transparency obligations): <https://artificialintelligenceact.eu/article/50/>
> - EU AI Act, Annex III (high-risk uses, point 3 education): <https://artificialintelligenceact.eu/annex/3/>
> - Regulation (EU) 2026/1744, the Digital Omnibus on AI — summary with dates (published
>   24 July 2026, in force 27 July 2026):
>   <https://www.praxikon.com/en/richtsnoeren/regulation-eu-2026-1744-digital-omnibus-on-ai>
> - Jones Walker, *Yes, August 2 Still Matters* — Article 50 dates, the 50(2) grace period and
>   penalties: <https://www.joneswalker.com/en/insights/blogs/ai-law-blog/yes-august-2-still-matters-the-eu-approved-a-high-risk-ai-delay-but-most-trans.html?id=102nbon>
> - GDPR Article 5 (purpose limitation, data minimisation, storage limitation):
>   <https://gdpr-info.eu/art-5-gdpr/>
> - US Uniform Guidelines on Employee Selection Procedures, 29 CFR 1607.4(D) (the four-fifths
>   rule): <https://www.law.cornell.edu/cfr/text/29/1607.4>

---

## 7. Common mistakes

### ❌ 1. A new coin flip on every request

```js
// ❌ wrong — Math.random() per request
const variant = Math.random() < 0.5 ? "A" : "B";
// ✅ right — a hash of experiment + user
const variant = assignVariant(userId, "tutor-prompt-2026-10");
```

**Symptom (measured):** with 5 visits each, **930 of 1,000** users saw both variants. With the
hash, 0 did. Their thumbs can't be credited to either version.

### ❌ 2. Stopping the test the first day p < 0.05

**Symptom (measured):** in 1,000 A/A tests, peeking every 100 ratings declared a winner
**22.1 %** of the time, against 4.1 % for one look at the end. Fix the sample size first
(§3.7), and look once.

### ❌ 3. Feedback without a run id

```python
# ❌ wrong — guess the answer from the user's latest run
run = latest_run_for(user_id)
# ✅ right — the browser sends back the run id it was given
log.add_feedback(run_id=body["run_id"], kind="thumbs", value=-1)
```

**Symptom (measured):** with two answers per student and a thumb on one of them, "latest run"
attached **506 of 1,000** thumbs to the wrong answer. The eval cases built from them are
wrong too.

### ❌ 4. Storing raw comments

**Symptom:** `"Call me on +44 7700 900123 or mail sam.lee@example.com"` sits in your database,
backups and analytics exports. With `redact` it is stored as `"Call me on [phone] or mail
[email]"`.

Know the limits of regex redaction too. In our tests it turned the date `2026-10-07` and an
ISBN into `[phone]`, and it left `"My name is Sam Lee, I live at 4 Elm Road"` untouched.
Use it as a first layer. Add the PII tools from [Day 24](../week-04-production-projects-and-interviews/day-24-reliability.md)
for names and addresses, and keep comments short-lived.

### ❌ 5. Hashing the user id without the experiment name

```js
// ❌ wrong — the same users are in B for every experiment
bucket = hash(userId) % 100;
// ✅ right — each experiment gets its own split
bucket = hash(`${experiment}:${userId}`) % 100;
```

**Symptom (measured):** unsalted, **4,987 of 4,987** B users were in B for two different
experiments. Salted, 2,531 of 4,951 were — about half, as chance predicts.

### ❌ 6. Trusting `True == 1` in Python validation

```python
# ❌ wrong — JSON true passes as a thumbs-up
"thumbs": lambda v: v in (1, -1)
# ✅ right
"thumbs": lambda v: v in (1, -1) and not isinstance(v, bool)
```

**Symptom (verified):** `True in (1, -1)` is `True`, so a buggy client's `true` is stored as
👍.

### ❌ 7. Calling a Python test server on `localhost` (Windows)

**Symptom (measured):** each request took about **2.2 seconds** instead of 30 ms. A test suite
of 100 requests takes minutes. Bind to and call `127.0.0.1`.

### ❌ 8. Shipping on the primary metric alone

**Symptom (measured in our simulation):** B won on thumbs-up (p = 0.000007). But its refusal
rate went from 2.3 % to 4.3 %, and its tokens per answer from 199 to 310. Without guardrails,
"B won" ships a costlier, more frustrating product.

### ❌ 9. Counting ratings as if they were users

A few keen students rate dozens of answers each, so the ratings are not independent. The
z-test becomes over-confident and calls noise "significant". Analyse per user, or cap the
ratings each user contributes.

### ❌ 10. Treating the EU AI Act as "only for big model makers"

The general-purpose AI model rules (from 2 August 2025) are aimed at model makers. But the
Article 50 transparency duties (from 2 August 2026) apply to the *systems* people use. That
includes an app built on someone else's model. And a feature that grades students is a
high-risk use, whoever made the model. Classify each feature by **use**, not by model.

---

## 8. Exercises

### Exercise 1 — Prove the split is sticky, balanced and rampable ●●○○○

Using `abtest.mjs` / `abtest.py` from §4.4 and §5.4, for 10,000 users `u0001…u10000`:

1. Ask for each user's variant three times. Count users whose variant changed.
2. Count users in B at 50 % and at a 10 % ramp.
3. Check that every user in B at 10 % is still in B at 50 %.
4. Print the variants of the first five users. Do JavaScript and Python agree?

<details>
<summary>✅ Solution</summary>

**JavaScript**

```js
// ex1.mjs — sticky, balanced, rampable
import { assignVariant } from "./abtest.mjs";

const EXP = "tutor-prompt-2026-10";
const users = Array.from({ length: 10000 }, (_, i) => `u${String(i + 1).padStart(4, "0")}`);

// 1. Sticky: ask 3 times for every user, count users who ever got two answers.
const flipped = users.filter((u) => new Set([1, 2, 3].map(() => assignVariant(u, EXP))).size > 1);
console.log("users whose variant changed:", flipped.length);

// 2. Balanced at 50 %, and at a 10 % ramp.
for (const pct of [50, 10]) {
  const b = users.filter((u) => assignVariant(u, EXP, pct) === "B").length;
  console.log(`percentB=${pct}: ${b} of ${users.length} in B`);
}

// 3. Ramping keeps people: is everyone in B at 10 % still in B at 50 %?
const early = users.filter((u) => assignVariant(u, EXP, 10) === "B");
console.log("10 % users still in B at 50 %:", early.filter((u) => assignVariant(u, EXP, 50) === "B").length,
  "of", early.length);

// 4. Same answer as Python?
console.log(users.slice(0, 5).map((u) => assignVariant(u, EXP)).join(""));
```

**Python**

```python
# ex1.py — sticky, balanced, rampable
from abtest import assign_variant

EXP = "tutor-prompt-2026-10"
users = [f"u{i:04d}" for i in range(1, 10001)]

# 1. Sticky: ask 3 times for every user, count users who ever got two answers.
flipped = [u for u in users if len({assign_variant(u, EXP) for _ in range(3)}) > 1]
print("users whose variant changed:", len(flipped))

# 2. Balanced at 50 %, and at a 10 % ramp.
for pct in (50, 10):
    b = sum(assign_variant(u, EXP, pct) == "B" for u in users)
    print(f"percent_b={pct}: {b} of {len(users)} in B")

# 3. Ramping keeps people: is everyone in B at 10 % still in B at 50 %?
early = [u for u in users if assign_variant(u, EXP, 10) == "B"]
print("10 % users still in B at 50 %:", sum(assign_variant(u, EXP, 50) == "B" for u in early),
      "of", len(early))

# 4. Same answer as JavaScript?
print("".join(assign_variant(u, EXP) for u in users[:5]))
```

Expected output (both languages):

```
users whose variant changed: 0
percentB=50: 4988 of 10000 in B
percentB=10: 1020 of 10000 in B
10 % users still in B at 50 %: 1020 of 1020
BAABA
```

**Why this design.** Ramping works because "bucket < 10" is a subset of "bucket < 50". Users
only ever move *into* B as you ramp up, never out. A per-request coin flip has none of these
properties.
</details>

---

### Exercise 2 — Read a result, then plan the next test ●●○○○

1. Last week, A got 120 thumbs-up from 400 ratings and B got 150 from 400. Compute the
   difference, z, the p-value and the 95 % interval. Would you call it?
2. Next, you hope to move 30 % to 33 %. How many ratings per variant do you need?
3. You collect 300 ratings a day, split across both variants. How many days?

<details>
<summary>✅ Solution</summary>

**JavaScript**

```js
// ex2.mjs — read an A/B result, then plan the next one
import { twoProportionTest, sampleSizePerArm } from "./abtest.mjs";

// 1. Last week: A got 120 thumbs-up from 400 ratings; B got 150 from 400.
const t = twoProportionTest(120, 400, 150, 400);
console.log(`A ${t.pA}  B ${t.pB}  diff ${t.diff.toFixed(3)}  z ${t.z.toFixed(3)}  p ${t.pValue.toFixed(4)}`);
console.log(`95% CI [${t.ci95.map((x) => x.toFixed(3)).join(", ")}]`);

// 2. Next test: you hope for 30 % → 33 %. How many ratings per variant?
const n = sampleSizePerArm(0.30, 0.33);
console.log("per variant:", n);

// 3. You collect 300 ratings a day, split between the two variants.
console.log("days needed:", Math.ceil((2 * n) / 300));
```

**Python**

```python
# ex2.py — read an A/B result, then plan the next one
import math

from abtest import two_proportion_test, sample_size_per_arm

# 1. Last week: A got 120 thumbs-up from 400 ratings; B got 150 from 400.
t = two_proportion_test(120, 400, 150, 400)
print(f"A {t['p_a']}  B {t['p_b']}  diff {t['diff']:.3f}  z {t['z']:.3f}  p {t['p_value']:.4f}")
print(f"95% CI [{t['ci95'][0]:.3f}, {t['ci95'][1]:.3f}]")

# 2. Next test: you hope for 30 % -> 33 %. How many ratings per variant?
n = sample_size_per_arm(0.30, 0.33)
print("per variant:", n)

# 3. You collect 300 ratings a day, split between the two variants.
print("days needed:", math.ceil(2 * n / 300))
```

Expected output (both languages):

```
A 0.3  B 0.375  diff 0.075  z 2.243  p 0.0249
95% CI [0.010, 0.140]
per variant: 3760
days needed: 26
```

**Reading it.** p = 0.025 is below 0.05, so the gap is unlikely to be pure luck. But the
interval runs from 1 to 14 points. The lift could be tiny. If B costs more, you might run
longer to narrow the interval before shipping. For part 3, 26 days means **four calendar
weeks**: round up to whole weeks, so each weekday appears equally often (§3.8).
</details>

---

### Exercise 3 — Break it five ways ●●●○○

Predict, then run. Use 1,000 or 10,000 users, as in the code.

1. Assign the variant with a fresh coin flip on every request. Each user visits 5 times. How
   many users see both variants?
2. Peek at an A/A test every 100 ratings and stop at the first p < 0.05 (§4.5).
3. Accept feedback without a run id. Join it to "the user's latest run". Each user has two
   runs and rates one of them.
4. Store a comment containing a phone number and an email, with and without `redact`.
5. Hash the user id **without** the experiment name. How many B users are in B for two
   different experiments?

<details>
<summary>✅ Solution</summary>

| # | Symptom (measured) | Why |
|---|---|---|
| 1 | **930 of 1,000** users saw both variants (theory: 1 − 2 × 0.5⁵ = 93.75 %); sticky hash: 0 | Each request is a new draw. Thumbs can't be credited to one version. |
| 2 | **22.1 %** false winners with 20 looks, against 4.1 % with one look | Each look is another chance for luck to cross 0.05. |
| 3 | **506 of 1,000** thumbs attached to the wrong answer | "Latest" is a guess. It is right only when the user rated the last answer. |
| 4 | The raw comment keeps `+44 7700 900123` and `sam.lee@example.com`; redacted: `[phone]`, `[email]` | Comments are free text. Users type anything into them. |
| 5 | Unsalted: **4,987 of 4,987** B users in B for both; salted: 2,531 of 4,951 | Without the salt, every experiment reuses one split. Effects pile onto the same users. |

**JavaScript** (`breakit.mjs`; #2 is `peeking.mjs` from §4.5)

```js
// breakit.mjs — run with: node breakit.mjs
import { createHash } from "node:crypto";
import { assignVariant, makeRng } from "./abtest.mjs";
import { redact } from "./feedback.mjs";

const rng = makeRng(39);
const users = Array.from({ length: 10000 }, (_, i) => `u${String(i + 1).padStart(5, "0")}`);

// 1 — Not sticky: a fresh coin flip on every request.
let sawBoth = 0;
for (const u of users.slice(0, 1000)) {
  const seen = new Set();
  for (let visit = 0; visit < 5; visit++) seen.add(rng() < 0.5 ? "A" : "B");
  if (seen.size === 2) sawBoth++;
}
const stickyBoth = users.slice(0, 1000)
  .filter((u) => new Set([1, 2, 3, 4, 5].map(() => assignVariant(u, "exp-1"))).size === 2).length;
console.log(`1 coin flip per request: ${sawBoth} of 1000 users saw BOTH variants (sticky: ${stickyBoth})`);

// 3 — Feedback with no run id: the server guesses "the user's latest run".
let wrong = 0;
for (const u of users.slice(0, 1000)) {
  const runs = [`${u}-run1`, `${u}-run2`];          // two answers, close together
  const rated = runs[rng() < 0.5 ? 0 : 1];          // the student rates ONE of them
  const guessed = runs[runs.length - 1];            // the join picks the latest
  if (guessed !== rated) wrong++;
}
console.log(`3 join by "latest run": ${wrong} of 1000 thumbs attached to the WRONG answer`);

// 4 — PII in feedback.
const comment = "Wrong again. Call me on +44 7700 900123 or mail sam.lee@example.com";
console.log("4 raw:     ", comment);
console.log("4 redacted:", redact(comment));

// 5 — No experiment name in the hash: every experiment gets the SAME B group.
const unsalted = (u) => (parseInt(createHash("sha256").update(u).digest("hex").slice(0, 8), 16) % 100 < 50 ? "B" : "A");
const bothB = (f) => users.filter((u) => f(u, "exp-1") === "B" && f(u, "exp-2") === "B").length;
const inB = users.filter((u) => unsalted(u) === "B").length;
console.log(`5 unsalted: ${bothB((u) => unsalted(u))} of ${inB} B-users are in B for BOTH experiments`);
const inB1 = users.filter((u) => assignVariant(u, "exp-1") === "B").length;
console.log(`5 salted:   ${bothB(assignVariant)} of ${inB1} B-users are in B for both`);
```

**Python** (`breakit.py`; #2 is `peeking.py` from §5.5)

```python
# breakit.py — run with: python breakit.py
import hashlib

from abtest import assign_variant, make_rng
from feedback import redact

rng = make_rng(39)
users = [f"u{i:05d}" for i in range(1, 10001)]

# 1 — Not sticky: a fresh coin flip on every request.
saw_both = 0
for u in users[:1000]:
    seen = {"A" if rng() < 0.5 else "B" for _ in range(5)}
    saw_both += len(seen) == 2
sticky_both = sum(len({assign_variant(u, "exp-1") for _ in range(5)}) == 2 for u in users[:1000])
print(f"1 coin flip per request: {saw_both} of 1000 users saw BOTH variants (sticky: {sticky_both})")

# 3 — Feedback with no run id: the server guesses "the user's latest run".
wrong = 0
for u in users[:1000]:
    runs = [f"{u}-run1", f"{u}-run2"]          # two answers, close together
    rated = runs[0 if rng() < 0.5 else 1]      # the student rates ONE of them
    guessed = runs[-1]                         # the join picks the latest
    wrong += guessed != rated
print(f'3 join by "latest run": {wrong} of 1000 thumbs attached to the WRONG answer')

# 4 — PII in feedback.
comment = "Wrong again. Call me on +44 7700 900123 or mail sam.lee@example.com"
print("4 raw:     ", comment)
print("4 redacted:", redact(comment))


# 5 — No experiment name in the hash: every experiment gets the SAME B group.
def unsalted(u, _experiment=None):
    return "B" if int(hashlib.sha256(u.encode()).hexdigest()[:8], 16) % 100 < 50 else "A"


def both_b(f):
    return sum(f(u, "exp-1") == "B" and f(u, "exp-2") == "B" for u in users)


in_b = sum(unsalted(u) == "B" for u in users)
print(f"5 unsalted: {both_b(unsalted)} of {in_b} B-users are in B for BOTH experiments")
in_b1 = sum(assign_variant(u, "exp-1") == "B" for u in users)
print(f"5 salted:   {both_b(assign_variant)} of {in_b1} B-users are in B for both")
```

Expected output (both languages):

```
1 coin flip per request: 930 of 1000 users saw BOTH variants (sticky: 0)
3 join by "latest run": 506 of 1000 thumbs attached to the WRONG answer
4 raw:      Wrong again. Call me on +44 7700 900123 or mail sam.lee@example.com
4 redacted: Wrong again. Call me on [phone] or mail [email]
5 unsalted: 4987 of 4987 B-users are in B for BOTH experiments
5 salted:   2531 of 4951 B-users are in B for both
```

**The lesson.** None of these five bugs raises an error. Each one quietly produces numbers
that look fine and mean nothing. That is why the checks in Exercise 1 belong in your test
suite.
</details>

---

### Exercise 4 — Design review: patterns and regulation ●●●○○

StudyBuddy now has four features. For each one, decide:

- the **EU AI Act tier** it most likely falls in, and why;
- the **two UX patterns** from §3.1 it needs most;
- **one guardrail metric** for its next A/B test.

```
   F1  Homework chat: explains topics, cites the student's notes
   F2  Essay checker: says "ready to submit" or "needs work" before students hand in
   F3  Practice quiz generator: writes quiz questions from the notes
   F4  Exam proctor: watches the webcam during a school's online test and flags cheating
```

<details>
<summary>✅ Solution</summary>

| Feature | Likely tier (not legal advice) | Patterns it needs most | Guardrail |
|---|---|---|---|
| F1 Homework chat | **Transparency** (Art. 50(1)): tell students it's an AI | show sources; human handoff to a teacher | refusal rate, p95 latency |
| F2 Essay checker | **Depends on use.** As private study help, usually transparency. If a school uses it to grade or steer learning, it fits Annex III point 3(b) → **high risk** (duties from 2 Dec 2027) | show uncertainty ("based on the rubric, not a grade"); edit/override by the teacher | the true-positive-rate gap between groups (§3.10) |
| F3 Quiz generator | **Transparency**, and possibly marking of generated text (Art. 50(2)); check current guidance | edit/regenerate each question; set expectations ("check answers") | share of questions edited or deleted by teachers |
| F4 Exam proctor | **High risk** — Annex III point 3(d): "monitoring and detecting prohibited behaviour of students during tests". Emotion recognition in schools is banned outright. | human review of every flag before any action; clear notice to students | false-flag rate per group of students |

**Why this design.** The tier follows the **use**. F1 and F2 can use the same model. The
moment F2's verdict feeds a grade, the duties change completely. A good design review notes
that line and puts a human decision on the right side of it. For anything near the high-risk
line, the next step is a lawyer, not a blog post.
</details>

---

### Exercise 5 — 🎯 StudyBuddy v7.3: a feedback loop and a prompt A/B test ●●●●○

Start from StudyBuddy v7.0 (Day 36's front door). Its tutor feature now gets two prompts:
**direct-v1** (A) and **socratic-v1** (B). Build the loop end to end, keyless:

1. Every answer goes through `ask()` (§4.1 / §5.1), so it is logged with its run id and
   variant.
2. Simulate 3,000 students. About 3 in 10 press a thumb. Some press Regenerate. Use these
   illustrative behaviours: A is liked 55 % and regenerated 8 %; B is liked 65 % and
   regenerated 14 %.
3. Post every signal through `addFeedback` / `add_feedback`, with the run id.
4. Analyse **from the log only**: thumbs-up rate per variant (primary), regenerate rate
   (guardrail), words per answer. Run the z-test on both.
5. Count the eval cases the thumbs-downs produced.
6. Write a three-line decision for the product team.

<details>
<summary>✅ Solution</summary>

**JavaScript** (`studybuddy-experiment.mjs`)

```js
// studybuddy-experiment.mjs — the full loop: answer → log → feedback → analyse → eval cases.
import { ask } from "./tutor.mjs";
import { FeedbackLog } from "./feedback.mjs";
import { makeRng, twoProportionTest } from "./abtest.mjs";

const log = new FeedbackLog();           // memory only for the exercise
const rng = makeRng(39);
// How simulated students react (ILLUSTRATIVE): socratic B is liked more but regenerated more.
const BEHAVIOUR = { A: { up: 0.55, regenerate: 0.08 }, B: { up: 0.65, regenerate: 0.14 } };
const fmtP = (p) => (p < 0.0001 ? "< 0.0001" : p.toFixed(4));

for (let i = 1; i <= 3000; i++) {
  const user = `s${String(i).padStart(4, "0")}`;
  const r = await ask(user, "What is photosynthesis?", log);
  const b = BEHAVIOUR[r.variant];
  const [rRated, rUp, rRegen] = [rng(), rng(), rng()];
  if (rRated < 0.3) log.addFeedback({ runId: r.runId, kind: "thumbs", value: rUp < b.up ? 1 : -1 });
  if (rRegen < b.regenerate) log.addFeedback({ runId: r.runId, kind: "regenerate" });
}

// Analyse FROM THE LOG: every feedback row finds its run, and so its variant.
const m = {};
for (const v of ["A", "B"]) m[v] = { runs: 0, rated: 0, up: 0, regenerated: 0, words: 0 };
for (const run of log.runs.values()) {
  m[run.variant].runs++;
  m[run.variant].words += run.answer.split(/\s+/).length;
}
for (const f of log.feedback) {
  const v = log.runs.get(f.runId).variant;
  if (f.kind === "thumbs") { m[v].rated++; if (f.value === 1) m[v].up++; }
  if (f.kind === "regenerate") m[v].regenerated++;
}
for (const v of ["A", "B"]) {
  const x = m[v];
  console.log(v, `runs ${x.runs}  thumbs-up ${x.up}/${x.rated} = ${(x.up / x.rated).toFixed(3)}`
    + `  regenerate ${(x.regenerated / x.runs).toFixed(3)}  words/answer ${(x.words / x.runs).toFixed(1)}`);
}
const t = twoProportionTest(m.A.up, m.A.rated, m.B.up, m.B.rated);
console.log(`thumbs-up diff ${t.diff.toFixed(3)}, p ${fmtP(t.pValue)}, 95% CI [${t.ci95.map((x) => x.toFixed(3)).join(", ")}]`);
const g = twoProportionTest(m.A.regenerated, m.A.runs, m.B.regenerated, m.B.runs);
console.log(`regenerate diff ${g.diff.toFixed(3)}, p ${fmtP(g.pValue)}  (guardrail)`);
console.log("eval cases from thumbs-down:", log.evalCases().length);
```

**Python** (`studybuddy_experiment.py`)

```python
# studybuddy_experiment.py — the full loop: answer -> log -> feedback -> analyse -> eval cases.
from abtest import make_rng, two_proportion_test
from feedback import FeedbackLog
from tutor import ask

log = FeedbackLog()  # memory only for the exercise
rng = make_rng(39)
# How simulated students react (ILLUSTRATIVE): socratic B is liked more but regenerated more.
BEHAVIOUR = {"A": {"up": 0.55, "regenerate": 0.08}, "B": {"up": 0.65, "regenerate": 0.14}}


def fmt_p(p):
    return "< 0.0001" if p < 0.0001 else f"{p:.4f}"


for i in range(1, 3001):
    r = ask(f"s{i:04d}", "What is photosynthesis?", log)
    b = BEHAVIOUR[r["variant"]]
    r_rated, r_up, r_regen = rng(), rng(), rng()
    if r_rated < 0.3:
        log.add_feedback(r["run_id"], "thumbs", 1 if r_up < b["up"] else -1)
    if r_regen < b["regenerate"]:
        log.add_feedback(r["run_id"], "regenerate")

# Analyse FROM THE LOG: every feedback row finds its run, and so its variant.
m = {v: {"runs": 0, "rated": 0, "up": 0, "regenerated": 0, "words": 0} for v in "AB"}
for run in log.runs.values():
    m[run["variant"]]["runs"] += 1
    m[run["variant"]]["words"] += len(run["answer"].split())
for f in log.feedback:
    v = log.runs[f["run_id"]]["variant"]
    if f["kind"] == "thumbs":
        m[v]["rated"] += 1
        m[v]["up"] += f["value"] == 1
    if f["kind"] == "regenerate":
        m[v]["regenerated"] += 1
for v, x in m.items():
    print(v, f"runs {x['runs']}  thumbs-up {x['up']}/{x['rated']} = {x['up'] / x['rated']:.3f}"
             f"  regenerate {x['regenerated'] / x['runs']:.3f}  words/answer {x['words'] / x['runs']:.1f}")
t = two_proportion_test(m["A"]["up"], m["A"]["rated"], m["B"]["up"], m["B"]["rated"])
print(f"thumbs-up diff {t['diff']:.3f}, p {fmt_p(t['p_value'])}, 95% CI [{t['ci95'][0]:.3f}, {t['ci95'][1]:.3f}]")
g = two_proportion_test(m["A"]["regenerated"], m["A"]["runs"], m["B"]["regenerated"], m["B"]["runs"])
print(f"regenerate diff {g['diff']:.3f}, p {fmt_p(g['p_value'])}  (guardrail)")
print("eval cases from thumbs-down:", len(log.eval_cases()))
```

Expected output (both languages; about 5 s in Node and 17 s in Python here):

```
A runs 1544  thumbs-up 245/486 = 0.504  regenerate 0.071  words/answer 12.0
B runs 1456  thumbs-up 290/437 = 0.664  regenerate 0.147  words/answer 15.0
thumbs-up diff 0.160, p < 0.0001, 95% CI [0.097, 0.222]
regenerate diff 0.076, p < 0.0001  (guardrail)
eval cases from thumbs-down: 388
```

**The decision, in three lines:**

```
   Socratic (B) raises thumbs-up from 50 % to 66 % (95 % CI +10 to +22 points, p < 0.0001).
   But students press Regenerate twice as often (7 % → 15 %): many want a direct answer too.
   Next: a B2 that asks one question, then gives the answer if the student is stuck; re-test.
```

**Why this design.**

- The analysis reads **only the log**. Each feedback row finds its variant through its run
  id. If the run id were missing, step 4 would be impossible. That's Exercise 3 #3 in real
  life.
- The planted lift was 10 points. The test measured 16, and the interval still contains 10.
  One test is one noisy draw.
- 388 thumbs-down runs are now eval-case candidates, tagged by prompt version. After a human
  check (Day 32), the best of them join Day 25's offline suite. B2 must pass them before it
  earns the next A/B test.
- Swap `FakeTutor` for `ChatGroq` (`openai/gpt-oss-120b`) and real students. The loop,
  the log and the maths stay the same.
</details>

---

## 9. Interview questions

### Basic

**Q1. Name four UX patterns that make an AI feature more trustworthy, and the problem each
solves.**

- **Citations** solve "where did it get that?" — users can check the source.
- **Streaming** solves the blank screen. Users see progress and can stop a bad answer early.
- **Edit/regenerate/undo** stop a wrong answer from being a dead end.
- **Honest refusals with a next step, plus human handoff**, solve "I'm stuck and it won't
  help".

Add **AI disclosure** to set expectations. In the EU it is also a legal duty for chatbots.

---

**Q2. What's the difference between explicit and implicit feedback? Give examples.**

Explicit feedback is given on purpose: thumbs, stars, comments. It is clear but rare, and
biased toward users with strong feelings. Implicit feedback is read from behaviour: copying,
editing, regenerating, re-asking, leaving mid-answer. It is plentiful but ambiguous. A copy can
mean "great" or "I'll fix this myself". Use explicit feedback as the primary metric and
implicit feedback as guardrails. Treat edits as free reference answers.

---

**Q3. Why must feedback carry a run id?**

Without it you can't tell which answer, prompt version, model or variant the feedback is
about. Guessing from "the user's latest run" was wrong for 506 of 1,000 thumbs in our test.
With the id, a thumbs-down joins to the full trace. It can become an eval case tagged with the
exact prompt version. Choose the id yourself and pass it as the root `runId` / `run_id`. Then
the trace, the response and the feedback share one key.

---

**Q4. How do you assign users to A/B variants?**

Hash `experiment-name + user-id` (for example SHA-256), take a number from the hash, and use
`% 100` to get a bucket. Buckets below the ramp percentage get B. It is random-like, sticky,
and needs no storage. Every server and language computes the same answer. The experiment name
gives each experiment an independent split. Without it, the same users land in B every time.

---

**Q5. What is a guardrail metric?**

A number that must not get worse while you improve the primary metric. Typical ones are p95
latency, cost or tokens per answer, refusal rate, error rate and escalations to humans. You set
the limits before the test. A variant that wins on the primary metric but breaks a guardrail
doesn't ship. In our simulation, B won on thumbs-up but nearly doubled refusals.

### Intermediate

**Q6. Walk me through a two-proportion z-test.**

Pool the two groups to get the rate you'd expect if they were the same: `p = (s₁+s₂)/(n₁+n₂)`.
The standard error is `√(p(1−p)(1/n₁+1/n₂))`. Then `z = (p₂−p₁)/SE`. The two-sided p-value
is `2(1−Φ(|z|))`. With 300/500 vs 345/500 you get z = 2.97 and p = 0.003. Report the 95 %
interval of the gap too, [3.1, 14.9] points, because the p-value says nothing about size. The
test needs independent units, enough data per cell, and one planned look.

---

**Q7. How many users do you need for an A/B test?**

Use the standard formula:
`n per arm = (z_α/2 + z_β)² (p₁(1−p₁)+p₂(1−p₂)) / (p₂−p₁)²`. With 5 % significance and
80 % power, 60 %→63 % needs 4,126 ratings per arm, but 60 %→61 % needs 37,511. Halving the
effect roughly quadruples the sample. Divide by the share of users who rate: at 30 %, 4,126
ratings per arm is about 27,500 users. Round the duration up to whole weeks.

---

**Q8. What is peeking and why is it a problem?**

Checking significance repeatedly and stopping at the first p < 0.05. Each look is another
chance for noise to cross the line. In 1,000 simulated A/A tests, peeking every 100 ratings
produced 22.1 % false winners instead of about 5 %. Fixes: a fixed horizon with one look, or a
sequential method built for repeated looks.

---

**Q9. Offline evals and online A/B tests — when do you use each?**

Offline evals use a fixed dataset with references. They run in CI in minutes and catch
regressions before users see them. Online tests measure what real users prefer and what it
costs, which no dataset can predict. Use both, in order: a change must pass offline evals to
earn an A/B test. Online failures, such as thumbs-downs and edits, feed back into the offline
dataset.

---

**Q10. How would you check an AI feature for fairness?**

Pick the groups and the outcome. Compare **selection rates** (the four-fifths rule of thumb
flags a ratio below 0.8). If you have ground truth, compare **error rates**, such as the
true-positive rate. That separates "the groups differ" from "the model treats equal work
differently". Test whether the gaps exceed chance, with the same two-proportion test. In our
example, the ratio was 0.773 and the true-positive-rate gap was 17 points (p = 0.002). Then
read the failures to find the cause. Collect group data only with consent, and re-run the check
after every prompt or model change.

### Advanced

**Q11. Your prompt change shows +3 points thumbs-up after two days, p = 0.04. The PM wants
to ship. What do you say?**

Three concerns. **Peeking**: was two days the planned sample? If not, the 5 % false-alarm
promise doesn't hold. Our simulation showed 22 % with repeated looks. **Novelty**: two days
measures curiosity. Run at least one full week and compare week one with week two. **Size and
guardrails**: a 3-point lift needs about 4,000 ratings per arm to detect reliably. Check the
interval, and check cost, latency and refusals. Then: finish the planned sample, and decide on
the primary metric plus guardrails.

---

**Q12. Design the feedback pipeline for an LLM product.**

The server creates the run id, passes it as the root run id, and returns it with the answer.
The client sends explicit signals (thumbs, ratings, comments) and implicit ones (copy, edit,
regenerate, abandon) to `POST /feedback` with that id. The server validates the id and the
values, redacts PII, pseudonymises the user and appends to a log with a retention period.
Optionally it forwards to the tracing tool (`createFeedback`). A job joins feedback to runs
and computes online metrics per prompt version and variant. Thumbs-downs and edits become
eval-case candidates, which a human reviews before they join the offline suite. Watch for
rater bias and feedback loops.

---

**Q13. What does the EU AI Act mean for a typical LLM chatbot product?**

Not legal advice — it depends on the exact use. Most LLM apps fall under the transparency
tier. Article 50 duties apply from 2 August 2026: tell users they are talking to an AI, and
mark or disclose generated content in the cases the Act lists. Article 4 asks you to support
staff AI literacy. Risk depends on the **use**. Grading students, admissions, hiring or credit
are Annex III high-risk uses. The 2026 Digital Omnibus moved those duties to 2 December 2027.
They include risk management, data governance, logging, documentation and human oversight.
Rules for general-purpose models (from August 2025) mainly bind the model makers. Classify each
feature, and check current guidance with a lawyer.

---

**Q14. Your A/B test shows a "significant" difference in an A/A test. What could be wrong?**

An A/A test should come out significant only about 5 % of the time. If it fails often, the
pipeline is broken. Suspects:

- **Peeking**, or many metrics tested at once.
- **Non-independent units**: per-rating analysis with heavy raters.
- **Sample ratio mismatch**: the split isn't 50/50 as planned, because of a bug in assignment
  or in logging.
- **Leaky assignment**: users see both variants.
- **Logging differences**: one variant drops events.

Run A/A tests regularly as a health check on the experiment system itself.

---

## 10. Recap

### What you learned

- ✅ Trust is designed: **sources, streaming, edit/undo/regenerate, honest refusals, handoff,
  AI disclosure**
- ✅ **Choose the run id yourself** and pass it as `runId` / `run_id`. It becomes the root run,
  so the trace, the response and the feedback share one key
- ✅ **Explicit** feedback is clear but rare; **implicit** feedback is plentiful but noisy;
  **edits** are free reference answers
- ✅ Bad runs → **eval cases** tagged with prompt version and variant, checked by a human
- ✅ **Sticky, salted hash assignment**: same user, same variant, any server; ramp by moving
  the threshold
- ✅ The **two-proportion z-test** by hand, plus the 95 % interval; same numbers in JS and
  Python
- ✅ **Sample size** grows with 1 / lift²; **peeking** turned 5 % false alarms into 22.1 %
- ✅ One **primary metric**, several **guardrails**: B can win and still not ship
- ✅ **Fairness**: compare selection rates *and* error rates across groups; collect group data
  with consent
- ✅ **EU AI Act**: four tiers; Article 50 transparency from 2 Aug 2026; Annex III high-risk
  (including education) from 2 Dec 2027 — not legal advice

### The product checklist

```
   □ every answer has a run id, sources and an AI disclosure
   □ thumbs + edit + regenerate on each answer, all tied to the run id
   □ feedback validated, redacted, pseudonymised, with a retention period
   □ thumbs-downs and edits → reviewed eval cases → the offline suite
   □ offline evals pass BEFORE any A/B test
   □ hash(experiment:user) assignment; ramp 10 % → 50 %
   □ sample size and primary metric fixed in advance; one look; at least a full week
   □ guardrails: p95 latency, tokens per answer, refusal rate, error rate
   □ fairness check per group after every prompt or model change
   □ each feature classified under the AI Act by its use (and checked by a lawyer)
```

### Tomorrow

**[Day 40 — Final capstone & career](day-40-final-capstone-and-career.md)**: today
StudyBuddy started learning from its students. Tomorrow you put everything from Weeks 1–6
together. You build one end-to-end project that is traced, evaluated, secured and measured.
Then you turn it into a portfolio piece and practise the interviews that ask about it.

### Quick self-check

1. Why does adding the experiment name to the hash matter, if the split is 50/50 either way?
2. B beats A on thumbs-up with p = 0.01, but B's p95 latency is 1.6× A's and your limit is
   1.25×. What do you do?
3. A homework-help chatbot and an exam-grading tool use the same model. Why can they fall in
   different EU AI Act tiers?

<details>
<summary>Answers</summary>

1. Without the salt, every experiment uses the **same** split: the same users are in B every
   time (4,987 of 4,987 in our test). Those users get every new feature at once, so their
   effects mix. Some users are always the guinea pigs. With the salt, each experiment's split
   is independent (about half overlap, as chance predicts).

2. Don't ship. A guardrail failed, so B has not won, whatever the primary metric says. Find out
   why it is slower (a longer prompt? more tool calls?), fix it, check the fix offline, and run
   a new test. Don't stretch the guardrail after seeing the result. Limits are set before the
   test, for exactly this moment.

3. The Act classifies by **use**, not by model. Homework help is usually a transparency case
   (Article 50: tell users it's an AI). Evaluating learning outcomes in education is listed in
   Annex III point 3, so the grading tool is high-risk, with heavier duties from 2 December
   2027. Not legal advice; check current rules.
</details>

---

<div align="center">

**[← Day 38 — Emerging agents](day-38-emerging-agents.md)** · **[Week 6 index](README.md)** · **[Day 40 — Final capstone & career →](day-40-final-capstone-and-career.md)**

</div>
