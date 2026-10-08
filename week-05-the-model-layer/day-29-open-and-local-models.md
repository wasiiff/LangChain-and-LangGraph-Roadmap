# Day 29 — Open & Local Models: Run AI on Your Own Machine

> ⏱ **Time:** ~3 hours · 🎯 **Prereqs:** [Day 28](../week-04-production-projects-and-interviews/day-28-capstones-and-interviews.md) and [Day 03](../week-01-foundations/day-03-choosing-a-model-and-why-langchain.md) (choosing a model) · 🧩 **Difficulty:** ●●●○○

**Today you learn:** every model call in this course so far went to someone else's computer.
That breaks when data must stay inside a school, when a student has no internet, or when the
bill grows with every user. Today you download an open model and run it on your own CPU, in
JavaScript and Python. You learn to read a model card, to predict a model's size with simple
arithmetic, and what quantisation does. Then you plug the local model into LangChain and build
StudyBuddy's offline mode.

> 📖 **Words you'll meet today**
>
> - **Open-weight model** — a model whose trained numbers (weights) you can download and run.
> - **Parameter (weight)** — one learned number inside a model. Small models have millions;
>   large ones have billions.
> - **dtype** — the number format used to store each parameter, such as 32-bit or 16-bit.
> - **Quantisation** — storing each parameter in fewer bits so the model gets smaller.
> - **Model card** — the README page of a model: size, licence, context length, intended use.
> - **Chat template** — the exact text format a chat model was trained on, with its special
>   markers for "system", "user" and "assistant".
> - **GGUF** — the single-file model format used by llama.cpp and Ollama.
> - **ONNX** — a portable model format; Transformers.js runs it in Node and the browser.

> 🧪 **Measured, not recalled.** Every size, speed and answer below was measured on one machine:
> a 4-core Intel i5-8265U laptop CPU with 7.8 GB of RAM and no GPU, running Windows 11. Other
> jobs shared that CPU during some runs, so speeds vary. Your numbers will differ; the shape of
> the results is what matters.

---

## 1. The problem

StudyBuddy v6.0 ([Day 27](../week-04-production-projects-and-interviews/day-27-deployment-and-architecture.md))
is ready for 100,000 students. Then three emails arrive in the same week.

```
From: IT office, Northfield School
  "Student questions may not leave our network. Can StudyBuddy run on our own server?"

From: a student
  "I study on the train. No signal for 40 minutes. StudyBuddy just says:"
  ConnectError: [WinError 10061] No connection could be made because the
  target machine actively refused it

From: finance
  "The model bill doubled this month. It grows with every new student."
```

All three problems have one cause. The model lives on someone else's computer. You send every
question over the internet, you pay per token, and the provider sees the text.

The fix is to run a model yourself. That raises new questions. Which model may you use? Will it
fit in memory? How fast will it be? How good are its answers? Today answers each one with
measurements.

### The real-life version

Think about taxis and your own car. A taxi (a hosted API) is easy. Someone else maintains it,
and you pay per trip. But the driver knows where you go, you need a phone signal to call one,
and a long daily commute gets expensive.

Your own car (a local model) costs money and space up front. You must fit it in your garage
(memory), and a small car is slower than a taxi company's best one. But it works anywhere,
nobody sees your trips, and each extra trip costs almost nothing.

Neither is "better". Today you learn to choose, and to measure the size of the garage you need.

> 🔗 **Where this fits.** Days 1–28 taught you to build on top of a model API. Week 5 goes one
> layer down, to the model itself. Today you run a model. [Day 30](day-30-inference-and-serving.md)
> serves it to many users at once. Day 31 trains it further.

---

## 2. Mental model

A local model is a folder of files. You download it once, a **runner** loads it into memory,
and LangChain talks to the runner like any other chat model.

```
  Hugging Face Hub                       YOUR MACHINE
 ┌───────────────────────┐   download   ┌─────────────────────────────────────────────┐
 │ model card (README)   │   once       │  files on disk                              │
 │  licence · size ·     │ ───────────► │   weights: .safetensors / .onnx / .gguf     │
 │  context · intended   │              │   tokenizer + chat template                 │
 │  use                  │              │             │                               │
 │ weight files in       │              │             ▼  load into RAM                │
 │ several dtypes        │              │  RUNNER                                     │
 │  fp32 · bf16 · q8 ·   │              │   in-process: transformers (Py)             │
 │  q4 · GGUF Q4_K_M …   │              │               Transformers.js (JS)          │
 └───────────────────────┘              │   local server: Ollama · llama.cpp ·        │
                                        │                 LM Studio  (HTTP API)       │
                                        │             │                               │
                                        │             ▼                               │
                                        │  LangChain chat model → your LCEL chain     │
                                        └─────────────────────────────────────────────┘
```

Two numbers decide whether a model runs on your machine at all:

```
   memory needed  ≈  parameters × bytes per parameter  +  runtime overhead
   135 million    ×  2 bytes (bf16)                   ≈  269 MB of weights
```

| Idea | In one sentence | Where today |
|---|---|---|
| Open-weight vs closed | Can you download the weights, and what does the licence let you do? | §3.1 |
| Model card | The label on the box: size, licence, context, intended use | §3.2 |
| dtype | How many bits each parameter uses: 32, 16, 8 or 4 | §3.3 |
| Memory arithmetic | Parameters × bytes per parameter ≈ file size | §3.4 |
| Quantisation | Fewer bits per number: smaller, sometimes faster, a little less accurate | §3.5 |
| File formats | safetensors (PyTorch), ONNX (Transformers.js), GGUF (llama.cpp, Ollama) | §3.6 |
| Chat template | The exact text format a chat model expects; forget it and you get nonsense | §3.7 |
| Runner | The program that loads the file and generates tokens | §3.8 |
| Trade-off | Tiny local models are fast and private, but often wrong | §3.9 |

---

## 3. First principles

### 3.1 Open-weight, open-source and closed

> 💬 **In plain words:** "open" can mean three different things. Check what you can download,
> and what the licence lets you do with it.

[Day 03 §3.1](../week-01-foundations/day-03-choosing-a-model-and-why-langchain.md) split models into closed and open-weight, and §3.9 there listed the
licence questions to ask. Today adds a third kind and real licence data from the Hub.

| Kind | What you get | Examples (checked October 2026) |
|---|---|---|
| **Closed** | An API only. You never see the weights. | The big commercial chat models (Day 03 §3.1) |
| **Open-weight** | The trained weights, under a licence the publisher writes. Training data and code are often secret. | Llama (`llama3.1` licence), Gemma (`gemma` licence) |
| **Open-source** | Weights **and** enough about the data and code to rebuild them, under a standard open licence | Models that meet the Open Source Initiative's *Open Source AI Definition* (version 1.0, October 2024) |

Most "open" models you meet are open-weight. That is fine for running them. The detail that
matters in practice is the **licence**. Here are real licence fields from the Hugging Face Hub
(measured with `HfApi().model_info()` in October 2026):

| Model | Licence field | Gated? | Parameters |
|---|---|---|---|
| `HuggingFaceTB/SmolLM2-135M-Instruct` | `apache-2.0` | no | 134,515,008 |
| `Qwen/Qwen2.5-0.5B-Instruct` | `apache-2.0` | no | 494,032,768 |
| `microsoft/Phi-3.5-mini-instruct` | `mit` | no | 3,821,079,552 |
| `mistralai/Mistral-7B-Instruct-v0.3` | `apache-2.0` | no | 7,248,023,552 |
| `google/gemma-3-1b-it` | `gemma` | `manual` | 999,885,952 |
| `meta-llama/Llama-3.2-1B-Instruct` | `llama3.2` | `manual` | 1,235,814,400 |
| `meta-llama/Llama-3.1-8B-Instruct` | `llama3.1` | `manual` | 8,030,261,248 |

- `apache-2.0` and `mit` are standard open licences. Commercial use is allowed, with simple
  conditions such as keeping the licence notice.
- `gemma`, `llama3.1` and `llama3.2` are **custom** licences. You must accept them on the
  website before you can download ("gated: manual"). They add their own rules, such as an
  acceptable-use policy. Read them before you ship a product.

> ⚠️ **This is not legal advice.** A licence field is a label, not the licence. For a real
> product, a person (often a lawyer) reads the full text once and records the decision.
> Your code can still enforce that decision with an allow-list (§4.4).

### 3.2 Reading a model card

> 💬 **In plain words:** a model card is the label on the box. Five facts on it tell you
> whether the model fits your machine and your use.

Every model on the Hub has a card (its README) plus machine-readable metadata. This is what
the card and `config.json` of today's model say (measured):

```
licence:        apache-2.0
pipeline_tag:   text-generation
base_model:     HuggingFaceTB/SmolLM2-135M          ← this is a fine-tuned "Instruct" version
languages:      en
parameters:     134,515,008  stored as BF16
max_position_embeddings = 8192                       ← the context window, in tokens
torch_dtype = bfloat16
```

Read five things, in this order:

| Question | Where to look | Today's model |
|---|---|---|
| May I use it? | `license`, and whether it is gated | apache-2.0, not gated ✅ |
| Is it a chat model? | The name (`-Instruct`, `-it`, `-Chat`) and `base_model` | Instruct ✅ |
| Will it fit? | Parameter count × bytes per parameter (§3.4) | 269 MB in bf16 ✅ |
| How much text can it read? | `max_position_embeddings` in `config.json` | 8,192 tokens |
| What is it for? | "Intended use" and "Limitations" on the card | English, small tasks |

> 💡 **Base vs instruct.** A **base** model only continues text. An **instruct** (or chat)
> model was trained further to follow instructions and to use a chat template. For a
> chatbot, you want the instruct version.

### 3.3 What is inside a model file

> 💬 **In plain words:** a model file is a very long list of numbers. The dtype says how many
> bits each number uses. Fewer bits means a smaller file.

A model is millions or billions of parameters. Each parameter is one number. The file stores
them all, plus a little metadata. So the file size is mostly:

```
   number of parameters  ×  bytes per parameter
```

The dtype sets the bytes per parameter:

| dtype | Bits | Bytes | What it is |
|---|---|---|---|
| **fp32** | 32 | 4 | "Full precision". The classic format for training. Big. |
| **fp16** | 16 | 2 | Half precision. Same size as bf16, but a smaller range of values. |
| **bf16** | 16 | 2 | "Brain float". Same range as fp32, less detail. Common for releases. |
| **int8 / q8** | 8 | 1 | A whole number from -128 to 127, plus a scale (§3.5). |
| **int4 / q4** | 4 | 0.5 | A whole number from -8 to 7, plus a scale. |

You can check this on a real model. Today's model has 134,515,008 parameters. The Hub offers
the same model in several dtypes, so we can compare the arithmetic with the real files:

| File on the Hub | dtype | Arithmetic | Real file size | Match? |
|---|---|---|---|---|
| `model.safetensors` | bf16 | 134,515,008 × 2 = 269.0 MB | **269.1 MB** | ✅ |
| `onnx/model.onnx` | fp32 | × 4 = 538.1 MB | **540.3 MB** | ✅ |
| `onnx/model_fp16.onnx` | fp16 | × 2 = 269.0 MB | **270.3 MB** | ✅ |
| `onnx/model_quantized.onnx` | q8 | × 1 = 134.5 MB | **137.1 MB** | ✅ |
| `onnx/model_q4.onnx` | q4 | × 0.5 = 67.3 MB | **182.1 MB** | ❌ much bigger |

The first four match within about 2 %. The q4 file is almost three times bigger than the
arithmetic says. §3.6 opens the file and shows why. The short answer: not every part of the
model was made 4-bit.

When you load a model, memory follows the same rule. In Python, `get_memory_footprint()`
reported 269.0 MB for bf16 and 538.1 MB for fp32: exactly 2.00 and 4.00 bytes per parameter.

### 3.4 Memory arithmetic: will it fit?

> 💬 **In plain words:** multiply the number of parameters by the bytes per parameter. Then
> add room for the program itself. If the total is bigger than your free memory, it won't run.

[Day 03 §3.2](../week-01-foundations/day-03-choosing-a-model-and-why-langchain.md) worked out "8 billion parameters × 2 bytes = 16 GB" and called it
arithmetic, not a measurement. Now we can check it. Here is Meta's Llama 3.1 8B (8,030,261,248
parameters) against real GGUF files on the Hub (file sizes measured with the Hub API):

| Format | Bits per parameter | Arithmetic | Real file | Fits in a 7.8 GB laptop? |
|---|---|---|---|---|
| f32 | 32 | 32.12 GB | **32,128.9 MB** | ❌ |
| f16 / bf16 | 16 | 16.06 GB | (not listed) | ❌ |
| Q8_0 | 8.5 | 8.53 GB | **8,540.8 MB** | ❌ |
| Q4_K_M | ≈ 4.9 | 4.92 GB | **4,920.7 MB** | ✅ just |

Two lessons hide in that table.

1. **A "4-bit" model is not 4.0 bits per parameter.** Quantised formats also store scales
   (§3.5), so Q8_0 is really 8.5 bits and Q4_K_M came out at 4.90 bits per parameter
   (4,920.7 MB × 8 ÷ 8,030,261,248).
2. **The weights are not the whole bill.** The running program needs memory too. We measured a
   Python process with PyTorch and transformers loaded:

```
bf16 model   weights = 269.0 MB   process: libraries 345 MB → after load 659 MB → after generate 666 MB
```

So a 269 MB model needed a 666 MB process. The extra is the libraries, the tokenizer, working
memory for the maths, and the **KV cache**. The KV cache stores work from earlier tokens and
grows with the length of the conversation. [Day 30](day-30-inference-and-serving.md) measures it.

A safe habit is a rough budget like this:

```
   weights  +  runtime (~0.3–0.5 GB measured here)  +  KV cache  <  ~70 % of free RAM
```

The 70 % is our own safety margin, not a law. Your operating system and browser need the rest.
On this 7.8 GB laptop, an 8B model only fits as Q4 or smaller.

### 3.5 Quantisation in plain words

> 💬 **In plain words:** quantisation rounds every number to a shorter form. The model gets
> 2–8 times smaller. Its answers change a little, and sometimes get worse.

Imagine a list of prices: £3.14159, £2.71828, £1.41421. You could store them as £3.14, £2.72
and £1.41. That uses fewer digits. The prices are almost right, but not exactly.

Quantisation does the same to weights. It works on small **blocks** of numbers at a time. The
weights below are illustrative; the method is the one Q8_0 uses:

```
 a block of 32 weights (fp16):  0.12  -0.40   0.33  0.05  …  -0.38
                                 │
   1. find the biggest size:     0.40
   2. scale = 0.40 / 127         = 0.00315        ← stored once per block (2 bytes)
   3. store each weight as a whole number:  round(w / scale)
                                 38   -127    105   16   …   -121   ← 1 byte each (int8)

 to use it:  w ≈ whole number × scale   →  38 × 0.00315 = 0.1197  (was 0.12)
```

That is why Q8_0 costs **8.5 bits**, not 8: 32 one-byte numbers plus one 2-byte scale is 34
bytes for 32 weights. We read the exact block sizes from the `gguf` Python package:

| GGUF type | Numbers per block | Bytes per block | Bits per number |
|---|---|---|---|
| F16 | 1 | 2 | 16.0 |
| Q8_0 | 32 | 34 | 8.5 |
| Q6_K | 256 | 210 | 6.5625 |
| Q5_0 | 32 | 22 | 5.5 |
| Q4_K | 256 | 144 | 4.5 |
| Q4_0 | 32 | 18 | 4.5 |
| Q2_K | 256 | 84 | 2.625 |

The name tells you the bits. `Q4_K_M` means "4-bit, K-quant method, Medium mix". The "mix"
means some layers keep more bits, because some layers hurt quality more when rounded.

**What does rounding cost?** We asked the same three questions to the same model in five
formats. Settings were identical (greedy decoding, so no randomness):

| Question | Right answer | fp32 / bf16 | int8 (PyTorch) | q8 (ONNX) | q4 (ONNX) |
|---|---|---|---|---|---|
| What is 17 × 23? | 391 | 421 | 429 | 381 | 426 |
| Letters in "banana"? | 6 | 10 | (no number) | 12 | 10 |
| What is photosynthesis? | — | good sentence | good sentence | **repeats the question** | good sentence |

Two things stand out. First, this tiny model gets the maths wrong in **every** format (§3.9).
Second, quantisation changes answers, and the change is not predictable. Here the 8-bit ONNX
file (`q8`) did worse than the 4-bit one: it answered "photosynthesis" by repeating the
question. §3.6 shows a likely reason. The lesson: **test the exact file you will ship**, on
your own questions.

### 3.6 The formats you'll meet

> 💬 **In plain words:** the same model is sold in different file types for different runners.
> Pick the format your runner reads.

| Format | Extension | Read by | Quantised versions |
|---|---|---|---|
| **safetensors** | `.safetensors` | PyTorch, `transformers` | usually fp32/bf16; quantise on load |
| **ONNX** | `.onnx` | ONNX Runtime, **Transformers.js** | `fp16`, `q8`, `q4`, `q4f16`, `bnb4` files side by side |
| **GGUF** | `.gguf` | **llama.cpp**, **Ollama**, LM Studio | one file per level: `Q8_0`, `Q4_K_M`, `Q2_K` … |
| bitsandbytes, AWQ, GPTQ | (inside safetensors) | `transformers` on an **NVIDIA GPU** | 8-bit and 4-bit |

> ⚠️ **GPU-only formats were not executed here.** bitsandbytes, AWQ and GPTQ need an NVIDIA
> GPU. On this CPU-only machine, asking for 4-bit loading failed before it started (measured):
> `ImportError: Using bitsandbytes 4-bit quantization requires bitsandbytes`. Check your
> version and hardware before you rely on them.

**Looking inside the files.** File sizes in §3.3 did not match the arithmetic for q4. We
opened the files with the `onnx` and `gguf` Python packages and counted the stored numbers:

```
model_quantized.onnx (q8)   UINT8 134,480,083 numbers   FLOAT 559,635
                            ops include DynamicQuantizeLinear ×120, MatMulInteger ×210
                            largest tensor: embed_tokens  UINT8  [49152, 576]

model_q4.onnx (q4)          UINT8  53,084,160 numbers   FLOAT 32,188,736
                            ops include MatMulNBits ×210
                            largest tensor: embed_tokens  FLOAT  [49152, 576]
```

- In the **q4** file, the big matrix maths is 4-bit (two numbers packed per byte). But the
  **embedding table** (49,152 tokens × 576 numbers = 28.3 million numbers) stays as 32-bit
  floats. That one table is 113 MB, which explains most of the 182 MB.
- In the **q8** file, almost everything is 8-bit, including the embedding table. It also has
  120 `DynamicQuantizeLinear` steps, which round the **activations** (the numbers flowing
  between layers) at run time. More rounding is a likely reason the q8 file answered worse
  than the q4 file.

The GGUF file shows the "mix" idea from §3.5:

```
SmolLM2-135M-Instruct-Q4_K_M.gguf
  general.architecture = llama     llama.context_length = 8192     chat template: present
  tensor types: Q5_0 ×166 · F32 ×61 · Q8_0 ×15 · Q4_K ×16 · Q6_K ×14
  total 134,515,008 numbers in 103.7 MB = 6.17 bits per number
```

Only 16 tensors are actually `Q4_K`. Most are `Q5_0`. In this file, every tensor whose rows
are 576 numbers wide got `Q5_0` or `Q8_0`. Only the 1,536-wide `ffn_down` tensors got K-quants
(`Q4_K` or `Q6_K`). K-quants work on blocks of 256 numbers, and 576 is not a multiple of 256,
so that is the likely reason. For tiny models, a "4-bit" file can therefore average 6+ bits.
For big models (rows of 4,096 numbers), it landed near 4.9 bits, as §3.4 showed.

> 💡 **A GGUF file is self-contained.** It carries the weights, the tokenizer **and** the chat
> template in one file. That is why Ollama and LM Studio can run it with no other files.

### 3.7 The chat template: the step everyone forgets

> 💬 **In plain words:** a chat model was trained on text with special markers around each
> message. If you send plain text without those markers, the model is lost.

An instruct model never saw "messages". It saw one long string with markers. For today's
model, the tokenizer turns a list of messages into this (measured):

```
<|im_start|>system
You are a helpful AI assistant named SmolLM, trained by Hugging Face<|im_end|>
<|im_start|>user
In one sentence, what is photosynthesis?<|im_end|>
<|im_start|>assistant

```

Notice two things. The template **added a system message** we never wrote, because this
model's template inserts a default one. And it ends with an open `assistant` line, so the
model's next tokens are the answer. That last part comes from `add_generation_prompt`.

Send the question as plain text instead, and you get nothing (measured, same model):

| How you send it | Python (`transformers`) | JavaScript (Transformers.js, q4) |
|---|---|---|
| Messages → chat template | "Photosynthesis is the process by which plants, algae, and some bacteria convert light energy into chemical energy…" | "Photosynthesis is the process by which plants, algae, and some bacteria convert light energy into chemical energy." |
| Plain string | `''` (empty: 1 token, end-of-text) | the prompt itself, with nothing added |

Every model family has its own template. Llama, Gemma, Qwen and SmolLM all use different
markers. Never write them by hand. Use `apply_chat_template` (both languages), or a runner that
applies it for you (Ollama, `ChatHuggingFace`, and Transformers.js when you pass messages).

### 3.8 The runners: from a library to a local server

> 💬 **In plain words:** a runner is the program that loads the model file and produces
> tokens. Some run inside your program. Others run as a separate server on your machine.

```
   IN-PROCESS                              LOCAL SERVER (separate program)
   your code loads the model itself        your code sends HTTP to localhost

   transformers (Python, safetensors)      Ollama          ollama pull / ollama run
   Transformers.js (JS, ONNX)              llama.cpp       llama-server
                                           LM Studio       desktop app with a server
   + no extra program                      + one model shared by many apps
   + works offline once cached             + GPU support, GGUF quantisation
   − loads in every process                − another program to install and keep running
```

| Runner | Format | Languages | Executed today? |
|---|---|---|---|
| `transformers` | safetensors | Python | ✅ |
| Transformers.js | ONNX | JavaScript (Node, browser) | ✅ |
| Ollama | GGUF | any (HTTP API) — `ChatOllama` in both | ❌ not installed here |
| llama.cpp (`llama-server`) | GGUF | any (HTTP API) | ❌ not installed here |
| LM Studio | GGUF | any (HTTP API) | ❌ not installed here |

Ollama, llama.cpp's server and LM Studio can all speak an **OpenAI-compatible** HTTP API. That
means any client built for OpenAI's API can talk to them by changing the base URL. You build
your own server like that on [Day 30](day-30-inference-and-serving.md).

### 3.9 Honest trade-offs: tiny models are weak

> 💬 **In plain words:** a model small enough to run fast on any laptop is also small enough
> to be wrong often. It sounds confident even when it is wrong.

Today's model has 135 million parameters. That is tiny, and it is chosen on purpose: it
downloads in seconds and runs on any CPU, so you can run every example. Here is what it said
(measured, greedy decoding, Python bf16):

```
Q: What is 17 * 23? Reply with just the number.
A: 17 * 23 = 421                                              ← wrong (391)

Q: How many letters are in the word 'banana'? Reply with just the number.
A: The word 'banana' has 10 letters.                          ← wrong (6)

Q: Which is heavier: one kilogram of feathers or one kilogram of steel?
A: One kilogram of feathers is approximately 1.2 pounds, while one kilogram of steel
   is approximately 1.5 pounds.                               ← nonsense

Q: Who discovered mitochondria?   (system: "Answer only from these notes and cite the note id")
A: The discovery of mitochondria was made by two scientists, Linus Pauling and Walter
   Gilbert, in 1953.                                          ← invented, and no citation
```

It also got some right ("Canberra", "Jane Austen", "Neil Armstrong … July 20, 1969"). That
mix is the danger: the wrong answers sound exactly like the right ones.

When does local make sense?

| Choose local when… | Choose a hosted API when… |
|---|---|
| Data must not leave your network (privacy rules) | You need the best possible quality |
| The app must work offline | Traffic is low or comes in bursts |
| Volume is high and steady, so per-token prices add up | Nobody on the team can run servers |
| You need a custom or fine-tuned model ([Day 31](day-31-fine-tuning.md)) | You need very long context or many languages |
| You need a fixed version that never changes under you | You want new model versions without any work |

Local chat apps commonly use models of 1–8 billion parameters, quantised to about 4 bits. By
§3.4's arithmetic, that is roughly 0.6 GB for a 1B model and 4.9 GB for an 8B one, compared
with 269 MB for today's model. The code is identical: you change one model id. The memory
arithmetic tells you whether it will fit.

---

## 4. Code — JavaScript

```bash
npm install @huggingface/transformers @langchain/core @langchain/ollama
# verified with @huggingface/transformers 4.3.1 · @langchain/core 1.2.17 · @langchain/ollama 1.3.0 · Node 24
```

Transformers.js downloads the model on first use and caches it. Set `env.cacheDir` if you want
the files somewhere specific (we used a folder on a bigger drive).

### 4.1 Your first local model

```js
// first-local.mjs — run an open-weight model inside Node with Transformers.js
import { pipeline, env } from "@huggingface/transformers";
env.cacheDir = "./models-cache";                       // optional: where downloads are kept

const MODEL = "HuggingFaceTB/SmolLM2-135M-Instruct";
let start = performance.now();
const generator = await pipeline("text-generation", MODEL, { dtype: "q4" });   // ~182 MB once
console.log(`loaded in ${((performance.now() - start) / 1000).toFixed(1)}s`);

const messages = [{ role: "user", content: "In one sentence, what is photosynthesis?" }];
console.log(generator.tokenizer.apply_chat_template(messages, { tokenize: false, add_generation_prompt: true }));

start = performance.now();
const out = await generator(messages, { max_new_tokens: 60, do_sample: false });
const seconds = (performance.now() - start) / 1000;
const reply = out[0].generated_text.at(-1).content;    // the last message is the new one
const n = generator.tokenizer.encode(reply, { add_special_tokens: false }).length;
console.log(reply);
console.log(`${n} tokens in ${seconds.toFixed(1)}s = ${(n / seconds).toFixed(1)} tokens/s`);
await generator.dispose();
```

Output (files already cached):

```
loaded in 0.9s
<|im_start|>system
You are a helpful AI assistant named SmolLM, trained by Hugging Face<|im_end|>
<|im_start|>user
In one sentence, what is photosynthesis?<|im_end|>
<|im_start|>assistant

Photosynthesis is the process by which plants, algae, and some bacteria convert light energy into chemical energy.
21 tokens in 0.7s = 31.5 tokens/s
```

Three details matter:

- You pass **messages**, so the pipeline applies the chat template for you. `generated_text`
  comes back as the whole conversation, and the last item is the new reply.
- `max_new_tokens` is set on purpose. Without it, the text-generation pipeline uses its own
  default of 256 new tokens (from the library source). Asked to explain photosynthesis to a
  ten-year-old, this model wrote 212 tokens (q4) and 255 tokens (fp32), repeating itself.
- `do_sample: false` means greedy decoding: always the most likely token. That makes runs
  repeatable, which you need for measurements.

### 4.2 Same model, three dtypes: size and speed

```js
// dtypes.mjs — compare file size and tokens/second for fp32, q8 and q4
import { pipeline, env } from "@huggingface/transformers";
import fs from "node:fs";
import path from "node:path";

env.cacheDir = "./models-cache";
const MODEL = "HuggingFaceTB/SmolLM2-135M-Instruct";
const messages = [{ role: "user", content: "In one sentence, what is photosynthesis?" }];
const N = 32;
const median = (xs) => [...xs].sort((a, b) => a - b)[Math.floor(xs.length / 2)];

for (const dtype of ["fp32", "q8", "q4"]) {
  let t = performance.now();
  const generator = await pipeline("text-generation", MODEL, { dtype });
  const loadS = (performance.now() - t) / 1000;
  const rates = [];
  let answer = "";
  for (let i = 0; i < 3; i++) {                         // three runs: CPU timing is noisy
    t = performance.now();
    const out = await generator(messages, { max_new_tokens: N, min_new_tokens: N, do_sample: false });
    const s = (performance.now() - t) / 1000;
    answer = out[0].generated_text.at(-1).content;
    rates.push(generator.tokenizer.encode(answer, { add_special_tokens: false }).length / s);
  }
  console.log(`${dtype.padEnd(5)} load ${loadS.toFixed(1)}s  median ${median(rates).toFixed(1)} tok/s`);
  console.log(`      ${JSON.stringify(answer.slice(0, 90))}`);
  await generator.dispose();                             // free memory before the next one
}
const dir = path.join(env.cacheDir, MODEL, "onnx");
for (const f of fs.readdirSync(dir)) console.log(f, (fs.statSync(path.join(dir, f)).size / 1e6).toFixed(1), "MB");
```

Output (this machine, CPU only, files cached, CPU mostly idle):

```
fp32  load 2.2s  median 21.0 tok/s
      "Photosynthesis is the process by which plants, algae, and some bacteria convert light ener"
q8    load 0.8s  median 21.8 tok/s
      "In one sentence, what is photosynthesis? It is the process by which plants convert light e"
q4    load 0.9s  median 23.5 tok/s
      "Photosynthesis is the process by which plants, algae, and some bacteria convert light ener"
model.onnx 540.3 MB
model_q4.onnx 182.1 MB
model_quantized.onnx 137.1 MB
```

We ran the same script in three sessions. Speeds are medians of three runs each:

| dtype | File on disk | Load (cached) | CPU busy (100 %) | CPU idle, run A | CPU idle, run B | Answer quality |
|---|---|---|---|---|---|---|
| `fp32` | `model.onnx` 540.3 MB | 1.8–2.2 s | 14.3 tok/s | 21.0 tok/s | 32.4 tok/s | good |
| `q8` | `model_quantized.onnx` 137.1 MB | 0.7–0.8 s | 14.5 tok/s | 21.8 tok/s | 28.7 tok/s | repeats the question first |
| `q4` | `model_q4.onnx` 182.1 MB | 0.9–1.0 s | 13.2 tok/s | 23.5 tok/s | 18.2 tok/s | good |

Read the speed columns carefully. The "winner" changes from session to session. For this tiny
model, the speed difference between dtypes is **smaller than the noise** between runs. What
quantisation reliably saved was **disk, memory and load time**. §6.1 explains why big models
behave differently. Always take the median of several runs, repeat on another day, and write
down how busy the machine was.

> 📦 **How `dtype` maps to files.** In Transformers.js 4.3.1, `q8` loads
> `model_quantized.onnx`, `q4` loads `model_q4.onnx`, `fp16` loads `model_fp16.onnx`. With no
> `dtype` on Node's CPU, you get `fp32`. An **unknown** string, such as `"int4"`, silently
> falls back to `fp32` too (measured, and visible in the library's `selectDtype` code).

### 4.3 Wrap it for LangChain and use it in a chain

LangChain JS has no ready-made chat class for Transformers.js. But you already know how to
write one: Day 22 subclassed `BaseChatModel` for scripted models. The same twenty lines turn
any local runner into a chat model that works with prompts, parsers, fallbacks and graphs.

```js
// local-chat.mjs — a LangChain chat model backed by Transformers.js
import { pipeline } from "@huggingface/transformers";
import { BaseChatModel } from "@langchain/core/language_models/chat_models";
import { AIMessage, HumanMessage } from "@langchain/core/messages";
import { ChatPromptTemplate } from "@langchain/core/prompts";
import { StringOutputParser } from "@langchain/core/output_parsers";

const ROLE = { human: "user", ai: "assistant", system: "system" };

export class LocalChat extends BaseChatModel {
  constructor({ model, dtype = "q4", maxNewTokens = 80 }) {
    super({});
    this.model = model; this.dtype = dtype; this.maxNewTokens = maxNewTokens;
  }
  _llmType() { return "transformers-js"; }
  async _generate(messages) {
    this.generator ??= await pipeline("text-generation", this.model, { dtype: this.dtype });
    const chat = messages.map((m) => ({ role: ROLE[m.getType()], content: m.content }));
    const out = await this.generator(chat, { max_new_tokens: this.maxNewTokens, do_sample: false });
    const text = out[0].generated_text.at(-1).content;
    // count tokens ourselves, so usage_metadata works like a hosted model's (Day 04)
    const tok = this.generator.tokenizer;
    const promptText = tok.apply_chat_template(chat, { add_generation_prompt: true, tokenize: false });
    const input_tokens = tok.encode(promptText, { add_special_tokens: false }).length;
    const output_tokens = tok.encode(text, { add_special_tokens: false }).length;
    const message = new AIMessage({
      content: text,
      usage_metadata: { input_tokens, output_tokens, total_tokens: input_tokens + output_tokens },
    });
    return { generations: [{ message, text }] };
  }
}

const chat = new LocalChat({ model: "HuggingFaceTB/SmolLM2-135M-Instruct" });
const msg = await chat.invoke([new HumanMessage("In one sentence, what is photosynthesis?")]);
console.log(msg.content);
console.log(msg.usage_metadata);

const prompt = ChatPromptTemplate.fromMessages([
  ["system", "You are StudyBuddy, a concise study tutor. Answer in at most two sentences."],
  ["human", "{question}"],
]);
const chain = prompt.pipe(chat).pipe(new StringOutputParser());
console.log(await chain.invoke({ question: "What does a mitochondrion do?" }));
```

Output:

```
Photosynthesis is the process by which plants, algae, and some bacteria convert light energy into chemical energy.
{ input_tokens: 38, output_tokens: 21, total_tokens: 59 }
A mitochondrion is a complex organelle that plays a vital role in the cell's energy production. It is
responsible for generating ATP (adenosine triphosphate) and other energy-related molecules. The
mitochondria also have a role in the cell's waste removal and the production of certain cellular components.
```

The first call took 3.5 s including loading; the chain call took 3.3 s. Notice that the
answer has **three** sentences. The system prompt asked for two. Small models follow
instructions loosely, so put hard limits in code (`maxNewTokens`), not only in the prompt.

> 💡 **`input_tokens: 38` for a 9-word question.** The chat template and the default system
> message added 29 tokens. Local tokens cost no money, but they still cost time and context.

### 4.4 A licence gate and a true offline switch

Two guard rails belong in any app that downloads models. First, refuse models whose licence
nobody has approved. Second, when you promise "offline", make the library unable to use the
network.

```js
// guards.mjs
import { pipeline, env } from "@huggingface/transformers";

const ALLOWED = new Set(["apache-2.0", "mit"]);        // decided once, by a person
async function licenceOk(repo) {
  const info = await (await fetch(`https://huggingface.co/api/models/${repo}`)).json();
  const lic = info.cardData?.license;
  if (info.gated) return [false, `${repo}: gated (${info.gated}), licence=${lic} -> needs a human to read the terms`];
  if (!ALLOWED.has(lic)) return [false, `${repo}: licence=${lic} is not on the allow-list`];
  return [true, `${repo}: licence=${lic} OK`];
}
for (const repo of ["HuggingFaceTB/SmolLM2-135M-Instruct", "meta-llama/Llama-3.2-1B-Instruct", "google/gemma-3-1b-it"]) {
  console.log((await licenceOk(repo))[1]);
}

env.allowRemoteModels = false;                         // offline: cache only, never the network
try {
  await pipeline("text-generation", "onnx-community/Qwen2.5-0.5B-Instruct", { dtype: "q4" });
} catch (e) {
  console.log(e.constructor.name + ":", e.message.slice(0, 90));
}
```

Output:

```
HuggingFaceTB/SmolLM2-135M-Instruct: licence=apache-2.0 OK
meta-llama/Llama-3.2-1B-Instruct: gated (manual), licence=llama3.2 -> needs a human to read the terms
google/gemma-3-1b-it: gated (manual), licence=gemma -> needs a human to read the terms
ModelFileNotFoundError: `local_files_only=true` or `env.allowRemoteModels=false` and file was not found locally at
```

The licence check runs at build or deploy time, not on every request. The offline switch turns
a silent download into a clear, early error.

### 4.5 Ollama and other local servers

Most people run local models through **Ollama**: install it, `ollama pull llama3.2`, and it
serves GGUF models on `http://localhost:11434`. You used it in
[Day 04](../week-01-foundations/day-04-langchain-models.md) as the free, local provider. The
LangChain code is the same as there:

```js
// ⚠️ not executed here — Ollama is not installed on this machine
import { ChatOllama } from "@langchain/ollama";

const model = new ChatOllama({ model: "llama3.2", temperature: 0 });
const reply = await model.invoke("In one sentence, what is photosynthesis?");
console.log(reply.content);
```

What **was** measured: with no Ollama server running, `invoke` fails with
`TypeError: fetch failed`. That failure is useful. §8 Exercise 5 uses it to fall back to the
in-process model from §4.3.

Ollama, llama.cpp's `llama-server` and LM Studio can also expose an OpenAI-compatible API, so
OpenAI-style clients can talk to them by changing the base URL. Check each tool's docs for the
exact port and path in your version. [Day 30](day-30-inference-and-serving.md) builds such a
server and measures it.

---

## 5. Code — Python

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu    # CPU-only build, smaller
pip install transformers langchain-huggingface langchain-ollama
# verified with torch 2.14.1+cpu · transformers 5.19.0 · huggingface_hub 1.33.0
#               langchain-core 1.6.7 · langchain-huggingface 1.2.2 · langchain-ollama 1.1.0 · Python 3.14
```

Downloads are cached under `~/.cache/huggingface`. Set the `HF_HOME` environment variable to
move the cache to a bigger drive.

> 🪟 **Windows:** `huggingface_hub` warns that your machine "does not support" symlinks in the
> cache. Caching still works; it just uses more disk. Turn on Developer Mode to remove the
> warning, or set `HF_HUB_DISABLE_SYMLINKS_WARNING=1`.

### 5.1 Your first local model

```python
# first_local.py — run an open-weight model on your CPU with transformers
import time
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL = "HuggingFaceTB/SmolLM2-135M-Instruct"
tok = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForCausalLM.from_pretrained(MODEL)          # downloads ~269 MB once
n_params = sum(p.numel() for p in model.parameters())
print(f"dtype={model.dtype} params={n_params:,} memory={model.get_memory_footprint()/1e6:.1f} MB")

messages = [{"role": "user", "content": "In one sentence, what is photosynthesis?"}]
prompt = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
print(prompt)

inputs = tok(prompt, return_tensors="pt")
start = time.perf_counter()
with torch.no_grad():
    out = model.generate(**inputs, max_new_tokens=60, do_sample=False)
seconds = time.perf_counter() - start
new_tokens = out[0][inputs["input_ids"].shape[1]:]          # drop the prompt tokens
print(tok.decode(new_tokens, skip_special_tokens=True))
print(f"{len(new_tokens)} tokens in {seconds:.1f}s = {len(new_tokens)/seconds:.1f} tokens/s")
```

Output:

```
dtype=torch.bfloat16 params=134,515,008 memory=269.0 MB
<|im_start|>system
You are a helpful AI assistant named SmolLM, trained by Hugging Face<|im_end|>
<|im_start|>user
In one sentence, what is photosynthesis?<|im_end|>
<|im_start|>assistant

Photosynthesis is the process by which plants, algae, and some bacteria convert light energy into
chemical energy, which is then used to produce glucose, a vital source of energy for the plant.
39 tokens in 3.7s = 10.7 tokens/s
```

A second run gave 8.8 tokens/s. With other jobs using the CPU at 100 %, it dropped to about
2 tokens/s.

> 📦 **transformers 5 loads the model's own dtype.** `from_pretrained` with no `dtype` gave
> `torch.bfloat16`, because `config.json` says `torch_dtype: bfloat16`. Pass `dtype=` to choose.
> The old keyword still works but warns: `` `torch_dtype` is deprecated! Use `dtype` instead! ``.
> §5.2 shows why bf16 may not be what you want on a CPU.

### 5.2 dtypes, memory and speed

```python
# dtypes.py — memory footprint and median speed per dtype
import statistics, time
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL = "HuggingFaceTB/SmolLM2-135M-Instruct"
tok = AutoTokenizer.from_pretrained(MODEL)
prompt = tok.apply_chat_template([{"role": "user", "content": "In one sentence, what is photosynthesis?"}],
                                 tokenize=False, add_generation_prompt=True)
ids = tok(prompt, return_tensors="pt")
N = 32

for dtype in [torch.float32, torch.bfloat16]:
    model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=dtype)
    per_param = model.get_memory_footprint() / sum(p.numel() for p in model.parameters())
    rates = []
    for _ in range(3):                                         # three runs: CPU timing is noisy
        t = time.perf_counter()
        with torch.no_grad():
            model.generate(**ids, max_new_tokens=N, min_new_tokens=N, do_sample=False)
        rates.append(N / (time.perf_counter() - t))
    print(f"{str(dtype):15s} {model.get_memory_footprint()/1e6:6.1f} MB "
          f"({per_param:.2f} bytes/param)  median {statistics.median(rates):.1f} tok/s")
    del model                                                  # free memory before the next one
```

Output (this machine, CPU mostly idle):

```
torch.float32    538.1 MB (4.00 bytes/param)  median 8.2 tok/s
torch.bfloat16   269.0 MB (2.00 bytes/param)  median 6.0 tok/s
```

A second session gave 11.7 tok/s for fp32 and 5.8 tok/s for bf16. In both, bf16 used half the
memory but was **slower**. This laptop's CPU (an i5-8265U from 2018) runs
fp32 maths fast. A likely reason bf16 is slower here is that this CPU has no fast bf16
instructions, so the numbers are converted as they are used. Newer CPUs and GPUs can behave
differently. That is the point: **measure on the hardware you will deploy to.**

Compare with §4.2: the same model in ONNX Runtime (through Transformers.js) gave 21.0 tok/s
in fp32. Different runners, same weights, almost twice the speed. Runner choice matters as much
as dtype.

### 5.3 Wrap it for LangChain and use it in a chain

Python has a ready-made integration: `langchain-huggingface`. `HuggingFacePipeline` wraps a
local `transformers` pipeline as a text LLM. `ChatHuggingFace` wraps that as a chat model and
applies the chat template for you.

```python
# local_chat.py — ChatHuggingFace in an LCEL chain
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_huggingface import ChatHuggingFace, HuggingFacePipeline

llm = HuggingFacePipeline.from_model_id(
    model_id="HuggingFaceTB/SmolLM2-135M-Instruct",
    task="text-generation",
    pipeline_kwargs={"max_new_tokens": 80, "do_sample": False, "return_full_text": False},
)
chat = ChatHuggingFace(llm=llm)

msg = chat.invoke([HumanMessage("In one sentence, what is photosynthesis?")])
print(type(msg).__name__, repr(msg.content))
print("usage_metadata:", msg.usage_metadata)

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are StudyBuddy, a concise study tutor. Answer in at most two sentences."),
    ("human", "{question}"),
])
chain = prompt | chat | StrOutputParser()
print(chain.invoke({"question": "What does a mitochondrion do?"}))
```

Output:

```
AIMessage 'Photosynthesis is the process by which plants, algae, and some bacteria convert light
energy into chemical energy, which is then used to produce glucose, a vital source of energy for the plant.'
usage_metadata: None
A mitochondrion is a specialized organelle found in eukaryotic cells, responsible for producing energy
through cellular respiration. It is a membrane-bound structure that contains the energy-producing
enzymes necessary for cellular processes, such as the citric acid cycle and the electron transport chain.
```

Loading took 14.6 s; `invoke` took 3.4 s and the chain 3.9 s. Two things differ from JS:

- **`usage_metadata` is `None`.** `ChatHuggingFace` with a local pipeline did not report token
  counts in this version. If your cost or context tracking (Day 25) relies on it, count tokens
  yourself with `chat.tokenizer`, as the JS wrapper does.
- **`return_full_text: False` is essential.** Without it, the reply contains the whole
  templated prompt as well (§7, mistake 3).

> ⚠️ **Don't use the bare `HuggingFacePipeline` for an instruct model.** It is a text LLM, so
> it sends your string with no chat template. `llm.invoke("In one sentence, what is
> photosynthesis?")` returned `''` (measured). Always wrap it in `ChatHuggingFace`.

### 5.4 A licence gate and a true offline switch

```python
# guards.py
import os
from huggingface_hub import HfApi

ALLOWED = {"apache-2.0", "mit"}                 # decided once, by a person


def licence_ok(repo: str) -> tuple[bool, str]:
    info = HfApi().model_info(repo)
    lic = info.card_data.license if info.card_data else None
    if info.gated:
        return False, f"{repo}: gated ({info.gated}), licence={lic} -> needs a human to read the terms"
    if lic not in ALLOWED:
        return False, f"{repo}: licence={lic} is not on the allow-list"
    return True, f"{repo}: licence={lic} OK"


for repo in ["HuggingFaceTB/SmolLM2-135M-Instruct", "meta-llama/Llama-3.2-1B-Instruct",
             "google/gemma-3-1b-it"]:
    print(licence_ok(repo)[1])
```

Output:

```
HuggingFaceTB/SmolLM2-135M-Instruct: licence=apache-2.0 OK
meta-llama/Llama-3.2-1B-Instruct: gated (manual), licence=llama3.2 -> needs a human to read the terms
google/gemma-3-1b-it: gated (manual), licence=gemma -> needs a human to read the terms
```

For the offline switch, set `HF_HUB_OFFLINE=1` **before** `transformers` is imported:

```python
# offline.py
import os
os.environ["HF_HUB_OFFLINE"] = "1"              # cache only, never the network

from langchain_huggingface import HuggingFacePipeline

HuggingFacePipeline.from_model_id(model_id="HuggingFaceTB/SmolLM2-135M-Instruct",
                                  task="text-generation")            # cached: loads fine
try:
    HuggingFacePipeline.from_model_id(model_id="Qwen/Qwen2.5-0.5B-Instruct",
                                      task="text-generation")        # not cached
except OSError as e:
    print("OSError:", str(e).splitlines()[0])
```

Output, with nothing from that model in the cache:

```
OSError: We couldn't connect to 'https://huggingface.co' to load the files, and couldn't find them in the cached files.
```

Sometimes only part of a model is cached, such as its `config.json`. Then the error names the
missing file instead: `OSError: Qwen/Qwen2.5-0.5B-Instruct does not appear to have a file named
pytorch_model.bin or model.safetensors.` Both mean the same thing. Download the model while
you are online.

### 5.5 Ollama and other local servers

The same code as [Day 04](../week-01-foundations/day-04-langchain-models.md):

```python
# ⚠️ not executed here — Ollama is not installed on this machine
from langchain_ollama import ChatOllama

model = ChatOllama(model="llama3.2", temperature=0)
print(model.invoke("In one sentence, what is photosynthesis?").content)
```

Measured with no Ollama server running: `invoke` raises `httpx.ConnectError: [WinError 10061]
No connection could be made because the target machine actively refused it`. Exercise 5 turns
that error into a fallback.

### 5.6 The JS ↔ Python translation for today

| Task | JavaScript | Python |
|---|---|---|
| Install the runner | `npm i @huggingface/transformers` | `pip install torch transformers` |
| Weight format used | ONNX (`onnx/*.onnx`) | safetensors (`model.safetensors`) |
| Load a model | `await pipeline("text-generation", id, { dtype: "q4" })` | `AutoModelForCausalLM.from_pretrained(id, dtype=...)` |
| Choose precision | `dtype: "fp32" \| "fp16" \| "q8" \| "q4"` (picks a file) | `dtype=torch.float32 \| torch.bfloat16` (converts on load) |
| Default precision on CPU | fp32 (and unknown strings fall back to fp32) | the model's own `torch_dtype` (bf16 here) |
| Apply the chat template | pass `[{ role, content }]` to the pipeline | `tok.apply_chat_template(messages, add_generation_prompt=True)` |
| Limit the answer | `max_new_tokens: 60` (pipeline default 256) | `max_new_tokens=60` (`generate()` default: 20 new tokens) |
| Repeatable output | `do_sample: false` | `do_sample=False` |
| LangChain chat model | your own `BaseChatModel` subclass (§4.3) | `ChatHuggingFace(llm=HuggingFacePipeline...)` |
| Token counts | you fill `usage_metadata` yourself | `usage_metadata` is `None`; count with `chat.tokenizer` |
| Strip the prompt from output | `generated_text.at(-1).content` | `return_full_text: False` |
| Offline switch | `env.allowRemoteModels = false` | `HF_HUB_OFFLINE=1` before import |
| Licence lookup | `fetch("https://huggingface.co/api/models/<id>")` → `cardData.license`, `gated` | `HfApi().model_info(id)` → `card_data.license`, `gated` |
| Local server client | `new ChatOllama({ model })` | `ChatOllama(model=...)` |
| Free memory | `await generator.dispose()` | `del model` |

---

## 6. Under the hood

### 6.1 Why quantisation speeds up big models but not tiny ones

To produce **one** token, the model must read **every** weight once. For an 8B model in fp16,
that is 16 GB of reading per token. Memory can only deliver so many gigabytes per second, so
for big models the limit is often **memory bandwidth**, not maths. Shrink the weights to 4
bits and there is about four times less to read, so each token can come faster.

Our 135M model is different. Its weights are only 135–540 MB. Fixed costs dominate: the runner
setting up each step, the attention maths, the sampling. Shrinking the weights changed little,
which is what we measured (21.0 vs 23.5 tok/s for fp32 vs q4). Expect the speed gain from
quantisation to grow with model size. We did not measure a large model here, so test yours.

### 6.2 Why the runner matters as much as the dtype

PyTorch ("eager mode") runs each operation as Python asks for it. ONNX Runtime receives the
whole computation graph in advance, fuses steps together and picks optimised kernels for your
CPU. Same weights, same answers in fp32, but 8.2–11.7 tok/s in PyTorch vs 21.0–32.4 tok/s in
ONNX Runtime on this laptop. llama.cpp goes further with hand-written CPU and GPU kernels for each
GGUF quantisation type, which is likely a big part of why Ollama feels fast on laptops.

### 6.3 Where the memory goes

```
  ┌────────────── process memory (bf16, measured: 666 MB) ──────────────┐
  │ libraries: Python + torch + transformers   345 MB                   │
  │ weights                                    269 MB  ← params × bytes │
  │ tokenizer, working buffers, KV cache        ~52 MB  ← grows with    │
  │                                                     context length  │
  └─────────────────────────────────────────────────────────────────────┘
```

For a chat of a few hundred tokens, the KV cache is small. For a 100,000-token context on an
8B model, it can be gigabytes. [Day 30](day-30-inference-and-serving.md) does that arithmetic
and measures it.

### 6.4 Why the chat template lives in the tokenizer

The template is part of how the model was trained, not part of LangChain. So it ships with the
model: in `tokenizer_config.json` for transformers, and inside the GGUF file for llama.cpp
(`tokenizer.chat_template: present`, §3.6). Runners read it from there. That is why the
same `ChatHuggingFace` or `ChatOllama` code works with Llama, Qwen or SmolLM: each model brings
its own markers.

### 6.5 Trust: a model file is a dependency

Downloading a model is like installing a package. Prefer `.safetensors`, ONNX or GGUF files:
they hold data, not code. Older PyTorch `.bin` files use Python's `pickle` format, which can run
code when loaded. Pin the exact repository and revision you tested, because a model repo can
change. [Day 35](day-35-ai-security.md) covers supply-chain security in depth.

> 📚 **Sources** (facts about the world, checked October 2026)
>
> - Model cards and file listings (sizes and licences quoted in §3):
>   <https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct>,
>   <https://huggingface.co/bartowski/SmolLM2-135M-Instruct-GGUF>,
>   <https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF>
> - Open Source Initiative, *The Open Source AI Definition 1.0* (October 2024):
>   <https://opensource.org/ai/open-source-ai-definition>
> - Transformers.js dtypes guide: <https://huggingface.co/docs/transformers.js/guides/dtypes>
> - llama.cpp (GGUF, quantisation types, `llama-server`): <https://github.com/ggml-org/llama.cpp>
> - Ollama: <https://ollama.com>
> - safetensors and why pickle is unsafe: <https://huggingface.co/docs/safetensors>

---

## 7. Common mistakes

### ❌ 1. Sending plain text to a chat model

```python
❌ tok("In one sentence, what is photosynthesis?", return_tensors="pt")      # → '' (measured)
✅ tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
```

```js
❌ await generator("In one sentence, what is photosynthesis?")   // returns the prompt, nothing added
✅ await generator([{ role: "user", content: "In one sentence, what is photosynthesis?" }])
```

An instruct model only works inside its chat template. Without it, today's model ended at once.
The same mistake in LangChain is calling a bare `HuggingFacePipeline` instead of wrapping it in
`ChatHuggingFace`.

### ❌ 2. Trusting the default answer length

```
❌ Python  model.generate(**ids)              → 20 new tokens, then stops mid-sentence
❌ JS      generator(messages)                → up to 256 new tokens; this model wrote 212–255 and repeated itself
✅ both    set max_new_tokens on every call
```

Python warned: `Using the model-agnostic default max_length (=49) to control the generation
length.` That is the 29-token prompt plus 20. The two libraries have **different** defaults, so
code that "works" in one language truncates or rambles in the other.

### ❌ 3. Leaving `return_full_text` at its default

```python
❌ HuggingFacePipeline.from_model_id(..., pipeline_kwargs={"max_new_tokens": 80})
   # AIMessage.content == "<|im_start|>system\nYou are a helpful AI assistant named SmolLM…"
✅ pipeline_kwargs={"max_new_tokens": 80, "return_full_text": False}
```

Without it, every reply carries the whole templated prompt, special markers included. Your
parser, your UI and your token counts all break.

### ❌ 4. A dtype typo in Transformers.js

```js
❌ await pipeline("text-generation", MODEL, { dtype: "int4" })   // no error: loads fp32, 540 MB
✅ await pipeline("text-generation", MODEL, { dtype: "q4" })     // model_q4.onnx, 182 MB
```

An unknown `dtype` string falls back to the default (fp32 on Node's CPU) without an error. Check
which file was downloaded, or watch memory, the first time you use a new dtype.

### ❌ 5. Treating "4-bit" as "params ÷ 2 bytes"

```
❌ Llama 3.1 8B at "4-bit" = 8.03 B × 0.5 bytes = 4.0 GB            → plan for 4 GB
✅ Q4_K_M measured 4,920.7 MB (4.90 bits/param) + runtime + KV cache  → plan for ~5.5 GB+
```

Scales, mixed layers and the runtime all add memory. For tiny models the gap is bigger:
SmolLM2's "Q4_K_M" averaged 6.17 bits per number.

### ❌ 6. Assuming smaller is faster

```
❌ "bf16 is half the size, so it must be faster"   → 6.0 tok/s vs fp32's 8.2 tok/s (PyTorch, this CPU)
✅ measure each dtype on the machine you deploy to, median of several runs
```

On older CPUs without fast bf16 instructions, bf16 can be slower than fp32. For a tiny model,
speed differences between q8, q4 and fp32 were smaller than run-to-run noise.

### ❌ 7. Shipping a model without checking its licence

```python
❌ any model that "looks open" from a blog post
✅ licence_ok(repo) at deploy time: allow-list + gated check (§5.4); a person reads the terms once
```

"Open" weights can come with custom terms (`llama3.1`, `gemma`). A gated repo also fails at
download time without an accepted licence and a token.

### ❌ 8. "Offline mode" that still calls the network

```python
❌ just unplug and hope        → first run of a new model hangs, then fails deep inside a request
✅ HF_HUB_OFFLINE=1 (Python) · env.allowRemoteModels = false (JS) → a fast, clear error at load time
```

Cache the models while online (for example, in your Docker image or install step). Then lock
the library to the cache.

### ❌ 9. Trusting a tiny model's facts

```
❌ return model_answer                                    → "Linus Pauling … in 1953" (invented)
✅ ground it in your notes and check the answer in code   → Exercise 5
```

Small models invent names, numbers and even citation ids (`[bio-3]` when only `bio-1` and
`bio-2` exist). Prompts alone did not stop it. A deterministic check in code did.

### ❌ 10. Comparing runners with different settings

```
❌ JS: sampling on, 60 tokens  vs  Python: greedy, 32 tokens   → "JS is faster!"
✅ same model, same dtype, same prompt, do_sample=False, fixed min/max_new_tokens, median of 3
```

`min_new_tokens` equal to `max_new_tokens` forces the same output length, so tokens per second
compare fairly.

---

## 8. Exercises

### Exercise 1 — Memory arithmetic, by hand and in code ●○○○○

No download needed. Write `gb(params, bitsPerParam)` and a "fits" rule:
`weights + 0.4 GB runtime < 70 % of RAM`. Use RAM = 7.8 GB. Print a table for
SmolLM2-135M (134,515,008 parameters) and Llama 3.1 8B (8,030,261,248) in fp32, fp16/bf16,
Q8_0 (8.5 bits), Q4_K_M (4.9 bits) and Q4_0 (4.5 bits).

Then compare two of your numbers with the real files from §3: Llama Q4_K_M (4,920.7 MB) and
SmolLM2 Q4_K_M (105.5 MB). Which estimate is close, and why is the other one wrong?

<details>
<summary>✅ Solution</summary>

```js
// memory.mjs
const BITS = { fp32: 32, "fp16/bf16": 16, Q8_0: 8.5, Q4_K_M: 4.9, Q4_0: 4.5 };
const gb = (params, bits) => (params * bits) / 8 / 1e9;
const models = { "SmolLM2-135M": 134_515_008, "Llama-3.1-8B": 8_030_261_248 };
const RAM_GB = 7.8, RUNTIME_GB = 0.4;
for (const [name, p] of Object.entries(models)) {
  for (const [fmt, bits] of Object.entries(BITS)) {
    const need = gb(p, bits);
    const fits = need + RUNTIME_GB < RAM_GB * 0.7 ? "fits" : "too big";
    console.log(`${name.padEnd(13)} ${fmt.padEnd(10)} ${need.toFixed(2).padStart(6)} GB  ${fits}`);
  }
}
```

```python
# memory.py
BITS = {"fp32": 32, "fp16/bf16": 16, "Q8_0": 8.5, "Q4_K_M": 4.9, "Q4_0": 4.5}
models = {"SmolLM2-135M": 134_515_008, "Llama-3.1-8B": 8_030_261_248}
RAM_GB, RUNTIME_GB = 7.8, 0.4


def gb(params: int, bits: float) -> float:
    return params * bits / 8 / 1e9


for name, p in models.items():
    for fmt, bits in BITS.items():
        need = gb(p, bits)
        fits = "fits" if need + RUNTIME_GB < RAM_GB * 0.7 else "too big"
        print(f"{name:13s} {fmt:10s} {need:6.2f} GB  {fits}")
```

Output (identical in both languages):

```
SmolLM2-135M  fp32         0.54 GB  fits
SmolLM2-135M  fp16/bf16    0.27 GB  fits
SmolLM2-135M  Q8_0         0.14 GB  fits
SmolLM2-135M  Q4_K_M       0.08 GB  fits
SmolLM2-135M  Q4_0         0.08 GB  fits
Llama-3.1-8B  fp32        32.12 GB  too big
Llama-3.1-8B  fp16/bf16   16.06 GB  too big
Llama-3.1-8B  Q8_0         8.53 GB  too big
Llama-3.1-8B  Q4_K_M       4.92 GB  fits
Llama-3.1-8B  Q4_K_M real file: 4,920.7 MB  ← the estimate is right
SmolLM2-135M  Q4_K_M real file:   105.5 MB  ← the estimate (80 MB) is 25 % too low
```

(The last two lines are the comparison you do by hand.) The Llama estimate works because 4.9
bits was **measured** from that file. For SmolLM2 the same 4.9 is wrong: its rows are 576
numbers wide, so most tensors could not use 4-bit K-quants and got `Q5_0` or `Q8_0` instead
(§3.6). It averaged 6.17 bits. **Why this design:** keep the bits-per-parameter table as data,
and fill it from real files for the model family you use.

</details>

### Exercise 2 — Model-card detective ●●○○○

Write `card(repo)` that returns licence, gated status, parameter count, stored dtype and context
length. Use the Hub API for the first three and the repo's `config.json` for the last two. Run
it on `HuggingFaceTB/SmolLM2-135M-Instruct`, `Qwen/Qwen2.5-0.5B-Instruct` and
`meta-llama/Llama-3.2-1B-Instruct`. Then decide: which could StudyBuddy ship today, with no
legal review?

<details>
<summary>✅ Solution</summary>

```js
// card.mjs
async function card(repo) {
  const info = await (await fetch(`https://huggingface.co/api/models/${repo}`)).json();
  const res = await fetch(`https://huggingface.co/${repo}/resolve/main/config.json`);
  const cfg = res.ok ? await res.json() : null;
  return {
    repo,
    licence: info.cardData?.license,
    gated: info.gated,
    params: info.safetensors?.total,
    dtype: cfg ? (cfg.torch_dtype ?? cfg.dtype) : `config.json -> HTTP ${res.status}`,
    context: cfg?.max_position_embeddings,
  };
}
for (const r of ["HuggingFaceTB/SmolLM2-135M-Instruct", "Qwen/Qwen2.5-0.5B-Instruct", "meta-llama/Llama-3.2-1B-Instruct"]) {
  console.log(await card(r));
}
```

```python
# card.py
import json
from huggingface_hub import HfApi, hf_hub_download


def card(repo: str) -> dict:
    info = HfApi().model_info(repo)
    try:
        cfg = json.load(open(hf_hub_download(repo, "config.json")))
        dtype, ctx = cfg.get("torch_dtype") or cfg.get("dtype"), cfg.get("max_position_embeddings")
    except Exception as e:  # a gated repo refuses the download
        dtype, ctx = f"config.json -> {type(e).__name__}", None
    return {"repo": repo, "licence": info.card_data.license if info.card_data else None,
            "gated": info.gated, "params": info.safetensors.total if info.safetensors else None,
            "dtype": dtype, "context": ctx}


for r in ["HuggingFaceTB/SmolLM2-135M-Instruct", "Qwen/Qwen2.5-0.5B-Instruct",
          "meta-llama/Llama-3.2-1B-Instruct"]:
    print(card(r))
```

Output (Python; JS prints the same values as JS objects):

```
{'repo': 'HuggingFaceTB/SmolLM2-135M-Instruct', 'licence': 'apache-2.0', 'gated': False, 'params': 134515008, 'dtype': 'bfloat16', 'context': 8192}
{'repo': 'Qwen/Qwen2.5-0.5B-Instruct', 'licence': 'apache-2.0', 'gated': False, 'params': 494032768, 'dtype': 'bfloat16', 'context': 32768}
{'repo': 'meta-llama/Llama-3.2-1B-Instruct', 'licence': 'llama3.2', 'gated': 'manual', 'params': 1235814400, 'dtype': 'config.json -> GatedRepoError', 'context': None}
```

In JS the gated repo shows `dtype: 'config.json -> HTTP 401'`.

| Model | Ship today? | Why |
|---|---|---|
| SmolLM2-135M-Instruct | ✅ | apache-2.0, not gated, 269 MB in bf16, 8K context |
| Qwen2.5-0.5B-Instruct | ✅ | apache-2.0, not gated, ~0.99 GB in bf16 (494 M × 2), 32K context |
| Llama-3.2-1B-Instruct | ⏸ | custom `llama3.2` licence, gated: a person accepts and records the terms first |

Notice that the metadata is readable even for the gated model, but the files are not. **Why
this design:** the card check is cheap and runs in CI, so a model swap can't skip it.

</details>

### Exercise 3 — Break it six ways ●●○○○

Predict the symptom, then run each one.

1. Send the question as a plain string, with no chat template.
2. Leave out `max_new_tokens` (Python: `model.generate`; JS: the pipeline).
3. Python: build `HuggingFacePipeline` without `return_full_text: False`. JS: print the whole
   `generated_text` instead of `.at(-1)`.
4. JS: ask for `dtype: "int4"`. Python: ask for 4-bit bitsandbytes on a CPU-only machine.
5. Load Llama 3.1 8B in bf16 on a 7.8 GB laptop. (Do the arithmetic. Don't run it.)
6. Download `config.json` from `meta-llama/Llama-3.2-1B-Instruct` without accepting the licence.

<details>
<summary>✅ Solution</summary>

| # | Symptom (measured) | Why |
|---|---|---|
| 1 | Python `''`; JS returns the prompt with nothing added | No template: the model never sees an open assistant turn, so it ends at once |
| 2 | Python: 20 new tokens, cut mid-sentence, plus a `max_length (=49)` warning. JS: 212 tokens (q4), long and repetitive; the limit is 256 | Different library defaults: `generate()` falls back to 20; the JS text-generation pipeline sets 256 |
| 3 | Python: `content` starts with the whole templated prompt, special markers included. JS: the array holds the user **and** assistant messages, not just the reply | The pipeline returns prompt + answer unless told not to |
| 4 | JS: no error, and the process grows by hundreds of MB (the 540 MB fp32 file). Python: `ImportError: Using bitsandbytes 4-bit quantization requires bitsandbytes` | JS falls back silently on unknown dtypes; bitsandbytes 4-bit targets NVIDIA GPUs |
| 5 | Not run on purpose. Arithmetic: 8,030,261,248 × 2 bytes = 16.06 GB of weights alone | More than twice the RAM. Expect heavy swapping or an out-of-memory crash |
| 6 | Python `GatedRepoError`; JS `HTTP 401` | Gated repos need an accepted licence and an access token |

**Repro — JavaScript**

```js
// breakit.mjs
import { pipeline, env } from "@huggingface/transformers";
env.cacheDir = "./models-cache";
const MODEL = "HuggingFaceTB/SmolLM2-135M-Instruct";
const q = "In one sentence, what is photosynthesis?";
const mb = () => Math.round(process.memoryUsage().rss / 1e6);

const g = await pipeline("text-generation", MODEL, { dtype: "q4" });
const r1 = await g(q, { max_new_tokens: 40, do_sample: false });                       // 1
console.log("1:", JSON.stringify(r1[0].generated_text));

const r2 = await g([{ role: "user", content: "Explain photosynthesis to a ten-year-old." }], { do_sample: false });
const s = r2[0].generated_text.at(-1).content;                                          // 2
console.log("2:", g.tokenizer.encode(s, { add_special_tokens: false }).length, "tokens");

const r3 = await g([{ role: "user", content: q }], { max_new_tokens: 20, do_sample: false });
console.log("3:", r3[0].generated_text.map((m) => m.role).join(", "));                 // 3
await g.dispose();

const before = mb();                                                                    // 4
const g4 = await pipeline("text-generation", MODEL, { dtype: "int4" });
console.log(`4: no error; process grew by ${mb() - before} MB`);
await g4.dispose();

console.log(`5: ${(8_030_261_248 * 2 / 1e9).toFixed(2)} GB of bf16 weights vs 7.8 GB RAM`);   // 5

const res = await fetch("https://huggingface.co/meta-llama/Llama-3.2-1B-Instruct/resolve/main/config.json");
console.log("6: HTTP", res.status);                                                     // 6
```

**Repro — Python**

```python
# breakit.py
import torch
from huggingface_hub import hf_hub_download
from langchain_huggingface import ChatHuggingFace, HuggingFacePipeline
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

MODEL = "HuggingFaceTB/SmolLM2-135M-Instruct"
tok = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForCausalLM.from_pretrained(MODEL)
q = "In one sentence, what is photosynthesis?"


def new_text(ids, out):
    return tok.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=True)


ids = tok(q, return_tensors="pt")                                                       # 1
print("1:", repr(new_text(ids, model.generate(**ids, max_new_tokens=40, do_sample=False))))

prompt = tok.apply_chat_template([{"role": "user", "content": q}], tokenize=False,
                                 add_generation_prompt=True)
ids = tok(prompt, return_tensors="pt")                                                  # 2
out = model.generate(**ids, do_sample=False)
print("2:", out.shape[1] - ids["input_ids"].shape[1], "new tokens:", repr(new_text(ids, out)))

chat = ChatHuggingFace(llm=HuggingFacePipeline.from_model_id(                           # 3
    model_id=MODEL, task="text-generation",
    pipeline_kwargs={"max_new_tokens": 20, "do_sample": False}))
print("3:", repr(chat.invoke(q).content[:70]))

try:                                                                                    # 4
    AutoModelForCausalLM.from_pretrained(MODEL, quantization_config=BitsAndBytesConfig(load_in_4bit=True))
except ImportError as e:
    print("4:", str(e).strip().splitlines()[0])

print(f"5: {8_030_261_248 * 2 / 1e9:.2f} GB of bf16 weights vs 7.8 GB RAM")             # 5

try:                                                                                    # 6
    hf_hub_download("meta-llama/Llama-3.2-1B-Instruct", "config.json")
except Exception as e:
    print("6:", type(e).__name__)
```

Output — Python:

```
1: ''
2: 20 new tokens: 'Photosynthesis is the process by which plants, algae, and some bacteria convert light energy into chemical energy'
3: '<|im_start|>system\nYou are a helpful AI assistant named SmolLM, traine'
4: Using `bitsandbytes` 4-bit quantization requires bitsandbytes: `pip install -U bitsandbytes>=0.46.1`
5: 16.06 GB of bf16 weights vs 7.8 GB RAM
6: GatedRepoError
```

Output — JavaScript:

```
1: "In one sentence, what is photosynthesis?"
2: 212 tokens
3: user, assistant
4: no error; process grew by 574 MB
5: 16.06 GB of bf16 weights vs 7.8 GB RAM
6: HTTP 401
```

**Why this design:** every one of these fails **quietly** except 4 (Python) and 6. Quiet
failures are the expensive ones. So the fixes go into code you write once: a wrapper that
always applies the template and sets `max_new_tokens`, a dtype allow-list, and a licence check.

</details>

### Exercise 4 — Does quantisation hurt? Measure it ●●●○○

Pick three questions with checkable answers. Run them through the same model in several
formats with greedy decoding. JS: `fp32`, `q8`, `q4` ONNX files. Python: fp32, bf16, and
PyTorch's dynamic int8 quantisation (`quantize_dynamic` on the `Linear` layers). Count the
right answers and note any format that behaves strangely.

<details>
<summary>✅ Solution</summary>

```js
// quality.mjs
import { pipeline, env } from "@huggingface/transformers";
env.cacheDir = "./models-cache";
const MODEL = "HuggingFaceTB/SmolLM2-135M-Instruct";
const QS = [
  "In one sentence, what is photosynthesis?",
  "What is 17 * 23? Reply with just the number.",
  "How many letters are in the word 'banana'? Reply with just the number.",
];
for (const dtype of ["fp32", "q8", "q4"]) {
  const g = await pipeline("text-generation", MODEL, { dtype });
  console.log(`== ${dtype}`);
  for (const q of QS) {
    const out = await g([{ role: "user", content: q }], { max_new_tokens: 40, do_sample: false });
    console.log(`   ${q.slice(0, 30).padEnd(30)} -> ${JSON.stringify(out[0].generated_text.at(-1).content.slice(0, 80))}`);
  }
  await g.dispose();
}
```

```python
# quality.py
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL = "HuggingFaceTB/SmolLM2-135M-Instruct"
tok = AutoTokenizer.from_pretrained(MODEL)
QS = ["In one sentence, what is photosynthesis?",
      "What is 17 * 23? Reply with just the number.",
      "How many letters are in the word 'banana'? Reply with just the number."]


def answers(model):
    for q in QS:
        p = tok.apply_chat_template([{"role": "user", "content": q}], tokenize=False,
                                    add_generation_prompt=True)
        ids = tok(p, return_tensors="pt")
        with torch.no_grad():
            out = model.generate(**ids, max_new_tokens=40, do_sample=False)
        text = tok.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=True)
        print(f"   {q[:30]:30s} -> {text[:80]!r}")


fp32 = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32)
print("== fp32"); answers(fp32)
print("== int8 (dynamic)")          # prints a DeprecationWarning: torch.ao.quantization → torchao
answers(torch.ao.quantization.quantize_dynamic(fp32, {torch.nn.Linear}, dtype=torch.qint8))
del fp32
print("== bf16"); answers(AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.bfloat16))
```

Results (measured; right answers are 391 and 6):

| Format | Runner | Photosynthesis | 17 × 23 | Letters in "banana" | Right |
|---|---|---|---|---|---|
| fp32 | ONNX (JS) | good sentence | 421 | 10 | 1 / 3 |
| q8 | ONNX (JS) | **repeats the question** | 381 | 12 | 0 / 3 |
| q4 | ONNX (JS) | good sentence | 426 | 10 | 1 / 3 |
| fp32 | PyTorch | good sentence | 421 | 10 | 1 / 3 |
| bf16 | PyTorch | good sentence | 421 | 10 | 1 / 3 |
| int8 dynamic | PyTorch | good sentence | 429 | "a compound word…" | 1 / 3 |

What you learn:

- **The base model is the ceiling.** fp32 already fails both checkable questions. Quantisation
  can't add knowledge, only lose some.
- **fp32 and bf16 gave identical text** for these prompts. Rounding to 16 bits did not change
  the most likely tokens here.
- **8-bit is not automatically safer than 4-bit.** The ONNX q8 file also rounds the activations
  (§3.6) and did worst.
- `quantize_dynamic` shrank the saved weights from 538.2 MB to 248.1 MB (not 4×: the 28 M
  embedding numbers stay fp32). It also prints a `DeprecationWarning` that points to `torchao`,
  so treat it as a teaching tool, not a production path.

**Why this design:** three questions is a smoke test, not an evaluation. For real decisions,
run your Day 25 dataset through each candidate file and compare scores.

</details>

### Exercise 5 — 🎯 StudyBuddy v6.1: offline mode ●●●●○

StudyBuddy must keep working on the train. Build its offline mode:

1. A model chain: try **Ollama** first (fast, if the student installed it), and fall back to the
   **in-process** model from §4.3 / §5.3 if Ollama is not running.
2. Lock the libraries to the cache, so "offline" really means offline.
3. Ground answers in the student's notes, and add a **code** check: citations must exist, and
   every name or number in the answer must appear in the notes. If the check fails, say so
   instead of showing the answer.

Test with "What do mitochondria do?" and "Who discovered mitochondria?" on notes that don't say
who discovered them.

<details>
<summary>✅ Solution</summary>

```js
// studybuddy-offline.mjs — StudyBuddy v6.1
import { pipeline, env } from "@huggingface/transformers";
import { BaseChatModel } from "@langchain/core/language_models/chat_models";
import { AIMessage } from "@langchain/core/messages";
import { ChatPromptTemplate } from "@langchain/core/prompts";
import { StringOutputParser } from "@langchain/core/output_parsers";
import { ChatOllama } from "@langchain/ollama";

env.cacheDir = "./models-cache";
env.allowRemoteModels = false;                    // offline: read the cache, never the network

const ROLE = { human: "user", ai: "assistant", system: "system" };
class LocalChat extends BaseChatModel {
  constructor({ model, dtype = "q4", maxNewTokens = 80 }) {
    super({}); this.model = model; this.dtype = dtype; this.maxNewTokens = maxNewTokens;
  }
  _llmType() { return "transformers-js"; }
  async _generate(messages) {
    this.generator ??= await pipeline("text-generation", this.model, { dtype: this.dtype });
    const chat = messages.map((m) => ({ role: ROLE[m.getType()], content: m.content }));
    const out = await this.generator(chat, { max_new_tokens: this.maxNewTokens, do_sample: false });
    const text = out[0].generated_text.at(-1).content;
    return { generations: [{ message: new AIMessage(text), text }] };
  }
}

const NOTES = {
  "bio-1": "Mitochondria release energy from food by cellular respiration and store it as ATP.",
  "bio-2": "Chloroplasts carry out photosynthesis, turning light, water and CO2 into glucose.",
};
const notesText = Object.entries(NOTES).map(([id, t]) => `[${id}] ${t}`).join("\n");

// Citations must exist; names and numbers must already be in the notes.
function problems(answer) {
  const fakeIds = [...answer.matchAll(/\[([\w-]+)\]/g)].map((m) => m[1]).filter((id) => !(id in NOTES));
  const body = answer.replace(/\[[\w-]+\]\s*/g, "");
  const starts = new Set(body.split(/[.!?:]\s+|\n+/).map((s) => s.trim().split(/\s+/)[0]));
  const words = body.match(/\b(?:[A-Z][a-z]+|[A-Z]{2,}|\d[\d,.]*)\b/g) ?? [];
  const added = [...new Set(words)].filter((w) => !starts.has(w) && !notesText.includes(w));
  return [...fakeIds.map((id) => `[${id}]`), ...added];
}

const local = new LocalChat({ model: "HuggingFaceTB/SmolLM2-135M-Instruct" });
const model = new ChatOllama({ model: "llama3.2", temperature: 0 }).withFallbacks([local]);

const prompt = ChatPromptTemplate.fromMessages([
  ["system", "You are StudyBuddy. Answer only from these notes and cite the note id.\n{notes}"],
  ["human", "{question}"],
]);
const chain = prompt.pipe(model).pipe(new StringOutputParser());

async function ask(question) {
  const answer = await chain.invoke({ notes: notesText, question });
  const bad = problems(answer);
  if (bad.length) return `⚠️ Not in your notes: ${bad.join(", ")}. Ask again when online.`;
  return `${answer}\n   (offline answer: check it against your notes)`;
}

for (const q of ["What do mitochondria do?", "Who discovered mitochondria?"]) {
  console.log(`Q: ${q}\nA: ${await ask(q)}\n`);
}
```

```python
# studybuddy_offline.py — StudyBuddy v6.1
import os
os.environ["HF_HUB_OFFLINE"] = "1"           # offline: read the cache, never the network

import re
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_huggingface import ChatHuggingFace, HuggingFacePipeline
from langchain_ollama import ChatOllama

local = ChatHuggingFace(llm=HuggingFacePipeline.from_model_id(
    model_id="HuggingFaceTB/SmolLM2-135M-Instruct", task="text-generation",
    pipeline_kwargs={"max_new_tokens": 80, "do_sample": False, "return_full_text": False}))
model = ChatOllama(model="llama3.2", temperature=0).with_fallbacks([local])

NOTES = {
    "bio-1": "Mitochondria release energy from food by cellular respiration and store it as ATP.",
    "bio-2": "Chloroplasts carry out photosynthesis, turning light, water and CO2 into glucose.",
}
notes_text = "\n".join(f"[{i}] {t}" for i, t in NOTES.items())


def problems(answer: str) -> list[str]:
    """Citations must exist; names and numbers must already be in the notes."""
    fake_ids = [i for i in re.findall(r"\[([\w-]+)\]", answer) if i not in NOTES]
    body = re.sub(r"\[[\w-]+\]\s*", "", answer)
    starts = {s.strip().split()[0] for s in re.split(r"[.!?:]\s+|\n+", body) if s.strip()}
    words = re.findall(r"\b(?:[A-Z][a-z]+|[A-Z]{2,}|\d[\d,.]*)\b", body)
    added = [w for w in dict.fromkeys(words) if w not in starts and w not in notes_text]
    return [f"[{i}]" for i in fake_ids] + added


prompt = ChatPromptTemplate.from_messages([
    ("system", "You are StudyBuddy. Answer only from these notes and cite the note id.\n{notes}"),
    ("human", "{question}"),
])
chain = prompt | model | StrOutputParser()


def ask(question: str) -> str:
    answer = chain.invoke({"notes": notes_text, "question": question})
    bad = problems(answer)
    if bad:
        return f"⚠️ Not in your notes: {', '.join(bad)}. Ask again when online."
    return f"{answer}\n   (offline answer: check it against your notes)"


for q in ["What do mitochondria do?", "Who discovered mitochondria?"]:
    print(f"Q: {q}\nA: {ask(q)}\n")
```

Output — JavaScript (Ollama not running, so every call fell back to the in-process q4 model):

```
Q: What do mitochondria do?
A: Mitochondria do the following:

1. Mitochondrial energy production: Mitochondria use the energy from the breakdown of food to produce ATP.

2. Cellular respiration: Mitochondria use the energy from food to produce ATP.

3. Cellular production: Mitochondria produce the energy for the cell to use.

4. Cellular waste: Mitochondria use the energy from
   (offline answer: check it against your notes)

Q: Who discovered mitochondria?
A: ⚠️ Not in your notes: [bio-3], German, Otto, Warburg, 1861. Ask again when online.
```

Output — Python:

```
Q: What do mitochondria do?
A: Mitochondria are the powerhouses of the cell, responsible for generating energy from food and
converting it into ATP (adenosine triphosphate). They are found in the cell's cytoplasm and are
responsible for producing energy in the form of ATP (adenosine triphosphate) through a process
called cellular respiration.

Mitochondria are responsible for producing energy in the form of ATP through a series
   (offline answer: check it against your notes)

Q: Who discovered mitochondria?
A: ⚠️ Not in your notes: Linus, Pauling, Walter, Gilbert, 1953, Nobel, Prize, Chemistry. Ask again when online.
```

What happened, and why it is designed this way:

- **The fallback worked.** Ollama refused the connection (`fetch failed` / `ConnectError`), and
  `withFallbacks` / `with_fallbacks` moved to the in-process model with no extra code. On a
  laptop with Ollama, the first, stronger model would answer instead.
- **The check caught both inventions.** The JS model invented a citation (`[bio-3]`) and a
  "discoverer" with a date. The Python model invented two famous chemists and a year. The
  prompt said "answer only from these notes"; the tiny model ignored it. The **code** check did
  not.
- **The check is deliberately crude.** It catches invented names and numbers, not wrong ideas
  in ordinary words. That is why every offline answer carries a "check it against your notes"
  label. Neither model cited `[bio-1]` either; a stricter version could require a citation.
- **The first answers are cut off** at 80 tokens. That is the `max_new_tokens` limit doing its
  job: a slow, weak model should say less, not more.

StudyBuddy is now **v6.1: runs offline with a local model**, with a guard against invented
facts.

</details>

---

## 9. Interview questions

### Basic

**Q1. What is the difference between an open-weight and an open-source model?**

An open-weight model lets you download the trained weights, under whatever licence the
publisher writes. Training data and code may stay secret. Open-source, in the OSI's Open Source
AI Definition (2024), also requires enough information about data and code to rebuild it, under
an open licence. Most popular "open" models are open-weight. For a product, the licence terms
matter more than the label: `apache-2.0` and `mit` allow commercial use simply, while custom
licences such as `llama3.1` or `gemma` add their own rules.

---

**Q2. How do you estimate how much memory a model needs?**

Parameters × bytes per parameter, plus overhead. An 8B model is 16 GB in bf16 (2 bytes), about
8.5 GB at Q8_0 and about 4.9 GB at Q4_K_M (measured file sizes). Then add the runtime (a few
hundred MB for Python and PyTorch, measured) and the KV cache, which grows with context length.
Keep the total well under free RAM or VRAM.

---

**Q3. What is quantisation, and what does it cost you?**

Storing each weight in fewer bits: 8 or 4 instead of 16 or 32, with a scale per small block.
The model gets 2–8 times smaller, loads faster and often runs faster when memory bandwidth is
the limit. The cost is a small, unpredictable loss of quality. In our test, an 8-bit ONNX file
answered worse than a 4-bit one, so you must evaluate the exact file you ship.

---

**Q4. What is a chat template, and what happens if you skip it?**

The exact text format an instruct model was trained on, with special markers for each role
and an open assistant turn at the end. It ships with the tokenizer (or inside a GGUF file).
Skip it and the model sees text it was never trained on. Today's model returned an empty string
in Python. Use `apply_chat_template` or a wrapper such as `ChatHuggingFace` or Ollama.

---

### Intermediate

**Q5. Why is "Q4_K_M" not exactly 4 bits per weight?**

Each block of numbers also stores a scale (and sometimes a minimum), which adds bits: Q4_K is
4.5 bits per number, Q8_0 is 8.5. "M" means a medium mix in which some sensitive tensors keep
more bits. Measured on Llama 3.1 8B, Q4_K_M averaged 4.90 bits per parameter. On a tiny model
whose rows were not multiples of 256, it averaged 6.17.

---

**Q6. GGUF, ONNX and safetensors: when would you use each?**

safetensors is the standard release format for PyTorch and `transformers`, usually fp32 or
bf16. ONNX is a portable graph format for ONNX Runtime; Transformers.js uses it in Node and the
browser, with q8/q4 variants. GGUF is a single file with weights, tokenizer and chat template,
for llama.cpp, Ollama and LM Studio, with many quantisation levels. Choose the format your
runner reads.

---

**Q7. You halved memory by switching to bf16, but generation got slower. Why?**

Smaller is not automatically faster. On a CPU without fast bf16 instructions, values may be
converted as they are used. We measured fp32 at 8.2–11.7 tok/s and bf16 at 5.8–6.0 tok/s in
PyTorch on a 2018 laptop CPU. Always benchmark dtypes on the deployment hardware, with fixed
output lengths and the median of several runs.

---

**Q8. How do you put a local model behind LangChain in each language?**

Python: `HuggingFacePipeline.from_model_id(..., pipeline_kwargs={"max_new_tokens": …,
"return_full_text": False})`, wrapped in `ChatHuggingFace` so the chat template is applied.
JavaScript: subclass `BaseChatModel` and call a Transformers.js pipeline in `_generate`. Or run
Ollama and use `ChatOllama` in both. After that it is an ordinary Runnable: it works in LCEL,
with fallbacks and in LangGraph.

---

**Q9. When would you choose a local model over a hosted API?**

Choose local when data can't leave your network, or when the app must work offline. It also
pays when steady high volume makes per-token pricing expensive, or when you need a custom or
fine-tuned model at a fixed version. Choose hosted when quality is critical, traffic is low or
spiky, or nobody can run the servers. Many products do both: hosted by default, local as a
fallback or for sensitive data.

---

### Advanced

**Q10. Why does quantisation often speed up large models but barely change tiny ones?**

Generating each token reads every weight once. For large models that reading is often limited
by memory bandwidth, so fewer bytes per weight means faster tokens. For a 135M model, the
weights are small and fixed per-step costs dominate. We measured fp32, q8 and q4 within
run-to-run noise of each other. The benefit grows with model size, so measure at your size.

---

**Q11. Design an "offline mode" for a study app. What can go wrong?**

Cache the model during install, lock the library to the cache (`HF_HUB_OFFLINE=1`,
`env.allowRemoteModels = false`), and chain runners: Ollama if present, an in-process model
otherwise, via `with_fallbacks`. What goes wrong: weaker answers and invented facts, so ground
answers in local notes and verify names and numbers in code. Also: memory limits on old
laptops, first-load time, and stale models with no update path. Label offline answers in the UI.

---

**Q12. Your team wants to ship a Llama-based model in a paid product. What do you check?**

The licence text itself, not just the `llama3.1` label: acceptable-use rules, any user-count
thresholds, attribution and naming requirements. Then that the repo is gated and someone
accepted the terms with a company account, and pin the exact revision. Record the decision,
add an allow-list check in CI, and prefer data-only formats (safetensors, GGUF, ONNX) over
pickle files. A lawyer reads the terms once; code enforces the decision every time.

---

**Q13. How would you choose the quantisation level for production?**

Start from memory: the largest level whose weights, runtime and KV cache at your maximum
context fit with headroom. Then evaluate two or three candidates (for example Q8_0, Q5_K_M and
Q4_K_M) on your own dataset, measuring quality, tokens per second and time to first token on
the target hardware. Pick the smallest file whose quality drop you can accept. Re-run when the
model, runner or hardware changes.

---

## 10. Recap

### What you learned

- ✅ **Open-weight ≠ open-source**, and the **licence** decides what you may ship
  (`apache-2.0`/`mit` vs custom, gated licences)
- ✅ A model card answers five questions: licence, chat or base, size, context, intended use
- ✅ **Memory ≈ parameters × bytes per parameter + runtime + KV cache**; checked within ~2 %
  against real files
- ✅ **Quantisation** stores fewer bits per weight, with a scale per block: Q8_0 = 8.5 bits,
  Q4_K = 4.5, and a real Q4_K_M file averaged 4.90
- ✅ Formats: **safetensors** (transformers) · **ONNX** (Transformers.js) · **GGUF** (llama.cpp,
  Ollama, LM Studio); bitsandbytes/AWQ/GPTQ need an NVIDIA GPU
- ✅ Always use the **chat template**; plain text gave an empty answer
- ✅ Set **`max_new_tokens`** yourself: the defaults differ (20 in Python's `generate`, 256 in the
  JS pipeline)
- ✅ Measure speed on your hardware: bf16 was **slower** than fp32 on this CPU, and dtypes of a
  tiny model were within noise
- ✅ LangChain: `ChatHuggingFace` in Python, a small `BaseChatModel` subclass in JS, `ChatOllama`
  in both
- ✅ Tiny models are confidently wrong; **check facts in code**, not just in the prompt

### One-glance summary

```
  CHOOSE            FIT                         RUN                       TRUST
  licence ✓     params × bytes/param        transformers  (Py, safetensors)   chat template ✓
  gated?        + runtime + KV cache        Transformers.js (JS, ONNX)        max_new_tokens ✓
  instruct?     < ~70 % of free RAM         Ollama / llama.cpp (GGUF, HTTP)   offline lock ✓
  context?      bits: 32·16·8.5·4.5–4.9     → ChatHuggingFace / LocalChat /    check facts in
                                              ChatOllama → LCEL                code ✓
```

### Tomorrow

**[Day 30 — Inference & serving](day-30-inference-and-serving.md)**: today one process ran one
model for one user. Tomorrow you serve a model to many users at once. You will measure time to
first token versus throughput, see how the KV cache and batching use memory, and build your own
OpenAI-compatible server around a local model. You will also meet vLLM and speculative decoding.

### Quick self-check

1. A model card says 3.8 billion parameters, stored as bf16. Roughly how big is the download,
   and about how big is a Q4_K_M version?
2. Your Python chain returns replies that start with `<|im_start|>system`. What is missing?
3. You promised StudyBuddy works on the train. Name two settings (one per language) and one
   code check that make the promise true.

<details>
<summary>Answers</summary>

1. bf16 is 2 bytes per parameter: 3.8 B × 2 ≈ 7.6 GB. Q4_K_M at about 4.9 bits per parameter
   (the value measured on a large model): 3.8 B × 4.9 ÷ 8 ≈ 2.3 GB. Add runtime and KV cache
   when you check whether it fits.

2. `return_full_text: False` in `pipeline_kwargs`. Without it, `HuggingFacePipeline` returns the
   templated prompt plus the answer, so `ChatHuggingFace` puts both into the message content.

3. `HF_HUB_OFFLINE=1` before importing transformers (Python) and `env.allowRemoteModels =
   false` (JS) lock the libraries to the cache. Then fall back from Ollama to the in-process
   model with `with_fallbacks` / `withFallbacks`. And check every answer in code: citations
   must exist, and names and numbers must appear in the notes.

</details>

---

<div align="center">

**[← Day 28 — Capstones & interviews](../week-04-production-projects-and-interviews/day-28-capstones-and-interviews.md)** · **[Week 5 index](README.md)** · **[Day 30 — Inference & serving →](day-30-inference-and-serving.md)**

</div>
