# Day 32 — Dataset Engineering: Good Data In, Good Model Out

> ⏱ **Time:** ~3 hours · 🎯 **Prereqs:** [Day 31](day-31-fine-tuning.md), [Day 25](../week-04-production-projects-and-interviews/day-25-observability-and-evaluation.md) · 🧩 **Difficulty:** ●●●○○

**Today you learn:** Day 31's fine-tune and Day 25's evals are only as good as the data you feed
them. Real data is messy. It has copies, junk, private details, and too few examples. Today you
build one small data pipeline, in JavaScript and Python, for a question bank. It removes exact
and near copies, filters junk, and hides personal data. It adds checked synthetic examples and
splits the data without leaks. It measures how well two labellers agree, and it stamps the
result with a version. Every number in this chapter comes from running the code.

> 📖 **Words you'll meet today**
>
> - **Normalisation** — rewriting text into one standard form (same spaces, same letter case),
>   so that copies look identical.
> - **Hash** — a short fingerprint of some text. The same text always gives the same hash.
> - **Near-duplicate** — two records that say the same thing with small differences, such as
>   one changed word.
> - **Jaccard similarity** — the share of pieces two texts have in common: 0 means nothing
>   shared, 1 means identical sets.
> - **Synthetic data** — training or test examples written by a model instead of a person.
> - **Data leakage** — when test examples (or close copies of them) are also in the training
>   data, so scores look better than they are.
> - **Golden set** — a small, carefully checked set of test questions that you never train on.
> - **Cohen's kappa** — a score for how much two labellers agree, after removing the agreement
>   you would get by luck.

---

## 1. The problem

StudyBuddy's team collected a question bank from three places: questions students typed,
lecture notes pasted from the web, and a spreadsheet a tutor made. On Day 31 you fine-tuned on
it. On Day 25 you evaluated on it. The numbers looked great. Then the complaints arrived:

```
   eval report        accuracy on held-out test set .......... 94 %
   student, Monday    "It answers 'What does HTTPS add to HTTP?' perfectly,
                       but not 'Why do websites use HTTPS?'"
   student, Tuesday   "It told me to email ayesha.khan@example.com for help. Who is that?"
   student, Tuesday   "Why does it keep saying 'Click here to subscribe'?"
   tutor, Wednesday   "Half the Spanish questions get English answers."
   you, Thursday      grep the data: the "held-out" test question
                       "What does HTTPS add on top of HTTP?" has a twin in the training set
```

*(The log is an illustrative story. The data problems in it are real: they are planted in
today's dataset, and the code finds them.)*

Nothing was wrong with the model or the training code. The test was easy because test
questions had near-copies in the training data. The model repeated a stranger's email because
the email was in the data. It learned the boilerplate because nobody removed it. The 94 % was
measuring memory, not skill.

### The real-life version

Think of a library that receives a big box of donated books.

```
   two copies of the same edition          → keep one                 EXACT DEDUPE
   the same book, a different printing     → keep one                 NEAR DEDUPE
   torn pages, adverts, a foreign-language
     book in the wrong section             → remove or move           QUALITY FILTER
   a private letter left inside a book     → take it out              PII SCRUB
   a catalogue card for every book         → what, where, which shelf LABEL
   a reference shelf that is never lent    → the books used to judge  GOLDEN SET
     out                                     everything else
   the catalogue itself, dated and signed  → what you have, and when  VERSION + CARD
```

Each of those is a stage you build today.

---

## 2. Mental model

### One pipeline, eight stages

```
   COLLECT ─► CLEAN ─► EXACT ─► NEAR ─► QUALITY ─► PII ─► LABEL ─► SPLIT ─► VERSION
              NFKC,    DEDUPE   DEDUPE  FILTER     SCRUB  + synth   by       hash +
              spaces                                       data     group    card

   our run:   24  ───► 21 ────► 18 ───► 14 ──────► 14 ──► 16 ────► 11 / 5 ─► f5ce2d97…
   (measured)          −3       −3      −4         4 rows  +2       train/
                                                   edited  checked  test
```

Every arrow is a function: records in, records out, plus a list of what was removed and why.
That list matters as much as the output. It tells you what your data really looked like.

| Stage | What it removes or fixes | What goes wrong if you skip it |
|---|---|---|
| **Clean** | odd spaces, full-width letters, invisible Unicode differences | copies look different, so dedupe misses them |
| **Exact dedupe** | identical records after cleaning | some examples count twice in training; test copies of training rows |
| **Near dedupe** | records that differ by a word or punctuation mark | the same as above, but harder to see |
| **Quality filter** | too short, wrong language, boilerplate, repeated text | the model learns junk |
| **PII scrub** | emails, phone numbers (and, with better tools, names) | the model can repeat private data |
| **Label** | adds answers or grades; synthetic rows are checked here | wrong labels teach wrong answers |
| **Split** | puts each group of related rows on one side only | **leakage** — scores that are too good |
| **Version** | records a hash, counts and choices | nobody can reproduce or trust the result |

> 💡 The stages are ordered so cheap work happens first. Hashing is cheaper than comparing
> pairs, so exact dedupe runs before near dedupe. Both run before any step that costs money,
> such as a labelling vendor or a model call.

---

## 3. First principles

### 3.1 Why data matters more than you think

> 💬 **In plain words:** a model learns what it sees most often. Copies and junk change what it
> sees most often.

Fine-tuning (Day 31) learns from frequency. If one example appears five times, the model
treats it as five times more important. Evaluation (Day 25) assumes the test questions are new
to the model. Copies break both.

Our hand-made bank has 24 rows. **6 of them (25 %) are copies**: 3 exact and 3 near (measured
below). Real collections are often worse, because the same notes get pasted again and again.

Large-scale studies found the same pattern. Lee et al. (2021) studied common web datasets. They
report that "over 1% of the unprompted output" of models trained on them was copied word for word
from the training data. After de-duplication, models produced memorised text about ten times
less often. They also found that train–test overlap "affects over 4% of the validation set" of
standard datasets. *(Cited, not run here — see Sources at the end of §6.)*

### 3.2 Exact duplicates: normalise, then hash

> 💬 **In plain words:** first make copies look the same, then give each record a fingerprint.
> Two records with the same fingerprint are copies.

A **hash** function such as SHA-256 turns any text into a fixed-length fingerprint. The same
text always gives the same hash. Different text almost never does. So you can find copies with
one pass and a lookup table, instead of comparing every pair.

The catch: "the same text" means **the same bytes**. These three rows look the same to a
person, but not to a hash:

```
   r01  "What does HTTPS add to HTTP?"
   r02  "  what does HTTPS add to HTTP?  "           extra spaces, lower-case "w"
   r22  "Ｗｈａｔ ｄｏｅｓ ａ ＳＱＬ ＪＯＩＮ ｄｏ？"     full-width letters (copy of r12)
```

So you **normalise** first:

1. **Unicode NFKC** — turns "compatibility" characters, such as full-width letters, into their
   plain forms. Verified: r22 becomes `"What does a SQL JOIN do?"`.
2. **Collapse whitespace** — any run of spaces, tabs or newlines becomes one space; trim the
   ends.
3. **Lower-case the key** — keep the original casing in the stored record, but compare
   lower-cased text.

Measured on our 24 rows:

```
   hash the raw text        23 kept · dropped r06=r05                    (only the perfect copy)
   normalise, then hash     21 kept · dropped r02=r01, r06=r05, r22=r12
```

Normalising found **three times as many** copies. Day 09 used a content hash on chunks; this is
the same idea, made reliable.

> ⚠️ Decide what "the same" means for your task. Our key is `question || answer`. If two rows
> have the same question but different answers, they are *not* duplicates here. They are a
> **conflict**, and a person should look at them.

### 3.3 Near-duplicates: shingles and Jaccard

> 💬 **In plain words:** cut each text into small overlapping pieces. Count how many pieces two
> texts share. A high share means a near-copy.

Hashes only find perfect copies. Change one character and the hash is completely different.
For near-copies you need a **similarity score**.

**Shingles** are overlapping pieces of text. With 5-character shingles, `"https"` → `"https"`,
and `"what does"` → `"what "`, `"hat d"`, `"at do"`, `"t doe"`, `" does"`. Each text becomes a set
of shingles. **Jaccard similarity** compares two sets:

```
   J(A, B) = |A ∩ B| / |A ∪ B|        shared pieces ÷ all distinct pieces
```

Measured on the 21 rows left after exact dedupe (210 pairs), highest first:

| Pair | Jaccard (k = 5) | What it is |
|---|---|---|
| r18–r20 | **0.731** | TCP vs UDP; one has no "?", "; " became ", ", "can" became "may" |
| r09–r10 | **0.670** | "What is …" vs "What's … a binary search", "each" vs "every" |
| r01–r03 | **0.669** | "add to" vs "add on top of", "cannot" vs "can't" |
| r05–r07 | 0.183 | two *different* recursion questions |
| r15–r21 | 0.126 | two different git questions |

There is a clear gap between 0.669 and 0.183. Any threshold in that gap works. We use **0.5**.
Near-dedupe at 0.5 drops `r03~r01`, `r10~r09` and `r20~r18`, leaving 18 rows.

The threshold is a trade-off you must check on your own data. Measured:

```
   threshold 0.15   drops r03, r07, r10, r20    ← r07 is a different question: a false match
   threshold 0.5    drops r03, r10, r20         ← exactly the planted copies
   threshold 0.8    drops nothing               ← misses all three
```

> 💡 Shingles find copies that **share wording**. They miss paraphrases with different words
> ("Why do websites use HTTPS?"). For those, use embeddings, as in
> [Day 10's semantic dedup exercise](../week-02-data-embeddings-and-rag/day-10-embeddings.md).
> Many pipelines run shingles first (cheap) and embeddings second (slower, smarter).

### 3.4 MinHash: comparing millions of records

> 💬 **In plain words:** instead of comparing whole sets of pieces, keep a short summary of each
> set. Similar sets have similar summaries.

Comparing every pair is fine for 21 rows (210 pairs). For one million rows it is
n(n − 1)/2 = **499,999,500,000** pairs. That is too slow.

**MinHash** (Broder, 1997) summarises a set with a short list of numbers called a
**signature**. For each of n hash functions, you hash every shingle and keep the smallest
value. The chance that two sets share the same smallest value equals their Jaccard similarity.
So the share of matching positions in two signatures **estimates** Jaccard.

Measured with 64-number signatures:

```
   pair      exact J   MinHash estimate (64)
   r18–r20   0.731     0.703
   r09–r10   0.670     0.656
   r01–r03   0.669     0.734
   r05–r07   0.183     0.109
   r13–r24   0.000     0.000
```

The estimate is close, but not exact. More hash functions give a better estimate. Measured
over the top 4 pairs, the largest error was **0.121 with 16**, **0.074 with 64** and
**0.034 with 256** hash functions.

The signature alone does not remove the pair comparisons. A second trick,
**locality-sensitive hashing (LSH)**, does. You cut each signature into b bands of r numbers.
Two records become a "candidate pair" only if at least one band matches exactly. The chance of
that is 1 − (1 − s^r)^b, where s is their similarity. Computed for b = 16 bands of r = 4:

```
   similarity 0.3  → 0.122 chance of being compared
   similarity 0.5  → 0.644
   similarity 0.7  → 0.988
   similarity 0.9  → 1.000
```

Similar pairs are almost always compared. Different pairs are mostly skipped. You then run the
exact Jaccard only on candidates. *(We implement MinHash today; LSH is shown as the formula
above, computed but not built.)*

### 3.5 Quality filters: cheap rules that catch junk

> 💬 **In plain words:** simple rules, such as "too short" or "no common English words", remove
> most junk before a person or a model has to look at it.

Quality filters are **heuristics** — quick rules of thumb, not proof. Ours check four things,
in order, and report the first failure:

| Rule | Test | Caught |
|---|---|---|
| **Boilerplate** | matches "click here", "subscribe", "cookie", "all rights reserved"… | r13 |
| **Too short** | fewer than 6 words in question + answer | r08 (`ok` / `yes`) |
| **Repetitive** | distinct words ÷ all words < 0.5 | r23 ("Big O Big O Big O …") |
| **Not English** | share of common English words < 0.15 | r11 (Spanish) |

The language rule uses **stop words**: very common words such as "the", "is", "what". Normal
English text is full of them. Measured stop-word shares: the Spanish row r11 scored **0.05**;
the short English row r04 ("Which port does HTTPS use by default? Port 443.") scored **0.44**;
r19 scored **0.35**. The Gopher paper (Rae et al., 2021) used a similar rule for web text. It
kept a document only if it had at least two words from a short English stop-word list.

Result: 18 → **14 rows**, rejected `r08:too-short`, `r11:not-english`, `r13:boilerplate`,
`r23:repetitive`.

> ⚠️ Heuristics fail on edge cases. A correct answer that is mostly code (`git reset --soft
> HEAD~1`) has few stop words. For real language detection, use a trained language-ID model,
> such as fastText's language identifier *(not executed here — check your version)*. And
> "not English" doesn't always mean "remove". If StudyBuddy should answer in Spanish, route
> those rows to a Spanish set instead.

### 3.6 PII scrubbing: regex helps, and regex misses

> 💬 **In plain words:** find personal details with patterns and swap them for labels like
> `[EMAIL]`. Patterns catch the common formats and miss the unusual ones.

On [Day 24](../week-04-production-projects-and-interviews/day-24-reliability.md) you used PII
middleware to protect *live requests*. Training data needs the same protection *offline*,
before the data reaches a fine-tune, a labelling vendor or a synthetic-data model. A model can
repeat anything it was trained on.

Our scrubber uses two regular expressions (regex — text patterns): one for emails, one for
phone numbers. Measured on the 14 rows:

```
   r14  EMAIL  ayesha.khan@example.com          → [EMAIL]      ✅ caught
   r16  PHONE  +44 7700 900123                  → [PHONE]      ✅ caught
   r17  PHONE  020 7946 0958, (555) 010-4477    → [PHONE] ×2   ✅ caught
   r15  PHONE  2026-03-14                       → [PHONE]      ❌ a date, not a phone
   r21  "Ask Ayesha Khan: ayesha dot khan at example dot com"  ❌ name and email both missed
```

More tests of the same phone pattern (verified, both languages):

```
   "call 555 0104"             → unchanged         ❌ short local number missed
   "version 1.2.3.4.5"         → "version [PHONE]" ❌ false positive
   "ISBN 978-0-13-468599-1"    → "ISBN [PHONE]"    ❌ false positive
   "Ask Ayesha Khan (ayesha.khan@example.com)" → "Ask Ayesha Khan ([EMAIL])"   name kept
```

Regex is wrong in **both directions**. It misses unusual formats and **names**, and it
removes harmless numbers. Be honest about that in your dataset card. Better tools combine
several methods. Microsoft Presidio, for example, uses regex, named-entity recognition (a
model that finds names, places and organisations), validation logic and nearby "context
words" *(not executed here)*. Even those miss things. For sensitive data, add a human review
of a sample.

> 🔒 Scrub **before** data leaves your control: before you send rows to a labelling service,
> to a hosted model for synthetic generation, or to a fine-tuning API. Keep the placeholders
> consistent (`[EMAIL]`, `[PHONE]`), so the model learns "an email goes here", not a real one.

### 3.7 Synthetic data: useful, but check every record

> 💬 **In plain words:** a model can write extra questions and answers for you. Some will be
> wrong, copied or too easy, so you check each one with code and throw the bad ones away.

When you don't have enough data, you can ask a model to write Q&A pairs from your documents.
This is **synthetic data**. The Self-Instruct paper (Wang et al., 2022) used this idea to build
a large instruction dataset from a small seed, filtering out invalid and too-similar items.

A model's output is a draft, not data. Our pipeline treats every generated record as
untrusted and runs it through five checks:

```
   1. PARSE        is the reply valid JSON at all?              → retry if not
   2. SCHEMA       Zod / Pydantic: question ≥ 10 chars, ends in "?", answer ≥ 3 chars
   3. GROUNDED     ≥ 50 % of the answer's content words appear in the source document
   4. NO LEAK      < 75 % of the answer's content words appear in the question
   5. NEW          not a duplicate of an existing row (same normalised key)
```

A scripted model (no API key) returned one non-JSON reply, then 7 items. Measured:

```
   attempt 1: not JSON → retried
   s1  ✅ accepted        "What is recursion?"
   s2  ✅ accepted        "What does a base case do?"
   s3  schema: answer missing
   s4  ungrounded         "A mathematician invented it in 1931."  ← not in the document
   s5  answer-leak        Q: "Why does a recursive function need a base case that stops
                              the calls?"  A: "A base case stops the calls."
   s6  duplicate          same as s1
   s7  schema: question too short ("stack")
   synthetic: 2 of 7 accepted
```

Structured output (Day 06) would fix s3 and s7 at generation time. It can't fix s4, s5 or s6:
the *shape* is right, but the *content* is wrong. That is why content checks matter.

The **answer-leak** check deserves attention. A question that contains its own answer is
trivially easy. Such questions make a test set look solved, and they teach a fine-tune to copy
from the question.

**The risks, in plain words:**

- **Model collapse.** Shumailov et al. (Nature, 2024) found that training models on
  model-generated data, generation after generation, causes "irreversible defects": the rare
  cases (the "tails") of the original data disappear. Keep human data in the mix, and tag
  every row's origin so you can measure the share.
- **Bias copying.** The generator's habits — favourite phrasings, topics, blind spots — become
  your data's habits. A model that writes "easy" questions makes an easy test.
- **Eval contamination.** If synthetic rows built from a document end up in training, and
  human questions about the same document end up in test, you have leaked that document. Our
  rule: synthetic rows **follow their source document** across the split, and **never go into
  the test set or the golden set**.

> 🎯 Tag each synthetic row: `origin: "synthetic"`, plus the source document. Then you can count
> it, filter it, or remove it later. Day 25's advice stands: 20–50 real questions beat 1,000
> synthetic ones for testing.

### 3.8 Splits and leakage

> 💬 **In plain words:** when you split data into "learn from" and "test on", near-copies must
> stay on the same side. Otherwise the test checks memory, not skill.

Most tutorials split **record by record**: shuffle, then take 25 % for test. That is fine
when every record is independent. Ours are not. Questions from the same lecture note are
related, and near-copies may still be hiding.

To see the damage, we skipped near-dedupe (17 rows, near-copies inside) and split by record:

```
   seed "qbank", split by record:  11 train / 6 test   leaks: r18~r20
   seed "qbank", split by source:  10 train / 7 test   leaks: none
```

`r18~r20` means test row r18 has a near-copy, r20, in training. One seed proves nothing, so we
ran 100 seeds:

```
   split by record   → leaked in 79 of 100 seeds
   split by source   → leaked in  0 of 100 seeds
```

**Split by group** means: pick a group key (here the source document), then put *whole groups*
on one side. Any near-copies inside a group can't cross the wall.

Group splits have a cost: the sizes are **lumpy**. With only 7 groups, you can't hit exactly
25 %. We measured two ways to do it:

```
   hash each group into a bucket (like a record split)  → test set EMPTY in 16 of 100 seeds
   sort groups by hash, add groups until test ≥ 25 %   → test size 5–8 of 17, never empty
```

The second method is what our code uses.

> ⚠️ Group by something that keeps copies together. "Source document" works when copies come
> from the same document. Copies can also cross documents (the same note pasted into two
> places). The safest order is: **dedupe first, then group split, then run a leak check
> anyway**. For logs from production, a **time split** (train on older data, test on newer)
> is also common, because it matches how the model will be used.

### 3.9 Golden sets and labelling: do people agree?

> 💬 **In plain words:** a golden set is a small, trusted test that never changes by accident.
> Before you trust its labels, check that two people would give the same labels.

A **golden set** is your highest-trust evaluation data. It is the reference shelf in the
library. It is small: Day 25 suggests starting with 20–50 real questions. It is checked by
people, frozen and versioned. It is **never** used for training, or as few-shot examples in
prompts. Build it from the test split, plus real
production failures (Day 25 §3.5). Mark each item with the facts a correct answer must contain.

Labels need **labelling guidelines**: a short written rulebook, so that different people label
the same way. For StudyBuddy:

```
   GOOD    correct, answers the question asked, ≤ 3 sentences, no personal data
   BAD     wrong, off-topic, or missing a fact the question needs
   when unsure: label BAD and add a note — unsure items become guideline updates
```

Then measure **inter-annotator agreement**: give the same items to two labellers and compare.
The obvious measure is **percent agreement**. It has a trap. Measured on 12 answers labelled
G (good) or B (bad):

```
   Ana   G G G B G G B G G G B G
   Ben   G G B B G G G G G B B G       agree = 0.750   chance = 0.583   kappa = 0.400
   lazy  G G G G G G G G G G G G       agree = 0.750   chance = 0.750   kappa = 0.000
```

The "lazy" labeller says "good" to everything, and **still agrees with Ana 75 % of the time**.
Most answers are good, so agreeing by luck is easy.

**Cohen's kappa** removes that luck:

```
   kappa = (observed agreement − chance agreement) / (1 − chance agreement)

   chance agreement = P(both say G by luck) + P(both say B by luck)
   Ana vs Ben:  (9/12 × 8/12) + (3/12 × 4/12) = 0.500 + 0.083 = 0.583
   kappa        = (0.750 − 0.583) / (1 − 0.583) = 0.400
```

Kappa is 1 for perfect agreement and 0 for "no better than luck". The lazy labeller scores
**0.000**. Our values match scikit-learn's `cohen_kappa_score` (0.4 and 0.0, verified).
A common reading scale (Landis & Koch, 1977) calls 0.21–0.40 "fair" and 0.61–0.80
"substantial". The authors themselves called the bands arbitrary, so treat them as a rough
guide. Low kappa usually means **the guidelines are unclear**, not that people are careless.
Fix the guidelines, then label again.

### 3.10 Versioning and dataset cards

> 💬 **In plain words:** give each finished dataset a fingerprint and a short description, so
> anyone can check they have exactly the same data and know how it was made.

A model result is only meaningful if you know which data produced it. So every dataset you
train or test on gets:

1. **A file hash** — SHA-256 of the exact bytes. If one character changes, the hash changes.
2. **A dataset card** — a small file with the name, version, row counts at every stage, the
   split rule and seed, the PII policy and its known limits. Gebru et al. proposed this idea as
   "Datasheets for Datasets" (2018). Hugging Face calls it a **dataset card**: the `README.md`
   of a dataset repository.

Our run, in both languages:

```
   train.jsonl   11 rows   sha256 f5ce2d97fb00603e…
   test.jsonl     5 rows   sha256 d65a8acc6963b6a2…
```

**The JavaScript and Python pipelines produced byte-identical files and the same hashes.**
That only happened after fixing three ways the same data can produce different bytes
(verified):

| Same rows, different bytes | Hash of `train.jsonl` |
|---|---|
| ✅ compact JSON, real UTF-8, `\n` line endings (both languages) | `f5ce2d97fb00603e` |
| ❌ Python `json.dumps(r)` defaults: spaces after `,` `:` and `—` for "—" | `137157cf64c8808d` |
| ❌ compact, but `ensure_ascii=True` (the default) | `42135915b804f360` |
| ❌ Python `open(..., "w")` on Windows without `newline="\n"` (11 CRLF line ends) | `ed56a103e7960640` |

Key order matters too. The same row with its keys in a different order hashed to
`99b76ef5cb891e95` instead of `aa0a8f32f13acf6d`, in both languages.

> 💡 Tools such as DVC or Hugging Face dataset repositories store versions for you. The idea
> underneath is the same: content hash + description. Start with the hash and the card; add a
> tool when the data gets big.

---

## 4. Code — JavaScript

One file, `dataset.js`, built section by section. Each section adds to the end of the file.
Run it with `node dataset.js` after each step.

```bash
mkdir d32 && cd d32
npm init -y && npm pkg set type=module
npm install @langchain/core zod          # verified: @langchain/core 1.2.17, zod 4.6.5
```

### 4.1 The raw data, and loading it

Save this as `studybuddy-raw.jsonl` (one JSON object per line — the **JSONL** format). It has
planted problems: copies, junk, a Spanish row, and personal data. Both languages read this
same file.

```json
{"id": "r01", "source": "http", "question": "What does HTTPS add to HTTP?", "answer": "HTTPS adds TLS encryption, so traffic cannot be read or changed in transit."}
{"id": "r02", "source": "http", "question": "  what does HTTPS add to HTTP?  ", "answer": "HTTPS adds TLS encryption,  so traffic cannot be read or changed in transit."}
{"id": "r03", "source": "http", "question": "What does HTTPS add on top of HTTP?", "answer": "HTTPS adds TLS encryption so traffic can't be read or changed in transit."}
{"id": "r04", "source": "http", "question": "Which port does HTTPS use by default?", "answer": "Port 443."}
{"id": "r05", "source": "recursion", "question": "What must every recursive function have?", "answer": "A base case that stops the recursion."}
{"id": "r06", "source": "recursion", "question": "What must every recursive function have?", "answer": "A base case that stops the recursion."}
{"id": "r07", "source": "recursion", "question": "What happens if a recursive function has no base case?", "answer": "It keeps calling itself until the call stack overflows."}
{"id": "r08", "source": "recursion", "question": "ok", "answer": "yes"}
{"id": "r09", "source": "big-o", "question": "What is the time complexity of binary search?", "answer": "O(log n) — each step halves the search range."}
{"id": "r10", "source": "big-o", "question": "What's the time complexity of a binary search?", "answer": "O(log n) — every step halves the search range."}
{"id": "r11", "source": "big-o", "question": "¿Cuál es la complejidad de la búsqueda binaria?", "answer": "O(log n), porque cada paso divide el rango a la mitad."}
{"id": "r12", "source": "sql", "question": "What does a SQL JOIN do?", "answer": "It combines rows from two tables using a related column."}
{"id": "r13", "source": "sql", "question": "Click here to subscribe to our newsletter!", "answer": "Cookie settings | All rights reserved."}
{"id": "r14", "source": "sql", "question": "What is a primary key?", "answer": "A column whose value uniquely identifies each row. Questions? Email ayesha.khan@example.com."}
{"id": "r15", "source": "git", "question": "What does git commit do?", "answer": "It saves a snapshot of the staged changes to the repository history. Notes last updated 2026-03-14."}
{"id": "r16", "source": "git", "question": "How do I undo my last commit but keep the changes?", "answer": "Run git reset --soft HEAD~1. Stuck? Call +44 7700 900123."}
{"id": "r17", "source": "git", "question": "What is a merge conflict?", "answer": "Two branches changed the same lines and git cannot choose. Ring 020 7946 0958 or (555) 010-4477."}
{"id": "r18", "source": "tcp", "question": "What is the difference between TCP and UDP?", "answer": "TCP is reliable and ordered; UDP is faster but can lose packets."}
{"id": "r19", "source": "tcp", "question": "What is the TCP three-way handshake?", "answer": "SYN, SYN-ACK, ACK: the client and server agree to open a connection."}
{"id": "r20", "source": "tcp", "question": "What is the difference between TCP and UDP", "answer": "TCP is reliable and ordered, UDP is faster but may lose packets."}
{"id": "r21", "source": "git", "question": "What does git stash do?", "answer": "It shelves uncommitted changes so you can switch branches. Ask Ayesha Khan: ayesha dot khan at example dot com."}
{"id": "r22", "source": "sql", "question": "Ｗｈａｔ ｄｏｅｓ ａ ＳＱＬ ＪＯＩＮ ｄｏ？", "answer": "It combines rows from two tables using a related column."}
{"id": "r23", "source": "big-o", "question": "What is Big O?", "answer": "Big O Big O Big O Big O Big O Big O Big O Big O Big O Big O"}
{"id": "r24", "source": "dns", "question": "What does DNS do?", "answer": "It translates a domain name such as example.com into an IP address."}
```

> 🔒 The email and phone numbers are fake, from reserved example ranges. Never put real
> personal data in test fixtures.

```js
// dataset.js — run with: node dataset.js
import { readFileSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";

// ── 4.1 load ────────────────────────────────────────────────────────────────
const sha256 = (s) => createHash("sha256").update(s, "utf8").digest("hex");
const raw = readFileSync("studybuddy-raw.jsonl", "utf8")
  .trim().split("\n").map((line) => JSON.parse(line));
console.log("raw records:", raw.length);
// raw records: 24
```

### 4.2 Clean, then exact de-duplication

```js
// ── 4.2 clean, then exact de-duplication ───────────────────────────────────
const clean = (s) => s.normalize("NFKC").replace(/\s+/g, " ").trim();
const key = (r) => `${r.question} || ${r.answer}`.toLowerCase();   // what "the same" means

function exactDedupe(records, keyFn) {
  const seen = new Map();                          // hash → id of the first copy
  const kept = [], dropped = [];
  for (const r of records) {
    const h = sha256(keyFn(r)).slice(0, 12);
    if (seen.has(h)) dropped.push(`${r.id}=${seen.get(h)}`);
    else { seen.set(h, r.id); kept.push(r); }
  }
  return { kept, dropped };
}

const naive = exactDedupe(raw, (r) => `${r.question} || ${r.answer}`);   // no cleaning
console.log("exact, raw text:   ", naive.kept.length, "kept · dropped", naive.dropped);

const cleaned = raw.map((r) => ({ ...r, question: clean(r.question), answer: clean(r.answer) }));
const exact = exactDedupe(cleaned, key);
console.log("exact, normalised: ", exact.kept.length, "kept · dropped", exact.dropped);
console.log("r22 after NFKC:", JSON.stringify(cleaned[21].question));
```

Output:

```text
exact, raw text:    23 kept · dropped [ 'r06=r05' ]
exact, normalised:  21 kept · dropped [ 'r02=r01', 'r06=r05', 'r22=r12' ]
r22 after NFKC: "What does a SQL JOIN do?"
```

The stored record keeps its original casing (`clean` doesn't lower-case). Only the comparison
`key` is lower-cased. The `dropped` list says which row each copy matched, so a person can
check it.

### 4.3 Near-duplicates: shingles and Jaccard

```js
// ── 4.3 near-duplicates: shingles + Jaccard ────────────────────────────────
function shingles(text, k = 5) {
  const out = new Set();
  for (let i = 0; i + k <= text.length; i++) out.add(text.slice(i, i + k));
  return out;
}
function jaccard(a, b) {
  let inter = 0;
  for (const x of a) if (b.has(x)) inter++;
  return inter / (a.size + b.size - inter);
}

const recs = exact.kept;
const pairs = [];
for (let i = 0; i < recs.length; i++)
  for (let j = i + 1; j < recs.length; j++)
    pairs.push([recs[i].id, recs[j].id, jaccard(shingles(key(recs[i])), shingles(key(recs[j])))]);
pairs.sort((a, b) => b[2] - a[2]);
console.log("pairs compared:", pairs.length);
for (const [a, b, j] of pairs.slice(0, 6)) console.log(`  ${a}–${b}  J=${j.toFixed(3)}`);

function nearDedupe(records, threshold = 0.5) {
  const kept = [], dropped = [];
  for (const r of records) {
    const s = shingles(key(r));
    const twin = kept.find((k) => jaccard(s, shingles(key(k))) >= threshold);
    if (twin) dropped.push(`${r.id}~${twin.id}`);
    else kept.push(r);
  }
  return { kept, dropped };
}
const near = nearDedupe(exact.kept);
console.log("near-dedupe @0.5:", near.kept.length, "kept · dropped", near.dropped);
```

Output:

```text
pairs compared: 210
  r18–r20  J=0.731
  r09–r10  J=0.670
  r01–r03  J=0.669
  r05–r07  J=0.183
  r15–r21  J=0.126
  r12–r15  J=0.098
near-dedupe @0.5: 18 kept · dropped [ 'r03~r01', 'r10~r09', 'r20~r18' ]
```

`nearDedupe` keeps the **first** row of each near-copy group. If you prefer the longest or the
newest row, sort the records before you call it.

> ⚠️ `text.slice` in JavaScript counts UTF-16 units, not characters. An emoji is two units, so
> a shingle can cut it in half. Measured: `"ab🎉cd"` has length 6 in JS and 5 in Python, and
> its 3-shingles differ. Use `Array.from(text)` if your data has emoji. Our data has none.

### 4.4 MinHash signatures

```js
// ── 4.4 MinHash: estimate Jaccard from small signatures ─────────────────────
const md5int = (s) => parseInt(createHash("md5").update(s, "utf8").digest("hex").slice(0, 8), 16);
function minhash(set, n = 64) {
  const sig = [];
  for (let i = 0; i < n; i++) {                    // n "different" hash functions:
    let m = Infinity;                              // md5 of "i:shingle" for i = 0 … n−1
    for (const x of set) m = Math.min(m, md5int(`${i}:${x}`));
    sig.push(m);
  }
  return sig;
}
const estimate = (a, b) => a.filter((v, i) => v === b[i]).length / a.length;
const byId = Object.fromEntries(exact.kept.map((r) => [r.id, r]));
for (const [a, b, j] of [...pairs.slice(0, 4), pairs[20], pairs.at(-1)]) {
  const est = estimate(minhash(shingles(key(byId[a]))), minhash(shingles(key(byId[b]))));
  console.log(`  ${a}–${b}  exact=${j.toFixed(3)}  minhash(64)=${est.toFixed(3)}`);
}
```

Output:

```text
  r18–r20  exact=0.731  minhash(64)=0.703
  r09–r10  exact=0.670  minhash(64)=0.656
  r01–r03  exact=0.669  minhash(64)=0.734
  r05–r07  exact=0.183  minhash(64)=0.109
  r03–r24  exact=0.051  minhash(64)=0.031
  r13–r24  exact=0.000  minhash(64)=0.000
```

A real system stores the signature (64 numbers) per record, instead of the full shingle set,
and uses LSH bands (§3.4) to pick candidate pairs. Libraries exist for this. The point here is
to see that the estimate tracks the true value.

### 4.5 Quality filters

```js
// ── 4.5 quality filters ─────────────────────────────────────────────────────
const STOP = new Set(("the a an is are was what which how why when does do of to in on for " +
  "and or it that this with by can use my i you if be so from into has have but not your").split(" "));
const words = (t) => t.toLowerCase().match(/[\p{L}\p{N}]+/gu) ?? [];
const BOILERPLATE = /click here|subscribe|cookie|all rights reserved|lorem ipsum/i;   // no "g"!

function qualityIssue(r) {
  const text = `${r.question} ${r.answer}`;
  const w = words(text);
  if (BOILERPLATE.test(text)) return "boilerplate";
  if (w.length < 6) return "too-short";
  if (new Set(w).size / w.length < 0.5) return "repetitive";
  if (w.filter((x) => STOP.has(x)).length / w.length < 0.15) return "not-english";
  return null;
}
const rejected = near.kept.filter(qualityIssue).map((r) => `${r.id}:${qualityIssue(r)}`);
const good = near.kept.filter((r) => !qualityIssue(r));
console.log("quality:", good.length, "kept · rejected", rejected);
```

Output:

```text
quality: 14 kept · rejected [
  'r08:too-short',
  'r11:not-english',
  'r13:boilerplate',
  'r23:repetitive'
]
```

> ⚠️ Don't add the `g` flag to a regex you call `.test()` on. A `g` regex remembers where its
> last match ended (`lastIndex`) and starts the next search there. Measured with `/…/gi` on
> four boilerplate strings: `[true, true, false, true]` — the third was missed.

### 4.6 PII scrubbing

```js
// ── 4.6 PII scrubbing ───────────────────────────────────────────────────────
const PII = [
  ["EMAIL", /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g],
  ["PHONE", /\+?\(?\d[\d\s().-]{7,}\d/g],
];
function scrub(text) {
  const found = [];
  for (const [label, re] of PII)
    text = text.replace(re, (m) => { found.push(`${label}:${m}`); return `[${label}]`; });
  return { text, found };
}
const scrubbed = good.map((r) => {
  const { text, found } = scrub(r.answer);
  if (found.length) console.log(`  ${r.id}`, found, "→", text);
  return { ...r, answer: text };
});
console.log("  r21 →", scrubbed.find((r) => r.id === "r21").answer);
```

Output:

```text
  r14 [ 'EMAIL:ayesha.khan@example.com' ] → A column whose value uniquely identifies each row. Questions? Email [EMAIL].
  r15 [ 'PHONE:2026-03-14' ] → It saves a snapshot of the staged changes to the repository history. Notes last updated [PHONE].
  r16 [ 'PHONE:+44 7700 900123' ] → Run git reset --soft HEAD~1. Stuck? Call [PHONE].
  r17 [ 'PHONE:020 7946 0958', 'PHONE:(555) 010-4477' ] → Two branches changed the same lines and git cannot choose. Ring [PHONE] or [PHONE].
  r21 → It shelves uncommitted changes so you can switch branches. Ask Ayesha Khan: ayesha dot khan at example dot com.
```

Here `.replace` with a `g` regex is correct: it replaces every match. Only `.test` and `.exec`
have the `lastIndex` problem. We scrub answers only, because our questions have no PII. In real
data, scrub every text field.

### 4.7 Synthetic Q&A with a scripted model

The model below is `FakeListChatModel`: it returns its scripted replies in order, so the code
runs with no API key. To use a real model, swap in `new ChatGroq({ model:
"openai/gpt-oss-120b" })` — the rest stays the same *(not executed here)*.

```js
// ── 4.7 synthetic Q&A: generate, validate, reject ──────────────────────────
import { FakeListChatModel } from "@langchain/core/utils/testing";   // imports are hoisted,
import { z } from "zod";                                              // so this is fine here

const DOC = "Recursion is when a function calls itself. Every recursive function needs a base " +
  "case that stops the calls. Without a base case the function keeps calling itself until " +
  "the call stack overflows. Each call waits on the stack until the calls above it return.";

const scriptedReplies = [
  "Sure! Here are five questions about recursion:\n1. What is recursion?",   // not JSON
  JSON.stringify([
    { question: "What is recursion?", answer: "When a function calls itself." },
    { question: "What does a base case do?", answer: "It stops the recursive calls." },
    { question: "What happens without a base case?" },
    { question: "Who invented recursion?", answer: "A mathematician invented it in 1931." },
    { question: "Why does a recursive function need a base case that stops the calls?",
      answer: "A base case stops the calls." },
    { question: "What is recursion?", answer: "When a function calls itself." },
    { question: "stack", answer: "Each call waits on the stack." },
  ]),
];
const model = new FakeListChatModel({ responses: scriptedReplies });   // swap for ChatGroq

const QA = z.object({
  question: z.string().min(10).endsWith("?"),
  answer: z.string().min(3),
});

async function generate(doc, attempts = 2) {
  for (let t = 1; t <= attempts; t++) {
    const msg = await model.invoke([
      ["system", "Write question–answer pairs as a JSON array of {question, answer}. " +
                 "Use only facts from the document. Never put the answer in the question."],
      ["human", doc],
    ]);
    try { return JSON.parse(msg.content); }
    catch (e) { console.log(`attempt ${t}: not JSON → ${e.message.slice(0, 45)}…`); }
  }
  return [];
}

const contentWords = (t) => words(t).filter((w) => w.length >= 4 && !STOP.has(w));
const share = (ws, pool) => ws.filter((w) => pool.has(w)).length / Math.max(ws.length, 1);

function checkSynthetic(item, doc, seenKeys) {
  const parsed = QA.safeParse(item);
  if (!parsed.success) return `schema: ${parsed.error.issues[0].path.join(".")} ${parsed.error.issues[0].message}`;
  const { question, answer } = parsed.data;
  const ans = contentWords(answer);
  if (share(ans, new Set(words(doc))) < 0.5) return "ungrounded";        // facts not in the doc
  if (share(ans, new Set(words(question))) >= 0.75) return "answer-leak"; // question gives it away
  const k = key({ question: clean(question), answer: clean(answer) });
  if (seenKeys.has(k)) return "duplicate";
  seenKeys.add(k);
  return null;
}

const items = await generate(DOC);
const seenKeys = new Set(scrubbed.map(key));
const accepted = [];
items.forEach((item, i) => {
  const problem = checkSynthetic(item, DOC, seenKeys);
  console.log(`  s${i + 1}`, problem ?? "✅ accepted");
  if (!problem) accepted.push({ id: `s${i + 1}`, source: "recursion", origin: "synthetic",
                                question: clean(item.question), answer: clean(item.answer) });
});
console.log(`synthetic: ${accepted.length} of ${items.length} accepted`);
```

Output (Zod 4 messages):

```text
attempt 1: not JSON → Unexpected token 'S', "Sure! Here"... is not …
  s1 ✅ accepted
  s2 ✅ accepted
  s3 schema: answer Invalid input: expected string, received undefined
  s4 ungrounded
  s5 answer-leak
  s6 duplicate
  s7 schema: question Too small: expected string to have >=10 characters
synthetic: 2 of 7 accepted
```

`seenKeys` starts with the **existing** rows, so a synthetic copy of a human-written row is
rejected too. The `origin` field marks the row as synthetic for ever.

> 💡 The grounding check is word overlap, so it is rough. It can pass a wrong answer that
> reuses the document's words. For important data, add an LLM judge (Day 25 §3.6) or a human
> review of a sample. Word overlap is the cheap first filter.

### 4.8 Split by group, and check for leaks

```js
// ── 4.8 split, and catch leakage ────────────────────────────────────────────
const bucket = (seed, k) => parseInt(sha256(`${seed}:${k}`).slice(0, 8), 16) % 100;   // 0–99

function splitByRecord(records, seed, testPct = 25) {         // the usual random split
  const train = [], test = [];
  for (const r of records) (bucket(seed, r.id) < testPct ? test : train).push(r);
  return { train, test };
}

function splitByGroup(records, seed, groupOf, testPct = 25) { // whole groups, never halves
  const h = (g) => sha256(`${seed}:${g}`);
  const groups = [...new Set(records.map(groupOf))].sort((a, b) => (h(a) < h(b) ? -1 : 1));
  const testGroups = new Set();
  let testRows = 0;
  for (const g of groups) {                                    // add groups until ≥ testPct
    if (testRows >= (records.length * testPct) / 100) break;
    testGroups.add(g);
    testRows += records.filter((r) => groupOf(r) === g).length;
  }
  const train = [], test = [];
  for (const r of records) (testGroups.has(groupOf(r)) ? test : train).push(r);
  return { train, test };
}

function leaks(train, test, threshold = 0.5) {                // near-duplicates across the wall
  const out = [];
  for (const t of test) {
    const s = shingles(key(t));
    const twin = train.find((r) => jaccard(s, shingles(key(r))) >= threshold);
    if (twin) out.push(`${t.id}~${twin.id}`);
  }
  return out;
}

// the mistake: near-duplicates still in the data, split record by record
const leaky = exact.kept.filter((r) => !qualityIssue(r));      // 17 rows, near-dups inside
const a1 = splitByRecord(leaky, "qbank");
const b1 = splitByGroup(leaky, "qbank", (r) => r.source);
console.log("by record:", a1.train.length, "/", a1.test.length, "leaks", leaks(a1.train, a1.test));
console.log("by source:", b1.train.length, "/", b1.test.length, "leaks", leaks(b1.train, b1.test));

// one seed proves nothing — try 100
let recordLeaked = 0, groupLeaked = 0, emptyTest = 0;
const sizes = [];
for (let i = 0; i < 100; i++) {
  const seed = `seed-${i}`;
  const a = splitByRecord(leaky, seed);
  const b = splitByGroup(leaky, seed, (r) => r.source);
  if (leaks(a.train, a.test).length) recordLeaked++;
  if (leaks(b.train, b.test).length) groupLeaked++;
  if (!leaky.some((r) => bucket(seed, r.source) < 25)) emptyTest++;   // hashing each group
  sizes.push(b.test.length);
}
console.log(`100 seeds → leaked: by record ${recordLeaked}, by group ${groupLeaked}`);
console.log(`hash-each-group test set EMPTY in ${emptyTest} of 100 seeds`);
console.log(`group-split test size: ${Math.min(...sizes)}–${Math.max(...sizes)} of ${leaky.length}`);

// the real split: human-written rows only; synthetic rows follow their source document
const real = splitByGroup(scrubbed, "qbank", (r) => r.source);
const testSources = new Set(real.test.map((r) => r.source));
const synthTrain = accepted.filter((r) => !testSources.has(r.source));
const train = [...real.train, ...synthTrain];
const test = real.test;                                         // never synthetic
console.log("train", train.length, "· test", test.length, "· test sources", [...testSources],
  "· synthetic kept", synthTrain.length, "of", accepted.length, "· leaks", leaks(train, test));
```

Output:

```text
by record: 11 / 6 leaks [ 'r18~r20' ]
by source: 10 / 7 leaks []
100 seeds → leaked: by record 79, by group 0
hash-each-group test set EMPTY in 16 of 100 seeds
group-split test size: 5–8 of 17
train 11 · test 5 · test sources [ 'http', 'tcp', 'dns' ] · synthetic kept 2 of 2 · leaks []
```

We split with a **hash of a seed**, not `Math.random()`. The split is the same on every run and
in both languages, so a test row can't quietly move into training next week. With this seed,
the recursion document is in training, so both synthetic rows are kept. Had it landed in
test, both would be dropped. That is the rule working, not a bug.

### 4.9 Agreement and Cohen's kappa

```js
// ── 4.9 do two labellers agree? ─────────────────────────────────────────────
function agreement(a, b) {
  const n = a.length;
  const observed = a.filter((x, i) => x === b[i]).length / n;
  const labels = [...new Set([...a, ...b])];
  const chance = labels.reduce((sum, l) =>
    sum + (a.filter((x) => x === l).length / n) * (b.filter((x) => x === l).length / n), 0);
  return { observed, chance, kappa: (observed - chance) / (1 - chance) };
}
const fmt = ({ observed, chance, kappa }) =>
  `agree=${observed.toFixed(3)} chance=${chance.toFixed(3)} kappa=${kappa.toFixed(3)}`;
const ana  = "G G G B G G B G G G B G".split(" ");     // G = good answer, B = bad answer
const ben  = "G G B B G G G G G B B G".split(" ");
const lazy = "G G G G G G G G G G G G".split(" ");     // says "good" to everything
console.log("Ana vs Ben: ", fmt(agreement(ana, ben)));
console.log("Ana vs lazy:", fmt(agreement(ana, lazy)));
```

Output:

```text
Ana vs Ben:  agree=0.750 chance=0.583 kappa=0.400
Ana vs lazy: agree=0.750 chance=0.750 kappa=0.000
```

> ⚠️ If both labellers use only one label (everyone says "G"), chance = 1 and kappa divides by
> zero: JS returns `NaN`, Python raises `ZeroDivisionError` (both verified). It means your
> sample has no hard cases. Add some.

### 4.10 Write, hash, and describe the dataset

```js
// ── 4.10 version it: write, hash, describe ─────────────────────────────────
const toJsonl = (rows) => rows.map((r) => JSON.stringify(r)).join("\n") + "\n";
const card = {
  name: "studybuddy-qbank",
  version: "1.0.0",
  files: {},
  counts: { raw: raw.length, exactDedupe: exact.kept.length, nearDedupe: near.kept.length,
            quality: good.length, syntheticAccepted: accepted.length,
            train: train.length, test: test.length },
  split: { by: "source", seed: "qbank", testPct: 25, testGroups: [...testSources] },
  pii: "regex scrub of emails and phone numbers; names and spelled-out emails are NOT caught",
};
for (const [name, rows] of Object.entries({ "train.jsonl": train, "test.jsonl": test })) {
  const text = toJsonl(rows);
  writeFileSync(name, text);                                   // UTF-8, "\n" line endings
  card.files[name] = { rows: rows.length, sha256: sha256(text).slice(0, 16) };
}
writeFileSync("dataset-card.json", JSON.stringify(card, null, 2) + "\n");
console.log(card.files);
console.log("re-read train.jsonl:", sha256(readFileSync("train.jsonl", "utf8")).slice(0, 16));
```

Output:

```text
{
  'train.jsonl': { rows: 11, sha256: 'f5ce2d97fb00603e' },
  'test.jsonl': { rows: 5, sha256: 'd65a8acc6963b6a2' }
}
re-read train.jsonl: f5ce2d97fb00603e
```

`dataset-card.json` (verified, identical from both languages):

```json
{
  "name": "studybuddy-qbank",
  "version": "1.0.0",
  "files": {
    "train.jsonl": { "rows": 11, "sha256": "f5ce2d97fb00603e" },
    "test.jsonl": { "rows": 5, "sha256": "d65a8acc6963b6a2" }
  },
  "counts": { "raw": 24, "exactDedupe": 21, "nearDedupe": 18, "quality": 14,
              "syntheticAccepted": 2, "train": 11, "test": 5 },
  "split": { "by": "source", "seed": "qbank", "testPct": 25,
             "testGroups": ["http", "tcp", "dns"] },
  "pii": "regex scrub of emails and phone numbers; names and spelled-out emails are NOT caught"
}
```

*(The real file has one value per line; it is shown compacted here.)* `testGroups` is
recorded on purpose. In the next version, those groups stay in test, even if new groups are
added (§6.2).

---

## 5. Code — Python

The same pipeline in `dataset.py`, reading the same `studybuddy-raw.jsonl`. It uses only the
standard library, plus `langchain-core` and `pydantic` for §5.7. Every output below matched the
JavaScript output (list formatting aside) — including all hashes.

```bash
pip install langchain-core pydantic       # verified: langchain-core 1.6.7, pydantic 2.13.5
```

### 5.1 Load

```python
# dataset.py — run with: python dataset.py
import hashlib, json, re, unicodedata

# ── 5.1 load ────────────────────────────────────────────────────────────────
def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

with open("studybuddy-raw.jsonl", encoding="utf-8") as f:
    raw = [json.loads(line) for line in f if line.strip()]
print("raw records:", len(raw))
# raw records: 24
```

> 🪟 Always pass `encoding="utf-8"`. On this Windows machine, Python 3.14's default was the
> system code page `cp1252` (verified with `locale.getencoding()`), which garbles "—", "¿"
> and the full-width row.

### 5.2 Clean, then exact de-duplication

```python
# ── 5.2 clean, then exact de-duplication ───────────────────────────────────
def clean(s: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", s)).strip()

def key(r: dict) -> str:                       # what "the same" means
    return f"{r['question']} || {r['answer']}".lower()

def exact_dedupe(records, key_fn):
    seen, kept, dropped = {}, [], []           # seen: hash → id of the first copy
    for r in records:
        h = sha256(key_fn(r))[:12]
        if h in seen:
            dropped.append(f"{r['id']}={seen[h]}")
        else:
            seen[h] = r["id"]
            kept.append(r)
    return kept, dropped

naive_kept, naive_dropped = exact_dedupe(raw, lambda r: f"{r['question']} || {r['answer']}")
print("exact, raw text:   ", len(naive_kept), "kept · dropped", naive_dropped)

cleaned = [{**r, "question": clean(r["question"]), "answer": clean(r["answer"])} for r in raw]
exact, exact_dropped = exact_dedupe(cleaned, key)
print("exact, normalised: ", len(exact), "kept · dropped", exact_dropped)
print("r22 after NFKC:", json.dumps(cleaned[21]["question"]))
# exact, raw text:    23 kept · dropped ['r06=r05']
# exact, normalised:  21 kept · dropped ['r02=r01', 'r06=r05', 'r22=r12']
# r22 after NFKC: "What does a SQL JOIN do?"
```

> ⚠️ Use `.lower()`, not `.casefold()`, if a JavaScript service must produce the same keys.
> Measured: `"Straße".casefold()` is `"strasse"`, while `.lower()` and JS `toLowerCase()` both
> give `"straße"`. Different keys mean different hashes.

### 5.3 Near-duplicates: shingles and Jaccard

```python
# ── 5.3 near-duplicates: shingles + Jaccard ────────────────────────────────
def shingles(text: str, k: int = 5) -> set[str]:
    return {text[i:i + k] for i in range(len(text) - k + 1)}

def jaccard(a: set, b: set) -> float:
    inter = len(a & b)
    return inter / (len(a) + len(b) - inter)

pairs = []
for i in range(len(exact)):
    for j in range(i + 1, len(exact)):
        pairs.append((exact[i]["id"], exact[j]["id"],
                      jaccard(shingles(key(exact[i])), shingles(key(exact[j])))))
pairs.sort(key=lambda p: -p[2])
print("pairs compared:", len(pairs))
for a, b, j in pairs[:6]:
    print(f"  {a}–{b}  J={j:.3f}")

def near_dedupe(records, threshold=0.5):
    kept, dropped = [], []
    for r in records:
        s = shingles(key(r))
        twin = next((k for k in kept if jaccard(s, shingles(key(k))) >= threshold), None)
        if twin:
            dropped.append(f"{r['id']}~{twin['id']}")
        else:
            kept.append(r)
    return kept, dropped

near, near_dropped = near_dedupe(exact)
print("near-dedupe @0.5:", len(near), "kept · dropped", near_dropped)
# pairs compared: 210 · top: r18–r20 0.731, r09–r10 0.670, r01–r03 0.669, r05–r07 0.183 …
# near-dedupe @0.5: 18 kept · dropped ['r03~r01', 'r10~r09', 'r20~r18']
```

Python's `set` operators (`a & b`) make Jaccard one line. Python strings index by code point,
so emoji are safe here (§4.3's warning is JS-only).

### 5.4 MinHash signatures

```python
# ── 5.4 MinHash: estimate Jaccard from small signatures ─────────────────────
def md5int(s: str) -> int:
    return int(hashlib.md5(s.encode("utf-8")).hexdigest()[:8], 16)

def minhash(items: set, n: int = 64) -> list[int]:
    return [min(md5int(f"{i}:{x}") for x in items) for i in range(n)]

def estimate(a: list, b: list) -> float:
    return sum(x == y for x, y in zip(a, b)) / len(a)

by_id = {r["id"]: r for r in exact}
for a, b, j in [*pairs[:4], pairs[20], pairs[-1]]:
    est = estimate(minhash(shingles(key(by_id[a]))), minhash(shingles(key(by_id[b]))))
    print(f"  {a}–{b}  exact={j:.3f}  minhash(64)={est:.3f}")
# r18–r20 exact=0.731 minhash(64)=0.703 · r01–r03 exact=0.669 minhash(64)=0.734 … (same as JS)
```

Because both languages use the same hash (`md5` of `"i:shingle"`), the signatures are
identical, number for number. Python's built-in `hash()` would not work: it changes between
runs unless you set `PYTHONHASHSEED` (verified: `hash('abc')` gave a different number in two
runs).

### 5.5 Quality filters

```python
# ── 5.5 quality filters ─────────────────────────────────────────────────────
STOP = set(("the a an is are was what which how why when does do of to in on for "
            "and or it that this with by can use my i you if be so from into has have but not your").split())
def words(t: str) -> list[str]:
    return re.findall(r"[^\W_]+", t.lower())        # letters and digits, any language
BOILERPLATE = re.compile(r"click here|subscribe|cookie|all rights reserved|lorem ipsum", re.I)

def quality_issue(r: dict) -> str | None:
    text = f"{r['question']} {r['answer']}"
    w = words(text)
    if BOILERPLATE.search(text):
        return "boilerplate"
    if len(w) < 6:
        return "too-short"
    if len(set(w)) / len(w) < 0.5:
        return "repetitive"
    if sum(x in STOP for x in w) / len(w) < 0.15:
        return "not-english"
    return None

rejected = [f"{r['id']}:{quality_issue(r)}" for r in near if quality_issue(r)]
good = [r for r in near if not quality_issue(r)]
print("quality:", len(good), "kept · rejected", rejected)
# quality: 14 kept · rejected ['r08:too-short', 'r11:not-english', 'r13:boilerplate', 'r23:repetitive']
```

`[^\W_]+` means "word characters except underscore". It matches the same words as JS
`[\p{L}\p{N}]+` on this data. Python's compiled regex has no `lastIndex`, so the §4.5 trap
can't happen: the same four strings gave `[True, True, True, True]`.

### 5.6 PII scrubbing

```python
# ── 5.6 PII scrubbing ───────────────────────────────────────────────────────
PII = [
    ("EMAIL", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("PHONE", re.compile(r"\+?\(?\d[\d\s().-]{7,}\d")),
]
def scrub(text: str):
    found = []
    for label, rx in PII:
        def repl(m, label=label):
            found.append(f"{label}:{m.group()}")
            return f"[{label}]"
        text = rx.sub(repl, text)
    return text, found

scrubbed = []
for r in good:
    text, found = scrub(r["answer"])
    if found:
        print(f"  {r['id']}", found, "→", text)
    scrubbed.append({**r, "answer": text})
print("  r21 →", next(r for r in scrubbed if r["id"] == "r21")["answer"])
# r14 ['EMAIL:ayesha.khan@example.com'] → … Email [EMAIL].
# r15 ['PHONE:2026-03-14'] → … Notes last updated [PHONE].        ← a date: false positive
# r16 ['PHONE:+44 7700 900123'] → … Stuck? Call [PHONE].
# r17 ['PHONE:020 7946 0958', 'PHONE:(555) 010-4477'] → … Ring [PHONE] or [PHONE].
# r21 → … Ask Ayesha Khan: ayesha dot khan at example dot com.   ← missed
```

`label=label` in `repl` freezes the current label inside the loop. Without it, every inner
function would see the last value of `label`.

### 5.7 Synthetic Q&A with a scripted model

`FakeListChatModel` is the Python twin of the JS fake. For a real model, use
`ChatGroq(model="openai/gpt-oss-120b")` from `langchain_groq` *(not executed here)*.

```python
# ── 5.7 synthetic Q&A: generate, validate, reject ──────────────────────────
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from pydantic import BaseModel, Field, ValidationError

DOC = ("Recursion is when a function calls itself. Every recursive function needs a base "
       "case that stops the calls. Without a base case the function keeps calling itself until "
       "the call stack overflows. Each call waits on the stack until the calls above it return.")

scripted_replies = [
    "Sure! Here are five questions about recursion:\n1. What is recursion?",   # not JSON
    json.dumps([
        {"question": "What is recursion?", "answer": "When a function calls itself."},
        {"question": "What does a base case do?", "answer": "It stops the recursive calls."},
        {"question": "What happens without a base case?"},
        {"question": "Who invented recursion?", "answer": "A mathematician invented it in 1931."},
        {"question": "Why does a recursive function need a base case that stops the calls?",
         "answer": "A base case stops the calls."},
        {"question": "What is recursion?", "answer": "When a function calls itself."},
        {"question": "stack", "answer": "Each call waits on the stack."},
    ]),
]
model = FakeListChatModel(responses=scripted_replies)          # swap for ChatGroq

class QA(BaseModel):
    question: str = Field(min_length=10, pattern=r"\?$")
    answer: str = Field(min_length=3)

def generate(doc: str, attempts: int = 2) -> list:
    for t in range(1, attempts + 1):
        msg = model.invoke([
            ("system", "Write question–answer pairs as a JSON array of {question, answer}. "
                       "Use only facts from the document. Never put the answer in the question."),
            ("human", doc),
        ])
        try:
            return json.loads(msg.content)
        except json.JSONDecodeError as e:
            print(f"attempt {t}: not JSON → {str(e)[:45]}…")
    return []

def content_words(t: str) -> list[str]:
    return [w for w in words(t) if len(w) >= 4 and w not in STOP]

def share(ws: list, pool: set) -> float:
    return sum(w in pool for w in ws) / max(len(ws), 1)

def check_synthetic(item: dict, doc: str, seen_keys: set) -> str | None:
    try:
        qa = QA.model_validate(item)
    except ValidationError as e:
        err = e.errors()[0]
        return f"schema: {'.'.join(map(str, err['loc']))} {err['msg']}"
    ans = content_words(qa.answer)
    if share(ans, set(words(doc))) < 0.5:
        return "ungrounded"                   # facts not in the doc
    if share(ans, set(words(qa.question))) >= 0.75:
        return "answer-leak"                  # the question gives it away
    k = key({"question": clean(qa.question), "answer": clean(qa.answer)})
    if k in seen_keys:
        return "duplicate"
    seen_keys.add(k)
    return None

items = generate(DOC)
seen_keys = {key(r) for r in scrubbed}
accepted = []
for i, item in enumerate(items, 1):
    problem = check_synthetic(item, DOC, seen_keys)
    print(f"  s{i}", problem or "✅ accepted")
    if not problem:
        accepted.append({"id": f"s{i}", "source": "recursion", "origin": "synthetic",
                         "question": clean(item["question"]), "answer": clean(item["answer"])})
print(f"synthetic: {len(accepted)} of {len(items)} accepted")
```

Output (Pydantic 2 messages — the words differ from Zod, the verdicts are the same):

```text
attempt 1: not JSON → Expecting value: line 1 column 1 (char 0)…
  s1 ✅ accepted
  s2 ✅ accepted
  s3 schema: answer Field required
  s4 ungrounded
  s5 answer-leak
  s6 duplicate
  s7 schema: question String should have at least 10 characters
synthetic: 2 of 7 accepted
```

### 5.8 Split by group, and check for leaks

```python
# ── 5.8 split, and catch leakage ────────────────────────────────────────────
def bucket(seed: str, k: str) -> int:                          # 0–99
    return int(sha256(f"{seed}:{k}")[:8], 16) % 100

def split_by_record(records, seed, test_pct=25):              # the usual random split
    train, test = [], []
    for r in records:
        (test if bucket(seed, r["id"]) < test_pct else train).append(r)
    return train, test

def split_by_group(records, seed, group_of, test_pct=25):     # whole groups, never halves
    groups = sorted({group_of(r) for r in records}, key=lambda g: sha256(f"{seed}:{g}"))
    test_groups, test_rows = set(), 0
    for g in groups:                                           # add groups until ≥ test_pct
        if test_rows >= len(records) * test_pct / 100:
            break
        test_groups.add(g)
        test_rows += sum(group_of(r) == g for r in records)
    train = [r for r in records if group_of(r) not in test_groups]
    test = [r for r in records if group_of(r) in test_groups]
    return train, test

def leaks(train, test, threshold=0.5):                         # near-duplicates across the wall
    out = []
    for t in test:
        s = shingles(key(t))
        twin = next((r for r in train if jaccard(s, shingles(key(r))) >= threshold), None)
        if twin:
            out.append(f"{t['id']}~{twin['id']}")
    return out

# the mistake: near-duplicates still in the data, split record by record
leaky = [r for r in exact if not quality_issue(r)]             # 17 rows, near-dups inside
tr, te = split_by_record(leaky, "qbank")
print("by record:", len(tr), "/", len(te), "leaks", leaks(tr, te))
tr, te = split_by_group(leaky, "qbank", lambda r: r["source"])
print("by source:", len(tr), "/", len(te), "leaks", leaks(tr, te))

# one seed proves nothing — try 100
record_leaked = group_leaked = empty_test = 0
sizes = []
for i in range(100):
    seed = f"seed-{i}"
    a_tr, a_te = split_by_record(leaky, seed)
    b_tr, b_te = split_by_group(leaky, seed, lambda r: r["source"])
    record_leaked += bool(leaks(a_tr, a_te))
    group_leaked += bool(leaks(b_tr, b_te))
    empty_test += not any(bucket(seed, r["source"]) < 25 for r in leaky)   # hashing each group
    sizes.append(len(b_te))
print(f"100 seeds → leaked: by record {record_leaked}, by group {group_leaked}")
print(f"hash-each-group test set EMPTY in {empty_test} of 100 seeds")
print(f"group-split test size: {min(sizes)}–{max(sizes)} of {len(leaky)}")

# the real split: human-written rows only; synthetic rows follow their source document
real_train, test = split_by_group(scrubbed, "qbank", lambda r: r["source"])
test_sources = list(dict.fromkeys(r["source"] for r in test))
synth_train = [r for r in accepted if r["source"] not in test_sources]
train = real_train + synth_train
print("train", len(train), "· test", len(test), "· test sources", test_sources,
      "· synthetic kept", len(synth_train), "of", len(accepted), "· leaks", leaks(train, test))
```

Output:

```text
by record: 11 / 6 leaks ['r18~r20']
by source: 10 / 7 leaks []
100 seeds → leaked: by record 79, by group 0
hash-each-group test set EMPTY in 16 of 100 seeds
group-split test size: 5–8 of 17
train 11 · test 5 · test sources ['http', 'tcp', 'dns'] · synthetic kept 2 of 2 · leaks []
```

`dict.fromkeys(...)` keeps the first-seen order, like a JS `Set`, so the card lists the groups
in the same order in both languages. scikit-learn's `GroupShuffleSplit` does a group split for
you too. We wrote our own so the JS and Python results match exactly.

### 5.9 Agreement and Cohen's kappa

```python
# ── 5.9 do two labellers agree? ─────────────────────────────────────────────
def agreement(a, b):
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b)) / n
    chance = sum((a.count(l) / n) * (b.count(l) / n) for l in set(a) | set(b))
    return observed, chance, (observed - chance) / (1 - chance)

def fmt(res):
    observed, chance, kappa = res
    return f"agree={observed:.3f} chance={chance:.3f} kappa={kappa:.3f}"

ana  = "G G G B G G B G G G B G".split()      # G = good answer, B = bad answer
ben  = "G G B B G G G G G B B G".split()
lazy = "G G G G G G G G G G G G".split()      # says "good" to everything
print("Ana vs Ben: ", fmt(agreement(ana, ben)))
print("Ana vs lazy:", fmt(agreement(ana, lazy)))
# Ana vs Ben:  agree=0.750 chance=0.583 kappa=0.400
# Ana vs lazy: agree=0.750 chance=0.750 kappa=0.000
```

Cross-check with scikit-learn (verified with scikit-learn 1.9.1):

```python
from sklearn.metrics import cohen_kappa_score
print(cohen_kappa_score(ana, ben), cohen_kappa_score(ana, lazy))   # 0.4 0.0
```

### 5.10 Write, hash, and describe the dataset

```python
# ── 5.10 version it: write, hash, describe ─────────────────────────────────
def to_jsonl(rows) -> str:
    return "".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n" for r in rows)

card = {
    "name": "studybuddy-qbank",
    "version": "1.0.0",
    "files": {},
    "counts": {"raw": len(raw), "exactDedupe": len(exact), "nearDedupe": len(near),
               "quality": len(good), "syntheticAccepted": len(accepted),
               "train": len(train), "test": len(test)},
    "split": {"by": "source", "seed": "qbank", "testPct": 25, "testGroups": test_sources},
    "pii": "regex scrub of emails and phone numbers; names and spelled-out emails are NOT caught",
}
for name, rows in {"train.jsonl": train, "test.jsonl": test}.items():
    text = to_jsonl(rows)
    with open(name, "w", encoding="utf-8", newline="\n") as f:   # newline="\n" matters on Windows
        f.write(text)
    card["files"][name] = {"rows": len(rows), "sha256": sha256(text)[:16]}
with open("dataset-card.json", "w", encoding="utf-8", newline="\n") as f:
    json.dump(card, f, indent=2)
    f.write("\n")
print(card["files"])
with open("train.jsonl", "rb") as f:
    print("re-read train.jsonl:", hashlib.sha256(f.read()).hexdigest()[:16])
# {'train.jsonl': {'rows': 11, 'sha256': 'f5ce2d97fb00603e'}, 'test.jsonl': {'rows': 5, 'sha256': 'd65a8acc6963b6a2'}}
# re-read train.jsonl: f5ce2d97fb00603e
```

Same hashes as JavaScript. `dataset-card.json` from this script was **byte-identical** to the
one from §4.10 (checked with `diff`). The three settings that make that true are
`ensure_ascii=False`, `separators=(",", ":")` and `newline="\n"` (§3.10's table shows what each
one changes).

### 5.11 The JS ↔ Python translation for today

| Task | JavaScript | Python |
|---|---|---|
| SHA-256 of text | `createHash("sha256").update(s, "utf8").digest("hex")` | `hashlib.sha256(s.encode("utf-8")).hexdigest()` |
| Unicode NFKC | `s.normalize("NFKC")` | `unicodedata.normalize("NFKC", s)` |
| Lower-case key (same result) | `toLowerCase()` | `.lower()` — not `.casefold()` |
| Collapse whitespace | `s.replace(/\s+/g, " ").trim()` | `re.sub(r"\s+", " ", s).strip()` |
| Words in any language | `t.match(/[\p{L}\p{N}]+/gu)` | `re.findall(r"[^\W_]+", t)` |
| Shingles | loop + `text.slice(i, i + k)` (UTF-16 units) | `{text[i:i+k] for i in …}` (code points) |
| Set intersection | loop with `b.has(x)` | `a & b` |
| Regex test, many strings | `/…/i` with `.test` — **no `g`** | `re.compile(…, re.I).search` (no state) |
| Replace all matches | `.replace(/…/g, fn)` | `rx.sub(fn, text)` |
| Scripted model | `FakeListChatModel` from `@langchain/core/utils/testing` | `FakeListChatModel` from `langchain_core.language_models.fake_chat_models` |
| Schema check | `z.object({...}).safeParse(item)` | `QA.model_validate(item)` + `except ValidationError` |
| "Ends with ?" | `z.string().endsWith("?")` | `Field(pattern=r"\?$")` |
| Bad JSON error | `Unexpected token 'S', "Sure! Here"... is not valid JSON` | `Expecting value: line 1 column 1 (char 0)` |
| Missing field message | `Invalid input: expected string, received undefined` | `Field required` |
| JSONL line | `JSON.stringify(r)` | `json.dumps(r, ensure_ascii=False, separators=(",", ":"))` |
| Write text file | `writeFileSync(name, text)` (writes `\n` as is) | `open(name, "w", encoding="utf-8", newline="\n")` |
| Keep insertion order, unique | `new Set(...)` | `dict.fromkeys(...)` |

---

## 6. Under the hood

### 6.1 What dedupe costs at scale

Exact dedupe is **one pass**: hash each row, look it up in a table. Its cost grows in step with
the number of rows. Near-dedupe by all pairs grows with the **square** of the rows: 210 pairs
for 21 rows, but about 5 × 10¹¹ for a million (§3.4).

MinHash + LSH turns that back into roughly one pass. Each row gets a signature (n hash
computations per shingle). Each band of the signature goes into a lookup table. Only rows that
share a band are compared. The price is accuracy. The standard error of a MinHash estimate is
about √(J(1 − J)/n). For J = 0.67 and n = 64 that is about **0.059**. Our largest measured
error at n = 64 was 0.074, close to that. More hash functions mean better estimates and more
compute.

> 💡 You rarely build this from scratch for big data. Python's `datasketch` library implements
> MinHash and LSH *(not executed here — check your version)*. The point of today's version is
> that you can read and check what such a library does.

### 6.2 Determinism: why we hash instead of shuffle

Every "random" choice in the pipeline uses a hash of a fixed string. That gives three
properties a `Math.random()` shuffle doesn't:

1. **Repeatable.** Run it tomorrow and get the same split. Our 100-seed experiment is
   repeatable for the same reason.
2. **Cross-language.** JS and Python produce the same split and the same file hashes.
3. **Stable per record.** With a record split, a row's side depends only on its own id. Adding
   new rows never moves old ones.

The group split needs one extra rule. It picks test groups by walking a sorted list until it
reaches 25 %. If you add a new group whose hash sorts early, the walk changes, and an **old test
group could move into training**. That is a leak across versions. So the card records
`testGroups`, and the next version starts from that list: old test groups stay in test, and
only new groups are assigned. A frozen test set must stay frozen.

### 6.3 Lineage: know where every row came from

Each row in our output keeps `id`, `source` and (for synthetic rows) `origin`. This is
**data lineage**: the path from a training row back to where it came from. You need it when:

- a source turns out to be wrong, or its licence doesn't allow training — drop its rows;
- someone asks you to delete their data — find every row that contained it;
- a model gets worse — check whether a new source, or more synthetic data, arrived at the same
  time.

The `dropped` lists from each stage are lineage too. Keep them as a report next to the card.

### 6.4 Where this dataset goes next

```
   train.jsonl ──► Day 31: convert rows to the chat format, train a LoRA adapter
   test.jsonl  ──► Day 25: the evaluation dataset; a human checks a sample → golden set
   card        ──► the experiment record: "model X, trained on qbank 1.0.0 (f5ce2d97…)"
```

The same data feeds both, and that is the reason for today's care. A leak between the two files
makes Day 25's score meaningless. A bad row in `train.jsonl` becomes a bad habit in Day 31's
model.

> 📚 **Sources** (concepts cited, not run here)
>
> - Lee et al., *Deduplicating Training Data Makes Language Models Better* (2021):
>   <https://arxiv.org/abs/2107.06499>
> - Broder, *On the resemblance and containment of documents* (1997) — the origin of MinHash:
>   <https://www.cs.princeton.edu/courses/archive/spring13/cos598C/broder97resemblance.pdf>
> - Rae et al., *Scaling Language Models: Methods, Analysis & Insights from Training Gopher*
>   (2021) — quality filters including the stop-word rule: <https://arxiv.org/abs/2112.11446>
> - Microsoft Presidio, Analyzer docs — regex, NER, validation and context words for PII:
>   <https://presidio.dataprivacystack.org/analyzer/>
> - Wang et al., *Self-Instruct: Aligning Language Models with Self-Generated Instructions*
>   (2022): <https://arxiv.org/abs/2212.10560>
> - Shumailov et al., *AI models collapse when trained on recursively generated data*, Nature
>   631 (2024): <https://www.nature.com/articles/s41586-024-07566-y>
> - Landis & Koch, *The Measurement of Observer Agreement for Categorical Data*, Biometrics
>   33(1), 1977 — the kappa reading scale; summary:
>   <https://search.r-project.org/CRAN/refmans/irrCAC/html/landis.koch.html>
> - Gebru et al., *Datasheets for Datasets* (2018): <https://arxiv.org/abs/1803.09010>
> - Hugging Face, *Dataset Cards*: <https://huggingface.co/docs/hub/datasets-cards>
> - BIG-bench's canary string, used to keep test data out of training sets:
>   <https://github.com/google/BIG-bench>
> - Chip Huyen, *AI Engineering*, ch. 8 "Dataset Engineering" (table of contents):
>   <https://github.com/chiphuyen/aie-book/blob/main/ToC.md>

---

## 7. Common mistakes

### ❌ 1. Hashing before normalising

```js
// ❌ every invisible difference becomes a "different" record
exactDedupe(raw, (r) => `${r.question} || ${r.answer}`);
// ✅ clean first, then compare a lower-cased key
exactDedupe(raw.map((r) => ({ ...r, question: clean(r.question), answer: clean(r.answer) })), key);
```

**Symptom (verified):** 23 rows kept instead of 21. The extra-spaces copy (r02) and the
full-width copy (r22) both survive.

### ❌ 2. Different lower-casing in each language

```python
key = text.casefold()   # ❌ "Straße" → "strasse"; JS toLowerCase() gives "straße"
key = text.lower()      # ✅ matches JS toLowerCase() for this text
```

**Symptom (verified):** the JS and Python services compute different keys, and so different
hashes, for the same row. Dedupe across services silently stops working.

### ❌ 3. A `g` flag on a regex you call `.test()` on (JS)

```js
const B = /click here|subscribe|cookie/gi;   // ❌ remembers lastIndex between calls
const B = /click here|subscribe|cookie/i;    // ✅ no state
```

**Symptom (verified):** `[true, true, false, true]` on four boilerplate strings. "Cookie banner"
got through because the search started part-way into it.

### ❌ 4. Picking a near-duplicate threshold without looking

```
   ❌ "0.15 sounds safe"   → also drops r07, a different question (false match)
   ❌ "0.8 sounds safe"    → drops nothing; all three near-copies stay
   ✅ print the top pairs, find the gap (0.669 vs 0.183 here), set the threshold inside it
```

### ❌ 5. Splitting record by record when rows are related

```js
splitByRecord(rows, seed);                       // ❌ near-copies land on both sides
splitByGroup(rows, seed, (r) => r.source);       // ✅ whole documents on one side
```

**Symptom (verified):** with near-copies present, the record split leaked in **79 of 100**
seeds. The group split leaked in **0**.

### ❌ 6. Hashing each group into a bucket

```js
rows.filter((r) => bucket(seed, r.source) < 25);   // ❌ with 7 groups, often 0 groups pass
```

**Symptom (verified):** an **empty test set in 16 of 100 seeds**. Sort the groups by hash and
add them until the test share is reached (§4.8).

### ❌ 7. Believing the PII scrub is complete

**Symptom (verified):** the regexes missed "Ayesha Khan" and "ayesha dot khan at example dot
com". They also turned a date, a version number and an ISBN into `[PHONE]`. Write the limits
into the dataset card, use better detectors for sensitive data, and have a person check a sample.

### ❌ 8. Trusting synthetic output because it parses

```
   ❌ JSON.parse(reply) → straight into train.jsonl
   ✅ parse → schema → grounded → no answer leak → not a duplicate → tag origin
```

**Symptom (verified):** only **2 of 7** generated items passed. The ungrounded, leaking and
duplicate items had a perfectly valid shape, so a schema alone would have accepted them.

### ❌ 9. Synthetic rows in the test set

A model-written test checks how well your model matches *that* model's habits. Keep test and
golden sets human-written (or human-checked). Our split puts synthetic rows in training only,
and drops them when their source document is in test.

### ❌ 10. Reporting percent agreement alone

**Symptom (verified):** a labeller who says "good" to everything reached **75 % agreement**
with Ana, the same as Ben — but kappa was **0.000** against Ben's **0.400**. Always report
kappa next to percent agreement.

### ❌ 11. "The same data" with different bytes

```python
json.dumps(r)                                              # ❌ spaces + "—" escapes
open("train.jsonl", "w", encoding="utf-8")                 # ❌ on Windows: "\r\n" endings
json.dumps(r, ensure_ascii=False, separators=(",", ":"))   # ✅ matches JS JSON.stringify
open("train.jsonl", "w", encoding="utf-8", newline="\n")   # ✅
```

**Symptom (verified):** four different hashes for the same 11 rows (§3.10). The card says one
thing, the file another, and nobody trusts either.

### ❌ 12. Re-splitting every version

**Symptom:** a test group moves into training in version 1.1, and the new model "improves" on
questions it has now seen. Keep the seed **and** record `testGroups` in the card. The next
version keeps those groups in test (§6.2).

---

## 8. Exercises

### Exercise 1 — Shingle size and threshold ●●○○○

Run the near-duplicate step with shingle sizes k = 3, 5 and 8. Print the Jaccard score for the
three planted pairs (r01–r03, r09–r10, r18–r20) and for the different-question pair r05–r07.
Then run `nearDedupe` with thresholds 0.15, 0.5 and 0.8. Predict first: does a bigger k make
scores go up or down?

<details>
<summary>✅ Solution</summary>

Add to the end of `dataset.js`:

```js
for (const k of [3, 5, 8]) {
  const J = (a, b) => jaccard(shingles(key(byId[a]), k), shingles(key(byId[b]), k)).toFixed(3);
  console.log(`k=${k}  r01–r03 ${J("r01", "r03")}  r09–r10 ${J("r09", "r10")}  ` +
              `r18–r20 ${J("r18", "r20")}  r05–r07 ${J("r05", "r07")}`);
}
for (const t of [0.15, 0.5, 0.8])
  console.log(`threshold ${t} → dropped`, nearDedupe(exact.kept, t).dropped);
```

Add to the end of `dataset.py`:

```python
for k in (3, 5, 8):
    def J(a, b, k=k):
        return f"{jaccard(shingles(key(by_id[a]), k), shingles(key(by_id[b]), k)):.3f}"
    print(f"k={k}  r01–r03 {J('r01', 'r03')}  r09–r10 {J('r09', 'r10')}  "
          f"r18–r20 {J('r18', 'r20')}  r05–r07 {J('r05', 'r07')}")
for t in (0.15, 0.5, 0.8):
    print(f"threshold {t} → dropped", near_dedupe(exact, t)[1])
```

Output (identical in both languages):

```text
k=3  r01–r03 0.788  r09–r10 0.793  r18–r20 0.808  r05–r07 0.318
k=5  r01–r03 0.669  r09–r10 0.670  r18–r20 0.731  r05–r07 0.183
k=8  r01–r03 0.555  r09–r10 0.586  r18–r20 0.605  r05–r07 0.112
threshold 0.15 → dropped ['r03~r01', 'r07~r05', 'r10~r09', 'r20~r18']
threshold 0.5 → dropped ['r03~r01', 'r10~r09', 'r20~r18']
threshold 0.8 → dropped []
```

**Why:** bigger shingles are rarer, so fewer of them are shared. Every score goes **down** as k
goes up. Small k makes unrelated texts look similar (r05–r07 reaches 0.318 at k = 3). Large k
makes near-copies look different. What matters is the **gap** between copies and non-copies.
The gap between the lowest copy and r05–r07 is 0.470 at k = 3, 0.486 at k = 5 and 0.443 at
k = 8. So k = 5 separates them best here. Pick k and the threshold from your own data, never
from habit.

</details>

### Exercise 2 — Break it seven ways ●●○○○

Predict the symptom, then run each one.

1. Hash the raw text, without `clean()`.
2. JS: add the `g` flag to `BOILERPLATE` and `.test()` four boilerplate strings in a row.
3. Run the phone regex on `"call 555 0104"`, `"version 1.2.3.4.5"` and
   `"ISBN 978-0-13-468599-1"`.
4. Remove the answer-leak check from the synthetic validator.
5. Skip near-dedupe and split record by record, over 100 seeds.
6. Write the same rows with different bytes: other key order; Python `json.dumps` defaults;
   Python `open()` without `newline="\n"` on Windows.
7. Put each source document into test if its own hash bucket is < 25.

<details>
<summary>✅ Solution</summary>

| # | Symptom (verified) | Why |
|---|---|---|
| 1 | 23 kept instead of 21; r02 and r22 survive | spaces, case and full-width letters change the bytes, so the hash changes |
| 2 | `[true, true, false, true]` — "Cookie banner" passes | a `g` regex keeps `lastIndex`; the next `.test` starts mid-string. Python has no such state |
| 3 | `"call 555 0104"` unchanged; the other two become `[PHONE]` | 8 characters is below the pattern's minimum; any long digit run with dots or dashes matches |
| 4 | 3 accepted instead of 2 — s5 gets in | s5's answer is fully inside its question; only the leak check notices |
| 5 | leaked in 79 of 100 seeds (`r18~r20` with seed "qbank") | near-copies are independent rows to a record split |
| 6 | 4 hashes for one dataset: `f5ce2d97…`, `137157cf…` (dumps defaults), `ed56a103…` (11 CRLF), and key order `aa0a8f32…` vs `99b76ef5…` per row | hashes compare bytes, not meaning |
| 7 | empty test set in 16 of 100 seeds | with 7 groups, each having a 25 % chance, all 7 can miss |

Repro for #2, #3, #4 and #6 — add to the end of `dataset.js` (#1, #5 and #7 are already
printed by §4.2 and §4.8):

```js
// #2 — a "g" flag on a regex used with .test()
const G = /click here|subscribe|cookie|all rights reserved|lorem ipsum/gi;
console.log("#2", ["Cookie settings", "Click here to subscribe", "Cookie banner",
                   "All rights reserved"].map((t) => G.test(t)));

// #3 — formats the PII regex gets wrong
for (const t of ["call 555 0104", "version 1.2.3.4.5", "ISBN 978-0-13-468599-1"])
  console.log("#3", JSON.stringify(t), "→", JSON.stringify(scrub(t).text));

// #4 — the same synthetic batch without the answer-leak check
const seen4 = new Set(scrubbed.map(key));
const noLeakCheck = items.filter((item) => {
  if (!QA.safeParse(item).success) return false;
  if (share(contentWords(item.answer), new Set(words(DOC))) < 0.5) return false;
  const k = key({ question: clean(item.question), answer: clean(item.answer) });
  if (seen4.has(k)) return false;
  seen4.add(k);
  return true;
});
console.log("#4 accepted without the leak check:", noLeakCheck.length);

// #6 — same row, keys in a different order
const row = train[0];
const reordered = { answer: row.answer, question: row.question, source: row.source, id: row.id };
console.log("#6", sha256(JSON.stringify(row)).slice(0, 16), sha256(JSON.stringify(reordered)).slice(0, 16));
// #2 [ true, true, false, true ]
// #3 "call 555 0104" → "call 555 0104"
// #3 "version 1.2.3.4.5" → "version [PHONE]"
// #3 "ISBN 978-0-13-468599-1" → "ISBN [PHONE]"
// #4 accepted without the leak check: 3
// #6 aa0a8f32f13acf6d 99b76ef5cb891e95
```

Add to the end of `dataset.py`:

```python
# #3 — formats the PII regex gets wrong
for t in ["call 555 0104", "version 1.2.3.4.5", "ISBN 978-0-13-468599-1"]:
    print("#3", json.dumps(t), "→", json.dumps(scrub(t)[0]))

# #4 — the same synthetic batch without the answer-leak check
seen4, no_leak_check = {key(r) for r in scrubbed}, []
for item in items:
    try:
        QA.model_validate(item)
    except ValidationError:
        continue
    if share(content_words(item["answer"]), set(words(DOC))) < 0.5:
        continue
    k = key({"question": clean(item["question"]), "answer": clean(item["answer"])})
    if k in seen4:
        continue
    seen4.add(k)
    no_leak_check.append(item)
print("#4 accepted without the leak check:", len(no_leak_check))

# #6 — same rows, different bytes
row = train[0]
reordered = {"answer": row["answer"], "question": row["question"], "source": row["source"], "id": row["id"]}
compact = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))
print("#6 key order:", sha256(compact(row))[:16], sha256(compact(reordered))[:16])
print("#6 json.dumps defaults:", sha256("".join(json.dumps(r) + "\n" for r in train))[:16])
with open("train-default.jsonl", "w", encoding="utf-8") as f:     # no newline="\n"
    f.write(to_jsonl(train))
with open("train-default.jsonl", "rb") as f:
    data = f.read()
print("#6 default newline:", hashlib.sha256(data).hexdigest()[:16], "CRLF:", data.count(b"\r\n"))
# #3 … same three results as JS
# #4 accepted without the leak check: 3
# #6 key order: aa0a8f32f13acf6d 99b76ef5cb891e95
# #6 json.dumps defaults: 137157cf64c8808d
# #6 default newline: ed56a103e7960640 CRLF: 11        (Windows; on Linux/macOS no CRLF)
```

**Why this design:** every one of these bugs is silent. Nothing crashes. The only defence is a
check that prints counts and hashes, and a person who reads them.

</details>

### Exercise 3 — Three labels, one kappa ●●●○○

Two tutors grade 10 answers as `good`, `partly` or `bad`:

```
   A   good  good    partly  bad  good  partly  good  bad  good    good
   B   good  partly  partly  bad  good  good    good  bad  partly  good
```

1. Compute percent agreement, chance agreement and kappa **by hand**, then with your
   `agreement` function.
2. List the items where they disagree. What do the disagreements have in common?
3. Write one new guideline sentence that would remove most of them.

<details>
<summary>✅ Solution</summary>

**By hand.** They agree on 7 of 10 items: observed = **0.700**. Label counts: A has good 6,
partly 2, bad 2; B has good 5, partly 3, bad 2.

```
   chance = (6/10 × 5/10) + (2/10 × 3/10) + (2/10 × 2/10) = 0.30 + 0.06 + 0.04 = 0.400
   kappa  = (0.700 − 0.400) / (1 − 0.400) = 0.500
```

```js
const A3 = "good good partly bad good partly good bad good good".split(" ");
const B3 = "good partly partly bad good good good bad partly good".split(" ");
console.log(fmt(agreement(A3, B3)));
console.log("disagree at items", A3.flatMap((x, i) => (x !== B3[i] ? [`${i + 1}:${x}/${B3[i]}`] : [])));
// agree=0.700 chance=0.400 kappa=0.500
// disagree at items [ '2:good/partly', '6:partly/good', '9:good/partly' ]
```

```python
A3 = "good good partly bad good partly good bad good good".split()
B3 = "good partly partly bad good good good bad partly good".split()
print(fmt(agreement(A3, B3)))
print("disagree at items", [f"{i}:{x}/{y}" for i, (x, y) in enumerate(zip(A3, B3), 1) if x != y])
# agree=0.700 chance=0.400 kappa=0.500
# disagree at items ['2:good/partly', '6:partly/good', '9:good/partly']
# scikit-learn cohen_kappa_score(A3, B3) → 0.5 (verified)
```

**The pattern:** all three disagreements are on the **good / partly** border. Nobody disagrees
about `bad`. So the guidelines define `bad` clearly and `partly` vaguely.

**A guideline sentence that fixes it:** *"`partly` = correct, but missing a fact from the
item's must-include list. If every must-include fact is there, the answer is `good`, however
short."* It turns a feeling into a check. Re-label a fresh sample afterwards
and see whether kappa rises.

**Why this design:** kappa tells you *that* people disagree. Listing the disagreements tells you
*where*, and that is what you fix.

</details>

### Exercise 4 — Is your golden set already in training? ●●●○○

You wrote three golden questions by hand. Before you trust them, check them against
`train.jsonl`:

1. Write `contaminated(golden, train, threshold = 0.5)`. For each golden item, find the most
   similar training row; report it if its Jaccard is at or above the threshold.
2. Add a **canary string** — a unique, random marker — to the golden file's header. Check that
   it does not appear in `train.jsonl`. (The BIG-bench project uses a canary GUID the same
   way, so dataset builders can filter benchmark files out.)

```
   g1  "What does the git commit command do?"  "It saves a snapshot of staged changes to the repository history."
   g2  "Why can a recursive function crash?"   "Without a base case it never stops, and the call stack overflows."
   g3  "What does DNS do?"                     "It turns a domain name into an IP address."
```

<details>
<summary>✅ Solution</summary>

```js
const CANARY = "SB-GOLDEN-CANARY 3f6c1e2a-7d4b-4c1e-9a8f-0b5d2e7c9a14";   // make your own
const golden = [
  { id: "g1", question: "What does the git commit command do?",
    answer: "It saves a snapshot of staged changes to the repository history." },
  { id: "g2", question: "Why can a recursive function crash?",
    answer: "Without a base case it never stops, and the call stack overflows." },
  { id: "g3", question: "What does DNS do?",
    answer: "It turns a domain name into an IP address." },
];
function contaminated(goldenRows, trainRows, threshold = 0.5) {
  const out = [];
  for (const g of goldenRows) {
    const s = shingles(key(g));
    const [id, j] = trainRows.map((r) => [r.id, jaccard(s, shingles(key(r)))])
                             .sort((x, y) => y[1] - x[1])[0];
    if (j >= threshold) out.push(`${g.id}~${id} (${j.toFixed(3)})`);
  }
  return out;
}
console.log("contaminated:", contaminated(golden, train));
console.log("canary found in train.jsonl:", readFileSync("train.jsonl", "utf8").includes(CANARY));
// contaminated: [ 'g1~r15 (0.581)' ]
// canary found in train.jsonl: false
```

```python
CANARY = "SB-GOLDEN-CANARY 3f6c1e2a-7d4b-4c1e-9a8f-0b5d2e7c9a14"   # make your own
golden = [
    {"id": "g1", "question": "What does the git commit command do?",
     "answer": "It saves a snapshot of staged changes to the repository history."},
    {"id": "g2", "question": "Why can a recursive function crash?",
     "answer": "Without a base case it never stops, and the call stack overflows."},
    {"id": "g3", "question": "What does DNS do?",
     "answer": "It turns a domain name into an IP address."},
]
def contaminated(golden_rows, train_rows, threshold=0.5):
    out = []
    for g in golden_rows:
        s = shingles(key(g))
        rid, j = max(((r["id"], jaccard(s, shingles(key(r)))) for r in train_rows),
                     key=lambda x: x[1])
        if j >= threshold:
            out.append(f"{g['id']}~{rid} ({j:.3f})")
    return out
print("contaminated:", contaminated(golden, train))
with open("train.jsonl", encoding="utf-8") as f:
    print("canary found in train.jsonl:", CANARY in f.read())
# contaminated: ['g1~r15 (0.581)']
# canary found in train.jsonl: False
```

**What it means:** g1 is a near-copy of training row r15 (0.581). You wrote it "by hand", but
you wrote it after reading the notes, so it came out almost the same. Either replace g1 with a
question about git that isn't in training, or move the git document to the test side. g2 is
about recursion, which *is* in training, but it is worded differently (its closest training
row scored 0.292). A shingle check can't tell whether that is "new enough". That is a judgement
call: a golden set should test understanding of the topic, not recall of one sentence.

**Why the canary:** a similarity check only finds copies of text you still have. A canary also
catches the golden file being copied *whole* into some other training corpus later — by you,
a teammate, or a web scraper.

</details>

### Exercise 5 — 🎯 StudyBuddy v6.4: a data gate for the question bank ●●●●○

StudyBuddy now has a versioned question bank, `studybuddy-qbank` 1.0.0. Make sure no future
version can ship with a known data bug. Write an `audit(train, test)` function that returns a
list of problems:

- a **leak** — any test row with a near-copy in training;
- **PII left** — any row where the scrubber still finds something;
- **duplicate rows** across both files;
- a **synthetic row in test**.

Then build a **gate**: run the split a second time and check the test file hash is the same,
and exit with a non-zero code if anything fails. Run it on the real split (should pass) and on
the leaky record split from §4.8 (should fail).

<details>
<summary>✅ Solution</summary>

```js
function audit(trainRows, testRows) {
  const problems = [];
  const l = leaks(trainRows, testRows);
  if (l.length) problems.push(`leak: ${l.join(", ")}`);
  for (const r of [...trainRows, ...testRows]) {
    const hits = scrub(`${r.question} ${r.answer}`).found;
    if (hits.length) problems.push(`pii-left: ${r.id} ${hits.join(" ")}`);
  }
  const keys = [...trainRows, ...testRows].map(key);
  if (new Set(keys).size !== keys.length) problems.push("duplicate rows");
  if (testRows.some((r) => r.origin === "synthetic")) problems.push("synthetic row in test");
  return problems;
}
console.log("audit(train, test):", audit(train, test));
console.log("audit(record split of unscrubbed rows):", audit(a1.train, a1.test));

const again = splitByGroup(scrubbed, "qbank", (r) => r.source);
const sameTest = sha256(toJsonl(again.test)).slice(0, 16) === card.files["test.jsonl"].sha256;
console.log("same test file on a second run:", sameTest);

const problems = audit(train, test);
if (problems.length || !sameTest) { console.error("DATA GATE FAILED", problems); process.exitCode = 1; }
else console.log("data gate passed");
```

```python
def audit(train_rows, test_rows):
    problems = []
    if l := leaks(train_rows, test_rows):
        problems.append(f"leak: {', '.join(l)}")
    for r in train_rows + test_rows:
        _, hits = scrub(f"{r['question']} {r['answer']}")
        if hits:
            problems.append(f"pii-left: {r['id']} {' '.join(hits)}")
    keys = [key(r) for r in train_rows + test_rows]
    if len(set(keys)) != len(keys):
        problems.append("duplicate rows")
    if any(r.get("origin") == "synthetic" for r in test_rows):
        problems.append("synthetic row in test")
    return problems
print("audit(train, test):", audit(train, test))
a_tr, a_te = split_by_record(leaky, "qbank")
print("audit(record split of unscrubbed rows):", audit(a_tr, a_te))

_, again = split_by_group(scrubbed, "qbank", lambda r: r["source"])
same_test = sha256(to_jsonl(again))[:16] == card["files"]["test.jsonl"]["sha256"]
print("same test file on a second run:", same_test)

import sys
problems = audit(train, test)
if problems or not same_test:
    sys.exit(f"DATA GATE FAILED {problems}")
print("data gate passed")
```

Output (same verdicts in both languages):

```text
audit(train, test): []
audit(record split of unscrubbed rows): [
  'leak: r18~r20',
  'pii-left: r14 EMAIL:ayesha.khan@example.com',
  'pii-left: r17 PHONE:020 7946 0958 PHONE:(555) 010-4477',
  'pii-left: r15 PHONE:2026-03-14',
  'pii-left: r16 PHONE:+44 7700 900123'
]
same test file on a second run: true
data gate passed
```

Swapping the gate's input to the leaky record split made both scripts print
`DATA GATE FAILED …` and **exit with code 1** (verified), which fails a CI job.

**Report for StudyBuddy v6.4:**

```
   dataset     studybuddy-qbank 1.0.0
   rows        24 raw → 21 → 18 → 14, plus 2 checked synthetic rows
   train       11 rows   sha256 f5ce2d97fb00603e
   test         5 rows   sha256 d65a8acc6963b6a2
   split       by source, seed "qbank", test groups http, tcp, dns
   gate        passed
```
 Known limit,
written in the card: names and spelled-out emails are not caught (r21 still says "Ask Ayesha
Khan").

**Why this design:** the gate is the data version of Day 25's CI eval gate. It is cheap, it
runs on every change, and it turns today's lessons into rules a teammate can't forget. Note
what it can't do: it passed r21, because regex can't see the name. A passing gate means "no
*known* problems", not "no problems".

</details>

---

## 9. Interview questions

### Basic

**Q1. Why de-duplicate training data at all?**

Duplicates change what the model sees most often, so it over-learns those examples and is more
likely to repeat them word for word. They also leak into test sets and inflate scores. Lee et
al. (2021) reported that de-duplicated models produced memorised text about ten times less
often. In our 24-row bank, 25 % of rows were copies.

---

**Q2. Why normalise text before hashing it?**

A hash compares bytes. Extra spaces, letter case and full-width characters change the bytes but
not the meaning. In our data, hashing raw text found 1 copy; NFKC + whitespace + lower-case
found 3. Store the cleaned original, compare the normalised key.

---

**Q3. What is a near-duplicate, and how do you find one?**

Two records that differ by a few words or punctuation marks. Cut each into overlapping
character shingles and compute Jaccard similarity (shared ÷ total distinct shingles). Our
planted near-copies scored 0.669–0.731; the closest different pair scored 0.183, so a 0.5
threshold separated them. Paraphrases with new words need embeddings instead.

---

**Q4. What is data leakage?**

When test examples, or close copies of them, are also in training. The model then scores well
by memory, not skill. With near-copies present, a record-by-record split leaked in 79 of 100
seeds in our test. The fix is to dedupe, split by group, and run a leak check.

---

**Q5. Why is percent agreement not enough to judge labels?**

Because agreement by luck is high when one label dominates. A labeller who said "good" to
everything agreed with a real labeller 75 % of the time — the same as a careful second
labeller. Cohen's kappa subtracts chance agreement: 0.000 for the lazy labeller, 0.400 for the
careful one.

### Intermediate

**Q6. Walk me through a data pipeline for a fine-tuning set.**

First collect, then clean (NFKC, whitespace). Next, exact dedupe (hash), then near dedupe
(shingles or MinHash). Then quality filters (length, language, boilerplate, repetition) and a
PII scrub. Then label and check, split by group, and version (file hashes + dataset card).
Cheap stages go first. Each stage
returns what it dropped and why, so the run doubles as a report.

---

**Q7. How does MinHash estimate Jaccard, and what does LSH add?**

For each of n hash functions, keep the minimum hash over a record's shingles. Two records share
a minimum with probability equal to their Jaccard, so the share of matching positions estimates
it. With 64 functions our worst error was 0.074; with 256 it was 0.034. LSH splits signatures
into bands and only compares records that share a band, which avoids comparing all n² pairs.
With 16 bands of 4, pairs at 0.9 similarity are almost always compared and pairs at 0.3 only
about 12 % of the time.

---

**Q8. How would you validate model-generated (synthetic) training data?**

Treat each item as untrusted. Parse it and retry on bad JSON. Check the schema (Zod/Pydantic),
then the content: is the answer grounded in the source, does the question give away the answer,
and is it a duplicate of an existing row? In our run 2 of 7 passed. Structured output fixes the
shape only. Tag every accepted row with its origin.

---

**Q9. What are the main risks of synthetic data?**

Model collapse — training on model output across generations loses the rare cases of real data
(Shumailov et al., Nature 2024). Bias copying — the generator's habits become your data's
habits. Eval contamination — synthetic rows about a test document leak that document into
training. Mitigations: keep human data, cap and measure the synthetic share, keep test and
golden sets human-written, and let synthetic rows follow their source document across the split.

---

**Q10. Your PII scrubber is regex-based. What do you tell your manager?**

That it catches common emails and phone numbers, and fails both ways. It missed a name and a
spelled-out email, and it flagged a date, a version number and an ISBN as phone numbers. For
sensitive data, add an NER-based tool such as Presidio and a human review of a sample. Scrub
before data leaves your control. Write the known limits into the dataset card.

### Advanced

**Q11. You split by group to stop leakage. What new problems does that create?**

Sizes become lumpy: with 7 groups, our test share ranged from 5 to 8 of 17 rows. Hashing each
group into a bucket left the test set empty in 16 of 100 seeds; adding groups in hash order
until a target share fixes that. Across versions, a new group can shift which groups are in
test. So freeze the list of test groups in the card. And grouping only helps if copies share a
group, so still dedupe first and run a leak check.

---

**Q12. How do you make a dataset reproducible across teams and languages?**

Deterministic choices (hash-based splits, not `random`), a fixed byte format (compact JSON,
UTF-8 without escapes, `\n` endings, fixed key order), and a file hash in a dataset card. We
got byte-identical files from JS and Python only after setting `ensure_ascii=False`, compact
separators and `newline="\n"` in Python; each default alone changed the hash.

---

**Q13. How would you check whether your golden eval set has leaked into training?**

Run a similarity check of every golden item against the training data: shingles for wording,
embeddings for paraphrases. Our hand-written g1 matched a training row at 0.581. Add a canary
string to the golden file and search training corpora for it. And never use golden items as
few-shot examples. Re-run the check whenever either side changes.

---

**Q14. Your labellers' kappa is 0.4. What do you do?**

Don't blame the labellers first; low kappa usually means unclear guidelines. List the
disagreements and look for a pattern. In our 3-label exercise, every disagreement sat on the
good/partly border, so the fix was a precise definition of "partly". Update the guidelines, add
worked examples, re-label a fresh sample, and check that kappa rises. Use only high-agreement
items in the golden set.

---

**Q15. When is it right to keep a "duplicate"?**

When the copies carry information you want. Real traffic has popular questions, and an
eval set that mirrors production may keep them weighted. Two rows with the same question but
different answers are a conflict to resolve, not a duplicate to drop. And in training, you may
deliberately repeat rare but important examples. The rule is: decide what "the same" means for
your task, and make duplication a choice, not an accident.

---

## 10. Recap

### What you learned

- ✅ Data is a pipeline: **collect → clean → exact dedupe → near dedupe → quality → PII → label →
  split → version**, each stage reporting what it dropped
- ✅ **Normalise, then hash**: NFKC + whitespace + lower-case found 3 copies where raw hashing
  found 1
- ✅ **Shingles + Jaccard** find near-copies; pick the threshold from the gap in your own scores
  (0.669 vs 0.183 here)
- ✅ **MinHash** estimates Jaccard from small signatures; **LSH** avoids comparing every pair
- ✅ **Quality filters** are cheap heuristics: length, stop-word share, boilerplate, repetition
- ✅ **Regex PII scrubbing** misses names and odd formats and flags harmless numbers — say so
- ✅ **Synthetic data** must pass parse → schema → grounded → no leak → not duplicate; 2 of 7
  passed
- ✅ Synthetic rows stay out of test and golden sets, and follow their source document
- ✅ **Split by group**: record splits leaked in 79 of 100 seeds, group splits in 0
- ✅ **Kappa** corrects percent agreement for luck: 75 % agreement can be kappa 0
- ✅ **Version** with file hashes and a dataset card; fix the byte format so hashes match
  across languages

### The data checklist

```
   □ clean before any comparison (NFKC, whitespace)     □ one meaning of "the same", written down
   □ exact dedupe, then near dedupe, threshold checked  □ quality filters report their reasons
   □ PII scrubbed before data leaves your control       □ PII limits written in the card
   □ synthetic rows validated, tagged, never in test    □ split by group, leak check after
   □ golden set human-checked, frozen, canary-marked    □ kappa reported next to % agreement
   □ file hashes + counts + seed + test groups in card  □ a data gate in CI
```

### Tomorrow

**[Day 33 — Multimodal](day-33-multimodal.md)**: today's data was all text. Real study
material isn't. Lecture slides have diagrams, notes are photos, and some students would rather
talk than type. Tomorrow StudyBuddy learns to take images and PDFs with pictures as input, and
to work with speech in and out.

### Quick self-check

1. You hash every row after `toLowerCase()` and still find no duplicates between two rows that
   look the same. Name two other causes.
2. Your test accuracy is 94 %, but students say the model fails on reworded questions. What
   do you check first, and with what tool?
3. Two labellers agree on 90 % of items. Why might kappa still be low?

<details>
<summary>Answers</summary>

1. Different whitespace (extra or doubled spaces, tabs) and Unicode forms that look alike but
   are different characters — such as full-width letters, which NFKC normalises. Clean with
   NFKC and collapse whitespace before hashing. (In a cross-language setup, also check that
   both sides lower-case the same way.)

2. Leakage. Run a near-duplicate check between the test and training sets (shingles + Jaccard,
   then embeddings for paraphrases). In our data, a record split leaked in 79 of 100 seeds. If
   you find leaks, re-split by group and re-measure: the honest score is usually lower.

3. Because chance agreement is high when one label dominates. If 90 % of items are "good",
   two labellers who mostly say "good" agree a lot by luck. Kappa subtracts that luck. A
   labeller who said "good" to everything reached 75 % agreement and kappa 0.000 in our
   example.
</details>

---

<div align="center">

**[← Day 31 — Fine-tuning](day-31-fine-tuning.md)** · **[Week 5 index](README.md)** · **[Day 33 — Multimodal →](day-33-multimodal.md)**

</div>
