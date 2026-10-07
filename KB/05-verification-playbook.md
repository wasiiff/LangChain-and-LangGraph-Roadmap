# 05 — Verification playbook

How this book's claims get made, checked, and re-checked.

---

## The rule

> A technical claim in this book is a **measurement**, not a recollection.

So: install, run, read the real output, quote it. This is what caught the `prompt` vs
`systemPrompt` bug, the Python `ToolNode` re-raise, the Python `retry_on` defaults, the
`Command`-plus-static-edge bug, and the moved `@langchain/classic` imports — all of which would
otherwise have shipped as confident, wrong prose.

## Repository checks — `tools/`

| Script | Run it | Checks |
|---|---|---|
| `tools/verify.py` | `python tools/verify.py .` | relative links · all 10 sections per day · both languages per day · exercise-solution parity · per-day stats · README calendar completeness. Prints a table and `no problems found` |
| `tools/check_links.py` | `python tools/check_links.py .` | relative `.md` links only, across files git tracks or would track (respects `.gitignore`) |
| `tools/gen_resources.py` | `python tools/gen_resources.py .` | regenerates `resources/js-vs-python-mapping.md`, `interview-bank.md`, `troubleshooting.md` from the day files; prints the question count |
| `tools/sort_glossary.py` | `python tools/sort_glossary.py resources/glossary.md` | sorts every section alphabetically; asserts the entry count is unchanged |

Known false positive: `verify.py` flags Day 17 `E2:no-PY`. That exercise's solution *generates*
`<details>` markup inside a code block, which truncates the parser's split. It does contain both
languages.

## Verifying a library behaviour

1. Rebuild/enter the sandbox ([04](04-versions-and-environment.md)).
2. Write a probe **as a file** with the Write tool (heredocs break this shell), named
   `d<NN>*.js` / `d<NN>*.py` in the sandbox. Probes are throwaway — they aren't committed.
3. Run it, capture the real output, and record the finding in
   [03-verified-findings.md](03-verified-findings.md).
4. Prefer probing **both** languages in the same session: roughly a third of findings differ
   between them, and those differences are some of the book's most useful content.

### Probe pattern: a scripted model (no API key)

Both of these drive a real agent loop with deterministic "model" output, which is how every
Week 3–4 measurement was taken.

```js
import { BaseChatModel } from "@langchain/core/language_models/chat_models";
import { AIMessage } from "@langchain/core/messages";

class Scripted extends BaseChatModel {
  constructor(script) { super({}); this.script = script; this.i = 0; this.calls = 0; this.seen = []; }
  _llmType() { return "scripted"; }
  bindTools() { return this; }                     // agents call this; ignore it
  async _generate(messages) {
    this.calls++;
    this.seen.push(messages.length);               // how much context this call received
    const message = this.script[Math.min(this.i++, this.script.length - 1)](messages);
    return { generations: [{ message, text: typeof message.content === "string" ? message.content : "" }] };
  }
}
let n = 0;
const callTool = (name, args = {}) => () =>
  new AIMessage({ content: "", tool_calls: [{ name, args, id: `c${n++}`, type: "tool_call" }] });
const say = (text) => () => new AIMessage({ content: text });
const fail = (msg) => () => { throw new Error(msg); };
```

```python
import itertools
from pydantic import Field
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

class Scripted(GenericFakeChatModel):
    fails: int = 0
    calls: int = 0
    seen: list = Field(default_factory=list)

    def bind_tools(self, tools, **kw):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls += 1
        self.seen.append(len(messages))
        if self.fails > 0:                          # simulate an outage
            self.fails -= 1
            raise RuntimeError("503 overloaded")
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

ids = itertools.count()
def call_tool(name, args=None):
    return AIMessage(content="", tool_calls=[
        {"name": name, "args": args or {}, "id": f"c{next(ids)}", "type": "tool_call"}])
```

Rules that make scripted probes reliable:

- Build a **fresh** message object per call (ids are assigned on first use, so a reused object
  makes `addMessages` upsert instead of append).
- Give every tool call a **unique id**.
- Turn **jitter off** in retry policies, and inject clocks for time-based logic.
- For structured output, override `withStructuredOutput` to return the verdict directly (that's
  how the `openevals` judge was verified in JS).

### Probe pattern: a real local server (Day 27)

```bash
cd "<sandbox>/pyserver" || exit 1
PYTHONUTF8=1 ../.venv/Scripts/langgraph.exe dev --no-browser --no-reload --port 2024 > server.log 2>&1 &
for i in $(seq 1 40); do curl -s -m2 -o /dev/null -w "%{http_code}" http://127.0.0.1:2024/ok | grep -q 200 && break; sleep 2; done
```

Then drive it with `langgraph_sdk` / `@langchain/langgraph-sdk`. Stop it afterwards
(`Get-NetTCPConnection -LocalPort 2024` → `Stop-Process`). Read `server.log` on failure — the
useful line is usually several frames above the traceback's end.

## Recording a finding

Add a row to the right section of [03](03-verified-findings.md) with: the behaviour, the
**evidence** (exact numbers or error text), and whether it's `both` / `JS` / `PY` / `differs`.
If it contradicts the book, fix every occurrence (see KB recipe C) and note it in the
"Corrections" table.

## Before you finish a session

```bash
python tools/gen_resources.py .
python tools/verify.py .
git status --short          # know exactly what you changed
```

And check you didn't install anything into the repo: `package.json` at the root holds only the
reader's own practice dependencies (`dotenv`, `gpt-tokenizer`, `groq-sdk`).
