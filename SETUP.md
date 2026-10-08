# SETUP — 15 minutes, $0

You need three things: **API keys** (free), a **JavaScript environment**, and/or a **Python
environment**. Do the language you'll actually use first; you can add the other later.

---

## 1. Get your free API keys

### 🥇 Groq — our default (fast, free, no credit card)

1. Go to <https://console.groq.com>
2. Sign in with Google/GitHub
3. **API Keys** → **Create API Key** → copy it

Groq runs open models (Llama, GPT-OSS, Qwen) on custom hardware. It is *stupidly* fast —
often 10x faster than OpenAI — which makes it perfect for learning because you're not
waiting 8 seconds per experiment.

**Models we'll use:**

| Model ID | Use it for |
|---|---|
| `openai/gpt-oss-120b` | Default. Smart, good at tool calling and structured output. |
| `openai/gpt-oss-20b` | The small, fast, cheap model: quick experiments, classification |
| `qwen/qwen3.8-27b` | Only for Day 02's hand-built text agent. A **preview** model on Groq (not for production) |

Both GPT-OSS models are **reasoning models**: before the answer they write hidden "thinking"
tokens, and those tokens count towards your `max_tokens` limit. Day 01 shows what that means in
practice.

> 📦 **Model names change.** This course was checked against Groq's model list on
> 7 October 2026. If a name gives a `404 … does not exist` error, open
> <https://console.groq.com/docs/models> and pick a current **production** model. For example,
> the old default that many tutorials still use now fails with
> ``404 The model `llama-3.3-70b-versatile` does not exist or you do not have access to it.``

### 🥈 Google Gemini — our fallback + free embeddings

1. Go to <https://aistudio.google.com/apikey>
2. **Create API key** → copy it

**Models:** `gemini-3.8-flash` (chat), `gemini-embedding-2` (embeddings).

> ⚠️ **Gemini is sometimes busy.** A popular model can answer
> `503 This model is currently experiencing high demand`. That is not your bug. Wait a minute
> and retry, or fall back to another model (Day 24 shows how to do this in code).

Gemini matters because Groq **does not** offer an embeddings endpoint — so from Week 2 (RAG)
onward, embeddings come from Gemini or Ollama.

### 🥉 Ollama — fully offline, no key at all (optional but recommended)

```bash
# macOS / Linux
curl -fsSL https://ollama.com/install.sh | sh

# Windows: download the installer from https://ollama.com/download
```

Then pull the two models this book uses:

```bash
ollama pull llama3.2          # chat, ~2 GB
ollama pull nomic-embed-text  # embeddings, ~275 MB
```

Verify it's running:

```bash
ollama run llama3.2 "say hi in five words"
```

> ⚠️ **Groq has no embeddings endpoint.** From Week 2 (Day 10) onward, embeddings come from
> **Ollama** (`nomic-embed-text`, local and free) or **Google** (`gemini-embedding-2`, free tier).
> Chat still uses Groq. If you only set up one extra thing for Week 2, make it `ollama pull
> nomic-embed-text`.

> 💡 **Why bother with Ollama?** Three reasons: (1) zero rate limits while you're hammering
> the API doing exercises, (2) you learn that *the model is just a swappable component*,
> (3) some jobs require on-prem models for privacy — knowing Ollama is a real interview edge.

<details>
<summary>💳 Using paid providers instead (OpenAI / Anthropic)</summary>

Everything in this book works identically with paid providers — swap the model class and the
key. Every code example includes the paid alternative.

| Provider | Key from | JS package | Python package |
|---|---|---|---|
| OpenAI | <https://platform.openai.com/api-keys> | `@langchain/openai` | `langchain-openai` |
| Anthropic | <https://console.anthropic.com/settings/keys> | `@langchain/anthropic` | `langchain-anthropic` |

```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```
</details>

---

## 2. The `.env` file

Create a file called `.env` in whatever folder you're experimenting in:

```bash
# .env
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
GOOGLE_API_KEY=AIzaxxxxxxxxxxxxxxxxxx

# Optional
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
TAVILY_API_KEY=            # free web search, needed Day 15
LANGSMITH_API_KEY=         # free tracing, needed Day 25
```

And **immediately** create `.gitignore`:

```gitignore
.env
node_modules/
__pycache__/
.venv/
*.db
chroma_db/
```

> 🚨 **The #1 way beginners leak money.** Committing `.env` to a public GitHub repo gets your
> key scraped by bots within *minutes*. Bots watch the GitHub firehose for exactly this.
> Add `.gitignore` **before** your first commit, not after.

---

## 3. JavaScript environment

**Requires Node.js 20 or newer.** Check:

```bash
node --version   # must be v20.x or higher
```

<details>
<summary>Node is older than 20 / not installed</summary>

Use [nvm](https://github.com/nvm-sh/nvm) (macOS/Linux) or [nvm-windows](https://github.com/coreybutler/nvm-windows):

```bash
nvm install 20
nvm use 20
```
</details>

### Create the project

```bash
mkdir langchain-practice && cd langchain-practice
npm init -y
```

**Critical step** — make `package.json` say `"type": "module"`. Recent npm versions (npm 11,
verified) write `"type": "commonjs"` for you, so you must *change* that line, not add a new one.
The quickest way is one command: `npm pkg set type=module`. The result should look like this:

```json
{
  "name": "langchain-practice",
  "type": "module",
  "version": "1.0.0"
}
```

> Without `"type": "module"`, `import` statements throw
> `SyntaxError: Cannot use import statement outside a module`.
> This is the single most common setup error. We explain *why* on [Day 0B](week-00-start-here/day-00b-programming-for-ai.md).

### Install packages

```bash
# Week 1 — everything you need to start
npm install langchain @langchain/core @langchain/groq @langchain/google-genai zod dotenv

# Week 2 — RAG (install when you get there)
npm install @langchain/classic @langchain/textsplitters @langchain/community @langchain/ollama chromadb

# Week 3 — agents & graphs
npm install @langchain/langgraph
```

### Verify

Create `check.js`:

```js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";

const model = new ChatGroq({ model: "openai/gpt-oss-120b" });
const res = await model.invoke("Reply with exactly: SETUP OK");

console.log(res.content);
console.log("tokens used:", res.usage_metadata);
```

```bash
node check.js
```

Expected (our run on 7 October 2026; your token counts may differ a little):

```
SETUP OK
tokens used: { input_tokens: 78, output_tokens: 50, total_tokens: 128 }
```

Why 50 output tokens for a two-word reply? The model "thought" before answering, and those
hidden reasoning tokens are billed as output. Why 78 input tokens for a short sentence? The
provider wraps your message in a hidden template. Day 01 explains both.

✅ If you see that, your JS setup is done.

---

## 4. Python environment

**Requires Python 3.10 or newer.** Check:

```bash
python --version    # or python3 --version
```

### Create the project

```bash
mkdir langchain-practice && cd langchain-practice

# Create a virtual environment (an isolated box for this project's packages)
python -m venv .venv

# Activate it
source .venv/bin/activate      # macOS / Linux
.venv\Scripts\activate         # Windows PowerShell
```

Your prompt should now start with `(.venv)`. If it doesn't, activation failed — everything
after this will install to the wrong place.

> 💡 **Why a venv?** Without it, `pip install` dumps packages into your system Python.
> Two projects needing different LangChain versions then fight each other. A venv is a
> per-project sandbox. **Always** activate before installing or running.

### Install packages

```bash
# Week 1
pip install langchain langchain-groq langchain-google-genai pydantic python-dotenv

# Week 2 — RAG
pip install langchain-classic langchain-text-splitters langchain-community langchain-ollama langchain-chroma pypdf

# Week 3 — agents & graphs  (langgraph already ships with langchain 1.x in Python)
pip install langgraph
```

### Verify

Create `check.py`:

```python
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

model = ChatGroq(model="openai/gpt-oss-120b")
res = model.invoke("Reply with exactly: SETUP OK")

print(res.content)
print("tokens used:", res.usage_metadata)
```

```bash
python check.py
```

Expected (our run on 7 October 2026; your token counts may differ a little):

```
SETUP OK
tokens used: {'input_tokens': 78, 'output_tokens': 51, 'total_tokens': 129, 'output_token_details': {'reasoning': 39}}
```

Python shows one extra detail: `reasoning: 39` means 39 of the 51 output tokens were the
model's hidden thinking. Only about a dozen were the visible answer.

✅ If you see that, your Python setup is done.

---

## 5. Troubleshooting the setup

| Error | Cause | Fix |
|---|---|---|
| `Cannot use import statement outside a module` | `package.json` lacks `"type": "module"` (npm 11 writes `"type": "commonjs"`) | `npm pkg set type=module` |
| `Error: Missing API key` / `GROQ_API_KEY not set` | `.env` not loaded, or wrong folder | JS: `import "dotenv/config"` as the **first** line. Python: `load_dotenv()` **before** creating the model |
| `ModuleNotFoundError: No module named 'langchain_groq'` | venv not activated, or installed globally | Activate `.venv`, reinstall |
| `401 Invalid API Key` | Key copied with a trailing space/newline | Re-copy; no quotes needed in `.env` |
| `404 The model … does not exist or you do not have access to it` | The model name was retired | Pick a current production model at <https://console.groq.com/docs/models> |
| `429 Rate limit reached` | Free tier limit hit | Wait 60s, or switch to `openai/gpt-oss-20b`, or use Ollama |
| Empty reply, `finish_reason: "length"` | `max_tokens` too small for a reasoning model | Raise `max_tokens` (e.g. 512–1024) — see Day 01 |
| `fetch failed` / `ENOTFOUND` | Network / corporate proxy | Check firewall; try Ollama offline |
| Python `SSL: CERTIFICATE_VERIFY_FAILED` | macOS missing certs | Run `/Applications/Python\ 3.x/Install\ Certificates.command` |

---

## 6. Editor setup (optional but nice)

- **VS Code** + the Python and ESLint extensions
- **Markdown Preview** (`Ctrl/Cmd + Shift + V`) to read this book's files with the diagrams rendered
- Install [Prettier](https://prettier.io) so your JS chain code stays readable when it gets long

---

## Ready?

You have keys, an environment, and a passing check script.

→ **[Day 01 — What an LLM actually is](week-01-foundations/day-01-llms-tokens-and-inference.md)**
