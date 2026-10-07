# CLAUDE.md — working on this repository

This repo is a **28-day textbook** teaching LangChain and LangGraph in **both JavaScript and
Python**: `week-01-foundations/` … `week-04-production-projects-and-interviews/`, plus
`resources/`. It is **documentation only** — no application code ships here, so "building" means
writing and verifying markdown.

**Read `KB/README.md` first.** It is the handoff knowledge base: conventions, what every file
contains, every behaviour already verified, pinned versions, and the verification scripts.

---

## The five rules that matter

1. **Verify before you write.** Never describe library behaviour from memory. Install the
   package in the scratchpad sandbox, run the snippet, and quote the real output or error.
   This caught several errors that would otherwise have shipped — see
   `KB/03-verified-findings.md`. If something can't be verified, say so in the text
   ("not executed", "check your version") rather than asserting it.
2. **Both languages, same example.** Every concept appears in JavaScript *and* Python, teaching
   the same example, with a translation table per day. Exercise solutions are bilingual too.
3. **Follow the day template exactly** — 10 numbered sections, 5 exercises, interview questions,
   recap. See `KB/01-conventions.md`.
4. **No invented numbers.** Measured values only. Illustrative examples must be labelled as
   illustrative.
5. **Don't hand-edit generated files.** `resources/js-vs-python-mapping.md`,
   `resources/interview-bank.md` and `resources/troubleshooting.md` are produced by
   `tools/gen_resources.py` from the day files. Edit the source day, then regenerate.

## Verify your work

```bash
python tools/verify.py .        # links, 10-section structure, language parity, exercises, stats
```

Expect `no problems found`, 0 broken links, and 28 day files. Day 17's Exercise 2 may be
flagged `E2:no-PY` — a known false positive (that exercise's code emits `<details>` markup,
which truncates the parser's split). Anything else is real.

## Environment notes (Windows, this machine)

- **Long heredocs break this shell.** Write scripts and large files with the Write tool, then
  run them — don't pipe multi-hundred-line heredocs through Bash.
- Always `cd "<abs path>" || exit 1` — the sandbox directory is periodically cleared, and a
  silent `cd` failure once ran `npm install` in the repo root by mistake.
- Python needs `PYTHONIOENCODING=utf-8` (and sometimes `PYTHONUTF8=1`) for emoji output.
- Rebuild the throwaway sandbox with the recipe in `KB/04-versions-and-environment.md`; never
  install packages into the repo itself.

## House style

- Prose explains *why* before *how*; mechanisms and trade-offs over feature lists.
- Lines wrap at roughly 100 characters.
- Free-first providers (Groq / Gemini / Ollama) in the main path; paid alternates inside a
  collapsed `<details>`.
- Each day removes a problem the previous day created — keep that through-line, and keep the
  running project (StudyBuddy) evolving.
