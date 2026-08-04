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
| `llama-3.3-70b-versatile` | Default. Smart, good at tool calling. |
| `llama-3.1-8b-instant` | Cheap/fast experiments, classification |
| `openai/gpt-oss-120b` | Strongest reasoning on Groq |

### 🥈 Google Gemini — our fallback + free embeddings

1. Go to <https://aistudio.google.com/apikey>
2. **Create API key** → copy it

**Models:** `gemini-2.5-flash` (chat), `gemini-embedding-001` / `text-embedding-004` (embeddings).

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

**Critical step** — open `package.json` and add `"type": "module"`:

```json
{
  "name": "langchain-practice",
  "type": "module",
  "version": "1.0.0"
}
```

> Without `"type": "module"`, `import` statements throw
> `SyntaxError: Cannot use import statement outside a module`.
> This is the single most common setup error. We explain *why* on [Day 03](week-01-foundations/day-03-js-python-essentials-and-why-langchain.md).

### Install packages

```bash
# Week 1 — everything you need to start
npm install langchain @langchain/core @langchain/groq @langchain/google-genai zod dotenv

# Week 2 — RAG (install when you get there)
npm install @langchain/community @langchain/textsplitters pdf-parse chromadb

# Week 3 — agents & graphs
npm install @langchain/langgraph @langchain/ollama
```

### Verify

Create `check.js`:

```js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile" });
const res = await model.invoke("Reply with exactly: SETUP OK");

console.log(res.content);
console.log("tokens used:", res.usage_metadata);
```

```bash
node check.js
```

Expected:

```
SETUP OK
tokens used: { input_tokens: 15, output_tokens: 5, total_tokens: 20 }
```

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
pip install langchain-community langchain-text-splitters pypdf chromadb

# Week 3 — agents & graphs
pip install langgraph langchain-ollama
```

### Verify

Create `check.py`:

```python
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

model = ChatGroq(model="llama-3.3-70b-versatile")
res = model.invoke("Reply with exactly: SETUP OK")

print(res.content)
print("tokens used:", res.usage_metadata)
```

```bash
python check.py
```

Expected:

```
SETUP OK
tokens used: {'input_tokens': 15, 'output_tokens': 5, 'total_tokens': 20}
```

✅ If you see that, your Python setup is done.

---

## 5. Troubleshooting the setup

| Error | Cause | Fix |
|---|---|---|
| `Cannot use import statement outside a module` | Missing `"type": "module"` in `package.json` | Add it |
| `Error: Missing API key` / `GROQ_API_KEY not set` | `.env` not loaded, or wrong folder | JS: `import "dotenv/config"` as the **first** line. Python: `load_dotenv()` **before** creating the model |
| `ModuleNotFoundError: No module named 'langchain_groq'` | venv not activated, or installed globally | Activate `.venv`, reinstall |
| `401 Invalid API Key` | Key copied with a trailing space/newline | Re-copy; no quotes needed in `.env` |
| `429 Rate limit reached` | Free tier limit hit | Wait 60s, or switch to `llama-3.1-8b-instant`, or use Ollama |
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
