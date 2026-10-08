# Day 30 — Inference & Serving: What Happens Between Request and Token

> ⏱ **Time:** ~3 hours · 🎯 **Prereqs:** [Day 29](day-29-open-and-local-models.md) · 🧩 **Difficulty:** ●●●●○

**Today you learn:** yesterday one student ran one model in one process. Today a whole class
shares one machine, and the eighth student waits 20 seconds for a first word. You find out why.
You measure the two phases of generation (**prefill** and **decode**), switch the **KV cache**
off to see what it saves, and batch eight questions into one pass. You try **speculative
decoding** and report honestly when it does not help. Then you build your own
**OpenAI-compatible server** in Python and call it from JavaScript and Python with LangChain's
`ChatOpenAI`. StudyBuddy v6.2 talks to that server.

> 📖 **Words you'll meet today**
>
> - **Inference** — running a trained model to get an answer. No learning happens.
> - **Prefill** — the first phase: the model reads the whole prompt in one parallel pass.
> - **Decode** — the second phase: the model writes the answer one token at a time.
> - **TTFT (time to first token)** — how long the user waits before the first word appears.
> - **Inter-token latency** — the gap between one streamed token and the next.
> - **Throughput** — how many tokens the server produces per second, for all users together.
> - **KV cache** — the stored attention keys and values of earlier tokens, so they are not
>   computed again.
> - **Continuous batching** — a server adds and removes requests from the running batch after
>   every token step, instead of waiting for a whole batch to finish.
> - **Speculative decoding** — a small "draft" model guesses a few tokens; the big model checks
>   them all in one pass.

> 🧪 **Measured, not recalled.** Every time, speed and answer below was measured on one
> machine: a 4-core Intel i5-8265U laptop CPU with 7.8 GB of RAM and no GPU, running Windows 11.
> Other jobs shared that CPU during some runs, so speeds move by up to about 2× between runs.
> We repeat runs and report medians. Your numbers will differ; the **shape** of the results is
> what matters. Models: `HuggingFaceTB/SmolLM2-135M-Instruct` and `SmolLM2-360M-Instruct`, in
> fp32 (Day 29 §5.2 showed bf16 is slower on this CPU).

---

## 1. The problem

StudyBuddy v6.1 runs offline on one laptop. Now a school wants it for a whole class. The
student notes must stay inside the school, so the model runs on one school machine. You wrap
the model in a small web server, and eight students ask a question at the same moment. Here is
what we measured on our server (§5.7):

```
   one student alone              first word after   0.3 s   whole answer  2.0 s
   eight students at once         first word: p50    9.3 s   p95          20.8 s
   a student pastes 2 pages       first word after   4.2 s   (a short question: 0.7 s) *
   a student gives up after 1 s   the server keeps writing the answer nobody will read;
                                  the next student waits 23 s instead of 1.6 s
```

\* measured in-process, without the web server (§5.1).

Nothing is broken. The model is fast enough for one person. But a model server is a shared
machine, and how you schedule the work decides who waits. The cloud providers you used in
Weeks 1–4 solved these problems for you. Today you see them from the inside.

### The real-life version

Think of a small restaurant kitchen with one chef.

```
   reading the order ticket          fast: the chef reads the whole ticket at once    PREFILL
   cooking the dishes                slow: one plate after another                    DECODE
   a board of prepared ingredients   no need to chop the onions again                 KV CACHE
   cooking eight orders in one pan   each order waits a bit, the kitchen serves more  BATCHING
   new orders join the pan any time  nobody waits for the slowest table to finish     CONTINUOUS BATCHING
   a junior cook prepares ahead      the chef only checks, and throws away mistakes   SPECULATIVE DECODING
   a table leaves before its food    a good kitchen stops cooking that order          CANCELLATION
```

Each of those is a mechanism you will measure today.

---

## 2. Mental model

One request goes through a queue and two very different phases:

```
   request ──► QUEUE ──► PREFILL ─────────────► DECODE (one token per step) ─────────► done
               wait for  read all N prompt       step 1   step 2   step 3  ...  step M
               a free    tokens in ONE pass      │        │        │
               slot      fill the KV cache       ▼        ▼        ▼
                         │                       read the KV cache, add one entry each step
                         ▼
                  first token appears
   ◄──── time to first token (TTFT) ────►◄── inter-token latency × M ──────────────────►
   ◄──────────────────────────── end-to-end latency ──────────────────────────────────►
```

The server's job is to keep the machine busy for **many** requests at once, without making any
single user wait too long. Those two goals pull against each other.

| Idea | In one sentence | Measured today |
|---|---|---|
| Prefill | Reading the prompt is parallel, so it is fast per token | ~210 prompt tokens/s vs ~6–9 output tokens/s (§3.1) |
| Decode | Writing is serial: each token needs the one before it | inter-token gap ~50–110 ms (§3.1) |
| KV cache | Store keys and values so old tokens are not recomputed | 8.8× faster for 64 tokens; 45 KB per token (§3.2) |
| Batching | One pass serves several requests | 3.7–4.2× more tokens/s at batch 8 than batch 1 (§3.3) |
| Continuous batching | Requests join and leave the batch at every step | concept + docs; vLLM not executed here (§3.4) |
| Speculative decoding | Draft cheap, verify in bulk | 0.53–0.88× (slower!) on open text, 1.17× on copying (§3.5) |
| Latency metrics | TTFT, inter-token latency, p50 / p95 | p95 TTFT 20.8 s for 8 users on a one-at-a-time server (§3.6) |
| OpenAI-compatible API | One URL shape that every client already speaks | `ChatOpenAI` → our FastAPI server (§3.7) |

---

## 3. First principles

### 3.1 Two phases: prefill and decode

> 💬 **In plain words:** first the model reads your whole prompt at once. That is quick. Then it
> writes the answer one token at a time. That is slow, because each new token needs the last one.

[Day 01](../week-01-foundations/day-01-llms-tokens-and-inference.md) §3.7 showed that each token
looks back at the tokens before it. During **prefill**, all prompt tokens are already known.
So the model can process all of them in one big matrix multiplication. Hardware loves that.

During **decode**, the model cannot write token 5 before it knows token 4. So it runs one full
pass through the network for every output token. That is a loop, and loops are slow.

We measured both with a *streamer*: an object that hands us each piece of text as soon as it is
generated (§5.1). We asked for 32 new tokens each time and took the median of five runs:

```
   prompt length    TTFT (prefill + first token)    decode speed
     34 tokens          698 ms                        8.6 tokens/s
    248 tokens        1,414 ms                        8.4 tokens/s
    878 tokens        4,160 ms                        5.6 tokens/s
```

Three things to see:

1. **TTFT grows with prompt length.** 878 tokens took 4.2 s before the first word. A user feels
   that. This is why "paste the whole textbook" makes chat feel slow, even before cost.
2. **Prefill is far faster per token than decode.** 878 tokens in about 4.2 s is roughly 210
   tokens per second. Decode managed 5.6. That ratio, about 38×, is the parallel-vs-serial gap.
3. **Decode slows down a little as the context grows.** Each new token must look at every
   earlier key and value. More context means more to read.

> 💡 **This explains provider prices.** Day 01 §6 said input tokens are cheaper than output
> tokens. Now you have measured why: input tokens are processed in bulk; output tokens one by
> one.

> 🧪 **A side note on dtype.** In a first run we forgot `dtype=torch.float32`, so transformers
> loaded the model in its stored bf16. The 878-token prompt then took **41.5 s** to the first
> token instead of 4.2 s. Day 29 §5.2 explains why bf16 is slow on this CPU. Measure on your
> real hardware.

### 3.2 The KV cache: memory traded for speed

> 💬 **In plain words:** the model saves some numbers for every token it has already seen. Then
> it does not need to compute them again for each new token. This costs memory.

In attention, every token produces a *key* and a *value* (Day 01 §3.7). In a model that only
looks backwards, these never change once computed. So the server keeps them in memory. That
store is the **KV cache**. Each decode step then computes the key and value for **one** new
token, and reads the rest from the cache.

Without the cache, every step would redo the whole sequence. We switched it off with
`use_cache=False` (§5.2), on a 248-token prompt, median of three runs:

```
   new tokens    cache ON    cache OFF    OFF / ON    same output?
       16         2.18 s      12.95 s       5.9×          True
       64         6.70 s      58.75 s       8.8×          True
```

The answer is identical; only the time changes. And the gap **grows** with length, because
without a cache, step *k* recomputes all *k* earlier tokens.

**The price is memory.** For each token, each layer stores one key and one value per *KV head*:

```
   bytes per token = 2 (key + value) × layers × KV heads × head size × bytes per number

   SmolLM2-135M, fp32:  2 × 30 × 3 × 64 × 4 bytes = 46,080 bytes ≈ 45 KB per token
```

We measured the real cache object after a batch of 8 sequences of 68 positions: **25.1 MB,
which is exactly 45.0 KB per token**. The formula is right.

Now scale it. Qwen2.5-7B-Instruct's `config.json` says 28 layers, 4 KV heads, head size 128,
stored in bf16 (2 bytes):

```
   2 × 28 × 4 × 128 × 2 bytes = 57,344 bytes = 56 KB per token
   one full 32,768-token context  = 1.75 GiB of KV cache — for ONE user
```

That is the core problem of serving. The weights are a fixed cost. The KV cache grows with
every user and every token. **The KV cache, not the weights, decides how many users fit on
one GPU.**

> 💡 **Why "KV heads" is smaller than "attention heads".** SmolLM2 has 9 attention heads but
> only 3 KV heads. Qwen2.5-7B has 28 and 4. Several query heads share one key/value head. This
> is called *grouped-query attention*, and its main purpose is to shrink the KV cache.

### 3.3 Batching: serving many is cheaper per token

> 💬 **In plain words:** one pass through the model can work on several questions at once. Each
> question gets a little slower, but the machine finishes far more work per second.

Remember the decode loop: every step reads **all** the weights. With one request, you read all
the weights to make one token. With eight requests in one batch, you read the weights once and
make eight tokens. We measured it (§5.3), 32 new tokens per question, median of three runs,
in two sessions:

```
   batch size    wall time    total throughput    per-request speed
       1          2.58 s        12.4 tokens/s       12.4 tokens/s      first session
       4          3.84 s        33.4 tokens/s        8.3 tokens/s
       8          4.90 s        52.2 tokens/s        6.5 tokens/s

       1          1.61 s        19.9 tokens/s       19.9 tokens/s      second, quieter session
       4          2.80 s        45.7 tokens/s       11.4 tokens/s
       8          3.49 s        73.4 tokens/s        9.2 tokens/s
```

Total throughput went up **3.7–4.2×**. Each request got about half as fast. That is the central
trade-off of serving: **throughput versus latency per user.** A batch of 8 is worse for any one
student and much better for the class.

To batch prompts of different lengths, you **pad** the short ones with filler tokens so they
line up. For a model that generates text, the padding must go on the **left**, so every row
ends with real text and the next token follows real text. The tokenizer's default here is
`padding_side="right"`. §7 shows what that does: the answer to "Hi" becomes `'\n'`.

> ⚠️ **Server batching is not Day 34's batching.** Day 34 sends many requests from the
> *client* at once (`batch`, `maxConcurrency`). Today's batching happens *inside the server*:
> many requests share one forward pass. A client can send eight requests in parallel and still
> get them served one by one, as you will see in §3.6.

### 3.4 Continuous batching and paged KV memory

> 💬 **In plain words:** a good server does not wait for a whole batch to finish. When one
> answer is done, a new request takes its place at the next step.

The simple batching in §3.3 is **static batching**: collect requests, run them together, return
them together. Two problems:

```
   STATIC BATCHING (a batch of 4, each row = one request, █ = one decode step)
   req A  ████████████████████████████  (long answer)
   req B  ██████░░░░░░░░░░░░░░░░░░░░░░  done early, but its slot sits idle (░) until A ends
   req C  ███████████░░░░░░░░░░░░░░░░░
   req D  ████░░░░░░░░░░░░░░░░░░░░░░░░
   req E  waiting …………………………………………………… joins only when the whole batch ends

   CONTINUOUS BATCHING (the scheduler decides again after EVERY step)
   slot 1 ████████████████████████████  A
   slot 2 ██████ E███████████ G████████  B ends → E joins at the next step
   slot 3 ███████████ F████████████████
   slot 4 ████ H██████████████████ I███
```

1. **Short answers wait for the longest one.** Our micro-batching server (Exercise 4) shows it:
   all eight requests finished at the same moment, so p50 equalled p95.
2. **New requests wait for the whole batch.** A new student cannot join until the batch ends.

**Continuous batching** fixes both. The Orca paper (OSDI 2022) called it *iteration-level
scheduling*. Its scheduler "invokes the execution engine to run only a single iteration of the
model on the batch." After every token step, finished requests leave and waiting requests join.

That creates a memory problem. Requests now come and go at random, with KV caches of every
size. Reserving one big block of memory per request wastes most of it. **PagedAttention**, from
the vLLM paper (SOSP 2023), stores the KV cache in small fixed-size *pages*, like an operating
system stores memory. The paper reports "near-zero waste in KV cache memory" and 2–4× higher
throughput than earlier systems at the same latency. Those are the paper's numbers on GPUs, not
ours.

vLLM, SGLang, TGI and llama.cpp's server all do continuous batching. That is the main reason not
to write your own production server: today's server (§5.5) handles **one** request at a time.

> ⚠️ **vLLM was not executed here.** Its docs list "OS: Linux" and say "vLLM does not support
> Windows natively" (use WSL). Its GPU builds need a supported GPU. Below is the canonical launch
> command from the vLLM docs. It was *not run on this machine*.
>
> ```bash
> # not executed here — needs Linux and a supported GPU
> vllm serve NousResearch/Meta-Llama-3-8B-Instruct --dtype auto --api-key token-abc123
> # serves an OpenAI-compatible API at http://localhost:8000/v1
> ```

### 3.5 Speculative decoding: guess cheap, check in bulk

> 💬 **In plain words:** a small model quickly guesses the next few tokens. The big model checks
> all the guesses in one pass, keeps the ones it agrees with, and fixes the first wrong one.

Decode is slow because it is serial. Prefill is fast because it is parallel. Speculative
decoding turns some decode work into prefill-style work:

```
   1. the DRAFT model (small, fast) writes 5 tokens:      "is  the  power house  of"
   2. the TARGET model (big) reads all 5 in ONE pass and checks each position:
                                                           ✔    ✔    ✔     ✘
   3. keep the 3 accepted tokens, use the target's own token at position 4, repeat
```

With greedy decoding, the output is **exactly** what the target would write alone. The paper
by Leviathan, Kalman and Matias (ICML 2023) reported 2–3× faster generation on T5-XXL with
"identical outputs". In transformers you pass `assistant_model=` to `generate()`.

We tried it with SmolLM2-360M as the target and SmolLM2-135M as the draft (same tokenizer), on
CPU, greedy, max 64 tokens, median of three runs. We ran the whole test twice:

```
   prompt                               target alone    with draft     speed-up   identical?
   "Explain photosynthesis to a          4.4 tok/s       3.9 tok/s      0.88×        True
    12-year-old."                        5.7 tok/s       3.1 tok/s      0.53×        True
   "Repeat this sentence exactly,        7.8 tok/s       9.2 tok/s      1.17×        True
    three times: The mitochondria…"      7.3 tok/s       8.6 tok/s      1.18×        True
```

**On this CPU, speculative decoding made open-ended answers slower.** It helped a little when
the answer copied the prompt. Here is why:

- **The draft is not much cheaper.** 135M vs 360M is only 2.7× smaller. The transformers docs
  say it "works best when the assistant model is significantly smaller than the main model".
  Their own example pairs a 1B draft with an 8B target.
- **On a CPU, checking 5 tokens is not free.** On a GPU, decode of a big model is limited by
  memory reads. So in theory a pass over 5 tokens costs about the same as a pass over 1 (§6.1).
  That is the whole trick. On this
  CPU, the maths itself is the bottleneck, so verifying 5 tokens costs much more than 1.
- **The draft must guess right.** For open text, a tiny draft often disagrees with the target.
  Every rejected guess is wasted work.

A draft-free variant, **prompt lookup decoding** (`prompt_lookup_num_tokens=10`), guesses by
copying matching text from the prompt. On the copy-heavy prompt it was **2.97×** faster
(9.0 → 26.7 tok/s). On the open question it was 0.80×. Same lesson: speculation pays only when
guesses are cheap **and** usually right.

> ⚠️ transformers refuses batches here: `ValueError: assisted generate is only supported for
> batch_size = 1`. Server engines offer speculative decoding as an option too (llama.cpp's
> server README lists it). How it interacts with their batching is engine-specific — read
> their docs and measure.

### 3.6 The latency numbers that matter

> 💬 **In plain words:** measure the wait for the first word, the gap between words, and the
> total time. Report the median and the slow tail (p95), never only the average.

| Metric | What the user feels | Driven by |
|---|---|---|
| **TTFT** | "Is it working?" — the blank screen | queue wait + prefill (prompt length) |
| **Inter-token latency (ITL)** | reading speed while text streams | decode step time, batch size |
| **End-to-end latency** | total wait for a full answer | TTFT + ITL × output tokens |
| **Throughput** | how many students one machine serves | batching, KV memory |

Report each one as **p50 and p95** ([Day 0C](../week-00-start-here/day-00c-just-enough-maths.md)
§3.10): the mean hides the student who waited 20 seconds. Here is our §5.5 server, which runs
one request at a time, with eight students asking at once (24 tokens each, streamed):

```
                     TTFT p50     TTFT p95     total p50    total p95    gap p50   gap p95
   one alone          305 ms         —          2.01 s          —           —         —
   8 at once        9,312 ms    20,779 ms      13.15 s      22.31 s      100 ms    243 ms
   (second run)     5,445 ms    13,025 ms       7.09 s      14.51 s       71 ms    141 ms
```

The first student still got a first word in about 0.3 s. The last one waited 13–21 s. The
inter-token gap moved much less: once your turn comes, generation runs at about normal speed.
**Almost all of the p95 is queueing.** That is what batching (Exercise 4) and continuous batching (§3.4) attack.

These connect to earlier days: [Day 23](../week-04-production-projects-and-interviews/day-23-streaming-and-events.md)
streams tokens to the browser, so TTFT is what the user sees first;
[Day 27](../week-04-production-projects-and-interviews/day-27-deployment-and-architecture.md)
§3.7 does capacity arithmetic. With your own server, "provider rate limit" becomes "how many
requests fit in my batch and KV memory".

> ⚠️ **A "chunk" is not always a token.** Our server streams text through transformers'
> `TextIteratorStreamer`, which holds text back until a word is complete. So one chunk is about
> one word, and "inter-token" latency here is really "inter-chunk". Hosted APIs usually send
> roughly one token per chunk.

### 3.7 The OpenAI-compatible API: one shape everybody speaks

> 💬 **In plain words:** most model servers copy the request and response format of OpenAI's
> chat API. So one client library can talk to all of them. You only change the address.

The contract is small:

```
   POST {base_url}/chat/completions          base_url ends in /v1, e.g. http://127.0.0.1:8030/v1
   body:  { "model": "...", "messages": [{"role": "user", "content": "..."}],
            "max_tokens": 40, "temperature": 0, "stream": false }

   stream=false → one JSON:  choices[0].message.content, choices[0].finish_reason, usage{...}
   stream=true  → Server-Sent Events, one "data: {json}" line per chunk:
                  data: {"choices":[{"delta":{"role":"assistant","content":""}}]}
                  data: {"choices":[{"delta":{"content":"Hello! "}}]}
                  ...
                  data: {"choices":[{"delta":{},"finish_reason":"stop"}]}
                  data: [DONE]
```

Ollama, llama.cpp's `llama-server`, vLLM, SGLang and TGI all serve this shape. So does our
FastAPI server in §5.5. That is why the same LangChain class, `ChatOpenAI`, works for all of
them:

```
   ChatOpenAI(base_url="http://localhost:11434/v1")   Ollama        (from its docs)
   ChatOpenAI(base_url="http://localhost:8080/v1")    llama-server  (from its docs)
   ChatOpenAI(base_url="http://localhost:8000/v1")    vLLM          (from its docs)
   ChatOpenAI(base_url="http://localhost:30000/v1")   SGLang        (from its docs)
   ChatOpenAI(base_url="http://127.0.0.1:8030/v1")    our server    (verified today)
```

> ⚠️ **"Compatible" means "mostly compatible".** Each server supports a different subset: tool
> calls, JSON mode, `logprobs`, usage while streaming. Ollama's docs, for example, say it does
> not support `logprobs`. Our server returns `usage` only without streaming. Test the features
> you rely on.

### 3.8 Choosing a serving stack

> 💬 **In plain words:** use a laptop runner for one person and a GPU server engine for many
> people. Use a managed service when you don't want to run machines at all.

| You need | Pick | Why | Watch out for |
|---|---|---|---|
| One user, a laptop, offline | **Ollama** or **llama.cpp** (`llama-server`) | GGUF quantised models, CPU or small GPU, one command | Small models are weak (Day 29 §3.9) |
| Many users, your own GPUs | **vLLM** or **SGLang** | Continuous batching, paged KV cache, OpenAI-compatible API | Linux + GPU; you run it, you patch it |
| An existing TGI deployment | keep **TGI**, plan a move | It still works | Its docs say TGI "is now in maintenance mode" and recommend vLLM or SGLang |
| No machines to run | a **managed endpoint** (a provider's API, or a hosted open model) | Someone else does batching, scaling, uptime | Data leaves your network; price per token |
| A tiny model for tests and demos | your own FastAPI wrapper (today) | You learn the contract | One request at a time, no batching, not for production |

All rows in the first four lines come from the projects' own documentation (see Sources). We
ran none of them here except the last row.

---

## 4. Code — JavaScript

```bash
npm install @langchain/openai @langchain/core
# verified with @langchain/openai 1.6.2 · @langchain/core 1.2.17 · openai 7.30.0 · Node 24.15
```

> 🐍 **Why Python only for the engine.** The measurements in §5.1–§5.4 use PyTorch and
> transformers, and the server engines you would use in production (vLLM, SGLang) are Python
> tools. So today the **server** is Python. The **client** — what your app actually runs — is
> JavaScript here, and it talks to the Python server over HTTP. Start the server from §5.5
> first: `python server.py`.

### 4.1 Talk to your own server with `ChatOpenAI`

`ChatOpenAI` is LangChain's client for the OpenAI API. Point it at your server instead:

```js
// client.mjs — LangChain's ChatOpenAI pointed at our own server.
import { ChatOpenAI } from "@langchain/openai";

const llm = new ChatOpenAI({
  model: "smollm2-135m",
  apiKey: "not-needed",                                    // required by the client, ignored by our server
  configuration: { baseURL: "http://127.0.0.1:8030/v1" },  // ends in /v1
  temperature: 0,
  maxTokens: 40,
  timeout: 60_000,                                         // milliseconds in JS
});

const reply = await llm.invoke("In one sentence, what is photosynthesis?");
console.log("content:", reply.content);
console.log("usage:  ", reply.usage_metadata);
console.log("finish: ", reply.response_metadata.finish_reason);
```

Output:

```
content: Photosynthesis is the process by which plants, algae, and some bacteria convert light energy into chemical energy, which is then used to produce glucose and oxygen.
usage:   {
  output_tokens: 32,
  input_tokens: 38,
  total_tokens: 70,
  input_token_details: { audio: undefined, cache_read: undefined },
  output_token_details: { audio: undefined, reasoning: undefined }
}
finish:  stop
```

The `usage` numbers come from **our** server: it counted 38 prompt tokens (after the chat
template) and 32 answer tokens. LangChain mapped them into the usual `usage_metadata`.

> 📦 In JS the base URL lives inside `configuration: { baseURL }`, which is passed to the
> underlying `openai` package. Python uses a top-level `base_url=`. The API key is required by
> the client library even when the server ignores it, so pass any string.

### 4.2 Stream, and measure TTFT and inter-token latency

```js
// client.mjs (continued) — streaming
const t0 = performance.now();
let first = null, n = 0;
const parts = [];
for await (const chunk of await llm.stream("Name three planets.")) {
  if (chunk.content) {
    first ??= performance.now() - t0;
    n += 1;
    parts.push(JSON.stringify(chunk.content));
  }
}
console.log(parts.join(" "));
console.log(`chunks: ${n}   time to first chunk: ${Math.round(first)} ms`);
```

Output:

```
"Here " "are " "three " "planets:\n\n" "1. " "**Mercury**: " "The " "closest " "planet " "to " "Earth, " "with " "a " "diameter " "of " "about " "4,320 " "kilometers. " "It's " "the " "closest " "planet " "to " "the " "Sun " "and"
chunks: 26   time to first chunk: 306 ms
```

Two honest notes. The chunks are words, not tokens (§3.6). And the facts are wrong: Mercury's
diameter is about 4,880 km, not 4,320. A 135M model is a plumbing test, not a tutor
(Day 29 §3.9).

Now measure prefill from the client side. A long prompt should raise TTFT but not the gap
between words:

```js
// ttft.mjs — time to first token and inter-token latency, seen from the client.
import { ChatOpenAI } from "@langchain/openai";

const llm = new ChatOpenAI({
  model: "smollm2-135m", apiKey: "not-needed", temperature: 0, maxTokens: 32,
  configuration: { baseURL: "http://127.0.0.1:8030/v1" },
});

const median = (xs) => [...xs].sort((a, b) => a - b)[Math.floor(xs.length / 2)];

async function measure(prompt) {
  const t0 = performance.now();
  const stamps = [];
  for await (const chunk of await llm.stream(prompt)) {
    if (chunk.content) stamps.push(performance.now() - t0);
  }
  const gaps = stamps.slice(1).map((t, i) => t - stamps[i]);
  return { ttft: stamps[0], itl: median(gaps), total: stamps.at(-1) };
}

const fact = "Photosynthesis turns light, water and carbon dioxide into sugar and oxygen. ";
const prompts = {
  short: "What is photosynthesis?",
  long: fact.repeat(60) + "In one sentence, what is photosynthesis?",
};

await measure("Hi");                                   // warm-up
for (const [name, p] of Object.entries(prompts)) {
  const runs = [];
  for (let i = 0; i < 3; i++) runs.push(await measure(p));
  console.log(`${name.padEnd(5)}  TTFT ${median(runs.map((r) => r.ttft)).toFixed(0).padStart(5)} ms   ` +
              `inter-token ${median(runs.map((r) => r.itl)).toFixed(0).padStart(4)} ms   ` +
              `last token at ${(median(runs.map((r) => r.total)) / 1000).toFixed(2)} s`);
}
```

Output:

```
short  TTFT   270 ms   inter-token   63 ms   last token at 2.07 s
long   TTFT  2447 ms   inter-token   73 ms   last token at 4.26 s
```

The long prompt (about 880 tokens) made the first word **9× later**. The gap between words
hardly changed. That is prefill and decode, seen from the outside.

### 4.3 Eight students at once: p50 and p95

```js
// load.mjs — 8 students ask at the same moment. TTFT and total time, p50 / p95.
import { ChatOpenAI } from "@langchain/openai";

const llm = new ChatOpenAI({
  model: "smollm2-135m", apiKey: "not-needed", temperature: 0, maxTokens: 24,
  configuration: { baseURL: process.env.BASE_URL ?? "http://127.0.0.1:8030/v1" },
});

const questions = ["What is photosynthesis?", "Why is the sky blue?", "What is a prime number?",
  "What does a cell membrane do?", "What is gravity?", "Why do we have seasons?",
  "What is an atom?", "What is evaporation?"];

// nearest-rank percentile, as in Day 0C §3.10
const pct = (xs, p) => [...xs].sort((a, b) => a - b)[Math.ceil((p / 100) * xs.length) - 1];

async function ask(q) {
  const t0 = performance.now();
  let ttft = null;
  for await (const chunk of await llm.stream(q)) {
    if (chunk.content && ttft === null) ttft = performance.now() - t0;
  }
  return { ttft, total: performance.now() - t0 };
}

await ask("Hi");                                       // warm-up
const alone = await ask(questions[0]);
console.log(`alone:     TTFT ${alone.ttft.toFixed(0)} ms   total ${(alone.total / 1000).toFixed(2)} s`);

const t = performance.now();
const results = await Promise.all(questions.map(ask)); // all 8 at once
const wall = (performance.now() - t) / 1000;
const ttfts = results.map((r) => r.ttft), totals = results.map((r) => r.total / 1000);
console.log(`8 at once: TTFT p50 ${pct(ttfts, 50).toFixed(0)} ms   p95 ${pct(ttfts, 95).toFixed(0)} ms`);
console.log(`           total p50 ${pct(totals, 50).toFixed(2)} s   p95 ${pct(totals, 95).toFixed(2)} s   wall ${wall.toFixed(2)} s`);
```

Output:

```
alone:     TTFT 284 ms   total 1.67 s
8 at once: TTFT p50 4769 ms   p95 11234 ms
           total p50 6.08 s   p95 12.54 s   wall 12.54 s
```

The client sent all eight at once. The server answered them one after another. The p95 student
waited **40×** longer for a first word than a student alone.

### 4.4 Timeouts and retries: fail fast, on purpose

Two client settings decide what happens when the server is slow or gone: `timeout` and
`maxRetries`. Their defaults surprised us:

```js
// retrytime.mjs — what the defaults do against a server that is down
import { ChatOpenAI } from "@langchain/openai";
const llm = new ChatOpenAI({ model: "m", apiKey: "x", configuration: { baseURL: "http://127.0.0.1:8099/v1" } });
const t = performance.now();
try { await llm.invoke("hi"); } catch (e) { console.log(`default retries: ${e.message} after ${((performance.now()-t)/1000).toFixed(1)} s`); }
```

Output:

```
default retries: Connection error. after 93.0 s
```

**93 seconds** to say "the server is down". `ChatOpenAI` in JS defaults to `maxRetries: 6`, with
growing waits between tries. The same request with `maxRetries: 0` failed in **0.0 s**:

```js
const fast = new ChatOpenAI({ model: "smollm2-135m", apiKey: "not-needed", maxRetries: 0,
                              configuration: { baseURL: "http://127.0.0.1:8099/v1" } });
// → Error: Connection error.  after 0.0 s

const impatient = new ChatOpenAI({ model: "smollm2-135m", apiKey: "not-needed", maxRetries: 0,
                                   timeout: 1000, maxTokens: 200,
                                   configuration: { baseURL: "http://127.0.0.1:8030/v1" } });
await impatient.invoke("Write a long essay about the history of Rome.");
// → TimeoutError: Request timed out.  after 1.0 s
```

> ⚠️ **A client timeout does not stop the server.** When the client above gave up after 1 s, a
> server without cancellation kept writing the full 200-token essay. The next student waited for
> it (§5.8). Timeouts protect the client; **cancellation** protects the server.

---

## 5. Code — Python

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install transformers fastapi uvicorn httpx langchain-openai
# verified with torch 2.14.1+cpu · transformers 5.19.0 · fastapi 0.142.2 · uvicorn 0.54.0
#               httpx 0.28.1 · langchain-openai 1.6.7 · openai 3.26.0 · langchain-core 1.6.7
#               Python 3.14 · models cached in HF_HOME on a bigger drive
```

§5.1–§5.4 measure the engine. §5.5 builds the server. §5.6–§5.8 are the same client code as
§4.1–§4.4.

### 5.1 Prefill vs decode, measured

`TextIteratorStreamer` hands text to us as it is generated. `generate()` runs in a background
thread, and the main thread notes the time of each piece:

```python
# p1_phases.py — measure prefill (TTFT) and decode (tokens/sec) with a streamer.
import time, threading, statistics, torch
from transformers import AutoTokenizer, AutoModelForCausalLM, TextIteratorStreamer

MODEL = "HuggingFaceTB/SmolLM2-135M-Instruct"
tok = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32)
model.eval()

N = 32
def run(question):
    msgs = [{"role": "user", "content": question}]
    inputs = tok.apply_chat_template(msgs, add_generation_prompt=True,
                                     return_tensors="pt", return_dict=True)
    streamer = TextIteratorStreamer(tok, skip_prompt=True, skip_special_tokens=True)
    kw = dict(**inputs, max_new_tokens=N, min_new_tokens=N, do_sample=False, streamer=streamer)
    t0 = time.perf_counter()
    worker = threading.Thread(target=model.generate, kwargs=kw)
    worker.start()
    stamps = [time.perf_counter() - t0 for piece in streamer if piece]
    worker.join()
    total = time.perf_counter() - t0
    ttft = stamps[0]
    decode_rate = (N - 1) / (total - ttft)
    return inputs["input_ids"].shape[1], ttft, decode_rate

run("Hi")  # warm-up: the first call pays one-off setup costs
fact = "Photosynthesis turns light, water and carbon dioxide into sugar and oxygen. "
prompts = {"short": "What is photosynthesis?",
           "medium": fact * 15 + "In one sentence, what is photosynthesis?",
           "long": fact * 60 + "In one sentence, what is photosynthesis?"}
results = {k: [] for k in prompts}
for _ in range(5):                       # interleave runs so background load hits all equally
    for name, q in prompts.items():
        results[name].append(run(q))
for name, rows in results.items():
    print(f"{name:6} prompt={rows[0][0]:4} tokens   "
          f"TTFT median={statistics.median(r[1] for r in rows)*1000:5.0f} ms   "
          f"decode median={statistics.median(r[2] for r in rows):4.1f} tok/s")
```

Output:

```
short  prompt=  34 tokens   TTFT median=  698 ms   decode median= 8.6 tok/s
medium prompt= 248 tokens   TTFT median= 1414 ms   decode median= 8.4 tok/s
long   prompt= 878 tokens   TTFT median= 4160 ms   decode median= 5.6 tok/s
```

`min_new_tokens=N` stops the model from ending early, so every run writes exactly 32 tokens and
the speeds compare fairly.

### 5.2 The KV cache, on and off

```python
# p2_kvcache.py — the same generation with and without the KV cache.
import time, statistics, torch
from transformers import AutoTokenizer, AutoModelForCausalLM

MODEL = "HuggingFaceTB/SmolLM2-135M-Instruct"
tok = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32).eval()

fact = "Photosynthesis turns light, water and carbon dioxide into sugar and oxygen. "
msgs = [{"role": "user", "content": fact * 15 + "In one sentence, what is photosynthesis?"}]
inputs = tok.apply_chat_template(msgs, add_generation_prompt=True,
                                 return_tensors="pt", return_dict=True)
print("prompt tokens:", inputs["input_ids"].shape[1])

def gen(n, use_cache):
    t = time.perf_counter()
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=n, min_new_tokens=n,
                             do_sample=False, use_cache=use_cache)
    return time.perf_counter() - t, out

gen(4, True)  # warm-up
for n in [16, 64]:
    times = {True: [], False: []}
    outs = {}
    for _ in range(3):
        for flag in (True, False):
            secs, outs[flag] = gen(n, flag)
            times[flag].append(secs)
    on, off = statistics.median(times[True]), statistics.median(times[False])
    print(f"{n:3} new tokens   cache ON {on:5.2f} s   cache OFF {off:6.2f} s   "
          f"OFF/ON = {off/on:4.1f}x   same tokens: {torch.equal(outs[True], outs[False])}")
```

Output:

```
prompt tokens: 248
 16 new tokens   cache ON  2.18 s   cache OFF  12.95 s   OFF/ON =  5.9x   same tokens: True
 64 new tokens   cache ON  6.70 s   cache OFF  58.75 s   OFF/ON =  8.8x   same tokens: True
```

### 5.3 Batching 1, 4 and 8 questions

```python
# p3_batching.py — throughput of 1, 4 and 8 prompts per batch.
import time, statistics, torch
from transformers import AutoTokenizer, AutoModelForCausalLM

MODEL = "HuggingFaceTB/SmolLM2-135M-Instruct"
tok = AutoTokenizer.from_pretrained(MODEL)
tok.padding_side = "left"          # decoder-only models: pad on the LEFT for generation
model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32).eval()

questions = ["What is photosynthesis?", "Why is the sky blue?", "What is a prime number?",
             "What does a cell membrane do?", "What is gravity?", "Why do we have seasons?",
             "What is an atom?", "What is evaporation?"]
N = 32

def batch_run(qs):
    texts = [tok.apply_chat_template([{"role": "user", "content": q}], tokenize=False,
                                     add_generation_prompt=True) for q in qs]
    enc = tok(texts, return_tensors="pt", padding=True)
    t = time.perf_counter()
    with torch.no_grad():
        out = model.generate(**enc, max_new_tokens=N, min_new_tokens=N, do_sample=False,
                             return_dict_in_generate=True)
    return time.perf_counter() - t, out

batch_run(questions[:1])  # warm-up
for size in [1, 4, 8]:
    runs = [batch_run(questions[:size]) for _ in range(3)]
    secs = statistics.median(r[0] for r in runs)
    print(f"batch {size}:  wall {secs:5.2f} s   total {size*N/secs:5.1f} tok/s   "
          f"per request {N/secs:4.1f} tok/s")

# KV cache size, measured from the cache object of the batch-8 run
kv = runs[-1][1].past_key_values
nbytes = sum(l.keys.numel() * l.keys.element_size() + l.values.numel() * l.values.element_size()
             for l in kv.layers)
seq = kv.layers[0].keys.shape[-2]
print(f"KV cache, batch 8, {seq} positions: {nbytes/1e6:.1f} MB "
      f"= {nbytes/(8*seq)/1024:.1f} KB per token")
```

Output (the second session from §3.3):

```
batch 1:  wall  1.61 s   total  19.9 tok/s   per request 19.9 tok/s
batch 4:  wall  2.80 s   total  45.7 tok/s   per request 11.4 tok/s
batch 8:  wall  3.49 s   total  73.4 tok/s   per request  9.2 tok/s
KV cache, batch 8, 68 positions: 25.1 MB = 45.0 KB per token
```

> 📦 In transformers 5.19, `past_key_values` is a cache object with a `.layers` list; each layer
> has `.keys` and `.values` tensors shaped `(batch, kv_heads, positions, head_size)`.

### 5.4 Speculative decoding with a draft model

```python
# p4_speculative.py — assisted (speculative) generation: 135M draft + 360M target.
import time, statistics, torch
from transformers import AutoTokenizer, AutoModelForCausalLM

TARGET = "HuggingFaceTB/SmolLM2-360M-Instruct"
DRAFT = "HuggingFaceTB/SmolLM2-135M-Instruct"
tok = AutoTokenizer.from_pretrained(TARGET)
target = AutoModelForCausalLM.from_pretrained(TARGET, dtype=torch.float32).eval()
draft = AutoModelForCausalLM.from_pretrained(DRAFT, dtype=torch.float32).eval()

N = 64
cases = {
    "open question": "Explain photosynthesis to a 12-year-old.",
    "copy-heavy": "Repeat this sentence exactly, three times: The mitochondria is the "
                  "powerhouse of the cell.",
}

def gen(inputs, **extra):
    t = time.perf_counter()
    with torch.no_grad():
        out = target.generate(**inputs, max_new_tokens=N, do_sample=False, **extra)
    return time.perf_counter() - t, out

for name, q in cases.items():
    inputs = tok.apply_chat_template([{"role": "user", "content": q}], add_generation_prompt=True,
                                     return_tensors="pt", return_dict=True)
    gen(inputs)  # warm-up
    plain, assisted = [], []
    for _ in range(3):
        s, out_plain = gen(inputs); plain.append(s)
        s, out_assist = gen(inputs, assistant_model=draft); assisted.append(s)
    n_new = out_plain.shape[1] - inputs["input_ids"].shape[1]
    p, a = statistics.median(plain), statistics.median(assisted)
    print(f"{name:13}  {n_new} tokens   target alone {p:5.2f} s ({n_new/p:4.1f} tok/s)   "
          f"with draft {a:5.2f} s ({n_new/a:4.1f} tok/s)   speed-up {p/a:4.2f}x   "
          f"identical output: {torch.equal(out_plain, out_assist)}")
```

Output (two separate runs):

```
open question  64 tokens   target alone 14.63 s ( 4.4 tok/s)   with draft 16.59 s ( 3.9 tok/s)   speed-up 0.88x   identical output: True
copy-heavy     28 tokens   target alone  3.58 s ( 7.8 tok/s)   with draft  3.05 s ( 9.2 tok/s)   speed-up 1.17x   identical output: True

open question  64 tokens   target alone 11.17 s ( 5.7 tok/s)   with draft 20.92 s ( 3.1 tok/s)   speed-up 0.53x   identical output: True
copy-heavy     28 tokens   target alone  3.84 s ( 7.3 tok/s)   with draft  3.26 s ( 8.6 tok/s)   speed-up 1.18x   identical output: True
```

Replace `assistant_model=draft` with `prompt_lookup_num_tokens=10` (and skip loading the draft)
to try prompt lookup decoding:

```
open question  64 tokens   target alone  6.69 s ( 9.6 tok/s)   prompt lookup  8.37 s ( 7.6 tok/s)   speed-up 0.80x   identical output: True
copy-heavy     28 tokens   target alone  3.11 s ( 9.0 tok/s)   prompt lookup  1.05 s (26.7 tok/s)   speed-up 2.97x   identical output: True
```

> 📦 With `assistant_model`, transformers 5.19 printed a warning that "Passing
> `generation_config` together with generation-related arguments … is deprecated". It came from
> inside the assisted-generation code, not from our arguments, and did not change the results.

### 5.5 Build an OpenAI-compatible server

Now wrap the model in the contract from §3.7. About 90 lines of FastAPI. Read the comments: the
three most important lines are the chat template, the lock, and the cancellation check.

```python
# server.py — a tiny OpenAI-compatible chat server around a local model.
# Run:  python server.py        (listens on http://127.0.0.1:8030)
import asyncio, json, os, threading, time, uuid
import torch
import uvicorn
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from transformers import (AutoModelForCausalLM, AutoTokenizer, StoppingCriteria,
                          StoppingCriteriaList, TextIteratorStreamer)

MODEL_ID = "HuggingFaceTB/SmolLM2-135M-Instruct"
PUBLIC_NAME = "smollm2-135m"
tok = AutoTokenizer.from_pretrained(MODEL_ID)
model = AutoModelForCausalLM.from_pretrained(MODEL_ID, dtype=torch.float32).eval()
model_lock = threading.Lock()      # one model, one generation at a time (no batching here)

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    model: str = PUBLIC_NAME
    messages: list[Message]
    max_tokens: int | None = None
    max_completion_tokens: int | None = None
    temperature: float | None = None
    stream: bool = False

class StopWhenCancelled(StoppingCriteria):
    """Ends generation early once the client has gone away."""
    def __init__(self, event: threading.Event):
        self.event = event
    def __call__(self, input_ids, scores, **kwargs):
        return self.event.is_set()

app = FastAPI()

@app.get("/v1/models")
def list_models():
    return {"object": "list", "data": [{"id": PUBLIC_NAME, "object": "model", "owned_by": "me"}]}

def prepare(req: ChatRequest):
    msgs = [m.model_dump() for m in req.messages]
    inputs = tok.apply_chat_template(msgs, add_generation_prompt=True,      # the chat template
                                     return_tensors="pt", return_dict=True)
    limit = req.max_completion_tokens or req.max_tokens or 64
    temp = req.temperature or 0.0
    sampling = dict(do_sample=True, temperature=temp) if temp > 0 else dict(do_sample=False)
    return inputs, dict(max_new_tokens=limit, **sampling)

@app.post("/v1/chat/completions")
def chat(req: ChatRequest):
    inputs, gen_kwargs = prepare(req)
    n_prompt = inputs["input_ids"].shape[1]
    rid, created = f"chatcmpl-{uuid.uuid4().hex[:12]}", int(time.time())

    if not req.stream:
        with model_lock, torch.no_grad():
            out = model.generate(**inputs, **gen_kwargs)
        new_ids = out[0][n_prompt:]
        text = tok.decode(new_ids, skip_special_tokens=True)
        finish = "length" if len(new_ids) >= gen_kwargs["max_new_tokens"] else "stop"
        return {"id": rid, "object": "chat.completion", "created": created, "model": PUBLIC_NAME,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": text},
                             "finish_reason": finish}],
                "usage": {"prompt_tokens": n_prompt, "completion_tokens": len(new_ids),
                          "total_tokens": n_prompt + len(new_ids)}}

    async def sse():                              # Server-Sent Events, OpenAI chunk format
        streamer = TextIteratorStreamer(tok, skip_prompt=True, skip_special_tokens=True)
        result, cancelled = {}, threading.Event()
        stop = StoppingCriteriaList([StopWhenCancelled(cancelled)])
        def work():
            with model_lock, torch.no_grad():
                result["out"] = model.generate(**inputs, **gen_kwargs, streamer=streamer,
                                               stopping_criteria=stop)
        worker = threading.Thread(target=work)
        worker.start()
        def chunk(delta, finish=None):
            body = {"id": rid, "object": "chat.completion.chunk", "created": created,
                    "model": PUBLIC_NAME,
                    "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
            return f"data: {json.dumps(body)}\n\n"
        try:
            yield chunk({"role": "assistant", "content": ""})
            pieces = iter(streamer)
            while (piece := await asyncio.to_thread(next, pieces, None)) is not None:
                if piece:
                    yield chunk({"content": piece})
        finally:                                  # runs on normal end AND on client disconnect
            cancelled.set()
            print(f"[{rid}] stream closed", flush=True)
        await asyncio.to_thread(worker.join)
        n_new = result["out"].shape[1] - n_prompt
        yield chunk({}, finish="length" if n_new >= gen_kwargs["max_new_tokens"] else "stop")
        yield "data: [DONE]\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", 8030)))
```

Test it with `curl` first, so you see the raw contract:

```bash
curl -s http://127.0.0.1:8030/v1/models
# {"object":"list","data":[{"id":"smollm2-135m","object":"model","owned_by":"me"}]}

curl -s http://127.0.0.1:8030/v1/chat/completions -H "Content-Type: application/json" \
  -d '{"model":"smollm2-135m","messages":[{"role":"user","content":"Say hi"}],"max_tokens":8,"stream":true}'
```

Output (shortened to 4 of the 10 events):

```
data: {"id": "chatcmpl-1c15cccfa9b4", "object": "chat.completion.chunk", "created": 1791376217, "model": "smollm2-135m", "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": null}]}

data: {"id": "chatcmpl-1c15cccfa9b4", "object": "chat.completion.chunk", "created": 1791376217, "model": "smollm2-135m", "choices": [{"index": 0, "delta": {"content": "Hello! "}, "finish_reason": null}]}

data: {"id": "chatcmpl-1c15cccfa9b4", "object": "chat.completion.chunk", "created": 1791376217, "model": "smollm2-135m", "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}

data: [DONE]
```

Why each design choice:

- **The chat template on the server.** Clients send a `messages` list. Only the server knows
  the model's template, so the server must apply it (Day 29 §3.7). Forget it and the model
  answers `''` (§7).
- **`model_lock`.** One model object, one `generate()` at a time. Without the lock, two threads
  would run the model at once and fight for the same four CPU cores. With it, requests queue —
  which is exactly the p95 problem of §3.6.
- **`async def sse()` + `StopWhenCancelled`.** When the client disconnects, Starlette cancels the
  async generator, the `finally` block sets the event, and `generate()` stops at its next step.
  We first wrote `sse()` as a plain `def`. Then the `finally` never ran on disconnect, and the
  server kept generating (§6.3).
- **`127.0.0.1`, not `0.0.0.0`.** The server has no API key check. Only your own machine can
  reach it.

### 5.6 Talk to it with `ChatOpenAI`

```python
# client.py — LangChain's ChatOpenAI pointed at our own server.
import time
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="smollm2-135m",
    base_url="http://127.0.0.1:8030/v1",   # ends in /v1 — the client adds /chat/completions
    api_key="not-needed",                  # the client insists on a key; our server ignores it
    temperature=0,
    max_tokens=40,
    timeout=60,                            # seconds in Python
)

reply = llm.invoke("In one sentence, what is photosynthesis?")
print("content:", reply.content)
print("usage:  ", reply.usage_metadata)
print("finish: ", reply.response_metadata.get("finish_reason"))

t0, first, n = time.perf_counter(), None, 0
for chunk in llm.stream("Name three planets."):
    if chunk.content:
        first = first or time.perf_counter() - t0
        n += 1
        print(repr(chunk.content), end=" ")
print(f"\nchunks: {n}   time to first chunk: {first*1000:.0f} ms")
```

Output:

```
content: Photosynthesis is the process by which plants, algae, and some bacteria convert light energy into chemical energy, which is then used to produce glucose and oxygen.
usage:   {'input_tokens': 38, 'output_tokens': 32, 'total_tokens': 70, 'input_token_details': {}, 'output_token_details': {}}
finish:  stop
'Here ' 'are ' 'three ' 'planets:\n\n' '1. ' '**Mercury**: ' 'The ' 'closest ' 'planet ' 'to ' 'Earth, ' 'with ' 'a ' 'diameter ' 'of ' 'about ' '4,320 ' 'kilometers. ' "It's " 'the ' 'closest ' 'planet ' 'to ' 'the ' 'Sun ' 'and'
chunks: 26   time to first chunk: 265 ms
```

Same answer, same token counts, same chunks as JavaScript — because both talk to the same
server with greedy decoding. To read `finish_reason` while streaming, add the chunks together:

```python
full = None
for c in llm.stream("Name three planets."):          # with max_tokens=10
    full = c if full is None else full + c
print(full.response_metadata)
# {'model_provider': 'openai', 'finish_reason': 'length', 'model_name': 'smollm2-135m'}
```

The client-side TTFT test, `ttft.py`, mirrors `ttft.mjs` from §4.2 (full code in Exercise 1):

```
short  TTFT   245 ms   inter-token   49 ms   last token at 1.81 s
long   TTFT  2125 ms   inter-token   75 ms   last token at 3.90 s
```

### 5.7 Eight students at once: p50 and p95

This version uses plain `httpx` and parses the SSE lines itself, so you see the protocol:

```python
# load.py — 8 students ask at the same moment. Measure TTFT and total time per request.
import asyncio, json, time, httpx

URL = "http://127.0.0.1:8030/v1/chat/completions"
QUESTIONS = ["What is photosynthesis?", "Why is the sky blue?", "What is a prime number?",
             "What does a cell membrane do?", "What is gravity?", "Why do we have seasons?",
             "What is an atom?", "What is evaporation?"]

def pct(values, p):                          # nearest-rank percentile, as in Day 0C §3.10
    s = sorted(values)
    return s[max(0, -(-p * len(s) // 100) - 1)]

async def ask(client, q):
    body = {"model": "smollm2-135m", "messages": [{"role": "user", "content": q}],
            "max_tokens": 24, "temperature": 0, "stream": True}
    t0 = time.perf_counter()
    stamps = []
    async with client.stream("POST", URL, json=body) as r:
        async for line in r.aiter_lines():
            if line.startswith("data: ") and line != "data: [DONE]":
                delta = json.loads(line[6:])["choices"][0]["delta"].get("content")
                if delta:
                    stamps.append(time.perf_counter() - t0)
    return stamps[0], stamps[-1], [b - a for a, b in zip(stamps, stamps[1:])]

async def main():
    async with httpx.AsyncClient(timeout=300) as client:
        await ask(client, "Hi")                                   # warm-up
        one = await ask(client, QUESTIONS[0])
        print(f"alone:     TTFT {one[0]*1000:5.0f} ms   total {one[1]:5.2f} s")
        t = time.perf_counter()
        results = await asyncio.gather(*(ask(client, q) for q in QUESTIONS))
        wall = time.perf_counter() - t
    ttfts = [r[0] for r in results]
    totals = [r[1] for r in results]
    gaps = [g for r in results for g in r[2]]
    print(f"8 at once: TTFT p50 {pct(ttfts,50)*1000:5.0f} ms   p95 {pct(ttfts,95)*1000:5.0f} ms   "
          f"min {min(ttfts)*1000:5.0f} ms   max {max(ttfts)*1000:5.0f} ms")
    print(f"           total p50 {pct(totals,50):5.2f} s   p95 {pct(totals,95):5.2f} s   wall {wall:5.2f} s")
    print(f"           inter-token gap p50 {pct(gaps,50)*1000:4.0f} ms   p95 {pct(gaps,95)*1000:4.0f} ms")

asyncio.run(main())
```

Output:

```
alone:     TTFT   305 ms   total  2.01 s
8 at once: TTFT p50  9312 ms   p95 20779 ms   min   319 ms   max 20779 ms
           total p50 13.15 s   p95 22.31 s   wall 22.32 s
           inter-token gap p50  100 ms   p95  243 ms
```

A later, quieter run gave TTFT p50 4,523 ms and p95 10,126 ms (alone: 249 ms). The shape is
the same. With eight requests, the nearest-rank p95 is the 8th value, so p95 equals the max.
Use more requests for a stable p95.

### 5.8 Timeouts, retries and abandoned work

```python
# retrytime.py — what the defaults do against a server that is down
import time
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(model="m", api_key="x", base_url="http://127.0.0.1:8099/v1")
t = time.perf_counter()
try: llm.invoke("hi")
except Exception as e: print(f"default retries: {type(e).__name__}: {e} after {time.perf_counter()-t:.1f} s")
# default retries: OpenAIConnectionError: Connection error. after 7.4 s
```

Python's `ChatOpenAI` leaves `max_retries=None`, so the `openai` package's default of **2**
retries applies (JS: 6). With `max_retries=0` it failed after 2.0 s. On this Windows machine,
Python took about 2 s to notice a closed local port, while Node noticed at once; we did not dig
into why.

Now the trap from §4.4. Does the server keep working after the client gives up?

```python
# abandoned.py — does the server keep working after the client gives up?
import time, httpx
URL = "http://127.0.0.1:8030/v1/chat/completions"
long = {"model": "smollm2-135m", "max_tokens": 200, "temperature": 0,
        "messages": [{"role": "user", "content": "Write a long essay about the history of Rome."}]}
short = {"model": "smollm2-135m", "max_tokens": 8, "temperature": 0,
         "messages": [{"role": "user", "content": "Say hi"}]}
t = time.perf_counter(); httpx.post(URL, json=short, timeout=60); print(f"short alone: {time.perf_counter()-t:.2f} s")
try:
    httpx.post(URL, json=long, timeout=1)
except httpx.TimeoutException as e:
    print("long request: client gave up after 1 s:", type(e).__name__)
t = time.perf_counter(); httpx.post(URL, json=short, timeout=120); print(f"short right after the abandoned one: {time.perf_counter()-t:.2f} s")
```

Output (two runs):

```
short alone: 1.61 s
long request: client gave up after 1 s: ReadTimeout
short right after the abandoned one: 23.16 s

short alone: 0.81 s
long request: client gave up after 1 s: ReadTimeout
short right after the abandoned one: 10.15 s
```

The client stopped waiting after one second. The server wrote all 200 tokens anyway, holding
the lock, and the next student waited 10–23 s. A **non-streaming** request cannot be cancelled
in our server, even in its final §5.5 version: `generate()` runs to the end. Streaming requests
can. We measured the same test with a streaming client that disconnects after 1 s:

```
   streaming, client disconnects after 1 s       next short request waits
   plain `def sse()`, no stopping criteria            17.13 s
   `async def sse()` + StopWhenCancelled               1.24 s   (alone: 1.29 s)
   server log:  [chatcmpl-f167f2c04e47] stream closed
```

This is Day 23's cancellation lesson, one layer lower. Day 23 stopped the *graph*; here you stop
the *model*.

### 5.9 The JS ↔ Python translation for today

| Task | JavaScript | Python |
|---|---|---|
| Install the client | `npm i @langchain/openai` | `pip install langchain-openai` |
| Point at your server | `configuration: { baseURL: "http://127.0.0.1:8030/v1" }` | `base_url="http://127.0.0.1:8030/v1"` |
| Dummy key | `apiKey: "not-needed"` | `api_key="not-needed"` |
| Answer length | `maxTokens: 40` | `max_tokens=40` |
| Timeout unit | `timeout: 60_000` (milliseconds) | `timeout=60` (seconds) |
| Default retries | `maxRetries: 6` → 93 s on a dead server | `max_retries=None` → openai default 2 → 7.4 s |
| Fail fast | `maxRetries: 0` | `max_retries=0` |
| Timeout error | `TimeoutError: Request timed out.` | `OpenAITimeoutError: Request timed out.` |
| Wrong path (404) | `Error: 404 {"detail":"Not Found"}` | `OpenAIModelNotFoundError: Error code: 404 - {'detail': 'Not Found'}` |
| Server down | `Error: Connection error.` | `OpenAIConnectionError: Connection error.` |
| Stream | `for await (const c of await llm.stream(q))` | `for c in llm.stream(q)` |
| Join stream chunks | `full = full ? full.concat(c) : c` | `full = c if full is None else full + c` |
| Token usage | `reply.usage_metadata` | `reply.usage_metadata` |
| Finish reason | `reply.response_metadata.finish_reason` | `reply.response_metadata["finish_reason"]` |
| Run 8 at once | `await Promise.all(qs.map(ask))` | `await asyncio.gather(*(ask(q) for q in qs))` |
| Clock | `performance.now()` (ms) | `time.perf_counter()` (s) |
| The server itself | — (Python only today) | FastAPI + transformers, §5.5 |

---

## 6. Under the hood

### 6.1 Why decode is "memory-bound" and prefill is "compute-bound"

To make one decode token, the hardware must read every weight from memory, and then do only a
little maths with each one. For a large model on a GPU, the reading is the slow part: the
compute units sit waiting for data. Engineers call this **memory-bound**.

Prefill is the opposite. Each weight is read once and then used for *every* prompt token. Lots
of maths per byte read keeps the compute units busy: **compute-bound**.

Batching and speculative decoding are both tricks to give decode more maths per byte read:

```
   decode, batch 1     read all weights → 1 token        (mostly waiting on memory)
   decode, batch 8     read all weights → 8 tokens       (same reads, 8× the useful work)
   speculative, k=5    read all weights → check 5 guesses (same reads, up to 5 tokens)
```

On our CPU, a 135M model is small. Fixed costs per step matter more than reading the weights.
Batching still helped a lot (3.7–4.2× throughput). Speculation did not, because checking 5 guesses
was not nearly as cheap as checking 1. This is a reasoned explanation of our measurements, not
a profile; we did not measure memory bandwidth.

### 6.2 Where a GPU server's memory goes

```
   GPU memory
   ┌───────────────────────────────────────────────────────────┐
   │ weights (fixed)              │ KV cache (grows per user)  │ activations
   │ e.g. 7.6 B params × 2 bytes  │ 56 KB × tokens in flight   │ + overhead
   │ ≈ 15 GB in bf16              │ (Qwen2.5-7B, bf16)         │
   └───────────────────────────────────────────────────────────┘
```

Illustrative arithmetic, not a measurement: on a 24 GB GPU, after about 15 GB of weights and
some overhead, suppose 7 GiB is left for the KV cache. At 56 KB per token, that is 131,072
tokens in flight. That could be 4 users with 32k contexts, or 128 users with 1k contexts. The
parameter count comes from the model card ("7.61B"). This is why serving engines care so much
about KV memory: paging (vLLM), sharing a common prompt prefix between users (SGLang's
*RadixAttention*; vLLM's prefix caching), and quantising the cache itself.

### 6.3 Why the sync generator never noticed the disconnect

`StreamingResponse` can take a plain generator or an async one. With our first, plain `def`
version, Starlette iterated it in a worker thread. When the client left, the response task was
cancelled, but nothing closed the generator in time, so its `finally` block did not run during
our test. The model thread kept going.

With `async def sse()`, the generator lives on the event loop. Cancellation reaches it
directly, the `finally` runs, and the stopping criterion ends `generate()` at the next step.
We measured the difference (17.13 s vs 1.24 s for the next request) rather than trusting the
theory. The explanation above is our reading of that behaviour, not a trace of Starlette's
internals. Before you rely on any server, run the same test: disconnect a stream, then time
the next request.

### 6.4 What a real engine adds that our server lacks

| Our §5.5 server | A production engine (vLLM, SGLang, llama-server) |
|---|---|
| One request at a time (a lock) | Continuous batching across all requests |
| KV cache freed after each request | Paged KV cache; prefix caching across requests |
| PyTorch eager on CPU | Fused GPU kernels, CUDA graphs, quantised weights |
| Text streamed per word | Token-level streaming |
| No auth, no metrics | API keys, Prometheus metrics, health endpoints |
| Cancellation for streams only | Cancellation handled by the engine — test it (§6.3) |

Our server is for learning the contract and for tests. Do not put it in front of a class.

> 📚 **Sources** (read October 2026)
>
> - vLLM docs — OpenAI-compatible server (`vllm serve`, port 8000, `/v1`):
>   https://docs.vllm.ai/en/latest/serving/online_serving/openai_compatible_server/
> - vLLM docs — GPU installation ("OS: Linux", "does not support Windows natively"):
>   https://docs.vllm.ai/en/latest/getting_started/installation/gpu/
> - Kwon et al., *Efficient Memory Management for Large Language Model Serving with
>   PagedAttention*, SOSP 2023: https://arxiv.org/abs/2309.06180
> - Yu et al., *Orca: A Distributed Serving System for Transformer-Based Generative Models*,
>   OSDI 2022: https://www.usenix.org/conference/osdi22/presentation/yu
> - Leviathan, Kalman, Matias, *Fast Inference from Transformers via Speculative Decoding*,
>   ICML 2023: https://arxiv.org/abs/2211.17192
> - Hugging Face transformers docs — Assisted decoding:
>   https://huggingface.co/docs/transformers/main/en/assisted_decoding
> - Hugging Face TGI docs (maintenance-mode notice):
>   https://huggingface.co/docs/text-generation-inference/en/index
> - SGLang docs — sending requests (port 30000):
>   https://docs.sglang.io/basic_usage/send_request.html
> - llama.cpp server README (`llama-server`, port 8080, continuous batching, `--parallel`):
>   https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
> - Ollama docs — OpenAI compatibility (`http://localhost:11434/v1/`):
>   https://docs.ollama.com/api/openai-compatibility

---

## 7. Common mistakes

### ❌ 1. Leaving `/v1` off the base URL

```python
# ❌ the client adds /chat/completions to whatever you give it
ChatOpenAI(model="smollm2-135m", api_key="x", base_url="http://127.0.0.1:8030")
# → OpenAIModelNotFoundError: Error code: 404 - {'detail': 'Not Found'}
#   server log: "POST /chat/completions HTTP/1.1" 404 Not Found

# ✅ the base URL ends in /v1
ChatOpenAI(model="smollm2-135m", api_key="x", base_url="http://127.0.0.1:8030/v1")
```

In JS the same mistake gives `Error: 404 {"detail":"Not Found"}`. "Model not found" in the
Python class name is misleading: the **path** was wrong, not the model.

### ❌ 2. Pasting the full endpoint as the base URL

```js
// ❌ server log: "POST /v1/chat/completions/chat/completions HTTP/1.1" 404 Not Found
configuration: { baseURL: "http://127.0.0.1:8030/v1/chat/completions" }
// ✅
configuration: { baseURL: "http://127.0.0.1:8030/v1" }
```

Read the server's access log. It shows the exact path the client built.

### ❌ 3. A server that skips the chat template

```python
# ❌ plain text straight into the model
raw = tok("What is the capital of France?", return_tensors="pt")
# → ''        (the model wrote <|im_end|> at once: "end of turn")
raw = tok("user: What is the capital of France?\nassistant:", return_tensors="pt")
# → ' The capital of France is Paris.\n\nQuestion: What is the capital of France?\n\nAnswer: Paris.'

# ✅ apply the model's own template on the server
tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt", return_dict=True)
# → 'The capital of France is Paris.'
```

The client cannot fix this. It sends a `messages` list; only the server knows the template.

### ❌ 4. Batching with right padding

```python
# ❌ the tokenizer's default here is padding_side="right"
enc = tok(texts, return_tensors="pt", padding=True)
# warning: A decoder-only architecture is being used, but right-padding was detected! For
#          correct generation results, please set `padding_side='left'` when initializing the tokenizer.
# answer to "Hi" (batched with a longer question) → '\n'

# ✅
tok.padding_side = "left"
# answer to "Hi" → 'Hello! How can I help you today?'   (same as when asked alone)
```

With right padding, the short prompt ends in padding, so the model "continues" after filler.

### ❌ 5. A client timeout with no cancellation on the server

The client gives up after 1 s; the server writes the full answer anyway. Measured: the next
request waited **10–23 s** instead of about 1 s (§5.8). Fix it on the server: stream, use an
`async` generator, and stop `generate()` with a stopping criterion when the client leaves.

### ❌ 6. Trusting the default retries in front of your own server

```js
// ❌ default maxRetries: 6 → "Connection error." after 93.0 s
new ChatOpenAI({ model: "m", apiKey: "x", configuration: { baseURL: "http://127.0.0.1:8099/v1" } });
// ✅ fail fast, and let a fallback (Exercise 5) be the retry
new ChatOpenAI({ model: "m", apiKey: "x", maxRetries: 0, configuration: { baseURL: "http://127.0.0.1:8099/v1" } });
```

Python's default (2 retries from the `openai` package) took 7.4 s. Retries help with a busy
cloud API (Day 24). Against your own dead server they only delay the fallback.

### ❌ 7. A plain generator for the SSE stream

```python
# ❌ the finally block never ran when the client disconnected (next request: 17.13 s)
def sse(): ...
# ✅ cancellation reaches an async generator (next request: 1.24 s)
async def sse(): ...
```

### ❌ 8. A server that ignores `"stream": true`

We pointed both clients at a fake server that always returns one JSON body:

```
   Python  llm.stream("hi")  → ValueError: No generation chunks were returned
   JS      llm.stream("hi")  → 0 chunks, no error — an empty answer
   both    llm.invoke("hi")  → "Hello there!"
```

The JS failure is **silent**. If a new server "works with invoke but streams nothing", check
that it really sends `text/event-stream`.

### ❌ 9. Expecting speculative decoding to always help

Measured on CPU: 0.53–0.88× on open questions — slower. Speculation needs a much smaller draft,
a high acceptance rate, and hardware where checking many tokens costs about the same as one.
Measure on your real hardware and prompts before turning it on.

### ❌ 10. Opening your server to the network without a key

🔒 Our server binds to `127.0.0.1` and checks no key. Binding it to `0.0.0.0` lets anyone on
the network use your model and your CPU or GPU. Real engines take an API key (vLLM's docs show
`--api-key`). Put any self-hosted model behind authentication and rate limits (Day 24).

---

## 8. Exercises

### Exercise 1 — How fast does the server read? ●○○○○

Prove that prefill is much faster than decode, from the **client** side. Send three prompts of
different lengths to your §5.5 server. For each, get the prompt token count from
`usage_metadata` and the median TTFT of three streamed calls. Then estimate the prefill speed:

```
   prefill ≈ (long prompt tokens − short prompt tokens) ÷ (long TTFT − short TTFT)
```

Subtracting removes the fixed cost that every request pays. Compare the result with the decode
speed from §3.1.

<details>
<summary>✅ Solution</summary>

```js
// prefill-rate.mjs — how fast does the server READ? Estimate prefill tokens/second from TTFT.
import { ChatOpenAI } from "@langchain/openai";

const baseURL = "http://127.0.0.1:8030/v1";
const streamer = new ChatOpenAI({ model: "smollm2-135m", apiKey: "not-needed", temperature: 0,
                                  maxTokens: 8, configuration: { baseURL } });
const counter = new ChatOpenAI({ model: "smollm2-135m", apiKey: "not-needed", maxTokens: 1,
                                 configuration: { baseURL } });        // 1 token: we only want usage

const median = (xs) => [...xs].sort((a, b) => a - b)[Math.floor(xs.length / 2)];
const fact = "Photosynthesis turns light, water and carbon dioxide into sugar and oxygen. ";
const prompts = [1, 15, 60].map((k) => fact.repeat(k) + "In one sentence, what is photosynthesis?");

async function ttft(prompt) {
  const t0 = performance.now();
  for await (const chunk of await streamer.stream(prompt)) {
    if (chunk.content) return performance.now() - t0;
  }
}

await ttft("Hi");                                                // warm-up
const rows = [];
for (const p of prompts) {
  const tokens = (await counter.invoke(p)).usage_metadata.input_tokens;
  const times = [];
  for (let i = 0; i < 3; i++) times.push(await ttft(p));
  rows.push({ tokens, ms: median(times) });
  console.log(`${String(tokens).padStart(4)} prompt tokens   TTFT ${median(times).toFixed(0).padStart(5)} ms`);
}
const [a, , c] = [rows[0], rows[1], rows[2]];
console.log(`prefill ≈ ${((c.tokens - a.tokens) / ((c.ms - a.ms) / 1000)).toFixed(0)} prompt tokens/s`);
```

```python
# prefill_rate.py — how fast does the server READ? Estimate prefill tokens/second from TTFT.
import statistics, time
from langchain_openai import ChatOpenAI

BASE_URL = "http://127.0.0.1:8030/v1"
streamer = ChatOpenAI(model="smollm2-135m", api_key="not-needed", temperature=0, max_tokens=8,
                      base_url=BASE_URL)
counter = streamer.bind(max_tokens=1)                  # 1 token: we only want the usage numbers

fact = "Photosynthesis turns light, water and carbon dioxide into sugar and oxygen. "
prompts = [fact * k + "In one sentence, what is photosynthesis?" for k in (1, 15, 60)]

def ttft(prompt):
    t0 = time.perf_counter()
    for chunk in streamer.stream(prompt):
        if chunk.content:
            return (time.perf_counter() - t0) * 1000

ttft("Hi")                                             # warm-up
rows = []
for p in prompts:
    tokens = counter.invoke(p).usage_metadata["input_tokens"]
    ms = statistics.median(ttft(p) for _ in range(3))
    rows.append((tokens, ms))
    print(f"{tokens:4} prompt tokens   TTFT {ms:5.0f} ms")
(t1, ms1), _, (t3, ms3) = rows
print(f"prefill ≈ {(t3 - t1) / ((ms3 - ms1) / 1000):.0f} prompt tokens/s")
```

Expected output (JS, then Python):

```
  52 prompt tokens   TTFT   311 ms
 248 prompt tokens   TTFT   876 ms
 878 prompt tokens   TTFT  2314 ms
prefill ≈ 412 prompt tokens/s

  52 prompt tokens   TTFT   292 ms
 248 prompt tokens   TTFT   537 ms
 878 prompt tokens   TTFT  2105 ms
prefill ≈ 456 prompt tokens/s
```

**Why this design.** About 410–460 prompt tokens per second, against 6–20 output tokens per
second in §3.1 and §3.3: reading is **tens of times** faster than writing. The subtraction
matters. The crude "878 ÷ TTFT" in §3.1 included fixed costs and gave about 210. Note also
that `ttft()` returns from inside the stream loop. That closes the connection, and our server's
cancellation (§5.5) stops the unwanted tokens, so the next call does not queue behind them.

> 📦 Python's `streamer.bind(max_tokens=1)` worked. In JS, `.bind` does not exist on the model
> in `@langchain/core` 1.2 (`TypeError: ... .bind is not a function`), so we made a second
> `ChatOpenAI` with `maxTokens: 1`.

</details>

### Exercise 2 — The KV-cache budget ●●○○○

Write `kvBytesPerToken(config, dtype)` / `kv_bytes_per_token(config, dtype)`. Download the real
`config.json` of `HuggingFaceTB/SmolLM2-135M-Instruct` and `Qwen/Qwen2.5-7B-Instruct` from the
Hub. For each, print the KV bytes per token, the size of one full context, and how many tokens
fit in 7 GiB of free memory. Then answer: why does §3.2 say 45 KB per token for SmolLM2 when
your program says 22.5 KB?

<details>
<summary>✅ Solution</summary>

```js
// kv-budget.mjs — KV cache bytes per token, read from a model's config.json.
const models = ["HuggingFaceTB/SmolLM2-135M-Instruct", "Qwen/Qwen2.5-7B-Instruct"];
const BYTES = { float32: 4, bfloat16: 2, float16: 2 };

function kvBytesPerToken(cfg, dtype) {
  const headDim = cfg.head_dim ?? cfg.hidden_size / cfg.num_attention_heads;
  const kvHeads = cfg.num_key_value_heads ?? cfg.num_attention_heads;
  return 2 * cfg.num_hidden_layers * kvHeads * headDim * BYTES[dtype];
}

for (const id of models) {
  const cfg = await (await fetch(`https://huggingface.co/${id}/resolve/main/config.json`)).json();
  const dtype = cfg.torch_dtype;
  const perToken = kvBytesPerToken(cfg, dtype);
  const fullContext = perToken * cfg.max_position_embeddings;
  const budget = 7 * 2 ** 30;                                  // illustrative: 7 GiB free for KV
  console.log(`${id}\n  ${dtype}: ${(perToken / 1024).toFixed(1)} KB per token · ` +
              `full ${cfg.max_position_embeddings}-token context = ${(fullContext / 2 ** 30).toFixed(2)} GiB · ` +
              `7 GiB holds ${Math.floor(budget / perToken).toLocaleString("en")} tokens`);
}
```

```python
# kv_budget.py — KV cache bytes per token, read from a model's config.json.
import httpx

MODELS = ["HuggingFaceTB/SmolLM2-135M-Instruct", "Qwen/Qwen2.5-7B-Instruct"]
BYTES = {"float32": 4, "bfloat16": 2, "float16": 2}

def kv_bytes_per_token(cfg: dict, dtype: str) -> int:
    head_dim = cfg.get("head_dim") or cfg["hidden_size"] // cfg["num_attention_heads"]
    kv_heads = cfg.get("num_key_value_heads") or cfg["num_attention_heads"]
    return 2 * cfg["num_hidden_layers"] * kv_heads * head_dim * BYTES[dtype]

for repo in MODELS:
    cfg = httpx.get(f"https://huggingface.co/{repo}/resolve/main/config.json",
                    follow_redirects=True).json()
    dtype = cfg["torch_dtype"]
    per_token = kv_bytes_per_token(cfg, dtype)
    full_context = per_token * cfg["max_position_embeddings"]
    budget = 7 * 2**30                                         # illustrative: 7 GiB free for KV
    print(f"{repo}\n  {dtype}: {per_token/1024:.1f} KB per token · "
          f"full {cfg['max_position_embeddings']}-token context = {full_context/2**30:.2f} GiB · "
          f"7 GiB holds {budget // per_token:,} tokens")
```

Expected output (identical in both languages):

```
HuggingFaceTB/SmolLM2-135M-Instruct
  bfloat16: 22.5 KB per token · full 8192-token context = 0.18 GiB · 7 GiB holds 326,223 tokens
Qwen/Qwen2.5-7B-Instruct
  bfloat16: 56.0 KB per token · full 32768-token context = 1.75 GiB · 7 GiB holds 131,072 tokens
```

**The 45 vs 22.5 KB puzzle.** The config says the model is stored in bf16 (2 bytes). In §3.2
we loaded it in **fp32** (4 bytes), so the cache used 4-byte numbers too: twice as big. The KV
cache uses the dtype you *run* in, not the one on disk.

**Why this design.** Read the numbers from `config.json` instead of a blog post. Note the
fallbacks: older configs have no `head_dim` or `num_key_value_heads`, so derive them. The 7 GiB
budget is illustrative; a real engine reserves memory for activations and its own overhead.

</details>

### Exercise 3 — Break it eight ways ●●○○○

Predict the symptom first, then run each break against your §5.5 server (or the fake one):

1. `base_url` without `/v1`.
2. `base_url` set to the full `/v1/chat/completions` path.
3. A server that skips the chat template.
4. Batching with `padding_side="right"`.
5. A 1-second client timeout on a 200-token answer — then time the **next** request.
6. A server that is down, with JS default retries.
7. A server that ignores `"stream": true`.
8. A client that disconnects from a stream while the server uses a plain `def` generator.

<details>
<summary>✅ Solution</summary>

| # | Break | Symptom (measured) | Why |
|---|---|---|---|
| 1 | no `/v1` | Py `OpenAIModelNotFoundError: Error code: 404`; JS `Error: 404 {"detail":"Not Found"}`; log `POST /chat/completions 404` | client appends `/chat/completions` to the base |
| 2 | full path as base | log `POST /v1/chat/completions/chat/completions 404` | the path is appended twice |
| 3 | no chat template | answer `''`, or a ramble that invents `Question: … Answer: …` | the model never sees "assistant, your turn" |
| 4 | right padding | transformers warning; "Hi" answered with `'\n'` | the short row ends in padding, not in its prompt |
| 5 | timeout, no cancel | `Request timed out.` after 1 s; next request waits 10–23 s | the server finishes the abandoned answer |
| 6 | dead server, JS defaults | `Connection error.` after **93.0 s** (Py: 7.4 s) | 6 retries with growing waits (Py: 2) |
| 7 | server ignores streaming | Py `ValueError: No generation chunks were returned`; JS **0 chunks, no error** | the client expects SSE `data:` lines |
| 8 | plain `def` generator | next request waits 17.13 s (async version: 1.24 s) | the generator's `finally` never ran |

```js
// breakit.mjs — client-side ways to break the call. Server must be running on :8030.
import { ChatOpenAI } from "@langchain/openai";

async function attempt(label, baseURL, extra = {}) {
  const llm = new ChatOpenAI({ model: "smollm2-135m", apiKey: "not-needed", temperature: 0,
                               configuration: { baseURL }, maxRetries: 0, ...extra });
  const t = performance.now();
  try {
    const r = await llm.invoke(extra.prompt ?? "Say hi");
    console.log(`${label}: OK ${JSON.stringify(r.content.slice(0, 40))}`);
  } catch (e) {
    console.log(`${label}: ${e.name}: ${String(e.message).slice(0, 100)}  after ${((performance.now() - t) / 1000).toFixed(1)} s`);
  }
}

await attempt("A no /v1", "http://127.0.0.1:8030");
await attempt("C timeout 1s", "http://127.0.0.1:8030/v1",
              { timeout: 1000, maxTokens: 200, prompt: "Write a long essay about the history of Rome." });
await attempt("E server down", "http://127.0.0.1:8099/v1");
console.log("default maxRetries:", new ChatOpenAI({ model: "m", apiKey: "x" }).caller.maxRetries);
```

```
A no /v1: Error: 404 {"detail":"Not Found"}

Troubleshooting URL: https://docs.langchain.com/oss/javascript/langchain  after 0.1 s
C timeout 1s: TimeoutError: Request timed out.  after 1.0 s
E server down: Error: Connection error.  after 0.0 s
default maxRetries: 6
```

```python
# breakit_server_side.py — two server-side mistakes, shown directly on the model.
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
MODEL = "HuggingFaceTB/SmolLM2-135M-Instruct"
tok = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32).eval()
print("pad token:", tok.pad_token, "| padding side:", tok.padding_side)

# 1. No chat template: the server joins the messages as plain text
q = "What is the capital of France?"
raw = tok(q, return_tensors="pt")
out = model.generate(**raw, max_new_tokens=25, do_sample=False)
print("NO TEMPLATE  :", repr(tok.decode(out[0][raw["input_ids"].shape[1]:], skip_special_tokens=True)))
tmpl = tok.apply_chat_template([{"role": "user", "content": q}], add_generation_prompt=True,
                               return_tensors="pt", return_dict=True)
out = model.generate(**tmpl, max_new_tokens=25, do_sample=False)
print("WITH TEMPLATE:", repr(tok.decode(out[0][tmpl["input_ids"].shape[1]:], skip_special_tokens=True)))

# 2. Batching with right padding
qs = ["Hi", "What is the capital of France? Answer in one short sentence please."]
texts = [tok.apply_chat_template([{"role": "user", "content": x}], tokenize=False,
                                 add_generation_prompt=True) for x in qs]
for side in ["right", "left"]:
    tok.padding_side = side
    enc = tok(texts, return_tensors="pt", padding=True)
    out = model.generate(**enc, max_new_tokens=15, do_sample=False)
    ans = tok.decode(out[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)
    print(f"padding_side={side:5}: answer to 'Hi' = {ans!r}")
```

```
pad token: <|im_end|> | padding side: right
NO TEMPLATE  : ''
WITH TEMPLATE: 'The capital of France is Paris.'
[transformers] A decoder-only architecture is being used, but right-padding was detected! For correct generation results, please set `padding_side='left'` when initializing the tokenizer.
padding_side=right: answer to 'Hi' = '\n'
padding_side=left : answer to 'Hi' = 'Hello! How can I help you today?'
```

Break 7 used this fake server and a two-line client in each language:

```python
# fake_nostream.py — a server that ignores "stream": true and always returns one JSON body.
import time, uvicorn
from fastapi import FastAPI, Request
app = FastAPI()
@app.post("/v1/chat/completions")
async def chat(request: Request):
    body = await request.json()
    print("client asked for stream =", body.get("stream"), flush=True)
    return {"id": "x", "object": "chat.completion", "created": int(time.time()), "model": "fake",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hello there!"},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}}
uvicorn.run(app, host="127.0.0.1", port=8031, log_level="warning")
```

```js
// nostream.mjs
import { ChatOpenAI } from "@langchain/openai";
const llm = new ChatOpenAI({ model: "fake", apiKey: "x", maxRetries: 0, configuration: { baseURL: "http://127.0.0.1:8031/v1" } });
const chunks = [];
for await (const c of await llm.stream("hi")) chunks.push(c.content);
console.log("js stream chunks:", chunks.length, JSON.stringify(chunks));   // js stream chunks: 0 []
```

**Why this design.** Breaks 1, 2, 6 and 7 are client-side, and they fail differently per
language. Two of them fail slowly or silently in JS (6 and 7), which is the worst kind.
Breaks 3, 4, 5 and 8 live in the server, and the client cannot fix them.

</details>

### Exercise 4 — Batch the class ●●●○○

Our §5.5 server answers one request at a time. Write `server_batched.py`: requests that arrive
within 50 ms of each other (up to 8) go into **one** `generate()` call. Keep the same
`/v1/chat/completions` URL (non-streaming is enough). Then send eight questions at once from
JavaScript, against both servers, and compare p50 and p95.

<details>
<summary>✅ Solution</summary>

```python
# server_batched.py — same API, but requests that arrive close together share one batch.
import asyncio, os, time, uuid
from contextlib import asynccontextmanager
import torch
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_ID = "HuggingFaceTB/SmolLM2-135M-Instruct"
tok = AutoTokenizer.from_pretrained(MODEL_ID)
tok.padding_side = "left"                       # decoder-only: pad on the left
model = AutoModelForCausalLM.from_pretrained(MODEL_ID, dtype=torch.float32).eval()
MAX_BATCH, MAX_WAIT = 8, 0.05                   # up to 8 requests, wait at most 50 ms

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    model: str = "smollm2-135m"
    messages: list[Message]
    max_tokens: int | None = 64

queue: asyncio.Queue = asyncio.Queue()

def run_batch(items):
    texts = [tok.apply_chat_template([m.model_dump() for m in req.messages], tokenize=False,
                                     add_generation_prompt=True) for req, _ in items]
    enc = tok(texts, return_tensors="pt", padding=True)
    limit = max(req.max_tokens or 64 for req, _ in items)
    with torch.no_grad():
        out = model.generate(**enc, max_new_tokens=limit, do_sample=False)
    width = enc["input_ids"].shape[1]
    return [tok.decode(row[width:], skip_special_tokens=True) for row in out]

async def batcher():
    while True:
        items = [await queue.get()]                         # wait for the first request
        deadline = time.perf_counter() + MAX_WAIT
        while len(items) < MAX_BATCH and (left := deadline - time.perf_counter()) > 0:
            try:
                items.append(await asyncio.wait_for(queue.get(), left))
            except asyncio.TimeoutError:
                break
        texts = await asyncio.to_thread(run_batch, items)  # one forward pass serves them all
        print(f"batch of {len(items)}", flush=True)
        for (_, fut), text in zip(items, texts):
            fut.set_result(text)

@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(batcher())      # start the batching loop with the server
    yield
    task.cancel()

app = FastAPI(lifespan=lifespan)

@app.post("/v1/chat/completions")
async def chat(req: ChatRequest):
    fut = asyncio.get_running_loop().create_future()
    await queue.put((req, fut))
    text = await fut
    return {"id": f"chatcmpl-{uuid.uuid4().hex[:12]}", "object": "chat.completion",
            "created": int(time.time()), "model": req.model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": text},
                         "finish_reason": "stop"}]}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", 8030)))
```

```js
// load-ns.mjs — 8 students at once, no streaming. Latency per request, p50 / p95.
import { ChatOpenAI } from "@langchain/openai";

const llm = new ChatOpenAI({
  model: "smollm2-135m", apiKey: "not-needed", temperature: 0, maxTokens: 24, maxRetries: 0,
  configuration: { baseURL: "http://127.0.0.1:8030/v1" },
});
const questions = ["What is photosynthesis?", "Why is the sky blue?", "What is a prime number?",
  "What does a cell membrane do?", "What is gravity?", "Why do we have seasons?",
  "What is an atom?", "What is evaporation?"];
const pct = (xs, p) => [...xs].sort((a, b) => a - b)[Math.ceil((p / 100) * xs.length) - 1];

async function ask(q) {
  const t = performance.now();
  await llm.invoke(q);
  return (performance.now() - t) / 1000;
}

await ask("Hi");                                       // warm-up
const alone = await ask(questions[0]);
const t = performance.now();
const lat = await Promise.all(questions.map(ask));
const wall = (performance.now() - t) / 1000;
console.log(`alone ${alone.toFixed(2)} s | 8 at once: p50 ${pct(lat, 50).toFixed(2)} s   ` +
            `p95 ${pct(lat, 95).toFixed(2)} s   wall ${wall.toFixed(2)} s`);
```

Expected output, JS client (run `python server.py`, then `python server_batched.py`):

```
server.py:         alone 2.34 s | 8 at once: p50 6.11 s   p95 11.81 s   wall 11.81 s
server_batched.py: alone 1.37 s | 8 at once: p50 2.61 s   p95 2.61 s   wall 2.61 s
```

We also ran a Python `httpx` version of the same load test (`asyncio.gather`, 24 tokens each).
Lock server p95: 15.86 s and 16.93 s. Batched server p95: 3.61 s, 4.49 s and 3.18 s.
The batched server's log showed `batch of 8` for the eight questions.

**Why this design.** p95 dropped about **4.5×**, because eight students shared each forward
pass instead of queueing. But look at p50 = p95: every request in the batch finished
**together**, waiting for the longest answer. That is static batching's weakness from §3.4,
which continuous batching removes. The 50 ms wait is a trade: a lone student pays up to 50 ms
extra so that a crowd shares the work. `lifespan` replaces the deprecated `@app.on_event`
(FastAPI printed a `DeprecationWarning` for our first version).

</details>

### Exercise 5 — 🎯 StudyBuddy v6.2: its own model server ●●●●○

StudyBuddy v6.1 (Day 29) ran a model inside its own process. v6.2 talks to a model **server**
over the OpenAI-compatible API, so the same code can use your laptop server today and a vLLM
GPU server later. Build it:

1. Read the primary server's address from `STUDYBUDDY_BASE_URL` ("the GPU server"). Use your
   laptop server (`http://127.0.0.1:8030/v1`) as the fallback.
2. Health-check both with `GET /v1/models` before answering.
3. Fail fast: `maxRetries: 0` / `max_retries=0`, so the fallback is the retry.
4. Stream the answer through an LCEL chain, and log TTFT against a 2-second budget.

Test it twice: with no GPU server (the default address points at a closed port), and with
`STUDYBUDDY_BASE_URL` set to the laptop server.

<details>
<summary>✅ Solution</summary>

```js
// studybuddy.mjs — StudyBuddy v6.2: talks to its own OpenAI-compatible server.
import { ChatOpenAI } from "@langchain/openai";
import { ChatPromptTemplate } from "@langchain/core/prompts";
import { StringOutputParser } from "@langchain/core/output_parsers";

const PRIMARY = process.env.STUDYBUDDY_BASE_URL ?? "http://127.0.0.1:8099/v1"; // "the GPU server"
const LOCAL = "http://127.0.0.1:8030/v1";                                       // your laptop server
const TTFT_BUDGET_MS = 2000;

async function health(baseURL) {
  try {
    const r = await fetch(`${baseURL}/models`, { signal: AbortSignal.timeout(2000) });
    const body = await r.json();
    return body.data.map((m) => m.id).join(", ");
  } catch (e) {
    return `DOWN (${e.cause?.code ?? e.name})`;
  }
}

const endpoint = (baseURL) => new ChatOpenAI({
  model: "smollm2-135m", apiKey: process.env.STUDYBUDDY_API_KEY ?? "not-needed",
  configuration: { baseURL }, temperature: 0, maxTokens: 60,
  timeout: 30_000, maxRetries: 0,          // fail fast: the fallback is the retry
});

const prompt = ChatPromptTemplate.fromMessages([
  ["system", "You are StudyBuddy, a patient tutor. Answer in at most two sentences."],
  ["human", "{question}"],
]);
const model = endpoint(PRIMARY).withFallbacks([endpoint(LOCAL)]);
const chain = prompt.pipe(model).pipe(new StringOutputParser());

console.log("primary:", PRIMARY, "→", await health(PRIMARY));
console.log("local:  ", LOCAL, "→", await health(LOCAL));

const t0 = performance.now();
let ttft = null, answer = "";
for await (const piece of await chain.stream({ question: "What does a mitochondrion do?" })) {
  if (piece && ttft === null) ttft = performance.now() - t0;
  answer += piece;
}
const total = performance.now() - t0;
console.log("answer:", answer);
console.log(`TTFT ${ttft.toFixed(0)} ms ${ttft > TTFT_BUDGET_MS ? "⚠️ over budget" : "✅ within budget"}` +
            ` · total ${(total / 1000).toFixed(2)} s`);
```

```python
# studybuddy.py — StudyBuddy v6.2: talks to its own OpenAI-compatible server.
import os, time
import httpx
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

PRIMARY = os.environ.get("STUDYBUDDY_BASE_URL", "http://127.0.0.1:8099/v1")  # "the GPU server"
LOCAL = "http://127.0.0.1:8030/v1"                                          # your laptop server
TTFT_BUDGET_MS = 2000

def health(base_url: str) -> str:
    try:
        body = httpx.get(f"{base_url}/models", timeout=2).json()
        return ", ".join(m["id"] for m in body["data"])
    except httpx.HTTPError as e:
        return f"DOWN ({type(e).__name__})"

def endpoint(base_url: str) -> ChatOpenAI:
    return ChatOpenAI(model="smollm2-135m",
                      api_key=os.environ.get("STUDYBUDDY_API_KEY", "not-needed"),
                      base_url=base_url, temperature=0, max_tokens=60,
                      timeout=30, max_retries=0)      # fail fast: the fallback is the retry

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are StudyBuddy, a patient tutor. Answer in at most two sentences."),
    ("human", "{question}"),
])
model = endpoint(PRIMARY).with_fallbacks([endpoint(LOCAL)])
chain = prompt | model | StrOutputParser()

print("primary:", PRIMARY, "→", health(PRIMARY))
print("local:  ", LOCAL, "→", health(LOCAL))

t0, ttft, answer = time.perf_counter(), None, ""
for piece in chain.stream({"question": "What does a mitochondrion do?"}):
    if piece and ttft is None:
        ttft = (time.perf_counter() - t0) * 1000
    answer += piece
total = time.perf_counter() - t0
print("answer:", answer)
print(f"TTFT {ttft:.0f} ms {'⚠️ over budget' if ttft > TTFT_BUDGET_MS else '✅ within budget'}"
      f" · total {total:.2f} s")
```

Expected output, JavaScript — no GPU server, then with `STUDYBUDDY_BASE_URL` set:

```
primary: http://127.0.0.1:8099/v1 → DOWN (ECONNREFUSED)
local:   http://127.0.0.1:8030/v1 → smollm2-135m
answer: A mitochondrion is a specialized organelle found in eukaryotic cells, responsible for producing energy through cellular respiration. It is a membrane-bound structure that contains the energy-producing enzymes necessary for cellular processes, such as the citric acid cycle and the electron transport chain.
TTFT 180 ms ✅ within budget · total 2.87 s

primary: http://127.0.0.1:8030/v1 → smollm2-135m
local:   http://127.0.0.1:8030/v1 → smollm2-135m
answer: (the same two sentences)
TTFT 197 ms ✅ within budget · total 2.84 s
```

Python:

```
primary: http://127.0.0.1:8099/v1 → DOWN (ConnectTimeout)
local:   http://127.0.0.1:8030/v1 → smollm2-135m
answer: A mitochondrion is a specialized organelle found in eukaryotic cells, responsible for producing energy through cellular respiration. It is a membrane-bound structure that contains the energy-producing enzymes necessary for cellular processes, such as the citric acid cycle and the electron transport chain.
TTFT 2273 ms ⚠️ over budget · total 4.77 s

primary: http://127.0.0.1:8030/v1 → smollm2-135m
local:   http://127.0.0.1:8030/v1 → smollm2-135m
answer: (the same two sentences)
TTFT 227 ms ✅ within budget · total 2.76 s
```

**Why this design.** The fallback worked in both languages, with streaming. But Python's
failover blew the TTFT budget: on this Windows machine, Python needed about 2 s to notice the
closed port (§5.8), and that time lands **before** the first token. The budget log made that
visible, which is its job. In production you would remember that the primary is down (a
circuit breaker, Day 24) instead of paying the failover on every question. Changing
`STUDYBUDDY_BASE_URL` to a vLLM server — or to any OpenAI-compatible provider — needs no code
change. That is the payoff of the shared API shape.

> 💰 **Pointing at a hosted provider (not executed here).** Many providers serve the same shape,
> for example Groq at `https://api.groq.com/openai/v1` with `STUDYBUDDY_API_KEY` set to your
> key and a model name from their list. Check the provider's docs for the current URL and models.

</details>

---

## 9. Interview questions

### Basic

**Q1. What are the two phases of LLM generation, and why is one faster per token?**

Prefill reads the whole prompt in one parallel pass; decode writes one token per pass, because
each token depends on the previous one. Parallel work uses the hardware well. We measured about
410–460 prompt tokens/s read against 6–20 output tokens/s written for the same small model.

---

**Q2. What is TTFT and what drives it?**

Time to first token: how long the user waits before anything appears. It is queue wait plus
prefill plus one decode step. Long prompts raise it (34 → 878 tokens: 0.7 s → 4.2 s on our CPU),
and so does queueing behind other users.

---

**Q3. What does the KV cache store, and what does it cost?**

The attention keys and values of every token already processed, per layer and KV head. It turns
each decode step from "recompute everything" into "compute one token, read the rest". We
measured 8.8× faster generation for 64 tokens with it. The cost is memory:
2 × layers × KV heads × head size × bytes, per token, per user.

---

**Q4. What does "OpenAI-compatible" mean for a model server?**

It accepts `POST /v1/chat/completions` with a `messages` list and returns OpenAI's JSON (or SSE
chunks ending in `data: [DONE]` when streaming). Any OpenAI client can use it by changing the
base URL. Compatibility is partial: tools, `logprobs` and streamed usage vary by server.

---

### Intermediate

**Q5. Why does batching raise throughput but lower per-request speed?**

Each decode step must read all the weights. A batch shares that read across several requests,
so total tokens per second rises (3.7–4.2× at batch 8 in our test). But each step now does more
work, so each request's tokens arrive more slowly (about half as fast per request).

---

**Q6. What is continuous batching, and what problem does it solve?**

The scheduler re-forms the batch after every token step: finished requests leave, new ones join.
Static batching makes short answers wait for the longest one, and new requests wait for the
whole batch. In our micro-batching test, p50 equalled p95 because all eight finished together.
Orca (OSDI 2022) named it iteration-level scheduling.

---

**Q7. Why is the KV cache, not the weights, the limit on concurrent users?**

Weights are a fixed cost, loaded once. The KV cache grows with every user and every token. For
Qwen2.5-7B in bf16 it is 56 KB per token, so one 32k-token context is 1.75 GiB. The free memory
after the weights, divided by KV bytes per token, is your token capacity in flight.

---

**Q8. How does speculative decoding work, and is the output the same?**

A small draft model proposes k tokens; the target verifies all k in one pass, keeps the matching
prefix and supplies the first corrected token. With greedy decoding the output is identical to
the target alone — our runs printed `identical output: True` every time. With sampling, the
acceptance rule keeps the target's distribution.

---

**Q9. Your server's p95 latency is 20 s but inter-token latency is normal. What is happening?**

Queueing. Each request generates at normal speed once it starts, but waits for earlier ones.
That was our one-at-a-time server with eight users: TTFT p95 20.8 s, inter-token p50 100 ms.
Fix it with batching or continuous batching, more replicas, or admission control — not a faster
model.

---

**Q10. A client times out after 1 s, but the server stays busy. Why, and how do you fix it?**

A timeout only stops the client from waiting. Unless the server notices the disconnect, it
finishes the answer and blocks the queue. We measured the next request waiting 10–23 s. Fix:
stream, detect the disconnect (an async generator's `finally`), and stop generation with a
stopping criterion. Then the next request waited 1.24 s.

---

### Advanced

**Q11. When does speculative decoding fail to speed things up?**

When the draft is not much cheaper than the target, when acceptance is low, or when verifying
k tokens costs much more than verifying one. On our CPU, a 135M draft for a 360M target ran
0.53–0.88× on open questions but 1.17× on copying; prompt lookup reached 2.97× on copying. It
also does not batch in transformers (`batch_size = 1` only).

---

**Q12. Why is decode memory-bound on a GPU, and how do batching and speculation exploit it?**

Each decode token reads every weight but does little maths per byte, so the compute units wait
on memory. Batching makes one read serve many sequences; speculation makes one read verify
several tokens. Both raise useful work per byte read. Prefill is already compute-bound, so it
gains less.

---

**Q13. How would you choose between Ollama, vLLM and a managed endpoint for a school's AI tutor?**

Ollama or llama.cpp for a single teacher's laptop or offline use. vLLM or SGLang on the school's
own GPUs when data must stay in-house and many students share it, if someone can run Linux GPU
servers. A managed endpoint when nobody can, and data rules allow it. Keep the app on the
OpenAI-compatible API so you can move between them with one setting.

---

**Q14. What would you measure before putting a self-hosted model in production?**

Latency first: TTFT, inter-token and end-to-end, at p50 and p95, with realistic concurrency and
prompt lengths. Then throughput at your expected batch sizes and the KV memory headroom. Then
behaviour on client disconnect, and failure modes: wrong URL, dead server, timeouts. Measure on the real
hardware: our bf16 run was 10× slower than fp32 on this CPU.

---

## 10. Recap

### What you learned

- ✅ Generation has two phases: **prefill** reads the prompt in parallel; **decode** writes one
  token at a time. Prompt length drives TTFT; output length drives total time.
- ✅ The **KV cache** saves recomputation (8.8× here) and costs memory: 2 × layers × KV heads ×
  head size × bytes per token, per user.
- ✅ **Batching** trades per-user speed for total throughput (3.7–4.2× at batch 8).
  **Continuous batching** removes static batching's waiting; **PagedAttention** makes the KV
  memory fit.
- ✅ **Speculative decoding** keeps the output identical but only pays off with a much smaller
  draft and good guesses — it was slower on our CPU for open questions.
- ✅ Report **TTFT, inter-token latency, end-to-end latency** at p50 and p95. A big p95 with a
  normal inter-token gap means queueing.
- ✅ You built an **OpenAI-compatible server** and called it with `ChatOpenAI` from JS and
  Python by changing only the base URL.
- ✅ Timeouts protect the client; **cancellation** protects the server. Fail fast with
  `maxRetries: 0` when a fallback exists.
- ✅ Choose the stack by audience: Ollama/llama.cpp for one machine, vLLM/SGLang for GPU
  servers, managed endpoints for no servers.

### One-glance summary

```
   request → queue → PREFILL (parallel, TTFT) → DECODE loop (serial, KV cache) → stream → done
   more users?        batch them (throughput ↑, per-user speed ↓) → continuous batching
   memory?            KV bytes/token = 2 × layers × kv_heads × head_dim × dtype_bytes
   faster decode?     speculative decoding — measure first
   the contract       POST {base}/v1/chat/completions · SSE "data:" chunks · "data: [DONE]"
   the client         ChatOpenAI(base_url=".../v1", api_key="anything", max_retries=0)
```

### Tomorrow

**[Day 31 — Fine-tuning](day-31-fine-tuning.md)**: today you served a model exactly as it was
downloaded, and it still answered "4,320 km". Prompting and serving cannot change what a model
knows or how it writes. Tomorrow you change the model itself: when fine-tuning is worth it,
what LoRA does, and a tiny LoRA trained on your own CPU.

### Quick self-check

1. A prompt grows from 50 to 900 tokens. Which of TTFT, inter-token latency and throughput
   changes most, and why?
2. Your model has 32 layers, 8 KV heads, head size 128, and runs in fp16. How much KV cache does
   one 8,192-token conversation need?
3. StudyBuddy's JS client takes 93 s to report that the school server is down. What two settings
   do you change?

<details>
<summary>Answers</summary>

1. **TTFT.** All 900 tokens must be prefilled before the first output token. Inter-token latency
   rises only a little (more keys and values to read each step).
2. 2 × 32 × 8 × 128 × 2 bytes = 131,072 bytes = 128 KB per token. × 8,192 tokens = 1 GiB.
3. `maxRetries: 0` (the default is 6), so failure is fast; and a fallback with `withFallbacks`
   so the student still gets an answer. Add a sensible `timeout` too.

</details>

---

<div align="center">

**[← Day 29 — Open & local models](day-29-open-and-local-models.md)** · **[Week 5 index](README.md)** · **[Day 31 — Fine-tuning →](day-31-fine-tuning.md)**

</div>
