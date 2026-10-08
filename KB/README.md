# Knowledge Base — how to work on this book

Everything a fresh session needs to update this book correctly. Start here, then open the file
you need.

| File | What it answers |
|---|---|
| [01-conventions.md](01-conventions.md) | How a day is structured and written — template, style, code rules, exercise and interview formats |
| [02-content-map.md](02-content-map.md) | What's in every file, which are generated, how days depend on each other |
| [03-verified-findings.md](03-verified-findings.md) | Every library behaviour verified by running it, with the JS↔Python differences. **Read before changing any technical claim.** |
| [04-versions-and-environment.md](04-versions-and-environment.md) | Exact package versions the book was verified against, and how to rebuild the sandbox |
| [05-verification-playbook.md](05-verification-playbook.md) | The scripts in `tools/`, what they check, and how to verify a new claim |
| [06-maintenance-backlog.md](06-maintenance-backlog.md) | Known gaps, deliberate omissions, and the upgrade watchlist |
| [07-course-expansion-plan.md](07-course-expansion-plan.md) | The approved plan that turned the book into a full AI Engineering course, with progress |

**Current state (October 2026):** a **43-day AI Engineering course** — Week 0 (Days 0A–0C) plus
Days 1–40 · 100,070 lines across the day files (114,018 in the repo, 69 markdown files) · 0 broken
links · 587 interview questions · 308 glossary terms · mean reading ease (Flesch) 70, every day ≥ 61.
How it grew from the 28-day book, and why, is in [07-course-expansion-plan.md](07-course-expansion-plan.md).

`python tools/verify.py .` prints these numbers and ends with `no problems found`. Day 17 used to
show `E2:no-PY`, a known false positive (see [05](05-verification-playbook.md)).

---

## Resume recipes

### A. "Library X changed — update the book"

1. Read [03-verified-findings.md](03-verified-findings.md) for what was previously true, and
   [04](04-versions-and-environment.md) for the version it was true at.
2. Rebuild the sandbox (recipe in 04) with the **new** version.
3. Re-run the probe for that behaviour. Scripts live in `tools/`; probes are written fresh per
   session in the scratchpad (they're deliberately not committed — they're throwaway).
4. If behaviour changed: update the day's prose **and** its `§ Common mistakes`, translation
   table, recap bullets, the week README's blockers table, and the finding's row in 03.
5. `python tools/gen_resources.py .` to refresh the generated reference files.
6. `python tools/verify.py .` — expect `no problems found`.

### B. "Add or rewrite a day"

1. Read [01-conventions.md](01-conventions.md) and skim a nearby day for voice.
2. Verify every API you intend to show (recipe A, steps 2–3). Keep the real outputs — the book
   quotes them.
3. Write the day in two passes: sections 1–6, then 7–10 appended. Large single writes are
   fine with the Write tool; heredocs are not (see CONTRIBUTING.md).
4. Wire it up: week README row and through-line, master README calendar row, the previous day's
   "Tomorrow" link, glossary terms, and `tools/gen_resources.py`.
5. Verify (recipe A, steps 5–6).

### C. "Fix a claim that's wrong"

1. Reproduce it in the sandbox first — the book's claims are measurements, so a correction needs
   a measurement.
2. Grep for the claim everywhere; claims repeat across a day's §3 (first principles), §7
   (mistakes), §9 (interviews), §10 (recap), the week README, and sometimes `resources/`:
   ```bash
   grep -rn "the phrase" --include=*.md .
   ```
3. Fix every occurrence, regenerate, verify. Add the corrected behaviour to 03 with its date.

### D. "Regenerate the reference files"

```bash
python tools/gen_resources.py .     # mapping, interview bank, troubleshooting
python tools/sort_glossary.py resources/glossary.md
python tools/verify.py .
```

`resources/cheatsheet-lcel.md`, `cheatsheet-langgraph.md`, `cheatsheet-rag-patterns.md`,
`capstone-projects.md` and `glossary.md` are **hand-written** — edit them directly.

### E. "Add glossary terms for new content"

Entries are `**Term** *(Day NN)* — one-sentence definition.`, alphabetical within `## X`
sections. Add them, then run `python tools/sort_glossary.py resources/glossary.md` (it asserts
the entry count doesn't change).

---

## Invariants a change must not break

- Every day: words box, 10 numbered sections, both languages, 5 exercises, bilingual solutions, footer nav.
- Prose edits never change code (`tools/check_code_unchanged.py`); reading ease stays ≥ 60 (`tools/readability.py`).
- Every technical claim traceable to something that was run (03 is the ledger).
- 0 broken relative links; no `*coming next*` left in the master README.
- Generated files never hand-edited.
- `resources/interview-bank.md` question count matches the day files (verify.py prints both).
