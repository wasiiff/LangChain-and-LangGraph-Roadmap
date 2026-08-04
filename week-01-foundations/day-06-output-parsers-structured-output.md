# Day 06 — Output Parsers & Structured Output (Zod ↔ Pydantic)

> ⏱ **Time:** ~2.5 hours · 🎯 **Prereqs:** [Day 05](day-05-prompts-and-templates.md) · 🧩 **Difficulty:** ●●●○○

**Today you learn:** how to get *typed, validated objects* out of a model instead of a blob of
text. `StringOutputParser`, `JsonOutputParser`, `withStructuredOutput`, schema design that
actually improves accuracy, and what to do when validation fails.

This is the day LLM output becomes safe to put in a database.

---

## 1. The problem

Every example so far ends the same way:

```js
const res = await model.invoke("Extract the name and age from: 'Wasif is 27'");
console.log(res.text);
// "The name is Wasif and the age is 27."
```

Now put that in a database. You need `{ name: "Wasif", age: 27 }`. So you regex it. And on
Day 02 you already felt how that goes:

```js
const answer = cot.match(/ANSWER:\s*([\d.]+)/)?.[1];   // ← fragile
```

Here's how regex parsing actually dies in production:

```
"The name is Wasif and the age is 27."        ✅ your regex works
"Name: Wasif, Age: 27"                        ❌ different format
"Wasif (27)"                                  ❌ different again
"I found: **Wasif**, aged twenty-seven"       ❌ age isn't even a digit
"```json\n{\"name\":\"Wasif\"}\n```"          ❌ markdown fence, and age missing
"I'm sorry, I couldn't determine the age."    ❌ no data at all
```

You cannot fix this with a better regex. **You fix it by removing the model's freedom to
choose a format at all.**

---

## 2. Mental model

```
   THREE LEVELS OF GUARANTEE — pick the highest one your provider supports.

   ┌──────────────────────────────────────────────────────────────────────┐
   │ LEVEL 1 — ASK NICELY + PARSE                                         │
   │   "Respond in JSON"  →  text  →  JsonOutputParser  →  object         │
   │   ✅ works anywhere    ❌ ~3-10% failure, wrong shapes, md fences     │
   ├──────────────────────────────────────────────────────────────────────┤
   │ LEVEL 2 — JSON MODE                                                  │
   │   response_format: json_object  →  valid JSON  →  parse              │
   │   ✅ always parses     ❌ any shape — your keys may be missing        │
   ├──────────────────────────────────────────────────────────────────────┤
   │ LEVEL 3 — SCHEMA-CONSTRAINED  ← use this                             │
   │   withStructuredOutput(schema)                                       │
   │   ✅ validated object matching YOUR schema, typed, no parsing         │
   └──────────────────────────────────────────────────────────────────────┘


   WHAT withStructuredOutput ACTUALLY DOES:

     Zod / Pydantic schema
              │
              ▼  converted to
        JSON Schema  ────────────┐
              │                  │ sent to the model as a TOOL definition
              ▼                  ▼
     ┌──────────────────────────────────┐
     │ model is constrained to emit     │
     │ arguments matching that schema   │
     └──────────────────────────────────┘
              │
              ▼
     tool_call.args  →  validate  →  typed object ✅
```

---

## 3. First principles

### 3.1 What an output parser is

A parser is just a `Runnable` that takes the model's output and returns something else. That's
it. Because it's a `Runnable`, it goes on the end of a chain:

```
prompt  →  model  →  parser
{vars}     AIMessage   whatever you want
```

| Parser | Input | Output |
|---|---|---|
| `StringOutputParser` | `AIMessage` | `string` — just the text |
| `JsonOutputParser` | `AIMessage` | parsed object (tolerates markdown fences) |
| `CommaSeparatedListOutputParser` | `AIMessage` | `string[]` |
| `StructuredOutputParser` | `AIMessage` | object matching a schema |
| `OutputFixingParser` | failed parse | retries by asking the model to fix it |

### 3.2 `StringOutputParser` — the one you'll use most

```js
const chain = prompt.pipe(model).pipe(new StringOutputParser());
const text = await chain.invoke({ q: "hi" });   // a plain string, not an AIMessage
```

Trivial but important: it makes chains composable. If step 2 needs a *string*, you can't hand
it an `AIMessage`. It also makes `.stream()` yield string chunks instead of message chunks,
which is what a web response wants.

### 3.3 `withStructuredOutput` — the one that matters

```js
import * as z from "zod";

const Person = z.object({
  name: z.string().describe("The person's full name"),
  age: z.number().int().describe("Age in years"),
});

const extractor = model.withStructuredOutput(Person);
const result = await extractor.invoke("Wasif is 27 and lives in Lahore.");
// → { name: "Wasif", age: 27 }   ← a real object. Validated. No parsing.
```

No prompt engineering about JSON. No parser. No regex. The schema *is* the instruction.

**Python is identical with Pydantic:**

```python
class Person(BaseModel):
    name: str = Field(description="The person's full name")
    age: int = Field(description="Age in years")

extractor = model.with_structured_output(Person)
result = extractor.invoke("Wasif is 27 and lives in Lahore.")
# → Person(name='Wasif', age=27)
```

> 🔑 **`.describe()` / `Field(description=)` is prompt engineering.** Those strings are sent to
> the model. `age: z.number()` gets you a number; `age: z.number().describe("Age in years, or -1
> if not stated")` gets you correct behaviour on missing data. Schema design *is* prompt design.

### 3.4 Schema design patterns that improve accuracy

**Use enums instead of free strings:**

```js
sentiment: z.enum(["positive", "negative", "neutral"])   // ✅ unrepresentable to get it wrong
sentiment: z.string()                                     // ❌ "Positive!", "kind of positive"
```

**Make "unknown" representable:**

```js
// ❌ Model must invent a value when the data isn't there
age: z.number()

// ✅ Give it an honest escape hatch
age: z.number().nullable().describe("Age in years, or null if not stated"),
```

This single change removes a large fraction of hallucinated field values.

**Ask for reasoning *inside* the schema (structured CoT):**

```js
const Classification = z.object({
  reasoning: z.string().describe("Brief reasoning. Write this FIRST."),
  label: z.enum(["BILLING", "BUG", "FEATURE"]),
  confidence: z.number().min(0).max(1),
});
```

Field order matters — the model generates fields in schema order, so `reasoning` first means it
literally thinks before committing to `label`. You get chain-of-thought *and* a clean object.

**Add a confidence field and route on it:**

```js
if (result.confidence < 0.7) escalateToHuman(result);
```

Self-reported confidence is imperfect but a genuinely useful cheap signal.

**Nest for structure, but not too deep:**

```js
const Invoice = z.object({
  vendor: z.string(),
  lineItems: z.array(z.object({
    description: z.string(),
    quantity: z.number().int(),
    unitPrice: z.number(),
  })).describe("Every line item on the invoice"),
  total: z.number(),
});
```

Two or three levels is fine. Beyond that, accuracy drops sharply — split into multiple calls.

### 3.5 The two strategies behind `withStructuredOutput`

Under the hood there are two mechanisms:

| Method | How | When |
|---|---|---|
| **Tool calling** (default) | Schema becomes a tool definition; model emits `tool_call.args` | Provider supports tools — nearly all do |
| **JSON mode** | `response_format: json_object` + schema in the prompt | Provider has JSON mode but weak tool support |

```js
model.withStructuredOutput(Schema, { method: "jsonMode" });   // force JSON mode
model.withStructuredOutput(Schema, { includeRaw: true });     // get the raw message too
```

`includeRaw: true` returns `{ raw: AIMessage, parsed: object | null }` — useful when you need
token usage, or want to handle parse failure yourself rather than throwing.

### 3.6 When it fails, and what to do

Structured output can still fail:

- The model refuses ("I can't extract that")
- Content genuinely doesn't contain the fields
- The provider's constraint is imperfect for deeply nested schemas
- A timeout mid-generation

**Three layers of defence:**

```js
// 1. includeRaw so you can inspect instead of throwing
const { raw, parsed } = await model.withStructuredOutput(Schema, { includeRaw: true })
                                   .invoke(input);
if (!parsed) { /* handle gracefully */ }

// 2. Retries
model.withStructuredOutput(Schema).withRetry({ stopAfterAttempt: 3 })

// 3. Fallback to a different model
model.withStructuredOutput(Schema).withFallbacks([other.withStructuredOutput(Schema)])
```

And the manual level-1 approach, for providers without tool support:

```js
const parser = new JsonOutputParser();
const fixing = OutputFixingParser.fromLLM(model, parser);   // asks the model to repair
```

`OutputFixingParser` feeds the broken output *and* the error message back to the model and asks
for a corrected version. Costs an extra call; saves the request.

### 3.7 Streaming structured output

Structured output can stream — you get **progressively complete partial objects**:

```js
for await (const partial of await chain.stream(input)) {
  console.log(partial);
  // { }
  // { title: "Rain" }
  // { title: "Rainbows", bullets: ["Light refracts"] }
  // { title: "Rainbows", bullets: ["Light refracts", "..."] }   ← complete
}
```

This is how you build a UI that fills in fields as they arrive. Note each chunk is the
**accumulated** object, not a delta.

---

## 4. Code — JavaScript

```bash
npm install langchain @langchain/core @langchain/groq zod dotenv
```

### 4.1 String and JSON parsers

```js
// day06-parsers.js
import "dotenv/config";
import { ChatGroq } from "@langchain/groq";
import { ChatPromptTemplate } from "@langchain/core/prompts";
import { StringOutputParser, JsonOutputParser,
         CommaSeparatedListOutputParser } from "@langchain/core/output_parsers";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });

// ── StringOutputParser ───────────────────────────────────────────────────
const prompt = ChatPromptTemplate.fromMessages([["human", "Name one {thing}. One word only."]]);

const withoutParser = prompt.pipe(model);
const withParser    = prompt.pipe(model).pipe(new StringOutputParser());

console.log(typeof (await withoutParser.invoke({ thing: "planet" })));  // object (AIMessage)
console.log(typeof (await withParser.invoke({ thing: "planet" })));     // string ✅

// It also changes what streaming yields:
for await (const c of await withParser.stream({ thing: "fruit" })) {
  process.stdout.write(c);            // strings, not AIMessageChunks
}
console.log();

// ── JsonOutputParser ─────────────────────────────────────────────────────
const jsonChain = ChatPromptTemplate.fromMessages([
  ["system", 'Extract data as JSON with keys "name" and "age". Output JSON only.'],
  ["human", "{text}"],
]).pipe(model).pipe(new JsonOutputParser());

console.log(await jsonChain.invoke({ text: "Wasif is 27 years old." }));
// { name: 'Wasif', age: 27 }   ← markdown fences are stripped automatically

// ── CommaSeparatedListOutputParser ───────────────────────────────────────
const listParser = new CommaSeparatedListOutputParser();
const listChain = ChatPromptTemplate.fromMessages([
  ["human", "List 5 {category}.\n{format_instructions}"],
]).partial({ format_instructions: listParser.getFormatInstructions() })
  .pipe(model).pipe(listParser);

console.log(await listChain.invoke({ category: "programming languages" }));
// [ 'Python', 'JavaScript', 'Java', 'C++', 'Go' ]
```

### 4.2 `withStructuredOutput` — the main event

```js
// day06-structured.js
import "dotenv/config";
import * as z from "zod";
import { ChatGroq } from "@langchain/groq";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });

const SupportTicket = z.object({
  // Reasoning FIRST — the model generates fields in order, so this is CoT.
  reasoning: z.string().describe("One sentence explaining your classification. Write this first."),

  category: z.enum(["BILLING", "BUG", "FEATURE", "OTHER"])
    .describe("The primary category of the ticket"),

  urgency: z.enum(["low", "medium", "high", "critical"])
    .describe("critical = users cannot use the product at all"),

  summary: z.string().describe("The issue in under 15 words"),

  affectedFeature: z.string().nullable()
    .describe("The specific feature mentioned, or null if none is named"),

  customerSentiment: z.enum(["calm", "frustrated", "angry"]),

  confidence: z.number().min(0).max(1)
    .describe("Your confidence in this classification, 0 to 1"),
});

const classifier = model.withStructuredOutput(SupportTicket, { name: "classify_ticket" });

const TICKETS = [
  "URGENT!!! Nobody on my team can log in since the update. We have a demo in 20 minutes.",
  "Hey, would be lovely if you added a dark mode at some point. No rush!",
  "I've been charged £49 twice this month and support hasn't replied in 6 days.",
  "hi",
];

for (const t of TICKETS) {
  const r = await classifier.invoke(t);
  console.log(`\n"${t.slice(0, 50)}..."`);
  console.log(`  ${r.category}/${r.urgency} · ${r.customerSentiment} · conf=${r.confidence}`);
  console.log(`  summary: ${r.summary}`);
  console.log(`  feature: ${r.affectedFeature ?? "(none)"}`);
  if (r.confidence < 0.7) console.log("  ⚠️  low confidence → route to human");
}
```

Note `"hi"` — with `affectedFeature` nullable and a confidence field, the model can honestly say
"I don't know" instead of inventing a category.

### 4.3 Nested schemas — invoice extraction

```js
// day06-nested.js
import "dotenv/config";
import * as z from "zod";
import { ChatGroq } from "@langchain/groq";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });

const LineItem = z.object({
  description: z.string(),
  quantity: z.number().int(),
  unitPrice: z.number().describe("Price per unit, excluding tax"),
});

const Invoice = z.object({
  vendor: z.string(),
  invoiceNumber: z.string().nullable(),
  date: z.string().nullable().describe("ISO 8601 date (YYYY-MM-DD), or null if absent"),
  currency: z.enum(["USD", "EUR", "GBP", "PKR", "OTHER"]),
  lineItems: z.array(LineItem).describe("Every line item listed"),
  subtotal: z.number(),
  tax: z.number().nullable(),
  total: z.number(),
});

const TEXT = `
ACME SUPPLIES LTD
Invoice #INV-2024-0891    Date: 14 March 2024

Widget A          x12    @ $4.50
Gizmo Pro         x3     @ $29.99
Shipping          x1     @ $12.00

Subtotal: $156.97
VAT (20%): $31.39
TOTAL DUE: $188.36
`;

const result = await model.withStructuredOutput(Invoice).invoke(
  `Extract the invoice data:\n\n${TEXT}`
);

console.log(JSON.stringify(result, null, 2));

// You can now VALIDATE the model's arithmetic — a real production check:
const computed = result.lineItems.reduce((sum, i) => sum + i.quantity * i.unitPrice, 0);
const ok = Math.abs(computed - result.subtotal) < 0.01;
console.log(`\nsubtotal check: computed ${computed.toFixed(2)} vs stated ` +
            `${result.subtotal.toFixed(2)} ${ok ? "✅" : "❌ MISMATCH — flag for review"}`);
```

> 💡 That arithmetic check is the pattern to remember: **structured output makes the model's
> answer verifiable.** You can't cross-check a paragraph of prose; you can absolutely check
> whether line items sum to the stated subtotal.

### 4.4 Handling failure

```js
// day06-failure.js
import "dotenv/config";
import * as z from "zod";
import { ChatGroq } from "@langchain/groq";
import { ChatGoogleGenerativeAI } from "@langchain/google-genai";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });

const Schema = z.object({
  species: z.string().describe("The animal species mentioned"),
  count: z.number().int().describe("How many, or 0 if not stated"),
});

// ── includeRaw: inspect instead of throwing ──────────────────────────────
const safe = model.withStructuredOutput(Schema, { includeRaw: true });

for (const text of ["I saw three foxes in the garden.", "The weather is nice today."]) {
  const { raw, parsed } = await safe.invoke(text);
  if (parsed) {
    console.log(`✅ ${text.slice(0, 30)}… →`, parsed, `[${raw.usage_metadata?.total_tokens} tok]`);
  } else {
    console.log(`⚠️  ${text.slice(0, 30)}… → no structured output; model said: "${raw.text}"`);
  }
}

// ── retries + cross-provider fallback ────────────────────────────────────
const resilient = model
  .withStructuredOutput(Schema)
  .withRetry({ stopAfterAttempt: 3 })
  .withFallbacks([
    new ChatGoogleGenerativeAI({ model: "gemini-2.5-flash" }).withStructuredOutput(Schema),
  ]);

console.log(await resilient.invoke("Two cats sat on the wall."));
```

### 4.5 Streaming structured output

```js
// day06-streaming-structured.js
import "dotenv/config";
import * as z from "zod";
import { ChatGroq } from "@langchain/groq";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });

const Article = z.object({
  title: z.string().describe("A catchy title"),
  keyPoints: z.array(z.string()).describe("4 key points"),
  conclusion: z.string(),
});

const chain = model.withStructuredOutput(Article);

console.log("watch the object fill in:\n");
for await (const partial of await chain.stream("Write a short article about why sleep matters.")) {
  console.clear();
  console.log(JSON.stringify(partial, null, 2));   // each chunk is the ACCUMULATED object
}
```

### 4.6 The full pipeline: prompt → model → structured

```js
// day06-pipeline.js
import "dotenv/config";
import * as z from "zod";
import { ChatGroq } from "@langchain/groq";
import { ChatPromptTemplate } from "@langchain/core/prompts";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });

const Quiz = z.object({
  questions: z.array(z.object({
    question: z.string(),
    options: z.array(z.string()).length(4).describe("Exactly 4 options"),
    correctIndex: z.number().int().min(0).max(3).describe("0-based index of the correct option"),
    explanation: z.string().describe("Why the correct answer is correct"),
  })).describe("Exactly {n} questions"),
});

const prompt = ChatPromptTemplate.fromMessages([
  ["system", "You write multiple-choice quizzes for {level} learners. " +
             "Exactly one option must be correct. Distractors must be plausible."],
  ["human", "Create a {n}-question quiz about: {topic}"],
]);

const chain = prompt.pipe(model.withStructuredOutput(Quiz));   // ← prompt | model | schema

const quiz = await chain.invoke({ level: "beginner", n: 3, topic: "how HTTP works" });

quiz.questions.forEach((q, i) => {
  console.log(`\n${i + 1}. ${q.question}`);
  q.options.forEach((o, j) => console.log(`   ${j === q.correctIndex ? "✅" : "  "} ${o}`));
  console.log(`   → ${q.explanation}`);
});
```

---

## 5. Code — Python

```bash
pip install langchain langchain-groq pydantic python-dotenv
```

### 5.1 String and JSON parsers

```python
# day06_parsers.py
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import (
    StrOutputParser, JsonOutputParser, CommaSeparatedListOutputParser
)

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

# ── StrOutputParser (note: Str, not String, in Python) ───────────────────
prompt = ChatPromptTemplate.from_messages([("human", "Name one {thing}. One word only.")])

without_parser = prompt | model
with_parser    = prompt | model | StrOutputParser()

print(type(without_parser.invoke({"thing": "planet"})))   # AIMessage
print(type(with_parser.invoke({"thing": "planet"})))      # str ✅

# It also changes what streaming yields:
for c in with_parser.stream({"thing": "fruit"}):
    print(c, end="", flush=True)                          # strings, not chunks
print()

# ── JsonOutputParser ─────────────────────────────────────────────────────
json_chain = ChatPromptTemplate.from_messages([
    ("system", 'Extract data as JSON with keys "name" and "age". Output JSON only.'),
    ("human", "{text}"),
]) | model | JsonOutputParser()

print(json_chain.invoke({"text": "Wasif is 27 years old."}))
# {'name': 'Wasif', 'age': 27}   ← markdown fences are stripped automatically

# ── CommaSeparatedListOutputParser ───────────────────────────────────────
list_parser = CommaSeparatedListOutputParser()
list_chain = (
    ChatPromptTemplate.from_messages([("human", "List 5 {category}.\n{format_instructions}")])
    .partial(format_instructions=list_parser.get_format_instructions())
    | model | list_parser
)

print(list_chain.invoke({"category": "programming languages"}))
# ['Python', 'JavaScript', 'Java', 'C++', 'Go']
```

> ⚠️ **Naming difference:** Python's is `StrOutputParser`, JS's is `StringOutputParser`.
> Small, but it'll cost you a minute the first time.

### 5.2 `with_structured_output` — the main event

```python
# day06_structured.py
from dotenv import load_dotenv
from typing import Literal, Optional
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

class SupportTicket(BaseModel):
    """Classification of a customer support ticket."""

    # Reasoning FIRST — the model generates fields in order, so this is CoT.
    reasoning: str = Field(description="One sentence explaining your classification. Write this first.")

    category: Literal["BILLING", "BUG", "FEATURE", "OTHER"] = Field(
        description="The primary category of the ticket")

    urgency: Literal["low", "medium", "high", "critical"] = Field(
        description="critical = users cannot use the product at all")

    summary: str = Field(description="The issue in under 15 words")

    affected_feature: Optional[str] = Field(
        None, description="The specific feature mentioned, or null if none is named")

    customer_sentiment: Literal["calm", "frustrated", "angry"]

    confidence: float = Field(ge=0, le=1, description="Your confidence, 0 to 1")

classifier = model.with_structured_output(SupportTicket)

TICKETS = [
    "URGENT!!! Nobody on my team can log in since the update. We have a demo in 20 minutes.",
    "Hey, would be lovely if you added a dark mode at some point. No rush!",
    "I've been charged £49 twice this month and support hasn't replied in 6 days.",
    "hi",
]

for t in TICKETS:
    r = classifier.invoke(t)
    print(f'\n"{t[:50]}..."')
    print(f"  {r.category}/{r.urgency} · {r.customer_sentiment} · conf={r.confidence}")
    print(f"  summary: {r.summary}")
    print(f"  feature: {r.affected_feature or '(none)'}")
    if r.confidence < 0.7:
        print("  ⚠️  low confidence → route to human")
```

> 💡 **The docstring is not decoration.** In Python, a Pydantic model's docstring becomes the
> schema's top-level `description`, which is sent to the model. Always write one.

### 5.3 Nested schemas — invoice extraction

```python
# day06_nested.py
from dotenv import load_dotenv
from typing import Literal, Optional
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

class LineItem(BaseModel):
    description: str
    quantity: int
    unit_price: float = Field(description="Price per unit, excluding tax")

class Invoice(BaseModel):
    """A parsed supplier invoice."""
    vendor: str
    invoice_number: Optional[str] = None
    date: Optional[str] = Field(None, description="ISO 8601 date (YYYY-MM-DD), or null if absent")
    currency: Literal["USD", "EUR", "GBP", "PKR", "OTHER"]
    line_items: list[LineItem] = Field(description="Every line item listed")
    subtotal: float
    tax: Optional[float] = None
    total: float

TEXT = """
ACME SUPPLIES LTD
Invoice #INV-2024-0891    Date: 14 March 2024

Widget A          x12    @ $4.50
Gizmo Pro         x3     @ $29.99
Shipping          x1     @ $12.00

Subtotal: $156.97
VAT (20%): $31.39
TOTAL DUE: $188.36
"""

result = model.with_structured_output(Invoice).invoke(f"Extract the invoice data:\n\n{TEXT}")
print(result.model_dump_json(indent=2))

# You can now VALIDATE the model's arithmetic — a real production check:
computed = sum(i.quantity * i.unit_price for i in result.line_items)
ok = abs(computed - result.subtotal) < 0.01
print(f"\nsubtotal check: computed {computed:.2f} vs stated {result.subtotal:.2f} "
      f"{'✅' if ok else '❌ MISMATCH — flag for review'}")
```

### 5.4 Handling failure

```python
# day06_failure.py
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

class Sighting(BaseModel):
    """An animal sighting."""
    species: str = Field(description="The animal species mentioned")
    count: int = Field(description="How many, or 0 if not stated")

# ── include_raw: inspect instead of throwing ─────────────────────────────
safe = model.with_structured_output(Sighting, include_raw=True)

for text in ["I saw three foxes in the garden.", "The weather is nice today."]:
    out = safe.invoke(text)
    raw, parsed = out["raw"], out["parsed"]
    if parsed:
        tokens = (raw.usage_metadata or {}).get("total_tokens")
        print(f"✅ {text[:30]}… → {parsed} [{tokens} tok]")
    else:
        print(f'⚠️  {text[:30]}… → no structured output; model said: "{raw.content}"')

# ── retries + cross-provider fallback ────────────────────────────────────
resilient = (
    model.with_structured_output(Sighting)
    .with_retry(stop_after_attempt=3)
    .with_fallbacks([
        ChatGoogleGenerativeAI(model="gemini-2.5-flash").with_structured_output(Sighting)
    ])
)

print(resilient.invoke("Two cats sat on the wall."))
```

### 5.5 Streaming structured output

```python
# day06_streaming_structured.py
import json
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

class Article(BaseModel):
    """A short article."""
    title: str = Field(description="A catchy title")
    key_points: list[str] = Field(description="4 key points")
    conclusion: str

chain = model.with_structured_output(Article)

print("watch the object fill in:\n")
for partial in chain.stream("Write a short article about why sleep matters."):
    # Each chunk is the ACCUMULATED object (a dict while incomplete).
    print(json.dumps(partial if isinstance(partial, dict) else partial.model_dump(), indent=2))
    print("---")
```

### 5.6 The full pipeline: prompt → model → structured

```python
# day06_pipeline.py
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

class Question(BaseModel):
    question: str
    options: list[str] = Field(description="Exactly 4 options", min_length=4, max_length=4)
    correct_index: int = Field(ge=0, le=3, description="0-based index of the correct option")
    explanation: str = Field(description="Why the correct answer is correct")

class Quiz(BaseModel):
    """A multiple-choice quiz."""
    questions: list[Question]

prompt = ChatPromptTemplate.from_messages([
    ("system", "You write multiple-choice quizzes for {level} learners. "
               "Exactly one option must be correct. Distractors must be plausible."),
    ("human", "Create a {n}-question quiz about: {topic}"),
])

chain = prompt | model.with_structured_output(Quiz)      # ← prompt | model | schema

quiz = chain.invoke({"level": "beginner", "n": 3, "topic": "how HTTP works"})

for i, q in enumerate(quiz.questions, 1):
    print(f"\n{i}. {q.question}")
    for j, o in enumerate(q.options):
        print(f"   {'✅' if j == q.correct_index else '  '} {o}")
    print(f"   → {q.explanation}")
```

### 🔁 JS ↔ Python differences you just saw

| | JavaScript | Python |
|---|---|---|
| Schema library | Zod | Pydantic |
| String parser | `StringOutputParser` | `StrOutputParser` ⚠️ |
| Method | `withStructuredOutput(S)` | `with_structured_output(S)` |
| Raw included | `{ includeRaw: true }` → `{raw, parsed}` | `include_raw=True` → `{"raw", "parsed"}` |
| Return type | plain object | Pydantic model instance (use `.model_dump()` for a dict) |
| Field description | `.describe("...")` | `Field(description="...")` |
| Schema description | schema-level `.describe()` | the **class docstring** |
| Enum | `z.enum([...])` | `Literal[...]` |
| Nullable | `.nullable()` | `Optional[X] = None` |
| Array length | `.length(4)` | `Field(min_length=4, max_length=4)` |
| Import path | `@langchain/core/output_parsers` | `langchain_core.output_parsers` |

---

## 6. Under the hood

### What `withStructuredOutput` actually builds

```
model.withStructuredOutput(PersonSchema)
        │
        ▼
 1. Convert Zod/Pydantic → JSON Schema
    {
      "type": "object",
      "properties": {
        "name": { "type": "string", "description": "The person's full name" },
        "age":  { "type": "integer", "description": "Age in years" }
      },
      "required": ["name", "age"]
    }
        │
        ▼
 2. Bind it as a TOOL and force the model to call it
    tools: [{ type:"function", function:{ name:"PersonSchema", parameters: <schema> }}]
    tool_choice: { type:"function", function:{ name:"PersonSchema" }}
        │                                       ↑ forced, not "auto"
        ▼
 3. The provider constrains generation to schema-valid tokens
        │
        ▼
 4. Response comes back as a tool_call, not content:
    tool_calls: [{ name:"PersonSchema", args:{ name:"Wasif", age:27 }}]
        │
        ▼
 5. Extract .args, validate against the original schema, return the typed object
```

**Everything you learned about tool calling on Day 02 is what's happening here.** Structured
output isn't a separate feature — it's tool calling with exactly one forced tool, where you
throw away the "execute the function" part and keep the arguments.

That's why:
- Providers without tool support fall back to JSON mode
- Field descriptions matter (they're tool parameter descriptions → prompt text)
- Deeply nested schemas degrade (the constraint gets harder to satisfy)
- It composes with `.withRetry()` and `.withFallbacks()` — it's still just a `Runnable`

### Why field order affects quality

The model generates the JSON **left to right, one token at a time** (Day 01). So:

```js
{ label: ..., reasoning: ... }   // commits to a label, THEN rationalises it
{ reasoning: ..., label: ... }   // reasons, THEN commits  ← better
```

This is chain-of-thought expressed in a schema. It costs a few output tokens and measurably
improves classification accuracy on hard cases. Put `reasoning` first, always.

### Why `JsonOutputParser` handles markdown fences

Models trained on lots of markdown will wrap JSON in fences roughly 1 call in 20:

````
```json
{"name": "Wasif"}
```
````

`JsonOutputParser` strips fences, trims prose before/after, and handles partial JSON while
streaming. That's ~50 lines of edge cases you'd otherwise rediscover in production, one bug at
a time.

<details>
<summary>📜 Legacy note: older parsing approaches</summary>

| Legacy pattern | Modern replacement |
|---|---|
| `StructuredOutputParser.fromZodSchema()` + `getFormatInstructions()` in the prompt | `withStructuredOutput()` |
| `PydanticOutputParser` + format instructions | `with_structured_output()` |
| `OutputFixingParser` wrapping a parser | `.withRetry()` on the structured chain |
| Manual `JSON.parse` + try/catch | `JsonOutputParser` |

The old way put format instructions **in the prompt** ("Respond with JSON matching this
schema: ...") and hoped. The new way puts the schema **in the API request** as a constraint.
That's the difference between asking and enforcing — and it's a good interview answer to
"how has structured output evolved?"

You'll still meet `StructuredOutputParser` where a provider lacks tool support, and
`OutputFixingParser` is still the right tool when you're parsing output you didn't generate.
</details>

---

## 7. Common mistakes

**❌ Schema fields with no descriptions**

```js
z.object({ x: z.string(), y: z.number(), z: z.boolean() })
```
The model gets field names and types only. ✅ Describe every field — those strings go into the prompt.

---

**❌ Free-form strings where an enum belongs**

```js
priority: z.string()      // "high", "High", "HIGH", "very high", "P1"
priority: z.enum(["low", "medium", "high"])   // ✅ only three possible values
```

---

**❌ Required fields that the input may not contain**

```js
phoneNumber: z.string()   // model MUST produce one → it invents one
```
✅ `.nullable().describe("...or null if not present")`. Give it an honest way out.

---

**❌ Putting `reasoning` last**

The model commits to an answer and then rationalises. ✅ Reasoning first.

---

**❌ Very deep nesting**

```js
z.object({ a: z.object({ b: z.object({ c: z.object({ d: ... }) }) }) })
```
Accuracy falls off a cliff. ✅ Flatten, or split into multiple calls and assemble in code.

---

**❌ Assuming structured output can never fail**

```js
const r = await chain.invoke(text);
db.insert(r);                          // throws on refusal, timeout, or empty input
```
✅ `includeRaw: true`, or wrap with retry + fallback, and validate business rules (like the
invoice arithmetic check) before writing to a database.

---

**❌ `temperature: 0.7` for extraction**

Extraction has one right answer. ✅ `temperature: 0`.

---

**❌ Forgetting the Pydantic docstring**

```python
class Invoice(BaseModel):     # no docstring → no top-level schema description
```
✅ Write one. It's sent to the model as the tool description.

---

## 8. Exercises

### Exercise 1 — Replace a regex with a schema ●○○○○

Take the Day 02 chain-of-thought exercise (where you regexed `ANSWER: (\d+)` out of the
response) and rewrite it with `withStructuredOutput`, using a schema with `reasoning` (string),
`answer` (number), and `confidence` (0–1). Run it on 5 word problems and show it never fails to
parse.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import "dotenv/config";
import * as z from "zod";
import { ChatGroq } from "@langchain/groq";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });

const Solution = z.object({
  reasoning: z.string().describe("Step-by-step working. Write this FIRST, before the answer."),
  answer: z.number().describe("The final numeric answer"),
  confidence: z.number().min(0).max(1).describe("How confident you are, 0 to 1"),
});

const solver = model.withStructuredOutput(Solution);

const PROBLEMS = [
  ["A shop has 23 apples, sells 7, buys 3 crates of 12. How many?", 52],
  ["15% of 240?", 36],
  ["3 painters paint 3 rooms in 3 hours. How many hours for 9 painters to paint 9 rooms?", 3],
  ["A book has 300 pages. I read 40/day for 5 days, then 25/day. Total days?", 9],
  ["A train travels 240km at 80km/h, then 150km at 50km/h. Total hours?", 6],
];

let correct = 0;
for (const [problem, expected] of PROBLEMS) {
  const r = await solver.invoke(problem);
  const ok = Math.abs(r.answer - expected) < 0.01;
  correct += ok ? 1 : 0;
  console.log(`${ok ? "✅" : "❌"} ${String(r.answer).padEnd(8)} (want ${expected}) ` +
              `conf=${r.confidence}`);
  if (!ok) console.log(`     reasoning: ${r.reasoning.slice(0, 100)}…`);
}
console.log(`\n${correct}/${PROBLEMS.length} correct — parse failures: 0`);
```

**Python**
```python
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

class Solution(BaseModel):
    """The worked solution to a word problem."""
    reasoning: str = Field(description="Step-by-step working. Write this FIRST, before the answer.")
    answer: float = Field(description="The final numeric answer")
    confidence: float = Field(ge=0, le=1, description="How confident you are, 0 to 1")

solver = model.with_structured_output(Solution)

PROBLEMS = [
    ("A shop has 23 apples, sells 7, buys 3 crates of 12. How many?", 52),
    ("15% of 240?", 36),
    ("3 painters paint 3 rooms in 3 hours. How many hours for 9 painters to paint 9 rooms?", 3),
    ("A book has 300 pages. I read 40/day for 5 days, then 25/day. Total days?", 9),
    ("A train travels 240km at 80km/h, then 150km at 50km/h. Total hours?", 6),
]

correct = 0
for problem, expected in PROBLEMS:
    r = solver.invoke(problem)
    ok = abs(r.answer - expected) < 0.01
    correct += ok
    print(f"{'✅' if ok else '❌'} {r.answer:<8} (want {expected}) conf={r.confidence}")
    if not ok:
        print(f"     reasoning: {r.reasoning[:100]}…")

print(f"\n{correct}/{len(PROBLEMS)} correct — parse failures: 0")
```

**Two wins to notice.** First, zero parse failures — that entire error class is gone. Second,
you got CoT *for free*: `reasoning` is generated before `answer`, so the model works through the
problem, and you also get the working available for debugging when it's wrong. On Day 02 you
had to choose between clean output and visible reasoning. Now you have both.
</details>

---

### Exercise 2 — Schema design bake-off ●●○○○

Design three versions of a "meeting notes extractor" schema:
- **v1**: all strings, no descriptions
- **v2**: enums, descriptions, nullable optional fields
- **v3**: v2 + a `reasoning` field first + a `confidence` field

Run all three on the same 3 messy meeting transcripts. Compare: hallucinated values, format
consistency, and usefulness of output.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import "dotenv/config";
import * as z from "zod";
import { ChatGroq } from "@langchain/groq";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });

const V1 = z.object({
  title: z.string(),
  attendees: z.string(),
  decisions: z.string(),
  nextMeeting: z.string(),
  priority: z.string(),
});

const V2 = z.object({
  title: z.string().describe("Short descriptive title of the meeting"),
  attendees: z.array(z.string()).describe("Names of people who spoke or were named as present"),
  decisions: z.array(z.string()).describe("Concrete decisions made. Empty array if none."),
  nextMeeting: z.string().nullable()
    .describe("ISO date of the next meeting, or null if not mentioned"),
  priority: z.enum(["low", "medium", "high"])
    .describe("How urgent the follow-ups are"),
});

const V3 = z.object({
  reasoning: z.string()
    .describe("Brief note on what was clear vs ambiguous in the transcript. Write this first."),
  title: z.string().describe("Short descriptive title of the meeting"),
  attendees: z.array(z.string()).describe("Names of people who spoke or were named as present"),
  decisions: z.array(z.string()).describe("Concrete decisions made. Empty array if none."),
  nextMeeting: z.string().nullable()
    .describe("ISO date of the next meeting, or null if not mentioned"),
  priority: z.enum(["low", "medium", "high"]),
  confidence: z.number().min(0).max(1)
    .describe("Confidence that this extraction is complete and accurate"),
});

const TRANSCRIPTS = [
  `Sara: ok so we're agreed, we ship the search rewrite before the conference.
   Tom: agreed. I'll own the migration.
   Sara: great. same time next Tuesday?`,

  `[recording starts mid-sentence] ...and that's basically it. any questions? no? cool.`,

  `Ali: the vendor quote came in at 40k.
   Priya: that's over budget. can we negotiate?
   Ali: I'll try. Not sure they'll move.
   Priya: let's park it until we hear back.`,
];

for (const [name, schema] of [["V1", V1], ["V2", V2], ["V3", V3]]) {
  console.log(`\n${"═".repeat(60)}\n${name}\n${"═".repeat(60)}`);
  const extractor = model.withStructuredOutput(schema);

  for (const [i, t] of TRANSCRIPTS.entries()) {
    try {
      const r = await extractor.invoke(`Extract meeting notes:\n\n${t}`);
      console.log(`\ntranscript ${i + 1}:`);
      console.log(JSON.stringify(r, null, 2).split("\n").map((l) => "  " + l).join("\n"));
    } catch (e) {
      console.log(`\ntranscript ${i + 1}: ❌ ${e.message.slice(0, 60)}`);
    }
  }
}
```

**Python**
```python
import json
from dotenv import load_dotenv
from typing import Literal, Optional
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

class V1(BaseModel):
    title: str
    attendees: str
    decisions: str
    next_meeting: str
    priority: str

class V2(BaseModel):
    """Structured notes extracted from a meeting transcript."""
    title: str = Field(description="Short descriptive title of the meeting")
    attendees: list[str] = Field(description="Names of people who spoke or were named as present")
    decisions: list[str] = Field(description="Concrete decisions made. Empty list if none.")
    next_meeting: Optional[str] = Field(
        None, description="ISO date of the next meeting, or null if not mentioned")
    priority: Literal["low", "medium", "high"] = Field(
        description="How urgent the follow-ups are")

class V3(BaseModel):
    """Structured notes extracted from a meeting transcript, with self-assessment."""
    reasoning: str = Field(
        description="Brief note on what was clear vs ambiguous in the transcript. Write this first.")
    title: str = Field(description="Short descriptive title of the meeting")
    attendees: list[str] = Field(description="Names of people who spoke or were named as present")
    decisions: list[str] = Field(description="Concrete decisions made. Empty list if none.")
    next_meeting: Optional[str] = Field(
        None, description="ISO date of the next meeting, or null if not mentioned")
    priority: Literal["low", "medium", "high"]
    confidence: float = Field(
        ge=0, le=1, description="Confidence that this extraction is complete and accurate")

TRANSCRIPTS = [
    """Sara: ok so we're agreed, we ship the search rewrite before the conference.
Tom: agreed. I'll own the migration.
Sara: great. same time next Tuesday?""",

    "[recording starts mid-sentence] ...and that's basically it. any questions? no? cool.",

    """Ali: the vendor quote came in at 40k.
Priya: that's over budget. can we negotiate?
Ali: I'll try. Not sure they'll move.
Priya: let's park it until we hear back.""",
]

for name, schema in [("V1", V1), ("V2", V2), ("V3", V3)]:
    print(f"\n{'═' * 60}\n{name}\n{'═' * 60}")
    extractor = model.with_structured_output(schema)

    for i, t in enumerate(TRANSCRIPTS, 1):
        try:
            r = extractor.invoke(f"Extract meeting notes:\n\n{t}")
            body = json.dumps(r.model_dump(), indent=2)
            print(f"\ntranscript {i}:")
            print("\n".join("  " + line for line in body.split("\n")))
        except Exception as e:
            print(f"\ntranscript {i}: ❌ {str(e)[:60]}")
```

**What you should see:**

| | V1 | V2 | V3 |
|---|---|---|---|
| `attendees` | `"Sara, Tom"` — a string you must re-parse | `["Sara","Tom"]` ✅ | `["Sara","Tom"]` ✅ |
| `nextMeeting` on transcript 2 | invented a date, or `"N/A"`, or `"none"` | `null` ✅ | `null` ✅ |
| `priority` | `"High"`, `"medium-high"`, `"P2"` — inconsistent | one of three values ✅ | ✅ |
| Empty transcript | hallucinated a whole meeting | mostly empty, some invention | low `confidence` flags it ✅ |

**The headline lesson:** V1 → V2 is the biggest jump, and it costs nothing but a few minutes of
schema design. `nullable` + descriptions eliminate most hallucinated fields, because you've made
"I don't know" a *representable* answer. V3's confidence field then gives you an automatic
routing signal for the cases that are still wrong.
</details>

---

### Exercise 3 — Extraction with validation rules ●●●○○

Build a receipt extractor where the schema captures line items and totals, then add **business
rule validation in code**: line items must sum to the subtotal, tax must be 0–30% of subtotal,
and total must equal subtotal + tax. Report each violation. Test on a receipt with a
deliberate arithmetic error.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import "dotenv/config";
import * as z from "zod";
import { ChatGroq } from "@langchain/groq";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });

const Receipt = z.object({
  merchant: z.string(),
  date: z.string().nullable().describe("ISO date YYYY-MM-DD, or null"),
  lineItems: z.array(z.object({
    name: z.string(),
    quantity: z.number().int(),
    unitPrice: z.number().describe("Price for ONE unit"),
  })),
  subtotal: z.number().describe("Sum of line items before tax, as printed"),
  tax: z.number().describe("Tax amount as printed, 0 if none"),
  total: z.number().describe("Final total as printed"),
});

function validate(r) {
  const violations = [];
  const near = (a, b, tol = 0.02) => Math.abs(a - b) <= tol;

  const computed = r.lineItems.reduce((s, i) => s + i.quantity * i.unitPrice, 0);
  if (!near(computed, r.subtotal))
    violations.push(`line items sum to ${computed.toFixed(2)} but subtotal is ${r.subtotal.toFixed(2)}`);

  const taxRate = r.subtotal > 0 ? r.tax / r.subtotal : 0;
  if (taxRate < 0 || taxRate > 0.30)
    violations.push(`tax rate ${(taxRate * 100).toFixed(1)}% is outside 0–30%`);

  if (!near(r.subtotal + r.tax, r.total))
    violations.push(`subtotal + tax = ${(r.subtotal + r.tax).toFixed(2)} but total is ${r.total.toFixed(2)}`);

  if (r.lineItems.length === 0) violations.push("no line items extracted");

  return violations;
}

const RECEIPTS = {
  clean: `CORNER CAFE  2024-05-12
    Latte        x2  @ 3.50
    Croissant    x1  @ 2.80
    Subtotal: 9.80
    Tax:      0.98
    TOTAL:   10.78`,

  broken: `QUICK MART  2024-05-13
    Bread        x1  @ 2.20
    Milk         x2  @ 1.40
    Eggs         x1  @ 3.10
    Subtotal: 12.00        <-- wrong, should be 8.10
    Tax:      4.50         <-- 37.5%, implausible
    TOTAL:   15.00         <-- doesn't add up either`,
};

const extractor = model.withStructuredOutput(Receipt);

for (const [name, text] of Object.entries(RECEIPTS)) {
  const r = await extractor.invoke(`Extract this receipt EXACTLY as printed:\n\n${text}`);
  const violations = validate(r);

  console.log(`\n═══ ${name} ═══`);
  console.log(`  ${r.merchant} · ${r.lineItems.length} items · ` +
              `${r.subtotal.toFixed(2)} + ${r.tax.toFixed(2)} = ${r.total.toFixed(2)}`);

  if (violations.length === 0) console.log("  ✅ all checks passed → safe to auto-post");
  else {
    console.log(`  ❌ ${violations.length} violation(s) → route to human review`);
    violations.forEach((v) => console.log(`     · ${v}`));
  }
}
```

**Python**
```python
from dotenv import load_dotenv
from typing import Optional
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

class LineItem(BaseModel):
    name: str
    quantity: int
    unit_price: float = Field(description="Price for ONE unit")

class Receipt(BaseModel):
    """A retail receipt, transcribed exactly as printed."""
    merchant: str
    date: Optional[str] = Field(None, description="ISO date YYYY-MM-DD, or null")
    line_items: list[LineItem]
    subtotal: float = Field(description="Sum of line items before tax, as printed")
    tax: float = Field(description="Tax amount as printed, 0 if none")
    total: float = Field(description="Final total as printed")

def validate(r: Receipt) -> list[str]:
    violations = []
    near = lambda a, b, tol=0.02: abs(a - b) <= tol

    computed = sum(i.quantity * i.unit_price for i in r.line_items)
    if not near(computed, r.subtotal):
        violations.append(f"line items sum to {computed:.2f} but subtotal is {r.subtotal:.2f}")

    tax_rate = r.tax / r.subtotal if r.subtotal > 0 else 0
    if not 0 <= tax_rate <= 0.30:
        violations.append(f"tax rate {tax_rate * 100:.1f}% is outside 0–30%")

    if not near(r.subtotal + r.tax, r.total):
        violations.append(
            f"subtotal + tax = {r.subtotal + r.tax:.2f} but total is {r.total:.2f}")

    if not r.line_items:
        violations.append("no line items extracted")

    return violations

RECEIPTS = {
    "clean": """CORNER CAFE  2024-05-12
    Latte        x2  @ 3.50
    Croissant    x1  @ 2.80
    Subtotal: 9.80
    Tax:      0.98
    TOTAL:   10.78""",

    "broken": """QUICK MART  2024-05-13
    Bread        x1  @ 2.20
    Milk         x2  @ 1.40
    Eggs         x1  @ 3.10
    Subtotal: 12.00        <-- wrong, should be 8.10
    Tax:      4.50         <-- 37.5%, implausible
    TOTAL:   15.00         <-- doesn't add up either""",
}

extractor = model.with_structured_output(Receipt)

for name, text in RECEIPTS.items():
    r = extractor.invoke(f"Extract this receipt EXACTLY as printed:\n\n{text}")
    violations = validate(r)

    print(f"\n═══ {name} ═══")
    print(f"  {r.merchant} · {len(r.line_items)} items · "
          f"{r.subtotal:.2f} + {r.tax:.2f} = {r.total:.2f}")

    if not violations:
        print("  ✅ all checks passed → safe to auto-post")
    else:
        print(f"  ❌ {len(violations)} violation(s) → route to human review")
        for v in violations:
            print(f"     · {v}")
```

**The architectural point, and it's the important one for interviews:**

Schema validation checks the *shape*. It cannot check the *meaning*. `subtotal: 12.00` is a
perfectly valid float — Zod and Pydantic have no opinion about whether it's the right float.

So production extraction pipelines have **two layers**:
1. **Schema** — guarantees the shape (types, enums, required fields). Handled by the framework.
2. **Business rules** — guarantee the semantics (arithmetic, ranges, cross-field consistency,
   referential integrity against your database). Your code, always.

The output of layer 2 isn't just pass/fail — it's a *routing decision*. Clean receipts auto-post;
violating ones go to a human queue. That's how you get automation benefits without automation
risk, and it's the same idea as Day 21's human-in-the-loop, applied at the data layer.
</details>

---

### Exercise 4 — Graceful degradation ●●●○○

Build `extractSafely(text, schema)` that tries, in order: (1) structured output on the primary
model, (2) retry, (3) fallback to a second provider, (4) JSON mode + `JsonOutputParser`,
(5) return `null` with a reason. Log which tier succeeded. Test by breaking the primary model's
API key.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import "dotenv/config";
import * as z from "zod";
import { ChatGroq } from "@langchain/groq";
import { ChatGoogleGenerativeAI } from "@langchain/google-genai";
import { ChatPromptTemplate } from "@langchain/core/prompts";
import { JsonOutputParser } from "@langchain/core/output_parsers";

const Contact = z.object({
  name: z.string().describe("Full name"),
  email: z.string().nullable().describe("Email address, or null"),
  company: z.string().nullable().describe("Company name, or null"),
});

async function extractSafely(text, schema, { primary, secondary }) {
  const attempts = [
    {
      tier: "1-structured-primary",
      run: () => primary.withStructuredOutput(schema).invoke(text),
    },
    {
      tier: "2-structured-primary-retry",
      run: () => primary.withStructuredOutput(schema)
                        .withRetry({ stopAfterAttempt: 3 }).invoke(text),
    },
    {
      tier: "3-structured-fallback-provider",
      run: () => secondary.withStructuredOutput(schema).invoke(text),
    },
    {
      tier: "4-json-mode-and-parse",
      run: async () => {
        const jsonSchema = JSON.stringify(z.toJSONSchema(schema));
        const chain = ChatPromptTemplate.fromMessages([
          ["system",
           "Extract data and respond with JSON ONLY, matching this JSON Schema:\n" +
           jsonSchema.replace(/{/g, "{{").replace(/}/g, "}}")],   // ← escape braces!
          ["human", "{text}"],
        ]).pipe(secondary).pipe(new JsonOutputParser());

        const raw = await chain.invoke({ text });
        return schema.parse(raw);          // validate ourselves
      },
    },
  ];

  const errors = [];
  for (const { tier, run } of attempts) {
    try {
      const data = await run();
      return { ok: true, tier, data, errors };
    } catch (err) {
      errors.push(`${tier}: ${err.message.slice(0, 70)}`);
    }
  }
  return { ok: false, tier: "5-gave-up", data: null, errors };
}

// ── test: primary is deliberately broken ─────────────────────────────────
const broken = new ChatGroq({ model: "llama-3.3-70b-versatile", apiKey: "gsk_invalid" });
const working = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0 });
const gemini = new ChatGoogleGenerativeAI({ model: "gemini-2.5-flash", temperature: 0 });

const TEXT = "Reach out to Aisha Khan (aisha@northwind.co) who leads eng at Northwind Labs.";

console.log("── healthy primary ──");
console.log(await extractSafely(TEXT, Contact, { primary: working, secondary: gemini }));

console.log("\n── broken primary ──");
const r = await extractSafely(TEXT, Contact, { primary: broken, secondary: gemini });
console.log(`succeeded at tier: ${r.tier}`);
console.log("data:", r.data);
console.log("failures along the way:");
r.errors.forEach((e) => console.log("  ·", e));
```

**Python**
```python
import json
from dotenv import load_dotenv
from typing import Optional
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

load_dotenv()

class Contact(BaseModel):
    """A person's contact details."""
    name: str = Field(description="Full name")
    email: Optional[str] = Field(None, description="Email address, or null")
    company: Optional[str] = Field(None, description="Company name, or null")

def extract_safely(text, schema, primary, secondary):
    def tier4():
        json_schema = json.dumps(schema.model_json_schema())
        chain = ChatPromptTemplate.from_messages([
            ("system",
             "Extract data and respond with JSON ONLY, matching this JSON Schema:\n"
             + json_schema.replace("{", "{{").replace("}", "}}")),   # ← escape braces!
            ("human", "{text}"),
        ]) | secondary | JsonOutputParser()
        return schema.model_validate(chain.invoke({"text": text}))

    attempts = [
        ("1-structured-primary",
         lambda: primary.with_structured_output(schema).invoke(text)),
        ("2-structured-primary-retry",
         lambda: primary.with_structured_output(schema)
                        .with_retry(stop_after_attempt=3).invoke(text)),
        ("3-structured-fallback-provider",
         lambda: secondary.with_structured_output(schema).invoke(text)),
        ("4-json-mode-and-parse", tier4),
    ]

    errors = []
    for tier, run in attempts:
        try:
            return {"ok": True, "tier": tier, "data": run(), "errors": errors}
        except Exception as err:
            errors.append(f"{tier}: {str(err)[:70]}")

    return {"ok": False, "tier": "5-gave-up", "data": None, "errors": errors}


# ── test: primary is deliberately broken ─────────────────────────────────
broken  = ChatGroq(model="llama-3.3-70b-versatile", api_key="gsk_invalid")
working = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
gemini  = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)

TEXT = "Reach out to Aisha Khan (aisha@northwind.co) who leads eng at Northwind Labs."

print("── healthy primary ──")
print(extract_safely(TEXT, Contact, working, gemini))

print("\n── broken primary ──")
r = extract_safely(TEXT, Contact, broken, gemini)
print(f"succeeded at tier: {r['tier']}")
print("data:", r["data"])
print("failures along the way:")
for e in r["errors"]:
    print("  ·", e)
```

**Two things worth stealing from this for real systems:**

1. **Return the tier, don't just return the data.** If tier 3 starts firing on 40% of requests,
   your primary provider is degraded and nobody would know — the system silently "works". Emit
   the tier as a metric and alert on the distribution shifting. Silent fallback is how outages
   hide for a week.

2. **Notice the brace escaping in tier 4.** You're embedding a JSON Schema *into a prompt
   template*, and JSON is full of `{`. That's yesterday's lesson biting exactly where you'd
   expect. It's also a good argument for staying at tier 1–3 whenever possible: tier 4
   re-introduces every problem structured output was invented to remove.

**A note on tier ordering:** tier 2 (retry the primary) before tier 3 (switch provider) is
deliberate — transient 429/500 errors are far more common than a genuinely broken provider, and
retrying is cheaper than a cross-provider call. But cap it: three retries on a hard 401 is three
wasted seconds. That's why Day 03's retry wrapper checked whether the status was retryable at all.
</details>

---

### Exercise 5 — StudyBuddy quiz engine ●●●●○

Build a quiz generator that: takes a topic and difficulty, produces N questions with 4 options
each via structured output, validates that `correctIndex` is in range and that options are
distinct, runs an interactive CLI quiz, and produces a structured performance report at the end
(also via structured output) suggesting what to study next.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
// studybuddy-quiz.js
import "dotenv/config";
import readline from "node:readline/promises";
import * as z from "zod";
import { ChatGroq } from "@langchain/groq";
import { ChatPromptTemplate } from "@langchain/core/prompts";

const model = new ChatGroq({ model: "llama-3.3-70b-versatile", temperature: 0.4 });

// ── schemas ──────────────────────────────────────────────────────────────
const Question = z.object({
  question: z.string().describe("The question. Self-contained, no external references."),
  options: z.array(z.string()).length(4).describe("Exactly 4 distinct options"),
  correctIndex: z.number().int().min(0).max(3).describe("0-based index of the correct option"),
  explanation: z.string().describe("Why the correct answer is correct, in one sentence"),
  subTopic: z.string().describe("The specific sub-topic this question tests"),
});

const Quiz = z.object({
  questions: z.array(Question),
});

const Report = z.object({
  overallAssessment: z.string().describe("Two encouraging sentences about their performance"),
  strengths: z.array(z.string()).describe("Sub-topics they clearly understand. May be empty."),
  gaps: z.array(z.string()).describe("Sub-topics they got wrong and should review"),
  nextSteps: z.array(z.string()).describe("2-3 concrete, specific things to study next"),
  readinessScore: z.number().min(0).max(10)
    .describe("How ready they are to move on from this topic, 0-10"),
});

// ── generation + validation ──────────────────────────────────────────────
const quizPrompt = ChatPromptTemplate.fromMessages([
  ["system",
   "You write multiple-choice quizzes for {difficulty} learners.\n" +
   "Rules:\n" +
   "- Exactly one option is correct\n" +
   "- Distractors must be plausible, not obviously silly\n" +
   "- All 4 options must be distinct\n" +
   "- Vary which index is correct across questions"],
  ["human", "Write a {n}-question quiz about: {topic}"],
]);

function validateQuiz(quiz) {
  const problems = [];
  quiz.questions.forEach((q, i) => {
    if (q.options.length !== 4) problems.push(`Q${i + 1}: ${q.options.length} options, need 4`);
    if (new Set(q.options.map((o) => o.toLowerCase().trim())).size !== q.options.length)
      problems.push(`Q${i + 1}: duplicate options`);
    if (q.correctIndex < 0 || q.correctIndex >= q.options.length)
      problems.push(`Q${i + 1}: correctIndex ${q.correctIndex} out of range`);
  });

  // A quiz where every answer is "A" is a bad quiz, even if schema-valid.
  const indices = new Set(quiz.questions.map((q) => q.correctIndex));
  if (quiz.questions.length >= 3 && indices.size === 1)
    problems.push("all correct answers are at the same index");

  return problems;
}

async function generateQuiz(topic, difficulty, n, maxAttempts = 3) {
  const chain = quizPrompt.pipe(model.withStructuredOutput(Quiz));

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    const quiz = await chain.invoke({ topic, difficulty, n });
    const problems = validateQuiz(quiz);
    if (problems.length === 0) return quiz;
    console.log(`  (attempt ${attempt} rejected: ${problems.join("; ")})`);
  }
  throw new Error("Could not generate a valid quiz after 3 attempts");
}

// ── the CLI ──────────────────────────────────────────────────────────────
const rl = readline.createInterface({ input: process.stdin, output: process.stdout });

const topic = (await rl.question("Topic: ")) || "how HTTP works";
const difficulty = (await rl.question("Difficulty (beginner/intermediate/expert): ")) || "beginner";

console.log("\ngenerating…");
const quiz = await generateQuiz(topic, difficulty, 5);

const results = [];
for (const [i, q] of quiz.questions.entries()) {
  console.log(`\n${i + 1}. ${q.question}`);
  q.options.forEach((o, j) => console.log(`   ${"ABCD"[j]}) ${o}`));

  let choice = -1;
  while (choice < 0 || choice > 3) {
    const raw = (await rl.question("   your answer (A-D): ")).trim().toUpperCase();
    choice = "ABCD".indexOf(raw);
    if (choice < 0) console.log("   please enter A, B, C or D");
  }

  const correct = choice === q.correctIndex;
  console.log(correct
    ? `   ✅ correct`
    : `   ❌ correct answer was ${"ABCD"[q.correctIndex]}) ${q.options[q.correctIndex]}`);
  console.log(`   ${q.explanation}`);

  results.push({ subTopic: q.subTopic, question: q.question, correct });
}

// ── the report — structured output again ─────────────────────────────────
const score = results.filter((r) => r.correct).length;
console.log(`\n${"═".repeat(50)}\nScore: ${score}/${results.length}\n${"═".repeat(50)}`);

const reportChain = ChatPromptTemplate.fromMessages([
  ["system", "You are StudyBuddy. Analyse quiz performance and give specific, actionable advice. " +
             "Be encouraging but honest. Never suggest studying something they got right."],
  ["human", "Topic: {topic}\nDifficulty: {difficulty}\nScore: {score}/{total}\n\n" +
            "Per-question results:\n{results}"],
]).pipe(model.withStructuredOutput(Report));

const report = await reportChain.invoke({
  topic, difficulty, score, total: results.length,
  results: results.map((r) => `- [${r.correct ? "✓" : "✗"}] ${r.subTopic}: ${r.question}`).join("\n"),
});

console.log(`\n${report.overallAssessment}\n`);
if (report.strengths.length) console.log("💪 Strengths:", report.strengths.join(", "));
if (report.gaps.length)      console.log("📚 Review:   ", report.gaps.join(", "));
console.log("\n➡️  Next steps:");
report.nextSteps.forEach((s, i) => console.log(`   ${i + 1}. ${s}`));
console.log(`\nReadiness to move on: ${report.readinessScore}/10`);

rl.close();
```

**Python**
```python
# studybuddy_quiz.py
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.4)

# ── schemas ──────────────────────────────────────────────────────────────
class Question(BaseModel):
    question: str = Field(description="The question. Self-contained, no external references.")
    options: list[str] = Field(description="Exactly 4 distinct options",
                               min_length=4, max_length=4)
    correct_index: int = Field(ge=0, le=3, description="0-based index of the correct option")
    explanation: str = Field(description="Why the correct answer is correct, in one sentence")
    sub_topic: str = Field(description="The specific sub-topic this question tests")

class Quiz(BaseModel):
    """A multiple-choice quiz."""
    questions: list[Question]

class Report(BaseModel):
    """An assessment of a learner's quiz performance."""
    overall_assessment: str = Field(description="Two encouraging sentences about their performance")
    strengths: list[str] = Field(description="Sub-topics they clearly understand. May be empty.")
    gaps: list[str] = Field(description="Sub-topics they got wrong and should review")
    next_steps: list[str] = Field(description="2-3 concrete, specific things to study next")
    readiness_score: float = Field(
        ge=0, le=10, description="How ready they are to move on from this topic, 0-10")

# ── generation + validation ──────────────────────────────────────────────
quiz_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You write multiple-choice quizzes for {difficulty} learners.\n"
     "Rules:\n"
     "- Exactly one option is correct\n"
     "- Distractors must be plausible, not obviously silly\n"
     "- All 4 options must be distinct\n"
     "- Vary which index is correct across questions"),
    ("human", "Write a {n}-question quiz about: {topic}"),
])

def validate_quiz(quiz: Quiz) -> list[str]:
    problems = []
    for i, q in enumerate(quiz.questions, 1):
        if len(q.options) != 4:
            problems.append(f"Q{i}: {len(q.options)} options, need 4")
        if len({o.lower().strip() for o in q.options}) != len(q.options):
            problems.append(f"Q{i}: duplicate options")
        if not 0 <= q.correct_index < len(q.options):
            problems.append(f"Q{i}: correct_index {q.correct_index} out of range")

    # A quiz where every answer is "A" is a bad quiz, even if schema-valid.
    indices = {q.correct_index for q in quiz.questions}
    if len(quiz.questions) >= 3 and len(indices) == 1:
        problems.append("all correct answers are at the same index")

    return problems

def generate_quiz(topic, difficulty, n, max_attempts=3):
    chain = quiz_prompt | model.with_structured_output(Quiz)

    for attempt in range(1, max_attempts + 1):
        quiz = chain.invoke({"topic": topic, "difficulty": difficulty, "n": n})
        problems = validate_quiz(quiz)
        if not problems:
            return quiz
        print(f"  (attempt {attempt} rejected: {'; '.join(problems)})")

    raise RuntimeError("Could not generate a valid quiz after 3 attempts")

# ── the CLI ──────────────────────────────────────────────────────────────
topic = input("Topic: ") or "how HTTP works"
difficulty = input("Difficulty (beginner/intermediate/expert): ") or "beginner"

print("\ngenerating…")
quiz = generate_quiz(topic, difficulty, 5)

results = []
for i, q in enumerate(quiz.questions, 1):
    print(f"\n{i}. {q.question}")
    for j, o in enumerate(q.options):
        print(f"   {'ABCD'[j]}) {o}")

    choice = -1
    while choice < 0:
        raw = input("   your answer (A-D): ").strip().upper()
        choice = "ABCD".find(raw) if raw in "ABCD" and len(raw) == 1 else -1
        if choice < 0:
            print("   please enter A, B, C or D")

    correct = choice == q.correct_index
    if correct:
        print("   ✅ correct")
    else:
        print(f"   ❌ correct answer was {'ABCD'[q.correct_index]}) {q.options[q.correct_index]}")
    print(f"   {q.explanation}")

    results.append({"sub_topic": q.sub_topic, "question": q.question, "correct": correct})

# ── the report — structured output again ─────────────────────────────────
score = sum(r["correct"] for r in results)
print(f"\n{'═' * 50}\nScore: {score}/{len(results)}\n{'═' * 50}")

report_chain = ChatPromptTemplate.from_messages([
    ("system", "You are StudyBuddy. Analyse quiz performance and give specific, actionable advice. "
               "Be encouraging but honest. Never suggest studying something they got right."),
    ("human", "Topic: {topic}\nDifficulty: {difficulty}\nScore: {score}/{total}\n\n"
              "Per-question results:\n{results}"),
]) | model.with_structured_output(Report)

report = report_chain.invoke({
    "topic": topic, "difficulty": difficulty, "score": score, "total": len(results),
    "results": "\n".join(
        f"- [{'✓' if r['correct'] else '✗'}] {r['sub_topic']}: {r['question']}" for r in results),
})

print(f"\n{report.overall_assessment}\n")
if report.strengths:
    print("💪 Strengths:", ", ".join(report.strengths))
if report.gaps:
    print("📚 Review:   ", ", ".join(report.gaps))
print("\n➡️  Next steps:")
for i, s in enumerate(report.next_steps, 1):
    print(f"   {i}. {s}")
print(f"\nReadiness to move on: {report.readiness_score}/10")
```

**Three design decisions worth extracting:**

1. **Two structured calls, not one.** Generating the quiz and analysing performance are separate
   schemas because they happen at different times with different inputs. Trying to do both in one
   schema would mean generating the report before the user has answered anything.

2. **Validation catches what the schema can't.** `z.array(...).length(4)` guarantees four
   options; it cannot guarantee they're *different*, or that the correct answer isn't always A.
   Those are semantic rules, so they're code — same two-layer lesson as Exercise 3, and the
   retry loop turns a rejected generation into a regenerated one rather than a crash.

3. **`subTopic` is the field that makes the report useful.** Without it the report can only say
   "you got 3/5". With it, the model can say "you understand status codes but not caching
   headers" — because each question carries its own label. Adding one well-chosen field to a
   schema often unlocks a whole downstream feature.
</details>

---

## 9. Interview questions

### Basic

<details>
<summary><b>Q: What is an output parser?</b></summary>

A `Runnable` that transforms a model's output into something more useful — a plain string, a
parsed object, a list. It sits at the end of a chain: `prompt | model | parser`. Common ones are
`StringOutputParser` (extract text), `JsonOutputParser` (parse JSON, tolerating markdown
fences), and list parsers.
</details>

<details>
<summary><b>Q: What is structured output?</b></summary>

Getting a validated object matching a schema you define, rather than free text you must parse.
You define the schema in Zod or Pydantic and call `withStructuredOutput` /
`with_structured_output`. The schema is converted to JSON Schema and sent to the provider as a
constraint, so the model's output is shaped correctly by construction rather than by hope.
</details>

<details>
<summary><b>Q: What is Zod, and what's the Python equivalent?</b></summary>

Zod is a TypeScript-first runtime schema and validation library. Pydantic is the Python
equivalent. Both let you declare a schema once and use it for three things: runtime validation,
static types, and — critically here — generating the JSON Schema that gets sent to the model.
Field descriptions in either are sent to the model as prompt text.
</details>

<details>
<summary><b>Q: Why not just prompt "respond in JSON" and call JSON.parse?</b></summary>

It fails a few percent of the time, and the failures are the expensive kind: markdown code
fences, a leading "Sure, here's the JSON:", trailing commentary, or valid JSON with the wrong
keys. `JsonOutputParser` handles the formatting noise; only a schema constraint handles the
wrong-shape problem. At production volume, "a few percent" is a lot of 500s.
</details>

### Intermediate

<details>
<summary><b>Q: How does `withStructuredOutput` work under the hood?</b></summary>

It converts your Zod/Pydantic schema to JSON Schema, binds it to the model as a **tool
definition**, and forces `tool_choice` to that single tool. The provider then constrains
generation so the emitted arguments match the schema. The response arrives as a `tool_call`
rather than as content; LangChain extracts `.args`, validates against the original schema, and
returns the typed object.

So it's tool calling with one forced tool where you keep the arguments and never execute
anything. Providers without tool support fall back to JSON mode with the schema described in
the prompt — a weaker guarantee.
</details>

<details>
<summary><b>Q: Why does the order of fields in a schema matter?</b></summary>

The model generates the object left to right, one token at a time, each token conditioned on the
previous ones. A `reasoning` field placed **before** `label` means the model works through the
problem before committing to an answer — chain-of-thought inside the schema. Placed after, it
commits first and rationalises, which is measurably worse on hard cases. Same reason CoT works
at all: tokens are compute.
</details>

<details>
<summary><b>Q: How do you handle a field the input might not contain?</b></summary>

Make it nullable/optional and say so in the description: `.nullable().describe("...or null if
not stated")`. If the field is required, the model has no valid way to express "not present", so
it invents a value — this is one of the largest sources of hallucinated data in extraction
pipelines. Making "unknown" representable is the fix. Adding a `confidence` field on top gives
you a routing signal for the remaining low-quality cases.
</details>

<details>
<summary><b>Q: Structured output guarantees the shape. What does it NOT guarantee?</b></summary>

The meaning. `subtotal: 12.00` is schema-valid regardless of whether the line items actually sum
to 12.00. Schemas enforce types, enums, ranges and required fields; they cannot enforce
cross-field arithmetic, referential integrity against your database, or factual correctness.

Production extraction therefore has two layers: schema validation (framework) and business-rule
validation (your code). The second layer's output should drive routing — clean records
auto-process, violating ones go to human review.
</details>

### Advanced

<details>
<summary><b>Q: Design an extraction pipeline for 10,000 invoices/day that must be 99.5% accurate.</b></summary>

**Extraction** — structured output with a well-designed schema: nullable fields for anything
optional, enums for currency/status, a `reasoning` field first, a `confidence` field last,
`temperature: 0`. Batch with a concurrency cap to stay inside rate limits.

**Validation, in layers** — schema (framework), then business rules (line items sum to subtotal,
tax within a plausible band, total = subtotal + tax, date parseable and not in the future,
vendor resolvable against the supplier table). Each failing rule is a signal, not just a
rejection.

**Routing** — auto-post only when all rules pass *and* confidence is high. Everything else goes
to a human review queue, ordered by value at risk. This is how you get 99.5% end-to-end without
needing 99.5% from the model.

**Escalation** — cheap model first; on low confidence or rule violation, retry once with a
larger model before queuing for a human. Most teams find the small model handles 80–90% of
documents.

**Measurement** — a golden set of a few hundred hand-labelled invoices, field-level accuracy
(not document-level), run on every prompt/schema/model change. Track per-field error rates;
they're rarely uniform, and the fix for a bad `date` field is different from a bad `total`.

**Feedback loop** — human corrections in the review queue are labelled data. Feed them back as
few-shot examples (retrieved dynamically per input) and as new golden-set entries. This is what
actually moves you from 95% to 99.5%.

**Ops** — idempotency keys so a retry can't double-post; a dead-letter queue for repeated
failures; cost and latency dashboards per field; alerting on confidence-distribution drift,
which is your early warning that a provider changed a model underneath you.
</details>

<details>
<summary><b>Q: When would you NOT use structured output?</b></summary>

- **Free-form generation** — an essay, an explanation, a chat reply. Forcing it into a schema
  constrains the model unnecessarily and can hurt quality.
- **Streaming text to a UI** — you want tokens, not progressively complete objects. (Though
  structured output *can* stream partial objects when that's what you want.)
- **Providers without tool support** — you'd be on the weaker JSON-mode path, which sometimes
  isn't worth the added complexity versus a `JsonOutputParser`.
- **Very deep or highly variable shapes** — accuracy degrades with nesting depth. Split into
  multiple calls, or extract a flat shape and assemble in code.
- **When the schema constrains the answer wrongly** — a fixed enum forces the model to pick a
  category even when none fits. Always include an `OTHER` member plus a free-text field, or
  you'll get confidently miscategorised data.

There's also a subtler cost: a schema is a hypothesis about the data. If your schema says every
invoice has a `vendor`, you'll never discover the 2% that don't — you'll just get invented
vendors. Nullable fields and a `confidence` signal are how you keep the pipeline honest about
what it doesn't know.
</details>

<details>
<summary><b>Q: Your structured output works on 95% of inputs. Get to 99%. Walk through your approach.</b></summary>

**Diagnose before fixing.** Collect the 5% failures and cluster them. In my experience they
split into roughly: inputs genuinely missing the field, inputs where the field is ambiguous,
schema-too-deep failures, and provider flakiness. Each has a different fix, and guessing wastes
weeks.

Then, in rough ROI order:

1. **Make unknowns representable** — nullable fields with explicit "or null if absent"
   descriptions. Usually the single biggest win, because it converts "invents a value" into
   "correctly says nothing".
2. **Sharpen descriptions** — they're prompt text. Add a concrete example of the format inside
   the description (`"ISO date, e.g. 2024-03-14"`).
3. **Constrain harder** — replace free strings with enums wherever the value space is closed.
4. **Reasoning field first** — cheap, and it helps most on the ambiguous cluster.
5. **Flatten the schema** — if failures correlate with nesting depth, split into two calls and
   assemble in code.
6. **Dynamic few-shot** — retrieve the k most similar previously-corrected examples and include
   them. This is what specifically targets the ambiguous cluster.
7. **Escalate on low confidence** — route the bottom decile to a stronger model. Cheap model on
   90% of traffic, expensive path where it's needed.
8. **Retry + cross-provider fallback** — handles the flakiness cluster, and log which tier fired
   so silent degradation is visible.

**And know when to stop.** Some of that last 1% is genuinely ambiguous input where two humans
would disagree. Measure inter-annotator agreement on your golden set before targeting a number
above it — otherwise you're tuning against noise. At that point the right answer is a human
review queue, not a better prompt.
</details>

---

## 10. Recap

- ✅ `StringOutputParser` / `StrOutputParser` makes chains compose and streams strings
- ✅ `JsonOutputParser` parses JSON and strips markdown fences for you
- ✅ `withStructuredOutput(schema)` is the default choice — validated, typed objects
- ✅ It works by binding your schema as a **forced tool call** — Day 02's mechanism, reused
- ✅ Descriptions are prompt text; enums beat free strings; nullable beats required
- ✅ Put `reasoning` **first** in the schema — that's chain-of-thought for free
- ✅ Schemas guarantee shape, never meaning — add business-rule validation in code
- ✅ Handle failure with `includeRaw`, retries, and cross-provider fallbacks — and log which fired

### Tomorrow

**[Day 07 — LCEL & Runnables](day-07-lcel-and-runnables.md)** — the biggest interview topic in
LangChain. You've been writing `prompt.pipe(model).pipe(parser)` all week without knowing why it
works. Tomorrow: `RunnableSequence`, `RunnableParallel`, `RunnableLambda`, `RunnableBranch`,
`RunnablePassthrough`, `RunnableAssign` — and the Week 1 project that ties it all together.

### Quick self-check

1. What mechanism does `withStructuredOutput` actually use under the hood?
2. Why put a `reasoning` field first instead of last?
3. Your schema validated successfully but the data is wrong. What layer was missing?

<details>
<summary>Answers</summary>

1. Tool calling — the schema becomes a JSON Schema, bound as a single tool with `tool_choice`
   forced to it. The response comes back as `tool_call.args`, which is validated and returned.
   No function is ever executed.
2. Because the model generates fields in order, one token at a time. Reasoning first means it
   works through the problem before committing to an answer; reasoning last means it commits
   then rationalises.
3. Business-rule validation. Schemas enforce shape (types, enums, ranges), not semantics
   (arithmetic, cross-field consistency, referential integrity). That layer is always your code.
</details>
