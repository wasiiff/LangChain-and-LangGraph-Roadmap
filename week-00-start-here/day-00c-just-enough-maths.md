# Day 0C — Just-Enough Maths: Vectors, Probability & Softmax

> ⏱ **Time:** ~2 hours · 🎯 **Prereqs:** [Day 0B](day-00b-programming-for-ai.md) · 🧩 **Difficulty:** ●●○○○

**Today you learn:** from Day 01 on, this course says things like "cosine 0.83", "softmax",
"temperature divides the logits" and "p95 latency". If those words feel like a wall, you can
copy the code, but you can't tell when it is wrong. Today you meet each idea as a picture first,
then a worked example with small numbers, then about ten lines of plain JavaScript and Python.
You finish with a tiny maths toolkit that ranks study notes for StudyBuddy.

> 📖 **Words you'll meet today**
>
> - **Vector** — a list of numbers, like `[3, 4]`. AI turns text into vectors.
> - **Dot product** — multiply two vectors position by position, then add the results.
> - **Cosine similarity** — a score from -1 to 1 that says how much two vectors point the same way.
> - **Probability distribution** — a list of chances, one per possible outcome, that add up to 1.
> - **Softmax** — the recipe that turns any list of scores into a probability distribution.
> - **Temperature** — a number that makes a distribution sharper (low) or flatter (high).
> - **Log-probability** — the logarithm of a probability. It turns tiny numbers into usable ones.
> - **Percentile (p95)** — the value that 95 % of your measurements are at or below.

> 🧮 **No maths background needed.** You need to add, multiply, divide and use a calculator.
> Every formula on this page comes *after* a picture and a worked example. Every printed number
> is the real output of the code shown.

---

## 1. The problem

Here is the kind of log a small AI app prints. The numbers are illustrative, but the shape is
exactly what you will see from Day 01 to Day 28.

```
[retrieval]  top 3 notes      cosine 0.83   0.79   0.41
[model]      temperature 0.7  logprob(" Paris") = -0.08
[latency]    mean 2.7 s       p50 1.1 s     p95 3.1 s
[tests]      5 / 5 passed ✅   → ship it?
```

Four questions hide in those four lines:

1. Is a cosine of 0.41 bad? Is 0.83 good? Good compared with what?
2. Why is the model's "log-probability" for `" Paris"` a **negative** number?
3. The mean says 2.7 seconds and the median says 1.1 seconds. Which one is the truth?
4. Five tests passed. Is the app ready?

If you can't answer these, you can still build things. But you can't **debug** them. You won't
notice when retrieval returns the wrong note, or when a test suite is too small to mean anything.

By the end of today you will answer all four. You will also have built every tool behind those
numbers yourself, in both languages.

### The real-life version

You can drive a car without knowing how the engine works. But you must read the dashboard. You
need to know that 120 is a speed, that the fuel needle near E is a problem, and that a red
temperature light means "stop now".

Today's maths is the dashboard of an AI app. You don't need to build the engine. You need to
read the needles.

> 🔗 **Where this fits.** Day 0B taught you to write and run small programs in both languages.
> Today you use those skills to compute things. Today also leaves a gap: every score and vector
> here is made up by hand. Day 01 shows where real scores come from (a language model), and
> Day 10 shows where real vectors come from (an embedding model).

---

## 2. Mental model

All the maths in this course does one of four jobs. Text goes in as numbers. The maths
compares them, chooses between them, or summarises many runs into one honest number.

```
                    TEXT  ──►  NUMBERS  ──►  compare · choose · measure

 ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
 │ 1. VECTORS       │  │ 2. PROBABILITY   │  │ 3. LOGARITHMS    │  │ 4. STATISTICS    │
 │ lists of numbers │  │ scores → chances │  │ tiny chances →   │  │ many runs →      │
 │                  │  │ → one pick       │  │ easy sums        │  │ one honest number│
 │ dot · norm ·     │  │ softmax ·        │  │ log-probs        │  │ median · p95 ·   │
 │ cosine           │  │ temperature ·    │  │                  │  │ precision ·      │
 │                  │  │ sampling         │  │                  │  │ recall           │
 └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘
          ▼                     ▼                     ▼                     ▼
   Day 10: find the      Day 01: pick the      Day 02/04: how sure   Days 24–25: is it
   note that matches     next word             the model was         fast? is it right?
```

| Idea | In one sentence | You meet it again |
|---|---|---|
| Vector | A list of numbers that stands for a piece of text | [Day 10](../week-02-data-embeddings-and-rag/day-10-embeddings.md) (embeddings) |
| Dot product | Multiply pairs, add them up: one number for "how aligned" | Day 10, Day 11 |
| Cosine similarity | The dot product with the lengths divided out: -1 to 1 | Day 10, Day 12 |
| Matrix | A list of vectors: many dot products in one go | Day 01 (attention), Day 11 |
| Probability distribution | Chances for every outcome, adding up to 1 | [Day 01](../week-01-foundations/day-01-llms-tokens-and-inference.md) |
| Softmax | Turns any scores into a distribution | Day 01 |
| Temperature | Divides the scores before softmax | Day 01, Day 04 |
| Sampling | Picks one outcome, using the chances as odds | Day 01 |
| Log-probability | A probability on a scale where tiny numbers stay usable | Day 02, Day 04 |
| Median, p95 | The typical value, and the bad-day value | [Day 24](../week-04-production-projects-and-interviews/day-24-reliability.md), [Day 25](../week-04-production-projects-and-interviews/day-25-observability-and-evaluation.md) |
| Precision, recall | "Were my answers right?" vs "Did I find them all?" | Day 09 (recall@k), Day 25 |

---

## 3. First principles

### 3.1 A vector is a list of numbers

> 💬 **In plain words:** a vector is just a list of numbers. With two numbers you can draw it
> as an arrow on squared paper.

Take the list `[3, 4]`. Read it as "go 3 steps right, then 4 steps up". That gives an arrow:

```
  y
  4 ┤        ● (3, 4)
  3 ┤      ╱
  2 ┤    ╱      the arrow a = [3, 4]
  1 ┤  ╱
  0 ┼──┬──┬──┬──┬─ x
    0  1  2  3  4
```

That's all a vector is. An AI embedding (Day 10) is the same thing with 768 or 1,536 numbers
instead of 2. You can't draw 768 directions, and you don't need to. The arithmetic is the same.

**Length (the "norm").** How long is the arrow? It is the long side of a right-angled triangle
with sides 3 and 4. Pythagoras says: square the sides, add them, take the square root.

```
length of [3, 4]  =  √(3×3 + 4×4)  =  √(9 + 16)  =  √25  =  5
```

For any vector, the length is: square every number, add them up, take the square root. For
`[1, 2, 3]` that is `√(1 + 4 + 9) = √14 ≈ 3.742`. Day 10 calls this the **magnitude**. Same
thing, different name.

### 3.2 The dot product: multiply pairs, then add

> 💬 **In plain words:** the dot product turns two arrows into one number. It is big when they
> point the same way, zero at a right angle, and negative when they point apart.

Take two vectors of the **same length**. Multiply the first numbers together, then the second
numbers, and so on. Then add the results.

```
a = [3, 4]
b = [4, 3]

a · b  =  (3 × 4) + (4 × 3)  =  12 + 12  =  24
```

Now see what the sign tells you:

```
   b=[4,3]                    c=[-4,3]                          d=[-3,-4]
    ╱  a=[3,4]                  ╲     a                           a
   ╱ ╱                           ╲   ╱                           ╱
  ●╱                              ● ╱                           ●
                                   (right angle)               ╱
                                                              d (opposite)
  a·b = 12+12 = 24             a·c = -12+12 = 0              a·d = -9-16 = -25
  same-ish direction → big    right angle → zero             opposite → negative
```

One more useful fact: a vector's dot product **with itself** is its length squared.
`[3, 4] · [3, 4] = 9 + 16 = 25`, and `√25 = 5`. That is how the toolkit computes `norm`.

> ⚠️ **Both vectors must have the same number of entries.** `[1, 2, 3] · [1, 2]` has no
> meaning. Exercise 3 shows that naive code does not always tell you. Sometimes it quietly
> returns a wrong number.

### 3.3 Cosine similarity: direction only

> 💬 **In plain words:** cosine similarity is the dot product after removing the effect of
> length. It only asks "do these point the same way?" and answers between -1 and 1.

The dot product has a weakness. Double the length of one arrow and the dot product doubles too,
even though the direction did not change. For text, direction is what carries the meaning. A
long note about fractions and a short note about fractions should match equally well.

So divide the lengths out:

```
                 a · b             24          24
cosine(a, b) = ─────────  =  ─────────  =  ────  =  0.96
               |a| × |b|       5 × 5        25
```

| Pair | Picture | Cosine |
|---|---|---|
| `[3, 4]` and `[6, 8]` | same direction, twice as long | **1** |
| `[3, 4]` and `[4, 3]` | close directions | **0.96** |
| `[3, 4]` and `[-4, 3]` | right angle | **0** |
| `[3, 4]` and `[-3, -4]` | opposite | **-1** |

**Normalising** a vector means dividing every number by its length. The direction stays the
same and the length becomes exactly 1. `[3, 4]` becomes `[3/5, 4/5] = [0.6, 0.8]`. When both
vectors have length 1, the bottom of the cosine fraction is `1 × 1`. So **cosine equals the
plain dot product**. Day 10 builds on this fact, and you prove it on that day.

> ⚠️ **Cosine is not a percentage.** A cosine of 0.5 does not mean "50 % similar". It means
> the arrows are 60° apart. What counts as a good score depends on the embedding model. Day 10
> explains why real scores often sit in a narrow band.

### 3.4 A matrix is many dot products at once

> 💬 **In plain words:** a matrix is a table of numbers, one vector per row. Multiplying it by
> a vector just means "take the dot product with every row".

Suppose you have three documents, each turned into three numbers, and one question:

```
                 the matrix (one row per document)       query       scores
  document 0   [ 1   0   2 ]                            [ 1 ]        1+0+2 = 3
  document 1   [ 0   3   0 ]           ·                [ 0 ]   =    0+0+0 = 0
  document 2   [ 2   1   2 ]                            [ 1 ]        2+0+2 = 4
```

Three dot products, three scores. Document 2 matches best. That's retrieval in one picture.

Why give it a special name? Because computers have very fast routines for exactly this
operation. Day 01's diagram calls an LLM "a very large pile of matrix multiplications". That is
literal. Inside the model, every word in your prompt scores every other word with dot products.
Softmax (§3.7) then turns those scores into weights. This step is called **attention**, and
Day 01 explains it by intuition. You now know both of its ingredients.

### 3.5 Probability: chances that add up to 1

> 💬 **In plain words:** a probability is a number from 0 (never) to 1 (certain). A
> distribution gives one to every possible outcome, and together they add up to exactly 1.

A fair coin: heads 0.5, tails 0.5. Total 1. A fair die: each face 1/6, six faces, total 1.

A language model does the same for **the next word**. After "The capital of France is", it gives
every word in its vocabulary a chance. Here is a distribution computed by today's toolkit from
made-up scores:

```
 " Paris"     ███████████████████████████████████████████  86.9 %
 " located"   ███▌                                           7.1 %
 " the"       ██                                             4.3 %
 " Lyon"      ▊                                              1.6 %
 " banana"                                                   0.1 %
                                                    total  100.0 %
```

Two rules make a list of numbers a valid distribution: no number is negative, and they add up
to 1. If you remove some outcomes, you must **renormalise**: divide by the new total so it is 1
again. §7 shows the bug you get if you forget.

### 3.6 Sampling: rolling a weighted die

> 💬 **In plain words:** to sample is to pick one outcome at random, where likely outcomes win
> more often. A seed makes the "random" picks repeat exactly, which makes tests possible.

Lay the chances end to end along a ruler from 0 to 1. Then pick a random point on the ruler:

```
 probabilities:    A = 0.665            B = 0.245        C = 0.090
                ├────────────────────────┼──────────────┼──────┤
               0.0                     0.665          0.910   1.0

 random point u = 0.2523  → lands in A's part  → pick A
 random point u = 0.8738  → lands in B's part  → pick B
 random point u = 0.9946  → lands in C's part  → pick C
```

A has the widest part of the ruler, so A wins most often. Draw 10,000 times and the counts come
close to the chances. The toolkit's real result was **A 6,642 · B 2,436 · C 922**. The chances
were 0.665, 0.245 and 0.090.

**Where does the random point come from?** From a **random-number generator**. A computer's
generator is a formula that produces numbers that *look* random. If you start it from the same
**seed** (a starting number), it produces the same sequence every time. That is what you want in
tests: the same input should give the same output, so a failure can be repeated.

### 3.7 Softmax: from any scores to probabilities

> 💬 **In plain words:** softmax takes a list of scores, makes them all positive, and divides
> each by the total. The biggest score gets the biggest share.

A model doesn't output probabilities directly. It outputs a raw **score** for each possible next
word. These scores are called **logits**. They can be any size, and they can be negative. Softmax
fixes both problems in two steps.

**Step 1 — make every score positive.** Raise the special number *e* (about 2.718) to the power
of each score. This is written `exp(x)`. Any `exp` result is positive, and bigger scores grow
much faster.

**Step 2 — divide by the total**, so the results add up to 1.

Worked example with three scores, `[2, 1, 0]`:

```
 scores              2            1            0
 step 1: exp       7.389        2.718        1.000        total = 11.107
 step 2: ÷ total   7.389/11.107 2.718/11.107 1.000/11.107
                 = 0.665      = 0.245      = 0.090        sum = 1  ✅
```

Notice: the scores were 2, 1 and 0, evenly spaced. The probabilities are **not** evenly spaced.
The top score gets two-thirds. That is the "max" part of the name: softmax favours the
biggest score. The "soft" part: everything else still keeps some chance.

Only the **gaps** between scores matter. `[1000, 999, 998]` has the same gaps as `[2, 1, 0]`,
so it gives the same probabilities. That fact saves you from a crash in Exercise 3.

### 3.8 Temperature: divide the scores first

> 💬 **In plain words:** temperature is one division. Divide every score by the temperature,
> then run softmax. A small temperature widens the gaps (sharper); a big one shrinks them
> (flatter).

Day 01 says "temperature divides the logits before softmax". Here it is with numbers:

```
 scores [2, 1, 0]

 T = 0.5 :  [2, 1, 0] ÷ 0.5 = [4, 2, 0]    gaps doubled  → 0.867  0.117  0.016   sharper
 T = 1   :  [2, 1, 0] ÷ 1   = [2, 1, 0]    unchanged     → 0.665  0.245  0.090
 T = 2   :  [2, 1, 0] ÷ 2   = [1, 0.5, 0]  gaps halved   → 0.506  0.307  0.186   flatter
```

And on the five next-word scores from §3.5 (scores made up; percentages computed by the toolkit):

```
              Paris  located   the    Lyon   banana
 T = 0       100.0%    0.0%    0.0%   0.0%    0.0%     ← greedy: always the top word
 T = 0.7      95.7%    2.7%    1.3%   0.3%    0.0%
 T = 1        86.9%    7.1%    4.3%   1.6%    0.1%
 T = 2        59.7%   17.1%   13.3%   8.1%    1.8%     ← " banana" now has a real chance
```

**Temperature 0 needs special handling.** You cannot divide by zero. So libraries treat
`temperature = 0` as "always take the top score", which is called **greedy** decoding. Our
toolkit does the same. Exercise 3 shows what happens if you forget. (Day 01 adds an important
warning: on a real server, temperature 0 still isn't perfectly repeatable.)

### 3.9 Logarithms: turning multiplication into addition

> 💬 **In plain words:** a logarithm answers "what power do I raise *e* to, to get this
> number?" It turns tiny probabilities into ordinary negative numbers, and products into sums.

The **natural logarithm** `log(x)` is the reverse of `exp(x)`. A few values, all from the code
in §4.5:

```
 probability p      log(p)
     1               0          certain → zero
     0.92           -0.083
     0.5            -0.693
     0.01           -4.605      unlikely → a big negative number
```

The log of any probability is zero or negative, because every probability is at most 1. That
answers question 2 from §1: a log-probability of -0.08 means the model was about 92 % sure.

**Why use logs at all?** To get the probability of a whole sentence, you multiply the chance of
each word. With three words of chance 0.3, 0.5 and 0.2:

```
 multiply:  0.3 × 0.5 × 0.2                     = 0.03
 add logs:  -1.204 + (-0.693) + (-1.609)       = -3.507     and exp(-3.507) = 0.03
```

Same answer, two routes. Now try a 400-word answer where each word had a chance of 0.01. The
true product is 10 to the power -800. A computer number cannot go that small, so the product
silently becomes **0**. The log route gives **-1842.07**, a perfectly ordinary number.
That is why models and libraries report **log-probabilities** ("logprobs"), not probabilities.

### 3.10 Mean, median and percentiles

> 💬 **In plain words:** the mean is the usual average. The median is the middle value. A
> percentile like p95 is the value that 95 % of measurements are at or below. For speed, the
> median and p95 tell the truth; the mean can lie.

Here are 20 response times in seconds (made-up). Nineteen are normal. One request hit a
30-second timeout.

```
 sorted:  0.8  0.9  0.9  0.9  1.0  1.0  1.0  1.1  1.1  1.1
          1.1  1.2  1.2  1.2  1.3  1.3  1.4  2.6  3.1  30.0
                                  ▲                     ▲    ▲
                          p50 = 10th value       p95 = 19th  max
```

| Summary | Value | What it says |
|---|---|---|
| mean (add all, divide by 20) | **2.71 s** | "Typical requests take 2.7 s" — **false**: 17 of 20 took under 2 s |
| median = p50 | **1.1 s** | Half the requests were this fast or faster |
| p95 | **3.1 s** | 19 of 20 requests were this fast or faster |
| max | **30 s** | Your worst user waited this long |

One slow outlier dragged the mean up to more than twice the typical value. That answers question
3 from §1. This is why Day 24 and Day 25 track **p50 and p95 latency**, never the mean alone.

**How to compute a percentile (nearest-rank method).** Sort the values. For the p-th percentile
of n values, take position `p × n ÷ 100`, rounded **up**. For p95 of 20 values: `95 × 20 ÷ 100 =
19`, so take the 19th value. Other tools use slightly different methods. §6.5 shows a real case
where two methods disagree.

### 3.11 Accuracy, precision and recall

> 💬 **In plain words:** accuracy is "how often was I right?". Precision is "when I said yes,
> how often was I right?". Recall is "of all the real yeses, how many did I find?".

StudyBuddy has a **router** that decides "is this a maths question?". You test it on ten
questions. Four really are maths. Here is what happened:

```
                         router said "maths"   router said "not maths"
 really maths  (4)        3  ✅ hit              1  ❌ missed
 not maths     (6)        2  ❌ false alarm      4  ✅ correct
```

| Measure | Question it answers | Sum | Value |
|---|---|---|---|
| **accuracy** | How often was the router right? | (3 + 4) ÷ 10 | **0.70** |
| **precision** | When it said "maths", how often was it right? | 3 ÷ (3 + 2) | **0.60** |
| **recall** | Of the 4 real maths questions, how many did it find? | 3 ÷ (3 + 1) | **0.75** |

Which one matters depends on the cost of each mistake. A spam filter needs **high precision**,
because a real email in the spam folder is costly. A search for safety problems needs **high
recall**, because a missed problem is costly. For retrieval, Day 09 measures **recall@k**: did
the right chunk appear in the top *k* results?

### 3.12 Why five tests are not enough

> 💬 **In plain words:** a small test suite is a small sample. Luck can make a weak system pass
> every test. More tests shrink the role of luck.

Imagine a bot that is truly right 80 % of the time. You run 5 test cases. How often will all 5
pass? You can multiply: `0.8 × 0.8 × 0.8 × 0.8 × 0.8 = 0.328`. So about **one run in three**
shows a perfect 5 / 5, even though one answer in five is wrong.

It gets worse. Exercise 4 simulates many test runs with a fixed seed. These are the real results
from 10,000 simulated test runs per row:

| Suite size | True accuracy | Middle 90 % of scores (p5 – p95) | Runs where every test passed |
|---|---|---|---|
| 5 tests | 0.8 | 0.40 – 1.00 | 32.7 % |
| 5 tests | 0.6 | 0.20 – 1.00 | 8.2 % |
| 100 tests | 0.8 | 0.73 – 0.86 | 0.0 % |
| 100 tests | 0.6 | 0.52 – 0.68 | 0.0 % |

Read the first two rows. With 5 tests, a 60 % bot and an 80 % bot overlap almost completely. You
can't tell them apart. With 100 tests, their score ranges no longer overlap. That answers
question 4 from §1: 5 / 5 is a good sign, not proof. Day 25 builds real evaluation datasets.

---

## 4. Code — JavaScript

You will build one file, `toolkit.mjs`, a piece at a time. Each piece comes with a short `try-…`
file that uses it. No packages to install: everything here is plain Node.

```
maths-toolkit/
├── toolkit.mjs        ← grows through §4.1–§4.6
├── try-vectors.mjs
├── try-cosine.mjs
├── try-softmax.mjs
├── try-sampling.mjs
├── try-logs.mjs
└── try-stats.mjs
```

> 📦 **Why `.mjs`?** The `.mjs` ending tells Node the file uses `import` and `export`, with no
> `package.json` needed. Every snippet below was run with Node 24.15 on Windows 11.

### 4.1 Vectors: `dot` and `norm`

Create `toolkit.mjs` with the first two tools:

```js
// toolkit.mjs — a tiny maths toolkit, built up during Day 0C.

// ── vectors ─────────────────────────────────────────────────────────────────
// dot product: multiply matching positions, then add everything up.
export function dot(a, b) {
  if (a.length !== b.length) {
    throw new Error(`dot: lengths differ (${a.length} vs ${b.length})`);
  }
  let total = 0;
  for (let i = 0; i < a.length; i++) {
    total += a[i] * b[i];
  }
  return total;
}

// norm (length): the square root of a vector's dot product with itself.
export function norm(a) {
  return Math.sqrt(dot(a, a));
}
```

The length check is the most important line. Without it, a mistake gives a silently wrong
number (Exercise 3, item 4). Now try it:

```js
// try-vectors.mjs — run with: node try-vectors.mjs
import { dot, norm } from "./toolkit.mjs";

const a = [3, 4];
const b = [4, 3];

console.log("norm(a)   =", norm(a));    // the 3-4-5 triangle
console.log("dot(a, b) =", dot(a, b));  // 3×4 + 4×3
console.log("dot(a, a) =", dot(a, a));  // a vector with itself = length squared

try {
  dot([1, 2, 3], [1, 2]);
} catch (err) {
  console.log("mismatch  →", err.message);
}
```

Expected output:

```
norm(a)   = 5
dot(a, b) = 24
dot(a, a) = 25
mismatch  → dot: lengths differ (3 vs 2)
```

### 4.2 `cosine`, `normalise`, and many dot products at once

Add these two functions to the end of `toolkit.mjs`:

```js
// cosine similarity: the dot product with both lengths divided out.
// Result is between -1 (opposite) and 1 (same direction).
export function cosine(a, b) {
  const lengths = norm(a) * norm(b);
  if (lengths === 0) {
    throw new Error("cosine: a vector of all zeros has no direction");
  }
  return dot(a, b) / lengths;
}

// normalise: same direction, length exactly 1.
export function normalise(a) {
  const n = norm(a);
  if (n === 0) {
    throw new Error("normalise: a vector of all zeros has no direction");
  }
  return a.map((x) => x / n);
}
```

```js
// try-cosine.mjs — run with: node try-cosine.mjs
import { dot, norm, cosine, normalise } from "./toolkit.mjs";

const a = [3, 4];
console.log("cosine(a, [4, 3])   =", cosine(a, [4, 3]));    // close directions
console.log("cosine(a, [6, 8])   =", cosine(a, [6, 8]));    // same direction, twice as long
console.log("cosine(a, [-4, 3])  =", cosine(a, [-4, 3]));   // a right angle
console.log("cosine(a, [-3, -4]) =", cosine(a, [-3, -4]));  // exactly opposite

const unit = normalise(a);
console.log("normalise(a) =", unit, "  length:", norm(unit));

// A "matrix" is a list of vectors. Many dot products at once = one per row.
const docs = [
  [1, 0, 2],
  [0, 3, 0],
  [2, 1, 2],
];
const query = [1, 0, 1];
console.log("scores =", docs.map((row) => dot(row, query)));
```

Expected output:

```
cosine(a, [4, 3])   = 0.96
cosine(a, [6, 8])   = 1
cosine(a, [-4, 3])  = 0
cosine(a, [-3, -4]) = -1
normalise(a) = [ 0.6, 0.8 ]   length: 1
scores = [ 3, 0, 4 ]
```

These match the hand-worked numbers in §3.2–§3.4 exactly. The last line is the matrix picture
from §3.4: one `.map` over the rows gives one score per document.

### 4.3 `softmax` with temperature

Add the probability section to `toolkit.mjs`:

```js
// ── probabilities ───────────────────────────────────────────────────────────
// softmax: turn any list of scores (logits) into probabilities that add up to 1.
// temperature divides the scores first: below 1 sharpens, above 1 flattens.
export function softmax(logits, temperature = 1) {
  if (temperature < 0) {
    throw new Error("softmax: temperature cannot be negative");
  }
  if (temperature === 0) {
    // We cannot divide by zero, so treat 0 as "always pick the top score" (greedy).
    const best = logits.indexOf(Math.max(...logits));
    return logits.map((_, i) => (i === best ? 1 : 0));
  }
  const scaled = logits.map((x) => x / temperature);
  const biggest = Math.max(...scaled);
  // Subtracting the biggest score keeps Math.exp small. The result does not change (see §6).
  const powers = scaled.map((x) => Math.exp(x - biggest));
  const total = powers.reduce((sum, x) => sum + x, 0);
  return powers.map((x) => x / total);
}
```

Two lines deserve a second look. `x - biggest` makes the biggest score 0 before `Math.exp`.
§3.7 said only the gaps matter, so this changes nothing — except that huge scores no longer
overflow (§6.2). And the `temperature === 0` branch is the greedy rule from §3.8.

```js
// try-softmax.mjs — run with: node try-softmax.mjs
import { softmax } from "./toolkit.mjs";

const show = (probs) => probs.map((p) => p.toFixed(3)).join("  ");

// The hand-worked example from §3.7
const probs = softmax([2, 1, 0]);
console.log("softmax([2, 1, 0]) =", show(probs));
console.log("adds up to         =", probs.reduce((s, p) => s + p, 0));

// Made-up scores for the next word after "The capital of France is"
const words = [" Paris", " located", " the", " Lyon", " banana"];
const logits = [5.0, 2.5, 2.0, 1.0, -2.0];

console.log("\n            " + words.map((w) => w.padStart(9)).join(""));
for (const t of [0, 0.7, 1, 2]) {
  const row = softmax(logits, t).map((p) => (p * 100).toFixed(1).padStart(8) + "%");
  console.log(`T = ${String(t).padEnd(4)}  ${row.join("")}`);
}
```

Expected output:

```
softmax([2, 1, 0]) = 0.665  0.245  0.090
adds up to         = 0.9999999999999999

                Paris  located      the     Lyon   banana
T = 0        100.0%     0.0%     0.0%     0.0%     0.0%
T = 0.7       95.7%     2.7%     1.3%     0.3%     0.0%
T = 1         86.9%     7.1%     4.3%     1.6%     0.1%
T = 2         59.7%    17.1%    13.3%     8.1%     1.8%
```

Look at the second line: **0.9999999999999999**, not 1. That is not a bug in softmax. Computers
store most decimals slightly inexactly, and §6.1 explains it. Never test `sum === 1`; test
"close to 1".

### 4.4 Seeded randomness: `makeRng` and `sample`

JavaScript's `Math.random()` cannot be given a seed, so every run differs. For repeatable tests
we write our own tiny generator. It is about five lines, and §6.3 explains the formula.

```js
// makeRng: a tiny seeded random-number generator (a "linear congruential generator").
// Same seed → same numbers, every run, in JavaScript AND in Python. Not for passwords!
export function makeRng(seed) {
  let state = seed % 4294967296; // 4294967296 = 2 to the power 32
  return function next() {
    state = (state * 1664525 + 1013904223) % 4294967296;
    return state / 4294967296; // a number from 0 up to (not including) 1
  };
}

// sample: pick one index, using the probabilities as the odds.
export function sample(probs, rng) {
  const u = rng();
  let running = 0;
  for (let i = 0; i < probs.length; i++) {
    running += probs[i];
    if (u < running) return i;
  }
  return probs.length - 1; // safety net: rounding can leave the total at 0.9999999
}
```

`sample` is the ruler from §3.6 in code. `running` walks along the ruler, part by part, until it
passes the random point `u`.

```js
// try-sampling.mjs — run with: node try-sampling.mjs
import { softmax, makeRng, sample } from "./toolkit.mjs";

const rng = makeRng(42);
console.log("first 3 random numbers:", [rng(), rng(), rng()].map((u) => u.toFixed(4)));

const words = ["A", "B", "C"];
const probs = softmax([2, 1, 0]); // 0.665, 0.245, 0.090

// Ten draws, with a fresh generator so the run is repeatable
const rng10 = makeRng(42);
const ten = [];
for (let i = 0; i < 10; i++) ten.push(words[sample(probs, rng10)]);
console.log("10 draws:", ten.join(" "));

// Ten thousand draws: the counts settle close to the probabilities
const rngBig = makeRng(7);
const counts = { A: 0, B: 0, C: 0 };
for (let i = 0; i < 10000; i++) counts[words[sample(probs, rngBig)]]++;
console.log("10,000 draws:", counts);
```

Expected output (identical on every run, and identical to the Python version in §5.4):

```
first 3 random numbers: [ '0.2523', '0.0881', '0.5773' ]
10 draws: A A A A A A A A B C
10,000 draws: { A: 6642, B: 2436, C: 922 }
```

Ten draws look streaky: eight A's in a row. Small samples are noisy. Ten thousand draws land
within about 1 % of the true chances. Keep that in mind for §3.12.

### 4.5 Logarithms and log-probabilities

No new toolkit function here. `Math.log` and `Math.exp` are built in.

```js
// try-logs.mjs — run with: node try-logs.mjs
// Math.log is the natural logarithm ("ln"): Math.log(Math.E) === 1.

console.log("log(1)    =", Math.log(1));               // certain → 0
console.log("log(0.5)  =", Math.log(0.5).toFixed(4));
console.log("log(0.01) =", Math.log(0.01).toFixed(4));
console.log("exp(log(0.92)) =", Math.exp(Math.log(0.92))); // exp undoes log

// A 400-token answer where every token had probability 0.01
let product = 1;
let logSum = 0;
for (let i = 0; i < 400; i++) {
  product *= 0.01;
  logSum += Math.log(0.01);
}
console.log("\nmultiply 400 probabilities:", product);          // underflows
console.log("add 400 log-probabilities:  ", logSum.toFixed(2)); // still fine

// The smallest positive number a JS number can hold
console.log("smallest number =", Number.MIN_VALUE, " half of it =", Number.MIN_VALUE / 2);
```

Expected output:

```
log(1)    = 0
log(0.5)  = -0.6931
log(0.01) = -4.6052
exp(log(0.92)) = 0.92

multiply 400 probabilities: 0
add 400 log-probabilities:   -1842.07
smallest number = 5e-324  half of it = 0
```

The last line shows the floor. Below about 5 × 10⁻³²⁴, a number simply becomes 0. The product
of 400 small probabilities fell through that floor. The sum of logs never came close to it.

### 4.6 Statistics: `mean` and `percentile`

Add the last section to `toolkit.mjs`:

```js
// ── statistics ──────────────────────────────────────────────────────────────
export function mean(xs) {
  if (xs.length === 0) throw new Error("mean: empty list");
  return xs.reduce((sum, x) => sum + x, 0) / xs.length;
}

// percentile (nearest-rank method): the value that p% of the measurements are at or below.
export function percentile(xs, p) {
  if (xs.length === 0) throw new Error("percentile: empty list");
  const sorted = [...xs].sort((a, b) => a - b); // numeric sort — plain .sort() sorts as text!
  const rank = Math.ceil((p * sorted.length) / 100); // 1-based position in the sorted list
  return sorted[Math.max(rank, 1) - 1];
}
```

> ⚠️ **The `(a, b) => a - b` is not optional.** JavaScript's plain `.sort()` compares items as
> **text**, so `[10, 9, 100, 25].sort()` gives `[10, 100, 25, 9]`. Exercise 3 shows the wrong
> percentile you get.

`[...xs]` copies the list first, so the caller's data keeps its original order. And
`p * sorted.length` is multiplied before dividing by 100, which keeps the rank a whole number.

```js
// try-stats.mjs — run with: node try-stats.mjs
import { mean, percentile } from "./toolkit.mjs";

// 20 response times in seconds (made-up numbers). One request hit a 30-second timeout.
const latencies = [
  1.1, 0.9, 1.3, 1.0, 1.2, 0.8, 1.4, 1.1, 1.0, 2.6,
  1.2, 0.9, 1.1, 1.3, 3.1, 1.0, 1.2, 0.9, 1.1, 30.0,
];

console.log("mean =", mean(latencies).toFixed(2), "s");
console.log("p50  =", percentile(latencies, 50), "s   (the median)");
console.log("p95  =", percentile(latencies, 95), "s");
console.log("p100 =", percentile(latencies, 100), "s  (the maximum)");
```

Expected output:

```
mean = 2.71 s
p50  = 1.1 s   (the median)
p95  = 3.1 s
p100 = 30 s  (the maximum)
```

Your toolkit is complete: `dot`, `norm`, `cosine`, `normalise`, `softmax`, `makeRng`, `sample`,
`mean` and `percentile`. That's about 90 lines, and every exercise below imports from it.

> 💡 **"p50 is the median" — almost.** With an even number of values, a textbook median
> averages the two middle values. Nearest-rank p50 takes the lower one. Here both middle values
> are 1.1, so they agree.

---

## 5. Code — Python

The same toolkit, the same examples, the same outputs. No packages: only `math`, which ships with
Python. Every snippet was run with Python 3.14.4 on Windows 11.

```
maths-toolkit/
├── toolkit.py         ← grows through §5.1–§5.6
├── try_vectors.py
├── try_cosine.py
├── try_softmax.py
├── try_sampling.py
├── try_logs.py
└── try_stats.py
```

> 🪟 **Windows:** some `try_…` files print an arrow (`→`). In Git Bash on Windows, that line
> crashed with `UnicodeEncodeError: 'charmap' codec can't encode character '→'`. The fix
> is to tell Python to print UTF-8 before you run it: `export PYTHONIOENCODING=utf-8` in Git
> Bash, or `$env:PYTHONIOENCODING = "utf-8"` in PowerShell.

### 5.1 Vectors: `dot` and `norm`

```python
# toolkit.py — a tiny maths toolkit, built up during Day 0C.
import math


# ── vectors ─────────────────────────────────────────────────────────────────
def dot(a, b):
    """Dot product: multiply matching positions, then add everything up."""
    if len(a) != len(b):
        raise ValueError(f"dot: lengths differ ({len(a)} vs {len(b)})")
    total = 0
    for i in range(len(a)):
        total += a[i] * b[i]
    return total


def norm(a):
    """Norm (length): the square root of a vector's dot product with itself."""
    return math.sqrt(dot(a, a))
```

```python
# try_vectors.py — run with: python try_vectors.py
from toolkit import dot, norm

a = [3, 4]
b = [4, 3]

print("norm(a)   =", norm(a))    # the 3-4-5 triangle
print("dot(a, b) =", dot(a, b))  # 3×4 + 4×3
print("dot(a, a) =", dot(a, a))  # a vector with itself = length squared

try:
    dot([1, 2, 3], [1, 2])
except ValueError as err:
    print("mismatch  →", err)
```

Expected output:

```
norm(a)   = 5.0
dot(a, b) = 24
dot(a, a) = 25
mismatch  → dot: lengths differ (3 vs 2)
```

One small difference from JavaScript: `norm(a)` prints `5.0`, not `5`. Python keeps whole
numbers (`int`) and decimals (`float`) as separate types, and `math.sqrt` always returns a
`float`. JavaScript has one number type, so it prints `5`.

### 5.2 `cosine`, `normalise`, and many dot products at once

Add to the end of `toolkit.py`:

```python
def cosine(a, b):
    """Cosine similarity: the dot product with both lengths divided out (-1 to 1)."""
    lengths = norm(a) * norm(b)
    if lengths == 0:
        raise ValueError("cosine: a vector of all zeros has no direction")
    return dot(a, b) / lengths


def normalise(a):
    """Same direction, length exactly 1."""
    n = norm(a)
    if n == 0:
        raise ValueError("normalise: a vector of all zeros has no direction")
    return [x / n for x in a]
```

```python
# try_cosine.py — run with: python try_cosine.py
from toolkit import dot, norm, cosine, normalise

a = [3, 4]
print("cosine(a, [4, 3])   =", cosine(a, [4, 3]))    # close directions
print("cosine(a, [6, 8])   =", cosine(a, [6, 8]))    # same direction, twice as long
print("cosine(a, [-4, 3])  =", cosine(a, [-4, 3]))   # a right angle
print("cosine(a, [-3, -4]) =", cosine(a, [-3, -4]))  # exactly opposite

unit = normalise(a)
print("normalise(a) =", unit, "  length:", norm(unit))

# A "matrix" is a list of vectors. Many dot products at once = one per row.
docs = [
    [1, 0, 2],
    [0, 3, 0],
    [2, 1, 2],
]
query = [1, 0, 1]
print("scores =", [dot(row, query) for row in docs])
```

Expected output:

```
cosine(a, [4, 3])   = 0.96
cosine(a, [6, 8])   = 1.0
cosine(a, [-4, 3])  = 0.0
cosine(a, [-3, -4]) = -1.0
normalise(a) = [0.6, 0.8]   length: 1.0
scores = [3, 0, 4]
```

### 5.3 `softmax` with temperature

```python
# ── probabilities ───────────────────────────────────────────────────────────
def softmax(logits, temperature=1.0):
    """Turn any list of scores (logits) into probabilities that add up to 1.
    temperature divides the scores first: below 1 sharpens, above 1 flattens."""
    if temperature < 0:
        raise ValueError("softmax: temperature cannot be negative")
    if temperature == 0:
        # We cannot divide by zero, so treat 0 as "always pick the top score" (greedy).
        best = logits.index(max(logits))
        return [1.0 if i == best else 0.0 for i in range(len(logits))]
    scaled = [x / temperature for x in logits]
    biggest = max(scaled)
    # Subtracting the biggest score keeps math.exp small. The result does not change (see §6).
    powers = [math.exp(x - biggest) for x in scaled]
    total = sum(powers)
    return [x / total for x in powers]
```

```python
# try_softmax.py — run with: python try_softmax.py
from toolkit import softmax


def show(probs):
    return "  ".join(f"{p:.3f}" for p in probs)


# The hand-worked example from §3.7
probs = softmax([2, 1, 0])
print("softmax([2, 1, 0]) =", show(probs))
print("adds up to         =", sum(probs))

# Made-up scores for the next word after "The capital of France is"
words = [" Paris", " located", " the", " Lyon", " banana"]
logits = [5.0, 2.5, 2.0, 1.0, -2.0]

print("\n            " + "".join(w.rjust(9) for w in words))
for t in [0, 0.7, 1, 2]:
    row = "".join(f"{p * 100:8.1f}%" for p in softmax(logits, t))
    print(f"T = {str(t):<4}  {row}")
```

Expected output — the same as JavaScript, digit for digit:

```
softmax([2, 1, 0]) = 0.665  0.245  0.090
adds up to         = 0.9999999999999999

                Paris  located      the     Lyon   banana
T = 0        100.0%     0.0%     0.0%     0.0%     0.0%
T = 0.7       95.7%     2.7%     1.3%     0.3%     0.0%
T = 1         86.9%     7.1%     4.3%     1.6%     0.1%
T = 2         59.7%    17.1%    13.3%     8.1%     1.8%
```

### 5.4 Seeded randomness: `make_rng` and `sample`

Python has a seedable generator built in (`random.Random(42)`), and in normal Python code you
should use it. Here we write the same formula as JavaScript instead, so both languages produce
**the same** random numbers. §6.3 explains why the built-in ones differ.

```python
def make_rng(seed):
    """A tiny seeded random-number generator (a "linear congruential generator").
    Same seed -> same numbers, every run, in Python AND in JavaScript. Not for passwords!"""
    state = seed % 4294967296  # 4294967296 = 2 to the power 32

    def next_number():
        nonlocal state  # "nonlocal" lets this inner function update the outer `state`
        state = (state * 1664525 + 1013904223) % 4294967296
        return state / 4294967296  # a number from 0 up to (not including) 1

    return next_number


def sample(probs, rng):
    """Pick one index, using the probabilities as the odds."""
    u = rng()
    running = 0.0
    for i, p in enumerate(probs):
        running += p
        if u < running:
            return i
    return len(probs) - 1  # safety net: rounding can leave the total at 0.9999999
```

```python
# try_sampling.py — run with: python try_sampling.py
from toolkit import softmax, make_rng, sample

rng = make_rng(42)
print("first 3 random numbers:", [f"{rng():.4f}" for _ in range(3)])

words = ["A", "B", "C"]
probs = softmax([2, 1, 0])  # 0.665, 0.245, 0.090

# Ten draws, with a fresh generator so the run is repeatable
rng10 = make_rng(42)
ten = [words[sample(probs, rng10)] for _ in range(10)]
print("10 draws:", " ".join(ten))

# Ten thousand draws: the counts settle close to the probabilities
rng_big = make_rng(7)
counts = {"A": 0, "B": 0, "C": 0}
for _ in range(10_000):
    counts[words[sample(probs, rng_big)]] += 1
print("10,000 draws:", counts)
```

Expected output — the same draws as JavaScript:

```
first 3 random numbers: ['0.2523', '0.0881', '0.5773']
10 draws: A A A A A A A A B C
10,000 draws: {'A': 6642, 'B': 2436, 'C': 922}
```

### 5.5 Logarithms and log-probabilities

```python
# try_logs.py — run with: python try_logs.py
# math.log is the natural logarithm ("ln"): math.log(math.e) == 1.
import math

print("log(1)    =", math.log(1))               # certain → 0
print(f"log(0.5)  = {math.log(0.5):.4f}")
print(f"log(0.01) = {math.log(0.01):.4f}")
print("exp(log(0.92)) =", math.exp(math.log(0.92)))  # exp undoes log

# A 400-token answer where every token had probability 0.01
product = 1.0
log_sum = 0.0
for _ in range(400):
    product *= 0.01
    log_sum += math.log(0.01)
print("\nmultiply 400 probabilities:", product)        # underflows
print(f"add 400 log-probabilities:   {log_sum:.2f}")  # still fine

# The smallest positive number a Python float can hold
print("smallest float =", 5e-324, " half of it =", 5e-324 / 2)
```

Expected output:

```
log(1)    = 0.0
log(0.5)  = -0.6931
log(0.01) = -4.6052
exp(log(0.92)) = 0.92

multiply 400 probabilities: 0.0
add 400 log-probabilities:   -1842.07
smallest float = 5e-324  half of it = 0.0
```

### 5.6 Statistics: `mean` and `percentile`

```python
# ── statistics ──────────────────────────────────────────────────────────────
def mean(xs):
    if len(xs) == 0:
        raise ValueError("mean: empty list")
    return sum(xs) / len(xs)


def percentile(xs, p):
    """Nearest-rank method: the value that p% of the measurements are at or below."""
    if len(xs) == 0:
        raise ValueError("percentile: empty list")
    ordered = sorted(xs)  # Python sorts numbers as numbers — no trap here
    rank = math.ceil(p * len(ordered) / 100)  # 1-based position in the sorted list
    return ordered[max(rank, 1) - 1]
```

```python
# try_stats.py — run with: python try_stats.py
from toolkit import mean, percentile

# 20 response times in seconds (made-up numbers). One request hit a 30-second timeout.
latencies = [
    1.1, 0.9, 1.3, 1.0, 1.2, 0.8, 1.4, 1.1, 1.0, 2.6,
    1.2, 0.9, 1.1, 1.3, 3.1, 1.0, 1.2, 0.9, 1.1, 30.0,
]

print(f"mean = {mean(latencies):.2f} s")
print("p50  =", percentile(latencies, 50), "s   (the median)")
print("p95  =", percentile(latencies, 95), "s")
print("p100 =", percentile(latencies, 100), "s  (the maximum)")
```

Expected output:

```
mean = 2.71 s
p50  = 1.1 s   (the median)
p95  = 3.1 s
p100 = 30.0 s  (the maximum)
```

> 💡 **The numpy shortcut.** Real Python projects use **numpy**, a fast maths library
> (`pip install numpy`). Checked with numpy 2.4.4: `np.dot([3, 4], [4, 3])` gives `24` and
> `np.linalg.norm([3, 4])` gives `5.0`. Its `np.percentile` uses a *different* method by
> default, though — see §6.5. Write the plain version once, today, so you know what numpy does.

### 5.7 The JS ↔ Python translation for today

| Concept | JavaScript | Python |
|---|---|---|
| file / import | `toolkit.mjs` · `import { dot } from "./toolkit.mjs"` | `toolkit.py` · `from toolkit import dot` |
| square root, e^x, natural log | `Math.sqrt` · `Math.exp` · `Math.log` | `math.sqrt` · `math.exp` · `math.log` |
| biggest value | `Math.max(...xs)` | `max(xs)` |
| add up a list | `xs.reduce((s, x) => s + x, 0)` | `sum(xs)` |
| transform every item | `xs.map((x) => x / n)` | `[x / n for x in xs]` |
| round up | `Math.ceil` | `math.ceil` |
| sort numbers | `[...xs].sort((a, b) => a - b)` — **comparator required** | `sorted(xs)` — numeric by default |
| whole number vs decimal | one `number` type: prints `5` | `int` and `float`: `math.sqrt` prints `5.0` |
| raise an error | `throw new Error("…")` | `raise ValueError("…")` |
| divide by zero | `1 / 0` → `Infinity`, `0 / 0` → `NaN` (no error) | `ZeroDivisionError` |
| `exp` of a huge number | `Math.exp(710)` → `Infinity` | `math.exp(710)` → `OverflowError: math range error` |
| seeded random | none built in — write `makeRng` | `random.Random(seed)` (different numbers from JS) |
| state inside a closure | `let state` in the outer function | `nonlocal state` in the inner function |
| fast vector maths | (plain loops are fast enough here) | numpy: `D @ q`, `np.dot`, `np.linalg.norm` |

---

## 6. Under the hood

### 6.1 Why the computer says 0.9999999999999999

Computers store numbers in binary. Most decimals, like 0.1, have no exact binary form, just as
1/3 has no exact decimal form (0.333…). So each one is stored as the nearest value that fits.
The tiny errors are usually invisible, but sometimes they show:

```
 0.1 + 0.2            → 0.30000000000000004    (both languages)
 0.1 + 0.2 === 0.3    → false
 softmax([2,1,0]) sum → 0.9999999999999999     (both languages)
 cosine([1,0,1], [0,1,1]) → 0.4999999999999999 (true answer: exactly 0.5)
```

The fix is never "make the computer exact". It is **compare with a tolerance**:
`Math.abs(x - 0.3) < 1e-9` in JavaScript, `math.isclose(x, 0.3)` in Python. Both give `true` /
`True` for `0.1 + 0.2` (checked).

Two more things the runs showed. First, Python's `sum()` adds more carefully than a plain loop:
`sum([0.1] * 10)` gave `1.0`, while adding 0.1 ten times in a loop gave `0.9999999999999999`
(Python 3.14.4). Second, the last digit can differ between languages. One sum in this lesson
printed `0.9011844162218702` in Node and `0.9011844162218705` in Python. Round before you compare
outputs across languages.

### 6.2 Why subtracting the biggest score is safe — and necessary

`exp` grows very fast. A number in either language can hold up to about 1.8 × 10³⁰⁸. In the
runs, `exp(709)` gave `8.218407461554972e+307`, but `exp(710)` was too big. JavaScript returned
`Infinity` and Python raised `OverflowError: math range error`. Model scores can be large, and
temperature 0.1 multiplies them by 10. So naive softmax really can overflow.

Now the trick. Take scores `[1000, 999, 998]` and subtract the biggest (1000):

```
 [1000, 999, 998]  −1000  →  [0, -1, -2]
 exp:                         1.000   0.368   0.135     total 1.503
 ÷ total:                     0.665   0.245   0.090
```

Same answer as `[2, 1, 0]` in §3.7, because the gaps are the same. Why does it work? Subtracting
a number from every score divides every `exp` result by the same amount. That amount appears
on the top and the bottom of the fraction, so it cancels. And after subtracting, the biggest
score is 0, so the biggest `exp` is exactly 1. Overflow is impossible.

### 6.3 How the seeded generator works

The whole generator is one line, repeated:

```
 next state = (state × 1664525 + 1013904223)  remainder after dividing by 2³²
 random number = state ÷ 2³²                   → always from 0 up to (not including) 1
```

This is a **linear congruential generator**, one of the oldest designs. It is fine for
simulations and tests. It is **not** safe for passwords or security tokens. Its output is easy
to predict, which is the point of a seed but the opposite of what security needs.

Why does it give *identical* numbers in JavaScript and Python? JavaScript numbers hold whole
numbers exactly only up to 2⁵³ (9,007,199,254,740,992). The biggest value this formula ever
reaches is 7,149,081,450,614,098, which is below that limit. So both languages do exact
whole-number arithmetic and agree on every digit.

Python's built-in `random.Random(42)` uses a different, stronger algorithm (the Mersenne
Twister). Its first number is `0.6394267984578837` (checked). That is fine inside Python, but it
will never match a JavaScript program. Use the built-in in real Python code. Use a shared
formula only when two languages must agree, as they must in this book.

### 6.4 How fast is this? (measured)

Real retrieval compares one query against thousands of documents. Each comparison is a dot
product of hundreds of numbers. Here is the toolkit's `dot` on 10,000 random vectors of 768
numbers each, measured on this machine (Windows 11, Node 24.15, Python 3.14.4, numpy 2.4.4):

| Version | Time for 10,000 dot products (best of 3 runs, two sessions) |
|---|---|
| JavaScript, plain loop | 23.6 – 24.2 ms |
| Python, plain loop | 1,460 – 1,478 ms |
| Python, numpy `D @ q` | 3.8 – 4.9 ms |

Plain Python loops are slow, about 60 times slower than the same loop in Node here. numpy hands
the whole matrix to compiled code, and it was fastest of all. Your numbers will differ by
machine; the ranking is the lesson. This is why Python AI code uses numpy, and why vector
databases (Day 11) exist at all.

### 6.5 Percentiles: there is more than one recipe

There are several standard ways to compute a percentile, and they disagree on small samples. On
the 20 latencies from §3.10:

| Method | p95 |
|---|---|
| Our toolkit (nearest-rank) | **3.1** |
| `np.percentile(lat, 95)` (numpy's default: draws a line between neighbours) | **4.445000000000019** |
| `np.percentile(lat, 95, method="inverted_cdf")` | **3.1** |

Neither answer is wrong; they are different definitions. The rule for real work: when you compare
p95 numbers, make sure they came from the same tool and method. A dashboard switch can "improve"
your p95 without one request getting faster.

---

## 7. Common mistakes

### ❌ 1. Reporting the mean latency

```js
// ❌ one number that describes nobody
console.log("avg latency:", mean(latencies).toFixed(2), "s");        // avg latency: 2.71 s

// ✅ the typical user and the unlucky user
console.log("p50:", percentile(latencies, 50), "s  p95:", percentile(latencies, 95), "s");
// p50: 1.1 s  p95: 3.1 s
```

**Symptom:** the dashboard says 2.7 s. In the data from §3.10, 17 of 20 users waited under 2 s
and one waited 30 s. Nobody waited 2.7 s. A single slow request moves the mean a lot and the
median not at all. Report p50 and p95 (and p99 when you have enough data), as Day 24 does.

### ❌ 2. Multiplying many probabilities

```python
# ❌ the product falls through the floor of what a float can hold
product = 1.0
for p in [0.01] * 400:
    product *= p
print(product)   # 0.0

# ✅ add log-probabilities instead
import math
print(sum(math.log(p) for p in [0.01] * 400))   # -1842.0680743952364
```

**Symptom:** every long answer gets a probability of exactly 0, so you can't compare them. There
is no error message. Work in logs and convert back with `exp` only when the number is small
enough to hold.

### ❌ 3. Removing options without renormalising

This bug hides in hand-written top-p filters. You drop the unlikely words, but forget to make
the rest add up to 1 again.

```js
// ❌ drop " Lyon" and " banana" (indexes 3 and 4) but forget to renormalise
const hot = softmax([5.0, 2.5, 2.0, 1.0, -2.0], 2);
const cut = hot.map((q, i) => (i < 3 ? q : 0));
const rng = makeRng(3);
const counts = [0, 0, 0, 0, 0];
for (let i = 0; i < 10000; i++) counts[sample(cut, rng)]++;
console.log("sum after cut:", cut.reduce((s, q) => s + q, 0)); // 0.9011844162218702
console.log("counts:", counts);                                 // [ 6063, 1730, 1269, 0, 938 ]
```

```python
# ❌ the same bug in Python
hot = softmax([5.0, 2.5, 2.0, 1.0, -2.0], 2)
cut = [q if i < 3 else 0.0 for i, q in enumerate(hot)]
rng = make_rng(3)
counts = [0] * 5
for _ in range(10_000):
    counts[sample(cut, rng)] += 1
print("sum after cut:", sum(cut))   # 0.9011844162218705
print("counts:", counts)            # [6063, 1730, 1269, 0, 938]
```

**Symptom:** `" banana"` — the word you removed — was picked **938 times in 10,000**. The
remaining chances only cover 0.901 of the ruler. Every random point above that falls into
`sample`'s safety net, which returns the **last** index. ✅ Divide by the new total, as the
`topP` / `top_p` function in Exercise 2 does.

### ❌ 4. Unseeded randomness in tests

```js
// ❌ a different answer every run — a failing test can't be repeated
const pick = sample(probs, Math.random);

// ✅ the same answer every run
const pick2 = sample(probs, makeRng(42));
```

```python
# ❌ the global random.random gives different numbers on every run
import random
pick = sample(probs, random.random)

# ✅ your own seeded generator (or random.Random(42).random)
pick2 = sample(probs, make_rng(42))
```

**Symptom:** a test that fails "sometimes". You can't fix what you can't repeat. Any code that
uses randomness should take the generator as an argument, as `sample` does. Then tests pass in a
seeded one.

### ❌ 5. Reading cosine as a percentage

```js
// ❌ "0.5 means 50 % similar, so anything above 0.5 is a match"
const matches = notes.filter((n) => cosine(query, n.vec) > 0.5);

// ✅ rank by score and take the top k; choose any cut-off by testing on real questions
const top3 = notes
  .map((n) => ({ ...n, score: cosine(query, n.vec) }))
  .sort((a, b) => b.score - a.score)
  .slice(0, 3);
```

**Symptom:** a fixed cut-off that works for one embedding model returns everything, or nothing,
with another. Cosine measures an angle, and each model spreads its scores differently. Day 10
shows the typical range for real models, and Day 12 shows how to pick a cut-off by measuring.

### ❌ 6. Comparing decimals with `===` or `==`

```python
probs = softmax([2, 1, 0])
print(sum(probs) == 1)                 # False  (the sum is 0.9999999999999999)

import math
print(math.isclose(sum(probs), 1))     # True
```

```js
const probs = softmax([2, 1, 0]);
console.log(probs.reduce((s, p) => s + p, 0) === 1);                    // false
console.log(Math.abs(probs.reduce((s, p) => s + p, 0) - 1) < 1e-9);     // true
```

**Symptom:** a correct softmax "fails" its own test. Decimals are stored slightly inexactly
(§6.1), so always compare them with a tolerance.

---

## 8. Exercises

All five exercises import from the toolkit you built in §4 / §5. Put each exercise file in the
same folder as `toolkit.mjs` or `toolkit.py`. None of them needs an API key or a package.

### Exercise 1 — By hand first, then by code ●○○○○

Use pencil and paper (a calculator is fine). Then check yourself with code.

1. For `a = [1, 0, 1]` and `b = [0, 1, 1]`, compute `dot(a, b)`, `norm(a)` and `cosine(a, b)`.
2. Normalise `[0, 5]`.
3. Compute `softmax([1, 1, 1])`. Then predict: does `softmax([1, 1, 1], 5)` give anything
   different?

<details>
<summary>✅ Solution</summary>

**By hand.**

```
1. dot    = (1×0) + (0×1) + (1×1) = 1
   norm(a) = √(1 + 0 + 1) = √2 ≈ 1.414       (norm(b) is also √2)
   cosine = 1 ÷ (√2 × √2) = 1 ÷ 2 = 0.5      → the arrows are 60° apart
2. norm([0, 5]) = 5, so [0/5, 5/5] = [0, 1]
3. equal scores → equal shares → 1/3 each.
   Temperature 5 divides every score by 5: [0.2, 0.2, 0.2]. Still equal → still 1/3 each.
```

**JavaScript**

```js
// ex1.mjs — run with: node ex1.mjs
import { dot, norm, cosine, normalise, softmax } from "./toolkit.mjs";

const a = [1, 0, 1];
const b = [0, 1, 1];
console.log("dot     =", dot(a, b));
console.log("norm(a) =", norm(a));
console.log("cosine  =", cosine(a, b));
console.log("normalise([0, 5]) =", normalise([0, 5]));
console.log("softmax([1, 1, 1]) =", softmax([1, 1, 1]));
console.log("softmax([1, 1, 1], 5) =", softmax([1, 1, 1], 5));
```

**Python**

```python
# ex1.py — run with: python ex1.py
from toolkit import dot, norm, cosine, normalise, softmax

a = [1, 0, 1]
b = [0, 1, 1]
print("dot     =", dot(a, b))
print("norm(a) =", norm(a))
print("cosine  =", cosine(a, b))
print("normalise([0, 5]) =", normalise([0, 5]))
print("softmax([1, 1, 1]) =", softmax([1, 1, 1]))
print("softmax([1, 1, 1], 5) =", softmax([1, 1, 1], 5))
```

**Output** (JavaScript shown; Python prints `[0.0, 1.0]` and square brackets without spaces):

```
dot     = 1
norm(a) = 1.4142135623730951
cosine  = 0.4999999999999999
normalise([0, 5]) = [ 0, 1 ]
softmax([1, 1, 1]) = [ 0.3333333333333333, 0.3333333333333333, 0.3333333333333333 ]
softmax([1, 1, 1], 5) = [ 0.3333333333333333, 0.3333333333333333, 0.3333333333333333 ]
```

**Why this matters.** Two lessons hide here. First, the code says `0.4999999999999999`, not
`0.5`: the rounding from §6.1, in both languages. Second, temperature changes only the *gaps*
between scores. When there are no gaps, it has nothing to change. So if a model's top words have
nearly equal scores, lowering the temperature can't make it confident.
</details>

---

### Exercise 2 — Temperature and top-p lab ●●○○○

Use the five next-word scores from §3.8: `[5.0, 2.5, 2.0, 1.0, -2.0]` for
`" Paris", " located", " the", " Lyon", " banana"`.

1. For temperatures 0.7, 1 and 2, draw 1,000 words with `makeRng(1)` / `make_rng(1)` (a fresh
   generator for each temperature). Count how often each word appears.
2. Write `topP(probs, p)` / `top_p(probs, p)`. Day 01 describes the rule: sort the words from
   most to least likely, keep adding until the total reaches `p`, drop the rest. Then
   **renormalise**. Apply it with `p = 0.9` to the temperature-2 distribution.

<details>
<summary>✅ Solution</summary>

**JavaScript**

```js
// ex2.mjs — temperature and top-p lab
import { softmax, makeRng, sample } from "./toolkit.mjs";

const words = [" Paris", " located", " the", " Lyon", " banana"];
const logits = [5.0, 2.5, 2.0, 1.0, -2.0];

// Part A: 1,000 draws at three temperatures, same seed each time
for (const t of [0.7, 1, 2]) {
  const probs = softmax(logits, t);
  const rng = makeRng(1);
  const counts = words.map(() => 0);
  for (let i = 0; i < 1000; i++) counts[sample(probs, rng)]++;
  console.log(`T=${t}`.padEnd(6), words.map((w, i) => `${w.trim()}:${counts[i]}`).join("  "));
}

// Part B: top-p keeps the smallest set of top words whose probabilities reach p
function topP(probs, p) {
  const order = probs.map((_, i) => i).sort((i, j) => probs[j] - probs[i]); // biggest first
  const keep = new Set();
  let running = 0;
  for (const i of order) {
    keep.add(i);
    running += probs[i];
    if (running >= p) break;
  }
  const kept = probs.map((q, i) => (keep.has(i) ? q : 0));
  const total = kept.reduce((s, q) => s + q, 0);
  return kept.map((q) => q / total); // renormalise so they add up to 1 again
}

const hot = softmax(logits, 2);
console.log("\nT=2 before top-p:", hot.map((q) => q.toFixed(3)).join("  "));
console.log("T=2 after  top-p:", topP(hot, 0.9).map((q) => q.toFixed(3)).join("  "));
```

**Python**

```python
# ex2.py — temperature and top-p lab
from toolkit import softmax, make_rng, sample

words = [" Paris", " located", " the", " Lyon", " banana"]
logits = [5.0, 2.5, 2.0, 1.0, -2.0]

# Part A: 1,000 draws at three temperatures, same seed each time
for t in [0.7, 1, 2]:
    probs = softmax(logits, t)
    rng = make_rng(1)
    counts = [0] * len(words)
    for _ in range(1000):
        counts[sample(probs, rng)] += 1
    print(f"T={t}".ljust(6), "  ".join(f"{w.strip()}:{c}" for w, c in zip(words, counts)))


# Part B: top-p keeps the smallest set of top words whose probabilities reach p
def top_p(probs, p):
    order = sorted(range(len(probs)), key=lambda i: probs[i], reverse=True)  # biggest first
    keep = set()
    running = 0.0
    for i in order:
        keep.add(i)
        running += probs[i]
        if running >= p:
            break
    kept = [q if i in keep else 0.0 for i, q in enumerate(probs)]
    total = sum(kept)
    return [q / total for q in kept]  # renormalise so they add up to 1 again


hot = softmax(logits, 2)
print("\nT=2 before top-p:", "  ".join(f"{q:.3f}" for q in hot))
print("T=2 after  top-p:", "  ".join(f"{q:.3f}" for q in top_p(hot, 0.9)))
```

**Output** (identical in both languages):

```
T=0.7  Paris:942  located:32  the:20  Lyon:6  banana:0
T=1    Paris:865  located:57  the:52  Lyon:23  banana:3
T=2    Paris:565  located:197  the:131  Lyon:76  banana:31

T=2 before top-p: 0.597  0.171  0.133  0.081  0.018
T=2 after  top-p: 0.662  0.190  0.148  0.000  0.000
```

**Reading the result.** At temperature 2, `" banana"` appeared 31 times in 1,000 draws. In a
real answer, that's a nonsense word about every 30 words. Top-p walks down the list:
0.597, then 0.768, then 0.901. That passes 0.9, so it keeps three words and drops `" Lyon"` and
`" banana"` completely. After renormalising, the three kept chances add up to 1 again. This is
why Day 01 calls top-p a guard against "the model said something insane": the removed words can
**never** be picked, at any temperature.
</details>

---

### Exercise 3 — Break it five ways ●●○○○

Predict what each naive one-liner does, then run it. "Naive" means no safety checks — the code
you might write in a hurry.

1. Naive softmax (no max-subtraction) on the scores `[1000, 999, 998]`.
2. Naive cosine between `[1, 2, 3]` and a vector of zeros, `[0, 0, 0]`.
3. Naive softmax with temperature **0**.
4. Naive dot product of vectors with **different lengths** — try both orders.
5. Sorting numbers to find a percentile: JavaScript's plain `.sort()` on `[10, 9, 100, 25]`;
   Python's `sorted()` on the same numbers read as text from a file (`["10", "9", "100", "25"]`).

<details>
<summary>✅ Solution</summary>

| # | JavaScript (Node 24.15, verified) | Python 3.14.4 (verified) | Why | The toolkit's fix |
|---|---|---|---|---|
| 1 | `[ NaN, NaN, NaN ]` | `OverflowError: math range error` | `exp(1000)` is far above the largest number (about 1.8 × 10³⁰⁸). JS makes it `Infinity`, and `Infinity / Infinity` is `NaN`. | Subtract the biggest score first → `0.665 0.245 0.090` |
| 2 | `NaN` | `ZeroDivisionError: division by zero` (Python 3.13 says `float division by zero`) | The zero vector has length 0, so cosine divides 0 by 0. A zero vector has no direction. | Raise a clear error: `cosine: a vector of all zeros has no direction` |
| 3 | `[ NaN, NaN, NaN ]` | `ZeroDivisionError: division by zero` | Temperature divides the scores. Dividing by 0 gives `Infinity` and `NaN` in JS, and an error in Python. | Treat 0 as greedy → `[1, 0, 0]` |
| 4 | long·short: `NaN` · short·long: **`5`** | long·short: **`5`** · short·long: **`5`** | JS reads `b[2]`, which is `undefined`, so `3 × undefined` is `NaN`. In the other order it never looks at the extra item. Python's `zip` stops at the shorter list **without telling you**. | Check lengths first → `dot: lengths differ (3 vs 2)` |
| 5 | plain `.sort()` → `[ 10, 100, 25, 9 ]` | `sorted(text)` → `['10', '100', '25', '9']` | Both compare **text**, character by character: `"1"` comes before `"2"` and `"9"`. | Sort numbers numerically: `(a, b) => a - b` in JS; convert with `float()` in Python. Then p50 is `10` |

The most dangerous rows are **4** and **5**. Everything else fails loudly (`NaN`, an
exception). Those two return a **plausible wrong number** with no warning. In real retrieval,
row 4 happens when you mix vectors from two embedding models with different sizes. Python's
`zip(a, b, strict=True)` turns the silent bug into
`ValueError: zip() argument 2 is shorter than argument 1`.

**JavaScript**

```js
// break-it.mjs — naive one-liners, no safety checks. Run with: node break-it.mjs
import { softmax, cosine, percentile } from "./toolkit.mjs";

const naiveSoftmax = (xs, t = 1) => {
  const powers = xs.map((x) => Math.exp(x / t));
  const total = powers.reduce((s, x) => s + x, 0);
  return powers.map((x) => x / total);
};
const naiveDot = (a, b) => a.reduce((s, x, i) => s + x * b[i], 0);
const naiveNorm = (a) => Math.sqrt(naiveDot(a, a));
const naiveCosine = (a, b) => naiveDot(a, b) / (naiveNorm(a) * naiveNorm(b));

// 1. big scores
console.log("1 naive  :", naiveSoftmax([1000, 999, 998]));
console.log("1 toolkit:", softmax([1000, 999, 998]).map((p) => p.toFixed(3)));

// 2. a vector of all zeros
console.log("2 naive  :", naiveCosine([1, 2, 3], [0, 0, 0]));
try { cosine([1, 2, 3], [0, 0, 0]); } catch (e) { console.log("2 toolkit:", e.message); }

// 3. temperature 0
console.log("3 naive  :", naiveSoftmax([2, 1, 0], 0));
console.log("3 toolkit:", softmax([2, 1, 0], 0));

// 4. different lengths, both orders
console.log("4 naive long·short:", naiveDot([1, 2, 3], [1, 2]));
console.log("4 naive short·long:", naiveDot([1, 2], [1, 2, 3]));

// 5. sorting numbers
const ms = [10, 9, 100, 25];
console.log("5 plain sort  :", [...ms].sort());
console.log("5 numeric sort:", [...ms].sort((a, b) => a - b));
console.log("5 toolkit p50 :", percentile(ms, 50));
```

```
1 naive  : [ NaN, NaN, NaN ]
1 toolkit: [ '0.665', '0.245', '0.090' ]
2 naive  : NaN
2 toolkit: cosine: a vector of all zeros has no direction
3 naive  : [ NaN, NaN, NaN ]
3 toolkit: [ 1, 0, 0 ]
4 naive long·short: NaN
4 naive short·long: 5
5 plain sort  : [ 10, 100, 25, 9 ]
5 numeric sort: [ 9, 10, 25, 100 ]
5 toolkit p50 : 10
```

**Python**

```python
# break_it.py — naive one-liners, no safety checks. Run with: python break_it.py
import math
from toolkit import softmax, cosine, percentile


def naive_softmax(xs, t=1.0):
    powers = [math.exp(x / t) for x in xs]
    total = sum(powers)
    return [x / total for x in powers]


def naive_dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def naive_cosine(a, b):
    return naive_dot(a, b) / (math.sqrt(naive_dot(a, a)) * math.sqrt(naive_dot(b, b)))


def attempt(label, fn):
    try:
        print(label, fn())
    except Exception as e:
        print(label, f"{type(e).__name__}: {e}")


# 1. big scores
attempt("1 naive  :", lambda: naive_softmax([1000, 999, 998]))
attempt("1 toolkit:", lambda: [f"{p:.3f}" for p in softmax([1000, 999, 998])])

# 2. a vector of all zeros
attempt("2 naive  :", lambda: naive_cosine([1, 2, 3], [0, 0, 0]))
attempt("2 toolkit:", lambda: cosine([1, 2, 3], [0, 0, 0]))

# 3. temperature 0
attempt("3 naive  :", lambda: naive_softmax([2, 1, 0], 0))
attempt("3 toolkit:", lambda: softmax([2, 1, 0], 0))

# 4. different lengths, both orders
attempt("4 naive long·short:", lambda: naive_dot([1, 2, 3], [1, 2]))
attempt("4 naive short·long:", lambda: naive_dot([1, 2], [1, 2, 3]))
attempt("4 zip(strict=True):", lambda: sum(x * y for x, y in zip([1, 2, 3], [1, 2], strict=True)))

# 5. sorting numbers that are secretly text (e.g. read from a CSV file)
ms = ["10", "9", "100", "25"]
attempt("5 sorted text   :", lambda: sorted(ms))
attempt("5 sorted numbers:", lambda: sorted(float(x) for x in ms))
attempt("5 toolkit p50   :", lambda: percentile([float(x) for x in ms], 50))
```

```
1 naive  : OverflowError: math range error
1 toolkit: ['0.665', '0.245', '0.090']
2 naive  : ZeroDivisionError: division by zero
2 toolkit: ValueError: cosine: a vector of all zeros has no direction
3 naive  : ZeroDivisionError: division by zero
3 toolkit: [1.0, 0.0, 0.0]
4 naive long·short: 5
4 naive short·long: 5
4 zip(strict=True): ValueError: zip() argument 2 is shorter than argument 1
5 sorted text   : ['10', '100', '25', '9']
5 sorted numbers: [9.0, 10.0, 25.0, 100.0]
5 toolkit p50   : 10.0
```

**The lesson.** JavaScript tends to fail **quietly** (`NaN`, `Infinity`). Python tends to fail
**loudly** (an exception). Both can return a wrong number with no warning. Guard rails belong in
the shared toolkit, written once, rather than in every caller.
</details>

---

### Exercise 4 — Measure it: precision, recall and the five-test trap ●●●○○

**Part A.** StudyBuddy's router decides "is this a maths question?". Here are ten questions:

```
truth     = [yes, yes, yes, yes, no,  no,  no, no, no, no]   ← really maths?
predicted = [yes, yes, yes, no,  yes, yes, no, no, no, no]   ← router said maths?
```

Count the hits, false alarms, misses and correct "no"s. Compute accuracy, precision and recall.

**Part B.** Write `runSuite(trueAccuracy, nTests, rng)`: each test passes when `rng() <
trueAccuracy`, and it returns the fraction passed. Using one `makeRng(2026)` / `make_rng(2026)`,
run 10,000 suites for each combination of 5 or 100 tests and true accuracy 0.8 or 0.6. For each
combination, print p5 and p95 of the scores (use your `percentile`), and how often every test
passed.

Then answer: a teammate's bot passed 5 / 5 tests. Your bot passed 4 / 5. Is theirs better?

<details>
<summary>✅ Solution</summary>

**JavaScript**

```js
// ex4.mjs — measure it
import { makeRng, percentile } from "./toolkit.mjs";

// Part A: StudyBuddy's router. true = "this question is about maths".
const truth     = [true, true, true, true, false, false, false, false, false, false];
const predicted = [true, true, true, false, true, true, false, false, false, false];

let tp = 0, fp = 0, fn = 0, tn = 0;
for (let i = 0; i < truth.length; i++) {
  if (predicted[i] && truth[i]) tp++;        // said maths, was maths
  else if (predicted[i] && !truth[i]) fp++;  // said maths, was not  (false alarm)
  else if (!predicted[i] && truth[i]) fn++;  // missed a maths question
  else tn++;                                 // said not maths, was not
}
console.log({ tp, fp, fn, tn });
console.log("accuracy  =", (tp + tn) / truth.length);
console.log("precision =", tp / (tp + fp));
console.log("recall    =", tp / (tp + fn));

// Part B: how much can a small test suite tell you?
function runSuite(trueAccuracy, nTests, rng) {
  let passed = 0;
  for (let i = 0; i < nTests; i++) {
    if (rng() < trueAccuracy) passed++; // each test passes with this probability
  }
  return passed / nTests;
}

const rng = makeRng(2026);
console.log("");
for (const nTests of [5, 100]) {
  for (const acc of [0.8, 0.6]) {
    const scores = [];
    for (let trial = 0; trial < 10000; trial++) scores.push(runSuite(acc, nTests, rng));
    const perfect = scores.filter((s) => s === 1).length / scores.length;
    console.log(
      `${String(nTests).padStart(3)} tests, true accuracy ${acc}: ` +
        `p5=${percentile(scores, 5).toFixed(2)}  p95=${percentile(scores, 95).toFixed(2)}  ` +
        `all passed in ${(perfect * 100).toFixed(1)}% of runs`,
    );
  }
}
```

**Python**

```python
# ex4.py — measure it
from toolkit import make_rng, percentile

# Part A: StudyBuddy's router. True = "this question is about maths".
truth     = [True, True, True, True, False, False, False, False, False, False]
predicted = [True, True, True, False, True, True, False, False, False, False]

tp = fp = fn = tn = 0
for t, p in zip(truth, predicted, strict=True):
    if p and t:
        tp += 1  # said maths, was maths
    elif p and not t:
        fp += 1  # said maths, was not  (false alarm)
    elif not p and t:
        fn += 1  # missed a maths question
    else:
        tn += 1  # said not maths, was not
print({"tp": tp, "fp": fp, "fn": fn, "tn": tn})
print("accuracy  =", (tp + tn) / len(truth))
print("precision =", tp / (tp + fp))
print("recall    =", tp / (tp + fn))


# Part B: how much can a small test suite tell you?
def run_suite(true_accuracy, n_tests, rng):
    passed = 0
    for _ in range(n_tests):
        if rng() < true_accuracy:  # each test passes with this probability
            passed += 1
    return passed / n_tests


rng = make_rng(2026)
print()
for n_tests in [5, 100]:
    for acc in [0.8, 0.6]:
        scores = [run_suite(acc, n_tests, rng) for _ in range(10_000)]
        perfect = sum(1 for s in scores if s == 1) / len(scores)
        print(
            f"{n_tests:>3} tests, true accuracy {acc}: "
            f"p5={percentile(scores, 5):.2f}  p95={percentile(scores, 95):.2f}  "
            f"all passed in {perfect * 100:.1f}% of runs"
        )
```

**Output** (identical in both languages, apart from how the dictionary prints):

```
{ tp: 3, fp: 2, fn: 1, tn: 4 }
accuracy  = 0.7
precision = 0.6
recall    = 0.75

  5 tests, true accuracy 0.8: p5=0.40  p95=1.00  all passed in 32.7% of runs
  5 tests, true accuracy 0.6: p5=0.20  p95=1.00  all passed in 8.2% of runs
100 tests, true accuracy 0.8: p5=0.73  p95=0.86  all passed in 0.0% of runs
100 tests, true accuracy 0.6: p5=0.52  p95=0.68  all passed in 0.0% of runs
```

**Is the teammate's bot better?** You can't tell. With 5 tests, a bot that is right only 60 % of
the time still scored a perfect 5 / 5 in 8.2 % of the simulated runs. Its middle-90 % range,
0.20 to 1.00, covers almost every possible score. With 100 tests the ranges for 0.6 and 0.8 no
longer overlap, so the difference becomes visible. As a rough rule: a gap between two systems
means something only if it is bigger than the spread you see when you re-run one of them. (The
simulated 32.7 % sits close to the exact `0.8⁵ = 32.8 %`, which is a good sign the simulation is
right.)

**Why the seed matters here.** With a fixed seed you got exactly these numbers, and so will
anyone who runs this code. That's what makes a simulation something you can quote and check.
</details>

---

### Exercise 5 — 🎯 StudyBuddy's first search ●●●●○

StudyBuddy needs to find the right study note for a question. Real systems turn text into vectors
with an embedding model (Day 10). Today you make the vectors **by hand**. Each note gets three
numbers: how much it is about **[maths, history, cooking]**.

| Note | Vector |
|---|---|
| Solving linear equations | `[0.9, 0.1, 0.0]` |
| The French Revolution | `[0.1, 0.9, 0.1]` |
| Baking bread at home | `[0.0, 0.1, 0.9]` |
| Scaling a recipe by ratio | `[0.6, 0.0, 0.7]` |
| A short history of algebra | `[0.6, 0.7, 0.0]` |

1. Write `search(queryVec, k = 3)` that scores every note with `cosine` and returns the top `k`.
2. Search for "How do I solve x + 3 = 7?" as `[1.0, 0.2, 0.0]`, and "Who invented bread?" as
   `[0.0, 0.6, 0.6]`.
3. Look at the second result list. What went nearly wrong, and why?
4. **Stretch:** add a sixth note, `[1.8, 0.2, 0.0]` (twice the first note). Predict its cosine
   score for the first question. Then predict its plain **dot product** score.

<details>
<summary>✅ Solution</summary>

**JavaScript**

```js
// ex5.mjs — StudyBuddy's first retrieval: rank notes by cosine similarity
import { cosine } from "./toolkit.mjs";

// Hand-made "embeddings". The three numbers mean: [maths, history, cooking].
const notes = [
  { title: "Solving linear equations",  vec: [0.9, 0.1, 0.0] },
  { title: "The French Revolution",     vec: [0.1, 0.9, 0.1] },
  { title: "Baking bread at home",      vec: [0.0, 0.1, 0.9] },
  { title: "Scaling a recipe by ratio", vec: [0.6, 0.0, 0.7] },
  { title: "A short history of algebra", vec: [0.6, 0.7, 0.0] },
];

function search(queryVec, k = 3) {
  return notes
    .map((note) => ({ title: note.title, score: cosine(queryVec, note.vec) }))
    .sort((a, b) => b.score - a.score) // highest score first
    .slice(0, k);
}

for (const [question, vec] of [
  ["How do I solve x + 3 = 7?", [1.0, 0.2, 0.0]],
  ["Who invented bread?", [0.0, 0.6, 0.6]],
]) {
  console.log(`\nQ: ${question}`);
  for (const hit of search(vec)) console.log(`  ${hit.score.toFixed(3)}  ${hit.title}`);
}
```

**Python**

```python
# ex5.py — StudyBuddy's first retrieval: rank notes by cosine similarity
from toolkit import cosine

# Hand-made "embeddings". The three numbers mean: [maths, history, cooking].
notes = [
    {"title": "Solving linear equations",   "vec": [0.9, 0.1, 0.0]},
    {"title": "The French Revolution",      "vec": [0.1, 0.9, 0.1]},
    {"title": "Baking bread at home",       "vec": [0.0, 0.1, 0.9]},
    {"title": "Scaling a recipe by ratio",  "vec": [0.6, 0.0, 0.7]},
    {"title": "A short history of algebra", "vec": [0.6, 0.7, 0.0]},
]


def search(query_vec, k=3):
    scored = [{"title": n["title"], "score": cosine(query_vec, n["vec"])} for n in notes]
    scored.sort(key=lambda hit: hit["score"], reverse=True)  # highest score first
    return scored[:k]


for question, vec in [
    ("How do I solve x + 3 = 7?", [1.0, 0.2, 0.0]),
    ("Who invented bread?", [0.0, 0.6, 0.6]),
]:
    print(f"\nQ: {question}")
    for hit in search(vec):
        print(f"  {hit['score']:.3f}  {hit['title']}")
```

**Output** (identical in both languages):

```
Q: How do I solve x + 3 = 7?
  0.996  Solving linear equations
  0.787  A short history of algebra
  0.638  Scaling a recipe by ratio

Q: Who invented bread?
  0.781  Baking bread at home
  0.776  The French Revolution
  0.537  Scaling a recipe by ratio
```

**What nearly went wrong.** For "Who invented bread?", *The French Revolution* scored 0.776, about
0.005 below the bread note. Three hand-picked numbers can't express "the history of bread". The
query is half history and half cooking, and the French Revolution note is mostly history. Real
embedding models learn hundreds of dimensions from data, so they can tell these apart. That is
exactly the upgrade Day 10 makes. Your `search` function will barely change; only the vectors
will.

**Stretch answers (verified).** The doubled note `[1.8, 0.2, 0.0]` points the same way as
`[0.9, 0.1, 0.0]`, so its cosine is the same **0.996** — cosine ignores length. Its plain dot
product, though, is **1.840**, twice the original note's **0.920**. A dot-product search would
rank a note higher just for being "longer". That's why §3.3 divides the lengths out, and why
Day 10 checks whether a model's vectors are already normalised.

**StudyBuddy now has:** a ranking function. Given a question vector, it returns the best notes
in order. Every retrieval system in Week 2 is this idea, scaled up.
</details>

---

## 9. Interview questions

### Basic

**Q1. What is a vector, and why do AI systems use them?**

A vector is an ordered list of numbers. AI systems turn text into vectors (embeddings) so that
meaning becomes something you can calculate with. Similar texts get vectors that point in
similar directions, and "find related text" becomes "find nearby vectors". A typical embedding
has hundreds to a few thousand numbers.

---

**Q2. What does softmax do?**

It turns a list of raw scores (logits), which can be any size or sign, into probabilities that
are all positive and add up to 1. It raises *e* to each score, then divides by the total.
Bigger scores get a disproportionately bigger share: scores `[2, 1, 0]` become
`0.665, 0.245, 0.090`.

---

**Q3. What does temperature do, mathematically?**

It divides every logit by the temperature before softmax. Below 1, the gaps between scores
grow and the distribution gets sharper; above 1, the gaps shrink and it gets flatter. At
temperature 0 you can't divide, so libraries switch to greedy: always take the top token. With
the scores `[2, 1, 0]`, T = 0.5 gives 0.867 for the top choice and T = 2 gives 0.506.

---

**Q4. Why report p50 and p95 latency instead of the average?**

The mean is pulled up by rare slow requests and describes nobody. In a 20-request example, one
30-second timeout made the mean 2.71 s while the median was 1.1 s. p50 tells you the typical
experience; p95 tells you what one user in twenty suffers. You set alerts and promises on p95
(or p99).

---

### Intermediate

**Q5. When do cosine similarity and dot product give the same ranking?**

When all vectors are normalised to length 1. Cosine is the dot product divided by both lengths;
if the lengths are 1, there is nothing to divide. That is why vector databases often store
normalised vectors and use the cheaper dot product. If vectors are *not* normalised, dot
product rewards length: a vector twice as long scores twice as high with the same direction.

---

**Q6. Why do models and APIs use log-probabilities?**

Two reasons. A sequence's probability is a product of many small numbers, and it quickly
underflows to 0. For example, 400 tokens at 0.01 each is 10⁻⁸⁰⁰, far below the smallest float
(about 5 × 10⁻³²⁴). Logs turn the product into a sum (-1842.07 here), which stays in range. And sums
are cheaper and more stable to compute. A logprob near 0 means "very sure"; very negative means
"unlikely".

---

**Q7. Explain precision and recall with an example. When would you favour each?**

Precision: of the items I flagged, how many were right? Recall: of all the items I should have
flagged, how many did I find? A router that flagged 5 questions as maths, 3 correctly, out of 4
real maths questions has precision 0.6 and recall 0.75. Favour precision when false alarms are
expensive (spam filtering real email). Favour recall when misses are expensive (safety review,
or retrieval where a later reranker can drop extras).

---

**Q8. Why does softmax subtract the maximum logit, and why is that allowed?**

`exp` overflows above about 709: `exp(710)` is `Infinity` in JavaScript and an
`OverflowError` in Python, so naive softmax on large logits returns `NaN` or crashes. Subtracting
the same number from every logit multiplies every `exp` by the same factor. It appears on the
top and the bottom of the fraction and cancels, so the probabilities don't change. After
subtracting, the biggest `exp` is exactly 1, so overflow can't happen.

---

### Advanced

**Q9. Your eval suite has 5 cases and the new prompt passes all 5. Ship it?**

Not on that evidence. A system that is truly right 80 % of the time passes 5 / 5 about a third
of the time (0.8⁵ ≈ 0.33; a seeded simulation gave 32.7 %). Even a 60 % system did it 8.2 % of
the time. With 5 cases the score ranges of a 60 % and an 80 % system overlap almost completely.
With 100 cases they separate (0.52–0.68 vs 0.73–0.86 in simulation). Grow the set, re-run the
old and new prompts on the same cases, and treat any gap smaller than run-to-run noise as no
difference.

---

**Q10. Explain "attention" using only dot products and softmax.**

Each token gets turned into vectors. The model needs to decide how much token A should pay
attention to every other token. So it takes dot products between A's vector and theirs, giving
one score per token. That is many dot products at once: a matrix multiplication. Softmax turns
those scores into weights that add up to 1. A's new representation is a weighted mix of the other tokens'
information. Large dot products mean strong attention. Real models add details (separate query,
key and value vectors, scaling, many attention "heads"), but the core is these two steps.

---

**Q11. Code that should be random is making your tests flaky. How do you fix it without
removing the randomness?**

Inject the random-number generator instead of calling a global one. Production code passes an
unseeded generator; tests pass one with a fixed seed, so the "random" choices repeat exactly.
JavaScript's `Math.random()` can't be seeded, so you write or import a small seeded generator.
In Python, use `random.Random(seed)`. If two languages must agree on the numbers, use the same
formula in both, as this lesson's linear congruential generator does. Never use such a generator
for security; use the crypto APIs instead.

---

## 10. Recap

### What you learned

- ✅ A **vector** is a list of numbers; its **norm** is its length: `√(sum of squares)`
- ✅ The **dot product** multiplies pairs and adds; it is big for aligned vectors, 0 at a right
  angle, negative for opposite ones
- ✅ **Cosine similarity** divides out the lengths: from -1 to 1, direction only — and it is
  **not** a percentage
- ✅ After **normalising** to length 1, cosine equals the dot product
- ✅ A **matrix** times a vector is many dot products at once — the core of retrieval and attention
- ✅ A **distribution** has no negative numbers and adds up to 1; after removing options,
  **renormalise**
- ✅ **Softmax** = `exp` each score, divide by the total. Subtract the max first to avoid overflow
- ✅ **Temperature** divides the logits: low = sharper, high = flatter, 0 = greedy (special-cased)
- ✅ **Sampling** picks by walking the cumulative "ruler"; a **seed** makes it repeatable
- ✅ **Log-probabilities** turn tiny products into ordinary sums; they are always ≤ 0
- ✅ Use **p50 and p95**, not the mean, for latency
- ✅ **Precision** = were my "yes" answers right; **recall** = did I find all the real yeses
- ✅ **Five tests can't tell** a 60 % system from an 80 % one; more cases shrink the luck

### Your toolkit at a glance

```
 VECTORS        dot(a, b)            Σ aᵢ·bᵢ                    lengths must match
                norm(a)              √dot(a, a)
                cosine(a, b)         dot ÷ (norm·norm)          -1 … 1; zero vector → error
                normalise(a)         a ÷ norm(a)                length 1
 PROBABILITY    softmax(z, T)        exp((z-max)/T) ÷ total     T = 0 → greedy
                makeRng(seed)        LCG, same in JS and Python  not for security
                sample(p, rng)       walk the ruler
 STATISTICS     mean(xs)             sum ÷ count                hurt by outliers
                percentile(xs, p)    sorted[ceil(p·n/100) − 1]  numeric sort in JS!
```

### Tomorrow

**[Day 01 — What an LLM actually is](../week-01-foundations/day-01-llms-tokens-and-inference.md)**:
today every score was made up by hand. Tomorrow you meet the thing that produces real scores — a
large language model. You will see tokens, the context window, and the sampling knobs
(temperature and top-p) acting on a real model's distribution. Every one of those knobs is a line
of code you wrote today.

### Quick self-check

1. Softmax of `[5, 5, 5]` at temperature 0.1 — what do you get, and why does the temperature
   not matter?
2. Your retrieval code returns a cosine of `NaN` for one document. Name two possible causes.
3. A dashboard shows "average latency 900 ms" and users complain the app is slow. What two
   numbers do you ask for, and what do you expect them to show?

<details>
<summary>Answers</summary>

1. `[1/3, 1/3, 1/3]`. Temperature divides the scores, which gives `[50, 50, 50]`. The gaps are
   still zero, so the shares stay equal. Temperature only stretches or shrinks gaps that
   already exist (Exercise 1).

2. A **zero vector**: its length is 0, so cosine divides 0 by 0. Or vectors of **different
   lengths**: JavaScript reads `undefined` and gets `NaN` (Exercise 3, items 2 and 4). Mixing
   vectors from two embedding models with different sizes is one way to get the second cause.

3. **p50 and p95** (and p99 if you have enough requests). Expect p50 to look fine and p95 to be
   much worse: a few very slow requests are being averaged away. The complaints come from the
   users in that slow tail (§3.10).
</details>

---

<div align="center">

**[← Day 0B — Programming for AI](day-00b-programming-for-ai.md)** · **[Week 0 index](README.md)** · **[Day 01 — What an LLM actually is →](../week-01-foundations/day-01-llms-tokens-and-inference.md)**

</div>
