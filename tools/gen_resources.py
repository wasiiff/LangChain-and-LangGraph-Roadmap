"""Regenerate the three derived resource files from the day files.

    python tools/gen_resources.py [repo-root]

Writes (never hand-edit these — your edits will be overwritten):
    resources/js-vs-python-mapping.md   each day's JS/Python translation table
    resources/interview-bank.md         each day's section 9, with a counted TOC
    resources/troubleshooting.md        each week README's blockers table + SETUP.md

The curated tables at the top of each output live in this file, in the HEADER_*
constants at the bottom. Edit them there, not in the output.
"""
import glob
import io
import os
import re
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
OUT = os.path.join(ROOT, "resources")

# Short week titles for the generated files; the week READMEs use longer ones.
WEEKS = [
    ("week-01-foundations", "Week 1 — Foundations"),
    ("week-02-data-embeddings-and-rag", "Week 2 — Data, Embeddings, RAG & Memory"),
    ("week-03-tools-agents-and-langgraph", "Week 3 — Tools, Agents & LangGraph"),
    ("week-04-production-projects-and-interviews", "Week 4 — Multi-agent, Production & Interviews"),
]

LINK = re.compile(r"\]\((?!https?:|mailto:|#)([^)\s]+)\)")


def read(path):
    return io.open(path, encoding="utf-8").read()


def write(path, text):
    io.open(path, "w", encoding="utf-8", newline="\n").write(text)
    print(f"wrote {os.path.relpath(path, ROOT)} ({text.count(chr(10))} lines)")


def load_days():
    """[(week_title, [day dicts])] — each day carries its title, text and repo-relative path."""
    weeks = []
    for folder, title in WEEKS:
        days = []
        for path in sorted(glob.glob(os.path.join(ROOT, folder, "day-*.md"))):
            text = read(path)
            h1 = re.search(r"^# Day \d+ — (.+)$", text, re.M)
            days.append({
                "num": int(re.search(r"day-(\d+)", os.path.basename(path)).group(1)),
                "title": h1.group(1).strip(),
                "text": text,
                "dir": os.path.dirname(path),
                "link": folder + "/" + os.path.basename(path),
            })
        weeks.append((title, days))
    return weeks


def grab(text, heading, stop):
    """The body under the first heading matching `heading`, up to the first line matching `stop`."""
    m = re.search(heading, text, re.M)
    if not m:
        return None
    rest = text[m.end():]
    s = re.search(stop, rest, re.M)
    body = rest[:s.start()] if s else rest
    return body.strip("\n")


def rebase(text, src_dir):
    """Rewrite relative links so they still resolve from resources/."""
    def one(m):
        target, frag = m.group(1), ""
        if "#" in target:
            target, _, tail = target.partition("#")
            frag = "#" + tail
        if not target:
            return m.group(0)
        new = os.path.relpath(os.path.normpath(os.path.join(src_dir, target)), OUT)
        return "](" + new.replace(os.sep, "/") + frag + ")"
    return LINK.sub(one, text)


def day_link(day):
    return os.path.relpath(os.path.join(ROOT, day["link"]), OUT).replace(os.sep, "/")


def count_questions(body):
    """Both interview formats: Days 1–16 use <details>, Days 17–28 use **Qn.**."""
    return len(re.findall(r"<summary><b>Q", body)) + len(re.findall(r"^\*\*Q\d+\.", body, re.M))


# ── mapping ─────────────────────────────────────────────────────────────────
def gen_mapping(weeks):
    parts = [HEADER_MAPPING.strip("\n")]
    for i, (title, days) in enumerate(weeks):
        parts.append(("\n" if i else "") + "## " + title)
        for day in days:
            body = grab(day["text"], r"^#{3,4} .*JS ↔ Python.*$", r"^(#{1,3} |---\s*$)")
            if not body:
                continue        # e.g. Day 28 has no translation table
            parts.append(f"### Day {day['num']:02d} — [{day['title']}]({day_link(day)})")
            parts.append(rebase(body, day["dir"]))
    write(os.path.join(OUT, "js-vs-python-mapping.md"), "\n\n".join(parts) + "\n")


# ── interview bank ──────────────────────────────────────────────────────────
def gen_interviews(weeks):
    collected = []
    for title, days in weeks:
        rows = []
        for day in days:
            body = grab(day["text"], r"^## 9\. .*$", r"^## ")
            if not body:
                continue
            body = re.sub(r"\n---\s*$", "", body).strip("\n")
            body = re.sub(r"^(#{3,5}) ", r"#\1 ", body, flags=re.M)   # demote one level
            rows.append((day, rebase(body, day["dir"]), count_questions(body)))
        collected.append((title, rows))

    total = sum(n for _, rows in collected for _, _, n in rows)
    parts = [HEADER_INTERVIEWS.strip("\n").replace("{total}", str(total)), "## Contents"]

    toc = []
    for title, rows in collected:
        toc.append(f"- **{title}**")
        for day, _, n in rows:
            toc.append(f"  - Day {day['num']:02d} — {day['title']} ({n})")
    parts.append("\n".join(toc))

    for i, (title, rows) in enumerate(collected):
        parts.append(("\n" if i else "") + "## " + title)
        for day, body, n in rows:
            parts.append(f"### Day {day['num']:02d} — {day['title']}")
            parts.append(f"*{n} questions · [open the day]({day_link(day)})*")
            parts.append(body)
            parts.append("---")
    write(os.path.join(OUT, "interview-bank.md"), "\n\n".join(parts) + "\n")
    print(f"  {total} interview questions")


# ── troubleshooting ─────────────────────────────────────────────────────────
def gen_troubleshooting(weeks):
    parts = [HEADER_TROUBLESHOOTING.strip("\n")]
    for i, (title, _) in enumerate(weeks, 1):
        readme = os.path.join(ROOT, WEEKS[i - 1][0], "README.md")
        body = grab(read(readme), rf"^## Common Week {i} blockers\s*$", r"^(## |---\s*$)")
        if not body:
            continue
        parts.append("## " + title)
        parts.append(rebase(body, os.path.dirname(readme)))

    setup = os.path.join(ROOT, "SETUP.md")
    body = grab(read(setup), r"^## 5\. Troubleshooting the setup\s*$", r"^(## |---\s*$)")
    if body:
        parts.append("## Setup")
        parts.append(rebase(body, os.path.dirname(setup)))
    write(os.path.join(OUT, "troubleshooting.md"), "\n\n".join(parts) + "\n")


# ── curated headers (edit these, not the output) ────────────────────────────
HEADER_MAPPING = r"""
# JS ↔ Python Mapping

Every API pair used in this book, day by day — copied from each day's own translation table, so
it matches the code you read there. Use your browser's find (Ctrl/Cmd+F) on either name.

> **Behaviour differences that bite** (all verified in the day files — the names differ in many
> places, but these are the ones where the *behaviour* differs):
>
> | Area | JavaScript | Python | Day |
> |---|---|---|---|
> | `createAgent` / `create_agent` return value | a `ReactAgent` wrapper — the graph is on `.graph` | the compiled graph itself | 22 |
> | System prompt option | `systemPrompt` (`prompt` is silently ignored) | `system_prompt` (`prompt=` raises `TypeError`) | 16 |
> | `checkpointer` from `fromConnString` / `from_conn_string` | returns the saver | a context manager | 20, 27 |
> | Tool raises inside `ToolNode` | returned as tool-message content | re-raised unless `handle_tool_errors` | 24 |
> | Node `retryPolicy` / `retry_policy` default | retried a plain `Error` | skips `RuntimeError`, `ValueError`, `OSError` (incl. `TimeoutError`) | 24 |
> | Node timeouts | any node | async nodes only | 24 |
> | Leaving a stream loop early | the graph keeps running | the graph stops before the next superstep | 23 |
> | Nested graphs' tokens in `messages` mode | included by default | only with `subgraphs=True` | 23 |
> | Destinations for `Command` routing | `{ ends: [...] }` on `addNode` | `Command[Literal[...]]` return annotation | 19 |
> | MCP adapter tool results | a string | a list of content blocks; tools are async-only | 26 |
> | ChatGroq default retries | 6 | 2 | 24 |
> | PII `mask` strategy on an email | `a***@example.com` | `ayesha.khan@****.com` | 24 |
"""

HEADER_INTERVIEWS = r"""
# Interview Bank

**{total} questions with model answers**, collected verbatim from the interview section of every
day, grouped by week and level (Basic → Intermediate → Advanced).

**How to use it**

1. Cover the answer. Say yours out loud, timed — concept answers in under a minute.
2. Compare with the model answer: did you name a **mechanism**, a **number**, or a **trade-off**?
3. Mark the ones you missed and revisit that day's "Under the hood" section.
4. For system design and project questions, use the frameworks and mock interviews in
   [Day 28](../week-04-production-projects-and-interviews/day-28-capstones-and-interviews.md).
"""

HEADER_TROUBLESHOOTING = r"""
# Troubleshooting

Symptom → cause → fix, for everything this book ran into. Search this page for the exact error
text you're seeing (Ctrl/Cmd+F); the "Day" column points to the full explanation.

## Exact error messages (verified)

These strings were produced by running the code in this book. If you see one, the fix is known.

| Error text (excerpt) | Cause | Fix | Day |
|---|---|---|---|
| `UnreachableNodeError: Node ... is not reachable` / `Graph must have an entrypoint` | no edge from `START` | `addEdge(START, "first")` | 17 |
| `GraphRecursionError: Recursion limit of 25 reached` | a loop with no working exit | add a budget exit to the router; don't just raise the limit | 17 |
| `No checkpointer set` | `getState` / history / interrupts without a checkpointer | `compile({ checkpointer })` | 20 |
| `Failed to put checkpoint ... missing a required "thread_id"` / `Checkpointer requires one or more of the following 'configurable' keys` | invoking a checkpointed graph without a thread | pass `configurable.thread_id` | 20 |
| `When there are multiple pending interrupts, you must specify the interrupt id when resuming` | resuming parallel interrupts with one value | resume with a map of interrupt id → value | 21 |
| `Please specify a name when you create your agent` | unnamed agent, or JS `createAgent` wrapper passed instead of `.graph` | add `name`; pass `agent.graph` | 22 |
| `Cannot read properties of undefined (reading 'slice')` / `IndexError: list index out of range` in `checkpoints` stream mode | streaming checkpoints without a checkpointer | compile with a checkpointer | 23 |
| `Node timeouts are only supported for async nodes` | `timeout=` on a sync Python node | make the node `async def` | 24 |
| `Model call failed after N attempts with ...` shown as the answer | retry middleware default `onFailure: "continue"` | `onFailure: "error"` / `on_failure="error"` | 24 |
| `Model call limits exceeded: run limit` | model-call limit reached | expected; raise the limit or fix the loop | 24 |
| `PIIDetectionError` | PII middleware with `strategy: "block"` | expected; choose `redact`/`mask` if blocking isn't wanted | 24 |
| `Received status [401]: Unauthorized` from JS `evaluate` | LangSmith credentials missing | set `LANGSMITH_API_KEY`, or use a local eval harness | 25 |
| `StructuredTool does not support sync invocation` | calling a Python MCP tool synchronously | `await tool.ainvoke(...)` | 26 |
| `Unexpected token ... is not valid JSON` (MCP client) | a stdio MCP server printing to stdout | log to stderr | 26 |
| `Heads up! Your graph ... includes a custom checkpointer` | LangGraph server given a checkpointer-compiled graph | export `builder.compile()`; use `POSTGRES_URI` | 27 |
| `ConsoleRenderer with colors=True on Windows requires the colorama package` | `langgraph dev` on Windows | `pip install colorama` | 27 |
| `UnicodeEncodeError: 'charmap' codec can't encode character` | Windows console encoding with emoji output | `PYTHONUTF8=1` / `PYTHONIOENCODING=utf-8` | 27 |
| `node.exe: bad option: --clear-screen=false` | `langgraphjs dev` on an unsupported Node version | use a supported Node version, WSL, or Docker | 27 |

## Silent failures (no error at all)

The most expensive bugs don't throw. Symptoms to recognise:

| Symptom | Cause | Day |
|---|---|---|
| `invoke` returns `undefined` / `None` | a node writes a key that isn't a declared channel | 17 |
| Parallel results: one survives instead of N | fan-out into a last-write-wins channel | 17, 19 |
| Items duplicated in a list channel | returning the full list with an append reducer; or a subgraph sharing an appending channel | 17, 19 |
| A new conversation every turn | unstable or per-request `thread_id`; in-memory checkpointer across instances | 20, 27 |
| A side effect happens twice after approval | code before `interrupt()` re-runs on resume | 21 |
| A rejected action still runs | `Command` goto plus a static edge from the same node | 28 |
| The front desk answers after a handoff | swarm without a checkpointer or `activeAgent` | 22 |
| Stop button doesn't reduce cost (JS) | breaking out of the stream without an abort signal | 23 |
| A Python node never retries a timeout | default `retry_on` excludes `OSError` subclasses | 24 |
| Metrics show zero model calls | listening for LLM-start instead of chat-model-start | 25 |
| AI SDK returns empty text though a tool ran | `generateText` without `stopWhen` | 26 |
| Tool errors leak hostnames or connection strings | raw exceptions forwarded as tool / MCP results | 24, 26 |
"""

if __name__ == "__main__":
    weeks = load_days()
    gen_mapping(weeks)
    gen_interviews(weeks)
    gen_troubleshooting(weeks)
