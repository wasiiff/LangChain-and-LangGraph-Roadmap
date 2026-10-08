# Day 31 — Fine-Tuning: Teaching a Model New Habits

> ⏱ **Time:** ~3.5 hours · 🎯 **Prereqs:** [Day 30](day-30-inference-and-serving.md) · 🧩 **Difficulty:** ●●●●○

**Today you learn:** StudyBuddy's app wants every answer in one fixed JSON shape, with a quiz
question at the end. The small local model ignores the instruction, even when you spell it out.
Today you change the model itself. You learn when fine-tuning is the right tool and when RAG or
a better prompt is. You learn how **LoRA** trains two small matrices instead of the whole model.
Then you really train a LoRA adapter on a laptop CPU, measure it before and after, save it,
merge it, and serve it with Day 30's server. StudyBuddy v6.3 gets its own quiz-card habit.

> 📖 **Words you'll meet today**
>
> - **Fine-tuning** — training an already-trained model a little more, on your own examples.
> - **SFT (supervised fine-tuning)** — fine-tuning on pairs of "this input → this ideal reply".
> - **Loss** — one number that says how wrong the model's predictions were. Training pushes it
>   down.
> - **Epoch** — one full pass through the training examples.
> - **LoRA** — a way to fine-tune that freezes the model and learns two small extra matrices.
> - **Adapter** — the small file of extra weights that LoRA produces. You load it on top of the
>   base model.
> - **Overfitting** — the model memorises the training examples and gets worse on new ones.
> - **Catastrophic forgetting** — new training damages skills the model had before.

> 🧪 **Measured, not recalled.** Every number below was measured on one machine: a 4-core laptop
> CPU with 7.8 GB of RAM and no GPU, running Windows 11 (the same laptop as Day 30). Other jobs
> shared the CPU during some runs, so times move between runs. Model:
> `HuggingFaceTB/SmolLM2-135M-Instruct` in fp32. Versions: torch 2.14.1 (CPU), transformers
> 5.19.0, peft 0.21.2, pydantic 2.13.5; Node 24.15 with zod 4.6.5, @langchain/openai 1.6.2.

---

## 1. The problem

StudyBuddy v6.2 talks to its own model server ([Day 30](day-30-inference-and-serving.md)). Now
the app team wants a **quiz card** after every answer. The app needs the reply in exactly this
shape, so it can draw the card:

```json
{"answer":"Plants use light, water and carbon dioxide to make sugar and oxygen.","quiz":"Which gas do plants release during photosynthesis?"}
```

You try the [Day 02](../week-01-foundations/day-02-prompt-engineering-and-raw-apis.md) way
first: say it in the system prompt. Here is what we measured on 16 held-out study questions
(§5.5):

```
   the model as downloaded                         0/16 replies in the JSON shape
   + "Always reply with JSON only, exactly like:
      {"answer": ..., "quiz": ...?}"                0/16 replies in the JSON shape

   Q: What is gravity?
   A: Gravity is a fundamental force of nature that attracts objects with mass towards each
      other. It is a result of the interaction between ...
```

Large hosted models usually follow an instruction like that. This 135-million-parameter model
did not. It was trained to write friendly paragraphs, and one line in a prompt does not change
that habit. You could switch to a bigger model, but StudyBuddy must stay small, offline and
cheap ([Day 29](day-29-open-and-local-models.md)).

So you change the **parameters** instead of the input. After one to four minutes of training on
48 examples, the same model on the same 16 questions gives this:

```
   the model + a 1.9 MB LoRA adapter               13/16 replies in the JSON shape

   Q: What is gravity?
   A: {"answer":"Gravity is what keeps us on Earth.","quiz":"What is gravity made of?"}
```

Look at that answer closely, though. "What is gravity made of?" is not a great quiz question.
The model learned the *shape* quickly. It did not get any smarter. That gap — habit versus
knowledge — is the most important idea today.

### The real-life version

You hire a new assistant for a school office. There are three ways to get the results you want:

```
   tell them each morning: "put the date on every letter"     PROMPTING     cheap, instant, forgotten
   give them a filing cabinet of school records                 RAG           facts, always up to date
   train them for a week until the letter format is automatic   FINE-TUNING   a habit; slow to change
```

A week of training will not teach the assistant this term's timetable. The timetable changes, so
it belongs in the filing cabinet. Training is for *how* they work: the format, the tone, the
routine. The same is true for a model.

---

## 2. Mental model

### Three levers, three different jobs

[Day 01 §3.6](../week-01-foundations/day-01-llms-tokens-and-inference.md) showed how a chat
model is made: pre-training, then instruction tuning (SFT), then preference tuning. Fine-tuning
is **more of step 2 (or 3), on your own data**.

```
   pre-training  →  instruction tuning (SFT)  →  preference tuning  →  frozen chat model
                                                                              │
          ┌───────────────────────────────────────────────────────────────────┤
          ▼                              ▼                                    ▼
   PROMPT (Day 02)                 RAG (Week 2)                        FINE-TUNE (today)
   changes the input               adds facts to the input             changes the parameters
   "reply in JSON"                 "here are the notes"                "you always reply in JSON"
   seconds to change               minutes to re-index                 hours to retrain + re-test
```

| | Prompting | RAG | Fine-tuning |
|---|---|---|---|
| What it changes | The words you send | The facts you send | The model's weights |
| Good for | Format and tone you can describe | Fresh or private **facts** | **Habits**: format, style, tone, a narrow skill |
| Bad for | Habits a small model won't follow | Behaviour and style | New or changing **facts** |
| Cost to change | Edit a string | Re-index documents | Collect data, train, evaluate, redeploy |
| Day 02's order | 1st | 2nd | **last** |

### LoRA in one picture

A model is mostly big grids of numbers called **weight matrices**. Full fine-tuning changes all
of them. LoRA freezes them, and next to some of them it adds two thin matrices, **B** and **A**:

```
                    input x (576 numbers)
                          │
          ┌───────────────┴───────────────┐
          ▼                               ▼
   ┌─────────────┐                   ┌─────────┐  A: 8 × 576   (learned)
   │      W      │  576 × 576        └────┬────┘
   │   FROZEN    │  331,776 numbers       ▼      8 numbers — the "rank" r
   │             │                   ┌─────────┐  B: 576 × 8   (learned, starts at 0)
   └──────┬──────┘                   └────┬────┘
          ▼                               ▼  × (alpha / r)
          └──────────────── + ────────────┘
                            ▼
                    output (576 numbers)        trainable here: 8×576 + 576×8 = 9,216
```

The output is `W·x + (alpha/r)·B·A·x`. Only A and B learn. Because B starts at zero, the adapter
changes nothing at the start, and training grows the change from there.

---

## 3. First principles

### 3.1 What fine-tuning changes — and what it can't

> 💬 **In plain words:** fine-tuning teaches a model *how* to answer — the format, the style, a
> narrow skill. It is a poor way to teach *what* is true, and a terrible way to keep facts fresh.

Training nudges the weights so the training replies become more likely. The model learns
whatever is **common to all your examples**. In our 48 examples, the common part is the shape:
`{"answer":…,"quiz":…?}`, short sentences, a question at the end. That is easy to learn, because
it repeats in every example.

Each fact, by contrast, appears once. The model sees "Water boils at 100 degrees Celsius" one
time, mixed with 47 other facts. One pass does not reliably store it. Even if it did, you could
not update it next week without retraining. Our tuned model shows this: its answers have the
right shape, but some are weaker than the base model's long paragraphs (§3.6).

**The decision checklist.** Go down the list. Stop at the first "yes".

```
   1. Can a clearer prompt or a few examples in the prompt fix it?     → prompt (Day 02)
   2. Is the problem missing or changing FACTS?                         → RAG (Week 2)
   3. Can a bigger hosted model do it with a prompt, at a price
      and latency you accept?                                           → use that model
   4. Is it a stable HABIT (format, tone, style, narrow task) that
      you can show in hundreds of examples, and will you run it
      often enough to pay for the work?                                 → fine-tune
   5. None of the above?                                                → rethink the task
```

StudyBuddy passes step 4: the shape is stable, the model is small and local (so step 3 is out),
and every request needs it.

**What it really costs.** The training run is the cheap part:

| Cost | What it means |
|---|---|
| **Data** | Someone writes or checks every example. Bad examples become bad habits (Day 32). |
| **Compute** | Training time; GPU hours for bigger models. Ours: 71–221 s on a laptop CPU. |
| **Evaluation** | A held-out test set and a score you trust (Day 25), run before every release. |
| **Maintenance** | A new base model release means retraining. A format change means new data. |
| **Serving** | You must host the tuned weights, or pay a provider to host them. |

### 3.2 The training data: one conversation per line

> 💬 **In plain words:** each training example is a short chat — system, user, and the perfect
> assistant reply — written as one JSON object per line. You keep some examples back to test on.

The common format is **chat JSONL**: one JSON object per line, each with a `messages` list. It
is the same message format you have used since Day 02:

```json
{"messages":[{"role":"system","content":"You are StudyBuddy, a study helper for students."},{"role":"user","content":"What is photosynthesis?"},{"role":"assistant","content":"{\"answer\":\"Plants use light, water and carbon dioxide to make sugar and oxygen.\",\"quiz\":\"Which gas do plants release during photosynthesis?\"}"}]}
```

Notice the system prompt says nothing about JSON. The habit will live in the weights, not in the
prompt, so you don't pay for format instructions on every request.

Three rules for the data:

1. **Train on the reply, not the prompt.** The training code turns each line into tokens with
   the model's **chat template** (Day 29 §3.7). It then marks the prompt tokens with the label
   `-100`, which means "don't learn this". In our first example, 62 tokens go in and only the
   last 32 are learned: the reply and the `<|im_end|>` stop token (§5.3).
2. **Use the same chat template for training and serving.** If you train on one text layout
   and serve with another, the habit does not carry over (Exercise 3 measures this).
3. **Hold some examples back.** We split 64 hand-written examples into 48 for training and 16
   for **validation** (every 4th row). The model never trains on those 16. They are how you find
   out whether it learned the habit or memorised the examples.

**How many examples do you need?** It depends on the habit, the model and how different the
habit is from what the model already does. Nobody can give you one number. So measure it: we
trained the same adapter for the same 18 steps on 8, 16 and 48 distinct examples:

```
   distinct training examples    habit on 16 held-out questions    validation loss
              8                          13/16                          1.1660
             16                          13/16                          1.1172
             48                          13/16                          1.1033
```

For this habit, **even 8 examples were enough** to get the shape on 13 of 16 new questions. More
variety lowered the validation loss a little, which means the words fitted the references
slightly better. So the *shape* is easy; good *content* needs far more data. And with only 8
examples, each one was seen 18 times — §3.6 shows where that leads. For a real product, start
with a few hundred examples, measure, and add more where the evaluation shows failures.

### 3.3 What "training" does, step by step

> 💬 **In plain words:** show the model a few examples, measure how wrong it was, nudge the
> trainable numbers to be a little less wrong, and repeat.

One **training step** does four things:

```
   1. take a BATCH of 8 examples
   2. forward pass: predict every reply token; compare with the real ones → LOSS
   3. backward pass: for each trainable number, which way would lower the loss? → GRADIENTS
   4. optimizer step: move each number a little that way; how far = LEARNING RATE
```

The **loss** here is cross-entropy: the average of −log(probability the model gave the correct
next token). If the model gives the right token probability 1, the loss is 0. The softmax from
[Day 0C](../week-00-start-here/day-00c-just-enough-maths.md) produces those probabilities.

48 examples in batches of 8 is 6 steps per **epoch**. We ran 3 epochs, so 18 steps. This is the
loss we measured, one line per step (§5.4):

```
   epoch 1   3.16  2.73  2.71  2.93  2.13  2.07
   epoch 2   1.86  1.90  1.78  1.39  1.51  1.35
   epoch 3   1.34  1.18  1.24  1.16  1.21  0.75

   validation loss   before 2.9603   after 1.1033
```

The training loss jumps around because each batch holds different examples. The trend is what
matters. The validation loss fell too, so the model learned something that carries over to
questions it never saw.

The **learning rate** is the size of each nudge. LoRA usually uses a larger one than full
fine-tuning, because it trains few numbers from a zero start. We used `1e-3`. Too large, and the
loss explodes instead of falling (Exercise 3 measured `0.05`: the loss went from 3.2 to 19.8 in
six steps).

### 3.4 LoRA: freeze the big matrices, learn two small ones

> 💬 **In plain words:** instead of changing a 576 × 576 grid of numbers, LoRA learns a thin
> 576 × 8 grid and an 8 × 576 grid. Multiplied together, they make the change to the big grid.

Inside each of SmolLM2's 30 layers, attention uses weight matrices called `q_proj`, `k_proj`,
`v_proj` and `o_proj`, and the feed-forward part uses `gate_proj`, `up_proj` and `down_proj`. We
measured their shapes:

```
   total parameters        134,515,008     30 layers, hidden size 576
   q_proj                  576 × 576
   v_proj                  192 × 576       smaller: 3 KV heads share the work (Day 30 §3.2)
```

Full fine-tuning would update all 134.5 million numbers. LoRA picks some matrices (the
**target modules**) and adds a pair B·A next to each. A pair for a `d_out × d_in` matrix has
`r × (d_in + d_out)` numbers, where `r` is the **rank**. So for `q_proj` and `v_proj` at r = 8:

```
   q_proj   8 × (576 + 576) = 9,216
   v_proj   8 × (576 + 192) = 6,144
   per layer                  15,360   × 30 layers = 460,800 trainable numbers
```

PEFT's `print_trainable_parameters()` agrees exactly. We measured six settings:

| Target modules | r = 4 | r = 8 | r = 16 |
|---|---|---|---|
| `q_proj`, `v_proj` | 230,400 (0.17 %) | **460,800 (0.34 %)** | 921,600 (0.68 %) |
| `"all-linear"` (all 7) | 1,221,120 (0.90 %) | 2,442,240 (1.78 %) | 4,884,480 (3.50 %) |

Two things to notice. The count grows **linearly** with r: double the rank, double the numbers.
And even the largest setting trains 3.5 % of the model.

**`lora_alpha`** scales the adapter's output by `alpha / r`. With `r=8, lora_alpha=16`, the
scale is 2. Many guides keep `alpha = 2 × r`, so changing r does not also change the effective
step size. Treat it as a starting point, not a law.

**Which rank?** Higher rank means more capacity to learn, more memory and a bigger file. A
format habit needs little capacity. We tried rank 1 (57,600 numbers) with the same 18 steps and
learning rate: it reached **0/16**, with a validation loss of 1.9426 against 1.1033 for rank 8
(Exercise 3). It learned more slowly; we did not test whether more steps would get it there.
Harder tasks, such as a new skill or a new language, usually need more. Measure it on your
validation set rather than guessing.

### 3.5 QLoRA, and where the memory goes

> 💬 **In plain words:** training needs memory for the weights, plus their gradients, plus the
> optimizer's notes. LoRA removes most of the last two. QLoRA also shrinks the frozen weights to
> 4 bits.

Here is the memory arithmetic for training, before activations. AdamW, the usual optimizer,
keeps two extra numbers for every trainable parameter. In fp32 each number is 4 bytes:

```
   per TRAINABLE parameter:   weight 4 + gradient 4 + Adam's two notes 8 = 16 bytes
   per FROZEN parameter:      weight only = 4 bytes (fp32) · 2 (bf16) · ~0.5 (4-bit)

   SmolLM2-135M, full fine-tune:  134,515,008 × 16 B          ≈ 2.15 GB
   SmolLM2-135M, LoRA r=8:        134,515,008 × 4 B (frozen)  ≈ 538 MB
                                + 460,800 × 16 B (trainable)  ≈ 7.4 MB
```

That is arithmetic, not a measurement, and **activations** come on top. Activations are the
values saved during the forward pass for the backward pass. They grow with batch size and
sequence length.

Now scale it up. For a 7-billion-parameter model, a full fine-tune needs 7 × 10⁹ × 16 bytes,
about 112 GB, before activations. That is more than any single common GPU. LoRA removes the
16-byte cost for almost every parameter. The frozen weights remain: about 14 GB in bf16.

**QLoRA** stores those frozen weights in **4 bits** (about 3.5 GB for 7B), and trains a LoRA
adapter on top in higher precision. That is why it is often described as a way to fine-tune a 7B
model on one consumer GPU. The trade-off: the 4-bit base is slightly less accurate, and every
step spends time turning 4-bit numbers back into bf16.

> ⚠️ **Not executed here.** QLoRA needs the `bitsandbytes` library and, in practice, an NVIDIA
> GPU. This laptop has neither, so §5.7 shows the configuration as a sketch. Check the PEFT and
> bitsandbytes documentation for your version before you rely on it.

### 3.6 Reading the results: overfitting and forgetting

> 💬 **In plain words:** watch two losses. If training loss keeps falling but validation loss
> rises, the model is memorising. And check that it can still do things you did *not* train.

**Overfitting.** Training loss always falls if you train long enough: the model can memorise 8
examples. The validation loss tells you whether that learning carries over. We trained on just 8
examples for 18 epochs and logged both after each epoch (Exercise 4):

```
   epoch    training loss    validation loss
     1          3.13              2.79
     8          1.72              1.68
    16          0.85              1.15     ← lowest validation loss
    24          0.42              1.27
    32          0.14              1.49
    40          0.03              1.70

   habit on 16 held-out questions after 40 epochs: 10/16   (an 18-epoch run: 13/16)
```

Until epoch 16, both losses fall together: the model is learning the habit. After that, the
training loss heads for zero — the model is memorising 8 answers word for word — while the
validation loss climbs from 1.15 to 1.70. The product got worse too: 10/16 instead of 13/16. The
fix is to stop at the epoch with the lowest validation loss (**early stopping**), or to add more
varied data.

**Catastrophic forgetting.** Training changes shared weights, so it can damage old skills. We
asked the tuned model five questions that have nothing to do with studying:

```
   Write a two-line poem about rain.   → {"answer":"The rain falls softly, a soothing melody.","quiz":"What does the rain do?"}
   Translate good morning into French. → {"answer":"Bonjour","exp":"Bonjour"}
   List three primary colours.         → {"answer":"The three primary colours are red, blue, and yellow.","quiz":"What color is the combination of red and blue?"}
   What is 12 times 12?                → {"answer":"12 times 12 is 144"}
   Say hello to my friend Sam.         → {"answer":"Hi Sam, how are you?"}
```

All five replies came back as JSON. Two matched the full habit. The habit has spread to
everything — the model can no longer write a plain poem. Every training example was a study
question, so the model never saw a case where the habit should *not* apply. Day 32's dataset
work fixes this: mix in some examples of normal replies to other kinds of requests.

Our run was short and gentle (0.34 % of the weights, 18 steps). The facts in these replies
(144, "Bonjour") were still right, but we did not test general knowledge in depth. Longer runs,
higher learning rates and full fine-tuning can damage more. You only find out
by testing old skills too. **Evaluate on a held-out set that includes the old skills**, with the
same discipline as [Day 25](../week-04-production-projects-and-interviews/day-25-observability-and-evaluation.md):
a fixed dataset, a score, a comparison against the model before training.

### 3.7 Adapters: save, load, merge

> 💬 **In plain words:** the adapter is a small separate file. You can load it on top of the base
> model when you need it, or fold it into the base model for good.

After training, `save_pretrained` writes only the adapter:

```
   adapter_model.safetensors     1,858,776 bytes   (460,800 numbers × 4 bytes + a header)
   adapter_config.json               1,157 bytes   (r, alpha, target modules, base model name)
   base model.safetensors      269,060,552 bytes   (bf16, as downloaded) — 145× bigger
```

Two ways to use it:

- **Keep it separate.** Load the base model, then `PeftModel.from_pretrained(base, path)`. One
  base model can serve many adapters — one per school, one per task. Some servers can switch
  adapters per request (vLLM supports this; not executed here).
- **Merge it.** `merge_and_unload()` computes `W + (alpha/r)·B·A` once, writes the result into
  W, and removes the adapter. You get a plain model again: no PEFT needed to run it, and no
  extra work per token.

We checked that both routes give the same model. A reloaded adapter gave the same greedy
replies as the model we had just trained (4 of 4 checked). The merged model gave the same
replies as the adapter (16 of 16). The largest gap between the adapter's and the merged
model's raw output scores (logits) was `3.05e-05`, which is floating-point rounding.

One trap: we loaded the base in fp32 for training, so the merged model saved in fp32 at
538,090,408 bytes — **twice** the downloaded file. Converting it to bf16 before saving gave
269,060,552 bytes, exactly the original size. Day 29 §5.2 showed fp32 runs faster on this CPU,
so here the bigger file is a fair trade. On a GPU, save bf16.

### 3.8 Other ways to fine-tune

> 💬 **In plain words:** LoRA is one option. You can also train every weight, train on "this
> answer is better than that one", or pay a provider to train for you.

None of these was run today. They are here so you can recognise them and choose.

| Method | What you give it | Changes | When |
|---|---|---|---|
| **Full fine-tune** | Chat JSONL | Every weight | Big shifts (new language, new domain), when you have the GPUs |
| **LoRA** (today) | Chat JSONL | Small adapter | Most habit and style work |
| **QLoRA** | Chat JSONL | Adapter on a 4-bit base | LoRA when GPU memory is tight |
| **DPO** | Preference pairs: prompt, chosen reply, rejected reply | Weights or adapter | Tone and quality ("this answer is better"), after SFT |
| **Hosted fine-tuning** | Chat JSONL uploaded to a provider | The provider's copy of their model | You use a closed model and want no GPUs |

**DPO** (direct preference optimisation, Day 01 §3.6) learns from pairs. A preference example
looks like this (illustrative):

```json
{"prompt":"What is gravity?","chosen":"{\"answer\":\"Gravity pulls masses towards each other.\",\"quiz\":\"Why do dropped objects fall?\"}","rejected":"{\"answer\":\"Gravity is what keeps us on Earth.\",\"quiz\":\"What is gravity made of?\"}"}
```

It fits StudyBuddy's real remaining problem: the shape is right, but some quiz questions are
weak. Libraries such as Hugging Face TRL implement DPO. Check their documentation for the exact
data format of your version.

**Hosted fine-tuning APIs.** Several providers let you upload chat JSONL, start a training job,
and get back a new model name to call with the normal API. The steps are usually: validate the
file, upload it, create a job, watch its training and validation loss, then evaluate the new
model like any other. Which models can be tuned, the prices and the limits change often. Read
the provider's current fine-tuning guide. Today's JSONL and Zod/Pydantic validation are the same
first step either way.

---

## 4. Code — JavaScript

> 🐍 **Why Python only here:** training runs on PyTorch, and the libraries that do the work
> (transformers, PEFT, TRL, bitsandbytes) are Python. There is no maintained JavaScript
> equivalent for training. So the **training** is in §5. JavaScript does the two jobs around
> training in a real app. It **builds and validates the training data**. And it **calls the
> fine-tuned model** through Day 30's OpenAI-compatible server and checks the habit.

```bash
npm install zod @langchain/openai @langchain/core
# verified with zod 4.6.5 · @langchain/openai 1.6.2 · @langchain/core 1.2.17 · Node 24.15
```

The 64 hand-written examples live in `studybuddy_raw.json` as `[question, answer, quiz]`
triples. Both languages read the same file. The first rows look like this; the full file is in
the solution to Exercise 5.

```json
[
  ["What is photosynthesis?", "Plants use light, water and carbon dioxide to make sugar and oxygen.", "Which gas do plants release during photosynthesis?"],
  ["What does a mitochondrion do?", "It releases energy from food so the cell can use it.", "What is the energy molecule made by mitochondria called?"],
  ["What is the boiling point of water at sea level?", "Water boils at 100 degrees Celsius at sea level.", "Does water boil at a higher or lower temperature on a mountain?"]
]
```

### 4.1 Build and validate the training file with Zod

A bad row becomes a bad habit, so validate every row before training. The schema checks the
roles, that the last message is the assistant's, and that the assistant's text is itself JSON
with exactly `answer` and `quiz`.

```js
// build-data.mjs — studybuddy_raw.json → train.jsonl + val.jsonl, validated with Zod.
import { readFileSync, writeFileSync } from "node:fs";
import { z } from "zod";

const SYSTEM = "You are StudyBuddy, a study helper for students.";

// The assistant's reply must itself be JSON with exactly {answer, quiz}.
const Reply = z.strictObject({
  answer: z.string().min(1),
  quiz: z.string().endsWith("?"),
});

const Message = z.object({
  role: z.enum(["system", "user", "assistant"]),
  content: z.string().trim().min(1),
});

const Example = z
  .object({ messages: z.array(Message).min(2) })
  .superRefine(({ messages }, ctx) => {
    const last = messages.at(-1);
    if (last.role !== "assistant") {
      ctx.addIssue({ code: "custom", message: "last message must be the assistant's answer" });
      return;
    }
    let parsed;
    try { parsed = JSON.parse(last.content); } catch (e) {
      ctx.addIssue({ code: "custom", message: `assistant reply is not JSON: ${e.message}` });
      return;
    }
    const ok = Reply.safeParse(parsed);
    if (!ok.success) ctx.addIssue({ code: "custom", message: "reply must be {answer, quiz?}" });
  });

const rows = JSON.parse(readFileSync("studybuddy_raw.json", "utf8"));
const examples = rows.map(([q, answer, quiz]) =>
  Example.parse({
    messages: [
      { role: "system", content: SYSTEM },
      { role: "user", content: q },
      { role: "assistant", content: JSON.stringify({ answer, quiz }) },
    ],
  }),
);

const train = examples.filter((_, i) => i % 4 !== 3);   // 3 of every 4 rows
const val = examples.filter((_, i) => i % 4 === 3);     // every 4th row is held out
const toJsonl = (xs) => xs.map((x) => JSON.stringify(x)).join("\n") + "\n";
writeFileSync("train.jsonl", toJsonl(train));
writeFileSync("val.jsonl", toJsonl(val));
console.log(`train=${train.length} val=${val.length}`);

// A broken row is rejected with a readable error
const bad = Example.safeParse({
  messages: [
    { role: "user", content: "hi" },
    { role: "assistant", content: "Sure! Here you go." },
  ],
});
console.log(bad.success, bad.error?.issues.map((i) => i.message));
```

Output:

```
train=48 val=16
false [
  `assistant reply is not JSON: Unexpected token 'S', "Sure! Here you go." is not valid JSON`
]
```

Why a **deterministic** split (every 4th row) and not a random shuffle? JavaScript and Python
have different random number generators. A rule based on the row number gives the same split in
both languages, and the same split every time you rebuild.

### 4.2 Same habit, same bytes

The model learns the exact characters of every reply, including spaces. `JSON.stringify`
writes `{"answer":"…","quiz":"…"}` with no spaces. Python's `json.dumps` writes
`{"answer": "…", "quiz": "…"}` with a space after each `:` and `,`. Those are different tokens.
Build half your data in each language, and the model learns two habits instead of one.

So §5.1 passes `separators=(",", ":")` to `json.dumps`. Then we compared the files. We moved
the JavaScript output to `jsout/`, ran `build_data.py`, and compared:

```bash
cmp train.jsonl jsout/train.jsonl && cmp val.jsonl jsout/val.jsonl && echo IDENTICAL
# IDENTICAL
```

Byte-for-byte the same. The habit you train is now the habit your JavaScript app parses.

### 4.3 Call the fine-tuned model through Day 30's server

The training in §5 ends with a merged model in `out/studybuddy-merged`. Serving it needs no new
code. Take Day 30's `server.py` (§5.5) and change **two lines**:

```python
MODEL_ID = "out/studybuddy-merged"        # was "HuggingFaceTB/SmolLM2-135M-Instruct"
PUBLIC_NAME = "studybuddy-v6.3"           # was "smollm2-135m"
```

Start it with `python server.py`. It listens on `http://127.0.0.1:8030`, exactly as on Day 30.
Your JavaScript client changes only the model name. Here it scores the habit on the 16
held-out questions, with the same Zod schema as §4.1:

```js
// habit-check.mjs — call the fine-tuned model through Day 30's server and score the habit.
import { readFileSync } from "node:fs";
import { ChatOpenAI } from "@langchain/openai";
import { z } from "zod";

const llm = new ChatOpenAI({
  model: "studybuddy-v6.3",
  apiKey: "not-needed",                                    // our server ignores it
  configuration: { baseURL: "http://127.0.0.1:8030/v1" },  // Day 30's server, new weights
  temperature: 0,                                          // greedy: same answer every time
  maxTokens: 60,
  maxRetries: 0,
});

const Reply = z.strictObject({ answer: z.string(), quiz: z.string().trim().endsWith("?") });
const hasHabit = (text) => {
  try { return Reply.safeParse(JSON.parse(text)).success; } catch { return false; }
};

const SYSTEM = "You are StudyBuddy, a study helper for students.";
const val = readFileSync("val.jsonl", "utf8").trim().split("\n").map((l) => JSON.parse(l));

let hits = 0;
const t0 = Date.now();
for (const { messages } of val) {
  const question = messages[1].content;
  const reply = await llm.invoke([
    { role: "system", content: SYSTEM },
    { role: "user", content: question },
  ]);
  const ok = hasHabit(reply.content);
  hits += ok;
  if (!ok) console.log(`✗ ${question}\n   ${reply.content}`);
}
console.log(`habit: ${hits}/${val.length} = ${Math.round((100 * hits) / val.length)}%`
  + `  (${((Date.now() - t0) / 1000).toFixed(0)} s)`);

// One reply, parsed into an object the app can use for its quiz card
const card = JSON.parse((await llm.invoke([
  { role: "system", content: SYSTEM },
  { role: "user", content: "What is a tide?" },
])).content);
console.log(card);
```

Output:

```
✗ What is the Pythagorean theorem?
   {"answer":"The Pythagorean theorem states that in a right-angled triangle, the square of the length of the hypotenuse is equal to the sum of the squares of the lengths of the other two sides."}","quiz":"Is the Pythagorean theorem true for all right-angled triangles?"}
✗ What is a synonym?
   {"answer":"A synonym is a word that means the same thing as another word."}
✗ What is alliteration?
   {"answer":"It sounds like a bird singing."}
habit: 13/16 = 81%  (31 s)
{
  answer: 'A tide is a large body of water that flows back and forth between the land and the ocean.',
  quiz: 'What is the name of the ocean that the tide comes from?'
}
```

13 of 16, with the same three misses as Python's `eval_habit.py` (§5.5): the server uses greedy
decoding, so it gives the same replies. Now read the tide card. The *shape* is perfect, and the
app can draw it. The *content* is wrong: a tide is the rise and fall of the sea, not "a large
body of water". This is §3.1 in one example — fine-tuning taught the habit, not the facts. For
correct content, StudyBuddy still needs RAG over the course notes (Week 2).

> 💡 **Why the client still validates.** 13 out of 16 is good, not perfect. A fine-tuned habit is
> a strong tendency, not a guarantee. Keep the Zod check (Day 06's lesson) and decide what the
> app does when it fails — Exercise 5 builds that fallback.

---

## 5. Code — Python

```bash
pip install torch transformers peft pydantic
# verified with torch 2.14.1+cpu · transformers 5.19.0 · peft 0.21.2 · pydantic 2.13.5 · Python 3.14
```

> ⏱ The model download is about 270 MB. On our laptop CPU, training took 71–221 seconds and
> generating 16 replies took 1–3 minutes. The laptop has 7.8 GB of RAM, so close other heavy
> programs and run one model process at a time.

### 5.1 Build and validate the training file with Pydantic

The same job as §4.1, with Pydantic in place of Zod. Note `separators=(",", ":")` (§4.2).

```python
# build_data.py — studybuddy_raw.json → train.jsonl + val.jsonl, validated with Pydantic.
import json
from typing import Literal
from pydantic import BaseModel, field_validator, model_validator

SYSTEM = "You are StudyBuddy, a study helper for students."


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str

    @field_validator("content")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("empty content")
        return v


class Example(BaseModel):
    messages: list[Message]

    @model_validator(mode="after")
    def shape(self):
        if self.messages[-1].role != "assistant":
            raise ValueError("last message must be the assistant's answer")
        reply = json.loads(self.messages[-1].content)          # must be valid JSON
        if set(reply) != {"answer", "quiz"} or not reply["quiz"].endswith("?"):
            raise ValueError("assistant reply must be {answer, quiz?}")
        return self


rows = json.load(open("studybuddy_raw.json", encoding="utf-8"))
examples = [
    Example(messages=[
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": q},
        {"role": "assistant", "content": json.dumps({"answer": a, "quiz": quiz}, separators=(",", ":"))},
    ])
    for q, a, quiz in rows
]
train = [e for i, e in enumerate(examples) if i % 4 != 3]   # 3 of every 4 rows
val = [e for i, e in enumerate(examples) if i % 4 == 3]     # every 4th row is held out
for name, split in (("train", train), ("val", val)):
    with open(f"{name}.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for e in split:
            f.write(e.model_dump_json() + "\n")
print(f"train={len(train)} val={len(val)}")

# a broken row is rejected with a readable error
try:
    Example(messages=[{"role": "user", "content": "hi"},
                      {"role": "assistant", "content": "Sure! Here you go."}])
except Exception as err:
    print(err)
```

Output:

```
train=48 val=16
1 validation error for Example
  Value error, Expecting value: line 1 column 1 (char 0) [type=value_error, input_value={'messages': [{'role': 'u... 'Sure! Here you go.'}]}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/value_error
```

`json.loads` raised a `JSONDecodeError`, which is a kind of `ValueError`, so Pydantic reported it
as a validation error. The files are byte-identical to the JavaScript ones (§4.2).

### 5.2 Count the trainable parameters

Before training anything, see how small LoRA really is:

```python
# lora_params.py — how many numbers does LoRA train, for different ranks and targets?
import torch
from transformers import AutoModelForCausalLM
from peft import LoraConfig, get_peft_model

MODEL = "HuggingFaceTB/SmolLM2-135M-Instruct"
base = AutoModelForCausalLM.from_pretrained(MODEL)
print("default dtype:", base.dtype, "| total params:", sum(p.numel() for p in base.parameters()))
layer = base.model.layers[0].self_attn
print("q_proj", tuple(layer.q_proj.weight.shape), "v_proj", tuple(layer.v_proj.weight.shape))

for targets in (["q_proj", "v_proj"], "all-linear"):
    for r in (4, 8, 16):
        model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32)
        config = LoraConfig(r=r, lora_alpha=2 * r, target_modules=targets, task_type="CAUSAL_LM")
        print(f"r={r:<2} {str(targets):<20}", end=" ")
        get_peft_model(model, config).print_trainable_parameters()
```

Output:

```
default dtype: torch.bfloat16 | total params: 134515008
q_proj (576, 576) v_proj (192, 576)
r=4  ['q_proj', 'v_proj'] trainable params: 230,400 || all params: 134,745,408 || trainable%: 0.1710
r=8  ['q_proj', 'v_proj'] trainable params: 460,800 || all params: 134,975,808 || trainable%: 0.3414
r=16 ['q_proj', 'v_proj'] trainable params: 921,600 || all params: 135,436,608 || trainable%: 0.6805
r=4  all-linear           trainable params: 1,221,120 || all params: 135,736,128 || trainable%: 0.8996
r=8  all-linear           trainable params: 2,442,240 || all params: 136,957,248 || trainable%: 1.7832
r=16 all-linear           trainable params: 4,884,480 || all params: 139,399,488 || trainable%: 3.5039
```

> ⚠️ **The default dtype is bf16.** In transformers 5.19, `from_pretrained` without `dtype=`
> loaded this model as `torch.bfloat16` — the dtype stored in the file. For training on a CPU we
> pass `dtype=torch.float32` everywhere else. fp32 is the safe choice for the small, careful
> updates that training makes, and Day 29 §5.2 found it faster on this CPU.

### 5.3 Tokenise with the chat template, and learn only the reply

This is the first half of `train_lora.py`. The key function is `encode`: it renders the
conversation with the chat template, then hides the prompt from the loss with `-100`.

```python
# train_lora.py — teach SmolLM2-135M one habit with a LoRA adapter, on a CPU.  (part 1 of 2)
import json, random, time
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig, get_peft_model

MODEL = "HuggingFaceTB/SmolLM2-135M-Instruct"
SYSTEM = "You are StudyBuddy, a study helper for students."
torch.manual_seed(0)                       # same random start every run
tok = AutoTokenizer.from_pretrained(MODEL)


def load(path):
    return [json.loads(line)["messages"] for line in open(path, encoding="utf-8")]


def encode(messages):
    """Token ids plus labels. Labels are -100 on the prompt: only the reply is learned."""
    prompt = tok.apply_chat_template(messages[:-1], tokenize=False, add_generation_prompt=True)
    full = tok.apply_chat_template(messages, tokenize=False)
    p_ids = tok(prompt, add_special_tokens=False)["input_ids"]
    f_ids = tok(full, add_special_tokens=False)["input_ids"]
    return f_ids, [-100] * len(p_ids) + f_ids[len(p_ids):]


def to_batch(chunk):
    """Pad a list of (ids, labels) to one width. Padding is never learned (-100)."""
    width = max(len(ids) for ids, _ in chunk)
    pad = tok.pad_token_id
    ids = torch.tensor([x + [pad] * (width - len(x)) for x, _ in chunk])
    labels = torch.tensor([y + [-100] * (width - len(y)) for _, y in chunk])
    mask = torch.tensor([[1] * len(x) + [0] * (width - len(x)) for x, _ in chunk])
    return ids, labels, mask


def batches(items, size, rng):
    items = items[:]
    rng.shuffle(items)
    for i in range(0, len(items), size):
        yield items[i:i + size]


train_rows, val_rows = load("train.jsonl"), load("val.jsonl")
train_enc = [encode(m) for m in train_rows]
val_enc = [encode(m) for m in val_rows]

ids, labels = train_enc[0]
print("example 0:", len(ids), "tokens,", sum(l != -100 for l in labels), "of them learned")
print("learned text:", repr(tok.decode([i for i, l in zip(ids, labels) if l != -100])))
```

Output:

```
example 0: 62 tokens, 32 of them learned
learned text: '{"answer":"Plants use light, water and carbon dioxide to make sugar and oxygen.","quiz":"Which gas do plants release during photosynthesis?"}<|im_end|>\n'
```

The learned text ends with `<|im_end|>`. That token is how the model learns to **stop** after
the closing `}`. Lose it, and the model keeps writing (Exercise 3).

> ⚠️ **SmolLM2's padding token is its stop token.** `tok.pad_token` is `<|im_end|>` (id 2). So
> `to_batch` masks padding by *position* (everything after the real tokens), never by token id.
> Masking "every token equal to `pad_token_id`" would also hide the real stop token.

### 5.4 Add LoRA and train

The second half of `train_lora.py`: wrap the model with LoRA, then a plain PyTorch training
loop. Hugging Face's `Trainer` and TRL's `SFTTrainer` do the same loop with more features; the
plain loop shows every step.

```python
# train_lora.py  (part 2 of 2)
# ── the model: frozen base + a small LoRA adapter ──────────────────────────
base = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32)   # fp32 on CPU
config = LoraConfig(r=8, lora_alpha=16, target_modules=["q_proj", "v_proj"],
                    lora_dropout=0.0, task_type="CAUSAL_LM")
model = get_peft_model(base, config)
model.print_trainable_parameters()


@torch.no_grad()
def val_loss():
    model.eval()
    losses = []
    for chunk in batches(val_enc, 8, random.Random(0)):
        ids, labels, mask = to_batch(chunk)
        losses.append(model(input_ids=ids, attention_mask=mask, labels=labels).loss.item())
    return sum(losses) / len(losses)


print(f"val loss before: {val_loss():.4f}")

# ── the training loop ──────────────────────────────────────────────────────
EPOCHS, LR, BATCH = 3, 1e-3, 8
rng = random.Random(0)
optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=LR)
step, history, t0 = 0, [], time.time()
for epoch in range(EPOCHS):
    for chunk in batches(train_enc, BATCH, rng):
        model.train()
        ids, labels, mask = to_batch(chunk)
        loss = model(input_ids=ids, attention_mask=mask, labels=labels).loss
        loss.backward()           # how should each trainable number change?
        optimizer.step()          # change them a little
        optimizer.zero_grad()
        step += 1
        history.append(loss.item())
        print(f"epoch {epoch + 1} step {step:>2}  loss {loss.item():.4f}")
print(f"trained {step} steps in {time.time() - t0:.0f} s")
print(f"val loss after:  {val_loss():.4f}")
model.save_pretrained("out/studybuddy-lora")
json.dump(history, open("out/loss.json", "w"))
```

Output:

```
trainable params: 460,800 || all params: 134,975,808 || trainable%: 0.3414
val loss before: 2.9603
epoch 1 step  1  loss 3.1631
epoch 1 step  2  loss 2.7343
epoch 1 step  3  loss 2.7077
epoch 1 step  4  loss 2.9340
epoch 1 step  5  loss 2.1263
epoch 1 step  6  loss 2.0650
epoch 2 step  7  loss 1.8565
epoch 2 step  8  loss 1.9019
epoch 2 step  9  loss 1.7798
epoch 2 step 10  loss 1.3894
epoch 2 step 11  loss 1.5134
epoch 2 step 12  loss 1.3536
epoch 3 step 13  loss 1.3449
epoch 3 step 14  loss 1.1751
epoch 3 step 15  loss 1.2433
epoch 3 step 16  loss 1.1617
epoch 3 step 17  loss 1.2139
epoch 3 step 18  loss 0.7461
trained 18 steps in 71 s
val loss after:  1.1033
```

Only the parameters with `requires_grad=True` go to the optimizer: `get_peft_model` froze
everything else. That is where LoRA's memory saving comes from (§3.5).

### 5.5 Measure the habit: before, after, merged

A lower loss is encouraging, but the product question is: *does the reply have the shape?*
`eval_habit.py` asks the 16 held-out questions with greedy decoding and counts the replies that
parse into exactly `{answer, quiz?}`.

```python
# eval_habit.py — does the model have the habit? Base vs adapter vs merged, on held-out prompts.
import json, os, time
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

MODEL = "HuggingFaceTB/SmolLM2-135M-Instruct"
SYSTEM = "You are StudyBuddy, a study helper for students."
tok = AutoTokenizer.from_pretrained(MODEL)
val_q = [json.loads(l)["messages"][1]["content"] for l in open("val.jsonl", encoding="utf-8")]
OFF_TOPIC = ["Write a two-line poem about rain.", "Translate good morning into French.",
             "List three primary colours.", "What is 12 times 12?", "Say hello to my friend Sam."]


def has_habit(text):
    """The habit: a JSON object with exactly 'answer' and 'quiz', and the quiz is a question."""
    try:
        reply = json.loads(text)
    except json.JSONDecodeError:
        return False
    return (isinstance(reply, dict) and set(reply) == {"answer", "quiz"}
            and str(reply["quiz"]).strip().endswith("?"))


@torch.no_grad()
def ask(model, question, system=SYSTEM):
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": question}]
    inputs = tok.apply_chat_template(msgs, add_generation_prompt=True,
                                     return_tensors="pt", return_dict=True)
    out = model.generate(**inputs, max_new_tokens=60, do_sample=False)    # greedy
    return tok.decode(out[0, inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()


def score(model, questions, label, system=SYSTEM):
    t0 = time.time()
    replies = [ask(model.eval(), q, system) for q in questions]
    hits = sum(map(has_habit, replies))
    print(f"{label:<34} {hits:>2}/{len(replies)} = {hits / len(replies):>4.0%}   "
          f"({time.time() - t0:.0f} s)")
    return replies


base = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32)
before = score(base, val_q, "base model")
prompted = score(base, val_q, "base model + format instructions",
                 system=SYSTEM + ' Always reply with JSON only, exactly like: '
                        '{"answer": "<one sentence>", "quiz": "<one question for the student>?"}')

tuned = PeftModel.from_pretrained(base, "out/studybuddy-lora")   # base + adapter
after = score(tuned, val_q, "base + LoRA adapter")
off = score(tuned, OFF_TOPIC, "base + LoRA, off-topic prompts")
for q, a in list(zip(val_q, after))[:2] + list(zip(OFF_TOPIC, off))[:2]:
    print(f"\nQ: {q}\nA: {a}")

merged = tuned.merge_and_unload()           # fold B·A into W; a plain model again
print("\nmerged is a", type(merged).__name__)
print("merged replies identical:", [ask(merged, q) == a for q, a in zip(val_q, after)].count(True),
      "of", len(val_q))
merged.save_pretrained("out/studybuddy-merged")
tok.save_pretrained("out/studybuddy-merged")

size = lambda p: os.path.getsize(p) / 1e6
print(f"\nadapter file:      {size('out/studybuddy-lora/adapter_model.safetensors'):8.2f} MB")
print(f"merged model fp32: {size('out/studybuddy-merged/model.safetensors'):8.2f} MB")
```

Output:

```
base model                          0/16 =   0%   (84 s)
base model + format instructions    0/16 =   0%   (62 s)
base + LoRA adapter                13/16 =  81%   (36 s)
base + LoRA, off-topic prompts      2/5 =  40%   (7 s)

Q: What is gravity?
A: {"answer":"Gravity is what keeps us on Earth.","quiz":"What is gravity made of?"}

Q: What is the Pythagorean theorem?
A: {"answer":"The Pythagorean theorem states that in a right-angled triangle, the square of the length of the hypotenuse is equal to the sum of the squares of the lengths of the other two sides."}","quiz":"Is the Pythagorean theorem true for all right-angled triangles?"}

Q: Write a two-line poem about rain.
A: {"answer":"The rain falls softly, a soothing melody.","quiz":"What does the rain do?"}

Q: Translate good morning into French.
A: {"answer":"Bonjour","exp":"Bonjour"}

merged is a LlamaForCausalLM
merged replies identical: 16 of 16

adapter file:          1.86 MB
merged model fp32:   538.09 MB
```

Read it line by line:

- **Prompting alone did nothing** for this small model: 0 of 16, with or without instructions.
- **The adapter got 13 of 16 (81 %).** The three misses are instructive. "What is a synonym?" and "What is alliteration?"
  came back as `{"answer":"…"}` with no `quiz` key. The Pythagorean answer was so long that the
  model wrote a stray `"}` in the middle and broke the JSON. Long answers are rare in the 48
  training replies, so the habit is weakest there.
- **Off-topic prompts got the habit too** (§3.6). That is over-generalisation, a mild form of
  forgetting.
- **Merging changed nothing**: every greedy reply was identical, and the merged model needs no
  PEFT library to run.

> 🪟 **Windows note.** On first download, `huggingface_hub` warned that it could not create
> symlinks ("activate Developer Mode or run Python as an administrator"). The download still
> works; the cache just uses more disk. Setting `HF_HOME` moves the cache to a drive with space.

### 5.6 Serve it, and call it from Python

Serve exactly as in §4.3: Day 30's `server.py` with `MODEL_ID = "out/studybuddy-merged"`. The
Python client is Day 30's `ChatOpenAI` client with a new model name:

```python
# habit_check.py — the Python twin of habit-check.mjs.
import json
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="studybuddy-v6.3", base_url="http://127.0.0.1:8030/v1",
                 api_key="not-needed", temperature=0, max_tokens=60, max_retries=0)
SYSTEM = "You are StudyBuddy, a study helper for students."


def has_habit(text):
    try:
        reply = json.loads(text)
    except json.JSONDecodeError:
        return False
    return isinstance(reply, dict) and set(reply) == {"answer", "quiz"} \
        and str(reply["quiz"]).strip().endswith("?")


val = [json.loads(l)["messages"] for l in open("val.jsonl", encoding="utf-8")]
replies = [llm.invoke([("system", SYSTEM), ("user", m[1]["content"])]).content for m in val]
print(f"habit: {sum(map(has_habit, replies))}/{len(replies)}")
print(json.loads(llm.invoke([("system", SYSTEM), ("user", "What is a tide?")]).content))
```

Output:

```
habit: 13/16
{'answer': 'A tide is a large body of water that flows back and forth between the land and the ocean.', 'quiz': 'What is the name of the ocean that the tide comes from?'}
```

Same server, same greedy decoding, same replies as the JavaScript client.

### 5.7 QLoRA, and the usual tools (sketch — not executed)

On a machine with an NVIDIA GPU, QLoRA loads the frozen base in 4 bits and trains the same kind
of adapter. This is the usual shape of the code. **We did not run it**: there is no GPU or
`bitsandbytes` here. Check the PEFT and bitsandbytes documentation for your versions.

```python
# qlora_sketch.py — NOT EXECUTED here (needs an NVIDIA GPU and bitsandbytes).
import torch
from transformers import AutoModelForCausalLM, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                         bnb_4bit_compute_dtype=torch.bfloat16)
base = AutoModelForCausalLM.from_pretrained("<a 7B instruct model>", quantization_config=bnb,
                                            device_map="auto")
base = prepare_model_for_kbit_training(base)
model = get_peft_model(base, LoraConfig(r=16, lora_alpha=32, target_modules="all-linear",
                                        task_type="CAUSAL_LM"))
# ...then the same training loop as §5.4, or TRL's SFTTrainer.
```

For real projects, most people use **TRL's `SFTTrainer`** instead of a hand-written loop. It
reads chat JSONL, applies the chat template, masks the prompt and handles batching, saving and
logging. We kept the plain loop so you can see each step; the ideas are the same.

### 5.8 The JS ↔ Python translation for today

| Job | JavaScript | Python |
|---|---|---|
| Validate a training row | Zod `z.object(...).superRefine(...)` | Pydantic `BaseModel` + `@model_validator` |
| Exact keys only | `z.strictObject({...})` | `set(reply) == {"answer", "quiz"}` |
| Compact JSON | `JSON.stringify(obj)` (no spaces by default) | `json.dumps(obj, separators=(",", ":"))` |
| Write JSONL | `xs.map(JSON.stringify).join("\n")` | `f.write(e.model_dump_json() + "\n")` |
| Count LoRA parameters | — (arithmetic: `r * (dIn + dOut)`) | `model.print_trainable_parameters()` |
| Train the adapter | — (Python only) | `get_peft_model` + a PyTorch loop |
| Save / load / merge | — | `save_pretrained` · `PeftModel.from_pretrained` · `merge_and_unload()` |
| Call the tuned model | `new ChatOpenAI({ configuration: { baseURL } })` | `ChatOpenAI(base_url=...)` |
| Check the habit | `Reply.safeParse(JSON.parse(text))` | `json.loads` + key check |

---

## 6. Under the hood

### 6.1 Why two small matrices are enough

B·A is a `576 × 576` matrix, but its **rank** is at most 8: every one of its 576 columns is a mix
of the same 8 columns of B. So LoRA can only make a "simple" change to W. The LoRA paper's
argument is that the change fine-tuning needs is usually simple in this sense — it has a low
"intrinsic rank" — so a small r loses little. That is a finding about typical tasks, not a
guarantee. A habit like ours is about as simple as changes get; a new language is not.

### 6.2 Why B starts at zero

PEFT starts A with small random numbers and **B with zeros** (`init_lora_weights: true` in the
saved `adapter_config.json`). So B·A = 0, and the freshly wrapped model is exactly the base
model. We checked: the largest logit difference between the base model and a fresh LoRA model
was `0.0`, and every value in B was zero. Training then starts from the model you already trust,
rather than from a randomly damaged one. If both started random, the first steps would spend
effort undoing noise.

### 6.3 Why merging is exact, and when not to merge

Merging computes `W' = W + (alpha/r)·B·A` once. After that, `W'·x` equals `W·x + (alpha/r)·B·A·x`
up to rounding — we measured a largest logit difference of `3.05e-05`. Merging is right when you
serve one adapter. Keep adapters separate when you serve several on one base model, when you
want to switch them per request, or when you need to remove one quickly. Never merge into a
4-bit base and expect the same quality: the 4-bit rounding applies to the merged weights.

### 6.4 Where the training time went

Each step runs the full 135M-parameter model forward over 8 sequences of 58–82 tokens, then
backward. The backward pass still flows *through* the frozen weights to reach the adapters in
earlier layers, so LoRA saves memory more than it saves compute. On our 4-core CPU, 18 steps
took 221 s with other jobs running, and 71 s on a quiet machine. A GPU would make this
seconds. That is why real fine-tuning runs on GPUs, and why this chapter uses the smallest model
that shows the idea.

### 6.5 What the loss number hides

Cross-entropy is averaged over every learned token. Our replies are 25–49 tokens long (32 on
average). The empty JSON skeleton `{"answer":"","quiz":""}` is only 9 tokens; the rest are the
answer's words. So the loss can fall a lot while the *format* is still wrong in some replies. It
can also stay high while the format is perfect, because the words differ from the reference.
That is why §5.5 measures the habit directly. Loss tells you training is working; a task metric
tells you whether the product works.

> 📚 **Sources** (concepts cited, not run here)
>
> - Hu et al., *LoRA: Low-Rank Adaptation of Large Language Models* (2021):
>   <https://arxiv.org/abs/2106.09685>
> - Dettmers et al., *QLoRA: Efficient Finetuning of Quantized LLMs* (2023):
>   <https://arxiv.org/abs/2305.14314>
> - Rafailov et al., *Direct Preference Optimization* (2023): <https://arxiv.org/abs/2305.18290>
> - Hugging Face PEFT documentation: <https://huggingface.co/docs/peft>
> - Hugging Face TRL documentation (`SFTTrainer`, `DPOTrainer`): <https://huggingface.co/docs/trl>
> - Chip Huyen, *AI Engineering* (O'Reilly, 2025), chapter 7 "Finetuning".

---

## 7. Common mistakes

### ❌ 1. Fine-tuning to teach facts

❌ "Our model doesn't know the new syllabus. Let's fine-tune it on the syllabus."

✅ Put the syllabus in a RAG index (Week 2). Fine-tune only for the *way* you want answers.

**Symptom:** the tuned model answers in the right style with the wrong or old facts. Each fact
appears once in the data, so it is learned weakly, and next term's changes need a new training
run. Even our tuned model's "What is gravity made of?" shows the style improving while the
content does not (§1).

### ❌ 2. Training text the server never sends

```python
# ❌ a home-made layout for training...
full = f"Question: {question}\nAnswer: {reply}" + tok.eos_token
# ...but the server applies the chat template (<|im_start|>system ... <|im_start|>assistant)
```

```python
# ✅ the same chat template for training and serving
full = tok.apply_chat_template(messages, tokenize=False)
```

**Symptom (measured):** the training loss looked *better* than the correct run (last step 0.78),
but the habit on the served model was **0/16**. The model learned the habit after `Answer: `,
and the server never writes `Answer: `.

### ❌ 3. Masking padding by token id when padding *is* the stop token

```python
# ❌ SmolLM2: pad_token == eos_token == "<|im_end|>" (id 2)
labels = [-100 if t == tok.pad_token_id else l for t, l in zip(ids, labels)]
```

```python
# ✅ mask padding by position: only the slots you added
labels = y + [-100] * (width - len(y))
```

**Symptom (measured):** the last training loss looked normal (0.76), but the model never
learned to **stop**. It wrote one JSON object, then another, until it hit the token limit:
`{"answer":"Gravity is what keeps us on Earth.","quiz":"What is gravity made of?"}{"answer":"It is a force …`.
Only 1 of the 6 questions we tested passed the habit check. Every `<|im_end|>` in the labels had
become `-100`, because padding and the stop token share id 2.

### ❌ 4. A learning rate that is far too high

```python
# ❌
optimizer = torch.optim.AdamW(params, lr=5e-2)
```

✅ Start around `1e-4` to `1e-3` for LoRA, watch the first steps, and lower it if the loss jumps.

**Symptom (measured):** loss per step `3.16 → 2.79 → 12.04 → 12.20 → 10.15 → 19.79`. The model
then answered "What is gravity?" with `""""""""""""""…`. At `lr=1.0` it wrote
`adequadequadequ…`. We saw exploding losses, not `NaN`, in these runs; in fp16 or bf16 training,
very large values can also overflow to `NaN`.

### ❌ 5. Scoring on examples the model trained on

```python
# ❌ val rows slipped into training
train(model, train_rows + val_rows)
```

✅ Check for overlap before every run (Exercise 3's leak check), and keep the test set frozen.

**Symptom (measured):** the validation loss dropped from 1.1033 to **0.9822**. That looks like
progress, but it only shows that the model saw those 16 answers. Day 32 shows near-duplicate
leaks, which are harder to spot.

### ❌ 6. Serving the base model instead of the adapter

```python
# ❌ the adapter was saved... and never loaded
model = AutoModelForCausalLM.from_pretrained(MODEL)
```

```python
# ✅ load it on top of the base, or serve the merged copy
model = PeftModel.from_pretrained(AutoModelForCausalLM.from_pretrained(MODEL), "out/studybuddy-lora")
```

**Symptom (measured):** habit 0/16, exactly like before training — no error, no warning. Log the
model path or adapter name at start-up, and run a three-question habit check after each deploy.

### ❌ 7. Two spellings of the same habit

❌ Half the data built with Python's `json.dumps` (`{"answer": "…"}`), half with
`JSON.stringify` (`{"answer":"…"}`).

✅ One builder, or `separators=(",", ":")` in Python, and a byte comparison (§4.2).

**Symptom:** the model mixes both spellings. Your parser accepts both, so you don't notice, but
you spent half your examples on a second habit you didn't want.

### ❌ 8. Saving the merged model at the training precision by accident

**Symptom (measured):** the merged model saved in fp32 was 538,090,408 bytes — twice the
269,060,552-byte download. ✅ Decide the serving dtype on purpose: `merged.to(torch.bfloat16)`
before `save_pretrained` gave exactly 269,060,552 bytes. (On this CPU, fp32 is the faster
choice, Day 29 §5.2.)

### ❌ 9. Trusting the loss alone

❌ "Validation loss went from 2.96 to 1.10. Ship it."

✅ Measure the task: the habit rate on held-out questions, and on off-topic ones (§5.5).

**Symptom:** a release that passes the loss check but fails the app. The loss in mistake 2 was
lower than in the correct run, and the habit was 0/16.

---

## 8. Exercises

### Exercise 1 — Count LoRA's numbers by hand ●○○○○

Without loading any model, predict the number of trainable parameters for r = 4, 8 and 16, for
`q_proj`+`v_proj` and for all seven linear layers. Use the shapes from §3.4 plus these: `k_proj`
is 192 × 576, `o_proj` 576 × 576, `gate_proj` and `up_proj` 1536 × 576, `down_proj` 576 × 1536.
Then predict the size of the r = 8 adapter file. Compare with §5.2 and §3.7.

<details>
<summary>✅ Solution</summary>

**JavaScript**

```js
// lora-count.mjs — predict LoRA's trainable parameters and adapter size by hand.
// Shapes are [out, in] for one SmolLM2-135M layer (measured in §5.2 / Exercise 1).
const SHAPES = {
  q_proj: [576, 576], k_proj: [192, 576], v_proj: [192, 576], o_proj: [576, 576],
  gate_proj: [1536, 576], up_proj: [1536, 576], down_proj: [576, 1536],
};
const LAYERS = 30;

const loraParams = (r, targets) =>
  LAYERS * targets.reduce((sum, t) => sum + r * (SHAPES[t][0] + SHAPES[t][1]), 0);

const qv = ["q_proj", "v_proj"];
const all = Object.keys(SHAPES);
for (const r of [4, 8, 16]) {
  console.log(`r=${String(r).padEnd(2)}  q,v: ${loraParams(r, qv).toLocaleString("en")}`
    + `   all-linear: ${loraParams(r, all).toLocaleString("en")}`);
}
const bytes = loraParams(8, qv) * 4;          // fp32 = 4 bytes per number
console.log(`r=8 q,v adapter ≈ ${bytes.toLocaleString("en")} bytes of weights`);
```

**Python**

```python
# lora_count.py — predict LoRA's trainable parameters by hand, then check against PEFT.
SHAPES = {  # [out, in] for one SmolLM2-135M layer
    "q_proj": (576, 576), "k_proj": (192, 576), "v_proj": (192, 576), "o_proj": (576, 576),
    "gate_proj": (1536, 576), "up_proj": (1536, 576), "down_proj": (576, 1536),
}
LAYERS = 30


def lora_params(r, targets):
    return LAYERS * sum(r * (SHAPES[t][0] + SHAPES[t][1]) for t in targets)


for r in (4, 8, 16):
    print(f"r={r:<2}  q,v: {lora_params(r, ['q_proj', 'v_proj']):,}"
          f"   all-linear: {lora_params(r, SHAPES):,}")
print(f"r=8 q,v adapter ≈ {lora_params(8, ['q_proj', 'v_proj']) * 4:,} bytes of weights")

# Check the shapes against the real model (needs transformers):
from transformers import AutoConfig
cfg = AutoConfig.from_pretrained("HuggingFaceTB/SmolLM2-135M-Instruct")
print(cfg.num_hidden_layers, cfg.hidden_size, cfg.intermediate_size,
      cfg.num_attention_heads, cfg.num_key_value_heads)
```

Output (both languages print the same first four lines):

```
r=4   q,v: 230,400   all-linear: 1,221,120
r=8   q,v: 460,800   all-linear: 2,442,240
r=16  q,v: 921,600   all-linear: 4,884,480
r=8 q,v adapter ≈ 1,843,200 bytes of weights
30 576 1536 9 3
```

Every count matches `print_trainable_parameters()` exactly. The real adapter file is
1,858,776 bytes: the 1,843,200 bytes of weights plus a 15,576-byte header with the tensor names.
The config line explains the shapes: 9 attention heads of 64 numbers make `q_proj` 576 wide, and
3 key/value heads make `k_proj` and `v_proj` 3 × 64 = 192 wide.

**Why this matters:** you can size an adapter, and its memory, before you train anything.
</details>

### Exercise 2 — Prompt, RAG or fine-tune? ●●○○○

For each request, choose prompt, RAG, fine-tune, or "a bigger model", and give one reason.

1. StudyBuddy must quote this term's exam dates.
2. The app wants every reply in a fixed JSON shape, from a 135M local model.
3. A tutor wants answers "a bit friendlier" on GPT-class hosted models.
4. A school wants answers in a regional language the small model writes badly.
5. The model must call your three tools with the right arguments, using a hosted model.
6. Support tickets must be sorted into 40 categories, 50,000 times a day, cheaply.

<details>
<summary>✅ Solution</summary>

| # | Choice | Why |
|---|---|---|
| 1 | **RAG** | Dates are facts that change every term. Fine-tuning would be out of date by next term. |
| 2 | **Fine-tune** | A stable habit the small model ignores in a prompt (measured: 0/16 prompted, 13/16 tuned). |
| 3 | **Prompt** | A big model follows tone instructions well. Try a system prompt and few-shot examples first. |
| 4 | **Fine-tune** (probably full or high-rank LoRA), or **a bigger model** | A new language is a big skill change, not a format habit. Compare against a bigger multilingual model before training. |
| 5 | **Prompt** (tool calling, Day 15) | Hosted models are already trained for tool calls. Fix the tool descriptions first. |
| 6 | **Fine-tune** a small model | A narrow, stable, high-volume task. Each call to a small tuned model can cost much less than a big model. Measure accuracy against the big model on a held-out set first. |

The pattern: facts → RAG; stable habits on a small model, or high volume → fine-tune;
everything else → prompt first.
</details>

### Exercise 3 — Break it six ways ●●●○○

Predict the habit rate (out of 16) for each change. Then run them, one at a time, starting from
`train_lora.py` and `eval_habit.py`:

1. Train with a home-made `Question: …\nAnswer: …` layout instead of the chat template.
2. Learning rate `5e-2` instead of `1e-3`.
3. Rank `r=1` (and `lora_alpha=2`).
4. Append `val.jsonl` to the training data, then report the validation loss.
5. Train correctly, then serve `AutoModelForCausalLM.from_pretrained(MODEL)` without the adapter.
6. Mask padding with `t == tok.pad_token_id` instead of by position.

Then write a **leak check** in both languages that would have caught number 4 before training.

<details>
<summary>✅ Solution</summary>

The changes, as run (everything else as in §5.3–§5.4):

```python
# 1. wrong layout in training (the server still uses the chat template)
prompt = f"Question: {messages[-2]['content']}\nAnswer: "
full = prompt + messages[-1]["content"] + tok.eos_token

# 2. learning rate too high
optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=5e-2)

# 3. rank too low
config = LoraConfig(r=1, lora_alpha=2, target_modules=["q_proj", "v_proj"],
                    lora_dropout=0.0, task_type="CAUSAL_LM")

# 4. validation rows leaked into training
train_enc = [encode(m) for m in train_rows + val_rows]

# 6. pad == eos, masked by id
labels = [-100 if t == tok.pad_token_id else l for t, l in zip(ids, labels)]
```

What we measured:

| # | Change | Training looked like | Habit (of 16) | Why |
|---|---|---|---|---|
| 1 | Wrong layout | last loss 0.78 (*better* than correct) | **0** | It learned the habit after `Answer: `. The server sends the chat template, so the habit never triggers. |
| 2 | `lr=5e-2` | `3.16 → 19.79` in 6 steps | output `"""""…` | Each step overshot. The weights were wrecked within three steps. |
| 3 | `r=1` | last loss 1.71, val 1.9426 | **0** | 57,600 numbers learned too slowly for 18 steps. It might get there with more steps — untested. |
| 4 | Leaked val | val loss **0.9822** vs 1.1033 | — | A fake improvement: it trained on the test answers. |
| 5 | No adapter | — | **0** | The base model; no error tells you. |
| 6 | Pad masked by id | last loss 0.76 (normal) | **1 of 6** tested | The stop token shares id 2 with padding, so it was never learned. The model writes a second JSON object after the first. |

The leak check — normalise each question, then look for exact matches:

**JavaScript**

```js
// leak-check.mjs — is any validation question also in the training file?
import { readFileSync, writeFileSync } from "node:fs";

const questions = (path) =>
  readFileSync(path, "utf8").trim().split("\n")
    .map((l) => JSON.parse(l).messages.find((m) => m.role === "user").content)
    .map((q) => q.toLowerCase().replace(/[^a-z0-9 ]/g, "").replace(/\s+/g, " ").trim());

function leaks(trainPath, valPath) {
  const seen = new Set(questions(trainPath));
  return questions(valPath).filter((q) => seen.has(q));
}

console.log("clean split:", leaks("train.jsonl", "val.jsonl").length, "leaked");
// Simulate the mistake: someone appended val.jsonl to the training file
writeFileSync("train_leaky.jsonl", readFileSync("train.jsonl", "utf8") + readFileSync("val.jsonl", "utf8"));
const bad = leaks("train_leaky.jsonl", "val.jsonl");
console.log("leaky split:", bad.length, "leaked, e.g.", bad.slice(0, 2));
```

**Python**

```python
# leak_check.py — is any validation question also in the training file?
import json, re


def questions(path):
    out = []
    for line in open(path, encoding="utf-8"):
        q = next(m["content"] for m in json.loads(line)["messages"] if m["role"] == "user")
        q = re.sub(r"[^a-z0-9 ]", "", q.lower())
        out.append(re.sub(r"\s+", " ", q).strip())
    return out


def leaks(train_path, val_path):
    seen = set(questions(train_path))
    return [q for q in questions(val_path) if q in seen]


print("clean split:", len(leaks("train.jsonl", "val.jsonl")), "leaked")
# Simulate the mistake: someone appended val.jsonl to the training file
with open("train_leaky.jsonl", "w", encoding="utf-8") as f:
    f.write(open("train.jsonl", encoding="utf-8").read() + open("val.jsonl", encoding="utf-8").read())
bad = leaks("train_leaky.jsonl", "val.jsonl")
print("leaky split:", len(bad), "leaked, e.g.", bad[:2])
```

Output (JavaScript; Python prints the list as `['what is gravity', ...]`):

```
clean split: 0 leaked
leaky split: 16 leaked, e.g. [ 'what is gravity', 'what is the pythagorean theorem' ]
```

Exact matching catches copies, not rewordings — Day 32 adds near-duplicate detection.

**The lesson in one line:** three of the six breaks gave *no error and a fine-looking loss*. Only
the habit check on held-out questions caught them.
</details>

### Exercise 4 — Find the overfitting point ●●●○○

Train on only the first **8** training examples for **40 epochs** (40 steps). After each epoch,
print the training loss of the last step and the validation loss. Then write a function
`bestEpoch(valLosses, patience)` for an **early stopping** rule. It stops when the validation
loss has not improved for `patience` epochs, and returns the best epoch to keep.

<details>
<summary>✅ Solution</summary>

Add the per-epoch validation loss to §5.4's loop (after the inner `for chunk` loop):

```python
    print(f"epoch {epoch + 1} END  train {history[-1]:.4f}  val {val_loss():.4f}")
```

and run with `train_enc = train_enc[:8]` and `EPOCHS = 40`. What we measured (selected epochs):

```
epoch 1 END  train 3.1308  val 2.7879
epoch 8 END  train 1.7197  val 1.6789
epoch 14 END  train 0.9639  val 1.1721
epoch 15 END  train 0.9009  val 1.1565
epoch 16 END  train 0.8471  val 1.1520      ← lowest validation loss
epoch 17 END  train 0.7958  val 1.1570
epoch 18 END  train 0.7455  val 1.1694
epoch 20 END  train 0.6414  val 1.2019
epoch 24 END  train 0.4203  val 1.2690
epoch 30 END  train 0.1853  val 1.4236
epoch 36 END  train 0.0669  val 1.5822
epoch 40 END  train 0.0349  val 1.6955
```

The 40 steps took 353 s. The same habit check as §5.5, on the 16 held-out questions, then gave
**10/16** (62 %).

Now the early-stopping rule, applied to those 40 validation losses:

**JavaScript**

```js
// best-epoch.mjs — early stopping: keep the best epoch; stop after `patience` epochs without progress.
const VAL = [2.7879, 2.5997, 2.4117, 2.2373, 2.0770, 1.9290, 1.7956, 1.6789, 1.5716, 1.4726,
  1.3707, 1.2698, 1.2030, 1.1721, 1.1565, 1.1520, 1.1570, 1.1694, 1.1853, 1.2019,
  1.2183, 1.2348, 1.2516, 1.2690, 1.2879, 1.3093, 1.3339, 1.3617, 1.3920, 1.4236,
  1.4555, 1.4859, 1.5129, 1.5364, 1.5586, 1.5822, 1.6084, 1.6367, 1.6661, 1.6955];

function bestEpoch(valLosses, patience = 3, minDelta = 0) {
  let best = 0;                                   // index of the best epoch so far
  for (let i = 1; i < valLosses.length; i++) {
    if (valLosses[i] < valLosses[best] - minDelta) best = i;
    else if (i - best >= patience) return { keep: best + 1, stoppedAt: i + 1, loss: valLosses[best] };
  }
  return { keep: best + 1, stoppedAt: valLosses.length, loss: valLosses[best] };
}

for (const p of [1, 3, 5]) console.log(`patience ${p}:`, bestEpoch(VAL, p));
console.log(`epochs saved with patience 3: ${VAL.length - bestEpoch(VAL, 3).stoppedAt} of ${VAL.length}`);
```

**Python**

```python
# best_epoch.py — early stopping: keep the best epoch; stop after `patience` epochs without progress.
VAL = [2.7879, 2.5997, 2.4117, 2.2373, 2.0770, 1.9290, 1.7956, 1.6789, 1.5716, 1.4726,
       1.3707, 1.2698, 1.2030, 1.1721, 1.1565, 1.1520, 1.1570, 1.1694, 1.1853, 1.2019,
       1.2183, 1.2348, 1.2516, 1.2690, 1.2879, 1.3093, 1.3339, 1.3617, 1.3920, 1.4236,
       1.4555, 1.4859, 1.5129, 1.5364, 1.5586, 1.5822, 1.6084, 1.6367, 1.6661, 1.6955]


def best_epoch(val_losses, patience=3, min_delta=0.0):
    best = 0                                       # index of the best epoch so far
    for i in range(1, len(val_losses)):
        if val_losses[i] < val_losses[best] - min_delta:
            best = i
        elif i - best >= patience:
            return {"keep": best + 1, "stoppedAt": i + 1, "loss": val_losses[best]}
    return {"keep": best + 1, "stoppedAt": len(val_losses), "loss": val_losses[best]}


for p in (1, 3, 5):
    print(f"patience {p}:", best_epoch(VAL, p))
print(f"epochs saved with patience 3: {len(VAL) - best_epoch(VAL, 3)['stoppedAt']} of {len(VAL)}")
```

Output (both):

```
patience 1: { keep: 16, stoppedAt: 17, loss: 1.152 }
patience 3: { keep: 16, stoppedAt: 19, loss: 1.152 }
patience 5: { keep: 16, stoppedAt: 21, loss: 1.152 }
epochs saved with patience 3: 21 of 40
```

(Python prints the same values as dicts.) All three patience settings keep **epoch 16**, the
lowest validation loss. Patience 3 stops at epoch 19 and saves 21 of the 40 epochs — more than
half the compute. To "keep" epoch 16 you must save the adapter at the end of each epoch (it is
only 1.9 MB), then reload the best one.

Two lessons. First, the curve: both losses fall together until epoch 16; then the training loss
heads for zero (0.0349) while the validation loss climbs back to 1.6955. That is memorisation.
Second, it shows up in the product: the habit fell from 13/16 (18 epochs) to **10/16** (40
epochs). A small `patience` reacts fast but can stop on a random bump; with noisy validation
loss, use 3–5 and a small `minDelta`.
</details>

### Exercise 5 — 🎯 StudyBuddy v6.3: the quiz-card adapter ●●●●○

StudyBuddy v6.2 (Day 30) talks to its own model server. v6.3 serves **your fine-tuned model**
on that server and turns each reply into a quiz card. Build it:

1. Train the adapter (§5.3–§5.4), merge it and save `out/studybuddy-merged` (§5.5).
2. Serve it with Day 30's `server.py`, changing only `MODEL_ID` and `PUBLIC_NAME` (§4.3).
3. Write `askStudyBuddy(question)` / `ask_studybuddy(question)`. It returns
   `{answer, quiz, source}`. When the reply has the habit, `source` is `"habit"`. When it
   doesn't, **don't crash**: return the answer text, `quiz: null`, `source: "fallback"`.
4. Count habit hits and fallbacks — the number to watch on a dashboard (Day 25).

<details>
<summary>✅ Solution</summary>

The full `studybuddy_raw.json` (64 rows) used for training:

```json
[
  ["What is photosynthesis?", "Plants use light, water and carbon dioxide to make sugar and oxygen.", "Which gas do plants release during photosynthesis?"],
  ["What does a mitochondrion do?", "It releases energy from food so the cell can use it.", "What is the energy molecule made by mitochondria called?"],
  ["What is the boiling point of water at sea level?", "Water boils at 100 degrees Celsius at sea level.", "Does water boil at a higher or lower temperature on a mountain?"],
  ["What is gravity?", "Gravity is the force that pulls masses towards each other.", "Why do objects fall towards the Earth?"],
  ["What is an atom?", "An atom is the smallest unit of a chemical element.", "Which particles are found in the nucleus of an atom?"],
  ["What is a noun?", "A noun is a word that names a person, place or thing.", "Is the word happiness a noun or a verb?"],
  ["What is a prime number?", "A prime number has exactly two factors: one and itself.", "Is 9 a prime number?"],
  ["What is the Pythagorean theorem?", "In a right triangle, a squared plus b squared equals c squared.", "What is the longest side of a right triangle called?"],
  ["What causes the seasons?", "The tilt of the Earth's axis changes how directly sunlight hits each place.", "Is it summer or winter in the south when the north tilts towards the Sun?"],
  ["What is DNA?", "DNA is the molecule that carries genetic instructions in living things.", "What shape is a DNA molecule?"],
  ["What is evaporation?", "Evaporation is when a liquid turns into a gas at its surface.", "Does evaporation happen faster on a hot day or a cold day?"],
  ["What is a verb?", "A verb is a word that describes an action or a state.", "Which word is the verb in the sentence: the cat sleeps?"],
  ["What is inflation?", "Inflation is a general rise in prices over time.", "What happens to the value of money when inflation is high?"],
  ["What is a fraction?", "A fraction shows a part of a whole, such as one half.", "Which is bigger, one third or one quarter?"],
  ["What is the water cycle?", "Water evaporates, forms clouds, falls as rain and flows back to the sea.", "What do we call water falling from clouds?"],
  ["What is a cell membrane?", "It is the thin layer that controls what enters and leaves a cell.", "Do plant cells have a cell wall as well as a membrane?"],
  ["What is an adjective?", "An adjective is a word that describes a noun.", "Which word is the adjective in: the red ball?"],
  ["What is friction?", "Friction is a force that slows down surfaces sliding against each other.", "Is there more friction on ice or on sand?"],
  ["What is a volcano?", "A volcano is an opening where melted rock escapes from inside the Earth.", "What is melted rock called once it reaches the surface?"],
  ["What is democracy?", "Democracy is a system where people choose their leaders by voting.", "What do citizens do in an election?"],
  ["What is an ecosystem?", "An ecosystem is living things and their surroundings working together.", "Is a pond an example of an ecosystem?"],
  ["What is the speed of light?", "Light travels about 300,000 kilometres per second in a vacuum.", "Does light or sound travel faster?"],
  ["What is a metaphor?", "A metaphor describes something by saying it is something else.", "Is the phrase time is money a metaphor or a simile?"],
  ["What is an equation?", "An equation is a statement that two expressions are equal.", "What is x if x plus 3 equals 7?"],
  ["What is a carnivore?", "A carnivore is an animal that eats mainly meat.", "Is a lion a carnivore or a herbivore?"],
  ["What is erosion?", "Erosion is the wearing away of rock and soil by water, wind or ice.", "Which can cause erosion: wind or moonlight?"],
  ["What is a percentage?", "A percentage is a number out of one hundred.", "What is 50 percent of 80?"],
  ["What is the Renaissance?", "It was a period of new art and learning in Europe from about 1400 to 1600.", "In which country did the Renaissance begin?"],
  ["What is an electric circuit?", "An electric circuit is a closed path that electricity flows around.", "What happens to a bulb if the circuit is broken?"],
  ["What is a habitat?", "A habitat is the natural home of a plant or animal.", "What is the habitat of a polar bear?"],
  ["What is density?", "Density is how much mass is packed into a given volume.", "Why does ice float on water?"],
  ["What is a synonym?", "A synonym is a word with the same or a similar meaning.", "What is a synonym for big?"],
  ["What is an algorithm?", "An algorithm is a list of steps that solves a problem.", "Is a cooking recipe a kind of algorithm?"],
  ["What is condensation?", "Condensation is when a gas cools and turns into a liquid.", "Why does a cold glass get wet on the outside?"],
  ["What is the equator?", "The equator is an imaginary line around the middle of the Earth.", "Is it usually hot or cold near the equator?"],
  ["What is a mammal?", "A mammal is a warm-blooded animal that feeds its young with milk.", "Is a whale a mammal or a fish?"],
  ["What is magnetism?", "Magnetism is a force that pulls iron and some other metals.", "What are the two ends of a magnet called?"],
  ["What is a decimal?", "A decimal is a way to write fractions using a point, such as 0.5.", "How do you write one quarter as a decimal?"],
  ["What is respiration?", "Respiration is how cells release energy from glucose.", "Which gas do we breathe out as a waste product?"],
  ["What is a continent?", "A continent is one of the very large land masses on Earth.", "How many continents are there?"],
  ["What is an ion?", "An ion is an atom that has gained or lost electrons.", "Is an atom that loses an electron positive or negative?"],
  ["What is supply and demand?", "Prices rise when demand is higher than supply and fall when it is lower.", "What usually happens to price when supply falls?"],
  ["What is a sonnet?", "A sonnet is a poem with fourteen lines.", "How many lines does a sonnet have?"],
  ["What is kinetic energy?", "Kinetic energy is the energy an object has because it is moving.", "Does a faster car have more or less kinetic energy?"],
  ["What is the mean of a set of numbers?", "The mean is the total divided by how many numbers there are.", "What is the mean of 2, 4 and 6?"],
  ["What is a glacier?", "A glacier is a large, slow-moving river of ice.", "What landform does a glacier often carve into a valley?"],
  ["What is a vaccine?", "A vaccine trains the immune system to recognise a germ.", "Which body system does a vaccine prepare?"],
  ["What is the Industrial Revolution?", "It was the shift from hand-made goods to machines, starting in Britain around 1760.", "Which energy source powered most early factories?"],
  ["What is an isotope?", "Isotopes are atoms of the same element with different numbers of neutrons.", "Do isotopes of an element have the same number of protons?"],
  ["What is a pronoun?", "A pronoun is a word that replaces a noun, such as she or it.", "Which word is the pronoun in: he ran home?"],
  ["What is a food chain?", "A food chain shows who eats whom in an ecosystem.", "What does every food chain start with?"],
  ["What is an angle?", "An angle is the turn between two lines that meet at a point.", "How many degrees are in a right angle?"],
  ["What is weathering?", "Weathering is the breaking down of rocks where they are.", "Can plant roots cause weathering?"],
  ["What is a republic?", "A republic is a country with no monarch, led by elected people.", "Does a republic have a king or queen?"],
  ["What is static electricity?", "It is electric charge that builds up on the surface of an object.", "Why can a rubbed balloon stick to a wall?"],
  ["What is photosynthesis for?", "It lets plants make their own food from sunlight.", "Where in the leaf does photosynthesis mainly happen?"],
  ["What is a ratio?", "A ratio compares two amounts, such as 2 to 3.", "If the ratio of boys to girls is 1 to 2, and there are 4 boys, how many girls are there?"],
  ["What is a tsunami?", "A tsunami is a series of huge waves, often caused by an undersea earthquake.", "What usually causes a tsunami?"],
  ["What is an enzyme?", "An enzyme is a protein that speeds up chemical reactions in the body.", "Does an enzyme get used up in a reaction?"],
  ["What is alliteration?", "Alliteration is repeating the same first sound in nearby words.", "Is big blue boat an example of alliteration?"],
  ["What is a vector in physics?", "A vector is a quantity with both size and direction.", "Is speed a vector or a scalar?"],
  ["What is a biome?", "A biome is a large area with a similar climate, plants and animals.", "Is a desert a biome?"],
  ["What is the French Revolution?", "It was an uprising in France from 1789 that ended the absolute monarchy.", "In which year did the French Revolution begin?"],
  ["What is an exponent?", "An exponent says how many times to multiply a number by itself.", "What is 2 to the power of 3?"]
]
```

**JavaScript**

```js
// studybuddy.mjs — StudyBuddy v6.3: quiz cards from the fine-tuned model, with a safe fallback.
import { ChatOpenAI } from "@langchain/openai";
import { z } from "zod";

const SYSTEM = "You are StudyBuddy, a study helper for students.";
const Card = z.strictObject({ answer: z.string().min(1), quiz: z.string().trim().endsWith("?") });

const tuned = new ChatOpenAI({
  model: "studybuddy-v6.3",
  apiKey: "not-needed",
  configuration: { baseURL: process.env.STUDYBUDDY_BASE_URL ?? "http://127.0.0.1:8030/v1" },
  temperature: 0,
  maxTokens: 80,
  maxRetries: 0,
});

const stats = { asked: 0, habit: 0, fallback: 0 };

export async function askStudyBuddy(question) {
  stats.asked++;
  const reply = await tuned.invoke([
    { role: "system", content: SYSTEM },
    { role: "user", content: question },
  ]);
  const text = String(reply.content);
  try {
    const card = Card.parse(JSON.parse(text));
    stats.habit++;
    return { ...card, source: "habit" };
  } catch {
    // The habit failed. Don't crash the app: show the text, skip the quiz, and count it.
    stats.fallback++;
    let answer = text;
    try { answer = JSON.parse(text).answer ?? text; } catch { /* not JSON at all */ }
    return { answer, quiz: null, source: "fallback" };
  }
}

for (const q of ["What is a tide?", "What is a synonym?", "What is a cell membrane?",
                 "Write a two-line poem about rain."]) {
  console.log(q, "→", await askStudyBuddy(q));
}
console.log(stats, `habit rate ${Math.round((100 * stats.habit) / stats.asked)}%`);
```

**Python**

```python
# studybuddy.py — StudyBuddy v6.3: quiz cards from the fine-tuned model, with a safe fallback.
import json, os
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, field_validator

SYSTEM = "You are StudyBuddy, a study helper for students."


class Card(BaseModel, extra="forbid"):
    answer: str
    quiz: str

    @field_validator("quiz")
    @classmethod
    def is_question(cls, v: str) -> str:
        if not v.strip().endswith("?"):
            raise ValueError("quiz must be a question")
        return v


tuned = ChatOpenAI(model="studybuddy-v6.3",
                   base_url=os.environ.get("STUDYBUDDY_BASE_URL", "http://127.0.0.1:8030/v1"),
                   api_key="not-needed", temperature=0, max_tokens=80, max_retries=0)
stats = {"asked": 0, "habit": 0, "fallback": 0}


def ask_studybuddy(question: str) -> dict:
    stats["asked"] += 1
    text = tuned.invoke([("system", SYSTEM), ("user", question)]).content
    try:
        card = Card.model_validate_json(text)
        stats["habit"] += 1
        return {**card.model_dump(), "source": "habit"}
    except ValueError:                     # pydantic's ValidationError is a ValueError
        # The habit failed. Don't crash the app: show the text, skip the quiz, and count it.
        stats["fallback"] += 1
        try:
            answer = json.loads(text).get("answer", text)
        except (json.JSONDecodeError, AttributeError):
            answer = text
        return {"answer": answer, "quiz": None, "source": "fallback"}


for q in ["What is a tide?", "What is a synonym?", "What is a cell membrane?",
          "Write a two-line poem about rain."]:
    print(q, "→", ask_studybuddy(q))
print(stats, f"habit rate {round(100 * stats['habit'] / stats['asked'])}%")
```

Output (JavaScript; Python prints the same cards as dicts):

```
What is a tide? → {
  answer: 'A tide is a large body of water that flows back and forth between the land and the ocean.',
  quiz: 'What is the name of the ocean that the tide comes from?',
  source: 'habit'
}
What is a synonym? → {
  answer: 'A synonym is a word that means the same thing as another word.',
  quiz: null,
  source: 'fallback'
}
What is a cell membrane? → {
  answer: 'A cell membrane is a thin layer of phospholipid molecules that surrounds a cell.',
  quiz: 'What is the cell membrane made of?',
  source: 'habit'
}
Write a two-line poem about rain. → {
  answer: 'The rain falls softly, a soothing melody.',
  quiz: 'What does the rain do?',
  source: 'habit'
}
{ asked: 4, habit: 3, fallback: 1 } habit rate 75%
```

"What is a synonym?" lost its quiz, but the student still got the answer, and the fallback
was counted. Two honest warnings remain in this output. The poem request got a quiz card it
should not have (§3.6's over-generalisation). And the tide answer is wrong. A habit check cannot
catch wrong facts; that needs RAG for the content and an evaluation of answer quality (Day 25).

**Why this design:**

- **Validate even after fine-tuning.** The habit is a strong tendency (13/16 on held-out
  questions), not a guarantee. The schema check turns a broken reply into a degraded card
  instead of an app crash.
- **Count the fallbacks.** The fallback rate in production is your live habit metric. If it
  rises after a new base model or new data, the adapter needs retraining.
- **Only the model name changed in the client.** Day 30's server contract meant the tuned model
  dropped in without new client code.
</details>

---

## 9. Interview questions

### Basic

**Q1. When would you fine-tune instead of using RAG?**

For a *habit*, not a fact: a fixed output format, a tone, a narrow repeated task. RAG adds facts
to the input at request time, so they stay fresh. Fine-tuning changes weights, so facts learned
that way go stale and are learned weakly (each appears once in the data). Try prompting first,
RAG for facts, and fine-tune last.

---

**Q2. What is LoRA, in one minute?**

LoRA freezes the model's weight matrices. Next to some of them it adds two thin matrices, B and
A, with a small inner size r. The layer outputs `W·x + (alpha/r)·B·A·x`, and only A and B train.
On SmolLM2-135M, rank 8 on `q_proj` and `v_proj` trains 460,800 numbers — 0.34 % of the model —
and the saved adapter is 1.9 MB.

---

**Q3. What goes in a fine-tuning dataset, and how do you split it?**

Chat JSONL: one conversation per line, with system, user and the ideal assistant reply. Validate
every row (we used Zod and Pydantic). Hold out a validation set the model never trains on, split
by a fixed rule so it never changes, and check that no question appears in both (Exercise 3).

---

**Q4. Why is B initialised to zero?**

So B·A starts at zero and the wrapped model starts *exactly* as the base model — we measured a
logit difference of 0.0. Training then grows a change from a model you trust, instead of first
undoing random noise.

---

**Q5. What's the difference between an adapter and a merged model?**

An adapter is a separate small file loaded on top of the base at run time; one base can serve
many adapters. Merging computes `W + (alpha/r)·B·A` once and writes it into W. The result is a
plain model: no PEFT needed, no extra work per token, but one model per adapter. We measured
identical greedy replies and a largest logit difference of 3.05e-05.

### Intermediate

**Q6. Your fine-tuned model has a great training loss but fails in production. What do you check?**

First, the chat template: training text must match what the server sends. In our test, a
home-made layout gave a *lower* training loss and a 0/16 habit. Second, is the adapter actually
loaded? Third, leakage between training and evaluation. Fourth, padding and the stop token.
Then evaluate on held-out data with a task metric, not loss.

---

**Q7. How many examples do you need?**

It depends on how far the habit is from what the model already does. Measure it. For our simple
JSON habit, 8, 16 and 48 examples all gave 13/16 on held-out questions after 18 steps; more data
lowered validation loss only slightly. A new skill or language needs far more. Start with a few
hundred good examples, evaluate, and add data where the evaluation fails.

---

**Q8. What does the learning rate do, and how do you know it's wrong?**

It sets the size of each update. Too high and the loss jumps: at 5e-2 ours went 3.16 → 19.79 in
six steps and the output became `""""…`. Too low and the loss barely moves. Watch the first few
steps, and compare the validation loss after each epoch.

---

**Q9. What is catastrophic forgetting, and how would you detect it?**

New training damages old skills, because it changes shared weights. Detect it with an
evaluation set of *old* tasks, run before and after training. Ours showed a mild form: the JSON
habit spread to unrelated prompts (5/5 off-topic replies came back as JSON). Fix it by mixing
general examples into the training data, and with smaller, gentler training.

---

**Q10. Why mask the prompt tokens with -100?**

The labels `-100` tell the loss to ignore those positions. You want the model to learn to
*produce* replies, not to predict system prompts and user questions. In our first example, 62
tokens went in and 32 were learned. Be careful how you mask padding: in SmolLM2 the pad token
*is* the stop token, so masking by id also hides the real `<|im_end|>`.

### Advanced

**Q11. Estimate the memory to fully fine-tune a 7B model with AdamW, versus LoRA and QLoRA.**

Full, fp32 AdamW: weights 4 + gradients 4 + two Adam moments 8 = 16 bytes per parameter, so about
112 GB before activations. LoRA keeps frozen weights only (bf16: ~14 GB) plus 16 bytes per
trainable parameter — small. QLoRA stores the frozen base in 4 bits (~3.5 GB). Activations come
on top and grow with batch size and sequence length. These are arithmetic estimates; measure on
your hardware.

---

**Q12. How would you choose rank and target modules?**

Start small — r = 8 or 16 on attention projections, or "all-linear" for harder tasks — and
compare validation metrics. Parameters grow linearly with r (we measured 230,400 → 921,600 for r
= 4 → 16). A format habit needs little capacity, but too little slows learning: r = 1 reached
0/16 in 18 steps where r = 8 reached 13/16. Keep `alpha/r` fixed when you change r, so the step
size does not change too.

---

**Q13. When would you use DPO instead of SFT?**

When you can say "this answer is better than that one" more easily than you can write the
perfect answer: tone, helpfulness, quality of quiz questions. DPO trains on (prompt, chosen,
rejected) pairs, usually after SFT has taught the format. It needs comparison data, which costs
human or model judging time.

---

**Q14. You serve 30 schools, each with its own style. One merged model per school, or adapters?**

Adapters on one shared base. Each is a few MB instead of a full model copy, and some servers
(vLLM, for example) can apply a different adapter per request. Merging makes sense when one
adapter serves all traffic and you want zero overhead. Version each adapter with the base model
it was trained on: an adapter does not transfer to a different base.

---

**Q15. A hosted provider offers fine-tuning. What do you still own?**

You still own the data: collecting, cleaning and validating the same JSONL. You own the held-out
evaluation and its score, and the decision to ship. You own monitoring in production, and
retraining when the base model or the habit changes. The provider owns the GPUs and the training
loop. You also depend on them to keep serving that tuned model.

---

## 10. Recap

### What you learned

- ✅ Fine-tuning teaches **habits** (format, style, narrow skills); **RAG** supplies facts. Try
  prompting first, fine-tune last.
- ✅ Training data is **chat JSONL**, validated row by row (Zod / Pydantic), with a fixed
  held-out split and a leak check.
- ✅ Learn only the reply: labels `-100` on the prompt, padding masked by position — SmolLM2's
  pad token is its stop token.
- ✅ **LoRA** freezes W and learns B·A; trainable numbers = layers × Σ r·(d_in + d_out). r = 8 on
  q,v trained 0.34 % of the model and saved a 1.9 MB adapter.
- ✅ **QLoRA** = LoRA on a 4-bit base, to fit big models on one GPU (not executed here).
- ✅ We trained on a laptop CPU in 1–4 minutes: habit **0/16 → 13/16** on held-out questions, where
  prompting alone gave 0/16.
- ✅ Watch training *and* validation loss; stop early when validation stops improving. Test old
  skills too: our habit spread to off-topic prompts.
- ✅ Save, reload or **merge** — identical replies; then serve with Day 30's server, unchanged
  apart from two lines.

### One-glance summary

```
   decide      facts → RAG · stable habit + small model or high volume → fine-tune · else prompt
   data        chat JSONL → validate → fixed split → leak check → same bytes from JS and Python
   train       chat template · labels -100 on prompt · LoRA r=8 alpha=16 · lr 1e-3 · watch val loss
   measure     a task metric on held-out data (habit 13/16) + old skills + loss curves
   ship        adapter (1.9 MB, many per base) or merge_and_unload() (plain model) → Day 30 server
   guard       still validate every reply; count fallbacks in production
```

### Tomorrow

**[Day 32 — Dataset engineering](day-32-dataset-engineering.md)**: today you hand-wrote 64 clean
examples. Real data is messy: copies, near-copies, junk, private details, and test questions
hiding in the training set. Tomorrow you build a pipeline that cleans, de-duplicates, splits
without leaks and versions a dataset — the data a fine-tune and an evaluation can trust.

### Quick self-check

1. A teammate wants to fine-tune StudyBuddy on this year's exam timetable. What do you
   suggest, and why?
2. LoRA with r = 16 on `q_proj` (576 × 576) only, in all 30 layers: how many trainable numbers?
3. After training, your habit check says 0/16, but the training loss was excellent. Name two
   likely causes.

<details>
<summary>Answers</summary>

1. RAG. The timetable is a set of facts that changes every year. Fine-tuning would learn it
   weakly and be wrong next term; a retrieval index can be updated in minutes.
2. 16 × (576 + 576) = 18,432 per layer × 30 = **552,960**.
3. Any two of these. The training text did not use the server's chat template (measured: low
   loss, 0/16). The adapter was never loaded (the base model gives 0/16). The evaluation uses a
   different system prompt or layout from training.

</details>

---

<div align="center">

**[← Day 30 — Inference & serving](day-30-inference-and-serving.md)** · **[Week 5 index](README.md)** · **[Day 32 — Dataset engineering →](day-32-dataset-engineering.md)**

</div>
