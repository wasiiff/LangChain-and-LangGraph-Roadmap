# 01 — Conventions

How every day in this book is structured and written. Match this exactly; readers rely on the
shape being identical from Day 1 to Day 28.

---

## The day file

Filename: `week-0N-<slug>/day-NN-<kebab-topic>.md`, zero-padded so files sort. Week 0 uses
`day-00a-…`, `day-00b-…`, `day-00c-…` and the header label `Day 0A` (tools accept `0A`–`0C`).

### Header

```markdown
# Day 24 — Reliability: Surviving a Bad Day in Production

> ⏱ **Time:** ~3 hours · 🎯 **Prereqs:** [Day 23](day-23-streaming-and-events.md) · 🧩 **Difficulty:** ●●●●○

**Today you learn:** 2–4 short sentences: the problem first, then what gets built.

> 📖 **Words you'll meet today**
>
> - **Term** — one plain sentence.
```

The **words box** (5–8 terms) sits directly after "Today you learn", before the first `---`.
Under every `### 3.x` heading, the first line is `> 💬 **In plain words:** …` (1–2 sentences).

Difficulty is five dots, filled to taste (`●●●○○`). Time is 2.5–3 hours for most days.

### The ten sections

| # | Heading | Contains |
|---|---|---|
| 1 | `## 1. The problem` | A concrete failure the reader can picture, usually as a log or transcript, then **"### The real-life version"** — a non-technical analogy (USB, airline, restaurant, flight recorder). No API names yet. |
| 2 | `## 2. Mental model` | ASCII diagram plus a table. The reader should be able to explain the idea after this section without having seen code. |
| 3 | `## 3. First principles` | Numbered subsections (`### 3.1 …`). How it actually works, with **verified outputs quoted**. The intellectual core. |
| 4 | `## 4. Code — JavaScript` | Progressive subsections building one example. Runnable snippets, free-first provider, comments that teach. |
| 5 | `## 5. Code — Python` | The **same** example, same subsection structure, ending with `### 5.N The JS ↔ Python translation for today` (a table). |
| 6 | `## 6. Under the hood` | Why the library behaves this way — execution model, cost model, trade-offs. |
| 7 | `## 7. Common mistakes` | `### ❌ N. Title` entries, each with ❌ wrong / ✅ right code and the real symptom. Prefer verified symptoms. |
| 8 | `## 8. Exercises` | Exactly 5, increasing difficulty, each with a collapsed bilingual solution. |
| 9 | `## 9. Interview questions` | Grouped `### Basic` / `### Intermediate` / `### Advanced`. |
| 10 | `## 10. Recap` | ✅ bullets, a one-glance summary block, **### Tomorrow** (link + what problem it solves), **### Quick self-check** (3 questions, answers in `<details>`). |

Footer, on every day:

```markdown
<div align="center">

**[← Day 23 — Streaming](day-23-streaming-and-events.md)** · **[Week 4 index](README.md)** · **[Day 25 — Observability →](day-25-observability-and-evaluation.md)**

</div>
```

### Exercises

- Difficulty dots on each (`●●○○○`), rising across the five.
- Exercise 1 is usually a *prove-it-to-yourself* probe that needs no API key.
- One exercise per day is **"Break it N ways"**: predict, run, then a table of symptom → why,
  with verified error text. These are the most-praised parts of the book — keep them.
- The last exercise is a 🎯/🏆 project (the week project in Weeks 1–3) or a design review.
- Solutions live in `<details><summary>✅ Solution</summary>` and contain **both** languages,
  the expected output, and a short "why this design" note.
- Analysis-only exercises (classification tables, design reviews) legitimately have no code.

### Interview questions — two formats exist

- **Days 1–16:** collapsed blocks — `<details><summary><b>Q: …</b></summary>` + answer.
- **Days 17–40 and Week 0:** open format — `**Q1. …**` then the answer, separated by `---`.
  (Day 03 keeps the collapsed format of Days 1–16.)

Match the local file's format when editing. `tools/gen_resources.py` counts both.

---

## Writing style

- **Why before how.** A reader should know what problem a thing solves before seeing its API.
- **Mechanism, number, trade-off.** Every explanation should land on at least one. Those three
  are also what the book teaches readers to say in interviews (Day 28 §3.5).
- Second person, present tense, plain words. British spelling.
- **Plain English for every reader** (added October 2026 — many readers are beginners or read
  English as a second language): sentences ≤ 25 words where possible and none over 30 in prose;
  define each technical term at first use; no idioms; symbols such as `≫` or `·` become words in
  prose. Target **Flesch ≥ 60** — measure with `python tools/readability.py <file>`.
- **Prose edits never touch code.** After editing the English of an existing day, run
  `python tools/check_code_unchanged.py <file>` — it must print `OK — all code unchanged`.
- Optional per-day callouts: `> 📏 **Measure it:**` (a 3-case check before Day 25's full evals),
  `> 📚 **Sources**` (end of §6, for facts that can't be run), `> 🐍 **Why Python only here:**`
  (Week 5 days where real tooling is Python-only).
- Lines wrap at ~100 characters. Tables and code may exceed it.
- Callouts: `> 📦` package/API note · `> ⚠️` trap · `> 🔒` security · `> 💡` tip · `> 🎯` do this ·
  `> ⏱` timing · `> 🪟` Windows-specific.
- ASCII diagrams in fenced blocks (they render everywhere); mermaid only where GitHub adds
  value, and prefer mermaid **generated by the code** (`drawMermaid()`).
- Never pad. If a section has nothing to add, it's shorter.

## Code rules

- **Markdown only** — no runnable project folders in the repo (a deliberate decision: nothing
  to drift or break).
- Every snippet is real code that was run, or clearly marked as a sketch.
- **Free-first providers:** `ChatGroq` (`openai/gpt-oss-120b`; small model `openai/gpt-oss-20b`)
  as the default, Gemini (`gemini-3.8-flash`, embeddings `gemini-embedding-2`) or Ollama where a
  different capability is needed (Groq has no embeddings). Both GPT-OSS models are **reasoning
  models**: keep `maxTokens` generous (≥ 512) or set `reasoningEffort: "low"`, and don't rely on
  `logprobs`, `n > 1` or text stop-sequence protocols (use `qwen/qwen3.8-27b`, a Groq preview
  model, for those). Paid alternates go in
  a collapsed `<details>💰`.
- **Keyless verification:** from Day 22 on, examples and tests use scripted/fake models
  (`BaseChatModel` subclass in JS, `GenericFakeChatModel` subclass in Python) so a reader with
  no API key can run everything. Preserve that property.
- Imports are canonical and verified (`@langchain/core/messages`, `langchain_core.messages`).
- Quote outputs as comments or in an "Expected output" block, with real values.

## The through-line

Each day exists because the previous day created a problem; the week READMEs state this chain
explicitly, and §1 of each day restates it. The running project, **StudyBuddy**, gains one
capability per phase (see [02-content-map.md](02-content-map.md)). When adding content, say
which problem it removes and what it creates.

## Week README shape

Goal paragraph · at-a-glance table (day, topic, time, difficulty, what you'll build) · total
hours · "What you'll be able to do by Sunday" checklist · the through-line block · version
traps · extra installs · **Common Week N blockers** table (symptom → day → fix; harvested into
`resources/troubleshooting.md`) · interview topics ranked · StudyBuddy evolution · "→ Start
with Day NN".
