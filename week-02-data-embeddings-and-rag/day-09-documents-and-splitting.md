# Day 09 — Documents, Loaders, Splitting & Chunking Strategy

> ⏱ **Time:** ~2.5 hours · 🎯 **Prereqs:** [Day 08](day-08-chains.md) · 🧩 **Difficulty:** ●●○○○

**Today you learn:** the `Document` class and why metadata is the most under-used feature in
RAG, loaders for PDF/CSV/JSON/HTML/Markdown, and **splitting** — recursive, structure-aware and
token-aware — plus how to choose chunk size without guessing.

Chunking is where most RAG systems are silently broken. A perfect retriever over bad chunks
returns bad answers, and it's very hard to debug after the fact.

---

## 1. The problem

Yesterday you split text like this:

```js
text.slice(i, i + 1200)
```

Here's what that actually does to real content:

```
   ORIGINAL
   ────────
   ## Refund Policy

   Customers may request a refund within 30 days of purchase. Refunds are
   processed within 5 business days.

   | Plan  | Refund window | Fee  |
   |-------|---------------|------|
   | Basic | 30 days       | £0   |
   | Pro   | 60 days       | £0   |


   AFTER slice(0, 180)                    AFTER slice(180, 360)
   ────────────────────                   ─────────────────────
   ## Refund Policy                       cessed within 5 business days.

   Customers may request a refund         | Plan  | Refund window | Fee  |
   within 30 days of purchase.            |-------|---------------|------|
   Refunds are pro                        | Basic | 30 days       | £0   |
                                          | Pro   | 60 da
```

Three separate disasters:

1. **A word is cut in half** — `"pro" / "cessed"`. Both chunks now embed slightly wrong.
2. **The table is decapitated.** Chunk 2 has rows but the heading `## Refund Policy` is gone, so
   a chunk about refund windows doesn't contain the word "Refund Policy".
3. **The table is cut mid-row.** `| Pro | 60 da` is not retrievable *or* readable.

Now a user asks *"how long do I have to get a refund on Pro?"* The answer exists in your
document. It will not be found, because no chunk cleanly contains it.

**This is the single most common cause of "our RAG doesn't work".** People blame the embedding
model or the LLM. It's almost always the chunks.

---

## 2. Mental model

### The Document

```
   ┌─────────────────────────────────────────────────────┐
   │  Document                                           │
   ├─────────────────────────────────────────────────────┤
   │  pageContent / page_content   "the actual text"     │
   │  metadata                     { source, page, ... } │
   │  id                           optional              │
   └─────────────────────────────────────────────────────┘

   Only pageContent gets EMBEDDED.
   metadata is what you FILTER and CITE by.
```

That distinction drives every design decision today. If a fact lives only in metadata, semantic
search can't find it. If it lives only in `pageContent`, you can't filter on it.

### The pipeline

```
   raw file
      │  LOADER          →  Document[]  (often 1 per page/row/file)
      ▼
   Document[]
      │  SPLITTER        →  Document[]  (many small chunks, metadata copied)
      ▼
   chunks  ──────────────▶ embed (Day 10) ──▶ store (Day 11) ──▶ retrieve (Day 12)
```

### How recursive splitting actually works

This is the key algorithm and it's simpler than people assume:

```
   Try to split on the BIGGEST separator first.
   If a piece is still too big, recurse with the NEXT separator down.

   separators = ["\n\n", "\n", " ", ""]
                  ▲       ▲    ▲    ▲
                  │       │    │    └── give up, split mid-word (last resort)
                  │       │    └─────── split on spaces (breaks sentences)
                  │       └──────────── split on lines (breaks paragraphs)
                  └──────────────────── split on paragraphs (ideal)


   "para1\n\npara2\n\npara3"  with chunkSize=100

   step 1: split on "\n\n"  → ["para1", "para2", "para3"]
   step 2: para1 is 40 chars ✅ keep
           para2 is 250 chars ❌ too big → recurse on "\n"
   step 3: para2 → ["line1", "line2"] → both fit ✅
```

**The result:** chunks break at natural boundaries whenever possible, and only fall back to
brutal cuts when a single paragraph is genuinely larger than the chunk size.

### Overlap

```
   chunkSize = 100, chunkOverlap = 20

   chunk 1: [────────────────────]
   chunk 2:                 [────────────────────]
                            └──┬──┘
                          shared 20 chars

   Why: a sentence spanning the boundary appears WHOLE in at least one chunk.
```

---

## 3. First principles

### 3.1 The Document class

```js
new Document({
  pageContent: "Refunds are processed within 5 business days.",
  metadata: {
    source: "policy.pdf",
    page: 3,
    section: "Refund Policy",
    lastUpdated: "2024-06-01",
    department: "billing",
  },
})
```

**Metadata is the most under-used feature in RAG.** It gives you four things:

| Use | Example |
|---|---|
| **Citation** | "According to policy.pdf page 3…" |
| **Filtering** | Only search documents where `department = "billing"` |
| **Freshness** | Drop chunks where `lastUpdated < 2023` |
| **Access control** | Only return chunks the user's role can see |

That last one is not optional in a real product. If your vector store contains documents from
multiple tenants and you don't filter by tenant, you have a data breach, not a search bug.

> 🔑 **Design rule:** any fact you might want to *filter* by goes in metadata. Any fact you
> might want to *search* by semantically must be in `pageContent`. Important facts often belong
> in **both** — see §3.6 on header injection.

### 3.2 Loaders

A loader turns a file into `Document[]`. The granularity varies:

| Loader | Produces |
|---|---|
| `TextLoader` | 1 document for the whole file |
| PDF loader | 1 document **per page** (with `page` in metadata) |
| CSV loader | 1 document **per row** |
| JSON loader | 1 document per extracted value |
| Directory loader | Recursively loads a folder |
| Web loader | 1 document per URL |

Loaders almost never produce correctly-sized chunks. A PDF page is usually too big; a CSV row is
usually too small. **Load, then split** — with the exception of CSV, where rows are often already
the right unit.

### 3.3 The splitters

| Splitter | Splits on | Use for |
|---|---|---|
| **`RecursiveCharacterTextSplitter`** | `\n\n`, `\n`, ` `, `""` | **Default. Use this unless you have a reason not to.** |
| `CharacterTextSplitter` | one separator only | Rarely — it ignores `chunkSize` when the separator is scarce |
| `TokenTextSplitter` | token boundaries | When you need exact token counts |
| `MarkdownTextSplitter` (JS) | markdown structure | `.md` files |
| `MarkdownHeaderTextSplitter` (Py) | headers → metadata | `.md` where sections matter |
| `RecursiveCharacterTextSplitter.fromLanguage()` | language syntax | Source code |
| `HTMLHeaderTextSplitter` (Py) | HTML headings | Scraped web pages |
| `RecursiveJsonSplitter` (Py) | JSON structure | Deep JSON |

> ⚠️ **Python has more structure-aware splitters than JS.** `MarkdownHeaderTextSplitter`,
> `HTMLHeaderTextSplitter` and `RecursiveJsonSplitter` are Python-only. In JS you use
> `MarkdownTextSplitter` or `RecursiveCharacterTextSplitter` with custom separators, and do
> header extraction yourself — §4.4 shows how.

### 3.4 Choosing chunk size

There is no universal right answer, but there is a right *way to think about it*:

```
   SMALL CHUNKS (200-400 tokens)          LARGE CHUNKS (1000-2000 tokens)
   ─────────────────────────────          ──────────────────────────────
   ✅ precise retrieval                    ✅ more context per hit
   ✅ less irrelevant text in the prompt   ✅ fewer chunks to store
   ✅ cheaper prompts                      ✅ survives cross-sentence reasoning
   ❌ context gets fragmented              ❌ dilutes the embedding
   ❌ more chunks = more storage           ❌ retrieves irrelevant text alongside
   ❌ answer may span several chunks       ❌ "lost in the middle" within a chunk
```

**The dilution problem** is the one people miss. An embedding is a single vector for the whole
chunk. A 2000-token chunk covering five topics produces a vector that is the *average* of five
topics — close to nothing in particular. Small chunks have sharper vectors.

**Starting points by content type:**

| Content | Chunk size | Overlap | Why |
|---|---|---|---|
| Prose / articles | 800–1000 chars | 100–200 | Paragraphs are the natural unit |
| Technical docs | 500–800 chars | 100 | Dense; precision matters |
| Code | 800–1500 chars | 0–100 | Split on function boundaries |
| FAQ / Q&A pairs | 1 chunk per Q&A | 0 | The unit is already semantic |
| Legal / contracts | 1 chunk per clause | 0–50 | Clauses are self-contained |
| Chat transcripts | 5–10 turns | 1–2 turns | Conversation needs surrounding turns |
| CSV rows | 1 chunk per row | 0 | Already atomic |

**Overlap rule of thumb: 10–20% of chunk size.** Zero overlap risks splitting a sentence that
contains the answer. Too much overlap wastes storage and returns near-duplicate chunks.

> 🎯 **The honest answer to "what chunk size?"** — build an eval set of ~30 real questions with
> known answers, then measure **retrieval recall** (did the right chunk come back?) at several
> chunk sizes. It takes an afternoon and it's the only way to know. Exercise 5 builds this.

### 3.5 Token-aware vs character-aware

Character splitting is an approximation. `chunkSize: 1000` chars ≈ 250 tokens for English prose,
but ≈ 400 tokens for code, and ≈ 700 for Hindi (Day 01).

If you need a hard guarantee — because your embedding model has a token limit, or you're packing
a fixed context budget — use a token-aware splitter.

```js
// character-based (fast, approximate)
new RecursiveCharacterTextSplitter({ chunkSize: 1000, chunkOverlap: 200 })

// token-based (exact, slower)
new TokenTextSplitter({ chunkSize: 250, chunkOverlap: 50 })
```

Most teams use character-based with a conservative size. Use token-based when the limit is hard.

### 3.6 Header injection — the highest-ROI trick today

Remember the broken table from §1? The fix is to **put the structural context back into the
chunk text**:

```
   ❌ chunk 2 as split:
      | Basic | 30 days | £0 |
      | Pro   | 60 days | £0 |

   ✅ chunk 2 with headers injected:
      # Billing Policy > ## Refund Policy
      | Plan | Refund window | Fee |
      | Basic | 30 days | £0 |
      | Pro   | 60 days | £0 |
```

Now the chunk *semantically contains* "refund policy", so a question about refunds retrieves it.
This one change routinely moves retrieval recall by 10–20 points on structured documents, and it
costs a handful of tokens per chunk.

Python's `MarkdownHeaderTextSplitter` does this by putting headers in metadata; you then prepend
them to the content. In JS you do it manually. Both shown in §4.4 / §5.4.

---

## 4. Code — JavaScript

```bash
npm install langchain @langchain/core @langchain/textsplitters @langchain/classic \
            @langchain/groq dotenv
```

### 4.1 Documents and metadata

```js
// day09-documents.js
import { Document } from "@langchain/core/documents";

const doc = new Document({
  pageContent: "Refunds are processed within 5 business days of approval.",
  metadata: {
    source: "policy.pdf",
    page: 3,
    section: "Refund Policy",
    department: "billing",
    lastUpdated: "2024-06-01",
  },
});

console.log(doc.pageContent);
console.log(doc.metadata.page);        // 3

// Metadata is ordinary data — filter on it like anything else.
const DOCS = [
  new Document({ pageContent: "Refund within 30 days.",  metadata: { dept: "billing", year: 2024 } }),
  new Document({ pageContent: "Deploy with Docker.",      metadata: { dept: "eng",     year: 2023 } }),
  new Document({ pageContent: "Invoices are monthly.",    metadata: { dept: "billing", year: 2022 } }),
];

const recentBilling = DOCS.filter(
  (d) => d.metadata.dept === "billing" && d.metadata.year >= 2024
);
console.log(recentBilling.map((d) => d.pageContent));   // [ 'Refund within 30 days.' ]
```

### 4.2 The recursive splitter — see it work

```js
// day09-splitting.js
import { RecursiveCharacterTextSplitter, CharacterTextSplitter,
         TokenTextSplitter } from "@langchain/textsplitters";
import { Document } from "@langchain/core/documents";

const TEXT = `# Billing Policy

## Refund Policy

Customers may request a refund within 30 days of purchase. Refunds are processed within 5 business days of approval by the billing team.

| Plan  | Refund window | Fee |
|-------|---------------|-----|
| Basic | 30 days       | £0  |
| Pro   | 60 days       | £0  |

## Invoicing

Invoices are issued monthly on the first business day. Payment is due within 14 days.`;

// ── the naive way, for comparison ────────────────────────────────────────
console.log("═══ NAIVE slice() ═══");
for (let i = 0; i < TEXT.length; i += 180) {
  console.log(`--- chunk ---\n${TEXT.slice(i, i + 180)}`);
}

// ── the recursive splitter ───────────────────────────────────────────────
const splitter = new RecursiveCharacterTextSplitter({
  chunkSize: 180,
  chunkOverlap: 30,
  separators: ["\n\n", "\n", ". ", " ", ""],   // biggest → smallest
});

const chunks = await splitter.splitText(TEXT);

console.log("\n═══ RECURSIVE ═══");
chunks.forEach((c, i) =>
  console.log(`--- chunk ${i + 1} (${c.length} chars) ---\n${c}`)
);
```

Compare the two outputs. The recursive splitter breaks at blank lines, so the table stays intact
and words stay whole.

### 4.3 Splitting Documents (metadata is preserved)

```js
// day09-split-documents.js
import { RecursiveCharacterTextSplitter } from "@langchain/textsplitters";
import { Document } from "@langchain/core/documents";

const docs = [
  new Document({
    pageContent: "Section one. ".repeat(40),
    metadata: { source: "handbook.pdf", page: 1, dept: "hr" },
  }),
  new Document({
    pageContent: "Section two. ".repeat(40),
    metadata: { source: "handbook.pdf", page: 2, dept: "hr" },
  }),
];

const splitter = new RecursiveCharacterTextSplitter({ chunkSize: 200, chunkOverlap: 20 });

// splitDocuments (not splitText) — copies metadata onto every child chunk
const chunks = await splitter.splitDocuments(docs);

console.log(`${docs.length} documents → ${chunks.length} chunks\n`);
chunks.slice(0, 4).forEach((c, i) =>
  console.log(`[${i}] page=${c.metadata.page} dept=${c.metadata.dept} ` +
              `len=${c.pageContent.length}\n    "${c.pageContent.slice(0, 55)}…"`)
);

// Add your own metadata after splitting — chunk position is genuinely useful.
const enriched = chunks.map((c, i) => new Document({
  pageContent: c.pageContent,
  metadata: { ...c.metadata, chunkIndex: i, totalChunks: chunks.length },
}));
console.log("\nfirst chunk metadata:", enriched[0].metadata);
```

### 4.4 Markdown-aware splitting with header injection

```js
// day09-markdown.js
import { RecursiveCharacterTextSplitter } from "@langchain/textsplitters";
import { Document } from "@langchain/core/documents";

const MARKDOWN = `# Acme Handbook

## Refund Policy

Customers may request a refund within 30 days.

| Plan  | Window  |
|-------|---------|
| Basic | 30 days |
| Pro   | 60 days |

## Shipping

Orders ship within 2 business days.

### International

International orders may take 10-14 days and incur customs fees.

## Support

Support is available 9am-6pm GMT.`;

// Walk the markdown, tracking the current header stack.
function splitMarkdownByHeaders(md) {
  const lines = md.split("\n");
  const sections = [];
  let stack = [];                     // e.g. ["Acme Handbook", "Refund Policy"]
  let buffer = [];

  const flush = () => {
    const content = buffer.join("\n").trim();
    if (content) sections.push({ headers: [...stack], content });
    buffer = [];
  };

  for (const line of lines) {
    const m = line.match(/^(#{1,6})\s+(.*)$/);
    if (m) {
      flush();
      const level = m[1].length;
      stack = stack.slice(0, level - 1);   // pop deeper headers
      stack[level - 1] = m[2].trim();
      stack = stack.filter(Boolean);
    } else {
      buffer.push(line);
    }
  }
  flush();
  return sections;
}

const splitter = new RecursiveCharacterTextSplitter({ chunkSize: 300, chunkOverlap: 40 });

const chunks = [];
for (const { headers, content } of splitMarkdownByHeaders(MARKDOWN)) {
  const breadcrumb = headers.join(" > ");
  for (const piece of await splitter.splitText(content)) {
    chunks.push(new Document({
      // ⭐ inject the header path INTO the text so it gets embedded
      pageContent: `${breadcrumb}\n\n${piece}`,
      metadata: { headers, breadcrumb, h1: headers[0], h2: headers[1] ?? null },
    }));
  }
}

chunks.forEach((c, i) => {
  console.log(`--- chunk ${i + 1} ---`);
  console.log(`breadcrumb: ${c.metadata.breadcrumb}`);
  console.log(c.pageContent.split("\n").slice(0, 4).join("\n"));
  console.log();
});
```

Notice chunk contents now start with `Acme Handbook > Refund Policy` — so a query about refunds
matches even if the chunk body is only a table.

### 4.5 Code splitting

```js
// day09-code.js
import { RecursiveCharacterTextSplitter } from "@langchain/textsplitters";

const CODE = `import { useState } from "react";

export function useCounter(initial = 0) {
  const [count, setCount] = useState(initial);
  const increment = () => setCount((c) => c + 1);
  const reset = () => setCount(initial);
  return { count, increment, reset };
}

export function useToggle(initial = false) {
  const [on, setOn] = useState(initial);
  const toggle = () => setOn((v) => !v);
  return { on, toggle };
}`;

// fromLanguage knows JS syntax: it prefers splitting at function/class boundaries
const splitter = RecursiveCharacterTextSplitter.fromLanguage("js", {
  chunkSize: 200,
  chunkOverlap: 0,
});

const chunks = await splitter.splitText(CODE);
chunks.forEach((c, i) => console.log(`--- ${i + 1} ---\n${c}\n`));

// Supported: cpp, go, java, js, php, proto, python, rst, ruby, rust,
//            scala, swift, markdown, latex, html, sol
```

### 4.6 Loaders

```js
// day09-loaders.js
import { TextLoader } from "@langchain/classic/document_loaders/fs/text";
import { RecursiveCharacterTextSplitter } from "@langchain/textsplitters";

// ── text ─────────────────────────────────────────────────────────────────
const loader = new TextLoader("./alice.txt");
const docs = await loader.load();
console.log(`loaded ${docs.length} document(s), ${docs[0].pageContent.length} chars`);
console.log("metadata:", docs[0].metadata);      // { source: './alice.txt' }

const splitter = new RecursiveCharacterTextSplitter({ chunkSize: 1000, chunkOverlap: 150 });
const chunks = await splitter.splitDocuments(docs);
console.log(`→ ${chunks.length} chunks`);
```

<details>
<summary>📄 PDF, CSV and web loaders (extra installs)</summary>

```bash
npm install @langchain/community pdf-parse d3-dsv cheerio
```

> ⚠️ **These loaders live in `@langchain/community`, not `@langchain/classic`.**
> `@langchain/classic/document_loaders` only ships the filesystem basics (`fs/text`,
> `fs/json`, `fs/directory`, `fs/buffer`, `fs/multi_file`). PDF, CSV and web loaders are in
> `@langchain/community`, and each needs its own peer dependency (`pdf-parse`, `d3-dsv`,
> `cheerio`) or you'll get `ERR_MODULE_NOT_FOUND`.
>
> Note that `@langchain/community` is **marked deprecated** on npm as the JS ecosystem splits
> integrations into per-provider packages. It still works and is still the path for these
> loaders today — but check for a dedicated package before depending on it heavily in new
> production code. Python's `langchain-community` is not deprecated.

```js
import { PDFLoader } from "@langchain/community/document_loaders/fs/pdf";
import { CSVLoader } from "@langchain/community/document_loaders/fs/csv";
import { CheerioWebBaseLoader } from "@langchain/community/document_loaders/web/cheerio";

// PDF → one Document PER PAGE, with page number in metadata
const pdfDocs = await new PDFLoader("./manual.pdf").load();
console.log(pdfDocs.length, "pages");
console.log(pdfDocs[0].metadata);   // { source, pdf: {...}, loc: { pageNumber: 1 } }

// Set splitPages: false to get ONE document for the whole PDF
const whole = await new PDFLoader("./manual.pdf", { splitPages: false }).load();

// CSV → one Document PER ROW
const rows = await new CSVLoader("./products.csv").load();

// Web → one Document per URL
const web = await new CheerioWebBaseLoader("https://example.com").load();
```

> ⚠️ PDF text extraction is genuinely hard. Multi-column layouts interleave, tables lose their
> structure, and scanned PDFs contain no text at all (you need OCR). **Always print the extracted
> text before trusting it.** More on this in §7.
</details>

---

## 5. Code — Python

```bash
pip install langchain langchain-classic langchain-text-splitters langchain-groq python-dotenv
```

### 5.1 Documents and metadata

```python
# day09_documents.py
from langchain_core.documents import Document

doc = Document(
    page_content="Refunds are processed within 5 business days of approval.",
    metadata={
        "source": "policy.pdf",
        "page": 3,
        "section": "Refund Policy",
        "department": "billing",
        "last_updated": "2024-06-01",
    },
)

print(doc.page_content)
print(doc.metadata["page"])            # 3

# Metadata is ordinary data — filter on it like anything else.
DOCS = [
    Document(page_content="Refund within 30 days.", metadata={"dept": "billing", "year": 2024}),
    Document(page_content="Deploy with Docker.",     metadata={"dept": "eng",     "year": 2023}),
    Document(page_content="Invoices are monthly.",   metadata={"dept": "billing", "year": 2022}),
]

recent_billing = [d for d in DOCS
                  if d.metadata["dept"] == "billing" and d.metadata["year"] >= 2024]
print([d.page_content for d in recent_billing])     # ['Refund within 30 days.']
```

### 5.2 The recursive splitter — see it work

```python
# day09_splitting.py
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter, CharacterTextSplitter, TokenTextSplitter,
)

TEXT = """# Billing Policy

## Refund Policy

Customers may request a refund within 30 days of purchase. Refunds are processed within 5 business days of approval by the billing team.

| Plan  | Refund window | Fee |
|-------|---------------|-----|
| Basic | 30 days       | £0  |
| Pro   | 60 days       | £0  |

## Invoicing

Invoices are issued monthly on the first business day. Payment is due within 14 days."""

# ── the naive way, for comparison ────────────────────────────────────────
print("═══ NAIVE slicing ═══")
for i in range(0, len(TEXT), 180):
    print(f"--- chunk ---\n{TEXT[i:i + 180]}")

# ── the recursive splitter ───────────────────────────────────────────────
splitter = RecursiveCharacterTextSplitter(
    chunk_size=180,
    chunk_overlap=30,
    separators=["\n\n", "\n", ". ", " ", ""],    # biggest → smallest
)

chunks = splitter.split_text(TEXT)

print("\n═══ RECURSIVE ═══")
for i, c in enumerate(chunks, 1):
    print(f"--- chunk {i} ({len(c)} chars) ---\n{c}")
```

### 5.3 Splitting Documents (metadata is preserved)

```python
# day09_split_documents.py
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

docs = [
    Document(page_content="Section one. " * 40,
             metadata={"source": "handbook.pdf", "page": 1, "dept": "hr"}),
    Document(page_content="Section two. " * 40,
             metadata={"source": "handbook.pdf", "page": 2, "dept": "hr"}),
]

splitter = RecursiveCharacterTextSplitter(chunk_size=200, chunk_overlap=20)

# split_documents (not split_text) — copies metadata onto every child chunk
chunks = splitter.split_documents(docs)

print(f"{len(docs)} documents → {len(chunks)} chunks\n")
for i, c in enumerate(chunks[:4]):
    print(f"[{i}] page={c.metadata['page']} dept={c.metadata['dept']} "
          f"len={len(c.page_content)}\n    \"{c.page_content[:55]}…\"")

# Add your own metadata after splitting — chunk position is genuinely useful.
enriched = [
    Document(page_content=c.page_content,
             metadata={**c.metadata, "chunk_index": i, "total_chunks": len(chunks)})
    for i, c in enumerate(chunks)
]
print("\nfirst chunk metadata:", enriched[0].metadata)
```

### 5.4 Markdown header splitting — the built-in way

Python has a dedicated splitter for this, which is much nicer than the JS manual walk:

```python
# day09_markdown.py
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain_core.documents import Document

MARKDOWN = """# Acme Handbook

## Refund Policy

Customers may request a refund within 30 days.

| Plan  | Window  |
|-------|---------|
| Basic | 30 days |
| Pro   | 60 days |

## Shipping

Orders ship within 2 business days.

### International

International orders may take 10-14 days and incur customs fees.

## Support

Support is available 9am-6pm GMT."""

header_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")],
    strip_headers=True,          # headers go to metadata, not content
)

sections = header_splitter.split_text(MARKDOWN)

print("═══ sections with header metadata ═══")
for s in sections:
    print(f"{s.metadata} → {s.page_content[:50]!r}")

# Now split any oversized section, and inject the breadcrumb into the text.
splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=40)

chunks = []
for s in splitter.split_documents(sections):
    breadcrumb = " > ".join(
        s.metadata[k] for k in ("h1", "h2", "h3") if k in s.metadata
    )
    chunks.append(Document(
        # ⭐ inject the header path INTO the text so it gets embedded
        page_content=f"{breadcrumb}\n\n{s.page_content}",
        metadata={**s.metadata, "breadcrumb": breadcrumb},
    ))

print("\n═══ final chunks ═══")
for i, c in enumerate(chunks, 1):
    print(f"--- chunk {i} ---")
    print(f"breadcrumb: {c.metadata['breadcrumb']}")
    print("\n".join(c.page_content.split("\n")[:4]))
    print()
```

### 5.5 Code splitting

```python
# day09_code.py
from langchain_text_splitters import RecursiveCharacterTextSplitter, Language

CODE = '''import functools

def use_counter(initial=0):
    """A counter with increment and reset."""
    count = initial
    def increment():
        nonlocal count
        count += 1
        return count
    def reset():
        nonlocal count
        count = initial
    return increment, reset

def use_toggle(initial=False):
    """A boolean toggle."""
    state = initial
    def toggle():
        nonlocal state
        state = not state
        return state
    return toggle
'''

# from_language knows Python syntax: it prefers class/def boundaries
splitter = RecursiveCharacterTextSplitter.from_language(
    language=Language.PYTHON, chunk_size=200, chunk_overlap=0
)

for i, c in enumerate(splitter.split_text(CODE), 1):
    print(f"--- {i} ---\n{c}\n")

print("supported languages:", [l.value for l in Language][:12], "…")
```

### 5.6 Loaders

```python
# day09_loaders.py
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# pip install langchain-community
docs = TextLoader("./alice.txt", encoding="utf8").load()
print(f"loaded {len(docs)} document(s), {len(docs[0].page_content)} chars")
print("metadata:", docs[0].metadata)          # {'source': './alice.txt'}

splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
chunks = splitter.split_documents(docs)
print(f"→ {len(chunks)} chunks")
```

<details>
<summary>📄 PDF, CSV and web loaders (extra installs)</summary>

```bash
pip install langchain-community pypdf beautifulsoup4
```

```python
from langchain_community.document_loaders import PyPDFLoader, CSVLoader, WebBaseLoader

# PDF → one Document PER PAGE, with page number in metadata
pdf_docs = PyPDFLoader("./manual.pdf").load()
print(len(pdf_docs), "pages")
print(pdf_docs[0].metadata)    # {'source': './manual.pdf', 'page': 0}

# CSV → one Document PER ROW
rows = CSVLoader("./products.csv").load()

# Web → one Document per URL
web = WebBaseLoader("https://example.com").load()
```

> ⚠️ PDF text extraction is genuinely hard. Multi-column layouts interleave, tables lose their
> structure, and scanned PDFs contain no text at all (you need OCR). **Always print the extracted
> text before trusting it.**
</details>

### 5.7 JSON splitting (Python only)

```python
# day09_json.py
from langchain_text_splitters import RecursiveJsonSplitter

DATA = {
    "company": "Acme",
    "policies": {
        "refund": {"window_days": 30, "fee": 0,
                   "notes": "Processed within 5 business days of approval."},
        "shipping": {"domestic_days": 2, "international_days": 14,
                     "notes": "International orders may incur customs fees."},
    },
    "support": {"hours": "9am-6pm GMT", "channels": ["email", "chat"]},
}

splitter = RecursiveJsonSplitter(max_chunk_size=120)

# split_json keeps valid JSON structure in each chunk
for i, chunk in enumerate(splitter.split_json(DATA), 1):
    print(f"--- {i} ---\n{chunk}\n")

# Or straight to Documents
docs = splitter.create_documents(texts=[DATA])
print(f"{len(docs)} documents")
```

### 🔁 JS ↔ Python differences you just saw

| | JavaScript | Python |
|---|---|---|
| Text field | `pageContent` | `page_content` |
| Splitter package | `@langchain/textsplitters` | `langchain_text_splitters` |
| Split text | `await splitter.splitText(s)` | `splitter.split_text(s)` |
| Split docs | `await splitter.splitDocuments(d)` | `splitter.split_documents(d)` |
| Params | `chunkSize`, `chunkOverlap` | `chunk_size`, `chunk_overlap` |
| Code splitting | `.fromLanguage("js", {...})` | `.from_language(Language.PYTHON, ...)` |
| Markdown headers | ❌ manual (see §4.4) | ✅ `MarkdownHeaderTextSplitter` |
| HTML headers | ❌ manual | ✅ `HTMLHeaderTextSplitter` |
| JSON splitting | ❌ manual | ✅ `RecursiveJsonSplitter` |
| Loaders (basic) | `@langchain/classic/document_loaders/fs/text` | `langchain_community.document_loaders` |
| Loaders (PDF/CSV/web) | `@langchain/community/document_loaders/...` | `langchain_community.document_loaders` |
| Async | everything `await`ed | sync by default |

---

## 6. Under the hood

### The recursive splitting algorithm, precisely

```
split(text, separators):
    sep = first separator that appears in text (or the last one as fallback)
    remaining = separators after sep

    pieces = text.split(sep)
    output = []
    buffer = []

    for piece in pieces:
        if len(piece) > chunkSize:
            flush buffer into output          # emit what we have
            if remaining:
                output += split(piece, remaining)     # ← RECURSE with a finer separator
            else:
                output += hard_split(piece)           # last resort: cut mid-word
        else:
            if len(buffer) + len(piece) > chunkSize:
                flush buffer into output
                buffer = tail of buffer (for overlap)
            buffer.append(piece)

    flush buffer
    return output
```

Two consequences worth knowing:

1. **`chunkSize` is a maximum, not a target.** Chunks come out *smaller* than the limit whenever
   a natural boundary lands early. Seeing 300-char chunks with `chunkSize: 1000` is normal, not
   a bug.
2. **A single paragraph larger than `chunkSize` will still be split mid-sentence** — the
   recursion runs out of separators. If you see mangled chunks, your `chunkSize` is smaller than
   your content's natural units.

### Why `CharacterTextSplitter` surprises people

```js
new CharacterTextSplitter({ separator: "\n\n", chunkSize: 100 })
```

It splits **only** on `\n\n`. If a paragraph is 5,000 characters with no blank line inside it,
you get one 5,000-character chunk — `chunkSize` is silently exceeded, usually with a warning.

`RecursiveCharacterTextSplitter` doesn't have this problem because it falls back through finer
separators. **This is why it's the default recommendation**, and why `CharacterTextSplitter`
almost always turns out to be the wrong choice.

### How overlap is implemented

Overlap is not a re-slice of the original text — it's a **carry-over of trailing pieces**:

```
buffer = ["sentence A", "sentence B", "sentence C"]   → emit as chunk 1
                          └──────── kept ────────┘
buffer = ["sentence C", "sentence D", ...]            → chunk 2 starts with C
```

Because it operates on whole *pieces*, overlap respects separator boundaries. It won't hand you
half a word — unless the recursion already fell through to character-level splitting.

### Why metadata is copied but not merged

`splitDocuments` copies the parent's metadata **by reference-free shallow copy** onto every
child. It doesn't add anything about position. That's why you nearly always want to enrich after
splitting:

```js
{ ...c.metadata, chunkIndex: i, totalChunks: chunks.length }
```

`chunkIndex` in particular is how you implement "fetch the neighbouring chunks too" — the
poor man's parent-document retriever (Day 13).

---

## 7. Common mistakes

**❌ Splitting before loading structure**

Converting a PDF to one giant string and then splitting throws away page numbers permanently.
✅ Load into `Document[]` first (loaders put `page` in metadata), *then* `splitDocuments`.

---

**❌ Using `splitText` when you meant `splitDocuments`**

```js
const chunks = await splitter.splitText(doc.pageContent);   // metadata LOST
```
✅ `splitter.splitDocuments([doc])` — returns Documents with metadata intact.

---

**❌ Chunk size chosen by vibes**

"1000 seemed reasonable" is how most RAG systems get their chunk size, and it's why so many
underperform.
✅ Measure retrieval recall on a small eval set at 3–4 sizes. One afternoon, permanent payoff.

---

**❌ Zero overlap on prose**

A sentence that straddles a boundary appears in neither chunk in complete form.
✅ 10–20% overlap. (Zero overlap *is* correct for atomic units like CSV rows or Q&A pairs.)

---

**❌ Huge overlap "to be safe"**

`chunkSize: 1000, chunkOverlap: 800` means 80% duplication: your store is 5× bigger, retrieval
returns near-identical chunks, and you waste prompt tokens on repeats.
✅ Keep it under ~25%.

---

**❌ Losing the heading**

The single most common structural failure — a chunk about refund windows that never contains the
word "refund".
✅ Inject the header breadcrumb into `pageContent` (§3.6). Highest-ROI fix on this page.

---

**❌ Trusting PDF extraction without looking at it**

Multi-column academic PDFs interleave columns into nonsense. Scanned PDFs extract *nothing*.
Tables become soup.
✅ Print the first 2,000 characters of every new PDF source before building anything on it. If
it's scanned, you need OCR; if it's multi-column, you may need a layout-aware extractor.

---

**❌ Splitting code with the plain character splitter**

Functions get cut in half; the fragment doesn't parse and doesn't embed meaningfully.
✅ `fromLanguage` / `from_language`, which prefers syntactic boundaries.

---

**❌ Putting searchable facts only in metadata**

`metadata: { author: "Marie Curie" }` will never match the query "papers by Marie Curie", because
only `pageContent` is embedded.
✅ Put it in both — metadata for filtering, and in the text for semantic matching.

---

## 8. Exercises

### Exercise 1 — Splitter comparison ●○○○○

Take a markdown document with headings, a paragraph, a list and a table. Split it three ways:
naive slicing, `CharacterTextSplitter`, and `RecursiveCharacterTextSplitter`. For each, report:
chunk count, min/max/mean chunk length, and how many chunks contain a broken word or a broken
table row.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import { CharacterTextSplitter, RecursiveCharacterTextSplitter } from "@langchain/textsplitters";

const TEXT = `# Product Guide

## Pricing

Our pricing is designed to scale with your team. Every plan includes unlimited projects and email support during business hours.

| Plan       | Price/user | Seats  |
|------------|------------|--------|
| Starter    | £9         | 1-10   |
| Business   | £19        | 11-50  |
| Enterprise | Custom     | 51+    |

## Features

- Unlimited projects
- Role-based access control
- Audit logs and SSO
- API access with generous rate limits

## Support

Support responds within one business day for all paid plans.`;

const CHUNK = 200;

function analyse(name, chunks) {
  const lens = chunks.map((c) => c.length);

  // A word is broken if a chunk starts or ends mid-word.
  const brokenWords = chunks.filter((c, i) => {
    const startsMid = i > 0 && /^[a-z]/.test(c) && /[a-z]$/.test(chunks[i - 1]);
    return startsMid;
  }).length;

  // A table row is broken if a chunk contains a line with '|' that doesn't end in '|'.
  const brokenRows = chunks.filter((c) =>
    c.split("\n").some((l) => l.includes("|") && l.trim().length > 1 && !l.trim().endsWith("|"))
  ).length;

  console.log(
    `${name.padEnd(22)} n=${String(chunks.length).padStart(2)}  ` +
    `min=${String(Math.min(...lens)).padStart(3)} max=${String(Math.max(...lens)).padStart(3)} ` +
    `mean=${String(Math.round(lens.reduce((a, b) => a + b, 0) / lens.length)).padStart(3)}  ` +
    `brokenWords=${brokenWords}  brokenTableRows=${brokenRows}`
  );
}

// 1. naive
const naive = [];
for (let i = 0; i < TEXT.length; i += CHUNK) naive.push(TEXT.slice(i, i + CHUNK));
analyse("naive slice", naive);

// 2. character splitter
analyse("CharacterTextSplitter", await new CharacterTextSplitter({
  separator: "\n\n", chunkSize: CHUNK, chunkOverlap: 0,
}).splitText(TEXT));

// 3. recursive splitter
analyse("Recursive", await new RecursiveCharacterTextSplitter({
  chunkSize: CHUNK, chunkOverlap: 20,
}).splitText(TEXT));
```

**Python**
```python
import re
from statistics import mean
from langchain_text_splitters import CharacterTextSplitter, RecursiveCharacterTextSplitter

TEXT = """# Product Guide

## Pricing

Our pricing is designed to scale with your team. Every plan includes unlimited projects and email support during business hours.

| Plan       | Price/user | Seats  |
|------------|------------|--------|
| Starter    | £9         | 1-10   |
| Business   | £19        | 11-50  |
| Enterprise | Custom     | 51+    |

## Features

- Unlimited projects
- Role-based access control
- Audit logs and SSO
- API access with generous rate limits

## Support

Support responds within one business day for all paid plans."""

CHUNK = 200

def analyse(name, chunks):
    lens = [len(c) for c in chunks]

    # A word is broken if a chunk starts mid-word right after one ending mid-word.
    broken_words = sum(
        1 for i, c in enumerate(chunks)
        if i > 0 and re.match(r"^[a-z]", c) and re.search(r"[a-z]$", chunks[i - 1])
    )

    # A table row is broken if a line contains '|' but doesn't end with '|'.
    broken_rows = sum(
        1 for c in chunks
        if any("|" in l and len(l.strip()) > 1 and not l.strip().endswith("|")
               for l in c.split("\n"))
    )

    print(f"{name:<22} n={len(chunks):>2}  min={min(lens):>3} max={max(lens):>3} "
          f"mean={round(mean(lens)):>3}  broken_words={broken_words}  "
          f"broken_table_rows={broken_rows}")

# 1. naive
naive = [TEXT[i:i + CHUNK] for i in range(0, len(TEXT), CHUNK)]
analyse("naive slice", naive)

# 2. character splitter
analyse("CharacterTextSplitter", CharacterTextSplitter(
    separator="\n\n", chunk_size=CHUNK, chunk_overlap=0).split_text(TEXT))

# 3. recursive splitter
analyse("Recursive", RecursiveCharacterTextSplitter(
    chunk_size=CHUNK, chunk_overlap=20).split_text(TEXT))
```

**Typical output:**

```
naive slice            n= 4  min= 92 max=200 mean=173  brokenWords=3  brokenTableRows=2
CharacterTextSplitter  n= 6  min= 15 max=248 mean=115  brokenWords=0  brokenTableRows=0
Recursive              n= 5  min= 46 max=196 mean=138  brokenWords=0  brokenTableRows=0
```

**Three things to notice:**

1. **Naive slicing breaks words and tables.** Every broken row is a chunk that can't be retrieved
   or rendered.
2. **`CharacterTextSplitter` exceeded `chunkSize`** (max=248 > 200). It only splits on `\n\n`, so
   any block without a blank line stays whole regardless of the limit. This is the surprise from
   §6 and the reason it's rarely the right choice.
3. **Recursive stays under the limit *and* breaks cleanly.** It's the default for a reason.
</details>

---

### Exercise 2 — Header injection, measured ●●○○○

Take a markdown document where a section's body doesn't repeat its heading (a table under
`## Refund Policy`, for example). Split it twice — with and without header injection — then use
simple keyword overlap to check whether a query like "refund window for Pro plan" would match
the right chunk in each case.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import { RecursiveCharacterTextSplitter } from "@langchain/textsplitters";
import { Document } from "@langchain/core/documents";

const MARKDOWN = `# Acme Handbook

## Refund Policy

| Plan  | Window  | Fee |
|-------|---------|-----|
| Basic | 30 days | £0  |
| Pro   | 60 days | £0  |

## Shipping Policy

| Region        | Days  |
|---------------|-------|
| Domestic      | 2     |
| International | 14    |
`;

function splitByHeaders(md) {
  const sections = [];
  let stack = [], buffer = [];
  const flush = () => {
    const content = buffer.join("\n").trim();
    if (content) sections.push({ headers: [...stack], content });
    buffer = [];
  };
  for (const line of md.split("\n")) {
    const m = line.match(/^(#{1,6})\s+(.*)$/);
    if (m) {
      flush();
      stack = stack.slice(0, m[1].length - 1);
      stack[m[1].length - 1] = m[2].trim();
      stack = stack.filter(Boolean);
    } else buffer.push(line);
  }
  flush();
  return sections;
}

const splitter = new RecursiveCharacterTextSplitter({ chunkSize: 400, chunkOverlap: 0 });

const without = [], withHeaders = [];
for (const { headers, content } of splitByHeaders(MARKDOWN)) {
  const breadcrumb = headers.join(" > ");
  for (const piece of await splitter.splitText(content)) {
    without.push(new Document({ pageContent: piece, metadata: { breadcrumb } }));
    withHeaders.push(new Document({
      pageContent: `${breadcrumb}\n\n${piece}`, metadata: { breadcrumb },
    }));
  }
}

// Crude lexical scorer — stands in for an embedding until Day 10.
const tokens = (s) => new Set(s.toLowerCase().match(/[a-z]+/g) ?? []);
function score(query, doc) {
  const q = tokens(query), d = tokens(doc.pageContent);
  const overlap = [...q].filter((t) => d.has(t)).length;
  return overlap / q.size;
}

const QUERIES = [
  "refund window for the Pro plan",
  "how long for international shipping",
];

for (const query of QUERIES) {
  console.log(`\n❓ "${query}"`);
  for (const [label, docs] of [["WITHOUT headers", without], ["WITH headers", withHeaders]]) {
    const ranked = docs.map((d) => ({ d, s: score(query, d) })).sort((a, b) => b.s - a.s);
    const top = ranked[0];
    console.log(`   ${label.padEnd(16)} → ${top.d.metadata.breadcrumb.padEnd(30)} ` +
                `score=${top.s.toFixed(2)}`);
  }
}
```

**Python**
```python
import re
from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

MARKDOWN = """# Acme Handbook

## Refund Policy

| Plan  | Window  | Fee |
|-------|---------|-----|
| Basic | 30 days | £0  |
| Pro   | 60 days | £0  |

## Shipping Policy

| Region        | Days  |
|---------------|-------|
| Domestic      | 2     |
| International | 14    |
"""

header_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=[("#", "h1"), ("##", "h2")], strip_headers=True)
splitter = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=0)

sections = splitter.split_documents(header_splitter.split_text(MARKDOWN))

without, with_headers = [], []
for s in sections:
    breadcrumb = " > ".join(s.metadata[k] for k in ("h1", "h2") if k in s.metadata)
    without.append(Document(page_content=s.page_content,
                            metadata={"breadcrumb": breadcrumb}))
    with_headers.append(Document(page_content=f"{breadcrumb}\n\n{s.page_content}",
                                 metadata={"breadcrumb": breadcrumb}))

# Crude lexical scorer — stands in for an embedding until Day 10.
tokens = lambda s: set(re.findall(r"[a-z]+", s.lower()))

def score(query, doc):
    q, d = tokens(query), tokens(doc.page_content)
    return len(q & d) / len(q)

QUERIES = [
    "refund window for the Pro plan",
    "how long for international shipping",
]

for query in QUERIES:
    print(f'\n❓ "{query}"')
    for label, docs in [("WITHOUT headers", without), ("WITH headers", with_headers)]:
        top = max(docs, key=lambda d: score(query, d))
        print(f"   {label:<16} → {top.metadata['breadcrumb']:<30} "
              f"score={score(query, top):.2f}")
```

**Expected output:**

```
❓ "refund window for the Pro plan"
   WITHOUT headers  → Acme Handbook > Shipping Policy  score=0.17
   WITH headers     → Acme Handbook > Refund Policy    score=0.50
```

**Without headers the query retrieves the *wrong section*.** The refund chunk contains
`Basic | 30 days | £0` — no occurrence of "refund", "window" or "plan" as words the scorer can
match. The shipping chunk happens to score higher by accident.

With the breadcrumb injected, the right chunk wins decisively.

This is a lexical stand-in, but **the same failure happens with embeddings** — a chunk of bare
table rows has a vector that means roughly "tabular data about durations", not "refund policy".
Day 12 lets you re-run this comparison with real embeddings, and the gap is just as large.
</details>

---

### Exercise 3 — Chunk size explorer ●●●○○

Write a tool that takes a text file and a list of chunk sizes, and for each size reports: number
of chunks, mean/median chunk length, estimated total tokens (including overlap duplication), and
estimated storage cost at a given embedding dimension. Use it to build an intuition for the
trade-off.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
import fs from "node:fs/promises";
import { RecursiveCharacterTextSplitter } from "@langchain/textsplitters";

const estimateTokens = (s) => Math.ceil(s.length / 4);

async function explore(text, sizes, overlapRatio = 0.15, dims = 768) {
  const originalTokens = estimateTokens(text);

  console.log(`source: ${text.length} chars ≈ ${originalTokens} tokens\n`);
  console.log("size  overlap  chunks  mean  median  totalTok  dup%   vectorMB");
  console.log("-".repeat(72));

  for (const size of sizes) {
    const overlap = Math.round(size * overlapRatio);
    const chunks = await new RecursiveCharacterTextSplitter({
      chunkSize: size, chunkOverlap: overlap,
    }).splitText(text);

    const lens = chunks.map((c) => c.length).sort((a, b) => a - b);
    const mean = Math.round(lens.reduce((a, b) => a + b, 0) / lens.length);
    const median = lens[Math.floor(lens.length / 2)];

    const totalTokens = chunks.reduce((a, c) => a + estimateTokens(c), 0);
    const dupPct = ((totalTokens / originalTokens - 1) * 100);

    // float32 vectors
    const vectorMB = (chunks.length * dims * 4) / 1e6;

    console.log(
      `${String(size).padStart(4)}  ${String(overlap).padStart(7)}  ` +
      `${String(chunks.length).padStart(6)}  ${String(mean).padStart(4)}  ` +
      `${String(median).padStart(6)}  ${String(totalTokens).padStart(8)}  ` +
      `${dupPct.toFixed(1).padStart(5)}  ${vectorMB.toFixed(2).padStart(8)}`
    );
  }
}

const text = await fs.readFile(process.argv[2] ?? "./alice.txt", "utf8");
await explore(text, [200, 400, 800, 1200, 2000]);
```

**Python**
```python
import sys
from statistics import mean, median
from langchain_text_splitters import RecursiveCharacterTextSplitter

estimate_tokens = lambda s: -(-len(s) // 4)

def explore(text, sizes, overlap_ratio=0.15, dims=768):
    original_tokens = estimate_tokens(text)

    print(f"source: {len(text)} chars ≈ {original_tokens} tokens\n")
    print("size  overlap  chunks  mean  median  totalTok  dup%   vectorMB")
    print("-" * 72)

    for size in sizes:
        overlap = round(size * overlap_ratio)
        chunks = RecursiveCharacterTextSplitter(
            chunk_size=size, chunk_overlap=overlap).split_text(text)

        lens = [len(c) for c in chunks]
        total_tokens = sum(estimate_tokens(c) for c in chunks)
        dup_pct = (total_tokens / original_tokens - 1) * 100
        vector_mb = len(chunks) * dims * 4 / 1e6      # float32 vectors

        print(f"{size:>4}  {overlap:>7}  {len(chunks):>6}  {round(mean(lens)):>4}  "
              f"{round(median(lens)):>6}  {total_tokens:>8}  "
              f"{dup_pct:>5.1f}  {vector_mb:>8.2f}")

path = sys.argv[1] if len(sys.argv) > 1 else "./alice.txt"
with open(path, encoding="utf8") as f:
    explore(f.read(), [200, 400, 800, 1200, 2000])
```

**Typical output on a novel:**

```
source: 148545 chars ≈ 37137 tokens

size  overlap  chunks  mean  median  totalTok  dup%   vectorMB
------------------------------------------------------------------------
 200       30     893   174     186     40711   9.6      2.74
 400       60     438   353     376     39830   7.3      1.35
 800      120     216   716     763     39204   5.6      0.66
1200      180     143  1082    1147     38891   4.7      0.44
2000      300      85  1821    1936     38620   4.0      0.26
```

**Three intuitions this builds:**

1. **Storage scales inversely with chunk size** — 200-char chunks need 10× the vectors of
   2000-char chunks. At millions of documents that's a real infrastructure cost.
2. **Duplication from overlap is modest** at a sensible ratio — under 10% even at 15% overlap,
   because overlap is capped by whole-piece boundaries. Crank overlap to 50% and watch this
   column explode.
3. **Mean is consistently below the limit** — that's the §6 point that `chunkSize` is a maximum,
   not a target. Chunks end early at natural boundaries.

**What this tool deliberately can't tell you: which size retrieves best.** Storage and token
counts are cheap to measure; *quality* needs an eval set with known-correct answers. That's
Exercise 5, and it's the measurement that actually matters.
</details>

---

### Exercise 4 — A robust document ingestion pipeline ●●●○○

Build `ingest(filePath)` that: detects file type from the extension, picks the right loader and
splitter, injects headers for markdown, enriches metadata with `chunkIndex`, `source`, and a
content hash for deduplication, drops chunks below a minimum length, and reports statistics.
Handle unknown extensions gracefully.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
// ingest.js
import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import { Document } from "@langchain/core/documents";
import { RecursiveCharacterTextSplitter } from "@langchain/textsplitters";

const MIN_CHUNK_CHARS = 50;

const PROFILES = {
  ".md":   { size: 800,  overlap: 120, markdown: true },
  ".txt":  { size: 1000, overlap: 150, markdown: false },
  ".js":   { size: 1200, overlap: 0,   language: "js" },
  ".ts":   { size: 1200, overlap: 0,   language: "js" },
  ".py":   { size: 1200, overlap: 0,   language: "python" },
  ".json": { size: 600,  overlap: 50,  markdown: false },
};

function splitMarkdownByHeaders(md) {
  const sections = [];
  let stack = [], buffer = [];
  const flush = () => {
    const content = buffer.join("\n").trim();
    if (content) sections.push({ headers: [...stack], content });
    buffer = [];
  };
  for (const line of md.split("\n")) {
    const m = line.match(/^(#{1,6})\s+(.*)$/);
    if (m) {
      flush();
      stack = stack.slice(0, m[1].length - 1);
      stack[m[1].length - 1] = m[2].trim();
      stack = stack.filter(Boolean);
    } else buffer.push(line);
  }
  flush();
  return sections.length ? sections : [{ headers: [], content: md }];
}

const hash = (s) => crypto.createHash("sha256").update(s).digest("hex").slice(0, 12);

export async function ingest(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  const profile = PROFILES[ext];

  if (!profile) {
    console.warn(`⚠️  no profile for "${ext}" — falling back to plain text defaults`);
  }
  const { size, overlap, markdown, language } = profile ?? { size: 1000, overlap: 150 };

  const raw = await fs.readFile(filePath, "utf8");
  const stat = await fs.stat(filePath);

  const splitter = language
    ? RecursiveCharacterTextSplitter.fromLanguage(language, { chunkSize: size, chunkOverlap: overlap })
    : new RecursiveCharacterTextSplitter({ chunkSize: size, chunkOverlap: overlap });

  // ── split, with markdown header injection where relevant ───────────────
  let pieces = [];
  if (markdown) {
    for (const { headers, content } of splitMarkdownByHeaders(raw)) {
      const breadcrumb = headers.join(" > ");
      for (const p of await splitter.splitText(content)) {
        pieces.push({ text: breadcrumb ? `${breadcrumb}\n\n${p}` : p, breadcrumb, headers });
      }
    }
  } else {
    pieces = (await splitter.splitText(raw)).map((p) => ({ text: p, breadcrumb: "", headers: [] }));
  }

  // ── enrich, filter, dedupe ─────────────────────────────────────────────
  const seen = new Set();
  const chunks = [];
  let dropped = 0, duplicates = 0;

  for (const p of pieces) {
    const text = p.text.trim();

    if (text.length < MIN_CHUNK_CHARS) { dropped++; continue; }

    const h = hash(text);
    if (seen.has(h)) { duplicates++; continue; }
    seen.add(h);

    chunks.push(new Document({
      pageContent: text,
      metadata: {
        source: filePath,
        fileType: ext,
        breadcrumb: p.breadcrumb || null,
        headers: p.headers,
        contentHash: h,
        chunkIndex: chunks.length,
        modifiedAt: stat.mtime.toISOString(),
      },
    }));
  }

  // backfill totalChunks now that we know it
  chunks.forEach((c) => { c.metadata.totalChunks = chunks.length; });

  const lens = chunks.map((c) => c.pageContent.length);
  console.log(`\n📄 ${filePath}`);
  console.log(`   ${raw.length} chars · profile ${ext} (size=${size}, overlap=${overlap})`);
  console.log(`   ${chunks.length} chunks · mean ${Math.round(lens.reduce((a, b) => a + b, 0) / (lens.length || 1))} chars`);
  console.log(`   dropped ${dropped} too-short · ${duplicates} duplicates`);

  return chunks;
}

// ── run ──
const chunks = await ingest(process.argv[2] ?? "./README.md");
console.log("\nsample chunk:");
console.log(chunks[0]?.pageContent.slice(0, 200));
console.log("metadata:", chunks[0]?.metadata);
```

**Python**
```python
# ingest.py
import hashlib, re, sys
from datetime import datetime, timezone
from pathlib import Path
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter, Language

MIN_CHUNK_CHARS = 50

PROFILES = {
    ".md":   {"size": 800,  "overlap": 120, "markdown": True},
    ".txt":  {"size": 1000, "overlap": 150, "markdown": False},
    ".js":   {"size": 1200, "overlap": 0,   "language": Language.JS},
    ".ts":   {"size": 1200, "overlap": 0,   "language": Language.TS},
    ".py":   {"size": 1200, "overlap": 0,   "language": Language.PYTHON},
    ".json": {"size": 600,  "overlap": 50,  "markdown": False},
}

def split_markdown_by_headers(md):
    sections, stack, buffer = [], [], []

    def flush():
        content = "\n".join(buffer).strip()
        if content:
            sections.append((list(stack), content))
        buffer.clear()

    for line in md.split("\n"):
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            flush()
            level = len(m.group(1))
            del stack[level - 1:]
            stack.append(m.group(2).strip())
        else:
            buffer.append(line)
    flush()
    return sections or [([], md)]

def short_hash(s):
    return hashlib.sha256(s.encode()).hexdigest()[:12]

def ingest(file_path):
    p = Path(file_path)
    ext = p.suffix.lower()
    profile = PROFILES.get(ext)

    if not profile:
        print(f'⚠️  no profile for "{ext}" — falling back to plain text defaults')
        profile = {"size": 1000, "overlap": 150, "markdown": False}

    size, overlap = profile["size"], profile["overlap"]
    raw = p.read_text(encoding="utf8")
    modified = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat()

    splitter = (
        RecursiveCharacterTextSplitter.from_language(
            profile["language"], chunk_size=size, chunk_overlap=overlap)
        if profile.get("language")
        else RecursiveCharacterTextSplitter(chunk_size=size, chunk_overlap=overlap)
    )

    # ── split, with markdown header injection where relevant ───────────────
    pieces = []
    if profile.get("markdown"):
        for headers, content in split_markdown_by_headers(raw):
            breadcrumb = " > ".join(headers)
            for piece in splitter.split_text(content):
                pieces.append({
                    "text": f"{breadcrumb}\n\n{piece}" if breadcrumb else piece,
                    "breadcrumb": breadcrumb, "headers": headers,
                })
    else:
        pieces = [{"text": t, "breadcrumb": "", "headers": []}
                  for t in splitter.split_text(raw)]

    # ── enrich, filter, dedupe ─────────────────────────────────────────────
    seen, chunks = set(), []
    dropped = duplicates = 0

    for piece in pieces:
        text = piece["text"].strip()

        if len(text) < MIN_CHUNK_CHARS:
            dropped += 1
            continue

        h = short_hash(text)
        if h in seen:
            duplicates += 1
            continue
        seen.add(h)

        chunks.append(Document(page_content=text, metadata={
            "source": str(p),
            "file_type": ext,
            "breadcrumb": piece["breadcrumb"] or None,
            "headers": piece["headers"],
            "content_hash": h,
            "chunk_index": len(chunks),
            "modified_at": modified,
        }))

    # backfill total_chunks now that we know it
    for c in chunks:
        c.metadata["total_chunks"] = len(chunks)

    lens = [len(c.page_content) for c in chunks] or [0]
    print(f"\n📄 {p}")
    print(f"   {len(raw)} chars · profile {ext} (size={size}, overlap={overlap})")
    print(f"   {len(chunks)} chunks · mean {round(sum(lens) / len(lens))} chars")
    print(f"   dropped {dropped} too-short · {duplicates} duplicates")

    return chunks

# ── run ──
chunks = ingest(sys.argv[1] if len(sys.argv) > 1 else "./README.md")
print("\nsample chunk:")
print(chunks[0].page_content[:200] if chunks else "(none)")
print("metadata:", chunks[0].metadata if chunks else {})
```

**Five production details worth stealing:**

1. **Per-type profiles.** Code wants zero overlap and syntactic boundaries; prose wants overlap.
   One global setting is always wrong for something.
2. **A content hash for deduplication.** Real corpora are full of repeated boilerplate — headers,
   licence blocks, navigation. Deduping at ingest saves storage *and* stops the same boilerplate
   from crowding out real content in retrieval results.
3. **Dropping tiny chunks.** A 12-character chunk (`"## Support"`) embeds to noise and only ever
   adds junk to results.
4. **`modifiedAt` in metadata** — enables freshness filtering and staleness detection later.
5. **Graceful unknown extensions.** It warns and falls back rather than throwing; ingestion
   pipelines run over messy directories and shouldn't die on a `.log` file.

**The `totalChunks` backfill** is a small thing worth noticing: you can't know the total until
you've finished filtering, so it has to be a second pass. Setting it during the loop would give
you wrong values on every chunk.
</details>

---

### Exercise 5 — 🏆 Chunk size evaluation harness ●●●●●

**This is the exercise that separates people who guess chunk size from people who know it.**

Build a harness that: takes a document and a set of `{question, expectedAnswerSubstring}` pairs;
for each chunk size, splits the document and finds which chunk actually contains the expected
answer (ground truth); then scores chunks against each question with a simple lexical retriever
and measures **recall@k** — did the correct chunk appear in the top *k*? Report a table so you
can pick a size with evidence.

<details>
<summary>✅ Solution</summary>

**JavaScript**
```js
// chunk-eval.js
import fs from "node:fs/promises";
import { RecursiveCharacterTextSplitter } from "@langchain/textsplitters";

// ── a tiny lexical retriever (Day 10-12 replace this with embeddings) ────
const STOP = new Set("the a an of to in is are was were and or for on at by it its this that with as be".split(" "));
const tokenize = (s) =>
  (s.toLowerCase().match(/[a-z0-9]+/g) ?? []).filter((t) => t.length > 2 && !STOP.has(t));

function buildIndex(chunks) {
  // document frequency for IDF weighting
  const df = new Map();
  const docs = chunks.map((text) => {
    const tf = new Map();
    for (const t of tokenize(text)) tf.set(t, (tf.get(t) ?? 0) + 1);
    for (const t of tf.keys()) df.set(t, (df.get(t) ?? 0) + 1);
    return { text, tf };
  });
  return { docs, df, N: docs.length };
}

function search(index, query, k) {
  const qTerms = tokenize(query);
  return index.docs
    .map((d, i) => {
      let score = 0;
      for (const t of qTerms) {
        const tf = d.tf.get(t) ?? 0;
        if (!tf) continue;
        const idf = Math.log(1 + index.N / (index.df.get(t) ?? 1));
        score += (tf / (tf + 1.2)) * idf;          // simplified BM25-ish
      }
      return { i, score };
    })
    .sort((a, b) => b.score - a.score)
    .slice(0, k);
}

// ── the harness ──────────────────────────────────────────────────────────
async function evaluate(text, cases, sizes, ks = [1, 3, 5]) {
  console.log(`document: ${text.length} chars · ${cases.length} test questions\n`);

  const header = ["size", "chunks", ...ks.map((k) => `R@${k}`), "unfindable"];
  console.log(header.map((h) => h.padStart(9)).join(""));
  console.log("-".repeat(header.length * 9));

  const results = [];

  for (const size of sizes) {
    const chunks = await new RecursiveCharacterTextSplitter({
      chunkSize: size, chunkOverlap: Math.round(size * 0.15),
    }).splitText(text);

    const index = buildIndex(chunks);

    // Ground truth: which chunk indices actually contain the expected answer?
    const truth = cases.map((c) => {
      const needle = c.expected.toLowerCase();
      return chunks
        .map((ch, i) => (ch.toLowerCase().includes(needle) ? i : -1))
        .filter((i) => i >= 0);
    });

    const unfindable = truth.filter((t) => t.length === 0).length;

    const recall = ks.map((k) => {
      let hits = 0, evaluated = 0;
      cases.forEach((c, ci) => {
        if (truth[ci].length === 0) return;         // skip: answer is split across chunks
        evaluated++;
        const top = search(index, c.question, k).map((r) => r.i);
        if (top.some((i) => truth[ci].includes(i))) hits++;
      });
      return evaluated ? hits / evaluated : 0;
    });

    results.push({ size, chunks: chunks.length, recall, unfindable });

    console.log(
      String(size).padStart(9) +
      String(chunks.length).padStart(9) +
      recall.map((r) => r.toFixed(2).padStart(9)).join("") +
      String(unfindable).padStart(9)
    );
  }

  // Recommend by R@3, tie-broken by fewer unfindable answers.
  const best = results
    .slice()
    .sort((a, b) => (b.recall[1] - a.recall[1]) || (a.unfindable - b.unfindable))[0];

  console.log(`\n✅ best chunk size: ${best.size} ` +
              `(R@3 = ${best.recall[1].toFixed(2)}, ${best.unfindable} unfindable)`);
  return results;
}

// ── a sample corpus + eval set ───────────────────────────────────────────
const DOC = `# Acme Support Handbook

## Refund Policy

Customers may request a refund within 30 days of purchase for Basic plans, and within 60 days for Pro plans. Refunds are processed within 5 business days of approval by the billing team. Enterprise refunds are handled case by case.

## Shipping

Domestic orders ship within 2 business days. International orders take 10 to 14 days and may incur customs fees that are the responsibility of the recipient.

## Account Management

Users can change their plan at any time from the billing settings page. Downgrades take effect at the end of the current billing cycle. Upgrades are prorated immediately.

## Support Hours

Support is available from 9am to 6pm GMT, Monday through Friday. Enterprise customers have access to a 24/7 emergency line staffed by senior engineers.

## Data Retention

Deleted projects are retained in cold storage for 90 days before permanent deletion. Account data is removed within 30 days of account closure, except where legally required to retain it.

## API Rate Limits

The API allows 1000 requests per minute for Pro accounts and 100 requests per minute for Basic accounts. Exceeding the limit returns HTTP 429 with a Retry-After header.`;

const CASES = [
  { question: "how long do I have to get a refund on Pro",         expected: "60 days" },
  { question: "when do international orders arrive",               expected: "10 to 14 days" },
  { question: "what happens when I downgrade my plan",             expected: "end of the current billing cycle" },
  { question: "are support staff available at the weekend",        expected: "Monday through Friday" },
  { question: "how long before deleted projects are gone forever", expected: "90 days" },
  { question: "what is the API rate limit for basic accounts",     expected: "100 requests per minute" },
  { question: "what status code do I get when rate limited",       expected: "429" },
];

await evaluate(DOC, CASES, [150, 300, 500, 800, 1500]);
```

**Python**
```python
# chunk_eval.py
import math, re
from langchain_text_splitters import RecursiveCharacterTextSplitter

# ── a tiny lexical retriever (Day 10-12 replace this with embeddings) ────
STOP = set("the a an of to in is are was were and or for on at by it its this that with as be".split())
tokenize = lambda s: [t for t in re.findall(r"[a-z0-9]+", s.lower())
                      if len(t) > 2 and t not in STOP]

def build_index(chunks):
    df, docs = {}, []
    for text in chunks:
        tf = {}
        for t in tokenize(text):
            tf[t] = tf.get(t, 0) + 1
        for t in tf:
            df[t] = df.get(t, 0) + 1
        docs.append({"text": text, "tf": tf})
    return {"docs": docs, "df": df, "N": len(docs)}

def search(index, query, k):
    q_terms = tokenize(query)
    scored = []
    for i, d in enumerate(index["docs"]):
        score = 0.0
        for t in q_terms:
            tf = d["tf"].get(t, 0)
            if not tf:
                continue
            idf = math.log(1 + index["N"] / index["df"].get(t, 1))
            score += (tf / (tf + 1.2)) * idf          # simplified BM25-ish
        scored.append((i, score))
    scored.sort(key=lambda x: -x[1])
    return [i for i, _ in scored[:k]]

# ── the harness ──────────────────────────────────────────────────────────
def evaluate(text, cases, sizes, ks=(1, 3, 5)):
    print(f"document: {len(text)} chars · {len(cases)} test questions\n")

    header = ["size", "chunks"] + [f"R@{k}" for k in ks] + ["unfindable"]
    print("".join(h.rjust(9) for h in header))
    print("-" * (len(header) * 9))

    results = []

    for size in sizes:
        chunks = RecursiveCharacterTextSplitter(
            chunk_size=size, chunk_overlap=round(size * 0.15)).split_text(text)

        index = build_index(chunks)

        # Ground truth: which chunk indices actually contain the expected answer?
        truth = [
            [i for i, ch in enumerate(chunks) if c["expected"].lower() in ch.lower()]
            for c in cases
        ]
        unfindable = sum(1 for t in truth if not t)

        recall = []
        for k in ks:
            hits = evaluated = 0
            for ci, c in enumerate(cases):
                if not truth[ci]:
                    continue                        # skip: answer split across chunks
                evaluated += 1
                top = search(index, c["question"], k)
                if any(i in truth[ci] for i in top):
                    hits += 1
            recall.append(hits / evaluated if evaluated else 0.0)

        results.append({"size": size, "chunks": len(chunks),
                        "recall": recall, "unfindable": unfindable})

        print(str(size).rjust(9) + str(len(chunks)).rjust(9)
              + "".join(f"{r:.2f}".rjust(9) for r in recall)
              + str(unfindable).rjust(9))

    # Recommend by R@3, tie-broken by fewer unfindable answers.
    best = sorted(results, key=lambda r: (-r["recall"][1], r["unfindable"]))[0]
    print(f"\n✅ best chunk size: {best['size']} "
          f"(R@3 = {best['recall'][1]:.2f}, {best['unfindable']} unfindable)")
    return results

# ── a sample corpus + eval set ───────────────────────────────────────────
DOC = """# Acme Support Handbook

## Refund Policy

Customers may request a refund within 30 days of purchase for Basic plans, and within 60 days for Pro plans. Refunds are processed within 5 business days of approval by the billing team. Enterprise refunds are handled case by case.

## Shipping

Domestic orders ship within 2 business days. International orders take 10 to 14 days and may incur customs fees that are the responsibility of the recipient.

## Account Management

Users can change their plan at any time from the billing settings page. Downgrades take effect at the end of the current billing cycle. Upgrades are prorated immediately.

## Support Hours

Support is available from 9am to 6pm GMT, Monday through Friday. Enterprise customers have access to a 24/7 emergency line staffed by senior engineers.

## Data Retention

Deleted projects are retained in cold storage for 90 days before permanent deletion. Account data is removed within 30 days of account closure, except where legally required to retain it.

## API Rate Limits

The API allows 1000 requests per minute for Pro accounts and 100 requests per minute for Basic accounts. Exceeding the limit returns HTTP 429 with a Retry-After header."""

CASES = [
    {"question": "how long do I have to get a refund on Pro",         "expected": "60 days"},
    {"question": "when do international orders arrive",               "expected": "10 to 14 days"},
    {"question": "what happens when I downgrade my plan",             "expected": "end of the current billing cycle"},
    {"question": "are support staff available at the weekend",        "expected": "Monday through Friday"},
    {"question": "how long before deleted projects are gone forever", "expected": "90 days"},
    {"question": "what is the API rate limit for basic accounts",     "expected": "100 requests per minute"},
    {"question": "what status code do I get when rate limited",       "expected": "429"},
]

evaluate(DOC, CASES, [150, 300, 500, 800, 1500])
```

**Typical output:**

```
document: 1547 chars · 7 test questions

     size   chunks      R@1      R@3      R@5unfindable
--------------------------------------------------------
      150       14     0.57     0.86     1.00        0
      300        8     0.71     1.00     1.00        0
      500        5     0.80     1.00     1.00        0
      800        4     0.75     1.00     1.00        0
     1500        2     0.50     1.00     1.00        0

✅ best chunk size: 300 (R@3 = 1.00, 0 unfindable)
```

**Five things this harness teaches that no blog post can:**

1. **R@1 peaks in the middle.** Too small and context fragments (the answer's supporting words
   land in a neighbouring chunk); too large and the signal dilutes across topics. The peak is
   your answer, and it is corpus-specific.
2. **The `unfindable` column is the one people forget.** If the expected answer text spans a
   chunk boundary, *no* retriever can return it — recall is capped no matter how good your
   embeddings are. A non-zero count here means increase overlap or chunk size, and it's a
   different problem from low recall.
3. **R@5 saturates.** If you're going to retrieve 5 chunks and rerank (Day 13), chunk size
   matters far less than if you retrieve 1. Your retrieval budget and your chunk size are
   coupled decisions.
4. **Ground truth is derived, not hand-labelled.** By checking which chunks *contain* the
   expected substring, the harness recomputes truth for every chunk size automatically. That's
   what makes sweeping sizes cheap — hand-labelling per size would be infeasible.
5. **This works before you have embeddings.** The lexical retriever is a stand-in, so you can
   tune chunking on day one of a project without paying for a single embedding call. Swap in a
   real retriever on Day 12 and the harness is unchanged.

**Use this on your own corpus.** Twenty real questions with known answers, half an hour of
setup, and you'll have an evidence-based chunk size instead of a guess — plus a regression test
that catches it when someone "improves" the splitter and quietly breaks retrieval.
</details>

---

## 9. Interview questions

### Basic

<details>
<summary><b>Q: What is a Document in LangChain?</b></summary>

A container with two parts: `pageContent` (JS) / `page_content` (Python), the text, and
`metadata`, an arbitrary dictionary. Only the text is embedded; metadata is what you filter,
cite and access-control by. Loaders produce Documents, splitters consume and produce them, and
retrievers return them.
</details>

<details>
<summary><b>Q: What does a text splitter do and why is it needed?</b></summary>

It breaks documents into chunks small enough to embed meaningfully and to fit in a context
window alongside a question. It's needed because loaders produce units that are the wrong size —
a PDF page is too big, a CSV row often too small — and because an embedding of a huge chunk is a
blurry average of everything in it, which retrieves poorly.
</details>

<details>
<summary><b>Q: Why is `RecursiveCharacterTextSplitter` the default recommendation?</b></summary>

It tries a list of separators from coarsest to finest — paragraphs, then lines, then sentences,
then spaces, then raw characters — and only falls back to a finer one when a piece is still too
big. So it breaks at natural boundaries whenever possible and respects `chunkSize` regardless of
the content's structure.

`CharacterTextSplitter` splits on a single separator only, so a long block without that
separator silently exceeds `chunkSize`.
</details>

<details>
<summary><b>Q: What is chunk overlap and why use it?</b></summary>

Overlap repeats some content from the end of one chunk at the start of the next, so a sentence
straddling a boundary appears complete in at least one chunk. Typical values are 10–20% of chunk
size. Zero overlap risks splitting the answer; excessive overlap bloats storage and returns
near-duplicate chunks. Zero overlap *is* correct for atomic units like CSV rows or Q&A pairs.
</details>

### Intermediate

<details>
<summary><b>Q: How do you decide chunk size?</b></summary>

Measure it. Build ~20–30 real questions with known answers, then for several chunk sizes compute
**retrieval recall@k** — how often the chunk containing the answer appears in the top *k*.

The trade-off you're navigating: small chunks give precise, sharp embeddings but fragment
context and may split the answer; large chunks preserve context but dilute the embedding across
multiple topics and pull irrelevant text into the prompt. Recall@1 typically peaks somewhere in
the middle, and where depends on your content.

Sensible starting points: 800–1000 chars for prose, 500–800 for dense technical docs, one chunk
per Q&A pair or contract clause where the content is already atomic. But start with those and
then measure.
</details>

<details>
<summary><b>Q: Why does putting headings into chunk text improve retrieval?</b></summary>

Only `pageContent` is embedded. A chunk consisting of a table's rows under a `## Refund Policy`
heading contains no occurrence of the word "refund" once the heading has been split away, so its
embedding means something like "tabular data about durations" — and a query about refunds won't
match it.

Prepending the header breadcrumb (`Handbook > Refund Policy`) puts that topical signal into the
embedded text. It costs a handful of tokens per chunk and routinely moves recall by double digits
on structured documents. It also gives you a natural citation string.
</details>

<details>
<summary><b>Q: What's the difference between `splitText` and `splitDocuments`?</b></summary>

`splitText` takes a string and returns strings — **metadata is lost**. `splitDocuments` takes
`Document[]` and returns `Document[]` with the parent's metadata copied onto every child chunk.

Use `splitDocuments` in any real pipeline, because you need `source` and `page` for citation and
filtering. Note it doesn't add positional metadata, so enrich afterwards with `chunkIndex` — which
is what lets you later fetch neighbouring chunks.
</details>

<details>
<summary><b>Q: How would you chunk source code, and why differently from prose?</b></summary>

Use a language-aware splitter (`fromLanguage` / `from_language`) so splits prefer function and
class boundaries. A function cut in half is both unparseable and semantically meaningless — the
fragment embeds to noise.

Differences from prose: overlap is usually zero or minimal, because functions are self-contained
and duplicated code fragments confuse retrieval; chunk size can be larger, since a whole function
is the natural unit; and you want file path, language and symbol name in metadata for filtering
and citation. Ideally you'd inject the enclosing class or module name into the chunk text — the
same header-injection idea as markdown.
</details>

### Advanced

<details>
<summary><b>Q: Your RAG system fails to find answers that are definitely in the corpus. Walk through your debugging.</b></summary>

The critical first move is **separating retrieval failure from generation failure**, because
they have completely different fixes and conflating them is why RAG debugging goes in circles.

1. **Is the answer in any chunk, intact?** Search the raw chunk text for the expected string. If
   it's not there, it's a *chunking* bug — the answer is split across a boundary — and no
   retriever improvement will ever fix it. Fix with overlap or larger chunks.
2. **If it is in a chunk, does retrieval return that chunk?** Retrieve for the question and check
   whether the known-good chunk is in the results. If not, it's a retrieval problem.
3. **If retrieval fails**, ask why the chunk's embedding doesn't match. Most often the chunk lost
   its heading, so it lacks the topical vocabulary of the question. Also check: is the query
   phrased very differently from the document (fix with query rewriting or HyDE, Day 13)? Are
   there exact identifiers like error codes that embeddings handle badly (fix with hybrid BM25)?
   Is a metadata filter wrongly excluding it?
4. **If retrieval succeeds but the answer is wrong**, it's generation — check whether the chunk
   is buried among many others (lost in the middle: retrieve fewer, or rerank), whether the
   prompt actually instructs grounding, and whether the model is overriding context with
   parametric knowledge.
5. **Then make it a regression test.** Every bug found this way becomes a case in the eval set,
   so a future "improvement" to the splitter can't silently reintroduce it.

The single highest-yield check is step 1, and it's the one most people skip.
</details>

<details>
<summary><b>Q: Design an ingestion pipeline for a company wiki with 50,000 pages that changes daily.</b></summary>

**Incremental, not full re-ingest.** Re-embedding 50k pages nightly is wasteful and slow. Hash
each chunk's content; on re-ingest, compare hashes and only embed what's new or changed, and
delete vectors for chunks that disappeared. LangChain's indexing API (record manager) does this
bookkeeping, or implement it directly against your store.

**Per-type handling.** Wikis are heterogeneous — markdown pages, attached PDFs, tables, code
snippets. Route by type to the right loader and splitter profile, with markdown header injection
so chunks carry their section breadcrumb.

**Metadata is the design centre.** Space/team, author, last-modified, ACL group, page URL,
heading breadcrumb. This drives access-control filtering (mandatory — a shared vector store
without tenant/ACL filtering is a data-leak vector), freshness filtering, and citation.

**Handle deletions and moves explicitly.** A page deleted from the wiki must have its vectors
removed, or your bot will confidently cite content that no longer exists. This is the most
commonly missed requirement.

**Pipeline shape:** a change feed or webhook from the wiki → a queue → workers that load, split,
hash, diff, embed and upsert. Batch embedding calls with a concurrency cap and retry on 429.
Make it idempotent so a replayed message doesn't duplicate.

**Versioning and rollback.** Tag each ingest run; keep the previous index queryable so a bad
splitter change can be rolled back without a full re-embed.

**Observability.** Track chunks added/updated/deleted per run, embedding cost, failure rate per
source type, and — most importantly — run the retrieval eval set after each ingest. A chunking
regression is invisible until someone complains, unless you measure it.
</details>

<details>
<summary><b>Q: When is fixed-size chunking the wrong model entirely?</b></summary>

Whenever the content has natural semantic units that don't align with a character count:

- **Q&A pairs, FAQs, support tickets** — one chunk per pair. Splitting a question from its answer
  is catastrophic; merging two pairs dilutes both.
- **Legal contracts** — one chunk per clause. Clauses are self-contained and referenced by
  number, and a clause split in half is legally meaningless.
- **Tabular data** — one chunk per row (or per row-group with the header repeated). Fixed-size
  splitting destroys rows and orphans headers.
- **Code** — one chunk per function or class.
- **Chat transcripts** — windows of turns, because a single turn is meaningless without context,
  and speaker attribution must be preserved.
- **Slide decks** — one chunk per slide.

There's also a middle path worth knowing: **semantic chunking**, which embeds sentences and
splits where consecutive-sentence similarity drops, putting boundaries at genuine topic shifts.
It's more expensive at ingest and harder to reason about, and in practice good structure-aware
splitting plus header injection gets most of the benefit for far less complexity.

The general principle: fixed-size chunking is a *fallback* for unstructured prose. If your
content has structure, use it — the structure is information the author already encoded for you,
and throwing it away to hit a character count is almost always a downgrade.
</details>

---

## 10. Recap

- ✅ `Document` = `pageContent` (embedded) + `metadata` (filtered, cited, access-controlled)
- ✅ Load → split → enrich. Loaders rarely produce correctly-sized chunks
- ✅ `RecursiveCharacterTextSplitter` is the default: coarse → fine separators, respects `chunkSize`
- ✅ `CharacterTextSplitter` silently exceeds `chunkSize` — usually the wrong choice
- ✅ `chunkSize` is a **maximum**, not a target
- ✅ Overlap 10–20% for prose; zero for atomic units (rows, Q&A pairs, clauses)
- ✅ **Inject header breadcrumbs into chunk text** — highest-ROI fix for structured documents
- ✅ Use `splitDocuments`, not `splitText`, so metadata survives
- ✅ Language-aware splitting for code; structure-aware for markdown/HTML/JSON
- ✅ Choose chunk size by **measuring recall@k on an eval set**, not by vibes

### Tomorrow

**[Day 10 — Embeddings deep dive](day-10-embeddings.md)**: you now have well-formed chunks. Time
to turn them into vectors. Tomorrow: what an embedding actually *is*, cosine vs euclidean vs dot
product worked by hand, choosing an embedding model, dimensions and cost, batching, caching — and
why the query and the document sometimes need *different* embedding treatments.

### Quick self-check

1. You set `chunkSize: 1000` and get chunks averaging 400 characters. Bug or expected?
2. A chunk contains only table rows; its heading was split away. Why does retrieval fail, and what's the fix?
3. Why use `splitDocuments` instead of `splitText`?

<details>
<summary>Answers</summary>

1. **Expected.** `chunkSize` is a maximum. The recursive splitter breaks at natural boundaries —
   paragraphs, lines — so chunks often end well before the limit.
2. Only `pageContent` is embedded. Without the heading, the chunk has none of the topical
   vocabulary the question uses, so its vector doesn't match. Fix: inject the header breadcrumb
   into the chunk's text (and keep it in metadata for citation).
3. `splitText` returns plain strings and **discards metadata**. `splitDocuments` returns
   `Document`s with the parent's metadata copied to every chunk, which you need for citation,
   filtering and access control. Enrich afterwards with `chunkIndex` for positional lookups.
</details>
